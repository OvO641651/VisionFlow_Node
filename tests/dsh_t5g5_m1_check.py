# -*- coding: utf-8 -*-
"""
dsh_t5g5_m1_check.py —— 批次5 目标5-M1 的判据（图库：缩略图尺寸 + 播放中点图库）

覆盖两件事（用户 2026.10.16 实测报的）：
  A、**缩略图固定大小**：图一多/混进竖长图时，缩略图被压成细条、点不中。
     根因 = 旧写法 `scaled(80, 60, KeepAspectRatio)` 让缩略图尺寸随原图长宽比变（竖长图只有 15×60），
     而列表开着 `setUniformItemSizes(True)` ⇒ "某项的宽度"成了全列表的统一宽度 ⇒ 单元格被压到 ~21px。
     修法 = 缩略图统一装进**固定 80×60 画布**（等比缩放 + 居中 + 浅灰留白）+ `setGridSize()` 钉死单元格。
  B、**播放中点图库会"闪一帧" + 缩放串扰 + 参数被换**：
     根因 = `_on_gallery_image_selected()` 无条件走 `_show_static_image()`（记住当前图 / 按图切参数 /
     用静态图 key 画到画布），而播放定时器 30~60ms 后把视频帧盖回来。
     修法 = 播放中（视频或相机）点图库**只改选中项**，不碰画面、不碰参数（用户拍板"甲"，不加日志）。

运行：`python tests\dsh_t5g5_m1_check.py`（无头；退出码 0 = 全过）
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import numpy as np

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication, QListWidgetItem   # noqa: E402
from PySide2.QtCore import QPointF, QSize, Qt                 # noqa: E402

app = QApplication([])

import main as m                                              # noqa: E402
from widgets.ImageGalleryWidget import (                      # noqa: E402
    make_thumbnail_pixmap, THUMB_W, THUMB_H, CELL_W, CELL_H, THUMB_BG)

_ok = [0]
_bad = [0]


def check(title, ok, extra=None):
    if ok:
        _ok[0] += 1
        print("PASS  {0}{1}".format(title, "" if extra is None else "   <- {0}".format(extra)))
    else:
        _bad[0] += 1
        print("FAIL  {0}{1}".format(title, "" if extra is None else "   <- {0}".format(extra)))


def img(shape, value=0):
    return np.full(shape, value, np.uint8)


TALL = (1200, 300, 3)      # 竖长图：旧写法缩出来只有 15×60（就是压窄全列表的元凶）
LAND = (480, 640, 3)       # 横图

print("=" * 70)
print("批次5 目标5-M1：图库缩略图固定尺寸 + 播放中点图库不碰画面")
print("=" * 70)

# ======================================================================
# ① ~ ⑥   M1-a：缩略图装进固定画布，项尺寸不再受内容影响
# ======================================================================
p_land = make_thumbnail_pixmap(img(LAND, 30))
p_tall = make_thumbnail_pixmap(img(TALL, 200))
check("① 缩略图统一装进固定画布：横图与竖长图**都是 80×60**",
      (p_land.width(), p_land.height()) == (THUMB_W, THUMB_H)
      and (p_tall.width(), p_tall.height()) == (THUMB_W, THUMB_H),
      ((p_land.width(), p_land.height()), (p_tall.width(), p_tall.height())))

land_corner = p_land.toImage().pixelColor(0, 0).getRgb()[:3]
tall_corner = p_tall.toImage().pixelColor(0, 0).getRgb()[:3]
check("② 不变形且整图可见：横图铺满画布（角落 = 图像内容）、竖长图两侧留白（角落 = 底色）",
      land_corner != THUMB_BG and tall_corner == THUMB_BG,
      (land_corner, tall_corner, THUMB_BG))

w = m.MainWindow()
w.main_window.show()
gw = w.gallery_widget
gl = gw.gallery_list

widths = []
for i in range(12):                                  # 横、横、竖 循环 —— 修前"最后加竖长图"会把全列表压窄
    gw.add_image(img(TALL if i % 3 == 2 else LAND, i * 11), "m1_{0}.png".format(i))
    QApplication.processEvents()
    widths.append(gl.visualItemRect(gl.item(gl.count() - 1)).width())
check("③ [回归钉] 逐张添加（横、横、竖…共 12 张）时**每项宽度恒定**（修前会掉到 ~21px）",
      len(set(widths)) == 1 and min(widths) >= 60, (sorted(set(widths)), len(widths)))

icon_sizes = {tuple(gl.item(i).icon().pixmap(200, 200).size().toTuple()) for i in range(gl.count())}
check("④ [回归钉] 12 张（含 4 张竖长图）的缩略图尺寸**只有一种**：80×60",
      icon_sizes == {(THUMB_W, THUMB_H)}, sorted(icon_sizes))


def item_sizes(n):
    gl.clear()
    for i in range(n):
        gw.add_image(img(LAND, i), "num{0}.png".format(i))
    QApplication.processEvents()
    return {(gl.visualItemRect(gl.item(i)).width(), gl.visualItemRect(gl.item(i)).height())
            for i in range(gl.count())}


s7, s53 = item_sizes(7), item_sizes(53)
check("⑤ **数量无关**：7 张与 53 张的项尺寸完全相同（都是同一种 88×84 单元格）",
      s7 == s53 and len(s7) == 1, (s7, s53))

last = gl.item(gl.count() - 1)
check("⑥ 点得中：第 1 张与最后一张的**中心点**都能被 itemAt() 命中（修前 ~21px 宽时点不中）",
      gl.itemAt(gl.visualItemRect(last).center()) is last
      and gl.itemAt(gl.visualItemRect(gl.item(0)).center()) is gl.item(0),
      (gl.visualItemRect(last).width(), gl.visualItemRect(gl.item(0)).width()))

check("⑦ 单元格尺寸被 setGridSize() 钉死（= 缩略图 80×60 + 内边距）",
      gl.gridSize() == QSize(CELL_W, CELL_H), (gl.gridSize(), QSize(CELL_W, CELL_H)))

# ======================================================================
# ⑧ ~ ⑭   M1-b：播放中（视频 / 相机）点图库 —— 只改选中项，不碰画面 / 参数
# ======================================================================
calls = []
orig_display = w._display_image


def spy_display(image, image_key=None):
    calls.append(image_key)
    return orig_display(image, image_key)


w._display_image = spy_display

node = w.add_flow_node("取反", QPointF(20, 20))
node.params["m1_marker"] = 1
before_params = dict(node.params)
static = img((90, 120, 3), 7)
w._frame_paths[id(static)] = "m1_static.png"
# 给这张静态图准备一份**不同的**参数存档（若播放中点它不该被载入）
w._get_node_params_store(node)["m1_static.png"] = {"m1_marker": 99}

w._video_playing = True
w._camera_playing = False
w.current_static_image = None
calls[:] = []
w._on_gallery_image_selected(static)
check("⑧ [回归钉] 播放中点图库：**不再往画布上画静态图**（带静态图 key 的显示调用 = 0 次；修前 = 1 次）",
      calls == [], calls)
check("⑨ [回归钉] 播放中点图库：不把「当前图」换成那张静态图（缩放也就不会被切到它的记录）",
      w.current_static_image is None, w.current_static_image)
check("⑩ [回归钉] 播放中点图库：节点参数**不被换成**那张静态图的存档（视频 / 相机槽不被污染）",
      dict(node.params) == before_params, (dict(node.params), before_params))
check("⑪ 播放状态没被打断（点完还在播）", w._is_playing() is True, w._is_playing())

w._video_playing = False
w._camera_playing = True
check("⑫ _is_playing() 判定：**视频 / 相机任一在播都算**（相机分支同样被挡住）",
      w._is_playing() is True and w._on_gallery_image_selected(static) is None and calls == [],
      (w._is_playing(), calls))

w._camera_playing = False
check("⑬ 都不播时 _is_playing() 为假", w._is_playing() is False, w._is_playing())

calls[:] = []
# 假装"当前正在看另一张图"——否则按既有语义（`_switch_image_params`：current_image_key 为 None 时
# **故意不载入**，保护"先调好 ROI 再开图"那份参数）不会去读存档，这条就验不到"按图恢复"。
w.current_image_key = "m1_other.png"
w._on_gallery_image_selected(static)
keyed = [k for k in calls if k is not None]
check("⑭ **未播放时老行为一个字不改**：正常显示这张静态图（1 次带 key 的显示调用）+ 参数按图恢复",
      len(keyed) == 1 and w.current_static_image is static and node.params.get("m1_marker") == 99,
      (len(keyed), w.current_static_image is static, node.params.get("m1_marker")))

# ======================================================================
# ⑮ ~ ⑯   M1 追加（用户 2026.10.16 报的第 2 条）：播放中点图库，"图像源 (n/N)"标签被顶一下又弹回
#        根因 = `_on_item_clicked()` 末尾的 `refresh_count()`（写图库计数），而播放侧每 tick 写"视频帧 (n/N)"
# ======================================================================
gl.clear()
for i in range(3):
    gw.add_image(img(LAND, i), "tag{0}.png".format(i))
QApplication.processEvents()
check("⑮ 前置：标签本来显示图库计数「图像源 (n/N)」",
      gl.count() == 3 and "图像源" in gw.count_label.text(), gw.count_label.text())

w._video_playing = True
gw.set_count_locked(True)                        # 真实入口 = `_video_tick` 里那一句（播放开始交接标签）
gw.count_label.setText("视频帧 (3/250)")          # 播放侧每个 tick 写进来的文案
before_text = gw.count_label.text()
gw._on_item_clicked(gl.item(1))                  # = 播放中点图库
check("⑮ [回归钉] 播放中点图库：**标签不被刷成图库计数**（保持播放侧的「视频帧 (n/N)」）",
      gw.count_label.text() == before_text, (before_text, gw.count_label.text()))

gw.refresh_count()                               # 即使别处主动调 refresh_count（加图 / 删图路径），也不该抢标签
check("⑮ [回归钉] 播放中其它路径调 refresh_count() 也不会抢走标签（加图 / 删图同样安全）",
      gw.count_label.text() == before_text, gw.count_label.text())

w._stop_video_playback("测试停止")
check("⑯ 停止播放 ⇒ 标签**交还图库**并立刻刷回「图像源 (n/N)」（不会停在「视频帧 …」上）",
      "图像源" in gw.count_label.text() and w._is_playing() is False,
      (gw.count_label.text(), w._is_playing()))

# ======================================================================
# ⑰ ~ ⑲   M1 最后一条（用户 2026.10.16 报的第 1 条原始问题）：
#         **导入方案后，"图片源"那张图会被塞进图库、跟当前选择的那张冲突**
#         取证（修前）：画布没被顶、选中项没被改，但图库从 1 张变 2 张（源图被 append）
# ======================================================================
import tempfile                                                  # noqa: E402


class FakeMB(object):                                            # 挡掉载入方案时的确认框
    Yes = 0x4000
    No = 0x10000
    Ok = 0x400

    @staticmethod
    def question(*a, **k):
        return 0x4000

    @staticmethod
    def information(*a, **k):
        return 0x400

    @staticmethod
    def warning(*a, **k):
        return 0x400

    @staticmethod
    def critical(*a, **k):
        return 0x400


_real_mb = m.QMessageBox
m.QMessageBox = FakeMB

LENA_P = os.path.abspath(os.path.join("image", "lena.png"))
HOUGH_P = os.path.abspath(os.path.join("image", "HoughLines.jpg"))
tmp_dir = tempfile.mkdtemp()
proj_path = os.path.join(tmp_dir, "m1_import.vfproj")

# 造一个"含图片源节点"的方案（源图 = HoughLines）
w_src = m.MainWindow()
w_src.main_window.show()
_src = w_src.add_flow_node("图片源", QPointF(20, 20))
_src.params["source_path"] = HOUGH_P
_src.params["source_type"] = "图片"
w_src.flow_page_mgr.current_page["project_path"] = proj_path
w_src.save_project()
check("⑰ 前置：方案文件写好（含一个指向 HoughLines 的「图片源」节点）",
      os.path.exists(proj_path) and os.path.getsize(proj_path) > 0, os.path.getsize(proj_path))

# 用户侧：图库里只有 lena，并且"当前选中的就是它"
w_imp = m.MainWindow()
w_imp.main_window.show()
gw_i = w_imp.gallery_widget
w_imp.import_image_path(LENA_P)
w_imp._show_static_image(gw_i.item_frame(gw_i.gallery_list.item(0)))
gw_i.set_current_index(0)
count_before = gw_i.count()
key_before_imp = w_imp._image_key_of(w_imp.current_static_image)
w_imp.load_project(proj_path)                       # = 用户说的"导入项目"
QApplication.processEvents()
check("⑰ [回归钉] 导入项目**不会**把「图片源」那张图塞进图库（图库张数不变）",
      gw_i.count() == count_before and not gw_i.has_path(HOUGH_P),
      (count_before, gw_i.count(), [gw_i.item_path(gw_i.gallery_list.item(i)) for i in range(gw_i.count())]))
check("⑰ [回归钉] 导入项目**不动**当前选择与画布（选中的还是 lena 那张）",
      gw_i.current_index() == 0 and w_imp._image_key_of(w_imp.current_static_image) == key_before_imp,
      (gw_i.current_index(), w_imp._image_key_of(w_imp.current_static_image)))

check("⑱ 前置：导入后确实切到了新页（当前页里有那个「图片源」节点）",
      any(n.name == "图片源" for n in w_imp.flow_nodes), [n.name for n in w_imp.flow_nodes])
w_imp._execute_static(w_imp.current_static_image, "continuous")      # = 用户自己点执行
check("⑲ [需求保护] 正常执行时，图片源那张图**仍然会进图库**（保住 2026.10.5 的「图库里看得见」）",
      gw_i.has_path(HOUGH_P) and gw_i.count() == count_before + 1,
      (gw_i.count(), gw_i.has_path(HOUGH_P)))

m.QMessageBox = _real_mb

w._display_image = orig_display
w._video_playing = False
w._camera_playing = False

print("-" * 70)
print("通过 {0} 项，失败 {1} 项".format(_ok[0], _bad[0]))
if _bad[0]:
    print("失败项：{0} 项".format(_bad[0]))
    sys.exit(1)
print("失败项：无")
sys.exit(0)
