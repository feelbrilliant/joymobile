"""주제 목록(topics.csv) 읽기, 자동 선정, 사용 기록."""
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .paths import TOPICS

READY = "사용가능"
DRAFTED = "초안생성"
PUBLISHED = "사용완료"

FIELDS = ["id", "분류", "키워드", "제목", "권장_유형", "대상_고객", "상태", "사용일"]


@dataclass
class Topic:
    id: str
    category: str
    keyword: str
    title: str
    post_type: str
    audience: str
    status: str
    used_on: str

    @classmethod
    def from_row(cls, row: dict) -> "Topic":
        return cls(
            id=row["id"].strip(),
            category=row["분류"].strip(),
            keyword=row["키워드"].strip(),
            title=row["제목"],  # 제목은 공백까지 그대로 보존
            post_type=row["권장_유형"].strip(),
            audience=row["대상_고객"].strip(),
            status=row["상태"].strip(),
            used_on=(row.get("사용일") or "").strip(),
        )

    def to_row(self) -> dict:
        return {
            "id": self.id,
            "분류": self.category,
            "키워드": self.keyword,
            "제목": self.title,
            "권장_유형": self.post_type,
            "대상_고객": self.audience,
            "상태": self.status,
            "사용일": self.used_on,
        }


def _read_text(path: Path) -> str:
    # 엑셀에서 저장하면 cp949가 되는 경우가 있어 둘 다 받는다
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{path.name} 파일의 인코딩을 읽을 수 없습니다. UTF-8로 저장해 주세요.")


def load(path: Path = TOPICS) -> list[Topic]:
    rows = csv.DictReader(_read_text(path).splitlines())
    missing = [f for f in FIELDS if f not in (rows.fieldnames or [])]
    if missing:
        raise ValueError(f"{path.name} 에 열이 없습니다: {', '.join(missing)}")
    return [Topic.from_row(r) for r in rows if (r.get("id") or "").strip()]


def save(topics: list[Topic], path: Path = TOPICS) -> None:
    # utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않도록 BOM 포함
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(t.to_row() for t in topics)


def find(topics: list[Topic], topic_id: str) -> Topic:
    for t in topics:
        if t.id == str(topic_id):
            return t
    raise KeyError(f"id {topic_id} 주제가 topics.csv 에 없습니다.")


def pick(topics: list[Topic]) -> Topic:
    """사용가능 주제 중 하나를 고른다.

    직전에 쓴 글과 분류·권장 유형이 겹치지 않는 주제를 우선해서,
    같은 형식의 글이 연달아 나오지 않게 한다.
    """
    ready = [t for t in topics if t.status == READY]
    if not ready:
        raise LookupError(
            "자동 선정할 주제가 없습니다. topics.csv 에서 확인한 주제의 상태를 '사용가능'으로 바꿔 주세요."
        )
    used = sorted((t for t in topics if t.used_on), key=lambda t: t.used_on)
    last = used[-1] if used else None
    if last:
        fresh = [t for t in ready if t.category != last.category and t.post_type != last.post_type]
        if fresh:
            return fresh[0]
        fresh = [t for t in ready if t.post_type != last.post_type]
        if fresh:
            return fresh[0]
    return ready[0]


def mark(topics: list[Topic], topic: Topic, status: str, on: date | None = None) -> None:
    target = find(topics, topic.id)
    target.status = status
    target.used_on = (on or date.today()).isoformat()
