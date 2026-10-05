"""초안을 쓰고, 검수에 걸리면 같은 대화에서 한 번 고쳐 쓰게 한다.

두 가지 방식을 지원한다.
- ClaudeCodeWriter (기본): PC에 설치된 Claude Code(`claude` 명령)를 부른다. Claude 구독 사용량에서 차감
- ApiWriter: Claude API를 직접 부른다. API 키 필요, 사용한 만큼 과금
"""
import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

API_MODEL = "claude-opus-5-5"
EFFORT = "high"
MAX_TOKENS = 64000
# 안전 필터가 요청을 거절하면 서버가 대체 모델로 자동 재시도한다
FALLBACK_BETA = "server-side-fallback-2026-07-01"
CLAUDE_CODE_TIMEOUT_SEC = 15 * 60


class GenerationError(RuntimeError):
    pass


def revise_prompt(problems: list[str]) -> str:
    listed = "\n".join(f"- {p}" for p in problems)
    return (
        "방금 쓴 글을 자동 검수했더니 아래 문제가 나왔다.\n"
        f"{listed}\n\n"
        "문제가 된 부분만 고치고, 나머지 규칙은 그대로 지켜서 완성된 글 전체를 다시 출력해."
    )


class ClaudeCodeWriter:
    """`claude -p` 로 글을 쓴다. 고쳐 쓰기는 같은 세션을 이어서(--resume) 요청한다."""

    def __init__(self, system: str, model: str | None = None):
        self.exe = shutil.which("claude")
        if not self.exe:
            raise GenerationError(
                "Claude Code가 설치되어 있지 않습니다. README의 '처음 설치'를 따라 설치하고 로그인해 주세요."
            )
        # 저장소의 CLAUDE.md 같은 작업 설정이 글쓰기에 섞이지 않도록 빈 폴더에서 실행한다
        self.workdir = Path(tempfile.mkdtemp(prefix="joyblog_"))
        self.system_file = self.workdir / "system.md"
        self.system_file.write_text(system, encoding="utf-8")
        self.model = model
        self.session_id = str(uuid.uuid4())
        self.started = False
        self.model_used = model or "Claude Code 기본 모델"

    def _ask(self, text: str) -> str:
        cmd = [
            self.exe, "-p",
            "--system-prompt-file", str(self.system_file),
            "--tools", "",
            "--disable-slash-commands",
            "--output-format", "json",
            "--effort", EFFORT,
        ]
        cmd += ["--resume", self.session_id] if self.started else ["--session-id", self.session_id]
        if self.model:
            cmd += ["--model", self.model]
        try:
            proc = subprocess.run(
                cmd, input=text, capture_output=True, encoding="utf-8", errors="replace",
                cwd=self.workdir, timeout=CLAUDE_CODE_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired as e:
            raise GenerationError("Claude Code 응답이 15분 넘게 오지 않았습니다. 다시 실행해 주세요.") from e
        self.started = True

        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            detail = (proc.stderr or proc.stdout).strip()[:300]
            raise GenerationError(
                "Claude Code 실행에 실패했습니다. 명령 프롬프트에서 `claude` 를 한 번 실행해 로그인되어 있는지 확인해 주세요.\n"
                f"상세: {detail}"
            )
        if result.get("is_error") or result.get("subtype") != "success":
            raise GenerationError(f"Claude Code 오류: {str(result.get('result') or result.get('subtype'))[:300]}")
        if result.get("stop_reason") == "max_tokens":
            raise GenerationError("글이 너무 길어 중간에 끊겼습니다. 다시 실행해 주세요.")

        models = list((result.get("modelUsage") or {}).keys())
        if models:
            self.model_used = ", ".join(models) + " (Claude Code)"
        out = (result.get("result") or "").strip()
        if not out:
            raise GenerationError("Claude Code 응답에 본문이 없습니다. 다시 실행해 주세요.")
        return out

    def write(self, user_prompt: str) -> str:
        return self._ask(user_prompt)

    def revise(self, problems: list[str]) -> str:
        return self._ask(revise_prompt(problems))


class ApiWriter:
    """Claude API로 글을 쓴다. 고쳐 쓰기 요청은 같은 대화에 이어 붙인다."""

    def __init__(self, system: str, client=None):
        import anthropic

        self.anthropic = anthropic
        self.client = client or anthropic.Anthropic()
        # 시스템 프롬프트는 글마다 같으므로 캐시해서 비용을 줄인다
        self.system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        self.messages: list[dict] = []
        self.model_used = API_MODEL

    def _ask(self, text: str) -> str:
        anthropic = self.anthropic
        self.messages.append({"role": "user", "content": text})
        try:
            with self.client.beta.messages.stream(
                model=API_MODEL,
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive"},
                output_config={"effort": EFFORT},
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=self.system,
                messages=self.messages,
            ) as stream:
                response = stream.get_final_message()
        except anthropic.AuthenticationError as e:
            raise GenerationError(
                "Claude API 키가 올바르지 않습니다. ANTHROPIC_API_KEY 환경변수를 확인해 주세요."
            ) from e
        except anthropic.RateLimitError as e:
            raise GenerationError("Claude API 사용량 한도에 걸렸습니다. 잠시 후 다시 실행해 주세요.") from e
        except anthropic.APIStatusError as e:
            raise GenerationError(f"Claude API 오류 ({e.status_code}): {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise GenerationError("Claude API에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요.") from e

        if response.stop_reason == "refusal":
            raise GenerationError("Claude가 이 주제의 글 작성을 거절했습니다. 키워드나 제목을 바꿔 보세요.")
        if response.stop_reason == "max_tokens":
            raise GenerationError("글이 너무 길어 중간에 끊겼습니다. 다시 실행해 주세요.")

        # 다음 요청에 이어 붙일 수 있도록 응답 블록을 그대로 보관한다
        self.messages.append({"role": "assistant", "content": response.content})
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise GenerationError("Claude 응답에 본문이 없습니다. 다시 실행해 주세요.")
        self.model_used = response.model
        return text

    def write(self, user_prompt: str) -> str:
        return self._ask(user_prompt)

    def revise(self, problems: list[str]) -> str:
        return self._ask(revise_prompt(problems))
