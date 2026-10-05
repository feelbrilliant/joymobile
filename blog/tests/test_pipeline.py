import unittest

from joyblog.check import check, count_keyword
from joyblog.post import parse
from joyblog.prompt import load_plans, render_plans
from joyblog.render import body_html
from joyblog.topics import Topic, pick

PLANS = load_plans()
RULES = {
    "min_chars_without_spaces": 50,
    "keyword_count": {"min": 1, "max": 3},
    "max_same_ending_in_a_row": 2,
    "banned_cliche_patterns": ["오늘은 .{0,30}알아보겠습니다"],
    "banned_ad_phrases": ["최저가", "무조건"],
    "banned_patterns": {
        "url": r"https?://|www\.",
        "phone": r"(?<!\d)0\d{1,2}[- .]?\d{3,4}[- .]?\d{4}(?!\d)",
    },
    "max_exclamation_marks": 1,
    "max_emojis": 1,
}

DRAFT = """선불폰 요금제 선택 전에 내 사용량부터 확인해보세요

한 달에 데이터를 얼마나 쓰는지 모르면 요금제를 고르기 어렵습니다.

## 사용량별로 나눠 보면

선불폰 요금제 선택은 데이터 사용량에서 시작하는 편이에요.

요금제 | 월 요금 | 데이터
---|---|---
선불396 | 39,600원 | 10.3GB
선불459 | 45,900원 | 20.3GB

-----

## 마무리

**선불396**은 월 39,600원에 10.3GB를 제공합니다.
"""


def topic(**kw):
    base = dict(id="1", category="가이드", keyword="선불폰 요금제 선택",
                title="선불폰 요금제 선택 전에 내 사용량부터 확인해보세요",
                post_type="선택 가이드형", audience="", status="사용가능", used_on="")
    base.update(kw)
    return Topic(**base)


class ParseTest(unittest.TestCase):
    def test_blocks(self):
        post = parse(DRAFT)
        self.assertEqual(post.title, "선불폰 요금제 선택 전에 내 사용량부터 확인해보세요")
        kinds = [b.kind for b in post.blocks]
        self.assertEqual(kinds, ["paragraph", "heading", "paragraph", "table", "divider", "heading", "paragraph"])
        table = post.blocks[3]
        self.assertEqual(table.rows[0], ["요금제", "월 요금", "데이터"])
        self.assertEqual(len(table.rows), 3)  # 구분 행(---)은 버림

    def test_lists(self):
        post = parse("제목\n\n이런 경우라면:\n- 첫째 경우\n- 둘째 경우\n\n1. 확인하기\n2. 신청하기\n\n끝 문단입니다.")
        kinds = [(b.kind, len(b.lines)) for b in post.blocks]
        self.assertEqual(kinds, [("paragraph", 1), ("ulist", 2), ("olist", 2), ("paragraph", 1)])
        self.assertIn("<ul><li>첫째 경우</li>", body_html(post))
        self.assertIn("<ol><li>확인하기</li>", body_html(post))

    def test_divider_is_not_list(self):
        self.assertEqual([b.kind for b in parse("제목\n\n-----\n\n- 항목").blocks], ["divider", "ulist"])

    def test_html(self):
        out = body_html(parse(DRAFT))
        self.assertIn("<h3>사용량별로 나눠 보면</h3>", out)
        self.assertIn("<th>요금제</th>", out)
        self.assertIn("<b>선불396</b>", out)
        self.assertIn("<hr>", out)


class CheckTest(unittest.TestCase):
    def run_check(self, text, **kw):
        t = topic(**kw)
        return check(parse(text), t.keyword, t.title, PLANS, RULES)

    def test_clean_draft_passes(self):
        report = self.run_check(DRAFT)
        self.assertEqual(report.errors, [])

    def test_title_changed(self):
        report = self.run_check(DRAFT.replace("확인해보세요", "확인하세요", 1))
        self.assertTrue(any("제목" in e for e in report.errors))

    def test_wrong_price_in_table(self):
        report = self.run_check(DRAFT.replace("선불459 | 45,900원", "선불459 | 44,900원"))
        self.assertTrue(any("선불459" in e and "44,900원" in e for e in report.errors))

    def test_wrong_data_in_sentence(self):
        report = self.run_check(DRAFT.replace("월 39,600원에 10.3GB", "월 39,600원에 11GB"))
        self.assertTrue(any("데이터 제공량" in e for e in report.errors))

    def test_speed_is_not_data(self):
        text = DRAFT.replace("선불459 | 45,900원 | 20.3GB", "선불459 | 45,900원 | 20.3GB 소진 후 최대 3Mbps")
        self.assertEqual(self.run_check(text).errors, [])

    def test_wrong_speed(self):
        text = DRAFT.replace("선불459 | 45,900원 | 20.3GB", "선불459 | 45,900원 | 20.3GB 소진 후 최대 5Mbps")
        self.assertTrue(any("속도" in e for e in self.run_check(text).errors))

    def test_video_word_is_not_plan(self):
        text = DRAFT + "\n비디오 시청이 많다면 20GB 이상이 편합니다.\n"
        report = self.run_check(text)
        self.assertEqual(report.errors, [])

    def test_banned_and_contacts(self):
        text = DRAFT + "\n최저가로 개통하세요. 문의는010-1234-5678 또는 www.example.com\n"
        errors = self.run_check(text).errors
        self.assertTrue(any("최저가" in e for e in errors))
        self.assertTrue(any("전화번호" in e for e in errors))
        self.assertTrue(any("URL" in e for e in errors))

    def test_list_items_not_counted_as_sentence_endings(self):
        text = DRAFT + "\n- 기능이 없는 경우\n- 자주 바꾸는 경우\n- 낯선 경우\n- 따로 쓰는 경우\n"
        self.assertFalse(any("연속" in w for w in self.run_check(text).warnings))

    def test_short_body(self):
        rules = dict(RULES, min_chars_without_spaces=2000)
        t = topic()
        report = check(parse(DRAFT), t.keyword, t.title, PLANS, rules)
        self.assertTrue(any("짧습니다" in e for e in report.errors))

    def test_keyword_ignores_spacing(self):
        self.assertEqual(count_keyword("선불폰요금제 선택, 선불폰 요금제선택", "선불폰 요금제 선택"), 2)

    def test_same_ending_streak(self):
        text = DRAFT + "\n어렵지 않습니다. 쉽습니다. 좋습니다.\n"
        report = self.run_check(text)
        self.assertTrue(any("연속" in w for w in report.warnings))


class TopicTest(unittest.TestCase):
    def test_pick_skips_same_type_as_last(self):
        topics = [
            topic(id="1", status="초안생성", used_on="2026-10-01", category="가이드", post_type="선택 가이드형"),
            topic(id="2", category="가이드", post_type="선택 가이드형"),
            topic(id="3", category="비교", post_type="비교형"),
            topic(id="4", status="검토필요", category="지역", post_type="질문형"),
        ]
        self.assertEqual(pick(topics).id, "3")

    def test_pick_needs_ready_topic(self):
        with self.assertRaises(LookupError):
            pick([topic(status="검토필요")])


class PromptTest(unittest.TestCase):
    def test_plans_rendered_from_json(self):
        text = render_plans(PLANS)
        self.assertIn("- 선불396 (주력)", text)
        self.assertIn("월 39,600원", text)
        self.assertIn("음성 50분", text)


if __name__ == "__main__":
    unittest.main()
