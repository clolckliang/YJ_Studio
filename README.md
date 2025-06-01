# YJ Studio 串口调试工具

## 项目概述

YJ Studio 是一个功能强大的串口调试工具，采用模块化架构设计，支持插件扩展。主要功能包括：

- 串口通信管理
- 数据收发和记录
- 协议分析和解析
- 可扩展的插件系统
- 自定义UI面板

## 功能特性

### 核心功能
- **串口通信**：支持多种波特率、数据位、停止位和校验位配置
- **协议支持**：内置YJ协议栈，支持原始求和/累加校验和CRC16校验
- **数据记录**：实时记录串口数据，支持多种格式导出
- **插件系统**：支持开发自定义功能面板插件

### UI特性
- **主题支持**：支持深色/浅色主题切换
- **多面板布局**：可自由拖拽和停靠的面板系统
- **数据可视化**：内置绘图组件，实时显示数据曲线
- **脚本支持**：内置脚本编辑和执行环境

### 插件功能
- **PID代码生成器**：自动生成C语言PID控制器代码
- **自定义面板**：支持开发各种功能扩展面板

## 安装指南

### 依赖项
- Python 3.8+
- PySide6
- pyserial
- numpy
- matplotlib

### 安装步骤
1. 克隆仓库：
   ```bash
   git clone https://github.com/your-repo/YJ_Studio.git
   cd YJ_Studio
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 运行程序：
   ```bash
   python main.py
   ```

## 使用说明

### 主界面
- **串口配置面板**：配置串口参数和连接状态
- **数据收发面板**：发送和接收原始数据
- **日志面板**：显示系统日志和调试信息
- **绘图面板**：实时绘制数据曲线

### 基本操作
1. 在串口配置面板中选择端口和参数
2. 点击"连接"按钮建立串口连接
3. 在发送面板中输入数据并发送
4. 在接收面板中查看返回数据

## 插件开发指南

### 插件结构
所有插件应放置在`panel_plugins/`目录下，基本结构如下：
```
panel_plugins/
└── my_plugin/
    ├── __init__.py      # 插件注册入口
    ├── plugin_panel.py  # 插件面板实现
    └── README.md        # 插件说明文档
```

### 开发要求
1. 必须继承`PanelInterface`基类
2. 必须定义`PANEL_TYPE_NAME`和`PANEL_DISPLAY_NAME`
3. 实现必要的接口方法：
   - `get_config()` - 获取面板配置
   - `apply_config()` - 应用面板配置
   - `get_initial_dock_title()` - 获取面板标题

完整开发指南请参考[docs/plugins_develop_PRO.md](docs/plugins_develop_PRO.md)

## 协议说明

### 协议格式
```
帧头(1B) | 源地址(1B) | 目的地址(1B) | 功能码(1B) | 长度(2B) | 数据(NB) | 校验(2B)
```

### 校验模式
1. **原始模式**：求和校验+累加校验
2. **CRC16模式**：CRC-16/CCITT-FALSE

详细协议定义请参考[protocol/yj_protocol.h](protocol/yj_protocol.h)

## 贡献指南

欢迎通过以下方式参与贡献：
- 报告问题和建议
- 提交Pull Request
- 开发新功能插件

## 许可证

本项目采用MIT许可证。详细信息请查看LICENSE文件。

---
**开发者**: YJ Studio Team  
**版本**: 2.0  
**最后更新**: 2025-06-01
