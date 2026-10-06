# -*- coding: utf-8 -*-
"""
输出类算子（批次4 目标3-M5「输出图像」，2026.10.7）。

和 ProcessOps.py / SourceOps.py 一样，本文件**只导出声明**、不 import NodeRegistry
（注册表在末尾统一 `_register_category` 汇总，这样"注册表 ←→ 分类模块"不会循环导入）。

## 这个算子干什么

把它**从上游拿到的那张数据层图像**写到磁盘：
    · 放流程**末尾**：存的就是整条链处理完的结果（最常见）；
    · 放流程**中间**：它**原样透传**（`return img`，连副本都不建），下游拿到的是同一个对象，
      所以"中间插一个输出节点"不会改变任何下游结果。

## 三条设计约定（用户 2026.10.7 拍板）

1. **存的是数据层图像**，不是屏幕上那张 —— 数据层/渲染层分离是项目铁律：
   绿线 / 红圆 / ROI 黄框只属于显示层，永远不进数据层，所以也不会进文件。
2. **单步执行选中本节点 = 按既有语义只跑它自己**，输入沿"图像源"绑定追到起点那张图 ⇒
   存下来的是那张起点原图；**要存处理后的结果请用「连续执行」**。
3. **参数必须按"流程级配置"处理，绝不能按图片归档**（见 main.py 的 `_is_flow_level_node()`）：
   参数归档是"整份 params 按图片存取 + 载入前 clear()"，如果输出节点跟着图片走，
   用户换一张图之后"输出目录 / 文件名"就会被清空。

## V1 范围

只做**单帧图片**（png / jpg / bmp / tiff）+ 输出目录 + 文件名 + 重名策略。
保存成视频（VideoWriter）、带检测叠加、每 N 帧存一张 ⇒ 留 M5-2 / M5-3（见技术方案《九、想法》）。
"""

import os
import re
import time

import cv2

# 支持的图片格式 → 扩展名
FORMATS = (
    ("PNG（无损，推荐）", ".png"),
    ("JPG（有损，文件小）", ".jpg"),
    ("BMP（无压缩）", ".bmp"),
    ("TIFF（无损）", ".tiff"),
)
FORMAT_NAMES = [item[0] for item in FORMATS]
_EXT_OF_FORMAT = dict(FORMATS)

# 重名策略
POLICY_AUTO = "自动编号"
POLICY_OVERWRITE = "覆盖同名"
POLICY_TIME = "按时间戳"
POLICY_NAMES = [POLICY_AUTO, POLICY_OVERWRITE, POLICY_TIME]

# 「保存内容」（用户 2026.10.7 要求）：
#   · 数据层图像 —— 纯处理结果（灰度 / 二值化 / 取反……）；
#   · 带检测叠加 —— 把**检测类算子的结果**（绿线 / 红圆 / 圆心）画上去。
#     为什么需要它：检测类算子按引擎铁律**不改图像**（只多产出一份结果数据），
#     所以"直线 / 圆"这种流程如果存数据层，存出来的就是原始画面、看不到任何检测内容。
#   · 只画**检测结果**，不画 ROI 辅助框（那是调参用的辅助线，存进文件没意义）。
#   · 默认 = 带检测叠加：没有检测结果的流程（纯处理链）两者像素完全一样，
#     有检测结果的流程才看得出差别 —— 所以默认它不会改变原有表现，却能让检测内容存下来。
SAVE_LAYER = "数据层图像"
SAVE_OVERLAY = "带检测叠加"
SAVE_CONTENT_NAMES = [SAVE_LAYER, SAVE_OVERLAY]

# ----------------------------------------------------------------------
# 「输出类型」（M5-2，用户 2026.10.7 拍板）
#   自动 = 跟输入走：图片源 ⇒ 图片序列；视频源 / 相机源 ⇒ 视频文件
#   （用户原话："如果输入是视频文件则保存为检测处理后的视频文件，如果输入是摄像头则保存为
#     检测处理后的摄像头拍摄到的视频文件"）
# ----------------------------------------------------------------------
KIND_AUTO = "自动"
KIND_IMAGES = "图片序列"
KIND_VIDEO = "视频文件"
OUTPUT_KIND_NAMES = [KIND_AUTO, KIND_IMAGES, KIND_VIDEO]

