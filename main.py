from collections import deque  # 拓扑排序要用到的队列（数据流引擎按连线顺序执行）

# 视频（视频源节点 / 摄像头帧）**整段共用一份参数**用的"视频槽"键：
# 参数按图片归档时用它当键，这样一段视频里每帧共用同一份参数（中途改参数、后面的帧按新的跑）。
VIDEO_ROI_KEY = "video"
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QFileDialog
)
# 打开主窗口，显示小窗口，模体ui窗口，设置流程图画布，导入文件
from PySide2.QtUiTools import QUiLoader # 导入ui
from PySide2.QtGui import QIcon # QIcon设置图标，QImage显示图像
from PySide2.QtCore import QTimer, Qt, QPointF # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死

import cv2
import json
import time
import os

from Detector import DetectorShape
from FlowChart import NodeItem, EdgeItem, FlowchartView
from FlowPages import FlowPageManager
from LineParamsDialog import LineParamsDialog
from CircleParamsDialog import CircleParamsDialog
from GrayParamsDialog import GrayParamsDialog
from GenericProcessDialog import GenericProcessDialog
from ImageGraphicsView import ImageGraphicsView
from ImageGalleryWidget import ImageGalleryWidget
from NodeRegistry import KIND_SINK, KIND_SOURCE, SOURCE_KEY, get_spec, result_bbox
# 参数校验（批次4 目标4）：规则表写在各算子里，这里只负责"跑一遍 + 拿结果"
from ParamRules import run_validation
from OutputOps import (SAVE_OVERLAY, SOURCE_CAMERA, SOURCE_IMAGE, SOURCE_VIDEO,
                       close_all_recordings, close_recording, set_input_name_provider,
                       set_overlay_frame_provider, set_round_info_provider)


uiloader = QUiLoader()


def _fingerprint_value(value):
    """
    算"页面内容指纹"时把参数值规范化。
    数字统一 round 到 4 位：避免 1 与 1.0、以及浮点误差（0.1+0.2）造成"明明一样却判成不同"。
    """
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("num", round(float(value), 4))
    return ("str", str(value))


def _result_note(results):
    """
    从某个算子这一轮的 results 里取"要写进执行日志的那句话"（批次4 目标4「参数校验」用）。

    引擎的老约定：results 里可以放 dict 带日志文案（`result_bbox()` 只认 tuple/list，
    所以检测结果里混一个 dict 不影响"ROI 继承"）。参数非法被跳过时就是靠它递文案的：
        results = [{"__note__": "参数非法（累加器阈值必须 ≥ 1），已跳过本节点"}]
    （dict 也不会被 `_draw_line()` / `_draw_circle()` 画出来 —— 它们只认长度 4 / 3 的元组。）
    :return: 文案字符串；没有就返回 None
    """
    for item in results or []:
        if isinstance(item, dict) and item.get("__note__"):
            return str(item["__note__"])
    return None


