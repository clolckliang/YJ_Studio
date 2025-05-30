# PID代码生成器插件

这是一个基于YJ Studio插件框架的C语言PID控制器代码生成器。它可以根据用户配置的参数，使用模板文件生成完整的、可编译的C语言PID控制器代码。

## 功能特性

### 🎯 核心功能
- **双算法支持**: 支持位置式PID和增量式PID两种算法
- **参数可配置**: 支持Kp、Ki、Kd等所有PID参数的实时调整
- **代码模板化**: 使用模板文件生成代码，易于维护和扩展
- **语法高亮**: 内置C语言语法高亮显示
- **实时预览**: 参数修改后实时更新代码预览
- **代码导出**: 支持将生成的代码导出为.c文件

### 📋 支持的参数
- **PID系数**: Kp (比例)、Ki (积分)、Kd (微分)
- **输出限制**: 最大输出值、最小输出值
- **积分限制**: 防止积分饱和
- **采样时间**: 控制循环的采样周期
- **数据类型**: 支持float和double类型
- **代码选项**: 可选择是否包含注释和头文件

## 文件结构

```
panel_plugins/pid_code_generator/
├── __init__.py                    # 插件初始化文件
├── pid_generator_widget.py        # 主要的UI组件和逻辑
├── test_template.py              # 模板功能测试脚本
├── README.md                     # 本说明文件
└── templates/                    # 代码模板目录
    ├── positional_pid_template.c    # 位置式PID模板
    └── incremental_pid_template.c   # 增量式PID模板
```

## 使用方法

### 1. 在主程序中添加插件

插件会自动被YJ Studio的插件管理器发现和加载。

### 2. 配置PID参数

在"PID参数"选项卡中：
- 选择算法类型（位置式/增量式）
- 设置Kp、Ki、Kd系数
- 配置输出限制和积分限制
- 设置采样时间

### 3. 配置代码生成选项

在"代码配置"选项卡中：
- 设置结构体名称
- 设置函数前缀
- 选择数据类型（float/double）
- 选择是否包含注释

### 4. 预览和导出代码

在"代码预览"选项卡中：
- 实时查看生成的C代码
- 使用"生成代码"按钮刷新预览
- 使用"导出代码"按钮保存到文件

## 模板系统

### 模板文件格式

模板文件使用`{变量名}`的格式进行参数替换：

```c
typedef struct {
    {data_type} kp;           // 比例系数
    {data_type} ki;           // 积分系数
    {data_type} kd;           // 微分系数
    // ...
} {struct_name};

void {function_prefix}_Init({struct_name}* pid, {data_type} kp, {data_type} ki, {data_type} kd) {
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;
    pid->max_output = {max_output};
    // ...
}
```

### 支持的模板变量

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `{timestamp}` | 生成时间 | `2025-05-31 01:02:31` |
| `{data_type}` | 数据类型 | `float` 或 `double` |
| `{struct_name}` | 结构体名称 | `PID_Controller` |
| `{function_prefix}` | 函数前缀 | `PID` |
| `{max_output}` | 最大输出 | `100.0` |
| `{min_output}` | 最小输出 | `-100.0` |
| `{integral_limit}` | 积分限制 | `50.0` |
| `{sample_time}` | 采样时间 | `0.01` |
| `{kp}` | 比例系数 | `1.0` |
| `{ki}` | 积分系数 | `0.1` |
| `{kd}` | 微分系数 | `0.01` |

## 生成的代码示例

### 位置式PID

```c
typedef struct {
    float kp;           // 比例系数
    float ki;           // 积分系数
    float kd;           // 微分系数
    float setpoint;     // 设定值
    float last_error;   // 上次误差
    float integral;     // 积分累积
    float max_output;   // 最大输出
    float min_output;   // 最小输出
    float integral_limit; // 积分限制
    float sample_time;  // 采样时间
} PID_Controller;

float PID_Compute(PID_Controller* pid, float current_value) {
    float error = pid->setpoint - current_value;
    
    // 积分项计算
    pid->integral += error * pid->sample_time;
    
    // 积分限制
    if (pid->integral > pid->integral_limit) {
        pid->integral = pid->integral_limit;
    } else if (pid->integral < -pid->integral_limit) {
        pid->integral = -pid->integral_limit;
    }
    
    // 微分项计算
    float derivative = (error - pid->last_error) / pid->sample_time;
    
    // PID输出计算
    float output = pid->kp * error + pid->ki * pid->integral + pid->kd * derivative;
    
    // 输出限制
    if (output > pid->max_output) {
        output = pid->max_output;
    } else if (output < pid->min_output) {
        output = pid->min_output;
    }
    
    // 保存当前误差
    pid->last_error = error;
    
    return output;
}
```

### 增量式PID

增量式PID包含额外的历史误差存储和增量计算逻辑。

## 测试

运行测试脚本来验证模板功能：

```bash
cd panel_plugins/pid_code_generator
python test_template.py
```

测试脚本会生成两个示例文件：
- `generated_positional_pid.c` - 位置式PID示例
- `generated_incremental_pid.c` - 增量式PID示例

## 扩展开发

### 添加新的模板

1. 在`templates/`目录下创建新的模板文件
2. 使用`{变量名}`格式定义可替换的参数
3. 在`pid_generator_widget.py`中添加对应的模板选择逻辑

### 添加新的参数

1. 在`pid_params`字典中添加新参数
2. 在UI中添加对应的控件
3. 在模板替换字典中添加新的变量映射

## 技术特性

- **框架兼容**: 完全兼容YJ Studio插件框架
- **配置持久化**: 支持面板状态的保存和恢复
- **错误处理**: 完善的错误日志记录
- **主题支持**: 支持主题切换
- **资源管理**: 自动清理资源和信号连接

## 许可证

本插件遵循YJ Studio项目的许可证条款。

---

**开发者**: YJ Studio Team  
**版本**: 1.0  
**最后更新**: 2025-05-31
