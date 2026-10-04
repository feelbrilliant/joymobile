"""포스트 자동 점검. 사용법: python check_post.py <포스트 폴더>

점검 항목
- 근거 없는 단정·순위 표현 (이관 문서 5번)
- 자주 나온 오타 (본인인종 등)
- 브랜드 하단 문구가 프롬프트에 정확히 들어갔는지
- 본문과 프롬프트의 시간 표기(08:00 ~ 21:50 등)가 서로 같은지
- 프롬프트 수와 이미지 수, 이미지 수와 섹션 수

ERROR가 하나라도 있으면 종료 코드 1.
"""
from __future__ import annotations

import re
import sys

from post_lib import load_post

BANNED = [
    "무조건 개통", "무조건 가능", "100%", "승인 보장", "누구나 가능", "누구나 개통",
    "모든 미납", "모든 휴대폰", "모든 본인인증", "당일 개통 보장", "당일개통 보장",
    "BEST PICK", "가장 많이 선택", "업계 최저", "최저가", "최고의",
]
TYPOS = ["본인인종", "조이모바일 .com", "조이 모바일"]
FOOTER = ["조이모바일.com", "개통센터 대표번호 / 010-4486-2532"]
TIME_RE = re.compile(r"\d{2}:\d{2}\s*~\s*\d{2}:\d{2}")
# 프롬프트 안의 금지 목록 문장은 검사 대상에서 뺀다
PROMPT_BAN_LINE = re.compile(r"금지|단정 표현|넣지 말 것")


def norm_time(s: str) -> str:
    return re.sub(r"\s+", "", s)


def main(folder: str) -> int:
    post = load_post(folder)
    body = post.title + "\n" + "\n".join(post.sections)
    prompt_lines = [l for l in post.prompt_text.splitlines() if not PROMPT_BAN_LINE.search(l)]
    prompt = "\n".join(prompt_lines)
    errors: list[str] = []
    warns: list[str] = []

    for word in BANNED:
        if word in body:
            errors.append(f"본문에 단정·순위 표현: '{word}'")
        if word in prompt:
            errors.append(f"프롬프트에 단정·순위 표현: '{word}'")
    for word in TYPOS:
        if word in body or word in prompt:
            errors.append(f"오타: '{word}'")

    if "조이모바일.com" not in body:
        warns.append("본문에 조이모바일.com 안내가 없음")
    if post.prompt_text:
        for f in FOOTER:
            if f not in prompt:
                errors.append(f"프롬프트에 하단 브랜드 문구 없음/불일치: '{f}'")
        body_times = {norm_time(t) for t in TIME_RE.findall(body)}
        prompt_times = {norm_time(t) for t in TIME_RE.findall(post.prompt_text)}
        if prompt_times - body_times:
            errors.append(f"본문에 없는 시간 표기가 프롬프트에 있음: {sorted(prompt_times - body_times)}")
    else:
        warns.append("이미지프롬프트.md 없음")

    n_prompt, n_img, n_sec = len(post.prompt_titles), len(post.images), len(post.sections)
    if n_img == 0:
        warns.append(f"images/ 가 비어 있음 (프롬프트 {n_prompt}개)")
    elif n_prompt and n_img != n_prompt:
        errors.append(f"이미지 {n_img}장 ≠ 프롬프트 {n_prompt}개")
    if n_img > n_sec:
        errors.append(f"이미지 {n_img}장이 섹션 {n_sec}개보다 많음")

    print(f"[{post.folder.name}] 제목: {post.title}")
    print(f"섹션 {n_sec} / 프롬프트 {n_prompt} / 이미지 {n_img}")
    for w in warns:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    if not errors:
        print("OK   자동 점검 통과 (사람 검수는 별도)")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
