import os
from dotenv import load_dotenv

# load_dotenv() reads a .env file in the project root (if it exists)
# and sets the values as environment variables.
# It's a no-op if the file doesn't exist — safe to call unconditionally.
# Think of it like sourcing a secrets file in a shell script:
#   source .env  →  load_dotenv()
load_dotenv()

HF_API_KEY: str | None = os.getenv("HF_API_KEY") or None
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY") or None
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY") or None
