# -*- coding: utf-8 -*-
"""批次6 目标1-M5b 判据：**棋盘格网格 + 拖动中不吸附 + 松手吸附 + 对齐线按锚点**（方案 §4.5）。

用户 2026.10.18 实机报三条（M5b 修的就是这三条）：
  · ① "网格颜色存在问题，基本看不到网格" ⇒ 改成**一白一灰棋盘格**；
  · ② "现在的吸附是每移动一下都会吸附，移动起来一卡一卡" ⇒ **拖动中不吸附，松手才吸附**；
  · ③ "对齐吸附出现的线不是在中间的，应该与引出/接收线点在同一个高度上" ⇒ 线取**锚点坐标**
    （旧实现用 `boundingRect().center()`，而 boundingRect 外扩了 8.5px ⇒ 偏位）。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import Qt, QPoint, QPointF, QEvent, QRectF   # noqa: E402
from PySide2.QtGui import QImage, QPainter, QColor               # noqa: E402
from PySide2.QtWidgets import (QApplication, QGraphicsSceneMouseEvent)  # noqa: E402

app = QApplication([])
import main as m                                                  # noqa: E402
import time                                                       # noqa: E402
from widgets.FlowChart import (NodeItem, GRID_SIZE, GRID_COLOR_LIGHT,  # noqa: E402
                               GRID_COLOR_DARK, ALIGN_THRESHOLD,
                               CANVAS_W, CANVAS_H)

_check_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _check_pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def pump(n=4):
    for _ in range(n):
        app.processEvents()


def new_window():
    win = m.MainWindow()
    win.main_window.resize(1280, 800)
    win.main_window.show()
    pump()
    return win


def view_of(win):
    return win.flow_page_mgr.current_page["view"]


def fresh():
    """新窗口 + 清空场景（每个场景独立 ⇒ 互不污染）。"""
    win = new_window()
    view = view_of(win)
    view.flow_scene.clear()
    pump()
    return win, view


def make_move_event(node, target, start):
    """手工造 QGraphicsSceneMouseEvent（真实拖动入口）。"""
    ev = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMouseMove)
    ev.setScenePos(target)
    ev.setLastScenePos(start)
    ev.setPos(node.mapFromScene(target))
    ev.setLastPos(node.mapFromScene(start))
    ev.setButtonDownScenePos(Qt.LeftButton, start)
    ev.setButtonDownPos(Qt.LeftButton, node.mapFromScene(start))
    ev.setScreenPos(QPoint(0, 0))
    ev.setLastScreenPos(QPoint(0, 0))
    ev.setButtons(Qt.LeftButton)
    ev.setButton(Qt.LeftButton)
    ev.setModifiers(Qt.NoModifier)
    ev.setAccepted(True)
    return ev


def drag_to(node, target):
    """拖到 target（**不松手**）⇒ 返回最终位置。"""
    start = node.pos()
    node.mouseMoveEvent(make_move_event(node, target, start))
    return node.pos()


def press(node):
    """模拟一次**真实的按下** —— Qt 的 `ItemIsMovable` 用"按下时记住的位置"当基准，
    不发 press、只在 move 里改 `buttonDownScenePos` 是**不生效**的（实测：第二次 move 会
    按第一次的基准算，节点只挪一小步 ⇒ 假失败）。"""
    ev = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMousePress)
    ev.setScenePos(node.pos())
    ev.setLastScenePos(node.pos())
    ev.setButtonDownScenePos(Qt.LeftButton, node.pos())
    ev.setButtonDownPos(Qt.LeftButton, node.mapFromScene(node.pos()))
    ev.setScreenPos(QPoint(0, 0))
    ev.setLastScreenPos(QPoint(0, 0))
    ev.setButtons(Qt.LeftButton)
    ev.setButton(Qt.LeftButton)
    ev.setModifiers(Qt.NoModifier)
    ev.setAccepted(True)
    node.mousePressEvent(ev)


def one_drag(node, target):
    """一次**完整的拖到 target**（按下 → 移动，不松手）⇒ 返回最终位置。"""
    press(node)
    return drag_to(node, target)


def release(node):
    """松手（触发 `_snap_on_release()` + 清对齐线）。"""
    ev = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMouseRelease)
    ev.setScenePos(node.pos())
    ev.setLastScenePos(node.pos())
    ev.setButtonDownScenePos(Qt.LeftButton, node.pos())
    ev.setScreenPos(QPoint(0, 0))
    ev.setButton(Qt.LeftButton)
    ev.setAccepted(True)
    try:
        node.mouseReleaseEvent(ev)
    except RuntimeError:
        pass


def board_pixels(view, w=240, h=180):
    """把 drawBackground 画进 QImage，返回 (暗格像素数, 总像素数)。"""
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    try:
        view.drawBackground(p, QRectF(0, 0, w, h))
    finally:
        p.end()
    target = GRID_COLOR_DARK.rgb() & 0x00FFFFFF
    n = 0
    for y in range(h):
        for x in range(w):
            if (img.pixel(x, y) & 0x00FFFFFF) == target:
                n += 1
    return n, w * h


def anchor_x(node):
    return float(node.pos().x()) + float(node.in_port.x())


def anchor_y(node):
    return float(node.pos().y()) + float(node.left_port.y())


# ================================================================ ① 棋盘格网格
print("\n--- ① 棋盘格网格（20px，白/浅灰交替）---")
win, view = fresh()
check("★ grid_size == 20（用户口径）", float(view.grid_size) == 20.0, view.grid_size)
check("★ grid_enabled 默认 True（不加开关）", view.grid_enabled is True, view.grid_enabled)
check("★ snap_enabled 默认 True（不加开关）", view.snap_enabled is True, view.snap_enabled)
check("★ 两色不同（白/浅灰）", GRID_COLOR_LIGHT != GRID_COLOR_DARK,
      (GRID_COLOR_LIGHT.name(), GRID_COLOR_DARK.name()))
view.grid_enabled = False
n_off, total = board_pixels(view)
view.grid_enabled = True
n_on, _ = board_pixels(view)
check("★ 关网格 ⇒ 暗格像素为 0", n_off == 0, n_off)
ratio = float(n_on) / float(total)
check("★ 开网格 ⇒ 暗格像素约占一半（棋盘格，不是点阵）", 0.40 <= ratio <= 0.60, ratio)
print("      暗格像素 = %d / %d（%.1f%%）" % (n_on, total, ratio * 100.0))
check("★ 网格是背景、不影响命中（空白处 itemAt is None）",
      view.itemAt(QPoint(30, 30)) is None, view.itemAt(QPoint(30, 30)))

# ================================================================ ② 拖动中不吸附
print("\n--- ② 拖动中**不吸附**（拖到非 20 倍数的位置，坐标应精确等于鼠标位置）---")
win, view = fresh()
a = win.add_flow_node("灰度", QPointF(600, 600))
pump()
bad = []
for k, (wx, wy) in enumerate([(613, 617), (627, 631), (651, 643), (663, 659)]):
    a.setPos(QPointF(600, 600))                  # 每轮归位（避开夹取/边界干扰）
    got = one_drag(a, QPointF(wx, wy))
    if abs(got.x() - wx) > 0.01 or abs(got.y() - wy) > 0.01:
        bad.append((k, wx, wy, got.x(), got.y()))
check("★ 拖动中坐标 == 鼠标位置（4 组非 20 倍数都精确落位，不被拉向网格）", not bad, bad)
# 松手后才吸附
release(a)
pos = a.pos()
check("★ 松手后吸附到 20 的倍数", int(round(pos.x())) % 20 == 0 and int(round(pos.y())) % 20 == 0,
      (pos.x(), pos.y()))

# ================================================================ ③ 松手吸附到网格
print("\n--- ③ 松手吸附：(237,253) ⇒ (240,260) ---")
win, view = fresh()
a = win.add_flow_node("灰度", QPointF(200, 200))
pump()
one_drag(a, QPointF(237, 253))
mid = a.pos()
check("★ 拖动中不吸附（pos == (237,253)）", (mid.x(), mid.y()) == (237.0, 253.0), (mid.x(), mid.y()))
release(a)
end = a.pos()
check("★ 松手后 pos == (240,260)", (end.x(), end.y()) == (240.0, 260.0), (end.x(), end.y()))

# ================================================================ ④ 对齐：线按锚点 + 松手才吸
print("\n--- ④ 对齐吸附（阈值 = 顶部常量，用户可自行调大调小）+ 线坐标 = 锚点坐标 ---")
# ★ 2026.10.18：原来钉死 `== 6` 属"把可调参数当协议值"⇒ 用户实机把 6 调成 30 就照红。
#   这里只守"是个正数"；真正的契约由下面两条行为判据保证：差 3px 会提示/吸附、差 40px 不吸附。
check("★ ALIGN_THRESHOLD > 0（手感参数，不钉死具体值）", float(ALIGN_THRESHOLD) > 0, ALIGN_THRESHOLD)
win, view = fresh()
na = win.add_flow_node("灰度", QPointF(100, 100))
nb = win.add_flow_node("取反", QPointF(400, 400))
pump()
view.grid_size = 0                       # 关网格吸附，单独看"对齐"
ax = anchor_x(na)
target_x = ax - float(nb.in_port.x()) + 3.0     # 让 nb 的锚点 x 与 na 差 3px
one_drag(nb, QPointF(target_x, 380))
mid = nb.pos()
check("★ 拖动中**不**被对齐吸走（pos 仍是鼠标位置）",
      abs(anchor_x(nb) - (ax + 3.0)) < 0.01, (anchor_x(nb), ax + 3.0))
lines = list(view._align_lines)
vlines = [v for k, v in lines if k == "v"]
check("★ 拖动中显示竖直提示线", len(vlines) >= 1, lines)
check("★ 提示线坐标 == A 的**锚点** x（<0.5px，旧实现偏 8.5px）",
      bool(vlines) and abs(vlines[0] - ax) < 0.5, (vlines[:1], ax))
release(nb)
check("★ 松手后 B 的锚点 x == A 的锚点 x（<0.5px）", abs(anchor_x(nb) - ax) < 0.5,
      (anchor_x(nb), ax))
check("★ 松手后对齐线清空", list(view._align_lines) == [], list(view._align_lines))
check("★ 吸附后的线位置 = 两节点锚点（用锚点算，不用 boundingRect 中心）",
      abs(float(nb.in_port.x()) + float(nb.pos().x()) - (float(na.in_port.x()) + float(na.pos().x()))) < 0.5,
      (anchor_x(nb), ax))
# 差 40px ⇒ 不吸
nb.setPos(QPointF(400, 400))
far_tx = ax - float(nb.in_port.x()) + 40.0
one_drag(nb, QPointF(far_tx, 380))
release(nb)
check("★ 差 40px ⇒ 不吸附（锚点差仍≈40）", abs(abs(anchor_x(nb) - ax) - 40.0) < 1.0,
      abs(anchor_x(nb) - ax))

# ================================================================ ⑤ 只算视口内 + 排除自己
print("\n--- ⑤ 对齐只算视口内节点 / 排除自己 ---")
win, view = fresh()
near_node = win.add_flow_node("灰度", QPointF(200, 200))
far_node = win.add_flow_node("取反", QPointF(3500, 2500))
pump()
vrect = view.mapToScene(view.viewport().rect()).boundingRect()
in_view = [it for it in view.flow_scene.items(vrect) if isinstance(it, NodeItem)]
check("★ 视口内的节点在候选里", near_node in in_view, len(in_view))
check("★ 视口外的远节点不在候选里（性能与语义都靠这条）", far_node not in in_view, len(in_view))
bx, by = near_node._align_targets()
check("★ 排除自己（单节点对齐目标为空）", bx is None and by is None, (bx, by))

# ================================================================ ⑥ 与四边夹取共存
print("\n--- ⑥ 吸附 + 四边夹取（拖到画布外）---")
win, view = fresh()
a = win.add_flow_node("灰度", QPointF(200, 200))
pump()
one_drag(a, QPointF(CANVAS_W + 199, CANVAS_H + 199))
release(a)
end = a.pos()
right = end.x() + a.rect().width()
bottom = end.y() + a.rect().height()
check("★ 右缘不超过画布宽", right <= float(CANVAS_W) + 0.01, right)
check("★ 下缘不超过画布高", bottom <= float(CANVAS_H) + 0.01, bottom)
check("★ 仍被夹在画布内（x,y ≥ 0）", end.x() >= 0 and end.y() >= 0, (end.x(), end.y()))
# ★ 边界处：**夹取优先于吸附**（贴边时坐标未必是 20 的倍数，这是预期 —— ③ 已单独验过非边界情形）
check("★ 贴边时夹取生效（下缘正好贴住画布底边）",
      abs((end.y() + float(a.boundingRect().height())) - float(CANVAS_H)) < 0.5,
      (end.y(), float(a.boundingRect().height()), float(CANVAS_H)))

# ================================================================ ⑦ 撤销顺序
print("\n--- ⑦ 松手吸附 = 那次拖动的撤销终点（栈深只 +1）---")
win, view = fresh()
a = win.add_flow_node("灰度", QPointF(300, 300))
pump()
old = (a.pos().x(), a.pos().y())
depth0 = win._undo_stack.depth
one_drag(a, QPointF(357, 353))
release(a)
win._commit_pending_moves()
pump()
snapped = (a.pos().x(), a.pos().y())
check("★ 拖动+松手只 +1 条撤销命令", win._undo_stack.depth == depth0 + 1,
      (depth0, win._undo_stack.depth))
check("★ 吸附后的坐标确实变了（357,353 → 20 的倍数）", snapped != old and snapped == (360.0, 360.0),
      (old, snapped))
win.undo()
pump()
back = (a.pos().x(), a.pos().y())
check("★ undo ⇒ 回到拖动前位置", abs(back[0] - old[0]) < 0.01 and abs(back[1] - old[1]) < 0.01,
      (back, old))
win.redo()
pump()
again = (a.pos().x(), a.pos().y())
check("★ redo ⇒ 回到**吸附后**的位置（不是零碎坐标）",
      abs(again[0] - snapped[0]) < 0.01 and abs(again[1] - snapped[1]) < 0.01, (again, snapped))

# ================================================================ ⑧ 对中
print("\n--- ⑧ 对中（居中所选 / 居中全部）+ 菜单顶部 ---")
win, view = fresh()
a = win.add_flow_node("灰度", QPointF(1200, 900))
pump()
for it in view.flow_scene.selectedItems():
    it.setSelected(False)
a.setSelected(True)
pump()
view._center_selected()
pump()
vc = view.mapToScene(view.viewport().rect()).boundingRect().center()
nc = a.sceneBoundingRect().center()
check("★ 居中所选：视口中心 ≈ 节点中心（≤2px）",
      abs(vc.x() - nc.x()) <= 2 and abs(vc.y() - nc.y()) <= 2, (vc.x(), vc.y(), nc.x(), nc.y()))
view._center_all()
pump()
vc2 = view.mapToScene(view.viewport().rect()).boundingRect().center()
cc = view.flow_scene.itemsBoundingRect().center()
check("★ 居中全部：视口中心 ≈ 内容中心（≤2px）",
      abs(vc2.x() - cc.x()) <= 2 and abs(vc2.y() - cc.y()) <= 2, (vc2.x(), vc2.y(), cc.x(), cc.y()))
menu = view.build_create_menu()
texts = [a2.text() for a2 in menu.actions()]
check("★ 右键空白菜单**顶部**是「居中所选」「居中全部」",
      texts[:2] == ["居中所选", "居中全部"], texts[:3])
check("★ 工具项之后才是「添加节点」子菜单",
      any(t in ("采集", "处理", "检测识别", "颜色处理") for t in texts[2:]), texts)

# ================================================================ ⑨ 性能
print("\n--- ⑨ 性能：120 节点拖动 + 棋盘格重绘 ---")
win, view = fresh()
nodes = []
for i in range(120):
    nodes.append(win.add_flow_node("灰度", QPointF(100 + (i % 12) * 160, 100 + (i // 12) * 90)))
pump()
t0 = time.time()
for k in range(30):
    one_drag(nodes[0], QPointF(300 + k, 200 + k))
per = (time.time() - t0) / 30.0 * 1000.0
check("★ 120 节点单次拖动（提示线 + 夹取 + 跟随）< 25ms", per < 25.0, per)
print("      实测 = %.2f ms/步" % per)

print("\n=== 结果：通过 %d 项，失败 %d 项 ===" % (_check_pass[0], len(_fails)))
if _fails:
    for t in _fails:
        print("  FAILED: " + t)
    raise SystemExit(1)
