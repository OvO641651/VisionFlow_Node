# -*- coding: utf-8 -*-
"""
颜色处理算子（树里归**"颜色处理"**分组，2026.10.14 新建的树干）：**颜色提取**（原树里叫"颜色"，用户 2026.10.12 要求改名）。

为什么单独一个文件：同 `FaceDetectOps.py`（用户定的"**一个节点一个文件**"，批次5 再按大标题分文件夹）。

语义（**处理类** `KIND_PROCESS`，和灰度 / 二值化一样）：
    · **阈值内的像素保留原色，阈值外的像素变黑**（用户原话："运行后则提取出阈值颜色的画面。
      不在阈值中的画面变成黑色。"）；
    · 只处理 **ROI 那一块**，ROI 以外保持原样（"所见即所算"，与其他处理类同一条口径）；
    · 输出必须是 3 通道 BGR；**绝不就地改传进来的 img**（处理类铁律）。

两种颜色模型（用户要求用下拉框切换）：
    · **HSV**：OpenCV 的 H 是 **0~179**（不是 0~360），S / V 是 0~255；
    · **RGB**：R / G / B 各 0~255。注意 OpenCV 读进来的是 BGR，所以这里会先 `BGR2RGB`
      再 `inRange`，保证"参数里的 R 就是用户看到的 R"。
    选哪个模型，参数页只显示哪一套阈值 —— 靠通用参数窗口的 `visible_when` 声明（见 GenericProcessDialog）。

参数校验（批次4 目标4 的规则表）：按**当前模型**那 6 个通道夹取 + "下限 > 上限自动互换"（与 Canny 低/高同一条规则）。
另一套（当前没显示的）**不校验也不改** —— 免得提示里冒出一堆用户看不见的参数名。
"""

from core import log_texts as T
import cv2
import numpy as np

# 复用处理类的通用外壳（copy 出新图 → 只在 ROI 上做变换 → 回填 → 保证 3 通道）：
# 这样"ROI 只处理一块、绝不改传入对象"这条契约只有一份实现，不会两处跑偏。
from core.ImageOps import apply_to_roi
from core.ParamRules import clamp_int, read_int


def _limits_for(model, params):
    """
    按当前模型取 `(下限, 上限)` 两组 BGR / HSV 分量。

    :param model: "HSV" 或 "RGB"
    :return: (lo, hi)，都是长度为 3 的 int 元组，顺序与模型一致（RGB 时是 R,G,B）
    """
    if model == "RGB":
        lo = (int(params.get("rgb_r_low", 150)), int(params.get("rgb_g_low", 0)),
              int(params.get("rgb_b_low", 0)))
        hi = (int(params.get("rgb_r_high", 255)), int(params.get("rgb_g_high", 100)),
              int(params.get("rgb_b_high", 100)))
    else:
        lo = (int(params.get("hsv_h_low", 0)), int(params.get("hsv_s_low", 70)),
              int(params.get("hsv_v_low", 50)))
        hi = (int(params.get("hsv_h_high", 10)), int(params.get("hsv_s_high", 255)),
              int(params.get("hsv_v_high", 255)))
    return lo, hi


def run_color_extract(detector, img, roi, params):
    """
    颜色提取（处理类）：ROI 内"阈值内保留原色、阈值外置黑"，ROI 外原样。

    :return: (新图, [结果 dict])；结果 dict 里带像素计数，供执行日志写"提取到 N 个像素（x.x%）"
    """
    model = str(params.get("color_model", "HSV") or "HSV")
    lo, hi = _limits_for(model, params)
    lo = np.array(lo, dtype=np.uint8)
    hi = np.array(hi, dtype=np.uint8)

    used = [0]        # 命中像素数（闭包往外递：_apply_to_roi 只认"返回一张新图"）

    def _do(patch):
        # 上游若是单通道图，先补成 3 通道（inRange 的 shape 要对得上）
        if patch.ndim == 2:
            patch = cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR)
        work = (cv2.cvtColor(patch, cv2.COLOR_BGR2RGB) if model == "RGB"
                else cv2.cvtColor(patch, cv2.COLOR_BGR2HSV))
        mask = cv2.inRange(work, lo, hi)
        out = np.zeros_like(patch)                 # ★ 阈值外 = 黑
        out[mask > 0] = patch[mask > 0]            # ★ 阈值内 = 原色
        used[0] = int(cv2.countNonZero(mask))
        return out

    out = apply_to_roi(img, roi, _do)
    x, y, w, h = roi
    return out, [{"提取像素": used[0], "总像素": max(0, int(w)) * max(0, int(h)), "模型": model}]


