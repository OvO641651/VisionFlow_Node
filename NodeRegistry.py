# -*- coding: utf-8 -*-
"""
节点能力注册表（数据流引擎的"节点契约"）。

为什么要单独拎一个文件出来：
    以前 main.py 里靠 `if node.name == "直线": ... elif node.name == "圆": ...`
    一边判断节点类型、一边跑算法、一边拼日志文案。加一个算子要改好几处，
    而且日志里的"检测到N条直线"是写死的（用户 2026.8 提过这个问题）。
    现在每个算子只在这里登记一次，主引擎、参数窗口、执行日志就都认识它。

数据流引擎的两条铁律，都在这里体现：

    1、数据层与渲染层分离
       run()  负责改"数据"（图像 + 结果数据）
       draw() 负责画"显示"（绿线、红圆……）
       draw() 画的东西永远不会回到数据层，所以下游模块不可能"看见"上游画的线。

    2、影响必须由算子声明
       kind = process（处理类，比如灰度）：输出图像和输入不一样，下游看得见；
       kind = detect （检测类，比如直线/圆）：输出图像就是输入图像（原样透传），
                                            只多产出一份结果数据。
       检测类想影响下游，只有一条合法通道：下游节点把"ROI创建"选成"继承"，
       引擎用 result_bbox() 把上游结果算成包围盒，当作下游的 ROI。

新增一个算子要做的事：
    1、写 run(detector, img, roi, params) -> (out_img, results)
       处理类必须返回一张新图（绝不能就地改传进来的 img，否则会污染上游）；
       检测类原样 `return img, results` 就行，连副本都不用建。
    2、写 draw(display_img, results, params)（只有检测类需要）
    3、写 format_result(results) 供执行日志用
    4、在 NODE_SPECS 里登记一行
"""

import cv2

# 参数校验的公共零件（夹取 / 取奇数 / 读数字）：规则表本身写在下面各自的算子里，
# 零件抽出去是因为窗口层（LineParamsDialog）与引擎层（main.py::_execute_node）
# 都要用，而且 ProcessOps.py 不能反向 import 本文件（会循环导入）。
from ParamRules import clamp_float, clamp_int, read_float, read_int

# 全局图像源的标识：流程图的起点（就是用户导入的那一帧原图）
SOURCE_KEY = "__global_source__"
# "图像源"参数 = 自动（沿连线继承上游的图像输出）
AUTO_SOURCE = "__auto__"

# 算子类型
KIND_PROCESS = "process"    # 处理类：会改写数据层图像
KIND_DETECT = "detect"      # 检测类：图像透传，只产出结果
KIND_SOURCE = "source"      # 图像源类：流程的起点，自己"造"图（读文件 / 当前图像 / 测试图），没有上游
KIND_SINK = "sink"          # 输出类：图像**原样透传**，只把结果送出去（写磁盘等）——M5「输出图像」


