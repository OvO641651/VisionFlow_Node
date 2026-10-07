# VisionFlowNode 代码说明书

> **这份文档写什么**：工程里**每个文件干什么**、**每个函数/方法干什么、怎么实现的**（实现原理与关键判断）。
> **怎么用**：想改某个功能时，先在下面的"文件总览"里找到对应文件 → 再翻到该文件的章节看函数清单；
> 每个函数一行，形如 `函数名` | 作用 | 实现原理与要点。
>
> **口径与免责**：
> 1. 函数说明**以代码里的中文 docstring 与真实实现为依据**（本项目 docstring 写得很密，是权威来源）；
> 2. 表里出现「（未注释，按调用点推断：……）」的地方，是**我读代码后推断的**，不是作者原话；
> 3. 行号（`L123` 这种）是 **2026.10.7 这一版**的行号，改动代码后行号会漂；
> 4. 本文件由 4 段独立编写的内容拼成（核心 6 个文件由主 agent 写，外围 12 个文件由 3 个子任务分别写），
>    因此个别文件的表格列名/详略略有差异——内容都以源码为准。

---

## 文件总览

| 文件 | 行数 | 一句话职责 | 分层 |
|---|---|---|---|
| `main.py` | 3221 | 主窗口 + 数据流引擎 + 周边设施（方案、归档、图库、相机/视频接线） | ① 核心 |
| `NodeRegistry.py` | 259 | 节点契约（`NodeSpec`）+ 注册表（四类 kind、`get_spec`、`result_bbox`） | ② 契约 |
| `ProcessOps.py` | 319 | 处理类算子算法 + `PROCESS_SPECS`（灰度/取反/滤波/二值化/形态学/边缘提取） | ③ 算子 |
| `SourceOps.py` | 317 | 图像源类算子 + `SOURCE_SPECS`（图片源/视频源/相机源） | ③ 算子 |
| `OutputOps.py` | 512 | 输出类算子 + `OUTPUT_SPECS`（输出图像：图片序列 / 视频文件 / 保存内容） | ③ 算子 |
| `GenericProcessDialog.py` | 433 | 通用参数窗口：按 `param_specs` 自动生成"运行参数"页 | ④ 参数窗口 |
| `LineParamsDialog.py` | 902 | 参数窗口**基类**（三页签、ROI 绘制/继承、执行按钮；加载 `LineParamsDialog.ui`） | ④ 参数窗口 |
| `CircleParamsDialog.py` | 253 | 圆专用参数窗口（重写部分控件与 `_load_params/_update_params`） | ④ 参数窗口 |
| `GrayParamsDialog.py` | 119 | 灰度专用参数窗口（"作用于整图"联动置灰 ROI 区） | ④ 参数窗口 |
| `FlowChart.py` | 569 | 流程图画布：`NodeItem` / `EdgeItem` / `FlowchartView`（拖放、连线、右键删除） | ⑤ 画布 |
| `FlowPages.py` | 626 | 多页签页面管理 `FlowPageManager`（增删改、就地改名、关闭前回调） | ⑤ 画布 |
| `ImageGraphicsView.py` | 195 | 显示图像/视频的 `QGraphicsView` 子类（滚轮缩放、按图片分别记缩放平移） | ⑥ 显示 |
| `ImageGalleryWidget.py` | 477 | 图像列表 + 上方工具栏的包装类（对外只暴露自己的接口） | ⑥ 显示 |
| `Detector.py` | 137 | 直线 / 圆检测算法封装 + 造测试图 | ⑦ 算法 |
| `main.ui` | — | 主界面布局（树、画布、显示区、工具栏、图库、执行日志） | ⑧ 界面 |
| `SetCameraID.ui` | — | "设置相机编号"小窗口 | ⑧ 界面 |
| `LineParamsDialog.ui` | — | 参数窗口的布局（基本参数 / 运行参数 / 显示结果三页） | ⑧ 界面 |
| `pyside6.txt` | 5512 行 | 开发日志（每个改动一条；`plan\pyside6_开发日志.md` 是它的 Markdown 版） | 记录 |

## 分层与调用关系（谁调谁）

```
                    ┌──────────────────────── main.py（MainWindow）────────────────────────┐
                    │  界面接线 / 数据流引擎 / 方案持久化 / 参数归档 / 图库 / 相机与视频接线  │
                    └───┬───────────────┬────────────────┬───────────────┬───────────────┘
                        │               │                │               │
              ┌─────────▼──────┐  ┌─────▼──────┐  ┌──────▼───────┐  ┌────▼─────────────┐
              │ FlowPages.py   │  │ FlowChart  │  │ImageGraphics │  │ImageGalleryWidget│
              │ 多页签管理      │  │ 画布/节点/线│  │View 显示      │  │ 图像列表+工具栏   │
              └────────────────┘  └────────────┘  └──────────────┘  └──────────────────┘
                        │
              ┌─────────▼──────────────────────────────────────────────────────────────┐
              │ NodeRegistry.py（节点契约：NodeSpec / NODE_SPECS / get_spec / result_bbox）│
              └───┬──────────────────┬──────────────────┬──────────────────┬───────────┘
                  │                  │                  │                  │
        ┌─────────▼───────┐ ┌────────▼────────┐ ┌───────▼────────┐ ┌───────▼────────┐
        │ ProcessOps.py   │ │ SourceOps.py    │ │ OutputOps.py   │ │ 检测类（注册在   │
        │ 处理类 6 个      │ │ 图像源类 3 个    │ │ 输出类 1 个     │ │ NodeRegistry 里）│
        └─────────────────┘ └─────────────────┘ └────────────────┘ └───────┬────────┘
                                                                          │
                                                                  ┌───────▼────────┐
                                                                  │ Detector.py    │
                                                                  │ 直线 / 圆算法   │
                                                                  └────────────────┘

                参数窗口一侧：GenericProcessDialog ← LineParamsDialog ← （Circle / Gray 专用窗口）
                都用：LineParamsDialog.ui 那份布局
```

**三条最该记住的约定**（在 `main.py` / `NodeRegistry.py` 章节里有详细说明）：

1. **加一个算子 = 一个算法方法 + 一张参数表 + 树里一项**：算法与参数表放分类模块（`ProcessOps` / `SourceOps` / `OutputOps`），注册表只在末尾汇总；分类模块**不 import 注册表**（避免循环导入）。
2. **数据层与渲染层分离**：`run()` 改数据，`draw()` 只画显示；叠加永不回流。
3. **参数按图片归档，但"流程级节点"（起点节点 + 输出节点）除外**：判据是 `NodeSpec.is_flow_level`。

---


---

> **本章属于**：① 入口 + 数据流引擎（核心）

## main.py（3221 行；主窗口 + 数据流引擎）


**文件作用**：整个软件的主入口与大脑。它装下三件事：① 主窗口 `MainWindow`（把 `main.ui` 加载进来、用 `findChild` 收编控件、接线所有按钮/菜单/信号）；② **数据流引擎**（拓扑排序、图像源绑定、ROI 继承、按节点契约执行、渲染层合成）；③ **周边设施**（方案持久化、参数按图片归档、图库导入、相机与视频的播放/录制接线、执行日志）。几乎所有"跨模块"的逻辑都在这里收口，其余文件只提供"声明"或"单一职责的小部件"。

**关键设计与原理（读这个文件前必须知道的 8 条）**：

1. **数据层与渲染层彻底分离**：`_run_flow_pipeline*` 只算数据（图像 + 结果数据），叠加（绿线/红圆/ROI 框）一律在 `_render_display()` 里画到显示图上，**永不回流**。
2. **影响只能靠声明的通道**：节点之间传图像靠"图像源绑定"（`_resolve_input`），传 ROI 靠"ROI 继承"（`_resolve_roi` + `roi_of` 字典），没有第二条暗路。
3. **连续执行 = 执行到当前选中节点为止**（`stop_at` 显式参数，由 `_run_flow_pipeline` 从 `self.selected_node` 传下去）；**单步执行 = 只跑选中的那一个节点**（`_run_flow_pipeline_step`，输入沿绑定追到起点）。两者共用 `_run_nodes` 里的"取输入 / ROI / 日志"那一段，但"跑哪些节点"截然不同。
4. **参数按图片归档**：每个节点的参数在内存里按"图片标识"存多份（`params_per_image`），切图时 `_switch_image_params` 存档+载入。**例外**：起点节点（图片源/视频源/相机源）与输出类节点（输出图像）属于"流程级配置"，靠 `_is_flow_level_node()` 跳过归档。
5. **结果缓存键 =（图片标识, 页面 key, 执行方式）**（`_result_cache_key`）：单步与连续分开存、按页分开、只在内存。而**画面（缩放/平移）键**是另一套（`_display_key_of` / `_camera_display_key`），视频整段共用 `video:路径`、相机共用 `camera:编号`。
6. **"起点节点"是流程真正的取图处**：`_source_node_frame()` 按 `self.flow_nodes` 顺序问每个起点类节点要图；`_flow_source_frame()` 决定这一轮的"全局图像源"帧（主窗口当前图 > 起点节点兜底 > 报错文案）。
7. **设备类只在主窗口开一次**：相机由 `_open_camera_device()/ _release_camera_device()` 统一开关（相机源节点通过注入的取帧器 `_latest_camera_frame()` 复用）；视频由 `SourceOps._open_video()` 各自缓存 `VideoCapture`（各读各的，不抢读指针）。
8. **输出类节点的三个 provider**：`_bind_output_providers()` 把"输入图片名 / 带检测叠加图 / 这一轮上下文"三个取用器绑到**当前正在跑的主窗口**上（一个进程可能有多个 MainWindow，例如测试里）。

