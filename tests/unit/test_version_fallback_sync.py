"""P0-5 回归: 版本号 fallback 必须与 version.txt 同步。

背景:
    version.txt 是版本单一来源, 但代码里有 3 处硬编码 fallback:
      - main.py                                -> "1.1.12"
      - secureredact/__init__.py               -> "1.1.12"
      - secureredact/ui/main_window/window.py -> "1.1.12"
    而 version.txt 已是 "1.1.13"。version.txt 缺失(例如打包路径异常)时,
    UI 会显示旧版本号, 与 EXE 属性 / About 窗口不一致。

本文件锁定三处 fallback 与 version.txt 的一致性, 防止再次漂移。
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = REPO_ROOT / "version.txt"

# 允许出现版本 fallback 字面量的文件(相对仓库根)
FALLBACK_SITES = (
    "main.py",
    "secureredact/__init__.py",
    "secureredact/ui/main_window/window.py",
)


def _read_version_txt() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def _extract_fallback_literals(text: str):
    """扫描 except OSError 之后紧跟的 return "<字面量>"。

    只做字符串扫描, 不用正则, 避免引号转义在跨工具传递时出错。
    """
    found = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "except OSError:" not in line:
            continue
        for j in range(i + 1, min(i + 8, len(lines))):
            stripped = lines[j].strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("return"):
                for quote in (chr(34), chr(39)):
                    if quote in stripped:
                        start = stripped.index(quote) + 1
                        end = stripped.find(quote, start)
                        if end > start:
                            found.append(stripped[start:end])
            break
    return found


class TestVersionFallbackSync(unittest.TestCase):

    def test_version_txt_is_readable(self):
        self.assertTrue(VERSION_FILE.exists(), f"缺少版本单一来源: {VERSION_FILE}")
        self.assertTrue(_read_version_txt(), "version.txt 内容为空")

    def test_fallback_literals_match_version_txt(self):
        """三处 fallback 字面量必须等于 version.txt 的内容。"""
        expected = _read_version_txt()
        offenders = []

        for rel in FALLBACK_SITES:
            path = REPO_ROOT / rel
            self.assertTrue(path.exists(), f"缺少文件: {rel}")
            text = path.read_text(encoding="utf-8")
            for found in _extract_fallback_literals(text):
                if found != expected:
                    offenders.append(f"{rel}: fallback={found} != version.txt={expected}")

        self.assertEqual(
            offenders,
            [],
            "版本 fallback 与 version.txt 漂移: " + "; ".join(offenders),
        )

    def test_each_fallback_site_has_exactly_one_fallback(self):
        """每个站点必须恰好有一个 fallback(防止新增站点漏改)。"""
        for rel in FALLBACK_SITES:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            literals = _extract_fallback_literals(text)
            self.assertEqual(
                len(literals),
                1,
                f"{rel} 应恰好有 1 个版本 fallback, 实际 {literals}",
            )

    def test_read_app_version_matches_version_txt(self):
        """main.read_app_version() 必须等于 version.txt。"""
        from main import read_app_version

        self.assertEqual(read_app_version(), _read_version_txt())

    def test_package_version_matches_version_txt(self):
        """secureredact.__version__ 必须等于 version.txt。"""
        import secureredact

        self.assertEqual(secureredact.__version__, _read_version_txt())

    def test_no_stale_112_literal_in_fallback_sites(self):
        """三处 fallback 站点里不应再出现 1.1.12 字面量。"""
        offenders = []
        for rel in FALLBACK_SITES:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            for marker in ("return " + chr(34) + "1.1.12" + chr(34),
                           "return " + chr(39) + "1.1.12" + chr(39)):
                if marker in text:
                    offenders.append(f"{rel}: {marker}")
        self.assertEqual(offenders, [], f"仍存在旧 fallback: {offenders}")


if __name__ == "__main__":
    unittest.main()