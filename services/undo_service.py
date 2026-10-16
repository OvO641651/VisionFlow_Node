# -*- coding: utf-8 -*-
"""
撤销 / 重做（批次5 目标4）—— **碰 Qt 的那一半**（见《批次5 技术方案》§7.2 / §7.7）

分工：
    · **纯逻辑**（命令 + 栈）在 `core/commands.py`：零 Qt、可单独测；
    · **本文件**（`UndoMixin` + `_UndoContext`）负责"与流程图和界面打交道"：把命令下到改动入口、
      用 **uid** 解析"当前活着的那个节点 / 连线"、接菜单与按钮、联动 `enabled`、写日志行、清栈时机。

为什么这么分：落点规则（方案 §八）—— **零 Qt 的逻辑进 `core/`，碰 Qt 的服务进 `services/`**。
`UndoMixin` 是第 **7** 个 Mixin，由 `MainWindow` 多重继承 ⇒ 方法之间照旧 `self.xxx` 互调、调用点零改动。

## ★ uid 是什么、为什么需要它（2026.10.15 修两个 bug 的核心）

`NodeItem` / `EdgeItem` 是 Qt 对象：**撤销会把它们销毁，重做是"重建一个新对象"**。
如果命令里存的是节点对象引用，就会出现（用户实测报的两个现象）：
    ① **线飘了** —— 重做连线时 `EdgeItem(旧起点, 旧终点)` 拿到的是**已销毁**的对象，几何算不对；
    ② **按钮灰了、节点还在** —— "删节点 → 撤销（重建新对象）→ 再撤销那条更早的『新建节点』"时，
       命令里的旧引用早已不在流程图里 ⇒ 删了个寂寞。
所以：**给每个节点 / 连线一个 uid**（存在 `node._undo_uid` 上），命令只存 uid，
执行时用 `ctx.resolve(uid)` 取"现在活着的那一个"；重建时**沿用同一个 uid** ⇒ 身份连续。

★ 记录口径（用户 2026.10.15 拍板）：命令只记在 `main.py` 的四个改动入口上
（`add_flow_node` / `add_edge` / `delete_flow_node` / `delete_edge`，右键菜单与树双击也都走它们）
+ `_mark_dirty_if_params_changed`（改参数）+ `_on_node_moved`（拖动）；撤销 / 重做执行期间用
`_undo_busy` 挡住记录，避免"回退动作又被记成新动作"。
"""
from PySide2.QtCore import QPointF, QTimer            # 坐标拷贝 + 拖动"攒一条命令"的延时提交
from PySide2.QtWidgets import QAction, QPushButton    # 只用于 findChild 找 .ui 里的四个控件

from core.host_contract import MainHost
from core.commands import (UNDO_LIMIT, AddEdgeCommand, AddNodeCommand, MoveNodeCommand,
                           RemoveEdgeCommand, RemoveNodeCommand, SetParamsCommand, UndoStack,
                           snapshot_params)

MOVE_COMMIT_DELAY_MS = 400        # 拖动停止多久算"这一拖结束"（只影响记命令的时机，不影响画面）


