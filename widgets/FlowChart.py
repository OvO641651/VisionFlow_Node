from PySide2.QtCore import Qt, QPointF, Signal, QObject, QTimer, QRectF
from PySide2.QtGui import (QColor, QPen, QPainterPath, QBrush, QFont,
                           QFontMetricsF, QPainter)

# ★ 批次6 目标1-M2a：算子名 → 图标键（零 Qt）+ 图标的占位画法（QPainter 自绘，不用图片素材）
from core.icon_keys import icon_key_for
# ★ 批次6 目标1-M4：右键画布「添加节点」两级菜单的清单（零 Qt；目标2 的树搜索以后共用这一份）
from core import node_catalog
from widgets.node_visuals import draw_icon
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem, QMenu, QAction
)


# ★ 批次6 目标1-M1（2026.10.17，用户报"拖动节点后其它节点留在最左边"）：
#   流程图**固定大画布**的尺寸与兜底余量。以前从不设 sceneRect ⇒ Qt 按内容自动算：
#   内容小时视图自动居中、内容超出视口后视图锚定场景矩形左上角 ⇒ 拖节点时其余节点整体跳。
#   设成下面这块固定大画布后：滚动条一开始就在、**原点恒 (0,0)**、只在节点被拖到画布外时
#   向右下兜底增长（原点不动 ⇒ 画面永不跳）。
CANVAS_W, CANVAS_H = 4000, 3000
CANVAS_MARGIN = 200
# ★ 批次6 目标1-M1 第 3 次修改曾加过 `FOLLOW_MARGIN = 24`（"视口跟着节点走"的**乙方案**）；
#   ★ **第 5 次修改（2026.10.17）已撤回乙**：乙会让 sceneRect 随拖动**无限增长**
#   （实测 4000×3000 → 5141×3851 → …），用户要的是"跟随到画布中间就**停止增大**"
#   ⇒ 改用 **丙 = 四个边界全固定**。乙的方案细节留在《批次6 技术方案》§4.1「★ 已撤回：乙方案」里备查。
# ★ **第 6 次修改（2026.10.17，用户选"甲"）= 丙 + 只复活乙的 B（视图跟随）**：
#   拖动时**只滚视图**（`ensureVisible`），**绝不调 `_apply_canvas_rect()`** ⇒ sceneRect 恒 4000×3000、
#   滚动条范围不变；而 `ensureVisible` 会改滚动条 ⇒ Qt **同步重投 `mouseMoveEvent`** ⇒
#   必须有 `NodeItem._in_follow` 重入锁（否则就是第 3 次那种 `stack overflow` 无限递归崩溃）。
FOLLOW_MARGIN = 24
# ★ **第 7 次修改（2026.10.17，用户："移动速度太快了，能否降低一下速度"）**：
#   第 6 次用的是 `ensureVisible()` —— "差多少就一次滚多少" ⇒ 节点一碰 24px 边距就是一记大跳
#   （实测单步滚动量 **最大 120px / 平均 113px**）。
#   ★ 第一版改成"硬上限 6px/帧"，实测**快拖时视图追不上**（节点在视口内只有 2/20 步 ✗，等于跑丢）
#   ⇒ 改成**按差距比例追（比例 + 单帧上限 + 最小步长）**：慢拖很平滑、快拖也跟得住。
FOLLOW_FACTOR = 0.35      # 每帧只追"差距"的 35%（越大跟得越紧；0.2~0.5 之间调手感）
FOLLOW_MAX_STEP = 24      # 单帧最多滚多少像素（防瞬移）
FOLLOW_MIN_STEP = 1       # 差距小于它就别动（防抖）


