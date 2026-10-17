# -*- coding: utf-8 -*-
"""批次6 目标1-M3 判据：**画布右下角小地图（可拖视口框导航）**（方案 §4.3）。

用户 2026.10.17 拍板的口径：
  · 位置 = **右下角**（距边 8px；原方案"左下角"已被用户改掉）
  · 尺寸 = **180×135**（与固定大画布 4000×3000 等比，s = 0.045）
  · 外观 = 浅灰底 `#F5F5F5` + 圆角 4 + 1px 边框 `#C8C8C8`
  · 只画 **节点小方块**（颜色 = 运行状态 绿/灰/红）+ **橙色视口框 `#F0A030`**；**不画连线**
  · 交互 = **可拖视口框**导航；**框外点击不响应（甲）**；滚轮 `ignore()` 交给上层
  · 实例 = **全局一个**，换页 `bind_view()` 重绑（不残留旧页）
"""
import os
import sys
import time

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import QPointF, Qt                      # noqa: E402
from PySide2.QtGui import QMouseEvent                       # noqa: E402
from PySide2.QtWidgets import QApplication                  # noqa: E402

app = QApplication([])
import main as m                                            # noqa: E402
from widgets.flow_minimap import (FlowMiniMap, MAP_W, MAP_H, MAP_MARGIN,  # noqa: E402
                                  COLOR_BG, COLOR_VIEW_RECT)

_check_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _check_pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def pump(n=6):
    for _ in range(n):
        app.processEvents()


def new_window():
    win = m.MainWindow()
    win.main_window.resize(1280, 800)
    win.main_window.show()
    pump()
    return win


def send_mouse(widget, kind, pos):
    types = {"press": QMouseEvent.MouseButtonPress,
             "move": QMouseEvent.MouseMove,
             "release": QMouseEvent.MouseButtonRelease}
    ev = QMouseEvent(types[kind], QPointF(pos), Qt.LeftButton,
                     Qt.LeftButton if kind != "release" else Qt.NoButton, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)
    pump(2)


def scene_center(mm):
    return mm.viewport_scene_rect().center()


print("=== 批次6 目标1-M3：右下角小地图 ===")
w = new_window()
mgr = w.flow_page_mgr
page = mgr.current_page
view = page["view"]
mm = getattr(mgr, "minimap", None)

# ① 实例与几何
check("① 全局只有一个小地图且已创建", isinstance(mm, FlowMiniMap), type(mm).__name__)
check("② 小地图挂在当前页画布视口里", mm.parentWidget() is view.viewport())
vp = view.viewport()
check("③ 尺寸 = 180×135", (mm.width(), mm.height()) == (MAP_W, MAP_H), (mm.width(), mm.height()))
check("④ 贴在右下角（距边 8px）",
      (mm.x(), mm.y()) == (vp.width() - MAP_W - MAP_MARGIN, vp.height() - MAP_H - MAP_MARGIN),
      ((mm.x(), mm.y()), (vp.width() - MAP_W - MAP_MARGIN, vp.height() - MAP_H - MAP_MARGIN)))
check("⑤ 视口随容器 resize 重新贴右下角（不靠 FlowchartView 改代码）",
      hasattr(mm, "eventFilter") and mm.eventFilter is not None)

# ② 视口框与主视图同步（3 个滚动位置）
worst = 0.0
for (hx, vy) in ((0.0, 0.0), (0.5, 0.5), (0.999, 0.999)):
    h = view.horizontalScrollBar()
    v = view.verticalScrollBar()
    h.setValue(int(h.minimum() + (h.maximum() - h.minimum()) * hx))
    v.setValue(int(v.minimum() + (v.maximum() - v.minimum()) * vy))
    pump(2)
    vr_scene = mm.viewport_scene_rect()
    back = mm.map_to_scene(mm.view_rect_in_map().topLeft())
    worst = max(worst, abs(back.x() - vr_scene.left()), abs(back.y() - vr_scene.top()))
check("⑥ 视口框与主视图同步（3 个位置，回算误差 ≤ 2 场景像素）", worst <= 2.0, worst)

