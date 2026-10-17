# -*- coding: utf-8 -*-
"""节点清单（树干 → 节点名）—— **零 Qt**。

谁在用：
    · 批次6 目标1-M4：右键画布空白处的**两级「添加节点」菜单**（一级 = 树干，二级 = 节点名）；
    · 目标2（后续）：左侧树上方搜索框的候选清单（**共用这一份**，别各写一套）。

为什么单独一个文件、为什么是"手写清单 + 门禁校验"：
    · 树的分组写在 `main.ui`（Qt 资源）里，`core/` **不能碰 Qt**；
      而 `NodeRegistry.NODE_SPECS` 只有"名字 → 声明"，**没有分组信息** ⇒ 分组只能在代码里表达一次；
    · 于是这里存一份**纯字符串**清单，再由门禁用例 `tests/dsh_t6_m4_check.py` 做**双向校验**：
      ① 清单里的节点**都在** `NODE_SPECS` 里（不多、不写错名）；
      ② 与 `main.ui` 里那棵树（去掉"测试"分组）**逐项一致、且顺序相同**（不漏、不乱序）。
      ⇒ 以后"加一个算子 / 改树的分组"，门禁会立刻报出来，不会悄悄漂移。

★ "警告（测试用）"是 M2b 的**测试夹具**，**不进用户菜单**（树里照旧保留，方便测出错/传播）。
"""

# 一级 = 树干（顺序与左侧树 **完全一致**）；二级 = 节点名（同样与树一致）
GROUPS = (
    ("采集", ("图片源", "视频源", "相机源", "输出图像")),
    ("处理", ("灰度", "取反", "滤波", "二值化", "形态学", "边缘提取")),
    ("检测识别", ("直线识别", "圆识别", "人脸识别")),
    ("颜色处理", ("颜色提取",)),
)

# 测试夹具分组（树里有、菜单里**没有**）
TEST_GROUP = "测试"
TEST_NODES = ("警告（测试用）",)


def is_user_node(name):
    """这个名字是不是"给用户的"节点（测试夹具不算）"""
    return name not in TEST_NODES


def groups(registered=None):
    """
    返回 `[(树干, [节点名, ...]), ...]`（**只含给用户的节点**）：

    :param registered: 已注册的节点名集合 / 字典（通常传 `NODE_SPECS`）；
                       传了就**只保留已注册的**（防止清单里写了名字但算子没登记）。
                       不传 ⇒ 延迟 import `NodeRegistry`（避免本模块被 import 时就拉起全部算子）。
    """
    if registered is None:
        from core.NodeRegistry import NODE_SPECS as registered
    names_ok = set(registered or ())
    out = []
    for group, names in GROUPS:
        kept = [n for n in names if (n in names_ok) and is_user_node(n)]
        if kept:
            out.append((group, kept))
    return out


def node_names(registered=None):
    """所有给用户的节点名（拍平）"""
    plain = []
    for _group, names in groups(registered):
        plain.extend(names)
    return plain


def group_of(name):
    """某个节点属于哪个树干（找不到 ⇒ None；测试夹具 ⇒ 返回 TEST_GROUP）"""
    if name in TEST_NODES:
        return TEST_GROUP
    for group, names in GROUPS:
        if name in names:
            return group
    return None
