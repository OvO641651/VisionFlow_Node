# -*- coding: utf-8 -*-
"""
处理类算子的算法实现（"处理"这一大类）。

为什么单独一个文件，而不是继续往 NodeRegistry.py / Detector.py 里塞：
    算子会越来越多。按大类分文件——处理类放这里、检测类留在 Detector.py、
    识别类以后另开一个——每个大类一个类 + 一组方法：
        · 文件小，改一个算子只动一个文件；
        · 算法的**参数表 + 结果文案**跟着算法写在本文件末尾的 PROCESS_SPECS 里，
          注册表（NodeRegistry）只负责把这份声明组装成 NodeSpec，
          所以"加一个算子"= 加一个方法 + 加一张参数表（+ main.ui 树里加一项）；
        · 本文件**不 import NodeRegistry**，避免循环导入。

处理类的三条硬规矩（下面每个方法都守）：
    1、**绝不就地改传进来的 img**——先 copy 一份再改。就地改会污染数据层，
       下游节点就会"看见"上游处理过的像素（历史上被绿线污染坑过一次）；
    2、输出必须是 **3 通道 BGR**：下游 cv2.line / cv2.circle 都要求 3 通道，
       单通道图会把后面的算子弄崩，所以统一的 _apply_to_roi() 会兜一层 cvtColor；
    3、只处理 **ROI 那一块**，ROI 以外保持原样（"所见即所算"）。

参数命名约定：小写下划线，键名和 PROCESS_SPECS 里的第一项一一对应。
"""

import cv2

# 参数校验的公共零件（夹取 / 取奇数 / 读数字）；规则表写在文件末尾各自的算子里
from ParamRules import clamp_float, clamp_int, force_odd, read_float, read_int


def _to_bgr(img):
    """保证是 3 通道 BGR（处理类算子的输出必须是 3 通道）"""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


