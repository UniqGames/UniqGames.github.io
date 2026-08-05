#!/usr/bin/env python3
"""Derive the website's image set from the Unity project's source art.

Run from anywhere:  python3 tools/build_assets.py

The art lives in the Unity repository, which is checked out separately. This
looks for it beside this repository; set UNITY_PROJECT to point somewhere else.

Content images are emitted as WebP only, which every browser we target supports
and which keeps the repo an order of magnitude smaller than PNG. PNG survives
only where a platform demands it: favicons, the Apple touch icon and the PWA
manifest icons. The Open Graph card is additionally written as JPEG because some
social scrapers still refuse WebP.

The Monster Sort wordmark does not exist as a single flattened file. In game it
is assembled at runtime from three sprites (badge plate, "MONSTER", "SORT") using
the constants in WinCelebrationLayout.cs, so this script reproduces that same
lockup rather than shipping a hand-made copy that could drift from the game.
"""

from __future__ import annotations

import colorsys
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required:  python3 -m pip install Pillow")

SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "assets" / "img"

def _unity_project() -> Path:
    """Locate the game checkout: an explicit override, else a sibling directory."""
    override = os.environ.get("UNITY_PROJECT")
    if override:
        return Path(override).expanduser()
    for name in ("MonsterSort", "Factory of Monsters"):
        candidate = SITE.parent / name
        if candidate.is_dir():
            return candidate
    return SITE.parent / "MonsterSort"


UNITY = _unity_project()
ASSETS = UNITY / "Assets"
SRC = ASSETS / "_Project" / "Art" / "Sprites"

WEBP_QUALITY = 82

# Brand palette, mirrored from Assets/_Project/ScriptableObjects/Settings/UiTheme.asset
INK = (18, 15, 31)
DEEP_PURPLE = (52, 0, 79)

# Lockup geometry copied from WinCelebrationLayout.cs. Unity draws each piece with
# preserveAspect inside these rects, so `fit_rect` below matches that behaviour.
PLAKA_RECT = (850, 547)
MONSTER_RECT = (750, 280)
SORT_RECT = (617, 256)
MONSTER_CENTRE = (0, 112)
SORT_CENTRE = (0, -72)
MONSTER_STRETCH_X = 1.04


def load(rel: str, root: Path = SRC) -> Image.Image:
    path = root / rel
    if not path.exists():
        sys.exit(f"missing source art: {path}")
    return Image.open(path).convert("RGBA")


def fit(img: Image.Image, width: int) -> Image.Image:
    if img.width <= width:
        return img.copy()
    height = round(img.height * width / img.width)
    return img.resize((width, height), Image.LANCZOS)


def fit_rect(img: Image.Image, box: tuple[int, int]) -> Image.Image:
    """Scale to fit inside `box` without distorting, the way Unity's preserveAspect does."""
    scale = min(box[0] / img.width, box[1] / img.height)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(size, Image.LANCZOS)


def trim(img: Image.Image, threshold: int = 8) -> Image.Image:
    """Crop fully transparent margins so layout sizing is predictable."""
    alpha = img.getchannel("A")
    box = alpha.point(lambda v: 255 if v > threshold else 0).getbbox()
    return img.crop(box) if box else img


def flatten(img: Image.Image, bg: tuple[int, int, int]) -> Image.Image:
    canvas = Image.new("RGBA", img.size, bg + (255,))
    canvas.alpha_composite(img)
    return canvas.convert("RGB")


def paste_centre(canvas: Image.Image, img: Image.Image, centre: tuple[float, float]) -> None:
    canvas.alpha_composite(img, (round(centre[0] - img.width / 2), round(centre[1] - img.height / 2)))


