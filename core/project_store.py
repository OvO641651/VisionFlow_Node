# -*- coding: utf-8 -*-
"""方案持久化（收集 / 指纹 / 读写 / 追加去重）

批次5 目标2「拆 `MainWindow`」：**v1 只是把 main.py 里的代码原样搬出来**（方法体一字未改），
由 `main.py` 的 `MainWindow` 多重继承本 Mixin —— `self` 仍是主窗口，方法之间照旧 `self.xxx` 互调。
"""

from PySide2.QtCore import QPointF  # 只有 _apply_project 拼节点坐标时用到
import json
import time
import os
from core.NodeRegistry import SOURCE_KEY, get_spec, is_bound_node
from core.host_contract import MainHost   # ★ 宿主契约（只为静态检查；运行时是空类），见《批次5 技术方案》§11.6


class ProjectStoreMixin(MainHost):
    """方案持久化（收集 / 指纹 / 读写 / 追加去重）（批次5 目标2 从 main.py 拆出）"""

    def _page_title(self, page):
        """取某一页的标签标题（找不到就返回空串）"""
        try:
            index = self.flow_page_mgr.tab_widget.indexOf(page["widget"])
            if index >= 0:
                return self.flow_page_mgr.tab_widget.tabText(index)
        except RuntimeError:
            pass
        return ""

    def _page_fingerprint(self, page):
        """
        给"工作区里的一页"算内容指纹：标题 + 每个节点的名字/坐标/图像源绑定/参数 + 连线关系。
        用来判断"方案文件里的这一页，工作区里是不是已经有一模一样的了"。
        """
        nodes = page["nodes"]
        index_of = {node: index for index, node in enumerate(nodes)}
        node_items = []
        for node in nodes:
            pos = node.pos()
            binding = getattr(node, "input_source", None)
            if is_bound_node(binding):
                # 绑定的是某个节点对象 → 换成页内序号，和文件里的表示保持一致
                binding = index_of.get(binding)
            node_items.append((
                node.name,
                round(float(pos.x()), 1), round(float(pos.y()), 1),
                binding,
                tuple(sorted((str(key), _fingerprint_value(value))
                             for key, value in node.params.items())),
            ))
        edges = []
        for edge in page["edges"]:
            start = index_of.get(edge.start_node)
            end = index_of.get(edge.end_node)
            if start is not None and end is not None:
                edges.append((start, end))
        return (self._page_title(page).strip(), tuple(node_items), tuple(sorted(edges)))

    def _model_page_fingerprint(self, page_model):
        """给"方案文件里的一页模型"算指纹——结构必须和 _page_fingerprint 完全一致"""
        node_items = []
        for node in page_model["nodes"]:
            node_items.append((
                node["name"],
                round(float(node["x"]), 1), round(float(node["y"]), 1),
                node.get("input_source"),
                tuple(sorted((str(key), _fingerprint_value(value))
                             for key, value in node["params"].items())),
            ))
        edges = tuple(sorted(tuple(edge) for edge in page_model["edges"]))
        return (page_model["title"].strip(), tuple(node_items), edges)

    def _collect_page(self, page):
        """把"一页流程图"收成可 JSON 化的 dict（节点 + 连线）"""
        nodes = page["nodes"]
        index_of = {node: index for index, node in enumerate(nodes)}
        nodes_data = []
        for index, node in enumerate(nodes):
            pos = node.pos()
            binding = getattr(node, "input_source", None)
            if is_bound_node(binding):
                # 绑定的是某个上游节点：存它的页内序号（不在本页就退回"自动"）
                binding = index_of.get(binding, None)
            nodes_data.append({
                "id": index,
                "name": node.name,
                "x": round(float(pos.x()), 2),
                "y": round(float(pos.y()), 2),
                "input_source": binding,
                "params": dict(node.params),
                # 顺便把"按文件路径存的其它图片参数"也存进方案文件，
                # 这样"运行全部"给每张图调好的参数下次打开还在（原来是只存当前那一份）
                "params_by_image": self._node_params_by_image(node),
            })
        edges_data = []
        for edge in page["edges"]:
            start = index_of.get(edge.start_node)
            end = index_of.get(edge.end_node)
            if start is not None and end is not None:
                edges_data.append([start, end])
        return {
            "title": self._page_title(page),
            "nodes": nodes_data,
            "edges": edges_data,
        }

    def _collect_project(self):
        """
        把**当前这一页**收成方案 dict（"保存方案"用）。

        规则：**一个方案文件只装一页**（一个文件对应一个流程图窗口）——
        以前是"把整张工作区的所有页面都写进去"，结果打开某个方案会把当时开着的
        其它页面一起带出来，用户反馈过这个问题，所以改成只存当前页。

        节点参数存的是"当前图片那一份"（node.params）：参数是按图片归档的、归档键用的是
        id(原图)，跨进程不可复现，所以方案里只带当前这一份，另外用 last_source 记下它属于谁。
        """
        page = self.flow_page_mgr.current_page
        pages_data = [self._collect_page(page)] if page is not None else []
        return {
            "format": self.PROJECT_FORMAT,
            "version": self.PROJECT_VERSION,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "current_page": 0,
            "last_source": self.last_source,
            "pages": pages_data,
        }

    def save_project(self):
        """
        "保存方案"：**这一页**已经有对应文件就直接存；没有（例如刚新建的页面）就当"另存为"，
        弹窗让用户选路径——绝不拿别的页面用过的文件路径去覆盖。
        """
        page = self.flow_page_mgr.current_page
        path = page.get("project_path") if page is not None else None
        if path:
            return self._write_project_file(path)
        return self.save_project_as()

    def save_project_as(self):
        """菜单"另存为…"：弹文件对话框选路径"""
        page = self.flow_page_mgr.current_page
        path = page.get("project_path") if page is not None else None
        if path:
            default_name = os.path.basename(path)
        else:
            # 一个文件对应一个流程图页面：默认就用这一页的标签名当文件名
            title = self._page_title(page).strip() or "方案"
            default_name = "{0}.vfproj".format(title)
        path = self._ask_save_path(default_name)
        if not path:
            return False
        if not path.lower().endswith(".vfproj"):
            path += ".vfproj"
        return self._write_project_file(path)

    def _write_project_file(self, path):
        """把当前流程写进方案文件（JSON / UTF-8 / 缩进 2）"""
        try:
            data = self._collect_project()
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._warn("保存方案失败", "写入文件时出错：\n{0}".format(exc))
            return False
        page = self.flow_page_mgr.current_page
        if page is not None:
            # 这一页从此认这个文件（新建的页面也就有了自己的方案文件）
            page["project_path"] = path
        # 只把"刚存过的这一页"清干净：别的页面如果还有改动，仍然算未保存
        self.flow_page_mgr.clear_dirty(page)
        self._update_project_title()
        return True

    def _update_project_title(self):
        """把**当前这一页**对应的方案文件名显示到窗口标题上"""
        page = self.flow_page_mgr.current_page
        path = page.get("project_path") if page is not None else None
        name = os.path.basename(path) if path else "未保存的方案"
        try:
            self.main_window.setWindowTitle("VisionFlowNode - {0}".format(name))
        except RuntimeError:
            pass

    def open_project(self):
        """菜单"打开方案"：选文件后交给 load_project()"""
        path = self._ask_open_path()
        if not path:
            return False
        return self.load_project(path)

    def load_project(self, path):
        """
        加载方案：先解析 + 校验（这一步完全不碰界面），全部通过之后才重建页面；
        校验不过就原样返回，不破坏当前流程图。
        """
        # 1、读文件 + 基本校验
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception as exc:
            self._warn("打开方案失败", "读取或解析文件出错：\n{0}".format(exc))
            return False
        if not isinstance(data, dict) or data.get("format") != self.PROJECT_FORMAT:
            self._warn("打开方案失败", "这不是 VisionFlowNode 的方案文件。")
            return False
        version = data.get("version")
        if not isinstance(version, int) or version > self.PROJECT_VERSION:
            self._warn(
                "打开方案失败",
                "方案版本（{0}）比当前程序支持的版本（{1}）新，打不开。".format(version, self.PROJECT_VERSION))
            return False
        pages = data.get("pages")
        if not isinstance(pages, list) or not pages:
            self._warn("打开方案失败", "方案里没有任何流程图页面。")
            return False

        # 2、整理成"待应用模型"（只读数据，界面还没动）
        model, warnings = self._build_project_model(pages)

        # 3、去重：文件里与"工作区里已有的页面"内容完全相同的页，不再重复创建
        #    （不然"保存 → 再打开同一个文件"会把页面越堆越多：Flow、Flow(2)、Flow(2)(2)…）
        existing = set(self._page_fingerprint(page) for page in self.flow_page_mgr.pages)
        kept_pages = []
        skipped_pages = 0
        for page_model in model["pages"]:
            fingerprint = self._model_page_fingerprint(page_model)
            if fingerprint in existing:
                skipped_pages += 1
                continue
            existing.add(fingerprint)   # 同一个文件里若有重复页，也只建一份
            kept_pages.append(page_model)
        model["pages"] = kept_pages
        if skipped_pages:
            warnings.append("有 {0} 页与工作区里已有的页面完全相同，已跳过".format(skipped_pages))
        if not kept_pages:
            # 文件里的页面工作区里全都有：什么都不用建，提示一句就好
            self._info(
                "打开方案",
                "这个方案里的 {0} 页与当前工作区里已有的页面完全相同，没有新增页面。".format(skipped_pages))
            return True

        # 4、真正重建（到这里才开始动界面）
        try:
            self._apply_project(model, data, path)
        except Exception as exc:
            self._warn("打开方案失败", "重建流程图时出错：\n{0}".format(exc))
            return False

        self._update_project_title()
        if warnings:
            self._info(
                "打开方案",
                "方案已加载；下面是 {0} 条提示：\n{1}".format(len(warnings), "\n".join(warnings)))
        return True

    def _build_project_model(self, pages):
        """
        把方案文件里的页面数据整理成"待应用模型"：
        没注册的算子、悬空的连线、无效的图像源绑定都会被过滤掉，并记进 warnings。
        """
        model_pages = []
        warnings = []
        for page_index, page in enumerate(pages):
            if not isinstance(page, dict):
                warnings.append("第 {0} 页数据格式不对，已跳过".format(page_index + 1))
                continue
            title = str(page.get("title") or "Flow{0}".format(page_index + 1))
            nodes = []
            raw_nodes = page.get("nodes") if isinstance(page.get("nodes"), list) else []
            for raw in raw_nodes:
                if not isinstance(raw, dict):
                    continue
                name = str(raw.get("name") or "")
                if get_spec(name) is None:
                    warnings.append("算子“{0}”没有实现，已跳过".format(name or "(空)"))
                    continue
                try:
                    x = float(raw.get("x", 0.0))
                    y = float(raw.get("y", 0.0))
                except (TypeError, ValueError):
                    x, y = 0.0, 0.0
                params = raw.get("params")
                # "按图片（文件路径）存的其它参数"：原样带进来，供 _apply_project 还原到节点上
                params_by_image = raw.get("params_by_image")
                nodes.append({
                    "name": name,
                    "x": x,
                    "y": y,
                    "params": dict(params) if isinstance(params, dict) else {},
                    "params_by_image": dict(params_by_image) if isinstance(params_by_image, dict) else {},
                    "input_source": raw.get("input_source", None),
                    "old_id": raw.get("id"),
                })

            # 连线：两端都要能对上"留下来的节点"，自环直接丢掉
            index_by_old_id = {}
            for index, node in enumerate(nodes):
                index_by_old_id.setdefault(node["old_id"], index)
            edges = []
            raw_edges = page.get("edges") if isinstance(page.get("edges"), list) else []
            for raw_edge in raw_edges:
                if not (isinstance(raw_edge, (list, tuple)) and len(raw_edge) == 2):
                    warnings.append("第 {0} 页有一条连线格式不对，已跳过".format(page_index + 1))
                    continue
                start = index_by_old_id.get(raw_edge[0])
                end = index_by_old_id.get(raw_edge[1])
                if start is None or end is None or start == end:
                    warnings.append("第 {0} 页有一条连线指向不存在的节点，已跳过".format(page_index + 1))
                    continue
                edges.append([start, end])

            # 图像源绑定：数字要能对上本页节点；对不上、或者指向自己，就退回"自动"
            for index, node in enumerate(nodes):
                binding = node["input_source"]
                target = None
                if isinstance(binding, int) and not isinstance(binding, bool):
                    target = index_by_old_id.get(binding)
                elif isinstance(binding, str) and binding == SOURCE_KEY:
                    target = SOURCE_KEY
                if target is None or target == index:
                    target = None
                node["input_source"] = target

            model_pages.append({"title": title, "nodes": nodes, "edges": edges})
        return {"pages": model_pages}, warnings

    def _apply_project(self, model, data, project_path=None):
        """
        按模型把这些页面**追加**到现有流程后面（已有的页面一律保留、不动），
        并恢复节点参数、图像源绑定、连线（界面从这里才开始变）。
        :param project_path: 这些页来自哪个方案文件（记到 page["project_path"] 上，
                             以后在这一页点"保存方案"就直接存回这个文件）
        """
        titles = [page["title"] for page in model["pages"]]
        new_pages = self.flow_page_mgr.append_pages(titles)
        if not new_pages:
            return

        # 1、逐页建节点 → 恢复参数 → 恢复图像源绑定 → 连连线
        #    （mark_dirty=False：从文件读进来的内容不算"未保存的改动"）
        for page, page_model in zip(new_pages, model["pages"]):
            created = []
            for node_model in page_model["nodes"]:
                node = self._add_node_to_page(
                    page, node_model["name"], QPointF(node_model["x"], node_model["y"]),
                    mark_dirty=False)
                node.params.clear()
                node.params.update(node_model["params"])
                # 还原"按图片（文件路径）存的参数"：以后切到同一张图就能拿回各自那一份
                store = self._get_node_params_store(node)
                store.clear()
                for key, value in (node_model.get("params_by_image") or {}).items():
                    if isinstance(key, str) and isinstance(value, dict):
                        store[key] = dict(value)
                created.append(node)
            for index, node_model in enumerate(page_model["nodes"]):
                binding = node_model["input_source"]
                if binding == SOURCE_KEY:
                    created[index].input_source = SOURCE_KEY
                elif isinstance(binding, int) and 0 <= binding < len(created):
                    created[index].input_source = created[binding]
                else:
                    created[index].input_source = None
            for start, end in page_model["edges"]:
                self._add_edge_to_page(page, created[start], created[end], mark_dirty=False)

        # 2、参数同时写进"当前图片"的存档，否则切走再切回来就被清空了
        if self.current_image_key is not None:
            for page in new_pages:
                for node in page["nodes"]:
                    self._get_node_params_store(node)[self.current_image_key] = dict(node.params)

        # 3、新追加的页面 = "刚打开的样子"：不算未保存改动，并记住它们来自哪个方案文件
        for page in new_pages:
            self.flow_page_mgr.clear_dirty(page)
            page["project_path"] = project_path

        # 4、切到方案里记录的那一页（它是新追加页面里的第 current_index 页）
        current_index = data.get("current_page", 0)
        if not isinstance(current_index, int) or not (0 <= current_index < len(new_pages)):
            current_index = 0
        try:
            first_index = self.flow_page_mgr.tab_widget.indexOf(new_pages[0]["widget"])
        except RuntimeError:
            first_index = -1
        if first_index >= 0:
            # 走正常换页流程：主窗口引用重新绑定、旧页参数也会存好
            self.flow_page_mgr.tab_widget.setCurrentIndex(first_index + current_index)
        else:
            # 兜底：标签栏状态异常时，至少把当前页和引用绑过去
            self.flow_page_mgr.current_page = new_pages[current_index]
            self._bind_current_flow_page()
        self.selected_node = None
        if self.current_node_label:
            self.current_node_label.setText("未选中节点")

        # 5、刷新画面与日志：有图就按新流程重跑一次，没图就只把连线刷新一下
        self.update_all_edges()
        if self.current_static_image is not None:
            # ★ 批次5目标5-M1（2026.10.16，实测取证）：这次"重画"只是把**当前那张图**按新页面重算一遍，
            #   并不是用户真的要用「图片源」那张图 ⇒ **不要**让执行收尾把源图补进图库。
            #   否则用户会看到"导入方案后图库里凭空多出一张、跟当前选择的那张冲突"（实测：图库 1 → 2 张）。
            #   正常点执行时不受影响（那个标志只有这里会置上）。
            self._no_source_gallery_sync = True
            try:
                self._execute_static(self.current_static_image, "continuous")
            finally:
                self._no_source_gallery_sync = False



def _fingerprint_value(value):
    """
    算"页面内容指纹"时把参数值规范化。
    数字统一 round 到 4 位：避免 1 与 1.0、以及浮点误差（0.1+0.2）造成"明明一样却判成不同"。
    """
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("num", round(float(value), 4))
    return ("str", str(value))