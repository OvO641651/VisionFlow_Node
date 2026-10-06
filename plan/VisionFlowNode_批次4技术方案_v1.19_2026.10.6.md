# VisionFlowNode 批次4 技术方案

| 项 | 内容 |
|---|---|
| 文档版本 | **v1.18**（历次修订见下方"v1.1 相对 v1.0 的变更"第 1~22 条；v1.0 原版保留不动） |
| 撰写日期 | 2026.10.2 起（…v1.17 于 10.6 22:11：下拉只选模式 + 删图清图片源路径；**v1.18 于 10.6 22:24：范围控件换成"运行全部 / 运行选中"下拉框、停止独立成按钮（排在下拉框后、＋图片前），并修掉"图片源节点未随模式同步"的两个真 bug**） |
| 适用工程 | `E:\opencv_python_3_8\PySide\VisionFlowNoed`（目录名少个 d） |
| 代码基线 | 批次2 提交 `668320d`、批次3 提交 `d64d7b6`；**目标1、目标2 已完成**，**目标3-M1 图片源已完成并收尾**，**目标3-M2 图像列表工具栏已全部完成（含方案 B 分工与三个 V2 项）**（均尚未提交） |
| 备份基线 | `E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_at_20261006_2149` |
| 当前状态 | **目标1、目标2 已完成**；**目标3：M1 图片源 ✅ / M2 图像列表工具栏 ✅（2026.10.6 21:49 完成）/ M3 视频流 ⬜ / M4 相机源 ⬜**；目标4 参数校验未开工（决策 d 待拍板） |
| 说明 | ★ **里程碑口径（v1.14 重订）**：**目标3 的 M1 / M2 / M3 / M4 = 图片源 / 图像列表工具栏 / 视频流 / 相机源**；**文档里原先用"M1 / M2"指"目标1 / 目标2"的写法一律作废，改写成"目标1 / 目标2"**，避免撞车。第 3 / 4 节、第 5.5~5.13 节已按**实际实现 / 最新要求**更新；第 5.1~5.4 与第 6 节的代码片段仍为**拟定**。**归档约定**：本文件是"当前版本"，只放在工程 `plan\`；每改一次方案，先在 `E:\opencv_python_3_8\backups` 存一份带版本号的快照。 |

**v1.1 相对 v1.0 的变更（按用户反馈调整）**

1. **打开方案改为"追加"**：不再清空现有页面；方案里的页面追加到现有页面之后（"+"标签前面）。原方案里的 `reset_pages()` 换成 `append_pages()`。
2. **顶部两个按钮**：`main.ui` 里新增的"保存项目 / 导入项目"两个按钮改名为 `save_project_button` / `open_project_button`，并与菜单"方案"下的两项接到**同一套实现**。
3. **关闭页面提醒保存**：每个页面增加"有未保存改动"标记（`page["dirty"]`），关闭该页时按需弹出"保存 / 不保存 / 取消"。
4. **加载去重（v1.1.1 补充）**：文件里与工作区已有页面**内容完全相同**的页不再重复创建——否则"保存 → 再打开同一文件"会把页面越堆越多（`Flow`、`Flow8(2)`、`Flow(2)(2)`…）。判定用"页面内容指纹"：标题 + 每个节点的名字/坐标/图像源绑定/参数（数值 round 4 位）+ 连线关系。
5. **一个文件只装一页（v1.1.2 补充）**：`_collect_project()` 只收**当前页**（新增 `_collect_page(page)` 负责"收一页"），`pages` 数组长度恒为 1、`current_page` 恒为 0；"另存为"的默认文件名用**当前页的标签名**；关闭非当前页时选"保存"，会先把那一页切成当前页再存。原因：以前的"保存方案"写的是**整张工作区**，导致打开某个方案会把当时开着的其它页面一起带出来（用户实测反馈）。
6. **方案文件路径按页面记（v1.1.3 补充）**：路径存在 `page["project_path"]` 上（不再是窗口级变量）。新建的页面没有文件，"保存项目"会**弹窗让用户选路径**；已有文件的页面保存时静默写回自己的文件。同时修掉"保存一页把**所有**页面的未保存标记都清掉"的问题——现在只 `clear_dirty(当前页)`。
7. **M2 落地（v1.2）**：处理类算子扩到 6 个（灰度 / 取反 / 滤波 / 二值化 / 形态学 / 边缘提取），算法与参数表放进新文件 **`ProcessOps.py`**（按大类分文件，注册表只做汇总）；新文件 **`GenericProcessDialog.py`** 按 `param_specs` 自动生成"运行参数"页（直线 / 圆 / 灰度 仍用各自的专用窗口）；双击路由改为"专用优先、通用兜底"；左侧树分成 **处理 / 检测 / 识别** 三组（灰度从"检测"移到"处理"）。识别类（人脸 / 颜色）本批不做。
8. **形态学补 3 档 + 灰度算法搬家（v1.3）**：形态学的 `morph_op` 从 4 档扩到 **7 档**（+ 梯度 / 顶帽 / 黑帽——OpenCV 同一个 `cv2.morphologyEx`，参数完全同构，所以仍是**一个节点 + 一张参数表**）；灰度的**算法本身**从 `DetectorShape.gray_bgr()` 搬到 `ProcessOps.to_gray()`（`Detector.py` 只放检测类），`ProcessOps.gray()` 不再接收 `gray_func` 参数。
9. **目标三第一版"图片源"落地（v1.4）**：新增 `SourceOps.py` 与第三类算子 `KIND_SOURCE`；树里新开顶层分组 **"采集"**；来源三选一（当前图像 / 单张图片 / 测试图），读文件按 `(路径, mtime, 大小)` **缓存**；起点节点窗口**只留"运行参数"页**；与全局图像源**并存**（决策 c 已拍板）。新增一个节点只动了 1 个新文件 + 3 处小改（注册表 / 通用窗口 / 树），节点自身的接线没动 main.py。（**注**：当时漏了执行入口的前置检查，见第 10 条。）
10. **执行入口兜底（v1.5 修复）**：用户实测发现"图库为空时点执行会被拦住、图片源那张图根本跑不了"。根因：主界面两个按钮的前置检查 + 参数窗口两处静默跳过 ⇒ 只验了引擎内部、没验 UI 入口。修法：新增 `_source_node_frame()` / `_flow_source_frame()` / `run_flow_step()` / `run_flow_continuous()`，**没有当前图时用图片源那张帧兜底**，所有执行按钮统一走这条入口；提示语也改成"或者在流程图里放一个"图片源"节点并指定图片！"。**教训：有 UI 入口的功能，验证必须走"点按钮 / 调窗口槽函数"的真实路径。**
11. **执行语义 + 参数归档的两个根本问题（v1.6 修复）**：用户一次报了 5 条问题，根因是
    ① `_run_flow_pipeline_step()` 把主窗口当前图**直接**喂给目标节点、完全不看 `input_source` 绑定
    （于是"绑了图片源却处理图库那张"、"换了图不生效"、"单步与连续逻辑不一致"）；
    ② 图片源的"来源 / 路径"存在按图片归档的 `params` 里，切图时被 `clear()` 清掉。
    修法：抽出 `_run_nodes()` 让单步与连续共用（单步 = 目标节点 + 全部祖先）、新增
    `_node_input_frame()` 供对话框取上游整图尺寸、起点节点的有效 ROI = 它自己输出的整图（且不画框）、
    图片源兜底的帧不再写进 `current_static_image`、参数归档跳过起点节点。详见 §5.7。
12. **单步语义 / 图库统一 / 起点窗口精简（v1.7）**：① **单步执行 = 只跑选中的那一个节点**
    （v1.6 改成的"目标节点 + 全部祖先"在线性链上会与连续执行结果完全相同，用户实测报为"最致命"），
    输入按它声明的"图像源"沿绑定追到起点那张图；② 框选与 ROI 尺寸也改用"该节点实际会收到的图"；
    ③ **图库与图片源统一**：图库条目开始记文件路径（`PATH_ROLE`）、执行后图片源的图自动进图库、
    点图库某张图会把当前页"图片源"的路径同步过去、新增"设置 → 导入文件夹"批量导入；
    ④ 图片源窗口：来源合并为"图片 / 测试图"，隐藏"执行 / 连续执行"，只留"确定"（= 保存并关窗）。
13. **点确定即入图库 + 导入支持文件夹（v1.8）**：① `GenericProcessDialog.on_ok()` 对起点节点
    保存参数后调用 `_ensure_source_images_in_gallery()` ⇒ **点"确定"就把那张图加进图像列表**（仍不执行）；
    ② 新增 `pick_images_or_folder()`（非原生 QFileDialog + Directory 模式 + 文件/目录列表多选），
    让"打开文件"按钮和图片源窗口的"浏览…"**一个对话框里既可选图片、也可选文件夹**
    （选文件夹 → `import_folder_path()` 导入里面所有图片、路径填第一张；选图片 → 导入这一张）；
    ③ **删除菜单里的"导入文件夹"**（main.ui 的 action 与 addaction、main.py 的接线与旧 `import_folder()`）；
    ④ 导入**全程不弹任何提示**，读不出来的图片静默跳过（去掉了"无法读取"/"以下图片读取失败"两个提示）。
14. **图片与文件夹分开、对话框回到原生（v1.9）**：v1.8 那个"非原生二合一对话框"两个毛病——
    外观与系统对话框不同（用户要"回复原本的界面"）、把两件事混在一个动作里。改成：
    ① 删除 `pick_images_or_folder()`；**"打开文件"回到原生 `getOpenFileNames`，只负责图片/视频**
    （文件夹路径因为没有图片后缀被自然忽略）；
    ② 图片源的"图像来源"新增第三档 **"文件夹"**（选项 = 图片 / 文件夹 / 测试图），路径标签改成通用的"路径"；
    ③ `_browse_file()` **按来源分开弹原生对话框**（新增 `_browse_wants_folder()` 读下拉框当前值）：
    来源=文件夹 → `getExistingDirectory`（路径 = 该文件夹，里面的图片静默进图库）；否则 →
    `getOpenFileName`（路径 = 该图片）；
    ④ `SourceOps` 新增 `first_image_in_folder()` 与"文件夹"分支（取排序第一张，兼容路径其实是图片的情况）；
    ⑤ `_ensure_source_images_in_gallery()` 对文件夹来源把整个文件夹的图片放进图库。
15. **窗口宽度 + ROI 缺省继承（v1.10）**：① 取反（没有可调参数）的窗口比别人宽一截，真因是
    "没有可调参数"那行长灰字提示——QLabel 的 sizeHint 按整行文字宽度算，把整页顶宽了；
    改成短文案 + `setWordWrap(True)` + 长说明移到 tooltip（tooltip 不参与布局），
    窗口宽度从 483 回到 340（各通用窗口统一 340）；② **"ROI创建"缺省从"绘制"改为"继承上游"**：
    `LineParamsDialog.__init__` / `_load_params` 的缺省、以及 `main.py::_resolve_roi` 与
    `_format_result_text` 的兜底全部改成"继承"（方案里明确存过 `roi_inherit: False` 的节点才走"绘制"）；
    兜底行为不变——上游没有可继承的框时自动退回本节点 ROI，不会 0 面积跳过。
16. **M2 第一阶段：图像列表工具栏接线 + 批量执行 + 归档键改路径（v1.12）**：
    ① `ImageGalleryWidget` 新增 `_build_toolbar()`——**优先收编 main.ui 里摆好的 7 个控件**
    （`findChild` 按 objectName，找不到才动态建一条同样的栏插到列表上方），并新增
    `count/current_index/set_current_index/select_frame/items/item_frame/item_path/auto_switch/refresh_count/remove_item`
    与 5 个信号（`add_requested` / `add_folder_requested` / `delete_requested` / `run_all_requested` / `auto_switch_changed`）；
    ② **归档键从 `id(原图)` 改成文件路径**（`_frame_paths` + `_image_key_of()`），
    参数存档 / 结果缓存 / 缩放记录全部跟着换，`.vfproj` 里每个节点新增 `params_by_image`（按路径存的多份参数），
    加载时还原（`_build_project_model` 必须带上这个字段，否则存了读不回来——实测踩到）；
    ③ `run_all_images(mode)`：**开始时清空日志**、逐张跑、单张出错**跳过继续**、
    **"自动切换"中途关掉即停**、结束时写一行汇总；批量循环里只切参数与当前图
    （不能用 `_show_static_image`，它会把上次缓存结果重写进日志造成重复）；
    ④ **"自动切换"只影响连续执行**："连续执行"在开关打开时 = 跑整个列表，关闭时维持原行为；
    "单步执行"永远只打当前图；⑤ 删除图库项时**连它的参数 / 结果 / 缩放一起清**；
    ⑥ "＋文件夹"按钮走原生 `getExistingDirectory` 静默导入。"折叠 ∨"与"运行选中 / 停止"仍是占位（V2）。
17. **M2 第二阶段：修用户实测报的 4 个问题（v1.13）**：① **"运行全部"改成"只做范围选择、不执行"**
    （`setCheckable(True)` + 新增 `scope_all()`；"连续执行"按 `自动切换 or 运行全部` 决定是否跑整列表）；
    ② **批量执行逐张把"图片源"节点同步到这一张**（`_sync_source_nodes_to_path(path)`）——这是"每张都在跑
    同一幅图""图 2 显示的还是图 1 的结果"的根因；③ **删除后不再被自动加回**：新增 `_removed_paths`
    黑名单（`_path_key()` / `_is_removed_path()`，`_ensure_source_images_in_gallery()` 会跳过；
    用户主动"＋图片"重新导入则放行）；④ **列表删空后画布也清空**（`ImageGraphicsView.set_image(None)`
    现在会把图像图元从场景里摘掉，以前是直接 return）。
18. **里程碑重编号 + M2 剩余任务的技术要求（v1.14，2026.10.6）**：① 目标3 的子里程碑重订为
    **M1 图片源 / M2 图像列表工具栏 / M3 视频流 / M4 相机源**（原来的"M2 视频源、M3 相机源"作废），
    文档里用"M1 / M2"指"目标1 / 目标2"的老写法一并作废；② 两个开关按**方案 B 分工**（详见 §5.13）；
    ③ 三个 V2 占位项（折叠 ∨、运行选中的菜单、"运行全部"的真下拉菜单 + 停止）本轮一起做完。
19. **目标3-M2 剩余任务实施完成（v1.15，2026.10.6 21:49）**：① 两个开关按**方案 B** 分工落地
    （范围只看 `scope_all()`；`自动切换` = 执行时是否跟随选中项；两条急停 = 菜单"停止" / 中途取消勾选"运行全部"）；
    ② 三个 V2 项做完（折叠 ∨ = 隐藏 / 恢复图像列表；`setMenu()` 挂真下拉菜单【运行选中 / 停止】；
    `run_selected_image()` 只跑当前选中的那一张）；③ 验收：新增 20 项断言 + 工具栏 34 项 + 上一轮修复 14 项 +
    九套回归 316 项全过，折叠前后截图各一张。**至此目标3-M2 全部完成**，下一个里程碑是 M3 视频流。
20. **M2 第三轮：修 4 个实测问题（v1.16，2026.10.6 22:01）**：① **"运行全部"点不动 / 菜单弹不出**——
    带下拉菜单的 QToolButton 必须显式 `setPopupMode(QToolButton.MenuButtonPopup)`，否则点主体不切换勾选
    （`scope_all()` 恒为 False ⇒ "连续执行"只跑当前一张）、点箭头也弹不出菜单；同时把 **main.ui 里早前丢失的
    `gallery_run_all_menu` 补回**，并**去掉按钮上重复挂的那两个 `<addaction>`**（菜单项只留在菜单里）；
    ② **不勾"自动切换"时，跑完要把选中项与画面还原成开始时那一张**（批量每张都会显示结果，否则
    "自动切换"形同虚设）——只恢复画面、**不动执行日志**；③ **图库一空就无条件清画布**
    （原条件"删的正好是当前图"太窄，会出现"图删光了画布还在"）；④ 菜单项 `setEnabled(True)` 兜底。
    验收：新用例 19 项 + M2 剩余任务 20 项 + 工具栏 34 项 + 上一轮修复 14 项 + 九套回归 316 项全过。
21. **M2 第四轮：下拉只选模式 + 删图要清图片源路径（v1.17，2026.10.6 22:11）**：
    ① 菜单项"运行选中"由"直接执行"改成**可勾选的"范围模式"**（与"运行全部"互斥，两者**都只改状态、
    不执行**；"停止"仍是动作），新增 `scope_current()`；`run_selected_image()` 保留为备用入口但 UI 不接；
    ② 新增 `main.py::_clear_source_nodes_path(path)`：**从图库删掉的图，图片源节点里那条路径也一并清空**，
    否则图库空了、点执行还会按图片源里的路径把这张图跑出来（用户实测）。
    验收：新用例 14 项 + M2 剩余任务 24 项 + 第三轮修复 18 项 + 工具栏 34 项 + 第二轮修复 14 项 +
    九套回归 316 项全过。
22. **M2 第五轮：范围换成下拉框 + 停止独立按钮（v1.18，2026.10.6 22:24）**：① **范围控件 = `QComboBox
    gallery_run_mode`**（两项：运行全部 / 运行选中）——下拉框**永远有且只有一项**，从结构上消掉
    用户报的"取消勾选后两个模式都没选"；切换模式**不执行**（执行只由"单步执行 / 连续执行"触发）。
    ② **`QToolButton gallery_stop_button`（"停止"）独立成按钮**，排在范围下拉框之后、"＋图片"之前，
    随手可点（以后停视频复用）；旧的 QToolButton+QMenu+两个 QAction 全部删除。
    ③ 顺带修两个真 bug：**批量结束后"还原画面"时没有还原"图片源"节点的路径**、
    **范围="运行选中"走单张时没有把图片源节点同步到当前选中那张**（会导致"范围说当前、跑的是上一张"，
    且结果被缓存到当前这张名下）。
    ④ 验收：新用例 26 项 + 九套回归 316 项全过；
    `dsh_round4 / dsh_five_issues / dsh_run_entry` 三套只加了一行 `set_scope_all(False)` 的场景设置
    （它们原本假设"连续执行只跑当前这一张"），断言未改；四套 M2 早期用例因断言的是已删除的旧控件，
    由本条合并版用例取代，不再作为门禁。

---

## 1. 批次4 的目标

| # | 事项 | 一句话目标 | 性质 |
|---|---|---|---|
| 1 | **方案持久化** | 流程图能存成文件、下次能原样打开 | 结构性改动（最大） |
| 2 | **算子扩充 + 通用参数窗口** | 处理类算子从 1 个（灰度）扩到 6 个，且以后加算子不用写界面 | 结构性改动 |
| 3 | **独立"图像源"节点** | 让流程有显式起点、能声明图像从哪来 | 新增算子 + 引擎小改 |
| 4 | **参数校验** | 参数不合法时不再静默算出错结果 | 机械、覆盖面广 |
| 5 | 收尾 | 树里未实现模块标注、日志、截图、备份 | 例行 |

**为什么要这个顺序**：事项 1 决定了"算子/参数怎么落盘"，必须先立；事项 2 引入的参数声明（`param_specs`）又是事项 4 的依据；事项 3 依赖事项 2 的通用窗口与 `file` 参数类型。所以顺序是 **1 → 2 → 3 → 4 → 收尾**。

---

## 2. 现状盘点与硬约束

### 2.1 已经存在、可以直接复用的东西

| 能力 | 现状 |
|---|---|
| 节点契约 | `NodeRegistry.NODE_SPECS`（`NodeSpec`：`kind` = process/detect、`run`、`draw`、`format_result`、`whole_image_param`） |
| 数据流引擎 | `main.py`：`_build_execution_order` 拓扑排序、`_resolve_input` 图像源绑定、`_resolve_roi` ROI 继承、`_execute_node`、`_render_display`、`_run_flow_pipeline` / `_run_flow_pipeline_step` |
| 多页面 | `FlowPageManager`：每页 `{key, widget, view, label, nodes, edges, selected_node}`，标题在标签 `tabText` |
| 参数窗口 | 直线/圆/灰度三个窗口**共用** `LineParamsDialog.ui`，靠继承做差异；基类已有图像源下拉、ROI 创建（绘制/继承上游）、继承自、外扩、框选 |
| 参数按图片归档 | `node.params_per_image = {图片标识: 整份 params}`；`_switch_image_params` 收旧→`clear()`→灌新 |
| 结果缓存 | `result_cache`，键 =（图片标识, 页面 key） |
| 视图缩放 | `ImageGraphicsView._zoom_states` 按图片标识记 `(QTransform, 中心)` |

### 2.2 三条硬约束（经代码核实，直接决定实现方式）

1. **左侧树硬编码在 `main.ui` 里**：`项目 / 检测 → 直线、圆、灰度`。
   节点是靠树项**文字**拖进画布的：`FlowchartView.dropEvent` 取 `tree.currentItem().text(0)` → `main_window.add_flow_node(text, pos)`（**不依赖 MIME 数据**）。
   ⇒ **新增算子必须改两处**：① `NodeRegistry.NODE_SPECS` 注册；② `main.ui` 树里加同名一项。
   ⇒ 未注册的名字（人脸 / 颜色）拖进去会变成一个"模块未实现"的节点（`spec is None` → 图像原样透传 + 日志写明）。

2. **节点参数的归档键是 `id(原图)`**（静态图）/ `VIDEO_ROI_KEY`（视频）：
   `_get_node_params_store` / `_save_node_params` / `_load_node_params` / `_switch_image_params`。
   ⇒ `id()` 是进程内地址，**跨会话不可复现** ⇒ **方案文件只能存"当前这一份参数"**，另存一个 `last_image` 路径。
   ⇒ 若将来要"一个方案带多张图的多套参数"，必须先把键改成**文件名/路径**（独立小改动，会波及 `_switch_image_params`、`result_cache` 键、`_zoom_states` 键）。

3. **`FlowPageManager` 没有"静默重建页面"的接口**：现有 `add_page()` / `delete_page()` 会弹确认框、且"至少保留一页"。
   ⇒ 方案加载必须新增一个内部接口（如 `reset_pages(titles)`），用于"清空并重建 N 页"。

---

## 3. 事项一：方案持久化（`.vfproj`）

### 3.1 要保存的状态

| 状态 | 来源 | 备注 |
|---|---|---|
| 页面数量 / 标题 / 顺序 / 当前页 | `FlowPageManager.pages` + `tabText` | 顺序 = `pages` 列表顺序 |
| 每页节点 | `page["nodes"]` | `name`、`pos()`、`params`、`input_source` |
| 每页连线 | `page["edges"]` | `start_node` / `end_node` |
| 当前图片路径 | `current_static_image` 的来源路径 | 用于"打开方案后自动载图"（可选） |
| 视图缩放平移 | `ImageGraphicsView._zoom_states` | 可选，第一版可不存 |

> 节点用**页内序号 id** 表示，连线和 `input_source` 引用这个 id（不用对象引用，跨会话稳定）。

### 3.2 文件格式（JSON 草案）

```json
{
  "format": "VisionFlowNode.project",
  "version": 1,
  "saved_at": "2026-10-02 18:00:00",
  "current_page": 0,
  "last_image": "E:/opencv_python_3_8/PySide/VisionFlowNoed/image/lena.png",
  "pages": [
    {
      "title": "Flow",
      "nodes": [
        {
          "id": 0,
          "name": "直线",
          "x": 20.0,
          "y": 20.0,
          "input_source": null,
          "params": {"roi_x": 0, "roi_y": 0, "roi_w": 640, "roi_h": 480,
                     "roi_inherit": false, "canny_low": 50, "canny_high": 150}
        },
        {
          "id": 1,
          "name": "灰度",
          "x": 20.0,
          "y": 220.0,
          "input_source": "__auto__",
          "params": {"roi_inherit": true, "roi_source": "roi", "roi_margin": 0}
        }
      ],
      "edges": [[0, 1]]
    }
  ]
}
```

字段语义：
- `input_source`：`null` = 自动（继承上游图像）；`"__global_source__"` = 全局图像源；`"__auto__"` = 下拉里的"自动"；数字 = 上游节点的 `id`。**建议统一**：存 `null` 表示自动、存 `"__global_source__"` 表示全局、存整数表示具体节点（读入时若该 id 不存在，退回 `null` 并记一条警告）。
- `edges`：`[[起点 id, 终点 id], ...]`。
- `params`：该节点**当前图片**的那一份 `dict(node.params)`。
- 整个文件**只装一页**（v1.1.2）：`pages` 长度恒为 1、`current_page` 恒为 0 —— 一个方案文件对应一个流程图窗口。（老的多页文件仍能整篇读进来，向后兼容。）

### 3.3 新增 / 修改的函数

| 位置 | 新增 | 说明 |
|---|---|---|
| `main.py` | `save_project(path)` | 收集 → `json.dump(ensure_ascii=False, indent=2)`；成功/失败给状态栏或日志反馈 |
| `main.py` | `load_project(path)` | 解析 → 校验 → 应用；失败**不破坏现场** |
| `main.py` | `_collect_page(page)` / `_collect_project()` | 前者把"一页"收成可 JSON 化的 dict；后者**只收当前页**（一个文件一页，v1.1.2），并带上 `last_source` |
| `main.py` | `_build_project_model(pages)` | 把文件数据整理成"待应用模型"，过滤脏数据并收集 warnings |
| `main.py` | `_apply_project(model, data)` | **追加**页面 + 恢复节点 / 参数 / 绑定 / 连线，并切到记录的当前页 |
| `main.py` | `_add_node_to_page` / `_add_edge_to_page` | 建节点 / 连线的共用底层（交互添加与加载方案共用；`mark_dirty` 参数区分） |
| `FlowPages.py` | `append_pages(titles)` | 在"+"标签前面**追加** N 页（不动任何已有页面），标题重名自动加 (2)(3)… |
| `FlowPages.py` | `mark_dirty` / `clear_dirty` / `mark_all_clean` / `has_dirty_pages` + `on_page_close_requested` 回调 | 每页记"有未保存改动"；关闭该页前先问调用方（可取消关闭） |
| `main.ui` | 菜单项 + 顶部按钮 | "方案"菜单（打开方案… / 保存方案 / 另存为…）+ 顶部 `save_project_button` / `open_project_button` |
| `main.py` | 动作接线 | 菜单三项与两个按钮都接到同一套 `save_project` / `save_project_as` / `open_project`；文件对话框过滤 `*.vfproj` |

### 3.4 加载流程（含失败回滚）

```
1. 读文件 → json.loads          失败 ⇒ 提示"文件不是合法 JSON"，直接返回
2. 校验 format / version        不匹配 ⇒ 提示（版本高于当前：拒绝；低于当前：尝试兼容读）
3. 全量构造"待应用模型"（不碰 UI）：pages → nodes(name 必须已注册) → edges → 参数
   · 未知算子：跳过该节点，收集到 warnings
   · 引用不存在的节点 id 的连线 / 绑定：丢弃，收集到 warnings
