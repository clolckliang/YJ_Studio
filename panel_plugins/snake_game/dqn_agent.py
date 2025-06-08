# dqn_agent.py

import numpy as np
from collections import deque
import random
from typing import List, Tuple

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# --- 神经网络模型 ---
class DQN(nn.Module):
    """
    一个简单的前馈神经网络，用于逼近Q函数。
    输入层大小为11（根据状态向量定义），输出层大小为4（对应四个动作）。
    """
    def __init__(self, input_size=11, hidden_size=256, output_size=4):
        super().__init__()
        self.linear1 = nn.Linear(input_size, hidden_size)
        self.linear2 = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        x = F.relu(self.linear1(x))
        x = self.linear2(x)
        return x

# --- 经验回放池 ---
class ReplayMemory:
    """一个固定大小的循环队列，用于存储经验元组。"""
    def __init__(self, capacity):
        self.memory = deque([], maxlen=capacity)

    def push(self, *args):
        """保存一个经验 (state, action, reward, next_state, done)"""
        self.memory.append(args)

    def sample(self, batch_size):
        """从记忆库中随机抽取一批经验。"""
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)

# --- DQN智能体 ---
class DQNAgent:
    def __init__(self, grid_size: int, learning_rate=0.001, gamma=0.9,
                 epsilon_start=1.0, epsilon_end=0.01, epsilon_decay=0.995,
                 memory_capacity=10000, batch_size=128):
        
        self.grid_size = grid_size
        self.state_size = 11  # 状态向量的大小
        self.action_size = 4  # 动作数量: 上, 下, 左, 右

        # 超参数
        self.gamma = gamma  # 折扣因子
        self.epsilon = epsilon_start  # 探索率
        self.epsilon_min = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.learning_rate = learning_rate
        self.batch_size = batch_size

        # 经验回放池
        self.memory = ReplayMemory(memory_capacity)

        # 神经网络
        self.policy_net = DQN(self.state_size, 256, self.action_size)
        self.target_net = DQN(self.state_size, 256, self.action_size)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()  # 目标网络不进行训练

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.learning_rate)
        self.loss_fn = nn.MSELoss()

    def remember(self, state, action, reward, next_state, done):
        """将经验存入回放池。"""
        self.memory.push(state, action, reward, next_state, done)

    def act(self, state: np.ndarray, is_training=True) -> int:
        """
        根据当前状态，使用ε-贪婪策略选择一个动作。
        返回动作的索引 (0:上, 1:下, 2:左, 3:右)。
        """
        if is_training and np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)  # 探索：随机选择一个动作
        
        # 利用：选择Q值最高的动作
        state_tensor = torch.FloatTensor(state).unsqueeze(0) # 增加一个batch维度
        with torch.no_grad():
            action_values = self.policy_net(state_tensor)
        return np.argmax(action_values.cpu().data.numpy())

    def learn(self):
        """从经验池中采样进行学习，更新网络权重。"""
        if len(self.memory) < self.batch_size:
            return  # 记忆库中的经验不足

        # 从记忆库中随机采样一批经验
        minibatch = self.memory.sample(self.batch_size)
        
        # 将经验元组解压
        states, actions, rewards, next_states, dones = zip(*minibatch)

        # 将数据转换为PyTorch张量
        states = torch.FloatTensor(np.array(states))
        actions = torch.LongTensor(actions).unsqueeze(1)
        rewards = torch.FloatTensor(rewards).unsqueeze(1)
        next_states = torch.FloatTensor(np.array(next_states))
        dones = torch.BoolTensor(dones).unsqueeze(1)

        # --- 计算Q值 ---
        # 1. 计算当前状态的Q值 (Q(s, a))
        #    网络会输出所有动作的Q值，我们只选择实际执行过的动作的Q值
        q_values = self.policy_net(states).gather(1, actions)

        # 2. 计算下一状态的最大Q值 (max Q(s', a'))
        #    使用 target_net 来增加稳定性
        with torch.no_grad():
            next_q_values = self.target_net(next_states).max(1)[0].unsqueeze(1)
        
        # 如果游戏结束 (done=True)，则下一状态的Q值为0
        next_q_values[dones] = 0.0

        # 3. 计算期望的Q值 (目标Q值)
        #    Target Q = r + γ * max Q(s', a')
        expected_q_values = rewards + (self.gamma * next_q_values)

        # --- 计算损失并更新网络 ---
        loss = self.loss_fn(q_values, expected_q_values)
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        # 更新探索率ε
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def update_target_network(self):
        """定期将策略网络的权重复制到目标网络。"""
        self.target_net.load_state_dict(self.policy_net.state_dict())

    def save_model(self, file_path='dqn_snake_model.pth'):
        """保存模型权重。"""
        torch.save(self.policy_net.state_dict(), file_path)
        print(f"模型已保存至 {file_path}")

    def load_model(self, file_path='dqn_snake_model.pth'):
        """加载模型权重。"""
        try:
            self.policy_net.load_state_dict(torch.load(file_path))
            self.update_target_network()
            self.epsilon = self.epsilon_min # 加载模型后，通常使用最低探索率
            print(f"模型已从 {file_path} 加载")
        except FileNotFoundError:
            print(f"警告：找不到模型文件 {file_path}，将使用随机初始化的新模型。")
        except Exception as e:
            print(f"加载模型时出错: {e}")

