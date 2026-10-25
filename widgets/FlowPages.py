from PySide2.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTabWidget,
                               QGraphicsView, QMenu, QMessageBox, QLineEdit,
                               QToolButton, QTabBar, QSlider, QStyle,
                               QStyleOptionSlider, QHBoxLayout)
from PySide2.QtCore import QObject, Qt, QEvent, QTimer

# ★ 批次6 目标1-M3：画布右下角小地图（全局一个，换页重绑）
from widgets.flow_minimap import FlowMiniMap

# ★ 批次6 目标1-M7b：缩放滑块在 100% 附近的"吸附区"
#   用户口径："比如到 98%-102% 之间都直接吸附变成 100%"
ZOOM_SNAP_LOW, ZOOM_SNAP_HIGH, ZOOM_SNAP_VALUE = 98, 102, 100

# ★ 批次6 目标1-M7e：**所有页的底部行统一规格**（用户："flow 页面的布局和其他的页面会有
#   细微的差别，切换页面时会有大小不一的感觉，下方的滑块大小也不一样"）——
#   把 main.ui 那套（边距 11 / 滑块 224 / 标签 35）换成与"代码搭的新页"完全一致的一套：
#   边距 9 · 行距 6 · 百分比标签固定 46 · 滑块固定 140。两边都走这个常量，切页不再跳变。
PAGE_MARGINS = (9, 9, 9, 9)      # 页面最外层 QVBoxLayout 的四周留白
PAGE_SPACING = 6                 # 画布与底部行之间的间距
FOOTER_SPACING = 6               # 底部行内部的间距
ZOOM_LABEL_WIDTH = 46            # 百分比标签固定宽（放得下 "400%"）
ZOOM_SLIDER_WIDTH = 140          # 缩放滑块固定宽


