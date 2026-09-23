"""Build six root-level PDFs from maintained sources and real screenshot files.

Host setup: python -m pip install -r requirements-pdf.txt
Run: python scripts/build-submission-pdfs.py
Screenshots are loaded from screenshots/ first, with project-root fallback.
"""

import html
import json
import re
from io import BytesIO
from pathlib import Path

from markdown_it import MarkdownIt
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "submission"
PAGE_W, PAGE_H = A4
WIDTH = PAGE_W - 88
INK = colors.HexColor("#17324d")
TEAL = colors.HexColor("#087f8c")
PALE = colors.HexColor("#edf5f7")
GRAY = colors.HexColor("#586577")
MD = MarkdownIt("commonmark").enable("table")


def font_setup():
    windows = Path("C:/Windows/Fonts")
    names = {
        "Body": "arial.ttf",
        "Body-Bold": "arialbd.ttf",
        "Body-Italic": "ariali.ttf",
        "Body-BoldItalic": "arialbi.ttf",
        "Code": "consola.ttf",
    }
    if all((windows / name).exists() for name in names.values()):
        for alias, filename in names.items():
            pdfmetrics.registerFont(TTFont(alias, str(windows / filename)))
        pdfmetrics.registerFontFamily(
            "Body",
            normal="Body",
            bold="Body-Bold",
            italic="Body-Italic",
            boldItalic="Body-BoldItalic",
        )
        return "Body", "Body-Bold", "Code"
    return "Helvetica", "Helvetica-Bold", "Courier"


BODY, BOLD, CODE = font_setup()
styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        "Text",
        fontName=BODY,
        fontSize=9.5,
        leading=13.6,
        textColor=INK,
        spaceAfter=7,
        splitLongWords=True,
    )
)
styles.add(ParagraphStyle("SmallText", parent=styles["Text"], fontSize=8, leading=11))
styles.add(
    ParagraphStyle(
        "MonoBlock",
        fontName=CODE,
        fontSize=8,
        leading=11.5,
        backColor=PALE,
        borderPadding=9,
        spaceBefore=5,
        spaceAfter=12,
        textColor=INK,
        splitLongWords=True,
    )
)
styles.add(
    ParagraphStyle(
        "Section",
        fontName=BOLD,
        fontSize=15,
        leading=19,
        textColor=TEAL,
        spaceBefore=17,
        spaceAfter=9,
        keepWithNext=True,
    )
)
styles.add(ParagraphStyle("Subsection", parent=styles["Section"], fontSize=11.5, leading=15))
styles.add(
    ParagraphStyle("DocTitle", fontName=BOLD, fontSize=26, leading=31, textColor=INK, spaceAfter=12)
)
styles.add(
    ParagraphStyle(
        "CardTitle",
        fontName=BOLD,
        fontSize=10,
        leading=14,
        textColor=TEAL,
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True,
    )
)


def clean(text):
    return text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", " - ")


def link_target(target):
    mappings = {
        "README.md": "README.pdf",
        "report.md": "REPORT.pdf",
        "VERIFICATION.md": "VERIFICATION.pdf",
        "VIVA-NOTES.md": "VIVA-NOTES.pdf",
        "ASSIGNMENT-CHECKLIST.md": "ASSIGNMENT-CHECKLIST.pdf",
        "DEMO-CHECKLIST.md": "SCREENSHOT-CHECKLIST.pdf",
    }
    bare = target.split("#")[0]
    if bare.endswith(".md") and Path(bare).name in mappings:
        return "http://localhost:8011/" + mappings[Path(bare).name]
    if target.startswith(("http://", "https://")):
        return target
    return None


def inline(tokens):
    chunks = []
    link_stack = []
    for token in tokens or []:
        kind = token.type
        if kind == "text":
            value = html.escape(clean(token.content))
            if not any(link_stack):
                value = re.sub(
                    r"https?://\S+",
                    lambda match: f'<a href="{match[0]}" color="#087f8c">{match[0]}</a>',
                    value,
                )
            chunks.append(value)
        elif kind == "code_inline":
            chunks.append(
                f'<font name="{CODE}" size="8">{html.escape(clean(token.content))}</font>'
            )
        elif kind == "strong_open":
            chunks.append("<b>")
        elif kind == "strong_close":
            chunks.append("</b>")
        elif kind == "em_open":
            chunks.append("<i>")
        elif kind == "em_close":
            chunks.append("</i>")
        elif kind == "link_open":
            target = link_target(token.attrGet("href"))
            link_stack.append(bool(target))
            if target:
                chunks.append(f'<a href="{html.escape(target, quote=True)}" color="#087f8c">')
        elif kind == "link_close":
            if link_stack.pop():
                chunks.append("</a>")
        elif kind in ("softbreak", "hardbreak"):
            chunks.append("<br/>" if kind == "hardbreak" else " ")
        elif kind == "html_inline":
            chunks.append(html.escape(token.content))
    return "".join(chunks)


