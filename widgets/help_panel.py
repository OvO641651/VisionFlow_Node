# -*- coding: utf-8 -*-
"""帮助页（批次6 目标3-M2，`3.2.1`，2026.10.19）。

用户口径：「**可以在右下角的当前结果这个 tabwidget 中添加一页「帮助」，用于怎么显示节点内容**。」

★ 结构：
    main.ui 的 `result_tab`（「当前结果」那个 QTabWidget）现在有 2 页 ——
        第 1 页 `tab_2`      「当前结果」（日志表，未改动）
        第 2 页 `tab_help`   「帮助」（`lbl_help_title` + `text_help_body`，本文件负责刷新）
    * 说明文本的**内容**在 `core/help_texts.py`（纯数据），本文件只负责"取出来摆上去"。

★ 为什么逻辑放这里、而不是 `main.py`：`dsh_t5g2_api_check` 的白名单只允许 `main.py`
  里那些既有方法 —— 新功能一律写成 `widgets/` 的模块级函数 / 小类，`main.py` 只加一行调用
  （这条和 M3 的 `install_toolbox_collapse` 同一个套路）。

★ 接线用 `QObject` 子对象 + 绑定方法（**不用 lambda / 闭包**）——
  批次6 目标2-M1 踩过"闭包 + 控件生命周期"导致的析构期偶发崩溃（0xC0000409），这里沿用安全做法。
"""

from PySide2.QtCore import QObject
from PySide2.QtWidgets import QLabel, QTextEdit

from core.NodeRegistry import get_spec
from core.node_catalog import group_of

# 未选中 / 没有说明时的兜底文案
NO_SELECTION_TITLE = "帮助"
NO_SELECTION_BODY = "请选择节点"
NO_HELP_BODY = "该节点暂无说明。"


class _HelpPanel(QObject):
    """把"当前选中节点"的说明摆到「帮助」页上。"""

    def __init__(self, host):
        # ★ host 可能是外层 MainWindow（它**没有 Qt 基类**！不能直接当 QObject 父对象），
        #   也可能直接是 QMainWindow ⇒ 父对象一律取"真正的窗口控件"，取不到才退回 None。
        window = getattr(host, "main_window", host)
        parent = window if isinstance(window, QObject) else None
        super().__init__(parent)
        self._host = host
        self._title = window.findChild(QLabel, "lbl_help_title")
        self._body = window.findChild(QTextEdit, "text_help_body")

    # ---------------- 内部 ----------------
    def _node_name(self, node):
        """取节点名（`NodeItem.name` 是普通属性，不是方法）。取不到就返回空串。"""
        try:
            return str(getattr(node, "name", "") or "")
        except Exception:
            return ""

    def _title_for(self, name):
        """标题 = 「节点名（分组）」；取不到分组就只显示名字。"""
        try:
            group = group_of(name)
        except Exception:
            group = ""
        return "%s（%s）" % (name, group) if group else name

    # ---------------- 对外 ----------------
    def refresh(self):
        """按当前选中节点刷新帮助页。任何异常都不往外抛（帮助页坏了不能影响主流程）。"""
        if self._title is None or self._body is None:
            return
        name = self._node_name(getattr(self._host, "selected_node", None))
        if not name:
            self._title.setText(NO_SELECTION_TITLE)
            self._body.setPlainText(NO_SELECTION_BODY)
            return
        spec = get_spec(name)
        text = (getattr(spec, "help_text", "") or "").strip() if spec is not None else ""
        self._title.setText(self._title_for(name))
        self._body.setPlainText(text or NO_HELP_BODY)


def install_help_panel(host):
    """
    在主窗口上装一个帮助页控制器（重复调用会复用同一个）。
    :return: 控制器对象；main.ui 里没有帮助页控件时返回 None（不崩）
    """
    panel = getattr(host, "_help_panel", None)
    if panel is not None:
        return panel
    panel = _HelpPanel(host)
    if panel._title is None or panel._body is None:
        return None
    host._help_panel = panel
    try:
        panel.refresh()
    except Exception:
        pass
    return panel


def refresh_help(host):
    """选中节点变化后调用（`main.py::on_node_selected` 末尾一行）。"""
    panel = getattr(host, "_help_panel", None)
    if panel is None:
        return
    try:
        panel.refresh()
    except Exception:
        pass
