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


# 参数校验的公共零件（夹取 / 取奇数 / 读数字）：规则表本身写在下面各自的算子里，
# 零件抽出去是因为窗口层（LineParamsDialog）与引擎层（main.py::_execute_node）
# 都要用，而且各"分类 / 节点模块"不能反向 import 本文件（会循环导入）。

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
# 结果文案都放在各自节点文件里，本文件只在下面把它们的声明汇总成 NodeSpec
# （这样"加一个处理类算子"= 加一个节点文件 + main.ui 树里加一项，不用动引擎）。
# 检测类算子（直线 / 圆）同样"一个节点一个文件"：见 ops/detect/ 下的两个文件。
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# 检测类算子：直线 / 圆（2026.10.14 起也是"一个节点一个文件"）
#
# 算法、引擎入口、显示层绘制、日志文案、参数校验、声明表都在各自文件里：
#     ops/detect/LineDetectOps.py    （LineDetector  + LINE_SPECS）
#     ops/detect/CircleDetectOps.py  （CircleDetector + CIRCLE_SPECS）
# 本文件只在下面把它们登记进注册表 —— 这样"改一个算子只动一个文件"。
# ----------------------------------------------------------------------
NODE_SPECS = {}


def _register_category(entries, kind):
    """
    把某个"分类模块"导出的声明表组装成 NodeSpec 登记进注册表。
    分类模块（各 `ops/*/` 下的节点文件）只导出声明、
    **不 import 本文件**，所以"注册表 ←→ 分类模块"不会循环导入。

    `draw` 也照传：检测类算子（人脸）要往显示层画框，2026.10.12 起允许分类模块声明它
    （原来是写死 None，只有本文件里手写的直线 / 圆能画）。
    """
    for entry in entries:
        NODE_SPECS[entry["name"]] = NodeSpec(
            name=entry["name"],
            kind=kind,
            run=entry["run"],
            draw=entry.get("draw"),
            format_result=entry.get("format_result"),
            whole_image_param=entry.get("whole_image_param"),
            param_specs=entry.get("param_specs"),
            validate=entry.get("validate"),      # 参数校验规则（批次4 目标4），没有就 None
        )


# 放在文件末尾 import：避免循环导入（注册表 ←→ 分类模块）
# 处理类 6 个节点（2026.10.14 起"一个节点一个文件"）
from ops.process.GrayOps import GRAY_SPECS
from ops.process.InvertOps import INVERT_SPECS
from ops.process.BlurOps import BLUR_SPECS
from ops.process.ThresholdOps import THRESHOLD_SPECS
from ops.process.MorphologyOps import MORPHOLOGY_SPECS
from ops.process.EdgeExtractOps import EDGE_SPECS
# 图像源类（"采集"分组）：2026.10.14 起**一个节点一个文件**
from ops.source.ImageSourceOps import IMAGE_SOURCE_SPECS      # noqa: E402
from ops.source.VideoSourceOps import VIDEO_SOURCE_SPECS      # noqa: E402
from ops.source.CameraSourceOps import CAMERA_SOURCE_SPECS    # noqa: E402
from ops.sink.OutputOps import OUTPUT_SPECS    # noqa: E402
# 检测 / 识别类（树里合并成"检测识别"分组）：2026.10.12 目标5-M2 起**一个节点一个文件**
from ops.detect.FaceDetectOps import FACE_SPECS       # noqa: E402
from ops.color.ColorExtractOps import COLOR_SPECS     # noqa: E402
# 检测类算子（直线 / 圆）：2026.10.14 起各自一个文件
from ops.detect.LineDetectOps import LINE_SPECS        # noqa: E402
from ops.detect.CircleDetectOps import CIRCLE_SPECS    # noqa: E402

_register_category(GRAY_SPECS, KIND_PROCESS)         # 处理类：灰度
_register_category(INVERT_SPECS, KIND_PROCESS)       # 取反
_register_category(BLUR_SPECS, KIND_PROCESS)         # 滤波
_register_category(THRESHOLD_SPECS, KIND_PROCESS)    # 二值化
_register_category(MORPHOLOGY_SPECS, KIND_PROCESS)   # 形态学
_register_category(EDGE_SPECS, KIND_PROCESS)         # 边缘提取
_register_category(IMAGE_SOURCE_SPECS, KIND_SOURCE)    # 图片源
_register_category(VIDEO_SOURCE_SPECS, KIND_SOURCE)    # 视频源
_register_category(CAMERA_SOURCE_SPECS, KIND_SOURCE)   # 相机源
_register_category(OUTPUT_SPECS, KIND_SINK)       # 输出类：输出图像（M5）
# 识别类的 kind 由"它到底改不改图"决定（分组是功能心智，kind 是引擎语义，两者不必一致）：
_register_category(FACE_SPECS, KIND_DETECT)       # 人脸：不改图，只产出人脸框（检测类）
_register_category(COLOR_SPECS, KIND_PROCESS)     # 颜色提取：改图（阈值外置黑），下游看得见（处理类）
_register_category(LINE_SPECS, KIND_DETECT)      # 直线：不改图，只出线段（检测类）
_register_category(CIRCLE_SPECS, KIND_DETECT)    # 圆：不改图，只出圆（检测类）


def node_level_param_keys(spec):
    """
    这个算子声明了哪些"**节点级参数**"（不按图片归档：换图 / 换视频 / 换页都保持不变）。

    声明方式：`param_specs` 里那一项 options 写 `"per_node": True`。
    现在只有「人脸」的级联文件用它 —— 用户 2026.10.12 实测报："更换图片后级联文件需要重新导入，
    可能是每幅图片的参数设置会重置导致……我希望这个人脸识别节点的级联文件每幅图都可以使用，
    不会更换图片后就重置。但是其他的节点的参数需要保持原样，每幅图片独立参数。"

    为什么级联文件该是节点级：它是"**这个节点用哪个模型文件**"的配置，
    跟"当前打开的是哪张图"没有任何关系；而缩放步长 / 邻居数 / 最小尺寸那些**调参**参数，
    用户明确要求"其他参数保持原样、每幅图独立" ⇒ 它们照旧按图片归档。

    :return: set（键名集合）；没有声明就返回空集合
    """
    keys = set()
    for entry in getattr(spec, "param_specs", None) or []:
        try:
            key, _label, _kind, options = entry
        except (TypeError, ValueError):
            # 声明表写坏了一项：跳过它，不要让参数窗口 / 引擎跟着崩
            continue
        if isinstance(options, dict) and options.get("per_node"):
            keys.add(key)
    return keys


def get_spec(name):
    """
    取算子的能力声明。
    :return: NodeSpec；返回 None 表示这个模块还没实现
             （引擎会原样透传图像、并在日志里如实写"模块未实现"，不再假装成功）
    """
    return NODE_SPECS.get(name)


def is_implemented(name):
    """
    这个模块实现了吗？
    （2026.10.12 目标5-M2 起："识别"分组的人脸 / 颜色提取都实现了 —— 树上每一项都有算子）
    """
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
