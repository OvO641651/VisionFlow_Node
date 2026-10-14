# -*- coding: utf-8 -*-
"""
批次4 目标5-M2 验证①：人脸节点 + 通用错误通道（日志红字）

    python dsh_m2_face_check.py before    # 指向改前快照 ⇒ 复现"模块未实现、图像原样透传"
    python dsh_m2_face_check.py after     # 当前工程

判据要点：
    · 真样本（本机自带 `haarcascade_frontalface_default.xml` + `image/lena.png`）⇒ 检出 1 张，
      且**框与 OpenCV 直算的结果逐个一致**（不是写死坐标，换 OpenCV 版本也不假报）；
    · 检测类铁律：数据层图像**同一个对象**（连副本都不建）；
    · 结果格式与"ROI 继承"兼容：`result_bbox()` 能把它算成人脸框；
    · 空路径 / 文件不存在 / 坏 xml ⇒ 不崩、透传、**执行日志那一行是红字**（通用错误通道）；
    · 参数校验：scaleFactor ≤ 1 会夹到 1.01（实测 cv2 会抛异常）、邻居数 0 → 1、最小尺寸 0 → 5；
    · "浏览…"是**只选文件**（不弹选图片、不把文件导进图库）。
"""
import os
import sys
import tempfile
import shutil

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
BACKUP = r"E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_before_m2_face"

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

import cv2
import numpy as np
from PySide2.QtWidgets import QApplication, QPushButton
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ui.GenericProcessDialog as GPD
from core.NodeRegistry import get_spec, result_bbox

print('MODE = %s | NodeRegistry 来自 %s' % (MODE, os.path.dirname(m.__file__)))

CASCADE = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
LENA_PATH = os.path.join(PROJ, "image", "lena.png")
lena = cv2.imread(LENA_PATH)
assert lena is not None, LENA_PATH

browse_calls = []


class FakeMB(object):
    warning = information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


class FakeFD(object):
    """QFileDialog 替身：形状与真实 API 一致（返回 (路径, 过滤器)）"""
    getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
    getOpenFileName = staticmethod(lambda parent, caption, text, filters="":
                                   (browse_calls.append((caption, filters)) or CASCADE, filters))
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


def log_rows(w):
    """执行日志每行 = (模块, 结果数据文案, 结果数据那一列的前景色)"""
    out = []
    for r in range(w.execution_log.rowCount()):
        mod = w.execution_log.item(r, 2)
        res = w.execution_log.item(r, 4)
        if mod is None or res is None:
            continue
        out.append((mod.text(), res.text(), res.foreground().color().name()))
    return out


RED = "#c80000"          # main.py 里通用错误通道用的红色

TMP = tempfile.mkdtemp(prefix="vf_m2face_")
BAD_XML = os.path.join(TMP, "bad.xml")
with open(BAD_XML, "w", encoding="utf-8") as fh:
    fh.write("这不是一个级联分类器")
MISSING = os.path.join(TMP, "nope.xml")

w = m.MainWindow()
w.main_window.show()
w.current_static_image = lena.copy()

# ======================================================================
# ① 真样本：lena 里的人脸要被找出来
# ======================================================================
face_node = w.add_flow_node("人脸识别", QPointF(20, 20))
face_node.params["cascade_file"] = CASCADE
w.selected_node = face_node

spec = get_spec("人脸识别")
if MODE == 'before':
    check('① 改前：「人脸」还没实现（注册表里没有这个算子）', spec is None, spec)
    w.btn_step.click()
    rows = log_rows(w)
    hit = [r for r in rows if r[0] == "人脸识别"]
    check('① 改前：日志如实写「模块未实现，图像原样传给下游」',
          bool(hit) and "模块未实现" in hit[-1][1], hit)
else:
    check('① 改后：注册表里有人脸算子，且是**检测类**（图像不改、只出结果）',
          spec is not None and spec.kind == "detect" and spec.draw is not None,
          None if spec is None else (spec.kind, spec.draw is not None))
    check('① 改后：4 个参数都在（级联文件 / 缩放步长 / 最小邻居数 / 最小人脸尺寸）',
          [s[0] for s in spec.param_specs] ==
          ["cascade_file", "face_scale_factor", "face_min_neighbors", "face_min_size"],
          [s[0] for s in spec.param_specs])

    # OpenCV 直算一份"标准答案"，跟算子结果逐个比（不写死坐标）
    cascade = cv2.CascadeClassifier(CASCADE)
    faces = cascade.detectMultiScale(cv2.cvtColor(lena, cv2.COLOR_BGR2GRAY), 1.1, 5,
                                     minSize=(30, 30))
    expected = sorted([(int(x), int(y), int(x + fw), int(y + fh)) for x, y, fw, fh in faces])
    out_img, results = spec.run(None, lena, (0, 0, lena.shape[1], lena.shape[0]),
                                dict(face_node.params))
    check('① 改后：检出人脸数与 OpenCV 直算一致（lena 预期 1 张）',
          len(results) == len(expected) == 1, (len(results), len(expected), expected))
    check('① 改后：框与 OpenCV 直算逐个一致', sorted(results) == expected, (results, expected))
    check('① 改后：检测类铁律——数据层图像是**同一个对象**（连副本都不建）',
          out_img is lena, out_img is lena)
    check('① 改后：结果格式与「ROI 继承 → 继承上游结果框」兼容（result_bbox 能算成框）',
          result_bbox(results) == (expected[0][0], expected[0][1],
                                   expected[0][2] - expected[0][0],
                                   expected[0][3] - expected[0][1]),
          result_bbox(results))

    # 走真实 UI 入口：窗口里填好级联文件 → 点「执行」→ 日志里那一行要正常（不是红的）
    dlg = GPD.GenericProcessDialog(w.main_window, node=face_node, main_window=w)
    dlg.param_controls["cascade_file"].edit.setText(CASCADE)
    dlg.on_step_click()
    app.processEvents()
    rows = log_rows(w)
    hit = [r for r in rows if r[0] == "人脸识别"]
    check('① 改后：UI 入口（参数窗口点执行）也能跑出人脸', bool(hit), rows)
    check('① 改后：成功那一行不是红字（错误通道没有误伤正常结果）',
          bool(hit) and hit[-1][2] != RED, hit)
    check('① 改后：日志文案是「检测到1张人脸」', bool(hit) and hit[-1][1].startswith("检测到1张人脸"),
          hit)
    dlg.close()

