# VisionFlowNode 代码说明书

> **本文件是什么**：把工程里**每一个文件的每一个函数**讲清楚 —— **它干什么（作用）** 与 **它为什么这么干（实现原理）**。
> 读者对象是"要接着改这个工程的人"，所以重点写**约定、判据与踩过的坑**，而不是逐行翻译代码。
> **文档版本：v1.1**（2026.10.7 首次成文时为 v1.0；2026.10.16 按新目录整体重写、按代码现状校准；**同日又按用户要求把版号升一级到 v1.1** —— 用户原话"把用户手册，项目技术文档，代码说明书版号升一个级"）。
> ★ **本文件已冻结**（2026.10.16，批次5 打包前）：**后续如需修改，必须由用户明确提出**（批次4 起的“三份文档冻结”约定）。

>
> ★ **2026.10.16 按新目录整体重写**（批次5 目标1「目录重构」 + 目标2「拆 `MainWindow`」之后）：
> ① 代码从"根目录平铺 21 个文件"改成 **`core/ + services/ + ops/ + ui/ + widgets/ + tests/`** 分层；
> ② `main.py` 从 **3327 行**拆到 **964 行**（入口 + 界面装配 + 建图与改动 + 双击路由 + 脏标记 + 5 个弹窗薄壳），
> 其余按职责搬进 **6 个 Mixin**（`param_store` / `project_store` / `flow_engine` / `camera_service` / `video_service` / `gallery_service`）
> 与 **第 7 个 Mixin `undo_service`**（批次5 目标4）；
> ③ 新增 **`core/host_contract.py`**（宿主契约，只为静态检查）、**`core/result_cache.py`**（缓存上限 + LRU）、**`core/commands.py`**（命令与栈）；
> ④ 算子按树干分组（`ops/source/` · `ops/process/` · `ops/detect/` · `ops/sink/` · `ops/color/`），**14 个节点 = 一个节点一个文件**。
> 每章末尾的 **`本章属于`** 是"分组标签"，方便按层检索。

---

## 文件总览

行数为 **2026.10.16 实测**（含空行）。

| 位置 | 文件 | 行数 | 一句话 |
|---|---|---|---|
| **根** | `main.py` | 964 | 入口 + 界面装配 + 建图与改动 + 双击路由 + 脏标记 + 5 个弹窗薄壳 |
| | `main.ui` | 683 | 主窗口布局（含树、流程图标签页 `flowWidget`、预览、图库、执行日志、工具按钮） |
| | `SetCameraID.ui` | 71 | "设置摄像头 ID"小对话框 |
| **`core/`**（零 Qt 或只做契约，共 2879 行） | `NodeRegistry.py` | 272 | **节点能力注册表**（数据流引擎的"节点契约"） |
| | `ParamRules.py` | 107 | 参数校验的公共零件（读参数 / 夹范围 / 强制奇数） |
| | `ImageIO.py` | 79 | 图片读写：**支持中文路径** |
| | `ImageOps.py` | 50 | 处理类算子共用的"通用外壳"（`to_bgr` / `apply_to_roi` / `odd_kernel`） |
| | `Detector.py` | 75 | 直线 / 圆算法的**兼容门面**（真算法已搬进 `ops/detect/`） |
| | `param_store.py` | 176 | `ParamStoreMixin`：参数归档（按图片 / 流程级 / per_node 三套口径） |
| | `project_store.py` | 421 | `ProjectStoreMixin`：方案持久化（收集 / 指纹 / 读写 / 追加去重） |
| | `flow_engine.py` | 1181 | `FlowEngineMixin`：执行入口与数据流引擎 + 渲染显示 + 画面键 |
| | `host_contract.py` | 105 | `MainHost`：Mixin 用到的宿主接口声明（**运行时是空类**，只为静态检查） |
| | `result_cache.py` | 109 | 结果缓存的上限与 LRU 淘汰（**纯逻辑、零 Qt**） |
| | `commands.py` | 301 | 撤销 / 重做的命令与栈（**纯逻辑、零 Qt**） |
| **`services/`**（碰 Qt / 硬件的服务，共 1490 行） | `camera_service.py` | 326 | `CameraMixin`：相机开关 / 取帧 / 执行时自动打开 / 老预览分支 |
| | `video_service.py` | 243 | `VideoMixin`：帧游标 / 播放定时器 / 录制收尾 |
| | `gallery_service.py` | 491 | `GalleryMixin`：图库导入 / 删除 / 切换 / 运行范围 / **批量分片** |
| | `undo_service.py` | 429 | `UndoMixin` + `_UndoContext`：撤销 / 重做（宿主侧那一半） |
| **`ops/`**（算子：一个节点一个文件，共 1937 行） | `source/ImageSourceOps.py` | 164 | 图片源 |
| | `source/VideoSourceOps.py` | 114 | 视频源（帧游标只读、越界回落） |
| | `source/CameraSourceOps.py` | 64 | 相机源（复用主窗口相机） |
| | `process/GrayOps.py` | 55 | 灰度（唯一带"作用于整图"的） |
| | `process/InvertOps.py` | 33 | 取反 |
| | `process/BlurOps.py` | 68 | 滤波（均值 / 高斯 / 中值） |
| | `process/ThresholdOps.py` | 72 | 二值化（固定 / Otsu / 自适应） |
| | `process/MorphologyOps.py` | 78 | 形态学（7 档共用一个节点） |
| | `process/EdgeExtractOps.py` | 80 | 边缘提取（Canny / Sobel / Laplacian） |
| | `detect/LineDetectOps.py` | 166 | 直线识别（`LineDetector`） |
| | `detect/CircleDetectOps.py` | 135 | 圆识别（`CircleDetector`） |
| | `detect/FaceDetectOps.py` | 201 | 人脸识别（级联文件是**节点级参数**） |
| | `sink/OutputOps.py` | 517 | 输出图像（写图片 / 录视频 + 原样透传） |
| | `color/ColorExtractOps.py` | 172 | 颜色提取（HSV / RGB 双模型） |
| **`ui/`**（独立窗口，共 2242 行） | `LineParamsDialog.py` | 1242 | **参数窗口基类**：ROI / 图像源绑定 / 软范围 / 校验提示 / 三个按钮 |
| | `GenericProcessDialog.py` | 603 | **通用参数窗口**：按 `param_specs` 自动生成"运行参数"页 |
| | `CircleParamsDialog.py` | 274 | 圆专用窗口（换控件 + 自定义结果计数） |
| | `GrayParamsDialog.py` | 120 | 灰度专用窗口（加"作用于整图"） |
| | `LineParamsDialog.ui` | 782 | 上面三个窗口共用的界面文件 |
| **`widgets/`**（嵌进主界面的控件，共 1932 行） | `FlowChart.py` | 569 | `NodeItem` / `EdgeItem` / `FlowchartView`（画布） |
| | `FlowPages.py` | 627 | `FlowPageManager`：多页面（浏览器式标签页） |
| | `ImageGraphicsView.py` | 196 | 图像显示视图（滚轮缩放 / 拖拽平移 / 按键记缩放） |
| | `ImageGalleryWidget.py` | 537 | 图库控件（缩略图列表 + 工具栏 + 标签） |
| **`tests/`** | `dsh_run_all_checks.py` | 98 | **门禁一键跑**（每个用例一个子进程，跑完校验口径） |
| | `dsh_*_check.py` | **44 套** | 见《tests/ 门禁》一节 |
| **`temp/`**（本机工具，**不进 git**） | — | — | 拆文件工具 / 截图工具 / 探针脚本等 |
| **`plan/`**（文档，**不进代码**） | — | — | 现行口径真源 = 《批次5 技术方案》 · 开发日志 · 本说明书 · 用户手册 · 项目技术文档 |

---

## 分层与调用关系（谁调谁）

```text
        main.py（入口 + 界面装配）
          │  class MainWindow(CameraMixin, VideoMixin, GalleryMixin,
          │                    FlowEngineMixin, ParamStoreMixin,
          │                    ProjectStoreMixin, UndoMixin)
          ▼
  ┌─────────────────────────── 7 个 Mixin（同一个 self） ───────────────────────────┐
  │ services/camera_service.py   CameraMixin     相机设备 / 取帧 / 老预览          │
  │ services/video_service.py    VideoMixin      视频帧游标 / 自动播放 / 录制收尾   │
  │ services/gallery_service.py  GalleryMixin    图库导入删除切换 / 运行范围 / 分片 │
  │ core/flow_engine.py          FlowEngineMixin 执行入口 / 数据流引擎 / 渲染 / 画面键│
  │ core/param_store.py          ParamStoreMixin 参数按图片归档 / 流程级 / per_node  │
  │ core/project_store.py        ProjectStoreMixin 方案 .vfproj 读写 + 追加去重     │
  │ services/undo_service.py     UndoMixin       撤销 / 重做（命令模式）            │
  └────────────────────────────────────────────────────────────────────────────────┘
          │ 只能用 self.xxx（宿主状态）              ▲
          │ 静态检查读 core/host_contract.py::MainHost（运行时是空类）
          ▼
  core/（零 Qt 或只做契约）        services/（碰 Qt / 硬件）        ui/  widgets/
  NodeRegistry · ParamRules        camera / video / gallery        LineParamsDialog
  ImageIO · ImageOps · Detector    undo_service                    GenericProcessDialog
  result_cache · commands                                          FlowChart · FlowPages
  param_store · project_store                                      ImageGraphicsView
  flow_engine · host_contract                                      ImageGalleryWidget
          │
          ▼  反向导入（注册表 → 算子；算子**绝不** import 注册表）
  ops/{source, process, detect, sink, color}/*.py  —— 14 个节点，一个节点一个文件
          │
          ▼
  tests/  44 套 dsh_*_check.py + dsh_run_all_checks.py（门禁）
```

**四条铁律（读代码前先记住）**：
1. **`core/` 不许依赖 `widgets/`**：`NodeRegistry.is_bound_node()` 就是为此存在的（判断"绑定值是不是上游节点对象"时**不 import `NodeItem`**，改判"对象带 `name` 属性"）；
2. **算子文件只导出声明，绝不 import `NodeRegistry`**（注册表反向 import 它们，否则循环导入）；
3. **数据层与渲染层彻底分离**：绿线 / 红圆 / 人脸框只画在显示图上，永不回流参与算法；
4. **算子的"影响"只能通过声明的图像源绑定 + ROI 继承发生**。

---

## main.py（964 行；入口 + 界面装配 + 建图与改动 + 双击路由 + 脏标记 + 5 个弹窗薄壳）

**文件作用**：程序入口与**界面装配**。批次5 目标2 之后它**只留四类东西**：
① 启动与界面接线（把 `.ui` 里的控件找出来、把信号接上）；② **建图与改动的唯一入口**（节点 / 连线的增删、拖动、参数提交 —— **撤销命令就记在这四个入口上**）；
③ 双击路由（哪个节点用哪个参数窗口）；④ 脏标记与页面装配；外加 **5 个弹窗薄壳**（让 Mixin 不再直接引用 `QMessageBox` / `QFileDialog` 这两个全局名，
这样用例对 `main` 模块打补丁时**仍然有效**）。

**关键设计与原理**：
- **类头 = 7 个 Mixin**（`class MainWindow(CameraMixin, VideoMixin, GalleryMixin, FlowEngineMixin, ParamStoreMixin, ProjectStoreMixin, UndoMixin)`）；
  ★ 它**没有 Qt 基类** —— 只是普通类，持有 `QUiLoader().load('main.ui')` 出来的 `self.main_window`；
- **Mixin 只能通过 `self.xxx` 用宿主状态**：跨文件的 65 个名字（25 状态 + 40 方法）声明在 `core/host_contract.py::MainHost` 里，**运行时是空类**（`if TYPE_CHECKING:`）；
- **四个改动入口 = 命令记录点**：`add_flow_node` / `add_edge` / `delete_flow_node` / `delete_edge`（外加参数提交与拖动），
  命令**只记一次**（右键菜单、树双击、拖拽都最终走到这几个方法）；
- **`main` 模块里 4 个"故意的再导出"**：`VIDEO_ROI_KEY` / `LOG_ERROR_MARK` / `KIND_SOURCE` / `result_bbox`
  —— 用例把 `main` 当聚合入口读 `m.<名字>`，**别当废 import 删掉**。

### 模块级

| 名字 | 作用 | 实现原理与要点 |
|---|---|---|
| `from core.Detector import DetectorShape` | 直线 / 圆算法的门面 | 真算法已搬到 `ops/detect/`，这里只为了让老调用点不用改 |
| `from core.NodeRegistry import KIND_SINK, KIND_SOURCE, get_spec, result_bbox` | 节点契约 | `KIND_SOURCE` / `result_bbox` 同时是**给用例读的再导出** |
| `from core.param_store / project_store / flow_engine import …` | 三个核心 Mixin | 拆 `MainWindow` 的第 1~2 批产物 |
| `from services.camera/video/gallery_service import …` | 三个服务 Mixin | 拆 `MainWindow` 的第 3 批产物 |
| `from services.undo_service import UndoMixin` | **第 7 个 Mixin** | 批次5 目标4：撤销 / 重做 |

