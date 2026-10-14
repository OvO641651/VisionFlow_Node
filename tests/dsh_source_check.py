# -*- coding: utf-8 -*-
"""批次4 目标3 第一版（图片源节点）验证脚本，跑完即删"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2 import QtWidgets
from PySide2.QtWidgets import QApplication, QComboBox, QWidget
from PySide2.QtCore import QPointF

app = QApplication([])

import main as m
from core.NodeRegistry import KIND_SOURCE, get_spec

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


lena = cv2.imread(os.path.join("image", "lena.png"))
other = np.zeros((100, 100, 3), dtype=np.uint8)
other[:, :] = (255, 0, 0)          # 一张明显不同的 100x100 蓝图（模拟"主窗口当前图"）

w = m.MainWindow()
detector = w.detector
ROI = (0, 0, lena.shape[1], lena.shape[0])

# ===================== 1、注册表 与 树 =====================
spec = get_spec("图片源")
check("注册了'图片源'，kind = source", spec is not None and spec.kind == KIND_SOURCE,
      None if spec is None else spec.kind)
keys = [(p[0], p[2]) for p in (spec.param_specs or [])]
check("图片源的参数表 = source_type(combo) + source_path(file)",
      keys == [("source_type", "combo"), ("source_path", "file")], keys)
check("图片源属于'产出新图'那一类（modifies_image = True）", spec.modifies_image is True)
check("直线仍是检测类（modifies_image = False）", get_spec("直线识别").modifies_image is False)
check("灰度仍然是处理类", get_spec("灰度").kind == "process")
check("旧算子都还在", all(get_spec(n) is not None
                      for n in ("灰度", "取反", "滤波", "二值化", "形态学", "边缘提取", "直线识别", "圆识别")))

tree = w.main_window.findChild(QtWidgets.QTreeWidget, "tree")
groups = {}
leaves = []
for i in range(tree.topLevelItemCount()):
    top = tree.topLevelItem(i)
    children = [top.child(j).text(0) for j in range(top.childCount())]
    groups[top.text(0)] = children
    leaves.extend(children)
_known_collect = ["图片源", "视频源", "相机源", "输出图像"]
check("树里新开了'采集'分组，按顺序含 图片源 / 视频源 / 相机源 / 输出图像（允许以后再往后加）",
      [x for x in (groups.get("采集") or []) if x in _known_collect] == _known_collect,
      groups.get("采集"))
check("处理 / 检测识别 / 颜色处理 三组的叶子都对（2026.10.14：直线识别 / 圆识别 改名、颜色提取移到新组「颜色处理」、检测与识别合并成「检测识别」）",
      groups.get("处理") == ["灰度", "取反", "滤波", "二值化", "形态学", "边缘提取"]
      and groups.get("检测识别") == ["直线识别", "圆识别", "人脸识别"]
      and groups.get("颜色处理") == ["颜色提取"], groups)
check("树里每个叶子都已注册（识别类也实现之后，没有「未实现」的叶子了）",
      sorted([x for x in leaves if get_spec(x) is None]) == [],
      sorted([x for x in leaves if get_spec(x) is None]))

# ===================== 2、三条来源分支 =====================
out, results = spec.run(detector, lena, ROI, {"source_type": "当前图像"})
check("当前图像：返回的是**同一个对象**（零拷贝，可用 is 断言）", out is lena)
check("当前图像：结果里带来源说明、日志文案短",
      results and isinstance(results[0], dict) and spec.format_result(results) == "图片源：当前图像",
      spec.format_result(results))

path = os.path.join("image", "lena.png")
src_params = {"source_type": "单张图片", "source_path": path}
out1, res1 = spec.run(detector, other, ROI, src_params)
expect = cv2.imread(path)
check("单张图片：输出 = 该文件的内容（不是传进来的当前图）",
      np.array_equal(out1, expect) and out1.shape == expect.shape)
check("单张图片：第二次调用命中缓存（返回同一对象，不重新解码）",
      spec.run(detector, other, ROI, src_params)[0] is out1)
check("单张图片：日志里写出了文件名", spec.format_result(res1) == "图片源：lena.png",
      spec.format_result(res1))

out_test, res_test = spec.run(detector, other, ROI, {"source_type": "测试图"})
check("测试图：自动生成了一张（不是传进来的当前图）",
      out_test is not other and out_test.ndim == 3 and out_test.shape != other.shape,
      None if out_test is None else out_test.shape)
check("测试图：同样命中缓存", spec.run(detector, other, ROI, {"source_type": "测试图"})[0] is out_test)

out_bad, res_bad = spec.run(detector, other, ROI,
                            {"source_type": "单张图片", "source_path": "no/such/file.png"})
check("文件读不到：不崩、原样透传输入图", out_bad is other)
check("文件读不到：日志如实写失败原因", "读取失败" in spec.format_result(res_bad),
      spec.format_result(res_bad))
out_empty, res_empty = spec.run(detector, other, ROI, {"source_type": "单张图片", "source_path": ""})
check("路径为空：按合并后的语义 = 用当前图（原样透传）",
      out_empty is other and "当前图像" in spec.format_result(res_empty))
check("结果里放 dict 不会干扰下游 ROI 继承（result_bbox 只认 tuple/list）",
      m.result_bbox(res1) is None and m.result_bbox(res_test) is None)

# ===================== 3、引擎：与全局图像源并存 =====================
tabs = w.flow_page_mgr.tab_widget
tabs.setTabText(0, "图片源测试")
n_src = w.add_flow_node("图片源", QPointF(20, 20))
n_gray = w.add_flow_node("灰度", QPointF(20, 200))
n_inv = w.add_flow_node("取反", QPointF(300, 20))          # 不连图片源 → 应该吃"全局图像源"
n_bin = w.add_flow_node("二值化", QPointF(300, 200))       # 给 取反 接一个下游，让它成为一条独立的链
n_src.params.update({"source_type": "单张图片", "source_path": path})
n_gray.params["gray_full_image"] = True
w.add_edge(n_src, n_gray)
w.add_edge(n_inv, n_bin)

w.selected_node = n_gray          # 让显示底图 = 灰度节点的输出，便于断言
display, all_data, exec_info = w._run_flow_pipeline(other)
rows = {row[2]: row for row in exec_info}
check("引擎跑通两条链（图片源→灰度 / 取反→二值化，共 4 行日志）", len(exec_info) == 4, exec_info)
check("灰度这一行绑的是'节点：图片源'", rows.get("灰度") and rows["灰度"][3] == "节点：图片源",
      None if "灰度" not in rows else rows["灰度"][3])
check("取反这一行仍然绑'全局图像源'（并存，各走各的）",
      rows.get("取反") and rows["取反"][3] == "全局图像源",
      None if "取反" not in rows else rows["取反"][3])
check("二值化这一行绑的是'节点：取反'",
      rows.get("二值化") and rows["二值化"][3] == "节点：取反",
      None if "二值化" not in rows else rows["二值化"][3])
check("图片源这一行的结果文案写了文件名",
      rows.get("图片源") and "lena.png" in str(rows["图片源"][4]),
      None if "图片源" not in rows else rows["图片源"][4])
check("显示图来自图片源那张（尺寸 = lena，而不是 100x100 的当前图）",
      display.shape == lena.shape, display.shape)
check("传进去的当前图没被改动", np.array_equal(other, np.full((100, 100, 3), (255, 0, 0), dtype=np.uint8)))

# 来源选"当前图像"时应该回归老行为（就是传进来的那张）
n_src.params["source_type"] = "当前图像"
display2, _d2, exec2 = w._run_flow_pipeline(other)
rows2 = {row[2]: row for row in exec2}
check("把来源改回'当前图像'：灰度这一行吃的还是'节点：图片源'，但输出回到当前图尺寸",
      display2.shape == other.shape and rows2["灰度"][4].startswith("执行成功"), display2.shape)

# ===================== 4、参数窗口：只留"运行参数"页 =====================
node = w.add_flow_node("图片源", QPointF(600, 20))
dlg = m.GenericProcessDialog(w.main_window, node=node, main_window=w)
titles = [dlg.ui.tabWidget.tabText(i) for i in range(dlg.ui.tabWidget.count())]
check("图片源窗口只剩 1 页，且是'运行参数'", titles == ["运行参数"], titles)
check("控件就是 来源 与 路径 两个", sorted(dlg.param_controls) == ["source_path", "source_type"],
      sorted(dlg.param_controls))
check("来源是下拉、路径是 file 控件（带 .edit）",
      isinstance(dlg.param_controls["source_type"], QComboBox)
      and isinstance(dlg.param_controls["source_path"], QWidget)
      and hasattr(dlg.param_controls["source_path"], "edit"))
dlg.param_controls["source_type"].setCurrentText("图片")
dlg.param_controls["source_path"].edit.setText(path)
dlg._update_params()
check("窗口里选的值写进了 node.params",
      node.params.get("source_type") == "图片" and node.params.get("source_path") == path,
      (node.params.get("source_type"), node.params.get("source_path")))
check("没有混进直线那些参数",
      all(k not in node.params for k in ("canny_low", "canny_high", "hough_threshold",
                                         "min_line_length", "max_line_gap")))
dlg2 = m.GenericProcessDialog(w.main_window, node=node, main_window=w)
check("重开窗口能读回来源与路径",
      dlg2.param_controls["source_type"].currentText() == "图片"
      and dlg2.param_controls["source_path"].edit.text() == path)
check("图片源的参数会进方案文件结构",
      any(item["name"] == "图片源" and "source_path" in item["params"]
          for item in w._collect_project()["pages"][0]["nodes"]))

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
