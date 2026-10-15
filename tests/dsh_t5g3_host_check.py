# -*- coding: utf-8 -*-
"""
批次5 目标3 收尾（B′ 方案）：**宿主契约 `MainHost`** 的自洽性（2026.10.15）

    python dsh_t5g3_host_check.py

背景：6 个 Mixin 的 `self.xxx` 里有 **65 个名字**（25 个状态字段 + 40 个方法）定义在**别的文件**里，
PyCharm 只做单文件分析 ⇒ 这些引用点（6 个文件合计 211 个）会报"未解析的特性引用"。
解法 = 把清单**集中声明**在 `core/host_contract.py::MainHost`，6 个 Mixin 都继承它
（声明写在 `if TYPE_CHECKING:` 里 ⇒ **运行时它是个空类**，零行为影响）。

判据（每条都能回答"什么情况下为 False"）：

    ① 清单里每个名字都能在**真实的** `MainWindow` 实例上取到（`hasattr`）—— 不许声明不存在的东西；
    ② 6 个 Mixin 里**所有跨文件的 `self.X` 引用**都已在清单里 —— 漏一个 ⇒ 那条警告就回潮；
    ③ 清单 = **真正依赖的名字集合**（多一个 / 少一个都不一致，且不许重复声明）；
    ④ **运行时它就是空壳**：`vars(MainHost)` 里除 dunder 外没有任何成员
       —— 否则可能遮蔽真实属性 / 把"声明"变成"实现"，这条最关键；
    ⑤ MRO：6 个 Mixin 都**直接**继承 `MainHost`，`MainHost` 只继承 `object`，`MainWindow` 的 MRO 里含 `MainHost`。
"""
import ast
import io
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
MIXINS = ["core/flow_engine.py", "core/project_store.py", "core/param_store.py",
          "services/camera_service.py", "services/video_service.py", "services/gallery_service.py",
          "services/undo_service.py"]
HOST = "core/host_contract.py"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication        # noqa: E402
app = QApplication([])
import main as m                                  # noqa: E402
from core import host_contract                    # noqa: E402
from core.flow_engine import FlowEngineMixin       # noqa: E402
from core.param_store import ParamStoreMixin       # noqa: E402
from core.project_store import ProjectStoreMixin   # noqa: E402
from services.camera_service import CameraMixin    # noqa: E402
from services.video_service import VideoMixin      # noqa: E402
from services.gallery_service import GalleryMixin  # noqa: E402
from services.undo_service import UndoMixin        # noqa: E402

MIXIN_CLASSES = [FlowEngineMixin, ParamStoreMixin, ProjectStoreMixin,
                 CameraMixin, VideoMixin, GalleryMixin, UndoMixin]

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


def read(path):
    return io.open(os.path.join(PROJ, path.replace("/", os.sep)), encoding="utf-8").read()


def self_loads(text):
    """方法体里读到的 `self.<名字>`（不含 `self.x = …` 的左边）"""
    tree = ast.parse(text)
    out = set()
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for n in ast.walk(fn):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
                    and n.value.id == "self" and isinstance(n.ctx, ast.Load):
                out.add(n.attr)
    return out


def host_names(text):
    """本文件定义的"属于 MainWindow 的名字"：`self.x = …` / 类体赋值 / 类里的方法"""
    tree = ast.parse(text)
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
                and n.value.id == "self" and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.attr)
        if isinstance(n, ast.ClassDef):
            for st in n.body:
                if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.add(st.name)
                elif isinstance(st, ast.Assign):
                    for tg in st.targets:
                        if isinstance(tg, ast.Name):
                            out.add(tg.id)
                elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    out.add(st.target.id)
    return out


def declared_names(text):
    """`MainHost` 里声明的名字（`if TYPE_CHECKING:` 那些注解）—— 连重复也数出来"""
    tree = ast.parse(text)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MainHost")
    seq = []
    for st in ast.walk(cls):
        if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
            seq.append(st.target.id)
    return seq


# ---------------------------------------------------------------- 算实测需要哪些名字
defined = {f: host_names(read(f)) for f in MIXINS}
needed = set()
for f in MIXINS:
    for name in self_loads(read(f)):
        if name in defined[f]:
            continue
        if any(name in defined[g] for g in MIXINS):     # 定义在**别的** Mixin 里 ⇒ 跨文件
            needed.add(name)
        elif name in host_names(read("main.py")):       # 定义在 main.py 里 ⇒ 也算跨文件
            needed.add(name)
        # 两边都没有 = "真缺失"，那是另一类 bug（temp\dsh_t5g2_self_contract_check.py 管）

declared_seq = declared_names(read(HOST))
declared = set(declared_seq)

# ---------------------------------------------------------------- ① 声明的名字真实存在
w = m.MainWindow()
missing_real = sorted(n for n in declared if not hasattr(w, n))
check("① 清单里每个名字都能在真实 MainWindow 上取到（%d 个）" % len(declared),
      missing_real == [], missing_real)

# ---------------------------------------------------------------- ② 跨文件引用都声明了
undeclared = sorted(n for n in needed if n not in declared)
check("② Mixin 的跨文件 self.X 引用都已声明（需要 %d 个）" % len(needed),
      undeclared == [], undeclared)

# ---------------------------------------------------------------- ③ 清单 = 依赖（含不许重复）
check("③ 清单 = 真正依赖的名字集合（多/少/重复都不行）",
      declared == needed and len(declared_seq) == len(declared),
      (sorted(declared - needed), sorted(needed - declared), len(declared_seq) - len(declared)))

# ---------------------------------------------------------------- ④ 运行时是空壳
extra_members = sorted(n for n in vars(host_contract.MainHost) if not n.startswith("__"))
check("④ 运行时 MainHost 是空壳（除 dunder 外无成员）", extra_members == [], extra_members)

# ---------------------------------------------------------------- ⑤ MRO
mro_bad = [c.__name__ for c in MIXIN_CLASSES if len(c.__mro__) < 2 or c.__mro__[1] is not host_contract.MainHost]
check("⑤ 7 个 Mixin 都直接继承 MainHost",
      mro_bad == [] and host_contract.MainHost.__mro__ == (host_contract.MainHost, object)
      and host_contract.MainHost in m.MainWindow.__mro__,
      (mro_bad, host_contract.MainHost.__mro__, host_contract.MainHost in m.MainWindow.__mro__))

print("-" * 70)
print("清单：%d 个名字（需要在 %d 个）；覆盖 6 个 Mixin 的跨文件引用" % (len(declared), len(needed)))
if fails:
    print("失败项：%d" % len(fails))
    for name in fails:
        print("   - " + name)
else:
    print("失败项：无")
sys.exit(1 if fails else 0)
