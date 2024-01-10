try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import time
import datetime
import json
import cv2
import numpy as np

from libs.utils import newIcon, get_rotate_crop_image

BB = QDialogButtonBox


class Worker(QThread):
    progressBarValue = pyqtSignal(int)
    listValue = pyqtSignal(str)
    endsignal = pyqtSignal(int, str)
    handle = 0

    def __init__(self, ocr, mImgList, templateBoxs, mainThread, model):
        super(Worker, self).__init__()
        self.ocr = ocr
        self.mImgList = mImgList
        self.templateBoxs = templateBoxs
        self.mainThread = mainThread
        self.model = model
        self.setStackSize(1024 * 1024)

    def run(self):
        try:
            findex = 0
            for Imgpath in self.mImgList:
                if self.handle == 0:
                    self.listValue.emit(Imgpath)
                    self.result_dic = []

                    if self.model == "paddle":
                        # 第一次检测
                        self.ocr_dic = self.ocr.ocr(Imgpath, cls=True, det=True)[0]

                        marks = []
                        for box in self.templateBoxs:
                            if box["is_mark"]:
                                marks.append(box)

                        box_rec = []
                        box_temp = []
                        for mark_box in marks:
                            for ocr_box in self.ocr_dic:
                                if mark_box["label"] and ocr_box[1][0]:
                                    if (
                                        mark_box["label"].casefold()
                                        == ocr_box[1][0].casefold()
                                    ):
                                        box_rec.append(ocr_box)
                                        box_temp.append(mark_box)

                        print("box_rec", box_rec)
                        print("box_temp", box_temp)

                        if len(box_rec) >= 2:
                            # 对齐 目前只采用两个点 随机选择?
                            # 每个框用中心点来对齐
                            [cx1_rec, cy1_rec] = [
                                (a + b + c + d) / 4
                                for a, b, c, d in zip(
                                    box_rec[0][0][0],
                                    box_rec[0][0][1],
                                    box_rec[0][0][2],
                                    box_rec[0][0][3],
                                )
                            ]
                            [cx2_rec, cy2_rec] = [
                                (a + b + c + d) / 4
                                for a, b, c, d in zip(
                                    box_rec[1][0][0],
                                    box_rec[1][0][1],
                                    box_rec[1][0][2],
                                    box_rec[1][0][3],
                                )
                            ]
                            [cx1_temp, cy1_temp] = [
                                (a + b + c + d) / 4
                                for a, b, c, d in zip(
                                    box_temp[0]["points"][0],
                                    box_temp[0]["points"][1],
                                    box_temp[0]["points"][2],
                                    box_temp[0]["points"][3],
                                )
                            ]
                            [cx2_temp, cy2_temp] = [
                                (a + b + c + d) / 4
                                for a, b, c, d in zip(
                                    box_temp[1]["points"][0],
                                    box_temp[1]["points"][1],
                                    box_temp[1]["points"][2],
                                    box_temp[1]["points"][3],
                                )
                            ]
                            ratio_x = (cx1_rec - cx2_rec) / (cx1_temp - cx2_temp)
                            ratio_y = (cy1_rec - cy2_rec) / (cy1_temp - cy2_temp)
                            dx = cx1_temp * ratio_x - cx1_rec
                            dy = cy1_temp * ratio_y - cy1_rec

                            # 对所有templateBoxs进行坐标换算并识别
                            img = cv2.imdecode(np.fromfile(Imgpath, dtype=np.uint8), 1)
                            for templateBox in self.templateBoxs:
                                recPoints = [
                                    [x * ratio_x - dx, y * ratio_y - dy]
                                    for [x, y] in templateBox["points"]
                                ]

                                assert len(recPoints) == 4

                                img_crop = get_rotate_crop_image(
                                    img, np.array(recPoints, np.float32)
                                )
                                result = self.ocr.ocr(img_crop, cls=True, det=False)[0]
                                result = [
                                    recPoints,
                                    result[0],
                                    templateBox["label"],
                                    templateBox["is_mark"],
                                ]
                                self.result_dic.append(result)

                        else:
                            print("匹配到的对准框少于两个，模版识别失败")
                            self.result_dic = None

                    # 结果保存
                    if self.result_dic is None or len(self.result_dic) == 0:
                        print("Can not recognise file", Imgpath)
                        pass
                    else:
                        strs = ""
                        for res in self.result_dic:
                            chars = res[1][0]
                            cond = res[1][1]
                            posi = res[0]
                            strs += (
                                "Transcription: "
                                + chars
                                + " Probability: "
                                + str(cond)
                                + " Location: "
                                + json.dumps(posi)
                                + "\n"
                            )
                        # Sending large amounts of data repeatedly through pyqtSignal may affect the program efficiency
                        self.listValue.emit(strs)
                        self.mainThread.result_dic = self.result_dic
                        self.mainThread.filePath = Imgpath
                        # 保存
                        self.mainThread.saveFile(mode_="Auto", mode=1)
                    findex += 1
                    self.progressBarValue.emit(findex)
                else:
                    break
            self.endsignal.emit(0, "readAll")
            self.exec()
        except Exception as e:
            print(e)
            raise