class MainWindow:
    # 视频 / 摄像头也当成一个"图片槽"，参数单独存一份，与图片的运行参数分开
    VIDEO_ROI_KEY = "video"

    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # 摄像头相关参数
        self.cap = None # 视频捕获对象
        self.timer = None # 刷新定时器
        self.camera_id = 0  # 默认摄像头ID，可通过设置菜单修改
        self._is_video_file = False  # 标记当前打开的是否为视频文件
        # 用于视频 / 摄像头的单步执行状态
        self.video_processing_mode = "continuous"  # "continuous" 表示连续执行，"step" 表示单步执行
        self.video_step_node = None  # 当前单步执行的节点对象

        # 存储当前加载的静态图片，用于删除方框后恢复原图
        self.current_static_image = None

        # 当前图片的标识，用于"参数和检测结果按图片分别保存"
        # 静态图片用 id(原图)；视频/摄像头统一用 VIDEO_ROI_KEY；None 表示还没有显示过任何图片/视频
        self.current_image_key = None
        # {id(原图): 文件路径}：把"图片标识"从内存 id 换成文件路径（跨会话稳定、可进方案文件）
        self._frame_paths = {}
        # "运行全部"执行期间为 True：此时执行日志**逐张累积**而不是每张覆盖
        self._log_accumulate = False
        # 用户在图库里**主动删掉**过的图片路径：以后执行时不要再自动加回图库（删了又回来是 bug）
        self._removed_paths = set()
        # 批量执行的"停止"标志：菜单里的"停止"把它置 True，批量循环每张之前检查一次
        self._batch_stop = False
        # 视频"自动播放"（勾了"自动切换"时点执行就按原帧率连续播）：定时器 + 两个状态标志
        self._video_timer = None
        self._video_playing = False
        self._video_tick_running = False

        # 相机源（目标3-M4，2026.10.7）——相机是**无界流**：没有帧游标、没有末尾、不循环，
        # 所以单独一个"正在出相机画面"的标志；_video_timer 与视频播放共用（同一时刻只播一种）。
        self._camera_playing = False
        # 一轮执行**只读一次**相机：读到的这一帧既当流程起点、又给"相机源"节点当输入
        # （否则一次执行会从设备里抠走两帧，画面和实际算的不是同一张）。
        self._camera_round = 0
        self._camera_frame_round = -1
        self._camera_round_frame = None
        # 当前 self.cap 对应的相机编号（换编号时才知道要不要重开设备）
        self._camera_device_id = None
        # 方案 A（用户 2026.10.7 拍板）：相机源节点**复用主窗口相机** —— 主窗口注入一个
        # "取最新一帧"的取帧器，节点自己不碰设备（局部导入，避免与"注册表 ← 分类模块"的顺序纠缠）。
        from SourceOps import set_camera_frame_provider
        set_camera_frame_provider(self._latest_camera_frame)
        # 输出类节点（M5「输出图像」）的"文件名默认值"要跟着"输入图片的文件名"走：
        # 节点自己拿不到图片路径（run() 只收到图像数组），所以由主窗口在每一轮执行前准备好，
        # 这里注入一个"取这一轮来源图片名"的取名字器（做法与上面那套一致）。
        self._current_input_name = ""
        # "带检测叠加"那张图（只有"输出图像"节点、而且保存内容选了叠加时才会有值）
        self._current_overlay_frame = None
        # "这一轮的执行上下文"：哪个节点、来源是图片/视频/相机、源帧率多少
        # （输出节点要靠它决定"自动"档存图片还是存视频、录制文件的标称帧率）
        self._round_info = {}
        self._bind_output_providers()

        # 每张图片上一次的执行结果缓存
        # 结构：{图片标识: {"frame": 画好检测结果的图, "data": 检测数据, "exec_info": 执行日志}}
        # 切换回某张图片时，如果这里存着它上一次的结果，就直接显示出来，不用再点执行按钮
        self.result_cache = {}

        # ★ 参数校验（批次4 目标4）：这一轮里"哪些节点的参数被自动纠正过什么"。
        #   键 = id(节点)、值 = 说明列表；每轮 _run_nodes 开头清空，
        #   执行日志的"结果数据"列末尾会把说明追上去 —— 值被改了必须让用户看见。
        self._param_corrections = {}

        # 执行日志表格的"节流"状态：
        # 视频模式下 update_frame 每 30ms 跑一次，而真刷一次表格要清空行、再为每个
        # 单元格 new 一个 QTableWidgetItem，每帧重建会明显拖慢画面。
        # 这里记住"上一次真正刷进表格的内容"和刷新时刻。
        self._exec_log_signature = None
        self._exec_log_flush_time = 0.0

        # 初始化选中节点变量，用来显示当前单击选中的节点
        self.selected_node = None

        # 保存主窗口最后一次的检测结果，用来显示直线检测的结果
        self.last_detected_data = None

        # 通过 findChild 找到被 tab 包裹的 graphicsView_video 控件
        # self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")
        # 原本使用的是 QLable 控件，现在改成使用graphicsView控件，方便对图片进行缩放，绘制ROI区域等
        view_video = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView_video")
        if view_video:
            parent_layout = view_video.parentWidget().layout()
            if parent_layout:
                # 实例化自定义视图 ImageGraphicsView 类
                new_view = ImageGraphicsView(view_video.parentWidget())
                # 原地替换，保留布局拉伸比例
                parent_layout.replaceWidget(view_video, new_view)
                view_video.deleteLater()
                # 保存新控件的引用
                self.image_view = new_view


        # 通过 findChild 获取文本 label 控件
        # 显示当前选中的流程图节点文本 lbl_current_node
        self.current_node_label = self.main_window.findChild(QtWidgets.QLabel, "lbl_current_node")

        # 通过 findChild 获取按钮控件名字Name
        # 打开摄像头
        self.camera_button = self.main_window.findChild(QtWidgets.QPushButton, "camera_button")
        # 关闭摄像头 或者 关闭图片
        self.close_button = self.main_window.findChild(QtWidgets.QPushButton, "close_button")
        # 打开图片
        self.open_button = self.main_window.findChild(QtWidgets.QPushButton, "open_button")
        # 顶部"菜单"按钮（main.ui 里一直有这个按钮，但从来没接过槽）
        self.menu_button = self.main_window.findChild(QtWidgets.QPushButton, "menu_button")
        # 单步执行按钮 btn_step_execute
        self.btn_step = self.main_window.findChild(QtWidgets.QPushButton, "btn_step_execute")
        # 连续执行按钮 btn_continuous_execute
        self.btn_continuous = self.main_window.findChild(QtWidgets.QPushButton, "btn_continuous_execute")


        # 设置按钮的点击 clicked 槽事件
        self.camera_button.clicked.connect(self.open_camera) # 开启摄像头按钮
        self.close_button.clicked.connect(self.close_camera) # 关闭摄像头按钮
        self.open_button.clicked.connect(self.open_file) # 导入图片或者视频
        self.btn_step.clicked.connect(self.on_step_execute) # 单步执行
        self.btn_continuous.clicked.connect(self.on_continuous_execute) # 连续执行
        if self.menu_button:
            # 点"菜单"按钮 = 把菜单栏里的菜单弹出来（效果和点菜单栏一样）
            self.menu_button.clicked.connect(self._show_menubar_menu)

        # 顶部那两个显眼的按钮（main.ui 里新加的：保存项目 / 导入项目）：
        # 功能和菜单栏"方案 → 保存方案 / 打开方案"完全一样，只是位置更显眼
        self.save_project_button = self.main_window.findChild(
            QtWidgets.QPushButton, "save_project_button")
        self.open_project_button = self.main_window.findChild(
            QtWidgets.QPushButton, "open_project_button")
        if self.save_project_button:
            self.save_project_button.clicked.connect(self.save_project)
        if self.open_project_button:
            self.open_project_button.clicked.connect(self.open_project)


        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

        # 点击设置->摄像头设置后 弹出 新窗口
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 方案（.vfproj）的保存 / 加载：菜单"方案"下的三个动作
        # 注意：方案文件路径是**按页面**记的（page["project_path"]），不是窗口级别的——
        # 新建的页面没有对应文件，"保存方案"会弹窗让用户选路径，绝不会覆盖别的页面的文件。
        self.last_source = None     # 最近打开的图片来源 {"kind": "image"/"video", "path": ...}
        self.action_open_project = self.main_window.findChild(QtWidgets.QAction, "action_open_project")
        self.action_save_project = self.main_window.findChild(QtWidgets.QAction, "action_save_project")
        self.action_save_project_as = self.main_window.findChild(QtWidgets.QAction, "action_save_project_as")
        if self.action_open_project:
            self.action_open_project.triggered.connect(self.open_project)
        if self.action_save_project:
            self.action_save_project.triggered.connect(self.save_project)
        if self.action_save_project_as:
            self.action_save_project_as.triggered.connect(self.save_project_as)

        # 创建树控件
        self.tree = self.main_window.tree
        # 树控件 tree 绑定双击事件，双击实现在画布view中创建方框流程图
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)


        # 流程图初始化，按照 FlowChart 中的 TestWindow 类的内容进行初始化和编写具体内容
        # 初始化节点和连线列表
        self.flow_nodes = []  # 存放所有方框
        self.flow_edges = []  # 存放所有连线

        self.current_dialog = None  # 用于记录当前是否打开了配置窗口

        # 启用左侧树控件的拖拽功能
        self.main_window.tree.setDragEnabled(True) # 拖动使能，可以拖动里面树枝控件
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction) # 拖拽时的行为是“复制”，而不是“剪切”

        # 改为"浏览器式"多页面流程图
        """页面管理（标签页、添加/删除页面、每页自己的方框和连线）都封装在 FlowPages.py 的FlowPageManager 类里，
        这里只把控件和两个回调交给它。"""
        self.flow_page_mgr = FlowPageManager(
            self.main_window.findChild(QtWidgets.QTabWidget, "flowWidget"),
            view_factory=lambda parent: FlowchartView(parent, main_window=self),
            on_page_switched=self._on_flow_page_switched,
            on_page_close_requested=self._confirm_close_flow_page,
        )
        self.flow_page_mgr.setup()
        # "当前页"的引用：换页时由 _on_flow_page_switched 整体替换，
        self._bind_current_flow_page()


        # 使用 QTableWidget 表格控件来显示运行日志，控件名字 Name 为 execution_log
        self.execution_log = self.main_window.findChild(QtWidgets.QTableWidget, "execution_log")
        if self.execution_log:
            # 5个头标题
            self.execution_log.setColumnCount(5)
            # 5个头标题名称，在ui文件里面已经设置，但是在这里用代码设置更直观
            # 多出来的"图像源"一列是数据流引擎的"体检表"：
            # 每个节点这一步是从哪一份图像开始算的，一眼就能看出来
            self.execution_log.setHorizontalHeaderLabels(
                ["执行序号", "执行时间", "模块", "图像源", "结果数据"])
            # 设置只读，不能修改内容
            self.execution_log.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            # 隐藏最左侧的垂直表头（行号）
            self.execution_log.verticalHeader().setVisible(False)


        # 初始化 图像预览进度条 QListWidget 控件，控件名字 Name 为 image_gallery
        self.image_gallery = self.main_window.findChild(QtWidgets.QListWidget, "image_gallery")
        if self.image_gallery:
            # 实例化逻辑类，传入 UI 控件自身
            self.gallery_widget = ImageGalleryWidget(self.image_gallery)
            # 连接图库点击信号到主窗口的显示函数
            self.gallery_widget.image_selected.connect(self._on_gallery_image_selected)
            # 点图库时顺便知道"这张图来自哪个文件"，用来同步"图片源"节点的路径
            self.gallery_widget.image_path_selected.connect(self._on_gallery_path_selected)
            # 工具栏（main.ui 里摆好、由 ImageGalleryWidget 收编）的几个信号
            self.gallery_widget.add_requested.connect(self.open_file)
            self.gallery_widget.add_folder_requested.connect(self.add_folder_to_gallery)
            self.gallery_widget.delete_requested.connect(self.delete_gallery_item)
            self.gallery_widget.run_all_requested.connect(self.run_all_images)
            # 菜单"停止"（急停）；"运行选中"在 v1.17 改成"范围模式"的选择，不再直接执行，
            # 所以这里只接 stop（run_selected_image() 保留为备用入口，当前 UI 没接）。
            self.gallery_widget.stop_requested.connect(self.stop_batch)



    def open_file(self):
        """点击打开按钮后弹出文件选择框，可以选择图片或者视频进行导入"""
        '''
        QFileDialog.getOpenFileNames()函数（注意结尾有 s，表示可以多选）:
        parent:main_window, 
        caption:打卡的界面的名字, 
        dir:默认选择的文件目录(默认不选择), 
        filter:文件类型过滤器, 中间用;;隔开
        option:对话框选项标注
        返回 file_path, _ :选中文件的绝对路径；选择的文件的名称(_表示忽略)
        '''
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.main_window,
            "选择图片或视频",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;视频文件 (*.mp4 *.avi *.mkv);;所有文件(*.*)"
        )
        if not file_paths:
            # 用户点了取消，或者一个文件都没有选中
            return

        # 无论当前是播放摄像头还是视频，先关闭释放资源
        self.close_camera()

        # 把选中的文件按后缀分成 图片 / 视频 两类（"打开文件"只负责选图片和视频，不管文件夹）
        image_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
        video_exts = ('.mp4', '.avi', '.mkv')
        image_paths = [p for p in file_paths
                       if os.path.isfile(p) and p.lower().endswith(image_exts)]
        video_paths = [p for p in file_paths
                       if os.path.isfile(p) and p.lower().endswith(video_exts)]

        # 1、选中了视频：只播放视频（视频和静态图片不能混着处理）
        if video_paths:
            if image_paths:
                # 同时选了图片和视频时只播放视频，避免静态图片和视频状态互相干扰
                QMessageBox.information(
                    self.main_window, "提示",
                    "选中的文件里既有图片又有视频，这里只播放视频，图片已忽略。"
                )
            if len(video_paths) > 1:
                # 一次只能播放一个视频，多选的只打开第一个
                QMessageBox.information(
                    self.main_window, "提示",
                    "一次只能播放一个视频，将打开第一个：\n" + os.path.basename(video_paths[0])
                )
            video_path = video_paths[0]
            # 处理视频文件
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                # 如果读取视频失败，则弹出小窗口警告
                QMessageBox.warning(self.main_window, "错误", "无法打开视频文件")
                return
            self.cap = cap
            self._is_video_file = True
            # 记下最近打开的来源（方案文件里会记它，便于知道参数属于哪张图/哪个视频）
            self.last_source = {"kind": "video", "path": video_path}

            # 视频是独立的一个"图片槽"，把各节点的运行参数切到它自己那一份
            self._switch_image_params(self.VIDEO_ROI_KEY)

            # 启动定时器循环读取视频帧，每隔 30ms 自动执行一次 update_frame
            if self.timer is not None:
                # 清除旧的定时器
                self.timer.stop()
                self.timer = None
            self.timer = QTimer()  # 创建新的定时器
            # 绑定处理函数
            self.timer.timeout.connect(self.update_frame)  # type:ignore
            self.timer.start(30)  # 30帧fps
            return

        # 2、选中了图片：批量导入（一张也可以）
        #    用户要求：读不出来的图片直接跳过，不弹任何提示
        if image_paths:
            loaded = []
            for image_path in image_paths:
                loaded.extend(self.import_image_path(image_path))

            if not loaded:
                # 一张都没读进来：静默结束（不弹提示）
                return

            # 记下最近打开的来源（方案文件里会记它）
            self.last_source = {"kind": "image", "path": loaded[0][1]}

            # 批量导入时主画面默认显示第一张，其余的点击图库缩略图切换
            # 新导入的图片还没有执行过，所以这里只显示原图
            self._show_static_image(loaded[0][0])
            if hasattr(self, "gallery_widget"):
                # 顺便把第一张点亮，让"图像源 (n/N)"标签显示正确
                self.gallery_widget.select_frame(loaded[0][0])

            # 如果此时刚好有配置窗口开着，通知它刷新尺寸为图片的实际大小
            if self.current_dialog and self.current_dialog.isVisible():
                self.current_dialog.refresh_size()
            return

        # 3、剩下的都是不支持的类型
        QMessageBox.warning(self.main_window, "错误", "不支持的文件格式")


    # ------------------------------------------------------------------
    # 方案（.vfproj）保存 / 加载
    # ------------------------------------------------------------------
    PROJECT_FORMAT = "VisionFlowNode.project"
    PROJECT_VERSION = 1

    def _page_title(self, page):
        """取某一页的标签标题（找不到就返回空串）"""
        try:
            index = self.flow_page_mgr.tab_widget.indexOf(page["widget"])
            if index >= 0:
                return self.flow_page_mgr.tab_widget.tabText(index)
        except RuntimeError:
            pass
        return ""

    def _page_fingerprint(self, page):
        """
        给"工作区里的一页"算内容指纹：标题 + 每个节点的名字/坐标/图像源绑定/参数 + 连线关系。
        用来判断"方案文件里的这一页，工作区里是不是已经有一模一样的了"。
        """
        nodes = page["nodes"]
        index_of = {node: index for index, node in enumerate(nodes)}
        node_items = []
        for node in nodes:
            pos = node.pos()
            binding = getattr(node, "input_source", None)
            if isinstance(binding, NodeItem):
                # 绑定的是某个节点对象 → 换成页内序号，和文件里的表示保持一致
                binding = index_of.get(binding)
            node_items.append((
                node.name,
                round(float(pos.x()), 1), round(float(pos.y()), 1),
                binding,
                tuple(sorted((str(key), _fingerprint_value(value))
                             for key, value in node.params.items())),
            ))
        edges = []
        for edge in page["edges"]:
            start = index_of.get(edge.start_node)
            end = index_of.get(edge.end_node)
            if start is not None and end is not None:
                edges.append((start, end))
        return (self._page_title(page).strip(), tuple(node_items), tuple(sorted(edges)))

    def _model_page_fingerprint(self, page_model):
        """给"方案文件里的一页模型"算指纹——结构必须和 _page_fingerprint 完全一致"""
        node_items = []
        for node in page_model["nodes"]:
            node_items.append((
                node["name"],
                round(float(node["x"]), 1), round(float(node["y"]), 1),
                node.get("input_source"),
                tuple(sorted((str(key), _fingerprint_value(value))
                             for key, value in node["params"].items())),
            ))
        edges = tuple(sorted(tuple(edge) for edge in page_model["edges"]))
        return (page_model["title"].strip(), tuple(node_items), edges)

    def _add_node_to_page(self, page, name, pos, mark_dirty=True):
        """
        在指定页里建一个节点（拖拽添加与加载方案共用）。
        :param mark_dirty: 加载方案时传 False —— 从文件读进来的内容不算"未保存的改动"
        """
        node = NodeItem(name, pos)
        page["view"].flow_scene.addItem(node)
        # 方框被拖动时：刷新连线 + 把这一页标记成"有改动"
        node.positionChanged.connect(lambda *_: self._on_node_moved(page))  # type:ignore
        page["nodes"].append(node)
        if mark_dirty:
            self.flow_page_mgr.mark_dirty(page)
        return node

    def _add_edge_to_page(self, page, start_node, end_node, mark_dirty=True):
        """在指定页里连一条线（同一对起终点不重复连）"""
        for edge in page["edges"]:
            if edge.start_node == start_node and edge.end_node == end_node:
                return None
        edge = EdgeItem(start_node, end_node)
        page["view"].flow_scene.addItem(edge)
        page["edges"].append(edge)
        if mark_dirty:
            self.flow_page_mgr.mark_dirty(page)
        return edge

    def _on_node_moved(self, page=None):
        """方框被拖动：刷新连线，并把所在页面标记成"有改动" """
        self.flow_page_mgr.mark_dirty(page or self.flow_page_mgr.current_page)
        self.update_all_edges()

    def _collect_page(self, page):
        """把"一页流程图"收成可 JSON 化的 dict（节点 + 连线）"""
        nodes = page["nodes"]
        index_of = {node: index for index, node in enumerate(nodes)}
        nodes_data = []
        for index, node in enumerate(nodes):
            pos = node.pos()
            binding = getattr(node, "input_source", None)
            if isinstance(binding, NodeItem):
                # 绑定的是某个上游节点：存它的页内序号（不在本页就退回"自动"）
                binding = index_of.get(binding, None)
            nodes_data.append({
                "id": index,
                "name": node.name,
                "x": round(float(pos.x()), 2),
                "y": round(float(pos.y()), 2),
                "input_source": binding,
                "params": dict(node.params),
                # 顺便把"按文件路径存的其它图片参数"也存进方案文件，
                # 这样"运行全部"给每张图调好的参数下次打开还在（原来是只存当前那一份）
                "params_by_image": self._node_params_by_image(node),
            })
        edges_data = []
        for edge in page["edges"]:
            start = index_of.get(edge.start_node)
            end = index_of.get(edge.end_node)
            if start is not None and end is not None:
                edges_data.append([start, end])
        return {
            "title": self._page_title(page),
            "nodes": nodes_data,
            "edges": edges_data,
        }

    def _collect_project(self):
        """
        把**当前这一页**收成方案 dict（"保存方案"用）。

        规则：**一个方案文件只装一页**（一个文件对应一个流程图窗口）——
        以前是"把整张工作区的所有页面都写进去"，结果打开某个方案会把当时开着的
        其它页面一起带出来，用户反馈过这个问题，所以改成只存当前页。

        节点参数存的是"当前图片那一份"（node.params）：参数是按图片归档的、归档键用的是
        id(原图)，跨进程不可复现，所以方案里只带当前这一份，另外用 last_source 记下它属于谁。
        """
        page = self.flow_page_mgr.current_page
        pages_data = [self._collect_page(page)] if page is not None else []
        return {
            "format": self.PROJECT_FORMAT,
            "version": self.PROJECT_VERSION,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "current_page": 0,
            "last_source": self.last_source,
            "pages": pages_data,
        }

    def save_project(self):
        """
        "保存方案"：**这一页**已经有对应文件就直接存；没有（例如刚新建的页面）就当"另存为"，
        弹窗让用户选路径——绝不拿别的页面用过的文件路径去覆盖。
        """
        page = self.flow_page_mgr.current_page
        path = page.get("project_path") if page is not None else None
        if path:
            return self._write_project_file(path)
        return self.save_project_as()

    def save_project_as(self):
        """菜单"另存为…"：弹文件对话框选路径"""
        page = self.flow_page_mgr.current_page
        path = page.get("project_path") if page is not None else None
        if path:
            default_name = os.path.basename(path)
        else:
            # 一个文件对应一个流程图页面：默认就用这一页的标签名当文件名
            title = self._page_title(page).strip() or "方案"
            default_name = "{0}.vfproj".format(title)
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "保存方案", default_name,
            "VisionFlowNode 方案 (*.vfproj);;所有文件 (*.*)")
        if not path:
            return False
        if not path.lower().endswith(".vfproj"):
            path += ".vfproj"
        return self._write_project_file(path)

    def _write_project_file(self, path):
        """把当前流程写进方案文件（JSON / UTF-8 / 缩进 2）"""
        try:
            data = self._collect_project()
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
        except Exception as exc:
            QMessageBox.warning(self.main_window, "保存方案失败", "写入文件时出错：\n{0}".format(exc))
            return False
        page = self.flow_page_mgr.current_page
        if page is not None:
            # 这一页从此认这个文件（新建的页面也就有了自己的方案文件）
            page["project_path"] = path
        # 只把"刚存过的这一页"清干净：别的页面如果还有改动，仍然算未保存
        self.flow_page_mgr.clear_dirty(page)
        self._update_project_title()
        return True

    def _update_project_title(self):
        """把**当前这一页**对应的方案文件名显示到窗口标题上"""
        page = self.flow_page_mgr.current_page
        path = page.get("project_path") if page is not None else None
        name = os.path.basename(path) if path else "未保存的方案"
        try:
            self.main_window.setWindowTitle("VisionFlowNode - {0}".format(name))
        except RuntimeError:
            pass

    def open_project(self):
        """菜单"打开方案"：选文件后交给 load_project()"""
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, "打开方案", "",
            "VisionFlowNode 方案 (*.vfproj);;所有文件 (*.*)")
        if not path:
            return False
        return self.load_project(path)

    def load_project(self, path):
        """
        加载方案：先解析 + 校验（这一步完全不碰界面），全部通过之后才重建页面；
        校验不过就原样返回，不破坏当前流程图。
        """
        # 1、读文件 + 基本校验
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception as exc:
            QMessageBox.warning(self.main_window, "打开方案失败", "读取或解析文件出错：\n{0}".format(exc))
            return False
        if not isinstance(data, dict) or data.get("format") != self.PROJECT_FORMAT:
            QMessageBox.warning(self.main_window, "打开方案失败", "这不是 VisionFlowNode 的方案文件。")
            return False
        version = data.get("version")
        if not isinstance(version, int) or version > self.PROJECT_VERSION:
            QMessageBox.warning(
                self.main_window, "打开方案失败",
                "方案版本（{0}）比当前程序支持的版本（{1}）新，打不开。".format(version, self.PROJECT_VERSION))
            return False
        pages = data.get("pages")
        if not isinstance(pages, list) or not pages:
            QMessageBox.warning(self.main_window, "打开方案失败", "方案里没有任何流程图页面。")
            return False

        # 2、整理成"待应用模型"（只读数据，界面还没动）
        model, warnings = self._build_project_model(pages)

        # 3、去重：文件里与"工作区里已有的页面"内容完全相同的页，不再重复创建
        #    （不然"保存 → 再打开同一个文件"会把页面越堆越多：Flow、Flow(2)、Flow(2)(2)…）
        existing = set(self._page_fingerprint(page) for page in self.flow_page_mgr.pages)
        kept_pages = []
        skipped_pages = 0
        for page_model in model["pages"]:
            fingerprint = self._model_page_fingerprint(page_model)
            if fingerprint in existing:
                skipped_pages += 1
                continue
            existing.add(fingerprint)   # 同一个文件里若有重复页，也只建一份
            kept_pages.append(page_model)
        model["pages"] = kept_pages
        if skipped_pages:
            warnings.append("有 {0} 页与工作区里已有的页面完全相同，已跳过".format(skipped_pages))
        if not kept_pages:
            # 文件里的页面工作区里全都有：什么都不用建，提示一句就好
            QMessageBox.information(
                self.main_window, "打开方案",
                "这个方案里的 {0} 页与当前工作区里已有的页面完全相同，没有新增页面。".format(skipped_pages))
            return True

        # 4、真正重建（到这里才开始动界面）
        try:
            self._apply_project(model, data, path)
        except Exception as exc:
            QMessageBox.warning(self.main_window, "打开方案失败", "重建流程图时出错：\n{0}".format(exc))
            return False

        self._update_project_title()
        if warnings:
            QMessageBox.information(
                self.main_window, "打开方案",
                "方案已加载；下面是 {0} 条提示：\n{1}".format(len(warnings), "\n".join(warnings)))
        return True

    def _build_project_model(self, pages):
        """
        把方案文件里的页面数据整理成"待应用模型"：
        没注册的算子、悬空的连线、无效的图像源绑定都会被过滤掉，并记进 warnings。
        """
        model_pages = []
        warnings = []
        for page_index, page in enumerate(pages):
            if not isinstance(page, dict):
                warnings.append("第 {0} 页数据格式不对，已跳过".format(page_index + 1))
                continue
            title = str(page.get("title") or "Flow{0}".format(page_index + 1))
            nodes = []
            raw_nodes = page.get("nodes") if isinstance(page.get("nodes"), list) else []
            for raw in raw_nodes:
                if not isinstance(raw, dict):
                    continue
                name = str(raw.get("name") or "")
                if get_spec(name) is None:
                    warnings.append("算子“{0}”没有实现，已跳过".format(name or "(空)"))
                    continue
                try:
                    x = float(raw.get("x", 0.0))
                    y = float(raw.get("y", 0.0))
                except (TypeError, ValueError):
                    x, y = 0.0, 0.0
                params = raw.get("params")
                # "按图片（文件路径）存的其它参数"：原样带进来，供 _apply_project 还原到节点上
                params_by_image = raw.get("params_by_image")
                nodes.append({
                    "name": name,
                    "x": x,
                    "y": y,
                    "params": dict(params) if isinstance(params, dict) else {},
                    "params_by_image": dict(params_by_image) if isinstance(params_by_image, dict) else {},
                    "input_source": raw.get("input_source", None),
                    "old_id": raw.get("id"),
                })

            # 连线：两端都要能对上"留下来的节点"，自环直接丢掉
            index_by_old_id = {}
            for index, node in enumerate(nodes):
                index_by_old_id.setdefault(node["old_id"], index)
            edges = []
            raw_edges = page.get("edges") if isinstance(page.get("edges"), list) else []
            for raw_edge in raw_edges:
                if not (isinstance(raw_edge, (list, tuple)) and len(raw_edge) == 2):
                    warnings.append("第 {0} 页有一条连线格式不对，已跳过".format(page_index + 1))
                    continue
                start = index_by_old_id.get(raw_edge[0])
                end = index_by_old_id.get(raw_edge[1])
                if start is None or end is None or start == end:
                    warnings.append("第 {0} 页有一条连线指向不存在的节点，已跳过".format(page_index + 1))
                    continue
                edges.append([start, end])

            # 图像源绑定：数字要能对上本页节点；对不上、或者指向自己，就退回"自动"
            for index, node in enumerate(nodes):
                binding = node["input_source"]
                target = None
                if isinstance(binding, int) and not isinstance(binding, bool):
                    target = index_by_old_id.get(binding)
                elif isinstance(binding, str) and binding == SOURCE_KEY:
                    target = SOURCE_KEY
                if target is None or target == index:
                    target = None
                node["input_source"] = target

            model_pages.append({"title": title, "nodes": nodes, "edges": edges})
        return {"pages": model_pages}, warnings

    def _apply_project(self, model, data, project_path=None):
        """
        按模型把这些页面**追加**到现有流程后面（已有的页面一律保留、不动），
        并恢复节点参数、图像源绑定、连线（界面从这里才开始变）。
        :param project_path: 这些页来自哪个方案文件（记到 page["project_path"] 上，
                             以后在这一页点"保存方案"就直接存回这个文件）
        """
        titles = [page["title"] for page in model["pages"]]
        new_pages = self.flow_page_mgr.append_pages(titles)
        if not new_pages:
            return

        # 1、逐页建节点 → 恢复参数 → 恢复图像源绑定 → 连连线
        #    （mark_dirty=False：从文件读进来的内容不算"未保存的改动"）
        for page, page_model in zip(new_pages, model["pages"]):
            created = []
            for node_model in page_model["nodes"]:
                node = self._add_node_to_page(
                    page, node_model["name"], QPointF(node_model["x"], node_model["y"]),
                    mark_dirty=False)
                node.params.clear()
                node.params.update(node_model["params"])
                # 还原"按图片（文件路径）存的参数"：以后切到同一张图就能拿回各自那一份
                store = self._get_node_params_store(node)
                store.clear()
                for key, value in (node_model.get("params_by_image") or {}).items():
                    if isinstance(key, str) and isinstance(value, dict):
                        store[key] = dict(value)
                created.append(node)
            for index, node_model in enumerate(page_model["nodes"]):
                binding = node_model["input_source"]
                if binding == SOURCE_KEY:
                    created[index].input_source = SOURCE_KEY
                elif isinstance(binding, int) and 0 <= binding < len(created):
                    created[index].input_source = created[binding]
                else:
                    created[index].input_source = None
            for start, end in page_model["edges"]:
                self._add_edge_to_page(page, created[start], created[end], mark_dirty=False)

        # 2、参数同时写进"当前图片"的存档，否则切走再切回来就被清空了
        if self.current_image_key is not None:
            for page in new_pages:
                for node in page["nodes"]:
                    self._get_node_params_store(node)[self.current_image_key] = dict(node.params)

        # 3、新追加的页面 = "刚打开的样子"：不算未保存改动，并记住它们来自哪个方案文件
        for page in new_pages:
            self.flow_page_mgr.clear_dirty(page)
            page["project_path"] = project_path

        # 4、切到方案里记录的那一页（它是新追加页面里的第 current_index 页）
        current_index = data.get("current_page", 0)
        if not isinstance(current_index, int) or not (0 <= current_index < len(new_pages)):
            current_index = 0
        try:
            first_index = self.flow_page_mgr.tab_widget.indexOf(new_pages[0]["widget"])
        except RuntimeError:
            first_index = -1
        if first_index >= 0:
            # 走正常换页流程：主窗口引用重新绑定、旧页参数也会存好
            self.flow_page_mgr.tab_widget.setCurrentIndex(first_index + current_index)
        else:
            # 兜底：标签栏状态异常时，至少把当前页和引用绑过去
            self.flow_page_mgr.current_page = new_pages[current_index]
            self._bind_current_flow_page()
        self.selected_node = None
        if self.current_node_label:
            self.current_node_label.setText("未选中节点")

        # 5、刷新画面与日志：有图就按新流程重跑一次，没图就只把连线刷新一下
        self.update_all_edges()
        if self.current_static_image is not None:
            self._execute_static(self.current_static_image, "continuous")

    @staticmethod
    def _path_key(path):
        """路径比较用的键（绝对化 + 大小写不敏感），用于"用户删过的图别再自动加回来"这类判断"""
        return os.path.normcase(os.path.abspath(path)) if path else ""

    def _is_removed_path(self, path):
        """这张图是不是被用户在图像列表里主动删掉过"""
        key = self._path_key(path)
        return bool(key) and key in getattr(self, "_removed_paths", set())

    def _image_key_of(self, frame):
        """
        这张图在"参数存档 / 结果缓存 / 缩放记录"里用的标识。

        2026.10.6 起优先用**文件路径**（跨会话稳定，也能写进方案文件让"每图一套参数"持久化）；
        没有路径的（摄像头帧、测试图、测试视频帧）才退回 id(frame)。
        """
        if frame is None:
            return None
        known = self._frame_paths.get(id(frame))
        if known:
            return known
        video = self._video_source_node()
        if video is not None and video.params.get("video_path"):
            # 视频帧：**结果缓存**按"路径#帧号"分开（这样回看得到某一帧的结果，也不会几千帧共用一个键）；
            # 画面缩放/平移走 _display_key_of()（整段共用一个键）——两者刻意分开，别混。
            index = int(video.params.get("frame_index") or 0)
            return "{0}#{1}".format(video.params["video_path"], index)
        return id(frame)

    @staticmethod
    def _node_params_by_image(node):
        """
        取一个节点"按图片存的参数"里**键是文件路径**的那部分（存进方案文件用）。

        id(原图) 这种键跨进程没有意义，所以只导出字符串键（路径 / 视频槽）的那几份。
        """
        store = getattr(node, "params_per_image", None)
        if not isinstance(store, dict):
            return {}
        return {key: dict(value) for key, value in store.items() if isinstance(key, str)}

    def _get_node_params_store(self, node):
        """
        取出某个节点"按图片分别保存的运行参数"字典，没有就现场建一个。
        结构：{图片标识: {参数名: 参数值, ...}}（整份 node.params 的副本）
        """
        store = getattr(node, 'params_per_image', None)
        if store is None:
            store = {}
            node.params_per_image = store
        return store

    def _is_source_node(self, node):
        """
        这个节点是不是"流程起点"（图片源）。

        起点节点的参数（来源 / 路径）属于**流程图本身**，不按图片归档 ——
        否则用户一换图库里的图，图片源的路径就被清空了，它会退回"当前图像"，
        于是"绑了图片源却处理当前图"（和当年"图像源绑定绝不能存进 params"是同一类坑）。
        """
        spec = get_spec(node.name)
        return spec is not None and spec.kind == KIND_SOURCE

    def _is_flow_level_node(self, node):
        """
        这个节点的参数是不是**流程级配置**（不按图片归档）。

        除了起点节点（图片源 / 视频源 / 相机源），输出类节点（"输出图像"，M5，2026.10.7）也一样：
        它的"输出目录 / 文件名"属于**这个节点自己的配置**，跟"当前打开的是哪张图"没有任何关系。
        为什么必须跳过：`_load_node_params()` 是**先 `node.params.clear()` 再载入**，
        如果它跟着图片走，用户一换图（新图名下没有快照）这些参数就被清空了 ——
        和当年"图片源路径被切图清掉"是同一类坑（用户实测报过）。
        """
        spec = get_spec(node.name)
        return spec is not None and spec.is_flow_level

    def _save_node_params(self, nodes, image_key):
        """
        把一批节点的当前参数存到某个图片名下。
        :param nodes: 要存的节点列表（一般是某一页流程图里的节点）。
        :param image_key: 图片标识；为 None 表示还没显示过图片/视频，这时不存。
        """
        if image_key is None:
            return
        for node in nodes:
            if self._is_flow_level_node(node):
                # 流程级配置（起点节点 / 输出节点）不参与按图片归档，见 _is_flow_level_node
                continue
            store = self._get_node_params_store(node)
            snapshot = dict(node.params)
            # 空字典不存：既省内存，也避免往 params 里灌 None 导致后面切片报错
            if snapshot:
                store[image_key] = snapshot

    def _load_node_params(self, nodes, image_key):
        """
        把一批节点的参数换成某个图片名下的那一份。
        :param nodes: 要换参数的节点列表（一般是某一页流程图里的节点）。
        :param image_key: 图片标识。
        """
        for node in nodes:
            if self._is_flow_level_node(node):
                # 流程级配置（起点节点 / 输出节点）不跟着图片走，切图时保持原样
                continue
            store = self._get_node_params_store(node)
            # 先清空：这张图片以前没设置过的话，就保持空，
            # 各处的 .get(参数名, 默认值) 会自动取默认值（ROI 的默认宽高就是当前这张图的尺寸）
            node.params.clear()
            snapshot = store.get(image_key)
            if snapshot:
                node.params.update(snapshot)

    def _switch_image_params(self, new_key):
        """
        切换当前图片时，把"当前这一页"每个节点的运行参数按图片分别存档 / 载入。

        存档的是节点参数的全部内容：ROI 的 XYHW / XYR（含形状、是否隐藏黄框），以及运行参数，所以每张图片的参数完全独立，互不继承。。

        :param new_key: 新图片的标识。静态图片用 id(原图)，视频/摄像头用 VIDEO_ROI_KEY。
        """
        if new_key == self.current_image_key:
            # 还是同一张图片
            return

        # 1、先把当前页每个节点的参数存到上一张图片名下（只处理"当前页"的节点）
        self._save_node_params(self.flow_nodes, self.current_image_key)

        # 2、再按新图片取参数（这张图片没设置过就会是空，各处自动用默认值）
        #    注意：如果之前还没有关联任何图片 / 视频（current_image_key 是 None），
        #    说明用户是在"还没开图"的时候就把参数设好了（比如先双击节点调好 ROI 再打开图片），
        #    这份参数要留给新图片当初始值，不能在这里清掉——否则刚设好的 ROI 会凭空消失。
        if self.current_image_key is not None:
            self._load_node_params(self.flow_nodes, new_key)

        self.current_image_key = new_key

    def _result_cache_key(self, image_key, mode):
        """
        检测结果缓存的键 = 图片 × 流程图页面 × 执行方式。
        这样同一张图片在不同流程图页面上的执行结果各自独立，
        并且**单步执行的结果不会把整流程执行的结果覆盖掉**。
        :param mode: "step" 单步执行；"continuous" 连续执行
        """
        return (image_key, self.flow_page_mgr.page_key(), mode) # type:ignore

    def _show_static_image(self, frame):
        """
        显示一张静态图片（导入图片、点击图库缩略图切换图片时调用）。
        规则：
            这张图片之前点过"单步执行"/"连续执行" -> 直接显示它上一次的检测结果，不用再点执行按钮；
            这张图片还没执行过 -> 只显示原图，不显示任何检测结果。
        另外，切换图片时会把每个节点的运行参数（ROI + 算法参数）按图片分别存档 / 载入，
        所以每张图片的参数也是独立的。

        :param frame: OpenCV BGR 原图（内部只用副本，不会污染原图）。
        """
        if frame is None:
            return

        # 记住当前图片，后面点执行按钮都是基于它计算
        self.current_static_image = frame

        # 切换图片：把每个节点的运行参数按图片分别存档 / 载入
        # （标识优先用文件路径，见 _image_key_of：跨会话稳定、能写进方案文件）
        image_key = self._image_key_of(frame)
        self._switch_image_params(image_key)

        # 取"这张图片 × 这一页流程图"上一次的执行结果：
        # 优先取连续执行（整条流程，画面和日志表最完整），没有连续结果时才取单步执行的
        cached = self.result_cache.get(self._result_cache_key(image_key, "continuous"))
        if cached is None:
            cached = self.result_cache.get(self._result_cache_key(image_key, "step"))
        if cached is not None:
            # 有缓存：直接显示上次画好检测结果的那张图
            self._display_image(cached["frame"], image_key)
            # 顺便把"上次检测数据"和日志表格也同步过来，保证和画面对得上
            self.last_detected_data = cached["data"]
            self._update_execution_log(cached["exec_info"] or [])
            return

        # 没有缓存（这张图片还没执行过）：只显示原图
        self._display_image(frame.copy(), image_key)

        # 没执行过就没有检测结果，把上一次的数据和日志一并清空
        self.last_detected_data = None
        self._update_execution_log([])

    def _execute_static(self, frame, mode, node=None, adopt_frame=True):
        """
        对一张静态图片执行检测并把结果显示出来。
        只有"单步执行"、"连续执行"两个按钮会调用它。
        执行完会把结果按图片缓存起来（见 self.result_cache），
        以后再切回这张图片时可以直接显示这次的结果，不用再点按钮。

        :param frame: OpenCV BGR 原图。
        :param mode: "step" 单步执行（跑 node 及其上游）；"continuous" 连续执行（跑整个流程图）。
        :param node: 单步执行时要执行的节点。
        :param adopt_frame: 是否把这一帧记成"当前静态图片"。
               从"打开的图片 / 图库 / 视频"来的帧传 True（老行为）；
               从**图片源节点兜底**来的帧传 False——它只是"这一轮驱动流程用的帧"，
               不该篡改"主窗口当前打开的是哪张图"（否则用户换了图片源的文件、
               再点执行时还会拿旧的那张，用户实测报过这个问题）。
        :return: 检测到的数据列表 data。
        """
        if adopt_frame:
            # 保证"当前静态图片"就是这次要算的图，后面再点执行按钮时用的还是它
            self.current_static_image = frame

        # 复制图像处理，防止污染原图
        work_frame = frame.copy()

        if mode == "continuous":
            # 调用连续执行_run_flow_pipeline，接收返回的 data 和日志 exec_info
            # stop_at = 当前选中的节点：连续执行只跑到它为止（用户 2026.10.7 定的语义）
            work_frame, data, exec_info = self._run_flow_pipeline(
                work_frame, stop_at=self.selected_node)
        else:
            # 调用单步执行_run_flow_pipeline_step，只执行 node 这一个节点
            # （单步执行现在也会返回一行日志，否则"画面有结果、日志表却是空的"）
            work_frame, data, exec_info = self._run_flow_pipeline_step(work_frame, node)

        # 更新执行日志表格：单步 / 连续都走这里
        self._update_execution_log(exec_info)

        # 显示处理后的图像；传图片标识让每张图片的缩放互相独立
        # （缓存键用 _image_key_of；画面键用 _display_key_of —— 视频帧/相机帧的画面键整段共用）
        image_key = self._image_key_of(frame)
        camera_used = self._camera_used_by(node, mode)
        display_key = self._camera_display_key(node, mode) if camera_used else None
        self._display_image(work_frame, display_key or self._display_key_of(frame))

        # ★ 相机帧**不进结果缓存**（用户 2026.10.7 定）：相机是无界流，每一帧都是新内容，
        #   缓存既没有"切回来还能看到上次结果"的意义，又会让内存随运行时间线性增长。
        if not camera_used:
            # 把这次的结果缓存到"这张图片 × 这一页流程图 × 本次执行方式"名下
            # 下次切回这张图片（或这一页）时可以直接显示，不用再点一次执行按钮。
            # work_frame 本来就是 frame 的独立副本，直接存起来即可。
            self.result_cache[self._result_cache_key(image_key, mode)] = {
                "frame": work_frame,
                "data": data,
                "exec_info": exec_info,
            }

        # 保存数据并同步窗口
        self.last_detected_data = data  # 保存给以后打开的窗口使用
        if self.current_dialog and self.current_dialog.isVisible():
            self.current_dialog.update_result_count(data)

        # 图片源节点用到的图片也放进图库列表（用户 2026.10.5 要求：不管是"打开文件"导入的，
        # 还是图片源节点指定的，都要在图库里看得见）
        self._ensure_source_images_in_gallery()
        # 相机源（目标3-M4，2026.10.7）：相机是**无界流**——
        #   · 没有帧游标可以推进（视频那套 "一次执行 = 前进一帧" 不适用）；
        #   · 参数**复用视频槽**（用户定："相机和视频共用一份参数"），跑完把这份存回槽里；
        #   · 勾了"自动切换"就接着自动出画面（走 _maybe_start_video_playback 里分派的那条相机分支）。
        if self._camera_used_by(node, mode):
            self._save_node_params(self.flow_nodes, VIDEO_ROI_KEY)
            self._maybe_start_video_playback(node, mode)
        # "一次执行 = 前进一帧"（用户 2026.10.6 定）：这一轮真的用到视频源的话，把帧号 +1。
        # 放在"执行结束"这里而不是 run() 里，是为了让同一轮里多个节点共用同一帧。
        if self._video_used_by(node, mode):
            self._advance_video_cursor()
            # 视频的**参数整段共用一份**（用户 2026.10.6 定的语义）：跑完把当前这份参数存进"视频槽"
            # （VIDEO_ROI_KEY，模块顶部已定义），这样切去别的图、再切回来点视频执行时，参数不会被清空。
            self._save_node_params(self.flow_nodes, VIDEO_ROI_KEY)
            # 结果缓存加个上限（尾巴之二，2026.10.7 补）：视频逐帧跑会不断新增键，
            # 超过 400 条就把最旧的丢掉（FIFO 近似 LRU），免得越跑越吃内存。
            if len(self.result_cache) > 400:
                for old_key in list(self.result_cache)[:-400]:
                    self.result_cache.pop(old_key, None)
            # 勾了"自动切换"时：这一轮结束后**接着自动播放**（用户 2026.10.6 要求：
            # "点自动切换后再点执行，视频会转成自动播放，不用一帧一帧点；点停止就停"）。
            self._maybe_start_video_playback(node, mode)

        return data



    def _display_image(self, img, image_key=None):
        """
        将 OpenCV 图像转换并渲染到 UI 的 QGraphicsView 上
        :param image_key: 静态图片的标识（用 id(原图) 传入）。
                          传入后这张图片的缩放 / 平移会被单独记住，各图片互不影响；
                          不传（视频 / 摄像头的连续帧）时保持当前缩放不变。
        """
        if not hasattr(self, 'image_view'):
            return
        # 直接调用自定义视图 ImageGraphicsView 类的 set_image 方法，无需手动缩放
        self.image_view.set_image(img, image_key)


    # ------------------------------------------------------------------
    # 相机设备开关（内部 API，目标3-M4 抽出来的，2026.10.7）
    #
    # 为什么单独抽一层：主窗口原来那个"打开摄像头 / 关闭"按钮以后可能删掉（用户 2026.10.7 说），
    # 相机源节点要靠这两个函数自己开关设备，不能再依赖按钮那条老路径。
    # ------------------------------------------------------------------
    def _open_camera_device(self, camera_id=0, quiet=True):
        """
        打开相机设备（内部 API）。

        · 已经开着、而且就是同一个编号 ⇒ **直接复用**，不重开（方案 A：节点复用主窗口相机）；
        · 开着别的编号 ⇒ 先关掉再开新的；
        · 打不开 ⇒ 返回 False；quiet=False 时才弹原来那个警告小窗口（按钮路径用）。
        :return: True = 相机可用
        """
        camera_id = int(camera_id or 0)
        cap = self.cap
        if cap is not None and cap.isOpened():
            if getattr(self, "_camera_device_id", None) == camera_id:
                return True
            self._release_camera_device()
        new_cap = cv2.VideoCapture(camera_id)
        if not new_cap.isOpened():
            try:
                new_cap.release()
            except Exception:
                pass
            if not quiet:
                # 如果识别不到摄像头标签，则弹出警告的小窗口
                QMessageBox.warning(self.main_window, "错误", "无法打开摄像头，请检查设备连接")
            return False
        self.cap = new_cap
        self._camera_device_id = camera_id
        self._camera_round_frame = None
        self.camera_id = camera_id          # 和主窗口老变量（设置菜单里那个编号）保持一致
        return True

    def _release_camera_device(self):
        """
        关闭相机设备、释放资源（内部 API）——用户 2026.10.7 定的分工：
        **"停止"不关相机（只停画面，保留最后一帧），"删除"才关相机**。

        M5-2 起：相机一关，正在录的视频也跟着收尾（流没了，文件必须 release）。
        """
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        cap, self.cap = self.cap, None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        self._close_recordings("相机已关闭")
        self._camera_device_id = None
        # 丢掉"这一轮读到的那一帧"：相机都关了，别让取帧器再把它交出去
        self._camera_round_frame = None
        self._camera_frame_round = -1
        # 重置视频标注
        self._is_video_file = False

    def _latest_camera_frame(self):
        """
        "相机最新一帧"（**注入给"相机源"节点用的取帧器**）——方案 A：节点复用主窗口相机。

        · 相机没开 ⇒ 返回 None（节点会原样透传 + 日志写说明，不弹窗、也不自己乱开设备）；
        · 一轮执行里只读一次：`_begin_camera_round()` 之后第一次读到的帧会被记住，
          同一个编号的后续调用直接返回它（这一帧既当流程起点、又给相机源节点当输入）。
        """
        if self._camera_round_frame is not None and self._camera_frame_round == self._camera_round:
            return self._camera_round_frame
        cap = self.cap
        if cap is None or not cap.isOpened():
            return None
        try:
            ret, frame = cap.read()
        except Exception:
            return None
        if not ret or frame is None:
            return None
        self._camera_round_frame = frame
        self._camera_frame_round = self._camera_round
        return frame

    def open_camera(self):
        """打开摄像头并启动视频刷新（主窗口"打开摄像头"按钮的老行为，界面表现一个字不变）"""
        # 原本不管是图片还是视频，点击打开摄像头后都会清空原本的画面
        self.close_camera()

        if not self._open_camera_device(self.camera_id, quiet=False):
            return

        # 摄像头/视频是独立的一个"图片槽"，把各节点的运行参数切到它自己那一份
        self._switch_image_params(self.VIDEO_ROI_KEY)


        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame) # type: ignore
        self.timer.start(30)

    def close_camera(self):
        """关闭摄像头，停止定时器，清空显示区域，包括导入的视频和图片"""
        self._release_camera_device()

        # 关闭时清空静态图片缓存
        self.current_static_image = None

        # 清空 QGraphicsView 的画面
        if hasattr(self, 'image_view') and self.image_view is not None:
            # 清空场景
            self.image_view.scene().clear()
            # 将 pixmap_item 重置为 None，防止下次打开图片时残留引用出错
            self.image_view.pixmap_item = None

            # 顺便把缩放/平移复位，避免下次显示图片或视频时沿用上一次的缩放
            self.image_view.reset_zoom()


    def update_frame(self):
        """定时器槽函数：读取摄像头帧并显示到 video 标签"""
        if self.cap is None or not self.cap.isOpened():
            # 识别不到摄像头时或者打开摄像头失败时执行返回，不读取视频帧
            return

        ret, frame = self.cap.read()
        if not ret:
            # 区分是摄像头出错还是视频播放结束
            if self._is_video_file:
                # 视频播放结束，停止定时器，释放资源（不弹警告，不清除最后一帧画面）
                if self.timer is not None:
                    self.timer.stop()
                    self.timer = None
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                self._is_video_file = False
                return
            else:
                # 摄像头读取失败
                self.close_camera()
                QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
                return

        work_frame = frame.copy()

        # 让"相机源"节点也能用到主窗口这一帧（方案 A：节点复用主窗口相机，不重复读设备）
        self._camera_round_frame = frame
        self._camera_frame_round = self._camera_round

        # 根据模式选择执行管道
        if self.video_processing_mode == "step" and self.video_step_node:
            # 处于单步执行模式且指定了目标节点
            work_frame, data, exec_info = self._run_flow_pipeline_step(work_frame, self.video_step_node)
        else:
            # 处于连续执行模式（或未指定节点），执行完整流程图，解包三个值
            # 同样截到"当前选中节点"为止（和按钮那条路保持一致）
            work_frame, data, exec_info = self._run_flow_pipeline(
                work_frame, stop_at=self.selected_node)

        # 更新日志：视频是每 30ms 一帧，用"节流版"，内容没变就完全不重画表格
        self._update_execution_log_throttled(exec_info)

        # 显示到画布（视频 / 摄像头帧不传 image_key，保持用户当前的缩放和平移不变）
        self._display_image(work_frame)

        # 保存消息，避免关闭摄像头/视频时数据消失
        self.last_detected_data = data

        # 实时更新配置窗口的计数
        if self.current_dialog and self.current_dialog.isVisible():
            self.current_dialog.update_result_count(data)


    # ==================================================================================
    # 数据流引擎（数据层 / 渲染层分离）
    #
    # 和以前"每个节点都从最初那份 clean_img 切一块"相比，这里改了两件事：
    #
    #   1、数据层与渲染层彻底分开
    #      · 数据层：out_images —— 每个节点执行完都留下一份"图像输出"，下游按
    #        "图像源"绑定去取；只有处理类算子（灰度）会产出和输入不同的图像；
    #      · 渲染层：_render_display() 最后统一把结果和 ROI 框画在一份副本上，
    #        画出来的绿线 / 红圆永远不会回流，所以"直线→圆"时圆看不见直线画的线。
    #
    #   2、影响必须由算子声明
    #      · 检测类算子的输出图像 = 输入图像（原样透传，连副本都不建）；
    #      · 检测类想影响下游，唯一合法通道是"ROI 继承"：下游把 ROI创建 选成继承，
    #        引擎用 NodeRegistry.result_bbox() 把上游结果算成包围盒，当作下游的 ROI。
    # ==================================================================================

    def _build_execution_order(self, nodes, edges):
        """
        按连线做拓扑排序（Kahn 算法），顺便整理出每个节点的上游列表。

        为什么不能再用原来的"队列广度优先"：
            广度优先在多上游时会乱序。比如连线是 A→D、B→C、C→D，
            队列里 D 可能排在 C 前面，D 执行时上游 C 还没算，数据流就取不到输入图像。

        :param nodes: 这一页流程图上的所有方框
        :param edges: 这一页流程图上的所有连线
        :return: (order, parents, skipped)
                 order   本次要执行的节点，父节点一定排在子节点前面
                 parents {节点: [上游节点, ...]}
                 skipped 不参与执行的节点（孤立的，或者落在环里的）
        """
        children = {node: [] for node in nodes}
        parents = {node: [] for node in nodes}
        in_degree = {node: 0 for node in nodes}

        for edge in edges:
            start = edge.start_node
            end = edge.end_node
            if start not in children or end not in in_degree:
                # 连线的某一端已经不在这一页的方框表里（理论上不会发生）
                continue
            children[start].append(end)
            parents[end].append(start)
            in_degree[end] += 1

        # 起点 = 没有上游、并且有下游。孤零零一个方框不执行（沿用 2026.6.28 定下的约定）
        queue = deque([node for node in nodes if in_degree[node] == 0 and children[node]])
        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for child in children[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    # 它的上游全都排好队了，这才轮到它
                    queue.append(child)

        done = set(order)
        skipped = [node for node in nodes if node not in done]
        return order, parents, skipped

    def _node_modifies_image(self, node):
        """
        这个节点会不会改写数据层图像？
        用来在多上游时挑出"真正产出新图像"的那一支（读的是节点契约里的 kind 声明）。
        """
        spec = get_spec(node.name)
        return spec is not None and spec.modifies_image

    def _resolve_input(self, node, parents, out_images):
        """
        决定这个节点从哪一份图像开始算（数据流引擎的"图像源"绑定）。

        优先级：节点上手动绑定的图像源 > 自动（取最后一个上游）。
        "自动"里的"最后一个"是按连线顺序取的，是确定的，所以同一张流程图每次跑结果一致。

        :param out_images: {图像源标识: 图像输出}，本轮已经产出的图像
        :return: (源标识, 给日志看的来源说明)
                 源标识是 NodeRegistry.SOURCE_KEY（全局图像源）或者某个上游节点对象
        """
        binding = getattr(node, 'input_source', None)
        if isinstance(binding, str) and binding == SOURCE_KEY:
            # 绑的是"全局图像源"
            return SOURCE_KEY, "全局图像源"

        if binding is not None and binding in out_images:
            return binding, "节点：{0}".format(binding.name)

        note = ""
        if binding is not None:
            # 绑定的节点本轮没执行（被删掉了 / 不属于这一页），退回自动
            note = "（原绑定已失效，自动回退）"

        if parents:
            source = parents[-1]
            label = "节点：{0}".format(source.name)
            if len(parents) > 1:
                # 多上游时优先挑"处理类"的上游：只有它会产出新的图像数据
                # （检测类算子的输出图像就是它的输入，等于什么都没改）。
                # 这样"图像源 -> 灰度 -> 圆"和"直线 -> 圆"同时存在时，
                # 圆默认接在灰度后面，而不是接到那条没改图的直线上。
                image_parents = [p for p in parents if self._node_modifies_image(p)]
                if image_parents:
                    source = image_parents[-1]
                    label = "节点：{0}（多上游，自动取最后一个改图的上游）".format(source.name)
                else:
                    label += "（多上游，自动取最后一个）"
            return source, label + note
        return SOURCE_KEY, "全局图像源" + note

    def _resolve_roi(self, node, img_shape, in_results, in_roi=None):
        """
        算出这个节点真正要处理的 ROI，两种来源：

            1、ROI创建 = "继承上游"：具体继承什么由 params["roi_source"] 决定
                 · "roi"（默认）：直接沿用上游那一轮实际用的 ROI 框（in_roi）——
                   框固定、逐级一致，不受上游检出几个目标、目标跑到哪儿的影响；
                 · "result"：把上游结果（直线端点 / 圆心半径）算成外接框 ——
                   目标动、框跟着动，就是"结果数据流"；
               两种都再向外扩 roi_margin 像素（默认 0 = 与上游完全重合）。
               首选那种拿不到时（单步执行没有 in_roi、或者上游是处理类算子没有结果数据）
               会自动退回另一种，实在什么都没有才用本节点手画的 ROI；
            2、其余情况：用参数里的 roi_x / roi_y / roi_w / roi_h
               （这张图片还没设置过时，默认就是整幅图），并统一裁剪到图像范围内。

        :param in_roi: 输入源那个节点这一轮实际用的 ROI（roi_info 元组），供"继承 ROI 框"用
        :return: (roi_x, roi_y, roi_w, roi_h, roi_shape, inherited)
                 inherited = ""       这块 ROI 不是继承来的（用的是本节点参数）
                             "roi"    沿用上游那一轮实际用的 ROI 框
                             "result" 用上游"检测结果"的外接框
        """
        params = node.params
        roi_shape = params.get("roi_shape", "矩形")
        img_h = img_shape[0]
        img_w = img_shape[1]

        # 算子声明了"整图模式参数"并且已经打开时（目前是灰度的 gray_full_image），
        # ROI 一律当成整幅图 —— 算法本身也是按整图处理的，这样日志和 ROI 框才与事实一致。
        spec = get_spec(node.name)
        whole_key = getattr(spec, 'whole_image_param', None) if spec is not None else None
        if whole_key and params.get(whole_key, False):
            return 0, 0, img_w, img_h, roi_shape, ""

        # 默认就是"继承上游"（2026.10.5 用户要求把缺省从"绘制"改成"继承上游"）；
        # 方案里明确存过 False 的节点才走"用本节点参数里的 ROI"那条路。
        if params.get("roi_inherit", True):
            margin = int(params.get("roi_margin", 0))
            source = params.get("roi_source", "roi")     # 默认：继承上游那一轮用的 ROI 框
            bbox = None
            inherited = ""
            if source == "roi":
                # 默认做法：直接沿用上游那一轮实际用的框（框固定、逐级一致）
                if in_roi is not None and in_roi[2] > 0 and in_roi[3] > 0:
                    bbox = (in_roi[0], in_roi[1], in_roi[2], in_roi[3])
                    inherited = "roi"
                else:
                    # 上游这一轮没执行（单步执行）、或者输入源就是全局图像源：
                    # 退回"上游检出的结果外接框"
                    bbox = result_bbox(in_results)
                    if bbox is not None:
                        inherited = "result"
            else:
                # "上游结果框"（roi_source = result）：用上游检出目标的最小外接框（目标动、框跟着动）
                bbox = result_bbox(in_results)
                if bbox is not None:
                    inherited = "result"
                elif in_roi is not None and in_roi[2] > 0 and in_roi[3] > 0:
                    # 上游是处理类算子（比如灰度）、没有结果数据：退回继承它用的框
                    bbox = (in_roi[0], in_roi[1], in_roi[2], in_roi[3])
                    inherited = "roi"
            if bbox is not None:
                left = max(0, int(round(bbox[0])) - margin)
                top = max(0, int(round(bbox[1])) - margin)
                right = min(img_w, int(round(bbox[0] + bbox[2])) + margin)
                bottom = min(img_h, int(round(bbox[1] + bbox[3])) + margin)
                if right > left and bottom > top:
                    return left, top, right - left, bottom - top, roi_shape, inherited
            # 上游既没有结果、也没有可继承的处理区域（比如单步执行，或者输入源就是全局图像源）：
            # 自动退回参数里的 ROI，免得整个节点因为 ROI 尺寸为 0 被跳过

        roi_x = int(params.get("roi_x", 0))
        roi_y = int(params.get("roi_y", 0))
        roi_w = int(params.get("roi_w", img_w))
        roi_h = int(params.get("roi_h", img_h))

        # 统一裁剪到图像范围内（这里必须裁）：
        # numpy 的切片越界时不会报错，而是"静默变空"——一张 0 像素的空图丢给
        # cv2.cvtColor / Canny / HoughCircles 会直接抛异常。
        # 老代码是靠 roi_img.size == 0 兜住的，现在从源头裁掉，
        # 顺便让日志和黄色 ROI 框显示的就是真正参与计算的那块区域（所见即所算）。
        roi_x = max(0, min(roi_x, img_w))
        roi_y = max(0, min(roi_y, img_h))
        roi_w = max(0, min(roi_w, img_w - roi_x))
        roi_h = max(0, min(roi_h, img_h - roi_y))
        return roi_x, roi_y, roi_w, roi_h, roi_shape, ""

    def _execute_node(self, node, in_img, in_results, in_roi=None):
        """
        执行一个节点（节点契约的执行侧）。

        :param in_img: 数据层输入图像（按"图像源"绑定取到的那一份）
        :param in_results: 输入源那个节点的结果数据，供"ROI 继承"用
        :param in_roi: 输入源那个节点这一轮实际用的 ROI（上游是处理类算子、没有结果时用它）
        :return: (out_img, results, roi_info, spec)
                 out_img  这个节点的图像输出，会被下游当成图像源；
                          检测类算子是原样透传（同一个对象，不复制）
                 results  这个节点产出的结果数据（原图坐标）
                 roi_info (x, y, w, h, hide, shape, inherited)
                 spec     节点能力声明；None 表示这个模块还没实现
        """
        spec = get_spec(node.name)
        roi_x, roi_y, roi_w, roi_h, roi_shape, inherited = self._resolve_roi(
            node, in_img.shape, in_results, in_roi)
        hide_roi = node.params.get("hide_roi", False)
        roi_info = (roi_x, roi_y, roi_w, roi_h, hide_roi, roi_shape, inherited)

        if roi_w <= 0 or roi_h <= 0 or spec is None:
            # roi_w / roi_h 为 0 时跳过：_resolve_roi() 已经把 ROI 裁进图像范围了，
            # 所以"整块 ROI 落在图外"或"参数里填了 0"都会走到这里，图像原样往下传；
            # spec 为 None（人脸、颜色这些还没实现的模块）也一样透传，
            # 日志里如实写"模块未实现"，不再假装"执行成功"。
            return in_img, [], roi_info, spec

        # ★ 参数校验（批次4 目标4）：**真要跑这个算子之前**再查一遍。
        #   位置放在"ROI 尺寸为 0 已跳过"之后 ⇒ 两个跳过原因不会重复写进同一行日志。
        #   · 能安全纠正的（Canny 高低互换、核大小取奇数、阈值夹范围…）：就地改 node.params，
        #     说明存进 _param_corrections，由 _format_result_text 追到执行日志末尾；
        #   · 纠正不了的（errors 非空）：跳过本节点 —— 图像原样透传 + 用 __note__ 递一句文案，
        #     **绝不弹窗、绝不把异常抛出去**（异常在 Qt 槽里会被吞掉，用户只会看到"点了没反应"）。
        fixed, corrections, errors = run_validation(spec, node.params)
        if fixed != node.params:
            node.params.update(fixed)
        if corrections:
            self._param_corrections[id(node)] = corrections
        if errors:
            return in_img, [{"__note__": "参数非法（{0}），已跳过本节点".format("；".join(errors))}], \
                roi_info, spec

        out_img, results = spec.run(self.detector, in_img, (roi_x, roi_y, roi_w, roi_h), node.params)
        if out_img is None:
            # 万一某个算子忘了返回图像，就当它不改图像，保证下游还有图可用
            out_img = in_img
        if spec.kind == KIND_SOURCE:
            # 起点节点（图片源）没有"处理区域"这个概念：它的有效 ROI 就是**它自己输出的整张图**。
            # 这样 ① 画面上不会出现一个莫名其妙的黄框（用户实测到过"512×512 的怪框"——
            # 那是对话框把主窗口当前图的尺寸写进了 ROI 参数留下的）；② 下游"继承上游 ROI"
            # 拿到的是整张图，而不是那个过时的尺寸。
            out_h, out_w = out_img.shape[:2]
            roi_info = (0, 0, out_w, out_h, True, roi_shape, "")
        return out_img, results, roi_info, spec

    def _format_result_text(self, node, results, roi_info, spec):
        """执行日志"结果数据"那一列的文案：由节点注册表提供，新增算子不用改这里"""
        # ★ 参数非法被跳过时，results 里带着一句 __note__（批次4 目标4）：直接用它当文案，
        #   不要再去问算子的 format_result —— 那个节点根本没跑起来。
        note = _result_note(results)
        if note:
            return note
        if roi_info[2] <= 0 or roi_info[3] <= 0:
            return "ROI 尺寸为 0，已跳过（图像原样传给下游）"
        if spec is None:
            return "模块未实现，图像原样传给下游"
        text = spec.format_result(results)
        # 缺省也是"继承上游"（2026.10.5 起），所以这里要用 True 兜底，
        # 否则默认继承的节点不会把"继承到没继承到"写进日志，用户就看不出来了。
        if node.params.get("roi_inherit", True):
            # 勾了"继承上游"之后到底继承到了什么，必须让用户看见（否则会以为继承生效了）。
            # 注意：单步执行 / 视频每帧都会走到这里，所以只能用日志文案、不能弹窗；
            # 文案也要尽量短——"结果数据"那一列显示不全会被截断。
            if roi_info[6] == "roi":
                text += "  ← 继承上游ROI框"
            elif roi_info[6] == "result":
                text += "  ← 继承上游结果框"
            else:
                text += "  ← 继承未生效（改用本节点 ROI）"
        # ★ 这一轮这个节点的参数被自动纠正过（批次4 目标4）：追一句短说明。
        #   不写的话用户会以为"我填的就是生效值"，而这恰恰是目标4 要消灭的"静默"。
        corrections = getattr(self, "_param_corrections", {}).get(id(node)) or []
        for line in corrections:
            text += "  ← 已自动纠正：{0}".format(line)
        return text

    def _render_display(self, base_img, executed, draw_roi=True):
        """
        渲染层：把数据层的图像复制一份，再按执行顺序把各节点的结果和 ROI 框画上去。

        这里画的所有东西都只活在这张显示图上，永远不会回流到数据层，
        所以下一个节点执行时看不到上一个节点画的绿线 / 红圆。

        :param base_img: 数据层底图（取最后一个执行节点的图像输出）
        :param executed: [(节点, 结果, roi_info, spec), ...]，按执行顺序
        :param draw_roi: 要不要把 ROI 黄框 / 洋红框也画上。
                屏幕上要（方便调参）；**"输出图像"节点存"带检测叠加"时不要** ——
                那是辅助线，存进文件里没意义（用户 2026.10.7 要求存的是"检测的内容"）。
        :return: 可以直接显示的图像
        """
        display = base_img.copy()
        rois_to_draw = []

        for node, results, roi_info, spec in executed:
            if results and spec is not None and spec.draw is not None:
                # 检测类算子的结果画到显示层
                spec.draw(display, results, node.params)
            if spec is not None and spec.kind == KIND_SOURCE:
                # 起点节点（图片源）没有"处理区域"，不画它的 ROI 框——
                # 否则画面上会出现一个跟检测毫无关系、还可能是过时尺寸的框（用户实测反馈过）
                continue
            rois_to_draw.append(roi_info)

        # 结果全部画完之后再统一画 ROI 框，避免黄框被后面的算法当成图像内容
        if draw_roi:
            for rx, ry, rw, rh, hide, roi_shape, inherited in rois_to_draw:
                if hide:
                    continue
                # 继承来的 ROI 用洋红色，和手动画的黄色区分开，一眼能看出这块是从上游结果来的
                color = (255, 0, 255) if inherited else (0, 255, 255)
                if roi_shape == "圆":
                    cv2.circle(display, (rx + rw // 2, ry + rh // 2), rw // 2, color, 2)
                else:
                    cv2.rectangle(display, (rx, ry), (rx + rw, ry + rh), color, 2)

        return display


    def _run_flow_pipeline(self, frame, stop_at=None):
        """
        连续执行：按连线做拓扑排序，让图像数据顺着连线在各模块之间流动。

        数据层：out_images[图像源] —— 每个节点执行完都会留下一份"图像输出"，
                下游节点的"图像源"绑定到谁，就取谁那一份；
                全局图像源（NodeRegistry.SOURCE_KEY）就是最初那一帧的副本。
        渲染层：_render_display() 最后统一画，不参与任何算法。

        :param frame: OpenCV BGR 原图（内部只用副本，不会污染原图）
        :param stop_at: **执行到哪个节点为止（含它）**；None = 跑完整条。
                连续执行的入口（按钮 / 摄像头老预览）传 self.selected_node ——
                用户 2026.10.7 定："连续执行 = 选中哪个节点就执行到那个节点，不再往下执行"
                （这样"输出图像"只有在选中它自己或它后面的节点时才会存文件）。
        :return: (显示用图像, 所有节点结果汇总, 执行日志列表)
        """
        img = frame.copy()              # 全局图像源（数据层的起点）
        if not self.flow_nodes:
            # 画布上一个方框都没有，没什么可执行的
            return img, [], []

        # 拓扑排序：父节点一定排在子节点前面
        order, parents, skipped = self._build_execution_order(self.flow_nodes, self.flow_edges)
        if not order:
            # 有方框，但一条能跑的链路都没有：给一行提示，而不是静默什么都不做
            return img, [], [("-", time.strftime("%H:%M:%S"), "提示", "-",
                              "没有可执行的流程：请先用连线把模块连起来")]
        # 真正的执行 + 渲染都在 _run_nodes 里：
        # 连续执行 = 全部节点（截到 stop_at 为止）；单步执行 = 目标节点 + 它的上游（同一段代码，保证逻辑一致）
        return self._run_nodes(order, parents, img, skipped, stop_at=stop_at)


    def _parent_nodes(self, node):
        """
        当前页面里直接连到 node 的上游节点（按连线顺序）。
        "图像源 = 自动"时引擎取最后一个上游（见 _resolve_input），这里保持一致。
        """
        parents = []
        for edge in self.flow_edges:
            if edge.end_node is node and edge.start_node in self.flow_nodes:
                parents.append(edge.start_node)
        return parents

    def _node_input_frame(self, node, _depth=0):
        """
        这个节点这一轮**实际会收到的图**——沿着它声明的"图像源"往上追到起点。

        对话框用它来取"上游整张图"的尺寸当 ROI 宽高默认值
        （老实现只看主窗口当前那张图，所以"绑了图片源"的下游节点，ROI 默认尺寸
        和上游图片源那张图对不上——用户实测反馈过）。

        :return: BGR 图；追不到返回 None
        """
        if node is None or _depth > 20:
            return None
        # 起点节点（图片源）自己就是图的来源：直接问它要图，别去问"主窗口当前图"
        spec = get_spec(node.name)
        if spec is not None and spec.kind == KIND_SOURCE:
            frame, _results = spec.run(self.detector, None, (0, 0, 0, 0), node.params)
            return frame
        binding = getattr(node, "input_source", None)
        if isinstance(binding, NodeItem):
            # 绑到了某个上游节点：继续往上追（处理类不改图像尺寸，追到起点就够）
            return self._node_input_frame(binding, _depth + 1)
        if isinstance(binding, str) and binding == SOURCE_KEY:
            return self.current_static_image if self.current_static_image is not None \
                else self._source_node_frame()
        # "自动"（没显式绑定）：跟引擎一样取最后一个上游；一个上游都没有才是全局图像源
        parents = self._parent_nodes(node)
        if parents:
            return self._node_input_frame(parents[-1], _depth + 1)
        return self.current_static_image if self.current_static_image is not None \
            else self._source_node_frame()

    def _run_nodes(self, order, parents, frame, skipped=None, base_node=None, stop_at=None):
        """
        按给定的拓扑顺序执行一串节点。

        连续执行和单步执行**共用这一段**，两边的取输入 / ROI 继承 / 日志文案完全一致
        （老实现单步是自己另写一套，于是出了"单步不按图像源绑定取图"的问题）。

        :param order: 要执行的节点列表（必须已按拓扑序排好）
        :param parents: {节点: [上游节点]}，来自 _build_execution_order
        :param frame: 数据层起点那一帧（全局图像源）
        :param skipped: 没有执行的节点（只在连续执行时给一行提示）
        :param base_node: 显示底图用哪个节点的输出；None = 用"当前选中的节点"（点谁看谁）
        :param stop_at: **执行到哪个节点为止（含它）**；None = 把 order 全跑完。
                用户 2026.10.7 定："连续执行 = 选中哪个节点就执行到那个节点，不再往下执行"
                —— 由连续执行的入口（_run_flow_pipeline）显式传进来，**不在引擎里偷偷读选中项**
                （直接调引擎的地方，例如测试里验"取输入 / 图像源绑定"的，仍旧跑完整条）。
        :return: (显示用图像, 所有节点结果汇总, 执行日志列表)
        """
        out_images = {SOURCE_KEY: frame}   # {图像源标识: 图像输出}
        results_of = {}                    # {节点: 它产出的结果数据}
        roi_of = {}                        # {节点: 它这一轮实际用的 ROI}，供下游"继承"用
        executed = []                      # [(节点, 结果, roi_info, spec), ...]，按执行顺序
        all_data = []                      # 所有节点结果汇总（给结果计数用）
        exec_info = []                     # 执行日志
        # ★ 参数纠正说明是"每一轮的临时状态"：每轮开头清空，
        #   否则上一个节点（或上一轮）的"已自动纠正…"会串到这一轮的行里。
        self._param_corrections = {}

        # ★ 截断：连续执行只跑到"当前选中的节点"为止（用户 2026.10.7 定的语义）。
        #   为什么要有它：画面本来就只画到选中节点（下面的 shown = executed[:选中节点]），
        #   但执行却一直跑到底 ⇒ "选中中间的节点、点连续执行"时，末尾的"输出图像"照样存了文件
        #   （用户实测报的）。现在把执行也截到同一个边界，引擎与画面才一致。
        not_run = []
        if stop_at is not None and stop_at in order:
            cut = order.index(stop_at) + 1
            not_run = list(order[cut:])
            order = order[:cut]

        seq = 1
        for node in order:
            # 1、按"图像源"绑定取本节点的输入（数据层）
            source_key, source_label = self._resolve_input(node, parents.get(node, []), out_images)
            in_img = out_images.get(source_key)
            if in_img is None:
                # 绑定的图像源这一轮不存在，退回全局图像源
                source_key = SOURCE_KEY
                source_label = "全局图像源（回退）"
                in_img = out_images[SOURCE_KEY]
            in_results = results_of.get(source_key)
            in_roi = roi_of.get(source_key)   # 上游没有结果时，下游继承它这块处理区域

            # 2、执行节点；它的图像输出挂到 out_images 上，供下游当图像源
            #    （执行前把"这一轮的来源图片名"准备好：输出类节点要用它当默认文件名）
            self._current_input_name = self._origin_image_name(node)
            #    "输出图像"节点存"带检测叠加"时，还要把"这一轮上游检测出来的绿线 / 红圆"画好交给它
            #    （只画检测结果、**不画 ROI 辅助框**；拿不到就让它退回数据层图像）
            node_spec = get_spec(node.name)
            self._current_overlay_frame = None
            self._round_info = {}
            if node_spec is not None and node_spec.kind == KIND_SINK:
                # "这一轮的执行上下文"：录制文件按节点分开、来源种类决定"自动"档存图片还是视频、
                # 源帧率当录制的标称帧率（只有输出节点用得上，所以只对它算）
                self._round_info = {
                    "node_key": id(node),
                    "source_kind": self._source_kind_of(node),
                    "source_fps": self._source_fps_of(node),
                }
                if self._wants_overlay(node):
                    self._current_overlay_frame = self._render_display(
                        in_img, executed, draw_roi=False)
            out_img, results, roi_info, spec = self._execute_node(node, in_img, in_results, in_roi)
            out_images[node] = out_img
            results_of[node] = results
            roi_of[node] = roi_info
            executed.append((node, results, roi_info, spec))

            # 3、汇总结果 + 记一行日志（图像源也记下来，方便排查数据流走向）
            if results:
                all_data.extend(results)
            exec_info.append((seq, time.strftime("%H:%M:%S"), node.name, source_label,
                              self._format_result_text(node, results, roi_info, spec)))
            seq += 1

        if skipped:
            # 孤立方框、或者连线成环的方框：如实告诉用户它们没有执行
            names = "、".join(node.name for node in skipped)
            exec_info.append(("-", time.strftime("%H:%M:%S"), "提示", "-",
                              "以下节点未执行（没有连线，或者连线成环）：" + names))

        if not_run:
            # "连续执行到选中节点为止"截掉的那些节点，也要如实写一行 ——
            # 否则用户会以为"流程跑完了、后面的节点怎么没结果"（用户 2026.10.7 定的截断语义）
            names = "、".join(node.name for node in not_run)
            exec_info.append(("-", time.strftime("%H:%M:%S"), "提示", "-",
                              "连续执行到「{0}」为止，以下节点本次未执行：{1}".format(
                                  stop_at.name, names)))

        # 4、渲染层：底图取 base_node（单步执行 = 目标节点；连续执行 = 当前选中的节点），
        #    没选中 / 选中的节点这一轮没执行，就退回用最后一个执行节点的输出。
        pick = base_node if base_node is not None else self.selected_node
        if pick in out_images:
            shown = executed[:order.index(pick) + 1]
        else:
            pick = order[-1]
            shown = executed
        display = self._render_display(out_images[pick], shown)
        return display, all_data, exec_info

    def _bind_output_providers(self):
        """
        把"输出类节点要用的两个取名字 / 取图器"绑到**当前正在执行的那个主窗口**上。

        OutputOps 里那两个 provider 是模块级的，而"一个进程里可能同时存在多个 MainWindow"
        （测试里就是这样）：谁最后构造谁就把 provider 抢过去了。所以每开始一轮执行都重新绑一次，
        保证输出节点读到的一定是**正在跑的这个窗口**的数据。
        """
        set_input_name_provider(lambda: self._current_input_name)
        set_overlay_frame_provider(lambda: self._current_overlay_frame)
        set_round_info_provider(lambda: self._round_info)

    def _source_kind_of(self, node):
        """
        这个节点这一轮的图"从哪来"：图片 / 视频 / 相机。

        给"输出图像"节点的「输出类型 = 自动」用（用户 2026.10.7：图片源存图片、视频/相机存视频）。
        判据：沿"图像源"绑定追到这条链最上头的起点节点是谁；追不到（用全局图像源）就算"图片"。
        """
        origin = self._binding_origin(node)
        name = getattr(origin, "name", "") if origin is not None else ""
        if name == "视频源":
            return SOURCE_VIDEO
        if name == "相机源":
            return SOURCE_CAMERA
        return SOURCE_IMAGE

    def _source_fps_of(self, node):
        """
        这一轮的"来源帧率"，给录制当标称帧率用（用户在参数窗口里手填的优先，见 OutputOps._resolve_fps）。
            · 视频源 → 读它那段视频的 fps（读不到 SourceOps 内部已兜 25）；
            · 相机源 → 读设备帧率，读不到按 30（主窗口老摄像头预览就是这个节奏）；
            · 图片 / 全局图像源 → 用不上，返回 0。
        """
        origin = self._binding_origin(node)
        name = getattr(origin, "name", "") if origin is not None else ""
        if name == "视频源":
            try:
                from SourceOps import video_info
                _count, fps = video_info(origin.params.get("video_path") or "")
                return float(fps or 0)
            except Exception:
                return 0.0
        if name == "相机源":
            try:
                cap = self.cap
                if cap is not None and cap.isOpened():
                    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                    if fps > 0.5:
                        return fps
            except Exception:
                pass
            return 30.0
        return 0.0

    def _close_recordings(self, reason):
        """
        收尾所有正在录制的视频文件，并把结果写进执行日志。

        「停止」/ 视频播到末尾 / 换页 / 删节点 / 关程序 / 关闭相机 都会调它
        （用户 2026.10.7 拍板："下一次录制开始、旧文件要不要收尾"这套生命周期按推荐做）。
        """
        for message in close_all_recordings(reason):
            self._append_log_hint(message)

    @staticmethod
    def _wants_overlay(node):
        """
        "输出图像"节点的「保存内容」是不是"带检测叠加"。

        默认就是叠加：没有检测结果的流程（纯处理链）两者像素完全一样，
        有检测结果的流程只有叠加才看得到绿线 / 红圆（用户 2026.10.7 报的"检测内容存不下来"）。
        """
        return (node.params.get("save_content") or SAVE_OVERLAY) == SAVE_OVERLAY

    def _origin_image_name(self, node):
        """
        这个节点这一轮的"来源图片"叫什么名字（**不含扩展名**）—— 给"输出图像"节点当默认文件名用
        （用户 2026.10.7 要求："输出文件名的默认值修改成输入图片的文件名"）。

        怎么找：沿着"图像源"绑定往上追到这条链最上头的起点
            · 起点是"图片源" → 用它的 `source_path`
            · 起点是"视频源" → 用它的 `video_path`（帧号由"自动编号"去区分）
            · 追不到（用全局图像源）→ 用主窗口当前那张图的路径
            · 相机帧 / 测试图 / 还没开图 → 返回空串（界面显示 placeholder，保存时兜底成 output）
        :return: 名字字符串（不含扩展名）
        """
        origin = self._binding_origin(node)
        path = ""
        if origin is not None:
            path = origin.params.get("source_path") or origin.params.get("video_path") or ""
        if not path and self.current_static_image is not None:
            key = self._image_key_of(self.current_static_image)
            if isinstance(key, str):
                path = key
        if not path:
            return ""
        path = path.split("#")[0]          # 视频帧的键是"路径#帧号"，取路径那半截
        if "\\" not in path and "/" not in path:
            return ""                      # 不是文件路径（例如 id(原图)）就别当名字
        return os.path.splitext(os.path.basename(path))[0]

    def input_image_name_of_node(self, node):
        """给参数窗口用的公开入口：这个节点"输入图片的文件名"（没有就返回空串）"""
        try:
            return self._origin_image_name(node)
        except Exception:
            return ""

    def _binding_origin(self, node, _depth=0):
        """
        沿着"图像源"绑定一直往上追，返回这条链最上头的**起点节点**（图片源）；
        如果这条链最终落到"全局图像源"，返回 None。
        只用于给执行日志写清楚"这一轮吃的到底是哪张图"。
        """
        if node is None or _depth > 20:
            return None
        spec = get_spec(node.name)
        if spec is not None and spec.kind == KIND_SOURCE:
            return node
        binding = getattr(node, "input_source", None)
        if isinstance(binding, NodeItem):
            return self._binding_origin(binding, _depth + 1)
        if isinstance(binding, str) and binding == SOURCE_KEY:
            return None
        parents = self._parent_nodes(node)
        if parents:
            return self._binding_origin(parents[-1], _depth + 1)
        return None

    def _run_flow_pipeline_step(self, frame, target_node):
        """
        单步执行：**只跑选中的这一个节点**（沿用 2026.7.25 定的规则："不管流程图中其他的流程，
        只执行选中的节点"），它的输入按自己声明的"图像源"取 —— 沿绑定往上追到起点：
        起点是"图片源"就用它那张图，是"全局图像源"就用当前图。

        **为什么不把上游链一起跑**：那样"单步执行"和"连续执行"的结果会一模一样
        （用户 2026.10.5 实测报过这个"最致命的错误"）。单步执行的用处是**单独调试这一个算子**：
        改参数、点执行，立刻看到这个算子对"流程输入图"做了什么；
        要看整条链的结果就用连续执行。

        :param frame: 数据层起点那一帧（全局图像源用它；追不到绑定链时也用它）
        :param target_node: 要执行的节点
        :return: (显示用图像, 目标节点的结果数据, 一行执行日志)
        """
        if target_node is None:
            return frame.copy(), [], []

        # 输入帧：优先"这个节点声明的图像源"那张图（沿绑定追到起点），追不到才用传进来的当前帧
        in_img = self._node_input_frame(target_node)
        if in_img is None:
            in_img = frame
            source_label = "全局图像源（单步：只跑本节点）"
        else:
            origin = self._binding_origin(target_node)
            if origin is not None:
                source_label = "节点：{0}（单步：只跑本节点）".format(origin.name)
            else:
                source_label = "全局图像源（单步：只跑本节点）"

        img = in_img.copy()
        # 单步执行也要把"这一轮的来源图片名"准备好（输出类节点要用它当默认文件名；
        # 单步执行选中"输出图像"时存的就是这张起点原图，名字自然也是它的名字）
        self._bind_output_providers()
        self._current_input_name = self._origin_image_name(target_node)
        # 单步执行**不叠检测结果**：这一轮只跑了选中的那一个节点，没有任何上游检测结果可叠，
        # 所以"带检测叠加"会自然等于数据层图像（和"要存处理后的图请用连续执行"是同一条口径）。
        self._current_overlay_frame = None
        # 单步执行选中"输出图像"时也可能要录一帧（"自动"档靠来源种类判断存图片还是存视频）
        self._round_info = {
            "node_key": id(target_node),
            "source_kind": self._source_kind_of(target_node),
            "source_fps": self._source_fps_of(target_node),
        }
        out_img, results, roi_info, spec = self._execute_node(target_node, img, None)
        display = self._render_display(out_img, [(target_node, results, roi_info, spec)])

        # 单步执行也产出一行日志：否则切图回来会出现"画面有结果、日志表却是空的"，
        # 缓存里的（画面 + 结果数据 + 日志）三者就对不上了。
        exec_info = [(1, time.strftime("%H:%M:%S"), target_node.name, source_label,
                      self._format_result_text(target_node, results, roi_info, spec))]
        return display, results, exec_info



    def close_event(self,event):
        """窗口关闭时释放摄像头 + **收尾正在录制的视频文件**（否则文件没 release、打不开）"""
        self._close_recordings("关闭程序")
        self.close_camera()
        event.accept() # 允许窗口关闭

    def _show_menubar_menu(self):
        """点击顶部"菜单"按钮：把菜单栏里的菜单弹出来（效果和点菜单栏一样）"""
        # 优先用 .ui 里那个 menubar 控件；万一 QUiLoader 没把它设成菜单栏，再退回 menuBar()
        menubar = self.main_window.findChild(QtWidgets.QMenuBar, "menubar")
        if menubar is None:
            menubar = self.main_window.menuBar()
        actions = menubar.actions() if menubar is not None else []
        if not actions:
            return
        menu = actions[0].menu()
        if menu is None:
            return
        menu.exec_(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))

    def set_camera_id(self):
        """设置摄像头ID(数字)"""
        loader = QUiLoader()
        widget = loader.load('SetCameraID.ui')
        '''
        # 直接使用widget打开窗口，这样显示的窗口是非模态的，同时可以操作main_window
        widget.show()
        widget.exec()
        '''
        if widget is None:
            return

        dialog = QDialog(self.main_window)
        # 使用QDialog相对于新创了一个新窗口，不是设计的ui窗口，所以窗口名Title需要重新设置，大小可以继承widget
        dialog.setWindowTitle("设置摄像头ID")
        dialog.setModal(True)  # 模态，SetCameraID窗口显示后main窗口不能使用
        dialog.setAttribute(Qt.WA_DeleteOnClose)  # 关闭后自动销毁

        # 将 widget 嵌入 dialog，不使用布局；相对于继承SetCameraID的布局，move()表示新窗口在原窗口的位置
        widget.setParent(dialog)
        widget.move(0, 0)

        # 禁止用户缩放对话框（保持固定大小）
        dialog.setFixedSize(widget.size())

        # 获取输入框和确定按钮
        line_edit = widget.findChild(QtWidgets.QLineEdit, "ID")
        ok_button = widget.findChild(QtWidgets.QPushButton, "SetID")
        if line_edit and ok_button:
            # 预填当前摄像头ID
            line_edit.setText(str(self.camera_id))

            def on_ok():
                """确定按钮槽函数：验证并保存摄像头ID"""
                id_str = line_edit.text().strip()
                if not id_str:
                    QMessageBox.warning(dialog, "输入错误", "摄像头ID不能为空")
                    return
                try:
                    new_id = int(id_str)
                    if new_id < 0:
                        raise ValueError
                    self.camera_id = new_id
                    dialog.accept()  # 关闭对话框
                except ValueError:
                    QMessageBox.warning(dialog, "输入错误", "请输入一个有效的非负整数")

            ok_button.clicked.connect(on_ok)
        else:
            # 如果UI中找不到对应控件，给出提示
            QMessageBox.warning(dialog, "界面错误", "未找到输入框或确定按钮，请检查SetCameraID.ui")

        # 模态显示（窗口打开后不能在动其他窗口），直到用户关闭
        dialog.exec_()

    def add_flow_node(self, name, pos):
        """拖拽 / 双击添加节点：加到"当前页"（真正建节点在 _add_node_to_page）"""
        return self._add_node_to_page(self.flow_page_mgr.current_page, name, pos)

    def add_edge(self, start_node, end_node):
        """从蓝点开始生成一条曲线（同一对起终点不重复连）"""
        edge = self._add_edge_to_page(self.flow_page_mgr.current_page, start_node, end_node)
        self.update_all_edges()  # 刷新一次画面，刷新出曲线
        return edge

    def delete_flow_node(self, node_to_delete):
        """实现删除与需要删除的节点相连接的曲线"""
        if node_to_delete not in self.flow_nodes:
            # 检测节点是否存在
            return
        # 删掉的如果是"输出图像"节点，它正在录制的文件要先收尾（否则是一个打不开的半个文件）
        spec = get_spec(getattr(node_to_delete, "name", ""))
        if spec is not None and spec.kind == KIND_SINK:
            message = close_recording(id(node_to_delete), "节点已删除")
            if message:
                self._append_log_hint(message)
        edges_to_remove = []
        for edge in self.flow_edges:
            # 找出任何起点或终点是当前要删除节点的连线
            if edge.start_node == node_to_delete or edge.end_node == node_to_delete:
                edges_to_remove.append(edge)
        for edge in edges_to_remove:
            # 遍历刚才找出来的待删除连线列表
            self.main_window.graphicsView.flow_scene.removeItem(edge) # 从画布上擦除这条线的图像
            self.flow_edges.remove(edge) # 从数据列表里清空这条线的记录
        self.main_window.graphicsView.flow_scene.removeItem(node_to_delete) # 把这个方块本身从画布上彻底抹去
        self.flow_nodes.remove(node_to_delete) # 从列表中移除节点记录
        self.flow_page_mgr.mark_dirty()  # 删了东西，这一页就算"有改动"
        self.update_all_edges() # 刷新画面

    def update_all_edges(self):
        """可更新的边缘连接曲线，移动方框后曲线会跟着移动"""
        for edge in self.flow_edges:
            # 遍历所有已存在的连线
            try:
                edge.update_positions()  # 命令这条连线执行自身的刷新方法
            except RuntimeError:
                # 这条连线（或它两端的方框）已经被 Qt 销毁了——典型场景是"打开方案"时
                # 把旧页面的场景 clear() 掉。这里跳过就行，不然一次刷新就会把程序崩掉。
                continue


    def _on_tree_double_click(self, _item, _column):
        """双击左侧树节点时触发（数据抓取阶段）"""
        # 获取当前项的 QModelIndex
        index = self.tree.currentIndex()
        if not index.isValid():
            return

        # 判断是否是根节点（一级标题），如果是则不放行，即只双击树枝使才创建方框
        parent = index.parent()
        if not parent.isValid():
            return

        # 直接通过 index 获取节点名称
        node_name = index.data(0)
        if not node_name:
            return

        # 延迟 1 毫秒的，把“文本数据”而不是“C++对象”传给创建函数，然后触发创建方框的功能
        QTimer.singleShot(1, lambda: self._create_node_from_name(node_name))

    def _create_node_from_name(self, name):
        """双击树状图的树枝后执行的内容"""

        '''计算新方框的摆放坐标'''
        if self.flow_nodes:
            # 第二个或者之后方框的位置
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x()  # + 180 # x方向距离增加180
            new_y = last_node.pos().y() + 180  # y方向距离不变
        else:
            new_x, new_y = 20, 20  # 第一个方框的位置

        self.add_flow_node(name, QPointF(new_x, new_y))

    def delete_edge(self, edge_to_delete):
        """删除连接曲线"""
        if edge_to_delete not in self.flow_edges:
            # 判断要删除的曲线线是否还在当前的连线列表中
            return
        self.main_window.graphicsView.flow_scene.removeItem(edge_to_delete) # 在画布上删除
        self.flow_edges.remove(edge_to_delete) # 在列表中删除
        self.flow_page_mgr.mark_dirty()  # 删了连线，这一页也算"有改动"
        self.update_all_edges() # 刷新画面

    def on_node_double_clicked(self, node):
        """
        双击流程图方框时触发：弹出这个算子自己的参数窗口。

        路由顺序（批次4 决策 b）：**专用窗口优先，通用窗口兜底**——
        · 直线 / 圆 / 灰度各有专用窗口（灰度那个带"作用于整图"这种特殊开关）；
        · 其余算子只要在注册表里声明了 param_specs（含空表），就走通用窗口
          GenericProcessDialog，界面按参数表自动生成 ⇒ **新增算子不用改这里**。
        """
        spec = get_spec(node.name)
        if node.name == "直线":
            self._open_node_dialog(node, LineParamsDialog)
        elif node.name == "圆":
            self._open_node_dialog(node, CircleParamsDialog)
        elif node.name == "灰度":
            self._open_node_dialog(node, GrayParamsDialog)
        elif spec is not None and spec.param_specs is not None:
            self._open_node_dialog(node, GenericProcessDialog)
        else:
            # 人脸/颜色这些还没实现的模块：双击保持"无反应"、不弹提示
            pass

    def _open_node_dialog(self, node, dialog_class):
        """
        双击节点时统一的开窗流程。
        顺手记下打开之前的参数：窗口关掉之后如果参数真的变了，就把当前页标记成"有改动"，
        这样关闭这一页时才能提醒用户保存。
        """
        before = dict(node.params)
        dialog = dialog_class(self.main_window, node=node, main_window=self)
        dialog.resize(390, 560)
        self.current_dialog = dialog
        dialog.finished.connect(lambda *_: self._clear_current_dialog())
        dialog.finished.connect(lambda *_: self._mark_dirty_if_params_changed(node, before))
        dialog.exec_()  # 模态显示

    def _mark_dirty_if_params_changed(self, node, before):
        """参数窗口关掉之后：只有参数确实变了，才把当前页标记成"有改动" """
        if before != dict(node.params):
            self.flow_page_mgr.mark_dirty()

    def _confirm_close_flow_page(self, page):
        """
        关闭某一页之前的检查（FlowPageManager 的回调）：
        这一页有未保存的改动，就先问"要不要保存方案"；用户点"取消"就放弃关闭。
        :return: True = 可以关；False = 别关
        """
        if not page.get("dirty"):
            # 没有未保存的改动，直接放行，不用打扰用户
            return True
        title = self._page_title(page) or "这一页"

        # 用带中文按钮的对话框（标准按钮在没装 Qt 中文翻译时会显示英文）
        box = QMessageBox(self.main_window)
        box.setWindowTitle("未保存的改动")
        box.setIcon(QMessageBox.Question)
        box.setText("流程图页面“{0}”有改动，关闭前要保存方案吗？".format(title))
        button_save = box.addButton("保存", QMessageBox.AcceptRole)
        box.addButton("不保存", QMessageBox.DestructiveRole)
        button_cancel = box.addButton("取消", QMessageBox.RejectRole)
        box.exec_()

        clicked = box.clickedButton()
        if clicked is button_cancel:
            return False
        if clicked is button_save:
            # 方案文件是"一个文件一页"，所以先把要关的这一页切成当前页再存，
            # 否则会把"当前那一页"存进去、真正要关的这一页反而没保存
            try:
                index = self.flow_page_mgr.tab_widget.indexOf(page["widget"])
                if index >= 0:
                    self.flow_page_mgr.tab_widget.setCurrentIndex(index)
            except RuntimeError:
                pass
            # 保存方案（还没有路径时会弹"另存为"）；保存失败或用户取消 → 不关这一页
            return bool(self.save_project())
        return True

    def _clear_current_dialog(self):
        """对话框关闭时，清除内部持有的引用"""
        self.current_dialog = None


    def on_node_selected(self, node):
        """处理节点选中，当流程图中的节点被单击选中时调用"""
        # 先看流程图页面管理器的状态，别被"别的页面"发出的信号干扰
        mgr = getattr(self, 'flow_page_mgr', None)
        if mgr is not None:
            if mgr.switching:
                # 正在添加 / 删除流程图页面：被删页面的 scene 也会发出选中变化信号，
                # 直接忽略，别让它把"当前页"的选中状态和底部提示文字清掉
                return
            if node is not None and mgr.current_page is not None:
                # 只处理"当前页"画布上选中的节点
                if node.scene() is not mgr.current_page["view"].flow_scene:
                    return

        self.selected_node = node
        if node:
            # 设置文本控件 label 的文本内容，文本控件的 Name 为 current_node_label
            self.current_node_label.setText(f"当前选中的节点为：{node.name}")
        else:
            self.current_node_label.setText("未选中节点")

    # ------------------------------------------------------------------
    # 执行入口（UI 上所有"单步执行 / 连续执行"都从这里走）
    # ------------------------------------------------------------------
    def _source_node_frame(self, allow_camera_open=False):
        """
        当前页面里"图像源类节点"这一轮能给出的图（没有就返回 None）。

        只用于兜底：图库为空、也没打开任何图时，只要流程里放了"图片源"并指定了图片
        （或选了测试图），点执行照样能跑——跑的就是它那张图。

        :param allow_camera_open: 轮到"相机源"时，要不要**顺手把相机打开**。
                只有执行路径（`_flow_source_frame()`）传 True。
                为什么需要它（用户 2026.10.7 实测报的 bug）：画布上只有"相机源"、而且**没连线**时，
                `_ensure_camera_open_for_run()` 的判据是"这一轮真用到相机源"（要有一条下游连线）
                ⇒ 判成"没用到" ⇒ 设备压根没开 ⇒ 这里问它要图只能拿到 None ⇒ 点"连续执行"
                会弹"请先导入图片/视频…"，而点"单步执行"（选中相机源，走了 `_camera_used_by` 的
                `node is camera` 分支）却正常 —— 两条入口表现不一致，就是这里漏的。
                改成"走到相机源这一项、真要向它取图时再开"，判据就从"有没有连线"变成"是不是轮到它取图"。
        """
        for node in list(self.flow_nodes):
            spec = get_spec(node.name)
            if spec is None or spec.kind != KIND_SOURCE:
                continue
            if allow_camera_open and node is self._camera_source_node():
                # 轮到相机源取图了：先把设备准备好（已经开着同一编号就复用；用户关掉了
                # "执行时自动打开相机"就不开，那样这里问它要图只会拿到 None，由调用方如实提示）
                self._ensure_camera_device_open(node)
            try:
                # 图像源节点不看传入的图与 ROI（"当前图像"这个来源会把传入的 None 原样返回）
                frame, _results = spec.run(self.detector, None, (0, 0, 0, 0), node.params)
            except Exception:
                frame = None
            if frame is not None:
                return frame
        return None

    def _flow_source_frame(self):
        """
        决定"这一轮流程从哪张帧开始跑"（只决定**全局图像源**那一帧；绑到图片源 / 上游节点的
        节点各自按自己的绑定取图，见 _run_nodes）：
            ① 主窗口已经打开图片 / 视频 / 摄像头 → 就用它（老行为一个字不变）；
            ② 都没有，但当前页面里有图像源节点能给出图 → 用那张图兜底（图库为空也能跑）；
            ③ 什么都没有 → 返回 (None, 提示语)，由调用方弹提示。
        :return: (frame, 提示语, 这一帧是不是"图片源兜底"来的)
        """
        if self.current_static_image is not None:
            return self.current_static_image, "", False
        # 允许"走到相机源时顺手开设备"：画布上只有相机源、又没连线时，这一步就是唯一能开相机的时机
        frame = self._source_node_frame(allow_camera_open=True)
        if frame is not None:
            return frame, "", True
        return None, "请先导入图片/视频、打开摄像头，或者在流程图里放一个“图片源”/“视频源”/“相机源”节点并给它指定图片 / 视频 / 相机编号！", True

    def _legacy_camera_preview_active(self):
        """
        主窗口"打开摄像头"按钮那套**老预览**还在跑吗？（目标3-M4，2026.10.7 修）

        老预览 = `self.timer` 那个 30ms 定时器直接读设备、直接刷帧；**只有在用它的时候**，
        单步 / 连续执行才该走 `update_frame()` 那条老路。相机源节点是流程里的起点节点，
        必须走引擎正常路径，否则"画面键整段共用 / 相机帧不进缓存 / 参数复用视频槽 / 自动出画面"
        这套 M4 语义全被绕过。

        （实测踩到：相机源一自动打开相机，第二次点"连续执行"就被老分支接走了 ——
        走的是 update_frame()，_execute_static 压根没执行。）
        """
        return (self.current_static_image is None
                and self.cap is not None and self.cap.isOpened()
                and self.timer is not None
                and self._camera_source_node() is None)

    def run_flow_step(self, target_node):
        """
        UI 的"单步执行"统一入口：主界面的"单步执行"按钮、参数窗口的"执行 / 确定"都调它。
        :return: True = 真的执行了；False = 没有可用的图（已经弹过提示）
        """
        # 相机源（M4）：本轮开始（这一轮只读一次相机）+ 真用到相机就先把它打开（没开才开、开着就复用）
        self._begin_camera_round()
        self._ensure_camera_open_for_run(target_node, "step")
        frame, reason, from_source = self._flow_source_frame()
        if frame is None:
            QMessageBox.warning(self.main_window, "提示", reason)
            return False
        # 执行"target_node + 它声明的上游链"；计算、显示、写缓存、刷新日志都在 _execute_static 里完成。
        # 帧来自"图片源兜底"时不把它记成"当前图片"，否则换了图片源的文件还会拿旧图跑。
        self._execute_static(frame, "step", target_node, adopt_frame=not from_source)
        return True

    def run_flow_continuous(self):
        """
        UI 的"连续执行"统一入口：主界面的"连续执行"按钮、参数窗口的"连续执行"都调它。
        :return: True = 真的执行了；False = 没有可用的图（已经弹过提示）
        """
        # 相机源（M4）：同上（连续执行这一轮也可能只有相机这一个来源）
        self._begin_camera_round()
        self._ensure_camera_open_for_run(None, "continuous")
        frame, reason, from_source = self._flow_source_frame()
        if frame is None:
            QMessageBox.warning(self.main_window, "提示", reason)
            return False
        # 跑完整个流程图；计算、显示、刷新日志表格都在 _execute_static 里完成
        self._execute_static(frame, "continuous", adopt_frame=not from_source)
        return True

    def on_step_execute(self):
        """点击单步执行按钮时触发：只执行当前选中的节点"""
        # 视频 / 摄像头模式：老行为不变（切单步 + 立刻刷一帧，让用户马上看到效果）
        if self._legacy_camera_preview_active():
            if self.selected_node is None:
                QMessageBox.warning(self.main_window, "提示", "请先在流程图中单击选择一个节点！")
                return
            self.video_processing_mode = "step"
            self.video_step_node = self.selected_node
            self.update_frame()
            return

        if self.selected_node is None:
            # 检测是否选中节点
            QMessageBox.warning(self.main_window, "提示", "请先在流程图中单击选择一个节点！")
            return

        # 静态图：有当前图就用当前图；图库为空但流程里有"图片源"就用它那张（内部判定）
        self.run_flow_step(self.selected_node)

    def on_continuous_execute(self):
        """点击连续执行按钮时触发：按整个流程图顺序执行"""
        # 视频 / 摄像头模式：老行为不变
        if self._legacy_camera_preview_active():
            self.video_processing_mode = "continuous"
            self.video_step_node = None
            self.update_frame()
            return

        # 方案 B（用户 2026.10.6 拍板）：**范围只看下拉框**（运行全部 / 运行选中）——
        # "自动切换"不参与范围判定，它只管"执行时是否跟随选中项"（见 run_all_images）。
        gallery = getattr(self, "gallery_widget", None)
        if gallery is not None and gallery.count() > 0 and gallery.scope_all():
            self.run_all_images("continuous")
            return

        # 范围 = "运行选中"（或图库为空）→ 走单张。先把"图片源"节点同步到图库里当前选中的那一张，
        # 否则流程会按图片源节点里上次留下的路径去跑（范围说"当前"，跑的却是上一张）。
        if gallery is not None and gallery.count() > 0:
            entries = gallery.items()
            idx = gallery.current_index()
            if 0 <= idx < len(entries) and entries[idx][2]:
                self._sync_source_nodes_to_path(entries[idx][2])

        # 静态图 / "图片源"兜底
        self.run_flow_continuous()

    # 用表格显示执行日志，execution_log可更新的执行记录
    def _update_execution_log(self, exec_info):
        """
        用表格显示执行日志，刷新 execution_log 表格内容。
        该函数接收一个执行记录列表，将其清空并重新填充到 QTableWidget 中，实现执行日志的实时更新。
        :param exec_info: 执行记录列表，每个元素为 (序号, 时间字符串, 模块名, 图像源, 结果描述)；
                          "提示"行用的是 ("-", 时间, "提示", "-", 文字)
        """
        if not self.execution_log:
            # 如果控件不存在
            return
        if getattr(self, "_video_log_throttle", False):
            # 视频自动播放中：不每格重写表格（不然日志刷屏、播放也变卡），
            # 播放进度看工具栏那个"视频帧 (n/N)"标签；停播时会另写一行说明。
            return
        if getattr(self, "_log_accumulate", False):
            # "运行全部"期间：**不清空**表格，逐张往后累积（用户 2026.10.6 定的规则）
            offset = self.execution_log.rowCount()
            self.execution_log.setRowCount(offset + len(exec_info))
        else:
            # 单张执行：清空旧数据再填（原来的行为）
            offset = 0
            self.execution_log.setRowCount(len(exec_info))
        # 遍历每一条执行记录，row 为行号（从 0 开始）
        for row, info in enumerate(exec_info):
            info = tuple(info)
            if len(info) == 4:
                # 兼容老格式 (序号, 时间, 模块, 结果)，图像源补一个占位
                seq, time_str, module, result = info
                source = "-"
            else:
                # 新格式：(序号, 时间, 模块, 图像源, 结果)
                seq, time_str, module, source, result = info[:5]

            # 将五个字段转换为字符串列表，准备填充到表格的五个列中
            values = [str(seq), time_str, module, source, result]

            # 遍历当前行的每一列，col 为列号（0~4）
            for col, text in enumerate(values):
                # 创建一个新的表格项，存储该单元格的文本内容
                item = QtWidgets.QTableWidgetItem(text)
                # 将表格项放入指定行和列的单元格中
                # 如果该单元格已有内容，会自动替换；如果之前没有，会创建新单元格
                self.execution_log.setItem(offset + row, col, item)


    def _update_execution_log_throttled(self, exec_info):
        """
        执行日志的"节流版"刷新，专供视频 / 摄像头路径使用（静态图片仍走立刻刷新的版本）。

        为什么需要：
            update_frame 由定时器每 30ms 调一次，而真刷一次表格要清空行、再为每个
            单元格 new 一个 QTableWidgetItem。视频下每帧重建一次表格会明显拖慢画面。
        策略：
            · 内容和上一次真正刷进去的完全一样 -> 直接返回，一格都不动（视频里最常见）；
            · 内容变了 -> 最多每 0.2 秒刷一次，把高频变化攒一攒。
        """
        if not self.execution_log:
            return

        # 把日志列表转成可比较的"签名"（里面都是元组，直接 tuple 化）
        signature = tuple(tuple(row) for row in exec_info)
        if signature == self._exec_log_signature:
            # 和表格里已经显示的内容一模一样，不用重画
            return

        now = time.time()
        if now - self._exec_log_flush_time < 0.2:
            # 内容在变但太频繁（比如视频里每帧结果都不同），先攒着，≥0.2 秒后再刷
            return

        self._update_execution_log(exec_info)
        self._exec_log_signature = signature
        self._exec_log_flush_time = now


    def _on_gallery_image_selected(self, img_bgr):
        """
        当用户点击图库中的图片时，切换主画面显示
        这张图片以前执行过 -> 直接显示它上一次的检测结果（不用再点执行按钮）；
        这张图片没执行过   -> 只显示原图，不显示检测结果。
        同时，每个节点在这张图片上设置过的运行参数（ROI + 算法参数）会被恢复。
        """
        if img_bgr is not None:
            self._show_static_image(img_bgr)

    def _on_gallery_path_selected(self, path):
        """
        点图库缩略图时，如果这张图来自某个文件，就把当前页"图片源"节点的路径同步过去
        （用户 2026.10.5 的要求：图库列表和图片源节点是统一的——点哪张图，图片源就吃哪张）。
        """
        self._sync_source_nodes_to_path(path)

    # ------------------------------------------------------------------
    # 图像列表工具栏（控件在 main.ui 里、由 ImageGalleryWidget 收编，这里负责干活）
    # ------------------------------------------------------------------
    def add_folder_to_gallery(self):
        """工具栏"＋文件夹"：弹系统原生的"选择文件夹"，把里面的图片静默导进图库"""
        folder = QFileDialog.getExistingDirectory(self.main_window, "选择文件夹")
        if not folder:
            return
        self.import_folder_path(folder)
        if hasattr(self, "gallery_widget"):
            self.gallery_widget.refresh_count()

    def delete_gallery_item(self, item):
        """
        删除图库里的一个条目：**连它的参数存档 / 结果缓存 / 缩放记录一起清掉**
        （用户 2026.10.6 定的规则）——不清的话，图片标识被后面的图复用时会把参数串过去。
        """
        gallery = getattr(self, "gallery_widget", None)
        if gallery is None:
            return
        # ★ 删除前先停掉正在播放的视频/相机：否则下面把视频路径清掉之后，播放定时器还在每一格
        #   去取帧、每格都会弹一次"请先导入图片/视频…"（用户实测：点完 OK 又弹一个，无限弹）。
        if self._video_playing:
            self._stop_video_playback("相机已被删除" if self._camera_playing else "视频已被删除")
        # ★ 相机源（M4）：点"删除"要把相机**关掉**（用户 2026.10.7 定："停止不关、删除才关"），
        #   同时把画布清掉；但**不动相机源节点里的参数**（编号 / 分辨率留着，下次执行会重新打开）。
        camera = self._camera_source_node()
        if camera is not None and (self.cap is not None and self.cap.isOpened()):
            self._release_camera_device()
            self._append_log_hint("已关闭相机（相机源节点里的参数保留）")
        if item is None:
            # 列表里**没有可删的条目**（典型场景：画布上放的是"视频源"的帧，帧不进图库）⇒
            # 退化成"清空画布"：顺便把视频源节点里的路径也清掉，免得下次执行又把它跑出来
            # （用户 2026.10.6 实测："点击删除按钮无法清除画布上的视频"）。
            self.current_static_image = None
            self.current_image_key = None
            view = getattr(self, "image_view", None)
            if view is not None:
                view.set_image(None)
            video = self._video_source_node()
            if video is not None:
                video.params["video_path"] = ""
            self._append_log_hint("已清除画布内容（图像列表里没有可删除的条目）")
            return
        frame = gallery.item_frame(item)
        path = gallery.item_path(item)
        key = path if path else (id(frame) if frame is not None else None)

        gallery.remove_item(item)          # 先从列表移除

        # ★ 这张图的路径如果正是某个"图片源"节点的路径，也要一并清空。
        # 否则图库删了图、点执行时流程还会按图片源里那条路径把这张图跑出来
        # （用户实测："图像列表清空后画布确实没了，但点执行图片又出现了"）。
        if path:
            self._clear_source_nodes_path(path)

        if key is not None:
            # 1、参数存档（每个节点里"这张图那一份"）
            for node in list(self.flow_nodes):
                store = getattr(node, "params_per_image", None)
                if isinstance(store, dict):
                    store.pop(key, None)
            # 2、结果缓存（这张图在所有页面、两种执行方式下的记录）
            for cache_key in [k for k in self.result_cache if k and k[0] == key]:
                self.result_cache.pop(cache_key, None)
            # 3、显示层的缩放记录
            view = getattr(self, "image_view", None)
            states = getattr(view, "_zoom_states", None)
            if isinstance(states, dict):
                states.pop(key, None)

        # 记住"用户删过的图"：以后执行时别再把这张图自动加回图库（用户实测报过"删了又回来"）
        if path:
            self._removed_paths.add(self._path_key(path))

        # 图库空了：**不管删的是不是"当前图"，画布一律清空**
        # （用户实测报过"图像列表里的图全删了，画布上还留着图片"）
        if gallery.count() == 0:
            self.current_static_image = None
            self.current_image_key = None
            view = getattr(self, "image_view", None)
            if view is not None:
                view.set_image(None)
        # 删掉的是"当前图"（但列表里还有别的图）：把画面切到最后一张
        elif frame is not None and self.current_static_image is frame:
            self.current_static_image = None
            self.current_image_key = None
            items = gallery.items()
            if items:
                self._show_static_image(items[-1][1])
        gallery.refresh_count()

    def run_all_images(self, mode="continuous"):
        """
        "运行全部"：把图像列表里的图**逐张**跑一遍（用户 2026.10.6 定的规则）。

        · 开始时**先清空执行日志**，之后每张图的日志**逐张累积**；
        · 某张图出错 -> **跳过继续**跑下一张，不弹任何提示；
        · 如果"自动切换"在执行过程中**被关掉** -> 立刻停（开始时就是关着的，则跑完全部）。
        :return: 真正跑了多少张
        """
        gallery = getattr(self, "gallery_widget", None)
        if gallery is None or gallery.count() == 0:
            return 0
        items = gallery.items()
        # 进来时"运行全部"是不是勾着：只有一开始就勾着，才把"中途取消勾选"当成急停
        started_with_scope = gallery.scope_all()
        # 记下开始时的选中项与画面：不勾"自动切换"（不跟随）时，跑完要还原回去
        start_index = gallery.current_index()
        start_frame = self.current_static_image
        start_path = gallery.item_path(items[start_index][0]) if 0 <= start_index < len(items) else ""
        self._batch_stop = False

        # 清空旧日志（用户要求：运行全部开始时先清空）
        if self.execution_log is not None:
            self.execution_log.setRowCount(0)

        self._log_accumulate = True
        done = 0
        try:
            for index, (item, frame, path) in enumerate(items, 1):
                # 两条急停路径：菜单"停止"、或批量运行中取消勾选"运行全部"
                if self._batch_stop:
                    self._append_log_hint("用户停止，批量执行中断")
                    break
                if index > 1 and started_with_scope and not gallery.scope_all():
                    self._append_log_hint("已取消“运行全部”，批量执行中断")
                    break
                try:
                    # "自动切换"= 是否跟随：勾着才把选中项切到正在跑的那张
                    if gallery.auto_switch():
                        gallery.set_current_index(index - 1)
                    # 只切"当前图 + 它的参数"（画面由 _execute_static 显示结果时刷新）：
                    # 这里**不能**用 _show_static_image()——它会把这张图上一次的缓存结果
                    # 也重新写进日志，批量执行时日志就会重复两遍。
                    self.current_static_image = frame
                    self._switch_image_params(self._image_key_of(frame))
                    # **关键**：流程里若有"图片源"节点，它才是那一轮的取图处——必须把它也切到
                    # 这一张，否则批量执行会一直用图片源原来那张图（用户实测："每次处理的都是同一幅图"）
                    if path:
                        self._sync_source_nodes_to_path(path)
                    self._execute_static(frame, mode)        # 跑一遍当前页的流程图
                    done += 1
                except Exception as exc:                     # 单张出错不中断整批（用户要求继续）
                    self._append_log_hint("第 {0} 张出错已跳过：{1}".format(index, exc))
        finally:
            self._log_accumulate = False

        # 没勾"自动切换"（不跟随）时：把选中项与画面**还原成开始时那一张**。
        # 否则用户会觉得"自动切换勾不勾都一样——跑完画面总是停在最后一张图上"（用户实测报过）。
        # 注意这里只恢复画面、**不动执行日志**（不走 _show_static_image，它会把缓存日志重放一遍）。
        if not gallery.auto_switch():
            if 0 <= start_index < len(items):
                gallery.set_current_index(start_index)
            # 图片源节点也要还原成开始时那一张，否则下次"运行选中"会按它跑上一张
            if start_path:
                self._sync_source_nodes_to_path(start_path)
            if start_frame is not None:
                self.current_static_image = start_frame
                key = self._image_key_of(start_frame)
                self._switch_image_params(key)
                cached = (self.result_cache.get(self._result_cache_key(key, mode))
                          or self.result_cache.get(self._result_cache_key(key, "step")))
                self._display_image(cached["frame"] if cached is not None else start_frame.copy(), key)

        self._append_log_hint("运行全部结束：共执行 {0}/{1} 张".format(done, len(items)))
        return done

    def _append_log_hint(self, text):
        """往执行日志表**追加**一行"提示"（批量执行时写"出错跳过 / 结束"这类信息用）"""
        if self.execution_log is None:
            return
        row = self.execution_log.rowCount()
        self.execution_log.insertRow(row)
        for col, value in enumerate(["-", time.strftime("%H:%M:%S"), "提示", "-", text]):
            self.execution_log.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))

    def run_selected_image(self):
        """
        菜单"运行选中"：**只跑图像列表里当前选中的那一张**（用户口径：不看多选）。

        它的用处：即使"运行全部"勾着（范围 = 整个列表），也能一键只跑当前这一张。
        """
        gallery = getattr(self, "gallery_widget", None)
        if gallery is None or gallery.count() == 0:
            return 0
        # 注意：这里拿到的是包装类 ImageGalleryWidget（不是 QListWidget 本身），
        # 要用它自己的接口（current_index / items），不能直接调 currentItem()。
        index = gallery.current_index()
        entries = gallery.items()
        if index < 0 or index >= len(entries):
            gallery.set_current_index(0)
            index = 0
            entries = gallery.items()
        if not entries:
            return 0
        item, frame, path = entries[index]
        if frame is None:
            return 0
        self._show_static_image(frame)          # 切到这一张（参数 / 缩放 / 画面）
        if path:
            self._sync_source_nodes_to_path(path)   # 流程里若有"图片源"，也切到这一张
        self.run_flow_continuous()
        return 1

    def _maybe_load_video_params(self):
        """
        视频参数"整段共用一份"的**载入侧**（尾巴之一，2026.10.7 补）：

        换了一段视频（或第一次对某段视频动手）时，把"视频槽"里存过的那份参数载回来；
        同一段视频只在**换路径时载一次**，绝不每帧载 —— 否则会把用户播放中刚改的参数覆盖掉。
        """
        video = self._video_source_node()
        path = (video.params.get("video_path") or "") if video is not None else ""
        if not path or path == getattr(self, "_video_params_path", None):
            return
        self._video_params_path = path
        has_store = any(VIDEO_ROI_KEY in (getattr(n, "params_per_image", None) or {})
                        for n in self.flow_nodes)
        if has_store:
            self._load_node_params(self.flow_nodes, VIDEO_ROI_KEY)
            self._append_log_hint("已载回这段视频上一次的参数（视频参数整段共用一份）")

    def _maybe_start_video_playback(self, node, mode):
        """
        勾了"自动切换"时：这一轮执行结束后**接着自动出画面**（用户 2026.10.6 的要求）。

        只在"这一轮真的用到视频源 / 相机源"、而且当前**不是**播放中的那一帧 tick 时才启动，
        避免播放 tick 再套一层播放。

        M4 起这里兼作**分派口**：相机源走 _start_camera_playback（无界流），视频源走
        _start_video_playback（有帧号、有末尾、可循环）。
        """
        if self._video_playing or self._video_tick_running:
            return False
        gallery = getattr(self, "gallery_widget", None)
        if gallery is None or not gallery.auto_switch():
            return False
        if self._camera_used_by(node, mode):
            self._start_camera_playback(node, mode)
            return True
        if not self._video_used_by(node, mode):
            return False
        self._start_video_playback(node, mode)
        return True

    def _start_camera_playback(self, node, mode):
        """
        开始"相机画面"的自动刷新（用户 2026.10.7：勾了"自动切换"再点执行 ⇒ 连续出画面）。

        相机是**无界流**：没有帧号、没有末尾、不循环 —— 一直出到用户点"停止"为止；
        "停止"只停画面（最后一帧留在画布上），**不关相机**（用户定："停止不关、删除才关"）。
        定时器与视频自动播放**共用同一个**（同一时刻只会播一种）。
        """
        if self._video_timer is None:
            self._video_timer = QTimer(self.main_window)
            self._video_timer.setSingleShot(False)
        try:
            self._video_timer.timeout.disconnect()
        except (RuntimeError, TypeError):
            pass
        # 相机读不到帧率就按 30ms 一格（和主窗口原来的相机刷新间隔一致）
        fps = 0.0
        try:
            cap = self.cap
            if cap is not None and cap.isOpened():
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        except Exception:
            fps = 0.0
        interval = int(1000.0 / fps) if fps and fps > 1 else 30
        interval = max(5, min(interval, 1000))
        self._video_timer.setInterval(interval)
        self._video_timer.timeout.connect(lambda: self._video_tick(node, mode))
        self._batch_stop = False
        self._video_playing = True
        self._camera_playing = True
        self._video_timer.start()
        self._append_log_hint("开始显示相机画面（点“停止”可停；相机保持打开）")

    def _display_key_of(self, frame):
        """
        **画面（缩放/平移）**用的键 —— 与"结果缓存键"分开：

        · 来自文件的图：还是用它的路径（每张图的缩放仍然各自独立）；
        · 视频帧：整段视频**共用一个键**（"video:路径"）。否则每帧都是新对象 ⇒ 显示层把每帧都当
          "新图片" ⇒ 每帧复位默认缩放 ⇒ 播放时"画面一大一小"、鼠标滚轮的缩放也被下一帧覆盖掉
          （用户 2026.10.6 实测报的这两个现象，根因就是同一个）。
        """
        known = self._frame_paths.get(id(frame))
        if known:
            return known
        video = self._video_source_node()
        if video is not None and video.params.get("video_path"):
            return "video:" + video.params["video_path"]
        return id(frame)

    def _camera_display_key(self, node, mode):
        """
        相机帧的**画面（缩放/平移）键**：整段共用一个（"camera:编号"）——目标3-M4，2026.10.7。

        为什么不并进 `_display_key_of()`：相机帧每一帧都是 `run_camera()` 返回的**新副本**，
        用对象同一性认不出来；这里直接按"这一轮是不是真的用到相机源、而且相机真的开着"判定，更稳。
        视频那条（"video:路径"）是同一个目的：别让显示层把每一帧都当成"新图片"、每帧复位一次缩放。
        :return: 键字符串；这一轮不是相机帧就返回 None（调用方退回 _display_key_of）
        """
        if not self._camera_used_by(node, mode):
            return None
        if self.cap is None or not self.cap.isOpened():
            return None
        camera = self._camera_source_node()
        return "camera:{0}".format(
            camera.params.get("camera_id", 0) if camera is not None else 0)

    def _video_source_node(self):
        """当前页的"视频源"节点（没有就返回 None）"""
        for node in self.flow_nodes:
            if getattr(node, "name", "") == "视频源":
                return node
        return None

    def _camera_source_node(self):
        """当前页的"相机源"节点（没有就返回 None）"""
        for node in self.flow_nodes:
            if getattr(node, "name", "") == "相机源":
                return node
        return None

    def _begin_camera_round(self):
        """
        每开始一轮执行就让"相机读数"作废一次（目标3-M4，2026.10.7）。

        用处：一轮执行里 `_flow_source_frame()` 和"相机源"节点都会去要一帧，
        没有这个计数器就会从设备里抠走两帧（画面和实际算的不是同一张）。
        """
        self._camera_round += 1
        self._camera_round_frame = None
        self._camera_frame_round = -1

    def _ensure_camera_device_open(self, camera_node):
        """
        把某个"相机源"节点要用的设备准备好（已经开着同一编号就**复用**，不重开）。

        两条路径共用：① 执行前按"这一轮真用到相机源"预开（`_ensure_camera_open_for_run()`）；
        ② `_source_node_frame()` 轮到相机源取图时顺手开（画布上只有相机源、又没连线的场景）。
        "执行时自动打开相机"这个开关在这里统一判断，免得两条路各写一份、判据不一致。
        :return: True = 相机可用
        """
        if camera_node is None:
            return False
        if camera_node.params.get("open_on_run", True) is False:
            return False
        if self.cap is not None and self.cap.isOpened():
            return True
        if not self._open_camera_device(int(camera_node.params.get("camera_id") or 0), quiet=True):
            return False
        # 相机 / 视频是同一个"图片槽"，把各节点的运行参数切到它自己那一份
        self._switch_image_params(VIDEO_ROI_KEY)
        self._append_log_hint("已自动打开相机 {0}（参数与视频共用一份）".format(
            int(camera_node.params.get("camera_id") or 0)))
        return True

    def _ensure_camera_open_for_run(self, node, mode):
        """
        执行前准备相机：这一轮**真的用到**"相机源"、而相机还没开 ⇒ **自动打开**（用户 2026.10.7 定）。

        · 节点上的"执行时自动打开相机"没勾 ⇒ 不自动开（取不到帧就原样透传 + 日志写说明）；
        · 已经开着同一个编号 ⇒ 复用，不重开（方案 A："节点复用主窗口相机"）；
        · 打开时顺带把各节点参数切到"视频槽"——相机和视频**共用一份参数**（用户定）。
        :return: True = 相机可用
        """
        camera = self._camera_source_node()
        if camera is None:
            return False
        if self.cap is not None and self.cap.isOpened():
            return True
        if not self._camera_used_by(node, mode):
            return False
        return self._ensure_camera_device_open(camera)

    def _camera_used_by(self, node, mode):
        """
        这一轮执行有没有**真的用到**相机源（判定方式和 _video_used_by 一致）。

        · 单步：从被执行的节点沿"父节点"往上追，能追到相机源才算用到；
        · 连续：按拓扑序跑全部节点，相机源只要有下游（连进了流程）就算用到。
        """
        camera = self._camera_source_node()
        if camera is None:
            return False
        if mode == "step":
            if node is None:
                return False
            seen, stack = set(), [node]
            while stack:
                cur = stack.pop()
                if cur is camera:
                    return True
                if id(cur) in seen:
                    continue
                seen.add(id(cur))
                stack.extend(self._parent_nodes(cur) or [])
            return False
        return any(getattr(edge, "start_node", None) is camera
                   for edge in getattr(self, "flow_edges", []))

    def _video_used_by(self, node, mode):
        """
        这一轮执行有没有**真的用到**视频源（没用到就不该吃掉一帧，用户 2026.10.6 的要求）。

        · 单步：从被执行的节点沿"父节点"往上追，能追到视频源才算用到；
        · 连续：按拓扑序跑全部节点，视频源只要有下游（连进了流程）就算用到。
        """
        video = self._video_source_node()
        if video is None or not video.params.get("video_path"):
            return False
        if mode == "step":
            if node is None:
                return False
            seen, stack = set(), [node]
            while stack:
                cur = stack.pop()
                if cur is video:
                    return True
                if id(cur) in seen:
                    continue
                seen.add(id(cur))
                stack.extend(self._parent_nodes(cur) or [])
            return False
        return any(getattr(edge, "start_node", None) is video
                   for edge in getattr(self, "flow_edges", []))

    def _advance_video_cursor(self):
        """"执行后前进一帧"：把视频源的 frame_index +1（一次执行只 +1 一次）"""
        video = self._video_source_node()
        if video is None or not video.params.get("video_path"):
            return
        if video.params.get("auto_next", True) is False:
            return
        video.params["frame_index"] = int(video.params.get("frame_index") or 0) + 1

    def _start_video_playback(self, node, mode):
        """
        开始"自动播放"视频（用户 2026.10.6 要求：勾了"自动切换"后点执行 ⇒ 自动播，不用一帧一帧点）。

        · 帧间隔 = 原帧率（`1000 / fps` 毫秒）；fps 读不到就按 25 兜底；
        · 用 QTimer 驱动（不是死循环）⇒ 界面不卡，"停止"按钮任意两帧之间都能立刻停；
        · 播到末尾：节点参数"到末尾回到开头"勾着 ⇒ 回到第 0 帧继续（反复播放）；
          没勾 ⇒ 自动停。
        """
        if self._video_timer is None:
            self._video_timer = QTimer(self.main_window)
            self._video_timer.setSingleShot(False)
        self._maybe_load_video_params()           # 换了视频就先把"视频槽"那份参数载回来（只载一次）
        from SourceOps import video_info          # 局部导入，避免与"注册表 ← 分类模块"的顺序纠缠
        video = self._video_source_node()
        _count, fps = video_info(video.params.get("video_path") or "" if video else "")
        interval = int(1000.0 / (fps if fps and fps > 0 else 25.0))
        interval = max(5, min(interval, 1000))
        try:
            self._video_timer.timeout.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._video_timer.setInterval(interval)
        self._video_timer.timeout.connect(lambda: self._video_tick(node, mode))
        self._batch_stop = False
        self._video_playing = True
        self._video_timer.start()
        self._append_log_hint("开始自动播放视频（原帧率约 {0:.1f} fps，点“停止”可停）".format(
            fps if fps and fps > 0 else 25.0))

    def _stop_video_playback(self, reason):
        """
        停止自动出画面（"停止"按钮 / 视频播到末尾 / 相机被关掉都会走这里）。

        M4 起兼管相机：相机这条路**只停画面、保留最后一帧、不关设备**（用户 2026.10.7 定）。
        M5-2 起还要**收尾正在录制的视频文件** —— 流都停了，文件必须 release，否则打不开。
        """
        self._video_playing = False
        self._camera_playing = False
        if self._video_timer is not None and self._video_timer.isActive():
            self._video_timer.stop()
        self._close_recordings(reason)
        self._append_log_hint("停止播放：{0}".format(reason))

    def _camera_tick(self, node, mode):
        """
        相机画面的一格（M4）：不像视频那样有帧号可判，只检查"相机还在不在"，
        然后用和手点一模一样的那条路径（run_flow_step / run_flow_continuous）跑一遍。
        """
        camera = self._camera_source_node()
        if camera is None:
            self._stop_video_playback("相机源节点已不存在")
            return
        if self.cap is None or not self.cap.isOpened():
            # 相机被关掉了（典型场景：用户点了"删除"）⇒ **只停播、不弹提示**，
            # 和视频那套"删掉就只停播、别再弹窗"的处理保持一致。
            self._stop_video_playback("相机已关闭")
            return
        self._video_tick_running = True
        self._video_log_throttle = True        # 出画面期间不刷执行日志（不然每格都重写表格）
        try:
            try:
                label = getattr(getattr(self, "gallery_widget", None), "count_label", None)
                if label is not None:
                    label.setText("相机画面")
            except Exception:
                pass
            if mode == "step":
                # 实时取当前选中的节点（和视频播放一样：播放中途换选中项，后续帧按新的跑）
                target = getattr(self, "selected_node", None) or node
                if target is not None:
                    self.run_flow_step(target)
            else:
                self.run_flow_continuous()
        finally:
            self._video_tick_running = False
            self._video_log_throttle = False

    def _video_tick(self, node, mode):
        """自动播放的一帧：先看要不要停；是相机就走相机那条，否则按原来的执行方式跑一帧"""
        if not self._video_playing:
            return
        if self._batch_stop:
            self._stop_video_playback("用户停止")
            return
        if self._camera_playing:
            self._camera_tick(node, mode)
            return
        from SourceOps import video_info
        video = self._video_source_node()
        if video is None:
            self._stop_video_playback("视频源节点已不存在")
            return
        count, _fps = video_info(video.params.get("video_path") or "")
        if not (video.params.get("video_path") or ""):
            # 视频已被删除 / 路径被清空：**只停播、不弹提示**（用户要求：
            # "运行时点击删除按钮后不再弹出这个弹窗，只需要清除画布上的视频即可"）
            self._stop_video_playback("视频源没有可用的视频")
            return
        index = int(video.params.get("frame_index") or 0)
        if count and index >= count:
            if video.params.get("loop"):
                video.params["frame_index"] = 0          # 反复播放
            else:
                self._stop_video_playback("已播到末尾")
                return
        self._video_tick_running = True
        self._video_log_throttle = True        # 播放中不刷执行日志（不然每格都重写表格）
        try:
            # 状态标签顺带显示帧进度（复用"图像源 (n/N)"那个标签，播放时它就是"视频帧 (n/N)"）
            try:
                label = getattr(getattr(self, "gallery_widget", None), "count_label", None)
                if label is not None:
                    label.setText("视频帧 ({0}/{1})".format(
                        min(int(video.params.get("frame_index") or 0), count or 0), count or "?"))
            except Exception:
                pass
            if mode == "step":
                # 单步播放时**实时取当前选中的节点**：用户播放中途换选中项（例如从"二值化"改成"取反"），
                # 后续帧就该按新选中的节点跑；如果用启动时捕获的那个节点，换选中项只会影响手点的那一帧
                # （用户 2026.10.6 实测报过："自动切换"状态下单步运行切不了其他节点）。
                target = getattr(self, "selected_node", None) or node
                if target is not None:
                    self.run_flow_step(target)
            else:
                self.run_flow_continuous()
        finally:
            self._video_tick_running = False
            self._video_log_throttle = False

    def stop_batch(self):
        """
        菜单 / 工具栏"停止"：中断正在跑的批量执行；视频正在自动播放也一起停掉；
        **顺手收尾正在录制的视频文件**（用户 2026.10.7："停止"就是结束录制、把文件收好）。
        """
        self._batch_stop = True
        if self._video_playing:
            self._stop_video_playback("用户停止")
        else:
            # 没在播放（例如一帧一帧点着录）也要能收尾，否则用户点了"停止"文件还是打不开
            self._close_recordings("用户停止")

    def _sync_source_nodes_to_path(self, path):
        """
        把当前页面里所有"图片源"节点的路径改成 path（图库点选后调用）。

        :param path: 图片文件路径；空字符串 / None 表示这张图没有对应文件（摄像头帧、测试图），忽略。
        """
        if not path:
            return
        changed = False
        for node in list(self.flow_nodes):
            spec = get_spec(node.name)
            if spec is None or spec.kind != KIND_SOURCE:
                continue
            if node.params.get("source_type") == "图片" and node.params.get("source_path") == path:
                continue
            node.params["source_type"] = "图片"
            node.params["source_path"] = path
            changed = True
        if changed:
            # 参数被改了，这一页要标成"有改动"，免得用户关页时丢东西
            self.flow_page_mgr.mark_dirty()

    def _clear_source_nodes_path(self, path):
        """
        把当前页"图片源"节点里路径正好等于 path 的那些清空（这张图被用户从图库里删掉时调用）。

        为什么必须清：图库删了图之后，如果图片源节点里还留着那条路径，点执行时流程照样会把
        这张图跑出来（用户实测："图像列表清空后画布确实没了，但点执行图片又出现了"）。
        """
        key = self._path_key(path)
        if not key:
            return
        for node in list(self.flow_nodes):
            spec = get_spec(node.name)
            if spec is None or spec.kind != KIND_SOURCE:
                continue
            if self._path_key(node.params.get("source_path") or "") == key:
                node.params["source_path"] = ""
            # 视频源节点用的是 video_path，也要一起清（用户要求：删掉这段视频就别再拿它跑）
            if self._path_key(node.params.get("video_path") or "") == key:
                node.params["video_path"] = ""

    def _ensure_source_images_in_gallery(self):
        """
        把当前页"图片源"节点用的那张图也加进图库列表（已经有的不重复加）。

        这样"图片源指定的图"和"打开文件导入的图"一样，都能在图库里看到、点选。
        """
        if not hasattr(self, 'gallery_widget') or self.gallery_widget is None:
            return
        for node in list(self.flow_nodes):
            spec = get_spec(node.name)
            if spec is None or spec.kind != KIND_SOURCE:
                continue
            path = node.params.get("source_path") or ""
            if not path:
                continue
            # 用户在图库里**主动删掉**过的图不要再自动加回来（否则"删了又出现"，用户实测报过）
            if self._is_removed_path(path):
                continue
            if node.params.get("source_type") == "文件夹":
                # 文件夹来源：把里面所有图片都放进图库（内部按路径去重、坏文件静默跳过），
                # 这样点图库缩略图就能在同一个文件夹的图片之间切换
                self.import_folder_path(path)
                continue
            if self.gallery_widget.has_path(path):
                continue
            frame, _results = spec.run(self.detector, None, (0, 0, 0, 0), node.params)
            # ★ 这张图也要登记"来自哪个文件"：否则它的图片标识会退化成 id(原图)，
            # 一旦那张图对象被重建（重新导入、重开方案），id 就变了 ——
            # 单步 / 连续的结果缓存键跟着变，表现就是"换图再切回来结果没了"。
            if path:
                self._frame_paths[id(frame)] = path
            if frame is not None:
                self.gallery_widget.add_image(frame, path)

    def import_image_path(self, path):
        """
        把一个图片文件加进图库（已经有的不重复加）。

        用户要求：读不出来的**直接跳过、不弹任何提示**。
        :return: [(frame, path)]；失败返回 []
        """
        if not path or not os.path.isfile(path):
            return []
        frame = cv2.imread(path)
        if frame is None:
            return []                      # 读不出来就跳过，不提示
        # 记住"这张图来自哪个文件"：参数 / 结果 / 缩放都用它当标识（见 _image_key_of）
        self._frame_paths[id(frame)] = path
        # 用户主动导入的图，从"删过的图"名单里放出来（重新导入就是想要它）
        self._removed_paths.discard(self._path_key(path))
        if not (hasattr(self, 'gallery_widget') and self.gallery_widget.has_path(path)):
            if hasattr(self, 'gallery_widget'):
                self.gallery_widget.add_image(frame, path)
        return [(frame, path)]

    def import_folder_path(self, folder):
        """
        把一个文件夹里的图片全部加进图库（不递归子目录；坏文件自动跳过、不弹提示）。
        :return: [(frame, path), ...]，按文件名排序
        """
        if not folder or not os.path.isdir(folder):
            return []
        exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
        loaded = []
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(exts):
                loaded.extend(self.import_image_path(os.path.join(folder, name)))
        return loaded

    def import_paths(self, paths):
        """
        统一导入入口：传进来的每一项可能是**图片文件**也可能是**文件夹**。
        图片 → 导入这一张；文件夹 → 导入里面所有图片。失败自动跳过，**全程不弹任何提示**（用户要求）。

        :return: 成功导入的 [(frame, path), ...]（不切换主画面，切画面由调用方决定）
        """
        if not paths:
            return []
        loaded = []
        for path in paths:
            if os.path.isdir(path):
                loaded.extend(self.import_folder_path(path))
            else:
                loaded.extend(self.import_image_path(path))
        return loaded


    # 流程图多页面（页面管理在 FlowPages.py）
    def _bind_current_flow_page(self):
        """把 FlowPageManager 里"当前页"的视图 / 方框 / 连线 / 提示 label 绑到主窗口上"""
        page = self.flow_page_mgr.current_page
        if page is None:
            return
        self.main_window.graphicsView = page["view"]
        self.flow_nodes = page["nodes"]
        self.flow_edges = page["edges"]
        self.current_node_label = page["label"]

    def _on_flow_page_switched(self, new_page, old_page):
        """
        流程图换页时被 FlowPageManager 回调：
        存旧页节点参数 → 绑定新页 → 取新页节点参数 → 刷新当前图片。
        （标签页本身的增删、右键菜单都在 FlowPages.py 里）
        """
        # 1、离开上一页之前：记下它的选中节点，并把它每个节点的参数存到"当前图片"名下
        if old_page is not None:
            old_page["selected_node"] = self.selected_node
            self._save_node_params(old_page["nodes"], self.current_image_key)
            # 换页了：上一页那个"输出图像"节点正在录的视频必须收尾（不然文件没写完、打不开）
            self._close_recordings("切换页面")

        # 2、把"当前页"的引用换成新页面的
        self._bind_current_flow_page()
        self.selected_node = new_page["selected_node"]

        # 3、新页面里每个节点，按"当前图片"取回它自己的参数
        #    （同一张图片在不同流程图页面上的 ROI / 算法参数也是各自独立的）
        #    同样地：还没关联任何图片/视频时不取参数，免得把刚设好的参数清掉
        if self.current_image_key is not None:
            self._load_node_params(new_page["nodes"], self.current_image_key)

        # 4、刷新底部"当前选中节点"的文字，再重新显示当前图片：
        #    会取"这一页 × 这张图片"缓存的结果，没有缓存就显示原图
        self.on_node_selected(self.selected_node)
        if self.current_static_image is not None:
            self._show_static_image(self.current_static_image)

        # 5、窗口标题跟着"当前页对应的方案文件"走（每页各有自己的方案文件）
        self._update_project_title()





def main():
    # 开启高DPI缩放支持（必须在 QApplication 创建之前设置）
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication([])

    # 主窗口图标：工程里没有 image/lena.png 也能正常启动（有就用它）
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'image', 'lena.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()

    # 窗口启动时直接最大化
    window.main_window.showMaximized()
    # window.main_window.show() # 只显示，不最大化

    app.exec_()

if __name__ == '__main__':
    main()