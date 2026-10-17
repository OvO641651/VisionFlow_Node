# -*- coding: utf-8 -*-
"""
批次6 目标1-M3：画布**右下角小地图**（方案 §4.3）。

用户 2026.10.17 拍板的口径：
  · 位置 = **右下角**（距边 8px；原方案写"左下角"，用户已改掉）；
  · 尺寸 = **180×135**（与固定大画布 4000×3000 同为 4:3）；
  · 外观 = 浅灰底 `#F5F5F5` + 圆角 4 + 1px 边框 `#C8C8C8`；
  · 只画 **节点小方块**（颜色 = 运行状态：绿/灰/红，最小 2×2）+ **橙色视口框 `#F0A030`**；
    **不画连线、不画图标与文字**（缩小后看不清，节点多时也拖慢重绘）；
  · 交互 = **可拖视口框**导航（框内按下拖动 ⇒ 主画布跟着移到对应区域）；
    **框外点击不响应（甲）**；滚轮 `event.ignore()` 交给上层（与在画布上一致）；
  · 实例 = **全局一个**，换页时 `bind_view(新页的 view)`（内部会断开旧信号）。

职责边界：
  只读主视图的状态（场景矩形 / 视口矩形 / 节点状态），**唯一会反向影响主视图的动作**
  就是拖动视口框时的 `centerOn()`。不碰节点、参数、执行逻辑。
"""
from PySide2.QtCore import QEvent, QPointF, QRectF, Qt
from PySide2.QtGui import QColor, QPainter, QPen
from PySide2.QtWidgets import QWidget

# ---- 尺寸与配色（改这里就能调外观）----
MAP_W = 180                       # 小地图宽（px）
MAP_H = 135                       # 小地图高（px）—— 180:135 = 4000:3000，等比
MAP_MARGIN = 8                    # 距画布边缘的留白
MAP_RADIUS = 4                    # 圆角半径
COLOR_BG = "#F5F5F5"              # 浅灰底
COLOR_BG_EDGE = "#C8C8C8"         # 1px 边框
COLOR_VIEW_RECT = "#F0A030"       # 视口框（橙）：与"选中蓝"区分，一眼认出
VIEW_RECT_WIDTH = 1.5             # 视口框线宽
NODE_MIN_PX = 2.0                 # 节点方块最小边长（太小会看不见）
NODE_BLOCK_ALPHA = 200            # 节点方块不透明度（0~255）


