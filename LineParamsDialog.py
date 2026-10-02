import sys
import cv2
import numpy as np
from PySide2.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                               QComboBox, QSpinBox, QPushButton, QRadioButton,
                               QWidget, QSlider, QLabel, QCheckBox,
                               QGraphicsView, QGraphicsScene, QGraphicsRectItem,
                               QGraphicsEllipseItem, QMessageBox)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QBrush
from PySide2.QtCore import Qt, QRectF
# 数据流引擎的公共词汇：SOURCE_KEY = 全局图像源，AUTO_SOURCE = 图像源"自动"
from NodeRegistry import SOURCE_KEY, AUTO_SOURCE

# ===== 用于在弹窗中显示图片并绘制框选的画布 =====
class ROISelectGraphicsView(QGraphicsView):
    def __init__(self, pixmap, shape_type="矩形", parent=None):
        """
        :param pixmap: 图像数据载体，QPixmap 类的一个实例，用来在屏幕上显示和处理图像
        :param shape_type: 框选的形状 (矩形 或 圆)
        :param parent: 父对象
        """
        super().__init__(parent)
        self.shape_type = shape_type
        # 属性不能叫 self.scene：会遮蔽 QGraphicsView.scene() 方法
        self.roi_scene = QGraphicsScene(self) # 作为背景存放画面
        self.setScene(self.roi_scene)

        # 将图片添加到场景中
        self.pixmap_item = self.roi_scene.addPixmap(pixmap)
        # 设置场景大小和图片完全一致
        self.setSceneRect(0, 0, pixmap.width(), pixmap.height())

        # 开启抗锯齿和更新优化，作用是确保画布的交互体验丝滑、图像清晰，并且与后续的鼠标框选逻辑不产生冲突。
        self.setRenderHints(QPainter.Antialiasing) # 开启抗锯齿，使画出的矩形框的边光滑
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate) # 将视口的更新模式设置为"全视口更新"
        self.setDragMode(QGraphicsView.NoDrag) # 禁用拖拽模式

        self.start_point = None # 记录鼠标开始的起始点
        self.rect_item = None # 记录矩形对象
        self.final_rect = None # 矩形最终的位置
        # 绘制圆使用的参数
        self.center_point = None  # 圆形的圆心
        self.ellipse_item = None  # 记录圆形对象，ellipse：椭圆(圆为特殊的椭圆)
        self.center_dot_item = None  # 记录圆心点对象
        self.final_ellipse = None  # 圆形最终数据 (cx, cy, r)


    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 判断是否为左键按下
            self.start_point = self.mapToScene(event.pos())# mapToScene 会自动计算因为图片缩放产生的坐标差异，拿到绝对像素坐标

            # 如果是画圆，记录圆心
            if self.shape_type == "圆":
                self.center_point = self.start_point

                # 绘制并显示圆心点（绿色小实心圆）
                if self.center_dot_item:
                    # 如果圆心点对象存在
                    self.roi_scene.removeItem(self.center_dot_item) # 清空原本的圆心点对象
                # 用来绘制圆，Ellipse：椭圆；中心为6的小圆心
                self.center_dot_item = QGraphicsEllipseItem(self.center_point.x() - 3,
                                                            self.center_point.y() - 3,
                                                            6, 6)
                self.center_dot_item.setBrush(QBrush(QColor(0, 255, 0)))  # 填充绿色
                self.roi_scene.addItem(self.center_dot_item) # 添加到画布中

            # 清除画布上已有的图形
            if self.shape_type == "矩形" and self.rect_item:
                # 如果有矩形对象已经存在
                self.roi_scene.removeItem(self.rect_item) # 去除已有的矩形对象
                self.rect_item = None # 重置矩形对象的记录
            elif self.shape_type == "圆" and self.ellipse_item:
                # 如果有圆形对象已经存在
                self.roi_scene.removeItem(self.ellipse_item) # 去除已有的圆形对象
                self.ellipse_item = None # 重置圆形对象的记录


    def mouseMoveEvent(self, event):
        """鼠标拖动事件"""
        if self.start_point and event.buttons() == Qt.LeftButton:
            # 判断已经按下了鼠标左键，且当前依然按着左键拖拽时，才执行
            current_point = self.mapToScene(event.pos())

            if self.shape_type == "矩形":
                # # 计算矩形的左上角和宽高
                x = min(self.start_point.x(), current_point.x()) # 开始和末尾的最小值(预防反向拖拽的情况)
                y = min(self.start_point.y(), current_point.y())
                w = abs(self.start_point.x() - current_point.x()) #绝对值(反向时也可以获取长度)
                h = abs(self.start_point.y() - current_point.y())

                if self.rect_item is None:
                    # 画笔上原来没有矩形框
                    self.rect_item = QGraphicsRectItem(x, y, w, h) # 创建一个新的矩形图元对象
                    self.rect_item.setPen(QPen(QColor(0, 255, 0), 2, Qt.SolidLine)) # 设置矩形的画笔样式：绿色、线宽2、实线
                    self.roi_scene.addItem(self.rect_item) # 将绿框添加到场景画布中
                else:
                    # 矩形框已经存在
                    self.rect_item.setRect(x, y, w, h) # 直接更新它的坐标和宽高

            elif self.shape_type == "圆":
                # 计算半径：鼠标当前位置 到 圆心的距离
                cx = self.center_point.x() # 圆心(cx,cy)
                cy = self.center_point.y()
                dx = current_point.x() - cx # x轴上圆心到终点的距离
                dy = current_point.y() - cy # y轴上圆心到终点的距离
                r = np.sqrt(dx * dx + dy * dy) # 半径

                # 保持圆心点固定不动
                if self.center_dot_item:
                    # 在用户拖拽的过程中，保持圆心点的位置固定不变并确保它被绘制出来
                    self.center_dot_item.setRect(cx - 3, cy - 3, 6, 6)

                if self.ellipse_item is None:
                    # 如果椭圆(圆)不存在时
                    # 实时绘制跟随鼠标拖拽的绿色大圆圈（ROI区域）
                    self.ellipse_item = QGraphicsEllipseItem(cx - r, cy - r, 2 * r, 2 * r)
                    self.ellipse_item.setPen(QPen(QColor(0, 255, 0), 2, Qt.SolidLine)) # 设置画笔
                    self.roi_scene.addItem(self.ellipse_item) # 添加到画布上
                else:
                    # 如果椭圆存在时
                    self.ellipse_item.setRect(cx - r, cy - r, 2 * r, 2 * r) # 绘制外界矩形


    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.start_point:
            # 只有当松开的键是左键，且之前有记录过起点坐标时，才执行收尾动作
            # 记录松开鼠标时，鼠标位置的原始真实像素坐标（作为终点）
            current_point = self.mapToScene(event.pos())

            if self.shape_type == "矩形":
                # 根据起点和终点生成一个矩形，并调用 .normalized() 进行规范化
                self.final_rect = QRectF(self.start_point, current_point).normalized()
            elif self.shape_type == "圆":
                cx = self.center_point.x()
                cy = self.center_point.y()
                dx = current_point.x() - cx
                dy = current_point.y() - cy
                r = np.sqrt(dx * dx + dy * dy)
                self.final_ellipse = (cx, cy, r)

            # 将起点坐标重置为 None，彻底结束这一次的框选动作
            self.start_point = None

    def get_roi(self):
        """获取框选的坐标 (x, y, w, h)"""
        if self.shape_type == "矩形":
            if hasattr(self, 'final_rect') and self.final_rect:
                return (int(self.final_rect.x()), int(self.final_rect.y()),
                        int(self.final_rect.width()), int(self.final_rect.height()))

        elif self.shape_type == "圆":
            if hasattr(self, 'final_ellipse') and self.final_ellipse:
                cx, cy, r = self.final_ellipse
                # 返回圆心xy和半径，h暂时返回0
                return (int(cx), int(cy), int(r), 0) # noqa

        return 0, 0, 0, 0


