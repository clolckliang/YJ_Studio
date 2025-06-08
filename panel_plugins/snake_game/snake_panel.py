# panel_plugins/snake_game/snake_panel.py
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QWidget, QGridLayout, QCheckBox, QComboBox, QSizePolicy,
                             QSpinBox, QDoubleSpinBox, QFileDialog)
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QKeyEvent, QPainter, QColor, QBrush
from typing import Dict, Any, Optional, List, Tuple, Set, Type
import random
import heapq
import math
import numpy as np
from collections import deque
from dataclasses import dataclass
from enum import Enum
import time
from abc import ABC, abstractmethod
import os
from pathlib import Path
import yaml

# --- 依赖检查 ---
try:
    import torch
    TORCH_AVAILABLE = True
    from .rl_algorithms import DQNAgent, PPOAgent, A2CAgent, get_rl_state, is_collision
except ImportError:
    TORCH_AVAILABLE = False
    DQNAgent, PPOAgent, A2CAgent, get_rl_state, is_collision = None, None, None, None, None

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.style as mplstyle
    mplstyle.use('dark_background')
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# --- 核心接口 ---
try:
    from core.panel_interface import PanelInterface
except ImportError:
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from core.panel_interface import PanelInterface

# ==============================================================================
#  强化学习可视化组件
# ==============================================================================
if MATPLOTLIB_AVAILABLE and TORCH_AVAILABLE:
    class RLVisualizationWidget(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumSize(600, 400)
            self.init_ui()
            
        def init_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(5, 5, 5, 5)
            
            plt.rcParams['font.sans-serif'] = ['SimHei']
            plt.rcParams['axes.unicode_minus'] = False

            self.figure = Figure(figsize=(12, 8), facecolor='#2c3e50')
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setStyleSheet("background-color: #2c3e50;")
            
            self.figure.subplots_adjust(hspace=0.4, wspace=0.3)
            self.ax_loss_policy = self.figure.add_subplot(2, 2, 1)
            self.ax_reward = self.figure.add_subplot(2, 2, 2)
            self.ax_score = self.figure.add_subplot(2, 2, 3)
            self.ax_loss_value = self.figure.add_subplot(2, 2, 4)
            
            self.setup_axes()
            layout.addWidget(self.canvas)
            
        def setup_axes(self, agent_type='DQN'):
            for ax in [self.ax_loss_policy, self.ax_reward, self.ax_score, self.ax_loss_value]:
                ax.clear()
                ax.set_facecolor('#34495e')
                ax.grid(True, alpha=0.3, color='white')
                ax.tick_params(colors='white')
                for spine in ax.spines.values():
                    spine.set_color('white')

            self.ax_reward.set_title('每局奖励', color='white', fontsize=12, fontweight='bold')
            self.ax_reward.set_xlabel('游戏局数', color='white')
            self.ax_reward.set_ylabel('累计奖励', color='white')
            
            self.ax_score.set_title('游戏分数', color='white', fontsize=12, fontweight='bold')
            self.ax_score.set_xlabel('游戏局数', color='white')
            self.ax_score.set_ylabel('分数', color='white')

            if agent_type == 'DQNAgent':
                self.ax_loss_policy.set_title('DQN 训练损失', color='white', fontsize=12, fontweight='bold')
                self.ax_loss_policy.set_xlabel('训练步数', color='white')
                self.ax_loss_policy.set_ylabel('损失值', color='white')
                self.ax_loss_value.set_title('探索率变化', color='white', fontsize=12, fontweight='bold')
                self.ax_loss_value.set_xlabel('游戏局数', color='white')
                self.ax_loss_value.set_ylabel('ε值', color='white')
            elif agent_type in ['PPOAgent', 'A2CAgent']:
                loss_name = 'PPO' if agent_type == 'PPOAgent' else 'A2C'
                self.ax_loss_policy.set_title(f'{loss_name} 策略损失', color='white', fontsize=12, fontweight='bold')
                self.ax_loss_policy.set_xlabel('更新次数', color='white')
                self.ax_loss_policy.set_ylabel('策略损失', color='white')
                self.ax_loss_value.set_title(f'{loss_name} 价值损失', color='white', fontsize=12, fontweight='bold')
                self.ax_loss_value.set_xlabel('更新次数', color='white')
                self.ax_loss_value.set_ylabel('价值损失', color='white')

        def update_plots(self, training_history, agent_type='DQNAgent'):
            try:
                self.setup_axes(agent_type)
                
                if training_history.get('rewards') and training_history.get('episodes'):
                    self.ax_reward.plot(training_history['episodes'], training_history['rewards'], color='#3498db', linewidth=2, marker='o', markersize=3)
                if training_history.get('scores') and training_history.get('episodes'):
                    self.ax_score.plot(training_history['episodes'], training_history['scores'], color='#2ecc71', linewidth=2, marker='s', markersize=3)

                if agent_type == 'DQNAgent':
                    if training_history.get('losses'):
                        self.ax_loss_policy.plot(training_history['losses'], color='#e74c3c', linewidth=2)
                    if training_history.get('epsilons') and training_history.get('episodes'):
                        self.ax_loss_value.plot(training_history['episodes'], training_history['epsilons'], color='#f39c12', linewidth=2)
                elif agent_type in ['PPOAgent', 'A2CAgent']:
                    if training_history.get('policy_losses'):
                        self.ax_loss_policy.plot(training_history['policy_losses'], color='#e74c3c', linewidth=2)
                    if training_history.get('value_losses'):
                        self.ax_loss_value.plot(training_history['value_losses'], color='#9b59b6', linewidth=2)

                self.canvas.draw()
            except Exception as e:
                print(f"更新图表时出错: {e}")

# ==============================================================================
#  游戏渲染与UI
# ==============================================================================
class GridWidget(QWidget):
    def __init__(self,grid_size,parent=None):
        super().__init__(parent);self.grid_size=grid_size
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);self.setMinimumSize(200,200)
        self.snake,self.food,self.path,self.viz_data=[],None,[],None
        self.BG_COLOR=QColor("#2c3e50");self.PATH_COLOR=QColor("#000000")
        self.SNAKE_BODY_COLOR=QColor("#27ae60");self.SNAKE_HEAD_COLOR=QColor("#2ecc71");self.FOOD_COLOR=QColor("#e74c3c")
    def update_data(self,snake,food,path,viz_data=None):self.snake,self.food,self.path,self.visualization_data=snake,food,path,viz_data;self.update()
    def resizeEvent(self,event):self.update();super().resizeEvent(event)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        cell_size=min(self.width()/self.grid_size,self.height()/self.grid_size)
        grid_w,grid_h=cell_size*self.grid_size,cell_size*self.grid_size
        off_x,off_y=(self.width()-grid_w)/2,(self.height()-grid_h)/2
        painter.translate(off_x,off_y);painter.fillRect(QRectF(0,0,grid_w,grid_h),self.BG_COLOR)
        if self.visualization_data is not None and isinstance(self.visualization_data,np.ndarray):
            field=self.visualization_data
            try:
                valid_data=field[field!=np.inf]
                if valid_data.size>0:
                    min_v,max_v=np.min(valid_data),np.max(valid_data);val_range=max(1.0,max_v-min_v)
                    for r in range(self.grid_size):
                        for c in range(self.grid_size):
                            val=field[r,c]
                            if val!=np.inf and(r,c)not in self.snake and(r,c)!=self.food:
                                norm=(val-min_v)/val_range;hue=0.7*(1.0-norm)
                                color=QColor.fromHsvF(hue,0.95,0.95)
                                painter.fillRect(QRectF(c*cell_size,r*cell_size,cell_size,cell_size),color)
            except Exception:pass
        if self.path:
            painter.setBrush(self.PATH_COLOR);painter.setPen(Qt.NoPen)
            for r,c in self.path:painter.drawRect(QRectF(c*cell_size,r*cell_size,cell_size,cell_size))
        if self.snake:
            painter.setBrush(self.SNAKE_BODY_COLOR);painter.setPen(Qt.NoPen)
            for r,c in self.snake[1:]:painter.drawRect(QRectF(c*cell_size,r*cell_size,cell_size,cell_size))
            painter.setBrush(self.SNAKE_HEAD_COLOR);r,c=self.snake[0];painter.drawRect(QRectF(c*cell_size,r*cell_size,cell_size,cell_size))
        if self.food:
            painter.setBrush(self.FOOD_COLOR);painter.setPen(Qt.NoPen);r,c=self.food;painter.drawEllipse(QRectF(c*cell_size,r*cell_size,cell_size,cell_size))

