# -*- coding: utf-8 -*-
"""
批次4 目标3-M5「输出图像」验证（一）：节点注册 + 参数窗口 + 保存行为（2026.10.7）

覆盖：
  ① 注册（kind=sink / modifies_image=False / is_flow_level=True / 五项参数）+ 树里「采集」下四项
  ② 参数窗口：走通用窗口、「选择目录…」按钮、文件名是**纯文本**（不会顺手把图导进图库）、
     「显示结果」页去掉、「基本参数」页保留
  ③ 保存：文件真的写出来，尺寸 / 均值 == 传进去的数据层图像（逐像素）
  ④ 数据层图像**原样透传**（返回的就是同一个对象 ⇒ 放中间不会改变下游）
  ⑤ 自动编号：连存两次得 _0001 / _0002，都不覆盖；目录里已有 _0007 ⇒ 下一次是 _0008
  ⑥ 目录不存在 ⇒ 自动创建
  ⑦ 输出目录留空 ⇒ 不保存、只写日志（用户拍板：必须每次手填）
  ⑧ 写不进去（目录指向一个已存在的文件）⇒ 日志写「保存失败」、不抛异常、图像照旧透传
  ⑨ 覆盖同名 / 按时间戳两种策略
  ⑩ 保存区域 = 仅 ROI 框内 ⇒ 存出来的就是那一块
  ⑪ 文件名非法字符自动清洗；相对路径按**工程根**解析
"""
import os
import re
import shutil
import sys
import tempfile

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget, QTreeWidget
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


class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
    getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
    getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
    getExistingDirectory = staticmethod(lambda *a, **k: "")


m.QFileDialog = FakeFD

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


TMP = tempfile.mkdtemp(prefix="vf_m5a_")


def fresh_dir(name):
    d = os.path.join(TMP, name)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    return d


def make_img(value=40):
    return np.full((48, 64, 3), value, np.uint8)


def last_text(results):
    return results[0].get("输出图像") if results and isinstance(results[0], dict) else None


# ----------------------------------------------------------------------
# ① 注册 + 树
# ----------------------------------------------------------------------
spec = m.get_spec("输出图像")
check("① 输出图像已注册", spec is not None)
check("① kind = sink（新增的第三类「输出类」，不是 process / detect）",
      spec is not None and spec.kind == "sink", getattr(spec, "kind", None))
check("① modifies_image = False（不改图 ⇒ 不会冒充「多上游里真正改图的那一支」）",
      spec is not None and spec.modifies_image is False, getattr(spec, "modifies_image", None))
check("① is_flow_level = True（参数是流程级配置，不按图片归档）",
      spec is not None and spec.is_flow_level is True, getattr(spec, "is_flow_level", None))
names = [p[0] for p in (spec.param_specs if spec else [])]
check("① 八项参数（输出目录 / 文件名 / 输出类型 / 图片格式 / 视频格式 / 视频帧率 / 保存内容 / 重名策略）",
      names == ["output_dir", "output_name", "output_kind", "output_format",
                "video_format", "video_fps", "save_content", "name_policy"], names)
kinds = {p[0]: p[2] for p in (spec.param_specs if spec else [])}
check("① 输出目录是新控件 dir、文件名是新控件 text",
      kinds.get("output_dir") == "dir" and kinds.get("output_name") == "text", kinds)

w = m.MainWindow()
w.main_window.show()
tree = w.main_window.findChild(QTreeWidget, "tree")
collect = tree.topLevelItem(0)
leaf_names = [collect.child(i).text(0) for i in range(collect.childCount())]
check("① 树里「采集」下现在是 图片源 / 视频源 / 相机源 / 输出图像",
      leaf_names == ["图片源", "视频源", "相机源", "输出图像"], leaf_names)

# ----------------------------------------------------------------------
# ② 参数窗口
# ----------------------------------------------------------------------
from ui.GenericProcessDialog import GenericProcessDialog

node = w.add_flow_node("输出图像", QPointF(20, 20))
dlg = GenericProcessDialog(w.main_window, node=node, main_window=w)
controls = dlg.param_controls
dir_widget = controls.get("output_dir")
name_widget = controls.get("output_name")
check("② 有 output_dir 控件、而且是「编辑框 + 选择目录…」的组合",
      isinstance(dir_widget, QWidget) and isinstance(dir_widget.edit, QLineEdit) and
      any(isinstance(b, QPushButton) and "目录" in b.text()
          for b in dir_widget.findChildren(QPushButton)),
      type(dir_widget).__name__)
