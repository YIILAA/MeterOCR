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
# !/usr/bin/env python
# -*- coding: utf-8 -*-
# pyrcc5 -o libs/resources.py resources.qrc
import argparse
import ast
import codecs
import json
import os.path
import platform
import subprocess
import sys
import xlrd
from functools import partial

from PyQt5.QtCore import (
    QSize,
    Qt,
    QPoint,
    QByteArray,
    QTimer,
    QFileInfo,
    QPointF,
    QProcess,
)
from PyQt5.QtGui import QImage, QCursor, QPixmap, QImageReader
from PyQt5.QtWidgets import (
    QMainWindow,
    QListWidget,
    QVBoxLayout,
    QToolButton,
    QHBoxLayout,
    QDockWidget,
    QWidget,
    QSlider,
    QGraphicsOpacityEffect,
    QMessageBox,
    QListView,
    QScrollArea,
    QWidgetAction,
    QApplication,
    QLabel,
    QGridLayout,
    QFileDialog,
    QListWidgetItem,
    QComboBox,
    QDialog,
    QAbstractItemView,
    QSizePolicy,
    QButtonGroup,
    QRadioButton,
    QLineEdit,
)

__dir__ = os.path.dirname(os.path.abspath(__file__))

sys.path.append(__dir__)
sys.path.append(os.path.abspath(os.path.join(__dir__, "../..")))
sys.path.append(os.path.abspath(os.path.join(__dir__, "../PaddleOCR")))
sys.path.append("..")

from paddleocr import PaddleOCR, PPStructure
from libs.constants import *
from libs.utils import *
from libs.labelColor import label_colormap
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR, DEFAULT_LOCK_COLOR
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.autoDialog import AutoDialog
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.templateRecDialog import templateRecDialog
from libs.ustr import ustr
from libs.hashableQListWidgetItem import HashableQListWidgetItem
from libs.editinlist import EditInList
from libs.unique_label_qlist_widget import UniqueLabelQListWidget
from libs.keyDialog import KeyDialog

__appname__ = "PPOCRLabel"

LABEL_COLORMAP = label_colormap()