# ==============================================================================
#  算法策略定义
# ==============================================================================
class PathfindingAlgorithm(Enum):
    A_STAR="A* 算法"
    BFS="BFS 广度优先"
    DFS="DFS 深度优先"
    DIJKSTRA="Dijkstra 算法"
    GREEDY="贪心算法"
    POTENTIAL_FIELD="人工势场法"
    GENETIC="遗传算法"
    MCTS="蒙特卡洛树搜索"
    RL_DQN="RL (DQN)"
    RL_PPO="RL (PPO)"
    RL_A2C="RL (A2C)"

@dataclass
class PathNode:
    position:Tuple[int,int];g_cost:float=0;h_cost:float=0;f_cost:float=0;parent:Optional['PathNode']=None
    def __lt__(self,other):return self.f_cost<other.f_cost
@dataclass
class GameState:
    snake:List[Tuple[int,int]];food:Tuple[int,int];direction:str;score:int;game_over:bool;grid_size:int
    def copy(self):return GameState(list(self.snake),self.food,self.direction,self.score,self.game_over,self.grid_size)

class PathfindingStrategy(ABC):
    def __init__(self,grid_size:int,panel_ref:'SnakeGamePanel'):
        self.grid_size=grid_size;self.panel=panel_ref;self.visualization_data:Any=None
    @abstractmethod
    def calculate_path(self,gs:GameState,obs:Set[Tuple[int,int]])->Optional[List[Tuple[int,int]]]:raise NotImplementedError
    def create_parameters_ui(self)->Optional[QWidget]:return None
    def get_parameters(self)->Dict[str,Any]:return{}
    def apply_parameters(self,params:Dict[str,Any]):pass
    def _heuristic(self,p1,p2):return abs(p1[0]-p2[0])+abs(p1[1]-p2[1])
    def _get_neighbors(self,p):return[(p[0]-1,p[1]),(p[0]+1,p[1]),(p[0],p[1]-1),(p[0],p[1]+1)]
    def _is_valid(self,p):return 0<=p[0]<self.grid_size and 0<=p[1]<self.grid_size
    def _reconstruct_path(self,n):
        path=[];c=n
        while c:path.append(c.position);c=c.parent
        return path[::-1]

class AStarStrategy(PathfindingStrategy):
    def calculate_path(self,gs,obs):
        s,g=gs.snake[0],gs.food;os,cs=[],set();sn=PathNode(s,h_cost=self._heuristic(s,g));sn.f_cost=sn.h_cost
        nm={s:sn};viz_data=np.full((self.grid_size,self.grid_size),np.inf);viz_data[s]=sn.f_cost;heapq.heappush(os,sn)
        while os:
            c=heapq.heappop(os)
            if c.position==g:self.visualization_data=viz_data;return self._reconstruct_path(c)
            if c.position in cs:continue
            cs.add(c.position)
            for n_pos in self._get_neighbors(c.position):
                if not self._is_valid(n_pos)or n_pos in obs or n_pos in cs:continue
                g_cost=c.g_cost+1;nn=nm.get(n_pos)
                if nn is None or g_cost<nn.g_cost:
                    if nn is None:nn=PathNode(n_pos,h_cost=self._heuristic(n_pos,g));nm[n_pos]=nn
                    nn.parent=c;nn.g_cost=g_cost;f_cost=g_cost+nn.h_cost;nn.f_cost=f_cost;viz_data[n_pos]=f_cost;heapq.heappush(os,nn)
        self.visualization_data=viz_data;return None

class BFSStrategy(PathfindingStrategy):
    def calculate_path(self,gs,obs):
        q=deque([PathNode(gs.snake[0])]);v={gs.snake[0]};step=0
        viz_data=np.full((self.grid_size,self.grid_size),np.inf);viz_data[gs.snake[0]]=step
        while q:
            c=q.popleft()
            if c.position==gs.food:self.visualization_data=viz_data;return self._reconstruct_path(c)
            current_step=viz_data[c.position]
            for n in self._get_neighbors(c.position):
                if self._is_valid(n)and n not in obs and n not in v:v.add(n);viz_data[n]=current_step+1;q.append(PathNode(n,parent=c))
        self.visualization_data=viz_data;return None

class DFSStrategy(PathfindingStrategy):
     def calculate_path(self,gs,obs):
        s=[PathNode(gs.snake[0])];v={gs.snake[0]};step=0
        viz_data=np.full((self.grid_size,self.grid_size),np.inf);viz_data[gs.snake[0]]=step
        while s:
            c=s.pop()
            if c.position==gs.food:self.visualization_data=viz_data;return self._reconstruct_path(c)
            neighbors=self._get_neighbors(c.position);random.shuffle(neighbors)
            for n in neighbors:
                if self._is_valid(n)and n not in obs and n not in v:v.add(n);step+=1;viz_data[n]=step;s.append(PathNode(n,parent=c))
        self.visualization_data=viz_data;return None

class DijkstraStrategy(PathfindingStrategy):
    def calculate_path(self,gs,obs):
        os=[PathNode(gs.snake[0])];nm={gs.snake[0]:os[0]}
        viz_data=np.full((self.grid_size,self.grid_size),np.inf);viz_data[gs.snake[0]]=0
        while os:
            c=heapq.heappop(os)
            if c.position==gs.food:self.visualization_data=viz_data;return self._reconstruct_path(c)
            for n in self._get_neighbors(c.position):
                if not self._is_valid(n)or n in obs:continue
                g=c.g_cost+1;nn=nm.get(n)
                if nn is None or g<nn.g_cost:
                    if nn is None:nn=PathNode(n);nm[n]=nn
                    nn.parent=c;nn.g_cost=g;nn.f_cost=g;viz_data[n]=g;heapq.heappush(os,nn)
        self.visualization_data=viz_data;return None

class GreedyStrategy(PathfindingStrategy):
    def calculate_path(self,gs,obs):
        os=[];sn=PathNode(gs.snake[0],h_cost=self._heuristic(gs.snake[0],gs.food));sn.f_cost=sn.h_cost
        heapq.heappush(os,sn);cs=set()
        viz_data=np.full((self.grid_size,self.grid_size),np.inf);viz_data[gs.snake[0]]=sn.f_cost
        while os:
            c=heapq.heappop(os)
            if c.position==gs.food:self.visualization_data=viz_data;return self._reconstruct_path(c)
            if c.position in cs:continue
            cs.add(c.position)
            for n in self._get_neighbors(c.position):
                if self._is_valid(n)and n not in obs and n not in cs:
                    nn=PathNode(n,h_cost=self._heuristic(n,gs.food),parent=c);nn.f_cost=nn.h_cost
                    viz_data[n]=nn.f_cost;heapq.heappush(os,nn)
        self.visualization_data=viz_data;return None

