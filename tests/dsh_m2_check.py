# -*- coding: utf-8 -*-
"""批次4 目标二（5 个处理类算子 + 通用参数窗口 + 树分组）验证脚本，跑完即删"""
import os
import sys
import traceback

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2 import QtWidgets
from PySide2.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QLabel,
                               QSpinBox, QWidget)
from PySide2.QtCore import QPointF

app = QApplication([])

import main as m
import core.NodeRegistry as NodeRegistry
from core.NodeRegistry import get_spec, KIND_PROCESS

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


# ===================== 1、注册表 =====================
PROCESS_OPS = ("灰度", "取反", "滤波", "二值化", "形态学", "边缘提取")
for name in PROCESS_OPS:
    spec = get_spec(name)
    check("注册了处理类算子：%s" % name, spec is not None and spec.kind == KIND_PROCESS,
          None if spec is None else spec.kind)
check("灰度 / 直线 / 圆 都还在", all(get_spec(n) is not None for n in ("灰度", "直线识别", "圆识别")))
check("灰度走专用窗口（param_specs=None）", get_spec("灰度").param_specs is None)
check("取反走通用窗口但没有参数（[]）", get_spec("取反").param_specs == [])
check("直线 / 圆 仍是检测类、走专用窗口",
      get_spec("直线识别").kind == "detect" and get_spec("圆识别").kind == "detect"
      and get_spec("直线识别").param_specs is None and get_spec("圆识别").param_specs is None)
check("灰度仍是处理类、仍带 whole_image_param",
      get_spec("灰度").modifies_image is True
      and get_spec("灰度").whole_image_param == "gray_full_image")
check("目标2 当时明确不做的两个识别节点，2026.10.12 目标5-M2 起都已注册（人脸 / 颜色提取）",
      get_spec("人脸识别") is not None and get_spec("颜色提取") is not None)

EXPECTED_PARAMS = {
    "滤波": [("blur_type", "combo"), ("blur_ksize", "int"), ("blur_sigma", "float")],
    "二值化": [("thresh_mode", "combo"), ("thresh_value", "int"),
               ("thresh_maxval", "int"), ("thresh_type", "combo")],
    "形态学": [("morph_op", "combo"), ("morph_shape", "combo"),
               ("morph_ksize", "int"), ("morph_iterations", "int")],
    "边缘提取": [("edge_method", "combo"), ("edge_low", "int"),
                 ("edge_high", "int"), ("edge_ksize", "int")],
}
for name, expected in EXPECTED_PARAMS.items():
    specs = get_spec(name).param_specs
    got = [(item[0], item[2]) for item in specs]
    check("%s 的参数表（名字 + 控件类型）" % name, got == expected, got)
    check("%s 参数表每一项都是 4 元组且带中文名" % name,
          all(len(item) == 4 and item[1] for item in specs))

# ===================== 2、算子效果 =====================
img = cv2.imread(os.path.join("image", "lena.png"))
check("测试图 lena.png 读到了", img is not None and img.ndim == 3)
w = m.MainWindow()
detector = w.detector
ROI = (100, 100, 300, 300)          # 故意不取整图


def run(name, params, roi=ROI):
    return get_spec(name).run(detector, img, roi, params)


CASES = [
    ("取反", {}),
    ("滤波", {"blur_type": "高斯", "blur_ksize": 7, "blur_sigma": 0}),
    ("二值化", {"thresh_mode": "固定阈值", "thresh_value": 127, "thresh_maxval": 255,
                "thresh_type": "二值"}),
    ("形态学", {"morph_op": "腐蚀", "morph_shape": "矩形", "morph_ksize": 5,
                "morph_iterations": 1}),
    ("边缘提取", {"edge_method": "Canny", "edge_low": 50, "edge_high": 150}),
    ("灰度", {}),
]
for name, params in CASES:
    before = img.copy()
    out, results = run(name, params)
    check("%s：传进去的原图没被改动（数据层没被污染）" % name, np.array_equal(img, before))
    check("%s：返回的是新图、3 通道、尺寸不变" % name,
          out is not img and out.ndim == 3 and out.shape == img.shape,
          (out is img, out.ndim, out.shape))
    check("%s：只有 ROI 那一块变了，ROI 以外原样" % name,
          not np.array_equal(out[100:400, 100:400], img[100:400, 100:400])
          and np.array_equal(out[:100, :], img[:100, :])
          and np.array_equal(out[:, :100], img[:, :100]))
    check("%s：结果是空列表、日志文案短" % name,
          results == [] and isinstance(get_spec(name).format_result(results), str)
          and 0 < len(get_spec(name).format_result(results)) < 30,
          get_spec(name).format_result(results))

