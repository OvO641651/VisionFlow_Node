# -*- coding: utf-8 -*-
"""批次6 目标1-M6 判据：**连线改正交折线 + 转角圆角 + 入口方向箭头 + 起线点扩到下/左/右**（方案 §4.6）。

用户 2026.10.17 拍板：
  · 曲线 → **正交折线**（只有横竖段）+ **转角圆角**（参考海康 VM）；
  · **入口处画方向箭头**（一眼看出输入/输出，每条线只画一个）；
  · **起线点 = 下 / 左 / 右**（上边只接收、不能起线）；★ 左右点**只能引出、不能接收**；
  · 反向连接（下游在源上方）**走右侧绕行、不穿过节点**；
  · ★ 存档不记端口（`.vfproj` 仍只存两端 uid）⇒ 重启后统一下点起画，端口持久化留给 M8。
"""
import os
import sys
import time

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import Qt, QPoint, QPointF, QEvent, QRectF            # noqa: E402
from PySide2.QtGui import QPainterPath, QMouseEvent               # noqa: E402
from PySide2.QtWidgets import QApplication                        # noqa: E402

app = QApplication([])
import main as m                                                  # noqa: E402
from widgets.FlowChart import (NodeItem, EdgeItem,                 # noqa: E402
                               EDGE_ARROW_SIZE, EDGE_CORNER_RADIUS,
                               EDGE_SIDE_MARGIN, orthogonal_points)

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


def fresh():
    win = new_window()
    view = win.flow_page_mgr.current_page["view"]
    view.flow_scene.clear()
    pump()
    return win, view


def segments_ok(pts):
    """true = 全是横段/竖段（斜段数 == 0）。"""
    bad = 0
    for i in range(1, len(pts)):
        dx = abs(pts[i].x() - pts[i - 1].x())
        dy = abs(pts[i].y() - pts[i - 1].y())
        if dx > 1e-6 and dy > 1e-6:
            bad += 1
    return bad


def curve_count(path):
    return sum(1 for i in range(path.elementCount())
               if path.elementAt(i).type == QPainterPath.CurveToElement)


def mid_points_inside(edge, nodes):
    hits = []
    for p in edge._pts[1:-1]:                      # 端点本来就贴在节点边上，排除
        for n in nodes:
            if n.shape().contains(n.mapFromScene(p)):
                hits.append((n.name, round(p.x(), 1), round(p.y(), 1)))
    return hits


def press_port(view, node, attr, dx=0.0, dy=0.0):
    """在端口旁（偏移 dx,dy 像素，落在矩形外）按下鼠标左键，返回 (是否进入拉线, 端口类型)。"""
    scene_pt = node.mapToScene(getattr(node, attr))
    vp = view.mapFromScene(scene_pt + QPointF(dx, dy))
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(vp), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    view.mousePressEvent(ev)
    started = view._start_node is not None
    kind = getattr(view, "_start_port_type", None) if started else None
    view._cancel_connection()
    pump(1)
    return started, kind


# ---------------------------------------------------------------- ① 正交折线
win, view = fresh()
sc = view.flow_scene
a = NodeItem("灰度", QPointF(80, 80))
b = NodeItem("滤波", QPointF(360, 300))
c = NodeItem("取反", QPointF(120, 520))
for n in (a, b, c):
    sc.addItem(n)
win.flow_nodes.extend([a, b, c])          # ★ 起线判定遍历 flow_nodes，必须登记

e_z = EdgeItem(a, b)
e_rev = EdgeItem(c, a)
e_l = EdgeItem(a, b, start_port="left")
e_r = EdgeItem(a, b, start_port="right")
for e in (e_z, e_rev, e_l, e_r):
    sc.addItem(e)

check("① 常规 Z 形：只有横段/竖段（斜段 = 0）", segments_ok(e_z._pts) == 0, segments_ok(e_z._pts))
check("① 反向连接：只有横段/竖段", segments_ok(e_rev._pts) == 0, segments_ok(e_rev._pts))
check("① 左/右起线：只有横段/竖段",
      segments_ok(e_l._pts) == 0 and segments_ok(e_r._pts) == 0,
      (segments_ok(e_l._pts), segments_ok(e_r._pts)))

