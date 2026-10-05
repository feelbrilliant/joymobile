"""조이모바일 블로그 초안 생성기.

사용 예
  python run.py                       topics.csv 에서 주제를 자동으로 골라 초안 생성
  python run.py --id 12               12번 주제로 초안 생성
  python run.py --keyword "유심 eSIM 차이" --title "유심 eSIM 차이, 내 휴대폰에는 어떤 게 맞을까"
  python run.py --id 12 --from-file 초안.txt   API 호출 없이 이미 있는 글을 검수·미리보기
  python run.py --id 12 --dry-run     Claude에 보낼 프롬프트만 출력
  python run.py --engine api          Claude Code 대신 Claude API로 작성 (API 키 필요)
"""
import argparse
import json
import sys
import webbrowser
from dataclasses import asdict
from datetime import date
from pathlib import Path

from joyblog import topics as topic_store
from joyblog.check import check
from joyblog.paths import POSTS_DIR
from joyblog.post import parse
from joyblog.prompt import load_plans, system_prompt, user_prompt
from joyblog.render import body_html, preview_page


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="조이모바일 블로그 초안 생성기")
    ap.add_argument("--id", help="topics.csv 의 주제 id")
    ap.add_argument("--keyword", help="직접 지정할 메인 키워드 (--title 과 함께)")
    ap.add_argument("--title", help="직접 지정할 제목 (그대로 발행됨)")
    ap.add_argument("--type", default="", help="권장 유형 (직접 지정 시)")
    ap.add_argument("--audience", default="", help="중심 고객층 (직접 지정 시)")
    ap.add_argument("--from-file", type=Path, help="API 호출 없이 이 파일의 글을 검수")
    ap.add_argument("--dry-run", action="store_true", help="프롬프트만 출력하고 끝냄")
    ap.add_argument("--no-revise", action="store_true", help="검수에 걸려도 자동으로 고쳐 쓰지 않음")
    ap.add_argument("--no-open", action="store_true", help="미리보기를 브라우저로 열지 않음")
    ap.add_argument("--engine", choices=["claude-code", "api"], default="claude-code",
                    help="claude-code: Claude 구독으로 작성(기본) / api: Claude API로 작성(API 키 필요)")
    ap.add_argument("--model", help="Claude Code에서 쓸 모델 (예: opus, sonnet). 지정하지 않으면 계정 기본 모델")
    return ap.parse_args()


def choose_topic(args, topics):
    if args.keyword or args.title:
        if not (args.keyword and args.title):
            sys.exit("--keyword 와 --title 은 함께 지정해야 합니다.")
        return topic_store.Topic("custom", "직접입력", args.keyword, args.title, args.type, args.audience, "", ""), False
    if args.id:
        return topic_store.find(topics, args.id), True
    return topic_store.pick(topics), True


def save_outputs(topic, text, post, report, model, first=None) -> Path:
    folder = POSTS_DIR / f"{date.today().isoformat()}_{topic.id}"
    n = 2
    while folder.exists():
        folder = POSTS_DIR / f"{date.today().isoformat()}_{topic.id}_{n}"
        n += 1
    folder.mkdir(parents=True)
    (folder / "draft.txt").write_text(text + "\n", encoding="utf-8")
    if first:
        # 자동 수정 전 원본도 남겨 두면 어떤 문제가 있었는지 비교할 수 있다
        (folder / "draft_before_revise.txt").write_text(first["draft"] + "\n", encoding="utf-8")
    (folder / "body.html").write_text(body_html(post), encoding="utf-8")
    (folder / "preview.html").write_text(preview_page(post, topic, report, model), encoding="utf-8")
    (folder / "post.json").write_text(
        json.dumps(
            {"topic": topic.to_row(), "model": model, "title": post.title,
             "blocks": [asdict(b) for b in post.blocks], "report": report.to_dict(),
             "errors_before_revise": first["errors"] if first else []},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return folder


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    topics = topic_store.load()
    try:
        topic, from_csv = choose_topic(args, topics)
    except (KeyError, LookupError) as e:
        print(e.args[0])
        return 1

    plans = load_plans()
    system = system_prompt(plans)
    user = user_prompt(topic)
    print(f"주제 #{topic.id} · {topic.keyword}\n제목: {topic.title}")

    if args.dry_run:
        print("\n===== SYSTEM =====\n" + system + "\n\n===== USER =====\n" + user)
        return 0

    first = None
    if args.from_file:
        text = args.from_file.read_text(encoding="utf-8-sig")
        model = f"(파일: {args.from_file.name})"
        post = parse(text)
        report = check(post, topic.keyword, topic.title, plans)
    else:
        from joyblog.generate import ApiWriter, ClaudeCodeWriter, GenerationError

        try:
            writer = ApiWriter(system) if args.engine == "api" else ClaudeCodeWriter(system, args.model)
            print("Claude가 초안을 쓰는 중입니다. 1~3분 정도 걸립니다...")
            text = writer.write(user)
            post = parse(text)
            report = check(post, topic.keyword, topic.title, plans)
            if report.revise_items and not args.no_revise:
                print(f"검수에서 {len(report.revise_items)}개 문제가 나와 한 번 고쳐 씁니다...")
                for x in report.revise_items:
                    print(f"  - {x}")
                first = {"draft": text, "errors": report.revise_items}
                text = writer.revise(report.revise_items)
                post = parse(text)
                report = check(post, topic.keyword, topic.title, plans)
        except GenerationError as e:
            print(f"초안 생성 실패: {e}")
            return 1
        model = writer.model_used

    folder = save_outputs(topic, text, post, report, model, first)
    if from_csv and not args.from_file:
        topic_store.mark(topics, topic, topic_store.DRAFTED)
        topic_store.save(topics)

    print(f"\n본문 {report.stats['본문_글자수_공백제외']:,}자 · 키워드 {report.stats['키워드_횟수']}회")
    for x in report.errors:
        print(f"  [수정 필요] {x}")
    for x in report.warnings:
        print(f"  [확인] {x}")
    print("자동 검수 통과" if report.ok else "자동 검수에서 고칠 곳이 남았습니다. 미리보기에서 확인하세요.")
    preview = folder / "preview.html"
    print(f"저장 위치: {folder}")
    if not args.no_open:
        webbrowser.open(preview.resolve().as_uri())
    return 0 if report.ok else 2


if __name__ == "__main__":
    sys.exit(main())
