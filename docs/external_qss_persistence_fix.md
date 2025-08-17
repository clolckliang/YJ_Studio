# 外部QSS文件持久化问题解决方案

## 问题描述

用户反馈加载外部QSS样式文件后，应用程序重启时无法自动恢复上次使用的外部QSS主题，每次都需要重新加载。

## 问题原因

原始的`ThemeManager`实现中：

1. `apply_external_qss()`方法只是应用了外部QSS文件，但没有将文件路径保存到设置中
2. `restore_last_theme()`方法只能恢复内置主题、预设主题和用户自定义主题，不支持外部QSS文件的恢复

## 解决方案

### 1. 修改`apply_external_qss()`方法

在`ui/theme_manager.py`中，为`apply_external_qss()`方法添加了设置保存功能：

```python
def apply_external_qss(self, qss_file_path: str) -> None:
    """从外部QSS文件加载并应用样式表。"""
    try:
        with open(qss_file_path, 'r', encoding='utf-8') as f:
            qss_content = f.read()
        self.app.setStyleSheet(qss_content)
        self._current_theme_info = {"type": "external", "name": Path(qss_file_path).name, "path": qss_file_path}
        
        # 保存外部QSS文件路径到设置中，以便下次启动时恢复
        self.settings.setValue("last_theme", Path(qss_file_path).name)
        self.settings.setValue("last_theme_type", "external")
        self.settings.setValue("last_external_qss_path", qss_file_path)
        
        # 发射主题变化信号
        self.theme_changed.emit(Path(qss_file_path).name)
        
        if self.error_logger:
            self.error_logger.log_info(f"已从外部文件加载并应用QSS样式: {qss_file_path}")
    except Exception as e:
        # 错误处理代码...
```

### 2. 修改`restore_last_theme()`方法

添加了对外部QSS文件类型的支持：

```python
def restore_last_theme(self) -> None:
    """恢复上次使用的主题"""
    last_theme = self.settings.value("last_theme", "light")
    last_theme_type = self.settings.value("last_theme_type", "internal")
    
    if last_theme_type == "external":
        # 恢复外部QSS文件
        last_external_qss_path = self.settings.value("last_external_qss_path", "")
        if last_external_qss_path and os.path.exists(last_external_qss_path):
            try:
                self.apply_external_qss(last_external_qss_path)
                if self.error_logger:
                    self.error_logger.log_info(f"已恢复外部QSS主题: {last_external_qss_path}")
                return
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(f"恢复外部QSS主题失败: {e}", "THEME_RESTORE")
                # 如果外部QSS文件加载失败，继续使用默认主题
        else:
            if self.error_logger:
                self.error_logger.log_warning(f"外部QSS文件不存在或路径为空: {last_external_qss_path}")
    elif last_theme_type == "preset" and hasattr(self, 'preset_themes') and last_theme in self.preset_themes:
        self.apply_theme(last_theme)
    elif last_theme_type == "internal" and last_theme in self.themes:
        self.apply_theme(last_theme)
    elif last_theme_type == "user_custom" and last_theme in self.user_themes:
        self.apply_theme(last_theme)
    else:
        self.apply_theme("light")  # 默认主题
```

## 保存的设置项

修改后，当用户加载外部QSS文件时，系统会保存以下设置：

- `last_theme`: 外部QSS文件的文件名
- `last_theme_type`: "external"
- `last_external_qss_path`: 外部QSS文件的完整路径

## 错误处理

系统会处理以下情况：

1. **文件不存在**: 如果保存的外部QSS文件路径不存在，会记录警告并使用默认主题
2. **文件读取失败**: 如果文件存在但读取失败，会记录错误并使用默认主题
3. **路径为空**: 如果保存的路径为空，会记录警告并使用默认主题

## 测试方法

可以使用提供的测试脚本验证功能：

```bash
python tests/test_external_qss_persistence.py
```

测试步骤：
1. 运行测试程序
2. 点击"加载外部QSS文件"选择一个QSS文件
3. 观察界面样式变化
4. 点击"模拟重启"测试恢复功能
5. 重新运行程序，检查是否自动恢复了外部QSS主题

## 使用说明

现在用户可以：

1. 通过菜单或代码加载外部QSS文件
2. 应用程序会自动保存外部QSS文件的路径
3. 下次启动应用程序时，会自动恢复上次使用的外部QSS主题
4. 如果外部QSS文件被移动或删除，应用程序会自动回退到默认主题

这样就完全解决了外部QSS文件无法持久化的问题。