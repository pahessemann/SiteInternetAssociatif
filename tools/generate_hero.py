from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "hero-garden.png"
WIDTH = 1800
HEIGHT = 1100


def vertical_gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), top)
    pixels = image.load()
    for y in range(HEIGHT):
        ratio = y / max(HEIGHT - 1, 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        for x in range(WIDTH):
            pixels[x, y] = color
    return image


def draw_leaf(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: tuple[int, int, int]) -> None:
    draw.ellipse((cx - size, cy - size // 2, cx + size, cy + size // 2), fill=color)
    draw.line((cx - size // 2, cy, cx + size // 2, cy), fill=(36, 84, 54), width=max(1, size // 8))


def main() -> None:
    random.seed(14)
    image = vertical_gradient((220, 238, 231), (250, 244, 219))
    draw = ImageDraw.Draw(image, "RGBA")

    draw.rectangle((0, 610, WIDTH, HEIGHT), fill=(74, 121, 74, 255))
    draw.polygon([(0, 650), (430, 560), (850, 660), (1260, 540), (1800, 665), (1800, 1100), (0, 1100)], fill=(90, 143, 82, 255))
    draw.polygon([(0, 730), (540, 635), (1050, 745), (1550, 640), (1800, 710), (1800, 1100), (0, 1100)], fill=(44, 101, 67, 255))

    for x in range(80, WIDTH, 220):
        height = random.randint(155, 250)
        color = random.choice([(202, 177, 142, 170), (189, 202, 190, 165), (215, 190, 154, 155)])
        draw.rectangle((x, 430 - height // 3, x + 120, 610), fill=color)
        for wx in range(x + 18, x + 100, 34):
            for wy in range(430 - height // 3 + 24, 575, 48):
                draw.rectangle((wx, wy, wx + 14, wy + 18), fill=(236, 242, 232, 160))

    draw.rectangle((0, 585, WIDTH, 650), fill=(43, 92, 61, 220))
    for x in range(0, WIDTH, 45):
        draw.rectangle((x, 540 + random.randint(-18, 18), x + 8, 650), fill=(54, 78, 60, 210))

    path = [(0, 1030), (520, 820), (820, 745), (1090, 835), (1800, 1040), (1800, 1100), (0, 1100)]
    draw.polygon(path, fill=(205, 180, 126, 255))
    draw.line([(0, 1030), (520, 820), (820, 745), (1090, 835), (1800, 1040)], fill=(234, 213, 157, 180), width=7)

    bed_colors = [(52, 91, 57), (65, 112, 64), (72, 126, 74), (92, 143, 85)]
    beds = [
        [(90, 805), (455, 700), (640, 770), (290, 910)],
        [(610, 740), (920, 670), (1125, 725), (825, 830)],
        [(1110, 805), (1510, 690), (1730, 770), (1340, 920)],
        [(455, 930), (770, 830), (980, 885), (675, 1010)],
    ]
    for points in beds:
        draw.polygon(points, fill=(114, 79, 48, 255))
        inset = [(x, y - 18) for x, y in points]
        draw.polygon(inset, fill=random.choice(bed_colors) + (255,))
        xs = [point[0] for point in inset]
        ys = [point[1] for point in inset]
        for _ in range(80):
            cx = random.randint(min(xs) + 10, max(xs) - 10)
            cy = random.randint(min(ys) + 10, max(ys) - 10)
            if random.random() < 0.72:
                draw_leaf(draw, cx, cy, random.randint(5, 11), random.choice([(39, 124, 67), (55, 148, 78), (102, 156, 70)]))
            else:
                draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=random.choice([(228, 176, 60), (191, 93, 67), (244, 231, 118), (241, 242, 235)]) + (245,))

    for tx in [210, 1390, 1610]:
        trunk_height = random.randint(170, 230)
        draw.rounded_rectangle((tx - 18, 560 - trunk_height, tx + 18, 665), radius=10, fill=(106, 75, 45, 255))
        for _ in range(75):
            cx = tx + random.randint(-110, 110)
            cy = 520 - trunk_height + random.randint(-60, 95)
            draw.ellipse((cx - 42, cy - 32, cx + 42, cy + 32), fill=random.choice([(41, 103, 67), (54, 127, 75), (82, 143, 83)]) + (220,))

    draw.rounded_rectangle((965, 735, 1165, 780), radius=8, fill=(115, 82, 50, 255))
    draw.rectangle((990, 780, 1010, 845), fill=(91, 62, 40, 255))
    draw.rectangle((1120, 780, 1140, 845), fill=(91, 62, 40, 255))
    draw.rounded_rectangle((955, 690, 1175, 730), radius=8, fill=(143, 96, 55, 255))

    for _ in range(320):
        x = random.randint(0, WIDTH)
        y = random.randint(650, HEIGHT)
        alpha = random.randint(22, 55)
        draw.ellipse((x, y, x + 2, y + 2), fill=(255, 255, 220, alpha))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay, "RGBA")
    overlay_draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(255, 248, 220, 28))
    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=105, threshold=3))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(OUT, quality=92)
    print(OUT)


if __name__ == "__main__":
    main()
