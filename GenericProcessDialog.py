# -*- coding: utf-8 -*-
"""
通用参数窗口：按算子的"参数声明（param_specs）"自动生成"运行参数"页。

为什么要它（批次4 决策 b）：
    处理类算子会一批批加（取反 / 滤波 / 二值化 / 形态学 / 边缘提取 …）。
    按老办法"一个算子一份 .ui + 一套读写代码"，加第 6 个算子就得把第 1 个的活儿
    再干一遍；改成"参数变成声明、界面由声明生成"之后，新增一个算子只需要：
        写一个算法方法 + 在 ProcessOps.PROCESS_SPECS 里加一张参数表
        （+ main.ui 树里加一项），**不用再动界面代码**。

它继承 LineParamsDialog，所以"基本参数"页整套行为原样复用：
图像源、ROI 创建（绘制 / 继承上游）、继承自、外扩、框选、XYWH ——
那一页装的是**引擎级通用能力**，每个算子都要用，不该各写一遍。

本项目参数窗口的"三页语义"（新加算子时照这个判断该改哪页）：
    基本参数 —— 共用 LineParamsDialog.ui（引擎级，算子一律不改）
    运行参数 —— 本窗口按 param_specs 动态生成（算子私有参数）
    显示结果 —— 按算子类型：处理类没有结构化结果 → 直接 removeTab 去掉

控件类型（和 ProcessOps.PROCESS_SPECS 里的声明一一对应）：
    int   -> QSpinBox（odd=True 时步长 2、并把偶数纠正成奇数）
    float -> QDoubleSpinBox
    combo -> QComboBox
    bool  -> QCheckBox
    file  -> QLineEdit + "浏览…" 按钮
控件名字统一是 param_<参数名>，方便 findChild / 排查问题。
"""

from PySide2.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from LineParamsDialog import LineParamsDialog
from NodeRegistry import get_spec

# 直线专用、但要被通用窗口藏起来的控件（它们的值对处理类算子没有意义）
LINE_ONLY_WIDGETS = ("canny_low", "canny_high", "spin_canny_low", "spin_canny_high",
                     "spin_hough_threshold", "spin_min_line_length", "spin_max_line_gap")