def _format_extract(results):
    """执行日志"结果数据"列的文案（短：这一列会截断）"""
    info = results[0] if results and isinstance(results[0], dict) else {}
    count = int(info.get("提取像素", 0) or 0)
    total = int(info.get("总像素", 0) or 0)
    ratio = (count * 100.0 / total) if total else 0.0
    return T.COLOR_PIXELS.format(n=count, pct=ratio)


def validate_color_extract(params):
    """
    颜色提取的参数校验：按**当前模型**夹取 6 个阈值 + "下限 > 上限自动互换"。

    为什么下限 > 上限也要管：`cv2.inRange` 对 lo > hi 不会报错，而是**整幅图都不命中**（全黑）——
    用户看到的就是"提取出来一片黑"，属于目标4 要消灭的那种"静默"；互换之后"参数值 = 实际生效值"。
    """
    fixed, notes = dict(params), []
    model = str(fixed.get("color_model", "HSV") or "HSV")

    if model == "RGB":
        pairs = (("rgb_r_low", "rgb_r_high", "R"), ("rgb_g_low", "rgb_g_high", "G"),
                 ("rgb_b_low", "rgb_b_high", "B"))
    else:
        # H 只有 0~179（OpenCV 口径）；S / V 是 0~255
        pairs = (("hsv_h_low", "hsv_h_high", "H"), ("hsv_s_low", "hsv_s_high", "S"),
                 ("hsv_v_low", "hsv_v_high", "V"))

    for low_key, high_key, label in pairs:
        top = 179 if label == "H" else 255
        low = clamp_int(read_int(fixed, low_key, 0, label + " 下限", notes), 0, top,
                        label + " 下限", notes)
        high = clamp_int(read_int(fixed, high_key, top, label + " 上限", notes), 0, top,
                         label + " 上限", notes)
        if low > high:
            notes.append("{0} 下限/上限已互换（{1}/{2} → {3}/{4}）".format(
                label, low, high, high, low))
            low, high = high, low
        fixed[low_key], fixed[high_key] = low, high
    return fixed, notes, []


# ----------------------------------------------------------------------
# 算子声明表（注册表组装成 NodeSpec，kind 由注册时指定 = KIND_PROCESS）
#
# 阈值一律用 **slider_int**（用户 2026.10.12 要求）：界面上每行 = 参数名 + 进度条 + 微调框，
# 即 `H ──进度条── 50`；`visible_when` 让"选哪个模型就只显示哪一套阈值"。
# ----------------------------------------------------------------------
_HINT_HSV = ("color_model", ["HSV"])
_HINT_RGB = ("color_model", ["RGB"])

COLOR_SPECS = (
    {
        "name": "颜色提取",
        "run": run_color_extract,
        "format_result": _format_extract,
        "validate": validate_color_extract,
        "param_specs": [
            ("color_model", "颜色模型", "combo",
             {"options": ["HSV", "RGB"], "default": "HSV"}),

            # ---- HSV 那套（默认一组"红色"：H 0~10 / S 70~255 / V 50~255）----
            ("hsv_h_low", "H 下限", "slider_int",
             {"min": 0, "max": 179, "default": 0, "visible_when": _HINT_HSV}),
            ("hsv_h_high", "H 上限", "slider_int",
             {"min": 0, "max": 179, "default": 10, "visible_when": _HINT_HSV}),
            ("hsv_s_low", "S 下限", "slider_int",
             {"min": 0, "max": 255, "default": 70, "visible_when": _HINT_HSV}),
            ("hsv_s_high", "S 上限", "slider_int",
             {"min": 0, "max": 255, "default": 255, "visible_when": _HINT_HSV}),
            ("hsv_v_low", "V 下限", "slider_int",
             {"min": 0, "max": 255, "default": 50, "visible_when": _HINT_HSV}),
            ("hsv_v_high", "V 上限", "slider_int",
             {"min": 0, "max": 255, "default": 255, "visible_when": _HINT_HSV}),

            # ---- RGB 那套（默认也是一组"红"：R 150~255 / G 0~100 / B 0~100）----
            ("rgb_r_low", "R 下限", "slider_int",
             {"min": 0, "max": 255, "default": 150, "visible_when": _HINT_RGB}),
            ("rgb_r_high", "R 上限", "slider_int",
             {"min": 0, "max": 255, "default": 255, "visible_when": _HINT_RGB}),
            ("rgb_g_low", "G 下限", "slider_int",
             {"min": 0, "max": 255, "default": 0, "visible_when": _HINT_RGB}),
            ("rgb_g_high", "G 上限", "slider_int",
             {"min": 0, "max": 255, "default": 100, "visible_when": _HINT_RGB}),
            ("rgb_b_low", "B 下限", "slider_int",
             {"min": 0, "max": 255, "default": 0, "visible_when": _HINT_RGB}),
            ("rgb_b_high", "B 上限", "slider_int",
             {"min": 0, "max": 255, "default": 100, "visible_when": _HINT_RGB}),
        ],
    },
)
