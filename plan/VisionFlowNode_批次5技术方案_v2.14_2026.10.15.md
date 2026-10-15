# VisionFlowNode 批次5 技术方案（重构）


## 修改代码 / 文件的规矩（沿用批次4 口径；用户 2026.10.13 起，**必须遵守**）

1. **改代码前先备份代码** —— 把要改的代码文件复制到 `E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_before_<说明>\`；改完再存一份 `_at_<yyyyMMdd_HHmm>` 快照（快照含 `plan\`、`tests\` 各一份）。
2. **改技术文档前先备份该技术文档** —— 同样先把这份文档复制到 `E:\opencv_python_3_8\backups\`；改完再把新版存一份带版本号的快照（本方案每改一版都换版本号、旧版留档）。
3. **改完写开发日志** —— 写进 `plan\pyside6_开发日志.md`（markdown 版；`pyside6.txt` 已冻结、不再改动）。格式 = 标题（`## 日期 批次N目标M-MZ 时间`）+「存在问题 / 原因分析 / 修改 / 验证 / 遗留」；**标题命名规则写在日志最开头**，写之前先看那几行。
4. **三份文档继续冻结**：《VisionFlowNode 代码说明书》《VisionFlowNode 项目技术文档》《VisionFlowNode 用户手册》 —— **只有用户明确要求时才修改**，而且**版本号不动**（批次5 打包、批次6 开工之后才改版号）。用户说"**更新技术文档**"时，**批次5 期间默认只更新本方案这一份**。
5. **做批次5 时以本方案为主**：《批次4 技术方案》（v1.53）**已冻结**（2026.10.13，批次4 全部收口），只作历史参考；《项目技术文档》只作参考。
6. ★ **重构类的硬判据（本批次每一小步都要过）**：**行为零变化 + 门禁全部通过 + 界面零变化**；改完要用**改前快照**跑同一套用例做对照，失败项要逐条分类（是"老用例在描述旧行为"还是真回归）。
7. **门禁与备份的位置**：门禁用例在**工程内 `temp\`**（一键跑 `temp\dsh_run_all_checks.py`，当前 **37 套 861 项**；目标1 之后变成 `tests\run_all_checks.py`）；备份与截图在**工程外** `E:\opencv_python_3_8\backups`（**不上传 GitHub**）；**git 一律不碰** —— 提交节奏由用户掌握。

---

| 项 | 内容 |
|---|---|
| 文档版本 | **v1.9**（v1.0 新建；v1.1 于 2026.10.14：节点错误态图标移出批次5、并入批次6，新增 §十二《想法（未开发）》；v1.2 于 2026.10.14：修净标题/正文里漏改的 M 编号；v1.3 于 2026.10.14：把 M1~M4 直接改成"目标1~目标4"；v1.4 于 2026.10.14：批次4 已提交 GitHub、写入仓库地址、收录参考项目目录分类；v1.5 于 2026.10.14：批次5 目标1（目录重构）落地 ✅；v1.6 于 2026.10.14：目标1 补做 —— 直线 / 圆各成一个节点文件；v1.7 于 2026.10.14：目标1 第二轮 —— `ops/` 按"树分组"重排、直线/圆 改名、`main.ui` 树新增「颜色处理」组、PyCharm 红线解法入档；v1.8 于 2026.10.14：目标1 第三轮 —— `ops/source/` 拆成 3 个节点文件、`main.ui` 把"检测"+"识别"合并成「检测识别」；**v1.9 于 2026.10.15：目标1 收口 —— §11.3 门禁口径改 `tests\`、新增 §4.5（落地后的目录现状速查）与 §4.6（节点文件为什么用函数而不是类）、《项目技术文档》事实同步**；**v2.0 于 2026.10.15：批次5 目标2「拆 `MainWindow`」落地 ✅ —— 三批（+ 第 0 步备份 / 基线）把 117 个方法里的 **90 个**搬进 `core/flow_engine.py` · `core/project_store.py` · `core/param_store.py` + `services/{camera,video,gallery}_service.py`，`main.py` **3327 → 888 行**；弹窗出口收口成 5 个薄壳 `_warn` / `_info` / `_ask_open_path` / `_ask_save_path` / `_ask_dir`；新增门禁用例 `tests\dsh_t5g2_api_check.py`（8 项，把"接口面零变化"钉死）⇒ 门禁口径 **37 套 861 项 → 38 套 870 项**，`dsh_doc_consistency_check` 的套数口径升级为"冻结文档只增不减 + 现行方案精确相等"，`dsh_run_all_checks.py` 自己兜住 `QT_QPA_FONTDIR`；界面零变化 = 改前 / 改后截图 **sha256 完全相同**；详见 §5.4~§5.6**；**v2.1 于 2026.10.15：目标2 收尾（用户 2026.10.15 点选 a+b+c）—— ① 清掉 `main.py` 里 17 个"只被搬走的方法用过"的 import；② 修掉 `core/ → widgets/` 倒挂（4 处 `isinstance(binding, NodeItem)` → 新增 `core/NodeRegistry.py::is_bound_node()`）；③ §4.5 目录速查同步到目标2 之后；④ **PyCharm 静态警告按 A 方案"只登记、不改代码"**（新增 §11.6：实测数据 + 排查 / 排除步骤）。★ **收尾踩了一个坑**：我按"没人 import 了"把 `KIND_SOURCE` / `result_bbox` 也删掉 ⇒ **3 套用例直接 `AttributeError`，门禁当场抓出**（`dsh_source_check` / `dsh_m3_video_check` / `dsh_m4_camera_check`），已恢复成"**故意的再导出**"（与 `VIDEO_ROI_KEY` / `LOG_ERROR_MARK` 同类，共 4 个，别再删）；`main.py` 888 → **885 行**，门禁仍 **38 套 870 项全绿** + 界面截图 sha256 仍完全相同**；**v2.2 于 2026.10.15：按用户要求"把现在的目录放到技术文档的批次5目标2中" + "全部完成则总结并更新修改文档 / 技术文档" —— 新增 §5.7《目标2 落地后的目录（现在的真实目录，含每个文件的行数）》与 §5.8《完工判定（✅ 目标2 已完工）》；开发日志同日写《总结：批次5 目标2「拆 `MainWindow`」整体总结》**；**v2.3 于 2026.10.15：批次5 目标3「执行线程化」落地 ✅ —— 采用"分片执行"（一张图一个分片、片之间 `QTimer.singleShot(0, …)` 让出事件循环），`services/gallery_service.py::run_all_images` 从同步 for 改成状态机（+ `_batch_step` / `_batch_finish` / `_batch_state`），**不引入线程**；判据 = 不阻塞 + 可取消 + 与串行逐像素一致 + 界面零变化；新增门禁用例 `tests\dsh_t5g3_batch_check.py`（25 项）⇒ 门禁口径 **38 套 870 项 → 39 套 895 项**；`dsh_m2_v5_check` 因"分片是异步的"补了 `wait_batch()` 等待（判据一条没改）；实测（用户给的 `data` 目录最大 12 张 + 重流程）单张最慢 28.1 ms、取消延迟 6.9 ms、同步对照事件循环 0 次 ⇒ **不上真线程化**；§六 从"初步设计"改写为"已落地"（含诊断 / 改法 / 实测 / 判据 / 遗留），详见 §六**；**v2.4 于 2026.10.15：目标3 收尾 —— 按用户"修改代码，按照 B′ 做"落地【宿主契约 `MainHost`】**：新增 `core/host_contract.py`（104 行，其中 65 行声明 = 25 个状态字段 + 40 个跨 Mixin 方法；**运行时是空类**、清单由脚本按实测算出），6 个 Mixin 各加 1 个 `MainHost` 基类（真实继承空类，PyCharm 100% 认），新增门禁用例 `tests\dsh_t5g3_host_check.py`（5 项防腐化）⇒ 门禁 **39 套 895 项 → 40 套 900 项**；§11.6 从"只登记（A）"改写为"B′ 根治（含数字纠偏：需要声明的是 65 个名字、不是 87）"，§6.5 补第 ④ 条；⚠️ PyCharm 里的归零需用户人工确认**；**v2.5 于 2026.10.15：修正「自动切换」的语义（用户报的问题：不勾也会自动播放处理后的图片）** —— 用户原话"我原本是设计只有选择了「自动切换」按钮才会在运行时自动切换画布的图片，将处理后的图片从头播放到尾……修改代码，重新实现我原本的这个功能"；**根因交代**：这个行为以前就存在（每张都无条件刷画布、跑完还原），只是**改前事件循环被占死、Qt 重绘不了所以看不见**，**目标3 让出事件循环才把它暴露出来**；改法 = `_execute_static` 新增 `show=True` 参数（`False` ⇒ 只算不显示）+ `_batch_step` 传 `show=gallery.auto_switch()` + 连带改 2 条写死签名的用例桩函数（收 `**kwargs`）⇒ 门禁 **40 套 900 项 → 40 套 904 项**（新用例 ⑩ 4 项：不勾期间画布 0 次刷新 / 整批只兜底还原 1 次 / 图照样都算 / 勾上则每张都刷）；新增 **§6.6** 记录根因与判据**；**v2.6 于 2026.10.15：再修正「自动切换」—— 让它在批量开始时"定格"**（用户第二次报："不开启自动切换运行连续执行后，再打开自动切换、没有再点执行，画布上的内容会自动播放到最后"）；**实测排查**：拨开关本身**不会显示任何东西**（`auto_switch_changed` 信号全工程无人监听；换图只走用户真点图库的 `itemClicked`）⇒ 现象只可能发生在**批量还在跑**时；**真根因** = §6.6 里 `_batch_step` 每片都**重读**开关 ⇒ 中途拨上就"半途跟随"、收尾又因开关已 ON 而**不还原** ⇒ 停在最后一张；**改法** = `_batch_state["follow"]` 在批开始时快照，`_batch_step`（切选中项 + `show`）与 `_batch_finish`（要不要还原）都改用它 + 新增薄处理器 `_on_auto_switch_changed`（批量进行中拨动 ⇒ 一行短提示，`main.py` 接线 `auto_switch_changed`）⇒ 门禁 **40 套 904 项 → 40 套 908 项**（新用例 ⑪ 4 项）；新增 **§6.7** 记录根因与判据**；**v2.7 于 2026.10.15：目标3 验收收口**（用户："**批次5目标3以验收**，现在给我总结一下批次5目标3做的内容，并更新修改日志和技术文档"）—— §六 顶部加《✅ 验收记录》（含"PyCharm 归零待人工看一眼"这一项悬留）；头部"当前状态"改标 **目标3 ✅ 已验收**、版本号从 v2.5 补正到 **v2.7**（v2.6 那轮漏改了这一行）；开发日志同日写《总结：批次5 目标3「执行批量化（分片执行）+「自动切换」语义修正」整体总结》**；**v2.8 于 2026.10.15：目标4 方案定稿 + 控件落位（用户拍板七条）** —— ① 缓存上限 = **内存 256 MB 为主 + 条数 400 硬顶**；② **视频序列帧单独分池**；③ 撤销范围 = **结构 + 参数 + 页面 + 节点拖动**（不含图库）；④ 控件 = **菜单「编辑」+ 顶部两个按钮**（甲+乙）；⑤ **快捷键先不做**（体系化做，入档 §12.3）；⑥ 栈上限 **50**；⑦ 清栈 = 换页 / 载入方案 / 新建项目 / 删除页面。**§七 从"初步设计"整节改写为"方案已定"**（7.1 缓存 LRU：现状三毛病 + 实测内存 66 条 62.4 MB / 单条最大 5.72 MB + "继续用 dict、只改淘汰逻辑"的实现决定 + **"真 LRU 判别"判据** / 7.2 撤销重做：入口清点 + 落点 `core/commands.py` + `services/undo_service.py` + **三个坑** / 7.3 日志策略：**追加不清空 + 补 `scrollToBottom()`**（实测全工程没有自动滚动）/ 7.4 三批动手顺序）；§十 待拍板第 2、3 项标"已定"；**§12.3 新增《快捷键体系》想法**；`main.ui` 加「编辑」菜单并统一命名（`menu_edit` / `action_undo` / `action_redo` / `btn_undo` / `btn_redo`，四个控件初始 `enabled=false`）；门禁仍 **40 套 908 项全绿****；**v2.9 于 2026.10.15：目标4 落地 3 批（缓存 LRU + 撤销/重做 + 参数/拖动）** —— 用户："**接下来修改代码实现批次5目标4的内容**"。① **新增 `core/result_cache.py`**（两池 LRU：静态 400 条/256 MB + 视频序列 120 条/64 MB；命中即 `touch`、写入即淘汰）⇒ 改 `flow_engine`（并**发现旧上限只写在视频分支里**：静态图批量跑原来根本没上限）+ 日志两处补 `scrollToBottom()`；② **新增 `core/commands.py`**（零 Qt：Command + Add/Remove Node/Edge + UndoStack，回调通知）+ **新增 `services/undo_service.py`**（`UndoMixin` = **第 7 个 Mixin**；`_UndoContext` 承担"命令↔流程图"的翻译）⇒ `main.py` 四个改动入口各记一条 + `_init_undo()` + **换页清栈**；`core/host_contract.py` 按新 Mixin 重新生成（仍 65 个名字）、`dsh_t5g2_api_check` 白名单 +7、`dsh_t5g3_host_check` 改 7 个 Mixin；③ **参数修改**（`SetParamsCommand`，钩在 `_mark_dirty_if_params_changed`）+ **节点拖动**（`MoveNodeCommand` + 400 ms 去抖 ⇒ 一次拖动一条命令 + 建节点/绑页时登记坐标基准）；**新增两套用例 `dsh_t5g4_cache_check.py`（13 项）/ `dsh_t5g4_undo_check.py`（29 项）** ⇒ 门禁 **40 套 908 项 → 42 套 950 项**；**遗留：页面新建/删除的撤销**（设计见 §7.6）+ 快捷键（§12.3）**；**v2.10 于 2026.10.15：修掉撤销/重做的两个 bug（命令改存 uid）** —— 用户实测报："**全部撤销后再一步一步按重做，节点和线并不是连在一起的**"+"**撤销按钮已经灰了，但图上还存在灰度节点**"；**同一根因** = 命令里存的是 Qt 对象引用，撤销销毁 / 重做重建后引用失效（前者让 `EdgeItem` 拿到死对象 ⇒ 线飘；后者让 `delete_flow_node` 撞上 `if node not in self.flow_nodes: return` ⇒ 删了个寂寞、栈却弹空 ⇒ 按钮灰了节点还在）；**改法 = "身份连续"**：节点/连线各发 **uid**、命令只存 uid、执行时 `ctx.resolve(uid)` 取活对象、重建沿用同一 uid；`resolve()` 两层探活（在不在 `flow_nodes` 里 + C++ 是否已销毁）+ 删除类命令先 `forget(uid)` + `undo/redo` 抽 `_run_stack_step`（挡记录 + 异常兜底）；**新增 §7.7** 记录机制与回归断言（⑮⑯ 共 +10 项，含"线两端误差 < 1.5px"）⇒ 门禁 **42 套 950 项 → 42 套 960 项**；`dsh_t5g2_api_check` 白名单 +1（`_run_stack_step`）**；**v2.11 于 2026.10.15：修「改参数撤销不到位」（按图片恢复）** —— 用户实测报："**我一直撤销……但是参数还是没有回到参数值，而是显示修改后的值**；重新运行程序就没有这个问题了"；**根因** = 运行参数是**按图片分别存档**的（`params_per_image`），而 v2.10 的 `apply_params` 只改"当前那张图"的状态 ⇒ "A 图改完 → 切到 B 图 → 撤销 → 切回 A 图"时 A 的存档里还是改后的值，`_load_node_params` 又把它载回去（"重启就没事"是因为存档只在内存里）；**改法** = `SetParamsCommand` 带 **`image_key`**，`apply_params(uid, snapshot, image_key)` 只在"就是当前图"时改 `node.params`、否则**只改那张图的存档**（流程级节点不写槽、空快照按约定销槽）；`main.py::_open_node_dialog` 捕获 `before_key` 传进命令；**新增 §7.8**（含修前/修后的复现数据）与回归断言 ⑰（3 项）⇒ 门禁 **42 套 960 项 → 42 套 963 项****；**v2.12 于 2026.10.15：撤销栈改成"每页一条"（修"换页后撤销失效"）+ 页面撤销技术要求入档《想法》** —— 用户口径："**页面新建/删除的撤销我不打算做，可以把技术要求写到《想法》里面**"；"**在一个页面中画好流程图后再切到另一个页面画流程图，然后回到第一个页面后撤销按钮失去了作用**……**修复这个问题**"；"**对于导入的流程图，设置撤销最多只能撤销到导入时，即以刚导入时为基准，修改后才能撤销/重写**"；**根因** = v2.10 之前那条拍板"清栈时机 = 换页"（`_on_flow_page_switched` 开头 `stack.clear()`）；**改法** = `self._undo_stacks`（页 key → 该页自己的栈）+ `_stack_for()` / `_bind_undo_stack_for_page()`（换页只**切**栈、不 clear，并丢掉已删页的栈）+ 占位栈阶段用 `getattr` 取控件；**导入即基准**无需额外代码（`_apply_project` 不经过记录入口 + 新页栈本来就空）；新增 **§7.9**（含判据）与 **§12.5《页面新建 / 删除的撤销》**（技术要求：行为 / 四处落点 / 五个必防点 / 判据 / 工作量；原 §12.5 顺延为 §12.6）；回归断言 ⑦ 改写 6 项 + 新增 ⑱ 4 项 ⇒ 门禁 **42 套 963 项 → 42 套 972 项****；**v2.13 于 2026.10.15：目标4 收口**（用户："**给我总结一下批次5目标4所完成的内容，并完成日志和技术文档的修改**"）—— §七 顶部新增《✅ 目标4 交付记录》（交付内容 = 三批 + 四轮修正 + 控件落位；用户两次追加口径；明确不做的两项；判据与结果 = 两套新用例 13 + 51 项全过、门禁 42 套 972 项全绿、界面零变化；交付后残留 = 一条待补的界面证据图）；拍板第 ⑦ 条标注已被 §7.9 取代；头部"当前状态"改标 **目标4 ✅ 已落地并收口**；开发日志同日写《总结：批次5 目标4「缓存上限 LRU + 撤销 / 重做」整体总结》**；**v2.14 于 2026.10.15：按用户要求"**都以完成，把目标2和目标4也打上勾**" —— §3《目标表》补上目标2 / 目标4 的 ✅ 并把完成情况写清**（目标2：三批 + 收尾，`main.py` **3327 → 885 行**、6 个 Mixin、弹窗出口 5 个薄壳、门禁 37 套 861 → 38 套 870 项、界面 sha256 零变化；目标4：3 批 + 四轮修正并收口，新增 `core/result_cache.py` / `core/commands.py` / `services/undo_service.py`（第 7 个 Mixin），用例 13 + 51 项，门禁 40 套 908 → **42 套 972 项**）；**纯文档维护、口径与代码均未变****；历次修订见文末"变更说明"） |
| 撰写日期 | 2026.10.14 起（历次修订见文末"变更说明"） |
| 适用工程 | `E:\opencv_python_3_8\PySide\VisionFlowNoed`（目录名少个 d，也是 git 根）；**GitHub 仓库 = https://github.com/OvO641651/VisionFlow_Node** |
| 代码基线 | 批次4 全部收口后的工程（回退点 = `_backup_VisionFlowNoed_at_20261013_1216`）；**批次4 目标5-M3 / M4 已完成并已提交到 GitHub** —— 仓库地址见 §11.4 |
| 门禁基线 | **42 套 972 项断言全过**（一键跑 = `tests\dsh_run_all_checks.py`；★ 2026.10.15 目标2 起**脚本自己兜住** `QT_QPA_FONTDIR=C:\Windows\Fonts` —— 不设它时"参数窗口宽度"那 4 项会假失败；详细清单见 §11.3） |
| 当前状态 | **批次5 进行中**：本方案 **v2.13**；**目标1 ✅ / 目标2 ✅ / 目标3 ✅ 已验收**；**目标4「缓存上限 LRU + 撤销 / 重做」✅ 已落地并收口（2026.10.15）** —— 三批（缓存两池 LRU + 日志自动滚动 · 撤销/重做骨架 · 参数 + 拖动）+ 四轮修正（§7.7 命令改存 uid · §7.8 参数按图片恢复 · §7.9 撤销栈每页一条 · §7.3 日志策略）+ 控件落位（「编辑」菜单 + 两按钮）；**明确不做**：页面新建/删除的撤销（技术要求入档 **§12.5**）· 快捷键（**§12.3**，后续体系化）；门禁 **42 套 972 项全绿**；**批次6 = UI 界面大改**（节点修改 / 预览控件 / 帮助页 / 其它）未排期 |
| 说明 | ★ 本方案是**批次5 的口径真源**，目录 / 术语 / 判据一律以本文为准。**归档约定**：本文件只放工程 `plan\`；每改一版先在 `E:\opencv_python_3_8\backups` 存一份带版本号的快照。 |

---


## 一、为什么做批次5：现状体检（数据都是实测）

| 项 | 现状（2026.10.13 实测） | 为什么要动 |
|---|---|---|
| 文件布局 | **21 个文件全平铺在工程根**（18 个 `.py` + 3 个 `.ui`） | "一个节点一个文件"之后文件只会更多；从目录看不出"哪块管什么" |
| `main.py` | **3327 行 / 117 个方法 / 54 个状态字段**（另 4 个模块级函数） | 主窗口 + 数据流引擎 + 方案持久化 + 参数归档 + 相机 / 视频 / 图库全挤在一个类里 |
| 工程内 `import` | **38 条**（都是平铺导入） | 挪文件要一起改，是**目标1**的主要工作量 |
| `QUiLoader` 相对路径 | **3 处**：`main.py` → `main.ui` / `SetCameraID.ui`，`LineParamsDialog.py` → `LineParamsDialog.ui` | 它按**当前工作目录**解析 ⇒ `.ui` 一挪目录就必须改成显式路径，否则启动即崩 |
| 用例对 `main.py` 的直连 | **29 个方法被 40 套门禁用例直接以 `w.方法名(...)` 调用**（`add_flow_node` / `_execute_node` / `_run_flow_pipeline` / `_show_static_image` / `save_project` / `_video_tick` …） | 决定了"拆 `MainWindow` 必须先走 Mixin"（见 §五） |
| 执行模型 | 在**界面线程里同步跑**（点「停止」只能急停） | 大批量跑图会"卡"到跑完；没有进度、不能取消 —— ★ **2026.10.15 目标3 已改**："运行全部"改成**分片执行**（界面不卡、能取消），详见 §六 |
| 结果缓存 | **没有容量上限** | 长时间大量跑图会占内存 |
| 编辑能力 | **没有撤销 / 重做**，没有快捷键 | 改流程只能删了重来 |
| 节点状态 | 只有**执行日志那一行红字**，节点本身没有状态显示 | 用户要 VM 式"节点左边图标，出错变红"—— **已移到批次6 与 UI 大改一起做**（见 §十二《想法（未开发）》） |

> ★ **2026.10.15 复核纠偏**（上表是 2026.10.13 的实测，两处数字后来核过）：`main.py` 是 **53 个 `__init__` 赋值字段 + 3 个类属性 = 56 个宿主状态**（不是 54）；用例对 `main.py` 的直连是 **27 个方法 / 35 套用例 `import main as m`**（不是"29 个方法 × 40 套"）。详见 §5.2 / §5.6。

> 这些都是《批次4 技术方案》§9.2 里列的**架构债**；批次4 全部收口、备份链完整，才有条件动它们（用户口径："重构类，等前面稳定、且有备份 / 版本控制之后再做"）。

---


## 二、总目标与验收方式

**总目标**：在**不改变任何用户可见行为**的前提下，把工程从"单文件大杂烩"整理成"分层 + 分类清晰"的骨架，并补上三项长期缺的能力（**执行线程化 / 缓存上限 / 撤销重做**）。

**四条铁律（每一小步都要过）**：

1. **行为零变化**（重构步）：门禁 **37 套 861 项全绿**（之后只增不减）；
2. **界面零变化**：改完 `grab()` 抓图与改前对照（对照集 = `backups\_ui_preview\截图索引.md` 里已登记的 73 张）；
3. **先备份、改完写日志**（见开头规矩）；
4. **目标3 / 目标4 属于"新增能力"，不算零变化**（**目标1 / 目标2 是纯重构，必须零变化**）—— 按各自判据验收，并且**先出最小可用第一版**，后续再分批扩展（用户一贯的工作方式）。

**分批验收**（沿用用户 2026.10.7 给的方式表）：批次5 = 重构类 ⇒ 每个子里程碑做完**单独给验收点**，用户逐个过；**整体总结只在用户要求（验收）时才写**。

---


## 三、批次5 的目标划分（用户 2026.10.13 已拍板；2026.10.14 编号改为"目标"）

> **结构（沿用批次4 的编号习惯）**：**批次5 → 目标1 ~ 目标4**（本批次**不再分 M 层** —— 一个目标就是一件事）；日志条目标题按 **`## 日期 批次5目标1 时间`** 这样写（批次4 是 `批次4目标5-M3` 那种形式，**只有"目标下面再分 M"时才带 `-MZ`**）。**批次6 也照此办**（`批次6 目标1~目标4`，见 §十二）。

