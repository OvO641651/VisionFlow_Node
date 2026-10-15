from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QFileDialog
)
# 打开主窗口，显示小窗口，模体ui窗口，设置流程图画布，导入文件
from PySide2.QtUiTools import QUiLoader # 导入ui
from PySide2.QtGui import QIcon    # QIcon 设置图标、QImage 显示图像（QBrush/QColor 随"日志红字"搬去 core/flow_engine.py）
from PySide2.QtCore import QTimer, Qt, QPointF # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死

import cv2
import os

from core.Detector import DetectorShape
from widgets.FlowChart import NodeItem, EdgeItem, FlowchartView
from widgets.FlowPages import FlowPageManager
from ui.LineParamsDialog import LineParamsDialog
from ui.CircleParamsDialog import CircleParamsDialog
from ui.GrayParamsDialog import GrayParamsDialog
from ui.GenericProcessDialog import GenericProcessDialog
from widgets.ImageGraphicsView import ImageGraphicsView
from widgets.ImageGalleryWidget import ImageGalleryWidget
# ★ 再导出（别当"废 import"删）：用例把 main 当**聚合入口**读 `m.KIND_SOURCE` 与 `m.result_bbox`
#   —— `dsh_m3_video_check.py` / `dsh_m4_camera_check.py` / `dsh_source_check.py`（2026.10.15 收尾时踩过：
#   我按"没人 import 了"把它们删掉 ⇒ 3 套用例直接 AttributeError，门禁当场抓出来）。
from core.NodeRegistry import KIND_SINK, KIND_SOURCE, get_spec, result_bbox
# ★ 批次5 目标2 收尾（2026.10.15）：`deque` / `json` / `time` / `read_image` / `QBrush` / `QColor` /
#   `KIND_SOURCE` / `SOURCE_KEY` / `result_bbox` / `run_validation` / `node_level_param_keys` /
#   `SAVE_OVERLAY` / `SOURCE_*` / `close_all_recordings` / `set_*_provider` 这些名字**只被搬进 Mixin 的方法用过**，
#   已随各自的方法搬到 `core/flow_engine.py` · `core/project_store.py` · `services/*_service.py`，这里不再重复导入。
from ops.sink.OutputOps import close_recording
# ★ 批次5 目标2：下面三行 import 里的 `VIDEO_ROI_KEY` / `LOG_ERROR_MARK` 是**故意的再导出** ——
#   用例里有 `m.VIDEO_ROI_KEY`（dsh_m4_camera_check.py），而且 main 一直是"聚合入口"；
#   搬进 Mixin / core 的模块级常量仍然从 main 读得到 ⇒ **别当成"没用的 import"删掉**。
from core.param_store import ParamStoreMixin, VIDEO_ROI_KEY
from core.project_store import ProjectStoreMixin
from core.flow_engine import FlowEngineMixin, LOG_ERROR_MARK
from services.camera_service import CameraMixin
from services.video_service import VideoMixin
from services.gallery_service import GalleryMixin
from services.undo_service import UndoMixin    # ★ 批次5 目标4：撤销 / 重做（第 7 个 Mixin）


uiloader = QUiLoader()