### 一、弹窗出口薄壳（批次5 目标2 收口）

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_warn(title, text)` | 统一"警告"出口 | 父窗口固定是主窗口；Mixin 只调 `self._warn` ⇒ 用例打补丁（`m.QMessageBox = FakeMB`）依然生效 |
| `_info(title, text)` | 统一"提示"出口 | 同上（信息类） |
| `_ask_open_path()` | 选一个方案文件来打开 | 取消返回空串；重写它就能挡掉文件对话框 |
| `_ask_save_path(default_name)` | 选方案保存路径 | 同上 |
| `_ask_dir()` | 选一个文件夹 | 同上 |
| `_show_menubar_menu()` | 点顶部"菜单"按钮 = 弹出菜单栏的第一项 | 老按钮：`菜单栏` 被 `setNativeMenuBar(False)` 后仍要有入口 |

### 二、启动与界面装配

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `__init__` | 装配整个主窗口 | 顺序很讲究：先 `QUiLoader` 载 `.ui` → 找控件 → `self._init_undo()`（**必须在 `flow_page_mgr.setup()` 之前**，否则换页回调里拿不到撤销栈）→ `FlowPageManager.setup()` → `_bind_current_flow_page()` → 建图库/相机/视频 → 接信号 |
| `_bind_current_flow_page()` | 把"当前页"的 `view` / `flow_nodes` / `flow_edges` / 提示 label 绑到 self 上 | 换页时整体替换（Mixin 全靠这几个名字工作） |
| `_on_flow_page_switched(new_page, old_page)` | 换页回调 | 顺序：绑新页 → **绑这一页自己的撤销栈** → 存旧页节点参数 → 取新页参数 → 刷新画面 |
| `_clear_current_dialog()` | 对话框关闭时清引用 | 防止主窗口攥着已销毁的窗口 |
| `close_event(event)` | 关窗口 | 释放摄像头 + **收尾正在录制的视频文件**（否则文件没 release） |

### 三、建图与改动入口（撤销就记在这四处）

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `add_flow_node(name, pos)` | 拖拽 / 双击添加节点 | 加到"当前页"；记一条 `add_node` 命令；节点名决定用哪个算子（`get_spec`） |
| `add_edge(start_node, end_node)` | 从蓝点拉一条连线 | 同一对起终点不重复连；**只有真连上才记命令**（`edge is not None`） |
| `delete_flow_node(node_to_delete)` | 删节点（**连带删它的连线**） | 头一句是 `if node not in self.flow_nodes: return`（★ 撤销 bug 的根因：旧引用失效时会在这里静默返回）；删之前先让 `UndoMixin` **采集状态**并 `forget(uid)` |
| `delete_edge(edge_to_delete)` | 删一条连线 | 同上（先采集后删） |
| `update_all_edges()` | 让所有连线跟着节点动 | 拖动 / 建删节点后调用 |
| `_add_node_to_page(page, name, pos, mark_dirty=True)` | **在指定页**建节点 | 拖拽与"加载方案"共用；加载时 `mark_dirty=False`（从文件读进来的不算改动）；顺带 `_undo_remember_node` |
| `_add_edge_to_page(page, start, end, mark_dirty=True)` | **在指定页**连一条线 | 同上（方案加载共用） |
| `_on_node_moved(page=None, node=None)` | 节点被拖动 | 刷新连线 + 标脏 + 攒一条 `move_pending`（去抖后提交成一条命令） |
| `on_node_selected(node)` | 节点被单击选中 | 记 `selected_node`、刷新状态栏、刷新帮助页 |

### 四、双击路由与参数窗口

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_on_tree_double_click(_item, _column)` | 双击左侧树 | **先取文本再延迟**：`QTreeWidgetItem` 只是 C++ 指针，槽里直接 `text()` 可能 RuntimeError（老坑） |
| `_create_node_from_name(name)` | 双击树枝 = 建节点 | 复用 `add_flow_node`（因此也走命令记录） |
| `on_node_double_clicked(node)` | 双击方框 → 弹它的参数窗口 | **专用优先、通用兜底**：直线 / 圆 / 灰度各有专用窗口，其余只要声明了 `param_specs`（含空表）就走 `GenericProcessDialog` |
| `_open_node_dialog(node, dialog_class)` | 统一开窗流程 | 开窗前先 `dict(node.params)` 存快照 + 记下 `current_image_key`（参数是按图片归档的） |
| `_mark_dirty_if_params_changed(node, before, image_key=None)` | 参数真变了才标脏 | 变了 ⇒ `mark_dirty()` + 记一条 `set_params` 命令（带 image_key ⇔ "这是哪张图的参数"） |
| `_confirm_close_flow_page(page)` | 关页前的"要不要保存" | `FlowPageManager` 的回调；返回 False = 取消关闭 |

### 五、执行入口（含"活源"判据）

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `run_flow_step(target_node)` | "单步执行"统一入口 | 主界面按钮 / 参数窗口的"执行 / 确定"都调它；**单步 = 只跑选中的那一个节点** |
| `run_flow_continuous()` | "连续执行"统一入口 | 真跑一次整流程（按拓扑序） |
| `on_step_execute()` | 点"单步执行"按钮 | 老摄像头预览还在跑 ⇒ 走老路（`update_frame`），否则 `run_flow_step` |
| `on_continuous_execute()` | 点"连续执行"按钮 | ① 老预览 ⇒ 老路；② ★ **活源流程 ⇒ 不展开成批量**（走 `run_flow_continuous`）；③ 图库有图 + 运行模式="运行全部" ⇒ `run_all_images`（**分片批量**） |
| `_uses_live_source()` | 这一轮的取图来源是不是"活源"（视频 / 相机） | 判据：正在播 / **流程里有视频源节点**（★ 只看节点在不在，不看有没有配视频）/ 有相机源且真会用到；活源流程的"连续执行"**不该**变成"跑图库每一张" |
| `set_camera_id()` | "设置摄像头 ID"小窗口 | 写回相机源节点参数（设备真源仍是主窗口 `cap`） |
| `open_file()` | 顶部"打开文件" | 选图片或视频 ⇒ 走图库 / 视频两条路；批量导入时主画面显示第一张 |

### 六、脏标记与收尾

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_clear_current_dialog()` / `close_event` | 见上 | — |
| `main()` | 程序入口 | `QApplication` → `MainWindow` → `show()` → `app.exec_()` |

---

> **本章属于**：① 入口与界面装配

## main.ui（683 行；主窗口布局）

**文件作用**：主窗口的**全部静态布局**（控件摆位与初始属性）。**控件真源 = `.ui` 摆占位、运行时代码 `findChild` 收编**（约定：能在 Designer 里预览，就不在代码里手搓控件）。

**关键控件（objectName 是代码的抓手）**：

| objectName | 类型 | 作用 |
|---|---|---|
| `flowWidget` | `QTabWidget` | 流程图标签页：被 `FlowPageManager` 改造成"浏览器式"多页（每页一个画布） |
| `image_gallery` | `QListWidget` | 图库缩略图列表（由 `ImageGalleryWidget` 收编并改成 `IconMode`） |
| `gallery_count_label` | `QLabel` | "图像源 (n/N)"标签（播放时被播放侧改写成"视频帧 (n/N)"，见 `set_count_locked`） |
| `execution_log` | `QTableWidget` | 5 列执行日志（序号 / 时间 / 模块 / 图像源 / 结果数据）；**按像素滚动**（批次5目标5-M2） |
| `menu_edit` + `action_undo` / `action_redo` | `QMenu` + `QAction` | 顶部「编辑」菜单的撤销 / 重做（**初始 `enabled=false`**，由撤销栈联动） |
| `btn_undo` / `btn_redo` | `QPushButton` | 工具条上的两个按钮（与菜单共用同一套 enabled 联动） |
| `videoLabel` | `QLabel` | 普通图片 / 视频帧的显示位置（图像视图由 `ImageGraphicsView` 接管） |
| 树 `treeWidget` | `QTreeWidget` | 左侧算子树（采集 / 处理 / 检测识别 / 颜色处理 / 新建项目） |

**关键设计与原理**：
- 工具栏顺序是**用户定的**：图像源 n/N → 自动切换 → 运行模式下拉框（**只选模式、不执行**）→ 停止 → ＋图片 / ＋文件夹 / 删除 / 折叠；
- `.ui` 里丢了控件、代码有"找不到就自己建"的兜底时，**测试会照常通过、问题被掩盖**（曾踩到 `gallery_run_all_menu`）⇒ 兜底逻辑要与"断言用的是 `.ui` 里那个"配套。

> **本章属于**：① 入口与界面装配

## SetCameraID.ui（71 行；设置摄像头 ID 的小对话框）

**文件作用**：给"相机源"节点选设备编号 / 分辨率的极简窗口（一个下拉框或数字框 + 确定 / 取消）。

**关键设计与原理**：它**只管把值填进参数**；真正的设备开关在 `services/camera_service.py`（方案 A：节点复用主窗口相机）。
分辨率目前**只存不生效**（用户 2026.10.7 定），预留给后续。

> **本章属于**：① 入口与界面装配

---

## NodeRegistry.py（core/NodeRegistry.py；272 行；节点能力注册表 = "节点契约"）

**文件作用**：把"一个算子能干什么"集中声明成 `NodeSpec`：怎么跑（`run`）、怎么画（`draw`）、怎么把结果写成一行日志（`format_result`）、
有哪些参数（`param_specs`）、参数怎么校验（`validate`）、是不是"改图"的算子（`kind`）。
**它是引擎与界面之间唯一的契约**：引擎不认识任何具体算子，界面也不认识 —— 全靠这张表。

**关键设计与原理**：
- **反向导入**：注册表 import 各 `ops/*/` 的声明表（`_register_category`），**算子文件绝不 import 注册表** ⇒ 不会循环导入；
- **`kind` 决定语义**：`KIND_SOURCE`（采集）/ `KIND_PROCESS`（处理，改图）/ `KIND_DETECT`（检测，只出结果）/ `KIND_SINK`（输出，原样透传）；
- **`is_bound_node()`（批次5 目标2 收尾新增）**：判断"图像源绑定值是不是某个上游节点对象"时**不 import `widgets/FlowChart.NodeItem`**
  （否则 `core/` 反向依赖 `widgets/`）；判据改成"对象带 `name` 属性" —— 这样 `core/` 与 `widgets/` 彻底解耦；
- **节点级参数**：`param_specs` 里写 `"per_node": True` ⇒ 该参数**不按图片归档**（换图 / 换视频 / 换页都不重置）；现在只有人脸的级联文件用它。

| 函数 / 类 | 作用 | 实现原理与要点 |
|---|---|---|
| `class NodeSpec(name, kind, run, draw, format_result, whole_image_param, param_specs, validate)` | 一个算子的能力声明 | `run(detector, img, roi, params) -> (out_img, results)`；`roi` 是**原图坐标** `(x,y,w,h)` |
| `NodeSpec.modifies_image()` | 输出图像会不会和输入不一样 | 处理类 / 图像源 = True；检测类、**输出类 = False**（输出类必须算 False，否则"中间插一个输出节点"会被误当成真正改图的那一支） |
| `NodeSpec.is_flow_level()` | 这个节点的参数是不是**流程级配置**（不按图片归档） | 起点节点（来源 / 路径）与输出类（输出目录 / 文件名）都算：它们与"当前是哪张图"无关；不跳过的话换图会被 `clear()` 清掉 |
| `_register_category(...)` | 把分类模块导出的声明表组装成 `NodeSpec` 登记 | 各 `ops/*/` 只导出声明；`draw` 也照传（2026.10.12 起允许分类模块自己声明绘制） |
| `node_level_param_keys(spec)` | 这个算子声明了哪些"节点级参数" | 读 `param_specs` 里的 `"per_node": True`（人脸的级联文件） |
| `get_spec(name)` | 取算子的能力声明 | 返回 None = 这个模块还没实现（引擎会原样透传 + 日志如实写"模块未实现"） |
| `is_implemented(name)` | 实现了吗 | 现在树上每一项都有算子 |
| `result_bbox(results)` | 把一串结果算成"原图坐标"包围盒（供下游 ROI 继承） | 支持直线 `(x1,y1,x2,y2)` 与圆 `(cx,cy,r)`；没有可用结果返回 None |
| `is_bound_node(binding)` | 绑定值是不是上游节点对象 | 绑定值只有三种：`None`（自动）/ 字符串键 / 节点对象；**不 import `NodeItem`** |

> **本章属于**：③ 公共工具

## ParamRules.py（core/ParamRules.py；107 行；参数校验的公共零件）

**文件作用**：批次4 目标4「参数校验」的公共零件 —— 读参数、夹范围、强制奇数这些琐碎判断放这里，
供**参数窗口**（`LineParamsDialog._validate_params()`）与**引擎**（`flow_engine._execute_node`）**共用同一张规则表**。
为什么单独一个文件：各算子文件不能反向 import `NodeRegistry`（注册表反向 import 它们，会循环导入），零件也不能写在注册表里；本文件不依赖任何算子模块。

**关键设计与原理**：
- **统一签名** `validate(params) -> (fixed_params, corrections, errors)`；`errors` 非空 ⇒ **引擎侧跳过这个节点**（窗口侧只提示、不拦）；
- **只写回"入参里本来就有的键"**：规则为取值方便会把默认值填进 `fixed`，但默认值不算纠正 —— 灌进 `node.params` 会把一堆默认值写进方案文件、还会让"视频参数整段共用"误判"参数变了"（实测踩到、门禁抓出）；
- **规则抛异常不许拖累执行**：`run_validation()` 兜住并转成一条 `errors`；
- **纯函数、不做 IO**：视频播放每秒跑 25 次，规则里绝不许查文件。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `read_int(params, key, default, label, notes)` | 把参数读成 int | 读不出来（方案文件被手改坏）⇒ 用默认值并记一条说明 |
| `read_float(params, key, default, label, notes)` | 读成 float | 同上 |
| `clamp_int(value, low, high, label, notes)` | 夹进 `[low, high]` | **只有真越界才记说明**（不许无脑刷屏） |
| `clamp_float(value, low, high, label, notes)` | 浮点夹取 | 口径同上 |
| `force_odd(value, low, high, label, notes)` | 夹范围并强制奇数 | 卷积核 / 结构元 / `ksize` 要求正奇数，否则 OpenCV 直接抛；与 `ImageOps.odd_kernel()` 同口径 —— 那边算法侧兜底，这边参数侧说明 |
| `run_validation(spec, params)` | **窗口层与引擎层共用的唯一入口** | `spec` 为 None 或没有 `validate` ⇒ 放行；副本进副本出；`fixed` 过滤成"只含入参原有的键"；规则抛异常 ⇒ 写一条"参数校验规则异常" |

> **本章属于**：③ 公共工具

## ImageIO.py（core/ImageIO.py；79 行；图片读写：支持中文路径）

**文件作用**：图片读写的统一入口，解决 Windows 上"**中文（非 ASCII）路径读不了 / 写不了**"。
根因（只读探针实测，cv2 4.13）：`cv2.imread` / `cv2.imwrite` 走**窄字符（ANSI）文件 API**，且 `imread` 失败是**返回 None 不抛异常** ⇒ 表现为"静默读不出来"。

**关键设计与原理**：
- 读 = `np.fromfile(path)` → `cv2.imdecode(buf, flags)`；写 = `cv2.imencode(ext, img)` → `buf.tofile(path)` —— 不碰窄字符 API；
- **返回值契约与 cv2 一致**（失败 None / False）⇒ 调用方的 `if img is None:` 一行都不用改；
- 视频不受影响（`VideoCapture` / `VideoWriter` 走 FFmpeg），所以这里只处理图片。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `read_image(path, flags=cv2.IMREAD_COLOR)` | 读一张图（支持中文路径） | 空路径 / `fromfile` 抛 `OSError·ValueError` / 字节流为空 / `imdecode` 失败 ⇒ None |
| `write_image(path, img, params=None)` | 写一张图（支持中文路径） | 空图或空路径 ⇒ False；扩展名缺失按 `.png`；`imencode` 抛异常 / 不认识扩展名 / `tofile` 失败 ⇒ False |

> **本章属于**：③ 公共工具

## ImageOps.py（core/ImageOps.py；50 行；处理类的通用外壳）

**文件作用**：处理类算子**共用**的三个零件，把"copy 出来 → 只在 ROI 上改 → 回填 → 保证 3 通道"这条流水线固定下来。

**关键设计与原理**：绝不就地改传入数组（否则污染上游数据层）；输出**永远 3 通道 BGR**（单通道图丢给下游 `cv2.line` / HoughCircles 会抛）。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `to_bgr(img)` | 保证 3 通道 BGR | 单通道 → `cv2.cvtColor(GRAY2BGR)`；已是 3 通道直接返回 |
| `apply_to_roi(img, roi, func)` | 处理类通用外壳 | copy 新图 → 取 ROI 视图交给 `func(patch)` → 回填 → `to_bgr`；`func` 的返回值会被写回 ROI |
| `odd_kernel(value, low, high)` | 夹范围并强制奇数 | 卷积核尺寸必须奇数（算法侧兜底） |

> **本章属于**：③ 公共工具

## Detector.py（core/Detector.py；75 行；直线 / 圆算法的兼容门面）

**文件作用**：批次5 目标1 把直线 / 圆算法各自拆成 `ops/detect/` 下的独立文件之后留下的**门面** —— 老调用点（`DetectorShape.line_detector()`）不用改。

**关键设计与原理**：门面只做转发；`make_test_image()` 仍是"没有测试图时自己造一张"的公用函数（自检 / 单独运行本文件用）。

| 名字 | 作用 | 实现原理与要点 |
|---|---|---|
| `class DetectorShape` | 门面 | `line_detector()` → 转发 `ops/detect/LineDetectOps.LineDetector`；`circle_detector()` → `CircleDetectOps.CircleDetector` |
| `make_test_image()` | 造一张带矩形 / 圆 / 长横线的测试图 | 单测与自检用（工程里没有 `image/` 也能跑） |

> **本章属于**：③ 公共工具

## param_store.py（core/param_store.py；176 行；`ParamStoreMixin` —— 参数归档）

**文件作用**：回答"**这个参数属于谁**" —— 按图片 / 流程级 / 节点级三套口径存取，是"每张图一套参数"这条老语义的唯一实现处。

**关键设计与原理（三套口径，缺一不可）**：
1. **按图片归档**（默认）：`params_per_image[图片标识] = {参数名: 值}`；换图 = 存旧的、载新的；`_load_node_params()` 是**先 `clear()` 再载入**；
2. **流程级**（`_is_flow_level_node`）：起点节点（源 / 路径）与输出类（输出目录 / 文件名）**不跟图片走**；
3. **节点级**（`_node_level_param_keys`，`per_node: True`）：如人脸级联文件，**换图 / 换视频 / 换页都不重置**（不剔除就会"每张图各记一份"）。
- 图片标识 `_image_key_of()` **优先用文件路径**（跨会话稳定、能写进方案文件），没路径（摄像头帧 / 测试图）才退回 `id(原图)`；
  视频帧的标识 = `"{video_path}#{帧号}"`（带 `#` ⇒ 结果缓存里能一眼认出"这是逐帧那一类"）；
