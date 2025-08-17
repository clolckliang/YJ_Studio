from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QTabWidget,
    QWidget, QFileDialog, QMessageBox, QProgressBar,
    QGroupBox, QCheckBox, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QColor
import json
import os
import zipfile
import tempfile
from typing import Dict, List, Any


class ThemePackageWorker(QThread):
    """主题包处理工作线程"""
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str)  # success, message
    
    def __init__(self, operation: str, **kwargs):
        super().__init__()
        self.operation = operation
        self.kwargs = kwargs
    
    def run(self):
        try:
            if self.operation == "export":
                self._export_themes()
            elif self.operation == "import":
                self._import_themes()
        except Exception as e:
            self.finished.emit(False, str(e))
    
    def _export_themes(self):
        """导出主题包"""
        themes = self.kwargs['themes']
        file_path = self.kwargs['file_path']
        theme_manager = self.kwargs['theme_manager']
        include_presets = self.kwargs.get('include_presets', False)
        
        self.status_updated.emit("正在创建主题包...")
        
        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            package_info = {
                'name': self.kwargs.get('package_name', '主题包'),
                'description': self.kwargs.get('package_description', ''),
                'version': '1.0',
                'themes': {},
                'created_by': 'YJ Studio Theme Manager'
            }
            
            total_themes = len(themes)
            for i, theme_name in enumerate(themes):
                self.status_updated.emit(f"正在处理主题: {theme_name}")
                
                # 获取主题信息
                theme_info = theme_manager.get_theme_info(theme_name)
                theme_content = theme_manager.get_theme_content(theme_name)
                
                if theme_content:
                    package_info['themes'][theme_name] = {
                        'name': theme_info.get('name', theme_name),
                        'description': theme_info.get('description', ''),
                        'type': theme_info.get('type', 'custom'),
                        'category': theme_info.get('category', 'other'),
                        'colors': theme_info.get('colors', {}),
                        'css': theme_content
                    }
                
                progress = int((i + 1) / total_themes * 100)
                self.progress_updated.emit(progress)
            
            # 写入包信息文件
            zf.writestr('package.json', json.dumps(package_info, ensure_ascii=False, indent=2))
            
            # 如果包含预设主题，也添加预设文件
            if include_presets and hasattr(theme_manager, 'preset_themes'):
                preset_data = {
                    'theme_presets': theme_manager.preset_themes,
                    'theme_categories': getattr(theme_manager, 'theme_categories', {}),
                    'theme_settings': getattr(theme_manager, 'theme_settings', {})
                }
                zf.writestr('presets.json', json.dumps(preset_data, ensure_ascii=False, indent=2))
        
        self.status_updated.emit("主题包创建完成")
        self.finished.emit(True, f"主题包已保存到: {file_path}")
    
    def _import_themes(self):
        """导入主题包"""
        file_path = self.kwargs['file_path']
        theme_manager = self.kwargs['theme_manager']
        selected_themes = self.kwargs.get('selected_themes', [])
        
        self.status_updated.emit("正在解析主题包...")
        
        with zipfile.ZipFile(file_path, 'r') as zf:
            # 读取包信息
            package_data = json.loads(zf.read('package.json').decode('utf-8'))
            themes = package_data.get('themes', {})
            
            imported_count = 0
            total_themes = len(selected_themes) if selected_themes else len(themes)
            
            themes_to_import = selected_themes if selected_themes else list(themes.keys())
            
            for i, theme_name in enumerate(themes_to_import):
                if theme_name in themes:
                    self.status_updated.emit(f"正在导入主题: {theme_name}")
                    
                    theme_data = themes[theme_name]
                    
                    # 创建主题
                    try:
                        theme_manager.create_custom_theme(
                            theme_name,
                            base_theme="dark"
                        )
                        
                        # 更新主题内容
                        theme_manager.update_custom_theme(
                            theme_name,
                            theme_data.get('css', ''),
                            theme_data
                        )
                        
                        imported_count += 1
                    except Exception as e:
                        print(f"导入主题 {theme_name} 失败: {e}")
                
                progress = int((i + 1) / total_themes * 100)
                self.progress_updated.emit(progress)
        
        self.status_updated.emit(f"导入完成，成功导入 {imported_count} 个主题")
        self.finished.emit(True, f"成功导入 {imported_count} 个主题")


