from PySide2.QtCore import Qt, QPointF, Signal, QObject, QTimer, QRectF
from PySide2.QtGui import (QColor, QPen, QPainterPath, QBrush, QFont,
                           QFontMetricsF, QPainter, QPixmap, QPolygonF, QPainterPathStroker)

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

# ★ 批次6 目标1-M5（2026.10.18，用户口径）：
#   ① 网格 20px（**默认开启、不加开关**；大小以后看效果再调）
#   ② 网格吸附（**默认开、不加开关**）：坐标吸附到 20 的倍数
#   ③ 对齐辅助线 + 吸附（阈值 6px）
#   ④ 对中：右键画布空白菜单顶部「居中所选」「居中全部」
#   ★ 不做：一键对齐 / 整理流程（已移入想法，见《批次6 技术方案》§十三 第 24 条）
#
# ★★ 第 2 次修改（M5b，2026.10.18 用户实机报三条）：
#   ① "网格基本看不到" ⇒ 1px 灰点对比太弱 ⇒ 改成**一白一灰棋盘格**（照用户参考图）；
#   ② "每移动一下都吸附，一卡一卡" ⇒ 拖动中**不再吸附**，只显示对齐提示线；**松手时才吸附**；
#   ③ "对齐线不在中间，应与引出/接收线点同一高度" ⇒ 线改取**锚点坐标**：
#      旧实现用 `boundingRect().center()`，而 `boundingRect()` 是 `rect()` 外扩 8.5px（圆环 5 + 线宽 1.5 + 2）
#      ⇒ 线偏了 8.5px（实测出现 178.5 这种半像素就是奇数宽 + 外扩造成的）。
GRID_SIZE = 20                              # 网格间距（px）
GRID_COLOR_LIGHT = QColor(255, 255, 255)    # #FFFFFF 棋盘格亮格
GRID_COLOR_DARK = QColor(230, 230, 230)     # #E6E6E6 棋盘格暗格（用户参考图观感）
ALIGN_THRESHOLD = 30.0                       # 对齐吸附阈值（px）
ALIGN_LINE_COLOR = QColor(30, 136, 229)     # #1E88E5（与 M3 的橙色视口框区分）