class NodeSpec(object):
    """一个算子的能力声明"""

    def __init__(self, name, kind, run, draw=None, format_result=None, whole_image_param=None,
                 param_specs=None, validate=None):
        """
        :param name: 算子名字（和左侧树、流程图上方框里的文字一致）
        :param kind: KIND_PROCESS 或 KIND_DETECT
        :param run: run(detector, img, roi, params) -> (out_img, results)
                    roi 是 (x, y, w, h)，都是原图坐标
        :param draw: draw(display_img, results, params)，只画显示层；处理类不需要
        :param format_result: format_result(results) -> str，执行日志"结果数据"那一列
        :param whole_image_param: 参数名。该参数为真时这个算子忽略 ROI、作用于整幅图，
                                  引擎会把它的 ROI 当成整图（做到"所见即所算"）。
                                  目前只有灰度用它（gray_full_image）。
        :param validate: 参数校验规则（批次4 目标4）：
                                 validate(params) -> (fixed_params, corrections, errors)
                                 与 param_specs 一起声明在这个算子里；None = 还没有规则（直接放行）。
                                 同一张规则表会被跑**两遍**：参数窗口一次（纠正 + 提示）、
                                 引擎 _execute_node 一次（纠正 + 挡住非法值），零件见 ParamRules.py。
        :param param_specs: 参数声明表（决定"参数窗口"长什么样），每一项是
                            (参数名, 界面中文名, 控件类型, 附加选项)；
                            int / float / combo / bool / file 五种控件类型。
                            · None = 这个算子走"专用参数窗口"（直线 / 圆 / 灰度）
                            · []   = 走通用窗口，但没有可调参数（取反）
                            · 有内容 = 通用窗口按这张表自动生成控件（决策 b）
        """
        self.name = name
        self.kind = kind
        self.run = run
        self.draw = draw
        self.format_result = format_result
        self.whole_image_param = whole_image_param
        self.param_specs = param_specs
        self.validate = validate

    @property
    def modifies_image(self):
        """
        这个算子的输出图像会不会和输入不一样。
        处理类 = True；图像源类 = True（它读出来的是新图）；检测类 = False（原样透传）；
        输出类（KIND_SINK）= False（**原样透传**，它只是把结果送出去）。
        main.py 在多上游时用它挑"真正产出新图像"的那一支当默认图像源
        —— 输出类必须算 False，否则"中间插一个输出节点"会被误当成真正改图的那一支。
        """
        return self.kind in (KIND_PROCESS, KIND_SOURCE)

    @property
    def is_flow_level(self):
        """
        这个节点的参数是不是**流程级配置**（不按图片归档）。

        起点节点（图片源 / 视频源 / 相机源）的"来源 / 路径"属于流程图本身；
        输出类节点（输出图像）的"输出目录 / 文件名"同理 —— 它们都不该跟着"当前是哪张图"变。
        必须跳过按图归档，否则用户换一张图之后这些参数会被清掉（见 main.py）。
        """
        return self.kind in (KIND_SOURCE, KIND_SINK)


# ----------------------------------------------------------------------
# 处理类算子
#
# 处理类（灰度 / 取反 / 滤波 / 二值化 / 形态学 / 边缘提取）的算法、参数表、
# 结果文案都放在 ProcessOps.py 里，本文件只在下面把它们的声明汇总成 NodeSpec
# （这样"加一个处理类算子"= 改 ProcessOps.py + main.ui 树里加一项，不用动引擎）。
# 检测类算子（直线 / 圆）的算法依赖 DetectorShape，仍然登记在本文件下方。
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# 检测类算子
# ----------------------------------------------------------------------
def _run_line(detector, img, roi, params):
    """
    直线（检测类）：只在 ROI 的一份副本上跑算法，结果数据按原图坐标返回。

    注意 patch 后面的 .copy()：
        line_detector() 会顺手把绿线画进传进去的数组里，那是它的"副作用"。
        这里给的是副本，画完直接丢掉，绿线不会进数据层；
        真正的绘制交给 _draw_line() 在显示层做。
        如果忘了 copy()，画绿线时会把数据层图像改掉，下游就又"看见"绿线了。
    """
    x, y, w, h = roi
    patch = img[y:y + h, x:x + w].copy()
    _ignored, results = detector.line_detector(
        patch,
        roi_offset_x=x,
        roi_offset_y=y,
        canny_low=params.get("canny_low", 50),
        canny_high=params.get("canny_high", 150),
        threshold=params.get("hough_threshold", 100),
        min_line_length=params.get("min_line_length", 100.0),
        max_line_gap=params.get("max_line_gap", 10.0),
    )
    # 数据层图像原样透传（同一个对象，不复制）
    return img, results


def _run_circle(detector, img, roi, params):
    """圆（检测类）：和直线同理，只在 ROI 副本上跑，数据层图像透传"""
    x, y, w, h = roi
    patch = img[y:y + h, x:x + w].copy()
    _ignored, results = detector.circle_detector(
        patch,
        roi_offset_x=x,
        roi_offset_y=y,
        dp=params.get("dp", 1.0),
        min_dist=params.get("min_dist", 150.0),
        param1=params.get("param1", 100.0),
        param2=params.get("param2", 80.0),
        min_radius=params.get("min_radius", 20),
        max_radius=params.get("max_radius", 0),
    )
    return img, results