- ★ `_switch_image_params()` 有个**故意**的分支：`current_image_key is None`（还没开过图）时**不载入**新图参数 ——
  保护"先双击节点调好 ROI 再打开图片"那份参数不被清掉。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_path_key(path)` / `_is_removed_path(path)` | 路径比较键 / "这张图是不是被用户删过" | 绝对化 + 大小写不敏感（用户删过的图不再被自动加回图库） |
| `_image_key_of(frame)` | 这张图在参数 / 缓存 / 缩放里的标识 | 优先文件路径；无路径退回 `id(frame)`；视频帧 `路径#帧号` |
| `_get_node_params_store(node)` | 取节点"按图片存的参数"字典 | 结构 `{图片标识: 整份 params 的副本}`；没有就现场建 |
| `_is_source_node` / `_is_flow_level_node` / `_node_level_param_keys` | 三套口径的判据 | 见上；三者都在 `_save_node_params` / `_load_node_params` 里被查 |
| `_save_node_params(nodes, image_key)` | 把一批节点的参数存到某张图名下 | 跳过流程级节点；剔除节点级参数；**空字典不存**（省内存 + 避免灌 None） |
| `_load_node_params(nodes, image_key)` | 把一批节点的参数换成某张图名下那份 | `clear()` 之前先把**节点级参数留一份**，载入后再放回（否则级联文件一换图就丢） |
| `_switch_image_params(new_key)` | 换图：存旧的 + 载新的 | 同一张图直接返回；`new_key` 与 `current_image_key` 都参与判据（见上"故意的分支"） |
| `_node_params_by_image(node)` | 导出可写进方案文件的那部分（**只导出字符串键**） | `id(原图)` 这种键跨进程没意义 |

> **本章属于**：④ 状态与服务层

## project_store.py（core/project_store.py；421 行；`ProjectStoreMixin` —— 方案持久化）

**文件作用**：`.vfproj` 的读写（JSON / UTF-8 / 缩进 2），以及"打开方案 = **追加**一页 + 指纹去重"这套语义。

**关键设计与原理**：
- **一个方案文件只装一页**（一个文件 ↔ 一个流程图窗口）；保存目标**按页面记**（`page["project_path"]`）：
  从没保存过的新页必须弹窗选路径，绝不拿别的页面用过的文件去覆盖；
- **打开 = 追加 + 去重**：`append_pages()` 把新页插在"+"标签前；`_page_fingerprint()`（标题 + 节点名/坐标/绑定/参数 + 连线）与
  `_model_page_fingerprint()` 结构必须**完全一致**，用来跳过"工作区里已经有一模一样的一页"；
- **指纹规范化**：`_fingerprint_value()` 把数字 round 到 4 位，避免 `1` 与 `1.0`、`0.1+0.2` 造成"明明一样却判成不同"；
- **`params_by_image`**：方案里带"按图片存的参数"里**键是字符串**的那几份；加载时还原到节点的 `params_per_image`（否则"存了读不回来"）。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_page_title(page)` | 取页面标签标题 | 找不到返回空串 |
| `_page_fingerprint(page)` / `_model_page_fingerprint(page_model)` | 内容指纹（去重用） | 两者结构必须一致：标题 + 每个节点的名字 / 坐标 / 图像源绑定 / 参数 + 连线关系 |
| `_collect_page(page)` | 把一页收成可 JSON 化的 dict | `{title, nodes[{name,x,y,input_source,params,params_by_image}], edges[[i,j]]}` |
| `_collect_project()` | 把**当前这一页**收成方案 dict | 只收当前页（老实现收整张工作区，会把别的页面一起带出来） |
| `save_project()` | "保存方案" | 有 `project_path` 直接存；没有就当"另存为" |
| `save_project_as()` / `_write_project_file(path)` / `_update_project_title()` | 另存为 / 落盘 / 更新标题 | 落盘 = JSON；标题显示**当前页**的文件名 |
| `open_project()` | 菜单"打开方案" | 选文件后交给 `load_project()` |
| `load_project(path)` | 加载方案 | **先解析 + 校验（完全不碰界面）**，通过后才重建页面；不通过就原样返回、不破坏当前流程 |
| `_build_project_model(pages)` | 整理成"待应用模型" | 过滤没注册的算子 / 悬空连线 / 无效绑定，并记进 `warnings` |
| `_apply_project(model, data, project_path=None)` | 把模型**追加**成新页 | 建节点 → 恢复参数与 `params_by_image` → 恢复图像源绑定 → 连线（全程 `mark_dirty=False`）；末尾在"当前有静态图"时会**重画一次**（那次重画用 `_no_source_gallery_sync` 挡住"顺带补图库"） |

> **本章属于**：④ 状态与服务层

## flow_engine.py（core/flow_engine.py；1181 行；`FlowEngineMixin` —— 执行入口 / 数据流引擎 / 渲染 / 画面键）

**文件作用**：整个工程的**心脏**。三条路都从这里走：**执行**（单步 / 连续 / 批量的一张）、**渲染**（数据层 → 显示层）、
**显示键**（画面缩放 / 平移按谁记账）。

**关键设计与原理**：
- **数据层 / 渲染层彻底分离**：数据层是 `out_images[图像源]`（节点输出的图），渲染层是 `_render_display()` 最后统一画的一张**副本**；
  绿线 / 红圆 / 人脸框永远只活在渲染层；
- **执行顺序**：`_build_execution_order()` 用 **Kahn 拓扑排序**（老版广度优先在多上游时会乱序 ⇒ 下游取不到上游的图）；
- **单步 vs 连续**：单步 = **只跑选中那一个节点**（输入按它声明的"图像源"沿绑定往上追）；连续 = 整流程；
  **两者共用 `_run_nodes()`**（老实现单步另写一套，于是出了"单步不按图像源绑定取图"）—— 单步**不许**把上游链一起跑（否则两者结果一样，用户报过"最致命的错误"）；
- **ROI 继承**：`params["roi_source"]` 缺省 `"roi"`（沿用上游**实际用的框**，能穿过没有结果数据的算子）/ `"result"`（上游结果的最小外接框）；首选拿不到自动退回另一种；
- **结果缓存键** = 图片 × 页面 × 执行方式（`_result_cache_key`）；**画面键**另算（`_display_key_of`：静态图 = 路径，视频 = `"video:路径"` 整段共用）
  —— **一个标识不能同时承担"数据身份"和"视图身份"**（否则播放时每帧都被当新图 ⇒ 画面一大一小、缩放被吃掉）；
- **活源轮的三件事**（批次5目标5-M2）：`_video_used_by` / `_camera_used_by` 判断"这一轮真用到谁" ⇒
  ① 标签交给播放侧并写"视频帧 (n/总数)"；② `_canvas_shows_live = True`（删除判据用）；③ 写缓存的键换成**视频帧键**（不污染静态图的键）；④ 活源轮**不补图库**；
- **`show=False`** = 只算不显示（"运行全部"不勾「自动切换」时用），结果照旧进缓存、日志照旧写；
- **相机帧不进结果缓存**（无界流，缓存没意义还会线性涨内存）。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_show_static_image(frame)` | 显示一张静态图（导入 / 点缩略图） | 记当前图 → `_switch_image_params` → 有缓存就显示上次结果（并 `touch` 刷 LRU）、没缓存只显示原图；顺带清 `_canvas_shows_live` |
| `_result_cache_key(image_key, mode)` | 结果缓存键 | `(图片标识, 页面 key, 执行方式)` —— 同一张图在**不同页面**的结果互不干扰；单步的结果不会被连续覆盖 |
| `_execute_static(frame, mode, node=None, adopt_frame=True, show=True)` | **对一张图执行检测并显示** | 全工程唯一的执行路径：算 → 显示（`show`）→ 写缓存（★ 活源轮写**视频帧键**、相机轮不写）→ 淘汰一次 → 同步日志 / 数据 / 帮助页；`adopt_frame` 决定要不要把这一帧记成"当前图" |
| `_display_image(img, image_key=None)` | 渲染到视图 | 交给 `ImageGraphicsView.set_image`；传 `image_key` ⇒ 这张图的缩放 / 平移单独记账 |
| `_source_node_frame(allow_camera_open)` | 问当前页的源节点要一张图（兜底用） | 轮到相机源时**顺手开设备**（`allow_camera_open`）—— 判据是"是不是轮到它取图"，不是"有没有连线" |
| `_flow_source_frame()` | 这一轮的起点帧 | ① 主窗口已打开图片 / 视频 / 相机 ⇒ 用它；② 有源节点能出图 ⇒ 兜底用它；③ 都没有 ⇒ 返回 `(None, 提示语)`，由调用方弹提示 |
| `_build_execution_order(nodes, edges)` | 拓扑排序 + 上游表 | Kahn；返回 `(order, parents, skipped)` |
| `_upstream_closure(node, parents)` | 选中节点 + 全部上游 | 连续执行的范围（老版"拓扑序前缀"会把**无关分支**也跑掉） |
| `_node_modifies_image(node)` / `_resolve_input(...)` | 挑"真正产出新图"的一支 / 决定从哪份图开始算 | 图像源绑定：手动绑定 > 自动（最后一个上游，顺序确定 ⇒ 结果可复现） |
| `_resolve_roi(...)` | 算这一轮的 ROI | 绘制 / 继承上游（`roi_source` 两档，见上） |
| `_execute_node(...)` | 执行一个节点 | 参数校验（errors ⇒ **跳过并在日志说明**）→ `spec.run` → 处理通用错误通道 / 提示文案 |
| `_render_display(base_img, executed, draw_roi)` | 渲染层 | 复制数据层底图 → 按执行顺序画结果与 ROI 框 |
| `_run_flow_pipeline(frame, ...)` / `_run_flow_pipeline_step(frame, node)` | 连续 / 单步 | 前者整流程，后者只跑一个节点（输入沿绑定往上追） |
| `_run_nodes(order, parents, frame, ...)` | **单步与连续共用**的执行段 | 取输入 / ROI 继承 / 日志文案完全一致 |
| `_node_input_frame(node)` | 这个节点实际会收到的图 | 追到起点；参数窗口用它算 ROI 默认宽高（老实现只看主窗口当前图 ⇒ 和上游对不上） |
| `_bind_output_providers()` / `_source_kind_of()` / `_source_fps_of()` | 给输出节点绑"这一轮"的取名字 / 取图器 / 来源类型 / 标称帧率 | provider 是模块级 globals（进程里可能有多个 MainWindow）⇒ 每轮重新绑 |
| `_close_recordings(reason)` | 收尾所有录制文件 | 「停止」/ 播到末尾 / 换页 / 删节点 / 关程序 / 关相机都会调 |
| `_wants_overlay()` / `_origin_image_name(node)` / `input_image_name_of_node(node)` | 输出节点要的"保存内容 / 默认文件名 / 输入图名" | 默认叠加（纯处理链两档等价）；文件名默认 = 输入图片名 |
| `_binding_origin(node)` | 沿绑定追到最上头的起点节点 | 给日志写清"这一轮吃的到底是哪张图" |
| `_parent_nodes(node)` | 直接连到 node 的上游节点（按连线顺序） | 单步追链与 ROI 继承都用它 |
| `_format_result_text(spec, results)` | 日志"结果数据"列的文案 | 由节点注册表提供 ⇒ **新增算子不用改这里**；错误标记在这里变成红字前缀 |
| `_update_execution_log(exec_info)` / `_update_execution_log_throttled(...)` / `_append_log_hint(text)` | 刷日志表格 / 节流版 / 追加一行提示 | 视频每 30ms 一帧 ⇒ 表格重建要节流（内容一模一样就一格不动；变了最多每 0.2s 刷一次）；写完都 `scrollToBottom()` |
| `_display_key_of(frame)` / `_camera_display_key(node, mode)` | **画面键** | 来自文件的图 = 路径；视频 = `"video:路径"`、相机 = `"camera:编号"`（**整段共用**，见上"为什么"） |
| `_video_source_node()` / `_camera_source_node()` | 当前页的视频 / 相机源节点 | 找不到返回 None |
| `_result_note(results)` / `_result_error(results)` | 从 results 里取"日志文案" / "有没有声明出错" | 通用错误通道：`{"__note__": …}`（文案）、`{"__error__": True}`（那一行涂红） |

