# Storybook Agent

An AI agent that takes a single prompt and produces a 5-page illustrated
children's story as a clean PDF, with a visually consistent main character.

## Pipeline
1. Planner: prompt -> structured story JSON (5-page arc, character bible
   with a fixed hex palette, one pose per page), validated with Pydantic
2. Character designer: LLM generates one SVG head + 5 body poses, validated
   against the palette
3. Scene generator: per-page background SVG (no characters), validated
4. Compositor: places the character SVG on each background
5. PDF builder: cover + 5 pages using ReportLab + svglib

## How character consistency is achieved
The character is generated ONCE. The same head SVG is reused in every pose,
and the same pose file is inserted unchanged on every page. The character is
never regenerated per page, so it cannot drift.

## Setup
pip install -r requirements.txt
copy .env.example .env   (then add GEMINI_API_KEY and model names)
python main.py "<your prompt>"
python run_m4.py
python run_pdf.py
Output: output/storybook.pdf

## Why SVG instead of generated images
Image-generation quota was unavailable on my API key, and diffusion models do
not guarantee the same character across pages. The SVG approach guarantees
consistency by construction.

## Limitations
- Flat vector style, not painted illustrations
- LLM-generated SVGs can occasionally need a regeneration (delete the file in
  output/backgrounds and rerun)
- No vision-based consistency scoring yet; consistency is structural
- Pipeline runs as 3 commands (not yet merged into one)

## Sample
samples/storybook_sample.pdf