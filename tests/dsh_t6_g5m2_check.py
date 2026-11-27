# -*- coding: utf-8 -*-
"""批次6 目标5-M2 判据：**顶部 8 个按钮 + 树节点接入 SVG 图标**（方案 §3.2.5 目标5-M2 / §十三 第 74 条）。

用户 2026.10.27 提供 `icons/` 素材：
  · `icons/button_icons/`（8 个顶部按钮，24×24）· `icons/node_icons/`（节点/分组，键与文件名同名）；
  · `icons/toolbar_icons/` **本次不接**（留 M3）；`start/stop/undo_gray/redo_gray` **不使用**（撤销禁用态由 Qt 自动置灰）。

设计要点：`make_icon()` 统一入口 ⇒ **SVG 优先 → 缺文件回退 QPainter 自绘**（绝不返回空白、绝不抛异常）。
★ 本套：用 `QUiLoader` 加载 `.ui` + 调 `main._apply_top_button_size()` 装图标；**不启动主窗口**。
"""
import io
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import QFile, QSize, Qt                                # noqa: E402
from PySide2.QtUiTools import QUiLoader                               # noqa: E402
from PySide2.QtGui import QIcon                                       # noqa: E402
from PySide2.QtWidgets import QApplication, QPushButton               # noqa: E402

app = QApplication([])

import main as m                                                      # noqa: E402
from widgets import node_visuals as nv                                # noqa: E402

_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def _opaque(icon, size=24):
    """图标在 size×size 下的非透明像素数（0 = 空白图）。"""
    try:
        img = icon.pixmap(QSize(size, size)).toImage()
        if img.isNull():
            return 0
        return sum(1 for y in range(img.height()) for x in range(img.width())
                   if img.pixelColor(x, y).alpha() > 0)
    except Exception:
        return 0


# ---------- 加载 .ui 并装图标（复用产品代码的入口，不重复实现）----------
f = QFile(os.path.join(PROJ, "main.ui"))
f.open(QFile.ReadOnly)
ui = QUiLoader().load(f)


class _FakeHost(object):
    main_window = ui


m._apply_top_button_size(_FakeHost())

EIGHT = [("menu_button", "menu"), ("open_button", "import_image"),
         ("btn_step_execute", "step_run"), ("btn_continuous_execute", "run_all"),
         ("save_project_button", "save_project"), ("open_project_button", "load_project"),
         ("btn_undo", "undo"), ("btn_redo", "redo")]

# ---------- ① 8 个顶部按钮逐个有非空图标（且不是空白图）----------
bad = []
for nm, key in EIGHT:
    b = ui.findChild(QPushButton, nm)
    if b is None:
        bad.append((nm, "按钮不存在"))
        continue
    ic = b.icon()
    px = _opaque(ic, 24)
    if ic.isNull() or px <= 0:
        bad.append((nm, key, "null=%s" % ic.isNull(), "px=%d" % px))
check("① 8 个顶部按钮逐个有非空图标且非空白图（SVG 生效）", not bad, bad)

# ---------- ② 撤销 / 重做 图标可区分 ----------
u = ui.findChild(QPushButton, "btn_undo").icon()
r = ui.findChild(QPushButton, "btn_redo").icon()
check("② 撤销 / 重做 图标不同（cacheKey 不同）", u.cacheKey() != r.cacheKey(),
      (u.cacheKey(), r.cacheKey()))

# ---------- ③ 树里 22 个键（14 算子 + 5 分组 + 测试 + 新建项目 + generic）逐个非空 ----------
nv.install_tree_icons(ui.tree)
tree = ui.tree
items_bad = []
n_items = 0
for i in range(tree.topLevelItemCount()):
    top = tree.topLevelItem(i)
    stack = [top]
    while stack:
        it = stack.pop()
        if it is None:
            continue
        n_items += 1
        if it.icon(0).isNull():
            items_bad.append(it.text(0))
        for j in range(it.childCount()):
            stack.append(it.child(j))
check("③ 树里每一项都有非空图标（节点 + 分组 + 新建项目）", n_items >= 20 and not items_bad,
      (n_items, items_bad))