> **本章属于**：② 数据流引擎

## host_contract.py（core/host_contract.py；105 行；宿主契约 `MainHost`）

**文件作用**：把"7 个 Mixin 跨文件用到的宿主 `self.X`"**集中声明**在一处，让 PyCharm 不再报 ~120 条"未解析的特性引用"。

**关键设计与原理**：
- **运行时是空类**：所有声明写在 `if TYPE_CHECKING:` 里（恒 False）⇒ 零行为影响；
- 6+1 个 Mixin 都 `class XxxMixin(MainHost)` —— 用"**真实继承空类**"而不是 `if TYPE_CHECKING:` 包住基类（各家 IDE 支持不一致，不赌）；
- 声明**用脚本按实测算出**（AST 扫 `self.X` 引用 − 本文件定义），方法用 `name: Any` 声明而不是写 `def`（既能被调用、又不用维护签名）；
- 实测口径：**65 个名字 = 25 状态 + 40 方法**，消掉 6 个 Mixin 的 211 个引用点；
- 门禁用例 `dsh_t5g3_host_check.py` 防腐化：声明的名字都能在真实实例上取到 / Mixin 的跨文件引用都已声明 / 清单=依赖（多·少·重复都不行）/ **运行时 `vars(MainHost)` 除 dunder 外无成员**（防有人把实现写进契约）。

> **本章属于**：③ 公共工具

## result_cache.py（core/result_cache.py；109 行；结果缓存的上限 + 真 LRU）

**文件作用**：批次5 目标4-1。给 `self.result_cache`（仍是**普通 dict**，很多用例把它当 dict 用）加上"条数 + 字节"双上限与**真 LRU**。

**关键设计与原理**：
- **两个池**：静态图一池（400 条 / 256 MB）、**视频逐帧单独一池**（120 条 / 64 MB）—— 视频帧量大且"看过就没用"，不能把静态图挤出去；
  池的判据 = 键里带 `#`（`is_sequence_key`）；
- **真 LRU**：命中时 `touch()` 把该键移到 dict 末尾（O(1)）；淘汰时按"最久没用过"丢 —— 少了 `touch` 就是 FIFO 近似（刚看过的图照样被丢）；
- **纯逻辑、零 Qt**：`evict(cache)` 原地改 dict，返回被丢的键列表（调用方可写日志 / 断言）；
- 引擎侧：每次写完缓存就 `evict` 一次；`_show_static_image` 命中时 `touch` 一次。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `is_sequence_key(key)` | 是不是"视频逐帧"那一类键 | 图片标识里带 `#` |
| `frame_bytes(entry)` | 一条缓存占的近似内存 | 只算那张处理后的图（`data` / `exec_info` 都很小） |
| `touch(cache, key)` | 命中时移到末尾 | `cache[k] = cache.pop(k)` |
| `pool_stats(cache)` | 两个池各自的（条数, 字节） | 给用例 / 日志看 |
| `evict(cache)` | 按上限淘汰最久没用过的 | 分池各自淘汰；返回被丢的键 |

> **本章属于**：③ 公共工具

## commands.py（core/commands.py；301 行；撤销 / 重做的命令与栈）

**文件作用**：批次5 目标4-2 的**零 Qt 那一半** —— 6 个命令 + `UndoStack` + 参数快照工具。

**关键设计与原理**：
- **命令只存 uid**（不存对象）：撤销会销毁对象、重做是"重建一个新对象" ⇒ 存引用必然失效（实测出过"线飘""按钮灰了节点还在"两个 bug）；
  执行时用 `ctx.resolve(uid)` 取"现在活着的那个"，重建时**沿用同一个 uid**（身份连续）；
- **首次不执行**：界面已经把动作做完了，`push(cmd, execute=False)` 只入栈；`undo()` / `redo()` 返回被执行的那条命令；
- 删除类命令的状态（名字 / 坐标 / 参数 / 连线）必须在**删之前**采集（`UndoMixin` 负责），连线记的是**另一端节点的 uid**；
- `SetParamsCommand` 记 `image_key`（参数是按图片归档的 ⇒ 撤销要按同一张图恢复）；
- `MoveNodeCommand` 的坐标是**不透明对象**（本项目是 `QPointF`）—— 本文件不 import Qt，靠 `ctx.copy_pos()` / `ctx.move_node(uid, pos)` 碰它们；
- 栈上限 50（用户拍板），超了丢**最旧的**；变化时回调通知（不引 Qt Signal）。

| 名字 | 作用 | 实现原理与要点 |
|---|---|---|
| `class Command` | 动作基类 | `do()` / `undo()` / `text`（人话，写日志 / 菜单） |
| `AddNodeCommand(uid, name, ctx)` | 新建节点 | `undo` = 删；`do` = 用同一 uid **重建** |
| `RemoveNodeCommand(uid, state, links, ctx)` | 删节点（连带连线） | `links = [(另一端 uid, "out"/"in")]`；`undo` 把节点与连线一起放回 |
| `AddEdgeCommand(uid, src_uid, dst_uid, ctx)` / `RemoveEdgeCommand(...)` | 新建 / 删除连线 | 两端都是 uid（不是对象） |
| `SetParamsCommand(uid, name, before, after, image_key, ctx)` | 改参数 | undo / redo = 换成另一份参数字典快照；带 `image_key` |
| `MoveNodeCommand(uid, name, old_pos, new_pos, ctx)` | 拖动节点 | 一次拖动只记一条（宿主去抖后提交） |
| `class UndoStack(limit=50)` | 栈 | `push/undo/redo/clear`；`can_undo/can_redo/undo_text/redo_text/depth/redo_depth`；`add_changed_callback(fn)` 立刻回调一次 |
| `snapshot_params(params)` | 参数字典深拷贝 | 避免与节点里那份共享同一个 dict |

> **本章属于**：③ 公共工具

---

## camera_service.py（services/camera_service.py；326 行；`CameraMixin` —— 相机）

**文件作用**：相机设备的**开关 / 取帧 / 执行时自动打开 / 老预览分支**。方案 A（用户拍板）：**"相机源"节点复用主窗口的那一个相机**，不自己再开一路。

**关键设计与原理**：
- **"停止不关、删除才关"**（用户 2026.10.7 定）：`_release_camera_device()` 只在"删除 / 关程序"时被调；
  "停止"只停画面（最后一帧留在画布上）；
- **一轮只读一次帧**：`_begin_camera_round()` 每轮把计数器 +1、把记住的帧作废；`_latest_camera_frame()` 在**同一轮**里第二次被问就直接返回记住的那张 ——
  否则 `_flow_source_frame()` 和"相机源"节点会从设备里**各抠走一帧**（画面和实际算的不是同一张）；
- **老预览分支**（`self.timer` 30ms 直接读设备刷帧）与"相机源节点走引擎"**必须分开**：`_legacy_camera_preview_active()` 是分岔判据；
- **相机帧不参与"按图片归档"**：参数复用**视频槽**（用户定："相机和视频共用一份参数"）。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_open_camera_device(camera_id, quiet=False)` | 打开相机设备（内部 API） | 已开着同一编号 ⇒ **复用**；开着别的 ⇒ 先关再开；打不开返回 False；`quiet=False` 才弹警告（按钮路径用） |
| `_release_camera_device()` | 关设备、释放资源 | "删除才关"；M5-2 起相机一关，**正在录的视频也跟着收尾**（流没了文件必须 release） |
| `_latest_camera_frame()` | 注入给"相机源"节点的取帧器 | 相机没开 ⇒ None（节点原样透传 + 日志说明，不弹窗、也不自己乱开设备）；一轮只读一次（见上） |
| `open_camera()` / `close_camera()` | 主窗口"打开摄像头 / 关闭"按钮的老行为 | 界面表现一个字不变（保留给老用户习惯） |
| `update_frame()` | 老预览的定时器槽 | 读一帧显示到 `videoLabel`；**同时把"图像源 (n/N)"标签写成"相机画面"** |
| `_legacy_camera_preview_active()` | 老预览还在跑吗 | 用它的时候，单步 / 连续才走 `update_frame()` 老路；相机源节点必须走引擎正常路径 |
| `_ensure_camera_device_open(node)` | 把某个相机源节点要用的设备准备好 | 两条路径共用（执行前预开 / 取图时顺手开）；"执行时自动打开相机"这个开关**在这里统一判断** |
| `_begin_camera_round()` | 每轮开始让"相机读数"作废一次 | `_camera_round += 1`；配 `_latest_camera_frame` 用 |
| `_ensure_camera_open_for_run(node, mode)` | 执行前准备相机 | 这一轮**真用到**且没勾"自动打开"⇒ 不开；已开着同编号 ⇒ 复用；打开时顺带把参数切到**视频槽** |
| `_camera_used_by(node, mode)` | 这一轮有没有真用到相机源 | 单步：从节点沿父节点往上追；连续：相机源**只要有下游**就算用到 |
| `_camera_tick(node, mode)` | 相机画面的一格 | 只检查"相机还在不在"，然后走和手点**一模一样**的 `run_flow_step` / `run_flow_continuous`；顺带给标签上锁并写"相机画面" |

> **本章属于**：④ 状态与服务层

## video_service.py（services/video_service.py；243 行；`VideoMixin` —— 视频）

**文件作用**：视频的**帧游标推进 / 自动播放定时器 / 录制收尾**。

**关键设计与原理**：
- **"一次执行 = 前进一帧"**（用户 2026.10.6 定）：只有这一轮**真用到视频源**才吃帧（`_video_used_by`），且一轮只 +1；
- **★ 到末尾的处置分两条路**：播放那条（`_video_tick`）自己判"到末尾 ⇒ 勾了循环回卷 / 没勾停播"；
  **单步那条**（`_advance_video_cursor`）原本只 +1、没有末尾处理 ⇒ 用户实测"连点单步帧号一直涨（49/36）、画面停在第一帧" ⇒
  现在**在"没在播放"时**处理末尾（勾循环回卷 / 没勾停在最后一帧），**播放中不动**（老用例钉着那段行为）；
- **视频参数整段共用一份**（用户 2026.10.6 定）：换路径时载入一次，之后**绝不每帧载**（否则覆盖用户播放中刚改的参数）；
- **"停止"只停画面**（相机不关、最后一帧留着），并**收尾正在录制的视频文件**；
- **定时器是 QTimer 不是死循环**：界面不卡，任意两帧之间"停止"都能立刻生效。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_maybe_load_video_params()` | 视频参数整段共用的**载入侧** | 只在**换路径**时载一次（同一段视频不重复载） |
| `_maybe_start_video_playback(node, mode)` | 勾了「自动切换」⇒ 执行结束后接着自动出画面 | 只在"这一轮真用到视频 / 相机"且**不是**播放中的那一帧 tick 时启动（避免播放里再套播放）；**这里也是相机 / 视频的分派口** |
| `_start_camera_playback(...)` | 相机自动出画面 | 相机是无界流：没有帧号 / 末尾 / 循环，一直出到"停止"；与视频**共用同一个** `_video_timer` |
| `_advance_video_cursor()` | 执行后前进一帧 | 见上"到末尾的处置"；`auto_next` 关掉时不动 |
| `_start_video_playback(node, mode)` | 开始自动播放 | 帧间隔 = `1000 / fps`（读不到按 25）；播到末尾按 `loop` 回卷或停 |
| `_stop_video_playback(reason)` | 停止自动出画面 | "停止"按钮 / 播到末尾 / 相机关掉都走这里；写日志"停止播放：…"；**把标签交还图库**（`set_count_locked(False)`） |
| `_video_tick(node, mode)` | 自动播放的一帧 | 先看要不要停 → 相机走相机那支 → **给标签上锁并写"视频帧 (n/总数)"** → 按 `mode` 跑一帧 |
| `_video_used_by(node, mode)` | 这一轮有没有真用到视频源 | 同 `_camera_used_by` 的两种判法 |

> **本章属于**：④ 状态与服务层

## gallery_service.py（services/gallery_service.py；491 行；`GalleryMixin` —— 图库 + 批量执行）

**文件作用**：图像列表（图库）的**导入 / 删除 / 切换 / 运行范围**，以及 **"运行全部"的分片批量执行**。

**关键设计与原理**：
- **点击图库 = 切画面 + 切参数**（`_show_static_image`）：这张图执行过 ⇒ 直接显示上次结果；没执行过 ⇒ 只显示原图；
  ★ **例外**（批次5目标5-M1 用户拍板"甲"）：**视频 / 相机正在播时点图库只改选中项**，不碰画面与参数 ——
  否则会"闪一帧"（静态图被画出来又被视频帧盖掉）+ 缩放串扰 + 参数污染；
- **删除语义**（批次5目标5-M2，两轮修正后定稿）：**"删除" = 一次点掉"当前画布上显示的那个东西"** ——
  活源（正在播 / 相机开着 / 画布是视频帧或活源帧 / 活源流程 + 画布空）⇒ 停播 + 关相机 + **清画布 + 清视频源路径**（不动图库条目）；
  否则 ⇒ 删那条图库条目（**连带清它的参数存档 / 结果缓存 / 缩放记录**）。**"停止"才是只停播**；
- **删条目之后必须清"图片源"的路径**（`_clear_source_nodes_path`）：否则点执行那张图又会被跑出来；
- **批量执行是分片的**（批次5 目标3）：一张图 = 一片，片间 `QTimer.singleShot(0, …)` 让出事件循环 ⇒ 界面不卡、**"停止"真的能中断**；
  `follow`（跟不跟画布）在**批量开始时定格**（中途拨开关不影响正在跑的这一批）；