class ProcessOps(object):
    """处理类算子的算法：每个方法都是 (img, roi, params) -> 一张新图"""

    # ------------------------------------------------------------------
    # 通用外壳
    # ------------------------------------------------------------------
    @staticmethod
    def _apply_to_roi(img, roi, func):
        """
        处理类的通用外壳：copy 出新图 → 只在 ROI 上做变换 → 回填 → 保证 3 通道。

        :param func: func(patch) -> patch；patch 是 ROI 的视图（可以就地改），
                     返回值会被写回 ROI
        """
        out = _to_bgr(img).copy()          # ① copy：绝不改传进来的 img
        x, y, w, h = roi
        if w <= 0 or h <= 0:
            # ROI 越界被裁成 0 尺寸时，原样返回（引擎已经按整图兜过一层，这里只防崩）
            return out
        patch = out[y:y + h, x:x + w]
        out[y:y + h, x:x + w] = _to_bgr(func(patch))   # ② 回填时保证 3 通道
        return out

    @staticmethod
    def _odd(value, low, high):
        """把值夹进 [low, high] 并强制成奇数（卷积核尺寸必须奇数）"""
        value = max(low, min(high, int(value)))
        if value % 2 == 0:
            value = value + 1 if value < high else value - 1
        return max(low, min(high, value))

    # ------------------------------------------------------------------
    # 灰度
    # （2026.10.3：算法本身也从 Detector.py 搬过来了——Detector.py 只放检测类算法，
    #   灰度是处理类，归这里）
    # ------------------------------------------------------------------
    @staticmethod
    def to_gray(img):
        """
        灰度化（"数据层"版本）：始终返回 3 通道 BGR 图。

        数据流引擎里灰度是"处理类"算子，输出图像要交给下游继续算，而下游的
        cv2.line / cv2.circle / HoughCircles 都要求 3 通道，所以不能返回单通道：
        先转灰度、再补回 3 通道——图像没颜色了，但通道数和彩色图一致，下游不会报错。
        """
        if img is None or img.size == 0:
            return img
        if len(img.shape) == 2:
            # 本来就是单通道，补成 3 通道即可
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def gray(img, roi, params):
        """灰度：ROI 内转 3 通道灰度；params["gray_full_image"] 为真时整幅图都转"""
        if params.get("gray_full_image", False):
            # "作用于整图"：忽略 ROI（引擎那边也会把 ROI 当成整图，做到"所见即所算"）
            return ProcessOps.to_gray(_to_bgr(img).copy())
        return ProcessOps._apply_to_roi(img, roi, ProcessOps.to_gray)

    # ------------------------------------------------------------------
    # 取反
    # ------------------------------------------------------------------
    @staticmethod
    def invert(img, roi, params):
        """反色：ROI 内 255 - x"""
        return ProcessOps._apply_to_roi(img, roi, lambda patch: cv2.bitwise_not(patch))

    # ------------------------------------------------------------------
    # 滤波
    # ------------------------------------------------------------------
    @staticmethod
    def blur(img, roi, params):
        """滤波：均值 / 高斯 / 中值"""
        blur_type = params.get("blur_type", "高斯")
        ksize = ProcessOps._odd(params.get("blur_ksize", 3), 1, 31)
        sigma = float(params.get("blur_sigma", 0.0))

        def _do(patch):
            if blur_type == "均值":
                return cv2.blur(patch, (ksize, ksize))
            if blur_type == "中值":
                # 中值滤波要求核奇数且 > 1
                return cv2.medianBlur(patch, max(3, ksize))
            return cv2.GaussianBlur(patch, (ksize, ksize), sigma)

        return ProcessOps._apply_to_roi(img, roi, _do)

    # ------------------------------------------------------------------
    # 二值化
    # ------------------------------------------------------------------
    @staticmethod
    def threshold(img, roi, params):
        """二值化：固定阈值 / Otsu / 自适应（先转灰度再算，结果补回 3 通道）"""
        mode = params.get("thresh_mode", "固定阈值")
        thresh = int(params.get("thresh_value", 127))
        maxval = int(params.get("thresh_maxval", 255))
        flag = (cv2.THRESH_BINARY_INV if params.get("thresh_type", "二值") == "反二值"
                else cv2.THRESH_BINARY)

        def _do(patch):
            gray = cv2.cvtColor(_to_bgr(patch), cv2.COLOR_BGR2GRAY)
            if mode == "Otsu":
                # Otsu 自己算阈值，传进去的 thresh 会被忽略
                _used, out = cv2.threshold(gray, 0, maxval, flag | cv2.THRESH_OTSU)
                return out
            if mode == "自适应":
                # 自适应阈值：blockSize 必须是 > 1 的奇数
                return cv2.adaptiveThreshold(gray, maxval, cv2.ADAPTIVE_THRESH_MEAN_C,
                                             flag, 11, 2)
            _used, out = cv2.threshold(gray, thresh, maxval, flag)
            return out

        return ProcessOps._apply_to_roi(img, roi, _do)

    # ------------------------------------------------------------------
    # 形态学
    # ------------------------------------------------------------------
    @staticmethod
    def morphology(img, roi, params):
        """形态学：腐蚀 / 膨胀 / 开运算 / 闭运算 / 梯度 / 顶帽 / 黑帽

        OpenCV 里这七个是同一个 API（cv2.morphologyEx）的不同模式，参数完全一样
        （核形状 + 核大小 + 迭代次数），只有 op 不同，所以共用一个节点、一张参数表。
        """
        op_name = params.get("morph_op", "腐蚀")
        shape_name = params.get("morph_shape", "矩形")
        ksize = ProcessOps._odd(params.get("morph_ksize", 3), 1, 31)
        iterations = max(1, min(10, int(params.get("morph_iterations", 1))))
        shape = {"矩形": cv2.MORPH_RECT,
                 "椭圆": cv2.MORPH_ELLIPSE,
                 "十字": cv2.MORPH_CROSS}.get(shape_name, cv2.MORPH_RECT)
        op = {"腐蚀": cv2.MORPH_ERODE,
              "膨胀": cv2.MORPH_DILATE,
              "开运算": cv2.MORPH_OPEN,
              "闭运算": cv2.MORPH_CLOSE,
              "梯度": cv2.MORPH_GRADIENT,       # 膨胀 - 腐蚀，勾出轮廓
              "顶帽": cv2.MORPH_TOPHAT,         # 原图 - 开运算，挑出比周围亮的细节
              "黑帽": cv2.MORPH_BLACKHAT}.get(op_name, cv2.MORPH_ERODE)  # 闭运算 - 原图

        def _do(patch):
            kernel = cv2.getStructuringElement(shape, (ksize, ksize))
            return cv2.morphologyEx(_to_bgr(patch), op, kernel, iterations=iterations)

        return ProcessOps._apply_to_roi(img, roi, _do)

    # ------------------------------------------------------------------
    # 边缘提取
    # ------------------------------------------------------------------
    @staticmethod
    def edge(img, roi, params):
        """边缘提取：Canny / Sobel / Laplacian"""
        method = params.get("edge_method", "Canny")
        low = max(0, int(params.get("edge_low", 50)))
        high = max(0, int(params.get("edge_high", 150)))
        ksize = ProcessOps._odd(params.get("edge_ksize", 3), 1, 31)

        def _do(patch):
            gray = cv2.cvtColor(_to_bgr(patch), cv2.COLOR_BGR2GRAY)
            if method == "Sobel":
                gx = cv2.convertScaleAbs(cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=ksize))
                gy = cv2.convertScaleAbs(cv2.Sobel(gray, cv2.CV_16S, 0, 1, ksize=ksize))
                return cv2.addWeighted(gx, 0.5, gy, 0.5, 0)
            if method == "Laplacian":
                return cv2.convertScaleAbs(cv2.Laplacian(gray, cv2.CV_16S, ksize=ksize))
            return cv2.Canny(gray, low, high)

        return ProcessOps._apply_to_roi(img, roi, _do)


