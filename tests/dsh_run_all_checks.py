# -*- coding: utf-8 -*-
"""跑一遍所有 dsh_*_check.py，汇总每套的 PASS/FAIL 与退出码"""
import os
import re
import subprocess
import sys

TMP = os.environ.get("TEMP")
# 2026.10.13 起门禁用例搬进工程内 temp/（本脚本所在目录）；%TEMP% 只作兜底，兼容旧位置
_HERE = os.path.dirname(os.path.abspath(__file__))
_SEARCH = [_HERE] + ([TMP] if TMP and os.path.isdir(TMP) else [])
PY = r"E:\opencv_python_3_8\.venv\Scripts\python.exe"
PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"

SKIP = {"dsh_m4_probe.py"}
# 历史留档用例：引用的控件 / 属性在更早的里程碑里就已经删掉或改名（gallery_run_all / run_all_button /
# MainWindow.project_path），本来就跑不过，与本次改动无关 —— 只留档，不当作门禁。
STALE = {"dsh_m2_final_check.py", "dsh_m2_fix_check.py", "dsh_m2_fix2_check.py",
         "dsh_m2_fix3_check.py", "dsh_toolbar_check.py", "dsh_ui_layout_check.py",
         "dsh_ui_toolbar_check.py", "dsh_single_page_check.py"}
_found = set()
for _d in _SEARCH:
    _found |= {f for f in os.listdir(_d)
               if f.startswith("dsh_") and f.endswith("_check.py")
               and f not in SKIP and f not in STALE}
scripts = sorted(_found)

env = dict(os.environ)
env["QT_QPA_PLATFORM"] = "offscreen"
env["PYTHONIOENCODING"] = "utf-8"

total_p = total_f = 0
bad = []
for name in scripts:
    path = next((os.path.join(_d, name) for _d in _SEARCH
                  if os.path.exists(os.path.join(_d, name))), os.path.join(_HERE, name))
    try:
        r = subprocess.run([PY, path], cwd=PROJ, env=env, capture_output=True,
                           timeout=600)
        text = (r.stdout or b"").decode("utf-8", "replace") + \
               (r.stderr or b"").decode("utf-8", "replace")
        p = len(re.findall(r"^PASS", text, re.M))
        f = len(re.findall(r"^FAIL", text, re.M))
        total_p += p
        total_f += f
        flag = "OK " if (r.returncode == 0 and f == 0) else "BAD"
        if flag == "BAD":
            bad.append((name, r.returncode, f))
            fails = [ln for ln in text.splitlines() if ln.startswith("FAIL")]
            print("{0} {1:<34} PASS={2:<4} FAIL={3:<3} exit={4}".format(flag, name, p, f, r.returncode))
            for ln in fails[:8]:
                print("      " + ln)
        else:
            print("{0} {1:<34} PASS={2:<4} FAIL={3:<3} exit={4}".format(flag, name, p, f, r.returncode))
    except Exception as exc:
        bad.append((name, "TIMEOUT/ERR", 0))
        print("ERR {0:<34} {1}".format(name, exc))

print()
print("合计：{0} 套，PASS {1}，FAIL {2}；不合格 {3} 套".format(
    len(scripts), total_p, total_f, len(bad)))
if bad:
    print("不合格：", bad)
sys.exit(1 if bad else 0)
