"""네이버 블로그 임시저장 자동 입력 (사용자 PC에서 실행).

사용법
    python naver_draft.py <포스트 폴더> --blog-id 내블로그아이디
    python naver_draft.py <포스트 폴더> --dry-run      # 입력 순서만 출력
    python naver_draft.py <포스트 폴더> --blog-id ID --no-save   # 입력만 하고 저장 버튼은 누르지 않음

동작
1. 이 PC 전용 크롬 프로필(~/.joymobile_naver_profile)로 브라우저를 연다.
   처음 한 번은 열린 창에서 직접 네이버에 로그인한다. 비밀번호는 스크립트가 다루지 않는다.
2. 글쓰기 화면에서 제목 → (이미지 → 문단들 → 구분선) 순서로 입력한다.
3. '저장'(임시저장) 버튼만 누른다. '발행' 버튼은 절대 누르지 않는다.
4. 브라우저를 열어둔 채 대기한다. 직접 검수 후 발행하고 Enter를 누르면 종료.

주의
- 네이버 스마트에디터 화면 구조가 바뀌면 SELECTORS 값을 고쳐야 한다.
- 이 스크립트는 클라우드 환경에서 네이버 접속이 막혀 실제 화면으로 시험하지 못했다.
  처음에는 --no-save 로 돌려 입력 결과를 눈으로 확인할 것.
- 자동 입력은 네이버 운영정책상 제재 위험이 있으므로 한 번에 한 글, 사람 검수 후 발행만 한다.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from post_lib import load_post

WRITE_URL = "https://blog.naver.com/{blog_id}/postwrite"
PROFILE_DIR = Path.home() / ".joymobile_naver_profile"

# 스마트에디터 ONE 요소. 화면이 바뀌면 여기만 고친다.
SELECTORS = {
    "resume_popup_cancel": ".se-popup-button-cancel",   # '작성 중인 글이 있습니다' → 취소
    "help_close": ".se-help-panel-close-button",
    "title": ".se-documentTitle .se-text-paragraph",
    "body_paragraph": ".se-main-container .se-text-paragraph",
    "image_button": "button.se-image-toolbar-button",
    "save_button_text": "저장",                          # 임시저장 버튼 글자
}
TYPING_DELAY = 0.15  # 블록 사이 대기(초). 너무 빠르면 에디터가 입력을 놓친다.


def focus_end(page) -> None:
    page.locator(SELECTORS["body_paragraph"]).last.click()
    page.keyboard.press("Control+End")


def type_paragraph(page, text: str) -> None:
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i:
            page.keyboard.press("Enter")
        page.keyboard.insert_text(line)
    # 예문처럼 문단 사이 빈 줄 하나
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")


def upload_image(page, path: str) -> None:
    with page.expect_file_chooser() as fc:
        page.locator(SELECTORS["image_button"]).first.click()
    fc.value.set_files(path)
    # 업로드 완료 대기: 이미지 컴포넌트 수가 늘어날 때까지
    page.wait_for_timeout(2500)
    focus_end(page)


def dismiss_popups(page) -> None:
    for key in ("resume_popup_cancel", "help_close"):
        loc = page.locator(SELECTORS[key])
        try:
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                page.wait_for_timeout(500)
        except Exception:
            pass


def run(folder: str, blog_id: str, save: bool) -> None:
    from playwright.sync_api import sync_playwright

    post = load_post(folder)
    blocks = post.blocks()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False, channel="chrome", viewport={"width": 1400, "height": 900}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(WRITE_URL.format(blog_id=blog_id))

        if "nid.naver.com" in page.url:
            print("열린 창에서 네이버에 로그인해주세요. (최대 5분 대기)")
            page.wait_for_url("**/postwrite**", timeout=300_000)

        page.wait_for_selector(SELECTORS["title"], timeout=60_000)
        page.wait_for_timeout(1500)
        dismiss_popups(page)

        page.locator(SELECTORS["title"]).first.click()
        page.keyboard.insert_text(post.title)
        focus_end(page)

        for i, (kind, val) in enumerate(blocks, 1):
            print(f"[{i}/{len(blocks)}] {kind} {Path(val).name if kind == 'image' else val[:20]}")
            if kind == "image":
                upload_image(page, val)
            elif kind == "divider":
                type_paragraph(page, "-----")
            else:
                type_paragraph(page, val)
            time.sleep(TYPING_DELAY)

        if save:
            page.get_by_role("button", name=SELECTORS["save_button_text"], exact=True).first.click()
            page.wait_for_timeout(2000)
            print("임시저장 버튼을 눌렀습니다. 발행은 하지 않았습니다.")
        else:
            print("--no-save: 입력만 하고 저장하지 않았습니다.")

        input("브라우저에서 검수를 마치면 Enter를 눌러 종료하세요...")
        ctx.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--blog-id")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()

    post = load_post(a.folder)
    if a.dry_run:
        print("제목:", post.title)
        for kind, val in post.blocks():
            print(f"{kind:8} {Path(val).name if kind == 'image' else val.replace(chr(10), ' / ')[:60]}")
        return
    if not a.blog_id:
        sys.exit("--blog-id 가 필요합니다")
    if not post.images:
        sys.exit("images/ 폴더가 비어 있습니다. 이미지를 먼저 넣어주세요.")
    run(a.folder, a.blog_id, save=not a.no_save)


if __name__ == "__main__":
    main()