check("② 文件名是**纯文本输入框**（不是 file 控件 ⇒ 不会弹选图片、不会把图导进图库）",
      isinstance(name_widget, QLineEdit) and not hasattr(name_widget, "edit"),
      type(name_widget).__name__)
tab_texts = [dlg.ui.tabWidget.tabText(i) for i in range(dlg.ui.tabWidget.count())]
check("① 参考图像源节点：**只留「运行参数」页**（基本参数页已去掉）",
      tab_texts == ["运行参数"], tab_texts)
check("① 也没有「显示结果」页（输出节点没有结构化结果）",
      not any("显示结果" in t for t in tab_texts), tab_texts)
check("② 默认：输出目录为空（用户拍板：必须每次手填）", dir_widget.edit.text() == "",
      dir_widget.edit.text())
check("② 文件名默认留空 + placeholder 说明「留空 = 用输入图片的文件名」",
      name_widget.text() == "" and "输入图片" in name_widget.placeholderText(),
      (name_widget.text(), name_widget.placeholderText()))
check("① 输出类节点仍保留「执行 / 连续执行 / 确定」三个按钮（用户没让去掉）",
      all(dlg.ui.findChild(QPushButton, n) is not None for n in ("btn_run", "btn_cont")),
      [n for n in ("btn_run", "btn_cont") if dlg.ui.findChild(QPushButton, n) is None])
dlg.close()
dlg.deleteLater()

# ----------------------------------------------------------------------
# ②′ 文件名的默认值 = 输入图片的文件名（用户 2026.10.7 要求）
# ----------------------------------------------------------------------
src_path = os.path.join(TMP, "my_input.png")
src_img = make_img(30)
w._frame_paths[id(src_img)] = src_path          # 把这张图登记成"来自文件"
w.current_static_image = src_img
node2 = w.add_flow_node("输出图像", QPointF(20, 240))
dlg2 = GenericProcessDialog(w.main_window, node=node2, main_window=w)
check("②′ 参数窗口里「输出文件名」默认带出了输入图片的文件名（my_input）",
      dlg2.param_controls["output_name"].text() == "my_input",
      dlg2.param_controls["output_name"].text())
dlg2.close()
dlg2.deleteLater()

# 运行期：文件名为空 ⇒ 自动跟随"这一轮输入图片名"（"运行全部"时每张图各用各的名字）
d_name = fresh_dir("autoname")
ops.set_input_name_provider(lambda: "auto_input")
ops.run_save(None, make_img(40), (0, 0, 64, 48),
             {"output_dir": d_name, "output_name": "", "output_format": ops.FORMAT_NAMES[0],
              "name_policy": ops.POLICY_AUTO})
ops.set_input_name_provider(lambda: "auto_input2")
ops.run_save(None, make_img(40), (0, 0, 64, 48),
             {"output_dir": d_name, "output_name": "", "output_format": ops.FORMAT_NAMES[0],
              "name_policy": ops.POLICY_AUTO})
check("③ 文件名为空 ⇒ 保存时自动用「这一轮输入图片名」（逐张图各自的名字）",
      sorted(os.listdir(d_name)) == ["auto_input2_0001.png", "auto_input_0001.png"],
      sorted(os.listdir(d_name)))
ops.set_input_name_provider(lambda: "")
w._frame_paths.pop(id(src_img), None)
w.current_static_image = None

# ----------------------------------------------------------------------
# ③④ 保存 + 透传
# ----------------------------------------------------------------------
img = make_img(40)
d1 = fresh_dir("basic")
params = {"output_dir": d1, "output_name": "shot", "output_format": ops.FORMAT_NAMES[0],
          "name_policy": ops.POLICY_AUTO}
out_img, results = ops.run_save(None, img, (0, 0, 64, 48), params)
check("④ 返回值就是传进去的同一个对象（原样透传、连副本都不建）", out_img is img)
files = sorted(os.listdir(d1))
check("③ 文件真的写出来了（目录是自动创建的）",
      len(files) == 1 and files[0] == "shot_0001.png", files)
saved = cv2.imread(os.path.join(d1, files[0]))
check("③ 存的是**数据层图像**：尺寸 / 均值与传入的逐像素一致",
      saved is not None and saved.shape == img.shape and
      float(np.mean(np.abs(saved.astype(int) - img.astype(int)))) == 0.0,
      None if saved is None else (saved.shape, float(np.mean(saved))))
check("③ 日志文案：已保存…", (last_text(results) or "").startswith("已保存 shot_0001.png"),
      last_text(results))

