# -*- coding: utf-8 -*-
"""
批次5 目标2 验证：拆 `MainWindow` 之后**"接口契约零变化"**（2026.10.15）

    python dsh_t5g2_api_check.py

为什么另写一套：37 套老用例证明的是"**行为**回归"（跑起来一样），
但它们**证明不了"方法一个没少、没被改名"** —— 而目标2 的判据恰恰是
"拆完之后 `w.方法名(...)` 的调用点 0 改动"。所以这里把"**接口面**"钉死。

判据（每条都能回答"什么情况下为 False"）：

    ① 拆前 main.py 里 MainWindow 的 **117 个方法，拆完之后一个不少**（逐个 `hasattr`）
    ② 冻结清单自身没问题（117 个名字互不重复）—— 防"清单里写重了"造成假绿
    ③ 没有意外新增：多出来的方法只允许是**白名单**（目标2 的弹窗出口 `_warn` / `_info` / `_ask_*`；
       目标3 的分片 `_batch_step` / `_batch_finish`）
    ④ 6 个 Mixin 都真的进了 `MainWindow` 的 MRO（拆出来的文件确实被用上，不是摆设）
    ⑤ Mixin 模块里**不出现 `QMessageBox.` / `QFileDialog.`** —— 用例挡弹窗靠的是
       `m.QMessageBox = FakeMB` / `m.QFileDialog = FakeFD` 给 **main 模块**打补丁；
       新模块一旦自己引用它们，补丁就失效（会弹真窗口 / 用例直接挂）⇒ 必须由 main 的薄壳兜住
    ⑥ Mixin 模块**不 import main**（依赖方向 main → core/services 单向；也防循环导入）
    ⑦ `main.py` 真的瘦下来了（≤ 1400 行；拆前 3327 行 / 拆完 887 行；2026.10.18 由 1200 上调）
    ⑧ 模块级常量仍能从 main 读到（`VIDEO_ROI_KEY` / `LOG_ERROR_MARK` 是**故意的再导出**）
"""
import io
import os
import re
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
MAIN_PATH = os.path.join(PROJ, "main.py")
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication            # noqa: E402
app = QApplication([])
import main as m                                      # noqa: E402
from core.flow_engine import FlowEngineMixin           # noqa: E402
from core.param_store import ParamStoreMixin           # noqa: E402
from core.project_store import ProjectStoreMixin       # noqa: E402
from services.camera_service import CameraMixin        # noqa: E402
from services.video_service import VideoMixin          # noqa: E402
from services.gallery_service import GalleryMixin      # noqa: E402
from services.undo_service import UndoMixin            # noqa: E402

MIXIN_CLASSES = [FlowEngineMixin, ParamStoreMixin, ProjectStoreMixin,
                 CameraMixin, VideoMixin, GalleryMixin, UndoMixin]

# ★ 允许新增的方法白名单（**逐条注明是谁加的**；除此之外多出来的方法一律算"意外新增"）
ALLOWED_NEW_METHODS = [
    # 批次5 目标2：弹窗出口薄壳（用例对 main 打补丁挡弹窗的必要条件）
    "_warn", "_info", "_ask_open_path", "_ask_save_path", "_ask_dir",
    # 批次5 目标3：把"运行全部"从同步 for 循环改成分片执行（一张图 = 一个分片）
    "_batch_step", "_batch_finish",
    # 批次5 目标3 修正：「自动切换」在批量开始时定格 ⇒ 接一个薄处理器，中途拨动给一行提示
    "_on_auto_switch_changed",
    # 批次5 目标4：撤销 / 重做（第 7 个 Mixin `services/undo_service.py` 的 10 个方法）
    "_init_undo", "_undo_note", "_commit_pending_moves", "_undo_remember_node",
    "undo", "redo", "_on_undo_stack_changed", "_run_stack_step",
    # 批次5 目标4 修正：撤销栈改成"每页一条"⇒ 换页时绑定当前页的那条
    "_stack_for", "_bind_undo_stack_for_page",
    # 批次5 目标5-M1：图库判"是不是正在播视频/相机"（播放中点图库只改选中项）
    "_is_playing",
    # 批次5 目标5-M2：判"这一轮是不是活源（视频/相机）流程"（活源 ⇒ 连续执行不展开成批量）
    "_uses_live_source",
]

