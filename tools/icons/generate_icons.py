#!/usr/bin/env python3
"""Turkify uygulama ikonu üreticisi (Windows .ico + macOS AppIcon PNG seti).

Tasarım: mavi gradyan yuvarlak-kare (squircle) + beyaz geometrik "T" + üstünde
Türkçe diakritik işareti (breve ˘). Marka rengi macOS/Windows ortak mavi tonu.

Tek bağımlılık: Pillow (yalnızca derleme/asset üretimi için; çalışma-zamanı değil).
Çalıştırma:  python tools/icons/generate_icons.py
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

# --- Tasarım sabitleri (tile boyutuna göre oransal) ---
SS = 4  # supersampling: kenarları pürüzsüzleştirmek için bu kat büyük çizilir
RADIUS_RATIO = 0.225  # köşe yarıçapı / tile boyutu (squircle görünümü)
GRAD_TOP = (62, 131, 244)    # #3E83F4 — üst (açık mavi)
GRAD_BOTTOM = (27, 77, 189)  # #1B4DBD — alt (koyu mavi)
GLYPH = (255, 255, 255)      # beyaz harf

REPO = Path(__file__).resolve().parents[2]
WIN_ICO = REPO / "windows" / "Turkify" / "Assets" / "Turkify.ico"
MAC_SET = REPO / "macos" / "Turkify" / "Turkify" / "Assets.xcassets" / "AppIcon.appiconset"


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient(size: int) -> Image.Image:
    """Dikey mavi gradyan (size x size)."""
    column = Image.new("RGB", (1, size))
    px = column.load()
    for y in range(size):
        px[0, y] = _lerp(GRAD_TOP, GRAD_BOTTOM, y / (size - 1))
    return column.resize((size, size))


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


WITH_BREVE = False  # Türkçe breve aksanı (deneysel). Sade "T" her boyutta daha net okunur.


def _draw_glyph(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float]) -> None:
    """Verilen kutuya beyaz geometrik 'T' çizer (opsiyonel breve aksanıyla)."""
    x0, y0, x1, y1 = box
    s = x1 - x0           # kutu (kare) boyutu
    cx = (x0 + x1) / 2

    bar_h = 0.15 * s
    stem_w = 0.17 * s
    type_w = 0.54 * s
    type_h = 0.54 * s
    corner = 0.04 * s

    if WITH_BREVE:
        breve_h = 0.115 * s
        gap = 0.085 * s
        total_h = breve_h + gap + type_h
        top = y0 + (s - total_h) / 2
        breve_w, breve_th = 0.34 * s, 0.05 * s
        draw.arc(
            [cx - breve_w / 2, top, cx + breve_w / 2, top + breve_h * 2],
            start=30, end=150, fill=GLYPH, width=round(breve_th),
        )
        t_top = top + breve_h + gap
    else:
        t_top = y0 + (s - type_h) / 2

    # T: üst bar + dikey gövde (hafif yuvarlatılmış köşeler).
    draw.rounded_rectangle(
        [cx - type_w / 2, t_top, cx + type_w / 2, t_top + bar_h],
        radius=corner, fill=GLYPH,
    )
    draw.rounded_rectangle(
        [cx - stem_w / 2, t_top, cx + stem_w / 2, t_top + type_h],
        radius=corner, fill=GLYPH,
    )


def render(px: int, margin_ratio: float) -> Image.Image:
    """İkonu `px` boyutunda RGBA olarak üretir (supersample + downscale)."""
    big = px * SS
    margin = round(big * margin_ratio)
    tile = big - 2 * margin
    radius = round(tile * RADIUS_RATIO)

    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    gradient = _gradient(tile)
    mask = _rounded_mask(tile, radius)
    canvas.paste(gradient, (margin, margin), mask)

    draw = ImageDraw.Draw(canvas)
    _draw_glyph(draw, (margin, margin, big - margin, big - margin))

    return canvas.resize((px, px), Image.LANCZOS)


def build_windows() -> None:
    WIN_ICO.parent.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    # Windows tray/taskbar: kenar boşluğu küçük (hücreyi doldursun).
    master = render(256, margin_ratio=0.04)
    master.save(WIN_ICO, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Windows: {WIN_ICO.relative_to(REPO)} ({sizes})")


def build_macos() -> None:
    # (dosya adı, piksel) — macOS dock/Finder için 1x/2x setleri.
    images = [
        ("icon_16x16.png", 16, "16x16", "1x"),
        ("icon_16x16@2x.png", 32, "16x16", "2x"),
        ("icon_32x32.png", 32, "32x32", "1x"),
        ("icon_32x32@2x.png", 64, "32x32", "2x"),
        ("icon_128x128.png", 128, "128x128", "1x"),
        ("icon_128x128@2x.png", 256, "128x128", "2x"),
        ("icon_256x256.png", 256, "256x256", "1x"),
        ("icon_256x256@2x.png", 512, "256x256", "2x"),
        ("icon_512x512.png", 512, "512x512", "1x"),
        ("icon_512x512@2x.png", 1024, "512x512", "2x"),
    ]
    MAC_SET.mkdir(parents=True, exist_ok=True)
    # macOS ikon ızgarası: ~%10 şeffaf kenar boşluğu (native uygulamalarla hizalı).
    for name, px, _size, _scale in images:
        render(px, margin_ratio=0.10).save(MAC_SET / name, format="PNG")
    contents = {
        "images": [
            {"filename": name, "idiom": "mac", "scale": scale, "size": size}
            for name, _px, size, scale in images
        ],
        "info": {"author": "turkify", "version": 1},
    }
    (MAC_SET / "Contents.json").write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    print(f"macOS: {MAC_SET.relative_to(REPO)} ({len(images)} PNG + Contents.json)")


def build_previews(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for px in (256, 64, 32, 16):
        render(px, margin_ratio=0.04).save(out_dir / f"preview-{px}.png", format="PNG")
    print(f"Önizleme: {out_dir}")


if __name__ == "__main__":
    import sys

    build_windows()
    build_macos()
    if len(sys.argv) > 1:
        build_previews(Path(sys.argv[1]))
    print("Bitti.")