class FlowPageManager(QObject):
    """
    流程图多页面管理器：把 main.ui 里的 flowWidget(QTabWidget) 改造成"浏览器式"标签页。

    每一页都有自己独立的一份东西：
        view  —— 一页一个 FlowchartView（自带 QGraphicsScene）
        nodes —— 这一页的方框列表
        edges —— 这一页的连线列表
        label —— 这一页底部"当前选中的节点"提示
    所以各页的流程图内容互不干扰。

    标签栏上可以做的操作：
        点最后面那个独立的 + 标签 —— 新建一页（和右键菜单里的"添加页面"是同一个动作）
        双击标签        —— 就地改这一页的名字（标签文字原地变成小输入框，不弹窗口）
        拖动标签        —— 调整页面顺序（每页的内容跟着标签一起走，不会串页）
        点标签右边的 ×  —— 关掉这一页（不弹确认框，像浏览器那样干脆）
    右键标签栏还能：
        添加页面 / 重命名页面 / 删除页面（"删除页面"会先弹确认框）
    注意：至少保留一页，只剩一页时 × 和"删除页面"都会提示。

    职责边界：
        这个类只管"页面"本身（标签页、每页的画布和方框/连线表），
        不碰检测、参数、图像。
        换页之后主窗口需要做的事（切换当前节点表、换参数、刷新画面），
        通过 on_page_switched 回调交给调用方处理。
    """

    def __init__(self, tab_widget, view_factory, on_page_switched=None, parent=None,
                 on_page_close_requested=None):
        """
        :param tab_widget: main.ui 里的 QTabWidget（控件名 flowWidget）。
        :param view_factory: 创建画布的函数，签名 view_factory(parent_widget) -> FlowchartView。
        :param on_page_switched: 换页后的回调，签名 on_page_switched(new_page, old_page)。
        :param parent: Qt 父对象。
        :param on_page_close_requested: 关闭某一页之前的回调，签名
               on_page_close_requested(page) -> bool；返回 False 表示"别关这一页"。
               有未保存改动时，调用方可以在这里弹"是否保存"。
        """
        super().__init__(parent)
        self.tab_widget = tab_widget
        self.view_factory = view_factory
        self.on_page_switched = on_page_switched
        self.on_page_close_requested = on_page_close_requested

        self.pages = []            # 每页一条记录，顺序和标签栏保持一致
        self._pages_by_key = {}    # {页面标识: 页面记录}；拖动标签换序后靠它认页，不会认错
        self.current_page = None   # 当前正在使用的那一页
        self.switching = False     # 换页 / 删页过程中的保护标志（调用方也会读它）
        self._seq = 0              # 页面标识计数器(flow1,flow2,flow3...)
        self._title_editor = None        # 双击标题改名用的小输入框（没在改名字时是 None）
        self._title_editor_index = None  # 这个小输入框正在改第几页
        self.add_button = None           # "+"标签里那个按钮（setup() 里创建）
        self.add_tab_widget = None       # "+"所在的那个装饰标签（它不是流程图页面）
        self.minimap = None   # ★ 批次6 目标1-M3：全局唯一的小地图（换页重绑，不是每页一个）

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def setup(self):
        """接管 flowWidget：登记第一页，装上 + 新建 / 右键菜单 / 双击改名 / × 关闭 / 拖动换序，返回第一页记录"""
        # 1、第一页：main.ui 里已经有一页（标题 Flow），把里面的 flowView 换成自定义画布
        first_widget = self.tab_widget.widget(0)
        first_view = self._make_view(first_widget)
        # ★ M7e：第 1 页的底部行原本是 main.ui 搭的（边距 11 / 滑块 224 / 标签 35），与代码搭的
        #   新页（9 / 140 / 46）不一致 ⇒ 切页时画布与滑块大小会跳。这里**原位统一**成同一套规格。
        first_label = self._normalize_first_footer(first_widget)
        # ★ M7：状态栏右端的缩放滑块 / 百分比标签（只新增控件，未改任何现有控件名）
        self.zoom_slider = first_widget.findChild(QSlider, "zoom_slider")
        self.zoom_percent_label = first_widget.findChild(QLabel, "zoom_percent_label")
        self.current_page = self._register_page(first_widget, first_view, first_label)

        # 2、右键标签栏 → 弹出"添加页面 / 重命名页面 / 删除页面"
        tab_bar = self.tab_widget.tabBar()
        tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._on_tab_context_menu)
        tab_bar.setToolTip("点最后面那个 + 标签可以新建页面；右键点击标签可以添加 / 重命名 / 删除流程图页面；"
                           "双击标签可就地改名；拖动标签可以调整页面顺序")
        # 双击标签 → 重命名（QTabBar 没有双击信号，用事件过滤器接）
        tab_bar.installEventFilter(self)
        # 标签控件被销毁时（关窗口 / 退出程序）先把引用清掉，
        # 不然之后还会收到事件、去访问已经销毁的 C++ 对象而报 RuntimeError
        self.tab_widget.destroyed.connect(self._on_tab_widget_destroyed)

        # 3、每个标签右边显示一个 × ：点它就关掉这一页
        #    （右键菜单里的"删除页面"仍然会先弹确认框，两个入口都保留）
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)

        # 4、允许用鼠标拖动标签调整页面顺序（像浏览器 / 编辑器那样）
        self.tab_widget.setMovable(True)
        tab_bar.tabMoved.connect(self._on_tab_moved)

        # 5、在最后面放一个独立的"+"标签（它自己就是一个标签，
        #    位置和间距都由标签栏负责，不用手算坐标）
        self._create_add_tab()

        # 6、切换标签页 → 换掉 current_page 并通知调用方
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # 7、★ 批次6 目标1-M3：画布右下角小地图（全局一个，换页时重绑到新页的 view）
        self.minimap = FlowMiniMap()
        self._bind_minimap(self.current_page)
        self._bind_zoom_slider(self.current_page)
        return self.current_page

    def _create_add_tab(self):
        """
        建一个独立的"+"标签放在最后面。作为标签栏里的一个标签，位置、间距、高度全由标签栏自己算，

        它不是流程图页面：
            它没有页面记录（标签的 tabData 里没有它的标识），
            所以 _page_at() 找不到它 —— 双击改名、删除页面都会自动跳过它。
        它的"×"位置被换成了我们自己的"+"按钮，
            所以这个标签上不会出现关闭按钮。
        """
        tab_bar = self.tab_widget.tabBar()
        self.add_tab_widget = QWidget()
        index = self.tab_widget.addTab(self.add_tab_widget, "")   # 标签文字留空，只放按钮

        self.add_button = QToolButton(self.tab_widget)
        self.add_button.setText("+")
        self.add_button.setAutoRaise(True)          # 扁平样式，像浏览器那样
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setFixedSize(16, 22)        # 固定大小，让这个标签看起来像个小标签
        self.add_button.clicked.connect(self.add_page) # type:ignore
        # 把标签右侧那个位置交给我们的按钮（那个位置本来是放 × 的）
        tab_bar.setTabButton(index, QTabBar.RightSide, self.add_button)
        tab_bar.setTabToolTip(index, "新建页面")
        return index

    def _add_tab_index(self):
        """"+"那个装饰标签的下标（新页面都插在它前面，"+"永远在最后）"""
        if self.add_tab_widget is None:
            return self.tab_widget.count()
        index = self.tab_widget.indexOf(self.add_tab_widget)
        return index if index >= 0 else self.tab_widget.count()

    def _ensure_add_tab_last(self):
        """"+"标签必须永远待在最后：被拖到别处时，这里把它移回最后"""
        try:
            if self.add_tab_widget is None or self.tab_widget is None:
                return
            index = self.tab_widget.indexOf(self.add_tab_widget)
            if index < 0:
                return
            last = self.tab_widget.count() - 1
            if index != last:
                self.tab_widget.tabBar().moveTab(index, last)
                # 拖动"+"标签没有意义（它不是页面），顺手把当前页同步回真正的页面
                self._resync_current_page()
        except RuntimeError:
            # 控件已经销毁（关窗口 / 退出程序），忽略
            return

    def page_key(self):
        """当前页的标识；用来给"每页 × 每图"这类缓存做键"""
        return self.current_page["key"] if self.current_page is not None else None

    def add_page(self):
        """添加一页流程图，并自动切换到新页面，返回新页记录"""
        page_widget = QWidget()
        layout = QVBoxLayout(page_widget)
        view = self._create_view(page_widget)
        layout.addWidget(view)
        # ★ M7d：底部那行也要带「缩放滑块 + 百分比」（第 1 页这组控件在 main.ui 里；
        #         新建页必须自己建一份，否则换页后缩放滑块就"消失"了 —— 用户实测现象）
        label = self._add_page_footer(layout, page_widget)

        # 用页面标识来编号；再用 _unique_title 挡一下"用户手动改过名字"造成的重名
        title = self._unique_title("Flow{0}".format(self._seq + 1))
        # 新页面插在"+"标签前面（"+"永远待在最后）
        index = self.tab_widget.insertTab(self._add_tab_index(), page_widget, title)
        page = self._register_page(page_widget, view, label)

        # 切到新页面（会触发 currentChanged → _on_tab_changed → 通知调用方）
        self.tab_widget.setCurrentIndex(index)
        return page

    def append_pages(self, titles):
        """
        在最后追加 N 页（"打开方案"专用）：新页插在"+"标签前面，
        已有的页面原样保留（画布、方框、连线、状态都不动）。

        和 add_page() 的区别：不切换当前页、不触发换页回调；
        建完之后由调用方自己决定要不要切到哪一页。

        :param titles: 新页面的标题列表（顺序就是标签顺序）
        :return: 新页面记录列表（顺序与 titles 一致）
        """
        new_pages = []
        for title in titles or []:
            page_widget = QWidget()
            layout = QVBoxLayout(page_widget)
            view = self._create_view(page_widget)
            layout.addWidget(view)
            label = self._add_page_footer(layout, page_widget)   # ★ M7d（打开方案追加的页同样要有）
            # 插在"+"标签前面；标题重名时自动加 (2)(3)…，避免出现两个一模一样的标签
            self.tab_widget.insertTab(self._add_tab_index(), page_widget,
                                      self._unique_title(str(title)))
            new_pages.append(self._register_page(page_widget, view, label))
        # 万一"+"标签被挤跑了，这里兜一下（正常情况下它本来就在最后）
        self._ensure_add_tab_last()
        return new_pages

    def delete_page(self, index=None):
        """右键菜单"删除页面"：先弹确认框，确认后再删；成功返回 True"""
        if index is None:
            index = self.tab_widget.currentIndex()
        # 注意：标签栏里还有一个"+"装饰标签，所以判断"只剩一页"要用 len(self.pages)
        if len(self.pages) <= 1:
            QMessageBox.information(self.tab_widget, "提示", "至少要保留一个流程图页面。")
            return False
        if self._page_at(index) is None:
            return False

        # 先确认，避免误删
        title = self.tab_widget.tabText(index)
        ret = QMessageBox.question(
            self.tab_widget, "删除页面",
            "确定删除页面“{0}”吗？该页面里的方框和连线都会一起删除。".format(title),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return False

        return self._remove_page(index)

    def close_page(self, index=None):
        """
        关闭某一页（点标签右边的 × 时调用），成功返回 True。
        为了像浏览器那样干脆，这里不再弹确认框；
        右键菜单里的"删除页面"仍然会先确认，两个入口随便用哪个都行。
        """
        if index is None:
            index = self.tab_widget.currentIndex()
        if len(self.pages) <= 1:
            QMessageBox.information(self.tab_widget, "提示", "至少要保留一个流程图页面。")
            return False
        return self._remove_page(index)

    def _on_tab_close_requested(self, index):
        """点了标签上的 × ：关掉这一页"""
        self.close_page(index)

    def _remove_page(self, index):
        """真正删掉某一页：先把当前页切走 → 清画面 → 移除标签和数据记录 → 销毁页面控件"""
        deleted_page = self._page_at(index)
        if deleted_page is None:
            return False

        # 这一页有未保存的改动时，先问调用方要不要处理（例如弹"是否保存方案"）；
        # 回调返回 False 表示"取消关闭"，这里就原样返回、什么都不动。
        if self.on_page_close_requested is not None:
            if not self.on_page_close_requested(deleted_page):
                return False

        # 1、如果删的正好是当前页，先切到别的页，避免把正在使用的画布删掉
        if deleted_page is self.current_page:
            other_index = 0 if index != 0 else 1
            self.tab_widget.setCurrentIndex(other_index)   # 正常触发换页，调用方的引用会切过去

        # 2、丢掉这一页的画面（方框、连线都在这页自己的 scene 里），再移除标签页和数据记录。
        #    清空 scene 会让它发出 selectionChanged 信号，
        #    所以这一段把 switching 置上，让调用方忽略这次信号、也不会下标错位
        self.switching = True
        try:
            deleted_page["view"].flow_scene.clear()
            deleted_page["nodes"] = []
            deleted_page["edges"] = []
            if deleted_page in self.pages:
                self.pages.remove(deleted_page)
            self._pages_by_key.pop(deleted_page["key"], None)
            self.tab_widget.removeTab(index)
        finally:
            self.switching = False

        # 3、removeTab 不会删除页面控件，这里手动销毁（view / label 都是它的子控件）
        deleted_page["widget"].setParent(None)
        deleted_page["widget"].deleteLater()

        # 4、兜底：万一 Qt 的下标变化没走到回调，这里补一次同步
        self._resync_current_page()
        return True

    def _on_tab_moved(self, from_index, to_index):
        """
        用户拖动标签换了顺序。

        - 真正的页面之间换序：把 self.pages 也跟着换，保持顺序一致；
        - 如果牵涉到"+"那个装饰标签：它不是一个页面，必须永远待在最后，
          所以安排一次把它移回最后（用单次定时器，避免在信号里再改序造成递归）。
        真正"按标签找页面"用的是 _page_at()（读标签里存的页面标识），
        所以即使 Qt 先发 currentChanged、后发 tabMoved，也不会把页面认错。
        """
        if self.add_tab_widget is not None and self.tab_widget is not None:
            try:
                if self.tab_widget.indexOf(self.add_tab_widget) != self.tab_widget.count() - 1:
                    QTimer.singleShot(0, self._ensure_add_tab_last)
            except RuntimeError:
                return
        # 只有"页面和页面之间"换序才需要动 self.pages（"+"标签本来就没有页面记录）
        if not (0 <= from_index < len(self.pages) and 0 <= to_index < len(self.pages)):
            return
        page = self.pages.pop(from_index)
        self.pages.insert(to_index, page)

    def rename_page(self, index=None):
        """
        就地重命名某一页（默认当前页）：标签文字原来的位置上直接出现一个小输入框，
        回车或者点到别处就保存，按 Esc 取消。
        双击标签、或右键菜单"重命名页面"都会调到这里。
        """
        if index is None:
            index = self.tab_widget.currentIndex()
        if index < 0 or index >= self.tab_widget.count():
            return False
        if self._page_at(index) is None:
            # 这是"+"那个装饰标签（不是真正的页面），不能改名
            return False

        # 如果已经有一个名字在改，先把它收掉（相当于回车保存）
        self._close_title_editor(commit=True)

        tab_bar = self.tab_widget.tabBar()
        rect = tab_bar.tabRect(index)   # 这一页标签在标签栏里的位置和大小
        if rect.isNull() or rect.isEmpty():
            return False

        # 把小输入框直接盖在标签原来的位置上（父控件设成标签栏，坐标就一致）
        editor = QLineEdit(tab_bar)
        editor.setText(tab_bar.tabText(index))   # 预填当前名字
        editor.selectAll()                      # 全选，直接打字就能替换
        editor.setGeometry(rect.adjusted(2, 2, -2, -2))   # 留 2 像素边，不完全盖住标签框
        editor.show()
        editor.setFocus()
        editor.installEventFilter(self)         # 用来接 Esc

        # 回车 / 失去焦点 → 保存
        editor.editingFinished.connect(lambda ed=editor: self._on_title_editor_finished(ed)) # type:ignore

        self._title_editor = editor
        self._title_editor_index = index
        return True

    def _on_title_editor_finished(self, editor=None):
        """就地改名的输入框：回车或者失去焦点，把名字写回去"""
        if editor is not None and editor is not self._title_editor:
            # 不是当前这个输入框发出来的信号，忽略
            return
        self._close_title_editor(commit=True)

    def _close_title_editor(self, commit=True):
        """收掉就地改名的小输入框；commit=True 保存新名字，False 取消（保持原名）"""
        editor = self._title_editor
        index = self._title_editor_index
        if editor is None:
            return

        # 先把引用清掉：下面 hide() / deleteLater() 可能再次触发 editingFinished，
        # 那时再进来会直接返回，不会重复处理
        self._title_editor = None
        self._title_editor_index = None

        try:
            new_title = editor.text().strip()
            editor.removeEventFilter(self)
            editor.hide()
            editor.deleteLater()
        except RuntimeError:
            # 输入框已经被销毁（窗口正在关闭），不用再收尾了
            return

        if not commit or not new_title or self.tab_widget is None:
            # 取消、名字为空、或者标签控件已经销毁：都保持原来的名字不改
            return
        try:
            if 0 <= index < self.tab_widget.count():
                if self.tab_widget.tabText(index) != new_title:
                    # 改了页面名字也算这一页被改动过
                    self.mark_dirty(self._page_at(index))
                self.tab_widget.setTabText(index, new_title)
        except RuntimeError:
            # 标签控件也已经销毁，忽略即可
            pass

    # ------------------------------------------------------------------
    # "有没有未保存的改动"：关闭页面时用来提醒用户
    # ------------------------------------------------------------------
    def mark_dirty(self, page=None):
        """把某一页（默认当前页）标记成"有改动" """
        page = page or self.current_page
        if page is not None:
            page["dirty"] = True

    def clear_dirty(self, page):
        """某一页已经保存过（或者刚从文件里读进来）：清掉"有改动"标记"""
        if page is not None:
            page["dirty"] = False

    def mark_all_clean(self):
        """保存方案之后调用：所有页面都标记成"没有未保存的改动" """
        for page in self.pages:
            page["dirty"] = False

    def has_dirty_pages(self):
        """有没有任何一页存在未保存的改动"""
        return any(page.get("dirty") for page in self.pages)

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _register_page(self, widget, view, label):
        """登记一页流程图，返回这一页的记录"""
        page = {
            "key": self._seq,        # 稳定标识，用于"每页 × 每图"的检测结果缓存
            "widget": widget,        # 这一页所在的 QWidget
            "view": view,            # 这一页的画布 FlowchartView
            "label": label,          # 这一页底部提示"当前选中的节点"的 label
            "nodes": [],             # 这一页的方框
            "edges": [],             # 这一页的连线
            "selected_node": None,   # 这一页当前选中的节点
            "dirty": False,          # 有没有还没保存的改动（关闭这一页时提醒保存用）
            "project_path": None,    # 这一页对应的方案文件（新建的页是 None → 保存时弹窗选路径）
        }
        self._seq += 1
        self.pages.append(page)
        self._pages_by_key[page["key"]] = page
        # 把页面标识存进标签里：拖动标签换序之后，靠它来认"这个标签是哪一页"
        index = self.tab_widget.indexOf(widget)
        if index >= 0:
            self.tab_widget.tabBar().setTabData(index, page["key"])
        return page

    def _page_at(self, index):
        """
        按标签下标取页面记录。
        取的是"标签里存的页面标识"对应的记录，所以用户拖动标签换过顺序也不会认错页。
        """
        if self.tab_widget is None or index < 0 or index >= self.tab_widget.count():
            return None
        key = self.tab_widget.tabBar().tabData(index)
        return self._pages_by_key.get(key)

    def _create_view(self, parent_widget):
        """调用外部给的工厂创建一页画布，并设置好绘制刷新方式（防止拖尾残影）"""
        view = self.view_factory(parent_widget)
        view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        return view

    def _add_page_footer(self, layout, page_widget):
        """★ M7d：给一页补上"底部那一行"：当前选中节点提示 + 缩放百分比 + 缩放滑块。

        第 1 页这三个控件在 main.ui 里就有；之后新建的页（「+」号 / 打开方案追加）
        必须在代码里补一份 —— 否则换页后**缩放滑块会消失**（用户实测：只有启动页有滑块）。
        控件对象名与 main.ui 保持一致，`_bind_zoom_slider()` 用 findChild 就能取到。

        ★ M7e（用户："flow 页面的布局和其他的页面会有细微的差别……下方的滑块大小也不一样"）：
        这里用**统一常量**决定边距 / 间距 / 标签宽 / 滑块宽，并且**第 1 页也走这里**
        （`setup()` 里先把 main.ui 那套拆掉再重建）⇒ 所有页的底部行与画布尺寸完全一致。
        """
        # 外层布局的留白与行距：所有页统一（main.ui 原本是 11，代码默认是 9 ⇒ 统一成 9）
        try:
            layout.setContentsMargins(*PAGE_MARGINS)
            layout.setSpacing(PAGE_SPACING)
        except (AttributeError, TypeError):
            pass
        label = QLabel("未选中节点", page_widget)
        label.setObjectName("lbl_current_node")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(FOOTER_SPACING)
        row.addWidget(label)
        row.addStretch(1)
        zoom_label = QLabel("{0}%".format(ZOOM_SNAP_VALUE), page_widget)
        zoom_label.setObjectName("zoom_percent_label")
        zoom_label.setFixedWidth(ZOOM_LABEL_WIDTH)
        row.addWidget(zoom_label)
        slider = QSlider(Qt.Horizontal, page_widget)
        slider.setObjectName("zoom_slider")
        slider.setMinimum(20)
        slider.setMaximum(400)
        slider.setValue(ZOOM_SNAP_VALUE)
        slider.setFixedWidth(ZOOM_SLIDER_WIDTH)
        row.addWidget(slider)
        layout.addLayout(row)
        return label

    def _normalize_first_footer(self, page_widget):
        """★ M7e：把 main.ui 搭出来的第 1 页底部行**原位统一**到与代码搭的新页完全一致。

        ★ 为什么不拆掉重建（原计划的"甲"）：`main.py` 在 `flow_page_mgr.setup()`
        **之前**（L187）就 `findChild("lbl_current_node")` 存了引用；若这里删除重建，
        那个引用会指向已销毁的 C++ 对象 ⇒ 之后 `setText` 会 RuntimeError（用户会看到"点节点没反应"）✗
        所以改成**原位规范化**：只改属性、不换对象 —— 边距 9 / 行距 6 / 百分比标签固定 46 /
        滑块固定 140，与 `_add_page_footer()` 用的是**同一套常量** ⇒ 切页不再跳变 ✓
        """
        try:
            layout = page_widget.layout()
            if layout is not None:
                layout.setContentsMargins(*PAGE_MARGINS)
                layout.setSpacing(PAGE_SPACING)
            row = page_widget.findChild(QHBoxLayout, "statusZoomLayout")
            if row is not None:
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(FOOTER_SPACING)
                # ★ .ui 里那个 spacer 的 sizeHint 带 height=20 ⇒ 会把底部行整体撑高 1px
                #   （实测：上游 20 / 代码版 19 ⇒ 切页时画布高度差 1px）。换成 h=0 的 stretch，
                #   与 `_add_page_footer()` 里的 `addStretch(1)` 等价 ⇒ 行高一致 ✓
                for i in range(row.count()):
                    item = row.itemAt(i)
                    if item is not None and item.spacerItem() is not None:
                        row.removeItem(item)
                        row.insertStretch(i, 1)
                        break
            label = page_widget.findChild(QLabel, "lbl_current_node")
            zoom_label = page_widget.findChild(QLabel, "zoom_percent_label")
            if zoom_label is not None:
                zoom_label.setFixedWidth(ZOOM_LABEL_WIDTH)
            slider = page_widget.findChild(QSlider, "zoom_slider")
            if slider is not None:
                slider.setFixedWidth(ZOOM_SLIDER_WIDTH)
                slider.setMinimum(20)
                slider.setMaximum(400)
            return label
        except RuntimeError:
            return None

    def _make_view(self, page_widget):
        """
        让一页里有一个自定义画布：
        main.ui 里的第一页已经有 QGraphicsView，用 replaceWidget 原地替换（拉伸比例、边距都会继承）；
        自己新建的空白页还没有 QGraphicsView，就直接建一个放进布局。
        """
        old_view = page_widget.findChild(QGraphicsView)
        if old_view is None:
            view = self._create_view(page_widget)
            layout = page_widget.layout()
            if layout is None:
                layout = QVBoxLayout(page_widget)
            layout.addWidget(view)
        else:
            parent_layout = old_view.parentWidget().layout()
            view = self._create_view(old_view.parentWidget())
            parent_layout.replaceWidget(old_view, view)
            # 彻底销毁旧控件，释放内存
            old_view.deleteLater()
        return view

    def _on_tab_context_menu(self, pos):
        """右键点击标签栏：弹出菜单，选择"添加页面 / 重命名页面 / 删除页面" """
        tab_bar = self.tab_widget.tabBar()
        click_index = tab_bar.tabAt(pos)   # 被右击的那一页；点在标签栏空白处会返回 -1

        # 右击的必须是一个真正的页面（"+"那个装饰标签不算），对应的菜单项才可用
        clicked_page = self._page_at(click_index)

        menu = QMenu(self.tab_widget)
        act_add = menu.addAction("添加页面")
        act_rename = menu.addAction("重命名页面")
        act_del = menu.addAction("删除页面")
        # 右击在标签栏空白处、或者右击在"+"标签上时，不知道该改哪一页，置灰
        act_rename.setEnabled(clicked_page is not None)
        # 只剩一个真页面时不允许删除，也置灰
        act_del.setEnabled(clicked_page is not None and len(self.pages) > 1)

        act = menu.exec_(tab_bar.mapToGlobal(pos))
        if act is None:
            # 用户点了菜单外面，取消操作
            return
        if act is act_add:
            self.add_page()
        elif act is act_rename and clicked_page is not None:
            self.rename_page(click_index)
        elif act is act_del and clicked_page is not None and len(self.pages) > 1:
            # 右击的是某一页就删那一页，右击空白处就删当前页
            self.delete_page(click_index if click_index >= 0 else self.tab_widget.currentIndex())

    def eventFilter(self, watched, event):
        """事件过滤器：双击标签 → 就地改名；改名输入框里按 Esc → 取消"""
        # 窗口 / 标签控件已经销毁时（程序退出阶段）不能再碰它，直接放行
        if self.tab_widget is None:
            return False

        try:
            # 1、就地改名的输入框里按 Esc：取消（回车由 editingFinished 处理）
            #    这一条只用 Python 身份比较，放在前面，尽量少去访问 C++ 对象
            if watched is self._title_editor and event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self._close_title_editor(commit=False)
                    return True

            # 2、双击标签栏上的标签（"+"那个装饰标签会被 rename_page 自己挡掉）
            if (watched is self.tab_widget.tabBar()
                    and event.type() == QEvent.MouseButtonDblClick):
                index = self.tab_widget.tabBar().tabAt(event.pos())
                if index >= 0:
                    self.rename_page(index)
                    # 这个双击已经处理掉了，不再传给标签栏
                    return True

            # 3、★ M7b：缩放滑块尺寸/显示状态变化 ⇒ 重新摆「100% 刻度线」
            if watched is getattr(self, "zoom_slider", None) and event.type() in (QEvent.Resize, QEvent.Show):
                self._ensure_zoom_marker()
                return False
        except RuntimeError:
            # 底层 C++ 对象已经被销毁（关窗口 / 退出程序时会出现），
            # 这时不用再处理事件，安静放行，避免往终端打印 Traceback
            return False

        return super().eventFilter(watched, event)

    def _on_tab_widget_destroyed(self, *args):
        """标签控件（连同整个窗口）被销毁时：把引用清掉，后续事件一律忽略"""
        self._title_editor = None
        self._title_editor_index = None
        self.add_button = None
        self.add_tab_widget = None
        self.current_page = None
        self.tab_widget = None

    def _unique_title(self, base):
        """给新页面起名字时避免和已有标签重名（用户可能手动改成过一样的名字）"""
        titles = [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]
        if base not in titles:
            return base
        n = 2
        while "{0}({1})".format(base, n) in titles:
            n += 1
        return "{0}({1})".format(base, n)

    def _on_tab_changed(self, index):
        """标签页切换：换掉 current_page，并通知调用方"""
        if self.switching:
            return
        page = self._page_at(index)
        if page is None:
            # 选中的不是真正的页面：说明用户点到了最后那个"+"装饰标签（例如点到它的空白处）。
            # 这种情况直接新建一页并切过去，效果和点 + 按钮一样。
            if index >= 0 and self.add_tab_widget is not None:
                try:
                    if index == self.tab_widget.indexOf(self.add_tab_widget):
                        self.add_page()
                except RuntimeError:
                    return
            return
        if page is self.current_page:
            # 已经就是这一页，不用重复处理
            return
        old_page = self.current_page
        self.current_page = page
        self._notify_switched(old_page)

    def _resync_current_page(self):
        """兜底同步：万一标签栏当前页和 current_page 对不上，这里纠正并通知调用方"""
        page = self._page_at(self.tab_widget.currentIndex())
        if page is not None and page is not self.current_page:
            old_page = self.current_page
            self.current_page = page
            self._notify_switched(old_page)

    def _bind_zoom_slider(self, page):
        """★ M7：把状态栏右端的缩放滑块绑到当前页画布（换页重绑，先断旧连接）。"""
        view = None if page is None else page.get("view")
        # ★ M7d：取"这一页自己的"滑块/标签（第 1 页来自 main.ui，新页由 _add_page_footer 建），
        #   并把引用同步到 self 上，供 `_ensure_zoom_marker()` / 事件过滤器使用。
        page_widget = None if page is None else page.get("widget")
        slider = page_widget.findChild(QSlider, "zoom_slider") if page_widget is not None else None
        label = page_widget.findChild(QLabel, "zoom_percent_label") if page_widget is not None else None
        self.zoom_slider = slider
        self.zoom_percent_label = label
        if view is None or slider is None:
            return
        for sig in (getattr(slider, "valueChanged", None), getattr(view, "zoom_changed", None)):
            try:
                if sig is not None:
                    sig.disconnect()
            except (RuntimeError, TypeError):
                pass
        try:
            pct = int(view.zoom_percent())
            slider.blockSignals(True)
            slider.setValue(pct)
            slider.blockSignals(False)
            if label is not None:
                label.setText("{0}%".format(pct))
        except RuntimeError:
            return

        def _on_slider(val):
            # ★ M7b（用户："98%-102% 之间都直接吸附变成 100%"）—— 拖动过程中就吸
            try:
                val = int(val)
                if ZOOM_SNAP_LOW <= val <= ZOOM_SNAP_HIGH and val != ZOOM_SNAP_VALUE:
                    slider.blockSignals(True)
                    slider.setValue(ZOOM_SNAP_VALUE)
                    slider.blockSignals(False)
                    val = ZOOM_SNAP_VALUE
                    if label is not None:
                        label.setText("{0}%".format(ZOOM_SNAP_VALUE))
            except RuntimeError:
                return
            try:
                view.set_zoom(val)
            except RuntimeError:
                pass

        def _on_zoom(pct):
            try:
                slider.blockSignals(True)
                slider.setValue(int(pct))
                slider.blockSignals(False)
                if label is not None:
                    label.setText("{0}%".format(int(pct)))
            except RuntimeError:
                pass

        try:
            slider.valueChanged.connect(_on_slider)
            view.zoom_changed.connect(_on_zoom)
        except RuntimeError:
            return
        # ★ M7b：滑块上的「100% 刻度线」—— 装一次事件过滤器（跟随尺寸变化），再摆一次位置
        try:
            if not getattr(slider, "_zoom_filter_installed", False):   # ★ M7d：每个滑块的标记各装一次
                slider.installEventFilter(self)
                slider._zoom_filter_installed = True
        except RuntimeError:
            pass
        self._ensure_zoom_marker()

    def _ensure_zoom_marker(self):
        """★ M7b：在缩放滑块上给 **100%** 画一条固定刻度线（自绘子控件，不改 QSlider 外观）。

        用户口径："对于滑动条，能否在 100% 处加个标记" ⇒ 选乙（自绘一条线）。
        Qt 的 `setTickPosition/setTickInterval` 只能按**固定间隔**画刻度（20~400 落不到只标 100 ✗），
        所以用一个 1~2px 宽的小 `QWidget` 贴在滑块上，位置按 `QStyle.SC_SliderGroove` 的几何换算。
        """
        slider = getattr(self, "zoom_slider", None)
        if slider is None:
            return
        try:
            marker = getattr(slider, "_marker_100", None)   # ★ M7d：标记按“当前页的滑块”各存一份
            if marker is None:
                marker = QWidget(slider)
                marker.setObjectName("zoom_100_marker")
                marker.setAttribute(Qt.WA_TransparentForMouseEvents, True)   # 不挡滑块拖动
                marker.setStyleSheet("background-color: #D08A20;")           # 与橙色视口框同色系
                self._zoom_marker = marker
                slider._marker_100 = marker
            option = QStyleOptionSlider()
            option.initFrom(slider)
            option.minimum = slider.minimum()
            option.maximum = slider.maximum()
            option.sliderPosition = slider.value()
            option.orientation = Qt.Horizontal
            groove = slider.style().subControlRect(
                QStyle.CC_Slider, option, QStyle.SC_SliderGroove, slider)
            lo, hi = float(slider.minimum()), float(slider.maximum())
            ratio = 0.0 if hi <= lo else (float(ZOOM_SNAP_VALUE) - lo) / (hi - lo)
            x = float(groove.left()) + ratio * float(groove.width())
            marker.setGeometry(int(round(x)) - 1, groove.top() - 2, 2, groove.height() + 4)
            marker.raise_()
            marker.show()
        except RuntimeError:
            return

    def _bind_minimap(self, page):
        """把全局唯一的小地图重绑到某一页的画布（★ 批次6 目标1-M3：换页重绑，不残留旧页）。"""
        mm = getattr(self, "minimap", None)
        if mm is None or page is None:
            return
        try:
            mm.bind_view(page.get("view"))   # 内部会断开旧信号、setParent 到新画布视口、贴右下角
        except RuntimeError:
            return                            # 控件/画布已销毁（关窗口、删页瞬间）

    def _notify_switched(self, old_page):
        """通知调用方：当前页换了（调用方在这里切换节点表、参数，并刷新画面）"""
        self._bind_minimap(self.current_page)   # ★ M3：换页重绑小地图
        self._bind_zoom_slider(self.current_page)   # ★ M7：换页重绑缩放滑块
        self._ensure_canvas_ready(self.current_page)   # ★ M7b：换页后兜底（画布矩形异常才补）
        if self.on_page_switched is not None:
            self.on_page_switched(self.current_page, old_page)

    def _ensure_canvas_ready(self, page):
        """★ M7b：换页后**条件自愈** —— 只有当前页画布的 sceneRect 真的不是"固定大画布"时才补。

        用户报："我更换页面后滚动条就消失了，只有第一页才能看到滚动条"。
        无头环境三轮（含 show + 事件循环 + 3 页来回切）**复现不出**：每页都是
        `sceneRect=(0,0,4000x3000)`、`h[0..3527]`、`v[0..2449]` ⇒ 滚动条都在。
        因此这里**不做"每页都重设一遍"的创可贴**，只在真的发现矩形异常时才调
        M1 的 `_apply_canvas_rect()`（幂等：原点恒 (0,0)、只向右下扩）。

        ★ 注意：**滚动条范围 = 0 不一定算异常** —— 缩放到 20% 时整块画布可能正好装进视口，
          那时没有滚动条是**正确**表现。所以判据只看 sceneRect。
        """
        view = None if page is None else page.get("view")
        if view is None:
            return
        try:
            sr = view.sceneRect()
            bad = (sr.width() < 1000.0 or sr.height() < 1000.0
                   or abs(float(sr.x())) > 0.5 or abs(float(sr.y())) > 0.5)
            if not bad:
                return                      # 正常页面一律不动
            apply_rect = getattr(view, "_apply_canvas_rect", None)
            if apply_rect is None:
                return
            apply_rect()
            try:
                view.viewport().update()
            except RuntimeError:
                pass
            self.canvas_healed = int(getattr(self, "canvas_healed", 0)) + 1
        except (RuntimeError, AttributeError):
            return


# ---------- 独立测试：不启动主程序，单独试用多页面标签 ----------
if __name__ == '__main__':
    import sys
    from PySide2.QtWidgets import QApplication, QMainWindow
    from widgets.FlowChart import FlowchartView

    class MockHost:
        """最简宿主：只满足画布的少数回调，方便单独测试本模块"""
        def __init__(self):
            self.flow_nodes = []

        def on_node_selected(self, node):
            pass

        def on_node_double_clicked(self, node):
            pass

        def delete_flow_node(self, node):
            pass

        def add_flow_node(self, name, pos):
            pass

        def add_edge(self, start_node, end_node):
            pass

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.resize(900, 600)

    # 模拟 main.ui：一个 flowWidget，里面先放一页（标题 Flow）
    tabs = QTabWidget()
    tabs.addTab(QWidget(), "Flow")
    window.setCentralWidget(tabs)

    host = MockHost()
    manager = FlowPageManager(tabs, lambda parent: FlowchartView(parent, main_window=host))
    manager.setup()
    print("初始页面数：", tabs.count(), " 当前页标识：", manager.page_key())

    manager.add_page()
    print("添加后页面数：", tabs.count(), " 当前页标识：", manager.page_key())
    print("提示：点最后面那个 + 标签可直接新建页面；右键标签栏可以添加 / 重命名 / 删除页面；"
          "双击标签可就地改名；拖动标签可换顺序；点标签右边的 × 可关闭这一页")

    window.show()
    sys.exit(app.exec_())

# ===================== 批次6 目标2-M3：左面板折叠 / 展开 =====================
# ★ 为什么放在本文件：用户拍板「main.py 只允许加 1~2 行调用，稍大逻辑一律先写成
#   widgets/ 或 core/ 的模块级函数」；折叠逻辑 = 纯界面行为 ⇒ 落 widgets/。
# ★ 信号接线用 QObject 子对象（parent=按钮）的绑定方法，**不用 lambda / 闭包**
#   （2026.10.18 的教训：lambda/闭包在控件析构时会偶发崩 0xC0000409）。
COLLAPSE_ARROW_OPEN = "<"
COLLAPSE_ARROW_CLOSED = ">"

# ===================== 批次6 目标3-M3：可拖分界线（QSplitter） =====================
# ★ 用户拍板：只做**左中右三个区域**（上下不做）；分界线宽 23、禁止拖成 0、
#   拖动比例不记忆、**双击 handle 复位**、折叠后仍保持「中 : 右 = 1 : 1」。
# ★ 结构在 main.ui 里**静态**建于 QSplitter（**绝不运行时 setParent 已有控件** ——
#   2026.10.18 那次运行时"包一层"导致析构偶发崩溃 0xC0000409 的教训）。
SPLITTER_HANDLE_WIDTH = 10
MAIN_SPLITTER_NAME = "main_splitter"
RIGHT_SPLITTER_NAME = "right_splitter"
_MAIN_WEIGHTS = (1, 3, 3)       # 左 : 中 : 右 的默认比例（沿用改造前 stretch 1,3,3）
_RIGHT_WEIGHTS = (16, 6)        # 图像区 : 结果区（沿用改造前 14+0+2 : 6）
_MAIN_STRETCH = (0, 1, 1)       # 窗口变大时，多出来的空间给中间与右侧（左侧保持）


def _find_splitter(host, name):
    """按对象名找 QSplitter（host 既可能是 MainWindow，也可能是主窗口 QWidget）。"""
    try:
        from PySide2.QtWidgets import QSplitter
    except Exception:
        return None
    mw = getattr(host, "main_window", host)
    try:
        return mw.findChild(QSplitter, name)
    except RuntimeError:
        return None


def _weights_of(name):
    return _MAIN_WEIGHTS if name == MAIN_SPLITTER_NAME else _RIGHT_WEIGHTS


def _proportional_sizes(sp, name):
    """按权重把当前总宽（总高）分配成一组 sizes（最后一项吃掉余数，保证总和不变）。"""
    total = sum(sp.sizes()) or (sp.width() or sp.height())
    weights = list(_weights_of(name))[:max(1, sp.count())]
    s = sum(weights) or 1
    out = [int(total * w / s) for w in weights]
    if out:
        out[-1] += total - sum(out)
    return out


def capture_splitter_defaults(host):
    """把两个 splitter 当前 sizes 记成"默认比例"（双击 handle 复位用）。"""
    done = []
    for name in (MAIN_SPLITTER_NAME, RIGHT_SPLITTER_NAME):
        sp = _find_splitter(host, name)
        if sp is None:
            continue
        try:
            sizes = list(sp.sizes())
            if sum(sizes) > 0:
                sp._m3_default_sizes = sizes
                done.append((name, sizes))
        except RuntimeError:
            continue
    return done


def reset_splitters(host):
    """双击分界线 ⇒ 回到默认比例（记过默认值就精确还原，否则按默认权重分配）。"""
    done = []
    for name in (MAIN_SPLITTER_NAME, RIGHT_SPLITTER_NAME):
        sp = _find_splitter(host, name)
        if sp is None:
            continue
        try:
            total = sum(sp.sizes())
            dflt = getattr(sp, "_m3_default_sizes", None)
            if dflt and total > 0 and abs(sum(dflt) - total) <= max(4, total // 20):
                sp.setSizes(list(dflt))
            else:
                sp.setSizes(_proportional_sizes(sp, name))
            done.append(name)
        except RuntimeError:
            continue
    return done


class _SplitterResetHost(QObject):
    """双击分界线复位 + 延迟捕获默认比例（★ 用 QObject 子对象的绑定方法，不用 lambda）。"""

    def __init__(self, host, parent=None):
        super().__init__(parent if parent is not None else host)
        self._host = host

    def eventFilter(self, obj, event):
        try:
            from PySide2.QtCore import QEvent
            if event.type() == QEvent.MouseButtonDblClick:
                reset_splitters(self._host)
                return True
        except Exception:
            pass
        return False

    def capture(self):
        """布局跑完之后再记默认比例（安装那一刻 layout 还没算出来）。"""
        return capture_splitter_defaults(self._host)


def install_main_splitter(host):
    """把「左树 | 画布 | 右侧」与「图像区 / 结果区」两条分界线装好（找不到就什么都不做）。"""
    obj = _SplitterResetHost(host)
    installed = []
    for name, stretch in ((MAIN_SPLITTER_NAME, _MAIN_STRETCH),
                          (RIGHT_SPLITTER_NAME, (0, 0))):
        sp = _find_splitter(host, name)
        if sp is None:
            continue
        try:
            sp.setHandleWidth(SPLITTER_HANDLE_WIDTH)
            sp.setChildrenCollapsible(False)
            for i, v in enumerate(stretch):
                if i < sp.count():
                    sp.setStretchFactor(i, v)
            for i in range(1, sp.count()):
                handle = sp.handle(i)
                if handle is not None:
                    handle.installEventFilter(obj)
            installed.append(name)
        except RuntimeError:
            continue
    mw = getattr(host, "main_window", host)
    try:
        mw._splitter_reset_host = obj       # 强引用，防被回收
    except Exception:
        pass
    if installed:
        try:
            from PySide2.QtCore import QTimer
            QTimer.singleShot(0, obj.capture)
        except Exception:
            pass
    return obj


def _activate_parent_layout(widget):
    """★ 显示 / 隐藏面板后**立刻让父布局重新分配空间**（真机上有 resize 事件会自然触发，
    无头环境不会 ⇒ 这里显式激活一次；对真机只是"提前生效"，行为一致）。"""
    try:
        from PySide2.QtWidgets import QLayout, QApplication
        win = widget.window()
        # ★ 面板所在的 QHBoxLayout 嵌在 QVBoxLayout 里 ⇒ 只激活 parentWidget().layout()
        #   是不够的（那是外层竖布局）⇒ 把窗口里**所有布局**都激活一次（幂等、代价可忽略）。
        # ★ 要**跑两遍**：外层布局先给"页面/TabWidget"新宽度，内层布局（tab 页 → 画布视图）
        #   才会跟着重新分配；中间让事件循环跑一次（实测一遍只更新到 flowWidget 层）。
        for _ in range(2):
            for lay in win.findChildren(QLayout):
                lay.activate()
            try:
                QApplication.processEvents()
            except Exception:
                pass
    except Exception:
        pass


def _side_by_side_layout(panel):
    """★ 批次6 目标3-M1：找「直接装着 panel 的那个横向布局」（找不到返回 None）。

    ★ 实测（2026.10.18）：`centralwidget` 的 QHBoxLayout 只有 **1 个 item（嵌套布局）**，
    真正的横向分栏在**下一层嵌套布局**里 ⇒ 必须递归进嵌套布局找，不能只看 parent().layout()。
    ★ 只动 stretch，不搬控件、不嵌套（2026.10.18 的析构崩溃教训）。
    """
    try:
        from PySide2.QtWidgets import QHBoxLayout
    except Exception:
        return None
    root = panel.parent() if panel is not None else None
    first = root.layout() if root is not None else None
    queue = [first]
    guard = 0
    while queue and guard < 50:
        guard += 1
        lay = queue.pop(0)
        if lay is None:
            continue
        try:
            count = lay.count()
        except RuntimeError:
            continue
        for i in range(count):
            it = lay.itemAt(i)
            if it is None:
                continue
            wd = it.widget()
            if wd is panel and isinstance(lay, QHBoxLayout):
                return lay
            sub = it.layout()
            if sub is not None:
                queue.append(sub)
    return None


def _apply_collapse_ratio(layout, closed):
    """折叠时把「中间画布」与「最右侧区域」设成 1:1；展开时还原原值。

    跳过「工具箱」与 14px 折叠把手本身，把剩下的两项（画布标签页、右侧容器）
    stretch 都设 1 ⇒ 两者等分剩余宽度（用户："折叠后按 1:1 布局"）。
    """
    try:
        count = layout.count()
        if count < 2:
            return
        if closed:
            if not hasattr(layout, "_m1_saved_stretches"):
                layout._m1_saved_stretches = [layout.stretch(i) for i in range(count)]
            visible = []
            for i in range(count):
                it = layout.itemAt(i)
                if it is None:
                    continue
                wd = it.widget()
                if wd is not None and wd.objectName() in ("tool_tab_widget", "btn_collapse_toolbox"):
                    continue          # 工具箱本身与 14px 把手不参与等分
                visible.append(i)     # ★ 右侧区域在 .ui 里是「嵌套布局」而不是控件 ⇒ 也要算进来
            if len(visible) >= 2:
                for i in visible:
                    layout.setStretch(i, 0)
                layout.setStretch(visible[0], 1)      # 中间：流程图画布
                layout.setStretch(visible[-1], 1)     # 右侧：图像 / 日志
        else:
            saved = getattr(layout, "_m1_saved_stretches", None)
            if saved is not None:
                for i, v in enumerate(saved):
                    if i < count:
                        layout.setStretch(i, v)
                try:
                    del layout._m1_saved_stretches
                except Exception:
                    pass
    except Exception:
        pass


class _ToolboxCollapseHost(QObject):
    """左面板折叠开关：一个按钮切换「工具箱」Tab 的显示 / 隐藏。

    ★ 目标3-M3：有 `main_splitter` 时走 **`setSizes`**（折叠后 中:右 = 1:1），
      没有时退回原来的 stretch 方案（老 .ui 也能跑）。
    """

    def __init__(self, button, panel, parent=None, host=None):
        super().__init__(parent if parent is not None else button)
        self._button = button
        self._panel = panel
        self._host = host
        self._saved_width = 0
        self._saved_sizes = None
        self._closed = False
        button.clicked.connect(self.toggle)

    def _splitter(self):
        if self._host is None:
            return None
        return _find_splitter(self._host, MAIN_SPLITTER_NAME)

    def _toggle_with_splitter(self, sp):
        """折叠 ⇒ sizes=[把手宽, w, w]（中:右 = 1:1）；展开 ⇒ 精确还原折叠前的 sizes。"""
        handle = 14                       # 折叠把手常驻宽度（就 14px）
        total = sum(sp.sizes()) or sp.width()
        if self._closed:                  # 展开
            self._panel.setVisible(True)
            self._closed = False
            if self._saved_sizes and len(self._saved_sizes) == sp.count():
                sp.setSizes(list(self._saved_sizes))
            else:
                w = max(0, total - handle)
                left = self._saved_width if self._saved_width > 0 else int(w * 0.18)
                rest = max(0, w - left)
                sp.setSizes([left, rest // 2, rest - rest // 2])
            self._button.setText(COLLAPSE_ARROW_OPEN)
            self._button.setToolTip("折叠工具箱")
        else:                             # 折叠
            try:
                self._saved_sizes = list(sp.sizes())
            except RuntimeError:
                self._saved_sizes = None
            self._saved_width = max(handle, sp.sizes()[0] if sp.count() else self._panel.width())
            self._panel.setMinimumWidth(0)
            self._panel.setVisible(False)
            w = max(0, total - handle)
            sp.setSizes([handle, w // 2, w - w // 2])
            self._closed = True
            self._button.setText(COLLAPSE_ARROW_CLOSED)
            self._button.setToolTip("展开工具箱")
        _activate_parent_layout(self._panel)

    def toggle(self, *_args):
        try:
            sp = self._splitter()
            if sp is not None:
                self._toggle_with_splitter(sp)
                return
            if self._closed:
                self._panel.setVisible(True)
                self._closed = False
                # ★ 目标3-M1：展开 ⇒ 还原折叠前的伸缩比例
                _apply_collapse_ratio(_side_by_side_layout(self._panel), False)
                # ★ 还原折叠前宽度：布局按 stretch 给的宽度可能差几像素 ⇒ 用最小宽兜住
                if self._saved_width > 0:
                    self._panel.setMinimumWidth(self._saved_width)
                _activate_parent_layout(self._panel)
                self._button.setText(COLLAPSE_ARROW_OPEN)
                self._button.setToolTip("折叠工具箱")
            else:
                w = self._panel.width()
                if w > 0:
                    self._saved_width = w
                self._panel.setMinimumWidth(0)
                self._panel.setVisible(False)
                # ★ 目标3-M1：折叠后 中间画布 : 右侧区域 = 1:1（用户：不要再把工具箱的位置全给画布）
                _apply_collapse_ratio(_side_by_side_layout(self._panel), True)
                _activate_parent_layout(self._panel)
                self._closed = True
                self._button.setText(COLLAPSE_ARROW_CLOSED)
                self._button.setToolTip("展开工具箱")
        except RuntimeError:
            pass                      # 窗口正在销毁 ⇒ 忽略


def install_toolbox_collapse(host):
    """把「工具箱」折叠开关接到 main.ui 里的 btn_collapse_toolbox 上（找不到就什么都不做）。"""
    try:
        from PySide2.QtWidgets import QToolButton
    except Exception:
        return None
    mw = getattr(host, "main_window", host)
    panel = mw.findChild(QTabWidget, "tool_tab_widget")
    button = mw.findChild(QToolButton, "btn_collapse_toolbox")
    if panel is None or button is None:
        return None
    try:
        button.setAutoRaise(True)
        button.setFixedWidth(14)
        # ★ 把手一直可见（折叠后它就是唯一的"展开"入口）
        button.setVisible(True)
    except RuntimeError:
        return None
    obj = _ToolboxCollapseHost(button, panel, parent=button, host=host)
    mw._toolbox_collapse = obj       # 存一份强引用，防被回收
    return obj


def block_group_drag(tree):
    """★ 批次6 目标2-M3c：**树干（顶层项）不许被拖拽到画布上建节点**。

    做法 = 从顶层项的 flags 里摘掉 `Qt.ItemIsDragEnabled`：
    Qt 的 `QAbstractItemView` 在**没有这个标志**时根本不会启动拖拽 ⇒ 从源头拖不动，
    不依赖 `startDrag` 子类/事件过滤器（树控件是在 `main.ui` 里声明的，换子类代价大）。
    ★ 只摘**顶层**项：子项（真实节点）照旧可以拖 ✓；用户自己加的测试树干也是顶层 ⇒ 同样被挡住 ✓
    ★ `QTreeWidgetItem` 只是 C++ 指针 ⇒ 这里**当场遍历、当场改**，不保存任何 item 引用。
    返回被处理的顶层项数（找不到树就返回 0，不抛异常）。
    """
    if tree is None:
        return 0
    count = 0
    try:
        top_count = tree.topLevelItemCount()
    except RuntimeError:
        return 0
    for i in range(top_count):
        try:
            item = tree.topLevelItem(i)
            if item is None:
                continue
            flags = item.flags()
            if flags & Qt.ItemIsDragEnabled:
                item.setFlags(flags & ~Qt.ItemIsDragEnabled)
                count += 1
        except RuntimeError:
            continue                 # 项已被销毁 ⇒ 跳过
    return count
