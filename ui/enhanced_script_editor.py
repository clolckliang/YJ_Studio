from typing import Optional, Dict, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QGroupBox, QSplitter, QTextEdit, QCompleter,
    QFrame, QScrollBar, QApplication
)
from PySide6.QtCore import Qt, Signal, Slot, QStringListModel, QRect, QSize, QTimer
from PySide6.QtGui import (
    QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QPainter,
    QTextCursor, QKeySequence, QShortcut, QTextDocument, QFontMetrics
)
import re
import keyword


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    """Python语法高亮器"""
    
    def __init__(self, parent: QTextDocument = None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 定义颜色和格式
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#0000FF"))  # 蓝色
        self.keyword_format.setFontWeight(QFont.Weight.Bold)
        
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#008000"))  # 绿色
        
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#808080"))  # 灰色
        self.comment_format.setFontItalic(True)
        
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#FF6600"))  # 橙色
        
        self.function_format = QTextCharFormat()
        self.function_format.setForeground(QColor("#800080"))  # 紫色
        self.function_format.setFontWeight(QFont.Weight.Bold)
        
        self.class_format = QTextCharFormat()
        self.class_format.setForeground(QColor("#0080FF"))  # 浅蓝色
        self.class_format.setFontWeight(QFont.Weight.Bold)
        
        self.operator_format = QTextCharFormat()
        self.operator_format.setForeground(QColor("#FF0000"))  # 红色
        
        # Python关键字
        keywords = keyword.kwlist + ['self', 'cls', 'True', 'False', 'None']
        for word in keywords:
            pattern = f"\\b{word}\\b"
            self.highlighting_rules.append((pattern, self.keyword_format))
        
        # 字符串
        self.highlighting_rules.extend([
            ('".*?"', self.string_format),
            ("'.*?'", self.string_format),
            ('""".*?"""', self.string_format),
            ("'''.*?'''", self.string_format),
        ])
        
        # 数字
        self.highlighting_rules.append((r'\b\d+\.?\d*\b', self.number_format))
        
        # 函数定义
        self.highlighting_rules.append((r'\bdef\s+(\w+)', self.function_format))
        
        # 类定义
        self.highlighting_rules.append((r'\bclass\s+(\w+)', self.class_format))
        
        # 操作符
        operators = ['+', '-', '*', '/', '%', '=', '==', '!=', '<', '>', '<=', '>=']
        for op in operators:
            escaped_op = re.escape(op)
            self.highlighting_rules.append((escaped_op, self.operator_format))
        
        # 注释
        self.highlighting_rules.append((r'#.*', self.comment_format))
    
    def highlightBlock(self, text: str):
        """高亮文本块"""
        for pattern, format_obj in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                start, end = match.span()
                self.setFormat(start, end - start, format_obj)


class LineNumberArea(QWidget):
    """行号区域"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor
    
    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class EnhancedCodeEditor(QPlainTextEdit):
    """增强的代码编辑器，支持行号、语法高亮等功能"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 设置字体
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        
        # 创建行号区域
        self.line_number_area = LineNumberArea(self)
        
        # 连接信号
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        
        # 初始化
        self.update_line_number_area_width(0)
        self.highlight_current_line()
        
        # 设置语法高亮
        self.highlighter = PythonSyntaxHighlighter(self.document())
        
        # 设置代码补全
        self.setup_completer()
        
        # 设置快捷键
        self.setup_shortcuts()
        
        # 设置样式
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                selection-background-color: #3399FF;
                selection-color: #FFFFFF;
            }
        """)
    
    def setup_completer(self):
        """设置代码补全"""
        # Python内置函数和关键字
        completions = [
            # Python关键字
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'exec', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'not', 'or', 'pass', 'print', 'raise', 'return', 'try',
            'while', 'with', 'yield', 'True', 'False', 'None',
            # 常用内置函数
            'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'dir',
            'enumerate', 'eval', 'filter', 'float', 'format', 'hex',
            'input', 'int', 'isinstance', 'len', 'list', 'map', 'max',
            'min', 'open', 'ord', 'print', 'range', 'repr', 'round',
            'set', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
            # 常用模块
            'import', 'from', 'os', 'sys', 'time', 'datetime', 'json',
            'math', 'random', 're', 'collections', 'itertools'
        ]
        
        self.completer = QCompleter(completions, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)
    
    def setup_shortcuts(self):
        """设置快捷键"""
        # Ctrl+Space 触发代码补全
        completion_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        completion_shortcut.activated.connect(self.show_completion)
        
        # Ctrl+/ 注释/取消注释
        comment_shortcut = QShortcut(QKeySequence("Ctrl+/"), self)
        comment_shortcut.activated.connect(self.toggle_comment)
    
    def insert_completion(self, completion):
        """插入补全文本"""
        cursor = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfWord)
        cursor.insertText(completion[-extra:])
        self.setTextCursor(cursor)
    
    def show_completion(self):
        """显示代码补全"""
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        completion_prefix = cursor.selectedText()
        
        if len(completion_prefix) < 1:
            return
        
        self.completer.setCompletionPrefix(completion_prefix)
        popup = self.completer.popup()
        popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
        
        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) +
                   self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)
    
    def toggle_comment(self):
        """切换注释状态"""
        cursor = self.textCursor()
        
        # 如果有选中文本，对选中的行进行操作
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            start_line = cursor.blockNumber()
            cursor.setPosition(end)
            end_line = cursor.blockNumber()
        else:
            # 没有选中文本，只对当前行操作
            start_line = end_line = cursor.blockNumber()
        
        cursor.beginEditBlock()
        
        for line_num in range(start_line, end_line + 1):
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(line_num):
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
            
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            line_text = cursor.selectedText()
            
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            
            if line_text.strip().startswith('#'):
                # 取消注释
                if line_text.startswith('#'):
                    cursor.deleteChar()
                else:
                    # 找到第一个#并删除
                    pos = line_text.find('#')
                    if pos >= 0:
                        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, pos)
                        cursor.deleteChar()
            else:
                # 添加注释
                cursor.insertText('#')
        
        cursor.endEditBlock()
    
    def line_number_area_width(self):
        """计算行号区域宽度"""
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def update_line_number_area_width(self, new_block_count):
        """更新行号区域宽度"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        """更新行号区域"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
    
    def line_number_area_paint_event(self, event):
        """绘制行号"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(240, 240, 240))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor(120, 120, 120))
                painter.drawText(0, int(top), self.line_number_area.width(), 
                               self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
    
    def highlight_current_line(self):
        """高亮当前行"""
        extra_selections = []
        
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(Qt.GlobalColor.yellow).lighter(160)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        
        self.setExtraSelections(extra_selections)
    
    def keyPressEvent(self, event):
        """按键事件处理"""
        # 处理代码补全
        if self.completer and self.completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                event.ignore()
                return
        
        # 自动缩进
        if event.key() == Qt.Key.Key_Return:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
            line_text = cursor.selectedText()
            indent = len(line_text) - len(line_text.lstrip())
            
            super().keyPressEvent(event)
            
            # 添加相同的缩进
            if indent > 0:
                self.insertPlainText(' ' * indent)
            
            # 如果上一行以冒号结尾，增加额外缩进
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            prev_line = cursor.selectedText().strip()
            if prev_line.endswith(':'):
                self.insertPlainText('    ')  # 4个空格缩进
            
            return
        
        super().keyPressEvent(event)
        
        # 触发代码补全
        completion_prefix = self.text_under_cursor()
        if len(completion_prefix) >= 2 and event.text().isalnum():
            self.completer.setCompletionPrefix(completion_prefix)
            popup = self.completer.popup()
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
            
            cr = self.cursorRect()
            cr.setWidth(self.completer.popup().sizeHintForColumn(0) +
                       self.completer.popup().verticalScrollBar().sizeHint().width())
            self.completer.complete(cr)
    
    def text_under_cursor(self):
        """获取光标下的文本"""
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()


class EnhancedScriptingPanelWidget(QWidget):
    """增强的脚本面板，包含语法高亮、行号、代码补全等功能"""
    
    execute_script_requested = Signal(str)
    
    def __init__(self, main_window_ref, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window_ref = main_window_ref
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建脚本组
        script_group = QGroupBox("增强脚本编辑器 (Enhanced Script Editor)")
        group_layout = QVBoxLayout()
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 脚本输入区域
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(QLabel("Python脚本输入 (支持语法高亮、代码补全、行号显示):"))
        toolbar_layout.addStretch()
        
        # 功能按钮
        self.run_button = QPushButton("▶ 执行脚本")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.run_button.clicked.connect(self._on_run_script_clicked)
        
        self.clear_input_button = QPushButton("🗑 清空输入")
        self.clear_input_button.clicked.connect(self._clear_input)
        
        toolbar_layout.addWidget(self.run_button)
        toolbar_layout.addWidget(self.clear_input_button)
        
        input_layout.addLayout(toolbar_layout)
        
        # 增强的代码编辑器
        self.script_input_edit = EnhancedCodeEditor()
        self.script_input_edit.setPlaceholderText(
            "在此输入Python脚本...\n\n"
            "功能特性:\n"
            "• 语法高亮 - 自动高亮Python关键字、字符串、注释等\n"
            "• 行号显示 - 左侧显示行号，便于定位\n"
            "• 代码补全 - Ctrl+Space 触发自动补全\n"
            "• 智能缩进 - 自动处理Python缩进\n"
            "• 注释切换 - Ctrl+/ 快速注释/取消注释\n"
            "• 当前行高亮 - 高亮显示当前编辑行"
        )
        input_layout.addWidget(self.script_input_edit)
        
        # 脚本输出区域
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        
        output_toolbar_layout = QHBoxLayout()
        output_toolbar_layout.addWidget(QLabel("脚本输出/结果:"))
        output_toolbar_layout.addStretch()
        
        self.clear_output_button = QPushButton("🗑 清空输出")
        self.clear_output_button.clicked.connect(self._clear_output)
        output_toolbar_layout.addWidget(self.clear_output_button)
        
        output_layout.addLayout(output_toolbar_layout)
        
        self.script_output_edit = QPlainTextEdit()
        self.script_output_edit.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.script_output_edit.setFont(font)
        self.script_output_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #F5F5F5;
                color: #333333;
                border: 1px solid #CCCCCC;
            }
        """)
        output_layout.addWidget(self.script_output_edit)
        
        # 添加到分割器
        splitter.addWidget(input_widget)
        splitter.addWidget(output_widget)
        splitter.setSizes([300, 200])  # 设置初始比例
        
        group_layout.addWidget(splitter)
        script_group.setLayout(group_layout)
        layout.addWidget(script_group)
        
        # 添加使用提示
        tips_label = QLabel(
            "💡 <b>使用提示:</b> "
            "Ctrl+Space=代码补全 | Ctrl+/=注释切换 | Enter=智能缩进 | "
            "支持Python语法高亮和行号显示"
        )
        tips_label.setStyleSheet("""
            QLabel {
                background-color: #E3F2FD;
                color: #1976D2;
                padding: 8px;
                border-radius: 4px;
                border: 1px solid #BBDEFB;
            }
        """)
        layout.addWidget(tips_label)
    
    @Slot()
    def _on_run_script_clicked(self):
        """执行脚本按钮点击事件"""
        script_text = self.script_input_edit.toPlainText()
        if script_text.strip():
            self.execute_script_requested.emit(script_text)
        elif self.main_window_ref.error_logger:
            self.main_window_ref.error_logger.log_warning("尝试执行空脚本。")
            self.display_script_result("错误：脚本内容为空。")
    
    @Slot()
    def _clear_input(self):
        """清空输入区域"""
        self.script_input_edit.clear()
    
    @Slot()
    def _clear_output(self):
        """清空输出区域"""
        self.script_output_edit.clear()
    
    def display_script_result(self, result_text: str):
        """显示脚本执行结果"""
        self.script_output_edit.setPlainText(result_text)
    
    def get_config(self) -> Dict:
        """获取配置"""
        return {"current_script": self.script_input_edit.toPlainText()}
    
    def apply_config(self, config: Dict):
        """应用配置"""
        self.script_input_edit.setPlainText(config.get("current_script", ""))