# ---------------------------------------------------------------- ② 转角圆角
check("② 常规 Z 形：拐角是圆弧（存在 CurveTo 段，且 ≥2 个）",
      curve_count(e_z.path()) >= 2, curve_count(e_z.path()))
check("② 反向连接：拐角是圆弧", curve_count(e_rev.path()) >= 2, curve_count(e_rev.path()))
check("② 圆角半径常量 = " + str(EDGE_CORNER_RADIUS), EDGE_CORNER_RADIUS > 0, EDGE_CORNER_RADIUS)

# ---------------------------------------------------------------- ③ 端点贴锚点
err_z = (e_z._pts[-1] - b.get_input_pos()).manhattanLength()
err_start = (e_z._pts[0] - a.get_output_pos()).manhattanLength()
err_l = (e_l._pts[0] - a.mapToScene(a.left_port)).manhattanLength()
err_r = (e_r._pts[0] - a.mapToScene(a.right_port)).manhattanLength()
check("③ 端点贴锚点 ≤1.5px（终点 / 下起线 / 左起线 / 右起线）",
      err_z <= 1.5 and err_start <= 1.5 and err_l <= 1.5 and err_r <= 1.5,
      (round(err_z, 3), round(err_start, 3), round(err_l, 3), round(err_r, 3)))

# ---------------------------------------------------------------- ④ 入口箭头
arrow_bbox = e_z._arrow_polygon.boundingRect()
end_pt = b.get_input_pos()
near = abs(arrow_bbox.center().x() - end_pt.x()) <= 10 and abs(arrow_bbox.bottom() - end_pt.y()) <= 10
check("④ 每条线恰有 1 个箭头（3 个顶点）且位于输入点 ±10px",
      e_z._arrow_polygon.count() == 3 and near,
      (e_z._arrow_polygon.count(), arrow_bbox, end_pt))
check("④ 箭头尺寸 = " + str(EDGE_ARROW_SIZE), EDGE_ARROW_SIZE > 0, EDGE_ARROW_SIZE)

# ---------------------------------------------------------------- ⑤ 起线点：下/左/右 可起线，上边不可
ok_out, kind_out = press_port(view, a, "out_port", 0, 12)
ok_left, kind_left = press_port(view, a, "left_port", -12, 0)
ok_right, kind_right = press_port(view, a, "right_port", 12, 0)
ok_top, kind_top = press_port(view, a, "in_port", 0, -12)
check("⑤ 下/左/右三个点都能起线（端口类型正确）",
      ok_out and ok_left and ok_right and (kind_out, kind_left, kind_right) == ("out", "left", "right"),
      (ok_out, kind_out, ok_left, kind_left, ok_right, kind_right))
check("⑤ 上边（输入点）不能起线", ok_top is False, (ok_top, kind_top))

# 矩形内按下 ⇒ 不起线（M2e 规则推广）
scene_pt = a.mapToScene(a.out_port)
vp = view.mapFromScene(scene_pt)                # 正下方 = 矩形内（out_port 在底边中点，往内挪一点）
vp_in = view.mapFromScene(a.mapToScene(QPointF(a.out_port.x(), a.out_port.y() - 6)))
ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(vp_in), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
view.mousePressEvent(ev)
inside_started = view._start_node is not None
view._cancel_connection()
check("⑤ 端口在矩形内那半圈按下 ⇒ 不起线（M2e 规则推广到左/右）", inside_started is False, inside_started)

# ---------------------------------------------------------------- ⑥ 落到左/右点被拒 + 提示
win3, view3 = fresh()
n1 = NodeItem("图片源", QPointF(80, 80))
n2 = NodeItem("灰度", QPointF(400, 340))
for n in (n1, n2):
    view3.flow_scene.addItem(n)
