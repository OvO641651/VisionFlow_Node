# -*- coding: utf-8 -*-
"""
批次4 目标5-M2 验证⑤：**中文（非 ASCII）路径的图片读写**

用户 2026.10.12 实测报：打开 `E:\\OpenCV_python\\python_opencv\\OpenCV_Book\\data` 时日志刷出
    cv::findDecoder imread_('.../data\\所有数据按行排列结果.png'): can't open/read file
而 `image\\lena.png`（纯英文名）没事。

判据（改前 / 改后**在同一轮里对照**，因为根因就摆在眼前）：
    · `cv2.imread(中文路径)` == None（复现根因）而 `ImageIO.read_image(中文路径)` 读得出来；
    · `cv2.imwrite(中文路径)` == False（同一个根因）而 `ImageIO.write_image` 写得成、读得回、像素一致；
    · 契约不变：路径不存在 / 空路径 ⇒ 返回 None（不抛异常），调用方的 `if img is None` 不用改；
    · **端到端（用户实际路径）**：`w.import_folder_path(中文目录)` ⇒ 中文名图片真的进了图库；
      "输出图像"节点把文件保存到**中文目录 + 中文文件名** ⇒ 存得住、读得回（原来会判"保存失败"）；
    · 视频（`VideoCapture` / `VideoWriter`）中文路径本来就没问题，这里只钉一条"确实没问题"。
"""
import os
import shutil
import sys
import tempfile

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
USER_DIR = r"E:\OpenCV_python\python_opencv\OpenCV_Book\data"

os.chdir(PROJ)
sys.path.insert(0, PROJ)

import cv2
import numpy as np
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ops.sink.OutputOps as OutputOps
from core.ImageIO import read_image, write_image
from core.NodeRegistry import get_spec

fails = []


def check(name, cond, extra=None):
    text = '' if extra is None else '   <- ' + str(extra)
    print(('PASS  ' if cond else 'FAIL  ') + name + text)
    if not cond:
        fails.append(name)


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
m.QFileDialog = FakeFD

# 造一个"中文目录 + 中文文件名"的样本图
TMP = tempfile.mkdtemp(prefix="vf_cn_")
CN_DIR = os.path.join(TMP, "中文 目录")           # 顺便带上空格
os.makedirs(CN_DIR, exist_ok=True)
CN_PATH = os.path.join(CN_DIR, "所有数据按行排列结果.png")
img = np.zeros((60, 80, 3), np.uint8)
img[:, :40] = (0, 0, 255)                          # 左半红
img[:, 40:] = (255, 0, 0)                          # 右半蓝
check('前置：样本图写出来了（用字节流写，避免测试自己踩同一个坑）',
      write_image(CN_PATH, img) and os.path.exists(CN_PATH), CN_PATH)

# ======================================================================
# ① 根因与修法的对照（同一轮里就能看出区别）
# ======================================================================
check('① 复现根因：cv2.imread 读不了中文路径（返回 None）', cv2.imread(CN_PATH) is None)
got = read_image(CN_PATH)
check('① 修法：ImageIO.read_image 读得出来，且与写入的像素完全一致',
      got is not None and got.shape == img.shape and np.array_equal(got, img),
      None if got is None else got.shape)

CN_OUT = os.path.join(CN_DIR, "中文名输出.png")
check('① 复现根因：cv2.imwrite 写不了中文路径（返回 False）',
      cv2.imwrite(CN_OUT, img) is False)
if os.path.exists(CN_OUT):
    os.remove(CN_OUT)
check('① 修法：ImageIO.write_image 写得成', write_image(CN_OUT, img) is True
      and os.path.exists(CN_OUT), os.path.exists(CN_OUT))
back = read_image(CN_OUT)
check('① 写出来的文件读得回、像素一致（往返断言）',
      back is not None and np.array_equal(back, img), None if back is None else back.shape)

# ======================================================================
# ② 契约与 cv2 保持一致（调用方不用改判断）
# ======================================================================
check('② 路径不存在 ⇒ None（与 imread 一致，不抛异常）',
      read_image(os.path.join(CN_DIR, "没有这个文件.png")) is None)
check('② 空路径 ⇒ None', read_image("") is None and read_image(None) is None)
check('② 是目录而不是文件 ⇒ None（不抛）', read_image(CN_DIR) is None)
check('② 写空图 / 空路径 ⇒ False（与 imwrite 一致）',
      write_image(CN_OUT, None) is False and write_image("", img) is False)

# ======================================================================
# ③ 用户实际那个目录（存在就顺便验一下，算真实样本证据）
# ======================================================================
if os.path.isdir(USER_DIR):
    sample = os.path.join(USER_DIR, "所有数据按行排列结果.png")
    if os.path.exists(sample):
        real = read_image(sample)
        check('③ 用户报的那个中文名文件现在读得出来（真实样本）',
              real is not None and real.size > 0, None if real is None else real.shape)
    else:
        print('       （用户目录里没有那个文件，跳过这条真实样本断言）')

# ======================================================================
# ④ 端到端：走真实入口（打开文件夹导入 + 输出节点保存）
# ======================================================================
w = m.MainWindow()
w.main_window.show()
gallery_before = w.gallery_widget.count()
w.import_folder_path(CN_DIR)
app.processEvents()
check('④ 端到端：打开"中文名文件夹" ⇒ 中文名图片被导入图库（用户报的场景）',
      w.gallery_widget.count() > gallery_before,
      (gallery_before, w.gallery_widget.count()))

out_node = w.add_flow_node("输出图像", QPointF(20, 20))
out_node.params["output_dir"] = CN_DIR
out_node.params["output_name"] = "中文名输出_端到端"
out_node.params["output_kind"] = "图片"
out_node.params["save_content"] = "数据层图像"
out_node.params["name_policy"] = "自动编号"
w.current_static_image = img.copy()
w.selected_node = out_node
w.btn_step.click()
app.processEvents()
saved = [f for f in os.listdir(CN_DIR) if f.startswith("中文名输出_端到端")]
check('④ 端到端：输出节点保存到"中文目录 + 中文文件名"真的写出了文件（原来会"保存失败"）',
      len(saved) == 1, saved)
rows = []
for r in range(w.execution_log.rowCount()):
    item = w.execution_log.item(r, 4)
    if item is not None:
        rows.append(item.text())
check('④ 端到端：日志里没有"保存失败"（错误通道也没被点亮）',
      not any("保存失败" in t for t in rows), rows)
if saved:
    read_back = read_image(os.path.join(CN_DIR, saved[0]))
    check('④ 端到端：存出来的文件读得回、像素一致',
          read_back is not None and np.array_equal(read_back, img),
          None if read_back is None else read_back.shape)

# ======================================================================
# ⑤ 视频中文路径本来就正常（钉一条，免得以后误改）
# ======================================================================
vi_path = os.path.join(CN_DIR, "中文名视频.avi")
vw = cv2.VideoWriter(vi_path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
for i in range(4):
    vw.write(np.full((48, 64, 3), i * 50, np.uint8))
vw.release()
cap = cv2.VideoCapture(vi_path)
frames = 0
if cap.isOpened():
    while True:
        ok, _frame = cap.read()
        if not ok:
            break
        frames += 1
cap.release()
check('⑤ 视频中文路径：VideoWriter 写得成、VideoCapture 读得回（4 帧）',
      frames == 4, frames)

shutil.rmtree(TMP, ignore_errors=True)

print('-' * 70)
if fails:
    print('失败项：%d' % len(fails))
    for name in fails:
        print('   - ' + name)
else:
    print('失败项：无')
sys.exit(1 if fails else 0)
