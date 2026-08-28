"""
Word 双栏预览 mixin — MainWindow Word 双栏预览逻辑 (PR-B2.3 迁出)

提供 19 个 Word 双栏预览相关方法,作为 `MainWindowWordPreviewMixin`。
`MainWindow` 通过多继承复用本 mixin,行为零改动。

来源:原 `main.py` 中 19 个 Word 双栏相关方法(共 700 行),逐字搬迁,逻辑零改动。

依赖 MainWindow 上的属性:
    - self.word_doc / self.word_data / self.word_compare_mode
    - self.word_web_view / self.lbl_word_original_header / self.lbl_word_replaced_header
    - self.word_compare_header / self.word_header_divider / self.word_preview_shell
    - self.app_state / self.density_mode
    - self.theme / self.Theme
"""
from __future__ import annotations

from bs4 import BeautifulSoup
from secureredact.redaction.word_rules import merge_word_matches_with_priority  # PR-C1.1
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QWidget,
)


# Word 双栏预览专用字体栈(原 main.py:301,PR-B2.3 迁出)
PREVIEW_FONT_STACK = '"Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", Arial, sans-serif'


class MainWindowWordPreviewMixin:
    """Word 双栏预览 / 滚动同步 / 资源缓存 / HTML 片段构建。

    方法签名与实现与原 MainWindow 内一致,直接被 MainWindow 继承使用。
    """

    def _reset_word_preview_cache(self):
        """重置 Word 预览缓存与待应用的局部更新状态。"""
        if hasattr(self, "_word_scroll_sync_timer"):
            self._invalidate_word_scroll_sync()
        self._cleanup_word_preview_assets_dir()
        self._word_base_html = None
        self._word_html_source_path = None
        self._word_tagged_html = None
        self._word_preview_document_html = None
        self._word_replaced_document_html = None
        self._word_replaced_html = None
        self._pending_word_preview_blocks = None
        self._pending_word_replaced_blocks = None
        self._word_preview_ready = False
        self._word_replaced_ready = False
        self._word_preview_loaded_source_path = None
        self._word_replaced_loaded_source_path = None
        self._word_preview_target_source_path = None
        self._word_replaced_target_source_path = None
        self._word_preview_assets_base_url = QUrl()

    def _cleanup_word_preview_assets_dir(self):
        """清理当前 Word 预览图片临时目录。"""
        asset_dir = getattr(self, "_word_preview_assets_dir", None)
        if not asset_dir:
            return

        try:
            if os.path.isdir(asset_dir):
                shutil.rmtree(asset_dir, ignore_errors=True)
        except Exception as e:
            print(f"[清理] 删除 Word 预览图片目录失败: {e}")

        temp_manager = getattr(self, "temp_manager", None)
        instance_lock = getattr(temp_manager, "_instance_lock", None)
        temp_dirs = getattr(temp_manager, "temp_dirs", None)
        if temp_manager is not None and instance_lock is not None and isinstance(temp_dirs, list):
            try:
                with instance_lock:
                    if asset_dir in temp_dirs:
                        temp_dirs.remove(asset_dir)
            except Exception:
                pass

        self._word_preview_assets_dir = None

    def _create_word_preview_asset_dir(self):
        """创建当前 Word 预览使用的图片资源目录。"""
        self._cleanup_word_preview_assets_dir()
        if hasattr(self, "temp_manager") and self.temp_manager is not None:
            asset_dir = self.temp_manager.create_temp_dir()
        else:
            asset_dir = tempfile.mkdtemp(prefix="pg_word_preview_")
        self._word_preview_assets_dir = asset_dir
        self._word_preview_assets_base_url = QUrl.fromLocalFile(os.path.join(asset_dir, ""))
        return asset_dir

    def _build_word_html_from_docx(self, docx_path):
        """将 DOCX 转成 HTML，并把嵌入图片提取到临时目录。"""
        import mammoth

        asset_dir = self._create_word_preview_asset_dir()
        image_counter = {"value": 0}

        def convert_image_to_file(image):
            image_counter["value"] += 1
            suffix = resolve_word_preview_image_suffix(getattr(image, "content_type", ""))
            image_name = f"word_image_{image_counter['value']:04d}{suffix}"
            target_path = os.path.join(asset_dir, image_name)
            try:
                with image.open() as image_source, open(target_path, "wb") as output_file:
                    shutil.copyfileobj(image_source, output_file)
                return {
                    "src": image_name,
                    "loading": "lazy",
                    "decoding": "async",
                }
            except Exception as e:
                print(f"[Word预览] 提取嵌入图片失败: {e}")
                return {
                    "src": WORD_PREVIEW_BROKEN_IMAGE_DATA_URI,
                    "loading": "lazy",
                    "decoding": "async",
                    "data-pg-image-error": "1",
                }

        with open(docx_path, "rb") as docx_file:
            result = mammoth.convert_to_html(
                docx_file,
                convert_image=mammoth.images.img_element(convert_image_to_file),
            )

        if getattr(result, "messages", None):
            for message in result.messages:
                print(f"[Word预览] Mammoth: {message}")
        return result.value

    def toggle_word_compare_preview(self):
        """允许用户主动隐藏或恢复 Word 右侧对比预览。"""
        if not self.word_doc:
            QMessageBox.information(self, "提示", "请先打开 Word 文档。")
            return

        if not self._has_word_replacement_candidates():
            QMessageBox.information(
                self,
                "提示",
                "当前还没有可对比的替换结果。\n请先设置替换规则或执行智能脱敏。"
            )
            self._refresh_word_compare_toggle()
            return

        self.word_compare_user_hidden = not self.word_compare_user_hidden
        self.render_word_preview()
        self._refresh_word_compare_toggle()

    def _set_word_compare_mode(self, enabled):
        """切换 Word 单栏/双栏预览。"""
        self.word_compare_mode = bool(enabled) and bool(self.word_doc)
        self.canvas_container.hide()
        self.word_compare_container.show()

        if self.word_compare_mode:
            if hasattr(self, "word_compare_header"):
                self.word_compare_header.show()
            if hasattr(self, "lbl_word_original_header"):
                self.lbl_word_original_header.setText("原文预览")
            if hasattr(self, "lbl_word_replaced_header"):
                self.lbl_word_replaced_header.show()
            if hasattr(self, "word_header_divider"):
                self.word_header_divider.show()
            self.word_preview_replaced_panel.show()
            self.word_preview_replaced.show()
            if hasattr(self, "word_compare_layout"):
                self.word_compare_layout.setStretch(0, 1)
                self.word_compare_layout.setStretch(1, 1)
        else:
            if hasattr(self, "word_compare_header"):
                self.word_compare_header.hide()
            if hasattr(self, "lbl_word_original_header"):
                self.lbl_word_original_header.setText("文档预览")
            if hasattr(self, "lbl_word_replaced_header"):
                self.lbl_word_replaced_header.hide()
            if hasattr(self, "word_header_divider"):
                self.word_header_divider.hide()
            self.word_preview_replaced_panel.hide()
            self.word_preview_replaced.hide()
            if hasattr(self, "word_compare_layout"):
                self.word_compare_layout.setStretch(0, 1)
                self.word_compare_layout.setStretch(1, 0)

        self._configure_word_scroll_sync_panels()

    def _build_word_replaced_preview_html(self, base_html):
        """构建替换后 HTML（右侧只读预览）。"""
        if not base_html:
            return ""

        text_blocks = {}
        for key, data in self.word_data.items():
            text = data.get("text", "")
            if text:
                text_blocks[key] = {"text": text, "escaped": text}

        try:
            html = self._add_data_key_attributes(base_html, text_blocks)
            soup = BeautifulSoup(html, "html.parser")
            for element in soup.find_all(attrs={"data-key": True}):
                key = element.get("data-key")
                if not key or key not in self.word_data:
                    continue

                source_text = self.word_data[key].get("text", "")
                merged_matches = merge_word_matches_with_priority(
                    source_text,
                    self.word_replace_rules,
                    self.replacement_text,
                    manual_matches=self.word_data[key].get("manual", []),
                    ocr_matches=self.word_data[key].get("ocr", [])
                )
                if not merged_matches:
                    continue

                replaced_fragment = self._build_replaced_preview_fragment(source_text, merged_matches)
                element.clear()
                fragment_soup = BeautifulSoup(replaced_fragment, "html.parser")
                children = list(fragment_soup.contents)
                if children:
                    for child in children:
                        element.append(child)
                else:
                    element.append(source_text)

            replaced_html = self._wrap_html_document(str(soup))
            style = f"""
            <style>
                body {{ font-family: {PREVIEW_FONT_STACK}; padding: 20px; line-height: 1.6; }}
                p:empty {{ display: none; margin: 0; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                td, th {{ border: 1px solid #ddd; padding: 8px; }}
                mark.replace-preview-highlight {{
                    background-color: #ffd666;
                    color: #2b1f00;
                    border-radius: 3px;
                    padding: 0 2px;
                    box-decoration-break: clone;
                    -webkit-box-decoration-break: clone;
                    box-shadow: inset 0 -1px 0 rgba(43, 31, 0, 0.20);
                }}
            </style>
            """
            if "<head>" in replaced_html:
                replaced_html = replaced_html.replace("<head>", "<head>" + style, 1)
            else:
                replaced_html = style + replaced_html
            return replaced_html
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            print(f"[WordReplacePreview] 构建替换预览失败: {e}")
            return self._wrap_html_document(base_html)

    def render_word_preview(self):
        """渲染 Word 文档预览（HTML）"""
        if not self.word_doc:
            return

        try:
            source_changed = self._word_base_html is None or self._word_html_source_path != self.file_path

            # 仅在源文件变化或无缓存时进行 docx -> html 转换
            if source_changed:
                self._word_base_html = self._build_word_html_from_docx(self.file_path)
                self._word_html_source_path = self.file_path
                self._build_word_preview_documents()

            has_candidates = self._has_word_replacement_candidates()
            if not has_candidates:
                self.word_compare_user_hidden = False
            compare_enabled = has_candidates and not self.word_compare_user_hidden
            self.word_compare_mode = compare_enabled
            self._set_word_compare_mode(compare_enabled)
            self._refresh_word_compare_toggle()
            self.word_preview.show()

            # v1.1.11: 禁用 Word 预览的拖拽接受，让事件传递到 MainWindow
            # 解决 Word 打开后无法拖拽打开新文件的问题
            self.word_preview.setAcceptDrops(False)
            self.word_preview_replaced.setAcceptDrops(False)

            # 设置 WebChannel（仅首次）
            if not hasattr(self, 'bridge') or self.bridge is None:
                channel = QWebChannel(self)
                self.bridge = WebViewBridge(self, self)
                channel.registerObject("pyBridge", self.bridge)
                self.word_web_channel = channel
            if self.word_web_channel is not None:
                self.word_preview.page().setWebChannel(self.word_web_channel)
                self.word_preview_replaced.page().setWebChannel(self.word_web_channel)

            self._pending_word_preview_blocks = self._build_word_original_panel_updates()
            base_url = self._word_preview_assets_base_url if self._word_preview_assets_base_url.isValid() else QUrl()
            if should_reload_word_panel(
                source_changed,
                self._word_preview_loaded_source_path,
                self.file_path,
                self._word_preview_ready
            ):
                self._word_preview_target_source_path = self.file_path
                self.word_preview.setHtml(self._word_preview_document_html or "", base_url)
            else:
                self._apply_word_panel_updates(self.word_preview, self._pending_word_preview_blocks)

            if compare_enabled:
                self._pending_word_replaced_blocks = self._build_word_replaced_panel_updates()
                self._word_replaced_html = self._word_replaced_document_html
                if should_reload_word_panel(
                    source_changed,
                    self._word_replaced_loaded_source_path,
                    self.file_path,
                    self._word_replaced_ready
                ):
                    self._word_replaced_target_source_path = self.file_path
                    self.word_preview_replaced.setHtml(self._word_replaced_document_html or "", base_url)
                else:
                    self._apply_word_panel_updates(self.word_preview_replaced, self._pending_word_replaced_blocks)
            else:
                self._word_replaced_html = None
                self._pending_word_replaced_blocks = None
                self._word_replaced_ready = False
                self._word_replaced_loaded_source_path = None
                self._word_replaced_target_source_path = None
                self.word_preview_replaced.setHtml("")

            self._configure_word_scroll_sync_panels()
            if compare_enabled:
                QTimer.singleShot(0, self._sync_word_compare_scroll_from_original)

            self._refresh_workbench_context()

        except (IOError, OSError, ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "错误", f"渲染预览失败: {str(e)}")

    def _build_word_preview_documents(self):
        """构建只需首屏加载一次的 Word 预览文档。"""
        base_html = self._wrap_html_document(self._word_base_html or "")
        text_blocks = self._build_word_text_blocks()
        tagged_html = self._add_data_key_attributes(base_html, text_blocks)

        style = f"""
        <style>
            body {{ font-family: {PREVIEW_FONT_STACK}; padding: 20px; line-height: 1.6; }}
            p:empty {{ display: none; margin: 0; }}
            table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
            td, th {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
            mark.ocr-highlight {{ background-color: #ffeb3b; color: #000; display: inline; box-decoration-break: clone; -webkit-box-decoration-break: clone; }}
            mark.ocr-hit--confirmed {{ background-color: #ff9800; color: #000; display: inline; box-decoration-break: clone; -webkit-box-decoration-break: clone; }}
            mark.manual-highlight {{ background-color: #ff6b6b; color: #fff; display: inline; cursor: pointer; box-shadow: 0 0 0 1px #e03131; box-decoration-break: clone; -webkit-box-decoration-break: clone; }}
            mark.manual-highlight:hover {{ box-shadow: 0 0 0 1px #e03131, 0 0 4px rgba(225, 49, 49, 0.5); }}
            mark.replace-preview-highlight {{
                background-color: #ffd666;
                color: #2b1f00;
                border-radius: 3px;
                padding: 0 2px;
                box-decoration-break: clone;
                -webkit-box-decoration-break: clone;
                box-shadow: inset 0 -1px 0 rgba(43, 31, 0, 0.20);
            }}
        </style>
        """

        if "<head>" in tagged_html:
            tagged_html = tagged_html.replace("<head>", "<head>" + style, 1)
        else:
            tagged_html = style + tagged_html

        scroll_restore_script = self._get_word_preview_scroll_restore_script()
        document_html = self._inject_interactive_html(tagged_html, scroll_restore_script)

        self._word_tagged_html = tagged_html
        self._word_preview_document_html = document_html
        self._word_replaced_document_html = document_html
        self._word_preview_ready = False
        self._word_replaced_ready = False

    def _get_word_preview_scroll_restore_script(self):
        return '''<script>
    (function() {
        const STORAGE_KEY = 'word_preview_scroll_pos';
        let memoryScrollPos = 0;
        let syncTimeout = null;
        let syncFrame = null;
        let syncInterval = null;
        let lastNotifiedRatio = null;
        window.__wordPreviewPanelId = '';
        window.__wordScrollSyncEnabled = false;
        window.__wordScrollSyncApplying = false;

        function isLocalStorageAvailable() {
            try {
                const test = '__localStorage_test__';
                localStorage.setItem(test, test);
                localStorage.removeItem(test);
                return true;
            } catch (e) {
                return false;
            }
        }

        const useLocalStorage = isLocalStorageAvailable();

        function saveScroll() {
            const scrollY = window.pageYOffset || document.documentElement?.scrollTop || document.body?.scrollTop || 0;
            memoryScrollPos = scrollY;
            if (useLocalStorage) {
                try {
                    localStorage.setItem(STORAGE_KEY, scrollY.toString());
                } catch (e) {}
            }
        }

        function getMaxScrollY() {
            const docEl = document.documentElement;
            const body = document.body;
            const docHeight = Math.max(
                docEl ? docEl.scrollHeight : 0,
                body ? body.scrollHeight : 0
            );
            return Math.max(0, docHeight - window.innerHeight);
        }

        function getScrollRatio() {
            const scrollY = window.pageYOffset || document.documentElement?.scrollTop || document.body?.scrollTop || 0;
            const maxScrollY = getMaxScrollY();
            if (maxScrollY <= 0) {
                return 0;
            }
            return Math.max(0, Math.min(1, scrollY / maxScrollY));
        }

        function notifyScrollSync(force) {
            if (!window.__wordScrollSyncEnabled || window.__wordScrollSyncApplying) {
                return;
            }
            if (!pyBridge || !webChannelReady || typeof pyBridge.report_word_preview_scroll !== 'function') {
                return;
            }
            const ratio = getScrollRatio();
            if (!force && lastNotifiedRatio !== null && Math.abs(ratio - lastNotifiedRatio) < 0.002) {
                return;
            }
            lastNotifiedRatio = ratio;
            try {
                pyBridge.report_word_preview_scroll(window.__wordPreviewPanelId || '', ratio);
            } catch (e) {}
        }

        function refreshSyncInterval() {
            if (syncInterval) {
                clearInterval(syncInterval);
                syncInterval = null;
            }
            if (!window.__wordScrollSyncEnabled) {
                return;
            }
            syncInterval = setInterval(function() {
                notifyScrollSync(false);
            }, 80);
        }

        window.__setWordPreviewPanelId = function(panelId) {
            window.__wordPreviewPanelId = panelId || '';
        };

        window.__setWordPreviewScrollSyncEnabled = function(enabled) {
            window.__wordScrollSyncEnabled = !!enabled;
            refreshSyncInterval();
            if (window.__wordScrollSyncEnabled) {
                notifyScrollSync(true);
            }
        };

        window.__getWordPreviewScrollRatio = function() {
            return getScrollRatio();
        };

        window.__applyExternalWordScrollRatio = function(ratio) {
            const numericRatio = Number(ratio);
            if (!Number.isFinite(numericRatio)) {
                return;
            }
            const maxScrollY = getMaxScrollY();
            const targetRatio = Math.max(0, Math.min(1, numericRatio));
            const targetY = maxScrollY <= 0 ? 0 : Math.round(maxScrollY * targetRatio);
            lastNotifiedRatio = targetRatio;
            window.__wordScrollSyncApplying = true;
            window.scrollTo(0, targetY);
            setTimeout(function() {
                window.__wordScrollSyncApplying = false;
            }, 55);
        };

        function restoreScroll() {
            let savedPos = null;
            if (useLocalStorage) {
                try {
                    savedPos = localStorage.getItem(STORAGE_KEY);
                } catch (e) {}
            }
            if (!savedPos) {
                savedPos = memoryScrollPos.toString();
            }

            if (savedPos) {
                const targetY = parseInt(savedPos, 10);
                if (!isNaN(targetY) && targetY > 0) {
                    window.scrollTo(0, targetY);
                    setTimeout(function() {
                        window.scrollTo(0, targetY);
                    }, 10);
                }
            }
        }

        saveScroll();
        let scrollTimeout;
        window.addEventListener('scroll', function() {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(saveScroll, 36);
            clearTimeout(syncTimeout);
            if (syncFrame !== null) {
                cancelAnimationFrame(syncFrame);
            }
            syncFrame = requestAnimationFrame(function() {
                syncFrame = null;
                notifyScrollSync(false);
            });
            syncTimeout = setTimeout(function() {
                notifyScrollSync(false);
            }, 24);
        });
        window.addEventListener('beforeunload', saveScroll);
        document.addEventListener('visibilitychange', function() {
            if (document.hidden) {
                saveScroll();
            } else if (window.__wordScrollSyncEnabled) {
                notifyScrollSync(true);
            }
        });
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', restoreScroll);
        }
        window.addEventListener('load', restoreScroll);
        requestAnimationFrame(restoreScroll);
        refreshSyncInterval();
    })();
    </script>'''

    def _build_word_text_blocks(self):
        text_blocks = {}
        for key, data in self.word_data.items():
            text = data.get("text", "")
            if text:
                text_blocks[key] = {"text": text, "escaped": text}
        return text_blocks

    def _build_word_original_panel_updates(self):
        updates = {}
        for key, data in self.word_data.items():
            source_text = data.get("text", "")
            merged_matches = merge_word_matches_with_priority(
                source_text,
                [],
                self.replacement_text,
                manual_matches=data.get("manual", []),
                ocr_matches=data.get("ocr", [])
            )
            updates[key] = self._build_word_original_preview_fragment(key, source_text, merged_matches)
        return updates

    def _build_word_original_preview_fragment(self, key, source_text, merged_matches):
        from html import escape as html_escape

        segments = build_highlight_preview_segments(source_text, merged_matches)
        # v1.1.11: HitOverrideStore 过滤 — ignored 命中整段不渲染为 <mark>;
        # confirmed 命中打 ocr-hit--confirmed 类以便 CSS 加深背景。
        store = getattr(self, "_override_store", None)
        doc_hash = getattr(self, "_current_doc_hash", "") or ""
        parts = []
        for segment in segments:
            value = segment.get("value", "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                value = str(value)
            escaped_value = html_escape(value).replace("\n", "<br/>")

            if segment.get("type") != "highlight":
                parts.append(escaped_value)
                continue

            source = str(segment.get("source", "manual"))
            seg_start = int(segment.get("start", 0))
            seg_end = int(segment.get("end", 0))
            seg_text = str(segment.get("value", ""))

            # v1.1.11: 构造 HitRef 走 store 过滤;manual 永远保留。
            if source != "manual" and store is not None and doc_hash:
                ref = HitRef(
                    doc_hash=doc_hash,
                    location=str(key),
                    start=seg_start,
                    end=seg_end,
                    text=seg_text,
                    source=source,
                )
                if store.is_ignored(ref):
                    # 忽略命中:不渲染 <mark>,保留原文
                    parts.append(escaped_value)
                    continue
                hit_id_str = ref.hit_id
            else:
                hit_id_str = ""

            css_class = "manual-highlight" if source == "manual" else "ocr-highlight"
            if source != "manual" and store is not None and doc_hash:
                ref = HitRef(
                    doc_hash=doc_hash,
                    location=str(key),
                    start=seg_start,
                    end=seg_end,
                    text=seg_text,
                    source=source,
                )
                if store.is_confirmed(ref):
                    css_class += " ocr-hit--confirmed"
            attrs = [
                f'class="{css_class}"',
                f'data-key="{html_escape(str(key))}"',
                f'data-start="{seg_start}"',
                f'data-end="{seg_end}"',
                f'data-source="{html_escape(source)}"',
            ]
            if hit_id_str:
                attrs.append(f'data-hit-id="{html_escape(hit_id_str)}"')
            title = "手动脱敏" if source == "manual" else str(segment.get("rule_name", "")).strip() or "智能脱敏"
            if title:
                attrs.append(f'title="{html_escape(title)}"')
            parts.append(f"<mark {' '.join(attrs)}>{escaped_value}</mark>")

        return "".join(parts)

    def _build_word_replaced_panel_updates(self):
        updates = {}
        # v1.1.11: HitOverrideStore 过滤 — ignored OCR hit 不进入 merge
        # (manual 永远保留;confirm 保留)。与 _save_word / _rects_for_page 保持一致。
        store = getattr(self, "_override_store", None)
        doc_hash = getattr(self, "_current_doc_hash", "") or ""
        for key, data in self.word_data.items():
            source_text = data.get("text", "")
            raw_ocr = data.get("ocr", [])
            if store is not None and doc_hash:
                filtered_ocr = store.filtered_hits(
                    list(raw_ocr),
                    location=key,
                    doc_hash=doc_hash,
                )
            else:
                filtered_ocr = list(raw_ocr)
            merged_matches = merge_word_matches_with_priority(
                source_text,
                self.word_replace_rules,
                self.replacement_text,
                manual_matches=data.get("manual", []),
                ocr_matches=filtered_ocr
            )
            updates[key] = self._build_replaced_preview_fragment(source_text, merged_matches)
        return updates

    def _sync_word_compare_scroll(self, source_panel, ratio):
        """双栏对比模式下，同步左右预览滚动位置。"""
        if not self.word_compare_mode or self.word_compare_user_hidden:
            return
        if source_panel not in {"original", "replaced"}:
            return
        try:
            ratio_value = max(0.0, min(1.0, float(ratio)))
        except (TypeError, ValueError):
            return
        if (
            self._word_scroll_sync_pending_target == source_panel
            and self._word_scroll_sync_pending_ratio is not None
            and abs(ratio_value - float(self._word_scroll_sync_pending_ratio)) <= 0.02
        ):
            self._word_scroll_sync_pending_target = None
            self._word_scroll_sync_pending_ratio = None
            return
        if source_panel == "original":
            self._apply_word_scroll_ratio_to_panel("replaced", ratio_value)
        else:
            self._apply_word_scroll_ratio_to_panel("original", ratio_value)

    def _sync_word_compare_scroll_from_original(self):
        """用左侧原文预览的当前位置对齐右侧替换预览。"""
        if not self.word_compare_mode or self.word_compare_user_hidden:
            return
        if not self._word_preview_ready or not self._word_replaced_ready:
            return
        if not self._is_word_web_view_valid(self.word_preview):
            return
        if not self._is_word_web_view_valid(self.word_preview_replaced):
            return
        if self.word_preview.isHidden() or self.word_preview_replaced.isHidden():
            return

        generation = self._word_scroll_sync_generation
        self.word_preview.page().runJavaScript(
            "window.__getWordPreviewScrollRatio ? window.__getWordPreviewScrollRatio() : 0;",
            lambda ratio, sync_generation=generation: self._sync_word_compare_scroll_from_original_callback(ratio, sync_generation),
        )

    def _sync_word_compare_scroll_from_original_callback(self, ratio, generation):
        """仅在同步代次仍有效时，把左侧滚动位置应用到右侧。"""
        if generation != self._word_scroll_sync_generation:
            return
        self._apply_word_scroll_ratio_to_panel("replaced", ratio)

    def _poll_word_compare_scroll_sync(self):
        """轮询双栏 Word 预览滚动位置，作为联动兜底方案。"""
        if self._word_scroll_sync_polling:
            return
        if not self._word_scroll_sync_timer.isActive():
            return
        if not self.word_compare_mode or self.word_compare_user_hidden:
            return
        if not self._word_preview_ready or not self._word_replaced_ready:
            return
        if not self._is_word_web_view_valid(self.word_preview):
            return
        if not self._is_word_web_view_valid(self.word_preview_replaced):
            return
        if self.word_preview.isHidden() or self.word_preview_replaced.isHidden():
            return

        self._word_scroll_sync_polling = True
        generation = self._word_scroll_sync_generation
        self.word_preview.page().runJavaScript(
            "window.__getWordPreviewScrollRatio ? window.__getWordPreviewScrollRatio() : 0;",
            lambda ratio, sync_generation=generation: self._handle_word_scroll_sync_original_ratio(ratio, sync_generation),
        )

    def _on_word_preview_load_finished(self, ok):
        self._word_preview_ready = bool(ok)
        self._word_preview_loaded_source_path = self._word_preview_target_source_path if ok else None
        if ok and self._pending_word_preview_blocks:
            self._apply_word_panel_updates(self.word_preview, self._pending_word_preview_blocks)
        if ok:
            self._configure_word_scroll_sync_panel(self.word_preview, "original")
            self._refresh_word_scroll_sync_timer()
            QTimer.singleShot(0, self._sync_word_compare_scroll_from_original)
