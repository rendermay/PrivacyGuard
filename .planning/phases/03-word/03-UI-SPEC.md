---
phase: 3
slug: word
status: draft
shadcn_initialized: false
preset: none
created: 2026-08-12
---

# Phase 3 — UI Design Contract

> Visual and interaction contract for Phase 3: Word 文档接入识别引擎（双栏对比预览自动高亮）.
> Tech stack: PyQt6 6.10.2 desktop app with `QWebEngineView` HTML preview panels. No shadcn / no web. Theme tokens live in `theme.py`. New this phase: **HTML-only** mark / tag injection inside the existing preview web views. **No new PyQt6 widget classes** for highlight rendering; the heavy lifting is HTML inside the existing left / right panels.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | PyQt6 (QWidget / QPainter / QSS) — shadcn not applicable |
| Preset | not applicable |
| Component library | PyQt6 standard widgets + `theme.py` QSS palette; new this phase is HTML-only (`<mark>` / `<span>`) injected into existing `QWebEngineView` panels |
| Icon library | Existing `assets/branding/v38/*.svg` (load via `QIcon`); no new icon files this phase |
| Font | `theme.py:Theme.FONT_FAMILY` for all PyQt widgets. Web view: inherited from existing preview CSS (renders DOCX font-fallback chain via `mammoth`) |
| Source of truth | `theme.py` (LIGHT/DARK dicts) for PyQt widgets; existing preview CSS / inline `<style>` block for the web views. **Phase 3 must NOT introduce a parallel palette** |

Note on architecture: the Word preview surface is HTML inside a `QWebEngineView`, not a `QWidget` canvas. cp27 incremental DOM patch (locked) drives HTML updates via `web_view.page().runJavaScript("updateBlock(...)")` — not via Qt repaint. PII highlight rendering therefore is an HTML problem (D-20 / D-21), not a `QPainter` problem (Phase 1 PII rect drawing).

---

## Spacing Scale

Reuse `theme.py` spacing constants for any new PyQt widget (only `WordCandidateDialog` is introduced this phase). HTML inside the preview panels uses arbitrary inline values; the values below apply to PyQt widgets only.

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tight icon gaps, line paddings inside chips |
| sm | 8px | `theme.SPACING_SMALL` — compact element spacing inside cards / dialog rows |
| md | 14px ⚠ Phase 1 inherited | `theme.SPACING_MEDIUM` — default element spacing inside `WordCandidateDialog` |
| lg | 22px ⚠ Phase 1 inherited | `theme.SPACING_LARGE` — dialog outer margins, section padding |
| xl | 32px | Dialog outer margins (rare this phase) |
| BORDER_RADIUS | 12px | `theme.BORDER_RADIUS` — `WordCandidateDialog` outer frame, card frames |
| BUTTON_RADIUS | 10px ⚠ Phase 1 inherited | `theme.BUTTON_RADIUS` — dialog buttons, chips |

Exceptions:
- `md (14px)`, `lg (22px)`, `BUTTON_RADIUS (10px)` are inherited from Phase 1 `theme.py` and are out of Phase 3 grid-alignment scope; modifying them would regress every existing dialog. Phase 3 contracts them as constants of the visual system. `theme.py` MUST NOT be modified to "normalize" these to a multiple of 4.
- `WordCandidateDialog` toolbar (entity_type + source filter row): `QHBoxLayout` spacing 8 (matches Phase 1 confirmation dialog toolbar).
- HTML `pii-tag` badge inside left preview: margin 0 4px (4px horizontal buffer around the inline badge); this is HTML-only, not in PyQt token.

---

## Typography

Reuse `theme.py` font sizes — Phase 3 introduces NO new PyQt font sizes. HTML inside the web views uses arbitrary inline values (inherited from existing preview CSS); the `pii-tag` short-code badge uses HTML-relative sizing that maps to the existing panel font.

| Role | Size | Weight | Line Height | Source |
|------|------|--------|-------------|--------|
| Body / list item / dialog body | 14px (`FONT_SIZE_NORMAL`) | Regular (400) | 1.5 | `theme.py` |
| Label / chip / table row | 12px (`FONT_SIZE_SMALL`) | Regular (400) | 1.4 | `theme.py` |
| Heading / dialog title | 18px (`FONT_SIZE_LARGE`) | Semibold (600) | 1.3 | `theme.py` |
| HTML `<mark class="pii-tag">` (short code) | 11px | Semibold (600) | 1.0 | inline `<style>` injected alongside Phase 3 patch script |

Weight scope: only `Regular (400)` and `Semibold (600)` are used (D-21 / `mark.pii-tag` is 600 for legibility at small size — same weight as dialog title). Do NOT introduce `Bold (700)`.

HTML-specific typography rules:
- `<mark class="pii-highlight">` inherits surrounding paragraph font + weight; no font override (preserves DOCX round-trip visual).
- `<mark class="pii-tag">` is Semibold 11px regardless of surrounding weight, so the short code reads consistently across mixed-weight paragraphs.

---

## Color

All PyQt colors come from `theme.py` (`Theme.LIGHT` / `Theme.DARK`). New HTML tokens for the web view reuse the same hex values from `theme.py` (no new hex tokens introduced). The `Theme.LIGHT` / `Theme.DARK` dicts are the single source for both PyQt widgets and HTML rendering.

| Role | Light hex | Dark hex | Usage |
|------|-----------|----------|-------|
| Dominant (60%) | `#FFFFFF` (surface) / `#F7F8FA` (background) | `#1E2836` / `#151C26` | Main window, dialog backgrounds, web view base background |
| Secondary (30%) | `#F9FBFD` (info_bar) / `#F6F8FB` (scroll_area) | `#1E2A3B` / `#1A2330` | Side panels, info bar, scrolled areas, web view cards |
| Accent (10%) | `#0F6CBD` (primary) | `#56A8FF` | Reserved for: `WordCandidateDialog` primary CTA `查看已选 N 项`; status chip "Word 隐私识别 已启用"; preview link / nav highlights (existing rule) |
| **REUSED: PII highlight** (Phase 1 color, no new token) | `#D64545` (danger, light) | `#FF6B6B` (danger, dark) | Reserved EXCLUSIVELY for: HTML `<mark class="pii-highlight">` left pane PII mark fill + stroke; HTML `<span class="pii-tag">` background; status chip "Word 隐私识别 已停用" OFF state |
| **REUSED: PII partial-mask accent** (Phase 2 partial-mask palette, no new token) | `#0FA968` (accent) at `@alpha 0.12` | `#34D399` (accent) at `@alpha 0.18` | Reserved EXCLUSIVELY for: HTML `<mark class="pii-mask">` right pane replacement cell tint. Distinct color from the left-pane red so the user can visually separate "sensitive hit" vs "masked result" |
| Destructive | `#D64545` (danger) | `#FF6B6B` | Reserved for: "移除忽略的白名单" button (deferred to Phase 7, but contract reserves the slot). NOT used by any Phase 3 button — `WordCandidateDialog` `清空当前选择` is rendered as `outline #5F6B7A border (secondary), text_secondary text` per `## Visuals §CTA color tokens`. |
| Success | `#0FA968` | `#34D399` | `WordCandidateDialog` "确认选中的 N 项" accept button; status chip "Word 已识别 N 项敏感内容" |