# 来源种类（主窗口每轮执行前告诉节点"这一轮吃的图是从哪来的"）
SOURCE_IMAGE = "图片"
SOURCE_VIDEO = "视频"
SOURCE_CAMERA = "相机"

# 视频格式：(界面名, 扩展名, fourcc)
#   实测过本机 OpenCV 4.13：下面三种都能写能读；**H.264(avc1) 不放进来** ——
#   它依赖本机没有的 openh264 dll，会打印 "Failed to load OpenH264 library"，
#   靠回退"侥幸"能写但不保证（别把不稳的东西做成选项）。
#   体积参考（1280×720 / 25fps，实测）：mp4v ≈ 7.7 MB/分钟，XVID ≈ 7.9 MB/分钟，MJPG ≈ 23 MB/分钟。
VIDEO_FORMATS = (
    ("MP4（mp4v，体积小，推荐）", ".mp4", "mp4v"),
    ("AVI（XVID，体积小）", ".avi", "XVID"),
    ("AVI（MJPG，最兼容、体积大）", ".avi", "MJPG"),
)
VIDEO_FORMAT_NAMES = [item[0] for item in VIDEO_FORMATS]
_VIDEO_OF_NAME = dict((item[0], item) for item in VIDEO_FORMATS)

# "这一轮的执行上下文"取用器（主窗口注入）：() -> {"node_key": 节点标识, "source_kind": 来源种类,
# "source_fps": 来源帧率}
#   为什么要它：`run()` 只收到图像数组，拿不到"这一轮是哪个节点、图是视频还是相机来的、源帧率多少"，
#   而这三点分别决定"用哪个录制文件""要不要自动录成视频""标称帧率取多少"。
#   （做法与相机取帧器、文件名取名字器一致；node_key 让**每个输出节点各自一个录制文件**。）
ROUND_INFO_PROVIDER = None

# 正在录制的文件：{node_key: {"writer","path","size","frames","signature","fps","label"}}
#   故意放内存：录制状态不该进 params（会被写进 .vfproj、也会被按图归档）
_RECORDINGS = {}


def set_round_info_provider(fn):
    """主窗口注入"这一轮的执行上下文"取用器"""
    global ROUND_INFO_PROVIDER
    ROUND_INFO_PROVIDER = fn


def current_round_info():
    """"这一轮的执行上下文"（拿不到就返回空字典，各处的默认值会兜住）"""
    provider = ROUND_INFO_PROVIDER
    if not callable(provider):
        return {}
    try:
        return dict(provider() or {})
    except Exception:
        return {}

# "带检测叠加"那张图的取图器（主窗口注入）：() -> np.ndarray | None
#   为什么要注入：run() 只收到数据层图像，拿不到"这一轮上游检测出来的绿线红圆"；
#   主窗口在执行到"输出图像"节点的那一刻，把"只画检测结果、不画 ROI 框"的合成图算好交进来
#   （做法与相机取帧器、文件名取名字器一致）。
OVERLAY_PROVIDER = None


def set_overlay_frame_provider(fn):
    """主窗口注入"这一轮带检测叠加的那张图"取图器"""
    global OVERLAY_PROVIDER
    OVERLAY_PROVIDER = fn


def current_overlay_frame():
    """"这一轮带检测叠加的那张图"（拿不到就返回 None，调用方退回数据层图像）"""
    provider = OVERLAY_PROVIDER
    if not callable(provider):
        return None
    try:
        return provider()
    except Exception:
        return None

# 文件名里不允许出现的字符（Windows 下会直接写失败）
_BAD_NAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')

# 自动编号的"下一个可用序号"缓存：{(目录, 名字, 后缀): 下一个序号}
#   为什么不用"每次扫目录"：视频 / 相机逐帧保存时会变成 O(n²)；
#   为什么要扫一次目录：关掉软件重开之后接着上次的序号往下排，绝不覆盖旧文件。
_NEXT_INDEX = {}

