# -*- coding: utf-8 -*-
"""
批次4 目标5-M3 验证：**收口产物的自洽性**（截图索引 / 日志里程碑索引 / 验收点清单）

    python dsh_m3_index_check.py

判据（都是"能回答什么情况下为 False"的硬断言）：
    ① 截图索引与截图目录**双向覆盖**：目录里每张 png 都在索引里、索引里每个 png 文件名都真实存在；
    ② 凡是"能被某个 dsh_*_check.py 用例生成"的截图，索引里那一行必须写出那个用例名（防止索引腐化）；
    ③ 日志末尾的《批次4 里程碑索引》里"关键日志条目"一列写的条目名，必须真的能在日志里按行首找到；
    ④ 验收点清单里引用的**用例名 / 截图名 / 方案节号**都真实存在（不许写空话）。
"""
import io
import os
import re

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
SHOT_DIR = r"E:\opencv_python_3_8\backups\_ui_preview"
INDEX = os.path.join(SHOT_DIR, "截图索引.md")
LOG = os.path.join(PROJ, "plan", "pyside6_开发日志.md")
CHECKLIST = os.path.join(PROJ, "plan", "批次4_验收点清单_v1.md")
PLAN = os.path.join(PROJ, "plan", "VisionFlowNode_批次4技术方案_v1.53_2026.10.13.md")
TEMP = os.environ.get("TEMP", "")
# 2026.10.13 起用例在工程内 temp/（本文件所在目录）；%TEMP% 兜底
SUITE_DIRS = [os.path.dirname(os.path.abspath(__file__))] + ([TEMP] if TEMP and os.path.isdir(TEMP) else []) + [d for d in (os.path.join(PROJ, 'temp', 'legacy'), os.path.join(PROJ, 'temp')) if os.path.isdir(d)]   # 批次5 目标1：用例进 tests/，历史留档在 temp/legacy/，工具在 temp/

fails = []


def check(name, cond, extra=None):
    text = '' if extra is None else '   <- ' + str(extra)
    print(('PASS  ' if cond else 'FAIL  ') + name + text)
    if not cond:
        fails.append(name)


def read(path):
    assert os.path.exists(path), '缺文件：%s' % path
    return io.open(path, 'r', encoding='utf-8', newline='').read().replace('\r\n', '\n')


# ======================================================================
# ① 截图索引 ↔ 截图目录 双向覆盖
# ======================================================================
index_text = read(INDEX)
pngs_on_disk = sorted(f for f in os.listdir(SHOT_DIR) if f.lower().endswith('.png'))
pngs_in_index = sorted(set(re.findall(r'`([0-9A-Za-z_\-]+\.png)`', index_text)))

missing_in_index = [p for p in pngs_on_disk if p not in pngs_in_index]
phantom_in_index = [p for p in pngs_in_index if p not in pngs_on_disk]
check('① 截图目录里的每张 png 都登记在索引里（%d 张）' % len(pngs_on_disk),
      missing_in_index == [], missing_in_index)
check('① 索引里写到的每个 png 都真实存在（没有指到不存在的文件）',
      phantom_in_index == [], phantom_in_index)

# ======================================================================
# ② 索引里的"生成"一列必须与实际能生成它的用例一致
# ======================================================================
suite_map = {}
for _d in SUITE_DIRS:
  for name in sorted(os.listdir(_d)):
    if not (name.startswith('dsh_') and name.endswith('_check.py')):
        continue
    src = io.open(os.path.join(_d, name), 'r', encoding='utf-8', newline='').read()
    for png in pngs_on_disk:
        if png in src:
            suite_map.setdefault(png, set()).add(name)

bad_rows = []
for png, suites in sorted(suite_map.items()):
    row = [line for line in index_text.split('\n') if png in line]
    if not row:
        bad_rows.append('%s（索引里没有这一行）' % png)
        continue
    if not any(any(s in line for s in suites) for line in row):
        bad_rows.append('%s（索引那行没写生成它的用例 %s）' % (png, '/'.join(sorted(suites))))
check('② 能被用例重新生成的截图，索引里都写了那个用例名（%d 张）' % len(suite_map),
      bad_rows == [], bad_rows)