# 对照实验：参数不同 → 输出必须不同（否则这个参数就是"正确但没用"）
PAIRS = [
    ("二值化", {"thresh_mode": "固定阈值", "thresh_value": 60},
     {"thresh_mode": "固定阈值", "thresh_value": 200}),
    ("二值化", {"thresh_mode": "固定阈值", "thresh_value": 127, "thresh_type": "二值"},
     {"thresh_mode": "固定阈值", "thresh_value": 127, "thresh_type": "反二值"}),
    ("滤波", {"blur_type": "均值", "blur_ksize": 9}, {"blur_type": "中值", "blur_ksize": 9}),
    ("形态学", {"morph_op": "腐蚀", "morph_ksize": 5}, {"morph_op": "膨胀", "morph_ksize": 5}),
    ("边缘提取", {"edge_method": "Canny"}, {"edge_method": "Sobel"}),
    ("边缘提取", {"edge_method": "Canny", "edge_low": 20, "edge_high": 60},
     {"edge_method": "Canny", "edge_low": 150, "edge_high": 300}),
]
for name, p1, p2 in PAIRS:
    o1, _ = run(name, p1)
    o2, _ = run(name, p2)
    check("%s：换参数结果就不同 %s vs %s" % (name, p1, p2), not np.array_equal(o1, o2))

# 核尺寸强制奇数
out_even, _ = run("滤波", {"blur_type": "高斯", "blur_ksize": 8})
out_odd, _ = run("滤波", {"blur_type": "高斯", "blur_ksize": 9})
check("滤波：偶数核会自动纠正成奇数（8 -> 9，不会报错）", np.array_equal(out_even, out_odd))

# 灰度"作用于整图"（whole_image_param 那条路）
out_full, _ = run("灰度", {"gray_full_image": True})
check("灰度 作用于整图：ROI 以外也变灰了", not np.array_equal(out_full[:50, :50], img[:50, :50]))

# ROI 被裁成 0 尺寸时不崩
out_zero, _ = run("取反", {}, roi=(10, 10, 0, 0))
check("ROI 为 0 尺寸时不崩、原样返回", out_zero.shape == img.shape)

# ===================== 3、引擎跑一条链 =====================
n1 = w.add_flow_node("直线识别", QPointF(20, 20))
n2 = w.add_flow_node("灰度", QPointF(20, 200))
n3 = w.add_flow_node("二值化", QPointF(20, 380))
w.add_edge(n1, n2)
w.add_edge(n2, n3)
before = img.copy()
display, all_data, exec_info = w._run_flow_pipeline(img)
check("引擎跑通 直线→灰度→二值化（3 行日志）", len(exec_info) == 3, exec_info)
check("日志模块名顺序对", [row[2] for row in exec_info] == ["直线识别", "灰度", "二值化"],
      [row[2] for row in exec_info])
check("日志结果文案非空且短", all(row[4] and len(str(row[4])) < 36 for row in exec_info),
      [row[4] for row in exec_info])
check("整条链跑完：喂进去的原始帧没被改动", np.array_equal(img, before))
check("显示图确实被处理过（与原始帧不同）", not np.array_equal(display, img))

# ===================== 4、通用参数窗口 =====================
def new_dialog(op, params=None):
    node = w.add_flow_node(op, QPointF(600, 20))
    if params:
        node.params.update(params)
    return node, m.GenericProcessDialog(w.main_window, node=node, main_window=w)


KIND_CLASS = {"combo": QComboBox, "int": QSpinBox, "float": QDoubleSpinBox}
for name, expected in EXPECTED_PARAMS.items():
    node, dlg = new_dialog(name)
    keys = [item[0] for item in expected]
    check("%s：通用窗口生成了 %d 个控件" % (name, len(keys)),
          sorted(dlg.param_controls) == sorted(keys), sorted(dlg.param_controls))
    check("%s：控件类型对" % name,
          all(isinstance(dlg.param_controls[k], KIND_CLASS[t]) for k, t in expected))
    check("%s：控件名字是 param_<键名>" % name,
          all(dlg.param_controls[k].objectName() == "param_" + k for k in keys))
    check("%s：直线专用控件被藏起来" % name, not dlg.spin_canny_low.isVisibleTo(dlg.ui))
    # 动态控件在"运行参数"页上：先切到那一页再看可见性（非当前页会被 QTabWidget 藏起来）
    dlg.ui.tabWidget.setCurrentIndex(1)
    check("%s：动态控件在'运行参数'页上是可见的" % name,
          dlg.param_controls[keys[0]].isVisibleTo(dlg.ui))
    check("%s：'显示结果'页已去掉（只剩 基本参数/运行参数）" % name,
          dlg.ui.tabWidget.count() == 2, dlg.ui.tabWidget.count())
    dlg._update_params()
    check("%s：参数写进了 node.params" % name, all(k in node.params for k in keys),
          sorted(node.params))
    check("%s：没有把直线参数混进 node.params" % name,
          all(k not in node.params for k in ("canny_low", "canny_high", "hough_threshold",
                                             "min_line_length", "max_line_gap")),
          sorted(node.params))
    check("%s：基本参数照常保存（roi_x / roi_inherit 在）" % name,
          "roi_x" in node.params and "roi_inherit" in node.params)
    # 重开窗口会不会把值读回来
    dlg2 = m.GenericProcessDialog(w.main_window, node=node, main_window=w)
    first_key, first_kind = expected[0]
    check("%s：重开窗口能读回参数" % name,
          dlg2._widget_value(first_kind, dlg2.param_controls[first_key])
          == node.params[first_key],
          (dlg2._widget_value(first_kind, dlg2.param_controls[first_key]),
           node.params[first_key]))
    # 参数能进方案（.vfproj 往返）
    saved_node = None
    for item in w._collect_project()["pages"][0]["nodes"]:
        if item["name"] == name:
            saved_node = item
    check("%s：参数会写进方案文件的结构里" % name,
          saved_node is not None and all(k in saved_node["params"] for k in keys))

