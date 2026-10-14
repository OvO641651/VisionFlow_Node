# -*- coding: utf-8 -*-
"""按页面记方案路径（新建页面保存要弹选路径、不覆盖别的页面文件）验证脚本，跑完即删"""
import os
import sys
import json
import traceback

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])

import main as m
import widgets.FlowPages as FlowPages

fails = []
msgs = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


class FakeBox(object):
    Question = 0
    AcceptRole = 0
    DestructiveRole = 1
    RejectRole = 2
    choice = "保存"
    exec_count = 0

    def __init__(self, parent=None):
        self._buttons = {}

    def setWindowTitle(self, text):
        pass

    def setIcon(self, icon):
        pass

    def setText(self, text):
        pass

    def addButton(self, text, role):
        button = {"text": text, "role": role}
        self._buttons[text] = button
        return button

    def exec_(self):
        FakeBox.exec_count += 1

    def clickedButton(self):
        return self._buttons.get(FakeBox.choice)

    @staticmethod
    def warning(parent, title, text):
        msgs.append(("warning", title, text))

    @staticmethod
    def information(parent, title, text):
        msgs.append(("information", title, text))


class FakeFileDialog(object):
    """记录被调用了几次；保存对话框返回 save_path"""
    save_path = None
    open_path = None
    save_calls = 0
    open_calls = 0

    @staticmethod
    def getSaveFileName(parent, caption, dir, filters):
        FakeFileDialog.save_calls += 1
        return FakeFileDialog.save_path, ""

    @staticmethod
    def getOpenFileName(parent, caption, dir, filters):
        FakeFileDialog.open_calls += 1
        return FakeFileDialog.open_path, ""


m.QMessageBox = FakeBox
m.QFileDialog = FakeFileDialog
FlowPages.QMessageBox = FakeBox

TMP = os.environ.get("TEMP", PROJ)
f3 = os.path.join(TMP, "dsh_fangan3.vfproj")
fnew = os.path.join(TMP, "dsh_flow_new.vfproj")
for path in (f3, fnew):
    if os.path.exists(path):
        os.remove(path)


def read_file(path):
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


try:
    w = m.MainWindow()
    check("MainWindow 构造成功（不再有窗口级 project_path）", not hasattr(w, "project_path"))
except Exception:
    traceback.print_exc()
    check("MainWindow 构造成功", False)
    sys.exit(1)

tabs = w.flow_page_mgr.tab_widget

# ---------- 1、造一个"方案3"页面并保存成文件 ----------
tabs.setTabText(0, "方案3")
w.add_flow_node("直线识别", QPointF(20, 20))
w.add_flow_node("灰度", QPointF(20, 220))
FakeFileDialog.save_path = f3
FakeFileDialog.save_calls = 0
w.save_project_button.click()
check("第一次保存（页面还没有文件）：弹了选路径窗口", FakeFileDialog.save_calls == 1)
check("方案3 文件已生成", os.path.exists(f3))
check("这一页记住了自己的文件", w.flow_page_mgr.pages[0].get("project_path") == f3,
      w.flow_page_mgr.pages[0].get("project_path"))
check("窗口标题显示该文件", "dsh_fangan3.vfproj" in w.main_window.windowTitle(),
      w.main_window.windowTitle())
f3_before = read_file(f3)

# ---------- 2、新建一个 Flow 页面 → 保存必须弹窗、且不能动方案3的文件 ----------
w.flow_page_mgr.add_page()
tabs.setTabText(tabs.count() - 2, "Flow")
w.add_flow_node("圆识别", QPointF(50, 50))
new_page = w.flow_page_mgr.pages[-1]
check("新建页面没有对应文件", new_page.get("project_path") is None, new_page.get("project_path"))