# ----------------------------------------------------------------------
# "输入图片的文件名"取名字器（主窗口注入，做法同相机那套 set_camera_frame_provider）
#
# 用户 2026.10.7 要求："输出文件名的默认值 = 输入图片的文件名"。
#   · 参数窗口打开时用它当默认值（见 GenericProcessDialog 的 default_from）；
#   · 用户把文件名**留空**时，保存那一刻再用它兜底 ⇒ 逐张图各自的名字
#     （"运行全部"跑一整个图库时，每张图用自己的文件名）。
# 节点自己拿不到"图片路径"（run() 只收到图像数组），所以由主窗口在每一轮执行前
# 把"这一轮的来源图片名"准备好，这里只负责读。
# ----------------------------------------------------------------------
INPUT_NAME_PROVIDER = None      # 主窗口注入：() -> str（不含扩展名；拿不到就返回空串）


def set_input_name_provider(fn):
    """主窗口注入"这一轮输入图片的文件名"取名字器"""
    global INPUT_NAME_PROVIDER
    INPUT_NAME_PROVIDER = fn


def current_input_name():
    """"这一轮输入图片的文件名"（没有就返回空串）"""
    provider = INPUT_NAME_PROVIDER
    if not callable(provider):
        return ""
    try:
        return str(provider() or "")
    except Exception:
        return ""


def _sanitize_name(name):
    """把用户填的文件名清洗成磁盘上合法的名字（空则退回 "output"）"""
    cleaned = _BAD_NAME_CHARS.sub("_", str(name or "")).strip().strip(".")
    return cleaned or "output"


def _resolve_dir(output_dir):
    """
    把参数里的输出目录解析成绝对路径。

    相对路径**相对工程根**解析（不能靠当前工作目录：换一个目录启动就会写歪）。
    工程根 = 本文件所在目录（main.py / OutputOps.py 都在根下）。
    """
    text = str(output_dir or "").strip()
    if not text:
        return ""
    text = os.path.expanduser(os.path.expandvars(text))
    if os.path.isabs(text):
        return os.path.normpath(text)
    root = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(root, text))


def _scan_next_index(folder, base, ext, start=1):
    """
    扫一遍目录里已经存在的 `名字_数字.后缀`，返回"最大序号 + 1"。

    这样"关软件 → 隔天再跑"也不会把上次存的文件覆盖掉。
    """
    pattern = re.compile(r"^" + re.escape(base) + r"_(\d+)" + re.escape(ext) + r"$",
                         re.IGNORECASE)
    biggest = start - 1
    try:
        for entry in os.listdir(folder):
            match = pattern.match(entry)
            if match:
                try:
                    biggest = max(biggest, int(match.group(1)))
                except ValueError:
                    continue
    except OSError:
        # 目录还不存在 / 读不了：交给后面 makedirs 与 imwrite 去如实报错
        return start
    return biggest + 1


def _next_auto_index(folder, base, ext):
    """自动编号：拿"下一个可用序号"（缓存 + 存在性兜底）"""
    key = (folder.lower(), base, ext.lower())
    index = _NEXT_INDEX.get(key)
    if index is None:
        index = _scan_next_index(folder, base, ext)
    # 兜底：万一算出来的名字已经被占了（用户手动放了一个同名文件），往后让
    while os.path.exists(os.path.join(folder, "{0}_{1:04d}{2}".format(base, index, ext))):
        index += 1
    _NEXT_INDEX[key] = index + 1
    return index


def _free_path(path):
    """
    这个路径已经被占了的话，就在文件名后面加 `_1` / `_2` … 找一个空位。

    只有"按时间戳"策略用它（两次保存落在同一毫秒时会撞名，不能因此把上一次的覆盖掉）。
    """
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists("{0}_{1}{2}".format(base, n, ext)):
        n += 1
    return "{0}_{1}{2}".format(base, n, ext)


