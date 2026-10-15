# -*- coding: utf-8 -*-
"""
批次5 目标4-2：**撤销 / 重做**（2026.10.15）

    python dsh_t5g4_undo_check.py

背景：方案 §7.2 —— 命令模式，纯逻辑在 `core/commands.py`（零 Qt），碰 Qt 的那半在
`services/undo_service.py`（`UndoMixin`，第 7 个 Mixin），命令记在 `main.py` 的四个改动入口上
（`add_flow_node` / `add_edge` / `delete_flow_node` / `delete_edge`）。

判据（每条都能回答"什么情况下为 False"）：

    ① 初始：栈空 ⇒ 菜单两项 + 顶部两个按钮**都是灰的**；
    ② 建节点 ⇒ 记一条命令；撤销 ⇒ 节点消失；重做 ⇒ **名字 / 坐标 / 参数**都回来；
    ③ **往返断言**（做 N 步 → 撤销 N 步 = 回到初始 → 重做 N 步 = 回到末态，逐项比对）；
    ④ ★ **删节点会把它的连线一起删掉** ⇒ 撤销必须把**节点和那些连线**都放回去（最容易漏的一条）；
    ⑤ 删连线 ⇒ 撤销按原两端恢复；
    ⑥ 栈**上限**：超过上限丢最旧的（用户拍板 50，用例里改小来验）；
    ⑦ **撤销栈每页一条**：换页**不清**历史（用户 2026.10.15 修正："换页后撤销失效"），
       新出现的页面（新建 / 导入）**以出现时为基准**（栈本来就是空的）；⑧ 撤销**不清结果缓存**（既有语义：缓存键里没有流程图指纹）；
    ⑨ 撤销 / 重做各写一行日志；⑩ 重复连同一对起终点 ⇒ 不算动作、不记命令；
    ⑪ 参数快照跟着命令走（撤销后重做，节点参数还在）。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication        # noqa: E402
from PySide2.QtCore import QPointF                # noqa: E402
app = QApplication([])
import main as m                                  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


def snap(w):
    """流程图快照：节点（名字 + 坐标 + 参数）+ 连线（两端名字）—— 往返断言的判据"""
    nodes = sorted((n.name, int(n.pos().x()), int(n.pos().y()),
                    tuple(sorted((k, str(v)) for k, v in (getattr(n, "params", None) or {}).items())))
                   for n in w.flow_nodes)
    edges = sorted((e.start_node.name, e.end_node.name) for e in w.flow_edges)
    return (nodes, edges)


def last_row(w):
    log = w.execution_log
    return log.item(log.rowCount() - 1, 4).text() if log is not None and log.rowCount() else ""


w = m.MainWindow()
w.main_window.show()
w.execution_log.setRowCount(0)

# ======================================================================
# ① 初始：栈空 ⇒ 四项控件都灰
# ======================================================================
check("① 初始撤销栈为空", w._undo_stack.can_undo is False and w._undo_stack.depth == 0)
check("① 初始：菜单两项 + 顶部两个按钮都是灰的（.ui 里就是 enabled=false，接线后由栈联动）",
      w.action_undo.isEnabled() is False and w.action_redo.isEnabled() is False
      and w.btn_undo.isEnabled() is False and w.btn_redo.isEnabled() is False,
      (w.action_undo.isEnabled(), w.btn_undo.isEnabled()))

# ======================================================================
# ② 建节点 ⇒ 记一条；撤销 ⇒ 没了；重做 ⇒ 名字/坐标/参数都回来
# ======================================================================
n1 = w.add_flow_node("取反", QPointF(40, 60))
n1.params["test_key"] = 123
check("② 建一个节点 ⇒ 栈深 1、撤销可用（菜单与按钮都被点亮）",
      w._undo_stack.depth == 1 and w._undo_stack.can_undo is True
      and w.action_undo.isEnabled() is True and w.btn_undo.isEnabled() is True,
      (w._undo_stack.depth, w.action_undo.isEnabled()))
w.undo()
check("② 撤销 ⇒ 节点从流程图里消失（flow_nodes 空 + 场景里也没了）",
      len(w.flow_nodes) == 0 and len(w.flow_edges) == 0, len(w.flow_nodes))
check("② 撤销后：重做可用、撤销变灰（栈的联动是对的）",
      w._undo_stack.can_redo is True and w.action_redo.isEnabled() is True
      and w.action_undo.isEnabled() is False)
w.redo()
back = w.flow_nodes[0] if w.flow_nodes else None
check("② 重做 ⇒ 节点回来了，**名字 / 坐标 / 参数**都对",
      back is not None and back.name == "取反"
      and (int(back.pos().x()), int(back.pos().y())) == (40, 60)
      and back.params.get("test_key") == 123,
      None if back is None else (back.name, back.pos(), back.params.get("test_key")))

# ======================================================================
# ③ 往返断言：N 步 → 撤销 N 步 → 重做 N 步
# ======================================================================
w2 = m.MainWindow()
w2.main_window.show()
initial = snap(w2)
a = w2.add_flow_node("取反", QPointF(20, 20))
b = w2.add_flow_node("灰度", QPointF(20, 200))
c = w2.add_flow_node("二值化", QPointF(20, 380))
w2.add_edge(a, b)
w2.add_edge(b, c)
final = snap(w2)
steps = w2._undo_stack.depth
for _ in range(steps):
    w2.undo()
check("③ 往返：做 %d 步 ⇒ 撤销 %d 步 = 回到**初始**状态（逐项比对）" % (steps, steps),
      snap(w2) == initial and w2._undo_stack.can_undo is False, (steps, snap(w2) != initial))
for _ in range(steps):
    w2.redo()
check("③ 往返：再重做 %d 步 = 回到**末态**（逐项比对）" % steps,
      snap(w2) == final, snap(w2) != final)

# ======================================================================
# ④ ★ 删节点会连带删连线 ⇒ 撤销要把"节点 + 那些连线"一起放回
# ======================================================================
w3 = m.MainWindow()
w3.main_window.show()
p1 = w3.add_flow_node("取反", QPointF(20, 20))
p2 = w3.add_flow_node("灰度", QPointF(20, 200))
p3 = w3.add_flow_node("二值化", QPointF(20, 380))
w3.add_edge(p1, p2)
w3.add_edge(p2, p3)
before_delete = snap(w3)
w3.delete_flow_node(p2)
check("④ 删中间节点 ⇒ 它的**两条连线**也一起被删掉",
      [n.name for n in w3.flow_nodes] == ["取反", "二值化"] and len(w3.flow_edges) == 0,
      ([n.name for n in w3.flow_nodes], len(w3.flow_edges)))
w3.undo()
check("④ 撤销 ⇒ 节点**和两条连线**都回来了（端点、坐标、参数逐项一致）",
      snap(w3) == before_delete, (snap(w3), before_delete))

# ======================================================================
# ⑤ 删连线 ⇒ 撤销按原两端恢复
# ======================================================================
w3.delete_edge(w3.flow_edges[0])
check("⑤ 删一条连线 ⇒ 少一条", len(w3.flow_edges) == 1, len(w3.flow_edges))
w3.undo()
check("⑤ 撤销 ⇒ 连线回来了，且两端还是原来那两个节点",
      len(w3.flow_edges) == 2
      and all(e.start_node in w3.flow_nodes and e.end_node in w3.flow_nodes for e in w3.flow_edges),
      [(e.start_node.name, e.end_node.name) for e in w3.flow_edges])

# ======================================================================
# ⑥ 栈上限（丢最旧的）
# ======================================================================
w4 = m.MainWindow()
w4.main_window.show()
w4._undo_stack.limit = 3
for i in range(5):
    w4.add_flow_node("取反", QPointF(20 + i * 30, 20))
check("⑥ 栈上限 3 ⇒ 做了 5 步只留 3 步（丢最旧的）",
      w4._undo_stack.depth == 3, w4._undo_stack.depth)
for _ in range(3):
    w4.undo()
check("⑥ 撤到头只能撤 3 步 ⇒ 还剩 2 个节点（最早的 2 步撤不回来，符合上限语义）",
      len(w4.flow_nodes) == 2, len(w4.flow_nodes))

# ======================================================================
# ⑦ 【2026.10.15 修正】撤销栈**每页一条**：换页不清历史；新出现的页（新建 / 导入）以出现时为基准
# ======================================================================
w12 = m.MainWindow()
w12.main_window.show()
w12.add_flow_node("取反", QPointF(20, 20))          # 第一页：一次动作
depth_page1 = w12._undo_stack.depth
w12.flow_page_mgr.add_page()                        # 新建一页并切过去（= 一次"新页面出现"）
check("⑦ 新出现的页面（新建 / 导入同理）⇒ 撤销栈**本来就是空的**、按钮灰（= 以出现时为基准）",
      w12._undo_stack.depth == 0 and w12.action_undo.isEnabled() is False,
      (w12._undo_stack.depth, w12.action_undo.isEnabled()))
w12.add_flow_node("灰度", QPointF(20, 20))          # 在新页上做一次改动
check("⑦ 在新页上改一处 ⇒ 可撤销（只记这一页自己的历史）",
      w12._undo_stack.depth == 1 and w12.action_undo.isEnabled() is True, w12._undo_stack.depth)
w12.undo()
check("⑦ 撤销一次就回到'这一页刚出现时'（页面本身撤不掉、也不该撤掉）",
      len(w12.flow_nodes) == 0 and w12._undo_stack.can_undo is False, len(w12.flow_nodes))
w12.flow_page_mgr.tab_widget.setCurrentIndex(0)      # 切回第一页
check("⑦ 切回第一页：它的节点回来了（确认真的切过去了）",
      [n.name for n in w12.flow_nodes] == ["取反"], [n.name for n in w12.flow_nodes])
check("⑦ [Bug 修复] **换页之后历史还在、撤销按钮还能用**（用户报的「换页后撤销失效」）",
      w12._undo_stack.depth == depth_page1 and w12.action_undo.isEnabled() is True
      and w12._undo_stack.undo_text.startswith("新建节点"),
      (w12._undo_stack.depth, depth_page1))
w12.undo()
check("⑦ 在第一页撤销 ⇒ 它的节点没了（每页各管自己的历史，互不干扰）",
      len(w12.flow_nodes) == 0, [n.name for n in w12.flow_nodes])

# ======================================================================
# ⑧ 撤销不清结果缓存（既有语义：结果缓存键里没有"流程图指纹"）
# ======================================================================
w5 = m.MainWindow()
w5.main_window.show()
q1 = w5.add_flow_node("取反", QPointF(20, 20))
import numpy as np                                        # noqa: E402
frame = np.full((60, 80, 3), 30, np.uint8)
w5._frame_paths[id(frame)] = "u1.png"
w5._execute_static(frame, "continuous")
n_cache = len(w5.result_cache)
w5.add_flow_node("灰度", QPointF(20, 200))
w5.undo()
check("⑧ 撤销**不会**清空结果缓存（改拓扑/改参数本来就不清缓存 —— 这是既有语义）",
      n_cache > 0 and len(w5.result_cache) == n_cache, (n_cache, len(w5.result_cache)))

# ======================================================================
# ⑨ 日志：撤销 / 重做各写一行
# ======================================================================
w5.execution_log.setRowCount(0)
w5.undo() if w5._undo_stack.can_undo else None
n_after_undo = last_row(w5)
w5.redo() if w5._undo_stack.can_redo else None
n_after_redo = last_row(w5)
check("⑨ 撤销写了一行'已撤销：…'", n_after_undo.startswith("已撤销："), n_after_undo)
check("⑨ 重做写了一行'已重做：…'", n_after_redo.startswith("已重做："), n_after_redo)

# ======================================================================
# ⑩ 重复连同一对起终点 ⇒ 不算动作、不记命令
# ======================================================================
w6 = m.MainWindow()
w6.main_window.show()
x = w6.add_flow_node("取反", QPointF(20, 20))
y = w6.add_flow_node("灰度", QPointF(20, 200))
w6.add_edge(x, y)
depth_1 = w6._undo_stack.depth
again = w6.add_edge(x, y)
check("⑩ 同一对起终点再连一次 ⇒ 返回 None 且**不记命令**（栈深不变）",
      again is None and w6._undo_stack.depth == depth_1, (again, w6._undo_stack.depth))

# ======================================================================
# ⑪ 参数快照跟着命令走
# ======================================================================
z = w6.add_flow_node("二值化", QPointF(20, 380))
z.params["thresh"] = 77
w6.undo()                                   # 撤销"新建节点"（此时会把 params 一并采集）
w6.redo()
z2 = [n for n in w6.flow_nodes if n.name == "二值化"]
check("⑪ 撤销后重做：节点参数跟着回来（命令里存的是参数字典快照）",
      len(z2) == 1 and z2[0].params.get("thresh") == 77,
      None if not z2 else z2[0].params.get("thresh"))

# ======================================================================
# ⑫ 参数修改（参数窗口"确定"后记一条；undo / redo 换参数字典快照）
# ======================================================================
w7 = m.MainWindow()
w7.main_window.show()
pnode = w7.add_flow_node("二值化", QPointF(30, 40))
p_before = dict(pnode.params)
w7._undo_stack.clear()
pnode.params["thresh_dummy"] = 5                       # 模拟参数窗口改完并提交
w7._mark_dirty_if_params_changed(pnode, p_before)      # 真实入口就是这个（main.py）
check("⑫ 参数确实变了 ⇒ 记一条命令（文案里带'参数'）",
      w7._undo_stack.depth == 1 and "参数" in w7._undo_stack.undo_text,
      (w7._undo_stack.depth, w7._undo_stack.undo_text))
w7.undo()
check("⑫ 撤销 ⇒ 参数回到改之前（逐项一致）", dict(pnode.params) == p_before,
      (dict(pnode.params), p_before))
w7.redo()
check("⑫ 重做 ⇒ 参数又变回改之后", pnode.params.get("thresh_dummy") == 5,
      pnode.params.get("thresh_dummy"))
w7._undo_stack.clear()
w7._mark_dirty_if_params_changed(pnode, dict(pnode.params))
check("⑫ 参数**没变**时不记命令（只在真改了才进栈）", w7._undo_stack.depth == 0, w7._undo_stack.depth)

# ======================================================================
# ⑬ / ⑭ 拖动节点（拖动期间信号连发 ⇒ 攒成"一次拖动 = 一条命令"）
# ======================================================================
w8 = m.MainWindow()
w8.main_window.show()
mnode = w8.add_flow_node("取反", QPointF(20, 20))
w8._undo_stack.clear()
start_pos = (mnode.pos().x(), mnode.pos().y())
for dx in (10, 20, 30):                                # 模拟拖动过程中的多次移动
    mnode.setPos(QPointF(20 + dx, 20 + dx))
    mnode.positionChanged.emit()
check("⑬ 拖动过程中**不**立刻记命令（先攒着，免得一次拖动塞进几十条）",
      w8._undo_stack.depth == 0, w8._undo_stack.depth)
w8._commit_pending_moves()                             # 等价于"停 0.4 秒后提交"（用例直接调，不 sleep）
check("⑬ 拖动停下 ⇒ 只记 **1 条**命令", w8._undo_stack.depth == 1, w8._undo_stack.depth)
end_pos = (mnode.pos().x(), mnode.pos().y())
check("⑬ 记的是「起点→终点」（终点 = 松手时的坐标）",
      end_pos == (50.0, 50.0), end_pos)
w8.undo()
check("⑭ 撤销拖动 ⇒ 坐标回到拖动前", (mnode.pos().x(), mnode.pos().y()) == start_pos,
      (start_pos, (mnode.pos().x(), mnode.pos().y())))
w8.redo()
check("⑭ 重做拖动 ⇒ 坐标回到拖动后", (mnode.pos().x(), mnode.pos().y()) == end_pos,
      (end_pos, (mnode.pos().x(), mnode.pos().y())))

# ======================================================================
# ⑮ 【Bug 修复回归】撤销到底 → 全部重做：节点/坐标/连线都对，且线**真的贴在节点上**
#     （用户 2026.10.15 报："全部撤销后再一步一步重做，节点和线并不是连在一起的"）
# ======================================================================
def edges_attached(w):
    """每条连线的两端是否**真的贴在**两端节点上（线的路径起点 = 起点节点的输出点）"""
    try:
        for e in w.flow_edges:
            path = e.path()
            p0 = path.pointAtPercent(0.0)
            p1 = path.pointAtPercent(1.0)
            s = e.start_node.get_output_pos()
            t = e.end_node.get_input_pos()
            if abs(p0.x() - s.x()) > 1.5 or abs(p0.y() - s.y()) > 1.5:
                return False
            if abs(p1.x() - t.x()) > 1.5 or abs(p1.y() - t.y()) > 1.5:
                return False
        return True
    except (RuntimeError, AttributeError):
        return False


def edges_reference_live_nodes(w):
    """连线的两端是不是"当前流程图里活着的那些节点"（而不是被销毁的旧对象）"""
    live = {id(n) for n in w.flow_nodes}
    try:
        return all(id(e.start_node) in live and id(e.end_node) in live for e in w.flow_edges)
    except RuntimeError:
        return False


w9 = m.MainWindow()
w9.main_window.show()
n_src = w9.add_flow_node("图片源", QPointF(20, 20))
n_inv = w9.add_flow_node("取反", QPointF(20, 200))
n_blur = w9.add_flow_node("滤波", QPointF(20, 380))
w9.add_edge(n_src, n_inv)
w9.add_edge(n_inv, n_blur)
n_src.setPos(QPointF(300, 60))            # 再拖一下（用户图里那一步）
n_src.positionChanged.emit()
w9._commit_pending_moves()
final_snap = snap(w9)
check("⑮ 撤销前：3 个节点 + 2 条连线，且线都贴在节点上",
      len(w9.flow_nodes) == 3 and len(w9.flow_edges) == 2 and edges_attached(w9))
steps_9 = w9._undo_stack.depth
for _ in range(steps_9):
    w9.undo()
check("⑮ 撤销到底：画布清空、栈也空了", len(w9.flow_nodes) == 0 and w9._undo_stack.can_undo is False,
      (len(w9.flow_nodes), w9._undo_stack.can_undo))
for _ in range(steps_9):
    w9.redo()
check("⑮ [Bug 修复] 全部重做后：节点 / 坐标 / 连线与撤销前**逐项一致**",
      snap(w9) == final_snap, (snap(w9), final_snap))
check("⑮ [Bug 修复] 重做出来的每条连线，两端都是**当前活着的节点**（不是被销毁的旧对象）",
      edges_reference_live_nodes(w9), [(id(e.start_node), id(e.end_node)) for e in w9.flow_edges])
check("⑮ [Bug 修复] 重做出来的线**真的贴在节点上**（用户报的「线飘着」）",
      edges_attached(w9),
      [(e.start_node.name, e.end_node.name) for e in w9.flow_edges])

# ======================================================================
# ⑯ 【Bug 修复回归】"删节点 → 撤销 → 再撤销那条新建"：节点必须真的消失、栈必须空
#     （用户 2026.10.15 报："撤销按钮已经灰了，但图上还存在灰度节点"）
# ======================================================================
w10 = m.MainWindow()
w10.main_window.show()
n_gray = w10.add_flow_node("灰度", QPointF(20, 20))
w10.delete_flow_node(n_gray)              # 栈：[新建节点, 删除节点]
w10.undo()                                # 撤销"删除" ⇒ 节点被**重建**（新对象）
check("⑯ 撤销'删除节点'后：节点回来了",
      [x.name for x in w10.flow_nodes] == ["灰度"], [x.name for x in w10.flow_nodes])
w10.undo()                                # 撤销"新建节点" ⇒ 必须删掉**活着的那一个**
check("⑯ [Bug 修复] 再撤销'新建节点'：画布上**没有**节点了，且栈已空（按钮该灰）",
      len(w10.flow_nodes) == 0 and w10._undo_stack.can_undo is False
      and w10.action_undo.isEnabled() is False,
      ([x.name for x in w10.flow_nodes], w10._undo_stack.can_undo, w10.action_undo.isEnabled()))
w10.redo()                                # 重做"新建节点" ⇒ 节点回来
check("⑯ [Bug 修复] 重做'新建节点' ⇒ 节点又回来（身份连续）",
      [x.name for x in w10.flow_nodes] == ["灰度"], [x.name for x in w10.flow_nodes])
w10.redo()                                # 重做"删除节点" ⇒ 又删掉（净效果 = 用户那两步）
check("⑯ [Bug 修复] 重做'删除节点' ⇒ 又删掉了（重做的净效果与用户操作序列一致）",
      len(w10.flow_nodes) == 0, [x.name for x in w10.flow_nodes])
w10.undo()                                # 再撤销一次 ⇒ 还能弄回来（反复往返都不坏）
check("⑯ [Bug 修复] 再撤销一次 ⇒ 节点还能回来（反复往返不坏）",
      [x.name for x in w10.flow_nodes] == ["灰度"], [x.name for x in w10.flow_nodes])

# ======================================================================
# ⑰ 【Bug 修复回归】参数是"按图片"存的：**跨图撤销也要撤对**
#     （用户 2026.10.15 报："我一直撤销……但是参数还是没有回到参数值，而是显示修改后的值；
#       重新运行程序就没有这个问题了" —— 因为存档只在内存里）
# ======================================================================
w11 = m.MainWindow()
w11.main_window.show()
img_a = np.full((80, 100, 3), 90, np.uint8)
img_b = np.full((80, 100, 3), 30, np.uint8)
w11._frame_paths[id(img_a)] = "pa.png"
w11._frame_paths[id(img_b)] = "pb.png"
w11.current_static_image = img_a
w11.current_image_key = "pa.png"
pnode2 = w11.add_flow_node("边缘提取", QPointF(20, 20))
w11._load_node_params(w11.flow_nodes, "pa.png")
p_before2 = dict(pnode2.params)
pnode2.params["edge_low"] = 99                                  # = 在 A 图上把低阈值改成 99
w11._mark_dirty_if_params_changed(pnode2, p_before2, "pa.png")  # 真实入口（会带上图片键）
w11._switch_image_params("pb.png")                              # 切到 B 图（A 的参数进存档）
w11.current_static_image = img_b
w11.current_image_key = "pb.png"
w11.undo()                                                      # 在 B 图上撤销那次改参数
w11._switch_image_params("pa.png")                              # 再切回 A 图
w11.current_static_image = img_a
w11.current_image_key = "pa.png"
check("⑰ [Bug 修复] 在 A 图改参数 → 切到 B 图撤销 → 切回 A 图：参数**真的回到改之前**",
      pnode2.params.get("edge_low") != 99 and dict(pnode2.params) == p_before2,
      (pnode2.params.get("edge_low"), p_before2))
check("⑰ [Bug 修复] A 图的参数存档里也不再留着改后的值（存档键被清掉）",
      (w11._get_node_params_store(pnode2).get("pa.png") or {}).get("edge_low") != 99,
      w11._get_node_params_store(pnode2).get("pa.png"))

w11.redo()
w11._switch_image_params("pb.png")
w11.current_image_key = "pb.png"
w11._switch_image_params("pa.png")
w11.current_image_key = "pa.png"
check("⑰ [Bug 修复] 重做之后切回 A 图：参数又变回改后的值（重做同样按图片走）",
      pnode2.params.get("edge_low") == 99, pnode2.params.get("edge_low"))

# ======================================================================
# ⑱ 导入的流程图：**以"刚导入时"为基准**（导入动作本身不可撤销，导入之后的修改才能撤销/重做）
#     —— 用户 2026.10.15 口径："对于导入的流程图，设置撤销最多只能撤销到导入时"
# ======================================================================
w13 = m.MainWindow()
w13.main_window.show()
imported = w13.flow_page_mgr.append_pages(["导入的页"])[0]      # = `_apply_project` 用的那条路
i1 = w13._add_node_to_page(imported, "取反", QPointF(30, 30))     # 模拟"导入时带来的"节点与连线
i2 = w13._add_node_to_page(imported, "灰度", QPointF(30, 200))
w13._add_edge_to_page(imported, i1, i2)
w13.flow_page_mgr.tab_widget.setCurrentIndex(w13.flow_page_mgr.tab_widget.indexOf(imported["widget"]))
check("⑱ 导入动作本身**不进撤销栈**（导入用的是 `_add_node_to_page`，不经过四个入口）",
      w13._undo_stack.depth == 0 and w13.action_undo.isEnabled() is False,
      (w13._undo_stack.depth, w13.action_undo.isEnabled()))
w13.add_flow_node("二值化", QPointF(30, 380))                    # 导入**之后**的修改
check("⑱ 导入之后做一次修改 ⇒ 可以撤销（重做同理）",
      w13._undo_stack.depth == 1 and w13.action_undo.isEnabled() is True, w13._undo_stack.depth)
w13.undo()
check("⑱ 撤销到底 = **回到导入时的样子**（两个节点 + 一条连线仍在），且不能再撤",
      [n.name for n in w13.flow_nodes] == ["取反", "灰度"] and len(w13.flow_edges) == 1
      and w13._undo_stack.can_undo is False,
      ([n.name for n in w13.flow_nodes], len(w13.flow_edges)))
w13.redo()
check("⑱ 再重做 ⇒ 导入之后的那一步回来（重做也不越过导入这条基线）",
      [n.name for n in w13.flow_nodes] == ["取反", "灰度", "二值化"],
      [n.name for n in w13.flow_nodes])

print("-" * 70)
if fails:
    print("失败项：%d" % len(fails))
    for name in fails:
        print("   - " + name)
else:
    print("失败项：无")
sys.exit(1 if fails else 0)
