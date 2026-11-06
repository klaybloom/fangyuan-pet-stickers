#!/usr/bin/env python3
"""Export already-transparent pet sprites as captioned, gently animated stickers."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps, ImageSequence

MOTIONS = {"nod", "jump", "breathe", "sway"}
FRAMES = 24
DELAY = 80


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def transparent_sprite(path):
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] != 0 or not alpha.getbbox():
        raise ValueError(f"Expected transparent PNG with visible artwork: {path}")
    return rgba.crop(alpha.getbbox())


def caption(text, font_path, size):
    font_size = round(size * .125)
    font = ImageFont.truetype(str(font_path), font_size)
    while font.getlength(text) > size * .84:
        font_size -= 1
        if font_size < size * .065:
            raise ValueError("Caption too long; shorten or split the wording")
        font = ImageFont.truetype(str(font_path), font_size)
    layer = Image.new("RGBA", (size, size))
    ImageDraw.Draw(layer).text(
        (size // 2, round(size * .885)), text, font=font, anchor="mm",
        fill="#171717", stroke_width=max(1, round(size * .009)), stroke_fill="white")
    return layer


def render(sprite, text, motion, font_path, size):
    label = caption(text, font_path, size)
    fitted = ImageOps.contain(sprite, (round(size * .72), round(size * .66)), Image.Resampling.LANCZOS)
    frames = []
    for i in range(FRAMES):
        phase = i / FRAMES
        cycle = math.sin(2 * math.pi * phase)
        bounce = .5 - .5 * math.cos(2 * math.pi * phase)
        dy, angle, scale = 0, 0, 1
        if motion == "jump":
            dy = -.045 * size * bounce
        elif motion == "nod":
            dy = .017 * size * bounce
            angle = 2 * cycle
        elif motion == "sway":
            angle = 4 * cycle
        elif motion == "breathe":
            scale = 1 + .018 * cycle
        art = fitted.resize((round(fitted.width * scale), round(fitted.height * scale)), Image.Resampling.LANCZOS)
        art = art.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        frame = Image.new("RGBA", (size, size))
        frame.alpha_composite(art, ((size - art.width) // 2, round(size * .77 - art.height + dy)))
        frame.alpha_composite(label)
        frame.putalpha(frame.getchannel("A").point(lambda x: 255 if x >= 128 else 0))
        frames.append(frame)
    return frames


def save_gif(path, frames, limit):
    # One shared palette keeps fur colors stable; index 255 is reserved for transparency.
    size = frames[0].width
    sheet = Image.new("RGB", (size * 4, size * 6), "white")
    for i, frame in enumerate(frames):
        sheet.paste(frame, ((i % 4) * size, (i // 4) * size), frame.getchannel("A"))
    for colors in (250, 192, 128, 96, 64, 48, 32):
        pal = sheet.quantize(colors=colors)
        indexed = []
        for frame in frames:
            matte = Image.new("RGB", frame.size, "white")
            matte.paste(frame, (0, 0), frame.getchannel("A"))
            item = matte.quantize(palette=pal, dither=Image.Dither.NONE)
            item.paste(255, mask=ImageChops.invert(frame.getchannel("A")))
            indexed.append(item)
        indexed[0].save(path, save_all=True, append_images=indexed[1:], duration=DELAY,
                        loop=0, disposal=2, transparency=255, optimize=False)
        if path.stat().st_size <= limit:
            return
    raise ValueError(f"Cannot meet size limit without further artwork changes: {path}")


def check_gif(path, size, limit):
    hashes, margins, duration = set(), [], 0
    with Image.open(path) as gif:
        if gif.format != "GIF" or gif.size != (size, size) or gif.info.get("loop") != 0:
            raise ValueError(f"Wrong GIF size/type/loop: {path}")
        for frame in ImageSequence.Iterator(gif):
            rgba = frame.convert("RGBA")
            alpha = rgba.getchannel("A")
            box = alpha.getbbox()
            if not box or alpha.getextrema() != (0, 255):
                raise ValueError(f"Frame has no visible art or transparency: {path}")
            margins.append(min(box[0], box[1], size - box[2], size - box[3]))
            hashes.add(hashlib.sha256(rgba.tobytes()).hexdigest())
            duration += frame.info.get("duration", 0)
        count = gif.n_frames
    if min(margins) < 2 or len(hashes) < 4 or duration != FRAMES * DELAY:
        raise ValueError(f"Invalid motion, clipping, or timing: {path}")
    if path.stat().st_size > limit:
        raise ValueError(f"File exceeds byte limit: {path}")
    return {"file": path.name, "bytes": path.stat().st_size, "decoded_frames": count,
            "distinct_frames": len(hashes), "duration_ms": duration,
            "minimum_margin_px": min(margins), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def check_image(path, size, fmt, limit):
    with Image.open(path) as im:
        im.load()
        if im.size != size or im.format != fmt or path.stat().st_size > limit:
            raise ValueError(f"Wrong companion image size, format, or bytes: {path}")


def copy_companion(source, target, size):
    # Do not crop designer artwork or quietly cover missing material.
    with Image.open(source) as im:
        if im.size != size:
            raise ValueError(f"Design companion at {size} before exporting: {source}")
        im.convert("RGB").save(target, quality=93, optimize=True)
    check_image(target, size, "JPEG", 500_000)


def verify(out):
    metadata = json.loads((out / "submission.json").read_text(encoding="utf-8"))
    entries = metadata["captions"]
    if not 8 <= len(entries) <= 24:
        raise ValueError("WeChat album baseline requires 8–24 entries")
    expected_names = {f"{i:02}.gif" for i in range(1, len(entries) + 1)}
    for folder in ("wechat/gif", "hd"):
        if {p.name for p in (out / folder).glob("*.gif")} != expected_names:
            raise ValueError(f"GIF count or filenames do not match submission: {folder}")
    reports = []
    for i in range(1, len(entries) + 1):
        reports.append(check_gif(out / f"wechat/gif/{i:02}.gif", 240, 500_000))
        check_gif(out / f"hd/{i:02}.gif", 512, 8_000_000)
        check_image(out / f"wechat/thumb/{i:02}.png", (120, 120), "PNG", 50_000)
    for name, size, fmt, limit in [("cover.png", (240, 240), "PNG", 500_000),
                                   ("icon.png", (50, 50), "PNG", 100_000),
                                   ("banner.jpg", (750, 400), "JPEG", 500_000)]:
        check_image(out / "wechat/companion" / name, size, fmt, limit)
    for key, size in [("reward-guide", (750, 560)), ("reward-thanks", (750, 750))]:
        if key in metadata.get("optional_companions", []):
            check_image(out / f"wechat/companion/{key}.jpg", size, "JPEG", 500_000)
    for name in ("preview.html", "overview.jpg"):
        if not (out / name).is_file():
            raise ValueError(f"Missing {name}")
    archive = out / "stickers-delivery.zip"
    if archive.exists():
        expected = {str(p.relative_to(out)) for p in out.rglob("*")
                    if p.is_file() and p != archive}
        with ZipFile(archive) as z:
            if set(z.namelist()) != expected or z.testzip() is not None:
                raise ValueError("Delivery ZIP is incomplete or damaged")
    return {"status": "technical_checks_passed", "count": len(entries), "wechat": reports,
            "visual_review": "not_performed_by_script", "published": False}


def build(manifest, font, out):
    config = json.loads(manifest.read_text(encoding="utf-8"))
    entries = config["entries"]
    if not 8 <= len(entries) <= 24:
        raise ValueError("Expected 8–24 entries")
    texts = [entry["text"] for entry in entries]
    if any(not isinstance(text, str) or not text.strip() for text in texts) or len(set(texts)) != len(texts):
        raise ValueError("Provide nonempty, distinct captions")
    sprites = []
    for entry in entries:
        if entry.get("motion", "breathe") not in MOTIONS:
            raise ValueError(f"Unsupported motion: {entry.get('motion')}")
        sprites.append(transparent_sprite(manifest.parent / entry["sprite"]))
    ImageFont.truetype(str(font), 24)  # Fail before creating output if font is unavailable.
    if out.exists():
        raise ValueError("Output directory already exists; use a fresh revision")
    banner = manifest.parent / config["banner"]
    with Image.open(banner) as im:
        if im.size != (750, 400):
            raise ValueError("Banner must already be 750×400")
    for sub in ("wechat/gif", "wechat/thumb", "wechat/companion", "hd"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    thumbs = []
    for i, (entry, sprite) in enumerate(zip(entries, sprites), 1):
        frames = render(sprite, entry["text"], entry.get("motion", "breathe"), font, 512)
        save_gif(out / f"hd/{i:02}.gif", frames, 8_000_000)
        small = []
        for frame in frames:
            item = frame.resize((240, 240), Image.Resampling.LANCZOS)
            item.putalpha(item.getchannel("A").point(lambda x: 255 if x >= 128 else 0))
            small.append(item)
        save_gif(out / f"wechat/gif/{i:02}.gif", small, 500_000)
        thumb = small[0].resize((120, 120), Image.Resampling.LANCZOS)
        thumb.save(out / f"wechat/thumb/{i:02}.png", optimize=True)
        thumbs.append(small[0])
    for name, size in [("cover", 240), ("icon", 50)]:
        art = ImageOps.contain(sprites[0], (round(size * .9), round(size * .9)), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size))
        canvas.alpha_composite(art, ((size - art.width) // 2, (size - art.height) // 2))
        canvas.save(out / f"wechat/companion/{name}.png", optimize=True)
    copy_companion(banner, out / "wechat/companion/banner.jpg", (750, 400))
    optional = []
    for key, size in [("reward-guide", (750, 560)), ("reward-thanks", (750, 750))]:
        if config.get(key):
            copy_companion(manifest.parent / config[key], out / f"wechat/companion/{key}.jpg", size)
            optional.append(key)
    overview = Image.new("RGB", (960, math.ceil(len(entries) / 4) * 240), "white")
    for i, thumb in enumerate(thumbs):
        overview.paste(thumb, ((i % 4) * 240, (i // 4) * 240), thumb.getchannel("A"))
    overview.save(out / "overview.jpg", quality=94)
    title = config["title"]
    write_json(out / "submission.json", {"title": title, "description": config.get("description", ""),
               "copyright": config.get("copyright", ""), "captions": texts,
               "optional_companions": optional, "status": "local_only_not_submitted"})
    cards = "".join(f'<a href="wechat/gif/{i:02}.gif"><img src="wechat/gif/{i:02}.gif" alt="{html.escape(text, quote=True)}"></a>'
                    for i, text in enumerate(texts, 1))
    (out / "preview.html").write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + '</title>'
        '<style>body{margin:24px;background:#fff;color:#171717;font-family:sans-serif}main{max-width:1100px;margin:auto}'
        '.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}img{width:100%;display:block}'
        '.grid a{border:1px solid #ddd;border-radius:16px}body.dark{background:#171717;color:#fff}'
        'button{padding:12px;margin-bottom:20px}@media(max-width:600px){.grid{grid-template-columns:repeat(2,1fr)}}</style>'
        '<main><h1>' + html.escape(title) + '</h1><p>单姿势轻动效 · 本地成品 · 未投稿</p>'
        '<button onclick="document.body.classList.toggle(\'dark\')">切换浅色／深色背景</button><div class="grid">'
        + cards + '</div></main></html>', encoding="utf-8")
    write_json(out / "verification.json", verify(out))
    with ZipFile(out / "stickers-delivery.zip", "w", ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file() and p.name != "stickers-delivery.zip":
                z.write(p, str(p.relative_to(out)))
    verify(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build", help="Build from transparent sprites; never generates images")
    make.add_argument("--manifest", type=Path, required=True)
    make.add_argument("--font", type=Path, required=True)
    make.add_argument("--out", type=Path, required=True)
    check = commands.add_parser("verify", help="Decode and verify all final files and ZIP")
    check.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        build(args.manifest.resolve(), args.font.resolve(), args.out.resolve())
    report = verify(args.out.resolve())
    print(json.dumps({"status": report["status"], "count": report["count"],
                      "max_gif_bytes": max(x["bytes"] for x in report["wechat"]),
                      "visual_review": report["visual_review"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
