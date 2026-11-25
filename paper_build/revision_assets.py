from pathlib import Path
import json

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'revision_assets'
OUT.mkdir(exist_ok=True)
APPARATUS = ROOT.parent / 'models' / 'figure' / 'apparatus.png'
image = Image.open(APPARATUS).convert('RGBA')
image.crop(image.getchannel('A').getbbox()).save(OUT / 'apparatus_crop.png')


def save_tile(values, name):
    preview = Image.fromarray(np.round(255 * values).astype('uint8'))
    preview.resize((480, 480), Image.Resampling.NEAREST).save(OUT / f'{name}.png')


profiles = {}
for gap in (2, 4, 8):
    tile = np.zeros((96, 96))
    centre = 47  # Deliberate 1-sample offset from the block-average grid.
    start = centre - gap // 2
    tile[28:68, start - 2:start] = 1
    tile[28:68, start + gap:start + gap + 2] = 1
    coarse = tile.reshape(24, 4, 24, 4).mean((1, 3))
    save_tile(tile, f'vertical_{gap}')
    save_tile(tile.T, f'horizontal_{gap}')
    save_tile(coarse, f'coarse_{gap}')
    profiles[str(gap)] = {
        'target': tile[48, 36:60].tolist(),
        'coarse': coarse.repeat(4, 0).repeat(4, 1)[48, 36:60].tolist(),
    }
(OUT / 'profiles.json').write_text(json.dumps(profiles), encoding='utf-8')
