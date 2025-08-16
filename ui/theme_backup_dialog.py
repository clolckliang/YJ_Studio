from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QMessageBox, QFileDialog, QProgressBar, QTextEdit,
    QGroupBox, QCheckBox, QDateTimeEdit, QComboBox, QSpinBox
)
from PySide6.QtCore import Qt, QDateTime, QTimer, QThread, Signal
from PySide6.QtGui import QFont
import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional


class BackupWorker(QThread):
    """备份工作线程"""
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str)  # success, message
    
    def __init__(self, theme_manager, backup_path: str, selected_themes: List[str], include_settings: bool):
        super().__init__()
        self.theme_manager = theme_manager
        self.backup_path = backup_path
        self.selected_themes = selected_themes
        self.include_settings = include_settings
    
    def run(self):
        try:
            self.status_updated.emit("正在创建备份...")
            
            backup_data = {
                "backup_info": {
                    "version": "1.0",
                    "created_at": datetime.now().isoformat(),
                    "app_version": "YJ Studio 1.0",
                    "theme_count": len(self.selected_themes)
                },
                "themes": {},
                "settings": {} if self.include_settings else None
            }
            
            # 备份主题
            total_themes = len(self.selected_themes)
            for i, theme_name in enumerate(self.selected_themes):
                self.status_updated.emit(f"正在备份主题: {theme_name}")
                
                theme_info = self.theme_manager.get_theme_info(theme_name)
                theme_content = self.theme_manager.get_theme_content(theme_name)
                
                if theme_content:
                    backup_data["themes"][theme_name] = {
                        "content": theme_content,
                        "info": theme_info,
                        "type": theme_info.get("type", "unknown")
                    }
                
                progress = int((i + 1) / total_themes * 90)
                self.progress_updated.emit(progress)
            
            # 备份设置
            if self.include_settings:
                self.status_updated.emit("正在备份设置...")
                backup_data["settings"] = {
                    "current_theme": self.theme_manager.current_theme_info,
                    "theme_history": getattr(self.theme_manager, 'theme_history', []),
                    "user_preferences": getattr(self.theme_manager, 'user_preferences', {})
                }
            
            # 保存备份文件
            self.status_updated.emit("正在保存备份文件...")
            with open(self.backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            self.progress_updated.emit(100)
            self.status_updated.emit("备份完成")
            self.finished.emit(True, f"成功备份 {len(self.selected_themes)} 个主题")
            
        except Exception as e:
            self.finished.emit(False, f"备份失败: {str(e)}")


class RestoreWorker(QThread):
    """恢复工作线程"""
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str, dict)  # success, message, restored_themes
    
    def __init__(self, theme_manager, backup_path: str, selected_themes: List[str], restore_settings: bool):
        super().__init__()
        self.theme_manager = theme_manager
        self.backup_path = backup_path
        self.selected_themes = selected_themes
        self.restore_settings = restore_settings
    
    def run(self):
        try:
            self.status_updated.emit("正在读取备份文件...")
            
            with open(self.backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            themes_data = backup_data.get("themes", {})
            settings_data = backup_data.get("settings", {})
            
            restored_themes = {}
            total_themes = len(self.selected_themes)
            
            # 恢复主题
            for i, theme_name in enumerate(self.selected_themes):
                if theme_name in themes_data:
                    self.status_updated.emit(f"正在恢复主题: {theme_name}")
                    
                    theme_data = themes_data[theme_name]
                    theme_content = theme_data.get("content", "")
                    
                    if theme_content:
                        # 确保主题名唯一
                        original_name = theme_name
                        counter = 1
                        while (theme_name in self.theme_manager.themes or 
                               theme_name in self.theme_manager.user_themes):
                            theme_name = f"{original_name}_restored_{counter}"
                            counter += 1
                        
                        self.theme_manager.user_themes[theme_name] = theme_content
                        restored_themes[original_name] = theme_name
                
                progress = int((i + 1) / total_themes * 90)
                self.progress_updated.emit(progress)
            
            # 保存恢复的主题
            if restored_themes:
                self.theme_manager._save_user_themes()
                self.theme_manager.theme_list_updated.emit()
            
            # 恢复设置
            if self.restore_settings and settings_data:
                self.status_updated.emit("正在恢复设置...")
                # 这里可以添加设置恢复逻辑
                pass
            
            self.progress_updated.emit(100)
            self.status_updated.emit("恢复完成")
            self.finished.emit(True, f"成功恢复 {len(restored_themes)} 个主题", restored_themes)
            
        except Exception as e:
            self.finished.emit(False, f"恢复失败: {str(e)}", {})


class ThemeBackupDialog(QDialog):
    """主题备份和恢复对话框"""
    
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.backup_worker = None
        self.restore_worker = None
        
        self.setWindowTitle("主题备份与恢复")
        self.setFixedSize(700, 600)
        
        self.setup_ui()
        self.load_theme_list()
        self.load_backup_history()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("主题备份与恢复")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 备份区域
        backup_group = QGroupBox("创建备份")
        backup_layout = QVBoxLayout(backup_group)
        
        # 主题选择
        backup_layout.addWidget(QLabel("选择要备份的主题:"))
        self.backup_theme_list = QListWidget()
        self.backup_theme_list.setMaximumHeight(150)
        backup_layout.addWidget(self.backup_theme_list)
        
        # 备份选项
        options_layout = QHBoxLayout()
        self.select_all_backup_btn = QPushButton("全选")
        self.select_all_backup_btn.clicked.connect(self.select_all_backup_themes)
        options_layout.addWidget(self.select_all_backup_btn)
        
        self.include_settings_cb = QCheckBox("包含主题设置")
        self.include_settings_cb.setChecked(True)
        options_layout.addWidget(self.include_settings_cb)
        
        options_layout.addStretch()
        backup_layout.addLayout(options_layout)
        
        # 备份按钮
        self.create_backup_btn = QPushButton("创建备份")
        self.create_backup_btn.clicked.connect(self.create_backup)
        backup_layout.addWidget(self.create_backup_btn)
        
        layout.addWidget(backup_group)
        
        # 恢复区域
        restore_group = QGroupBox("恢复备份")
        restore_layout = QVBoxLayout(restore_group)
        
        # 备份文件选择
        file_layout = QHBoxLayout()
        restore_layout.addWidget(QLabel("选择备份文件:"))
        self.backup_file_label = QLabel("未选择文件")
        self.backup_file_label.setStyleSheet("color: gray;")
        file_layout.addWidget(self.backup_file_label)
        
        self.select_backup_file_btn = QPushButton("浏览...")
        self.select_backup_file_btn.clicked.connect(self.select_backup_file)
        file_layout.addWidget(self.select_backup_file_btn)
        restore_layout.addLayout(file_layout)
        
        # 恢复主题列表
        restore_layout.addWidget(QLabel("选择要恢复的主题:"))
        self.restore_theme_list = QListWidget()
        self.restore_theme_list.setMaximumHeight(120)
        restore_layout.addWidget(self.restore_theme_list)
        
        # 恢复选项
        restore_options_layout = QHBoxLayout()
        self.select_all_restore_btn = QPushButton("全选")
        self.select_all_restore_btn.clicked.connect(self.select_all_restore_themes)
        restore_options_layout.addWidget(self.select_all_restore_btn)
        
        self.restore_settings_cb = QCheckBox("恢复主题设置")
        restore_options_layout.addWidget(self.restore_settings_cb)
        
        restore_options_layout.addStretch()
        restore_layout.addLayout(restore_options_layout)
        
        # 恢复按钮
        self.restore_backup_btn = QPushButton("恢复备份")
        self.restore_backup_btn.clicked.connect(self.restore_backup)
        self.restore_backup_btn.setEnabled(False)
        restore_layout.addWidget(self.restore_backup_btn)
        
        layout.addWidget(restore_group)
        
        # 进度区域
        progress_group = QGroupBox("操作进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("就绪")
        progress_layout.addWidget(self.status_label)
        
        layout.addWidget(progress_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def load_theme_list(self):
        """加载主题列表"""
        self.backup_theme_list.clear()
        all_themes = self.theme_manager.get_all_themes()
        
        for theme_name, theme_type in all_themes.items():
            item = QListWidgetItem(f"{theme_name} ({theme_type})")
            item.setData(Qt.ItemDataRole.UserRole, theme_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.backup_theme_list.addItem(item)
    
    def load_backup_history(self):
        """加载备份历史（可选功能）"""
        # 这里可以添加备份历史记录功能
        pass
    
    def select_all_backup_themes(self):
        """全选备份主题"""
        for i in range(self.backup_theme_list.count()):
            item = self.backup_theme_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)
    
    def select_all_restore_themes(self):
        """全选恢复主题"""
        for i in range(self.restore_theme_list.count()):
            item = self.restore_theme_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)
    
    def create_backup(self):
        """创建备份"""
        # 获取选中的主题
        selected_themes = []
        for i in range(self.backup_theme_list.count()):
            item = self.backup_theme_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                theme_name = item.data(Qt.ItemDataRole.UserRole)
                selected_themes.append(theme_name)
        
        if not selected_themes:
            QMessageBox.warning(self, "警告", "请至少选择一个主题进行备份")
            return
        
        # 选择保存位置
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存备份文件", 
            f"theme_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        
        if not file_path:
            return
        
        # 开始备份
        self.create_backup_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
        include_settings = self.include_settings_cb.isChecked()
        self.backup_worker = BackupWorker(self.theme_manager, file_path, selected_themes, include_settings)
        self.backup_worker.progress_updated.connect(self.progress_bar.setValue)
        self.backup_worker.status_updated.connect(self.status_label.setText)
        self.backup_worker.finished.connect(self.on_backup_finished)
        self.backup_worker.start()
    
    def on_backup_finished(self, success: bool, message: str):
        """备份完成"""
        self.create_backup_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "错误", message)
        
        self.backup_worker = None
    
    def select_backup_file(self):
        """选择备份文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择备份文件", "",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            self.backup_file_label.setText(os.path.basename(file_path))
            self.backup_file_label.setProperty("file_path", file_path)
            self.load_backup_themes(file_path)
            self.restore_backup_btn.setEnabled(True)
    
    def load_backup_themes(self, file_path: str):
        """加载备份文件中的主题列表"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            self.restore_theme_list.clear()
            themes_data = backup_data.get("themes", {})
            
            for theme_name, theme_data in themes_data.items():
                theme_type = theme_data.get("info", {}).get("type", "unknown")
                type_text = {
                    'builtin': '内置主题',
                    'preset': '预设主题',
                    'custom': '自定义主题'
                }.get(theme_type, '未知主题')
                
                item = QListWidgetItem(f"{theme_name} ({type_text})")
                item.setData(Qt.ItemDataRole.UserRole, theme_name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.restore_theme_list.addItem(item)
            
            # 显示备份信息
            backup_info = backup_data.get("backup_info", {})
            created_at = backup_info.get("created_at", "未知")
            theme_count = backup_info.get("theme_count", 0)
            self.status_label.setText(f"备份文件: {theme_count} 个主题, 创建于 {created_at[:19]}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取备份文件失败: {str(e)}")
            self.backup_file_label.setText("文件读取失败")
            self.restore_backup_btn.setEnabled(False)
    
    def restore_backup(self):
        """恢复备份"""
        # 获取选中的主题
        selected_themes = []
        for i in range(self.restore_theme_list.count()):
            item = self.restore_theme_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                theme_name = item.data(Qt.ItemDataRole.UserRole)
                selected_themes.append(theme_name)
        
        if not selected_themes:
            QMessageBox.warning(self, "警告", "请至少选择一个主题进行恢复")
            return
        
        # 确认恢复
        reply = QMessageBox.question(
            self, "确认恢复", 
            f"确定要恢复 {len(selected_themes)} 个主题吗？\n\n如果存在同名主题，将会自动重命名。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 开始恢复
        self.restore_backup_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
        file_path = self.backup_file_label.property("file_path")
        restore_settings = self.restore_settings_cb.isChecked()
        
        self.restore_worker = RestoreWorker(self.theme_manager, file_path, selected_themes, restore_settings)
        self.restore_worker.progress_updated.connect(self.progress_bar.setValue)
        self.restore_worker.status_updated.connect(self.status_label.setText)
        self.restore_worker.finished.connect(self.on_restore_finished)
        self.restore_worker.start()
    
    def on_restore_finished(self, success: bool, message: str, restored_themes: Dict[str, str]):
        """恢复完成"""
        self.restore_backup_btn.setEnabled(True)
        
        if success:
            if restored_themes:
                details = "\n".join([f"• {old} → {new}" for old, new in restored_themes.items()])
                QMessageBox.information(self, "成功", f"{message}\n\n恢复的主题:\n{details}")
            else:
                QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "错误", message)
        
        self.restore_worker = None
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.backup_worker and self.backup_worker.isRunning():
            reply = QMessageBox.question(
                self, "确认关闭", "备份操作正在进行中，确定要关闭吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.backup_worker.terminate()
        
        if self.restore_worker and self.restore_worker.isRunning():
            reply = QMessageBox.question(
                self, "确认关闭", "恢复操作正在进行中，确定要关闭吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.restore_worker.terminate()
        
        event.accept()