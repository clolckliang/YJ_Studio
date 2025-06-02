# panel_plugins/snake_game/snake_panel.py
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QWidget, QGridLayout)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from typing import Dict, Any, Optional, List, Tuple
import random

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


class SnakeGamePanel(PanelInterface):
    """
    贪吃蛇游戏面板实现
    
    实现了一个完整的贪吃蛇游戏，包括：
    - 蛇的移动和控制
    - 食物生成
    - 碰撞检测
    - 分数计算
    """
    
    # PanelInterface 必须定义的静态属性
    PANEL_TYPE_NAME: str = "snake_game"
    PANEL_DISPLAY_NAME: str = "贪吃蛇游戏"
    
    # 游戏常量
    GRID_SIZE = 20
    CELL_SIZE = 30
    INITIAL_SPEED = 200  # 毫秒
    
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
        
        # 初始化游戏
        self._init_ui()
        self._new_game()
        
        # 应用初始配置
        if initial_config:
            self.apply_config(initial_config)
    
    def _init_ui(self) -> None:
        """构建贪吃蛇游戏界面"""
        main_layout = QVBoxLayout(self)
        
        # 分数显示区域
        score_layout = QHBoxLayout()
        self.score_label = QLabel("分数: 0")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        score_layout.addWidget(self.score_label)
        
        # 开始按钮
        self.start_button = QPushButton("开始游戏")
        self.start_button.clicked.connect(self._start_game)
        score_layout.addWidget(self.start_button)
        
        main_layout.addLayout(score_layout)
        
        # 游戏网格
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(1)
        
        # 创建游戏网格
        for row in range(self.GRID_SIZE):
            for col in range(self.GRID_SIZE):
                cell = QLabel("")
                cell.setMinimumSize(self.CELL_SIZE, self.CELL_SIZE)
                cell.setStyleSheet("""
                    QLabel {
                        background-color: #f0f0f0;
                        border: 1px solid #ddd;
                    }
                """)
                self.cells[row][col] = cell
                self.grid_layout.addWidget(cell, row, col)
        
        main_layout.addLayout(self.grid_layout)
        self.setLayout(main_layout)
        
        # 设置面板可获得焦点
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()
    
    def _new_game(self) -> None:
        """初始化新游戏"""
        # 初始化蛇
        center = self.GRID_SIZE // 2
        self.snake = [(center, center), (center, center-1), (center, center-2)]
        self.direction = 'RIGHT'
        self.next_direction = 'RIGHT'
        
        # 生成食物
        self._generate_food()
        
        # 重置分数
        self.score = 0
        self.game_over = False
        self.game_started = False
        
        # 更新UI
        self._update_ui()
    
    def _start_game(self) -> None:
        """开始游戏"""
        if self.game_over:
            self._new_game()
            self.game_started = True
        elif not self.game_started:
            self.game_started = True
            
        self.start_button.setText("重新开始")
        self.timer.start(self.INITIAL_SPEED)
    
    def _game_loop(self) -> None:
        """游戏主循环"""
        if not self.game_started or self.game_over:
            return
            
        # 更新方向
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
        else:
            self.snake.pop()
        
        # 更新UI
        self._update_ui()
    
    def _check_collision(self, pos: Tuple[int, int]) -> bool:
        """检查碰撞"""
        row, col = pos
        
        # 检查墙壁碰撞
        if (row < 0 or row >= self.GRID_SIZE or 
            col < 0 or col >= self.GRID_SIZE):
            return True
            
        # 检查自身碰撞
        if pos in self.snake:
            return True
            
        return False
    
    def _generate_food(self) -> None:
        """生成食物"""
        empty_cells = [
            (row, col) 
            for row in range(self.GRID_SIZE) 
            for col in range(self.GRID_SIZE) 
            if (row, col) not in self.snake
        ]
        
        if empty_cells:
            self.food = random.choice(empty_cells)
    
    def _update_ui(self) -> None:
        """更新游戏界面"""
        # 更新分数
        if self.score_label:
            self.score_label.setText(f"分数: {self.score}")
        
        # 清空所有格子
        for row in range(self.GRID_SIZE):
            for col in range(self.GRID_SIZE):
                self.cells[row][col].setStyleSheet("""
                    QLabel {
                        background-color: #f0f0f0;
                        border: 1px solid #ddd;
                    }
                """)
        
        # 绘制蛇
        for i, (row, col) in enumerate(self.snake):
            color = "#2ecc71" if i == 0 else "#27ae60"  # 蛇头绿色，蛇身深绿色
            self.cells[row][col].setStyleSheet(f"""
                QLabel {{
                    background-color: {color};
                    border: 1px solid #16a085;
                }}
            """)
        
        # 绘制食物
        food_row, food_col = self.food
        self.cells[food_row][food_col].setStyleSheet("""
            QLabel {
                background-color: #e74c3c;
                border: 1px solid #c0392b;
                border-radius: 15px;
            }
        """)
        
        # 更新标题
        self._update_title()
    
    def _update_title(self) -> None:
        """更新停靠窗口标题"""
        new_title = f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}] - 分数: {self.score}"
        self.dock_title_changed.emit(new_title)
    
    def _end_game(self) -> None:
        """结束游戏"""
        self.game_over = True
        self.game_started = False
        self.timer.stop()
        
        if self.score_label:
            self.score_label.setText(f"游戏结束! 分数: {self.score}")
        
        if self.start_button:
            self.start_button.setText("重新开始")
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """处理键盘事件"""
        if not self.hasFocus() or not self.game_started or self.game_over:
            return
            
        # 确保事件传递给父类处理
        super().keyPressEvent(event)
        
        # 处理方向键
        if event.key() == Qt.Key_Up and self.direction != 'DOWN':
            self.next_direction = 'UP'
        elif event.key() == Qt.Key_Down and self.direction != 'UP':
            self.next_direction = 'DOWN'
        elif event.key() == Qt.Key_Left and self.direction != 'RIGHT':
            self.next_direction = 'LEFT'
        elif event.key() == Qt.Key_Right and self.direction != 'LEFT':
            self.next_direction = 'RIGHT'
    
    # === PanelInterface 必须实现的方法 ===
    
    def get_config(self) -> Dict[str, Any]:
        """返回当前游戏状态配置"""
        return {
            "version": "1.0",
            "snake": self.snake,
            "food": self.food,
            "direction": self.direction,
            "score": self.score,
            "game_over": self.game_over,
            "game_started": self.game_started,
            "panel_type": self.PANEL_TYPE_NAME
        }
    
    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置恢复游戏状态"""
        try:
            self.snake = config.get("snake", [])
            self.food = config.get("food", (0, 0))
            self.direction = config.get("direction", "RIGHT")
            self.next_direction = self.direction
            self.score = config.get("score", 0)
            self.game_over = config.get("game_over", False)
            self.game_started = config.get("game_started", False)
            
            if self.game_started and not self.game_over:
                self.timer.start(self.INITIAL_SPEED)
            
            self._update_ui()
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"应用配置失败: {str(e)}", self.PANEL_TYPE_NAME)
    
    def get_initial_dock_title(self) -> str:
        """返回初始停靠窗口标题"""
        return f"{self.PANEL_DISPLAY_NAME} ({self.panel_id})"
    
    # === PanelInterface 可选实现的方法 ===
    
    def on_panel_added(self) -> None:
        """面板被添加后的回调"""
        super().on_panel_added()
        if self.error_logger:
            self.error_logger.log_info(
                f"贪吃蛇游戏面板 (ID: {self.panel_id}) 已添加",
                self.PANEL_TYPE_NAME
            )
    
    def on_panel_removed(self) -> None:
        """面板被移除前的清理"""
        super().on_panel_removed()
        self.timer.stop()
        if self.error_logger:
            self.error_logger.log_info(
                f"贪吃蛇游戏面板 (ID: {self.panel_id}) 正在清理",
                self.PANEL_TYPE_NAME
            )
    
    def update_theme(self) -> None:
        """主题变化时的更新"""
        super().update_theme()
        self._update_ui()
