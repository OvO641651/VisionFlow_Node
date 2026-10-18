# -*- coding: utf-8 -*-
"""批次6 目标2-M2 判据：**树控件给节点 / 分组 / 测试 / 「新建项目」加 16×16 图标**（方案 §五 M2）。

用户 2026.10.18 拍板：
  · 图标 **16×16**，位置在**文字前面**；
  · 颜色**统一中性深灰**（QColor(90,90,90)）；
  · 「新建项目」那一项**也加图标**；
  · 未知 / 历史节点名 **回退 generic**；
  · ★ **画布右键菜单不加图标**（只树里有）。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication, QLineEdit, QAction          # noqa: E402

app = QApplication([])
import main as m                                                        # noqa: E402
from core import icon_keys, node_catalog                                 # noqa: E402
from widgets import node_visuals                                         # noqa: E402

_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def pump(n=4):
    for _ in range(n):
        app.processEvents()


def opaque_pixels(icon, size=16):
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


def tree_rows(tree):
    """[(depth, item)] —— 顶层 + 一层子项（树的实际结构）。"""
    out = []
    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        out.append((0, top))
        for j in range(top.childCount()):
            out.append((1, top.child(j)))
    return out


def item_named(tree, name):
    for _d, it in tree_rows(tree):
        try:
            if it.text(0) == name:
                return it
        except RuntimeError:
            continue
    return None


win = m.MainWindow()
win.main_window.resize(1400, 900)
win.main_window.show()
pump(6)
tree = win.tree
rows = tree_rows(tree)

# ① 14 个注册节点在树里**逐个都有非空 icon**
missing = []
for name in node_catalog.node_names():
    it = item_named(tree, name)
    if it is None:
        missing.append((name, "树里没有该项"))
    elif it.icon(0).isNull():
        missing.append((name, "icon 为空"))
check("① 14 个注册节点在树里都有非空 icon", not missing, missing)

# ② 4 个分组 + 测试组 都有 icon
groups = [node_catalog.TEST_GROUP] + [g for g in node_catalog.groups()]
groups = [g[0] if isinstance(g, (tuple, list)) else g for g in groups]
bad_groups = []
for g in groups:
    it = item_named(tree, g)
    if it is None or it.icon(0).isNull():
        bad_groups.append(g)
check("② 分组（含测试组）都有 icon", not bad_groups, bad_groups)

# ②b 「新建项目」那一项也有 icon（用户拍板 ③）
it_new = item_named(tree, "新建项目")
check("②b 「新建项目」项有 icon", it_new is not None and not it_new.icon(0).isNull(),
      None if it_new is None else it_new.icon(0).isNull())

# ③ ★ 图标不是空白（有非透明像素）—— 逐个查
blank = []
for _d, it in rows:
    try:
        text = it.text(0)
    except RuntimeError:
        continue
    px = opaque_pixels(it.icon(0))
    if px <= 0:
        blank.append((text, px))
check("③ ★ 所有树项图标的非透明像素 > 0", not blank, blank)
check("③ 抽查：灰度的图标像素数 >= 40（确实画了东西）",
      opaque_pixels(item_named(tree, "灰度").icon(0)) >= 40 if item_named(tree, "灰度") else False,
      opaque_pixels(item_named(tree, "灰度").icon(0)) if item_named(tree, "灰度") else None)

# ④ ★ 画布右键菜单**不加图标**（用户要求）
view = win.flow_page_mgr.current_page["view"]
menu = view.build_create_menu()
acts = []


def collect(menu_obj):
    for a in menu_obj.actions():
        acts.append(a)
        if a.menu() is not None:
            collect(a.menu())


collect(menu)
menu_with_icon = [a.text() for a in acts if isinstance(a, QAction) and not a.icon().isNull()]
check("④ ★ 右键菜单项数 > 0（先证菜单本身存在）", len(acts) > 0, len(acts))
check("④ ★ 右键菜单**没有任何项带图标**", not menu_with_icon, menu_with_icon)

# ⑤ key 对得上（抽查三处：图片源 / 灰度 / 一个分组）
pairs = [("图片源", "image"), ("灰度", "gray"), ("检测识别", "group_detect")]
wrong = []
for name, expect in pairs:
    it = item_named(tree, name)
    if it is None:
        wrong.append((name, "缺项"))
        continue
    got = it.icon(0).pixmap(16, 16).toImage()
    want = node_visuals.make_icon(expect).pixmap(16, 16).toImage()
    if got != want:
        wrong.append((name, "图案与 %s 不一致" % expect))
check("⑤ key 映射对得上（图片源/灰度/检测识别）", not wrong, wrong)
check("⑤ icon_keys 里新增了 测试 / 新建项目 的映射",
      icon_keys.icon_key_for("测试") == "group_test" and icon_keys.icon_key_for("新建项目") == "add",
      (icon_keys.icon_key_for("测试"), icon_keys.icon_key_for("新建项目")))

# ⑥ 搜索过滤后图标仍在
edit = win.main_window.findChild(QLineEdit, "edit_tree_search")
edit.setText("边缘")
pump(3)
it_edge = item_named(tree, "边缘提取")
still = it_edge is not None and not it_edge.isHidden() and not it_edge.icon(0).isNull()
check("⑥ 搜「边缘」后命中项仍可见且带图标", still,
      None if it_edge is None else (it_edge.isHidden(), it_edge.icon(0).isNull()))
edit.setText("")
pump(3)

# ⑦ 兜底：未知算子名 → generic 非空；缓存命中返回同一对象
unknown_icon = node_visuals.make_icon("这个算子不存在")
check("⑦ 未知算子名回退 generic（icon 非空且画出了像素）",
      not unknown_icon.isNull() and opaque_pixels(unknown_icon) > 0,
      opaque_pixels(unknown_icon))
check("⑦ 缓存命中：同名同对象", node_visuals.make_icon("灰度") is node_visuals.make_icon("gray"), None)

# ⑦b 统一中性灰（用户拍板 ②）：灰度图标里出现的最深颜色应接近 (90,90,90)
img_gray = item_named(tree, "灰度").icon(0).pixmap(16, 16).toImage()
col_mismatch = None
for y in range(img_gray.height()):
    for x in range(img_gray.width()):
        c = img_gray.pixelColor(x, y)
        if c.alpha() > 200:
            if abs(c.red() - 90) > 40 or abs(c.green() - 90) > 40 or abs(c.blue() - 90) > 40:
                col_mismatch = c.getRgb()
                break
    if col_mismatch:
        break
check("⑦b 图标颜色是统一中性深灰（≈90,90,90）", col_mismatch is None, col_mismatch)

print("=" * 60)
print("通过 %d 项，失败 %d 项" % (_pass[0], len(_fails)))
if _fails:
    for t in _fails:
        print("  FAIL: " + t)
    sys.exit(1)
sys.exit(0)
