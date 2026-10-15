from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

W, H = A4
M = 40
BG = HexColor("#FFF9EE")
INK = HexColor("#3A3A3A")
ACCENT = HexColor("#5B7CFA")


def _draw_svg(c, path, x, y_top, width):
    d = svg2rlg(path)
    s = width / d.width
    h = d.height * s
    d.scale(s, s)
    d.width, d.height = width, h
    renderPDF.draw(d, c, x, y_top - h)
    return h


def _bg(c):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, stroke=0, fill=1)


def build_pdf(story, out_path="output/storybook.pdf"):
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setTitle(story.title)

    # Cover
    _bg(c)
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 30)
    y = H - 110
    for ln in simpleSplit(story.title, "Helvetica-Bold", 30, W - 2 * M):
        c.drawCentredString(W / 2, y, ln)
        y -= 38
    h = _draw_svg(c, "output/characters/character_standing.svg", W / 2 - 110, y - 30, 220)
    c.setFillColor(INK)
    c.setFont("Helvetica", 14)
    c.drawCentredString(W / 2, y - 60 - h, f"A story about {story.character.name}")
    c.showPage()

    # Story pages
    for p in story.pages:
        _bg(c)
        h = _draw_svg(c, f"output/pages/page_{p.page_no}.svg", M, H - M, W - 2 * M)
        y = H - M - h - 40
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(M, y, p.title)
        y -= 32
        c.setFillColor(INK)
        c.setFont("Helvetica", 15)
        for ln in simpleSplit(p.text, "Helvetica", 15, W - 2 * M):
            c.drawString(M, y, ln)
            y -= 23
        c.setFont("Helvetica", 10)
        c.drawCentredString(W / 2, 22, f"- {p.page_no} -")
        c.showPage()

    c.save()
    return out_path