4. 去重（v1.1.1）：先算"工作区已有页面"的指纹集合，文件里每一页算指纹——命中就跳过
   （并记一条"有 N 页与工作区里已有的页面完全相同，已跳过"）；全都被跳过 ⇒ 什么都不建，
   弹一句"没有新增页面"后直接返回成功
5. 应用：调 FlowPageManager.append_pages(titles)（**只追加、不动已有页面**）
        → 逐页建节点（mark_dirty=False）→ 恢复 params → 恢复 input_source → 连好线
        → 参数同时写进 params_per_image[当前图片键] → 新页清掉 dirty
        → 切到"新页里的第 current_page 页"（标签下标 = 第一张新页的下标 + N）
6. 刷新：换页回调会重新绑定主窗口引用并刷新画面；有图时再按新流程跑一次连续执行
7. 有任何 warnings ⇒ 汇总弹一次提示（例如"有 3 页…已跳过"、"算子'人脸'没有实现"）
```

关键要求：**第 3 步全部通过之后才执行第 4 步**；由于第 4 步是"追加"，失败也不会毁掉已有页面（比 v1.0 的"清空重建"安全得多），但仍然要把第 3 步的校验做足。

**补充：关闭页面时提醒保存（v1.1）**

- 每页有 `page["dirty"]`：加 / 删节点、加 / 删连线、拖动节点、参数窗口改过参数、改页面名 ⇒ 置 True；
  保存方案成功 ⇒ 全部清 False；刚从文件加载进来的新页 ⇒ 保持 False。
- 关闭页面（`close_page` / 右键"删除页面"）时，`FlowPageManager._remove_page()` 先回调
  `on_page_close_requested(page)`：main 的 `_confirm_close_flow_page()` 只在 dirty 时弹出
  "保存 / 不保存 / 取消"（自带中文按钮，避免依赖 Qt 中文翻译）；回调返回 False 就取消关闭。

### 3.5 边界与容错清单

- 文件不存在 / 无权限 / 编码不是 UTF-8。
- `version` 缺失或非整数；`pages` 为空数组；`title` 重复或为空。
- 节点 `name` 未注册 / `params` 不是字典 / 坐标不是数字（给默认 0,0）。
- 连线引用不存在的 id；自环（`from == to`）；**成环**（引擎已有"成环节点跳过"的兜底，但要保证 UI 上也能看出来）。
- `input_source` 指向的节点在**同一页之外**（跨页绑定）→ 视为无效，退回自动。
- 大方案（比如 50 个节点 × 10 页）加载耗时；保存时不要阻塞 UI 太久（第一版可接受同步）。

### 3.6 验收用例（无头冒烟）

1. **往返一致**：搭 1~3 页 / 每页 2~3 节点 / 带连线与绑定 / 带非默认参数 → `save_project` → 改点东西（删节点、加节点、改参数）→ `load_project` → 逐项断言：新增页数、标题、每页节点数与 `name`、坐标（±0.5）、`input_source`、`params` 全等、连线集合相等、切到的页正确。
2. **追加语义（v1.1 新增）**：现场先有 2 页（都 dirty）→ 打开方案（方案里 1 页）→ 断言变成 3 页、原有页的标题/内容/dirty 全部保留、新页追加在最后且重名自动加 (2)、"+"标签仍在最后、新页 `dirty=False`。
   再断言**去重（v1.1.1）**：把刚保存的文件再打开一次 ⇒ 页数不变并提示"没有新增页面"；文件里多出一页时只追加那一页；同一文件里两页内容相同只建一份。
3. **关闭提醒（v1.1 新增）**：干净页直接关（一次弹窗都不弹）；dirty + 取消 ⇒ 页面还在；dirty + 不保存 ⇒ 关掉且不触发保存；dirty + 保存 ⇒ 先保存再关；保存失败 ⇒ 不关。
4. **两个按钮（v1.1 新增）**：`save_project_button` / `open_project_button` 存在，点击后分别走保存 / 打开（用替身 `QFileDialog` 验证，保存要真的写出文件）。
5. **容错**：坏 JSON / 空 `pages` / 未知算子 / 悬空连线 / 成环 / 版本不符 —— 逐个跑，断言"不抛未捕获异常 + warnings 内容正确 + 现场未被破坏（当校验阶段失败时）"。
6. **单页保存（v1.1.2 新增）**：切到某一页 → 保存 → 断言文件里**只有 1 页**且就是那一页（其它页不在文件里）；用同一个文件保存另一页会覆盖成那一页；关闭"非当前页"并选"保存"时，存进文件的是**要关的那一页**。
7. **按页面记路径（v1.1.3 新增）**：导入一个方案后再**新建**一页 → 在新页上点保存 → 断言**弹出了选路径窗口**、新文件按选择生成、**原来那个方案的文件内容一字未改**；切回原页面保存 → 不弹窗、写回它自己的文件；保存一页之后，**别的页面的 dirty 仍然是 True**。
8. **回退点**：每次改动前先建对应的 `_backup_VisionFlowNoed_before_<改动>`（M1 是 `before_project_persist`，v1.1 是 `before_append_pages_and_buttons`，去重是 `before_project_dedupe`，单页保存是 `before_single_page_save`，按页面记路径是 `before_page_project_path`）。

---

## 4. 事项二：算子扩充 + 通用参数窗口

### 4.1 现状与问题

- 现在 3 个算子里，**每个算子一个参数窗口**（`LineParamsDialog` / `CircleParamsDialog` / `GrayParamsDialog`，后两者继承前者）。
- 若要按老办法加 5 个处理类算子，就是 5 份 `.ui` + 5 套读写代码，后续每加一个算子都要重复一遍。
- 目标：**把参数变成声明**，界面由声明生成。

### 4.2 设计：`NodeSpec.param_specs`

```python
NodeSpec(
    name="二值化", kind=KIND_PROCESS, run=_run_threshold,
    format_result=_format_process,
    param_specs=[
        ("mode",    "模式",   "combo", {"options": ["固定阈值", "Otsu", "自适应"], "default": "固定阈值"}),
        ("thresh",  "阈值",   "int",   {"min": 0, "max": 255, "default": 127}),
        ("maxval",  "最大值", "int",   {"min": 0, "max": 255, "default": 255}),
        ("bin_type","类型",   "combo", {"options": ["二值", "反二值"], "default": "二值"}),
    ],
    validate=_validate_threshold,     # 可选：返回 [错误信息, ...]
)
```

### 4.3 控件类型映射表

| `type` | 控件 | 附加键 | 取值 |
|---|---|---|---|
| `int` | `QSpinBox`（`odd=True` 时只允许奇数，步长 2） | `min` / `max` / `default` / `odd` | `int` |
| `float` | `QDoubleSpinBox` | `min` / `max` / `step` / `decimals` / `default` | `float` |
| `combo` | `QComboBox` | `options` / `default` | 选中的文本 |
| `bool` | `QCheckBox` | `default` | `bool` |
| `file` | `QLineEdit` + "浏览…" 按钮（`QFileDialog`） | `filter` / `default` | 绝对路径字符串 |

> 兼容性原则：**取值统一存进 `node.params[参数名]`**，键名与现有参数风格一致（小写下划线）；未设置过时读 `default`。

### 4.4 `GenericProcessDialog` 设计

- **新增文件 `GenericProcessDialog.py`**，`class GenericProcessDialog(LineParamsDialog)`：
  1. `super().__init__(...)` 复用"图像源 + ROI创建 + 继承自 + 外扩 + 框选"那一整套（含 ROI 区自适应布局、显隐规则）；
  2. 标题设为算子名（`self.setWindowTitle(spec.name)`）；
  3. 取 `spec.param_specs`，把"运行参数"页（`tab_2`）里原有的 5 个直线专用控件**隐藏**，在同一个布局里**动态插入**生成的控件（一行一个：`QLabel(中文名) + 控件`）；
  4. `_load_params()`：先 `super()._load_params()`，再按 `param_specs` 把 `node.params` 灌进动态控件（缺值用 `default`）；
  5. `_update_params()`：先 `super()._update_params()`，再把动态控件的值写回 `node.params`；
  6. 保留"只显示与它有关的页"的规则：处理类算子不需要"显示结果"页（那里是结果计数），按需 `removeTab`；
  7. `validate` 钩子：保存/执行前跑 `spec.validate(params)`，有问题按第 6 节的策略处理。
- **路由改造**（`main.py::on_node_double_clicked`）：
  ```python
  spec = get_spec(node.name)
  if spec is not None and spec.param_specs is not None:      # 有参数声明的处理类算子
      dialog = GenericProcessDialog(self.main_window, node=node, main_window=self)
  elif node.name == "直线": ...
  elif node.name == "圆":   ...
  elif node.name == "灰度": ...                              # 灰度窗口仍可保留专用（它只有一个开关）
  ```
  ⇒ 新增算子不再需要改 `on_node_double_clicked`。

### 4.5 五个算子的参数表与 OpenCV 映射

| 算子 | `param_specs` | `run()` 关键实现（处理类：必须 `copy` 出新图） |
|---|---|---|
| **取反** | 无（沿用 ROI / 继承） | `out[roi] = cv2.bitwise_not(patch)` |
| **滤波** | `type`(均值/高斯/中值)、`ksize`(int, odd, 1~31, 默认 3)、`sigma`(float, 默认 0) | `cv2.blur` / `cv2.GaussianBlur` / `cv2.medianBlur` |
| **二值化** | `mode`(固定/Otsu/自适应)、`thresh`(0~255)、`maxval`(0~255)、`bin_type`(二值/反二值) | `cv2.threshold` / `cv2.threshold(..., THRESH_OTSU)` / `cv2.adaptiveThreshold`；结果需 `cvtColor(GRAY2BGR)` 回 3 通道 |
| **形态学** | `op`(**腐蚀/膨胀/开/闭/梯度/顶帽/黑帽**，v1.3 起 7 档)、`shape`(矩形/椭圆/十字)、`ksize`(odd)、`iterations`(1~10) | `cv2.getStructuringElement` + `cv2.morphologyEx`（含 `MORPH_GRADIENT` / `MORPH_TOPHAT` / `MORPH_BLACKHAT`） |
| **边缘提取** | `method`(Canny/Sobel/Laplacian)、`low`、`high`、`ksize`(odd) | `cv2.Canny` / `cv2.Sobel` / `cv2.Laplacian`；输出灰度 → 补成 3 通道 |

**统一结果文案**：`ProcessOps.format_process()` 返回"执行成功（图像已处理，下游可见）"，取反 / 滤波 / 二值化 / 形态学 / 边缘提取共用（灰度保留"图像已灰度化"那句）。

### 4.6 实现落地（v1.2，2026.10.3）

| 项 | 落地情况 |
|---|---|
| 算法位置 | 新文件 **`ProcessOps.py`**：`ProcessOps` 类（每个算子一个方法）+ 文件末尾 `PROCESS_SPECS` 声明表；三条硬规矩写在文件头（不就地改入参 / 输出保证 3 通道 / 只动 ROI）；本文件不 import `NodeRegistry`（避免循环导入）。**灰度算法本身也在 `ProcessOps.to_gray()`**（v1.3 从 `DetectorShape.gray_bgr` 搬来，`Detector.py` 只放检测类） |
| 参数表实际键名 | 取反：无；滤波 `blur_type` / `blur_ksize`(odd) / `blur_sigma`；二值化 `thresh_mode` / `thresh_value` / `thresh_maxval` / `thresh_type`；形态学 `morph_op` / `morph_shape` / `morph_ksize`(odd) / `morph_iterations`；边缘提取 `edge_method` / `edge_low` / `edge_high` / `edge_ksize`(odd) |
| 注册方式 | `NodeRegistry` 文件末尾 `from ProcessOps import PROCESS_SPECS`，逐条组装成 `NodeSpec(kind=KIND_PROCESS)` ⇒ 加一个处理类算子只改 `ProcessOps.py` + `main.ui` 树，不动引擎 |
| 参数声明语义 | `param_specs=None` = 专用窗口（直线 / 圆 / 灰度）；`[]` = 通用窗口但没有可调参数（取反）；有内容 = 通用窗口按表生成 |
| 通用窗口 | `GenericProcessDialog(LineParamsDialog)`：先藏掉"运行参数"页里直线专用那几行（按布局项遍历，不依赖控件名），再按表生成 `param_<键名>` 控件（int / float / combo / bool / file）；处理类去掉"显示结果"页；没参数时给一句灰字提示。**必须先把父类写进来的直线参数 pop 掉**，否则无参数算子会混入无关参数 |
| 双击路由 | 专用优先（直线 / 圆 / 灰度），其余 `param_specs is not None` 的走通用窗口 ⇒ 新增算子不必再改 `on_node_double_clicked` |
| 树分组 | 处理（灰度 / 取反 / 滤波 / 二值化 / 形态学 / 边缘提取）、检测（直线 / 圆）、识别（人脸 / 颜色，未实现） |
| 本批未做 | 除灰度外没有"作用于整图"开关（引擎已支持 `whole_image_param`，加一行声明即可）；`validate`（目标四）未接；`file` 控件类型已实现但暂无算子使用（留给目标三的图像源节点） |

**共同注意**：
- 处理类算子必须 `out = img.copy()` 后改 ROI 区域，**不能就地改入参**；
- 单通道结果要 `cv2.cvtColor(..., cv2.COLOR_GRAY2BGR)` 再返回（下游的 `cv2.line/circle` 要求 3 通道——灰度的实现里已有这条说明）；
- 参数缺失时取 `default`，不要出现 `None` 参与切片。

### 4.6 左侧树与注册（每个算子两处都要改）

1. `NodeRegistry.py`：加 `NodeSpec`（含 `param_specs`）；
2. `main.ui`：在树里加一项。**建议新增一个"处理"分组**：
   ```
   项目
   ├─ 检测     直线 / 圆
   ├─ 处理     灰度 / 取反 / 滤波 / 二值化 / 形态学 / 边缘提取
   └─ 识别     （空，人脸/颜色标"未实现"或暂时移除）
   ```
   （"灰度"从"检测"挪到"处理"会改变用户习惯，见第 9 节附加问题。）

### 4.7 验收用例

- 每个算子：对真实图跑一遍，断言 ① 输出形状 = 输入形状 ② `dtype=uint8` ③ 3 通道 ④ **参数确实生效**：
  - 取反：`np.array_equal(out, 255 - src)`
  - 二值化（固定阈值）：`set(np.unique(out)) <= {0, 255}`
  - 滤波（中值核 5）：对椒盐噪声图，噪点数量显著减少
  - 形态学（膨胀核 3 迭代 1）：白色像素数量 ≥ 输入
  - 边缘（Canny 50/150）：输出只有黑/白两值
- 通用窗口：`findChild` 能拿到动态控件；改值 → `_update_params()` → `node.params` 有值；`_load_params()` 能读回；`param_specs` 缺省值生效。
- 界面截图：取"参数最多的算子"（形态学/边缘）窗口 + 至少一张，覆盖"内容最多"状态。

---

## 5. 事项三：独立"图像源"节点

### 5.1 目标语义

- 给流程一个**显式起点**，并声明"图像从哪来"，而不是永远靠工具栏"打开"来驱动。
- 它**不产出检测结果**，只产出图像（`kind` 可复用 process 语义：图像输出 = 输入帧）。
- 与现有"全局图像源"**并存**：流程里没放它就还是老行为。

### 5.2 参数设计（`param_specs`）

| 参数 | 类型 | 说明 |
|---|---|---|
| `source_type` | combo | 当前图像 / 相机 / 视频文件 / 单张图片 / 测试图 |
| `path` | file | `source_type` 为文件类时使用（过滤 `*.png *.jpg *.bmp *.mp4`） |
| `camera_id` | int | 相机模式用（可复用现有 `SetCameraID.ui` 的思路） |
| `crop` | bool | 是否只把图的一块喂给下游 |
| `crop_x/y/w/h` | int | 裁剪区域（复用 ROI 的框选交互更好，第二版再做） |
| `scale` | float | 缩放系数（0.1~4.0，默认 1.0） |

### 5.3 引擎落点

- 它没有父节点 —— `_build_execution_order` 已支持（`parents[node]` 为空列表）。
- `_resolve_input` 对它返回 `SOURCE_KEY`（当前帧）即可；它的 `run()` 直接把 `in_img` 返回（同一对象，符合"检测/透传"的省内存约定），或按参数裁剪/缩放后返回**新图**。
- `source_type = 文件` 时由节点自己读文件：**必须缓存**（按 `(path, mtime)` 缓存解码结果），否则每帧重复解码会卡。
- ROI 继承对它是"起点无上游"的情况：`in_roi = None` → 若节点开了"继承上游"，日志按现有规则写"← 继承未生效（改用本节点 ROI）"。

### 5.4 验收用例

- 拖入"图像源"节点 → 双击出窗口 → 选"当前图像"：与不放它时结果一致（回归）。
- 选"单张图片"并指定 `image/lena.png`：下游拿到的是该文件图像（不是主窗口当前打开的那张）。
- 选"裁剪"，裁一块后下游只在那一块处理。
- `crop`/`scale` 关掉时，节点输出与输入是同一对象（可用 `is` 断言，验证没多做一次拷贝）。

### 5.5 实现落地（v1.4，2026.10.5）

| 项 | 落地情况 |
|---|---|
| 第一版范围（用户定） | 只做 **"图片源"** 一个节点；来源三选一：**当前图像 / 单张图片 / 测试图**；树里新开顶层分组 **"采集"**（排在"处理"前）；**视频源 / 相机源 / 多图批量留后续** |
| 新增文件 | `SourceOps.py`：`run_source()` + `_load_image()`（按 (路径, mtime, 大小) 缓存）+ `_cached_test_image()` + 文件末尾 `SOURCE_SPECS` 声明表；**不 import NodeRegistry**（避免循环导入） |
| 第三类算子 | 新增 `KIND_SOURCE = "source"`（流程起点：没有上游、自己造图）；`modifies_image` 改为 `kind in (KIND_PROCESS, KIND_SOURCE)` |
| 结果怎么带来源 | results 里放 **dict**（`[{"图片源": "lena.png"}]`）——日志列由 `format_result` 生成、拿不到 params；而 `result_bbox()` 只认 tuple / list、会跳过 dict ⇒ 不影响下游 ROI 继承 |
| 窗口 | 起点节点**只留"运行参数"页**（`GenericProcessDialog._remove_basic_tab()`：`kind == KIND_SOURCE` 时去掉"基本参数"页——没有上游，图像源绑定 / ROI 继承对它没意义） |
| 引擎落点 | 双击路由本就"有 param_specs 就走通用窗口"、拓扑排序已支持无父节点、`_resolve_input` 对起点返回全局源（`run()` 忽略它、改用自己的图）⇒ 与全局图像源**并存**，日志"图像源"列能区分。**但第一版漏了执行入口的前置检查**（v1.5 已修，见 §5.6） |
| 尚未做 | 缩放 / 裁剪参数；多选 / 目录（多图 + 批量执行）；视频源 / 相机源 |

### 5.6 执行入口兜底（v1.5 修复，2026.10.5）

**问题**：主界面"单步执行 / 连续执行"两个按钮都有一道前置检查
`if current_static_image is None and cap is None: 弹窗提示 + return`；参数窗口里的
"执行 / 连续执行"更是 `if current_static_image is not None: ...`，不满足时静默跳过。
⇒ **图库为空、也没打开图时，即使流程里放了"图片源"，点执行也跑不了**（用户实测发现）。
根因是验证只覆盖了引擎内部（直接喂帧），没走 UI 入口。

**修法**：把"这一轮用哪张帧"集中判定，并让所有执行按钮走同一条入口。

| 新增（main.py） | 作用 |
|---|---|
| `_source_node_frame()` | 遍历当前页节点，取**图像源类**节点这一轮能给出的图（`spec.run(detector, None, (0,0,0,0), params)`；来源选"当前图像"时返回 None） |
| `_flow_source_frame()` | ① 有当前图 / 视频 → 用它（老行为）；② 没有但页面里有图像源节点 → **用那张图兜底**；③ 都没有 → 返回 (None, 提示语) |
| `run_flow_step(node)` / `run_flow_continuous()` | UI 单步 / 连续的唯一入口：先定帧（定不到就弹提示返回 False），再交给 `_execute_static`（计算 → 显示 → 写缓存 → 刷日志） |

- `on_step_execute()` / `on_continuous_execute()`：视频分支保持原样，静态那条改为调上面两个入口；
- `LineParamsDialog.on_step_click()` / `on_cont_click()`：先判断是否视频模式，不是就走主窗口入口
  ⇒ **窗口里点执行也能用图片源那张图跑**，并能返回 True 让"确定"正常关窗；
- 提示语改成："请先导入图片/视频或者打开摄像头，**或者在流程图里放一个"图片源"节点并指定图片**！"
- **显示**：`_execute_static` 本来就是"计算 → `_display_image` → 写结果缓存 → 刷日志"一条链，
  所以只要能进得来，处理后的图就会显示在右侧画布上（实测：图库为空时点连续执行，
  右侧显示灰度后的 lena，日志两行"全局图像源 / 节点：图片源"）。

### 5.7 执行语义与参数归档的两个根本问题（v1.6 修复，2026.10.5）

用户实测一次报了 5 条问题（"单步执行处理的是图库那张图"、"ROI 读不到上游图尺寸"、
"图片源窗口执行后多出个 512×512 黄框"、"换了图片源的文件还是跑旧图"、
"单步与连续逻辑错乱"），追到根上只有两个错误：

**① 单步执行不看"图像源"绑定（执行语义错误）**
`_run_flow_pipeline_step()` 老实现是 `_execute_node(target_node, frame.copy(), None)`——
把主窗口当前那张图**直接**喂给目标节点，完全不解析 `node.input_source`；
而连续执行是按绑定走的 ⇒ 绑定形同虚设、两套逻辑不一致；上一轮执行写进
`current_static_image` 的帧还会被下一轮"优先"取用（所以换了图也不生效）。

**② 起点节点的参数被"按图片归档"清掉（归档错误）**
`_save_node_params()` / `_load_node_params()` 是"整份 `node.params` 按图片存取"，
而图片源的"来源 / 路径"也在 `params` 里 ⇒ 切换图库里的图时被 `clear()` 清空、退回"当前图像"。
（与当年"`input_source` 绝不能存 `params`"同类。）

**修法**：

| 改动 | 内容 |
|---|---|
| 共用执行段 | 新增 `_run_nodes(order, parents, frame, skipped, base_node)`；连续执行 = 全部节点，单步执行 = **目标节点 + 它的所有祖先**，两者共用同一段执行 / 渲染逻辑 |
| 单步语义 | `_run_flow_pipeline_step()` 改成"收集祖先 + 按拓扑序跑"，目标节点的输入严格按它声明的图像源来（本引擎每次从起点重算，所以"运行到这一步"必须把上游链一起算出来）；显示底图固定为目标节点 |
| ROI 默认值 | 新增 `_node_input_frame(node)`：沿图像源绑定往上追到起点，返回"这个节点实际会收到的图"；对话框用它定 ROI 默认宽高（追不到才退回主窗口当前图） |
| 起点节点的 ROI | `_execute_node()` 对 `KIND_SOURCE` 直接把有效 ROI 设成**它自己输出的整张图** + `hide=True`；`_render_display()` 跳过起点节点画框；`GenericProcessDialog._update_params()` 把起点节点的 ROI 参数 pop 掉 |
| 不篡改"当前图" | `_flow_source_frame()` 多返回"是否图片源兜底"；`_execute_static(..., adopt_frame=False)` 时不更新 `current_static_image` |
| 归档跳过起点节点 | 新增 `_is_source_node()`；`_save_node_params()` / `_load_node_params()` 跳过起点节点（图片源的配置属于流程图本身） |

**验证**：22 项针对性断言（按用户场景：图库 lena 512×512 + 图片源 HoughLines 897×708）
全 PASS；M2 114 / 形态学 43 / 方案路径 21 / 图片源 35 / 执行入口 17 项回归全过；
截图 `fix5_step_uses_source_image.png`（画布是 HoughLines 的灰度图）、
`fix5_source_no_roi_box.png`（图片源执行后没有黄框）、
`fix5_gray_dialog_roi_from_upstream.png`（ROI 自动填 897×708）。

### 5.8 单步语义 / 图库统一 / 起点窗口精简（v1.7，2026.10.5 23:02）

用户实测报 4 条（含"最致命"的单步与连续结果相同），逐条修法：

| 问题 | 修法 |
|---|---|
| **单步执行与连续执行结果一模一样** | `_run_flow_pipeline_step()` 改成**只跑选中的那一个节点**（回到 2026.7.25 的规则），输入帧 = `_node_input_frame(target_node)`（沿绑定追到起点那张图）；新增 `_binding_origin()` 供日志写明"节点：图片源（单步：只跑本节点）"。原因：v1.6 的"目标 + 全部祖先"在线性链上等价于整条链 |
| 图库为空时"框选"弹提示 | `on_select_click()` 与 `refresh_size()` 都改成优先用 `_node_input_frame(node)`，取不到才退回当前图 / 视频帧 |
| 图片源的图不在图库、点图库不同步、没有文件夹导入 | 图库条目新增 `PATH_ROLE` 记文件路径、`has_path()` 去重、`image_path_selected` 信号；主窗口新增 `_sync_source_nodes_to_path()`（点图库 → 同步图片源路径）、`_ensure_source_images_in_gallery()`（执行后图片源的图进图库）、`import_folder()` + 设置菜单 `action_import_folder`；`open_file()` 加图库时带路径 |
| 图片源窗口按钮与来源多余 | 来源合并为 **图片 / 测试图**（"图片"没填路径 = 用当前图；老值"当前图像"/"单张图片"继续兼容）；`_remove_run_buttons()` 隐藏 `btn_run`/`btn_cont`；`on_ok()` 对起点节点 = 只保存并关窗 |

**验证**：26 项针对性断言全 PASS（含"单步结果 ≠ 连续结果"逐像素断言、框选拿到上游图、
图库同步与去重、文件夹导入、窗口只剩确定、来源分支与老值兼容）；
六套回归（五问 22 / 执行入口 16 / 图片源 35 / M2 114 / 形态学 41 / 方案路径 21）全过；
截图 `round4_source_dialog_only_ok.png`、`round4_gallery_unified.png`。

### 5.9 导入路径与提示（v1.8，2026.10.5 23:17）

用户两条要求（连同对我上一轮实现的两句质疑）：

| 要求 / 质疑 | 我上一轮错在哪 | v1.8 修法 |
|---|---|---|
| "在图像源节点中导入的图片也发到图像列表中…为什么点确定后没看到" | 只把"进图库"挂在 `_execute_static()`（**执行之后**），而"确定"= 只保存不执行 ⇒ 不触发；且只验了"执行路径" | `on_ok()` 里对起点节点保存后调 `_ensure_source_images_in_gallery()` ⇒ **点确定即入库**（仍不执行流程） |
| "删除菜单栏的'导入文件夹'按钮，把功能集成到'打开文件'按钮和图像源节点中…选文件夹则导入文件夹内容，选图片则导入该图片。删掉导入后的提示窗口；导入失败自动跳过、不需要提示" | 功能藏在**菜单**里；`open_file`/`_browse_file` 仍用只能选文件的 `getOpenFileNames`/`getOpenFileName`；导入后弹提示、失败也弹提示 | 新增 `pick_images_or_folder()`（**一个对话框**里既能选图片也能选文件夹：非原生 QFileDialog + `Directory` 模式 + 文件/目录列表 `MultiSelection`）；`open_file()` 与 `_browse_file()` 都改用它；新增 `import_image_path()` / `import_folder_path()` / `import_paths()`（**静默跳过坏文件、全程无提示**）；删除菜单项与旧 `import_folder()` |

**验证**：25 项新断言全 PASS（点确定入库且不执行、无提示、菜单项已删、"打开文件"选文件夹/图片/混选、
坏文件静默跳过、图片源"浏览…"选文件夹后路径填第一张且图库到 2 张）；
八套回归合计 **302 项**全过；截图 `round5_ok_adds_to_gallery.png`、`round5_browse_folder.png`、
`round5_browse_folder_main.png`。
**备注**：非原生对话框是为了让"文件/文件夹二选一都能选"；文件夹导入不递归子目录、只导入图片。

### 5.10 图片与文件夹分开（v1.9，2026.10.5 23:30）

**用户原话**："把选择文件夹和选择图片的功能分开，回复原本的界面，'打开文件'按钮只负责选择图片，
不再需要导入文件夹的功能。图像源节点中图像来源加一条文件夹的词条，用来于只选择图片分开，
选择图片选项后图片路径为图片，选中文件后则可以选中整个文件夹。"

| 位置 | v1.8（被否） | v1.9（现在） |
|---|---|---|
| "打开文件"按钮 | 一个非原生对话框，既能选图片也能选文件夹 | **原生 `getOpenFileNames`**，只负责图片 / 视频（多选）；文件夹路径被忽略 |
| 图片源"浏览…" | 同上（二合一） | **按"图像来源"分开**：来源=图片 → 原生 `getOpenFileName`（选图片，路径=图片）；来源=文件夹 → 原生 `getExistingDirectory`（选文件夹，路径=该文件夹） |
| 图像来源下拉 | 图片 / 测试图 | **图片 / 文件夹 / 测试图**（路径标签：图片路径 → "路径"） |
| 文件夹来源的取图 | — | `first_image_in_folder()`：取文件夹里**按文件名排序的第一张**；点"浏览…"或执行后，整个文件夹的图片会静默进入图库（便于点缩略图切换） |
| 提示 | 已静默 | 保持静默（坏文件跳过、无任何弹窗） |

**验证**：26 项新断言全 PASS（原生对话框按来源分开、文件夹路径被"打开文件"忽略、文件夹来源取排序第一张
且逐像素一致、空文件夹/未填路径兜底、执行后整个文件夹进图库、静态检查不再出现 `DontUseNativeDialog`）；
八套回归合计 **302 项**全过；截图 `round6_source_folder_option.png`、`round6_folder_browse_main.png`、
`round6_folder_execute.png`。

### 5.11 窗口宽度与 ROI 缺省（v1.10，2026.10.6 00:04）

| 问题 | 真因 | 修法 |
|---|---|---|
| 取反窗口比别人宽（483 vs 340） | 取反没有可调参数，"运行参数"页只有一行长的灰字提示；**QLabel 的 sizeHint 按整行文字宽度算**，把整页顶宽（451 → 各页里最宽） | 文案缩短为"该模块没有可调参数" + `setWordWrap(True)` + 长说明移到 tooltip（tooltip 不参与布局）；该页 sizeHint 451 → **132**，窗口回到 340 |
| "ROI创建"缺省是"绘制" | `LineParamsDialog.__init__` 里写死 `roi_draw.setChecked(True)`；`_load_params` 与 `main.py::_resolve_roi` 的 `.get("roi_inherit", False)` 也都缺省"绘制" | 三处缺省全改成 **"继承上游"**（`_format_result_text` 的兜底一并改，保证日志会写"← 继承上游ROI框"）；存过 `roi_inherit: False` 的节点仍走"绘制"；上游没有可继承的框时自动退回本节点 ROI（不会 0 面积跳过） |

**验证**：14 项新断言全 PASS（各通用窗口宽度全 340、取反运行参数页 132、窗口默认选中继承上游、
缺省继承上游的 ROI 与日志、明确选绘制时用自己的 ROI、上游无框时退回整图、
真实按钮连续执行日志带继承提示）；九套回归合计 **316 项**全过；
截图 `round7_invert_window.png`、`round7_threshold_window.png`。

### 5.12 M2 第一阶段：图像列表工具栏与批量执行（v1.12，2026.10.6 13:50）

**控件**（main.ui 里摆好、`ImageGalleryWidget._build_toolbar()` 收编，**真源只有运行时那一套**）：

| objectName | 作用 |
|---|---|
| `gallery_toolbar` + `gallery_toolbar_layout` | 容器（`image_gallery` 上方；`verticalLayout_2` 的 stretch = `14,0,2,3`；布局四周留白 0、spacing 6） |
| `gallery_count_label` | "图像源 (n/N)"：导入 / 点选 / 增删时刷新 |
| `gallery_auto_switch` | **自动切换 = 状态**：打开后"连续执行"的范围变成整个列表 |
| `gallery_run_all` | **"运行全部" = 执行范围选择（v1.13 起它自己不执行）**：勾选 = 连续执行时跑整个列表；执行交给"单步执行 / 连续执行"（下拉里的"运行选中 / 停止"仍为占位） |
| `gallery_add_button` | ＋图片（复用"打开文件"：原生多选、只管图片/视频） |
| `gallery_add_folder_button` | ＋文件夹（原生 `getExistingDirectory` → 静默导入里面所有图片） |
| `gallery_delete_button` | 删除选中项：**连它的参数 / 结果 / 缩放一起清** |
| `gallery_collapse_button` | ∨ 折叠（**占位**，V2 再接） |

**执行语义（关键）**

- **执行范围（v1.13 定稿）**：勾了"自动切换"**或**勾了"运行全部" ⇒ "连续执行"跑整个列表；两个都不勾 ⇒ 只跑当前这一张。
  **"运行全部"自己不执行**（只做范围选择），执行只由"单步执行 / 连续执行"触发；
- 批量执行期间**把"自动切换"关掉 ⇒ 立刻停**；
- **批量执行每跑一张，都会把当前页的"图片源"节点同步到这一张**——流程里若有图片源节点，它才是那一轮的取图处，
  不同步就会出现"每张都在跑同一幅图"（v1.13 修的正是这个）；
- **单步执行永远只打当前图**（不受自动切换影响，保持调参调试语义）；
- 批量：**开始时清空日志**、之后**逐张累积**（本轮先不做分组标题）、单张出错**跳过继续**并写一行提示、
  结束写"运行全部结束：共执行 n/N 张"。

**每幅图 / 每帧的参数归属**

- **图片列表：每张图各自一份**（`params_per_image`，键 = **文件路径**）；没设过的用默认值 / 初始值；
- **同一段视频：整段共用一份**（沿用现成的 `VIDEO_ROI_KEY` 视频槽）⇒ 视频流里中途改参数，
  **后面的帧按改后的参数跑**。

**归档键改造（一起做了）**：`id(原图)` → **文件路径**（视频帧 → `视频路径#帧号`）；
影响 `current_image_key` / `params_per_image` / `result_cache` / `ImageGraphicsView._zoom_states`；
`.vfproj` 每个节点新增 `params_by_image`（只导出字符串键），加载时还原到 `params_per_image`。

