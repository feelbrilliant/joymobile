"""초안을 스마트에디터에 붙여넣을 HTML과, 검수 결과가 함께 보이는 미리보기 페이지로 만든다."""
import html

from .check import Report
from .post import BOLD, Post
from .topics import Topic


def _inline(text: str) -> str:
    return BOLD.sub(r"<b>\1</b>", html.escape(text))


def body_html(post: Post) -> str:
    """스마트에디터 붙여넣기용 본문 HTML (제목 제외)."""
    out: list[str] = []
    for b in post.blocks:
        if b.kind == "heading":
            out.append(f"<h3>{_inline(b.lines[0])}</h3>")
        elif b.kind == "paragraph":
            out.append("<p>" + "<br>".join(_inline(line) for line in b.lines) + "</p>")
        elif b.kind == "divider":
            out.append("<hr>")
        elif b.kind == "table":
            head, *rows = b.rows
            cells = "".join(f"<th>{_inline(c)}</th>" for c in head)
            body = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f"<table><thead><tr>{cells}</tr></thead><tbody>{body}</tbody></table>")
        # 문단 사이 빈 줄: 모바일에서 읽기 편하도록
        out.append("<p><br></p>")
    return "\n".join(out[:-1])


PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_text} · 초안 미리보기</title>
<style>
  :root {{ --bg:#f5f6f8; --paper:#fff; --ink:#1c232d; --muted:#5d6878; --line:#dfe3e9;
          --err:#b3261e; --err-bg:#fbe9e7; --warn:#9a5a00; --warn-bg:#fdf3e1; --ok:#1d7a4a; --ok-bg:#e4f4ea; --accent:#1f5fbf; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.7 "Malgun Gothic","Apple SD Gothic Neo",sans-serif; word-break:keep-all; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:24px 16px 64px; display:grid; gap:16px; }}
  .panel {{ background:var(--paper); border:1px solid var(--line); border-radius:8px; padding:16px 20px; }}
  .meta {{ display:grid; grid-template-columns:max-content 1fr; gap:4px 14px; font-size:14px; }}
  .meta dt {{ color:var(--muted); }} .meta dd {{ margin:0; }}
  .status {{ font-weight:700; padding:10px 14px; border-radius:6px; }}
  .status.ok {{ background:var(--ok-bg); color:var(--ok); }}
  .status.bad {{ background:var(--err-bg); color:var(--err); }}
  .stats {{ display:flex; flex-wrap:wrap; gap:8px; font-size:13px; }}
  .stats span {{ background:var(--bg); border:1px solid var(--line); border-radius:999px; padding:2px 10px; font-variant-numeric:tabular-nums; }}
  ul.issues {{ margin:8px 0 0; padding-left:1.2em; font-size:14px; }}
  ul.issues li.err {{ color:var(--err); }} ul.issues li.warn {{ color:var(--warn); }}
  .actions {{ display:flex; flex-wrap:wrap; gap:8px; }}
  button {{ font:inherit; font-weight:600; border:1px solid var(--accent); background:var(--accent); color:#fff; border-radius:6px; padding:8px 14px; cursor:pointer; }}
  button.ghost {{ background:var(--paper); color:var(--accent); }}
  button:focus-visible {{ outline:3px solid #9cc0f5; outline-offset:2px; }}
  .toast {{ font-size:13px; color:var(--ok); min-height:1.2em; }}
  .post h1 {{ font-size:24px; line-height:1.4; margin:0 0 20px; }}
  .post h3 {{ font-size:18px; margin:0; }}
  .post p {{ margin:0; }}
  .post hr {{ border:0; border-top:1px solid var(--line); margin:4px 0; }}
  .post table {{ border-collapse:collapse; width:100%; font-size:14px; }}
  .post th, .post td {{ border:1px solid var(--line); padding:8px 10px; text-align:left; vertical-align:top; }}
  .post th {{ background:var(--bg); }}
  .table-scroll {{ overflow-x:auto; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="panel">
    <div class="status {status_class}">{status_text}</div>
    <div class="stats" style="margin-top:10px">{stats}</div>
    {issues}
  </div>
  <div class="panel">
    <dl class="meta">
      <dt>키워드</dt><dd>{keyword}</dd>
      <dt>권장 유형</dt><dd>{post_type}</dd>
      <dt>대상 고객</dt><dd>{audience}</dd>
      <dt>작성 모델</dt><dd>{model}</dd>
    </dl>
  </div>
  <div class="panel actions">
    <button type="button" id="copy-title">제목 복사</button>
    <button type="button" id="copy-body" class="ghost">본문 복사 (서식 포함)</button>
    <span class="toast" id="toast" role="status"></span>
  </div>
  <article class="panel post">
    <h1 id="post-title">{title}</h1>
    <div id="post-body" class="table-scroll">{body}</div>
  </article>
</div>
<script>
  const toast = document.getElementById("toast");
  function copyElement(el, label) {{
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    const done = document.execCommand("copy");
    sel.removeAllRanges();
    toast.textContent = done ? label + "을 복사했습니다. 스마트에디터에 붙여넣으세요." : "복사하지 못했습니다. 직접 선택해서 복사해 주세요.";
  }}
  document.getElementById("copy-title").addEventListener("click", () => copyElement(document.getElementById("post-title"), "제목"));
  document.getElementById("copy-body").addEventListener("click", () => copyElement(document.getElementById("post-body"), "본문"));
</script>
</body>
</html>
"""


def preview_page(post: Post, topic: Topic, report: Report, model: str) -> str:
    e = html.escape
    if report.ok:
        status_class, status_text = "ok", "자동 검수 통과" + (f" · 확인할 점 {len(report.warnings)}개" if report.warnings else "")
    else:
        status_class, status_text = "bad", f"수정 필요 {len(report.errors)}개 · 확인할 점 {len(report.warnings)}개"
    stats = "".join(f"<span>{e(k.replace('_', ' '))}: {v:,}</span>" for k, v in report.stats.items())
    items = [f'<li class="err">{e(x)}</li>' for x in report.errors] + [f'<li class="warn">{e(x)}</li>' for x in report.warnings]
    issues = f'<ul class="issues">{"".join(items)}</ul>' if items else ""
    return PAGE.format(
        title_text=e(post.title),
        status_class=status_class,
        status_text=e(status_text),
        stats=stats,
        issues=issues,
        keyword=e(topic.keyword),
        post_type=e(topic.post_type or "-"),
        audience=e(topic.audience or "-"),
        model=e(model),
        title=e(post.title),
        body=body_html(post),
    )
