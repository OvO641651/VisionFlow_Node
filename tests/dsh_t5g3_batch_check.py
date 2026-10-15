# -*- coding: utf-8 -*-
"""
批次5 目标3 验证：**"运行全部"分片执行**（不卡 / 能取消 / 行为等价）（2026.10.15）

    python dsh_t5g3_batch_check.py

背景：原来 `services/gallery_service.py::run_all_images` 是一个**同步 for 循环** ——
整个批量期间事件循环被占死 ⇒ 界面不刷新、连"停止"按钮的点击都排不上队
（用户实测："批量跑图时界面卡住，点了也停不下来"）。目标3 改成**分片**：
一张图 = 一个分片，片与片之间 `QTimer.singleShot(0, …)` 把控制权还给事件循环。

判据（每条都能回答"什么情况下为 False"）：

    ① 调用后**立刻返回**（返回计划张数）：返回时一张都还没跑、日志已被清空 —— 这就是"不阻塞"；
    ② 推进事件循环 ⇒ 逐张跑完 + 分片上下文清空 + "停止"标志复位 + 结尾写"运行全部结束：共执行 N/N 张"；
    ③ **行为等价**：分片跑出来的每张结果 与 "逐张直接 `_execute_static`" **逐像素一致**；
       而且 3 张图的结果**互不相同**（证明确实每张跑的都是它自己那张）；
    ④ 日志**逐张累积**（行数单调不减、至少长 3 档）；
    ⑤ **中途"停止"有效**：没跑满、已完成的结果与日志都保留、追加"用户停止，批量执行中断"、
       上下文清空、**还能再跑一批**；
    ⑥ 中途**取消勾选"运行全部"** ⇒ 立刻停（文案"已取消…"）；
    ⑦ 不勾"自动切换" ⇒ 跑完把**当前图**还原成开始时那张；勾着 ⇒ 跟随到最后一张；
    ⑧ 单张出错**跳过继续**（写"第 2 张出错已跳过"，整批不中断，结尾 2/3）；
    ⑨ 批量跑着时再点"连续执行" ⇒ 忽略（返回 0 + 一行"批量执行中，本次忽略"），不会开第二批；
    ⑩ **画布只在勾了「自动切换」时才跟随**：不勾 ⇒ 批量期间 `_display_image` **0 次**、整批只兜底还原 1 次；
       勾着 ⇒ 每张都刷（从头播到尾）；
    ⑪ **「自动切换」在批量开始时定格**：开始不勾、跑到一半拨上 ⇒ 这一批仍不刷画布、收尾照样还原
       （不会"自动播放到最后"）；开始勾着、中途拨回不勾 ⇒ 这一批继续跟随。中途拨动会写一行提示。
"""
import os
import sys
import tempfile

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np                            # noqa: E402
import cv2                                    # noqa: E402
from PySide2.QtWidgets import QApplication    # noqa: E402
from PySide2.QtCore import QPointF            # noqa: E402

app = QApplication([])
import main as m                              # noqa: E402
from core.ImageIO import write_image          # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


TMP = tempfile.mkdtemp(prefix="vf_t5g3_")


def make_images(n=3):
    """造 n 张**内容各不相同**的小图（内容不同才验得出"每张跑的都是自己那张"）"""
    paths = []
    for i in range(1, n + 1):
        img = np.full((48, 64, 3), 20 * i, np.uint8)
        cv2.rectangle(img, (4, 4), (20 + i * 4, 24), (255, 255, 255), 2)
        cv2.circle(img, (40, 30), 3 + i, (0, 0, 255), -1)
        p = os.path.join(TMP, "t5g3_img_%d.png" % i)
        assert write_image(p, img), "造测试图失败：%s" % p     # ★ 写图要断言，别学 cv2.imwrite 静默 False
        paths.append(p)
    return paths


