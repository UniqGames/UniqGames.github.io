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

The Monster Trip logo is the flattened lockup at tools/source/logo-monster-trip.png.
Do not rebuild it from the in-game celebration sprites: those still spell SORT.
"""

from __future__ import annotations

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

# The candy set is drawn at runtime in game, so there is no per-colour sprite to
# read. This reference sheet is the design as approved; replace it if the art
# changes. Layout is (column, row) in a 2x4 grid, top-left first.
CANDY_SHEET = SITE / "tools" / "source" / "candy-sheet.png"
CANDY_SHEET_BG = (70, 70, 70)
CANDY_GRID = (2, 4)
CANDY_LAYOUT = {
    "teal": (0, 0),
    "blue": (1, 0),
    "red": (0, 1),
    "orange": (1, 1),
    "yellow": (0, 2),
    "pink": (1, 2),
    "green": (0, 3),
}
# Editor gridlines sit about this far above the backdrop in brightness.
GRIDLINE_LIFT = 26


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


def cut_candies(sheet: Path) -> dict[str, Image.Image]:
    """Lift each candy off the flat backdrop of the reference sheet.

    The sheet is a screen grab laid out as a 2x4 grid, so the backdrop is one
    neutral grey crossed by faint editor gridlines. Keying on plain colour
    distance keeps those lines; keying on chroma drops them, because the lines
    are neutral and the candy is not. Specular highlights are neutral too, hence
    the brightness term alongside it.
    """
    image = Image.open(sheet).convert("RGB")
    pixels = image.load()
    width, height = image.size
    cell_w, cell_h = width // CANDY_GRID[0], height // CANDY_GRID[1]
    grey = sum(CANDY_SHEET_BG) / 3

    def signal(x: int, y: int) -> float:
        r, g, b = pixels[x, y]
        chroma = max(r, g, b) - min(r, g, b)
        return max(chroma, (r + g + b) / 3 - grey - GRIDLINE_LIFT)

    out: dict[str, Image.Image] = {}
    for name, (col, row) in CANDY_LAYOUT.items():
        x0, y0 = col * cell_w, row * cell_h
        solid = {
            (x, y)
            for y in range(y0, y0 + cell_h)
            for x in range(x0, x0 + cell_w)
            if signal(x, y) > 18
        }
        blob = largest_region(solid, (x0 + cell_w // 2, y0 + cell_h // 2))

        mask = Image.new("L", (cell_w, cell_h), 0)
        mask_px = mask.load()
        for x, y in blob:
            mask_px[x - x0, y - y0] = 255
        # Pull the edge in before feathering it: the outermost pixels are part
        # candy and part backdrop, and keeping them leaves a dark speckled rim.
        mask = mask.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.2))

        # A gridline crossing a candy survives the key, because inside the blob
        # it is just a lighter pixel. It is never more than two pixels wide, and
        # the artwork is smooth, so a small median erases it without a trace.
        candy = image.crop((x0, y0, x0 + cell_w, y0 + cell_h)).filter(ImageFilter.MedianFilter(5))
        candy = candy.convert("RGBA")
        candy.putalpha(mask)
        out[name] = trim(candy)
    return out


def largest_region(points: set[tuple[int, int]], seed: tuple[int, int]) -> set[tuple[int, int]]:
    """Flood the region containing (or nearest to) `seed`, ignoring stray specks."""
    if not points:
        return set()
    if seed not in points:
        seed = min(points, key=lambda p: (p[0] - seed[0]) ** 2 + (p[1] - seed[1]) ** 2)

    region = {seed}
    stack = [seed]
    while stack:
        x, y = stack.pop()
        for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if neighbour in points and neighbour not in region:
                region.add(neighbour)
                stack.append(neighbour)
    return region


def lockup(badge: Image.Image | None, monster: Image.Image, sort: Image.Image, supersample: float = 2.0) -> Image.Image:
    """Legacy SORT lockup. Unused; the shipped mark is tools/source/logo-monster-trip.png."""
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
    trip = trim(load("logo-monster-trip.png", root=SITE / "tools" / "source"))
    emit_alpha(trip, "logo-monster-trip", 900)
    emit_alpha(trip, "logo-monster-trip-badge", 1000)
    emit_alpha(trip, "logo-monster-sort", 900)
    emit_alpha(trip, "logo-monster-sort-badge", 1000)
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
    for name, image in cut_candies(CANDY_SHEET).items():
        emit_alpha(image, f"candy-{name}", 240)

    print("scenes")
    # The phone frame shows the first area's key art, which already has all three
    # monsters in it, rather than a composite of our own.
    key_art = load("UI/MainMenu/Backgrounds/1-19_level_bg.png")
    emit_flat(key_art, "screen-key-art", 720)

    print("world")
    world = {
        "area-holiday-road": ("UI/Areas/first_area.png", 720),
        "area-treasure-island": ("UI/Areas/second_area.png", 720),
        "panel-leaderboard": ("UI/LockScreens/leaderboard_image.png", 720),
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
    }
    for name, (rel, width) in items.items():
        emit_alpha(trim(load(rel)), name, width)

    print("social")
    social_card("og-default", trip, trio)

    print("\ndone")


if __name__ == "__main__":
    main()