def build_output_path(params, ext=None):
    """
    按参数算出这一次要写的完整路径。
    :param ext: 指定扩展名（视频模式用，例如 ".mp4"）；不传就按"图片格式"参数推。
    :return: (路径, 说明)。路径为空字符串表示"参数不完整，没法存"。
    """
    folder = _resolve_dir(params.get("output_dir"))
    if not folder:
        return "", "没有设置输出目录"
    # 文件名为空 ⇒ 自动用"这一轮输入图片的文件名"（用户 2026.10.7 要求：
    # 默认值就是输入图片的文件名；他填了就用他填的）
    raw_name = str(params.get("output_name") or "").strip() or current_input_name()
    base = _sanitize_name(raw_name)
    if not ext:
        ext = _EXT_OF_FORMAT.get(params.get("output_format"), ".png")
    policy = params.get("name_policy") or POLICY_AUTO

    if policy == POLICY_OVERWRITE:
        return os.path.join(folder, base + ext), ""
    if policy == POLICY_TIME:
        stamp = time.strftime("%Y%m%d_%H%M%S") + "_{0:03d}".format(int(time.time() * 1000) % 1000)
        return _free_path(os.path.join(folder, "{0}_{1}{2}".format(base, stamp, ext))), ""
    index = _next_auto_index(folder, base, ext)
    return os.path.join(folder, "{0}_{1:04d}{2}".format(base, index, ext)), ""


def _resolve_fps(params, info):
    """
    录制用的标称帧率：① 参数里手填的（>0 就用它）；② 来源帧率（视频源读到的 / 相机读到的）；
    ③ 都拿不到就 25（和 SourceOps 里视频 fps 坏值的兜底保持一致）。

    口径说明（用户 2026.10.7 拍板）：**按"每写一帧算一帧"**，标称帧率只影响播放速度，
    不去按墙上时间推算真实帧率（那样"点一帧写一帧"的时长会乱跳）。
    """
    try:
        manual = float(params.get("video_fps") or 0)
    except (TypeError, ValueError):
        manual = 0.0
    if manual > 0.1:
        return max(1.0, min(240.0, manual))
    try:
        source = float(info.get("source_fps") or 0)
    except (TypeError, ValueError):
        source = 0.0
    if source > 0.5:
        return max(1.0, min(240.0, source))
    return 25.0


def _close_recording(state, reason):
    """收尾一个录制文件：释放编码器；一帧都没写就删掉空文件。返回给日志用的一句话。"""
    if state is None:
        return ""
    try:
        state["writer"].release()
    except Exception:
        pass
    name = os.path.basename(state.get("path") or "")
    if state.get("frames", 0) <= 0:
        # 一帧都没写：这种文件打不开，直接删掉，别给用户留一个坏文件
        try:
            if state.get("path") and os.path.exists(state["path"]):
                os.remove(state["path"])
        except OSError:
            pass
        return "已取消录制（一帧都没写，{0}；{1}）".format(reason, name)
    return "录制结束（{0}），共 {1} 帧，已保存 {2}".format(reason, state["frames"], name)


def close_recording(node_key, reason="结束"):
    """收尾某个节点的录制（返回给日志用的一句话；没在录就返回空串）"""
    return _close_recording(_RECORDINGS.pop(node_key, None), reason)


def close_all_recordings(reason="结束"):
    """收尾所有正在录制的文件（「停止」/ 换页 / 删节点 / 关程序 / 关闭相机都调它）"""
    messages = []
    for key in list(_RECORDINGS):
        message = close_recording(key, reason)
        if message:
            messages.append(message)
    return messages


def recording_count():
    """现在有几个文件在录制（给测试和界面反馈用）"""
    return len(_RECORDINGS)


def _save_image_file(img, target, params):
    """图片序列模式：把这一帧写成一张图片（M5-1 的原有行为）"""
    path, why = build_output_path(params)
    if not path:
        # 用户口径（2026.10.7）：输出目录"必须每次手填"（建节点后在参数窗口里设一次）。
        # 没填不弹窗、也不偷偷写到某个默认目录，只如实写进执行日志（项目准则：执行路径绝不弹窗）。
        return img, [{"输出图像": "未保存：{0}（请在“输出图像”节点的参数窗口里设置）".format(why)}]

    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)      # 目录不存在就自动建
        ok = cv2.imwrite(path, target)
    except Exception as exc:                        # 无权限 / 非法路径 / 磁盘满 …
        return img, [{"输出图像": "保存失败：{0}".format(exc)}]

    if not ok:
        return img, [{"输出图像": "保存失败：{0}".format(path)}]

    height, width = target.shape[:2]
    return img, [{"输出图像": "已保存 {0}（{1}×{2}）".format(
        os.path.basename(path), width, height)}]


