# -*- coding: utf-8 -*-
"""
识别类算子（"识别"分组）：**人脸**。

为什么单独一个文件（用户 2026.10.12 定的组织方式）：
    从这两个识别节点起，**一个节点一个文件** —— 文件里放这个节点的算法、参数表、
    结果文案、画法、校验规则；注册表（`NodeRegistry.py`）只在末尾把这份声明组装成 `NodeSpec`。
    老的"一个大类一个文件"（`ProcessOps` / `SourceOps` / `OutputOps`）留到**批次5** 再按同一原则拆，
    批次5 的目录规划见《批次4 技术方案》《九、想法》9.9。
    本文件**不 import NodeRegistry**（注册表是反向 import 它的，会循环导入）。

语义（与直线 / 圆完全一致，**检测类** `KIND_DETECT`）：
    · 图像**原样透传**（`return img`，连副本都不建）—— 数据层绝不许被它改动；
    · 只多产出一份结果：人脸框列表，每项 = `(左上x, 左上y, 右下x, 右下y)`（**与直线的端点格式一致**），
      所以 `NodeRegistry.result_bbox()` 一行都不用改，下游"ROI 继承 → 继承上游结果框"就能直接用人脸框；
    · 绿框由 `draw()` 画在显示层，只活在这一帧的显示层上，永远不回流到数据层。

"出错"怎么表现（用户 2026.10.12 要求 = **日志红字**）：
    没选级联文件 / 文件不存在 / 不是有效的级联分类器 —— **都不弹窗、不抛异常**，
    而是原样透传 + 在结果里递一句话 `{"__note__": …, "__error__": True}`；
    引擎看到 `__error__` 会把执行日志那一行**涂红**（通用错误通道，见 `main.py` 的 `LOG_ERROR_MARK`）。
    为什么必须自己先挡：实测 `cv2.CascadeClassifier('')`（空路径）**会抛异常**，
    坏 xml 也会 —— 引擎里没有 try/except，抛出来就是"点了执行什么都没发生"（目标4 消灭过的静默）。
"""

import os

import cv2

# 参数校验的公共零件；规则表写在本文件末尾的 validate_face() 里
from ParamRules import clamp_float, clamp_int, read_float, read_int


# ----------------------------------------------------------------------
# 级联分类器缓存
#
# 为什么要缓存：视频 / 相机路径下每秒要跑 25 次，每次都 `cv2.CascadeClassifier(path)`
# 重新解析一遍 xml（几十毫秒）会把播放拖垮 —— 2026.10.7 给视频 / 图片做缓存时踩过同类坑。
# 键 = (绝对路径, 修改时间, 大小)：文件被换掉（重下 / 覆盖）时会自动重新加载。
# ----------------------------------------------------------------------
_CASCADE_CACHE = {}
_CASCADE_CACHE_MAX = 4          # 只留最近几个：用户最多在几个级联文件之间来回切


def _load_cascade(path):
    """
    取（必要时加载）级联分类器。

    :return: (分类器, 错误说明)；成功时说明是空串，失败时分类器是 None
             失败**不抛异常**：调用方原样透传图像 + 把说明写进日志（红字）
    """
    try:
        info = os.stat(path)
    except OSError:
        return None, "级联文件不存在：{0}".format(path)

    key = (os.path.abspath(path), int(info.st_mtime), int(info.st_size))
    cached = _CASCADE_CACHE.get(key)
    if cached is not None:
        return cached, ""

    try:
        cascade = cv2.CascadeClassifier(path)
    except Exception:
        # 坏 xml / 空路径都会抛（实测 cv2 抛的是 SystemError，原文是
        # "returned a result with an error set" 这种机器话，直接展示给用户看不懂）
        return None, "级联文件加载失败（不是有效的 OpenCV 级联文件）：{0}".format(path)
    if cascade.empty():
        return None, "级联文件不是有效的 OpenCV 级联分类器：{0}".format(path)

    if len(_CASCADE_CACHE) >= _CASCADE_CACHE_MAX:
        _CASCADE_CACHE.clear()
    _CASCADE_CACHE[key] = cascade
    return cascade, ""


def _error(message):
    """
    包一行"错误"结果：`__note__` 给执行日志当文案，`__error__` 让那一行显示成**红字**。

    用结果里的 dict 递文案是引擎的老约定（`result_bbox()` 只认 tuple/list，会跳过 dict），
    `__error__` 是 2026.10.12 加的**通用错误通道**标记（见 `main.py::_format_result_text`）。
    """
    return {"__note__": message, "__error__": True}


