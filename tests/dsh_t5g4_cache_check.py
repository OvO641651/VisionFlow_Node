# -*- coding: utf-8 -*-
"""
批次5 目标4-1：**结果缓存的上限 + 真 LRU（两池）**（2026.10.15）

    python dsh_t5g4_cache_check.py

背景：`self.result_cache`（键 = 图片 × 页面 × 执行方式）存"每张图算完的结果"，切回该图直接显示。
旧实现只有视频分支里一段"超过 400 条丢最旧"⇒ ① **静态图批量跑其实没有上限**；② 是 **FIFO 近似 LRU**
（命中缓存时不刷新顺序 ⇒ "刚看过的图照样被淘汰"）；③ 按条数不按内存。改成 `core/result_cache.py` 的
**两池 LRU**（静态池 400 条 / 256 MB；视频序列池 120 条 / 64 MB，用户 2026.10.15 拍板"乙"）。

判据（每条都能回答"什么情况下为 False"）：

    ① 静态池**条数上限**：超限就淘汰（丢最旧的）；
    ② ★ **真 LRU 判别**：填满 → **访问第 1 条** → 再填 1 张 ⇒ **第 1 条仍在、第 2 条被淘汰**
       （FIFO 近似会淘汰"第 1 条"⇒ 这条断言能把两种实现区分开，是本轮最硬的判据）；
    ③ 静态池**字节上限**：只按字节也能触发淘汰；
    ④ **视频序列帧单独分池**：序列池满只挤序列池，**静态图结果不受影响**；
    ⑤ 淘汰后重算 = **逐像素一致**（淘汰不影响正确性）；
    ⑥ 删图库项 ⇒ 该图的缓存按图清掉（既有行为不回归）；
    ⑦ 日志写完**自动滚到最后一行**（`scrollToBottom`，用户提问"日志太长看不见"的修法）；
    ⑧ 上限常量本身合理（正数、序列池 ≤ 静态池、`is_sequence_key` 分类正确）。
"""
import os
import sys

import numpy as np

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication        # noqa: E402
from PySide2.QtCore import QPointF                # noqa: E402
app = QApplication([])
import main as m                                  # noqa: E402
from core import result_cache as rc               # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


w = m.MainWindow()
w.main_window.show()
gw = w.gallery_widget


def img(path, size=(100, 100), value=10, win=None):
    """造一张小图并登记成"来自这个文件"（`_image_key_of` 就是查 window._frame_paths）
    ★ `win` 必须传"这张图要交给哪个窗口"—— 登记错窗口的话键就不是文件路径了（本用例踩过）。"""
    frame = np.full((size[1], size[0], 3), value, np.uint8)
    (win or w)._frame_paths[id(frame)] = path
    return frame


def run(frame):
    w._execute_static(frame, "continuous")


def key_of(path):
    return w._result_cache_key(path, "continuous")


ORIG = (rc.STATIC_MAX_ITEMS, rc.STATIC_MAX_BYTES, rc.SEQUENCE_MAX_ITEMS, rc.SEQUENCE_MAX_BYTES)


def restore():
    """把两个池的上限还原成工程里的默认值（用例前面几组会临时改小来触发淘汰）"""
    rc.STATIC_MAX_ITEMS, rc.STATIC_MAX_BYTES, rc.SEQUENCE_MAX_ITEMS, rc.SEQUENCE_MAX_BYTES = ORIG


def reset(items=400, sbytes=rc.STATIC_MAX_BYTES, sitems=None, sbytes2=None):
    """把两个池的上限临时改小（用例要的是"能快速触发淘汰"），并清空缓存"""
    w.result_cache.clear()
    rc.STATIC_MAX_ITEMS = items
    rc.STATIC_MAX_BYTES = sbytes
    if sitems is not None:
        rc.SEQUENCE_MAX_ITEMS = sitems
    if sbytes2 is not None:
        rc.SEQUENCE_MAX_BYTES = sbytes2


# ======================================================================
# ① 静态池条数上限
# ======================================================================
reset(items=3)
imgs = [img("a1.png"), img("a2.png"), img("a3.png"), img("a4.png")]
for f in imgs:
    run(f)
check("① 静态池条数上限：跑 4 张（上限 3）⇒ 只留 3 条",
      len(w.result_cache) == 3, len(w.result_cache))
check("① 淘汰的是**最旧的**那张（a1 没了、a2~a4 还在）",
      key_of("a1.png") not in w.result_cache
      and all(key_of(p) in w.result_cache for p in ("a2.png", "a3.png", "a4.png")),
      sorted(k[0] for k in w.result_cache))

# ======================================================================
# ② ★ 真 LRU 判别（本轮最硬的一条）
# ======================================================================
reset(items=3)
imgs = [img("b1.png"), img("b2.png"), img("b3.png")]
for f in imgs:
    run(f)
# 访问第 1 条（= 走"切回这张图"的路径，命中缓存会 touch）
w.current_static_image = imgs[0]
w._show_static_image(imgs[0])
before = sorted(k[0] for k in w.result_cache)
run(img("b4.png"))
check("② 真 LRU：被访问过的 b1 **仍在**、没被访问的 b2 被淘汰（FIFO 近似会淘汰 b1）",
      key_of("b1.png") in w.result_cache and key_of("b2.png") not in w.result_cache,
      (before, sorted(k[0] for k in w.result_cache), "touch 后 b1 应排到最后"))