class ThemeImportExportDialog(QDialog):
    """主题导入导出对话框"""
    
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.worker = None
        
        self.setWindowTitle("主题导入导出")
        self.setFixedSize(600, 500)
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 导出标签页
        export_tab = self.create_export_tab()
        tab_widget.addTab(export_tab, "导出主题")
        
        # 导入标签页
        import_tab = self.create_import_tab()
        tab_widget.addTab(import_tab, "导入主题")
        
        layout.addWidget(tab_widget)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def create_export_tab(self) -> QWidget:
        """创建导出标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 包信息
        info_group = QGroupBox("包信息")
        info_layout = QVBoxLayout(info_group)
        
        # 包名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("包名称:"))
        self.package_name_edit = QLineEdit("我的主题包")
        name_layout.addWidget(self.package_name_edit)
        info_layout.addLayout(name_layout)
        
        # 包描述
        info_layout.addWidget(QLabel("包描述:"))
        self.package_desc_edit = QTextEdit()
        self.package_desc_edit.setMaximumHeight(60)
        self.package_desc_edit.setPlainText("包含自定义主题的主题包")
        info_layout.addWidget(self.package_desc_edit)
        
        layout.addWidget(info_group)
        
        # 主题选择
        themes_group = QGroupBox("选择要导出的主题")
        themes_layout = QVBoxLayout(themes_group)
        
        # 全选/取消全选
        select_layout = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self.select_all_export_themes)
        select_layout.addWidget(select_all_btn)
        
        select_none_btn = QPushButton("取消全选")
        select_none_btn.clicked.connect(self.select_none_export_themes)
        select_layout.addWidget(select_none_btn)
        
        select_layout.addStretch()
        themes_layout.addLayout(select_layout)
        
        # 主题列表
        self.export_theme_list = QListWidget()
        self.load_export_themes()
        themes_layout.addWidget(self.export_theme_list)
        
        # 包含预设主题选项
        self.include_presets_cb = QCheckBox("包含预设主题配置")
        themes_layout.addWidget(self.include_presets_cb)
        
        layout.addWidget(themes_group)
        
        # 导出按钮
        export_btn = QPushButton("导出主题包")
        export_btn.clicked.connect(self.export_themes)
        layout.addWidget(export_btn)
        
        return widget
    
    def create_import_tab(self) -> QWidget:
        """创建导入标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 文件选择
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("主题包文件:"))
        
        self.import_file_edit = QLineEdit()
        self.import_file_edit.setReadOnly(True)
        file_layout.addWidget(self.import_file_edit)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_import_file)
        file_layout.addWidget(browse_btn)
        
        layout.addLayout(file_layout)
        
        # 包信息显示
        self.package_info_text = QTextEdit()
        self.package_info_text.setMaximumHeight(100)
        self.package_info_text.setReadOnly(True)
        layout.addWidget(QLabel("包信息:"))
        layout.addWidget(self.package_info_text)
        
        # 主题列表
        layout.addWidget(QLabel("包含的主题:"))
        
        # 全选/取消全选
        select_layout = QHBoxLayout()
        select_all_import_btn = QPushButton("全选")
        select_all_import_btn.clicked.connect(self.select_all_import_themes)
        select_layout.addWidget(select_all_import_btn)
        
        select_none_import_btn = QPushButton("取消全选")
        select_none_import_btn.clicked.connect(self.select_none_import_themes)
        select_layout.addWidget(select_none_import_btn)
        
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        self.import_theme_list = QListWidget()
        layout.addWidget(self.import_theme_list)
        
        # 导入按钮
        import_btn = QPushButton("导入选中主题")
        import_btn.clicked.connect(self.import_themes)
        layout.addWidget(import_btn)
        
        return widget
    
    def load_export_themes(self):
        """加载可导出的主题"""
        self.export_theme_list.clear()
        
        # 添加用户自定义主题
        for theme_name in self.theme_manager.user_themes.keys():
            item = QListWidgetItem(f"{theme_name} (自定义)")
            item.setData(Qt.ItemDataRole.UserRole, theme_name)
            item.setCheckState(Qt.CheckState.Checked)
            self.export_theme_list.addItem(item)
        
        # 添加预设主题（如果有）
        if hasattr(self.theme_manager, 'preset_themes'):
            for theme_name in self.theme_manager.preset_themes.keys():
                item = QListWidgetItem(f"{theme_name} (预设)")
                item.setData(Qt.ItemDataRole.UserRole, theme_name)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.export_theme_list.addItem(item)
    
    def select_all_export_themes(self):
        """全选导出主题"""
        for i in range(self.export_theme_list.count()):
            item = self.export_theme_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)
    
    def select_none_export_themes(self):
        """取消全选导出主题"""
        for i in range(self.export_theme_list.count()):
            item = self.export_theme_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)
    
    def select_all_import_themes(self):
        """全选导入主题"""
        for i in range(self.import_theme_list.count()):
            item = self.import_theme_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)
    
    def select_none_import_themes(self):
        """取消全选导入主题"""
        for i in range(self.import_theme_list.count()):
            item = self.import_theme_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)
    
    def browse_import_file(self):
        """浏览导入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择主题包文件",
            "",
            "主题包文件 (*.zip);;所有文件 (*)"
        )
        
        if file_path:
            self.import_file_edit.setText(file_path)
            self.load_package_info(file_path)
    
    def load_package_info(self, file_path: str):
        """加载包信息"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                package_data = json.loads(zf.read('package.json').decode('utf-8'))
                
                # 显示包信息
                info_text = f"名称: {package_data.get('name', '未知')}\n"
                info_text += f"版本: {package_data.get('version', '未知')}\n"
                info_text += f"描述: {package_data.get('description', '无描述')}\n"
                info_text += f"创建者: {package_data.get('created_by', '未知')}"
                
                self.package_info_text.setPlainText(info_text)
                
                # 加载主题列表
                self.import_theme_list.clear()
                themes = package_data.get('themes', {})
                
                for theme_name, theme_data in themes.items():
                    display_name = theme_data.get('name', theme_name)
                    theme_type = theme_data.get('type', 'custom')
                    category = theme_data.get('category', '')
                    
                    item_text = f"{display_name} ({theme_type})"
                    if category:
                        item_text += f" - {category}"
                    
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, theme_name)
                    item.setCheckState(Qt.CheckState.Checked)
                    self.import_theme_list.addItem(item)
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法读取主题包文件: {e}")
    
    def export_themes(self):
        """导出主题"""
        # 获取选中的主题
        selected_themes = []
        for i in range(self.export_theme_list.count()):
            item = self.export_theme_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                theme_name = item.data(Qt.ItemDataRole.UserRole)
                selected_themes.append(theme_name)
        
        if not selected_themes:
            QMessageBox.warning(self, "警告", "请至少选择一个主题进行导出")
            return
        
        # 选择保存文件
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存主题包",
            f"{self.package_name_edit.text()}.zip",
            "主题包文件 (*.zip)"
        )
        
        if not file_path:
            return
        
        # 开始导出
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.worker = ThemePackageWorker(
            "export",
            themes=selected_themes,
            file_path=file_path,
            theme_manager=self.theme_manager,
            package_name=self.package_name_edit.text(),
            package_description=self.package_desc_edit.toPlainText(),
            include_presets=self.include_presets_cb.isChecked()
        )
        
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.status_updated.connect(self.status_label.setText)
        self.worker.finished.connect(self.on_export_finished)
        self.worker.start()
    
    def import_themes(self):
        """导入主题"""
        if not self.import_file_edit.text():
            QMessageBox.warning(self, "警告", "请先选择要导入的主题包文件")
            return
        
        # 获取选中的主题
        selected_themes = []
        for i in range(self.import_theme_list.count()):
            item = self.import_theme_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                theme_name = item.data(Qt.ItemDataRole.UserRole)
                selected_themes.append(theme_name)
        
        if not selected_themes:
            QMessageBox.warning(self, "警告", "请至少选择一个主题进行导入")
            return
        
        # 开始导入
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.worker = ThemePackageWorker(
            "import",
            file_path=self.import_file_edit.text(),
            theme_manager=self.theme_manager,
            selected_themes=selected_themes
        )
        
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.status_updated.connect(self.status_label.setText)
        self.worker.finished.connect(self.on_import_finished)
        self.worker.start()
    
    def on_export_finished(self, success: bool, message: str):
        """导出完成"""
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "错误", f"导出失败: {message}")
        
        self.worker = None
    
    def on_import_finished(self, success: bool, message: str):
        """导入完成"""
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        
        if success:
            QMessageBox.information(self, "成功", message)
            # 重新加载主题列表
            if hasattr(self.theme_manager, 'theme_list_updated'):
                self.theme_manager.theme_list_updated.emit()
        else:
            QMessageBox.critical(self, "错误", f"导入失败: {message}")
        
        self.worker = None
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认",
                "操作正在进行中，确定要关闭吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.terminate()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()