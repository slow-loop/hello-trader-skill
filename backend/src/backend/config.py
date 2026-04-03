import os
from dotenv import load_dotenv

load_dotenv()

# Required only when DB_BACKEND=supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if os.getenv("DB_BACKEND", "sqlite") == "supabase":
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("DB_BACKEND=supabase requires SUPABASE_URL and SUPABASE_KEY")

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# Optional
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