### 模块级

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_fingerprint_value(value)` | 算"页面内容指纹"时把参数值规范化 | 把 bool/int/float/str 统一成可比较的元组（数字 round 到 4 位），避免 `1` 与 `1.0`、浮点误差造成"明明一样却判成不同" |
| `main()` | 程序入口 | 建 `QApplication`、实例化 `MainWindow`、`show()`、`app.exec_()` |

### 一、启动与界面接线

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `MainWindow.__init__` | 装主窗口、建状态、接线所有控件 | `QUiLoader().load('main.ui')`（**cwd 必须是工程根**）；`findChild` 收编按钮/图库/树；把 `graphicsView_video` **原地替换**成 `ImageGraphicsView`；建 `DetectorShape`、`FlowPageManager`、`ImageGalleryWidget`；初始化几十个状态字段（`cap/timer/current_static_image/_frame_paths/result_cache/_video_*` 等）；末尾注入三个 provider（相机取帧器、输出节点的文件名/叠加图/上下文） |
| `_clear_current_dialog()` | 对话框关闭时清引用 | 把 `self.current_dialog` 置 None，避免持有已销毁的窗口 |
| `on_node_selected(node)` | 单击方框时记录"当前选中节点" | 先看 `flow_page_mgr.switching`（正在增删页面时忽略信号）与"这个节点是否属于当前页场景"，再更新 `selected_node` 与底部提示 label |
| `_bind_current_flow_page()` | 把"当前页"的视图/节点/连线/label 绑到主窗口 | 从 `flow_page_mgr.current_page` 取 `view.flow_scene`、`nodes`、`edges`、提示 label，赋给 `self.flow_nodes/flow_edges/...`，让引擎只认当前页 |
| `_on_flow_page_switched(new_page, old_page)` | 换页回调 | ① 存旧页选中节点与参数；② 绑新页；③ 恢复新页选中节点与参数；④ **收尾正在录制的视频**（`_close_recordings("切换页面")`） |
| `close_event(event)` | 关窗口 | **先 `_close_recordings("关闭程序")`**（否则视频文件没 release、打不开），再 `close_camera()` 释放设备 |
| `_show_menubar_menu()` | 点顶部"菜单"按钮弹出菜单栏 | 取 menubar 第一个 action 的 menu，在按钮左下角 `exec_()` |
| `set_camera_id()` | 设置相机编号 | 加载 `SetCameraID.ui` 小窗口，确定后写 `self.camera_id` |
| `_on_tree_double_click(_item, _column)` | 双击左侧树项 | 交给 `_create_node_from_name()` |
| `_create_node_from_name(name)` | 双击树项在画布上建节点 | 算一个错开的位置 → `add_flow_node()` |
| `on_node_double_clicked(node)` | 双击方框 → 开这个算子的参数窗口 | **路由"专用优先、通用兜底"**：直线/圆/灰度→专用窗口；其余有 `param_specs` 的→`GenericProcessDialog`；未实现的（人脸/颜色）保持无反应 |
| `_open_node_dialog(node, dialog_class)` | 开参数窗口的统一流程 | 记下开窗前的参数 → 建窗口（`node=/main_window=`）→ 关窗后 `_mark_dirty_if_params_changed()` 决定要不要标"有改动" |
| `_mark_dirty_if_params_changed(node, before)` | 参数真的变了才标脏 | 比较 `before` 与当前 `node.params`，不同则 `flow_page_mgr.mark_dirty()` |
| `_confirm_close_flow_page(page)` | 关页前的"要保存吗" | 未标脏直接放行；否则弹中文按钮的 `QMessageBox`（保存/不保存/取消），"保存"时先把这一页切成当前页再 `save_project()` |
| `_page_title(page)` | 取页签标题 | 在 `tab_widget` 里找这一页的 index，取 `tabText`；找不到返回空串 |
| `_update_project_title()` | 把当前页的方案文件名显示到窗口标题 | 取当前页 `project_path` 的 basename 拼进 `setWindowTitle` |

### 二、方案持久化（.vfproj）

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_page_fingerprint(page)` | 给"工作区里的一页"算内容指纹 | 标题 + 每个节点的名字/坐标/图像源绑定/参数（`_fingerprint_value` 规范化）+ 连线；用于加载时**去重** |
| `_model_page_fingerprint(page_model)` | 给"方案文件里的一页模型"算指纹 | 结构必须与 `_page_fingerprint` **完全一致**，否则去重失效（这是刻意的双份实现） |
| `_collect_page(page)` | 把一页收成可 JSON 化的 dict | 节点字段 = id/name/x/y/input_source/params/**params_by_image**；连线 = [起点序号, 终点序号] |
| `_collect_project()` | 把**当前这一页**收成方案 dict | 一个文件只装一页（用户口径）；带 `format/version/saved_at/current_page/last_source/pages` |
| `save_project()` | "保存方案" | 当前页已有 `project_path` 就静默写回；没有就退化成"另存为"；保存只清**当前页**的 dirty |
| `save_project_as()` | "另存为…" | 弹原生保存对话框（默认名 = 当前页标签名）→ 写文件 → 记路径 |
| `_write_project_file(path)` | 真正写文件 | JSON / UTF-8 / 缩进 2；写完更新标题 |
| `open_project()` | 菜单"打开方案" | 弹原生打开对话框 → `load_project()` |
| `load_project(path)` | 加载方案 | **先解析+校验（完全不碰界面）**，全部通过才 `_apply_project()`；返回 False 表示失败（坏文件自动跳过、不弹提示） |
| `_build_project_model(pages)` | 把文件里的页面数据整理成"待应用模型" | 清洗脏数据、收集 warnings、把节点/连线转成可创建的结构；**必须带上 `params_by_image`**（漏了会"存了读不回来"） |
| `_apply_project(model, data, project_path)` | 把模型**追加**到现有页面后面 | 逐页 `add_page()` → 建节点/连线 → 恢复参数与选中项；**内容指纹去重**（相同的页跳过）；新页插在"＋"前 |

### 三、建图与改动

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_add_node_to_page(page, name, pos, mark_dirty)` | 在指定页建一个节点 | 拖拽添加与加载方案共用；未注册的名字也允许建（执行时日志写"模块未实现"） |
| `_add_edge_to_page(page, start_node, end_node, mark_dirty)` | 在指定页连一条线 | 同一对起终点不重复连 |
| `_on_node_moved(page)` | 方框被拖动 | 刷新连线（`update_positions`）+ 标记该页有改动 |
| `add_flow_node(name, pos)` | 对外：往**当前页**加节点 | 转调 `_add_node_to_page` |
| `add_edge(start_node, end_node)` | 对外：连一条线 | 转调 `_add_edge_to_page` |
| `delete_flow_node(node_to_delete)` | 删除节点与其连线 | 先摘掉所有相关连线 → 从场景与列表移除；**若删的是输出节点，先 `close_recording()` 收尾它的录制** |
| `update_all_edges()` | 移动方框后曲线跟着动 | 遍历 `flow_edges` 调 `update_positions()`；对已销毁对象包 `try/except RuntimeError` 跳过（Qt 残引用坑） |
| `delete_edge(edge_to_delete)` | 删除一条连线 | 从场景与 `flow_edges` 移除 |

### 四、参数归档（按图片 / 流程级）

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_path_key(path)` | 路径比较用的键 | 绝对化 + 大小写不敏感；用于"用户删过的图别再自动加回来" |
| `_is_removed_path(path)` | 这张图被用户主动删过吗 | 查 `self._removed_paths` |
| `_image_key_of(frame)` | 这张图在"参数/缓存/缩放"里的标识 | 优先 `_frame_paths[id(frame)]`（文件路径，跨会话稳定）；视频帧 → `路径#帧号`；否则 `id(frame)` |
| `_node_params_by_image(node)` | 取"键是字符串"的那部分参数存档 | 只导出字符串键（路径/视频槽），`id(原图)` 这种跨进程没意义 |
| `_get_node_params_store(node)` | 取节点的"按图参数"字典 | 没有就现场建 `params_per_image = {}` |
| `_is_source_node(node)` | 是不是起点节点 | `spec.kind == KIND_SOURCE` |
| `_is_flow_level_node(node)` | 参数是不是**流程级配置** | `spec.is_flow_level`（= source + **sink**）；归档/载入都要跳过它，否则换图会清空输出目录/文件名 |
| `_save_node_params(nodes, image_key)` | 把一批节点的参数存到某图片名下 | 跳过流程级节点；空字典不存（省内存、避免灌 None） |
| `_load_node_params(nodes, image_key)` | 把一批节点的参数换成某图片那份 | 跳过流程级节点；**先 `params.clear()` 再 update**（这就是"输出目录必须不按图归档"的原因） |
| `_switch_image_params(new_key)` | 切图时存档 + 载入 | 同键直接返回；先存旧图那份，再载入新图那份；`current_image_key is None` 时**不载入**（保留用户"还没开图时就设好的参数"） |
| `_result_cache_key(image_key, mode)` | 结果缓存键 | `(图片标识, 页面 key, 执行方式)`；单步/连续分开、按页分开 |

### 五、执行入口与数据流引擎（核心）

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_build_execution_order(nodes, edges)` | 拓扑排序（Kahn） | 返回 `(order, parents, skipped)`；`skipped` = 没连线的孤立节点 / 成环的节点（日志如实提示"未执行"） |
| `_node_modifies_image(node)` | 这个节点会不会改数据层图像 | 查 `spec.modifies_image`（处理类/图像源类 True；检测类、输出类 False） |
| `_resolve_input(node, parents, out_images)` | 决定节点从哪份图像开始算 | 手动绑定优先（`input_source` 是节点对象 → 用它；是 `SOURCE_KEY` → 全局图像源）；"自动"取最后一个上游，多上游时优先挑"会改图"的那一支 |
| `_resolve_roi(node, img_shape, in_results, in_roi)` | 算这个节点这轮真正用的 ROI | 勾"继承上游"时：`roi_source="roi"` 沿用上游实际用的框、`="result"` 用上游结果的外接框（首选拿不到自动换另一种）；都没有才用本节点手画的 ROI；最后统一外扩 `roi_margin` 并裁进图像范围。返回值含 `inherited` 标记，日志据此写"← 继承上游ROI框" |
| `_execute_node(node, in_img, in_results, in_roi)` | 执行一个节点（契约执行侧） | 解析 ROI → 调 `spec.run(detector, in_img, roi, params)` → 若算子没返回图像则当"不改图"处理；返回 `(out_img, results, roi_info, spec)` |
| `_format_result_text(node, results, roi_info, spec)` | 日志"结果数据"列文案 | 交给 `spec.format_result(results)`；再按需追加"← 继承…"短提示（**只用日志、不弹窗**） |
| `_run_flow_pipeline(frame, stop_at)` | **连续执行**入口 | 复制全局帧 → 拓扑排序 → **按 `stop_at`（= 当前选中节点）截断** → `_run_nodes()` |
| `_parent_nodes(node)` | 直接上游节点列表 | 扫 `flow_edges` 里 `end_node is node` 的边（顺序即连线顺序） |
| `_node_input_frame(node, _depth)` | 这个节点这轮实际会收到的图 | 起点节点直接问它要图；绑到某上游就递归往上；都没绑 → 主窗口当前图 / 起点节点兜底。对话框用它取"上游整张图"的尺寸当 ROI 默认值 |
| `_run_nodes(order, parents, frame, skipped, base_node, stop_at)` | **单步/连续共用**的执行主体 | 按顺序：`_resolve_input` 取输入 → 备好"这一轮上下文"（输入名/叠加图/节点标识/来源种类/源帧率）→ `_execute_node` → 累计 `all_data` 与 `exec_info`；截断掉的节点写一行"连续执行到「X」为止，以下节点未执行"；最后 `_render_display()` 出显示图 |
| `_bind_output_providers()` | 把输出节点的三个取用器绑到**当前窗口** | provider 是 OutputOps 的模块级变量，一个进程可能多个 MainWindow ⇒ 每轮执行前重绑，保证读到的是正在跑的那个窗口的数据 |
| `_source_kind_of(node)` | 这一轮的图从哪来 | 沿 `_binding_origin` 追到起点：视频源→视频、相机源→相机、其余→图片 |
| `_source_fps_of(node)` | 这一轮的来源帧率 | 视频源读 `video_info()` 的 fps；相机源读 `cap.get(CAP_PROP_FPS)`，读不到给 30；其余 0 |
| `_close_recordings(reason)` | 收尾所有录制中的视频 | 调 `OutputOps.close_all_recordings()` 并把每条收尾消息 `_append_log_hint()` 写进日志 |
| `_wants_overlay(node)` | 输出节点的"保存内容"是不是带检测叠加 | 缺省视为"带检测叠加"（默认值要和 `OutputOps.SAVE_OVERLAY` 一致） |
| `_origin_image_name(node)` | 这一轮"来源图片"的文件名（不含扩展名） | 追到起点节点取 `source_path`/`video_path`，追不到用主窗口当前图的路径；视频键 `路径#帧号` 取前半截；不是文件路径就返回空串 |
| `input_image_name_of_node(node)` | 给参数窗口用的公开入口 | 包一层 try/except 调 `_origin_image_name` |
| `_binding_origin(node, _depth)` | 沿绑定追到最上头的**起点节点** | 起点节点返回自己；绑到节点对象就递归；落到全局图像源返回 None |
| `_run_flow_pipeline_step(frame, target_node)` | **单步执行**入口 | 只跑 `target_node` 一个节点：输入 = `_node_input_frame(target)`（追到起点那张图）→ `_execute_node` → 一行日志 → `_render_display`。**不跑上游链**（这是 2026.10.5 定稿的语义） |
| `_execute_static(frame, mode, node, adopt_frame)` | 静态图执行的公共收尾 | 调连续/单步管线 → 刷日志 → 显示（画面键区分视频/相机/普通图）→ **写结果缓存（相机帧不写）**→ 收进图库 → 视频/相机分支：保存参数、推进帧游标、必要时启动自动出画面 |
| `_source_node_frame(allow_camera_open)` | 起点节点这轮能给出的图 | 按 `flow_nodes` 顺序问每个起点类节点；轮到相机源且允许开设备时**顺手把相机打开**（判据从"有没有连线"改成"是不是轮到它取图"） |
| `_flow_source_frame()` | 决定这一轮的"全局图像源"帧 | ① 主窗口当前图 → ② 起点节点兜底 → ③ 都没有则返回提示文案（调用方弹提示） |
| `run_flow_step(target_node)` | 单步执行的统一入口 | 开新一轮相机读数 → 必要时开相机 → 取帧 → `_execute_static(...,"step",target)` |
| `run_flow_continuous()` | 连续执行的统一入口 | 同上，`mode="continuous"`（内部按 `selected_node` 截断） |
| `on_step_execute()` | "单步执行"按钮槽 | 老预览在跑 → 走 `update_frame()`；否则要求先选中节点 → `run_flow_step()` |
| `on_continuous_execute()` | "连续执行"按钮槽 | 老预览在跑 → `update_frame()`；图库有图且范围=运行全部 → `run_all_images()`；否则先把"图片源"同步到选中那张 → `run_flow_continuous()` |
| `_legacy_camera_preview_active()` | 老摄像头预览是否在跑 | 判据 = `self.timer` 在跑 **且** 本页没有相机源节点（只看 `cap.isOpened()` 会把相机源节点的执行误判成老预览） |
| `run_all_images(mode)` | "运行全部"：逐张跑图库 | 开始时清空日志并逐张累积；每张：切参数 → 同步起点节点 → 执行 → 出错跳过继续；**"运行全部"中途被取消 = 急停**；"自动切换"关着则跑完还原选中项/画面/图片源路径 |
| `run_selected_image()` | 菜单"运行选中"：只跑当前这张 | 目前 UI 没接（保留为备用入口）；用 `gallery.current_index()/items()` 取条目 |
| `stop_batch()` | 工具栏/菜单"停止" | 置 `_batch_stop`；正在播放则 `_stop_video_playback()`，否则也要 `_close_recordings("用户停止")`（一帧帧点着录时也要能收尾） |

### 六、渲染与显示

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_render_display(base_img, executed, draw_roi)` | 渲染层：出显示图 | `base_img.copy()` → 按执行顺序调各检测算子的 `spec.draw()` 画结果 → 最后统一画 ROI 框（继承来的用洋红、手画用黄）。`draw_roi=False` 时**只画结果**（输出节点存"带检测叠加"时用） |
| `_display_image(img, image_key)` | 交给显示控件 | 转成 QImage → `image_view.set_image(img, image_key)` |
| `_show_static_image(frame)` | 显示一张静态图（切图） | 记住当前图 → 按图片切换参数存档 → 有缓存就重放缓存（画面+数据+日志），没有就显示原图并清日志 |
| `_update_execution_log(exec_info)` | 刷执行日志表（5 列） | 清空重填；`_log_accumulate` 时逐张累积；`_video_log_throttle` 时直接 return（播放中不刷） |
| `_update_execution_log_throttled(exec_info)` | 日志的"节流版" | 内容签名没变 + 距上次刷新 < 间隔就不重画（视频 30ms 一帧，重画会拖慢画面） |
| `_append_log_hint(text)` | 往日志**追加**一行"提示" | 用 `("-", 时间, "提示", "-", 文字)` 五元组；批量执行/收尾录制都靠它报话 |

### 七、显示键（画面缩放/平移）

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_display_key_of(frame)` | 普通图/视频帧的画面键 | 有文件路径就用路径（每张独立）；视频帧 → `video:路径`（**整段共用**，否则每帧复位缩放、播放时"画面一大一小"） |
| `_camera_display_key(node, mode)` | 相机帧的画面键 | `camera:编号` 整段共用；判据是"这一轮真用到相机源 + 相机真的开着"（相机帧每帧都是新副本，用对象同一性认不出来） |

### 八、相机（设备内部 API / 自动打开 / 老预览）

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_open_camera_device(camera_id, quiet)` | 打开相机设备（内部 API） | 已开着同一编号 → **复用不重开**；开着别的编号先关再开；打不开返回 False（`quiet=False` 才弹老警告窗）；记录 `_camera_device_id` |
| `_release_camera_device()` | 关设备释放资源 | 停老定时器 → `cap.release()` → 清 `_camera_round_frame`；**并收尾录制中的视频**（流没了文件必须 release） |
| `_latest_camera_frame()` | 注入给相机源节点的取帧器 | 相机没开返回 None；**一轮执行只读一次**（`_camera_round_frame` + `_begin_camera_round()` 作废）——否则起点取图和节点取图会各读一帧、画面与算法不是同一张 |
| `open_camera()` | 老"打开摄像头"按钮 | `close_camera()` → `_open_camera_device(quiet=False)` → 切视频槽参数 → 起 30ms 定时器 |
| `close_camera()` | 老"关闭"按钮 | `_release_camera_device()` → 清当前静态图 → 清场景与缩放 |
| `update_frame()` | 老预览的定时器槽 | 读一帧 → 缓存给取帧器 → 按 `video_processing_mode` 跑单步/连续 → 节流刷日志 → 显示 |
| `_begin_camera_round()` | 每轮执行让"相机读数"作废 | 轮次 +1、清缓存帧（配合 `_latest_camera_frame` 的一轮一读） |
| `_ensure_camera_device_open(camera_node)` | 准备好某个相机源节点的设备 | 统一判断 `open_on_run`、复用同一编号、切"视频槽"参数、写日志——两条开设备路径共用 |
| `_ensure_camera_open_for_run(node, mode)` | 执行前按需开相机 | 已开着 → True；不勾"执行时自动打开"或"这一轮没用到相机源" → False；否则调上一个函数 |
| `_camera_used_by(node, mode)` | 这一轮真用到相机源吗 | 单步沿父链追到相机源；连续看相机源有没有下游 |
| `_camera_source_node()` | 当前页的"相机源"节点 | 按名字在 `flow_nodes` 里找 |
| `_camera_tick(node, mode)` | 相机画面的一格 | 相机没了/被关了就停播；否则设节流标志、复用 `run_flow_step/run_flow_continuous` 跑一格（单步时实时取当前选中节点） |

### 九、视频与"自动出画面"

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_video_source_node()` | 当前页的"视频源"节点 | 按名字找 |
| `_video_used_by(node, mode)` | 这一轮真用到视频源吗 | 同相机；没用到就不该吃掉一帧 |
| `_advance_video_cursor()` | "执行后前进一帧" | `frame_index += 1`（`auto_next` 关着就不动）；一次执行只 +1 一次，保证同一轮多节点共用同一帧 |
| `_maybe_load_video_params()` | 视频参数"整段共用"的载入侧 | 换了视频路径时把"视频槽"那份参数载回一次（同一段只在换路径时载，免得覆盖播放中改的参数） |
| `_maybe_start_video_playback(node, mode)` | 自动出画面的**分派口** | 播放中/tick 中就直接返回；要求勾了"自动切换"；相机 → `_start_camera_playback()`，视频 → `_start_video_playback()` |
| `_start_camera_playback(node, mode)` | 开始出相机画面 | 与视频**共用同一个 QTimer**；帧率读不到按 30ms 一格；一直出到点「停止」（不判末尾、不循环） |
| `_start_video_playback(node, mode)` | 开始按原帧率播视频 | 间隔 = `1000/fps`（fps 坏值兜 25，夹到 5~1000ms）；连接 `_video_tick`；清 `_batch_stop`、置 `_video_playing` |
| `_stop_video_playback(reason)` | 停止自动出画面 | 清两个播放标志、停定时器、**收尾录制**、写日志（相机那条只停画面、不关设备） |
| `_video_tick(node, mode)` | 自动播放的一帧 | 先查停止标志 → 相机走 `_camera_tick`；视频判末尾（勾 `loop` 回第 0 帧，否则自动停）→ 设日志节流 → 复用执行入口跑一帧 |

### 十、图库（图像列表）

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `open_file()` | "打开文件"按钮 | 原生多选图片 → 每张 `import_image_path()` → 显示最后一张 |
| `_on_gallery_image_selected(img_bgr)` | 点图库缩略图 | `_show_static_image()` 切画面 |
| `_on_gallery_path_selected(path)` | 点缩略图时同步起点节点 | 调 `_sync_source_nodes_to_path()` |
| `add_folder_to_gallery()` | "＋文件夹"按钮 | 原生选目录 → `import_folder_path()` |
| `delete_gallery_item(item)` | 删除条目 | 先停播 + 关相机（本页有相机源且开着时）→ 从列表移除 → 清该路径的"图片源/视频源"路径 → 清参数存档/结果缓存/缩放记录 → 进 `_removed_paths` → **图库空了清画布** |
| `_sync_source_nodes_to_path(path)` | 把"图片源"节点路径改成这张 | 只改来源为"图片"的起点节点；改了要 `mark_dirty()` |
| `_clear_source_nodes_path(path)` | 清掉等于这个路径的来源 | 同时清 `source_path` 与 `video_path`（视频删了也不能再跑） |
| `_ensure_source_images_in_gallery()` | 把图片源用的图也放进图库 | 跳过 `_removed_paths` 里被用户删过的；**必须登记 `_frame_paths`**（漏登记会让这类图的标识退化成 id、缓存对不上） |
| `import_image_path(path)` | 单张导入图库 | 去重（按路径键）→ 缩略图 → 登记 `_frame_paths` |
| `import_folder_path(folder)` | 整目录导入 | 不递归子目录；坏文件静默跳过 |
| `import_paths(paths)` | 统一导入入口 | 每一项可能是文件或文件夹，分流到上面两个函数 |

---

---

> **本章属于**：② 节点契约（注册表）

## NodeRegistry.py（259 行；节点能力注册表 = "节点契约"）


**文件作用**：定义"一个算子应该声明什么"，并把各分类模块（`ProcessOps` / `SourceOps` / `OutputOps`）导出的声明表组装成 `NodeSpec` 注册进 `NODE_SPECS`；引擎、参数窗口、日志文案都从这里查"这个算子是什么"。它是整个扩展架构的枢纽：**加一个算子 = 一个算法方法 + 一张参数表 + 树里一项**。

**关键设计与原理**：
- **两类 kind 的语义**：`KIND_PROCESS`（改数据层图像）、`KIND_DETECT`（图像原样透传、只产出结果）、`KIND_SOURCE`（流程起点、自己造图）、`KIND_SINK`（输出类：图像原样透传，只把结果送出去——写磁盘）。
- **`draw()` 只画显示层**：`run()` 改数据、`draw()` 画显示，二者永不互相污染（"绿线被下游看见"这类 bug 的根治办法）。
- **检测类算子必须给算法 ROI 的 `.copy()`**：`Detector.line_detector/circle_detector` 会**就地**往传入数组上画线画圆，给原图就会被改。
- **不 import 分类模块的顶层**：文件末尾才 import 三个 `*_SPECS`，避免"注册表 ←→ 分类模块"循环导入。
- `is_flow_level` 与 `modifies_image` 两个属性是引擎的两处关键判据（详见 main.py 说明）。

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class NodeSpec` | 一个算子的能力声明 | 字段：name / kind / run / draw / format_result / whole_image_param / param_specs |
| `NodeSpec.__init__` | 组装声明 | 保存各字段；参数默认 None 表示"走专用窗口" |
| `NodeSpec.modifies_image`（属性） | 输出图像会不会和输入不一样 | `kind in (KIND_PROCESS, KIND_SOURCE)`；检测类与输出类都是 False（多上游时用它挑"真正改图"的那一支） |
| `NodeSpec.is_flow_level`（属性） | 参数是不是流程级配置 | `kind in (KIND_SOURCE, KIND_SINK)`；这类节点的参数不按图片归档 |
| `_run_line(detector, img, roi, params)` | 直线（检测类） | **只在 ROI 副本上跑** `line_detector`，结果按原图坐标偏移；数据层图像 `return img` 原样透传（同一个对象） |
| `_run_circle(detector, img, roi, params)` | 圆（检测类） | 同上，调 `circle_detector` |
| `_draw_line(display_img, results, params)` | 把直线结果画到显示层 | 每条 `(x1,y1,x2,y2)` 画绿线（0,255,0）粗 2 |
| `_draw_circle(display_img, results, params)` | 把圆结果画到显示层 | 每个 `(cx,cy,r)` 画红圆 + 红圆心 |
| `_format_line(results)` | 直线日志文案 | `"检测到N条直线"` |
| `_format_circle(results)` | 圆日志文案 | `"检测到N个圆"` |
| `_register_category(entries, kind)` | 把声明表组装成 NodeSpec | 遍历 entry dict，按字段建 `NodeSpec` 并登记（draw 一律 None，检测类在文件里手工登记） |
| `get_spec(name)` | 查算子声明 | 返回 None 表示"这个模块没实现"（引擎会透传 + 日志写"模块未实现"） |
| `is_implemented(name)` | 这个模块实现了吗 | 查注册表（人脸/颜色目前 False） |
| `result_bbox(results)` | 把结果算成原图坐标包围盒 | 支持直线 `(x1,y1,x2,y2)` 与圆 `(cx,cy,r)`；**只认 tuple/list**（dict 会被跳过）；无可用结果返回 None。供下游"ROI 继承" |
| `NODE_SPECS`（模块级 dict） | 注册表本体 | 键 = 算子名（与树、方框文字一致） |

---

---

> **本章属于**：③ 算子实现 · 处理类

## ProcessOps.py（319 行；处理类算子）


**文件作用**："处理"这一大类的**算法实现**（灰度/取反/滤波/二值化/形态学/边缘提取）与它们的参数声明 `PROCESS_SPECS`。处理类的共同语义：**输出图像和输入不一样**，下游看得见。

**关键设计与原理**：
- **一律"copy 出来 → 只在 ROI 上改 → 回填"**（`_apply_to_roi`）：绝不就地改传入数组（否则污染上游数据层）。
- **输出永远 3 通道 BGR**（`_to_bgr` 兜底）：单通道图丢给下游的 `cv2.line/circle` 会抛异常。
- **灰度是唯一带 `whole_image_param` 的**：`gray_full_image` 为真时引擎把 ROI 当整图（"所见即所算"）。
- 形态学/自适应阈值要求**奇数核**：`_odd()` 夹范围并强制奇数。

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `_to_bgr(img)` | 保证 3 通道 BGR | 单通道 → `cv2.cvtColor(GRAY2BGR)`；已是 3 通道直接返回 |
| `class ProcessOps` | 处理类算法集合 | 每个方法签名 `(img, roi, params) -> 新图` |
| `ProcessOps._apply_to_roi(img, roi, func)` | 处理类通用外壳 | `img.copy()` → 切 ROI → `func(patch)` → 回填 → `_to_bgr`；ROI 非法就返回整图副本 |
| `ProcessOps._odd(value, low, high)` | 夹范围 + 强制奇数 | 卷积核/自适应块尺寸必须是奇数 |
| `ProcessOps.to_gray(img)` | 灰度化（数据层版） | 始终返回 3 通道 BGR 灰度图（供别处复用） |
| `ProcessOps.gray(img, roi, params)` | 灰度 | ROI 内转灰度；`gray_full_image` 为真时整图 |
| `ProcessOps.invert(img, roi, params)` | 取反 | `255 - x` |
| `ProcessOps.blur(img, roi, params)` | 滤波 | 均值 / 高斯 / 中值（按 `blur_type`，核大小过 `_odd`） |
| `ProcessOps.threshold(img, roi, params)` | 二值化 | 先转灰度再算：固定阈值 / Otsu / 自适应（块大小过 `_odd`），结果补回 3 通道 |
| `ProcessOps.morphology(img, roi, params)` | 形态学 7 档 | 腐蚀 / 膨胀 / 开 / 闭 / 梯度 / 顶帽 / 黑帽；核形状（矩形/椭圆/十字）+ 核大小（奇数）+ 迭代次数 |
| `ProcessOps.edge(img, roi, params)` | 边缘提取 | Canny / Sobel / Laplacian（按 `edge_type`） |
| `format_process(results)` | 处理类日志文案 | 短文案（"结果数据"列会截断） |
| `_run_gray / _run_invert / _run_blur / _run_threshold / _run_morphology / _run_edge` | 6 个 `run` 适配器 | 统一签名 `(detector, img, roi, params)`，内部转调 `ProcessOps.<方法>`（`detector` 用不到） |
| `PROCESS_SPECS`（模块级 tuple） | 6 个处理类算子的声明表 | 每条 `{name, run, format_result, whole_image_param?, param_specs}` |

---

---

> **本章属于**：③ 算子实现 · 图像源类（采集）

## SourceOps.py（317 行；图像源类算子）


**文件作用**："采集"这一大类的实现：**图片源 / 视频源 / 相机源**。它们的共同点是"流程起点"——自己造图，没有上游。

**关键设计与原理**：
- **图片源**：三档来源（图片 / 文件夹 / 测试图）；带按路径的图片缓存；"当前图像"这一档会把传入的 `img` 原样返回（引擎给它 `None` 时即"没有图"）。
- **视频源**：`(路径, mtime, 大小)` 三元组缓存 `VideoCapture`，**与主窗口视频播放各读各的**（不抢读指针）；`run_video()` **只读当前帧、不前进**（前进由 main.py 的 `_advance_video_cursor()` 统一做，保证同一轮多节点共用同一帧）；读不到时按 `loop` 回第 0 帧，再失败就**原样透传 + 结果里带说明**（不弹窗）。
- **相机源**：**方案 A —— 复用主窗口相机**，自己不碰设备（靠主窗口注入的取帧器）；取不到帧就透传 + 说明；拿到帧 **`frame.copy()` 后返回**（主窗口那个缓冲会被下一帧覆盖）。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `first_image_in_folder(folder)` | 文件夹里第一张图（按文件名排序） | 遍历 + 扩展名过滤；没有返回空串 |
| `_load_image(path)` | 读一张图片（带缓存） | 按路径缓存 ndarray；读不出来返回 None |
| `_cached_test_image()` | 测试图（只生成一次） | 复用 `Detector.make_test_image()` |
| `run_source(detector, img, roi, params)` | **图片源** | 按 `source_type` 分流：图片 → 读 `source_path`；文件夹 → `first_image_in_folder`；测试图 → `_cached_test_image`；"当前图像" → 返回传入 `img`。返回值带 `[{"图片源": …}]` 说明 |
| `format_source(results)` | 图片源日志文案 | 短文案 |
| `_open_video(path)` | 缓存打开 VideoCapture | 键 = `(路径, mtime, 大小)`；返回 `(cap, 总帧数, fps)`；打不开 `(None, 0, 0.0)`；fps 坏值兜 25 |
| `video_info(path)` | 给主窗口读"总帧数 / 帧率" | 内部调 `_open_video`；打不开 `(0, 0.0)` |
| `run_video(detector, img, roi, params)` | **视频源** | 只读 `params["frame_index"]` 那一帧；越界时按 `loop` 回第 0 帧；再失败原样透传 + `[{"视频源": …}]` 说明（**不弹窗**） |
| `format_video(results)` | 视频源日志文案 | 写"第 N 帧 / 共 M 帧"这类短文案 |
| `set_camera_frame_provider(fn)` | 注入相机取帧器 | 模块级 `CAMERA_FRAME_PROVIDER`（主窗口启动时注入 `_latest_camera_frame`） |
| `run_camera(detector, img, roi, params)` | **相机源** | 相机类型不是 USB 相机 → 透传 + "暂不支持"；取不到帧 → 透传 + "没有可用的相机画面（相机未打开？编号 N）"；拿到帧 → **`frame.copy()`** 后返回（绝不交出会被覆盖的引用） |
| `format_camera(results)` | 相机源日志文案 | 短文案 |
| `SOURCE_SPECS`（模块级 tuple） | 3 个图像源算子的声明表 | 图片源：`source_type`(combo 图片/文件夹/测试图) + `source_path`(file)；视频源：`video_path`(file) + `frame_index`(int) + `auto_next`(bool) + `loop`(bool)；相机源：`camera_type`(combo，网络/工业相机用 `disabled` 置灰) + `camera_id`(int 0~9) + `resolution`(**只存不生效**) + `open_on_run`(bool) |
| `VIDEO_EXTS`（模块级常量） | 视频扩展名集合 | 供 main.py 判断"这个文件是不是视频" |

---

---

> **本章属于**：③ 算子实现 · 输出类（输出图像）

## OutputOps.py（512 行；输出类算子 = M5「输出图像」）


**文件作用**："输出"这一大类（目前一个节点）：把它从上游拿到的图像**写进磁盘**——图片序列或视频文件，内容可以是"数据层图像"或"带检测叠加"。它是 M5 的核心，也是全工程唯一在流水线里**产生副作用（写文件）**的节点，因此"什么时候开始写、什么时候收尾、参数变化怎么办"都在这里定义。

**关键设计与原理**：
- **原样透传**：`run_save()` 永远 `return img`（不复制、不改），所以它放流程中间不会影响下游。
- **`KIND_SINK` + `is_flow_level`**：输出节点的参数属于"流程级配置"（输出目录/文件名/格式…），不按图片归档，否则换图会把这些参数清空。
- **三个"注入式取用器"**（都是模块级变量 + `set_*_provider`）：`ROUND_INFO`（这一轮是哪个节点、来源是图片/视频/相机、源帧率）、`OVERLAY`（带检测叠加的那张图）、`INPUT_NAME`（这一轮输入图片的文件名）。因为 `run()` 只收到图像数组，这些上下文只能由主窗口注入。
- **录制生命周期**：`_RECORDINGS` 按 `node_key`（= `id(节点)`）登记正在录制的文件；第一帧自动开录（定尺寸/帧率）；**尺寸或输出参数变化 ⇒ 收尾 + 另开新文件**；`close_recording()` / `close_all_recordings()` 由主窗口在 6 个时机调用；**0 帧的录制删掉空文件**。
- **失败绝不弹窗**：目录为空、写不进去、编码器不支持，都只写进"结果数据"那一列（项目准则：执行/渲染路径不弹 `QMessageBox`）。
- **序号不进 `params`**：`_NEXT_INDEX` 缓存 + 首次扫目录取"最大序号 + 1"，所以关软件重开也不会覆盖旧文件。

| 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `set_round_info_provider(fn)` / `current_round_info()` | 注入 / 读取"这一轮上下文" | `{"node_key", "source_kind", "source_fps"}`；拿不到返回空 dict，各默认值兜住 |
| `set_overlay_frame_provider(fn)` / `current_overlay_frame()` | 注入 / 读取"带检测叠加的那张图" | 拿不到返回 None → 调用方退回数据层图像 |
| `set_input_name_provider(fn)` / `current_input_name()` | 注入 / 读取"这一轮输入图片名" | 文件名默认值 + 文件名为空时的兜底都靠它 |
| `_sanitize_name(name)` | 清洗文件名 | 去掉 `\ / : * ? " < > \|` 等非法字符；空则退回 `"output"` |
| `_resolve_dir(output_dir)` | 把输出目录解析成绝对路径 | 相对路径**按工程根**（本文件所在目录）解析，不看 cwd；支持 `~` 与 `%VAR%` |
| `_scan_next_index(folder, base, ext, start)` | 扫目录算"下一个序号" | 正则匹配 `名字_数字.后缀` 取最大 + 1；目录不存在返回 start |
| `_next_auto_index(folder, base, ext)` | 拿下一个可用序号（带缓存） | 缓存 `_NEXT_INDEX`，并 `while os.path.exists(...)` 往后让（防止被手工放的同名文件占位） |
| `_free_path(path)` | 给已存在的路径找一个空位 | 追加 `_1` / `_2` …（"按时间戳"策略用它防同毫秒撞名） |
| `build_output_path(params, ext)` | 算这次要写的完整路径 | 目录为空 → 返回 `("", 原因)`；文件名按"参数 > 这一轮输入图片名"；扩展名按 `ext` 或"图片格式"；三种重名策略：覆盖同名 / 按时间戳 / 自动编号 |
| `_resolve_fps(params, info)` | 录制标称帧率 | ① 手填 `video_fps` > 0 就用它；② 否则用来源帧率；③ 都没有给 25；夹在 1~240 |
| `_close_recording(state, reason)` | 收尾一个录制 | `writer.release()`；**0 帧 ⇒ 删掉空文件**；返回日志文案"录制结束（原因），共 N 帧，已保存 名字" |
| `close_recording(node_key, reason)` | 收尾某个节点的录制 | 从 `_RECORDINGS` 摘表 + 收尾；没在录返回空串 |
| `close_all_recordings(reason)` | 收尾全部录制 | 遍历表逐个收尾，返回消息列表（主窗口写日志） |
| `recording_count()` | 现在有几个在录 | `len(_RECORDINGS)`（测试与界面反馈用） |
| `_save_image_file(img, target, params)` | 图片序列模式 | 算路径 → `os.makedirs` → `cv2.imwrite`；失败/写不进去都返回说明文案；成功返回"已保存 名字（W×H）" |
| `_save_video_frame(img, frame, params, info)` | 视频文件模式（一帧） | 取 `video_format` → 目录校验 → 算 `signature`（目录/名/格式/策略/帧率/保存内容）→ 尺寸或 signature 变了先收尾旧文件并**摘表** → 没在录就 `cv2.VideoWriter(...)`（`isOpened()` False ⇒ "不支持该视频格式"）→ `write(frame)` → 返回"开始录制…"/"录制中…（第 n 帧）" |
| `run_save(detector, img, roi, params)` | **输出图像节点入口** | ① 按 `save_content` 决定存"数据层图像"还是取叠加图（取不到退回数据层）；② 按 `output_kind` 决定图片/视频（"自动"看 `source_kind`：视频/相机 ⇒ 视频文件）；③ 分派到上面两条；④ 始终 `return img` |
| `format_save(results)` | 输出节点日志文案 | 取 `results[0]["输出图像"]` |
| `OUTPUT_SPECS`（模块级 tuple） | 输出节点的声明表 | 8 项参数：`output_dir`(dir) / `output_name`(text，`default_from=input_image_name`) / `output_kind`(combo 自动·图片序列·视频文件) / `output_format`(combo) / `video_format`(combo，**不含 H.264**：本机缺 openh264) / `video_fps`(float 0=跟来源) / `save_content`(combo 数据层图像·带检测叠加) / `name_policy`(combo 自动编号·覆盖同名·按时间戳) |
| 模块级常量 | 界面选项与语义常量 | `FORMATS` / `VIDEO_FORMATS`（含 fourcc：mp4v/XVID/MJPG）/ `POLICY_*` / `SAVE_LAYER`、`SAVE_OVERLAY` / `KIND_*` / `SOURCE_IMAGE`、`SOURCE_VIDEO`、`SOURCE_CAMERA` / `_RECORDINGS` / `_NEXT_INDEX` |

---

---

> **本章属于**：④ 参数窗口 · 通用

## GenericProcessDialog.py（433 行；通用参数窗口）


**文件作用**：**按算子的参数声明自动生成界面**——"运行参数"页里的每一行都由 `param_specs` 决定（控件类型、中文名、默认值、选项）。有了它，"加一个算子"就不用再写界面（决策 b）。它继承 `LineParamsDialog`（复用那个 `.ui` 与"基本参数 / 显示结果"页），只重写/新增与动态参数有关的部分。

**关键设计与原理**：
- **控件类型**：`int` / `float` / `combo` / `bool` / `file`（浏览选文件）+ **M5 新增 `text`（纯文本）/ `dir`（选目录）**；`file` 的"浏览…"在**非起点节点**上会弹"选图片"框并把图导进图库，所以"输出文件名"必须用 `text` 而不是 `file`。
- **combo 支持 `options["disabled"]`**：把"预留"档位**置灰**（相机类型的网络/工业相机就用它，`QStandardItem.setEnabled(False)`）。
- **三类节点的窗口裁剪**：起点节点（`KIND_SOURCE`）去掉"基本参数"页 + 去掉"执行/连续执行"按钮；输出类节点（`KIND_SINK`）只去掉"基本参数"页；两者都清掉 ROI 参数。
- **`default_from` 动态默认值**：在 `_load_params()` **之后**才能补（`_apply_dynamic_defaults`），否则会被 `_load_params()` 用"空默认值"再 `setText("")` 冲掉——这是实测踩过的坑。
- **父类副作用要清**：父类 `_update_params()` 会把直线专用的 5 个参数也写进 `node.params`，子类必须 `pop` 掉，且**清理语句要放在所有提前 return 之前**。

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class GenericProcessDialog(LineParamsDialog)` | 通用参数窗口 | 构造顺序：建空控件表 → `super().__init__()` → `spec = get_spec(node.name)` → `_build_param_rows()` → `_remove_result_tab()` →（起点/输出类）`_remove_basic_tab()` →（起点）`_remove_run_buttons()` → `_load_params()` → `_apply_dynamic_defaults()` |
| `__init__(parent, node, main_window)` | 组装窗口 | 见上；`param_controls` 是 `{参数名: 控件}` 注册表 |
| `_param_group_layout()` | 找"运行参数"页里放行的布局 | 优先 `findChild(QVBoxLayout, "verticalLayout_8")`；找不到就在 `groupBox_3` 里现建一个（.ui 改名的兜底） |
| `_hide_item(item)` | 藏一个布局项里的所有控件 | 递归处理嵌套布局（处理类用不到直线那些行，要整体藏掉） |
| `_hide_line_rows(layout)` | 藏掉"运行参数"页里**已有的**行 | 那些行是直线专用控件（`.ui` 里写死的），通用窗口用不上 |
| `_build_param_rows()` | 按 `param_specs` 生成行 | 每行"中文名: 控件"；控件名统一 `param_<键名>`（便于 `findChild`） |
| `_apply_dynamic_defaults()` | 补"动态默认值" | 遍历参数，跳过"节点已存过值"的；调 `_apply_source_default()`；**必须在 `_load_params()` 之后** |
| `_apply_source_default(widget, kind, options)` | 按 `default_from` 填默认值 | 目前支持 `input_image_name`：向主窗口要"这个节点这一轮的输入图片名"；控件已有内容就不动 |
| `_make_widget(key, kind, options)` | 造控件（按类型） | combo（含 disabled 置灰）/ int（含 `odd` 纠偏）/ float / bool / file（编辑框+浏览…）/ text / dir（编辑框+选择目录…）；造不出来返回 None |
| `_to_odd(value)` | 偶数 → 最近奇数 | 卷积核 / 自适应块要求奇数 |
| `_browse_wants_folder()` | "浏览…"该弹选文件夹还是选图片 | 起点节点且 `source_type == "文件夹"` → 选文件夹；否则选图片 |
| `_browse_file(edit, filters)` | file 参数的"浏览…" | 原生对话框；选完**静默导入图库/文件夹**（坏文件跳过）；把路径填进编辑框 |
| `_browse_dir(edit)` | dir 参数的"选择目录…" | 原生选文件夹；**只填路径**，不导入、不建目录、不弹提示 |
| `_remove_result_tab()` | 去掉"显示结果"页 | 处理类/输出类没有结构化结果 |
| `_remove_basic_tab()` | 去掉"基本参数"页 | 起点节点没有上游；输出类节点也不需要 ROI/继承 |
| `_remove_run_buttons()` | 去掉"执行/连续执行"按钮 | 起点节点的参数只是"从哪拿图"，留那两个按钮会让人误会 |
| `on_ok()` | "确定"按钮 | 起点节点：只保存参数并关窗；其它算子沿用父类（先单步执行一次再关） |
| `_load_params()` | 把节点参数灌进控件 | 遍历 `param_specs` 取 `node.params` 的值 → `_set_widget_value()` |
| `_update_params()` | 把控件值写回 `node.params` | 先 `super()._update_params()`（基本参数）→ **pop 掉直线专用 5 个字段** → 起点/输出类再 pop ROI 相关字段 → 遍历动态控件写值 |
| `_set_widget_value(kind, widget, value)` | 控件 ← 值 | 按类型分别 `setCurrentText/setValue/setChecked/edit.setText/widget.setText` |
| `_widget_value(kind, widget)` | 控件 → 值 | 按类型分别读；`file`/`dir` 读 `widget.edit.text()` |
| 模块级 `LINE_ONLY_WIDGETS` | 直线专用控件名元组 | `_hide_line_rows()` 用它筛 |

---

> **本章属于**：④ 参数窗口 · 基类

## LineParamsDialog.py


**文件作用**：本项目"参数窗口"体系的基类文件。它提供三样东西：一个能在弹窗里显示图像并鼠标框选 ROI 的画布 `ROISelectGraphicsView`、一个把它包成独立模态小窗的 `ROISelectDialog`，以及主配置窗口基类 `LineParamsDialog`（加载 `LineParamsDialog.ui`，管理"图像源绑定 + ROI（手绘 / 继承上游）+ 运行参数 + 结果计数"）。主界面双击流程图方框时由 `main.py::on_node_double_clicked → _open_node_dialog` 打开（"直线"节点直接用它），同时它也是 `CircleParamsDialog`、`GrayParamsDialog`、`GenericProcessDialog` 的父类。

**关键设计与原理**：
- **界面来自 .ui，控件靠 `findChild` 取**：`QUiLoader().load('LineParamsDialog.ui')` 用的是**相对路径**（所以程序必须在工程根目录下运行），加载结果塞进自身的 `QVBoxLayout`（`setContentsMargins(0,0,0,0)`）；只有 `tabWidget` 是直接属性访问（`self.ui.tabWidget`），其余控件全部 `findChild`。**控件 objectName 是代码与 .ui 之间的隐式契约，改名会静默失效**（代码大多用 `if 控件:` 兜底，不报错）。
- **参数契约 = `node.params` 字典**：`_load_params()` 只负责"params → UI"，`_update_params()` 只负责"UI → params"，两者都是给子类重写的钩子（Circle 加圆参数、Gray 加"作用于整图"、Generic 加动态页）。图像源绑定是例外，单独存在 `node.input_source` 上（不是运行参数）。
- **执行路径只有主窗口那一条**：静态图下"执行 / 连续执行"统一调 `main_window.run_flow_step(node)` / `run_flow_continuous()`（计算→显示→写结果缓存→刷日志都在主窗口里），所以从参数窗口点执行和从主界面点执行结果完全一致；视频 / 摄像头才走老路（`video_processing_mode` + `update_frame()`）。
- **ROI 默认尺寸按"这个节点实际会收到的图"算**：优先 `main_window._node_input_frame(node)`（沿图像源绑定往上追到起点那张图），追不到才退回 `current_static_image`，再退回 `cap.get(CAP_PROP_FRAME_WIDTH/HEIGHT)`。老实现只看主窗口当前图，导致"图像源绑到图片源"的下游节点 ROI 默认尺寸对不上（用户实测反馈的坑）。
- **`.ui` 里 ROI 区域是绝对定位**：`groupBox_2` 没有布局管理器，子控件写死 geometry；行数一变（多出"外扩""作用于整图"，或选"继承"少几行）就会挤在一起。所以 `__init__` 里在代码中给 `groupBox_2` 现场套一个 `QVBoxLayout`，按 `roi_rows_widget → roi_buttons_widget → roi_params_widget` 排，让高度跟着内容走。
- **框选画布的属性不能叫 `self.scene`**：会遮蔽 `QGraphicsView.scene()` 方法，因此场景属性命名为 `roi_scene`（代码里明确注释了这一点）。坐标一律用 `mapToScene(event.pos())` 换算，自动抵消图片缩放带来的坐标差异。
- **"继承自"下拉框用文字反查而不是 `findData`**：类属性 `ROI_SOURCE_ITEMS = (("roi", "上游 ROI 框"), ("result", "上游结果框"))`，注释说明 PySide2 的 `findData` 比对 QVariant（装 Python 对象时不可靠），所以按 itemText 字符串匹配来映射内部取值。

**类 / 函数清单**：

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class ROISelectGraphicsView(QGraphicsView)` | 框选 ROI 用的画布：把 QPixmap 当背景，用鼠标在上面画绿色矩形或圆，并把框选结果换算成像素坐标 | 自建 `QGraphicsScene` 存背景（属性名 `roi_scene`，避免遮蔽 `scene()`）；`addPixmap` 后 `setSceneRect(0,0,w,h)`；开 `QPainter.Antialiasing`、`FullViewportUpdate`、`NoDrag`；`shape_type` 决定画矩形还是圆，两套状态各自记一份 |
| `ROISelectGraphicsView.__init__` | 初始化画布、背景图与矩形/圆两套状态变量 | 参数 `pixmap`（图像载体）、`shape_type`（"矩形"/"圆"）、`parent`；矩形状态 `start_point / rect_item / final_rect`，圆状态 `center_point / ellipse_item / center_dot_item / final_ellipse`；注释说明抗锯齿 + 全视口刷新是为了交互顺滑且不与框选逻辑冲突 |
| `ROISelectGraphicsView.mousePressEvent` | 鼠标按下：记起点；画圆时同时画出圆心绿点；清掉上一次的图形 | 仅响应 `Qt.LeftButton`；`start_point = mapToScene(event.pos())`；画圆时先 `removeItem` 旧的 `center_dot_item`，再建 6×6 的 `QGraphicsEllipseItem`（`center-3`）填绿色 `QBrush` 当圆心；随后按当前形状 `removeItem` 掉已有的 `rect_item` / `ellipse_item` 并置 None |
| `ROISelectGraphicsView.mouseMoveEvent` | 鼠标拖拽：实时画/更新绿色矩形或圆 | 条件是"已按下过起点 + `event.buttons() == Qt.LeftButton`"；矩形用 `min()` 取左上角、`abs()` 取宽高（防反向拖拽），无 `rect_item` 就新建并设绿色 2px 实线 `QPen`，有就 `setRect`；圆用 `np.sqrt(dx²+dy²)` 算半径，圆心点每帧 `setRect(cx-3,cy-3,6,6)` 保持不动，圆用外接矩形 `(cx-r, cy-r, 2r, 2r)` |
| `ROISelectGraphicsView.mouseReleaseEvent` | 鼠标松开：定稿框选结果并结束本次框选 | 左键且 `start_point` 非空才收尾；矩形把 `QRectF(起点, 终点).normalized()` 存进 `final_rect`（`.normalized()` 规范化，反向拖也能用）；圆算 r 后存 `final_ellipse = (cx, cy, r)`；最后 `start_point = None` 彻底结束 |
| `ROISelectGraphicsView.get_roi` | 取框选结果坐标 `(x, y, w, h)` | 矩形：有 `final_rect` 就返回 `int()` 取整后的 x/y/w/h；圆：有 `final_ellipse` 就返回 `(cx, cy, r, 0)`（**圆的第 4 个值固定 0**）；两者都没有返回 `(0,0,0,0)`。用 `hasattr` + 真值双重判断 | 
| `class ROISelectDialog(QDialog)` | 把框选画布包成一个独立模态小窗（"确定 / 取消"） | 只做外壳与图片格式转换，框选逻辑全在内部的 `ROISelectGraphicsView` 里；`get_roi` 直接转发给画布 |
| `ROISelectDialog.__init__` | 建窗、转换图片、装画布与按钮、调整窗口尺寸 | 参数 `img_bgr`（OpenCV BGR）、`parent`、`shape_type`；`setWindowTitle("ROI 框选工具")` + `setModal(True)`；BGR→RGB 后 `QImage(..., Format_RGB888)` → `QPixmap.fromImage`（注释说与 `ImageGraphicsView.set_image` 同做法）；`QVBoxLayout` 里放画布，再 `fitInView(sceneRect, Qt.KeepAspectRatio)` 自适应并消除滚动条；底部 `QPushButton("确定"/"取消")` 分别连 `accept`/`reject`；`resize(min(800, w+30), min(600, h+60))` 防超出显示器 |
| `ROISelectDialog.get_roi` | 对外暴露框选坐标 | 一行转发 `self.view.get_roi()` |
| `class LineParamsDialog(QDialog)` | 参数窗口基类：三页（基本参数 / 运行参数 / 显示结果）+ 图像源绑定 + ROI 绘制/继承 + 执行/连续执行/确定 | 见下方各方法；子类通过重写 `_load_params` / `_update_params` 扩展参数 |
| `LineParamsDialog.__init__` | 加载 .ui、取齐所有控件引用、接信号、设默认值、回填已有参数与结果计数 | 参数 `parent / node / main_window` 存成属性；`QUiLoader().load('LineParamsDialog.ui')` 嵌进 `QVBoxLayout`；`input_source` 填充后接 `currentIndexChanged`（注释：换图像源立刻记到节点上，免得用户点 × 关窗导致绑定丢失）；取 ROI 相关控件（两个单选框、四个 spin、外扩、继承自）、`groupBox_2 / roi_rows_widget / roi_buttons_widget / roi_params_widget` 并**给 groupBox_2 套 QVBoxLayout**；`pos_correction_slider.setValue(0)`；取 `comboBox`(形状)、`label_w/label_h`、三个按钮、`cb_hide_roi`、`cb_gray_full_image`（**先 `setVisible(False)`，只有灰度窗口才显示**）、`pushButton`(框选)、运行参数 5 个 spin、`label_7` 当结果计数并置 "0"；`btn_roi_toggle` 初始文字 "ROI参数 ▲"；信号：`roi_draw/roi_inherit.toggled → _update_roi_params_visibility`、`shape_combo.currentTextChanged → _update_shape_layout`、三按钮 → `on_step_click/on_ok/on_cont_click`；先 `roi_inherit.setChecked(True)`（用户 2026.10.5 要求新节点默认继承上游），再 `_load_params()`（会按 params 覆盖），再强制跑一次 `_update_shape_layout`；`self.ui.tabWidget.setCurrentIndex(0)` 固定显示"基本参数"；最后若主窗口有 `last_detected_data` 就 `update_result_count` |
| `LineParamsDialog._candidate_sources` | 列出可以当"图像源"的上游方框（直接或间接连到当前节点的所有祖先） | `node`/`main_window` 为空返回 `[]`；取 `main_window.flow_edges`，整理成 `{下游节点: [上游节点...]}`；用 `seen` 集合从当前节点的父节点做 BFS 展开（同时挡住连线成环时的死循环）；顺序是"先直接上游、再往上一层" |
| `LineParamsDialog._populate_input_source` | 填"图像源"下拉框，并恢复节点上已保存的绑定 | `clear()` 后依次加：`自动（继承上游图像）`→`AUTO_SOURCE`、`全局图像源（原图）`→`SOURCE_KEY`、每个上游 `"节点：{name}"`→节点对象；恢复选中项时**不**用 Qt `findData()`（QVariant 装 Python 对象不可靠），而是遍历 `itemData(i)`：节点对象按身份 `is` 比、字符串按值比；找不到或本来没绑（None）就落回第 0 项"自动" |
| `LineParamsDialog._on_input_source_changed` | 下拉框一改就写回节点 | 忽略 `_index`，直接调 `_save_input_source()`（注释：这个绑定不是"运行参数"，不跟图片走） |
| `LineParamsDialog._save_input_source` | 把下拉框当前的图像源绑定写到 `node.input_source` | `node` 为空或控件不存在则返回；`currentData()` 若是 `AUTO_SOURCE` 字符串则存 `None`（引擎会沿连线去找上游），否则原样存绑定对象（全局源字符串或上游节点对象） |
| `LineParamsDialog._load_params` | 从 `node.params` 回填 UI；ROI 宽高默认值用"当前图像尺寸" | 写 `roi_x/roi_y`（默认 0）；宽高默认值 `640×480`，优先 `_node_input_frame(node)`，其次 `main_window.current_static_image`（`shape[:2]` 是 h,w，注意赋值顺序 `h, w = ...; default_w, default_h = w, h`），再其次 `cap.get(CAP_PROP_FRAME_WIDTH/HEIGHT)`（只有 >0 才用）；写 `hide_roi`（默认 False）、`roi_w/roi_h`、`roi_shape`（默认 "矩形"）、`roi_inherit`（**默认 True**，明确存过 False 才回到"绘制"）、`roi_margin`（默认 0）、`roi_source`（经 `_set_roi_source_to_ui`）；最后加载 5 个运行参数：`canny_low=50`、`canny_high=150`、`hough_threshold=100`、`min_line_length=100`、`max_line_gap=10` |
| `LineParamsDialog._update_params` | 把 UI 上的值写回 `node.params`（子类重写它以扩展） | 写 `roi_x/roi_y/roi_w/roi_h`、`roi_shape`、`roi_inherit`、`roi_margin`、`roi_source`（经 `_roi_source_from_ui`）、顺手再 `_save_input_source()` 一次、5 个运行参数、`hide_roi`。**它不保存 `gray_full_image`**，那由 Gray 子类补 |
| `LineParamsDialog.on_step_click` | "执行"按钮：单步执行当前节点；返回值被"确定"用来决定窗口关不关 | 先 `_update_params()`；`roi_w==0 or roi_h==0` → `QMessageBox.warning("请输入ROI区域！")` 并 `return False`；有主窗口时先判断 `video_ready`（`current_static_image is None` 且 `cap` 已打开）：**不是视频**就走静态统一入口 `run_flow_step(node)`，成功则 `update_result_count(last_detected_data)` 并返回 True，失败返回 False（提示已由主窗口弹过）；**是视频**则设 `video_processing_mode="step"`、`video_step_node=node`、调 `update_frame()` 并返回 True；没有主窗口返回 False |
| `LineParamsDialog.on_cont_click` | "连续执行"按钮：按完整流程图顺序执行 | 同样先 `_update_params()` 并拦截 ROI 全 0（警告后 `return`，无返回值）；不是视频就调 `run_flow_continuous()`，成功则刷新结果计数；是视频则设 `video_processing_mode="continuous"`、`video_step_node=None`、`update_frame()` 恢复完整流程检测 |
| `LineParamsDialog.on_ok` | "确定"按钮：先执行一次单步检测，成功才关窗 | `if self.on_step_click(): self.accept()` —— ROI 为 0 或没有可用图时窗口保持不关闭 |
| `LineParamsDialog.toggle_roi_params` | "ROI参数"按钮：展开 / 折叠 XYWH 参数区并同步箭头 | 读 `roi_params_widget.isVisible()` 取反后 `setVisible`，再按**点击前**的状态把按钮文字设成 "ROI参数 ▲"（变可见）或 "ROI参数 ▼"。（未注释，实现细节：用的是 `isVisible()`，窗口本身不可见时该值可能恒为 False） |
| `LineParamsDialog._set_roi_margin_visible` | 显示 / 隐藏"外扩"那一行 | 对 `label_roi_margin` 和 `spin_roi_margin` 分别 `setVisible`（各自判空），注释说明只有 ROI 创建 = 继承上游 时才用得上 |
| `LineParamsDialog.ROI_SOURCE_ITEMS` | 类属性常量：`("继承自"下拉框文字 → 内部取值)` 的对应表 | 值为 `(("roi", "上游 ROI 框"), ("result", "上游结果框"))`；注释：用文字匹配，不依赖 PySide2 的 `findData` |
| `LineParamsDialog._set_roi_source_to_ui` | 把 `params["roi_source"]` 反映到"继承自"下拉框 | 用 `dict(ROI_SOURCE_ITEMS).get(key, "上游 ROI 框")` 得到文字（认不出来时按默认"上游 ROI 框"），再遍历 `combo_roi_source` 的 `itemText(index)` 匹配后 `setCurrentIndex`；匹配不到就什么都不做 |
| `LineParamsDialog._roi_source_from_ui` | 从"继承自"下拉框读出内部取值 | 控件不存在返回 `"roi"`；拿 `currentText()` 反查 `ROI_SOURCE_ITEMS`，识别不出也返回 `"roi"` |
| `LineParamsDialog._set_roi_source_visible` | 显示 / 隐藏"继承自"那一行 | 对 `label_roi_source` 与 `combo_roi_source` 分别 `setVisible`（判空），只有选"继承上游"时才用得上 |
| `LineParamsDialog._update_roi_params_visibility` | 按"ROI创建"单选框（绘制 / 继承上游）控制框选按钮、展开按钮与参数区的可见性 | 走 `self.roi_draw.isChecked()`（而不是读 sender）；**绘制**：显示 `btn_roi_toggle`，参数区若不可见则显示并置 ▲，显示"框选"按钮，隐藏"外扩"和"继承自"；**继承上游**：隐藏参数区与 `btn_roi_toggle`（ROI 从上游来，手绘没意义，整行空了外层布局会自动收掉高度），隐藏"框选"，显示"外扩"和"继承自" |
| `LineParamsDialog._update_shape_layout` | 按形状下拉框文字动态改标签名与行可见性 | 形参是 `shape_text`（不是直接用控件值，便于在 `__init__` 里强制对齐一次）；`"圆"` → `label_w` 文本改 "R:"，隐藏 `label_h` 与 `spin_roi_h`（第四个参数只留 XYR 三个）；其他 → `label_w` 改回 "W:"，显示 `label_h` 与 `spin_roi_h` |
| `LineParamsDialog.refresh_size` | 供主窗口在加载新图片后主动触发，重新按图像真实尺寸刷新 ROI 宽高 | 被 `main.py` 在导入图片后调用（`current_dialog.isVisible()` 时）；取图顺序同 `_load_params`：`_node_input_frame(node)` → `current_static_image`，拿到就 `shape[:2]` 后**直接强制 `setValue(w/h)`**（注释：避免被 `node.params` 里的旧值盖掉）；否则退到摄像头 / 视频流的 `cap.get` 宽高，只有 >0 才写 |
| `LineParamsDialog.on_select_click` | "框选"按钮：取一张图弹框选窗，把结果回填到 XYWH | 取图三级兜底：`_node_input_frame(node)` → `current_static_image` → 若 `cap` 已打开则**先暂停主窗口定时器**（`timer.stop()` 并记 `timer_paused`）再 `cap.read()` 抓一帧，读完/失败都 `timer.start(30)` 恢复（失败还要弹"视频/摄像头读取失败…"并 return）；仍然没图就弹"请先导入图片或打开摄像头/视频！"；否则 `ROISelectDialog(img_bgr, self, shape_text).exec_()`，Accepted 时 `get_roi()`：先无条件填 X/Y，再按形状——**矩形**填 XYWH，**圆**把 `(cx, cy, r)` 换算成外接矩形（左上角 `cx-r, cy-r`，宽高 `2r`）后填四个框 |
| `LineParamsDialog.update_result_count` | 按传入数据刷新"显示结果"页的直线数量 | `label_result_count` 不存在直接返回；只有 `node.name == "直线"` 才统计：`data` 非空时数 `isinstance(item, tuple) and len(item) == 4` 的项（元组 4 个值 = 起点 xy + 终点 xy），写进 label；`data` 为 None 或节点名不符则填 "0" |
| 模块级 `if __name__ == '__main__':`（测试入口，非函数） | 不启动主程序，单独把基类窗口跑起来看效果 | 建 `QApplication`；读 `image/lena.png`，读不到就 `from Detector import make_test_image` 生成测试图（注释：黑图什么都测不出来）；造 `MockMainWindow` / `MockNode` 后 `LineParamsDialog(...)`，`resize(390, 560)` 并 `show()` |
| `class MockMainWindow`（`__main__` 内） | 测试用的假主窗口，模拟对话框依赖的主窗口接口 | `__init__` 里给 `current_static_image`、`cap=None`、`video_processing_mode="continuous"`、`video_step_node=None`；其余方法全是"占位 + 打印"，防止调用时抛 `AttributeError` |
| `MockMainWindow.__init__` | 存下测试图并补齐对话框会读的属性 | `self.current_static_image = img`，`cap=None`（让代码走静态图分支） |
| `MockMainWindow.update_frame` | 占位：模拟主窗口刷新视频帧 | `@staticmethod`，只 `print("[Mock主窗口] 执行视频帧更新 ...")`（注释：加 staticmethod 是为消掉"方法可能为 static 及未使用的形参"警告） |
| `MockMainWindow._display_image` | 占位：模拟主窗口显示图片 | `@staticmethod`，打印图片尺寸 `img.shape` |
| `MockMainWindow._execute_static` | 占位：模拟旧的静态执行入口 | `@staticmethod`，打印 mode 与节点名，`return []` 模拟检测结果（注释：配置窗口的执行现在统一走主窗口入口） |
| `MockMainWindow._update_execution_log` | 占位：模拟刷新执行日志 | `@staticmethod`，打印日志行数 `len(exec_info)` |
| `MockMainWindow._run_flow_pipeline_step` | 占位：模拟单步执行流水线 | `@staticmethod`，打印节点名，返回 `(frame, [], [])`（与主窗口"图, 数据, 一行日志"的约定保持一致） |
| `MockMainWindow._run_flow_pipeline` | 占位：模拟完整流程图执行 | `@staticmethod`，打印提示，返回 `(frame, [], [])` |
| `class MockNode`（`__main__` 内） | 测试用的假流程图节点 | `params = {}`、`name = "模拟检测节点"`；注意它没有 `input_source`，所以下拉框恢复绑定那一步走的是 `getattr(..., None)` 的兜底 |
| `MockNode.__init__` | 造一个空参数、带名字的假节点 | 直接赋 `self.params = {}`、`self.name = "模拟检测节点"` |

---

> **本章属于**：④ 参数窗口 · 圆专用

## CircleParamsDialog.py


**文件作用**：圆检测节点的专用参数窗口。它继承 `LineParamsDialog`，**完全复用** `LineParamsDialog.ui` 的"基本参数"页（图像源 / ROI 绘制或继承 / 框选 / XYWH）与底部三个按钮，只在窗口里把"运行参数"那 5 行的标签文字改成圆的参数名（dp / minDist / param1 / param2 / minRadius），并把 5 个整数微调框换成合适的控件（dp 换成 `QDoubleSpinBox`）。主界面在 `node.name == "圆"` 时由 `main.py::on_node_double_clicked` 打开它。

**关键设计与原理**：
- **不新建 .ui，靠 `replaceWidget` 原位换控件**：`_replace_widget` 用 `parentWidget().layout().replaceWidget(旧, 新)` 把旧控件换掉，新控件"完美继承旧控件原本的物理坐标、对齐方式、拉伸比例"，不破坏父布局结构；旧控件 `setParent(None)` 脱钩后 `deleteLater()` 释放。注释明确写了"不动原布局"。
- **父类 `__init__` 末尾会调一次 `_load_params()`，那时新控件还不存在**：所以重写的 `_load_params` 第一句就是 `if not hasattr(self, 'spin_dp'): return` 当守卫；子类 `__init__` 末尾再调一次 `self._load_params()` 真正灌值。这是"子类要先建控件、后加载参数"的固定套路。
- **替换后父类留下的 `self.spin_canny_low` 等引用是悬空的**（旧 C++ 对象已被 `deleteLater`），但重写的 `_load_params` / `_update_params` 不再碰它们，所以安全；反过来说，**它不往 `node.params` 里写 `canny_low` 那 5 个直线参数**（父类 `_update_params` 被整体重写掉了）。
- **标签改名与控件替换都沿用直线的 objectName**（`canny_low`、`spin_canny_low`…），名字与实际语义已经不符，是历史包袱；`_replace_widget` 里是 `findChild(QSpinBox, old_name)`，所以它只能替换 `QSpinBox` 类型的旧控件。
- **与父类的默认值不一致（坑）**：父类 `_load_params` 里 `roi_inherit` 默认 True（用户 2026.10.5 要求"继承上游"），而本文件重写的 `_load_params` 用的是 `params.get("roi_inherit", False)`，即**没存过参数的圆窗口默认落在"绘制"**；ROI 宽高默认值这里也只看 `main_window.current_static_image`，没有追图像源。

**类 / 函数清单**：

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class CircleParamsDialog(LineParamsDialog)` | 圆检测的参数窗口：复用父类界面与基本参数行为，改写运行参数 5 行 | 只重写 `_load_params` / `_update_params` / `update_result_count` 三个钩子，其余（ROI、图像源、执行按钮）全继承 |
| `CircleParamsDialog.__init__` | 搭好父类界面后，改标题、改标签文字、把 5 个 spin 换成圆专用控件、再加载参数 | `super().__init__(parent, node, main_window)`；`setWindowTitle("圆检测")`；`findChild(QLabel,"label_6").setText("圆数量：")`；用 `_set_label_text` 把 `canny_low→累加器分辨率(dp):`、`canny_high→圆心最小距离(minDist):`、`threshold→Canny高阈值(param1):`、`min_line_length→累加器阈值(param2):`、`max_line_gap→最小半径(minRadius):`；`spin_dp = QDoubleSpinBox()`（range 0.1–10.0、singleStep 0.1、decimals 2、初值 1.00）替换 `spin_canny_low`；`spin_min_dist`（QSpinBox 10–10000，初值 150）替换 `spin_canny_high`；`spin_param1`（0–1000，初值 100）替换 `spin_hough_threshold`；`spin_param2`（0–1000，初值 80）替换 `spin_min_line_length`；`spin_min_radius`（0–10000，初值 20）替换 `spin_max_line_gap`；最后调 `self._load_params()` 把节点已有参数灌进新控件 |
| `CircleParamsDialog._set_label_text` | 辅助函数：只改某个 QLabel 的文字（不动布局） | 用 `self.ui.findChild(QLabel, label_name)` 取控件，取到就 `setText(new_text)`，取不到静默跳过（`if label:`） |
| `CircleParamsDialog._replace_widget` | 辅助函数：在父布局的原位置拔掉旧控件、插上新控件 | docstring 说明 `old_name` 是旧控件 objectName、`new_widget` 是建好的新控件实例；实现：`findChild(QSpinBox, old_name)` 取旧控件 → `old_widget.parentWidget().layout()` 取父布局 → 有布局才 `replaceWidget(old, new)`，随后 `old_widget.setParent(None)` 脱钩、`old_widget.deleteLater()` 释放；**父布局取不到时整个替换被静默跳过**（旧控件仍在） |
| `CircleParamsDialog._load_params` | 重写：加载参数（ROI 基础参数 + 圆的 5 个参数） | 先 `if not hasattr(self, 'spin_dp'): return`（挡住父类 `__init__` 期间的那次调用）；`node` 为空返回；ROI 的 x/y（默认 0）、w/h（默认值只在 `current_static_image` 非空时取它的 `shape[:2]`，否则 640×480）、`roi_shape`（默认"矩形"）、`roi_inherit`（**默认 False → "绘制"**）、`roi_margin`（默认 0）、`roi_source`（默认 "roi"）、`hide_roi`（默认 False）；圆的 5 个参数键名是 `dp`(1.0) / `min_dist`(150) / `param1`(100) / `param2`(80) / `min_radius`(20) |
| `CircleParamsDialog._update_params` | 重写：保存参数（基础参数 + 圆的 5 个参数） | `node` 为空返回；写 `roi_x/roi_y/roi_w/roi_h`、`roi_shape`、`roi_inherit`、`roi_margin`、`roi_source`，再 `_save_input_source()`（注释：图像源绑定顺手存一次），再 `hide_roi`；最后把 5 个新控件写进 `dp / min_dist / param1 / param2 / min_radius`；**不写父类那 5 个直线参数键** |
| `CircleParamsDialog.update_result_count` | 重写：把"显示结果"页刷成圆的数量 | `label_result_count` 不存在返回；只有 `node.name == "圆"` 才统计：`data` 非空时数 `isinstance(item, tuple) and len(item) == 3` 的项（圆 = 圆心 x、y + 半径），写入 label；否则填 "0" |
| 模块级 `if __name__ == '__main__':`（测试入口，非函数） | 独立测试入口：单独看圆窗口，验证"5 行参数被完美替换，无残留、无错位" | 建 `QApplication`，读 `image/lena.png`（失败用 `Detector.make_test_image`），造 mock 后 `CircleParamsDialog(...)`，`resize(390, 560)` 并 `show()`；首次运行时它会 `print` 那句自检提示 |
| `class MockMainWindow`（`__main__` 内） | 测试用假主窗口 | 与基类文件里的同名 mock 结构一致：`current_static_image`、`cap=None`、`video_processing_mode`、`video_step_node` |
| `MockMainWindow.__init__` | 存测试图并补齐对话框会读的属性 | `self.current_static_image = img`；`cap = None`；`video_processing_mode = "continuous"`；`video_step_node = None` |
| `MockMainWindow.update_frame` | 占位：模拟刷新视频帧 | `@staticmethod`，只打印一行 |
| `MockMainWindow._display_image` | 占位：模拟显示图片 | `@staticmethod`，打印 `img.shape` |
| `MockMainWindow._execute_static` | 占位：模拟静态执行入口 | `@staticmethod`，打印 mode 与节点名（`node.name if node is not None else "-"`），返回 `[]` |
| `MockMainWindow._update_execution_log` | 占位：模拟刷新执行日志 | `@staticmethod`，打印 `len(exec_info)` |
| `MockMainWindow._run_flow_pipeline_step` | 占位：模拟单步执行 | `@staticmethod`，返回 `(frame, [], [])` |
| `MockMainWindow._run_flow_pipeline` | 占位：模拟连续执行 | `@staticmethod`，返回 `(frame, [], [])` |
| `class MockNode`（`__main__` 内） | 测试用假节点 | `params = {}`、`name = "模拟圆节点"`（**注意不是 "圆"，所以 `update_result_count` 会走 else 填 0**） |
| `MockNode.__init__` | 造一个空参数、带名字的假节点 | 赋 `self.params = {}`、`self.name = "模拟圆节点"` |

---

> **本章属于**：④ 参数窗口 · 灰度专用

## GrayParamsDialog.py


**文件作用**：灰度节点的参数窗口。它同样继承 `LineParamsDialog`、共用 `LineParamsDialog.ui`，但把对灰度没意义的页去掉、只留"基本参数"，并多出一个"作用于整图"勾选项（勾上=忽略 ROI 整幅图转灰度，不勾=只转 ROI 那块，ROI 可手绘也可继承上游结果）。入口是双击流程图里的"灰度"方框（`main.py::on_node_double_clicked`）；参数存在 `node.params` 里，所以同样是"按图片分别记"的。

**关键设计与原理**：
- **删页用"倒着删"**：`for index in range(self.ui.tabWidget.count() - 1, -1, -1)`，只保留 `tabText(index) == "基本参数"` 的那一页，其余 `removeTab(index)`——倒序遍历索引不会错位（模块 docstring 明确写了这点）。运行参数页（直线专用）与显示结果页（结果计数）对灰度无意义。
- **"作用于整图"是父类里特意预埋的控件**：父类 `__init__` 里对 `cb_gray_full_image` 显式 `setVisible(False)`，本类再 `setVisible(True)` 并接 `toggled` 信号——所以这个选项**只出现在灰度窗口**，直线 / 圆窗口看不见它。
- **勾上"作用于整图"是"置灰"而不是"隐藏"ROI 区**：`_on_gray_full_toggled` 把 `roi_params_widget` 和"框选"按钮 `setEnabled(not checked)`，docstring 说这样"免得用户以为它还有用"。
- **重写钩子时先 `super()` 再补自己的参数**：`_load_params` / `_update_params` 都先调父类实现，再单独处理 `gray_full_image`，保证父类那套 ROI / 图像源 / 继承 / 外扩逻辑不用重复写。
- **勾选状态要手动同步一次**：父类 `__init__` 末尾调 `_load_params()` 时信号已经连好了，但 `setChecked()` 在值没变时不会发 `toggled`，所以 `_load_params` 里 `setChecked(checked)` 之后又手动调了一次 `_on_gray_full_toggled(checked)`，保证打开窗口时 ROI 区的灰/亮状态与参数一致。

**类 / 函数清单**：

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class GrayParamsDialog(LineParamsDialog)` | 灰度节点的参数窗口：只留"基本参数"页 + 额外的"作用于整图"开关 | 只重写 `_on_gray_full_toggled` / `_load_params` / `_update_params` 三个钩子，ROI、图像源、执行按钮等全部沿用父类 |
| `GrayParamsDialog.__init__` | 改标题、删掉多余的两页、亮出"作用于整图"、再按参数刷一遍界面 | `super().__init__(...)` 先把界面搭好（注释：它会把"作用于整图"先藏起来）；`setWindowTitle("灰度")`；倒序 `removeTab` 只留"基本参数"；`cb_gray_full_image.setVisible(True)` 并 `toggled.connect(self._on_gray_full_toggled)`；最后 `self._load_params()`（注释：信号已连好，勾选状态会同步到 ROI 区的可用性） |
| `GrayParamsDialog._on_gray_full_toggled` | 勾上"作用于整图"后把 ROI 参数区与"框选"按钮置灰 | `roi_params_widget.setEnabled(not checked)`、`btn_select.setEnabled(not checked)`，两个控件都先判空；用"置灰"而非"隐藏"，避免用户误以为 ROI 还在起作用 |
| `GrayParamsDialog._load_params` | 重写：父类负责常规参数，这里补"作用于整图" | `super()._load_params()` 先灌 ROI / 图像源 / 继承 / 外扩；`node` 存在时读 `bool(node.params.get("gray_full_image", False))`，`setChecked(checked)` 后**再手动调一次 `_on_gray_full_toggled(checked)`**（因为 `setChecked` 同值时不发信号，不手动调 ROI 区就不同步） |
| `GrayParamsDialog._update_params` | 重写：父类负责常规参数，这里补"作用于整图" | `super()._update_params()` 后，`node` 存在时写 `node.params["gray_full_image"] = self.cb_gray_full_image.isChecked()` |
| 模块级 `if __name__ == '__main__':`（测试入口，非函数） | 独立测试入口：不启动主程序，单独看灰度窗口 | 建 `QApplication`；读 `image/lena.png`，失败则 `from Detector import make_test_image`（注释：和 `Detector.make_test_image` 一致）；造 mock 后 `GrayParamsDialog(...)`，`resize(390, 560)` 并 `show()` |
| `class MockMainWindow`（`__main__` 内） | 测试用假主窗口 | 比另两个文件多给了 `flow_nodes = []` 与 `flow_edges = []`（灰度窗口继承父类的 `_candidate_sources` 会读 `flow_edges`，给了空表就不用 `getattr` 兜底） |
| `MockMainWindow.__init__` | 存测试图并补齐对话框会读的属性 | `current_static_image`、`cap = None`、`video_processing_mode = "continuous"`、`video_step_node = None`、`flow_nodes = []`、`flow_edges = []` |
| `MockMainWindow.update_frame` | 占位：模拟刷新视频帧 | `@staticmethod`，只打印一行 |
| `MockMainWindow._display_image` | 占位：模拟显示图片 | `@staticmethod`，打印 `img.shape` |
| `MockMainWindow._execute_static` | 占位：模拟静态执行入口 | `@staticmethod`，把节点名存进局部变量 `_name` 后打印 mode 与节点名，返回 `[]` |
| `MockMainWindow._update_execution_log` | 占位：模拟刷新执行日志 | `@staticmethod`，打印 `len(exec_info)` |
| `class MockNode`（`__main__` 内） | 测试用假节点，带一套预置 ROI 参数 | `params = {"roi_x":0, "roi_y":0, "roi_w":512, "roi_h":512}`、`name = "灰度"`（名字对得上，所以走的是灰度窗口自己的逻辑） |
| `MockNode.__init__` | 造一个带预置 ROI 参数的灰度假节点 | 直接赋 `params` 与 `name` |

---

> **本章属于**：⑤ 流程图画布（节点 / 连线 / 拖放 / 删除）

## FlowChart.py


**文件作用**：定义节点式流程图的"画布层"——节点方框（NodeItem）、贝塞尔连线（EdgeItem）、支持拖放与手工连线的视图（FlowchartView），以及一个只用于单独调试本文件的测试窗口（FlowChartWindow）。它被 main.py 导入（`from FlowChart import NodeItem, EdgeItem, FlowchartView`）：节点和连线由主窗口控制器（main.py 的 MainWindow）在拖拽落点、双击树控件、加载方案时创建，然后加进"每一页自己的" `flow_scene`（画布归属由 FlowPages.FlowPageManager 的 `view_factory` 为每页新建的 FlowchartView 提供）。文件末尾的 `FlowChartWindow` 与 `main()` 不参与正式程序，只在直接运行本文件时用来试画布。

**关键设计与原理**：
- **节点方框与端口的画法**：方框是固定尺寸的 `QGraphicsRectItem(0, 0, 140, 50)`，填充 `QColor(250,250,250)`、深蓝 2px 边框；`paint()` 里先让基类画背景边框，再 `drawText(rect(), Qt.AlignCenter, name)` 居中写名字，最后用 `drawEllipse` 在**本地坐标** `in_port=(70,0)`（上边中点，红点）和 `out_port=(70,50)`（下边中点，蓝点）画两个半径 4 的圆点。注释里还留着"右侧端口 out_port_1"和"黄点"的代码，已被注释掉、不生效。
- **端口命中判定用曼哈顿距离而不是 `itemAt()`**：视图在 `mousePressEvent` / `mouseReleaseEvent` 里遍历 `main_window.flow_nodes`，用 `node.mapFromScene(scene_pos)` 转成本地坐标后算 `(local_pos - 端口).manhattanLength() < 30`。注释说明原因：`self.itemAt(event.pos())` 只能判断是否点进方框内部，点"方框外部的半截蓝点"会失灵。
- **连线跟随靠自定义信号**：`NodeItem` 混入 `QObject` 并声明 `positionChanged = Signal()`（代码注释原话："自定义信号，解决线没有跟着方框一起动的问题"），在 `mouseMoveEvent` / `mouseReleaseEvent` 里先调基类完成位移、再 `emit()`。主窗口把它接到刷新所有连线的槽上，于是拖动方框时曲线实时重算。注意：`QObject` 写在基类列表的第一位，且两个基类的 `__init__` 必须分别显式调用。
- **连线是三次贝塞尔曲线，且只存节点引用不存坐标**：`EdgeItem` 保存 `start_node` / `end_node`，`update_path()` 每次都重新取 `get_output_pos()` / `get_input_pos()`（即 `mapToScene(端口)` 得到的场景坐标），用 `QPainterPath.moveTo(start)` + `cubicTo(ctrl1, ctrl2, end)` 生成 S 型平滑曲线；控制点用"点在上下两条边上"的写法：`dy = abs(end.y()-start.y())`，`ctrl1=(start.x, start.y+dy*0.5)`、`ctrl2=(end.x, end.y-dy*0.5)`（乘 0.5 是为了曲线平滑）。代码里保留了"点在左右两条边上"的版本（沿 X 偏移 dx），未启用。
- **场景属性必须叫 `flow_scene`，不能叫 `self.scene`**：`QGraphicsView` 自带 `scene()` 方法，用同名属性会把它遮蔽掉，Python 侧就再也调不到 `scene()`（而 NodeItem / EdgeItem 找视图、找主窗口全靠 `self.scene()`）。代码注释明确写了这一条。
- **拖放要同时重写 `dragEnterEvent` 和 `dragMoveEvent`**：视图设了 `ScrollHandDrag`，注释说明不写 `dragMoveEvent` 的话 `dropEvent` 永远不会触发；而 `dropEvent` 里取模块名做了 4 层兜底（当前项 → tree 的选中项 → 拖拽源 QTreeWidget 的选中项 → MIME 文本），注释说是为了不受 Windows 环境和 PySide2 版本影响。连线交互则是"起点 `_start_node` + 灰色虚线 `_temp_line`"的状态机：点蓝点开始拉线并把拖拽模式切成 `NoDrag`，松手时落在红点范围内才成线，失败或点空白都走 `_cancel_connection()` 删虚线与恢复 `ScrollHandDrag`。

**类 / 函数清单**：

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class NodeItem` | 流程图上的一个节点方框：可拖动、可选中、可右键删除、可双击打开配置 | 多重继承 `QObject` 与 `QGraphicsRectItem`——前者提供自定义信号，后者提供矩形图元与鼠标事件；构造时分别显式初始化两个基类，方框尺寸固定 140×50。 |
| `NodeItem.__init__` | 建节点：名字、位置、参数表、颜色边框、交互标志位、两个端口坐标 | `QGraphicsRectItem.__init__(self, 0, 0, 140, 50)` 建方块（x,y 为左上角）；`self.params = {}` 存该节点的参数配置；`setBrush(QBrush(QColor(250,250,250)))` 填充、`setPen(QPen(QColor("darkblue"), 2))` 深蓝 2px 边框；`setFlags(ItemIsMovable ／ ItemIsSelectable)` 允许鼠标拖拽与选中；`setAcceptHoverEvents(True)` 允许悬停；`setPos(pos)` 就位；端口按 140×50 的尺寸取 `in_port=(70,0)`、`out_port=(70,50)`。 |
| `NodeItem.mouseMoveEvent` | 拖拽过程中实时告诉外界"位置变了" | 先 `super().mouseMoveEvent(event)` 让底层真正把方块拖过去，再 `self.positionChanged.emit()`——顺序很关键，先移动后发信号，接收方才能拿到新坐标。 |
| `NodeItem.mouseReleaseEvent` | 松开鼠标时补发一次位置变化 | 同样先调基类（更新最后一次位置）再 `emit()`，用于拖拽结束后把连线对齐到最终位置。 |
| `NodeItem.mouseDoubleClickEvent` | 双击节点时把事件交给主窗口（打开参数配置） | 用 `self.scene()` 判存在、`self.scene().views()[0]` 取第一个视图，检查视图有 `main_window` 属性后调用 `view.main_window.on_node_double_clicked(self)`；最后 `super()` 继续传递事件。（docstring 没写主窗口具体做什么，按 main.py 的 `on_node_double_clicked` 推断是弹该节点的参数窗口。） |
| `NodeItem._make_context_menu` | 组装右键菜单，返回 `(menu, 菜单项字典)` | 只放一个 `QAction("删除节点")`；docstring 说明灰度的"作用于整图"已经挪到节点自己的参数窗口里了，所以菜单只剩这一项；单独抽成函数是为了能自动化测试（不必真的弹菜单等用户点）。 |
| `NodeItem.contextMenuEvent` | 右键节点弹菜单，选"删除节点"就交给主窗口删 | `menu.exec_(event.screenPos())` 在鼠标屏幕位置弹出并阻塞等待；返回 `None`（点了菜单外）直接 return；命中删除项时同样用 `self.scene().views()[0]` 找视图，调 `view.main_window.delete_flow_node(self)`——真正的删除（连带删线、改列表）不在本文件，交给调用方。 |
| `NodeItem.paint` | 描述节点的样子：方框、居中名字、红/蓝两个端口点 | 先 `super().paint(painter, option, widget)` 把 init 里设的背景色和边框画出来，再 `painter.drawText(super().rect(), Qt.AlignCenter, self.name)` 居中写字；然后 `setBrush(Qt.red)` + `drawEllipse(self.in_port, 4, 4)` 画输入红点，`setBrush(Qt.blue)` + `drawEllipse(self.out_port, 4, 4)` 画输出蓝点（宽高 4、圆心为端口）；下面画黄点的代码被注释掉了。 |
| `NodeItem.get_input_pos` | 返回输入端口在画布（场景）里的绝对坐标，即连线终点 | `self.mapToScene(self.in_port)`：把节点自身的本地坐标转成整个流程图的场景坐标。docstring 说明这使"方框 + 输入输出圆点合成一个控件一起移动"，也让从左侧树拖到 view 时"拖到哪里方框就在哪里创建"。 |
| `NodeItem.get_output_pos` | 返回输出端口在场景里的绝对坐标，即连线起点 | `self.mapToScene(self.out_port)`；EdgeItem 用它当曲线起点。 |
| `class EdgeItem` | 两个节点之间的连线（S 型平滑贝塞尔曲线），可右键删除 | 继承 `QGraphicsPathItem`（自带路径与画笔）；保存的是首尾**节点对象**而不是坐标，因此可以随时按节点最新位置重算路径。 |
| `EdgeItem.__init__` | 记下首尾节点、生成初始路径、设定画笔 | 存 `self.start_node` / `self.end_node` 后立即 `update_path()` 出曲线，再 `setPen(QPen(QColor("darkGray"), 2))`（深灰、线宽 2）。 |
| `EdgeItem.update_path` | 按两个节点当前的端口位置重算曲线 | 实时取 `start = start_node.get_output_pos()`、`end = end_node.get_input_pos()`；建 `QPainterPath()`，`moveTo(start)` 后 `cubicTo(ctrl1, ctrl2, end)`——三次贝塞尔需要两个控制点；控制点用上下边版本：`dy = abs(end.y()-start.y())`，`ctrl1=(start.x(), start.y()+dy*0.5)`、`ctrl2=(end.x(), end.y()-dy*0.5)`（注释：×0.5 使曲线平滑，不乘也行）；最后 `setPath(path)` 挂到对象上。左右边版本（`dx` 沿 X 偏移）保留在注释里未启用。 |
| `EdgeItem.update_positions` | 对外的"刷新位置"统一入口 | 直接调用 `self.update_path()`；主窗口刷新所有连线时就是逐条调它。 |
| `EdgeItem.contextMenuEvent` | 右键连线弹"删除连线"菜单并执行删除 | 现场建 `QMenu` 和 `QAction("删除连线")`，`menu.exec_(event.screenPos())` 等待选择；命中后经 `self.scene().views()[0].main_window.delete_edge(self)` 交给主窗口执行删除。 |
| `class FlowchartView` | 一页流程图的自定义画布视图：接收从树控件的拖放、自己处理连线交互、把选中变化上报 | 继承 `QGraphicsView`；内部持有一个属于自己的 `flow_scene`，并把主窗口控制器存进 `self.main_window` 作为回调出口。docstring：自定义流程图视图（支持拖放）。 |
| `FlowchartView.__init__` | 建画布、开启拖放、设拖拽模式、接上选中变化信号 | `self.main_window = main_window`；`setAcceptDrops(True)` 允许画布内拖拽；`setDragMode(QGraphicsView.ScrollHandDrag)` 设定空白处按住左键拖动时的行为；`self.flow_scene = QGraphicsScene()` 再 `setScene(self.flow_scene)`；**代码注释明确说明这个属性不能叫 `self.scene`**，否则会遮蔽 `QGraphicsView.scene()` 方法；`self._start_node = None`（起点）/ `self._temp_line = None`（灰线）为连线状态；`flow_scene.selectionChanged.connect(self.on_selection_changed)` 用来在 main.ui 中显示当前选中的节点。 |
| `FlowchartView.dragEnterEvent` | 判断拖过来的东西画布是否接受 | `event.mimeData().hasText()` 为真、或者 `event.source()` 是 `QTreeWidget`，就 `event.acceptProposedAction()`；其他来源不处理。 |
| `FlowchartView.dragMoveEvent` | 让拖拽过程持续被接受，否则放不下 | 直接 `event.acceptProposedAction()`。docstring 强调必须加：不然因为 `ScrollHandDrag` 的干扰，`dropEvent` 永远不会触发，左侧树就拖不到右侧画布。 |
| `FlowchartView.dropEvent` | 在松开鼠标处创建节点：从树控件取出模块名并换算场景坐标 | 用 4 层兜底取名字：① `main_window.tree.currentItem()` 的 `text(0)`；② 仍为空则 `main_window.tree.selectedItems()[0]`；③ 仍为空且 `event.source()` 是 `QTreeWidget`，取其 `selectedItems()`；④ 最后才用 `event.mimeData().text()`（注释说明这套兜底比原来单个 if 更鲁棒，不受 Windows 环境和 PySide2 版本影响）。拿到文字且 `main_window` 存在时 `pos = self.mapToScene(event.pos())` 并调 `main_window.add_flow_node(text, pos)`，然后 `acceptProposedAction()`；否则 `event.ignore()`。 |
| `FlowchartView.mousePressEvent` | 左键按下时判断点到了蓝点／红点／节点空白／背景，由此开始或结束连线 | 只有 `Qt.LeftButton` 才进逻辑：先 `mapToScene(event.pos())` 得场景坐标，再遍历 `main_window.flow_nodes`（先 `hasattr` 检查），对每个 `NodeItem` 用 `node.mapFromScene(scene_pos)` 转本地坐标，先查 `(local_pos - node.out_port).manhattanLength() < 30` 判蓝点（输出）、再查 `in_port` 判红点（输入），命中就 break 并记下 `clicked_node` / `clicked_port_type`。点到蓝点 → `setDragMode(NoDrag)` 禁掉平移 + `_start_connection(node)` 拉出跟随鼠标的虚线，`event.accept()` 后返回；点到红点且已有起点 → `_try_finish_edge(...)` 完成连线。都没命中时再看 `self.itemAt(event.pos())`：是 `NodeItem` 就交 `super()`（能正常拖动方框）；点在空白背景且正在拉线 → `_cancel_connection()` 取消。 |
| `FlowchartView.mouseMoveEvent` | 拉线状态下让灰虚线实时跟着鼠标，其他情况交给基类 | 有 `_start_node` 时：`mapToScene(event.pos())` 取鼠标场景坐标，取出 `self._temp_line.line()`，只 `line.setP2(pos)` 改终点（起点是引出的那个蓝点），再 `setLine(line)` 刷新画面后返回；否则 `super().mouseMoveEvent(event)`，实现拖方框或拖背景。 |
| `FlowchartView.mouseReleaseEvent` | 松手时判断落点是否在红点上：在就成线，不在就放弃 | 左键且 `_start_node` 非空时，同样遍历 `flow_nodes` 用 `mapFromScene` + `manhattanLength() < 30` 找落在哪个 `in_port` 上；找到就 `_try_finish_edge(self._start_node, target_node, event)`；没找到就 `_cancel_connection()` 取消虚线并 `event.accept()`；其余交 `super()`。 |
| `FlowchartView._start_connection` | 记录连线起点，并生成一条初始的灰色虚线 | 先 `_cancel_connection()` 清掉可能残留的状态（上一次没成功的虚线），再 `self._start_node = node`，取 `node.get_output_pos()`；用 `flow_scene.addLine(x, y, x, y, QPen(Qt.gray, 2, Qt.DashLine))` 建一条首尾重合的灰色虚线（返回的 QGraphicsLineItem 存进 `_temp_line`），之后由 mouseMoveEvent 拖出长度。 |
| `FlowchartView._try_finish_edge` | 把虚线变实线，并把连线状态清理干净 | 只有 `start_node` 非空且 `start_node != end_node`（不允许自己连自己）才调 `self.main_window.add_edge(start_node, end_node)` 创建真正的曲线；之后一定 `_cancel_connection()` 删掉虚线；若传了 `event` 就 `event.accept()`（已完成，不再通知父类）。 |
| `FlowchartView._cancel_connection` | 把连线状态彻底清空，回到"没有拉线"的初始状态 | 有 `_temp_line` 就 `flow_scene.removeItem(self._temp_line)` 并置 `None`；`self._start_node = None`；`setDragMode(QGraphicsView.ScrollHandDrag)` 恢复"拖动背景平移画布"的功能。 |
| `FlowchartView.on_selection_changed` | 画布中选中项变化时，把当前选中的节点上报主窗口 | `self.flow_scene.selectedItems()` 包在 `try` 里捕获 `RuntimeError`（关窗口时底层对象已销毁会抛），异常就忽略本次信号返回；有选中项时取第一个，并 `isinstance(node, NodeItem)` 确认选的是节点而不是连线，才调 `main_window.on_node_selected(node)`；没有选中项则上报 `None` 以取消选中状态（同样先 `hasattr` 检查 `main_window`）。 |
| `class FlowChartWindow` | 直接运行本文件时的测试窗口：左边模块树、右边画布，自带一份最简的节点/连线管理 | 不属于正式程序；相当于"主窗口控制器"的极简版，把 NodeItem / EdgeItem / FlowchartView 需要的回调（add_flow_node、add_edge、delete_flow_node、on_node_selected、on_node_double_clicked）实现了一遍。 |
| `FlowChartWindow.__init__` | 搭测试界面：左树右画布、分割器、状态栏、拖拽使能、信号绑定 | 建 `QTreeWidget`：表头"检测模块"、`setDragEnabled(True)`、`setDefaultDropAction(Qt.CopyAction)`（拖拽是复制而不是剪切），根节点"图像处理"下挂"直线""圆"，`expandAll()` 默认全展开；状态栏初值"当前选中节点：无"；`self.flow_nodes = []` / `self.flow_edges = []` 两个列表分别存方框和连线；`self.view = FlowchartView(main_window=self)`，并 `setViewportUpdateMode(QGraphicsView.FullViewportUpdate)` 防拖尾残影、`setAcceptDrops(True)`；`QSplitter(Qt.Horizontal)` 左加 tree 右加 view，`setStretchFactor(1, 1)` 后 `setCentralWidget`；最后把 `tree.itemDoubleClicked` 接到 `_on_tree_double_click`。 |
| `FlowChartWindow.add_flow_node` | 建一个节点、加进画布、接上"移动就刷新连线"的信号并登记 | 未写 docstring（只有注释"添加节点时，绑定信号并更新连线逻辑"），按代码与调用点推断：`NodeItem(name, pos)` → `view.flow_scene.addItem(node)` → `node.positionChanged.connect(self.update_all_edges)` → `flow_nodes.append(node)` → 返回 node；中间那段"自动把上一个节点连到新节点"的代码被整段注释掉了，所以新建节点不会自动连线，末尾的 `QTimer.singleShot(0, self.update_all_edges)` 也被注释掉。 |
| `FlowChartWindow.add_edge` | 从输出端口生成一条到输入端口的新曲线（带重复检查） | 先遍历 `flow_edges`，若已存在 `start_node` 和 `end_node` 都相同的连线就直接 return（注释：防止重连）；否则 `EdgeItem(start_node, end_node)` → `view.flow_scene.addItem(edge)` → `flow_edges.append(edge)` → `update_all_edges()` 刷一次画面。 |
| `FlowChartWindow.delete_flow_node` | 删除节点，并连带删掉所有连在它身上的曲线 | 节点不在 `flow_nodes` 里就返回（先检测是否存在）；第一轮遍历 `flow_edges`，把 `start_node` 或 `end_node` 等于待删节点的边收进 `edges_to_remove`，再逐条 `removeItem` 并 `flow_edges.remove`；然后 `removeItem(node_to_delete)` 把方块从画布抹去、`flow_nodes.remove` 清记录，最后 `update_all_edges()` 刷新。 |
| `FlowChartWindow._on_tree_double_click` | 双击树里的具体模块，就在画布上按顺序新建一个方框 | docstring 说是照着 main.py 的同名函数改的。用 `self.tree.currentIndex()` 取当前索引：无效就返回；`index.parent()` 无效（点到的是一级分类）也返回；名字取 `index.data(0)`，为空返回。位置计算：已有节点则沿用最后一个节点的 x、y 再 +180（纵向往下排），没有节点则用 `(20, 20)`；最后 `self.add_flow_node(name, QPointF(new_x, new_y))`。 |
| `FlowChartWindow.update_all_edges` | 刷新所有连线的路径，使移动方框后曲线跟着移动 | 遍历 `self.flow_edges`，对每条连线调 `edge.update_positions()`（内部重算贝塞尔路径）。 |
| `FlowChartWindow.delete_edge` | 删除一条连接曲线 | 连线不在 `flow_edges` 里就返回；否则 `view.flow_scene.removeItem(edge_to_delete)` 从画布删除、`flow_edges.remove` 从列表删除，最后 `update_all_edges()` 刷新。 |
| `FlowChartWindow.on_node_double_clicked` | 测试窗口的双击方框回调：只在控制台打印节点名 | `print(f"FlowChartWindow 双击了方框: {node.name}")`，替代正式程序里"弹出该节点参数窗口"的行为。 |
| `FlowChartWindow.on_node_selected` | 单击节点时更新状态栏文字 | 有节点就 `statusBar().showMessage(f"当前选中节点：{node.name}")`，为 `None` 则显示"当前选中节点：无"。 |
| `def main()` | 直接运行 FlowChart.py 时的程序入口：起 Qt 应用、显示测试窗口 | 函数内 `import sys`；`app = QApplication(sys.argv)` → `window = FlowChartWindow()` → `window.show()` → `sys.exit(app.exec_())`。 |

---

> **本章属于**：⑤ 多页签管理

## FlowPages.py


**文件作用**：把 main.ui 里的 `flowWidget`（QTabWidget）改造成"浏览器式"多标签流程图页面管理器。每一页有自己独立的一份东西——一个 `FlowchartView`（自带 QGraphicsScene）、这一页的方框列表、连线列表、底部"当前选中的节点"提示 label，所以各页流程图内容互不干扰。它由 main.py 的 `MainWindow` 实例化（传入控件、`view_factory=lambda parent: FlowchartView(parent, main_window=self)`、`on_page_switched`、`on_page_close_requested`）后调用 `setup()`。文件只负责"页面"本身（标签页、每页画布与方框/连线表），不碰检测、参数、图像；换页之后该做的事（切换当前节点表、换参数、刷新画面）全部通过回调交给调用方。

**关键设计与原理**：
- **每页一条记录（page dict）**：字段为 `key / widget / view / label / nodes / edges / selected_node / dirty / project_path`。`key` 是自己递增的整数标识，并且在登记时**写进标签的 `tabData`**（`tabBar().setTabData(index, page["key"])`）；`_page_at(index)` 是"读 tabData → 从 `_pages_by_key` 查记录"，所以用户拖动标签换了顺序之后依然能认对页，不会串页（`self.pages` 只用来保持与标签栏一致的顺序和判断"还剩几页"）。
- **"+"是一个"装饰标签"，不是流程图页面**：它本身就是标签栏里的一个标签（`addTab(QWidget(), "")`，标题留空），靠 `tabBar().setTabButton(index, QTabBar.RightSide, QToolButton("+"))` 把本该放 × 的位置换成自己的按钮——所以这个标签上不会出现关闭按钮，位置和间距全由标签栏算，不用手写坐标。它的 tabData 里没有页面标识，`_page_at()` 找不到它，于是双击改名、删除页面、右键菜单都会自动跳过它；新页面一律用 `_add_tab_index()` 插在它前面，一旦它被拖走，`_on_tab_moved` 会用 `QTimer.singleShot(0, self._ensure_add_tab_last)` 把它移回最后（注释：用单次定时器，避免在信号里再改序造成递归）。
- **多页签增删改与 `currentChanged` 的时序**：`setup()` 里前 5 步都做完（登记第一页、装右键菜单、设可关闭、设可拖动、建"+"标签），**第 6 步才** `currentChanged.connect(self._on_tab_changed)`（未注释，按调用点推断：先让页面和各种监听就绪，再接换页信号）。`add_page()` 的顺序是 `insertTab` → `_register_page`（此时才补写 tabData）→ `setCurrentIndex(index)`，靠 `currentChanged` 走进 `_on_tab_changed` 通知调用方；`append_pages()` 则故意**不切页、不触发回调**，留给"打开方案"的调用方自己决定切哪页。`_remove_page()` 删的若是当前页，**先 `setCurrentIndex(其它页)`**（避免把正在使用的画布删掉），再清 scene、移除标签与数据记录，最后 `_resync_current_page()` 兜底纠正 `current_page` 与标签栏下标的不一致。
- **`switching` 保护标志的作用**：清空一页的 scene 会让它发出 `selectionChanged`，删页期间会误伤"当前页"的选中状态。所以 `_remove_page()` 在清画面/移列表/`removeTab` 这几步外面套 `self.switching = True` … `finally: False`；`_on_tab_changed` 开头直接 return，调用方（main.py 的 `on_node_selected`）也会先读 `mgr.switching` 来决定忽略这次信号，避免被删页面的信号把选中状态和底部提示清掉、也不会下标错位。
- **关闭页面时的"未保存"回调**：页记录带 `dirty` 位，对外有 `mark_dirty` / `clear_dirty` / `mark_all_clean` / `has_dirty_pages` 四个接口（main.py 在增删节点、删连线、改参数、改页面名等处调用 `mark_dirty`）。`_remove_page()` 在真正动手之前先调 `on_page_close_requested(page)`，返回 `False` 表示"别关这一页"，管理器就原样返回、什么都不动——main.py 的 `_confirm_close_flow_page` 在这里检查 `page.get("dirty")` 并弹"保存／不保存／取消"，点"保存"时还会先把要关的那一页切成当前页再调 `save_project()`（因为方案文件是"一个文件一页"）。
- **就地改名不弹窗口**：QTabBar 没有双击信号，所以对 tabBar 装 `installEventFilter(self)`，在 `eventFilter` 里接 `MouseButtonDblClick`。改名用一个 `QLineEdit(tab_bar)` 直接 `setGeometry(tab_bar.tabRect(index))` 盖在标签原位置上（父控件设成 tabBar，坐标才一致），回车/失焦由 `editingFinished` 保存，Esc 由事件过滤器取消；`_close_title_editor()` 先把 `_title_editor` 引用清空再 `hide()/deleteLater()`，防止收尾动作再次触发 `editingFinished` 而重复处理。
- **"页面内容指纹去重"不在本文件**：本文件只提供 `page_key()`（当前页标识）给"每页 × 每图"这类结果缓存当键（main.py 把它和图片键、模式拼在一起）。真正的"按内容判重"是 main.py 的 `_page_fingerprint()` / `_model_page_fingerprint()`（标题 + 每个节点的名字/坐标/图像源绑定/参数 + 连线关系算指纹），用来判断方案文件里的某一页在工作区里是否已经存在。
- **到处 try/except RuntimeError**：窗口关闭时底层 C++ 对象已销毁，再去访问会抛 `RuntimeError`。`_ensure_add_tab_last`、`eventFilter`、`_close_title_editor`、`_on_tab_moved`、`_on_tab_changed` 等都捕获它并安静放行（注释：避免往终端打印 Traceback）；`tab_widget.destroyed` 连到 `_on_tab_widget_destroyed`，把 `tab_widget`、`current_page`、`add_button`、`add_tab_widget`、标题编辑框等引用全部清空，之后事件一律忽略。

**类 / 函数清单**：

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class FlowPageManager` | 多页面管理器：管标签页、每页画布与方框/连线表，以及标签的增删改、拖序、关闭；换页时回调调用方 | 继承 `QObject`（需要事件过滤器、父对象与槽）；页面数据放在 `self.pages`（列表，顺序与标签栏一致）与 `self._pages_by_key`（标识 → 记录，拖动换序后靠它认页）；docstring 明确职责边界：只管"页面"，不碰检测、参数、图像。 |
| `FlowPageManager.__init__` | 存下控件与三个回调，初始化页面列表和一堆状态字段 | 保存 `tab_widget` / `view_factory` / `on_page_switched` / `on_page_close_requested`；`pages=[]`、`_pages_by_key={}`、`current_page=None`、`switching=False`（注释：换页/删页过程中的保护标志，**调用方也会读它**）、`_seq=0`（页面标识计数器 flow1/flow2…）、`_title_editor=None`、`_title_editor_index=None`（就地改名的输入框及它在改第几页）、`add_button=None`、`add_tab_widget=None`（在 `setup()` 里创建）。docstring 记明 `on_page_close_requested(page) -> bool`：返回 False 表示"别关这一页"，有未保存改动时调用方可以在这里弹"是否保存"。 |
| `FlowPageManager.setup` | 接管 flowWidget：登记第一页，装上"+"新建／右键菜单／双击改名／× 关闭／拖动换序，返回第一页记录 | ① `tab_widget.widget(0)` 为第一页，用 `_make_view(first_widget)` 把它里面的 `flowView` 换成自定义画布，`findChild(QLabel, "lbl_current_node")` 找底部提示 label，`_register_page(...)` 登记并设为 `current_page`；② tabBar 设 `Qt.CustomContextMenu` 并接 `_on_tab_context_menu`、设 ToolTip（说明 + 标签新建／右键／双击／拖动等操作）、`installEventFilter(self)` 接双击、`tab_widget.destroyed` 接 `_on_tab_widget_destroyed`（先清引用，避免之后再去访问已销毁的 C++ 对象而报 RuntimeError）；③ `setTabsClosable(True)` + `tabCloseRequested` → `_on_tab_close_requested`（标签右边显示 ×，与右键菜单的"删除页面"两个入口都保留）；④ `setMovable(True)` + `tabBar().tabMoved` → `_on_tab_moved`；⑤ `_create_add_tab()` 建最后的"+"标签；⑥ 最后才 `currentChanged` → `_on_tab_changed`（未注释，按调用点推断：先让第一页与各监听就绪再接换页信号）。 |
| `FlowPageManager._create_add_tab` | 在最后面建一个独立的"+"标签，并返回它的下标 | `addTab(QWidget(), "")`（标签文字留空，只放按钮）；建 `QToolButton("+")`：`setAutoRaise(True)` 扁平样式、`setCursor(Qt.PointingHandCursor)`、`setFixedSize(16, 22)` 让它看起来像个小标签、`clicked` 接 `add_page`；`tab_bar.setTabButton(index, QTabBar.RightSide, self.add_button)` 把标签右侧本该放 × 的位置交给这个按钮；`setTabToolTip(index, "新建页面")`。docstring 强调它不是流程图页面：标签的 tabData 里没有它的标识，`_page_at()` 找不到它，所以双击改名、删除页面都会自动跳过；它的"×"位置被换成了自己的按钮，所以这个标签上不会出现关闭按钮。 |
| `FlowPageManager._add_tab_index` | 返回"+"那个装饰标签的下标（新页面都插在它前面） | `add_tab_widget` 为 `None` 时直接返回 `tab_widget.count()`；否则 `indexOf(self.add_tab_widget)`，结果 `< 0`（找不到）时也退化成 `count()`，保证"+"永远在最后。 |
| `FlowPageManager._ensure_add_tab_last` | 保证"+"标签永远待在最后：被拖到别处时把它移回最后 | 整体包 `try/except RuntimeError`（控件已销毁就忽略）。`add_tab_widget` 或 `tab_widget` 为 `None` 直接返回；`indexOf` 为负也返回；否则比较 `index` 与 `count()-1`，不等就 `tabBar().moveTab(index, last)`，并顺手 `_resync_current_page()`——注释说明拖动"+"标签没有意义（它不是页面），当前页可能被带偏，要同步回来。 |
| `FlowPageManager.page_key` | 返回当前页的标识，用来给"每页 × 每图"这类缓存做键 | `self.current_page["key"] if self.current_page is not None else None`。 |
| `FlowPageManager.add_page` | 添加一页流程图并自动切换到新页面，返回新页记录 | 建 `QWidget` + `QVBoxLayout`，加 `self._create_view(page_widget)` 得到的画布和一个 `QLabel("未选中节点")`（与第一页保持一致）；标题用 `self._unique_title("Flow{0}".format(self._seq + 1))`（注释：用页面标识编号，再用 `_unique_title` 挡一下用户手动改过名字造成的重名）；`insertTab(self._add_tab_index(), page_widget, title)` 插在"+"前面；`_register_page` 登记；最后 `setCurrentIndex(index)` 切过去，触发 `currentChanged → _on_tab_changed → 通知调用方`。 |
| `FlowPageManager.append_pages` | "打开方案"专用：在最后追加 N 页，已有页面（画布、方框、连线、状态）原样保留 | 遍历 `titles or []`，每页同样建 `QWidget` + `QVBoxLayout` + `QLabel("未选中节点")` + `_create_view(page_widget)`；`insertTab(self._add_tab_index(), page_widget, self._unique_title(str(title)))`（标题重名时自动加 (2)(3)…，避免出现两个一模一样的标签）；`_register_page` 记入并收进 `new_pages`。与 `add_page()` 的区别是**不切换当前页、不触发换页回调**，建完由调用方决定切到哪一页；结尾 `_ensure_add_tab_last()` 兜一下"+"的位置；返回新页面记录列表（顺序与 titles 一致）。 |
| `FlowPageManager.delete_page` | 右键菜单"删除页面"：先弹确认框，确认后再删；成功返回 True | `index` 默认当前页；`len(self.pages) <= 1` 时弹 `QMessageBox.information`"至少要保留一个流程图页面。"并返回 False（注释提醒：标签栏里还有一个"+"装饰标签，所以判断"只剩一页"必须用 `len(self.pages)` 而不能用 `count()`）；`_page_at(index)` 为 `None`（点的是"+"标签或空白）也返回 False；然后用 `QMessageBox.question`（`Yes ／ No`，默认 `No`）确认"该页面里的方框和连线都会一起删除"，不是 Yes 就返回 False；最后交给 `_remove_page(index)`。 |
| `FlowPageManager.close_page` | 关闭某一页（点标签右边的 × 时调用），成功返回 True | `index` 默认当前页；只剩一页时同样提示并返回 False；否则直接 `_remove_page(index)`。docstring 说明为了像浏览器那样干脆**不再弹确认框**，右键菜单里的"删除页面"仍然会先确认，两个入口随便用哪个都行。 |
| `FlowPageManager._on_tab_close_requested` | 点了标签上的 × 时的槽：关掉这一页 | 直接转发 `self.close_page(index)`（`QTabWidget.tabCloseRequested` 会带上被关页的下标）。 |
| `FlowPageManager._remove_page` | 真正删掉某一页：先给调用方"未保存"回调 → 把当前页切走 → 清画面 → 移除标签和数据记录 → 销毁页面控件 | ① `_page_at(index)` 取记录，`None` 直接返回 False。② 若 `on_page_close_requested` 存在就调用它，返回 False（取消关闭）就原样返回、什么都不动。③ 若删的正好是当前页，先 `setCurrentIndex(0 if index != 0 else 1)` 切到别的页——注释：避免把正在使用的画布删掉，而且这样会正常触发换页、调用方的引用会跟着切过去。④ `self.switching = True` 后（`try/finally` 复位）：`deleted_page["view"].flow_scene.clear()` 清掉这一页的方框和连线、`nodes`/`edges` 置空、从 `self.pages` 移除、`_pages_by_key.pop(key, None)`、`tab_widget.removeTab(index)`；注释说明清空 scene 会发 `selectionChanged` 信号，所以这一段把 `switching` 置上让调用方忽略这次信号。⑤ `removeTab` 不会删除页面控件，所以手动 `widget.setParent(None)` + `widget.deleteLater()`（view / label 都是它的子控件）。⑥ `_resync_current_page()` 兜底（万一 Qt 的下标变化没走到回调），返回 True。 |
| `FlowPageManager._on_tab_moved` | 用户拖动标签换序：同步 `self.pages` 的顺序，并保证"+"标签仍在最后 | 先处理"+"：若 `indexOf(add_tab_widget) != count()-1`，就 `QTimer.singleShot(0, self._ensure_add_tab_last)`（注释：用单次定时器，避免在信号里再改序造成递归），这段包 `try/except RuntimeError` 直接返回。然后只有 `from_index` 和 `to_index` 都落在 `self.pages` 范围内（即"页面和页面之间"换序，动"+"标签本来就没有页面记录）才 `pages.pop(from_index)` + `pages.insert(to_index, page)`。docstring 还说明：真正"按标签找页面"用的是 `_page_at()`（读标签里存的标识），所以即使 Qt 先发 `currentChanged`、后发 `tabMoved`，也不会把页面认错。 |
| `FlowPageManager.rename_page` | 就地重命名某一页（双击标签或右键菜单进来）：标签原位出现小输入框 | `index` 默认当前页；`index < 0` 或 `>= count()` 返回 False；`_page_at(index)` 为 `None`（是"+"装饰标签，不是真正的页面）也返回 False；若已有名字在改，先 `_close_title_editor(commit=True)` 收掉（相当于回车保存）；`tab_bar.tabRect(index)` 为空返回 False。然后建 `QLineEdit(tab_bar)`（父控件设成标签栏，坐标才和标签一致），`setText(tab_bar.tabText(index))` 预填当前名字、`selectAll()` 全选（直接打字就能替换）、`setGeometry(rect.adjusted(2, 2, -2, -2))` 留 2 像素边不完全盖住标签、`show()` + `setFocus()`、`installEventFilter(self)`（用来接 Esc）；`editingFinished` 接 `_on_title_editor_finished`（用 lambda 把当前 editor 绑进去）；记下 `self._title_editor` 与 `self._title_editor_index`，返回 True。 |
| `FlowPageManager._on_title_editor_finished` | 就地改名输入框的回调：回车或失去焦点时把名字写回去 | 如果传进来的 `editor` 不是当前的 `self._title_editor`，说明是别的（已被收掉的）输入框发出的信号，直接忽略；否则调 `_close_title_editor(commit=True)` 保存。 |
| `FlowPageManager._close_title_editor` | 收掉就地改名的小输入框：`commit=True` 保存新名字，`False` 取消（保持原名） | `editor is None` 直接返回。**先把 `_title_editor` / `_title_editor_index` 清空**——注释说明下面 `hide()` / `deleteLater()` 可能再次触发 `editingFinished`，那时再进来会直接返回，不会重复处理。然后在 `try` 里取 `new_title = editor.text().strip()`、`removeEventFilter`、`hide()`、`deleteLater()`；捕获 `RuntimeError`（输入框已随窗口销毁）就返回。若"不提交"或名字为空或 `tab_widget` 已销毁，都保持原名不改。否则（`try` 内，下标仍有效时）如果 `tabText(index) != new_title` 就先 `self.mark_dirty(self._page_at(index))`（注释：改了页面名字也算这一页被改动过）再 `setTabText(index, new_title)`；`RuntimeError` 忽略。 |
| `FlowPageManager.mark_dirty` | 把某一页（默认当前页）标记成"有改动" | `page = page or self.current_page`，非 `None` 就 `page["dirty"] = True`。main.py 在加节点、删节点、删连线、参数变化、改页面名等处都会调它。 |
| `FlowPageManager.clear_dirty` | 某一页已经保存过（或者刚从文件里读进来）时，清掉"有改动"标记 | `page` 非 `None` 就 `page["dirty"] = False`。 |
| `FlowPageManager.mark_all_clean` | 保存方案之后调用：所有页面都标记成"没有未保存的改动" | 遍历 `self.pages`，逐条 `page["dirty"] = False`。 |
| `FlowPageManager.has_dirty_pages` | 判断有没有任何一页存在未保存的改动 | `any(page.get("dirty") for page in self.pages)`——用 `get` 而不是下标，容错。 |
| `FlowPageManager._register_page` | 登记一页流程图，返回这一页的记录 | 构造 page 字典：`key`（本页稳定标识，用于"每页 × 每图"的检测结果缓存）、`widget`、`view`、`label`、`nodes=[]`、`edges=[]`、`selected_node=None`、`dirty=False`、`project_path=None`（新建的页是 None，保存时会弹窗选路径）；`self._seq += 1`；追加进 `self.pages` 和 `self._pages_by_key[page["key"]]`；若 `tab_widget.indexOf(widget) >= 0` 就 `tabBar().setTabData(index, page["key"])`——注释说明这是"把页面标识存进标签里"，拖动标签换序之后靠它认"这个标签是哪一页"。 |
| `FlowPageManager._page_at` | 按标签下标取页面记录 | `tab_widget` 为 `None` 或下标越界返回 `None`；否则 `key = tabBar().tabData(index)`，返回 `self._pages_by_key.get(key)`。因为取的是"标签里存的页面标识"对应的记录，用户拖动标签换过顺序也不会认错页；"+"标签与标签栏空白处自然返回 `None`。 |
| `FlowPageManager._create_view` | 调用外部给的工厂创建一页画布，并设置好绘制刷新方式 | `view = self.view_factory(parent_widget)`（main.py 传的工厂就是 `FlowchartView(parent, main_window=self)`），然后 `view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)`（防拖尾残影），返回该 view。 |
| `FlowPageManager._make_view` | 让一页里有一个自定义画布：main.ui 的第一页用 `replaceWidget` 原地替换，自己新建的空白页就直接建一个放进布局 | `page_widget.findChild(QGraphicsView)` 找旧画布：为 `None` → `_create_view(page_widget)` 后取 `page_widget.layout()`（为 `None` 就新建一个 `QVBoxLayout`）再 `addWidget(view)`；找到了 → 用 `old_view.parentWidget().layout()` 的 `replaceWidget(old_view, view)` 原地替换（注释：拉伸比例、边距都会继承），再 `old_view.deleteLater()` 彻底销毁旧控件、释放内存；返回新 view。 |
| `FlowPageManager._on_tab_context_menu` | 右键点击标签栏：弹出菜单选择"添加页面 / 重命名页面 / 删除页面" | `tab_bar.tabAt(pos)` 得被右击标签的下标（点在标签栏空白处返回 -1），`_page_at(click_index)` 得对应页记录；建 `QMenu(self.tab_widget)` 加三个动作：`act_rename.setEnabled(clicked_page is not None)`（右击空白处或"+"标签时不知道该改哪一页，置灰）、`act_del.setEnabled(clicked_page is not None and len(self.pages) > 1)`（只剩一个真页面时不允许删除）；`menu.exec_(tab_bar.mapToGlobal(pos))`，返回 `None`（用户点了菜单外）就返回；命中后分别调 `add_page()` / `rename_page(click_index)` / `delete_page(click_index if click_index >= 0 else currentIndex())`（且都再检查一次页面存在与页数条件）。 |
| `FlowPageManager.eventFilter` | 事件过滤器：双击标签 → 就地改名；改名输入框里按 Esc → 取消 | 开头 `if self.tab_widget is None: return False`（标签控件已销毁时不能再碰它，直接放行）；`try` 内两条判断：① `watched is self._title_editor` 且事件是 `QEvent.KeyPress` 且 `event.key() == Qt.Key_Escape` → `_close_title_editor(commit=False)` 取消并返回 True（注释：这条只用 Python 身份比较、放在前面，尽量少访问 C++ 对象；回车交给 `editingFinished` 处理）；② `watched is self.tab_widget.tabBar()` 且事件是 `QEvent.MouseButtonDblClick` → `tabBar().tabAt(event.pos())`，下标 `>= 0` 就 `rename_page(index)` 并返回 True（这个双击已处理掉，不再传给标签栏；点到"+"标签会被 `rename_page` 自己挡掉）。捕获 `RuntimeError`（底层 C++ 对象已销毁，关窗口/退出时会出现）则安静返回 False，避免打印 Traceback；其他情况交 `super().eventFilter(...)`。 |
| `FlowPageManager._on_tab_widget_destroyed` | 标签控件（连同整个窗口）被销毁时：把引用清掉，后续事件一律忽略 | 由 `setup()` 里 `tab_widget.destroyed` 触发，把 `_title_editor`、`_title_editor_index`、`add_button`、`add_tab_widget`、`current_page`、`tab_widget` 全部置 `None`。 |
| `FlowPageManager._unique_title` | 给新页面起名字时避免和已有标签重名（用户可能手动改成了相同的名字） | 先用 `[self.tab_widget.tabText(i) for i in range(count())]` 收集现有标题；`base` 不在其中就直接用它；否则从 `n = 2` 开始递增，找到第一个不在标题列表里的 `"{0}({1})".format(base, n)` 返回。 |
| `FlowPageManager._on_tab_changed` | 标签页切换：换掉 `current_page` 并通知调用方 | `if self.switching: return`（换页/删页过程中不处理）；`page = self._page_at(index)`，为 `None` 说明选中的不是真正的页面（用户点到了最后的"+"装饰标签，例如点到它的空白处）——若 `index >= 0` 且它正好是"+"标签的位置就 `self.add_page()`（效果与点 + 按钮一样，异常按 RuntimeError 处理），然后返回；`page is self.current_page` 时直接返回（已经就是这一页，不用重复处理）；否则记下 `old_page`、`self.current_page = page`、调 `_notify_switched(old_page)`。 |
| `FlowPageManager._resync_current_page` | 兜底同步：万一标签栏当前页和 `current_page` 对不上，这里纠正并通知调用方 | `self._page_at(self.tab_widget.currentIndex())` 取当前标签对应的记录；非 `None` 且不是 `self.current_page` 时，记下旧页、替换 `current_page`、调 `_notify_switched(old_page)`。删页结束、以及"+"标签被移动后都会调它，弥补 Qt 下标变化没走到回调的情况。 |
| `FlowPageManager._notify_switched` | 通知调用方"当前页换了" | `self.on_page_switched is not None` 时调 `self.on_page_switched(self.current_page, old_page)`；main.py 在这个回调里存旧页节点参数、绑定新页引用、取新页节点参数、刷新底部提示与当前图片、更新窗口标题。 |
| `class MockHost` | 文件末尾 `__main__` 测试块里的最简宿主：只满足画布的少数回调，方便单独测试本模块 | 它有 `flow_nodes` 列表和 `on_node_selected` / `on_node_double_clicked` / `delete_flow_node` / `add_flow_node` / `add_edge` 五个空方法，用来替代 main.py 的 MainWindow。 |
| `MockHost.__init__` | 建一个空的 `flow_nodes` 列表 | 未写 docstring，按调用点推断：`self.flow_nodes = []`，让 FlowchartView 里 `hasattr(main_window, 'flow_nodes')` 之后的遍历不报错。 |
| `MockHost.on_node_selected` | 空实现，占位 | `pass`（画布选中变化时会被 FlowchartView 调用）。 |
| `MockHost.on_node_double_clicked` | 空实现，占位 | `pass`（双击节点时会被调用）。 |
| `MockHost.delete_flow_node` | 空实现，占位 | `pass`（右键删除节点时会被调用）。 |
| `MockHost.add_flow_node` | 空实现，占位 | `pass`（拖放落点建节点时会被调用）。 |
| `MockHost.add_edge` | 空实现，占位 | `pass`（拉线成功时会被调用）。 |
| 模块级 `__main__` 测试入口 | 不启动主程序，单独试用多页面标签 | `import sys` 与 `QApplication` / `QMainWindow` / `FlowchartView`；建 `QApplication` 与 900×600 的 `QMainWindow`；模拟 main.ui：一个 `QTabWidget` 先 `addTab(QWidget(), "Flow")` 再 `setCentralWidget`；`manager = FlowPageManager(tabs, lambda parent: FlowchartView(parent, main_window=host))` 后 `manager.setup()`；打印初始页面数与 `manager.page_key()`，再 `manager.add_page()` 打印一次，并打印"点最后的 + 新建 / 右键标签栏增删改 / 双击改名 / 拖动换序 / 点 × 关闭"的提示；最后 `window.show()` + `sys.exit(app.exec_())`。 |

---

> **本章属于**：⑥ 图像显示控件（缩放 / 平移 / 按图记状态）

## ImageGraphicsView.py


**文件作用**：`ImageGraphicsView` 是替代原来 QLabel 的显示控件，专门显示图像并支持缩放 / 平移。main.py 启动时按名字找到被 Tab 包着的 `graphicsView_video`，用 `ImageGraphicsView(view_video.parentWidget())` 实例化后 `parent_layout.replaceWidget(...)` **原地替换掉**它（保留布局拉伸比例），存成 `self.image_view`；之后所有画面（静态图、视频帧、相机帧、流程结果）都通过 `_display_image()` → `set_image()` 刷进来。主窗口还直接读它的 `_zoom_states` 字典，在删除图库条目时把那张图的缩放记录一起 pop 掉。文件末尾有独立测试入口。

**关键设计与原理**：
- **每张图各自记住缩放 / 平移**：`_zoom_states` 的键是"图片标识"，值是一个二元组 `(QTransform 缩放矩阵, 视图中心对应的场景坐标)`；`_current_key` 记录当前显示的是哪张。切换图片时"先把上一张存起来、再看新图有没有存档"，这样各图互不影响，也解决了"第二张图沿用第一张的放大倍数"的问题。（`set_image` 的 docstring 写"主窗口用 id(原图) 传进来"，但 main.py 实际传的是 `_display_key_of()` / `_image_key_of()` 算出的键：来自文件的图用**文件路径**（跨会话稳定，还能写进方案文件），视频帧整段共用 `"video:路径"`、相机帧整段共用 `"camera:编号"`，没有路径的（摄像头帧副本、测试图）才退回 `id(frame)`——视频/相机这样处理是为了避免"每帧都是新对象 ⇒ 每帧复位缩放 ⇒ 播放时画面一大一小、滚轮缩放被下一帧覆盖"。）
- **`set_image(cv_img, image_key)` 的三态**：① `image_key is None`（视频 / 摄像头的连续帧）→ 只换画面，用户当前的缩放和平移**保持不动**；② `image_key == self._current_key`（还是同一张，例如点了"单步执行"重新渲染）→ 同样保持当前缩放、**不复位**；③ 换到另一张 key → 先保存上一张的 `(self.transform(), self.mapToScene(viewport().rect().center()))`，再看 `_zoom_states` 里有没有这张的存档：有就 `setTransform(transform)` + `centerOn(center)` **恢复该图自己的缩放**，没有就 `resetTransform()` + `centerOn(w/2.0, h/2.0)` 复位居中。
- **只有一个图元，复用不重建**：`pixmap_item` 不存在时新建 `QGraphicsPixmapItem(pixmap)` 并 `addItem`；已存在就 `setPixmap(pixmap)`。每次都 `setSceneRect(0, 0, w, h)`，让场景边界与图像一致，视图才能正确居中/贴合。`cv_img is None` 是专门的"清空画面"分支（图库最后一张被删掉时调用）：把图元从场景里 `removeItem` 并置 None，`_current_key` 也清掉，否则列表空了画布还留着上一张图。
- **BGR→RGB 前先保证内存连续**：`cv2.cvtColor` → `np.ascontiguousarray(rgb_frame)` → `QImage(rgb_frame.data, w, h, w*ch, Format_RGB888)`（QImage 直接引用 numpy 缓冲，所以必须连续且不能是临时视图）→ `QPixmap.fromImage`。
- **交互与渲染参数**：`setRenderHints(Antialiasing | SmoothPixmapTransform)`（抗锯齿 + 平滑缩放，避免马赛克）、`setDragMode(ScrollHandDrag)`（左键按住拖动 = 平移画面）、`setViewportUpdateMode(FullViewportUpdate)`（防拖拽残影）、水平/垂直滚动条常关（`ScrollBarAlwaysOff`），界面整洁。
- **滚轮以鼠标位置为中心缩放**：先判断 `event.angleDelta().y()` 正负决定 `factor = 1.1` 或 `1/1.1`；记下缩放前 `mapToScene(event.pos())`，`scale(factor, factor)`，再算缩放后的同一点，二者之差 `delta` 用 `translate(delta.x(), delta.y())` 补偿，使鼠标指着的像素停在原位。此处**不调用基类实现**（所以不会触发 QGraphicsView 默认的滚动），代码里也**没有给缩放设上下限**。
- **`reset_zoom()` 是给"关图片 / 关视频、开摄像头"用的**：`resetTransform()` + `_current_key = None`（忘掉当前图片标识），有图元就 `centerOn(boundingRect().center())`，避免下次显示时沿用上一次的缩放。

**类 / 函数清单**：

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class ImageGraphicsView(QGraphicsView)` | 显示图像、支持滚轮缩放 / 左键拖拽平移的自定义视图（代替 QLabel） | 继承 QGraphicsView；docstring 列的四个特点：滚轮以鼠标为中心缩放、左键拖拽平移、硬件加速渲染、隐藏滚动条 |
| `__init__(self, parent=None)` | 初始化场景和交互参数 | `setScene(QGraphicsScene(self))`；`self.pixmap_item = None`；`setRenderHints(Antialiasing \| SmoothPixmapTransform)`；`setDragMode(ScrollHandDrag)`；`setViewportUpdateMode(FullViewportUpdate)`；滚动条策略都设为 `ScrollBarAlwaysOff`；初始化的两个状态字段 `_zoom_states = {}` 与 `_current_key = None` |
| `set_image(self, cv_img, image_key=None)` | 设置并显示一幅 OpenCV BGR 图像（含清空、三态缩放恢复） | ① `cv_img is None` → `scene().removeItem(pixmap_item)`、置 None、`_current_key = None` 后返回；② 否则 `cvtColor(BGR2RGB)` → `np.ascontiguousarray` → `QImage(..., Format_RGB888)` → `QPixmap.fromImage`；③ `pixmap_item` 不存在就新建并 `addItem`，否则 `setPixmap`；④ `setSceneRect(0, 0, w, h)`；⑤ 按上面"关键设计"的三态处理缩放，最后 `_current_key = image_key` |
| `reset_zoom(self)` | 把缩放和平移复位成默认状态（1:1 居中），并忘记当前图片标识 | `resetTransform()`；`_current_key = None`；有图元时 `centerOn(self.pixmap_item.boundingRect().center())`。用于关闭图片 / 视频、打开摄像头时清理视图 |
| `wheelEvent(self, event)` | 重写滚轮事件，实现以鼠标位置为中心的缩放 | `angleDelta().y() > 0` 取 `1.1`，否则取 `1.0 / 1.1`；`mouse_pos = mapToScene(event.pos())` → `scale(factor, factor)` → `new_mouse_pos = mapToScene(event.pos())` → `delta = new - old` → `translate(delta.x(), delta.y())` 补偿。**没有 scale 范围限制**，也不调用基类 |
| `if __name__ == '__main__':`（模块级测试块） | 独立测试视图的显示与缩放 | 建 `QApplication` + `QMainWindow(800x600)`，中心 `QVBoxLayout` 放一个 `ImageGraphicsView`；读 `image/lena.png`，读不到就用 `np.zeros((512,512,3))` 手绘一张彩色渐变图（逐行填蓝通道、逐列填红通道，绿通道固定 128）并打印提示；`view.set_image(img)` 后 `window.show()` + `app.exec_()` |

---

> **本章属于**：⑥ 图像列表 + 工具栏

## ImageGalleryWidget.py


**文件作用**：ImageGalleryWidget 是"图像源（图库）"的包装类，接管 main.ui 里的 `QListWidget`（`image_gallery`）以及它上方那条 `gallery_toolbar`，把列表配置成横向排列的缩略图栏。主窗口 main.py 里用 `ImageGalleryWidget(self.image_gallery)` 实例化它（main.py:258），再把 `image_selected` / `image_path_selected` 以及工具栏的 add / add_folder / delete / stop 等信号接到主窗口自己的槽上。分工是"图库只负责界面 + 状态，具体干活（选文件、跑流程、清缓存、清缩放记录）全部交给主窗口"。本文件还能独立运行：`__main__` 里建一个 QMainWindow，把当前目录 `image/` 下的图片全部导入图库做自测。

**关键设计与原理**：
- **只接管、不新建**：`__init__` 收下外部传入的 QListWidget 后，在代码里重设 `Flow=LeftToRight`、`ViewMode=IconMode`、`ResizeMode=Adjust`、`Spacing=8`、`IconSize=80x70`、`setUniformItemSizes(True)`、`setFixedHeight(85)`——这些在 Qt Designer 里也设过，但代码设置会覆盖 .ui，确保不同运行环境下行为统一（85 像素高度刚好紧密包住 60 高的缩略图，去掉下方多余空白）。
- **彻底关掉拖放（双保险）**：QListWidget 继承 QAbstractItemView，本身就是拖放目标，默认 `defaultDropAction` 是 `Qt.CopyAction`，一旦发生拖放 Qt 会以"复制"方式新增条目（图标和 UserRole 里的原图被一并复制），看起来就是凭空多一张相同的图。因此先显式关掉 `setDragEnabled / setAcceptDrops / setDropIndicatorShown / setDragDropMode(NoDragDrop) / setDefaultDropAction(IgnoreAction) / setMovement(Static)`，再给**控件本体和它的 viewport 都**装事件过滤器（拖放事件实际是发给 viewport 的），把 DragEnter / DragMove / DragLeave / Drop 全部 `ignore()` 并返回 True 吃掉。
- **工具栏的策略是"控件摆在 main.ui 里，运行时 findChild 收编"**（用户 2026.10.6 定，这样能在 Designer 里预览整条界面）：`_build_toolbar` 先按 objectName 找齐 8 个控件和那条栏；缺哪个就在代码里造哪个，并在 .ui 里没有 `gallery_toolbar` 时用 `parent_layout.indexOf/insertWidget` 自建一条插到列表上方——保证控件永远存在，且真源只有一套。
- **工具栏控件顺序与各自语义**（从左到右）：`gallery_count_label`（图像源 n/N 计数）→ 伸缩项 spacer → `gallery_auto_switch`（自动切换）→ `gallery_run_mode`（运行模式下拉框）→ `gallery_stop_button`（停止）→ `gallery_add_button`（＋图片）→ `gallery_add_folder_button`（＋文件夹）→ `gallery_delete_button`（删除）→ `gallery_collapse_button`（折叠 ∨）。其中两个开关**职责正交**（方案 B，用户 2026.10.6 拍板）：下拉框是**唯一的"执行范围"开关**，"运行全部 / 运行选中"两项**永远有且只有一项**（不会出现两项都没选的空档），而且它**只选模式、自己不执行**，执行一律交给主界面的"单步执行 / 连续执行"；"自动切换"只管"执行时是否跟随"（勾 = 批量执行时把选中项与画面跟着切到正在跑的那张；不勾 = 照样按顺序跑完，但跑完还原成开始时那一张）；停止做成独立按钮（以后停视频也用同一个）。
- **条目里存两份数据**：`Qt.UserRole` 存原图（OpenCV BGR numpy 数组），`PATH_ROLE = Qt.UserRole + 1` 存这张图的**文件路径**（摄像头抓帧、测试图这类没有文件的存 None，读出时统一成空字符串）。点缩略图时两样都发出去：原图给显示层，路径给主窗口去同步"图片源"节点的路径（图库和图片源节点是统一的）。
- **"删除"在没选中时也发信号**：`_on_delete_clicked` 一律 `delete_requested.emit(self.gallery_list.currentItem())`，列表为空/没有选中项时 item 就是 None；这是刻意为之——画布上放的是"视频源"的帧（帧不进图库），此时"删除"应当退化为"清空画布"，否则用户点了删除什么都不会发生（用户 2026.10.6 实测报过）。
- **折叠 ∨**：勾下后把整个图像列表 `setVisible(False)`（只留工具栏那一条），同时按钮文字在 `∧` / `∨` 之间切换；折叠状态只存在内存里，重启复位。

**类 / 函数清单**：

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class ImageGalleryWidget(QWidget)` | 图像源（图库）管理器，包装外部传入的 QListWidget + 上方工具栏 | 继承 QWidget；`__init__` 里 `parent` 为 None 时自动挂到 `list_widget.parentWidget()`；类属性区声明 10 个自定义信号、`PATH_ROLE`、`_DROP_EVENTS` 三个常量组 |
| `（类属性）image_selected = Signal(object)` | 点击缩略图时把该图的原图数据（BGR numpy 数组）发给主窗口 | `_on_item_clicked` 里从 `item.data(Qt.UserRole)` 取出后 `emit`；主窗口接到后切大图显示 |
| `（类属性）image_path_selected = Signal(object)` | 点击缩略图时把它的文件路径发给主窗口 | 取 `item.data(PATH_ROLE)`，空则用 `or ""`；主窗口用它把"图片源"节点的路径同步过去 |
| `（类属性）PATH_ROLE = Qt.UserRole + 1` | 条目里存"图片文件路径"用的数据角色 | Qt.UserRole 已被原图占用，所以往后排一个；`item_path()` / `has_path()` / `add_image()` 都用它 |
| `（类属性）add_requested = Signal()` | 点了"＋图片" | 工具栏按钮 `clicked` 直连 `emit`，主窗口接到后打开文件对话框 |
| `（类属性）add_folder_requested = Signal()` | 点了"＋文件夹" | 同上，主窗口选文件夹并批量导入 |
| `（类属性）delete_requested = Signal(object)` | 点了"删除"，参数 = 要删除的条目（可能为 None） | 由 `_on_delete_clicked` 发出；主窗口负责清参数存档 / 结果缓存 / 缩放记录 |
| `（类属性）run_all_requested = Signal()` | 保留信号（V2 之后没有按钮直连，留给以后扩展） | 已定义但工具栏里没有控件连它——按代码注释是"保留" |
| `（类属性）auto_switch_changed = Signal(bool)` | "自动切换"开关变化（= 执行时是否跟随） | `auto_switch_box.toggled` 直连 `emit`；当前 main.py 没有接它 |
| `（类属性）run_selected_requested = Signal()` | 菜单"运行选中"：只跑当前选中的那一张 | 已定义；main.py 注释说明 v1.17 后"运行选中"改成"范围模式"选择、不再直接执行，所以没接 |
| `（类属性）stop_requested = Signal()` | 菜单"停止"：中断正在跑的批量执行 | `stop_button.clicked` 直连 `emit`；main.py 接到 `stop_batch` |
| `（类属性）_DROP_EVENTS` | 需要拦截并丢弃的拖放类事件元组 | = `(QEvent.DragEnter, QEvent.DragMove, QEvent.DragLeave, QEvent.Drop)`，只在 `eventFilter` 里用来判断 |
| `__init__(self, list_widget, parent=None)` | 接管列表控件、关拖放、装过滤器、建/收编工具栏 | 先按上面"关键设计"重配 QListWidget 的显示属性；`installEventFilter(self)` 同时装在列表和 `viewport()` 上；最后 `itemClicked.connect(self._on_item_clicked)` 并调 `_build_toolbar()` |
| `_find(host, name, cls)`（静态方法） | 在宿主窗口里按 objectName 找控件 | `host.findChild(cls, name)`；`host` 为 None 时返回 None，供 `_build_toolbar` 逐项兜底 |
| `_build_toolbar(self)` | 建 / 收编工具栏，接线所有工具栏信号 | 先取 `host = self.gallery_list.window() or self.gallery_list`，逐个 `_find` 8 个控件；缺失的用 `QLabel("图像源 (0/0)")`、`QCheckBox("自动切换")`、`QComboBox`（`addItems(["运行全部","运行选中"])`）、4 个 `QToolButton`（`ToolButtonTextOnly`）、可勾选的折叠按钮 `"∨"` 兜底；若 .ui 里没有 `gallery_toolbar` 且确实造了控件，就自建一条 `QHBoxLayout` 的栏（count 靠左 + `addStretch(1)` + 其余依次排开）并插到列表上一行；随后设 3 条 tooltip、接 `auto_switch_changed`、`stop_requested`、`_on_collapse_toggled`、`add_requested`、`add_folder_requested`、`_on_delete_clicked`，最后 `refresh_count()` |
| `scope_all(self)`（第一个定义，第 235 行） | 执行范围是不是"运行全部" | `return self.run_mode_box.currentIndex() == 0`。**注意：这个定义被文件后面第 321 行的同名方法覆盖了**（Python 后定义者生效），此处保留的是历史版本，实际运行的是后面那个 |
| `scope_current(self)` | 执行范围是不是"运行选中" | `return self.run_mode_box.currentIndex() == 1`——下拉框只有两项，`== 1` 即"运行选中" |
| `run_mode(self)` | 当前模式的文字（"运行全部" / "运行选中"） | 直接返回 `self.run_mode_box.currentText()`；当前 main.py 里没有调用点 |
| `set_scope_all(self, all_mode=True)` | 把范围切到"运行全部"（True）或"运行选中"（False） | `setCurrentIndex(0 if all_mode else 1)`——下拉框永远有且只有一项，所以不存在"清空选择"的分支 |
| `_on_collapse_toggled(self, checked)` | 折叠 ∨：收起时把图像列表藏起来，展开时恢复 | `gallery_list.setVisible(not checked)`，并按状态把按钮文字在 `"∧"`(收起) 与 `"∨"`(展开) 之间切换 |
| `is_collapsed(self)` | 图像列表当前是否被折叠收起 | `bool(self.collapse_button.isChecked())`，按钮本身就是可勾选的折叠开关 |
| `_on_delete_clicked(self)` | 把当前选中条目交给主窗口处理（没选中也发，参数为 None） | 无条件 `self.delete_requested.emit(self.gallery_list.currentItem())`；item 为 None 时主窗口退化成"清空画布" |
| `count(self)` | 图库里现在有多少张图 | `self.gallery_list.count()` |
| `current_index(self)` | 当前选中第几项（没选中返回 -1） | `self.gallery_list.currentRow()` |
| `set_current_index(self, index)` | 选中第 index 项 | `setCurrentRow(index)` 后 `refresh_count()`；**用 setCurrentRow 不会触发 itemClicked**，所以不会重复执行流程（批量执行时靠它跟随切图） |
| `select_frame(self, frame)` | 按"原图对象"选中对应条目 | 遍历 `count()`，用 `item_frame(item) is frame` 做**对象同一性**比较；命中就 `set_current_index(i)` 并返回 i，frame 为 None 或没找到返回 -1。用途：打开文件 / 文件夹导入后把第一张点亮，让"图像源 (n/N)"显示正确 |
| `items(self)` | 按列表顺序返回 `[(item, 原图, 文件路径), ...]` | 循环 `gallery_list.item(i)`，配 `item_frame` / `item_path` 组装；主窗口的"运行全部"就是遍历这个列表 |
| `item_frame(item)`（静态方法） | 取条目里存的原图 | `item.data(Qt.UserRole)`；item 为 None 时返回 None |
| `item_path(item)`（静态方法） | 取条目里存的文件路径 | `item.data(ImageGalleryWidget.PATH_ROLE) or ""`（摄像头帧 / 测试图返回空字符串） |
| `auto_switch(self)` | "自动切换"是否打开 | `bool(self.auto_switch_box.isChecked())`；主窗口用它决定批量执行时是否跟随切图、跑完是否还原 |
| `scope_all(self)`（第 321 行，**实际生效的定义**） | "运行全部"是否被选中（= 连续执行的范围是整个图像列表；它自己不执行） | `bool(getattr(self, "run_mode_box", None) is not None and self.run_mode_box.currentIndex() == 0)`，比前面那版多了一层 None 保护；main.py 执行入口用它判范围（main.py:2334）、批量运行中用它在中途取消时急停（main.py:2567） |
| `refresh_count(self)` | 刷新"图像源 (n/N)"标签：n = 当前第几张（没选中显示 0），N = 总数 | 先 `getattr(self, "count_label", None)` 取标签并做 None 保护；`row = currentRow()`，`current = row + 1 if 0 <= row < total else 0`，再 `setText("图像源 ({0}/{1})")` |
| `remove_item(self, item)` | 从列表里移除一个条目 | `row(item)` 取行号，`>= 0` 才 `takeItem(row)` 并刷新计数；**只动列表**，参数 / 缓存 / 缩放记录由主窗口自己清 |
| `eventFilter(self, watched, event)` | 事件过滤器：把落在图库控件上的拖放事件全部拦截并丢弃 | `event.type() in self._DROP_EVENTS` 时 `event.ignore()` 并 `return True`（不再交给 QListWidget，条目不会被复制 / 新增）；其它事件 `return super().eventFilter(...)`，不影响点击、绘制、滚动 |
| `add_image(self, cv_img, path=None)` | 把一张 OpenCV BGR 图作为无文字缩略图加进图库 | `cvtColor(BGR2RGB)` → 用 `QImage(rgb_frame.data, w, h, ch*w, Format_RGB888)`（零拷贝，直接引用 numpy 缓冲）→ `QPixmap.fromImage(...).scaled(80, 60, KeepAspectRatio, SmoothTransformation)` 缩略图；新建 `QListWidgetItem` 后 `setIcon(pixmap)`、`setData(Qt.UserRole, cv_img)`、`setData(PATH_ROLE, path)`，`addItem(item)`，最后 `refresh_count()` 并返回该 item |
| `has_path(self, path)` | 图库里是不是已经有这个文件了（去重用） | 用 `os.path.normcase(os.path.abspath(...))` 归一化后逐个条目比对 PATH_ROLE，避免同一个文件出现两张缩略图；path 为空直接 False |
| `_on_item_clicked(self, item)` | 内部槽：处理缩略图点击并发射信号 | item 为 None 直接返回；`item.data(Qt.UserRole)` 非 None 时发 `image_selected`，随后无论有没有原图都发 `image_path_selected(path or "")`，最后 `refresh_count()` |
| `if __name__ == '__main__':`（模块级测试块） | 独立测试图库的加载、布局和点击交互 | 建 `QApplication` + `QMainWindow(800x200)`，中间放一个普通 `QListWidget` 并 `ImageGalleryWidget(test_list)`；遍历当前目录 `image/` 文件夹、按文件名排序，读 `.png/.jpg/.jpeg/.bmp` 逐个 `add_image(img)`（注意这里**没传 path**）、读不出来的打印警告；文件夹不存在或统计完张数后 `print` 提示，再 `window.show()` + `app.exec_()` |

---

> **本章属于**：⑦ 检测算法（直线 / 圆）+ 测试图

## Detector.py


**文件作用**：`DetectorShape` 是"检测类算子"的算法集合，提供直线（`line_detector`）与圆（`circle_detector`）两种检测；它被 NodeRegistry.py 的 `_run_line` / `_run_circle` 在流程图执行时调用，也被若干参数对话框和 SourceOps 借用 `make_test_image()` 造测试图。这里的函数只负责"算"：它们顺手画在传入数组上的绿线、红圆只是副作用，会被引擎丢掉；真正给用户看的叠加绘制统一由 `NodeRegistry.py` 的 `_draw_line()` / `_draw_circle()` 在显示层完成，这样检测结果永远不会污染下游节点的输入图像。文件末尾可独立运行自检。

**关键设计与原理**：
- **⚠ 两个检测函数都会就地修改传入数组**：`line_detector` 里的 `cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 2)` 和 `circle_detector` 里的两条 `cv2.circle(img, ..., (0, 0, 255), ...)` 都是**直接画在传进来的 `img` 上**（不是副本），并把**同一个对象** `img` 原样 return 回去。所以调用方必须自己传副本——NodeRegistry 的 `_run_line` / `_run_circle` 正是先 `patch = img[y:y+h, x:x+w].copy()` 再调，注释里明确写了"如果忘了 copy()，画绿线时会把数据层图像改掉，下游就又'看见'绿线了"；独立测试 `main()` 里则是拿 `canvas, _ = ...` 接住这个被画过的数组去 `imshow`。
- **灰度化写法**：`len(img.shape) == 2` 时直接 `gray = img`（已经是单通道），否则 `cvtColor(img, COLOR_BGR2GRAY)`；边车/圆检测在 gray 上做，但绘制仍然发生在原始 `img` 上。类注释说明：原来的灰度化函数 `gray_bgr` 已于 2026.10.3 搬到 `ProcessOps.to_gray()`，本文件只放检测类算法，处理类统一归 ProcessOps.py。
- **ROI 偏移的处理顺序很关键**：算法是在 ROI 子图（patch）上跑的，所以 `x1,y1,x2,y2` 是子图局部坐标——**绘制用的是偏移前的局部坐标**，只有加进返回的 data 列表时才逐项 `+= roi_offset_x / roi_offset_y` 换回主图真实坐标；圆同理，`(x, y, r)` 中只有 x、y 加偏移，半径 r 不加。调用方（NodeRegistry）靠这个偏移量，让"在 ROI 副本上算出的结果"能直接对上原图坐标。
- **返回值统一是 `(img, data)`**：直线 data 元素是四元组 `(x1, y1, x2, y2)`，圆 data 元素是三元组 `(cx, cy, r)`；检测不到时 data 是空列表（`lines is not None` / `circles is not None` 才进入循环）。`_draw_circle` 用 `len(item) == 3`、`_draw_line` 用 `len(item) == 4` 来区分两类结果。
- **`make_test_image()` 是给全工程复用的"没有素材时的兜底图"**：480x640 黑底，画一个白色矩形边框、一个白色圆、一条白色长横线；GrayParamsDialog、CircleParamsDialog、LineParamsDialog、SourceOps 都 import 它来造测试图（工程里没有 `image/` 目录时也能跑，不会直接崩）。

**类 / 函数清单**：

| 类 / 函数 | 作用 | 实现原理与要点 |
|---|---|---|
| `class DetectorShape` | 形状 / 图像算子集合（检测类算法） | 无基类的普通类；类注释强调"只负责算，顺手画的绿线/红圆是会被引擎丢掉的副作用"，并注明灰度化已搬到 `ProcessOps.to_gray()` |
| `line_detector(self, img, rho=1.0, theta=np.pi/180, threshold=100, min_line_length=100.0, max_line_gap=10.0, canny_low=50, canny_high=150, aperture=3, roi_offset_x=0, roi_offset_y=0)` | 检测直线段并在**原图上**绘制绿色线段，返回 `(img, 直线数据列表)` | 先按通道数取 gray（2 维直接用，否则 `cvtColor` BGR2GRAY）；`cv2.Canny(gray, canny_low, canny_high, apertureSize=aperture)` 取边缘，`cv2.HoughLinesP(edges, rho, theta, threshold, minLineLength, maxLineGap)` 取线段；遍历 `line[0]` 解出 x1,y1,x2,y2，**先** `cv2.line(img, ..., (0,255,0), 2)`（就地改 `img`，用局部坐标），**再** 四个坐标各加 roi 偏移后 append 进 `line_data`；`lines is None` 时返回空列表；返回的 img 就是传进去的那个对象 |
| `circle_detector(self, img, method=cv2.HOUGH_GRADIENT, dp=1.0, min_dist=150.0, param1=100.0, param2=80.0, min_radius=20, max_radius=0, roi_offset_x=0, roi_offset_y=0)` | 检测圆形并在**原图上**绘制红色圆，返回 `(img, 圆数据列表)` | 同样先取 gray；`cv2.HoughCircles(gray, method, dp, min_dist, param1, param2, minRadius, maxRadius)`（注意形参名是 `dp` / `min_dist`，docstring 里写作 dp / minDist）；结果 `np.round(circles[0, :]).astype(int)` 取整后逐个 `cv2.circle(img, (x,y), r, (0,0,255), 2)` 画圆 + `cv2.circle(img, (x,y), 2, (0,0,255), 3)` 画圆心（都就地改 `img`、用局部坐标），data 里 append `(x + roi_offset_x, y + roi_offset_y, r)` |
| `make_test_image()`（模块级函数） | 造一张带矩形、圆和一条长横线的测试图 | `np.zeros((480, 640, 3), np.uint8)` 起黑底，然后 `cv2.rectangle(img, (100,100), (500,400), 白, 2)`、`cv2.circle(img, (300,250), 80, 白, 2)`、`cv2.line(img, (120,430), (520,430), 白, 3)`，返回 img；被多个对话框和 SourceOps 复用为兜底素材 |
| `main()`（模块级函数） | 独立测试：优先读 `image/lena.png`，读不到就自己造一张 | 先 `DetectorShape()`，`cv2.imread('image/lena.png')` 为 None 时打印提示并改用 `make_test_image()`；然后 `canvas, line_data = detector.line_detector(img)`、`canvas, circle_data = detector.circle_detector(img)`（**两次都画在同一个 img 上**，第二次结果里会同时带着绿线和红圆），print 两个结果列表，最后 `cv2.imshow('img', canvas)` + `cv2.waitKey(0)` |
| `if __name__ == '__main__':`（模块级测试块） | 直接运行本文件时执行自检 | 调用 `main()` |

---

> **本章属于**：⑧ 界面文件（主窗口 / 设置相机编号 / 参数窗口）

## main.ui / SetCameraID.ui


**main.ui**：`QUiLoader` 在运行时加载它生成主窗口（1524x786）。**布局结构**：`QMainWindow(MainWindow)` → `centralwidget` 装 `QHBoxLayout(horizontalLayout_4)` → 里面一个 `QVBoxLayout(verticalLayout_4)`，纵向分两段：

1. **顶部按钮条**（`QHBoxLayout horizontalLayout`）：菜单 / 启动 / 停止 / 打开文件 / 单步执行 / 连续执行 / 保存项目 / 导入项目，8 个按钮都是 100x90 的固定尺寸，末尾跟一个 `horizontalSpacer` 把它们顶到左边。
2. **主工作区**（`QHBoxLayout horizontalLayout_2`，`stretch="1,3,3"` 即宽度 1:3:3）：
   - **左（第 1 列）：项目树** `QTreeWidget(tree)`，表头"项目"，四级结构：采集（图片源 / 视频源 / 相机源 / 输出图像）、处理（灰度 / 取反 / 滤波 / 二值化 / 形态学 / 边缘提取）、检测（直线 / 圆）、识别（人脸 / 颜色），另有一项"新建项目"。
   - **中（第 2 列）：流程图画布** `QTabWidget(flowWidget)`，里面第一页是 `QWidget(flow)`（标题 "Flow"），页内 `QVBoxLayout(verticalLayout_3)` 放 `QGraphicsView(flowView)` + 底部 `QLabel(lbl_current_node)`（默认文字"未选中节点"）。运行时 FlowPages.py 会把这一页的 `flowView` 换成自定义画布，并把 `flowWidget` 改造成"浏览器式"多标签页（+ 新建 / 右键菜单 / 双击改名 / × 关闭 / 拖动换序）。
   - **右（第 3 列）：显示与图库** `QVBoxLayout(verticalLayout_2)`，`stretch="14,0,2,6"` 纵向四段：① `QTabWidget(tabWidget)` → `QWidget(Video)` 页，页内 `QHBoxLayout(horizontalLayout_5)` 里放 `QGraphicsView(graphicsView_video)`（运行时会整个被 `ImageGraphicsView` 替换掉）；② `QWidget(gallery_toolbar)` 图库工具栏；③ `QListWidget(image_gallery)` 图库缩略图列表；④ `QTabWidget(result_tab)` → `QWidget(tab_2)`（标题"当前结果"）→ `QTableWidget(execution_log)`。
3. **菜单栏**：`QMenuBar(menubar)`（高 40，字号 9），挂着两个 `QMenu`：`menu`"设置"（下有 `action`"摄像头设置"）与 `menu_project`"方案"（下有 `action_open_project`"打开方案…"、`action_save_project`"保存方案"、`action_save_project_as`"另存为…"）。

控件清单（覆盖 .ui 里所有有 name 的 `<widget>` 与 `<action>`，共 33 个 widget + 4 个 action）：

| objectName | 控件类型 | 用途 |
|---|---|---|
| `MainWindow` | QMainWindow | 主窗口本体，`QUiLoader.load("main.ui")` 的根对象 |
| `centralwidget` | QWidget | 中央容器，装整条主布局 |
| `menu_button` | QPushButton | 顶部"菜单"按钮（文本＝菜单）；main.py 接 `clicked` → `_show_menubar_menu()`，把 menubar 的菜单弹到按钮左下角 |
| `camera_button` | QPushButton | "启动"（打开摄像头），接 `open_camera` |
| `close_button` | QPushButton | "停止"（关闭摄像头 / 关闭图片），接 `close_camera` |
| `open_button` | QPushButton | "打开文件"，接 `open_file`（多选图片或视频） |
| `btn_step_execute` | QPushButton | "单步执行"，接 `on_step_execute` |
| `btn_continuous_execute` | QPushButton | "连续执行"，接 `on_continuous_execute` |
| `save_project_button` | QPushButton | "保存项目"，接 `save_project` |
| `open_project_button` | QPushButton | "导入项目"，接 `open_project` |
| `tree` | QTreeWidget | 左侧项目 / 算子树（表头"项目"）；接 `itemDoubleClicked` → `_on_tree_double_click`，并允许拖拽（CopyAction）把算子拖到画布上建节点 |
| `flowWidget` | QTabWidget | 中间放流程图页面的标签容器，交给 FlowPages 接管成多页面 |
| `flow` | QWidget | 第一页流程页本体（标题 "Flow"），承载画布 + 当前节点标签 |
| `flowView` | QGraphicsView | 流程图画布占位控件，运行时被 FlowPages 换成自定义画布 |
| `lbl_current_node` | QLabel | 显示当前选中节点的文字（默认"未选中节点"） |
| `tabWidget` | QTabWidget | 右侧显示区标签容器（当前只有 Video 一页） |
| `Video` | QWidget | "Video"显示页，装 `graphicsView_video` |
| `graphicsView_video` | QGraphicsView | 图像 / 视频显示控件占位，运行时被 `ImageGraphicsView` 原地替换并删除 |
| `gallery_toolbar` | QWidget（native） | 图库工具栏容器；`QHBoxLayout(gallery_toolbar_layout)`，spacing=6、四边 margin=0。由 `ImageGalleryWidget._build_toolbar()` 用 `findChild(QWidget, "gallery_toolbar")` 收编 |
| `gallery_count_label` | QLabel | "图像源 (0/0)"：n = 当前第几张、N = 总数，由 `refresh_count()` 刷新 |
| `gallery_auto_switch` | QCheckBox | "自动切换"：执行时是否跟随（勾 = 批量执行时选中项与画面跟着正在跑的那张；不勾 = 跑完还原成开始时那张）。只发给 `auto_switch_changed`，当前 main.py 没接 |
| `gallery_run_mode` | QComboBox | 执行范围下拉框："运行全部" / "运行选中"两项，**只选模式不执行**；`scope_all()` / `scope_current()` / `set_scope_all()` 读写的就是它 |
| `gallery_stop_button` | QToolButton | "停止"：中断正在跑的批量执行，接 `stop_requested` → `stop_batch` |
| `gallery_add_button` | QToolButton | "＋图片"：交给主窗口打开文件，接 `add_requested` → `open_file` |
| `gallery_add_folder_button` | QToolButton | "＋文件夹"：交给主窗口选文件夹并导入，接 `add_folder_requested` → `add_folder_to_gallery` |
| `gallery_delete_button` | QToolButton | "删除"：接 `_on_delete_clicked`（没选中也发，参数 None）→ 主窗口 `delete_gallery_item` |
| `gallery_collapse_button` | QToolButton | 可勾选的折叠按钮，初始文字 "∨"；勾上收起图像列表并把文字变 "∧" |
| `image_gallery` | QListWidget | 图库缩略图列表（.ui 里设了 flow=LeftToRight、resizeMode=Adjust、spacing=10、viewMode=IconMode；代码里再覆盖成 spacing=8、IconSize 80x70 等）。被 `ImageGalleryWidget` 接管 |
| `result_tab` | QTabWidget | 右侧底部"结果"标签容器（.py 里没有按名字 findChild 它，只通过子控件工作） |
| `tab_2` | QWidget | "当前结果"页本体（标题 "当前结果"） |
| `execution_log` | QTableWidget | 执行日志表格，5 列："执行序号 / 执行时间 / 模块 / 图像源 / 结果数据"；main.py 里隐藏了垂直表头 |
| `menubar` | QMenuBar | 菜单栏本体；`_show_menubar_menu()` 优先找它，找不到再退回 `main_window.menuBar()` |
| `menu` | QMenu | "设置"菜单，含 `action` |
| `menu_project` | QMenu | "方案"菜单，含打开 / 保存 / 另存为三个 action |
| `action` | QAction | "摄像头设置"；main.py 里作为主窗口属性直接接 `triggered` → `set_camera_id` |
| `action_open_project` | QAction | "打开方案…"，接 `open_project` |
| `action_save_project` | QAction | "保存方案"，接 `save_project` |
| `action_save_project_as` | QAction | "另存为…"，接 `save_project_as` |

**SetCameraID.ui**：独立的小窗口定义文件（250x150，窗口标题"设置摄像头ID"），本身不是主界面的一部分，而是由 `main.py::set_camera_id()` 用 `QUiLoader().load('SetCameraID.ui')` 加载，再嵌进一个新建的模态 `QDialog`（`setModal(True)`、`WA_DeleteOnClose`、`setFixedSize(widget.size())`，用 `widget.move(0, 0)` 定位，不走布局），因此主窗口在它打开期间不能被操作。**布局结构**：`QWidget(SetCameraID)` → `QVBoxLayout(verticalLayout_3)` → `QVBoxLayout(verticalLayout_2)` → `QVBoxLayout(verticalLayout)`（提示标签 + 输入框竖排），下面再放"确定"按钮；`<resources/>` 与 `<connections/>` 都是空的（没有在 Designer 里连信号，全部由代码连）。

| objectName | 控件类型 | 用途 |
|---|---|---|
| `SetCameraID` | QWidget | 根控件（250x150，窗口标题"设置摄像头ID"），被 QUiLoader 加载后作为模态 QDialog 的内容 |
| `IDText` | QLabel | 固定 180x20 的提示文字："请输入摄像头的ID(数字)：" |
| `ID` | QLineEdit | 摄像头编号输入框；代码里 `findChild(QLineEdit, "ID")` 后先用 `setText(str(self.camera_id))` 预填当前编号 |
| `SetID` | QPushButton | "确定"按钮；代码接 `clicked` → 内部 `on_ok()`：空输入弹"摄像头ID不能为空"，`int()` 失败或为负数弹"请输入一个有效的非负整数"，通过则写入 `self.camera_id` 并 `dialog.accept()` 关闭 |

---

> **本章属于**：⑧ 界面文件 · 参数窗口布局

## LineParamsDialog.ui


**文件作用**：整个参数窗口体系的界面文件，由 `LineParamsDialog.__init__` 里的 `QUiLoader().load('LineParamsDialog.ui')` 加载（相对路径）。**所有算子参数窗口共用这一份**——直线直接用，圆在它上面换控件、灰度在它上面删页、处理类算子（`GenericProcessDialog`）在它上面动态生成"运行参数"页。根控件是普通 `QWidget`（不是 `QDialog`），由代码嵌进对话框的垂直布局里，所以窗口标题、大小、模态性都由代码决定。

**关键设计与原理**：
- **三页语义固定**：`tab` = "基本参数"（引擎级通用能力：图像源 + ROI 创建/继承 + 框选 + XYWH，算子一律不改）、`tab_2` = "运行参数"（算子私有参数）、`tab_3` = "显示结果"（结果计数）。子类按算子类型增删这两页。
- **ROI 区域是"绝对定位"的**：`groupBox_2` **自己没有布局管理器**，它的三个子容器 `roi_rows_widget` / `roi_buttons_widget` / `roi_params_widget` 各自只写了 `geometry`（如 roi_params_widget 在 y=190，roi_buttons_widget 在 y=160）。一旦行数变化就会重叠，所以代码在运行时给 `groupBox_2` 现场套一个 `QVBoxLayout`，按 rows → buttons → params 的顺序重排。
- **控件的 objectName 是代码与 .ui 的唯一契约**：代码全靠 `findChild(类型, objectName)` 取控件，改名或改类型会让 `findChild` 返回 `None`（大多被 `if` 吞掉，表现为"选项没反应"而不是报错）。
- **信号全部在代码里连**：文件末尾 `<resources/>` 为空、`<connections/>` 为空，没有一条设计器里的连线。
- **三处"一处控件多处语义"的复用**：`label_6` 在圆窗口被改成"圆数量："；`spin_canny_low` 等 5 个 QSpinBox 在圆窗口被整体换成圆参数控件；`cb_gray_full_image` 只在灰度窗口才可见。

**关键控件一览**（objectName + 类型 + 用途；拿不准的按名字/上下文推断已注明）：

| 控件 objectName | 类型 | 用途 |
|---|---|---|
| `LineParamsDialog` | QWidget | 根控件（372×558，windowTitle 写的是 "Form"）。**不是 QDialog**——它是被嵌进 `LineParamsDialog(QDialog)` 的布局里的，所以实际标题由代码 `setWindowTitle` 决定 |
| `tabWidget` | QTabWidget | 三页容器。代码里是**直接属性访问** `self.ui.tabWidget`（不是 findChild）：`setCurrentIndex(0)` 固定首屏；灰度窗口用它倒序 `removeTab` 删页；`currentIndex` 属性预设为 0 |
| `tab` / `tab_2` / `tab_3` | QWidget | 分别是"基本参数"页、"运行参数"页、"显示结果"页（标题用 `<attribute name="title">` 给，**代码靠 `tabText()` 判断是哪一页**，所以这三个标题文字很重要） |
| `groupBox` | QGroupBox | "图像输入"分组框，只装图像源这一行（内部 `verticalLayout_7` + `horizontalLayout_2`） |
| `label` | QLabel | 文字"图像源："，图像源下拉框的说明标签 |
| `input_source` | QComboBox | **图像源绑定下拉框**（数据流引擎里"这个节点从谁的图像输出开始算"）。代码填充为"自动 / 全局图像源 / 各上游节点"，`currentIndexChanged → _on_input_source_changed`；placeholderText 属性里写着一串测试残留文字"0 图像源1.图像"（下拉框有值时看不见） |
| `groupBox_2` | QGroupBox | "ROI区域"分组框。**注意它自身没有 layout**，三个子容器是绝对定位；代码给它现场套 QVBoxLayout |
| `roi_rows_widget` | QWidget | ROI 各"行"的容器（ROI创建 / 形状 / 屏蔽形状 / 外扩 / 继承自 / 作用于整图 / 位置修正），内部是 `verticalLayout`；.ui 里 geometry 写死 y=31。外扩、继承自、作用于整图这三行由代码控制显示/隐藏 |
| `roi_buttons_widget` | QWidget | "框选"与"ROI参数"两个按钮的容器（`horizontalLayout_11`，stretch 1,2,1，中间有弹簧）；.ui 里写死 y=160 |
| `roi_params_widget` | QWidget | XYWH 四行参数区（有自己的 `verticalLayout_6` → `verticalLayout_2`）；选"继承上游"时整块隐藏（让外层布局自动收高度），灰度勾"作用于整图"时整块置灰。.ui 里写死 y=190 |
| `label_x` / `spin_roi_x` | QLabel / QSpinBox | ROI 左上角 X（文字"X:"，maximum 10000）。spin 的初值由代码按 `params["roi_x"]` 或 0 设置；框选回填时也被写入 |
| `label_y` / `spin_roi_y` | QLabel / QSpinBox | ROI 左上角 Y（"Y:"，maximum 10000） |
| `label_w` / `spin_roi_w` | QLabel / QSpinBox | ROI 宽（"W:"，maximum 10000）。**形状选"圆"时 `label_w` 的文字被代码改成 "R:"**，这个 spin 就代表半径。`spin_roi_w == 0` 时执行按钮会拦截并弹"请输入ROI区域！" |
| `label_h` / `spin_roi_h` | QLabel / QSpinBox | ROI 高（"H:"，maximum 10000）。形状选"圆"时这一行（标签 + spin）被代码隐藏，所以圆只填 XYR 三个值 |
| `label_2` | QLabel | 文字"ROI创建"，这一行的标题 |
| `roi_draw` | QRadioButton | "绘制"：手动画 ROI。`toggled → _update_roi_params_visibility`；选中时显示"框选"按钮与 ROI 参数区、隐藏"外扩/继承自" |
| `roi_inherit` | QRadioButton | "继承上游"：用上游的 ROI 框或上游检出目标的外接框当 ROI（toolTip 原文："用上游的 ROI 框、或者上游检出目标的外接框当 ROI，具体在下面的'继承自'里选"）。代码里 `setChecked(True)` 把它设为新节点默认值（用户 2026.10.5 要求） |
| `label_3` | QLabel | 文字"形状" |
| `comboBox` | QComboBox | **形状下拉框**（两项：矩形 / 圆）。`currentTextChanged → _update_shape_layout`，决定 W/H 行要不要变成 R 行；代码里属性名是 `shape_combo`，存进 `params["roi_shape"]` |
| `label_4` | QLabel | 文字"屏蔽形状" |
| `cb_hide_roi` | QCheckBox | "隐藏"复选框：控制画面上那个 ROI 黄框是否隐藏，参数键 `hide_roi`（`main.py` 读它决定要不要画黄框）。默认 False 即显示黄框 |
| `label_roi_margin` | QLabel | 文字"外扩:"，只在"继承上游"时显示 |
| `spin_roi_margin` | QSpinBox | **外扩像素数**（maximum 1000，默认 0）：选"继承上游"时在上游那块框外再扩多少像素，0 = 与上游完全重合（toolTip 原文如此）；参数键 `roi_margin` |
| `label_roi_source` | QLabel | 文字"继承自"，只在"继承上游"时显示 |
| `combo_roi_source` | QComboBox | **继承来源下拉框**（两项："上游 ROI 框" / "上游结果框"）。toolTip 说明两者区别：上游 ROI 框 = 框固定、逐级一致；上游结果框 = 用上游检出目标的最小外接框，目标动框跟着动。代码按**文字**匹配映射成 `roi` / `result` 存进 `params["roi_source"]` |
| `cb_gray_full_image` | QCheckBox | **"作用于整图"**（灰度专用）。toolTip："勾上：整幅图都转灰度、忽略 ROI；不勾：只把 ROI 那块区域转灰度"。父类默认把它 `setVisible(False)`，只有 `GrayParamsDialog` 才显示并接信号；参数键 `gray_full_image` |
| `label_5` | QLabel | 文字"位置修正"，这一行的标题 |
| `pos_correction_slider` | QSlider | 水平滑条（`maximum=1`、`pageStep=1`，带自定义橙色轨道样式表）。代码里只 `setValue(0)`（注释："0 代表关闭,左滑"），**全工程没找到任何信号连接或读取它的地方**（未注释，按调用点推断：预留/未启用的功能） |
| `pushButton` | QPushButton | **"框选"按钮**（加粗）。代码里属性名是 `btn_select`，`clicked → on_select_click` 打开 `ROISelectDialog` 回填 XYWH；选"继承上游"时被隐藏，灰度勾"作用于整图"时被置灰 |
| `btn_roi_toggle` | QPushButton | **"ROI参数"展开/折叠按钮**（flat、透明背景、浅灰字、左对齐）。代码把它的文字在 "ROI参数 ▲"（展开）与 "ROI参数 ▼"（折叠）之间切换，`clicked → toggle_roi_params`；选"继承上游"时整块隐藏 |
| `groupBox_3` | QGroupBox | "运行参数"页的分组框。内部是 `horizontalLayout_17` → **`verticalLayout_8`**（5 行参数就加在这里）：`GenericProcessDialog` 用 `findChild(QVBoxLayout, "verticalLayout_8")` 拿到它往里加动态行，并在加之前把这 5 行（直线专用）整体隐藏 |
| `canny_low` / `spin_canny_low` | QLabel / QSpinBox | 标签"Canny低阈值:" + 微调框（maximum 500，默认 50）。直线：Canny 低阈值 → `params["canny_low"]`；圆窗口：标签被改成"累加器分辨率(dp):"、spin 被换成 `QDoubleSpinBox`；通用窗口：整行被隐藏 |
| `canny_high` / `spin_canny_high` | QLabel / QSpinBox | "Canny高阈值:" + spin（maximum 500，默认 150）→ `params["canny_high"]`；圆窗口改为"圆心最小距离(minDist):" + `QSpinBox` |
| `threshold` / `spin_hough_threshold` | QLabel / QSpinBox | "累加器阈值:" + spin（maximum 1000，默认 100）→ `params["hough_threshold"]`；圆窗口改为"Canny高阈值(param1):" |
| `min_line_length` / `spin_min_line_length` | QLabel / QSpinBox | "最小线段长度:" + spin（maximum 1000，默认 100）→ `params["min_line_length"]`；圆窗口改为"累加器阈值(param2):" |
| `label_10` / `spin_max_line_gap` | QLabel / QSpinBox | "最大线段间隙:" + spin（maximum 500，默认 10）→ `params["max_line_gap"]`；圆窗口改为"最小半径(minRadius):"。（这一行是 5 行里唯一用 `label_10` 而不是语义名当标签 objectName 的） |
| `groupBox_4` | QGroupBox | "显示结果"页的"检测结果"分组框（绝对定位 x=20,y=10,301×81），内部嵌 `layoutWidget` |
| `layoutWidget` | QWidget | 结果计数那一行的容器（`horizontalLayout_18`）；由 Designer 自动生成，代码不引用它 |
| `label_6` | QLabel | 文字"直线数量："。代码在 `CircleParamsDialog` 里把它改成"圆数量："；灰度窗口会把整个"显示结果"页删掉 |
| `label_7` | QLabel | 结果数字（初值 "0"）。代码里属性名 `label_result_count`，由 `update_result_count()` 按节点类型统计元组长度（直线 len==4 / 圆 len==3）后写入 |
| `btn_cont` | QPushButton | **"连续执行"**（位于 `tabWidget` 外面的底部 `horizontalLayout_9`）→ `on_cont_click`：跑完整流程图（视频模式则切 `video_processing_mode="continuous"` 并刷帧）。`GenericProcessDialog` 对"图像源"类算子会把它去掉 |
| `btn_run` | QPushButton | **"执行"** → `on_step_click`：只执行当前节点 + 它的上游链。ROI 宽或高为 0 时被拦截 |
| `btn_ok` | QPushButton | **"确定"** → `on_ok`：先执行一次单步检测，成功才 `accept()` 关窗（失败时窗口不关，便于改参数） |
