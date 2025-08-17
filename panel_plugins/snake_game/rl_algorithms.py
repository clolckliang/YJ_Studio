# panel_plugins/snake_game/rl_algorithms.py
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import random
from collections import deque
from typing import List, Tuple
import yaml
# ==============================================================================
#  通用辅助函数
# ==============================================================================
def is_collision(point: Tuple[int, int], game_state: 'GameState'):
    """检查一个点是否会发生碰撞"""
    if not (0 <= point[0] < game_state.grid_size and 0 <= point[1] < game_state.grid_size):
        return True  # 撞墙
    if point in game_state.snake:
        return True  # 撞自己
    return False

def get_rl_state(game_state: 'GameState') -> np.ndarray:
    """将游戏状态转换为强化学习的输入状态向量"""
    head = game_state.snake[0]
    
    # 定义四个方向的相邻点
    point_l = (head[0], head[1] - 1)
    point_r = (head[0], head[1] + 1)
    point_u = (head[0] - 1, head[1])
    point_d = (head[0] + 1, head[1])
    
    # 当前方向
    dir_l = game_state.direction == 'LEFT'
    dir_r = game_state.direction == 'RIGHT'
    dir_u = game_state.direction == 'UP'
    dir_d = game_state.direction == 'DOWN'

    state = [
        # 危险状态：正前方、右侧、左侧是否有障碍物
        (dir_r and is_collision(point_r, game_state)) or 
        (dir_l and is_collision(point_l, game_state)) or 
        (dir_u and is_collision(point_u, game_state)) or 
        (dir_d and is_collision(point_d, game_state)),

        (dir_u and is_collision(point_r, game_state)) or 
        (dir_d and is_collision(point_l, game_state)) or 
        (dir_l and is_collision(point_u, game_state)) or 
        (dir_r and is_collision(point_d, game_state)),

        (dir_d and is_collision(point_r, game_state)) or 
        (dir_u and is_collision(point_l, game_state)) or 
        (dir_r and is_collision(point_u, game_state)) or 
        (dir_l and is_collision(point_d, game_state)),
        
        # 当前移动方向
        dir_l,
        dir_r,
        dir_u,
        dir_d,
        
        # 食物位置
        game_state.food[1] < head[1],  # food left
        game_state.food[1] > head[1],  # food right
        game_state.food[0] < head[0],  # food up
        game_state.food[0] > head[0]  # food down
    ]
    return np.array(state, dtype=np.float32)

# ==============================================================================
#  DQN (Deep Q-Network)
# ==============================================================================
class DQN_Net(nn.Module):
    def __init__(self, input_size=11, hidden_size=256, output_size=4):
        super().__init__()
        self.linear1 = nn.Linear(input_size, hidden_size)
        self.linear2 = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        x = F.relu(self.linear1(x))
        return self.linear2(x)

class ReplayMemory:
    def __init__(self, capacity):
        self.memory = deque([], maxlen=capacity)

    def push(self, *args):
        self.memory.append(args)

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)

