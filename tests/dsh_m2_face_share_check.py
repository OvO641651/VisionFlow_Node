# -*- coding: utf-8 -*-
"""
批次4 目标5-M2 验证④：**节点级参数**（人脸级联文件跨图共用，其它参数照旧每图独立）

    python dsh_m2_face_share_check.py before   # 指向 M2 落地时的快照（用户报 bug 的那版）⇒ 复现"换图后级联文件被清掉"
    python dsh_m2_face_share_check.py after    # 当前工程

用户报的原话（2026.10.12）："更换图片后级联文件需要重新导入，可能是每幅图片的参数设置会重置导致，
更换后级联文件也重置，我希望这个人脸识别节点的级联文件每幅图都可以使用，不会更换图片后就重置。
但是其他的节点的参数需要保持原样，每幅图片独立参数。"

判据：
    · 换图 ⇒ 人脸的 `cascade_file` **不重置**（节点级参数，声明 `per_node: True`）；
    · 换图 ⇒ 人脸的 `face_scale_factor` 与直线的 `canny_low` **照旧每图独立**（回到默认 / 拿回各自那一份）；
    · 图片槽里**不含**级联文件（不在每张图下面重复存一份）；
    · 参数窗口里看到的也是共享后的值（UI 路径，不是只改引擎）；
    · 方案文件里级联文件存得住、读得回来。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
BEFORE = r"E:\opencv_python_3_8\backups\_backup_VisionFlowNoed_at_20261012_2214"

MODE = (sys.argv[1] if len(sys.argv) > 1 else "after").lower()
assert MODE in ("before", "after"), MODE

if MODE == 'before':
    print('NOTE: 批次5 目标1 目录重构后，本套用例的 before 模式不再可用'
          '（备份快照是旧的扁平布局、与新的包路径不兼容）；本套现在只跑 after 模式。')
    sys.exit(0)

os.chdir(PROJ)
sys.path.insert(0, PROJ)
if MODE == "before":
    sys.path.insert(0, BEFORE)

import cv2
import numpy as np
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ui.GenericProcessDialog as GPD

print('MODE = %s | main.py 来自 %s' % (MODE, os.path.dirname(m.__file__)))

CASCADE_A = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
CASCADE_B = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_alt.xml")
assert os.path.exists(CASCADE_A) and os.path.exists(CASCADE_B)
LENA = cv2.imread(os.path.join(PROJ, "image", "lena.png"))


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


def check(name, cond, extra=None):
    text = '' if extra is None else '   <- ' + str(extra)
    print(('PASS  ' if cond else 'FAIL  ') + name + text)
    if not cond:
        fails.append(name)


# 两张明显不同的图（尺寸与均值都不一样，方便肉眼/断言区分）
IMG_A = np.full((60, 80, 3), 40, np.uint8)
IMG_B = np.full((90, 70, 3), 210, np.uint8)

w = m.MainWindow()
w.main_window.show()

face = w.add_flow_node("人脸识别", QPointF(20, 20))
line = w.add_flow_node("直线识别", QPointF(320, 20))

# ---- 在图 A 上：设置级联文件（节点级）+ 一个调参参数（每图独立）+ 直线的一个参数 ----
w._show_static_image(IMG_A)
key_a = w.current_image_key
face.params["cascade_file"] = CASCADE_A
face.params["face_scale_factor"] = 1.5
line.params["canny_low"] = 200

# ---- 换到图 B（这一步会先存 A 那一份、再按 B 载入）----
w._show_static_image(IMG_B)
key_b = w.current_image_key

check('① 两张图确实是两个不同的图片标识（前置断言，否则后面测不到东西）',
      key_a is not None and key_b is not None and key_a != key_b, (key_a, key_b))

if MODE == 'before':
    check('① 改前：换图后**级联文件被清掉了**（用户报的 bug 复现）',
          face.params.get("cascade_file") in (None, ""), face.params.get("cascade_file"))
else:
    check('① 改后：换图后**级联文件还在**（节点级参数，跨图共用）',
          face.params.get("cascade_file") == CASCADE_A, face.params.get("cascade_file"))

check('① 换图后：人脸自己的调参参数照旧**每图独立**（回到默认，不在 params 里）',
      face.params.get("face_scale_factor") is None, face.params.get("face_scale_factor"))
check('① 换图后：**其它节点**（直线）的参数照旧每图独立',
      line.params.get("canny_low") is None, line.params.get("canny_low"))

store = getattr(face, "params_per_image", None) or {}
if MODE == 'after':
    check('① 图片槽里**不含**级联文件（不在每张图下面重复存一份）',
          all("cascade_file" not in snap for snap in store.values()),
          {k: sorted(v.keys())[:4] for k, v in store.items()})
check('① A 那份参数存对了（调参参数在里面）',
      (store.get(key_a) or {}).get("face_scale_factor") == 1.5,
      store.get(key_a))
if MODE == 'before':
    check('① 改前：图片槽里**连级联文件也一起存了**（所以每张图各有一份、换图就换成别份 / 空的）',
          (store.get(key_a) or {}).get("cascade_file") == CASCADE_A, store.get(key_a))

# ---- 在图 B 上改成另一个级联文件 + 另一个缩放步长 ----
face.params["cascade_file"] = CASCADE_B
face.params["face_scale_factor"] = 1.3

# ---- 切回图 A：级联文件跟着节点走（最后一个值），调参参数拿回 A 那一份 ----
w._show_static_image(IMG_A)
if MODE == 'before':
    check('② 改前：在图 B 上选的级联文件**白设了** —— 切回图 A 看到的是 A 那份旧值（每张图各记一份）',
          face.params.get("cascade_file") == CASCADE_A, face.params.get("cascade_file"))
else:
    check('② 改后：切回图 A 后级联文件 = 最后设的那个（跟着节点走，不跟着图走）',
          face.params.get("cascade_file") == CASCADE_B, face.params.get("cascade_file"))
check('② 切回图 A：人脸的调参参数拿回了 A 那一份（1.5）',
      face.params.get("face_scale_factor") == 1.5, face.params.get("face_scale_factor"))
check('② 切回图 A：直线的参数也拿回了 A 那一份（200）',
      line.params.get("canny_low") == 200, line.params.get("canny_low"))

# ---- UI 路径：参数窗口里看到的就是共享后的值（用户不用重新导入）----
dlg = GPD.GenericProcessDialog(w.main_window, node=face, main_window=w)
shown = dlg.param_controls["cascade_file"].edit.text()
if MODE == 'before':
    check('③ 改前：参数窗口里显示的是图 A 的旧值（用户看到"我选的没了 / 又要重新导入"）',
          shown == CASCADE_A, shown)
else:
    check('③ 参数窗口里显示的级联文件 = 共享后的那个（用户不用重新选）',
          shown == CASCADE_B, shown)
dlg.close()

# ---- 方案持久化：存得住、读得回来 ----
data = w._collect_project()
face_model = [n for n in data["pages"][0]["nodes"] if n["name"] == "人脸识别"][0]
expect = CASCADE_A if MODE == 'before' else CASCADE_B
check('④ 方案里节点的 params 带着级联文件（"带的是哪一份"就是改前/改后的分水岭）',
      face_model["params"].get("cascade_file") == expect,
      face_model["params"].get("cascade_file"))
check('④ 方案里的 params_by_image **不含**级联文件（不在每张图下面重复）',
      all("cascade_file" not in snap for snap in (face_model.get("params_by_image") or {}).values()),
      face_model.get("params_by_image"))

w2 = m.MainWindow()
w2.main_window.show()
model, _warnings = w2._build_project_model(data["pages"])
w2._apply_project(model, data)
face2 = [n for n in w2.flow_nodes if n.name == "人脸识别"][0]
check('④ 重新加载方案后：级联文件读得回来（是最后设的那一份）',
      face2.params.get("cascade_file") == expect, face2.params.get("cascade_file"))

# ---- 引擎路径：共享的级联文件真的被用上了 ----
# 注意：这里 **不写死"检出几张"** —— 当前 scaleFactor 是图 A 那份（1.5），
# 配 alt 级联在 lena 上会检出 0 张（实测），那是"参数真的生效"的正常结果，不是共享失效。
w.current_static_image = LENA.copy()
w.selected_node = face
w.btn_step.click()
app.processEvents()
rows = []
for r in range(w.execution_log.rowCount()):
    mod = w.execution_log.item(r, 2)
    res = w.execution_log.item(r, 4)
    if mod is not None and res is not None:
        rows.append((mod.text(), res.text(), res.foreground().color().name()))
hit = [r for r in rows if r[0] == "人脸识别"]
check('⑤ 换过图之后：跑得动、**不是红字**（共享的级联文件确实被用上了，没退回"未选择级联文件"）',
      bool(hit) and hit[-1][2] != "#c80000" and hit[-1][1].startswith("检测到"), hit)
face.params["cascade_file"] = CASCADE_A
face.params["face_scale_factor"] = 1.1
w.btn_step.click()
app.processEvents()
rows = []
for r in range(w.execution_log.rowCount()):
    mod = w.execution_log.item(r, 2)
    res = w.execution_log.item(r, 4)
    if mod is not None and res is not None:
        rows.append((mod.text(), res.text()))
hit = [r for r in rows if r[0] == "人脸识别"]
check('⑤ 把共享的级联文件换成 default + 缩放步长 1.1 ⇒ 检出 1 张（参数真的在驱动算法）',
      bool(hit) and hit[-1][1].startswith("检测到1张人脸"), hit)

print('-' * 70)
if fails:
    print('MODE=%s  失败项：%d' % (MODE, len(fails)))
    for name in fails:
        print('   - ' + name)
else:
    print('MODE=%s  失败项：无' % MODE)
sys.exit(1 if fails else 0)