class NodeItem(QObject, QGraphicsRectItem):
    """流程图节点"""

    positionChanged = Signal() # 自定义信号，解决线没有跟着方框一起动的问题

    @classmethod
    def size_for(cls, name):
        """
        节点尺寸（宽随名字自适应、高固定 44）—— ★ **唯一公式**。

        批次6 目标1-M4 抽出来：右键画布建节点要"**以鼠标点为节点中心**"，
        必须先知道尺寸才能把中心换算成左上角；两处各写一份公式 ⇒ 迟早写歪（差几像素就"点哪建哪"不准）。
        """
        font = QFont()
        font.setPointSize(9)
        text_w = float(QFontMetricsF(font).width(str(name)))
        return float(max(140.0, 32.0 + 8.0 + text_w + 8.0 + 2.0)), 44.0

    def __init__(self, name, pos):
        """
        :param name: 节点名字
        :param pos: 位置
        """
        # 多重继承，继承QObject,QGraphicsRectItem，分别初始化
        QObject.__init__(self)
        # ★ 批次6 目标1-M2a：节点外观重构（方案 §4.2）—— 高固定 44；宽 = max(140, 图标块 32 + 文字宽 + 边距)
        # ★ 批次6 目标1-M4：尺寸改由 `size_for()` 统一算（"右键建节点"要用同一份公式换算"中心 → 左上角"）
        font = QFont()
        font.setPointSize(9)
        self._font = font
        self._node_w, self._node_h = self.size_for(name)
        QGraphicsRectItem.__init__(self, 0, 0, self._node_w, self._node_h) # 创建一个方块 (x,y,length,wide),(x,y)为左上角点的坐标
        self.name = name
        # ★ 四态：normal / error / idle（"selected" 不存状态，按 `isSelected()` 现判）
        # ★ M2c（2026.10.17，用户选甲）：**新建即 `idle`（灰 = 还没运行过）**；跑过一轮才变绿/红
        self._state = "idle"

        self.params = {} # 字典类型，存储该节点的参数配置

        # ★ 第 6 次修改：拖动时"视图跟随"的重入锁（`ensureVisible` 会同步重投 mouseMoveEvent）
        self._in_follow = False

        self.setPos(QPointF(max(0.0, pos.x()), max(0.0, pos.y())))  # ★ 甲：构造入口就夹在画布内（≥0,0）
        self.setBrush(QBrush(QColor(250, 250, 250))) # QBrush画刷，方块的内颜色(r,g,b),QBrush为填充颜色
        self.setPen(QPen(QColor("darkblue"), 2)) # QPen画笔，方块边框样式，参数为(颜色,线框宽度)

        # 设置标志位，可以与外界交互
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)# 允许用户用鼠标拖拽这个节点 | 允许节点被鼠标点击选中
        self.setAcceptHoverEvents(True) # 允许鼠标悬停

        # ★ 批次6 目标1-M2a：四个锚点（上 = 主输入、下 = 主输出；左 / 右本批**只画不接**，
        #   "可引线"能力在 M6、"双向"留 M8 —— 见方案 §4.2 / §4.6 / §4.9）
        _cx = self._node_w / 2.0
        _cy = self._node_h / 2.0
        self.in_port = QPointF(_cx, 0.0)              # 上（主输入）
        self.out_port = QPointF(_cx, self._node_h)    # 下（主输出）
        self.left_port = QPointF(0.0, _cy)            # 左（本批只画）
        self.right_port = QPointF(self._node_w, _cy)  # 右（本批只画）

    def _clamp_point(self, p):
        """★ 丙（第 5 次修改，2026.10.17）：把"节点左上角"夹进**固定大画布**四边内。

        规则 = **四个边界全固定**：节点的**整个矩形**必须留在画布内
        ⇒ `0 ≤ x ≤ CANVAS_W - 宽`、`0 ≤ y ≤ CANVAS_H - 高`（贴边可到 = 余量 0）。
        ★ 用 `boundingRect()`（**含画笔 2px**）而不是 `rect()`：`scene.itemsBoundingRect()`
        是按 `sceneBoundingRect()`（含画笔）算的 ⇒ 用 `rect()` 夹会让内容右缘 = 画布边 + 1
        ⇒ 反过来又触发兜底增长（实测 `sceneRect` 变 4201×3201 ✗，用例 ⑤/⑯ 照红）。
        :param p: 目标位置（节点左上角）
        :return: 夹取后的 QPointF
        """
        w = float(self.boundingRect().width())
        h = float(self.boundingRect().height())
        max_x = max(0.0, float(CANVAS_W) - w)
        max_y = max(0.0, float(CANVAS_H) - h)
        x = min(max(0.0, float(p.x())), max_x)
        y = min(max(0.0, float(p.y())), max_y)
        return QPointF(x, y)

    def setPos(self, *args):
        """★ 甲（2026.10.17）+ ★ 丙（第 5 次修改，2026.10.17）：**所有走 Python 的位置设定都在这里夹进画布**。

        为什么不用 `itemChange(ItemPositionChange)`：本类 `class NodeItem(QObject, QGraphicsRectItem)`
        （QObject 在前），**实测 PySide2 不把 `itemChange` 虚函数派发到 Python 侧** ⇒ 夹取不生效
        （用例 ⑩ 一度失败）。覆盖 `setPos` 能罩住：构造 `__init__` / 导入项目 / 撤销重做重建 /
        右键建节点 / 测试与将来代码的显式 `setPos`；Qt 内部（`ItemIsMovable` 的拖动）不走 Python
        ⇒ 那条路由 `mouseMoveEvent` 里的 `_clamp_into_canvas()` 兜。
        ★ 丙之后**四个边界都夹**（见 `_clamp_point`）；历史方案里若有超出 4000×3000 的坐标，
        导入时会被夹回画布内（当前所有已知数据都在画布内，风险低）。
        """
        if len(args) == 1:
            return super().setPos(self._clamp_point(args[0]))
        if len(args) == 2:
            return super().setPos(self._clamp_point(QPointF(float(args[0]), float(args[1]))))
        return super().setPos(*args)

    def _clamp_into_canvas(self):
        """把自身位置夹回固定大画布（★ 丙：四个边界全固定；供鼠标拖动这条路兜底）。"""
        pos = self.pos()
        clamped = self._clamp_point(pos)
        if clamped != pos:
            self.setPos(clamped)

    def _flow_view(self):
        """★ 第 6 次修改：取自己所在的 FlowchartView。

        为什么需要它：**拖动中鼠标被 item 抓着** ⇒ 视图层收不到 `mouseMoveEvent`，
        所以要跟随滚动就得从 item 这里拿到视图。
        """
        try:
            scene = self.scene()
            if scene is None:
                return None
            views = scene.views()
            return views[0] if views else None
        except RuntimeError:
            return None

    def mouseMoveEvent(self, event):
        """实时拖拽响应"""
        super().mouseMoveEvent(event) # 先让底层把方块真正拖拽过去
        self._clamp_into_canvas()     # ★ 丙：拖动时也不许出画布（四个边界全固定）
        # ★ 第 6 次修改（甲 = 丙 + 只复活乙的 B）：让视口跟着节点滚，节点始终留在视野里。
        #   · 只调 follow_item（ensureVisible）—— **绝不调 `_apply_canvas_rect()`**（那会让矩形无限增长）
        #   · ensureVisible 会改滚动条 ⇒ Qt 同步重投本函数 ⇒ 用 `_in_follow` 重入锁挡住，否则无限递归
        if not self._in_follow:
            view = self._flow_view()
            if view is not None:
                self._in_follow = True
                try:
                    view.follow_item(self)
                finally:
                    self._in_follow = False
        # 立即通知外界位置变了
        self.positionChanged.emit() # type:ignore

    def mouseReleaseEvent(self, event):
        """鼠标松开"""
        super().mouseReleaseEvent(event)  # 鼠标松开时更新最后一次位置
        self._clamp_into_canvas()         # ★ 丙：松手时再夹一次（保险）
        # ★ 第 7 次修改：限速跟随期间节点可能短暂贴边 ⇒ 松手时**不限速**拉回可见（同样持重入锁）
        if not self._in_follow:
            view = self._flow_view()
            if view is not None:
                self._in_follow = True
                try:
                    view.snap_item_visible(self)
                finally:
                    self._in_follow = False
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


    def _legacy_paint(self, painter, option: QStyleOptionGraphicsItem, widget=None):
        """★ M2a：旧版绘制已**被下方新 `paint` 取代**（保留作对照，不再被 Qt 调用）。"""
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

    # ==================================================================================
    # ★ 批次6 目标1-M2a：节点外观（方案 §4.2）
    #   圆角矩形 + 左侧绿色图标块（代码自绘图标） + 竖分隔线 + 节点名 + 四个空心圆环；
    #   四态：normal / selected（按 isSelected 现判）/ error（红）/ idle（灰）。
    #   ★ 硬兼容：`in_port` / `out_port` 属性名与位置（上/下边中点）保持不变 ——
    #      连线端点误差 < 1.5px 的老断言、以及 get_input_pos / get_output_pos 都依赖它。
    # ==================================================================================
    NODE_RADIUS = 7.0          # 圆角半径
    BLOCK_W = 32.0             # 左侧图标块宽
    BLOCK_RADIUS = 5.0         # 图标块圆角
    RING_RADIUS = 5.0          # 锚点圆环半径
    RING_WIDTH = 1.5           # 锚点圆环线宽
    COLOR_BLOCK_NORMAL = "#2E9E4F"     # 绿（正常）
    COLOR_BLOCK_ERROR = "#C62828"      # 红（出错）
    COLOR_BLOCK_IDLE = "#9E9E9E"       # 灰（未运行）
    COLOR_EDGE_NORMAL = "#B0B0B0"
    COLOR_EDGE_IDLE = "#D8D8D8"        # ★ M2c：未运行（灰态）的描边 —— 比正常更淡，弱化"没跑过"
    COLOR_EDGE_SELECTED = "#1E88E5"
    COLOR_EDGE_ERROR = "#C62828"
    COLOR_SEPARATOR = "#D0D0D0"
    COLOR_TEXT = "#202020"
    COLOR_RING = "#7A7A7A"

    def set_state(self, kind):
        """★ M2b 用：设置节点状态（normal / error / idle）。"selected" 由 Qt 选中态现判。"""
        kind = str(kind or "normal")
        if kind not in ("normal", "error", "idle", "selected"):
            kind = "normal"
        if kind == "selected":      # 传 selected 等价于"选中"——交给 Qt，不改底色
            kind = "normal"
        self._state = kind
        self.update()

    def state(self):
        return self._state

    def _block_color(self):
        if self._state == "error":
            return QColor(self.COLOR_BLOCK_ERROR)
        if self._state == "idle":
            return QColor(self.COLOR_BLOCK_IDLE)
        return QColor(self.COLOR_BLOCK_NORMAL)

    def _edge_pen(self):
        if self._state == "error":
            return QPen(QColor(self.COLOR_EDGE_ERROR), 2)
        if self.isSelected():
            pen = QPen(QColor(self.COLOR_EDGE_SELECTED), 2)
            pen.setStyle(Qt.SolidLine)
            return pen
        if self._state == "idle":                  # ★ M2c：未运行 = 淡灰描边（弱视觉）
            return QPen(QColor(self.COLOR_EDGE_IDLE), 1)
        return QPen(QColor(self.COLOR_EDGE_NORMAL), 1)

    def _ring_pen(self):
        if self.isSelected():
            return QPen(QColor(self.COLOR_EDGE_SELECTED), self.RING_WIDTH)
        return QPen(QColor(self.COLOR_RING), self.RING_WIDTH)

    def boundingRect(self):
        """★ 要含画笔宽度与四个圆环（否则拖过一次就残影）。"""
        pad = self.RING_RADIUS + self.RING_WIDTH + 2.0
        return self.rect().adjusted(-pad, -pad, pad, pad)

    def shape(self):
        """命中区 = 圆角矩形（点击/框选都按它算）。"""
        path = QPainterPath()
        path.addRoundedRect(self.rect(), self.NODE_RADIUS, self.NODE_RADIUS)
        return path

    def paint(self, painter, option: QStyleOptionGraphicsItem, widget=None):
        """★ M2a：自绘整张节点脸（不再调用 QGraphicsRectItem 的默认画法）。"""
        painter.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect()

        # ① 圆角矩形底 + 描边
        painter.setPen(self._edge_pen())
        painter.setBrush(QBrush(QColor(250, 250, 250)))
        painter.drawRoundedRect(r, self.NODE_RADIUS, self.NODE_RADIUS)

        # ② 左侧图标块（圆角、按状态取色）
        block = QRectF(r.left() + 1.5, r.top() + 1.5,
                       self.BLOCK_W, r.height() - 3.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self._block_color()))
        painter.drawRoundedRect(block, self.BLOCK_RADIUS, self.BLOCK_RADIUS)

        # ③ 图标（占位：代码自绘几何，白色）
        #   ★ M2c：未运行（idle）时**图标半透明** —— 让"没跑过"显得弱，不像"坏了"
        if self._state == "idle":
            painter.setOpacity(0.55)
        draw_icon(painter, icon_key_for(self.name),
                  block.adjusted(6.0, 7.0, -6.0, -7.0), QColor("#FFFFFF"))
        if self._state == "idle":
            painter.setOpacity(1.0)

        # ④ 图标块与文字区之间的竖分隔线
        sx = block.right() + 1.0
        painter.setPen(QPen(QColor(self.COLOR_SEPARATOR), 1))
        painter.drawLine(QPointF(sx, r.top() + 4.0), QPointF(sx, r.bottom() - 4.0))

        # ⑤ 节点名（左对齐、左内边距 8；序号本批不做、位置预留）
        painter.setPen(QPen(QColor(self.COLOR_TEXT)))
        painter.setFont(self._font)
        text_rect = QRectF(sx + 8.0, r.top(), r.right() - sx - 12.0, r.height())
        painter.drawText(text_rect, int(Qt.AlignVCenter | Qt.AlignLeft), str(self.name))

        # ⑥ 四个空心圆环（上/下 = 主端口；左/右本批只画）
        painter.setBrush(Qt.NoBrush)
        painter.setPen(self._ring_pen())
        for p in (self.in_port, self.out_port, self.left_port, self.right_port):
            painter.drawEllipse(p, self.RING_RADIUS, self.RING_RADIUS)

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