def pump_until_idle(w, limit=8000):
    """推进事件循环直到分片批量跑完（分片是异步的，测试里这样"等它"）"""
    guard = 0
    while w._batch_state is not None and guard < limit:
        app.processEvents()
        guard += 1
    return guard


def pump_one_image(w, limit=8000):
    """推进到"至少跑完第 1 张"，返回那一刻的 done（用来做"中途停止"）"""
    guard = 0
    while w._batch_state is not None and w._batch_state["done"] < 1 and guard < limit:
        app.processEvents()
        guard += 1
    return None if w._batch_state is None else w._batch_state["done"]


def row_texts(w):
    out = []
    for r in range(w.execution_log.rowCount()):
        item = w.execution_log.item(r, 4)
        if item is not None:
            out.append(item.text())
    return out


def last_row_text(w):
    texts = row_texts(w)
    return texts[-1] if texts else ""


def build_flow(w):
    """一页最小流程：灰度（作用于整图）→ 取反 —— 每张图产出内容不同的结果"""
    n1 = w.add_flow_node("灰度", QPointF(20, 20))
    n2 = w.add_flow_node("取反", QPointF(20, 200))
    n1.params["gray_full_image"] = True
    w.add_edge(n1, n2)
    return n1, n2


# ======================================================================
# 准备：3 张测试图 + 一页流程 + 图库
# ======================================================================
paths = make_images(3)
w = m.MainWindow()
w.main_window.show()
build_flow(w)
w.import_paths(paths)
gw = w.gallery_widget
gw.auto_switch_box.setChecked(False)      # "不跟随"：这样"跑完还原"的逻辑也会被验到
gw.set_scope_all(True)                    # 范围 = 运行全部
gw.set_current_index(0)
w._show_static_image(gw.item_frame(gw.items()[0][0]))   # 当前图 = 第 1 张
app.processEvents()
frame_before = w.current_static_image
check("准备：图库 3 张图、流程 2 个节点、当前图 = 第 1 张",
      gw.count() == 3 and len(w.flow_nodes) == 2 and frame_before is not None,
      (gw.count(), len(w.flow_nodes), frame_before is None))

# ======================================================================
# ① 立刻返回（不阻塞）+ ④ 日志逐张累积
# ======================================================================
planned = w.run_all_images("continuous")
check("① `run_all_images` 立刻返回**计划张数**（3）", planned == 3, planned)
check("① 返回时一张都还没跑（分片上下文已建、done = 0）",
      w._batch_state is not None and w._batch_state["done"] == 0,
      None if w._batch_state is None else w._batch_state["done"])
check("① 返回时执行日志是空的（已清空 + 还没跑；不推进事件循环就一行都不会有）",
      w.execution_log.rowCount() == 0, w.execution_log.rowCount())

counts = []
guard = 0
while w._batch_state is not None and guard < 8000:
    app.processEvents()
    counts.append(w.execution_log.rowCount())
    guard += 1
check("④ 日志逐张累积：行数单调不减，且至少长了 3 档（3 张图 + 收尾行）",
      all(b >= a for a, b in zip(counts, counts[1:])) and len(set(counts)) >= 3,
      sorted(set(counts)))

# ======================================================================
# ② 跑完：上下文清空 + 标志复位 + 结尾文案
# ======================================================================
check("② 分片上下文已清空", w._batch_state is None)
check("② '停止'标志复位（下一次批量 / 播放是干净起点）", w._batch_stop is False, w._batch_stop)
check("② 结尾写了'运行全部结束：共执行 3/3 张'",
      last_row_text(w) == "运行全部结束：共执行 3/3 张", last_row_text(w))

# ======================================================================
# ③ 行为等价：分片结果 vs 逐张直接执行（逐像素）
# ======================================================================
batch_frames = {}
for _item, frame, path in gw.items():
    key = w._image_key_of(frame)
    entry = w.result_cache.get(w._result_cache_key(key, "continuous"))
    batch_frames[path] = None if entry is None else entry["frame"]
