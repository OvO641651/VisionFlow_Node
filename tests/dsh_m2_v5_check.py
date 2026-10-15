# -*- coding: utf-8 -*-
"""M2 最终验收（v1.18：范围改成下拉框 + 停止独立按钮）：模式/范围/跟随/停止/删除/折叠"""
import os
import sys
import tempfile
import shutil

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2.QtWidgets import QApplication, QComboBox, QToolButton
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages

warns = []


class FakeMB(object):
    warning = staticmethod(lambda parent, title, text: warns.append(text))
    information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


def wait_batch(w, limit=8000):
    """★ 批次5 目标3：「运行全部」改成**分片执行**（一张图一个分片、片之间让出事件循环）
    ⇒ 点完"连续执行"要推进事件循环才算跑完。旧版是同步 for 循环，不需要等。
    本函数把事件循环推到批量结束（`_batch_state` 清空）。"""
    guard = 0
    while w._batch_state is not None and guard < limit:
        app.processEvents()
        guard += 1


tmp = tempfile.mkdtemp(prefix="vf_v5_")
vals = {"A": 40, "B": 130, "C": 210}
paths = {}
for k, v in vals.items():
    p = os.path.join(tmp, k + ".png")
    cv2.imwrite(p, np.full((80, 100, 3), v, np.uint8))
    paths[k] = p
pA, pB, pC = paths["A"], paths["B"], paths["C"]


class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([pA, pB, pC], ""))
    getOpenFileName = staticmethod(lambda *a, **k: (pA, ""))
    getExistingDirectory = staticmethod(lambda *a, **k: tmp)


m.QFileDialog = FakeFD
w = m.MainWindow()
w.main_window.show()
gw = w.gallery_widget
n_src = w.add_flow_node("图片源", QPointF(20, 20))
n_src.params["source_type"] = "图片"
n_src.params["source_path"] = pA
n_inv = w.add_flow_node("取反", QPointF(20, 160))
w.add_edge(n_src, n_inv)
w.selected_node = n_inv
gw.add_button.click()
check("准备：图库 3 张", gw.count() == 3, gw.count())


def ran_rows():
    return len([r for r in range(w.execution_log.rowCount())
                if w.execution_log.item(r, 2) and w.execution_log.item(r, 2).text() == "取反"])


# ============ 一、控件形态：下拉框（两种模式）+ 停止独立按钮放在它后面、＋图片前面 ============
check("范围控件是下拉框（QComboBox）", isinstance(gw.run_mode_box, QComboBox), type(gw.run_mode_box).__name__)
check("下拉框两项 = 运行全部 / 运行选中",
      [gw.run_mode_box.itemText(i) for i in range(gw.run_mode_box.count())] == ["运行全部", "运行选中"],
      [gw.run_mode_box.itemText(i) for i in range(gw.run_mode_box.count())])
check("停止是独立按钮（QToolButton，文字'停止'）",
      isinstance(gw.stop_button, QToolButton) and gw.stop_button.text() == "停止")
lay = gw.toolbar.layout()
order = [lay.itemAt(i).widget().objectName() for i in range(lay.count())
         if lay.itemAt(i).widget() is not None]
print("   工具栏顺序：", order)
check("停止按钮排在'范围下拉框'之后、'＋图片'之前",
      order.index("gallery_run_mode") < order.index("gallery_stop_button") < order.index("gallery_add_button"),
      order)

# ============ 二、问题 1：永远有且只有一个模式（切走不会变"两个都没选"）============
gw.set_scope_all(True)
check("选'运行全部'：scope_all 为真、scope_current 为假",
      gw.scope_all() is True and gw.scope_current() is False, (gw.scope_all(), gw.scope_current()))
gw.set_scope_all(False)
check("切到'运行选中'：scope_current 为真、scope_all 为假（不需要再点别的按钮）",
      gw.scope_current() is True and gw.scope_all() is False, (gw.scope_all(), gw.scope_current()))
check("任何时候都不会出现'两个都没选'", gw.scope_all() != gw.scope_current())
gw.set_scope_all(True)
check("切回'运行全部'：又是一真一假", gw.scope_all() != gw.scope_current(), gw.run_mode())

# ============ 三、下拉框只选模式、不执行 ============
w.execution_log.setRowCount(0)
cache_before = len(w.result_cache)
gw.set_scope_all(False)
gw.set_scope_all(True)
check("切模式本身**不执行**（日志 0 行）", w.execution_log.rowCount() == 0, w.execution_log.rowCount())
check("切模式本身**不执行**（无新缓存）", len(w.result_cache) == cache_before)