# ③ 节点方块：数量与状态色
view.horizontalScrollBar().setValue(view.horizontalScrollBar().minimum())
view.verticalScrollBar().setValue(view.verticalScrollBar().minimum())
n_idle = w.add_flow_node("灰度", QPointF(300, 200))
n_norm = w.add_flow_node("二值化", QPointF(300, 420))
n_err = w.add_flow_node("滤波", QPointF(300, 640))
pump(4)
n_idle.set_state("idle")
n_norm.set_state("normal")
n_err.set_state("error")
pump(2)
blocks = mm.node_blocks()
check("⑦ 节点方块数 = 当前页节点数", len(blocks) == len(page["nodes"]), (len(blocks), len(page["nodes"])))
from widgets.FlowChart import NodeItem                   # noqa: E402
colors = sorted(c for _, c in blocks)
check("⑧ 方块颜色跟运行状态（绿/灰/红各一）",
      colors == sorted([NodeItem.COLOR_BLOCK_IDLE, NodeItem.COLOR_BLOCK_NORMAL,
                        NodeItem.COLOR_BLOCK_ERROR]), colors)

# ④ 拖框导航（真鼠标事件）：视口中心按比例跟随
s, _ox, _oy = mm._transform()
check("⑨ 比例 = 180/4000 = 0.045（等比，无拉伸）", abs(s - 0.045) < 1e-9, s)
start = QPointF(mm.view_rect_in_map().center())
before = scene_center(mm)
send_mouse(mm, "press", start)
check("⑩ 框内按下 ⇒ 进入拖动并变抓取光标",
      mm._dragging and mm.cursor().shape() == Qt.ClosedHandCursor,
      (mm._dragging, mm.cursor().shape()))
dx_map, dy_map = 12.0, 9.0
send_mouse(mm, "move", QPointF(start.x() + dx_map, start.y() + dy_map))
after = scene_center(mm)
err_x = abs(after.x() - before.x() - dx_map / s)
err_y = abs(after.y() - before.y() - dy_map / s)
check("⑪ 拖框 ⇒ 主视图视口中心按比例跟随（误差 ≤ 2 场景像素）",
      err_x <= 2.0 and err_y <= 2.0, (err_x, err_y))
send_mouse(mm, "release", QPointF(start.x() + dx_map, start.y() + dy_map))
check("⑫ 松开后退出拖动", mm._dragging is False)

# ⑤ 拖到极限：视口不越出固定大画布
ok_all = True
detail = []
for (mx, my, tag) in ((MAP_W + 400, MAP_H + 400, "右下"), (-500, -500, "左上")):
    send_mouse(mm, "press", QPointF(mm.view_rect_in_map().center()))
    send_mouse(mm, "move", QPointF(mx, my))
    vrs = mm.viewport_scene_rect()
    sr = mm.scene_rect()
    ok = (vrs.left() >= sr.left() - 0.5 and vrs.top() >= sr.top() - 0.5
          and vrs.right() <= sr.right() + 0.5 and vrs.bottom() <= sr.bottom() + 0.5)
    ok_all = ok_all and ok
    detail.append((tag, ok))
    send_mouse(mm, "release", QPointF(mx, my))
check("⑬ 拖到极限 ⇒ 视口仍完整落在 4000×3000 画布内", ok_all, detail)

# ⑥ 框外点击 = 视口直接跳过去，并且按下就能接着拖（★ 乙，M3b）
# ★ 程序化挑一个"肯定在视口框外"、且**离画布边缘足够远**（不触发 centerOn 夹取）的点
vr_now = mm.view_rect_in_map()
candidates = [QPointF(MAP_W * 0.5, MAP_H * 0.5), QPointF(MAP_W * 0.62, MAP_H * 0.55),
              QPointF(MAP_W * 0.5, MAP_H * 0.72), QPointF(2.0, 2.0)]
outside = None
for p in candidates:
    if vr_now.contains(p):
        continue
    t = mm.map_to_scene(p)
    # 离画布四边都留 300 场景像素以上 ⇒ centerOn 不会被 sceneRect 夹住
    if 300.0 <= t.x() <= (mm.scene_rect().width() - 300.0) and 300.0 <= t.y() <= (mm.scene_rect().height() - 300.0):
        outside = p
        break
