"""포스트 폴더(본문.txt + 이미지프롬프트.md + images/)를 읽어 블록 목록으로 바꾸는 공통 모듈.

폴더 구조
    posts/<날짜_지역_주제>/
        본문.txt            첫 줄 제목, 이후 본문. 섹션은 '-----' 줄로 구분
        이미지프롬프트.md   '## 01 ...' 형식의 이미지별 프롬프트
        images/             01.png, 02.png ... (프롬프트 번호와 같은 순서)

이미지 배치 규칙: k번째 이미지는 k번째 섹션 맨 앞에 들어간다.
(01 썸네일 → 도입부, 02~ → 각 소제목, 마지막 FAQ·정리 순서. 해시태그 섹션에는 이미지 없음)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SECTION_SEP = re.compile(r"^-{5,}\s*$", re.M)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class Post:
    folder: Path
    title: str
    sections: list[str]          # 각 섹션 본문 (앞뒤 공백 제거)
    images: list[Path]           # 번호순 정렬
    prompt_titles: list[str] = field(default_factory=list)
    prompt_text: str = ""

    def blocks(self) -> list[tuple[str, str]]:
        """('image', 경로) / ('text', 문단) / ('divider', '') 순서 목록."""
        out: list[tuple[str, str]] = []
        for i, sec in enumerate(self.sections):
            if i > 0:
                out.append(("divider", ""))
            if i < len(self.images):
                out.append(("image", str(self.images[i])))
            for para in re.split(r"\n\s*\n", sec):
                para = para.strip()
                if para:
                    out.append(("text", para))
        return out


def load_post(folder: str | Path) -> Post:
    folder = Path(folder)
    raw = (folder / "본문.txt").read_text(encoding="utf-8").strip()
    title, _, body = raw.partition("\n")
    sections = [s.strip() for s in SECTION_SEP.split(body) if s.strip()]

    img_dir = folder / "images"
    images = sorted(
        (p for p in img_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS),
        key=lambda p: p.name,
    ) if img_dir.exists() else []

    prompt_path = folder / "이미지프롬프트.md"
    prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    prompt_titles = re.findall(r"^## (\d{2} .+)$", prompt_text, re.M)

    return Post(folder, title.strip(), sections, images, prompt_titles, prompt_text)
