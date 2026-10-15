"""Planner module for the Storybook Agent.

Generates a structured 5-page children's storybook outline (including character bible
and page breakdowns) using the configured text model and validates it against the Story schema.

Uses agent/llm.py (generate_text) so the LLM backend is provider-agnostic.
"""

import json
import logging
from typing import Optional

from pydantic import ValidationError

from agent.llm import generate_text
from agent.schemas import Story

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema skeleton embedded in the prompt so the model always uses correct keys
# ---------------------------------------------------------------------------
_SCHEMA_SKELETON = """{
  "title": "...",
  "character": {
    "name": "...",
    "age_description": "about X years old",
    "hair": "...",
    "eyes": "...",
    "skin_tone": "...",
    "outfit": "...",
    "signature_item": "...",
    "art_style": "...",
    "palette": {
      "hair": "#RRGGBB",
      "skin": "#RRGGBB",
      "eyes": "#RRGGBB",
      "coat": "#RRGGBB",
      "overalls": "#RRGGBB",
      "boots": "#RRGGBB",
      "ribbon": "#RRGGBB",
      "item": "#RRGGBB"
    }
  },
  "pages": [
    {
      "page_no": 1,
      "title": "...",
      "text": "...",
      "scene_description": "...",
      "pose": "standing"
    }
  ]
}"""

PLANNER_SYSTEM_INSTRUCTION = (
    "You are a children's book author and art director for ages 4-8. "
    "Given a story idea, produce a 5-page story. "
    "Arc: page 1 meet the character, page 2 discover the entrance or clue, "
    "page 3 a small gentle challenge, page 4 the magical discovery, page 5 a happy ending. "
    "Each page text must be 2-3 very simple sentences. "
    "\n\n"
    "CHARACTER BIBLE RULES:\n"
    "- Give concrete, fixed visual details: exact hair style and color, "
    "exact outfit with colors, one signature item.\n"
    "- Fill the 'palette' field with exact hex color codes (#RRGGBB) for EVERY key: "
    "hair, skin, eyes, coat, overalls, boots, ribbon, item. "
    "The hex values MUST match the colors described in the outfit and hair text. "
    "Example: if the coat is 'bright yellow', set palette.coat to '#FFD700'. "
    "If a key does not apply (e.g. no ribbon), still include it with a sensible neutral "
    "(e.g. '#888888').\n"
    "\n"
    "SCENE / POSE RULES:\n"
    "- In scene_description, describe ONLY the setting, action and mood. "
    "Never describe the character's appearance there.\n"
    "- For each page, set 'pose' to ONE of these exact string values:\n"
    "  'standing'  — neutral, calm, or walking scenes\n"
    "  'crouch'    — looking at the ground, hiding, or examining something small\n"
    "  'hop'       — jumping, leaping, or crossing an obstacle\n"
    "  'arms_up'   — excited, surprised, waving, or celebrating\n"
    "  'sit'       — resting, reading, or relaxed contemplation\n"
    "\n"
    "CRITICAL: You MUST use EXACTLY these JSON key names — no aliases:\n"
    "  'page_no' (not 'page_number'), 'title', 'text', 'scene_description', 'pose'\n"
    "  'age_description', 'skin_tone', 'art_style', 'outfit', 'signature_item'\n"
    "\n"
    f"Follow this JSON structure precisely (fill '...' with real values, keep all 5 pages):\n{_SCHEMA_SKELETON}\n"
    "\n"
    "Keep everything safe and child-friendly. "
    "Return valid JSON ONLY — no markdown, no extra text."
)


# ---------------------------------------------------------------------------
# Data normalization (tolerates common model field-name hallucinations)
# ---------------------------------------------------------------------------

_PAGE_ALIASES: dict[str, str] = {
    "page_number": "page_no",
    "pageNo": "page_no",
    "number": "page_no",
    "story_text": "text",
    "body": "text",
    "content": "text",
    "scene": "scene_description",
    "description": "scene_description",
    "scene_desc": "scene_description",
}

_CHAR_ALIASES: dict[str, str] = {
    "age": "age_description",
    "skin": "skin_tone",
    "style": "art_style",
    "clothing": "outfit",
    "clothes": "outfit",
    "item": "signature_item",
    "special_item": "signature_item",
    "accessories": "signature_item",
}


def _normalize_page(p: dict) -> dict:
    result = {}
    for k, v in p.items():
        result[_PAGE_ALIASES.get(k, k)] = v
    return result


def _normalize_character(c: dict) -> dict:
    result = {}
    for k, v in c.items():
        result[_CHAR_ALIASES.get(k, k)] = v
    return result


def _normalize_story(data: dict) -> dict:
    """Remap common model field-name variants to the canonical schema names."""
    if not isinstance(data, dict):
        return data

    # Normalize top-level: some models nest "story" inside a wrapper
    if "story" in data and isinstance(data["story"], dict):
        data = data["story"]

    if "character" in data and isinstance(data["character"], dict):
        data["character"] = _normalize_character(data["character"])

    if "pages" in data and isinstance(data["pages"], list):
        data["pages"] = [_normalize_page(p) if isinstance(p, dict) else p
                         for p in data["pages"]]

    return data


# ---------------------------------------------------------------------------
# JSON cleaning helper
# ---------------------------------------------------------------------------

def _clean_json_text(text: str) -> str:
    """Strip markdown code fence blocks if present in the model response."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plan_story(prompt: str) -> Story:
    """Plan a 5-page children's story from a text prompt.

    Args:
        prompt: User story idea or prompt.

    Returns:
        Validated Story pydantic model containing character bible and exactly 5 pages.

    Raises:
        ValueError: If config or API key is invalid.
        ValidationError: If model output fails schema validation after retry.
    """
    current_prompt = prompt
    last_error: Optional[Exception] = None

    # Up to 2 attempts: initial call + 1 retry if validation fails
    for attempt in range(2):
        raw_text = generate_text(
            current_prompt,
            system_instruction=PLANNER_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
        )

        cleaned_json = _clean_json_text(raw_text)

        try:
            data = json.loads(cleaned_json)
            data = _normalize_story(data)
            story = Story.model_validate(data)
            return story
        except (json.JSONDecodeError, ValidationError) as err:
            last_error = err
            if attempt == 0:
                logger.warning(
                    "Story schema validation failed on initial attempt: %s. Retrying once...",
                    err,
                )
                current_prompt = (
                    f"{prompt}\n\n"
                    f"[IMPORTANT: Your previous JSON output failed schema validation.\n"
                    f"Errors:\n{err}\n\n"
                    f"Fix ONLY the listed errors and return the COMPLETE story JSON. "
                    f"Pay attention to exact key names — use 'page_no' not 'page_number', "
                    f"'age_description' not 'age', 'outfit' not 'clothing', "
                    f"'signature_item' not 'item' or 'accessories'. "
                    f"Include 'palette' with 8 hex codes and 'pose' on every page.]\n"
                )
            else:
                logger.error("Story schema validation failed after retry: %s", err)
                raise err

    if last_error:
        raise last_error
    raise RuntimeError("Failed to generate story.")
