# -*- coding: utf-8 -*-
"""
相机源（"采集"分组）—— **一个节点一个文件**（2026.10.14 批次5 目标1 从 `SourceOps.py` 拆出）。

方案 A（目标3-M4，2026.10.7）：节点**复用主窗口相机**，不自己开设备
    · 主窗口启动时注入一个"取帧器"（`set_camera_frame_provider`）：返回相机**最新一帧**或 None；
    · `run_camera` 只读它、**并返回副本**（缓冲会被下一帧覆盖，绝不能把引用交出去）；
    · 取不到（相机没开 / 读失败）⇒ 原样透传传入的图 + 结果里带说明（日志会写，不弹窗）；
    · 相机是**无界流**：没有帧游标 / 循环参数；结果**不进缓存**（由主窗口跳过写入）。
"""
# 主窗口注入的取帧器：() -> np.ndarray | None
CAMERA_FRAME_PROVIDER = None


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


# 声明表（kind = KIND_SOURCE）
CAMERA_SOURCE_SPECS = [
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
]