def _run_face(detector, img, roi, params):
    """
    人脸识别（检测类）：只在 ROI 里找人脸，结果按**原图坐标**返回两个角点。

    :param roi: (x, y, w, h)，原图坐标
    :return: (原样透传的图像, 人脸框列表)；出错时返回 (图像, [一句红字说明])
    """
    path = str(params.get("cascade_file", "") or "").strip()
    if not path:
        # 用户 2026.10.12 定的口径：默认**不设级联文件**，直接运行就用红字把原因写清楚
        return img, [_error("未选择级联文件，本次未检测（图像原样传给下游）")]

    cascade, reason = _load_cascade(path)
    if cascade is None:
        return img, [_error(reason)]

    x, y, w, h = roi
    if w <= 0 or h <= 0:
        # ROI 被裁成 0 尺寸：引擎那边也会跳过这个节点，这里只防崩
        return img, []

    patch = img[y:y + h, x:x + w]
    # 检测类**不复制也不用改**这份 patch：cvtColor 会生成新数组，数据层一个像素都不动
    gray = patch if patch.ndim == 2 else cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)

    scale = float(params.get("face_scale_factor", 1.1))
    neighbors = int(params.get("face_min_neighbors", 5))
    min_size = int(params.get("face_min_size", 30))
    try:
        faces = cascade.detectMultiScale(gray, scale, neighbors, minSize=(min_size, min_size))
    except Exception as exc:
        # scaleFactor <= 1 之类会抛（窗口下限已经卡到 1.01、引擎侧还有 validate_face 兜底，
        # 这里只是最后一层"绝不把执行带崩"的保险）
        return img, [_error("人脸检测失败：{0}".format(exc))]

    boxes = [(int(fx) + x, int(fy) + y, int(fx) + x + int(fw), int(fy) + y + int(fh))
             for fx, fy, fw, fh in faces]
    return img, boxes


def _draw_face(display_img, results, params):
    """把每个人脸框画到**显示层**（绿色矩形，和直线一样只在显示图上）"""
    for item in results:
        if isinstance(item, (tuple, list)) and len(item) == 4:
            x1, y1, x2, y2 = item
            cv2.rectangle(display_img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)


def _format_face(results):
    """执行日志"结果数据"列的文案（短：这一列会截断）"""
    return "检测到{0}张人脸".format(len(results or []))


def validate_face(params):
    """
    人脸识别的参数校验（批次4 目标4 的规则表，窗口层 / 引擎层各跑一遍）。

    实测依据（cv2 4.13，2026.10.12 只读探针）：
        · `scaleFactor <= 1`（1.0 / 0.5 都试过）**直接抛异常** ⇒ 必须夹到 > 1（控件下限也是 1.01）；
        · `minNeighbors = 0 / -1` 不崩，但**检出 80 个**（噪声爆炸）⇒ 夹到 1~20；
        · `minSize = (0,0)` 不崩（等于不限）、`(5000,5000)` 检出 0 ⇒ 夹到 5~2000 的合理区间。
    """
    fixed, notes = dict(params), []

    fixed["face_scale_factor"] = clamp_float(
        read_float(fixed, "face_scale_factor", 1.1, "缩放步长", notes),
        1.01, 2.0, "缩放步长", notes)
    fixed["face_min_neighbors"] = clamp_int(
        read_int(fixed, "face_min_neighbors", 5, "最小邻居数", notes),
        1, 20, "最小邻居数", notes)
    fixed["face_min_size"] = clamp_int(
        read_int(fixed, "face_min_size", 30, "最小人脸尺寸", notes),
        5, 2000, "最小人脸尺寸", notes)
    return fixed, notes, []


# ----------------------------------------------------------------------
# 算子声明表（注册表会把它组装成 NodeSpec，kind 由注册时指定 = KIND_DETECT）
#   name           算子名（和左侧树、方框文字一致）
#   run            引擎调用：run(detector, img, roi, params) -> (out_img, results)
#   draw           只画显示层（检测类才有）
#   format_result  执行日志"结果数据"列
#   validate       参数校验规则（批次4 目标4）
#   param_specs    参数表：(参数名, 界面中文名, 控件类型, 附加选项)
# ----------------------------------------------------------------------
FACE_SPECS = (
    {
        "name": "人脸识别",
        "run": _run_face,
        "draw": _draw_face,
        "format_result": _format_face,
        "validate": validate_face,
        "param_specs": [
            # ★ 不设默认值（用户 2026.10.12 要求）：级联文件由用户自己选
            #   ★ **per_node = True**（节点级参数）：换图 / 换视频 / 换页都**不重置** ——
            #     它是"这个节点用哪个模型文件"的配置，跟当前是哪张图无关
            #     （用户 2026.10.12 实测报："更换图片后级联文件需要重新导入……我希望每幅图都可以使用"）；
            #     而下面三个调参参数照旧**每幅图独立**（用户："其他的参数需要保持原样"）。
            #   ★ plain = True：浏览时**只选文件、绝不导入图库**。
            #     通用窗口的 file 控件在非起点节点上默认弹的是"选图片"，还会顺手
            #     `import_image_path()` 把选中的图导进图库 —— 对"级联文件"这种参数是彻头彻尾的副作用
            #     （2026.10.7 做"输出文件名"时踩过同类坑，所以这次显式声明成普通文件选择）。
            ("cascade_file", "级联文件", "file",
             {"default": "", "plain": True, "per_node": True,
              "filter": "级联文件 (*.xml *.xml.gz);;所有文件 (*.*)"}),
            ("face_scale_factor", "缩放步长", "float",
             {"min": 1.01, "max": 2.0, "step": 0.05, "decimals": 2, "default": 1.1}),
            ("face_min_neighbors", "最小邻居数", "int",
             {"min": 1, "max": 20, "default": 5}),
            ("face_min_size", "最小人脸尺寸", "int",
             {"min": 5, "max": 2000, "default": 30}),
        ],
    },
)