check("③ 3 张图都在结果缓存里留了'连续执行'那一份",
      all(f is not None for f in batch_frames.values()),
      [p for p, f in batch_frames.items() if f is None])

serial_frames = {}
w.result_cache.clear()
for _item, frame, path in gw.items():
    w.current_static_image = frame
    w._switch_image_params(w._image_key_of(frame))
    w._sync_source_nodes_to_path(path)
    w._execute_static(frame, "continuous")
    entry = w.result_cache.get(w._result_cache_key(w._image_key_of(frame), "continuous"))
    serial_frames[path] = None if entry is None else entry["frame"]
check("③ 分片跑出来的每张结果 = 逐张直接执行的结果（逐像素一致）",
      all(batch_frames[p] is not None and serial_frames[p] is not None
          and np.array_equal(batch_frames[p], serial_frames[p]) for p in batch_frames),
      sorted(batch_frames))
check("③ 3 张结果**互不相同**（证明确实每张跑的都是它自己那张）",
      len({f.tobytes() for f in serial_frames.values() if f is not None}) == 3)

# ======================================================================
# ⑦ 不勾"自动切换" ⇒ 还原当前图；勾着 ⇒ 跟随到最后一张
# ======================================================================
# （先重新摆好"开始时那张"：上面 ③ 的串行对照循环把 current_static_image 改成了最后一张）
gw.set_current_index(0)
w._show_static_image(gw.item_frame(gw.items()[0][0]))
app.processEvents()
frame_one = w.current_static_image
w.result_cache.clear()
w.run_all_images("continuous")
pump_until_idle(w)
ran_all = last_row_text(w) == "运行全部结束：共执行 3/3 张"
check("⑦ 不勾'自动切换'：跑满 3 张之后，当前图**还原成开始时那张**（第 1 张，不是最后一张）",
      ran_all and w.current_static_image is frame_one,
      (ran_all, w.current_static_image is frame_one))
gw.auto_switch_box.setChecked(True)
w.run_all_images("continuous")
pump_until_idle(w)
check("⑦ 勾'自动切换'：跑完选中项跟随到最后一张（第 3 张）",
      gw.current_index() == 2, gw.current_index())
check("⑦ 勾'自动切换'：当前图 = 最后那张（跟随）",
      w.current_static_image is gw.item_frame(gw.items()[2][0]),
      None if w.current_static_image is None else w.current_static_image.shape)
gw.auto_switch_box.setChecked(False)
gw.set_current_index(0)
w._show_static_image(gw.item_frame(gw.items()[0][0]))
app.processEvents()

# ======================================================================
# ⑤ 中途"停止"：没跑满 + 保留已完成 + 能再跑
# ======================================================================
w.run_all_images("continuous")
done_at_click = pump_one_image(w)
w.stop_batch()                            # = 点工具栏"停止"（或菜单里的停止）
pump_until_idle(w)
texts = row_texts(w)
check("⑤ 中途停止：批量被中断（不是跑满 3 张）",
      done_at_click is not None and done_at_click < 3 and
      any("用户停止，批量执行中断" in t for t in texts),
      (done_at_click, texts[-2:]))
check("⑤ 停之前跑完的那几张：结果留在缓存里（没白跑）",
      sum(1 for _i, f, _p in gw.items()
          if w.result_cache.get(w._result_cache_key(w._image_key_of(f), "continuous")) is not None) >= 1)
check("⑤ 上下文清空 + '停止'标志复位（还能再跑）",
      w._batch_state is None and w._batch_stop is False, (w._batch_state, w._batch_stop))
n2 = w.run_all_images("continuous")
pump_until_idle(w)
check("⑤ 停止之后还能再跑满一批（3/3）",
      n2 == 3 and last_row_text(w) == "运行全部结束：共执行 3/3 张", (n2, last_row_text(w)))