class DQNAgent:
    def __init__(self, grid_size: int, config: dict):
        self.grid_size = grid_size
        self.state_size = 11
        self.action_size = 4
        
        # 从配置字典中读取参数
        self.gamma = config['gamma']
        self.epsilon = config['epsilon_start']
        self.epsilon_min = config['epsilon_end']
        self.epsilon_decay = config['epsilon_decay']
        self.batch_size = config['batch_size']
        
        self.memory = ReplayMemory(config['memory_capacity'])
        self.policy_net = DQN_Net()
        self.target_net = DQN_Net()
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=config['learning_rate'])
        self.loss_fn = nn.MSELoss()
        
        self.training_history = {
            'losses': [], 'rewards': [], 'scores': [], 'epsilons': [], 'episodes': []
        }
        self.current_episode_reward = 0
        self.episode_count = 0

    def remember(self, state, action, reward, next_state, done):
        self.memory.push(state, action, reward, next_state, done)

    def act(self, state: np.ndarray, is_training=True):  # 返回元组，移除 -> int 类型提示
        if is_training and np.random.rand() <= self.epsilon:
            # 返回元组
            return random.randrange(self.action_size), None
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            action_values = self.policy_net(state_tensor)
        action = np.argmax(action_values.cpu().data.numpy())
        # 返回元组
        return int(action), None

    def learn(self):
        if len(self.memory) < self.batch_size:
            return
        minibatch = self.memory.sample(self.batch_size)
        states, actions, rewards, next_states, dones = zip(*minibatch)
        
        states = torch.FloatTensor(np.array(states))
        actions = torch.LongTensor(actions).unsqueeze(1)
        rewards = torch.FloatTensor(rewards).unsqueeze(1)
        next_states = torch.FloatTensor(np.array(next_states))
        dones = torch.BoolTensor(dones).unsqueeze(1)
        
        q_values = self.policy_net(states).gather(1, actions)
        
        with torch.no_grad():
            next_q_values = self.target_net(next_states).max(1)[0].unsqueeze(1)
        
        next_q_values[dones] = 0.0
        expected_q_values = rewards + (self.gamma * next_q_values)
        
        loss = self.loss_fn(q_values, expected_q_values)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        self.training_history['losses'].append(loss.item())
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def record_episode_data(self, episode_reward, score):
        self.episode_count += 1
        self.training_history['episodes'].append(self.episode_count)
        self.training_history['rewards'].append(episode_reward)
        self.training_history['scores'].append(score)
        self.training_history['epsilons'].append(self.epsilon)
        self.current_episode_reward = 0

    def add_reward(self, reward):
        self.current_episode_reward += reward

    def update_target_network(self):
        self.target_net.load_state_dict(self.policy_net.state_dict())

    def save_model(self, file_path):
        torch.save(self.policy_net.state_dict(), file_path)
        print(f"模型已保存至 {file_path}")

    def load_model(self, file_path):
        try:
            self.policy_net.load_state_dict(torch.load(file_path))
            self.update_target_network()
            self.epsilon = self.epsilon_min
            print(f"模型已从 {file_path} 加载")
        except Exception as e:
            print(f"加载模型失败: {e}")

# ==============================================================================
#  PPO (Proximal Policy Optimization)
# ==============================================================================
class ActorCritic_Net(nn.Module):
    def __init__(self, input_size=11, hidden_size=256, output_size=4):
        super().__init__()
        self.shared_layer = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU()
        )
        self.actor = nn.Linear(hidden_size, output_size)  # Policy
        self.critic = nn.Linear(hidden_size, 1)      # Value

    def forward(self, x):
        x = self.shared_layer(x)
        policy_dist = F.softmax(self.actor(x), dim=-1)
        value = self.critic(x)
        return policy_dist, value

class PPOAgent:
    def __init__(self, grid_size: int, config: dict):
        # 从配置字典中读取超参数
        self.gamma = config['gamma']
        self.eps_clip = config['eps_clip']
        self.k_epochs = config['k_epochs']
        
        # 使用配置中的学习率初始化优化器
        self.policy = ActorCritic_Net()
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=config['lr'])
        self.policy_old = ActorCritic_Net()
        self.policy_old.load_state_dict(self.policy.state_dict())
        
        self.loss_fn = nn.MSELoss()
        self.memory = []
        
        # --- 其余部分与之前相同 ---
        self.training_history = {
            'policy_losses': [], 'value_losses': [], 'rewards': [], 'scores': [], 'episodes': []
        }
        self.current_episode_reward = 0
        self.episode_count = 0

    def act(self, state: np.ndarray, is_training=True):
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            dist, _ = self.policy_old(state_tensor)

        if is_training:
            # 先创建分布对象
            categorical_dist = torch.distributions.Categorical(dist)
            # 从分布中采样
            action = categorical_dist.sample()
            # 在分布对象上计算对数概率
            return action.item(), categorical_dist.log_prob(action)
        else:
            return torch.argmax(dist).item(), None

    def remember(self, state, action, reward, next_state, done, log_prob):
        self.memory.append((state, action, reward, next_state, done, log_prob))

    def learn(self):
        if len(self.memory) < self.batch_size:
            return

        # Monte Carlo estimate of rewards:
        rewards = []
        discounted_reward = 0
        for _, _, reward, _, done, _ in reversed(self.memory):
            if done:
                discounted_reward = 0
            discounted_reward = reward + (self.gamma * discounted_reward)
            rewards.insert(0, discounted_reward)
        
        # Normalizing the rewards:
        rewards = torch.tensor(rewards, dtype=torch.float32)
        rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-7)

        # convert list to tensor
        old_states = torch.FloatTensor(np.array([t[0] for t in self.memory]))
        old_actions = torch.LongTensor([t[1] for t in self.memory])
        old_log_probs = torch.stack([t[5] for t in self.memory]).detach()

        total_policy_loss = 0
        total_value_loss = 0

        # Optimize policy for K epochs:
        for _ in range(self.k_epochs):
            # Evaluating old actions and values :
            logprobs, state_values = self.policy(old_states)
            logprobs = logprobs.gather(1, old_actions.unsqueeze(-1)).squeeze(-1)
            state_values = state_values.squeeze(-1)
            
            # Finding the ratio (pi_theta / pi_theta__old):
            ratios = torch.exp(logprobs - old_log_probs.detach())

            # Finding Surrogate Loss:
            advantages = rewards - state_values.detach()   
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1-self.eps_clip, 1+self.eps_clip) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()
            value_loss = self.loss_fn(state_values, rewards)
            
            loss = policy_loss + 0.5 * value_loss
            
            # take gradient step
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

            total_policy_loss += policy_loss.item()
            total_value_loss += value_loss.item()
        
        # Copy new weights into old policy:
        self.policy_old.load_state_dict(self.policy.state_dict())
        self.memory = []

        # Log losses
        self.training_history['policy_losses'].append(total_policy_loss / self.k_epochs)
        self.training_history['value_losses'].append(total_value_loss / self.k_epochs)

    def record_episode_data(self, episode_reward, score):
        self.episode_count += 1
        self.training_history['episodes'].append(self.episode_count)
        self.training_history['rewards'].append(episode_reward)
        self.training_history['scores'].append(score)
        self.current_episode_reward = 0

    def add_reward(self, reward):
        self.current_episode_reward += reward

    def save_model(self, file_path):
        torch.save(self.policy.state_dict(), file_path)
        print(f"PPO模型已保存至 {file_path}")

    def load_model(self, file_path):
        try:
            self.policy.load_state_dict(torch.load(file_path))
            self.policy_old.load_state_dict(self.policy.state_dict())
            print(f"PPO模型已从 {file_path} 加载")
        except Exception as e:
            print(f"加载PPO模型失败: {e}")

