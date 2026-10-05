# -*- coding: utf-8 -*-
"""
图像源类算子的实现（"采集"这一大类）。

第一批只做 **图片源** 一个节点（用户 2026.10.4 定的范围：先出第一版看效果）：
给流程一个**显式起点**，并声明"这条流程吃的是哪张图"。来源三选一
（2026.10.5：把"图片"和"文件夹"分成两档，路径一个是图片、一个是文件夹）：
    · 图片   —— 路径是一个图片文件；没填路径时就跟"当前图像"一样，用主窗口当前那张（零拷贝）
    · 文件夹 —— 路径是一个文件夹，取里面按文件名排序的第一张（整个文件夹的图会由主窗口加进图库，
                点图库缩略图就能切换，和"图库与图片源统一"配套）
    · 测试图 —— 自动生成一张（不用打开任何图片就能跑通流程，调试用）

与现有"全局图像源"**并存**（用户拍板的决策 c）：
    流程里放了它、并且下游把"图像源"绑定到它，才吃它读出来的图；
    没放它 / 没连它 ⇒ 一切照旧（全局图像源 = 主窗口当前那张图）。
    所以数据层会有两个起点，各走各的，执行日志的"图像源"列能区分开。

三条实现要点：
    1、读文件**必须缓存**（按 (路径, mtime, 大小)），否则视频 / 连续执行每帧都重新解码会卡；
    2、"当前图像"这条分支**直接返回传入对象本身**（零拷贝，验收可以用 is 断言）；
    3、文件读不到**不崩、不弹窗**：原样透传输入图，并在结果里带一条说明（日志会写出来）。

本文件只导出声明（SOURCE_SPECS），**不 import NodeRegistry** —— 注册表在末尾汇总，
这样"注册表 ←→ 分类模块"不会循环导入（和 ProcessOps.py 一个套路）。
"""

import os

import cv2

# 图片解码缓存：同一时刻只缓存最后一张，切换文件时自动换掉，不会无限涨
_IMAGE_CACHE = {"key": None, "img": None}

# 认得的图片扩展名（"文件夹"来源挑图、主窗口导入文件夹都用它）
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')


def first_image_in_folder(folder):
    """
    文件夹里按文件名排序的第一张图片的完整路径。

    兼容两种情况：路径其实是一张图片（返回它自己）；路径不存在 / 里面没有图片（返回 None）。
    """
    if not folder:
        return None
    if os.path.isfile(folder):
        return folder
    if not os.path.isdir(folder):
        return None
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith(IMAGE_EXTS):
            return os.path.join(folder, name)
    return None


def _load_image(path):
    """
    读一张图片（带缓存）。
    :return: BGR 图；读不到返回 None
    """
    if not path:
        return None
    path = os.path.abspath(path)
    try:
        stat = os.stat(path)
        key = (path, stat.st_mtime, stat.st_size)
    except OSError:
        # 路径不存在 / 没权限
        return None
    if _IMAGE_CACHE["key"] == key and _IMAGE_CACHE["img"] is not None:
        return _IMAGE_CACHE["img"]          # 命中缓存：不再重新解码
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    _IMAGE_CACHE["key"] = key
    _IMAGE_CACHE["img"] = img
    return img


def _cached_test_image():
    """测试图：只生成一次、之后复用（Detector.py 里的 make_test_image）"""
    if _IMAGE_CACHE["key"] != "test" or _IMAGE_CACHE["img"] is None:
        from Detector import make_test_image
        _IMAGE_CACHE["key"] = "test"
        _IMAGE_CACHE["img"] = make_test_image()
    return _IMAGE_CACHE["img"]


def run_source(detector, img, roi, params):
    """
    图片源：按 params["source_type"] 决定输出哪张图。
    :return: (out_img, results)

    为什么 results 里放一个 dict：执行日志的"结果数据"列由 format_result 生成，
    它只拿得到 results（拿不到 params），所以把来源说明塞在这里；
    引擎的 result_bbox() 只认 tuple / list、会跳过 dict，所以不会干扰下游的"ROI 继承"。
    """
    source_type = params.get("source_type", "图片")

    # 老方案文件里的 "当前图像"：语义就是"用传进来的那一帧"，保持原样（不看路径），免得老方案行为变化
    if source_type == "当前图像":
        return img, [{"图片源": "当前图像"}]

    # "图片"（原来的"单张图片"和"当前图像"合并成这一档，用户 2026.10.5 定的）：
    #   填了路径 → 读那个文件；没填路径 → 跟"当前图像"一样，直接透传传进来的那一帧。
    if source_type in ("图片", "单张图片"):
        path = params.get("source_path", "")
        if not path:
            # 没填路径：用当前打开的那张图
            return img, [{"图片源": "当前图像（未指定路径）"}]
        loaded = _load_image(path)
        if loaded is None:
            # 读不到就原样透传，日志里如实写原因（执行路径绝不弹窗）
            return img, [{"图片源": "读取失败：{0}".format(os.path.basename(path))}]
        return loaded, [{"图片源": os.path.basename(path)}]

    # "文件夹"：路径是一个文件夹，取里面按文件名排序的第一张图
    # （整个文件夹的图片会由主窗口加进图库，点缩略图即可切换）
    if source_type == "文件夹":
        folder = params.get("source_path", "")
        first = first_image_in_folder(folder)
        if first is None:
            name = os.path.basename(folder) if folder else "(未填路径)"
            return img, [{"图片源": "文件夹里没有图片：{0}".format(name)}]
        loaded = _load_image(first)
        if loaded is None:
            return img, [{"图片源": "读取失败：{0}".format(os.path.basename(first))}]
        return loaded, [{"图片源": "{0}（第 1 张）".format(os.path.basename(first))}]

    if source_type == "测试图":
        return _cached_test_image(), [{"图片源": "测试图"}]

    # 认不出来的值（老文件 / 手改过）：原样透传，别让流程断在这里
    return img, [{"图片源": "当前图像"}]


def format_source(results):
    """执行日志"结果数据"列：短文案"""
    if results and isinstance(results[0], dict):
        return "图片源：{0}".format(results[0].get("图片源", ""))
    return "图片源"


# ----------------------------------------------------------------------
# 算子声明表：注册表（NodeRegistry）会把每一条组装成 NodeSpec(kind=KIND_SOURCE)
#   name / run / format_result / param_specs —— 含义同 ProcessOps.PROCESS_SPECS
# ----------------------------------------------------------------------
SOURCE_SPECS = (
    {
        "name": "图片源",
        "run": run_source,
        "format_result": format_source,
        "param_specs": [
            ("source_type", "图像来源", "combo",
             {"options": ["图片", "文件夹", "测试图"], "default": "图片"}),
            ("source_path", "路径", "file",
             {"filter": "图片 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)", "default": ""}),
        ],
    },
)
