"""Configuration module for the Storybook Agent.

Loads environment variables from .env and validates required credentials.
Fails clearly if GEMINI_API_KEY is missing.
"""

import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

# Locate and load .env file
_env_path = find_dotenv(usecwd=True)
if _env_path:
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

# Root and directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output")))
SAMPLES_DIR = BASE_DIR / "samples"

# Required API credentials
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is missing. Please set GEMINI_API_KEY in your .env file "
        "or system environment variables. (See .env.example for reference)"
    )

# Model names configured via environment variables (SPEC section 4: never hardcoded)
TEXT_MODEL = os.getenv("TEXT_MODEL", "gemini-2.5-flash").strip()
VISION_MODEL = os.getenv("VISION_MODEL", "gemini-2.5-flash").strip()
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "imagen-3.0-generate-002").strip()

if not TEXT_MODEL:
    raise ValueError("TEXT_MODEL cannot be empty. Please specify TEXT_MODEL in your .env file.")
if not VISION_MODEL:
    raise ValueError("VISION_MODEL cannot be empty. Please specify VISION_MODEL in your .env file.")
if not IMAGE_MODEL:
    raise ValueError("IMAGE_MODEL cannot be empty. Please specify IMAGE_MODEL in your .env file.")

# Fixed style suffix used across all illustrations for visual consistency (SPEC section 8)
STYLE_SUFFIX = os.getenv(
    "STYLE_SUFFIX",
    "charming children's book illustration, vibrant watercolor and soft digital painting, "
    "warm lighting, whimsical storybook aesthetic, clean lines, high detail, masterpiece",
).strip()


def get_config_summary() -> dict:
    """Return a masked summary of active configuration settings."""
    masked_key = (
        f"{GEMINI_API_KEY[:4]}...{GEMINI_API_KEY[-4:]}"
        if len(GEMINI_API_KEY) > 8
        else "***"
    )
    return {
        "GEMINI_API_KEY": masked_key,
        "TEXT_MODEL": TEXT_MODEL,
        "VISION_MODEL": VISION_MODEL,
        "IMAGE_MODEL": IMAGE_MODEL,
        "STYLE_SUFFIX": STYLE_SUFFIX,
        "OUTPUT_DIR": str(OUTPUT_DIR),
    }