**验证**：32 项新断言全 PASS（工具栏收编 `is` 同一控件、＋文件夹导入、运行全部逐张累积、
计数标签、归档键是路径、每图参数互不影响、自动切换只影响连续执行、中途关掉即停、
删除连参数结果一起清、方案 roundtrip 还原 `params_by_image`）；九套回归 **316 项**全过；
截图 `m2_toolbar_run_all.png`、`m2_auto_switch_off.png`。

### 5.13 目标3-M2 剩余任务的技术要求（v1.14，2026.10.6）

> 用户 2026.10.6 决定：**两个开关采用"方案 B"分工**，并把三个 V2 占位项**一起做完**；
> 里程碑重编号为 M1 图片源 / **M2 工具栏（本节）** / M3 视频流 / M4 相机源。

**一、两个开关的分工（方案 B——按"职责正交"拆开）**

| 控件 | 改后的职责 | 具体行为 |
|---|---|---|
| `gallery_run_all`（勾选） | **唯一的"范围"开关**（**它自己不执行**） | 勾 ⇒ "连续执行"跑**整个图像列表**；不勾 ⇒ 只跑当前这一张；**批量运行中取消勾选 ⇒ 立刻停（急停）** |
| `gallery_auto_switch`（勾选） | **执行时是否"跟随"**（退出范围判定） | 勾 ⇒ 批量执行时把**选中项**（列表高亮、"图像源 (n/N)"）跟着切到正在跑的那张；不勾 ⇒ 照样按顺序跑完，但**选中项不动** |
| 主界面"单步执行" | 不变 | 永远只跑当前选中的那一个节点 |
| `action_run_selected` | 菜单"运行选中" | **只跑当前选中的那一张**（不看多选）——即便"运行全部"勾着，也能一键只跑这一张 |
| `action_stop` | 菜单"停止" | 中断正在跑的批量：新增 `self._batch_stop` 由批量循环检查；停止后日志写一行"用户停止" |

