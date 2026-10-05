from pathlib import Path

BLOG_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BLOG_DIR / "prompts"
DATA_DIR = BLOG_DIR / "data"
POSTS_DIR = BLOG_DIR / "posts"

SYSTEM_PROMPT = PROMPTS_DIR / "system.md"
USER_PROMPT = PROMPTS_DIR / "user.md"
PLANS = DATA_DIR / "plans.json"
TOPICS = DATA_DIR / "topics.csv"
RULES = DATA_DIR / "rules.json"
