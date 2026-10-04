from collections import deque  # 拓扑排序要用到的队列（数据流引擎按连线顺序执行）
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
from NodeRegistry import SOURCE_KEY, get_spec, result_bbox


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

        # 每张图片上一次的执行结果缓存
        # 结构：{图片标识: {"frame": 画好检测结果的图, "data": 检测数据, "exec_info": 执行日志}}
        # 切换回某张图片时，如果这里存着它上一次的结果，就直接显示出来，不用再点执行按钮
        self.result_cache = {}

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
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;视频文件 (*.mp4 *.avi *.mkv);;所有文件(*.*)"
        )
        if not file_paths:
            # 用户点了取消，或者一个文件都没有选中
            return

        # 无论当前是播放摄像头还是视频，先关闭释放资源
        self.close_camera()

        # 把选中的文件按后缀分成 图片 / 视频 两类
        image_exts = ('.png', '.jpg', '.jpeg', '.bmp')
        video_exts = ('.mp4', '.avi', '.mkv')
        image_paths = [p for p in file_paths if p.lower().endswith(image_exts)]
        video_paths = [p for p in file_paths if p.lower().endswith(video_exts)]

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
        if image_paths:
            # 批量读取图片，读取失败的单独记下来，最后一起提示
            loaded_frames = []
            failed_names = []
            for image_path in image_paths:
                frame = cv2.imread(image_path)  # 读取图片
                if frame is None:
                    # 单张读取失败不影响其它图片，先记下文件名，最后统一提示
                    failed_names.append(os.path.basename(image_path))
                    continue
                loaded_frames.append(frame)
                # 把读取到的图片加到图库里
                if hasattr(self, 'gallery_widget'):
                    self.gallery_widget.add_image(frame)

            if not loaded_frames:
                # 一张都没读进来，直接提示并结束
                QMessageBox.warning(self.main_window, "错误", "无法读取选中的图片文件")
                return
            if failed_names:
                # 有部分图片读取失败，提示用户哪些被跳过了
                QMessageBox.warning(
                    self.main_window, "警告",
                    "以下图片读取失败，已跳过：\n" + "\n".join(failed_names)
                )

            # 记下最近打开的来源（方案文件里会记它）
            self.last_source = {"kind": "image", "path": image_paths[0]}

            # 批量导入时主画面默认显示第一张，其余的点击图库缩略图切换
            # 新导入的图片还没有执行过，所以这里只显示原图
            self._show_static_image(loaded_frames[0])

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
                nodes.append({
                    "name": name,
                    "x": x,
                    "y": y,
                    "params": dict(params) if isinstance(params, dict) else {},
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

    def _save_node_params(self, nodes, image_key):
        """
        把一批节点的当前参数存到某个图片名下。
        :param nodes: 要存的节点列表（一般是某一页流程图里的节点）。
        :param image_key: 图片标识；为 None 表示还没显示过图片/视频，这时不存。
        """
        if image_key is None:
            return
        for node in nodes:
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
        self._switch_image_params(id(frame))

        # 传 id(frame) 作为图片标识，保证每张图片的缩放互相独立
        image_key = id(frame)

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

    def _execute_static(self, frame, mode, node=None):
        """
        对一张静态图片执行检测并把结果显示出来。
        只有"单步执行"、"连续执行"两个按钮会调用它。
        执行完会把结果按图片缓存起来（见 self.result_cache），
        以后再切回这张图片时可以直接显示这次的结果，不用再点按钮。

        :param frame: OpenCV BGR 原图。
        :param mode: "step" 单步执行（只跑 node 这一个节点）；"continuous" 连续执行（跑整个流程图）。
        :param node: 单步执行时要执行的节点。
        :return: 检测到的数据列表 data。
        """
        # 保证"当前静态图片"就是这次要算的图，后面再点执行按钮时用的还是它
        self.current_static_image = frame

        # 复制图像处理，防止污染原图
        work_frame = frame.copy()

        if mode == "continuous":
            # 调用连续执行_run_flow_pipeline，接收返回的 data 和日志 exec_info
            work_frame, data, exec_info = self._run_flow_pipeline(work_frame)
        else:
            # 调用单步执行_run_flow_pipeline_step，只执行 node 这一个节点
            # （单步执行现在也会返回一行日志，否则"画面有结果、日志表却是空的"）
            work_frame, data, exec_info = self._run_flow_pipeline_step(work_frame, node)

        # 更新执行日志表格：单步 / 连续都走这里
        self._update_execution_log(exec_info)

        # 显示处理后的图像；传 id(frame) 让每张图片的缩放互相独立
        self._display_image(work_frame, id(frame))

        # 把这次的结果缓存到"这张图片 × 这一页流程图 × 本次执行方式"名下
        # 下次切回这张图片（或这一页）时可以直接显示，不用再点一次执行按钮。
        # work_frame 本来就是 frame 的独立副本，直接存起来即可。
        self.result_cache[self._result_cache_key(id(frame), mode)] = {
            "frame": work_frame,
            "data": data,
            "exec_info": exec_info,
        }

        # 保存数据并同步窗口
        self.last_detected_data = data  # 保存给以后打开的窗口使用
        if self.current_dialog and self.current_dialog.isVisible():
            self.current_dialog.update_result_count(data)

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


    def open_camera(self):
        """打开摄像头并启动视频刷新"""
        # 原本不管是图片还是视频，点击打开摄像头后都会清空原本的画面
        self.close_camera()

        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            # 如果识别不到摄像头标签，则弹出警告的小窗口
            QMessageBox.warning(self.main_window, "错误", "无法打开摄像头，请检查设备连接")
            self.cap = None
            return


        # 摄像头/视频是独立的一个"图片槽"，把各节点的运行参数切到它自己那一份
        self._switch_image_params(self.VIDEO_ROI_KEY)


        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame) # type: ignore
        self.timer.start(30)

    def close_camera(self):
        """关闭摄像头，停止定时器，清空显示区域，包括导入的视频和图片"""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        # 重置视频标注
        self._is_video_file = False

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


        # 根据模式选择执行管道
        if self.video_processing_mode == "step" and self.video_step_node:
            # 处于单步执行模式且指定了目标节点
            work_frame, data, exec_info = self._run_flow_pipeline_step(work_frame, self.video_step_node)
        else:
            # 处于连续执行模式（或未指定节点），执行完整流程图，解包三个值
            work_frame, data, exec_info = self._run_flow_pipeline(work_frame)

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

        if params.get("roi_inherit", False):
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

        out_img, results = spec.run(self.detector, in_img, (roi_x, roi_y, roi_w, roi_h), node.params)
        if out_img is None:
            # 万一某个算子忘了返回图像，就当它不改图像，保证下游还有图可用
            out_img = in_img
        return out_img, results, roi_info, spec

    def _format_result_text(self, node, results, roi_info, spec):
        """执行日志"结果数据"那一列的文案：由节点注册表提供，新增算子不用改这里"""
        if roi_info[2] <= 0 or roi_info[3] <= 0:
            return "ROI 尺寸为 0，已跳过（图像原样传给下游）"
        if spec is None:
            return "模块未实现，图像原样传给下游"
        text = spec.format_result(results)
        if node.params.get("roi_inherit", False):
            # 勾了"继承上游"之后到底继承到了什么，必须让用户看见（否则会以为继承生效了）。
            # 注意：单步执行 / 视频每帧都会走到这里，所以只能用日志文案、不能弹窗；
            # 文案也要尽量短——"结果数据"那一列显示不全会被截断。
            if roi_info[6] == "roi":
                text += "  ← 继承上游ROI框"
            elif roi_info[6] == "result":
                text += "  ← 继承上游结果框"
            else:
                text += "  ← 继承未生效（改用本节点 ROI）"
        return text

    def _render_display(self, base_img, executed):
        """
        渲染层：把数据层的图像复制一份，再按执行顺序把各节点的结果和 ROI 框画上去。

        这里画的所有东西都只活在这张显示图上，永远不会回流到数据层，
        所以下一个节点执行时看不到上一个节点画的绿线 / 红圆。

        :param base_img: 数据层底图（取最后一个执行节点的图像输出）
        :param executed: [(节点, 结果, roi_info, spec), ...]，按执行顺序
        :return: 可以直接显示的图像
        """
        display = base_img.copy()
        rois_to_draw = []

        for node, results, roi_info, spec in executed:
            if results and spec is not None and spec.draw is not None:
                # 检测类算子的结果画到显示层
                spec.draw(display, results, node.params)
            rois_to_draw.append(roi_info)

        # 结果全部画完之后再统一画 ROI 框，避免黄框被后面的算法当成图像内容
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


    def _run_flow_pipeline(self, frame):
        """
        连续执行：按连线做拓扑排序，让图像数据顺着连线在各模块之间流动。

        数据层：out_images[图像源] —— 每个节点执行完都会留下一份"图像输出"，
                下游节点的"图像源"绑定到谁，就取谁那一份；
                全局图像源（NodeRegistry.SOURCE_KEY）就是最初那一帧的副本。
        渲染层：_render_display() 最后统一画，不参与任何算法。

        :param frame: OpenCV BGR 原图（内部只用副本，不会污染原图）
        :return: (显示用图像, 所有节点结果汇总, 执行日志列表)
        """
        img = frame.copy()              # 全局图像源（数据层的起点）
        out_images = {SOURCE_KEY: img}  # {图像源标识: 图像输出}
        results_of = {}                 # {节点: 它产出的结果数据}
        roi_of = {}                     # {节点: 它这一轮实际用的 ROI}，供下游"继承"用
        executed = []                   # [(节点, 结果, roi_info, spec), ...]，按执行顺序
        all_data = []                   # 所有节点结果汇总（给结果计数用）
        exec_info = []                  # 执行日志

        if not self.flow_nodes:
            # 画布上一个方框都没有，没什么可执行的
            return img, all_data, exec_info

        # 1、拓扑排序：父节点一定排在子节点前面
        order, parents, skipped = self._build_execution_order(self.flow_nodes, self.flow_edges)
        if not order:
            # 有方框，但一条能跑的链路都没有：给一行提示，而不是静默什么都不做
            exec_info.append(("-", time.strftime("%H:%M:%S"), "提示", "-",
                              "没有可执行的流程：请先用连线把模块连起来"))
            return img, all_data, exec_info

        seq = 1
        for node in order:
            # 2、按"图像源"绑定取本节点的输入（数据层）
            source_key, source_label = self._resolve_input(node, parents[node], out_images)
            in_img = out_images.get(source_key)
            if in_img is None:
                # 绑定的图像源这一轮不存在，退回全局图像源
                source_key = SOURCE_KEY
                source_label = "全局图像源（回退）"
                in_img = out_images[SOURCE_KEY]
            in_results = results_of.get(source_key)
            in_roi = roi_of.get(source_key)   # 上游没有结果时，下游继承它这块处理区域

            # 3、执行节点；它的图像输出挂到 out_images 上，供下游当图像源
            out_img, results, roi_info, spec = self._execute_node(node, in_img, in_results, in_roi)
            out_images[node] = out_img
            results_of[node] = results
            roi_of[node] = roi_info
            executed.append((node, results, roi_info, spec))

            # 4、汇总结果 + 记一行日志（图像源也记下来，方便排查数据流走向）
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

        # 5、渲染层：底图取"当前选中的节点"的图像输出（点谁看谁），叠加也只画到它为止；
        #    没选中、或者选中的节点这一轮没执行，就退回用最后一个执行节点的输出（原来的行为）。
        base_node = self.selected_node
        if base_node in out_images:
            shown = executed[:order.index(base_node) + 1]
        else:
            base_node = order[-1]
            shown = executed
        display = self._render_display(out_images[base_node], shown)
        return display, all_data, exec_info


    def _run_flow_pipeline_step(self, frame, target_node):
        """
        单步执行：只从全局图像源跑选中的这一个节点，不跑流程图上其它的模块
        （沿用 2026.7.25 定下的规则："不管流程图中其他的流程，只执行选中的节点"）。

        所以如果这个节点开了"ROI 继承"，单步执行时上游没有结果可用，
        _resolve_roi() 会自动退回参数里手画的 ROI。

        :param frame: OpenCV BGR 原图
        :param target_node: 要执行的节点
        :return: (显示用图像, 这个节点的结果数据, 一行执行日志)
        """
        img = frame.copy()
        if target_node is None:
            return img, [], []

        out_img, results, roi_info, spec = self._execute_node(target_node, img, None)
        display = self._render_display(out_img, [(target_node, results, roi_info, spec)])

        # 单步执行也产出一行日志：否则切图回来会出现"画面有结果、日志表却是空的"，
        # 缓存里的（画面 + 结果数据 + 日志）三者就对不上了。
        exec_info = [(1, time.strftime("%H:%M:%S"), target_node.name, "全局图像源（单步）",
                      self._format_result_text(target_node, results, roi_info, spec))]
        return display, results, exec_info



    def close_event(self,event):
        """窗口关闭时释放摄像头"""
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

    def on_step_execute(self):
        """点击单步执行按钮时触发：只执行当前选中的节点"""
        # 前置检查
        if self.current_static_image is None and self.cap is None:
            # 检测是否导入图片 / 视频 或者打开摄像头
            QMessageBox.warning(self.main_window, "提示", "请先导入图片/视频或者打开摄像头！")
            return
        if self.selected_node is None:
            # 检测是否选中节点
            QMessageBox.warning(self.main_window, "提示", "请先在流程图中单击选择一个节点！")
            return

        # 处理静态图片模式
        if self.current_static_image is not None:
            # 仅执行选中的这个节点；计算、显示、写缓存、保存数据都在 _execute_static 里完成
            self._execute_static(self.current_static_image, "step", self.selected_node)
            return

        # 处理视频 / 摄像头模式
        if self.cap is not None and self.cap.isOpened():
            # 设置状态
            self.video_processing_mode = "step"
            self.video_step_node = self.selected_node
            # 立即主动刷新一帧画面，让用户立刻看到变成了单步检测的效果
            self.update_frame()

    def on_continuous_execute(self):
        """点击连续执行按钮时触发：按整个流程图顺序执行"""
        if self.current_static_image is None and self.cap is None:
            QMessageBox.warning(self.main_window, "提示", "请先导入图片/视频或者打开摄像头！")
            return

        # 静态图片模式：直接完整执行一次
        if self.current_static_image is not None:
            # 计算、显示、刷新日志表格都在 _execute_static 里完成
            self._execute_static(self.current_static_image, "continuous")
            return

        # 视频 / 摄像头模式
        if self.cap is not None and self.cap.isOpened():
            # 恢复连续执行状态
            self.video_processing_mode = "continuous"
            self.video_step_node = None
            # 立即主动刷新一帧画面，恢复完整流程图检测效果
            self.update_frame()

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
        # 根据执行记录的数量设置表格的行数，自动清空旧数据并调整表格高度
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
                self.execution_log.setItem(row, col, item)


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