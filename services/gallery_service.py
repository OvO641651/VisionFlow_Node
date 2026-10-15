# -*- coding: utf-8 -*-
"""图库：导入 / 删除 / 切换 / 运行范围

批次5 目标2「拆 `MainWindow`」：**v1 只是把 main.py 里的代码原样搬出来**（方法体一字未改），
由 `main.py` 的 `MainWindow` 多重继承本 Mixin —— `self` 仍是主窗口，方法之间照旧 `self.xxx` 互调。
"""

import os
from core.ImageIO import read_image  # 图片读取统一入口（支持中文路径，2026.10.12）
from core.NodeRegistry import KIND_SOURCE, get_spec


class GalleryMixin:
    """图库：导入 / 删除 / 切换 / 运行范围（批次5 目标2 从 main.py 拆出）"""

    def _on_gallery_image_selected(self, img_bgr):
        """
        当用户点击图库中的图片时，切换主画面显示
        这张图片以前执行过 -> 直接显示它上一次的检测结果（不用再点执行按钮）；
        这张图片没执行过   -> 只显示原图，不显示检测结果。
        同时，每个节点在这张图片上设置过的运行参数（ROI + 算法参数）会被恢复。
        """
        if img_bgr is not None:
            self._show_static_image(img_bgr)

    def _on_gallery_path_selected(self, path):
        """
        点图库缩略图时，如果这张图来自某个文件，就把当前页"图片源"节点的路径同步过去
        （用户 2026.10.5 的要求：图库列表和图片源节点是统一的——点哪张图，图片源就吃哪张）。
        """
        self._sync_source_nodes_to_path(path)

    # ------------------------------------------------------------------
    # 图像列表工具栏（控件在 main.ui 里、由 ImageGalleryWidget 收编，这里负责干活）
    # ------------------------------------------------------------------
    def add_folder_to_gallery(self):
        """工具栏"＋文件夹"：弹系统原生的"选择文件夹"，把里面的图片静默导进图库"""
        folder = self._ask_dir()
        if not folder:
            return
        self.import_folder_path(folder)
        if hasattr(self, "gallery_widget"):
            self.gallery_widget.refresh_count()

    def delete_gallery_item(self, item):
        """
        删除图库里的一个条目：**连它的参数存档 / 结果缓存 / 缩放记录一起清掉**
        （用户 2026.10.6 定的规则）——不清的话，图片标识被后面的图复用时会把参数串过去。
        """
        gallery = getattr(self, "gallery_widget", None)
        if gallery is None:
            return
        # ★ 删除前先停掉正在播放的视频/相机：否则下面把视频路径清掉之后，播放定时器还在每一格
        #   去取帧、每格都会弹一次"请先导入图片/视频…"（用户实测：点完 OK 又弹一个，无限弹）。
        if self._video_playing:
            self._stop_video_playback("相机已被删除" if self._camera_playing else "视频已被删除")
        # ★ 相机源（M4）：点"删除"要把相机**关掉**（用户 2026.10.7 定："停止不关、删除才关"），
        #   同时把画布清掉；但**不动相机源节点里的参数**（编号 / 分辨率留着，下次执行会重新打开）。
        camera = self._camera_source_node()
        if camera is not None and (self.cap is not None and self.cap.isOpened()):
            self._release_camera_device()
            self._append_log_hint("已关闭相机（相机源节点里的参数保留）")
        if item is None:
            # 列表里**没有可删的条目**（典型场景：画布上放的是"视频源"的帧，帧不进图库）⇒
            # 退化成"清空画布"：顺便把视频源节点里的路径也清掉，免得下次执行又把它跑出来
            # （用户 2026.10.6 实测："点击删除按钮无法清除画布上的视频"）。
            self.current_static_image = None
            self.current_image_key = None
            view = getattr(self, "image_view", None)
            if view is not None:
                view.set_image(None)
            video = self._video_source_node()
            if video is not None:
                video.params["video_path"] = ""
            self._append_log_hint("已清除画布内容（图像列表里没有可删除的条目）")
            return
        frame = gallery.item_frame(item)
        path = gallery.item_path(item)
        key = path if path else (id(frame) if frame is not None else None)

        gallery.remove_item(item)          # 先从列表移除

        # ★ 这张图的路径如果正是某个"图片源"节点的路径，也要一并清空。
        # 否则图库删了图、点执行时流程还会按图片源里那条路径把这张图跑出来
        # （用户实测："图像列表清空后画布确实没了，但点执行图片又出现了"）。
        if path:
            self._clear_source_nodes_path(path)

        if key is not None:
            # 1、参数存档（每个节点里"这张图那一份"）
            for node in list(self.flow_nodes):
                store = getattr(node, "params_per_image", None)
                if isinstance(store, dict):
                    store.pop(key, None)
            # 2、结果缓存（这张图在所有页面、两种执行方式下的记录）
            for cache_key in [k for k in self.result_cache if k and k[0] == key]:
                self.result_cache.pop(cache_key, None)
            # 3、显示层的缩放记录
            view = getattr(self, "image_view", None)
            states = getattr(view, "_zoom_states", None)
            if isinstance(states, dict):
                states.pop(key, None)

        # 记住"用户删过的图"：以后执行时别再把这张图自动加回图库（用户实测报过"删了又回来"）
        if path:
            self._removed_paths.add(self._path_key(path))

        # 图库空了：**不管删的是不是"当前图"，画布一律清空**
        # （用户实测报过"图像列表里的图全删了，画布上还留着图片"）
        if gallery.count() == 0:
            self.current_static_image = None
            self.current_image_key = None
            view = getattr(self, "image_view", None)
            if view is not None:
                view.set_image(None)
        # 删掉的是"当前图"（但列表里还有别的图）：把画面切到最后一张
        elif frame is not None and self.current_static_image is frame:
            self.current_static_image = None
            self.current_image_key = None
            items = gallery.items()
            if items:
                self._show_static_image(items[-1][1])
        gallery.refresh_count()

    def run_all_images(self, mode="continuous"):
        """
        "运行全部"：把图像列表里的图**逐张**跑一遍（用户 2026.10.6 定的规则）。

        · 开始时**先清空执行日志**，之后每张图的日志**逐张累积**；
        · 某张图出错 -> **跳过继续**跑下一张，不弹任何提示；
        · 如果"自动切换"在执行过程中**被关掉** -> 立刻停（开始时就是关着的，则跑完全部）。
        :return: 真正跑了多少张
        """
        gallery = getattr(self, "gallery_widget", None)
        if gallery is None or gallery.count() == 0:
            return 0
        items = gallery.items()
        # 进来时"运行全部"是不是勾着：只有一开始就勾着，才把"中途取消勾选"当成急停
        started_with_scope = gallery.scope_all()
        # 记下开始时的选中项与画面：不勾"自动切换"（不跟随）时，跑完要还原回去
        start_index = gallery.current_index()
        start_frame = self.current_static_image
        start_path = gallery.item_path(items[start_index][0]) if 0 <= start_index < len(items) else ""
        self._batch_stop = False

        # 清空旧日志（用户要求：运行全部开始时先清空）
        if self.execution_log is not None:
            self.execution_log.setRowCount(0)

        self._log_accumulate = True
        done = 0
        try:
            for index, (item, frame, path) in enumerate(items, 1):
                # 两条急停路径：菜单"停止"、或批量运行中取消勾选"运行全部"
                if self._batch_stop:
                    self._append_log_hint("用户停止，批量执行中断")
                    break
                if index > 1 and started_with_scope and not gallery.scope_all():
                    self._append_log_hint("已取消“运行全部”，批量执行中断")
                    break
                try:
                    # "自动切换"= 是否跟随：勾着才把选中项切到正在跑的那张
                    if gallery.auto_switch():
                        gallery.set_current_index(index - 1)
                    # 只切"当前图 + 它的参数"（画面由 _execute_static 显示结果时刷新）：
                    # 这里**不能**用 _show_static_image()——它会把这张图上一次的缓存结果
                    # 也重新写进日志，批量执行时日志就会重复两遍。
                    self.current_static_image = frame
                    self._switch_image_params(self._image_key_of(frame))
                    # **关键**：流程里若有"图片源"节点，它才是那一轮的取图处——必须把它也切到
                    # 这一张，否则批量执行会一直用图片源原来那张图（用户实测："每次处理的都是同一幅图"）
                    if path:
                        self._sync_source_nodes_to_path(path)
                    self._execute_static(frame, mode)        # 跑一遍当前页的流程图
                    done += 1
                except Exception as exc:                     # 单张出错不中断整批（用户要求继续）
                    self._append_log_hint("第 {0} 张出错已跳过：{1}".format(index, exc))
        finally:
            self._log_accumulate = False

        # 没勾"自动切换"（不跟随）时：把选中项与画面**还原成开始时那一张**。
        # 否则用户会觉得"自动切换勾不勾都一样——跑完画面总是停在最后一张图上"（用户实测报过）。
        # 注意这里只恢复画面、**不动执行日志**（不走 _show_static_image，它会把缓存日志重放一遍）。
        if not gallery.auto_switch():
            if 0 <= start_index < len(items):
                gallery.set_current_index(start_index)
            # 图片源节点也要还原成开始时那一张，否则下次"运行选中"会按它跑上一张
            if start_path:
                self._sync_source_nodes_to_path(start_path)
            if start_frame is not None:
                self.current_static_image = start_frame
                key = self._image_key_of(start_frame)
                self._switch_image_params(key)
                cached = (self.result_cache.get(self._result_cache_key(key, mode))
                          or self.result_cache.get(self._result_cache_key(key, "step")))
                self._display_image(cached["frame"] if cached is not None else start_frame.copy(), key)

        self._append_log_hint("运行全部结束：共执行 {0}/{1} 张".format(done, len(items)))
        return done

    def stop_batch(self):
        """
        菜单 / 工具栏"停止"：中断正在跑的批量执行；视频正在自动播放也一起停掉；
        **顺手收尾正在录制的视频文件**（用户 2026.10.7："停止"就是结束录制、把文件收好）。
        """
        self._batch_stop = True
        if self._video_playing:
            self._stop_video_playback("用户停止")
        else:
            # 没在播放（例如一帧一帧点着录）也要能收尾，否则用户点了"停止"文件还是打不开
            self._close_recordings("用户停止")

    def _sync_source_nodes_to_path(self, path):
        """
        把当前页面里所有"图片源"节点的路径改成 path（图库点选后调用）。

        :param path: 图片文件路径；空字符串 / None 表示这张图没有对应文件（摄像头帧、测试图），忽略。
        """
        if not path:
            return
        changed = False
        for node in list(self.flow_nodes):
            spec = get_spec(node.name)
            if spec is None or spec.kind != KIND_SOURCE:
                continue
            if node.params.get("source_type") == "图片" and node.params.get("source_path") == path:
                continue
            node.params["source_type"] = "图片"
            node.params["source_path"] = path
            changed = True
        if changed:
            # 参数被改了，这一页要标成"有改动"，免得用户关页时丢东西
            self.flow_page_mgr.mark_dirty()

    def _clear_source_nodes_path(self, path):
        """
        把当前页"图片源"节点里路径正好等于 path 的那些清空（这张图被用户从图库里删掉时调用）。

        为什么必须清：图库删了图之后，如果图片源节点里还留着那条路径，点执行时流程照样会把
        这张图跑出来（用户实测："图像列表清空后画布确实没了，但点执行图片又出现了"）。
        """
        key = self._path_key(path)
        if not key:
            return
        for node in list(self.flow_nodes):
            spec = get_spec(node.name)
            if spec is None or spec.kind != KIND_SOURCE:
                continue
            if self._path_key(node.params.get("source_path") or "") == key:
                node.params["source_path"] = ""
            # 视频源节点用的是 video_path，也要一起清（用户要求：删掉这段视频就别再拿它跑）
            if self._path_key(node.params.get("video_path") or "") == key:
                node.params["video_path"] = ""

    def _ensure_source_images_in_gallery(self):
        """
        把当前页"图片源"节点用的那张图也加进图库列表（已经有的不重复加）。

        这样"图片源指定的图"和"打开文件导入的图"一样，都能在图库里看到、点选。
        """
        if not hasattr(self, 'gallery_widget') or self.gallery_widget is None:
            return
        for node in list(self.flow_nodes):
            spec = get_spec(node.name)
            if spec is None or spec.kind != KIND_SOURCE:
                continue
            path = node.params.get("source_path") or ""
            if not path:
                continue
            # 用户在图库里**主动删掉**过的图不要再自动加回来（否则"删了又出现"，用户实测报过）
            if self._is_removed_path(path):
                continue
            if node.params.get("source_type") == "文件夹":
                # 文件夹来源：把里面所有图片都放进图库（内部按路径去重、坏文件静默跳过），
                # 这样点图库缩略图就能在同一个文件夹的图片之间切换
                self.import_folder_path(path)
                continue
            if self.gallery_widget.has_path(path):
                continue
            frame, _results = spec.run(self.detector, None, (0, 0, 0, 0), node.params)
            # ★ 这张图也要登记"来自哪个文件"：否则它的图片标识会退化成 id(原图)，
            # 一旦那张图对象被重建（重新导入、重开方案），id 就变了 ——
            # 单步 / 连续的结果缓存键跟着变，表现就是"换图再切回来结果没了"。
            if path:
                self._frame_paths[id(frame)] = path
            if frame is not None:
                self.gallery_widget.add_image(frame, path)

    def import_image_path(self, path):
        """
        把一个图片文件加进图库（已经有的不重复加）。

        用户要求：读不出来的**直接跳过、不弹任何提示**。
        :return: [(frame, path)]；失败返回 []
        """
        if not path or not os.path.isfile(path):
            return []
        frame = read_image(path)
        if frame is None:
            return []                      # 读不出来就跳过，不提示
        # 记住"这张图来自哪个文件"：参数 / 结果 / 缩放都用它当标识（见 _image_key_of）
        self._frame_paths[id(frame)] = path
        # 用户主动导入的图，从"删过的图"名单里放出来（重新导入就是想要它）
        self._removed_paths.discard(self._path_key(path))
        if not (hasattr(self, 'gallery_widget') and self.gallery_widget.has_path(path)):
            if hasattr(self, 'gallery_widget'):
                self.gallery_widget.add_image(frame, path)
        return [(frame, path)]

    def import_folder_path(self, folder):
        """
        把一个文件夹里的图片全部加进图库（不递归子目录；坏文件自动跳过、不弹提示）。
        :return: [(frame, path), ...]，按文件名排序
        """
        if not folder or not os.path.isdir(folder):
            return []
        exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
        loaded = []
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(exts):
                loaded.extend(self.import_image_path(os.path.join(folder, name)))
        return loaded

    def import_paths(self, paths):
        """
        统一导入入口：传进来的每一项可能是**图片文件**也可能是**文件夹**。
        图片 → 导入这一张；文件夹 → 导入里面所有图片。失败自动跳过，**全程不弹任何提示**（用户要求）。

        :return: 成功导入的 [(frame, path), ...]（不切换主画面，切画面由调用方决定）
        """
        if not paths:
            return []
        loaded = []
        for path in paths:
            if os.path.isdir(path):
                loaded.extend(self.import_folder_path(path))
            else:
                loaded.extend(self.import_image_path(path))
        return loaded
