"""Pillow rendering of the torn-map sheet: a real piece of the world on old paper.

The terrain uses the world view's hex art and road topology, so the sheet matches the
atlas exactly. The paper look is a sepia toning of that image with stains.
"""
import math
import random

import world_hex
from game.systems import torn_map

COLORS={'waste':'#665e49','road':'#665e49','forest':'#354a35','ruin':'#666359',
        'city':'#827346','site':'#708365','water':'#235665','cliff':'#686d64'}
FONTS=('segoepr.ttf','segoesc.ttf','segoeui.ttf','arial.ttf','DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')


def font(size):
    from PIL import ImageFont
    for name in FONTS:
        try:return ImageFont.truetype(name,size)
        except OSError:continue
    try:return ImageFont.load_default(size)
    except TypeError:return ImageFont.load_default()


def _bezier(a,c,b,steps=16):
    return [((1-t)**2*a[0]+2*(1-t)*t*c[0]+t*t*b[0],(1-t)**2*a[1]+2*(1-t)*t*c[1]+t*t*b[1])
            for t in (i/steps for i in range(steps+1))]


def _roads(draw,game,cells,point,radius):
    import world_map
    paths=[];junctions=[]
    for x,y in cells:
        if game.world[y][x]!='road':continue
        center=point((x,y));ends=[]
        for nxt in world_map.road_neighbors(game,(x,y)):
            other=point(nxt);ends.append(((center[0]+other[0])/2,(center[1]+other[1])/2))
        if len(ends)==2:paths.append(_bezier(ends[0],center,ends[1]))
        else:
            paths.extend([center,end] for end in ends)
            if ends:junctions.append(center)
    for color,width in (('#45463d',.67),('#777567',.49),('#a39d80',.035)):
        w=max(1,round(radius*width))
        for points in paths:draw.line(points,fill=color,width=w,joint='curve')
        if width>.1:
            for x,y in junctions:draw.ellipse((x-w/2,y-w/2,x+w/2,y+w/2),fill=color)


def render(game,state,ident,piece,target,paper=True):
    """RGB sheet of cols×rows pieces, each `piece` pixels; returns (image, target pixel)."""
    from PIL import Image,ImageDraw
    cols,rows=state['cols'],state['rows'];scale=2;size=piece*scale
    width,height=cols*size,rows*size
    r,ox,oy=torn_map.geometry(state['window'],cols,rows,state.get('bounds'))
    radius=r*size
    point=lambda p:world_hex.center(p,radius,ox*size,oy*size)
    w,h=len(game.world[0]),len(game.world)
    vx,vy,wc,wr=state['window']
    cells=[(x,y) for y in range(max(0,vy-3),min(h,vy+wr+3)) for x in range(max(0,vx-4),min(w,vx+wc+4))
           if -radius*2<point((x,y))[0]<width+radius*2 and -radius*2<point((x,y))[1]<height+radius*2]
    image=Image.new('RGBA',(width,height),COLORS['waste']);draw=ImageDraw.Draw(image)
    tw,th=max(2,round(math.sqrt(3)*radius)),max(2,round(2*radius))
    from world_hex_art import tile_image
    for x,y in cells:
        cx,cy=point((x,y))
        draw.polygon(world_hex.polygon(cx,cy,radius),fill=COLORS.get(game.world[y][x],COLORS['waste']),outline='#30392d')
        tile=tile_image(game,x,y,tw,th)
        image.alpha_composite(tile,(round(cx-tw/2),round(cy-th/2)))
    draw=ImageDraw.Draw(image)
    _roads(draw,game,cells,point,radius)
    image=image.convert('RGB')
    rng=random.Random('torn-map-paper:'+str(ident))
    image=_paper(image,rng) if paper else image
    ink=(59,42,23) if paper else (239,224,181);halo=(230,214,170) if paper else (20,30,25)
    draw=ImageDraw.Draw(image)
    label=font(round(size*.16))
    for n,pos in enumerate(game.cities):
        if tuple(pos) not in cells:continue
        cx,cy=point(tuple(pos));text=game.city_name(n)
        if not (0<cx<width and 0<cy<height):continue
        box=draw.textbbox((0,0),text,font=label);tw2=box[2]-box[0]
        x=min(max(4,cx-tw2/2),width-tw2-4);y=max(4,cy-radius-(box[3]-box[1])-6)
        draw.text((x,y),text,font=label,fill=ink,stroke_width=max(2,size//60),stroke_fill=halo)
    _compass(draw,size,ink)
    image=image.resize((cols*piece,rows*piece),Image.Resampling.LANCZOS)
    tx,ty=torn_map.target_point(state,target)
    return image,(tx*piece,ty*piece),r*piece


def _paper(image,rng):
    from PIL import Image,ImageChops,ImageDraw,ImageEnhance,ImageFilter,ImageOps
    w,h=image.size
    sepia=ImageOps.colorize(ImageOps.grayscale(image),'#2c1f10','#f6e8c2',mid='#9f8155')
    sepia=ImageEnhance.Contrast(Image.blend(image,sepia,.7)).enhance(1.08)
    sepia=ImageEnhance.Brightness(sepia).enhance(1.18)
    paper=Image.new('RGB',(w,h),'#ddc99a')
    noise=Image.effect_noise((w//2,h//2),24).resize((w,h)).convert('RGB')
    paper=ImageChops.multiply(paper,ImageEnhance.Brightness(noise).enhance(1.9))
    out=ImageChops.multiply(sepia,paper)
    out=Image.blend(out,Image.new('RGB',(w,h),'#e8d7a8'),.12)
    stains=Image.new('L',(w,h),0);d=ImageDraw.Draw(stains)
    for _ in range(5):
        x,y=rng.random()*w,rng.random()*h;r=(.06+rng.random()*.14)*min(w,h)
        d.ellipse((x-r,y-r*.8,x+r,y+r*.8),fill=60+rng.randrange(40))
    stains=stains.filter(ImageFilter.GaussianBlur(min(w,h)/25))
    return Image.composite(Image.new('RGB',(w,h),'#6e4b1e'),out,stains.point(lambda v:v*45//100))


def _compass(draw,size,ink):
    cx,cy,cr=size*.27,size*.4,size*.13
    draw.ellipse((cx-cr,cy-cr,cx+cr,cy+cr),outline=ink,width=max(2,size//90))
    draw.polygon([(cx,cy-cr*1.35),(cx+cr*.27,cy),(cx,cy+cr*1.35),(cx-cr*.27,cy)],fill=ink)
    f=font(round(size*.11));box=draw.textbbox((0,0),'Пн',font=f)
    draw.text((cx-(box[2]-box[0])/2,cy-cr*1.4-(box[3]-box[1])-4),'Пн',font=f,fill=ink)
