"""Prepare the supplied 5x5 emblem sheet for the standard Tk sprite loader."""
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'weapon_badges'

def build():
    with Image.open(ROOT / 'source.png') as source:
        source = source.convert('RGBA')
    # The supplied sheet has unequal margins, so use its actual gutters.
    xs = (10, 250, 501, 751, 1000, 1254)
    ys = (25, 270, 507, 744, 980, 1220)
    tiles = []
    for row in range(5):
        for col in range(5):
            tile = source.crop((xs[col], ys[row], xs[col+1], ys[row+1]))
            tiles.append(tile.crop(tile.getbbox()))
    for size in (16, 24, 32, 48, 64, 96, 144, 192):
        atlas = Image.new('RGBA', (size*5, size*5))
        for index, tile in enumerate(tiles):
            fitted = ImageOps.contain(tile, (size-2, size-2), Image.Resampling.LANCZOS)
            atlas.paste(fitted, (index%5*size+(size-fitted.width)//2,
                                 index//5*size+(size-fitted.height)//2))
        atlas.save(ROOT / f'atlas_{size}.png')

if __name__ == '__main__':
    build()