**判定式**：由 `自动切换 or 运行全部` 改为**只看 `scope_all()`（即"运行全部"勾选）**；
"自动切换"不再参与范围判定，只决定"跟随"。

**二、三个 V2 占位项（本轮做完）**

1. **折叠 ∨**：`gallery_collapse_button` 勾选 ⇒ `image_gallery` 收起（85px → 约 24px，或隐藏列表只留工具栏一行）、
   按钮文字变 "∧"；取消 ⇒ 恢复 85px。状态**只存内存**（重启复位；以后要持久化再放进 `.vfproj` 的界面偏好）。
2. **"运行全部"的真下拉菜单**：运行时用代码 `tb.setMenu(menu)` 把 main.ui 里已有的
   `gallery_run_all_menu` 挂到 `gallery_run_all` 上（**QUiLoader 不会自动挂**，设计器里那个 `<addaction>` 只是占位），
   菜单项 = **运行选中 / 停止**。
3. **停止**：见上表（`self._batch_stop`）。

**三、验收要求**

① 用两张**均值明显不同**的图做**像素/均值断言**，证明批量真的在逐张换图（沿用 2026.10.6 的做法）；
② 全部走真实按钮 / 菜单项（点"运行全部"、"自动切换"、菜单"运行选中"、"停止"）；
③ **四个组合各断言一次**（运行全部勾/不勾 × 自动切换勾/不勾），行为必须可区分
（不勾"运行全部"时"自动切换"不应改变范围）；
④ 两条急停路径（取消勾选"运行全部"、菜单"停止"）都要能停下并写日志；
⑤ 折叠前后各一张截图；⑥ **九套回归 316 项不许破**；⑦ 写 `pyside6.txt` 日志 + 方案升版本 + 存快照。

