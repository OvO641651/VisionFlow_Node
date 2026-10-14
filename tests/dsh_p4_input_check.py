# -*- coding: utf-8 -*-
"""
数值输入的"软范围"验证（用户 2026.10.7 要求）：
  范围 1~10 时输入 11 —— 现在打不进去（只留一个 1）；
  要改成"**可以先打完越界值，回车 / 点别处时自动变成上限或下限**"。

同一个脚本跑两遍：
    python dsh_p4_input_check.py before   # sys.path 指向改前的备份目录
    python dsh_p4_input_check.py after    # 当前工程
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
BACKUP = r"E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_before_param_input"

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

from PySide2.QtWidgets import QApplication, QSpinBox, QDoubleSpinBox
from PySide2.QtGui import QKeyEvent
from PySide2.QtCore import Qt, QEvent, QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ui.LineParamsDialog as LPD
import ui.GenericProcessDialog as GPD
from ui.CircleParamsDialog import CircleParamsDialog

print('MODE = %s | LineParamsDialog 来自 %s' % (MODE, os.path.dirname(LPD.__file__)))


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

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (('   <- ' + str(extra)) if extra else ''))
    if not cond:
        fails.append(name)


def type_text(widget, text):
    """把按键逐个投给控件（走真实 keyPressEvent + validator），模拟用户打字"""
    edit = widget.lineEdit()
    for ch in text:
        app.sendEvent(edit, QKeyEvent(QEvent.KeyPress, Qt.Key_0 + int(ch), Qt.NoModifier, ch))
        app.processEvents()


def retype(widget, old_value, keys):
    """把光标内容全选后重新键入 keys；返回 (打字后的 text, 打字后的 value)"""
    widget.setValue(old_value)
    widget.setFocus()
    widget.lineEdit().selectAll()
    type_text(widget, keys)
    return widget.lineEdit().text(), widget.value()


w = m.MainWindow()
w.main_window.show()

# ----------------------------------------------------------------------
# ① 直线窗口：Canny 低阈值（逻辑 0~500）打 999
# ----------------------------------------------------------------------
node = w.add_flow_node('直线识别', QPointF(10, 10))
dlg = LPD.LineParamsDialog(w.main_window, node=node, main_window=w)
spin = dlg.spin_canny_low
text, value = retype(spin, 50, '999')
if MODE == 'before':
    check('① 改前：打 999 进不去（只留下截断后的值）',
          text != '999', 'text=%r value=%s' % (text, value))
else:
    check('① 打 999 时**字符全都进得去**（text 就是 999）', text == '999', repr(text))
    check('① 打字过程中不改 value（关掉了边打边改）', value == 50, value)
    spin.interpretText()
    app.processEvents()
    check('① 提交（回车 / 失焦）后夹到上限 500',
          (spin.lineEdit().text(), spin.value()) == ('500', 500),
          (spin.lineEdit().text(), spin.value()))

# ----------------------------------------------------------------------
# ② 通用窗口：滤波核大小（逻辑 1~31，还要求奇数）打 44
# ----------------------------------------------------------------------
n2 = w.add_flow_node('滤波', QPointF(10, 10))
d2 = GPD.GenericProcessDialog(w.main_window, node=n2, main_window=w)
spin2 = d2.param_controls['blur_ksize']
text2, value2 = retype(spin2, 3, '44')
if MODE == 'before':
    check('② 改前：打 44 进不去（被奇数规则 + 上限一起吃掉了）',
          text2 != '44', 'text=%r value=%s' % (text2, value2))
else:
    check('② 打 44 时字符进得去', text2 == '44', repr(text2))
    spin2.interpretText()
    app.processEvents()
    check('② 提交后夹到上限 31（而且是奇数）',
          (spin2.lineEdit().text(), spin2.value()) == ('31', 31),
          (spin2.lineEdit().text(), spin2.value()))
    # 打字过程不许改值
    text3, value3 = retype(spin2, 3, '17')
    check('② 打 17（合法值）时 value 也等提交后才变', value3 == 3, value3)
    spin2.interpretText()
    app.processEvents()
    check('② 提交 17 ⇒ 17', spin2.value() == 17, spin2.value())
    # 偶数要变成奇数（老规矩不能丢）
    text4, _ = retype(spin2, 3, '8')
    spin2.interpretText()
    app.processEvents()
    check('② 提交偶数 8 ⇒ 变成奇数 9（奇数规则还在）', spin2.value() == 9, spin2.value())

# ----------------------------------------------------------------------
# ③ 圆窗口：param2（逻辑 1~1000）打 5000 / 打 0
# ----------------------------------------------------------------------
n3 = w.add_flow_node('圆识别', QPointF(10, 10))
d3 = CircleParamsDialog(w.main_window, node=n3, main_window=w)
spin3 = d3.spin_param2
text5, value5 = retype(spin3, 80, '5000')
if MODE == 'before':
    check('③ 改前：打 5000 进不去', text5 != '5000', 'text=%r value=%s' % (text5, value5))
else:
    check('③ 打 5000 时字符进得去', text5 == '5000', repr(text5))
    spin3.interpretText()
    app.processEvents()
    check('③ 提交后夹到上限 1000', spin3.value() == 1000, spin3.value())
    text6, _ = retype(spin3, 80, '0')
    spin3.interpretText()
    app.processEvents()
    check('③ 打 0 提交后夹到**下限** 1（不是 0）',
          (spin3.lineEdit().text(), spin3.value()) == ('1', 1),
          (spin3.lineEdit().text(), spin3.value()))

if MODE == 'after':
    # ------------------------------------------------------------------
    # ④ 软范围的"体检"：开关装上了、真范围存着、控件范围被放宽
    # ------------------------------------------------------------------
    check('④ 已关掉 keyboardTracking（不再边打边改）', spin.keyboardTracking() is False)
    check('④ 真范围存在 _soft_min / _soft_max 上（0 / 500）',
          (spin.property('_soft_min'), spin.property('_soft_max')) == (0, 500),
          (spin.property('_soft_min'), spin.property('_soft_max')))
    check('④ 控件自身范围被放宽了（比真范围宽）',
          spin.minimum() < 0 and spin.maximum() > 500, (spin.minimum(), spin.maximum()))
    check('④ 通用窗口的数值控件也装上了软范围',
          spin2.keyboardTracking() is False and spin2.property('_soft_max') == 31,
          (spin2.keyboardTracking(), spin2.property('_soft_max')))
    check('④ 圆窗口的数值控件也装上了软范围',
          spin3.keyboardTracking() is False and spin3.property('_soft_max') == 1000,
          (spin3.keyboardTracking(), spin3.property('_soft_max')))
    roi_w = dlg.spin_roi_w
    check('④ .ui 里的 ROI 控件也装上了软范围（真范围 0~10000）',
          roi_w.keyboardTracking() is False and roi_w.property('_soft_max') == 10000,
          (roi_w.keyboardTracking(), roi_w.property('_soft_max')))
    # 浮点控件
    sigma = d2.param_controls['blur_sigma']
    check('④ 浮点控件（QDoubleSpinBox）也装上了软范围',
          sigma.keyboardTracking() is False and sigma.property('_soft_max') == 20.0,
          (sigma.keyboardTracking(), sigma.property('_soft_max')))
    stext, _ = retype(sigma, 0.0, '999')
    sigma.interpretText()
    app.processEvents()
    check('④ 浮点打 999 提交后夹到 20', abs(sigma.value() - 20.0) < 1e-6, sigma.value())

    # ------------------------------------------------------------------
    # ⑤ "点了执行 / 确定"也要按提交处理：打了字没回车 ⇒ _update_params() 先提交
    # ------------------------------------------------------------------
    spin5 = d2.param_controls['blur_ksize']
    spin5.setValue(3)
    spin5.setFocus()
    spin5.lineEdit().selectAll()
    type_text(spin5, '99')                     # 打字后不按回车
    value_before_commit = spin5.value()
    d2._update_params()
    app.processEvents()
    check('⑤ 打字后（未提交）value 还是旧值', value_before_commit == 3, value_before_commit)
    check('⑤ _update_params() 会把没回车的输入提交并夹回 31',
          n2.params.get('blur_ksize') == 31 and spin5.value() == 31,
          (n2.params.get('blur_ksize'), spin5.value()))

    # ------------------------------------------------------------------
    # ⑥ 上/下箭头不许越界
    # ------------------------------------------------------------------
    spin6 = dlg.spin_canny_low
    spin6.setValue(500)
    spin6.stepBy(1)
    app.processEvents()
    check('⑥ 已在 500 时按上箭头 ⇒ 仍是 500（不许跑到 501）', spin6.value() == 500, spin6.value())
    spin6.setValue(0)
    spin6.stepBy(-1)
    app.processEvents()
    check('⑥ 已在 0 时按下箭头 ⇒ 仍是 0', spin6.value() == 0, spin6.value())

    # ------------------------------------------------------------------
    # ⑦ 老方案文件里带越界值 ⇒ 窗口加载那一刻就夹回来
    # ------------------------------------------------------------------
    n7 = w.add_flow_node('滤波', QPointF(10, 10))
    n7.params['blur_ksize'] = 99
    n7.params['blur_sigma'] = 999.0
    d7 = GPD.GenericProcessDialog(w.main_window, node=n7, main_window=w)
    check('⑦ 加载越界 blur_ksize=99 ⇒ 控件显示 31',
          d7.param_controls['blur_ksize'].value() == 31, d7.param_controls['blur_ksize'].value())
    check('⑦ 加载越界 blur_sigma=999 ⇒ 控件显示 20',
          abs(d7.param_controls['blur_sigma'].value() - 20.0) < 1e-6,
          d7.param_controls['blur_sigma'].value())

    # ------------------------------------------------------------------
    # ⑧ 回归：参数校验那一层还在（批次4 目标4 轮1/轮2 不能被这次改动弄坏）
    # ------------------------------------------------------------------
    n8 = w.add_flow_node('二值化', QPointF(10, 10))
    d8 = GPD.GenericProcessDialog(w.main_window, node=n8, main_window=w)
    d8._update_params()
    n8.params['thresh_value'] = 300
    d8._validate_params()
    check('⑧ 回归：越界 thresh_value=300 仍被校验层夹成 255 + 写回控件',
          n8.params['thresh_value'] == 255 and d8.param_controls['thresh_value'].value() == 255,
          (n8.params['thresh_value'], d8.param_controls['thresh_value'].value()))
    check('⑧ 回归：提示行还在工作', '已自动纠正' in d8.validate_hint.text(),
          d8.validate_hint.text()[:40])

    # ------------------------------------------------------------------
    # ⑨ 截图两张：打字中（超范围但没被打回）/ 提交后（已夹回上限）
    # ------------------------------------------------------------------
    SHOT_DIR = r"E:\opencv_python_3_8\backups\_ui_preview"
    dlg.ui.tabWidget.setCurrentIndex(1)
    dlg.show()
    app.processEvents()
    spin9 = dlg.spin_canny_low
    spin9.setValue(50)
    spin9.setFocus()
    spin9.lineEdit().selectAll()
    type_text(spin9, '999')
    app.processEvents()
    p1 = os.path.join(SHOT_DIR, 'p4_input_typed.png')
    dlg.grab().save(p1)
    print('      截图 ->', p1, os.path.exists(p1), '| 打字中的 text =', repr(spin9.lineEdit().text()))
    spin9.interpretText()
    app.processEvents()
    p2 = os.path.join(SHOT_DIR, 'p4_input_clamped.png')
    dlg.grab().save(p2)
    print('      截图 ->', p2, os.path.exists(p2), '| 提交后的 text =', repr(spin9.lineEdit().text()))

print('-' * 70)
if fails:
    print('MODE=%s  失败项：%d' % (MODE, len(fails)))
    for name in fails:
        print('   - ' + name)
else:
    print('MODE=%s  失败项：无' % MODE)
sys.exit(1 if fails else 0)
