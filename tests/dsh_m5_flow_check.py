# -*- coding: utf-8 -*-
"""
批次4 目标3-M5「输出图像」验证（二）：接进流程 + 参数归档 + 方案往返 + 界面（2026.10.7）

覆盖：
  ① 放流程**末尾**：连续执行 ⇒ 存的是**处理后的数据层图像**（不是原图、也不是显示层叠加图）
     —— 与 spy 到的 `_render_display` 底图逐像素一致
  ② 放流程**中间**：它原样透传 ⇒ 下游节点结果与"不插这个节点"时**逐像素相等**
  ③ 参数**不按图片归档**：切两张图之后"输出目录 / 文件名"仍在
     （对照组：同一页的处理类节点"二值化"的阈值**会被清空** ⇒ 证明这套机制确实在跑）
  ④ `.vfproj` 保存 → 加载往返 ⇒ 输出目录 / 文件名 / 重名策略都还在
  ⑤ 单步执行选中"输出图像" ⇒ 按既有语义存的是**起点原图**（用户 2026.10.7 拍板的口径）
  ⑥ 执行日志"结果数据"列写"已保存 …"；输出图像**不进图库**
"""
import os
import shutil
import sys
import tempfile

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ops.sink.OutputOps as ops


class FakeMB(object):
    warning = information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB

SAVE_PATH = [""]


class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
    getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
    getSaveFileName = staticmethod(lambda *a, **k: (SAVE_PATH[0], ""))
    getExistingDirectory = staticmethod(lambda *a, **k: "")


m.QFileDialog = FakeFD

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


TMP = tempfile.mkdtemp(prefix="vf_m5b_")


def fresh_dir(name):
    d = os.path.join(TMP, name)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    return d


def make_img(value=40):
    return np.full((48, 64, 3), value, np.uint8)


def load_first(path):
    files = sorted(os.listdir(path))
    return (files[0], cv2.imread(os.path.join(path, files[0]))) if files else (None, None)


def new_window():
    """新建窗口 + 截住渲染层底图（哪张图进了 _render_display）"""
    win = m.MainWindow()
    win.main_window.show()
    win.rendered = []
    orig = win._render_display

    def spy(base_img, executed, draw_roi=True):
        win.rendered.append(None if base_img is None else base_img.copy())
        return orig(base_img, executed, draw_roi=draw_roi)

    win._render_display = spy
    return win


def log_texts(win, col=4):
    out = []
    for r in range(win.execution_log.rowCount()):
        item = win.execution_log.item(r, col)
        if item is not None:
            out.append(item.text())
    return out


# ----------------------------------------------------------------------
# ① 放末尾：存的是处理后的数据层图像
# ----------------------------------------------------------------------
d1 = fresh_dir("tail")
w = new_window()
n_inv = w.add_flow_node("取反", QPointF(20, 20))
n_out = w.add_flow_node("输出图像", QPointF(20, 180))
w.add_edge(n_inv, n_out)
n_out.params["output_dir"] = d1
n_out.params["output_name"] = "chain"
w.selected_node = n_out
w._show_static_image(make_img(40))
w.btn_continuous.click()

name1, saved1 = load_first(d1)
check("① 流程末尾：文件写出来了", saved1 is not None, os.listdir(d1))
check("① 存的是**处理后的**图（255-40 = 215），不是原图 40",
      saved1 is not None and abs(float(np.mean(saved1)) - 215) < 1e-6 and
      abs(float(np.mean(saved1)) - 40) > 1, None if saved1 is None else float(np.mean(saved1)))
check("① 与渲染层底图**逐像素一致**（存数据层，不是屏幕上那张）",
      w.rendered and saved1 is not None and
      float(np.mean(np.abs(saved1.astype(int) - w.rendered[-1].astype(int)))) == 0.0,
      None if not w.rendered else float(np.mean(w.rendered[-1])))
check("⑥ 执行日志写「已保存 …」",
      any("已保存 chain_0001" in t for t in log_texts(w)), log_texts(w))
