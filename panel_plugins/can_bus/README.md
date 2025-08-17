# CAN总线插件

## 插件简介
这是一个集成在YJ Studio中的CAN总线通信工具面板插件，可以在主程序中作为独立面板使用。

## 功能特性
- 支持多种CAN接口类型
- 实时收发CAN消息
- 消息过滤和解析
- 数据可视化
- 总线状态监控

## 支持的接口类型
- socketcan (Linux)
- virtual (虚拟接口)
- pcan (PEAK CAN)
- ixxat (IXXAT USB-to-CAN)
- nican (NI CAN)
- iscan (Intrepid CAN)
- kvaser (Kvaser CAN)
- serial (串口转CAN)
- usb2can (USB转CAN)

## 使用方法

### 1. 连接设置
1. 选择接口类型
2. 输入通道名称(如can0)
3. 设置波特率(默认500kbps)
4. 点击"启动"按钮连接总线

### 2. 接收消息
- 接收到的消息会显示在表格中
- 表格包含时间戳、ID、类型、长度、数据和计数
- 自动滚动显示最新消息

### 3. 发送消息
1. 输入消息ID(16进制)
2. 输入数据(16进制，空格分隔)
3. 点击"发送"按钮发送消息

## 安装使用
1. 将`can_bus`文件夹放入`panel_plugins`目录
2. 在主程序中选择"添加面板" → "CAN总线工具"
3. 配置接口参数并启动连接

## 开发信息
- 开发者: YJ Studio
- 版本: 1.0.0
- 依赖: python-can

## 注意事项
1. 确保已安装python-can库: `pip install python-can`
2. 根据使用的接口类型，可能需要安装额外驱动
3. 部分接口类型需要管理员权限
