"""Reopen, extract and render every submission PDF; output visual QA sheets."""

import json
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp/pdfs"
NAMES = (
    "README",
    "REPORT",
    "ASSIGNMENT-CHECKLIST",
    "VIVA-NOTES",
    "VERIFICATION",
    "SCREENSHOT-CHECKLIST",
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for name in NAMES:
        path = ROOT / (name + ".pdf")
        reader = PdfReader(path)
        assert len(reader.pages) > 0 and path.stat().st_size > 1000, name
        document = fitz.open(path)
        thumbnails = []
        warnings = []
        texts = []
        for index, page in enumerate(document):
            text = page.get_text()
            texts.append(text)
            assert len(text.strip()) > 30, (name, index)
            assert "```" not in text, (name, "Unrendered Markdown fence")
            assert "\ufffd" not in text, (name, "Missing/replacement glyph")
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        x0, y0, x1, y1 = span["bbox"]
                        if (
                            x0 < 35
                            or x1 > page.rect.width - 35
                            or y0 < 25
                            or y1 > page.rect.height - 16
                        ):
                            warnings.append(
                                {"page": index + 1, "text": span["text"], "bbox": span["bbox"]}
                            )
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
            image_path = OUT / f"{name}-{index + 1:02}.png"
            pixmap.save(image_path)
            with Image.open(image_path) as source:
                thumb = source.copy()
            thumb.thumbnail((300, 425))
            thumbnails.append(thumb)
        # Contact sheets preserve every page; larger pages are also available for inspection.
        for start in range(0, len(thumbnails), 12):
            group = thumbnails[start : start + 12]
            sheet = Image.new("RGB", (960, ((len(group) + 2) // 3) * 455), "#dbe4ea")
            draw = ImageDraw.Draw(sheet)
            for position, thumb in enumerate(group):
                x, y = (position % 3) * 320 + 10, (position // 3) * 455 + 22
                draw.text((x, y - 17), f"{name} | page {start + position + 1}", fill="black")
                sheet.paste(thumb, (x, y))
            sheet.save(OUT / f"{name}-contact-{start // 12 + 1}.png")
        links = sum(len(page.get_links()) for page in document)
        result = {
            "file": path.name,
            "absolute_path": str(path),
            "bytes": path.stat().st_size,
            "pages": len(document),
            "links": links,
            "all_pages_rendered": True,
            "text_bounds_warnings": warnings,
        }
        results.append(result)
        print(
            name,
            "pages:",
            len(document),
            "bytes:",
            path.stat().st_size,
            "links:",
            links,
            "bounds warnings:",
            len(warnings),
        )
        (OUT / f"{name}.txt").write_text("\n".join(texts), encoding="utf-8")
    (OUT / "validation.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    assert not any(r["text_bounds_warnings"] for r in results), (
        "Inspect text bounds warnings before delivery"
    )


if __name__ == "__main__":
    main()
