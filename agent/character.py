"""SVG character designer for the Storybook Agent.

create_character(bible) asks the text model for a JSON blob containing
SVG group strings for one head and five pose bodies, validates the SVG
for banned tags / out-of-palette colours, composes per-pose SVG files,
and writes a preview HTML showing all five poses side by side.

Output:
    output/characters/character_<pose>.svg   (one per pose)
    output/character_preview.html
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from agent import config
from agent.llm import generate_text
from agent.schemas import CharacterBible

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POSES: list[str] = ["standing", "crouch", "hop", "arms_up", "sit"]

# SVG tags that are forbidden in generated character art
BANNED_TAGS: set[str] = {
    "image", "script", "foreignObject", "filter", "mask",
    "linearGradient", "radialGradient", "feBlend", "feColorMatrix",
    "feComposite", "feFlood", "feGaussianBlur", "feMerge", "feMorphology",
    "feOffset", "feTurbulence", "pattern", "animate", "animateTransform",
    "set", "use",  # 'use' could reference external resources
}

# Colours that are always allowed regardless of palette
ALWAYS_ALLOWED_COLOURS: set[str] = {"#ffffff", "#000000", "#f5f5f5", "#e0e0e0",
                                     "#cccccc", "#999999", "#888888", "#666666",
                                     "#444444", "#333333", "#222222", "#111111",
                                     "white", "black", "none", "transparent"}

# ---------------------------------------------------------------------------
# SVG template helpers
# ---------------------------------------------------------------------------

SVG_WRAPPER = """\
<svg xmlns="http://www.w3.org/2000/svg"
     width="200" height="300" viewBox="0 0 200 300">
  {head}
  {body}
</svg>"""


def _compose_svg(head_group: str, body_group: str) -> str:
    return SVG_WRAPPER.format(head=head_group.strip(), body=body_group.strip())


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_character_prompt(bible: CharacterBible) -> str:
    palette_lines = "\n".join(
        f'  "{k}": "{v}"' for k, v in bible.palette.items()
    )

    return f"""You are an SVG artist creating flat, child-friendly character art.

CHARACTER:
  Name: {bible.name}
  Age: {bible.age_description}
  Hair: {bible.hair}
  Eyes: {bible.eyes}
  Skin tone: {bible.skin_tone}
  Outfit: {bible.outfit}
  Signature item: {bible.signature_item}

