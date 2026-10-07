import sys
import cv2
import numpy as np
from PySide2.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                               QComboBox, QSpinBox, QDoubleSpinBox, QPushButton, QRadioButton,
                               QWidget, QSlider, QLabel, QCheckBox, QSizePolicy, QScrollArea,
                               QGroupBox, QFrame,
                               QGraphicsView, QGraphicsScene, QGraphicsRectItem,
                               QGraphicsEllipseItem, QMessageBox)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QBrush
from PySide2.QtCore import Qt, QRectF
# 数据流引擎的公共词汇：SOURCE_KEY = 全局图像源，AUTO_SOURCE = 图像源"自动"
from NodeRegistry import SOURCE_KEY, AUTO_SOURCE, get_spec
# 参数校验（批次4 目标4）：规则表写在各算子里，这里只负责"跑一遍 + 把结果显示出来"
from ParamRules import run_validation

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

        # ★ "运行参数"页做成可滚动的（用户 2026.10.7 要求）：
        #   提示行**不许改变窗口大小** —— 参数下面有富余空间就直接显示（不出滚动条），
        #   空间不够才出滚动条（例：直线节点）。见 _wrap_run_params_in_scroll()。
        self._wrap_run_params_in_scroll()

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

        # ★ 参数校验（批次4 目标4 轮2）：窗口层要"把纠正后的值写回控件"，
        #   所以先把"参数名 → 控件"登记起来（子类 CircleParamsDialog / GenericProcessDialog
        #   会把各自的控件追加进来）。
        self._validate_widgets = {
            "canny_low": self.spin_canny_low,
            "canny_high": self.spin_canny_high,
            "hough_threshold": self.spin_hough_threshold,
            "min_line_length": self.spin_min_line_length,
            "max_line_gap": self.spin_max_line_gap,
        }


        # 获取显示结果中的 label 控件
        self.label_result_count = self.ui.findChild(QLabel, "label_7")
        if self.label_result_count:
            self.label_result_count.setText("0")  # 初始化置0


        # 加载节点已有的参数
        # "ROI创建"默认选"继承上游"（用户 2026.10.5 要求：新节点默认继承上游的处理区域，
        # 想自己画框的点一下"绘制"即可，两档都还在）
        self.roi_inherit.setChecked(True)
        # ★ 数值输入的"软范围"（用户 2026.10.7 要求）：先把所有数值控件改成
        #   "越界值可以先打进去、提交时才夹回上下限"，再加载参数
        #   （放在 _load_params() 之前：老方案文件里带着越界值时，加载那一刻就会夹回来）。
        self._soft_range_all()
        self._load_params() # 设置 XYWH 的默认值
        self._update_shape_layout(self.shape_combo.currentText()) # 强制执行一次 UI 布局对齐

        # 强制默认显示“基本参数”选项卡
        self.ui.tabWidget.setCurrentIndex(0)

        # ★ 参数校验提示行（批次4 目标4 轮2）：.ui 里摆在"运行参数"页最上面、默认隐藏；
        #   找不到就自己补一行（"控件真源只有运行时那一套"）。**默认隐藏**很关键 ——
        #   QLabel 的 sizeHint 是按整行文字宽度算的，常显的长提示会把窗口顶宽（变更第 15 条那个坑）。
        self.validate_hint = self.ui.findChild(QLabel, "validate_hint")
        if self.validate_hint is None:
            self.validate_hint = self._build_validate_hint()
        if self.validate_hint is not None:
            self.validate_hint.setWordWrap(True)
            # 限宽 + 最小宽度一起用：上限防"顶宽窗口"（变更第 15 条那个坑），
            # 下限防"被挤成一列字"（GenericProcessDialog 那类窗口里没有控件撑着列宽时，
            # 光有 wordWrap 的 QLabel 会被压到最窄、变成"一列一个字"）。
            # 下限取 200 是量出来的：240 会把对话框宽度从 274 顶到 312，200 则**宽度不变**。
            self.validate_hint.setMinimumWidth(200)
            self.validate_hint.setMaximumWidth(300)
            # ★ 竖直方向"只占自己那一行、不分食多余空间"（用户 2026.10.7 实测要求）：
            #   直线窗口那一列是 5 行参数、没有间隔项，多出来的高度由各行**平分**；
            #   提示行若用默认策略（可伸展）就会被当成第 6 个"平分者"，
            #   把原本的布局撑变形（截图里：提示在上、参数被挤到下面、中间空一大块）。
            #   用 Maximum 策略 + 把它放在那一列的**最后**，参数行就保持原样，提示贴在它们下面。
            self.validate_hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self._show_validate_hint(None, None)          # 初始隐藏
        # ★ 微调框挪到紧挨标签（用户 2026.10.7 要求）；通用窗口在生成动态行之后会再调一次
        self._tighten_param_rows()

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

            # 设定 ROI 宽高的默认值：**优先取"这个节点实际会收到的图"的尺寸**——
            # 也就是沿它声明的"图像源"往上追到的起点那张图（图片源指定的文件 / 主窗口当前图）。
            # 老实现只看主窗口当前图，于是"图像源绑到图片源"的下游节点，
            # ROI 默认尺寸与上游那张图对不上（用户实测反馈：读不到上游图像源的整图大小）。
            default_w = 640
            default_h = 480

            if self.main_window:
                input_frame = None
                if self.node is not None and hasattr(self.main_window, "_node_input_frame"):
                    input_frame = self.main_window._node_input_frame(self.node)
                if input_frame is None:
                    # 追不到上游（比如起点节点自己）：退回"主窗口当前图"
                    input_frame = self.main_window.current_static_image
                if input_frame is not None:
                    h, w = input_frame.shape[:2]
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
            # 默认"继承上游"（用户 2026.10.5 要求）；方案里明确存过 False 的才回到"绘制"
            if params.get("roi_inherit", True):
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


    # ------------------------------------------------------------------
    # 数值输入的"软范围"（用户 2026.10.7 要求）
    #
    # 用户原话的诉求：现在范围是 1~10 时输入 11 直接"打不进去、只留一个 1"；
    # 想要的是"**可以先打完越界值，回车 / 点别处（和现在确定数字的方式一样）时自动变成上限或下限**"。
    #
    # 为什么不能只靠 `setKeyboardTracking(False)`（实测过）：
    #   QSpinBox 的 validator 对越界文本直接返回 **Invalid**（范围 1~10 时 `validate("11")` 就是 Invalid），
    #   关不关 keyboardTracking 都一样 ⇒ 第二个字符会被吃掉。
    # 做法（三步）：
    #   ① 把控件**自身的范围放宽**（validator 放行，用户想打多少打多少）；
    #   ② 关掉 `keyboardTracking`（打字过程中不改 value、不发 valueChanged，不会边打边跳）；
    #   ③ 在 `valueChanged`（只在**提交**时来：回车 / 失焦 / 点箭头 / interpretText）里夹回真范围。
    # 真范围存在控件自己的动态属性 `_soft_min` / `_soft_max` 上，任何窗口都能复用这一套。
    # ------------------------------------------------------------------
    def _apply_soft_range(self, widget):
        """把一个数值控件改成"软范围"（幂等：同一个控件只装一次）"""
        if not isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget
        if widget.property("_soft_ready"):
            return widget
        low, high = widget.minimum(), widget.maximum()
        # ★ 放宽之前先记下它"刚好装得下真范围"的宽度，放宽后**锁回这个宽度 + 12px**：
        #   范围一放宽，位数就变多（-309 比 31 宽、"220.00" 比 "20.00" 宽），
        #   控件会把整行、整窗顶宽（实测"滤波"窗口从 321px 涨到 341px，被门禁 `dsh_roi_default_check` 抓到）；
        #   锁宽度之后框里照样能打完超范围的值（QLineEdit 会自动横向滚动）。
        #   **+12px** 是用户 2026.10.7 要求的"微调框长一点点"：原来刚好贴着箭头、三位的值看着挤。
        width = widget.sizeHint().width() + 12
        span = max(abs(low), abs(high), 1)
        if isinstance(widget, QDoubleSpinBox):
            widget.setRange(float(low) - span * 10.0, float(high) + span * 10.0)
        else:
            widget.setRange(int(low) - span * 10, int(high) + span * 10)
        widget.setFixedWidth(width)
        widget.setProperty("_soft_min", low)
        widget.setProperty("_soft_max", high)
        widget.setKeyboardTracking(False)
        widget.valueChanged.connect(lambda value, box=widget: self._clamp_soft_range(box, value))
        widget.setProperty("_soft_ready", True)
        return widget

    def _clamp_soft_range(self, widget, value):
        """提交时把值夹回真范围（打字过程中不会走到这里 —— keyboardTracking 已关）"""
        low = widget.property("_soft_min")
        high = widget.property("_soft_max")
        if low is None or high is None:
            return
        if value < low or value > high:
            widget.setValue(max(low, min(high, value)))

    def _soft_range_all(self):
        """把窗口里**所有**数值控件都改成软范围（.ui 里的 + 运行时动态生成的，都会被子类再调一次）"""
        for cls in (QSpinBox, QDoubleSpinBox):
            for widget in self.ui.findChildren(cls):
                self._apply_soft_range(widget)

    def _commit_number_edits(self):
        """
        把"已经打了字、但还没回车 / 还没失焦"的输入提交掉（顺带夹回上下限）。

        为什么要在读参数之前做：`value()` 读的是**已提交**的值。用户把 500 打进框里、
        没按回车就点"执行"，不先提交的话读到的还是旧值 —— 用户会以为白填了。
        """
        for cls in (QSpinBox, QDoubleSpinBox):
            for widget in self.ui.findChildren(cls):
                widget.interpretText()

    def _update_params(self):
        """从 UI 控件保存参数到 node.params"""
        self._commit_number_edits()   # ★ 先把"打了字还没回车"的输入提交掉（并夹回上下限）
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


    # ------------------------------------------------------------------
    # 参数校验（批次4 目标4 轮2）——窗口层这一遍
    #
    # 与引擎层（main.py::_execute_node）跑的是**同一张规则表**（ParamRules.run_validation），
    # 只是出口不同：这里把纠正了什么显示成一行提示、并把纠正后的值写回控件；
    # 纠正不了的**不拦用户**（照样让他执行，由引擎层跳过那个节点、把原因写进执行日志），
    # 这样窗口层与引擎层的语义完全一致，也不违反"执行路径绝不弹 QMessageBox"的铁律。
    # ------------------------------------------------------------------
    def _build_validate_hint(self):
        """`.ui` 里找不到 validate_hint 时，自己往"运行参数"页**参数行的下面**补一行"""
        hint = QLabel()
        hint.setWordWrap(True)
        hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = getattr(self, "param_layout", None)
        if layout is None:
            layout = self.ui.findChild(QVBoxLayout, "verticalLayout_8")
        if layout is None:
            return hint                       # 布局都找不到：返回孤儿 label，显示不了也不许崩
        # 放到最后：通用窗口那一列末尾有个"弹簧"（addStretch），要插在它**之前**，
        # 这样提示贴在参数行下面，而不是被弹到分组框最底下。
        last = layout.itemAt(layout.count() - 1) if layout.count() else None
        if last is not None and last.spacerItem() is not None:
            layout.insertWidget(layout.count() - 1, hint)
        else:
            layout.addWidget(hint)
        return hint

    def _validate_widget_for(self, key):
        """这个参数在窗口里对应哪个控件（子类把新控件登记进 _validate_widgets 即可）"""
        return (getattr(self, "_validate_widgets", None) or {}).get(key)

    def _apply_fixed_to_widgets(self, fixed):
        """
        把被自动纠正的值写回控件。

        为什么必须写回：不写回的话用户会以为"我填的还是原值"，而引擎那边已经按纠正后的值跑了
        —— 这正是目标4 要消灭的那种"静默"。
        """
        for key, value in (fixed or {}).items():
            widget = self._validate_widget_for(key)
            if widget is None:
                continue
            try:
                if hasattr(widget, "setValue"):           # QSpinBox / QDoubleSpinBox
                    widget.setValue(value)
                elif hasattr(widget, "edit"):             # file / dir 那种复合控件
                    widget.edit.setText(str(value))
                elif hasattr(widget, "setCurrentText"):   # QComboBox
                    widget.setCurrentText(str(value))
                elif hasattr(widget, "setChecked"):       # QCheckBox
                    widget.setChecked(bool(value))
                elif hasattr(widget, "setText"):          # QLineEdit
                    widget.setText(str(value))
            except (TypeError, ValueError):
                continue

    # ------------------------------------------------------------------
    # "运行参数"页的布局护栏（用户 2026.10.7 要求）
    #
    # 两条要求：
    #   ① **提示行不许改变窗口大小**：参数下面有富余空间就直接显示（不出滚动条）；
    #      空间不够才出滚动条（用户举的例子：直线节点）——而"微调框右移、右边留富余"之后，
    #      滚动条也不会盖住微调框（滚动条占的是 QScrollArea 右侧的**保留位**，不是浮在控件上）；
    #   ② **微调框要紧挨着前面的文本**（原来标签在左、微调框被 stretch 推到最右，中间一大段空白）。
    # ------------------------------------------------------------------
    def _wrap_run_params_in_scroll(self):
        """
        把"运行参数"的分组框放进一个 `QScrollArea`（窗口大小从此不受提示行影响）。

        为什么用滚动区：`QScrollArea + setWidgetResizable(True)` 天然就是用户要的语义 ——
        内容按自己的需要长高；装得下就没有滚动条，装不下自动出现竖直滚动条，**窗口本身不变**。
        """
        group = self.ui.findChild(QGroupBox, "groupBox_3")
        if group is None or group.parentWidget() is None:
            return
        parent_layout = group.parentWidget().layout()
        if parent_layout is None:
            return
        scroll = QScrollArea()
        scroll.setObjectName("run_params_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        # 横向**永不出现**滚动条：用户要的是"竖直那一条"，而且横向滚动区会跟竖直滚动条打架 ——
        # 竖直条一出现（宽 14px），视口变窄，内容就被判成"宽了 14px"，于是又冒出一条横向条（实测）。
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # 宽度上"忽略滚动区自己的 sizeHint"：QScrollArea 的 sizeHint 会把滚动条的宽度也算进去，
        # 直接挂上去会把参数窗口从 274px 顶到 312px（实测）—— 用 Ignored 让宽度仍由原有内容决定。
        scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        parent_layout.removeWidget(group)
        scroll.setWidget(group)          # setWidget 会把分组框重新挂到滚动区里
        parent_layout.addWidget(scroll)
        self.run_params_scroll = scroll

    def _tighten_param_rows(self):
        """
        把"运行参数"页里每行的**微调框挪到紧挨标签**的位置（用户 2026.10.7 要求）。

        做法：① 每行末尾补一个弹簧，把控件推到左边；② 所有行的标签统一成"最宽标签"的宽度，
        这样各行的控件左边缘对齐（否则"方法：""核大小："长度不同，控件会参差不齐）。
        只处理"标签 + 数值微调框"这种两栏行：
          · 下拉框 / 文件 / 目录 / 文本输入框不动 —— 那些本来就是需要宽度的控件（路径框要能看全路径）；
          · 被 `_hide_line_rows()` 显式藏起来的行也不动（`isHidden()` 判据，与父窗口是否已 show 无关）。
        """
        layout = getattr(self, "param_layout", None)
        if layout is None:
            layout = self.ui.findChild(QVBoxLayout, "verticalLayout_8")
        if layout is None:
            return
        rows = []
        max_label = 0
        for index in range(layout.count()):
            item = layout.itemAt(index)
            row = item.layout() if item is not None else None
            if row is None or row.count() < 2:
                continue
            label = row.itemAt(0).widget()
            widget = row.itemAt(1).widget()
            if not isinstance(label, QLabel) or not isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                continue
            if label.isHidden() or widget.isHidden():
                continue
            rows.append((row, label))
            max_label = max(max_label, label.sizeHint().width())
        for row, label in rows:
            label.setFixedWidth(max_label)
            row.setStretch(0, 0)
            row.setStretch(1, 0)
            row.addStretch(1)            # 富余宽度全留给右边（滚动条的保留位也在这里）
        # ★ 收口成"…参数行… → 提示行 → **唯一一根**弹簧"。
        #   为什么必须收口：父类这一次收编已经在末尾加过弹簧；而 GenericProcessDialog 是**动态追加**行、
        #   还会把提示行挪到末尾（`_hint_to_bottom()`）⇒ 那根弹簧会被留在中间，
        #   于是**两根弹簧分食富余空间**，提示行一出现参数行整体位移（实测 33px）。
        #   做法：先把已有的弹簧全部摘掉，再按"提示行 + 一根弹簧"的顺序放回去。
        hint = getattr(self, "validate_hint", None)
        for index in reversed(range(layout.count())):
            item = layout.itemAt(index)
            if item is not None and item.spacerItem() is not None:
                layout.takeAt(index)
        if hint is not None:
            layout.removeWidget(hint)
            layout.addWidget(hint)
        # 弹簧放在**提示行之后**：参数行固定在自己的高度上，富余高度留在最下面；
        # 提示出现时吃掉的是弹簧的空间，参数行动都不动；富余不够时由滚动区出竖直滚动条。
        layout.addStretch(1)

    def _grow_for_hint(self, label):
        """
        【2026.10.7 22:4x 起不再使用】把窗口长高来给提示行腾位置。

        用户随后要求"提示**不许改变窗口大小**"（有富余空间就直接显示、没空间就出滚动条），
        改成 `_wrap_run_params_in_scroll()` 的方案，本方法保留只作历史参考，不要再调用。
        """
        return 0

    def _show_validate_hint(self, corrections, errors):
        """
        显示 / 隐藏参数校验提示行：纠正了 = 黄字，纠正不了（会被引擎跳过）= 红字。
        **不弹任何对话框**（项目铁律：执行 / 渲染路径绝不弹 QMessageBox，提醒只写日志 / 提示）。
        """
        label = getattr(self, "validate_hint", None)
        if label is None:
            return
        parts = []
        if corrections:
            parts.append("已自动纠正：" + "；".join(corrections))
        if errors:
            # 文案尽量短（"结果数据"/提示行的宽度都紧张），详细说明在 tooltip 里
            parts.append("参数非法，执行时会被跳过（图像原样传给下游）：" + "；".join(errors))
        if not parts:
            label.clear()
            label.setVisible(False)
            # 注：**不还原窗口大小、也不长高窗口** —— 提示行装在滚动区里（见 _wrap_run_params_in_scroll），
            # 有富余空间它就占富余的地方，空间不够就出滚动条，窗口本身始终不变（用户 2026.10.7 要求）。
            return
        label.setText("　".join(parts))
        label.setStyleSheet("color: #b00020;" if errors else "color: #8a6d00;")
        # 注意：GenericProcessDialog 生成"运行参数"页时会把这一列里**已有的行**全藏起来
        # （`_hide_line_rows()`），所以显示时要显式 setVisible(True) 把它捞回来。
        label.setVisible(True)

    def _validate_params(self):
        """
        跑一遍这个算子的参数校验（批次4 目标4）——**窗口层**这一遍。
        :return: errors 列表（纠正不了的参数；窗口层不据此拦人，只提示）
        """
        if self.node is None:
            return []
        fixed, corrections, errors = run_validation(get_spec(self.node.name), self.node.params)
        if fixed:
            self.node.params.update(fixed)
            self._apply_fixed_to_widgets(fixed)
        self._show_validate_hint(corrections, errors)
        return errors

    def on_step_click(self):
        """点击'执行'按钮时触发：实现单步执行（只执行当前节点）"""
        self._update_params()  # 先保存当前UI中的参数
        self._validate_params()  # ★ 再跑一遍参数校验（批次4 目标4）：纠正 + 把结果显示出来

        # 拦截无效的 ROI 区域，即ROI区域全为0时弹出小窗口警告，避免代码出错
        if self.spin_roi_w.value() == 0 or self.spin_roi_h.value() == 0:
            QMessageBox.warning(self, "提示", "请输入ROI区域！")
            # 返回 False 表示执行被阻断，不进行后续关闭操作，
            # 用于判断ROI区域是否数值为 0，如果为 0 然后点击"确定"按钮则不关闭窗口
            return False

        if self.main_window:
            main_window = self.main_window
            # 当前没有静态图、但有视频/摄像头时，才走视频那条路
            video_ready = (main_window.current_static_image is None
                           and main_window.cap is not None and main_window.cap.isOpened())
            if not video_ready:
                # 静态图统一走主窗口的执行入口（它决定用哪张帧：
                # 有当前图就用当前图；图库为空但流程里有"图片源"就用它那张）
                # 计算 -> 显示 -> 写结果缓存 -> 更新日志，全项目只有这一条执行路径，
                # 所以从配置窗口点"执行"和从主界面点"单步执行"，结果完全一致。
                if main_window.run_flow_step(self.node):
                    # 更新检查到的直线的数量
                    self.update_result_count(main_window.last_detected_data)
                    # 执行成功，用于判断ROI区域是否数值为 0，如果不为 0 然后点击"确定"按钮则关闭窗口
                    return True
                # 既没有图、流程里也没有可用的图片源：run_flow_step 已经弹过提示，窗口保持不关闭
                return False

            # 视频 / 摄像头单步执行（老行为）
            # 告诉主窗口切换为"单步执行"状态
            main_window.video_processing_mode = "step"
            # 指定当前要单步执行的节点
            main_window.video_step_node = self.node
            # 主动触发刷新一帧画面，让视频流立刻响应单步检测
            main_window.update_frame()
            return True

        # 如果因为没有图片/视频而导致无法执行，也保持窗口不关闭
        return False

    def on_cont_click(self):
        """点击'连续执行'按钮时触发：按完整的流程图顺序执行"""
        self._update_params()  # 先保存当前UI中的参数
        self._validate_params()  # ★ 再跑一遍参数校验（批次4 目标4）：纠正 + 把结果显示出来

        # 拦截无效的 ROI 区域，即ROI区域全为0时弹出小窗口警告，避免代码出错
        if self.spin_roi_w.value() == 0 or self.spin_roi_h.value() == 0:
            QMessageBox.warning(self, "提示", "请输入ROI区域！")
            return

        if self.main_window:
            main_window = self.main_window
            # 当前没有静态图、但有视频/摄像头时，才走视频那条路
            video_ready = (main_window.current_static_image is None
                           and main_window.cap is not None and main_window.cap.isOpened())
            if not video_ready:
                # 静态图（或"图片源"兜底）：统一走主窗口的连续执行入口
                # （它会跑完整个流程图、显示结果、写结果缓存、刷新日志表格）
                if main_window.run_flow_continuous():
                    # 更新检查到的直线的数量
                    self.update_result_count(main_window.last_detected_data)

            # 视频 / 摄像头连续执行（老行为）
            else:
                # 告诉主窗口切换为"连续执行"状态
                main_window.video_processing_mode = "continuous"
                main_window.video_step_node = None
                # 主动触发刷新一帧画面，恢复完整的流程图检测
                main_window.update_frame()

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
            # 优先用"这个节点实际会收到的图"的尺寸（沿图像源绑定追到起点那张）——
            # 这样"图像源绑到图片源"的节点，ROI 尺寸跟着上游那张图，而不是主窗口当前图
            frame = None
            if self.node is not None and hasattr(self.main_window, "_node_input_frame"):
                frame = self.main_window._node_input_frame(self.node)
            if frame is None:
                frame = self.main_window.current_static_image

            # 如果拿到静态图片
            if frame is not None:
                h, w = frame.shape[:2]
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

        # 优先取"这个节点实际会收到的图"——沿它声明的"图像源"往上追到起点：
        # 绑了"图片源"就用图片源那张图，没绑就用主窗口当前那张图。
        # （这样图库里没有图片、只放了"图片源"节点时，框选也能用——用户实测报过这里弹提示。）
        if self.main_window is not None:
            if hasattr(self.main_window, "_node_input_frame"):
                img_bgr = self.main_window._node_input_frame(self.node)
            if img_bgr is None:
                img_bgr = self.main_window.current_static_image

        # 还是没有静态图，但有开启的摄像头/视频流
        if img_bgr is None and self.main_window is not None \
                and self.main_window.cap is not None and self.main_window.cap.isOpened():
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