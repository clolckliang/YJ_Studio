#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强化学习可视化测试脚本
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
    from PySide6.QtCore import QTimer
    import numpy as np
    
    # 导入可视化组件
    from panel_plugins.snake_game.snake_panel import RLVisualizationWidget, MATPLOTLIB_AVAILABLE, TORCH_AVAILABLE
    
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("强化学习可视化测试")
            self.setGeometry(100, 100, 1200, 800)
            
            # 创建中央部件
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)
            
            # 添加测试按钮
            self.test_button = QPushButton("开始模拟训练数据")
            self.test_button.clicked.connect(self.start_simulation)
            layout.addWidget(self.test_button)
            
            # 添加可视化组件
            if MATPLOTLIB_AVAILABLE and TORCH_AVAILABLE:
                self.viz_widget = RLVisualizationWidget()
                layout.addWidget(self.viz_widget)
            else:
                print("Matplotlib or PyTorch not available.")
                return

            # 模拟训练数据
            self.training_history = {
                'losses': [],
                'rewards': [],
                'scores': [],
                'epsilons': [],
                'episodes': []
            }
            self.episode_count = 0
            self.epsilon = 1.0
            
            # 定时器用于模拟数据更新
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_data)

        def start_simulation(self):
            self.timer.start(200) # 每200ms更新一次数据

        def update_data(self):
            # 模拟损失值
            self.training_history['losses'].extend(np.random.rand(5) * 0.1 + 0.05)
            
            # 模拟每局数据
            self.episode_count += 1
            self.training_history['episodes'].append(self.episode_count)
            self.training_history['rewards'].append(np.random.randint(-10, 20))
            self.training_history['scores'].append(np.random.randint(0, 50))
            self.epsilon *= 0.995
            self.training_history['epsilons'].append(self.epsilon)
            
            # 更新图表
            self.viz_widget.update_plots(self.training_history)
            
            if self.episode_count > 100:
                self.timer.stop()

    if __name__ == "__main__":
        app = QApplication(sys.argv)
        window = TestWindow()
        window.show()
        sys.exit(app.exec())

except ImportError as e:
    print(f"导入失败: {e}")
    print("请确保已安装 PySide6, numpy, matplotlib, torch")
