from pathlib import Path
import json
import numpy as np
from PIL import Image

root=Path(r'D:\srdd\paper_build')
run=Path(r'D:\Desktop\汇报\新建文件夹 (1)\20260917_143733_877999')
dest=root/'assets'
dest.mkdir(exist_ok=True)
def save(name,a):
    a=(np.clip(a,0,1)*255).round().astype('uint8')
    Image.fromarray(a).resize((480,480),Image.Resampling.NEAREST).save(dest/(name+'.png'))
for digit,idx in [(7,0),(2,1),(1,2),(6,11),(8,61)]:
    d=run/f'digit_{digit}_index_{idx}'
    a=np.load(d/'target_96x96.npy',allow_pickle=False)
    p=np.load(d/'encoder_phase_24x24_rad.npy',allow_pickle=False)
    b=np.load(d/'normalized_reconstruction_96x96.npy',allow_pickle=False)
    assert a.shape==b.shape==(96,96) and p.shape==(24,24)
    for n,v in [('target',a),('phase',p/(2*np.pi)),('rec',b),('lr',a.reshape(24,4,24,4).mean((1,3)))]:save(f'{digit}_{n}',v)
for kind in ['v','h']:
    a=np.zeros((96,96))
    a[29:67,44:46]=a[29:67,48:50]=1
    if kind=='h':a=a.T
    save(kind+'_fine',a)
    save(kind+'_coarse',a.reshape(24,4,24,4).mean((1,3)))
    if kind=='v':
        v=a[48,36:60]
        c=a.reshape(24,4,24,4).mean((1,3)).repeat(4,0).repeat(4,1)[48,36:60]
        (dest/'profiles.json').write_text(json.dumps({'target':v.tolist(),'coarse':c.tolist()}))