# ======================================================================
# ③ 日志《批次4 里程碑索引》里的条目名必须真实存在
# ======================================================================
log_text = read(LOG)
check('③ 日志里已经有《全项目里程碑索引》（2026.10.13 从《批次4 里程碑索引》扩来）',
      '## 全项目里程碑索引' in log_text and '## 批次4 里程碑索引' not in log_text)
entries = set(l.strip() for l in log_text.split('\n') if l.startswith('## '))
idx_start = log_text.find('## 全项目里程碑索引')
idx_text = log_text[idx_start:] if idx_start >= 0 else ''
check('③ 索引已覆盖全项目（早期 / 批次1 / 批次2 / 批次3 / 批次5 五段都在）',
      all(k in idx_text for k in ('早期（未分批次）', '批次1', '批次2', '批次3', '批次5')))
check('③ 索引前言里写明了"新条目带批次号"的口径（用户 2026.10.13 定）',
      '新日志条目的标题带上批次号' in idx_text and '批次6' in idx_text)
head = '\n'.join(log_text.split('\n')[:40])
check('③ 日志**最开头**写明了"标题（日期）命名规则"（含格式串 `批次N目标M-MZ 时间`）',
      '标题（日期）命名规则' in head and '批次N目标M-MZ 时间' in head)
# 时间戳必须单调不减 —— **《总结：…》标题里的日期也一起纳入**（方案 B：顺序靠位置解决，不靠改时间）
_ts = []
for _l in log_text.split('\n'):
    _m = re.match(r'^## (?:总结：[^\n]*?（)?(\d{4})\.(\d+)\.(\d+) (?:\S+ )?(\d{1,2}):(\d{2})', _l)
    if _m and _l.startswith('## '):
        _ts.append(tuple(int(_m.group(k)) for k in (1, 2, 3, 4, 5)))
_bad_ts = [k for k in range(1, len(_ts)) if _ts[k] < _ts[k - 1]]
check('③ 全文件日期单调不减（过程条目 + 总结标题里的日期，共 %d 条）' % len(_ts),
      bool(_ts) and not _bad_ts, _bad_ts[:3])
# 方案 B：只有《全项目里程碑索引》固定在最后；《总结：…》按自己的时间排在中间
_tail = [l for l in log_text.split('\n') if l.startswith('## ')]
check('③ 最后一个二级标题 =《全项目里程碑索引》', _tail[-1].startswith('## 全项目里程碑索引'), _tail[-1][:40])

# ======================================================================
# ④ 验收点清单：引用的用例名 / 截图名 / 方案节号都真实存在
# ======================================================================
list_text = read(CHECKLIST)
suites_referenced = sorted(set(re.findall(r'(dsh_[0-9A-Za-z_]+_check\.py)', list_text)))
missing_suites = [s for s in suites_referenced
                  if not any(os.path.exists(os.path.join(_dd, s)) for _dd in SUITE_DIRS)]
check('④ 验收清单引用的用例名都存在（%d 个）' % len(suites_referenced),
      suites_referenced and missing_suites == [], missing_suites)

shots_referenced = sorted(set(re.findall(r'([0-9A-Za-z_\-]+\.png)', list_text)))
NON_SHOT = {'lena.png'}
missing_shots = [s for s in shots_referenced
                 if s not in NON_SHOT and not os.path.exists(os.path.join(SHOT_DIR, s))]
check('④ 验收清单引用的截图都存在（%d 张）' % len([s for s in shots_referenced if s not in NON_SHOT]),
      shots_referenced and missing_shots == [], missing_shots)
missing_inputs = [s for s in shots_referenced if s in NON_SHOT
                  and not os.path.exists(os.path.join(PROJ, 'image', s))]
check('④ 验收清单里引用的输入测试图（image\\lena.png）存在', missing_inputs == [], missing_inputs)

plan_text = read(PLAN)
sections_referenced = sorted(set(re.findall(r'§[0-9A-Za-z]+(?:\.[0-9]+)*', list_text)))
missing_sections = [s for s in sections_referenced if s[1:] not in plan_text]
check('④ 验收清单引用的方案节号都存在（%d 个）' % len(sections_referenced),
      sections_referenced and missing_sections == [], missing_sections)

print('-' * 70)
if fails:
    print('失败项：%d' % len(fails))
    for name in fails:
        print('   - ' + name)
else:
    print('失败项：无')
import sys
sys.exit(1 if fails else 0)
