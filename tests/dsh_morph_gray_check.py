# -*- coding: utf-8 -*-
"""形态学扩 3 档 + 灰度算法搬到 ProcessOps 的验证脚本，跑完即删"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])

import main as m
from core.NodeRegistry import get_spec
from ops.process.GrayOps import to_gray
from core.Detector import DetectorShape

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


img = cv2.imread(os.path.join("image", "lena.png"))
w = m.MainWindow()
detector = w.detector
ROI = (100, 100, 300, 300)
FULL = (0, 0, img.shape[1], img.shape[0])

# ===================== 1、灰度算法搬家 =====================
check("DetectorShape 里已经没有 gray_bgr（搬走了）", not hasattr(DetectorShape, "gray_bgr"))
check("灰度节点文件（ops/process/GrayOps.py）里有了 to_gray", callable(to_gray))

expect_gray = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
got = to_gray(img)
check("to_gray（BGR 输入）与原 gray_bgr 结果完全一致、且是 3 通道",
      np.array_equal(got, expect_gray) and got.ndim == 3)
single = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
check("to_gray 单通道输入 → 补成 3 通道", to_gray(single).ndim == 3)
check("to_gray 空输入 / None 不崩", to_gray(None) is None)

# 灰度算子（引擎调用的那条路）两条分支
before = img.copy()
out_roi, results = get_spec("灰度").run(detector, img, ROI, {})
check("灰度 ROI 分支：原图没被改 + 3 通道 + ROI 外原样 + ROI 内与预期一致",
      np.array_equal(img, before) and out_roi.ndim == 3
      and np.array_equal(out_roi[:100, :], img[:100, :])
      and np.array_equal(out_roi[100:400, 100:400], expect_gray[100:400, 100:400])
      and results == [])
out_full, _ = get_spec("灰度").run(detector, img, ROI, {"gray_full_image": True})
check("灰度 作用于整图分支：整幅都灰了", np.array_equal(out_full, expect_gray))

# ===================== 2、形态学 7 档 =====================
spec = get_spec("形态学")
options = list(spec.param_specs[0][3]["options"])
EXPECT_OPS = ["腐蚀", "膨胀", "开运算", "闭运算", "梯度", "顶帽", "黑帽"]
check("形态学下拉 = 7 档（新加 梯度 / 顶帽 / 黑帽）", options == EXPECT_OPS, options)
check("形态学默认值仍是 腐蚀", spec.param_specs[0][3]["default"] == "腐蚀")

outs = {}
for op in EXPECT_OPS:
    o, _ = spec.run(detector, img, ROI,
                    {"morph_op": op, "morph_shape": "矩形",
                     "morph_ksize": 5, "morph_iterations": 1})
    outs[op] = o
    check("形态学 %s：原图没被改 + 3 通道 + 尺寸不变" % op,
          np.array_equal(img, before) and o.ndim == 3 and o.shape == img.shape)
    check("形态学 %s：ROI 内确实变了" % op,
          not np.array_equal(o[100:400, 100:400], img[100:400, 100:400]))

for a, b in (("梯度", "腐蚀"), ("梯度", "膨胀"), ("梯度", "开运算"), ("顶帽", "开运算"),
             ("黑帽", "闭运算"), ("顶帽", "黑帽"), ("梯度", "顶帽")):
    check("形态学 %s 与 %s 的输出不同（不是同一个算法换了个名字）" % (a, b),
          not np.array_equal(outs[a], outs[b]))

# 语义核对：在灰度图上，顶帽 = 原图 - 开运算、黑帽 = 闭运算 - 原图、梯度 = 膨胀 - 腐蚀
gray3 = to_gray(img)


def morph(op, src):
    out, _ = spec.run(detector, src, (0, 0, src.shape[1], src.shape[0]),
                      {"morph_op": op, "morph_shape": "矩形",
                       "morph_ksize": 5, "morph_iterations": 1})
    return out


opened = morph("开运算", gray3)
closed = morph("闭运算", gray3)
check("顶帽 == 原图 − 开运算（逐像素相等）",
      np.array_equal(morph("顶帽", gray3), cv2.subtract(gray3, opened)))
check("黑帽 == 闭运算 − 原图（逐像素相等）",
      np.array_equal(morph("黑帽", gray3), cv2.subtract(closed, gray3)))
check("梯度 == 膨胀 − 腐蚀（逐像素相等）",
      np.array_equal(morph("梯度", gray3), cv2.subtract(morph("膨胀", gray3), morph("腐蚀", gray3))))

# ===================== 3、引擎链：直线 → 灰度 → 形态学(梯度) =====================
w.flow_page_mgr.tab_widget.setTabText(0, "链测试")
n1 = w.add_flow_node("直线识别", QPointF(20, 20))
n2 = w.add_flow_node("灰度", QPointF(20, 200))
n3 = w.add_flow_node("形态学", QPointF(20, 380))
n1.params["canny_low"] = 60
n2.params["gray_full_image"] = True
n3.params.update({"morph_op": "梯度", "morph_ksize": 3, "morph_iterations": 1})
w.add_edge(n1, n2)
w.add_edge(n2, n3)
before = img.copy()
display, all_data, exec_info = w._run_flow_pipeline(img)
check("引擎跑通 直线→灰度→形态学 (3 行日志)", len(exec_info) == 3, exec_info)
check("日志模块名对", [row[2] for row in exec_info] == ["直线识别", "灰度", "形态学"],
      [row[2] for row in exec_info])
check("日志文案都是处理类那句 / 检测那句", "执行成功（图像已处理" in exec_info[2][4], exec_info[2][4])
check("整条链跑完：原始帧没被改动", np.array_equal(img, before))
check("显示图确实被处理过", not np.array_equal(display, img))

# ===================== 4、通用窗口里的形态学下拉 =====================
node = w.add_flow_node("形态学", QPointF(600, 20))
dlg = m.GenericProcessDialog(w.main_window, node=node, main_window=w)
combo = dlg.param_controls["morph_op"]
check("通用窗口里 运算 下拉也是 7 项",
      combo.count() == 7 and [combo.itemText(i) for i in range(7)] == EXPECT_OPS,
      [combo.itemText(i) for i in range(combo.count())])
combo.setCurrentText("顶帽")
dlg._update_params()
check("窗口里选'顶帽'能写进 node.params", node.params.get("morph_op") == "顶帽",
      node.params.get("morph_op"))
dlg2 = m.GenericProcessDialog(w.main_window, node=node, main_window=w)
check("重开窗口能读回'顶帽'", dlg2.param_controls["morph_op"].currentText() == "顶帽",
      dlg2.param_controls["morph_op"].currentText())

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
