# -*- coding: utf-8 -*-
"""执行入口与数据流引擎 + 渲染显示 + 显示键

批次5 目标2「拆 `MainWindow`」：**v1 只是把 main.py 里的代码原样搬出来**（方法体一字未改），
由 `main.py` 的 `MainWindow` 多重继承本 Mixin —— `self` 仍是主窗口，方法之间照旧 `self.xxx` 互调。
"""

from collections import deque  # 拓扑排序要用到的队列（数据流引擎按连线顺序执行）
from PySide2 import QtWidgets
from PySide2.QtGui import QBrush, QColor  # QIcon设置图标，QImage显示图像；QBrush/QColor 给日志红字用（目标5-M2）
import cv2
import time
import os
from core.NodeRegistry import KIND_SINK, KIND_SOURCE, SOURCE_KEY, get_spec, is_bound_node, result_bbox
from core.ParamRules import run_validation
from ops.sink.OutputOps import SAVE_OVERLAY, SOURCE_CAMERA, SOURCE_IMAGE, SOURCE_VIDEO, close_all_recordings, set_input_name_provider, set_overlay_frame_provider, set_round_info_provider
from core.param_store import VIDEO_ROI_KEY
from core.host_contract import MainHost   # ★ 宿主契约（只为静态检查；运行时是空类），见《批次5 技术方案》§11.6
from core.result_cache import evict as _evict_result_cache, touch as _touch_result_cache  # ★ 目标4：两池 LRU


