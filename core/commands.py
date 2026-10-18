# -*- coding: utf-8 -*-
"""
撤销 / 重做的命令与栈（批次5 目标4；**纯逻辑、零 Qt**，见《批次5 技术方案》§7.2 / §7.7）

## 设计要点

· **`Command`** = 一个"会改流程图"的动作：`do()` / `undo()` / `text`；
· 命令**不碰任何 Qt 对象** —— 它只持有"要动的数据"（节点名 / 坐标 / 参数字典）、
  **节点 uid**（见下）和宿主给它的**能力对象 `ctx`**；真正建删 `NodeItem` / `EdgeItem` 的活
  由 `services/undo_service.py` 里的 `_UndoContext` 干（那里才碰 Qt）；
· **`UndoStack`** = 栈（上限由用户拍板：50 步）+ 变化回调。回调用**普通函数列表**，
  **不引 Qt 的 Signal** —— 这样这个文件永远不需要 import PySide2。

## ★ 为什么命令里存的是 **uid** 而不是节点对象（2026.10.15 修 bug 的关键）

`NodeItem` 是 Qt 对象，**撤销时会被销毁、重做时是"重建一个新对象"**。如果命令里存的是当时的对象引用，就会出现：

1. **线飘了**：重做连线时 `EdgeItem(旧起点, 旧终点)` 拿到的是**已销毁**的对象 ⇒ 几何算不出来 / 对不上；
2. **按钮灰了节点还在**：先"删节点"再撤销（重建了一个新对象），此时若又撤销那条更早的"新建节点"，
   命令里的旧引用已经不在流程图里 ⇒ 删了个寂寞 ⇒ 栈空了、画布上却还有节点。

改成"**命令只存 uid，执行时向 `ctx` 解析成活对象**"：重建时把**同一个 uid** 绑到新对象上，
于是"重做连线 / 重做删除 / 重做移动 / 重做改参数"永远作用在**当前活着的那一个**上。
（uid 的登记、解析、失效清理都在 `_UndoContext`，本文件只用 `ctx.xxx(uid, …)` 这套接口。）

## 统一约定

**所有命令的"首次执行"都已经由界面做过了** ⇒ 一律 `stack.push(cmd, execute=False)`；
之后 `undo()` 回退、`redo()` 调 `do()` 重做。
"""
import copy

UNDO_LIMIT = 50          # 栈上限（用户 2026.10.15 拍板：50 步）


