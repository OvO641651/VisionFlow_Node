# -*- coding: utf-8 -*-
"""警告（测试用）—— 批次6 目标1-M2b 的**测试夹具**，不是业务算子。

用途（用户 2026.10.17 定）：验证"节点出错变红"和"错误沿数据流传播一跳"这两条机制 ——
把这个节点插到任意位置，它就会让自己（以及它的**直接下游第一个节点**）在执行后变红，
从而不必特意造一个真的会失败的场景。

约定与本项目其它算子一致：
  · `kind = process`（图像**原样透传**，不改数据）；
  · `results` 里带 `{"__error__": True}` ⇒ 走**通用错误通道**（日志那一行涂红）；
  · `format_result` 给执行日志"结果数据"列用。
"""
from core.NodeRegistry import KIND_PROCESS  # noqa: F401  （声明 kind 的语义说明用）


def _run_warn(detector, img, roi, params):
    """图像原样透传，只往结果里塞一个错误标记。"""
    return img, [{"__error__": True, "提示": "测试用：故意报错"}]


WARN_SPECS = [
    {
        "name": "警告（测试用）",
        "run": _run_warn,
        "format_result": lambda results: "测试用：故意报错（下游第一个节点会被标红）",
        "param_specs": [],            # 没有可调参数
    },
]