# ======================================================================
# ② 空路径 / 文件不存在 / 坏 xml ⇒ 不崩 + 透传 + 红字
# ======================================================================
if MODE == 'after':
    for label, params, expect_text in (
            ("空路径", {}, "未选择级联文件"),
            ("文件不存在", {"cascade_file": MISSING}, "级联文件不存在"),
            ("坏 xml", {"cascade_file": BAD_XML}, "级联文件")):

        node = w.add_flow_node("人脸识别", QPointF(20, 20))
        node.params.update(params)
        w.selected_node = node
        w.current_static_image = lena.copy()
        before_rows = w.execution_log.rowCount()
        w.btn_step.click()
        app.processEvents()
        rows = log_rows(w)
        hit = [r for r in rows if r[0] == "人脸识别"]
        check('② %s：执行没崩、日志有这一行' % label, bool(hit), rows)
        check('② %s：文案写清了原因（含「%s」）' % (label, expect_text),
              bool(hit) and expect_text in hit[-1][1], hit)
        check('② %s：那一行是**红字**（通用错误通道）' % label,
              bool(hit) and hit[-1][2] == RED, hit)
        check('② %s：图像原样透传（当前图没被改动）' % label,
              w.current_static_image is not None and w.current_static_image.shape == lena.shape)

# ======================================================================
# ③ 参数校验（批次4 目标4 的规则表，人脸也有一份）
# ======================================================================
if MODE == 'after':
    fixed, notes, errors = spec.validate({"face_scale_factor": 1.0,
                                          "face_min_neighbors": 0,
                                          "face_min_size": 0})
    check('③ scaleFactor=1.0 ⇒ 夹到 1.01（实测 cv2 对 ≤1 直接抛异常）',
          fixed["face_scale_factor"] == 1.01 and any("缩放步长" in n for n in notes),
          (fixed.get("face_scale_factor"), notes))
    check('③ 最小邻居数=0 ⇒ 夹到 1（实测 0 会检出 80 个噪声）',
          fixed["face_min_neighbors"] == 1, fixed.get("face_min_neighbors"))
    check('③ 最小人脸尺寸=0 ⇒ 夹到 5', fixed["face_min_size"] == 5, fixed.get("face_min_size"))
    check('③ 合法参数：一条纠正说明都不加（不许无脑刷屏）',
          spec.validate({"face_scale_factor": 1.1, "face_min_neighbors": 5,
                         "face_min_size": 30})[1] == [],
          spec.validate({"face_scale_factor": 1.1, "face_min_neighbors": 5,
                         "face_min_size": 30})[1])
    check('③ 读不出数字（方案文件被手改坏）时用默认值 + 一条说明',
          spec.validate({"face_min_neighbors": "abc"})[0]["face_min_neighbors"] == 5
          and spec.validate({"face_min_neighbors": "abc"})[1] != [])

    # ==================================================================
    # ④ "浏览…"是**只选文件**：不弹"选图片"、不把文件导进图库
    # ==================================================================
    dlg = GPD.GenericProcessDialog(w.main_window, node=face_node, main_window=w)
    edit = dlg.param_controls["cascade_file"].edit
    edit.setText("")
    button = dlg.param_controls["cascade_file"].findChild(QPushButton)
    gallery_before = w.gallery_widget.count()
    browse_calls[:] = []
    button.click()
    app.processEvents()
    check('④ 点「浏览…」弹的是通用文件选择（标题 = 选择文件）',
          bool(browse_calls) and browse_calls[-1][0] == "选择文件", browse_calls)
    check('④ 选完只把路径填进输入框', edit.text() == CASCADE, edit.text())
    check('④ **没有**把选中的文件导进图库（file 控件的默认副作用被关掉了）',
          w.gallery_widget.count() == gallery_before,
          (gallery_before, w.gallery_widget.count()))
    dlg.close()

shutil.rmtree(TMP, ignore_errors=True)

print('-' * 70)
if fails:
    print('MODE=%s  失败项：%d' % (MODE, len(fails)))
    for name in fails:
        print('   - ' + name)
else:
    print('MODE=%s  失败项：无' % MODE)
sys.exit(1 if fails else 0)
