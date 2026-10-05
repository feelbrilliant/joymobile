"""가짜 스마트에디터 페이지(tests/fixtures)로 자동 입력 흐름을 확인한다.

실제 네이버 화면과 구조가 다를 수 있으므로, 선택자가 맞는지는 실제 PC에서 확인해야 한다.
Playwright나 Chromium이 없으면 건너뛴다. CHROMIUM_PATH 로 브라우저 경로를 지정할 수 있다.
"""
import os
import tempfile
import unittest
from pathlib import Path

from joyblog.editor import Editor, ForbiddenClick, fill_post, load_config
from joyblog.post import parse
from joyblog.render import body_html

FIXTURES = Path(__file__).parent / "fixtures"
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")

try:
    from playwright.sync_api import sync_playwright

    HAVE_BROWSER = Path(CHROMIUM).exists()
except ImportError:
    HAVE_BROWSER = False

DRAFT = """유심 eSIM 차이, 내 휴대폰에는 어떤 게 맞을까

새 휴대폰을 사면 유심으로 할지 eSIM으로 할지 고민하게 됩니다.

## 한눈에 보는 차이

구분 | 유심 | eSIM
형태 | 끼우는 칩 | 내장 칩

- 기기 지원 여부 확인
- 상품별 제공 여부 확인
"""


def mock_config() -> dict:
    cfg = load_config()
    cfg["blog_id"] = ""
    cfg["write_url_without_id"] = (FIXTURES / "mock_write.html").resolve().as_uri()
    return cfg


@unittest.skipUnless(HAVE_BROWSER, "Playwright/Chromium 없음")
class EditorFlowTest(unittest.TestCase):
    def launcher(self, pw, cfg):
        self.browser = pw.chromium.launch(executable_path=CHROMIUM)
        self.ctx = self.browser.new_context()
        return self.ctx

    def test_fill_title_body_and_save_without_publishing(self):
        post = parse(DRAFT)
        with sync_playwright() as pw:
            ctx = self.launcher(pw, mock_config())
            page = ctx.new_page()
            ed = Editor(page, mock_config())
            ed.open()
            ed.dismiss_popups()
            self.assertTrue(ed.fill_title(post.title))
            chars = ed.fill_body(body_html(post), post.body_text())
            self.assertTrue(ed.save_draft())
            body = ed.frame.locator("body")
            self.assertEqual(body.get_attribute("data-saved"), "1")
            self.assertIsNone(body.get_attribute("data-published"))
            self.assertEqual(ed.frame.locator("#draft-popup").count(), 0)
            self.assertGreater(chars, 50)
            self.assertIn("기기 지원 여부 확인", ed.frame.locator(".se-component.se-text").inner_text())

            with self.assertRaises(ForbiddenClick):
                ed.safe_click(ed.frame.locator(".publish_btn__mock"))
            self.assertIsNone(body.get_attribute("data-published"))
            ctx.close()
            self.browser.close()

    def test_fill_post_end_to_end(self):
        post = parse(DRAFT)
        with tempfile.TemporaryDirectory() as tmp:
            result = fill_post(post.title, body_html(post), post.body_text(), Path(tmp) / "debug",
                               cfg=mock_config(), launcher=self.launcher, keep_open=False)
        self.assertTrue(result.title_ok)
        self.assertTrue(result.saved)
        self.assertGreater(result.body_chars, 50)

    def test_missing_editor_leaves_debug_files(self):
        cfg = mock_config()
        cfg["title"] = [".does-not-exist"]
        post = parse(DRAFT)
        with tempfile.TemporaryDirectory() as tmp:
            debug = Path(tmp) / "debug"
            with self.assertRaises(Exception) as caught:
                fill_post(post.title, body_html(post), post.body_text(), debug,
                          cfg=cfg, launcher=self.launcher, keep_open=False)
            self.assertIn("제목 입력칸", str(caught.exception))
            self.assertTrue((debug / "screen.png").exists())
            self.assertTrue((debug / "editor.html").exists())


if __name__ == "__main__":
    unittest.main()