def _draw_line(display_img, results, params):
    """把直线结果画到显示层（绿色，和 Detector 里原来的画法一致）"""
    for item in results:
        if len(item) == 4:
            x1, y1, x2, y2 = item
            cv2.line(display_img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)


def _draw_circle(display_img, results, params):
    """把圆结果画到显示层（红色圆 + 红色圆心，和 Detector 里原来的画法一致）"""
    for item in results:
        if len(item) == 3:
            x, y, r = item
            cv2.circle(display_img, (int(x), int(y)), int(r), (0, 0, 255), 2)   # 红色圆
            cv2.circle(display_img, (int(x), int(y)), 2, (0, 0, 255), 3)        # 圆心


def _format_line(results):
    return "检测到{0}条直线".format(len(results))


def _format_circle(results):
    return "检测到{0}个圆".format(len(results))


# ----------------------------------------------------------------------
# 检测类的参数校验规则（批次4 目标4）
#
# 为什么直线的规则写在这里而不是 ProcessOps.py：
#     直线 / 圆的算子声明本来就登记在本文件（它们的算法在 Detector.py），
#     规则与"参数表"放一起，改动一个算子只动一处（与处理类放 ProcessOps 同一个道理）。
#
# 实测依据（cv2 4.13 / 2026.10.7）：
#     · Canny 低 > 高**不会崩**（OpenCV 内部自己交换）⇒ 我们互换只为让"参数值"与"实际生效值"一致；
#     · HoughLinesP 的 threshold=0 / minLineLength=0 **不崩**，但结果会暴增（实测 45 条 vs 正常）
#       ⇒ 纠正为 1 并写进说明；
#     · HoughCircles 的 param1 / param2 = 0 **会抛异常**，而圆窗口原先 setRange(0, 1000)
#       ⇒ 下限就是 0、**界面就能调到**（这是本次唯一"界面可达且会崩"的参数）；窗口下限已改成 1，
#       引擎侧这一层仍然保留——挡的是"方案文件里手改出来的 0"；
#     · dp=0 / minDist<=0 也抛异常，界面上够不到（0.1~10 / 10~10000），同样由引擎侧兜。
# ----------------------------------------------------------------------
def validate_line(params):
    """直线：Canny 高低阈值（夹范围 + 互换）、累加器阈值、最小线段长度、最大线段间隙"""
    fixed, notes = dict(params), []

    low = clamp_int(read_int(fixed, "canny_low", 50, "Canny 低阈值", notes),
                    0, 500, "Canny 低阈值", notes)
    high = clamp_int(read_int(fixed, "canny_high", 150, "Canny 高阈值", notes),
                     0, 500, "Canny 高阈值", notes)
    if low > high:
        notes.append("Canny 低/高阈值已互换（{0}/{1} → {2}/{3}）".format(low, high, high, low))
        low, high = high, low
    fixed["canny_low"], fixed["canny_high"] = low, high

    threshold = read_int(fixed, "hough_threshold", 100, "累加器阈值", notes)
    if threshold < 1:
        notes.append("累加器阈值已纠正为 1（原 {0}：阈值越小检出的线段越多、噪声也多）".format(threshold))
        threshold = 1
    fixed["hough_threshold"] = threshold

    min_len = read_int(fixed, "min_line_length", 100, "最小线段长度", notes)
    if min_len < 1:
        notes.append("最小线段长度已纠正为 1（原 {0}）".format(min_len))
        min_len = 1
    fixed["min_line_length"] = min_len

    gap = read_int(fixed, "max_line_gap", 10, "最大线段间隙", notes)
    if gap < 0:
        notes.append("最大线段间隙已纠正为 0（原 {0}）".format(gap))
        gap = 0
    fixed["max_line_gap"] = gap

    return fixed, notes, []