# ★ 批次6 目标1-M6：连线（正交折线 + 转角圆角 + 入口方向箭头）相关常量
import math
EDGE_STUB = 5.0            # 从端口沿外法线伸出的一小段（px）
EDGE_SIDE_MARGIN = 40.0     # 反向连接时右侧绕行的横向余量（px）
EDGE_CORNER_RADIUS = 8.0    # 拐角圆角半径（px）
EDGE_ARROW_SIZE = 8.0       # 入口方向箭头大小（px）
EDGE_HIT_WIDTH = 12.0       # 连线命中区宽度（px，右键选中用）
EDGE_GAP_MIN = 50.0          # ★ M6c：反向绕行「走两节点之间」所需的最小空隙（px），不够就退回外侧
EDGE_GAP_NEAR = 40.0         # ★ M6e：反向连接的「近/远」阈值（px）—— 两节点水平缝隙 < 它 ⇒ 绕到目标背离源的外侧；>= 它 ⇒ 走两节点之间（用户可自行调整）


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
        # ★ 批次6 目标1-M7：多选整组拖动（其它选中节点跟着一起走）
        self._group_drag = []      # [(其它节点, 它的起始 pos)]
        self._group_anchor = None  # 本节点按下时的 pos（算 delta 用）

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

    def _anchor_center_scene(self):
        """本节点的**锚点中心**（场景坐标）= `pos + (上/下锚点 x, 左/右锚点 y)`。

        ★ M5b 第 ③ 条（用户："对齐吸附出现的线不是在中间的，应该与引出/接收线点在同一个
          高度上才对"）：算中心**不能用 `boundingRect()`** —— 它为了让圆环/描边不留残影
          `rect().adjusted(-8.5, -8.5, 8.5, 8.5)` 外扩了一圈，`boundingRect().center()`
          比真正中心**偏 8.5px**（实测线坐标出现 178.5 这种半像素）。
          ⇒ 直接取**锚点**：上/下锚点 x == 节点中线 x；左/右锚点 y == 节点中线 y。
        """
        p = self.pos()
        return QPointF(float(p.x()) + float(self.in_port.x()),
                       float(p.y()) + float(self.left_port.y()))

    def _align_targets(self):
        """★ M5b：找**对齐目标**（只算视口内、排除自己）；返回 `(锚点 x, 锚点 y)`（None = 没命中）。

        与旧实现 `_apply_snap` 的区别：**只算、不动** ——
        拖动中由 `_update_align_hints()` 拿它画提示线；松手时由 `_snap_on_release()` 拿它真正吸附
        （用户："现在的吸附是每移动一下都会吸附，一卡一卡的" ⇒ 拖动中必须不吸）。
        """
        view = self._flow_view()
        if view is None or not getattr(view, "snap_enabled", True):
            return None, None
        try:
            mine = self._anchor_center_scene()
            vrect = view.mapToScene(view.viewport().rect()).boundingRect()
            # ★ M7b（用户报「两块一起选着拖，中线一直亮」）：对齐候选**必须排除同组被拖的节点** ——
            #   它们本来就跟着一起动（还常常本来就对齐）⇒ 留在候选里会让提示线常亮、吸附目标也错。
            mate_ids = set()
            for mate, _start in (self._group_drag or []):
                try:
                    mate_ids.add(id(mate))
                except RuntimeError:
                    continue
            others = [it for it in view.flow_scene.items(vrect)
                      if isinstance(it, NodeItem) and it is not self
                      and id(it) not in mate_ids]
        except RuntimeError:
            return None, None
        thr = float(getattr(view, "align_threshold", ALIGN_THRESHOLD))
        best_x = None
        best_y = None
        for other in others:
            try:
                oc = other._anchor_center_scene()
            except RuntimeError:
                continue
            dx = abs(oc.x() - mine.x())
            dy = abs(oc.y() - mine.y())
            if dx < thr and (best_x is None or dx < abs(best_x - mine.x())):
                best_x = float(oc.x())
            if dy < thr and (best_y is None or dy < abs(best_y - mine.y())):
                best_y = float(oc.y())
        return best_x, best_y

    def _update_align_hints(self):
        """★ M5b：拖动中**只显示**对齐虚线（提示"松手会吸到这里"），**不移动节点** ⇒ 手感顺滑。"""
        view = self._flow_view()
        if view is None:
            return
        bx, by = self._align_targets()
        lines = []
        if bx is not None:
            lines.append(("v", bx))
        if by is not None:
            lines.append(("h", by))
        try:
            if list(view._align_lines) != lines:
                view._align_lines = lines
                view.viewport().update()
        except RuntimeError:
            pass

    def _snap_delta(self):
        """★ M7b：算出「松手吸附」要让**本节点**移动的位移（对齐优先、否则网格）；**不改位置**。

        抽出来是为了让「单个节点松手吸附」与「整组松手吸附」共用同一份判定 ——
        整组时把这份位移原样加给组里每个节点，**组内相对位置一分不变**。
        """
        view = self._flow_view()
        try:
            pos = self.pos()
        except RuntimeError:
            return None
        x, y = float(pos.x()), float(pos.y())
        bx = by = None
        g = 0.0
        if view is not None and getattr(view, "snap_enabled", True):
            bx, by = self._align_targets()
            try:
                g = float(getattr(view, "grid_size", GRID_SIZE) or 0)
            except (TypeError, ValueError):
                g = 0.0
        # 对齐优先（用户要"与引出/接收线点同高"），没命中才吸网格
        if bx is not None:
            x = float(bx) - float(self.in_port.x())        # 锚点 x == 一半宽 ⇒ 换回左上角
        elif g > 0:
            x = round(x / g) * g
        if by is not None:
            y = float(by) - float(self.left_port.y())
        elif g > 0:
            y = round(y / g) * g
        return QPointF(x - float(pos.x()), y - float(pos.y()))

    def _snap_on_release(self):
        """★ M5b：**松手时一次性吸附**（对齐优先、否则网格），仍走 `setPos` ⇒ 四边夹取照旧。

        ★ 必须在 `positionChanged.emit()` **之前**完成 —— 撤销栈记的"这次拖动的终点"就是
          吸附后的位置（否则 undo/redo 会停在没吸附的零碎坐标上）。
        """
        delta = self._snap_delta()
        view = self._flow_view()
        try:
            if delta is not None and (abs(delta.x()) > 1e-9 or abs(delta.y()) > 1e-9):
                self.setPos(QPointF(self.pos().x() + delta.x(),
                                    self.pos().y() + delta.y()))
            if view is not None and view._align_lines:
                view._align_lines = []
                view.viewport().update()
        except RuntimeError:
            pass

    def _snap_group_on_release(self):
        """★ M7b：**整组松手吸附**（用户："有中线但不吸附"）。

        做法：用**被拖节点**的吸附位移（`_snap_delta()`）作为整组的统一位移 ——
        被拖节点吸到位、其余节点同量平移 ⇒ **组内相对位置不变**；
        仍用 `_clamp_point` 预判压缩（谁先到画布边界就整组少走一点，不各自夹取变形）。
        """
        delta = self._snap_delta()
        if delta is None:
            return
        gdx, gdy = float(delta.x()), float(delta.y())
        if abs(gdx) < 1e-9 and abs(gdy) < 1e-9:
            self._clear_align_lines()
            return
        # 先按"每个节点都还能走这么多"压缩一次
        group = list(self._group_drag or [])
        for other, _start in group:
            try:
                cur = other.pos()
                fixed = other._clamp_point(QPointF(cur.x() + gdx, cur.y() + gdy))
                if abs(gdx) > 0.01 and abs(fixed.x() - cur.x()) < abs(gdx):
                    gdx = fixed.x() - cur.x()
                if abs(gdy) > 0.01 and abs(fixed.y() - cur.y()) < abs(gdy):
                    gdy = fixed.y() - cur.y()
            except RuntimeError:
                continue
        try:
            self.setPos(QPointF(self.pos().x() + gdx, self.pos().y() + gdy))
            for other, _start in group:
                try:
                    cur = other.pos()
                    other.setPos(QPointF(cur.x() + gdx, cur.y() + gdy))
                    other.positionChanged.emit()   # setPos 不发信号 ⇒ 显式发，撤销一起回位
                except RuntimeError:
                    continue
        except RuntimeError:
            pass
        self._clear_align_lines()

    def _clear_align_lines(self):
        """清掉对齐虚线并重绘（松手后提示线消失）。"""
        view = self._flow_view()
        try:
            if view is not None and view._align_lines:
                view._align_lines = []
                view.viewport().update()
        except RuntimeError:
            pass

    def mousePressEvent(self, event):
        """★ M7：多选时记下整组起点（配合 mouseMoveEvent 让它们一起移动）"""
        self._group_drag = []
        self._group_anchor = None
        try:
            if event.button() == Qt.LeftButton and self.isSelected():
                scene = self.scene()
                others = [it for it in (scene.selectedItems() if scene is not None else [])
                          if isinstance(it, NodeItem) and it is not self]
                if others:
                    self._group_anchor = QPointF(self.pos())
                    self._group_drag = [(n, QPointF(n.pos())) for n in others]
        except RuntimeError:
            self._group_drag = []
            self._group_anchor = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """实时拖拽响应"""
        super().mouseMoveEvent(event) # 先让底层把方块真正拖拽过去
        # ★ M5b（第 2 次修改）：拖动中**不吸附**（旧版每步都吸 ⇒ 一卡一卡），只**显示**对齐虚线作提示；
        #   真正的吸附留到松手（`mouseReleaseEvent` 里的 `_snap_on_release()`）。
        self._update_align_hints()
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
        # ★ M7：多选 ⇒ 整组一起移动。用「被拖节点实际允许的位移」压缩 delta，
        #   保证整组保持相对位置（谁先到边界就整组少走一点，不各自夹取变形）。
        if self._group_anchor is not None and self._group_drag:
            gdx = self.pos().x() - self._group_anchor.x()
            gdy = self.pos().y() - self._group_anchor.y()
            for other, start in self._group_drag:
                try:
                    probe = QPointF(start.x() + gdx, start.y() + gdy)
                    fixed = other._clamp_point(probe)
                    if abs(gdx) > 0.01 and abs(fixed.x() - start.x()) < abs(gdx):
                        gdx = fixed.x() - start.x()
                    if abs(gdy) > 0.01 and abs(fixed.y() - start.y()) < abs(gdy):
                        gdy = fixed.y() - start.y()
                except RuntimeError:
                    continue
            try:
                self.setPos(QPointF(self._group_anchor.x() + gdx,
                                    self._group_anchor.y() + gdy))
            except RuntimeError:
                pass
            for other, start in self._group_drag:
                try:
                    other.setPos(QPointF(start.x() + gdx, start.y() + gdy))
                    other.positionChanged.emit()   # setPos 不发信号 ⇒ 显式发，撤销才能一起回位
                except RuntimeError:
                    continue
        self.positionChanged.emit() # type:ignore

    def mouseReleaseEvent(self, event):
        """鼠标松开"""
        super().mouseReleaseEvent(event)  # 鼠标松开时更新最后一次位置
        self._clamp_into_canvas()         # ★ 丙：松手时再夹一次（保险）
        # ★ M5b：**松手时才吸附**（对齐优先、否则网格），顺带清掉对齐虚线。
        #   ★ 必须在下面的 `positionChanged.emit()` **之前** —— 撤销栈记的终点就是吸附后的位置。
        #   ★ M7b（用户报"有中线但不吸附"）：整组拖动**也要吸附** —— 用被拖节点的吸附位移
        #     整组平移 ⇒ 被拖节点吸到位、**组内相对位置不变**（旧版整组直接跳过吸附 ✗）。
        if self._group_drag:
            self._snap_group_on_release()
        else:
            self._snap_on_release()
        # ★ 第 7 次修改：限速跟随期间节点可能短暂贴边 ⇒ 松手时**不限速**拉回可见（同样持重入锁）
        if not self._in_follow:
            view = self._flow_view()
            if view is not None:
                self._in_follow = True
                try:
                    view.snap_item_visible(self)
                finally:
                    self._in_follow = False
        self._group_drag = []      # ★ M7：松手清组
        self._group_anchor = None
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