**实施结果（v1.15，2026.10.6 21:49 已完成）**

- **方案 B 落地**：范围判定改成**只看 `scope_all()`**（`自动切换` 退出范围判定）；批量循环里
  "跟随" = `if gallery.auto_switch(): gallery.set_current_index(...)`；两条急停 = 循环每张之前检查
  `self._batch_stop`（菜单"停止"置位）与"中途取消勾选运行全部"（用 `started_with_scope` 判定）；
  停止时各写一行日志（"用户停止，批量执行中断" / "已取消"运行全部"，批量执行中断"）。
- **三个 V2 项**：折叠 ∨ 用 `gallery_list.setVisible(not checked)` 收起或展开、按钮文字切 "∨ / ∧"；
  `run_all_button.setMenu(gallery_run_all_menu)` 把设计器里那条菜单挂上（**QUiLoader 不会自动挂**），
  菜单项 = 运行选中 / 停止；`run_selected_image()` = 只跑当前选中的那一张
  （走 `current_index()` + `items()`——**不能调 `gallery.currentItem()`，那是 QListWidget 的方法，包装类没有**）。
- **验收**：新增用例 **20 项断言全 PASS**（四个组合各一次：范围✗/跟随✗ = 1 张、范围✓/跟随✗ = 2 张且选中项不动、
  范围✗/跟随✓ = **仍只 1 张**（自动切换不再决定范围）、范围✓/跟随✓ = 2 张且选中项跟到最后；
  两条急停各只跑 1 张并写日志；真下拉菜单与"运行选中"只跑 1 张；折叠 / 展开）；
  逐张换图仍用**均值断言**（A→≈212、B→≈53）；工具栏用例 34 项、上轮修复用例 14 项、
  **九套回归 316 项**全过；截图 `m2_collapse_off.png` / `m2_collapse_on.png`。