# ============ 四、范围对"连续执行"的影响 + 逐张真的换图 ============
gw.auto_switch_box.setChecked(False)
gw.set_scope_all(True)
gw.set_current_index(0)
w.execution_log.setRowCount(0)
w.btn_continuous.click()
wait_batch(w)                     # ★ 目标3：分片执行要推进事件循环才跑完
check("范围=运行全部 → 连续执行跑 3 张", ran_rows() == 3, ran_rows())
gw.set_scope_all(False)
gw.set_current_index(0)
w.execution_log.setRowCount(0)
w.btn_continuous.click()
check("范围=运行选中 → 连续执行只跑 1 张", ran_rows() == 1, ran_rows())


def cached_mean(path):
    key = os.path.normcase(os.path.abspath(path))
    hit = [v for k, v in w.result_cache.items()
           if isinstance(k[0], str) and os.path.normcase(os.path.abspath(k[0])) == key]
    return None if not hit else float(np.mean(hit[-1]["frame"]))


mA, mB, mC = cached_mean(pA), cached_mean(pB), cached_mean(pC)
print("   三张结果均值 =", mA, mB, mC, "（期望≈215 / 125 / 45）")
check("批量真的逐张换图（A/B/C 各自的结果对得上）",
      all(v is not None for v in (mA, mB, mC)) and abs(mA - 215) < 10 and abs(mB - 125) < 10
      and abs(mC - 45) < 10, (mA, mB, mC))

# ============ 五、自动切换：不跟随即还原，跟随则停在最后 ============
gw.auto_switch_box.setChecked(False)
gw.set_scope_all(True)
gw.set_current_index(1)
w._show_static_image(gw.item_frame(gw.gallery_list.item(1)))
w.btn_continuous.click()
wait_batch(w)                     # ★ 目标3：等分片跑完
cur = float(np.mean(w.current_static_image)) if w.current_static_image is not None else None
check("不勾'自动切换'：跑完选中项回到第 2 张", gw.current_index() == 1, gw.current_index())
check("不勾'自动切换'：画面也回到第 2 张（B=130）", cur is not None and abs(cur - 130) < 3, cur)
gw.auto_switch_box.setChecked(True)
gw.set_current_index(0)
w._show_static_image(gw.item_frame(gw.gallery_list.item(0)))
w.btn_continuous.click()
wait_batch(w)                     # ★ 目标3：等分片跑完
cur = float(np.mean(w.current_static_image)) if w.current_static_image is not None else None
check("勾'自动切换'：跑完停在最后一张（C=210）", gw.current_index() == 2 and cur is not None
      and abs(cur - 210) < 3, (gw.current_index(), cur))
gw.auto_switch_box.setChecked(False)

# ============ 六、"停止"按钮：批量跑一半点它 → 立刻停 ============
gw.set_scope_all(True)
gw.set_current_index(0)
calls = {"n": 0}
orig = w._execute_static


def patched(frame, mode, node=None, adopt_frame=True, **kwargs):
    calls["n"] += 1
    r = orig(frame, mode, node, adopt_frame, **kwargs)
    if calls["n"] == 1:
        gw.stop_button.click()                  # 用户中途点"停止"按钮
    return r


w.execution_log.setRowCount(0)
w._execute_static = patched
w.btn_continuous.click()
wait_batch(w)                     # ★ 目标3：等分片跑完（"停止"在下一片开头生效）
w._execute_static = orig
hints = [w.execution_log.item(r, 4).text() for r in range(w.execution_log.rowCount())
         if w.execution_log.item(r, 4)]
check("点'停止'按钮 → 只跑了 1 张就停", calls["n"] == 1, calls)
check("点'停止'按钮 → 日志写明原因", any("用户停止" in t for t in hints), hints)

# ============ 七、折叠 ============
gw.collapse_button.click()
check("折叠后列表收起、按钮变 ∧", gw.gallery_list.isVisible() is False and gw.collapse_button.text() == "∧",
      (gw.gallery_list.isVisible(), gw.collapse_button.text()))
gw.collapse_button.click()
check("再点恢复展开", gw.gallery_list.isVisible() is True and gw.collapse_button.text() == "∨")

# ============ 八、删光图库：清画布 + 清图片源路径 + 不再跑出来 ============
while gw.count() > 0:
    gw.set_current_index(0)
    gw.delete_button.click()
check("全删光后图库为空、画布已清空", gw.count() == 0 and getattr(w.image_view, "pixmap_item", "无") is None,
      (gw.count(), getattr(w.image_view, "pixmap_item", "无")))
check("全删光后'图片源'节点里的路径被清空", (n_src.params.get("source_path") or "") == "",
      n_src.params.get("source_path"))
warns[:] = []
w.execution_log.setRowCount(0)
w.btn_continuous.click()
check("再执行：图没有再被跑出来（画布仍空）",
      getattr(w.image_view, "pixmap_item", "无") is None and w.current_static_image is None)
check("再执行：给出'请先导入图片'提示", any("导入" in t for t in warns), warns)
check("再执行：图库仍是空的", gw.count() == 0, gw.count())

shutil.rmtree(tmp, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