check("⑭a 能造出一个「框外且不被夹取」的测试点", outside is not None, (vr_now, candidates))
if outside is not None:
    # ★ 鼠标事件坐标是整数 ⇒ 用"实际投递的整数点"算期望值，避免 0.5 像素截断误差
    pt = QPointF(float(int(outside.x())), float(int(outside.y())))
    target = mm.map_to_scene(pt)
    send_mouse(mm, "press", pt)
    c1 = scene_center(mm)
    err_jump = max(abs(c1.x() - target.x()), abs(c1.y() - target.y()))
    check("⑭ 框外点击 ⇒ 视口中心跳到点击处（误差 ≤ 2 场景像素）", err_jump <= 2.0,
          (err_jump, pt, target))
    check("⑭b 跳转后进入拖动状态（可以接着拖）", mm._dragging is True, mm._dragging)
    s2, _ox2, _oy2 = mm._transform()
    dx2, dy2 = -20.0, -12.0
    send_mouse(mm, "move", QPointF(pt.x() + dx2, pt.y() + dy2))
    c2 = scene_center(mm)
    err_mx = abs(c2.x() - c1.x() - dx2 / s2)
    err_my = abs(c2.y() - c1.y() - dy2 / s2)
    check("⑮ 跳转后继续拖动 ⇒ 视口跟着走（误差 ≤ 2 场景像素）",
          err_mx <= 2.0 and err_my <= 2.0, (err_mx, err_my))
    send_mouse(mm, "release", QPointF(pt.x() + dx2, pt.y() + dy2))

# ⑦ 滚轮交给上层
class _FakeWheel(object):
    def __init__(self):
        self.ignored = False

    def ignore(self):
        self.ignored = True

fw = _FakeWheel()
mm.wheelEvent(fw)
check("⑮ 滚轮 event.ignore() 交给上层（小地图自身不处理）", fw.ignored is True)

# ⑧ 性能：120 节点重绘
for i in range(117):
    w.add_flow_node("灰度", QPointF(120 + (i % 12) * 300, 120 + (i // 12) * 120))
pump(6)
t0 = time.time()
for _ in range(20):
    mm.update()
    mm.repaint()
per = (time.time() - t0) * 1000 / 20
check("⑯ 120 节点时单次重绘 < 16 ms", per < 16.0, round(per, 2))

# ⑨ 换页重绑
old_view = view
old_count = len(mm.node_blocks())
mgr.add_page()
pump(6)
new_page = mgr.current_page
check("⑰ 换页后小地图绑到新页的画布", mm._view is new_page["view"], mm._view is new_page["view"])
check("⑱ 换页后 parent 也换到新页视口", mm.parentWidget() is new_page["view"].viewport())
check("⑲ 新页没有节点 ⇒ 小地图方块数 0（不残留旧页）", len(mm.node_blocks()) == 0, len(mm.node_blocks()))
w.add_flow_node("取反", QPointF(400, 300))
pump(4)
check("⑳ 新页加 1 个节点 ⇒ 方块数 1", len(mm.node_blocks()) == 1, len(mm.node_blocks()))
mgr.tab_widget.setCurrentIndex(0)
pump(6)
check("㉑ 切回第 1 页 ⇒ 小地图绑回旧 view", mm._view is old_view)
check("㉒ 切回后方块数恢复 = 旧页节点数", len(mm.node_blocks()) == old_count,
      (len(mm.node_blocks()), old_count))
old_h = old_view.horizontalScrollBar()
old_h.setValue(old_h.minimum() + 50)
pump(2)
back = mm.map_to_scene(mm.view_rect_in_map().topLeft())
check("㉓ 换页后视口框仍与新页画布同步（回算误差 ≤ 2）",
      abs(back.x() - mm.viewport_scene_rect().left()) <= 2.0)

print("\n=== 结果 ===")
print("通过 %d 项，失败 %d 项" % (_check_pass[0], len(_fails)))
if _fails:
    print("失败项：")
    for t in _fails:
        print("  - " + t)
    sys.exit(1)
sys.exit(0)
