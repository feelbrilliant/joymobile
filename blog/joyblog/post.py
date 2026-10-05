"""Claude가 쓴 글(약속된 표기)을 블록 단위로 나눈다.

표기: 첫 줄 제목, "## " 소제목, "-----" 구분선, "항목 | 내용" 표, **굵게**.
"""
import re
from dataclasses import dataclass, field

DIVIDER = re.compile(r"^\s*-{3,}\s*$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
BOLD = re.compile(r"\*\*(.+?)\*\*")


@dataclass
class Block:
    kind: str  # heading | paragraph | divider | table
    lines: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Post:
    title: str
    blocks: list[Block]

    def body_lines(self) -> list[str]:
        """제목을 뺀 본문 텍스트 줄 (표는 칸을 공백으로 이어서)."""
        out: list[str] = []
        for b in self.blocks:
            if b.kind in ("heading", "paragraph"):
                out.extend(b.lines)
            elif b.kind == "table":
                out.extend(" ".join(row) for row in b.rows)
        return out

    def body_text(self) -> str:
        return strip_marks("\n".join(self.body_lines()))


def strip_marks(text: str) -> str:
    return BOLD.sub(r"\1", text)


def _is_table_line(line: str) -> bool:
    return "|" in line and len([c for c in line.strip().strip("|").split("|") if c.strip()]) >= 2


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(text: str) -> Post:
    lines = text.replace("\r\n", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        raise ValueError("빈 글입니다.")
    title = lines.pop(0)
    title = re.sub(r"^#+\s*", "", title).rstrip()

    blocks: list[Block] = []
    para: list[str] = []
    table: list[list[str]] = []

    def flush():
        if para:
            blocks.append(Block("paragraph", lines=para.copy()))
            para.clear()
        if table:
            blocks.append(Block("table", rows=[r for r in table]))
            table.clear()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush()
        elif TABLE_SEPARATOR.match(line) and table:
            continue
        elif DIVIDER.match(line):
            flush()
            blocks.append(Block("divider"))
        elif line.lstrip().startswith("#"):
            flush()
            blocks.append(Block("heading", lines=[re.sub(r"^\s*#+\s*", "", line)]))
        elif _is_table_line(line):
            if para:
                blocks.append(Block("paragraph", lines=para.copy()))
                para.clear()
            table.append(_cells(line))
        else:
            if table:
                flush()
            para.append(line.strip())
    flush()
    return Post(title=title, blocks=blocks)
