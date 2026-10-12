# -*- coding: utf-8 -*-
"""
图片读写小工具：解决 Windows 上"**中文（非 ASCII）路径读不了 / 写不了**"的老问题。

问题（用户 2026.10.12 实测报的）：
    打开 `E:\\OpenCV_python\\python_opencv\\OpenCV_Book\\data` 文件夹时，日志里刷出
        cv::findDecoder imread_('E:/OpenCV_python/python_opencv/OpenCV_Book/data\\所有数据按行排列结果.png'):
        can't open/read file: check file path/integrity
    而 `image\\lena.png` 这种**纯英文名**一点事没有。

根因（只读探针实测，cv2 4.13 / Windows）：
    `cv2.imread` / `cv2.imwrite` 在 Windows 上走的是**窄字符（ANSI）文件 API**，
    文件名里有中文就找不到文件 —— `cv2.imread` 直接返回 None（不是抛异常，所以表现为"静默读不出来"）。
    同一条路径换成"先把文件读成字节流、再交给 cv2 解码"就完全正常：
        imread            -> None
        imdecode(fromfile)-> (5000, 400, 3)   ← 同一个中文名文件

做法：
    读：`np.fromfile(path)` 拿到字节流 → `cv2.imdecode(buf, flags)`；
    写：`cv2.imencode(ext, img)` 编到内存 → `buf.tofile(path)`。
    这条路不碰 Windows 的窄字符 API，所以中文 / 空格 / emoji 路径都能用。
    **返回值契约与 cv2.imread / cv2.imwrite 保持一致**（失败返回 None / False），
    调用方原来的 `if img is None: ...` / `if not ok: ...` 一行都不用改。

顺带说明：视频（`cv2.VideoCapture` / `cv2.VideoWriter`）是另一条后端路径（FFmpeg），
中文路径实测能正常打开，所以这里只处理图片。
"""

import os

import cv2
import numpy as np


def read_image(path, flags=cv2.IMREAD_COLOR):
    """
    读一张图（**支持中文路径**）。读不出来返回 None —— 与 `cv2.imread` 同一个契约。

    :param path: 图片路径（相对 / 绝对都行）
    :param flags: 同 `cv2.imread` 的第二个参数（默认 IMREAD_COLOR）
    """
    if not path:
        return None
    try:
        buffer = np.fromfile(path, dtype=np.uint8)
    except (OSError, ValueError):
        # 路径不存在 / 是目录 / 没有权限：与 imread 一样"读不出来"，不抛
        return None
    if buffer.size == 0:
        return None
    try:
        return cv2.imdecode(buffer, flags)
    except Exception:
        # 解码失败（坏文件 / 不是图片）：同样返回 None
        return None


def write_image(path, img, params=None):
    """
    写一张图（**支持中文路径**）。成功返回 True —— 与 `cv2.imwrite` 同一个契约。

    :param params: 同 `cv2.imwrite` 的第三个参数（编码参数列表，一般不用）
    """
    if img is None or not path:
        return False
    ext = os.path.splitext(path)[1] or ".png"
    try:
        ok, buffer = cv2.imencode(ext, img, params or [])
    except Exception:
        # 扩展名不认识 / 图像数据不对：与 imwrite 一样返回 False
        return False
    if not ok:
        return False
    try:
        buffer.tofile(path)
    except (OSError, ValueError):
        return False
    return True