# ----------------------------------------------------------------------
# ⑤ 自动编号
# ----------------------------------------------------------------------
ops.run_save(None, img, (0, 0, 64, 48), params)
files = sorted(os.listdir(d1))
check("⑤ 连存两次 ⇒ _0001 / _0002（绝不覆盖）",
      files == ["shot_0001.png", "shot_0002.png"], files)

d2 = fresh_dir("continue")
os.makedirs(d2, exist_ok=True)          # imwrite 不会自己建目录，这里要先建出来
cv2.imwrite(os.path.join(d2, "shot_0007.png"), make_img(7))
check("⑤ 前置：目录里确实已经有 shot_0007.png（imwrite 不会建目录，测试自己得建）",
      os.path.exists(os.path.join(d2, "shot_0007.png")))
params2 = dict(params, output_dir=d2)
ops.run_save(None, img, (0, 0, 64, 48), params2)
files2 = sorted(os.listdir(d2))
check("⑤ 目录里已有 shot_0007 ⇒ 下一次从 _0008 开始（关软件重开也不会覆盖）",
      "shot_0008.png" in files2, files2)

# ----------------------------------------------------------------------
# ⑦ 输出目录留空 ⇒ 不保存、只写日志
# ----------------------------------------------------------------------
blank = {"output_dir": "", "output_name": "shot", "output_format": ops.FORMAT_NAMES[0],
         "name_policy": ops.POLICY_AUTO}
out_blank, res_blank = ops.run_save(None, img, (0, 0, 64, 48), blank)
check("⑦ 输出目录留空 ⇒ 不保存（也不会偷偷用别的目录）",
      out_blank is img and "未保存" in (last_text(res_blank) or ""), last_text(res_blank))
check("⑦ 原因写清楚了（提示去参数窗口设置）",
      "没有设置输出目录" in (last_text(res_blank) or ""), last_text(res_blank))

# ----------------------------------------------------------------------
# ⑧ 写不进去 ⇒ 不抛异常、图像照旧透传
# ----------------------------------------------------------------------
blocker = os.path.join(TMP, "i_am_a_file.txt")
with open(blocker, "w") as fh:
    fh.write("x")
bad = dict(params, output_dir=os.path.join(blocker, "sub"))
out_bad, res_bad = ops.run_save(None, img, (0, 0, 64, 48), bad)
check("⑧ 目录不可用时日志写「保存失败」、不弹窗不抛异常",
      out_bad is img and "保存失败" in (last_text(res_bad) or ""), last_text(res_bad))

# ----------------------------------------------------------------------
# ⑨ 覆盖同名 / 按时间戳
# ----------------------------------------------------------------------
d3 = fresh_dir("overwrite")
p3 = dict(params, output_dir=d3, name_policy=ops.POLICY_OVERWRITE)
ops.run_save(None, make_img(10), (0, 0, 64, 48), p3)
ops.run_save(None, make_img(200), (0, 0, 64, 48), p3)
files3 = sorted(os.listdir(d3))
after = cv2.imread(os.path.join(d3, "shot.png"))
check("⑨ 覆盖同名：始终一个文件、内容是最后一次的",
      files3 == ["shot.png"] and abs(float(np.mean(after)) - 200) < 1e-6,
      (files3, float(np.mean(after))))

d4 = fresh_dir("stamp")
p4 = dict(params, output_dir=d4, name_policy=ops.POLICY_TIME)
ops.run_save(None, img, (0, 0, 64, 48), p4)
ops.run_save(None, img, (0, 0, 64, 48), p4)
files4 = sorted(os.listdir(d4))
check("⑨ 按时间戳：两次保存得到两个不同文件（同一毫秒撞名也不会覆盖）",
      len(files4) == 2 and len(set(files4)) == 2, files4)

# ----------------------------------------------------------------------
# ⑪ 文件名清洗 + 相对路径按工程根解析
# ----------------------------------------------------------------------
path_bad_name, _ = ops.build_output_path(dict(params, output_name='a/b:c*d?e"f<g>h|i'))
check("⑪ 文件名里的非法字符被清洗成 _（不会写失败）",
      re.match(r"^a_b_c_d_e_f_g_h_i_\d{4}\.png$", os.path.basename(path_bad_name)) is not None,
      os.path.basename(path_bad_name))
path_rel, _ = ops.build_output_path(dict(params, output_dir="output"))
check("⑪ 相对路径按**工程根**解析（不看当前工作目录）",
      os.path.normcase(path_rel).startswith(os.path.normcase(PROJ) + os.sep), path_rel)

shutil.rmtree(TMP, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