| 目标 | 内容 | 硬判据 | 主要影响面 |
|---|---|---|---|
| **目标1** ✅ | **目录重构** + **37 套门禁用例从 `temp\` 迁到 `tests\`**（2026.10.14 完成，见 §4.4） | **37 套 861 项全绿 + 界面零变化** ✅ | 41 处代码 import + 用例/工具 import / 1 处 `.ui` 路径 / 用例路径 / 文档路径 |
| **目标2** ✅ | **拆 `MainWindow`**（**先用 Mixin**；2026.10.15 三批 + 收尾，见 §5.4~§5.8） | 行为零变化 + 用例全绿 + **界面零变化**（截图 sha256 相同）✅ | 新增 6 个 Mixin 文件；`main.py` **3327 → 885 行**；弹窗出口收成 5 个薄壳；门禁 **37 套 861 项 → 38 套 870 项** |
| **目标3** ✅ | **执行批量化（"运行全部"分片执行；**不引入线程**） | **不阻塞**（调用即返回）+ **可取消**（含中途取消勾选）+ 结果与串行**逐像素一致** + **界面零变化** | `services/gallery_service.py`（`run_all_images` → 分片状态机 + `_batch_step` / `_batch_finish`）· `main.py`（新增 `_batch_state`）· 新增用例 `dsh_t5g3_batch_check.py` |
| **目标4** ✅ | **结果缓存上限（LRU）+ 撤销 / 重做（命令模式）**（2026.10.15 落地 3 批 + 四轮修正并收口，见 §七 顶部《✅ 交付记录》） | **缓存上限断言**（条数 + 字节；含"真 LRU 判别"）✅ + **撤销 / 重做往返断言** ✅ —— 新增用例 `dsh_t5g4_cache_check`（13 项）+ `dsh_t5g4_undo_check`（51 项） | 新增 `core/result_cache.py` · `core/commands.py` · `services/undo_service.py`（**第 7 个 Mixin**）· `main.ui`（「编辑」菜单 + 两按钮）· 两个测试文件；门禁 **40 套 908 项 → 42 套 972 项** |

**顺序理由**：**目标1** 必须最先（后面每一项都要动 import / 路径）；**目标2（拆 `MainWindow`）最大、必须在目标1 之后**；**目标3 / 目标4 都依赖目标2 拆出来的引擎接口**。

> ★ **2026.10.14 调整**：原先排在批次5 的 **"节点错误态图标"已移出** —— 用户决定把 **UI 界面大改**（**节点的修改 / 流程图预览控件 / 帮助页面** 等）**集中到批次6** 做（原话："我打算在后续的批次6再把 ui 界面进行大改，包括节点的修改，添加流程图预览控件，帮助页面等内容，由于修改的内容比较多，所以设置一个批次6来实现"）⇒ 详见 **§十二《想法（未开发）》**。

---


## 四、批次5 目标1：目录重构（已拍板，2026.10.13）

### 4.1 目标目录（**2026.10.14 第二轮按"树分组"重排后的拍板版**）

```
ops/                                 算子（**一个节点一个文件**）
├── source/   采集 3 个节点，**各一个文件**：
│             ImageSourceOps.py（图片源）· VideoSourceOps.py（视频源）· CameraSourceOps.py（相机源）
├── sink/     输出：OutputOps.py（输出图像）                     ← 输出类不动
├── process/  处理 6 个节点，**各一个文件**：
│             GrayOps.py（灰度）· InvertOps.py（取反）· BlurOps.py（滤波）·
│             ThresholdOps.py（二值化）· MorphologyOps.py（形态学）· EdgeExtractOps.py（边缘提取）
├── detect/   检测 3 个节点：LineDetectOps.py（**直线识别**）· CircleDetectOps.py（**圆识别**）·
│             FaceDetectOps.py（人脸识别）
└── color/    **新建的"颜色处理"这一类**：ColorExtractOps.py（颜色提取）
              （2026.10.14 用户：这个文件夹后续放颜色分割 / 颜色转换等"颜色处理"的内容）

