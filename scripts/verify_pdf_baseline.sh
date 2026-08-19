#!/usr/bin/env bash
# verify_pdf_baseline.sh
#
# CONST-01 guard for v39.0.0 — Word 脱敏重做。
# 验证 HEAD..v38.0.1-pdf-baseline 之间没有任何 PDF 端脱敏代码被修改。
#
# 用法：
#   ./scripts/verify_pdf_baseline.sh           # 检查 HEAD
#   ./scripts/verify_pdf_baseline.sh <ref>     # 检查 <ref>..HEAD
#
# 退出码：
#   0 = PASS（PDF 端未触动）
#   1 = FAIL（PDF 端有修改，需立即修复 / 回滚）
#   2 = ERROR（tag 缺失 / 环境异常）
#
# 被守护的 PDF 端代码：
#   secureredact/ocr/text_pdf.py         — PDF 文本通道
#   secureredact/ocr/mixed_pdf.py        — PDF 混合通道（v39.6 仅 import，不修改）
#   secureredact/workers/ocr_worker.py   — OCRWorker（PDF）— 含 page_result_signal payload
#
# 任何不在以上列表中但属于 PDF 端路径的文件，应更新本脚本的 PDF_GUARD_PATHS。

set -uo pipefail

PDF_BASELINE_TAG="${PDF_BASELINE_TAG:-v38.0.1-pdf-baseline}"
REF="${1:-${PDF_BASELINE_TAG}}"

PDF_GUARD_PATHS=(
    "secureredact/ocr/text_pdf.py"
    "secureredact/ocr/mixed_pdf.py"
    "secureredact/workers/ocr_worker.py"
)

cd "$(git rev-parse --show-toplevel)" || { echo "ERROR: not in a git repo" >&2; exit 2; }

# 1) baseline tag 必须存在
if ! git rev-parse --verify "${REF}" >/dev/null 2>&1; then
    echo "ERROR: baseline tag '${REF}' not found" >&2
    echo "  → create it: git tag ${PDF_BASELINE_TAG} <commit-before-v39-work>" >&2
    exit 2
fi

echo ">>> CONST-01 guard: PDF baseline diff ${REF}..HEAD"
echo "    guarded paths:"
for p in "${PDF_GUARD_PATHS[@]}"; do
    echo "      - $p"
done
echo ""

# 2) 收集所有变更的 PDF 端文件 — 三层检查：committed / staged / working tree
violations=0

# 2a) committed: ref..HEAD
committed_changes="$(git diff --name-only "${REF}..HEAD" -- 'secureredact/ocr/' 'secureredact/workers/ocr_worker.py' 2>/dev/null)"
if [[ -n "$committed_changes" ]]; then
    echo "❌ FAIL [committed]: PDF-side files modified in commits since ${REF}:"
    echo "$committed_changes"
    git diff "${REF}..HEAD" -- 'secureredact/ocr/' 'secureredact/workers/ocr_worker.py' | head -30
    echo ""
    violations=$((violations + 1))
fi

# 2b) staged (--cached): 已 git add 但未 commit
staged_changes="$(git diff --name-only --cached -- 'secureredact/ocr/' 'secureredact/workers/ocr_worker.py' 2>/dev/null)"
if [[ -n "$staged_changes" ]]; then
    echo "❌ FAIL [staged]: PDF-side files staged for commit:"
    echo "$staged_changes"
    git diff --cached -- 'secureredact/ocr/' 'secureredact/workers/ocr_worker.py' | head -30
    echo ""
    violations=$((violations + 1))
fi

# 2c) working tree (unstaged): 已修改但未 git add
unstaged_changes="$(git diff --name-only -- 'secureredact/ocr/' 'secureredact/workers/ocr_worker.py' 2>/dev/null)"
if [[ -n "$unstaged_changes" ]]; then
    echo "❌ FAIL [working tree]: PDF-side files modified but not staged:"
    echo "$unstaged_changes"
    git diff -- 'secureredact/ocr/' 'secureredact/workers/ocr_worker.py' | head -30
    echo ""
    violations=$((violations + 1))
fi

# 3) 额外扫描：隐私目录中任何新增 / 重命名 / 删除的 PDF 端文件
new_paths="$(git diff --name-status "${REF}..HEAD" -- 'secureredact/ocr/' 'secureredact/workers/ocr_worker.py' 2>/dev/null | grep -E '^A|^D|^R' || true)"
if [[ -n "$new_paths" ]]; then
    echo "❌ FAIL: new/renamed/deleted files in PDF-guarded paths since ${REF}:"
    echo "$new_paths"
    echo ""
    violations=$((violations + 1))
fi

# 4) OCRWorker.page_result_signal payload 字段层面的轻量校验（committed + staged）
payload_changes="$( ( git diff "${REF}..HEAD" -- 'secureredact/workers/ocr_worker.py'; git diff --cached -- 'secureredact/workers/ocr_worker.py' ) 2>/dev/null | grep -E '^[+-].*page_result_signal' || true)"
if [[ -n "$payload_changes" ]]; then
    echo "❌ FAIL: OCRWorker.page_result_signal payload signature changed:"
    echo "$payload_changes"
    echo ""
    violations=$((violations + 1))
fi

if [[ $violations -eq 0 ]]; then
    echo "✅ PASS: PDF baseline intact since ${REF}"
    echo "   (verified: text_pdf.py / mixed_pdf.py / ocr_worker.py unchanged)"
    exit 0
else
    echo "❌ CONST-01 VIOLATION: $violations PDF-side file(s) modified"
    echo "   → revert all PDF-side changes"
    echo "   → if a change is unavoidable, update PDF_BASELINE_TAG in this script and re-tag"
    exit 1
fi