class FlowMiniMap(QWidget):
    """画布右下角的小地图：显示节点全局分布 + 当前视口框，可拖框导航。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = None            # 当前绑定的 FlowchartView
        self._dragging = False       # 是否正在拖视口框
        self._grab_scene = QPointF() # 按下瞬间：鼠标对应的**场景坐标**
        self._grab_center = QPointF()# 按下瞬间：主视图**视口中心**（场景坐标）
        self._conns = []             # [(signal, slot)]：换页时要逐个断开
        self._old_viewport = None    # 上一个 viewport（要摘掉事件过滤器）
        self.setFixedSize(MAP_W, MAP_H)
        self.setCursor(Qt.ArrowCursor)
        self.setToolTip("小地图：按住橙色的视口框拖动，可以把画布移到对应区域")
        self.setMouseTracking(False)

    # ------------------------------------------------------------------
    # 绑定 / 解绑（换页时调用）
    # ------------------------------------------------------------------
    def bind_view(self, view):
        """绑定到某一页的 FlowchartView；★ 先断开旧的一整套连接，避免旧页残留。

        换页时由 `FlowPageManager._bind_minimap()` 调用（全局只有一个小地图）。
        """
        self._unbind()
        self._view = view
        if view is None:
            self.hide()
            return
        try:
            vp = view.viewport()
            self.setParent(vp)                     # 跟着画布视口走 ⇒ 定位永远是"画布右下角"
            self._old_viewport = vp
            vp.installEventFilter(self)            # 视口尺寸变化 ⇒ 重新摆位
            h = view.horizontalScrollBar()
            v = view.verticalScrollBar()
            h.valueChanged.connect(self._on_view_changed)
            v.valueChanged.connect(self._on_view_changed)
            self._conns = [(h.valueChanged, self._on_view_changed),
                           (v.valueChanged, self._on_view_changed)]
            scene = view.scene()
            if scene is not None:
                scene.changed.connect(self._on_view_changed)   # 节点增删/移动 ⇒ 重画
                self._conns.append((scene.changed, self._on_view_changed))
        except RuntimeError:
            self._view = None
            self.hide()
            return
        self.update_geometry()
        self.show()
        self.raise_()
        self.update()

    def _unbind(self):
        """断开旧 view 的所有连接 + 摘掉事件过滤器 + 复位拖动状态"""
        self._dragging = False
        try:
            self.setCursor(Qt.ArrowCursor)
        except RuntimeError:
            pass
        for sig, slot in self._conns:
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._conns = []
        if self._old_viewport is not None:
            try:
                self._old_viewport.removeEventFilter(self)
            except RuntimeError:
                pass
        self._old_viewport = None

    # ------------------------------------------------------------------
    # 摆位：始终贴着父容器的**右下角**（距边 MAP_MARGIN）
    # ------------------------------------------------------------------
    def update_geometry(self):
        """按父容器（画布视口）当前的 rect 摆到右下角；容器太小时贴左上角（不出界）。"""
        parent = self.parentWidget()
        if parent is None:
            return
        try:
            pr = parent.rect()
        except RuntimeError:
            return
        x = max(0, pr.width() - MAP_W - MAP_MARGIN)
        y = max(0, pr.height() - MAP_H - MAP_MARGIN)
        self.move(x, y)
        self.setFixedSize(MAP_W, MAP_H)

    def eventFilter(self, watched, event):
        """视口尺寸变了 ⇒ 重新贴右下角（不依赖 FlowchartView 改代码）"""
        if event.type() == QEvent.Resize:
            self.update_geometry()
        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------
    # 坐标换算（等比 + 居中；场景矩形长大时也不会拉伸变形）
    # ------------------------------------------------------------------
    def scene_rect(self):
        """小地图覆盖的场景矩形（= 主场景的 sceneRect；固定大画布时就是 4000×3000）"""
        if self._view is None:
            return QRectF(0, 0, 1, 1)
        try:
            scene = self._view.scene()
            if scene is None:
                return QRectF(0, 0, 1, 1)
            sr = scene.sceneRect()
            if sr.width() <= 0 or sr.height() <= 0:
                return QRectF(0, 0, 1, 1)
            return QRectF(sr)
        except RuntimeError:
            return QRectF(0, 0, 1, 1)

    def _transform(self):
        """(比例, x 偏移, y 偏移)：场景 → 小地图的等比映射参数"""
        sr = self.scene_rect()
        s = min(float(MAP_W) / sr.width(), float(MAP_H) / sr.height())
        ox = (MAP_W - sr.width() * s) / 2.0
        oy = (MAP_H - sr.height() * s) / 2.0
        return s, ox, oy

    def scene_to_map(self, pt):
        """场景坐标 → 小地图坐标"""
        sr = self.scene_rect()
        s, ox, oy = self._transform()
        return QPointF(ox + (float(pt.x()) - sr.left()) * s,
                       oy + (float(pt.y()) - sr.top()) * s)

    def map_to_scene(self, pos):
        """小地图坐标 → 场景坐标"""
        sr = self.scene_rect()
        s, ox, oy = self._transform()
        return QPointF(sr.left() + (float(pos.x()) - ox) / s,
                       sr.top() + (float(pos.y()) - oy) / s)

    def viewport_scene_rect(self):
        """主视图**当前可见**的那片场景（★ 从主视图反算，不用鼠标位置推算）"""
        if self._view is None:
            return QRectF()
        try:
            vp = self._view.viewport()
            return QRectF(self._view.mapToScene(vp.rect()).boundingRect())
        except RuntimeError:
            return QRectF()

    def view_rect_in_map(self):
        """视口框在小地图坐标系里的矩形（判据与绘制都用它）"""
        vr = self.viewport_scene_rect()
        if vr.isNull():
            return QRectF()
        return QRectF(self.scene_to_map(vr.topLeft()), self.scene_to_map(vr.bottomRight()))

    # ------------------------------------------------------------------
    # 节点方块（只读：颜色跟运行状态）
    # ------------------------------------------------------------------
    def node_blocks(self):
        """返回 [(场景矩形 QRectF, 颜色字符串)]：当前页所有节点的缩略方块"""
        out = []
        if self._view is None:
            return out
        try:
            scene = self._view.scene()
            if scene is None:
                return out
            from widgets.FlowChart import NodeItem       # 延迟导入：避免模块级循环依赖
            for item in scene.items():
                if not isinstance(item, NodeItem):
                    continue
                try:
                    srect = QRectF(item.mapToScene(item.rect()).boundingRect())
                except RuntimeError:
                    continue                                  # 节点已销毁
                state = "normal"
                getter = getattr(item, "state", None)
                if callable(getter):
                    try:
                        state = str(getter() or "normal")
                    except RuntimeError:
                        state = "normal"
                color = {"error": NodeItem.COLOR_BLOCK_ERROR,
                         "idle": NodeItem.COLOR_BLOCK_IDLE}.get(state, NodeItem.COLOR_BLOCK_NORMAL)
                out.append((srect, color))
        except RuntimeError:
            return out
        return out

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            # 1、底 + 圆角边框
            p.setPen(QPen(QColor(COLOR_BG_EDGE), 1))
            p.setBrush(QColor(COLOR_BG))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                              MAP_RADIUS, MAP_RADIUS)
            if self._view is None:
                return
            # 2、节点方块（状态色；太小的补到 2×2，保证看得见）
            for srect, color in self.node_blocks():
                tl = self.scene_to_map(srect.topLeft())
                br = self.scene_to_map(srect.bottomRight())
                w = max(NODE_MIN_PX, br.x() - tl.x())
                h = max(NODE_MIN_PX, br.y() - tl.y())
                c = QColor(color)
                c.setAlpha(NODE_BLOCK_ALPHA)
                p.setPen(Qt.NoPen)
                p.setBrush(c)
                p.drawRect(QRectF(tl.x(), tl.y(), w, h))
            # 3、视口框（橙色）—— ★ 位置来自主视图真实滚动位置
            vr = self.view_rect_in_map()
            if not vr.isNull():
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(COLOR_VIEW_RECT), VIEW_RECT_WIDTH))
                p.drawRect(vr)
        finally:
            p.end()

    # ------------------------------------------------------------------
    # 鼠标：框内拖框 · ★ 框外点击 = 视口直接跳过去并接着能拖（乙，M3b）
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if self._view is None or event.button() != Qt.LeftButton:
            event.accept()
            return
        vr = self.view_rect_in_map()
        clicked = QPointF(event.pos())
        if vr.isNull() or not vr.contains(clicked):
            # ★ M3b（乙）：框外点击 ⇒ 视口中心跳到点击处，并且**按下就能接着拖**。
            #   注意：centerOn 到画布边缘会被 sceneRect 夹住 ⇒ _grab_center 必须取
            #   **夹取之后**的真实中心（用 viewport_scene_rect().center()），否则拖第一下会跳。
            target = self.map_to_scene(clicked)
            try:
                self._view.centerOn(target)
            except RuntimeError:
                event.accept()
                return
            self.update()
            self._dragging = True
            self._grab_scene = target
            self._grab_center = self.viewport_scene_rect().center()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        self._dragging = True
        self._grab_scene = self.map_to_scene(event.pos())
        self._grab_center = self.viewport_scene_rect().center()
        self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging or self._view is None:
            event.accept()
            return
        # ★ 用"位移量"而不是"把框中心对到鼠标" ⇒ 抓哪儿就是哪儿，按下瞬间不会跳
        scene_now = self.map_to_scene(event.pos())
        new_center = QPointF(self._grab_center.x() + (scene_now.x() - self._grab_scene.x()),
                             self._grab_center.y() + (scene_now.y() - self._grab_scene.y()))
        try:
            self._view.centerOn(new_center)     # 主画布跟着走（到画布边界由滚动条自然夹住）
        except RuntimeError:
            self._dragging = False
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)
            self.update()
        event.accept()

    def wheelEvent(self, event):
        """滚轮交给上层（在画布上滚和在小地图上滚行为一致），小地图自身不做任何事。"""
        event.ignore()

    # ------------------------------------------------------------------
    def _on_view_changed(self, *args):
        """主视图滚动 / 场景变化 ⇒ 重画（update 由 Qt 合并，天然节流）"""
        try:
            self.update()
        except RuntimeError:
            pass