# ======================================================================
# ⑥ 中途取消勾选"运行全部" ⇒ 立刻停
# ======================================================================
gw.set_scope_all(True)
w.run_all_images("continuous")
done_at_uncheck = pump_one_image(w)
gw.set_scope_all(False)                   # 用户中途把范围切回"运行选中"
pump_until_idle(w)
texts = row_texts(w)
check("⑥ 中途取消勾选'运行全部' ⇒ 立刻停（文案'已取消“运行全部”'）",
      any("已取消" in t for t in texts), texts[-2:])
check("⑥ 只跑了 1 张就停（没跑满 3 张）",
      done_at_uncheck is not None and done_at_uncheck < 3 and
      not any("共执行 3/3" in t for t in texts), done_at_uncheck)
gw.set_scope_all(True)

# ======================================================================
# ⑧ 单张出错 ⇒ 跳过继续（不中断整批）
# ======================================================================
real_exec = w._execute_static
calls = {"n": 0}


def boom(frame, mode, node=None, adopt_frame=True, **kwargs):
    calls["n"] += 1
    if calls["n"] == 2:
        raise RuntimeError("测试用：第 2 张故意失败")
    return real_exec(frame, mode, node=node, adopt_frame=adopt_frame, **kwargs)


w._execute_static = boom
w.run_all_images("continuous")
pump_until_idle(w)
texts = row_texts(w)
check("⑧ 单张出错跳过继续：日志写了'第 2 张出错已跳过'",
      any("第 2 张出错已跳过" in t for t in texts), texts[-3:])
check("⑧ 出错那张被跳过、其余照跑（结尾 2/3）",
      last_row_text(w) == "运行全部结束：共执行 2/3 张", last_row_text(w))
del w._execute_static

# ======================================================================
# ⑨ 批量跑着时再点"连续执行" ⇒ 忽略（不开第二批）
# ======================================================================
w.run_all_images("continuous")
n_second = w.run_all_images("continuous")
check("⑨ 批量跑着时再点'连续执行' ⇒ 返回 0（被忽略）", n_second == 0, n_second)
check("⑨ 并写了一行'批量执行中，本次忽略'",
      any("批量执行中，本次忽略" in t for t in row_texts(w)), row_texts(w)[-3:])
pump_until_idle(w)
check("⑨ 第二批被忽略后，第一批照常跑完（3/3）",
      last_row_text(w) == "运行全部结束：共执行 3/3 张", last_row_text(w))

# ======================================================================
# ⑩ 画布跟随：**只有勾了「自动切换」才刷画面**（用户 2026.10.15 报的问题）
# ======================================================================
# 用户口径："只有选择了自动切换按钮才会在运行时自动切换画布的图片、把处理后的图从头播到尾；
#          现在不勾也会自动播放处理后的图片、最后再切回选中的那一张" ⇒ **不勾时画布必须全程不动**。
gw.set_current_index(0)
w._show_static_image(gw.item_frame(gw.items()[0][0]))
app.processEvents()

calls_off = []
real_disp = w._display_image


def spy_off(img, image_key=None):
    calls_off.append(1)
    return real_disp(img, image_key)


gw.auto_switch_box.setChecked(False)
w.result_cache.clear()
w._display_image = spy_off
w.run_all_images("continuous")
mid = []
guard = 0
while w._batch_state is not None and guard < 8000:
    app.processEvents()
    mid.append(len(calls_off))
    guard += 1
total_off = len(calls_off)
del w._display_image
check("⑩ 不勾'自动切换'：批量**期间**画布一次都没刷（不许自动播放处理后的图）",
      bool(mid) and all(n == 0 for n in mid[:-1]), sorted(set(mid)))
check("⑩ 不勾'自动切换'：整批只刷了 1 次（收尾那次兜底还原），不是每张都刷",
      total_off == 1, (mid, total_off))
