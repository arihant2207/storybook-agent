# SPEC.md: Storybook Agent

## 1. Goal
Build a Python AI agent that takes ONE text prompt and produces a clean,
downloadable PDF: a 5-page illustrated children's book story outline.
The main character MUST look visually consistent on every page.

Demo prompt: "Create a five-page children's book story outlining a young,
brave character discovering a hidden, magical garden."
The agent must work for ANY prompt, not just this one.

## 2. Hard Requirements
- Input: single prompt string (CLI argument; optional Streamlit UI later)
- Output: `output/storybook.pdf` with a cover + exactly 5 story pages
- Each story page: one illustration, a short title, 2-3 simple sentences
- Main character graphically consistent across all pages
- Child-friendly content only (no violence, no scary imagery)
- No text rendered inside generated images; all text is overlaid in the PDF
- API keys only via `.env`, never hardcoded

## 3. Pipeline
1. Planner: prompt -> Story JSON (character bible + 5 pages)
2. Character Designer: bible -> reference image (character sheet)
3. Illustrator: for each page, generate image using reference image
   + bible + scene description + fixed style suffix
4. Consistency Checker: vision model compares page image vs reference,
   returns score 1-10 and issues; retry up to 2 times if score < 7
5. PDF Builder: assemble cover + 5 pages into the final PDF

## 4. Tech Stack
- Python 3.11+
- `google-genai` SDK (text, vision, image generation)
- `pydantic` (schemas, structured output validation)
- `reportlab` (PDF), `Pillow` (image handling)
- `python-dotenv`, `tenacity` (retries), `rich` (nice CLI logs)
- Model names must come from env vars, never hardcoded:
  TEXT_MODEL, VISION_MODEL, IMAGE_MODEL

## 5. Folder Structure
```
storybook-agent/
├── main.py
├── agent/
│   ├── __init__.py
│   ├── config.py
│   ├── schemas.py
│   ├── planner.py
│   ├── character.py
│   ├── illustrator.py
│   ├── checker.py
│   └── pdf_builder.py
├── output/            # generated files (gitignored except samples)
├── samples/           # final sample PDF committed here
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 6. Schemas (agent/schemas.py)
CharacterBible:
- name: str
- age_description: str          (e.g. "about 7 years old")
- hair: str                     (style + color)
- eyes: str
- skin_tone: str
- outfit: str                   (exact clothes + colors, fixed)
- signature_item: str           (e.g. "small brass lantern")
- art_style: str                (e.g. "soft watercolor, warm palette")

Page:
- page_no: int (1-5)
- title: str
- text: str                     (2-3 simple sentences)
- scene_description: str        (what to draw; NO character appearance
                                 details here, those come from the bible)

Story:
- title: str
- character: CharacterBible
- pages: list[Page]             (exactly 5, validated)

CheckResult:
- score: int (1-10)
- issues: list[str]

## 7. Module Specs

### planner.py
`plan_story(prompt: str) -> Story`
- Call TEXT_MODEL with structured JSON output matching Story schema
- Story arc: p1 meet character, p2 discover the clue/entrance,
  p3 face a small challenge, p4 magical discovery, p5 happy ending
- Language simple, warm, age 4-8
- Validate with pydantic; retry once on invalid JSON

### character.py
`create_reference(bible: CharacterBible) -> str` (returns image path)
- Generate one full-body character sheet on a plain light background
- Save to `output/character_ref.png`
- Skip generation if the file already exists (cache)

### illustrator.py
`illustrate_page(page, bible, ref_path) -> str`
- Prompt = STYLE_SUFFIX + bible fields (verbatim, same wording every page)
  + page.scene_description + "no text, no letters, no watermark"
- Pass reference image as input and instruct: "same character as the
  reference image, same face, hair, outfit, and colors"
- Save to `output/page_{n}.png`; skip if exists (cache)

### checker.py
`check_consistency(ref_path, page_path, bible) -> CheckResult`
- Send both images to VISION_MODEL
- Compare hair, face, outfit, colors, signature item, art style
- Return strict JSON matching CheckResult

### pdf_builder.py
`build_pdf(story, page_images, out_path)`
- Page size A4 portrait (or 8.5x8.5in square, pick one and stay consistent)
- Cover: story title + character reference image
- Each page: illustration (top ~70%), page title, text (bottom),
  readable font size (>= 14pt), page number, generous margins
- Register a clean font; do not clip or overflow text

### main.py
- `python main.py "<prompt>"` runs the full pipeline
- Retry loop: if check score < 7, regenerate that page (max 2 retries),
  keep the best-scoring attempt
- Print progress with rich; print the final PDF path
- Log consistency scores per page to `output/report.json`

## 8. Consistency Strategy (core of the project)
1. Character Bible text injected identically into every prompt
2. Reference image passed into every page generation
3. Fixed STYLE_SUFFIX constant used for all images
4. Vision-based checker with automatic retry
Document this clearly in README.

## 9. Error Handling
- Retry API calls with exponential backoff (tenacity)
- Clear error message if API key missing
- If one page fails after retries, keep best attempt and warn, don't crash
- Cache generated images so re-runs do not burn quota

## 10. Out of Scope
Web hosting, user accounts, databases, multiple languages, audio.

## 11. Definition of Done
- `python main.py "<demo prompt>"` produces output/storybook.pdf
- Character visibly the same on all 5 pages
- Works on at least 3 different prompts
- README with setup, architecture, consistency approach, limitations
- Sample PDF committed in samples/

## 12. Build Order (IMPORTANT)
Implement ONLY the milestone requested, then stop and wait.
M1: skeleton + config + schemas
M2: planner (print Story JSON)
M3: character reference image
M4: illustrator
M5: checker + retry loop
M6: pdf_builder
M7: main.py wiring, README, samples
