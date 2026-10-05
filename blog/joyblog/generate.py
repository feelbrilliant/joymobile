"""Claude API로 초안을 작성하고, 검수에 걸리면 한 번 고쳐 쓰게 한다."""
import anthropic

MODEL = "claude-opus-5-5"
EFFORT = "high"
MAX_TOKENS = 64000
# 안전 필터가 요청을 거절하면 서버가 대체 모델로 자동 재시도한다
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class GenerationError(RuntimeError):
    pass


class Writer:
    """한 편의 글을 쓰는 대화. 고쳐 쓰기 요청은 같은 대화에 이어 붙인다."""

    def __init__(self, system: str, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()
        # 시스템 프롬프트는 글마다 같으므로 캐시해서 비용을 줄인다
        self.system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        self.messages: list[dict] = []
        self.model_used = MODEL

    def _ask(self, text: str) -> str:
        self.messages.append({"role": "user", "content": text})
        try:
            with self.client.beta.messages.stream(
                model=MODEL,
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
        listed = "\n".join(f"- {p}" for p in problems)
        return self._ask(
            "방금 쓴 글을 자동 검수했더니 아래 문제가 나왔다.\n"
            f"{listed}\n\n"
            "문제가 된 부분만 고치고, 나머지 규칙은 그대로 지켜서 완성된 글 전체를 다시 출력해."
        )