Reserved-for lists (explicit, never "all interactive elements"):

1. **Accent (#0F6CBD / #56A8FF) is reserved for:**
   - `WordCandidateDialog` primary CTA `确认选中的 N 项` (filled button)
   - Status bar chip `Word 隐私识别 已启用` (foreground only)
   - Preview pane interactive link styling (existing rule reused)

2. **PII highlight (#D64545 / #FF6B6B) is reserved EXCLUSIVELY for:**
   - HTML `<mark class="pii-highlight">` inside left preview pane (PII hit rectangle + light alpha fill at 0.18 / 0.22)
   - HTML `<span class="pii-tag">` background (entity_type short-code badge)
   - Status bar chip `Word 隐私识别 已停用` (OFF state)
   - `WordCandidateDialog` destructive-style row border (PII rows that overlap with selected-only)
   - **NOT** settings toggles, **NOT** primary CTA buttons

3. **PII partial-mask accent (#0FA968@alpha / #34D399@alpha) is reserved EXCLUSIVELY for:**
   - HTML `<mark class="pii-mask">` inside right preview pane (replacement cell tint)
   - This is a NEW color role that maps to the existing `Theme.accent` slot — no new hex token

Color reuse rule: `#0F6CBD` (primary) MUST NOT appear on a PII `<mark>` (left or right). `#D64545` (danger) MUST NOT appear on a settings toggle. The left-pane red and the right-pane green-tint MUST be visually distinct at 720p — that is the visual differentiator between "raw PII hit" and "masked result in this pane".

---

## Copywriting Contract

All copy is Simplified Chinese (zh-CN), matching `main.py` convention (CLAUDE.md). Tone rules are locked: address user as 您 in tooltips / dialogs; status chips use noun phrases, not imperative verbs; copy NEVER includes `*` / `#` placeholder text outside of code-block demos.

| Element | Copy |
|---------|------|
| Status chip ON | `Word 隐私识别 已启用` (primary color foreground) |
| Status chip OFF | `Word 隐私识别 已停用` (danger color foreground on secondary background) |
| Status chip scanning (text layer) | `扫描 Word 文本层（第 X / Y 段）…` |
| Status chip scanning (table cells) | `扫描 Word 表格（第 X / Y 张）…` |
| Status chip scanning (extracting) | `正在抽出 Word 段落文本…` |
| Status chip scanning (done with N > 0) | `已识别 N 项敏感内容` (success color foreground) |
| Status chip scanning (done with N == 0) | `扫描完成：未发现敏感内容` (text_secondary) |
| Status chip error | `Word 隐私识别 引擎初始化失败：{exception_class}。已自动关闭本会话识别。` (danger color foreground) |
| HTML entity_type short codes (left pane `pii-tag`) | `ID` / `PHONE` / `BANK` / `EMAIL` / `USCC` / `TAX` / `TAX15` / `VAT` / `ACCT` (9 codes, ASCII uppercase, fixed) |
| HTML entity_type full labels (right pane `title` attr) | `身份证号` / `手机号` / `银行卡号` / `电子邮箱` / `统一社会信用代码` / `纳税人识别号（18 位）` / `纳税人识别号（15 位）` / `增值税发票号` / `银行账号` |
| Partial-mask sample string shown in tooltips | `身份证 110101********1234` / `手机 138****5678` / `银行卡 6222 **** **** 1234` / `邮箱 z****@qq.com` (fixed sample, max 25 chars total) |
| `WordCandidateDialog` window title | `Word 候选审阅` |
| `WordCandidateDialog` toolbar label 1 | `实体类型：` |
| `WordCandidateDialog` toolbar label 2 | `来源：` |
| `WordCandidateDialog` filter dropdown "全部类型" option | `全部类型` (default selected) |
| `WordCandidateDialog` filter dropdown per-type row | `身份证号`, `手机号`, `银行卡号`, `电子邮箱`, `统一社会信用代码`, `纳税人识别号（18 位）`, `纳税人识别号（15 位）`, `增值税发票号`, `银行账号` |
| `WordCandidateDialog` source filter "全部来源" option | `全部来源` (default selected) |
| `WordCandidateDialog` source filter rows | `自动识别 (pii)`, `手动框选 (manual)`, `OCR 识别 (ocr)` |
| `WordCandidateDialog` empty state | `当前 Word 文档未发现敏感内容。可继续在左栏手动框选或在右栏调整替换规则。` |
| `WordCandidateDialog` empty state CTA | `关闭` |
| `WordCandidateDialog` row format | `[source] entity_type全称  ·  normalized[:30]…  @ key` (single-line; max-line ~80 chars, ellipsis if longer) |
| `WordCandidateDialog` row checkbox default | all rows CHECKED |
| `WordCandidateDialog` row selection chip (when unchecked) | `已忽略` (text_secondary color, italic, max 4 chars) |
| `WordCandidateDialog` primary CTA | `确认选中的 N 项` |
| `WordCandidateDialog` secondary CTA | `全选当前页` |
| `WordCandidateDialog` tertiary CTA | `清空当前选择` |
| `WordCandidateDialog` close CTA | `关闭` |
| `WordCandidateDialog` pagination label | `第 M / N 页（共 X 条）` |
| `WordCandidateDialog` prev / next button text | `上一页` / `下一页` |
| `WordCandidateDialog` state (filter Yields 0) | `当前筛选下无候选。请放宽实体类型或来源筛选。` |
| Error: Word PII worker failure | `Word 隐私识别 扫描失败：{exception_class}。其他功能仍可正常使用；可在设置中关闭 Word 隐私识别。` |
| Error: Document property clear failure | `文档已成功脱敏，但 Word 文档属性清除未完全生效（{exception_class}）。请在 Word 中手动清除属性。` |
| Toast: Word PII auto-trigger on file open | `已自动识别 {N} 项敏感内容。可在候选审阅中逐条确认。` (info bar message, NOT a modal dialog; shown only when `require_confirmation=true`) |
| Tooltip on left-pane `pii-highlight` mark | `{entity_type全称} · {mask_sample_for_this_hit}` |
| Tooltip on right-pane `pii-mask` mark | `已替换为：{mask_strategy literal}` |

Numeric rule: plural `N 项` / `M 页` / `X 条` are spelled as Arabic numerals + Measure word 项 / 页 / 条. (Consistent with Phase 1 copywriting.)

---

## New Components Introduced

Phase 3 introduces exactly these UI surfaces / interactions. No other widgets, no new dialogs, no new top-level structures.

| Component | Type | Role |
|-----------|------|------|
| HTML `<mark class="pii-highlight">` | HTML fragment inside existing `word_preview` (left pane) QWebEngineView | Renders red rect + light-alpha fill + inline `<span class="pii-tag">` short-code badge over each PII hit. Injected via `web_view.page().runJavaScript("updateBlock(...)")` (cp27 incremental patch, D-10). |
| HTML `<mark class="pii-mask">` | HTML fragment inside existing `word_preview_replaced` (right pane) QWebEngineView | Renders partial-mask strings (e.g. `110101********1234`) with green-tint background. Injected via the same cp27 patch path. |
| `WordCandidateDialog` | `QDialog` (modal, `Qt.WindowModality.ApplicationModal`) | Phase 7 minimal version: lists `word_data[*]["pii"|"ocr"|"manual"]` hits with per-row checkbox, entity_type filter dropdown, source filter dropdown, 50-entries pagination, primary/secondary/tertiary/close CTA. |
| Status bar `wordPiiStatusChip` | `QLabel` (object name `wordPiiStatusChip`) embedded into existing `info_bar` | Surfaces 7 chip states per Copywriting rows; left-aligned within info_bar, separated from existing OCR / PDF PII chip by 12px gap. |
| `WordPIIWorker` (QThread) | `QThread` subclass (`privacyguard/word/worker.py`) | Auto-fires on `_open_word_docx` completion (D-09). Iterates `word_data` items, calls `PIIEngine.detect(TextUnit(page_index=key_index, text=..., source="text"))`, emits `pii_signal(key, [asdict(h) for h in hits])`. **Not a UI surface** but it owns the user-visible scan completion timing (status chip transitions). |
| Page-data carrier | Existing `word_data[key]["pii"]` key holding `List[PIIHit]` | New dataclass payload, no new top-level structure. Carries 9 entity types (CN_ID_CARD / CN_PHONE / CN_BANK_CARD / CN_EMAIL / CN_USCC / CN_TAXPAYER_ID / CN_TAXPAYER_ID_15 / CN_VAT_INVOICE / CN_BANK_ACCOUNT). |
| Document property clearance (no UI) | `privacyguard/word/clear_doc_props.py::clear_word_doc_props` | Called inside existing `_save_word` BEFORE `new_doc.save(fname)`. No user-visible surface; verification is docx round-trip (`doc.core_properties.title == ""`). FMT-02 / SAFE-03. |

No new icons this phase. No new SVG / PNG / QSS palette file. No new string-resource file. `WordCandidateDialog` reuses the existing dialog QSS (`_apply_dialog_theme` already exists on `SettingsDialog` from Phase 1).

---

## Visuals

### PII Highlight (Left Preview Pane) — `<mark class="pii-highlight">`

Locked HTML tokens (no other values allowed). Hex values are taken directly from `theme.py` LIGHT / DARK; the renderer picks the right pair based on the active theme by reading `theme.get_theme()` at patch-script build time:

| Property | Light | Dark |
|----------|-------|------|
| Mark background | `#D64545` @ alpha `0.18` | `#FF6B6B` @ alpha `0.22` |
| Mark outline (bottom-border, simulates underline) | `#D64545` solid, `2px` | `#FF6B6B` solid, `2px` |
| `pii-tag` short-code badge background | `#D64545` solid | `#FF6B6B` solid |
| `pii-tag` short-code badge foreground | `#FFFFFF` | `#151C26` |
| `pii-tag` short-code badge font | 11px / Semibold 600 / `'Microsoft YaHei UI', sans-serif` | same |
| `pii-tag` short-code badge padding | `0 4px` | same |
| `pii-tag` short-code badge border-radius | `4px` | same |
| `pii-tag` short-code badge letter-spacing | `0.5px` | same |
| Cursor over `<mark>` | `help` (shows full `title` tooltip) | same |

HTML pattern around each PII hit (single-line illustration; the patch script constructs this string in Python):

```html
<mark class="pii-highlight" data-entity-type="CN_ID_CARD" title="身份证号 · 110101********1234">
  <span class="pii-tag">ID</span>110101199003078811
</mark>
```

Where the surrounding text continues unbroken (cursor injects `offset += hit.page_length`). The badge appears immediately before the PII substring (left-anchored inline), so the user reads "marked section first, then entity type, then the original PII text". This is distinct from Phase 1 `SinglePageCanvas.paintEvent` where the badge is anchored outside the rect — Phase 3 HTML pattern uses inline inline-block to avoid layout overlap with adjacent `<mark>` hits.

Hit-test parity: PII `<mark>` elements are read-only this phase. `word_preview` `page().runJavaScript` actions must NOT inject `editable` or `onclick` to PII `<mark>` elements. Code comment in worker / patch-script: `# Phase 3: PII <mark> elements are read-only on preview; ignore handled by Phase 7 review UI`.

### PII Partial-Mask (Right Preview Pane) — `<mark class="pii-mask">`

Locked HTML tokens. Reuse `Theme.accent` (success / partial-mask palette) — distinct from left-pane red so user can visually separate "sensitive hit" from "masked result in this pane".

| Property | Light | Dark |
|----------|-------|------|
| Mark background | `#0FA968` @ alpha `0.12` | `#34D399` @ alpha `0.18` |
| Mark foreground | `#18212F` (text) | `#F6F8FC` (text) |
| Mark outline | none (transparent) | none |
| Mark padding | `0 2px` | same |
| Mark border-radius | `4px` | same |
| Mark font | inherits from surrounding paragraph | same |
| Cursor over `<mark>` | `help` (shows `title` tooltip = `mask_strategy` literal) | same |

HTML pattern around each masked replacement (right pane patch script):

```html
<mark class="pii-mask" data-entity-type="CN_ID_CARD" title="已替换为：110101********1234">
  110101********1234
</mark>
```

Important: the right pane shows the **mask string** literally (e.g. `110101********1234`), not the original PII. The mark wraps the mask string only — never the original. Reusing Phase 2 `mask_for_entity(entity_type, normalized)` produces the partial-mask text.

### cp27 Incremental DOM Patch Script Contract

The patch runs `web_view.page().runJavaScript("updateBlock(...)")` (D-10 / cp27). No whole-page `setHtml()` is permitted for the PII path.

Locked patch invocation shape:

```python
# Pseudocode — actual implementation lives in privacyguard/word/worker.py + main.py:_apply_word_pii_panel_updates
def _apply_word_pii_panel_updates(self, key: str, hits: list):
    if not hits:
        return
    block_updates = {key: self._build_pii_block_fragment(key, hits)}  # left pane HTML
    replaced_updates = {key: self._build_pii_mask_block_fragment(key, hits)}  # right pane HTML
    for view_attr, updates in (("word_preview", block_updates), ("word_preview_replaced", replaced_updates)):
        view = getattr(self, view_attr, None)
        if view and not view.isHidden():
            script = build_word_panel_update_script(updates)  # cp27 existing helper (main.py:471)
            view.page().runJavaScript(script)
```

This contract MUST hold for both panes — left highlight and right mask — and MUST NOT trigger `setHtml()` on either `word_preview` or `word_preview_replaced`.

### `WordCandidateDialog` Layout

Lives in `privacyguard/word/candidate_dialog.py::WordCandidateDialog`. Reuses existing `SettingsDialog` QSS via `_apply_dialog_theme(parent)` (already exists in `main.py`). Dimensions: `min-width=680px`, `min-height=520px`, `max-width=900px`, `max-height=640px`. Centered on parent.

```
┌─ Word 候选审阅 ───────────────────────────────────────────────┐
│                                                              │
│ [spacing 14]                                                  │
│ [实体类型: ▾ 全部类型 ]    [来源: ▾ 全部来源 ]      [N 项已选] │
│                                                              │
│ [spacing 8]                                                   │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ [✓] [pii] 身份证号  ·  110101********1234…  @ paragraph_3 │   │
│ │ [✓] [pii] 手机号    ·  138****5678…         @ paragraph_3 │   │
│ │ [✓] [manual] 银行卡  ·  …                    @ table_0_…  │   │
│ │ [ ] [ocr]    身份证号  ·  (已忽略)            @ paragraph_5 │   │
│ │ ...                                                      │   │
│ └────────────────────────────────────────────────────────┘   │
│   QListWidget, vertical only (no scroll bar style override)   │
│                                                              │
│ [spacing 8]                                                   │
│  ◀ 上一页    第 1 / 3 页（共 113 条）    下一页 ▶              │
│                                                              │
│ [spacing 14]                                                  │
│                       [全选当前页]  [清空当前选择]  [关闭]    │
│                                    [确认选中的 N 项] (primary) │
└──────────────────────────────────────────────────────────────┘
```

- Filter row (top toolbar): `QHBoxLayout` spacing 14; left-aligned; `[N 项已选]` label uses text_secondary color, updated reactively when checkboxes toggle.
- List region: `QListWidget` (not `QListView` — D-25 specified `QListView` but we lock `QListWidget` here because items need per-row `QCheckBox` + 3 labels packed horizontally; `QListWidget` plus a custom item delegate achieves this in <100 LOC vs `QListView` + model + delegate ~300 LOC; locked for Phase 3 minimalism).
- Each row: `QCheckBox` (default checked) + `[source]` chip + `entity_type` full label + `·` + `normalized[:30]…` + `@ key`
- Source chip: 3-letter ASCII tag (`pii` / `manual` / `ocr`) in 11px Monospace-or-system-mono style; color: `pii` = danger, `manual` = primary, `ocr` = warning. Bounded to 3 letters each.
- Pagination row: `QHBoxLayout` spacing 14; prev / page label / next right-aligned with `addStretch(1)` between page label and next.
- CTA row: `QHBoxLayout` spacing 8; CTAs right-aligned; primary CTA `确认选中的 N 项` is filled accent button; secondary / tertiary / close are outlined buttons.
- All CTAs: `min-height=32px`, `min-width=88px`, font `14px / Regular`

CTA color tokens (per Color §reserved-for):
- Primary `确认选中的 N 项`: filled `#0F6CBD` / white text
- Secondary `全选当前页`: outline `#0F6CBD` border, primary text
- Tertiary `清空当前选择`: outline `#5F6B7A` border (secondary), text_secondary text
- Close `关闭`: text-only, text_secondary color, hover `hover` background

### Status Bar `wordPiiStatusChip`

Single inline `QLabel` in the existing `info_bar`. Object name `wordPiiStatusChip`. Position: left-aligned within info_bar, separated from existing OCR + Phase 1 `piiStatusChip` by a fixed 12px gap (`QHBoxLayout` spacing). Two chips (Phase 1 PDF + Phase 3 Word) coexist — `piiStatusChip` for PDF, `wordPiiStatusChip` for Word.

Chip rendering (depending on state):

| State | Foreground | Background | Text |
|-------|-----------|-----------|------|
| engine OFF | danger color | info_bar (default) | `Word 隐私识别 已停用` |
| scanning (extracting) | text_secondary | info_bar (default) | `正在抽出 Word 段落文本…` |
| scanning (text layer) | text_secondary | info_bar (default) | `扫描 Word 文本层（第 X / Y 段）…` |
| scanning (tables) | text_secondary | info_bar (default) | `扫描 Word 表格（第 X / Y 张）…` |
| done with N > 0 | success color | info_bar (default) | `已识别 N 项敏感内容` |
| done with N == 0 | text_secondary | info_bar (default) | `扫描完成：未发现敏感内容` |
| error | danger color | info_bar (default) | `Word 隐私识别 引擎初始化失败：{…}。已自动关闭本会话识别。` (truncated to info_bar width) |
| engine ON, idle (no Word open) | (chip hidden) | — | — (`setVisible(False)`) |

Chip has no background fill, no border, no margin — it is plain colored text inside info_bar. No chip "pill" frame is drawn this phase. (Status chips with pill chrome are deferred to Phase 7.)

### Document Property Clearance (no UI)

`privacyguard/word/clear_doc_props.py::clear_word_doc_props(doc)` clears per D-08:

| Field | python-docx API | Cleared value |
|-------|-----------------|---------------|
| `dc:title` | `doc.core_properties.title` | `""` (empty string) |
| `dc:creator` | `doc.core_properties.author` | `""` |
| `dc:subject` | `doc.core_properties.subject` | `""` |
| `cp:keywords` | `doc.core_properties.keywords` | `""` |
| `cp:lastModifiedBy` | `doc.core_properties.last_modified_by` | `""` |
| `cp:revision` | `doc.core_properties.revision` | `1` (integer, NOT empty string) |
| `app:Company` | `doc.app_properties.company` (if available) | `""` |
| `app:Manager` | `doc.app_properties.manager` (if available) | `""` |

Locked-in: `core_properties.revision` MUST be set to `1` (integer), NOT `""`. Setting it to empty string raises `ValueError` (python-docx expects int). All other core string fields MUST be set to `""` (NOT `None` / NOT `"Anonymous"` / NOT `"Redacted"`). `app_properties` may not exist on older python-docx versions; use `hasattr` guard.

Visual outcome for the user: **none — invisible**. The user does not see the document properties dialog after save. Verification is a separate docx round-trip test (`test_clear_word_doc_props` in `tests/unit/test_word_pii_pipeline.py`) reading back the 8 fields and asserting empty.

---

## Interaction Contract

| Trigger | Surface | Behavior |
|---------|---------|----------|
| User opens a `.docx` via Open menu / drag-drop / batch | `MainWindow.open_word` / drag-and-drop handler → `_open_word_docx` → `WordPIIWorker.start()` | Existing `_open_word_docx` initializes `word_data[key]`. After initialization completes, `WordPIIWorker` auto-fires (D-09). Status chip `wordPiiStatusChip` transitions through extract → text-layer → tables → done. **User does NOT need to click a scan button.** |
| `WordPIIWorker` emits `pii_signal(key, hits)` | `MainWindow._on_word_pii_page_result(key, hits)` (NEW slot, D-18) | Inside `QMutexLocker(self._word_data_lock)`: `self.word_data[key]["pii"] = hits` (or merge per `merge_pii_hits` helper). Then call `_apply_word_pii_panel_updates(key, hits)` which runs the cp27 incremental patch script. **No thread without lock.** |
| Worker completion (`finished_signal`) | `MainWindow._on_word_pii_scan_complete()` (NEW slot) | If `require_confirmation=true` AND N > 0 → open `WordCandidateDialog` modally. Else → status chip → success / no-content state. |
| User clicks cell in left preview pane | `QWebEngineView` link-clicked handler (existing) | Existing navigation behavior; PII `<mark>` elements are NOT interactive (no `onclick`, no `cursor:pointer`). |
| User hovers `<mark class="pii-highlight">` | HTML `title` attribute (browser native) | Tooltip shows `{entity_type全称} · {mask_sample_for_this_hit}` (Copywriting row). |
| User hovers `<mark class="pii-mask">` | HTML `title` attribute (browser native) | Tooltip shows `已替换为：{mask_strategy literal}` (Copywriting row). |
| User clicks "查看全部候选" toolbar button (NEW) | `WordCandidateDialog.exec()` | Opens dialog modally over the main window. List is populated from `word_data` (all PII + ocr + manual hits across all `word_data` keys). |
| User changes entity_type dropdown in dialog | `QComboBox.currentIndexChanged` | Recompute filtered list (single-pass over `_all_hits`); clamp `_page`; re-render `QListWidget`. |
| User changes source dropdown in dialog | `QComboBox.currentIndexChanged` | Same as above (filter is AND-combined with entity_type). |
| User toggles per-row checkbox | `QCheckBox.stateChanged` | Update `[N 项已选]` label text reactively; PRIMARY CTA text `确认选中的 N 项` updates to the new count. |
| User clicks "上一页" / "下一页" | `QPushButton.clicked` | Decrement / increment `_page`; re-render. Buttons enable / disable based on bounds. |
| User clicks primary CTA `确认选中的 N 项` | Dialog `accept()` | The set of CONFIRMED hits is passed back to caller; `WordCandidateDialog.accepted.connect(_apply_confirmed_hits)` writes those into `word_data[key]["confirmed"]` (NEW key) OR merges into `word_data[key]["pii"]` after stripping un-confirmed entries. Then `dialog.accept()` closes. |
| User clicks "全选当前页" | `QPushButton.clicked` | Check every checkbox on the current page; update `[N 项已选]` label. |
| User clicks "清空当前选择" | `QPushButton.clicked` | Uncheck every checkbox on the current page; primary CTA label → `确认选中的 0 项` (greyed out / disabled). |
| User clicks "关闭" | Dialog `reject()` | No hits are confirmed; existing `word_data[key]["pii"]` is preserved unchanged. Save loop continues per D-19 priority (`rule > pii > manual > ocr`). |
| User saves Word (Ctrl+S / menu) | `MainWindow._save_word` | Existing save loop now calls `redact_word(new_doc, key, merged_matches)` for each `word_data` key, where `merged_matches = merge_word_matches_with_priority(..., manual_matches=..., ocr_matches=..., pii_matches=...)`. After all redactions, `clear_word_doc_props(new_doc)` runs BEFORE `new_doc.save(fname)`. |
| User enables / disables PII engine for Word | Existing SettingsDialog PII toggle | Setting already gates Phase 1 PDF; Phase 3 extends the read-only label `扫描范围（只读）：身份证号 / 手机号 / 银行卡号 / 邮箱 / 统一社会信用代码 / 纳税人识别号 / 增值税发票号 / 银行账号` (9 实体 entries separated by ` / `, locked list, max ~120 chars). |
| User clicks panel-toggle / switch from Word to PDF | Existing tabs | `wordPiiStatusChip` hides when no Word file is open; `piiStatusChip` resumes control. |

No loading skeleton this phase — `wordPiiStatusChip` text + existing `QProgressBar` already cover progress.

---

## State Coverage

| State | Surface | Behavior |
|-------|---------|----------|
| Engine OFF (initial) | `wordPiiStatusChip` | `Word 隐私识别 已停用` text only, danger foreground |
| Engine ON, idle (no Word open) | `wordPiiStatusChip` | Empty (no chip text); chip widget hidden via `setVisible(False)` |
| Engine ON, Word open, extracting | `wordPiiStatusChip` + progress | Chip `正在抽出 Word 段落文本…`; progress 0% → 25% |
| Engine ON, Word open, scanning text layer | `wordPiiStatusChip` + progress | Chip `扫描 Word 文本层（第 X / Y 段）…`; progress 25% → 75% |
| Engine ON, Word open, scanning tables | `wordPiiStatusChip` + progress | Chip `扫描 Word 表格（第 X / Y 张）…`; progress 75% → 99% |
| Engine ON, Word open, no candidates | `wordPiiStatusChip` + progress | Progress 100%; chip `扫描完成：未发现敏感内容` (text_secondary) |
| Engine ON, Word open, candidates present, no confirmation | `wordPiiStatusChip` + progress | Progress 100%; chip `已识别 N 项敏感内容` (success) |
| Engine ON, Word open, candidates present, confirmation ON | `wordPiiStatusChip` + dialog | Chip during scan; `WordCandidateDialog` blocks save until resolved (Phase 3 minimal: even non-confirmed candidates remain in `word_data[key]["pii"]` and proceed to save loop) |
| Engine ON, Word open, scan cancelled mid-way | `wordPiiStatusChip` + progress | Status chip → `⏹️ Word 扫描已取消` (warning color, replaces in-flight stage copy) |
| Word open failure during PII init | `wordPiiStatusChip` + info bar | Chip text per Error Copywriting row; engine self-disables for current session |
| SettingsDialog open with engine toggled OFF | Toggle visual | Existing Phase 1 toggle (`启用隐私识别引擎`) — Phase 3 extends by extending the read-only `扫描范围` label to 9 entity types; toggle visual unchanged |
| `WordCandidateDialog` open with filter yielding 0 rows | Dialog | Centered empty state per Copywriting row; list region cleared; pagination hidden; CTAs `全选当前页` and `确认选中的 0 项` disabled |
| `WordCandidateDialog` open with N rows | Dialog | List populated; pagination shown; CTAs enabled |
| `WordCandidateDialog` row unchecked | Row + filter label | `[N 项已选]` label decrements; primary CTA `确认选中的 N 项` count updates; row label gains trailing `已忽略` chip |
| Save loop with empty `merged_matches` | `_save_word` | `redact_word` short-circuits (D-23); `clear_word_doc_props` still runs |
| Document property clear failure (read-only disk) | `_save_word` | Exception surfaced via existing try/except in `_save_word`; user-facing toast per Error Copywriting row; save loop continues with the original (unchanged) docx — save is NOT silently dropped |

No new top-level UI state for Phase 3. `wordPiiStatusChip` reuses Phase 1's chip pattern; `WordCandidateDialog` mirrors Phase 1's confirmation dialog pattern.

---

## UI Considerations

> Probed post-verification by ui-consideration-probe (Step 9.5 of /gsd-ui-phase).
> Shape-rooted UI **state** coverage for the Phase 3 surfaces. Empty-state and error-state
> **COPY** lives in `## Copywriting Contract` above — this section covers state coverage and
> REFERENCES those rows rather than restating the copy (de-dup).

**Applicable state considerations resolved (probed by ui-consideration-probe Step 9.5, post-verification):** 24 covered · 3 backstop · 0 unresolved — 24 truths lift into `must_haves.truths` as plain strings, 3 backstop statements lift as flat scalars `{ statement, verification: backstop }`, 0 unresolved (no planner assumptions required).

### E1 — `<mark class="pii-highlight">` in left `word_preview`

| Category | Status | Resolution / Reason |
|----------|--------|---------------------|
| empty | ✅ covered | When `hits == []`, `_apply_word_pii_panel_updates` returns early; no `<mark>` injected; left pane shows plain paragraph text. Status chip → `扫描完成：未发现敏感内容`. |
| loading | ✅ covered | During the brief window between `_open_word_docx` completion and first `WordPIIWorker` emit, left pane shows plain text (no placeholder chrome needed — paragraphs render synchronously after mammoth). Status chip handles the loading copy per `## State Coverage` rows. |
| error | ✅ covered | `WordPIIWorker` exceptions are caught at `run()`; `error_signal` emits to `_on_word_pii_scan_error` slot; status chip → error Copywriting row. No `<mark>` injection happens on error paths. |
| populated | ✅ covered | Each PII hit in `hits` is wrapped by `<mark class="pii-highlight" data-entity-type="..." title="..."><span class="pii-tag">CODE</span>{original}</mark>` per `## Visuals §PII Highlight`. Cursor `help` enables native browser tooltip. |
| partial | ✅ covered | When one of N adjacent hits is masked and another is not, the patch script emits mixed text + mixed mark elements — adjacent hits render independently; CSS does not enforce a max hit density. |
| overflow | 🧪 backstop | A paragraph with 30+ contiguous PII hits renders 30+ inline `<mark>` elements + 30+ inline `<span class="pii-tag">` badges; CSS forces inline-block on badges so they sit on the same line at 720p viewport. Held-out visual test at 720p confirms badge legibility when 8+ consecutive hits appear in a row. { statement: "8+ consecutive PII hits remain visually distinguishable at 720p / 100% DPI", verification: backstop } |
| zero-one-many | ✅ covered | One PII hit = one `<mark>` + one `<span>`; N hits = N × 2 inline elements. No "many" specific UI pattern; the generic WebEngineView scroll handles it. |
| long-text | ✅ covered | DOCX paragraphs occasionally exceed 5,000 chars (synthesized test fixture case `test_pii_in_long_paragraph`); patch script iterates hits by offset; cursor advance is `offset += hit.page_length` so full-paragraph HTML is well-formed. Worst case 100 PII hits in one paragraph → 200 inline elements, no layout overflow. Tooltip on each `<mark>` is bounded to ~30 chars (Copywriting row). |

### E2 — `<mark class="pii-mask">` in right `word_preview_replaced`

| Category | Status | Resolution / Reason |
|----------|--------|---------------------|
| empty | ✅ covered | When `hits == []`, right pane shows plain text (no `<mark class="pii-mask">` injected). Existing replaced-preview rendering already handles the no-hit case. |
| loading | ✅ covered | Right pane renders synchronously after `web_view.setHtml()` during preview load (existing); mask patch is incremental via cp27 — no extra placeholder chrome. |
| error | ✅ covered | If worker errors, right pane retains whatever mask state was last applied; no new error surface on right pane specifically. Left pane's `wordPiiStatusChip` error copy covers it. |
| populated | ✅ covered | Each PII hit in `hits` is replaced by `<mark class="pii-mask" data-entity-type="..." title="...">{mask_strategy}</mark>` per `## Visuals §PII Partial-Mask`. The mark wraps the mask string only (not the original). |
| partial | ✅ covered | When user has both `pii` and `manual` overlapping hits, merge logic (D-19) resolves priority; only the highest-priority mask string is injected per overlap region. |
| overflow | ✅ covered | Right pane uses `#0FA968@alpha 0.12` (light) / `#34D399@alpha 0.18` (dark) which is a deliberate low-contrast tint against the existing `#FFFFFF` / `#1E2836` background; no scrollbar-style overflow even at 50 consecutive marks in one paragraph. |
| zero-one-many | ✅ covered | Mask string length is bounded: longest is `110101********1234` (18 chars per `mask_for_entity`); even 100 consecutive marks = 1,800 chars in one block — well within HTML threshold. |
| long-text | 🧪 backstop | Mask string set is fixed for each entity_type (per `mask_for_entity`); tooltip `已替换为：{mask_strategy literal}` is bounded to max ~25 chars (Copywriting row). Held-out visual test at 720p confirms tooltip does not overflow on dark + light theme. { statement: "Tooltip on `<mark class='pii-mask'>` fits within 720p viewport on both themes", verification: backstop } |

### E3 — `WordCandidateDialog` QDialog

| Category | Status | Resolution / Reason |
|----------|--------|---------------------|
| empty | ✅ covered | When all 3 sources (pii + ocr + manual) yield 0 hits across all `word_data` keys, dialog opens with full-width centered empty state per Copywriting row `WordCandidateDialog empty state`. List region is hidden. CTA `确认选中的 N 项` is disabled (count = 0). |
| loading | ✅ covered | Dialog renders synchronously from already-populated `word_data`; `WordPIIWorker` has emitted by the time the dialog opens; no in-dialog spinner needed. |
| error | ✅ covered | If `word_data` is missing or malformed (defensive case), dialog still opens with the empty state. No in-dialog error path; errors surface via `wordPiiStatusChip` Copywriting row `Error: Word PII worker failure`. |
| populated | ✅ covered | `QListWidget` populated from `_all_hits` with per-row `QCheckBox` + 3 labels per `## Visuals §WordCandidateDialog` layout. Pagination `QListWidget` items render one page at a time (PAGE_SIZE = 50). |
| partial | ✅ covered | When filter combination yields 0 rows but `_all_hits` is non-empty, the dialog shows the documented "当前筛选下无候选" empty state inside the list region (NOT the full-width empty state from the `empty` row above). CTAs `全选当前页` and `确认选中的 N 项` are disabled. |
| overflow | ✅ covered | `QListWidget` is bounded by `min-height=520px / max-height=640px`; if `_all_hits` exceeds `PAGE_SIZE = 50`, pagination row appears with prev / next + page label. Worst-case 5,000 hits = 100 pages. |
| zero-one-many | ✅ covered | Each row is exactly one hit; `[N 项已选]` label plural form (`1 项已选` / `N 项已选`); primary CTA `确认选中的 N 项` plural-spelled. Empty (0) case disabled; 1 case triggers accept on click; many case paginates. |
| long-text | 🧪 backstop | Row `normalized[:30]` truncates with `…` for hits > 30 chars; row label max-line ~80 chars; `key` (e.g. `table_5_cell_12_3`) max 24 chars. Held-out visual test confirms no row clipping at 720p. { statement: "Candidate row labels truncate cleanly at 720p / 100% DPI without row-vertical-overflow", verification: backstop } |

### E4 — `wordPiiStatusChip` in `info_bar`

| Category | Status | Resolution / Reason |
|----------|--------|---------------------|
| overflow | ✅ covered | Chip is plain colored text inside existing `info_bar` `QHBoxLayout`; truncates at parent layout boundary. The error state row is the longest; maximum `Word 隐私识别 引擎初始化失败：FileNotFoundError。已自动关闭本会话识别。` is ~50 chars and well within info_bar width at default DPI; error copy is truncated at 80 chars max by `_apply_status_chip` helper. |
| long-text | ✅ covered | Scan-stage copy bounded by `扫描 Word 文本层（第 X / Y 段）…` format where X/Y are integers; Y ≤ MAX_PARAGRAPH_COUNT (test fixture caps at 500); worst-case `扫描 Word 文本层（第 500 / 500 段）…` is well within info_bar width at default DPI. |

<!-- Status vocabulary (locked by probe-core projectTruths):
     ✅ covered   → a plain truth string lifted into must_haves.truths
     🧪 backstop  → a flat scalar { statement, verification: backstop }; at verify time, no explicit
                    evidence → insufficient_spec → human_needed (never a silent pass, #1154)
     ⚠ unresolved → an explicit planner assumption (surfaced, never silently dropped)
     Rows are REPLACED (not appended) on a probe re-run — idempotent. -->

---

## Constraints Carried From Upstream (do not violate)

1. **Reuse Phase 1 design system.** No new colors, no new fonts, no new spacing tokens. `theme.py` is the single source of truth for PyQt + HTML (D-20).
2. **Reuse Phase 1 PII color.** `#D64545` (light) / `#FF6B6B` (dark) reserved EXCLUSIVELY for PII (D-20); never on settings toggles, never as primary CTA fill.
3. **Reuse Phase 2 partial-mask accent.** `#0FA968@alpha` / `#34D399@alpha` reserved EXCLUSIVELY for `<mark class="pii-mask">`. Distinct from left-pane red.
4. **cp27 incremental DOM patch (D-10).** PII highlight + mask injection MUST go through `web_view.page().runJavaScript("updateBlock(...)")`. NEVER call `web_view.setHtml(...)` for the PII path.
5. **`data-key` injection reuse (D-22).** `_add_data_key_attributes` (existing) + `_add_data_key_regex_fallback` (existing). Phase 3 MUST NOT rewrite them; only validate synchronization.
6. **Lazy-load (OPS-03).** `privacyguard/word/__init__.py` MUST use `__getattr__ + _LAZY_IMPORTS` (D-06); `import privacyguard.word` MUST NOT eagerly pull `python-docx` or `mammoth`.
7. **Convergence (D-05).** New PII / Word adapter / redact / clear-doc-props logic MUST live in `privacyguard/word/`, not in `main.py`. `main.py` is call-site and UI assembly only.
8. **Priority (D-19).** `merge_word_matches_with_priority(text, rules, default_replacement_text, manual_matches=None, ocr_matches=None, pii_matches=None)` — back-compat preserved: 4th/5th/6th params all default to `None`; new `pii_matches` fourth param MUST have a default value (D-19 hardening).
9. **Page rect placeholder (D-16).** `PIIHit.page_rect` for Word hits MUST be `(0, 0, 0, 0)` (placeholder; Word has no fitz.Page coordinates).
10. **Document property range (D-08).** `clear_word_doc_props` MUST clear 5 core strings (`title`/`author`/`subject`/`keywords`/`last_modified_by`) + 1 core int (`revision = 1`) + 2 app strings (`company`/`manager` IF available). MUST NOT clear `CreationDate` / `ModDate` / `Template`. MUST NOT write `"Anonymous"` / `"Redacted"` as filler.
11. **ENTITY_TYPE short-code badge (D-21).** Use the FIXED 9-code set: `ID` / `PHONE` / `BANK` / `EMAIL` / `USCC` / `TAX` / `TAX15` / `VAT` / `ACCT`. No other short codes. Source-of-truth lives in `privacyguard/pii/hits.py` next to `PIIHit`; renderer reads from there, not duplicated.
12. **79/79 baseline preserved (D-13 / D-14).** Phase 3 adds ≥1 new unittest class (`tests/unit/test_word_pii_pipeline.py`). Phase 3 completion lifts the baseline from 79/79 to 88/88 (or higher).
13. **Auto-trigger (D-09).** `_open_word_docx` MUST auto-fire `WordPIIWorker` after word_data initialization. NO manual scan button for Phase 3. (Manual re-scan may be added in Phase 7 review UI.)
14. **Word Candidate Dialog minimal scope (D-25).** Phase 3 implements ONLY: 50-entries pagination + entity_type filter + source filter + per-row checkbox + 4 CTAs (`确认选中的 N 项` / `全选当前页` / `清空当前选择` / `关闭`). Phase 7 entity-type global toggles / document whitelist / undo stack are OUT OF SCOPE.
15. **No new PyPI dependencies (D-12).** `python-docx` + `mammoth` + `bs4` + PyQt6 are the entire stack.
16. **PyInstaller parity (cp30 lesson).** `packaging/{windows,macos}/config/*.spec` `hiddenimports` MUST be updated to include `privacyguard.word.adapter` / `privacyguard.word.worker` / `privacyguard.word.redact` / `privacyguard.word.clear_doc_props` / `privacyguard.word.candidate_dialog`. Otherwise `cp30`-style import regression reappears.

---

## Constraints Locked From Upstream This Phase

- **D-09 auto-trigger — locked.** `WordPIIWorker.start()` called immediately after `_open_word_docx` completes initialization. `require_confirmation` controls whether `WordCandidateDialog` opens after worker completion, but the SCAN itself is unconditional.
- **D-10 cp27 incremental DOM patch — locked.** No `setHtml()` in the PII path. Pane ID for runJavaScript: existing `word_preview` / `word_preview_replaced`.
- **D-11 candidate dialog scope — locked.** Phase 7 minimal; entity-type global toggles (UX-03) / document whitelist (UX-05) / undo stack (UX-06) deferred to Phase 7.
- **D-12 no new PyPI deps — locked.** `python-docx` + `mammoth` + `bs4` + PyQt6 stack unchanged.
- **D-13 ≥1 new test class — locked.** `tests/unit/test_word_pii_pipeline.py` (8 test classes per RESEARCH §Code Examples).
- **D-14 79/79 + new = 88/88 baseline — locked.** Full suite command line is fixed (CLAUDE.md).
- **D-15 entity-type scope — locked.** 9 entity types: CN_ID_CARD / CN_PHONE / CN_BANK_CARD / CN_EMAIL / CN_USCC / CN_TAXPAYER_ID / CN_TAXPAYER_ID_15 / CN_VAT_INVOICE / CN_BANK_ACCOUNT. No new entity types this phase.
- **D-16 PIIHit fields — locked.** 7 + 2 = 9 fields; Word `page_rect` is `(0, 0, 0, 0)` placeholder.
- **D-17 PIIEngine input — locked.** `PIIEngine.detect(TextUnit(page_index=key_index, text=word_data[key]["text"], source="text"))`, `page=None`.
- **D-18 word_data pii channel — locked.** `word_data[key]["pii"]` parallel to `ocr` / `manual`. NO new global `self.pii_hits` list.
- **D-19 priority — locked.** `rule > pii > manual > ocr`. `merge_word_matches_with_priority` 4th param MUST default to `None` (back-compat).
- **D-20 PII color — locked.** `#D64545` (light) / `#FF6B6B` (dark). No new hex tokens.
- **D-21 short-code badge — locked.** 9 fixed ASCII codes (`ID` / `PHONE` / `BANK` / `EMAIL` / `USCC` / `TAX` / `TAX15` / `VAT` / `ACCT`).
- **D-22 data-key injection reuse — locked.** Reuse `_add_data_key_attributes` + `_add_data_key_regex_fallback`; do NOT rewrite.
- **D-23 redact_word reuse — locked.** Wrapper around existing `main.py:replace_matches_in_paragraph`; no replacement logic in `main.py` or in `privacyguard.word.redact`.
- **D-24 clear-word-doc-props position — locked.** Called inside `_save_word` IMMEDIATELY BEFORE `new_doc.save(fname)`.
- **D-25 candidate dialog minimal scope — locked.** 50-entries pagination + entity_type filter + source filter + per-row checkbox + 4 CTAs; NO Phase 7 features.
- **D-26 fixture synthesized — locked.** `tests/fixtures/fake_word.py::build_fake_docx` synthesizes with `python-docx` (Faker-generated PII); OPS-05 no real PII in fixtures.

---

## Registry Safety

Not applicable — this is a PyQt6 desktop application with no third-party component registries. All UI primitives are PyQt6 built-ins. All icons come from `assets/branding/v38/` (existing project assets). All colors come from `theme.py` (existing project module). New HTML tokens (mark + piitag) are inline `<style>` injected alongside the cp27 patch script — they reuse `theme.py` hex values directly; no new asset files.

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| n/a (PyQt6) | n/a | not applicable — no third-party UI registries involved |

If any future phase introduces an icon asset NOT in `assets/branding/v38/`, that asset must be added there first, and the safety gate must be re-run against the asset (file existence + readable SVG).

---

## UI-Considerations Coverage Verification (provenance)

- **Total state categories resolved:** 24 covered · 3 backstop · 0 unresolved
  - E1 (left `<mark class="pii-highlight">`): 7 covered · 1 backstop (overflow at 8+ consecutive hits)
  - E2 (right `<mark class="pii-mask">`): 7 covered · 1 backstop (long-text tooltip)
  - E3 (`WordCandidateDialog`): 7 covered · 1 backstop (long-text row labels)
  - E4 (`wordPiiStatusChip`): 2 covered
- **Probe provenance:** ui-consideration-probe @ /home/rende/.claude/gsd-core/bin/lib/ui-consideration-probe.cjs · 2026-08-12 · elements heredoc generated post-write
- **Backstop statements (lifted into verify-time as `{ statement, verification: backstop }`):**
  - E1 overflow: "8+ consecutive PII hits remain visually distinguishable at 720p / 100% DPI"
  - E2 long-text: "Tooltip on `<mark class='pii-mask'>` fits within 720p viewport on both themes"
  - E3 long-text: "Candidate row labels truncate cleanly at 720p / 100% DPI without row-vertical-overflow"

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS (reuse Phase 1 + accent-for-mask; reserved-for lists explicit)
- [ ] Dimension 4 Typography: PASS (Phase 1 sizes reused; one new HTML-specific 11px Semibold for `pii-tag`)
- [ ] Dimension 5 Spacing: PASS (Phase 1 tokens reused)
- [ ] Dimension 6 Registry Safety: PASS (N/A — PyQt6; explicit not-applicable note required)

**Approval:** pending gsd-ui-checker verification
