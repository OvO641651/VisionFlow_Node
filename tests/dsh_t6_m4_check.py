# -*- coding: utf-8 -*-
"""批次6 目标1-M4 判据：**右键画布空白处 → 两级「添加节点」菜单**（方案 §4.4）。

用户 2026.10.17 更正后的口径（原话见方案 §4.4 顶部「★ 口径更正」块）：
  · ★ **左侧树双击功能保留**（本次只是**新增**一种建节点的方式，不是替换）；
  · ★ 菜单**只在「画布空白处」右键**时出现，**两级**：一级 = 树干（采集/处理/检测识别/颜色处理），
    二级 = 节点名；**不含「警告（测试用）」**（测试夹具不给用户入口，树里保留）；
  · ★ **右键节点 / 右键连线的菜单一字不改**（「删除节点」/「删除连线」）；
  · ★ 建出来的节点**中心对齐鼠标点击处**；与树双击**完全等效**（名字 / kind / 默认参数 / 撤销一条）；
  · ★ 建完**自动选中 + 滚动到可见**；ESC / 点菜单外 ⇒ 不建。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import QPoint, QPointF, QEvent                # noqa: E402
from PySide2.QtGui import QContextMenuEvent                      # noqa: E402
from PySide2.QtWidgets import (QApplication, QMenu,              # noqa: E402
                               QGraphicsSceneContextMenuEvent)

app = QApplication([])
import main as m                                                  # noqa: E402
from core import node_catalog                                     # noqa: E402
from core.NodeRegistry import NODE_SPECS, get_spec                # noqa: E402
from widgets.FlowChart import NodeItem, EdgeItem, CANVAS_W, CANVAS_H  # noqa: E402

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


def undo_depth(win):
    return len(getattr(getattr(win, "_undo_stack", None), "_done", []) or [])


def tree_structure(win):
    """从 main.ui 那棵树里读 `[(一级文本, [二级文本…]), …]`（**去掉"测试"分组与空分组**）"""
    out = []
    tree = win.main_window.tree
    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        text = top.text(0)
        if text == node_catalog.TEST_GROUP:
            continue
        kids = [top.child(j).text(0) for j in range(top.childCount())]
        if not kids:
            # 树末尾还有「新建项目」这类**没有子节点的占位项**（不是节点分组）⇒ 不算进去
            continue
        out.append((text, kids))
    return out


def collect_menu(menu):
    """把 `QMenu` 摊平成 `[(一级, [二级…]), …]`（子菜单里取 action 文本）"""
    out = []
    for act in menu.actions():
        sub = act.menu()
        if sub is not None:
            out.append((act.text(), [a.text() for a in sub.actions()]))
        else:
            out.append((act.text(), []))
    return out


print("=== 批次6 目标1-M4：右键画布建节点 ===")
w = new_window()
page = w.flow_page_mgr.current_page
view = page["view"]

# ---------------------------------------------------------------- ① 菜单结构与左侧树逐项一致
print("\n--- ① 菜单结构 / 与左侧树一致 / 不含测试节点 ---")
menu = view.build_create_menu(QPointF(500.0, 500.0))
struct = collect_menu(menu)
tree_struct = tree_structure(w)
check("一级是 4 个树干", len(struct) == 4, struct)
check("一级名字 = 采集/处理/检测识别/颜色处理",
      [g for g, _ in struct] == ["采集", "处理", "检测识别", "颜色处理"], struct)
check("★ 菜单与左侧树逐项一致（分组 + 顺序 + 每个节点名）", struct == tree_struct,
      "menu=%r tree=%r" % (struct, tree_struct))
flat = [n for _g, names in struct for n in names]
check("★ 菜单不含「警告（测试用）」", "警告（测试用）" not in flat, flat)
check("条目总数 = 14（15 个算子去掉测试夹具）", len(flat) == 14, len(flat))
check("★ 清单里的节点都在注册表里", all(n in NODE_SPECS for n in flat), flat)
check("树里仍有「测试」分组（夹具保留）",
      any(w.main_window.tree.topLevelItem(i).text(0) == node_catalog.TEST_GROUP
          for i in range(w.main_window.tree.topLevelItemCount())), None)

# ---------------------------------------------------------------- ② 真实 contextMenuEvent 的空白路径
print("\n--- ② 右键空白：走 contextMenuEvent，且不真弹菜单、不建节点 ---")
# ★ 关键：PySide2 的 `QMenu.exec_` 是 C++ 方法，**用例里替换不掉**（实测赋值被忽略 ⇒ 会真弹菜单
#   并把 offscreen 卡死）⇒ 视图里专门留了 `_exec_menu()` 这一层钩子，用例替换它即可。
recorded = {}
_orig_exec_menu = view._exec_menu


def _fake_exec_menu(menu, global_pos):
    recorded["struct"] = collect_menu(menu)
    return None            # = 用户按 ESC / 点菜单外


view._exec_menu = _fake_exec_menu
try:
    before = len(w.flow_nodes)
    ev = QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(20, 20), QPoint(20, 20))
    view.contextMenuEvent(ev)
    pump(2)
    check("★ 空白右键弹出的结构与清单一致", recorded.get("struct") == tree_struct, recorded)
    check("★ 不触发任何菜单项 ⇒ 不建节点", len(w.flow_nodes) == before, len(w.flow_nodes))
finally:
    view._exec_menu = _orig_exec_menu

# ---------------------------------------------------------------- ③ 点哪建哪（中心对齐）
print("\n--- ③ 点哪建哪：节点中心对齐点击处 ---")
center = QPointF(1234.0, 987.0)
node = w._create_node_from_name("灰度", center)
pump(2)
check("节点已建出", node is not None and node in w.flow_nodes, node)
cx = node.pos().x() + node._node_w / 2.0
cy = node.pos().y() + node._node_h / 2.0
check("★ 节点中心 ≈ 鼠标点（误差 ≤1px）",
      abs(cx - center.x()) <= 1.0 and abs(cy - center.y()) <= 1.0, (cx, cy))

# ---------------------------------------------------------------- ④ 贴边夹取
print("\n--- ④ 贴边：点画布最右下角，节点整体仍在画布内 ---")
edge_node = w._create_node_from_name("边缘提取", QPointF(CANVAS_W - 1.0, CANVAS_H - 1.0))
pump(2)
right = edge_node.pos().x() + edge_node._node_w
bottom = edge_node.pos().y() + edge_node._node_h
check("★ 节点右/下缘不越出画布", right <= CANVAS_W + 0.5 and bottom <= CANVAS_H + 0.5, (right, bottom))

# ---------------------------------------------------------------- ⑤ 与树双击等效
print("\n--- ⑤ 与树双击完全等效（名字 / kind / 默认参数）---")
spec = get_spec(node.name)
check("名字一致", node.name == "灰度", node.name)
check("kind 与注册表一致", spec is not None and spec.kind == "process", spec.kind if spec else None)
check("默认参数一致（新建为空 dict）", node.params == {}, node.params)

# ---------------------------------------------------------------- ⑥ 撤销只记一条
print("\n--- ⑥ 撤销：右键建一个节点 = 一条命令 ---")
base = undo_depth(w)
u = w._create_node_from_name("取反", QPointF(900.0, 1400.0))
pump(2)
check("★ 撤销栈只 +1", undo_depth(w) - base == 1, undo_depth(w) - base)
w.undo()
pump(2)
check("★ 撤销一次该节点就消失", u not in w.flow_nodes, len(w.flow_nodes))

# ---------------------------------------------------------------- ⑦ 自动选中 + 可见
print("\n--- ⑦ 建完自动选中 + 滚动到可见 ---")
sel_node = w._create_node_from_name("二值化", QPointF(2000.0, 1500.0))
pump(2)
check("★ 新节点被自动选中", sel_node.isSelected(), sel_node.isSelected())
check("★ selected_node 就是它", w.selected_node is sel_node, w.selected_node)
vp_pos = view.mapFromScene(sel_node.pos())
check("★ 节点落在视口内（已滚动到可见）", view.viewport().rect().contains(vp_pos), vp_pos)

# ---------------------------------------------------------------- ⑧ 老菜单一字不改
print("\n--- ⑧ 右键节点 / 右键连线 的菜单与改前一致 ---")
node_menu, node_actions = sel_node._make_context_menu()
check("★ 右键节点菜单 = ['删除节点']", [a.text() for a in node_menu.actions()] == ["删除节点"],
      [a.text() for a in node_menu.actions()])
# 连线的菜单是**内联**在 `EdgeItem.contextMenuEvent` 里的（老代码，本轮**一字未动**）：
#   PySide2 替换不掉 `QMenu.exec_` ⇒ 这里改成"源码断言"：那段只构造「删除连线」、且不出现「删除节点」。
import inspect                                                    # noqa: E402
edge_src = inspect.getsource(EdgeItem.contextMenuEvent)
check("★ 右键连线菜单 = ['删除连线']（源码断言：只有这一个动作）",
      'QAction("删除连线"' in edge_src and "删除节点" not in edge_src, edge_src[:80])
check("★ EdgeItem.contextMenuEvent 里没有新增「添加节点」之类的东西",
      "添加节点" not in edge_src and "node_create_requested" not in edge_src, None)

# ---------------------------------------------------------------- ⑨ 树双击仍完全可用
print("\n--- ⑨ 树双击那条路（老功能）仍完全可用 ---")
w2 = new_window()
w2._create_node_from_name("灰度")
first = w2.flow_nodes[-1]
w2._create_node_from_name("取反")
second = w2.flow_nodes[-1]
check("★ 第 1 个节点仍在 (80,80)",
      (first.pos().x(), first.pos().y()) == (80.0, 80.0), (first.pos().x(), first.pos().y()))
check("★ 第 2 个节点仍是 x 不变 / y+180",
      (second.pos().x(), second.pos().y()) == (80.0, 260.0), (second.pos().x(), second.pos().y()))

print("\n=== 结果：通过 %d 项，失败 %d 项 ===" % (_check_pass[0], len(_fails)))
if _fails:
    for t in _fails:
        print("  FAILED: " + t)
    raise SystemExit(1)