def node_topleft_for_center(name, center):
    """
    ★ 批次6 目标1-M4：把「**节点中心**落在 `center`」换算成 `NodeItem` 需要的**左上角**坐标。

    右键画布建节点时用 —— 用户 2026.10.17 拍板：**节点中心对齐鼠标点击处**（不是左上角对齐）。
    尺寸走 `NodeItem.size_for()`（唯一公式）；万一取不到就退化成"左上角对齐"，
    绝不让右键建节点因为这里报错而失败。
    """
    try:
        node_w, node_h = NodeItem.size_for(name)
    except Exception:                                  # pragma: no cover - 兜底，正常走不到
        return QPointF(float(center.x()), float(center.y()))
    return QPointF(float(center.x()) - node_w / 2.0, float(center.y()) - node_h / 2.0)


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

    # ★ 批次6 目标1-M4：右键画布空白处选中某个节点名 ⇒ 发这个信号（名字 / 场景坐标 = 节点中心）
    #   视图**不直接建节点**：建节点要碰 `main.py` 的 `add_flow_node`（撤销栈、脏标记、画布重算都在那儿）
    node_create_requested = Signal(str, QPointF)

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window # 主窗口
        self.setAcceptDrops(True) # 允许在画布内进行拖拽
        self.setDragMode(QGraphicsView.ScrollHandDrag) # 设置鼠标在空白处按住左键拖动时的行为
        # 注意：这个属性不能叫 self.scene——QGraphicsView 自己有个 scene() 方法，
        # 用同名属性会把它遮蔽掉，Python 侧就再也调不到 scene() 了
        self.flow_scene = QGraphicsScene() # 创建一个画布，专门用来存放方框（NodeItem）和连线（EdgeItem）。
        self.setScene(self.flow_scene) # 讲画布放到场景视图里面
        # ★ 批次6 目标1-M1：固定大画布（原点恒 (0,0)）+ 初始停在左上角
        self._content_positioned = False   # 这一页的视口是否已经"跟过内容"（导入方案时用）
        self._apply_canvas_rect(goto_topleft=True)

        self._start_node = None # 开始节点
        self._temp_line = None # 灰线

        # 监听场景中选中节点的变化，用来在main.ui中显示当前选中(单击)的节点
        self.flow_scene.selectionChanged.connect(self.on_selection_changed) # type:ignore

        # ★ 批次6 目标1-M4：右键画布建节点 —— 视图发信号，**主窗口用与"树双击"同一个入口**建节点
        #   （名字 / kind / 默认参数 / **撤销只记一条** 全部自动一致）。
        #   ★ 连接写在视图 `__init__` 里，是为了**不新增 MainWindow 方法**
        #     （门禁 `dsh_t5g2_api_check` 只允许白名单里的那几个新方法）。
        if main_window is not None and hasattr(main_window, "_create_node_from_name"):
            self.node_create_requested.connect(main_window._create_node_from_name)  # type: ignore


    def _apply_canvas_rect(self, goto_topleft=False):
        """
        把场景矩形固定成"固定大画布"（★ 批次6 目标1-M1）。

        · 原点**恒为 (0, 0)** ⇒ 无论怎么兜底增长，画面都不会跳；
        · 只有节点被拖到画布外时才**向右下**长大（叠加 CANVAS_MARGIN 余量）；
        · `goto_topleft=True` 时把滚动条拨到最小值（= 初始显示整图的**左上角**）。
        """
        scene = self.flow_scene
        try:
            content = scene.itemsBoundingRect()
        except RuntimeError:
            return                                  # 场景已销毁（关窗口 / 换页瞬间）
        self._canvas_rect_calls = getattr(self, "_canvas_rect_calls", 0) + 1   # 打点（第 3 次修改引入，判据已不需要；保留无害）
        # ★ 第 5 次修改（丙，2026.10.17）：**只有内容真的超出画布才兜底增长**。
        #   丙之后节点可以贴到画布最边（`x + 宽 == 4000`），若还写成
        #   `max(CANVAS_W, content.right() + CANVAS_MARGIN)` ⇒ 每次都会多扩 200
        #   ⇒ sceneRect 变成 4200×3200 ✗（用例 ⑤/⑯ 当场照红）⇒ 改成"超了才长"。
        right = float(CANVAS_W)
        bottom = float(CANVAS_H)
        if float(content.right()) > float(CANVAS_W):
            right = float(content.right()) + CANVAS_MARGIN
        if float(content.bottom()) > float(CANVAS_H):
            bottom = float(content.bottom()) + CANVAS_MARGIN
        scene.setSceneRect(QRectF(0, 0, right, bottom))
        if goto_topleft:
            h = self.horizontalScrollBar()
            v = self.verticalScrollBar()
            h.setValue(h.minimum())
            v.setValue(v.minimum())

    def follow_item(self, item):
        """★ 第 7 次修改（2026.10.17）：**限速平滑跟随**（第 6 次是 `ensureVisible` 一次滚到位 ⇒ 太快）。

        · 只**滚动视口**、**绝不改 `sceneRect`** ⇒ 滚动条范围始终是固定大画布（4000×3000）；
        · 算出"节点视口矩形与视口安全区"的差 ⇒ **每步最多滚 `FOLLOW_MAX_STEP` 像素**；
        · ★ `setValue` 一样会改滚动条 ⇒ Qt 同步重投 `mouseMoveEvent` ⇒ 调用方必须持 `_in_follow` 重入锁。
        """
        try:
            vp = self.viewport().rect()
            vr = self.mapFromScene(item.sceneBoundingRect()).boundingRect()
            dx = dy = 0
            if vr.left() < vp.left() + FOLLOW_MARGIN:
                dx = int(vr.left() - (vp.left() + FOLLOW_MARGIN))
            elif vr.right() > vp.right() - FOLLOW_MARGIN:
                dx = int(vr.right() - (vp.right() - FOLLOW_MARGIN))
            if vr.top() < vp.top() + FOLLOW_MARGIN:
                dy = int(vr.top() - (vp.top() + FOLLOW_MARGIN))
            elif vr.bottom() > vp.bottom() - FOLLOW_MARGIN:
                dy = int(vr.bottom() - (vp.bottom() - FOLLOW_MARGIN))
            # ★ 限速（第 7 次修改）：**按差距比例追**（不平滑就一记大跳；硬上限太死就追不上）
            #   · 每帧只追 FOLLOW_FACTOR 的差距 ⇒ 视觉上平滑；
            #   · 单帧不超过 FOLLOW_MAX_STEP、差距太小（< MIN）就不动 ⇒ 防瞬移 / 防抖。
            def _smooth(need):
                if not need:
                    return 0
                step = int(round(abs(need) * FOLLOW_FACTOR))
                step = max(FOLLOW_MIN_STEP, min(FOLLOW_MAX_STEP, step))
                return step if need > 0 else -step

            dx = _smooth(dx)
            dy = _smooth(dy)
            if dx:
                h = self.horizontalScrollBar()
                h.setValue(int(h.value() + dx))
            if dy:
                v = self.verticalScrollBar()
                v.setValue(int(v.value() + dy))
        except RuntimeError:
            pass                                   # item 已销毁（关窗口 / 撤销重建瞬间）

    def snap_item_visible(self, item):
        """★ 第 7 次修改：**松手时补一次"不限速"对齐**，把节点拉回视野里。

        限速跟随在快速拖动时允许节点短暂贴边/略微出界 ⇒ 松手用 `ensureVisible` 一次到位兜住。
        """
        try:
            self.ensureVisible(item, FOLLOW_MARGIN, FOLLOW_MARGIN)
        except RuntimeError:
            pass

    def goto_content_or_topleft(self):
        """
        视口定位（★ 批次6 目标1-M1）：场景里有节点 ⇒ **跟到内容**（第一个节点附近，用于
        导入项目 / 首次出现内容）；空页 ⇒ **左上角**。
        """
        first = None
        for item in self.flow_scene.items():
            if isinstance(item, NodeItem):
                first = item
                break
        if first is not None:
            self.centerOn(first)
        else:
            h = self.horizontalScrollBar()
            v = self.verticalScrollBar()
            h.setValue(h.minimum())
            v.setValue(v.minimum())
        self._apply_canvas_rect()

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
                    # ★ M2e：下方输出点的"拉线起点"只认**矩形之外**那半圈 ——
                    #   之前只判距离(30px)，而圆环有一半压在节点矩形里 ⇒ 想拖节点时在
                    #   节点下半部按下会误进"拉线"分支。现在：矩形内即便在感应圈内也不拉线，
                    #   落到下面"拖节点"那条分支；★ 上/左/右三个点的判定保持原样。
                    inside_rect = node.rect().contains(local_pos)
                    if (not inside_rect
                            and (local_pos - node.out_port).manhattanLength() < 30):
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
        # ★ 批次6 目标1-M1：拖动结束兜底重算一次画布矩形（正常情况什么都不变；只有被拖到
        #   画布外才会向右下长大，原点不动 ⇒ 其它节点的视口坐标不变、画面不跳）
        self._apply_canvas_rect()

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

    # ------------------------------------------------------------------ 右键画布建节点（M4）
    def contextMenuEvent(self, event):
        """
        右键菜单总入口（★ 批次6 目标1-M4，用户 2026.10.17 口径）。

        · 右键**节点 / 连线** ⇒ **老行为一字不改**：交给 `NodeItem` / `EdgeItem` 各自的
          `contextMenuEvent`（弹「删除节点」/「删除连线」）；
        · 右键**画布空白处** ⇒ 弹**两级「添加节点」菜单**（一级 = 树干，二级 = 节点名），
          选中后以**该点为中心**建一个节点（点哪建哪）。
        """
        item = self.itemAt(event.pos())
        if item is not None:
            # 命中节点 / 连线：完全走原有逻辑（不新建、不改菜单）
            super().contextMenuEvent(event)
            return

        scene_pos = self.mapToScene(event.pos())
        menu = self.build_create_menu(scene_pos)
        self._exec_menu(menu, event.globalPos())   # ESC / 点菜单外 ⇒ 返回 None ⇒ 什么都不建
        menu.deleteLater()

    def _exec_menu(self, menu, global_pos):
        """
        弹出菜单并返回用户点中的那一个动作（★ 单独一层，**方便无头用例替换掉**）。

        为什么要这一层：PySide2 的 `QMenu.exec_` 是 C++ 方法，**用例里无法用"="替换掉它**
        （实测赋值被忽略、仍会真的弹菜单并把 offscreen 环境卡死）⇒ 在我们自己的代码里留一个
        可替换的钩子，用例把它换成"记下菜单结构 + 返回 None"，就能验"右键空白会弹什么"而**不必真弹**。
        """
        return menu.exec_(global_pos)

    def build_create_menu(self, scene_pos=None):
        """
        构建**两级「添加节点」菜单**（★ 只构建、不弹 —— 无头用例直接断言它的结构，不必真弹菜单）。

        :param scene_pos: 建节点用的"**节点中心**"（场景坐标）；None ⇒ 用当前视口中心兜底。
        一级 = 树干（顺序与左侧树一致），二级 = 节点名；**不含测试夹具**（清单见 `core/node_catalog.py`）。
        """
        menu = QMenu(self)
        if scene_pos is None:
            center = self.mapToScene(self.viewport().rect().center())
        else:
            center = QPointF(scene_pos)
        pairs = node_catalog.groups()
        if not pairs:                                  # 兜底：别弹一个空菜单
            empty = QAction("（没有可用节点）", menu)
            empty.setEnabled(False)
            menu.addAction(empty)
            return menu
        for group, names in pairs:
            sub = menu.addMenu(group)
            for name in names:
                act = sub.addAction(name)
                act.triggered.connect(
                    lambda checked=False, n=name, p=QPointF(center):
                        self.node_create_requested.emit(n, p)
                )
        return menu

    def create_menu_structure(self, registered=None):
        """菜单结构快照 `[(树干, [节点名…]), …]`（给门禁用例核对"与左侧树逐项一致"用）"""
        return node_catalog.groups(registered)

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
        QTreeWidgetItem(root, ["直线识别"]) # 在root(即‘图像处理’)下面创建树枝，名字为直线识别
        QTreeWidgetItem(root, ["圆识别"]) # 在root(即‘图像处理’)下面创建树枝，名字为圆识别
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
            new_x, new_y = 80, 80 # 第一个方框的位置（★ 批次6 目标1-M1：20,20 → 80,80，不贴边）

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