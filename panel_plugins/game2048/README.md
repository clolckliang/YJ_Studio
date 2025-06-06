# 2048游戏插件

## 插件简介
这是一个集成在YJ Studio中的2048游戏面板插件，可以在主程序中作为独立面板使用。

## 游戏规则
2048是一款数字合并游戏，目标是通过移动数字块，将相同数字合并，最终得到2048数字块。

## 操作方法
- **方向键↑**：向上移动所有数字块
- **方向键↓**：向下移动所有数字块
- **方向键←**：向左移动所有数字块
- **方向键→**：向右移动所有数字块
- **重新开始按钮**：重置游戏

## 游戏特点
1. 每次移动后会在空白处随机生成一个2或4的数字块
2. 相同数字的块相撞时会合并成它们的和
3. 分数计算：每次合并的数字会加到总分中
4. 游戏结束条件：棋盘填满且无法继续合并

## 功能特性
- 支持游戏状态保存/恢复
- 自适应主题颜色
- 高分显示
- 游戏结束检测

## 安装使用
1. 将`game2048`文件夹放入`panel_plugins`目录
2. 在主程序中选择"添加面板" → "2048游戏"
3. 使用方向键开始游戏

## 界面说明
- 顶部显示当前分数
- 4x4网格显示游戏棋盘
- "重新开始"按钮可重置游戏

## 开发信息
- 开发者: YJ Studio
- 版本: 1.0.0
- 依赖: PySide6
