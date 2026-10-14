# -*- coding: utf-8 -*-
"""
视频源（"采集"分组）—— **一个节点一个文件**（2026.10.14 批次5 目标1 从 `SourceOps.py` 拆出）。

设计（目标3-M3，2026.10.6 用户拍板）：
    · 帧**不进图库**（不占内存、不污染图片列表），每帧结果按 "视频路径#帧号" 单独缓存；
    · 参数**整段共用一份**（主窗口用视频槽 VIDEO_ROI_KEY），中途改参数后面的帧按新的跑；
    · VideoCapture **自己一个、带缓存**（与主窗口的视频播放各读各的，不抢读指针）；
    · run() 只**读**当前帧、**不前进**——"执行后前进一帧"由主窗口在**一次执行结束后**
      统一做一次（见 main.py::_advance_video_cursor），这样同一轮里多个节点取图共用同一帧。

`video_info()` 还给主窗口用（显示"第 N / 共 M 帧"、判断能不能播）。
"""
import os

import cv2

VIDEO_EXTS = ('.mp4', '.avi', '.mkv', '.mov')

# 视频解码缓存：{路径: {"key": (mtime, size), "cap": VideoCapture, "count": 帧数, "fps": 帧率}}
_VIDEO_CACHE = {}


def _open_video(path):
    """按 (路径, mtime, 大小) 缓存 VideoCapture；返回 (cap, 总帧数, 帧率)，打不开返回 (None, 0, 0.0)"""
    try:
        stat = os.stat(path)
    except OSError:
        return None, 0, 0.0
    key = (stat.st_mtime, stat.st_size)
    hit = _VIDEO_CACHE.get(path)
    if hit is not None and hit["key"] == key:
        return hit["cap"], hit["count"], hit["fps"]
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        cap.release()
        return None, 0, 0.0
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0 or fps > 240:      # 有些文件 fps 读出来是坏值，兜一个 25
        fps = 25.0
    _VIDEO_CACHE[path] = {"key": key, "cap": cap, "count": count, "fps": fps}
    return cap, count, fps


def video_info(path):
    """给主窗口用：返回 (总帧数, 帧率)；打不开返回 (0, 0.0)"""
    if not path:
        return 0, 0.0
    cap, count, fps = _open_video(path)
    return (count, fps) if cap is not None else (0, 0.0)


def run_video(detector, img, roi, params):
    """
    视频源：读"当前帧号"那一帧作为这一轮的图（**只读、不前进**）。

    读不到（文件没了 / 帧号越界 / 坏文件）：
        · loop 开着 ⇒ 回到第 0 帧再读一次；
        · 仍失败 ⇒ **原样透传输入图**并在结果里带一条说明（日志会写出来，绝不弹窗）。
    """
    path = params.get("video_path") or ""
    index = int(params.get("frame_index") or 0)
    if index < 0:
        index = 0
    results = []
    if not path:
        results.append({"视频源": "没有指定视频文件"})
        return img, results
    name = os.path.basename(path)
    cap, count, _fps = _open_video(path)
    if cap is None:
        results.append({"视频源": "打不开视频：{0}".format(name)})
        return img, results

    def _read(idx):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        return frame if ok else None

    frame = _read(index)
    if frame is None and params.get("loop"):
        frame = _read(0)
        index = 0
    if frame is None:
        results.append({"视频源": "{0}：第 {1} 帧读不出来（共 {2} 帧）".format(name, index, count)})
        return img, results
    results.append({"视频源": "{0}（第 {1} 帧 / 共 {2} 帧）".format(name, index, count or "?")})
    return frame, results


def format_video(results):
    """执行日志"结果数据"列：短文案"""
    if results and isinstance(results[0], dict):
        return "视频源：{0}".format(results[0].get("视频源", ""))
    return "视频源"


# 声明表（kind = KIND_SOURCE）
VIDEO_SOURCE_SPECS = [
    {
        "name": "视频源",
        "run": run_video,
        "format_result": format_video,
        "param_specs": [
            ("video_path", "视频路径", "file",
             {"filter": "视频 (*.mp4 *.avi *.mkv *.mov)", "default": ""}),
            ("frame_index", "当前帧号", "int", {"min": 0, "max": 100000000, "default": 0}),
            ("auto_next", "执行后前进一帧", "bool", {"default": True}),
            ("loop", "到末尾回到开头", "bool", {"default": False}),
        ],
    },
]
