# -*- coding: utf-8 -*-
"""批次6 目标3-M1 判据：**日志列裁剪 + 文案精简 + 全部居中 + 折叠后 1:1 布局**（方案 §3.2.3 / §十三 53-54）。

用户 2026.10.18 拍板：
  · 日志只留「序号 / 时间 / 模块 / 结果数据」四列（「图像源」列不再显示）；
  · 直线识别 / 圆识别保持「检测到 N 条直线 / 个圆」，其余节点统一「执行成功」；
  · 图像源节点只显示**文件名**；失败行红字；未执行不加行；
  · 表头 + 单元格**全部居中**；
  · 折叠左面板后 **画布 : 右侧 = 1:1**（不再全给画布）；
  · ★ 先不动 `.ui` 布局（全部运行时改）。
"""
import os
import re
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import Qt, QPointF                                  # noqa: E402
from PySide2.QtWidgets import QApplication, QToolButton, QWidget        # noqa: E402

app = QApplication([])
import main as m                                                       # noqa: E402
from core.NodeRegistry import get_spec                                 # noqa: E402
from ops.source.ImageSourceOps import format_source                    # noqa: E402

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


# ===================== ① 列裁剪 + 表头改名 + 居中 =====================
w = m.MainWindow()
w.main_window.resize(1400, 900)
w.main_window.show()
pump(8)
log = w.execution_log

check("① 日志表列数 5（第 4 列数据保留、不再显示）", log.columnCount() == 5, log.columnCount())
check("① 「图像源」列已隐藏（用户：删除日志列表中的图像源）",
      log.isColumnHidden(3) is True, log.isColumnHidden(3))
visible_headers = [log.horizontalHeaderItem(i).text() for i in range(log.columnCount())
                   if not log.isColumnHidden(i)]
check("① 可见表头 == [序号, 时间, 模块, 结果数据]",
      visible_headers == ["序号", "时间", "模块", "结果数据"], visible_headers)
check("① 表头居中（AlignHCenter）",
      bool(int(log.horizontalHeader().defaultAlignment()) & int(Qt.AlignHCenter)),
      int(log.horizontalHeader().defaultAlignment()))

# ===================== ② 单元格居中 =====================
w._update_execution_log([("1", "21:00:00", "灰度", "全局图像源", "执行成功")])
pump()
item0 = log.item(0, 0)
res0 = log.item(0, 4)
check("② 单元格文字居中（序号列 AlignHCenter）",
      item0 is not None and bool(int(item0.textAlignment()) & int(Qt.AlignHCenter)),
      int(item0.textAlignment()) if item0 else None)
check("② 结果数据列居中",
      res0 is not None and bool(int(res0.textAlignment()) & int(Qt.AlignHCenter)),
      int(res0.textAlignment()) if res0 else None)

ROI = (0, 0, 10, 10, True, "矩形", "roi")

# ===================== ③ 普通节点文案 == 执行成功 =====================
n_gray = w.add_flow_node("灰度", QPointF(200, 200))
txt_gray = w._format_result_text(n_gray, [], ROI, get_spec("灰度"))
check("③ 普通节点（灰度）文案以「执行成功」开头", txt_gray.startswith("执行成功"), txt_gray)
check("③ 不再带「（图像已处理…）」这类长后缀", "（" not in txt_gray, txt_gray)

n_inv = w.add_flow_node("取反", QPointF(400, 200))
txt_inv = w._format_result_text(n_inv, [], ROI, get_spec("取反"))
check("③ 取反 文案同样以「执行成功」开头", txt_inv.startswith("执行成功"), txt_inv)

# ===================== ④ 检测类保持「检测到 N 条直线 / 个圆」 =====================
n_line = w.add_flow_node("直线识别", QPointF(600, 200))
txt_line = w._format_result_text(n_line, [(0, 0, 10, 10), (1, 1, 20, 20)], ROI, get_spec("直线识别"))
check("④ 直线识别文案含「条直线」", "条直线" in txt_line and "执行成功" not in txt_line, txt_line)
n_circle = w.add_flow_node("圆识别", QPointF(800, 200))
txt_circle = w._format_result_text(n_circle, [], ROI, get_spec("圆识别"))
check("④ 圆识别文案含「个圆」", "个圆" in txt_circle and "执行成功" not in txt_circle, txt_circle)