class _UndoContext(object):
    """
    命令要用的"宿主能力"（`core/commands.py` 只按这几个方法名调用它）。

    · **uid 注册表**：`uid -> 活对象`；`resolve()` 会顺手探活（Qt 对象被销毁会 `RuntimeError`，
      这时把条目清掉并返回 `None`，让命令"安静地跳过"而不是崩）；
    · 放在这里而不是给 `MainWindow` 加一堆公开方法：少一堆接口面，也让"命令 ↔ 流程图"的翻译集中一处。
    """

    def __init__(self, host):
        self.host = host
        self._live = {}            # uid -> 活着的 NodeItem
        self._live_edges = {}      # uid -> 活着的 EdgeItem
        self._uid_seq = 0

    # ---------------------------------------------------------------- uid
    def _next_uid(self):
        self._uid_seq += 1
        return self._uid_seq

    def ensure_uid(self, node):
        """取这个节点的 uid；没有就发一个（方案里读出来的节点也会在这里补上）"""
        uid = getattr(node, "_undo_uid", None)
        if uid is None or (uid in self._live and self._live[uid] is not node):
            uid = self._next_uid()
            node._undo_uid = uid
        self._live[uid] = node
        return uid

    def bind_edge(self, edge, uid=None):
        """取这条连线的 uid；没有就发一个"""
        uid = uid or getattr(edge, "_undo_uid", None) or self._next_uid()
        edge._undo_uid = uid
        self._live_edges[uid] = edge
        return uid

    def resolve(self, uid):
        """uid → 现在活着的节点（已被销毁 / 已经不在流程图里 ⇒ 清掉条目、返回 None）"""
        node = self._live.get(uid)
        if node is None:
            return None
        try:
            # 探活有两层：① 对象是否还在"当前页的节点表"里（`scene.removeItem` 只是解除场景归属，
            #   对象本身可能还活着 ⇒ 光看 pos() 探不出来）；② C++ 对象是否已被销毁。
            if node not in self.host.flow_nodes:
                self._live.pop(uid, None)
                return None
            node.pos()
        except RuntimeError:
            self._live.pop(uid, None)
            return None
        return node

    def forget(self, uid):
        """把某个 uid 从注册表里摘掉（用在"界面马上要删掉这个对象"之前，避免解析到僵尸对象）"""
        self._live.pop(uid, None)

    def forget_edge(self, uid):
        self._live_edges.pop(uid, None)

    def resolve_edge(self, uid):
        edge = self._live_edges.get(uid)
        if edge is None:
            return None
        try:
            edge.start_node                               # 探活
        except RuntimeError:
            self._live_edges.pop(uid, None)
            return None
        return edge

    # ---------------------------------------------------------------- 节点
    def create_node(self, uid, name, pos, params=None):
        """在当前页建一个节点，并把它绑到这个 uid 上（比界面入口少一步"记命令"，避免递归记录）"""
        host = self.host
        node = host._add_node_to_page(host.flow_page_mgr.current_page, name, pos)
        # `_add_node_to_page` 里会调 `_undo_remember_node` ⇒ 可能已经发过一个 uid，这里要换成本命令的
        old = getattr(node, "_undo_uid", None)
        node._undo_uid = uid
        if old is not None and old != uid:
            self._live.pop(old, None)
        self._live[uid] = node
        if params:
            node.params.update(params)
        return node

    def capture_node(self, node):
        """(名字, 坐标, 参数深拷贝) —— 删之前必须先采集"""
        return (getattr(node, "name", ""), node.pos(),
                snapshot_params(getattr(node, "params", {})))

    def drop_node(self, node):
        uid = getattr(node, "_undo_uid", None)
        self.host.delete_flow_node(node)
        if uid is not None:
            self._live.pop(uid, None)

    def capture_links(self, node):
        """这个节点牵扯的连线：`[(另一端节点的 uid, "out"/"in"), …]`（"out" = 它是起点）"""
        links = []
        for edge in list(self.host.flow_edges):
            src = getattr(edge, "start_node", None)
            dst = getattr(edge, "end_node", None)
            if src is node and dst is not node:
                links.append((self.ensure_uid(dst), "out"))
            elif dst is node and src is not node:
                links.append((self.ensure_uid(src), "in"))
        return links

    # ---------------------------------------------------------------- 连线
    def create_edge(self, src_uid, dst_uid, uid=None):
        src = self.resolve(src_uid)
        dst = self.resolve(dst_uid)
        if src is None or dst is None:
            return None
        edge = self.host.add_edge(src, dst)
        if edge is None:
            return None
        self.bind_edge(edge, uid)
        return edge

    def drop_edge(self, edge):
        uid = getattr(edge, "_undo_uid", None)
        self.host.delete_edge(edge)
        if uid is not None:
            self._live_edges.pop(uid, None)

    # ---------------------------------------------------------------- 参数 / 坐标
    def apply_params(self, uid, snapshot, image_key=None):
        """
        把节点参数换成这份快照。

        ★ 参数的存档是**按图片**的（`params_per_image[图片键]`），所以这里要区分两件事：
        · `image_key` 就是**当前这张图**（或为 None，老口径）⇒ 同时改 `node.params` 与那一份存档；
        · `image_key` 是**别的图** ⇒ **只改那张图的存档**，绝不碰 `node.params`
          （它代表的是当前这张图的参数）。
        这样"在 A 图改完 → 切到 B 图 → 撤销 → 再切回 A 图"时，A 的参数才会真的回到改之前。
        """
        node = self.resolve(uid)
        if node is None:
            return False
        host = self.host
        current = getattr(host, "current_image_key", None)
        if image_key is None or image_key == current:
            node.params.clear()
            node.params.update(snapshot)
        if image_key is not None:
            # 只给"跟着图片走"的节点写图片槽（起点 / 输出这类流程级节点不参与按图片归档）
            if not host._is_flow_level_node(node):
                store = host._get_node_params_store(node)
                if snapshot:
                    store[image_key] = dict(snapshot)
                else:
                    store.pop(image_key, None)     # 空快照 = 这张图当时没设过 ⇒ 按约定不占槽
        elif current is not None:
            host._save_node_params([node], current)
        return True

    def move_node(self, uid, pos):
        """把节点挪到指定坐标（`setPos` 会触发 `positionChanged` ⇒ 连线跟着刷新）"""
        node = self.resolve(uid)
        if node is None:
            return False
        node.setPos(pos)
        self.host.update_all_edges()
        return True

    def copy_pos(self, pos):
        """坐标的独立副本（命令里存快照用；core/commands.py 不 import Qt，所以拷贝放这儿）"""
        return QPointF(pos)