def emit_alpha(img: Image.Image, name: str, width: int) -> None:
    scaled = fit(img, width)
    scaled.save(OUT / f"{name}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
    print(f"  {name}  {scaled.width}x{scaled.height}")


def emit_flat(img: Image.Image, name: str, width: int, bg=INK) -> None:
    scaled = flatten(fit(img, width), bg)
    scaled.save(OUT / f"{name}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
    print(f"  {name}  {scaled.width}x{scaled.height}")


def recolour(img: Image.Image, hue: float, saturation_floor: float = 0.45) -> Image.Image:
    """Hue-rotate the red candy sprite to build the match-item colour set."""
    out = img.copy()
    pixels = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s < 0.08:  # keep the white highlight stripes neutral
                continue
            nr, ng, nb = colorsys.hsv_to_rgb(hue, max(s, saturation_floor), v)
            pixels[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), a)
    return out


def lockup(badge: Image.Image | None, monster: Image.Image, sort: Image.Image, supersample: float = 2.0) -> Image.Image:
    """Rebuild the in-game Monster Sort logo. Pass badge=None for the bare wordmark."""
    k = supersample
    canvas = Image.new("RGBA", (round(1400 * k), round(1000 * k)), (0, 0, 0, 0))
    cx, cy = canvas.width / 2, canvas.height / 2

    if badge is not None:
        paste_centre(canvas, fit_rect(badge, (round(PLAKA_RECT[0] * k), round(PLAKA_RECT[1] * k))), (cx, cy))

    word = fit_rect(monster, (round(MONSTER_RECT[0] * k), round(MONSTER_RECT[1] * k)))
    word = word.resize((round(word.width * MONSTER_STRETCH_X), word.height), Image.LANCZOS)
    paste_centre(canvas, word, (cx + MONSTER_CENTRE[0] * k, cy - MONSTER_CENTRE[1] * k))

    tail = fit_rect(sort, (round(SORT_RECT[0] * k), round(SORT_RECT[1] * k)))
    paste_centre(canvas, tail, (cx + SORT_CENTRE[0] * k, cy - SORT_CENTRE[1] * k))

    return trim(canvas)


def radial_backdrop(size: tuple[int, int]) -> Image.Image:
    """Soft purple spotlight on near-black, matching the in-game scene backdrop."""
    w, h = size
    small = Image.new("RGB", (w // 8, h // 8), INK)
    draw = ImageDraw.Draw(small)
    cx, cy = small.width / 2, small.height * 0.44
    steps = 48
    radius = max(small.width, small.height) * 0.72
    for i in range(steps, 0, -1):
        t = i / steps
        colour = tuple(round(INK[c] + (DEEP_PURPLE[c] - INK[c]) * (1 - t) ** 1.6) for c in range(3))
        r = radius * t
        draw.ellipse((cx - r, cy - r * 0.85, cx + r, cy + r * 0.85), fill=colour)
    return small.resize(size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(6))


# Candies drifting through the empty middle band of the key art: colour, centre as a
# fraction of the canvas, diameter as a fraction of the width, and rotation.
SPLASH_CANDIES = (
    ("purple", (0.17, 0.485), 0.175, -14),
    ("blue", (0.74, 0.445), 0.215, 22),
    ("green", (0.45, 0.575), 0.140, 8),
    ("orange", (0.88, 0.605), 0.115, -30),
    ("yellow", (0.28, 0.665), 0.105, 16),
)


def splash(
    background: Image.Image,
    logo: Image.Image,
    cast: Image.Image,
    candies: dict[str, Image.Image],
    name: str,
    width: int,
) -> None:
    """The portrait key art shown inside the phone frames: game backdrop, logo, candies, cast."""
    card = fit(background, width).convert("RGBA")
    w, h = card.size

    mark = fit(logo, round(w * 0.82))
    paste_centre(card, mark, (w / 2, h * 0.25))

    for colour, (fx, fy), fsize, angle in SPLASH_CANDIES:
        ball = fit(candies[colour], round(w * fsize)).rotate(angle, Image.BICUBIC, expand=True)
        paste_centre(card, ball, (w * fx, h * fy))

    trio = fit(trim(cast), round(w * 0.98))
    card.alpha_composite(trio, (round((w - trio.width) / 2), round(h * 0.98 - trio.height)))

    card.convert("RGB").save(OUT / f"{name}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
    print(f"  {name}  {w}x{h}")


def social_card(name: str, logo: Image.Image, cast: Image.Image) -> None:
    """1200x630 Open Graph card composed from the logo lockup and the monster trio."""
    w, h = 1200, 630
    card = radial_backdrop((w, h)).convert("RGBA")

    art = fit(trim(cast), 620)
    art_y = h - art.height + 40
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((w - 700, art_y - 60, w - 40, h + 40), fill=(156, 79, 217, 110))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))
    card.alpha_composite(art, (w - art.width - 30, art_y))

    mark = fit(logo, 560)
    card.alpha_composite(mark, (72, (h - mark.height) // 2 - 20))

    card.convert("RGB").save(OUT / f"{name}.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    print(f"  {name}  {w}x{h}  jpg")


def icons(app_icon: Image.Image) -> None:
    for size in (512, 192):
        fit(app_icon, size).save(OUT / f"app-icon-{size}.png", "PNG", optimize=True)
    fit(app_icon, 180).save(OUT / "apple-touch-icon.png", "PNG", optimize=True)
    fit(app_icon, 32).save(OUT / "favicon-32.png", "PNG", optimize=True)
    app_icon.save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("  favicons  512/192/180/32/ico")


def main() -> None:
    if not SRC.is_dir():
        sys.exit(
            f"Unity art not found at {SRC}\n"
            "Set UNITY_PROJECT to your checkout of the game repository, e.g.\n"
            "  UNITY_PROJECT=~/Projects/Unity/MonsterSort python3 tools/build_assets.py"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"source: {SRC}\noutput: {OUT}\n")

    print("brand")
    badge = load("UI/Gameplay/Celebration/logo_a.png")
    monster = load("UI/Gameplay/Celebration/logo_b.png")
    sort = load("UI/Gameplay/Celebration/logo_c.png")
    wordmark = lockup(None, monster, sort)
    emblem = lockup(badge, monster, sort)
    emit_alpha(wordmark, "logo-monster-sort", 900)
    emit_alpha(emblem, "logo-monster-sort-badge", 1000)
    icons(load("UI/AppIcon/App_icon2.png"))

    print("cast")
    # Named by colour: the game itself never names these three, so the site does not either.
    cast = {
        "monster-red": "UI/Popups/Loading Scene/character_1.png",
        "monster-yellow": "UI/Popups/Loading Scene/character_2.png",
        "monster-teal": "UI/Popups/Loading Scene/character_3.png",
    }
    for name, rel in cast.items():
        emit_alpha(trim(load(rel)), name, 620)
    trio = trim(load("UI/Teams/teams_characters.png"))
    emit_alpha(trio, "monsters-trio", 1000)

    print("candies")
    source_candy = trim(load("candy_1.png", root=ASSETS))
    # Hue targets sampled from CandyColorDatabase.
    candies = {
        name: recolour(source_candy, hue / 360)
        for name, hue in (
            ("red", 358),
            ("orange", 30),
            ("yellow", 48),
            ("green", 104),
            ("blue", 219),
            ("purple", 276),
        )
    }
    for name, image in candies.items():
        emit_alpha(image, f"candy-{name}", 240)

    print("scenes")
    # There is no shippable gameplay capture in the project yet, so the phone frames
    # show the game's own backdrop with the logo lockup and cast composited on top —
    # the same arrangement the player sees while a level loads.
    splash(load("UI/Gameplay/Backgrounds/gameplay_bg.png"), emblem, trio, candies, "screen-splash", 720)

    print("world")
    world = {
        "area-holiday-road": ("UI/Areas/first_area.png", 720),
        "area-treasure-island": ("UI/Areas/second_area.png", 720),
        "panel-leaderboard": ("UI/LockScreens/leaderboard_image.png", 720),
        "panel-collection": ("UI/Areas/card_collection_image.png", 720),
    }
    for name, (rel, width) in world.items():
        emit_alpha(trim(load(rel)), name, width)

    print("items")
    items = {
        "booster-undo": ("UI/Gameplay/Toolbar/booster_1.png", 280),
        "booster-add-jar": ("UI/Gameplay/Toolbar/booster_2.png", 280),
        "booster-shuffle": ("UI/Gameplay/Toolbar/booster_3.png", 280),
        "booster-hint": ("UI/Gameplay/Toolbar/booster_4.png", 280),
        "item-mystery": ("UI/Gameplay/New Item/mystery_ball.png", 320),
        "item-curtain": ("UI/Gameplay/New Item/curtain_item.png", 320),
        "item-stone": ("UI/Gameplay/New Item/NewItem_Stone.png", 320),
        "icon-coin": ("UI/MainMenu/Currency/coin.png", 200),
    }
    for name, (rel, width) in items.items():
        emit_alpha(trim(load(rel)), name, width)

    print("social")
    social_card("og-default", emblem, trio)

    print("\ndone")


if __name__ == "__main__":
    main()
