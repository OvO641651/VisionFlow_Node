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
# 视频源（目标3-M3，2026.10.6 用户拍板的设计）
#   · 帧**不进图库**（不占内存、不污染图片列表），每帧结果按 "视频路径#帧号" 单独缓存；
#   · 参数**整段共用一份**（主窗口用视频槽 VIDEO_ROI_KEY），中途改参数后面的帧按新的跑；
#   · VideoCapture **自己一个、带缓存**（与主窗口的视频播放各读各的，不抢读指针）；
#   · run() 只**读**当前帧、**不前进**——"执行后前进一帧"由主窗口在**一次执行结束后**
#     统一做一次（见 main.py::_advance_video_cursor），这样同一轮里多个节点取图共用同一帧。
# ----------------------------------------------------------------------
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


# ----------------------------------------------------------------------
# 相机源（目标3-M4，2026.10.7）——方案 A：节点**复用主窗口相机**，不自己开设备
#   · 主窗口启动时注入一个"取帧器"（set_camera_frame_provider）：返回相机**最新一帧**或 None；
#   · run_camera 只读它、**并返回副本**（缓冲会被下一帧覆盖，绝不能把引用交出去）；
#   · 取不到（相机没开 / 读失败）⇒ 原样透传传入的图 + 结果里带说明（日志会写，不弹窗）；
#   · 相机是**无界流**：没有帧游标 / 循环参数；结果**不进缓存**（由主窗口跳过写入）。
# ----------------------------------------------------------------------
CAMERA_FRAME_PROVIDER = None      # 主窗口注入的取帧器：() -> np.ndarray | None


def set_camera_frame_provider(fn):
    """主窗口注入"相机最新一帧"的取帧器（方案 A：节点复用主窗口相机）"""
    global CAMERA_FRAME_PROVIDER
    CAMERA_FRAME_PROVIDER = fn


def run_camera(detector, img, roi, params):
    """相机源：取主窗口相机的最新一帧；取不到就透传并说明（不弹窗）"""
    camera_id = params.get("camera_id", 0)
    camera_type = params.get("camera_type") or "USB 相机"
    if camera_type != "USB 相机":
        # V1 只适配 USB 相机；界面里那两个预留项已经置灰，这里再兜一层（方案文件可能是手改的）
        return img, [{"相机源": "暂不支持“{0}”（当前版本只适配 USB 相机）".format(camera_type)}]
    provider = CAMERA_FRAME_PROVIDER
    frame = provider() if callable(provider) else None
    if frame is None:
        return img, [{"相机源": "没有可用的相机画面（相机未打开？编号 {0}）".format(camera_id)}]
    h, w = frame.shape[:2]
    # ★ 返回副本：主窗口那个缓冲会被下一帧覆盖
    return frame.copy(), [{"相机源": "相机 {0}（{1}×{2}）".format(camera_id, w, h)}]


def format_camera(results):
    """执行日志"结果数据"列：短文案"""
    if results and isinstance(results[0], dict):
        return "相机源：{0}".format(results[0].get("相机源", ""))
    return "相机源"


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
    {
        "name": "相机源",
        "run": run_camera,
        "format_result": format_camera,
        "param_specs": [
            # V1 只适配 USB 相机；其余类型在下拉框里"占位置灰"（看得见、选不了），以后要做再启用
            # （用户 2026.10.7 定；参数窗口靠 options["disabled"] 把它们置灰，见 GenericProcessDialog）
            ("camera_type", "相机类型", "combo",
             {"options": ["USB 相机", "网络相机（预留）", "工业相机（预留）"],
              "disabled": ["网络相机（预留）", "工业相机（预留）"],
              "default": "USB 相机"}),
            ("camera_id", "相机编号", "int", {"min": 0, "max": 9, "default": 0}),
            ("resolution", "分辨率", "combo",
             {"options": ["默认", "640×480", "1280×720", "1920×1080"], "default": "默认"}),
            ("open_on_run", "执行时自动打开相机", "bool", {"default": True}),
        ],
    },
)
