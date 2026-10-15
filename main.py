"""Main entry point for Storybook Agent.

Usage
-----
    python main.py "<prompt>"          # use cache if available
    python main.py "<prompt>" --fresh  # always regenerate
    python main.py                     # default demo prompt, cache-aware
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure Rich (and any print) can output Unicode on Windows terminals.
os.environ.setdefault("PYTHONUTF8", "1")
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel

DEFAULT_DEMO_PROMPT = (
    "Create a five-page children's book story outlining a young, brave "
    "character discovering a hidden, magical garden."
)

POSE_NAMES = ["standing", "crouch", "hop", "arms_up", "sit"]


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _story_cached(output_dir: Path) -> bool:
    """Return True if a valid story.json exists in output_dir."""
    p = output_dir / "story.json"
    return p.is_file() and p.stat().st_size > 0


def _characters_cached(output_dir: Path) -> bool:
    """Return True if all 5 pose SVGs exist under output_dir/characters/."""
    char_dir = output_dir / "characters"
    return all((char_dir / f"character_{pose}.svg").is_file() for pose in POSE_NAMES)


def _pages_cached(output_dir: Path) -> bool:
    """Return True if all 5 page_N.svg files exist and are non-empty."""
    pages_dir = output_dir / "pages"
    return all(
        (pages_dir / f"page_{n}.svg").is_file()
        and (pages_dir / f"page_{n}.svg").stat().st_size > 0
        for n in range(1, 6)
    )


def _load_story(output_dir: Path):
    """Load and validate Story from the cached story.json."""
    from agent.schemas import Story
    data = json.loads((output_dir / "story.json").read_text(encoding="utf-8"))
    return Story.model_validate(data)


def _cached_svg_paths(output_dir: Path) -> dict:
    """Return {pose: path_str} for all cached SVG files."""
    char_dir = output_dir / "characters"
    return {pose: str(char_dir / f"character_{pose}.svg") for pose in POSE_NAMES}


def _write_pages_preview(story, output_dir: Path) -> Path:
    """Write output/pages_preview.html with all 5 pages inline as a grid."""
    pages_dir = output_dir / "pages"
    preview_path = output_dir / "pages_preview.html"

    cards_html = ""
    for page in story.pages:
        svg_path = pages_dir / f"page_{page.page_no}.svg"
        try:
            svg_content = svg_path.read_text(encoding="utf-8")
        except OSError:
            svg_content = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 600'><rect width='800' height='600' fill='#eee'/></svg>"

        cards_html += f"""
      <div class="card">
        <div class="page-wrap">{svg_content}</div>
        <div class="caption">
          <span class="page-num">Page {page.page_no}</span>
          <span class="page-title">{page.title}</span>
          <span class="pose-tag">{page.pose}</span>
        </div>
      </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Page Preview - {story.title}</title>
  <style>
    :root {{
      --bg: #1a1a2e; --card: #16213e; --accent: #e94560;
      --text: #eee; --sub: #aaa; --r: 14px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      font-family: "Segoe UI", system-ui, sans-serif;
      color: var(--text);
      padding: 40px 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 32px;
    }}
    h1 {{ font-size: 1.8rem; text-align: center; }}
    h1 em {{ color: var(--accent); font-style: normal; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(440px, 1fr));
      gap: 28px;
      width: 100%;
      max-width: 1400px;
    }}
    .card {{
      background: var(--card);
      border-radius: var(--r);
      overflow: hidden;
      box-shadow: 0 8px 32px rgba(0,0,0,.4);
      transition: transform .2s, box-shadow .2s;
    }}
    .card:hover {{
      transform: translateY(-4px);
      box-shadow: 0 16px 48px rgba(233,69,96,.25);
    }}
    .page-wrap {{ width: 100%; aspect-ratio: 4/3; overflow: hidden; }}
    .page-wrap svg {{ width: 100%; height: 100%; display: block; }}
    .caption {{
      padding: 14px 18px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .page-num {{
      background: var(--accent);
      color: #fff;
      font-size: .75rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 20px;
      flex-shrink: 0;
    }}
    .page-title {{ font-weight: 600; font-size: .95rem; flex: 1; }}
    .pose-tag {{
      font-size: .72rem;
      color: var(--sub);
      background: rgba(255,255,255,.06);
      padding: 2px 7px;
      border-radius: 10px;
    }}
  </style>
</head>
<body>
  <h1><em>{story.title}</em> — Page Previews</h1>
  <div class="grid">
    {cards_html}
  </div>
</body>
</html>
"""
    preview_path.write_text(html, encoding="utf-8")
    return preview_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    console = Console(legacy_windows=False)

    parser = argparse.ArgumentParser(
        description="Storybook Agent - Plan and outline a 5-page children's book."
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Story prompt or idea. Omit to use the default demo prompt.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore any cached outputs and regenerate everything from scratch.",
    )
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip() if args.prompt else DEFAULT_DEMO_PROMPT
    if not args.prompt:
        console.print(
            "[dim yellow]No prompt provided. Using default demo prompt.[/dim yellow]\n"
        )

    console.print(
        Panel.fit(
            f"[bold cyan]Prompt:[/bold cyan] {prompt}",
            title="[bold magenta]Storybook Agent[/bold magenta]",
            border_style="magenta",
        )
    )

    try:
        from agent import config
        from agent.character import create_character
        from agent.compose import compose_and_save
        from agent.planner import plan_story
        from agent.scene import generate_background

        output_dir: Path = config.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        story_ok  = _story_cached(output_dir)
        chars_ok  = _characters_cached(output_dir)
        pages_ok  = _pages_cached(output_dir)
        use_cache = (story_ok and chars_ok and pages_ok) and not args.fresh

        # ── Mode banner ──────────────────────────────────────────────────────
        if use_cache:
            console.print(
                Panel.fit(
                    "[bold green]>> CACHED mode[/bold green]  --  "
                    "Loading story.json + characters/*.svg + pages/*.svg from disk.\n"
                    "[dim]Pass [bold]--fresh[/bold] to regenerate.[/dim]",
                    border_style="green",
                )
            )
        else:
            reasons = []
            if args.fresh:
                reasons.append("--fresh flag set")
            else:
                if not story_ok:
                    reasons.append("story.json not found")
                if not chars_ok:
                    reasons.append("character SVGs missing")
                if not pages_ok:
                    reasons.append("page SVGs missing")
            console.print(
                Panel.fit(
                    "[bold yellow]>> FRESH mode[/bold yellow]  --  "
                    f"Regenerating from scratch ({', '.join(reasons)}).",
                    border_style="yellow",
                )
            )

        # ── Story ────────────────────────────────────────────────────────────
        if use_cache and story_ok:
            with console.status("[bold green]Loading story from cache...[/bold green]"):
                story = _load_story(output_dir)
            console.print("[bold green][OK] Story loaded from cache.[/bold green]")
        else:
            with console.status("[bold green]Planning story with AI...[/bold green]"):
                story = plan_story(prompt)
            story_file = output_dir / "story.json"
            story_file.write_text(story.model_dump_json(indent=2), encoding="utf-8")
            console.print(
                f"[bold green][OK] Story planned and saved ->[/bold green] "
                f"[underline]{story_file}[/underline]"
            )

        console.print_json(data=story.model_dump())

        # ── Characters ───────────────────────────────────────────────────────
        if use_cache and chars_ok:
            svg_paths = _cached_svg_paths(output_dir)
            console.print(
                "[bold green][OK] Character SVGs loaded from cache:[/bold green] "
                + ", ".join(svg_paths.keys())
            )
        else:
            with console.status(
                "[bold green]Generating SVG character poses...[/bold green]"
            ):
                svg_paths = create_character(story.character)
            console.print(
                "[bold green][OK] Character SVGs generated:[/bold green] "
                + ", ".join(svg_paths.keys())
            )
            console.print(
                f"[bold blue]Preview ->[/bold blue] "
                f"[underline]{output_dir / 'character_preview.html'}[/underline]"
            )

        # ── Backgrounds + Page Composition ───────────────────────────────────
        char_dir  = output_dir / "characters"
        bg_dir    = output_dir / "backgrounds"
        pages_dir = output_dir / "pages"
        bg_dir.mkdir(parents=True, exist_ok=True)
        pages_dir.mkdir(parents=True, exist_ok=True)

        if use_cache and pages_ok:
            console.print(
                "[bold green][OK] Page SVGs loaded from cache:[/bold green] "
                + " ".join(f"page_{n}.svg" for n in range(1, 6))
            )
        else:
            for page in story.pages:
                # -- Background (per-page cache) -----------------------------
                bg_path = bg_dir / f"bg_{page.page_no}.svg"
                if bg_path.is_file() and bg_path.stat().st_size > 0 and not args.fresh:
                    console.print(
                        f"[dim]  Page {page.page_no}: background cached.[/dim]"
                    )
                    bg_svg = bg_path.read_text(encoding="utf-8")
                else:
                    with console.status(
                        f"[bold cyan]  Page {page.page_no}/{len(story.pages)}: "
                        f"generating background '{page.title}'...[/bold cyan]"
                    ):
                        bg_svg = generate_background(page, story.character)
                    bg_path.write_text(bg_svg, encoding="utf-8")
                    console.print(
                        f"[bold cyan]  Page {page.page_no}: background saved.[/bold cyan]"
                    )

                # -- Compose (always fast — just string ops) -----------------
                page_path = compose_and_save(
                    page, bg_svg, char_dir, pages_dir, force=args.fresh
                )
                console.print(
                    f"[bold green]  Page {page.page_no} composed -> "
                    f"[underline]{page_path.name}[/underline][/bold green]"
                )

        preview_path = _write_pages_preview(story, output_dir)
        console.print(
            f"[bold blue]Pages preview ->[/bold blue] "
            f"[underline]{preview_path}[/underline]"
        )

    except ValueError as e:
        console.print(f"\n[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise


if __name__ == "__main__":
    main()
