# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10", "pyyaml>=6"]
# ///
"""Render a fine-art meme per the DESIGN.md rendering contract.

Input JSON on stdin:
  {
    "artwork": "goya-saturn",
    "labels": {"saturn": "the refactor", "victim": "the sprint"},
    "caption": null,            # optional strip above the canvas
    "style": "placard",         # placard | blunt
    "out": "out/goya-test.jpg"
  }
"""
import json
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
MAX_WIDTH = 1600
FONT_FLOOR = 18
FONT_START = 52
MAX_LINES = 2

SERIF_CANDIDATES = [
    REPO / "skill/fonts/serif.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSerif.ttf"),
]
SANS_CANDIDATES = [
    REPO / "skill/fonts/sans-bold.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
]


def find_font(candidates: list[Path]) -> Path:
    for p in candidates:
        if p.exists():
            return p
    sys.exit("render.py: no usable font found; bundle one in skill/fonts/")


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def wrap_to_fit(draw, text, font_path, box_w, box_h):
    """Return (font, lines) fitting box, or None below the floor."""
    words = text.split()
    for size in range(FONT_START, FONT_FLOOR - 1, -2):
        font = load_font(font_path, size)
        lines, line = [], []
        ok = True
        for w in words:
            trial = " ".join(line + [w])
            if draw.textlength(trial, font=font) <= box_w:
                line.append(w)
            elif line:
                lines.append(" ".join(line))
                line = [w]
            else:
                ok = False  # single word wider than box at this size
                break
        if not ok:
            continue
        if line:
            lines.append(" ".join(line))
        line_h = size * 1.25
        if len(lines) <= MAX_LINES and len(lines) * line_h <= box_h:
            return font, lines
    return None


def rects_overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def draw_label(img, draw, style, text, box_px, subject_px, font_path):
    x, y, w, h = box_px
    display = text.upper() if style == "placard" else text
    fit = wrap_to_fit(draw, display, font_path, w * 0.92, h * 0.88)
    if fit is None:
        sys.exit(f"render.py: label {text!r} cannot fit its box above the "
                 f"{FONT_FLOOR}px floor — fix the annotation")
    font, lines = fit
    line_h = font.size * 1.25
    text_w = max(draw.textlength(ln, font=font) for ln in lines)
    text_h = len(lines) * line_h

    # leader line when the box does not contain the subject point
    if not (x <= subject_px[0] <= x + w and y <= subject_px[1] <= y + h):
        edge = (min(max(subject_px[0], x), x + w),
                min(max(subject_px[1], y), y + h))
        draw.line([edge, subject_px], fill=(255, 255, 255, 230), width=3)
        r = 6
        draw.ellipse([subject_px[0] - r, subject_px[1] - r,
                      subject_px[0] + r, subject_px[1] + r],
                     fill=(255, 255, 255, 230))

    cx, cy = x + w / 2, y + h / 2
    if style == "placard":
        pad = font.size * 0.5
        rect = [cx - text_w / 2 - pad, cy - text_h / 2 - pad,
                cx + text_w / 2 + pad, cy + text_h / 2 + pad]
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle(rect, radius=6, fill=(15, 12, 10, 200))
        img.alpha_composite(overlay)
        draw = ImageDraw.Draw(img)
        for i, ln in enumerate(lines):
            lw = draw.textlength(ln, font=font)
            draw.text((cx - lw / 2, cy - text_h / 2 + i * line_h + line_h * 0.1),
                      ln, font=font, fill=(240, 234, 222, 255))
    else:  # blunt
        for i, ln in enumerate(lines):
            lw = draw.textlength(ln, font=font)
            pos = (cx - lw / 2, cy - text_h / 2 + i * line_h)
            draw.text(pos, ln, font=font, fill=(255, 255, 255, 255),
                      stroke_width=max(2, font.size // 12),
                      stroke_fill=(0, 0, 0, 255))
    return [rect[0], rect[1], rect[2], rect[3]] if style == "placard" else \
        [cx - text_w / 2, cy - text_h / 2, cx + text_w / 2, cy + text_h / 2]


def text_strip(width, text, font_path, size, bg, fg, upper=False):
    font = load_font(font_path, size)
    strip_h = int(size * 2.2)
    strip = Image.new("RGBA", (width, strip_h), bg)
    d = ImageDraw.Draw(strip)
    t = text.upper() if upper else text
    tw = d.textlength(t, font=font)
    d.text(((width - tw) / 2, (strip_h - size * 1.2) / 2), t, font=font, fill=fg)
    return strip


def main():
    spec = json.load(sys.stdin)
    style = spec.get("style", "placard")
    art = yaml.safe_load((REPO / "corpus" / f"{spec['artwork']}.yaml").read_text())

    img = Image.open(REPO / "corpus" / art["image"]).convert("RGBA")
    if max(img.size) > MAX_WIDTH:
        scale = MAX_WIDTH / max(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.LANCZOS)
    W, H = img.size
    draw = ImageDraw.Draw(img)
    font_path = find_font(SERIF_CANDIDATES if style == "placard" else SANS_CANDIDATES)

    targets = {t["id"]: t for t in art["targets"]}
    placed = []
    for tid, text in spec["labels"].items():
        t = targets.get(tid) or sys.exit(f"render.py: unknown target {tid!r}")
        bx, by, bw, bh = t["label_box"]
        box_px = (bx * W, by * H, bw * W, bh * H)
        sp = (t["subject_point"][0] * W, t["subject_point"][1] * H)
        rect = draw_label(img, draw, style, text, box_px, sp, font_path)
        draw = ImageDraw.Draw(img)
        for prev in placed:
            if rects_overlap(rect, prev):
                sys.exit("render.py: label boxes collide — fix the annotation")
        placed.append(rect)

    serif = find_font(SERIF_CANDIDATES)
    parts = []
    if spec.get("caption"):
        parts.append(text_strip(W, spec["caption"], font_path, 34,
                                (15, 12, 10, 255), (240, 234, 222, 255),
                                upper=(style == "placard")))
    parts.append(img)
    credit = f'{art["artist"]} \u2014 {art["title"]} ({art["date"]})'
    parts.append(text_strip(W, credit, serif, 22,
                            (15, 12, 10, 255), (200, 192, 180, 255)))

    total_h = sum(p.height for p in parts)
    canvas = Image.new("RGB", (W, total_h), (15, 12, 10))
    yoff = 0
    for p in parts:
        canvas.paste(p.convert("RGB"), (0, yoff),
                     p if p.mode == "RGBA" else None)
        yoff += p.height

    out = Path(spec["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "JPEG", quality=85)
    print(json.dumps({"out": str(out.resolve()), "width": W, "height": total_h,
                      "bytes": out.stat().st_size}))


if __name__ == "__main__":
    main()
