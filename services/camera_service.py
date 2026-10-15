# -*- coding: utf-8 -*-
"""相机：开关设备 / 取帧 / 执行时自动打开 / 老预览分支

批次5 目标2「拆 `MainWindow`」：**v1 只是把 main.py 里的代码原样搬出来**（方法体一字未改），
由 `main.py` 的 `MainWindow` 多重继承本 Mixin —— `self` 仍是主窗口，方法之间照旧 `self.xxx` 互调。
"""

from PySide2.QtCore import QTimer  # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死
import cv2
from core.param_store import VIDEO_ROI_KEY


class CameraMixin:
    """相机：开关设备 / 取帧 / 执行时自动打开 / 老预览分支（批次5 目标2 从 main.py 拆出）"""

    # ------------------------------------------------------------------
    # 相机设备开关（内部 API，目标3-M4 抽出来的，2026.10.7）
    #
    # 为什么单独抽一层：主窗口原来那个"打开摄像头 / 关闭"按钮以后可能删掉（用户 2026.10.7 说），
    # 相机源节点要靠这两个函数自己开关设备，不能再依赖按钮那条老路径。
    # ------------------------------------------------------------------
    def _open_camera_device(self, camera_id=0, quiet=True):
        """
        打开相机设备（内部 API）。

        · 已经开着、而且就是同一个编号 ⇒ **直接复用**，不重开（方案 A：节点复用主窗口相机）；
        · 开着别的编号 ⇒ 先关掉再开新的；
        · 打不开 ⇒ 返回 False；quiet=False 时才弹原来那个警告小窗口（按钮路径用）。
        :return: True = 相机可用
        """
        camera_id = int(camera_id or 0)
        cap = self.cap
        if cap is not None and cap.isOpened():
            if getattr(self, "_camera_device_id", None) == camera_id:
                return True
            self._release_camera_device()
        new_cap = cv2.VideoCapture(camera_id)
        if not new_cap.isOpened():
            try:
                new_cap.release()
            except Exception:
                pass
            if not quiet:
                # 如果识别不到摄像头标签，则弹出警告的小窗口
                self._warn("错误", "无法打开摄像头，请检查设备连接")
            return False
        self.cap = new_cap
        self._camera_device_id = camera_id
        self._camera_round_frame = None
        self.camera_id = camera_id          # 和主窗口老变量（设置菜单里那个编号）保持一致
        return True

    def _release_camera_device(self):
        """
        关闭相机设备、释放资源（内部 API）——用户 2026.10.7 定的分工：
        **"停止"不关相机（只停画面，保留最后一帧），"删除"才关相机**。

        M5-2 起：相机一关，正在录的视频也跟着收尾（流没了，文件必须 release）。
        """
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        cap, self.cap = self.cap, None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        self._close_recordings("相机已关闭")
        self._camera_device_id = None
        # 丢掉"这一轮读到的那一帧"：相机都关了，别让取帧器再把它交出去
        self._camera_round_frame = None
        self._camera_frame_round = -1
        # 重置视频标注
        self._is_video_file = False

    def _latest_camera_frame(self):
        """
        "相机最新一帧"（**注入给"相机源"节点用的取帧器**）——方案 A：节点复用主窗口相机。

        · 相机没开 ⇒ 返回 None（节点会原样透传 + 日志写说明，不弹窗、也不自己乱开设备）；
        · 一轮执行里只读一次：`_begin_camera_round()` 之后第一次读到的帧会被记住，
          同一个编号的后续调用直接返回它（这一帧既当流程起点、又给相机源节点当输入）。
        """
        if self._camera_round_frame is not None and self._camera_frame_round == self._camera_round:
            return self._camera_round_frame
        cap = self.cap
        if cap is None or not cap.isOpened():
            return None
        try:
            ret, frame = cap.read()
        except Exception:
            return None
        if not ret or frame is None:
            return None
        self._camera_round_frame = frame
        self._camera_frame_round = self._camera_round
        return frame

    def open_camera(self):
        """打开摄像头并启动视频刷新（主窗口"打开摄像头"按钮的老行为，界面表现一个字不变）"""
        # 原本不管是图片还是视频，点击打开摄像头后都会清空原本的画面
        self.close_camera()

        if not self._open_camera_device(self.camera_id, quiet=False):
            return

        # 摄像头/视频是独立的一个"图片槽"，把各节点的运行参数切到它自己那一份
        self._switch_image_params(self.VIDEO_ROI_KEY)


        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame) # type: ignore
        self.timer.start(30)

    def close_camera(self):
        """关闭摄像头，停止定时器，清空显示区域，包括导入的视频和图片"""
        self._release_camera_device()

        # 关闭时清空静态图片缓存
        self.current_static_image = None

        # 清空 QGraphicsView 的画面
        if hasattr(self, 'image_view') and self.image_view is not None:
            # 清空场景
            self.image_view.scene().clear()
            # 将 pixmap_item 重置为 None，防止下次打开图片时残留引用出错
            self.image_view.pixmap_item = None

            # 顺便把缩放/平移复位，避免下次显示图片或视频时沿用上一次的缩放
            self.image_view.reset_zoom()

    def update_frame(self):
        """定时器槽函数：读取摄像头帧并显示到 video 标签"""
        if self.cap is None or not self.cap.isOpened():
            # 识别不到摄像头时或者打开摄像头失败时执行返回，不读取视频帧
            return

        ret, frame = self.cap.read()
        if not ret:
            # 区分是摄像头出错还是视频播放结束
            if self._is_video_file:
                # 视频播放结束，停止定时器，释放资源（不弹警告，不清除最后一帧画面）
                if self.timer is not None:
                    self.timer.stop()
                    self.timer = None
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                self._is_video_file = False
                return
            else:
                # 摄像头读取失败
                self.close_camera()
                self._warn("错误", "摄像头读取失败，已关闭")
                return

        work_frame = frame.copy()

        # 让"相机源"节点也能用到主窗口这一帧（方案 A：节点复用主窗口相机，不重复读设备）
        self._camera_round_frame = frame
        self._camera_frame_round = self._camera_round

        # 根据模式选择执行管道
        if self.video_processing_mode == "step" and self.video_step_node:
            # 处于单步执行模式且指定了目标节点
            work_frame, data, exec_info = self._run_flow_pipeline_step(work_frame, self.video_step_node)
        else:
            # 处于连续执行模式（或未指定节点），执行完整流程图，解包三个值
            # 同样截到"当前选中节点"为止（和按钮那条路保持一致）
            work_frame, data, exec_info = self._run_flow_pipeline(
                work_frame, stop_at=self.selected_node)

        # 更新日志：视频是每 30ms 一帧，用"节流版"，内容没变就完全不重画表格
        self._update_execution_log_throttled(exec_info)

        # 显示到画布（视频 / 摄像头帧不传 image_key，保持用户当前的缩放和平移不变）
        self._display_image(work_frame)

        # 保存消息，避免关闭摄像头/视频时数据消失
        self.last_detected_data = data

        # 实时更新配置窗口的计数
        if self.current_dialog and self.current_dialog.isVisible():
            self.current_dialog.update_result_count(data)

    def _legacy_camera_preview_active(self):
        """
        主窗口"打开摄像头"按钮那套**老预览**还在跑吗？（目标3-M4，2026.10.7 修）

        老预览 = `self.timer` 那个 30ms 定时器直接读设备、直接刷帧；**只有在用它的时候**，
        单步 / 连续执行才该走 `update_frame()` 那条老路。相机源节点是流程里的起点节点，
        必须走引擎正常路径，否则"画面键整段共用 / 相机帧不进缓存 / 参数复用视频槽 / 自动出画面"
        这套 M4 语义全被绕过。

        （实测踩到：相机源一自动打开相机，第二次点"连续执行"就被老分支接走了 ——
        走的是 update_frame()，_execute_static 压根没执行。）
        """
        return (self.current_static_image is None
                and self.cap is not None and self.cap.isOpened()
                and self.timer is not None
                and self._camera_source_node() is None)

    def _ensure_camera_device_open(self, camera_node):
        """
        把某个"相机源"节点要用的设备准备好（已经开着同一编号就**复用**，不重开）。

        两条路径共用：① 执行前按"这一轮真用到相机源"预开（`_ensure_camera_open_for_run()`）；
        ② `_source_node_frame()` 轮到相机源取图时顺手开（画布上只有相机源、又没连线的场景）。
        "执行时自动打开相机"这个开关在这里统一判断，免得两条路各写一份、判据不一致。
        :return: True = 相机可用
        """
        if camera_node is None:
            return False
        if camera_node.params.get("open_on_run", True) is False:
            return False
        if self.cap is not None and self.cap.isOpened():
            return True
        if not self._open_camera_device(int(camera_node.params.get("camera_id") or 0), quiet=True):
            return False
        # 相机 / 视频是同一个"图片槽"，把各节点的运行参数切到它自己那一份
        self._switch_image_params(VIDEO_ROI_KEY)
        self._append_log_hint("已自动打开相机 {0}（参数与视频共用一份）".format(
            int(camera_node.params.get("camera_id") or 0)))
        return True

    def _begin_camera_round(self):
        """
        每开始一轮执行就让"相机读数"作废一次（目标3-M4，2026.10.7）。

        用处：一轮执行里 `_flow_source_frame()` 和"相机源"节点都会去要一帧，
        没有这个计数器就会从设备里抠走两帧（画面和实际算的不是同一张）。
        """
        self._camera_round += 1
        self._camera_round_frame = None
        self._camera_frame_round = -1

    def _ensure_camera_open_for_run(self, node, mode):
        """
        执行前准备相机：这一轮**真的用到**"相机源"、而相机还没开 ⇒ **自动打开**（用户 2026.10.7 定）。

        · 节点上的"执行时自动打开相机"没勾 ⇒ 不自动开（取不到帧就原样透传 + 日志写说明）；
        · 已经开着同一个编号 ⇒ 复用，不重开（方案 A："节点复用主窗口相机"）；
        · 打开时顺带把各节点参数切到"视频槽"——相机和视频**共用一份参数**（用户定）。
        :return: True = 相机可用
        """
        camera = self._camera_source_node()
        if camera is None:
            return False
        if self.cap is not None and self.cap.isOpened():
            return True
        if not self._camera_used_by(node, mode):
            return False
        return self._ensure_camera_device_open(camera)

    def _camera_used_by(self, node, mode):
        """
        这一轮执行有没有**真的用到**相机源（判定方式和 _video_used_by 一致）。

        · 单步：从被执行的节点沿"父节点"往上追，能追到相机源才算用到；
        · 连续：按拓扑序跑全部节点，相机源只要有下游（连进了流程）就算用到。
        """
        camera = self._camera_source_node()
        if camera is None:
            return False
        if mode == "step":
            if node is None:
                return False
            seen, stack = set(), [node]
            while stack:
                cur = stack.pop()
                if cur is camera:
                    return True
                if id(cur) in seen:
                    continue
                seen.add(id(cur))
                stack.extend(self._parent_nodes(cur) or [])
            return False
        return any(getattr(edge, "start_node", None) is camera
                   for edge in getattr(self, "flow_edges", []))

    def _camera_tick(self, node, mode):
        """
        相机画面的一格（M4）：不像视频那样有帧号可判，只检查"相机还在不在"，
        然后用和手点一模一样的那条路径（run_flow_step / run_flow_continuous）跑一遍。
        """
        camera = self._camera_source_node()
        if camera is None:
            self._stop_video_playback("相机源节点已不存在")
            return
        if self.cap is None or not self.cap.isOpened():
            # 相机被关掉了（典型场景：用户点了"删除"）⇒ **只停播、不弹提示**，
            # 和视频那套"删掉就只停播、别再弹窗"的处理保持一致。
            self._stop_video_playback("相机已关闭")
            return
        self._video_tick_running = True
        self._video_log_throttle = True        # 出画面期间不刷执行日志（不然每格都重写表格）
        try:
            try:
                label = getattr(getattr(self, "gallery_widget", None), "count_label", None)
                if label is not None:
                    label.setText("相机画面")
            except Exception:
                pass
            if mode == "step":
                # 实时取当前选中的节点（和视频播放一样：播放中途换选中项，后续帧按新的跑）
                target = getattr(self, "selected_node", None) or node
                if target is not None:
                    self.run_flow_step(target)
            else:
                self.run_flow_continuous()
        finally:
            self._video_tick_running = False
            self._video_log_throttle = False
