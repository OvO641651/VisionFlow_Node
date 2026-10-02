from PySide2.QtCore import Qt, QPointF, Signal, QObject, QTimer
from PySide2.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem, QMenu, QAction
)


class NodeItem(QObject, QGraphicsRectItem):
    """流程图节点"""

    positionChanged = Signal() # 自定义信号，解决线没有跟着方框一起动的问题

    def __init__(self, name, pos):
        """
        :param name: 节点名字
        :param pos: 位置
        """
        # 多重继承，继承QObject,QGraphicsRectItem，分别初始化
        QObject.__init__(self)
        QGraphicsRectItem.__init__(self, 0, 0, 140, 50) # 创建一个方块 (x,y,length,wide),(x,y)为左上角点的坐标
        self.name = name

        self.params = {} # 字典类型，存储该节点的参数配置

        self.setPos(pos)
        self.setBrush(QBrush(QColor(250, 250, 250))) # QBrush画刷，方块的内颜色(r,g,b),QBrush为填充颜色
        self.setPen(QPen(QColor("darkblue"), 2)) # QPen画笔，方块边框样式，参数为(颜色,线框宽度)

        # 设置标志位，可以与外界交互
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)# 允许用户用鼠标拖拽这个节点 | 允许节点被鼠标点击选中
        self.setAcceptHoverEvents(True) # 允许鼠标悬停

        # 方框的尺寸为(140, 50)
        self.in_port = QPointF(70, 0) # 输入端口（上侧）
        self.out_port = QPointF(70, 50) # 输出端口（下侧）
        # self.out_port_1 = QPointF(140, 25)  # 端口（右侧）

    def mouseMoveEvent(self, event):
        """实时拖拽响应"""
        super().mouseMoveEvent(event) # 先让底层把方块真正拖拽过去
        # 立即通知外界位置变了
        self.positionChanged.emit() # type:ignore

    def mouseReleaseEvent(self, event):
        """鼠标松开"""
        super().mouseReleaseEvent(event)  # 鼠标松开时更新最后一次位置
        self.positionChanged.emit() # type:ignore

    def mouseDoubleClickEvent(self, event):
        """双击节点时触发"""
        # 通过场景和视图找到主窗口，调用主窗口的处理函数
        if self.scene() and self.scene().views():
            # 判断节点是否还存在于画布中，以及画布是否有对应的窗口在显示
            view = self.scene().views()[0] # 获得第一个视图（画板）
            if hasattr(view, 'main_window'):
                # 找到“主窗口”并检查属性
                view.main_window.on_node_double_clicked(self) #  调用主窗口的“回调函数”
        super().mouseDoubleClickEvent(event) # 传递给父类


    def _make_context_menu(self):
        """
        组装右键菜单，返回 (menu, 菜单项字典)。

        菜单里只有"删除节点"：灰度的"作用于整图"已经挪到它自己的参数窗口里了。
        单独抽成函数是为了能自动化测试（不必真的弹菜单等用户点）。
        """
        menu = QMenu()
        actions = {"delete": QAction("删除节点", menu)}
        menu.addAction(actions["delete"])
        return menu, actions

    def contextMenuEvent(self, event):
        """右键点击节点时弹出菜单：删除节点"""
        menu, actions = self._make_context_menu()

        # 在鼠标点击的屏幕位置弹出菜单
        action = menu.exec_(event.screenPos())
        if action is None:
            return

        if action == actions.get("delete"):
            # 通过场景和视图找到主窗口，把删除交给它处理
            view = self.scene().views()[0] if (self.scene() and self.scene().views()) else None
            if view is not None and hasattr(view, 'main_window'):
                view.main_window.delete_flow_node(self)


    def paint(self, painter, option: QStyleOptionGraphicsItem, widget=None):
        """
        描述节点的样子，如输入输出节点的颜色
        :param painter:画家
        :param option:风格选择
        :param widget:装饰物
        :return:
        """
        super().paint(painter, option, widget) # 将init定义的输入输出位置和方块背景颜色等初始化
        painter.drawText(super().rect(), Qt.AlignCenter, self.name) # (rect:(length,width),居中对齐,名字(直线，圆，或者其他))

        # 绘制输入端口（红点）
        painter.setBrush(Qt.red) # setBrush填充颜色
        painter.drawEllipse(self.in_port, 4, 4) # 绘制圆形(椭圆)，圆心为in_port，(宽,高)为(4,4)

        # 绘制输出端口（蓝点）
        painter.setBrush(Qt.blue) # setBrush填充颜色
        painter.drawEllipse(self.out_port, 4, 4) # 绘制圆形(椭圆)，圆心为out_port，(宽,高)为(4,4)

        '''
        # 绘制输出端口（黄点）
        painter.setBrush(Qt.yellow)  # setBrush填充颜色
        painter.drawEllipse(self.out_port_1, 4, 4)  # 绘制圆形(椭圆)，圆心为out_port，(宽,高)为(4,4)
        '''

    def get_input_pos(self):
        """
        mapToScene：将节点自身的“本地坐标”，转换为整个流程图画布的“全局场景坐标”。
        即把方框，输入/输出圆点合并成一个控件，一起移动
        该函数可以使将左边树状图的控件拖到右边view画布时，拖到哪里方框就在哪里创建
        返回起点start位置
        """
        return self.mapToScene(self.in_port)

    def get_output_pos(self):
        return self.mapToScene(self.out_port) # 返回终点end位置


