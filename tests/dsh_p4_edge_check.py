# -*- coding: utf-8 -*-
"""
边缘提取「低/高阈值」追加规则验证（2026.10.7 晚，用户选 A）

用户实测报："把低阈值设置为 500、高阈值设置为 150，能正常运行，效果和 150/500 一样，
            没有看到黄字提醒和红字提醒"（他截图里"方法"选的是 Sobel）。

同一个脚本跑两遍：
    python dsh_p4_edge_check.py before   # 指向改前的备份目录 ⇒ 复现"没有提示"
    python dsh_p4_edge_check.py after    # 当前工程
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
BACKUP = r"E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_before_edge_rule"

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
import ui.GenericProcessDialog as GPD

print('MODE = %s | ProcessOps 来自 %s' % (MODE, os.path.dirname(m.__file__)))


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
GPD.QMessageBox = FakeMB
m.QFileDialog = FakeFD
GPD.QFileDialog = FakeFD

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (('   <- ' + str(extra)) if extra else ''))
    if not cond:
        fails.append(name)


w = m.MainWindow()
w.main_window.show()
w.current_static_image = np.full((120, 160, 3), 60, np.uint8)


def open_edge_dialog(method, low, high):
    node = w.add_flow_node('边缘提取', QPointF(10, 10))
    dlg = GPD.GenericProcessDialog(w.main_window, node=node, main_window=w)
    dlg.param_controls['edge_method'].setCurrentText(method)
    dlg.param_controls['edge_low'].setValue(low)
    dlg.param_controls['edge_high'].setValue(high)
    dlg.param_controls['edge_ksize'].setValue(3)
    dlg.spin_roi_w.setValue(160)
    dlg.spin_roi_h.setValue(120)
    return node, dlg


# ----------------------------------------------------------------------
# ① 规则层：直接调 run_validation
# ----------------------------------------------------------------------
from core.ParamRules import run_validation

spec = m.get_spec('边缘提取')
fixed, notes, errors = run_validation(spec, {'edge_low': 500, 'edge_high': 150, 'edge_ksize': 3})
if MODE == 'before':
    check('① 改前：500/150 **没有任何规则管它**（notes 为空 ⇒ 界面不会有提示）',
          notes == [] and fixed.get('edge_low') == 500, (notes, fixed.get('edge_low')))
else:
    check('① 500/150 ⇒ 被互换为 150/500 并给出说明',
          (fixed['edge_low'], fixed['edge_high']) == (150, 500) and len(notes) == 1,
          (fixed['edge_low'], fixed['edge_high'], notes))
    check('① 说明文案写明"改前 → 改后"',
          '互换' in notes[0] and '500/150' in notes[0] and '150/500' in notes[0], notes)
    check('① errors 为空（能安全纠正）', errors == [], errors)

    fixed2, notes2, errors2 = run_validation(spec, {'edge_low': -5, 'edge_high': 600})
    check('② 越界 -5 / 600 ⇒ 夹到 0 / 500 并各给一条说明',
          (fixed2['edge_low'], fixed2['edge_high']) == (0, 500) and len(notes2) == 2,
          (fixed2['edge_low'], fixed2['edge_high'], notes2))

    fixed3, notes3, errors3 = run_validation(spec, {'edge_low': 50, 'edge_high': 150})
    check('③ 合法值 50/150 ⇒ 原样返回、零说明（不无脑加 noise）',
          (fixed3['edge_low'], fixed3['edge_high'], notes3) == (50, 150, []), (fixed3, notes3))

    fixed4, notes4, errors4 = run_validation(spec, {'edge_ksize': 4})
    check('④ 回归：核大小 4 ⇒ 5（奇数规则还在）', fixed4['edge_ksize'] == 5, fixed4)

# ----------------------------------------------------------------------
# ⑤ 窗口层（用户能看见的那一层）：Sobel + 500/150 —— 用户截图里的原场景
# ----------------------------------------------------------------------
node, dlg = open_edge_dialog('Sobel', 500, 150)
dlg._update_params()
dlg._validate_params()
dlg.ui.tabWidget.setCurrentIndex(1)
hint = dlg.validate_hint
if MODE == 'before':
    check('⑤ 改前：提示行**不显示**、文字为空（复现用户报的"没有提示"）',
          (not hint.isVisibleTo(dlg)) and hint.text() == '',
          (hint.isVisibleTo(dlg), hint.text()))
    check('⑤ 改前：控件里仍是用户填的 500 / 150（没人纠正）',
          (dlg.param_controls['edge_low'].value(), dlg.param_controls['edge_high'].value()) == (500, 150),
          (dlg.param_controls['edge_low'].value(), dlg.param_controls['edge_high'].value()))
else:
    check('⑤ 改后：提示行**显示出来了**（Sobel 场景也会提示 —— 用户就是在这个场景下报的）',
          hint.isVisibleTo(dlg), (hint.isVisibleTo(dlg), hint.text()))
    check('⑤ 改后：提示是黄字 + 写明"已自动纠正…互换"',
          '8a6d00' in hint.styleSheet() and '已自动纠正' in hint.text() and '互换' in hint.text(),
          (hint.styleSheet(), hint.text()))
    check('⑤ 改后：**控件被写回**成 150 / 500（用户看得见值被改了）',
          (dlg.param_controls['edge_low'].value(), dlg.param_controls['edge_high'].value()) == (150, 500),
          (dlg.param_controls['edge_low'].value(), dlg.param_controls['edge_high'].value()))
    check('⑤ 改后：node.params 也被纠正为 150 / 500',
          (node.params['edge_low'], node.params['edge_high']) == (150, 500),
          (node.params.get('edge_low'), node.params.get('edge_high')))

    SHOT_DIR = r'E:\opencv_python_3_8\backups\_ui_preview'
    dlg.show()
    app.processEvents()
    shot = os.path.join(SHOT_DIR, 'p4_edge_fixed.png')
    dlg.grab().save(shot)
    print('      截图 ->', shot, os.path.exists(shot))

# ----------------------------------------------------------------------
# ⑥ 引擎层：Canny + 500/150 真跑一遍 ⇒ 不崩 + 日志写明纠正
# ----------------------------------------------------------------------
node2, dlg2 = open_edge_dialog('Canny', 500, 150)
dlg2._update_params()     # 真实流程：窗口里设完值 → 参数进 node.params（**不**先走窗口层校验）
log_rows = []
real_update = w._update_execution_log


def spy(exec_info):
    log_rows.append(list(exec_info))
    return real_update(exec_info)


w._update_execution_log = spy
raised = None
try:
    w.run_flow_step(node2)
except Exception as exc:
    raised = exc
w._update_execution_log = real_update
if MODE == 'before':
    check('⑥ 改前：Canny + 500/150 也能正常跑（OpenCV 内部自己交换，所以不报错）',
          raised is None, repr(raised))
else:
    texts = [row[4] for row in (log_rows[-1] if log_rows else [])]
    check('⑥ 改后：Canny + 500/150 不抛异常', raised is None, repr(raised))
    check('⑥ 改后：node.params 被引擎层纠正成 150 / 500',
          (node2.params['edge_low'], node2.params['edge_high']) == (150, 500),
          (node2.params.get('edge_low'), node2.params.get('edge_high')))
    check('⑥ 改后：执行日志里写明"← 已自动纠正：…互换"',
          any('已自动纠正' in t and '互换' in t for t in texts), texts)

print('-' * 70)
if fails:
    print('MODE=%s  失败项：%d' % (MODE, len(fails)))
    for name in fails:
        print('   - ' + name)
else:
    print('MODE=%s  失败项：无' % MODE)
sys.exit(1 if fails else 0)
