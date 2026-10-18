# -*- coding: utf-8 -*-
"""批次6 目标2-M2 第 2 次修改（2.2.2）判据：**参数窗口标题栏左上角用「节点自己的图标」**。

用户 2026.10.18 拍板：
  · 甲 = 窗口**标题栏左侧**的小图标（不是客户区再加一行）；
  · 图标颜色取「画布节点绿块同色 `#2E9D57`」（嫌艳只改 `make_icon(color=…)` 一处）；
  · 现在就做，**素材以后再换**（SVG 归目标5）。
判据口径：4 类参数窗口（通用 / 直线 / 圆 / 灰度）打开后 `windowIcon()` 非空、
        图案与该节点 key 对应、不同节点图标不同、主窗口图标不被串扰。
★ 打开窗口用 exec_() 是模态会阻塞 ⇒ 用**子类覆盖 exec_()** 打桩（不改产品代码）。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication                                  # noqa: E402
from PySide2.QtCore import QPointF                                         # noqa: E402

app = QApplication([])
import main as m                                                           # noqa: E402
from ui.GenericProcessDialog import GenericProcessDialog                    # noqa: E402
from ui.LineParamsDialog import LineParamsDialog                            # noqa: E402
from ui.CircleParamsDialog import CircleParamsDialog                        # noqa: E402
from ui.GrayParamsDialog import GrayParamsDialog                            # noqa: E402
from widgets import node_visuals                                            # noqa: E402

GREEN = "#2E9D57"
ICON_SIZE = 32

_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def pump(n=6):
    for _ in range(n):
        app.processEvents()


def opaque_pixels(icon, size=ICON_SIZE):
    """图标里**非透明**像素个数（防“画了个透明图”骗过 isNull）。"""
    if icon is None or icon.isNull():
        return 0
    img = icon.pixmap(size, size).toImage()
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 0:
                n += 1
    return n


def img_bytes(icon, size=ICON_SIZE):
    if icon is None or icon.isNull():
        return b""
    return bytes(icon.pixmap(size, size).toImage().bits())


# ---------------------------------------------------------------- 造窗口
win = m.MainWindow()
win.main_window.resize(1280, 800)
win.main_window.show()
pump()

main_icon_before = win.main_window.windowIcon().cacheKey()

created = []


def stub_of(cls):
    """子类覆盖 exec_()：记录实例、不真正模态阻塞。"""
    class _Stub(cls):
        def exec_(self):
            created.append(self)
            return 0
    return _Stub


cases = [
    ("灰度", GrayParamsDialog),
    ("直线识别", LineParamsDialog),
    ("圆识别", CircleParamsDialog),
    ("取反", GenericProcessDialog),
]

opened = []
for idx, (node_name, cls) in enumerate(cases):
    node = win.add_flow_node(node_name, QPointF(200 + idx * 40, 180 + idx * 40))
    pump(2)
    before = len(created)
    win._open_node_dialog(node, stub_of(cls))
    pump(2)
    if len(created) > before:
        opened.append((node_name, node, created[-1]))
    else:
        opened.append((node_name, node, None))

# ---------------------------------------------------------------- ① 四类窗口都有图标
check("① 4 类参数窗口都设了非空 windowIcon",
      len(opened) == 4 and all(d is not None and not d.windowIcon().isNull()
                                for _, _, d in opened),
      [(n, None if d is None else d.windowIcon().isNull()) for n, _, d in opened])

# ---------------------------------------------------------------- ② 图标不是空白
counts = [(n, opaque_pixels(d.windowIcon())) for n, _, d in opened if d is not None]
check("② 图标确实画出来了（非透明像素 > 0）",
      len(counts) == 4 and all(c > 0 for _, c in counts), counts)

# ---------------------------------------------------------------- ③ 与节点 key 对应
mismatch = []
for node_name, node, d in opened:
    if d is None:
        mismatch.append((node_name, "no dialog"))
        continue
    expect = node_visuals.make_icon(node.name, color=GREEN, size=ICON_SIZE)
    if d.windowIcon().cacheKey() != expect.cacheKey():
        mismatch.append((node_name, d.windowIcon().cacheKey(), expect.cacheKey()))
check("③ 窗口图标 == make_icon(节点名, 绿, 32)（同源缓存命中）", mismatch == [], mismatch)

# ---------------------------------------------------------------- ④ 不同节点图标不同
by_name = {n: d for n, _, d in opened}
inv = by_name.get("取反")
gray = by_name.get("灰度")
check("④ 不同节点的窗口图标不同（取反 vs 灰度）",
      inv is not None and gray is not None
      and img_bytes(inv.windowIcon()) != img_bytes(gray.windowIcon()),
      (opaque_pixels(inv.windowIcon()) if inv else None,
       opaque_pixels(gray.windowIcon()) if gray else None))

# ---------------------------------------------------------------- ⑤ 不串扰主窗口
check("⑤ 打开/关闭参数窗口后，主窗口图标不变",
      win.main_window.windowIcon().cacheKey() == main_icon_before,
      (main_icon_before, win.main_window.windowIcon().cacheKey()))

# ---------------------------------------------------------------- ⑥ 同一节点重复打开仍同图标
if opened and opened[0][2] is not None:
    node_name, node, _ = opened[0]
    before = len(created)
    win._open_node_dialog(node, stub_of(GrayParamsDialog if node_name == "灰度"
                                       else GenericProcessDialog))
    pump(2)
    again = created[-1] if len(created) > before else None
    check("⑥ 同一节点再开一次 ⇒ 图标 cacheKey 一致（缓存复用）",
          again is not None and again.windowIcon().cacheKey() == node_visuals.make_icon(
              node.name, color=GREEN, size=ICON_SIZE).cacheKey(),
          None if again is None else again.windowIcon().cacheKey())
else:
    check("⑥ 同一节点再开一次 ⇒ 图标 cacheKey 一致（缓存复用）", False, "no dialog")

# ---------------------------------------------------------------- 收尾
print("\n通过 %d 项，失败 %d 项" % (_pass[0], len(_fails)))
if _fails:
    for t in _fails:
        print("  失败: " + t)
    sys.exit(1)
sys.exit(0)