class UndoMixin(MainHost):
    """撤销 / 重做（批次5 目标4 从零新建；用户 2026.10.15 拍板：栈上限 50、快捷键先不做）"""

    # ------------------------------------------------------------------
    def _init_undo(self):
        """由 `main.py::__init__` 调一次（在 `flow_page_mgr.setup()` **之前**，这样换页回调也能用上）"""
        # ★ 撤销栈是**按页面各一条**的（用户 2026.10.15 口径："换页之后还要能撤销/重做"）：
        #   `_undo_stacks[页 key]` = 那一页自己的历史；`_undo_stack` 永远指向**当前页**那一条。
        #   好处：① 换页不再清空历史；② 每页的命令只作用在自己页的节点上
        #   （`ctx.resolve()` 本来也只认当前页的 `flow_nodes`）；
        #   ③ **导入的页面第一次出现时栈是空的** ⇒ 天然满足"撤销最多只能撤到导入时"。
        self._undo_stacks = {}
        self._undo_stack = UndoStack(limit=UNDO_LIMIT)     # 占位；绑定当前页时会被换掉
        self._undo_stack.add_changed_callback(self._on_undo_stack_changed)
        self._undo_ctx = _UndoContext(self)
        self._undo_busy = False            # 撤销 / 重做执行中：不许再记录新命令
        self._undo_ready = True
        # ★ 拖动撤销用：节点 uid → "上一次提交过的坐标" + 攒着待提交的拖动 + 延时器
        #   （拖动期间 positionChanged 会连发很多次 ⇒ 攒成"一次拖动 = 一条命令"）
        self._pos_committed = {}
        self._pending_moves = {}
        self._move_timer = QTimer()
        self._move_timer.setSingleShot(True)
        self._move_timer.timeout.connect(self._commit_pending_moves)
        # .ui 里已经摆好的四个控件（批次5 目标4 的控件占位）：菜单两项 + 顶部两个按钮
        window = getattr(self, "main_window", None)
        self.action_undo = window.findChild(QAction, "action_undo") if window is not None else None
        self.action_redo = window.findChild(QAction, "action_redo") if window is not None else None
        self.btn_undo = window.findChild(QPushButton, "btn_undo") if window is not None else None
        self.btn_redo = window.findChild(QPushButton, "btn_redo") if window is not None else None
        # 接线：菜单项 / 按钮 都接到同一对方法上（"一个操作一处定义" ⇒ 以后加快捷键只加在 action 上）
        if self.action_undo is not None:
            self.action_undo.triggered.connect(self.undo)
        if self.action_redo is not None:
            self.action_redo.triggered.connect(self.redo)
        if self.btn_undo is not None:
            self.btn_undo.clicked.connect(self.undo)
        if self.btn_redo is not None:
            self.btn_redo.clicked.connect(self.redo)
        # 栈状态一变就联动 enabled（add_changed_callback 会立刻同步一次 ⇒ 初始两个都是灰的）
        return self._undo_stack

    # ------------------------------------------------------------------ 每页一条撤销栈
    def _stack_for(self, page_key):
        """取某一页自己的撤销栈；没有就新建一个**空**栈（= 以这一页"刚出现时"为基准）"""
        if page_key is None:
            page_key = "__no_page__"
        stack = self._undo_stacks.get(page_key)
        if stack is None:
            stack = UndoStack(limit=UNDO_LIMIT)
            stack.add_changed_callback(self._on_undo_stack_changed)
            self._undo_stacks[page_key] = stack
        return stack

    def _bind_undo_stack_for_page(self):
        """
        换页 / 载入方案 / 新建页面之后：把"当前撤销栈"换成**这一页自己的**那一条。

        · **不清空**历史（用户 2026.10.15 要求："在一个页面画完 → 切到另一页画 → 回到第一页，
          撤销按钮还要能用"）；
        · 顺手把**已经删掉的页面**的栈丢掉（免得越攒越多）；
        · 刚导入 / 新建的页面第一次用到时栈是空的 ⇒ 撤销最多只能撤到"刚导入时"。
        """
        manager = getattr(self, "flow_page_mgr", None)
        if manager is None:
            return self._undo_stack
        keys = {page.get("key") for page in manager.pages}
        for key in list(self._undo_stacks):
            if key not in keys:
                del self._undo_stacks[key]
        self._undo_stack = self._stack_for(manager.page_key())
        self._on_undo_stack_changed(self._undo_stack)      # 立刻同步按钮 enabled
        return self._undo_stack

    # ------------------------------------------------------------------ 记录
    def _undo_note(self, kind, payload):
        """
        记一条命令（由 `main.py` 的改动入口调用）。

        :param kind: "add_node" / "remove_node" / "add_edge" / "remove_edge" /
                     "set_params"（payload = `(节点, 改之前的参数字典)`）/
                     "move_pending"（payload = 节点；攒着，停 0.4 秒后提交一条）/
                     "move_node"（payload = `(uid, 旧坐标, 新坐标)`，由 `_commit_pending_moves` 用）
        :param payload: 见上（删的那两类要在**删之前**调，这里会先采集状态）
        """
        if not getattr(self, "_undo_ready", False) or getattr(self, "_undo_busy", False):
            return None
        ctx = self._undo_ctx
        if kind == "add_node":
            node = payload
            uid = ctx.ensure_uid(node)
            self._pos_committed[uid] = QPointF(node.pos())
            command = AddNodeCommand(uid, getattr(node, "name", "节点"), ctx)
        elif kind == "remove_node":
            node = payload
            uid = ctx.ensure_uid(node)
            command = RemoveNodeCommand(uid, ctx.capture_node(node), ctx.capture_links(node), ctx)
            # 界面（调用方）紧接着就会真的删掉它 ⇒ 先把注册表摘干净：
            # 否则 `scene.removeItem` 之后对象其实还活着（Python 侧还有引用），会被误当成"还在"。
            ctx.forget(uid)
        elif kind == "add_edge":
            edge = payload
            uid = ctx.bind_edge(edge)
            command = AddEdgeCommand(uid, ctx.ensure_uid(edge.start_node),
                                     ctx.ensure_uid(edge.end_node), ctx)
        elif kind == "remove_edge":
            edge = payload
            uid = ctx.bind_edge(edge)
            command = RemoveEdgeCommand(uid, ctx.ensure_uid(edge.start_node),
                                        ctx.ensure_uid(edge.end_node), ctx)
            ctx.forget_edge(uid)               # 同理：紧接着会被界面删掉
        elif kind == "set_params":
            # payload = (节点, 改之前的参数字典, 是哪张图的参数)；老调用方可能只给 2 项
            node, before = payload[0], payload[1]
            image_key = payload[2] if len(payload) > 2 else None
            uid = ctx.ensure_uid(node)
            command = SetParamsCommand(uid, getattr(node, "name", "节点"),
                                       before, dict(getattr(node, "params", {})), image_key, ctx)
        elif kind == "move_pending":
            # 拖动中：攒着（同一节点反复移动只留最后一个位置），停止 0.4 秒后统一提交
            self._pending_moves[ctx.ensure_uid(payload)] = True
            self._move_timer.start(MOVE_COMMIT_DELAY_MS)
            return None
        elif kind == "move_node":
            uid, old, new = payload
            node = ctx.resolve(uid)
            command = MoveNodeCommand(uid, getattr(node, "name", "节点") if node else "节点",
                                      old, new, ctx)
        else:
            return None
        return self._undo_stack.push(command)

    def _commit_pending_moves(self):
        """把"攒着的拖动"提交成命令（一次拖动一条：起点 → 终点）"""
        pending, self._pending_moves = self._pending_moves, {}
        for uid in list(pending):
            node = self._undo_ctx.resolve(uid)
            if node is None:                   # 节点已被销毁（比如这一拖之后又删了它）
                continue
            old = self._pos_committed.get(uid)
            new = QPointF(node.pos())
            if old is None:
                self._pos_committed[uid] = new
                continue
            if abs(old.x() - new.x()) < 0.5 and abs(old.y() - new.y()) < 0.5:
                continue                       # 位置几乎没变：不算一次动作
            self._pos_committed[uid] = new
            self._undo_note("move_node", (uid, old, new))

    def _undo_remember_node(self, node):
        """
        记下节点"上一次提交过的坐标"（拖动撤销要知道拖动前在哪），顺便给它发一个 uid。

        在**建节点**与**绑定页面**两处各调一次（`main.py`）—— 这样无论是新建的、
        还是从方案里读出来的节点，第一次拖动都能撤回到原位置。
        """
        try:
            uid = self._undo_ctx.ensure_uid(node)
            self._pos_committed[uid] = QPointF(node.pos())
        except (RuntimeError, AttributeError):
            pass

    def _on_undo_stack_changed(self, stack):
        """栈变了：四项控件的 enabled / 提示文字跟着变（空栈 ⇒ 灰）

        ★ 用 `getattr` 取控件：`_init_undo()` 里建"占位栈"时会立刻回调一次，
        那时 `.ui` 里的四个控件还没找出来（不能直接 `self.action_undo`）。
        """
        pairs = ((getattr(self, "action_undo", None), getattr(self, "btn_undo", None),
                  stack.can_undo, "撤销：{0}".format(stack.undo_text)),
                 (getattr(self, "action_redo", None), getattr(self, "btn_redo", None),
                  stack.can_redo, "重做：{0}".format(stack.redo_text)))
        for action, button, enabled, tip in pairs:
            for widget in (action, button):
                if widget is None:
                    continue
                widget.setEnabled(bool(enabled))
                widget.setToolTip(tip if enabled else "")

    # ------------------------------------------------------------------ 动作
    def _run_stack_step(self, method_name, verb):
        """撤销 / 重做的公共部分：挡住记录 + 兜底异常 + 写日志行"""
        stack = getattr(self, "_undo_stack", None)
        if stack is None:
            return None
        self._undo_busy = True
        try:
            command = getattr(stack, method_name)()
        except Exception as exc:               # 万一某条命令出错（对象被销毁等），别让界面崩
            command = None
            self._append_log_hint("{0}失败：{1}".format(verb, exc))
        finally:
            self._undo_busy = False
        if command is None:
            if not getattr(self, "_undo_stack_error", False):
                self._append_log_hint("没有可{0}的操作".format(verb))
            return None
        self._append_log_hint("已{0}：{1}".format(verb, command.text))
        # ★ 批次5目标5-M2 轮2（2026.10.16，用户实测）：撤销 / 重做要**同步这一页的"未保存"标记** ——
        #   撤销到**栈底** = 回到这一页的基线（导入 / 保存那一刻）⇒ 清掉 dirty；重做 ⇒ 重新标脏。
        #   否则会出现用户报的："一直撤销到按钮变灰（已回到初始导入状态），点关闭页面却弹'有修改是否保存'"。
        try:
            manager = self.flow_page_mgr
            if method_name == "undo" and not stack.can_undo:
                manager.clear_dirty(manager.current_page)
            elif method_name == "redo":
                manager.mark_dirty()
        except Exception:
            pass
        return command

    def undo(self):
        """撤销一步（菜单 / 按钮 / 以后加 Ctrl+Z 都走这里）"""
        return self._run_stack_step("undo", "撤销")

    def redo(self):
        """重做一步"""
        return self._run_stack_step("redo", "重做")
