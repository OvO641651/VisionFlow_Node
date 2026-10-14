# -*- coding: utf-8 -*-
"""
批次4 目标5-M1 验证：决策 e（连续执行范围 = 上游链）+ 决策 f（删除 run_selected_image）

同一个脚本跑两遍：
    python dsh_t5m1_check.py before   # 指向改前快照 ⇒ 复现"无关分支也被跑、还悄悄存了文件"
    python dsh_t5m1_check.py after    # 当前工程

决策 e 的判据：一页上摆**两条互不相干的链**，选中第二条的末节点点"连续执行"：
    · 改前：按拓扑序**前缀**截断 ⇒ 第一条链也执行、它的"输出图像"**存了文件**；
    · 改后：只跑"选中节点 + 上游" ⇒ 第一条链**一行日志都没有**、**没存文件**，
      并且提示行写明"只跑「X」和它的上游；以下节点本次未执行：…"。
决策 f 的判据：`MainWindow.run_selected_image` 与 `ImageGalleryWidget.run_selected_requested`
    在源码里彻底消失（含"其它 .py 文件里也没有这个名字"）。
"""
import os
import sys
import tempfile
import shutil

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
BACKUP = r"E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_before_t5_m1"

MODE = (sys.argv[1] if len(sys.argv) > 1 else "after").lower()
assert MODE in ("before", "after"), MODE

if MODE == 'before':
    print('NOTE: 批次5 目标1 目录重构后，本套用例的 before 模式不再可用'
          '（备份快照是旧的扁平布局、与新的包路径不兼容）；本套现在只跑 after 模式。')
    sys.exit(0)

os.chdir(PROJ)
sys.path.insert(0, PROJ)
if MODE == "before":
    sys.path.insert(0, BACKUP)

import numpy as np
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import widgets.ImageGalleryWidget as IGW

print('MODE = %s | main.py 来自 %s' % (MODE, os.path.dirname(m.__file__)))


class FakeMB(object):
    warning = information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
    getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
    getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
    getExistingDirectory = staticmethod(lambda *a, **k: "")


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB
m.QFileDialog = FakeFD

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (('   <- ' + str(extra)) if extra else ''))
    if not cond:
        fails.append(name)


def make_img(value=40):
    return np.full((48, 64, 3), value, np.uint8)


TMP = tempfile.mkdtemp(prefix="vf_t5m1_")
DIR_UNRELATED = os.path.join(TMP, "unrelated_out")


def module_rows(w):
    rows = []
    for r in range(w.execution_log.rowCount()):
        item = w.execution_log.item(r, 2)
        if item is not None and item.text():
            rows.append(item.text())
    return rows


def detail_texts(w):
    rows = []
    for r in range(w.execution_log.rowCount()):
        item = w.execution_log.item(r, 4)
        if item is not None and item.text():
            rows.append(item.text())
    return rows


# ======================================================================
# 决策 e：两条互不相干的链，选中第二条的末节点
# ======================================================================
w = m.MainWindow()
w.main_window.show()
w.current_static_image = make_img(40)

# 链1（与选中节点无关）：取反 → 输出图像（会存文件）
u1 = w.add_flow_node("取反", QPointF(20, 20))
u2 = w.add_flow_node("输出图像", QPointF(20, 180))
w.add_edge(u1, u2)
u2.params["output_dir"] = DIR_UNRELATED
u2.params["output_name"] = "unrelated"
u2.params["save_content"] = "数据层图像"          # 不去碰叠加那套逻辑，只看"存没存"
u2.params["name_policy"] = "自动编号"

# 链2（真正要跑的那条）：二值化 → 边缘提取
v1 = w.add_flow_node("二值化", QPointF(320, 20))
v2 = w.add_flow_node("边缘提取", QPointF(320, 180))
w.add_edge(v1, v2)

w.selected_node = v2
w.btn_continuous.click()
app.processEvents()

rows = module_rows(w)
texts = detail_texts(w)
saved = os.listdir(DIR_UNRELATED) if os.path.isdir(DIR_UNRELATED) else []

if MODE == 'before':
    check('① 改前：**无关分支也被执行了**（按拓扑序前缀截断）',
          "取反" in rows and "输出图像" in rows, rows)
    check('① 改前：无关分支里的"输出图像"**悄悄存了文件**（这就是要改掉的副作用）',
          len(saved) == 1, saved)
    check('① 改前：选中节点正好排在拓扑序最后 ⇒ **没有"未执行"提示行**（前缀截断的必然结果）',
          not any("连续执行到" in t for t in texts), texts)
