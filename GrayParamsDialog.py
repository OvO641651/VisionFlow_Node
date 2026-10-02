# -*- coding: utf-8 -*-
"""
灰度的参数窗口（独立窗口，和直线 / 圆共用同一份 LineParamsDialog.ui，
只是把对灰度没意义的部分藏起来）。

和直线窗口的区别：
    1、标题改成"灰度"；
    2、隐藏"运行参数"页（Canny / Hough 那些参数对灰度没有意义）；
    3、多一个"作用于整图"勾选项：
         勾上   -> 忽略 ROI，整幅图都转灰度；
         不勾   -> 只把 ROI 那块区域转灰度（ROI 可以手绘，也可以"继承"上游的检测结果，
                   继承时的外扩像素数就是上面那个"外扩"）。
    4、勾上"作用于整图"时，ROI 参数区会置灰，免得用户以为它还有用。

入口：双击流程图里的"灰度"方框（和双击直线 / 圆一样）。
参数存在 node.params 里，所以同样是"按图片分别记"的。
"""

from LineParamsDialog import LineParamsDialog


class GrayParamsDialog(LineParamsDialog):
    def __init__(self, parent=None, node=None, main_window=None):
        # 先让父类把界面搭好（它会把"作用于整图"先藏起来）
        super().__init__(parent, node, main_window)

        # 1、窗口标题
        self.setWindowTitle("灰度")

        # 2、只保留"基本参数"这一页：
        #    运行参数（Canny / Hough）和显示结果（结果计数）对灰度都没有意义，
        #    直接把这两页从标签页里去掉（倒着删，索引不会错位）。
        for index in range(self.ui.tabWidget.count() - 1, -1, -1):
            if self.ui.tabWidget.tabText(index) != "基本参数":
                self.ui.tabWidget.removeTab(index)

        # 3、把"作用于整图"显示出来并接上信号
        if self.cb_gray_full_image:
            self.cb_gray_full_image.setVisible(True)
            self.cb_gray_full_image.toggled.connect(self._on_gray_full_toggled)

        # 4、按当前参数把界面刷一遍（信号已经连好，勾选状态会同步到 ROI 区的可用性）
        self._load_params()

    def _on_gray_full_toggled(self, checked):
        """勾上"作用于整图"后 ROI 就不起作用了，把它置灰，避免误会"""
        if self.roi_params_widget:
            self.roi_params_widget.setEnabled(not checked)
        if self.btn_select:
            self.btn_select.setEnabled(not checked)

    def _load_params(self):
        """父类负责常规参数（ROI / 图像源 / 继承 / 外扩），这里补上"作用于整图" """
        super()._load_params()
        if self.cb_gray_full_image and self.node:
            checked = bool(self.node.params.get("gray_full_image", False))
            self.cb_gray_full_image.setChecked(checked)
            self._on_gray_full_toggled(checked)

    def _update_params(self):
        """父类负责常规参数，这里补上"作用于整图" """
        super()._update_params()
        if self.cb_gray_full_image and self.node:
            self.node.params["gray_full_image"] = self.cb_gray_full_image.isChecked()


# 独立测试入口：不启动主程序，单独看这个窗口
if __name__ == '__main__':
    import sys

    import cv2
    import numpy as np

    from PySide2.QtWidgets import QApplication

    app = QApplication(sys.argv)

    test_img = cv2.imread('image/lena.png')
    if test_img is None:
        # 读不到就用自动生成的测试图（和 Detector.make_test_image 一致）
        from Detector import make_test_image
        test_img = make_test_image()

    class MockMainWindow:
        def __init__(self, img):
            self.current_static_image = img
            self.cap = None
            self.video_processing_mode = "continuous"
            self.video_step_node = None
            self.flow_nodes = []
            self.flow_edges = []

        @staticmethod
        def update_frame():
            print("[Mock主窗口] 执行视频帧更新")

        @staticmethod
        def _display_image(img):
            print(f"[Mock主窗口] 显示图片, 尺寸: {img.shape}")

        @staticmethod
        def _execute_static(frame, mode, node=None):
            _name = node.name if node is not None else "-"
            print(f"[Mock主窗口] _execute_static，模式: {mode}，节点: {_name}")
            return []

        @staticmethod
        def _update_execution_log(exec_info):
            print(f"[Mock主窗口] 刷新执行日志，共 {len(exec_info)} 行")

    class MockNode:
        def __init__(self):
            self.params = {"roi_x": 0, "roi_y": 0, "roi_w": 512, "roi_h": 512}
            self.name = "灰度"

    dialog = GrayParamsDialog(parent=None, node=MockNode(), main_window=MockMainWindow(test_img))
    dialog.resize(390, 560)
    dialog.show()
    sys.exit(app.exec_())
