# -*- coding: utf-8 -*-
"""
批次4 目标5-M2 验证③：颜色提取节点（语义 + 参数校验 + 引擎日志 + 树里改名）

    python dsh_m2_color_check.py before    # 指向改前快照 ⇒ 复现"模块未实现、颜色没改名"
    python dsh_m2_color_check.py after

判据要点：
    · **阈值内保留原色、阈值外置黑**（用户原话："不在阈值中的画面变成黑色"）；
    · 处理类铁律：返回**新图**、传进去的图**一个像素都不改**；
    · **只在 ROI 内**提取，ROI 外原样；
    · HSV / RGB 两套阈值都能用（RGB 那套要先把 BGR 转成 RGB，否则"参数里的 R"对不上用户看到的 R）；
    · 参数校验：H 上限夹到 179、下限 > 上限自动互换、**另一套（没显示的）不动**；
    · 引擎日志文案带像素计数（"提取到 N 个像素（x.x%）"）；
    · main.ui 树里"颜色"已改名成"颜色提取"。
"""
import os
import sys
import xml.etree.ElementTree as ET

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
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ui.GenericProcessDialog as GPD
from core.NodeRegistry import get_spec

print('MODE = %s | NodeRegistry 来自 %s' % (MODE, os.path.dirname(m.__file__)))


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
    # 注意：extra 可能是 numpy 数组 ⇒ 不能用 `if extra` 判真假（会抛"truth value is ambiguous"）
    text = '' if extra is None else '   <- ' + str(extra)
    print(('PASS  ' if cond else 'FAIL  ') + name + text)
    if not cond:
        fails.append(name)


