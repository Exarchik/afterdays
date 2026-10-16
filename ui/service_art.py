"""Full-height service art with a shaded caption area, cached per Tk root."""
from collections import OrderedDict
import sprites


def card_image(source,width,height):
    from PIL import Image,ImageDraw
    card=Image.new('RGBA',(width,height),'#1b2720')
    art=source.convert('RGBA')
    box=art.getbbox()
    if box:
        art=art.crop(box)
        art.thumbnail((max(1,width-8),max(1,height-4)),Image.Resampling.LANCZOS)
        card.alpha_composite(art,((width-art.width)//2,1))
    shade=Image.new('RGBA',card.size)
    draw=ImageDraw.Draw(shade);start=round(height*.58)
    for y in range(start,height):
        draw.line((0,y,width-1,y),fill=(12,20,16,round(225*(y-start)/max(1,height-start-1))))
    return Image.alpha_composite(card,shade)


def photo(widget,key,width,height):
    from PIL import ImageTk
    source=sprites.photo(widget,key,max(sprites.SIZES))
    if source is None:return None
    root=widget._root()
    if not hasattr(root,'_service_art_cache'):root._service_art_cache=OrderedDict()
    cache=root._service_art_cache
    identity=(str(source),width,height)
    if identity not in cache:
        cache[identity]=ImageTk.PhotoImage(card_image(ImageTk.getimage(source),width,height),master=root)
        if len(cache)>96:cache.popitem(last=False)
    cache.move_to_end(identity)
    return cache[identity]