COLOUR PALETTE (use ONLY these hex values, plus pure white #FFFFFF and black #000000 and greys):
{{{palette_lines}
}}

COORDINATE SPACE: 200 × 300 px.
HEAD: The neck base must be at exactly (100, 90).
      Draw everything above y=90 for the head (face, hair, eyes, ears, neck).
BODIES: Each body group attaches at the neck joint (100, 90).
        Draw everything at or below y=90 for the body (torso, arms, legs, feet, item).

STYLE RULES (MANDATORY – violations will be rejected):
- Flat fills ONLY. Use fill="…" attributes.
- NO gradients, NO filters, NO masks, NO <image>, NO <script>, NO <foreignObject>.
- Use ONLY these SVG elements: <g>, <circle>, <ellipse>, <path>, <rect>, <polygon>, <polyline>, <line>, <text> (for small labels only if needed).
- Use ONLY palette colours listed above + #FFFFFF white + #000000 black + grey shades.
- Child-friendly, simple, cute shapes. No scary details.

Return ONLY valid JSON with this exact structure (no markdown, no explanation):
{{
  "head": "<g id=\\"head\\">…SVG elements…</g>",
  "bodies": {{
    "standing": "<g id=\\"body_standing\\">…SVG elements…</g>",
    "crouch":   "<g id=\\"body_crouch\\">…SVG elements…</g>",
    "hop":      "<g id=\\"body_hop\\">…SVG elements…</g>",
    "arms_up":  "<g id=\\"body_arms_up\\">…SVG elements…</g>",
    "sit":      "<g id=\\"body_sit\\">…SVG elements…</g>"
  }}
}}

Each body pose description:
- standing : upright, arms relaxed at sides, legs straight, holding or displaying the signature item.
- crouch   : knees bent, body lowered, peering forward or down.
- hop      : one or both feet off ground, arms out for balance, mid-jump.
- arms_up  : arms raised above head, excited or celebrating.
- sit      : sitting cross-legged or on heels, relaxed, item in lap or beside.
"""


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _normalise_hex(colour: str) -> str:
    """Return lowercase 6-digit hex or the original string unchanged."""
    c = colour.strip().lower()
    if c.startswith("#") and len(c) == 4:
        c = "#" + c[1] * 2 + c[2] * 2 + c[3] * 2
    return c


def _palette_set(bible: CharacterBible) -> set[str]:
    """Build the set of accepted hex colours from the bible palette."""
    allowed = set(ALWAYS_ALLOWED_COLOURS)
    for v in bible.palette.values():
        norm = _normalise_hex(v)
        allowed.add(norm)
        # also allow the short form
        allowed.add(v.strip().lower())
    # Accept grey shades  #XXXXXX where R==G==B
    return allowed


def _hex_in_palette(hex_val: str, allowed: set[str]) -> bool:
    norm = _normalise_hex(hex_val)
    if norm in allowed:
        return True
    # loose grey check: if R==G==B it's greyscale → always OK
    if re.fullmatch(r"#([0-9a-f]{2})\1\1", norm):
        return True
    return False


def _validate_svg_fragment(fragment: str, bible: CharacterBible) -> list[str]:
    """Parse the SVG group fragment and return a list of violations (empty = OK)."""
    errors: list[str] = []
    allowed = _palette_set(bible)

    # Wrap in a root element so ET can parse a fragment
    try:
        root = ET.fromstring(f"<svg xmlns='http://www.w3.org/2000/svg'>{fragment}</svg>")
    except ET.ParseError as exc:
        return [f"XML parse error: {exc}"]

    for elem in root.iter():
        # Strip namespace prefix if any
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag in BANNED_TAGS:
            errors.append(f"Banned element <{tag}> found.")

        for attr in ("fill", "stroke", "color"):
            val = elem.get(attr, "").strip().lower()
            if not val or val in ("none", "transparent", "inherit", "currentcolor"):
                continue
            if val.startswith("#"):
                if not _hex_in_palette(val, allowed):
                    errors.append(
                        f"Colour {val!r} on <{tag}> is outside the palette. "
                        f"Allowed: {sorted(bible.palette.values())}."
                    )
            # named colours other than white/black/grey families are suspicious
            elif val not in ("white", "black"):
                # allow common greys by name
                if val not in ("gray", "grey", "silver", "darkgray", "lightgray",
                               "dimgray", "gainsboro", "whitesmoke"):
                    errors.append(
                        f"Non-hex colour {val!r} on <{tag}> — use explicit #RRGGBB hex codes."
                    )

    return errors


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def _ask_for_svg(bible: CharacterBible, extra: str = "") -> dict:
    """Call the LLM and return the parsed JSON dict. extra appended for retries."""
    prompt = _build_character_prompt(bible)
    if extra:
        prompt += f"\n\nPREVIOUS ATTEMPT FAILED WITH THESE ERRORS:\n{extra}\nPlease fix them.\n"

    raw = generate_text(
        prompt,
        system_instruction=(
            "You output ONLY raw JSON — no markdown fences, no explanation, "
            "no extra text before or after the JSON object."
        ),
        response_mime_type="application/json",
    )

    # Strip accidental markdown fences
    cleaned = raw.strip()
    for fence in ("```json", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return json.loads(cleaned.strip())


def create_character(bible: CharacterBible) -> dict:
    """Generate SVG character art for all 5 poses and write output files.

    Args:
        bible: The CharacterBible with palette already populated.

    Returns:
        A dict mapping pose name → Path of the saved SVG file.

    Raises:
        ValueError: If validation keeps failing after 2 retries.
    """
    output_dir = config.OUTPUT_DIR / "characters"
    output_dir.mkdir(parents=True, exist_ok=True)

    data: dict | None = None
    accumulated_errors: str = ""

    for attempt in range(3):  # initial + 2 retries
        try:
            data = _ask_for_svg(bible, accumulated_errors)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("SVG JSON parse failed on attempt %d: %s", attempt + 1, exc)
            accumulated_errors += f"\nJSON parse error: {exc}"
            continue

        # ---- Validate head ------------------------------------------------
        head_group: str = data.get("head", "")
        bodies: dict = data.get("bodies", {})

        all_errors: list[str] = []

        head_errs = _validate_svg_fragment(head_group, bible)
        if head_errs:
            all_errors.extend([f"[head] {e}" for e in head_errs])

        for pose in POSES:
            body_group = bodies.get(pose, "")
            if not body_group:
                all_errors.append(f"[{pose}] body group is missing or empty.")
                continue
            body_errs = _validate_svg_fragment(body_group, bible)
            if body_errs:
                all_errors.extend([f"[{pose}] {e}" for e in body_errs])

        if all_errors:
            logger.warning(
                "SVG validation failed on attempt %d (%d error(s)). %s",
                attempt + 1,
                len(all_errors),
                " | ".join(all_errors[:5]),
            )
            accumulated_errors = "\n".join(all_errors)
            if attempt == 2:
                raise ValueError(
                    f"SVG character failed validation after 3 attempts:\n{accumulated_errors}"
                )
            continue

        # ---- All good: write files ----------------------------------------
        break

    if data is None:
        raise ValueError("Failed to obtain SVG character data from the model.")

    head_group = data["head"]
    bodies = data["bodies"]
    saved: dict[str, Path] = {}

    for pose in POSES:
        body_group = bodies[pose]
        svg_content = _compose_svg(head_group, body_group)
        svg_path = output_dir / f"character_{pose}.svg"
        svg_path.write_text(svg_content, encoding="utf-8")
        saved[pose] = svg_path
        logger.info("Saved %s", svg_path)

    # ---- Write preview HTML -----------------------------------------------
    _write_preview_html(bible, saved)

    return {pose: str(path) for pose, path in saved.items()}


def _write_preview_html(bible: CharacterBible, saved: dict[str, Path]) -> None:
    """Write output/character_preview.html showing all 5 poses side by side."""
    preview_path = config.OUTPUT_DIR / "character_preview.html"

    cards_html = ""
    for pose in POSES:
        svg_path = saved.get(pose)
        if svg_path is None:
            continue
        # Embed SVG inline for portability
        try:
            svg_content = svg_path.read_text(encoding="utf-8")
        except OSError:
            svg_content = "<p>SVG not found</p>"

        cards_html += f"""
        <div class="card">
          <div class="svg-wrap">
            {svg_content}
          </div>
          <p class="label">{pose.replace("_", " ").title()}</p>
        </div>"""

    palette_swatches = ""
    for key, hex_val in bible.palette.items():
        palette_swatches += (
            f'<div class="swatch" style="background:{hex_val}" title="{key}: {hex_val}"></div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Character Preview – {bible.name}</title>
  <style>
    :root {{
      --bg: #f7f4ef;
      --card-bg: #ffffff;
      --shadow: 0 4px 16px rgba(0,0,0,.10);
      --accent: #5b8aff;
      --label: #333;
      --border-r: 16px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      font-family: "Segoe UI", system-ui, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 40px 20px;
      gap: 32px;
    }}
    h1 {{
      font-size: 2rem;
      color: var(--label);
      text-align: center;
    }}
    h1 span {{
      color: var(--accent);
    }}
    .meta {{
      font-size: .9rem;
      color: #666;
      text-align: center;
      max-width: 700px;
      line-height: 1.6;
    }}
    .poses {{
      display: flex;
      flex-wrap: wrap;
      gap: 24px;
      justify-content: center;
    }}
    .card {{
      background: var(--card-bg);
      border-radius: var(--border-r);
      box-shadow: var(--shadow);
      padding: 20px 16px 12px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
      transition: transform .2s;
    }}
    .card:hover {{ transform: translateY(-4px); }}
    .svg-wrap {{
      width: 160px;
      height: 240px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .svg-wrap svg {{
      width: 100%;
      height: 100%;
    }}
    .label {{
      font-size: .85rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: var(--accent);
    }}
    .palette-section {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
    }}
    .palette-section h2 {{
      font-size: 1rem;
      color: #555;
    }}
    .palette {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: center;
    }}
    .swatch {{
      width: 36px;
      height: 36px;
      border-radius: 50%;
      border: 2px solid #ddd;
      cursor: default;
    }}
  </style>
</head>
<body>
  <h1>Meet <span>{bible.name}</span></h1>
  <p class="meta">
    {bible.age_description} &bull; {bible.hair} &bull; {bible.outfit}<br/>
    Signature item: {bible.signature_item}
  </p>

  <div class="poses">
    {cards_html}
  </div>

  <div class="palette-section">
    <h2>Colour Palette</h2>
    <div class="palette">
      {palette_swatches}
    </div>
  </div>
</body>
</html>
"""
    preview_path.write_text(html, encoding="utf-8")
    logger.info("Saved preview: %s", preview_path)