def para(text, style="Text"):
    return Paragraph(text, styles[style])


class Architecture(Flowable):
    """Vector architecture lanes; labels explicitly distinguish push/pull directions."""

    def __init__(self):
        super().__init__()
        self.width, self.height = WIDTH, 218

    def draw(self):
        c = self.canv
        lanes = [
            (
                "BUSINESS",
                ["Client / k6", "FastAPI", "PostgreSQL"],
                "HTTP JSON",
                "SQL / transactions",
            ),
            (
                "METRICS",
                ["App + Node Exporter", "Prometheus", "Grafana"],
                "Prometheus scrapes",
                "Grafana queries",
            ),
            (
                "LOGS",
                ["App JSONL / Filebeat", "Elasticsearch", "Kibana"],
                "Filebeat pushes",
                "Kibana searches",
            ),
        ]
        for row, (label, nodes, first, second) in enumerate(lanes):
            y = 161 - row * 66
            c.setFillColor(TEAL)
            c.setFont(BOLD, 8)
            c.drawString(0, y + 38, label)
            for col, name in enumerate(nodes):
                x = col * 183
                c.setFillColor(PALE)
                c.setStrokeColor(colors.HexColor("#c7dce3"))
                c.roundRect(x, y, 137, 31, 5, stroke=1, fill=1)
                c.setFillColor(INK)
                c.setFont(BOLD, 8)
                c.drawCentredString(x + 68.5, y + 12, name)
            for col, caption in enumerate((first, second)):
                x = 137 + col * 183
                c.setStrokeColor(TEAL)
                c.line(x + 2, y + 15, x + 43, y + 15)
                # Flow lane depicts data delivery; caption names the initiating reader.
                c.line(x + 39, y + 18, x + 43, y + 15)
                c.line(x + 39, y + 12, x + 43, y + 15)
                c.setFont(BODY, 6.5)
                c.setFillColor(GRAY)
                c.drawCentredString(x + 23, y - 10, caption)
        c.setFont(BODY, 7)
        c.drawString(
            0, 0, "Named Docker volumes preserve data. k6 also pushes test metrics to Prometheus."
        )


def render_table(rows):
    count = len(rows[0])
    if count >= 5:
        # Wide technical tables become readable requirement/metric cards.
        output = []
        headers = rows[0]
        for row in rows[1:]:
            card = [para(row[0], "CardTitle")]
            for label, value in zip(headers[1:], row[1:], strict=False):
                card.append(para(f"<b>{label}:</b> {value}", "SmallText"))
            output.append(KeepTogether(card))
        return output
    widths = [WIDTH / count] * count
    if count == 2:
        widths = [WIDTH * 0.28, WIDTH * 0.72]
    elif count == 3:
        widths = [WIDTH * 0.23, WIDTH * 0.34, WIDTH * 0.43]
    cells = [[para(value, "SmallText") for value in row] for row in rows]
    table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PALE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, TEAL),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#dbe4ea")),
            ]
        )
    )
    return [table, Spacer(1, 9)]


def markdown_story(text):
    tokens = MD.parse(text)
    story, i, list_depth, ordered = [], 0, 0, []
    while i < len(tokens):
        token = tokens[i]
        if token.type == "heading_open":
            value = inline(tokens[i + 1].children)
            story.append(para(value, "Section" if token.tag in ("h1", "h2") else "Subsection"))
            i += 3
            continue
        if token.type in ("bullet_list_open", "ordered_list_open"):
            list_depth += 1
            ordered.append(1 if token.type == "ordered_list_open" else None)
        elif token.type in ("bullet_list_close", "ordered_list_close"):
            list_depth -= 1
            ordered.pop()
        elif token.type == "paragraph_open":
            value = inline(tokens[i + 1].children)
            if list_depth:
                prefix = "- " if ordered[-1] is None else str(ordered[-1]) + ". "
                if ordered[-1] is not None:
                    ordered[-1] += 1
                value = prefix + value
            story.append(para(value))
            i += 3
            continue
        elif token.type == "fence":
            if token.info.strip() == "mermaid":
                story.append(Architecture())
            else:
                content = html.escape(clean(token.content.rstrip())).replace("\n", "<br/>")
                story.append(KeepTogether([para(content, "MonoBlock")]))
        elif token.type == "table_open":
            rows, current = [], []
            i += 1
            while tokens[i].type != "table_close":
                if tokens[i].type == "tr_open":
                    current = []
                elif tokens[i].type == "inline":
                    current.append(inline(tokens[i].children))
                elif tokens[i].type == "tr_close":
                    rows.append(current)
                i += 1
            story.extend(render_table(rows))
        elif token.type == "hr":
            story.append(Spacer(1, 8))
        i += 1
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#c7dce3"))
    canvas.line(44, 38, PAGE_W - 44, 38)
    canvas.setFont(BODY, 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(44, 25, "Campus Room Booking | Assignment 1")
    canvas.drawRightString(PAGE_W - 44, 25, f"Page {doc.page}")
    canvas.restoreState()


def build(name, title, story, date):
    path = ROOT / (name + ".pdf")
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=44,
        leftMargin=44,
        topMargin=43,
        bottomMargin=54,
        title=title,
        author="Campus Room Booking Project",
    )
    header = [
        para("CAMPUS ROOM BOOKING", "CardTitle"),
        para(title, "DocTitle"),
        para(
            f"Verified Docker Desktop run | {date} | UTC and Pakistan Standard Time (UTC+05:00)",
            "SmallText",
        ),
        Spacer(1, 9),
    ]
    document.build(header + story, onFirstPage=footer, onLaterPages=footer)
    return path


