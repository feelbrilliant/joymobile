"""rules.json 과 plans.json 기준으로 초안을 자동 검수한다.

error: 발행하면 안 되는 문제 (자동 고쳐 쓰기 대상)
warning: 사람이 읽어 보고 판단할 문제
"""
import json
import re
from dataclasses import dataclass, field

from .paths import RULES
from .post import Post, strip_marks

PRICE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{4,})\s*원")
DATA = re.compile(r"(\d+(?:\.\d+)?)\s*(GB|MB)(?![a-z])", re.IGNORECASE)
SPEED = re.compile(r"(\d+(?:\.\d+)?)\s*Mbps", re.IGNORECASE)
SENTENCE_END = re.compile(r"([가-힣]{1,3})[.?!…]*\s*$")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings, "stats": self.stats}


def load_rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def count_keyword(text: str, keyword: str) -> int:
    """띄어쓰기 차이는 무시하고 키워드가 나온 횟수를 센다."""
    squashed = re.sub(r"\s+", "", text)
    key = re.sub(r"\s+", "", keyword)
    return squashed.count(key) if key else 0


def _norm_data(value: str, unit: str) -> str:
    return f"{float(value):g}{unit.upper()}"


def _plan_facts(plan: dict) -> dict:
    data = {_norm_data(v, u) for v, u in DATA.findall(plan["data"])}
    speeds = {f"{float(v):g}" for v in SPEED.findall(plan.get("after_data_limit") or "")}
    return {"fee": plan["monthly_fee_krw"], "data": data, "speeds": speeds}


def _plan_pattern(plan: dict) -> re.Pattern:
    name = re.escape(plan["name"]).replace(r"\ ", r"\s*")
    if plan["name"] == "비디오":
        # '비디오 시청' 같은 일반 단어와 구분: 요금제를 가리킬 때만
        return re.compile(r"비디오\s*요금제|^\s*\|?\s*비디오\s*\|")
    return re.compile(name)


def check_plans(post: Post, plans: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    facts = {p["name"]: _plan_facts(p) for p in plans["plans"]}
    patterns = {p["name"]: _plan_pattern(p) for p in plans["plans"]}
    all_fees = {f["fee"] for f in facts.values()}

    # 표는 행 단위로 본다. 한 행에 요금제 이름이 하나면 그 행의 숫자는 그 요금제 것
    lines: list[str] = []
    for b in post.blocks:
        if b.kind in ("heading", "paragraph"):
            lines.extend(b.lines)
        elif b.kind == "table":
            lines.extend("| " + " | ".join(r) + " |" for r in b.rows)

    seen_prices = set()
    for line in lines:
        text = strip_marks(line)
        named = [n for n, pat in patterns.items() if pat.search(text)]
        prices = [int(p.replace(",", "")) for p in PRICE.findall(text)]
        seen_prices.update(prices)
        if len(named) != 1:
            continue
        name, f = named[0], facts[named[0]]
        for price in prices:
            if price != f["fee"]:
                errors.append(f"'{name}' 요금이 다릅니다: 본문 {price:,}원, 기준 {f['fee']:,}원 → \"{text[:60]}\"")
        for value, unit in DATA.findall(text):
            amount = _norm_data(value, unit)
            if f["data"] and amount not in f["data"]:
                errors.append(f"'{name}' 데이터 제공량이 다릅니다: 본문 {amount}, 기준 {plans_data(name, plans)} → \"{text[:60]}\"")
        for value in SPEED.findall(text):
            if f["speeds"] and f"{float(value):g}" not in f["speeds"]:
                errors.append(f"'{name}' 소진 후 속도가 다릅니다: 본문 {value}Mbps → \"{text[:60]}\"")

    unknown = sorted(p for p in seen_prices if p not in all_fees)
    if unknown:
        warnings.append(
            "요금제 목록에 없는 금액이 나옵니다: " + ", ".join(f"{p:,}원" for p in unknown) + " (근거가 있는 금액인지 확인)"
        )
    return errors, warnings


def plans_data(name: str, plans: dict) -> str:
    return next(p["data"] for p in plans["plans"] if p["name"] == name)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.?!])\s+|\n+", text)
    return [p.strip() for p in parts if re.search(r"[가-힣]", p or "")]


