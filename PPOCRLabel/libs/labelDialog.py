# Copyright (c) <2015-Present> Tzutalin
# Copyright (C) 2013  MIT, Computer Science and Artificial Intelligence Laboratory. Bryan Russell, Antonio Torralba,
# William T. Freeman. Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction, including without
# limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
# NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.utils import newIcon, labelValidator

BB = QDialogButtonBox


class LabelDialog(QDialog):
    def __init__(self, text="Enter object label", parent=None, listItem=None):
        super(LabelDialog, self).__init__(parent)

        # label
        self.edit_label = QLineEdit()  # OLD
        # self.edit = QTextEdit()
        self.edit_label.setText(text)
        # self.edit.setValidator(labelValidator()) # 验证有效性
        self.edit_label.editingFinished.connect(self.postProcess)

        # 自动填充
        model = QStringListModel()
        model.setStringList(listItem)
        completer = QCompleter()
        completer.setModel(model)
        self.edit_label.setCompleter(completer)

        labelLabel = QLabel("Label:")
        layout1 = QHBoxLayout()
        layout1.addWidget(labelLabel)
        layout1.addWidget(self.edit_label)

        # is_mark
        self.choice_group = QButtonGroup()
        self.choice1 = QRadioButton("False")
        self.choice2 = QRadioButton("True")
        self.choice_group.addButton(self.choice1, 0)
        self.choice_group.addButton(self.choice2, 1)

        self.choice1.setChecked(True)

        markLabel = QLabel("is_mark:")
        layout2 = QHBoxLayout()
        layout2.addWidget(markLabel)
        layout2.addWidget(self.choice1)
        layout2.addWidget(self.choice2)

        # content
        self.edit_content = QLineEdit()
        self.edit_content.editingFinished.connect(self.postProcess_)

        contentLabel = QLabel("content:")
        layout3 = QHBoxLayout()
        layout3.addWidget(contentLabel)
        layout3.addWidget(self.edit_content)

        layout = QVBoxLayout()
        layout.addItem(layout1)
        layout.addItem(layout2)
        layout.addItem(layout3)

        self.buttonBox = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon("done"))
        bb.button(BB.Cancel).setIcon(newIcon("undo"))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

        # if listItem is not None and len(listItem) > 0:
        #     self.listWidget = QListWidget(self)
        #     for item in listItem:
        #         self.listWidget.addItem(item)
        #     self.listWidget.itemClicked.connect(self.listItemClick)
        #     self.listWidget.itemDoubleClicked.connect(self.listItemDoubleClick)
        #     layout.addWidget(self.listWidget)

        self.setLayout(layout)

    def validate(self):
        try:
            if self.edit_label.text().trimmed():
                self.accept()
        except AttributeError:
            # PyQt5: AttributeError: 'str' object has no attribute 'trimmed'
            if self.edit_label.text().strip():
                self.accept()

    def postProcess(self):
        try:
            self.edit_label.setText(self.edit_label.text().trimmed())
            # print(self.edit.text())
        except AttributeError:
            # PyQt5: AttributeError: 'str' object has no attribute 'trimmed'
            self.edit_label.setText(self.edit_label.text())

    def postProcess_(self):
        try:
            self.edit_content.setText(self.edit_content.text().trimmed())
            # print(self.edit.text())
        except AttributeError:
            # PyQt5: AttributeError: 'str' object has no attribute 'trimmed'
            self.edit_content.setText(self.edit_content.text())

    def popUp(self, text="", is_mark=False, content="", move=True):
        self.edit_label.setText(text)
        # self.edit_label.setSelection(0, len(text))
        self.edit_label.setFocus(Qt.PopupFocusReason)

        self.choice_group.button(1 if is_mark else 0).setChecked(True)
        self.edit_content.setText(content)
        if move:
            cursor_pos = QCursor.pos()
            parent_bottomRight = self.parentWidget().geometry()
            max_x = (
                parent_bottomRight.x()
                + parent_bottomRight.width()
                - self.sizeHint().width()
            )
            max_y = (
                parent_bottomRight.y()
                + parent_bottomRight.height()
                - self.sizeHint().height()
            )
            max_global = self.parentWidget().mapToGlobal(QPoint(max_x, max_y))
            if cursor_pos.x() > max_global.x():
                cursor_pos.setX(max_global.x())
            if cursor_pos.y() > max_global.y():
                cursor_pos.setY(max_global.y())
            self.move(cursor_pos)
            # return self.edit_label.text() if self.exec_() else None
        if self.exec_():
            print(
                "label_info is",
                self.edit_label.text(),
                self.choice_group.checkedId(),
                self.edit_content.text(),
            )

            return (
                self.edit_label.text(),
                True if self.choice_group.checkedId() == 1 else False,
                self.edit_content.text() if self.edit_content.text() else None,
            )
        else:
            return None

    def listItemClick(self, tQListWidgetItem):
        try:
            text = tQListWidgetItem.text().trimmed()
        except AttributeError:
            # PyQt5: AttributeError: 'str' object has no attribute 'trimmed'
            text = tQListWidgetItem.text().strip()
        self.edit_label.setText(text)

    def listItemDoubleClick(self, tQListWidgetItem):
        self.listItemClick(tQListWidgetItem)
        self.validate()
