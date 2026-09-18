"""Repack monster icons from intact source art. Offline: Pillow, numpy, scipy.

The generated sheet is not a uniform grid: creatures cross 222px boundaries.
Explicit rectangles separate illustrations; runtime needs no new dependencies.
Only atlas cells 64..75 and their metadata are changed.
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from scipy.ndimage import label, binary_dilation

ROOT = Path(__file__).resolve().parents[1]
BOXES = [
    (0, 0, 250, 245), (250, 0, 440, 245),
    (440, 0, 660, 245), (660, 0, 887, 245),
    (887, 0, 1110, 245), (1110, 0, 1330, 245),
    (1330, 0, 1552, 245), (1552, 0, 1774, 245),
    (0, 245, 230, 467), (230, 245, 446, 467),
    (446, 245, 670, 467), (670, 245, 887, 467),
]


def rebuild():
    source = Image.open(ROOT / 'assets/source_3.png').convert('RGBA')
    sprites, trims = [], []
    for box in BOXES:
        crop = source.crop(box)
        alpha = np.array(crop.getchannel('A'))
        labels, _ = label(alpha > 24)
        areas = np.bincount(labels.ravel())
        areas[0] = 0
        keep = areas >= max(12, areas.max() * .02)
        keep[0] = False
        mask = binary_dilation(keep[labels], iterations=2)
        crop.putalpha(Image.fromarray(np.where(mask, alpha, 0).astype('uint8')))
        trim = crop.getchannel('A').getbbox()
        sprites.append(crop.crop(trim))
        trims.append(trim)
    for path in sorted((ROOT / 'assets').glob('atlas_*.png')):
        size = int(path.stem.split('_')[-1])
        atlas = Image.open(path).convert('RGBA')
        for offset, sprite in enumerate(sprites):
            index = 64 + offset
            x, y = index % 16 * size, index // 16 * size
            atlas.paste((0, 0, 0, 0), (x, y, x + size, y + size))
            pic = sprite.copy()
            pic.thumbnail((size - 4, size - 4), Image.Resampling.LANCZOS)
            atlas.alpha_composite(pic, (x + (size - pic.width) // 2,
                                       y + (size - pic.height) // 2))
        temporary = path.with_suffix(".tmp.png")
        atlas.save(temporary, optimize=True)
        with Image.open(temporary) as check:
            check.load()
        temporary.replace(path)
    for relative in ('assets/manifest.json', 'data/sprites.json'):
        path = ROOT / relative
        data = json.loads(path.read_text(encoding='utf-8'))
        for entry in data.values():
            index = entry.get('index', -1)
            if entry.get('source') == 3 and 64 <= index < 76:
                entry['source_box'] = BOXES[index - 64]
                entry['trim'] = trims[index - 64]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Repacked 12 monsters in all 8 atlas sizes.')


if __name__ == '__main__':
    rebuild()