# ======================================================================
# ③ 静态池字节上限
# ======================================================================
one = 100 * 100 * 3
reset(items=400, sbytes=int(one * 1.5))
run(img("c1.png"))
run(img("c2.png"))
check("③ 字节上限：1.5 张图的字节配额 ⇒ 只留 1 条（按字节淘汰，不是按条数）",
      len(w.result_cache) == 1, (len(w.result_cache), rc.STATIC_MAX_BYTES, one))
check("③ 留下的是最新那张（c2）", key_of("c2.png") in w.result_cache)

# ======================================================================
# ④ 视频序列帧单独分池
# ======================================================================
reset(items=400, sbytes=rc.STATIC_MAX_BYTES, sitems=2, sbytes2=rc.SEQUENCE_MAX_BYTES)
run(img("static.png"))
for no in (1, 2, 3):
    run(img("v.mp4#{0}".format(no)))
stats = rc.pool_stats(w.result_cache)
check("④ 序列池上限 2 ⇒ 视频帧只剩 2 条（v.mp4#3、#2）",
      stats["sequence"][0] == 2 and key_of("v.mp4#3") in w.result_cache
      and key_of("v.mp4#1") not in w.result_cache, stats)
check("④ **静态图结果没被视频帧挤掉**（static.png 仍在）",
      key_of("static.png") in w.result_cache, stats)

# ======================================================================
# ⑤ 淘汰后重算 = 逐像素一致（淘汰不影响正确性）
# ======================================================================
w2 = m.MainWindow()
w2.main_window.show()
restore()                                    # 前面几组把上限改小过，这里还原成默认值
node = w2.add_flow_node("取反", QPointF(20, 20))
frame = img("d1.png", size=(120, 90), value=77, win=w2)
w2._execute_static(frame, "continuous")
first = w2.result_cache[w2._result_cache_key("d1.png", "continuous")]["frame"].copy()
w2.result_cache.clear()                      # = 模拟"被淘汰了"
w2._execute_static(frame, "continuous")      # 重算
again = w2.result_cache[w2._result_cache_key("d1.png", "continuous")]["frame"]
check("⑤ 淘汰后重算的结果与第一次**逐像素一致**（淘汰只慢一点、不影响正确性）",
      np.array_equal(first, again), (first.shape, again.shape))

# ======================================================================
# ⑥ 删图库项 ⇒ 该图的缓存按图清掉（既有行为不回归）
# ======================================================================
w3 = m.MainWindow()
w3.main_window.show()
restore()
g3 = w3.gallery_widget
f_a = img("e1.png", win=w3)
f_b = img("e2.png", win=w3)
g3.add_image(f_a, "e1.png")
g3.add_image(f_b, "e2.png")
w3._execute_static(f_a, "continuous")
w3._execute_static(f_b, "continuous")
n_before = len(w3.result_cache)
w3.delete_gallery_item(g3.items()[0][0])       # 删第 1 项（签名要带 item，信号里就是它）
check("⑥ 删掉图库第 1 项 ⇒ 它的缓存条目被清掉（另一张还在）",
      n_before == 2 and w3._result_cache_key("e1.png", "continuous") not in w3.result_cache
      and w3._result_cache_key("e2.png", "continuous") in w3.result_cache,
      (n_before, len(w3.result_cache)))

# ======================================================================
# ⑦ 日志写完自动滚到最后一行
# ======================================================================
calls = {"n": 0}
real_scroll = w.execution_log.scrollToBottom
w.execution_log.scrollToBottom = lambda: (calls.__setitem__("n", calls["n"] + 1), real_scroll())[1]
w._update_execution_log([("1", "00:00:00", "灰度", "-", "执行成功")])
n1 = calls["n"]
w._append_log_hint("测试提示")
n2 = calls["n"]
del w.execution_log.scrollToBottom
check("⑦ `_update_execution_log` 写完后滚到最后一行", n1 == 1, n1)
check("⑦ `_append_log_hint`（提示行）也滚到最后一行", n2 == 2, n2)

# ======================================================================
# ⑧ 上限常量与分类函数本身
# ======================================================================
check("⑧ 上限常量合理：正数、序列池 ≤ 静态池",
      0 < ORIG[0] and 0 < ORIG[1] and 0 < ORIG[2] <= ORIG[0] and 0 < ORIG[3] <= ORIG[1], ORIG)
check("⑧ `is_sequence_key` 分类正确（视频帧键带 `#`、静态图路径不带）",
      rc.is_sequence_key(("v.mp4#12", "continuous")) is True
      and rc.is_sequence_key(("C:/a/b.png", "continuous")) is False
      and rc.is_sequence_key(("video:abc", "step")) is False)

print("-" * 70)
if fails:
    print("失败项：%d" % len(fails))
    for name in fails:
        print("   - " + name)
else:
    print("失败项：无")
sys.exit(1 if fails else 0)