core/                                零 GUI 依赖的纯逻辑
├── NodeRegistry.py                  登记 + 查询 + result_bbox（各节点的声明由 ops/* 下的文件导出）
├── ParamRules.py · ImageIO.py       参数校验零件 · 图片读写（中文路径）
├── ImageOps.py                      **处理类公共零件**：to_bgr / apply_to_roi / odd_kernel
└── Detector.py                      **兼容门面**：DetectorShape 转发 + make_test_image

ui/     参数窗口与对话框（含同目录的 LineParamsDialog.ui）      widgets/  画布 / 页签 / 显示 / 图库
tests/  37 套门禁用例 + dsh_run_all_checks.py（进 git）        temp/     本机工具（不进 git）
```

> **图例**：★ = 批次5 要新建 / 迁移的；**规划中的文件刻意不写 `.py` 后缀**（免与现有文件混淆）；**上面这版已经落地**（见 §4.4），落地后的真实文件名就是树里写的那些。
> **文件名保持现状** —— 不改名、不改大小写风格（老文件仍 `CamelCase`，目标2 新建的拆出文件用 `snake_case`）、只挪目录。
>
> **★ 2026.10.14 第二轮（用户拍板）**：`ops/` 改成**按"树分组"分** —— `source/`（采集 3）· `sink/`（输出 1，两个都不动）· `process/`（处理 6，**一个节点一个文件**）· `detect/`（检测 3）· **`color/`（"颜色处理"这一类，新建）**；**暂不分二级目录**（用户："后续节点多了我再修改整理，现在还不需要分二级目录"）；**直线 / 圆 改名「直线识别」/「圆识别」**，`main.ui` 树控件同步（新增顶层组「颜色处理」→「颜色提取」）。注意：**kind（source / process / detect / sink）与文件夹无关** —— 它一直是 `_register_category(XXX_SPECS, KIND_?)` 注册时显式传入的，所以换目录不用动它（`ops/color/` 里放的就是 kind=process 的颜色提取）。

### 4.2 为什么 `main.ui` 不进 `ui/`

`QUiLoader().load('main.ui')` 用的是**当前工作目录**的相对路径，而 `main.py` 作为入口**必须留在工程根**（`python main.py` 的习惯 + 工作目录 = 工程根）⇒ **`main.ui` 跟着它留根**，`main.py` 里那两处 `load()` 一行都不用改。
只有 `LineParamsDialog.ui` 跟着窗口进 `ui\`，**改 1 处** `load()` 为显式路径（`os.path.join(BASE, 'ui', 'LineParamsDialog.ui')`）。

### 4.3 连带改动清单（一次做干净）

| # | 连带项 | 现状 | 处理 |
|---|---|---|---|
| 1 | 工程内 `import` | **38 条**平铺导入 | 按新路径改；不要靠到处 `sys.path` 兜底 |
| 2 | `QUiLoader().load(...)` | **3 处**、按工作目录解析 | `main.ui` / `SetCameraID.ui` 那 2 处不动；`LineParamsDialog.ui` 那 1 处改成显式路径 |
| 3 | 门禁用例路径 / `sys.path` | 用例在 `temp\`，内部写死工程根 | 37 套迁 `tests\`，用例里的路径与 `sys.path` 同步；**判据 = 用例数 / 断言数一个不少** |
| 4 | 备份脚本与快照口径 | 快照含 `plan\` + `temp\` | 改成含 `plan\` + `tests\` |
| 5 | 文档路径 | 本方案 §十一、《项目技术文档》§8、《代码说明书》文件总览 | 本方案先定新路径；**那三份文档冻结** ⇒ 等用户要求时再同步 |

### 4.4 落地结果（**2026.10.14 三轮全部完成 ✅**；现状目录见 §4.5，节点写法见 §4.6）

| 项 | 实际做了什么 |
|---|---|
| 目录 | 新建 `core/ ops/{source,process,detect,sink} ui/ widgets/ tests/`（各带 `__init__.py`）；**18 个文件按 §4.1 挪到位**（含 `LineParamsDialog.ui` 跟窗口一起进 `ui/`） |
| 工程根只剩 | `main.py` · `main.ui` · `SetCameraID.ui` · `pyside6.txt` · `.gitignore` · `haarcascade_frontalface_alt.xml`（用户放的级联文件） |
| 代码 import | **41 处**改成包路径（如 `from ParamRules import …` → `from core.ParamRules import …`、`import FlowPages` → `import widgets.FlowPages as FlowPages`）；`main.py` 17 处、17 个挪走的模块 24 处 |
| `.ui` 路径 | 只改了 1 处：`ui/LineParamsDialog.py` 的 `load('LineParamsDialog.ui')` → **显式路径**（`os.path.dirname(os.path.abspath(__file__))`）；`main.ui` / `SetCameraID.ui` 那两处**不动**（窗口留根） |
| 用例 | **37 套用例 + `dsh_run_all_checks.py` 进 `tests\`**（进 git）；**8 套历史留档进 `temp\legacy\`**（不进 git）；**149 个工具脚本留 `temp\`**；用例与工具里的工程内 import **一起改成包路径**（共 60 个文件） |
| **补做（用户 2026.10.14 提）** | **直线 / 圆各成一个节点文件**：新建 `ops/detect/LineDetectOps.py`（`LineDetector` + `LINE_SPECS`）与 `ops/detect/CircleDetectOps.py`（`CircleDetector` + `CIRCLE_SPECS`），算法 + 引擎入口 + 显示绘制 + 日志文案 + 参数校验 + 声明表**都在同一个文件里**；`core/Detector.py` 只剩**门面** `DetectorShape`（转发、方法签名不变）+ `make_test_image`（**74 行**）；`core/NodeRegistry.py` 里手写的 158 行（`_run_line` / `_run_circle` / `_draw_*` / `_format_*` / `validate_*` / 两条登记）移走 ⇒ **387 → 244 行**，直线 / 圆改由两个新文件登记（`_register_category(LINE_SPECS / CIRCLE_SPECS, KIND_DETECT)`） |
| **第二轮（用户 2026.10.14）** | ① **`ops/` 按"树分组"重排**：`process/` 拆成 6 个节点文件（原 `ProcessOps.py` 388 行删除）、新建 **`ops/color/`**（"颜色处理"这一类）并把 `ColorExtractOps.py` 挪进去、`source/` 与 `sink/` 不动；② **节点改名**：直线 → **直线识别**、圆 → **圆识别**（注册表 / 引擎路由 / 专用窗口 / 用例 / 树全部同步）；③ **公共零件提到 `core/ImageOps.py`**（`to_bgr` / `apply_to_roi` / `odd_kernel`）；④ **`main.ui` 树控件**：检测组里改名，识别组只剩人脸识别，**新增顶层组「颜色处理」→「颜色提取」**；⑤ 两份冻结文档（《项目技术文档》《代码说明书》）做了**被逼出来的最小同步**（旧文件/旧符号/旧节点名，**版本号不动**） |
| **第三轮（用户 2026.10.14）** | ① **`ops/source/` 拆成 3 个节点文件**（`ImageSourceOps.py` / `VideoSourceOps.py` / `CameraSourceOps.py`，原 `SourceOps.py` 322 行删除；`set_camera_frame_provider` 随相机源、`video_info` 随视频源）；② **`main.ui` 树干合并**：把"检测"与"识别"合成 **「检测识别」**，3 个节点（直线识别 / 圆识别 / 人脸识别）都在里面，「颜色处理」组不动；③ 连带改 `core/NodeRegistry.py`（3 条登记）、`main.py`（4 处导入）、4 套用例、1 个工具脚本；④ 两份冻结文档再次做**被逼出来的最小同步**（《项目技术文档》9 处、《代码说明书》4 处，**版本号不动**） |
| 守卫 | 7 套"改前/改后对照"用例加了守卫：**`before` 模式在重构后不再可用**（备份快照是旧的扁平布局），显式提示后跳过（默认跑 `after`，门禁不受影响） |
| 门禁用例的两处适配 | `dsh_doc_consistency_check.py` ① 改成**全树扫描** `PY_FILES`（文档提到 `NodeRegistry.py` 现在在 `core/`）；`dsh_m3_index_check.py` 的 `SUITE_DIRS` 加上 **`temp/` 与 `temp/legacy/`**（验点清单里引用了两套历史留档用例） |

**验收（全部实跑）**：
- **第三轮（拆源类 + 合并树干）实测**：树分组 = 采集(4) / 处理(6) / **检测识别(直线识别·圆识别·人脸识别)** / 颜色处理(颜色提取) / 新建项目；算子总数仍 **14**；三个源节点 `kind=source` 且各跑一次都正常（图片源/视频源/相机源，拿不到素材时按老口径"透传 + 结果里写说明"）；抓图 `backups\_ui_preview\m1c_after_merge_groups.png`（已登记《截图索引》）；**全量门禁 37 套 861 项全绿**（把 `dsh_m2_check` 里「识别分组」那条换成了更硬的「识别树干必须已并入」）。
- **`tests\dsh_run_all_checks.py` ⇒ 37 套 861 项断言"失败项：无"** ✅（37 套一套不少、断言数一项不少）；
- **界面零变化** ✅：抓图 `backups\_ui_preview\m1_after_dir_refactor_mainwindow.png`（1280×800，顶部 8 按钮 / 项目树 5 组 / Flow 页签 / 显示区 / 图库工具栏 8 控件 / "当前结果" 5 列 / 底部提示条，与重构前一致）—— 已登记进《截图索引》；
- `py_compile` 全部源文件通过 + `MainWindow` 能正常构造（节点树 5 个顶层项）+ 模块来源抽查（`main.py` / `core\NodeRegistry.py` / `widgets\FlowChart.py`）；
- **判据达成**：行为零变化（门禁全绿）+ 界面零变化（抓图）；
- **第二轮（按树分组 + 改名 + 拆 6 个处理节点）实测**：树分组 = 采集（4 叶子）· 处理（6）· 检测（直线识别 / 圆识别）· 识别（人脸识别）· **颜色处理（颜色提取）**· 新建项目；算子总数仍 **14**；`直线识别` / `圆识别` / `颜色提取` 都能 `get_spec` 到；抓图 `backups\_ui_preview\m1b_after_tree_groups.png`（已登记《截图索引》）；**全量门禁 37 套 861 项全绿**。
- **直线 / 圆拆分后的实测**：算子总数仍 **14**；`直线` / `圆` 的 `kind=detect`、`draw` 与 `validate` 都在；两个算子各跑一次 lena ⇒ **数据层图像未被改**（`out is img` 为真）+ 检出结果正常（直线 64 条 / 圆 7 个）；`DetectorShape().line_detector(...)` 门面仍可调用。

---


### 4.5 目标1 落地后的目录（现状速查，2026.10.14 三轮全部完成 ✅）

```
VisionFlowNoed/                      ← 工程根（= git 根；`QUiLoader` 按工作目录读 `.ui`，所以工作目录必须是这里）
├── main.py                          入口 + 界面装配 + 建图与改动 + 双击路由 + 弹窗出口（目标2 收尾后 **885 行 / 32 个方法**）
├── main.ui · SetCameraID.ui         主界面 / 相机编号对话框的布局（★ 按用户 2026.10.14 拍板**留在根**，跟 main.py 一起）
├── pyside6.txt · .gitignore · haarcascade_frontalface_alt.xml
├── core/                            零 GUI 依赖的纯逻辑
│   ├── NodeRegistry.py              登记 + 查询 + result_bbox + **is_bound_node**（NodeSpec 契约就定义在这里）
│   ├── ParamRules.py                参数校验零件（clamp_* / read_* / force_odd / run_validation）
│   ├── ImageIO.py                   图片读写（中文路径：np.fromfile + imdecode / imencode + tofile）
│   ├── ImageOps.py                  处理类公共零件（to_bgr / apply_to_roi / odd_kernel）
│   ├── Detector.py                  兼容门面 DetectorShape（转发给 ops/detect/ 两个算法类）+ make_test_image()
│   ├── param_store.py               ★ 目标2 拆出：ParamStoreMixin（11 方法；含模块级 VIDEO_ROI_KEY）
│   ├── project_store.py             ★ 目标2 拆出：ProjectStoreMixin（13 方法；含 _fingerprint_value）
│   └── flow_engine.py               ★ 目标2 拆出：FlowEngineMixin（34 方法；含 _result_note / _result_error / LOG_ERROR_MARK）
├── ops/                             算子：**一个节点一个文件，共 14 个**
│   ├── source/  ImageSourceOps.py · VideoSourceOps.py · CameraSourceOps.py     （采集 3）
│   ├── sink/    OutputOps.py                                                   （输出 1）
│   ├── process/ GrayOps.py · InvertOps.py · BlurOps.py · ThresholdOps.py ·
│   │            MorphologyOps.py · EdgeExtractOps.py                           （处理 6）
│   ├── detect/  LineDetectOps.py · CircleDetectOps.py · FaceDetectOps.py       （检测识别 3）
│   └── color/   ColorExtractOps.py                                            （颜色处理 1）
├── services/                        ★ 目标2 新建（碰 Qt / 硬件的服务）
│   ├── camera_service.py            CameraMixin（12 方法：开关设备 / 取帧 / 执行时自动打开 / 老预览分支）
│   ├── video_service.py             VideoMixin（8 方法：帧游标 / 播放定时器 / 录制收尾）
│   └── gallery_service.py           GalleryMixin（12 方法：导入 / 删除 / 切换 / 运行范围）
├── ui/                             参数窗口 + 同名 `.ui`（LineParamsDialog.py/.ui · CircleParamsDialog.py · GrayParamsDialog.py · GenericProcessDialog.py）
├── widgets/                        画布 / 多页签 / 显示区 / 图库（FlowChart · FlowPages · ImageGraphicsView · ImageGalleryWidget）
├── tests/                          ★ 门禁：**38 套** `*_check.py` + `dsh_run_all_checks.py`（**进 git**；脚本自带字体目录兜底 + 跑完校验口径与方案一致）
├── temp/                           本机工具（探针 / 截图 / 一次性脚本，**不进 git**；`legacy/` = 8 套历史留档用例）
└── plan/ · image/                  文档 · 测试图像
```

**与 `main.ui` 树干的对应关系**（树干 = 用户心智，文件夹 = 代码组织）：

| `main.ui` 树干 | 对应文件夹 | 叶子 |
|---|---|---|
| 采集 | `ops/source/` + `ops/sink/` | 图片源 · 视频源 · 相机源 · 输出图像 |
| 处理 | `ops/process/` | 灰度 · 取反 · 滤波 · 二值化 · 形态学 · 边缘提取 |
| **检测识别** | `ops/detect/` | 直线识别 · 圆识别 · 人脸识别 |
| **颜色处理** | `ops/color/` | 颜色提取 |

> ★ **kind 与文件夹无关**：`source / process / detect / sink` 是**逐节点**的引擎语义契约，由注册表 `_register_category(XXX_SPECS, KIND_?)` **注册时显式传入** ⇒ 换目录、改树干名都不用动它。
> ★ **加一个算子仍然只动三处**：① 新增一个节点文件（算法 + `_run_*` + `format_*` + `validate_*` + `*_SPECS`）；② `core/NodeRegistry.py` 末尾一行 `_register_category(…, KIND_?)`；③ `main.ui` 树里加一项。

### 4.6 节点文件为什么写成"函数 + 声明表"、而不是类（2026.10.14 定稿，用户提问后补写）

**现状一句话**：**契约用类、行为用函数、登记用数据**。

| 位置 | 形态 | 例子 |
|---|---|---|
| **节点契约**（一个算子是什么） | **类**（数据契约） | `core/NodeRegistry.py::NodeSpec`：`name` / `kind` / `run` / `draw` / `format_result` / `whole_image_param` / `param_specs` / `validate`，外加 `modifies_image`、`is_flow_level` 两个派生属性 |
| **节点声明**（登记哪几个节点、参数长什么样） | **纯数据**（dict 列表） | `GRAY_SPECS` · `LINE_SPECS` · `IMAGE_SOURCE_SPECS` … |
| **节点行为** | **函数** | `gray(img, roi, params)` · `_run_gray(detector, img, roi, params)` · `validate_blur(params)` · `format_camera(results)` |
| **算法族**（有状态 / 多方法） | **类** | `LineDetector` · `CircleDetector`（`ops/detect/` 里）· `DetectorShape`（门面） |
| **Qt 控件** | **类**（必须继承） | `FlowchartView` · `ImageGalleryWidget` · `FlowPages` |

**七条理由**（每条都对着本工程的实情）：

1. **节点是纯变换、没有状态**。引擎契约只有一个签名 `run(detector, img, roi, params) -> (out_img, results)`，输入输出**全在参数里**；节点自己不持有任何跨调用状态（状态都在 `FlowNode.params` 上、由引擎管）。给无状态的东西套类只有两种下场：全是 `@staticmethod`（早期 `class ProcessOps` 就是这样 —— **类只是个命名空间、没有语义**），或者要额外管实例生命周期（谁 new、何时 new、跨图 / 跨页要不要复用）——而引擎**根本不需要"实例"这个概念**，它要的是 `get_spec("灰度").run(...)`。
2. **注册表要的是"查表"，不是"多态"**。引擎全程只做 `NODE_SPECS[name] → NodeSpec → spec.run(...)`；面向对象在节点层的三个收益 —— 继承、覆写、`isinstance` 分支 —— **一个都用不上**：本项目**没有"子类节点"**（形态学 7 档是**参数差异**、不是类差异，正是"参数同构就合并进同一个节点"这条口径）。用类反而会诱导出"直线节点继承检测节点基类"这种**继承树**，那正是评估参考项目时明确避开的（不照搬插件化 / DI / 事件总线）。
3. **声明表天然就该是数据**。`param_specs` 是"键 / 标签 / 控件类型 / 选项"的表格，`GenericProcessDialog` 是**照着表生成界面**的；写成类就要多回答一堆没意义的问题（参数表放类属性还是方法返回？能不能被继承覆盖？）——而 dict 列表是最省事的数据：**加一个参数就是加一行**。
4. **一个节点一个文件 + 函数 ⇒ diff 最小、连锁最少**。改一个算子的算法 = 改那一个函数体，不碰类结构、不碰基类，不会出现"改基类、14 个节点一起受影响"。
5. **契约一眼看全**。函数签名就是契约（而且刻意把 `detector` 也传进来，让"公共零件只有一份实现" —— `ImageOps` 的 `to_bgr` / `apply_to_roi`）。写成类的话，契约会散在 `__init__`、方法、类属性三处。
6. **测试与门禁好写**。用例直接 `get_spec(name).run(w.detector, img, roi, params)`，或 `from ops.process.GrayOps import to_gray` 直接调算法函数 —— 不用构造实例、不用打桩（**861 项断言**全靠这个）。
7. ★ **依赖方向干净（硬理由）**：节点文件只 import `core.ParamRules` / `core.ImageOps`，**绝不 import `core.NodeRegistry`**；注册表在**文件末尾**才 import 各 `*_SPECS` ⇒ **不循环导入**。若让节点自己 `new NodeSpec(...)`，节点就必须 import 注册表 ⇒ **互相 import ⇒ 循环**。用"纯数据声明表"就没有这个问题：**谁都能读它、它不依赖谁**。

**一句话判据**：**数据 / 契约 ⇒ 类；无状态的行为 ⇒ 函数；有内部状态或一族相关方法 ⇒ 类；Qt 控件 ⇒ 类（继承是唯一的复用手段）。**

**如果真改成"每个节点一个类"**（例如 `class GrayNode(NodeBase)`）：① 得先造 `NodeBase` 基类（把 `kind` / `param_specs` / `validate` 定义成钩子）⇒ 框架复杂度上一档；② 依赖方向翻转（节点 → 框架，现在是 注册表 → 节点声明）⇒ 循环导入要重新设计；③ 引擎得决定"实例从哪来、跨图 / 跨页是否复用"⇒ **多一层可变状态**（本项目在"参数按图归档"上已经踩过三次坑，再多一层实例状态只会更难查）；④ 40 套用例里 29 个 `w.方法名()` 直连调用 + 大量 `get_spec(x).run(...)` 都要跟着改；⑤ 换来的收益是 **0**（没有继承需求、没有多态分支、没有实例状态）。

**什么时候该用类**：等真的出现"一族节点共享复杂内部状态"（例如以后接 ONNX 节点，要持模型句柄 / 会话缓存）⇒ **那一个文件**用类（就像现在的 `LineDetector` / `CircleDetector`），其余节点照旧用函数 —— 这就是现在 `ops/detect/` 里两种形态并存的原因。

## 五、批次5 目标2：拆 `MainWindow`（已定方案）

### 5.1 拆分边界（= 《代码说明书》里 `main.py` 那 10 章）

| 拆出的文件 | 装原 `main.py` 的哪些内容 | 落点 | 碰 Qt？ |
|---|---|---|---|
| `core/flow_engine` | 五 执行入口与数据流引擎 + 六 渲染显示 + 七 显示键 | `core/` | 否（numpy / cv2 为主） |
| `core/project_store` | 二 方案持久化（收集 / 指纹 / 读写 / 追加去重） | `core/` | 否（**弹对话框那两处留在 `main.py`**） |
| `core/param_store` | 四 参数归档（按图片 / 流程级 / `per_node`） | `core/` | 否 |
| `services/camera_service` | 八 相机（开关设备 / 取帧 / 执行时自动打开 / 老预览分支） | `services/` | 是（`QTimer` + 相机） |
| `services/video_service` | 九 视频（帧游标 / 播放定时器 / 录制收尾） | `services/` | 是 |
| `services/gallery_service` | 十 图库（导入 / 删除 / 切换 / 运行范围） | `services/` | 是（要操作图库控件） |
| `main.py`（剩下） | 一 启动与界面接线 + 三 建图与改动（信号接线 / 双击路由 / 脏标记 / `findChild` 收编） | **工程根** | 是 |

> ★ **2026.10.15 落地后纠偏 3 条（详见 §5.6）**：① `core/project_store` 那栏"碰 Qt？**否**"**不准** —— `_page_fingerprint` / `_collect_page` 要 `isinstance(x, NodeItem)`、`_apply_project` 要 `QPointF`；② "（弹对话框那两处留在 `main.py`）"**太小看它了**：实测是 **14 个方法**直接引用 `QMessageBox` / `QFileDialog` / 4 个对话框类 ⇒ 见 §5.2 **第二条硬约束**；③ `main.py` 里留下的不只是一章 + 三章，还有**弹窗出口 5 个薄壳**（`_warn` / `_info` / `_ask_open_path` / `_ask_save_path` / `_ask_dir`）。

### 5.2 先 Mixin、后组合

| 拆法 | 做法 | 门禁用例 | 建议 |
|---|---|---|---|
| **A. Mixin 拆分（目标2 就做这个）** | 每个新文件一个 `XxxMixin`，`class MainWindow(StartupMixin, ProjectStoreMixin, ParamStoreMixin, FlowEngineMixin, CameraMixin, VideoMixin, GalleryMixin, QMainWindow)`；方法之间照旧 `self.xxx` 互调 | **0 改动** | ★ 风险最低、行为零变化 |
| **B. 组合 / 委托（以后真需要再上）** | 抽成 `FlowEngine(self)` / `ProjectStore(self)` / `CameraService(self)`…，主窗口持引用并转调 | 调用点要改成 `w.engine._execute_node(...)` ⇒ **29 个方法 × 40 套用例都要改** | 收益不够抵成本 |

**关键约束（实测，2026.10.15 复核）**：**27 个方法被用例以 `w.方法名(...)` 直调、35 套用例 `import main as m`** ⇒ 这正是"先 Mixin"的理由（`self` 仍是主窗口，调用点一个都不用改）。★ v1.x 写的"**29 个方法 × 40 套用例**"是旧口径，开工时按实测改了。

**★ 第二条硬约束（v2.0 新补 —— v1.x 漏了它，是目标2 成败关键）："用例靠给 `main` 打补丁挡弹窗"**
用例里有 6 个模块级名字被替换：`m.QMessageBox = FakeMB` · `m.QFileDialog = FakeFD` · `m.LineParamsDialog` / `m.CircleParamsDialog` / `m.GrayParamsDialog` / `m.GenericProcessDialog = make_stub(...)`；
而 `main.py` 里**直接引用这些全局名的有 14 个方法**。方法一旦搬进新模块，全局名就在**新模块的命名空间**里解析 ⇒ 补丁失效（弹真窗口 / 接口用例挂）。所以目标2 立了三条：
① **弹窗出口收口**：`main.py` 留 5 个薄壳 `_warn` / `_info` / `_ask_open_path` / `_ask_save_path` / `_ask_dir`，Mixin 只调 `self.*`（一次性改写 **13 处**弹窗调用点）；
② **机械搬运只生成"真正用到的 import"**（工具 `temp\dsh_t5g2_split.py` 按 AST 推导新模块的 import）⇒ `QMessageBox` / `QFileDialog` 不会被顺手带进新模块；
③ **4 个对话框类的路由**（`on_node_double_clicked` / `_open_node_dialog`）**留 `main.py`**。
新用例 `tests\dsh_t5g2_api_check.py` 的第 ⑤ 条把这条钉死（Mixin 模块里出现 `QMessageBox.` / `QFileDialog.` 即红）。

**三条硬点（复核后的版本）**：
1. **54 个状态字段**散布在各方法里 ⇒ Mixin 直接共享 `self` 最省事（组合式则要先想清"哪些状态归哪个服务"）；**本轮一个字段都没挪**，仍在 `main.py::__init__` 里初始化；
2. **信号接线 + "当前页"状态**（`_bind_current_flow_page()` / `flow_nodes` / `selected_node`）**仍留主窗口**（收敛成 `FlowContext` 留到目标3 再谈）；
3. **`QUiLoader` 加载 `main.ui` + `findChild` 收编控件**必须留主窗口。★ **纠偏**：`MainWindow` **本来就没有 Qt 基类**（普通类，只持有 `self.main_window`）—— v1.x 照参考项目写的 `class MainWindow(…, QMainWindow)` 是**错的**，照它写会直接 `NameError: name 'QMainWindow' is not defined`（已踩一次）。**真实类头** = `class MainWindow(CameraMixin, VideoMixin, GalleryMixin, FlowEngineMixin, ParamStoreMixin, ProjectStoreMixin):`。

### 5.3 判据
**行为零变化 + 门禁套数 / 断言数一个不少 + 界面零变化**；每拆一块就复跑一次门禁。

### 5.4 落地结果（✅ 2026.10.15 三批全部完成）

| 批 | 内容 | 结果 |
|---|---|---|
| 第 0 步 | 改前**整份备份** `_backup_VisionFlowNoed_before_t5g2_split_mainwindow`（98 个文件）+ 基线门禁 + 改前截图 | 基线 = 37 套 861 项全绿（**踩坑**：漏设 `QT_QPA_FONTDIR` 时宽度 4 项假失败，见 §5.5） |
| 第 1 批 | **先**把弹窗出口收口进 `main.py`（5 个薄壳 + 13 处调用点）⇒ 门禁复跑仍 861 全绿；**再**搬 `core/param_store.py`（11 方法）+ `core/project_store.py`（13 方法） | `main.py` 3351 → **2793 行**；门禁 861 全绿 |
| 第 2 批 | 搬 `core/flow_engine.py`（**34 方法** + 模块级 `_result_note` / `_result_error` / `LOG_ERROR_MARK`） | **2793 → 1709 行**；门禁 861 全绿 |
| 第 3 批 | 搬 `services/camera_service.py`（12）· `video_service.py`（8）· `gallery_service.py`（12）；新建 `services\__init__.py` | 1716 → **888 行**；门禁 **38 套 870 项全绿** |
| **收尾**（2026.10.15，用户点选 a+b+c） | 清 17 个死 import（保留 4 个**故意的再导出**）· 修 `core/ → widgets/` 倒挂（新增 `is_bound_node()`）· §4.5 目录速查同步 · PyCharm 静态警告**只登记不改代码**（§11.6） | 888 → **885 行**；`project_store.py` 413→412 · `flow_engine.py` 1104→1103（各去掉 1 行被搬空的 import）；门禁仍 **38 套 870 项全绿**；界面截图 sha256 仍完全相同 |

**搬走的 90 个方法 / 5 个模块级**：`VIDEO_ROI_KEY`（进 `core/param_store.py`，`main.py` 再导出）· `_fingerprint_value`（进 `core/project_store.py`）· `_result_note` / `_result_error` / `LOG_ERROR_MARK`（进 `core/flow_engine.py`）。
**留下的 27 个方法 + 5 个薄壳**：入口 `__init__` / `main()` · 界面接线（`open_file` / `close_event` / `_show_menubar_menu` / `set_camera_id` / `_bind_current_flow_page` / `_on_flow_page_switched`）· 建图与改动（`add_flow_node` / `add_edge` / `delete_flow_node` / `delete_edge` / `update_all_edges` / `_add_node_to_page` / `_add_edge_to_page` / `_on_node_moved` / `_create_node_from_name` / `_on_tree_double_click`）· 双击路由（`on_node_double_clicked` / `_open_node_dialog` / `_mark_dirty_if_params_changed` / `_clear_current_dialog`）· 三个执行按钮入口（`on_step_execute` / `on_continuous_execute` / `run_flow_step` / `run_flow_continuous`）· 脏页确认（`_confirm_close_flow_page`）· 选中（`on_node_selected`）。

### 5.5 验证（都是可复现的硬证据）

1. **门禁**：`tests\dsh_run_all_checks.py` ⇒ **38 套 870 项断言、"失败项：无"**；**37 套老用例一行没改**（只新增 1 套 + 给 2 套加了口径 / 环境修复）⇒ "调用点 0 改动"由此证明；
2. **接口面**（新用例 `tests\dsh_t5g2_api_check.py`，8 项）：拆前 117 个方法 **一个不少**（逐个 `hasattr`）· 清单自身无重复 · 没有意外新增（多出来的只有 5 个薄壳白名单）· 6 个 Mixin 都在 MRO 里 · Mixin 模块**不出现** `QMessageBox.` / `QFileDialog.` · Mixin 模块不 `import main` · `main.py` ≤ 1200 行（实测 **885**）· `m.VIDEO_ROI_KEY` / `m.LOG_ERROR_MARK` 仍读得到；
3. **界面零变化**：`t5g2_before_split_mainwindow.png` 与 `t5g2_after_split_mainwindow.png` **sha256 完全相同**（`a84f5a04…d8ee`）⇒ **逐像素一致**；两张都已登记《截图索引》（77 → 79 张）；
4. **静态兜底**：`temp\dsh_t5g2_orphan_check.py` 逐个模块查"孤儿全局名"（`py_compile` 只查语法，`NameError` 要跑到那条分支才炸）⇒ **0 处**；
5. **覆盖度**：`temp\dsh_t5g2_split.py --coverage` ⇒ 117 = 搬走 90 + 留 27，**不丢不重**；
6. **冒烟**：`MainWindow()` 正常构造、MRO 正确、树仍 5 组、算子仍 **14** 个。

> **★ 环境坑（目标2 顺手修掉）**：参数窗口宽度那 3 套用例量的是"排版后的真实宽度"，**不指定字体目录**时 Qt 退回另一种字体 ⇒ 4 项断言假失败（实测：不设 = 857 过 / 4 失败；设上 = 861 过 / 0 失败）。现在由 `tests\dsh_run_all_checks.py` **自己设** `QT_QPA_FONTDIR`（目录不存在就跳过，非 Windows 不受影响），换人 / 换终端跑都不会莫名红。

### 5.6 已知纠偏与遗留

- **纠偏 3 条**：`MainWindow` **没有** Qt 基类（§5.2 已改）· `core/project_store.py` **不是**零 Qt（§5.1 已加注）· "29 方法 / 40 套用例"实测是 **27 方法 / 35 套 import**（§5.2 已改）；
- **冻结文档不动**：《项目技术文档》《代码说明书》《用户手册》里"37 套 861 项"是批次4 收口时的**当时事实**，本次**不回溯改**；因此 `dsh_doc_consistency_check` 的套数口径升级为"**冻结文档只增不减 + 现行方案精确相等**"—— 精确数字由**本方案**承担，且 `dsh_run_all_checks.py` 会在跑完时把实测项数与本方案写的对一遍（不一致直接算不合格）；
- **目标2 收尾（2026.10.15，用户点选 a+b+c 后做的）**：
  ① **清掉 `main.py` 里 17 个"只被搬走的方法用过"的 import**（`deque` / `json` / `time` / `read_image` / `QBrush` / `QColor` / `SOURCE_KEY` / `run_validation` / `node_level_param_keys` / `SAVE_OVERLAY` / `SOURCE_*` / `close_all_recordings` / `set_*_provider` 等）；
  ★ 保留 **4 个"故意的再导出"**：`VIDEO_ROI_KEY` · `LOG_ERROR_MARK` · `KIND_SOURCE` · `result_bbox` —— 用例把 `main` 当**聚合入口**读 `m.<名字>`（`dsh_m4_camera_check` / `dsh_m3_video_check` / `dsh_source_check`）。**我第一版把后两个也删了 ⇒ 3 套用例 `AttributeError`、门禁当场抓出**（已恢复并就地写了注释）；
  ② **修掉 `core/ → widgets/` 倒挂**：4 处 `isinstance(binding, NodeItem)` → 新增 `core/NodeRegistry.py::is_bound_node(binding)`（按"节点对象一定带 `name` / `params`"判断），两个 core 文件不再 import `widgets`（复核：`core/` 里对 `widgets` 的引用 **0 处**）；
  ③ **§4.5 目录速查同步**到目标2 之后（`services/` 的真实内容、`tests/` 38 套、`main.py` 885 行 / 32 方法）；§一 的"现状体检"表补一条 2026.10.15 复核纠偏注（56 个宿主状态 / 27 方法 × 35 套用例）；
  ④ **PyCharm 静态警告：按 A 方案"只登记、不改代码"**（用户 2026.10.15 拍板）—— 见 **§11.6**（实测数据 + 排查 / 排除步骤；不做的理由 = 目标3 会用 `FlowContext` 把契约显式化，现在做等于做两遍）。
  **验证**：门禁 **38 套 870 项全绿**（套数 / 断言数一个不少）；改前 / 改后界面截图 **sha256 仍完全相同**；`temp\dsh_t5g2_orphan_check.py` 0 处孤儿名；`temp\dsh_t5g2_self_contract_check.py` 真缺失 0 处。
- **已知静态警告（不修，登记在案）**：PyCharm 对 6 个 Mixin 报 ~120 条"**未解析的特性引用**"（`self.xxx` 跨文件）—— 这是 Mixin 方案的固有代价（见 §5.2 硬点 1 的 56 个宿主状态），**不是 bug**：实测 `self.X` 引用 261 处、其中跨文件 256 处、**真缺失 0 处**，门禁全绿。处置办法见 §11.6。
- **遗留**：① `main.py` 里那 27 个方法仍偏"界面装配"，要不要再抽 `StartupMixin` / `FlowBuilderMixin`，等目标3 / 目标4 之后再评估；② **56 个宿主状态（53 个 `__init__` 赋值 + 3 个类属性）仍集中在 `main.py`**，收敛成 `FlowContext` 留到目标3（届时静态警告与"混入不可独立测试"两个问题一起解决）；③ 三份**冻结文档**的目录树 / "37 套 861 项"不回溯改；④ `temp\` 里 5 个目标2 一次性工具留着（不进 git）；⑤ 本轮**没动 git**（提交由用户掌握）。

### 5.7 目标2 落地后的目录（**现在的真实目录**，2026.10.15 收尾后实测）

> 用户 2026.10.15 要求："把现在的目录放到技术文档的批次5目标2中"。行数口径 = `(Get-Content <文件>).Count`（与"`main.py` 拆前 3327 行"同一口径）；★ = 目标2 新建 / 拆出的。

```
VisionFlowNoed/                      ← 工程根（= git 根；`QUiLoader` 按工作目录读 `.ui`，所以工作目录必须是这里）
├── main.py                    885   **入口 + 界面装配 + 建图与改动 + 双击路由 + 5 个弹窗出口薄壳**（32 个方法）
├── main.ui · SetCameraID.ui         主界面 / 相机编号对话框的布局（★ 按用户 2026.10.14 拍板**留在根**）
├── pyside6.txt · .gitignore · haarcascade_frontalface_alt.xml
├── core/                            零 GUI 依赖（★ 目标2 收尾后**已不再 import widgets**）
│   ├── NodeRegistry.py        271   登记 + 查询 + result_bbox + **is_bound_node()**（NodeSpec 契约）
│   ├── ParamRules.py          106   参数校验零件（clamp_* / read_* / force_odd / run_validation）
│   ├── ImageIO.py              78   图片读写（中文路径：np.fromfile + imdecode / imencode + tofile）
│   ├── ImageOps.py             49   处理类公共零件（to_bgr / apply_to_roi / odd_kernel）
│   ├── Detector.py             74   兼容门面 DetectorShape（转发 ops/detect 两个算法类）+ make_test_image()
│   ├── param_store.py   ★     175   ParamStoreMixin（11 方法；含模块级 VIDEO_ROI_KEY）
│   ├── project_store.py ★     412   ProjectStoreMixin（13 方法；含 _fingerprint_value）
│   └── flow_engine.py   ★    1103   FlowEngineMixin（34 方法；含 _result_note / _result_error / LOG_ERROR_MARK）
│   └── host_contract.py ★     104   宿主契约 MainHost（65 行声明；**只为静态检查、运行时是空类**，见 §11.6）
├── ops/                             算子：**一个节点一个文件，共 14 个**
│   ├── source/   ImageSourceOps.py 163 · VideoSourceOps.py 113 · CameraSourceOps.py 63
│   ├── sink/     OutputOps.py 516
│   ├── process/  GrayOps.py 54 · InvertOps.py 32 · BlurOps.py 67 · ThresholdOps.py 71 ·
│   │             MorphologyOps.py 77 · EdgeExtractOps.py 79
│   ├── detect/   LineDetectOps.py 165 · CircleDetectOps.py 134 · FaceDetectOps.py 200
│   └── color/    ColorExtractOps.py 171
├── services/                ★ 新建  碰 Qt / 硬件的服务（从 main.py 拆出）
│   ├── camera_service.py      314   CameraMixin（12 方法：开关设备 / 取帧 / 执行时自动打开 / 老预览分支）
│   ├── video_service.py       219   VideoMixin（8 方法：帧游标 / 播放定时器 / 录制收尾）
│   └── gallery_service.py     339   GalleryMixin（12 方法：导入 / 删除 / 切换 / 运行范围）
├── ui/                             参数窗口 + 同名 `.ui`：LineParamsDialog.py 1242(+.ui) · GenericProcessDialog.py 602 ·
│                                   CircleParamsDialog.py 274 · GrayParamsDialog.py 119
├── widgets/                        画布 / 多页签 / 显示 / 图库：FlowPages.py 626 · FlowChart.py 569 ·
│                                   ImageGalleryWidget.py 480 · ImageGraphicsView.py 195
├── tests/                          **40 个文件 = 38 套 `*_check.py` + `dsh_run_all_checks.py` + `__init__.py`**（进 git）
├── temp/                           188 个文件（本机工具，**不进 git**；`legacy/` = 8 套历史留档用例）
└── plan/ · image/                  文档 7 份 · 测试图像
```

**这张表怎么读**：`main.py` 那 885 行 = **27 个"界面装配 / 建图与改动 / 双击路由"方法 + 5 个弹窗出口薄壳**；
业务逻辑已经按职责分到 **`core/`（引擎 / 持久化 / 参数）+ `services/`（相机 / 视频 / 图库）= 6 个 Mixin、90 个方法**；
`ops/` 仍是"一个节点一个文件、共 14 个"。与 §4.5（目标1 落地后）的差别 = **多了 `services/` 三个文件与 `core/` 三个 Mixin**，
`main.py` 从"含数据流引擎"变成"只做入口 + 装配"。

### 5.8 完工判定（**✅ 目标2 已完工**，2026.10.15）

| # | 判据 | 实测结果 |
|---|---|---|
| 1 | **行为零变化**：门禁套数 / 断言数一个不少 | `tests\dsh_run_all_checks.py` ⇒ **38 套 870 项断言、失败项：无**（37 套老用例**一行没改** ⇒ "调用点 0 改动"成立） |
| 2 | **接口面零变化**（新用例 8 项） | 拆前 117 个方法**一个不少** · 只多 5 个薄壳 · 6 个 Mixin 在 MRO · Mixin 不出现 `QMessageBox.`/`QFileDialog.` · 不 import main · `main.py` ≤ 1200 行（885）· 4 个再导出可读 |
| 3 | **界面零变化** | 改前 / 改后截图 **sha256 完全相同**（`a84f5a04…d8ee`）⇒ 逐像素一致 |
| 4 | **静态兜底** | 孤儿全局名 **0 处**；`self` 契约**真缺失 0 处**；`py_compile` 全过 |
| 5 | **覆盖度** | 117 个方法 = 搬走 90 + 留 27，**不丢不重** |
| 6 | **冒烟** | `MainWindow()` 正常构造 · MRO 正确 · 树 5 组 · 算子仍 **14** 个 |
| 7 | **文档同步** | 本方案 v2.2（含本节）+ 开发日志《总结：批次5 目标2…》+ 索引行 |
| 8 | **备份链** | 改前 `_backup_VisionFlowNoed_before_t5g2_split_mainwindow` / `…_before_t5g2_cleanup` + 改后 `_at_` 快照 + 方案 v1.9 / v2.0 / v2.1 均留档 |

**结论**：目标2（含收尾）**全部完成**；批次5 剩 **目标3 执行线程化 · 目标4 缓存上限 + 撤销 / 重做**（未开工）。

---


## 六、批次5 目标3：执行线程化（**✅ 已落地 + 已验收** 2026.10.15 —— 采用"**分片执行**"，未上真线程）

> **✅ 验收记录**：用户 2026.10.15 明确"**批次5目标3以验收**"；本节的落地内容、两轮修正（§6.6 / §6.7）
> 与判据（§6.4）都已在真机上验过，整体总结写在《开发日志》的
> 《总结：批次5 目标3「执行批量化（分片执行）+ 自动切换语义修正」整体总结》。
> **悬留一项**：PyCharm 里那 6 个文件的"未解析的特性引用"应已归零（B′，§11.6）—— 需在 IDE 里人工看一眼，有残留按清单补声明。

> **结论先说**：实测证明"卡"只有一个来源 —— `run_all_images` 那个**同步 for 循环**；
> 把它改成**一张图一个分片、片之间让出事件循环**就解决了，**不必上 `QThread`**。
> 用户 2026.10.15 在方案讨论中点选四条：**① 先做分片（实测后再定要不要真线程）· ② 进度显示先不做 ·
> ③ 只做"运行全部" · ④ 取消时保留已完成的结果与日志**。

### 6.1 现状诊断（2026.10.15 实测，这才是靶心）

| 执行路径 | 代码路径 | 是否阻塞事件循环 | "停止"有效？ |
|---|---|---|---|
| **单张**（单步 / 连续，范围 = 运行选中） | `on_step_execute` / `on_continuous_execute` → `run_flow_step` / `run_flow_continuous` → `_execute_static` | 一次跑完**一张图** | 不需要 |
| **批量（运行全部）** ★ | `gallery.scope_all()` 命中 → `GalleryMixin.run_all_images`：**一个完整同步 for 循环**，每张图里调 `_execute_static` | **是 —— 整个批量期间事件循环被占死** | **基本无效** |
| **视频 / 相机自动播放** | `_video_timer`（30~60ms QTimer）→ `_video_tick` → `_camera_tick` | **否** —— 每帧一个 tick，天然让出事件循环 | 有效 |

关键事实：① **全工程没有任何 `processEvents()`**（只有门禁用例里有）⇒ 批量期间的"卡"是真的；
② 循环占着事件循环 ⇒ `stop_batch()` 置的 `_batch_stop` 读不到、"运行全部中途取消勾选"也改不动；
③ `_batch_stop` 是**批量跑图与视频播放共用的一个 bool**。

### 6.2 改法（落地的实现）

1. **`services/gallery_service.py::run_all_images`**：同步 for → **分片状态机**
   - 开头把"这一批的上下文"装进 **`self._batch_state`**（`mode` / `items` / `index` / `done` /
     `started_with_scope` / `start_index` / `start_frame` / `start_path`）——★ 必须是 `self` 上的字段，
     因为**分片之间要过一遍事件循环，函数局部变量活不过去**；
   - 清空日志 + `_log_accumulate = True` + `_batch_stop = False`，然后 **`QTimer.singleShot(0, self._batch_step)`**，
     **本函数立刻返回**（返回"计划张数"，不再返回"真跑了几张"——分片是异步的）；
   - **`_batch_step()`**：跑**一个分片**（一张图）——先判两条急停（`_batch_stop` / 中途取消勾选"运行全部"），
     再判是否跑完，然后 `切当前图 + 切参数 + 同步图片源 + _execute_static(frame, mode)`，
     结尾 `state["index"] += 1` 并**再排下一片**（这里才是分片边界）；
   - **`_batch_finish(hint)`**：还原因"不勾自动切换"而临时改掉的选中项 / 图片源 / 画面 +
     清掉 `_batch_state` + `_log_accumulate = False` + `_batch_stop = False`（复位）+ 写收尾那行日志；
2. **防重入**：批量跑着时再点"连续执行" ⇒ 忽略并写一行"批量执行中，本次忽略"
   （旧版事件循环被占死，第二次点击会**排到整批跑完之后**再跑一遍 —— 那是没人想要的）；
3. **`stop_batch()`**：语义不变（顺带停播放 + 收尾录制），但现在**真的能中断批量**（标志在下一片开头被读到）；
4. **`main.py::__init__`**：新增 `self._batch_state = None`（宿主状态 56 → 57）。
5. **视频 / 相机一行不动**（它们本来就是定时器分片）。

**要遵守的既有语义（一条没改）**：连续执行 = 选中节点 + 全部上游；单步 = 只跑选中那一个；
结果缓存键 = 图片 × 页面 × 执行方式；**相机帧不进缓存**；执行 / 渲染路径**绝不弹 `QMessageBox`**；
取消 = 干净急停（分片边界天然没有"半张图"）。

### 6.3 实测证据（真实图片，`E:\opencv_python_3_8\data` 只读）

工具 `temp\dsh_t5g3_bench.py`；流程取偏重的 **灰度 → 形态学(梯度 7×7 ×2) → 边缘提取**，图取该目录**最大的 12 张**：

| 测什么 | 结果 |
|---|---|
| **① 单张耗时**（决定"分片后单张还会不会卡一下"） | 最慢 **28.1 ms**（`digits.png` 2000×1000）· 中位 6.7 ms · 平均 8.7 ms ⇒ **远低于"能看出卡"的量级** |
| **② 批量期间事件循环通不通** | 分片执行：12 张 122 ms，期间 10ms 定时器触发 **8 次**；**同步 for 对照（改前行为）：101 ms 内只触发 0 次** ⇒ 改前事件循环被占死、改后是活的 |
| **③ 取消延迟** | 点 `stop_batch()` 后 **6.9 ms** 批量就结束（= 等到下一片边界，量级就是单张耗时） |
| **④ 界面零变化** | 改前 / 改后主界面截图 **sha256 仍完全相同**（`a84f5a04…d8ee`）——本次**零新界面元素** |

**⇒ 因此不上方案 B（真线程化）**：单张最慢 28 ms，线程化要付的代价（`_execute_static` 拆 compute / present、
流程图拍快照、缓存加锁、56 个宿主状态收敛成 `FlowContext`）换不来用户能感知的收益。
**留档**：真需要时（例如将来出现"单张 > 300ms"的重流程 / 要并行多核）再按"方案 B"做，前置条件与代价记在 §十二。

### 6.4 判据与结果（✅ 全部通过）

| # | 判据 | 结果 |
|---|---|---|
| 1 | **不阻塞**：调用后立刻返回，返回时一张都没跑、日志已清空 | ✅ 新用例 ①（3 项） |
| 2 | **行为等价**：分片结果 = 逐张直接 `_execute_static`（**逐像素一致**），且 3 张互不相同 | ✅ 新用例 ③（2 项） |
| 3 | **取消干净**：中途"停止"只停在分片边界、已完成的结果与日志保留、上下文清空、**还能再跑一批** | ✅ 新用例 ⑤（3 项） |
| 4 | 中途**取消勾选"运行全部"** ⇒ 立刻停 | ✅ 新用例 ⑥（2 项） |
| 5 | 日志**逐张累积**；单张出错**跳过继续** | ✅ 新用例 ④（1 项）+ ⑧（2 项） |
| 6 | "自动切换"语义不变：不勾 ⇒ 还原成开始时那张；勾 ⇒ 跟随到最后一张 | ✅ 新用例 ⑦（3 项） |
| 7 | 防重入（不开第二批） | ✅ 新用例 ⑨（3 项） |
| 8 | **老门禁一个不少** | ✅ **42 套 972 项断言全绿**（详见 §11.3；其中 `dsh_m2_v5_check` 因为"分片是异步的"补了一个 `wait_batch()` 等待，**判据一条没改**） |
| 9 | **画布只在勾了「自动切换」时才跟随**（见 §6.6 的修正） | ✅ 新用例 ⑩（4 项） |
| 10 | **「自动切换」在批量开始时定格**（中途拨动不影响正在跑的这一批，见 §6.7） | ✅ 新用例 ⑪（4 项）+ 一行提示 |

### 6.5 遗留

① **进度显示不做**（用户 2026.10.15 拍板）：批量期间看"执行日志一张一张实时冒出来"就是进展；
② `_batch_stop` 仍是**批量与播放共用一个 bool**（拆成两个概念要碰 `video_service` 3 处、用户可见行为无变化，
按"最小改动"先不动）；
③ **真线程化（方案 B）** 与它需要的前置（`FlowContext` / 快照 / 锁）记在 **§十二《想法（未开发）》**，
等出现"单张明显卡"的实据再启动；
④ **PyCharm 静态警告**已在同一天用 **B′（宿主契约 `MainHost`）根治**，见 §11.6 —— 只是"让 IDE 不再报"，
**不是**把宿主状态收敛成 `FlowContext`（那是 ③ 的前置、属结构性重构）。

### 6.6 ★ 2026.10.15 修正：「自动切换」的语义 —— **不勾时批量不得刷画布**

**用户口径**（原话）："**我原本是设计只有选择了「自动切换」按钮才会在运行时自动切换画布的图片，将处理后的图片从头播放到尾**。
但是现在的问题是我不选择这个按钮画布也会自动播放图像列表中处理后的图片，最后再切换回到选中的那一张中。**修改代码，重新实现我原本的这个功能**。"

**根因（诚实交代）**：这个行为**以前就存在** —— 批量的每一张都会调 `_execute_static`，而它**无条件**把处理后的图画到画布上，
跑完再由 `_batch_finish`"还原"成开始时那张。**但改前事件循环被占死、Qt 根本重绘不了**，所以用户**看不到**中间那些帧；
**目标3 的分片改动让出事件循环之后，每张处理后的图都被真实画了出来** ⇒ 用户才看到"不勾也在播放"。
**换句话说：这个老问题是被目标3 暴露出来的**（不是目标3 新引入的逻辑，但观感上是这次改动带来的）。

**改法（两处，最小改动）**：
1. `core/flow_engine.py::_execute_static()` 新增参数 **`show=True`**：`show=False` 时**只算不显示**
   （跳过 `_display_image`；结果照旧进缓存、日志照旧逐张写 ⇒ 切回那张图仍看得到结果）；
2. `services/gallery_service.py::_batch_step()` 调用处传 **`show=state["follow"]`**（批开始时定格的开关值，
   见 §6.7）⇒ **开始时勾了「自动切换」才刷画布**（逐张从头播到尾，这正是用户原本的设计），不勾就全程不动；
   `_batch_finish()` 里那段"恢复画面"由此退化成**兜底**。
3. **连带修 2 条用例的桩函数**（`dsh_t5g3_batch_check.py` 的 `boom` / `dsh_m2_v5_check.py` 的 `patched`）：
   它们写死了签名，引擎多一个参数就 `TypeError` ⇒ 改成收 `**kwargs` 并原样转发（**以后再给引擎加参数不会断**）。

**判据（新用例 ⑩，4 项）**：不勾「自动切换」时 —— ① 批量**期间** `_display_image` **一次都不许调用**（画布全程不动）；
② 整批只调用 1 次（收尾那次兜底还原）；③ **图照样都算了**（3 张结果都在缓存 + 结尾"共执行 3/3 张"）；
④ 勾上之后每张都刷（3 张 = 3 次，从尾播到尾）。
（`_display_image` 是批量场景下**唯一**的画布写入路径，所以"调用计数"等价于"画布有没有变"。）

### 6.7 ★ 2026.10.15 再修正：「自动切换」在**批量开始时定格**（中途拨动不影响正在跑的这一批）

**用户口径**（原话）："**我不开启「自动切换」按钮运行连续执行后，在打开「自动切换」按钮，
并没有再点击执行按钮或者连续执行按钮，但是画布上的内容会自动播放到最后**。是不是我不开启「自动切换」按钮它堵塞了，
但是一打开就有自动播放了。给我修复这个问题。"

**根因（实测排查，两件事）**：
1. **拨开关本身不会显示任何东西** —— `auto_switch_changed` 这个信号在**整个工程里无人监听**
   （`widgets/ImageGalleryWidget.py` 里只有 `auto_switch_box.toggled → auto_switch_changed.emit`），
   而"点图库换图"走的是 `gallery_list.itemClicked → _on_item_clicked`（必须用户真点）。
   ⇒ 用户说的"堵塞后释放"其实不是排队，**而是批量还在跑**；
2. **真根因**：§6.6 的改法里 `_batch_step` 每跑一片都**重新读** `gallery.auto_switch()` ⇒
   开始不勾时前半程 `show=False`（画布不动），**跑到一半拨上**之后后半程 `show=True` ⇒ 画布开始逐张吐画面（"自动播放"）；
   而收尾的 `_batch_finish` 也在看**当下的开关**（此时已是 ON）⇒ **不还原** ⇒ 画布停在**最后一张**。
   两件事合起来 = 用户看到的"自动播放到最后"。

**改法（"定格"语义，最小改动）**：
1. `run_all_images()` 建 `_batch_state` 时**快照** `"follow": gallery.auto_switch()`；
2. `_batch_step()` 用 `state["follow"]` 决定"要不要把图库选中项跟着切"与 `show=`；
3. `_batch_finish()` 用 `state["follow"]` 决定"要不要还原" ⇒ **开始不勾、中途拨上，收尾照样还原**（不会停在最后一张）；
4. 新增薄处理器 **`_on_auto_switch_changed(checked)`**（挂在 `gallery_widget.auto_switch_changed` 上，`main.py` 接线）：
   **只在"批量进行中 + 与定格值不一致"时**写一行短提示 —— "批量执行中改动「自动切换」：本批仍按开始时的设置（跟随 / 不跟随）"，
   免得用户以为开关坏了。
**语义依据**（用户原话）："只有选择了自动切换…把处理后的图片**从头播放到尾**" —— 中途拨上不可能"从头播"，
所以整批统一按**开始那一刻**的开关走。开关的新状态对**下一次**批量生效。

**判据（新用例 ⑪，4 项）**：① 开始不勾、跑到一半拨上 ⇒ 这一批**仍然不刷画布**（采样恒 0）；
② 收尾**照样还原**成开始时那张（不是停在最后一张）；③ 中途拨动时**写了一行提示**；
④ 开始勾着、跑到一半拨回不勾 ⇒ 这一批**继续跟随**（每张都刷 = 3 次）。

---


## 七、批次5 目标4：结果缓存上限（LRU）+ 撤销 / 重做（**✅ 已落地并收口**，2026.10.15）

> ### ✅ 目标4 交付记录（2026.10.15）
>
> **交付内容**：**三批**（① 缓存两池 LRU + 日志自动滚动 · ② 撤销/重做骨架（节点 / 连线）· ③ 参数修改 + 节点拖动）
> ＋ **四轮修正**（§7.7 命令改存 uid · §7.8 改参数按图片恢复 · §7.9 撤销栈每页一条 · §7.3 日志策略）＋ **控件落位**（`main.ui` 的「编辑」菜单与两个按钮）。
> **用户 2026.10.15 两次追加口径**：**"换页后还要能撤销/重做"**（推翻"换页清栈"，见 §7.9）；**"导入的流程图，撤销最多只能撤到导入时"**（§7.9，已用断言钉住）。
> **明确不做**：**页面新建 / 删除的撤销**（用户 2026.10.15："**我不打算做，可以把技术要求写到《想法》里面**" ⇒ 技术要求入档 **§12.5**）；**快捷键**（§12.3，后续体系化做）。
> **判据与结果**：新增两套用例 **`dsh_t5g4_cache_check`（13 项）+ `dsh_t5g4_undo_check`（51 项）全过**；
> 门禁 **40 套 908 项 → 42 套 972 项全绿**；**界面零变化**（本目标只加菜单/按钮，未改布局）。
> **整体总结**写在《开发日志》：《总结：批次5 目标4「缓存上限 LRU + 撤销 / 重做」整体总结》。
> **交付后残留**：一条**待拍界面证据图**（撤销/重做可用态的主界面图，登记《截图索引》）—— 不影响功能，属"记录待补"。

> **用户 2026.10.15 拍板（七条；第 ⑦ 条已被"每页一条栈"取代，见 §7.9）**：① 缓存上限 = **内存 256 MB 为主 + 条数 400 作硬顶**；② **视频序列帧单独分池**（乙方案）；
> ③ 撤销范围 = **"结构 + 参数 + 页面" + "节点拖动位置"**（**不含图库导入 / 删除**）；④ 控件 = **菜单「编辑」+ 顶部两个按钮**（甲+乙方案）；
> ⑤ **快捷键先不做**（用户："我打算后续再为全部控件和操作添加快捷键" ⇒ 体系化做，见 **§12.3**）；
> ⑥ 栈上限 = **50 步**；⑦ 清栈时机 = ~~换页 / 载入方案 / 新建项目 / 删除页面~~ ⇒ **改：栈按页面各一条，换页不清历史**（§7.9）。

### 7.1 结果缓存上限（LRU）

**它到底是什么**：`result_cache` 存"**每张图算完之后的处理结果**"（键 = **图片 × 页面 × 执行方式**，值 = `{frame, data, exec_info}`），
作用是**切回某张图时直接显示上次的结果、不用再点执行**。

**现状（2026.10.15 实测）**：上限**其实早就有** —— `core/flow_engine.py:161-164`：

```python
# 超过 400 条就把最旧的丢掉（FIFO 近似 LRU），免得越跑越吃内存。
if len(self.result_cache) > 400:
    for old_key in list(self.result_cache)[:-400]:
        self.result_cache.pop(old_key, None)
```

三个毛病：① **是 FIFO 近似 LRU** —— `_show_static_image()` 命中缓存时**不刷新顺序** ⇒ "**刚看过的图照样被淘汰**"；
② 按**条数**（400 条）而不是按**内存** —— 实测小图 **0.75 MB/条**、大图 **5.72 MB/条**，同样 400 条可以是 **378 MB**、也可以是 **2.3 GB**；③ 阈值硬编码、不可配。
**实测内存**：`data` 目录 66 张跑完 = **66 条 / frame 合计 62.4 MB / 单条最大 5.72 MB**。

**要改成**：**上限 + 真 LRU**（命中即"移到最新"，超限淘汰**最久没用过**的那条）· 上限 **内存为主（256 MB）+ 条数硬顶 400** ·
**淘汰不影响正确性**（下次要用就重算，结果一样）· **相机帧仍然不进缓存**（既有规矩不动）·
★ **视频序列帧单独分池**（否则**看一段视频会一口气写几百条、把静态图结果全挤掉** —— 视频帧键是 `路径#帧号`，每帧一条）。

**实现方式（★ 已定：不改数据结构）**：**继续用普通 `dict`**，只把淘汰逻辑做成函数（命中时 `cache[k] = cache.pop(k)` 即 O(1) "移到最新"）。
理由：**至少 8 套用例直接把它当 dict 用**（`.values()` / `.items()` / `.get()` / `.clear()` / `len()` / `list(...)[-1]`）
⇒ 换成自定义类要动一堆用例，不划算。

**判据（4 条）**：① 跑超量图后 `len(cache) ≤ 条数上限` **且** `sum(frame.nbytes) ≤ 内存上限`；
② ★ **真 LRU 判别**：填满 → 访问第 1 条 → 再填几张 ⇒ **第 1 条仍在**（FIFO 会把它淘汰掉；这条能把两种实现区分开）；
③ 淘汰后重算的结果与"未被淘汰时"**逐像素一致**；④ 删图库项仍按图清缓存、相机帧仍不进缓存（既有行为不回归）。

### 7.2 撤销 / 重做（命令模式）

**要罩住的入口（已清点）**：加节点 `widgets/FlowChart.py::add_flow_node(453)` · 删节点（**连带删它的连线**）`delete_flow_node(484)` ·
加连线 `add_edge(473)` · 删连线 `delete_edge(539)` · 改参数 / ROI `core/param_store.py::_save_node_params(108)` ·
加 / 删页面 `widgets/FlowPages.py::add_page(154)` / `delete_page(201)` · 节点拖动（只记最终位置）·
载入方案 `core/project_store.py::_apply_project(327)`（= **清栈**时机）。

**落点**：**`core/commands.py`**（**纯逻辑、零 Qt**：`Command` 基类 + `AddNode` / `RemoveNode` / `AddEdge` / `RemoveEdge` / `MoveNode` / `SetParams` / `AddPage` / `RemovePage` + `UndoStack`，用**回调列表**通知变化）
+ **`services/undo_service.py`**（**碰 Qt 的服务进 `services/`**：`UndoMixin` —— 把命令下到入口处 / 接菜单与按钮 / 联动 `enabled` / 写日志行）⇒ **6 个 Mixin → 7 个**。

**控件（已落位，2026.10.15）**：菜单栏 **「编辑」→ 撤销 / 重做**（`menu_edit` · `action_undo` · `action_redo`）
+ 顶部按钮排两个按钮（`btn_undo` · `btn_redo`；用户自行加入、助手统一命名）。初始 `enabled = false`（撤销栈空 = 不可点），
接上代码后由栈状态联动。**快捷键先不做**（见 §12.3）。**不进右键菜单**（既有约定："右键只留删除节点 / 删除连线"）。

**判据（往返断言，复用现成的 `_page_fingerprint`）**：做 N 步（加节点 + 连线 + 改参数 + 新建页）→ **撤销 N 步 = 回到初始** →
**重做 N 步 = 回到末态**（逐项比对：节点集合 / 坐标 / 参数 dict / 连线集合 / 页数 / 当前页）。

**三个必须防的坑**：① **删节点命令要连"被连带删掉的连线"一起存**（undo 时一起放回）；
② **`add_flow_node` 有 `FlowChart.py` 与 `main.py` 两个入口**（后者是包装）⇒ 命令**只记一次**（下在最内层或最外层，别两边都记）；
③ **改参数 / 改拓扑都不清结果缓存**（现有语义 —— 缓存键里没有"流程图指纹"）⇒ **撤销后也不清**，想看到新结果需重新执行；**这条要写进文档，别被当成 bug**。

### 7.3 撤销 / 重做的日志怎么写（用户 2026.10.15 提问）

**用户的问题**："如果日志中存在执行的日志，那么撤销/重做的日志写到后面还是清空日志后再写？写到最后会不会因为前面的执行日志太长影响观看？"

**结论：追加（不清空）+ 与执行行区分 + ★ 顺手补"自动滚到底"。** 理由：
① **不能清空** —— 执行日志是"我刚才跑了什么"的唯一账本；撤销常常正是针对"上一次执行 / 上一次操作"，清空会把上下文抹掉；
② ★ **"太长看不见"的真症结不是日志长，而是日志表现在根本不会自动滚动** —— 全工程 grep **没有 `scrollToBottom()`**
⇒ 批量跑 66 张会有 130+ 行，新写的撤销行在**底部**、而视图还停在**顶部**，用户自然"看不见"。**目标4 顺手加"写完后 `scrollToBottom()`"**（一行改动、收益最大）；
③ 区分方式（二选一，**倾向甲**）：**甲 = 操作行加标记**（如 `—— 撤销：删除节点「灰度」 ——`），复用现成"错误行涂红"的标记思路（同类机制再加一种"操作行"标记与颜色）；
**乙 = 另择一处显示**（`lbl_current_node` 旁的状态标签）—— 零污染，但要多看一个地方。
**不推荐的备选**：清空重写（丢上下文）／只写状态标签不写日志（违背"提醒只走日志"的约定）。

### 7.4 动手顺序（3 批，最小可用第一版）

1. **第 1 批：缓存上限 + 真 LRU** ✅ 2026.10.15（无界面、判据最硬）—— `flow_engine` 淘汰逻辑 + 新用例 `dsh_t5g4_cache_check.py`（含"真 LRU"判别断言）+ **顺手加 `scrollToBottom()`**；
2. **第 2 批：撤销 / 重做骨架** ✅ 2026.10.15 —— `core/commands.py` + `services/undo_service.py` + 菜单与按钮接线，**先只罩"节点增删 + 连线增删"**（把往返跑通）；
3. **第 3 批：扩到"参数修改 + 节点拖动"** ✅ 2026.10.15 · **"页面新建 / 删除"仍待做**（见 §7.6 遗留）。
每批：**改前备份 → 门禁 → 日志 → 方案升版**；收口时全量 42 套。

### 7.5 落地结果（2026.10.15，第 1~3 批）

| 批次 | 新增 / 改动 | 关键点 |
|---|---|---|
| **① 缓存上限 + 真 LRU** | **新增 `core/result_cache.py`**（纯逻辑、零 Qt）· 改 `core/flow_engine.py` · 改 `services/gallery_service.py` · **新增用例 `dsh_t5g4_cache_check.py`（13 项）** | ★ **发现旧上限只写在视频分支里** ⇒ 静态图批量跑**根本没上限**；现在写入缓存即淘汰、命中缓存即 `touch`（真 LRU）；**两池**（静态 400 条 / 256 MB + 序列 120 条 / 64 MB）；`_show_static_image` / `_batch_finish` 命中时 `touch`；**日志写完 `scrollToBottom()`**（`_update_execution_log` + `_append_log_hint` 各一处） |
| **② 撤销 / 重做骨架** | **新增 `core/commands.py`**（零 Qt）· **新增 `services/undo_service.py`（`UndoMixin` = 第 7 个 Mixin）** · 改 `main.py`（基类 + `_init_undo()` + 四个入口各记一条 + 换页清栈）· `core/host_contract.py` 重新生成（仍 65 个名字）· `dsh_t5g2_api_check` 白名单加 7 个方法 · `dsh_t5g3_host_check` 改 7 个 Mixin · **新增用例 `dsh_t5g4_undo_check.py`** | 命令**只记在 `main.py` 的四个入口**（右键菜单与树双击也都走它们 ⇒ 不会记两遍）；`_undo_busy` 挡住"撤销动作又被记成新动作"；**删节点命令会把被连带删掉的连线一起存**；`UndoStack` 用**回调列表**通知（不引 Qt），栈上限 50；四项控件 `enabled` 随栈联动、空栈全灰 |
| **③ 参数 + 拖动** | `core/commands.py` 加 `SetParamsCommand` / `MoveNodeCommand` · `services/undo_service.py` 加 `apply_params` / `move_node` / `copy_pos` + 拖动去抖 · 改 `main.py`（`_mark_dirty_if_params_changed` 记参数命令；`_on_node_moved(page, node)` + 连接带节点；`_add_node_to_page` / `_bind_current_flow_page` 记坐标基准） | 参数命令存的是**深拷贝快照**（`before` / `after`），撤销后还会同步写回"按图片存档"；拖动期间 `positionChanged` 连发 ⇒ **攒成"一次拖动 = 一条命令"**（停 0.4 秒提交，`MOVE_COMMIT_DELAY_MS`）；坐标基准在建节点 / 绑定页面时登记（方案里读出来的节点也能撤回原位） |

**判据与结果（`dsh_t5g4_cache_check` 13 项 + `dsh_t5g4_undo_check` **51** 项全过）**：
① 缓存：条数上限 / 字节上限 / ★**真 LRU 判别**（填满→访问第 1 条→再填 ⇒ 第 1 条仍在）/ **视频帧分池**（静态图不被挤）/ 淘汰后重算逐像素一致 / 删图库项按图清缓存 / 日志两处 `scrollToBottom` / 常量与 `is_sequence_key`；
② 撤销：初始全灰 / 建节点→撤销→重做（名字·坐标·参数）/ ★**往返断言**（5 步 ↔ 初始 ↔ 末态逐项比对）/ ★**删节点连带连线的恢复** / 删连线恢复 / 栈上限 / **换页清栈** / 撤销不清缓存 / 日志两行 / 重复连线不记命令 / 参数快照 / 拖动（攒一条 + 往返坐标）。

### 7.6 遗留（目标4 还没做完的部分）

1. ~~**页面新建 / 删除的撤销**~~ **用户 2026.10.15 决定不做，技术要求已按用户要求移入《想法》§12.5（等后续再做）** —— 原文保留在下面备查：
   给 `FlowPageManager` 加 `on_page_added` / `on_page_removing` / `on_page_removed` 三个回调（它本来就收回调），
   删除前用**现成的 `_collect_page(page)`** 收下整页模型（含 `params_by_image`），撤销时按 `_apply_project` 里那段"从模型重建一页"的写法重建（`append_pages([title])` + 逐节点 `_add_node_to_page` + 逐连线 `_add_edge_to_page`）；
   ★ **要注意顺序**：`add_page()` / `delete_page()` 都会**切页** —— v2.12 起"换页不再清栈"（见 §7.9），但记录仍应放在**切页回调之后**（`on_page_added` 在末尾通知）；
   另需一起带回来的页面附加状态：`dirty` / `project_path` / `selected_node`。
2. **快捷键**：按用户 2026.10.15 口径**先不做**（后做时见 §12.3：`QAction` + `setShortcut`，纯表进 `core/shortcuts.py`）。
3. 页面若将来做撤销：重建后**标签页顺序**会回到末尾（`append_pages` 追加）—— 要保序得再动 tab bar，记为已知限制。

### 7.7 ★ 2026.10.15 修正：**命令改存 uid**（修用户报的两个 bug）

**用户报的两个现象**（原话）："1、**全部撤销后再一步一步按重做**，出现如图2所示的现象。可以看到**节点和线并不是连在一起的**，
但是一开始的流程是如图1所示。2、如图3所示，**撤销按钮已经按下来了**（说明没有内容可以撤销了），但是**图上还存在灰度节点**。"

**同一个根因**：v2.9 的命令里存的是**节点 / 连线对象引用**，而 `NodeItem` 是 Qt 对象 ——
**撤销会把它们销毁，重做是"重建一个新对象"** ⇒ 旧引用要么指向**已销毁的 C++ 对象**、要么指向**已经不在流程图里的对象**：
| 现象 | 机制 |
|---|---|
| **线飘了** | 重做连线时 `AddEdgeCommand.do()` 用的是**建线那一刻记下的旧两端对象**（撤销节点时已被销毁）⇒ `EdgeItem(死对象, 死对象)` ⇒ 几何算不出来 / 对不上节点 |
| **按钮灰了节点还在** | "新建节点 → 删除节点 → 撤销（删除）"会**重建**一个新节点；此时再撤销那条更早的"新建节点"，命令里的旧引用早已不在 `flow_nodes` 里 ⇒ `delete_flow_node` 头一句 `if node not in self.flow_nodes: return` **直接返回** ⇒ 删了个寂寞，栈却照常弹空 ⇒ 按钮变灰、画布上留着节点 |

**改法（"身份连续"）**：
1. **给节点 / 连线各发一个 uid**（存在 `node._undo_uid` / `edge._undo_uid` 上），**命令只存 uid**；
2. 执行时用 **`ctx.resolve(uid)` 取"现在活着的那一个"**，重建时**沿用同一个 uid** ⇒ 重做连线 / 重做删除 / 重做移动 / 重做改参数
   永远作用在当前对象上；
3. `resolve()` 做**两层探活**：① 对象是否还在 `flow_nodes` 里（`scene.removeItem` 只解除场景归属、对象其实还活着，
   光看 `pos()` 探不出来）；② C++ 对象是否已被销毁（`RuntimeError`）；
4. **删除类命令在"界面真正删掉之前"先把 uid 从注册表摘掉**（`ctx.forget` / `ctx.forget_edge`），避免解析到僵尸对象；
5. `undo()` / `redo()` 抽成 `_run_stack_step()`：**挡住记录 + 异常兜底**（某条命令出错只写一行日志，不让界面崩）。

**回归断言（`dsh_t5g4_undo_check` ⑮⑯，共 +10 项）**：
⑮ 建 3 节点 + 2 连线 + 拖一个节点 → **撤销到底 → 全部重做** ⇒ ① 节点/坐标/连线与撤销前**逐项一致**；
② 每条连线的两端都是**当前活着的节点**（`id()` 在同一集合里）；③ 每条线的路径起点/终点与两端节点的输入输出点**误差 < 1.5px**（直接钉"线贴在节点上"）；
⑯ 新建节点 → 删除 → 撤销（重建）→ **再撤销那条"新建"** ⇒ ① 节点真没了 ② 栈空、按钮灰；③ 继续重做/撤销**反复往返都不坏**。

### 7.8 ★ 2026.10.15 再修正：**改参数要"按图片"恢复**（修用户报的"撤销了参数还是改后的值"）

**用户口径**（原话）："**参数撤销的问题，我一直撤销，直到撤销到创建节点的那一步，但是参数还是没有回到参数值，而是显示修改后的值**。
也可能是边缘检测这个节点的问题，给我查一下。**我重新运行程序就没有这个问题了**。"

**根因（实测复现）**：本项目的**运行参数是按图片分别存档**的（`params_per_image[图片键]`，见 §7.1 与 `core/param_store.py`）。
v2.10 的 `apply_params()` 只改了"**当前那张图**"的两处状态（`node.params` + 当前图的槽），
于是"**在 A 图改完参数 → 切到 B 图 → 撤销 → 再切回 A 图**"时，A 的存档里还是改后的值 ⇒ 一切回 A 图，
`_load_node_params()` 又把改后的值载进 `node.params` ⇒ **看起来"撤销没生效"**。
"重新运行程序就没问题"也解释得通：**存档只在内存里**（没保存方案），重启后是空的，于是显示默认值。

**复现数据**（修前）：
```
① 改完(A 图)：node.params[edge_low] = 99 · 栈顶 = 修改「边缘提取」的参数
② 切到 B 图：存档 = {'A.png': 99}
③ 撤销后：node.params[edge_low] = None
   存档 = {'A.png': 99}          ← ★ 关键：撤销没清掉 A 图存档里的 99
④ 切回 A 图：node.params[edge_low] = 99   ← 参数又变回改后的值（= 用户看到的现象）
```

**改法**：`SetParamsCommand` 带上 **`image_key`**（"改的是哪张图的参数"），`apply_params(uid, snapshot, image_key)`：
- `image_key` 就是**当前图**（或为 None，老口径）⇒ 同时改 `node.params` 与那一份存档；
- `image_key` 是**别的图** ⇒ **只改那张图的存档**，绝不碰 `node.params`（它代表当前图的参数）；
- 只给"跟着图片走"的节点写图片槽（起点 / 输出这类**流程级节点**不参与按图片归档），
  且**空快照按既有约定不占槽**（`store.pop(image_key)`）—— 与 `_save_node_params` 的"空字典不存"保持一致；
- 记命令时由 `main.py::_open_node_dialog` 捕获 `before_key = self.current_image_key`，经
  `_mark_dirty_if_params_changed(node, before, image_key)` 传进命令（参数窗口是模态的，开窗到关窗期间图片不会变）。

**回归断言（`dsh_t5g4_undo_check` ⑰，3 项）**：① 在 A 图改参数 → 切到 B 图撤销 → 切回 A 图 ⇒ 参数**真的回到改之前**；
② A 图存档里**不再留着**改后的值；③ 重做之后切回 A 图 ⇒ 参数又变回改后的值（重做同样按图片走）。
**修后复现数据**：④ 切回 A 图 `node.params[edge_low] = None`、存档 `{}` ✓。

### 7.9 ★ 2026.10.15 修正：**撤销栈改成"每页一条"**（修用户报的"换页后撤销失效"+ 明确"导入即基准"）

**用户口径**（原话）："现在存在一个关于更换页面的问题，现在有两个页面，在一个页面中画好流程图后再切到另一个页面画流程图，
**然后回到第一个页面后撤销按钮失去了作用，即换页后不能再撤销和重写。修复这个问题**。
**对于导入的流程图，设置撤销最多只能撤销到导入时，即以刚导入时为基准，修改后才能撤销/重写**。"

**根因**：这是 v2.10 之前那条拍板"**清栈时机 = 换页 / 载入方案 / 新建项目 / 删除页面**"的直接后果 ——
`_on_flow_page_switched()` 开头就 `stack.clear()`，于是"换页 = 历史清零"。（用户的这条新口径**推翻了"换页清栈"**。）

**改法（每页一条撤销栈）**：
1. `services/undo_service.py`：新增 **`self._undo_stacks`（页 key → 该页自己的 `UndoStack`）**；
   `_init_undo()` 里先放一个**占位栈**（`_undo_stack`），随后由 `_bind_undo_stack_for_page()` 换成当前页那条；
2. 新增 **`_stack_for(page_key)`**（没有就建一个**空**栈 ⇒ "这一页刚出现时"就是它的基准）
   与 **`_bind_undo_stack_for_page()`**（换页 / 载入方案 / 新建页面后调用：把当前栈换成该页的、**顺手丢掉已删页面的栈**、并立刻同步按钮 `enabled`）；
3. `main.py::_on_flow_page_switched()`：把原来的 `stack.clear()` **换成** `self._bind_undo_stack_for_page()`（放在 `_bind_current_flow_page()` 之后，那时"当前页"已经换好）；
   `__init__` 里 `_bind_current_flow_page()` 之后也调一次（把第一页的栈绑上）；
4. `_on_undo_stack_changed()` 改用 `getattr(self, "action_undo", None)` 取控件 —— 因为"占位栈"建好时会**立刻回调一次**，那时 `.ui` 里的四个控件还没找出来；
5. **"导入即基准"不需要额外代码**：`_apply_project()` 建页/建节点走的是 `append_pages` + `_add_node_to_page` + `_add_edge_to_page`（**不经过四个记录入口**）⇒
   导入动作**从不进撤销栈**；而新页面的栈**本来就是空的** ⇒ 撤销最多撤到"刚导入时"。

**判据（`dsh_t5g4_undo_check` ⑦ 改写 6 项 + 新增 ⑱ 4 项）**：
⑦ 新出现的页面栈是空的、按钮灰（= 以出现时为基准）· 在新页改一处可撤销 · 撤销一次回到"这一页刚出现时"（页面本身撤不掉）·
**切回第一页：历史还在、按钮还能用、`undo_text` 正确**（用户报的现象）· 在第一页撤销只影响它自己的节点（每页互不干扰）；
⑱ 导入动作本身不进栈 · 导入之后做修改可以撤销 · **撤销到底 = 回到导入时的样子**（导入带来的节点与连线仍在）、不能越过 · 重做也回到"导入 + 修改"的末态。

---


## 八、新文件往哪放（落点规则，已拍板 2026.10.13）

| 你要加的东西 | 放哪 | 例子 |
|---|---|---|
| **新的算子**（一个节点一个文件） | `ops/<kind>/` | `ops/detect/FaceDetectOps.py` |
| **参数窗口 / 对话框**（独立弹出、有"确定/取消"） | `ui/`（同名 `.ui` 跟它同目录） | `ui/CircleParamsDialog.py` |
| **嵌进主界面的控件 / 面板** | `widgets/` | 流程图小地图 `widgets/flow_minimap`、帮助页 `widgets/help_panel` |
| **画布相关的类**（场景 / 节点项 / 连线项 / 视图） | `widgets/`；再大就开 `widgets/flow/` 子目录 | 照参考项目 `gui/node_editor/` 的 scene / node_item / edge_item / view 拆法 |
| **引擎、纯逻辑** | `core/` | `core/flow_engine`、`core/project_store` |
| **碰 Qt / 硬件的服务** | `services/` | `services/camera_service` |
| **节点自己的说明文本**（帮助页要显示的内容） | **跟着节点文件走** —— 算子声明的一部分（`NodeSpec` 加 `help_text` 字段），不集中到一个文件 | 写在 `ops/detect/FaceDetectOps.py` 里 |
| **门禁用例** | `tests/`（目标1 从 `temp\` 迁入后） | `tests/dsh_m5_output_check.py` |

**两个已确定的具体落点**：

1. **流程图右下角的"小地图 / 全图预览 + 快速移动视口"** ⇒ 新建 **`widgets/flow_minimap`**（`QGraphicsView` 子类：画 `FlowChart` 场景缩略图 + 视口矩形，拖动即移动主视口）；由 `main.py` 装配、跟随页签切换换绑 `scene`；**不需要改 `main.ui`**。
2. **日志位置新增"帮助"页**（解释当前选中节点的功能与参数含义、**逐节点不同文本**）⇒ ① 界面：新建 **`widgets/help_panel`**（`QTextBrowser`，挂进日志那个 `QTabWidget`）；② 文本：**写在各算子自己的文件里**（`NodeSpec` 加 `help_text`），继续守住"加一个算子 = 一个文件 + 一行注册"；③ 接线：`main.py` 把"选中节点变化"的信号连到 `help_panel.show_help(get_spec(name).help_text)`；④ 没写说明的显示"该节点暂无说明"。

⚠️ **两条硬点**：① 新建 `.ui` 时注意 `QUiLoader` 用的是**工作目录相对路径**（要么放根、要么写显式路径）；② "选中了哪个节点"这类状态仍由主窗口持有（`selected_node`），新控件通过**信号 / 回调**拿，不要自己去解析画布。

---


## 九、与开源参考项目（VisionFlow）的取舍（2026.10.13 定）

### 9.1 参考项目 VisionFlow 的目录分类（**原样收录**，方便直接查看）

> 来源：用户桌面上的说明文件（`C:\Users\Administrator\Desktop\文件说明 - 副本.md`，在仓库外）。它参考了 GitHub 上的开源项目，
> 是一个 **PyQt5 + 100+ 节点**的同类软件；下面是它的完整目录分类（**未做删减**，对照我们自己的分批计划看）。

```text
VisionFlow/
├── main.py                    # 应用入口 — 显式引导：AppContext → 发现节点 → 启动 GUI
├── requirements.txt           # Python 依赖 (PyQt5, opencv-python, numpy)
│
├── core/                      # 核心领域层 — 零 GUI 依赖，纯逻辑
│   ├── interfaces.py          # ABC 接口 — 层间契约 (INodeData, IVisionNodeData, ISrcFilesNodeData...)
│   ├── events.py              # 事件总线 — EventSystem pub/sub (EventType 枚举，handler(sender, **kwargs))
│   ├── ioc.py                 # DI 容器 — ServiceCollection / ServiceProvider (构造器注入)
│   ├── node_base.py           # 节点基类体系 (NodeBase → VisionNodeData → ROINodeData → SrcFilesVisionNodeData)
│   ├── workflow.py            # 工作流引擎 (拓扑排序 + 串行/并行执行 + 历史消息回调)
│   ├── project.py             # 项目模型 (ProjectItem + DiagramData + JSON 序列化)
│   ├── commands.py            # 命令模式 (撤销/重做) — 纯元组坐标，无 Qt 依赖
│   ├── registry.py            # 节点注册表 (type_name → type 映射)
│   ├── node_group.py          # 节点分组 (NodeGroup, NodeDataGroupBase — 工具箱分类)
│   ├── data_packet.py         # 数据包 (FlowableResult, FlowableInvokeMode, FlowableState)
│   ├── result_presenter.py    # 结果呈现 (ResultItem, VisionMessage, NodeResult, 几何/图像/表格结果)
│   ├── constants.py           # 共享常量 (GROUP_META 颜色/图标 — 单一数据源)
│   └── plugin_manager.py      # 旧版插件管理 (逐步迁移到 services/)
│
├── services/                  # 应用服务层 — 桥接 core ↔ gui
│   ├── app_context.py         # 中央 DI 容器 — 替代所有全局单例
│   ├── node_service.py        # 节点服务 — 封装 registry + groups 暴露给 GUI
│   └── workflow_runner.py     # 流程运行器 — 后台线程执行 + 生命周期管理
│
├── gui/                       # 用户界面 — 依赖 core 接口，不直接依赖具体类型
│   ├── main_window.py         # 主窗口 (接受 ctx 参数注入)
│   ├── theme.py · font_icons.py · presenters.py        # 主题系统 / FontIcon 系统 / Presenter 模板体系
│   ├── toolbox_panel.py · property_panel.py            # 左侧工具箱 / 属性编辑面板(动态反射)
│   ├── flow_resource_panel.py · image_viewer.py        # 图像源缩略图 / 图像查看器
│   ├── result_panel.py · log_panel.py · help_panel.py  # 结果面板 / 日志面板 / 帮助面板
│   ├── roi_editor.py · color_picker.py · crop_dialog.py · condition_editor.py
│   ├── start_page.py · template_dialog.py · dock_manager.py
│   ├── filter_box.py · message_center.py · guide_overlay.py
│   ├── widgets/               # 自定义控件 (grid_splitter_box.py · node_list_view.py)
│   └── node_editor/           # 流程图编辑器
│       ├── scene.py · node_item.py · socket_item.py · edge_item.py
│       └── link_drawer.py · editor_widget.py
│
├── nodes/                     # 视觉处理节点 (100+ 个，按领域分目录)
│   ├── sources/               # 数据源 (图像文件/摄像头/视频/Zoo测试集 14 个)
│   ├── preprocessings/        # 预处理 (灰度/翻转/旋转/缩放/阈值/通道分离/算术... 10 个)
│   ├── blurs/                 # 滤波 (高斯/铅笔素描/细节增强)
│   ├── takeoffs/              # 分割提取 (HSV范围/无缝融合/替换背景)
│   ├── morphology/            # 形态学 (腐蚀/膨胀/开/闭/梯度/顶帽/黑帽)
│   ├── conditions/            # 条件分支 (相等/大于/小于/范围内)
│   ├── template_matchings/    # 模板匹配 (Base64/SIFT/SURF)
│   ├── detectors/             # 检测 (Blob/Canny/Hough/QR/轮廓)
│   ├── features/              # 特征提取 (AKaze/Brisk/Fast/Freak/Kaze/MSER/Star)
│   ├── others/                # 其他 (拼接/透视变换/Haar/LBP/SVM/HOG/YOLOv3)
│   ├── video/                 # 视频 (MOG背景减除/视频写入)
│   ├── outputs/               # 输出 (OK/NG/通知消息)
│   ├── onnx/                  # ONNX 深度学习 (YOLOv5/年龄/性别/语义分割)
│   └── network/               # 网络通讯 (Modbus)
│
├── assets/                    # 资源文件
│   ├── projects/ · models/ (5 个 .onnx + 标签) · images/ (33 张) · icons/ · videos/
│
├── tests/                     # 测试
│   ├── test_execution_flow.py · test_history_results.py
│
└── WPF-VisionMaster/          # 原始 C# 源码 (参考用，不参与构建)
```

**与我们目录的对照**（详情见本节下面的"取舍"表）：它的 `core/` ↔ 我们的 `core/`；它的 `services/` ↔ 我们的 `services/`；
它的 `gui/` ↔ 我们的 **`ui/`（参数窗口）+ `widgets/`（画布 / 显示 / 图库 / 面板）**；它的 `nodes/` ↔ 我们的 `ops/`；
它的 `assets/` `tests/` ↔ 我们的 `image/` `tests/`；它的 `WPF-VisionMaster/` 我们不收（放在工程外）。


**它是什么**：一个 PyQt5 写的同类软件（100+ 节点、ONNX、Modbus），骨架 = `core/`（零 GUI 依赖：接口 ABC + 事件总线 + DI 容器 + 命令模式 + 注册表）+ `services/`（桥接层：AppContext / 节点服务 / 后台线程运行器）+ `gui/`（整个界面层，20+ 面板 + `node_editor/` 画布子包 + 主题与图标）+ `nodes/`（**按领域分 14 个子目录**）+ `assets/` + `tests/`。

| 结论 | 内容 |
|---|---|
| ✅ **借鉴** | ① `core/` + `services/` + `ui/` + `widgets/` 的分层（我们已有契约 / 零件 / 算法 / 界面这几类）；② `ops/` 按 kind 分的思路（**不学它的 14 个领域目录** —— 我们只有 14 个算子）；③ `services/` 这一层放"碰 Qt 与设备"的服务；④ **门禁用例进仓库**（**目标1** 落地：`temp\` → `tests\`）；⑤ 它的 `workflow_runner`（后台线程）与 `commands`（命令模式撤销 / 重做）**正是我们目标3 / 目标4 要的**；⑥ 画布类多了开 `widgets/flow/` 子目录的拆法 |
| ❌ **不照搬** | `interfaces.py`（接口 ABC）+ `ioc.py`（DI 容器）+ `events.py`（事件总线）+ `plugin_manager.py` + 主题系统 + FontIcon —— 那是为"100+ 节点 + 插件化 + 多人协作"设计的重架构；照搬要把 `main.py`（3327 行）彻底拆开、把显式引用全换成"注入 + 事件订阅"，并**打破"加一个算子 = 一个文件 + 一行注册"**，功能收益为零 |
| ❌ **不改命名风格** | 它用 `snake_case`，我们用 `CamelCase`（改名要动 38 条 import + 文档里几百处引用） |
| ❌ **不学"全代码搭界面"** | 它不用 `.ui`（界面全代码构造 + 主题系统）；我们用 `.ui` + `QUiLoader`，改成全代码要重写整个界面层 |

---


## 十、待用户拍板 / 未定项

| # | 事项 | 需要用户定的点 | 什么时候要 |
|---|---|---|---|
| 1 | ~~**目标3** 的**线程方案**~~ **已定并落地**（2026.10.15） | **分片执行**（不引入线程）· **进度显示先不做** · 范围只做"运行全部" · 取消保留已完成 | 已落地（见 §六） |
| 2 | ~~**目标4** 的**缓存上限数值**~~ **已定**（2026.10.15 用户拍板） | **内存 256 MB 为主 + 条数 400 作硬顶**；**视频序列帧单独分池**（乙方案） | 已定（见 §7.1） |
| 3 | ~~**目标4** 的**撤销范围 / 快捷键 / 栈上限**~~ **已定**（2026.10.15 用户拍板） | 范围 = **结构 + 参数 + 页面 + 节点拖动**（**不含图库**）；**快捷键先不做**（体系化做，见 §12.3）；栈上限 **50 步**；清栈 = 换页 / 载入方案 / 新建项目 / 删除页面 | 已定（见 §7.2） |
| 4 | **批次6 何时开工 / 范围要不要调整** | 批次6 = **UI 界面大改**（节点的修改 / 流程图预览控件 / 帮助页面 …），想法已入档 **§十二**；开工时机与范围由用户定 | 用户说开工时 |

---


## 十一、路径与资源索引

### 11.1 仓库内（= 工程根，也是 git 根）
| 路径 | 是什么 |
|---|---|
| `main.py`（+ `main.ui` · `SetCameraID.ui`） | **入口与主界面布局，留在工程根**（`QUiLoader` 按工作目录读）；目标2 收尾之后只剩 **885 行 / 32 个方法**（27 个界面·建图·路由 + **5 个弹窗出口薄壳**） |
| `core\` | 契约与零件：`NodeRegistry.py` · `ParamRules.py` · `ImageIO.py` · `Detector.py` · **`param_store.py`（`ParamStoreMixin`）· `project_store.py`（`ProjectStoreMixin`）· `flow_engine.py`（`FlowEngineMixin`）**（后三个 = 批次5 目标2 从 `main.py` 拆出）· **`host_contract.py`（宿主契约 `MainHost`：只为静态检查、运行时是空类 —— 批次5 目标3 收尾 B′）** |
| **`services\`** | **批次5 目标2 新建**：`camera_service.py`（`CameraMixin`）· `video_service.py`（`VideoMixin`）· `gallery_service.py`（`GalleryMixin`） |
| `ops\source\` · `ops\process\` · `ops\detect\` · `ops\sink\` · `ops\color\` | 算子（一个节点一个文件，按 kind 分） |
| `ui\` | 参数窗口与对话框（`LineParamsDialog.py` + **同目录的 `LineParamsDialog.ui`** 等） |
| `widgets\` | 画布 / 多页签 / 显示区 / 图库（`FlowChart.py` · `FlowPages.py` · `ImageGraphicsView.py` · `ImageGalleryWidget.py`） |
| `tests\` | **38 套门禁用例 + `dsh_run_all_checks.py`**（2026.10.14 起在工程内、**进 git**；脚本自带字体目录兜底） |
| `plan\VisionFlowNode_批次5技术方案_v2.0_2026.10.15.md` | **本文件**（批次5 口径真源） |
| `plan\VisionFlowNode_批次4技术方案_v1.53_2026.10.13.md` | 批次4 方案（**已冻结**，历史参考） |
| `plan\pyside6_开发日志.md` | 开发日志（markdown，LF；最开头是命名规则、末尾是《全项目里程碑索引》） |
| `plan\批次4_验收点清单_v1.md` | 批次4 验收点清单（照着点就能验收） |
| `plan\VisionFlowNode_用户手册_v1.0_2026.10.7.md` · `…代码说明书_v1.0…` · `…项目技术文档_v1.2…` | 三份冻结文档（**版本号不动**） |
| `image\` | 测试图像（如 `lena.png`） |
| `temp\` | 本地临时工具（截图 / 探针 / 一次性脚本，149 个）**被 `.gitignore` 忽略**；`temp\legacy\` 放 8 套历史留档用例 |
| `.dsh-meow\memory.db` | 跨会话记忆库 |
| `.gitignore` | 忽略 `temp/`、`__pycache__/`、`*.pyc` |

### 11.2 仓库外（**不上传 GitHub**）
| 路径 | 是什么 |
|---|---|
| `E:\opencv_python_3_8\backups` | 所有 `_backup_VisionFlowNoed_before_*` / `_at_*` 快照 + `_ui_preview` 截图**与《截图索引.md》**（73 张台账） |
| `E:\opencv_python_3_8\.venv` | Python 解释器（`…\.venv\Scripts\python.exe`） |
| `E:\opencv_python_3_8\save_test` | 用户的测试方案 |

### 11.3 门禁（**2026.10.14 起在工程内 `tests\`，进 git**）
- 一键跑：**`tests\dsh_run_all_checks.py`** ⇒ **42 套 972 项断言全过**（每个用例一个子进程，互不干扰）；★ 跑完它会**把实测套数 / 项数与本方案写的口径对一遍**，不一致直接算不合格；
- **★ 脚本自己设 `QT_QPA_FONTDIR=C:\Windows\Fonts`**（目录存在才设）—— 不设时"参数窗口宽度"4 项会假失败（见 §5.5 的环境坑）；
- 关键几套：`dsh_dlg_width_check`（参数窗口宽度护栏 31 项）· `dsh_imgio_check`（中文路径 16 项）· `dsh_m3_index_check`（收口产物自洽 13 项）· `dsh_doc_consistency_check`（文档 ↔ 代码一致性 15 项）· `dsh_t5g2_api_check`（拆 `MainWindow` 的"接口面契约" 8 项）· **`dsh_t5g3_batch_check`（"运行全部"分片执行 / 不阻塞 / 可取消 / 行为等价 / **画布只在勾「自动切换」时跟随** / **开关在批开始时定格** 33 项，2026.10.15 目标3 新增 + 同日两轮修正）**· **`dsh_t5g3_host_check`（宿主契约 `MainHost` 自洽性 5 项，2026.10.15 目标3 收尾 B′ 新增）**；
- ★ **新用例必须放 `tests\` 且名字叫 `*_check.py`** 才会被收集；`temp\` 只放**本机工具**（探针 / 截图 / 一次性脚本，**不进 git**），`temp\legacy\` 是 8 套历史留档用例；
- 门禁是**目标1 / 目标2 的判据**：目标1 三轮全程 **37 套 861 项全绿**；目标2 三批全程"**套数 / 断言数一个不少**"（新增 1 套 8 项 + `dsh_doc_consistency_check` 1 项 ⇒ **38 套 870 项**）。

---


### 11.4 GitHub 仓库

- **仓库地址：https://github.com/OvO641651/VisionFlow_Node**
- **批次4 目标5-M3 / M4 已提交**（提交标题 `批次4目标5-M3+M4修改，参考日志2026.10.12 23:45-2026.10.13 12:15`）。
- ★ **规矩不变**：**我不碰 git** —— 提交 / 打标签由用户操作；我做完了把该提交的东西备份到 `E:\opencv_python_3_8\backups` 并写日志。
- 仓库里有什么：`*.py` / `*.ui` / `image\` / `plan\`（方案 + 日志 + 验收点清单 + 三份冻结文档）+ `.gitignore`；
  **不在仓库里**：`temp\`（本机工具，`.gitignore` 忽略）、`backups\`、`.venv\`、`save_test\`。

### 11.5 IDE 里 import 出现"红线"的解法（PyCharm；用户 2026.10.14 定）

**现象**：代码能跑、门禁也全绿，但 PyCharm 里 `from core.ParamRules import clamp_int` 这类语句被标红、"未解析的引用"。

**原因**：`core` / `ops` / `ui` / `widgets` 是**顶层包**，运行时靠"工程根在 `sys.path` 上"解析（`main.py` 在根目录）；
而 PyCharm 的**静态索引**需要你明确告诉它"工程根就是导入的搜索起点"。

**解法（一句话）**：

> **选择项目文件夹（VisionFlowNoed）→ 右键 → 最下面"将目录标为" → 选择"源代码根目录"，即可解决导入出现红线的问题。**

（英文界面：**Mark Directory as → Sources Root**；成功后该文件夹图标变蓝。）

**配套几步**（若标完还红，按顺序试）：① 确认 PyCharm 打开的是**工程根**（Project 面板顶层应是 `VisionFlowNoed`，不是 `ops`/`core`，
也不是"只打开一个文件"的模式）；② 顺手 `File → Invalidate Caches… → Invalidate and Restart` 重建索引；
③ 确认解释器是 `E:\opencv_python_3_8\.venv\Scripts\python.exe`；
④ **判定标准**：在 `ops/detect/LineDetectOps.py` 里 **Ctrl + 左键点击 `clamp_int` 能跳到 `core/ParamRules.py`** ⇒ 索引真的解析成功了。

### 11.6 PyCharm 静态警告"未解析的特性引用"的处置（**2026.10.15：先登记 → 当天改用 B′ 根治 ✅**）

**现象**：打开 `core/flow_engine.py` 报 68 条、`core/project_store.py` 报 53 条（其余 Mixin 同理），
形如「类 'FlowEngineMixin' 的未解析的特性引用 '_image_key_of'」；`project_store.py:161` 另有一条
「应为类型 'SupportsWrite[str]'，但实际为 'TextIO'」。

**原因**：6 个 Mixin 的 `self.xxx` 里，**128 个名字（按文件计）是跨文件**的（定义在别的 Mixin 或 `main.py` 里）
—— PyCharm 只分析单个文件、看不到 `MainWindow` 把它们拼起来。这正是 §5.2 硬点 1 说的
"56 个宿主状态靠 Mixin 共享 `self`"，是**有意选择的代价**，不是代码错。

**实测（工具 `temp\dsh_t5g2_self_contract_check.py`）**：

| 文件 | `self.X` 名字数 | 跨文件名字 | 跨文件引用点 | 本文件自洽 |
|---|---|---|---|---|
| `main.py` | 78 | 29 | 44 | 49 |
| `core/flow_engine.py` | 55 | 20 | 55 | 35 |
| `core/project_store.py` | 30 | 19 | 45 | 11 |
| `core/param_store.py` | 10 | 3 | 4 | 7 |
| `services/camera_service.py` | 33 | 19 | 31 | 14 |
| `services/video_service.py` | 23 | 12 | 21 | 11 |
| `services/gallery_service.py` | 32 | 26 | 56 | 6 |
| **合计** | **261** | **128** | **256** | — |

**① 真缺失 = 0 处**（没有"整个工程都没定义"的 `self.X` ⇒ 不会 `AttributeError`）；门禁 **40 套 900 项全绿**。
（PyCharm 报的 68 / 53 是"**按问题条数**"，含同一名字的多处引用与它自己的类型检查项，口径不同、量级一致。
那条 `SupportsWrite[str]` vs `TextIO` 是 PyCharm/typeshed 对 `json.dump(fp, …)` 的老毛病，**改前快照里一模一样**，不是目标2 引入的。）

**当时的处置（A 方案：只登记、不改代码）**：在 PyCharm 里把这 6 个文件从该检查里排除 ——
`File → Settings → Editor → Inspections → Python → Unresolved references`，
在右侧 `Scope` 上新建一个 Scope（或用 `Exclude` 加路径）排除
`core/flow_engine.py` · `core/project_store.py` · `core/param_store.py` ·
`services/camera_service.py` · `services/video_service.py` · `services/gallery_service.py`
（`main.py` 不用排除）。**这一步本身仍然有效**（想"消音"随时可用）。

**★ 2026.10.15 当天改成 B′ 根治（用户拍板："修改代码，按照 B′ 做"）**：

> **背景**：用户看图后问"引用警告还在，不是说在目标3 中解决吗" ⇒ 复核后确认：目标3 走的是**分片执行**
> （不引入线程），`FlowContext` **不再是硬前置** ⇒ 这件事退化成"**纯粹为了让 IDE 干净**"的可选改造；
> 而助手既没做它、也没把这点写进 §6.5 遗留（**汇报疏漏，已认账**）。用户随后选择 **B′**。

1. **新增 `core/host_contract.py`**（**104 行**，其中 **65 行是声明**）：一个 `class MainHost(object)`，
   把 6 个 Mixin 依赖的 **65 个跨文件名字**（**25 个状态字段 + 40 个跨 Mixin 方法**）集中声明在它的
   `if TYPE_CHECKING:` 块里：
   - ★ **运行时它是空类**（`TYPE_CHECKING` 恒为 `False` ⇒ 声明段不执行）⇒ **零行为影响**；
   - ★ 清单**用脚本按实测算出来生成**（工具 `temp\dsh_t5g3_gen_host.py`），每行后面标"定义在哪个文件"；
   - ★ 方法用 `name: Any` 声明而不是写 `def` —— 既能被调用、又**不用跟着维护签名**（改了参数也不会误报）；
2. **6 个 Mixin 各改 2 处**：加 `from core.host_contract import MainHost` + 类改成 `class XxxMixin(MainHost):`。
   用"**真实继承一个空类**"而不是 `if TYPE_CHECKING:` 包住基类（后者各家 IDE / 类型检查器的支持不一致，不赌）。
   MRO 现在 = `MainWindow → CameraMixin → VideoMixin → GalleryMixin → FlowEngineMixin → ParamStoreMixin → ProjectStoreMixin → MainHost → object`；
3. **新增门禁用例 `tests\dsh_t5g3_host_check.py`（5 项，防腐化）**：
   ① 清单里每个名字都能在**真实 `MainWindow` 实例**上取到（不许声明不存在的东西）；
   ② 6 个 Mixin 里**所有跨文件 `self.X` 引用**都已声明（漏一个 ⇒ 那条警告就回潮）；
   ③ 清单 = 真正依赖的名字集合（**多 / 少 / 重复**都不行）；
   ④ **运行时 `MainHost` 是空壳**（`vars()` 里除 dunder 外无成员 —— 防"有人把真实现写进契约类"，这条最关键）；
   ⑤ MRO 关系（6 个 Mixin 直接继承 `MainHost`、`MainHost` 只继承 `object`、`MainWindow` 的 MRO 含它）；
4. **口径**：门禁 **39 套 895 项 → 40 套 900 项**。数字纠偏：需要声明的其实是 **65 个名字**，
   **不是**先前说的 87 个 —— 87 是"7 个文件全体"的跨文件名字数，其中 **22 个只有 `main.py` 引用**，
   而 `main.py` 的基类链里本来就有那 6 个 Mixin ⇒ 它**一条都不报**、不需要进契约；
5. ⚠️ **待人工确认（只能你来做）**：PyCharm 里这 6 个文件（`gallery_service.py` 58 条 / `flow_engine.py` 68 条 …）
   应**全部归零** —— 助手环境跑不了 IDE；若有个别残留，把残留清单贴出来，按清单补声明即可（门禁用例会同步提醒）。

**被否掉的选项（记下来，别以后重复讨论）**：
- **B″ 只声明状态字段**（25 个）：实测只消掉 **114 / 211** 个引用点，方法类那 **97 点**照旧报（`_show_static_image` / `_ask_dir` / `_append_log_hint` …）⇒ 等于做完还要看同一堆警告 ⇒ 不划算；
- **C 真组合化**（`FlowEngine(self)` 委托）：静态问题大部分消失，但用例要改 **27 个方法 × 35 套**，违背本批"调用点 0 改动" ⇒ 仍然否；
- **D 把 56 个宿主状态真正收敛成 `FlowContext`**：那是**结构性重构**、不是"让 IDE 干净"；只有**真线程化（§12.4）**才需要它 —— 别和 B′ 混为一谈。

## 十二、想法（未开发）—— 以后要补充开发时从这里挑

> **规矩（沿用《批次4 技术方案》第九篇章的做法）**：**没进当前批次排期的想法都记在这里**，每条写清"**是什么 / 为什么要做 / 前置条件**"；用户要补充开发时**从这里挑**，挑中的再排进某个批次的子里程碑。**《批次4 技术方案》§九 里的旧想法（9.8~9.11：输出目录自动建、参数联动置灰、圆最大半径控件、相机 id 预检、提示实时刷新、颜色提取多段阈值 / 其它颜色模型 / 阈值命中预览）继续留在那份文档里**，这里只记**批次5 之后**的新想法。

### 12.1 ★ 批次6：UI 界面大改（**未排期**；用户 2026.10.14 定；**原批次5 的「节点错误态图标」已并入这里** —— 当时它是批次5 的第二个条目）

**用户原话**："我打算在后续的批次6再把 ui 界面进行大改，包括节点的修改，添加流程图预览控件，帮助页面等内容，由于修改的内容比较多，所以设置一个批次6来实现。"

> 批次6 也按同一套编号：**批次6 → 目标1 ~ 目标4**（下面的四行依次对应，**都还没排期**）。

| 目标 | 是什么 | 为什么要做 | 前置条件 / 落点 |
|---|---|---|---|
| **目标1** | **节点的修改 / 视觉改版** | 节点项改成 VM 式：**左边状态图标（正常绿、出错变红）、右边节点名字**；可能连带调整节点类的绘制与命中区 | 用户 2026.10.12 原话："参考海康的 vision master，节点左边使用绿色显示图标，右边显示节点名字，如果该节点出错，绿色会变成红色……**现在不用实现**，因为**需要对节点类进行大改**，可能需要等到批次5之后再进行。" ⇒ 状态来源复用**通用错误通道**（`results` 里 `"__error__": True`）；**要动节点类 / 画布控件** ⇒ 排在批次5 的目录重构与拆 `MainWindow` 之后 |
| **目标2** | **流程图预览控件（小地图）** | 流程图右下角显示**全图缩略图 + 视口矩形**，拖动 / 点击即快速移动主视口 | 新建 `widgets/flow_minimap`（`QGraphicsView` 子类，画 `FlowChart` 场景缩略图）；由 `main.py` 装配、跟随页签换绑 `scene`；**不需要改 `main.ui`** |
| **目标3** | **帮助页面** | 在日志那个 `QTabWidget` 里加一页：解释**当前选中节点**的功能与参数含义，**逐节点不同文本** | 用户 2026.10.14 原话："我需要在日志的位置新添加一个帮助的页面，用于给用户解释当前选择的节点的的功能和一些参数含义，这可能需要对每个节点都需要添加不同的解释文本。" ⇒ 新建 `widgets/help_panel`（`QTextBrowser`）+ **`NodeSpec` 加 `help_text`**（文本写在各算子文件里 ⇒ 守住"加一个算子 = 一个文件 + 一行注册"）+ `main.py` 把"选中节点变化"信号连过去；没写说明的显示"该节点暂无说明" |
| **目标4** | **其它 UI 改动** | 用户在批次6 开工时可能再补：节点样式 / 主题 / 面板与停靠布局 / 快捷键 … | 到时候按用户指令补进本表 |

> **为什么整批放到批次6**：这几项**都要动 UI 层且互相牵连**（节点类 / 画布控件 / 主窗口面板），改动量大、回归面广 ⇒ 集中一个批次做，批次5 只承担**结构性重构**（目录 / 拆 `MainWindow` / 线程化 / 缓存与撤销）。

### 12.2 `NodeSpec.dialog_class` 声明式窗口路由（为"每节点一个窗口"铺垫）

现在 `main.py::on_node_double_clicked()` 是**硬编码 elif**（直线 / 圆 / 灰度三个专用窗口 + 通用窗口兜底）⇒ 改成"**专用窗口在算子文件里声明 `dialog_class`**、`main.py` 不再动"，这样"加一个算子 = 一个文件 + 一行注册"在"需要专用窗口"时也成立。**前置**：等用户真要做"每节点一个窗口"时一起做（用户 2026.10.13 已定："**每节点一个窗口暂时不做**"）。

### 12.3 ★ "快捷键体系"（用户 2026.10.15 提出，**未排期**；目标4 的撤销 / 重做已为它预留）

**用户口径**（原话）："**我打算后续再为全部控件和操作添加快捷键**，是否可以新创建一个文件来存放快捷键，还是说直接写到控件里面，这次先不做，可以写到《想法》里面。"

**怎么实现（Qt 三条路，按本项目现状推荐乙）**：

| 路 | 做法 | 评价 |
|---|---|---|
| 甲 | 在控件里直接 `QShortcut(QKeySequence("Ctrl+Z"), self.main_window, activated=槽)` | 散落各处、难查重、难做成"可配置"，**不推荐** |
| **乙（推荐）** | **`QAction` + `setShortcut()`**：把"一个操作"做成 action，菜单项 / 工具栏按钮都挂在**同一个 action** 上，快捷键写在 action 上 | **一处定义、菜单 + 按钮 + 快捷键三处同步**，`enabled` 也自动联动；撤销 / 重做已经是这个形态（`action_undo` / `action_redo`） |
| 丙 | `QShortcut` + **集中注册表**（纯数据表 + 装配时统一注册） | 便于以后做"快捷键可配置 / 冲突检测"，但要多一层"名字 → 方法"的解析 |

**放哪（回答"新建文件还是写控件里"）**：**两者都要，但分工**——
① **纯数据表 ⇒ `core/shortcuts.py`**（**零 Qt**：`[("Ctrl+Z", "undo"), ("Ctrl+Y", "redo"), ("Ctrl+S", "save_project"), ("F5", "on_continuous_execute"), …]`，可被用例直接断言，符合"零 Qt 逻辑进 `core/`"）；
② **注册与冲突检查 ⇒ `services/shortcut_service.py`**（**碰 Qt ⇒ `services/`**：遍历表 → 找 `QAction` 或建 `QShortcut` → 绑到对应方法，并按"**一套按键只做一件事**"查重、与既有快捷键不冲突）；
③ **控件自带的 action 仍写在控件里**（如撤销 / 重做），**集中表只放"全局快捷键"**（保存 / 打开 / 执行 / 停止 / 撤销 / 重做…）。

**为什么未排期**：得**先把"操作"收敛成 action**（撤销 / 重做是第一个），否则表里一行指向的方法还不存在。
**判据（到时候）**：表里每条按键**真实生效** + **无重复绑定** + 与既有快捷键不冲突。

### 12.4 ★ "真线程化"（= 原目标3 的方案 B）：**留档，等实据再启动**

**是什么**：把"算"搬进工作线程（`QThread` + worker，或 `QThreadPool` + `QRunnable`），结果 / 日志 / 进度用**信号**回主线程渲染。
**为什么现在不做**（2026.10.15 实测依据）：目标3 改成**分片执行**后已经不卡；而单张最慢只要 **28.1 ms**
（用户 `data` 目录最大 12 张 × 重流程 灰度→形态学梯度7×7×2→边缘提取），用户感知不到"单张卡一下"。
**什么时候该做**：出现"**单张 > 300ms**"的重流程（例如将来加"每帧深度学习推理""大图多档形态学"），
或者要"多核并行跑一批图"时。
**前置条件（代价，别低估）**：
1. `_execute_static` 要**拆成 compute / present 两半** —— 它现在把"算"（`_run_flow_pipeline`）与"碰界面"
   （`_update_execution_log` 写 QTableWidget · `_display_image` 刷 QGraphicsView · `_ensure_source_images_in_gallery`）揉在一个函数里；
2. **Qt 对象只能在主线程碰** ⇒ 执行前要把"这一页流程图"拍成**纯数据快照**（节点名 / 参数深拷贝 / 连线 / `stop_at` 的角色），
   工作线程不许碰 `NodeItem`（QGraphicsItem）；
3. `result_cache` / `current_static_image` / `flow_nodes` / `selected_node` 只能主线程写（或加锁）；取消用 `threading.Event`；
4. **先把 56 个宿主状态收敛成 `FlowContext`**（否则线程里没法安全读写主窗口状态）—— 这一步顺带能清掉 PyCharm 那 25 个"状态类"静态警告（§11.6）。
**参考**：开源参考项目 VisionFlow 的 `workflow_runner`（线程 + 信号）；本项目已把引擎抽到 `core/flow_engine.py`，地基是有的。

### 12.5 ★ "**页面新建 / 删除的撤销**"（用户 2026.10.15 决定**先不做**，技术要求按用户要求入档；未排期）

**用户口径**（原话）："1、**页面新建/删除的撤销我不打算做，可以把技术要求写到《想法》里面，等后续再做**。"

**做好之后对用户是什么行为**

| 用户动作 | 现在 | 做了撤销之后 |
|---|---|---|
| 点标签栏 **「+」新建页面** | 多一页并切过去 | 撤销 ⇒ 这一页**连同里面的节点 / 连线**被删掉、**自动切回原来那页**；重做 ⇒ 页回来 |
| 右键 **「删除页面」**（弹确认框） | 整页连同内容没了 | 撤销 ⇒ **整页复活**：标题 + 节点（名字/坐标/参数）+ 连线 + 每张图各自那份参数 |
| 标签上的 **「×」关页**（无确认框） | 同右键删除 | 同上（两个入口**共用一条命令**） |

**范围**：**切换页面本身不算一步**（不进撤销栈）；"新建项目 / 载入方案"**不是可撤销动作**（导入 = 新页面 ⇒ 该页栈本来就是空的，见 §7.9）。

**落点（四处，都在既有约定里）**
1. `widgets/FlowPages.py`：加 **`on_page_added(page)`** 与 **`on_page_removed(model, index)`** 两个回调（它本来就收 `on_page_switched` / `on_page_close_requested`）；
   ★ 采集必须在 `_remove_page()` 里的 `scene.clear()` + `deleteLater()` **之前**做；
2. `core/commands.py`（零 Qt）：加 **`AddPageCommand` / `RemovePageCommand`**（存模型 + 位置 + 页 key；`do/undo` 调 `ctx.create_page` / `ctx.drop_page`），
   与现有 8 个命令同一套"uid / 快照"风格；
3. `services/undo_service.py`：`_UndoContext` 加 **`capture_page(page)` / `create_page(model)` / `drop_page(page)`**；`_undo_note` 加 `"add_page"` / `"remove_page"` 两种 kind；
4. `main.py`：装配时接上两个回调（`on_page_added=self._on_flow_page_added`、`on_page_removed=self._on_flow_page_removed`）。

**数据模型与重建**：模型直接用现成的 **`_collect_page(page)`** = `{title, nodes[{name,x,y,input_source,params,params_by_image}], edges[[i,j]]}`；
重建照抄 `_apply_project()` 里那段（`append_pages([title])` → 逐节点 `_add_node_to_page` + 还原 `params` / `params_by_image` / `input_source` → 逐连线 `_add_edge_to_page`）。

**必须提前想清的五个点**
1. ★ **记录时机**：`add_page()` / `_remove_page()` 都会**切页**（`_remove_page` 删当前页时会先切走）⇒
   记录要放在**切页回调之后**（用 `on_page_added` / `on_page_removed` 在末尾通知）。v2.12 起"换页不再清栈"（§7.9），这个坑变小了，但顺序仍要对；
2. ★ **页 key**：页 key 是"图片 × 页面 × 执行方式"结果缓存的一部分 —— 恢复时**沿用旧 key**（`page["key"]` 手动设回；`_seq` 单调递增不会撞车）⇒
   连"这一页算过的结果缓存"都能复活；用新 key 则更干净但该页缓存作废、要重跑（**推荐沿用旧 key**）；
3. **页签顺序**：`append_pages` 只能**追加到末尾** ⇒ 恢复的页会跑到最后；要保序得给 `FlowPages` 加"在指定位置插页"（`insertTab`）；
4. **三个"页面附加状态"要一起带回来**（模型里没有、但影响行为）：`dirty`（未保存标记）· `project_path`（这一页对应的方案文件路径，"按页记"是既有语义）· `selected_node`；
5. **不该记的情况**：`delete_page()` 因"至少保留一页"直接返回 False、或用户在确认框点"取消" ⇒ **不能记命令**（否则会出现"从没发生过的动作"能被撤销）。

**判据（到时候的用例）**：① 新建页 → 撤销 ⇒ 页数回落、切回原页、标签标题消失；② **整页往返**：页内建 2 节点 + 1 连线 + 改一个参数 → 删页 → 撤销 ⇒
**`_collect_page()` 前后逐项一致**（节点名/坐标/参数/`params_by_image`/连线端点/`input_source`/标题）；③ 右键删除与 × 关页行为一致；
④ 不该记的两种情形不记；⑤ 恢复页的页 key 与缓存命中（若采用"沿用旧 key"）；⑥ **页签顺序的已知限制**用断言显式写出来（免得以后被当 bug 报）。

**工作量与风险**：`FlowPages` ~15 行 · `commands.py` ~50 行 · `undo_service` ~70 行 · `main.py` ~10 行 · 白名单 +2~4 个方法 · 用例 ~6~8 项（门禁套数不变、项数 +6~8）。
风险**中等**（涉及页面销毁 / 重建 + tab bar 操作），比缓存 LRU 高、与"拖动去抖"相当。

### 12.6 其它可能的小想法（待补充）

- 流程图控件如果再大改（节点 / 连线 / 交互），需要拆文件时按 §八 的落点规则开 `widgets/flow/` 子目录（照参考项目 `gui/node_editor/` 的 scene / node_item / edge_item / view 拆法）；
- 《批次4 技术方案》§九 那些没排期的想法（**9.8 参数校验范围外 / 9.9 目录规划 / 9.10 节点错误态图标 / 9.11 颜色提取增强**）仍然有效，挑的时候一并看。

## 十三、变更说明

1. **v1.0（2026.10.14，新建）**：按用户要求"开始批次5、先完成批次5 的技术文档"建立本方案。① **规矩照搬《批次4 技术方案》开头**（改前备份 / 改完写日志 / 三份文档冻结 / 以本方案为主），并补两条批次5 特有的：**重构类硬判据（行为零变化 + 门禁全过 + 界面零变化）**、**门禁与备份位置**；② 收录**现状体检**（21 个文件平铺、`main.py` 3327 行 / 117 方法 / 54 状态字段、38 条 import、3 处 `QUiLoader`、29 个方法被 40 套用例直连）；③ 收录**已拍板的四条**（目录方案 / `ui` 且 `main.ui` 留根 / 每节点一个窗口暂不做 + `temp\` 不进 git / 新文件落点规则）与**五条子里程碑**（M1 目录重构 → M2 节点错误态图标 → M3 拆 `MainWindow` → M4 线程化 → M5 缓存上限 + 撤销重做）；④ 收录**拆 `MainWindow` 的落地方法**（边界表 + 先 Mixin + 三条硬点 + 判据）；⑤ 收录 **M2 / M4 / M5 的初步设计**与**七条待拍板项**；⑥ 收录**与开源参考项目（VisionFlow）的取舍**、**新文件落点规则**、**路径与资源索引**。

2. **v1.1（2026.10.14，只改文档）**：按用户要求"**把 M2 去除**，我打算在后续的批次6再把 ui 界面进行大改，包括节点的修改，添加流程图预览控件，帮助页面等内容，由于修改的内容比较多，所以设置一个批次6来实现。这一点写到"想法（未开发）—— 以后要补充开发时从这里挑"里面，参考批次4的第九篇章" ⇒ ① **§3 去掉 M2（节点错误态图标）**，批次5 重排为 **M1 目录重构 → M2 拆 `MainWindow` → M3 执行线程化 → M4 缓存上限 + 撤销 / 重做**，并加一行说明它移到了哪儿；② **删掉原 §五（M2）整节**，其后各节中文序号前移一位（六→五 … 十一→十；子节 `6.x→5.x`、`12.x→11.x`），文内交叉引用（`§12.3`、`本方案 §12`、`见 §6`）同步；③ **新增 §十二《想法（未开发）—— 以后要补充开发时从这里挑》**（照《批次4 技术方案》第九篇章的做法）：**12.1 批次6：UI 界面大改**（① 节点的修改 / 视觉改版（VM 式状态图标、出错绿变红）；② 流程图预览控件（小地图）；③ 帮助页面；④ 其它 UI 改动 —— 每条写清"是什么 / 为什么要做 / 前置条件"并保留用户原话）、**12.2 `NodeSpec.dialog_class` 声明式窗口路由**（为"每节点一个窗口"铺垫）、**12.3 其它待补充想法**（含指向《批次4 技术方案》§九 9.8~9.11 的旧想法）；④ **§十（待拍板）去掉两条 M2 项与"三个顺带能力"那条**，变成 **M3 线程方案 / M4 缓存上限值 / 撤销范围·快捷键·栈上限 / 批次4 何时提交 / 批次6 何时开工** 共 5 项；⑤ 头部"版本 / 当前状态"同步。**（注：这一版当时的编号是 M1 目录重构 / M2 节点错误态图标 / M3 拆 `MainWindow` / M4 执行线程化 / M5 缓存 + 撤销；v1.1 起已重排，见下条。）**

3. **v1.2（2026.10.14，只改文档）**：用户指出两处 ——"① **技术文档内没有修改完全**，比如 M3 还是拆 `MainWindow`，这一步应该是 M2；② **批次5 采用参考批次4 使用批次-目标-M 的形式**，如果批次下面是目标再到 M 的子里程碑，现在把标题按照这个修改"。根因：v1.1 只把**章节的中文序号**前移了（六→五…），**标题里的 `M3`/`M4`/`M5` 编号没跟着改**，正文里还有 5 处（目录树两处、`snake_case` 那句、Mixin 表、"M3 拆出来的引擎"）。修改：
   ① **修净 M 编号**：`## 五、M3：拆 MainWindow` → **`## 五、批次5 目标1-M2：拆 MainWindow`**；`## 六、M4：执行线程化` → **`## 六、批次5 目标1-M3：执行线程化`**；`## 七、M5：结果缓存上限（LRU）+ 撤销 / 重做` → **`## 七、批次5 目标1-M4：…`**；正文 5 处 `M3`（拆 `MainWindow` 的）改成 `M2`；
   ② **采用"批次-目标-M"形式**：**批次5 → 目标1「重构」→ M1~M4**；§3 标题改成"批次5 目标1「重构」的子里程碑划分"、表里加上一段结构说明（并写明**日志条目标题按 `## 日期 批次5目标1-M1 时间` 这样写**）、表内 4 行改成 `目标1-M1~M4`；四个子节标题也都带上 `批次5 目标1-Mx`；
   ③ **批次6 照此办**：§12.1 标题改成"**批次6 目标1「UI 界面大改」（未排期）**"，表内四行改成 `目标1-M1~M4`；
   ④ 头部"版本 / 当前状态"同步；给 v1.0 那条补了"当时的编号"注（免得跟现在的编号混淆）。

4. **v1.3（2026.10.14，只改文档）**：用户纠正 ——"**我不是叫你在前面添加目标1，而是把 M1-4 直接改成目标1-4，M1 改成目标1，M2 改成目标2。重新重构技术文档**"。即批次5 这一层**不要 M 层**，直接就是 **目标1 ~ 目标4**（照批次4 的编号习惯）。修改：① 四个章节标题改成 `## 四、批次5 目标1：目录重构` / `## 五、批次5 目标2：拆 `MainWindow`` / `## 六、批次5 目标3：执行线程化` / `## 七、批次5 目标4：结果缓存上限 + 撤销 / 重做`；② §3 标题改成"**批次5 的目标划分**"、表头改成"目标"、表内四行改成 `目标1~目标4`，结构说明改成"**批次5 → 目标1~目标4（不分 M 层）**；日志标题按 `## 日期 批次5目标1 时间`"；③ **正文里所有 M 引用全部换成"目标N"**（顺序理由、铁律、现状体检、目录树、Mixin 表、线程化前置、落点规则、待拍板三项、路径索引、§11.3 标题）；④ §12 批次6 同样改成 `批次6 目标1~目标4`（不再写 `目标1-Mx`）；⑤ 头部"版本 / 当前状态"同步。**复核口径**：正文里**不允许再出现任何裸 `M1`~`M5` 编号**（脚本逐行查，见验证）。

5. **v1.4（2026.10.14，只改文档）**：按用户四条要求 ——"① 批次4 目标5-M3 / M4 的内容已经完成，并且已经上传到了 GitHub 上，把批次5技术文档中的'批次4 目标5-M3 / M4 这一段尚未提交'这一段话去除；② 把我这个项目的 GitHub 链接 https://github.com/OvO641651/VisionFlow_Node 也放到技术文档中；③ 把参考项目 `文件说明 - 副本.md` 里面的目录分类也写到技术文档里面，方便直接查看。"修改：
   ① **头部"代码基线"去掉"尚未提交"**，改成"**批次4 目标5-M3 / M4 已完成并已提交到 GitHub**"；② **头部"适用工程"补上 GitHub 仓库地址**，并新增 **§11.4 GitHub 仓库**（地址 + 本批提交标题 + "我不碰 git、提交由用户做" + 仓库里有什么 / 不在仓库里有什么）；
   ③ **新增 §9.1"参考项目 VisionFlow 的目录分类（原样收录）"** —— 把用户桌面说明文件里的**完整目录树**（`core/` / `services/` / `gui/`（含 `widgets/` 与 `node_editor/`）/ `nodes/`（14 个领域目录）/ `assets/` / `tests/` / `WPF-VisionMaster/`）原样抄进方案，并补一段"与我们目录的对照"；④ **§十 待拍板去掉"批次4 何时提交"那条**（已办）并把最后一条重编号为 4；⑤ 头部"版本 / 当前状态"同步。

6. **v1.5（2026.10.14，代码 + 文档）**：**批次5 目标1「目录重构」落地 ✅** —— 用户口径"开始批次5目标1的修改。由于这次修改太大，所以记得备份。对于拍板：1、SetCameraID.ui 留工程根。2、不用清除（`__pycache__`），留下来即可。"。① 改前**整份备份** `_backup_VisionFlowNoed_before_b5_m1_dirrefactor`（27 个顶层文件 + `plan/` + `temp/` + `image/`）；② 新建 `core/ ops/{source,process,detect,sink} ui/ widgets/ tests/`（各带 `__init__.py`），**18 个文件挪到位**、工程根只剩 `main.py` + `main.ui` + `SetCameraID.ui` + `pyside6.txt` + `.gitignore` + 级联 xml；③ **41 处代码 import + 60 个用例/工具文件的 import** 改成包路径；`ui/LineParamsDialog.py` 的 `.ui` 改成显式路径（1 处）；④ **37 套用例 + `dsh_run_all_checks.py` 进 `tests\`**（进 git）、8 套历史留档进 `temp\legacy\`、149 个工具留 `temp\`；⑤ 7 套"改前/改后"用例加 `before` 模式守卫（旧扁平备份与新包路径不兼容）；⑥ 两处用例适配：`dsh_doc_consistency_check` 改全树扫描、`dsh_m3_index_check` 的搜索路径加 `temp/` 与 `temp/legacy/`；⑦ **验收：`tests\dsh_run_all_checks.py` 37 套 861 项全绿 + 抓图证明界面零变化**（图已登记《截图索引》）；⑧ §4.4 换成"落地结果"表、§11.1 路径索引换成新布局、头部状态同步。

7. **v1.6（2026.10.14，代码 + 文档）**：**批次5 目标1 补做 —— 直线 / 圆各拆成一个节点文件**。起因 = 用户四条反馈里的第 2、3 条："直线检测和圆检测不是两个节点吗，为什么这两个节点的 `Detector.py` 不放在 `ops/` 下"、"把 `core\Detector.py` 文件中的圆检测和直线检测拆了，分开使用两个文件类来实现"。实情：原先"直线"被拆在**两处** —— 算法在 `core/Detector.py`（`DetectorShape.line_detector` / `circle_detector`），**节点声明却手写在 `core/NodeRegistry.py` 里**（`_run_line` / `_draw_line` / `_format_line` / `validate_line` + `NODE_SPECS` 两条），所以它两个都不符合"一个节点一个文件"。改法：
   ① 新建 **`ops/detect/LineDetectOps.py`** = `class LineDetector`（Canny + HoughLinesP）+ `_run_line` + `_draw_line` + `_format_line` + `validate_line` + `LINE_SPECS`；新建 **`ops/detect/CircleDetectOps.py`** = `class CircleDetector`（HoughCircles）+ 同构五件 + `CIRCLE_SPECS`；
   ② **`core/Detector.py` 变成兼容门面**（74 行）：`DetectorShape` 持有 `LineDetector` / `CircleDetector` 并**原签名转发** （`main.py` 的 `self.detector = DetectorShape()`、用例里的 `w.detector` 与 `dsh_morph_gray_check` 的 `hasattr(DetectorShape, "gray_bgr")` 断言全都照旧），另保留 `make_test_image()`（图片源"测试图"、三个参数窗口与两个用例都在用它）；
   ③ **`core/NodeRegistry.py` 移走 158 行手写代码**（`_run_line` … `validate_circle` + 两条登记）⇒ **387 → 244 行**，改成 `from ops.detect.LineDetectOps import LINE_SPECS` / `from ops.detect.CircleDetectOps import CIRCLE_SPECS` + `_register_category(…, KIND_DETECT)`（与其余 5 个分类完全同构）；顺手清掉它不再用的 `import cv2` 与 `from core.ParamRules import …`；
   ④ 改前备份 `_backup_VisionFlowNoed_before_line_circle_split`（6 个源码文件 + `plan/` + `tests/`）。
**验证**：py_compile 全过；算子总数仍 **14**；`直线` / `圆` 的 kind=detect、draw 与 validate 都在；各跑一次 lena ⇒ **数据层未被改**（`out is img` 真）+ 检出 64 条直线 / 7 个圆；**全量门禁 37 套 861 项全绿**。
**答复（用户同一轮的另两问）**： IDE 里的"未解析的引用"红线是**静态索引**问题（运行时/门禁全绿 ⇒ 代码没错）：确认用 IDE 打开的是**工程根**、把工程根标为 **Sources Root**（PyCharm）/ 在 VSCode 里配 `python.analysis.extraPaths`，并选对解释器 `E:\opencv_python_3_8\.venv\Scripts\python.exe`，必要时 Invalidate Caches 重建索引；`__init__.py` 的作用 = 把目录标记成 **Python 包**（让 `import core.X` 是"包内模块"、IDE 与打包工具都认），里面没内容是因为**不需要任何初始化副作用**（算子注册仍由 `NodeRegistry.py` 显式 import，不靠包自动注册）。

8. **v1.7（2026.10.14，代码 + 文档）**：**批次5 目标1 第二轮 —— `ops/` 按"树分组"重排 + 节点改名 + 树控件同步**。用户口径："① 将这一点下面的话放到技术文档和修改日志中：选择项目文件夹(VisionFlowNode)→右键→最下面"将目录标为"→选择"源代码根目录"，即可解决导入出现红线的问题。② 先按方案 B 执行，后续节点多了我再修改整理，现在还不需要分二级目录……把"直线""圆"分别改名为"直线识别""圆识别"，把直线识别、圆识别、人脸识别这三个节点放到 detect 文件内；再创建一个树干名为"颜色处理"，里面的树枝为"颜色提取"这一个节点，颜色处理树干也创建一个新的文件夹存放……其他 6 个节点直接放到 process 文件夹中。③ 在修改代码目录的同时也要修改 main.ui 文件中的树控件。④ source 和 sink 文件夹中的内容可以不用动"。
   ① **`ops/` 按树分组**：`source/`（采集 3，不动）· `sink/`（输出 1，不动）· **`process/` 拆成 6 个节点文件**（`GrayOps.py` / `InvertOps.py` / `BlurOps.py` / `ThresholdOps.py` / `MorphologyOps.py` / `EdgeExtractOps.py`，原 `ProcessOps.py` 388 行删除）· `detect/`（3 个：直线识别 / 圆识别 / 人脸识别）· **新建 `ops/color/`**（"颜色处理"这一类，先放 `ColorExtractOps.py`；将来放颜色分割 / 颜色转换）——**暂不分二级目录**；
   ② **公共零件**提到 **`core/ImageOps.py`**：`to_bgr()` / `apply_to_roi()` / `odd_kernel()`（原来在 `class ProcessOps` 里）；
   ③ **节点改名**：直线 → **直线识别**、圆 → **圆识别**（注册表声明 / `main.py::on_node_double_clicked` 路由 / `ui/LineParamsDialog.py`、`ui/CircleParamsDialog.py` 里的名字判断 / 11 个用例 / `main.ui` 树 / `widgets/FlowChart.py` 的示例树）；
   ④ **`main.ui` 树控件**：「检测」组里两项改名、「识别」组只剩「人脸识别」、**新增顶层组「颜色处理」→「颜色提取」**（排在「新建项目」之前）；
   ⑤ **两份冻结文档被逼出来的最小同步**（门禁的"文档一致性"用例会校验文档提到的 `.py` / 符号真实存在、以及 §五 算子表 ↔ 注册表）：《项目技术文档》13 处（算子表里的节点名与实现文件名、分层图、目录树、加算子那段的说明）、《代码说明书》23 处（文件总览、分层图、`NodeIdentity` 那章的文件作用、原处理类那一章的标题与 API 表、`Detector.py` 的定位）——**两份文档的版本号都没动**（仍是 v1.2 / v1.0）；
   ⑥ **PyCharm 红线解法**入档（用户原话那句），见新增的 **§11.4**；
   ⑦ 改前备份 `_backup_VisionFlowNoed_before_tree_group_dirs`。
   **验证**：树分组 = 采集(4) / 处理(6) / 检测(直线识别·圆识别) / 识别(人脸识别) / **颜色处理(颜色提取)** / 新建项目；算子总数仍 **14**；改名的三个节点都能 `get_spec` 到；抓图 `m1b_after_tree_groups.png` 已登记《截图索引》；**全量门禁 37 套 861 项全绿**。
   **过程中修掉 4 个自伤**：① 我在用例的中文字符串里嵌了 ASCII 双引号 ⇒ `dsh_source_check.py` SyntaxError（老教训又踩一次，改用「」）；② 上一轮脚本在 `dsh_source_check` 处中断，`dsh_morph_gray_check.py` 的 `ProcessOps` 导入/检查没改到（补上）；③ `dsh_source_check.py` 里那行 `ProcessOps` 导入其实没人用（删掉）；④ 文档一致性用例抓出《代码说明书》里还有两处旧引用（补干净）。

9. **v1.8（2026.10.14，代码 + 文档）**：**批次5 目标1 第三轮**。用户口径："1、main.ui 文件中把"检测"和"识别"树干合并成"检测识别"，里面的 3 个节点全部放到"检测识别"中。2、把 SourceOps.py 文件也拆了，拆成三个节点，图像源，视频源，相机源。放到 source\ 目录下"。
   ① **`ops/source/` 拆成 3 个节点文件**：`ImageSourceOps.py`（图片源：`IMAGE_EXTS` / `first_image_in_folder` / `_load_image` / `_cached_test_image` / `run_source` / `IMAGE_SOURCE_SPECS`）· `VideoSourceOps.py`（视频源：`_open_video` / `video_info` / `run_video` / `VIDEO_SOURCE_SPECS`）· `CameraSourceOps.py`（相机源：`CAMERA_FRAME_PROVIDER` / `set_camera_frame_provider` / `run_camera` / `CAMERA_SOURCE_SPECS`）；原 `SourceOps.py`（322 行）删除，三个文件各 163 / 113 / 63 行；
   ② **`main.ui` 树干合并**：「检测」+「识别」⇒ **「检测识别」**（直线识别 / 圆识别 / 人脸识别 三个叶子都在里面）；「颜色处理」组保持不动；顺手修掉上一轮插入「颜色处理」时"识别"组收尾标签多一个空格的缩进瑕疵；
   ③ **连线三处**：`core/NodeRegistry.py`（`SOURCE_SPECS` → 3 个 SPECS、3 条 `_register_category(…, KIND_SOURCE)`）、`main.py`（4 处导入：`set_camera_frame_provider` 归相机源文件、`video_info` 归视频源文件）、4 套用例（删 3 处没用到的 `import ops.source.SourceOps`、`SourceOps.video_info` → `video_info`）+ 1 个工具脚本；
   ④ **两份冻结文档再次最小同步**（《项目技术文档》9 处、《代码说明书》4 处：算子表实现文件列、分层图、目录树、四个入口、原大类文件那一章的标题与说明）—— **版本号仍不动**（v1.2 / v1.0）；
   ⑤ **门禁断言数**：`dsh_m2_check` 里「识别分组」那条已不适用 ⇒ 换成**更硬的**「识别树干必须已并入检测识别」，所以 **断言总数仍是 861**（如果只是删掉一条会变成 860 —— 判据"套数/断言数一个不少"要守住）；
   ⑥ 改前备份 `_backup_VisionFlowNoed_before_source_split`；
   ⑦ 验证：树 = 采集(4) / 处理(6) / **检测识别(3)** / 颜色处理(1) / 新建项目；算子仍 **14**；三个源各跑一次正常；抓图 `m1c_after_merge_groups.png` 已登记《截图索引》；**全量门禁 37 套 861 项全绿**。

10. **v1.9（2026.10.15，只改文档）**：**批次5 目标1 收口 + 补写设计说明**。用户口径："1、test/ 这个文件夹是什么时候创建的，是干什么的。是否需要上传到 GitHub。2、批次5 目标1 的内容是否已经完成，还有什么遗漏的，如果没有，则总结批次5 目标1 的内容，并更新修改日志和技术文档，把节点文件为什么使用函数而不使用类也详细写到技术文档里面。新的文件目录安排也更新到技术文档里面。"。
   ① **§11.3 门禁口径改过来**（原来还写着"现在在 `temp\`、批次5 目标1 之后进 `tests\`" —— 已经落地了）⇒ 改成 "**2026.10.14 起在工程内 `tests\`，进 git**"，一键跑 = `tests\dsh_run_all_checks.py`，并写明"新用例必须放 `tests\` 且叫 `*_check.py`"、`temp\` 只放本机工具（`legacy\` = 8 套历史留档）；
   ② **新增 §4.5「目标1 落地后的目录（现状速查）」**：把三轮之后的**真实目录树**逐行写出来（14 个节点文件、`services/` 标注"目标2 才建"），并给出"`main.ui` 树干 ↔ 文件夹"对应表 + "kind 与文件夹无关" + "加一个算子只动三处"；
   ③ **新增 §4.6「节点文件为什么写成‘函数 + 声明表’、而不是类」**（用户提问后补写）：现状表（契约用类 / 行为用函数 / 登记用数据）+ **七条理由**（节点是纯变换无状态 · 注册表要查表不要多态 · 声明表天然是数据 · 一个节点一个文件 diff 最小 · 契约一眼看全 · 测试好写 · **依赖方向干净：节点文件不 import 注册表 ⇒ 无循环导入**）+ 一句话判据 + "真改成类的五条代价、收益 0" + "什么时候该用类（算法族 / Qt 控件）"；
   ④ **《项目技术文档》事实同步 6 处**（版本号不动）：无头冒烟脚本的位置 `temp\` → `tests\`、目录树里 `批次5-M3` → `批次5 目标2`（两处）、`tests/` 那行从"★ 批次5-M1 把 temp\ 里 37 套迁进来"改成"已迁入"、`批次5-M1 只挪目录` → `批次5 目标1`、§10.5 标题里的 `批次5-M3` → `目标2`；
   ⑤ **`.gitignore` 注释更新**（原来写"37 套用例会在批次5-M1 时迁到 tests/ 正式进仓库"⇒ 已完成）；
   ⑥ 《批次4 技术方案》是**已冻结的历史文档**，里面的 `批次5-M1/M3` 旧编号与 `%TEMP%` 属当时事实 ⇒ **不动**；开发日志里的历史条目同理**不动**。

11. **v2.0（2026.10.15，代码 + 文档）**：**批次5 目标2「拆 `MainWindow`」落地 ✅**。用户口径："**现在完成到了批次5目标1，开始批次5目标2**"；三个待拍板项用户都选了推荐项 —— **① 分 3 批做**（每批独立跑门禁）· **② 弹窗出口"甲"方案**（在 `main.py` 留 `_warn` / `_info` / `_ask_*` 薄壳，Mixin 只调 `self.*`）· **③ 加更硬的门禁断言**（"拆分前后 MainWindow 方法名集合一致"⇒ 收紧成"117 个方法一个不少 + 只允许 5 个薄壳新增"）。
    ① **第 0 步**：改前整份备份 `_backup_VisionFlowNoed_before_t5g2_split_mainwindow`（98 个文件）+ 基线门禁 + 改前截图；**基线先红了 4 项**，根因 = 漏设 `QT_QPA_FONTDIR`（详见 ⑥）；
    ② **弹窗出口收口（甲）**：`main.py` 新增 5 个薄壳、改写 **13 处**弹窗调用点（`save_project_as` / `_write_project_file` / `open_project` / `load_project` ×7 / `_open_camera_device` / `update_frame` / `add_folder_to_gallery`）⇒ **行为零变化**（收口后门禁复跑仍 37 套 861 项全绿）；这是"用例给 main 打补丁"那条硬约束的解法（见 §5.2 第二条）；
    ③ **机械搬运**（工具 `temp\dsh_t5g2_split.py`，AST 按方法名原样剪贴 + 只生成用得到的 import）：**第 1 批** `core/param_store.py`（11 方法 / 175 行）+ `core/project_store.py`（13 方法 / 413 行，连带 `_fingerprint_value`）⇒ `main.py` 3351 → 2793 行；**第 2 批** `core/flow_engine.py`（34 方法 / 1104 行，连带 `_result_note` / `_result_error` / `LOG_ERROR_MARK`）⇒ 1709 行；**第 3 批** `services/camera_service.py`（12 / 314）· `video_service.py`（8 / 219）· `gallery_service.py`（12 / 339）⇒ **888 行**；`VIDEO_ROI_KEY` 落 `core/param_store.py` 并在 `main.py` 再导出（用例有 `m.VIDEO_ROI_KEY`）；类头 = `class MainWindow(CameraMixin, VideoMixin, GalleryMixin, FlowEngineMixin, ParamStoreMixin, ProjectStoreMixin):`；
    ④ **两条纠偏**（v1.x 写错的地方）：`MainWindow` **没有 Qt 基类**（照 v1.x 的示例写 `…, QMainWindow` 会直接 `NameError`，本批踩过一次）；`core/project_store.py` **不是零 Qt**（`NodeItem` / `QPointF`）；
    ⑤ **新增门禁用例 `tests\dsh_t5g2_api_check.py`（8 项）**：117 个方法一个不少 / 清单无重复 / 没有意外新增（只允许 5 个薄壳）/ 6 个 Mixin 都在 MRO / **Mixin 模块不出现 `QMessageBox.` `QFileDialog.`** / Mixin 模块不 `import main` / `main.py` ≤ 1200 行 / `m.VIDEO_ROI_KEY` `m.LOG_ERROR_MARK` 仍读得到；**门禁口径 37 套 861 项 → 38 套 870 项**；
    ⑥ **口径升级 + 环境兜底**（均为"换成更硬的"，不是删断言）：`dsh_doc_consistency_check` 的套数断言从"与冻结文档相等"改成"**冻结文档只增不减 + 现行《批次5 技术方案》精确相等**"（多出 1 项）；`dsh_run_all_checks.py` ① **自己设 `QT_QPA_FONTDIR`**（不设时宽度 4 项假失败：857 过 / 4 失败 → 861 过 / 0 失败）② 跑完**校验实测套数 / 项数与本方案写的一致**；
    ⑦ **验证**（详见 §5.5）：38 套 870 项全绿 · 界面改前改后截图 **sha256 完全相同**（`a84f5a04…d8ee`）· `temp\dsh_t5g2_orphan_check.py` 孤儿全局名 **0 处** · `temp\dsh_t5g2_split.py --coverage` **117 = 90 + 27 不丢不重** · `MainWindow()` 正常构造 / 算子仍 14；两张新截图已登记《截图索引》（77 → 79）；
    ⑧ **本节新增** §5.4 落地结果 / §5.5 验证 / §5.6 纠偏与遗留；§5.1 加纠偏注、§5.2 补第二条硬约束与类头纠偏、§5.3 判据改成"套数 / 断言数一个不少"、§11.1 补 `services\` 与三个 core 新文件、§11.3 门禁口径换 38 套 870 项、头部版本 / 门禁基线 / 当前状态同步；**v1.9 已留档到 `backups\VisionFlowNode_批次5技术方案_v1.9_2026.10.15.md`**。

12. **v2.1（2026.10.15，代码 + 文档）**：**批次5 目标2 收尾**。用户口径：先问"（PyCharm 截图）调用存在警告"+「告诉我批次5目标2还存在什么问题」，我给出实测分析（`self` 契约 261 个名字 / 跨文件 256 处 / **真缺失 0**）与问题清单后，用户点选：**静态警告按 A 方案（只登记不改代码）**，**收尾做 a + b + c**（清死 import / 同步 §4.5 / 修 `core/ → widgets/` 倒挂）。
    ① **清掉 `main.py` 里 17 个"只被搬走的方法用过"的 import**（`deque` / `json` / `time` / `read_image` / `QBrush` / `QColor` / `SOURCE_KEY` / `run_validation` / `node_level_param_keys` / `SAVE_OVERLAY` / `SOURCE_*` / `close_all_recordings` / `set_*_provider`）；**保留 4 个故意的再导出**（`VIDEO_ROI_KEY` · `LOG_ERROR_MARK` · `KIND_SOURCE` · `result_bbox`，用例把 `main` 当聚合入口读）—— ★ **我第一版把 `KIND_SOURCE` / `result_bbox` 也删了 ⇒ `dsh_source_check` / `dsh_m3_video_check` / `dsh_m4_camera_check` 三套直接 `AttributeError`、门禁当场抓出**，恢复后已就地写注释（教训：**清"没人 import 的 import"之前，必需先查用例是否以 `m.<名字>` 读它**）；
    ② **修 `core/ → widgets/` 倒挂**：新增 `core/NodeRegistry.py::is_bound_node(binding)`（按"节点对象一定带 `name` / `params`"判断），把 `core/flow_engine.py` 与 `core/project_store.py` 里 4 处 `isinstance(binding, NodeItem)` 换掉、删掉两处 `from widgets.FlowChart import NodeItem` ⇒ **`core/` 对 `widgets` 的引用归零**（复核 0 处）；
    ③ **§4.5 目录速查同步**（`services/` 真实内容、`tests/` 38 套、`main.py` 885 行 / 32 方法）；§5.4 加"收尾"行、§5.5 数字改 885、§5.6 补"收尾记录 + 已知静态警告 + 遗留（56 宿主状态）"、§一 现状体检表加 2026.10.15 复核纠偏注（56 状态 / 27 方法 × 35 套）；
    ④ **新增 §11.6**（PyCharm 静态警告的实测数据表 + 排除步骤 + 被否掉的 B / C 两个选项的理由），并在 §5.6 登记；
    ⑤ 头部"版本 / 当前状态"同步；`main.py` 888 → **885 行**；
    ⑥ **验证**：门禁 **38 套 870 项全绿**（套数 / 断言数一个不少）+ 改前改后界面截图 **sha256 仍完全相同** + 孤儿名 0 + self 契约真缺失 0 + `MainWindow()` 正常构造 + 算子仍 14；改前备份 `_backup_VisionFlowNoed_before_t5g2_cleanup`、**v2.0 已留档到 `backups\VisionFlowNode_批次5技术方案_v2.0_2026.10.15.md`**。

13. **v2.2（2026.10.15，只改文档）**：**批次5 目标2 完工收口**。用户口径："① **把现在的目录放到技术文档的批次5目标2中**。② **批次5目标2是否已经完工，若全部完成了则对批次5目标2的内容进行总结，并完成修改文档和技术文档的修改**。"
    ① **新增 §5.7《目标2 落地后的目录（现在的真实目录）》**：把**实测的真实目录树**逐行写出来（`main.py` 885 行 / `core/` 8 个文件含 3 个 Mixin / `services/` 3 个文件 / `ops/` 14 个节点文件 / `ui/` 4 个 / `widgets/` 4 个 / `tests/` 38 套 / `temp/` 188 个 / `plan/` 7 份），**每个文件都带真实行数**（口径 = `(Get-Content <文件>).Count`，与"`main.py` 拆前 3327 行"同口径），并写明"这张表怎么读"（885 行 = 27 个界面·建图·路由方法 + 5 个薄壳；业务逻辑 = 6 个 Mixin、90 个方法）；
    ② **新增 §5.8《完工判定（✅ 目标2 已完工）》**：8 条判据逐条给实测结果（门禁 38 套 870 项全绿 · 接口面 8 项 · 界面 sha256 相同 · 孤儿名 / 真缺失 0 处 · 覆盖度 117 = 90 + 27 · 冒烟 · 文档同步 · 备份链完整），结论 = **目标2（含收尾）全部完成**，批次5 剩目标3 / 目标4；
    ③ **§5.4 收尾行**补 `project_store.py` 413→412、`flow_engine.py` 1104→1103（各去掉 1 行被搬空的 import）；
    ④ **开发日志**：按用户要求写《**总结：批次5 目标2「拆 `MainWindow`」整体总结**》（用户明确要求时才写总结）+《全项目里程碑索引》批次5 行补该总结 + 本方案文件名换 v2.2；
    ⑤ 头部"版本 / 当前状态"同步；**v2.1 已留档到 `backups\VisionFlowNode_批次5技术方案_v2.1_2026.10.15.md`**；
    ⑥ 本轮**只改文档、不改任何代码**（用户 2026.10.15 明确："我说了先不要动代码，那么这次对话就不要改代码"）。

14. **v2.3（2026.10.15，代码 + 文档）**：**批次5 目标3「执行线程化」落地 ✅ —— 采用"分片执行"**。用户口径："**现在开始批次5目标3的修改**，路径 `E:\opencv_python_3_8\data` 中有大量图片，可以拿来测试，但是**别乱动该文件夹里面的内容**"；方案讨论阶段用户点选四条拍板：**① 先做分片（实测后再定要不要真线程）· ② 进度显示先不做 · ③ 只做"运行全部" · ④ 取消保留已完成的结果与日志**。
    ① **诊断（实测才是靶心）**：真正卡死的只有 `run_all_images` 那个**同步 for 循环**（整个批量期间事件循环被占死 ⇒ 界面不刷新、`stop_batch()` 置的标志读不到 ⇒ "停止"在批量中间几乎无效）；**视频 / 相机自动播放本来就是 QTimer 分片、不卡**；全工程**没有任何 `processEvents()`**；
    ② **改法**：`services/gallery_service.py::run_all_images` 同步 for → **分片状态机**（`self._batch_state` 装进度与"开始时的画面 / 选中项" + `QTimer.singleShot(0, self._batch_step)` 立刻返回 + 新增 `_batch_step()` / `_batch_finish(hint)`）；`main.py::__init__` 新增 `self._batch_state = None`（宿主状态 56 → 57）；**防重入**（批量跑着时再点"连续执行" ⇒ 忽略 + 一行"批量执行中，本次忽略"）；`stop_batch()` 语义不变但**真的能中断批量了**；**视频 / 相机一行不动**；
    ③ **行为等价（一条没改）**：连续执行 = 选中节点 + 全部上游 · 单步 = 只跑选中那一个 · 结果缓存键 = 图片 × 页面 × 执行方式 · 相机帧不进缓存 · 执行 / 渲染路径绝不弹 `QMessageBox` · 日志逐张累积 · 单张出错跳过继续 · 不勾"自动切换"时跑完还原画面 / 选中项 / 图片源 · 取消 = 干净急停（分片边界天然没有"半张图"）；
    ④ **新增门禁用例 `tests\dsh_t5g3_batch_check.py`（25 项）**：不阻塞 / 逐张累积 / 结尾文案 / **与串行逐像素一致 + 3 张结果互不相同** / 中途"停止"（没跑满 + 保留已完成 + 复位 + 还能再跑）/ 中途取消勾选 / 自动切换两态 / 单张出错跳过 / 防重入；⇒ 门禁口径 **38 套 870 项 → 39 套 895 项**；
    ⑤ **老用例一处适配**：`dsh_m2_v5_check`（它点"连续执行"按钮间接触发批量）因为"**分片是异步的**"补了 `wait_batch()` 等待事件循环 —— **判据一条没改**（这是门禁当场抓出的真回归：改完首跑它 5 项失败）；
    ⑥ **实测（用户给的 `data` 目录，只读；工具 `temp\dsh_t5g3_bench.py`）**：图取该目录**最大的 12 张**、流程取偏重的"灰度 → 形态学(梯度 7×7 ×2) → 边缘提取" ⇒ **单张最慢 28.1 ms / 中位 6.7 ms / 平均 8.7 ms**；**批量期间 10ms 定时器触发 8 次**（分片）vs **同步 for 对照 0 次**（改前行为，事件循环被占死）；**取消延迟 6.9 ms**；**界面截图 sha256 仍与基线完全相同**（零新界面元素）；⇒ 结论 **不上方案 B（真线程化）**，把它连同前置条件与"什么时候该做"记进 **§12.4**；
    ⑦ §六 从"初步设计"整节改写为"**已落地**"（6.1 诊断 / 6.2 改法 / 6.3 实测证据 / 6.4 判据与结果 / 6.5 遗留）；§3 目标表把目标3 标 ✅；§十 待拍板第 1 项标"已定并落地"；§11.3 门禁口径换 39 套 895 项；§一"执行模型"行补 2026.10.15 已改的注；头部版本 / 门禁基线 / 当前状态同步；**v2.2 已留档到 `backups\`**；
    ⑧ 用户还提了一条环境事实：`E:\opencv_python_3_8\data` 里有大量图片可作真实测试数据 —— 本轮**只读**使用（`import_paths` 读进内存），**没有往该目录写任何东西**（工具里也没加"输出图像"节点）。

15. **v2.4（2026.10.15，代码 + 文档）**：**目标3 收尾 —— 按用户"修改代码，按照 B′ 做"落地【宿主契约 `MainHost`】，把 PyCharm 静态警告根治**。
    ① **背景/认账**：用户看图后问"引用警告还在，不是说在目标3 中解决吗" ⇒ 复核确认：目标3 走的是**分片**（不引入线程），`FlowContext` **不再是硬前置** ⇒ 这件事退化成"**纯为 IDE 干净**"的可选改造；而助手**既没做、也没写进 §6.5 遗留**（汇报疏漏，已在对话里认账）。用户随后在 B′ / B″ / 维持 A 之间选了 **B′**；
    ② **新增 `core/host_contract.py`**（104 行，其中 **65 行声明** = **25 个状态字段 + 40 个跨 Mixin 方法**）：`class MainHost(object)` 把清单集中声明在 `if TYPE_CHECKING:` 里 ⇒ **运行时是空类、零行为影响**；清单**由脚本按实测算出**（新增 `temp\dsh_t5g3_gen_host.py`，每行标"定义在哪个文件"）；方法用 `name: Any` 声明（不用维护签名）；
    ③ **6 个 Mixin 各改 2 处**：`from core.host_contract import MainHost` + `class XxxMixin(MainHost):`（用**真实继承空类**，不赌"条件基类"的 IDE 支持）；MRO 实测 = `MainWindow → CameraMixin → VideoMixin → GalleryMixin → FlowEngineMixin → ParamStoreMixin → ProjectStoreMixin → MainHost → object`；
    ④ **新增门禁用例 `tests\dsh_t5g3_host_check.py`（5 项）**：① 清单名字都能在真实 `MainWindow` 实例上取到 · ② Mixin 的跨文件 `self.X` 都已声明 · ③ 清单 = 依赖（多/少/重复都不行）· ④ **运行时 `MainHost` 是空壳** · ⑤ MRO 关系；⇒ 门禁 **39 套 895 项 → 40 套 900 项**；
    ⑤ **数字纠偏**：需要声明的是 **65 个名字**（不是先前答复里说的 87 —— 87 是"7 个文件全体"的跨文件名字数，其中 22 个只有 `main.py` 引用，而它靠基类链本来就不报）；收益口径 = 6 个 Mixin 的 **211 个引用点**（114 状态 + 97 方法）全部消掉；B″ 只声明状态的话只消 114 点 ⇒ 被否；
    ⑥ **§11.6 从"只登记（A）"改写为"B′ 根治"**（保留 A 作为"想消音随时可用"的备选，并记下 B″ / C / `FlowContext` 三个被否选项的理由，避免以后重复讨论）；§6.5 补第 ④ 条（说清 B′ ≠ `FlowContext`）；§11.1 / §5.7 目录补 `core/host_contract.py`；§11.3 门禁口径换 40 套 900 项；头部版本 / 门禁基线 / 当前状态同步；**v2.3 已留档到 `backups\`**；
    ⑦ **验证**：门禁 **40 套 900 项全绿**（其中新用例 `dsh_t5g3_host_check` 5 项全过）；`MainHost` 运行时 `vars()` 里除 dunder **无成员**；界面截图 **sha256 仍与基线完全相同**（零界面改动）；改前备份 `_backup_VisionFlowNoed_before_t5g3_host_contract`；
    ⑧ ⚠️ **待人工确认**：PyCharm 里那 6 个文件应**归零** —— 这一步只能在 IDE 里看（助手环境跑不了 PyCharm），残留清单交给助手即可按清单补声明。

16. **v2.5（2026.10.15，代码 + 文档）**：**修正「自动切换」的语义**。用户口径（原话）："**我原本是设计只有选择了「自动切换」按钮才会在运行时自动切换画布的图片，将处理后的图片从头播放到尾**。但是现在的问题是我不选择这个按钮画布也会自动播放图像列表中处理后的图片，最后再切换回到选中的那一张中。**修改代码，重新实现我原本的这个功能**。"
    ① **根因（诚实交代）**：这个行为**以前就存在** —— 批量每张都调 `_execute_static`，而它**无条件**把处理后的图画到画布、跑完再由 `_batch_finish` 还原；**改前事件循环被占死、Qt 根本重绘不了** ⇒ 用户看不到中间帧；**目标3 的分片改动让出事件循环后，每张结果都被真实画了出来** ⇒ 用户才看到"不勾也在播放"。**是被目标3 暴露出来的老问题**；
    ② **改法（最小改动）**：`core/flow_engine.py::_execute_static()` 新增 `show=True` 参数（`show=False` ⇒ **只算不显示**：跳过 `_display_image`，结果照旧进缓存 + 日志逐张写）；`services/gallery_service.py::_batch_step()` 传 **`show=gallery.auto_switch()`** ⇒ **勾了才跟随、不勾全程不动**；`_batch_finish()` 的"恢复画面"退化为兜底（覆盖"批量中途切换开关"）；
    ③ **连带修 2 条用例桩函数**（`dsh_t5g3_batch_check.py::boom` / `dsh_m2_v5_check.py::patched`）：它们写死了签名，引擎多一个参数就 `TypeError` ⇒ 改成收 `**kwargs` 并原样转发（**以后再给引擎加参数不会断**）；
    ④ **新用例 ⑩（4 项）**：不勾「自动切换」⇒ 批量**期间** `_display_image` **0 次** / 整批只 1 次（兜底还原）/ **图照样都算了**（3 张缓存 + "共执行 3/3 张"）；勾上 ⇒ 每张都刷（3 张 = 3 次）；
    ⑤ 方案新增 **§6.6**（根因 / 改法 / 判据）· §6.4 判据表加第 9 行 · §11.3 与头部换 **40 套 904 项** · §十三 本条目；**v2.4 已留档到 `backups\`**；
    ⑥ **验证**：门禁 **40 套 904 项全绿**（先跑一次只有"方案口径"那 1 项红、**无代码回归**）；`py_compile` 全过；界面截图 sha256 不变；改前备份 `_backup_VisionFlowNoed_before_t5g3_autoswitch_fix`。

17. **v2.6（2026.10.15，代码 + 文档）**：**再修正「自动切换」—— 让它在批量开始时"定格"**。用户口径（原话）："**我不开启「自动切换」按钮运行连续执行后，在打开「自动切换」按钮，并没有再点击执行按钮或者连续执行按钮，但是画布上的内容会自动播放到最后**。是不是我不开启「自动切换」按钮它堵塞了，但是一打开就有自动播放了。给我修复这个问题。"
    ① **实测排查（两件事）**：**拨开关本身不会显示任何东西** —— `auto_switch_changed` 这个信号在整个工程里**无人监听**（widget 里只有 `auto_switch_box.toggled → auto_switch_changed.emit`），"点图库换图"走的是 `gallery_list.itemClicked → _on_item_clicked`（必须用户真点）⇒ 用户以为的"堵塞后释放"不是排队，**而是那一刻批量还在跑**；
    ② **真根因**：v2.5 的改法里 `_batch_step` **每跑一片都重新读** `gallery.auto_switch()` ⇒ 开始不勾时前半程 `show=False`（画布不动）、**中途拨上**之后后半程 `show=True`（画布开始逐张吐画面）；收尾 `_batch_finish` 也在看**当下的开关**（已是 ON）⇒ **不还原** ⇒ 画布停在**最后一张** —— 两点合起来正是用户看到的"自动播放到最后"；
    ③ **改法（"定格"语义）**：`run_all_images()` 建 `_batch_state` 时快照 **`"follow": gallery.auto_switch()`**；`_batch_step()` 用 `state["follow"]` 决定"要不要把图库选中项跟着切"与 `show=`；`_batch_finish()` 用它决定"要不要还原"（⇒ 开始不勾、中途拨上，收尾照样还原，不会停在最后一张）；新增薄处理器 **`_on_auto_switch_changed(checked)`**（`main.py` 接 `gallery_widget.auto_switch_changed`），**只在"批量进行中 + 与定格不一致"时**写一行短提示"批量执行中改动「自动切换」：本批仍按开始时的设置（跟随 / 不跟随）"；新方法已登记进 `tests\dsh_t5g2_api_check.py` 的 `ALLOWED_NEW_METHODS`；
    ④ **语义依据**（用户原话）："只有选择了自动切换…把处理后的图片**从头播放到尾**" —— 中途拨上不可能"从头播" ⇒ 整批统一按**开始那一刻**的开关走，开关的新状态对**下一次**批量生效；
    ⑤ **新用例 ⑪（4 项）**：开始不勾 + 中途拨上 ⇒ 本批仍不刷画布（采样恒 0）/ 收尾照样还原成开始时那张（不是最后一张）/ 中途拨动有一行提示；开始勾着 + 中途拨回不勾 ⇒ 本批继续跟随（3 张 = 3 次）；⇒ 门禁 **40 套 904 项 → 40 套 908 项**；
    ⑥ 方案新增 **§6.7** · §6.4 判据表加第 10 行 · §6.6 里那句 `show=gallery.auto_switch()` 更正为 `show=state["follow"]` · §11.3 与头部换 **40 套 908 项** · §十三 本条目；**v2.5 已留档到 `backups\`**；
    ⑦ **验证**：门禁 **40 套 908 项全绿**（先跑一次只有"方案口径"那 1 项红、**无代码回归**）；`py_compile` 全过；界面截图 sha256 不变；改前备份 `_backup_VisionFlowNoed_before_t5g3_follow_snapshot`。

18. **v2.7（2026.10.15，只改文档）**：**目标3 验收收口**。用户口径："**批次5目标3以验收**，现在给我总结一下批次5目标3做的内容，并更新修改日志和技术文档。"
    ① **§六 顶部加《✅ 验收记录》**：写明"用户 2026.10.15 验收"+"落地内容 / 两轮修正（§6.6 / §6.7）/ 判据（§6.4）都已在真机验过"+ 指向《开发日志》里的整体总结；
    ② **悬留一项**（写进验收记录里，不藏着）：PyCharm 里那 6 个文件的"未解析的特性引用"应已由 **B′（§11.6）**归零 —— 需在 IDE 里人工看一眼，有残留按清单补声明；
    ③ **头部"当前状态"改标** `目标3 ✅ 已验收`，并把版本号从 **v2.5 补正到 v2.7**（★ v2.6 那轮**漏改了这一行**，本次一并修正）；
    ④ **开发日志**：按用户要求写《**总结：批次5 目标3「执行批量化（分片执行）+ 自动切换语义修正」整体总结**》（用户明确要求时才写总结）+《全项目里程碑索引》批次5 行补该总结 + 本方案文件名换 v2.7；
    ⑤ **本轮只改文档、不改代码**；**v2.6 已留档到 `backups\VisionFlowNode_批次5技术方案_v2.6_2026.10.15.md`**；
    ⑥ 门禁口径**不变**（40 套 908 项）⇒ 文档一致性用例与"口径对照"都应保持全绿。

19. **v2.8（2026.10.15，只改 `.ui` + 文档）**：**目标4 方案定稿 + 控件落位**。用户口径："**这次不用修改代码，确定一些技术方案**"（七条拍板见 §七 开头）。
    ① **§七 整节改写**为"方案已定"：**7.1 缓存上限 LRU**（现状三毛病：FIFO 近似 LRU / 按条数不按内存 / 硬编码 400；实测 `data` 66 张 = 66 条 62.4 MB、单条最大 5.72 MB、400 条最坏 2.3 GB；改成"内存 256 MB + 条数 400 硬顶 + 真 LRU + 视频帧分池"；**实现决定 = 继续用普通 dict、只改淘汰逻辑**（8 套用例直接当 dict 用）；判据 4 条含**"真 LRU 判别"**）、**7.2 撤销 / 重做**（入口清点 + 落点 `core/commands.py`（零 Qt）+ `services/undo_service.py`（`UndoMixin`，6 → 7 个 Mixin）+ 控件 + 往返判据 + **三个坑**：删节点连带连线 / 两个 `add_flow_node` 入口只记一次 / 缓存不清）、**7.3 日志策略**（★ 用户提问的答复：**追加不清空** + 操作行加标记，并**实测发现日志表根本没有 `scrollToBottom()`** ⇒ 顺手补，这才是"看不见"的真症结）、**7.4 三批动手顺序**；
    ② **§十 待拍板**第 2、3 项（缓存上限值 / 撤销范围 + 快捷键 + 栈上限）标 **已定**；
    ③ **§12.3 新增《快捷键体系》**（用户要求写进《想法》：三条实现路 —— 控件里写 `QShortcut` / **`QAction` + `setShortcut`（推荐）** / 集中注册表；放哪 = **纯表进 `core/shortcuts.py`** + **注册与查重进 `services/shortcut_service.py`** + 控件自带 action 留控件；**未排期**，因为得先把"操作"收敛成 action）；
    ④ **`main.ui` 三处改动**（用户先自行加了两个按钮、只设了 text）：把 `pushButton` / `pushButton_2` 统一命名为 **`btn_undo` / `btn_redo`**；菜单栏新增 **「编辑」菜单 `menu_edit`**（位置：设置 与 方案 之间），内含 **`action_undo` / `action_redo`**（文字 撤销 / 重做）；四个控件初始 **`enabled = false`**（撤销栈空 = 不可点，接上代码后由栈状态联动）；**不设快捷键**（用户拍板先不做）；
    ⑤ **验证**：`QUiLoader` 冒烟 —— 菜单栏 = `['设置','编辑','方案']`、编辑菜单 = `['撤销','重做']`、四个控件都 `findChild` 到且 `enabled=False`；**门禁 40 套 908 项全绿**（`.ui` 改动未影响任何布局 / 宽度 / 产物自证用例）；改前备份 `_backup_VisionFlowNoed_before_t5g4_ui_undo_menu`；
    ⑥ **本轮没改任何 `.py`**（用户："这次不用修改代码"）；**v2.7 已留档到 `backups\`**。

20. **v2.9（2026.10.15，代码 + 文档）**：**目标4 落地 3 批**。用户口径："**接下来修改代码实现批次5目标4的内容**"（并按 §7.1~§7.4 的方案走）。
    ① **第 1 批（缓存上限 + 真 LRU）**：新增 **`core/result_cache.py`**（零 Qt：`is_sequence_key` / `touch` / `pool_stats` / `evict` + 两池上限常量）——
        ★ 排查中发现**旧上限只写在 `flow_engine` 的视频分支里**（"超过 400 条丢最旧，FIFO 近似 LRU"）⇒ **静态图批量跑根本没有上限**；
        现在改成"**写入缓存即淘汰 + 命中缓存即 `touch` 移到最新**"（真 LRU）、**两池**（静态 400 条/256 MB；视频序列 120 条/64 MB，用户拍板"乙"）；
        `_show_static_image` / `_batch_finish` 命中时也 `touch`；日志补 **`scrollToBottom()`**（`_update_execution_log` + `_append_log_hint`）；
        新增用例 **`dsh_t5g4_cache_check.py`（13 项）**，含 ★**真 LRU 判别**（填满 → 访问第 1 条 → 再填 ⇒ 第 1 条仍在，FIFO 会淘汰它）；
    ② **第 2 批（撤销 / 重做骨架）**：新增 **`core/commands.py`**（零 Qt：`Command` + `AddNode/RemoveNode/AddEdge/RemoveEdge` + `UndoStack`，**回调列表通知、不引 Qt Signal**，上限 50）；
        新增 **`services/undo_service.py`**（**`UndoMixin` = 第 7 个 Mixin**：`_init_undo` / `_undo_note` / `undo` / `redo` / `_on_undo_stack_changed` + `_UndoContext` 承担"命令 ↔ 流程图"的翻译）；
        `main.py`：基类加 `UndoMixin`、`__init__` 里 `_init_undo()`（放在 `flow_page_mgr.setup()` **之前**，因为建页会回调换页、那里要清栈）、
        **四个改动入口各记一条命令**（`add_flow_node` / `add_edge` / `delete_flow_node` / `delete_edge` —— 右键菜单与树双击也都走它们 ⇒ 不会记两遍）、**换页清栈**；
        ★ **删节点命令会把"被连带删掉的连线"一起存**（`capture_links`），撤销时节点与连线一起回来；`_undo_busy` 挡住"回退动作被记成新动作"；
        `core/host_contract.py` 用生成器按新 Mixin 重新生成（仍 **65 个名字**）；`dsh_t5g2_api_check` 白名单 +7、`dsh_t5g3_host_check` 改 7 个 Mixin；新增用例 **`dsh_t5g4_undo_check.py`**；
    ③ **第 3 批（参数 + 拖动）**：`SetParamsCommand`（钩在 `_mark_dirty_if_params_changed`，存 `before` / `after` **深拷贝**，撤销后同步写回"按图片存档"）+
        `MoveNodeCommand`（拖动期间 `positionChanged` 连发 ⇒ **400 ms 去抖凑成"一次拖动 = 一条命令"**；建节点与绑定页面时登记**坐标基准**，方案里读出来的节点也能撤回原位）；
    ④ **验证**：用例 **13 + 29 项全过**；门禁 **42 套 950 项全绿**（先跑时只剩"方案口径未更新"那 1 项红）；`py_compile` 全过；改前备份 `_backup_VisionFlowNoed_before_t5g4_batch`；
    ⑤ **遗留（写进 §7.6）**：**页面新建/删除的撤销**（需要给 `FlowPageManager` 加 3 个回调 + 用现成的 `_collect_page` / `_apply_project` 重建一页；★ 注意"切页会清栈"⇒ 记录必须在切页回调之后）· 快捷键按用户口径后做 · 页面重建后标签顺序回末尾（已知限制）；
    ⑥ §7.4 改成"三批完成情况"、新增 **§7.5 落地结果** 与 **§7.6 遗留**；§11.3 / §6.4 / 头部换 **42 套 950 项**；**v2.8 已留档到 `backups\`**。

21. **v2.10（2026.10.15，代码 + 文档）**：**修掉撤销 / 重做的两个 bug —— 命令改存 uid（"身份连续"）**。用户口径（原话）："1、**全部撤销后再一步一步按重做**，出现如图2所示的现象。可以看到**节点和线并不是连在一起的**……2、如图3所示，**撤销按钮已经按下来了**（说明没有内容可以撤销了），但是**图上还存在灰度节点**。修复上述的问题。"
    ① **同一根因**：v2.9 的命令里存的是**节点 / 连线对象引用**，而它们是 Qt 对象 —— 撤销会销毁、重做是重建新对象 ⇒ 旧引用失效；
    ② **两个现象各自的机制**：线飘 = `AddEdgeCommand.do()` 拿旧两端对象建 `EdgeItem`（此时已销毁）；按钮灰了节点还在 = "新建 → 删除 → 撤销（重建新节点）"之后再撤销那条更早的"新建"，
       旧引用已不在 `flow_nodes` 里 ⇒ `delete_flow_node` 的 `if node not in self.flow_nodes: return` 直接返回 ⇒ 删了个寂寞而栈照常弹空；
    ③ **改法**：节点 / 连线各发 **uid**（`node._undo_uid` / `edge._undo_uid`）、**命令只存 uid**、执行时 `ctx.resolve(uid)` **解析活对象**、重建时**沿用同一 uid**；
       `resolve()` **两层探活**（还在不在 `flow_nodes` 里 —— 因为 `scene.removeItem` 只解除场景归属、对象其实还活着；以及 C++ 对象是否已销毁）；
       删除类命令在"界面真正删之前"先 `ctx.forget(uid)` / `forget_edge(uid)`；`undo/redo` 抽成 `_run_stack_step()`（`_undo_busy` 挡记录 + 异常兜底 + 写日志行）；
    ④ **回归断言**（`dsh_t5g4_undo_check` 新增 ⑮⑯，+10 项）：撤销到底→全部重做后节点/坐标/连线逐项一致、**连线两端都是活着的节点**、**线的路径端点与节点输入输出点误差 < 1.5px**（直接钉"线贴在节点上"）；
       新建→删除→撤销→再撤销 ⇒ 节点真没了 + 栈空按钮灰 + 反复往返都不坏；
    ⑤ **验证**：门禁 **42 套 960 项全绿**（`dsh_t5g2_api_check` 白名单同步 +1：`_run_stack_step`）；`py_compile` 全过；新增 **§7.7**（机制 + 改法 + 回归断言）；§7.5 的用例项数改 39；头部 / §6.4 / §11.3 换 **42 套 960 项**；**v2.9 已留档到 `backups\`**；
    ⑥ 过程中还修了两个**我自己写用例时的错**（不是产品 bug）：`img()` 把 `_frame_paths` 登记到了别的窗口（缓存用例 ⑥ 假失败）、以及把 "重做两步的净效果" 期望写反（⑯ 末条）。
        ★ 教训：**Python 字符串里别嵌 ASCII 双引号**（用「」）—— 本轮又踩一次，直接 `SyntaxError`。

22. **v2.11（2026.10.15，代码 + 文档）**：**修「改参数撤销不到位」—— 参数要按图片恢复**。用户口径（原话）："**参数撤销的问题，我一直撤销，直到撤销到创建节点的那一步，但是参数还是没有回到参数值，而是显示修改后的值**。也可能是边缘检测这个节点的问题，给我查一下。**我重新运行程序就没有这个问题了**。"
    ① **根因（实测复现）**：运行参数**按图片分别存档**（`params_per_image[图片键]`）；v2.10 的 `apply_params()` 只改"当前那张图"（`node.params` + 当前图的槽）⇒
       "**在 A 图改完参数 → 切到 B 图 → 撤销 → 再切回 A 图**"时，A 的存档里还是改后的值 ⇒ `_load_node_params()` 又把它载回 `node.params` ⇒ **看起来撤销没生效**；
       "重启就没问题" = 存档只在内存里（没保存方案）⇒ 重启后是空的；
    ② **复现数据（修前）**：① 改完 A 图 `edge_low=99`；② 切 B 图：存档 `{'A.png': 99}`；③ 撤销后 `node.params` 回到 None 但**存档里还是 99**；④ 切回 A 图 ⇒ `edge_low` 又回到 99 ✓ 与用户描述一致；
    ③ **改法**：`SetParamsCommand` 带 **`image_key`**；`apply_params(uid, snapshot, image_key)` —— 是当前图就改 `node.params` + 该图存档，是别的图就**只改那张图的存档**（不碰 `node.params`）；
       只给"跟着图片走"的节点写图片槽（流程级节点不参与）；**空快照按既有约定销槽**（与 `_save_node_params` 的"空字典不存"一致）；
       记命令时由 `main.py::_open_node_dialog` 捕获 `before_key = self.current_image_key` 并传进 `_mark_dirty_if_params_changed(node, before, image_key)`（参数窗口是模态的，开窗期间图片不会变）；
    ④ **回归断言**：`dsh_t5g4_undo_check` ⑰（3 项）—— 跨图撤销后参数真回到改之前 / A 图存档不再留改后的值 / 重做后切回 A 图又变回改后的值；**修后复现**：④ 切回 A 图 `edge_low = None`、存档 `{}`；
    ⑤ **验证**：门禁 **42 套 963 项全绿**；`py_compile` 全过；新增 **§7.8**（根因 + 修前/修后数据 + 改法 + 回归）；
    ⑥ §7.5 用例项数改 42；头部 / §6.4 / §11.3 换 **42 套 963 项**；**v2.10 已留档到 `backups\`**。

23. **v2.12（2026.10.15，代码 + 文档）**：**撤销栈改成"每页一条"（修"换页后撤销失效"）+ 页面撤销技术要求入档**。用户口径（原话）："1、**页面新建/删除的撤销我不打算做，可以把技术要求写到《想法》里面，等后续再做**。2、现在存在一个关于更换页面的问题……**然后回到第一个页面后撤销按钮失去了作用，即换页后不能再撤销和重写。修复这个问题**。**对于导入的流程图，设置撤销最多只能撤销到导入时，即以刚导入时为基准，修改后才能撤销/重写**。"
    ① **根因**：v2.10 之前那条拍板"**清栈时机 = 换页 / 载入方案 / 新建项目 / 删除页面**"⇒ `_on_flow_page_switched()` 开头就 `stack.clear()` ⇒ "换页 = 历史清零"（用户这条新口径**推翻了"换页清栈"**）；
    ② **改法**：`services/undo_service.py` 新增 **`self._undo_stacks`（页 key → 该页自己的 `UndoStack`）**、**`_stack_for(page_key)`**（没有就建**空**栈）、
       **`_bind_undo_stack_for_page()`**（换页 / 载入方案 / 新建页面后：把当前栈换成该页的、丢掉已删页的栈、立刻同步按钮 `enabled`）；
       `main.py::_on_flow_page_switched()` 把 `stack.clear()` **换成** `self._bind_undo_stack_for_page()`（放在 `_bind_current_flow_page()` 之后），`__init__` 里再补一次；
       `_on_undo_stack_changed()` 改用 `getattr(self, "action_undo", None)`（"占位栈"建好时会立刻回调，那时控件还没找出来）；
    ③ **"导入即基准"无需额外代码**：`_apply_project()` 走 `append_pages` + `_add_node_to_page` + `_add_edge_to_page`（**不经过四个记录入口**）⇒ 导入动作从不进栈；新页面的栈本来就是空的 ⇒ 撤销最多撤到"刚导入时"；
    ④ **判据**（`dsh_t5g4_undo_check` ⑦ 改写 6 项 + 新增 ⑱ 4 项）：新页面以出现时为基准 / 新页可撤销 / **切回第一页历史还在且按钮可用（用户报的现象）** / 每页互不干扰；
       导入动作不进栈 · 导入后可撤销 · **撤销到底 = 回到导入时的样子** · 重做回到"导入 + 修改"的末态；
    ⑤ **文档**：新增 **§7.9**（根因 + 改法 + 判据）· **§12.5《页面新建 / 删除的撤销》**（原 §12.5 顺延为 §12.6）· §7.6 第 1 条改成"用户决定不做、入档 §12.5"；
       §7.5 用例项数改 51；头部 / §6.4 / §11.3 换 **42 套 972 项**；**v2.11 已留档到 `backups\`**；
    ⑥ **验证**：`dsh_t5g4_undo_check` **51 项全过**；门禁 **42 套 972 项全绿**；`py_compile` 全过；
    ⑦ ★ 又踩一次"**Python 字符串里嵌 ASCII 双引号**"（直接 `SyntaxError`）—— 这条教训已经写进 ops 记忆，这次是第 2 次，后续写用例时先自查。

24. **v2.13（2026.10.15，只改文档）**：**目标4 收口**。用户口径："**给我总结一下批次5目标4所完成的内容，并完成日志和技术文档的修改**。"
    ① **§七 顶部新增《✅ 目标4 交付记录》**：交付内容 = **三批**（缓存两池 LRU + 日志自动滚动 / 撤销·重做骨架 / 参数 + 拖动）+ **四轮修正**（§7.7 §7.8 §7.9 §7.3）+ **控件落位**（「编辑」菜单 + 两按钮）；
       用户两次追加口径（"换页后还要能撤销" / "导入最多撤到导入时"）；**明确不做**（页面新建/删除的撤销 ⇒ §12.5；快捷键 ⇒ §12.3）；
       判据与结果 = 新用例 **13 + 51 项全过**、门禁 **42 套 972 项全绿**、**界面零变化**；**交付后残留** = 一条待补的界面证据图；
    ② **拍板第 ⑦ 条**（清栈时机）标注"**已被 §7.9 取代**"（栈按页面各一条、换页不清历史）；
    ③ 头部"当前状态"改标 **目标4 ✅ 已落地并收口**；
    ④ **开发日志**：按用户要求写《**总结：批次5 目标4「缓存上限 LRU + 撤销 / 重做」整体总结**》（用户明确要求时才写总结）+《全项目里程碑索引》批次5 行补该总结 + 方案文件名换 v2.13；
    ⑤ **本轮只改文档、不改代码**；门禁口径**不变**（42 套 972 项）；**v2.12 已留档到 `backups\`**。

25. **v2.14（2026.10.15，只改文档）**：**按用户要求"都以完成，把目标2和目标4也打上勾"** —— §3《目标表》给**目标2**与**目标4**补 ✅：
    ① **目标2**：标注"2026.10.15 三批 + 收尾（见 §5.4~§5.8）"，判据栏写明"行为零变化 + 用例全绿 + **界面零变化（截图 sha256 相同）** ✅"，
       落地栏补全（新增 6 个 Mixin 文件 · `main.py` **3327 → 885 行** · 弹窗出口收成 5 个薄壳 · 门禁 **37 套 861 → 38 套 870 项**）；
    ② **目标4**：标注"2026.10.15 落地 3 批 + 四轮修正并收口（见 §七 顶部《✅ 交付记录》）"，判据栏写明缓存上限断言（含"真 LRU 判别"）✅ + 往返断言 ✅，
       落地栏补全（新增 `core/result_cache.py` · `core/commands.py` · `services/undo_service.py`（第 7 个 Mixin）· `main.ui` · 两个测试文件；门禁 **40 套 908 → 42 套 972 项**）；
    ③ 头部版本同步；**纯文档维护、代码与门禁口径均未变**（仍 42 套 972 项全绿）；**v2.13 已留档到 `backups\`**。
