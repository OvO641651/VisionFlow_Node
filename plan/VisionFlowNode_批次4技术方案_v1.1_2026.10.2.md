# VisionFlowNode 批次4 技术方案

| 项 | 内容 |
|---|---|
| 文档版本 | **v1.1.3**（v1.1 系列的当前修订；历次修订见下方"v1.1 相对 v1.0 的变更"第 1~6 条；v1.0 原版保留不动） |
| 撰写日期 | 2026.10.2（v1.1 更新于 22:57；v1.1.1 / v1.1.2 / v1.1.3 依次补于 23:13 / 23:24 / 23:38） |
| 适用工程 | `E:\opencv_python_3_8\PySide\VisionFlowNoed`（目录名少个 d） |
| 代码基线 | 批次2 提交 `668320d`、批次3 提交 `d64d7b6`；**M1 已实现**（尚未提交） |
| 备份基线 | `E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_at_20261002_2257` |
| 当前状态 | **M1（方案持久化）已完成并通过验证**；M2~M4 未开工，第 9 节的决策仍待拍板 |
| 说明 | 第 3 节已按**实际实现**更新（不再是"拟定"）；第 4~6 节的代码片段仍为**拟定**。**归档约定**：本文件是"当前版本"，只放在工程 `plan\`；**每改一次方案，先在 `E:\opencv_python_3_8\backups` 存一份带版本号的快照**（如 `VisionFlowNode_批次4技术方案_v1.1.3_2026.10.2.md`），历史版本按版本号排开。 |

**v1.1 相对 v1.0 的变更（按用户反馈调整）**

1. **打开方案改为"追加"**：不再清空现有页面；方案里的页面追加到现有页面之后（"+"标签前面）。原方案里的 `reset_pages()` 换成 `append_pages()`。
2. **顶部两个按钮**：`main.ui` 里新增的"保存项目 / 导入项目"两个按钮改名为 `save_project_button` / `open_project_button`，并与菜单"方案"下的两项接到**同一套实现**。
3. **关闭页面提醒保存**：每个页面增加"有未保存改动"标记（`page["dirty"]`），关闭该页时按需弹出"保存 / 不保存 / 取消"。
4. **加载去重（v1.1.1 补充）**：文件里与工作区已有页面**内容完全相同**的页不再重复创建——否则"保存 → 再打开同一文件"会把页面越堆越多（`Flow`、`Flow8(2)`、`Flow(2)(2)`…）。判定用"页面内容指纹"：标题 + 每个节点的名字/坐标/图像源绑定/参数（数值 round 4 位）+ 连线关系。
5. **一个文件只装一页（v1.1.2 补充）**：`_collect_project()` 只收**当前页**（新增 `_collect_page(page)` 负责"收一页"），`pages` 数组长度恒为 1、`current_page` 恒为 0；"另存为"的默认文件名用**当前页的标签名**；关闭非当前页时选"保存"，会先把那一页切成当前页再存。原因：以前的"保存方案"写的是**整张工作区**，导致打开某个方案会把当时开着的其它页面一起带出来（用户实测反馈）。
6. **方案文件路径按页面记（v1.1.3 补充）**：路径存在 `page["project_path"]` 上（不再是窗口级变量）。新建的页面没有文件，"保存项目"会**弹窗让用户选路径**；已有文件的页面保存时静默写回自己的文件。同时修掉"保存一页把**所有**页面的未保存标记都清掉"的问题——现在只 `clear_dirty(当前页)`。

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
| **形态学** | `op`(腐蚀/膨胀/开/闭)、`shape`(矩形/椭圆/十字)、`ksize`(odd)、`iterations`(1~10) | `cv2.getStructuringElement` + `cv2.morphologyEx` |
| **边缘提取** | `method`(Canny/Sobel/Laplacian)、`low`、`high`、`ksize`(odd) | `cv2.Canny` / `cv2.Sobel` / `cv2.Laplacian`；输出灰度 → 补成 3 通道 |

**统一结果文案**：新增 `_format_process(results)` 之类，返回"执行成功（图像已处理，下游模块可见）"，避免每个算子各写一份（现有 `_format_gray` 可并入）。

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
| **M2 通用窗口 + 5 算子** | `param_specs`、`GenericProcessDialog`、5 个算子 run、树项 | 5 个算子的效果断言全通过；双击能开窗口 | `before_generic_dialog` |
| **M3 图像源节点** | 新 spec + 引擎落点 + 参数表（含 file 类型） | 三种来源各跑通；不放它时行为不变 | `before_image_source` |
| **M4 参数校验** | `validate` 规则 + 窗口钩子 + 引擎兜底 | 规则逐条用例通过 | `before_validate` |
| **M5 收尾** | 树里未实现模块标注、批次总结日志、截图、最终备份 | 项目全景与日志齐全 | `at_<时间>` 快照 |

每步固定动作：**建 before 备份 → 改代码 → 验证四连 → 截图（涉及界面时）→ 写 pyside6.txt 日志 → 存 after 快照**。

---

## 9. 待拍板的决策

| 编号 | 问题 | 推荐做法 | 备选 |
|---|---|---|---|
| **a** | 方案文件里存哪些参数？ | 只存"当前图片那一份参数" + `last_image` | 先把 per-image 键从 `id(原图)` 改成文件名/路径，再存多图多套参数（额外一块工作） |
| **b** | 5 个算子的参数界面 | 通用动态窗口（`GenericProcessDialog`） | 每个算子单独 `.ui`（设计师可见，但每加一个算子就要重复一遍） |
| **c** | "图像源"节点与全局图像源 | 并存（流程里放了才生效） | 取代（老流程与老方案都要改） |
| **d** | 参数校验策略 | 能纠正的自动纠正 + 日志，不能的拦住 | 一律拦住、弹提示 |
| **e** | 附加问题 | 建议把"灰度"从"检测"分组挪到新的"处理"分组（它本来就是处理类算子） | 保持现状 |

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
