import os
from pathlib import Path
from rich import print
from agent.schemas import Story
from agent.scene import generate_background
from agent.compose import compose_page

story = Story.model_validate_json(open("output/story.json", encoding="utf-8").read())
os.makedirs("output/backgrounds", exist_ok=True)
os.makedirs("output/pages", exist_ok=True)

char_dir = Path("output/characters")

for p in story.pages:
    bg_path = f"output/backgrounds/bg_{p.page_no}.svg"
    if not os.path.exists(bg_path) or os.path.getsize(bg_path) == 0:
        print(f"[cyan]Generating background {p.page_no}: {p.title}[/cyan]")
        open(bg_path, "w", encoding="utf-8").write(generate_background(p, story.character))
    bg = open(bg_path, encoding="utf-8").read()
    # compose har baar chalta hai (sasta hai), taaki FOOT_OFFSET tune karna aasan ho
    open(f"output/pages/page_{p.page_no}.svg", "w", encoding="utf-8").write(
        compose_page(bg, p.pose, char_dir)
    )

cards = "".join(
    f'<div><img src="pages/page_{p.page_no}.svg" width="400"><p>{p.page_no}. {p.title} ({p.pose})</p></div>'
    for p in story.pages)
open("output/pages_preview.html", "w", encoding="utf-8").write(
    '<body style="font-family:sans-serif;display:grid;'
    f'grid-template-columns:repeat(auto-fill,420px);gap:16px;padding:16px">{cards}</body>')
print("[green]Done -> output/pages_preview.html[/green]")