"""Geometry of the circuit-board module art (assets/custom/sources/chemes.png), without Tk.

Every module is a 150×150 tile: the piece is cropped to its visible pixels, fitted into 130×130
and centred. Contacts sit on the visible edge of the piece, so the model and the UI share
the same coordinates.
"""
from functools import lru_cache
from pathlib import Path

SOURCE=Path(__file__).resolve().parent/'assets/custom/sources/chemes.png'
PIECES=16
TILE=150
FIT=130


@lru_cache(maxsize=1)
def _sheet():
    from PIL import Image
    with Image.open(SOURCE) as raw:return raw.convert('RGBA')


@lru_cache(maxsize=None)
def tile(piece):
    """PIL RGBA tile of one module, unrotated."""
    from PIL import Image,ImageOps
    source=_sheet();x,y=piece%4,piece//4
    crop=source.crop((round(x*source.width/4),round(y*source.height/4),round((x+1)*source.width/4),round((y+1)*source.height/4)))
    box=crop.getbbox()
    if box:crop=crop.crop(box)
    fit=ImageOps.contain(crop,(FIT,FIT),Image.Resampling.LANCZOS)
    result=Image.new('RGBA',(TILE,TILE));result.alpha_composite(fit,((TILE-fit.width)//2,(TILE-fit.height)//2))
    return result


@lru_cache(maxsize=None)
def edge_points(piece):
    """Candidate contact positions on the visible edge: left/right at 8 heights, top/bottom at 8 widths."""
    image=tile(piece);alpha=image.getchannel('A');box=alpha.point(lambda a:255 if a>180 else 0).getbbox() or (10,10,140,140)
    left,top,right,bottom=box;points=[]
    for k in range(8):
        f=.12+k*.76/7
        yy=round(top+(bottom-top)*f)
        xs=[x for x in range(TILE) if alpha.getpixel((x,yy))>180]
        if xs:points+=[('L',max(4,min(xs)-2),yy),('R',min(TILE-4,max(xs)+2),yy)]
        xx=round(left+(right-left)*f)
        ys=[y for y in range(TILE) if alpha.getpixel((xx,y))>180]
        if ys:points+=[('T',xx,max(4,min(ys)-2)),('B',xx,min(TILE-4,max(ys)+2))]
    return tuple(points)


def choose_contacts(rng,piece,count):
    """count contacts on the module edge, at least 30 px apart and on at least two sides; contact 1 first."""
    pool=list(edge_points(piece));best=[]
    for _ in range(80):
        rng.shuffle(pool);chosen=[]
        for side,x,y in pool:
            if len(chosen)>=count:break
            if all((x-a)**2+(y-b)**2>30**2 for _,a,b in chosen):chosen.append((side,x,y))
        if len(chosen)==count and len({side for side,_,_ in chosen})>=2:return [[x,y] for _,x,y in chosen]
        if len(chosen)>len(best):best=chosen
    return [[x,y] for _,x,y in best]


def rotate(point,angle):
    """Rotate a tile point clockwise by angle×90° around the tile centre."""
    x,y=point
    for _ in range(angle%4):x,y=TILE-y,x
    return [x,y]
