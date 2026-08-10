---
phase: 01-pdf
plan: 03
slug: worker-and-ui
type: execute
wave: 3
depends_on:
  - "01-02"
files_modified:
  - privacyguard/ocr/full_page_ocr.py
  - privacyguard/ocr/__init__.py
  - privacyguard/workers/ocr_worker.py
  - main.py
  - config.json
  - config.json.template
  - tests/unit/test_app_config.py
  - tests/unit/test_pii_offline.py
  - tests/unit/test_pdf_pii_pipeline.py
  - packaging/windows/config/PrivacyGuard_windows.spec
  - packaging/macos/scripts/build_complete.sh
autonomous: true
requirements:
  - FMT-01
  - ENGINE-07
  - ENGINE-08
  - OPS-03
  - OPS-07
  - NUM-01
  - NUM-02
  - NUM-03
user_setup: []

estimate:
  tokens: 75000
  raw_tokens: 37500
  tasks: 3
  confidence: medium

must_haves:
  truths:
    - privacyguard.ocr.full_page_ocr.collect_full_page_ocr_hits returns a list of (x, y, w, h) tuples for a page where page.get_text() is empty and image blocks are present, using the dependency-injection signature (recognize_fn / calculate_rect_fn / clip_to_page_rect_fn / preprocess_fn / render_fn).
    - _ModularOCRWorker.run invokes collect_full_page_ocr_hits when page_text is empty AND no image blocks present (full-page OCR fallback), wired before page_result_signal emission, with isInterruptionRequested() checked between page iterations.
    - _ModularOCRWorker emits pii_signal.emit(page_idx, [dataclasses.asdict(h) for h in pii_hits]) after the existing page_result_signal.emit, for each page where PII detection ran.
    - OCRWorker constructor in main.py accepts pii_engine_enabled: bool and pii_settings: dict kwargs and forwards them to _ModularOCRWorker super().__init__.
    - MainWindow.start_ocr connects self.worker.pii_signal.connect(self._on_pii_page_result) alongside the existing four signal connections.
    - MainWindow._on_pii_page_result writes the deserialized PIIHit list into self.page_data[page_num]["pii"] and calls self.render_view() when the current page equals page_num.
    - MainWindow.__init__ initializes page_data with 'pii' key as empty list (D-04: add-alongside 'ocr' / 'manual' siblings).
    - MainWindow._on_ocr_finished_safe emits the PII confirmation dialog (if require_confirmation=true AND HIGH hits > 0) before save flow.
    - MainWindow.save_pdf merges pii_list alongside ocr_list + manual_list and applies add_redact_annot + apply_redactions(images=PDF_REDACT_IMAGE_PIXELS) for all three (D-04 + SAFE-01).
    - SettingsDialog has a "5 隐私识别" tab with three QCheckBox (cb_pii_engine_enabled / cb_pii_auto_redact / cb_pii_require_confirm) and a read-only QLabel "扫描范围（只读）：身份证号 / 手机号" (UI-SPEC §E1 populated state).
    - SinglePageCanvas.paintEvent renders PII rects in a third paint loop after rects_ocr and rects_manual, using danger color #D64545 stroke + alpha-0.18 fill (light theme) / #FF6B6B with alpha-0.22 (dark theme), with anchored label badges "ID" / "PHONE" (UI-SPEC §PII Rect Rendering).
    - config.json + config.json.template contain a `pii_settings` block with `engine_enabled: true / auto_redact: true / require_confirmation: false / scan_scope: ["CN_ID_CARD","CN_PHONE"]`.
    - SimpleConfig round-trips pii_settings.* keys through set / save / reload (test_app_config.py extension).
    - tests/unit/test_pii_offline.py monkey-patches socket.socket, runs PIIEngine.detect over 500 pages, and asserts the recorded socket call count is zero (ENGINE-08 zero-network).
    - tests/unit/test_pdf_pii_pipeline.py builds a synthetic PDF, runs PIIEngine + pdf_adapter end-to-end, and asserts sensitive substrings absent from reverse-extraction (FMT-01 + SAFE-01/02).
    - packaging/windows/config/PrivacyGuard_windows.spec datas contains `(os.path.join(project_root, 'privacyguard', 'pii', 'data'), 'privacyguard/pii/data')` and hiddenimports contains the privacyguard.pii.* module names so frozen launches can load rules.json (cp30 regression guard).
    - packaging/macos/scripts/build_complete.sh copies privacyguard/pii/data/rules.json into the .app bundle (or has a parity check).
  artifacts:
    - privacyguard/ocr/full_page_ocr.py (render_full_page_to_bgr + collect_full_page_ocr_hits per D-03 DI signature)
    - privacyguard/ocr/__init__.py (extended with collect_full_page_ocr_hits + render_full_page_to_bgr re-export)
    - privacyguard/workers/ocr_worker.py (pii_signal signal, _detect_pii_for_page method, _get_pii_engine lazy init, run-loop integration)
    - main.py (page_data init with 'pii' key, OCRWorker compat layer pii_signal kwargs, MainWindow._on_pii_page_result slot, _pii_settings init, SettingsDialog "5 隐私识别" tab with 3 QCheckBox + scope label, SinglePageCanvas.paintEvent PII third loop, save_pdf pii_list merge, _pii_data_lock QMutex)
    - config.json (pii_settings block)
    - config.json.template (pii_settings block)
    - tests/unit/test_app_config.py (test_simple_config_pii_settings_default + test_simple_config_pii_settings_round_trip)
    - tests/unit/test_pii_offline.py (TestPiiOffline.test_engine_makes_no_network_calls over 500 pages)
    - tests/unit/test_pdf_pii_pipeline.py (end-to-end pipeline stub from Plan 01-01 extended with image-block + full-page paths)
    - packaging/windows/config/PrivacyGuard_windows.spec (datas + hiddenimports additions)
    - packaging/macos/scripts/build_complete.sh (data file copy verification line)
  key_links:
    - _ModularOCRWorker.run → collect_text_pdf_hit_boxes (existing) + collect_image_block_ocr_hits (existing) + collect_full_page_ocr_hits (NEW D-03) + PIIEngine.detect (NEW) → page_result_signal + pii_signal → MainWindow slots
    - MainWindow._on_pii_page_result → page_data[page_num]["pii"] (D-04) → SinglePageCanvas.paintEvent third loop (D-05 PIIHit.page_rect render)
    - MainWindow.save_pdf → ocr_list + manual_list + pii_list → add_redact_annot + apply_redactions(IMAGE_PIXELS) (D-04 + SAFE-01)
    - SettingsDialog "5 隐私识别" tab → cb_pii_engine_enabled / cb_pii_auto_redact / cb_pii_require_confirm → config.json.set("pii_settings.*") (D-08)
    - PyInstaller spec datas + hiddenimports → frozen launch loads rules.json via resource_path (cp30 + OPS-03)
  prohibitions:
    - 不得在 _ModularOCRWorker.run 中开新线程跑 PII 检测；必须复用 OCRWorker 同一线程 + isInterruptionRequested()（OPS-03 单线程契约）
    - 不得在 collect_full_page_ocr_hits 中硬编码 OCR 引擎；必须用 dependency-injection 的 recognize_fn / calculate_rect_fn / render_fn 注入（D-03 DI 形态）
    - 不得在 _on_pii_page_result 中同步触发画布重绘导致主线程卡顿；使用 render_view() 而非同步循环更新
    - 不得在 SettingsDialog 中修改现有四个 tab 的结构；新 PII tab 作为第 5 个 box_pii 卡片追加（D-09 不动现有 tab）
    - 不得在 PyInstaller spec 中漏声明 privacyguard.pii.data；否则 frozen 启动报 FileNotFoundError（cp30 教训）
    - 不得在 PII 引擎中触发任何 socket 调用；test_pii_offline.py 守护 ENGINE-08
    - 不得在 SinglePageCanvas 鼠标事件中允许删除 PII 命中框（UI-SPEC §PII Rect Rendering 锁定 PII 为只读，Phase 7 才提供删除 UI）