win3.flow_nodes.extend([n1, n2])          # ★ 起线/落线判定遍历 flow_nodes
before = len(win3.flow_edges)
# 用真实拖线路径：从 n1 下点起线，松开在 n2 的左点上
scene_pt = n1.mapToScene(n1.out_port)
vp = view3.mapFromScene(scene_pt + QPointF(0, 12))
view3.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(vp), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
left_pt = n2.mapToScene(n2.left_port)
vp_left = view3.mapFromScene(left_pt)
view3.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPointF(vp_left), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
pump()
after = len(win3.flow_edges)
check("⑥ 落在左点上 ⇒ 不建连线（flow_edges 不变）", after == before, (before, after))
check("⑥ 落在左点上 ⇒ 有明确提示（last_connect_hint）",
      "不支持接收" in (getattr(view3, "last_connect_hint", None) or ""),
      getattr(view3, "last_connect_hint", None))
view3._cancel_connection()

# ---------------------------------------------------------------- ⑦ 真实 add_edge 走端口 + 反向不穿节点
win4, view4 = fresh()
p1 = NodeItem("图片源", QPointF(80, 500))
p2 = NodeItem("灰度", QPointF(140, 80))
view4.flow_scene.addItem(p1)
view4.flow_scene.addItem(p2)
e_add = win4.add_edge(p1, p2, "left")
pump()
check("⑦ main.add_edge 支持 start_port（左起线）",
      e_add is not None and getattr(e_add, "start_port", None) == "left",
      (getattr(e_add, "start_port", None),))
check("⑦ 反向连接不穿过节点（中间点不在任何节点 shape 内）",
      mid_points_inside(e_add, (p1, p2)) == [],
      mid_points_inside(e_add, (p1, p2)))
_right = max(p1.sceneBoundingRect().right(), p2.sceneBoundingRect().right())
_left = min(p1.sceneBoundingRect().left(), p2.sceneBoundingRect().left())
_xs = [p.x() for p in e_add._pts]
# ★ M6b：绕行改为"选更近的一侧" ⇒ 断言改成"在左缘之外 或 在右缘之外（余量 ≥ EDGE_SIDE_MARGIN）"
right_ok = ((max(_xs) >= _right + EDGE_SIDE_MARGIN - 1e-6)
            or (min(_xs) <= _left - EDGE_SIDE_MARGIN + 1e-6))
check("⑦ 反向绕行在节点左/右缘之外（选近侧，余量 ≥ " + str(EDGE_SIDE_MARGIN) + "）", right_ok,
      (round(min(_xs), 1), round(max(_xs), 1), _left, _right))
dup = win4.add_edge(p1, p2)
check("⑦ 同一对起终点重复连线被拒（返回 None ⇒ 不会多出一条线）", dup is None, dup)

# ---------------------------------------------------------------- ⑨（M6b）拖动预览线 = 正交折线
from widgets.FlowChart import build_edge_path                      # noqa: E402

win6, view6 = fresh()
n6 = NodeItem("灰度", QPointF(100, 100))
view6.flow_scene.addItem(n6)
win6.flow_nodes.append(n6)
pump(1)
view6._start_connection(n6, "out")
vp6 = view6.mapFromScene(QPointF(430, 300))
view6.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(vp6),
                                 Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
pump(1)
tmp6 = view6._temp_line
check("⑨ 拖动中的预览线是路径对象（QGraphicsPathItem，不再是直线）",
      tmp6 is not None and type(tmp6).__name__ == "QGraphicsPathItem",
      type(tmp6).__name__ if tmp6 is not None else None)
check("⑨ 预览路径带圆角（CurveTo ≥ 2）",
      tmp6 is not None and curve_count(tmp6.path()) >= 2,
      curve_count(tmp6.path()) if tmp6 is not None else None)
_p6, pts6 = build_edge_path(QPointF(100, 160), QPointF(430, 300), "out",
                            n6.sceneBoundingRect(), None)
check("⑨ 预览用的同一函数产出的折线只有横段/竖段（斜段 = 0）", segments_ok(pts6) == 0, segments_ok(pts6))
view6._cancel_connection()
pump(1)

