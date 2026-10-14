# -*- coding: utf-8 -*-
"""
参数校验的公共零件（批次4 目标4「参数校验」）。

为什么要单独一个文件：
    同一张"规则表"要在**两个地方**各跑一遍 ——
      ① 参数窗口（`LineParamsDialog._validate_params()`）：用户点"执行 / 连续执行 / 确定"时，
         把能安全纠正的值改掉、并把"改了什么"显示在窗口里；
      ② 引擎（`main.py::_execute_node`）：真要把这个算子跑起来之前再查一次，
         专门挡住"方案文件 / 老方案里手改出来的非法值"；纠正不了的就把这个节点跳过去。
    两个地方都不想重复写"怎么夹取、怎么取奇数、读不出数字怎么办"这些琐碎判断，
    所以零件放这里。而 `ProcessOps.py` **不能** import `NodeRegistry.py`
    （注册表是反向 import 它的，会循环导入），所以零件也不能写在注册表里。
    本文件不依赖任何算子模块，谁都能 import。

统一约定（`NodeSpec.validate` 就是这个签名）：
    validate(params) -> (fixed_params, corrections, errors)
      fixed_params  纠正之后的参数（只有真的改了才会与入参不同；**缺的键不要补默认值**，
                    默认值是算子自己的事 —— 补进去会污染方案文件、还会干扰 M3 的"视频槽"比较）
      corrections   纠正说明（一条一句，已含"改前 → 改后"），给执行日志 / 窗口提示用
      errors        纠正不了的（引擎侧非空 ⇒ 跳过这个节点；窗口侧只提示、不拦）
    规则自己抛异常不许拖累执行：`run_validation()` 会兜住并转成一条 errors。

设计约束：**纯函数、O(1)、不做 IO**。视频播放时每秒会跑 25 次，规则里绝不许查文件是否存在。
"""


def read_int(params, key, default, label, notes):
    """把参数读成 int；读不出来（方案文件被手改坏了）就用默认值并记一条说明。"""
    try:
        return int(params.get(key, default))
    except (TypeError, ValueError):
        notes.append("{0}不是数字，已改用默认值 {1}".format(label, default))
        return int(default)


def read_float(params, key, default, label, notes):
    """把参数读成 float；读不出来就用默认值并记一条说明。"""
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        notes.append("{0}不是数字，已改用默认值 {1:g}".format(label, default))
        return float(default)


def clamp_int(value, low, high, label, notes):
    """把整数夹进 [low, high]；只有真的越界了才记说明（不许无脑加说明刷屏）。"""
    if value < low or value > high:
        fixed = max(low, min(high, int(value)))
        notes.append("{0}已夹到 {1}~{2}（原 {3}）".format(label, low, high, value))
        return fixed
    return int(value)


def clamp_float(value, low, high, label, notes):
    """把浮点夹进 [low, high]（口径同 clamp_int）。"""
    if value < low or value > high:
        fixed = max(low, min(high, float(value)))
        notes.append("{0}已夹到 {1:g}~{2:g}（原 {3:g}）".format(label, low, high, value))
        return fixed
    return float(value)


def force_odd(value, low, high, label, notes):
    """
    夹进 [low, high] 并强制成奇数。

    卷积核 / 形态学结构元 / Sobel·Laplacian 的 ksize 都要求"正奇数"，
    否则 OpenCV 直接抛异常（实测 cv2.GaussianBlur((4,4)) / getStructuringElement((0,0)) 都会 assert）。
    这里与 `ProcessOps._odd()` 同一个口径：那边是**算法侧的兜底**（保证不崩），
    这边是**参数侧的说明**（让用户知道值被改了）。
    """
    fixed = max(low, min(high, int(value)))
    if fixed % 2 == 0:
        fixed = fixed + 1 if fixed < high else fixed - 1
    fixed = max(low, min(high, fixed))
    if fixed != int(value):
        notes.append("{0}必须是 {1}~{2} 内的奇数，已改为 {3}（原 {4}）".format(
            label, low, high, fixed, int(value)))
    return fixed


def run_validation(spec, params):
    """
    跑一遍某个算子的参数校验（窗口层与引擎层共用的唯一入口）。

    :param spec: `NodeRegistry.get_spec(节点名)` 的结果；None（模块未实现）或没有规则 ⇒ 直接放行
    :param params: 节点当前参数（不会被就地改动，副本返回）
    :return: (fixed_params, corrections, errors)
    """
    current = dict(params or {})
    rule = getattr(spec, "validate", None) if spec is not None else None
    if rule is None:
        return current, [], []
    try:
        fixed, corrections, errors = rule(current)
    except Exception as exc:
        # 规则自己写坏了不许把执行带崩：转成一条 errors，引擎侧会"跳过这个节点 + 写日志"
        return current, [], ["参数校验规则异常（{0}）".format(exc)]
    # ★ 只把"入参里本来就有的键"写回去。
    #   规则为了取值方便，会把各键的**默认值**也一起填进 fixed；但默认值不算"纠正"——
    #   要是把默认值灌进 node.params，会 ① 把一堆默认值写进方案文件；
    #   ② 让 M3 的"视频参数整段共用"把"本来空参数的节点"误判成"参数变了"，
    #   每轮多写一行"已载回这段视频上一次的参数"提示（2026.10.7 实测踩到，靠门禁用例抓出来的）。
    fixed = {key: value for key, value in (fixed or {}).items() if key in current}
    return fixed, list(corrections or []), list(errors or [])