def append_screenshots(path, shots):
    """Append unchanged, full-resolution screenshots on individual landscape pages."""
    reader = PdfReader(path)
    writer = PdfWriter()
    writer.append(reader)
    start = len(reader.pages)
    for index, shot in enumerate(shots, 1):
        image = ROOT / "screenshots" / shot["filename"]
        if not image.is_file():
            image = ROOT / shot["filename"]
        if not image.is_file():
            raise FileNotFoundError(f"Missing screenshot: {shot['filename']}")
        stream = BytesIO()
        width, height = PAGE_H, PAGE_W
        canvas = pdfcanvas.Canvas(stream, pagesize=(width, height))
        canvas.setFillColor(INK)
        canvas.setFont(BOLD, 13)
        canvas.drawString(44, height - 38, f"Evidence {index:02d}: {shot['filename']}")
        caption = para(html.escape(shot["why"]), "SmallText")
        _, caption_height = caption.wrap(width - 88, 60)
        caption.drawOn(canvas, 44, height - 54 - caption_height)
        source = ImageReader(str(image))
        iw, ih = source.getSize()
        available_height = height - 135 - caption_height
        scale = min((width - 88) / iw, available_height / ih)
        dw, dh = iw * scale, ih * scale
        canvas.drawImage(
            source,
            (width - dw) / 2,
            65 + (available_height - dh) / 2,
            width=dw,
            height=dh,
            mask="auto",
        )
        canvas.setStrokeColor(colors.HexColor("#c7dce3"))
        canvas.line(44, 38, width - 44, 38)
        canvas.setFont(BODY, 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(44, 25, "Campus Room Booking | Original user-captured screenshot")
        canvas.drawRightString(width - 44, 25, f"Page {start + index}")
        canvas.save()
        stream.seek(0)
        writer.append(PdfReader(stream))
    writer.add_metadata(
        {
            "/Title": "Assignment report: Parts A-E with screenshot evidence",
            "/Author": "Campus Room Booking Project",
        }
    )
    with path.open("wb") as output:
        writer.write(output)


def main():
    manifest = json.loads((SOURCE / "latest.json").read_text(encoding="utf-8"))
    outputs = []
    for name, title, source in (
        ("README", "Setup and usage guide", ROOT / "README.md"),
        ("REPORT", "Assignment report: Parts A-E", SOURCE / "REPORT.md"),
        (
            "ASSIGNMENT-CHECKLIST",
            "Assignment requirement checklist",
            SOURCE / "ASSIGNMENT-CHECKLIST.md",
        ),
        ("VIVA-NOTES", "Viva preparation notes", ROOT / "docs/VIVA-NOTES.md"),
        ("VERIFICATION", "Fresh verification results", SOURCE / "VERIFICATION.md"),
    ):
        story = markdown_story(source.read_text(encoding="utf-8"))
        if name == "VIVA-NOTES":
            story = [
                KeepTogether([item]) if isinstance(item, Paragraph) else item for item in story
            ]
        output = build(name, title, story, manifest["date"])
        if name == "REPORT":
            append_screenshots(output, manifest["screenshots"])
        outputs.append(output)
    # One shared source for PDF and plain text: identical words and steps.
    checklist = (ROOT / "SCREENSHOT-CHECKLIST.txt").read_text(encoding="utf-8")
    story = []
    for block in checklist.split("\n\n"):
        if not block.strip():
            continue
        section = []
        for line in block.splitlines():
            text = html.escape(clean(line))
            text = re.sub(
                r"https?://\S+", lambda m: f'<a href="{m[0]}" color="#087f8c">{m[0]}</a>', text
            )
            style = "Subsection" if re.match(r"Screenshot \d+:", line) else "Text"
            section.append(para(text, style))
        section.append(Spacer(1, 6))
        story.extend([KeepTogether(section)] if block.startswith("Screenshot ") else section)
    outputs.append(
        build("SCREENSHOT-CHECKLIST", "Your screenshot checklist", story, manifest["date"])
    )
    for path in outputs:
        print(path.name, path.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
