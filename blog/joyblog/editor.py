"""네이버 스마트에디터에 초안을 채워 넣는다.

- 사용자 PC의 Chrome(또는 Edge)을 전용 프로필로 띄운다. 로그인은 사람이 직접 하고, 이후엔 로그인 상태가 유지된다
- 제목 입력 → 본문 붙여넣기(서식 유지) → 임시저장까지 하고 멈춘다
- 발행 버튼은 절대 누르지 않는다. 누르려는 요소에 '발행'이 보이면 예외를 낸다
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

from .paths import BLOG_DIR

CONFIG = BLOG_DIR / "config" / "editor.json"
PROFILE_DIR = BLOG_DIR / ".browser-profile"
LOGIN_WAIT_SEC = 5 * 60
READY_WAIT_MS = 60_000


class EditorError(RuntimeError):
    pass


class ForbiddenClick(EditorError):
    pass


@dataclass
class FillResult:
    title_ok: bool
    body_chars: int
    saved: bool


def load_config(path: Path = CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_url(cfg: dict) -> str:
    blog_id = cfg.get("blog_id", "").strip()
    return cfg["write_url"].format(blog_id=blog_id) if blog_id else cfg["write_url_without_id"]


def _pause(seconds: float = 0.6) -> None:
    # 에디터가 입력을 처리할 시간을 준다
    time.sleep(seconds)


class Editor:
    def __init__(self, page, cfg: dict):
        self.page = page
        self.cfg = cfg
        self.frame = page

    # ---------- 공통 ----------
    def _first(self, key: str, scope=None, timeout_ms: int = 0):
        """설정의 후보 선택자 중 화면에 보이는 첫 요소를 찾는다."""
        scope = scope or self.frame
        deadline = time.time() + timeout_ms / 1000
        while True:
            for sel in self.cfg[key]:
                loc = scope.locator(sel)
                try:
                    count = loc.count()
                except Exception:
                    count = 0
                for i in range(count):
                    if loc.nth(i).is_visible():
                        return loc.nth(i)
            if time.time() >= deadline:
                return None
            time.sleep(0.5)

    def safe_click(self, loc) -> None:
        text = (loc.inner_text(timeout=2000) or "") + " " + (loc.get_attribute("class") or "")
        if any(w.lower() in text.lower() for w in self.cfg["forbidden_words"]):
            raise ForbiddenClick(f"발행 관련 버튼은 누르지 않습니다: {text.strip()[:40]}")
        loc.click()

    # ---------- 단계 ----------
    def open(self) -> None:
        url = write_url(self.cfg)
        self.page.goto(url, wait_until="domcontentloaded")
        if self.cfg["login_url_marker"] in self.page.url:
            print("브라우저 창에서 네이버에 로그인해 주세요. 로그인하면 자동으로 이어서 진행합니다. (최대 5분 대기)")
            deadline = time.time() + LOGIN_WAIT_SEC
            while self.cfg["login_url_marker"] in self.page.url:
                if time.time() > deadline:
                    raise EditorError("5분 안에 로그인이 끝나지 않아 멈췄습니다. 다시 실행해 주세요.")
                time.sleep(1)
            self.page.goto(url, wait_until="domcontentloaded")
        self.frame = self._find_editor_frame()

    def _find_editor_frame(self):
        deadline = time.time() + READY_WAIT_MS / 1000
        while time.time() < deadline:
            try:
                candidates = [self.page]
                for sel in self.cfg["editor_frame"]:
                    handle = self.page.query_selector(sel)
                    if handle and handle.content_frame():
                        candidates.insert(0, handle.content_frame())
                candidates += [f for f in self.page.frames if f not in candidates]
                for scope in candidates:
                    if any(scope.locator(s).count() for s in self.cfg["ready"]):
                        return scope
            except Exception:
                pass  # 페이지가 아직 이동 중이면 잠시 후 다시 찾는다
            time.sleep(1)
        raise EditorError("글쓰기 화면을 찾지 못했습니다. 네이버 화면이 바뀌었을 수 있습니다.")

    def dismiss_popups(self) -> None:
        # '작성 중인 글이 있습니다' 같은 팝업은 취소(새 글로 시작), 도움말은 닫기
        for _ in range(3):
            loc = self._first("dismiss", timeout_ms=1500)
            if not loc:
                return
            self.safe_click(loc)
            _pause()

    def fill_title(self, title: str) -> bool:
        loc = self._first("title", timeout_ms=10_000)
        if not loc:
            raise EditorError("제목 입력칸을 찾지 못했습니다.")
        loc.click()
        _pause(0.3)
        self.page.keyboard.insert_text(title)
        _pause()
        return title.replace(" ", "") in loc.inner_text().replace(" ", "")

    def _body_text_len(self) -> int:
        total = 0
        for sel in self.cfg["body"]:
            loc = self.frame.locator(sel)
            for i in range(loc.count()):
                total += len("".join((loc.nth(i).inner_text() or "").split()))
        return total

    def fill_body(self, html: str, plain: str) -> int:
        loc = self._first("body", timeout_ms=10_000)
        if not loc:
            raise EditorError("본문 입력칸을 찾지 못했습니다.")
        loc.click()
        _pause(0.3)
        before = self._body_text_len()

        # 1차: 에디터에 붙여넣기 이벤트를 직접 보낸다 (사용자 클립보드를 건드리지 않음)
        loc.evaluate(
            """(el, data) => {
                const dt = new DataTransfer();
                dt.setData('text/html', data.html);
                dt.setData('text/plain', data.plain);
                const target = document.activeElement || el;
                target.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
            }""",
            {"html": html, "plain": plain},
        )
        _pause(1.5)
        if self._body_text_len() > before + 20:
            return self._body_text_len()

        # 2차: 실제 클립보드에 넣고 Ctrl+V
        self.page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        self.frame.evaluate(
            """async (data) => {
                const item = new ClipboardItem({
                    'text/html': new Blob([data.html], {type: 'text/html'}),
                    'text/plain': new Blob([data.plain], {type: 'text/plain'}),
                });
                await navigator.clipboard.write([item]);
            }""",
            {"html": html, "plain": plain},
        )
        loc.click()
        self.page.keyboard.press("Control+V")
        _pause(2)
        after = self._body_text_len()
        if after <= before + 20:
            raise EditorError("본문을 붙여넣지 못했습니다.")
        return after

    def save_draft(self) -> bool:
        loc = self._first("save", timeout_ms=3000)
        if not loc:
            return False
        self.safe_click(loc)
        _pause(1.5)
        return True

    def debug_dump(self, folder: Path) -> Path:
        """실패했을 때 원인을 볼 수 있도록 화면과 HTML을 남긴다."""
        folder.mkdir(parents=True, exist_ok=True)
        try:
            self.page.screenshot(path=str(folder / "screen.png"), full_page=True)
        except Exception:
            pass
        try:
            (folder / "editor.html").write_text(self.frame.content(), encoding="utf-8")
        except Exception:
            pass
        return folder


def launch(playwright, cfg: dict, profile_dir: Path = PROFILE_DIR, headless: bool = False):
    """사용자 PC에 설치된 Chrome → Edge 순서로 띄운다. 로그인 상태는 profile_dir 에 남는다."""
    channels = [cfg.get("browser") or "chrome", "chrome", "msedge"]
    errors = []
    for channel in dict.fromkeys(channels):
        try:
            return playwright.chromium.launch_persistent_context(
                str(profile_dir), channel=channel, headless=headless,
                viewport=None, args=["--start-maximized"],
            )
        except Exception as e:  # 해당 브라우저가 설치되지 않은 경우 다음 후보로
            errors.append(f"{channel}: {str(e).splitlines()[0]}")
    raise EditorError("Chrome 또는 Edge를 실행하지 못했습니다.\n" + "\n".join(errors))


def fill_post(title: str, body_html: str, body_plain: str, debug_dir: Path,
              cfg: dict | None = None, launcher=None, keep_open: bool = True) -> FillResult:
    """글쓰기 화면을 열고 제목·본문을 채운 뒤 임시저장한다. 발행은 사람이 한다."""
    from playwright.sync_api import sync_playwright

    cfg = cfg or load_config()
    with sync_playwright() as pw:
        ctx = (launcher or launch)(pw, cfg)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        editor = Editor(page, cfg)
        try:
            editor.open()
            editor.dismiss_popups()
            title_ok = editor.fill_title(title)
            body_chars = editor.fill_body(body_html, body_plain)
            saved = editor.save_draft()
        except Exception as e:
            where = editor.debug_dump(debug_dir)
            raise EditorError(f"{e}\n화면 기록을 남겼습니다: {where}") from e

        result = FillResult(title_ok, body_chars, saved)
        if keep_open:
            print("\n스마트에디터에 글을 채웠습니다. 브라우저에서 확인하고 직접 '발행'을 눌러 주세요.")
            print("끝나면 브라우저 창을 닫으세요.")
            try:
                ctx.wait_for_event("close", timeout=0)
            except Exception:
                pass
        else:
            ctx.close()
        return result