def red_blue(w=40, h=40):
    """左半纯红、右半纯蓝（BGR 顺序）"""
    img = np.zeros((h, w, 3), np.uint8)
    img[:, :w // 2] = (0, 0, 255)
    img[:, w // 2:] = (255, 0, 0)
    return img


# ======================================================================
# ① 树里改名（静态断言）
# ======================================================================
tree = ET.parse(os.path.join(PROJ, "main.ui"))
texts = [el.text for el in tree.iter("string") if el.text]
check('① main.ui 树里有「颜色提取」', "颜色提取" in texts, [t for t in texts if "颜色" in str(t)])
check('① main.ui 树里不再有裸的「颜色」项', "颜色" not in texts, [t for t in texts if t == "颜色"])
if MODE == 'before':
    # 注：main.ui 是**共用文件**（before 快照里没有它），所以这条树改名断言只在 after 模式跑
    check('① 改前：「颜色」还没实现（注册表里没有这个算子）',
          get_spec("颜色提取") is None and get_spec("颜色") is None)

spec = get_spec("颜色提取")

if MODE == 'after':
    check('① 改后：注册表里有「颜色提取」，且是**处理类**（改图、下游看得见）',
          spec is not None and spec.kind == "process", None if spec is None else spec.kind)
    check('① 改后：「颜色」这个名字不再对应任何算子（改名不留旧入口）',
          get_spec("颜色") is None)
    check('① 改后：13 个参数（模型 + HSV 6 + RGB 6）', len(spec.param_specs) == 13,
          len(spec.param_specs))

    # ==================================================================
    # ② 语义：阈值内保留原色、阈值外置黑（HSV 默认 = 红色）
    # ==================================================================
    img = red_blue()
    original = img.copy()
    out, res = spec.run(None, img, (0, 0, 40, 40), {})
    check('② HSV 默认（红色）：左半保留原色',
          tuple(int(v) for v in out[20, 5]) == (0, 0, 255), out[20, 5])
    check('② HSV 默认：右半（蓝色）**变黑**', int(out[20, 35].sum()) == 0, out[20, 35])
    check('② 处理类铁律：返回**新图**，不是同一个对象', out is not img)
    check('② 处理类铁律：传进去的图**一个像素都没改**', np.array_equal(img, original))
    check('② 结果里带像素计数（800/1600）',
          res[0].get("提取像素") == 800 and res[0].get("总像素") == 1600, res)

    # ==================================================================
    # ③ RGB 那套阈值（先把 BGR 转成 RGB，保证"参数里的 R"就是用户看到的 R）
    # ==================================================================
    out_rgb, res_rgb = spec.run(None, img, (0, 0, 40, 40), {"color_model": "RGB"})
    check('③ RGB 默认（红色）：左半保留、右半变黑',
          tuple(int(v) for v in out_rgb[20, 5]) == (0, 0, 255)
          and int(out_rgb[20, 35].sum()) == 0,
          (out_rgb[20, 5], out_rgb[20, 35]))
    check('③ 结果里写了用的哪种模型', res_rgb[0].get("模型") == "RGB", res_rgb)
    # RGB 档去匹配蓝色：R 0~50 / G 0~50 / B 150~255 ⇒ 蓝半命中
    out_blue, _ = spec.run(None, img, (0, 0, 40, 40),
                           {"color_model": "RGB", "rgb_r_low": 0, "rgb_r_high": 50,
                            "rgb_g_low": 0, "rgb_g_high": 50,
                            "rgb_b_low": 150, "rgb_b_high": 255})
    check('③ RGB 档改成"取蓝色"：右半保留、左半变黑（说明 R/G/B 没串位）',
          tuple(int(v) for v in out_blue[20, 35]) == (255, 0, 0)
          and int(out_blue[20, 5].sum()) == 0, (out_blue[20, 5], out_blue[20, 35]))

    # ==================================================================
    # ④ 只在 ROI 内提取，ROI 外原样
    # ==================================================================
    all_red = np.zeros((40, 40, 3), np.uint8)
    all_red[:, :] = (0, 0, 255)
    keep = all_red.copy()
    # ROI 只盖左半，阈值取"蓝色"（这张图里一个蓝像素都没有）⇒ ROI 内变黑、ROI 外保持红
    out_roi, _ = spec.run(None, all_red, (0, 0, 20, 40),
                          {"color_model": "HSV", "hsv_h_low": 100, "hsv_h_high": 130})
    check('④ ROI 内（没命中）⇒ 变黑', int(out_roi[20, 5].sum()) == 0, out_roi[20, 5])
    check('④ ROI 外 ⇒ 原样不动（还是红）', tuple(int(v) for v in out_roi[20, 35]) == (0, 0, 255),
          out_roi[20, 35])
    check('④ ROI 外的图也没被改坏', np.array_equal(all_red, keep))

    # ==================================================================
    # ⑤ 参数校验
    # ==================================================================
    fixed, notes, errors = spec.validate({"color_model": "HSV", "hsv_h_high": 200})
    check('⑤ H 上限 200 ⇒ 夹到 179（OpenCV 的 H 只有 0~179）',
          fixed["hsv_h_high"] == 179 and any("H 上限" in n for n in notes),
          (fixed.get("hsv_h_high"), notes))

    fixed, notes, errors = spec.validate({"color_model": "HSV",
                                          "hsv_h_low": 100, "hsv_h_high": 10})
    check('⑤ 下限 > 上限 ⇒ 自动互换 + 说明（否则 inRange 会静默全黑）',
          fixed["hsv_h_low"] == 10 and fixed["hsv_h_high"] == 100
          and any("已互换" in n for n in notes), (fixed.get("hsv_h_low"),
                                                 fixed.get("hsv_h_high"), notes))

    fixed, notes, errors = spec.validate({"color_model": "HSV", "rgb_r_high": 999})
    check('⑤ 没显示的那一套（RGB）**不校验也不改**（免得提示里冒出看不见的参数名）',
          fixed["rgb_r_high"] == 999 and notes == [], (fixed.get("rgb_r_high"), notes))

    fixed, notes, errors = spec.validate({"color_model": "RGB", "rgb_r_high": 999})
    check('⑤ 切到 RGB 之后，那套才被夹取（999 ⇒ 255）',
          fixed["rgb_r_high"] == 255 and any("R 上限" in n for n in notes),
          (fixed.get("rgb_r_high"), notes))

    check('⑤ 合法参数：零说明',
          spec.validate({"color_model": "HSV", "hsv_h_low": 0, "hsv_h_high": 10})[1] == [])

    # ==================================================================
    # ⑥ 引擎路径：日志文案带像素计数，且不是红字
    # ==================================================================
    w = m.MainWindow()
    w.main_window.show()
    w.current_static_image = red_blue()
    node = w.add_flow_node("颜色提取", QPointF(20, 20))
    w.selected_node = node
    w.btn_step.click()
    app.processEvents()
    rows = []
    for r in range(w.execution_log.rowCount()):
        mod = w.execution_log.item(r, 2)
        res_item = w.execution_log.item(r, 4)
        if mod is not None and res_item is not None:
            rows.append((mod.text(), res_item.text(), res_item.foreground().color().name()))
    hit = [r for r in rows if r[0] == "颜色提取"]
    check('⑥ 引擎路径跑得动，日志有「颜色提取」这一行', bool(hit), rows)
    check('⑥ 文案 = 提取到 800 个像素（50.0%）',
          bool(hit) and hit[-1][1].startswith("提取到 800 个像素（50.0%）"), hit)
    check('⑥ 正常结果不是红字（错误通道没误伤）',
          bool(hit) and hit[-1][2] != "#c80000", hit)

print('-' * 70)
if fails:
    print('MODE=%s  失败项：%d' % (MODE, len(fails)))
    for name in fails:
        print('   - ' + name)
else:
    print('MODE=%s  失败项：无' % MODE)
sys.exit(1 if fails else 0)