# ---------------------------------------------------------------- 连线的几何（★ M6b 抽成模块级）
def dedupe_points(pts):
    """去掉连续重复点。"""
    out = []
    for p in pts:
        if (not out) or (abs(out[-1].x() - p.x()) > 1e-6) or (abs(out[-1].y() - p.y()) > 1e-6):
            out.append(p)
    return out


def rounded_path_from_points(pts):
    """折线经过点 → 带圆角的路径（每个直角用 quadTo 换成 1/4 圆）。"""
    path = QPainterPath()
    if not pts:
        return path
    path.moveTo(pts[0])
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        v1 = QPointF(p1.x() - p0.x(), p1.y() - p0.y())
        v2 = QPointF(p2.x() - p1.x(), p2.y() - p1.y())
        l1 = math.hypot(v1.x(), v1.y())
        l2 = math.hypot(v2.x(), v2.y())
        if l1 < 1e-6 or l2 < 1e-6:
            continue
        rr = min(EDGE_CORNER_RADIUS, l1 / 2.0, l2 / 2.0)
        a = QPointF(p1.x() - v1.x() / l1 * rr, p1.y() - v1.y() / l1 * rr)
        b = QPointF(p1.x() + v2.x() / l2 * rr, p1.y() + v2.y() / l2 * rr)
        path.lineTo(a)
        path.quadTo(p1, b)
    path.lineTo(pts[-1])
    return path