# ===== 创建框选 ROI 的独立对话框 =====
class ROISelectDialog(QDialog):
    def __init__(self, img_bgr, parent=None, shape_type="矩形"):
        """
        :param img_bgr: OpenCV 读取的 BGR 格式图像数据
        :param parent: 父窗口控件
        :param shape_type: 选择框选的形状
        """
        super().__init__(parent)
        self.setWindowTitle("ROI 框选工具") # ROI窗口名字
        self.setModal(True) # Modal模态窗口

        # 将 OpenCV 的 BGR 图片转换为 Qt 的 QPixmap（同 ImageGraphicsView.set_image 的做法）
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = img_rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888) # type:ignore
        self.pixmap = QPixmap.fromImage(q_img)

        # 主布局
        layout = QVBoxLayout(self)

        # 实例化专门用于显示和交互的画布
        self.view = ROISelectGraphicsView(self.pixmap, shape_type=shape_type)
        # 自动缩放图片以完整适应视图大小，同时保持宽高比，彻底消除滚动条
        self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)
        # 把缩放好的画布加入到窗口的布局中
        layout.addWidget(self.view)

        # 底部按钮区
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # 点击(槽)事件
        self.btn_ok.clicked.connect(self.accept) # type:ignore
        self.btn_cancel.clicked.connect(self.reject) # type:ignore

        # 调整窗口自适应图片大小，并设置最大限制以防超出显示器
        self.resize(min(800, w + 30), min(600, h + 60))

    def get_roi(self):
        """获取画布上框选的坐标 (x, y, w, h)"""
        return self.view.get_roi()