---

## 6. 事项四：参数校验

### 6.1 规则表

| 位置 | 规则 | 处理 |
|---|---|---|
| 直线 | Canny 低 < 高 | **自动交换** + 日志说明 |
| 直线 | `hough_threshold > 0`、`min_line_length > 0`、`max_line_gap >= 0` | 拦住 + 提示 |
| 圆 | `min_radius <= max_radius` | 自动交换 + 日志 |
| 圆 | `dp >= 1`、`min_dist > 0`、`param1/param2 > 0` | 拦住 + 提示 |
| 通用 | ROI `w > 0 and h > 0`（引擎已能兜住越界，但"填 0"要提示） | 拦住 + 提示 |
| 二值化 | 阈值 / 最大值在 0~255 | 控件已限范围；越界拦住 |
| 形态学 / 滤波 | 核大小必须是**奇数**且 1~31 | **自动取奇数** + 日志说明 |
| 图像源 | 文件路径存在；相机 id 可打开 | 拦住 + 提示 |

### 6.2 两层校验与策略（默认策略见第 9 节 d）

1. **窗口保存时**（`_validate_params()`，由 执行 / 连续执行 / 确定 触发）：
   - 能安全纠正的（Canny 高低互换、核大小取奇数）→ 自动改 + 写进日志；
   - 不能的 → `QMessageBox.warning` 逐条列出，**不保存、不执行**。