def _save_video_frame(img, frame, params, info):
    """
    视频文件模式：把这一帧写进正在录制的文件（没有就**自动开始录制**）。

    生命周期（用户 2026.10.7 拍板，按推荐）：
      · **第一次执行到本节点时自动开始**：用第一帧定尺寸与帧率，日志写"开始录制 → …"；
      · 之后每次执行写一帧，日志写"录制中：…（第 n 帧）"；
      · 收尾由主窗口发起（「停止」/ 视频播到末尾 / 换页 / 删节点 / 关程序 / 关闭相机），
        见 `close_recording()` / `close_all_recordings()`；
      · **画面尺寸变了、或者输出参数改了** ⇒ 先收尾旧文件，再另开一个新文件（不硬塞，免得写花）。
    """
    label, ext, fourcc = _VIDEO_OF_NAME.get(params.get("video_format")) or VIDEO_FORMATS[0]
    folder = _resolve_dir(params.get("output_dir"))
    if not folder:
        return img, [{"输出图像": "未录制：没有设置输出目录（请在“输出图像”节点的参数窗口里设置）"}]

    base = _sanitize_name(str(params.get("output_name") or "").strip() or current_input_name())
    policy = params.get("name_policy") or POLICY_AUTO
    content = params.get("save_content") or SAVE_OVERLAY
    fps = _resolve_fps(params, info)
    size = (int(frame.shape[1]), int(frame.shape[0]))
    signature = (folder.lower(), base, label, policy, fps, content)
    key = info.get("node_key")

    notes = []
    state = _RECORDINGS.get(key)
    if state is not None and (state["size"] != size or state["signature"] != signature):
        notes.append(_close_recording(state, "画面尺寸或输出参数变了"))
        # ★ 收尾之后必须**把它从录制表里摘掉**，否则下面 `key not in _RECORDINGS` 判不出来、
        #   不会另开新文件，还会往一个已经 release 的 writer 里继续写（帧就悄悄丢了）。
        #   （这条是 M5-2 用例④"尺寸变化要另开文件"抓出来的真 bug。）
        _RECORDINGS.pop(key, None)

    if key not in _RECORDINGS:
        path, why = build_output_path(params, ext=ext)
        if not path:
            return img, [{"输出图像": "未录制：{0}（请在“输出图像”节点的参数窗口里设置）".format(why)}]
        try:
            os.makedirs(folder, exist_ok=True)
            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*fourcc), fps, size)
        except Exception as exc:                    # 无权限 / 非法路径 / 磁盘满 …
            return img, [{"输出图像": "保存失败：{0}".format(exc)}]
        if not writer.isOpened():
            try:
                writer.release()
            except Exception:
                pass
            # 编码器不支持：如实写日志、**不弹窗**，图像照旧透传（项目准则）
            return img, [{"输出图像": "保存失败：不支持该视频格式（{0}）".format(label)}]
        _RECORDINGS[key] = {"writer": writer, "path": path, "size": size, "frames": 0,
                            "signature": signature, "fps": fps, "label": label}
        notes.append("开始录制 → {0}（{1:g} fps，{2}×{3}）".format(
            os.path.basename(path), fps, size[0], size[1]))

    state = _RECORDINGS[key]
    try:
        state["writer"].write(frame)
    except Exception as exc:
        _RECORDINGS.pop(key, None)
        return img, [{"输出图像": "保存失败：{0}".format(exc)}]
    state["frames"] += 1
    notes.append("录制中：{0}（第 {1} 帧）".format(
        os.path.basename(state["path"]), state["frames"]))
    return img, [{"输出图像": "；".join(notes)}]