# ===== 主配置窗口类 =====
class LineParamsDialog(QDialog):
    def __init__(self, parent=None, node=None, main_window=None):
        """
        :param parent:标准父类窗口参数，父类窗口关闭时，该窗口也关闭
        :param node:传入流程图中双击的方框对象，用于修改ui中的XY等值
        :param main_window:传入主窗口示例
        """
        super().__init__(parent)
        self.node = node
        self.main_window = main_window

        # 修改窗口的名字 Text
        self.setWindowTitle("直线检测")

        # 加载 UI 文件
        loader = QUiLoader()
        self.ui = loader.load('LineParamsDialog.ui')

        # 将加载的 UI 嵌入到当前 Dialog 的垂直布局中
        layout = QVBoxLayout(self)
        layout.addWidget(self.ui)
        layout.setContentsMargins(0, 0, 0, 0) # 去除布局的四周内边距

        # 通过findChild函数来获取 UI 内部的控件引用，即获取各控件的名字 Name
        # 获取下拉框：图像源（数据流引擎里"这个节点从谁的图像输出开始算"）
        self.input_source = self.ui.findChild(QComboBox, "input_source")
        self._populate_input_source()
        if self.input_source:
            # 换图像源就立刻记到节点上，免得用户直接点 × 关窗口时绑定丢了
            self.input_source.currentIndexChanged.connect(self._on_input_source_changed)

        # 获取 "绘制" 和 "继承" 两个单选框
        self.roi_draw = self.ui.findChild(QRadioButton, "roi_draw")
        self.roi_inherit = self.ui.findChild(QRadioButton, "roi_inherit")

        # 获取 ROI 区域的四个计数框
        self.spin_roi_x = self.ui.findChild(QSpinBox, "spin_roi_x")
        self.spin_roi_y = self.ui.findChild(QSpinBox, "spin_roi_y")
        self.spin_roi_w = self.ui.findChild(QSpinBox, "spin_roi_w")
        self.spin_roi_h = self.ui.findChild(QSpinBox, "spin_roi_h")
        # "外扩"：ROI 创建选"继承上游"时，在上游那块框外再扩多少像素（默认 0）
        self.spin_roi_margin = self.ui.findChild(QSpinBox, "spin_roi_margin")
        self.label_roi_margin = self.ui.findChild(QLabel, "label_roi_margin")
        # "继承自"：继承上游的"ROI 框"还是上游"检出的结果外接框"
        self.combo_roi_source = self.ui.findChild(QComboBox, "combo_roi_source")
        self.label_roi_source = self.ui.findChild(QLabel, "label_roi_source")

        # 获取 "ROI参数" 这个按钮，用来实现下面 XYWH 的显示与隐藏
        self.btn_roi_toggle = self.ui.findChild(QPushButton, "btn_roi_toggle")
        self.roi_params_widget = self.ui.findChild(QWidget, "roi_params_widget")

        # ROI区域 这一组在 .ui 里是"绝对定位"（子控件写死几何、没有布局管理器），
        # 行数一变（比如"外扩""作用于整图"多出来、或者选"继承"少了几行）就会挤在一起。
        # 这里在代码里给这三块套一个垂直布局，让高度自动跟着内容走：
        #   行组（ROI创建/形状/屏蔽形状/外扩/作用于整图/位置修正）
        #   -> 框选 / ROI参数 按钮
        #   -> XYWH 参数区（选"继承"时整块隐藏，布局会自动收起来）
        self.roi_group_box = self.ui.findChild(QWidget, "groupBox_2")
        self.roi_rows_widget = self.ui.findChild(QWidget, "roi_rows_widget")
        self.roi_buttons_widget = self.ui.findChild(QWidget, "roi_buttons_widget")
        if (self.roi_group_box is not None and self.roi_rows_widget is not None
                and self.roi_buttons_widget is not None and self.roi_params_widget is not None):
            roi_group_layout = QVBoxLayout(self.roi_group_box)
            roi_group_layout.addWidget(self.roi_rows_widget)
            roi_group_layout.addWidget(self.roi_buttons_widget)
            roi_group_layout.addWidget(self.roi_params_widget)

        # 获取滑动条（即位置修正右边的左右移动条）
        self.pos_correction_slider = self.ui.findChild(QSlider, "pos_correction_slider")
        self.pos_correction_slider.setValue(0) # 设置默认状态的代码 (0 代表关闭,左滑)

        # 获取形状右边的下拉框(选择矩阵或者圆) 和  WH 的文本内容(label)
        self.shape_combo = self.ui.findChild(QComboBox, "comboBox")
        self.label_w = self.ui.findChild(QLabel, "label_w")
        self.label_h = self.ui.findChild(QLabel, "label_h")

        # 从 UI 文件中获取底部的 3 个按钮
        self.btn_cont = self.ui.findChild(QPushButton, "btn_cont")
        self.btn_run = self.ui.findChild(QPushButton, "btn_run")
        self.btn_ok = self.ui.findChild(QPushButton, "btn_ok")

        # 获取隐藏 "ROI参数" 绘制的黄色框的复选框
        self.cb_hide_roi = self.ui.findChild(QCheckBox, "cb_hide_roi")

        # "作用于整图"（只有灰度的参数窗口才显示它，直线 / 圆的窗口里隐藏）
        self.cb_gray_full_image = self.ui.findChild(QCheckBox, "cb_gray_full_image")
        if self.cb_gray_full_image:
            self.cb_gray_full_image.setVisible(False)

        # 获取框选按钮
        self.btn_select = self.ui.findChild(QPushButton, "pushButton")
        if self.btn_select:
            self.btn_select.clicked.connect(self.on_select_click)

        # 界面初始化与事件绑定
        self.roi_params_widget.setVisible(True) # 控件是否可见，用于选择继承时隐藏 XYWH 部分
        self.btn_roi_toggle.setText("ROI参数 ▲") # 设置 "ROI参数" 这个按钮的箭头形式
        self.btn_roi_toggle.clicked.connect(self.toggle_roi_params) # 通过点击来控制 "ROI参数"这个按钮的箭头形式

        # 绘制和继承两种形式时 "ROI参数" 这个按钮的显示控制，绘制时显示，继承时隐藏
        self.roi_draw.toggled.connect(self._update_roi_params_visibility)
        self.roi_inherit.toggled.connect(self._update_roi_params_visibility)
        # 控制四个计数框，如果形状选择矩形时，为 XYWH;如果选择圆时，为 XYR，第四个参数隐藏
        self.shape_combo.currentTextChanged.connect(self._update_shape_layout)


        # 绑定 UI 中的三个按钮事件，使用if判断这三个按钮是否存在
        if self.btn_run:
            self.btn_run.clicked.connect(self.on_step_click) # 执行按钮
        if self.btn_ok:
            self.btn_ok.clicked.connect(self.on_ok) #确定按钮
        if self.btn_cont:
            self.btn_cont.clicked.connect(self.on_cont_click) # 连续执行按钮


        # 获取运行参数中的控件
        self.spin_canny_low = self.ui.findChild(QSpinBox, "spin_canny_low")
        self.spin_canny_high = self.ui.findChild(QSpinBox, "spin_canny_high")
        self.spin_hough_threshold = self.ui.findChild(QSpinBox, "spin_hough_threshold")
        self.spin_min_line_length = self.ui.findChild(QSpinBox, "spin_min_line_length")
        self.spin_max_line_gap = self.ui.findChild(QSpinBox, "spin_max_line_gap")


        # 获取显示结果中的 label 控件
        self.label_result_count = self.ui.findChild(QLabel, "label_7")
        if self.label_result_count:
            self.label_result_count.setText("0")  # 初始化置0


        # 加载节点已有的参数
        self.roi_draw.setChecked(True) # "ROI创建"滑动条 默认为 "绘制" 打开
        self._load_params() # 设置 XYWH 的默认值
        self._update_shape_layout(self.shape_combo.currentText()) # 强制执行一次 UI 布局对齐

        # 强制默认显示“基本参数”选项卡
        self.ui.tabWidget.setCurrentIndex(0)

        # 窗口弹出时，主动读取主窗口最后一次检测的数据，用于"显示结果"中的数值的显示
        if self.main_window and hasattr(self.main_window, 'last_detected_data'):
            self.update_result_count(self.main_window.last_detected_data)


    # ------------------------------------------------------------------
    # 图像源（数据流引擎的输入绑定）
    # ------------------------------------------------------------------
    def _candidate_sources(self):
        """
        列出可以当图像源的上游方框：直接或间接连到当前节点的所有方框。
        返回顺序是先直接上游、再往上一层，最可能用到的一般排在最前面。
        """
        if self.node is None or self.main_window is None:
            return []
        edges = getattr(self.main_window, 'flow_edges', None) or []

        # 先把连线整理成 {下游节点: [上游节点, ...]}
        parents = {}
        for edge in edges:
            parents.setdefault(edge.end_node, []).append(edge.start_node)

        candidates = []
        seen = {self.node}
        queue = list(parents.get(self.node, []))
        while queue:
            upstream = queue.pop(0)
            if upstream in seen:
                # 已经找过了（也顺便挡住了连线成环时的无限循环）
                continue
            seen.add(upstream)
            candidates.append(upstream)
            queue.extend(parents.get(upstream, []))
        return candidates

    def _populate_input_source(self):
        """
        填"图像源"下拉框：
            第 1 项：自动（沿连线继承上游的图像输出）—— 数据流引擎的默认行为
            第 2 项：全局图像源（原图）        —— 想让这个模块只看原图就选它，
                                                以前"每个节点都从原图算"的独立模式靠它实现
            后面：  每一个上游节点的图像输出   —— 多上游时手动指定用谁的图
        最后按节点上已经保存的绑定，把下拉框选中项恢复回来。
        """
        if not self.input_source:
            return
        self.input_source.clear()
        self.input_source.addItem("自动（继承上游图像）", AUTO_SOURCE)
        self.input_source.addItem("全局图像源（原图）", SOURCE_KEY)
        for upstream in self._candidate_sources():
            self.input_source.addItem("节点：{0}".format(upstream.name), upstream)

        # 找回原来选中的那一项：
        # 不直接用 Qt 的 findData()，因为它比对的是 QVariant，装 Python 对象时不可靠；
        # 这里自己遍历：字符串按值比，节点对象按身份（is）比。
        binding = getattr(self.node, 'input_source', None) if self.node is not None else None
        index = 0
        if binding is not None:
            for i in range(self.input_source.count()):
                data = self.input_source.itemData(i)
                if data is binding or (isinstance(data, str) and data == binding):
                    index = i
                    break
        # 没绑过（None）或者绑定的节点已经不在了，就回到第 0 项"自动"
        self.input_source.setCurrentIndex(index)

    def _on_input_source_changed(self, _index):
        """下拉框一改就写回节点（这个绑定不是"运行参数"，不跟图片走）"""
        self._save_input_source()

    def _save_input_source(self):
        """把下拉框当前的图像源绑定写到节点上"""
        if self.node is None or not self.input_source:
            return
        binding = self.input_source.currentData()
        if isinstance(binding, str) and binding == AUTO_SOURCE:
            # 自动：清掉绑定，引擎会沿连线去找上游
            self.node.input_source = None
        else:
            self.node.input_source = binding

    def _load_params(self):
        """从 node.params 加载参数到 UI 控件，并使用当前图像尺寸作为默认值"""
        if self.node:
            params = self.node.params
            # 设置 XY 的默认值为 0
            self.spin_roi_x.setValue(params.get("roi_x", 0))
            self.spin_roi_y.setValue(params.get("roi_y", 0))

            # 设定没有图片或者视频时的 WH 默认值
            default_w = 640
            default_h = 480

            # 尝试获取当前主窗口加载的图像或视频尺寸
            if self.main_window:
                # 当前打开的是静态图片，current_static_image = True 表示当前静态图片存在
                if self.main_window.current_static_image is not None:
                    h, w = self.main_window.current_static_image.shape[:2]
                    default_w, default_h = w, h

                # 当前打开的是摄像头或视频流
                elif self.main_window.cap is not None and self.main_window.cap.isOpened():
                    # 获取视频流的真实宽高
                    stream_w = self.main_window.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    stream_h = self.main_window.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    # 只有正确读到了宽高才覆盖默认值
                    if stream_w > 0 and stream_h > 0:
                        default_w, default_h = int(stream_w), int(stream_h)

            # 加载复选框状态 (如果节点没保存过，默认设为 False 即显示黄框)
            if self.cb_hide_roi:
                self.cb_hide_roi.setChecked(params.get("hide_roi", False))

            # 将默认值写入 UI (如果 node.params 里没有存过数据，就会使用计算出的 default_w/h)
            self.spin_roi_w.setValue(params.get("roi_w", default_w))
            self.spin_roi_h.setValue(params.get("roi_h", default_h))

            # 读取并恢复保存的形状
            saved_shape = params.get("roi_shape", "矩形")
            self.shape_combo.setCurrentText(saved_shape)

            # 读取并恢复"ROI创建"的选择：绘制 = 手动画 ROI；继承 = 用上游结果的包围盒当 ROI
            if params.get("roi_inherit", False):
                self.roi_inherit.setChecked(True)
            else:
                self.roi_draw.setChecked(True)

            # 读取并恢复"继承"时向外扩的像素数（默认 0 = 与上游完全重合）
            if self.spin_roi_margin:
                self.spin_roi_margin.setValue(params.get("roi_margin", 0))

            # 读取并恢复"继承自"（默认继承上游的 ROI 框）
            self._set_roi_source_to_ui(params.get("roi_source", "roi"))

            # 加载运行参数到界面
            self.spin_canny_low.setValue(params.get("canny_low", 50))
            self.spin_canny_high.setValue(params.get("canny_high", 150))
            self.spin_hough_threshold.setValue(params.get("hough_threshold", 100))
            self.spin_min_line_length.setValue(params.get("min_line_length", 100))
            self.spin_max_line_gap.setValue(params.get("max_line_gap", 10))


    def _update_params(self):
        """从 UI 控件保存参数到 node.params"""
        if self.node:
            # 将 XYWH 进度条的数值写到 params 里面
            self.node.params["roi_x"] = self.spin_roi_x.value()
            self.node.params["roi_y"] = self.spin_roi_y.value()
            self.node.params["roi_w"] = self.spin_roi_w.value()
            self.node.params["roi_h"] = self.spin_roi_h.value()

            # 保存当前选择的形状
            self.node.params["roi_shape"] = self.shape_combo.currentText()

            # 保存"ROI创建"的选择（继承 = 用上游结果的包围盒当 ROI，也就是"结果数据流"）
            self.node.params["roi_inherit"] = self.roi_inherit.isChecked()

            # 保存"继承"时向外扩的像素数
            if self.spin_roi_margin:
                self.node.params["roi_margin"] = self.spin_roi_margin.value()

            # 保存"继承自"（roi = 上游的 ROI 框 / result = 上游检出的结果外接框）
            if self.combo_roi_source:
                self.node.params["roi_source"] = self._roi_source_from_ui()

            # 顺手把图像源绑定也存一次（正常情况下下拉框一变就已经存过了）
            self._save_input_source()

            # 保存运行参数
            self.node.params["canny_low"] = self.spin_canny_low.value()
            self.node.params["canny_high"] = self.spin_canny_high.value()
            self.node.params["hough_threshold"] = self.spin_hough_threshold.value()
            self.node.params["min_line_length"] = self.spin_min_line_length.value()
            self.node.params["max_line_gap"] = self.spin_max_line_gap.value()

            # 将复选框状态写入节点参数
            if self.cb_hide_roi:
                self.node.params["hide_roi"] = self.cb_hide_roi.isChecked()


    def on_step_click(self):
        """点击'执行'按钮时触发：实现单步执行（只执行当前节点）"""
        self._update_params()  # 先保存当前UI中的参数

        # 拦截无效的 ROI 区域，即ROI区域全为0时弹出小窗口警告，避免代码出错
        if self.spin_roi_w.value() == 0 or self.spin_roi_h.value() == 0:
            QMessageBox.warning(self, "提示", "请输入ROI区域！")
            # 返回 False 表示执行被阻断，不进行后续关闭操作，
            # 用于判断ROI区域是否数值为 0，如果为 0 然后点击"确定"按钮则不关闭窗口
            return False

        if self.main_window:
            # 静态图片单步执行：统一交给主窗口的 _execute_static 处理
            # （计算 -> 显示 -> 写结果缓存 -> 更新日志，全项目只有这一条执行路径，
            #  所以从配置窗口点"执行"和从主界面点"单步执行"，结果完全一致）
            if self.main_window.current_static_image is not None:
                data = self.main_window._execute_static(
                    self.main_window.current_static_image, "step", self.node)  # noqa
                # 更新检查到的直线的数量
                self.update_result_count(data)
                # 执行成功，用于判断ROI区域是否数值为 0，如果不为 0 然后点击"确定"按钮则关闭窗口
                return True

            # 视频/摄像头单步执行
            elif self.main_window.cap is not None:
                # 告诉主窗口切换为"单步执行"状态
                self.main_window.video_processing_mode = "step"
                # 指定当前要单步执行的节点
                self.main_window.video_step_node = self.node
                # 主动触发刷新一帧画面，让视频流立刻响应单步检测
                self.main_window.update_frame()
                # 执行成功，用于判断ROI区域是否数值为 0，如果不为 0 然后点击"确定"按钮则关闭窗口
                return True

        # 如果因为没有图片/视频而导致无法执行，也保持窗口不关闭
        return False

    def on_cont_click(self):
        """点击'连续执行'按钮时触发：按完整的流程图顺序执行"""
        self._update_params()  # 先保存当前UI中的参数

        # 拦截无效的 ROI 区域，即ROI区域全为0时弹出小窗口警告，避免代码出错
        if self.spin_roi_w.value() == 0 or self.spin_roi_h.value() == 0:
            QMessageBox.warning(self, "提示", "请输入ROI区域！")
            return

        if self.main_window:
            # 静态图片连续执行：同样统一走 _execute_static
            # （它会跑完整个流程图、显示结果、写结果缓存、刷新日志表格）
            if self.main_window.current_static_image is not None:
                data = self.main_window._execute_static(
                    self.main_window.current_static_image, "continuous")  # noqa
                # 更新检查到的直线的数量
                self.update_result_count(data)

            # 视频/摄像头连续执行
            elif self.main_window.cap is not None:
                # 告诉主窗口切换为"连续执行"状态
                self.main_window.video_processing_mode = "continuous"
                self.main_window.video_step_node = None
                # 主动触发刷新一帧画面，恢复完整的流程图检测
                self.main_window.update_frame()

    def on_ok(self):
        """点击确定：执行一次单步检测并关闭配置窗口"""
        if self.on_step_click():
            # 点击确定时，先执行一遍单步检测
            self.accept()  # 然后关闭当前的配置窗口



    def toggle_roi_params(self):
        """点击"ROI参数"这个按钮后触发，切换 "ROI参数" 区域的展开与折叠状态，并同步修改按钮图标"""
        # 获取当前参数区域 XYWH 是否处于可见状态，True表示可见，False表示不可见
        current_visible = self.roi_params_widget.isVisible()
        # 取反，可见变隐藏，隐藏变可见
        self.roi_params_widget.setVisible(not current_visible)
        # 根据点击前的状态同步更新按钮上的箭头方向
        if not current_visible:
            self.btn_roi_toggle.setText("ROI参数 ▲")
        else:
            self.btn_roi_toggle.setText("ROI参数 ▼")

    def _set_roi_margin_visible(self, visible):
        """显示 / 隐藏"外扩"这一行（只有 ROI 创建 = 继承上游 时才用得上）"""
        if self.label_roi_margin:
            self.label_roi_margin.setVisible(visible)
        if self.spin_roi_margin:
            self.spin_roi_margin.setVisible(visible)

    # "继承自"下拉框的两项与内部取值的对应关系（用文字匹配，不依赖 PySide2 的 findData）
    ROI_SOURCE_ITEMS = (("roi", "上游 ROI 框"), ("result", "上游结果框"))

    def _set_roi_source_to_ui(self, key):
        """把 params 里的 roi_source 反映到下拉框上（认不出来时按默认的"上游 ROI 框"）"""
        if not self.combo_roi_source:
            return
        text = dict(self.ROI_SOURCE_ITEMS).get(key, "上游 ROI 框")
        for index in range(self.combo_roi_source.count()):
            if self.combo_roi_source.itemText(index) == text:
                self.combo_roi_source.setCurrentIndex(index)
                return

    def _roi_source_from_ui(self):
        """从下拉框读出 roi_source（默认 roi = 继承上游的 ROI 框）"""
        if not self.combo_roi_source:
            return "roi"
        current = self.combo_roi_source.currentText()
        for key, text in self.ROI_SOURCE_ITEMS:
            if text == current:
                return key
        return "roi"

    def _set_roi_source_visible(self, visible):
        """显示 / 隐藏"继承自"这一行（只有选"继承上游"时才用得上）"""
        if self.label_roi_source:
            self.label_roi_source.setVisible(visible)
        if self.combo_roi_source:
            self.combo_roi_source.setVisible(visible)

    def _update_roi_params_visibility(self):
        """根据“ROI创建”的单选框状态(绘制 / 继承上游)，控制"框选"按钮、展开按钮与参数区域的显示与隐藏"""
        # 选择的是 绘制roi_draw 时
        if self.roi_draw.isChecked():
            # 将"ROI参数"按钮展示出来
            self.btn_roi_toggle.setVisible(True)
            if not self.roi_params_widget.isVisible():
                # 把 XYWH 展示出来
                self.roi_params_widget.setVisible(True)
                # 改变 "ROI参数"的图标
                self.btn_roi_toggle.setText("ROI参数 ▲")
            # 只有手绘 ROI 才需要"框选"
            if self.btn_select:
                self.btn_select.setVisible(True)
            # 手绘 ROI 用不到"外扩"和"继承自"
            self._set_roi_margin_visible(False)
            self._set_roi_source_visible(False)
        else:
            # 选中的是 继承上游 时，隐藏下面的内容
            self.roi_params_widget.setVisible(False)
            self.btn_roi_toggle.setVisible(False)
            # ROI 是从上游继承来的，"框选"（手动画 ROI）没有意义，和 XYWH 一起藏起来；
            # 这一整行都空了之后，外层布局会自动把这段高度收掉。
            if self.btn_select:
                self.btn_select.setVisible(False)
            # 只有"继承上游"才用得上"外扩"和"继承自"
            self._set_roi_margin_visible(True)
            self._set_roi_source_visible(True)

    def _update_shape_layout(self, shape_text):
        """根据形状下拉框当前选中的文字，动态更新参数框的标签名和可见性"""
        if shape_text == "圆":
            # 选中的是"圆"时，label_w的文本为 "R"，label_h这一行隐藏
            self.label_w.setText("R:")
            self.label_h.setVisible(False)
            self.spin_roi_h.setVisible(False)
        else:
            # 选择的是其他时(矩阵，绘制矩形)，正常按照ui展示
            self.label_w.setText("W:")
            self.label_h.setVisible(True)
            self.spin_roi_h.setVisible(True)

    def refresh_size(self):
        """允许外部主窗口在加载图片后，手动触发对话框重新计算尺寸"""
        if self.main_window:
            # 如果当前是静态图片
            if self.main_window.current_static_image is not None:
                h, w = self.main_window.current_static_image.shape[:2]
                # 直接强制赋值，避免被 node.params 里可能存在的旧值覆盖
                self.spin_roi_w.setValue(w)
                self.spin_roi_h.setValue(h)

            # 如果当前是摄像头或视频流
            elif self.main_window.cap is not None and self.main_window.cap.isOpened():
                stream_w = self.main_window.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                stream_h = self.main_window.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                if stream_w > 0 and stream_h > 0:
                    self.spin_roi_w.setValue(int(stream_w))
                    self.spin_roi_h.setValue(int(stream_h))

    # "框选"按钮触发的功能
    def on_select_click(self):
        """点击框选按钮：检查图片或视频/摄像头帧，调出框选窗口，回填坐标"""

        img_bgr = None # 用来存放最终要传给 ROISelectDialog 用于框选的BGR 格式图片数据的
        timer_paused = False # 视频刷新定时器，用来判断什么时候截取视频的一帧用来框选区域

        # 获取当前选中的形状类型
        shape_text = self.shape_combo.currentText()

        # 优先取主窗口的静态图片
        if self.main_window is not None and self.main_window.current_static_image is not None:
            img_bgr = self.main_window.current_static_image

        # 没有静态图片，但有开启的摄像头/视频流
        elif self.main_window is not None and self.main_window.cap is not None and self.main_window.cap.isOpened():
            # 为了框选画面时画面不跳动，先暂定主窗口的视频刷新定时器
            timer = self.main_window.timer
            if timer is not None and timer.isActive():
                timer.stop()
                timer_paused = True

            # 捕获当前最新的一帧
            ret, frame = self.main_window.cap.read()
            if ret:
                img_bgr = frame
            else:
                # 如果读取失败，需要恢复定时器并给出提示
                if timer_paused:
                    timer.start(30)
                QMessageBox.warning(self, "提示", "视频/摄像头读取失败，无法获取当前画面！")
                return

            # 抓取完成，立刻恢复主窗口的视频刷新
            if timer_paused:
                timer.start(30)

        # 没有图片/视频，也没有打开摄像头
        if img_bgr is None:
            QMessageBox.warning(self, "提示", "请先导入图片或打开摄像头/视频！")
            return

        # 弹出框选窗口，将主窗口的 静态图片/视频帧 传进去
        select_dialog  = ROISelectDialog(img_bgr, self, shape_text)

        # 如果用户点击了“确定”，获取坐标并填入输入框
        if select_dialog .exec_() == QDialog.Accepted:
            x, y, w, h = select_dialog .get_roi()
            self.spin_roi_x.setValue(x)
            self.spin_roi_y.setValue(y)

            # 根据形状类型，正确回填 R (W) 和 H
            if shape_text == "矩形":
                self.spin_roi_x.setValue(x)
                self.spin_roi_y.setValue(y)
                self.spin_roi_w.setValue(w)
                self.spin_roi_h.setValue(h)
            elif shape_text == "圆":
                # 将圆心(x,y)和半径R(r)转换为外接矩形包围盒 =====
                # x,y是圆心，w是半径r
                cx, cy, r = x, y, w
                self.spin_roi_x.setValue(int(cx - r))  # 左上角 X
                self.spin_roi_y.setValue(int(cy - r))  # 左上角 Y
                self.spin_roi_w.setValue(int(2 * r))  # 宽度 = 2R
                self.spin_roi_h.setValue(int(2 * r))  # 高度 = 2R


    def update_result_count(self, data):
        """根据接收到的 data 数据更新直线数量显示"""
        if not self.label_result_count:
            # 检查 label 控件是否存在
            return
        # 只要当前节点是直线，就统计 data 里元组长度为 4 的数据（即直线数据）
        if self.node and self.node.name == "直线":
            # 节点存在 且 节点名字为"直线"
            if data is not None:
                # 如果 data 存在
                #           累加                         判断是否为元组                判断长度为4(起点(x,y),终点(x,y))
                line_count = sum(1 for item in data if isinstance(item, tuple) and len(item) == 4)
                self.label_result_count.setText(str(line_count)) # 设置 label 的内容，类型为str
            else:
                self.label_result_count.setText("0") # 如果 data 没有数值，则填 0
        else:
            self.label_result_count.setText("0") # 节点不存在，也填 0