# ----------------------------------------------------------------------
# 算法 → 节点契约
# 引擎调用的签名是 run(detector, img, roi, params) -> (out_img, results)；
# 处理类没有结构化结果，results 一律返回空列表，执行日志给一句短文案。
# ----------------------------------------------------------------------
def format_process(results):
    """处理类的执行日志文案（短：'结果数据'列会截断）"""
    return "执行成功（图像已处理，下游可见）"


def _run_gray(detector, img, roi, params):
    # 灰度算法现在就在本文件里，不再需要 detector（引擎调用签名统一，参数照旧保留）
    return ProcessOps.gray(img, roi, params), []


def _run_invert(detector, img, roi, params):
    return ProcessOps.invert(img, roi, params), []


def _run_blur(detector, img, roi, params):
    return ProcessOps.blur(img, roi, params), []


def _run_threshold(detector, img, roi, params):
    return ProcessOps.threshold(img, roi, params), []


def _run_morphology(detector, img, roi, params):
    return ProcessOps.morphology(img, roi, params), []


def _run_edge(detector, img, roi, params):
    return ProcessOps.edge(img, roi, params), []


# ----------------------------------------------------------------------
# 处理类的参数校验规则（批次4 目标4）
#
# 这些参数的界面控件本身已经限了范围（QSpinBox 的 setRange + 奇数步进），
# 所以这一层的真正作用是**挡住"方案文件 / 老方案里手改出来的值"**：
# 实测 cv2 4.13 下，高斯核 / 结构元 / Sobel 核只要是偶数或 0 就直接抛异常，
# 而 `ProcessOps._odd()` 只是**算法侧的兜底**（默默改掉、用户看不见）；
# 这里补齐"参数侧"：把值改对 + 说明改了什么（窗口层会显示、引擎层写进执行日志）。
# ----------------------------------------------------------------------
def validate_blur(params):
    """滤波：核大小取 [1,31] 内的奇数、高斯标准差夹进 [0,20]"""
    fixed, notes = dict(params), []
    fixed["blur_ksize"] = force_odd(
        read_int(fixed, "blur_ksize", 3, "核大小", notes), 1, 31, "核大小", notes)
    fixed["blur_sigma"] = clamp_float(
        read_float(fixed, "blur_sigma", 0.0, "高斯标准差", notes), 0.0, 20.0, "高斯标准差", notes)
    return fixed, notes, []


def validate_threshold(params):
    """二值化：阈值 / 最大值夹进 [0,255]（越界时 OpenCV 不报错、只是静默饱和，用户看不出来）"""
    fixed, notes = dict(params), []
    fixed["thresh_value"] = clamp_int(
        read_int(fixed, "thresh_value", 127, "阈值", notes), 0, 255, "阈值", notes)
    fixed["thresh_maxval"] = clamp_int(
        read_int(fixed, "thresh_maxval", 255, "最大值", notes), 0, 255, "最大值", notes)
    return fixed, notes, []


def validate_morphology(params):
    """形态学：核大小取 [1,31] 内的奇数、迭代次数夹进 [1,10]"""
    fixed, notes = dict(params), []
    fixed["morph_ksize"] = force_odd(
        read_int(fixed, "morph_ksize", 3, "核大小", notes), 1, 31, "核大小", notes)
    fixed["morph_iterations"] = clamp_int(
        read_int(fixed, "morph_iterations", 1, "迭代次数", notes), 1, 10, "迭代次数", notes)
    return fixed, notes, []