class Command(object):
    """一个有 `do()` / `undo()` 的动作；`text` 是写给日志 / 菜单看的人话"""
    text = "操作"

    def do(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError


class AddNodeCommand(Command):
    """新建节点（用户已经建好 ⇒ 首次不执行）：撤销 = 删掉；重做 = 用**同一个 uid** 重建"""

    def __init__(self, uid, name, ctx):
        self.ctx = ctx
        self.uid = uid
        self.name = name or "节点"
        self.state = None                 # (name, pos, params)，撤销时采集

    @property
    def text(self):
        return "新建节点「{0}」".format(self.name)

    def do(self):
        if self.state is not None and self.ctx.resolve(self.uid) is None:
            self.ctx.create_node(self.uid, *self.state)

    def undo(self):
        node = self.ctx.resolve(self.uid)
        if node is None:
            return
        self.state = self.ctx.capture_node(node)
        self.ctx.drop_node(node)


class RemoveNodeCommand(Command):
    """
    删除节点（界面会**连带删掉它的连线**）：撤销 = 把节点**和那些连线**一起放回去。

    ★ 状态在**删之前**就采集好（由 `UndoMixin` 做）—— 因为删完对象就取不到了。
    ★ 连线存的是**另一端节点的 uid**（不是对象），所以重建出来的节点能正确接上。
    """

    def __init__(self, uid, state, links, ctx):
        """
        :param uid: 被删节点的 uid（重建时沿用，保持"同一身份"）
        :param state: `(name, pos, params)`，删之前采集
        :param links: `[(另一端节点的 uid, "out"/"in"), …]` —— "out" 表示原节点是起点
        """
        self.ctx = ctx
        self.uid = uid
        self.state = state
        self.links = list(links)
        self.name = state[0] if state else "节点"

    @property
    def text(self):
        return "删除节点「{0}」".format(self.name)

    def do(self):                          # 只在**重做**时走到：把重建出来的节点再删掉
        node = self.ctx.resolve(self.uid)
        if node is not None:
            self.links = self.ctx.capture_links(node)
            self.ctx.drop_node(node)

    def undo(self):
        node = self.ctx.create_node(self.uid, *self.state)
        for other_uid, direction in self.links:
            if direction == "out":
                self.ctx.create_edge(self.uid, other_uid)
            else:
                self.ctx.create_edge(other_uid, self.uid)
        return node


class AddEdgeCommand(Command):
    """新建连线（用户已经连好 ⇒ 首次不执行）：撤销 = 删掉；重做 = 按**两端 uid** 重建"""

    def __init__(self, uid, src_uid, dst_uid, ctx):
        self.ctx = ctx
        self.uid = uid                    # 连线自己的 uid（同样为了"重做时认得出"）
        self.src_uid = src_uid
        self.dst_uid = dst_uid

    text = "新建连线"

    def do(self):
        if self.ctx.resolve_edge(self.uid) is None:
            self.ctx.create_edge(self.src_uid, self.dst_uid, uid=self.uid)

    def undo(self):
        edge = self.ctx.resolve_edge(self.uid)
        if edge is not None:
            self.ctx.drop_edge(edge)


class RemoveEdgeCommand(Command):
    """删除连线（已删 ⇒ 首次不执行）：撤销 = 按两端 uid 重建；重做 = 再删一次"""

    def __init__(self, uid, src_uid, dst_uid, ctx):
        self.ctx = ctx
        self.uid = uid
        self.src_uid = src_uid
        self.dst_uid = dst_uid

    text = "删除连线"

    def do(self):
        edge = self.ctx.resolve_edge(self.uid)
        if edge is not None:
            self.ctx.drop_edge(edge)

    def undo(self):
        self.ctx.create_edge(self.src_uid, self.dst_uid, uid=self.uid)


class SetParamsCommand(Command):
    """
    改参数（参数窗口"确定"提交之后记一条）：undo / redo = 换成另一份**参数字典快照**。

    ★ **必须记住"是哪张图的参数"**（`image_key`）：本项目的运行参数是**按图片分别存档**的
    （`params_per_image[图片键]`），如果撤销时只改"当前那张图"的两处状态，就会出现
    ——"在 A 图上改完参数 → 切到 B 图 → 撤销 → 再切回 A 图"时，A 的存档里还是改后的值，
    参数看起来"撤销没生效"（用户 2026.10.15 实测报的就是这个）。
    """

    def __init__(self, uid, name, before, after, image_key, ctx):
        self.ctx = ctx
        self.uid = uid
        self.name = name or "节点"
        self.image_key = image_key
        self.before = snapshot_params(before)
        self.after = snapshot_params(after)

    @property
    def text(self):
        return "修改「{0}」的参数".format(self.name)

    def do(self):
        self.ctx.apply_params(self.uid, self.after, self.image_key)

    def undo(self):
        self.ctx.apply_params(self.uid, self.before, self.image_key)


class MoveNodeCommand(Command):
    """
    拖动节点（**一次拖动只记一条**：起点 → 终点）。

    `old_pos` / `new_pos` 是宿主给的**不透明坐标对象**（本项目里是 `QPointF`）——
    本文件不 import Qt，只用 `ctx.copy_pos()` / `ctx.move_node(uid, pos)` 去碰它们。
    """

    def __init__(self, uid, name, old_pos, new_pos, ctx):
        self.ctx = ctx
        self.uid = uid
        self.name = name or "节点"
        self.old_pos = ctx.copy_pos(old_pos)
        self.new_pos = ctx.copy_pos(new_pos)

    @property
    def text(self):
        return "移动节点「{0}」".format(self.name)

    def do(self):
        self.ctx.move_node(self.uid, self.new_pos)

    def undo(self):
        self.ctx.move_node(self.uid, self.old_pos)


class MoveNodesCommand(Command):
    """
    ★ 批次6 目标1-M7：一次移动多个节点（多选拖动）—— 撤销一次全部回位。

    items = [(uid, 节点名, 旧坐标, 新坐标), …]；与 MoveNodeCommand 一样只存 uid，
    坐标是宿主给的不透明对象（QPointF），本文件不 import Qt。
    """

    def __init__(self, items, ctx):
        self.ctx = ctx
        self.items = [(uid, name or "节点", ctx.copy_pos(old), ctx.copy_pos(new))
                      for (uid, name, old, new) in items]

    @property
    def text(self):
        return "移动 {0} 个节点".format(len(self.items))

    def do(self):
        for uid, _name, _old, new in self.items:
            self.ctx.move_node(uid, new)

    def undo(self):
        for uid, _name, old, _new in self.items:
            self.ctx.move_node(uid, old)


class UndoStack(object):
    """
    撤销 / 重做栈。

    · `push(cmd, execute=False)`：压一条命令（首次执行已由界面做过）；
    · `undo()` / `redo()`：返回被执行的那条命令（没有可执行的就返回 None）；
    · `limit`：超过就丢**最旧的**（栈底）；
    · 变化回调：`add_changed_callback(fn)` —— `fn(stack)`，用来联动菜单 / 按钮的 `enabled`。
    """

    def __init__(self, limit=UNDO_LIMIT):
        self.limit = int(limit)
        self._done = []
        self._redo = []
        self._callbacks = []

    # ---------------------------------------------------------------- 回调
    def add_changed_callback(self, callback):
        self._callbacks.append(callback)
        callback(self)                     # 立刻同步一次当前状态

    def _notify(self):
        for callback in list(self._callbacks):
            callback(self)

    # ---------------------------------------------------------------- 操作
    def push(self, command, execute=False):
        if execute:
            command.do()
        self._done.append(command)
        del self._redo[:]                  # 新动作一发生，"可重做"的那条链就作废
        if self.limit > 0 and len(self._done) > self.limit:
            del self._done[0]
        self._notify()
        return command

    def undo(self):
        if not self._done:
            return None
        command = self._done.pop()
        command.undo()
        self._redo.append(command)
        self._notify()
        return command

    def redo(self):
        if not self._redo:
            return None
        command = self._redo.pop()
        command.do()
        self._done.append(command)
        self._notify()
        return command

    def clear(self):
        if self._done or self._redo:
            del self._done[:]
            del self._redo[:]
            self._notify()

    # ---------------------------------------------------------------- 查询
    @property
    def can_undo(self):
        return bool(self._done)

    @property
    def can_redo(self):
        return bool(self._redo)

    @property
    def undo_text(self):
        return self._done[-1].text if self._done else ""

    @property
    def redo_text(self):
        return self._redo[-1].text if self._redo else ""

    @property
    def depth(self):
        """还能撤销几步（给用例 / 日志看）"""
        return len(self._done)

    @property
    def redo_depth(self):
        return len(self._redo)


def snapshot_params(params):
    """参数字典的深拷贝（命令里存参数用；避免与节点里的那份共享同一个 dict）"""
    try:
        return copy.deepcopy(dict(params or {}))
    except Exception:
        return dict(params or {})