- **收尾要还原**（`_batch_finish`）：不勾「自动切换」时临时改过的选中项 / 图片源 / 画面都要放回去（用户 2026.10.6 定）；
- **相机帧 / 视频帧不进图库**：图库只装"静态图片"；
- ★ **活源轮不"补图库"**（2026.10.16 探针定案）：`_ensure_source_images_in_gallery()` 会把当前页「图片源」节点那张图加进图库 ——
  但**活源轮**加了会让人误以为"相机第一帧进了图库" ⇒ 引擎侧用 `_canvas_shows_live` 挡住；**静态图轮保留**（用户 2026.10.5 定的"图库里看得见"）。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_is_playing()` | 正在播视频 / 相机吗 | `_video_playing or _camera_playing`；M1「播放中点图库」与 M2「删除 / 连续执行」共用 |
| `_on_gallery_image_selected(img_bgr)` | 点图库里的图 ⇒ 切主画面 | **播放中直接返回**（见上"例外"）；否则 `_show_static_image()` |
| `_on_gallery_path_selected(path)` | 点图库里的图 ⇒ 同步"图片源"路径 | 图库与图片源节点**统一**（用户 2026.10.5 要求） |
| `add_folder_to_gallery()` | 工具栏"＋文件夹" | 系统原生选文件夹 ⇒ `import_folder_path` ⇒ 刷新标签 |
| `delete_gallery_item(item)` | 「删除」（见上"删除语义"） | 相机开着 ⇒ 关相机（相机源节点参数保留）；活源在画布 ⇒ 清画布 + 清 `video_path`；否则删条目 + 清它的三样东西 |
| `run_all_images(mode="continuous")` | **"运行全部"入口**（分片批量） | 开始前把 `follow`（自动切换）/ 范围 / 起始选中项收拾好；`_batch_step` 一片一片跑 |
| `_batch_step()` | 跑一片（一张图） | `_execute_static(..., show=follow)`；片间 `QTimer.singleShot(0, …)` 排下一片；每片开头读 `_batch_stop` |
| `_batch_finish(hint)` | 批量收尾 | 还原因"不勾自动切换"临时改掉的选中项 / 图片源 / 画面；写收尾日志；清分片上下文、复位"停止"标志 |
| `_on_auto_switch_changed(checked)` | 「自动切换」被拨动 | 只写提示；**不影响正在跑的那一批**（`follow` 已在开始定格） |
| `stop_batch()` | 「停止」 | 中断批量 + 停播放 + **收尾录制文件**；分片之后"停止"在下一片开头就被读到 |
| `_sync_source_nodes_to_path(path)` / `_clear_source_nodes_path(path)` | 图库 ⇄ 图片源节点路径同步 / 清空 | 点图库 ⇒ 图片源吃这张；删这张图 ⇒ 把图片源里那条路径清掉（否则点执行它又出现） |
| `_ensure_source_images_in_gallery()` | 把"图片源"节点那张图也加进图库 | 按路径去重；**活源轮由引擎侧挡住不调**（见上） |
| `import_image_path(path)` / `import_folder_path(folder)` / `import_paths(items)` | 导入一张 / 一个文件夹 / 统一入口 | 读不出来的**静默跳过**（用户要求）；不递归子目录；返回 `[(frame, path), …]` |

> **本章属于**：④ 状态与服务层

## undo_service.py（services/undo_service.py；429 行；`UndoMixin` + `_UndoContext` —— 撤销 / 重做）

**文件作用**：批次5 目标4-2 的**宿主侧那一半** —— 把界面发生的动作翻译成 `core/commands.py` 的命令，并把命令执行时需要的"翻译层"（uid ⇄ 活对象）实现出来。

**关键设计与原理**：
- **身份连续（uid）**：`_UndoContext` 维护 `uid → 活对象` 注册表。撤销会销毁对象、重做是**重建新对象** ⇒
  命令只存 uid，执行时 `resolve(uid)` 取"现在活着的那个"；重建时**沿用同一个 uid**。
  `resolve()` 做**两层探活**：① 还在不在 `host.flow_nodes` 里（`scene.removeItem` 只解除场景归属，对象其实还活着）；
  ② C++ 对象是否已销毁（`RuntimeError`）；
- **删除类命令先采集、并 `forget(uid)`**：`_undo_note("remove_node" / "remove_edge")` 在**界面真删之前**把状态收下，
  再把 uid 从注册表摘掉（否则下次解析到"僵尸对象"）；
- **栈是"每页一条"**（用户 2026.10.15 口径："换页之后还要能撤销"）：`_undo_stacks[页 key]`；
  换页**只切换、不清空**；导入 / 新建的页面第一次用到时栈是空的 ⇒ **撤销最多撤到"刚导入时"**；
- **拖动能去抖**：拖动期间只攒 `move_pending`，400ms 后 `_commit_pending_moves()` 提交成**一条**命令；
- **参数按图片恢复**：`apply_params(uid, snapshot, image_key)` —— 是当前图才改 `node.params`，是别的图就**只改那张图的存档**；
- **撤销 / 重做要同步"未保存"标记**：撤到栈底（回到这一页的基线）⇒ `clear_dirty`；重做 ⇒ `mark_dirty`（否则"全部撤销后关页还问要不要保存"）；
- **入口统一兜底**：`_run_stack_step()` 挡记录（`_undo_busy`）+ 异常兜底 + 写一行日志。

| 名字 | 作用 | 实现原理与要点 |
|---|---|---|
| `_UndoContext.ensure_uid(node)` / `bind_edge(edge)` / `_next_uid()` | 发 / 取 uid | 节点、连线各一发；方案里读出来的对象也会在这里补上 |
| `resolve(uid)` / `resolve_edge(uid)` / `forget(uid)` / `forget_edge(uid)` | uid ⇄ 活对象 | 两层探活（见上）；`forget` 用在"界面马上要删"之前 |
| `create_node(uid, name, pos)` / `drop_node(node)` | 建 / 删节点 | 比界面入口**少一步"记命令"**（避免递归记录） |
| `capture_node(node)` / `capture_links(node)` | 采集节点状态 / 它牵扯的连线 | `(名字, 坐标, 参数深拷贝)`；links = `[(另一端 uid, "out"/"in"), …]` |
| `create_edge(uid, src_uid, dst_uid)` / `drop_edge(edge)` | 建 / 删连线 | 两端都是 uid |
| `apply_params(uid, snapshot, image_key=None)` | 换成这份参数快照 | 见上"参数按图片恢复" |
| `move_node(uid, pos)` / `copy_pos(pos)` | 挪节点 / 拷坐标 | `setPos` 会触发 `positionChanged` ⇒ 连线自动刷新；拷坐标放这儿（`core/commands.py` 不 import Qt） |
| `UndoMixin._init_undo()` | 初始化（`__init__` 里调，**在 `setup()` 之前**） | 建 `_undo_stacks`（每页一条）+ 一个**占位栈** + 四项控件回调 |
| `_stack_for(page_key)` | 取某一页自己的栈 | 没有就建一个**空**栈（= 以这一页"刚出现时"为基准） |
| `_bind_undo_stack_for_page()` | 换页 / 载入方案 / 新建页面后绑定当前栈 | **不清空**历史；顺手丢掉已删页面的栈；立刻同步按钮 enabled |
| `_undo_note(kind, payload)` | 记一条命令 | `kind` ∈ add_node / remove_node / add_edge / remove_edge / set_params / move_pending / move_node |
| `_commit_pending_moves()` | 把攒着的拖动提交成命令 | 一次拖动一条（起点 → 终点） |
| `_undo_remember_node(node)` | 记节点"上一次提交过的坐标" + 发 uid | 建节点与绑页面两处都调（新建的、从方案读出来的第一次拖动都能撤回原位） |
| `_on_undo_stack_changed(stack)` | 栈变了 ⇒ 四项控件联动 | ★ 用 `getattr` 取控件（占位栈建好会立刻回调一次，那时 `.ui` 控件还没找出来） |
| `_run_stack_step(method_name, verb)` | 撤销 / 重做的公共部分 | 挡记录 + 异常兜底 + 写日志 + 同步脏标记 |
| `undo()` / `redo()` | 撤销 / 重做一步 | 菜单 / 按钮（以后 Ctrl+Z）都走这里 |

> **本章属于**：④ 状态与服务层

---

## ops/ 总述（算子：**一个节点一个文件**，14 个节点）

**放什么**：所有**算子**（算法 + 参数声明 + 绘制）。按"树干"（用户在树里看到的分组）分目录：

| 目录 | 节点 | 数量 |
|---|---|---|
| `ops/source/` | 图片源 / 视频源 / 相机源 | 3 |
| `ops/process/` | 灰度 / 取反 / 滤波 / 二值化 / 形态学 / 边缘提取 | 6 |
| `ops/detect/` | 直线识别 / 圆识别 / 人脸识别 | 3 |
| `ops/sink/` | 输出图像 | 1 |
| `ops/color/` | 颜色提取 | 1 |

**每个节点文件里的"三件套"**（约定，缺一不可）：
1. **算法函数**（纯算法，签名 `(img, roi, params) -> 新图` 或 `(img, roi, params) -> (新图, results)`）；
2. **`_run_*` 引擎入口**（引擎只会调它；它内部再调算法）+ **`_draw_*`**（检测类才有，把结果画到显示层）+ **`_format_*`**（写日志"结果数据"列的短文案）；
3. **`*_SPECS` 声明表**（`NodeSpec` 的原料：名字 / kind / 参数表 / 校验函数 / 注册分组）+ **`validate_*`**（参数校验规则）。

**三条共同铁律**：
- **绝不就地改传入数组**（处理类一律走 `core/ImageOps.apply_to_roi()` 的"copy 出来 → 只在 ROI 改 → 回填"）；
- **输出永远 3 通道 BGR**（`to_bgr()` 兜底，单通道丢给下游 `cv2.line` / HoughCircles 会抛）；
- **读不到数据 / 出错 ⇒ 原样透传 + 把说明写进 `results`**（日志里写清楚，**绝不弹窗**）；
  标记 `{"__error__": True}` 会让那一行**显示成红字**（通用错误通道）。

**加一个算子的完整步骤**：① 在 `ops/<树干>/` 建一个文件（三件套）；② 在 `core/NodeRegistry.py` 末尾的注册区加**一行**登记；
③ 在 `main.ui` 的树里加一项。**不用改引擎、不用改参数窗口**（通用窗口按参数表自动生成）。

> **本章属于**：⑤ 算子实现

## ops/source/（3 个图像源节点文件）

**文件作用**：三种"起点"节点 —— 它们**没有输入**（流程最上游），只负责"这一轮吐哪张图"。

**关键设计与原理**：
- 图像源节点**不看传入的图与 ROI**（"当前图像"这个来源会把传入的 `None` 原样返回）；
- **视频帧游标只读、不在这里前进**：前进由引擎在"这一轮真用到视频源"时调 `_advance_video_cursor()`（一次执行 = 前进一帧）；
- **相机走"注入的取帧器"**（方案 A：节点复用主窗口相机）；相机帧**不进结果缓存、不进图库**；
- 三个节点都属于 `NodeSpec.is_flow_level()`（它们的"来源 / 路径"是**流程图级**配置，不按图片归档）。

| 文件 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `ImageSourceOps.first_image_in_folder(path)` | 文件夹里按名排序的第一张图 | 兼容"路径其实是一张图"（返回它自己）；不存在 / 没图片 ⇒ None |
| `ImageSourceOps._load_image(path)` | 读图（带缓存） | 走 `core/ImageIO.read_image`（中文路径）；失败返回 None |
| `ImageSourceOps._cached_test_image()` | "测试图"只生成一次 | 用 `core/Detector.make_test_image()` |
| `ImageSourceOps.run_source(detector, img, roi, params)` | 按 `source_type` 决定输出哪张图 | 三档：图片 / 文件夹 / 测试图；来源说明塞进 `results` 的一个 dict（`format_result` 只拿得到 `results`；引擎的 `result_bbox()` 会跳过 dict） |
| `ImageSourceOps.format_source(results)` | 日志"结果数据"列 | 短文案（这一列会截断） |
| `VideoSourceOps._open_video(path)` | 按 `(路径, mtime, 大小)` 缓存 `VideoCapture` | 返回 `(cap, 总帧数, 帧率)`；打不开 `(None, 0, 0.0)` |
| `VideoSourceOps.video_info(path)` | 给主窗口用 | `(总帧数, 帧率)`（标签写"视频帧 (n/总数)"、播放间隔都用它） |
| `VideoSourceOps.run_video(...)` | 读"当前帧号"那一帧（**只读、不前进**） | 读不到（文件没了 / 帧号越界 / 坏文件）：`loop` 开着 ⇒ 回第 0 帧再读；仍失败 ⇒ **原样透传 + 一条说明** |
| `VideoSourceOps.format_video(results)` | 日志文案 | — |
| `CameraSourceOps.set_camera_frame_provider(fn)` | 主窗口注入"相机最新一帧"取帧器 | 模块级 globals（进程里可能有多个 MainWindow）⇒ 每轮重新绑 |
| `CameraSourceOps.run_camera(...)` | 取主窗口相机最新一帧 | 取不到就透传 + 说明（不弹窗、也不自己乱开设备） |
| `CameraSourceOps.format_camera(results)` | 日志文案 | — |

> **本章属于**：⑤ 算子实现 · 采集

## ops/process/（6 个处理类节点文件）

**文件作用**："处理"这一大类的算法实现与参数声明。**处理类的共同语义：输出图像和输入不一样，下游看得见**（`NodeSpec.modifies_image() == True`）。

**关键设计与原理**：
- 全部跑在 `core/ImageOps.apply_to_roi()` 这个"通用外壳"上（签名 `(img, roi, params) -> 新图`）；
- **灰度是唯一带"作用于整图"的**（`gray_full_image` ⇒ 引擎把 ROI 当整图，"所见即所算"）；
- 形态学的**7 档共用一个节点**：OpenCV 里它们是同一个 API（`cv2.morphologyEx`）的不同 `op`，参数完全一样 ⇒ **参数同构就合并**；
- 参数校验的价值在于"**消灭静默**"：二值化越界 OpenCV 不报错只是饱和；Canny 高低阈值填反 OpenCV 自己会交换 —— 用户看着"能跑"却与预期不符 ⇒ 规则里夹范围 / 互换并把纠正写进日志。

| 文件 | 算法函数 | 参数声明 / 校验 | 实现原理与要点 |
|---|---|---|---|
| `process/GrayOps.py`（55 行） | `to_gray` / `gray` | `GRAY_SPECS` | 输出**始终 3 通道 BGR**（下游要 3 通道）；`gray_full_image` 为真 ⇒ 整图 |
| `process/InvertOps.py`（33 行） | `invert` | `INVERT_SPECS` | ROI 内 `255 - x`（最简节点，无参数校验） |
| `process/BlurOps.py`（68 行） | `blur` | `BLUR_SPECS` + `validate_blur` | 均值 / 高斯 / 中值；核大小取 `[1,31]` 的**奇数**（偶数 OpenCV 直接抛）、高斯 σ 夹 `[0,20]` |
| `process/ThresholdOps.py`（72 行） | `threshold` | `THRESHOLD_SPECS` + `validate_threshold` | 固定 / Otsu / 自适应（先转灰度再补回 3 通道）；阈值与最大值夹 `[0,255]` |
| `process/MorphologyOps.py`（78 行） | `morphology` | `MORPHOLOGY_SPECS` + `validate_morphology` | 腐蚀 / 膨胀 / 开 / 闭 / 梯度 / 顶帽 / 黑帽（7 档一个节点）；核大小奇数、迭代 `[1,10]` |
| `process/EdgeExtractOps.py`（80 行） | `edge` | `EDGE_SPECS` + `validate_edge` | Canny / Sobel / Laplacian；核大小奇数；Canny 低/高阈值夹 `0~500` 且**填反时互换**（`cv2.Canny` 内部自己会交换，用户看不出问题） |

> **本章属于**：⑥ 算子实现 · 处理类

## LineDetectOps.py（ops/detect/LineDetectOps.py；166 行；直线识别）

**文件作用**："检测 / 识别"这一大类的算法 + 绘制。**检测类的共同语义：图像输出 = 输入不变（原样透传），只多出结构化结果**（`modifies_image() == False`）。

**关键设计与原理**：
- 算法**只在 ROI 的一份副本上跑**，结果数据按**原图坐标**返回；画的线只进**显示层**（数据层一个像素都不动）；
- `_run_line` 里对 `patch` 后面跟一个 `.copy()`：`line_detector()` 会**顺手把绿线画进传进去的数组**（那是它的副作用）⇒ 不 copy 就会污染输入；
- 三个检测节点**同构**（同一套 `_run_ / _draw_ / _format_ / validate_ / *_SPECS`）。

| 名字 | 作用 | 实现原理与要点 |
|---|---|---|
| `class LineDetector.line_detector(img, ...)` | 直线检测算法 | Canny 找边 + `HoughLinesP` 找线段；**副作用**：把绿色线段画进传入数组 |
| `_run_line(detector, img, roi, params)` | 引擎入口 | 只在 ROI 副本上跑；结果按原图坐标返回；图像原样透传 |
| `_draw_line(display_img, results, params)` | 画到显示层 | 绿色线段（与算法里同一画法） |
| `_format_line(results)` | 日志"结果数据"列 | 短文案（这一列会截断） |
| `validate_line(spec, params)` | 参数校验 | Canny 高低阈值（夹范围 + **填反互换**）、累加器阈值、最小线段长度、最大线段间隙 |
| `LINE_SPECS` | 声明表 | 注册进 `NodeRegistry` |

> **本章属于**：⑦ 算子实现 · 检测类

## CircleDetectOps.py（ops/detect/CircleDetectOps.py；135 行；圆识别）

**文件作用**：圆检测（`HoughCircles`）—— 与 `LineDetectOps.py` **同构**。

| 名字 | 作用 | 实现原理与要点 |
|---|---|---|
| `class CircleDetector.circle_detector(img, ...)` | 圆检测算法 | 累加器分辨率 `dp` / 圆心最小距离 `min_dist` / `param1`（Canny 高阈值）/ `param2`（累加器阈值）；**副作用**：在原图上画红圆 |
| `_run_circle(detector, img, roi, params)` | 引擎入口 | 只在 ROI 副本上跑，数据层图像透传 |
| `_draw_circle(display_img, results, params)` | 画到显示层 | 红色圆 + 红色圆心 |
| `_format_circle(results)` | 日志文案 | 短文案 |
| `validate_circle(spec, params)` | 参数校验 | `param1 / param2 ≥ 1`、`dp`、`min_dist`（界面够不到，挡方案文件） |
| `CIRCLE_SPECS` | 声明表 | 注册进 `NodeRegistry` |

> **本章属于**：⑦ 算子实现 · 检测类

## FaceDetectOps.py（ops/detect/FaceDetectOps.py；201 行；人脸识别）

**文件作用**：人脸识别（`CascadeClassifier.detectMultiScale`）。它的**级联文件是"节点级参数"**（`per_node: True` ⇒ 换图 / 换视频 / 换页都不重置），
出错走**通用错误通道**（日志那一行显示成红字）。

**关键设计与原理**：
- **加载失败不抛异常**：`_load_cascade()` 返回 `(分类器, 错误说明)`，说明塞进结果 ⇒ 调用方原样透传图像 + 日志写红字（用户在界面上能看到原因）；
- `_error()` 包一行"错误结果"：`__note__` 是日志文案、`__error__` 让那一行**变红**（见 `flow_engine._format_result_text` / `_update_execution_log`）；
- 用 `results` 里的 dict 递文案是引擎的老约定（`result_bbox()` 只认 tuple/list，会跳过 dict）。

| 名字 | 作用 | 实现原理与要点 |
|---|---|---|
| `_load_cascade(params)` | 取（必要时加载）级联分类器 | 返回 `(分类器, 错误说明)`；失败**不抛异常** |
| `_error(text)` | 包一行"错误"结果 | `{"__note__": 文案, "__error__": True}` ⇒ 日志红字 |
| `_run_face(detector, img, roi, params)` | 引擎入口 | 只在 ROI 里找人脸，按**原图坐标**返回两个角点；出错时 `(图像, [一句说明])` |
| `_draw_face(display_img, results, params)` | 画到显示层 | 绿色矩形（只画显示层） |
| `_format_face(results)` | 日志文案 | 短文案 |
| `validate_face(spec, params)` | 参数校验 | 实测依据（cv2 4.13）：`scaleFactor ≤ 1` **直接抛异常** ⇒ 夹到 > 1；`minNeighbors` 等一并夹 |
| `FACE_SPECS` | 声明表 | 级联文件那一项带 `per_node: True` |

> **本章属于**：⑦ 算子实现 · 检测类

## OutputOps.py（ops/sink/OutputOps.py；517 行；输出图像 = "输出类"算子）

**文件作用**：批次4 目标3-M5。把"这一轮"的内容**写到磁盘**（图片序列或视频文件），同时把图像**原样透传**给下游
（所以它放流程**中间**或**末尾**都行，`kind = KIND_SINK`）。

**关键设计与原理**：
- **它什么都不改**（`modifies_image() == False`）：只往外送结果，不参与算法；
- **参数是流程级**（输出目录 / 文件名 / 格式 / 保存内容不跟图片走）；**输出目录必须手填**（不猜、不自动建），**文件名默认 = 输入图片名**，重名**自动编号**（"关软件 → 隔天再跑"也不会覆盖上次的）；
- **两档保存内容**：`数据层图像` / **`带检测叠加`（默认）** —— 因为检测类不改数据层，只存数据层等于存原画面；两档在纯处理链上**逐像素一样**，所以默认叠加不改变旧行为；
  叠加**只画检测结果、不画 ROI 辅助框**；
- **输出类型三档默认"自动"**：来源是图片源 ⇒ 图片序列；是视频源 / 相机源 ⇒ **视频文件**（默认 MP4 · `mp4v`，不做 H.264：本机缺 openh264）；
- **帧率口径 = "每写一帧算一帧"**（标称帧率只影响播放速度）；
- **6 处收尾挂点**：「停止」/ 播到末尾 / 换页 / 删节点 / 关程序 / 关相机 —— 都走 `close_all_recordings()`；
  尺寸或参数变了 ⇒ 收尾旧文件另开新文件；**0 帧删空文件**；
- 主窗口通过 4 个"注入器"（模块级 globals）把"这一轮的执行上下文"告诉它：轮次信息 / 叠加帧 / 输入文件名 / 录制收尾。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `set_round_info_provider(fn)` / `current_round_info()` | 注入 / 取"这一轮的执行上下文" | 拿不到就返回空字典（各处默认值兜住）；**每轮重新绑**（多窗口） |
| `set_overlay_frame_provider(fn)` / `current_overlay_frame()` | 注入 / 取"这一轮带检测叠加的那张图" | 拿不到 ⇒ 退回数据层图像 |
| `set_input_name_provider(fn)` / `current_input_name()` | 注入 / 取"这一轮输入图片的文件名" | 文件名默认值就靠它 |
| `_sanitize_name(name)` | 清洗成磁盘合法文件名 | 空 ⇒ `"output"` |
| `_resolve_dir(path)` | 输出目录解析成绝对路径 | **相对路径相对工程根**（不能靠当前工作目录：换目录启动就写歪） |
| `_scan_next_index(dir, ...)` / `_next_auto_index(...)` | 自动编号 | 扫目录里 `名字_数字.后缀` 取最大 +1；带缓存 + 存在性兜底 |
| `_free_path(...)` | 找一个没被占用的路径 | 撞名就加 `_1` / `_2`（时间戳策略会撞，绝不能覆盖） |
| `build_output_path(node)` | 算这一次要写的完整路径 | `ext` 可指定（视频模式）；返回 `(路径, 说明)`，空路径 = 参数不完整 |
| `_resolve_fps(node)` | 录制标称帧率 | ① 参数手填 `>0`；② 来源帧率；③ 兜底 25 |
| `_close_recording(node)` / `close_recording(node)` / `close_all_recordings()` / `recording_count()` | 收尾录制 / 数量 | release 编码器；**一帧没写就删空文件**；返回给日志用的一句话 |
| `_save_image_file(...)` | 图片序列模式 | 写一张图（`core/ImageIO.write_image`，中文路径 OK） |
| `_save_video_frame(...)` | 视频文件模式 | **第一次执行到本节点时自动开始录制**（用第一帧定尺寸与帧率，日志"开始录制 → …"，之后写"录制中：…（第 n 帧）"） |
| `run_save(detector, img, roi, params)` | **输出节点入口** | 写盘 → **原样透传** `img`；返回 `(img, [{"输出图像": 文案}])` |
| `format_save(results)` | 日志"结果数据"列 | 短文案 |

> **本章属于**：⑧ 算子实现 · 输出

## ColorExtractOps.py（ops/color/ColorExtractOps.py；172 行；颜色提取）

**文件作用**：树里「**颜色处理**」这个树干下的唯一节点（2026.10.14 新建树干）：**阈值内保留原色、阈值外置黑**。

**关键设计与原理**：
- 双模型 **HSV / RGB**（用户原话："可以选择 HSV、RGB 等模型"），各自 6 个阈值；
- **`cv2.inRange` 对"下限 > 上限"不报错，而是整幅图都不命中（全黑）** ⇒ 参数校验里**自动互换**并把纠正写进日志（消灭"提取出一片黑"这种静默）；
- 阈值界面用 `slider_int`（进度条 + 微调框，真范围 + 软范围双向联动）；
- 结果里带**像素计数**，日志写"提取到 N 个像素（x.x%）"。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_limits_for(model, params)` | 按模型取 `(下限, 上限)` 两组分量 | 返回长度 3 的 int 元组（RGB 时是 R,G,B；HSV 时是 H,S,V） |
| `run_color_extract(detector, img, roi, params)` | 颜色提取（处理类） | ROI 内 `inRange` 掩码 ⇒ 掩码内保原色、掩码外置 0；ROI 外原样；返回 `(新图, [结果 dict])` |
| `_format_extract(results)` | 日志文案 | 短文案 + 像素计数 |
| `validate_color_extract(spec, params)` | 参数校验 | 按**当前模型**夹 6 个阈值 + **下限 > 上限自动互换** |
| `COLOR_SPECS` | 声明表 | 13 个参数（1 个模型 + 12 个阈值），阈值用 `slider_int` |