check("⑥ 输出图像**不进图库**（它不产图片、只是写文件）", w.gallery_widget.count() == 0,
      w.gallery_widget.count())

# ----------------------------------------------------------------------
# ② 放中间：下游结果与"不插这个节点"逐像素相等
# ----------------------------------------------------------------------
d2 = fresh_dir("mid")
wa = new_window()
a_inv = wa.add_flow_node("取反", QPointF(20, 20))
a_out = wa.add_flow_node("输出图像", QPointF(20, 180))
a_bin = wa.add_flow_node("二值化", QPointF(20, 340))
wa.add_edge(a_inv, a_out)
wa.add_edge(a_out, a_bin)
a_out.params["output_dir"] = d2
a_bin.params["thresh_value"] = 100
a_bin.params["thresh_mode"] = "固定阈值"
wa.selected_node = a_bin
wa._show_static_image(make_img(40))
wa.btn_continuous.click()
mid_out = wa.rendered[-1].copy() if wa.rendered[-1] is not None else None
check("② 中间那个输出节点也把文件存下来了", len(os.listdir(d2)) == 1, os.listdir(d2))

wb = new_window()
b_inv = wb.add_flow_node("取反", QPointF(20, 20))
b_bin = wb.add_flow_node("二值化", QPointF(20, 340))
wb.add_edge(b_inv, b_bin)
b_bin.params["thresh_value"] = 100
b_bin.params["thresh_mode"] = "固定阈值"
wb.selected_node = b_bin
wb._show_static_image(make_img(40))
wb.btn_continuous.click()
plain_out = wb.rendered[-1].copy() if wb.rendered[-1] is not None else None

check("② 插了输出节点之后，下游（二值化）结果**逐像素不变**",
      mid_out is not None and plain_out is not None and mid_out.shape == plain_out.shape and
      float(np.mean(np.abs(mid_out.astype(int) - plain_out.astype(int)))) == 0.0,
      (None if mid_out is None else float(np.mean(mid_out)),
       None if plain_out is None else float(np.mean(plain_out))))

# ----------------------------------------------------------------------
# ②′ 连续执行**截断到选中节点为止**（用户 2026.10.7 要求：只有选中"输出图像"或它后面的节点才保存）
# ----------------------------------------------------------------------
d_cut = fresh_dir("cut")
wc = new_window()
c1 = wc.add_flow_node("取反", QPointF(20, 20))
c2 = wc.add_flow_node("输出图像", QPointF(20, 180))
c3 = wc.add_flow_node("二值化", QPointF(20, 340))
wc.add_edge(c1, c2)
wc.add_edge(c2, c3)
c2.params["output_dir"] = d_cut
c2.params["output_name"] = "cut"
c3.params["thresh_value"] = 100
wc._show_static_image(make_img(40))

wc.selected_node = c1                      # 选中"取反"（输出图像**之前**）
wc.btn_continuous.click()
check("②′ 选中「输出图像」之前的节点 ⇒ **不保存**（用户实测报的 bug 回归）",
      os.listdir(d_cut) == [], os.listdir(d_cut))
check("②′ 日志如实说明截断到哪、哪些没执行",
      any("只跑「取反」和它的上游" in t and "输出图像" in t and "二值化" in t
          for t in log_texts(wc)), log_texts(wc))
check("②′ 被截掉的下游节点**真的没执行**（日志里没有它的模块行）",
      "二值化" not in log_texts(wc, 2) and "输出图像" not in log_texts(wc, 2),
      log_texts(wc, 2))

wc.selected_node = c2                      # 选中"输出图像"自己
wc.btn_continuous.click()
check("②′ 选中「输出图像」自己 ⇒ 保存", len(os.listdir(d_cut)) == 1, os.listdir(d_cut))

wc.selected_node = c3                      # 选中它**后面**的节点
wc.btn_continuous.click()
check("②′ 选中「输出图像」后面的节点 ⇒ 也保存（用户要求）",
      len(os.listdir(d_cut)) == 2, os.listdir(d_cut))
