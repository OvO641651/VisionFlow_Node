# -*- coding: utf-8 -*-
"""算子名 → 图标键（**零 Qt**，批次6 目标1-M2a）。

为什么放 core/ 且只放"名字 → 键"的映射：
    · 项目落点规则：**零 Qt 的逻辑进 `core/`**、碰 Qt 的进 `widgets/`（见方案 §八）；
    · 图标**本批不用任何图片素材**（用户 2026.10.17 定"先占位"），画法在
      `widgets/node_visuals.py::draw_icon()`；
    · 将来（M5）换成真图标时，**只改这一张映射表 + 那个画法函数**，节点代码不动。

键名用英文，避免中文键在别的平台/编码下出幺蛾子。
"""

# 14 个已注册算子 + M2b 的测试用节点
ICON_KEYS = {
    "图片源": "image",
    "视频源": "video",
    "相机源": "camera",
    "输出图像": "save",
    "灰度": "gray",
    "取反": "invert",
    "滤波": "blur",
    "二值化": "threshold",
    "形态学": "morph",
    "边缘提取": "edge",
    "直线识别": "line",
    "圆识别": "circle",
    "人脸识别": "face",
    "颜色提取": "color",
    "警告（测试用）": "warn",
    # 树上的四个分组（分组本身不画在节点上，但留着供将来用）
    "采集": "group_source",
    "处理": "group_process",
    "检测识别": "group_detect",
    "颜色处理": "group_color",
}

# 没登记的算子（将来新加的）= 通用方块，保证"永远画得出来"
GENERIC = "generic"


def icon_key_for(name):
    """算子名 → 图标键；没登记的一律返回 GENERIC（画通用方块兜底）。"""
    return ICON_KEYS.get(str(name), GENERIC)