def get_rl_state(game_state: 'GameState') -> np.ndarray:
    """
    将游戏状态转换为一个11维的NumPy向量，作为神经网络的输入。
    
    状态向量 [11维]:
    - danger_straight: 前方是否有危险 (1或0)
    - danger_left: 左方是否有危险
    - danger_right: 右方是否有危险
    - move_left: 当前是否向左移动
    - move_right: 当前是否向右移动
    - move_up: 当前是否向上移动
    - move_down: 当前是否向下移动
    - food_left: 食物在左边
    - food_right: 食物在右边
    - food_up: 食物在上方
    - food_down: 食物在下方
    """
    head = game_state.snake[0]
    point_l = (head[0], head[1] - 1)
    point_r = (head[0], head[1] + 1)
    point_u = (head[0] - 1, head[1])
    point_d = (head[0] + 1, head[1])
    
    dir_l = game_state.direction == 'LEFT'
    dir_r = game_state.direction == 'RIGHT'
    dir_u = game_state.direction == 'UP'
    dir_d = game_state.direction == 'DOWN'

    state = [
        # 根据当前方向判断“前方”的危险
        (dir_r and is_collision(point_r, game_state)) or 
        (dir_l and is_collision(point_l, game_state)) or 
        (dir_u and is_collision(point_u, game_state)) or 
        (dir_d and is_collision(point_d, game_state)),

        # 根据当前方向判断“右侧”的危险
        (dir_u and is_collision(point_r, game_state)) or 
        (dir_d and is_collision(point_l, game_state)) or 
        (dir_l and is_collision(point_u, game_state)) or 
        (dir_r and is_collision(point_d, game_state)),

        # 根据当前方向判断“左侧”的危险
        (dir_d and is_collision(point_r, game_state)) or 
        (dir_u and is_collision(point_l, game_state)) or 
        (dir_r and is_collision(point_u, game_state)) or 
        (dir_l and is_collision(point_d, game_state)),
        
        # 当前移动方向 (One-Hot编码)
        dir_l,
        dir_r,
        dir_u,
        dir_d,
        
        # 食物位置
        game_state.food[1] < head[1],  # 食物在左
        game_state.food[1] > head[1],  # 食物在右
        game_state.food[0] < head[0],  # 食物在上
        game_state.food[0] > head[0]   # 食物在下
    ]
    
    return np.array(state, dtype=np.float32)

def is_collision(point: Tuple[int, int], game_state: 'GameState') -> bool:
    """辅助函数：检查一个点是否会发生碰撞。"""
    if (point[0] >= game_state.grid_size or point[0] < 0 or 
        point[1] >= game_state.grid_size or point[1] < 0):
        return True  # 撞墙
    if point in game_state.snake:
        return True  # 撞自身
    return False