> **本章属于**：⑨ 算子实现 · 颜色处理

---

## LineParamsDialog.py（ui/LineParamsDialog.py；1242 行；**参数窗口基类**）

**文件作用**：所有算子参数窗口的**基类**（直线直接用它；圆 / 灰度 / 通用都继承它）。它管四件事：
① ROI（绘制 or 继承上游、形状、外扩、框选窗口）；② **图像源绑定**下拉框；③ **"运行参数"页**（子类往里面填行 / 或由通用窗口按声明表生成）；
④ 三个按钮（执行 / 连续执行 / 确定）+ **参数校验提示行**。

**关键设计与原理**：
- **ROI 两种创建方式**：`绘制`（自己框，含"外扩"）与 `继承上游`（选"继承自"哪个上游），互斥显隐；
- **图像源绑定不是"运行参数"**（不跟图片走）：`自动` = 沿连线继承上游输出；`全局图像源` = 只看原图；绑到"图片源"= 用它的图；
  **绝不能存进 `params`**（老坑：存了就会被"按图片归档"清掉，表现为"绑了却不生效"）；
- **软范围**（用户 2026.10.7 要求）：数值控件允许填到真范围之外（打错字不弹错），**提交时**夹回真范围并写进提示行；
- **提交前先 `_commit_number_edits()`**：把"打了字但没回车 / 没失焦"的输入提交掉（`value()` 读的是已提交值，否则用户以为白填）；
- **提示行不改变窗口大小**（用户要求）：把"运行参数"分组放进 `QScrollArea`，装得下就没滚动条、装不下自动出竖直条；
  **横向条永久禁用** ⇒ 必须用 `_sync_scroll_min_width()` 保证"窗口不允许被缩到装不下内容"（否则右边被**静默裁掉**）；
- **执行 / 渲染路径绝不弹 `QMessageBox`**：参数被纠正 / 出错都只写提示行与执行日志（黄字 = 纠正、红字 = 会被引擎跳过）；
- **"执行"不关窗、"确定"执行一次再关**（用户的肌肉记忆）。

| 函数 / 类 | 作用 | 实现原理与要点 |
|---|---|---|
| `class ROISelectGraphicsView` | 框选画布 | `get_roi()` 返回 `(x, y, w, h)`；矩形 / 圆两种形状 |
| `class ROISelectDialog` | 框选窗口 | 拿一张图让用户拉框，回车返回 ROI |
| `_candidate_sources()` | 列出能当图像源的**上游**方框 | 直接上游优先，再往上一层 |
| `_populate_input_source()` | 填"图像源"下拉框 | 第 1 项自动（默认）/ 第 2 项全局图像源 / 之后是各个上游起点节点 |
| `_on_input_source_changed()` / `_save_input_source()` | 改了就写回节点 | 绑定**不跟图片走** |
| `_load_params()` / `_update_params()` | 参数 ⇄ 控件 | 子类重写后 `super()` 调它；ROI 用当前图尺寸当默认 |
| `_apply_soft_range()` / `_clamp_soft_range()` / `_soft_range_all()` | 软范围 | 幂等（同一控件只装一次）；提交时夹回 |
| `_commit_number_edits()` | 提交未回车的输入 | 读参数之前必做（见上） |
| `_build_validate_hint()` / `_validate_widget_for()` / `_apply_fixed_to_widgets()` / `_show_validate_hint()` | 校验提示三件套 | 纠正过的值**必须写回控件**（否则用户以为填的还是原值，而引擎已按纠正值跑 —— 目标4 要消灭的"静默"） |
| `_wrap_run_params_in_scroll()` / `_tighten_param_rows()` / `_sync_scroll_min_width()` | 布局护栏 | 每行末尾补弹簧 + 标签统一宽度（控件左缘对齐）；最小宽 = 内容最小宽；`_grow_for_hint()` 已废弃（保留作历史参考） |
| `_validate_params()` | **窗口层**跑一遍参数校验 | 返回 errors（窗口层只提示、不拦人） |
| `on_step_click()` / `on_cont_click()` / `on_ok()` | 三个按钮 | 分别调 `main_window.run_flow_step` / `run_flow_continuous`；`on_ok` = 执行一次 + 关窗（起点节点只保存） |
| `toggle_roi_params()` / `_update_roi_params_visibility()` / `_set_roi_margin_visible()` / `_set_roi_source_visible()` | ROI 区域显隐 | 按"绘制 / 继承上游"单选与下拉值切换 |
| `_update_shape_layout()` | 形状下拉联动 | 矩形 ↔ 圆：参数框标签名与可见性随之变 |
| `on_select_click()` | "框选"按钮 | 取当前图（图片 / 视频帧 / 相机帧）⇒ 弹 `ROISelectDialog` ⇒ 回填 XYWH |
| `refresh_size()` | 外部让窗口重算尺寸 | 主窗口加载图片后调用 |
| `update_result_count(data)` | 显示结果数量 | 子类按各自的结果改写文案 |

