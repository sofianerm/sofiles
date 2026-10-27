"""Deterministically draw the original Sofiles mark; never load target binaries.

The SVG is the editable source of truth. Pillow renders the same Bezier geometry
at 4x resolution for transparent PNG and ten standard Windows ICO sizes.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import struct
import sys

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/sofiles"
ICON_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
SCALE = 4

# M, L, cubic Bezier and Z only: identical paths in SVG and Pillow.
BACK = "M 64 166 C 64 148 78 134 96 134 L 181 134 C 191 134 198 138 205 145 L 225 165 L 416 165 C 434 165 448 179 448 197 L 448 356 C 448 377 431 394 410 394 L 102 394 C 81 394 64 377 64 356 Z"
TAB_BACK = "M 304 132 C 304 123 311 116 320 116 L 399 116 C 408 116 415 123 415 132 L 415 172 L 304 172 Z"
TAB_FRONT = "M 267 153 C 267 144 274 137 283 137 L 362 137 C 371 137 378 144 378 153 L 378 184 L 267 184 Z"
FRONT = "M 64 205 C 64 188 78 174 95 174 L 417 174 C 434 174 448 188 448 205 L 448 355 C 448 376 431 393 410 393 L 102 393 C 81 393 64 376 64 355 Z"
S_MARK = "M 309 224 C 291 210 273 205 252 205 C 217 205 193 225 193 253 C 193 282 216 294 246 303 L 267 309 C 281 313 289 319 289 327 C 289 338 279 344 262 344 C 240 344 219 335 201 322 L 182 351 C 204 368 231 378 261 378 C 300 378 327 357 327 325 C 327 295 305 282 274 272 L 253 266 C 237 261 231 257 231 250 C 231 241 239 236 253 236 C 270 236 286 242 299 252 Z"
# An optically centered wide S remains recognizable in a 16px title bar.
S_TRANSFORM = (1.2, 1.0, -49.4, -8.0)


def path_points(path, transform=None):
    tokens = path.split()
    result = []
    current = (0.0, 0.0)
    start = None
    i = 0
    while i < len(tokens):
        op = tokens[i]
        i += 1
        if op in ("M", "L"):
            current = tuple(float(x) for x in tokens[i:i + 2])
            i += 2
            if start is None:
                start = current
            result.append(current)
        elif op == "C":
            x1, y1, x2, y2, x3, y3 = map(float, tokens[i:i + 6])
            i += 6
            x0, y0 = current
            for n in range(1, 49):
                t = n / 48
                u = 1 - t
                result.append((u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3,
                               u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3))
            current = (x3, y3)
        elif op == "Z":
            result.append(start)
        else:
            raise ValueError(f"Unsupported path operation: {op}")
    if transform:
        sx, sy, tx, ty = transform
        result = [(x*sx + tx, y*sy + ty) for x, y in result]
    return [(round(x*SCALE), round(y*SCALE)) for x, y in result]


def render_icon():
    canvas = Image.new("RGBA", (512*SCALE, 512*SCALE))
    draw = ImageDraw.Draw(canvas)
    draw.polygon(path_points(BACK), fill="#102D4F")
    draw.polygon(path_points(TAB_BACK), fill="#45C7CA")
    draw.polygon(path_points(TAB_FRONT), fill="#ACE7E4")
    mask = Image.new("L", canvas.size)
    ImageDraw.Draw(mask).polygon(path_points(FRONT), fill=255)
    gradient = Image.new("RGBA", (1, canvas.height))
    grad = gradient.load()
    for y in range(canvas.height):
        t = min(1.0, max(0.0, (y/SCALE-174)/219))
        a, b = (16, 124, 174), (20, 78, 137)
        grad[0, y] = tuple(round(a[j]*(1-t)+b[j]*t) for j in range(3)) + (255,)
    canvas.paste(gradient.resize(canvas.size), (0, 0), mask)
    draw = ImageDraw.Draw(canvas)
    draw.polygon(path_points(S_MARK, S_TRANSFORM), fill="#F7FCFF")
    return canvas.resize((512, 512), Image.Resampling.LANCZOS)


def save_mark():
    OUT.mkdir(parents=True, exist_ok=True)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-labelledby="title desc">
  <title id="title">Sofiles</title>
  <desc id="desc">Original folder and S monogram for Sofiles, personal edition by Sofiane Messaoudi.</desc>
  <metadata>Copyright (c) 2026 Sofiane Messaoudi. Original geometric artwork. Generated from tools/create_sofiles_icon.py.</metadata>
  <defs>
    <linearGradient id="pocket" x1="0" y1="174" x2="0" y2="393" gradientUnits="userSpaceOnUse">
      <stop stop-color="#107CAE"/><stop offset="1" stop-color="#144E89"/>
    </linearGradient>
  </defs>
  <path fill="#102D4F" d="{BACK}"/>
  <path fill="#45C7CA" d="{TAB_BACK}"/>
  <path fill="#ACE7E4" d="{TAB_FRONT}"/>
  <path fill="url(#pocket)" d="{FRONT}"/>
  <path fill="#F7FCFF" transform="matrix(1.2 0 0 1 -49.4 -8)" d="{S_MARK}"/>
</svg>
'''
    (OUT / "sofiles.svg").write_text(svg, encoding="utf-8")
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Software", "tools/create_sofiles_icon.py; Pillow; deterministic vector geometry")
    png_info.add_text("Copyright", "Copyright (c) 2026 Sofiane Messaoudi")
    png_info.add_text("Source", "assets/sofiles/sofiles.svg; original geometric artwork, no AI generation")
    mark = render_icon()
    mark.save(OUT / "sofiles-512.png", pnginfo=png_info)
    about = Image.new("RGBA", (190, 145))
    about_mark = mark.crop(mark.getbbox())
    about_mark.thumbnail((174, 129), Image.Resampling.LANCZOS)
    about.alpha_composite(about_mark, ((190-about_mark.width)//2, (145-about_mark.height)//2))
    about.save(OUT / "sofiles-about-190x145.png", pnginfo=png_info)
    mark.save(OUT / "sofiles.ico", sizes=[(s, s) for s in ICON_SIZES], bitmap_format="bmp")
    # Every size, including 256px, gets an uncropped light/dark inspection row.
    sheet = Image.new("RGB", (1100, 690), "#EAF0F6")
    d = ImageDraw.Draw(sheet)
    d.rectangle((0, 345, 1100, 690), fill="#10243A")
    for row, background in ((0, "#102D4F"), (345, "#EAF0F6")):
        d.text((24, row+15), "Sofiles · transparent icon · 16–256px", fill=background, font=font(20))
        x = 24
        for size in ICON_SIZES:
            im = mark.resize((size, size), Image.Resampling.LANCZOS)
            sheet.paste(im, (x, row+55+(256-size)//2), im)
            d.text((x, row+315), str(size), fill=background, font=font(14))
            x += max(size, 54) + 10
    sheet.save(OUT / "sofiles-contact-sheet.png", pnginfo=png_info)
    ico = Image.open(OUT / "sofiles.ico")
    assert ico.ico.sizes() == {(s, s) for s in ICON_SIZES}
    assert mark.mode == "RGBA" and mark.getpixel((0, 0))[3] == 0
    result = {"artwork": "Original geometric folder, two tabs and S monogram",
              "author": "Sofiane Messaoudi", "year": 2026,
              "palette": {"navy": "#102D4F", "blue": "#107CAE", "deep_blue": "#144E89", "turquoise": "#45C7CA", "pale_teal": "#ACE7E4", "white": "#F7FCFF"},
              "ico_sizes": ICON_SIZES,
              "generator": "tools/create_sofiles_icon.py",
              "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in (".svg", ".png", ".ico")}}
    (OUT / "manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text("# Sofiles — icône originale\n\nDossier bleu, deux onglets turquoise et monogramme S blanc. Création géométrique originale pour l’édition personnelle de Sofiane Messaoudi.\n\n- `sofiles.svg` : master vectoriel éditable, autonome, sans police externe.\n- `sofiles-512.png` : aperçu transparent 512 × 512.\n- `sofiles.ico` : images BMP avec canal alpha et masque Windows, tailles 16, 20, 24, 32, 40, 48, 64, 96, 128 et 256.\n- `sofiles-contact-sheet.png` : contrôle aux tailles réelles sur fond clair et sombre.\n\nReproduction : exécuter `tools/create_sofiles_icon.py` avec le Python fourni dans l’environnement Codex (Pillow installé). Aucune exécution ou modification des binaires Clover.\n\nCopyright © 2026 Sofiane Messaoudi — création graphique Sofiles. Cette attribution concerne l’icône originale.\n", encoding="utf-8")
    return result


def font(size):
    return ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", size)


def inspect_original_groups():
    sys.path.insert(0, str(ROOT / "tools/python-libs"))
    import pefile
    folder = ROOT / "analysis/branding/icon-inspection"
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    thumbs = []
    for filename in ("clover.exe", "clover.dll"):
        pe = pefile.PE(str(ROOT / "analysis/extracted" / filename))
        resources = {}
        for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            for name in typ.directory.entries:
                for lang in name.directory.entries:
                    value = lang.data.struct
                    resources[(typ.id, str(name.name) if name.name else name.id, lang.id)] = pe.get_data(value.OffsetToData, value.Size)
        for (typ, name, lang), group in resources.items():
            if typ != 14:
                continue
            reserved, kind, count = struct.unpack_from("<HHH", group)
            assert reserved == 0 and kind == 1
            entries = []
            payloads = []
            offset = 6 + 16*count
            for i in range(count):
                w, h, colors, reserved, planes, bits, length, rid = struct.unpack_from("<BBBBHHIH", group, 6+14*i)
                payload = resources[(3, rid, lang)]
                assert len(payload) == length
                entries.append(struct.pack("<BBBBHHII", w, h, colors, reserved, planes, bits, length, offset))
                payloads.append(payload)
                offset += length
            content = struct.pack("<HHH", 0, 1, count) + b"".join(entries) + b"".join(payloads)
            stem = f"{filename.replace('.', '-')}-group-{name}-{lang}"
            (folder / f"{stem}.ico").write_bytes(content)
            icon = Image.open(io.BytesIO(content)).convert("RGBA")
            icon.thumbnail((76, 76), Image.Resampling.LANCZOS)
            thumbs.append((filename, str(name), lang, icon))
            record = {"file": filename, "type": 14, "group": name, "lang": lang,
                      "icon_ids": [struct.unpack_from("<H", group, 6+14*i+12)[0] for i in range(count)],
                      "image_count": count, "ico": f"{stem}.ico"}
            records.append(record)
    cols, cell_w, cell_h = 6, 175, 134
    rows = (len(thumbs)+cols-1)//cols
    sheet = Image.new("RGB", (cols*cell_w, rows*cell_h), "#EAF0F6")
    draw = ImageDraw.Draw(sheet)
    for idx, (filename, group, lang, icon) in enumerate(thumbs):
        x, y = (idx % cols)*cell_w, (idx//cols)*cell_h
        sheet.paste(icon, (x+(cell_w-icon.width)//2, y+7+(76-icon.height)//2), icon)
        draw.text((x+8, y+86), f"{filename} / {group}", fill="#102D4F", font=font(13))
        draw.text((x+8, y+106), f"lang {lang}", fill="#102D4F", font=font(12))
    sheet.save(folder / "original-icon-groups.png")
    (folder / "inventory.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    return records


def inspect_bindata():
    sys.path.insert(0, str(ROOT / "tools/python-libs"))
    import pefile
    folder = ROOT / "analysis/branding/icon-inspection/bindata"
    folder.mkdir(parents=True, exist_ok=True)
    pe = pefile.PE(str(ROOT / "analysis/extracted/clover.dll"))
    records, images, small_images = [], [], []
    for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if str(typ.name) != "BINDATA":
            continue
        for name in typ.directory.entries:
            key = str(name.name) if name.name else name.id
            for lang in name.directory.entries:
                value = lang.data.struct
                payload = pe.get_data(value.OffsetToData, value.Size)
                record = {"type": "BINDATA", "name": key, "lang": lang.id,
                          "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                try:
                    image = Image.open(io.BytesIO(payload))
                    image.load()
                    record.update({"format": image.format, "width": image.width,
                                   "height": image.height, "mode": image.mode})
                    rgba = image.convert("RGBA")
                    rgb = list(rgba.get_flattened_data())
                    opaque = [p for p in rgb if p[3] > 128]
                    record["green_fraction"] = round(sum(g > 60 and g > r*1.2 and g > b*1.15 for r, g, b, a in opaque) / max(1, len(opaque)), 4)
                    if max(image.size) >= 48 or record["green_fraction"] > 0.03:
                        filename = f"bindata-{key}-{lang.id}.png"
                        rgba.save(folder / filename)
                        record["preview"] = filename
                        images.append((record, rgba))
                    else:
                        small_images.append((record, rgba))
                except Exception as error:
                    record["image_error"] = str(error)[:100]
                records.append(record)
    # Bound sheet to candidate logos and large illustration resources. Lists retain
    # all image dimensions so the investigator can widen a named candidate.
    images.sort(key=lambda pair: (-(pair[0]["green_fraction"] > 0.03), -max(pair[1].size), str(pair[0]["name"])))
    images = images[:72]
    cols, cw, ch = 6, 200, 170
    rows = (len(images)+cols-1)//cols
    sheet = Image.new("RGB", (cols*cw, rows*ch), "#EAF0F6")
    draw = ImageDraw.Draw(sheet)
    for i, (record, original) in enumerate(images):
        thumb = original.copy()
        thumb.thumbnail((174, 114), Image.Resampling.LANCZOS)
        x, y = i % cols*cw, i//cols*ch
        sheet.paste(thumb, (x+(cw-thumb.width)//2, y+6+(114-thumb.height)//2), thumb)
        label = f"{record['name']} / {record['width']} x {record['height']}"
        draw.text((x+7, y+125), label, font=font(13), fill="#102D4F")
        draw.text((x+7, y+145), f"L{record['lang']} green {record['green_fraction']:.0%}", font=font(12), fill="#102D4F")
    sheet.save(folder / "bindata-candidates.png")
    cols, cw, ch = 14, 80, 76
    small_sheet = Image.new("RGB", (cols*cw, ((len(small_images)+cols-1)//cols)*ch), "#EAF0F6")
    draw = ImageDraw.Draw(small_sheet)
    for i, (record, original) in enumerate(small_images):
        thumb = original.copy()
        thumb.thumbnail((64, 43), Image.Resampling.LANCZOS)
        x, y = i % cols*cw, i//cols*ch
        small_sheet.paste(thumb, (x+(cw-thumb.width)//2, y+3+(43-thumb.height)//2), thumb)
        draw.text((x+4, y+48), str(record["name"]), font=font(11), fill="#102D4F")
        draw.text((x+4, y+61), f"{record['width']}x{record['height']}", font=font(10), fill="#102D4F")
    small_sheet.save(folder / "bindata-small-controls.png")
    (folder / "inventory.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    return {"resources": len(records), "images": sum("width" in r for r in records),
            "candidates": len(images), "sheet": str(folder / "bindata-candidates.png"),
            "green_candidates": [r for r in records if r.get("green_fraction", 0) > .03]}


if __name__ == "__main__":
    result = save_mark()
    if "--inspect-originals" in sys.argv:
        result["original_groups"] = inspect_original_groups()
    if "--inspect-bindata" in sys.argv:
        result["bindata"] = inspect_bindata()
    print(json.dumps(result, indent=2))
