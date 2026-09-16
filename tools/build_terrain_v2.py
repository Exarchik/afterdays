"""Offline atlas preparation; Pillow needed only to rebuild assets, not to play."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import json
ROOT=Path(__file__).resolve().parents[1]/'assets'
S=64
im=Image.open(ROOT/'terrain_roads_source.png').convert('RGB')
# Hand-checked row boundaries: the generated sheet has unequal row heights.
ys=[0,90,178,266,354,437,522,606,695,780,876,973,1070,1167,1264,1361,1458,1555,1655,1755,1855,1955,2032]
def crop(row,col):
    return im.crop((round(col*im.width/8)+2,ys[row]+2,round((col+1)*im.width/8)-2,ys[row+1]-2)).resize((S,S),Image.Resampling.LANCZOS)
tiles={f'waste{i}':crop(0,i) for i in range(8)}
# Synthesize quarter masks with shared geometry; all 8-neighbour patterns supported.
for kind,row in [('water',1),('forest',3),('cliff',5),('ruin',7)]:
    full=crop(row,0)
    for bits in range(256):
        mask=Image.new('L',(S,S),255);d=ImageDraw.Draw(mask)
        for sx,sy,h,v,diag in [(-1,-1,8,1,16),(1,-1,2,1,32),(1,1,2,4,64),(-1,1,8,4,128)]:
            # At missing cardinal neighbours, an earth margin follows the border.
            x0=0 if sx<0 else 32;y0=0 if sy<0 else 32
            if not bits&h:d.rectangle((x0 if sx<0 else 54,y0,9 if sx<0 else 63,y0+31),fill=0)
            if not bits&v:d.rectangle((x0,y0 if sy<0 else 54,x0+31,9 if sy<0 else 63),fill=0)
            if bits&h and bits&v and not bits&diag:
                cx=0 if sx<0 else 63;cy=0 if sy<0 else 63
                d.ellipse((cx-12,cy-12,cx+12,cy+12),fill=0)
        mask=mask.filter(ImageFilter.GaussianBlur(2))
        tiles[f'{kind}_{bits}']=Image.composite(full,tiles['waste0'],mask)
# Normalize road arms instead of trusting malformed generated end/corner tiles.
for family,row in [('waste',9),('forest',11),('ruin',13),('cliff',15),('water',17),('rad',19)]:
    base=tiles['waste0'] if family in ('waste','rad') else tiles[f'{family}_255']
    if family=='rad':base=crop(21,0)
    vertical=crop(row,5);horizontal=crop(row,6);cross=crop(row+1,7)
    for bits in range(16):
        tile=base.copy()
        for bit,box,src in [(1,(21,0,43,32),vertical),(2,(32,21,64,43),horizontal),(4,(21,32,43,64),vertical),(8,(0,21,32,43),horizontal)]:
            if bits&bit:tile.paste(src.crop(box),box[:2])
        tile.paste(cross.crop((21,21,43,43)),(21,21))
        tiles['road'+str(bits) if family=='waste' else f'road_{family}_{bits}']=tile
old=Image.open(ROOT/'terrain_tiles.png').convert('RGB')
oldindex=json.loads((ROOT/'terrain_manifest.json').read_text())
for key in ('city','site'):
    n=oldindex[key];tiles[key]=old.crop((n%8*64,n//8*64,n%8*64+64,n//8*64+64))
# Radiation tint retains the original biome silhouette, unlike the legacy replacement.
for key,tile in list(tiles.items()):
    if key.startswith('road_rad'):continue
    tint=Image.new('RGB',(S,S),(107,142,28))
    tiles[key+'_rad']=Image.blend(tile,tint,.24)
columns=32
sheet=Image.new('RGB',(columns*S,((len(tiles)+columns-1)//columns)*S))
for n,tile in enumerate(tiles.values()):sheet.paste(tile,(n%columns*S,n//columns*S))
sheet.save(ROOT/'terrain_v2.png')
(ROOT/'terrain_v2.json').write_text(json.dumps({k:n for n,k in enumerate(tiles)},indent=2))
print(len(tiles),'prepared tiles')
