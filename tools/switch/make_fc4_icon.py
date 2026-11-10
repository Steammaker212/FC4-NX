"""fc4-nx: the NRO/NSP icon (256x256 JPEG) from the game's own logo, SPLASH_720.PNG on the user's disc.

The output is made from game data: it goes to tools/switch/icon/fc4_icon.jpg (ignored by git, picked up by
app/CMakeLists.txt) and is never committed or shared.

    py -3 tools/switch/make_fc4_icon.py [--splash ../game/SPLASH_720.PNG] [--out tools/switch/icon/fc4_icon.jpg]
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--splash', default=os.path.join(ROOT, '..', 'game', 'SPLASH_720.PNG'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'tools', 'switch', 'icon', 'fc4_icon.jpg'))
    ap.add_argument('--size', type=int, default=256)
    args = ap.parse_args()

    size = args.size
    logo = Image.open(args.splash).convert('RGBA')
    # The logo's own pixels: anything brighter than the black background.
    lum = logo.convert('L').point(lambda v: 255 if v > 24 else 0)
    logo = logo.crop(lum.getbbox())

    # Background: near black with a warm glow behind the logo (the "4"'s orange), soft at the edges.
    bg = Image.new('RGB', (size, size), (10, 9, 8))
    glow = Image.new('L', (size, size), 0)
    ImageDraw.Draw(glow).ellipse((-size // 4, size // 4, size + size // 4, size * 3 // 4 + size // 8), fill=110)
    glow = glow.filter(ImageFilter.GaussianBlur(size // 6))
    bg.paste(Image.new('RGB', (size, size), (120, 40, 14)), (0, 0), glow)

    # The logo across the icon with a margin, centred.
    width = int(size * 0.90)
    height = round(logo.height * width / logo.width)
    logo = logo.resize((width, height), Image.LANCZOS)
    alpha = logo.convert('L').point(lambda v: min(255, v * 3))  # the black around the letters drops out
    bg.paste(logo.convert('RGB'), ((size - width) // 2, (size - height) // 2), alpha)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    bg.save(args.out, 'JPEG', quality=95)
    print(f'{args.out}: {size}x{size}')


if __name__ == '__main__':
    main()
