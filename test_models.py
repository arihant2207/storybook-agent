import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
os.makedirs("output", exist_ok=True)
c = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("--- TEXT MODELS ---")
for m in ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3.6-flash",
          "gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]:
    try:
        r = c.models.generate_content(model=m, contents="say hi")
        print("OK  ", m, "->", r.text.strip()[:30])
    except Exception as e:
        print("FAIL", m, "->", str(e)[:150])

print("--- IMAGE MODELS ---")
for m in ["gemini-2.5-flash-image", "gemini-3.1-flash-image"]:
    try:
        r = c.models.generate_content(
            model=m,
            contents="a cartoon girl in a yellow raincoat, watercolor children's book style",
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        saved = False
        for p in r.candidates[0].content.parts:
            if p.inline_data:
                open(f"output/test_{m}.png", "wb").write(p.inline_data.data)
                saved = True
        print("OK  " if saved else "NOIMG", m)
    except Exception as e:
        print("FAIL", m, "->", str(e)[:150])