def _reverse_detour_x(p0, p3, first_rect, last_rect):
    """★ M6e：反向绕行的横向位置。

    用户口径（2026.10.18，源=图片源、目标=灰度）：
      · 距离**远**（水平缝隙 gap >= EDGE_GAP_NEAR）⇒ **保持现状**：走两节点之间（缝隙中线）；
      · 距离**近**（gap < EDGE_GAP_NEAR）⇒ **绕到「目标背离源」的那一侧**：
          目标在右 ⇒ x = 目标右缘 + EDGE_SIDE_MARGIN；目标在左 ⇒ x = 目标左缘 - EDGE_SIDE_MARGIN。
    不变式：① 不穿源节点 ② 不穿目标节点 ③ 目标在左/在右两种布局镜像对称。
    """
    m = EDGE_SIDE_MARGIN
    if first_rect is not None and last_rect is not None:
        src_cx = first_rect.center().x()
        tgt_cx = last_rect.center().x()
        if tgt_cx > src_cx:                        # 目标在右
            gap = last_rect.left() - first_rect.right()
            if gap >= EDGE_GAP_NEAR:               # 远距 ⇒ 走两节点之间（现状）
                return (first_rect.right() + last_rect.left()) / 2.0
            x_far = last_rect.right() + m          # ★ 近距 ⇒ 目标背离源的右侧
            if x_far < first_rect.right() + EDGE_GAP_MIN:   # 保护：不穿源节点
                x_far = first_rect.right() + EDGE_GAP_MIN
            return x_far
        if tgt_cx < src_cx:                        # 目标在左（镜像）
            gap = first_rect.left() - last_rect.right()
            if gap >= EDGE_GAP_NEAR:
                return (last_rect.right() + first_rect.left()) / 2.0
            x_far = last_rect.left() - m           # ★ 近距 ⇒ 目标背离源的左侧
            if x_far > first_rect.left() - EDGE_GAP_MIN:    # 保护：不穿源节点
                x_far = first_rect.left() - EDGE_GAP_MIN
            return x_far
    # 没有矩形信息（预览时鼠标尚未命中节点）⇒ 旧规则：左右外侧取总长更短，相等走右
    if first_rect is not None and last_rect is not None:
        right_edge = max(first_rect.right(), last_rect.right())
        left_edge = min(first_rect.left(), last_rect.left())
    else:
        right_edge = max(p0.x(), p3.x())
        left_edge = min(p0.x(), p3.x())
    xs_right = right_edge + m
    xs_left = left_edge - m
    len_right = abs(xs_right - p0.x()) + abs(xs_right - p3.x())
    len_left = abs(p0.x() - xs_left) + abs(p3.x() - xs_left)
    return xs_right if len_right <= len_left else xs_left


def orthogonal_points(p1, p2, start_side="out", first_rect=None, last_rect=None):
    """p1 → p2 的正交折线经过点（全是横段/竖段）。

    ★ M6b 抽成模块级：`EdgeItem` 与**拖动预览**共用同一套走法（预览时 p2 = 鼠标位置）。
    ★ 反向绕行**选更近的一侧**：左/右各算一条候选、取总长度短的；两者相等时仍走**右侧**（保持旧行为）。
    """
    if start_side == "left":
        p0 = QPointF(p1.x() - EDGE_STUB, p1.y())
    elif start_side == "right":
        p0 = QPointF(p1.x() + EDGE_STUB, p1.y())
    else:
        p0 = QPointF(p1.x(), p1.y() + EDGE_STUB)
    p3 = QPointF(p2.x(), p2.y() - EDGE_STUB)
    pts = [QPointF(p1), p0]
    if abs(p0.x() - p3.x()) <= 1e-6:
        pts.append(p3)
    elif p0.y() < p3.y():
        mid_y = (p0.y() + p3.y()) / 2.0
        pts += [QPointF(p0.x(), mid_y), QPointF(p3.x(), mid_y), p3]
    else:
        # ★ M6c（乙）：绕行**优先走两节点之间的空隙**；没有空隙才退回"外侧取短"。
        #   绕行余量按「节点包围盒」算（不能只按端口 x，否则会从节点身上穿过）。
        xs = _reverse_detour_x(p0, p3, first_rect, last_rect)
        pts += [QPointF(p0.x(), p0.y() + EDGE_STUB),
                QPointF(xs, p0.y() + EDGE_STUB),
                QPointF(xs, p3.y() - EDGE_STUB),
                QPointF(p3.x(), p3.y() - EDGE_STUB),
                p3]
    pts.append(QPointF(p2))
    return dedupe_points(pts)


def build_edge_path(p1, p2, start_side="out", first_rect=None, last_rect=None):
    """返回 (QPainterPath, pts)。★ M6b：连好后的线与「拖动预览」共用。"""
    pts = orthogonal_points(p1, p2, start_side, first_rect, last_rect)
    return rounded_path_from_points(pts), pts


