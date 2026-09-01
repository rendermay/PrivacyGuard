"""
集中所有 MainWindow 用到的 setObjectName 字面量(PR-B2.0 引入)。

来源:`main.py` 中 97 个 `setObjectName("xxx")` 调用收集。
目的:跨模块引用安全(任何 setStyleSheet / findChild / 测试用例都引用同一常量)。

约定:
- 字符串常量全大写 + 下划线,值保持原 camelCase 不变(Qt 选择器语法兼容)。
- 按 widget 用途分组(主窗口 / 工具栏 / 工作台 / 工作区 / 路由卡 / 设置面板 / 批量 / 合并 / Word 双栏 / 进度)。
- 不再使用 `setObjectName("xxx")` 字面量 — 一律引用本模块常量。
- 主样式选择器保留在 .qss / setStyleSheet 内,本文件只管 setObjectName 调用点。

v1.1.13 基线(97 个),后续 PR-B3/B4 拆分 SettingsDialog / 对话框时按需扩充。
"""


# === 主窗口 ===
APP_ROOT = "appRoot"
WORKBENCH_PANEL = "workbenchPanel"
WORKBENCH_TITLE = "workbenchTitle"
WORKBENCH_SUBTITLE = "workbenchSubtitle"
WORKBENCH_FOCUS = "workbenchFocus"
WORKBENCH_HINT_TAG = "workbenchHintTag"
CONTEXT_MESSAGE = "contextMessage"
WORKFLOW_STEP = "workflowStep"

# === 工具栏 ===
TOOLBAR_ROOT = "toolbarRoot"
TOOLBAR_META = "toolbarMeta"
TOOLBAR_DIVIDER = "toolbarDivider"
TOOLBAR_MORE_BUTTON = "toolbarMoreButton"
TOOLBAR_TOGGLE_BUTTON = "toolbarToggleButton"

# === 工作区容器(主界面) ===
WORKSPACE_CARD = "workspaceCard"
WORKSPACE_TITLE = "workspaceTitle"
WORKSPACE_SUBTITLE = "workspaceSubtitle"
WORKSPACE_HINT = "workspaceHint"
PDF_PAGE_CANVAS = "pdfPageCanvas"
PREVIEW_STAGE = "previewStage"
PREVIEW_WORKSPACE_CARD = "previewWorkspaceCard"
WORD_PREVIEW_SHELL = "wordPreviewShell"
MERGE_WORKSPACE_CARD = "mergeWorkspaceCard"

# === 路由卡(主页引导卡) ===
ROUTE_CARD = "routeCard"
ROUTE_CARD_ACCENT = "routeCardAccent"
ROUTE_CARD_META = "routeCardMeta"
ROUTE_CARD_TEXT = "routeCardText"
ROUTE_CARD_TITLE = "routeCardTitle"

# === 空闲页(idle) ===
IDLE_ACTION_PANEL = "idleActionPanel"
IDLE_DROP_HINT = "idleDropHint"
IDLE_FLOW_PANEL = "idleFlowPanel"
IDLE_FLOW_TITLE = "idleFlowTitle"
IDLE_HERO_BADGE = "idleHeroBadge"
IDLE_HERO_PANEL = "idleHeroPanel"
IDLE_PRIMARY_ACTION_BUTTON = "idlePrimaryActionButton"
IDLE_SECTION_HINT = "idleSectionHint"
IDLE_SECTION_LABEL = "idleSectionLabel"
IDLE_SECTION_PANEL = "idleSectionPanel"
IDLE_START_CARD = "idleStartCard"
IDLE_START_TEXT = "idleStartText"
IDLE_START_TITLE = "idleStartTitle"

