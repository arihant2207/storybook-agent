"""Page compositor for the Storybook Agent (M4).

compose_and_save(page, bg_svg, char_dir, pages_dir, force=False) -> Path
  Overlays the character SVG (for the page's pose) onto the background SVG
  and saves the result to pages_dir/page_N.svg.
  Skips generation if the file already exists and force=False (cache).

The character is placed in a <g transform="translate(300, 220+offset)"> so its
200×300 bounding box is centred at x=400 with feet landing on y=520.

FOOT_OFFSET lets you nudge individual poses up/down without touching any
other file — just edit the dict values here.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tune these offsets (px) to adjust where each pose lands on the ground line.
# Positive  = character moves DOWN  (feet sink below ground)
# Negative  = character moves UP    (hover / jump effect)
# ---------------------------------------------------------------------------
FOOT_OFFSET: dict[str, int] = {
    "standing": 0,
    "crouch":   0,
    "hop":      -20,   # slight lift for mid-jump feel
    "arms_up":  0,
    "sit":      30,    # sit pose is shorter, push down so it reads as ground-level
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_svg_inner(svg_path: Path) -> str:
    """Read a character SVG and return its inner content byte-identical.

    Strips the outer <svg …>…</svg> wrapper so the content can be embedded
    inside the background SVG's coordinate space.
    """
    text = svg_path.read_text(encoding="utf-8")
    m = re.search(r"<svg[^>]*>([\s\S]*)</svg>", text, re.S)
    if not m:
        raise ValueError(f"Could not find <svg>…</svg> content in {svg_path}")
    return m.group(1)  # byte-identical inner content, never regenerated


def _find_character_svg(pose: str, char_dir: Path) -> Path:
    """Locate the SVG file for *pose* inside *char_dir*."""
    candidate = char_dir / f"character_{pose}.svg"
    if candidate.is_file():
        return candidate
    # Fallback: glob in case naming differs slightly
    matches = list(char_dir.glob(f"*{pose}*.svg"))
    if not matches:
        raise FileNotFoundError(
            f"No character SVG for pose '{pose}' in {char_dir}. "
            "Run the character step first."
        )
    return matches[0]


def _compose(bg_svg: str, pose: str, char_dir: Path) -> str:
    """Overlay the character group onto *bg_svg* and return the composed SVG."""
    offset = FOOT_OFFSET.get(pose, 0)
    ty = 220 + offset

    inner = _extract_svg_inner(_find_character_svg(pose, char_dir))
    char_group = (
        f'<g id="character" transform="translate(300,{ty})">'
        f"{inner}"
        f"</g>"
    )

    # Insert just before the closing </svg> tag
    insert_at = bg_svg.rfind("</svg>")
    if insert_at == -1:
        raise ValueError("Background SVG has no closing </svg> tag")
    return bg_svg[:insert_at] + char_group + bg_svg[insert_at:]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compose_page(
    bg_svg: str,
    pose: str,
    char_dir: Path,
) -> str:
    """Compose background + character and return the SVG string.

    Args:
        bg_svg:   Background SVG string (viewBox 0 0 800 600).
        pose:     One of the five pose names.
        char_dir: Directory containing character_<pose>.svg files.

    Returns:
        Composed SVG string.
    """
    return _compose(bg_svg, pose, char_dir)


def compose_and_save(
    page,
    bg_svg: str,
    char_dir: Path,
    pages_dir: Path,
    force: bool = False,
) -> Path:
    """Compose and save output/pages/page_N.svg, skipping if cached.

    Args:
        page:      A Page schema instance (needs .page_no and .pose).
        bg_svg:    Background SVG string.
        char_dir:  Directory containing character SVGs.
        pages_dir: Directory to write page SVGs into.
        force:     If True, overwrite even if the file exists.

    Returns:
        Path to the saved (or pre-existing) page SVG.
    """
    pages_dir.mkdir(parents=True, exist_ok=True)
    out_path = pages_dir / f"page_{page.page_no}.svg"

    if not bg_svg or not bg_svg.strip():
        raise ValueError(f"Background SVG for page {page.page_no} is empty — cannot compose.")

    if out_path.is_file() and not force:
        logger.info("Page %d SVG already exists — skipping composition.", page.page_no)
        return out_path

    composed = _compose(bg_svg, page.pose, char_dir)
    out_path.write_text(composed, encoding="utf-8")
    logger.info("Saved composed page %d -> %s", page.page_no, out_path)
    return out_path