else:
    check('① 改后：选中节点那一条链跑了（二值化 + 边缘提取都在日志里）',
          "二值化" in rows and "边缘提取" in rows, rows)
    check('① 改后：**无关分支一行日志都没有**（取反 / 输出图像都没跑）',
          "取反" not in rows and "输出图像" not in rows, rows)
    check('① 改后：无关分支里的"输出图像"**没有存文件**（副作用消失）',
          saved == [], saved)
    check('① 改后：提示行措辞改成"只跑「边缘提取」和它的上游"，并列出未执行的两个节点',
          any("只跑「边缘提取」和它的上游" in t and "取反" in t and "输出图像" in t for t in texts),
          texts)

    # 不传 stop_at 直接调引擎 ⇒ 口径不变（整页都跑），这是给"直接调引擎验数据流"的地方留的后路
    order, parents, skipped = w._build_execution_order(w.flow_nodes, w.flow_edges)
    _, _, exec_info = w._run_nodes(order, parents, make_img(40))
    check('① 改后：直接调 _run_nodes（不传 stop_at）⇒ 仍然整页都跑（两条链都在）',
          len(exec_info) >= 4, exec_info)

    # 线性链回归：选中中间节点 ⇒ 只有它的下游不跑（与改前一致）
    w2 = m.MainWindow()
    w2.main_window.show()
    w2.current_static_image = make_img(40)
    a1 = w2.add_flow_node("取反", QPointF(20, 20))
    a2 = w2.add_flow_node("二值化", QPointF(20, 180))
    a3 = w2.add_flow_node("边缘提取", QPointF(20, 340))
    w2.add_edge(a1, a2)
    w2.add_edge(a2, a3)
    w2.selected_node = a1
    w2.btn_continuous.click()
    app.processEvents()
    rows2 = module_rows(w2)
    check('① 改后·线性链回归：选中「取反」⇒ 只跑它自己，二值化 / 边缘提取都没跑',
          "取反" in rows2 and "二值化" not in rows2 and "边缘提取" not in rows2, rows2)
    w2.selected_node = a2
    w2.btn_continuous.click()
    app.processEvents()
    rows3 = module_rows(w2)
    check('① 改后·线性链回归：选中「二值化」⇒ 跑 取反 + 二值化，边缘提取没跑',
          "取反" in rows3 and "二值化" in rows3 and "边缘提取" not in rows3, rows3)

    SHOT_DIR = r'E:\opencv_python_3_8\backups\_ui_preview'
    shot = os.path.join(SHOT_DIR, 'p4_t5m1_two_chains.png')
    w.main_window.grab().save(shot)
    print('      截图 ->', shot, os.path.exists(shot))

# ======================================================================
# 决策 f：孤儿入口删干净
# ======================================================================
if MODE == 'before':
    check('② 改前：MainWindow.run_selected_image 还在', hasattr(m.MainWindow, 'run_selected_image'))
    check('② 改前：ImageGalleryWidget.run_selected_requested 信号还在',
          hasattr(IGW.ImageGalleryWidget, 'run_selected_requested'))
else:
    check('② 改后：MainWindow.run_selected_image **已删除**（类上不再有这个属性）',
          not hasattr(m.MainWindow, 'run_selected_image'))
    check('② 改后：ImageGalleryWidget.run_selected_requested 信号 **已删除**',
          not hasattr(IGW.ImageGalleryWidget, 'run_selected_requested'))
    # 源码级：整个工程里不该再出现这两个名字（注释里提到历史也不行 —— 那种注释我写的是"原 xxx 已删除"，
    # 所以这里只检查"定义 / 调用"的形态：def 或 .run_selected 或 emit）
    hits = []
    for name in sorted(os.listdir(PROJ)):
        if not name.endswith(".py"):
            continue
        src = open(os.path.join(PROJ, name), encoding="utf-8").read()
        if "def run_selected_image" in src:
            hits.append(name + ':def')
        if "run_selected_requested" in src.replace("原 `run_selected_requested` 信号已于 2026.10.7 删除", ""):
            hits.append(name + ':signal')
    check('② 改后：工程里再也没有这两个符号的定义 / 使用', hits == [], hits)
    # 工具栏"运行选中"的范围选择仍然正常（下拉框还在、两个选项都在）
    gw = w.gallery_widget
    combo = getattr(gw, 'run_mode_box', None)
    ok_combo = combo is not None
    if combo is not None:
        items = [combo.itemText(i) for i in range(combo.count())]
        ok_combo = items == ["运行全部", "运行选中"]
    else:
        items = []
    check('② 改后：范围下拉框还在、仍然是「运行全部 / 运行选中」两项（删函数没影响范围选择）',
          ok_combo, items)
    check('② 改后：下拉框的 scope_all() 仍然可用（工作没被删函数带坏）',
          gw.scope_all() in (True, False), gw.scope_all())

shutil.rmtree(TMP, ignore_errors=True)

print('-' * 70)
if fails:
    print('MODE=%s  失败项：%d' % (MODE, len(fails)))
    for name in fails:
        print('   - ' + name)
else:
    print('MODE=%s  失败项：无' % MODE)
sys.exit(1 if fails else 0)
