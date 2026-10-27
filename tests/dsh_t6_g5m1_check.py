# -*- coding: utf-8 -*-
"""批次6 目标5-M1 判据：**顶部按钮调整**（方案 §3.2.5 目标5-M1 / §十三 第 71 条）。

用户 2026.10.27 拍板：
  · ⛔ **删除「启动」「停止」两个按钮**（功能已并入**相机源节点**：`camera_service` 里相机源节点执行时自己 `_open_camera_device`，
    "停止"只停画面、关相机由"删除"承担 ⇒ 删按钮不丢功能）；
  · ✏️ 「打开文件」→ 改名「**导入图片**」（功能不变）；
  · 📏 按钮尺寸由**固定 100×90** 调小到 **80×52**（`main.py` 的 `TOP_BUTTON_W/H` 常量）。

★ 本套只读 `.ui`（`QUiLoader` 加载）+ 读 `main.py` 源码，不启动主窗口。
"""
import io
import os
import re
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import QFile                                          # noqa: E402
from PySide2.QtUiTools import QUiLoader                                   # noqa: E402
from PySide2.QtWidgets import QApplication, QPushButton, QWidget          # noqa: E402

app = QApplication([])

_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


# ---------- 常量（从 main.py 读，**不写死 80/52**）----------
src = io.open(os.path.join(PROJ, "main.py"), encoding="utf-8").read()
mm = re.search(r"TOP_BUTTON_W,\s*TOP_BUTTON_H\s*=\s*(\d+),\s*(\d+)", src)
TOP_W, TOP_H = (int(mm.group(1)), int(mm.group(2))) if mm else (None, None)

# ---------- 加载 .ui ----------
f = QFile(os.path.join(PROJ, "main.ui"))
f.open(QFile.ReadOnly)
ui = QUiLoader().load(f)

EIGHT = [("menu_button", "菜单"), ("open_button", "导入图片"),
         ("btn_step_execute", "单步执行"), ("btn_continuous_execute", "连续执行"),
         ("save_project_button", "保存项目"), ("open_project_button", "导入项目"),
         ("btn_undo", "撤销"), ("btn_redo", "重做")]

# ---------- ① 启动 / 停止 已删除 ----------
check("① 常量存在：TOP_BUTTON_W/H 已定义且 < (100, 90)",
      TOP_W is not None and TOP_W < 100 and TOP_H < 90, (TOP_W, TOP_H))
check("① camera_button（启动）已不存在", ui.findChild(QPushButton, "camera_button") is None)
check("① close_button（停止）已不存在", ui.findChild(QPushButton, "close_button") is None)

# ---------- ② 改名：导入图片 ----------
ob = ui.findChild(QPushButton, "open_button")
check("② 「导入图片」按钮存在且文本正确", ob is not None and ob.text() == "导入图片",
      ob.text() if ob else None)
all_texts = [b.text() for b in ui.findChildren(QPushButton)]
check("② 界面上已无「打开文件」按钮", "打开文件" not in all_texts, all_texts)

# ---------- ③ 尺寸 == 常量 ----------
bad = []
for n, _t in EIGHT:
    b = ui.findChild(QPushButton, n)
    if b is None or (b.width(), b.height()) != (TOP_W, TOP_H):
        bad.append((n, (b.width(), b.height()) if b else None))
check("③ 8 个按钮尺寸都 == (TOP_BUTTON_W, TOP_BUTTON_H)", not bad, bad)

# ---------- ④ 其余 8 个按钮仍在且文本正确 ----------
missing = [(n, t) for n, t in EIGHT
           if ui.findChild(QPushButton, n) is None or ui.findChild(QPushButton, n).text() != t]
check("④ 其余 8 个按钮仍在且文本正确", not missing, missing)

# ---------- ⑤ 顶部栏不裁切（1400 宽下右缘不超出容器）----------
holder = ui.findChild(QPushButton, "menu_button").parentWidget()
right_most = 0
for n, _t in EIGHT:
    b = ui.findChild(QPushButton, n)
    g = b.geometry()
    right_most = max(right_most, g.right())
check("⑤ 顶部 8 个按钮的右缘都在容器内（不裁切）",
      holder is not None and right_most <= holder.width(), (right_most, holder.width() if holder else None))
check("⑤ 8 个按钮总宽 ≤ 1400（1400 宽窗口下排得下，不依赖无头环境下未定稿的容器几何）",
      8 * TOP_W <= 1400, 8 * TOP_W)

# ---------- ⑥ main.py 源码已清理（无孤儿 connect）----------
orphan = [kw for kw in ("camera_button", "close_button") if kw in src]
check("⑥ main.py 不再引用 camera_button / close_button", not orphan, orphan)
check("⑥ main.py 仍有 open_button 接线（功能未误删）",
      "open_button" in src and "open_file" in src, None)

# ---------- 汇总 ----------
print("")
print("=" * 60)
if _fails:
    print("FAIL 共 %d 项；通过 %d 项" % (len(_fails), _pass[0]))
    for t in _fails:
        print("  - " + t)
    sys.exit(1)
print("通过 %d 项，失败 0 项" % _pass[0])
sys.exit(0)
