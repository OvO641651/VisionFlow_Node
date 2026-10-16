# -*- coding: utf-8 -*-
"""视频：帧游标 / 播放定时器 / 录制收尾

批次5 目标2「拆 `MainWindow`」：**v1 只是把 main.py 里的代码原样搬出来**（方法体一字未改），
由 `main.py` 的 `MainWindow` 多重继承本 Mixin —— `self` 仍是主窗口，方法之间照旧 `self.xxx` 互调。
"""

from PySide2.QtCore import QTimer  # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死
import cv2
from core.param_store import VIDEO_ROI_KEY
from core.host_contract import MainHost   # ★ 宿主契约（只为静态检查；运行时是空类），见《批次5 技术方案》§11.6


class VideoMixin(MainHost):
    """视频：帧游标 / 播放定时器 / 录制收尾（批次5 目标2 从 main.py 拆出）"""

    def _maybe_load_video_params(self):
        """
        视频参数"整段共用一份"的**载入侧**（尾巴之一，2026.10.7 补）：

        换了一段视频（或第一次对某段视频动手）时，把"视频槽"里存过的那份参数载回来；
        同一段视频只在**换路径时载一次**，绝不每帧载 —— 否则会把用户播放中刚改的参数覆盖掉。
        """
        video = self._video_source_node()
        path = (video.params.get("video_path") or "") if video is not None else ""
        if not path or path == getattr(self, "_video_params_path", None):
            return
        self._video_params_path = path
        has_store = any(VIDEO_ROI_KEY in (getattr(n, "params_per_image", None) or {})
                        for n in self.flow_nodes)
        if has_store:
            self._load_node_params(self.flow_nodes, VIDEO_ROI_KEY)
            self._append_log_hint("已载回这段视频上一次的参数（视频参数整段共用一份）")

    def _maybe_start_video_playback(self, node, mode):
        """
        勾了"自动切换"时：这一轮执行结束后**接着自动出画面**（用户 2026.10.6 的要求）。

        只在"这一轮真的用到视频源 / 相机源"、而且当前**不是**播放中的那一帧 tick 时才启动，
        避免播放 tick 再套一层播放。

        M4 起这里兼作**分派口**：相机源走 _start_camera_playback（无界流），视频源走
        _start_video_playback（有帧号、有末尾、可循环）。
        """
        if self._video_playing or self._video_tick_running:
            return False
        gallery = getattr(self, "gallery_widget", None)
        if gallery is None or not gallery.auto_switch():
            return False
        if self._camera_used_by(node, mode):
            self._start_camera_playback(node, mode)
            return True
        if not self._video_used_by(node, mode):
            return False
        self._start_video_playback(node, mode)
        return True

    def _start_camera_playback(self, node, mode):
        """
        开始"相机画面"的自动刷新（用户 2026.10.7：勾了"自动切换"再点执行 ⇒ 连续出画面）。

        相机是**无界流**：没有帧号、没有末尾、不循环 —— 一直出到用户点"停止"为止；
        "停止"只停画面（最后一帧留在画布上），**不关相机**（用户定："停止不关、删除才关"）。
        定时器与视频自动播放**共用同一个**（同一时刻只会播一种）。
        """
        if self._video_timer is None:
            self._video_timer = QTimer(self.main_window)
            self._video_timer.setSingleShot(False)
        try:
            self._video_timer.timeout.disconnect()
        except (RuntimeError, TypeError):
            pass
        # 相机读不到帧率就按 30ms 一格（和主窗口原来的相机刷新间隔一致）
        fps = 0.0
        try:
            cap = self.cap
            if cap is not None and cap.isOpened():
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        except Exception:
            fps = 0.0
        interval = int(1000.0 / fps) if fps and fps > 1 else 30
        interval = max(5, min(interval, 1000))
        self._video_timer.setInterval(interval)
        self._video_timer.timeout.connect(lambda: self._video_tick(node, mode))
        self._batch_stop = False
        self._video_playing = True
        self._camera_playing = True
        self._video_timer.start()
        self._append_log_hint("开始显示相机画面（点“停止”可停；相机保持打开）")

    def _advance_video_cursor(self):
        """"执行后前进一帧"：把视频源的 frame_index +1（一次执行只 +1 一次）"""
        video = self._video_source_node()
        if video is None or not video.params.get("video_path"):
            return
        if video.params.get("auto_next", True) is False:
            return
        _nxt = int(video.params.get("frame_index") or 0) + 1
        # ★ 2026.10.16 用户实测：不勾「自动切换」连点单步执行 ⇒ 帧号一直涨（"视频帧 (49/36)"）而画面停在第一帧。
        #   原因：这里**只 +1、没处理末尾**（播放那条路 `_video_tick` 里有"到末尾就回卷 / 停播"）。
        #   处置：**只在"没在播放"（= 单步这条路）时**处理末尾 —— 勾了「循环」⇒ 回卷到 0；没勾 ⇒ 停在最后一帧。
        #   ★ 播放中**不动**这里：`_video_tick` 自己管末尾（老用例 `dsh_m3_video2_check` 钉着那段行为）。
        if not (self._video_playing or self._camera_playing):
            try:
                from ops.source.VideoSourceOps import video_info
                _count, _fps = video_info(video.params.get("video_path") or "")
            except Exception:
                _count = 0
            if _count and _nxt >= _count:
                _nxt = 0 if video.params.get("loop") else max(int(_count) - 1, 0)
        video.params["frame_index"] = _nxt

    def _start_video_playback(self, node, mode):
        """
        开始"自动播放"视频（用户 2026.10.6 要求：勾了"自动切换"后点执行 ⇒ 自动播，不用一帧一帧点）。

        · 帧间隔 = 原帧率（`1000 / fps` 毫秒）；fps 读不到就按 25 兜底；
        · 用 QTimer 驱动（不是死循环）⇒ 界面不卡，"停止"按钮任意两帧之间都能立刻停；
        · 播到末尾：节点参数"到末尾回到开头"勾着 ⇒ 回到第 0 帧继续（反复播放）；
          没勾 ⇒ 自动停。
        """
        if self._video_timer is None:
            self._video_timer = QTimer(self.main_window)
            self._video_timer.setSingleShot(False)
        self._maybe_load_video_params()           # 换了视频就先把"视频槽"那份参数载回来（只载一次）
        from ops.source.VideoSourceOps import video_info     # 局部导入，避免与"注册表 ← 分类模块"的顺序纠缠
        video = self._video_source_node()
        _count, fps = video_info(video.params.get("video_path") or "" if video else "")
        interval = int(1000.0 / (fps if fps and fps > 0 else 25.0))
        interval = max(5, min(interval, 1000))
        try:
            self._video_timer.timeout.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._video_timer.setInterval(interval)
        self._video_timer.timeout.connect(lambda: self._video_tick(node, mode))
        self._batch_stop = False
        self._video_playing = True
        self._video_timer.start()
        self._append_log_hint("开始自动播放视频（原帧率约 {0:.1f} fps，点“停止”可停）".format(
            fps if fps and fps > 0 else 25.0))

    def _stop_video_playback(self, reason):
        """
        停止自动出画面（"停止"按钮 / 视频播到末尾 / 相机被关掉都会走这里）。

        M4 起兼管相机：相机这条路**只停画面、保留最后一帧、不关设备**（用户 2026.10.7 定）。
        M5-2 起还要**收尾正在录制的视频文件** —— 流都停了，文件必须 release，否则打不开。
        """
        self._video_playing = False
        self._camera_playing = False
        if self._video_timer is not None and self._video_timer.isActive():
            self._video_timer.stop()
        # ★ 批次5目标5-M1：把"图像源 (n/N)"标签**交还图库**（顺带立刻刷回图库计数 ——
        #   否则停止后标签会一直停在最后那格"视频帧 (n/N)"上）
        gallery = getattr(self, "gallery_widget", None)
        if gallery is not None and hasattr(gallery, "set_count_locked"):
            gallery.set_count_locked(False)
        self._close_recordings(reason)
        self._append_log_hint("停止播放：{0}".format(reason))

    def _video_tick(self, node, mode):
        """自动播放的一帧：先看要不要停；是相机就走相机那条，否则按原来的执行方式跑一帧"""
        if not self._video_playing:
            return
        if self._batch_stop:
            self._stop_video_playback("用户停止")
            return
        if self._camera_playing:
            self._camera_tick(node, mode)
            return
        from ops.source.VideoSourceOps import video_info
        video = self._video_source_node()
        if video is None:
            self._stop_video_playback("视频源节点已不存在")
            return
        count, _fps = video_info(video.params.get("video_path") or "")
        if not (video.params.get("video_path") or ""):
            # 视频已被删除 / 路径被清空：**只停播、不弹提示**（用户要求：
            # "运行时点击删除按钮后不再弹出这个弹窗，只需要清除画布上的视频即可"）
            self._stop_video_playback("视频源没有可用的视频")
            return
        index = int(video.params.get("frame_index") or 0)
        if count and index >= count:
            if video.params.get("loop"):
                video.params["frame_index"] = 0          # 反复播放
            else:
                self._stop_video_playback("已播到末尾")
                return
        # ★ 批次5目标5-M1：播放期间把"图像源 (n/N)"标签交给播放侧（免得点图库时被图库计数顶一下又弹回）
        gallery = getattr(self, "gallery_widget", None)
        if gallery is not None and hasattr(gallery, "set_count_locked"):
            gallery.set_count_locked(True)
        self._video_tick_running = True
        self._video_log_throttle = True        # 播放中不刷执行日志（不然每格都重写表格）
        try:
            # 状态标签顺带显示帧进度（复用"图像源 (n/N)"那个标签，播放时它就是"视频帧 (n/N)"）
            try:
                label = getattr(getattr(self, "gallery_widget", None), "count_label", None)
                if label is not None:
                    label.setText("视频帧 ({0}/{1})".format(
                        min(int(video.params.get("frame_index") or 0), count or 0), count or "?"))
            except Exception:
                pass
            if mode == "step":
                # 单步播放时**实时取当前选中的节点**：用户播放中途换选中项（例如从"二值化"改成"取反"），
                # 后续帧就该按新选中的节点跑；如果用启动时捕获的那个节点，换选中项只会影响手点的那一帧
                # （用户 2026.10.6 实测报过："自动切换"状态下单步运行切不了其他节点）。
                target = getattr(self, "selected_node", None) or node
                if target is not None:
                    self.run_flow_step(target)
            else:
                self.run_flow_continuous()
        finally:
            self._video_tick_running = False
            self._video_log_throttle = False

    def _video_used_by(self, node, mode):
        """
        这一轮执行有没有**真的用到**视频源（没用到就不该吃掉一帧，用户 2026.10.6 的要求）。

        · 单步：从被执行的节点沿"父节点"往上追，能追到视频源才算用到；
        · 连续：按拓扑序跑全部节点，视频源只要有下游（连进了流程）就算用到。
        """
        video = self._video_source_node()
        if video is None or not video.params.get("video_path"):
            return False
        if mode == "step":
            if node is None:
                return False
            seen, stack = set(), [node]
            while stack:
                cur = stack.pop()
                if cur is video:
                    return True
                if id(cur) in seen:
                    continue
                seen.add(id(cur))
                stack.extend(self._parent_nodes(cur) or [])
            return False
        return any(getattr(edge, "start_node", None) is video
                   for edge in getattr(self, "flow_edges", []))