# === 批量 Word 替换 ===
BATCH_WORKSPACE_CARD = "batchWorkspaceCard"
BATCH_DETAIL_SECTION = "batchDetailSection"
BATCH_TITLE = "batchTitle"
BATCH_SUBTITLE = "batchSubtitle"
BATCH_META = "batchMeta"
BATCH_CURRENT_FILE = "batchCurrentFile"
BATCH_STEP_CARD = "batchStepCard"
BATCH_STEP_TITLE = "batchStepTitle"
BATCH_STEP_NOTE = "batchStepNote"
BATCH_METRIC_CARD = "batchMetricCard"
BATCH_METRIC_TITLE = "batchMetricTitle"
BATCH_METRIC_NOTE = "batchMetricNote"
BATCH_METRIC_VALUE = "batchMetricValue"
BATCH_STAGE_BADGE = "batchStageBadge"
BATCH_LOG_HINT = "batchLogHint"
BATCH_SECTION_LABEL = "batchSectionLabel"
BATCH_RESULT_META = "batchResultMeta"
BATCH_RESULT_TABLE = "batchResultTable"
BATCH_LOG_LIST = "batchLogList"
BATCH_SUMMARY_BROWSER = "batchSummaryBrowser"
BATCH_FILTER_BUTTON = "batchFilterButton"

# === 设置面板 ===
SETTINGS_HERO = "settingsHero"
SETTINGS_HERO_TAG = "settingsHeroTag"
SETTINGS_OVERVIEW = "settingsOverview"
SETTINGS_OVERVIEW_TITLE = "settingsOverviewTitle"
SETTINGS_OVERVIEW_TEXT = "settingsOverviewText"
SETTINGS_TITLE = "settingsTitle"
SETTINGS_SUBTITLE = "settingsSubtitle"
SETTINGS_HINT = "settingsHint"
SETTINGS_NAV = "settingsNav"
SETTINGS_SECTION_CARD = "settingsSectionCard"
SETTINGS_SECTION_HEADER = "settingsSectionHeader"
SETTINGS_SECTION_TITLE = "settingsSectionTitle"
SETTINGS_SECTION_SUMMARY = "settingsSectionSummary"
SETTINGS_SECTION_LEAD = "settingsSectionLead"
SETTINGS_FIELD_CARD = "settingsFieldCard"
SETTINGS_FIELD_TITLE = "settingsFieldTitle"
SETTINGS_FIELD_LABEL = "settingsFieldLabel"
SETTINGS_FIELD_NOTE = "settingsFieldNote"
SETTINGS_FIELD_DIVIDER = "settingsFieldDivider"
SETTINGS_METRIC_CARD = "settingsMetricCard"
SETTINGS_METRIC_LABEL = "settingsMetricLabel"
SETTINGS_METRIC_VALUE = "settingsMetricValue"
SETTINGS_INLINE_BUTTON = "settingsInlineButton"
SETTINGS_INLINE_CHECKBOX = "settingsInlineCheckbox"
SETTINGS_PRIMARY_BUTTON = "settingsPrimaryButton"
SETTINGS_SECONDARY_BUTTON = "settingsSecondaryButton"
SETTINGS_QUICK_JUMP_BUTTON = "settingsQuickJumpButton"
SETTINGS_ACTION_HINT = "settingsActionHint"
SETTINGS_SIDEBAR = "settingsSidebar"
SETTINGS_SIDEBAR_NOTE = "settingsSidebarNote"
SETTINGS_SIDEBAR_STATUS = "settingsSidebarStatus"
SETTINGS_SIDEBAR_SUBTLE = "settingsSidebarSubtle"
SETTINGS_SIDEBAR_META_CARD = "settingsSidebarMetaCard"
SETTINGS_FOOTER = "settingsFooter"
SETTINGS_FOOTER_NOTE = "settingsFooterNote"

# === Word 双栏预览 ===
WORD_COMPARE_HEADER = "wordCompareHeader"
WORD_COMPARE_LABEL = "wordCompareLabel"