class FlowEngineMixin(MainHost):
    """执行入口与数据流引擎 + 渲染显示 + 显示键（批次5 目标2 从 main.py 拆出）"""

    def _show_static_image(self, frame):
        """
        显示一张静态图片（导入图片、点击图库缩略图切换图片时调用）。
        规则：
            这张图片之前点过"单步执行"/"连续执行" -> 直接显示它上一次的检测结果，不用再点执行按钮；
            这张图片还没执行过 -> 只显示原图，不显示任何检测结果。
        另外，切换图片时会把每个节点的运行参数（ROI + 算法参数）按图片分别存档 / 载入，
        所以每张图片的参数也是独立的。

        :param frame: OpenCV BGR 原图（内部只用副本，不会污染原图）。
        """
        if frame is None:
            return

        # 记住当前图片，后面点执行按钮都是基于它计算
        self.current_static_image = frame

        # 切换图片：把每个节点的运行参数按图片分别存档 / 载入
        # （标识优先用文件路径，见 _image_key_of：跨会话稳定、能写进方案文件）
        image_key = self._image_key_of(frame)
        self._switch_image_params(image_key)

        # 取"这张图片 × 这一页流程图"上一次的执行结果：
        # 优先取连续执行（整条流程，画面和日志表最完整），没有连续结果时才取单步执行的
        cache_key = self._result_cache_key(image_key, "continuous")
        cached = self.result_cache.get(cache_key)
        if cached is None:
            cache_key = self._result_cache_key(image_key, "step")
            cached = self.result_cache.get(cache_key)
        if cached is not None:
            # ★ 批次5 目标4：**命中缓存 = "用过一次"** ⇒ 把它移到最新（真 LRU；少了这步就是 FIFO 近似，
            #   "刚看过的图照样被淘汰"，用户 2026.10.15 拍板要修的就是这个）。
            _touch_result_cache(self.result_cache, cache_key)
            # 有缓存：直接显示上次画好检测结果的那张图
            self._display_image(cached["frame"], image_key)
            # 顺便把"上次检测数据"和日志表格也同步过来，保证和画面对得上
            self.last_detected_data = cached["data"]
            self._update_execution_log(cached["exec_info"] or [])
            return

        # 没有缓存（这张图片还没执行过）：只显示原图
        self._display_image(frame.copy(), image_key)

        # 没执行过就没有检测结果，把上一次的数据和日志一并清空
        self.last_detected_data = None
        self._update_execution_log([])

    def _result_cache_key(self, image_key, mode):
        """
        检测结果缓存的键 = 图片 × 流程图页面 × 执行方式。
        这样同一张图片在不同流程图页面上的执行结果各自独立，
        并且**单步执行的结果不会把整流程执行的结果覆盖掉**。
        :param mode: "step" 单步执行；"continuous" 连续执行
        """
        return (image_key, self.flow_page_mgr.page_key(), mode) # type:ignore

    def _execute_static(self, frame, mode, node=None, adopt_frame=True, show=True):
        """
        对一张静态图片执行检测并把结果显示出来。
        只有"单步执行"、"连续执行"两个按钮会调用它。
        执行完会把结果按图片缓存起来（见 self.result_cache），
        以后再切回这张图片时可以直接显示这次的结果，不用再点按钮。

        :param frame: OpenCV BGR 原图。
        :param mode: "step" 单步执行（跑 node 及其上游）；"continuous" 连续执行（跑整个流程图）。
        :param node: 单步执行时要执行的节点。
        :param adopt_frame: 是否把这一帧记成"当前静态图片"。
               从"打开的图片 / 图库 / 视频"来的帧传 True（老行为）；
               从**图片源节点兜底**来的帧传 False——它只是"这一轮驱动流程用的帧"，
               不该篡改"主窗口当前打开的是哪张图"（否则用户换了图片源的文件、
               再点执行时还会拿旧的那张，用户实测报过这个问题）。
        :param show: 要不要把处理后的图画到画布上。默认 True（单步 / 连续执行都要看结果）；
               **"运行全部"在没勾「自动切换」时传 False** —— 那时只算不显示（用户 2026.10.15 要求：
               不勾自动切换画布就不该动），结果照旧进缓存、日志照旧逐张写。
        :return: 检测到的数据列表 data。
        """
        if adopt_frame:
            # 保证"当前静态图片"就是这次要算的图，后面再点执行按钮时用的还是它
            self.current_static_image = frame

        # 复制图像处理，防止污染原图
        work_frame = frame.copy()

        if mode == "continuous":
            # 调用连续执行_run_flow_pipeline，接收返回的 data 和日志 exec_info
            # stop_at = 当前选中的节点：连续执行只跑到它为止（用户 2026.10.7 定的语义）
            work_frame, data, exec_info = self._run_flow_pipeline(
                work_frame, stop_at=self.selected_node)
        else:
            # 调用单步执行_run_flow_pipeline_step，只执行 node 这一个节点
            # （单步执行现在也会返回一行日志，否则"画面有结果、日志表却是空的"）
            work_frame, data, exec_info = self._run_flow_pipeline_step(work_frame, node)

        # 更新执行日志表格：单步 / 连续都走这里
        self._update_execution_log(exec_info)

        # 显示处理后的图像；传图片标识让每张图片的缩放互相独立
        # （缓存键用 _image_key_of；画面键用 _display_key_of —— 视频帧/相机帧的画面键整段共用）
        # ★ `show=False` 时**只算不显示**："运行全部"在**没勾「自动切换」**时就是这么用的 ——
        #   用户 2026.10.15 报的问题："不选自动切换，画布也会自动播放处理后的图片、最后再切回选中的那张"。
        #   不刷画布不影响正确性：结果照旧进缓存（切回那张图仍能看到）、日志照旧逐张写。
        image_key = self._image_key_of(frame)
        camera_used = self._camera_used_by(node, mode)
        display_key = self._camera_display_key(node, mode) if camera_used else None
        if show:
            self._display_image(work_frame, display_key or self._display_key_of(frame))

        # ★ 相机帧**不进结果缓存**（用户 2026.10.7 定）：相机是无界流，每一帧都是新内容，
        #   缓存既没有"切回来还能看到上次结果"的意义，又会让内存随运行时间线性增长。
        if not camera_used:
            # 把这次的结果缓存到"这张图片 × 这一页流程图 × 本次执行方式"名下
            # 下次切回这张图片（或这一页）时可以直接显示，不用再点一次执行按钮。
            # work_frame 本来就是 frame 的独立副本，直接存起来即可。
            self.result_cache[self._result_cache_key(image_key, mode)] = {
                "frame": work_frame,
                "data": data,
                "exec_info": exec_info,
            }
            # ★ 批次5 目标4：写完就按上限淘汰一次（**两池 LRU**：静态图一池、视频逐帧一池，各按"条数 + 字节"双上限）。
            #   旧版只有视频分支里那段"超过 400 条丢最旧"⇒ ① 静态图批量跑其实**没有上限**；
            #   ② 而且是 FIFO 近似（命中不刷新顺序）。实现见 `core/result_cache.py`。
            _evict_result_cache(self.result_cache)

        # 保存数据并同步窗口
        self.last_detected_data = data  # 保存给以后打开的窗口使用
        if self.current_dialog and self.current_dialog.isVisible():
            self.current_dialog.update_result_count(data)

        # 图片源节点用到的图片也放进图库列表（用户 2026.10.5 要求：不管是"打开文件"导入的，
        # 还是图片源节点指定的，都要在图库里看得见）
        self._ensure_source_images_in_gallery()
        # 相机源（目标3-M4，2026.10.7）：相机是**无界流**——
        #   · 没有帧游标可以推进（视频那套 "一次执行 = 前进一帧" 不适用）；
        #   · 参数**复用视频槽**（用户定："相机和视频共用一份参数"），跑完把这份存回槽里；
        #   · 勾了"自动切换"就接着自动出画面（走 _maybe_start_video_playback 里分派的那条相机分支）。
        if self._camera_used_by(node, mode):
            self._save_node_params(self.flow_nodes, VIDEO_ROI_KEY)
            self._maybe_start_video_playback(node, mode)
        # "一次执行 = 前进一帧"（用户 2026.10.6 定）：这一轮真的用到视频源的话，把帧号 +1。
        # 放在"执行结束"这里而不是 run() 里，是为了让同一轮里多个节点共用同一帧。
        if self._video_used_by(node, mode):
            self._advance_video_cursor()
            # 视频的**参数整段共用一份**（用户 2026.10.6 定的语义）：跑完把当前这份参数存进"视频槽"
            # （VIDEO_ROI_KEY，模块顶部已定义），这样切去别的图、再切回来点视频执行时，参数不会被清空。
            self._save_node_params(self.flow_nodes, VIDEO_ROI_KEY)
            # （结果缓存的上限已挪到 `_execute_static` 写完缓存处统一做 —— 见 `core/result_cache.py`：两池 LRU，
            #   不再只对视频路径生效，也不再是"命中不刷新顺序"的 FIFO 近似。）
            # 勾了"自动切换"时：这一轮结束后**接着自动播放**（用户 2026.10.6 要求：
            # "点自动切换后再点执行，视频会转成自动播放，不用一帧一帧点；点停止就停"）。
            self._maybe_start_video_playback(node, mode)

        return data

    def _display_image(self, img, image_key=None):
        """
        将 OpenCV 图像转换并渲染到 UI 的 QGraphicsView 上
        :param image_key: 静态图片的标识（用 id(原图) 传入）。
                          传入后这张图片的缩放 / 平移会被单独记住，各图片互不影响；
                          不传（视频 / 摄像头的连续帧）时保持当前缩放不变。
        """
        if not hasattr(self, 'image_view'):
            return
        # 直接调用自定义视图 ImageGraphicsView 类的 set_image 方法，无需手动缩放
        self.image_view.set_image(img, image_key)

    # ------------------------------------------------------------------
    # 执行入口（UI 上所有"单步执行 / 连续执行"都从这里走）
    # ------------------------------------------------------------------
    def _source_node_frame(self, allow_camera_open=False):
        """
        当前页面里"图像源类节点"这一轮能给出的图（没有就返回 None）。

        只用于兜底：图库为空、也没打开任何图时，只要流程里放了"图片源"并指定了图片
        （或选了测试图），点执行照样能跑——跑的就是它那张图。

        :param allow_camera_open: 轮到"相机源"时，要不要**顺手把相机打开**。
                只有执行路径（`_flow_source_frame()`）传 True。
                为什么需要它（用户 2026.10.7 实测报的 bug）：画布上只有"相机源"、而且**没连线**时，
                `_ensure_camera_open_for_run()` 的判据是"这一轮真用到相机源"（要有一条下游连线）
                ⇒ 判成"没用到" ⇒ 设备压根没开 ⇒ 这里问它要图只能拿到 None ⇒ 点"连续执行"
                会弹"请先导入图片/视频…"，而点"单步执行"（选中相机源，走了 `_camera_used_by` 的
                `node is camera` 分支）却正常 —— 两条入口表现不一致，就是这里漏的。
                改成"走到相机源这一项、真要向它取图时再开"，判据就从"有没有连线"变成"是不是轮到它取图"。
        """
        for node in list(self.flow_nodes):
            spec = get_spec(node.name)
            if spec is None or spec.kind != KIND_SOURCE:
                continue
            if allow_camera_open and node is self._camera_source_node():
                # 轮到相机源取图了：先把设备准备好（已经开着同一编号就复用；用户关掉了
                # "执行时自动打开相机"就不开，那样这里问它要图只会拿到 None，由调用方如实提示）
                self._ensure_camera_device_open(node)
            try:
                # 图像源节点不看传入的图与 ROI（"当前图像"这个来源会把传入的 None 原样返回）
                frame, _results = spec.run(self.detector, None, (0, 0, 0, 0), node.params)
            except Exception:
                frame = None
            if frame is not None:
                return frame
        return None

    def _flow_source_frame(self):
        """
        决定"这一轮流程从哪张帧开始跑"（只决定**全局图像源**那一帧；绑到图片源 / 上游节点的
        节点各自按自己的绑定取图，见 _run_nodes）：
            ① 主窗口已经打开图片 / 视频 / 摄像头 → 就用它（老行为一个字不变）；
            ② 都没有，但当前页面里有图像源节点能给出图 → 用那张图兜底（图库为空也能跑）；
            ③ 什么都没有 → 返回 (None, 提示语)，由调用方弹提示。
        :return: (frame, 提示语, 这一帧是不是"图片源兜底"来的)
        """
        if self.current_static_image is not None:
            return self.current_static_image, "", False
        # 允许"走到相机源时顺手开设备"：画布上只有相机源、又没连线时，这一步就是唯一能开相机的时机
        frame = self._source_node_frame(allow_camera_open=True)
        if frame is not None:
            return frame, "", True
        return None, "请先导入图片/视频、打开摄像头，或者在流程图里放一个“图片源”/“视频源”/“相机源”节点并给它指定图片 / 视频 / 相机编号！", True

    def _build_execution_order(self, nodes, edges):
        """
        按连线做拓扑排序（Kahn 算法），顺便整理出每个节点的上游列表。

        为什么不能再用原来的"队列广度优先"：
            广度优先在多上游时会乱序。比如连线是 A→D、B→C、C→D，
            队列里 D 可能排在 C 前面，D 执行时上游 C 还没算，数据流就取不到输入图像。

        :param nodes: 这一页流程图上的所有方框
        :param edges: 这一页流程图上的所有连线
        :return: (order, parents, skipped)
                 order   本次要执行的节点，父节点一定排在子节点前面
                 parents {节点: [上游节点, ...]}
                 skipped 不参与执行的节点（孤立的，或者落在环里的）
        """
        children = {node: [] for node in nodes}
        parents = {node: [] for node in nodes}
        in_degree = {node: 0 for node in nodes}

        for edge in edges:
            start = edge.start_node
            end = edge.end_node
            if start not in children or end not in in_degree:
                # 连线的某一端已经不在这一页的方框表里（理论上不会发生）
                continue
            children[start].append(end)
            parents[end].append(start)
            in_degree[end] += 1

        # 起点 = 没有上游、并且有下游。孤零零一个方框不执行（沿用 2026.6.28 定下的约定）
        queue = deque([node for node in nodes if in_degree[node] == 0 and children[node]])
        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for child in children[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    # 它的上游全都排好队了，这才轮到它
                    queue.append(child)

        done = set(order)
        skipped = [node for node in nodes if node not in done]
        return order, parents, skipped

    def _upstream_closure(self, node, parents):
        """
        收集"这个节点 **+ 它的全部上游**"（沿 parents 往上走，含自己）。

        连续执行的执行范围就用它（见 `_run_nodes()` 里那段说明）。为什么不用"拓扑序前缀"：
        前缀会把**排在选中节点前面、却与它毫无关系**的分支也一起跑掉。
        :param parents: `_build_execution_order()` 给的 {节点: [上游节点, ...]}
        :return: set（元素是节点对象，可直接 `node in result`）
        """
        seen = set()
        stack = [node]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            for parent in parents.get(current, []) or []:
                if parent not in seen:
                    stack.append(parent)
        return seen

    def _node_modifies_image(self, node):
        """
        这个节点会不会改写数据层图像？
        用来在多上游时挑出"真正产出新图像"的那一支（读的是节点契约里的 kind 声明）。
        """
        spec = get_spec(node.name)
        return spec is not None and spec.modifies_image

    def _resolve_input(self, node, parents, out_images):
        """
        决定这个节点从哪一份图像开始算（数据流引擎的"图像源"绑定）。

        优先级：节点上手动绑定的图像源 > 自动（取最后一个上游）。
        "自动"里的"最后一个"是按连线顺序取的，是确定的，所以同一张流程图每次跑结果一致。

        :param out_images: {图像源标识: 图像输出}，本轮已经产出的图像
        :return: (源标识, 给日志看的来源说明)
                 源标识是 NodeRegistry.SOURCE_KEY（全局图像源）或者某个上游节点对象
        """
        binding = getattr(node, 'input_source', None)
        if isinstance(binding, str) and binding == SOURCE_KEY:
            # 绑的是"全局图像源"
            return SOURCE_KEY, "全局图像源"

        if binding is not None and binding in out_images:
            return binding, "节点：{0}".format(binding.name)

        note = ""
        if binding is not None:
            # 绑定的节点本轮没执行（被删掉了 / 不属于这一页），退回自动
            note = "（原绑定已失效，自动回退）"

        if parents:
            source = parents[-1]
            label = "节点：{0}".format(source.name)
            if len(parents) > 1:
                # 多上游时优先挑"处理类"的上游：只有它会产出新的图像数据
                # （检测类算子的输出图像就是它的输入，等于什么都没改）。
                # 这样"图像源 -> 灰度 -> 圆"和"直线 -> 圆"同时存在时，
                # 圆默认接在灰度后面，而不是接到那条没改图的直线上。
                image_parents = [p for p in parents if self._node_modifies_image(p)]
                if image_parents:
                    source = image_parents[-1]
                    label = "节点：{0}（多上游，自动取最后一个改图的上游）".format(source.name)
                else:
                    label += "（多上游，自动取最后一个）"
            return source, label + note
        return SOURCE_KEY, "全局图像源" + note

    def _resolve_roi(self, node, img_shape, in_results, in_roi=None):
        """
        算出这个节点真正要处理的 ROI，两种来源：

            1、ROI创建 = "继承上游"：具体继承什么由 params["roi_source"] 决定
                 · "roi"（默认）：直接沿用上游那一轮实际用的 ROI 框（in_roi）——
                   框固定、逐级一致，不受上游检出几个目标、目标跑到哪儿的影响；
                 · "result"：把上游结果（直线端点 / 圆心半径）算成外接框 ——
                   目标动、框跟着动，就是"结果数据流"；
               两种都再向外扩 roi_margin 像素（默认 0 = 与上游完全重合）。
               首选那种拿不到时（单步执行没有 in_roi、或者上游是处理类算子没有结果数据）
               会自动退回另一种，实在什么都没有才用本节点手画的 ROI；
            2、其余情况：用参数里的 roi_x / roi_y / roi_w / roi_h
               （这张图片还没设置过时，默认就是整幅图），并统一裁剪到图像范围内。

        :param in_roi: 输入源那个节点这一轮实际用的 ROI（roi_info 元组），供"继承 ROI 框"用
        :return: (roi_x, roi_y, roi_w, roi_h, roi_shape, inherited)
                 inherited = ""       这块 ROI 不是继承来的（用的是本节点参数）
                             "roi"    沿用上游那一轮实际用的 ROI 框
                             "result" 用上游"检测结果"的外接框
        """
        params = node.params
        roi_shape = params.get("roi_shape", "矩形")
        img_h = img_shape[0]
        img_w = img_shape[1]

        # 算子声明了"整图模式参数"并且已经打开时（目前是灰度的 gray_full_image），
        # ROI 一律当成整幅图 —— 算法本身也是按整图处理的，这样日志和 ROI 框才与事实一致。
        spec = get_spec(node.name)
        whole_key = getattr(spec, 'whole_image_param', None) if spec is not None else None
        if whole_key and params.get(whole_key, False):
            return 0, 0, img_w, img_h, roi_shape, ""

        # 默认就是"继承上游"（2026.10.5 用户要求把缺省从"绘制"改成"继承上游"）；
        # 方案里明确存过 False 的节点才走"用本节点参数里的 ROI"那条路。
        if params.get("roi_inherit", True):
            margin = int(params.get("roi_margin", 0))
            source = params.get("roi_source", "roi")     # 默认：继承上游那一轮用的 ROI 框
            bbox = None
            inherited = ""
            if source == "roi":
                # 默认做法：直接沿用上游那一轮实际用的框（框固定、逐级一致）
                if in_roi is not None and in_roi[2] > 0 and in_roi[3] > 0:
                    bbox = (in_roi[0], in_roi[1], in_roi[2], in_roi[3])
                    inherited = "roi"
                else:
                    # 上游这一轮没执行（单步执行）、或者输入源就是全局图像源：
                    # 退回"上游检出的结果外接框"
                    bbox = result_bbox(in_results)
                    if bbox is not None:
                        inherited = "result"
            else:
                # "上游结果框"（roi_source = result）：用上游检出目标的最小外接框（目标动、框跟着动）
                bbox = result_bbox(in_results)
                if bbox is not None:
                    inherited = "result"
                elif in_roi is not None and in_roi[2] > 0 and in_roi[3] > 0:
                    # 上游是处理类算子（比如灰度）、没有结果数据：退回继承它用的框
                    bbox = (in_roi[0], in_roi[1], in_roi[2], in_roi[3])
                    inherited = "roi"
            if bbox is not None:
                left = max(0, int(round(bbox[0])) - margin)
                top = max(0, int(round(bbox[1])) - margin)
                right = min(img_w, int(round(bbox[0] + bbox[2])) + margin)
                bottom = min(img_h, int(round(bbox[1] + bbox[3])) + margin)
                if right > left and bottom > top:
                    return left, top, right - left, bottom - top, roi_shape, inherited
            # 上游既没有结果、也没有可继承的处理区域（比如单步执行，或者输入源就是全局图像源）：
            # 自动退回参数里的 ROI，免得整个节点因为 ROI 尺寸为 0 被跳过

        roi_x = int(params.get("roi_x", 0))
        roi_y = int(params.get("roi_y", 0))
        roi_w = int(params.get("roi_w", img_w))
        roi_h = int(params.get("roi_h", img_h))

        # 统一裁剪到图像范围内（这里必须裁）：
        # numpy 的切片越界时不会报错，而是"静默变空"——一张 0 像素的空图丢给
        # cv2.cvtColor / Canny / HoughCircles 会直接抛异常。
        # 老代码是靠 roi_img.size == 0 兜住的，现在从源头裁掉，
        # 顺便让日志和黄色 ROI 框显示的就是真正参与计算的那块区域（所见即所算）。
        roi_x = max(0, min(roi_x, img_w))
        roi_y = max(0, min(roi_y, img_h))
        roi_w = max(0, min(roi_w, img_w - roi_x))
        roi_h = max(0, min(roi_h, img_h - roi_y))
        return roi_x, roi_y, roi_w, roi_h, roi_shape, ""

    def _execute_node(self, node, in_img, in_results, in_roi=None):
        """
        执行一个节点（节点契约的执行侧）。

        :param in_img: 数据层输入图像（按"图像源"绑定取到的那一份）
        :param in_results: 输入源那个节点的结果数据，供"ROI 继承"用
        :param in_roi: 输入源那个节点这一轮实际用的 ROI（上游是处理类算子、没有结果时用它）
        :return: (out_img, results, roi_info, spec)
                 out_img  这个节点的图像输出，会被下游当成图像源；
                          检测类算子是原样透传（同一个对象，不复制）
                 results  这个节点产出的结果数据（原图坐标）
                 roi_info (x, y, w, h, hide, shape, inherited)
                 spec     节点能力声明；None 表示这个模块还没实现
        """
        spec = get_spec(node.name)
        roi_x, roi_y, roi_w, roi_h, roi_shape, inherited = self._resolve_roi(
            node, in_img.shape, in_results, in_roi)
        hide_roi = node.params.get("hide_roi", False)
        roi_info = (roi_x, roi_y, roi_w, roi_h, hide_roi, roi_shape, inherited)

        if roi_w <= 0 or roi_h <= 0 or spec is None:
            # roi_w / roi_h 为 0 时跳过：_resolve_roi() 已经把 ROI 裁进图像范围了，
            # 所以"整块 ROI 落在图外"或"参数里填了 0"都会走到这里，图像原样往下传；
            # spec 为 None（注册表里没登记的模块名）也一样透传，
            # 日志里如实写"模块未实现"，不再假装"执行成功"。
            return in_img, [], roi_info, spec

        # ★ 参数校验（批次4 目标4）：**真要跑这个算子之前**再查一遍。
        #   位置放在"ROI 尺寸为 0 已跳过"之后 ⇒ 两个跳过原因不会重复写进同一行日志。
        #   · 能安全纠正的（Canny 高低互换、核大小取奇数、阈值夹范围…）：就地改 node.params，
        #     说明存进 _param_corrections，由 _format_result_text 追到执行日志末尾；
        #   · 纠正不了的（errors 非空）：跳过本节点 —— 图像原样透传 + 用 __note__ 递一句文案，
        #     **绝不弹窗、绝不把异常抛出去**（异常在 Qt 槽里会被吞掉，用户只会看到"点了没反应"）。
        fixed, corrections, errors = run_validation(spec, node.params)
        if fixed != node.params:
            node.params.update(fixed)
        if corrections:
            self._param_corrections[id(node)] = corrections
        if errors:
            return in_img, [{"__note__": "参数非法（{0}），已跳过本节点".format("；".join(errors))}], \
                roi_info, spec

        out_img, results = spec.run(self.detector, in_img, (roi_x, roi_y, roi_w, roi_h), node.params)
        if out_img is None:
            # 万一某个算子忘了返回图像，就当它不改图像，保证下游还有图可用
            out_img = in_img
        if spec.kind == KIND_SOURCE:
            # 起点节点（图片源）没有"处理区域"这个概念：它的有效 ROI 就是**它自己输出的整张图**。
            # 这样 ① 画面上不会出现一个莫名其妙的黄框（用户实测到过"512×512 的怪框"——
            # 那是对话框把主窗口当前图的尺寸写进了 ROI 参数留下的）；② 下游"继承上游 ROI"
            # 拿到的是整张图，而不是那个过时的尺寸。
            out_h, out_w = out_img.shape[:2]
            roi_info = (0, 0, out_w, out_h, True, roi_shape, "")
        return out_img, results, roi_info, spec

    def _format_result_text(self, node, results, roi_info, spec):
        """执行日志"结果数据"那一列的文案：由节点注册表提供，新增算子不用改这里"""
        # ★ 参数非法被跳过时，results 里带着一句 __note__（批次4 目标4）：直接用它当文案，
        #   不要再去问算子的 format_result —— 那个节点根本没跑起来。
        note = _result_note(results)
        if note:
            # ★ 出错的行（比如"未选择级联文件"）加一个标记，_update_execution_log() 见到它就涂红
            return (LOG_ERROR_MARK + note) if _result_error(results) else note
        if roi_info[2] <= 0 or roi_info[3] <= 0:
            return "ROI 尺寸为 0，已跳过（图像原样传给下游）"
        if spec is None:
            return "模块未实现，图像原样传给下游"
        text = spec.format_result(results)
        # 缺省也是"继承上游"（2026.10.5 起），所以这里要用 True 兜底，
        # 否则默认继承的节点不会把"继承到没继承到"写进日志，用户就看不出来了。
        if node.params.get("roi_inherit", True):
            # 勾了"继承上游"之后到底继承到了什么，必须让用户看见（否则会以为继承生效了）。
            # 注意：单步执行 / 视频每帧都会走到这里，所以只能用日志文案、不能弹窗；
            # 文案也要尽量短——"结果数据"那一列显示不全会被截断。
            if roi_info[6] == "roi":
                text += "  ← 继承上游ROI框"
            elif roi_info[6] == "result":
                text += "  ← 继承上游结果框"
            else:
                text += "  ← 继承未生效（改用本节点 ROI）"
        # ★ 这一轮这个节点的参数被自动纠正过（批次4 目标4）：追一句短说明。
        #   不写的话用户会以为"我填的就是生效值"，而这恰恰是目标4 要消灭的"静默"。
        corrections = getattr(self, "_param_corrections", {}).get(id(node)) or []
        for line in corrections:
            text += "  ← 已自动纠正：{0}".format(line)
        return text

    def _render_display(self, base_img, executed, draw_roi=True):
        """
        渲染层：把数据层的图像复制一份，再按执行顺序把各节点的结果和 ROI 框画上去。

        这里画的所有东西都只活在这张显示图上，永远不会回流到数据层，
        所以下一个节点执行时看不到上一个节点画的绿线 / 红圆。

        :param base_img: 数据层底图（取最后一个执行节点的图像输出）
        :param executed: [(节点, 结果, roi_info, spec), ...]，按执行顺序
        :param draw_roi: 要不要把 ROI 黄框 / 洋红框也画上。
                屏幕上要（方便调参）；**"输出图像"节点存"带检测叠加"时不要** ——
                那是辅助线，存进文件里没意义（用户 2026.10.7 要求存的是"检测的内容"）。
        :return: 可以直接显示的图像
        """
        display = base_img.copy()
        rois_to_draw = []

        for node, results, roi_info, spec in executed:
            if results and spec is not None and spec.draw is not None:
                # 检测类算子的结果画到显示层
                spec.draw(display, results, node.params)
            if spec is not None and spec.kind == KIND_SOURCE:
                # 起点节点（图片源）没有"处理区域"，不画它的 ROI 框——
                # 否则画面上会出现一个跟检测毫无关系、还可能是过时尺寸的框（用户实测反馈过）
                continue
            rois_to_draw.append(roi_info)

        # 结果全部画完之后再统一画 ROI 框，避免黄框被后面的算法当成图像内容
        if draw_roi:
            for rx, ry, rw, rh, hide, roi_shape, inherited in rois_to_draw:
                if hide:
                    continue
                # 继承来的 ROI 用洋红色，和手动画的黄色区分开，一眼能看出这块是从上游结果来的
                color = (255, 0, 255) if inherited else (0, 255, 255)
                if roi_shape == "圆":
                    cv2.circle(display, (rx + rw // 2, ry + rh // 2), rw // 2, color, 2)
                else:
                    cv2.rectangle(display, (rx, ry), (rx + rw, ry + rh), color, 2)

        return display

    def _run_flow_pipeline(self, frame, stop_at=None):
        """
        连续执行：按连线做拓扑排序，让图像数据顺着连线在各模块之间流动。

        数据层：out_images[图像源] —— 每个节点执行完都会留下一份"图像输出"，
                下游节点的"图像源"绑定到谁，就取谁那一份；
                全局图像源（NodeRegistry.SOURCE_KEY）就是最初那一帧的副本。
        渲染层：_render_display() 最后统一画，不参与任何算法。

        :param frame: OpenCV BGR 原图（内部只用副本，不会污染原图）
        :param stop_at: **执行范围 = 它 + 它的全部上游**（决策 e，目标5-M1）；None = 跑完整条。
                连续执行的入口（按钮 / 摄像头老预览）传 self.selected_node ——
                用户 2026.10.7 先定"连续执行 = 选中哪个节点就执行到那个节点，不再往下执行"，
                2026.10.7 深夜（目标5-M1）把范围精确成"**上游链**"：
                与选中节点无关的分支不再执行（连带"输出图像"不会在无关分支里悄悄存文件）。
        :return: (显示用图像, 所有节点结果汇总, 执行日志列表)
        """
        img = frame.copy()              # 全局图像源（数据层的起点）
        if not self.flow_nodes:
            # 画布上一个方框都没有，没什么可执行的
            return img, [], []

        # 拓扑排序：父节点一定排在子节点前面
        order, parents, skipped = self._build_execution_order(self.flow_nodes, self.flow_edges)
        if not order:
            # 有方框，但一条能跑的链路都没有：给一行提示，而不是静默什么都不做
            return img, [], [("-", time.strftime("%H:%M:%S"), "提示", "-",
                              "没有可执行的流程：请先用连线把模块连起来")]
        # 真正的执行 + 渲染都在 _run_nodes 里：
        # 连续执行 = 选中节点 + 它的上游（其余不跑）；单步执行 = 只跑选中的那一个节点（见 _run_flow_pipeline_step）
        return self._run_nodes(order, parents, img, skipped, stop_at=stop_at)

    def _parent_nodes(self, node):
        """
        当前页面里直接连到 node 的上游节点（按连线顺序）。
        "图像源 = 自动"时引擎取最后一个上游（见 _resolve_input），这里保持一致。
        """
        parents = []
        for edge in self.flow_edges:
            if edge.end_node is node and edge.start_node in self.flow_nodes:
                parents.append(edge.start_node)
        return parents

    def _node_input_frame(self, node, _depth=0):
        """
        这个节点这一轮**实际会收到的图**——沿着它声明的"图像源"往上追到起点。

        对话框用它来取"上游整张图"的尺寸当 ROI 宽高默认值
        （老实现只看主窗口当前那张图，所以"绑了图片源"的下游节点，ROI 默认尺寸
        和上游图片源那张图对不上——用户实测反馈过）。

        :return: BGR 图；追不到返回 None
        """
        if node is None or _depth > 20:
            return None
        # 起点节点（图片源）自己就是图的来源：直接问它要图，别去问"主窗口当前图"
        spec = get_spec(node.name)
        if spec is not None and spec.kind == KIND_SOURCE:
            frame, _results = spec.run(self.detector, None, (0, 0, 0, 0), node.params)
            return frame
        binding = getattr(node, "input_source", None)
        if is_bound_node(binding):
            # 绑到了某个上游节点：继续往上追（处理类不改图像尺寸，追到起点就够）
            return self._node_input_frame(binding, _depth + 1)
        if isinstance(binding, str) and binding == SOURCE_KEY:
            return self.current_static_image if self.current_static_image is not None \
                else self._source_node_frame()
        # "自动"（没显式绑定）：跟引擎一样取最后一个上游；一个上游都没有才是全局图像源
        parents = self._parent_nodes(node)
        if parents:
            return self._node_input_frame(parents[-1], _depth + 1)
        return self.current_static_image if self.current_static_image is not None \
            else self._source_node_frame()

    def _run_nodes(self, order, parents, frame, skipped=None, base_node=None, stop_at=None):
        """
        按给定的拓扑顺序执行一串节点。

        连续执行和单步执行**共用这一段**，两边的取输入 / ROI 继承 / 日志文案完全一致
        （老实现单步是自己另写一套，于是出了"单步不按图像源绑定取图"的问题）。

        :param order: 要执行的节点列表（必须已按拓扑序排好）
        :param parents: {节点: [上游节点]}，来自 _build_execution_order
        :param frame: 数据层起点那一帧（全局图像源）
        :param skipped: 没有执行的节点（只在连续执行时给一行提示）
        :param base_node: 显示底图用哪个节点的输出；None = 用"当前选中的节点"（点谁看谁）
        :param stop_at: **执行到哪个节点为止（含它）**；None = 把 order 全跑完。
                用户 2026.10.7 定："连续执行 = 选中哪个节点就执行到那个节点，不再往下执行"
                —— 由连续执行的入口（_run_flow_pipeline）显式传进来，**不在引擎里偷偷读选中项**
                （直接调引擎的地方，例如测试里验"取输入 / 图像源绑定"的，仍旧跑完整条）。
        :return: (显示用图像, 所有节点结果汇总, 执行日志列表)
        """
        out_images = {SOURCE_KEY: frame}   # {图像源标识: 图像输出}
        results_of = {}                    # {节点: 它产出的结果数据}
        roi_of = {}                        # {节点: 它这一轮实际用的 ROI}，供下游"继承"用
        executed = []                      # [(节点, 结果, roi_info, spec), ...]，按执行顺序
        all_data = []                      # 所有节点结果汇总（给结果计数用）
        exec_info = []                     # 执行日志
        # ★ 参数纠正说明是"每一轮的临时状态"：每轮开头清空，
        #   否则上一个节点（或上一轮）的"已自动纠正…"会串到这一轮的行里。
        self._param_corrections = {}

        # ★ 执行范围 = "选中节点 + 它的全部上游"（决策 e，用户 2026.10.7 拍板，目标5-M1）。
        #   以前是"按拓扑序截到选中节点为止的**前缀**" —— 那会把排在它前面、却与它无关的分支也跑掉：
        #   实测一页上两条互不相干的链 A→B 与 C→D，选中 D 点连续执行，A / B 照样执行；
        #   如果那条无关分支里还有"输出图像"节点，会**悄悄存文件**（这就是要改掉的东西）。
        #   现在只跑与选中节点真正有关系的那条链，其余一律不执行、并如实写一行日志。
        not_run = []
        if stop_at is not None and stop_at in order:
            allowed = self._upstream_closure(stop_at, parents)
            not_run = [node for node in order if node not in allowed]
            order = [node for node in order if node in allowed]

        seq = 1
        for node in order:
            # 1、按"图像源"绑定取本节点的输入（数据层）
            source_key, source_label = self._resolve_input(node, parents.get(node, []), out_images)
            in_img = out_images.get(source_key)
            if in_img is None:
                # 绑定的图像源这一轮不存在，退回全局图像源
                source_key = SOURCE_KEY
                source_label = "全局图像源（回退）"
                in_img = out_images[SOURCE_KEY]
            in_results = results_of.get(source_key)
            in_roi = roi_of.get(source_key)   # 上游没有结果时，下游继承它这块处理区域

            # 2、执行节点；它的图像输出挂到 out_images 上，供下游当图像源
            #    （执行前把"这一轮的来源图片名"准备好：输出类节点要用它当默认文件名）
            self._current_input_name = self._origin_image_name(node)
            #    "输出图像"节点存"带检测叠加"时，还要把"这一轮上游检测出来的绿线 / 红圆"画好交给它
            #    （只画检测结果、**不画 ROI 辅助框**；拿不到就让它退回数据层图像）
            node_spec = get_spec(node.name)
            self._current_overlay_frame = None
            self._round_info = {}
            if node_spec is not None and node_spec.kind == KIND_SINK:
                # "这一轮的执行上下文"：录制文件按节点分开、来源种类决定"自动"档存图片还是视频、
                # 源帧率当录制的标称帧率（只有输出节点用得上，所以只对它算）
                self._round_info = {
                    "node_key": id(node),
                    "source_kind": self._source_kind_of(node),
                    "source_fps": self._source_fps_of(node),
                }
                if self._wants_overlay(node):
                    self._current_overlay_frame = self._render_display(
                        in_img, executed, draw_roi=False)
            out_img, results, roi_info, spec = self._execute_node(node, in_img, in_results, in_roi)
            out_images[node] = out_img
            results_of[node] = results
            roi_of[node] = roi_info
            executed.append((node, results, roi_info, spec))

            # 3、汇总结果 + 记一行日志（图像源也记下来，方便排查数据流走向）
            if results:
                all_data.extend(results)
            exec_info.append((seq, time.strftime("%H:%M:%S"), node.name, source_label,
                              self._format_result_text(node, results, roi_info, spec)))
            seq += 1

        if skipped:
            # 孤立方框、或者连线成环的方框：如实告诉用户它们没有执行
            names = "、".join(node.name for node in skipped)
            exec_info.append(("-", time.strftime("%H:%M:%S"), "提示", "-",
                              "以下节点未执行（没有连线，或者连线成环）：" + names))

        if not_run:
            # 没跑的节点也要如实写一行 —— 否则用户会以为"流程跑完了、后面的节点怎么没结果"。
            # 措辞按"上游链"口径写（决策 e，目标5-M1）：不是"截断到某节点"，而是"只跑它和它的上游"，
            # 所以名单里既可能有它的下游，也可能有与它无关的分支。
            names = "、".join(node.name for node in not_run)
            exec_info.append(("-", time.strftime("%H:%M:%S"), "提示", "-",
                              "连续执行：只跑「{0}」和它的上游；以下节点本次未执行：{1}".format(
                                  stop_at.name, names)))

        # 4、渲染层：底图取 base_node（单步执行 = 目标节点；连续执行 = 当前选中的节点），
        #    没选中 / 选中的节点这一轮没执行，就退回用最后一个执行节点的输出。
        pick = base_node if base_node is not None else self.selected_node
        if pick in out_images:
            shown = executed[:order.index(pick) + 1]
        else:
            pick = order[-1]
            shown = executed
        display = self._render_display(out_images[pick], shown)
        return display, all_data, exec_info

    def _bind_output_providers(self):
        """
        把"输出类节点要用的两个取名字 / 取图器"绑到**当前正在执行的那个主窗口**上。

        OutputOps 里那两个 provider 是模块级的，而"一个进程里可能同时存在多个 MainWindow"
        （测试里就是这样）：谁最后构造谁就把 provider 抢过去了。所以每开始一轮执行都重新绑一次，
        保证输出节点读到的一定是**正在跑的这个窗口**的数据。
        """
        set_input_name_provider(lambda: self._current_input_name)
        set_overlay_frame_provider(lambda: self._current_overlay_frame)
        set_round_info_provider(lambda: self._round_info)

    def _source_kind_of(self, node):
        """
        这个节点这一轮的图"从哪来"：图片 / 视频 / 相机。

        给"输出图像"节点的「输出类型 = 自动」用（用户 2026.10.7：图片源存图片、视频/相机存视频）。
        判据：沿"图像源"绑定追到这条链最上头的起点节点是谁；追不到（用全局图像源）就算"图片"。
        """
        origin = self._binding_origin(node)
        name = getattr(origin, "name", "") if origin is not None else ""
        if name == "视频源":
            return SOURCE_VIDEO
        if name == "相机源":
            return SOURCE_CAMERA
        return SOURCE_IMAGE

    def _source_fps_of(self, node):
        """
        这一轮的"来源帧率"，给录制当标称帧率用（用户在参数窗口里手填的优先，见 OutputOps._resolve_fps）。
            · 视频源 → 读它那段视频的 fps（读不到 SourceOps 内部已兜 25）；
            · 相机源 → 读设备帧率，读不到按 30（主窗口老摄像头预览就是这个节奏）；
            · 图片 / 全局图像源 → 用不上，返回 0。
        """
        origin = self._binding_origin(node)
        name = getattr(origin, "name", "") if origin is not None else ""
        if name == "视频源":
            try:
                from ops.source.VideoSourceOps import video_info
                _count, fps = video_info(origin.params.get("video_path") or "")
                return float(fps or 0)
            except Exception:
                return 0.0
        if name == "相机源":
            try:
                cap = self.cap
                if cap is not None and cap.isOpened():
                    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                    if fps > 0.5:
                        return fps
            except Exception:
                pass
            return 30.0
        return 0.0

    def _close_recordings(self, reason):
        """
        收尾所有正在录制的视频文件，并把结果写进执行日志。

        「停止」/ 视频播到末尾 / 换页 / 删节点 / 关程序 / 关闭相机 都会调它
        （用户 2026.10.7 拍板："下一次录制开始、旧文件要不要收尾"这套生命周期按推荐做）。
        """
        for message in close_all_recordings(reason):
            self._append_log_hint(message)

    @staticmethod
    def _wants_overlay(node):
        """
        "输出图像"节点的「保存内容」是不是"带检测叠加"。

        默认就是叠加：没有检测结果的流程（纯处理链）两者像素完全一样，
        有检测结果的流程只有叠加才看得到绿线 / 红圆（用户 2026.10.7 报的"检测内容存不下来"）。
        """
        return (node.params.get("save_content") or SAVE_OVERLAY) == SAVE_OVERLAY

    def _origin_image_name(self, node):
        """
        这个节点这一轮的"来源图片"叫什么名字（**不含扩展名**）—— 给"输出图像"节点当默认文件名用
        （用户 2026.10.7 要求："输出文件名的默认值修改成输入图片的文件名"）。

        怎么找：沿着"图像源"绑定往上追到这条链最上头的起点
            · 起点是"图片源" → 用它的 `source_path`
            · 起点是"视频源" → 用它的 `video_path`（帧号由"自动编号"去区分）
            · 追不到（用全局图像源）→ 用主窗口当前那张图的路径
            · 相机帧 / 测试图 / 还没开图 → 返回空串（界面显示 placeholder，保存时兜底成 output）
        :return: 名字字符串（不含扩展名）
        """
        origin = self._binding_origin(node)
        path = ""
        if origin is not None:
            path = origin.params.get("source_path") or origin.params.get("video_path") or ""
        if not path and self.current_static_image is not None:
            key = self._image_key_of(self.current_static_image)
            if isinstance(key, str):
                path = key
        if not path:
            return ""
        path = path.split("#")[0]          # 视频帧的键是"路径#帧号"，取路径那半截
        if "\\" not in path and "/" not in path:
            return ""                      # 不是文件路径（例如 id(原图)）就别当名字
        return os.path.splitext(os.path.basename(path))[0]

    def input_image_name_of_node(self, node):
        """给参数窗口用的公开入口：这个节点"输入图片的文件名"（没有就返回空串）"""
        try:
            return self._origin_image_name(node)
        except Exception:
            return ""

    def _binding_origin(self, node, _depth=0):
        """
        沿着"图像源"绑定一直往上追，返回这条链最上头的**起点节点**（图片源）；
        如果这条链最终落到"全局图像源"，返回 None。
        只用于给执行日志写清楚"这一轮吃的到底是哪张图"。
        """
        if node is None or _depth > 20:
            return None
        spec = get_spec(node.name)
        if spec is not None and spec.kind == KIND_SOURCE:
            return node
        binding = getattr(node, "input_source", None)
        if is_bound_node(binding):
            return self._binding_origin(binding, _depth + 1)
        if isinstance(binding, str) and binding == SOURCE_KEY:
            return None
        parents = self._parent_nodes(node)
        if parents:
            return self._binding_origin(parents[-1], _depth + 1)
        return None

    def _run_flow_pipeline_step(self, frame, target_node):
        """
        单步执行：**只跑选中的这一个节点**（沿用 2026.7.25 定的规则："不管流程图中其他的流程，
        只执行选中的节点"），它的输入按自己声明的"图像源"取 —— 沿绑定往上追到起点：
        起点是"图片源"就用它那张图，是"全局图像源"就用当前图。

        **为什么不把上游链一起跑**：那样"单步执行"和"连续执行"的结果会一模一样
        （用户 2026.10.5 实测报过这个"最致命的错误"）。单步执行的用处是**单独调试这一个算子**：
        改参数、点执行，立刻看到这个算子对"流程输入图"做了什么；
        要看整条链的结果就用连续执行。

        :param frame: 数据层起点那一帧（全局图像源用它；追不到绑定链时也用它）
        :param target_node: 要执行的节点
        :return: (显示用图像, 目标节点的结果数据, 一行执行日志)
        """
        if target_node is None:
            return frame.copy(), [], []

        # 输入帧：优先"这个节点声明的图像源"那张图（沿绑定追到起点），追不到才用传进来的当前帧
        in_img = self._node_input_frame(target_node)
        if in_img is None:
            in_img = frame
            source_label = "全局图像源（单步：只跑本节点）"
        else:
            origin = self._binding_origin(target_node)
            if origin is not None:
                source_label = "节点：{0}（单步：只跑本节点）".format(origin.name)
            else:
                source_label = "全局图像源（单步：只跑本节点）"

        img = in_img.copy()
        # 单步执行也要把"这一轮的来源图片名"准备好（输出类节点要用它当默认文件名；
        # 单步执行选中"输出图像"时存的就是这张起点原图，名字自然也是它的名字）
        self._bind_output_providers()
        self._current_input_name = self._origin_image_name(target_node)
        # 单步执行**不叠检测结果**：这一轮只跑了选中的那一个节点，没有任何上游检测结果可叠，
        # 所以"带检测叠加"会自然等于数据层图像（和"要存处理后的图请用连续执行"是同一条口径）。
        self._current_overlay_frame = None
        # 单步执行选中"输出图像"时也可能要录一帧（"自动"档靠来源种类判断存图片还是存视频）
        self._round_info = {
            "node_key": id(target_node),
            "source_kind": self._source_kind_of(target_node),
            "source_fps": self._source_fps_of(target_node),
        }
        out_img, results, roi_info, spec = self._execute_node(target_node, img, None)
        display = self._render_display(out_img, [(target_node, results, roi_info, spec)])

        # 单步执行也产出一行日志：否则切图回来会出现"画面有结果、日志表却是空的"，
        # 缓存里的（画面 + 结果数据 + 日志）三者就对不上了。
        exec_info = [(1, time.strftime("%H:%M:%S"), target_node.name, source_label,
                      self._format_result_text(target_node, results, roi_info, spec))]
        return display, results, exec_info

    # 用表格显示执行日志，execution_log可更新的执行记录
    def _update_execution_log(self, exec_info):
        """
        用表格显示执行日志，刷新 execution_log 表格内容。
        该函数接收一个执行记录列表，将其清空并重新填充到 QTableWidget 中，实现执行日志的实时更新。
        :param exec_info: 执行记录列表，每个元素为 (序号, 时间字符串, 模块名, 图像源, 结果描述)；
                          "提示"行用的是 ("-", 时间, "提示", "-", 文字)
        """
        if not self.execution_log:
            # 如果控件不存在
            return
        if getattr(self, "_video_log_throttle", False):
            # 视频自动播放中：不每格重写表格（不然日志刷屏、播放也变卡），
            # 播放进度看工具栏那个"视频帧 (n/N)"标签；停播时会另写一行说明。
            return
        if getattr(self, "_log_accumulate", False):
            # "运行全部"期间：**不清空**表格，逐张往后累积（用户 2026.10.6 定的规则）
            offset = self.execution_log.rowCount()
            self.execution_log.setRowCount(offset + len(exec_info))
        else:
            # 单张执行：清空旧数据再填（原来的行为）
            offset = 0
            self.execution_log.setRowCount(len(exec_info))
        # 遍历每一条执行记录，row 为行号（从 0 开始）
        for row, info in enumerate(exec_info):
            info = tuple(info)
            if len(info) == 4:
                # 兼容老格式 (序号, 时间, 模块, 结果)，图像源补一个占位
                seq, time_str, module, result = info
                source = "-"
            else:
                # 新格式：(序号, 时间, 模块, 图像源, 结果)
                seq, time_str, module, source, result = info[:5]

            # 将五个字段转换为字符串列表，准备填充到表格的五个列中
            values = [str(seq), time_str, module, source, result]

            # ★ 通用错误通道（批次4 目标5-M2）：带 LOG_ERROR_MARK 的行 = 出错了
            #   ⇒ 整行涂红；标记只是"内部信使"，显示前去掉，用户在表格里看到的是纯文案。
            is_error = result.startswith(LOG_ERROR_MARK)
            if is_error:
                values[4] = result[len(LOG_ERROR_MARK):]
                error_brush = QBrush(QColor(200, 0, 0))

            # 遍历当前行的每一列，col 为列号（0~4）
            for col, text in enumerate(values):
                # 创建一个新的表格项，存储该单元格的文本内容
                item = QtWidgets.QTableWidgetItem(text)
                if is_error:
                    item.setForeground(error_brush)
                # 将表格项放入指定行和列的单元格中
                # 如果该单元格已有内容，会自动替换；如果之前没有，会创建新单元格
                self.execution_log.setItem(offset + row, col, item)
        # ★ 批次5 目标4：写完**自动滚到最后一行**。用户 2026.10.15 提问："前面的执行日志太长会不会影响观看"
        #   —— 实测全工程原来**没有** scrollToBottom() ⇒ "运行全部"跑几十张后，新行写在**底部**、
        #   而视图还停在**顶部**，这才是"看不见"的真症结（不是日志太长）。
        self.execution_log.scrollToBottom()

    def _update_execution_log_throttled(self, exec_info):
        """
        执行日志的"节流版"刷新，专供视频 / 摄像头路径使用（静态图片仍走立刻刷新的版本）。

        为什么需要：
            update_frame 由定时器每 30ms 调一次，而真刷一次表格要清空行、再为每个
            单元格 new 一个 QTableWidgetItem。视频下每帧重建一次表格会明显拖慢画面。
        策略：
            · 内容和上一次真正刷进去的完全一样 -> 直接返回，一格都不动（视频里最常见）；
            · 内容变了 -> 最多每 0.2 秒刷一次，把高频变化攒一攒。
        """
        if not self.execution_log:
            return

        # 把日志列表转成可比较的"签名"（里面都是元组，直接 tuple 化）
        signature = tuple(tuple(row) for row in exec_info)
        if signature == self._exec_log_signature:
            # 和表格里已经显示的内容一模一样，不用重画
            return

        now = time.time()
        if now - self._exec_log_flush_time < 0.2:
            # 内容在变但太频繁（比如视频里每帧结果都不同），先攒着，≥0.2 秒后再刷
            return

        self._update_execution_log(exec_info)
        self._exec_log_signature = signature
        self._exec_log_flush_time = now

    def _append_log_hint(self, text):
        """往执行日志表**追加**一行"提示"（批量执行时写"出错跳过 / 结束"这类信息用）"""
        if self.execution_log is None:
            return
        row = self.execution_log.rowCount()
        self.execution_log.insertRow(row)
        for col, value in enumerate(["-", time.strftime("%H:%M:%S"), "提示", "-", text]):
            self.execution_log.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))
        # ★ 批次5 目标4：提示行也一样滚到最后（否则"用户停止 / 出错跳过 / 共执行 N/N 张"这些
        #   关键提示在批量跑几十张后全在视野外）。
        self.execution_log.scrollToBottom()

    def _display_key_of(self, frame):
        """
        **画面（缩放/平移）**用的键 —— 与"结果缓存键"分开：

        · 来自文件的图：还是用它的路径（每张图的缩放仍然各自独立）；
        · 视频帧：整段视频**共用一个键**（"video:路径"）。否则每帧都是新对象 ⇒ 显示层把每帧都当
          "新图片" ⇒ 每帧复位默认缩放 ⇒ 播放时"画面一大一小"、鼠标滚轮的缩放也被下一帧覆盖掉
          （用户 2026.10.6 实测报的这两个现象，根因就是同一个）。
        """
        known = self._frame_paths.get(id(frame))
        if known:
            return known
        video = self._video_source_node()
        if video is not None and video.params.get("video_path"):
            return "video:" + video.params["video_path"]
        return id(frame)

    def _camera_display_key(self, node, mode):
        """
        相机帧的**画面（缩放/平移）键**：整段共用一个（"camera:编号"）——目标3-M4，2026.10.7。

        为什么不并进 `_display_key_of()`：相机帧每一帧都是 `run_camera()` 返回的**新副本**，
        用对象同一性认不出来；这里直接按"这一轮是不是真的用到相机源、而且相机真的开着"判定，更稳。
        视频那条（"video:路径"）是同一个目的：别让显示层把每一帧都当成"新图片"、每帧复位一次缩放。
        :return: 键字符串；这一轮不是相机帧就返回 None（调用方退回 _display_key_of）
        """
        if not self._camera_used_by(node, mode):
            return None
        if self.cap is None or not self.cap.isOpened():
            return None
        camera = self._camera_source_node()
        return "camera:{0}".format(
            camera.params.get("camera_id", 0) if camera is not None else 0)

    def _video_source_node(self):
        """当前页的"视频源"节点（没有就返回 None）"""
        for node in self.flow_nodes:
            if getattr(node, "name", "") == "视频源":
                return node
        return None

    def _camera_source_node(self):
        """当前页的"相机源"节点（没有就返回 None）"""
        for node in self.flow_nodes:
            if getattr(node, "name", "") == "相机源":
                return node
        return None



def _result_note(results):
    """
    从某个算子这一轮的 results 里取"要写进执行日志的那句话"（批次4 目标4「参数校验」用）。

    引擎的老约定：results 里可以放 dict 带日志文案（`result_bbox()` 只认 tuple/list，
    所以检测结果里混一个 dict 不影响"ROI 继承"）。参数非法被跳过时就是靠它递文案的：
        results = [{"__note__": "参数非法（累加器阈值必须 ≥ 1），已跳过本节点"}]
    （dict 也不会被 `_draw_line()` / `_draw_circle()` 画出来 —— 它们只认长度 4 / 3 的元组。）
    :return: 文案字符串；没有就返回 None
    """
    for item in results or []:
        if isinstance(item, dict) and item.get("__note__"):
            return str(item["__note__"])
    return None


def _result_error(results):
    """这一轮的结果里有没有声明"出错了"（见上面通用错误通道的说明）"""
    for item in results or []:
        if isinstance(item, dict) and item.get("__error__"):
            return True
    return False


# ----------------------------------------------------------------------
# 通用错误通道（批次4 目标5-M2，2026.10.12 用户要求："在日志中使用红色字体写明出错的原因"）
#
# 怎么表达"这一行是错误"：算子在 results 的 dict 里带上 `"__error__": True` ——
#   · 人脸：`{"__note__": "级联文件不存在：…", "__error__": True}`（见 FaceDetectOps.py）
#   · 输出图像：`{"输出图像": "保存失败：…", "__error__": True}`（见 OutputOps.py）
# 这条通道是**通用的**：任何算子、任何错误都能用它把那一行涂红，不用改引擎的元组形状。
#
# 为什么用"文案前缀标记"而不是给 exec_info 元组加第 6 项：
#   元组的形状被缓存重放、`_update_execution_log()`、以及一堆老断言共用，
#   加一项的回归面太大；前缀标记只改"怎么拼文案 / 怎么填表格"一处，
#   而且**显示时会去掉标记**，用户在表格里看到的就是纯文案。
# ----------------------------------------------------------------------
LOG_ERROR_MARK = "\u26a0"        # ⚠ 只用来传递"这行是错误"，不给用户看