threat_model:
  trust_boundaries:
    - {name: Worker thread → MainWindow slot, description: pii_signal crosses thread boundary; PIIHit dataclasses serialized via dataclasses.asdict}
    - {name: PDF on disk → OCRWorker, description: untrusted PDF path crosses here; existing validate_safe_path guards the path (cp30)}
    - {name: SettingsDialog → config.json on disk, description: pii_settings fields persisted to disk via SimpleConfig.set; subsequent restart reads them}
    - {name: PyInstaller frozen launcher → privacyguard/pii/data/rules.json, description: spec datas must include the directory; sys._MEIPASS resolution at runtime}
  stride:
    - {id: T-03-PDF-PATH, category: Tampering / Information Disclosure, component: MainWindow.open_pdf path validation, severity: medium, disposition: mitigate, mitigation: existing validate_safe_path enforces path safety; PII worker inherits same path}
    - {id: T-03-FAKE, category: Information Disclosure, component: MainWindow.save_pdf pii_list merge, severity: critical, disposition: mitigate, mitigation: same add_redact_annot + apply_redactions(IMAGE_PIXELS) pattern as ocr/manual list; reverse-extraction test_pdf_pii_pipeline.py covers end-to-end merge path}
    - {id: T-03-NETWORK, category: Information Disclosure, component: PII engine + OCR worker, severity: high, disposition: mitigate, mitigation: test_pii_offline.py asserts zero socket calls; ENGINE-08 hard contract}
    - {id: T-03-LAZY-BREAK, category: Denial of Service / Import-time, component: pii_signal emitted from _ModularOCRWorker requires privacyguard.pii.engine loaded, severity: medium, disposition: mitigate, mitigation: lazy import inside _get_pii_engine; test_package_imports.py verifies import privacyguard does not load privacyguard.pii.engine}
    - {id: T-03-PYINSTALLER-MISS, category: Denial of Service, component: privacyguard/pii/data/rules.json missing in frozen bundle, severity: medium, disposition: mitigate, mitigation: spec datas + hiddenimports entries; build_complete.sh parity check; cp30 regression class extended}
    - {id: T-03-THREAD-RACE, category: Tampering, component: pii_signal slot mutating page_data while UI reads it, severity: low, disposition: mitigate, mitigation: _pii_data_lock = QMutex() wraps page_data[page]["pii"] assignment; existing _word_data_lock pattern}
    - {id: T-03-CONFIRM-SKIP, category: Repudiation, component: require_confirmation dialog dismissed without explicit choice, severity: low, disposition: accept, rationale: Phase 1 minimal confirmation dialog uses QDialog.reject(); save loop respects user's choice; Phase 7 replaces with proper review queue}

---

<objective>
Wire the PII engine into the running app: full-page OCR fallback (D-03), worker thread integration (pii_signal in _ModularOCRWorker), main.py UI surfaces (settings tab + canvas render + save loop merge + pii_data_lock), config persistence (pii_settings block + SimpleConfig round-trip), zero-network ENGINE-08 guard, and PyInstaller datas entry for frozen-launch compatibility.
</objective>

<purpose>
The engine + tracer are proven (Plans 01-01 + 01-02). Now they must actually run inside the user's app. This plan connects the engine to the OCR worker thread, the settings dialog, the canvas, and the save loop. It also locks the zero-network guarantee and the PyInstaller packaging so the v37.7.6 freeze contract (cp30) does not regress.
</purpose>

<output>
- privacyguard/ocr/full_page_ocr.py new module (D-03 collect_full_page_ocr_hits)
- privacyguard/ocr/__init__.py re-export
- privacyguard/workers/ocr_worker.py pii_signal + lazy engine init + run-loop integration
- main.py: page_data 'pii' key default, OCRWorker compat layer accepts pii_engine_enabled + pii_settings, _on_pii_page_result slot, _pii_settings init from config.json, SettingsDialog "5 隐私识别" tab + 3 QCheckBox + scope label, SinglePageCanvas.paintEvent PII third loop, save_pdf pii_list merge, _pii_data_lock QMutex, _on_ocr_finished_safe confirmation dialog (require_confirmation path)
- config.json + config.json.template pii_settings block
- tests/unit/test_app_config.py extension (default + round-trip)
- tests/unit/test_pii_offline.py new (500-page socket monkey-patch)
- tests/unit/test_pdf_pii_pipeline.py new (end-to-end with image block path)
- packaging/windows/config/PrivacyGuard_windows.spec datas + hiddenimports additions
- packaging/macos/scripts/build_complete.sh parity check
</output>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-pdf/01-CONTEXT.md
@.planning/phases/01-pdf/01-PATTERNS.md
@.planning/phases/01-pdf/01-VALIDATION.md
@.planning/phases/01-pdf/01-RESEARCH.md
@.planning/phases/01-pdf/01-UI-SPEC.md
@privacyguard/ocr/mixed_pdf.py
@privacyguard/ocr/text_pdf.py
@privacyguard/workers/ocr_worker.py
@main.py
@config.json
@config.json.template
@privacyguard/pii/__init__.py
@privacyguard/pii/engine.py
@privacyguard/pii/hits.py
@privacyguard/pii/pdf_adapter.py
</context>

<tasks>

<task type="auto">
  <name>Add collect_full_page_ocr_hits (D-03) + worker pii_signal + run-loop integration</name>
  <files>
    - privacyguard/ocr/full_page_ocr.py
    - privacyguard/ocr/__init__.py
    - privacyguard/workers/ocr_worker.py
  </files>
  <read_first>
    - .planning/phases/01-pdf/01-PATTERNS.md (lines 626-686 — full_page_ocr.py DI signature mirroring collect_image_block_ocr_hits)
    - .planning/phases/01-pdf/01-PATTERNS.md (lines 732-786 — ocr_worker.py pii_signal + _detect_pii_for_page pattern)
    - .planning/phases/01-pdf/01-RESEARCH.md (lines 308-369 — Pattern 1 DI collector shape)
    - privacyguard/ocr/mixed_pdf.py:76-131 (collect_image_block_ocr_hits exact analog)
    - privacyguard/ocr/__init__.py:7-18 (eager re-export pattern)
    - privacyguard/workers/ocr_worker.py:42-69 (signal definitions + __init__ params)
    - privacyguard/workers/ocr_worker.py:347-474 (run() loop body)
  </read_first>
  <action>
    Wire the full-page OCR fallback and the worker integration per D-03 + FMT-01.

    **privacyguard/ocr/full_page_ocr.py** (NEW): Mirror the DI shape of `collect_image_block_ocr_hits` from `privacyguard/ocr/mixed_pdf.py:76-131`.
    - `render_full_page_to_bgr(page, scan_scale: float)`: use `page.get_pixmap(matrix=fitz.Matrix(scan_scale, scan_scale), alpha=False)`, then `cv2.imdecode(np.frombuffer(pix.tobytes("png"), dtype=np.uint8), cv2.IMREAD_COLOR)`. Wrap in try/except returning None on error.
    - `collect_full_page_ocr_hits(page, scan_scale, recognize_fn, calculate_rect_fn, clip_to_page_rect_fn=None, preprocess_fn=None, render_fn=None)`:
      - Compute `page_rect = page.rect` once.
      - `render = render_fn or render_full_page_to_bgr`.
      - Try `img_bgr = render(page, scan_scale)`; on Exception return `[]`.
      - If img_bgr is None or `getattr(img_bgr, "size", 0) == 0`: return `[]`.
      - `scan_img = preprocess_fn(img_bgr) if preprocess_fn else img_bgr`.
      - Try `ocr_results = recognize_fn(scan_img)`; on Exception return `[]`.
      - For each `(box, text)` in `iter_ocr_lines(ocr_results)`: skip empty text.
      - For OCR-text hits, yield candidates to a new helper `_collect_pii_rects_in_ocr_text(text, scan_img.shape, calculate_rect_fn, clip_to_page_rect_fn=None, page_rect=page_rect, scan_scale=scan_scale)` — actually simpler: have `collect_full_page_ocr_hits` return raw `(x0, y0, w, h)` tuples in page coordinates by computing `sx = (page_rect.x1 - page_rect.x0) / scan_img.shape[1]`, `sy = (page_rect.y1 - page_rect.y0) / scan_img.shape[0]`, and applying the local → page transformation in the loop body (no extra helper).
      - This function returns a list of `(x0, y0, w, h)` tuples consistent with `collect_image_block_ocr_hits` output shape.
    - NO OCR engine import at module top-level — recognize_fn is injected (D-03 DI discipline).

    **privacyguard/ocr/__init__.py** (modify): Add to `__all__`: `'collect_full_page_ocr_hits'`, `'render_full_page_to_bgr'`. Add absolute import lines: `from privacyguard.ocr.full_page_ocr import collect_full_page_ocr_hits, render_full_page_to_bgr`.

    **privacyguard/workers/ocr_worker.py** (modify):
    - Add new signal after `error_signal`: `pii_signal = pyqtSignal(int, list)  # Phase 1: (page_idx, [PIIHit.asdict, ...])`.
    - Extend `__init__` to accept `pii_engine_enabled: bool = False, pii_settings: dict = None`. Store as `self.pii_engine_enabled` and `self._pii_settings`. Add `self._pii_engine = None` (lazy init, cp30 discipline).
    - Add method `_get_pii_engine(self)`: lazy import `from privacyguard.pii.engine import PIIEngine`, instantiate `PIIEngine(rules_data=self._pii_settings.get("rules_data"))` if `_pii_engine is None`, cache in `self._pii_engine`. Wrap in try/except returning None on exception (worker must not crash).
    - Add method `_detect_pii_for_page(self, page, page_idx, page_text) -> list`: import `from privacyguard.pii.hits import TextUnit` + `import dataclasses` inside; if `not self.pii_engine_enabled` return []; engine = `_get_pii_engine()`; if engine is None return []; source = "text" if `page_text.strip()` else "full_page_ocr"; unit = `TextUnit(page_idx, page_text, source)`; try hits = `engine.detect(unit)`; return `[dataclasses.asdict(h) for h in hits]`; except Exception as exc: `print(f"[PII ERROR] 页面 {page_idx}: {type(exc).__name__}: {exc}")` and return [].
    - In `run()` method (currently at lines 347-474), after `self.page_result_signal.emit(i, rects)` (around line 447), insert:
      ```python
      pii_hits = self._detect_pii_for_page(page, i, page_text)
      if pii_hits:
          self.pii_signal.emit(i, pii_hits)
      ```
    - Inside the existing `if not image_clip_rects and not page_text.strip():` block (around line 397-398), extend the condition so that when `not page_text.strip()` we still call `collect_full_page_ocr_hits` to populate `image_clip_rects` (D-03 fallback). Pass the same DI callbacks used for `collect_image_block_ocr_hits` (`recognize_fn=lambda scan_img: ocr_engine.recognize(scan_img)`, `calculate_rect_fn=lambda box, text, span, scan_img: self.calculate_sub_rect(...)`, etc.). This wires the full-page OCR fallback per FMT-01.

    After edits, run `python3 -m unittest tests.unit.test_mixed_pdf_ocr tests.unit.test_pdf_text_hit_dedup tests.unit.test_convergence -v` to confirm no regression.
  </action>
  <verify>
    <automated>python3 -m compileall -q privacyguard/ocr/full_page_ocr.py privacyguard/ocr/__init__.py privacyguard/workers/ocr_worker.py && python3 -m unittest tests.unit.test_mixed_pdf_ocr tests.unit.test_pdf_text_hit_dedup tests.unit.test_convergence tests.unit.test_pii_engine tests.unit.test_pdf_pii_redaction -v 2>&1 | tail -15</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m compileall -q privacyguard/ocr/full_page_ocr.py privacyguard/ocr/__init__.py privacyguard/workers/ocr_worker.py` exits 0.
    - `python3 -c "from privacyguard.ocr import collect_full_page_ocr_hits, render_full_page_to_bgr; print('OK')"` prints OK (eager re-export works).
    - `python3 -c "from privacyguard.workers.ocr_worker import _ModularOCRWorker; import inspect; sig = inspect.signature(_ModularOCRWorker.__init__); params = list(sig.parameters.keys()); assert 'pii_engine_enabled' in params; assert 'pii_settings' in params; print('OK')"` prints OK (worker signature extended).
    - `python3 -c "from privacyguard.workers.ocr_worker import _ModularOCRWorker; import inspect; src = inspect.getsource(_ModularOCRWorker.run); assert 'pii_signal' in src; assert '_detect_pii_for_page' in src; assert 'collect_full_page_ocr_hits' in src; print('OK')"` prints OK (run loop wired).
    - `python3 -m unittest tests.unit.test_mixed_pdf_ocr -v` remains green (image-block OCR + new full-page OCR fallback coexist without regression).
    - `python3 -m unittest tests.unit.test_convergence -v` remains green (no inline PII detection in main.py yet, but worker doesn't define inline PII either).
    - `python3 -m unittest tests.unit.test_pii_engine -v` remains green (engine pure-Python contract preserved).
  </acceptance_criteria>
  <done>
    Worker thread emits pii_signal alongside page_result_signal for each page where PII detection ran. Full-page OCR fallback (D-03) wires into the existing run loop using the same DI shape as collect_image_block_ocr_hits. No new eager imports in privacyguard.ocr or privacyguard.workers at module top-level.
  </done>
  <reversibility>rating="costly" rationale="Worker integration is consumed by every later plan (UI, settings, save loop). The pii_signal payload shape (page_idx, list of asdict'd PIIHit dicts) becomes the contract boundary between worker thread and MainWindow slot; renaming would break the wire protocol.</reversibility>
</task>

<task type="auto">
  <name>Wire main.py UI surfaces: settings tab + canvas render + save loop + pii_data_lock</name>
  <files>
    - main.py
    - config.json
    - config.json.template
    - tests/unit/test_app_config.py
  </files>
  <read_first>
    - .planning/phases/01-pdf/01-PATTERNS.md (lines 791-996 — main.py modifications at sites 1-7)
    - .planning/phases/01-pdf/01-UI-SPEC.md (lines 95-141 — copywriting contract)
    - .planning/phases/01-pdf/01-UI-SPEC.md (lines 148-203 — visuals PII rect rendering + settings card layout)
    - .planning/phases/01-pdf/01-UI-SPEC.md (lines 257-292 — interaction contract + state coverage)
    - main.py:1526-1601 (existing box_ocr card pattern — template for box_pii card)
    - main.py:4100-4126 (SinglePageCanvas.paintEvent existing 3-step render)
    - main.py:12354-12385 (save loop PyMuPDF redaction)
    - main.py:11130-11142 (start_ocr worker construction)
    - main.py:11255-11263 (_on_ocr_page_result slot)
    - main.py:10521 (page_data initialization)
    - main.py:4892-4910 (SimpleConfig read at MainWindow init)
    - config.json:19-82 (existing redaction block layout)
    - config.json.template:82-90 (existing template layout)
    - tests/unit/test_app_config.py:22-40 (existing SimpleConfig round-trip pattern)
  </read_first>
  <action>
    Modify main.py at six specific sites (per PATTERNS.md Site 1-7) and add `pii_settings` block to config.json + config.json.template.

    **Site 1: MainWindow config read (around main.py:4892-4911):** After the `self.custom_keywords = config.get(...)` line, add:
    ```python
    self.pii_settings = {
        "engine_enabled": config.get("pii_settings.engine_enabled", True),
        "auto_redact": config.get("pii_settings.auto_redact", True),
        "require_confirmation": config.get("pii_settings.require_confirmation", False),
    }
    self._pii_data_lock = QMutex()  # v38.x: protect page_data[page]["pii"] writes
    ```

    **Site 2: page_data init (around main.py:10521):** Change the page_data initialization to include `'pii': []` as a third key alongside `'ocr'` and `'manual'`. Search for the dict comprehension `{i: {'ocr': [], 'manual': []} for i in range(total)}` and add `'pii': []`.

    **Site 3: OCRWorker construction in start_ocr (around main.py:11130-11142):** Extend the `OCRWorker(...)` call to include `pii_engine_enabled=self.pii_settings.get("engine_enabled", True)` and `pii_settings=self.pii_settings`. Add `self.worker.pii_signal.connect(self._on_pii_page_result)` immediately after the existing signal connections.

    **Site 4: _on_pii_page_result slot (add new method near main.py:11255-11263):** Define:
    ```python
    def _on_pii_page_result(self, page_num: int, pii_hits: list):
        if page_num not in self.page_data:
            return
        from privacyguard.pii.hits import PIIHit  # lazy import inside slot
        with QMutexLocker(self._pii_data_lock):
            self.page_data[page_num]["pii"] = [PIIHit(**h) for h in pii_hits]
        if self.current_page == page_num:
            self.render_view()
    ```

    **Site 5: SinglePageCanvas.paintEvent PII third loop (main.py:4100-4126):** Insert a third paint loop after the `rects_manual` loop and before the dragging-rubber-band loop. Use `QPen(QColor("#D64545"), 2)` for stroke, `QColor("#D64545")` with `setAlphaF(0.18)` for fill. Iterate `self.main_window.page_data.get(self.page_index, {}).get("pii", [])`. Each hit: `r = QRectF(*hit.page_rect)`, `sr = self.pdf_to_screen(r)`, `painter.drawRect(sr)`. Then draw label badge: `label = "ID" if hit.entity_type == "CN_ID_CARD" else "PHONE"`; badge bg = solid `#D64545`; badge text color = `#FFFFFF`; badge rect = `QRectF(sr.x() - 2, sr.y() - 18, len(label) * 8 + 8, 16)`; `painter.drawText(QPointF(sr.x() + 2, sr.y() - 5), label)`. The canvas needs a reference to main_window; add `self.main_window = main_window` to the `SinglePageCanvas.__init__` constructor signature, default None. Update existing call sites that construct SinglePageCanvas to pass the main_window reference. The SinglePageCanvas.mousePressEvent delete-rubber-band loop must skip PII rects — add a guard check before deletion (read-only on canvas per UI-SPEC §PII Rect Rendering line 172).

    **Site 6: save_pdf pii_list merge (main.py:12354-12385):** Inside the page loop, after `for r in ocr_list + manual_list:` block (which adds redactions + applies + deletes annotations), add a separate loop for pii_list:
    ```python
    pii_list = self.page_data[i].get('pii', [])
    for hit in pii_list:
        x, y, w, h = hit.page_rect  # 4-tuple from PIIHit
        rect = fitz.Rect(x, y, x + w, y + h)
        annot = page.add_redact_annot(rect)
        annot.set_colors(stroke=fill_col, fill=fill_col)
        annot.update()
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
    for annot in page.annots():
        page.delete_annot(annot)
    ```
    IMPORTANT: move the `page.apply_redactions(...)` and `for annot in page.annots(): page.delete_annot(annot)` calls AFTER the pii_list loop so all three categories are baked into one apply call per page (more efficient and matches the existing single-page-loop semantics).

    **Site 7: SettingsDialog "5 隐私识别" tab (main.py:1526-1601 region):** After the existing `box_ocr` card definition, insert a new `box_pii` card following the exact QFrame + QVBoxLayout + settingsSectionCard objectName pattern. Header text per UI-SPEC §Copywriting. Three QCheckBox widgets: `cb_pii_engine_enabled`, `cb_pii_auto_redact`, `cb_pii_require_confirm` with locked labels + tooltips (verbatim from UI-SPEC lines 99-104). Read-only QLabel "扫描范围（只读）：身份证号 / 手机号" with `objectName=settingsFieldNote`. Add `box_pii` to `self._settings_sections` list. Add `cb_pii_engine_enabled.toggled.connect(self._sync_pii_toggle_state)` to grey-out toggles 2 + 3 when toggle 1 is off. In `save_settings` method, persist the three bools via `config.set("pii_settings.engine_enabled", self.cb_pii_engine_enabled.isChecked(), persist=False)` etc.

    **config.json + config.json.template:** Add after the existing `redaction` block (before `ocr` block):
    ```json
    "pii_settings": {
        "engine_enabled": true,
        "auto_redact": true,
        "require_confirmation": false,
        "scan_scope": ["CN_ID_CARD", "CN_PHONE"],
        "_comment": "Phase 1 隐私识别引擎设置；D-08 锁定"
    },
    ```

    **tests/unit/test_app_config.py:** Add two methods to TestAppConfig:
    - `test_simple_config_pii_settings_default`: build empty config, assert `config.get("pii_settings.engine_enabled")` is None (default behavior — MainWindow applies its own fallback).
    - `test_simple_config_pii_settings_round_trip`: set all three keys, save, reload, assert values match.

    After all edits, run the full 79/79 baseline + new PII tests + app_config tests. Note: this plan does NOT cover the PyQt-specific dialog / paintEvent testing (those need GUI; manual-verify table in 01-VALIDATION.md handles it). The reverse-extraction test_pdf_pii_redaction.py + test_pdf_pii_pipeline.py cover the engine+adapter path which is what matters for SAFE-01/02.
  </action>
  <verify>
    <automated>python3 -m compileall -q main.py && python3 -m unittest tests.unit.test_app_config tests.unit.test_pii_validators tests.unit.test_pii_engine tests.unit.test_pdf_pii_redaction tests.unit.test_mixed_pdf_ocr tests.unit.test_pdf_text_hit_dedup tests.unit.test_package_imports tests.unit.test_convergence tests.unit.test_fstring_safety tests.unit.test_config_alignment -v 2>&1 | tail -15</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m compileall -q main.py` exits 0 (syntax-only).
    - `python3 -c "from main import MainWindow, SettingsDialog; print('OK')"` prints OK (no import-time crash with all new code present).
    - `python3 -c "import json; cfg = json.load(open('config.json')); assert cfg['pii_settings']['engine_enabled'] is True; assert cfg['pii_settings']['auto_redact'] is True; assert cfg['pii_settings']['require_confirmation'] is False; assert cfg['pii_settings']['scan_scope'] == ['CN_ID_CARD', 'CN_PHONE']; print('OK')"` prints OK.
    - `python3 -c "import json; cfg = json.load(open('config.json.template')); assert cfg['pii_settings']['engine_enabled'] is True; print('OK')"` prints OK.
    - `python3 -m unittest tests.unit.test_app_config.TestAppConfig.test_simple_config_pii_settings_default tests.unit.test_app_config.TestAppConfig.test_simple_config_pii_settings_round_trip -v` both green.
    - `python3 -m unittest tests.unit.test_convergence -v` shows TestPiiConvergence (added in Plan 01-01 Task 3) still green — confirms main.py has no inline PIIHit / detect_pii.
    - Full 79/79 baseline + Plan 01-01 + Plan 01-02 + Plan 01-03 new tests all green.
  </acceptance_criteria>
  <done>
    MainWindow reads pii_settings from config.json; OCRWorker compat layer accepts pii_engine_enabled + pii_settings; _on_pii_page_result writes PIIHit list into page_data["pii"]; SinglePageCanvas.paintEvent renders PII rects with danger color + ID/PHONE label; save_pdf merges pii_list into the existing PyMuPDF add_redact_annot + apply_redactions(IMAGE_PIXELS) flow; SettingsDialog has "5 隐私识别" tab with three QCheckBox; config.json + config.json.template carry the pii_settings block.
  </done>
  <reversibility>rating="one-way" rationale="page_data["pii"] key contract (D-04), pii_settings field names (D-08 engine_enabled / auto_redact / require_confirmation), and SettingsDialog tab structure become reference contracts for Phase 2+ consumers (review queue, audit report, real-document accuracy baseline). Renaming any of these forces coordinated UI + worker + config edits.</reversibility>
</task>

<task type="auto">
  <name>Add ENGINE-08 zero-network test + FMT-01 pipeline test + PyInstaller packaging update</name>
  <files>
    - tests/unit/test_pii_offline.py
    - tests/unit/test_pdf_pii_pipeline.py
    - packaging/windows/config/PrivacyGuard_windows.spec
    - packaging/macos/scripts/build_complete.sh
  </files>
  <read_first>
    - .planning/phases/01-pdf/01-PATTERNS.md (lines 1252-1283 — test_pii_offline.py socket monkey-patch pattern)
    - .planning/phases/01-pdf/01-PATTERNS.md (lines 1287-1291 — test_pdf_pii_pipeline.py end-to-end pattern)
    - .planning/phases/01-pdf/01-VALIDATION.md (lines 1176-1189 — Wave 0 Requirements list)
    - .planning/phases/01-pdf/01-RESEARCH.md (lines 1248-1280 — Validation Architecture)
    - .planning/phases/01-pdf/01-RESEARCH.md (Pitfall 8 cp30 PyInstaller data file loss)
    - packaging/windows/config/PrivacyGuard_windows.spec (existing datas + hiddenimports)
    - packaging/macos/scripts/build_complete.sh (existing data copy logic)
    - tests/unit/test_package_imports.py (monkey-patch __import__ pattern)
  </read_first>
  <action>
    Add the offline / pipeline / packaging tests that close Phase 1's safety floor.

    **tests/unit/test_pii_offline.py** (NEW):
    - Class `TestPiiOffline(unittest.TestCase)` with one method `test_engine_makes_no_network_calls`:
      - `import socket`.
      - `original_socket = socket.socket`.
      - `socket_calls = []`.
      - Define `counting_socket(*args, **kwargs)` that appends to `socket_calls` then returns `original_socket(*args, **kwargs)`.
      - `from privacyguard.pii.engine import PIIEngine` and `from privacyguard.pii.hits import TextUnit`.
      - Inside `with patch("socket.socket", side_effect=counting_socket):`:
        - engine = `PIIEngine()`.
        - For i in range(500): unit = `TextUnit(page_index=i, text=f"page {i} 13812345678 53010219200508011X", source="text")`; `engine.detect(unit)`.
      - Assert `len(socket_calls) == 0` with a descriptive failure message.
    - Class `TestPrivacyGuardPiiNoTopLevelNetwork` with one method `test_no_requests_or_httpx_imports`: scan all `privacyguard/pii/*.py` and `privacyguard/pii/**/*.py` files; for each, read source and assert none contain `import requests`, `import httpx`, `import urllib.request`, `from requests import`, `from httpx import`, `from urllib.request import`. (Static guard.)

    **tests/unit/test_pdf_pii_pipeline.py** (NEW):
    - Class `TestPiiPipelineEndToEnd(unittest.TestCase)`:
      - `test_text_layer_pdf_full_pipeline`: build PDF with one 18-digit ID + one phone via `tests.e2e.create_pii_test_pdf.create_pii_test_pdf`; run `PIIEngine.detect` over `TextUnit(i, page.get_text(), "text")` per page; collect `pii_rects` via `collect_pii_rects`; call `apply_pii_redactions(in_pdf, out_pdf, rects_per_page)`; open output with `fitz.open`; assert no sensitive substrings; assert at least 2 PIIHits produced.
      - `test_image_block_pdf_full_pipeline`: build a hybrid PDF with both text layer + an inserted image (use `page.insert_image(rect, pixmap=...)` of a rendered scan); run detect; assert image-block OCR path contributes hits when text layer misses; assert reverse-extraction clean.
      - `test_save_loop_piilist_included_in_redaction`: simulate the save loop's pii_list merge path (the same for-hit-in-pii_list block from Site 6 in Task 2) and confirm sensitive substrings absent.

    **packaging/windows/config/PrivacyGuard_windows.spec** (modify):
    - Locate the existing `datas=[...]` block in the spec.
    - Append (after the existing `(os.path.join(project_root, 'privacyguard', 'ocr'), 'privacyguard/ocr')` entry if present): `(os.path.join(project_root, 'privacyguard', 'pii', 'data'), 'privacyguard/pii/data')`.
    - Locate the existing `hiddenimports=[...]` block.
    - Append: `'privacyguard.pii'`, `'privacyguard.pii.engine'`, `'privacyguard.pii.hits'`, `'privacyguard.pii.validators'`, `'privacyguard.pii.validators.id_card'`, `'privacyguard.pii.validators.phone_segment'`, `'privacyguard.pii.pdf_adapter'`.

    **packaging/macos/scripts/build_complete.sh** (modify):
    - Locate the section that copies `privacyguard/ocr` data files (if present); add a parallel block copying `privacyguard/pii/data/rules.json` into the `.app` bundle's `Resources/privacyguard/pii/data/rules.json`.
    - Add a parity check: after the copy, run `test -f "$APP_BUNDLE/Contents/Resources/privacyguard/pii/data/rules.json" || { echo "[ERROR] rules.json missing in .app bundle"; exit 1; }`.

    Run the full combined verification command to confirm no regression and the new tests all green.
  </action>
  <verify>
    <automated>python3 -m compileall -q tests/unit/test_pii_offline.py tests/unit/test_pdf_pii_pipeline.py && python3 -m unittest tests.unit.test_pii_offline tests.unit.test_pdf_pii_pipeline tests.unit.test_pii_validators tests.unit.test_pii_engine tests.unit.test_pdf_pii_redaction tests.unit.test_mixed_pdf_ocr tests.unit.test_pdf_text_hit_dedup tests.unit.test_package_imports tests.unit.test_convergence tests.unit.test_app_config tests.unit.test_ocr_api tests.test_path_validation tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_config_alignment tests.unit.test_fstring_safety -v 2>&1 | tail -25</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m unittest tests.unit.test_pii_offline -v` green (both test classes: 500-page scan produces zero socket calls; no requests/httpx/urllib imports in privacyguard/pii/*).
    - `python3 -m unittest tests.unit.test_pdf_pii_pipeline -v` green (text-layer + image-block + save-loop pii_list merge paths all reverse-extract clean).
    - `python3 -c "import ast; spec = open('packaging/windows/config/PrivacyGuard_windows.spec').read(); assert 'privacyguard/pii/data' in spec; assert \"'privacyguard.pii.engine'\" in spec; print('OK')"` prints OK (Windows spec datas + hiddenimports updated).
    - `grep -q "privacyguard/pii/data" packaging/macos/scripts/build_complete.sh` exits 0 (macOS script references the new data file).
    - Full 79/79 baseline + Plan 01-01 (≥2 reverse-extraction) + Plan 01-02 (≥40 validator + ≥30 engine) + Plan 01-03 (≥1 offline + ≥3 pipeline) all green.
    - `python3 -c "import main; print('main.py still imports OK after all UI changes')"` prints OK.
  </acceptance_criteria>
  <done>
    ENGINE-08 zero-network is enforced by automated regression (socket monkey-patch + static import scan). FMT-01 PDF text-layer + image-block + save-loop pii_list merge paths all verified end-to-end. Windows + macOS PyInstaller packaging updated so frozen launches can load privacyguard/pii/data/rules.json (cp30 regression class extended). Phase 1's safety floor is locked: SAFE-01/02, OPS-03, OPS-07 all enforced by automated tests.
  </done>
  <reversibility>rating="reversible" rationale="Test files + spec edits; deletion or revert is straightforward."</reversibility>
</task>

</tasks>

<verification>
After all three tasks, the following command sequence must return all-green:

```
python3 -m compileall -q main.py privacyguard tests \
  && python3 -m unittest \
      tests.unit.test_mixed_pdf_ocr \
      tests.test_path_validation \
      tests.unit.test_ocr_api \
      tests.unit.test_package_imports \
      tests.unit.test_pdf_text_hit_dedup \
      tests.unit.test_app_config \
      tests.unit.test_word_replace_rules \
      tests.unit.test_batch_word_replace \
      tests.unit.test_config_alignment \
      tests.unit.test_fstring_safety \
      tests.unit.test_convergence \
      tests.unit.test_pdf_pii_redaction \
      tests.unit.test_pdf_pii_pipeline \
      tests.unit.test_pii_validators \
      tests.unit.test_pii_engine \
      tests.unit.test_pii_offline \
      -v
```

Expected: 79 baseline + ≥2 reverse-extraction (Plan 01-01) + ≥40 validator + ≥30 engine (Plan 01-02) + ≥1 offline + ≥3 pipeline (Plan 01-03) all green.

PyInstaller smoke (manual): on a developer workstation, run `cd packaging/windows/scripts && build_complete.bat` and confirm the resulting .exe launches without `FileNotFoundError: rules.json`; same for macOS via `cd packaging/macos/scripts && ./build_complete.sh`.
</verification>

<success_criteria>
- PII engine runs inside the existing _ModularOCRWorker thread, sharing isInterruptionRequested() cancellation + worker_lock lifecycle (OPS-03 single-thread + UI responsiveness).
- Full-page OCR fallback (D-03) wires into the existing run loop using the same DI shape as collect_image_block_ocr_hits.
- MainWindow UI surfaces: settings tab with 3 QCheckBox, canvas PII rendering with locked colors and ID/PHONE labels, save loop merging pii_list with PyMuPDF true redaction.
- config.json + config.json.template carry pii_settings block; SimpleConfig round-trips the three keys.
- ENGINE-08 zero-network enforced by 500-page socket monkey-patch + static import scan.
- FMT-01 PDF text-layer + image-block + full-page paths all verified end-to-end.
- PyInstaller spec datas + hiddenimports updated for both Windows and macOS.
- Existing 79/79 baseline preserved.
</success_criteria>

<output>
Create `.planning/phases/01-pdf/01-03-worker-and-ui-SUMMARY.md` when done. Commit message: `feat(01-03): worker + UI + settings + offline + packaging for Phase 1 PII detection`.
</output>