def run_save(detector, img, roi, params):
    """
    输出图像：把这一帧写进磁盘（图片或视频），然后把图像**原样透传**给下游。

    故意"什么都不改"：这个节点只往外送结果，不参与算法
    （所以它放流程中间、末尾都可以，下游拿到的还是同一个对象）。

    :param img: 上游那一份数据层图像（原图坐标）
    :param roi: (x, y, w, h) 本节点这一轮实际用的 ROI（这个节点不用它）
    :return: (img, [{"输出图像": 日志文案}])
    """
    info = current_round_info()

    # 1、这一帧要存"哪一层"：数据层图像 / 带检测叠加（用户 2026.10.7 要求）
    target = img
    if (params.get("save_content") or SAVE_OVERLAY) == SAVE_OVERLAY:
        overlay = current_overlay_frame()
        if overlay is not None:
            target = overlay

    # 2、存图片还是存视频：默认"自动"，跟输入走
    #    （图片源 ⇒ 图片序列；视频源 / 相机源 ⇒ 视频文件。用户 2026.10.7 拍板）
    kind = params.get("output_kind") or KIND_AUTO
    if kind == KIND_AUTO:
        kind = KIND_VIDEO if info.get("source_kind") in (SOURCE_VIDEO, SOURCE_CAMERA) \
            else KIND_IMAGES

    if kind == KIND_VIDEO:
        return _save_video_frame(img, target, params, info)
    return _save_image_file(img, target, params)


def format_save(results):
    """执行日志"结果数据"列：短文案"""
    if results and isinstance(results[0], dict):
        return str(results[0].get("输出图像", ""))
    return "输出图像"


# ----------------------------------------------------------------------
# 算子声明表：注册表（NodeRegistry）会把每一条组装成 NodeSpec(kind=KIND_SINK)
#   name / run / format_result / param_specs —— 含义同 ProcessOps.PROCESS_SPECS
# ----------------------------------------------------------------------
OUTPUT_SPECS = (
    {
        "name": "输出图像",
        "run": run_save,
        "format_result": format_save,
        "param_specs": [
            # 用户 2026.10.7：输出目录**必须每次手填**（建好节点后在参数窗口里设一次，不是每次运行都设），
            # 所以默认留空；留空时执行只写日志、不保存、也不弹窗。
            ("output_dir", "输出目录", "dir", {"default": ""}),
            # 文件名的默认值 = **输入图片的文件名**（用户 2026.10.7 要求）：
            # default_from 让参数窗口打开时自动带出"这个节点这一轮的输入图片名"；
            # 用户把它**留空**的话，保存那一刻也会自动跟随输入图片名（"运行全部"时每张图各用各的名字）。
            ("output_name", "输出文件名", "text",
             {"default": "", "default_from": "input_image_name",
              "placeholder": "留空 = 用输入图片的文件名"}),
            # 输出类型：默认"自动"——图片源存图片序列、视频源/相机源存视频文件（用户 2026.10.7 拍板）
            ("output_kind", "输出类型", "combo",
             {"options": OUTPUT_KIND_NAMES, "default": KIND_AUTO}),
            ("output_format", "图片格式", "combo",
             {"options": FORMAT_NAMES, "default": FORMAT_NAMES[0]}),
            # 视频格式 + 帧率（只有"视频文件"模式用得上；界面上一直显示，文案里说明）
            ("video_format", "视频格式", "combo",
             {"options": VIDEO_FORMAT_NAMES, "default": VIDEO_FORMAT_NAMES[0]}),
            ("video_fps", "视频帧率", "float",
             {"min": 0.0, "max": 240.0, "decimals": 1, "step": 1.0, "default": 0.0}),
            # 保存内容：默认"带检测叠加"（没有检测结果的流程两者完全一样，有检测结果的流程才看得出差别，
            # 所以默认它不会改变纯处理链的表现，却能让直线 / 圆的检测内容存下来）
            ("save_content", "保存内容", "combo",
             {"options": SAVE_CONTENT_NAMES, "default": SAVE_OVERLAY}),
            ("name_policy", "重名策略", "combo",
             {"options": POLICY_NAMES, "default": POLICY_AUTO}),
        ],
    },
)
