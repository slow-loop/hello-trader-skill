"""
skill_tw_trader package.
"""

from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env in the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")
