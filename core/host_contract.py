# -*- coding: utf-8 -*-
"""宿主契约 `MainHost`（**只为静态检查**，见《批次5 技术方案》§11.6）

**运行时它是个空类**：所有声明都写在 `if TYPE_CHECKING:` 里（`TYPE_CHECKING` 恒为 False ⇒ 运行时不执行）。
它的唯一作用 = 让 PyCharm / mypy 知道「`MainWindow` 最终会给 6 个 Mixin 提供哪些名字」。

为什么需要它：6 个 Mixin 的 `self.xxx` 里有 **65 个名字是跨文件**的（**25 个状态字段** + **40 个方法**）
—— PyCharm 只做单文件分析、看不到 `main.py` 把它们拼起来 ⇒ 这些引用点会报「未解析的特性引用」
（`services/gallery_service.py` 58 条 / `core/flow_engine.py` 68 条 …，6 个文件合计 211 个引用点）。
把清单**集中声明一处**、让 6 个 Mixin 都继承它，警告就归零。

★ **防腐化**：`tests\dsh_t5g3_host_check.py` 会校验「这份清单 = Mixin 真正依赖的名字」
（多一个 / 少一个都红），并断言「运行时这个类不含任何非 dunder 成员」⇒ 它永远只是声明，不会变成实现。

★ **怎么维护**：Mixin 里新写了 `self.foo(...)`（foo 定义在别的文件）⇒ 门禁用例会红；
跑 `python temp\dsh_t5g3_gen_host.py` 重新生成（或手补一行）即可。
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class MainHost(object):
    """`MainWindow`（`main.py` 的类 + 6 个 Mixin 合起来）对 Mixin 暴露的接口。

    ★ 运行时是空的：下面的声明全在 `if TYPE_CHECKING:` 里（只有静态分析看得到）。
    """

    if TYPE_CHECKING:
        # ==================================================================
        # 一、状态字段（25 个）—— 在 `main.py::__init__` 里赋值（或在类体里声明）
        # ==================================================================
        PROJECT_FORMAT: Any  # main.py
        PROJECT_VERSION: Any  # main.py
        VIDEO_ROI_KEY: Any  # main.py
        _camera_playing: Any  # main.py、services/video_service.py
        _frame_paths: Any  # main.py
        _removed_paths: Any  # main.py
        _video_playing: Any  # main.py、services/video_service.py
        cap: Any  # main.py、services/camera_service.py
        current_dialog: Any  # main.py
        current_image_key: Any  # core/param_store.py、main.py、services/gallery_service.py
        current_node_label: Any  # main.py
        current_static_image: Any  # core/flow_engine.py、main.py、services/camera_service.py、services/gallery_service.py
        detector: Any  # main.py
        execution_log: Any  # main.py
        flow_edges: Any  # main.py
        flow_nodes: Any  # main.py
        flow_page_mgr: Any  # main.py
        gallery_widget: Any  # main.py
        image_view: Any  # main.py
        last_source: Any  # main.py
        main_window: Any  # main.py
        result_cache: Any  # main.py
        selected_node: Any  # core/project_store.py、main.py
        video_processing_mode: Any  # main.py
        video_step_node: Any  # main.py

        # ==================================================================
        # 二、跨 Mixin 方法（40 个）—— 谁定义就归谁。★ 用 `Any` 声明而不是写 `def`：
        #     既能被调用、又**不用跟着维护签名**（改了参数也不会误报）。
        # ==================================================================
        _add_edge_to_page: Any  # main.py
        _add_node_to_page: Any  # main.py
        _advance_video_cursor: Any  # services/video_service.py
        _append_log_hint: Any  # core/flow_engine.py
        _ask_dir: Any  # main.py
        _ask_open_path: Any  # main.py
        _ask_save_path: Any  # main.py
        _bind_current_flow_page: Any  # main.py
        _camera_source_node: Any  # core/flow_engine.py
        _camera_tick: Any  # services/camera_service.py
        _camera_used_by: Any  # services/camera_service.py
        _close_recordings: Any  # core/flow_engine.py
        _display_image: Any  # core/flow_engine.py
        _ensure_camera_device_open: Any  # services/camera_service.py
        _ensure_source_images_in_gallery: Any  # services/gallery_service.py
        _execute_static: Any  # core/flow_engine.py
        _get_node_params_store: Any  # core/param_store.py
        _image_key_of: Any  # core/param_store.py
        _info: Any  # main.py
        _is_removed_path: Any  # core/param_store.py
        _load_node_params: Any  # core/param_store.py
        _maybe_start_video_playback: Any  # services/video_service.py
        _node_params_by_image: Any  # core/param_store.py
        _parent_nodes: Any  # core/flow_engine.py
        _path_key: Any  # core/param_store.py
        _release_camera_device: Any  # services/camera_service.py
        _result_cache_key: Any  # core/flow_engine.py
        _run_flow_pipeline: Any  # core/flow_engine.py
        _run_flow_pipeline_step: Any  # core/flow_engine.py
        _save_node_params: Any  # core/param_store.py
        _show_static_image: Any  # core/flow_engine.py
        _stop_video_playback: Any  # services/video_service.py
        _switch_image_params: Any  # core/param_store.py
        _update_execution_log_throttled: Any  # core/flow_engine.py
        _video_source_node: Any  # core/flow_engine.py
        _video_used_by: Any  # services/video_service.py
        _warn: Any  # main.py
        run_flow_continuous: Any  # main.py
        run_flow_step: Any  # main.py
        update_all_edges: Any  # main.py

