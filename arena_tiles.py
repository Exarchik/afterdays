"""PNG atlas terrain tiles; scenery never consumes gameplay RNG."""
import math
import heapq
from pathlib import Path
from collections import OrderedDict, deque
import hexgrid
import world_hex

PALETTES={
    'waste':('#605d47','#81785a','#494a39'),
    'forest':('#354c35','#72845a','#253c2d'),
    'ruin':('#555b56','#858b7c','#383e3b'),
    'city':('#61665e','#96998a','#424b46'),
    'road':('#4b4a43','#8c8975','#343a36'),
    'water':('#425e59','#71938a','#304c4a'),
    'cliff':('#65645b','#97917a','#454940'),
    'site':('#5e6050','#92917a','#404838'),
}

def road_directions(game,b):
    """Match actual world-road edges, including suppressed triangular links."""
    if b.get('dungeon'):return ()
    from world_map import road_neighbors
    origin=(game.x,game.y);kind=game.world[game.y][game.x]
    if kind=='road':neighbours=road_neighbors(game,origin)
    elif kind in ('city','site'):
        neighbours=[p for p in world_hex.neighbors(*origin,len(game.world[0]),len(game.world))
                    if game.world[p[1]][p[0]]=='road' and origin in road_neighbors(game,p)]
    else:return ()
    cx,cy=world_hex.center(origin)
    return tuple((world_hex.center(p)[0]-cx,world_hex.center(p)[1]-cy) for p in neighbours)


def road_cells(b,directions):
    """Connected asphalt arms follow world compass directions around obstacles."""
    if not directions:return frozenset()
    floor=set(map(tuple,b.get('floor',[(x,y) for y in range(b['h']) for x in range(b['w'])])))
    walk=floor-set(map(tuple,b.get('walls',[])))
    if not walk:return frozenset()
    cx,cy=hexgrid.center(((b['w']-1)/2,(b['h']-1)/2),1)
    hub=min(walk,key=lambda p:((hexgrid.center(p,1)[0]-cx)**2+(hexgrid.center(p,1)[1]-cy)**2,p))
    # BFS once: every arm remains on the same connected, walkable floor.
    previous={hub:None};queue=deque([hub])
    while queue:
        p=queue.popleft()
        for q in hexgrid.neighbors(*p,b['w'],b['h']):
            if q in walk and q not in previous:previous[q]=p;queue.append(q)
    hx,hy=hexgrid.center(hub,1);roads={hub}
    for dx,dy in directions:
        length=math.hypot(dx,dy);dx/=length;dy/=length
        def score(p):
            px,py=hexgrid.center(p,1);x,y=px-hx,py-hy
            return x*dx+y*dy-3*abs(x*dy-y*dx),p
        end=max(previous,key=score)
        # Prefer a straight projected arm among equally short hex routes.
        costs={hub:0};parents={hub:None};pending=[(0,hub)]
        while pending:
            cost,p=heapq.heappop(pending)
            if cost!=costs[p]:continue
            if p==end:break
            for q in hexgrid.neighbors(*p,b['w'],b['h']):
                if q not in previous:continue
                px,py=hexgrid.center(q,1)
                candidate=cost+1+.5*abs((px-hx)*dy-(py-hy)*dx)
                if candidate<costs.get(q,float('inf')):
                    costs[q]=candidate;parents[q]=p;heapq.heappush(pending,(candidate,q))
        while end is not None:roads.add(end);end=parents[end]
    # A three-cell-wide carriageway, clipped to walkable arena ground.
    roads.update(q for p in tuple(roads) for q in hexgrid.neighbors(*p,b['w'],b['h']) if q in walk)
    return frozenset(roads)


