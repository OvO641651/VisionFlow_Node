# -*- coding: utf-8 -*-
"""用户报的 5 个问题：逐条验证修复效果（全部走按钮 / 窗口槽函数的真实路径）

背景设定（复现用户场景）：
    图库里"导入"的是 image/lena.png（512×512）；
    流程里的"图片源"指定的是 image/HoughLines.jpg（897×708）——两张明显不同尺寸的图。
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
import widgets.FlowPages as FlowPages

fails = []
warnings = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


class FakeMB(object):
    @staticmethod
    def warning(parent, title, text):
        warnings.append(text)

    @staticmethod
    def information(parent, title, text):
        pass

    @staticmethod
    def question(*a, **k):
        return 0


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB

LENA = cv2.imread(os.path.join("image", "lena.png"))            # 512x512，"图库里那张"
HOUGH = cv2.imread(os.path.join("image", "HoughLines.jpg"))     # 897x708，"图片源那张"
BLUE = np.zeros((200, 300, 3), dtype=np.uint8)                  # 全局图像源专用（换个尺寸好区分）
BLUE[:, :] = (255, 0, 0)
P_LENA = os.path.join("image", "lena.png")
P_HOUGH = os.path.join("image", "HoughLines.jpg")

w = m.MainWindow()
if getattr(w, 'gallery_widget', None) is not None:
    w.gallery_widget.set_scope_all(False)   # 本套假设'只跑当前这一张'
tabs = w.flow_page_mgr.tab_widget
tabs.setTabText(0, "用户场景")


def cached_shapes():
    return sorted(v["frame"].shape for v in w.result_cache.values())


def log_rows():
    rows = []
    for r in range(w.execution_log.rowCount()):
        name = w.execution_log.item(r, 2)
        src = w.execution_log.item(r, 3)
        rows.append((name.text() if name else "", src.text() if src else ""))
    return rows


# 页面：图片源(文件=HoughLines) → 灰度 → 二值化；另有一条 取反 → 边缘提取（吃全局图像源）
n_src = w.add_flow_node("图片源", QPointF(20, 20))
n_gray = w.add_flow_node("灰度", QPointF(20, 160))
n_bin = w.add_flow_node("二值化", QPointF(20, 300))
n_inv = w.add_flow_node("取反", QPointF(320, 20))
n_edge = w.add_flow_node("边缘提取", QPointF(320, 160))
n_src.params.update({"source_type": "单张图片", "source_path": P_HOUGH})
n_gray.input_source = n_src          # 显式绑定成"节点：图片源"（用户就是这么设的）
n_gray.params["gray_full_image"] = True
w.add_edge(n_src, n_gray)
w.add_edge(n_gray, n_bin)
w.add_edge(n_inv, n_edge)

w._show_static_image(LENA)           # 模拟"用户先导入了一张 lena 到图库"

# ============ 问题1：双击处理节点 → 窗口点执行 → 必须处理"图片源"那张图 ============
w.result_cache.clear()
dlg_gray = m.GenericProcessDialog(w.main_window, node=n_gray, main_window=w)
warnings[:] = []
dlg_gray.on_step_click()
check("问题1 窗口点'执行'：没有弹提示", warnings == [], warnings)
check("问题1 处理的是图片源那张（897×708），不是图库那张（512×512）",
      cached_shapes() == [(708, 897, 3)], cached_shapes())
check("问题1 日志里 灰度 的'图像源'列 = 节点：图片源（单步：只跑本节点）",
      any(n == "灰度" and "节点：图片源" in s for n, s in log_rows()), log_rows())
check("问题1 图库那张图没有被污染（current_static_image 还是 lena）",
      w.current_static_image is LENA, None if w.current_static_image is None else w.current_static_image.shape)

# ============ 问题2：ROI 默认值必须取"上游整图"的尺寸 ============
check("问题2 灰度窗口的 ROI 默认宽高 = 上游图片源那张图的尺寸（897×708）",
      dlg_gray.spin_roi_w.value() == 897 and dlg_gray.spin_roi_h.value() == 708,
      (dlg_gray.spin_roi_w.value(), dlg_gray.spin_roi_h.value()))
dlg_bin = m.GenericProcessDialog(w.main_window, node=n_bin, main_window=w)
check("问题2 二值化（上游是灰度→图片源）也追到同一张上游图",
      dlg_bin.spin_roi_w.value() == 897 and dlg_bin.spin_roi_h.value() == 708,
      (dlg_bin.spin_roi_w.value(), dlg_bin.spin_roi_h.value()))
dlg_inv = m.GenericProcessDialog(w.main_window, node=n_inv, main_window=w)
check("问题2 吃'全局图像源'的节点（取反）：ROI 默认值仍是主窗口当前图（512×512）",
      dlg_inv.spin_roi_w.value() == 512 and dlg_inv.spin_roi_h.value() == 512,
      (dlg_inv.spin_roi_w.value(), dlg_inv.spin_roi_h.value()))

# ============ 问题3：图片源不该画黄框、也不该留 ROI 参数 ============
spec_src = m.get_spec("图片源")
_out, _res, roi_info, _spec = w._execute_node(n_src, LENA, None)
check("问题3 起点节点的有效 ROI = 它自己输出的整张图（897×708），且标记为不画",
      roi_info[2] == 897 and roi_info[3] == 708 and roi_info[4] is True, roi_info)
disp = w._render_display(np.zeros((30, 30, 3), dtype=np.uint8), [(n_src, [], roi_info, spec_src)])
check("问题3 渲染起点节点时不会画任何 ROI 框（没有黄/洋红像素）",
      int(((disp == (0, 255, 255)).all(axis=2)).sum()) == 0
      and int(((disp == (255, 0, 255)).all(axis=2)).sum()) == 0)
n_src.params.update({"roi_x": 5, "roi_y": 5, "roi_w": 512, "roi_h": 512, "roi_shape": "矩形"})
_out2, _res2, roi_info2, _spec2 = w._execute_node(n_src, LENA, None)
check("问题3 就算方案里留着旧的 roi_w=512，起点节点也按整图算、不画框",
      roi_info2[2] == 897 and roi_info2[3] == 708 and roi_info2[4] is True, roi_info2)
dlg_src = m.GenericProcessDialog(w.main_window, node=n_src, main_window=w)
dlg_src._update_params()
check("问题3 起点节点的窗口不再把 ROI 参数写进 node.params",
      not any(k in n_src.params for k in ("roi_x", "roi_y", "roi_w", "roi_h", "hide_roi")),
      sorted(k for k in n_src.params if k.startswith("roi")))
check("问题3 起点节点特有的参数（来源/路径）仍然在",
      n_src.params.get("source_type") in ("图片", "单张图片")
      and n_src.params.get("source_path") == P_HOUGH)

# ============ 问题4：换了图片源的文件 → 单步执行必须用新图 ============
n_src.params["source_path"] = P_LENA
w.result_cache.clear()
w.selected_node = n_gray
warnings[:] = []
w.btn_step.click()
check("问题4 换成 lena.png 后单步执行：处理的是 512×512",
      cached_shapes() == [(512, 512, 3)], cached_shapes())
n_src.params["source_path"] = P_HOUGH
w.result_cache.clear()
warnings[:] = []
w.btn_step.click()
check("问题4 再换回 HoughLines.jpg 后单步执行：处理的是 897×708（没有用缓存的旧图）",
      cached_shapes() == [(708, 897, 3)], cached_shapes())
check("问题4 图库那张图始终没被改写", w.current_static_image is LENA)

# ============ 问题5：单步 / 连续 逻辑一致，且各自按绑定取图 ============
# 注意（2026.10.7 深夜·目标5-M1 起）：连续执行 = "**选中节点 + 它的全部上游**"（决策 e）——
# 以前是"按拓扑序截到选中节点为止的前缀"，那会把**与选中节点无关的并列链**也跑掉
# （本页的 取反→边缘提取 就是那条无关链）。所以下面的断言跟着改成"无关链不执行"。
w.result_cache.clear()
w.selected_node = n_gray
w.btn_continuous.click()
check("问题5 连续执行（底图=灰度）：处理的是图片源那张 897×708",
      cached_shapes() == [(708, 897, 3)], cached_shapes())
rows5 = log_rows()
check("问题5 连续执行：灰度=节点：图片源（按绑定取图）",
      ("灰度", "节点：图片源") in rows5, rows5)
check("问题5 改后：与选中节点**无关**的那条并列链（取反→边缘提取）本次不执行",
      ("取反", "全局图像源") not in rows5 and ("边缘提取", "节点：取反") not in rows5, rows5)
check("问题5 选中「灰度」时，它后面的节点本次不执行（执行范围是它 + 它的上游）",
      ("二值化", "节点：灰度") not in rows5 and ("边缘提取", "节点：取反") not in rows5
      and ("提示", "-") in rows5, rows5)

# 选中"拓扑序最后一个节点"（本页 = 二值化）⇒ 只跑**它和它的上游**（图片源→灰度→二值化），
# 另一条并列链（取反→边缘提取）不跑 —— 这正是决策 e 要的效果
# （"最后一个节点"由拓扑序决定，直接问引擎要，别写死）
_order, _parents, _skipped = w._build_execution_order(w.flow_nodes, w.flow_edges)
w.selected_node = _order[-1]
w.btn_continuous.click()
rows5 = log_rows()
check("问题5 选中拓扑序最后一个节点 ⇒ 只跑它和它的上游（二值化=节点：灰度），"
      "并列的另一条链（取反 / 边缘提取）不执行",
      ("二值化", "节点：灰度") in rows5
      and ("取反", "全局图像源") not in rows5 and ("边缘提取", "节点：取反") not in rows5, rows5)

# 把"当前图"换成蓝色小图，验证吃全局图像源的那条链确实跟着当前图走
w._show_static_image(BLUE)
w.result_cache.clear()
w.selected_node = n_inv
w.btn_continuous.click()
check("问题5 当前图换成 300×200 后：吃全局图像源的链输出 300×200",
      cached_shapes() == [(200, 300, 3)], cached_shapes())
w.result_cache.clear()
w.selected_node = n_gray
w.btn_continuous.click()
check("问题5 同一次执行里，绑图片源的那条链仍是 897×708（两条来源并存、互不影响）",
      cached_shapes() == [(708, 897, 3)], cached_shapes())

# 单步 / 连续 结果一致
step_shapes = cached_shapes()
w.result_cache.clear()
w.selected_node = n_bin
warnings[:] = []
w.btn_step.click()
check("问题5 单步执行 二值化：只跑这一个节点，输出尺寸仍是 897×708",
      cached_shapes() == step_shapes == [(708, 897, 3)], (step_shapes, cached_shapes()))
rows_step = log_rows()
check("问题5 单步执行只记一行日志（只跑选中的那个节点，不跑上游）",
      len(rows_step) == 1 and rows_step[0][0] == "二值化", rows_step)

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