check("⑩ 不勾'自动切换'：图**照样都算了**（3 张结果都在缓存 + 结尾 3/3）",
      last_row_text(w) == "运行全部结束：共执行 3/3 张"
      and sum(1 for _i, f, _p in gw.items()
              if w.result_cache.get(w._result_cache_key(w._image_key_of(f), "continuous"))
              is not None) == 3,
      (last_row_text(w), len(w.result_cache)))

calls_on = []


def spy_on(img, image_key=None):
    calls_on.append(1)
    return real_disp(img, image_key)


w._display_image = spy_on
gw.auto_switch_box.setChecked(True)
w.run_all_images("continuous")
pump_until_idle(w)
del w._display_image
gw.auto_switch_box.setChecked(False)
check("⑩ 勾'自动切换'：每张处理完都刷画布（= 从头播到尾，3 张 = 3 次）",
      len(calls_on) == 3, len(calls_on))

# ======================================================================
# ⑪ 「自动切换」在**批量开始时定格**：中途拨动不改变正在跑的这一批
# ======================================================================
# 用户第二次报的口径："我不开启自动切换运行连续执行后，再打开自动切换、没有再点执行按钮，
#   画布上的内容会自动播放到最后" ⇒ 根因 = 分片每片都重读开关 ⇒ 后半程"半途跟随"、
#   收尾又因为开关已是 ON 而不还原。修法：整批按**开始那一刻**的开关走。
gw.set_current_index(0)
w._show_static_image(gw.item_frame(gw.items()[0][0]))
app.processEvents()
frame_start = w.current_static_image

calls_mid = []
real_disp2 = w._display_image


def spy_mid(img, image_key=None):
    calls_mid.append(1)
    return real_disp2(img, image_key)


gw.auto_switch_box.setChecked(False)
w.result_cache.clear()
w._display_image = spy_mid
w.run_all_images("continuous")
guard = 0
while w._batch_state is not None and w._batch_state["done"] < 1 and guard < 8000:
    app.processEvents()
    guard += 1
gw.auto_switch_box.setChecked(True)          # ← 跑到一半把开关拨上（旧行为：后半程开始吐画面）
samples = [len(calls_mid)]
guard = 0
while w._batch_state is not None and guard < 8000:
    app.processEvents()
    samples.append(len(calls_mid))
    guard += 1
mid_total = len(calls_mid)
del w._display_image
check("⑪ 开始不勾、跑到一半拨上：这一批**仍然不刷画布**（开关在批开始时定格）",
      all(n == 0 for n in samples[:-1]), sorted(set(samples)))
check("⑪ 开始不勾…：收尾**照样还原**成开始时那张（不是停在最后一张）",
      mid_total == 1 and w.current_static_image is frame_start,
      (mid_total, w.current_static_image is frame_start))
check("⑪ 中途拨动时写了一行提示（'本批仍按开始时的设置'）",
      any("本批仍按开始时的设置" in t for t in row_texts(w)), row_texts(w)[-3:])

calls_on2 = []
w._display_image = lambda img, image_key=None: (calls_on2.append(1), real_disp2(img, image_key))[1]
gw.auto_switch_box.setChecked(True)
w.run_all_images("continuous")
guard = 0
while w._batch_state is not None and w._batch_state["done"] < 1 and guard < 8000:
    app.processEvents()
    guard += 1
gw.auto_switch_box.setChecked(False)         # ← 跑到一半拨回不勾
pump_until_idle(w)
del w._display_image
check("⑪ 开始勾着、跑到一半拨回不勾：这一批**继续跟随**（每张都刷 = 3 次）",
      len(calls_on2) == 3, len(calls_on2))
gw.auto_switch_box.setChecked(False)

print("-" * 70)
if fails:
    print("失败项：%d" % len(fails))
    for name in fails:
        print("   - " + name)
else:
    print("失败项：无")
sys.exit(1 if fails else 0)