class MainWindow(QMainWindow):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(
        self,
        lang="ch",
        gpu=False,
        default_filename=None,
        default_predefined_class_file=None,
        default_save_dir_0=None,
        default_save_dir_1=None,
    ):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)
        self.setWindowState(Qt.WindowMaximized)  # set window max
        self.activateWindow()  # PPOCRLabel goes to the front when activate

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings
        self.lang = lang

        # Load string bundle for i18n
        if lang not in ["ch", "en"]:
            lang = "en"
        self.stringBundle = StringBundle.getBundle(
            localeStr="zh-CN" if lang == "ch" else "en"
        )  # 'en'
        getStr = lambda strId: self.stringBundle.getString(strId)

        self.defaultSaveDir = [default_save_dir_0, default_save_dir_1]
        self.ocr = PaddleOCR(
            use_pdserving=False,
            use_angle_cls=True,
            det=True,
            cls=True,
            use_gpu=gpu,
            lang=lang,
            show_log=False,
        )

        if os.path.exists("./data/paddle.png"):
            result = self.ocr.ocr("./data/paddle.png", cls=True, det=True)

        # For loading all image under a directory
        self.mImgList = [[], []]  # 区分两个文件列表
        self.mImgList5 = []
        self.dirname = [None, None]  # 两个文件目录
        self.labelHist = []  # TODO
        self.lastOpenDir = [None, None]
        self.result_dic = []  # 当前操作文件存储的shape信息
        self.result_dic_locked = []
        # self.changeFileFolder = False # 好像没用
        self.haveAutoReced = False
        # self.labelFile = None # 好像没用
        self.currIndex = [0, 0]

        # Whether we need to save or not.
        self.dirty = [False, False]

        self.showMode = 0  # 当前canva上展示的类型 0/1
        self.operateMode = 0  # 操作类型

        self._noSelectionSlot = False
        self._beginner = True  # 什么用？
        self.screencastViewer = self.getAvailableScreencastViewer()
        self.screencast = "https://github.com/PaddlePaddle/PaddleOCR"

        # Load predefined classes to the list
        self.loadPredefinedClasses(default_predefined_class_file)  # 好像没用 待去除

        # Main widgets and related state.
        self.labelDialog = LabelDialog(
            parent=self, listItem=self.labelHist
        )  # TODO 添加字段
        self.autoDialog = AutoDialog(parent=self)

        self.itemsToShapes = {}
        self.shapesToItems = {}
        # 可能需要添加contentToShapes
        self.prevLabelText = getStr("tempLabel")
        self.noLabelText = getStr("nullLabel")
        self.model = "paddle"
        self.PPreader = None
        self.autoSaveNum = 5

        #  ================================= Left Area - Begin =================================
        templateLayout = QVBoxLayout()
        templateLayout.setContentsMargins(0, 0, 0, 0)

        #  ================== File List  ==================
        # self.templateFileListDock
        self.templateFileListWidget = QListWidget()
        self.templateFileListWidget.itemClicked.connect(
            partial(self.fileitemDoubleClicked, mode=0)
        )
        self.templateFileListWidget.setIconSize(QSize(25, 25))

        self.templateFileListName = getStr("templateFileList")
        self.templateFileListDock = QDockWidget(self.templateFileListName, self)
        self.templateFileListDock.setWidget(self.templateFileListWidget)

        self.templateFileListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        #  ================== Buttons  ==================
        # templateToolBoxContainer
        self.newButton_0 = QToolButton()
        self.newButton_0.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.checkButton_0 = QToolButton()
        self.checkButton_0.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.saveLabelButton_0 = QToolButton()
        self.saveLabelButton_0.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        templateToolBox = QGridLayout()
        templateToolBox.addWidget(self.newButton_0, 0, 0, 1, 1)
        templateToolBox.addWidget(self.checkButton_0, 0, 1, 1, 1)
        templateToolBox.addWidget(self.saveLabelButton_0, 1, 0, 1, 2)
        templateToolBoxContainer = QWidget()
        templateToolBoxContainer.setLayout(templateToolBox)

        #  ================== Result List  ==================
        # templateResultListContainer <- templateResultListBox <- (templateIndexListDock + templateLabelListDock)
        templateResultListBox = QHBoxLayout()

        # ===== Index List =====
        # Create and add a widget for showing current label item index
        self.templateIndexList = QListWidget()
        self.templateIndexList.setMaximumSize(30, 16777215)  # limit max width
        self.templateIndexList.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )  # no editable
        self.templateIndexList.itemSelectionChanged.connect(
            partial(self.indexSelectionChanged, mode=0)
        )
        self.templateIndexList.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )  # no scroll Bar
        self.templateIndexListDock = QDockWidget("No.", self)
        self.templateIndexListDock.setWidget(self.templateIndexList)
        self.templateIndexListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        # add to templateResultListBox
        templateResultListBox.addWidget(self.templateIndexListDock, 1)
        # no margin between two boxes
        templateResultListBox.setSpacing(0)

        # ===== Label List =====
        # Create and add a widget for showing current label items
        self.templateLabelList = EditInList()

        self.templateLabelList.itemSelectionChanged.connect(
            partial(self.labelSelectionChanged, mode=0)
        )
        self.templateLabelList.clicked.connect(self.templateLabelList.item_clicked)

        # Connect to itemChanged to detect checkbox changes.
        self.templateLabelList.itemChanged.connect(self.labelItemChanged)  # TODO

        self.templateLabelListDockName = getStr("templateLabel")
        self.templateLabelListDock = QDockWidget(self.templateLabelListDockName, self)
        self.templateLabelListDock.setWidget(self.templateLabelList)
        self.templateLabelListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        # add to templateResultListBox
        templateResultListBox.addWidget(
            self.templateLabelListDock, 10
        )  # label list is wider than index list

        # ===== ResultList 整体设置 =====
        # enable labelList drag_drop to adjust bbox order
        # 设置选择模式为单选
        self.templateLabelList.setSelectionMode(QAbstractItemView.SingleSelection)
        # 启用拖拽
        self.templateLabelList.setDragEnabled(True)
        # 设置接受拖放
        self.templateLabelList.viewport().setAcceptDrops(True)
        # 设置显示将要被放置的位置
        self.templateLabelList.setDropIndicatorShown(True)
        # 设置拖放模式为移动项目，如果不设置，默认为复制项目
        self.templateLabelList.setDragDropMode(QAbstractItemView.InternalMove)
        # 触发放置
        self.templateLabelList.model().rowsMoved.connect(self.drag_drop_happened)

        templateResultListContainer = QWidget()
        templateResultListContainer.setLayout(templateResultListBox)

        # labelList indexList同步滚动
        self.templateLabelListBar = self.templateLabelList.verticalScrollBar()
        self.templateIndexListBar = self.templateIndexList.verticalScrollBar()

        self.templateLabelListBar.valueChanged.connect(
            partial(self.move_scrollbar, mode=0)
        )
        self.templateIndexListBar.valueChanged.connect(
            partial(self.move_scrollbar, mode=0)
        )

        #  ================== 左侧整体的设置  ==================
        # templateLayout 添加三个子组件
        templateLayout.addWidget(self.templateFileListDock)
        templateLayout.addWidget(templateToolBoxContainer)
        templateLayout.addWidget(templateResultListContainer)

        templateContainer = QWidget()
        templateContainer.setLayout(templateLayout)
        self.templateDockName = getStr("template")
        self.templateDock = QDockWidget(self.templateDockName, self)
        self.templateDock.setObjectName(getStr("template"))
        self.templateDock.setWidget(templateContainer)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.templateDock)

        # self.templateDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        #  ================================= Right Area - Begin =================================
        recogLayout = QVBoxLayout()
        recogLayout.setContentsMargins(0, 0, 0, 0)

        #  ================== File List  ==================
        # self.recogFileListDock
        self.recogFileListWidget = QListWidget()
        self.recogFileListWidget.itemClicked.connect(
            partial(self.fileitemDoubleClicked, mode=1)
        )
        self.recogFileListWidget.setIconSize(QSize(25, 25))

        self.recogFileListName = getStr("recogFileList")
        self.recogFileListDock = QDockWidget(self.recogFileListName, self)
        self.recogFileListDock.setWidget(self.recogFileListWidget)

        self.recogFileListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        # ================== current template  ==================
        # self.templateRecogBoxContainer
        templateRecogBox = QVBoxLayout()

        self.showText = QLabel()
        self.showText.setText(getStr("templateRecogHint"))

        templateRecogSublayout = QHBoxLayout()
        self.templateFileName = QLineEdit()
        self.templateRecogButton = QToolButton()
        self.templateRecogButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.templateRecogButton.setIcon(newIcon("Auto"))  # TODO change icon
        templateRecogSublayout.addWidget(self.templateFileName)
        templateRecogSublayout.addWidget(self.templateRecogButton)

        templateRecogBox.addWidget(self.showText)
        templateRecogBox.addItem(templateRecogSublayout)

        self.templateRecogBoxContainer = QWidget()
        self.templateRecogBoxContainer.setLayout(templateRecogBox)

        self.templateFileName.textChanged.connect(self.on_templateFileName_input)

        #  ================== Buttons  ==================
        # recogToolBoxContainer
        # 自动识别
        self.AutoRecognition = QToolButton()
        self.AutoRecognition.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.AutoRecognition.setIcon(newIcon("Auto"))

        # 新建矩形
        self.newButton_1 = QToolButton()
        self.newButton_1.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 重新识别
        self.reRecogButton = QToolButton()
        self.reRecogButton.setIcon(newIcon("reRec", 30))
        self.reRecogButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # check当前图像
        self.checkButton_1 = QToolButton()
        self.checkButton_1.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 保存识别结果
        self.saveLabelButton_1 = QToolButton()
        self.saveLabelButton_1.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # TODO 设置相应的函数，或者用一样的saveButton，根据模式判断？还是分开吧，可以选择保存一种或都保存

        # self.DelButton = QToolButton()
        # self.DelButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        recogToolBox = QGridLayout()
        recogToolBox.addWidget(self.AutoRecognition, 0, 0, 1, 1)
        recogToolBox.addWidget(self.newButton_1, 0, 1, 1, 1)
        recogToolBox.addWidget(self.reRecogButton, 1, 0, 1, 1)
        recogToolBox.addWidget(self.checkButton_1, 1, 1, 1, 1)
        recogToolBox.addWidget(self.saveLabelButton_1, 2, 0, 1, 1)
        recogToolBoxContainer = QWidget()
        recogToolBoxContainer.setLayout(recogToolBox)

        #  ================== Result List  ==================
        # recogResultListContainer <- recogResultListBox <- (recogIndexListDock + recogLabelListDock + recogContentListDock)
        recogResultListBox = QHBoxLayout()

        # ===== Index List =====
        # Create and add a widget for showing current label item index
        self.recogIndexList = QListWidget()
        self.recogIndexList.setMaximumSize(30, 16777215)  # limit max width
        self.recogIndexList.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )  # no editable
        self.recogIndexList.itemSelectionChanged.connect(
            partial(self.indexSelectionChanged, mode=1)
        )
        self.recogIndexList.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )  # no scroll Bar
        self.recogIndexListDock = QDockWidget("No.", self)
        self.recogIndexListDock.setWidget(self.recogIndexList)
        self.recogIndexListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        # add to recogResultListBox
        recogResultListBox.addWidget(self.recogIndexListDock, 1)
        # no margin between two boxes
        recogResultListBox.setSpacing(0)

        # ===== Label List =====
        # Create and add a widget for showing current label items
        self.recogLabelList = QListWidget()
        # 不可编辑
        self.recogLabelList.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recogLabelList.itemSelectionChanged.connect(
            partial(self.labelSelectionChanged, mode=1)
        )
        self.recogLabelList.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )  # no scroll Bar

        self.recogLabelListDockName = getStr("recogLabel")
        self.recogLabelListDock = QDockWidget(self.recogLabelListDockName, self)
        self.recogLabelListDock.setWidget(self.recogLabelList)
        self.recogLabelListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        # add to recogResultListBox
        recogResultListBox.addWidget(self.recogLabelListDock, 5)

        # ===== Content List =====
        self.recogContentList = EditInList()

        # TODO 方法实现 self.contentSelectionChanged
        self.recogContentList.itemSelectionChanged.connect(self.contentSelectionChanged)
        self.recogContentList.clicked.connect(self.recogContentList.item_clicked)

        # Connect to itemChanged to detect checkbox changes.
        # TODO 方法实现 self.contentItemChanged
        self.recogContentList.itemChanged.connect(self.contentItemChanged)

        self.recogContentListDockName = getStr("recogContent")
        self.recogContentListDock = QDockWidget(self.recogContentListDockName, self)
        self.recogContentListDock.setWidget(self.recogContentList)
        self.recogContentListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        # add to recogResultListBox
        recogResultListBox.addWidget(self.recogContentListDock, 5)

        # ===== ResultList 整体设置 =====
        # TODO 当前设置在recogLabelList 是否设置在Index列
        # enable labelList drag_drop to adjust bbox order
        # 设置选择模式为单选
        self.recogLabelList.setSelectionMode(QAbstractItemView.SingleSelection)
        # 启用拖拽
        self.recogLabelList.setDragEnabled(True)
        # 设置接受拖放
        self.recogLabelList.viewport().setAcceptDrops(True)
        # 设置显示将要被放置的位置
        self.recogLabelList.setDropIndicatorShown(True)
        # 设置拖放模式为移动项目，如果不设置，默认为复制项目
        self.recogLabelList.setDragDropMode(QAbstractItemView.InternalMove)
        # 触发放置
        self.recogLabelList.model().rowsMoved.connect(self.drag_drop_happened)

        recogResultListContainer = QWidget()
        recogResultListContainer.setLayout(recogResultListBox)

        # labelList indexList contentList 同步滚动
        self.recogIndexListBar = self.recogIndexList.verticalScrollBar()
        self.recogLabelListBar = self.recogLabelList.verticalScrollBar()
        self.recogContentListBar = self.recogContentList.verticalScrollBar()

        self.recogIndexListBar.valueChanged.connect(
            partial(self.move_scrollbar, mode=1)
        )
        self.recogLabelListBar.valueChanged.connect(
            partial(self.move_scrollbar, mode=1)
        )
        self.recogContentListBar.valueChanged.connect(
            partial(self.move_scrollbar, mode=1)
        )

        #  ================== 右侧整体的设置  ==================
        # recogLayout 添加四个子组件
        recogLayout.addWidget(self.recogFileListDock)
        recogLayout.addWidget(self.templateRecogBoxContainer)
        recogLayout.addWidget(recogToolBoxContainer)
        recogLayout.addWidget(recogResultListContainer)

        recogContainer = QWidget()
        recogContainer.setLayout(recogLayout)
        self.recogDock = QDockWidget("recog", self)
        self.recogDock.setObjectName(getStr("recog"))
        self.recogDock.setWidget(recogContainer)
        self.addDockWidget(Qt.RightDockWidgetArea, self.recogDock)

        # self.recogDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        #  ================== Zoom Bar  ==================
        self.imageSlider = QSlider(Qt.Horizontal)
        self.imageSlider.valueChanged.connect(self.CanvasSizeChange)
        self.imageSlider.setMinimum(-9)
        self.imageSlider.setMaximum(510)
        self.imageSlider.setSingleStep(1)
        self.imageSlider.setTickPosition(QSlider.TicksBelow)
        self.imageSlider.setTickInterval(1)

        op = QGraphicsOpacityEffect()
        op.setOpacity(0.2)
        self.imageSlider.setGraphicsEffect(op)

        self.imageSlider.setStyleSheet("background-color:transparent")
        self.imageSliderDock = QDockWidget(getStr("ImageResize"), self)
        self.imageSliderDock.setObjectName(getStr("IR"))
        self.imageSliderDock.setWidget(self.imageSlider)
        self.imageSliderDock.setFeatures(QDockWidget.DockWidgetFloatable)
        self.imageSliderDock.setAttribute(Qt.WA_TranslucentBackground)
        self.addDockWidget(Qt.RightDockWidgetArea, self.imageSliderDock)

        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)
        self.zoomWidgetValue = self.zoomWidget.value()

        self.msgBox = QMessageBox()

        #  ================== Thumbnail ==================
        hlayout = QHBoxLayout()
        m = (0, 0, 0, 0)
        hlayout.setSpacing(0)
        hlayout.setContentsMargins(*m)
        self.preButton = QToolButton()
        self.preButton.setIcon(newIcon("prev", 40))
        self.preButton.setIconSize(QSize(40, 100))
        self.preButton.clicked.connect(self.openPrevImg)
        self.preButton.setStyleSheet("border: none;")
        self.preButton.setShortcut("a")
        self.iconlist = QListWidget()  # canvas下面的thumbnail
        self.iconlist.setViewMode(QListView.IconMode)
        self.iconlist.setFlow(QListView.TopToBottom)
        self.iconlist.setSpacing(10)
        self.iconlist.setIconSize(QSize(50, 50))
        self.iconlist.setMovement(QListView.Static)
        self.iconlist.setResizeMode(QListView.Adjust)
        self.iconlist.itemClicked.connect(self.iconitemDoubleClicked)
        self.iconlist.setStyleSheet(
            "QListWidget{ background-color:transparent; border: none;}"
        )
        self.iconlist.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nextButton = QToolButton()
        self.nextButton.setIcon(newIcon("next", 40))
        self.nextButton.setIconSize(QSize(40, 100))
        self.nextButton.setStyleSheet("border: none;")
        self.nextButton.clicked.connect(partial(self.openNextImg, self.showMode))
        self.nextButton.setShortcut("d")

        hlayout.addWidget(self.preButton)
        hlayout.addWidget(self.iconlist)
        hlayout.addWidget(self.nextButton)

        iconListContainer = QWidget()
        iconListContainer.setLayout(hlayout)
        iconListContainer.setFixedHeight(100)

        #  ================== Canvas ==================
        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoomRequest)
        self.canvas.setDrawingShapeToSquare(settings.get(SETTING_DRAW_SQUARE, False))

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar(),
        }
        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(partial(self.newShape, False, mode=self.showMode))
        # self.canvas.shapeMoved.connect(self.updateBoxlist)  # self.setDirty
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        #  ================== Buttons ==================
        self.modeButtonGroup = QButtonGroup()
        self.modeButton_0 = QRadioButton(getStr("defineTemplate"))
        self.modeButton_1 = QRadioButton(getStr("beginRecognize"))
        self.modeButtonGroup.addButton(self.modeButton_0, 0)
        self.modeButtonGroup.addButton(self.modeButton_1, 1)
        self.modeButtonGroup.buttonClicked.connect(self.modeChanged)

        self.modeButton_0.setChecked(True)

        modeButtonLayout = QHBoxLayout()
        modeButtonLayout.addWidget(self.modeButton_0)
        modeButtonLayout.addWidget(self.modeButton_1)

        centerLayout = QVBoxLayout()
        centerLayout.setContentsMargins(0, 0, 0, 0)
        centerLayout.addItem(modeButtonLayout)
        centerLayout.addWidget(scroll)
        centerLayout.addWidget(iconListContainer, 0, Qt.AlignCenter)
        centerContainer = QWidget()
        centerContainer.setLayout(centerLayout)

        self.setCentralWidget(centerContainer)

        #  ================== Actions ==================
        action = partial(newAction, self)  # text, slot, ...
        quit = action(getStr("quit"), self.close, "Ctrl+Q", "quit", getStr("quitApp"))

        # 区别两个目录
        # opendir = action(
        #     getStr("openDir"), self.openDirDialog, "Ctrl+u", "open", getStr("openDir")
        # )

        openDir_0 = action(
            getStr("openDir_0"),
            partial(self.openDirDialog, mode=0),
            "Ctrl+u",
            "open",
            getStr("openDir_0"),
        )

        openDir_1 = action(
            getStr("openDir_1"),
            partial(self.openDirDialog, mode=1),
            "Ctrl+u",
            "open",
            getStr("openDir_1"),
        )

        # 区别两种保存，不同的目录
        # 这个是保存单个文件的label？
        # save = action(
        #     getStr("save"),
        #     self.saveFile,
        #     "Ctrl+V",
        #     "verify",
        #     getStr("saveDetail"),
        #     enabled=False,
        # )
        check_0 = action(
            getStr("check"),
            partial(self.saveFile, mode=0),
            "Ctrl+V",
            "verify",
            getStr("checkFile"),
            enabled=False,
        )

        check_1 = action(
            getStr("check"),
            partial(self.saveFile, mode=1),
            "Ctrl+V",
            "verify",
            getStr("checkFile"),
            enabled=False,
        )

        alcm = action(
            getStr("choosemodel"),
            self.autolcm,
            "Ctrl+M",
            "next",
            getStr("tipchoosemodel"),
        )

        deleteImg = action(
            getStr("deleteImg"),
            self.deleteImg,
            "Ctrl+Shift+D",
            "close",
            getStr("deleteImgDetail"),
            enabled=True,
        )

        resetAll = action(
            getStr("resetAll"),
            self.resetAll,
            None,
            "resetall",
            getStr("resetAllDetail"),
        )

        color1 = action(
            getStr("boxLineColor"),
            self.chooseColor,
            "Ctrl+L",
            "color_line",
            getStr("boxLineColorDetail"),
        )

        createMode = action(
            getStr("crtBox"),
            self.setCreateMode,
            "w",
            "new",
            getStr("crtBoxDetail"),
            enabled=False,
        )
        editMode = action(
            "&Edit\nRectBox",
            self.setEditMode,
            "Ctrl+J",
            "edit",
            "Move and edit Boxs",
            enabled=False,
        )

        create = action(
            getStr("crtBox"),
            self.createShape,
            "w",
            "objects",
            getStr("crtBoxDetail"),
            enabled=False,
        )

        delete = action(
            getStr("delBox"),
            self.deleteSelectedShape,
            "backspace",
            "delete",
            getStr("delBoxDetail"),
            enabled=False,
        )

        copy = action(
            getStr("dupBox"),
            self.copySelectedShape,
            "Ctrl+C",
            "copy",
            getStr("dupBoxDetail"),
            enabled=False,
        )

        hideAll = action(
            getStr("hideBox"),
            partial(self.togglePolygons, False),
            "Ctrl+H",
            "hide",
            getStr("hideAllBoxDetail"),
            enabled=False,
        )
        showAll = action(
            getStr("showBox"),
            partial(self.togglePolygons, True),
            "Ctrl+A",
            "hide",
            getStr("showAllBoxDetail"),
            enabled=False,
        )

        help = action(
            getStr("tutorial"),
            self.showTutorialDialog,
            None,
            "help",
            getStr("tutorialDetail"),
        )
        showInfo = action(
            getStr("info"), self.showInfoDialog, None, "help", getStr("info")
        )
        showSteps = action(
            getStr("steps"), self.showStepsDialog, None, "help", getStr("steps")
        )
        showKeys = action(
            getStr("keys"), self.showKeysDialog, None, "help", getStr("keys")
        )

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            "Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas."
            % (fmtShortcut("Ctrl+[-+]"), fmtShortcut("Ctrl+Wheel"))
        )
        self.zoomWidget.setEnabled(False)

        zoomIn = action(
            getStr("zoomin"),
            partial(self.addZoom, 10),
            "Ctrl++",
            "zoom-in",
            getStr("zoominDetail"),
            enabled=False,
        )
        zoomOut = action(
            getStr("zoomout"),
            partial(self.addZoom, -10),
            "Ctrl+-",
            "zoom-out",
            getStr("zoomoutDetail"),
            enabled=False,
        )
        zoomOrg = action(
            getStr("originalsize"),
            partial(self.setZoom, 100),
            "Ctrl+=",
            "zoom",
            getStr("originalsizeDetail"),
            enabled=False,
        )
        fitWindow = action(
            getStr("fitWin"),
            self.setFitWindow,
            "Ctrl+F",
            "fit-window",
            getStr("fitWinDetail"),
            checkable=True,
            enabled=False,
        )
        fitWidth = action(
            getStr("fitWidth"),
            self.setFitWidth,
            "Ctrl+Shift+F",
            "fit-width",
            getStr("fitWidthDetail"),
            checkable=True,
            enabled=False,
        )
        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut, zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        #  ================== New Actions ==================

        # 编辑对象是当前展示图像 当前选中shape
        edit = action(
            getStr("editLabel"),
            self.editLabel,
            "Ctrl+E",
            "edit",
            getStr("editLabelDetail"),
            enabled=False,
        )

        AutoRec = action(
            getStr("autoRecognition"),
            self.autoRecognition,
            "",
            "Auto",
            getStr("autoRecognition"),
            enabled=True,
        )

        templateRec = action(
            getStr("templateRecognition"),
            self.templateRecognition,
            "",
            "tempRec",
            getStr("templateRecognition"),
            enabled=False,
        )

        reRec = action(
            getStr("reRecognition"),
            self.reRecognition,
            "Ctrl+Shift+R",
            "reRec",
            getStr("reRecognition"),
            enabled=False,
        )

        singleRere = action(
            getStr("singleRe"),
            self.singleRerecognition,
            "Ctrl+R",
            "reRec",
            getStr("singleRe"),
            enabled=False,
        )

        createpoly = action(
            getStr("creatPolygon"),
            self.createPolygon,
            "q",
            "new",
            getStr("creatPolygon"),
            enabled=False,
        )

        cellreRec = action(
            getStr("cellreRecognition"),
            self.cellreRecognition,
            "",
            "reRec",
            getStr("cellreRecognition"),
            enabled=False,
        )

        # # 保存crop的图像和单个结果
        # saveRec = action(
        #     getStr("saveRec"),
        #     self.saveRecResult,
        #     "",
        #     "save",
        #     getStr("saveRec"),
        #     enabled=False,
        # )

        # 保存整个目录
        # 区分两个目录
        # saveLabel = action(
        #     getStr("saveLabel"),
        #     self.saveLabelFile,
        #     "Ctrl+S",
        #     "save",
        #     getStr("saveLabel"),
        #     enabled=False,
        # )
        saveLabel_0 = action(
            getStr("saveLabel_0"),
            partial(self.saveLabelFile, mode=0),
            "Ctrl+S",
            "save",
            getStr("saveLabel_0"),
            enabled=False,
        )

        saveLabel_1 = action(
            getStr("saveLabel_1"),
            partial(self.saveLabelFile, mode=1),
            "Ctrl+S",
            "save",
            getStr("saveLabel_1"),
            enabled=False,
        )

        undoLastPoint = action(
            getStr("undoLastPoint"),
            self.canvas.undoLastPoint,
            "Ctrl+Z",
            "undo",
            getStr("undoLastPoint"),
            enabled=False,
        )

        rotateLeft = action(
            getStr("rotateLeft"),
            partial(self.rotateImgAction, 1),
            "Ctrl+Alt+L",
            "rotateLeft",
            getStr("rotateLeft"),
            enabled=False,
        )

        rotateRight = action(
            getStr("rotateRight"),
            partial(self.rotateImgAction, -1),
            "Ctrl+Alt+R",
            "rotateRight",
            getStr("rotateRight"),
            enabled=False,
        )

        undo = action(
            getStr("undo"),
            self.undoShapeEdit,
            "Ctrl+Z",
            "undo",
            getStr("undo"),
            enabled=False,
        )

        lock = action(
            getStr("lockBox"),
            self.lockSelectedShape,
            None,
            "lock",
            getStr("lockBoxDetail"),
            enabled=False,
        )

        # self.editButton.setDefaultAction(edit)
        # self.newButton.setDefaultAction(create)
        # self.createpolyButton.setDefaultAction(createpoly)
        # self.DelButton.setDefaultAction(deleteImg)
        # self.SaveButton.setDefaultAction(save)
        # self.saveButton.setDefaultAction(save)  # TODO 保存单个文件
        # self.saveRecogButton.setDefaultAction() # TODO
        # self.AutoRecognition.setDefaultAction(AutoRec)
        # self.reRecogButton.setDefaultAction(reRec)
        # self.tableRecButton.setDefaultAction(tableRec)
        # self.preButton.setDefaultAction(openPrevImg)
        # self.nextButton.setDefaultAction(openNextImg)

        self.newButton_0.setDefaultAction(create)
        self.checkButton_0.setDefaultAction(check_0)
        self.saveLabelButton_0.setDefaultAction(saveLabel_0)

        self.newButton_1.setDefaultAction(create)
        self.checkButton_1.setDefaultAction(check_1)
        self.saveLabelButton_1.setDefaultAction(saveLabel_1)
        self.AutoRecognition.setDefaultAction(AutoRec)
        self.reRecogButton.setDefaultAction(reRec)
        self.templateRecogButton.setDefaultAction(templateRec)

        #  ================== Zoom layout ==================
        zoomLayout = QHBoxLayout()
        zoomLayout.addStretch()
        self.zoominButton = QToolButton()
        self.zoominButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoominButton.setDefaultAction(zoomIn)
        self.zoomoutButton = QToolButton()
        self.zoomoutButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoomoutButton.setDefaultAction(zoomOut)
        self.zoomorgButton = QToolButton()
        self.zoomorgButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoomorgButton.setDefaultAction(zoomOrg)
        zoomLayout.addWidget(self.zoominButton)
        zoomLayout.addWidget(self.zoomorgButton)
        zoomLayout.addWidget(self.zoomoutButton)

        zoomContainer = QWidget()
        zoomContainer.setLayout(zoomLayout)
        zoomContainer.setGeometry(0, 0, 30, 150)

        shapeLineColor = action(
            getStr("shapeLineColor"),
            self.chshapeLineColor,
            icon="color_line",
            tip=getStr("shapeLineColorDetail"),
            enabled=False,
        )
        shapeFillColor = action(
            getStr("shapeFillColor"),
            self.chshapeFillColor,
            icon="color",
            tip=getStr("shapeFillColorDetail"),
            enabled=False,
        )

        # Label list context menu.
        labelMenu = QMenu()
        addActions(labelMenu, (edit, delete))

        # # 在labelList上右击，触发 `popLabelListMenu` 函数以显示相应的菜单内容。
        # self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.labelList.customContextMenuRequested.connect(self.popLabelListMenu)

        # Draw squares/rectangles
        self.drawSquaresOption = QAction(getStr("drawSquares"), self)
        self.drawSquaresOption.setCheckable(True)
        self.drawSquaresOption.setChecked(settings.get(SETTING_DRAW_SQUARE, False))
        self.drawSquaresOption.triggered.connect(self.toogleDrawSquare)

        # Store actions for further handling.
        self.actions = struct(
            check_0=check_0,
            check_1=check_1,
            resetAll=resetAll,
            deleteImg=deleteImg,
            lineColor=color1,
            create=create,
            createpoly=createpoly,
            # tableRec=tableRec,
            delete=delete,
            edit=edit,
            copy=copy,
            # saveRec=saveRec,
            singleRere=singleRere,
            AutoRec=AutoRec,
            templateRec=templateRec,
            reRec=reRec,
            cellreRec=cellreRec,
            createMode=createMode,
            editMode=editMode,
            shapeLineColor=shapeLineColor,
            shapeFillColor=shapeFillColor,
            zoom=zoom,
            zoomIn=zoomIn,
            zoomOut=zoomOut,
            zoomOrg=zoomOrg,
            fitWindow=fitWindow,
            fitWidth=fitWidth,
            zoomActions=zoomActions,
            saveLabel_0=saveLabel_0,
            saveLabel_1=saveLabel_1,
            undo=undo,
            undoLastPoint=undoLastPoint,
            # open_dataset_dir=open_dataset_dir,
            rotateLeft=rotateLeft,
            rotateRight=rotateRight,
            lock=lock,
            # exportJSON=exportJSON,
            fileMenuActions=(
                openDir_0,
                saveLabel_0,
                openDir_1,
                saveLabel_1,
                resetAll,
                quit,
            ),
            beginner=(),
            advanced=(),
            editMenu=(
                createpoly,
                edit,
                copy,
                delete,
                singleRere,
                cellreRec,
                None,
                undo,
                undoLastPoint,
                None,
                rotateLeft,
                rotateRight,
                None,
                color1,
                self.drawSquaresOption,
                lock,
            ),
            beginnerContext=(
                create,
                # createpoly,
                edit,
                copy,
                delete,
                singleRere,
                cellreRec,
                rotateLeft,
                rotateRight,
                lock,
            ),
            advancedContext=(
                createMode,
                editMode,
                edit,
                copy,
                delete,
                shapeLineColor,
                shapeFillColor,
            ),
            onLoadActive=(create, createpoly, createMode, editMode),
            onShapesPresent=(hideAll, showAll),
        )

        # menus
        self.menus = struct(
            file=self.menu("&" + getStr("mfile")),
            edit=self.menu("&" + getStr("medit")),
            view=self.menu("&" + getStr("mview")),
            autolabel=self.menu("&PaddleOCR"),
            help=self.menu("&" + getStr("mhelp")),
            recentFiles=QMenu("Open &Recent"),
            labelList=labelMenu,  # 在labelList右击触发的菜单栏
        )

        self.lastLabel = None
        # Add option to enable/disable labels being displayed at the top of bounding boxes
        self.displayLabelOption = QAction(getStr("displayLabel"), self)
        self.displayLabelOption.setShortcut("Ctrl+Shift+P")
        self.displayLabelOption.setCheckable(True)
        self.displayLabelOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.displayLabelOption.triggered.connect(self.togglePaintLabelsOption)

        # Add option to enable/disable box index being displayed at the top of bounding boxes
        self.displayIndexOption = QAction(getStr("displayIndex"), self)
        self.displayIndexOption.setCheckable(True)
        self.displayIndexOption.setChecked(settings.get(SETTING_PAINT_INDEX, False))
        self.displayIndexOption.triggered.connect(self.togglePaintIndexOption)

        self.labelDialogOption = QAction(getStr("labelDialogOption"), self)
        self.labelDialogOption.setShortcut("Ctrl+Shift+L")
        self.labelDialogOption.setCheckable(True)
        self.labelDialogOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.displayIndexOption.setChecked(settings.get(SETTING_PAINT_INDEX, False))
        self.labelDialogOption.triggered.connect(self.speedChoose)

        self.autoSaveOption = QAction(getStr("autoSaveMode"), self)
        self.autoSaveOption.setCheckable(True)
        self.autoSaveOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.displayIndexOption.setChecked(settings.get(SETTING_PAINT_INDEX, False))
        self.autoSaveOption.triggered.connect(self.autoSaveFunc)

        addActions(
            self.menus.file,
            (
                openDir_0,
                saveLabel_0,
                None,
                openDir_1,
                saveLabel_1,
                None,
                resetAll,
                deleteImg,
                quit,
            ),
        )

        addActions(self.menus.help, (showKeys, showSteps, showInfo))
        addActions(
            self.menus.view,
            (
                self.displayLabelOption,
                self.displayIndexOption,
                self.labelDialogOption,
                None,
                hideAll,
                showAll,
                None,
                zoomIn,
                zoomOut,
                zoomOrg,
                None,
                fitWindow,
                fitWidth,
            ),
        )

        addActions(self.menus.autolabel, (AutoRec, reRec, cellreRec, alcm, None, help))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)

        self.statusBar().showMessage("%s started." % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filePath = ustr(default_filename)
        self.lastOpenDir = [None, None]
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        # ==== new =====
        self.PPlabelpath = ["", ""]
        self.PPlabel = [{}, {}]  # 每个字典里时(file:label)对
        self.fileStatepath = ["", ""]
        self.fileStatedict = [{}, {}]
        self.Cachelabelpath = None  # 仅对于recognition文件列表
        self.Cachelabel = {}

        # Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(SETTING_RECENT_FILES)
                self.recentFiles = [ustr(i) for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(
                    SETTING_RECENT_FILES
                )

        size = settings.get(SETTING_WIN_SIZE, QSize(1200, 800))

        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)
        self.move(position)
        # saveDir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.lastOpenDir[0] = ustr(settings.get(SETTING_LAST_OPEN_DIR_0, None))
        self.lastOpenDir[1] = ustr(settings.get(SETTING_LAST_OPEN_DIR_1, None))

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.lineColor = QColor(
            settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR)
        )
        Shape.fill_color = self.fillColor = QColor(
            settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR)
        )
        self.canvas.setDrawingColor(self.lineColor)
        # Add chris
        Shape.difficult = self.difficult

        # ADD:
        # Populate the File menu dynamically.
        self.updateFileMenu()

        # TODO
        # Since loading the file may take some time, make sure it runs in the background.
        if self.filePath and os.path.isdir(self.filePath):
            self.queueEvent(partial(self.importDirImages, self.filePath or ""))
        elif self.filePath:
            self.queueEvent(partial(self.loadFile, self.filePath or ""))

        self.keyDialog = None

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # Display cursor coordinates at the right of status bar
        self.labelCoordinates = QLabel("")
        self.statusBar().addPermanentWidget(self.labelCoordinates)

        # Open Dir if deafult file
        if self.filePath and os.path.isdir(self.filePath):
            self.openDirDialog(dirpath=self.filePath, silent=True)

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.canvas.setDrawingShapeToSquare(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            # Draw rectangle if Ctrl is pressed
            self.canvas.setDrawingShapeToSquare(True)

    def noShapes(self):
        return not self.itemsToShapes

    def populateModeActions(self):
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        self.menus.edit.clear()
        actions = (
            self.actions.create,
        )  # if self.beginner() else (self.actions.createMode, self.actions.editMode)
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def setDirty(self, mode=0):
        self.dirty[mode] = True
        action_check = self.actions.check_0 if mode == 0 else self.actions.check_1
        action_check.setEnabled(True)

    def setClean(self, mode=0):
        self.dirty[mode] = False
        action_check = self.actions.check_0 if mode == 0 else self.actions.check_1
        action_check.setEnabled(False)
        self.actions.create.setEnabled(True)  # TODO

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self, mode=0):
        # TODO 区分？
        self.itemsToShapes.clear()
        self.shapesToItems.clear()

        if mode == 0:
            self.templateLabelList.clear()
            self.templateIndexList.clear()
        elif mode == 1:
            self.recogIndexList.clear()
            self.recogLabelList.clear()
            self.recogContentList.clear()
        self.filePath = None
        self.imageData = None
        # self.labelFile = None
        self.canvas.resetState()
        self.labelCoordinates.clear()
        # self.comboBox.cb.clear()
        self.result_dic = []

    # 当前展示图像 当前选中项
    def currentItem(self):
        mode = self.showMode
        labelList = self.templateLabelList if mode == 0 else self.recogLabelList
        items = labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def getAvailableScreencastViewer(self):
        osName = platform.system()

        if osName == "Windows":
            return ["C:\\Program Files\\Internet Explorer\\iexplore.exe"]
        elif osName == "Linux":
            return ["xdg-open"]
        elif osName == "Darwin":
            return ["open"]

    ## Callbacks ##
    def showTutorialDialog(self):
        subprocess.Popen(self.screencastViewer + [self.screencast])

    def showInfoDialog(self):
        from libs.__init__ import __version__

        msg = "Name:{0} \nApp Version:{1} \n{2} ".format(
            __appname__, __version__, sys.version_info
        )
        QMessageBox.information(self, "Information", msg)

    def showStepsDialog(self):
        msg = stepsInfo(self.lang)
        QMessageBox.information(self, "Information", msg)

    def showKeysDialog(self):
        msg = keysInfo(self.lang)
        QMessageBox.information(self, "Information", msg)

    def createShape(self):
        assert self.beginner()
        self.canvas.setEditing(False)
        self.actions.create.setEnabled(False)
        self.actions.createpoly.setEnabled(False)
        self.canvas.fourpoint = False

    def createPolygon(self):
        assert self.beginner()
        self.canvas.setEditing(False)
        self.canvas.fourpoint = True
        self.actions.create.setEnabled(False)
        self.actions.createpoly.setEnabled(False)
        self.actions.undoLastPoint.setEnabled(True)

    def rotateImg(self, filename, k, _value):
        self.actions.rotateRight.setEnabled(_value)
        pix = cv2.imread(filename)
        pix = np.rot90(pix, k)
        cv2.imwrite(filename, pix)
        self.canvas.update()
        self.loadFile(filename)

    def rotateImgWarn(self):
        if self.lang == "ch":
            self.msgBox.warning(self, "提示", "\n 该图片已经有标注框,旋转操作会打乱标注,建议清除标注框后旋转。")
        else:
            self.msgBox.warning(
                self,
                "Warn",
                "\n The picture already has a label box, "
                "and rotation will disrupt the label. "
                "It is recommended to clear the label box and rotate it.",
            )

    def rotateImgAction(self, k=1, _value=False, mode=0):
        mode = self.showMode
        filename = self.mImgList[mode][self.currIndex[mode]]

        if os.path.exists(filename):
            if self.itemsToShapesbox:
                self.rotateImgWarn()
            else:
                self.saveFile(mode)  # TODO mode是用当前状态？
                self.dirty[mode] = False
                self.rotateImg(filename=filename, k=k, _value=True)
        else:
            self.rotateImgWarn()
            self.actions.rotateRight.setEnabled(False)
            self.actions.rotateLeft.setEnabled(False)

    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            print("Cancel creation.")
            self.canvas.setEditing(True)
            self.canvas.restoreCursor()
            self.actions.create.setEnabled(True)
            self.actions.createpoly.setEnabled(True)

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def setCreateMode(self):
        assert self.advanced()
        self.toggleDrawMode(False)

    def setEditMode(self):
        assert self.advanced()
        self.toggleDrawMode(True)
        self.labelSelectionChanged()

    def updateFileMenu(self):
        currFilePath = self.filePath

        def exists(filename):
            return os.path.exists(filename)

        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f != currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon("labels")
            action = QAction(icon, "&%d %s" % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    # TODO
    def editLabel(self):
        if not self.canvas.editing():
            return
        item = self.currentItem()
        shape = self.itemsToShapes[item]
        if not item:
            return
        # text, is_mark, content = self.labelDialog.popUp(item.text())
        print("current shape: ", shape.label, shape.is_mark, shape.content)
        text, is_mark, content = self.labelDialog.popUp(
            shape.label, shape.is_mark, shape.content
        )
        # if text is not None:
        #     item.setText(text)
        #     # item.setBackground(generateColorByText(text))
        #     self.setDirty(self.showMode)
        #     self.updateComboBox()
        shape.content = text
        shape.is_mark = is_mark
        shape.content = content
        # item.setBackground(generateColorByText(text))
        self.setDirty(self.showMode)
        self.updateComboBox()

    # 返回值给self.mImgList5，表示thumbnail显示的5张图片
    def indexTo5Files(self, currIndex, mode=0):
        if currIndex < 2:
            return self.mImgList[mode][:5]
        elif currIndex > len(self.mImgList[mode]) - 3:
            return self.mImgList[mode][-5:]
        else:
            return self.mImgList[mode][currIndex - 2 : currIndex + 3]

    def fileitemDoubleClicked(self, item=None, mode=0):
        self.currIndex[mode] = self.mImgList[mode].index(
            ustr(os.path.join(os.path.abspath(self.dirname[mode]), item.text()))
        )
        filename = self.mImgList[mode][self.currIndex[mode]]
        if filename:
            self.mImgList5 = self.indexTo5Files(self.currIndex[mode], mode=mode)
            self.loadFile(filename, mode)

    # new
    def iconitemDoubleClicked(self, item=None, mode=0):
        self.currIndex[mode] = self.mImgList[mode].index(
            ustr(os.path.join(item.toolTip()))
        )
        filename = self.mImgList[mode][self.currIndex[mode]]
        if filename:
            self.mImgList5 = self.indexTo5Files(self.currIndex[mode], mode)
            # self.additems5(None)
            self.loadFile(filename)

    def CanvasSizeChange(self):
        mode = self.showMode
        if len(self.mImgList[mode]) > 0 and self.imageSlider.hasFocus():
            self.zoomWidget.setValue(self.imageSlider.value())

    def shapeSelectionChanged(self, selected_shapes):
        mode = self.showMode
        print(f"in shapeSelectionChanged(), current mode: {mode}")
        self._noSelectionSlot = True
        for shape in self.canvas.selectedShapes:
            shape.selected = False

        indexList = self.templateIndexList if mode == 0 else self.recogIndexList
        labelList = self.templateLabelList if mode == 0 else self.recogLabelList

        indexList.clearSelection()
        labelList.clearSelection()
        self.canvas.selectedShapes = selected_shapes

        for shape in self.canvas.selectedShapes:
            shape.selected = True
            self.shapesToItems[shape].setSelected(True)
            index = labelList.indexFromItem(self.shapesToItems[shape]).row()
            indexList.item(index).setSelected(True)

        labelList.scrollToItem(self.currentItem())  # QAbstractItemView.EnsureVisible
        # map current label item to index item and select it
        index = labelList.indexFromItem(self.currentItem()).row()
        indexList.scrollToItem(indexList.item(index))
        # TODO

        self._noSelectionSlot = False
        n_selected = len(selected_shapes)
        self.actions.singleRere.setEnabled(n_selected)
        self.actions.cellreRec.setEnabled(n_selected)
        self.actions.delete.setEnabled(n_selected)
        self.actions.copy.setEnabled(n_selected)
        self.actions.edit.setEnabled(n_selected == 1)
        self.actions.lock.setEnabled(n_selected)

    def addLabel(self, shape, mode=0):
        shape.paintLabel = self.displayLabelOption.isChecked()
        shape.paintIdx = self.displayIndexOption.isChecked()

        # 建立item（label）到shape的双向字典关系
        item = HashableQListWidgetItem(shape.label)  # 使其可以作为字典的键值
        # current difficult checkbox is disenble
        # item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        # item.setCheckState(Qt.Unchecked) if shape.difficult else item.setCheckState(Qt.Checked)

        # Checked means difficult is False
        # item.setBackground(generateColorByText(shape.label))
        self.itemsToShapes[item] = shape
        self.shapesToItems[shape] = item

        indexList = self.templateIndexList if mode == 0 else self.recogIndexList
        labelList = self.templateLabelList if mode == 0 else self.recogLabelList
        labelListDock = (
            self.templateLabelListDock if mode == 0 else self.recogLabelListDock
        )
        current_index = QListWidgetItem(str(labelList.count()))
        current_index.setTextAlignment(Qt.AlignHCenter)
        indexList.addItem(current_index)

        labelList.addItem(item)

        if mode == 1:
            content_item = HashableQListWidgetItem(shape.content)
            self.recogContentList.addItem(content_item)

        for action in self.actions.onShapesPresent:
            action.setEnabled(True)
        # self.updateComboBox()

        # update show counting
        labelListDock.setWindowTitle("Label" + f" ({labelList.count()})")

    def modeChanged(self):
        newMode = self.modeButtonGroup.checkedId()
        if newMode == self.operateMode:
            return

        # 1. 存储之前模式的状态
        if self.dirty[self.operateMode]:
            self.mayContinue(self.operateMode)
        # 2. 改变self.operateMode
        self.operateMode = newMode

        if self.operateMode == 0:
            self.templateDock.setEnabled(True)
            self.recogDock.setEnabled(False)
        elif self.operateMode == 1:
            self.templateDock.setEnabled(False)
            self.recogDock.setEnabled(True)

            # self.AutoRecognition.setEnabled(True)
            # self.reRecogButton.setEnabled(True)
            # self.actions.AutoRec.setEnabled(True)
            # self.actions.reRec.setEnabled(True)
        print("current oprateMode is ", self.operateMode)

    def on_templateFileName_input(self):
        self.templateRecogButton.setEnabled(True)

    # TODO
    def remLabels(self, shapes):
        if shapes is None:
            # print('rm empty label')
            return
        for shape in shapes:
            item = self.shapesToItems[shape]
            self.labelList.takeItem(self.labelList.row(item))
            del self.shapesToItems[shape]
            del self.itemsToShapes[item]
            self.updateComboBox()

        self.updateIndexList()

    def loadLabels(self, shapes):
        s = []
        shape_index = 0
        mode = self.showMode
        for label, is_mark, content, points, line_color, difficult in shapes:
            shape = Shape(
                label=label,
                is_mark=is_mark,
                content=content,
                line_color=line_color,
            )
            for x, y in points:
                # Ensure the labels are within the bounds of the image. If not, fix them.
                x, y, snapped = self.canvas.snapPointToCanvas(x, y)
                if snapped:
                    self.setDirty(mode)

                shape.addPoint(QPointF(x, y))
            shape.difficult = difficult
            shape.idx = shape_index
            shape_index += 1
            # shape.locked = False
            shape.close()
            s.append(shape)

            self._update_shape_color(shape)
            self.addLabel(shape, mode)

        # self.updateComboBox()
        self.canvas.loadShapes(s)

    def singleLabel(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapesToItems[shape]
        item.setText(shape.label)
        self.updateComboBox()

    def updateComboBox(self):
        pass
        """
        # Get the unique labels and add them to the Combobox.
        itemsTextList = [
            str(self.labelList.item(i).text()) for i in range(self.labelList.count())
        ]

        uniqueTextList = list(set(itemsTextList))
        # Add a null row for showing all the labels
        uniqueTextList.append("")
        uniqueTextList.sort()

        # self.comboBox.update_items(uniqueTextList)
        """

    # TODO
    def updateIndexList(self):
        self.templateIndexList.clear()
        for i in range(self.templateLabelList.count()):
            string = QListWidgetItem(str(i))
            string.setTextAlignment(Qt.AlignHCenter)
            self.templateIndexList.addItem(string)

    def saveLabels(self, annotationFilePath, mode_="Auto", mode=0):
        # Mode is Auto means that labels will be loaded from self.result_dic totally, which is the output of ocr model
        annotationFilePath = ustr(annotationFilePath)  # 转换为 Unicode 字符串

        def format_shape(s):
            print("s in saveLabels is ", s)
            return dict(
                label=s.label,  # str
                is_mark=s.is_mark,  # bool
                content=s.content,  # str
                line_color=s.line_color.getRgb(),
                fill_color=s.fill_color.getRgb(),
                points=[(int(p.x()), int(p.y())) for p in s.points],  # QPonitF
                difficult=s.difficult,
            )  # bool

        if mode_ == "Auto":
            shapes = []
        else:
            shapes = [
                format_shape(shape)
                for shape in self.canvas.shapes
                if shape.line_color != DEFAULT_LOCK_COLOR
            ]
        # Can add differrent annotation formats here
        for box in self.result_dic:
            # trans_dic = {"label": box[1][0], "points": box[0], "difficult": False}
            trans_dic = {
                "label": box[2],
                "is_mark": box[3],
                "content": box[1][0],
                "points": box[0],
                "difficult": False,
            }
            if trans_dic["content"] == "" and mode_ == "Auto":  # TODO
                continue
            shapes.append(trans_dic)

        try:
            trans_dic = []
            for box in shapes:
                trans_dict = {
                    "label": box["label"],
                    "is_mark": box["is_mark"],
                    "content": box["content"],
                    "points": box["points"],
                    "difficult": box["difficult"],
                }
                trans_dic.append(trans_dict)
            self.PPlabel[mode][annotationFilePath] = trans_dic
            if mode_ == "Auto":
                self.Cachelabel[annotationFilePath] = trans_dic

            # else:
            #     self.labelFile.save(annotationFilePath, shapes, self.filePath, self.imageData,
            #                         self.lineColor.getRgb(), self.fillColor.getRgb())
            # print('Image:{0} -> Annotation:{1}'.format(self.filePath, annotationFilePath))
            return True
        except:
            self.errorMessage("Error saving label data", "Error saving label data")
            return False

    def copySelectedShape(self):
        for shape in self.canvas.copySelectedShape():
            self.addLabel(shape, self.showMode)
        # fix copy and delete
        # self.shapeSelectionChanged(True)

    def move_scrollbar(self, value, mode=0):
        if mode == 0:
            self.templateLabelListBar.setValue(value)
            self.templateIndexListBar.setValue(value)
        elif mode == 1:
            self.recogIndexListBar.setValue(value)
            self.recogLabelListBar.setValue(value)
            self.recogContentListBar.setValue(value)

    def contentSelectionChanged(self):
        pass

    def labelSelectionChanged(self, mode=0):
        # 只能操作当前展示图片的label list
        mode = self.showMode
        if self._noSelectionSlot:
            return
        if self.canvas.editing():
            selected_shapes = []
            labelList = self.templateLabelList if mode == 0 else self.recogLabelList

            for item in labelList.selectedItems():
                # TODO 区分 self.itemsToShapes
                selected_shapes.append(self.itemsToShapes[item])

            if selected_shapes:
                self.canvas.selectShapes(selected_shapes)
            else:
                self.canvas.deSelectShape()

    def indexSelectionChanged(self, mode=0):
        # 只能操作当前展示图片的label list
        mode = self.showMode
        if self._noSelectionSlot:
            return
        if self.canvas.editing():
            selected_shapes = []
            indexList = self.templateIndexList if mode == 0 else self.recogIndexList
            labelList = self.templateLabelList if mode == 0 else self.recogLabelList

            for item in indexList.selectedItems():
                # map index item to label item
                index = indexList.indexFromItem(item).row()
                item = labelList.item(index)
                selected_shapes.append(self.itemsToShapes[item])

            if selected_shapes:
                self.canvas.selectShapes(selected_shapes)
            else:
                self.canvas.deSelectShape()

    def contentItemChanged(self, item):
        pass

    def labelItemChanged(self, item, mode=0):
        # avoid accidentally triggering the itemChanged siganl with unhashable item
        # Unknown trigger condition
        if type(item) == HashableQListWidgetItem:
            shape = self.itemsToShapes[item]
            label = item.text()
            if label != shape.label:
                shape.label = item.text()
                # shape.line_color = generateColorByText(shape.label)
                self.setDirty(mode)
            elif not ((item.checkState() == Qt.Unchecked) ^ (not shape.difficult)):
                shape.difficult = True if item.checkState() == Qt.Unchecked else False
                self.setDirty(mode)
            else:  # User probably changed item visibility
                self.canvas.setShapeVisible(
                    shape, True
                )  # item.checkState() == Qt.Checked
                # self.actions.save.setEnabled(True)
        else:
            print(
                "enter labelItemChanged slot with unhashable item: ", item, item.text()
            )

    # TODO
    def drag_drop_happened(self, mode=0):
        """
        label list drag drop signal slot
        """
        # print('___________________drag_drop_happened_______________')
        # should only select single item
        for item in self.labelList.selectedItems():
            newIndex = self.labelList.indexFromItem(item).row()

        # only support drag_drop one item
        assert len(self.canvas.selectedShapes) > 0
        for shape in self.canvas.selectedShapes:
            selectedShapeIndex = shape.idx

        if newIndex == selectedShapeIndex:
            return

        # move corresponding item in shape list
        shape = self.canvas.shapes.pop(selectedShapeIndex)
        self.canvas.shapes.insert(newIndex, shape)

        # update bbox index
        self.canvas.updateShapeIndex()

        """
        # boxList update simultaneously
        item = self.BoxList.takeItem(selectedShapeIndex)
        self.BoxList.insertItem(newIndex, item)
        """

        # changes happen
        self.setDirty(mode)

    # TODO
    # Callback functions:
    def newShape(self, value=True, mode=0):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if mode == 0:  # 模版模式下，显示labelDialog
            value = True

        if len(self.labelHist) > 0:
            self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist)

        if value:
            text, is_mark, content = self.labelDialog.popUp(text=self.prevLabelText)
            self.lastLabel = text
        else:
            text = self.prevLabelText

        if text is not None:
            self.prevLabelText = self.stringBundle.getString("tempLabel")

            shape = self.canvas.setLastLabel(
                text, is_mark, content, None, None
            )  # generate_color, generate_color

            self.addLabel(shape, self.showMode)
            if self.beginner():  # Switch to edit mode.
                self.canvas.setEditing(True)
                self.actions.create.setEnabled(True)
                self.actions.undoLastPoint.setEnabled(False)
                self.actions.undo.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.setDirty(mode)

        else:
            # self.canvas.undoLastLine()
            self.canvas.resetAllLines()

    def _update_shape_color(self, shape):
        # r, g, b = self._get_rgb_by_label(shape.key_cls, self.kie_mode)
        r, g, b = (0, 255, 0)
        shape.line_color = QColor(r, g, b)
        shape.vertex_fill_color = QColor(r, g, b)
        shape.hvertex_fill_color = QColor(255, 255, 255)
        shape.fill_color = QColor(r, g, b, 128)
        shape.select_line_color = QColor(255, 255, 255)
        shape.select_fill_color = QColor(r, g, b, 155)

    # def _get_rgb_by_label(self, label):
    #     # shift_auto_shape_color = 2  # use for random color
    #     # if kie_mode and label != "None":
    #     #     item = self.keyList.findItemsByLabel(label)[0]
    #     #     label_id = self.keyList.indexFromItem(item).row() + 1
    #     #     label_id += shift_auto_shape_color
    #     #     return LABEL_COLORMAP[label_id % len(LABEL_COLORMAP)]
    #     # else:
    #     #     return (0, 255, 0)
    #     return (0, 255, 0)

    def scrollRequest(self, delta, orientation):
        units = -delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)
        self.imageSlider.setValue(
            self.zoomWidget.value() + increment
        )  # set zoom slider value

    def zoomRequest(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scrollArea.width()
        h = self.scrollArea.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.items():
            self.canvas.setShapeVisible(shape, value)

    # new 区分mode
    # load具体的一个文件
    def loadFile(self, filePath=None, mode=0):
        """Load the specified file, or the last opened file if None."""
        if self.dirty[self.showMode]:
            self.mayContinue(self.showMode)
        self.resetState(mode)
        self.canvas.setEnabled(False)
        if filePath is None:
            filePath = self.settings.get(SETTING_FILENAME)

        # Make sure that filePath is a regular python string, rather than QString
        filePath = ustr(filePath)
        # Fix bug: An index error after select a directory when open a new file.
        unicodeFilePath = ustr(filePath)
        # unicodeFilePath = os.path.abspath(unicodeFilePath)
        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item

        # 判断处理哪个列表
        fileListWidget = (
            self.templateFileListWidget if mode == 0 else self.recogFileListWidget
        )
        fileListDock = (
            self.templateFileListDock if mode == 0 else self.recogFileListDock
        )
        fileListName = (
            self.templateFileListName if mode == 0 else self.recogFileListName
        )
        labelList = self.templateLabelList if mode == 0 else self.recogLabelList
        indexList = self.templateIndexList if mode == 0 else self.recogIndexList
        action_check = self.actions.check_0 if mode == 0 else self.actions.check_1

        # File List and Dock Handling
        if unicodeFilePath and fileListWidget.count() > 0:  # 当前存在列表
            if unicodeFilePath in self.mImgList[mode]:  # 文件在当前列表中，选中当前文件
                index = self.mImgList[mode].index(unicodeFilePath)  # 当前文件在mImgList中的索引
                fileWidgetItem = fileListWidget.item(index)  # 在ListWidget中的item
                print("unicodeFilePath is", unicodeFilePath)
                fileWidgetItem.setSelected(True)
                self.iconlist.clear()  # 清除thumbnail
                self.additems5(None)  # 更新thumbnail

                for i in range(5):
                    item_tooltip = self.iconlist.item(i).toolTip()
                    # print(i,"---",item_tooltip)
                    if item_tooltip == ustr(filePath):
                        titem = self.iconlist.item(i)
                        titem.setSelected(True)
                        self.iconlist.scrollToItem(titem)  # iconlist中的选中情况
                        break
            else:  # 文件不在当前列表中，清空当前列表（后续需要加载新的列表）
                fileListWidget.clear()
                self.mImgList[mode].clear()
                self.iconlist.clear()

        # if unicodeFilePath and self.iconList.count() > 0:
        #     if unicodeFilePath in self.mImgList:

        # Image Loading and Display
        if unicodeFilePath and os.path.exists(unicodeFilePath):
            self.showMode = mode  # new 加载显示当前图像时改变当前showMode

            self.canvas.verified = False
            cvimg = cv2.imdecode(np.fromfile(unicodeFilePath, dtype=np.uint8), 1)
            height, width, depth = cvimg.shape
            cvimg = cv2.cvtColor(cvimg, cv2.COLOR_BGR2RGB)
            image = QImage(
                cvimg.data, width, height, width * depth, QImage.Format_RGB888
            )

            if image.isNull():
                self.errorMessage(
                    "Error opening file",
                    "<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath,
                )
                self.status("Error reading %s" % unicodeFilePath)
                return False
            self.status("Loaded %s" % os.path.basename(unicodeFilePath))
            self.image = image
            self.filePath = unicodeFilePath
            self.canvas.loadPixmap(QPixmap.fromImage(image))

            if self.validFilestate(filePath, mode) is True:
                self.setClean()  # TODO
            else:
                self.dirty[mode] = False
                action_check.setEnabled(True)
            if len(self.canvas.lockedShapes) != 0:
                action_check.setEnabled(True)
                self.setDirty(mode)
            self.canvas.setEnabled(True)
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.filePath)
            self.toggleActions(True)

            # 根据PPlabel字典，读取当前文件对应的label并显示shape TODO 需要区分
            self.showBoundingBoxFromPPlabel(filePath)

            self.setWindowTitle(__appname__ + " " + filePath)

            # TODO
            # Default : select last item if there is at least one item
            if labelList.count():
                labelList.setCurrentItem(labelList.item(labelList.count() - 1))
                labelList.item(labelList.count() - 1).setSelected(True)
                indexList.item(labelList.count() - 1).setSelected(True)
                if mode == 1:
                    self.recogContentList.item(labelList.count() - 1).setSelected(True)

            # show file list image count
            select_indexes = fileListWidget.selectedIndexes()
            if len(select_indexes) > 0:
                fileListDock.setWindowTitle(
                    fileListName + f" ({select_indexes[0].row() + 1}"
                    f"/{fileListWidget.count()})"
                )
            # # update show counting
            # self.labelListDock.setWindowTitle(
            #     self.labelListDockName + f" ({self.labelList.count()})"
            # )

            self.canvas.setFocus(True)
            return True
        return False

    # new
    # 两个读取shape的途径，1）TODO self.canvas.lockedShapes 2）self.PPlabel
    def showBoundingBoxFromPPlabel(self, filePath):
        mode = self.showMode
        width, height = self.image.width(), self.image.height()
        imgidx = self.getImglabelidx(filePath)  # img filename
        shapes = []
        # box['ratio'] of the shapes saved in lockedShapes contains the ratio of the
        # four corner coordinates of the shapes to the height and width of the image
        for box in self.canvas.lockedShapes:
            if self.canvas.isInTheSameImage:
                shapes.append(
                    (
                        box["label"],
                        box["is_mark"],
                        box["content"],
                        [[s[0] * width, s[1] * height] for s in box["ratio"]],
                        DEFAULT_LOCK_COLOR,
                        box["difficult"],
                    )
                )
            else:
                shapes.append(
                    (
                        box["label"],
                        box["is_mark"],
                        "锁定框：待检测",
                        [[s[0] * width, s[1] * height] for s in box["ratio"]],
                        DEFAULT_LOCK_COLOR,
                        box["difficult"],
                    )
                )
        if imgidx in self.PPlabel[mode].keys():
            for box in self.PPlabel[mode][imgidx]:
                shapes.append(
                    (
                        box["label"],
                        box["is_mark"],
                        box["content"],
                        box["points"],
                        None,
                        box.get("difficult", False),
                    )
                )

        if shapes != []:
            self.loadLabels(shapes)
            self.canvas.verified = False

    def validFilestate(self, filePath, mode=0):
        if filePath not in self.fileStatedict[mode].keys():
            return None
        elif self.fileStatedict[mode][filePath] == 1:
            return True
        else:
            return False

    def resizeEvent(self, event):
        if (
            self.canvas
            and not self.image.isNull()
            and self.zoomMode != self.MANUAL_ZOOM
        ):
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))
        self.imageSlider.setValue(self.zoomWidget.value())  # set zoom slider value

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e - 110
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        else:
            settings = self.settings
            # If it loads images from dir, don't load it at the beginning
            if self.dirname is None:
                settings[SETTING_FILENAME] = self.filePath if self.filePath else ""
            else:
                settings[SETTING_FILENAME] = ""

            settings[SETTING_WIN_SIZE] = self.size()
            settings[SETTING_WIN_POSE] = self.pos()
            settings[SETTING_WIN_STATE] = self.saveState()
            settings[SETTING_LINE_COLOR] = self.lineColor
            settings[SETTING_FILL_COLOR] = self.fillColor
            settings[SETTING_RECENT_FILES] = self.recentFiles
            settings[SETTING_ADVANCE_MODE] = not self._beginner
            # 存储状态 TODO

            # 0/1 分开存储
            if self.defaultSaveDir[0] and os.path.exists(self.defaultSaveDir[0]):
                settings[SETTING_SAVE_DIR_0] = ustr(self.defaultSaveDir[0])
            else:
                settings[SETTING_SAVE_DIR_0] = ""
            if self.defaultSaveDir[1] and os.path.exists(self.defaultSaveDir[1]):
                settings[SETTING_SAVE_DIR_1] = ustr(self.defaultSaveDir[1])
            else:
                settings[SETTING_SAVE_DIR_1] = ""

            if self.lastOpenDir[0] and os.path.exists(self.lastOpenDir[0]):
                settings[SETTING_LAST_OPEN_DIR_0] = self.lastOpenDir[0]
            else:
                settings[SETTING_LAST_OPEN_DIR_0] = ""
            if self.lastOpenDir[1] and os.path.exists(self.lastOpenDir[1]):
                settings[SETTING_LAST_OPEN_DIR_1] = self.lastOpenDir[1]
            else:
                settings[SETTING_LAST_OPEN_DIR_1] = ""

            settings[SETTING_PAINT_LABEL] = self.displayLabelOption.isChecked()
            settings[SETTING_PAINT_INDEX] = self.displayIndexOption.isChecked()
            settings[SETTING_DRAW_SQUARE] = self.drawSquaresOption.isChecked()
            settings.save()
            try:
                self.saveLabelFile(mode=0)
                self.saveLabelFile(mode=1)
            except:
                pass

    def loadRecent(self, filename):
        if self.mayContinue():
            print(filename, "======")
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = [
            ".%s" % fmt.data().decode("ascii").lower()
            for fmt in QImageReader.supportedImageFormats()
        ]
        images = []

        for file in os.listdir(folderPath):
            if file.lower().endswith(tuple(extensions)):
                relativePath = os.path.join(folderPath, file)
                path = ustr(os.path.abspath(relativePath))
                images.append(path)
        natural_sort(images, key=lambda x: x.lower())
        return images

    def openDirDialog(self, _value=False, dirpath=None, silent=False, mode=0):
        if not self.mayContinue(self.showMode):
            return

        defaultOpenDirPath = dirpath if dirpath else "."
        if self.lastOpenDir[mode] and os.path.exists(self.lastOpenDir[mode]):
            defaultOpenDirPath = self.lastOpenDir[mode]
        else:
            defaultOpenDirPath = (
                os.path.dirname(self.filePath) if self.filePath else "."
            )
        if silent != True:
            targetDirPath = ustr(
                QFileDialog.getExistingDirectory(
                    self,
                    "%s - Open Directory" % __appname__,
                    defaultOpenDirPath,
                    QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
                )
            )
        else:
            targetDirPath = ustr(defaultOpenDirPath)
        self.lastOpenDir[mode] = targetDirPath
        self.importDirImages(targetDirPath, mode)

    def importDirImages(self, dirpath, mode=0, isDelete=False):
        if not self.mayContinue(self.showMode) or not dirpath:
            return
        if self.defaultSaveDir[mode] and self.defaultSaveDir[mode] != dirpath:
            self.saveLabelFile(self.showMode)

        if not isDelete:
            self.loadFilestate(dirpath, mode)
            self.PPlabelpath[mode] = dirpath + "/Label.txt"
            self.PPlabel[mode] = self.loadLabelFile(self.PPlabelpath[mode])
            print(self.PPlabel[mode])
            if mode == 1:
                self.Cachelabelpath = dirpath + "/Cache.cach"
                self.Cachelabel = self.loadLabelFile(self.Cachelabelpath)
                if self.Cachelabel:  # 如果 `Cachelabel` 存在，将其与 `PPlabel` 合并。
                    self.PPlabel[mode] = dict(self.Cachelabel, **self.PPlabel[mode])

            # self.init_key_list(self.PPlabel)

        self.lastOpenDir[mode] = dirpath
        self.dirname[mode] = dirpath

        self.defaultSaveDir[mode] = dirpath
        self.statusBar().showMessage(
            "%s started. Annotation will be saved to %s"
            % (__appname__, self.defaultSaveDir[mode])
        )
        self.statusBar().show()

        fileListWidget = (
            self.templateFileListWidget if mode == 0 else self.recogFileListWidget
        )
        fileListWidget.clear()

        self.filePath = None
        self.mImgList[mode] = self.scanAllImages(dirpath)
        self.mImgList5 = self.mImgList[mode][:5]
        self.openNextImg(mode)
        doneicon = newIcon("done")
        closeicon = newIcon("close")
        for imgPath in self.mImgList[mode]:
            filename = os.path.basename(imgPath)
            if self.validFilestate(imgPath, mode) is True:
                item = QListWidgetItem(doneicon, filename)
            else:
                item = QListWidgetItem(closeicon, filename)
            fileListWidget.addItem(item)

        if mode == 0:
            print("DirPath in importTemplateDirImages is", dirpath)
        elif mode == 1:
            print("DirPath in importRecognitionDirImages is", dirpath)
            self.AutoRecognition.setEnabled(True)
            self.reRecogButton.setEnabled(True)
            self.actions.AutoRec.setEnabled(True)
            self.actions.reRec.setEnabled(True)

        self.iconlist.clear()
        self.additems5(dirpath)
        # 设置一系列标志和按钮的状态。TODO
        # self.changeFileFolder = True
        self.haveAutoReced = False
        self.actions.rotateLeft.setEnabled(True)
        self.actions.rotateRight.setEnabled(True)

        fileListWidget.setCurrentRow(0)  # set list index to first
        fileListWidget.setWindowTitle(
            f" (1/{fileListWidget.count()})"
        )  # show image count

    def openPrevImg(self, _value=False, mode=0):
        if len(self.mImgList[mode]) <= 0:
            return

        if self.filePath is None:
            return

        currIndex = self.mImgList[mode].index(self.filePath)
        self.mImgList5 = self.mImgList[mode][:5]
        if currIndex - 1 >= 0:
            filename = self.mImgList[mode][currIndex - 1]
            self.mImgList5 = self.indexTo5Files(currIndex - 1, mode)
            if filename:
                self.loadFile(filename, mode)

    def openNextImg(self, _value=False, mode=0):
        if not self.mayContinue(self.showMode):
            return

        if len(self.mImgList[mode]) <= 0:
            return

        filename = None
        if self.filePath is None:
            filename = self.mImgList[mode][0]
            self.mImgList5 = self.mImgList[mode][:5]
        else:
            currIndex = self.mImgList[mode].index(self.filePath)
            if currIndex + 1 < len(self.mImgList[mode]):
                filename = self.mImgList[mode][currIndex + 1]
                self.mImgList5 = self.indexTo5Files(currIndex + 1, mode)
            else:
                self.mImgList5 = self.indexTo5Files(currIndex, mode)
        if filename:
            print("file name in openNext is ", filename)
            self.loadFile(filename, mode)

    def updateFileListIcon(self, filename):
        pass

    def saveFile(self, _value=False, mode_="Manual", mode=0):
        # Manual mode is used for users click "Save" manually,which will change the state of the image
        if self.filePath:
            imgidx = self.getImglabelidx(self.filePath)  # 文件名
            self._saveFile(imgidx, mode_=mode_, mode=mode)

    def saveLockedShapes(self):
        self.canvas.lockedShapes = []
        self.canvas.selectedShapes = []
        for s in self.canvas.shapes:
            if s.line_color == DEFAULT_LOCK_COLOR:
                self.canvas.selectedShapes.append(s)
        self.lockSelectedShape()
        for s in self.canvas.shapes:
            if s.line_color == DEFAULT_LOCK_COLOR:
                self.canvas.selectedShapes.remove(s)
                self.canvas.shapes.remove(s)

    def _saveFile(self, annotationFilePath, mode_="Manual", mode=0):
        if len(self.canvas.lockedShapes) != 0:
            self.saveLockedShapes()

        if mode_ == "Manual":
            self.result_dic_locked = []
            img = cv2.imread(self.filePath)
            width, height = self.image.width(), self.image.height()
            for shape in self.canvas.lockedShapes:
                # 计算每个形状的边界框坐标，将比例坐标转换为图像上的像素坐标
                box = [[int(p[0] * width), int(p[1] * height)] for p in shape["ratio"]]
                # assert len(box) == 4
                # 创建包含标签信息的结果列表，将边界框坐标插入到结果列表的开头
                result = [(shape["content"], 1), shape["label"], shape["is_mark"]]
                result.insert(0, box)
                self.result_dic_locked.append(result)
            self.result_dic += self.result_dic_locked
            self.result_dic_locked = []
            if annotationFilePath and self.saveLabels(
                annotationFilePath, mode_=mode_, mode=mode
            ):
                self.setClean(mode)
                self.statusBar().showMessage("Saved to  %s" % annotationFilePath)
                self.statusBar().show()
                # 改变状态icon
                currIndex = self.mImgList[mode].index(self.filePath)
                fileListWidget = (
                    self.templateFileListWidget
                    if mode == 0
                    else self.recogFileListWidget
                )
                item = fileListWidget.item(currIndex)
                item.setIcon(newIcon("done"))

                self.fileStatedict[mode][self.filePath] = 1
                if len(self.fileStatedict[mode]) % self.autoSaveNum == 0:
                    self.saveFilestate(mode=mode)
                    self.savePPlabel(mode_="Auto", mode=mode)

                fileListWidget.insertItem(int(currIndex), item)
                if not self.canvas.isInTheSameImage:
                    self.openNextImg(mode=mode)

                if mode == 0:
                    self.actions.saveLabel_0.setEnabled(True)
                elif mode == 1:
                    self.actions.saveLabel_1.setEnabled(True)

        elif mode_ == "Auto":
            if annotationFilePath and self.saveLabels(
                annotationFilePath, mode_=mode_, mode=mode
            ):
                self.setClean(mode)
                self.statusBar().showMessage("Saved to  %s" % annotationFilePath)
                self.statusBar().show()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def deleteImg(self, mode=0):
        deletePath = self.filePath
        if deletePath is not None:
            deleteInfo = self.deleteImgDialog()
            if deleteInfo == QMessageBox.Yes:
                if platform.system() == "Windows":
                    from win32com.shell import shell, shellcon

                    shell.SHFileOperation(
                        (
                            0,
                            shellcon.FO_DELETE,
                            deletePath,
                            None,
                            shellcon.FOF_SILENT
                            | shellcon.FOF_ALLOWUNDO
                            | shellcon.FOF_NOCONFIRMATION,
                            None,
                            None,
                        )
                    )
                    # linux
                elif platform.system() == "Linux":
                    cmd = "trash " + deletePath
                    os.system(cmd)
                    # macOS
                elif platform.system() == "Darwin":
                    import subprocess

                    absPath = (
                        os.path.abspath(deletePath)
                        .replace("\\", "\\\\")
                        .replace('"', '\\"')
                    )
                    cmd = [
                        "osascript",
                        "-e",
                        'tell app "Finder" to move {the POSIX file "'
                        + absPath
                        + '"} to trash',
                    ]
                    print(cmd)
                    subprocess.call(cmd, stdout=open(os.devnull, "w"))

                if self.filePath in self.fileStatedict.keys():
                    self.fileStatedict.pop(self.filePath)
                imgidx = self.getImglabelidx(self.filePath)
                if imgidx in self.PPlabel.keys():
                    self.PPlabel.pop(imgidx)
                self.openNextImg(mode)
                self.importDirImages(self.lastOpenDir[mode], mode=mode, isDelete=True)

    def deleteImgDialog(self):
        yes, cancel = QMessageBox.Yes, QMessageBox.Cancel
        msg = "The image will be deleted to the recycle bin"
        return QMessageBox.warning(self, "Attention", msg, yes | cancel)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(__file__))

    def mayContinue(self, mode=0):
        if not self.dirty[mode]:
            return True
        else:
            discardChanges = self.discardChangesDialog()
            if discardChanges == QMessageBox.No:
                return True
            elif discardChanges == QMessageBox.Yes:
                self.canvas.isInTheSameImage = True
                self.saveFile(mode)
                self.canvas.isInTheSameImage = False
                return True
            else:
                return False

    def discardChangesDialog(self):
        yes, no, cancel = QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel
        if self.lang == "ch":
            msg = '您有未保存的变更, 您想保存再继续吗?\n点击 "No" 丢弃所有未保存的变更.'
        else:
            msg = 'You have unsaved changes, would you like to save them and proceed?\nClick "No" to undo all changes.'
        return QMessageBox.warning(self, "Attention", msg, yes | no | cancel)

    def errorMessage(self, title, message):
        return QMessageBox.critical(
            self, title, "<p><b>%s</b></p>%s" % (title, message)
        )

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else "."

    def chooseColor(self):
        color = self.colorDialog.getColor(
            self.lineColor, "Choose line color", default=DEFAULT_LINE_COLOR
        )
        if color:
            self.lineColor = color
            Shape.line_color = color
            self.canvas.setDrawingColor(color)
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        self.remLabels(self.canvas.deleteSelected())
        self.actions.undo.setEnabled(True)
        self.setDirty()
        if self.noShapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)
        """
        self.BoxListDock.setWindowTitle(
            self.BoxListDockName + f" ({self.BoxList.count()})"
        )
        self.labelListDock.setWindowTitle(
            self.labelListDockName + f" ({self.labelList.count()})"
        )
        """

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(
            self.lineColor, "Choose line color", default=DEFAULT_LINE_COLOR
        )
        if color:
            for shape in self.canvas.selectedShapes:
                shape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(
            self.fillColor, "Choose fill color", default=DEFAULT_FILL_COLOR
        )
        if color:
            for shape in self.canvas.selectedShapes:
                shape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape, self.showMode)
        self.setDirty(self.showMode)

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty(self.showMode)

    def loadPredefinedClasses(self, predefClassesFile):
        if os.path.exists(predefClassesFile) is True:
            with codecs.open(predefClassesFile, "r", "utf8") as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.labelHist = [line]
                    else:
                        self.labelHist.append(line)

    def togglePaintLabelsOption(self):
        self.displayIndexOption.setChecked(False)
        for shape in self.canvas.shapes:
            shape.paintLabel = self.displayLabelOption.isChecked()
            shape.paintIdx = self.displayIndexOption.isChecked()
        self.canvas.repaint()

    def togglePaintIndexOption(self):
        self.displayLabelOption.setChecked(False)
        for shape in self.canvas.shapes:
            shape.paintLabel = self.displayLabelOption.isChecked()
            shape.paintIdx = self.displayIndexOption.isChecked()
        self.canvas.repaint()

    def toogleDrawSquare(self):
        self.canvas.setDrawingShapeToSquare(self.drawSquaresOption.isChecked())

    def additems(self, dirpath):
        for file in self.mImgList:
            pix = QPixmap(file)
            _, filename = os.path.split(file)
            filename, _ = os.path.splitext(filename)
            item = QListWidgetItem(
                QIcon(
                    pix.scaled(100, 100, Qt.IgnoreAspectRatio, Qt.FastTransformation)
                ),
                filename[:10],
            )
            item.setToolTip(file)
            self.iconlist.addItem(item)

    def additems5(self, dirpath):
        for file in self.mImgList5:
            pix = QPixmap(file)
            _, filename = os.path.split(file)
            filename, _ = os.path.splitext(filename)
            pfilename = filename[:10]
            if len(pfilename) < 10:
                lentoken = 12 - len(pfilename)
                prelen = lentoken // 2
                bfilename = prelen * " " + pfilename + (lentoken - prelen) * " "
            # item = QListWidgetItem(QIcon(pix.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)),filename[:10])
            item = QListWidgetItem(
                QIcon(
                    pix.scaled(100, 100, Qt.IgnoreAspectRatio, Qt.FastTransformation)
                ),
                pfilename,
            )
            # item.setForeground(QBrush(Qt.white))
            item.setToolTip(file)
            self.iconlist.addItem(item)
        owidth = 0
        for index in range(len(self.mImgList5)):
            item = self.iconlist.item(index)
            itemwidget = self.iconlist.visualItemRect(item)
            owidth += itemwidget.width()
        self.iconlist.setMinimumWidth(owidth + 50)

    def getImglabelidx(self, filePath):
        if platform.system() == "Windows":
            spliter = "\\"
        else:
            spliter = "/"
        filepathsplit = filePath.split(spliter)[-2:]
        return filepathsplit[0] + "/" + filepathsplit[1]

    # TODO 限定当前模式只有在recognition时执行
    def autoRecognition(self):
        mode = 1
        assert self.mImgList[mode] is not None
        print("Using model from ", self.model)

        uncheckedList = [
            i for i in self.mImgList[mode] if i not in self.fileStatedict[mode].keys()
        ]
        self.autoDialog = AutoDialog(
            parent=self, ocr=self.ocr, mImgList=uncheckedList, lenbar=len(uncheckedList)
        )
        self.autoDialog.popUp()
        self.currIndex[mode] = len(self.mImgList[mode]) - 1
        self.loadFile(self.filePath, mode=mode)  # ADD
        self.haveAutoReced = True
        self.AutoRecognition.setEnabled(False)
        self.actions.AutoRec.setEnabled(False)
        self.setDirty(mode)
        self.saveCacheLabel()

        # self.init_key_list(self.Cachelabel)

    def templateRecognition(self):
        msg = QMessageBox()
        msg.setWindowTitle("Template Recognition")

        if not self.mImgList[0]:
            msg.setText(self.stringBundle.getString("msg_importTemplateDir"))
            msg.exec_()
            return

        templateFileName = self.templateFileName.text().strip()
        if templateFileName not in os.listdir(self.dirname[0]):
            msg.setText(self.stringBundle.getString("msg_fileNameWrong"))
            msg.exec_()
            return

        templateFile = os.path.join(os.path.basename(self.dirname[0]), templateFileName)
        if templateFile not in self.PPlabel[0]:
            msg.setText(self.stringBundle.getString("msg_templateNotDefined"))
            msg.exec_()
            return

        print("templateFile is ", templateFile)
        boxs = self.PPlabel[0][templateFile]
        marks = []
        for box in boxs:
            if box["is_mark"]:
                marks.append(box)
        print("template boxs are: ", boxs)
        print("template marks are: ", marks)
        if len(marks) < 2:
            msg.setText(self.stringBundle.getString("msg_lackMark"))
            msg.exec_()
            return

        print("begin template recognition")
        assert self.mImgList[1] is not None
        print("Using model from ", self.model)

        uncheckedList = [
            i for i in self.mImgList[1] if i not in self.fileStatedict[1].keys()
        ]
        self.templateRecDialog = templateRecDialog(
            parent=self,
            ocr=self.ocr,
            mImgList=uncheckedList,
            lenbar=len(uncheckedList),
            templateBoxs=boxs,
        )
        self.templateRecDialog.popUp()
        self.currIndex[1] = len(self.mImgList[1]) - 1
        self.loadFile(self.filePath, mode=1)  # ADD
        self.templateRecogButton.setEnabled(False)
        self.actions.templateRec.setEnabled(False)
        self.setDirty(1)
        self.saveCacheLabel()

    def reRecognition(self):
        img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), 1)
        # org_box = [dic['points'] for dic in self.PPlabel[self.getImglabelidx(self.filePath)]]
        if self.canvas.shapes:
            self.result_dic = []
            self.result_dic_locked = (
                []
            )  # result_dic_locked stores the ocr result of self.canvas.lockedShapes
            rec_flag = 0
            for shape in self.canvas.shapes:
                box = [[int(p.x()), int(p.y())] for p in shape.points]  # 四个点的坐标
                shape_info = [shape.label, shape.is_mark]  # new

                assert len(box) == 4

                img_crop = get_rotate_crop_image(img, np.array(box, np.float32))
                if img_crop is None:
                    msg = (
                        "Can not recognise the detection box in "
                        + self.filePath
                        + ". Please change manually"
                    )
                    QMessageBox.information(self, "Information", msg)
                    return
                result = self.ocr.ocr(img_crop, cls=True, det=False)[0]
                if result[0][0] != "":
                    if shape.line_color == DEFAULT_LOCK_COLOR:
                        shape.content = result[0][0]
                        result = result + shape_info
                        result.insert(0, box)
                        self.result_dic_locked.append(result)
                    else:
                        result = result + shape_info
                        result.insert(0, box)
                        self.result_dic.append(result)
                else:
                    print("Can not recognise the box")
                    if shape.line_color == DEFAULT_LOCK_COLOR:
                        shape.label = result[0][0]
                        self.result_dic_locked.append(
                            [box, (self.noLabelText, 0), *shape_info]
                        )
                    else:
                        self.result_dic.append(
                            [box, (self.noLabelText, 0), *shape_info]
                        )
                try:
                    if self.noLabelText == shape.label or result[1][0] == shape.label:
                        print("label no change")
                    else:
                        rec_flag += 1
                except IndexError as e:
                    print("Can not recognise the box")
            if (len(self.result_dic) > 0 and rec_flag > 0) or self.canvas.lockedShapes:
                self.canvas.isInTheSameImage = True
                self.saveFile(mode_="Auto", mode=1)
                self.loadFile(self.filePath, mode=1)
                self.canvas.isInTheSameImage = False
                self.setDirty(mode=1)
            elif len(self.result_dic) == len(self.canvas.shapes) and rec_flag == 0:
                if self.lang == "ch":
                    QMessageBox.information(self, "Information", "识别结果保持一致！")
                else:
                    QMessageBox.information(
                        self, "Information", "The recognition result remains unchanged!"
                    )
            else:
                print("Can not recgonise in ", self.filePath)
        else:
            QMessageBox.information(self, "Information", "Draw a box!")

    def singleRerecognition(self):
        img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), 1)
        for shape in self.canvas.selectedShapes:
            box = [[int(p.x()), int(p.y())] for p in shape.points]

            assert len(box) == 4
            img_crop = get_rotate_crop_image(img, np.array(box, np.float32))
            if img_crop is None:
                msg = (
                    "Can not recognise the detection box in "
                    + self.filePath
                    + ". Please change manually"
                )
                QMessageBox.information(self, "Information", msg)
                return
            result = self.ocr.ocr(img_crop, cls=True, det=False)[0]
            if result[0][0] != "":
                result.insert(0, box)
                print("result in reRec is ", result)
                if result[1][0] == shape.label:
                    print("label no change")
                else:
                    shape.label = result[1][0]
            else:
                print("Can not recognise the box")
                if self.noLabelText == shape.label:
                    print("label no change")
                else:
                    shape.label = self.noLabelText
            self.singleLabel(shape)
            self.setDirty()

    def cellreRecognition(self):
        """
        re-recognise text in a cell
        """
        img = cv2.imread(self.filePath)
        for shape in self.canvas.selectedShapes:
            box = [[int(p.x()), int(p.y())] for p in shape.points]

            assert len(box) == 4

            # pad around bbox for better text recognition accuracy
            _box = boxPad(box, img.shape, 6)
            img_crop = get_rotate_crop_image(img, np.array(_box, np.float32))
            if img_crop is None:
                msg = (
                    "Can not recognise the detection box in "
                    + self.filePath
                    + ". Please change manually"
                )
                QMessageBox.information(self, "Information", msg)
                return

            # merge the text result in the cell
            texts = ""
            probs = 0.0  # the probability of the cell is avgerage prob of every text box in the cell
            bboxes = self.ocr.ocr(img_crop, det=True, rec=False, cls=False)[0]
            if len(bboxes) > 0:
                bboxes.reverse()  # top row text at first
                for _bbox in bboxes:
                    patch = get_rotate_crop_image(img_crop, np.array(_bbox, np.float32))
                    rec_res = self.ocr.ocr(patch, det=False, rec=True, cls=False)[0]
                    text = rec_res[0][0]
                    if text != "":
                        texts += text + (
                            "" if text[0].isalpha() else " "
                        )  # add space between english word
                        probs += rec_res[0][1]
                probs = probs / len(bboxes)
            result = [(texts.strip(), probs)]

            if result[0][0] != "":
                result.insert(0, box)
                print("result in reRec is ", result)
                if result[1][0] == shape.label:
                    print("label no change")
                else:
                    shape.label = result[1][0]
            else:
                print("Can not recognise the box")
                if self.noLabelText == shape.label:
                    print("label no change")
                else:
                    shape.label = self.noLabelText
            self.singleLabel(shape)
            self.setDirty()

    def autolcm(self):
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        self.panel = QLabel()
        self.panel.setText(self.stringBundle.getString("choseModelLg"))
        self.panel.setAlignment(Qt.AlignLeft)
        self.comboBox = QComboBox()
        self.comboBox.setObjectName("comboBox")
        self.comboBox.addItems(
            ["Chinese & English", "English", "French", "German", "Korean", "Japanese"]
        )
        vbox.addWidget(self.panel)
        vbox.addWidget(self.comboBox)
        self.dialog = QDialog()
        self.dialog.resize(300, 100)
        self.okBtn = QPushButton(self.stringBundle.getString("ok"))
        self.cancelBtn = QPushButton(self.stringBundle.getString("cancel"))

        self.okBtn.clicked.connect(self.modelChoose)
        self.cancelBtn.clicked.connect(self.cancel)
        self.dialog.setWindowTitle(self.stringBundle.getString("choseModelLg"))

        hbox.addWidget(self.okBtn)
        hbox.addWidget(self.cancelBtn)

        vbox.addWidget(self.panel)
        vbox.addLayout(hbox)
        self.dialog.setLayout(vbox)
        self.dialog.setWindowModality(Qt.ApplicationModal)
        self.dialog.exec_()
        if self.filePath:
            self.AutoRecognition.setEnabled(True)
            self.actions.AutoRec.setEnabled(True)

    def modelChoose(self):
        print(self.comboBox.currentText())
        lg_idx = {
            "Chinese & English": "ch",
            "English": "en",
            "French": "french",
            "German": "german",
            "Korean": "korean",
            "Japanese": "japan",
        }
        del self.ocr
        self.ocr = PaddleOCR(
            use_pdserving=False,
            use_angle_cls=True,
            det=True,
            cls=True,
            use_gpu=False,
            lang=lg_idx[self.comboBox.currentText()],
        )
        del self.table_ocr
        self.table_ocr = PPStructure(
            use_pdserving=False,
            use_gpu=False,
            lang=lg_idx[self.comboBox.currentText()],
            layout=False,
            show_log=False,
        )
        self.dialog.close()

    def cancel(self):
        self.dialog.close()

    def loadFilestate(self, saveDir, mode=0):
        self.fileStatepath[mode] = saveDir + "/fileState.txt"
        fileStatedict = self.fileStatedict[mode]
        fileStatedict = {}
        action_saveLabel = (
            self.actions.saveLabel_0 if mode == 0 else self.actions.saveLabel_1
        )
        if not os.path.exists(self.fileStatepath[mode]):
            f = open(self.fileStatepath[mode], "w", encoding="utf-8")
        else:
            with open(self.fileStatepath[mode], "r", encoding="utf-8") as f:
                states = f.readlines()
                for each in states:
                    file, state = each.split("\t")
                    fileStatedict[file] = 1
                action_saveLabel.setEnabled(True)
                # self.actions.saveRec.setEnabled(True)
                # self.actions.exportJSON.setEnabled(True)

    def saveFilestate(self, mode=0):
        with open(self.fileStatepath[mode], "w", encoding="utf-8") as f:
            for key in self.fileStatedict[mode]:
                f.write(key + "\t")
                f.write(str(self.fileStatedict[mode][key]) + "\n")

    def loadLabelFile(self, labelpath):
        labeldict = {}
        if not os.path.exists(labelpath):
            f = open(labelpath, "w", encoding="utf-8")

        else:
            with open(labelpath, "r", encoding="utf-8") as f:
                data = f.readlines()
                for each in data:
                    file, label = each.split("\t")
                    if label:
                        label = label.replace("false", "False")
                        label = label.replace("true", "True")
                        label = label.replace("null", "None")
                        labeldict[file] = eval(label)  # 在labeldict字典里添加项：file - label
                    else:
                        labeldict[file] = []
        return labeldict

    def savePPlabel(self, mode_="Manual", mode=0):
        savedfile = [self.getImglabelidx(i) for i in self.fileStatedict[mode].keys()]
        with open(self.PPlabelpath[mode], "w", encoding="utf-8") as f:
            for key in self.PPlabel[mode]:
                if key in savedfile and self.PPlabel[mode][key] != []:
                    f.write(key + "\t")
                    f.write(
                        json.dumps(self.PPlabel[mode][key], ensure_ascii=False) + "\n"
                    )

        if mode_ == "Manual":
            if self.lang == "ch":
                msg = "已将检查过的图片标签保存在 " + self.PPlabelpath[mode] + " 文件中"
            else:
                msg = (
                    "Images that have been checked are saved in "
                    + self.PPlabelpath[mode]
                )
            QMessageBox.information(self, "Information", msg)

    # 仅在recognition模式下触发
    def saveCacheLabel(self):
        with open(self.Cachelabelpath, "w", encoding="utf-8") as f:
            for key in self.Cachelabel:
                f.write(key + "\t")
                f.write(json.dumps(self.Cachelabel[key], ensure_ascii=False) + "\n")

    def saveLabelFile(self, mode=0):
        self.saveFilestate(mode)
        self.savePPlabel(mode)

    def speedChoose(self):
        if self.labelDialogOption.isChecked():
            self.canvas.newShape.disconnect()
            self.canvas.newShape.connect(partial(self.newShape, True))

        else:
            self.canvas.newShape.disconnect()
            self.canvas.newShape.connect(partial(self.newShape, False))

    def autoSaveFunc(self):
        if self.autoSaveOption.isChecked():
            self.autoSaveNum = 1  # Real auto_Save
            try:
                self.saveLabelFile(mode=0)
                self.saveLabelFile(mode=1)
            except:
                pass
            print("The program will automatically save once after confirming an image")
        else:
            self.autoSaveNum = 5  # Used for backup
            print(
                "The program will automatically save once after confirming 5 images (default)"
            )

    def undoShapeEdit(self):
        # 默认使用当前showMode
        mode = self.showMode
        self.canvas.restoreShape()
        if mode == 0:
            self.templateIndexList.clear()
            self.templateLabelList.clear()
        elif mode == 1:
            self.recogIndexList.clear()
            self.recogLabelList.clear()
            self.recogContentList.clear()
        self.loadShapes(self.canvas.shapes)
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)

    def loadShapes(self, shapes, replace=True):
        # 默认使用当前showMode
        mode = self.showMode
        self._noSelectionSlot = True
        for shape in shapes:
            self.addLabel(shape, mode)
        """
        self.labelList.clearSelection()
        self.indexList.clearSelection()
        """
        if mode == 0:
            self.templateIndexList.clearSelection()
            self.templateLabelList.clearSelection()
        elif mode == 1:
            self.recogIndexList.clearSelection()
            self.recogLabelList.clearSelection()
            self.recogContentList.clearSelection()
        self._noSelectionSlot = False
        self.canvas.loadShapes(shapes, replace=replace)
        print("loadShapes")  # 1

    def lockSelectedShape(self, mode=0):
        """lock the selected shapes.

        Add self.selectedShapes to lock self.canvas.lockedShapes,
        which holds the ratio of the four coordinates of the locked shapes
        to the width and height of the image
        """
        width, height = self.image.width(), self.image.height()

        action_check = self.actions.check_0 if mode == 0 else self.actions.check_1

        def format_shape(s):
            return dict(
                label=s.label,  # str
                is_mark=s.is_mark,  # bool
                content=s.content,  # str
                line_color=s.line_color.getRgb(),
                fill_color=s.fill_color.getRgb(),
                ratio=[
                    [int(p.x()) / width, int(p.y()) / height] for p in s.points
                ],  # QPonitF
                difficult=s.difficult,  # bool
            )

        # lock
        if len(self.canvas.lockedShapes) == 0:
            for s in self.canvas.selectedShapes:
                s.line_color = DEFAULT_LOCK_COLOR
                s.locked = True
            shapes = [format_shape(shape) for shape in self.canvas.selectedShapes]
            trans_dic = []
            for box in shapes:
                trans_dict = {
                    "label": box["label"],
                    "is_mark": box["is_mark"],
                    "content": box["content"],
                    "ratio": box["ratio"],
                    "difficult": box["difficult"],
                }
                trans_dic.append(trans_dict)
            self.canvas.lockedShapes = trans_dic
            action_check.setEnabled(True)

        # unlock
        else:
            for s in self.canvas.shapes:
                s.line_color = DEFAULT_LINE_COLOR
            self.canvas.lockedShapes = []
            self.result_dic_locked = []
            self.setDirty(mode)
            action_check.setEnabled(True)


def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        with open(filename, "rb") as f:
            return f.read()
    except:
        return default


def str2bool(v):
    return v.lower() in ("true", "t", "1")


def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("app"))
    # Tzutalin 201705+: Accept extra arguments to change predefined class file
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--lang", type=str, default="en", nargs="?")
    arg_parser.add_argument("--gpu", type=str2bool, default=True, nargs="?")
    arg_parser.add_argument(
        "--predefined_classes_file",
        default=os.path.join(
            os.path.dirname(__file__), "data", "predefined_classes.txt"
        ),
        nargs="?",
    )
    args = arg_parser.parse_args(argv[1:])

    win = MainWindow(
        lang=args.lang,
        gpu=args.gpu,
        default_predefined_class_file=args.predefined_classes_file,
    )
    win.show()
    return app, win


def main():
    """construct main app and run it"""
    app, _win = get_main_app(sys.argv)
    return app.exec_()


if __name__ == "__main__":
    resource_file = "./libs/resources.py"
    if not os.path.exists(resource_file):
        output = os.system("pyrcc5 -o libs/resources.py resources.qrc")
        assert output == 0, (
            "operate the cmd have some problems ,please check  whether there is a in the lib "
            "directory resources.py "
        )

    sys.exit(main())