class MainWindow(CameraMixin, VideoMixin, GalleryMixin, FlowEngineMixin, ParamStoreMixin, ProjectStoreMixin,
                 UndoMixin):
    # 视频 / 摄像头也当成一个"图片槽"，参数单独存一份，与图片的运行参数分开
    VIDEO_ROI_KEY = "video"

    # ==================================================================
    # 对话框出口（批次5 目标2 加）：凡"要弹窗"的地方都从这里走。
    # 为什么要收口：目标2 把一批方法搬进 Mixin（新模块），方法体里的全局名
    # 会在**新模块**里解析 —— 如果里面直接写 QMessageBox / QFileDialog，
    # 用例对 main 模块打的补丁（m.QMessageBox = FakeMB / m.QFileDialog = FakeFD）
    # 就失效了；收口到这几个薄壳之后，补丁照旧生效、行为一字不变。
    # ==================================================================
    def _warn(self, title, text):
        """统一"警告"出口（父窗口固定是主窗口）"""
        QMessageBox.warning(self.main_window, title, text)

    def _info(self, title, text):
        """统一"提示"出口（父窗口固定是主窗口）"""
        QMessageBox.information(self.main_window, title, text)

    def _ask_open_path(self):
        """选一个方案文件来打开（取消返回空串）"""
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, "打开方案", "",
            "VisionFlowNode 方案 (*.vfproj);;所有文件 (*.*)")
        return path

    def _ask_save_path(self, default_name):
        """选一个方案保存路径（取消返回空串）"""
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "保存方案", default_name,
            "VisionFlowNode 方案 (*.vfproj);;所有文件 (*.*)")
        return path

    def _ask_dir(self):
        """选一个文件夹（取消返回空串）"""
        return QFileDialog.getExistingDirectory(self.main_window, "选择文件夹")

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
        # 批量执行的"停止"标志：菜单里的"停止"把它置 True，分片循环每片之前检查一次
        self._batch_stop = False
        # ★ 批次5 目标3："运行全部"的**分片上下文**（None = 当前没有批量在跑）——
        #   一条记录装住这一批的进度 + "开始时的画面 / 选中项"（跑完要还原）。
        #   为什么必须是 self 上的字段：分片之间要过一遍事件循环，函数里的局部变量活不过去。
        self._batch_state = None
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
        from ops.source.CameraSourceOps import set_camera_frame_provider
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
        # ★ 批次5 目标4：撤销 / 重做（**必须在 setup() 之前** —— 建页时会回调换页，
        #   而换页要清空撤销栈；另外这一步也会把 .ui 里的四项控件接上线并置灰）
        self._init_undo()
        self.flow_page_mgr.setup()
        # "当前页"的引用：换页时由 _on_flow_page_switched 整体替换，
        self._bind_current_flow_page()
        # ★ 目标4：撤销栈也是"每页一条" ⇒ 这里把当前栈绑到第一页那个（setup 期间换页回调里也会绑）
        self._bind_undo_stack_for_page()


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
            # 菜单"停止"（急停）；"运行选中"在 v1.17 改成"范围模式"的选择（工具栏下拉框），不再直接执行，
            # 所以这里只接 stop。
            self.gallery_widget.stop_requested.connect(self.stop_batch)
            # ★ 批次5 目标3 修正：「自动切换」在**批量开始时定格**，所以批量跑着的时候拨它不影响
            #   正在跑的这一批（否则会"半途开始吐画面、最后停在最后一张"，用户 2026.10.15 报的就是这个）。
            #   这里只接一个薄处理器：批量进行中 + 与定格值不一致时，写一行短提示。
            self.gallery_widget.auto_switch_changed.connect(self._on_auto_switch_changed)


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

    def _add_node_to_page(self, page, name, pos, mark_dirty=True):
        """
        在指定页里建一个节点（拖拽添加与加载方案共用）。
        :param mark_dirty: 加载方案时传 False —— 从文件读进来的内容不算"未保存的改动"
        """
        node = NodeItem(name, pos)
        page["view"].flow_scene.addItem(node)
        # 方框被拖动时：刷新连线 + 把这一页标记成"有改动"
        node.positionChanged.connect(lambda *_, n=node: self._on_node_moved(page, n))  # type:ignore
        page["nodes"].append(node)
        # ★ 目标4：记下它的初始坐标（拖动撤销要知道"拖动前在哪"）
        self._undo_remember_node(node)
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

    def _on_node_moved(self, page=None, node=None):
        """方框被拖动：刷新连线，并把所在页面标记成"有改动" """
        self.flow_page_mgr.mark_dirty(page or self.flow_page_mgr.current_page)
        self.update_all_edges()
        if node is not None:
            # ★ 目标4：拖动也进撤销栈 —— 拖动期间这个信号连发很多次，`_undo_note` 会攒成
            #   "一次拖动 = 一条命令"（停下 0.4 秒后提交），所以这里每帧调用不会把栈撑爆。
            self._undo_note("move_pending", node)


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
        node = self._add_node_to_page(self.flow_page_mgr.current_page, name, pos)
        self._undo_note("add_node", node)   # ★ 目标4：记一条"新建节点"命令
        return node

    def add_edge(self, start_node, end_node):
        """从蓝点开始生成一条曲线（同一对起终点不重复连）"""
        edge = self._add_edge_to_page(self.flow_page_mgr.current_page, start_node, end_node)
        self.update_all_edges()  # 刷新一次画面，刷新出曲线
        if edge is not None:
            # ★ 目标4：记一条"新建连线"命令（`None` = 这对起终点已经连过了 ⇒ 什么都没发生，不记）
            self._undo_note("add_edge", edge)
        return edge

    def delete_flow_node(self, node_to_delete):
        """实现删除与需要删除的节点相连接的曲线"""
        if node_to_delete not in self.flow_nodes:
            # 检测节点是否存在
            return
        # ★ 目标4：**先**记命令（`_undo_note` 要在删之前把节点状态与相关连线采集下来），再删
        self._undo_note("remove_node", node_to_delete)
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
        self._undo_note("remove_edge", edge_to_delete)   # ★ 目标4：同样先记命令再删
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
        if node.name == "直线识别":
            self._open_node_dialog(node, LineParamsDialog)
        elif node.name == "圆识别":
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
        # ★ 目标4：参数是**按图片存档**的 ⇒ 记命令时要带上"这是哪张图的参数"
        #   （否则"在 A 图改完 → 切到 B 图 → 撤销 → 切回 A 图"时 A 的参数撤不回来）
        before_key = self.current_image_key
        dialog = dialog_class(self.main_window, node=node, main_window=self)
        dialog.resize(390, 560)
        self.current_dialog = dialog
        dialog.finished.connect(lambda *_: self._clear_current_dialog())
        dialog.finished.connect(lambda *_: self._mark_dirty_if_params_changed(node, before, before_key))
        dialog.exec_()  # 模态显示

    def _mark_dirty_if_params_changed(self, node, before, image_key=None):
        """参数窗口关掉之后：只有参数确实变了，才把当前页标记成"有改动" """
        if before != dict(node.params):
            self.flow_page_mgr.mark_dirty()
            # ★ 目标4：参数真的变了 ⇒ 记一条"改参数"命令（`before` 是开窗前那份快照；
            #   `image_key` 是"这张图"——参数按图片存档，撤销要按同一张图恢复）
            self._undo_note("set_params", (node, before, image_key))

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


    # （原 `run_selected_image()` 已于 2026.10.7 删除 —— 决策 f / 目标5-M1：
    #   "运行选中"的范围早就改由工具栏下拉框决定（下拉框只做选择、执行只由单步/连续执行触发），
    #   这个函数既没有任何 UI 入口、也没有任何用例引用，留着只会让"范围到底谁说了算"变含糊。）


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
        # ★ 目标4：把这一页所有节点的坐标记成"基准"（从方案读进来的节点也能撤回到原位置）
        for node in page["nodes"]:
            self._undo_remember_node(node)

    def _on_flow_page_switched(self, new_page, old_page):
        """
        流程图换页时被 FlowPageManager 回调：
        存旧页节点参数 → 绑定新页 → 取新页节点参数 → 刷新当前图片。
        （标签页本身的增删、右键菜单都在 FlowPages.py 里）
        """
        # ★ 批次5 目标4（2026.10.15 修正）：撤销栈**按页面各一条**，换页**不清空**历史 ——
        #   用户实测口径："在一个页面画好流程图 → 切到另一页画 → 回到第一页后撤销按钮失去了作用"。
        #   绑定放在 `_bind_current_flow_page()` 之后（那时"当前页"已经换好了），
        #   顺带把已删页面的栈丢掉。导入 / 新建的页面第一页用到时栈是空的 = 以导入那一刻为基准。
        self._bind_undo_stack_for_page()
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