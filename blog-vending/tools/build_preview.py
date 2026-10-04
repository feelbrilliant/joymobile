"""검수용 미리보기 HTML 생성. 사용법: python build_preview.py <포스트 폴더>

<포스트 폴더>/preview.html 을 만든다. 네이버 모바일 화면 폭(약 400px)으로
글과 이미지를 실제 업로드 순서대로 보여주고, 사람이 볼 검수 체크리스트를 붙인다.
"""
from __future__ import annotations

import html
import os
import sys

from post_lib import load_post

CHECKLIST = [
    "이미지마다 캐릭터 팔 2 · 손 2 · 다리 2 · 발 2, 팔이 본체 양옆에서 나오는지",
    "캐릭터 얼굴 화면 비율 · 색(#7CAEFD) · 표정이 원본과 같은지",
    "이미지 속 한국어 오타, 숫자(개통시간 등)가 본문과 같은지",
    "하단 브랜드 문구: 조이모바일.com / 개통센터 대표번호 / 010-4486-2532",
    "이미지 순서가 소제목과 맞는지, 잘린 글씨 · 발이 없는지",
    "본문에 단정 표현(무조건 · 100% · 누구나)이 없는지",
]


def main(folder: str) -> None:
    post = load_post(folder)
    out = post.folder / "preview.html"
    parts: list[str] = []
    for kind, val in post.blocks():
        if kind == "image":
            rel = os.path.relpath(val, post.folder)
            parts.append(f'<figure><img src="{html.escape(rel)}" alt=""><figcaption>{html.escape(os.path.basename(val))}</figcaption></figure>')
        elif kind == "divider":
            parts.append("<hr>")
        else:
            parts.append("<p>" + html.escape(val).replace("\n", "<br>") + "</p>")

    missing = ""
    if not post.images:
        missing = f'<div class="warn">images/ 폴더가 비어 있어요. 프롬프트 {len(post.prompt_titles)}개에 맞춰 01.png부터 넣어주세요.</div>'

    checklist = "".join(f"<li><label><input type=checkbox> {html.escape(c)}</label></li>" for c in CHECKLIST)
    doc = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(post.title)}</title>
<style>
:root{{--bg:#f4f5f7;--paper:#fff;--ink:#222;--muted:#888;--warn:#fff4d6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--paper:#22252b;--ink:#eee;--muted:#999;--warn:#4a3d10}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Noto Sans KR",sans-serif}}
main{{max-width:420px;margin:0 auto;background:var(--paper);padding:24px 16px 64px}}
h1{{font-size:20px;line-height:1.5}}
p{{font-size:15px;line-height:1.9;margin:0 0 18px}}
hr{{border:0;border-top:1px dashed var(--muted);margin:28px 0}}
figure{{margin:0 0 18px}} img{{width:100%;display:block;border-radius:6px}}
figcaption{{font-size:11px;color:var(--muted);text-align:right}}
.warn{{background:var(--warn);padding:12px;border-radius:6px;margin-bottom:16px;font-size:14px}}
aside{{max-width:420px;margin:16px auto;padding:16px;background:var(--paper);font-size:14px}}
aside li{{margin:6px 0;list-style:none}}
</style></head><body>
<aside><b>사람 검수 체크리스트</b><ul>{checklist}</ul></aside>
<main>{missing}<h1>{html.escape(post.title)}</h1>{''.join(parts)}</main>
</body></html>"""
    out.write_text(doc, encoding="utf-8")
    print(f"미리보기: {out}  (이미지 {len(post.images)}장)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
