# -*- coding: utf-8 -*-
"""
批次4 目标4「参数校验」轮2 验证（2026.10.7）：窗口内联提示 + 三个入口接线

覆盖：
  A. .ui 里那张 validate_hint 真的加载到了；默认隐藏
  B. 纠正态：非法值 ⇒ node.params 被纠正 + **控件被写回**（用户看得见）+ 黄字提示写明改了什么
  C. 无问题态：提示行隐藏、文字为空
  D. 非法态（errors）：红字提示写明「执行时会被跳过」；通用窗口把"隐藏行"捞回来后也能显示
  E. 通用窗口（二值化）的写回：方案文件里塞 300 ⇒ 控件回到 255
  F. 三个入口（执行 / 连续执行 / 确定）**都**走校验
  G. 提示行不许把窗口顶宽（QLabel sizeHint 的坑，变更第 15 条）
  H. 三张截图（无问题 / 有纠正 / 有非法）落到 backups\\_ui_preview
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
from PySide2.QtWidgets import QApplication, QDialog, QLabel
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ui.LineParamsDialog as LPD
import ui.GenericProcessDialog as GPD
import core.NodeRegistry as NR


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

SHOT_DIR = r"E:\opencv_python_3_8\backups\_ui_preview"
if not os.path.isdir(SHOT_DIR):
    os.makedirs(SHOT_DIR)

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (('   <- ' + str(extra)) if extra else ''))
    if not cond:
        fails.append(name)


w = m.MainWindow()
w.main_window.show()
w.current_static_image = np.full((120, 160, 3), 60, np.uint8)


def line_dialog(**bad):
    node = w.add_flow_node('直线识别', QPointF(10, 10))
    dlg = LPD.LineParamsDialog(w.main_window, node=node, main_window=w)
    dlg.spin_roi_w.setValue(160)
    dlg.spin_roi_h.setValue(120)
    for key, value in bad.items():
        getattr(dlg, 'spin_' + key).setValue(value)
    # 真实流程是"点按钮 → 先 _update_params()（控件写进 node.params）→ 再 _validate_params()"
    dlg._update_params()
    return node, dlg


def grab(dlg, name):
    dlg.ui.tabWidget.setCurrentIndex(1)          # 切到"运行参数"页，提示行才可见
    dlg.show()
    app.processEvents()
    path = os.path.join(SHOT_DIR, name)
    dlg.grab().save(path)
    print('      截图 ->', path, os.path.exists(path))
    return path


# ----------------------------------------------------------------------
# A. .ui 里的提示行加载到了、默认隐藏
# ----------------------------------------------------------------------
node, dlg = line_dialog()
loaded = dlg.ui.findChild(QLabel, 'validate_hint')
check('A .ui 里的 validate_hint 真的加载到了（不是动态兜底建的）', loaded is not None)
check('A 同一张 label 被收编成 self.validate_hint', dlg.validate_hint is loaded)
check('A 默认隐藏（没校验过就没有提示）', not dlg.validate_hint.isVisibleTo(dlg))
check('A 提示行有 wordWrap + 限宽 300（防顶宽窗口）',
      dlg.validate_hint.wordWrap() and dlg.validate_hint.maximumWidth() == 300,
      (dlg.validate_hint.wordWrap(), dlg.validate_hint.maximumWidth()))

# ----------------------------------------------------------------------
# C. 无问题态：合法参数 ⇒ 隐藏 + 空文字
# ----------------------------------------------------------------------
node_c, dlg_c = line_dialog()
dlg_c._validate_params()
dlg_c.ui.tabWidget.setCurrentIndex(1)
check('C 合法参数：提示行隐藏', not dlg_c.validate_hint.isVisibleTo(dlg_c))
check('C 合法参数：提示行没有文字', dlg_c.validate_hint.text() == '',
      repr(dlg_c.validate_hint.text()))
check('C 合法参数：node.params 还是控件里那两个值（没人乱改）',
      (node_c.params['canny_low'], node_c.params['canny_high']) == (50, 150),
      (node_c.params.get('canny_low'), node_c.params.get('canny_high')))
grab(dlg_c, 'p4_rules_ok.png')

# ----------------------------------------------------------------------
# B. 纠正态：黄字 + 写回控件 + 不许顶宽窗口
# ----------------------------------------------------------------------
node_b, dlg_b = line_dialog(canny_low=150, canny_high=50)
width_before = dlg_b.sizeHint().width()
dlg_b._validate_params()
check('B 纠正写回 node.params（Canny 低/高互换）',
      (node_b.params['canny_low'], node_b.params['canny_high']) == (50, 150),
      (node_b.params.get('canny_low'), node_b.params.get('canny_high')))
check('B 纠正写回**控件**（用户看得见值被改了）',
      (dlg_b.spin_canny_low.value(), dlg_b.spin_canny_high.value()) == (50, 150),
      (dlg_b.spin_canny_low.value(), dlg_b.spin_canny_high.value()))
dlg_b.ui.tabWidget.setCurrentIndex(1)
check('B 提示行显示出来了', dlg_b.validate_hint.isVisibleTo(dlg_b))
check('B 提示行写明改了什么（含「已自动纠正」和「互换」）',
      '已自动纠正' in dlg_b.validate_hint.text() and '互换' in dlg_b.validate_hint.text(),
      dlg_b.validate_hint.text())
check('B 纠正态用黄字', '8a6d00' in dlg_b.validate_hint.styleSheet(),
      dlg_b.validate_hint.styleSheet())
width_after = dlg_b.sizeHint().width()
check('G 提示行没有把窗口顶宽（sizeHint 增量 ≤ 8px）', width_after - width_before <= 8,
      (width_before, width_after))
grab(dlg_b, 'p4_rules_fixed.png')

# ----------------------------------------------------------------------
# D. 非法态：红字 + 「会被跳过」；通用窗口把隐藏行捞回来后也能显示
# ----------------------------------------------------------------------
bad_spec = NR.NodeSpec('__bad_param_ui__', NR.KIND_PROCESS,
                       run=lambda detector, img, roi, params: (img, []),
                       format_result=lambda results: '不该走到这里',
                       param_specs=[],
                       validate=lambda params: (dict(params), [], ['测试用非法参数（必须 ≥ 1）']))
NR.NODE_SPECS['__bad_param_ui__'] = bad_spec
nb = w.add_flow_node('__bad_param_ui__', QPointF(10, 10))
dlg_d = GPD.GenericProcessDialog(w.main_window, node=nb, main_window=w)
dlg_d._update_params()
errors = dlg_d._validate_params()
dlg_d.ui.tabWidget.setCurrentIndex(1)
check('D 非法态：_validate_params 返回了 errors', errors == ['测试用非法参数（必须 ≥ 1）'], errors)
check('D 非法态：提示行显示出来了（GenericProcessDialog 藏过它，又被捞回来）',
      dlg_d.validate_hint.isVisibleTo(dlg_d))
check('D 非法态：写明「执行时会被跳过」', '被跳过' in dlg_d.validate_hint.text(),
      dlg_d.validate_hint.text())
check('D 非法态：用红字', 'b00020' in dlg_d.validate_hint.styleSheet(),
      dlg_d.validate_hint.styleSheet())
grab(dlg_d, 'p4_rules_error.png')

# ----------------------------------------------------------------------
# E. 通用窗口的写回：方案文件里塞 thresh_value=300 ⇒ 控件回到 255
# ----------------------------------------------------------------------
n_e = w.add_flow_node('二值化', QPointF(10, 10))
dlg_e = GPD.GenericProcessDialog(w.main_window, node=n_e, main_window=w)
dlg_e._update_params()                 # 先按真实流程同步一次控件 → params
n_e.params['thresh_value'] = 300       # 再模拟"方案文件里塞了越界值"
n_e.params['thresh_maxval'] = 999
dlg_e._validate_params()
check('E 通用窗口写回：方案文件里的 300/999 ⇒ 控件显示 255/255',
      (dlg_e.param_controls['thresh_value'].value(),
       dlg_e.param_controls['thresh_maxval'].value()) == (255, 255),
      (dlg_e.param_controls['thresh_value'].value(),
       dlg_e.param_controls['thresh_maxval'].value()))
check('E 通用窗口写回：node.params 也被纠正成 255/255',
      (n_e.params['thresh_value'], n_e.params['thresh_maxval']) == (255, 255),
      (n_e.params['thresh_value'], n_e.params['thresh_maxval']))
check('E 通用窗口：提示行文案含「已自动纠正」', '已自动纠正' in dlg_e.validate_hint.text(),
      dlg_e.validate_hint.text())

# ----------------------------------------------------------------------
# F. 三个入口都走校验
# ----------------------------------------------------------------------
node_f1, dlg_f1 = line_dialog(canny_low=200, canny_high=10)
dlg_f1.on_step_click()
check('F 「执行」入口：node.params 被纠正成 10/200',
      (node_f1.params['canny_low'], node_f1.params['canny_high']) == (10, 200),
      (node_f1.params.get('canny_low'), node_f1.params.get('canny_high')))
check('F 「执行」入口：提示行显示出来了', dlg_f1.validate_hint.text().startswith('已自动纠正'),
      dlg_f1.validate_hint.text()[:40])

node_f2, dlg_f2 = line_dialog(canny_low=200, canny_high=10)
dlg_f2.on_cont_click()
check('F 「连续执行」入口：node.params 被纠正成 10/200',
      (node_f2.params['canny_low'], node_f2.params['canny_high']) == (10, 200),
      (node_f2.params.get('canny_low'), node_f2.params.get('canny_high')))

node_f3, dlg_f3 = line_dialog(canny_low=200, canny_high=10)
dlg_f3.on_ok()
check('F 「确定」入口：node.params 被纠正成 10/200',
      (node_f3.params['canny_low'], node_f3.params['canny_high']) == (10, 200),
      (node_f3.params.get('canny_low'), node_f3.params.get('canny_high')))
check('F 「确定」入口：窗口正常关闭（Accepted）', dlg_f3.result() == QDialog.Accepted,
      dlg_f3.result())

# 圆窗口也没落队（它走的是自己的控件 + 同一个父类入口）
from ui.CircleParamsDialog import CircleParamsDialog
n_g = w.add_flow_node('圆识别', QPointF(10, 10))
dlg_g = CircleParamsDialog(w.main_window, node=n_g, main_window=w)
dlg_g.spin_param2.setValue(dlg_g.spin_param2.maximum())      # 合法值，确认不误报
dlg_g.spin_roi_w.setValue(160)
dlg_g.spin_roi_h.setValue(120)
dlg_g._update_params()
dlg_g._validate_params()
check('F 圆窗口：合法 param2 不产生提示', dlg_g.validate_hint.text() == '',
      repr(dlg_g.validate_hint.text()))
n_g.params['param1'] = 0
dlg_g._validate_params()
check('F 圆窗口：param1=0（方案文件塞的）⇒ 纠正为 1 + 提示',
      n_g.params['param1'] == 1 and '已自动纠正' in dlg_g.validate_hint.text(),
      (n_g.params.get('param1'), dlg_g.validate_hint.text()[:50]))

del NR.NODE_SPECS['__bad_param_ui__']

print('-' * 70)
if fails:
    print('失败项：%d' % len(fails))
    for name in fails:
        print('   - ' + name)
else:
    print('失败项：无')
sys.exit(1 if fails else 0)
