# -*- coding: utf-8 -*-
"""批次6 目标1-M2a 判据：**节点外观重构 + 输入点唯一防线**（方案 §4.2）。

方案要求（用户 2026.10.17 定）：
  · 圆角矩形（半径 7）· 高 44 · 宽 = max(140, 图标块 32 + 文字宽 + 边距)
  · 左侧 32px 圆角图标块：正常 `#2E9E4F` / 出错 `#C62828` / 未运行 `#9E9E9E`
  · 竖分隔线 + 节点名（左对齐）· 描边：正常 `#B0B0B0` 1px / 选中 `#1E88E5` 2px / 出错 `#C62828` 2px
  · 四个锚点（上/下/左/右 边中点、空心圆环 r=5、线宽 1.5）
  · ★ 硬兼容：`in_port` / `out_port` 属性名与位置不变（连线端点误差 < 1.5px 的老断言仍要过）
  · ★ 输入点唯一防线：一个节点只接一条输入，第二条拒绝并提示走「参数 → 图像源绑定」
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import QPointF, QEvent, Qt          # noqa: E402
from PySide2.QtGui import QMouseEvent                     # noqa: E402
from PySide2.QtWidgets import QApplication, QGraphicsItem  # noqa: E402

app = QApplication([])
import main as m                                         # noqa: E402
from core.icon_keys import icon_key_for, GENERIC         # noqa: E402
from widgets.FlowChart import NodeItem                   # noqa: E402

_check_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _check_pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def new_window():
    win = m.MainWindow()
    win.main_window.resize(1280, 800)
    win.main_window.show()
    for _ in range(6):
        app.processEvents()
    return win


print("=== 批次6 目标1-M2a：节点外观 + 输入点唯一 ===")
w = new_window()
view = w.flow_page_mgr.current_page["view"]
page = w.flow_page_mgr.current_page

n = w.add_flow_node("灰度", QPointF(300, 200))
for _ in range(3):
    app.processEvents()

# ① 尺寸与自适应宽度
rect = n.rect()
check("① 节点高 = 44", abs(rect.height() - 44.0) < 0.01, rect.height())
check("② 节点宽 ≥ 140", rect.width() >= 140.0, rect.width())
n_long = w.add_flow_node("边缘提取（长名字测试）", QPointF(300, 400))
app.processEvents()
check("③ 宽随名字自适应（长名字更宽）", n_long.rect().width() > n.rect().width(),
      (n_long.rect().width(), n.rect().width()))

# ② 圆角：shape() 命中中心、不命中左上角
center = n.rect().center()
check("④ shape() 命中节点中心", n.shape().contains(center), center)
check("⑤ shape() 不含左上直角处（圆角生效）",
      not n.shape().contains(QPointF(n.rect().left() + 0.3, n.rect().top() + 0.3)))

# ③ boundingRect 含圆环/画笔余量
check("⑥ boundingRect() 比 rect() 大（含圆环与画笔）",
      n.boundingRect().width() > n.rect().width() + 8.0,
      (n.boundingRect().width(), n.rect().width()))

# ④ 四个锚点在四条边的中点
w2 = n.rect().width()
h2 = n.rect().height()
check("⑦ 上锚点 = 上边中点", abs(n.in_port.x() - w2 / 2) < 0.01 and n.in_port.y() == 0.0, n.in_port)
check("⑧ 下锚点 = 下边中点", abs(n.out_port.x() - w2 / 2) < 0.01 and abs(n.out_port.y() - h2) < 0.01, n.out_port)
check("⑨ 左/右锚点 = 左右边中点",
      abs(n.left_port.x() - 0.0) < 0.01 and abs(n.left_port.y() - h2 / 2) < 0.01
      and abs(n.right_port.x() - w2) < 0.01 and abs(n.right_port.y() - h2 / 2) < 0.01,
      (n.left_port, n.right_port))

# ⑤ get_input_pos / get_output_pos 与锚点一致（★ 硬兼容）
ip = n.get_input_pos()
op = n.get_output_pos()
check("⑩ get_input_pos() = 场景坐标下的上锚点",
      abs(ip.x() - (n.pos().x() + n.in_port.x())) < 0.01
      and abs(ip.y() - (n.pos().y() + n.in_port.y())) < 0.01, ip)
check("⑪ get_output_pos() = 场景坐标下的下锚点",
      abs(op.x() - (n.pos().x() + n.out_port.x())) < 0.01
      and abs(op.y() - (n.pos().y() + n.out_port.y())) < 0.01, op)

# ⑥ 四态配色
# ★ M2c：新建默认是 idle（灰）⇒ 断言"正常态是绿"前先显式设成 normal
n.set_state("normal")
check("⑫ 正常态图标块 = 绿 #2E9E4F", n._block_color().name().lower() == "#2e9e4f", n._block_color().name())
n.set_state("error")
check("⑬ 出错态图标块 = 红 #C62828", n._block_color().name().lower() == "#c62828", n._block_color().name())
check("⑭ 出错态描边 = 红 2px",
      n._edge_pen().color().name().lower() == "#c62828" and abs(n._edge_pen().widthF() - 2) < 0.01)
n.set_state("idle")
check("⑮ 未运行态图标块 = 灰 #9E9E9E", n._block_color().name().lower() == "#9e9e9e", n._block_color().name())
n.set_state("normal")
n.setSelected(True)
check("⑯ 选中态描边 = 蓝 #1E88E5",
      n._edge_pen().color().name().lower() == "#1e88e5", n._edge_pen().color().name())
n.setSelected(False)

# ⑦ 图标键
check("⑰ 不同算子 → 不同图标键", icon_key_for("灰度") != icon_key_for("二值化"),
      (icon_key_for("灰度"), icon_key_for("二值化")))
check("⑱ 未登记的算子 → 通用图标", icon_key_for("不存在的算子") == GENERIC)

# ⑧ 输入点唯一防线
a = w.add_flow_node("图片源", QPointF(120, 100))
b = w.add_flow_node("灰度", QPointF(120, 300))
c = w.add_flow_node("相机源", QPointF(400, 100))
app.processEvents()
hints = []
_orig_hint = w._append_log_hint


def _spy_hint(msg):
    hints.append(str(msg))
    return _orig_hint(msg)


w._append_log_hint = _spy_hint
before = len(page["edges"])
e1 = w.add_edge(a, b)
check("⑲ 第一条输入连得上", e1 is not None and len(page["edges"]) == before + 1,
      (e1, len(page["edges"])))
e2 = w.add_edge(c, b)
check("⑳ 第二条输入被拒（边数不变）", e2 is None and len(page["edges"]) == before + 1,
      (e2, len(page["edges"])))
check("㉑ 拒绝时有提示文案（提到『参数 → 图像源绑定』）",
      any("只接受一个输入" in h and "图像源绑定" in h for h in hints), hints[-2:])

# ⑨ 连线端点仍贴锚点（老断言）
path = e1.path()
check("㉒ 连线起点 = 上游下锚点（误差 < 1.5px）",
      (path.pointAtPercent(0.0) - a.get_output_pos()).manhattanLength() < 1.5,
      (path.pointAtPercent(0.0), a.get_output_pos()))
check("㉓ 连线终点 = 下游上锚点（误差 < 1.5px）",
      (path.pointAtPercent(1.0) - b.get_input_pos()).manhattanLength() < 1.5,
      (path.pointAtPercent(1.0), b.get_input_pos()))

# ⑩ M2b：警告（测试用）注册 + 错误状态回填 / 传播一跳
from core.NodeRegistry import NODE_SPECS          # noqa: E402
from core.flow_engine import _results_have_error as _rhe, _apply_run_states as _ars  # noqa: E402

check("㉔ 「警告（测试用）」已注册（算子数 = 15）",
      "警告（测试用）" in NODE_SPECS and len(NODE_SPECS) == 15, len(NODE_SPECS))
check("㉕ 它是处理类（透传不改图）", NODE_SPECS["警告（测试用）"].kind == "process")

warn = w.add_flow_node("警告（测试用）", QPointF(700, 100))
mid = w.add_flow_node("二值化", QPointF(700, 300))
tail = w.add_flow_node("滤波", QPointF(700, 500))
other = w.add_flow_node("取反", QPointF(980, 100))
w.add_edge(warn, mid)
w.add_edge(mid, tail)
for _ in range(3):
    app.processEvents()

spec = NODE_SPECS["警告（测试用）"]
err_res = spec.run(None, None, (0, 0, 0, 0), {})[1]
check("㉖ 警告节点 run() 的结果带 __error__ 标记", _rhe(err_res), err_res)

executed = [(warn, err_res, None, spec), (mid, [], None, None), (tail, [], None, None)]
_ars(w, executed)
check("㉗ 出错节点自己变红", warn.state() == "error", warn.state())
check("㉘ 直接下游（二值化）也变红 —— 传播一跳", mid.state() == "error", mid.state())
check("㉙ 第二跳（滤波）不变红", tail.state() == "normal", tail.state())
check("㉚ 无关分支（取反，本轮没执行）⇒ idle 灰（M2c 甲：未运行）",
      other.state() == "idle", other.state())
check("㉛ 「出错即停」开关默认关", getattr(w, "stop_on_error", False) is False)

_tree = w.tree
_names = []
for i in range(_tree.topLevelItemCount()):
    it = _tree.topLevelItem(i)
    _names.append(it.text(0))
    for j in range(it.childCount()):
        _names.append(it.child(j).text(0))
check("㉜ 树里有「测试」分组且含「警告（测试用）」",
      "测试" in _names and "警告（测试用）" in _names, _names)

# ⑪ ★ M2c（2026.10.17，用户选甲）：未运行灰态
fresh = w.add_flow_node("取反", QPointF(1240, 100))
for _ in range(3):
    app.processEvents()
check("㉝ 新建节点默认 idle（未运行灰）",
      fresh.state() == "idle", fresh.state())
check("㉞ idle 的左侧块 = #9e9e9e（灰）",
      fresh._block_color().name().lower() == "#9e9e9e", fresh._block_color().name())
check("㉟ idle 的描边 = COLOR_EDGE_IDLE（淡灰弱视觉）",
      (fresh._edge_pen().color().name().lower()
       == str(getattr(type(fresh), "COLOR_EDGE_IDLE", "#d8d8d8")).lower()),
      fresh._edge_pen().color().name())

# 一轮执行后：跑到的 = normal（绿），没跑到的 = idle（灰）
branch = [warn, mid, tail]
_ars(w, [(warn, [], None, None), (mid, [], None, None), (tail, [], None, None)])
check("㊱ 执行到的节点 = normal 绿；没跑到的仍 idle 灰",
      all(n.state() == "normal" for n in branch) and fresh.state() == "idle",
      [n.state() for n in branch] + [fresh.state()])

print("")
# ⑫ ★ M2d（2026.10.17，用户口径：「对于导入的项目，设置初始未灰色」）
#    ★ 关键路径：导入时**有当前图**会触发一轮自动重算（`_execute_static`），
#      收尾 `_apply_run_states` 会把执行到的节点刷成 normal（绿）⇒ 必须在导入收尾显式置回 idle。
import numpy as _np_m2d
_w2 = new_window()
_w2.current_static_image = _np_m2d.zeros((64, 64, 3), _np_m2d.uint8)
_w2._apply_project({"pages": [{"title": "M2d 导入测试", "nodes": [
    {"name": "图片源", "x": 200, "y": 120, "params": {}, "params_by_image": {}, "input_source": None},
    {"name": "灰度", "x": 200, "y": 320, "params": {}, "params_by_image": {}, "input_source": None},
], "edges": [(0, 1)]}]}, {"current_page": 0})
for _ in range(4):
    app.processEvents()
_p2 = _w2.flow_page_mgr.current_page
_nodes2 = _p2["nodes"]
check("㊲ 导入方案后（有当前图、走过自动重算）新页节点全部 idle（未运行灰）",
      len(_nodes2) == 2 and all(n.state() == "idle" for n in _nodes2),
      [n.state() for n in _nodes2])
check("㊳ 导入后块色 = #9e9e9e、描边 = COLOR_EDGE_IDLE",
      all(n._block_color().name().lower() == "#9e9e9e" for n in _nodes2)
      and all(n._edge_pen().color().name().lower() == "#d8d8d8" for n in _nodes2),
      [n._block_color().name() for n in _nodes2])
_w2.update_all_edges()
_w2.flow_page_mgr.tab_widget.setCurrentIndex(_w2.flow_page_mgr.tab_widget.currentIndex())
for _ in range(4):
    app.processEvents()
check("㊴ 导入后再做一次刷新连线 / 切页 ⇒ 仍 idle（不会被动变绿）",
      all(n.state() == "idle" for n in _w2.flow_page_mgr.current_page["nodes"]),
      [n.state() for n in _w2.flow_page_mgr.current_page["nodes"]])


print("")
# ⑬ ★ M2e（2026.10.17，用户口径：「下方的点只有矩形外的部分才能拖线，矩形内不能拖线，其他点不变」）
#    修前探针：矩形内·紧邻下边中点按下 ⇒ 进入了"拉线"分支（想拖节点却拉出线）✗
#    修后：矩形内不拉线、回落到"拖节点"；矩形外仍能拉线；上/左/右三点行为不变。
_w3 = new_window()
_v3 = _w3.flow_page_mgr.current_page["view"]
_n3 = _w3.add_flow_node("灰度", QPointF(300, 200))
for _ in range(4):
    app.processEvents()


def _m2e_press(view, node, lx, ly):
    """在节点的 item 局部坐标 (lx, ly) 处按下左键，返回视口坐标。"""
    sp = node.mapToScene(QPointF(lx, ly))
    vp = view.mapFromScene(sp)
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(vp), Qt.LeftButton,
                     Qt.LeftButton, Qt.NoModifier)
    view.mousePressEvent(ev)
    return vp


def _m2e_release(view, vp):
    ev = QMouseEvent(QEvent.MouseButtonRelease, QPointF(vp), Qt.LeftButton,
                     Qt.NoButton, Qt.NoModifier)
    view.mouseReleaseEvent(ev)


def _m2e_reset(view):
    if view._start_node is not None or view._temp_line is not None:
        view._cancel_connection()
    app.processEvents()


_r3 = _n3.rect()
_cx3 = _r3.width() / 2.0
_bot3 = _r3.bottom()
_top3 = _r3.top()
_left3 = _r3.left()
_right3 = _r3.right()
_midy3 = _r3.height() / 2.0

_vp3 = _m2e_press(_v3, _n3, _cx3, _bot3 - 6.0)          # 矩形内、紧邻下边中点
check("㊵ 矩形内·紧邻下边中点按下 ⇒ 不进入拉线（拖节点不再误拉线）",
      _v3._start_node is None and _v3._temp_line is None, _v3._start_node)
_hit3 = _v3.itemAt(_vp3)
check("㊶ 同上位置 ⇒ 仍命中节点且可移动（回落到拖节点分支）",
      isinstance(_hit3, NodeItem)
      and bool(_hit3.flags() & QGraphicsItem.ItemIsMovable), _hit3)
_m2e_release(_v3, _vp3)
_m2e_reset(_v3)

_vp3b = _m2e_press(_v3, _n3, _cx3, _bot3 + 10.0)        # 矩形外、下方 10px
check("㊷ 矩形外·下方 10px 按下 ⇒ 仍能开始拉线（感应圈保留）",
      _v3._start_node is _n3 and _v3._temp_line is not None, _v3._start_node)
_m2e_release(_v3, _vp3b)
_m2e_reset(_v3)

_ok3 = True
for _lx3, _ly3 in ((_cx3, _top3 + 6.0), (_left3 + 6.0, _midy3),
                   (_right3 - 6.0, _midy3)):
    _m2e_reset(_v3)
    _vp3c = _m2e_press(_v3, _n3, _lx3, _ly3)
    if _v3._start_node is not None or _v3._temp_line is not None:
        _ok3 = False
    _m2e_release(_v3, _vp3c)
_m2e_reset(_v3)
check("㊸ 上/左/右三点（矩形内紧邻）仍不拉线 —— 与改前一致", _ok3)

print("通过 {0} 项，失败 {1} 项".format(_check_pass[0], len(_fails)))
if _fails:
    print("失败项：")
    for f in _fails:
        print("  - " + f)
    sys.exit(1)
print("全部通过")