FakeFileDialog.save_path = fnew
FakeFileDialog.save_calls = 0
w.save_project_button.click()
check("新建页面保存：弹了选路径窗口（以前是直接覆盖方案3）", FakeFileDialog.save_calls == 1)
check("新文件已按选择生成", os.path.exists(fnew))
check("新页面记住了新文件", new_page.get("project_path") == fnew)
check("**方案3 的文件没有被改动**", read_file(f3) == f3_before,
      (read_file(f3).get("pages", [{}])[0].get("title"), f3_before.get("pages", [{}])[0].get("title")))
check("方案3 页面自己的文件路径没被改写",
      w.flow_page_mgr.pages[0].get("project_path") == f3)

# ---------- 3、切回方案3 页面再保存：不应弹窗，写回它自己的文件 ----------
tabs.setCurrentIndex(0)
check("窗口标题跟着当前页走（方案3 的文件）",
      "dsh_fangan3.vfproj" in w.main_window.windowTitle(), w.main_window.windowTitle())
FakeFileDialog.save_path = None      # 若真弹窗，会写到 None → 必然失败
FakeFileDialog.save_calls = 0
w.save_project_button.click()
check("已有文件的页面：保存不弹窗", FakeFileDialog.save_calls == 0)
check("写回的是它自己的文件（内容仍是方案3）",
      read_file(f3)["pages"][0]["title"] == "方案3", read_file(f3)["pages"][0]["title"])
check("新页面的文件没被动", read_file(fnew)["pages"][0]["title"] == "Flow",
      read_file(fnew)["pages"][0]["title"])

# ---------- 4、只清"刚存的那一页"的未保存标记 ----------
tabs.setCurrentIndex(0)
w.flow_page_mgr.mark_dirty(w.flow_page_mgr.pages[0])          # 方案3 页：脏
w.flow_page_mgr.mark_dirty(new_page)                           # Flow 页：脏
tabs.setCurrentIndex(tabs.indexOf(new_page["widget"]))
w.save_project()                                               # 存 Flow 页
check("存了 Flow 页之后：Flow 页变干净", new_page["dirty"] is False)
check("方案3 页仍然算'有未保存改动'（没被一起清掉）",
      w.flow_page_mgr.pages[0]["dirty"] is True)

# ---------- 5、打开一个方案文件：新页记住它来自哪个文件 ----------
tabs.setCurrentIndex(0)
w._write_project_file(f3)                        # 让方案3 页与文件内容一致
before = len(w.flow_page_mgr.pages)
w.load_project(f3)                               # 内容相同 → 去重，不新增
check("内容相同的方案：去重不新增", len(w.flow_page_mgr.pages) == before)

# 造一个"工作区没有"的单页方案，打开它 → 新页要记住这个文件
外来 = os.path.join(TMP, "dsh_wailai.vfproj")
with open(外来, "w", encoding="utf-8") as fp:
    json.dump({"format": m.MainWindow.PROJECT_FORMAT, "version": 1, "current_page": 0,
               "pages": [{"title": "外来页", "nodes": [{"id": 0, "name": "直线识别", "x": 3.0,
                                                       "y": 3.0, "input_source": None,
                                                       "params": {}}], "edges": []}]},
              fp, ensure_ascii=False)
w.load_project(外来)
loaded = w.flow_page_mgr.pages[-1]
check("打开进来的页面记住了它来自哪个文件",
      loaded.get("project_path") == 外来, loaded.get("project_path"))
check("切到它之后标题显示该文件",
      "dsh_wailai.vfproj" in w.main_window.windowTitle(), w.main_window.windowTitle())

# ---------- 6、回归 ----------
bad = os.path.join(TMP, "dsh_path_bad.vfproj")
with open(bad, "w", encoding="utf-8") as fp:
    fp.write("{ not json")
pages_now = len(w.flow_page_mgr.pages)
msgs[:] = []
check("坏 JSON 仍返回 False + 提示 + 不动现场",
      w.load_project(bad) is False and len(w.flow_page_mgr.pages) == pages_now
      and bool([x for x in msgs if x[0] == "warning"]), msgs)

for path in (f3, fnew, 外来, bad):
    try:
        os.remove(path)
    except OSError:
        pass

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
