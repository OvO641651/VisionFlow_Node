# -*- coding: utf-8 -*-
"""
M4 的门禁用例：**文档 ↔ 代码一致性**（`dsh_doc_consistency_check.py`）—— 第二版（修掉首版的误判）。

    python dsh_doc_consistency_check.py

判据：
    ① 三份文档里提到的每个 `.py` **工程文件**都真实存在（排除 `dsh_*` 门禁用例名 / 含通配符的写法）；
    ② 文档反引号里的项目内符号（`_xxx(` / `Xxx(`，排除 Qt 的 `Q*`）在工程源码里能搜到；
    ③ 《项目技术文档》里写的"门禁套数"与实测一致；两份技术文档写的"项数"彼此一致；
    ④ 《项目技术文档》§五 算子表 ↔ `NodeRegistry.NODE_SPECS` 完全一致（14 个）；
    ⑤ 文档引用的**方案版本文件名**真实存在；
    ⑥ 《用户手册》的《目录》每一项都能对上真实二级标题；
    ⑦ 三份文档的"版本号"与文件名一致（用户 2026.10.16 口径：三份文档各升一级 —— v1.0→v1.1 · v1.2→v1.3）；
    ⑧ 《代码说明书》不再出现"人脸/颜色 未实现"与旧行数，且已补 4 个新文件章节。
"""
import io
import os
import re
import sys

PROJ = r'E:\opencv_python_3_8\PySide\VisionFlowNoed'
PLAN = os.path.join(PROJ, 'plan')
DOCS = {
    '用户手册': 'VisionFlowNode_用户手册_v1.1_2026.10.7.md',
    '代码说明书': 'VisionFlowNode_代码说明书_v1.1_2026.10.7.md',
    '项目技术文档': 'VisionFlowNode_项目技术文档_v1.3_2026.10.7.md',
}
TEMP = os.environ.get('TEMP', '')
# 2026.10.13 起用例在工程内 temp/（本文件所在目录）；%TEMP% 兜底
SUITE_DIRS = [os.path.dirname(os.path.abspath(__file__))] + ([TEMP] if TEMP and os.path.isdir(TEMP) else [])
STALE = {'dsh_m2_final_check.py', 'dsh_m2_fix_check.py', 'dsh_m2_fix2_check.py', 'dsh_m2_fix3_check.py',
         'dsh_toolbar_check.py', 'dsh_ui_layout_check.py', 'dsh_ui_toolbar_check.py', 'dsh_single_page_check.py'}
fails = []


def check(name, cond, extra=None):
    print(('PASS  ' if cond else 'FAIL  ') + name + ('' if extra is None else '   <- ' + str(extra)))
    if not cond:
        fails.append(name)


def read(path):
    return io.open(path, 'r', encoding='utf-8', newline='').read().replace('\r\n', '\n')


docs = {k: read(os.path.join(PLAN, v)) for k, v in DOCS.items()}
# 批次5 目标1 目录重构后：源码按包分目录 ⇒ 全树扫描（跳过 temp/ 与 __pycache__）
PY_FILES = {}
for _root, _dirs, _files in os.walk(PROJ):
    _dirs[:] = [d for d in _dirs if d not in ('temp', '__pycache__', '.dsh-meow')]
    for _f in _files:
        if _f.endswith('.py'):
            PY_FILES.setdefault(_f, os.path.join(_root, _f))
sources = '\n'.join(read(v) for _, v in sorted(PY_FILES.items()))
print('载入：三份文档 + 工程源码 %d 字符' % len(sources))

# ---- ① 工程 .py 文件存在 ----
# 规矩：文档里写**规划中 / 尚未创建**的文件时不要带 `.py` 后缀（写成 `core/flow_engine`），
#       否则本检查会把它当成"文档提到的工程 .py"而报缺失（2026.10.13 就是这么抓出一处歧义的）。
bad = []
for label, text in docs.items():
    for m in sorted(set(re.findall(r'([A-Za-z_][A-Za-z0-9_]*\.py)', text))):
        if m.startswith('dsh') or m == '_check.py':        # 门禁用例名（在 %TEMP%，不是工程文件）
            continue
        if m not in PY_FILES:
            bad.append('%s: %s' % (label, m))
check('① 三份文档提到的工程 .py 都真实存在', bad == [], bad)

# ---- ② 文档里的项目内符号存在 ----
sym_bad, seen = [], set()
for label, text in docs.items():
    for raw in re.findall(r'`([A-Za-z_][A-Za-z0-9_.]*)\s*\(', text):
        base = raw.split('.')[-1]
        if raw.count('.') > 1:
            continue
        if not (base.startswith('_') or (base[:1].isupper() and not base.startswith('Q'))):
            continue
        if (label, base) in seen:
            continue
        seen.add((label, base))
        if base not in sources:
            sym_bad.append('%s: %s' % (label, base))
check('② 文档里的项目内符号在源码里都能搜到（%d 个）' % len(seen), sym_bad == [], sym_bad[:6])

# ---- ③ 门禁口径 ----
suites = sorted({f for _d in SUITE_DIRS for f in os.listdir(_d)
                 if f.startswith('dsh_') and f.endswith('_check.py') and f not in STALE})