# ===================== ⑤ 图像源只显示文件名 =====================
src_text = format_source([{"图片源": r"E:\some\deep\dir\pic_001.png"}])
check("⑤ 图像源文案只含文件名（不含目录分隔符）",
      "pic_001.png" in src_text and "\\" not in src_text and "/" not in src_text, src_text)

# ===================== ⑥ 失败行：红字 + 文案 ≤ 8 字 =====================
log.setRowCount(0)
w._update_execution_log([("1", "21:00:01", "灰度", "-", m.LOG_ERROR_MARK + "无输入")])
pump()
fail_item = log.item(0, 4)
fail_text = fail_item.text() if fail_item else ""
check("⑥ 失败行文案去掉内部标记后 ≤ 8 字",
      0 < len(fail_text) <= 8 and m.LOG_ERROR_MARK not in fail_text, fail_text)
check("⑥ 失败行是红字",
      fail_item is not None and fail_item.foreground().color().red() > 150,
      fail_item.foreground().color().name() if fail_item else None)

# ===================== ⑦ 折叠后 画布 : 右侧 = 1:1 =====================
panel = w.main_window.findChild(QWidget, "tool_tab_widget")
btn = w.main_window.findChild(QToolButton, "btn_collapse_toolbox")
fv = w.flow_page_mgr.current_page["view"]
pump(6)
before_flow = fv.viewport().width()
btn.click()
pump(8)
collapsed_flow = fv.viewport().width()
collapsed_right = log.width()
ratio = float(collapsed_flow) / max(1, collapsed_right)
check("⑦ 点折叠按钮后工具箱隐藏", panel.isVisible() is False, panel.isVisible())
check("⑦ 折叠后画布明显变宽（> 折叠前 +100px）", collapsed_flow > before_flow + 100,
      (before_flow, collapsed_flow))
check("⑦ 折叠后 画布 : 右侧 ≈ 1:1（0.85~1.15）", 0.85 <= ratio <= 1.15, round(ratio, 3))
check("⑦ 折叠后把手仍可见（唯一展开入口）", btn.isVisible() is True, btn.isVisible())
btn.click()
pump(8)
check("⑦ 再展开：工具箱回来 + 画布宽度还原（≤2px）",
      panel.isVisible() is True and abs(fv.viewport().width() - before_flow) <= 2,
      (panel.isVisible(), fv.viewport().width(), before_flow))

# ===================== ⑧ 结构自检 =====================
check("⑧ 折叠把手对象名仍是 btn_collapse_toolbox（未改控件名）",
      btn is not None and btn.objectName() == "btn_collapse_toolbox",
      btn.objectName() if btn else None)

# ===================== ⑨ 结果数据列够宽（3.1.2） =====================
from PySide2.QtWidgets import QHeaderView                                 # noqa: E402

_hdr = log.horizontalHeader()
check("⑨ 结果数据列（第 5 列）是自适应拉伸（Stretch）",
      _hdr.sectionResizeMode(4) == QHeaderView.Stretch, int(_hdr.sectionResizeMode(4)))
check("⑨ 结果数据列实际宽度占表格宽度的大头（≥45%，不再到处省略号）",
      log.columnWidth(4) >= int(log.width() * 0.45) and log.columnWidth(4) >= 240,
      (log.columnWidth(4), log.width()))
check("⑨ 序号/时间/模块 三列是固定宽",
      all(_hdr.sectionResizeMode(c) == QHeaderView.Fixed for c in (0, 1, 2)),
      [int(_hdr.sectionResizeMode(c)) for c in (0, 1, 2)])

# ===================== ⑩ 提示/汇总行也居中（3.1.2） =====================
log.setRowCount(0)
w._append_log_hint("测试提示行")
pump()
_hr = log.rowCount() - 1
_hal = [(log.item(_hr, c).textAlignment() if log.item(_hr, c) else 0)
        for c in range(log.columnCount())]
check("⑩ 提示行（序号列是「-」的那行）每个单元格都水平居中",
      _hr >= 0 and all((a & Qt.AlignHCenter) for a in _hal), [int(a) for a in _hal])