class EdgeItem(QGraphicsPathItem):
    """连线：★ M6 起为「正交折线 + 转角圆角 + 入口方向箭头」（原为贝塞尔曲线）。"""

    def __init__(self, start_node, end_node, start_port=None):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        # ★ 起线端口：out(下) / left / right —— ★ 存档不记端口（.vfproj 仍只存两端 uid），
        #   重启后统一下点起画；端口持久化留给 M8（端口对象化）。
        self.start_port = start_port or "out"
        self._arrow_polygon = QPolygonF()
        self._pts = []
        self.setPen(QPen(QColor("darkGray"), 2))
        self.update_path()

    def _start_point(self):
        node = self.start_node
        if self.start_port == "left":
            return node.mapToScene(node.left_port)
        if self.start_port == "right":
            return node.mapToScene(node.right_port)
        return node.get_output_pos()

    @staticmethod
    def _dedupe(pts):
        out = []
        for p in pts:
            if (not out) or (abs(out[-1].x() - p.x()) > 1e-6) or (abs(out[-1].y() - p.y()) > 1e-6):
                out.append(p)
        return out

    def _orthogonal_points(self):
        """返回正交折线的经过点（★ M6b：实际算法在模块级 `orthogonal_points`，与拖动预览共用）。"""
        try:
            r1 = self.start_node.sceneBoundingRect()
            r2 = self.end_node.sceneBoundingRect()
        except Exception:
            r1 = r2 = None
        return orthogonal_points(self._start_point(), self.end_node.get_input_pos(),
                                 self.start_port, r1, r2)

    @staticmethod
    def _rounded_path(pts):
        """★ M6b：实现移到模块级 `rounded_path_from_points`（预览线也用它）。"""
        return rounded_path_from_points(pts)
        path.moveTo(pts[0])
        for i in range(1, len(pts) - 1):
            p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
            v1 = QPointF(p1.x() - p0.x(), p1.y() - p0.y())
            v2 = QPointF(p2.x() - p1.x(), p2.y() - p1.y())
            l1 = math.hypot(v1.x(), v1.y())
            l2 = math.hypot(v2.x(), v2.y())
            if l1 < 1e-6 or l2 < 1e-6:
                continue
            rr = min(EDGE_CORNER_RADIUS, l1 / 2.0, l2 / 2.0)
            a = QPointF(p1.x() - v1.x() / l1 * rr, p1.y() - v1.y() / l1 * rr)
            b = QPointF(p1.x() + v2.x() / l2 * rr, p1.y() + v2.y() / l2 * rr)
            path.lineTo(a)
            path.quadTo(p1, b)
        path.lineTo(pts[-1])
        return path

    def _build_arrow(self, end):
        """入口方向箭头：末段固定自上而下 ⇒ 实心小三角，尖端贴在输入点上。"""
        s = EDGE_ARROW_SIZE
        return QPolygonF([QPointF(end.x(), end.y()),
                          QPointF(end.x() - s * 0.55, end.y() - s),
                          QPointF(end.x() + s * 0.55, end.y() - s)])

    def update_path(self):
        pts = self._orthogonal_points()
        self._pts = pts
        self._arrow_polygon = self._build_arrow(pts[-1])
        self.setPath(self._rounded_path(pts))

    def update_positions(self):
        self.update_path()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        if not self._arrow_polygon.isEmpty():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(self.pen().color()))
            painter.drawPolygon(self._arrow_polygon)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(EDGE_HIT_WIDTH)
        shape = stroker.createStroke(self.path())
        if not self._arrow_polygon.isEmpty():
            arrow = QPainterPath()
            arrow.addPolygon(self._arrow_polygon)
            shape = shape.united(arrow)
        return shape

    def contextMenuEvent(self, event):
        """右键点击连线时弹出菜单，实现删除连线"""
        menu = QMenu()
        delete_action = QAction("删除连线", menu)
        menu.addAction(delete_action)
        action = menu.exec_(event.screenPos())
        if action == delete_action:
            if self.scene() and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view, 'main_window'):
                    view.main_window.delete_edge(self)