def validate_circle(params):
    """圆：param1 / param2（必须 ≥ 1）、dp、min_dist（界面上够不到，挡方案文件）"""
    fixed, notes = dict(params), []

    for key, label, default in (("param1", "Canny 高阈值（param1）", 100),
                                ("param2", "圆心累加器阈值（param2）", 80)):
        value = read_int(fixed, key, default, label, notes)
        if value < 1:
            notes.append("{0}已纠正为 1（原 {1}：OpenCV 要求大于 0，原先会直接报错）".format(label, value))
            value = 1
        fixed[key] = value

    dp = clamp_float(read_float(fixed, "dp", 1.0, "累加器分辨率 dp", notes),
                     0.1, 10.0, "累加器分辨率 dp", notes)
    fixed["dp"] = dp

    min_dist = read_int(fixed, "min_dist", 150, "圆心最小距离", notes)
    if min_dist < 1:
        notes.append("圆心最小距离已纠正为 1（原 {0}）".format(min_dist))
        min_dist = 1
    fixed["min_dist"] = min_dist

    return fixed, notes, []


# ----------------------------------------------------------------------
# 注册表
# ----------------------------------------------------------------------
NODE_SPECS = {
    "直线": NodeSpec("直线", KIND_DETECT, _run_line, _draw_line, _format_line,
                     validate=validate_line),
    "圆": NodeSpec("圆", KIND_DETECT, _run_circle, _draw_circle, _format_circle,
                   validate=validate_circle),
}


def _register_category(entries, kind):
    """
    把某个"分类模块"导出的声明表组装成 NodeSpec 登记进注册表。
    分类模块（ProcessOps.py / SourceOps.py）只导出声明、**不 import 本文件**，
    所以"注册表 ←→ 分类模块"不会循环导入。
    """
    for entry in entries:
        NODE_SPECS[entry["name"]] = NodeSpec(
            name=entry["name"],
            kind=kind,
            run=entry["run"],
            draw=None,
            format_result=entry.get("format_result"),
            whole_image_param=entry.get("whole_image_param"),
            param_specs=entry.get("param_specs"),
            validate=entry.get("validate"),      # 参数校验规则（批次4 目标4），没有就 None
        )


# 放在文件末尾 import：避免循环导入（注册表 ←→ 分类模块）
from ProcessOps import PROCESS_SPECS  # noqa: E402
from SourceOps import SOURCE_SPECS    # noqa: E402
from OutputOps import OUTPUT_SPECS    # noqa: E402

_register_category(PROCESS_SPECS, KIND_PROCESS)   # 处理类：灰度 / 取反 / 滤波 / 二值化 / 形态学 / 边缘提取
_register_category(SOURCE_SPECS, KIND_SOURCE)     # 图像源类：图片源 / 视频源 / 相机源
_register_category(OUTPUT_SPECS, KIND_SINK)       # 输出类：输出图像（M5）


def get_spec(name):
    """
    取算子的能力声明。
    :return: NodeSpec；返回 None 表示这个模块还没实现
             （引擎会原样透传图像、并在日志里如实写"模块未实现"，不再假装成功）
    """
    return NODE_SPECS.get(name)


def is_implemented(name):
    """这个模块实现了吗（人脸 / 颜色 目前还没实现）"""
    return name in NODE_SPECS


def result_bbox(results):
    """
    把一串结果算成"原图坐标"下的包围盒，供下游节点"ROI 继承"使用。

    支持两种结果格式（和 Detector 的输出一致）：
        直线：(x1, y1, x2, y2)  端点
        圆：  (cx, cy, r)       圆心 + 半径

    :return: (x, y, w, h)；没有任何可用结果时返回 None
    """
    xs = []
    ys = []
    for item in results or []:
        if not isinstance(item, (tuple, list)):
            continue
        if len(item) == 4:
            x1, y1, x2, y2 = item
            xs.extend([x1, x2])
            ys.extend([y1, y2])
        elif len(item) == 3:
            cx, cy, r = item
            xs.extend([cx - r, cx + r])
            ys.extend([cy - r, cy + r])
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
