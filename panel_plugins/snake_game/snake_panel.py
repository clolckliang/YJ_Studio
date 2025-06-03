# panel_plugins/snake_game/snake_panel.py
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QWidget, QGridLayout, QCheckBox, QComboBox, QSizePolicy,
                             QSpinBox, QDoubleSpinBox) # 导入 QSpinBox 和 QDoubleSpinBox
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from typing import Dict, Any, Optional, List, Tuple, Set
import random
import heapq
import math
from collections import deque
from dataclasses import dataclass
from enum import Enum

# 导入 PanelInterface
try:
    from core.panel_interface import PanelInterface
except ImportError:
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from core.panel_interface import PanelInterface


class PathfindingAlgorithm(Enum):
    """寻路算法枚举"""
    A_STAR = "A* 算法"
    BFS = "BFS 广度优先"
    DFS = "DFS 深度优先"
    DIJKSTRA = "Dijkstra 算法"
    GREEDY = "贪心算法"
    POTENTIAL_FIELD = "人工势场法"
    GENETIC = "遗传算法"


@dataclass
class PathNode:
    """寻路算法使用的节点类"""
    position: Tuple[int, int]
    g_cost: float = 0  # 从起点到当前节点的实际代价
    h_cost: float = 0  # 从当前节点到终点的启发式代价
    f_cost: float = 0  # 总代价 f = g + h
    parent: Optional['PathNode'] = None
    
    def __lt__(self, other):
        return self.f_cost < other.f_cost


@dataclass
class Individual:
    """遗传算法个体类"""
    genes: List[str]  # 移动序列
    fitness: float = 0.0
    
    def __lt__(self, other):
        return self.fitness > other.fitness  # 适应度越高越好


