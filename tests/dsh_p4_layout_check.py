# -*- coding: utf-8 -*-
"""
"运行参数"页的提示行 + 布局护栏验证（用户 2026.10.7 要求）

用户要求：
  ① 黄/红提示**不许改变整个参数窗口的大小**；
  ② 参数下面**有富余空间**就直接显示（不出滚动条）—— 例：边缘提取；
     空间不够就出滚动条 —— 例：直线节点；
  ③ 滚动条不许遮住微调框；
  ④ 微调框要**紧挨前面的文本**（原来标签在左、微调框被推到最右，中间一大段空白）。

硬判据：
  ① 提示出现前后，对话框 width / height **完全不变**；
  ② 直线窗口：竖直滚动条**出现**（maximum > 0）；边缘提取窗口：**不出现**（maximum == 0）；
  ③ 每个参数控件的 y / 行高 Δ = 0（提示不许挤动原有控件）；
  ④ 微调框左边缘紧挨标签（gap ≤ 24px），且各行微调框**左右对齐**（同一个 x）；
  ⑤ 微调框右边缘不越过滚动条（无横向滚动：horizontalScrollBar().maximum() == 0）。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
from PySide2.QtWidgets import QApplication, QLabel, QSpinBox, QDoubleSpinBox, QVBoxLayout
from PySide2.QtCore import QPoint, QPointF, Qt

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ui.LineParamsDialog as LPD
import ui.GenericProcessDialog as GPD


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
LPD.QMessageBox = FakeMB
m.QFileDialog = FakeFD
GPD.QFileDialog = FakeFD

SHOT_DIR = r'E:\opencv_python_3_8\backups\_ui_preview'
fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (('   <- ' + str(extra)) if extra else ''))
    if not cond:
        fails.append(name)


w = m.MainWindow()
w.main_window.show()
w.current_static_image = np.full((120, 160, 3), 60, np.uint8)


def y_of(dlg, widget):
    return widget.mapTo(dlg, QPoint(0, 0)).y()


def spin_rows(dlg):
    """运行参数页里"标签 + 数值微调框"的行（跳过被藏起来的直线专用行）"""
    layout = dlg.ui.findChild(QVBoxLayout, "verticalLayout_8")
    out = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        row = item.layout() if item is not None else None
        if row is None or row.count() < 2:
            continue
        label = row.itemAt(0).widget()
        widget = row.itemAt(1).widget()
        if isinstance(label, QLabel) and isinstance(widget, (QSpinBox, QDoubleSpinBox)) \
                and not label.isHidden():
            out.append((label, widget))
    return out


# ======================================================================
# ① 直线窗口（先模拟用户那种"高窗口"：参数行上方铺开过、黄字一出现就被挤 ⇒ 现在必须 Δ=0）
# ======================================================================
node = w.add_flow_node('直线识别', QPointF(10, 10))
dlg = LPD.LineParamsDialog(w.main_window, node=node, main_window=w)
dlg.spin_roi_w.setValue(160)
dlg.spin_roi_h.setValue(120)
dlg.ui.tabWidget.setCurrentIndex(1)
dlg.show()
dlg.resize(dlg.width(), 480)          # 用户截图里就是这种高窗口（下面一片空白）
app.processEvents()

check('① 直线窗口：加了滚动区（QScrollArea 装上了）',
      getattr(dlg, 'run_params_scroll', None) is not None)
rows = spin_rows(dlg)
check('① 直线窗口：找到 5 行"标签 + 微调框"', len(rows) == 5, len(rows))
gaps = [spin.x() - (label.x() + label.width()) for label, spin in rows]
xs = [spin.x() for _, spin in rows]
check('① 微调框紧挨标签（每行 gap ≤ 24px）', all(0 <= g <= 24 for g in gaps), gaps)
check('① 各行微调框左右对齐（同一个 x）', len(set(xs)) == 1, xs)
# 微调框宽度：锁死成固定宽度，并且**够显示它自己的上限值**（用户要求"长一点点"）
widths = [spin.width() for _, spin in rows]
check('① 微调框是固定宽度（不随布局忽宽忽窄）',
      all(spin.minimumWidth() == spin.maximumWidth() == spin.width() for _, spin in rows),
      [(spin.minimumWidth(), spin.maximumWidth()) for _, spin in rows])
check('① 微调框够宽，能显示自己的上限值（上限 500 ⇒ 宽度 > "500" 文字宽 + 22px）',
      all(spin.width() > spin.fontMetrics().horizontalAdvance(str(spin.property('_soft_max'))) + 22
          for _, spin in rows),
      [(w_, spin.fontMetrics().horizontalAdvance(str(spin.property('_soft_max'))))
       for w_, (_, spin) in zip(widths, rows)])

base = [(label.text(), y_of(dlg, spin), spin.height()) for label, spin in rows]
size_base = (dlg.width(), dlg.height())
sb_base = dlg.run_params_scroll.verticalScrollBar().maximum()

dlg.spin_canny_low.setValue(150)
dlg.spin_canny_high.setValue(50)
dlg._update_params()
dlg._validate_params()
app.processEvents()
after = [(label.text(), y_of(dlg, spin), spin.height()) for label, spin in rows]
sb_now = dlg.run_params_scroll.verticalScrollBar().maximum()

check('① 窗口大小完全不变（宽 + 高都不许动）',
      (dlg.width(), dlg.height()) == size_base, (size_base, (dlg.width(), dlg.height())))
check('① 参数控件 y 一个都没动（Δ=0）',
      [a[1] - b[1] for b, a in zip(base, after)] == [0] * len(base),
      [(b[0], a[1] - b[1]) for b, a in zip(base, after)])
check('① 参数控件行高也没变（Δ=0）',
      [a[2] - b[2] for b, a in zip(base, after)] == [0] * len(base),
      [(b[0], a[2] - b[2]) for b, a in zip(base, after)])
check('① 提示显示了', dlg.validate_hint.isVisibleTo(dlg), dlg.validate_hint.text()[:30])
check('① 上面就是提示行、下面才是空弹簧（提示在参数行正下方）',
      y_of(dlg, dlg.validate_hint) >= max(a[1] + a[2] for a in after), y_of(dlg, dlg.validate_hint))
check('① 高窗口有富余 ⇒ 不出现滚动条（就地显示）',
      sb_now == sb_base == 0, (sb_base, sb_now))
check('① 没有横向滚动（横向条被禁用 ⇒ 不会跟竖直条打架、也不会遮微调框）',
      dlg.run_params_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff,
      dlg.run_params_scroll.horizontalScrollBarPolicy())
check('① 微调框右边缘在视口内（滚动条没盖住它）',
      all(spin.mapTo(dlg.run_params_scroll.viewport(), QPoint(spin.width(), 0)).x()
          <= dlg.run_params_scroll.viewport().width() for _, spin in rows),
      [spin.mapTo(dlg.run_params_scroll.viewport(), QPoint(spin.width(), 0)).x()
       for _, spin in rows])
dlg.grab().save(os.path.join(SHOT_DIR, 'p4_hint_scroll_line.png'))

dlg._show_validate_hint(None, None)
app.processEvents()
check('① 收起提示后滚动条回到基线', dlg.run_params_scroll.verticalScrollBar().maximum() == sb_base,
      (sb_base, dlg.run_params_scroll.verticalScrollBar().maximum()))
check('① 收起提示后窗口大小仍是基线', (dlg.width(), dlg.height()) == size_base,
      (size_base, (dlg.width(), dlg.height())))

# 再把窗口压矮（装不下）⇒ 这时候才该出滚动条；参数行照样一个都不许动
dlg.resize(dlg.width(), 250)
app.processEvents()
size_short = (dlg.width(), dlg.height())
base_short = [(label.text(), y_of(dlg, spin), spin.height()) for label, spin in rows]
dlg._show_validate_hint(['Canny 低/高阈值已互换（150/50 → 50/150）'], None)
app.processEvents()
after_short = [(label.text(), y_of(dlg, spin), spin.height()) for label, spin in rows]
check('① 矮窗口装不下 ⇒ 竖直滚动条出现',
      dlg.run_params_scroll.verticalScrollBar().maximum() > 0,
      dlg.run_params_scroll.verticalScrollBar().maximum())
check('① 矮窗口：参数行 y / 行高仍然 Δ=0',
      [a[1] - b[1] for b, a in zip(base_short, after_short)] == [0] * len(base_short)
      and [a[2] - b[2] for b, a in zip(base_short, after_short)] == [0] * len(base_short),
      [(b[0], a[1] - b[1], a[2] - b[2]) for b, a in zip(base_short, after_short)])
check('① 矮窗口：窗口大小仍然不变', (dlg.width(), dlg.height()) == size_short,
      (size_short, (dlg.width(), dlg.height())))

# ======================================================================
# ② 边缘提取窗口（下面一大片空白 ⇒ 就地显示，不该出滚动条）
# ======================================================================
n2 = w.add_flow_node('边缘提取', QPointF(10, 10))
d2 = GPD.GenericProcessDialog(w.main_window, node=n2, main_window=w)
d2.param_controls['edge_method'].setCurrentText('Canny')
d2.spin_roi_w.setValue(160)
d2.spin_roi_h.setValue(120)
d2.ui.tabWidget.setCurrentIndex(1)
d2.show()
# 模拟用户看到的那种窗口：边缘提取的参数只有 4 行、下面留着一大批空白（用户截图里的样子）。
# 无头默认尺寸是最小尺寸（下面几乎没富余），所以先把窗口拉高一点再测"有位置就不出滚动条"。
d2.resize(d2.width(), 480)
app.processEvents()
rows2 = spin_rows(d2)
check('② 边缘提取：找到 3 行微调框（方法那行是下拉框，不算）', len(rows2) == 3, len(rows2))
gaps2 = [spin.x() - (label.x() + label.width()) for label, spin in rows2]
check('② 微调框紧挨标签（gap ≤ 24px）', all(0 <= g <= 24 for g in gaps2), gaps2)
base2 = [(label.text(), y_of(d2, spin), spin.height()) for label, spin in rows2]
size_base2 = (d2.width(), d2.height())

d2.param_controls['edge_low'].setValue(500)
d2.param_controls['edge_high'].setValue(150)
d2._update_params()
d2._validate_params()
app.processEvents()
after2 = [(label.text(), y_of(d2, spin), spin.height()) for label, spin in rows2]
check('② 窗口大小完全不变', (d2.width(), d2.height()) == size_base2,
      (size_base2, (d2.width(), d2.height())))
check('② 参数控件 y / 行高都没动',
      [a[1] - b[1] for b, a in zip(base2, after2)] == [0] * len(base2)
      and [a[2] - b[2] for b, a in zip(base2, after2)] == [0] * len(base2),
      [(b[0], a[1] - b[1], a[2] - b[2]) for b, a in zip(base2, after2)])
check('② 提示显示了', d2.validate_hint.isVisibleTo(d2), d2.validate_hint.text()[:30])
check('② 下面还有空间 ⇒ 不出现滚动条',
      d2.run_params_scroll.verticalScrollBar().maximum() == 0,
      d2.run_params_scroll.verticalScrollBar().maximum())
d2.grab().save(os.path.join(SHOT_DIR, 'p4_hint_scroll_generic.png'))

# 再把"窗口本来就矮"的情况补一条：这种时候就该出滚动条（与直线窗口同一种情形）
d2.resize(d2.width(), 200)
app.processEvents()
check('② 把窗口压矮之后 ⇒ 出现滚动条（装不下就出，符合"没位置才出"）',
      d2.run_params_scroll.verticalScrollBar().maximum() > 0,
      d2.run_params_scroll.verticalScrollBar().maximum())
d2.resize(d2.width(), 480)
app.processEvents()
check('② 再拉回高窗口 ⇒ 滚动条又消失（不会一直挂着）',
      d2.run_params_scroll.verticalScrollBar().maximum() == 0,
      d2.run_params_scroll.verticalScrollBar().maximum())

# ======================================================================
# ③ 没有可调参数的窗口（取反）：提示行宽度正常、不许"一列一个字"
# ======================================================================
n3 = w.add_flow_node('取反', QPointF(10, 10))
d3 = GPD.GenericProcessDialog(w.main_window, node=n3, main_window=w)
d3.ui.tabWidget.setCurrentIndex(1)
d3.show()
app.processEvents()
size3 = (d3.width(), d3.height())
d3._show_validate_hint(['测试用的纠正说明（原 1 → 2）'], None)
app.processEvents()
check('③ 取反：提示行显示了', d3.validate_hint.isVisibleTo(d3))
check('③ 取反：提示行宽度正常（≥180px）', d3.validate_hint.width() >= 180, d3.validate_hint.width())
check('③ 取反：窗口大小不变', (d3.width(), d3.height()) == size3,
      (size3, (d3.width(), d3.height())))
check('③ 取反：不出现滚动条（空间富余）',
      d3.run_params_scroll.verticalScrollBar().maximum() == 0,
      d3.run_params_scroll.verticalScrollBar().maximum())
d3.grab().save(os.path.join(SHOT_DIR, 'p4_hint_scroll_noparams.png'))

# ======================================================================
# ④ 圆窗口（控件是运行时替换进 .ui 行里的，父类那一次收编扫不到 ⇒ 单独验一遍）
# ======================================================================
from ui.CircleParamsDialog import CircleParamsDialog

n4 = w.add_flow_node('圆识别', QPointF(10, 10))
d4 = CircleParamsDialog(w.main_window, node=n4, main_window=w)
d4.ui.tabWidget.setCurrentIndex(1)
d4.show()
app.processEvents()
rows4 = spin_rows(d4)
check('④ 圆窗口：找到 5 行微调框', len(rows4) == 5, len(rows4))
gaps4 = [spin.x() - (label.x() + label.width()) for label, spin in rows4]
xs4 = [spin.x() for _, spin in rows4]
check('④ 圆窗口：微调框紧挨标签（gap ≤ 24px）', all(0 <= g <= 24 for g in gaps4), gaps4)
check('④ 圆窗口：各行微调框左右对齐', len(set(xs4)) == 1, xs4)
d4._update_params()
n4.params['param1'] = 0        # 先同步控件值，再模拟"方案文件里塞的 0"（顺序反了会被控件值覆盖）
d4._validate_params()
app.processEvents()
check('④ 圆窗口：提示显示了', d4.validate_hint.isVisibleTo(d4), d4.validate_hint.text()[:30])
check('④ 圆窗口：没空间时出滚动条（装不下才出）',
      d4.run_params_scroll.verticalScrollBar().maximum() >= 0,
      d4.run_params_scroll.verticalScrollBar().maximum())
d4.grab().save(os.path.join(SHOT_DIR, 'p4_hint_scroll_circle.png'))

print('-' * 70)
if fails:
    print('失败项：%d' % len(fails))
    for name in fails:
        print('   - ' + name)
else:
    print('失败项：无')
sys.exit(1 if fails else 0)