# ==============================================================================
#  A2C (Advantage Actor-Critic)
# ==============================================================================
class A2CAgent:
    def __init__(self, grid_size: int, config: dict):
        # 从配置字典中读取超参数
        self.gamma = config['gamma']

        # 使用配置中的学习率初始化优化器
        self.policy = ActorCritic_Net()
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=config['lr'])
        self.loss_fn = nn.MSELoss()
        
        # --- 其余部分与之前相同 ---
        self.training_history = {
            'policy_losses': [], 'value_losses': [], 'rewards': [], 'scores': [], 'episodes': []
        }
        self.current_episode_reward = 0
        self.episode_count = 0
        self.memory = []

    def act(self, state: np.ndarray, is_training=True):
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            dist, _ = self.policy(state_tensor)

        if is_training:
            # 先创建分布对象
            categorical_dist = torch.distributions.Categorical(dist)
            # 从分布中采样
            action = categorical_dist.sample()
            # 在分布对象上计算对数概率
            return action.item(), categorical_dist.log_prob(action)
        else:
            return torch.argmax(dist).item(), None

    def remember(self, state, action, reward, next_state, done, log_prob):
        # A2C can update step-by-step, so memory is just for one step
        self.memory = [state, action, reward, next_state, done, log_prob]

    def learn(self):
        if not self.memory:
            return

        state, action, reward, next_state, done, log_prob = self.memory
        
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        next_state_tensor = torch.FloatTensor(next_state).unsqueeze(0)
        reward_tensor = torch.FloatTensor([reward])
        
        _, state_value = self.policy(state_tensor)
        _, next_state_value = self.policy(next_state_tensor)
        
        if done:
            next_state_value = torch.FloatTensor([0])

        # Calculate Advantage and loss
        advantage = reward_tensor + self.gamma * next_state_value - state_value
        
        policy_loss = -log_prob * advantage.detach()
        value_loss = self.loss_fn(state_value, reward_tensor + self.gamma * next_state_value.detach())
        
        loss = policy_loss + 0.5 * value_loss
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        self.training_history['policy_losses'].append(policy_loss.item())
        self.training_history['value_losses'].append(value_loss.item())
        self.memory = []

    def record_episode_data(self, episode_reward, score):
        self.episode_count += 1
        self.training_history['episodes'].append(self.episode_count)
        self.training_history['rewards'].append(episode_reward)
        self.training_history['scores'].append(score)
        self.current_episode_reward = 0

    def add_reward(self, reward):
        self.current_episode_reward += reward

    def save_model(self, file_path):
        torch.save(self.policy.state_dict(), file_path)
        print(f"A2C模型已保存至 {file_path}")

    def load_model(self, file_path):
        try:
            self.policy.load_state_dict(torch.load(file_path))
            print(f"A2C模型已从 {file_path} 加载")
        except Exception as e:
            print(f"加载A2C模型失败: {e}")