class EdgeItem(QGraphicsPathItem):
    """连线（贝塞尔曲线）：S型平滑曲线"""
    def __init__(self, start_node, end_node):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self.update_path() # 设置可更新的路径
        self.setPen(QPen(QColor("darkGray"), 2)) # 设置画笔，即设置颜色，厚度为2

    def update_path(self):
        """生成可更新路径"""
        # 实时获取启动和终点
        start = self.start_node.get_output_pos()
        end = self.end_node.get_input_pos()

        path = QPainterPath() # 创建一个画布
        path.moveTo(start) # 移动到起点start
        '''生成路径点，三次贝塞尔曲线：需要两个点ctrl1，ctrl2'''
        '''
        # 点在左右两条边上时使用
        dx = abs(end.x() - start.x()) * 0.5
        ctrl1 = QPointF(start.x() + dx, start.y())
        ctrl2 = QPointF(end.x() - dx, end.y())
        '''
        # 点在上下两条边上时使用
        dy = abs(end.y() - start.y())
        ctrl1 = QPointF(start.x(), start.y() + dy * 0.5) # * 0.5 可以使曲线平滑，不乘也可以
        ctrl2 = QPointF(end.x(), end.y() - dy * 0.5)

        path.cubicTo(ctrl1, ctrl2, end) # 从起点出发，经过控制点1 和 控制点2，最终平滑地连接到终点end
        self.setPath(path) # 设置在对象画布上

    def update_positions(self):
        """生成可更新位置"""
        self.update_path()

    def contextMenuEvent(self, event):
        """右键点击连线时弹出菜单，实现删除连线"""
        menu = QMenu() # 创建菜单容器
        delete_action = QAction("删除连线", menu) # 创建'删除连线'的按钮在菜单容器中
        menu.addAction(delete_action) # 弹出菜单并等待用户点击

        # 在鼠标点击的屏幕位置弹出菜单
        action = menu.exec_(event.screenPos())

        if action == delete_action:
            # 触发删除，通过视图寻找主窗口执行删除逻辑
            if self.scene() and self.scene().views():
                # 寻找主窗口
                view = self.scene().views()[0]
                if hasattr(view, 'main_window'):
                    # 执行删除
                    view.main_window.delete_edge(self)