if __name__ == '__main__':
    # 创建 Qt 应用
    app = QApplication(sys.argv)

    # 读取测试图片：读不到就用自动生成的测试图（黑图什么都测不出来）
    test_img_path  = 'image/lena.png'
    test_img  = cv2.imread(test_img_path )
    if test_img  is None:
        print(f"找不到图片，改用自动生成的测试图: {test_img_path }")
        from Detector import make_test_image
        test_img  = make_test_image()

    # 创建一个模拟的"主窗口"对象
    # 测试对话框需要访问 main_window.current_static_image，
    # 这里我们用 MockMainWindow 模拟这个属性
    class MockMainWindow:
        def __init__(self, img):
            self.current_static_image = img # 把图片赋给这个属性
            self.cap = None
            self.video_processing_mode = "continuous"
            self.video_step_node = None

        # 占位函数，防止调用时抛出 AttributeError
            # 添加 staticmethod 复制出现 "方法可能为 'static' 及未使用的形参" 的警告
        @staticmethod
        def update_frame():
            print("[Mock主窗口] 执行视频帧更新 (调用 update_frame)")

        @staticmethod
        def _display_image(img):
            print(f"[Mock主窗口] 显示图片，尺寸: {img.shape}")

        @staticmethod
        def _execute_static(frame, mode, node=None):
            # 配置窗口的"执行 / 连续执行"现在统一走主窗口的 _execute_static
            node_name = node.name if node is not None else "-"
            print(f"[Mock主窗口] _execute_static，模式: {mode}，节点: {node_name}")
            return []  # 模拟返回检测结果数据

        @staticmethod
        def _update_execution_log(exec_info):
            print(f"[Mock主窗口] 刷新执行日志，共 {len(exec_info)} 行")

        @staticmethod
        def _run_flow_pipeline_step(frame, node):
            # 单步执行现在返回 (图, 数据, 一行日志)，和主窗口保持一致
            print(f"[Mock主窗口] 执行单步检测，节点名: {node.name}")
            return frame, [], []

        @staticmethod
        def _run_flow_pipeline(frame):
            # 连续执行返回 (图, 数据, 日志列表)
            print("[Mock主窗口] 执行完整流程图检测")
            return frame, [], []

    mock_main_window = MockMainWindow(test_img )

    # 创建一个模拟的流程图节点
    class MockNode:
        def __init__(self):
            self.params = {}
            self.name = "模拟检测节点"

    mock_node = MockNode()

    # 实例化参数配置对话框，将模拟的主窗口和节点传进去
    dialog = LineParamsDialog(parent=None, node=mock_node, main_window=mock_main_window)
    dialog.setWindowTitle("直线查找 - 框选测试窗口")
    dialog.resize(390, 560)

    # 显示对话框
    dialog.show()

    sys.exit(app.exec_())