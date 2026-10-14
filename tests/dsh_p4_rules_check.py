# -*- coding: utf-8 -*-
"""
批次4 目标4「参数校验」轮1 验证（2026.10.7）

同一个脚本跑两遍：
    python dsh_p4_rules_check.py before   # sys.path 指向改前的备份目录 ⇒ 量「改前」的行为
    python dsh_p4_rules_check.py after    # 跑当前工程 ⇒ 验证修复

轮1 覆盖：
  A. 【改前的病】圆 param2=0（模拟老方案文件里手改的值）执行时抛异常、执行日志一行都不刷新
     —— 改前必须复现出来，改后必须「不抛 + 纠正 + 日志看得见」
  B. 引擎层：能纠正的就地纠正 + node.params 真的被改 + 日志尾追「← 已自动纠正：…」
  C. 规则表逐条（直线 / 圆 / 二值化 / 滤波 / 形态学 / 边缘）：非法 → 纠正值 + 说明文案
  D. errors 通道：纠不了的 ⇒ 跳过该节点（图像原样透传 + __note__ 文案），不弹窗、不抛异常
  E. 回归：ROI 尺寸 0 那条日志不变；没有规则的算子（图片源）直接放行
  F. 圆窗口 param1 / param2 下限 = 1（改前是 0，界面就能调到会崩的值）

注意：本文件里中文字符串一律用单引号或「」，**不嵌 ASCII 双引号**（踩过 SyntaxError）。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
BACKUP = r"E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_before_param_validate"

MODE = (sys.argv[1] if len(sys.argv) > 1 else "after").lower()
assert MODE in ("before", "after"), MODE

if MODE == 'before':
    print('NOTE: 批次5 目标1 目录重构后，本套用例的 before 模式不再可用'
          '（备份快照是旧的扁平布局、与新的包路径不兼容）；本套现在只跑 after 模式。')
    sys.exit(0)

os.chdir(PROJ)
sys.path.insert(0, PROJ)
if MODE == "before":
    sys.path.insert(0, BACKUP)          # 备份目录里的 6 个文件优先命中

import numpy as np
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import core.NodeRegistry as NR

print('MODE = %s | main.py 来自 %s' % (MODE, os.path.dirname(m.__file__)))


class FakeMB(object):
    warning = information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (('   <- ' + str(extra)) if extra else ''))
    if not cond:
        fails.append(name)


def make_img(value=40):
    return np.full((48, 64, 3), value, np.uint8)


w = m.MainWindow()
w.main_window.show()
w.current_static_image = make_img()

log_rows = []
real_update = w._update_execution_log


def spy_update(exec_info):
    log_rows.append(list(exec_info))
    return real_update(exec_info)


w._update_execution_log = spy_update


def circle_node(**params):
    node = w.add_flow_node('圆识别', QPointF(10, 10))
    node.params.update({'param1': 100, 'param2': 80, 'dp': 1.0, 'min_dist': 150,
                        'min_radius': 20, 'roi_inherit': False,
                        'roi_x': 0, 'roi_y': 0, 'roi_w': 64, 'roi_h': 48})
    node.params.update(params)
    return node


def run_node(node):
    del log_rows[:]
    raised = None
    try:
        w.run_flow_step(node)
    except Exception as exc:                      # 就是要抓「抛了什么」
        raised = exc
    return raised


def last_texts():
    return [row[4] for row in (log_rows[-1] if log_rows else [])]


# ----------------------------------------------------------------------
# A. 改前复现 / 改后修复：圆 param2 = 0
# ----------------------------------------------------------------------
node = circle_node(param2=0)
raised = run_node(node)
if MODE == 'before':
    check('A 改前复现：param2=0 执行时抛异常（cv2 报错）',
          raised is not None and 'error' in type(raised).__name__.lower(),
          '%s: %s' % (type(raised).__name__ if raised else None, str(raised)[:70]))
    check('A 改前复现：异常打断执行 ⇒ 执行日志一行都没刷新（用户看到的是「点了没反应」）',
          len(log_rows) == 0, log_rows)
    check('A 改前复现：param2 保持 0（没人纠正它）', node.params.get('param2') == 0,
          node.params.get('param2'))
else:
    check('A 修复后：param2=0 执行不再抛异常', raised is None, repr(raised))
    check('A 修复后：param2 被纠正成 1（写回 node.params）', node.params.get('param2') == 1,
          node.params.get('param2'))
    check('A 修复后：执行日志刷新了', len(log_rows) >= 1, len(log_rows))
    texts = last_texts()
    check('A 修复后：日志的「结果数据」列写明「已自动纠正…param2…」',
          any('已自动纠正' in t and 'param2' in t for t in texts), texts)

# ----------------------------------------------------------------------
# B. 引擎层：直线 Canny 高低互换（改了值 + 日志有说明）
# ----------------------------------------------------------------------
if MODE == 'after':
    line = w.add_flow_node('直线识别', QPointF(10, 10))
    line.params.update({'canny_low': 150, 'canny_high': 50, 'hough_threshold': 100,
                        'min_line_length': 100, 'max_line_gap': 10,
                        'roi_inherit': False, 'roi_x': 0, 'roi_y': 0, 'roi_w': 64, 'roi_h': 48})
    raised = run_node(line)
    check('B 直线 150/50 执行不抛异常', raised is None, repr(raised))
    check('B node.params 被就地纠正成 50/150',
          (line.params.get('canny_low'), line.params.get('canny_high')) == (50, 150),
          (line.params.get('canny_low'), line.params.get('canny_high')))
    texts = last_texts()
    check('B 日志里能看到「已自动纠正：Canny 低/高阈值已互换」',
          any('已自动纠正' in t and '互换' in t for t in texts), texts)

    # ------------------------------------------------------------------
    # C. 规则表逐条（直接调 run_validation，不经过界面）
    # ------------------------------------------------------------------
    from core.ParamRules import run_validation

    def fixed_of(name, params):
        return run_validation(m.get_spec(name), params)

    fixed, notes, errors = fixed_of('直线识别', {'canny_low': 150, 'canny_high': 50,
                                            'hough_threshold': 0, 'min_line_length': 0,
                                            'max_line_gap': -1})
    check('C 直线：低/高互换 + 阈值 0→1 + 最小长度 0→1 + 间隙 -1→0，一次纠正四条',
          (fixed['canny_low'], fixed['canny_high'], fixed['hough_threshold'],
           fixed['min_line_length'], fixed['max_line_gap']) == (50, 150, 1, 1, 0), fixed)
    check('C 直线：四条纠正都有说明', len(notes) == 4, notes)
    check('C 直线：errors 为空（都能安全纠正）', errors == [], errors)

    fixed, notes, errors = fixed_of('直线识别', {'canny_low': 50, 'canny_high': 150,
                                            'hough_threshold': 100, 'min_line_length': 100,
                                            'max_line_gap': 10})
    check('C 直线：合法参数原样返回、零说明（不无脑加 noise）',
          (fixed['canny_low'], fixed['canny_high'], notes) == (50, 150, []), (fixed, notes))

    fixed, notes, errors = fixed_of('圆识别', {'param1': 0, 'param2': 0, 'dp': 0, 'min_dist': 0})
    check('C 圆：param1/param2 0→1、dp 0→0.1、min_dist 0→1',
          (fixed['param1'], fixed['param2'], fixed['dp'], fixed['min_dist']) == (1, 1, 0.1, 1),
          fixed)

    fixed, notes, errors = fixed_of('二值化', {'thresh_value': 300, 'thresh_maxval': 999})
    check('C 二值化：阈值 300→255、最大值 999→255（越界时 OpenCV 不报错，只是静默饱和）',
          (fixed['thresh_value'], fixed['thresh_maxval']) == (255, 255), fixed)

    fixed, notes, errors = fixed_of('滤波', {'blur_ksize': 4, 'blur_sigma': 99})
    check('C 滤波：核大小 4→5（奇数）、标准差 99→20',
          (fixed['blur_ksize'], fixed['blur_sigma']) == (5, 20.0), fixed)
    fixed, notes, errors = fixed_of('形态学', {'morph_ksize': 0, 'morph_iterations': 99})
    check('C 形态学：核大小 0→1、迭代 99→10',
          (fixed['morph_ksize'], fixed['morph_iterations']) == (1, 10), fixed)
    fixed, notes, errors = fixed_of('边缘提取', {'edge_ksize': 4})
    check('C 边缘提取：核大小 4→5', fixed['edge_ksize'] == 5, fixed)

    fixed, notes, errors = fixed_of('滤波', {'blur_ksize': 'abc', 'blur_sigma': None})
    check('C 方案文件被手改成非数字 ⇒ 用默认值 + 说明、不抛异常',
          fixed['blur_ksize'] == 3 and fixed['blur_sigma'] == 0.0 and len(notes) >= 1,
          (fixed, notes))

    # ★ 不许给「没有参数的节点」灌默认值（2026.10.7：这一条害我弄坏了 dsh_m3_switch）
    #   根因——灌了默认值 ⇒ node.params 凭空多出键 ⇒ M3 的「视频参数整段共用」把它误判成
    #   「参数变了」⇒ 每轮多写一行「已载回这段视频上一次的参数」提示。
    fixed, notes, errors = fixed_of('二值化', {})
    check('C 空参数节点：fixed 为空、零说明（默认值是算子自己的事，不许灌进 node.params）',
          fixed == {} and notes == [], (fixed, notes))
    fixed, notes, errors = fixed_of('直线识别', {'canny_low': 50})
    check('C 只给了部分参数：只写回给了的那个键（不补 canny_high 等）',
          list(fixed.keys()) == ['canny_low'] and fixed['canny_low'] == 50, fixed)

    fixed, notes, errors = run_validation(m.get_spec('图片源'), {'source_path': 'x'})
    check('C 没有规则的算子（图片源）直接放行：参数原样、零说明',
          fixed == {'source_path': 'x'} and notes == [] and errors == [], (fixed, notes))

    class BoomSpec(object):
        validate = staticmethod(lambda p: 1 / 0)

    fixed, notes, errors = run_validation(BoomSpec(), {'a': 1})
    check('C 规则自己抛异常 ⇒ 变成一条 errors（引擎会跳过节点），不把异常放出去',
          fixed == {'a': 1} and len(errors) == 1 and '异常' in errors[0], (fixed, errors))

    # ------------------------------------------------------------------
    # D. errors 通道：真的走 _execute_node ⇒ 跳过 + __note__ 文案
    # ------------------------------------------------------------------
    bad = NR.NodeSpec('__bad_param__', NR.KIND_PROCESS,
                      run=lambda detector, img, roi, params: (img, []),
                      format_result=lambda results: '不该走到这里',
                      param_specs=[],
                      validate=lambda params: (dict(params), [], ['测试用的非法参数（必须 ≥ 1）']))
    NR.NODE_SPECS['__bad_param__'] = bad
    bad_node = w.add_flow_node('__bad_param__', QPointF(10, 10))
    bad_node.params.update({'roi_inherit': False, 'roi_x': 0, 'roi_y': 0, 'roi_w': 64, 'roi_h': 48})
    img = make_img(55)
    out_img, results, roi_info, spec = w._execute_node(bad_node, img, None)
    check('D 参数非法 ⇒ 图像原样透传（同一个对象，下游不受影响）', out_img is img)
    check('D 参数非法 ⇒ results 里带 __note__（引擎约定的「结果里放 dict 带文案」）',
          isinstance(results, list) and results and isinstance(results[0], dict)
          and '__note__' in results[0], results)
    text = w._format_result_text(bad_node, results, roi_info, spec)
    check('D 参数非法 ⇒ 日志文案是「参数非法（…），已跳过本节点」（不去问 format_result）',
          '参数非法' in text and '已跳过本节点' in text and '不该走到这里' not in text, text)

    raised = run_node(bad_node)
    check('D 走真实入口（run_flow_step）也不抛异常', raised is None, repr(raised))
    texts = last_texts()
    check('D 日志里出现「参数非法」那一行', any('参数非法' in t for t in texts), texts)

    # ------------------------------------------------------------------
    # E. 回归：ROI 尺寸 0 那条日志不变
    # ------------------------------------------------------------------
    zero = w.add_flow_node('取反', QPointF(10, 10))
    zero.params.update({'roi_inherit': False, 'roi_x': 0, 'roi_y': 0, 'roi_w': 0, 'roi_h': 0})
    raised = run_node(zero)
    texts = last_texts()
    check('E 回归：ROI 尺寸 0 ⇒ 仍是「ROI 尺寸为 0，已跳过（图像原样传给下游）」',
          raised is None and any('ROI 尺寸为 0' in t for t in texts), (repr(raised), texts))

# ----------------------------------------------------------------------
# F. 圆窗口下限（改前 = 0，界面可达会崩；改后 = 1）
# ----------------------------------------------------------------------
from ui.CircleParamsDialog import CircleParamsDialog

node_f = circle_node(param2=80)
dlg = CircleParamsDialog(w.main_window, node=node_f, main_window=w)
if MODE == 'before':
    check('F 改前：圆窗口 param1 / param2 下限 = 0（界面就能调到会崩的值）',
          dlg.spin_param1.minimum() == 0 and dlg.spin_param2.minimum() == 0,
          (dlg.spin_param1.minimum(), dlg.spin_param2.minimum()))
else:
    # 注意（2026.10.7 晚）：控件自身的范围后来被"软范围"（越界先打进去、提交才夹回）放宽了，
    # 所以"界面调不到 0"这件事现在看 **_soft_min**（真范围），不再看 widget.minimum()。
    soft = (dlg.spin_param1.property('_soft_min'), dlg.spin_param1.property('_soft_max'),
            dlg.spin_param2.property('_soft_min'), dlg.spin_param2.property('_soft_max'))
    check('F 改后：圆窗口 param1 / param2 的**逻辑范围** = 1~1000（界面再也调不到 0）',
          soft == (1, 1000, 1, 1000), soft)

print('-' * 70)
if fails:
    print('MODE=%s  失败项：%d' % (MODE, len(fails)))
    for name in fails:
        print('   - ' + name)
else:
    print('MODE=%s  失败项：无' % MODE)
sys.exit(1 if fails else 0)