# ===================== ⑪ 处理类文案不再追「← 继承上游ROI框」 =====================
class _FakeNode(object):
    name = "灰度"
    params = {"roi_inherit": True}


_txt = w._format_result_text(_FakeNode(), {}, (0, 0, 100, 100, 0, 0, "roi"), get_spec("灰度"))
check("⑪ 处理类文案 == 执行成功（不含「继承上游」短注）",
      _txt == "执行成功" and "继承上游" not in _txt, _txt)

# ===================== ⑫ 时间列：带年月日、用 . 分隔（3.1.3） =====================
_TIME_PAT = re.compile(r"^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}$")
# 先补一条「普通行」，保证普通行与提示行都有 —— 只测提示行会漏掉普通行的格式
import time as _time
# ★ _update_execution_log 会清空表格 ⇒ 先写普通行、再补一条提示行，两种行都要覆盖到
w._update_execution_log([(1, _time.strftime("%Y.%m.%d %H:%M"), "图片源", "全局图像源", "图片源：a.jpg")])
w._append_log_hint("测试提示行")
pump()
_trow = []
for _i in range(log.rowCount()):
    _it = log.item(_i, 1)
    if _it is not None:
        _trow.append((_it.text(), log.item(_i, 0).text() if log.item(_i, 0) else ""))
check("⑫ 时间列全部匹配 2026.10.18 22:37 格式（含提示行）",
      len(_trow) >= 2 and all(_TIME_PAT.match(t) for t, _ in _trow), _trow[:4])
check("⑬ 时间列宽 >= 138px（放得下 2026.10.18 22:38）", log.columnWidth(1) >= 138, log.columnWidth(1))
check("⑭ 同一批多行时间文本一致（分钟级）",
      len(set(t for t, _ in _trow)) == 1, sorted(set(t for t, _ in _trow))[:3])

# ===================== ⑮~⑱ 文案集中表（3.1.4） =====================
from core import log_texts as _T
_src = open(os.path.join(PROJ, "core", "log_texts.py"), encoding="utf-8").read()
_names = [n for n in dir(_T) if not n.startswith("_")]
_vals = [(n, getattr(_T, n)) for n in _names]
check("⑮ log_texts 里只有字符串常量（无 def / class / 函数）",
      all(isinstance(v, str) for _, v in _vals) and len(_vals) >= 20,
      [n for n, v in _vals if not isinstance(v, str)])
# ★ 用 AST 看“真正的 import 语句”（直接 grep 源码会被文档字符串里提到的词误导）
import ast as _ast
_tree = _ast.parse(_src)
_bad_imp = []
for _node in _ast.walk(_tree):
    if isinstance(_node, _ast.Import):
        for _a in _node.names:
            _bad_imp.append(_a.name)
    elif isinstance(_node, _ast.ImportFrom):
        _bad_imp.append(_node.module or "")
check("⑯ log_texts 零依赖（import 语句一条都没有）", not _bad_imp, _bad_imp)
_unnamed, _broken = [], []
for _n, _v in _vals:
    if "{" in _v:
        if "{0}" in _v:
            _unnamed.append(_n)
        try:
            _v.format(**{k: 1 for k in re.findall(r"\{([a-zA-Z_]\w*)[^}]*\}", _v)})
        except Exception:
            _broken.append(_n)
check("⑰ 模板占位符全是命名占位符且能被填满", not _unnamed and not _broken,
      {"unnamed": _unnamed, "broken": _broken})
_res_item = None
for _lr in range(log.rowCount()):
    _c = log.item(_lr, 3) or log.item(_lr, 4)
    if _c is not None and _c.text():
        _res_item = _c
        break
check("⑱ 日志单元格带 tooltip（悬停可看全文）",
      _res_item is not None and _res_item.toolTip() == _res_item.text(),
      (_res_item.text(), _res_item.toolTip()) if _res_item else None)

print("")
print("通过 %d 项，失败 %d 项" % (_pass[0], len(_fails)))
if _fails:
    print("失败项：" + " / ".join(_fails))
sys.exit(1 if _fails else 0)