class PotentialFieldStrategy(PathfindingStrategy):
    def __init__(self,grid_size:int,panel_ref:'SnakeGamePanel'):super().__init__(grid_size,panel_ref);self.attractive_k=1.0;self.repulsive_k_mult=5.0;self.repulsive_range_div=5.0
    def calculate_path(self,gs:GameState,obs:Set[Tuple[int,int]])->Optional[List[Tuple[int,int]]]:
        start,goal=gs.snake[0],gs.food;yy,xx=np.mgrid[0:self.grid_size,0:self.grid_size]
        attractive_potential=0.5*self.attractive_k*((yy-goal[0])**2+(xx-goal[1])**2)
        repulsive_potential=np.zeros_like(attractive_potential)
        if obs:
            rep_k=self.grid_size*self.repulsive_k_mult;rep_range=self.grid_size/self.repulsive_range_div
            obs_arr=np.array(list(obs));dist_sq=(yy[:,:,None]-obs_arr[:,0])**2+(xx[:,:,None]-obs_arr[:,1])**2
            dist=np.sqrt(dist_sq);mask=dist<=rep_range;inv_dist=1.0/(dist+1e-6);inv_range=1.0/rep_range
            rep_force=0.5*rep_k*(inv_dist-inv_range)**2;repulsive_potential=np.sum(rep_force*mask,axis=2)
        potential_field=attractive_potential+repulsive_potential;self.visualization_data=potential_field
        path,pos=[start],start
        for _ in range(self.grid_size**2):
            if pos==goal:break
            neighbors=self._get_neighbors(pos);random.shuffle(neighbors)
            best_n=min((n for n in neighbors if self._is_valid(n)and n not in path),key=lambda n:potential_field[n[0],n[1]],default=None)
            if not best_n:break
            path.append(best_n);pos=best_n
        return path if path[-1]==goal else None
    def create_parameters_ui(self)->QWidget:
        ui=QWidget();layout=QGridLayout(ui);layout.setContentsMargins(0,5,0,5)
        layout.addWidget(QLabel("吸引力系数:"),0,0);self.attractive_k_spin=QDoubleSpinBox();self.attractive_k_spin.setRange(0.1,10);self.attractive_k_spin.setValue(self.attractive_k);self.attractive_k_spin.valueChanged.connect(lambda v:setattr(self,'attractive_k',v));layout.addWidget(self.attractive_k_spin,0,1)
        layout.addWidget(QLabel("排斥力系数:"),1,0);self.repulsive_k_spin=QDoubleSpinBox();self.repulsive_k_spin.setRange(1,20);self.repulsive_k_spin.setValue(self.repulsive_k_mult);self.repulsive_k_spin.valueChanged.connect(lambda v:setattr(self,'repulsive_k_mult',v));layout.addWidget(self.repulsive_k_spin,1,1)
        layout.addWidget(QLabel("排斥力范围:"),2,0);self.repulsive_range_spin=QDoubleSpinBox();self.repulsive_range_spin.setRange(1,10);self.repulsive_range_spin.setValue(self.repulsive_range_div);self.repulsive_range_spin.valueChanged.connect(lambda v:setattr(self,'repulsive_range_div',v));layout.addWidget(self.repulsive_range_spin,2,1)
        return ui
    def get_parameters(self):return{"attractive_k":self.attractive_k,"repulsive_k_mult":self.repulsive_k_mult,"repulsive_range_div":self.repulsive_range_div}
    def apply_parameters(self,p):
        self.attractive_k=p.get("attractive_k",1.0);self.repulsive_k_mult=p.get("repulsive_k_mult",5.0);self.repulsive_range_div=p.get("repulsive_range_div",5.0)
        if hasattr(self,'attractive_k_spin'):self.attractive_k_spin.setValue(self.attractive_k);self.repulsive_k_spin.setValue(self.repulsive_k_mult);self.repulsive_range_spin.setValue(self.repulsive_range_div)