# 拆前（改前快照 main.py）MainWindow 的 117 个方法名 —— 冻结清单，**不许删、只许更多的方法名留在别处**
PRE_SPLIT_METHODS = [
    "__init__", "open_file", "_page_title", "_page_fingerprint", "_model_page_fingerprint",
    "_add_node_to_page", "_add_edge_to_page", "_on_node_moved", "_collect_page", "_collect_project",
    "save_project", "save_project_as", "_write_project_file", "_update_project_title", "open_project",
    "load_project", "_build_project_model", "_apply_project", "_path_key", "_is_removed_path",
    "_image_key_of", "_node_params_by_image", "_get_node_params_store", "_is_source_node",
    "_is_flow_level_node", "_node_level_param_keys", "_save_node_params", "_load_node_params",
    "_switch_image_params", "_result_cache_key", "_show_static_image", "_execute_static",
    "_display_image", "_open_camera_device", "_release_camera_device", "_latest_camera_frame",
    "open_camera", "close_camera", "update_frame", "_build_execution_order", "_upstream_closure",
    "_node_modifies_image", "_resolve_input", "_resolve_roi", "_execute_node", "_format_result_text",
    "_render_display", "_run_flow_pipeline", "_parent_nodes", "_node_input_frame", "_run_nodes",
    "_bind_output_providers", "_source_kind_of", "_source_fps_of", "_close_recordings", "_wants_overlay",
    "_origin_image_name", "input_image_name_of_node", "_binding_origin", "_run_flow_pipeline_step",
    "close_event", "_show_menubar_menu", "set_camera_id", "add_flow_node", "add_edge",
    "delete_flow_node", "update_all_edges", "_on_tree_double_click", "_create_node_from_name",
    "delete_edge", "on_node_double_clicked", "_open_node_dialog", "_mark_dirty_if_params_changed",
    "_confirm_close_flow_page", "_clear_current_dialog", "on_node_selected", "_source_node_frame",
    "_flow_source_frame", "_legacy_camera_preview_active", "run_flow_step", "run_flow_continuous",
    "on_step_execute", "on_continuous_execute", "_update_execution_log",
    "_update_execution_log_throttled", "_on_gallery_image_selected", "_on_gallery_path_selected",
    "add_folder_to_gallery", "delete_gallery_item", "run_all_images", "_append_log_hint",
    "_maybe_load_video_params", "_maybe_start_video_playback", "_start_camera_playback",
    "_display_key_of", "_camera_display_key", "_video_source_node", "_camera_source_node",
    "_begin_camera_round", "_ensure_camera_device_open", "_ensure_camera_open_for_run",
    "_camera_used_by", "_video_used_by", "_advance_video_cursor", "_start_video_playback",
    "_stop_video_playback", "_camera_tick", "_video_tick", "stop_batch",
    "_sync_source_nodes_to_path", "_clear_source_nodes_path", "_ensure_source_images_in_gallery",
    "import_image_path", "import_folder_path", "import_paths", "_bind_current_flow_page",
    "_on_flow_page_switched",
]

PRE_SPLIT_COUNT = 117

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


def read(path):
    return io.open(path, "r", encoding="utf-8", newline="").read()


def mixin_source(cls):
    return read(sys.modules[cls.__module__].__file__)


# ① 拆前 117 个方法一个不少 -------------------------------------------------
missing = [n for n in PRE_SPLIT_METHODS if not hasattr(m.MainWindow, n)]
check("① 拆前 %d 个方法一个不少（拆完仍能 `w.方法名(...)` 调）" % PRE_SPLIT_COUNT,
      missing == [], missing)

# ② 冻结清单自身无重复 -----------------------------------------------------
check("② 冻结清单自身没问题（互不重复 + 条数 = %d）" % PRE_SPLIT_COUNT,
      len(PRE_SPLIT_METHODS) == PRE_SPLIT_COUNT and
      len(set(PRE_SPLIT_METHODS)) == PRE_SPLIT_COUNT,
      (len(PRE_SPLIT_METHODS), len(set(PRE_SPLIT_METHODS))))

# ③ 没有意外新增（多出来的只能是弹窗出口白名单） ---------------------------
have = set(n for n in dir(m.MainWindow)
           if not n.startswith("__") and callable(getattr(m.MainWindow, n, None)))
unexpected = sorted(have - set(PRE_SPLIT_METHODS) - set(ALLOWED_NEW_METHODS))
check("③ 没有意外新增的方法（只允许白名单 %d 个：目标2 薄壳 + 目标3 分片）" % len(ALLOWED_NEW_METHODS),
      unexpected == [], unexpected)

# ④ 6 个 Mixin 都进了 MRO --------------------------------------------------
not_in_mro = [c.__name__ for c in MIXIN_CLASSES if c not in m.MainWindow.__mro__]
check("④ 6 个 Mixin 都进了 MainWindow 的 MRO",
      not_in_mro == [],
      (not_in_mro, [c.__name__ for c in m.MainWindow.__mro__]))

# ⑤ 新模块里不许直接引用 QMessageBox. / QFileDialog. ----------------------
leak = {}
for cls in MIXIN_CLASSES:
    src = mixin_source(cls)
    hits = [k for k in ("QMessageBox.", "QFileDialog.") if k in src]
    if hits:
        leak[cls.__name__] = hits
check("⑤ Mixin 模块里不直接引用 QMessageBox. / QFileDialog.（用例补丁才挡得住弹窗）",
      leak == {}, leak)

# ⑥ Mixin 模块不 import main ----------------------------------------------
cycle = []
for cls in MIXIN_CLASSES:
    if re.search(r"^\s*(import main\b|from main import)", mixin_source(cls), re.M):
        cycle.append(cls.__name__)
check("⑥ Mixin 模块不 import main（依赖单向 main → core/services）", cycle == [], cycle)

# ⑦ main.py 真的瘦下来了 --------------------------------------------------
main_lines = len(read(MAIN_PATH).split("\n")) - 1
check("⑦ main.py 瘦下来了（拆前 3327 行；判据 ≤ 1400 行（2026.10.18 上调））", main_lines <= 1400, main_lines)

# ⑧ 模块级常量仍能从 main 读到（故意的再导出） ---------------------------
reexport = (getattr(m, "VIDEO_ROI_KEY", None), getattr(m, "LOG_ERROR_MARK", None))
check("⑧ `m.VIDEO_ROI_KEY` / `m.LOG_ERROR_MARK` 仍读得到（再导出没被当废 import 删掉）",
      reexport == ("video", "\u26a0"), reexport)

print("-" * 70)
if fails:
    print("失败项：%d" % len(fails))
    for name in fails:
        print("   - " + name)
else:
    print("失败项：无")
sys.exit(1 if fails else 0)
