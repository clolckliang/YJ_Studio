# quick_send_editor_dialog.py
# 快捷发送编辑对话框

import json
from typing import List, Optional
from dataclasses import dataclass, asdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QCheckBox, QMessageBox, QGroupBox, QListWidget,
    QListWidgetItem, QSplitter, QFileDialog,
    QDialogButtonBox, QComboBox
)


@dataclass
class QuickSendItem:
    """快捷发送项数据类"""
    name: str
    data: str
    is_hex: bool
    description: str = ""
    hotkey: str = ""  # 快捷键
    category: str = "默认"  # 分类


class QuickSendEditorDialog(QDialog):
    """快捷发送编辑对话框
    
    功能：
    1. 添加、编辑、删除快捷发送项
    2. 支持分类管理
    3. 支持导入导出配置
    4. 支持快捷键设置
    5. 支持数据验证
    """
    
    items_changed = Signal(list)  # 发送项列表改变信号
    
    def __init__(self, items: List[QuickSendItem], parent=None):
        super().__init__(parent)
        self.items = items.copy()  # 复制一份，避免直接修改原数据
        self.current_item: Optional[QuickSendItem] = None
        self.current_index = -1
        
        self.setWindowTitle("快捷发送编辑器")
        self.setModal(True)
        self.resize(800, 600)
        
        self._init_ui()
        self._load_items()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 创建主要区域
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：项目列表
        left_widget = self._create_list_widget()
        main_splitter.addWidget(left_widget)
        
        # 右侧：编辑区域
        right_widget = self._create_edit_widget()
        main_splitter.addWidget(right_widget)
        
        main_splitter.setSizes([300, 500])
        layout.addWidget(main_splitter)
        
        # 底部按钮
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
    
    def _create_list_widget(self) -> QGroupBox:
        """创建项目列表区域"""
        group = QGroupBox("快捷发送项列表")
        layout = QVBoxLayout()
        
        # 分类过滤
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("分类:"))
        self.category_filter = QComboBox()
        self.category_filter.addItem("全部")
        filter_layout.addWidget(self.category_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # 项目列表
        self.items_list = QListWidget()
        self.items_list.setAlternatingRowColors(True)
        layout.addWidget(self.items_list)
        
        # 列表操作按钮
        list_buttons_layout = QHBoxLayout()
        
        self.add_button = QPushButton("添加")
        self.add_button.clicked.connect(self._add_item)
        list_buttons_layout.addWidget(self.add_button)
        
        self.duplicate_button = QPushButton("复制")
        self.duplicate_button.clicked.connect(self._duplicate_item)
        list_buttons_layout.addWidget(self.duplicate_button)
        
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self._delete_item)
        list_buttons_layout.addWidget(self.delete_button)
        
        list_buttons_layout.addStretch()
        layout.addLayout(list_buttons_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_edit_widget(self) -> QGroupBox:
        """创建编辑区域"""
        group = QGroupBox("编辑快捷发送项")
        layout = QVBoxLayout()
        
        # 基本信息
        basic_group = QGroupBox("基本信息")
        basic_layout = QGridLayout()
        
        # 名称
        basic_layout.addWidget(QLabel("名称:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入快捷发送项名称")
        basic_layout.addWidget(self.name_edit, 0, 1)
        
        # 分类
        basic_layout.addWidget(QLabel("分类:"), 0, 2)
        self.category_edit = QLineEdit()
        self.category_edit.setPlaceholderText("输入分类名称")
        basic_layout.addWidget(self.category_edit, 0, 3)
        
        # 快捷键
        basic_layout.addWidget(QLabel("快捷键:"), 1, 0)
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setPlaceholderText("如: Ctrl+1")
        basic_layout.addWidget(self.hotkey_edit, 1, 1)
        
        # 数据类型
        basic_layout.addWidget(QLabel("数据类型:"), 1, 2)
        self.is_hex_checkbox = QCheckBox("Hex数据")
        basic_layout.addWidget(self.is_hex_checkbox, 1, 3)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 数据内容
        data_group = QGroupBox("数据内容")
        data_layout = QVBoxLayout()
        
        self.data_edit = QTextEdit()
        self.data_edit.setMaximumHeight(120)
        self.data_edit.setFont(QFont("Consolas", 10))
        self.data_edit.setPlaceholderText(
            "输入要发送的数据\n" +
            "Hex模式: AB CD EF 或 ABCDEF\n" +
            "文本模式: Hello World"
        )
        data_layout.addWidget(self.data_edit)
        
        # 数据操作按钮
        data_buttons_layout = QHBoxLayout()
        
        validate_btn = QPushButton("验证数据")
        validate_btn.clicked.connect(self._validate_data)
        data_buttons_layout.addWidget(validate_btn)
        
        format_btn = QPushButton("格式化")
        format_btn.clicked.connect(self._format_data)
        data_buttons_layout.addWidget(format_btn)
        
        data_buttons_layout.addStretch()
        data_layout.addLayout(data_buttons_layout)
        
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)
        
        # 描述
        desc_group = QGroupBox("描述")
        desc_layout = QVBoxLayout()
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("输入描述信息（可选）")
        desc_layout.addWidget(self.description_edit)
        
        desc_group.setLayout(desc_layout)
        layout.addWidget(desc_group)
        
        # 预览
        preview_group = QGroupBox("预览")
        preview_layout = QVBoxLayout()
        
        self.preview_label = QLabel("选择一个项目进行预览")
        self.preview_label.setStyleSheet(
            "QLabel { "
            "background-color: #f0f0f0; "
            "border: 1px solid #ccc; "
            "padding: 10px; "
            "font-family: Consolas; "
            "}"
        )
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        group.setLayout(layout)
        return group
    
    def _create_button_layout(self) -> QHBoxLayout:
        """创建底部按钮布局"""
        layout = QHBoxLayout()
        
        # 文件操作按钮
        import_btn = QPushButton("导入配置")
        import_btn.clicked.connect(self._import_config)
        layout.addWidget(import_btn)
        
        export_btn = QPushButton("导出配置")
        export_btn.clicked.connect(self._export_config)
        layout.addWidget(export_btn)
        
        layout.addStretch()
        
        # 标准对话框按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply_changes)
        
        layout.addWidget(button_box)
        return layout
    
    def _connect_signals(self):
        """连接信号"""
        self.items_list.currentRowChanged.connect(self._on_item_selected)
        self.name_edit.textChanged.connect(self._on_data_changed)
        self.data_edit.textChanged.connect(self._on_data_changed)
        self.description_edit.textChanged.connect(self._on_data_changed)
        self.category_edit.textChanged.connect(self._on_data_changed)
        self.hotkey_edit.textChanged.connect(self._on_data_changed)
        self.is_hex_checkbox.toggled.connect(self._on_data_changed)
        self.category_filter.currentTextChanged.connect(self._filter_items)
    
    def _load_items(self):
        """加载项目到列表"""
        self.items_list.clear()
        
        # 更新分类过滤器
        categories = set(item.category for item in self.items)
        categories.add("默认")
        
        current_filter = self.category_filter.currentText()
        self.category_filter.clear()
        self.category_filter.addItem("全部")
        for category in sorted(categories):
            self.category_filter.addItem(category)
        
        # 恢复过滤器选择
        if current_filter:
            index = self.category_filter.findText(current_filter)
            if index >= 0:
                self.category_filter.setCurrentIndex(index)
        
        # 加载项目
        for i, item in enumerate(self.items):
            list_item = QListWidgetItem()
            list_item.setText(f"{item.name} ({item.category})")
            list_item.setData(Qt.ItemDataRole.UserRole, i)
            
            # 设置工具提示
            tooltip = f"名称: {item.name}\n"
            tooltip += f"分类: {item.category}\n"
            tooltip += f"类型: {'Hex' if item.is_hex else '文本'}\n"
            tooltip += f"数据: {item.data[:50]}{'...' if len(item.data) > 50 else ''}\n"
            if item.description:
                tooltip += f"描述: {item.description}"
            list_item.setToolTip(tooltip)
            
            self.items_list.addItem(list_item)
        
        self._filter_items()
    
    def _filter_items(self):
        """根据分类过滤项目"""
        filter_category = self.category_filter.currentText()
        
        for i in range(self.items_list.count()):
            item = self.items_list.item(i)
            item_index = item.data(Qt.ItemDataRole.UserRole)
            
            if filter_category == "全部":
                item.setHidden(False)
            else:
                item_category = self.items[item_index].category
                item.setHidden(item_category != filter_category)
    
    def _on_item_selected(self, row: int):
        """项目选择事件"""
        if row < 0:
            self._clear_edit_fields()
            return
        
        # 保存当前编辑的项目
        if self.current_index >= 0:
            self._save_current_item()
        
        # 加载选中的项目
        item = self.items_list.item(row)
        if item:
            item_index = item.data(Qt.ItemDataRole.UserRole)
            self.current_index = item_index
            self.current_item = self.items[item_index]
            self._load_item_to_edit_fields(self.current_item)
            self._update_preview()
    
    def _load_item_to_edit_fields(self, item: QuickSendItem):
        """加载项目到编辑字段"""
        self.name_edit.setText(item.name)
        self.data_edit.setPlainText(item.data)
        self.description_edit.setPlainText(item.description)
        self.category_edit.setText(item.category)
        self.hotkey_edit.setText(item.hotkey)
        self.is_hex_checkbox.setChecked(item.is_hex)
    
    def _clear_edit_fields(self):
        """清空编辑字段"""
        self.name_edit.clear()
        self.data_edit.clear()
        self.description_edit.clear()
        self.category_edit.setText("默认")
        self.hotkey_edit.clear()
        self.is_hex_checkbox.setChecked(False)
        self.preview_label.setText("选择一个项目进行预览")
        self.current_item = None
        self.current_index = -1
    
    def _save_current_item(self):
        """保存当前编辑的项目"""
        if self.current_index < 0 or not self.current_item:
            return
        
        # 验证数据
        if not self._validate_current_data():
            return
        
        # 更新项目数据
        self.current_item.name = self.name_edit.text().strip()
        self.current_item.data = self.data_edit.toPlainText().strip()
        self.current_item.description = self.description_edit.toPlainText().strip()
        self.current_item.category = self.category_edit.text().strip() or "默认"
        self.current_item.hotkey = self.hotkey_edit.text().strip()
        self.current_item.is_hex = self.is_hex_checkbox.isChecked()
        
        # 更新列表显示
        current_row = self.items_list.currentRow()
        if current_row >= 0:
            item = self.items_list.item(current_row)
            item.setText(f"{self.current_item.name} ({self.current_item.category})")
    
    def _validate_current_data(self) -> bool:
        """验证当前数据"""
        name = self.name_edit.text().strip()
        data = self.data_edit.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, "验证错误", "请输入项目名称")
            return False
        
        if not data:
            QMessageBox.warning(self, "验证错误", "请输入数据内容")
            return False
        
        # 验证Hex数据格式
        if self.is_hex_checkbox.isChecked():
            if not self._validate_hex_data(data):
                QMessageBox.warning(self, "验证错误", 
                                  "Hex数据格式不正确\n" +
                                  "请输入有效的十六进制数据，如: AB CD EF")
                return False
        
        return True
    
    def _validate_hex_data(self, data: str) -> bool:
        """验证Hex数据格式"""
        import re
        hex_text = re.sub(r'[\s\-:,]', '', data.upper())
        
        if not re.match(r'^[0-9A-F]*$', hex_text):
            return False
        
        return len(hex_text) % 2 == 0 and len(hex_text) > 0
    
    def _on_data_changed(self):
        """数据改变事件"""
        self._update_preview()
    
    def _update_preview(self):
        """更新预览"""
        name = self.name_edit.text().strip()
        data = self.data_edit.toPlainText().strip()
        description = self.description_edit.toPlainText().strip()
        category = self.category_edit.text().strip() or "默认"
        hotkey = self.hotkey_edit.text().strip()
        is_hex = self.is_hex_checkbox.isChecked()
        
        if not name and not data:
            self.preview_label.setText("选择一个项目进行预览")
            return
        
        preview_text = f"名称: {name or '未命名'}\n"
        preview_text += f"分类: {category}\n"
        preview_text += f"类型: {'Hex数据' if is_hex else '文本数据'}\n"
        
        if hotkey:
            preview_text += f"快捷键: {hotkey}\n"
        
        preview_text += f"数据: {data[:100]}{'...' if len(data) > 100 else ''}\n"
        
        if description:
            preview_text += f"描述: {description}"
        
        # 如果是Hex数据，显示字节数
        if is_hex and data:
            try:
                import re
                hex_text = re.sub(r'[\s\-:,]', '', data.upper())
                if self._validate_hex_data(data):
                    byte_count = len(hex_text) // 2
                    preview_text += f"\n字节数: {byte_count}"
            except:
                pass
        
        self.preview_label.setText(preview_text)
    
    def _add_item(self):
        """添加新项目"""
        new_item = QuickSendItem(
            name="新项目",
            data="",
            is_hex=False,
            description="",
            hotkey="",
            category="默认"
        )
        
        self.items.append(new_item)
        self._load_items()
        
        # 选中新添加的项目
        self.items_list.setCurrentRow(self.items_list.count() - 1)
    
    def _duplicate_item(self):
        """复制当前项目"""
        current_row = self.items_list.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "提示", "请先选择要复制的项目")
            return
        
        item = self.items_list.item(current_row)
        item_index = item.data(Qt.ItemDataRole.UserRole)
        original_item = self.items[item_index]
        
        # 创建副本
        new_item = QuickSendItem(
            name=f"{original_item.name}_副本",
            data=original_item.data,
            is_hex=original_item.is_hex,
            description=original_item.description,
            hotkey="",  # 清空快捷键避免冲突
            category=original_item.category
        )
        
        self.items.append(new_item)
        self._load_items()
        
        # 选中新复制的项目
        self.items_list.setCurrentRow(self.items_list.count() - 1)
    
    def _delete_item(self):
        """删除当前项目"""
        current_row = self.items_list.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "提示", "请先选择要删除的项目")
            return
        
        item = self.items_list.item(current_row)
        item_index = item.data(Qt.ItemDataRole.UserRole)
        item_name = self.items[item_index].name
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除项目 '{item_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            del self.items[item_index]
            self._load_items()
            self._clear_edit_fields()
    
    def _validate_data(self):
        """验证数据按钮事件"""
        data = self.data_edit.toPlainText().strip()
        is_hex = self.is_hex_checkbox.isChecked()
        
        if not data:
            QMessageBox.information(self, "验证结果", "数据为空")
            return
        
        if is_hex:
            if self._validate_hex_data(data):
                import re
                hex_text = re.sub(r'[\s\-:,]', '', data.upper())
                byte_count = len(hex_text) // 2
                QMessageBox.information(
                    self, "验证结果",
                    f"Hex数据格式正确\n字节数: {byte_count}"
                )
            else:
                QMessageBox.warning(
                    self, "验证结果",
                    "Hex数据格式不正确\n请检查数据格式"
                )
        else:
            byte_count = len(data.encode('utf-8'))
            QMessageBox.information(
                self, "验证结果",
                f"文本数据\n字符数: {len(data)}\n字节数: {byte_count}"
            )
    
    def _format_data(self):
        """格式化数据按钮事件"""
        data = self.data_edit.toPlainText().strip()
        is_hex = self.is_hex_checkbox.isChecked()
        
        if not data:
            return
        
        if is_hex:
            # 格式化Hex数据
            import re
            hex_text = re.sub(r'[\s\-:,]', '', data.upper())
            if self._validate_hex_data(data):
                # 每两个字符添加一个空格
                formatted = ' '.join(hex_text[i:i+2] for i in range(0, len(hex_text), 2))
                self.data_edit.setPlainText(formatted)
        else:
            # 文本数据格式化（移除多余空白）
            lines = data.split('\n')
            formatted_lines = [line.strip() for line in lines if line.strip()]
            self.data_edit.setPlainText('\n'.join(formatted_lines))
    
    def _import_config(self):
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入快捷发送配置",
            "", "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 验证数据格式
                if not isinstance(data, list):
                    raise ValueError("配置文件格式不正确")
                
                imported_items = []
                for item_data in data:
                    item = QuickSendItem(
                        name=item_data.get('name', '未命名'),
                        data=item_data.get('data', ''),
                        is_hex=item_data.get('is_hex', False),
                        description=item_data.get('description', ''),
                        hotkey=item_data.get('hotkey', ''),
                        category=item_data.get('category', '默认')
                    )
                    imported_items.append(item)
                
                # 询问是否替换还是追加
                reply = QMessageBox.question(
                    self, "导入方式",
                    f"找到 {len(imported_items)} 个项目\n" +
                    "选择导入方式：\n" +
                    "是：替换现有项目\n" +
                    "否：追加到现有项目",
                    QMessageBox.StandardButton.Yes | 
                    QMessageBox.StandardButton.No |
                    QMessageBox.StandardButton.Cancel
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.items = imported_items
                elif reply == QMessageBox.StandardButton.No:
                    self.items.extend(imported_items)
                else:
                    return
                
                self._load_items()
                QMessageBox.information(self, "成功", "配置导入成功")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {str(e)}")
    
    def _export_config(self):
        """导出配置"""
        if not self.items:
            QMessageBox.information(self, "提示", "没有项目可导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出快捷发送配置",
            "quick_send_config.json",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                # 保存当前编辑的项目
                if self.current_index >= 0:
                    self._save_current_item()
                
                data = [asdict(item) for item in self.items]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "成功", f"配置已导出到: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def _apply_changes(self):
        """应用更改"""
        if self.current_index >= 0:
            self._save_current_item()
        
        self.items_changed.emit(self.items)
        QMessageBox.information(self, "成功", "更改已应用")
    
    def accept(self):
        """确定按钮"""
        if self.current_index >= 0:
            if not self._validate_current_data():
                return
            self._save_current_item()
        
        self.items_changed.emit(self.items)
        super().accept()
    
    def get_items(self) -> List[QuickSendItem]:
        """获取编辑后的项目列表"""
        return self.items


if __name__ == "__main__":
    # 测试代码
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 测试数据
    test_items = [
        QuickSendItem("心跳包", "AA BB CC DD", True, "设备心跳包", "Ctrl+1", "通信"),
        QuickSendItem("查询状态", "01 03 00 00", True, "查询设备状态", "Ctrl+2", "查询"),
        QuickSendItem("Hello", "Hello World!", False, "文本测试", "Ctrl+3", "测试")
    ]
    
    dialog = QuickSendEditorDialog(test_items)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        items = dialog.get_items()
        print(f"编辑后的项目数量: {len(items)}")
        for item in items:
            print(f"- {item.name}: {item.data}")
    
    sys.exit(app.exec())