__all__ = [
    # 主窗口
    "APP_ROOT", "WORKBENCH_PANEL", "WORKBENCH_TITLE", "WORKBENCH_SUBTITLE",
    "WORKBENCH_FOCUS", "WORKBENCH_HINT_TAG", "CONTEXT_MESSAGE", "WORKFLOW_STEP",
    # 工具栏
    "TOOLBAR_ROOT", "TOOLBAR_META", "TOOLBAR_DIVIDER",
    "TOOLBAR_MORE_BUTTON", "TOOLBAR_TOGGLE_BUTTON",
    # 工作区
    "WORKSPACE_CARD", "WORKSPACE_TITLE", "WORKSPACE_SUBTITLE", "WORKSPACE_HINT",
    "PDF_PAGE_CANVAS", "PREVIEW_STAGE", "PREVIEW_WORKSPACE_CARD",
    "WORD_PREVIEW_SHELL", "MERGE_WORKSPACE_CARD",
    # 路由卡
    "ROUTE_CARD", "ROUTE_CARD_ACCENT", "ROUTE_CARD_META",
    "ROUTE_CARD_TEXT", "ROUTE_CARD_TITLE",
    # idle
    "IDLE_ACTION_PANEL", "IDLE_DROP_HINT", "IDLE_FLOW_PANEL", "IDLE_FLOW_TITLE",
    "IDLE_HERO_BADGE", "IDLE_HERO_PANEL", "IDLE_PRIMARY_ACTION_BUTTON",
    "IDLE_SECTION_HINT", "IDLE_SECTION_LABEL", "IDLE_SECTION_PANEL",
    "IDLE_START_CARD", "IDLE_START_TEXT", "IDLE_START_TITLE",
    # 批量
    "BATCH_WORKSPACE_CARD", "BATCH_DETAIL_SECTION", "BATCH_TITLE",
    "BATCH_SUBTITLE", "BATCH_META", "BATCH_CURRENT_FILE",
    "BATCH_STEP_CARD", "BATCH_STEP_TITLE", "BATCH_STEP_NOTE",
    "BATCH_METRIC_CARD", "BATCH_METRIC_TITLE", "BATCH_METRIC_NOTE",
    "BATCH_METRIC_VALUE", "BATCH_STAGE_BADGE", "BATCH_LOG_HINT",
    "BATCH_SECTION_LABEL", "BATCH_RESULT_META", "BATCH_RESULT_TABLE",
    "BATCH_LOG_LIST", "BATCH_SUMMARY_BROWSER", "BATCH_FILTER_BUTTON",
    # 设置
    "SETTINGS_HERO", "SETTINGS_HERO_TAG", "SETTINGS_OVERVIEW",
    "SETTINGS_OVERVIEW_TITLE", "SETTINGS_OVERVIEW_TEXT",
    "SETTINGS_TITLE", "SETTINGS_SUBTITLE", "SETTINGS_HINT",
    "SETTINGS_NAV", "SETTINGS_SECTION_CARD", "SETTINGS_SECTION_HEADER",
    "SETTINGS_SECTION_TITLE", "SETTINGS_SECTION_SUMMARY",
    "SETTINGS_SECTION_LEAD", "SETTINGS_FIELD_CARD",
    "SETTINGS_FIELD_TITLE", "SETTINGS_FIELD_LABEL", "SETTINGS_FIELD_NOTE",
    "SETTINGS_FIELD_DIVIDER", "SETTINGS_METRIC_CARD",
    "SETTINGS_METRIC_LABEL", "SETTINGS_METRIC_VALUE",
    "SETTINGS_INLINE_BUTTON", "SETTINGS_INLINE_CHECKBOX",
    "SETTINGS_PRIMARY_BUTTON", "SETTINGS_SECONDARY_BUTTON",
    "SETTINGS_QUICK_JUMP_BUTTON", "SETTINGS_ACTION_HINT",
    "SETTINGS_SIDEBAR", "SETTINGS_SIDEBAR_NOTE",
    "SETTINGS_SIDEBAR_STATUS", "SETTINGS_SIDEBAR_SUBTLE",
    "SETTINGS_SIDEBAR_META_CARD", "SETTINGS_FOOTER", "SETTINGS_FOOTER_NOTE",
    # Word
    "WORD_COMPARE_HEADER", "WORD_COMPARE_LABEL",
]