# ---------------------------------------------------------------- ⑩（M6b）反向绕行选更近的一侧
r_src = QRectF(100, 100, 140, 44)          # 源（左、低）
r_tgt = QRectF(120, 60, 300, 44)           # 目标（右缘 420）⇒ 该布局下"左绕"总长更短
_pA, ptsA = build_edge_path(QPointF(170, 144), QPointF(270, 60), "out", r_src, r_tgt)
xsA = max(p.x() for p in ptsA)
check("⑩ 近距/重叠 ⇒ 绕到目标背离源的外侧（target.right + " + str(EDGE_SIDE_MARGIN) + "px）",
      abs(xsA - (r_tgt.right() + EDGE_SIDE_MARGIN)) < 1e-6, round(xsA, 1))
insideA = [p for p in ptsA[1:-1] if r_src.contains(p) or r_tgt.contains(p)]
check("⑩ 左绕不穿过节点（中间点不在两端节点包围盒内）", insideA == [], insideA)
r_far = QRectF(1400, 60, 140, 44)
_pB, ptsB = build_edge_path(QPointF(170, 144), QPointF(1470, 60), "out", r_src, r_far)
# ★ M6c：绕行 x 取"中间那段竖线"的 x（第 4/5 个点），不能取 max（会取到目标端口 x）
xsB = ptsB[3].x() if len(ptsB) >= 6 else max(p.x() for p in ptsB)
# ★ M6c：规则改成"优先走两节点之间" ⇒ 目标很远时绕行点落在**源右缘与目标左缘之间的空隙里**
#   （比"绕到最外侧"短得多）；空隙不存在时才退回外侧。
check("⑩ 目标很远时绕行点仍落在两节点之间的空隙里（不外扩到最外侧）",
      r_src.right() + 1e-6 <= xsB <= r_far.left() - 1e-6,
      (round(xsB, 1), round(r_src.right(), 1), round(r_far.left(), 1)))

# ---------------------------------------------------------------- ⑪⑫⑬（M6c）反向绕行优先走"两节点之间"
r_srcC = QRectF(80, 240, 140, 44)          # 源（左、低）：80..220
r_tgtC = QRectF(300, 185, 140, 44)         # 目标（右、高）：300..440 ⇒ 空隙 80px
_pC, ptsC = build_edge_path(QPointF(150, 284), QPointF(370, 185), "out", r_srcC, r_tgtC)
_midC = (r_srcC.right() + r_tgtC.left()) / 2.0
xsC = [p.x() for p in ptsC if abs(p.x() - _midC) < 1e-6]
check("⑪ 反向（目标在右）绕行走在两节点之间（x = 空隙中线 " + format(_midC, ".1f") + "）",
      len(xsC) >= 2, [round(p.x(), 1) for p in ptsC])
_insideC = [p for p in ptsC[1:-1] if (r_srcC.contains(p) or r_tgtC.contains(p))]
check("⑪ 走两节点之间不穿过源/目标节点", _insideC == [], _insideC)

r_srcD = QRectF(300, 240, 140, 44)         # 镜像：源在右、目标在左
r_tgtD = QRectF(80, 185, 140, 44)
_pD, ptsD = build_edge_path(QPointF(370, 284), QPointF(150, 185), "out", r_srcD, r_tgtD)
_midD = (r_tgtD.right() + r_srcD.left()) / 2.0
xsD = [p.x() for p in ptsD if abs(p.x() - _midD) < 1e-6]
check("⑫ 反向（目标在左）绕行同样走两节点之间（x = 空隙中线 " + format(_midD, ".1f") + "）",
      len(xsD) >= 2, [round(p.x(), 1) for p in ptsD])

r_srcE = QRectF(230, 75, 140, 44)          # 图1 布局：目标在左下、更低
r_tgtE = QRectF(60, 190, 140, 44)
_pE, ptsE = build_edge_path(QPointF(300, 119), QPointF(130, 190), "out", r_srcE, r_tgtE)
check("⑬ 目标在下方偏左 ⇒ 走常规 Z 形（6 点、不绕行）", len(ptsE) == 6,
      [round(p.x(), 1) for p in ptsE])