2. **引擎执行前**（`_execute_node` 里）：再查一次（防止方案文件里带着非法参数），非法时在"结果数据"列写"参数非法（xxx），已跳过本节点"，图像原样传给下游。

### 6.3 实现落点

- 规则写在 **`NodeSpec.validate(params) -> [str]`** 里（与 `param_specs` 放一起，避免散落在各窗口）；
- `LineParamsDialog` 增加 `_validate_params()` 抽象钩子（默认查 `get_spec(self.node.name).validate`），三个子窗口自动受益；
- 引擎侧：`_execute_node` 开头调用 `spec.validate(node.params)`，非空 → 走"跳过 + 日志"分支。

### 6.4 验收用例

- 每个规则各一条断言：非法输入 → 断言"被拦住"或"被自动纠正且值正确"；
- 方案文件里塞非法参数 → 加载后执行 → 断言日志含"参数非法"且图像原样透传。

---

## 7. 改动文件清单

| 文件 | 改动 | 事项 |
|---|---|---|
| `main.py` | **M1 已完成**：`save_project` / `save_project_as` / `_collect_project` / `_write_project_file` / `open_project` / `load_project` / `_build_project_model` / `_apply_project`（追加式）/ `_add_node_to_page` / `_add_edge_to_page` / `_on_node_moved` / `_open_node_dialog` / `_mark_dirty_if_params_changed` / `_confirm_close_flow_page`；菜单三项 + 顶部两个按钮接线。M2~M4 还要：双击路由改成"按 spec 决定窗口"、`_execute_node` 加校验兜底 | 1 / 2 / 3 / 4 |
| `FlowPages.py` | **M1 已完成**：`append_pages(titles)`、`mark_dirty` / `clear_dirty` / `mark_all_clean` / `has_dirty_pages`、`on_page_close_requested` 回调 | 1 |
| `main.ui` | **M1 已完成**：菜单"方案"（打开方案… / 保存方案 / 另存为…）+ 顶部 `save_project_button` / `open_project_button`。M2 还要：左侧树新增"处理"分组与算子项 | 1 / 2 / 3 |
| `NodeRegistry.py` | `NodeSpec` 增 `param_specs` / `validate`；新增 5 个处理类算子 + `图像源` 的 `run` / `format_result` / 参数表 | 2 / 3 / 4 |
| `GenericProcessDialog.py` | **新增**：按 `param_specs` 动态生成"运行参数"页 | 2 / 3 |
| `Detector.py` | 新增 5 个算子的 OpenCV 封装（invert / blur / threshold / morphology / edge） | 2 |
| `LineParamsDialog.py` | 加 `_validate_params()` 钩子；`tab_2` 里原有控件可隐藏以腾给动态控件 | 2 / 4 |
| `CircleParamsDialog.py` / `GrayParamsDialog.py` | 跟随基类（校验钩子）；灰度是否并入通用窗口待定 | 2 / 4 |
| `pyside6.txt` | 每次改动按项目格式追加日志；批次结束再补一份"批次4 整体总结" | 全程 |
| `E:\opencv_python_3_8\backups\` | 每次改动前建 `_backup_VisionFlowNoed_before_<改动>`，改完存 `_at_<时间>` | 全程 |

---

## 8. 实施顺序、里程碑与回退点

| 里程碑 | 内容 | 交付判定 | 回退点 |
|---|---|---|---|
| **M1 方案持久化 ✅ 已完成（2026.10.2）** | `append_pages` + `save/load_project` + 菜单 + 顶部两个按钮 + 关闭页面提醒保存 | 46 项 + 35 项无头冒烟全 PASS；坏文件不破坏现场；追加式加载不影响已有页面 | `before_project_persist`（第一版）/ `before_append_pages_and_buttons`（v1.1） |
| **M2 通用窗口 + 5 算子 ✅ 已完成（2026.10.3）** | `ProcessOps.py`（5 个算子 + 灰度迁移）、`NodeSpec.param_specs`、`GenericProcessDialog`、树三分组、双击路由 | 114 项无头冒烟全 PASS（参数表 / 控件生成 / 算子效果与对照实验 / 数据层不被污染 / 路由 / 树结构）+ 5 张界面截图 | `before_M2` / `at_20261003_2238` |
| **M3 图像源节点** | 新 spec + 引擎落点 + 参数表（含 file 类型） | 三种来源各跑通；不放它时行为不变 | `before_image_source` |
| **M4 参数校验** | `validate` 规则 + 窗口钩子 + 引擎兜底 | 规则逐条用例通过 | `before_validate` |
| **M5 收尾** | 树里未实现模块标注、批次总结日志、截图、最终备份 | 项目全景与日志齐全 | `at_<时间>` 快照 |

每步固定动作：**建 before 备份 → 改代码 → 验证四连 → 截图（涉及界面时）→ 写 pyside6.txt 日志 → 存 after 快照**。

---

## 9. 待拍板的决策

| 编号 | 问题 | 推荐做法 | 备选 |
|---|---|---|---|
| **a** | 方案文件里存哪些参数？ | 只存"当前图片那一份参数" + `last_image` | 先把 per-image 键从 `id(原图)` 改成文件名/路径，再存多图多套参数（额外一块工作） |
| **b** | 5 个算子的参数界面 | ✅ **已定（2026.10.3）：通用动态窗口**（`GenericProcessDialog` 已实现） | 每个算子单独 `.ui`（未采用） |
| **c** | "图像源"节点与全局图像源 | 并存（流程里放了才生效）——**待拍板** | 取代（老流程与老方案都要改） |
| **d** | 参数校验策略 | 能纠正的自动纠正 + 日志，不能的拦住——**待拍板** | 一律拦住、弹提示 |
| **e** | 附加问题 | ✅ **已定（2026.10.3）：灰度移到新的"处理"分组**（树已改成 处理 / 检测 / 识别） | 保持现状（未采用） |

---

## 10. 通用验证方案（每一步都要跑）

1. **验证四连**：`py_compile` 全部源文件 → `xml.etree` 解析 `.ui` → `QApplication([])` 后 import 全部模块并构造 `MainWindow` → 无头冒烟脚本（放 `%TEMP%`，跑完删）+ `findChild` 断言；
2. **界面看图**：`dialog.grab().save(png)` 后人工读图，**必须覆盖"内容最多"的状态**；同一状态单独起进程抓（切换状态后渲染会滞后一帧）；
3. **回归**：批次1/2/3 的关键行为不能被改坏——底图"点谁看谁"、ROI 继承两种来源、外扩、单步/连续日志 5 元组、越界 ROI 裁成 0 尺寸；
4. **日志**：按 `pyside6.txt` 既有格式逐条追加（日期时间行 + 存在问题/原因分析/修改/验证/遗留/后续待办，代码原样贴）；
5. **备份**：改动前 `before_*`、改动后 `at_*`，统一放 `E:\opencv_python_3_8\backups`。

---

## 11. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 方案加载到一半失败 | 旧流程没了、新流程不完整 | 校验阶段与"应用阶段"分离；校验全部通过才动 UI；应用阶段用 try/except + 兜底空页 |
| per-image 键是 `id(原图)` | 方案里的多图参数无意义 | 第一版只存当前参数 + `last_image`（决策 a） |
| 动态生成的参数控件在 Designer 里看不到 | 用户改不了、容易困惑 | 在日志与说明里写清楚；把控件名做成 `f"param_{key}"` 便于 `findChild`；必要时后续改成静态 `.ui` |
| 处理类算子就地改图 | 污染数据层（曾有绿线污染的教训） | 一律 `copy` 后再改；冒烟里断言"输入图未被改动" |
| 单通道图丢给下游 | downstream `cv2.line/circle` 抛异常 | 返回前统一 `cvtColor(GRAY2BGR)` |
| 图像源"文件模式"每帧解码 | 视频卡顿 | 按 `(path, mtime)` 缓存 |
| 树里 `name` 与注册表不一致 | 拖进去变成"模块未实现" | 加一条冒烟断言：树里每个叶子名都能 `get_spec()` 到（或明确标记为未实现） |
| 方案文件被手工改坏 | 打不开或行为怪 | 严格校验 + warnings 汇总 + 不破坏现场 |

---

## 12. 附：路径与资源索引

| 资源 | 路径 |
|---|---|
| 工程目录（也是 git 仓库根） | `E:\opencv_python_3_8\PySide\VisionFlowNoed` |
| 程序入口 | `main.py` + `main.ui`（工作目录必须是工程根：`QUiLoader` 用相对路径读 `.ui`） |
| 项目解释器 | `E:\opencv_python_3_8\.venv\Scripts\python.exe`（Python 3.8.10 + cv2 4.13.0 + PySide2） |
| 开发日志 | 工程内 `pyside6.txt`（用户也会亲手编辑，追加前先重读） |
| 测试图像 | 工程内 `image\`（lena.png / coins.png / HoughLines.jpg / mulballs.mp4 等） |
| 备份与快照 | `E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_*` |
| 界面预览截图 | 工程内 `_ui_preview\`（灰度窗口三种状态 + 直线窗口两种模式） |
| 记忆库 | 工程内 `.dsh-meow\memory.db` |
23. **视频源 P0 收尾（v1.19，2026.10.7）**：① 视频帧的**结果缓存键 = `视频路径#帧号`**（画面缩放键仍走
    `_display_key_of()` 的 `"video:路径"`，两者刻意分开）；② **参数整段共用一份**：视频执行完把当前参数
    存进"视频槽"（`VIDEO_ROI_KEY`），换图再切回来不会丢；③ **播放时不刷执行日志**（`_video_log_throttle`），
    进度改用工具栏标签显示 `视频帧 (n/N)`；④ 修正几处测试断言写法。