class FlowchartView(QGraphicsView):
    """
    自定义流程图视图（支持拖放）
    继承画布QGraphicsView模块(用来放置方块的模块)
    """

    # ★ 批次6 目标1-M4：右键画布空白处选中某个节点名 ⇒ 发这个信号（名字 / 场景坐标 = 节点中心）
    #   视图**不直接建节点**：建节点要碰 `main.py` 的 `add_flow_node`（撤销栈、脏标记、画布重算都在那儿）
    node_create_requested = Signal(str, QPointF)

    # ★ 批次6 目标1-M7：缩放百分比变化（状态栏滑块 ↔ 视图双向同步）
    zoom_changed = Signal(int)

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window # 主窗口
        self.setAcceptDrops(True) # 允许在画布内进行拖拽
        # ★ 批次6 目标1-M7：左键改为「框选」（画布平移改到中键，见 mousePressEvent）
        self.setDragMode(QGraphicsView.RubberBandDrag) # 左键在空白处拖动 = 框选
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape) # 部分相交也算选中
        # 注意：这个属性不能叫 self.scene——QGraphicsView 自己有个 scene() 方法，
        # 用同名属性会把它遮蔽掉，Python 侧就再也调不到 scene() 了
        self.flow_scene = QGraphicsScene() # 创建一个画布，专门用来存放方框（NodeItem）和连线（EdgeItem）。
        self.setScene(self.flow_scene) # 讲画布放到场景视图里面
        # ★ 批次6 目标1-M1：固定大画布（原点恒 (0,0)）+ 初始停在左上角
        self._content_positioned = False   # 这一页的视口是否已经"跟过内容"（导入方案时用）
        # ★ 批次6 目标1-M7：缩放 + 中键平移
        self._zoom = 1.0       # 缩放比例（1.0 = 100%）
        self._in_pan = False   # 中键平移重入锁（改滚动条会回投鼠标事件，M1 踩过栈溢出）
        self._pan_start = None
        self._pan_scroll = (0, 0)
        self._apply_canvas_rect(goto_topleft=True)

        # ★ 批次6 目标1-M5：点阵网格 / 网格吸附 / 对齐辅助线（用户：默认全开、不加开关）
        self.grid_enabled = True                     # 是否画点阵网格
        self.grid_size = float(GRID_SIZE)            # 网格间距（px）
        self.snap_enabled = True                     # 网格吸附 + 对齐吸附的总开关（默认开）
        self.align_threshold = float(ALIGN_THRESHOLD)  # 对齐吸附阈值（px）
        self._align_lines = []                       # 当前要对齐的线：[("v", x) / ("h", y)]

        self._start_node = None # 开始节点
        self._start_port_type = "out"     # ★ M6：本次起线用的端口
        self.last_connect_hint = None   # ★ M6：最近一次连线提示（用例可断言）
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

    def showEvent(self, event):
        """
        ★ 批次6 目标1-M7c：页面**第一次真正显示**时，确保"固定大画布"已经生效。

        用户实测过一条**无头环境复现不出来**的现象：点「+」新建的页面里，
        滚动条滑块占满整条轨道（= `maximum() == minimum()`，没有可滚动范围）。
        方向是"新页在某个创建路径上没走到 `_apply_canvas_rect()`"，
        但真机与无头的差异无法在无头里重现 ⇒ 这里做**幂等自愈**（覆盖所有建页路径：
        「+」号 / 打开方案追加页 / 以后新增的入口）：
          · 只在"场景矩形明显不是固定大画布"（宽/高 < 1000，或原点 ≠ 0）时才补一次；
          · 健康状态下**一个字节都不动**（`_canvas_healed == 0`，判据钉住）。
        """
        super().showEvent(event)
        if getattr(self, "_in_show_heal", False):
            return                              # 防重入（自愈里可能触发重绘/布局）
        self._in_show_heal = True
        try:
            try:
                rect = self.flow_scene.sceneRect()
            except RuntimeError:
                return                          # 场景已销毁（关窗口 / 删页瞬间）
            too_small = float(rect.width()) < 1000.0 or float(rect.height()) < 1000.0
            bad_origin = abs(float(rect.x())) > 0.5 or abs(float(rect.y())) > 0.5
            if too_small or bad_origin:
                self._apply_canvas_rect()
                self._canvas_healed = int(getattr(self, "_canvas_healed", 0)) + 1
        finally:
            self._in_show_heal = False

    # ------------------------------------------------------------------ 缩放（M7）
    def _grid_step_scene(self):
        """★ M7：网格的**场景**步长 = 20px / 缩放比 ⇒ 屏幕上视觉恒 20px。"""
        try:
            z = float(self._zoom)
        except (TypeError, ValueError):
            z = 1.0
        if z <= 0.01:
            z = 0.01
        try:
            base = float(self.grid_size)
        except (TypeError, ValueError):
            base = 20.0
        return base / z

    def zoom_percent(self):
        """当前缩放（百分比整数）。"""
        try:
            return int(round(float(self._zoom) * 100.0))
        except (TypeError, ValueError):
            return 100

    def set_zoom(self, percent):
        """★ M7：设置缩放（20%~400%），以视口中心为锚点，并发出 zoom_changed。

        用 resetTransform() + scale() 控制（不是 scale() 累乘 —— 累乘会漂移）。
        """
        try:
            z = float(percent) / 100.0
        except (TypeError, ValueError):
            return
        z = max(0.2, min(4.0, z))
        if abs(z - float(self._zoom)) < 1e-6:
            return
        try:
            center = self.mapToScene(self.viewport().rect()).boundingRect().center()
        except RuntimeError:
            return
        self._zoom = z
        self.resetTransform()
        self.scale(z, z)
        try:
            self.centerOn(center)
        except RuntimeError:
            pass
        self._grid_brush_cache = None      # 纹理尺寸随缩放变化 ⇒ 重建
        try:
            self.viewport().update()
        except RuntimeError:
            pass
        try:
            self.zoom_changed.emit(int(round(z * 100.0)))
        except RuntimeError:
            pass

    def _grid_brush(self):
        """★ M5b：**一白一灰棋盘格**纹理（2×2 格 = 40×40 小图，做 `QBrush` 平铺）。

        为什么用纹理而不是逐格 `fillRect`：整块画布 4000×3000 / 20 = **200×150 = 3 万格**，
        逐格填会明显拖慢重绘；纹理平铺是**一次 `drawRect`**，实测不影响拖动帧率。
        小图做缓存（`grid_size` 变了才重建）。
        """
        try:
            g = int(round(self._grid_step_scene()))   # ★ M7：网格按缩放换算 ⇒ 屏幕上恒 20px
        except (TypeError, ValueError):
            return None
        if g <= 0:
            return None
        cached = getattr(self, "_grid_brush_cache", None)
        if cached is not None and getattr(self, "_grid_brush_size", None) == g:
            return cached
        pix = QPixmap(g * 2, g * 2)
        pix.fill(GRID_COLOR_LIGHT)
        p = QPainter(pix)
        try:
            p.fillRect(QRectF(0, 0, g, g), GRID_COLOR_DARK)                 # 左上 暗
            p.fillRect(QRectF(g, g, g, g), GRID_COLOR_DARK)                 # 右下 暗
        finally:
            p.end()
        brush = QBrush(pix)
        self._grid_brush_cache = brush
        self._grid_brush_size = g
        return brush

    def drawBackground(self, painter, rect):
        """★ M5b：**一白一灰棋盘格**背景（20px 格）—— 用户："点阵基本看不到，要图 2 那种棋盘格"。

        · 只画**背景**、不往场景加任何图元 ⇒ **不影响命中/连线/小地图/存档**；
        · 先把 `rect` 与"当前视口覆盖的场景矩形"求交 —— 否则 Qt 有时会传整块 4000×3000；
        · 平铺起点对齐到 **2×2 格的整数倍**（`setBrushOrigin`）⇒ 否则起点随 rect 变化会"爬格子"。
        """
        super().drawBackground(painter, rect)
        if not self.grid_enabled:
            return
        try:
            brush = self._grid_brush()
            if brush is None:
                return
            area = QRectF(rect).intersected(self.mapToScene(self.viewport().rect()).boundingRect())
            if area.isEmpty():
                return
            g = self._grid_step_scene()   # ★ M7：网格保持屏幕 20px
            step = g * 2.0
            left = int(area.left() // step) * step
            top = int(area.top() // step) * step
            painter.save()
            try:
                painter.setPen(Qt.NoPen)
                painter.setBrush(brush)
                painter.setBrushOrigin(QPointF(left, top))
                painter.drawRect(QRectF(left, top,
                                        float(area.right()) - left,
                                        float(area.bottom()) - top))
            finally:
                painter.restore()
        except (RuntimeError, ValueError):
            return

    def drawForeground(self, painter, rect):
        """★ 批次6 目标1-M5：**对齐辅助线**（拖动时临时虚线，蓝色）。

        画在**前景**而不是往场景里加 `QGraphicsLineItem` ⇒ 不污染场景、不进 `.vfproj` 存档、
        也不会被框选/命中到（松手即清空）。
        """
        super().drawForeground(painter, rect)
        if not self._align_lines:
            return
        try:
            painter.setPen(QPen(ALIGN_LINE_COLOR, 1, Qt.DashLine))
            for kind, value in self._align_lines:
                if kind == "v":
                    painter.drawLine(QPointF(value, rect.top()), QPointF(value, rect.bottom()))
                else:
                    painter.drawLine(QPointF(rect.left(), value), QPointF(rect.right(), value))
        except (RuntimeError, ValueError):
            return

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
        # ★ 批次6 目标1-M7：中键拖动画布（左键已让给框选）
        if event.button() == Qt.MiddleButton:
            self._pan_start = event.pos()
            self._pan_scroll = (self.horizontalScrollBar().value(),
                                self.verticalScrollBar().value())
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
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
                    # ★ M6：起线点 = 下(out) / 左 / 右 —— 三处都只认"圆环在矩形之外"那半圈
                    #   （M2e 的规则推广；矩形内按下仍然走"拖节点"，不误拉线；上边只接收、不能起线）
                    inside_rect = node.rect().contains(local_pos)
                    if not inside_rect:
                        for _port_attr, _port_kind in (("out_port", "out"),
                                                       ("left_port", "left"),
                                                       ("right_port", "right")):
                            if (local_pos - getattr(node, _port_attr)).manhattanLength() < 30:
                                clicked_node = node
                                clicked_port_type = _port_kind
                                break
                        if clicked_node is not None:
                            break

                    # 检查是否点击到红点（输入端口）
                    if (local_pos - node.in_port).manhattanLength() < 30:
                        clicked_node = node
                        clicked_port_type = 'in'
                        break

            if clicked_node is not None:
                # 开始连线
                if clicked_port_type in ('out', 'left', 'right'):
                    # 点到了蓝点，禁用抓握开始连线
                    self.setDragMode(QGraphicsView.NoDrag) # 设置模式，禁止拖到窗口NoDrag
                    self._start_connection(clicked_node, clicked_port_type) # ★ M6：带上起线端口
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
        # ★ M7：中键平移（带重入锁 —— 改滚动条会同步回投本事件）
        if self._in_pan:
            event.accept()
            return
        if self._pan_start is not None and (event.buttons() & Qt.MiddleButton):
            try:
                self._in_pan = True
                dx = event.pos().x() - self._pan_start.x()
                dy = event.pos().y() - self._pan_start.y()
                self.horizontalScrollBar().setValue(int(self._pan_scroll[0] - dx))
                self.verticalScrollBar().setValue(int(self._pan_scroll[1] - dy))
            finally:
                self._in_pan = False
            event.accept()
            return
        if self._start_node is not None:
            # ★ M6b：预览线也用正交折线（与连好后的线共用 build_edge_path）
            pos = self.mapToScene(event.pos())
            self._update_temp_line(pos)
            return
        # 非连线状态时使用，交给父类处理，实现拖到方框或者拖到背景画面
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """判断终点是否在红点上，如果在红点上则完成连线，如果不在则曲线这次连线"""
        # ★ M7：中键平移结束（复原光标）
        if event.button() == Qt.MiddleButton and self._pan_start is not None:
            self._pan_start = None
            self._pan_scroll = (0, 0)
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
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

            # ★ M6：落在左/右点上 ⇒ 明确拒绝（左/右点本批"只能引出、不能接收"）
            _hint = None
            if hasattr(self.main_window, 'flow_nodes'):
                for _node in self.main_window.flow_nodes:
                    if not isinstance(_node, NodeItem):
                        continue
                    _lp = _node.mapFromScene(scene_pos)
                    if ((_lp - _node.left_port).manhattanLength() < 30
                            or (_lp - _node.right_port).manhattanLength() < 30):
                        _hint = "该点暂不支持接收连线（左/右点本批只能引出）"
                        break
            if _hint:
                self.last_connect_hint = _hint
                try:
                    self.main_window._append_log_hint(_hint)
                except Exception:
                    pass

            # 没有落在红点上，连线失败，取消虚线
            self._cancel_connection()
            event.accept()
            return

        super().mouseReleaseEvent(event)
        # ★ 批次6 目标1-M1：拖动结束兜底重算一次画布矩形（正常情况什么都不变；只有被拖到
        #   画布外才会向右下长大，原点不动 ⇒ 其它节点的视口坐标不变、画面不跳）
        self._apply_canvas_rect()

    def _start_connection(self, node, port_type="out"):
        """负责记录连线的起点（含起线端口），并在屏幕上生成一条初始的灰色虚线。"""
        self._cancel_connection()
        self._start_node = node
        self._start_port_type = port_type
        if port_type == "left":
            start_pos = node.mapToScene(node.left_port)
        elif port_type == "right":
            start_pos = node.mapToScene(node.right_port)
        else:
            start_pos = node.get_output_pos()
        # ★ M6b：预览线改用**路径**对象（与连好后的线同一套正交折线走法）
        self._temp_start_pos = start_pos
        self._temp_line = QGraphicsPathItem()
        self._temp_line.setPen(QPen(Qt.gray, 2, Qt.DashLine))
        self.flow_scene.addItem(self._temp_line)
        self._update_temp_line(start_pos)


    def _update_temp_line(self, p2):
        """★ M6b：拖动中的预览线 = 正交折线（与连好后的线同一个 `build_edge_path`）。"""
        item = getattr(self, "_temp_line", None)
        start = getattr(self, "_temp_start_pos", None)
        if item is None or start is None:
            return
        r1 = None
        try:
            if self._start_node is not None:
                r1 = self._start_node.sceneBoundingRect()
        except Exception:
            r1 = None
        # ★ M6d：拖动中**命中目标节点**时，预览直接按"该节点的输入点 + 该节点矩形"算
        #   ⇒ 预览与落定后的线**逐点一致**（用户 2026.10.18：「鼠标拉线时还是原本的远路程，
        #     但是接线后就是短路程了」）。
        p2_eff = QPointF(p2)
        r2 = None
        try:
            hover = self._hovered_end_node(QPointF(p2))
            if hover is not None:
                p2_eff = hover.get_input_pos()
                r2 = hover.sceneBoundingRect()
        except Exception:
            hover = None
            r2 = None
        path, _pts = build_edge_path(start, p2_eff,
                                     getattr(self, "_start_port_type", "out"), r1, r2)
        item.setPath(path)

    def _hovered_end_node(self, scene_pos):
        """★ M6d：拖动中的"可作为终点的节点"（排除源节点自身）。"""
        try:
            nodes = getattr(self.main_window, "flow_nodes", None) or []
        except Exception:
            return None
        for node in nodes:
            if not isinstance(node, NodeItem) or node is self._start_node:
                continue
            try:
                local = node.mapFromScene(scene_pos)
            except Exception:
                continue
            if (local - node.in_port).manhattanLength() < 30 or node.rect().contains(local):
                return node
        return None

    def _try_finish_edge(self, start_node, end_node, event=None):
        """将虚线变成实线，并把整个系统状态清理干净"""
        if start_node is not None and start_node != end_node:
            self.main_window.add_edge(start_node, end_node,
                                      getattr(self, "_start_port_type", "out"))
        self._cancel_connection()
        if event:
            event.accept()


    def _cancel_connection(self):
        """负责把当前的连线状态彻底清空，恢复到“没有拉线”的初始状态"""
        if self._temp_line:
            # 去除灰色虚线
            self.flow_scene.removeItem(self._temp_line)
            self._temp_line = None
        self._temp_start_pos = None
        self._start_node = None
        self.setDragMode(QGraphicsView.RubberBandDrag) # ★ M7：连线结束恢复「左键框选」

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
        # ★ 批次6 目标1-M5：**工具项放菜单最顶部**（用户 2026.10.18：节点类型一多，“添加节点”会很长，
        #   工具项若放下面会被挤到底部、越来越难找 ⇒ 固定在顶部，永远看得见）。
        act_center_sel = QAction("居中所选", menu)
        act_center_sel.triggered.connect(self._center_selected)
        menu.addAction(act_center_sel)
        act_center_all = QAction("居中全部", menu)
        act_center_all.triggered.connect(self._center_all)
        menu.addAction(act_center_all)
        menu.addSeparator()
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

    # ------------------------------------------------------------------ 对中（M5）
    def _center_selected(self):
        """★ 批次6 目标1-M5「居中所选」：把**当前选中的节点**居中到视口。

        ★ 放在 `FlowchartView` 而不是 `MainWindow`：不用新增 MainWindow 方法
        （门禁 `dsh_t5g2_api_check` 只允许白名单里的那几个），也就不碰 main.py。
        """
        try:
            items = [it for it in self.flow_scene.selectedItems() if isinstance(it, NodeItem)]
        except RuntimeError:
            return
        if not items:
            return
        try:
            self.centerOn(items[0].sceneBoundingRect().center())
        except RuntimeError:
            pass

    def _center_all(self):
        """★ 批次6 目标1-M5「居中全部」：把**整页内容**（包围盒中心）居中到视口；空页 ⇒ 回左上角。"""
        try:
            rect = self.flow_scene.itemsBoundingRect()
        except RuntimeError:
            return
        if rect.isNull() or rect.isEmpty():
            h = self.horizontalScrollBar()
            v = self.verticalScrollBar()
            h.setValue(h.minimum())
            v.setValue(v.minimum())
            return
        try:
            self.centerOn(rect.center())
        except RuntimeError:
            pass

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