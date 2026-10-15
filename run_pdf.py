from agent.schemas import Story
# pyrefly: ignore [missing-import]
from agent.pdf_builder import build_pdf

story = Story.model_validate_json(open("output/story.json", encoding="utf-8").read())
print("PDF:", build_pdf(story))