def _ending(sentence: str) -> str | None:
    m = SENTENCE_END.search(sentence)
    return m.group(1) if m else None


def check(post: Post, keyword: str, title: str, plans: dict, rules: dict | None = None) -> Report:
    rules = rules or load_rules()
    report = Report()
    body = post.body_text()
    full = post.title + "\n" + body

    # 제목
    if post.title != title:
        report.errors.append(f"제목이 입력값과 다릅니다. 입력: \"{title}\" / 출력: \"{post.title}\"")

    # 분량
    chars = len(re.sub(r"\s+", "", body))
    report.stats["본문_글자수_공백제외"] = chars
    if chars < rules["min_chars_without_spaces"]:
        report.errors.append(f"본문이 {chars:,}자로 기준({rules['min_chars_without_spaces']:,}자)보다 짧습니다.")

    # 키워드
    kw = count_keyword(full, keyword)
    report.stats["키워드_횟수"] = kw
    lo, hi = rules["keyword_count"]["min"], rules["keyword_count"]["max"]
    if not lo <= kw <= hi:
        report.warnings.append(f"메인 키워드 '{keyword}'가 {kw}회 나옵니다 (권장 {lo}~{hi}회).")

    # 구조
    headings = [b for b in post.blocks if b.kind == "heading"]
    report.stats["소제목_수"] = len(headings)
    report.stats["표_수"] = sum(1 for b in post.blocks if b.kind == "table")
    if not headings:
        report.warnings.append("소제목(## )이 하나도 없습니다.")
    long_paras = [b for b in post.blocks if b.kind == "paragraph" and len(_sentences(" ".join(b.lines))) > 5]
    if long_paras:
        report.warnings.append(f"5문장이 넘는 긴 문단이 {len(long_paras)}개 있습니다 (모바일 가독성).")

    # 금지 표현
    for phrase in rules["banned_ad_phrases"]:
        if phrase in full:
            report.errors.append(f"광고 금지 표현 '{phrase}'이 들어 있습니다.")
    for pattern in rules["banned_cliche_patterns"]:
        m = re.search(pattern, full)
        if m:
            report.warnings.append(f"AI식 상투 표현: \"{m.group(0)}\"")
    labels = {"url": "URL", "phone": "전화번호", "html_tag": "HTML 태그", "ai_mention": "AI 작성 언급"}
    for key, pattern in rules["banned_patterns"].items():
        m = re.search(pattern, full)
        if m:
            report.errors.append(f"{labels.get(key, key)}이 들어 있습니다: \"{m.group(0)}\"")

    # 문체
    excl = full.count("!")
    if excl > rules["max_exclamation_marks"]:
        report.warnings.append(f"느낌표가 {excl}개입니다 (최대 {rules['max_exclamation_marks']}개).")
    emojis = len(EMOJI.findall(full))
    if emojis > rules["max_emojis"]:
        report.warnings.append(f"이모지가 {emojis}개입니다 (최대 {rules['max_emojis']}개).")
    limit = rules["max_same_ending_in_a_row"]
    streak, prev, worst = 0, None, ("", 0)
    for s in _sentences(body):
        end = _ending(s)
        streak = streak + 1 if end and end == prev else 1
        prev = end
        if streak > worst[1]:
            worst = (end or "", streak)
    if worst[1] > limit:
        report.warnings.append(f"같은 어미 '~{worst[0]}'로 끝나는 문장이 {worst[1]}번 연속됩니다.")

    # 요금제
    errors, warnings = check_plans(post, plans)
    report.errors.extend(errors)
    report.warnings.extend(warnings)
    return report