# ---------- ④ ★ 回退测试：SVG 目录不可用 ⇒ 仍返回非空图标且不抛异常 ----------
ok_fallback = False
detail = ""
_old_root = nv._SVG_ROOT
try:
    nv._SVG_ROOT = os.path.join(PROJ, "icons__definitely_missing__")
    nv._ICON_CACHE.clear()
    ic = nv.make_icon("gray", size=404)   # 404 避开缓存
    ok_fallback = (not ic.isNull()) and _opaque(ic, 404) > 0
    detail = "null=%s px=%d" % (ic.isNull(), _opaque(ic, 404))
except Exception as exc:                  # noqa: BLE001
    detail = "抛异常: %r" % (exc,)
finally:
    nv._SVG_ROOT = _old_root
    nv._ICON_CACHE.clear()
check("④ 回退测试：SVG 缺失时仍返回非空图标（灰方块兜底，不空白、不抛异常）", ok_fallback, detail)

# ---------- ⑤ SVG 映射表完整性（8 按钮 + 22 节点键都有文件；且不含已弃用的 4 张）----------
miss_btn = [k for k in nv.SVG_BUTTON if not nv.svg_path_for(k)]
miss_node = [k for k in sorted(nv._KNOWN_ICON_KEYS) if not nv.svg_path_for(k)]
dropped = [k for k in ("start", "stop", "undo_gray", "redo_gray") if k in nv.SVG_BUTTON]
check("⑤ SVG_BUTTON 8 个文件都存在", len(nv.SVG_BUTTON) == 8 and not miss_btn, miss_btn)
check("⑤ node_icons 对 22 个节点键都有文件", not miss_node, miss_node)
check("⑤ 映射里不引用 start / stop / undo_gray / redo_gray", not dropped, dropped)

# ---------- ⑥ ★ 5.2.2：只显示图标（text 空）+ tooltip 原文字 + 尺寸 == 常量 ----------
text_bad, tip_bad, size_bad = [], [], []
for nm, _k in EIGHT:
    _b = ui.findChild(QPushButton, nm)
    if _b is None:
        text_bad.append((nm, "按钮不存在"))
        continue
    if _b.text() != "":
        text_bad.append((nm, _b.text()))
    if not _b.toolTip().strip():
        tip_bad.append((nm, _b.toolTip()))
    if (_b.width(), _b.height()) != (m.TOP_BUTTON_W, m.TOP_BUTTON_H):
        size_bad.append((nm, (_b.width(), _b.height())))
check("⑥ 8 个按钮只显示图标（text 为空）", not text_bad, text_bad)
check("⑥ 8 个按钮都有 tooltip（原文字：菜单/导入图片/单步执行/…）", not tip_bad, tip_bad)
check("⑥ 8 个按钮尺寸 == (TOP_BUTTON_W, TOP_BUTTON_H)",
      not size_bad, (size_bad, m.TOP_BUTTON_W, m.TOP_BUTTON_H))
check("⑥ 8 个按钮总宽 ≤ 1400（1400 宽窗口下排得下）",
      8 * m.TOP_BUTTON_W <= 1400, 8 * m.TOP_BUTTON_W)

# ---------- ⑦ 图标尺寸常量 ----------
check("⑦ 按钮图标尺寸常量合理（> 16，具体值由用户调）", m.TOP_ICON_SIZE > 16, m.TOP_ICON_SIZE)
ic_size = ui.findChild(QPushButton, "menu_button").iconSize()
check("⑦ 按钮 iconSize 已设成 (TOP_ICON_SIZE, TOP_ICON_SIZE)",
      (ic_size.width(), ic_size.height()) == (m.TOP_ICON_SIZE, m.TOP_ICON_SIZE),
      (ic_size.width(), ic_size.height()))

# ---------- ⑧ ★ 5.2.2：画布改用 render_svg（染色生效）+ draw_icon 已退役 ----------
from PySide2.QtGui import QColor                                       # noqa: E402

pm_w = nv.render_svg("gray", QColor("white"), 32)
pm_r = nv.render_svg("gray", QColor("red"), 32)
check("⑧ render_svg 返回非空 pixmap 且尺寸正确",
      (not pm_w.isNull()) and pm_w.size().width() == 32,
      (pm_w.isNull(), pm_w.size().width()))
check("⑧ render_svg 染色生效（white 与 red 渲染像素不同）", pm_w.toImage() != pm_r.toImage())
check("⑧ draw_icon 已退役（node_visuals 里不再有该函数）", not hasattr(nv, "draw_icon"),
      hasattr(nv, "draw_icon"))
