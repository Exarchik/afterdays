"""Render an unfogged world using the game's actual tile selection. Requires Pillow."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import game.model as afterdays
from terrain_tiles import tile_key,INDEX,ROOT
from PIL import Image,ImageDraw,ImageFont

def render(seed=13,destination='Afterdays-world.png'):
    g=afterdays.Game(seed)
    atlas=Image.open(ROOT/'terrain_v2.png');size=40
    out=Image.new('RGB',(len(g.world[0])*size,len(g.world)*size+64),'#17201c');d=ImageDraw.Draw(out)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
    d.text((16,12),f'AFTERDAYS · Повна мапа {len(g.world[0])} × {len(g.world)} · seed {seed} · без туману війни',font=font,fill='#e4e9ce')
    for y in range(len(g.world)):
        for x in range(len(g.world[0])):
            n=INDEX[tile_key(g,x,y)];tx=n%32*64;ty=n//32*64
            tile=atlas.crop((tx,ty,tx+64,ty+64)).resize((size,size),Image.Resampling.LANCZOS)
            out.paste(tile,(x*size,64+y*size))
    d=ImageDraw.Draw(out)
    for i,(x,y) in enumerate(g.cities):
        cx=x*size+size//2;cy=64+y*size+size//2
        d.ellipse((cx-12,cy-12,cx+12,cy+12),fill='#182222',outline='#edc267',width=2)
        d.text((cx,cy),str(i+1),anchor='mm',fill='#ffffff')
    x,y=g.x*size+20,64+g.y*size+20
    d.polygon([(x,y-9),(x-8,y+7),(x+8,y+7)],fill='#89ffb2')
    out.save(destination)
if __name__=='__main__':render(int(sys.argv[1]) if len(sys.argv)>1 else 13,sys.argv[2] if len(sys.argv)>2 else 'Afterdays-world.png')