> **本章属于**：⑩ 参数窗口

## GenericProcessDialog.py（ui/GenericProcessDialog.py；603 行；通用参数窗口）

**文件作用**：**按算子的 `param_specs` 自动生成"运行参数"页** —— 这是"新增算子不用改界面"的关键。
起点类节点（图片源 / 视频源 / 相机源）与没有专用窗口的算子都走它。

**关键设计与原理**：
- **建行流程**：读 `spec.param_specs` → 每项造一个控件（`_make_widget`）→ 前面配一个标签 → 组成一行（`_build_param_rows`）；
- **控件类型**：`int / float`（带软范围）、`combo`、`bool`、`file`（带"浏览…"）、**`file` + `plain: True`**（只选文件、**不导进图库**，级联文件用）、
  `dir`（选目录）、**`slider_int`**（进度条 + 微调框，真范围 + 软范围双向联动；值相同不发信号 ⇒ 不会死循环）；
- **动态默认值**：`default_from` 声明的参数（如 ROI 相关）在 `_load_params()` **之后**填，保证"跟着当前图走"；
- **行联动 `visible_when`**：只有被依赖参数取到允许值时才显示那一行（颜色提取选 HSV ⇒ 只显示 HSV 那 6 行）；**必须 `setVisible`**（清空文字仍占位）；
- **起点类节点**特殊处理：去掉"基本参数"页（没有上游）、去掉"执行 / 连续执行"按钮（只留"确定"，用户 2026.10.5 要求）、去掉"显示结果"页（处理类没有结构化结果）；
- **偶数自动改奇数**（`_to_odd`）：卷积核 / 自适应阈值块要求奇数。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_param_group_layout()` | 取"运行参数"页的垂直布局 | `.ui` 里叫 `verticalLayout_8` |
| `_hide_item()` / `_set_item_visible()` | 藏 / 显示一个布局项（含嵌套布局） | 先把 `.ui` 里**直线专用的行**藏起来（`_hide_line_rows`） |
| `_hint_to_bottom()` | 参数校验提示行挪到参数行**下面** | 用户 2026.10.7 要求（提示不许挤上面把布局弄乱） |
| `_build_param_rows()` | 按声明表生成行 | 见上"建行流程" |
| `_bind_linked_rows()` / `_apply_param_visibility()` | 行联动 | 给被依赖控件接信号 + 先按当前值算一次显隐 |
| `_apply_dynamic_defaults()` / `_apply_source_default()` | 动态默认值 | **必须在 `_load_params()` 之后**跑 |
| `_make_widget(...)` / `_to_odd(...)` | 造控件 / 偶数转奇数 | 造不出来返回 None（界面不崩） |
| `_browse_file(...)` / `_browse_plain(...)` / `_browse_dir(...)` / `_browse_wants_folder(...)` | 三个浏览按钮 | 文件夹 / 图片 / 只选文件 / 选目录 |
| `_load_params()` / `_update_params()` / `_set_widget_value()` / `_widget_value()` | 参数 ⇄ 控件 | 子类 / 基类共用 |
| `on_ok()` | "确定" | 起点节点：只保存 + 关窗；其它：沿用父类（先单步执行一次再关） |
| `_remove_result_tab()` / `_remove_basic_tab()` / `_remove_run_buttons()` | 起点类节点的界面裁剪 | 见上"起点类节点特殊处理" |

> **本章属于**：⑩ 参数窗口

## CircleParamsDialog.py（ui/CircleParamsDialog.py；274 行；圆专用窗口）

**文件作用**：圆的参数窗口。为什么圆不能直接用基类：**HoughCircles 的参数名与"最小距离"这类控件形态不同**，且结果计数文案是"圆的数量"。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_set_label_text(name, text)` / `_replace_widget(old_name, new_widget)` | 原地改造基类界面 | 只改标签文字；按 `objectName` 精准拔旧控件插新控件 |
| `_load_params()` / `_update_params()` | 重写：圆自己的参数 | 先 `super()` 管公共部分（ROI / 图像源 / 继承 / 外扩），再补圆的 |
| `update_result_count(data)` | 显示"圆的数量" | 重写父类文案 |

> **本章属于**：⑩ 参数窗口

## GrayParamsDialog.py（ui/GrayParamsDialog.py；120 行；灰度专用窗口）