class templateRecDialog(QDialog):
    def __init__(
        self,
        text="Enter object label",
        parent=None,
        ocr=None,
        mImgList=None,
        lenbar=0,
        templateBoxs=None,
    ):
        super(templateRecDialog, self).__init__(parent)
        self.setFixedWidth(1000)
        self.parent = parent
        self.ocr = ocr
        self.mImgList = mImgList
        self.lender = lenbar
        self.templateBoxs = templateBoxs
        self.pb = QProgressBar()
        self.pb.setRange(0, self.lender)
        self.pb.setValue(0)

        layout = QVBoxLayout()
        layout.addWidget(self.pb)
        self.model = "paddle"
        self.listWidget = QListWidget(self)
        layout.addWidget(self.listWidget)

        self.buttonBox = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon("done"))
        bb.button(BB.Cancel).setIcon(newIcon("undo"))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)
        bb.button(BB.Ok).setEnabled(False)

        self.setLayout(layout)
        # self.setWindowTitle("自动标注中")
        self.setWindowModality(Qt.ApplicationModal)

        # self.setWindowFlags(Qt.WindowCloseButtonHint)

        self.thread_1 = Worker(
            self.ocr, self.mImgList, self.templateBoxs, self.parent, "paddle"
        )
        self.thread_1.progressBarValue.connect(self.handleProgressBarSingal)
        self.thread_1.listValue.connect(self.handleListWidgetSingal)
        self.thread_1.endsignal.connect(self.handleEndsignalSignal)
        self.time_start = time.time()  # save start time

    def handleProgressBarSingal(self, i):
        self.pb.setValue(i)

        # calculate time left of auto labeling
        avg_time = (
            time.time() - self.time_start
        ) / i  # Use average time to prevent time fluctuations
        time_left = str(datetime.timedelta(seconds=avg_time * (self.lender - i))).split(
            "."
        )[
            0
        ]  # Remove microseconds
        self.setWindowTitle("PPOCRLabel  --  " + f"Time Left: {time_left}")  # show

    def handleListWidgetSingal(self, i):
        self.listWidget.addItem(i)
        titem = self.listWidget.item(self.listWidget.count() - 1)
        self.listWidget.scrollToItem(titem)

    def handleEndsignalSignal(self, i, str):
        if i == 0 and str == "readAll":
            self.buttonBox.button(BB.Ok).setEnabled(True)
            self.buttonBox.button(BB.Cancel).setEnabled(False)

    def reject(self):
        print("reject")
        self.thread_1.handle = -1
        self.thread_1.quit()
        # del self.thread_1
        # if self.thread_1.isRunning():
        #     self.thread_1.terminate()
        # self.thread_1.quit()
        # super(AutoDialog,self).reject()
        while not self.thread_1.isFinished():
            pass
        self.accept()

    def validate(self):
        self.accept()

    def postProcess(self):
        try:
            self.edit.setText(self.edit.text().trimmed())
            # print(self.edit.text())
        except AttributeError:
            # PyQt5: AttributeError: 'str' object has no attribute 'trimmed'
            self.edit.setText(self.edit.text())
            print(self.edit.text())

    def popUp(self):
        self.thread_1.start()
        return 1 if self.exec_() else None

    def closeEvent(self, event):
        print("???")
        # if self.thread_1.isRunning():
        #     self.thread_1.quit()
        #
        #     # self._thread.terminate()
        # # del self.thread_1
        # super(AutoDialog, self).closeEvent(event)
        self.reject()