class GeneticAlgorithmStrategy(PathfindingStrategy):
    @dataclass
    class Individual:
        genes:List[str];fitness:float=0.0;reached_goal:bool=False
        def __lt__(self,other):return self.fitness>other.fitness
    def __init__(self,grid_size:int,panel_ref:'SnakeGamePanel'):
        super().__init__(grid_size,panel_ref);self.pop_size=50;self.gens=30;self.mut_rate=0.1;self.cross_rate=0.8
    def calculate_path(self,gs:GameState,obs:Set[Tuple[int,int]])->Optional[List[Tuple[int,int]]]:
        start,goal=gs.snake[0],gs.food;obstacle_grid=np.zeros((self.grid_size,self.grid_size),dtype=bool)
        for r,c in obs:obstacle_grid[r,c]=True
        population=self._init_population(start,goal);best_overall=None
        for _ in range(self.gens):
            for ind in population:ind.fitness,ind.reached_goal=self._evaluate_fitness_numpy(ind,start,goal,obstacle_grid)
            population.sort()
            current_best=population[0]
            if best_overall is None or current_best.fitness>best_overall.fitness:best_overall=current_best
            if current_best.reached_goal:break
            elite_count=max(2,int(self.pop_size*0.1));new_pop=population[:elite_count]
            while len(new_pop)<self.pop_size:
                p1,p2=self._select(population),self._select(population)
                c1_genes,c2_genes=self._crossover(p1,p2)if random.random()<self.cross_rate else(p1.genes[:],p2.genes[:])
                new_pop.append(self.Individual(self._mutate(c1_genes)))
                if len(new_pop)<self.pop_size:new_pop.append(self.Individual(self._mutate(c2_genes)))
            population=new_pop
        return self._genes_to_path(best_overall,start,obstacle_grid)if best_overall else None
    def _evaluate_fitness_numpy(self,ind,start,goal,obstacle_grid):
        sim_grid=obstacle_grid.copy();pos=start;fitness=0.0;sim_grid[pos]=True;path_len=0
        for gene in ind.genes:
            path_len+=1;dr,dc={'UP':(-1,0),'DOWN':(1,0),'LEFT':(0,-1),'RIGHT':(0,1)}[gene];next_pos=(pos[0]+dr,pos[1]+dc)
            if not(0<=next_pos[0]<self.grid_size and 0<=next_pos[1]<self.grid_size)or sim_grid[next_pos]:return fitness-200,False
            if self._heuristic(next_pos,goal)<self._heuristic(pos,goal):fitness+=10
            pos=next_pos;sim_grid[pos]=True
            if pos==goal:return fitness+10000-path_len*2,True
        return fitness-self._heuristic(pos,goal)*20,False
    def _genes_to_path(self,ind,start,obstacle_grid):
        path,pos=[start],start;sim_grid=obstacle_grid.copy();sim_grid[pos]=True
        for gene in ind.genes:
            dr,dc={'UP':(-1,0),'DOWN':(1,0),'LEFT':(0,-1),'RIGHT':(0,1)}[gene];next_pos=(pos[0]+dr,pos[1]+dc)
            if not(0<=next_pos[0]<self.grid_size and 0<=next_pos[1]<self.grid_size)or sim_grid[next_pos]:break
            path.append(next_pos);pos=next_pos
            if pos==self.panel.food:break
        return path
    def _init_population(self,s,g):
        pop=[];dirs=['UP','DOWN','LEFT','RIGHT'];base=int(self._heuristic(s,g))
        for _ in range(self.pop_size):pop.append(self.Individual([random.choice(dirs)for _ in range(random.randint(base,int(base*2.0)+2))]))
        return pop
    def _select(self,p):return max(random.sample(p,k=max(2,len(p)//10)))
    def _crossover(self,p1,p2):
        l=min(len(p1.genes),len(p2.genes))
        if l<2:return p1.genes[:],p2.genes[:]
        pt=random.randint(1,l-1);return p1.genes[:pt]+p2.genes[pt:],p2.genes[:pt]+p1.genes[pt:]
    def _mutate(self,genes):
        for i in range(len(genes)):
            if random.random()<self.mut_rate:genes[i]=random.choice(['UP','DOWN','LEFT','RIGHT'])
        return genes
    def create_parameters_ui(self)->QWidget:
        ui=QWidget();layout=QGridLayout(ui);layout.setContentsMargins(0,5,0,5)
        layout.addWidget(QLabel("种群大小:"),0,0);self.pop_size_spin=QSpinBox();self.pop_size_spin.setRange(10,500);self.pop_size_spin.setValue(self.pop_size);self.pop_size_spin.valueChanged.connect(lambda v:setattr(self,'pop_size',v));layout.addWidget(self.pop_size_spin,0,1)
        layout.addWidget(QLabel("迭代次数:"),1,0);self.gens_spin=QSpinBox();self.gens_spin.setRange(10,200);self.gens_spin.setValue(self.gens);self.gens_spin.valueChanged.connect(lambda v:setattr(self,'gens',v));layout.addWidget(self.gens_spin,1,1)
        layout.addWidget(QLabel("变异率:"),0,2);self.mut_rate_spin=QDoubleSpinBox();self.mut_rate_spin.setRange(0,1);self.mut_rate_spin.setValue(self.mut_rate);self.mut_rate_spin.valueChanged.connect(lambda v:setattr(self,'mut_rate',v));layout.addWidget(self.mut_rate_spin,0,3)
        layout.addWidget(QLabel("交叉率:"),1,2);self.cross_rate_spin=QDoubleSpinBox();self.cross_rate_spin.setRange(0,1);self.cross_rate_spin.setValue(self.cross_rate);self.cross_rate_spin.valueChanged.connect(lambda v:setattr(self,'cross_rate',v));layout.addWidget(self.cross_rate_spin,1,3)
        return ui
    def get_parameters(self):return{"pop_size":self.pop_size,"gens":self.gens,"mut_rate":self.mut_rate,"cross_rate":self.cross_rate}
    def apply_parameters(self,p):
        self.pop_size=p.get("pop_size",50);self.gens=p.get("gens",30);self.mut_rate=p.get("mut_rate",0.1);self.cross_rate=p.get("cross_rate",0.8)
        if hasattr(self,'pop_size_spin'):self.pop_size_spin.setValue(self.pop_size);self.gens_spin.setValue(self.gens);self.mut_rate_spin.setValue(self.mut_rate);self.cross_rate_spin.setValue(self.cross_rate)

class MCTSStrategy(PathfindingStrategy):
    class MCTSNode:
        def __init__(self,parent=None,state=None,action=None):
            self.parent=parent;self.state=state;self.action=action;self.children:List['MCTSStrategy.MCTSNode']=[];self.wins=0.0;self.visits=0
            self.unexplored_actions=state.get_legal_actions()if state else[]
        def is_fully_expanded(self):return not self.unexplored_actions
        def best_child(self,c=1.414):
            if not self.children:return None
            visits=np.array([k.visits for k in self.children],dtype=np.float32);wins=np.array([k.wins for k in self.children],dtype=np.float32)
            eps=1e-6;exploit=wins/(visits+eps);explore=c*np.sqrt(np.log(self.visits+1)/(visits+eps));ucb=exploit+explore
            ucb[visits==0]=np.inf;return self.children[np.argmax(ucb)]
    def __init__(self,grid_size:int,panel_ref:'SnakeGamePanel'):
        super().__init__(grid_size,panel_ref);self.time_budget=0.05
    def calculate_path(self,gs:GameState,obs:Set[Tuple[int,int]])->Optional[List[Tuple[int,int]]]:
        root=self.MCTSNode(state=gs.copy());start=time.time()
        while time.time()-start<self.time_budget:
            node=self._select(root)
            if not node.state.game_over:node=self._expand(node)
            reward=self._rollout_numpy(node.state);self._backpropagate(node,reward)
        if not root.children:return None
        best=max(root.children,key=lambda c:c.visits);dr,dc={'UP':(-1,0),'DOWN':(1,0),'LEFT':(0,-1),'RIGHT':(0,1)}[best.action]
        return[(gs.snake[0][0]+dr,gs.snake[0][1]+dc)]
    def _select(self,node):
        while node.is_fully_expanded()and not node.state.game_over:node=node.best_child()
        return node
    def _expand(self,node):
        if node.unexplored_actions:
            a=node.unexplored_actions.pop(0);s=node.state.copy();s.make_move(a)
            c=self.MCTSNode(parent=node,state=s,action=a);node.children.append(c);return c
        return node
    def _rollout_numpy(self,initial_state:GameState):
        grid=np.zeros((self.grid_size,self.grid_size),dtype=np.int8);snake=deque(initial_state.snake);food=initial_state.food
        for r,c in snake:grid[r,c]=1
        grid[snake[0]]=2;grid[food]=3;score=initial_state.score;moves=[(-1,0),(1,0),(0,-1),(0,1)]
        for _ in range(self.grid_size*2):
            head=snake[0];valid_moves=[(head[0]+dr,head[1]+dc)for dr,dc in moves if 0<=(head[0]+dr)<self.grid_size and 0<=(head[1]+dc)<self.grid_size and grid[head[0]+dr,head[1]+dc]in{0,3}]
            if not valid_moves:score-=500;break
            dists=[self._heuristic(pos,food)for pos in valid_moves];new_head=valid_moves[np.argmin(dists)]
            grid[head]=1;ate_food=(grid[new_head]==3);grid[new_head]=2;snake.insert(0,new_head)
            if not ate_food:tail=snake.pop();grid[tail]=0
            else:
                score+=1;empty=np.argwhere(grid==0)
                if empty.size>0:food=tuple(empty[np.random.randint(0,len(empty))]);grid[food]=3
                else:break
        return float(score*10-self._heuristic(snake[0],food))
    def _backpropagate(self,node,reward):
        while node:node.visits+=1;node.wins+=reward;node=node.parent
    def create_parameters_ui(self)->QWidget:
        ui=QWidget();layout=QHBoxLayout(ui);layout.setContentsMargins(0,5,0,5)
        layout.addWidget(QLabel("思考时间(s):"));self.time_spin=QDoubleSpinBox();self.time_spin.setRange(0.01,1.0);self.time_spin.setSingleStep(0.01);self.time_spin.setValue(self.time_budget)
        self.time_spin.valueChanged.connect(lambda v:setattr(self,'time_budget',v));layout.addWidget(self.time_spin)
        return ui
    def get_parameters(self):return{"time_budget":self.time_budget}
    def apply_parameters(self,p):
        self.time_budget=p.get("time_budget",0.05)
        if hasattr(self,'time_spin'):self.time_spin.setValue(self.time_budget)

class RLStrategy(PathfindingStrategy):
    def __init__(self, grid_size: int, panel_ref: 'SnakeGamePanel'):
        super().__init__(grid_size, panel_ref)
        if not TORCH_AVAILABLE: return
        self.agent = None
        self.is_training = False
        self.training_games = 0
        self.record_score = 0
        self.viz_window = None
        self.viz_widget = None
        self.training_timer = QTimer(self.panel)
        self.training_timer.timeout.connect(self._training_step)

    def calculate_path(self, gs: GameState, obs: Set[Tuple[int, int]]) -> Optional[List[Tuple[int, int]]]:
        if not TORCH_AVAILABLE or not self.agent: return None
        state = get_rl_state(gs)
        action_idx, _ = self.agent.act(state, is_training=False)
        action = ['UP', 'DOWN', 'LEFT', 'RIGHT'][action_idx]
        head = gs.snake[0]
        dr, dc = {'UP': (-1, 0), 'DOWN': (1, 0), 'LEFT': (0, -1), 'RIGHT': (0, 1)}[action]
        return [(head[0] + dr, head[1] + dc)]

    def create_rl_ui(self):
        if not TORCH_AVAILABLE:
            return QLabel("PyTorch 未安装，无法使用此功能。")
        
        ui = QWidget()
        layout = QVBoxLayout(ui)
        layout.setContentsMargins(0, 5, 0, 5)

        self.train_button = QPushButton("开始训练")
        self.train_button.clicked.connect(self.toggle_training)
        self.train_button.setStyleSheet("font-size:16px;font-weight:bold;color:white;background-color:#27ae60;border:none;border-radius:8px;padding:8px 20px;")

        self.save_button = QPushButton("保存模型")
        self.save_button.clicked.connect(self.save_model)
        self.save_button.setStyleSheet("font-size:15px;color:white;background-color:#2980b9;border:none;border-radius:8px;padding:7px 18px;")

        self.load_button = QPushButton("加载模型")
        self.load_button.clicked.connect(self.load_model)
        self.load_button.setStyleSheet("font-size:15px;color:white;background-color:#8e44ad;border:none;border-radius:8px;padding:7px 18px;")

        self.viz_button = QPushButton("📊 训练可视化")
        self.viz_button.clicked.connect(self.show_visualization)
        self.viz_button.setStyleSheet("font-size:15px;color:white;background-color:#e67e22;border:none;border-radius:8px;padding:7px 18px;")

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.save_button)
        h_layout.addWidget(self.load_button)
        h_layout.setSpacing(15)

        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(self.viz_button)
        h_layout2.addStretch()

        self.games_label = QLabel("训练局数: 0")
        self.record_label = QLabel("最高分: 0")
        self.epsilon_label = QLabel(f"探索率 (ε): N/A")

        layout.addWidget(self.train_button)
        layout.addLayout(h_layout)
        layout.addLayout(h_layout2)
        layout.addWidget(self.games_label)
        layout.addWidget(self.record_label)
        layout.addWidget(self.epsilon_label)
        
        return ui

    def toggle_training(self):
        self.is_training = not self.is_training
        self.train_button.setText("停止训练" if self.is_training else "开始训练")
        if self.is_training:
            self.training_timer.start(0)
        else:
            self.training_timer.stop()

    def _training_step(self):
        raise NotImplementedError

    def show_visualization(self):
        if not MATPLOTLIB_AVAILABLE:
            print("matplotlib 未安装，无法显示可视化")
            return
            
        if self.viz_window is None:
            from PySide6.QtWidgets import QDialog, QVBoxLayout
            self.viz_window = QDialog(self.panel)
            self.viz_window.setWindowTitle("强化学习训练可视化")
            self.viz_window.setModal(False)
            self.viz_window.resize(1000, 700)
            self.viz_window.setStyleSheet("QDialog { background-color: #2c3e50; color: white; }")
            
            layout = QVBoxLayout(self.viz_window)
            layout.setContentsMargins(10, 10, 10, 10)
            self.viz_widget = RLVisualizationWidget()
            layout.addWidget(self.viz_widget)
            self.viz_widget.update_plots(self.agent.training_history, self.agent.__class__.__name__)
        
        self.viz_window.show()
        self.viz_window.raise_()
        self.viz_window.activateWindow()

    def update_ui_stats(self):
        self.games_label.setText(f"训练局数: {self.training_games}")
        self.record_label.setText(f"最高分: {self.record_score}")
        if hasattr(self.agent, 'epsilon'):
            self.epsilon_label.setText(f"探索率 (ε): {self.agent.epsilon:.3f}")
        else:
            self.epsilon_label.setText("探索率 (ε): N/A")

    def save_model(self):
        if not self.agent: return
        path, _ = QFileDialog.getSaveFileName(self.panel, "保存模型", f"{self.agent.__class__.__name__}_snake_model.pth", "PyTorch Models (*.pth)")
        if path: self.agent.save_model(path)

    def load_model(self):
        if not self.agent: return
        path, _ = QFileDialog.getOpenFileName(self.panel, "加载模型", "", "PyTorch Models (*.pth)")
        if path: self.agent.load_model(path)

class DQNStrategy(RLStrategy):
    def __init__(self, grid_size: int, panel_ref: 'SnakeGamePanel'):
        super().__init__(grid_size, panel_ref)
        if TORCH_AVAILABLE:
            # 通过 panel_ref 访问主面板的 rl_config
            # 如果配置为空（加载失败），则传递一个空字典
            dqn_config = panel_ref.rl_config.get('dqn_agent', {})
            if dqn_config:
                self.agent = DQNAgent(grid_size, config=dqn_config)
            else:
                # 如果配置文件加载失败或没有dqn_agent部分，可以提供一组备用默认值
                print("使用DQN的硬编码默认参数进行初始化。")
                default_conf = {'learning_rate': 0.001, 
                                'gamma': 0.9, 
                                'epsilon_start': 1.0, 
                                'epsilon_end': 0.01, 
                                'epsilon_decay': 0.995, 
                                'memory_capacity': 10000, 
                                'batch_size': 128}
                self.agent = DQNAgent(grid_size, config=default_conf)

    def create_parameters_ui(self) -> QWidget:
        return self.create_rl_ui()

    def _training_step(self):
        if not self.is_training or not self.agent:
            self.training_timer.stop()
            return

        state_old = get_rl_state(self.panel.get_current_gamestate())
        action_idx, _ = self.agent.act(state_old, is_training=True)
        reward, done, score = self.panel.play_step_rl(action_idx)
        state_new = get_rl_state(self.panel.get_current_gamestate())
        self.agent.remember(state_old, action_idx, reward, state_new, done)
        self.agent.add_reward(reward)
        
        if done:
            self.agent.record_episode_data(self.agent.current_episode_reward, score)
            self.panel._new_game_for_rl()
            self.training_games += 1
            self.record_score = max(self.record_score, score)
            
            if len(self.agent.memory) > self.agent.batch_size:
                self.agent.learn()
            
            self.update_ui_stats()
            
            if self.viz_window and self.viz_window.isVisible():
                self.viz_widget.update_plots(self.agent.training_history, 'DQNAgent')

        if self.training_games > 0 and self.training_games % 20 == 0:
            self.agent.update_target_network()

class PPOStrategy(RLStrategy):
    def __init__(self, grid_size: int, panel_ref: 'SnakeGamePanel'):
        super().__init__(grid_size, panel_ref)
        if TORCH_AVAILABLE:
            ppo_config = panel_ref.rl_config.get('ppo_agent', {})
            if ppo_config:
                self.agent = PPOAgent(grid_size, config=ppo_config)
                # 从配置中读取更新频率
                self.update_interval = ppo_config.get('update_interval', 2000)
            else:
                # 提供备用默认值
                print("使用PPO的硬编码默认参数进行初始化。")
                default_conf = {'lr': 0.0003, 'gamma': 0.99, 'eps_clip': 0.2, 'k_epochs': 4}
                self.agent = PPOAgent(grid_size, config=default_conf)
                self.update_interval = 2000

            self.time_step = 0
    
    def create_parameters_ui(self) -> QWidget:
        return self.create_rl_ui()

    def _training_step(self):
        if not self.is_training or not self.agent:
            self.training_timer.stop()
            return

        self.time_step += 1
        
        state_old = get_rl_state(self.panel.get_current_gamestate())
        action_idx, log_prob = self.agent.act(state_old, is_training=True)
        reward, done, score = self.panel.play_step_rl(action_idx)
        state_new = get_rl_state(self.panel.get_current_gamestate())
        
        self.agent.remember(state_old, action_idx, reward, state_new, done, log_prob)
        self.agent.add_reward(reward)
        
        if self.time_step % self.update_interval == 0:
            self.agent.learn()
            self.time_step = 0

        if done:
            self.agent.record_episode_data(self.agent.current_episode_reward, score)
            self.panel._new_game_for_rl()
            self.training_games += 1
            self.record_score = max(self.record_score, score)
            self.update_ui_stats()
            
            if self.viz_window and self.viz_window.isVisible():
                self.viz_widget.update_plots(self.agent.training_history, 'PPOAgent')

class A2CStrategy(RLStrategy):
    def __init__(self, grid_size: int, panel_ref: 'SnakeGamePanel'):
        super().__init__(grid_size, panel_ref)
        if TORCH_AVAILABLE:
            a2c_config = panel_ref.rl_config.get('a2c_agent', {})
            if a2c_config:
                self.agent = A2CAgent(grid_size, config=a2c_config)
            else:
                # 提供备用默认值
                print("使用A2C的硬编码默认参数进行初始化。")
                default_conf = {'lr': 0.0007, 'gamma': 0.99}
                self.agent = A2CAgent(grid_size, config=default_conf)

    def create_parameters_ui(self) -> QWidget:
        return self.create_rl_ui()

    def _training_step(self):
        if not self.is_training or not self.agent:
            self.training_timer.stop()
            return

        state_old = get_rl_state(self.panel.get_current_gamestate())
        action_idx, log_prob = self.agent.act(state_old, is_training=True)
        reward, done, score = self.panel.play_step_rl(action_idx)
        state_new = get_rl_state(self.panel.get_current_gamestate())
        
        self.agent.remember(state_old, action_idx, reward, state_new, done, log_prob)
        self.agent.add_reward(reward)
        
        # A2C updates every step
        self.agent.learn()

        if done:
            self.agent.record_episode_data(self.agent.current_episode_reward, score)
            self.panel._new_game_for_rl()
            self.training_games += 1
            self.record_score = max(self.record_score, score)
            self.update_ui_stats()
            
            if self.viz_window and self.viz_window.isVisible():
                self.viz_widget.update_plots(self.agent.training_history, 'A2CAgent')

class SnakeGamePanel(PanelInterface):
    PANEL_TYPE_NAME="snake_game";PANEL_DISPLAY_NAME="贪吃蛇游戏"
    # GRID_SIZE=100;
 
    def __init__(self,panel_id,main_window_ref,initial_config=None,parent=None):
        super().__init__(panel_id,main_window_ref,initial_config,parent)
        self.rl_config = {}
        # 将这些值作为实例变量进行初始化
        self.grid_size= 20
        self.initial_speed = 150
        self.auto_speed = 50
        try:
            # Path(__file__) 是当前 snake_panel.py 文件的完整路径
            # .parent 会一层层地返回上级目录
            # 我们假设项目根目录在 snake_panel.py 的上三级
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / 'panel_plugins/snake_game/config.yaml'
            with open(config_path, 'r', encoding='utf-8') as f:
                self.rl_config = yaml.safe_load(f)
                # 打印加载成功的路径，方便确认
                print(f"成功加载强化学习配置文件: {config_path}")
        except FileNotFoundError:
            print("警告: 未找到 config.yaml, 将使用默认参数。请确保它位于项目根目录。")
        except Exception as e:
            print(f"加载 config.yaml 失败: {e}")
        self.snake,self.food,self.direction,self.score=[],(0,0),'RIGHT',0
        self.game_over,self.game_started,self.auto_mode=True,False,False
        self.current_path,self.path_index=[],0;self.current_strategy:Optional[PathfindingStrategy]=None
        
        self.strategies = {
            PathfindingAlgorithm.A_STAR: AStarStrategy,
            PathfindingAlgorithm.BFS: BFSStrategy,
            PathfindingAlgorithm.DFS: DFSStrategy,
            PathfindingAlgorithm.DIJKSTRA: DijkstraStrategy,
            PathfindingAlgorithm.GREEDY: GreedyStrategy,
            PathfindingAlgorithm.POTENTIAL_FIELD: PotentialFieldStrategy,
            PathfindingAlgorithm.GENETIC: GeneticAlgorithmStrategy,
            PathfindingAlgorithm.MCTS: MCTSStrategy,
        }
        if TORCH_AVAILABLE:
            self.strategies.update({
                PathfindingAlgorithm.RL_DQN: DQNStrategy,
                PathfindingAlgorithm.RL_PPO: PPOStrategy,
                PathfindingAlgorithm.RL_A2C: A2CStrategy,
            })

        self.timer=QTimer(self);self.timer.timeout.connect(self._game_loop)
        self._init_ui();self._new_game()
        if initial_config:self.apply_config(initial_config)
        else:self._on_algorithm_changed(PathfindingAlgorithm.A_STAR.value)

    def _init_ui(self):
        main_layout=QVBoxLayout(self);main_layout.setSpacing(10);main_layout.setContentsMargins(10,10,10,10);self.setStyleSheet("background-color:#2c3e50;border:none;")
        top_widget=QWidget();top_layout=QVBoxLayout(top_widget);top_layout.setSpacing(10);top_layout.setContentsMargins(15,15,15,15);top_widget.setStyleSheet("background-color:#34495e;border-radius:15px;")
        title=QLabel("🐍 贪吃蛇 AI 对战");title.setAlignment(Qt.AlignCenter);title.setStyleSheet("font-size:24px;font-weight:bold;color:#ecf0f1;padding:5px;");top_layout.addWidget(title)
        score_start_layout=QHBoxLayout();score_start_layout.setSpacing(20)
        self.score_label=QLabel("分数: 0");self.score_label.setStyleSheet("font-size:18px;font-weight:bold;color:#2ecc71;background-color:#2c3e50;padding:8px 15px;border-radius:8px;")
        self.start_button=QPushButton("🎮 开始游戏");self.start_button.clicked.connect(self._start_game);self.start_button.setStyleSheet("font-size:16px;font-weight:bold;color:white;background-color:#3498db;border:none;border-radius:8px;padding:8px 20px;")
        score_start_layout.addStretch();score_start_layout.addWidget(self.score_label);score_start_layout.addWidget(self.start_button);score_start_layout.addStretch()
        top_layout.addLayout(score_start_layout)
        # --- 新增：游戏设置区域（美化版） ---
        settings_layout = QGridLayout()
        settings_layout.setContentsMargins(10, 5, 10, 10)
        settings_layout.setSpacing(15)

        label_style = "font-size:15px;font-weight:bold;color:#ecf0f1;padding:2px 8px;"
        spin_style = (
            "QSpinBox {font-size:15px;padding:5px 10px;border-radius:6px;background-color:#22313a;color:#ecf0f1;border:1px solid #2980b9;min-width:60px;}"
            "QSpinBox::up-button, QSpinBox::down-button {width:18px;height:18px;}"
            "QSpinBox::up-arrow, QSpinBox::down-arrow {background:transparent;}"
        )

        # Grid Size 输入框
        grid_label = QLabel("地图大小:")
        grid_label.setStyleSheet(label_style)
        settings_layout.addWidget(grid_label, 0, 0)
        self.grid_size_spin = QSpinBox()
        self.grid_size_spin.setRange(10, 100)
        self.grid_size_spin.setValue(self.grid_size)
        self.grid_size_spin.setStyleSheet(spin_style)
        self.grid_size_spin.valueChanged.connect(self._on_grid_size_changed)
        settings_layout.addWidget(self.grid_size_spin, 0, 1)

        # Manual Speed 输入框
        manual_label = QLabel("手动速度(ms):")
        manual_label.setStyleSheet(label_style)
        settings_layout.addWidget(manual_label, 0, 2)
        self.manual_speed_spin = QSpinBox()
        self.manual_speed_spin.setRange(10, 1000)
        self.manual_speed_spin.setValue(self.initial_speed)
        self.manual_speed_spin.setStyleSheet(spin_style)
        self.manual_speed_spin.valueChanged.connect(self._on_manual_speed_changed)
        settings_layout.addWidget(self.manual_speed_spin, 0, 3)
        
        # Auto Speed 输入框
        auto_label = QLabel("AI速度(ms):")
        auto_label.setStyleSheet(label_style)
        settings_layout.addWidget(auto_label, 0, 4)
        self.auto_speed_spin = QSpinBox()
        self.auto_speed_spin.setRange(1, 1000)
        self.auto_speed_spin.setValue(self.auto_speed)
        self.auto_speed_spin.setStyleSheet(spin_style)
        self.auto_speed_spin.valueChanged.connect(self._on_auto_speed_changed)
        settings_layout.addWidget(self.auto_speed_spin, 0, 5)

        top_layout.addLayout(settings_layout)
        # ------------------------

        ai_layout=QHBoxLayout();ai_layout.setSpacing(15)
        self.auto_checkbox=QCheckBox("🤖 AI自动寻路");self.auto_checkbox.stateChanged.connect(self._toggle_auto_mode);self.auto_checkbox.setStyleSheet("font-size:16px;font-weight:bold;color:#ecf0f1;spacing:8px;")
        self.algorithm_combo=QComboBox();self.algorithm_combo.addItems([a.value for a in self.strategies]);self.algorithm_combo.currentTextChanged.connect(self._on_algorithm_changed)
        self.algorithm_combo.setStyleSheet("font-size:16px;padding:8px;border-radius:5px;")
        ai_layout.addStretch();ai_layout.addWidget(self.auto_checkbox);ai_layout.addWidget(self.algorithm_combo);ai_layout.addStretch()
        top_layout.addLayout(ai_layout)
        self.params_container=QWidget();self.params_container.setStyleSheet("QLabel{font-size:14px;color:#ecf0f1;}QSpinBox,QDoubleSpinBox{font-size:14px;padding:5px;border-radius:3px;}")
        self.params_layout=QVBoxLayout(self.params_container);self.params_layout.setContentsMargins(0,5,0,5);top_layout.addWidget(self.params_container);self.params_container.setVisible(False)
        main_layout.addWidget(top_widget)
        self.grid_widget=GridWidget(self.grid_size,self);main_layout.addWidget(self.grid_widget,1);self.setFocusPolicy(Qt.StrongFocus)
# --- 新增：处理UI事件的函数 ---
    def _on_grid_size_changed(self, value):
        """处理地图大小变化的事件"""
        self.grid_size = value
        self.grid_widget.grid_size = value
        # 重新初始化当前策略以适应新地图大小
        self._on_algorithm_changed(self.algorithm_combo.currentText())
        # 地图大小改变，必须重启游戏
        self._new_game()
        print(f"地图大小已更改为: {value}x{value}，游戏已重置。")

    def _on_manual_speed_changed(self, value):
        """处理手动速度变化的事件"""
        self.initial_speed = value
        # 如果当前在手动模式且游戏正在运行，则更新计时器
        if not self.auto_mode and self.timer.isActive():
            self.timer.start(self.initial_speed)

    def _on_auto_speed_changed(self, value):
        """处理AI速度变化的事件"""
        self.auto_speed = value
        # 如果当前在AI模式且游戏正在运行，则更新计时器
        if self.auto_mode and self.timer.isActive():
            self.timer.start(self.auto_speed)
    # ----------------------------


    def _on_algorithm_changed(self,algo_text):
        enum_member = next((member for member in PathfindingAlgorithm if member.value == algo_text), PathfindingAlgorithm.A_STAR)
        
        if hasattr(self.current_strategy, 'is_training') and self.current_strategy.is_training:
            self.current_strategy.toggle_training()

        strategy_class = self.strategies.get(enum_member)
        if strategy_class:
            self.current_strategy = strategy_class(self.grid_size, self)
        else:
            return

        while(item:=self.params_layout.takeAt(0)):
            if item.widget():item.widget().deleteLater()
        params_ui=self.current_strategy.create_parameters_ui()
        if params_ui:self.params_layout.addWidget(params_ui)
        self.params_container.setVisible(self.auto_mode and params_ui is not None)
        if self.auto_mode and self.game_started and not self.game_over and not isinstance(self.current_strategy,RLStrategy):self._calculate_path()
    
    def _toggle_auto_mode(self,state):
        self.auto_mode=(state==Qt.Checked.value);has_params=self.params_layout.count()>0
        self.params_container.setVisible(self.auto_mode and has_params)
        if isinstance(self.current_strategy,RLStrategy)and self.current_strategy.is_training:self.current_strategy.toggle_training()
        if self.timer.isActive():self.timer.start(self.auto_speed if self.auto_mode else self.initial_speed)
        if self.auto_mode and self.game_started and not self.game_over and not isinstance(self.current_strategy,RLStrategy):self._calculate_path()
        else:self.current_path=[]

    def _new_game(self):
        center=self.grid_size//2;self.snake=[(center,center),(center,center-1),(center,center-2)];self.direction='RIGHT';self.next_direction='RIGHT';self._generate_food();self.score=0;self.game_over=False;self.game_started=False
        self.current_path=[];self.path_index=0;self.start_button.setText("开始游戏");self._update_ui()
    
    def _new_game_for_rl(self):
        center=self.grid_size//2;self.snake=[(center,center),(center,center-1),(center,center-2)];self.direction='RIGHT';self.next_direction='RIGHT';self._generate_food();self.score=0;self.game_over=False
    
    def _start_game(self):
        if isinstance(self.current_strategy,RLStrategy)and self.current_strategy.is_training:return
        if self.game_over:self._new_game()
        self.game_started=True;self.game_over=False;self.start_button.setText("重新开始")
        self.timer.start(self.auto_speed if self.auto_mode else self.initial_speed)
        if self.auto_mode:self._calculate_path()
        self.setFocus()

    def _game_loop(self):
        if not self.game_started or self.game_over:self.timer.stop();return
        if self.auto_mode and isinstance(self.current_strategy,RLStrategy):self._rl_play_step()
        else:self._normal_play_step()

    def _normal_play_step(self):
        if self.auto_mode:self._auto_move()
        else:self.direction=self.next_direction
        head=self.snake[0];dr,dc={'UP':(-1,0),'DOWN':(1,0),'LEFT':(0,-1),'RIGHT':(0,1)}[self.direction];new_head=(head[0]+dr,head[1]+dc)
        if not self._is_valid(new_head)or new_head in self.snake:self._end_game();return
        self.snake.insert(0,new_head)
        if new_head==self.food:self.score+=10;self._generate_food();
        else:self.snake.pop()
        if self.auto_mode and new_head==self.food:self._calculate_path()
        self._update_ui()

    def _rl_play_step(self):
        gs = self.get_current_gamestate()
        if not self.current_strategy.agent: return
        # 在调用 act 之前，转换状态
        state = get_rl_state(gs)
        action_idx, _ = self.current_strategy.agent.act(state, is_training=False)
        _,done,_=self.play_step_rl(action_idx)
        if done:self._end_game()
        self._update_ui()
    
    def play_step_rl(self,action_idx):
        action=['UP','DOWN','LEFT','RIGHT'][action_idx];head=self.snake[0]
        if(action=='UP'and self.direction=='DOWN')or(action=='DOWN'and self.direction=='UP')or(action=='LEFT'and self.direction=='RIGHT')or(action=='RIGHT'and self.direction=='LEFT'):action=self.direction
        self.direction=action
        dr,dc={'UP':(-1,0),'DOWN':(1,0),'LEFT':(0,-1),'RIGHT':(0,1)}[action];new_head=(head[0]+dr,head[1]+dc)
        reward=0;self.game_over=is_collision(new_head,self.get_current_gamestate())
        if self.game_over:reward=-10;return reward,True,self.score
        self.snake.insert(0,new_head)
        if new_head==self.food:self.score+=1;reward=10;self._generate_food()
        else:self.snake.pop()
        return reward,False,self.score

    def _auto_move(self):
        if not self.current_path or self.path_index>=len(self.current_path):self._calculate_path()
        if self.current_path and self.path_index<len(self.current_path):
            n_pos=self.current_path[self.path_index];self.path_index+=1;head=self.snake[0]
            if n_pos[0]<head[0]:self.direction='UP'
            elif n_pos[0]>head[0]:self.direction='DOWN'
            elif n_pos[1]<head[1]:self.direction='LEFT'
            else:self.direction='RIGHT'
        else:self._fallback_move()

    def _calculate_path(self):
        if not self.auto_mode or not self.current_strategy or self.game_over:return
        gs=self.get_current_gamestate();obs=set(self.snake[1:])
        path=self.current_strategy.calculate_path(gs,obs)
        if path:self.current_path=path[1:]if len(path)>1 and path[0]==self.snake[0]else path;self.path_index=0
        else:
            tail_finder=AStarStrategy(self.grid_size,self);tail_gs=GameState(self.snake,self.snake[-1],self.direction,self.score,False,self.grid_size)
            tail_path=tail_finder.calculate_path(tail_gs,set(self.snake[1:-1]))
            if tail_path:self.current_path=tail_path[1:];self.path_index=0
            else:self.current_path=[]

    def _fallback_move(self):
        head=self.snake[0];safe_moves=[]
        for d in['UP','DOWN','LEFT','RIGHT']:
            dr,dc={'UP':(-1,0),'DOWN':(1,0),'LEFT':(0,-1),'RIGHT':(0,1)}[d]
            if self._is_valid((head[0]+dr,head[1]+dc))and(head[0]+dr,head[1]+dc)not in self.snake:safe_moves.append(d)
        if safe_moves:self.direction=random.choice(safe_moves)

    def _generate_food(self):
        empty=[(r,c)for r in range(self.grid_size)for c in range(self.grid_size)if(r,c)not in self.snake]
        if empty:self.food=random.choice(empty)
        else:self._end_game()
    
    def _end_game(self):
        self.game_over=True;self.game_started=False;self.timer.stop()
        self.start_button.setText("重新开始");self.score_label.setText(f"游戏结束!分数:{self.score}")

    def _update_ui(self):
        path=self.current_path[self.path_index:]if self.auto_mode and not isinstance(self.current_strategy,RLStrategy)else[]
        viz=self.current_strategy.visualization_data if self.auto_mode and self.current_strategy else None
        self.grid_widget.update_data(self.snake,self.food,path,viz)
        self.score_label.setText(f"分数:{self.score}");self.dock_title_changed.emit(f"贪吃蛇[{self.panel_id}]-分数:{self.score}")

    def keyPressEvent(self,event:QKeyEvent):
        if self.auto_mode:return
        key=event.key()
        if key==Qt.Key_Up and self.direction!='DOWN':self.next_direction='UP'
        elif key==Qt.Key_Down and self.direction!='UP':self.next_direction='DOWN'
        elif key==Qt.Key_Left and self.direction!='RIGHT':self.next_direction='LEFT'
        elif key==Qt.Key_Right and self.direction!='LEFT':self.next_direction='RIGHT'

    def get_config(self):
        cfg={"version":"10.0","auto_mode":self.auto_mode,"current_algorithm":self.algorithm_combo.currentText(),"game_state":{"snake":self.snake,"food":self.food,"direction":self.direction,"score":self.score}}
        if self.current_strategy:cfg["strategy_params"]=self.current_strategy.get_parameters()
        return cfg
    def apply_config(self,cfg):
        self.auto_checkbox.setChecked(cfg.get("auto_mode",False));self.algorithm_combo.setCurrentText(cfg.get("current_algorithm",PathfindingAlgorithm.A_STAR.value))
        gs=cfg.get("game_state",{});self.snake=gs.get("snake",[]);self.food=gs.get("food",(0,0));self.direction=gs.get("direction",'RIGHT');self.score=gs.get("score",0)
        if self.current_strategy and "strategy_params" in cfg:self.current_strategy.apply_parameters(cfg["strategy_params"])
        self._update_ui()
    def _is_valid(self,pos):return 0<=pos[0]<self.grid_size and 0<=pos[1]<self.grid_size
    def on_panel_removed(self):
        if hasattr(self.current_strategy, 'is_training') and self.current_strategy.is_training:
            self.current_strategy.is_training = False
            if hasattr(self.current_strategy, 'training_timer'):
                self.current_strategy.training_timer.stop()
        if self.timer:
            self.timer.stop()
        if hasattr(self, 'current_strategy') and hasattr(self.current_strategy, 'viz_window') and self.current_strategy.viz_window:
            self.current_strategy.viz_window.close()
    def get_current_gamestate(self):return GameState(list(self.snake),self.food,self.direction,self.score,self.game_over,self.grid_size)

# --- 为 GameState 添加辅助方法 ---
def get_legal_actions(state):
    moves={'UP','DOWN','LEFT','RIGHT'};opposites={'UP':'DOWN','DOWN':'UP','LEFT':'RIGHT','RIGHT':'LEFT'}
    if state.direction in opposites:moves.discard(opposites[state.direction])
    legal=[];head=state.snake[0];obstacles=set(state.snake[1:])
    for m in moves:
        dr,dc={'UP':(-1,0),'DOWN':(1,0),'LEFT':(0,-1),'RIGHT':(0,1)}[m];n_pos=(head[0]+dr,head[1]+dc)
        if 0<=n_pos[0]<state.grid_size and 0<=n_pos[1]<state.grid_size and n_pos not in obstacles:legal.append(m)
    return legal
def make_move(state,action):
    dr,dc={'UP':(-1,0),'DOWN':(1,0),'LEFT':(0,-1),'RIGHT':(0,1)}[action];head=state.snake[0];n_head=(head[0]+dr,head[1]+dc)
    if not(0<=n_head[0]<state.grid_size and 0<=n_head[1]<state.grid_size)or n_head in state.snake:state.game_over=True;return
    state.snake.insert(0,n_head);state.direction=action
    if n_head==state.food:
        state.score+=1;empty=[(r,c)for r in range(state.grid_size)for c in range(state.grid_size)if(r,c)not in state.snake]
        if empty:state.food=random.choice(empty)
    else:state.snake.pop()
def get_next_head(state,action):
    dr,dc={'UP':(-1,0),'DOWN':(1,0),'LEFT':(0,-1),'RIGHT':(0,1)}[action];head=state.snake[0]
    return(head[0]+dr,head[1]+dc)
GameState.get_legal_actions=get_legal_actions;GameState.make_move=make_move;GameState.get_next_head=get_next_head

# </final_file_content>

# IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.Tool [attempt_completion] was not executed because a tool has already been used in this message. Only one tool may be used per message. You must assess the first tool's result before proceeding to use the next tool.<environment_details>
# # VSCode Visible Files
# panel_plugins/snake_game/rl_algorithms.py

# # VSCode Open Tabs
# tests/test_main_app.py
# panel_plugins/pid_code_generator/templates/advanced_pid_template.c
# panel_plugins/snake_game/dqn_agent.py
# panel_plugins/snake_game/test_visualization.py
# panel_plugins/snake_game/snake_panel.py
# panel_plugins/snake_game/rl_algorithms.py
# panel_plugins/pid_code_generator/templates/advanced_pid_template.h
# panel_plugins/pid_code_generator/README.md
# panel_plugins/pid_code_generator/advanced_pid_generator.py

# # Recently Modified Files
# These files have been modified since you last accessed them (file was just edited so you may need to re-read it before editing):
# panel_plugins/snake_game/snake_panel.py

# # Current Time
# 2025/6/8 下午10:57:59 (Asia/Shanghai, UTC+8:00)

# # Context Window Usage
# 857,516 / 1,048.576K tokens used (82%)

# # Current Mode
# ACT MODE
# </environment_details>