check("②′ 这时下游节点正常执行（日志里有二值化的行）",
      "二值化" in log_texts(wc, 2), log_texts(wc, 2))

# ----------------------------------------------------------------------
# ③ 参数不按图片归档（关键回归）
# ----------------------------------------------------------------------
w3 = new_window()
c_out = w3.add_flow_node("输出图像", QPointF(20, 20))
c_bin = w3.add_flow_node("二值化", QPointF(20, 180))
c_out.params["output_dir"] = d2
c_out.params["output_name"] = "keepme"
c_out.params["name_policy"] = ops.POLICY_TIME
c_bin.params["thresh_value"] = 111

img_a = make_img(20)
img_b = make_img(200)
w3._show_static_image(img_a)          # 第一次：把 A 设成当前图（还没有归档动作）
w3._show_static_image(img_b)          # 切到 B：会把 A 那份存起来、再载入 B 的（B 没存过 ⇒ 清空）
check("③ 切图之后，输出目录**还在**（输出节点是流程级配置，不按图归档）",
      c_out.params.get("output_dir") == d2, c_out.params.get("output_dir"))
check("③ 输出文件名 / 重名策略也还在",
      c_out.params.get("output_name") == "keepme" and
      c_out.params.get("name_policy") == ops.POLICY_TIME,
      (c_out.params.get("output_name"), c_out.params.get("name_policy")))
check("③ 对照：同页处理类节点（二值化）的阈值**被清空了** ⇒ 证明这套归档机制确实在跑",
      c_bin.params.get("thresh_value") is None, c_bin.params.get("thresh_value"))

# ----------------------------------------------------------------------
# ④ .vfproj 往返
# ----------------------------------------------------------------------
proj_path = os.path.join(TMP, "dsh_m5.vfproj")
if os.path.exists(proj_path):
    os.remove(proj_path)
SAVE_PATH[0] = proj_path
w3.save_project()
check("④ 方案文件写出来了", os.path.exists(proj_path), proj_path)

w4 = new_window()
w4.load_project(proj_path)
loaded = [n for page in w4.flow_page_mgr.pages for n in page["nodes"] if n.name == "输出图像"]
check("④ 加载回来找得到「输出图像」节点", len(loaded) == 1, len(loaded))
if loaded:
    lp = loaded[0].params
    check("④ 往返之后输出目录 / 文件名 / 重名策略都还在",
          lp.get("output_dir") == d2 and lp.get("output_name") == "keepme" and
          lp.get("name_policy") == ops.POLICY_TIME,
          {k: lp.get(k) for k in ("output_dir", "output_name", "name_policy")})

# ----------------------------------------------------------------------
# ⑤ 单步执行选中"输出图像" ⇒ 存起点原图（用户拍板口径）
# ----------------------------------------------------------------------
d5 = fresh_dir("step")
w5 = new_window()
e_inv = w5.add_flow_node("取反", QPointF(20, 20))
e_out = w5.add_flow_node("输出图像", QPointF(20, 180))
w5.add_edge(e_inv, e_out)
e_out.params["output_dir"] = d5
e_out.params["output_name"] = "single"
w5._show_static_image(make_img(40))
w5.selected_node = e_out
w5.btn_step.click()
_, saved5 = load_first(d5)
check("⑤ 单步执行选中输出节点 ⇒ 存的是**起点原图**（40），不是上游取反后的 215",
      saved5 is not None and abs(float(np.mean(saved5)) - 40) < 1e-6,
      None if saved5 is None else float(np.mean(saved5)))
check("⑤ 日志的「图像源」列如实写「单步：只跑本节点」",
      any("单步：只跑本节点" in t for t in log_texts(w5, 3)), log_texts(w5, 3))
check("⑤ 日志的「结果数据」列写「已保存 single_0001」",
      any("已保存 single_0001" in t for t in log_texts(w5)), log_texts(w5))

shutil.rmtree(TMP, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