n_suites = len(suites)
td = docs['项目技术文档']
nums = re.findall(r'(\d+)\s*套用例\s*/\s*(\d+)\s*项断言', td)
check('③ 《项目技术文档》写了"N 套用例 / M 项断言"', bool(nums), nums)
if nums:
    # ★ 2026.10.15（批次5 目标2）口径升级：《项目技术文档》是**冻结**的（写的是批次4 收口时的
    #   37 套 861 项），而门禁会随批次增长 ⇒ 这里从"相等"改成"**只增不减**"：
    #   既能保住"套数一个不少"，又不用去动冻结文档。**精确相等**改由 ③d 盯现行方案。
    check('③ 门禁套数只增不减（冻结文档写的不超过实测；%d）' % n_suites,
          int(nums[0][0]) <= n_suites, '文档 %s / 实测 %d' % (nums[0][0], n_suites))
else:
    check('③ 门禁套数只增不减（冻结文档写的不超过实测；%d）' % n_suites, False)
cm_nums = re.findall(r'(\d+)\s*套用例\s*/\s*(\d+)\s*项断言', docs['代码说明书'])
check('③ 两份技术文档的"项数"一致（若都写了）',
      (not nums or not cm_nums or nums[0][1] == cm_nums[0][1]),
      (nums[:1], cm_nums[:1]))
# ③d ★ 现行口径真源 =《批次6 技术方案》：写的套数必须**正好等于**实测
#   （★ 2026.10.17 批次6 目标1-M1：口径校验目标从《批次5 技术方案》**移交**到《批次6 技术方案》，
#     批次5 方案同日冻结、只作历史；已在其冻结标记处补一句"门禁口径已移交"。）
_p6 = sorted(f for f in os.listdir(PLAN)
             if f.startswith('VisionFlowNode_批次6技术方案_v') and f.endswith('.md'))
p6 = read(os.path.join(PLAN, _p6[-1])) if _p6 else ''
p6_nums = re.findall(r'(\d+)\s*套\s*(\d+)\s*项断言', p6)
check('③ 《批次6 技术方案》写的套数 = 实测套数（%d）' % n_suites,
      bool(p6_nums) and int(p6_nums[0][0]) == n_suites,
      (_p6[-1:] or 'plan 里缺《批次6 技术方案》', p6_nums[:1], '实测 %d 套' % n_suites))

# ---- ④ §五 算子表 ↔ NODE_SPECS ----
sec5 = td[td.index('## 五、算子全景'):td.index('## 六、进度与验证方式')]
names = []
for l in sec5.split('\n'):
    if not l.startswith('|'):
        continue
    cells = [c.strip() for c in l.strip('|').split('|')]
    if len(cells) >= 2 and cells[0] in ('采集', '处理', '检测', '识别'):
        names.append(cells[1].replace('**', '').strip())
sys.path.insert(0, PROJ)
os.chdir(PROJ)
from core.NodeRegistry import NODE_SPECS          # noqa: E402
check('④ §五 算子表条数 = 注册表算子数（%d）' % len(NODE_SPECS), len(names) == len(NODE_SPECS),
      '表 %d 行 / 注册表 %d 个' % (len(names), len(NODE_SPECS)))
check('④ §五 表里的算子名都在注册表里', [n for n in names if n not in NODE_SPECS] == [],
      [n for n in names if n not in NODE_SPECS])
check('④ 注册表里的算子都写进了 §五 表', [n for n in NODE_SPECS if n not in names] == [],
      [n for n in NODE_SPECS if n not in names])

# ---- ⑤ 引用的方案版本文件存在 ----
refs = set()
for text in docs.values():
    refs |= set(re.findall(r'(VisionFlowNode_批次4技术方案_v[0-9.]+_[0-9.]+\.md)', text))
bad_ref = [r for r in sorted(refs) if not os.path.exists(os.path.join(PLAN, r))]
check('⑤ 文档引用的方案版本文件都存在（%d 个）' % len(refs), refs and bad_ref == [], bad_ref)

# ---- ⑥ 用户手册目录 ↔ 标题 ----
um = docs['用户手册']
toc = um[um.index('## 目录'):um.index('\n## ', um.index('## 目录') + 5)]
toc_items = [t.strip() for t in re.findall(r'\[([^\]]+)\]\(#', toc)]
headings = [l[3:].strip() for l in um.split('\n') if l.startswith('## ')]
missing_toc = [it for it in toc_items if not any(it in h for h in headings)]
check('⑥ 用户手册《目录》每一项都对得上真实标题（%d 项）' % len(toc_items),
      bool(toc_items) and missing_toc == [], missing_toc)

# ---- ⑦ 版本号与文件名一致 ----
ver_ok = []
for label, fname in DOCS.items():
    m = re.search(r'_v([0-9.]+)_', fname)
    ver = m.group(1) if m else ''
    text = docs[label]
    ver_ok.append((label, ver, ('文档版本：v%s' % ver) in text or ('**v%s**' % ver) in text))
check('⑦ 三份文档声明的版本号与文件名一致', all(ok for _, _, ok in ver_ok), ver_ok)

# ---- ⑧ 代码说明书旧口径清干净 ----
cm = docs['代码说明书']
check('⑧ 代码说明书不再说"人脸/颜色 未实现"', '人脸/颜色' not in cm and '颜色目前 False' not in cm)
old_counts = ['3221 行', '259 行', '319 行', '317 行', '512 行', '433 行']
check('⑧ 代码说明书没有残留旧行数', [k for k in old_counts if k in cm] == [],
      [k for k in old_counts if k in cm])
check('⑧ 代码说明书已补 4 个新文件章节',
      all(('## %s（' % f) in cm for f in ('ParamRules.py', 'ImageIO.py', 'ColorExtractOps.py', 'FaceDetectOps.py')))

print('-' * 70)
print('失败项：%d' % len(fails))
for f in fails:
    print('   - ' + f)
sys.exit(1 if fails else 0)
