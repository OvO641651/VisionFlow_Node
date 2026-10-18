# -*- coding: utf-8 -*-
"""批次6 目标3-M2 判据：**帮助页 + 14 个节点 help_text**（方案 §3.2.3 / §十三 第 60 条）。

用户 2026.10.19 拍板：
  · 「可以在右下角的当前结果这个 tabwidget 中添加一页「帮助」，用于怎么显示节点内容」；
  · 帮助文本模板 =【用途】/【输入 / 输出】/【参数】/【典型场景】，**无【注意】段**；
  · **参数把参数窗口里出现的全部写上**，★ **每个参数独占一行**；没有可调参数就省略【参数】段；
  · 文案集中在 `core/help_texts.py`（纯数据、零依赖，风格对齐 `core/log_texts.py`）。
"""
import ast
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import QPointF                                   # noqa: E402
from PySide2.QtWidgets import QApplication, QLabel, QTextEdit        # noqa: E402

app = QApplication([])
import main as m                                                     # noqa: E402
from core import help_texts                                          # noqa: E402
from core.NodeRegistry import NODE_SPECS, get_spec                   # noqa: E402
from core.node_catalog import node_names                             # noqa: E402

_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def pump(n=4):
    for _ in range(n):
        app.processEvents()


# ===================== ① 14 个业务节点都有非空 help_text =====================
names = node_names()
missing = [n for n in names
           if not (getattr(NODE_SPECS.get(n), "help_text", "") or "").strip()]
check("① 14 个业务节点全部有非空 help_text", not missing, missing)
short = [n for n in names if len((getattr(NODE_SPECS.get(n), "help_text", "") or "").strip()) < 20]
check("① 每段说明都够长（≥20 字）", not short, short)

# ===================== ② 键集合 == 注册表 =====================
check("② help_texts.HELP 键集合 == 注册表节点名集合",
      set(help_texts.HELP) == set(NODE_SPECS),
      (sorted(set(help_texts.HELP) ^ set(NODE_SPECS)),))

# ===================== ③ 纯数据 / 零依赖（AST 检查） =====================
_src = open(os.path.join(PROJ, "core", "help_texts.py"), encoding="utf-8").read()
_tree = ast.parse(_src)
_bad = [type(n).__name__ for n in _tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                          ast.Import, ast.ImportFrom))]
check("③ help_texts 里没有 def / class / import（AST 检查）", not _bad, _bad)
_non_str = [k for k, v in help_texts.HELP.items() if not isinstance(v, str)]
check("③ HELP 的值全部是 str", not _non_str, _non_str)

# ===================== ④ 文本结构：三段必有 + 参数独占一行 =====================
REQ = ("【用途】", "【输入 / 输出】", "【典型场景】")
bad_sec = [n for n in names
           if any(seg not in (getattr(NODE_SPECS.get(n), "help_text", "") or "") for seg in REQ)]
check("④ 每段说明都含【用途】【输入 / 输出】【典型场景】", not bad_sec, bad_sec)
bad_note = [n for n in names if "【注意】" in (getattr(NODE_SPECS.get(n), "help_text", "") or "")]
check("④ 没有任何节点带【注意】段（用户要求去掉）", not bad_note, bad_note)

# 参数段：每个参数独占一行（形如「  ① …」「  ② …」的行数 ≥ 参数个数，且不出现「① …；②」同一行）
bad_param_line = []
no_param_ok = []
for n in names:
    txt = (getattr(NODE_SPECS.get(n), "help_text", "") or "")
    lines = [ln.strip() for ln in txt.splitlines()]
    if "【参数】" not in lines:
        # 没有参数段是允许的（灰度 / 取反），但不能出现 ①②③ 这种参数标记
        if any(ln[:1] in "①②③④⑤" for ln in lines):
            bad_param_line.append((n, "无【参数】段却写了参数"))
        else:
            no_param_ok.append(n)
        continue
    idx = lines.index("【参数】")
    # 取【参数】之后、下一个【xxx】之前的所有行
    block = []
    for ln in lines[idx + 1:]:
        if ln.startswith("【"):
            break
        if ln:
            block.append(ln)
    for ln in block:
        if ln.count("：") != 1 or ln[:1] not in "①②③④⑤⑥":
            bad_param_line.append((n, ln))
check("④ 每个参数独占一行（①…；② 不再挤在同一行）", not bad_param_line, bad_param_line)
check("④ 无参数段的节点只有预期的那几个（灰度 / 取反）",
      set(no_param_ok) <= {"灰度", "取反"}, no_param_ok)

# ===================== ⑤ 帮助页存在（在「当前结果」TabWidget 里） =====================
w = m.MainWindow()
w.main_window.resize(1400, 900)
w.main_window.show()
pump(8)
tab = w.main_window.result_tab
titles = [tab.tabText(i) for i in range(tab.count())]
check("⑤ 「当前结果」TabWidget 里新增了一页「帮助」", "帮助" in titles, titles)
check("⑤ 第 1 页仍是「当前结果」（日志页没被顶掉）", titles[0] == "当前结果", titles)
title = w.main_window.findChild(QLabel, "lbl_help_title")
body = w.main_window.findChild(QTextEdit, "text_help_body")
check("⑤ 帮助页控件存在（lbl_help_title / text_help_body）",
      title is not None and body is not None, (title, body))
check("⑤ 帮助正文只读、可滚（QTextEdit readOnly）", body is not None and body.isReadOnly(), None)

# ===================== ⑥ 未选中 / 选中 / 切换 / 取消 联动 =====================
w.on_node_selected(None)
pump(2)
check("⑥ 未选中：标题 =「帮助」、正文 =「请选择节点」",
      title.text() == "帮助" and body.toPlainText() == "请选择节点",
      (title.text(), body.toPlainText()))

node_a = w.add_flow_node("灰度", pos=QPointF(120, 120))
w.on_node_selected(node_a)
pump(2)
txt_a = body.toPlainText()
check("⑥ 选中「灰度」：标题含节点名与分组", "灰度" in title.text() and "处理" in title.text(), title.text())
check("⑥ 选中「灰度」：正文 == 注册表 help_text 原文",
      txt_a == get_spec("灰度").help_text, txt_a[:40])

node_b = w.add_flow_node("直线识别", pos=QPointF(360, 360))
w.on_node_selected(node_b)
pump(2)
txt_b = body.toPlainText()
check("⑥ 切换选中 ⇒ 标题与正文随之变化（两次文本不同）", txt_a != txt_b, (txt_a[:20], txt_b[:20]))
check("⑥ 选中「直线识别」：正文 == 该节点的 help_text",
      txt_b == get_spec("直线识别").help_text, txt_b[:40])

w.on_node_selected(None)
pump(2)
check("⑥ 取消选中 ⇒ 回到「请选择节点」", body.toPlainText() == "请选择节点", body.toPlainText())

# ===================== ⑦ 帮助页不撑宽窗口 =====================
w.main_window.resize(1400, 900)
pump(6)
check("⑦ 帮助正文不撑宽主窗口（正文宽 < 窗口宽）",
      body.width() < w.main_window.width(), (body.width(), w.main_window.width()))
check("⑦ 主窗口宽度没有被帮助页顶大（≤1400）", w.main_window.width() <= 1400, w.main_window.width())

print("")
print("通过 %d 项，失败 %d 项" % (_pass[0], len(_fails)))
if _fails:
    print("失败项：" + " / ".join(_fails))
sys.exit(1 if _fails else 0)