def terrain(game,b,pos,roads=frozenset()):
    main=b.get('biome',game.world[game.y][game.x])
    if b.get('dungeon'):return 'ruin'
    if list(pos) in b.get('water_cells',[]) or list(pos) in b.get('shore_cells',[]):return 'water'
    if tuple(pos) in roads:return 'road'
    if main=='road':
        surrounding=[game.world[y][x] for x,y in world_hex.neighbors(game.x,game.y,len(game.world[0]),len(game.world)) if game.world[y][x] not in ('road','city','site')]
        main=max(sorted(set(surrounding)),key=surrounding.count) if surrounding else 'waste'
    # Blend outer sectors toward the corresponding world neighbour.
    center=b.get('arena_center',hexgrid.center(((b['w']-1)/2,(b['h']-1)/2),1))
    point=hexgrid.center(pos,1);dx,dy=point[0]-center[0],point[1]-center[1]
    if 'arena_extent' in b:
        if max(abs(dx)/b['arena_extent'][0],abs(dy)/b['arena_extent'][1]+.5*abs(dx)/b['arena_extent'][0])<.65:return main
    elif math.hypot(dx,dy)<min(b['w'],b['h'])*.48:return main
    neighbours=world_hex.neighbors(game.x,game.y,len(game.world[0]),len(game.world))
    if not neighbours:return main
    # World cells use offset rows; compare rendered directions, not array offsets.
    def vector(p):
        return (p[0]+.5*(p[1]%2)-game.x-.5*(game.y%2),(p[1]-game.y)*.866)
    target=max(neighbours,key=lambda p:(dx*vector(p)[0]+dy*vector(p)[1])/math.hypot(*vector(p)))
    other=game.world[target[1]][target[0]]
    if other=='road':other=main
    return other if (pos[0]*13+pos[1]*7)%5 else main

ATLAS = Path(__file__).resolve().parent / 'assets/arena/terrain_atlas_v049.png'
TILE_PAIRS = {'waste':0, 'forest':2, 'ruin':4, 'city':6,
              'road':8, 'water':10, 'cliff':12, 'site':14}


_ATLAS=None
_TILES=OrderedDict()


def atlas():
    global _ATLAS
    if _ATLAS is None:
        from PIL import Image
        with Image.open(ATLAS) as source:_ATLAS=source.convert('RGBA')
    return _ATLAS


def tile_size(radius):
    return max(2,round(2*hexgrid.HALF_WIDTH*radius)),max(2,round(2*hexgrid.HALF_HEIGHT*radius))


def tile_image(kind, radius, variant, pad=0):
    """Hex-masked PIL tile for one terrain kind at the given hex radius (cached).

    pad enlarges the tile by that many pixels so neighbouring tiles overlap without seams.
    """
    from PIL import Image, ImageDraw
    width,height=tile_size(radius);width+=pad;height+=pad
    index=TILE_PAIRS.get(kind,0)+variant%2
    key=(index,width,height)
    if key not in _TILES:
        source=atlas();col,row=index%4,index//4
        bounds=(round(col*source.width/4),round(row*source.height/4),
                round((col+1)*source.width/4),round((row+1)*source.height/4))
        tile=source.crop(bounds).resize((width,height),Image.Resampling.LANCZOS)
        mask=Image.new('L',(width,height))
        ImageDraw.Draw(mask).polygon([(width-1,height/2),(3*width/4,height-1),
            (width/4,height-1),(0,height/2),(width/4,0),(3*width/4,0)],fill=255)
        tile.putalpha(mask)
        _TILES[key]=tile
    _TILES.move_to_end(key)
    while len(_TILES)>64:_TILES.popitem(last=False)
    return _TILES[key]


def photo(canvas, kind, radius, variant):
    from PIL import ImageTk
    root=canvas._root()
    if not hasattr(root,'_arena_photos'):root._arena_photos=OrderedDict()
    tile=tile_image(kind,radius,variant)
    key=(TILE_PAIRS.get(kind,0)+variant%2,)+tile.size;cache=root._arena_photos
    if key not in cache:cache[key]=ImageTk.PhotoImage(tile,master=root)
    cache.move_to_end(key)
    while len(cache)>128:cache.popitem(last=False)
    return cache[key]


def draw(c,kind,px,py,u,x,y):
    """Single tile on a Tk canvas (legacy path; the arena uses render_floor)."""
    base=PALETTES.get(kind,PALETTES['waste'])[0]
    c.create_polygon(*hexgrid.polygon(px,py,u),fill=base,outline=base)
    tile=photo(c,kind,u,(x*13+y*7)%2)
    if not hasattr(c,'_arena_refs'):c._arena_refs=[]
    c._arena_refs.append(tile)
    c.create_image(px,py,image=tile,anchor='center')


