"""Runtime hex masks for the approved draft art; no generated files or rad variants.

The source's irregular rows are normalized in memory. Road arms are drawn by
the map renderer from topology, rather than trusting the draft's junctions.
"""
from collections import OrderedDict
from pathlib import Path
import math

SOURCE=Path(__file__).resolve().parent/'assets'/'hex'/'terrain_hex_v01.png'
ROWS=(0,200,388,575,757,932,1086)


def art_cell(game,x,y):
    kind=game.world[y][x];variant=(x*17+y*31)%8
    if kind in ('waste','road'):return 0,variant
    if kind=='forest':return 1,variant
    if kind=='ruin':return 2,variant%3
    if kind=='city':return 2,3+variant%3
    if kind=='site':return 2,6+variant%2
    if kind=='cliff':return 4,variant
    if kind=='water':return 3,variant%2
    return 0,0


_SOURCE=None
_TILES={}


def _source_tile(row,col):
    """Trimmed RGBA art of one terrain cell (shared by the world view and paper maps)."""
    global _SOURCE
    from PIL import Image
    if _SOURCE is None:
        with Image.open(SOURCE) as image:_SOURCE=image.convert('RGBA')
    if (row,col) not in _TILES:
        sheet=_SOURCE
        tile=sheet.crop((round(col*sheet.width/8)+3,ROWS[row]+3,
                         round((col+1)*sheet.width/8)-3,ROWS[row+1]-3))
        # Ignore isolated low-opacity edge noise when finding the content.
        bbox=tile.getchannel('A').point(lambda a:255 if a>200 else 0).getbbox()
        _TILES[row,col]=tile.crop(bbox) if bbox else tile
    return _TILES[row,col]


def tile_image(game,x,y,width,height):
    """Terrain art of cell (x,y) scaled to width×height and masked to the hex."""
    from PIL import Image,ImageDraw,ImageChops
    row,col=art_cell(game,x,y)
    image=_source_tile(row,col).resize((width,height),Image.Resampling.LANCZOS)
    # A common exact mask defines geometry, independent of generated outlines.
    mask=Image.new('L',(width,height),0)
    ImageDraw.Draw(mask).polygon([(width/2,0),(width-1,height/4),(width-1,height*3/4),
                                 (width/2,height-1),(0,height*3/4),(0,height/4)],fill=255)
    # Source content may have tiny transparent holes: the map's base polygon
    # supplies matching ground underneath, while outer pixels remain clear.
    image.putalpha(ImageChops.multiply(image.getchannel('A'),mask))
    return image


def photo(canvas,game,x,y,radius):
    from PIL import ImageTk
    root=canvas._root()
    if not hasattr(root,'_world_hex_photos'):root._world_hex_photos=OrderedDict()
    row,col=art_cell(game,x,y)
    width=max(2,round(math.sqrt(3)*radius));height=max(2,round(2*radius))
    key=(row,col,width,height);cache=root._world_hex_photos
    if key not in cache:
        cache[key]=ImageTk.PhotoImage(tile_image(game,x,y,width,height),master=root)
    cache.move_to_end(key)
    while len(cache)>256:cache.popitem(last=False)
    return cache[key]