# 取反：没有参数
node, dlg = new_dialog("取反")
check("取反：通用窗口没有动态控件", dlg.param_controls == {})
check("取反：运行参数页给了提示文字",
      any(isinstance(x, QLabel) and "没有可调参数" in x.text()
          for x in dlg.ui.findChildren(QLabel)))
check("取反：'显示结果'页也去掉了", dlg.ui.tabWidget.count() == 2)
dlg._update_params()
check("取反：不会产生多余参数（只有基本参数那几个）",
      set(node.params) <= {"roi_x", "roi_y", "roi_w", "roi_h", "roi_shape", "roi_inherit",
                           "roi_margin", "roi_source", "hide_roi"},
      sorted(node.params))

# ===================== 5、双击路由（替身类） =====================
def make_stub(label, log):
    class Stub(object):
        def __init__(self, parent=None, node=None, main_window=None):
            log.append((label, node.name))

        def resize(self, *args):
            pass

        def exec_(self):
            pass

        class _Sig(object):
            def connect(self, *args):
                pass

        finished = _Sig()

    return Stub


log = []
m.LineParamsDialog = make_stub("专用-直线", log)
m.CircleParamsDialog = make_stub("专用-圆", log)
m.GrayParamsDialog = make_stub("专用-灰度", log)
m.GenericProcessDialog = make_stub("通用", log)
for op in ("直线识别", "圆识别", "灰度", "滤波", "二值化", "取反", "形态学", "边缘提取"):
    node = w.add_flow_node(op, QPointF(800, 20))
    w.on_node_double_clicked(node)
expected_routes = [("专用-直线", "直线识别"), ("专用-圆", "圆识别"), ("专用-灰度", "灰度"),
                   ("通用", "滤波"), ("通用", "二值化"), ("通用", "取反"),
                   ("通用", "形态学"), ("通用", "边缘提取")]
check("双击路由：专用窗口优先、通用窗口兜底", log == expected_routes, log)
log[:] = []
node = w.add_flow_node("人脸识别", QPointF(1000, 20))
w.on_node_double_clicked(node)
check("人脸：双击现在会打开通用参数窗口（目标5-M2 起已实现，不再是「双击无反应」）",
      log == [("通用", "人脸识别")], log)

# ===================== 6、左侧树结构 =====================
tree = w.main_window.findChild(QtWidgets.QTreeWidget, "tree")
groups = {}
leaves = []
for i in range(tree.topLevelItemCount()):
    top = tree.topLevelItem(i)
    children = [top.child(j).text(0) for j in range(top.childCount())]
    groups[top.text(0)] = children
    leaves.extend(children)
check("树里有'处理'分组，且内容正确",
      groups.get("处理") == ["灰度", "取反", "滤波", "二值化", "形态学", "边缘提取"],
      groups.get("处理"))
check("'检测识别'分组是 直线识别 / 圆识别 / 人脸识别（2026.10.14 两个树干合并）",
      groups.get("检测识别") == ["直线识别", "圆识别", "人脸识别"], groups.get("检测识别"))
check("'识别'树干已并入'检测识别'（不再单独存在）", "识别" not in groups, sorted(groups))
check("树里每个叶子都已注册（识别类的两个也算实现了）",
      sorted([x for x in leaves if get_spec(x) is None]) == [],
      sorted([x for x in leaves if get_spec(x) is None]))
check("分组都在（处理 / 检测识别 / 颜色处理）",
      set(["处理", "检测识别", "颜色处理"]) <= set(groups), sorted(groups))

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
