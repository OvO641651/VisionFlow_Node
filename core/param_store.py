# -*- coding: utf-8 -*-
"""参数归档（按图片 / 流程级 / per_node 三套口径）

批次5 目标2「拆 `MainWindow`」：**v1 只是把 main.py 里的代码原样搬出来**（方法体一字未改），
由 `main.py` 的 `MainWindow` 多重继承本 Mixin —— `self` 仍是主窗口，方法之间照旧 `self.xxx` 互调。
"""

import os
from core.NodeRegistry import KIND_SOURCE, get_spec, node_level_param_keys
from core.host_contract import MainHost   # ★ 宿主契约（只为静态检查；运行时是空类），见《批次5 技术方案》§11.6

# 视频 / 摄像头帧**整段共用一份参数**用的"视频槽"键（原在 main.py 顶部，批次5 目标2 随参数归档搬来）：
# 参数按图片归档时用它当键，这样一段视频里每帧共用同一份参数（中途改参数、后面的帧按新的跑）。
# ★ main.py 仍然 `from core.param_store import VIDEO_ROI_KEY` 再暴露一次 ——
#   用例里有 `m.VIDEO_ROI_KEY`（dsh_m4_camera_check.py），不能只搬不导出。
VIDEO_ROI_KEY = "video"


class ParamStoreMixin(MainHost):
    """参数归档（按图片 / 流程级 / per_node 三套口径）（批次5 目标2 从 main.py 拆出）"""

    @staticmethod
    def _path_key(path):
        """路径比较用的键（绝对化 + 大小写不敏感），用于"用户删过的图别再自动加回来"这类判断"""
        return os.path.normcase(os.path.abspath(path)) if path else ""

    def _is_removed_path(self, path):
        """这张图是不是被用户在图像列表里主动删掉过"""
        key = self._path_key(path)
        return bool(key) and key in getattr(self, "_removed_paths", set())

    def _image_key_of(self, frame):
        """
        这张图在"参数存档 / 结果缓存 / 缩放记录"里用的标识。

        2026.10.6 起优先用**文件路径**（跨会话稳定，也能写进方案文件让"每图一套参数"持久化）；
        没有路径的（摄像头帧、测试图、测试视频帧）才退回 id(frame)。
        """
        if frame is None:
            return None
        known = self._frame_paths.get(id(frame))
        if known:
            return known
        video = self._video_source_node()
        if video is not None and video.params.get("video_path"):
            # 视频帧：**结果缓存**按"路径#帧号"分开（这样回看得到某一帧的结果，也不会几千帧共用一个键）；
            # 画面缩放/平移走 _display_key_of()（整段共用一个键）——两者刻意分开，别混。
            index = int(video.params.get("frame_index") or 0)
            return "{0}#{1}".format(video.params["video_path"], index)
        return id(frame)

    @staticmethod
    def _node_params_by_image(node):
        """
        取一个节点"按图片存的参数"里**键是文件路径**的那部分（存进方案文件用）。

        id(原图) 这种键跨进程没有意义，所以只导出字符串键（路径 / 视频槽）的那几份。
        """
        store = getattr(node, "params_per_image", None)
        if not isinstance(store, dict):
            return {}
        return {key: dict(value) for key, value in store.items() if isinstance(key, str)}

    def _get_node_params_store(self, node):
        """
        取出某个节点"按图片分别保存的运行参数"字典，没有就现场建一个。
        结构：{图片标识: {参数名: 参数值, ...}}（整份 node.params 的副本）
        """
        store = getattr(node, 'params_per_image', None)
        if store is None:
            store = {}
            node.params_per_image = store
        return store

    def _is_source_node(self, node):
        """
        这个节点是不是"流程起点"（图片源）。

        起点节点的参数（来源 / 路径）属于**流程图本身**，不按图片归档 ——
        否则用户一换图库里的图，图片源的路径就被清空了，它会退回"当前图像"，
        于是"绑了图片源却处理当前图"（和当年"图像源绑定绝不能存进 params"是同一类坑）。
        """
        spec = get_spec(node.name)
        return spec is not None and spec.kind == KIND_SOURCE

    def _is_flow_level_node(self, node):
        """
        这个节点的参数是不是**流程级配置**（不按图片归档）。

        除了起点节点（图片源 / 视频源 / 相机源），输出类节点（"输出图像"，M5，2026.10.7）也一样：
        它的"输出目录 / 文件名"属于**这个节点自己的配置**，跟"当前打开的是哪张图"没有任何关系。
        为什么必须跳过：`_load_node_params()` 是**先 `node.params.clear()` 再载入**，
        如果它跟着图片走，用户一换图（新图名下没有快照）这些参数就被清空了 ——
        和当年"图片源路径被切图清掉"是同一类坑（用户实测报过）。
        """
        spec = get_spec(node.name)
        return spec is not None and spec.is_flow_level

    def _node_level_param_keys(self, node):
        """
        这个节点声明了哪些"**节点级参数**"（不按图片归档，换图 / 换视频 / 换页都保持原样）。

        见 `NodeRegistry.node_level_param_keys()`：现在只有「人脸」的级联文件用它
        （用户 2026.10.12 报："更换图片后级联文件需要重新导入……我希望每幅图都可以使用"）。
        """
        return node_level_param_keys(get_spec(node.name))

    def _save_node_params(self, nodes, image_key):
        """
        把一批节点的当前参数存到某个图片名下。
        :param nodes: 要存的节点列表（一般是某一页流程图里的节点）。
        :param image_key: 图片标识；为 None 表示还没显示过图片/视频，这时不存。
        """
        if image_key is None:
            return
        for node in nodes:
            if self._is_flow_level_node(node):
                # 流程级配置（起点节点 / 输出节点）不参与按图片归档，见 _is_flow_level_node
                continue
            store = self._get_node_params_store(node)
            # ★ 节点级参数（比如人脸的级联文件）**不进图片槽**：它跟"当前是哪张图"无关，
            #   存进去只会在每张图下面重复一份；它一直留在 node.params 里（见 _load_node_params），
            #   也会跟着"当前图那一份"一起写进方案文件。
            keep_out = self._node_level_param_keys(node)
            snapshot = {key: value for key, value in node.params.items() if key not in keep_out}
            # 空字典不存：既省内存，也避免往 params 里灌 None 导致后面切片报错
            if snapshot:
                store[image_key] = snapshot

    def _load_node_params(self, nodes, image_key):
        """
        把一批节点的参数换成某个图片名下的那一份。
        :param nodes: 要换参数的节点列表（一般是某一页流程图里的节点）。
        :param image_key: 图片标识。
        """
        for node in nodes:
            if self._is_flow_level_node(node):
                # 流程级配置（起点节点 / 输出节点）不跟着图片走，切图时保持原样
                continue
            store = self._get_node_params_store(node)
            # ★ 节点级参数：`clear()` 之前先留一份，载入之后再放回去 ——
            #   否则一换图就会把"级联文件"这种配置清掉（用户 2026.10.12 实测报的 bug：
            #   "更换图片后级联文件需要重新导入，可能是每幅图片的参数设置会重置导致"）。
            kept = {key: node.params[key] for key in self._node_level_param_keys(node)
                    if key in node.params}
            # 先清空：这张图片以前没设置过的话，就保持空，
            # 各处的 .get(参数名, 默认值) 会自动取默认值（ROI 的默认宽高就是当前这张图的尺寸）
            node.params.clear()
            snapshot = store.get(image_key)
            if snapshot:
                node.params.update(snapshot)
            node.params.update(kept)

    def _switch_image_params(self, new_key):
        """
        切换当前图片时，把"当前这一页"每个节点的运行参数按图片分别存档 / 载入。

        存档的是节点参数的全部内容：ROI 的 XYHW / XYR（含形状、是否隐藏黄框），以及运行参数，所以每张图片的参数完全独立，互不继承。。

        :param new_key: 新图片的标识。静态图片用 id(原图)，视频/摄像头用 VIDEO_ROI_KEY。
        """
        if new_key == self.current_image_key:
            # 还是同一张图片
            return

        # 1、先把当前页每个节点的参数存到上一张图片名下（只处理"当前页"的节点）
        self._save_node_params(self.flow_nodes, self.current_image_key)

        # 2、再按新图片取参数（这张图片没设置过就会是空，各处自动用默认值）
        #    注意：如果之前还没有关联任何图片 / 视频（current_image_key 是 None），
        #    说明用户是在"还没开图"的时候就把参数设好了（比如先双击节点调好 ROI 再打开图片），
        #    这份参数要留给新图片当初始值，不能在这里清掉——否则刚设好的 ROI 会凭空消失。
        if self.current_image_key is not None:
            self._load_node_params(self.flow_nodes, new_key)

        self.current_image_key = new_key