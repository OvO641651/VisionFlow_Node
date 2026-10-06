from PySide2.QtWidgets import (QWidget, QListWidgetItem, QListWidget,
                               QApplication, QMainWindow, QVBoxLayout,
                               QListView, QAbstractItemView,
                               QLabel, QCheckBox, QToolButton, QHBoxLayout,
                               QComboBox)
from PySide2.QtCore import Signal, Qt, QSize, QEvent
from PySide2.QtGui import QPixmap, QImage
import cv2
import os
import sys

# 图像预览进度条 QListWidget 控件

class ImageGalleryWidget(QWidget):
    """
    ImageGalleryWidget 类：图像源（图库）管理器。

    功能说明：
        接管外部传入的 QListWidget 控件，将其配置为横向排列的缩略图列表。
        提供 add_image 方法，将 OpenCV 的 BGR 图片转换成无文字的纯净缩略图添加到图库。
        当用户点击某个缩略图时，将触发 image_selected 信号，并把该图片的原图数据传送出去，供主窗口切换大图显示。

    注意：
        本控件已彻底禁用拖拽 / 放置功能（见 eventFilter）。因此只支持"点击缩略图切换大图"，
        拖动缩略图不会有任何反应，更不会复制 / 移动条目。
        图库中的图片只能通过 add_image() 主动添加，例如主窗口的"打开"按钮。
    """

    # 自定义信号：当点击缩略图时，把原图的数据（OpenCV BGR numpy数组）发送出去
    image_selected = Signal(object)

    # 自定义信号：点击缩略图时，把它对应的**文件路径**发送出去
    # （路径可能为空：摄像头抓帧、测试图这些没有对应文件）
    # 主窗口用它把"图片源"节点的路径同步过去——图库和图片源节点是统一的
    image_path_selected = Signal(object)

    # 条目里存"图片文件路径"用的角色（Qt.UserRole 已经存了原图数据，往后排一个）
    PATH_ROLE = Qt.UserRole + 1

    # ------------------------------------------------------------------
    # 工具栏相关信号（2026.10.6 加）
    # 图库只负责"界面 + 状态"，具体干活（选文件、跑流程、清缓存）全部交给主窗口，
    # 保持"视图 / 逻辑"这一层分工不变。
    # ------------------------------------------------------------------
    add_requested = Signal()               # 点了"＋图片"：交给主窗口打开文件
    add_folder_requested = Signal()        # 点了"＋文件夹"：交给主窗口选文件夹并导入
    delete_requested = Signal(object)      # 点了"删除"：参数 = 要删除的条目
    run_all_requested = Signal()           # 保留（V2 之后没再用按钮直连，留给以后扩展）
    auto_switch_changed = Signal(bool)     # "自动切换"开关变化（= 执行时是否跟随）
    run_selected_requested = Signal()      # 菜单"运行选中"：只跑当前选中的那一张
    stop_requested = Signal()              # 菜单"停止"：中断正在跑的批量执行

    # 需要拦截并丢弃的拖放类事件（配合 eventFilter 使用）
    # 类属性 _DROP_EVENTS
    # QEvent.DragEnter	拖拽进入事件	鼠标拖着一个东西刚进入控件范围时触发
    # QEvent.DragMove	拖拽移动事件	鼠标拖着东西在控件内移动时持续触发
    # QEvent.DragLeave	拖拽离开事件	鼠标拖着东西离开控件范围时触发
    # QEvent.Drop	放下事件	在控件内松开鼠标（完成放下动作）时触发
    _DROP_EVENTS = (QEvent.DragEnter, QEvent.DragMove,
                    QEvent.DragLeave, QEvent.Drop)

    def __init__(self, list_widget, parent=None):
        """
        初始化图库管理器。
        :param list_widget: 外部传入的 QListWidget 控件实例 (UI 拖放的控件)。
        :param parent: 父级组件；不传时自动挂靠到 list_widget 的父容器。
        """
        if parent is None:
            parent = list_widget.parentWidget()
        super().__init__(parent)

        # 接管外部传入的 QListWidget 控件（此处不创建新控件，仅接管）
        self.gallery_list = list_widget

        # 在代码中重新配置 QListWidget 的显示属性。
        # 这些配置在qt设计师里面已经设置，但是这里代码设置会覆盖 Qt Designer 的 UI 设置，确保在不同的运行环境下行为统一。
        #    Flow: 设置为从左到右横向排列。
        self.gallery_list.setFlow(QListWidget.LeftToRight)
        #    ViewMode: 设置为图标模式，以支持显示大图标。
        self.gallery_list.setViewMode(QListWidget.IconMode)
        #    ResizeMode: 设置为自动调整，当窗口缩放时列表项会自动适应布局。
        self.gallery_list.setResizeMode(QListWidget.Adjust)
        #    Spacing: 设置缩略图之间的水平间距为 8 像素。
        self.gallery_list.setSpacing(8)
        #    IconSize: 强行指定图标显示的尺寸为 80x70 像素。
        self.gallery_list.setIconSize(QSize(80, 70))

        #    setUniformItemSizes(True) 会强制每一个条目的尺寸严格保持一致。
        self.gallery_list.setUniformItemSizes(True)

        #    FixedHeight: 固定图库控件自身的高度为 85 像素，防止它撑破主布局。
        #    缩略图高度为 60，加上上下内边距，85 像素刚好能紧密包裹住图片，去除了下方多余的方形空白区域。
        self.gallery_list.setFixedHeight(85)

        # 彻底关闭图库控件的拖拽 / 放置功能
        # 现象：图片导入图库后，只要在控件里拖一下（把缩略图拖动，或把外部文件 /
        #       左侧树里的条目拖进来），图库中就会自动多出一张一模一样的图片。
        # 原因：QListWidget 继承自 QAbstractItemView，它本身就是拖放目标。其默认
        #       defaultDropAction 是 Qt.CopyAction，一旦拖放发生，Qt 就会以"复制"
        #       的方式新增一个条目；而条目里的图标和 UserRole 中保存的原图会被一并
        #       复制，所以看上去就是凭空多了一张相同的图片。
        # 处理：1、把相关属性显式关掉，用代码覆盖 .ui 里可能存在的设置；
        #      2、再挂事件过滤器把拖放事件直接吞掉（见 eventFilter），双保险，这样无论拖放来自哪里，都不可能再往图库里添加条目。
        self.gallery_list.setDragEnabled(False)                            # 禁止从本控件把条目拖出去
        self.gallery_list.setAcceptDrops(False)                            # 禁止接受任何拖入
        self.gallery_list.setDropIndicatorShown(False)                     # 不显示放置指示线
        self.gallery_list.setDragDropMode(QAbstractItemView.NoDragDrop)    # 直接关闭拖放模式
        self.gallery_list.setDefaultDropAction(Qt.IgnoreAction)            # 默认拖放动作改成"忽略"
        self.gallery_list.setMovement(QListView.Static)                    # 条目位置固定，不允许拖动

        # 拖放事件实际是发给 viewport 的，所以控件本体和 viewport 都要装事件过滤器
        self.gallery_list.installEventFilter(self)
        self.gallery_list.viewport().installEventFilter(self)

        # 绑定列表内部点击信号槽到自定义的处理函数
        self.gallery_list.itemClicked.connect(self._on_item_clicked)

        # 工具栏：优先收编 main.ui 里已经摆好的控件（这样用户能在 Designer 里预览整条界面）
        self._build_toolbar()

    # ------------------------------------------------------------------
    # 工具栏（图像源 n/N、自动切换、运行全部、＋图片、＋文件夹、删除、折叠占位）
    # ------------------------------------------------------------------
    @staticmethod
    def _find(host, name, cls):
        """在宿主窗口里按 objectName 找控件；找不到返回 None"""
        if host is None:
            return None
        return host.findChild(cls, name)

    def _build_toolbar(self):
        """
        建/收编工具栏。

        约定（用户 2026.10.6 定）：**控件摆在 main.ui 里**（可在 Designer 里预览），
        运行时代码 `findChild` **收编**它们；万一 .ui 里没有（例如单独使用图库的测试场景），
        就在代码里动态建一条同样的栏插到列表上方，保证控件永远存在、真源只有一套。
        """
        host = self.gallery_list.window() or self.gallery_list

        self.count_label = self._find(host, "gallery_count_label", QLabel)
        self.auto_switch_box = self._find(host, "gallery_auto_switch", QCheckBox)
        self.run_mode_box = self._find(host, "gallery_run_mode", QComboBox)
        self.stop_button = self._find(host, "gallery_stop_button", QToolButton)
        self.add_button = self._find(host, "gallery_add_button", QToolButton)
        self.add_folder_button = self._find(host, "gallery_add_folder_button", QToolButton)
        self.delete_button = self._find(host, "gallery_delete_button", QToolButton)
        self.collapse_button = self._find(host, "gallery_collapse_button", QToolButton)

        # 兜底：.ui 里缺哪个就自己造哪个（造的控件会插进下面那条动态栏里）
        created = []
        if self.count_label is None:
            self.count_label = QLabel("图像源 (0/0)")
            created.append(self.count_label)
        if self.auto_switch_box is None:
            self.auto_switch_box = QCheckBox("自动切换")
            created.append(self.auto_switch_box)
        if self.run_mode_box is None:
            self.run_mode_box = QComboBox()
            self.run_mode_box.addItems(["运行全部", "运行选中"])
            created.append(self.run_mode_box)
        if self.stop_button is None:
            self.stop_button = QToolButton()
            self.stop_button.setText("停止")
            self.stop_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            created.append(self.stop_button)
        if self.add_button is None:
            self.add_button = QToolButton()
            self.add_button.setText("＋图片")
            self.add_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            created.append(self.add_button)
        if self.add_folder_button is None:
            self.add_folder_button = QToolButton()
            self.add_folder_button.setText("＋文件夹")
            self.add_folder_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            created.append(self.add_folder_button)
        if self.delete_button is None:
            self.delete_button = QToolButton()
            self.delete_button.setText("删除")
            self.delete_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            created.append(self.delete_button)
        if self.collapse_button is None:
            self.collapse_button = QToolButton()
            self.collapse_button.setText("∨")
            self.collapse_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            self.collapse_button.setCheckable(True)
            created.append(self.collapse_button)

        self.toolbar = self._find(host, "gallery_toolbar", QWidget)
        if self.toolbar is None and created:
            # .ui 里没有那条栏：自己搭一条，插到图像列表上方
            self.toolbar = QWidget(host)
            self.toolbar.setObjectName("gallery_toolbar")
            bar_layout = QHBoxLayout(self.toolbar)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(6)
            bar_layout.addWidget(self.count_label)
            bar_layout.addStretch(1)
            for widget in (self.auto_switch_box, self.run_mode_box, self.stop_button, self.add_button,
                           self.add_folder_button, self.delete_button, self.collapse_button):
                bar_layout.addWidget(widget)
            parent = self.gallery_list.parentWidget()
            parent_layout = parent.layout() if parent is not None else None
            if parent_layout is not None:
                index = parent_layout.indexOf(self.gallery_list)
                parent_layout.insertWidget(index if index >= 0 else parent_layout.count(),
                                           self.toolbar)

        # 接线（图库只发信号，干活交给主窗口）
        self.auto_switch_box.toggled.connect(self.auto_switch_changed.emit)
        # ★ 方案 B（用户 2026.10.6 拍板）——两个开关职责正交：
        #   `运行全部`（勾选）= 唯一的"执行范围"开关：勾 = "连续执行"跑整个列表；
        #                       取消勾选 = 只跑当前这一张；**它自己不执行**；
        #                       批量运行中取消勾选 = **立刻停**（见 main.py::run_all_images）。
        #   `自动切换`（勾选）= "执行时是否跟随"：勾 = 批量执行时把选中项跟着切到正在跑的那张；
        #                       不勾 = 照样按顺序跑完，但选中项不动。
        # ★ 执行范围 = 一个**下拉框**（用户 2026.10.6 晚要求）：两项"运行全部 / 运行选中"，
        #   **永远有且只有一项**（不存在"两个都没选"的空档）。下拉框只选模式、**不执行**；
        #   执行一律交给主界面的"单步执行 / 连续执行"。停止单独做成按钮放在它右边（以后停视频也用同一个）。
        self.run_mode_box.setToolTip(
            "执行范围（这里只选模式、不执行）：运行全部 = 连续执行跑整个图像列表；"
            "运行选中 = 只跑当前选中的那一张。")
        self.auto_switch_box.setToolTip(
            "执行时是否跟随：勾选 = 批量执行时把选中项与画面跟着切到正在跑的那张；"
            "不勾 = 跑完还原成开始时那一张。")
        self.stop_button.setToolTip("停止正在跑的批量执行")
        self.stop_button.clicked.connect(self.stop_requested.emit)
        # 折叠 ∨：收起 / 展开图像列表（状态只存内存，重启复位）
        self.collapse_button.toggled.connect(self._on_collapse_toggled)
        self.add_button.clicked.connect(self.add_requested.emit)
        self.add_folder_button.clicked.connect(self.add_folder_requested.emit)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.refresh_count()

    def scope_all(self):
        """执行范围是不是"运行全部"（= 连续执行跑整个图像列表）"""
        return self.run_mode_box.currentIndex() == 0

    def scope_current(self):
        """执行范围是不是"运行选中"（= 只跑当前选中的那一张）"""
        return self.run_mode_box.currentIndex() == 1

    def run_mode(self):
        """当前模式的文字（运行全部 / 运行选中）"""
        return self.run_mode_box.currentText()

    def set_scope_all(self, all_mode=True):
        """把范围切到"运行全部"（True）或"运行选中"（False）——下拉框永远有且只有一项"""
        self.run_mode_box.setCurrentIndex(0 if all_mode else 1)

    def _on_collapse_toggled(self, checked):
        """折叠 ∨：收起时把图像列表藏起来（只留工具栏那一条），展开时恢复"""
        self.gallery_list.setVisible(not checked)
        self.collapse_button.setText("∧" if checked else "∨")

    def is_collapsed(self):
        """图像列表当前是否被折叠收起"""
        return bool(self.collapse_button.isChecked())

    def _on_delete_clicked(self):
        """
        点"删除"：把当前选中的条目交给主窗口处理（主窗口负责清参数 / 结果 / 缩放）。

        注意：列表里**没有选中项 / 列表为空**时也要把信号发出去（item 为 None）——
        例如画布上放的是"视频源"的帧（帧不进图库），此时"删除"应当退化为"清空画布"，
        否则用户点了删除什么都不会发生（用户 2026.10.6 实测报过）。
        """
        self.delete_requested.emit(self.gallery_list.currentItem())

    # ------------------------------------------------------------------
    # 给主窗口用的小接口
    # ------------------------------------------------------------------
    def count(self):
        """图库里现在有多少张图"""
        return self.gallery_list.count()

    def current_index(self):
        """当前选中第几项（没选中返回 -1）"""
        return self.gallery_list.currentRow()

    def set_current_index(self, index):
        """选中第 index 项（不会触发 itemClicked，所以不会重复执行）"""
        self.gallery_list.setCurrentRow(index)
        self.refresh_count()

    def select_frame(self, frame):
        """
        按"原图对象"选中对应条目（打开文件 / 文件夹导入后把第一张点亮，让"图像源 (n/N)"显示正确）。
        :return: 选中项的序号；没找到返回 -1
        """
        if frame is None:
            return -1
        for i in range(self.gallery_list.count()):
            if self.item_frame(self.gallery_list.item(i)) is frame:
                self.set_current_index(i)
                return i
        return -1

    def items(self):
        """按列表顺序遍历，返回 [(item, 原图, 文件路径), ...]"""
        result = []
        for i in range(self.gallery_list.count()):
            item = self.gallery_list.item(i)
            result.append((item, self.item_frame(item), self.item_path(item)))
        return result

    @staticmethod
    def item_frame(item):
        """取条目里存的原图"""
        return item.data(Qt.UserRole) if item is not None else None

    @staticmethod
    def item_path(item):
        """取条目里存的文件路径（摄像头帧 / 测试图这类没有文件的返回空字符串）"""
        return (item.data(ImageGalleryWidget.PATH_ROLE) or "") if item is not None else ""

    def auto_switch(self):
        """"自动切换"是否打开（打开 = 连续执行的范围变成整个图像列表）"""
        return bool(self.auto_switch_box.isChecked())

    def scope_all(self):
        """"运行全部"是否被勾选（= 连续执行的范围是整个图像列表；它自己不执行）"""
        return bool(getattr(self, "run_mode_box", None) is not None
                    and self.run_mode_box.currentIndex() == 0)

    def refresh_count(self):
        """刷新"图像源 (n/N)"标签：n = 当前第几张（没选中显示 0），N = 总数"""
        label = getattr(self, "count_label", None)
        if label is None:
            return
        total = self.gallery_list.count()
        row = self.gallery_list.currentRow()
        current = row + 1 if 0 <= row < total else 0
        label.setText("图像源 ({0}/{1})".format(current, total))

    def remove_item(self, item):
        """从列表里移除一个条目（不动主窗口的参数 / 缓存，那些由主窗口自己清）"""
        row = self.gallery_list.row(item)
        if row >= 0:
            self.gallery_list.takeItem(row)
            self.refresh_count()

    def eventFilter(self, watched, event):
        """
        事件过滤器：把落在图库控件上的拖放事件全部拦截并丢弃。

        :param watched: 事件发生的对象（图库控件本身，或它的 viewport）。
        :param event: Qt 传过来的事件对象。
        :return: True 表示事件已处理完毕，不再向下传递；其它事件交回基类默认处理。
        """
        if event.type() in self._DROP_EVENTS:
            event.ignore()  # 明确拒绝这次拖放
            return True     # 不再交给 QListWidget 处理，条目不会被复制 / 新增

        # 非拖放事件交回 QWidget 的默认实现，避免影响点击、绘制、滚动等正常功能
        return super().eventFilter(watched, event)

    def add_image(self, cv_img, path=None):
        """
        将一张 OpenCV 格式的图片添加到图库列表。

        :param cv_img: OpenCV 读取的 BGR 格式图像数据 (numpy 数组)。
        :param path: 这张图对应的文件路径（可选）。
                     传了就能"点图库改图片源节点的路径"；摄像头帧这类没有文件的就不传。
        :return: 新增的 QListWidgetItem
        """
        # 图像格式转换：BGR -> RGB，并转换为 Qt 能够识别的 QPixmap。
        rgb_frame = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        # 使用零拷贝方式创建 QImage
        qt_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888) # type:ignore
        # 将原始图片按比例缩小至 80x60 像素，作为缩略图显示。
        pixmap = QPixmap.fromImage(qt_img).scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # 创建一个空白的列表项，并设置图标。
        # QListWidgetItem 不能直接传 pixmap，必须使用 setIcon 方法
        item = QListWidgetItem()
        # 将刚才生成的 QPixmap 设为该条目的图标
        item.setIcon(pixmap)

        # 将原始的大图数据存到条目中。
        item.setData(Qt.UserRole, cv_img)
        # 顺便记住它来自哪个文件（没有就存 None）
        item.setData(self.PATH_ROLE, path)

        # 将配置好的条目添加到 QListWidget 中
        self.gallery_list.addItem(item)
        # 张数变了，"图像源 (n/N)"标签跟着刷新
        self.refresh_count()
        return item

    def has_path(self, path):
        """
        图库里是不是已经有这个文件了。

        批量导入 / "图片源"执行完之后顺手把它的图也放进图库时，用它去重，避免同一个文件出现两张缩略图。
        """
        if not path:
            return False
        target = os.path.normcase(os.path.abspath(path))
        for i in range(self.gallery_list.count()):
            item = self.gallery_list.item(i)
            saved = item.data(self.PATH_ROLE) if item is not None else None
            if saved and os.path.normcase(os.path.abspath(saved)) == target:
                return True
        return False

    def _on_item_clicked(self, item):
        """
        内部槽函数：处理列表项的点击事件，并发射信号。
        :param item: 被点击的 QListWidgetItem 对象。
        """
        if item is None:
            return
        # 从点击的条目中取出之前绑定的原图数据
        img_bgr = item.data(Qt.UserRole)
        if img_bgr is not None:
            # 触发自定义信号，把原图数据传给主窗口
            self.image_selected.emit(img_bgr) # type:ignore
        # 再把"这张图来自哪个文件"也发出去（可能是空字符串：摄像头帧、测试图没有文件）
        path = item.data(self.PATH_ROLE) or ""
        self.image_path_selected.emit(path) # type:ignore
        # 选中变了，"图像源 (n/N)"标签跟着刷新
        self.refresh_count()