class SnakeGamePanel(PanelInterface):
    """
    贪吃蛇游戏面板实现
    
    实现了一个完整的贪吃蛇游戏，包括：
    - 蛇的移动和控制
    - 食物生成
    - 碰撞检测
    - 分数计算
    - 多种自动寻路算法模式
    """
    
    # PanelInterface 必须定义的静态属性
    PANEL_TYPE_NAME: str = "snake_game"
    PANEL_DISPLAY_NAME: str = "贪吃蛇游戏"
    
    # 游戏常量 - 优化网格大小和界面
    GRID_SIZE = 20         # 增加网格大小，提高密度
    CELL_SIZE = 20          # 减小单元格大小，以适应高密度网格
    INITIAL_SPEED = 200     # 毫秒
    AUTO_SPEED = 100        # 自动模式的速度（更快一些，适应大地图）
    
    # 遗传算法参数 (默认值)
    GA_POPULATION_SIZE = 50  # 增加种群大小以适应大网格
    GA_GENERATIONS = 30      # 增加代数
    GA_MUTATION_RATE = 0.1
    GA_CROSSOVER_RATE = 0.8

    # 人工势场法参数 (默认值)
    PF_ATTRACTIVE_K = 1.0 
    PF_REPULSIVE_K_MULTIPLIER = 5.0 # 原本是 self.GRID_SIZE * 5.0，现在改为乘数
    PF_REPULSIVE_RANGE_DIVISOR = 5.0 # 原本是 self.GRID_SIZE / 5.0，现在改为除数
    
    def __init__(self,
                 panel_id: int,
                 main_window_ref: 'SerialDebugger',
                 initial_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        """
        初始化贪吃蛇游戏面板
        
        Args:
            panel_id: 面板唯一标识符
            main_window_ref: 主窗口引用
            initial_config: 初始配置数据
            parent: 父级组件
        """
        super().__init__(panel_id, main_window_ref, initial_config, parent)
        
        # 游戏状态
        self.snake: List[Tuple[int, int]] = []
        self.food: Tuple[int, int] = (0, 0)
        self.direction: str = 'RIGHT'
        self.next_direction: str = 'RIGHT'
        self.score: int = 0
        self.game_over: bool = False
        self.game_started: bool = False
        
        # 自动模式相关
        self.auto_mode: bool = False
        self.current_algorithm: PathfindingAlgorithm = PathfindingAlgorithm.A_STAR
        self.current_path: List[Tuple[int, int]] = []
        self.path_index: int = 0
        
        # 遗传算法状态
        self.ga_population: List[Individual] = []
        self.ga_generation: int = 0
        self.ga_best_path: List[str] = []
        
        # 势场法状态
        self.potential_field: List[List[float]] = []
        
        # 游戏定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._game_loop)
        
        # UI组件
        self.score_label: Optional[QLabel] = None
        self.grid_layout: Optional[QGridLayout] = None
        self.cells: List[List[QLabel]] = [
            [None for _ in range(self.GRID_SIZE)] for _ in range(self.GRID_SIZE)
        ]
        self.start_button: Optional[QPushButton] = None
        self.auto_checkbox: Optional[QCheckBox] = None
        self.algorithm_combo: Optional[QComboBox] = None
        self.pathfinding_info_label: Optional[QLabel] = None

        # 遗传算法参数UI组件
        self.ga_params_group: Optional[QWidget] = None
        self.ga_pop_size_spinbox: Optional[QSpinBox] = None
        self.ga_generations_spinbox: Optional[QSpinBox] = None
        self.ga_mutation_rate_spinbox: Optional[QDoubleSpinBox] = None
        self.ga_crossover_rate_spinbox: Optional[QDoubleSpinBox] = None

        # 人工势场法参数UI组件
        self.pf_params_group: Optional[QWidget] = None
        self.pf_attractive_k_spinbox: Optional[QDoubleSpinBox] = None
        self.pf_repulsive_k_multiplier_spinbox: Optional[QDoubleSpinBox] = None
        self.pf_repulsive_range_divisor_spinbox: Optional[QDoubleSpinBox] = None
        
        # 初始化游戏界面和状态
        self._init_ui() # 先初始化UI元素
        self._new_game() # 然后初始化游戏逻辑状态 (这会设置一个正确的初始snake)
        
        # 应用外部传入的初始配置 (这可能会覆盖 _new_game 设置的snake)
        if initial_config:
            self.apply_config(initial_config)
    
    def _init_ui(self) -> None:
        """构建贪吃蛇游戏界面 - 全面重写UI布局和样式"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0) # 整体布局无间距
        main_layout.setContentsMargins(0, 0, 0, 0) # 整体布局无边距
        
        # 顶部控制区域
        top_control_widget = QWidget()
        top_control_layout = QVBoxLayout(top_control_widget)
        top_control_layout.setSpacing(10)
        top_control_layout.setContentsMargins(20, 15, 20, 15)
        top_control_widget.setStyleSheet("""
            QWidget {
                background-color: #2c3e50; /* 深蓝色背景 */
                border-bottom-left-radius: 15px;
                border-bottom-right-radius: 15px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            }
        """)

        # 标题
        title_label = QLabel("🐍 贪吃蛇游戏")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #ecf0f1; /* 浅灰色文字 */
                padding: 5px;
            }
        """)
        top_control_layout.addWidget(title_label)

        # 分数和开始按钮行
        score_start_layout = QHBoxLayout()
        score_start_layout.setSpacing(20)
        score_start_layout.setAlignment(Qt.AlignCenter)

        self.score_label = QLabel("分数: 0")
        self.score_label.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: bold;
                color: #2ecc71; /* 绿色分数 */
                background-color: #34495e; /* 深一点的背景 */
                padding: 10px 20px;
                border-radius: 10px;
                border: 2px solid #27ae60;
            }
        """)
        score_start_layout.addWidget(self.score_label)
        
        self.start_button = QPushButton("🎮 开始游戏")
        self.start_button.clicked.connect(self._start_game)
        self.start_button.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                color: white;
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3498db, stop: 1 #2980b9); /* 蓝色渐变 */
                border: none;
                border-radius: 10px;
                padding: 10px 25px;
                min-width: 150px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #2980b9, stop: 1 #3498db);
            }
            QPushButton:pressed {
                background: #2980b9;
            }
        """)
        score_start_layout.addWidget(self.start_button)
        top_control_layout.addLayout(score_start_layout)

        # AI控制行
        ai_control_layout = QHBoxLayout()
        ai_control_layout.setSpacing(15)
        ai_control_layout.setAlignment(Qt.AlignCenter)

        self.auto_checkbox = QCheckBox("🤖 AI自动寻路")
        self.auto_checkbox.setToolTip("启用AI自动寻路算法控制蛇移动")
        self.auto_checkbox.stateChanged.connect(self._toggle_auto_mode)
        self.auto_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 16px;
                font-weight: bold;
                color: #ecf0f1; /* 浅灰色文字 */
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 5px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #7f8c8d; /* 灰色边框 */
                background-color: #bdc3c7; /* 浅灰色背景 */
            }
            QCheckBox::indicator:checked {
                border: 2px solid #27ae60; /* 绿色边框 */
                background-color: #2ecc71; /* 绿色背景 */
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iMTAiIHZpZXdCb3g9IjAgMCAxMCAxMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTggMkwzLjU2LjVMMiA1IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4=);
            }
        """)
        ai_control_layout.addWidget(self.auto_checkbox)
        
        self.algorithm_combo = QComboBox()
        for algorithm in PathfindingAlgorithm:
            self.algorithm_combo.addItem(algorithm.value)
        self.algorithm_combo.setCurrentText(PathfindingAlgorithm.A_STAR.value)
        self.algorithm_combo.currentTextChanged.connect(self._on_algorithm_changed)
        self.algorithm_combo.setToolTip("选择寻路算法")
        self.algorithm_combo.setStyleSheet("""
            QComboBox {
                font-size: 16px;
                padding: 8px 12px;
                border: 2px solid #3498db;
                border-radius: 8px;
                background-color: white;
                color: #2c3e50;
                min-width: 180px;
            }
            QComboBox:hover {
                border-color: #2980b9;
            }
            QComboBox::drop-down {
                border: none;
                width: 25px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 6px solid #3498db;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #3498db;
                border-radius: 8px;
                background-color: white;
                selection-background-color: #e0f2f7;
                color: #2c3e50;
            }
        """)
        ai_control_layout.addWidget(self.algorithm_combo)
        top_control_layout.addLayout(ai_control_layout)

        # 遗传算法参数控制区域
        self.ga_params_group = QWidget()
        ga_params_layout = QGridLayout(self.ga_params_group)
        ga_params_layout.setSpacing(10)
        ga_params_layout.setContentsMargins(0, 10, 0, 0) # 顶部留白
        self.ga_params_group.setStyleSheet("""
            QWidget {
                background-color: #34495e; /* 遗传算法参数区域背景 */
                border-radius: 8px;
                padding: 10px;
                margin-top: 10px;
            }
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #ecf0f1;
            }
            QSpinBox, QDoubleSpinBox {
                font-size: 14px;
                padding: 5px;
                border: 1px solid #7f8c8d;
                border-radius: 5px;
                background-color: white;
                color: #2c3e50;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                width: 16px;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                width: 16px;
            }
        """)

        # 种群大小
        ga_params_layout.addWidget(QLabel("种群大小:"), 0, 0)
        self.ga_pop_size_spinbox = QSpinBox()
        self.ga_pop_size_spinbox.setRange(10, 500)
        self.ga_pop_size_spinbox.setSingleStep(10)
        self.ga_pop_size_spinbox.setValue(self.GA_POPULATION_SIZE)
        self.ga_pop_size_spinbox.valueChanged.connect(self._on_ga_pop_size_changed)
        ga_params_layout.addWidget(self.ga_pop_size_spinbox, 0, 1)

        # 迭代次数
        ga_params_layout.addWidget(QLabel("迭代次数:"), 1, 0)
        self.ga_generations_spinbox = QSpinBox()
        self.ga_generations_spinbox.setRange(10, 200)
        self.ga_generations_spinbox.setSingleStep(5)
        self.ga_generations_spinbox.setValue(self.GA_GENERATIONS)
        self.ga_generations_spinbox.valueChanged.connect(self._on_ga_generations_changed)
        ga_params_layout.addWidget(self.ga_generations_spinbox, 1, 1)

        # 变异率
        ga_params_layout.addWidget(QLabel("变异率:"), 0, 2)
        self.ga_mutation_rate_spinbox = QDoubleSpinBox()
        self.ga_mutation_rate_spinbox.setRange(0.01, 1.0)
        self.ga_mutation_rate_spinbox.setSingleStep(0.01)
        self.ga_mutation_rate_spinbox.setDecimals(2)
        self.ga_mutation_rate_spinbox.setValue(self.GA_MUTATION_RATE)
        self.ga_mutation_rate_spinbox.valueChanged.connect(self._on_ga_mutation_rate_changed)
        ga_params_layout.addWidget(self.ga_mutation_rate_spinbox, 0, 3)

        # 交叉率
        ga_params_layout.addWidget(QLabel("交叉率:"), 1, 2)
        self.ga_crossover_rate_spinbox = QDoubleSpinBox()
        self.ga_crossover_rate_spinbox.setRange(0.01, 1.0)
        self.ga_crossover_rate_spinbox.setSingleStep(0.01)
        self.ga_crossover_rate_spinbox.setDecimals(2)
        self.ga_crossover_rate_spinbox.setValue(self.GA_CROSSOVER_RATE)
        self.ga_crossover_rate_spinbox.valueChanged.connect(self._on_ga_crossover_rate_changed)
        ga_params_layout.addWidget(self.ga_crossover_rate_spinbox, 1, 3)

        top_control_layout.addWidget(self.ga_params_group) # 将遗传算法参数组添加到顶部控制布局


        # 人工势场法参数控制区域
        self.pf_params_group = QWidget()
        pf_params_layout = QGridLayout(self.pf_params_group)
        pf_params_layout.setSpacing(10)
        pf_params_layout.setContentsMargins(0, 10, 0, 0) # 顶部留白
        self.pf_params_group.setStyleSheet("""
            QWidget {
                background-color: #34495e; /* 人工势场法参数区域背景 */
                border-radius: 8px;
                padding: 10px;
                margin-top: 10px;
            }
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #ecf0f1;
            }
            QDoubleSpinBox {
                font-size: 14px;
                padding: 5px;
                border: 1px solid #7f8c8d;
                border-radius: 5px;
                background-color: white;
                color: #2c3e50;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 16px;
            }
        """)

        # 吸引力系数
        pf_params_layout.addWidget(QLabel("吸引力系数 (k_att):"), 0, 0)
        self.pf_attractive_k_spinbox = QDoubleSpinBox()
        self.pf_attractive_k_spinbox.setRange(0.1, 10.0)
        self.pf_attractive_k_spinbox.setSingleStep(0.1)
        self.pf_attractive_k_spinbox.setDecimals(1)
        self.pf_attractive_k_spinbox.setValue(self.PF_ATTRACTIVE_K)
        self.pf_attractive_k_spinbox.valueChanged.connect(self._on_pf_attractive_k_changed)
        pf_params_layout.addWidget(self.pf_attractive_k_spinbox, 0, 1)

        # 排斥力系数乘数
        pf_params_layout.addWidget(QLabel("排斥力系数乘数 (k_rep_mult):"), 1, 0)
        self.pf_repulsive_k_multiplier_spinbox = QDoubleSpinBox()
        self.pf_repulsive_k_multiplier_spinbox.setRange(1.0, 20.0)
        self.pf_repulsive_k_multiplier_spinbox.setSingleStep(0.5)
        self.pf_repulsive_k_multiplier_spinbox.setDecimals(1)
        self.pf_repulsive_k_multiplier_spinbox.setValue(self.PF_REPULSIVE_K_MULTIPLIER)
        self.pf_repulsive_k_multiplier_spinbox.valueChanged.connect(self._on_pf_repulsive_k_multiplier_changed)
        pf_params_layout.addWidget(self.pf_repulsive_k_multiplier_spinbox, 1, 1)

        # 排斥力范围除数
        pf_params_layout.addWidget(QLabel("排斥力范围除数 (range_div):"), 2, 0)
        self.pf_repulsive_range_divisor_spinbox = QDoubleSpinBox()
        self.pf_repulsive_range_divisor_spinbox.setRange(1.0, 10.0)
        self.pf_repulsive_range_divisor_spinbox.setSingleStep(0.5)
        self.pf_repulsive_range_divisor_spinbox.setDecimals(1)
        self.pf_repulsive_range_divisor_spinbox.setValue(self.PF_REPULSIVE_RANGE_DIVISOR)
        self.pf_repulsive_range_divisor_spinbox.valueChanged.connect(self._on_pf_repulsive_range_divisor_changed)
        pf_params_layout.addWidget(self.pf_repulsive_range_divisor_spinbox, 2, 1)

        top_control_layout.addWidget(self.pf_params_group) # 将人工势场法参数组添加到顶部控制布局
        self.pf_params_group.setVisible(False) # 默认隐藏

        self.pathfinding_info_label = QLabel("")
        self.pathfinding_info_label.setAlignment(Qt.AlignCenter)
        self.pathfinding_info_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #ecf0f1;
                background-color: #34495e;
                padding: 10px;
                border-radius: 8px;
                margin-top: 10px;
            }
        """)
        self.pathfinding_info_label.setWordWrap(True)
        top_control_layout.addWidget(self.pathfinding_info_label)

        main_layout.addWidget(top_control_widget)
        
        # 游戏区域容器
        game_container = QWidget()
        # 显式设置 sizePolicy 为 Expanding，让其在父布局中尽可能扩展
        game_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) 
        game_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a; /* 更深的背景色 */
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                padding: 0px; /* 移除内边距，确保网格紧贴容器 */
                margin-top: 15px; /* 与上方控件的间距 */
            }
        """)
        game_layout = QVBoxLayout(game_container)
        game_layout.setSpacing(0)
        game_layout.setContentsMargins(0, 0, 0, 0)
        # 移除居中对齐，让网格可以拉伸

        # 游戏网格
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(0) # 关键: 确保格子间距为0
        self.grid_layout.setContentsMargins(0, 0, 0, 0) # 关键: 确保网格布局没有内容边距
        
        # 确保每个单元格尺寸精确，并允许拉伸
        for i in range(self.GRID_SIZE):
            self.grid_layout.setColumnMinimumWidth(i, self.CELL_SIZE)
            self.grid_layout.setRowMinimumHeight(i, self.CELL_SIZE)
            self.grid_layout.setColumnStretch(i, 1) # 允许列拉伸
            self.grid_layout.setRowStretch(i, 1) # 允许行拉伸

        # 创建游戏网格
        for row in range(self.GRID_SIZE):
            for col in range(self.GRID_SIZE):
                cell = QLabel("")
                # 不再设置 fixedSize，让其根据布局拉伸
                # cell.setFixedSize(self.CELL_SIZE, self.CELL_SIZE) 
                cell.setStyleSheet("""
                    QLabel {
                        background-color: #34495e; /* 网格单元格背景色 */
                        border: none; /* 移除边框 */
                        border-radius: 0px; /* 移除圆角 */
                        margin: 0px; /* 移除默认外边距 */
                        padding: 0px; /* 移除默认内边距 */
                    }
                """)
                self.cells[row][col] = cell
                self.grid_layout.addWidget(cell, row, col)
        
        game_layout.addLayout(self.grid_layout)
        # 在主布局中给 game_container 设置拉伸因子，使其占据剩余空间
        main_layout.addWidget(game_container, 1) 
        
        # 底部帮助信息
        help_label = QLabel("⌨️ 方向键控制 | 🎯 吃红色食物得分 | 🤖 可开启AI自动寻路")
        help_label.setAlignment(Qt.AlignCenter)
        help_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #7f8c8d; /* 灰色文字 */
                padding: 10px;
                background-color: #2c3e50; /* 与顶部控制区相同的背景 */
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                margin-top: 15px; /* 与游戏区域的间距 */
            }
        """)
        main_layout.addWidget(help_label)
        
        self.setLayout(main_layout)
        
        # 设置面板可获得焦点
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()
    
    # 遗传算法参数值改变时的槽函数
    def _on_ga_pop_size_changed(self, value: int) -> None:
        self.GA_POPULATION_SIZE = value
        if self.auto_mode and self.current_algorithm == PathfindingAlgorithm.GENETIC:
            self._calculate_path() # 参数改变时重新计算路径

    def _on_ga_generations_changed(self, value: int) -> None:
        self.GA_GENERATIONS = value
        if self.auto_mode and self.current_algorithm == PathfindingAlgorithm.GENETIC:
            self._calculate_path()

    def _on_ga_mutation_rate_changed(self, value: float) -> None:
        self.GA_MUTATION_RATE = value
        if self.auto_mode and self.current_algorithm == PathfindingAlgorithm.GENETIC:
            self._calculate_path()

    def _on_ga_crossover_rate_changed(self, value: float) -> None:
        self.GA_CROSSOVER_RATE = value
        if self.auto_mode and self.current_algorithm == PathfindingAlgorithm.GENETIC:
            self._calculate_path()

    # 新增：人工势场法参数值改变时的槽函数
    def _on_pf_attractive_k_changed(self, value: float) -> None:
        self.PF_ATTRACTIVE_K = value
        if self.auto_mode and self.current_algorithm == PathfindingAlgorithm.POTENTIAL_FIELD:
            self._calculate_path()

    def _on_pf_repulsive_k_multiplier_changed(self, value: float) -> None:
        self.PF_REPULSIVE_K_MULTIPLIER = value
        if self.auto_mode and self.current_algorithm == PathfindingAlgorithm.POTENTIAL_FIELD:
            self._calculate_path()

    def _on_pf_repulsive_range_divisor_changed(self, value: float) -> None:
        self.PF_REPULSIVE_RANGE_DIVISOR = value
        if self.auto_mode and self.current_algorithm == PathfindingAlgorithm.POTENTIAL_FIELD:
            self._calculate_path()

    def _on_algorithm_changed(self, algorithm_text: str) -> None:
        """算法选择改变"""
        for algorithm in PathfindingAlgorithm:
            if algorithm.value == algorithm_text:
                self.current_algorithm = algorithm
                break
        
        # 根据选择的算法，显示/隐藏遗传算法参数控制和人工势场法参数控制
        is_genetic_algo = (self.current_algorithm == PathfindingAlgorithm.GENETIC)
        is_potential_field_algo = (self.current_algorithm == PathfindingAlgorithm.POTENTIAL_FIELD)

        if self.ga_params_group:
            self.ga_params_group.setVisible(is_genetic_algo and self.auto_mode)
        if self.pf_params_group:
            self.pf_params_group.setVisible(is_potential_field_algo and self.auto_mode)

        # 如果游戏正在进行且是自动模式，重新计算路径
        if self.auto_mode and self.game_started and not self.game_over:
            self._calculate_path()
    
    def _toggle_auto_mode(self, state: int) -> None:
        """切换自动模式"""
        self.auto_mode = state == Qt.Checked.value
        
        # 根据自动模式和当前算法，控制参数组的可见性
        is_genetic_algo_and_auto = self.auto_mode and (self.current_algorithm == PathfindingAlgorithm.GENETIC)
        is_potential_field_algo_and_auto = self.auto_mode and (self.current_algorithm == PathfindingAlgorithm.POTENTIAL_FIELD)

        if self.ga_params_group:
            self.ga_params_group.setVisible(is_genetic_algo_and_auto)
        if self.pf_params_group:
            self.pf_params_group.setVisible(is_potential_field_algo_and_auto)


        if self.auto_mode:
            self.pathfinding_info_label.setText(f"🚀 AI寻路中... ({self.current_algorithm.value})")
            # 如果游戏正在进行，立即计算路径
            if self.game_started and not self.game_over:
                self._calculate_path()
                # 调整定时器速度
                if self.timer.isActive():
                    self.timer.stop()
                    self.timer.start(self.AUTO_SPEED)
        else:
            self.pathfinding_info_label.setText("")
            self.current_path = []
            self.path_index = 0
            # 恢复正常速度
            if self.timer.isActive():
                self.timer.stop()
                self.timer.start(self.INITIAL_SPEED)
    
    def _new_game(self) -> None:
        """初始化新游戏"""
        # 初始化蛇
        center = self.GRID_SIZE // 2
        self.snake = [(center, center), (center, center-1), (center, center-2)]
        self.direction = 'RIGHT'
        self.next_direction = 'RIGHT'
        
        # 生成食物
        self._generate_food()
        
        # 重置分数和路径
        self.score = 0
        self.game_over = False
        self.game_started = False
        self.current_path = []
        self.path_index = 0
        
        # 重置遗传算法状态
        self.ga_population = []
        self.ga_generation = 0
        self.ga_best_path = []
        
        # 更新UI
        self._update_ui()
    
    def _start_game(self) -> None:
        """开始游戏"""
        if self.game_over: # 如果游戏已结束，则调用 _new_game 重置
            self._new_game() 
            # _new_game 内部已将 game_started 置为 False, 此处需置为 True
        
        # 无论如何，开始或重新开始游戏，都应将 game_started 设为 True
        self.game_started = True
        self.game_over = False # 确保 game_over 状态被重置

        if self.start_button:
            self.start_button.setText("🔄 重新开始")
        
        # 根据模式选择合适的速度
        speed = self.AUTO_SPEED if self.auto_mode else self.INITIAL_SPEED
        self.timer.start(speed)
        
        # 如果是自动模式，立即计算路径
        if self.auto_mode:
            self._calculate_path()
        
        self._update_ui() # 确保UI在开始时刷新
        self.setFocus() # 确保面板获得焦点以接收键盘事件
    
    def _game_loop(self) -> None:
        """游戏主循环"""
        if not self.game_started or self.game_over:
            return
        
        # 自动模式下使用寻路算法
        if self.auto_mode:
            self._auto_move()
        else:
            # 手动模式：更新方向
            self.direction = self.next_direction
        
        # 移动蛇
        head_row, head_col = self.snake[0]
        
        if self.direction == 'UP':
            new_head = (head_row-1, head_col)
        elif self.direction == 'DOWN':
            new_head = (head_row+1, head_col)
        elif self.direction == 'LEFT':
            new_head = (head_row, head_col-1)
        else:  # RIGHT
            new_head = (head_row, head_col+1)
        
        # 检查碰撞
        if self._check_collision(new_head):
            self._end_game()
            return
            
        # 移动蛇
        self.snake.insert(0, new_head)
        
        # 检查是否吃到食物
        if new_head == self.food:
            self.score += 10
            self._generate_food()
            # 自动模式下重新计算路径
            if self.auto_mode:
                self._calculate_path()
        else:
            self.snake.pop()
        
        # 更新UI
        self._update_ui()
    
    def _auto_move(self) -> None:
        """自动模式移动逻辑"""
        # 如果没有路径或路径已走完，重新计算
        if not self.current_path or self.path_index >= len(self.current_path):
            self._calculate_path()
            
        # 如果仍然没有路径，尝试随机移动避免死循环
        if not self.current_path:
            self._fallback_move()
            return
            
        # 按照路径移动
        if self.path_index < len(self.current_path):
            next_pos = self.current_path[self.path_index]
            self.path_index += 1
            
            # 根据下一个位置计算方向
            head_row, head_col = self.snake[0]
            next_row, next_col = next_pos
            
            if next_row < head_row:
                self.direction = 'UP'
            elif next_row > head_row:
                self.direction = 'DOWN'
            elif next_col < head_col:
                self.direction = 'LEFT'
            else:
                self.direction = 'RIGHT'
    
    def _fallback_move(self) -> None:
        """备用移动策略：随机选择一个安全方向"""
        head_row, head_col = self.snake[0]
        possible_moves = []
        
        # 检查所有可能的移动方向
        directions_map = {
            'UP': (head_row-1, head_col),
            'DOWN': (head_row+1, head_col),
            'LEFT': (head_row, head_col-1),
            'RIGHT': (head_row, head_col+1)
        }
        
        # 优先选择不后退的方向
        valid_directions = ['UP', 'DOWN', 'LEFT', 'RIGHT']
        if self.direction == 'UP': valid_directions.remove('DOWN')
        elif self.direction == 'DOWN': valid_directions.remove('UP')
        elif self.direction == 'LEFT': valid_directions.remove('RIGHT')
        elif self.direction == 'RIGHT': valid_directions.remove('LEFT')

        for move_dir in valid_directions:
            pos = directions_map[move_dir]
            if not self._check_collision(pos):
                possible_moves.append(move_dir)
        
        if possible_moves:
            self.direction = random.choice(possible_moves)
            self.pathfinding_info_label.setText("🎲 AI随机移动 (安全)")
        else: # 如果没有安全的不后退方向，则允许后退（但通常意味着死路）
            all_possible_moves = []
            for move_dir, pos in directions_map.items():
                 if not self._check_collision(pos):
                    all_possible_moves.append(move_dir)
            if all_possible_moves:
                self.direction = random.choice(all_possible_moves)
                self.pathfinding_info_label.setText("🎲 AI随机移动 (紧急)")
            else:
                self.pathfinding_info_label.setText("⚠️ AI无路可走")

    def _calculate_path(self) -> None:
        """根据当前选择的算法计算路径"""
        if not self.snake: # 蛇不存在则不计算
            return
        if self.game_over: # 游戏结束不计算
            return

        start = self.snake[0]
        goal = self.food
        # 寻路时，蛇的身体（除了即将移动的尾巴）都是障碍物
        # 如果蛇长为1，则没有身体障碍
        snake_body_set = set(self.snake) if len(self.snake) == 1 else set(self.snake[:-1])

        algorithm_map = {
            PathfindingAlgorithm.A_STAR: self._a_star_pathfinding,
            PathfindingAlgorithm.BFS: self._bfs_pathfinding,
            PathfindingAlgorithm.DFS: self._dfs_pathfinding,
            PathfindingAlgorithm.DIJKSTRA: self._dijkstra_pathfinding,
            PathfindingAlgorithm.GREEDY: self._greedy_pathfinding,
            PathfindingAlgorithm.POTENTIAL_FIELD: self._potential_field_pathfinding,
            PathfindingAlgorithm.GENETIC: self._genetic_pathfinding,
        }
        
        pathfinding_func = algorithm_map.get(self.current_algorithm)
        if pathfinding_func:
            path = pathfinding_func(start, goal, snake_body_set)
            
            if path and len(path) > 1: # 路径至少包含起点和下一个点
                self.current_path = path[1:] # 路径不包含起点本身
                self.path_index = 0
                self.pathfinding_info_label.setText(
                    f"✅ {self.current_algorithm.value} - 找到路径 (长度: {len(self.current_path)})"
                )
            else:
                self.current_path = []
                self.path_index = 0
                self.pathfinding_info_label.setText(f"❌ {self.current_algorithm.value} - 未找到路径")
    
    # === 各种寻路算法实现 ===
    
    def _a_star_pathfinding(self, start: Tuple[int, int], goal: Tuple[int, int], 
                           obstacles: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """A*寻路算法实现"""
        open_set = []
        closed_set: Set[Tuple[int, int]] = set()
        
        start_node = PathNode(
            position=start,
            g_cost=0,
            h_cost=self._heuristic(start, goal),
            f_cost=0, # f_cost 会在下面计算
            parent=None
        )
        start_node.f_cost = start_node.g_cost + start_node.h_cost
        
        heapq.heappush(open_set, start_node)
        # 使用字典存储节点信息，避免重复创建和快速查找
        node_map: Dict[Tuple[int, int], PathNode] = {start: start_node}
        
        while open_set:
            current_node = heapq.heappop(open_set)
            current_pos = current_node.position
            
            if current_pos == goal:
                return self._reconstruct_path(current_node)
            
            if current_pos in closed_set: # 如果已在closed_set中，则跳过
                continue
            closed_set.add(current_pos)
            
            for neighbor_pos in self._get_neighbors(current_pos):
                if not self._is_valid_position(neighbor_pos) or neighbor_pos in obstacles:
                    continue
                
                # 如果邻居已经在 closed_set 中，则跳过
                if neighbor_pos in closed_set:
                    continue

                tentative_g_cost = current_node.g_cost + 1 # 假设每步代价为1
                
                neighbor_node = node_map.get(neighbor_pos)

                if neighbor_node is None or tentative_g_cost < neighbor_node.g_cost:
                    if neighbor_node is None:
                        neighbor_node = PathNode(
                            position=neighbor_pos,
                            h_cost=self._heuristic(neighbor_pos, goal)
                        )
                        node_map[neighbor_pos] = neighbor_node
                    
                    neighbor_node.parent = current_node
                    neighbor_node.g_cost = tentative_g_cost
                    neighbor_node.f_cost = tentative_g_cost + neighbor_node.h_cost
                    
                    # 检查是否已在 open_set 中，避免重复添加（heapq不直接支持update）
                    # 简单的做法是直接添加，因为 heapq 会处理最小值，但可能导致 open_set 略大
                    # 更优化的做法是标记已在 open_set 或使用支持更新优先级的队列
                    heapq.heappush(open_set, neighbor_node)
        
        return [] # 未找到路径
    
    def _bfs_pathfinding(self, start: Tuple[int, int], goal: Tuple[int, int], 
                        obstacles: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """BFS广度优先搜索算法"""
        queue = deque([PathNode(position=start, parent=None)])
        visited = {start} # 用于记录已访问或已在队列中的节点位置
        
        while queue:
            current_node = queue.popleft()
            current_pos = current_node.position

            if current_pos == goal:
                return self._reconstruct_path(current_node)
            
            for neighbor_pos in self._get_neighbors(current_pos):
                if (self._is_valid_position(neighbor_pos) and
                    neighbor_pos not in obstacles and
                    neighbor_pos not in visited): # 确保邻居有效、不是障碍物且未访问过
                    
                    visited.add(neighbor_pos)
                    neighbor_node = PathNode(position=neighbor_pos, parent=current_node)
                    queue.append(neighbor_node)
        
        return [] # 未找到路径
    
    def _dfs_pathfinding(self, start: Tuple[int, int], goal: Tuple[int, int], 
                        obstacles: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """DFS深度优先搜索算法"""
        stack = [PathNode(position=start, parent=None)]
        # 对于DFS，visited通常在节点从栈中弹出并处理其邻居时标记，
        # 或者在节点加入栈之前标记，以避免重复访问和无限循环。
        # 这里选择在加入栈之前标记，以防止同一个节点被多次加入栈。
        visited_positions = {start} 
        
        while stack:
            current_node = stack.pop()
            current_pos = current_node.position
            
            if current_pos == goal:
                return self._reconstruct_path(current_node)
            
            # DFS通常按特定顺序（如逆时针或顺时针）扩展邻居，
            # 这里简单按_get_neighbors返回的顺序
            for neighbor_pos in self._get_neighbors(current_pos):
                if (self._is_valid_position(neighbor_pos) and
                    neighbor_pos not in obstacles and
                    neighbor_pos not in visited_positions):
                    
                    visited_positions.add(neighbor_pos)
                    neighbor_node = PathNode(position=neighbor_pos, parent=current_node)
                    stack.append(neighbor_node)
        
        return [] # 未找到路径

    def _dijkstra_pathfinding(self, start: Tuple[int, int], goal: Tuple[int, int], 
                             obstacles: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Dijkstra算法实现 (等同于A*中h_cost=0的情况)"""
        # Dijkstra 可以看作是 A* 算法中启发函数 h_cost 恒为0的特例
        # 这里直接复用 A* 的逻辑，并将 h_cost 设为0
        open_set = [] 
        # closed_set: Set[Tuple[int, int]] = set() # Dijkstra 通常不需要显式的 closed_set，通过已访问的距离判断

        start_node = PathNode(
            position=start,
            g_cost=0,
            h_cost=0, # Dijkstra 的启发成本为0
            f_cost=0, 
            parent=None
        )
        # start_node.f_cost = start_node.g_cost # f_cost = g_cost for Dijkstra

        heapq.heappush(open_set, start_node)
        node_map: Dict[Tuple[int, int], PathNode] = {start: start_node}
        
        while open_set:
            current_node = heapq.heappop(open_set)
            current_pos = current_node.position
            
            # 如果当前节点的 g_cost 大于已记录的到该点的最短距离，则跳过 (优化)
            # (需要一个 dist 字典来记录最短距离，这里简化，依赖于 heapq 的性质)
            if current_node.g_cost > node_map[current_pos].g_cost and node_map[current_pos].parent is not None :
                 continue

            if current_pos == goal:
                return self._reconstruct_path(current_node)
            
            # closed_set.add(current_pos) # Dijkstra不需要显式closed_set，因为总是从open_set取最小g_cost

            for neighbor_pos in self._get_neighbors(current_pos):
                if not self._is_valid_position(neighbor_pos) or neighbor_pos in obstacles:
                    continue
                
                tentative_g_cost = current_node.g_cost + 1 # 每步代价为1
                
                neighbor_node_in_map = node_map.get(neighbor_pos)

                if neighbor_node_in_map is None or tentative_g_cost < neighbor_node_in_map.g_cost:
                    if neighbor_node_in_map is None:
                        new_neighbor_node = PathNode(position=neighbor_pos, h_cost=0) # h_cost=0
                        node_map[neighbor_pos] = new_neighbor_node
                        neighbor_node_in_map = new_neighbor_node
                    
                    neighbor_node_in_map.parent = current_node
                    neighbor_node_in_map.g_cost = tentative_g_cost
                    neighbor_node_in_map.f_cost = tentative_g_cost # f_cost = g_cost
                    
                    heapq.heappush(open_set, neighbor_node_in_map)
        
        return []

    def _greedy_pathfinding(self, start: Tuple[int, int], goal: Tuple[int, int], 
                           obstacles: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """贪心算法实现（只考虑启发式距离）"""
        # 贪心算法可以看作是 A* 算法中 g_cost 恒为0的特例，只用 h_cost (启发式)
        open_set = [] # 优先队列，按 h_cost 排序 (PathNode的 __lt__ 是按 f_cost)
                      # 为了直接用 PathNode，我们将 f_cost 设置为 h_cost
        
        start_node = PathNode(
            position=start,
            g_cost=0, # g_cost 不用于决策，但 PathNode 需要
            h_cost=self._heuristic(start, goal),
            parent=None
        )
        start_node.f_cost = start_node.h_cost # 关键：f_cost 就是启发值

        heapq.heappush(open_set, start_node)
        # visited 用于防止在路径中形成环路或重复访问已在当前路径上的点
        # 对于纯粹的贪心，有时会陷入局部最优或循环，closed_set 更重要
        closed_set: Set[Tuple[int, int]] = set() 
        node_map: Dict[Tuple[int, int], PathNode] = {start: start_node}


        while open_set:
            current_node = heapq.heappop(open_set)
            current_pos = current_node.position

            if current_pos == goal:
                return self._reconstruct_path(current_node)

            if current_pos in closed_set:
                continue
            closed_set.add(current_pos)

            # 对邻居排序，优先选择h_cost最小的 (贪心选择)
            # _get_neighbors 本身不排序，我们在循环中处理
            # 或者可以先获取所有有效邻居，排序后再处理，但 heapq 已经帮我们做了优先级的选择

            for neighbor_pos in self._get_neighbors(current_pos):
                if (not self._is_valid_position(neighbor_pos) or 
                    neighbor_pos in obstacles or 
                    neighbor_pos in closed_set): # 确保邻居有效、不是障碍物且未在closed_set
                    continue
                
                # 贪心算法通常不关心路径成本g，只看启发h
                # 如果要构建路径，还是需要parent信息
                if neighbor_pos not in node_map or node_map[neighbor_pos].h_cost > self._heuristic(neighbor_pos, goal):
                    neighbor_node = PathNode(
                        position=neighbor_pos,
                        h_cost=self._heuristic(neighbor_pos, goal),
                        parent=current_node
                    )
                    neighbor_node.f_cost = neighbor_node.h_cost # f_cost = h_cost
                    node_map[neighbor_pos] = neighbor_node
                    heapq.heappush(open_set, neighbor_node)
        
        return [] # 未找到路径
    
    def _potential_field_pathfinding(self, start: Tuple[int, int], goal: Tuple[int, int], 
                                   obstacles: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """人工势场法实现"""
        # 初始化势场
        self.potential_field = [[0.0 for _ in range(self.GRID_SIZE)] for _ in range(self.GRID_SIZE)]
        
        # 吸引力参数
        attractive_k = self.PF_ATTRACTIVE_K # 使用可配置的吸引力系数
        # 排斥力参数和影响范围
        repulsive_k = self.GRID_SIZE * self.PF_REPULSIVE_K_MULTIPLIER # 使用可配置的排斥力系数乘数
        repulsive_range = self.GRID_SIZE / self.PF_REPULSIVE_RANGE_DIVISOR # 使用可配置的排斥力范围除数

        # 设置目标吸引力 (目标点势能为0或最小)
        for r in range(self.GRID_SIZE):
            for c in range(self.GRID_SIZE):
                dist_sq_to_goal = (r - goal[0])**2 + (c - goal[1])**2
                self.potential_field[r][c] = 0.5 * attractive_k * dist_sq_to_goal # 吸引势能 U_att = 1/2 * k_att * dist^2
        
        # 设置障碍物斥力
        for obs_r, obs_c in obstacles:
            for r in range(self.GRID_SIZE):
                for c in range(self.GRID_SIZE):
                    dist_to_obstacle = math.sqrt((r - obs_r)**2 + (c - obs_c)**2)
                    if dist_to_obstacle <= repulsive_range:
                        # U_rep = 1/2 * k_rep * (1/dist - 1/range)^2 if dist < range else 0
                        if dist_to_obstacle < 0.1: dist_to_obstacle = 0.1 # 避免除零
                        self.potential_field[r][c] += 0.5 * repulsive_k * ( (1.0/dist_to_obstacle) - (1.0/repulsive_range) )**2
        
        # 设置边界斥力 (视为特殊障碍物)
        for i in range(self.GRID_SIZE):
            # 上下边界
            for r_idx, c_idx in [(0,i), (self.GRID_SIZE-1, i)]:
                 for r_check in range(self.GRID_SIZE):
                    for c_check in range(self.GRID_SIZE):
                        dist_to_boundary_obs = math.sqrt((r_check - r_idx)**2 + (c_check - c_idx)**2)
                        if dist_to_boundary_obs <= repulsive_range:
                            if dist_to_boundary_obs < 0.1: dist_to_boundary_obs = 0.1
                            self.potential_field[r_check][c_check] += 0.5 * repulsive_k * 2 * ( (1.0/dist_to_boundary_obs) - (1.0/repulsive_range) )**2 # 边界斥力加倍
            # 左右边界
            for r_idx, c_idx in [(i,0), (i, self.GRID_SIZE-1)]:
                 for r_check in range(self.GRID_SIZE):
                    for c_check in range(self.GRID_SIZE):
                        dist_to_boundary_obs = math.sqrt((r_check - r_idx)**2 + (c_check - c_idx)**2)
                        if dist_to_boundary_obs <= repulsive_range:
                            if dist_to_boundary_obs < 0.1: dist_to_boundary_obs = 0.1
                            self.potential_field[r_check][c_check] += 0.5 * repulsive_k * 2 * ( (1.0/dist_to_boundary_obs) - (1.0/repulsive_range) )**2


        # 沿着势场梯度下降寻找路径
        path = [start]
        current_pos = start
        # visited_potential 用于防止在势场法路径中循环 (陷入局部最小值)
        visited_potential = {start} 
        max_steps = self.GRID_SIZE * self.GRID_SIZE * 2 # 增加最大步数

        for step in range(max_steps):
            if current_pos == goal:
                break
            
            best_neighbor = None
            min_potential_val = float('inf')
            
            # 为了避免抖动，可以优先选择朝向目标的邻居
            neighbors_options = self._get_neighbors(current_pos)
            random.shuffle(neighbors_options) # 随机化邻居顺序以帮助跳出局部最小

            for neighbor_pos in neighbors_options:
                if (self._is_valid_position(neighbor_pos) and
                    # neighbor_pos not in obstacles and # 障碍物已体现在势场中
                    neighbor_pos not in visited_potential): # 避免重复访问同一位置导致循环
                    
                    potential_val = self.potential_field[neighbor_pos[0]][neighbor_pos[1]]
                    if potential_val < min_potential_val:
                        min_potential_val = potential_val
                        best_neighbor = neighbor_pos
                    # 如果势能相同，优先选择离目标更近的
                    elif potential_val == min_potential_val and best_neighbor is not None:
                        if self._heuristic(neighbor_pos, goal) < self._heuristic(best_neighbor, goal):
                            best_neighbor = neighbor_pos
            
            if best_neighbor is None: # 陷入局部最小或无路可走
                 # 尝试允许访问已访问过的点，但有次数限制，或者引入随机扰动
                non_visited_options = [
                    n for n in self._get_neighbors(current_pos) 
                    if self._is_valid_position(n) #and n not in obstacles
                ]
                if not non_visited_options: break # 彻底无路可走

                best_fallback_neighbor = None
                min_fallback_potential = float('inf')
                for fb_neighbor in non_visited_options:
                    fb_potential = self.potential_field[fb_neighbor[0]][fb_neighbor[1]]
                    if fb_potential < min_fallback_potential:
                        min_fallback_potential = fb_potential
                        best_fallback_neighbor = fb_neighbor
                if best_fallback_neighbor:
                    best_neighbor = best_fallback_neighbor
                else:
                    break


            if best_neighbor is None: break

            path.append(best_neighbor)
            visited_potential.add(best_neighbor) # 将选择的邻居加入visited
            current_pos = best_neighbor
        
        return path if current_pos == goal else []
    
    def _genetic_pathfinding(self, start: Tuple[int, int], goal: Tuple[int, int], 
                           obstacles: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """遗传算法实现"""
        # 如果距离很近，直接使用A*
        if self._heuristic(start, goal) <= max(5, self.GRID_SIZE // 10) : 
            return self._a_star_pathfinding(start, goal, obstacles)
        
        # 初始化种群
        self._init_ga_population(start, goal) # 传入起点和终点以优化初始种群
        
        best_overall_individual = None
        # best_overall_fitness = float('-inf') # fitness 越大越好

        for generation in range(self.GA_GENERATIONS):
            current_best_fitness_in_gen = float('-inf')
            current_best_individual_in_gen = None

            # 评估适应度
            for individual in self.ga_population:
                individual.fitness = self._evaluate_fitness(individual, start, goal, obstacles)
                if individual.fitness > current_best_fitness_in_gen:
                    current_best_fitness_in_gen = individual.fitness
                    current_best_individual_in_gen = individual
            
            if best_overall_individual is None or (current_best_individual_in_gen and current_best_individual_in_gen.fitness > best_overall_individual.fitness):
                best_overall_individual = current_best_individual_in_gen


            # 如果找到了到达目标的路径 (且适应度较高)，可以考虑提前结束
            if best_overall_individual and self._check_path_reaches_goal(best_overall_individual, start, goal, obstacles) and best_overall_individual.fitness > 1000 : # 适应度阈值
                break
            
            # 选择、交叉、变异
            new_population = []
            
            # 保留最好的个体（精英策略）
            self.ga_population.sort() # Individual的 __lt__ 是按 fitness 降序
            elite_count = max(1, int(self.GA_POPULATION_SIZE * 0.1)) # 保留10%精英
            new_population.extend(self.ga_population[:elite_count])
            
            # 生成新个体
            while len(new_population) < self.GA_POPULATION_SIZE:
                parent1 = self._tournament_selection()
                parent2 = self._tournament_selection()
                
                if random.random() < self.GA_CROSSOVER_RATE:
                    child1, child2 = self._crossover(parent1, parent2)
                else:
                    # 深拷贝父代以避免修改原始父代
                    child1 = Individual(genes=list(parent1.genes), fitness=parent1.fitness)
                    child2 = Individual(genes=list(parent2.genes), fitness=parent2.fitness)

                self._mutate(child1)
                self._mutate(child2)
                
                new_population.append(child1)
                if len(new_population) < self.GA_POPULATION_SIZE:
                    new_population.append(child2)

            self.ga_population = new_population
            self.ga_generation = generation + 1 # generation 是从0开始的
        
        # 将最佳个体的基因序列转换为路径
        if best_overall_individual:
            # 重新评估一次最佳个体的路径，确保它是最新的
            final_path = self._genes_to_path(best_overall_individual, start, obstacles)
            if final_path and final_path[-1] == goal: # 确保路径到达目标
                 return final_path
            elif final_path: # 如果没到终点，但有路径，也返回，让上层判断
                 return final_path

        # 如果遗传算法没找到，尝试用A*做最后努力
        return self._a_star_pathfinding(start, goal, obstacles)

    def _init_ga_population(self, start: Tuple[int, int], goal: Tuple[int, int]) -> None:
        """初始化遗传算法种群，可加入启发式个体"""
        self.ga_population = []
        directions = ['UP', 'DOWN', 'LEFT', 'RIGHT']
        
        # 尝试生成一个或多个基于简单启发（如直线朝向目标）的个体
        # (这里简化，只生成随机个体)

        for _ in range(self.GA_POPULATION_SIZE):
            # 基因长度可以与起点到终点的曼哈顿距离相关，但有随机性
            manhattan_dist = self._heuristic(start, goal)
            min_len = int(manhattan_dist * 0.8)
            max_len = int(manhattan_dist * 2.5)
            if max_len > self.GRID_SIZE * 3: max_len = self.GRID_SIZE * 3 # 限制最大长度
            if min_len < 5 : min_len = 5
            if max_len < min_len : max_len = min_len + 5

            gene_length = random.randint(min_len, max_len)
            genes = [random.choice(directions) for _ in range(gene_length)]
            individual = Individual(genes=genes)
            self.ga_population.append(individual)

    def _evaluate_fitness(self, individual: Individual, start: Tuple[int, int], 
                         goal: Tuple[int, int], obstacles: Set[Tuple[int, int]]) -> float:
        """评估个体适应度"""
        current_simulated_pos = start # 模拟蛇头的位置
        path_positions_set = {start} # 用于快速检查自相交
        fitness = 0.0
        
        path_len = 0
        
        for gene_idx, gene in enumerate(individual.genes):
            path_len += 1
            
            # 记录移动前的位置，用于与新位置比较距离
            pos_before_move = current_simulated_pos 

            row, col = current_simulated_pos
            if gene == 'UP': new_simulated_pos = (row-1, col)
            elif gene == 'DOWN': new_simulated_pos = (row+1, col)
            elif gene == 'LEFT': new_simulated_pos = (row, col-1)
            else: new_simulated_pos = (row, col+1) # RIGHT
            
            # 碰撞检测
            if (not self._is_valid_position(new_simulated_pos) or 
                new_simulated_pos in obstacles or 
                new_simulated_pos in path_positions_set): # 撞墙、撞障碍、撞自身路径
                fitness -= 100  # 严厉惩罚无效移动
                fitness -= (len(individual.genes) - gene_idx) * 5 # 越早撞，惩罚越多
                break 
            
            # 奖励：如果新位置比旧位置更接近目标，则给予奖励
            if self._heuristic(new_simulated_pos, goal) < self._heuristic(pos_before_move, goal):
                 fitness += 5

            current_simulated_pos = new_simulated_pos
            path_positions_set.add(current_simulated_pos)
            
            # 到达目标奖励
            if current_simulated_pos == goal:
                fitness += 5000 # 大幅奖励到达目标
                fitness -= path_len * 2 # 路径越短奖励越高 (到达目标时)
                break 
            
        # 最终位置离目标的距离惩罚 (如果没到终点)
        if current_simulated_pos != goal:
            fitness -= self._heuristic(current_simulated_pos, goal) * 10

        # 探索区域大小奖励 (不鼓励原地打转)
        fitness += len(path_positions_set) * 1.0

        # 避免无效基因（如连续的相反方向 U-D, L-R）
        for i in range(len(individual.genes) - 1):
            g1, g2 = individual.genes[i], individual.genes[i+1]
            if (g1 == 'UP' and g2 == 'DOWN') or \
               (g1 == 'DOWN' and g2 == 'UP') or \
               (g1 == 'LEFT' and g2 == 'RIGHT') or \
               (g1 == 'RIGHT' and g2 == 'LEFT'):
                fitness -= 20 # 惩罚无效摆动
        
        return fitness

    def _check_path_reaches_goal(self, individual: Individual, start: Tuple[int, int], 
                               goal: Tuple[int, int], obstacles: Set[Tuple[int, int]]) -> bool:
        """检查个体代表的路径是否能到达目标"""
        current_pos = start
        path_taken = {start} # 用于检测路径自相交
        
        for gene in individual.genes:
            row, col = current_pos
            if gene == 'UP': new_pos = (row-1, col)
            elif gene == 'DOWN': new_pos = (row+1, col)
            elif gene == 'LEFT': new_pos = (row, col-1)
            else: new_pos = (row, col+1) # RIGHT
            
            if (not self._is_valid_position(new_pos) or 
                new_pos in obstacles or 
                new_pos in path_taken): # 撞墙、撞障碍、撞自身路径
                return False # 路径无效
            
            current_pos = new_pos
            path_taken.add(current_pos)
            
            if current_pos == goal:
                return True # 到达目标
        
        return False # 未到达目标

    def _tournament_selection(self) -> Individual:
        """锦标赛选择"""
        tournament_size = max(3, self.GA_POPULATION_SIZE // 10) # 锦标赛规模
        # 从种群中随机选择 tournament_size 个体
        tournament_contenders = random.sample(self.ga_population, k=tournament_size)
        # 返回适应度最高的个体
        # Individual 类已实现 __lt__，所以可以直接用 max()
        return max(tournament_contenders) 

    def _crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """单点交叉"""
        genes1, genes2 = parent1.genes, parent2.genes
        min_len = min(len(genes1), len(genes2))
        
        if min_len < 2: # 如果基因太短，无法交叉，直接返回父代拷贝
            return Individual(genes=list(genes1)), Individual(genes=list(genes2))
        
        # 随机选择交叉点 (不包括首尾)
        cx_point = random.randint(1, min_len - 1)
        
        child1_genes = genes1[:cx_point] + genes2[cx_point:]
        child2_genes = genes2[:cx_point] + genes1[cx_point:]
        
        return Individual(genes=child1_genes), Individual(genes=child2_genes)

    def _mutate(self, individual: Individual) -> None:
        """变异操作: 随机改变基因、插入或删除基因"""
        genes = individual.genes
        if not genes: return # 没有基因无法变异

        directions = ['UP', 'DOWN', 'LEFT', 'RIGHT']
        
        # 基因位点变异
        for i in range(len(genes)):
            if random.random() < self.GA_MUTATION_RATE: # 按概率改变当前基因
                genes[i] = random.choice(directions)
        
        # 基因插入变异 (小概率)
        if random.random() < self.GA_MUTATION_RATE / 2:
            insert_idx = random.randint(0, len(genes))
            genes.insert(insert_idx, random.choice(directions))
            # 限制基因最大长度
            if len(genes) > self.GRID_SIZE * 3:
                 genes.pop(random.randrange(len(genes)))


        # 基因删除变异 (小概率)
        if len(genes) > 1 and random.random() < self.GA_MUTATION_RATE / 2: # 至少保留一个基因
            delete_idx = random.randrange(len(genes))
            genes.pop(delete_idx)
        
        individual.genes = genes # 更新个体的基因


    def _genes_to_path(self, individual: Individual, start: Tuple[int, int], 
                      obstacles: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """将基因序列转换为实际的坐标路径，直到撞墙/障碍/自身或基因结束"""
        path = [start]
        current_pos = start
        
        for gene in individual.genes:
            row, col = current_pos
            if gene == 'UP': new_pos = (row-1, col)
            elif gene == 'DOWN': new_pos = (row+1, col)
            elif gene == 'LEFT': new_pos = (row, col-1)
            else: new_pos = (row, col+1) # RIGHT
            
            # 检查碰撞 (撞墙、撞固定障碍物、撞路径自身)
            if (not self._is_valid_position(new_pos) or 
                new_pos in obstacles or 
                new_pos in path): # 注意: new_pos in path 检查的是路径自相交
                break # 路径中断
            
            path.append(new_pos)
            current_pos = new_pos
            
            # 如果路径中间到达食物，对于GA来说，这条路径就是有效的
            if current_pos == self.food: 
                break
        
        return path
    
    # === 辅助方法 ===
    
    def _reconstruct_path(self, node: PathNode) -> List[Tuple[int, int]]:
        """从目标节点回溯到起始节点以重构路径"""
        path = []
        current = node
        while current: # 当 current 不为 None (即有父节点)
            path.append(current.position)
            current = current.parent
        return path[::-1] # 返回反转后的路径 (从起点到终点)
    
    def _heuristic(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """曼哈顿距离启发式函数"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
    
    def _get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """获取给定位置的四个相邻邻居位置 (不检查有效性或障碍)"""
        row, col = pos
        # 返回顺序: 上, 下, 左, 右 (可以打乱以增加寻路随机性)
        neighbors = [
            (row-1, col), (row+1, col), (row, col-1), (row, col+1) 
        ]
        # random.shuffle(neighbors) # 可选：打乱邻居顺序
        return neighbors
    
    def _is_valid_position(self, pos: Tuple[int, int]) -> bool:
        """检查位置是否在有效网格范围内"""
        row, col = pos
        return 0 <= row < self.GRID_SIZE and 0 <= col < self.GRID_SIZE
    
    def _check_collision(self, pos: Tuple[int, int]) -> bool:
        """检查给定位置是否会发生碰撞 (撞墙或撞蛇自身)"""
        row, col = pos
        
        # 检查墙壁碰撞
        if not self._is_valid_position(pos):
            return True
            
        # 检查自身碰撞 (不包括即将移开的尾巴，除非蛇在吃食物长大)
        # 在游戏主循环中，蛇先增加头，后判断是否移除尾
        # 所以这里的 self.snake 包含了新头，可能也包含了旧尾
        # 如果新头的位置在 (旧头 + 旧身体) 中，则为碰撞
        if pos in self.snake: # 简单检查是否与当前蛇的任何部分重合
            return True
            
        return False
    
    def _generate_food(self) -> None:
        """在网格的空余位置随机生成食物"""
        empty_cells = []
        for r in range(self.GRID_SIZE):
            for c in range(self.GRID_SIZE):
                if (r, c) not in self.snake:
                    empty_cells.append((r,c))
        
        if empty_cells:
            self.food = random.choice(empty_cells)
        else:
            # 如果没有空位（理论上蛇占满全屏），游戏结束或特殊处理
            self._end_game() # 可以认为是一种胜利或结束条件
            if self.error_logger:
                self.error_logger.log_info("No empty cells to generate food. Game over?", self.PANEL_TYPE_NAME)

    def _update_ui(self) -> None:
        """更新游戏界面，重绘蛇、食物、路径等 - 适配新UI样式"""
        if not self.score_label or not self.cells or not self.cells[0]: # 确保UI元素已初始化
            return

        # 更新分数
        self.score_label.setText(f"分数: {self.score}")
        
        # 1. 清空所有格子到默认背景色
        default_cell_style = """
            QLabel {
                background-color: #34495e; /* 网格单元格背景色 */
                border: none; /* 移除边框 */
                border-radius: 0px; /* 移除圆角 */
                margin: 0px; /* 移除默认外边距 */
                padding: 0px; /* 移除默认内边距 */
            }
        """
        for r_idx in range(self.GRID_SIZE):
            for c_idx in range(self.GRID_SIZE):
                if self.cells[r_idx][c_idx]:
                     self.cells[r_idx][c_idx].setStyleSheet(default_cell_style)
        
        # 2. 可视化AI路径 (如果启用且有路径)
        if (self.auto_mode and self.current_path and 
            self.current_algorithm != PathfindingAlgorithm.POTENTIAL_FIELD):
            path_style_base = "background-color: {}; border: none; border-radius: 0px; margin: 0px; padding: 0px;"
            for i, (r, c) in enumerate(self.current_path):
                if 0 <= r < self.GRID_SIZE and 0 <= c < self.GRID_SIZE and self.cells[r][c]:
                    if i >= self.path_index:  # 只显示未走过的路径
                        progress = (i - self.path_index) / max(1, len(self.current_path) - self.path_index)
                        # 从亮黄 (#feca57) 到深黄 (#e67e22)
                        red_val = int(0xfe * (1 - progress) + 0xe6 * progress)
                        green_val = int(0xca * (1 - progress) + 0x7e * progress)
                        blue_val = int(0x57 * (1 - progress) + 0x22 * progress)
                        path_color = f"rgb({red_val},{green_val},{blue_val})"
                        self.cells[r][c].setStyleSheet(path_style_base.format(path_color))

        # 3. 可视化势场 (如果启用)
        elif (self.auto_mode and 
            self.current_algorithm == PathfindingAlgorithm.POTENTIAL_FIELD and 
            self.potential_field and len(self.potential_field) == self.GRID_SIZE):
            
            flat_potential = [p for row_pot in self.potential_field for p in row_pot if isinstance(p, (int, float)) and abs(p) < 1e7]
            if not flat_potential: flat_potential = [0.0]

            max_pot = max(flat_potential) if flat_potential else 0.0
            min_pot = min(flat_potential) if flat_potential else 0.0
            pot_range = max_pot - min_pot
            if pot_range < 1e-6: pot_range = 1.0 # 避免除零

            for r in range(self.GRID_SIZE):
                for c in range(self.GRID_SIZE):
                    if not (self.cells[r][c] and (r,c) not in self.snake and (r,c) != self.food): continue
                    
                    current_pot_val = self.potential_field[r][c]
                    if not isinstance(current_pot_val, (int,float)) or abs(current_pot_val) > 1e7:
                        color = "rgb(30,0,60)" # 极端值用深紫色
                    else:
                        normalized = (current_pot_val - min_pot) / pot_range
                        # 势能低（吸引） -> 蓝色, 势能高（排斥） -> 红色/紫色
                        blue_intensity = int(255 * max(0, min(1, 1 - normalized))) 
                        red_intensity = int(255 * max(0, min(1, normalized)))     
                        color = f"rgb({red_intensity // 2}, {max(0, blue_intensity - red_intensity //2) //2}, {blue_intensity})"

                    self.cells[r][c].setStyleSheet(f"background-color: {color}; border: none; border-radius: 0px; margin: 0px; padding: 0px;")

        # 4. 绘制蛇
        snake_head_style = "background-color: #2ecc71; border: none; border-radius: 0px; margin: 0px; padding: 0px;" # 鲜绿色蛇头
        snake_body_style = "background-color: #27ae60; border: none; border-radius: 0px; margin: 0px; padding: 0px;" # 深绿色蛇身
        for i, (r, c) in enumerate(self.snake):
            if 0 <= r < self.GRID_SIZE and 0 <= c < self.GRID_SIZE and self.cells[r][c]:
                style = snake_head_style if i == 0 else snake_body_style
                self.cells[r][c].setStyleSheet(style)
        
        # 5. 绘制食物
        if 0 <= self.food[0] < self.GRID_SIZE and 0 <= self.food[1] < self.GRID_SIZE and self.cells[self.food[0]][self.food[1]]:
            food_style = f"background-color: #e74c3c; border: none; border-radius: {self.CELL_SIZE // 2}px; margin: 0px; padding: 0px;" # 红色食物，保持圆形
            self.cells[self.food[0]][self.food[1]].setStyleSheet(food_style)
        
        # 更新窗口标题
        self._update_title()
    
    def _update_title(self) -> None:
        """更新停靠窗口标题以显示分数和模式"""
        mode_text = f" [{self.current_algorithm.value}]" if self.auto_mode else ""
        new_title = f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}]{mode_text} - 分数: {self.score}"
        self.dock_title_changed.emit(new_title) # 假设有这个信号
    
    def _end_game(self) -> None:
        """结束游戏的处理逻辑"""
        self.game_over = True
        self.game_started = False # 游戏未在进行
        self.timer.stop()
        # self.current_path = [] # 保留路径以供查看
        # self.path_index = 0
        
        if self.score_label:
            self.score_label.setText(f"游戏结束! 分数: {self.score}")
        
        if self.start_button:
            self.start_button.setText("🔄 重新开始") 
            
        if self.auto_mode and self.pathfinding_info_label:
            self.pathfinding_info_label.setText(f"{self.current_algorithm.value} - 游戏结束. 分数: {self.score}")
        elif self.pathfinding_info_label :
             self.pathfinding_info_label.setText(f"游戏结束. 分数: {self.score}")


    def keyPressEvent(self, event: QKeyEvent) -> None:
        """处理键盘事件以控制蛇或开始游戏"""
        key = event.key()

        if not self.game_started or self.game_over: # 游戏未开始或已结束
            if key == Qt.Key_Space or key == Qt.Key_Return: # 按空格或回车开始/重新开始
                self._start_game()
            super().keyPressEvent(event)
            return

        if self.auto_mode: # AI模式下不接受手动控制
            super().keyPressEvent(event)
            return

        # 手动模式下的方向键控制
        if key == Qt.Key_Up and self.direction != 'DOWN':
            self.next_direction = 'UP'
        elif key == Qt.Key_Down and self.direction != 'UP':
            self.next_direction = 'DOWN'
        elif key == Qt.Key_Left and self.direction != 'RIGHT':
            self.next_direction = 'LEFT'
        elif key == Qt.Key_Right and self.direction != 'LEFT':
            self.next_direction = 'RIGHT'
        # 可选：手动模式下的暂停功能
        # elif key == Qt.Key_P or key == Qt.Key_Space: 
        #     if self.timer.isActive():
        #         self.timer.stop()
        #         if self.pathfinding_info_label : self.pathfinding_info_label.setText("⏸️ 游戏暂停 (手动)")
        #     else:
        #         self.timer.start(self.INITIAL_SPEED)
        #         if self.pathfinding_info_label : self.pathfinding_info_label.setText("")
        else:
            super().keyPressEvent(event)
    
    # === PanelInterface 必须实现的方法 ===
    
    def get_config(self) -> Dict[str, Any]:
        """返回当前游戏状态配置，用于保存"""
        return {
            "version": "2.3", # 更新配置版本
            "snake": self.snake,
            "food": self.food,
            "direction": self.direction, # 保存最后的方向
            "score": self.score,
            "game_over": self.game_over,
            "game_started": self.game_started,
            "auto_mode": self.auto_mode,
            "current_algorithm": self.current_algorithm.value,
            "current_path": self.current_path, # 保存AI路径
            "path_index": self.path_index,
            # 遗传算法参数
            "ga_population_size": self.GA_POPULATION_SIZE,
            "ga_generations": self.GA_GENERATIONS,
            "ga_mutation_rate": self.GA_MUTATION_RATE,
            "ga_crossover_rate": self.GA_CROSSOVER_RATE,
            # 人工势场法参数
            "pf_attractive_k": self.PF_ATTRACTIVE_K,
            "pf_repulsive_k_multiplier": self.PF_REPULSIVE_K_MULTIPLIER,
            "pf_repulsive_range_divisor": self.PF_REPULSIVE_RANGE_DIVISOR,
            "panel_type": self.PANEL_TYPE_NAME
        }
    
    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置恢复游戏状态"""
        try:
            loaded_version = config.get("version")
            
            self.direction = config.get("direction", "RIGHT")
            self.next_direction = self.direction # 同步next_direction
            self.score = config.get("score", 0)
            self.game_over = config.get("game_over", False)
            self.game_started = config.get("game_started", False) # 恢复游戏是否已开始的状态
            self.auto_mode = config.get("auto_mode", False)
            
            loaded_snake = config.get("snake", [])
            center = self.GRID_SIZE // 2

            # 修正来自旧配置的、不连续的初始蛇身体的特定情况
            is_potentially_gapped_initial_snake = (
                len(loaded_snake) == 3 and
                loaded_snake[0] == (center, center) and
                loaded_snake[1] == (center, center - 2) and # 特征：第二个分段的列是 center - 2
                loaded_snake[2] == (center, center - 4) and # 特征：第三个分段的列是 center - 4
                self.score == 0 # 仅当分数为0时（初始状态）
            )

            if is_potentially_gapped_initial_snake and loaded_version != "2.1":
                # 如果检测到旧的、间隔的初始蛇状态，则强制使用正确的连续初始蛇
                self.snake = [(center, center), (center, center-1), (center, center-2)]
                if self.error_logger: # 假设有 self.error_logger
                    self.error_logger.log_warning(
                        "Old gapped initial snake configuration detected and corrected.",
                        self.PANEL_TYPE_NAME
                    )
            else:
                self.snake = loaded_snake
            
            # 确保食物位置在有效范围内
            loaded_food = config.get("food", (self.GRID_SIZE // 2, self.GRID_SIZE // 2 + 5))
            if self._is_valid_position(loaded_food):
                self.food = loaded_food
            else: # 如果无效，重新生成
                self._generate_food()


            self.current_path = config.get("current_path", [])
            self.path_index = config.get("path_index", 0)
            
            algorithm_name = config.get("current_algorithm", PathfindingAlgorithm.A_STAR.value)
            for algo in PathfindingAlgorithm:
                if algo.value == algorithm_name:
                    self.current_algorithm = algo
                    break
            
            # 从配置中加载遗传算法参数
            self.GA_POPULATION_SIZE = config.get("ga_population_size", self.GA_POPULATION_SIZE)
            self.GA_GENERATIONS = config.get("ga_generations", self.GA_GENERATIONS)
            self.GA_MUTATION_RATE = config.get("ga_mutation_rate", self.GA_MUTATION_RATE)
            self.GA_CROSSOVER_RATE = config.get("ga_crossover_rate", self.GA_CROSSOVER_RATE)

            # 从配置中加载人工势场法参数
            self.PF_ATTRACTIVE_K = config.get("pf_attractive_k", self.PF_ATTRACTIVE_K)
            self.PF_REPULSIVE_K_MULTIPLIER = config.get("pf_repulsive_k_multiplier", self.PF_REPULSIVE_K_MULTIPLIER)
            self.PF_REPULSIVE_RANGE_DIVISOR = config.get("pf_repulsive_range_divisor", self.PF_REPULSIVE_RANGE_DIVISOR)


            # 更新UI组件的值
            if self.ga_pop_size_spinbox: self.ga_pop_size_spinbox.setValue(self.GA_POPULATION_SIZE)
            if self.ga_generations_spinbox: self.ga_generations_spinbox.setValue(self.GA_GENERATIONS)
            if self.ga_mutation_rate_spinbox: self.ga_mutation_rate_spinbox.setValue(self.GA_MUTATION_RATE)
            if self.ga_crossover_rate_spinbox: self.ga_crossover_rate_spinbox.setValue(self.GA_CROSSOVER_RATE)

            if self.pf_attractive_k_spinbox: self.pf_attractive_k_spinbox.setValue(self.PF_ATTRACTIVE_K)
            if self.pf_repulsive_k_multiplier_spinbox: self.pf_repulsive_k_multiplier_spinbox.setValue(self.PF_REPULSIVE_K_MULTIPLIER)
            if self.pf_repulsive_range_divisor_spinbox: self.pf_repulsive_range_divisor_spinbox.setValue(self.PF_REPULSIVE_RANGE_DIVISOR)


            if self.auto_checkbox: self.auto_checkbox.setChecked(self.auto_mode)
            if self.algorithm_combo: self.algorithm_combo.setCurrentText(self.current_algorithm.value)
            
            # 确保GA和PF参数控制的可见性正确
            is_genetic_algo_and_auto = self.auto_mode and (self.current_algorithm == PathfindingAlgorithm.GENETIC)
            is_potential_field_algo_and_auto = self.auto_mode and (self.current_algorithm == PathfindingAlgorithm.POTENTIAL_FIELD)

            if self.ga_params_group:
                self.ga_params_group.setVisible(is_genetic_algo_and_auto)
            if self.pf_params_group:
                self.pf_params_group.setVisible(is_potential_field_algo_and_auto)


            if self.start_button:
                if self.game_started and not self.game_over:
                    self.start_button.setText("🔄 重新开始")
                elif self.game_over : # 如果游戏结束，按钮也应是“重新开始”
                    self.start_button.setText("🔄 重新开始")
                else: # 游戏未开始
                    self.start_button.setText("🎮 开始游戏")

            if self.game_started and not self.game_over:
                speed = self.AUTO_SPEED if self.auto_mode else self.INITIAL_SPEED
                if not self.timer.isActive(): self.timer.start(speed)
            elif self.game_over: # 如果加载的状态是游戏结束，确保计时器停止
                self.timer.stop()
            
            self._update_ui() # 最后更新界面显示
        except Exception as e:
            if hasattr(self, 'error_logger') and self.error_logger:
                self.error_logger.log_error(f"应用贪吃蛇配置失败: {str(e)}", self.PANEL_TYPE_NAME)
            # 发生错误时，尝试重置到安全状态
            self._new_game()


    def get_initial_dock_title(self) -> str:
        """返回初始停靠窗口标题"""
        return f"{self.PANEL_DISPLAY_NAME} ({self.panel_id})"
    
    # === PanelInterface 可选实现的方法 ===
    
    def on_panel_added(self) -> None:
        """面板被添加后的回调"""
        super().on_panel_added()
        if hasattr(self, 'error_logger') and self.error_logger:
            self.error_logger.log_info(
                f"贪吃蛇游戏面板 (ID: {self.panel_id}) 已添加",
                self.PANEL_TYPE_NAME
            )
    
    def on_panel_removed(self) -> None:
        """面板被移除前的清理"""
        super().on_panel_removed()
        self.timer.stop() # 确保计时器停止
        if hasattr(self, 'error_logger') and self.error_logger:
            self.error_logger.log_info(
                f"贪吃蛇游戏面板 (ID: {self.panel_id}) 正在清理",
                self.PANEL_TYPE_NAME
            )
    
    def update_theme(self) -> None:
        """主题变化时的更新 (如果需要)"""
        super().update_theme()
        # 如果UI元素样式依赖于主题，可能需要在这里重新应用
        # 例如，可以重新调用 _init_ui() 的部分样式设置逻辑
        # 或者，如果样式表是动态生成的，则重新生成并应用
        # 当前的实现中，大部分样式是固定的，但 _update_ui 会刷新格子颜色
        self._update_ui()
