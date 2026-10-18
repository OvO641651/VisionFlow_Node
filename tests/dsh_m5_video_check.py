# -*- coding: utf-8 -*-
"""
批次4 目标3-M5-2「输出图像：视频 / 摄像头保存为视频文件」验证（2026.10.7）

按用户拍板的口径（"全按推荐"）：
  · 「输出类型」= 自动（图片源 ⇒ 图片序列；视频源 / 相机源 ⇒ 视频文件）/ 图片序列 / 视频文件
  · 「视频格式」= MP4(mp4v)【默认】/ AVI(XVID) / AVI(MJPG)；不做 H.264
  · 帧率 = "每写一帧算一帧"，标称取 参数手填 > 来源帧率 > 25
  · 生命周期 = 第一次执行到输出节点自动开始录制；「停止」/ 播到末尾 / 换页 / 删节点 / 关程序 / 关相机 收尾
  · 尺寸变化 或 输出参数改了 ⇒ 收尾旧文件 + 另开一个新文件
  · 「保存内容」同样适用（数据层图像 / 带检测叠加，默认叠加）

覆盖 ①~⑫（见各 check 名字）
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
from core.Detector import make_test_image


class FakeMB(object):
    warning = information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB
m.QFileDialog = type("F", (), {"getOpenFileNames": staticmethod(lambda *a, **k: ([], "")),
                               "getOpenFileName": staticmethod(lambda *a, **k: ("", "")),
                               "getSaveFileName": staticmethod(lambda *a, **k: ("", "")),
                               "getExistingDirectory": staticmethod(lambda *a, **k: "")})

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


TMP = tempfile.mkdtemp(prefix="vf_m5v_")

# 真·VideoCapture 的引用：用例⑨ 会把 cv2.VideoCapture 换成假相机，
# 读回产物的辅助函数必须一直用真的那个（否则会拿假相机去读文件、报 int 转换错）。
REAL_CAP = cv2.VideoCapture


def fresh_dir(name):
    d = os.path.join(TMP, name)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    return d


def read_video(path):
    """读回一个视频：返回 (帧数, [每帧均值], fps)。"""
    cap = REAL_CAP(path)
    if not cap.isOpened():
        return -1, [], 0.0
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(fr)
    cap.release()
    return len(frames), [float(f.mean()) for f in frames], fps


def read_first_frame(path):
    cap = REAL_CAP(path)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def count_pixels(img, color, tol=10):
    diff = np.abs(img.astype(int) - np.array(color, int))
    return int(np.all(diff <= tol, axis=2).sum())


# 造一段 10 帧的测试视频（每帧灰度不同，方便逐帧核对）
VID_DIR = fresh_dir("srcvideo")
SRC_VIDEO = os.path.join(VID_DIR, "src.avi")
VW = cv2.VideoWriter(SRC_VIDEO, cv2.VideoWriter_fourcc(*"MJPG"), 25.0, (64, 48))
for _i in range(10):
    VW.write(np.full((48, 64, 3), _i * 20, np.uint8))
VW.release()

GREY = make_test_image()
GREEN = (0, 255, 0)


def build_video_chain(out_dir, save_content=None, output_kind=None, video_format=None,
                      video_fps=None, name="rec"):
    """图片源 → 视频源？不：这里搭 [视频源|图片源] → 输出图像，返回 (window, 输出节点)"""
    win = m.MainWindow()
    win.main_window.show()
    n_src = win.add_flow_node("视频源", QPointF(20, 20))
    n_out = win.add_flow_node("输出图像", QPointF(20, 180))
    win.add_edge(n_src, n_out)
    n_src.params["video_path"] = SRC_VIDEO
    n_out.params["output_dir"] = out_dir
    n_out.params["output_name"] = name
    if save_content is not None:
        n_out.params["save_content"] = save_content
    if output_kind is not None:
        n_out.params["output_kind"] = output_kind
    if video_format is not None:
        n_out.params["video_format"] = video_format
    if video_fps is not None:
        n_out.params["video_fps"] = video_fps
    win.selected_node = n_out            # 连续执行要跑到输出节点，就得选中它
    return win, n_src, n_out


def run_frames(win, times):
    """连点 times 次"连续执行"（视频源每执行一次前进一帧）"""
    for _ in range(times):
        win.btn_continuous.click()


# ----------------------------------------------------------------------
# ① 参数：多了 输出类型 / 视频格式 / 视频帧率，且默认值对
# ----------------------------------------------------------------------
spec = m.get_spec("输出图像")
names = [p[0] for p in spec.param_specs]
check("① 参数表含输出类型 / 图片格式 / 视频格式 / 视频帧率 / 保存内容",
      names == ["output_dir", "output_name", "output_kind", "output_format",
                "video_format", "video_fps", "save_content", "name_policy"], names)
kinds = {p[0]: p for p in spec.param_specs}
check("① 输出类型三档、默认「自动」",
      kinds["output_kind"][3]["options"] == [ops.KIND_AUTO, ops.KIND_IMAGES, ops.KIND_VIDEO]
      and kinds["output_kind"][3]["default"] == ops.KIND_AUTO, kinds["output_kind"][3])
check("① 视频格式三档、默认 MP4(mp4v)、且**不含 H.264**（本机缺 openh264 dll）",
      len(ops.VIDEO_FORMAT_NAMES) == 3 and "mp4v" in ops.VIDEO_FORMAT_NAMES[0]
      and all("H.264" not in n and "avc1" not in n for n in ops.VIDEO_FORMAT_NAMES),
      ops.VIDEO_FORMAT_NAMES)
check("① 视频帧率默认 0 = 跟来源", kinds["video_fps"][3]["default"] == 0.0,
      kinds["video_fps"][3]["default"])

# ----------------------------------------------------------------------
# ② 视频源 + 「自动」⇒ 存成**视频文件**，帧数 = 执行次数，逐帧内容对得上
# ----------------------------------------------------------------------
d2 = fresh_dir("auto_video")
w2, src2, out2 = build_video_chain(d2)
run_frames(w2, 4)
files2 = sorted(os.listdir(d2))
check("② 「自动」档 + 视频源 ⇒ 产出**视频文件**（不是一堆图片）",
      len(files2) == 1 and files2[0].endswith(".mp4"), files2)
w2._close_recordings("测试收尾")
n2, means2, fps2 = read_video(os.path.join(d2, files2[0]))
check("② 录制 4 帧 ⇒ 视频里正好 4 帧（收尾后能正常打开）", n2 == 4, n2)
check("② 逐帧内容对得上（视频源第 0~3 帧 = 灰度 0/20/40/60；视频是有损压缩，容差 4）",
      len(means2) == 4 and all(abs(a - b) < 4 for a, b in zip(means2, [0, 20, 40, 60]))
      and means2 == sorted(means2), means2)
check("② 标称帧率跟来源（视频源 25fps）", abs(fps2 - 25.0) < 1.0, fps2)

# ----------------------------------------------------------------------
# ③ 「保存内容」对视频同样生效：叠加 ⇒ 有绿线；数据层 ⇒ 没有
# ----------------------------------------------------------------------
d3 = fresh_dir("video_overlay")
w3 = m.MainWindow()
w3.main_window.show()
l3 = w3.add_flow_node("直线识别", QPointF(20, 20))
o3 = w3.add_flow_node("输出图像", QPointF(20, 180))
w3.add_edge(l3, o3)
o3.params["output_dir"] = d3
o3.params["output_name"] = "ov"
o3.params["output_kind"] = ops.KIND_VIDEO          # 图片输入也强制录成视频，方便核对叠加
w3.selected_node = o3
w3._show_static_image(GREY)
w3.btn_continuous.click()
check("③ 图片输入 + 主动选「视频文件」⇒ 也能录（单帧视频）",
      len(os.listdir(d3)) == 1 and os.listdir(d3)[0].endswith(".mp4"), os.listdir(d3))
w3._close_recordings("测试收尾")
_ovn, _ovm, _ovf = read_video(os.path.join(d3, sorted(os.listdir(d3))[0]))
frame_ov = read_first_frame(os.path.join(d3, sorted(os.listdir(d3))[0]))
check("③ 视频里那一帧是**带检测叠加**（有绿线）", count_pixels(frame_ov, GREEN) > 0,
      count_pixels(frame_ov, GREEN))

d3b = fresh_dir("video_layer")
w3b = m.MainWindow()
w3b.main_window.show()
l3b = w3b.add_flow_node("直线识别", QPointF(20, 20))
o3b = w3b.add_flow_node("输出图像", QPointF(20, 180))
w3b.add_edge(l3b, o3b)
o3b.params["output_dir"] = d3b
o3b.params["output_name"] = "layer"
o3b.params["output_kind"] = ops.KIND_VIDEO
o3b.params["save_content"] = ops.SAVE_LAYER
w3b.selected_node = o3b
w3b._show_static_image(GREY)
w3b.btn_continuous.click()
w3b._close_recordings("测试收尾")
frame_l = read_first_frame(os.path.join(d3b, sorted(os.listdir(d3b))[0]))
check("③ 选「数据层图像」⇒ 视频里那一帧没有绿线（只有原图）", count_pixels(frame_l, GREEN) == 0,
      count_pixels(frame_l, GREEN))

# ----------------------------------------------------------------------
# ④ 尺寸变化 ⇒ 收尾旧文件 + 另开一个新文件
# ----------------------------------------------------------------------
d4 = fresh_dir("resize")
w4 = m.MainWindow()
w4.main_window.show()
i4 = w4.add_flow_node("取反", QPointF(20, 20))
o4 = w4.add_flow_node("输出图像", QPointF(20, 180))
w4.add_edge(i4, o4)
o4.params["output_dir"] = d4
o4.params["output_name"] = "size"
o4.params["output_kind"] = ops.KIND_VIDEO
w4.selected_node = o4
w4._show_static_image(np.full((48, 64, 3), 30, np.uint8))
w4.btn_continuous.click()
w4._show_static_image(np.full((24, 32, 3), 30, np.uint8))     # 尺寸变了
w4.btn_continuous.click()
w4._close_recordings("测试收尾")
files4 = sorted(os.listdir(d4))
check("④ 尺寸变化 ⇒ 得到**两个**视频文件（旧的先收尾、另开新的）", len(files4) == 2, files4)
ok4 = True
for f in files4:
    cnt, _means, _fps = read_video(os.path.join(d4, f))
    ok4 = ok4 and cnt == 1
check("④ 两个文件都能正常打开（各 1 帧）⇒ 证明旧文件确实 release 了", ok4, files4)

# ----------------------------------------------------------------------
# ⑤ 视频源 + 主动选「图片序列」⇒ 每帧存一张图（保留这个组合）
# ----------------------------------------------------------------------
d5 = fresh_dir("images_from_video")
w5, _s5, _o5 = build_video_chain(d5, output_kind=ops.KIND_IMAGES, name="frame")
run_frames(w5, 3)
files5 = sorted(os.listdir(d5))
check("⑤ 视频输入 + 主动选「图片序列」⇒ 每帧存一张图（组合保留）",
      len(files5) == 3 and all(f.endswith(".png") for f in files5), files5)

# ----------------------------------------------------------------------
# ⑥ 编码器不支持 ⇒ 日志写"保存失败"、不弹窗、图像照旧透传
# ----------------------------------------------------------------------
d6 = fresh_dir("badcodec")
real_writer = cv2.VideoWriter


class BadWriter(object):
    def __init__(self, *a, **k):
        pass

    def isOpened(self):
        return False

    def release(self):
        pass

    def write(self, frame):
        pass


cv2.VideoWriter = BadWriter
w6, _s6, _o6 = build_video_chain(d6)
run_frames(w6, 1)
cv2.VideoWriter = real_writer
texts6 = [w6.execution_log.item(r, 4).text() for r in range(w6.execution_log.rowCount())
          if w6.execution_log.item(r, 4)]
check("⑥ 编码器不支持 ⇒ 日志写「保存失败：不支持该视频格式」", 
      any("不支持该视频格式" in t for t in texts6), texts6)
check("⑥ 这种情况不生成文件、也不抛异常", os.listdir(d6) == [], os.listdir(d6))
check("⑥ 输出节点原样透传（下游/画面照旧）", _o6 is not None)

# ----------------------------------------------------------------------
# ⑦ 「停止」= 收尾录制（一帧一帧点着录的场景）
# ----------------------------------------------------------------------
d7 = fresh_dir("stop")
w7, _s7, _o7 = build_video_chain(d7, name="stoprec")
run_frames(w7, 3)
check("⑦ 录制中：文件已经在磁盘上（还没收尾）", len(os.listdir(d7)) == 1, os.listdir(d7))
w7.gallery_widget.stop_button.click()          # 工具栏「停止」
files7 = sorted(os.listdir(d7))
n7, _m7, _f7 = read_video(os.path.join(d7, files7[0]))
check("⑦ 点「停止」⇒ 录制收尾，文件可正常打开且帧数 = 3", n7 == 3, n7)
texts7 = [w7.execution_log.item(r, 4).text() for r in range(w7.execution_log.rowCount())
          if w7.execution_log.item(r, 4)]
check("⑦ 日志写「录制结束…共 3 帧」", any("录制结束" in t and "共 3 帧" in t for t in texts7),
      texts7[-2:])
check("⑦ 停止之后再点执行会**另开一个文件**（旧文件已收尾）",
      (w7.btn_continuous.click() or len(os.listdir(d7)) == 2), os.listdir(d7))

# ----------------------------------------------------------------------
# ⑧ 手填帧率优先于来源帧率
# ----------------------------------------------------------------------
d8 = fresh_dir("fps")
w8, _s8, _o8 = build_video_chain(d8, video_fps=10.0, name="fps10")
run_frames(w8, 2)
w8._close_recordings("测试收尾")
_n8, _m8, fps8 = read_video(os.path.join(d8, sorted(os.listdir(d8))[0]))
check("⑧ 手填 10fps ⇒ 产物标称帧率 = 10（手填优先于来源 25）", abs(fps8 - 10.0) < 1.0, fps8)

# ----------------------------------------------------------------------
# ⑨ 相机源 + 「自动」⇒ 也存成视频文件（帧率兜 30）
# ----------------------------------------------------------------------
opened_caps = []


class FakeCapture(object):
    def __init__(self, index=0):
        self._open = True
        opened_caps.append(int(index))

    def isOpened(self):
        return self._open

    def read(self):
        return True, np.full((48, 64, 3), 90, np.uint8)

    def get(self, prop):
        return 0.0            # 相机帧率读不到 ⇒ 应该兜 30

    def release(self):
        self._open = False


real_capture = cv2.VideoCapture
cv2.VideoCapture = FakeCapture
d9 = fresh_dir("camera")
w9 = m.MainWindow()
w9.main_window.show()
c9 = w9.add_flow_node("相机源", QPointF(20, 20))
o9 = w9.add_flow_node("输出图像", QPointF(20, 180))
w9.add_edge(c9, o9)
o9.params["output_dir"] = d9
o9.params["output_name"] = "cam"
w9.selected_node = o9
run_frames(w9, 3)
files9 = sorted(os.listdir(d9))
check("⑨ 相机源 + 「自动」⇒ 存成视频文件", len(files9) == 1 and files9[0].endswith(".mp4"),
      files9)
w9._close_recordings("测试收尾")
n9, _m9, fps9 = read_video(os.path.join(d9, files9[0]))
check("⑨ 相机录 3 帧 ⇒ 视频 3 帧", n9 == 3, n9)
check("⑨ 相机帧率读不到 ⇒ 兜 30", abs(fps9 - 30.0) < 1.0, fps9)
w9.close_camera()
cv2.VideoCapture = real_capture
check("⑨ 关相机会自动收尾录制（不再是录制中）", ops.recording_count() == 0, ops.recording_count())

# ----------------------------------------------------------------------
# ⑩ 没填输出目录 ⇒ 不录、只写日志（与图片一致的口径）
# ----------------------------------------------------------------------
d10 = fresh_dir("nodir")
w10 = m.MainWindow()
w10.main_window.show()
s10 = w10.add_flow_node("视频源", QPointF(20, 20))
o10 = w10.add_flow_node("输出图像", QPointF(20, 180))
w10.add_edge(s10, o10)
s10.params["video_path"] = SRC_VIDEO        # video_path 是"视频源"节点的参数
o10.params["output_dir"] = ""               # 输出目录留空（这个节点自己的参数）
w10.selected_node = o10
w10.btn_continuous.click()
texts10 = [w10.execution_log.item(r, 4).text() for r in range(w10.execution_log.rowCount())
           if w10.execution_log.item(r, 4)]
check("⑩ 没填输出目录 ⇒ 日志写「未设置输出目录」，不生成文件",
      any("未设置输出目录" in t for t in texts10)
      and ops.recording_count() == 0, texts10)

# ----------------------------------------------------------------------
# ⑪ 关程序 / 换页 / 删节点 也会收尾
# ----------------------------------------------------------------------
d11 = fresh_dir("hooks")
w11, _s11, o11 = build_video_chain(d11, name="hook")
run_frames(w11, 2)
check("⑪ 前置：正在录制 1 个文件", ops.recording_count() == 1, ops.recording_count())
w11.delete_flow_node(o11)
check("⑪ 删掉输出节点 ⇒ 录制立即收尾", ops.recording_count() == 0, ops.recording_count())
n11, _m11, _f11 = read_video(os.path.join(d11, sorted(os.listdir(d11))[0]))
check("⑪ 收尾后文件可正常打开（2 帧）", n11 == 2, n11)

d11b = fresh_dir("hooks2")
w11b, _s11b, _o11b = build_video_chain(d11b, name="hook2")
run_frames(w11b, 2)
w11b.close_event(type("E", (), {"accept": lambda self: None})())
check("⑪ 关窗口 ⇒ 录制立即收尾", ops.recording_count() == 0, ops.recording_count())

# ----------------------------------------------------------------------
# ⑫ 图片源 + 「自动」⇒ 仍然是图片序列（不回归）
# ----------------------------------------------------------------------
d12 = fresh_dir("image_auto")
w12 = m.MainWindow()
w12.main_window.show()
g12 = w12.add_flow_node("取反", QPointF(20, 20))
o12 = w12.add_flow_node("输出图像", QPointF(20, 180))
w12.add_edge(g12, o12)
o12.params["output_dir"] = d12
o12.params["output_name"] = "still"
w12.selected_node = o12
w12._show_static_image(np.full((48, 64, 3), 40, np.uint8))
w12.btn_continuous.click()
files12 = sorted(os.listdir(d12))
check("⑫ 图片源 + 「自动」⇒ 仍存成图片（不回归）",
      len(files12) == 1 and files12[0].endswith(".png"), files12)
check("⑫ 没在录制任何视频", ops.recording_count() == 0, ops.recording_count())

shutil.rmtree(TMP, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
