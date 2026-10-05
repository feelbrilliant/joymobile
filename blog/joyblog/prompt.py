"""프롬프트 파일에 요금제 정보와 입력값을 채워 넣는다."""
import json

from .paths import PLANS, SYSTEM_PROMPT, USER_PROMPT
from .topics import Topic


def load_plans() -> dict:
    return json.loads(PLANS.read_text(encoding="utf-8"))


def render_plans(plans: dict) -> str:
    lines = [f"[{plans['carrier']} {plans['product']} 요금제]", ""]
    for p in plans["plans"]:
        lines.append(f"- {p['name']}" + (" (주력)" if p.get("featured") else ""))
        lines.append(f"  월 {p['monthly_fee_krw']:,}원")
        if p["voice"] == p["sms"] == "기본제공":
            lines.append("  음성·문자 기본제공")
        else:
            lines.append(f"  음성 {p['voice']}")
            lines.append(f"  문자 {p['sms']}")
        lines.append(f"  데이터 {p['data']}")
        if p.get("after_data_limit"):
            lines.append(f"  데이터 소진 후 {p['after_data_limit']}")
        if p.get("video_extra_call"):
            lines.append(f"  영상/부가통화 {p['video_extra_call']}")
        if p.get("note"):
            lines.append(f"  참고: {p['note']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def system_prompt(plans: dict) -> str:
    return SYSTEM_PROMPT.read_text(encoding="utf-8").replace("{{요금제_정보}}", render_plans(plans))


def user_prompt(topic: Topic) -> str:
    values = {
        "{{키워드}}": topic.keyword,
        "{{제목}}": topic.title,
        "{{권장_유형}}": topic.post_type or "자유 선택",
        "{{대상_고객}}": topic.audience or "검색 의도에 맞게 선택",
    }
    text = USER_PROMPT.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace(key, value)
    return text