**文件作用**：灰度的参数窗口（与直线 / 圆共用同一份 `ui/LineParamsDialog.ui`）。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_on_gray_full_toggled(checked)` | 勾"作用于整图" ⇒ 把 ROI 控件置灰 | 整图时 ROI 不起作用，置灰避免误会 |
| `_load_params()` / `_update_params()` | 重写：补"作用于整图" | 公共部分仍交给父类 |

> **本章属于**：⑩ 参数窗口

## ui/LineParamsDialog.ui（782 行；三个窗口共用的界面文件）

**文件作用**：参数窗口的**静态布局**：左侧"基本参数"页（ROI / 图像源绑定 / 运行参数）+ 右侧"显示结果"页 + 底部三个按钮。
**它被 4 个类共用**：`LineParamsDialog`（直接用）、`CircleParamsDialog`（原地换控件）、`GrayParamsDialog`（补一个开关）、`GenericProcessDialog`（把"运行参数"页清空后按声明表生成）。

**关键设计与原理**：控件名字是**代码的抓手**（`_find` / `findChild` 按 `objectName` 找）——改 `.ui` 里任何一个 `objectName` 都要同步改代码；
"运行参数"页里的行由代码动态生成 ⇒ **`.ui` 里只保留分组框与那个垂直布局**。

> **本章属于**：⑩ 参数窗口

---

## FlowChart.py（widgets/FlowChart.py；569 行；画布：节点 / 连线 / 视图）

**文件作用**：流程图画布的三件套 —— `NodeItem`（方框）、`EdgeItem`（贝塞尔连线）、`FlowchartView`（QGraphicsView 子类，管拖放与拉线）；
文件末尾的 `FlowChartWindow` 是**单独运行本文件时的自测窗口**（主窗口不用它，别拿它当入口）。

**关键设计与原理**：
- **拖放建节点**：`dragMoveEvent` 必须重写，否则 `ScrollHandDrag` 会吃掉事件、`dropEvent` 永不触发；
- **拉线是"点到蓝点 + 松开在红点"**：`mousePressEvent` 算距离 → `_start_connection` 画灰色虚线 → `mouseReleaseEvent` / `_try_finish_edge` 变实线并清状态；
- **右键菜单**：方框上只有"删除节点"；连线上是"删除连线"；菜单抽成 `_make_context_menu()` 是为了**能自动化测试**（不必真弹菜单等用户点）；
- **双击** = 打开该节点的参数窗口（事件转给主窗口的 `on_node_double_clicked`）；
- **节点拖动**实时刷新连线（`update_all_edges`）。

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `NodeItem.__init__(name, pos, ...)` | 一个方框 | 名字决定用哪个算子；持有输入 / 输出蓝红点 |
| `NodeItem.mouseMoveEvent` / `mouseReleaseEvent` | 拖动 | 松手时通知主窗口标记"有改动"（撤销在这里提交 "move_pending"） |
| `NodeItem.mouseDoubleClickEvent` | 双击 | 转成"打开参数窗口" |
| `NodeItem._make_context_menu()` / `contextMenuEvent` | 右键菜单 | 返回 `(menu, 菜单项字典)` 便于测试 |
| `NodeItem.paint` | 画方框 | 输入 / 输出节点颜色区分；选中态描边 |
| `NodeItem.get_input_pos()` / `get_output_pos()` | 蓝 / 红点的**场景坐标** | 连线两端就用它们（`mapToScene`） |
| `EdgeItem.update_path()` / `update_positions()` | 生成 / 更新贝塞尔路径 | 节点一动就调 |
| `EdgeItem.contextMenuEvent` | 右键删连线 | — |
| `FlowchartView.dragEnterEvent` / `dragMoveEvent` / `dropEvent` | 从左侧树拖到画布 | 见上"拖放建节点" |
| `FlowchartView.mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` | 拉线 | 见上"拉线" |
| `FlowchartView._start_connection()` / `_try_finish_edge()` / `_cancel_connection()` | 拉线状态机 | 虚线 → 实线 / 取消 |
| `FlowchartView.on_selection_changed()` | 场景选中变化 | 通知主窗口 `on_node_selected` |
| `def main()` | 单独运行本文件的自测 | 不进主程序 |

> **本章属于**：⑪ 界面控件

## FlowPages.py（widgets/FlowPages.py；627 行；`FlowPageManager` —— 多页面）

**文件作用**：把 `main.ui` 里的 `flowWidget`（`QTabWidget`）改造成**浏览器式标签页**：每页一套"画布 + 方框 + 连线"，外加 `+` 新建、
双击就地改名、右键菜单（添加 / 重命名 / 删除页面）、拖动换序、`×` 关闭、**每页独立的"有改动"标记**。

**关键设计与原理**：
- **每页一份独立状态**：`view`（`FlowchartView`）、节点表、连线表、`dirty`、`project_path`（这一页的保存目标）、**撤销栈**（在 `undo_service` 里按 page key 存）；
- **`+` 不是页面**：它没有页面记录（`tabData` 里没有标识）⇒ `_page_at()` 找不到它，改名 / 删除都会自动跳过；**永远待在最后**（被拖走也会被 `_ensure_add_tab_last` 移回）；
- **`page_key()` = "每页 × 每图"缓存 / 参数 / 撤销栈的键**；
- **关闭一页先问"要不要保存"**（回调主窗口 `_confirm_close_flow_page`）；点 `×` 不弹确认（像浏览器那样干脆），右键"删除页面"才确认；
- **换页回调** `_notify_switched(page)`：调用方在这里切节点表、切参数、**切撤销栈**、刷新画面；
- **第一页复用 `.ui` 里已有的 `QGraphicsView`**（`replaceWidget` 原地替换 ⇒ 拉伸比例与边距都继承）。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `__init__(tab_widget, view_factory, ...)` | 接管控件 | 外部给"造画布"的工厂函数（解耦） |
| `setup()` | 接管 `flowWidget` | 登记第一页 + 装新建 / 右键 / 双击改名 / `×` 关闭 / 拖动换序；返回第一页记录 |
| `_create_add_tab()` / `_add_tab_index()` / `_ensure_add_tab_last()` | `+` 装饰标签 | 见上"`+` 不是页面" |
| `page_key()` | 当前页标识 | 缓存 / 参数 / 撤销栈都用它 |
| `add_page(title=None)` | 新建一页并切过去 | 新页插在 `+` 前面 |
| `append_pages(titles)` | **追加 N 页（"打开方案"专用）** | 不切换当前页、不触发换页回调；已有页面原样保留 |
| `delete_page()` / `close_page()` / `_on_tab_close_requested()` / `_remove_page()` | 删除 / 关闭一页 | 先切走 → 清画面 → 移标签与记录 → 销毁控件 |
| `_on_tab_moved(...)` | 拖动换序 | 页面顺序跟着换；牵涉 `+` 时用单次定时器移回（避免信号里再改序造成递归） |
| `rename_page()` / `_on_title_editor_finished()` / `_close_title_editor()` | 就地改名 | 标签原位置出现小输入框；回车 / 失焦保存、Esc 取消 |
| `mark_dirty()` / `clear_dirty()` / `mark_all_clean()` / `has_dirty_pages()` | 脏标记 | "保存方案"成功后 `mark_all_clean()` |
| `_register_page(...)` / `_page_at(index)` | 登记 / 查页记录 | `_page_at` 查的是"标签里存的页面标识"⇒ 换过顺序也不会认错页 |
| `_create_view(...)` / `_make_view(...)` | 造 / 接管画布 | 第一页 `replaceWidget` 原地替换，新页直接建 |
| `_on_tab_context_menu(...)` / `eventFilter(...)` | 右键菜单 / 双击改名 | 事件过滤器还负责"改名框里按 Esc 取消" |
| `_on_tab_widget_destroyed()` | 控件被销毁 | 清引用，后续事件一律忽略 |
| `_unique_title()` | 新页起名 | 避免与已有标签重名（用户可能手改成一样的） |
| `_on_tab_changed(...)` / `_resync_current_page()` / `_notify_switched(page)` | 换页 | 兜底同步（标签当前页与 `current_page` 对不上时纠正）+ 通知调用方 |

> **本章属于**：⑪ 界面控件

## ImageGraphicsView.py（widgets/ImageGraphicsView.py；196 行；图像显示视图）

**文件作用**：显示图像并支持**滚轮缩放（以鼠标位置为中心）+ 左键拖拽平移**的视图；隐藏滚动条，硬件加速。

**关键设计与原理**：
- **OpenCV BGR → Qt RGB** 后渲染；
- **缩放 / 平移按"画面键"记账**：`set_image(cv_img, image_key)` —— 换了键就存起旧键的缩放并给新键复位默认比例并居中；
  ★ 因此**键必须与"数据身份"分开**：静态图 = 文件路径；视频 = `"video:路径"` **整段共用一个键**
  （否则每帧都是新键 ⇒ 每帧复位：画面一大一小、滚轮缩放被吃掉）；
- `reset_zoom()` = 1:1 居中并**忘掉当前键**（关闭图片 / 视频、打开摄像头时清视图）。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `__init__()` | 初始化场景与交互参数 | 自持一个 `QGraphicsScene`（**注意不要叫 `self.scene`**：会遮蔽 `QGraphicsView.scene()` 方法） |
| `set_image(cv_img, image_key=None)` | 显示一帧 | 换键 ⇒ 存旧键缩放 + 新键复位居中 |
| `reset_zoom()` | 复位缩放平移 | 见上 |
| `wheelEvent(event)` | 滚轮缩放 | 以鼠标位置为中心；缩放上下限夹住 |

> **本章属于**：⑪ 界面控件

## ImageGalleryWidget.py（widgets/ImageGalleryWidget.py；537 行；图库控件）

**文件作用**：图像列表（缩略图 + 工具栏 + "图像源 (n/N)"标签）的**控件侧**；它只负责"显示与交互"，**业务（切画面 / 清参数 / 删数据）都回调主窗口**。

**关键设计与原理**：
- **缩略图固定尺寸**（`make_thumbnail_pixmap()`：固定 80×60 画布 + 等比缩放 + 灰底居中）；单元格 `88×84` 并由 `setGridSize` 钉住 ——
  只设 `setUniformItemSizes(True)` 不够：混入一张竖版图会让**所有**单元格塌成 ~21px（实测 86→21）；
- **"图像源 (n/N)"标签的归属**：默认由图库刷新；**播放（视频 / 相机）期间交给播放侧**（`set_count_locked(True)` ⇒ `refresh_count()` 直接返回），
  否则视频每帧刷标签会把"当前点击的排序"顶掉（用户实测的一瞬间消失）；
- **拖放事件全部拦截丢弃**（别把图片拖进列表）；
- **工具栏收编**：从 `.ui` 找控件（`_find`），找不到才自己建（★ 兜底建过的控件要回头补回 `.ui`，否则"控件丢了"会被兜底掩盖）。

| 函数 / 类 | 作用 | 实现原理与要点 |
|---|---|---|
| `make_thumbnail_pixmap(cv_img, w, h)` | 任意长宽比 ⇒ 固定画布缩略图 | 等比缩放 + 居中 + 灰底（保证所有格子一样大） |
| `ImageGalleryWidget.__init__(...)` | 接管图库控件 | 把 `QListWidget` 改成 `IconMode`、固定格子、接信号 |
| `_find(name)` | 按 objectName 找宿主控件 | 找不到返回 None（走"自己建"的兜底） |
| `_build_toolbar()` | 建 / 收编工具栏 | 自动切换勾选框 / 运行模式下拉框 / 停止 / ＋图片 / ＋文件夹 / 删除 / 折叠 |
| `scope_all()` / `set_scope_all(flag)` / `scope_current()` / `run_mode()` | 运行范围 | 下拉框永远有且只有一项（"运行全部" / "运行选中"）；**它自己不执行** |
| `auto_switch()` | 「自动切换」是否打开 | 打开 = 连续执行的范围变成整个图像列表 |
| `_on_collapse_toggled(checked)` / `is_collapsed()` | 折叠 ∨ | 收起时只留工具栏那一条 |
| `_on_delete_clicked()` | 点「删除」 | **只把选中项交给主窗口**（主窗口负责清参数 / 结果 / 缩放；活源在画布时主窗口走"清画布"那支） |
| `count()` / `current_index()` / `set_current_index(i)` | 数量 / 当前项 / 选中 | `set_current_index` **不触发 `itemClicked`**（避免重复执行） |
| `select_frame(frame)` | 按"原图对象"选中条目 | 导入后把第一张点亮，让"图像源 (n/N)"显示正确 |
| `items()` / `item_frame(item)` / `item_path(item)` | 遍历 / 取原图 / 取路径 | 原图存在 `Qt.UserRole`；摄像头帧 / 测试图没有路径（空串） |
| `set_count_locked(locked)` / `refresh_count()` | 标签归属与刷新 | 上锁期间不刷新；解锁时立刻刷一次 |
| `remove_item(item)` | 移除条目 | 不动主窗口的参数 / 缓存（那些由主窗口清） |
| `eventFilter(obj, event)` | 拦截拖放 | 返回 True 表示已处理、不再下传 |
| `add_image(cv_img, path=None)` | 加一张图 | 造缩略图 + `QListWidgetItem`；`path` 决定能不能"点图库改图片源路径" |
| `has_path(path)` | 去重 | 批量导入 / 补图库时用 |
| `_on_item_clicked(item)` | 内部槽 | 发信号给主窗口（`_on_gallery_image_selected` / `_on_gallery_path_selected`） |

> **本章属于**：⑪ 界面控件

---

## tests/ 门禁（`dsh_run_all_checks.py` + 44 套 `dsh_*_check.py`）

**文件作用**：**改动后的唯一把关口**。每次改完代码跑一遍，全绿才算完；发现红先看是哪一套、再定位。

**`dsh_run_all_checks.py`（98 行；一键跑）**：
- 扫出目录下所有 `dsh_*_check.py`，**每个用例起一个子进程**（`subprocess.run`）跑 ⇒ **不存在进程内状态泄漏**（"上一个用例把状态带坏"这类猜测可直接排除）；
- 统一注入环境：`QT_QPA_PLATFORM=offscreen`（无头）/ `PYTHONIOENCODING=utf-8` / **`QT_QPA_FONTDIR=C:\Windows\Fonts`**（否则 QLabel 量不出正确宽度）；
- 汇总每套的 `PASS/FAIL` 与退出码；最后**校验门禁口径与《批次5 技术方案》一致**（当前：**44 套 1018 项**）——
  方案里写的项数与实测不符 ⇒ 直接判"不合格"，避免"文档说的和实际跑的不是一回事"。

**44 套用例（一句话各自管什么）**：

| 用例 | 管什么 |
|---|---|
| `dsh_t5g5_m1_check.py`（287 行） | **批次5目标5-M1**：缩略图固定尺寸（12 张宽度恒定 / 尺寸唯一 / `itemAt` 命中 / `gridSize`）+ **播放中点图库只改选中不动画面参数** + 导入方案不污染图库 |
| `dsh_t5g5_m2_check.py`（330 行） | **批次5目标5-M2（含并入的 M3）23 项**：日志按像素滚动 · 删除语义（播放中 / 相机 / 活源帧 / 静态图）· 活源判据与"连续执行不展开成批量" · **活源轮缓存键 = 视频帧键** · 标签写"视频帧 (n/总数)" · 切走再切回显示原图 · 单步到末尾回卷 / 停在最后一帧 · 活源轮不补图库 |
| `dsh_t5g4_cache_check.py`（211 行） | 批次5目标4-1：结果缓存的**上限 + 真 LRU**（静态图池 / 视频逐帧池分别控） |
| `dsh_t5g4_undo_check.py`（450 行） | 批次5目标4-2：**撤销 / 重做**（每页一条栈 / 换页保留 / 删除后重做 / 灰化 / 快捷键接线） |
| `dsh_t5g3_batch_check.py`（417 行） | 批次5目标3：**"运行全部"分片执行**（不卡 / 能取消 / 行为等价） |
| `dsh_t5g3_host_check.py`（158 行） | 批次5目标3 收尾：**宿主契约 `MainHost`** 自洽（名字都存在 / 清单=依赖 / 运行时无成员） |
| `dsh_t5g2_api_check.py`（178 行） | 批次5目标2：拆 `MainWindow` 之后**接口契约零变化**（白名单里的新方法要显式登记） |
| `dsh_m3_video_check.py` · `dsh_m3_video2_check.py` · `dsh_m3_video3_check.py` | 批次4 目标5-M3 视频源三版：注册 / 单步取帧与前进一帧 / `auto_next` / `loop` / 容错 / **不进图库** · 自动播放与"停止" · **视频帧画面键整段共用** |
| `dsh_m3_delete_check.py` · `dsh_m3_delete_play_check.py` | 删除清画布 · 播放中点删除先停播且**不弹窗** |
| `dsh_m3_switch_check.py` · `dsh_m3_index_check.py` | 播放中换选中节点后续帧按新节点跑 · 收口产物自洽（截图索引 / 日志索引 / 验收点清单） |
| `dsh_m4_camera_check.py`（329 行） | 批次4 目标3-M4 相机源（**不需要真摄像头**：注入假设备）；同族回归 `dsh_m4_cont_check.py`（M4 修复） |
| `dsh_m5_output_check.py` · `dsh_m5_flow_check.py` · `dsh_m5_overlay_check.py` · `dsh_m5_video_check.py` | 批次4 目标3-M5「输出图像」四套：注册与参数窗口与保存行为 · 接进流程 + 参数归档 + 方案往返 · 保存内容（数据层 / 带叠加）· 视频与摄像头录成视频文件 |
| `dsh_m2_check.py` · `dsh_m2_ctrl_check.py` · `dsh_m2_color_check.py` · `dsh_m2_face_check.py` · `dsh_m2_face_share_check.py` · `dsh_m2_v5_check.py` | 批次4 目标二：处理类算子 + **通用参数窗口**（按声明表生成 / 行联动 / 滑块）· 颜色提取 · 人脸 + **通用错误通道**（红字）· **节点级参数**（级联文件跨图共用）· M2 最终验收（范围改下拉框 + 停止独立按钮） |
| `dsh_p4_rules_check.py` · `dsh_p4_ui_check.py` · `dsh_p4_input_check.py` · `dsh_p4_layout_check.py` · `dsh_p4_edge_check.py` | 批次4 目标4「参数校验」四轮 + 边缘阈值规则：规则表 · 窗口内联提示与三入口接线 · **数值软范围** · 提示行与布局护栏 |
| `dsh_m5_flow_check` 之外的旧套 | `dsh_source_check.py`（图片源第一版）· `dsh_t5m1_check.py`（目标5-M1：连续执行范围 = 上游链 + 删 `run_selected_image`）· `dsh_round4_check.py`（当年 4 项改动）· `dsh_five_issues_check.py`（用户报的 5 个问题）· `dsh_import_v2_check.py`（图片与文件夹彻底分开）· `dsh_run_entry_check.py`（图库为空 + 流程里有图片源时能跑）· `dsh_page_path_check.py`（按页面记方案路径）· `dsh_roi_default_check.py`（ROI 默认宽高按"节点实际输入图"算）· `dsh_morph_gray_check.py`（形态学扩 3 档 + 灰度搬家） |
| 文档 / 布局 / 中文路径 三套护栏 | `dsh_doc_consistency_check.py`（**三份文档提到的 `.py` / 符号必须真实存在**；口径要跟方案一致）· `dsh_dlg_width_check.py`（所有参数窗口在任何宽度下不裁控件）· `dsh_imgio_check.py`（中文路径图片读写） |
| `dsh_width_check.py`（48 行） | 量各算子参数窗口的宽度（排查"某个窗口偏宽"的来源，属于诊断工具） |

**关键设计与原理**：
- **每个用例必须走"用户会点的那条路"**（按钮的槽函数 / 窗口的确定），**不许直接调内部方法代替**；
- **用假设备 / 打桩**：相机（`dsh_m4_camera_check`）、`QMessageBox`（`FakeMB`）、`QFileDialog` 都打桩 ⇒ 无头环境也能跑；
- **回归钉**：每条修过的 bug 都要留一条断言（用例名里带"修前：……"）；
- ★ 跑门禁**不要和其它任务并发**（几路同时读 `plan/` 会互相干扰）；
- 用例文件都在 `tests/` 下、`tests/__init__.py` 存在（包结构）⇒ 从工程根 `python tests/dsh_xxx_check.py` 跑。

> **本章属于**：⑫ 门禁

---

## 维护约定（改代码前先看这一节）

**1）加一个算子**：① 在 `ops/<树干>/` 建文件（三件套 + `validate_*`）；② `core/NodeRegistry.py` 注册区加一行；③ `main.ui` 树上加一项。**不用改引擎 / 不用改通用参数窗口**。

**2）加一个 Mixin 方法要跨文件用**：① 方法写在自己的文件里；② 在 **`core/host_contract.py::MainHost`** 里补一行声明；
③ 跑 `dsh_t5g3_host_check.py`（清单=依赖，多·少·重复都会红）。

**3）改了"谁在播 / 画布上是谁"的语义**：一次要同时看四处 —— **标签归属**（`ImageGalleryWidget.set_count_locked`）·
**缓存键**（`flow_engine.cache_image_key` / `_result_cache_key`）· **删除语义**（`gallery_service.delete_gallery_item` 的 `_canvas_shows_live`）·
**批量展开**（`main._uses_live_source`）。漏一处就换一种怪现象（2026.10.16 的教训）。

**4）文档分工**：
- **`plan/…用户手册_v1.1…md`** —— 给**用户**看：怎么用，界面每个按钮干什么；
- **`plan/…项目技术文档_v1.3…md`** —— 给**接入 / 评估**看：能力清单、依赖、边界；
- **`plan/…代码说明书_v1.1…md`（本文件）** —— 给**改代码的人**看：每个文件的每个函数"作用 + 实现原理"；
- **`plan/…批次N技术方案…md`** —— **口径真源**（当前 = 《批次5 技术方案》v2.29；门禁项数以它为准）；
- **`plan/pyside6_开发日志.md`** —— 按时间记"改了什么 / 为什么 / 怎么验证的 / 遗留"。

**5）改完必做**：`python -m py_compile <改过的文件>` → 跑相关那一套用例 → 跑 `tests/dsh_run_all_checks.py` 全绿 → 方案升版 + 写日志 → 改前备份 / 改后快照（`E:\opencv_python_3_8\backups\`）。**git 由用户自己提交，不要碰。**

---

## 本说明书的维护记录

| 日期 | 改了什么 |
|---|---|
| 2026.10.7 | **v1.0 初版**（当时目录还是平铺：`main.py` 3327 行 + 21 个根文件） |
| **2026.10.16** | **按新目录整体重写**（批次5 目标1「目录重构」+ 目标2「拆 `MainWindow`」之后）：<br>· 章节从"按旧文件名一节"改成 **按新目录分组**（根 / `core/` / `services/` / `ops/` / `ui/` / `widgets/` / `tests/` / `.ui`）；<br>· **新增章节**：`core/param_store.py` · `core/project_store.py` · `core/flow_engine.py` · `core/host_contract.py` · `core/result_cache.py` · `core/commands.py` · `services/camera_service.py` · `services/video_service.py` · `services/gallery_service.py` · `services/undo_service.py` · `ops/` 五个分组 · `tests/` 门禁；<br>· **重写章节**：`main.py`（3327 → **964 行**，改成"入口 / 界面装配 / 建图与改动 / 双击路由 / 脏标记 / 5 个弹窗薄壳"六节）· `NodeRegistry.py`（补 `is_bound_node` 与"只导出声明"的约定）· `Detector.py`（改成兼容门面）· `FlowChart.py` / `FlowPages.py` / `ImageGalleryWidget.py`（补批次5 的新能力）；<br>· **版本号由 v1.0 升为 v1.1**（用户 2026.10.16 要求升一级）；行数全部按 2026.10.16 实测校正。 |
| **2026.10.16（同日）** | **升版到 v1.1**（用户要求："把用户手册，项目技术文档，代码说明书版号升一个级"；**内容未变，只升版号与文件名**）。 |