---

## 九、想法（未开发）—— 以后要补充开发时从这里挑

> 说明：以下都**还没有开发**，只是用户提过 / 讨论过的想法，按主题罗列，供以后排期。

### 9.1 输出节点（用户 2026.10.6 提的想法，**原话**）
"我打算在完成摄像头节点后再添加一个输出节点，一般放到流程的最后，专门用于保存运行流程图后的
图片/视频/摄像头拍摄到的画面。"
—— 即在 M4 相机源之后，新增一个"输出"类节点：接在流程末端，把**运行后的图像 / 视频 / 摄像头画面**
保存下来（图片格式、视频编码、保存目录、是否覆盖等参数走 `param_specs`）。

### 9.2 视频源：按帧间隔检测（用户 2026.10.6 提的想法）
在视频源节点的参数窗口里增加"**每 N 帧检测一次**"——可以设置每两帧检测一次，不用每一帧都检测。
（实现要点：`frame_index += step`；`step` 参数加入 `VIDEO_SPECS`；播放时的定时器间隔按 `1000/fps*step` 调整；
检测结果按"实际检测到的那一帧"记键。）

### 9.3 视频源：播放与查看体验
播放 / 暂停按钮（现在只有"停止"）；帧滑杆 / 进度条（可拖到任意帧）；单帧步进与后退（←/→ 键）；
播放速度 0.5x / 1x / 2x；"跳到指定帧"输入框；**视频信息显示**（分辨率 / 总帧数 / 帧率 / 时长）。

### 9.4 视频源：结果与导出
整段检测结果**汇总表 + 导出 CSV**（哪一帧检出什么）；导出"处理后的视频"（`cv2.VideoWriter`）；
把当前帧 / 每 N 帧抽进图像列表；导出当前帧为 PNG。

### 9.5 视频源：区间与来源
区间播放（起止帧）；"来源"扩展（本地文件 / 网络流 rtsp、http / 一个文件夹里的视频列表）；
多段视频播放列表；网络流与 M4 相机源合并成"**实时来源**"抽象（相机 = 无界流、视频 = 有界流）。

### 9.6 视频源：性能与稳定
顺序读取优化（现在每格都 `cap.set(POS_FRAMES)` + `read()`，顺序播放应连续 read、只在跳帧时 seek）；
`_VIDEO_CACHE` 加 LRU 并 `release()`（现在只增不减）；大分辨率播放时**预览降采样**；
播放与编辑的并发保护（播放中删节点 / 换页 / 改路径的收尾）；明确"播放时忽略 `auto_next`"（否则会卡住）。

### 9.7 视频源：ROI 在帧间的行为
现在是"每帧独立、轴对齐"；可加"**锁定 ROI**（整段共用同一个框）"与"跟随结果"两档。
