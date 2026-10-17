# -*- coding: utf-8 -*-
"""批次6 目标1-M1 判据：**固定大画布**（画布滚动条 bug 修复）。

用户报的现象（2026.10.17）："节点向右移动到界限后会出现滚动条，但是其他节点会留在最左边
（开始创建时是放在中间的）" ⇒ 根因 = `FlowChart` 从不设 `sceneRect`，矩形跟着内容自动长，
内容超出视口后视图锚定左上角 ⇒ 其余节点整体跳（实测跳 194px）。

修法（方案 Z）：`FlowchartView` 固定大画布 4000×3000、**原点恒 (0,0)**、初始停左上角、
节点被拖到画布外时只**向右下**兜底增长（原点不动 ⇒ 永不跳）；起始点 (20,20) → (80,80)。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import QPointF, QEvent, Qt             # noqa: E402
from PySide2.QtWidgets import QApplication              # noqa: E402

app = QApplication([])
import main as m                                        # noqa: E402
from widgets.FlowChart import CANVAS_W, CANVAS_H, CANVAS_MARGIN   # noqa: E402

_check_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _check_pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def new_window(w=1280, h=800):
    win = m.MainWindow()
    win.main_window.resize(w, h)
    win.main_window.show()
    for _ in range(6):
        app.processEvents()
    return win


def bars(view):
    h = view.horizontalScrollBar()
    v = view.verticalScrollBar()
    r = view.flow_scene.sceneRect()
    return (r, h.maximum(), h.value(), h.minimum(), v.maximum(), v.value(), v.minimum())


print("=== 批次6 目标1-M1：固定大画布 ===")
w = new_window()
view = w.flow_page_mgr.current_page["view"]
r, hmax, hval, hmin, vmax, vval, vmin = bars(view)

check("① 新页初始就有滚动条（横向 max>0 且纵向 max>0）",
      hmax > 0 and vmax > 0, (hmax, vmax))
check("② 初始停在左上角（两条滚动条 value == minimum）",
      hval == hmin and vval == vmin, (hval, hmin, vval, vmin))
check("③ 场景矩形 = 固定大画布，且**原点恒 (0,0)**",
      (r.x(), r.y()) == (0.0, 0.0) and r.width() >= CANVAS_W and r.height() >= CANVAS_H,
      (r.x(), r.y(), r.width(), r.height()))

nodes = []
for i, nm in enumerate(("取反", "灰度", "二值化")):
    n = w.add_flow_node(nm, QPointF(80 + i * 30, 80 + i * 200))
    if n is None:
        n = w.flow_nodes[-1]
    nodes.append(n)
for _ in range(4):
    app.processEvents()
before = [view.mapFromScene(n.pos()) for n in nodes]
r0, hmax0, hval0 = bars(view)[0], bars(view)[1], bars(view)[2]

# ③/④ 把一个节点移到远处（= 模拟拖动）：画布内 ⇒ 矩形不变；画布外 ⇒ 只向右下长大
nodes[1].setPos(QPointF(CANVAS_W - 1200, CANVAS_H - 1200))
view._apply_canvas_rect()                 # = 真实路径里 mouseReleaseEvent 末尾会做的事
for _ in range(4):
    app.processEvents()
mid = [view.mapFromScene(n.pos()) for n in nodes]
r1 = view.flow_scene.sceneRect()
check("④ 节点在画布内移动 ⇒ 场景矩形**一动不动**、其它节点视口坐标不变（≤1px）",
      (r1.x(), r1.y(), r1.width(), r1.height()) == (r0.x(), r0.y(), r0.width(), r0.height())
      and (mid[0] - before[0]).manhattanLength() <= 1
      and (mid[2] - before[2]).manhattanLength() <= 1,
      ((r1.x(), r1.y(), r1.width(), r1.height()), (r0.x(), r0.y(), r0.width(), r0.height()),
       (mid[0] - before[0]).manhattanLength(), (mid[2] - before[2]).manhattanLength()))

nodes[1].setPos(QPointF(CANVAS_W + 800, CANVAS_H + 600))    # = 想把它挪到画布外（★ 丙：会被夹回）
view._apply_canvas_rect()
for _ in range(4):
    app.processEvents()
after = [view.mapFromScene(n.pos()) for n in nodes]
r2 = view.flow_scene.sceneRect()
_p2 = nodes[1].pos()
check("⑤ [回归钉·丙] 想把节点挪到画布外 ⇒ **被夹回画布内**、场景矩形**一点不变**、其它节点不跳（≤1px）",
      (r2.x(), r2.y()) == (0.0, 0.0)
      and abs(r2.width() - CANVAS_W) < 0.5 and abs(r2.height() - CANVAS_H) < 0.5
      and _p2.x() + nodes[1].rect().width() <= CANVAS_W + 0.5
      and _p2.y() + nodes[1].rect().height() <= CANVAS_H + 0.5
      and (after[0] - before[0]).manhattanLength() <= 1
      and (after[2] - before[2]).manhattanLength() <= 1,
      ((r2.x(), r2.y(), r2.width(), r2.height()), (_p2.x(), _p2.y()),
       (after[0] - before[0]).manhattanLength(), (after[2] - before[2]).manhattanLength()))

# ⑤ 起始点 (80,80)：双击树新建第一颗 / 第二颗
w2 = new_window()
leaf = None
for i in range(w2.tree.topLevelItemCount()):
    top = w2.tree.topLevelItem(i)
    if top.childCount():
        leaf = top.child(0)
        break
if leaf is None:
    check("⑥ 双击树新建：第一颗节点起点 = (80, 80)", False, "树里没有可双击的叶子")
else:
    w2.tree.setCurrentItem(leaf)
    w2._on_tree_double_click(leaf, 0)
    # ★ main.py 的 _on_tree_double_click 是 QTimer.singleShot(1, ...) **延迟**建节点的
    #   ⇒ 无头下必须"等够时间 + 多轮 processEvents"，否则定时器还没到就断言（实测会时好时坏）
    import time
    for _ in range(20):
        time.sleep(0.01)
        app.processEvents()
    n1 = w2.flow_nodes[0] if w2.flow_nodes else None
    check("⑥ 起始点：双击树新建的第一颗节点 = (80, 80)（不贴边；「同列 y+180」的公式未动）",
          n1 is not None and (n1.pos().x(), n1.pos().y()) == (80.0, 80.0),
          (None if n1 is None else (n1.pos().x(), n1.pos().y())))

# ⑥/⑦ 换页（新页）+ 新页里出现内容（= 导入方案那条路径）⇒ ① 仍成立 + 视口跟到内容
w3 = new_window()
mgr = w3.flow_page_mgr
mgr.add_page()
for _ in range(4):
    app.processEvents()
view3 = mgr.current_page["view"]
r3, hmax3, hval3, hmin3, vmax3, vval3, vmin3 = bars(view3)
check("⑦ 新建页（换页）后 ①② 仍成立（滚动条在 + 左上角 + 原点 (0,0)）",
      hmax3 > 0 and vmax3 > 0 and hval3 == hmin3 and vval3 == vmin3
      and (r3.x(), r3.y()) == (0.0, 0.0),
      (hmax3, vmax3, hval3, vmin3, r3.x(), r3.y()))
view3._content_positioned = False          # = 刚导入的方案：还没"跟过内容"
n3 = w3.add_flow_node("取反", QPointF(2600, 1800))
if n3 is None and w3.flow_nodes:
    n3 = w3.flow_nodes[-1]
for _ in range(4):
    app.processEvents()
vis = view3.viewport().rect()
p3 = view3.mapFromScene(n3.pos()) if n3 is not None else None
check("⑧ 新页首次出现内容（= 导入方案路径）⇒ 视口**跟到内容**（节点落在视口内），原点仍 (0,0)",
      p3 is not None and vis.contains(p3) and (view3.flow_scene.sceneRect().x(),
                                               view3.flow_scene.sceneRect().y()) == (0.0, 0.0),
      (None if p3 is None else (p3.x(), p3.y()), vis.width(), vis.height(),
       view3.flow_scene.sceneRect().x(), view3.flow_scene.sceneRect().y()))

# ⑨ 窗口 resize 不跳
w4 = new_window()
view4 = w4.flow_page_mgr.current_page["view"]
n4 = w4.add_flow_node("取反", QPointF(900, 900))
if n4 is None and w4.flow_nodes:
    n4 = w4.flow_nodes[-1]
for _ in range(4):
    app.processEvents()
p_before = view4.mapFromScene(n4.pos())
r_before = view4.flow_scene.sceneRect()
w4.main_window.resize(1000, 700)
for _ in range(6):
    app.processEvents()
p_after = view4.mapFromScene(n4.pos())
r_after = view4.flow_scene.sceneRect()
check("⑨ 窗口 resize 后「场景 ↔ 视口」映射不跳（节点视口坐标不变 ≤1px）、原点仍 (0,0)",
      (p_after - p_before).manhattanLength() <= 1
      and (r_after.x(), r_after.y()) == (0.0, 0.0)
      and r_after.width() >= r_before.width(),
      ((p_before.x(), p_before.y()), (p_after.x(), p_after.y()),
       (p_after - p_before).manhattanLength()))

# ======================================================================
# ⑩ ~ ⑫ 批次6 目标1-M1 修正（2026.10.17 用户实机报）：**左边 / 上边要有边界**
#   根因：`_apply_canvas_rect()` 用 `base.united(content.adjusted(...))` ⇒ 内容一旦带负坐标，
#         左/上边界也被扩出去 ⇒ 原点不再是 (0,0)、滚动条范围右移
#         （修前实测：pos=(-500,-500) ⇒ sceneRect.x=-501、h.minimum=-501）
# ======================================================================
w5 = new_window()
view5 = w5.flow_page_mgr.current_page["view"]
scene5 = view5.flow_scene
h5 = view5.horizontalScrollBar()
n5 = w5.add_flow_node("取反", QPointF(600, 600))
if n5 is None and w5.flow_nodes:
    n5 = w5.flow_nodes[-1]
for _ in range(4):
    app.processEvents()

# ⑩ 甲：往左 / 上拖到极限 ⇒ 位置被夹在 ≥ (0, 0)
n5.setPos(QPointF(-500, -500))
for _ in range(4):
    app.processEvents()
check("⑩ [回归钉] 节点往左/上拖到极限 ⇒ 位置被夹在 ≥ (0,0)（左边/上边真的成了边界）",
      n5.pos().x() >= 0 and n5.pos().y() >= 0, (n5.pos().x(), n5.pos().y()))

# ⑪ 乙：把场景矩形人为推到负原点（模拟旧数据 / 极端情形）⇒ 重算后原点必须回到 (0,0)
scene5.setSceneRect(scene5.sceneRect().adjusted(-500, -500, 0, 0))
view5._apply_canvas_rect()
for _ in range(4):
    app.processEvents()
r5 = scene5.sceneRect()
check("⑪ [回归钉] `_apply_canvas_rect()` 后原点恒 (0,0)、横向滚动条 minimum() == 0（不再左扩）",
      (r5.x(), r5.y()) == (0.0, 0.0) and h5.minimum() == 0,
      ((r5.x(), r5.y()), h5.minimum()))

# ⑫ 拖动节点前后，横向滚动条 value 不变（用户看到的就是「滚动条向右移动」）
v_before = h5.value()
n5.setPos(QPointF(1200, 900))
for _ in range(4):
    app.processEvents()
n5.setPos(QPointF(200, 200))
for _ in range(4):
    app.processEvents()
check("⑫ [回归钉] 拖动节点前后横向滚动条 value 不变（不会再出现「区域向右增大」的错觉）",
      abs(h5.value() - v_before) <= 1, (v_before, h5.value()))

# ======================================================================
# ⑬ ~ ⑯ 批次6 目标1-M1 **第 5 次修改（丙，2026.10.17）**：**四个边界全固定**
#     用户："现在我的想法是撤销乙的修改，按照丙固定所有边界的方式修改"
#     （乙 = 拖动中实时扩 sceneRect + 视口跟随 ⇒ 矩形随拖动**无限增长**，不是他要的；
#       他要的是"滚动条跟随到画布中间就**停止增大**" ⇒ 干脆四边全固定，节点整体留在画布内）
#     实测（temp\dsh_t6_m1_probe5.py，同一支对备份 / 工程各跑一次）：
#       修前（乙/1.1.4）：拖到极限 pos=(4900,3700)、右缘 5040 > 4000 ✗、sceneRect 长到 5241×3951（变 6 次）、
#                         h.max 3531→4772、v.max 2453→3404、"整个在画布内" 15/20 步；
#       修后（丙/1.1.5）：pos=(3860,2950)、右缘 4000、下缘 3000 ✓、sceneRect **恒 4000×3000（变 0 次）**、
#                         h.max/v.max **不变**、"整个在画布内" **20/20** 步 ✓
# ======================================================================
w6 = new_window()
view6 = w6.flow_page_mgr.current_page["view"]
scene6 = view6.flow_scene
n6 = w6.add_flow_node("取反", QPointF(100, 100))
if n6 is None and w6.flow_nodes:
    n6 = w6.flow_nodes[-1]
for _ in range(4):
    app.processEvents()

h6, v6 = view6.horizontalScrollBar(), view6.verticalScrollBar()
rect_base = scene6.sceneRect()
hmax_base, vmax_base = h6.maximum(), v6.maximum()
nw6 = float(n6.rect().width())
nh6 = float(n6.rect().height())


def _drag_to(target):
    """走**真实拖动入口** `NodeItem.mouseMoveEvent` 把节点拖到 target（**不松手**）。

    ★ `ItemIsMovable` 的位移按 `scenePos - buttonDownScenePos` 算 ⇒ 必须给 buttonDown。
    """
    from PySide2.QtWidgets import QGraphicsSceneMouseEvent
    from PySide2.QtCore import QEvent as _QE, QPoint
    if not hasattr(_drag_to, "start"):
        _drag_to.start = n6.pos()
    last = n6.pos()
    ev = QGraphicsSceneMouseEvent(_QE.GraphicsSceneMouseMove)
    ev.setScenePos(target)
    ev.setLastScenePos(last)
    ev.setPos(n6.mapFromScene(target))
    ev.setLastPos(n6.mapFromScene(last))
    ev.setButtonDownScenePos(Qt.LeftButton, _drag_to.start)
    ev.setButtonDownPos(Qt.LeftButton, n6.mapFromScene(_drag_to.start))
    ev.setScreenPos(QPoint(0, 0))
    ev.setLastScreenPos(QPoint(0, 0))
    ev.setButtons(Qt.LeftButton)
    ev.setButton(Qt.LeftButton)
    ev.setModifiers(Qt.NoModifier)
    ev.setAccepted(True)
    n6.mouseMoveEvent(ev)


# 分 20 步一路往右下拖到"远超画布"的位置（★ 全程不松手）
STEPS = 20
rects_during, hmax_during, vmax_during = [], [], []
tx, ty = CANVAS_W + 900.0, CANVAS_H + 700.0
for _i in range(1, STEPS + 1):
    _drag_to(QPointF(100.0 + (tx - 100.0) * _i / STEPS,
                     100.0 + (ty - 100.0) * _i / STEPS))
    app.processEvents()
    rects_during.append(scene6.sceneRect())
    hmax_during.append(h6.maximum())
    vmax_during.append(v6.maximum())

p6 = n6.pos()
check("⑬ [回归钉·丙] 往右/下拖到极限 ⇒ 节点**整个**留在画布内（x+宽 ≤ 4000、y+高 ≤ 3000）",
      p6.x() + nw6 <= CANVAS_W + 0.5 and p6.y() + nh6 <= CANVAS_H + 0.5
      and p6.x() >= -0.5 and p6.y() >= -0.5,
      (p6.x(), p6.y(), nw6, nh6))

n_bad_rect = sum(1 for r in rects_during if r != rect_base)
check("⑭ [回归钉·丙] 拖动**全程** sceneRect **不变** = 固定大画布（乙的「无限增长」已撤回）",
      n_bad_rect == 0,
      (rect_base, rects_during[-1] if rects_during else None, n_bad_rect))

n_bad_max = (sum(1 for a in hmax_during if abs(a - hmax_base) > 0)
             + sum(1 for b in vmax_during if abs(b - vmax_base) > 0))
check("⑮ [回归钉·丙] 拖动**全程**横向 / 纵向滚动条 `maximum()` **不变**（= 用户要的「停止增大」）",
      n_bad_max == 0,
      ((hmax_base, hmax_during[-1] if hmax_during else None),
       (vmax_base, vmax_during[-1] if vmax_during else None), n_bad_max))

# 松手（走视图的 mouseReleaseEvent，末尾会重算一次矩形）
try:
    from PySide2.QtGui import QMouseEvent
    _rel = QMouseEvent(QEvent.MouseButtonRelease, QPointF(10, 10),
                       Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    view6.mouseReleaseEvent(_rel)
except Exception:
    view6._apply_canvas_rect()
for _ in range(4):
    app.processEvents()
check("⑯ [回归钉·丙] 松手后 sceneRect 与节点位置都**不跳变**",
      scene6.sceneRect() == rect_base and n6.pos() == p6,
      (scene6.sceneRect() == rect_base, n6.pos() == p6))


# ======================================================================
# ⑰ ~ ⑳ 第 6 次修改（甲 = 丙 + 只复活乙的 B「视图跟随」）
#   · 只**滚视图**、**不改 sceneRect** ⇒ 矩形 / 滚动条范围不变（丙的判据继续成立）
#   · ★ `ensureVisible` 会**同步重投** mouseMoveEvent ⇒ 必须有 `_in_follow` 重入锁
#     （第 3 次修改就是没锁 ⇒ Fatal Python error: Cannot recover from stack overflow）
# ======================================================================
from PySide2.QtCore import QPoint                          # noqa: E402
from PySide2.QtWidgets import QGraphicsSceneMouseEvent as _GSME   # noqa: E402

view7, scene7, n7 = view6, scene6, n6
n7.setPos(QPointF(200.0, 200.0))          # 先放回画布内部（⑬ 把它拖到过极限）
view7.centerOn(QPointF(270.0, 225.0))
for _ in range(4):
    app.processEvents()

_rect7 = scene7.sceneRect()
_hmax7 = view7.horizontalScrollBar().maximum()
_vmax7 = view7.verticalScrollBar().maximum()

_calls = []
_real_follow = view7.follow_item


def _spy_follow(item, _r=_real_follow):
    _calls.append(1)
    return _r(item)


view7.follow_item = _spy_follow


def _ev7(kind, scene_pos, down_scene, button=Qt.NoButton, buttons=Qt.NoButton):
    ev = _GSME(kind)
    ev.setScenePos(scene_pos)
    ev.setPos(n7.mapFromScene(scene_pos))
    ev.setLastScenePos(scene_pos)
    ev.setLastPos(n7.mapFromScene(scene_pos))
    ev.setButtonDownScenePos(Qt.LeftButton, down_scene)
    ev.setButtonDownPos(Qt.LeftButton, n7.mapFromScene(down_scene))
    sp = view7.mapFromScene(scene_pos)
    ev.setScreenPos(QPoint(int(sp.x()), int(sp.y())))
    ev.setButton(button)
    ev.setButtons(buttons)
    return ev


start7 = n7.pos() + QPointF(n7.boundingRect().width() / 2.0, n7.boundingRect().height() / 2.0)
n7.mousePressEvent(_ev7(QEvent.GraphicsSceneMousePress, start7, start7,
                        button=Qt.LeftButton, buttons=Qt.LeftButton))
app.processEvents()
_in_view, _steps = 1, 40
for i in range(1, _steps + 1):
    # ★ 第 7 次修改起跟随**限速**（追差距的 35%、单帧上限 24px）⇒ 这里用**接近真实鼠标的慢拖**
    #   （每步 15/10px）来验"始终在视口内"；快拖允许短暂贴边，由 ㉒ 钉"松手立刻可见"。
    n7.mouseMoveEvent(_ev7(QEvent.GraphicsSceneMouseMove,
                           start7 + QPointF(15.0, 10.0) * i, start7, buttons=Qt.LeftButton))
    app.processEvents()
    if view7.viewport().rect().contains(view7.mapFromScene(n7.pos())):
        _in_view += 1
check("⑰ [回归钉·甲] 拖动中节点**始终在视口内**（修前实测只有 3/21 步）",
      _in_view == _steps + 1, (_in_view, _steps + 1))
check("⑱ [回归钉·甲] 拖动时 `follow_item` **被调用**（每步一次、不递归）",
      0 < len(_calls) <= _steps * 2, len(_calls))
check("⑲ [回归钉·甲] 拖动中 **sceneRect 与滚动条 maximum() 全程不变**（只滚视图、不扩画布）",
      scene7.sceneRect() == _rect7
      and view7.horizontalScrollBar().maximum() == _hmax7
      and view7.verticalScrollBar().maximum() == _vmax7,
      (scene7.sceneRect() == _rect7,
       view7.horizontalScrollBar().maximum() == _hmax7,
       view7.verticalScrollBar().maximum() == _vmax7))

_before = len(_calls)
n7._in_follow = True
try:
    n7.mouseMoveEvent(_ev7(QEvent.GraphicsSceneMouseMove, start7 + QPointF(10.0, 10.0), start7,
                           buttons=Qt.LeftButton))
finally:
    n7._in_follow = False
_locked = len(_calls) - _before
_before = len(_calls)
n7.mouseMoveEvent(_ev7(QEvent.GraphicsSceneMouseMove, start7 + QPointF(20.0, 20.0), start7,
                       buttons=Qt.LeftButton))
_unlocked = len(_calls) - _before
check("⑳ [回归钉·甲] **重入锁生效**：`_in_follow=True` 那一拍跟随 **0 次**、复位后一拍 **1 次**（防栈溢出递归）",
      _locked == 0 and _unlocked == 1, (_locked, _unlocked))
n7.mouseReleaseEvent(_ev7(QEvent.GraphicsSceneMouseRelease, start7, start7, button=Qt.LeftButton))


# ======================================================================
# ㉑ ~ ㉓ 第 7 次修改（2026.10.17，用户："**移动速度太快了，能否降低一下速度**"）
#   第 6 次用 `ensureVisible` ⇒ "差多少一次滚多少"（实测单步 120px / 平均 113px = 一记大跳）；
#   第 7 次改成 **按差距比例追（FOLLOW_FACTOR=0.35）+ 单帧上限（FOLLOW_MAX_STEP=24）+ 最小步长**，
#   并在**松手**时用 `snap_item_visible()` 不限速补一次（快拖允许短暂贴边，松手必须可见）。
# ======================================================================
from widgets.FlowChart import FOLLOW_MAX_STEP                            # noqa: E402

_h7 = view7.horizontalScrollBar()
_v7 = view7.verticalScrollBar()


def _run_drag(step_px, steps=20):
    """把 n7 从画布内的(200,200)起，按 step_px 一步一路往右下拖（不松手），返回统计。"""
    n7.setPos(QPointF(200.0, 200.0))
    view7.centerOn(n7)
    for _ in range(4):
        app.processEvents()
    c = n7.pos() + QPointF(n7.boundingRect().width() / 2.0, n7.boundingRect().height() / 2.0)
    n7.mousePressEvent(_ev7(QEvent.GraphicsSceneMousePress, c, c,
                            button=Qt.LeftButton, buttons=Qt.LeftButton))
    app.processEvents()
    last_h, last_v = _h7.value(), _v7.value()
    deltas, out_steps = [], 0
    for i in range(1, steps + 1):
        n7.mouseMoveEvent(_ev7(QEvent.GraphicsSceneMouseMove,
                               c + QPointF(step_px * i, step_px * i), c,
                               buttons=Qt.LeftButton))
        app.processEvents()
        deltas.append(max(abs(_h7.value() - last_h), abs(_v7.value() - last_v)))
        last_h, last_v = _h7.value(), _v7.value()
        if not view7.viewport().rect().contains(view7.mapFromScene(n7.pos())):
            out_steps += 1
    return deltas, out_steps


_slow, _slow_out = _run_drag(15.0)
check("㉑ [回归钉·第7次] 慢拖（15px/步）⇒ 节点**全程在视口内**、单步滚动量**不超过上限**（平滑、不再一记大跳）",
      _slow_out == 0 and max(_slow) <= FOLLOW_MAX_STEP,
      (max(_slow), FOLLOW_MAX_STEP, _slow_out, _slow))

_fast, _fast_out = _run_drag(120.0)
_n_snap = [0]
_real_snap = view7.snap_item_visible


def _spy_snap(item, _r=_real_snap):
    _n_snap[0] += 1
    return _r(item)


view7.snap_item_visible = _spy_snap
n7.mouseReleaseEvent(_ev7(QEvent.GraphicsSceneMouseRelease, n7.pos(), n7.pos(), button=Qt.LeftButton))
for _ in range(4):
    app.processEvents()
view7.snap_item_visible = _real_snap
check("㉒ [回归钉·第7次] 快拖（120px/步）⇒ 单步滚动量被**限速**（≤ 上限）、且**松手立刻把节点拉回可见**",
      max(_fast) <= FOLLOW_MAX_STEP and _n_snap[0] >= 1
      and view7.viewport().rect().contains(view7.mapFromScene(n7.pos())),
      (max(_fast), FOLLOW_MAX_STEP, _n_snap[0],
       view7.viewport().rect().contains(view7.mapFromScene(n7.pos()))))

check("㉓ [回归钉·第7次] 跟随仍**只滚视图**：`sceneRect` 与两条滚动条 `maximum()` 都没变（丙的约束不破）",
      scene7.sceneRect() == _rect7
      and _h7.maximum() == _hmax7 and _v7.maximum() == _vmax7,
      (scene7.sceneRect() == _rect7, _h7.maximum() == _hmax7, _v7.maximum() == _vmax7))


print()
print("通过 {0} 项，失败 {1} 项".format(_check_pass[0], len(_fails)))
print("失败项：", _fails if _fails else "无")
sys.exit(1 if _fails else 0)