_src_fc = io.open(os.path.join(PROJ, "widgets", "FlowChart.py"), encoding="utf-8").read()
check("⑧ FlowChart 已改用 render_svg 且不再 import draw_icon",
      ("render_svg(" in _src_fc) and ("import draw_icon" not in _src_fc),
      ("render_svg(" in _src_fc, "import draw_icon" in _src_fc))

# ---------- ⑨ ★ 5.2.2：SVG 全缺时 render_svg / make_icon 都走灰方块兜底 ----------
fb_ok = False
fb_detail = ""
_old2 = nv._SVG_ROOT
try:
    nv._SVG_ROOT = os.path.join(PROJ, "icons__definitely_missing__")
    nv._ICON_CACHE.clear()
    nv._SVG_PIX_CACHE.clear()
    _pm = nv.render_svg("gray", QColor("white"), 4242)
    _ic = nv.make_icon("gray", size=4343)
    fb_ok = (not _pm.isNull()) and _opaque(_ic, 4343) > 0
    fb_detail = "pm_null=%s" % _pm.isNull()
except Exception as exc:                                               # noqa: BLE001
    fb_detail = "抛异常: %r" % (exc,)
finally:
    nv._SVG_ROOT = _old2
    nv._ICON_CACHE.clear()
    nv._SVG_PIX_CACHE.clear()
check("⑨ 兜底：SVG 全缺时 render_svg / make_icon 都返回非空（灰方块）", fb_ok, fb_detail)

# ---------- ★ 退出前显式清理（防析构期崩溃 0xC0000409）----------
# 实测（2026.10.27）：不清理时本套 10 次里 9 次以 0xC0000409 退出（11 项全 PASS 但 exit≠0 ⇒ 门禁判 BAD）。
# 原因：退出时 QIcon 仍挂在 QPushButton / QTreeWidgetItem 上，Qt 的析构顺序出问题。
# 做法：清缓存 → 把按钮图标置空 → deleteLater + processEvents ⇒ 连跑 5 次 exit=0 ✓
# ---------- ⑩ ★ 5.2.3：画布图标按"缩放×DPR"高清渲染（防锯齿） ----------
print("")
print("⑩ 画布图标高清渲染（防锯齿）")

import widgets.FlowChart as FC                                             # noqa: E402
from PySide2.QtCore import QPointF                                         # noqa: E402
from PySide2.QtGui import QPainter, QPixmap                                # noqa: E402
from PySide2.QtWidgets import QStyleOptionGraphicsItem                     # noqa: E402

_calls = []
_orig_rs = FC.render_svg


def _rec_rs(key, color=None, size=16):
    _calls.append(int(size))
    return _orig_rs(key, color, size)


def _paint_at(node, scale):
    """在给定缩放下手动 paint 一次，返回 render_svg 收到的 size（最大值）。

    ★ 不用主窗口：本套只加载 `.ui`，这里直接 new 一个 NodeItem 手动 paint
      ⇒ 能精确控制 painter 的 worldTransform（= 视图缩放）。
    """
    del _calls[:]
    pm = QPixmap(max(1, int(400 * scale)), max(1, int(200 * scale)))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(scale, scale)
    node.paint(p, QStyleOptionGraphicsItem(), None)
    p.end()
    del pm
    return max(_calls) if _calls else 0


_nd = FC.NodeItem("灰度", QPointF(0, 0))
FC.render_svg = _rec_rs
try:
    _s1 = _paint_at(_nd, 1.0)
    _s4 = _paint_at(_nd, 4.0)
    _s20 = _paint_at(_nd, 20.0)
finally:
    FC.render_svg = _orig_rs

check("⑩ 1× 时按逻辑尺寸渲染（> 0）", _s1 > 0, _s1)
check("⑩ 4× 时渲染尺寸≈4 倍（高清位图，不再靠拉伸）",
      _s1 > 0 and _s4 >= _s1 * 3, (_s1, _s4))
check("⑩ 上限 ICON_PX_MAX 生效（20× 不超上限、且 ≥ 4×）",
      _s20 >= _s4 and 0 < _s20 <= FC.ICON_PX_MAX, (_s20, FC.ICON_PX_MAX))
del _nd

try:
    nv._ICON_CACHE.clear()
    nv._SVG_PIX_CACHE.clear()
    for _n, _k in EIGHT:
        _b = ui.findChild(QPushButton, _n)
        if _b is not None:
            _b.setIcon(QIcon())
    ui.deleteLater()
    app.processEvents()
except Exception:
    pass

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