RIM_DEPTH=.65
RIM_LEFT,RIM_RIGHT,RIM_OUTLINE,RIM_LINE='#293b36','#34473e','#263730','#8c9479'
WATER_FILL,WATER_OUTLINE=(0x40,0x5f,0x4c,128),'#596c50'


def terrain_map(game,b,cells,roads=frozenset()):
    """Terrain of every floor cell; computed once per arena instead of every frame."""
    return {tuple(p):terrain(game,b,p,roads) for p in cells}


def floor_bounds(cells,rim,u):
    """Pixel bounds of the floor relative to the camera origin (ox,oy)."""
    xs=[];ys=[]
    for pos in cells:
        px,py=hexgrid.center(pos,u)
        xs+=(px-hexgrid.HALF_WIDTH*u,px+hexgrid.HALF_WIDTH*u);ys+=(py-hexgrid.HALF_HEIGHT*u,py+hexgrid.HALF_HEIGHT*u)
    for a,b in rim:ys+=(a[1]*u+RIM_DEPTH*u,b[1]*u+RIM_DEPTH*u)
    left,top=math.floor(min(xs))-2,math.floor(min(ys))-2
    return left,top,math.ceil(max(xs))+2,math.ceil(max(ys))+2


def render_floor(cells,kinds,rim,u,water=(),background='#18211d'):
    """Bake the static arena (rim sides, terrain tiles, water, rim outline) into one PIL image.

    Returns (image, left, top): the image's top-left corner is at (ox+left, oy+top) on screen.
    Drawing order matches the former per-item canvas renderer.
    """
    from PIL import Image, ImageDraw
    cells=list(cells)
    if not cells:return Image.new('RGB',(1,1),background),0,0
    left,top,right,bottom=floor_bounds(cells,rim,u)
    image=Image.new('RGBA',(right-left,bottom-top),background)
    draw=ImageDraw.Draw(image)
    def at(x,y):return x*u-left,y*u-top
    depth=RIM_DEPTH*u
    for a,b in sorted(rim,key=lambda edge:max(edge[0][1],edge[1][1])):
        ax,ay=at(*a);bx,by=at(*b)
        draw.polygon([(ax,ay),(bx,by),(bx,by+depth),(ax,ay+depth)],fill=RIM_LEFT if ax<bx else RIM_RIGHT,outline=RIM_OUTLINE)
    water=set(map(tuple,water));shade={}
    order=sorted(cells,key=lambda a:(hexgrid.center(a,1)[1],hexgrid.center(a,1)[0]))
    for x,y in order:
        px,py=hexgrid.center((x,y),u);px-=left;py-=top
        kind=kinds.get((x,y),'waste');base=PALETTES.get(kind,PALETTES['waste'])[0]
        poly=hexgrid.polygon(px,py,u);points=list(zip(poly[::2],poly[1::2]))
        draw.polygon(points,fill=base)
        # Tiles are 2 px larger than the hex, so rows and columns overlap instead of leaving seams.
        tile=tile_image(kind,u,(x*13+y*7)%2,pad=2)
        image.alpha_composite(tile,(round(px-tile.width/2),round(py-tile.height/2)))
        if (x,y) in water:
            # Former stippled water polygon: a half-transparent tint, then its outline, before the next cell.
            ix,iy=math.floor(px)-tile.width//2-2,math.floor(py)-tile.height//2-2
            fx,fy=px-ix,py-iy;key=(round(fx,2),round(fy,2))
            if key not in shade:
                patch=Image.new('RGBA',(tile.width+4,tile.height+4),(0,0,0,0))
                hexagon=hexgrid.polygon(fx,fy,u)
                ImageDraw.Draw(patch).polygon(list(zip(hexagon[::2],hexagon[1::2])),fill=WATER_FILL)
                shade[key]=patch
            image.alpha_composite(shade[key],(ix,iy))
            draw.polygon(points,outline=WATER_OUTLINE)
    for a,b in rim:draw.line([at(*a),at(*b)],fill=RIM_LINE,width=1)
    return image.convert('RGB'),left,top