# 独立测试代码
# 功能描述: 用于不启动主程序，单独测试该图库控件的图片加载、布局和点击交互功能。
if __name__ == '__main__':
    # 创建独立测试用的 Qt 应用
    app = QApplication(sys.argv)

    # 创建模拟主窗口，设置窗口标题和尺寸
    window = QMainWindow()
    window.setWindowTitle("ImageGalleryWidget 独立测试")
    window.resize(800, 200)

    # 模拟主 UI 的布局（放一个普通的 QListWidget 进去）
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(10, 10, 10, 10)

    test_list = QListWidget()
    layout.addWidget(test_list)

    window.setCentralWidget(central_widget)

    # 实例化我们的逻辑类（传入 test_list 作为控件引用）
    gallery_widget = ImageGalleryWidget(test_list)

    # 遍历 image 文件夹并添加所有图片，用来在 GalleryWidget 控件中展示
    image_folder = "image"
    if os.path.exists(image_folder):
        files = os.listdir(image_folder)
        # 按照文件名排序，看起来更整齐
        files.sort()

        loaded_count = 0
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                path = os.path.join(image_folder, f)
                img = cv2.imread(path)
                if img is not None:
                    gallery_widget.add_image(img)
                    loaded_count += 1
                else:
                    print(f"警告：无法读取图片文件 {f}")

        print(f"测试完成，成功加载了 {loaded_count} 张图片。")
    else:
        print(f"警告：当前目录下没有找到名为 '{image_folder}' 的文件夹，请确保程序运行目录下存在 image 文件夹。")

    # 显示窗口并进入事件循环
    window.show()
    sys.exit(app.exec_())