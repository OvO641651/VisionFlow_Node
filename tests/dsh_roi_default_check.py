# -*- coding: utf-8 -*-
"""本轮验证：
1、取反（没有可调参数）的参数窗口宽度要和其他算子一致；
2、"RSI创建"默认选中"继承上游"（窗口里 + 引擎默认行为都要如此），"绘制"仍可选。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2 import QtWidgets
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])

import main as m

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


w = m.MainWindow()
w.main_window.show()
P_HOUGH = os.path.join("image", "HoughLines.jpg")
HOUGH = cv2.imread(P_HOUGH)

DIALOGS = {"灰度": m.GrayParamsDialog, "直线识别": m.LineParamsDialog, "圆识别": m.CircleParamsDialog}

# ============ 1、窗口宽度一致 ============
widths = {}
for i, name in enumerate(["灰度", "取反", "滤波", "二值化", "形态学", "边缘提取", "直线识别", "圆识别"]):
    node = w.add_flow_node(name, QPointF(20 + i * 10, 20 + i * 10))
    cls = DIALOGS.get(name, m.GenericProcessDialog)
    dlg = cls(w.main_window, node=node, main_window=w)
    dlg.show()
    for _ in range(3):
        app.processEvents()
    widths[name] = dlg.width()
    if name == "取反":
        tw = dlg.ui.tabWidget
        for j in range(tw.count()):
            if tw.tabText(j) == "运行参数":
                run_page_w = tw.widget(j).sizeHint().width()
    dlg.close()

print("各窗口宽度:", widths)
base = widths["二值化"]
check("取反窗口宽度与其他算子一致（≤ 基准 + 6px）",
      widths["取反"] <= base + 6, (widths["取反"], base))
check("取反的'运行参数'页不再被长提示顶宽（≤ 260px）", run_page_w <= 260, run_page_w)
check("通用窗口的算子宽度全都一致（都在基准 ±6px 内）",
      all(abs(widths[n] - base) <= 6
          for n in ["灰度", "取反", "滤波", "二值化", "形态学", "边缘提取", "直线识别"]), widths)
check("'圆识别'是专用窗口（自己一套参数），宽度允许更宽一点",
      widths["圆识别"] >= base, (widths["圆识别"], base))

# ============ 2、窗口里默认选中"继承上游" ============
node = w.add_flow_node("取反", QPointF(400, 20))
dlg = m.GenericProcessDialog(w.main_window, node=node, main_window=w)
check("新节点的窗口：ROI创建默认选中'继承上游'",
      dlg.roi_inherit.isChecked() and not dlg.roi_draw.isChecked(),
      (dlg.roi_inherit.isChecked(), dlg.roi_draw.isChecked()))
check("默认选中'继承上游'后，手绘 ROI 那些行是隐藏的",
      not dlg.spin_roi_x.isVisibleTo(dlg.ui) and not dlg.spin_roi_y.isVisibleTo(dlg.ui))
dlg.roi_draw.setChecked(True)
for _ in range(2):
    app.processEvents()
check("切回'绘制'后，手绘 ROI 行恢复可见", dlg.spin_roi_x.isVisibleTo(dlg.ui))
check("两档都还在（没有删掉'绘制'）",
      dlg.roi_draw.isCheckable() and dlg.roi_inherit.isCheckable())

# ============ 3、引擎默认也走"继承上游" ============
n_src = w.add_flow_node("图片源", QPointF(400, 200))
n_inv = w.add_flow_node("取反", QPointF(400, 360))
n_src.params.update({"source_type": "图片", "source_path": P_HOUGH})
w.add_edge(n_src, n_inv)

# 上游（图片源）这一轮的有效 ROI
_out, _res, src_roi, _spec = w._execute_node(n_src, HOUGH, None)
check("图片源的有效 ROI = 它输出的整张图", src_roi[2] == HOUGH.shape[1] and src_roi[3] == HOUGH.shape[0],
      src_roi)

# 下游节点不写 roi_inherit（= 缺省）→ 应该继承上游那块 ROI
n_inv.params.pop("roi_inherit", None)
_out2, _res2, roi2, spec2 = w._execute_node(n_inv, HOUGH, None, src_roi)
check("缺省情况下：下游节点继承上游的 ROI 框（roi_info 与上游一致、标记为 roi）",
      (roi2[0], roi2[1], roi2[2], roi2[3]) == (src_roi[0], src_roi[1], src_roi[2], src_roi[3])
      and roi2[6] == "roi", roi2)
# ★ 批次6 目标3-M1 第 2 次修改（3.1.2）：用户要求去掉「← 继承上游ROI框」短注
#   ⇒ 这里改断言"日志里**不再**写这句"；继承是否生效仍由上一条 roi_info 断言证明。
check("日志里不再追「继承上游ROI框」短注（3.1.2 起）",
      "继承上游" not in w._format_result_text(n_inv, _res2, roi2, spec2),
      w._format_result_text(n_inv, _res2, roi2, spec2))

# 明确选"绘制"（roi_inherit=False）+ 自己的 ROI → 就用自己的
n_inv.params.update({"roi_inherit": False, "roi_x": 10, "roi_y": 20, "roi_w": 100, "roi_h": 80})
_out3, _res3, roi3, spec3 = w._execute_node(n_inv, HOUGH, None, src_roi)
check("明确选'绘制'时：用自己的 ROI（10,20,100,80），不继承",
      (roi3[0], roi3[1], roi3[2], roi3[3]) == (10, 20, 100, 80) and roi3[6] == "", roi3)

# 缺省 + 上游是全局图像源（没有可继承的框）→ 自动退回本节点 ROI（不能因为默认继承就 0 面积跳过）
n_inv.params.pop("roi_inherit", None)
n_inv.params.pop("roi_x", None)
n_inv.params.pop("roi_y", None)
n_inv.params.pop("roi_w", None)
n_inv.params.pop("roi_h", None)
_out4, _res4, roi4, spec4 = w._execute_node(n_inv, HOUGH, None, None)
check("缺省但上游没有可继承的框：自动退回整图 ROI（不会 0 面积跳过）",
      roi4[2] == HOUGH.shape[1] and roi4[3] == HOUGH.shape[0], roi4)

# 走一遍真实按钮：连续执行，日志里应出现"继承上游ROI框"
w.result_cache.clear()
w.selected_node = n_inv
w.btn_continuous.click()
rows = []
for r in range(w.execution_log.rowCount()):
    rows.append((w.execution_log.item(r, 2).text() if w.execution_log.item(r, 2) else "",
                 w.execution_log.item(r, 4).text() if w.execution_log.item(r, 4) else ""))
check("连续执行：取反那行不再带「← 继承上游ROI框」短注（3.1.2 起）",
      not any(n == "取反" and "继承上游" in t for n, t in rows), rows)

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