# ---------------------------------------------------------------- ⑧ 性能：120 节点 + 100 条线
win5, view5 = fresh()
sc5 = view5.flow_scene
nodes = []
for i in range(120):
    nd = NodeItem("灰度", QPointF(80 + (i % 12) * 260, 80 + (i // 12) * 120))
    sc5.addItem(nd)
    nodes.append(nd)
edges = []
for i in range(100):
    e = EdgeItem(nodes[i], nodes[i + 1])
    sc5.addItem(e)
    edges.append(e)
win5.flow_edges.extend(edges)
t0 = time.time()
for _ in range(10):
    win5.update_all_edges()
pump()
per = (time.time() - t0) / 10.0 * 1000.0
check("⑧ 120 节点 + 100 条线：每次刷新所有连线 < 16ms（实测留数字）", per < 16.0, round(per, 2))
print("      实测：%.2f ms/次" % per)

# ---------------------------------------------------------------- M6d：预览==落定 + 近距对称绕行
# 用户 2026.10.18 两条问题：
#   ①「鼠标拉线时还是原本的远路程，但是接线后就是短路程了」⇒ 预览命中目标节点时要用该节点的
#     输入点 + 矩形去算，使**预览与落定逐点一致**；
#   ②「下一个节点距离上一个节点在左边距离近时，线会绕道上一个节点的右边」⇒ 近距绕行要**左右对称**：
#     只要两节点水平方向还有缝（gap > 0）就走**缝中线**。
def _detour_x(pts, p1, p3):
    """从正交经过点里取"绕行段的 x"（既不是起点的 x、也不是终点的 x）。"""
    xs = [p.x() for p in pts
          if abs(p.x() - p1.x()) > 1e-6 and abs(p.x() - p3.x()) > 1e-6]
    return xs[0] if xs else None


def _geo_case(src_rect, tgt_rect):
    p1 = QPointF(src_rect.center().x(), src_rect.bottom())
    p2 = QPointF(tgt_rect.center().x(), tgt_rect.top())
    pts = orthogonal_points(p1, p2, "out", src_rect, tgt_rect)
    return p1, QPointF(p2.x(), p2.y() - 20.0), pts


# ㊱ 预览 == 落定（拖到目标节点上时）
win6, view6 = fresh()
sc6 = view6.flow_scene
_src = NodeItem("图片源", QPointF(200, 400))
_tgt = NodeItem("灰度", QPointF(420, 200))          # 反向：目标更高、更靠右
sc6.addItem(_src)
sc6.addItem(_tgt)
win6.flow_nodes.extend([_src, _tgt])
pump()
view6._start_connection(_src, "out")
view6._update_temp_line(_tgt.get_input_pos())       # 模拟"鼠标已经拖到目标节点上"
pump()
_prev = view6._temp_line.path()
_fin = EdgeItem(_src, _tgt).path()
_same = (_prev.elementCount() == _fin.elementCount())
if _same:
    for _i in range(_prev.elementCount()):
        _a, _b = _prev.elementAt(_i), _fin.elementAt(_i)
        if abs(_a.x - _b.x) > 1e-6 or abs(_a.y - _b.y) > 1e-6:
            _same = False
            break
check("㊱ 预览 == 落定：拖到目标节点上时，预览路径与落定路径逐点一致",
      _same, (_prev.elementCount(), _fin.elementCount()))
view6._cancel_connection()

# ㊲ 近距·目标在左 ⇒ 绕行落在两节点之间（不再绕到源节点右边）
_r_src = QRectF(300, 400, 140, 44)                  # 源 300..440
_r_tgt = QRectF(150, 200, 140, 44)                  # 目标 150..290 ⇒ 缝 10px（近距）
_p1, _p3, _pts = _geo_case(_r_src, _r_tgt)
_x = _detour_x(_pts, _p1, _p3)
check("㊲ 近距·目标在左 ⇒ 绕到目标背离源的外侧（x == target.left - " + str(EDGE_SIDE_MARGIN) + "）",
      _x is not None and abs(_x - (_r_tgt.left() - EDGE_SIDE_MARGIN)) < 1e-6, _x)
check("㊲b 近距·目标在左 ⇒ 不绕到源节点右边（x 在源左侧之外，左右镜像对称的前提）",
      _x is not None and _x <= _r_src.left() + 1e-6, _x)

# ㊳ 近距·目标在右 ⇒ 与 ㊲ 镜像对称
_r_src2 = QRectF(200, 400, 140, 44)                 # 源 200..340
_r_tgt2 = QRectF(350, 200, 140, 44)                 # 目标 350..490 ⇒ 缝 10px
_p1b, _p3b, _ptsb = _geo_case(_r_src2, _r_tgt2)
_xb = _detour_x(_ptsb, _p1b, _p3b)
check("㊳ 近距·目标在右 ⇒ 绕到目标背离源的外侧（x == target.right + " + str(EDGE_SIDE_MARGIN) + "）",
      _xb is not None and abs(_xb - (_r_tgt2.right() + EDGE_SIDE_MARGIN)) < 1e-6, _xb)
# 镜像对称：把左例整体镜像到右例，绕行 x 应关于两节点中线对称
_mid_left = (_r_tgt.right() + _r_src.left()) / 2.0
_mid_right = (_r_src2.right() + _r_tgt2.left()) / 2.0
_sym = (abs((_mid_right - _r_src2.right()) - (_mid_left - _r_tgt.right())) < 1e-6)
_sym2 = (abs((_r_tgt.left() - _x) - EDGE_SIDE_MARGIN) < 1e-6 and abs((_xb - _r_tgt2.right()) - EDGE_SIDE_MARGIN) < 1e-6)
check("㊳b 近距左/右两例镜像对称（各自到「背离侧」的余量都 == EDGE_SIDE_MARGIN）",
      _sym2, (round(_r_tgt.left() - _x, 3), round(_xb - _r_tgt2.right(), 3)))

# ㊴ 远距回归：缝很大时仍取缝中线（图 1/2/3 的观感不得退化）
_r_src3 = QRectF(80, 400, 140, 44)                  # 源 80..220
_r_tgt3 = QRectF(300, 200, 140, 44)                 # 目标 300..440 ⇒ 缝 80px
_p1c, _p3c, _ptsc = _geo_case(_r_src3, _r_tgt3)
_xc = _detour_x(_ptsc, _p1c, _p3c)
check("㊴ 远距回归：缝 80px ⇒ 绕行 x == 缝中线 260",
      _xc is not None and abs(_xc - 260.0) < 1e-6, _xc)

# ---------------------------------------------------------------- ㊵㊶㊷（M6e）新规则补充
_insideL = [q for q in _pts if q not in (_pts[0], _pts[-1]) and (_r_src.contains(q) or _r_tgt.contains(q))]
_insideR = [q for q in _ptsb if q not in (_ptsb[0], _ptsb[-1]) and (_r_src2.contains(q) or _r_tgt2.contains(q))]
check("㊵ 近距（目标在左）绕外侧不穿两端节点", _insideL == [], _insideL)
check("㊶ 近距（目标在右）绕外侧不穿两端节点", _insideR == [], _insideR)
_r_src4 = QRectF(300, 400, 140, 44)                 # 镜像远距：源在右、目标在左，缝 80px
_r_tgt4 = QRectF(80, 200, 140, 44)
_p1d, _p3d, _ptsd = _geo_case(_r_src4, _r_tgt4)
_xd = _detour_x(_ptsd, _p1d, _p3d)
check("㊷ 远距（目标在左）仍走两节点之间（x == 缝中线 260）",
      _xd is not None and abs(_xd - 260.0) < 1e-6, _xd)

# ---------------------------------------------------------------- 汇总
print("")
print("通过 %d 项，失败 %d 项" % (_check_pass[0], len(_fails)))
if _fails:
    print("失败项：" + " | ".join(_fails))
sys.exit(0 if not _fails else 1)