def validate_edge(params):
    """边缘提取：核大小取 [1,31] 内的奇数；Canny 的低/高阈值夹 0~500 并在填反时互换

    低/高阈值这两条 2026.10.7 晚追加（用户实测报"填 500/150 也能跑、效果和 150/500 一样、
    却看不到任何提示"）。为什么它值得管：`cv2.Canny` 内部**自己会交换** low/high（实测），
    所以结果不受影响 —— 但"参数框里写着 500/150、实际按 150/500 跑"这件事用户看不到，
    正是本项目要消灭的那种"静默"。互换之后"参数值 = 实际生效值"，并且会出黄字提示。
    注意：只有"方法 = Canny"才用这两个值（Sobel / Laplacian 只看核大小），
    "选 Sobel 时把这两个框置灰"属于范围外（见《批次4 技术方案》§6.5）。
    """
    fixed, notes = dict(params), []
    fixed["edge_ksize"] = force_odd(
        read_int(fixed, "edge_ksize", 3, "核大小", notes), 1, 31, "核大小", notes)

    low = clamp_int(read_int(fixed, "edge_low", 50, "低阈值", notes), 0, 500, "低阈值", notes)
    high = clamp_int(read_int(fixed, "edge_high", 150, "高阈值", notes), 0, 500, "高阈值", notes)
    if low > high:
        notes.append("Canny 低/高阈值已互换（{0}/{1} → {2}/{3}）".format(low, high, high, low))
        low, high = high, low
    fixed["edge_low"], fixed["edge_high"] = low, high
    return fixed, notes, []


# ----------------------------------------------------------------------
# 算子声明表：注册表（NodeRegistry）会把每一条组装成 NodeSpec。
#   name             算子名（和左侧树、方框文字一致）
#   run              引擎调用的函数
#   format_result    执行日志"结果数据"列
#   param_specs      参数表：(参数名, 界面中文名, 控件类型, 附加选项)
#                    控件类型 int / float / combo / bool / file
#                    None 表示"这个算子走自己的专用参数窗口"，[]
#                    表示"有通用窗口但没有可调参数"
#   whole_image_param 该参数为真时忽略 ROI、作用于整幅图
# ----------------------------------------------------------------------
PROCESS_SPECS = (
    {
        "name": "灰度",
        "run": _run_gray,
        "format_result": lambda results: "执行成功（图像已灰度化，下游模块可见）",
        "param_specs": None,          # 灰度有自己的专用窗口（带"作用于整图"开关）
        "whole_image_param": "gray_full_image",
    },
    {
        "name": "取反",
        "run": _run_invert,
        "format_result": format_process,
        "param_specs": [],            # 没有可调参数，只按 ROI / 继承处理
    },
    {
        "name": "滤波",
        "run": _run_blur,
        "format_result": format_process,
        "validate": validate_blur,
        "param_specs": [
            ("blur_type", "滤波方式", "combo",
             {"options": ["均值", "高斯", "中值"], "default": "高斯"}),
            ("blur_ksize", "核大小", "int",
             {"min": 1, "max": 31, "default": 3, "odd": True}),
            ("blur_sigma", "高斯标准差", "float",
             {"min": 0.0, "max": 20.0, "step": 0.5, "decimals": 2, "default": 0.0}),
        ],
    },
    {
        "name": "二值化",
        "run": _run_threshold,
        "format_result": format_process,
        "validate": validate_threshold,
        "param_specs": [
            ("thresh_mode", "阈值方式", "combo",
             {"options": ["固定阈值", "Otsu", "自适应"], "default": "固定阈值"}),
            ("thresh_value", "阈值", "int", {"min": 0, "max": 255, "default": 127}),
            ("thresh_maxval", "最大值", "int", {"min": 0, "max": 255, "default": 255}),
            ("thresh_type", "类型", "combo",
             {"options": ["二值", "反二值"], "default": "二值"}),
        ],
    },
    {
        "name": "形态学",
        "run": _run_morphology,
        "format_result": format_process,
        "validate": validate_morphology,
        "param_specs": [
            ("morph_op", "运算", "combo",
             {"options": ["腐蚀", "膨胀", "开运算", "闭运算", "梯度", "顶帽", "黑帽"],
              "default": "腐蚀"}),
            ("morph_shape", "核形状", "combo",
             {"options": ["矩形", "椭圆", "十字"], "default": "矩形"}),
            ("morph_ksize", "核大小", "int",
             {"min": 1, "max": 31, "default": 3, "odd": True}),
            ("morph_iterations", "迭代次数", "int", {"min": 1, "max": 10, "default": 1}),
        ],
    },
    {
        "name": "边缘提取",
        "run": _run_edge,
        "format_result": format_process,
        "validate": validate_edge,
        "param_specs": [
            ("edge_method", "方法", "combo",
             {"options": ["Canny", "Sobel", "Laplacian"], "default": "Canny"}),
            ("edge_low", "低阈值", "int", {"min": 0, "max": 500, "default": 50}),
            ("edge_high", "高阈值", "int", {"min": 0, "max": 500, "default": 150}),
            ("edge_ksize", "核大小", "int",
             {"min": 1, "max": 31, "default": 3, "odd": True}),
        ],
    },
)
