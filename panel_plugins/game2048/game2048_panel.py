# panel_plugins/game2048/game2048_panel.py
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QWidget, QGridLayout)
from PySide6.QtCore import Qt, Signal
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


class Game2048Panel(PanelInterface):
    """
    2048游戏面板实现
    
    实现了一个完整的2048游戏，包括：
    - 游戏逻辑
    - 键盘控制
    - 分数计算
    - 配置保存/加载
    """
    
    # PanelInterface 必须定义的静态属性
    PANEL_TYPE_NAME: str = "game2048"
    PANEL_DISPLAY_NAME: str = "2048游戏"
    
    # 颜色映射 - 不同数字对应不同背景色
    COLOR_MAP = {
        0: "#cdc1b4",
        2: "#eee4da",
        4: "#ede0c8",
        8: "#f2b179",
        16: "#f59563",
        32: "#f67c5f",
        64: "#f65e3b",
        128: "#edcf72",
        256: "#edcc61",
        512: "#edc850",
        1024: "#edc53f",
        2048: "#edc22e"
    }
    
    def __init__(self,
                 panel_id: int,
                 main_window_ref: 'SerialDebugger',
                 initial_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        """
        初始化2048游戏面板
        
        Args:
            panel_id: 面板唯一标识符
            main_window_ref: 主窗口引用
            initial_config: 初始配置数据
            parent: 父级组件
        """
        super().__init__(panel_id, main_window_ref, initial_config, parent)
        
        # 游戏状态
        self.board: List[List[int]] = [[0] * 4 for _ in range(4)]
        self.score: int = 0
        self.game_over: bool = False
        
        # UI组件
        self.score_label: Optional[QLabel] = None
        self.grid_layout: Optional[QGridLayout] = None
        self.cells: List[List[QLabel]] = [[None] * 4 for _ in range(4)]
        self.restart_button: Optional[QPushButton] = None
        
        # 初始化游戏
        self._init_ui()
        self._new_game()
        
        # 应用初始配置
        if initial_config:
            self.apply_config(initial_config)
    
    def _init_ui(self) -> None:
        """构建2048游戏界面"""
        main_layout = QVBoxLayout(self)
        
        # 分数显示区域
        score_layout = QHBoxLayout()
        self.score_label = QLabel("分数: 0")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        score_layout.addWidget(self.score_label)
        
        # 重新开始按钮
        self.restart_button = QPushButton("重新开始")
        self.restart_button.clicked.connect(self._new_game)
        score_layout.addWidget(self.restart_button)
        
        main_layout.addLayout(score_layout)
        
        # 游戏网格
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)
        
        # 创建4x4网格
        for row in range(4):
            for col in range(4):
                cell = QLabel("")
                cell.setAlignment(Qt.AlignCenter)
                cell.setStyleSheet("""
                    QLabel {
                        font-size: 24px;
                        font-weight: bold;
                        border-radius: 5px;
                        min-width: 60px;
                        min-height: 60px;
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
        """开始新游戏"""
        self.board = [[0] * 4 for _ in range(4)]
        self.score = 0
        self.game_over = False
        
        # 添加两个初始数字
        self._add_random_tile()
        self._add_random_tile()
        
        self._update_ui()
    
    def _add_random_tile(self) -> None:
        """在随机空位置添加2或4"""
        empty_cells = [(i, j) for i in range(4) for j in range(4) if self.board[i][j] == 0]
        if empty_cells:
            row, col = random.choice(empty_cells)
            self.board[row][col] = 2 if random.random() < 0.9 else 4
    
    def _update_ui(self) -> None:
        """更新UI显示"""
        # 更新分数
        if self.score_label:
            self.score_label.setText(f"分数: {self.score}")
        
        # 更新游戏板
        for row in range(4):
            for col in range(4):
                value = self.board[row][col]
                cell = self.cells[row][col]
                
                if value == 0:
                    cell.setText("")
                    cell.setStyleSheet(f"background-color: {self.COLOR_MAP[0]};")
                else:
                    cell.setText(str(value))
                    cell.setStyleSheet(f"""
                        background-color: {self.COLOR_MAP.get(value, "#3c3a32")};
                        color: {"#f9f6f2" if value > 4 else "#776e65"};
                    """)
        
        # 更新标题
        self._update_title()
    
    def _update_title(self) -> None:
        """更新停靠窗口标题"""
        new_title = f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}] - 分数: {self.score}"
        self.dock_title_changed.emit(new_title)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """处理键盘事件"""
        if not self.hasFocus() or self.game_over:
            return
            
        # 确保事件传递给父类处理
        super().keyPressEvent(event)
            
        moved = False
        
        if event.key() == Qt.Key_Up:
            moved = self._move_up()
        elif event.key() == Qt.Key_Down:
            moved = self._move_down()
        elif event.key() == Qt.Key_Left:
            moved = self._move_left()
        elif event.key() == Qt.Key_Right:
            moved = self._move_right()
        
        if moved:
            self._add_random_tile()
            self._update_ui()
            self._check_game_over()
    
    def _move_up(self) -> bool:
        """向上移动并合并数字"""
        moved = False
        for col in range(4):
            # 合并相同数字
            for row in range(1, 4):
                if self.board[row][col] == 0:
                    continue
                    
                current_row = row
                while current_row > 0:
                    if self.board[current_row-1][col] == 0:
                        self.board[current_row-1][col] = self.board[current_row][col]
                        self.board[current_row][col] = 0
                        current_row -= 1
                        moved = True
                    elif self.board[current_row-1][col] == self.board[current_row][col]:
                        self.board[current_row-1][col] *= 2
                        self.score += self.board[current_row-1][col]
                        self.board[current_row][col] = 0
                        moved = True
                        break
                    else:
                        break
        return moved
    
    def _move_down(self) -> bool:
        """向下移动并合并数字"""
        moved = False
        for col in range(4):
            for row in range(2, -1, -1):
                if self.board[row][col] == 0:
                    continue
                    
                current_row = row
                while current_row < 3:
                    if self.board[current_row+1][col] == 0:
                        self.board[current_row+1][col] = self.board[current_row][col]
                        self.board[current_row][col] = 0
                        current_row += 1
                        moved = True
                    elif self.board[current_row+1][col] == self.board[current_row][col]:
                        self.board[current_row+1][col] *= 2
                        self.score += self.board[current_row+1][col]
                        self.board[current_row][col] = 0
                        moved = True
                        break
                    else:
                        break
        return moved
    
    def _move_left(self) -> bool:
        """向左移动并合并数字"""
        moved = False
        for row in range(4):
            for col in range(1, 4):
                if self.board[row][col] == 0:
                    continue
                    
                current_col = col
                while current_col > 0:
                    if self.board[row][current_col-1] == 0:
                        self.board[row][current_col-1] = self.board[row][current_col]
                        self.board[row][current_col] = 0
                        current_col -= 1
                        moved = True
                    elif self.board[row][current_col-1] == self.board[row][current_col]:
                        self.board[row][current_col-1] *= 2
                        self.score += self.board[row][current_col-1]
                        self.board[row][current_col] = 0
                        moved = True
                        break
                    else:
                        break
        return moved
    
    def _move_right(self) -> bool:
        """向右移动并合并数字"""
        moved = False
        for row in range(4):
            for col in range(2, -1, -1):
                if self.board[row][col] == 0:
                    continue
                    
                current_col = col
                while current_col < 3:
                    if self.board[row][current_col+1] == 0:
                        self.board[row][current_col+1] = self.board[row][current_col]
                        self.board[row][current_col] = 0
                        current_col += 1
                        moved = True
                    elif self.board[row][current_col+1] == self.board[row][current_col]:
                        self.board[row][current_col+1] *= 2
                        self.score += self.board[row][current_col+1]
                        self.board[row][current_col] = 0
                        moved = True
                        break
                    else:
                        break
        return moved
    
    def _check_game_over(self) -> None:
        """检查游戏是否结束"""
        # 检查是否有空格
        if any(0 in row for row in self.board):
            return
            
        # 检查是否可以合并
        for row in range(4):
            for col in range(3):
                if self.board[row][col] == self.board[row][col+1]:
                    return
                    
        for col in range(4):
            for row in range(3):
                if self.board[row][col] == self.board[row+1][col]:
                    return
        
        # 游戏结束
        self.game_over = True
        if self.score_label:
            self.score_label.setText(f"游戏结束! 分数: {self.score}")
    
    # === PanelInterface 必须实现的方法 ===
    
    def get_config(self) -> Dict[str, Any]:
        """返回当前游戏状态配置"""
        return {
            "version": "1.0",
            "board": self.board,
            "score": self.score,
            "game_over": self.game_over,
            "panel_type": self.PANEL_TYPE_NAME
        }
    
    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置恢复游戏状态"""
        try:
            self.board = config.get("board", [[0]*4 for _ in range(4)])
            self.score = config.get("score", 0)
            self.game_over = config.get("game_over", False)
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
                f"2048游戏面板 (ID: {self.panel_id}) 已添加",
                self.PANEL_TYPE_NAME
            )
    
    def on_panel_removed(self) -> None:
        """面板被移除前的清理"""
        super().on_panel_removed()
        if self.error_logger:
            self.error_logger.log_info(
                f"2048游戏面板 (ID: {self.panel_id}) 正在清理",
                self.PANEL_TYPE_NAME
            )
    
    def update_theme(self) -> None:
        """主题变化时的更新"""
        super().update_theme()
        self._update_ui()
