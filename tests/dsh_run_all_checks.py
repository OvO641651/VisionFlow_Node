# -*- coding: utf-8 -*-
"""跑一遍所有 dsh_*_check.py，汇总每套的 PASS/FAIL 与退出码"""
import io
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
# ★ 批次5 目标2 补：参数窗口宽度那几套（dsh_m2_ctrl_check / dsh_roi_default_check / dsh_dlg_width_check）
#   量的是"文字排版之后的真实宽度"，**不指定字体目录**时 Qt 会退回另一种字体，宽度直接飙到 380+
#   ⇒ 4 项断言假失败（实测：不设 = 857 过 / 4 失败；设上 = 861 过 / 0 失败）。
#   由门禁自己兜住，换个人跑 / 换个终端也不会莫名其妙红；目录不存在就跳过（非 Windows）。
_FONTDIR = r"C:\Windows\Fonts"
if os.path.isdir(_FONTDIR):
    env["QT_QPA_FONTDIR"] = _FONTDIR

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

# ★ 批次5 目标2 补：门禁的"套数 / 项数"是**不变量** —— 精确数字必须与**现行方案
#   《批次6 技术方案》**里写的一致（三份冻结文档写的是批次4 收口时的 37 套 861 项，
#   它们不动，所以"只增不减"那条由 dsh_doc_consistency_check 管，这里管"精确相等"）。
#   ★ 批次6 目标1-M1（2026.10.17）：口径校验目标**从《批次5 技术方案》移交到《批次6 技术方案》**
#     （批次5 方案同日冻结；已在其冻结标记处补一句"门禁口径已移交"）。
_plan_dir = os.path.join(PROJ, "plan")
_plans = sorted(f for f in os.listdir(_plan_dir)
                if f.startswith("VisionFlowNode_批次6技术方案_v") and f.endswith(".md"))
_total = total_p + total_f
if _plans:
    _txt = io.open(os.path.join(_plan_dir, _plans[-1]), "r", encoding="utf-8").read()
    _m = re.findall(r"(\d+)\s*套\s*(\d+)\s*项断言", _txt)
    if not _m:
        bad.append(("方案没写口径", _plans[-1]))
        print("BAD 《批次6 技术方案》里没找到形如「N 套 M 项断言」的口径")
    elif int(_m[0][0]) != len(scripts) or int(_m[0][1]) != _total:
        bad.append(("方案写的口径不一致", "方案 %s 套 %s 项 / 实测 %d 套 %d 项"
                    % (_m[0][0], _m[0][1], len(scripts), _total)))
        print("BAD 门禁口径与《批次6 技术方案》写的不一致：方案 %s 套 %s 项 / 实测 %d 套 %d 项"
              % (_m[0][0], _m[0][1], len(scripts), _total))
    else:
        print("OK  门禁口径与《批次6 技术方案》一致（%s 套 %s 项断言；%s）"
              % (_m[0][0], _m[0][1], _plans[-1]))
else:
    print("（提示：plan\\ 里没有《批次6 技术方案》，跳过口径对照）")

if bad:
    print("不合格：", bad)
sys.exit(1 if bad else 0)
