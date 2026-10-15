"""Background SVG generator for the Storybook Agent (M4).

generate_background(page, bible) -> str
  Asks TEXT_MODEL for a single 800x600 SVG showing only the scene setting.
  Validates with xml.etree; retries up to 2 times on failure.

Routes through agent/llm.py so the backend is provider-agnostic.
"""

import re
import logging
import xml.etree.ElementTree as ET

from agent.llm import generate_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tags banned from background SVGs (gradients OK per spec – "defs + linearGradient" allowed;
# but forbidden for PDF compatibility, so we keep the user's conservative set).
# Tags banned from background SVGs.
# linearGradient/radialGradient are ALLOWED per SPEC ("defs + linearGradient").
# PDF rendering concern is handled at the pdf_builder milestone.
BANNED: set[str] = {
    "filter", "mask", "image", "script", "foreignobject",
    "text", "tspan", "style", "a",
}

SYSTEM_INSTRUCTION = """\
You draw backgrounds for a children's picture book as ONE SVG.

RULES (violations will be auto-rejected, costing you a retry):
- viewBox must be exactly "0 0 800 600"; include xmlns="http://www.w3.org/2000/svg".
- Show ONLY the scene setting. NO people, NO characters, NO animals in the
  foreground, NO text, NO letters anywhere.
- Ground line at y=520. Keep the bottom-center area (x 250-550, y 220-520)
  visually calm and uncluttered — a character will be composited there.
- Allowed elements: rect, circle, ellipse, path, polygon, polyline, g, defs,
  linearGradient, radialGradient (gradients must be defined inside <defs>).
- BANNED elements: filter, mask, image, script, foreignObject, text, tspan,
  style, <a>.
- Flat fills OR simple gradient fills (opacity allowed). No drop-shadows,
  no blur filters, no pattern fills.
- Soft pastel children's-storybook look: layered sky / far hills / mid /
  near ground shapes. Rich scene, not blank.

Return ONLY the raw SVG code. No explanation, no markdown fences, no comments
outside the SVG."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(raw: str) -> str:
    """Extract the first <svg>…</svg> block and ensure xmlns is present."""
    m = re.search(r"<svg[\s\S]*?</svg>", raw, re.S)
    if not m:
        raise ValueError("no <svg>...</svg> found in the model response")
    svg = m.group(0)
    # Ensure namespace declaration so ET can parse it
    first_tag = svg.split(">")[0]
    if "xmlns=" not in first_tag:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg


def _validate(svg: str) -> None:
    """Parse with xml.etree and raise ValueError on any rule violation."""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise ValueError(f"XML parse error: {exc}") from exc

    if "viewBox" not in root.attrib:
        raise ValueError("missing viewBox attribute on <svg>")

    for el in root.iter():
        tag = el.tag.split("}")[-1].lower()  # strip namespace prefix
        if tag in BANNED:
            raise ValueError(f"banned element <{tag}> found in SVG")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_background(page, bible) -> str:
    """Generate a background SVG for *page* using *bible.art_style*.

    Args:
        page:  A Page schema instance (needs .scene_description, .page_no).
        bible: A CharacterBible instance (needs .art_style).

    Returns:
        A validated SVG string (viewBox 0 0 800 600).

    Raises:
        RuntimeError: If all 3 attempts fail.
    """
    base_prompt = (
        f"Page {page.page_no} setting: {page.scene_description}\n"
        f"Art style: {bible.art_style}\n"
        "Draw the background SVG now."
    )

    accumulated_err = ""
    last_exc: Exception | None = None

    for attempt in range(3):  # 1 initial + 2 retries
        prompt = base_prompt + accumulated_err
        try:
            raw = generate_text(
                prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="text/plain",
            )
            svg = _clean(raw)
            _validate(svg)
            logger.info("Background page %d OK on attempt %d", page.page_no, attempt + 1)
            return svg
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Background page %d attempt %d failed: %s",
                page.page_no, attempt + 1, exc,
            )
            accumulated_err = (
                f"\n\nYour previous answer was rejected with this error: {exc}\n"
                "Fix ONLY that problem and return the corrected SVG — nothing else."
            )

    raise RuntimeError(
        f"Background generation failed for page {page.page_no} after 3 attempts: {last_exc}"
    )