class GenericProcessDialog(LineParamsDialog):
    """按 param_specs 生成"运行参数"页的通用参数窗口（处理类算子用）"""

    def __init__(self, parent=None, node=None, main_window=None):
        # 动态控件的注册表要先建好：父类 __init__ 末尾会调一次 _load_params()，
        # 那时候动态控件还没生成，靠这个空表跳过动态部分，之后再手动加载一次。
        self.param_controls = {}
        self.param_layout = None
        super().__init__(parent, node, main_window)

        self.spec = get_spec(node.name) if node is not None else None
        title = getattr(self.spec, "name", None) or (node.name if node is not None else "运行参数")
        self.setWindowTitle(title)

        self._build_param_rows()      # 生成"运行参数"页（内部会先藏掉直线专用那几行）
        self._remove_result_tab()     # 处理类没有结构化结果 → 去掉"显示结果"页
        self._load_params()           # 再加载一次：这回把动态控件也灌上值

    # ------------------------------------------------------------------
    # 生成界面
    # ------------------------------------------------------------------
    def _param_group_layout(self):
        """"运行参数"页里放行的那个垂直布局（.ui 里叫 verticalLayout_8）"""
        layout = self.ui.findChild(QVBoxLayout, "verticalLayout_8")
        if layout is not None:
            return layout
        # 兜底：万一 .ui 里布局改名了，就在"运行参数"分组框里自己加一个竖排布局
        group = self.ui.findChild(QGroupBox, "groupBox_3")
        if group is not None and group.layout() is not None:
            layout = QVBoxLayout()
            group.layout().addLayout(layout)
            return layout
        return None

    @staticmethod
    def _hide_item(item):
        """把一个布局项（控件或嵌套布局）里的所有控件都藏起来"""
        widget = item.widget()
        if widget is not None:
            widget.setVisible(False)
            return
        child = item.layout()
        if child is not None:
            for index in range(child.count()):
                GenericProcessDialog._hide_item(child.itemAt(index))

    def _hide_line_rows(self, layout):
        """
        把"运行参数"页里**已有的行**藏起来——那些是直线专用控件
        （Canny 阈值 / Hough 阈值 / 最小线长 / 最大线间隙），处理类用不上。
        按布局项遍历，不依赖控件名，所以 .ui 里改个名字也不会失效。
        """
        for index in range(layout.count()):
            self._hide_item(layout.itemAt(index))

    def _build_param_rows(self):
        """按 param_specs 生成"运行参数"页的行"""
        layout = self._param_group_layout()
        if layout is None:
            return
        self._hide_line_rows(layout)
        self.param_layout = layout

        specs = list(getattr(self.spec, "param_specs", None) or [])
        if not specs:
            hint = QLabel("该模块没有可调参数（只按基本参数里的 ROI / 继承处理）")
            hint.setStyleSheet("color: #888888;")
            layout.addWidget(hint)
            layout.addStretch(1)
            return

        for key, label, kind, options in specs:
            widget = self._make_widget(key, kind, options)
            if widget is None:
                continue
            self.param_controls[key] = widget
            row = QHBoxLayout()
            row.addWidget(QLabel("{0}:".format(label)))
            row.addWidget(widget, 1)
            layout.addLayout(row)
        layout.addStretch(1)

    def _make_widget(self, key, kind, options):
        """按控件类型造控件；造不出来返回 None（该参数就当不存在，界面不崩）"""
        options = options or {}
        if kind == "combo":
            widget = QComboBox()
            widget.addItems([str(item) for item in options.get("options", [])])
            default = options.get("default")
            if default is not None:
                widget.setCurrentText(str(default))
        elif kind == "int":
            widget = QSpinBox()
            widget.setRange(int(options.get("min", 0)), int(options.get("max", 9999)))
            widget.setValue(int(options.get("default", 0)))
            if options.get("odd"):
                # 卷积核尺寸必须是奇数：步长 2，再把手动输入 / 默认值里的偶数纠正过来
                widget.setSingleStep(2)
                widget.valueChanged.connect(
                    lambda value, box=widget: box.setValue(self._to_odd(value)))
        elif kind == "float":
            widget = QDoubleSpinBox()
            widget.setDecimals(int(options.get("decimals", 2)))
            widget.setRange(float(options.get("min", 0.0)), float(options.get("max", 9999.0)))
            widget.setSingleStep(float(options.get("step", 1.0)))
            widget.setValue(float(options.get("default", 0.0)))
        elif kind == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(options.get("default", False)))
        elif kind == "file":
            widget = QWidget()
            row = QHBoxLayout(widget)
            row.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit(str(options.get("default", "")))
            browse = QPushButton("浏览…")
            browse.clicked.connect(
                lambda _checked=False, target=edit, filters=options.get("filter", "所有文件 (*.*)"):
                self._browse_file(target, filters))
            row.addWidget(edit)
            row.addWidget(browse)
            widget.edit = edit          # 取值时用它（见 _widget_value）
        else:
            return None

        widget.setObjectName("param_{0}".format(key))
        return widget

    @staticmethod
    def _to_odd(value):
        """偶数 → 最近的奇数（卷积核 / 自适应阈值块都要求奇数）"""
        value = int(value)
        return value + 1 if value % 2 == 0 else value

    def _browse_file(self, edit, filters):
        """file 类型参数右边那个"浏览…"按钮"""
        path, _selected = QFileDialog.getOpenFileName(self, "选择文件", edit.text(), filters)
        if path:
            edit.setText(path)

    def _remove_result_tab(self):
        """处理类没有结构化结果 → 去掉"显示结果"页（那页是结果计数）"""
        result_page = self.ui.findChild(QWidget, "tab_3")
        if result_page is None:
            return
        index = self.ui.tabWidget.indexOf(result_page)
        if index >= 0:
            self.ui.tabWidget.removeTab(index)

    # ------------------------------------------------------------------
    # 参数读写：基本参数交给父类，动态控件由本类处理
    # ------------------------------------------------------------------
    def _load_params(self):
        super()._load_params()          # 图像源 / ROI / 继承 / 外扩 / 框选（父类那套）
        controls = getattr(self, "param_controls", None) or {}
        if not controls or self.node is None:
            return
        for key, _label, kind, options in list(getattr(self.spec, "param_specs", None) or []):
            widget = controls.get(key)
            if widget is None:
                continue
            value = self.node.params.get(key, (options or {}).get("default"))
            self._set_widget_value(kind, widget, value)

    def _update_params(self):
        super()._update_params()        # 基本参数照旧存
        if self.node is None:
            return

        # 父类会把直线专用的 5 个参数也写进 node.params（那些控件只是被藏起来了，
        # 值还在）——通用窗口的算子用不上，这里**先**删掉。
        # 注意这一步必须放在下面"没有动态控件就返回"之前：取反这类没有参数的算子
        # 也得把直线参数清掉，否则会混进节点参数和方案文件里。
        for key in ("canny_low", "canny_high", "hough_threshold",
                    "min_line_length", "max_line_gap"):
            self.node.params.pop(key, None)

        controls = getattr(self, "param_controls", None) or {}
        for key, _label, kind, _options in list(getattr(self.spec, "param_specs", None) or []):
            widget = controls.get(key)
            if widget is None:
                continue
            self.node.params[key] = self._widget_value(kind, widget)

    def _set_widget_value(self, kind, widget, value):
        if value is None:
            return
        if kind == "combo":
            widget.setCurrentText(str(value))
        elif kind == "int":
            widget.setValue(int(value))
        elif kind == "float":
            widget.setValue(float(value))
        elif kind == "bool":
            widget.setChecked(bool(value))
        elif kind == "file":
            widget.edit.setText(str(value))

    def _widget_value(self, kind, widget):
        if kind == "combo":
            return widget.currentText()
        if kind == "int":
            return widget.value()
        if kind == "float":
            return widget.value()
        if kind == "bool":
            return widget.isChecked()
        if kind == "file":
            return widget.edit.text()
        return None