class FlowchartView(QGraphicsView):
    """
    自定义流程图视图（支持拖放）
    继承画布QGraphicsView模块(用来放置方块的模块)
    """
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window # 主窗口
        self.setAcceptDrops(True) # 允许在画布内进行拖拽
        self.setDragMode(QGraphicsView.ScrollHandDrag) # 设置鼠标在空白处按住左键拖动时的行为
        # 注意：这个属性不能叫 self.scene——QGraphicsView 自己有个 scene() 方法，
        # 用同名属性会把它遮蔽掉，Python 侧就再也调不到 scene() 了
        self.flow_scene = QGraphicsScene() # 创建一个画布，专门用来存放方框（NodeItem）和连线（EdgeItem）。
        self.setScene(self.flow_scene) # 讲画布放到场景视图里面

        self._start_node = None # 开始节点
        self._temp_line = None # 灰线

        # 监听场景中选中节点的变化，用来在main.ui中显示当前选中(单击)的节点
        self.flow_scene.selectionChanged.connect(self.on_selection_changed) # type:ignore


    def dragEnterEvent(self, event):
        """
        重写QGraphicsView里面的dragEnterEvent方法
        判断当前拖过来的方框是不是画布能接受的
        """
        if event.mimeData().hasText() or isinstance(event.source(), QTreeWidget):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """
        必须加上 dragMoveEvent，否则因为 ScrollHandDrag 的干扰，dropEvent 永远不会触发
        即不能通过拖动实现将左边树状图的树枝拖动到右侧view画布中
        """
        event.acceptProposedAction()

    def dropEvent(self, event):
        """当在画布上松开鼠标（完成放下的动作）时，这个函数被触发"""
        text = ""

        # 无需依赖 MIME 数据，直接在拖拽完成时获取左侧树控件的当前选中项
        if self.main_window and hasattr(self.main_window, 'tree'):
            current = self.main_window.tree.currentItem()
            if current:
                text = current.text(0)

        # 多重保险
        if not text and self.main_window and hasattr(self.main_window, 'tree'):
            items = self.main_window.tree.selectedItems()
            if items:
                text = items[0].text(0)
        if not text:
            source = event.source()
            if isinstance(source, QTreeWidget):
                items = source.selectedItems()
                if items:
                    text = items[0].text(0)
        if not text:
            text = event.mimeData().text()

        '''
        """上面的4个if与下面的一个if效果相同，但是修改了以下部分，增强了鲁棒性，使代码不受window环境和Pyside2版本的影响"""
        # 提取从左侧拖过来的文字（模块名称）
        if isinstance(event.source(), QTreeWidget):
            items = event.source().selectedItems()
            if items:
                text = items[0].text(0)
        else:
            text = event.mimeData().text()
        '''

        # 检查数据有效，并开始执行落地操作
        if text and self.main_window:
            pos = self.mapToScene(event.pos())
            self.main_window.add_flow_node(text, pos)
            event.acceptProposedAction()
        else:
            event.ignore()

    def mousePressEvent(self, event):
        """实现计算鼠标点击时点击的点到蓝点的距离"""
        if event.button() == Qt.LeftButton:
            # 拦截鼠标左键点击时间，获取鼠标点击时的场景坐标，如果点击的是右键则无视
            scene_pos = self.mapToScene(event.pos()) # mapToScene将屏幕坐标转换为画布真实坐标(map:地图，Scene:事件)

            clicked_node = None
            clicked_port_type = None

            # 直接遍历所有节点，计算鼠标到端口的真实距离
            # 使用 self.itemAt(event.pos())只能判断是否点到了矩形方框内部，导致点中方框外部的半截蓝点时无效
            if hasattr(self.main_window, 'flow_nodes'):
                for node in self.main_window.flow_nodes:
                    if not isinstance(node, NodeItem):
                        continue
                    local_pos = node.mapFromScene(scene_pos)
                    # 检查是否点击到蓝点（输出端口），感应距离为 30个像素
                    if (local_pos - node.out_port).manhattanLength() < 30:
                        clicked_node = node
                        clicked_port_type = 'out'
                        break
                    # 检查是否点击到红点（输入端口）
                    if (local_pos - node.in_port).manhattanLength() < 30:
                        clicked_node = node
                        clicked_port_type = 'in'
                        break

            if clicked_node is not None:
                # 开始连线
                if clicked_port_type == 'out':
                    # 点到了蓝点，禁用抓握开始连线
                    self.setDragMode(QGraphicsView.NoDrag) # 设置模式，禁止拖到窗口NoDrag
                    self._start_connection(clicked_node) # 创建一条跟随鼠标的虚线
                    event.accept()
                    return
                elif clicked_port_type == 'in' and self._start_node is not None:
                    # 点到了红点并且当前有起点，完成连线
                    self._try_finish_edge(self._start_node, clicked_node, event) # 把虚线变成实线
                    return

            # 如果没点到端口，检查是否点到了节点空白处（为了能正常拖拽移动节点）
            # 没点到蓝点时，支持拖动方框
            item = self.itemAt(event.pos())
            if isinstance(item, NodeItem):
                super().mousePressEvent(event)
                return

            # 如果点到了空白背景，并且有正在拉线的操作，则取消
            if self._start_node is not None:
                self._cancel_connection()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标拖拽过程中负责画面实时反馈，分为连线状态和非连线状态"""
        if self._start_node is not None:
            # 点击蓝点进入拖出虚线状态时实现以下代码
            pos = self.mapToScene(event.pos()) # 实时获取鼠标当前在屏幕上的坐标，并转换为画布内部真实的场景坐标
            line = self._temp_line.line() # 获取灰线
            line.setP2(pos) # 设置灰线的第二个点(第一个点为引出的蓝点)
            self._temp_line.setLine(line) # 更新画面
            return
        # 非连线状态时使用，交给父类处理，实现拖到方框或者拖到背景画面
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """判断终点是否在红点上，如果在红点上则完成连线，如果不在则曲线这次连线"""
        if event.button() == Qt.LeftButton and self._start_node is not None:
            # 确定左键是抬起的 并且 有连线

            # 与mousePressEvent()函数的内容类型，mousePressEvent函数是判断蓝点，该函数是判断红点
            scene_pos = self.mapToScene(event.pos())
            target_node = None
            # 在松开鼠标时，直接遍历所有节点，判断是不是在红点上方
            if hasattr(self.main_window, 'flow_nodes'):
                for node in self.main_window.flow_nodes:
                    if not isinstance(node, NodeItem):
                        continue
                    local_pos = node.mapFromScene(scene_pos)
                    if (local_pos - node.in_port).manhattanLength() < 30:
                        target_node = node
                        break

            if target_node is not None:
                # 落在红点上，连线成功
                self._try_finish_edge(self._start_node, target_node, event)
                return

            # 没有落在红点上，连线失败，取消虚线
            self._cancel_connection()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def _start_connection(self, node):
        """负责记录连线的起点，并在屏幕上生成一条初始的灰色虚线。"""
        self._cancel_connection() # 清理残留状态，比如上一次未成功的虚线
        self._start_node = node # 开始点
        start_pos = node.get_output_pos() # 获取开始位置蓝点的位置
        # 把一条虚线画到画布上，一开始时头尾的坐标都为(start_pos.x,start_pos.y)，gray灰色，线厚为2，DashLine虚线
        self._temp_line = self.flow_scene.addLine(
            start_pos.x(), start_pos.y(),
            start_pos.x(), start_pos.y(),
            QPen(Qt.gray, 2, Qt.DashLine)
        )

    def _try_finish_edge(self, start_node, end_node, event=None):
        """将虚线变成实线，并把整个系统状态清理干净"""
        if start_node is not None and start_node != end_node:
            # 确保确实存在一个合法的起点 and 不能自己连自己
            self.main_window.add_edge(start_node, end_node) # 创建直线并画到画布上
        self._cancel_connection() # 删除之前的虚线
        if event:
            # 完成连线，不需要再通知父类处理
            event.accept()

    def _cancel_connection(self):
        """负责把当前的连线状态彻底清空，恢复到“没有拉线”的初始状态"""
        if self._temp_line:
            # 去除灰色虚线
            self.flow_scene.removeItem(self._temp_line)
            self._temp_line = None
        self._start_node = None
        self.setDragMode(QGraphicsView.ScrollHandDrag) # 连线结束，回复可以拖到背景画布的功能

    def on_selection_changed(self):
        """当场景中的选中节点发生变化时触发"""
        # 捕捉可能抛出的 RuntimeError，防止关闭窗口时因底层对象已销毁而崩溃
        try:
            selected_items = self.flow_scene.selectedItems()
        except RuntimeError:
            # 如果场景已经被销毁，直接忽略此次信号并返回
            return

        if selected_items:
            # 获取第一个被选中的图元
            node = selected_items[0]
            # 确保选中的是节点，而不是连线
            if isinstance(node, NodeItem) and hasattr(self, 'main_window'):
                self.main_window.on_node_selected(node)
        else:
            # 如果点击了空白处，取消选中状态
            if hasattr(self, 'main_window'):
                self.main_window.on_node_selected(None)


# ---------- 用于独立测试的窗口类 ----------
class FlowChartWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("流程图测试窗口")
        self.resize(800, 500)

        """测试所有树状图创建方框和曲线的场景"""
        # 创建左侧模块树状图列表
        self.tree = QTreeWidget() # 创建树状图
        self.tree.setHeaderLabel("检测模块") # 设置树状图名字
        self.tree.setDragEnabled(True) # 拖动使能，可以拖动里面树枝控件
        self.tree.setDefaultDropAction(Qt.CopyAction) # 拖拽时的行为是“复制”，而不是“剪切”
        root = QTreeWidgetItem(self.tree, ["图像处理"]) # 在tree下面创建树枝，名字为‘图像处理’
        QTreeWidgetItem(root, ["直线"]) # 在root(即‘图像处理’)下面创建树枝，名字为直线
        QTreeWidgetItem(root, ["圆"]) # 在root(即‘图像处理’)下面创建树枝，名字为圆
        self.tree.expandAll() # 默认展开所有节点树枝

        # 初始化状态栏，显示当前选中节点
        self.statusBar().showMessage("当前选中节点：无")

        # 右侧流程图
        self.flow_nodes = []  # 存放所有方框
        self.flow_edges = []  # 存放所有连线

        self.view = FlowchartView(main_window=self) # 实例化FlowchartView类
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)  # 防拖尾残影
        self.view.setAcceptDrops(True) # 接受外部拖拽进来的东西

        # 布局分割
        splitter = QSplitter(Qt.Horizontal) # 创建一个横向排列的分割器（左和右）
        splitter.addWidget(self.tree) # 左边为tree树控件
        splitter.addWidget(self.view) # 右边为view画板控件
        splitter.setStretchFactor(1, 1) # 比例为1：1
        self.setCentralWidget(splitter) # 把这一整个分割器设定为当前窗口的中心控件

        # 绑定交互事件（信号与槽），双击事件，双击树控件的树枝会执行_on_tree_double_click
        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)  # type: ignore

    def add_flow_node(self, name, pos):
        # 添加节点时，绑定信号并更新连线逻辑
        node = NodeItem(name, pos) # 创建节点方框
        self.view.flow_scene.addItem(node) # 添加到画布view中

        # 给这个节点绑上连线刷新信号
        node.positionChanged.connect(self.update_all_edges) # type:ignore
        '''
        if self.flow_nodes:
            prev_node = self.flow_nodes[-1]
            # 自动连线：前一个节点的输出 -> 当前节点的输入
            edge = EdgeItem(prev_node.get_output_pos(), node.get_input_pos()) # 连线
            self.view.flow_scene.addItem(edge) # 添加到画布view中
            self.flow_edges.append(edge) # 添加到列表flow_edges[]中，方便管理
        '''
        self.flow_nodes.append(node) # 添加到flow_nodes[]中，方便管理
        # 新节点加入后，立刻用延时器保证连线正确对齐
        # QTimer.singleShot(0, self.update_all_edges)
        return node

    def add_edge(self, start_node, end_node):
        """从蓝点开始生成一条曲线"""
        for edge in self.flow_edges:
            if edge.start_node == start_node and edge.end_node == end_node:
                # 防止重连，即相同的起点和相同的终点
                return
        edge = EdgeItem(start_node, end_node) # 实例化EdgeItem类对象
        self.view.flow_scene.addItem(edge) # 添加到画布里面
        self.flow_edges.append(edge) # 添加到列表里面记录
        self.update_all_edges() # 刷新一次画面，刷新出曲线

    def delete_flow_node(self, node_to_delete):
        """重写该函数，实现删除与需要删除的节点相连接的曲线"""
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
            self.view.flow_scene.removeItem(edge) # 从画布上擦除这条线的图像
            self.flow_edges.remove(edge) # 从数据列表里清空这条线的记录
        self.view.flow_scene.removeItem(node_to_delete) # 把这个方块本身从画布上彻底抹去
        self.flow_nodes.remove(node_to_delete) # 从列表中移除节点记录
        self.update_all_edges() # 刷新画面


    def _on_tree_double_click(self, item, column):
        """双击树状图的树枝后执行的内容，按照main.py文件中的_on_tree_double_click函数的内容修改"""
        index = self.tree.currentIndex()
        if not index.isValid():
            return
        parent = index.parent()
        if not parent.isValid():
            return
        name = index.data(0)
        if not name:
            return
        '''
        if item.parent() is None:
            # 如果点击一级树控件，则直接返回，不在view中创建方框控件，根据是子树枝来判断
            return
        name = item.text(0) # 获取节点名称
        '''

        '''计算新方框的摆放坐标'''
        if self.flow_nodes:
            # 第二个或者之后方框的位置
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x() # + 180 # x方向距离增加180
            new_y = last_node.pos().y() + 180 # y方向距离不变
        else:
            new_x, new_y = 20, 20 # 第一个方框的位置

        self.add_flow_node(name, QPointF(new_x, new_y))


    def update_all_edges(self):
        """重写该函数，实现可更新的边缘连接曲线，移动方框后曲线会跟着移动"""
        for edge in self.flow_edges:
            # 遍历所有已存在的连线
            edge.update_positions() # 命令这条连线执行自身的刷新方法

    def delete_edge(self, edge_to_delete):
        """删除连接曲线"""
        if edge_to_delete not in self.flow_edges:
            # 判断要删除的曲线线是否还在当前的连线列表中
            return
        self.view.flow_scene.removeItem(edge_to_delete) # 在画布上删除
        self.flow_edges.remove(edge_to_delete) # 在列表中删除
        self.update_all_edges() # 刷新画面

    def on_node_double_clicked(self, node):
        """独立测试窗口双击方框回调：直接在控制台打印节点名"""
        print(f"FlowChartWindow 双击了方框: {node.name}")

    def on_node_selected(self, node):
        """单击节点事件，当流程图节点被选中时更新状态栏"""
        if node:
            self.statusBar().showMessage(f"当前选中节点：{node.name}")
        else:
            self.statusBar().showMessage("当前选中节点：无")


def main():
    import sys
    app = QApplication(sys.argv)
    window = FlowChartWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()