import quest_area
"""Tk rendering of the pointy-top hex overworld and its overview atlas."""
from dataclasses import dataclass
import math
import world_hex as grid

COLORS={'waste':'#665e49','road':'#665e49','forest':'#354a35','ruin':'#666359',
        'city':'#827346','site':'#708365','water':'#235665','cliff':'#686d64'}
HINT='Клік — обрати маршрут · ▶ — рух · Q/W — вгору ліворуч/праворуч · A/D — ліворуч/праворуч\nZ/X — вниз ліворуч/праворуч · Пробіл — пауза · E — дія · Shift+M — атлас'


@dataclass
class View:
    radius: float
    ox: float
    oy: float
    vx: int
    vy: int
    cols: int
    rows: int

    def point(self,pos):return grid.center(pos,self.radius,self.ox,self.oy)
    def cell(self,x,y):return grid.cell(x,y,self.radius,self.ox,self.oy)
    def polygon(self,pos,scale=1):return grid.polygon(*self.point(pos),self.radius*scale)
    def visible(self,pos):return self.vx<=pos[0]<self.vx+self.cols and self.vy<=pos[1]<self.vy+self.rows
    def edge(self,a,b):return grid.edge(a,b,self.radius,self.ox,self.oy)


def layout(width,height,w,h,focus=None):
    cols,rows=(min(w,18),min(h,13)) if focus is not None else (w,h)
    vx=max(0,min(w-cols,round(focus[0])-cols//2)) if focus is not None else 0
    vy=max(0,min(h-rows,round(focus[1])-rows//2)) if focus is not None else 0
    # Include the extreme shifted row even when viewport endpoints are even.
    xs=[grid.center((x,y))[0] for x in (vx,vx+cols-1) for y in range(vy,vy+rows)]
    left,right=min(xs)-math.sqrt(3)/2,max(xs)+math.sqrt(3)/2
    top,bottom=1.5*vy-1,1.5*(vy+rows-1)+1
    radius=max(.1,min((max(20,width)-8)/(right-left),(max(20,height)-8)/(bottom-top)))
    return View(radius,(width-(left+right)*radius)/2,(height-(top+bottom)*radius)/2,vx,vy,cols,rows)


def draw(app,canvas=None,overview=False):
    c=canvas if canvas is not None else app.canvas;g=app.game
    v=layout(c.winfo_width(),c.winfo_height(),len(g.world[0]),len(g.world),
             None if overview else app.fx.reveal_focus())
    if not overview:
        app.world_view=v;app.tile=v.radius*2;app.vx,app.vy=v.vx,v.vy
        app.ox,app.oy=v.ox,v.oy
        app.map_title.config(text='ГЕКСАГОНАЛЬНА МАПА · 6 напрямків')
    from debug_config import TEST_MODE
    explored=set(g.explored)
    full=TEST_MODE and app.show_full_map
    known_cell=lambda x,y:full or f'{x},{y}' in explored
    visible=lambda x,y:v.visible((x,y)) and known_cell(x,y)
    # Include neighbouring terrain because road arms depend on offscreen neighbours.
    terrain=tuple((x,y,g.world[y][x],known_cell(x,y))
                  for y in range(max(0,v.vy-1),min(len(g.world),v.vy+v.rows+1))
                  for x in range(max(0,v.vx-1),min(len(g.world[0]),v.vx+v.cols+1)))
    key=(id(g),v,overview,terrain)
    rebuild=getattr(c,'_world_background_key',None)!=key or not c.find_withtag('world_hex')
    if rebuild:
        c.delete('all');c._terrain_refs=[]
        for y in range(v.vy,v.vy+v.rows):
            for x in range(v.vx,v.vx+v.cols):
                known=known_cell(x,y);kind=g.world[y][x]
                color=COLORS.get(kind,COLORS['waste']) if known else '#101714'
                c.create_polygon(*v.polygon((x,y)),fill=color,outline='#30392d' if known else '#223128',tags='world_hex')
                if not known:continue
                if not overview:
                    from world_hex_art import photo
                    image=photo(c,g,x,y,v.radius)
                    c._terrain_refs.append(image)
                    c.create_image(*v.point((x,y)),image=image,tags='world_terrain')
        draw_roads(c,g,v,known_cell,overview)
        c._world_background_key=key
    else:
        c.delete('route')
    c=OverlayCanvas(c,reset=rebuild)
    trails=set(map(tuple,g.trails))
    for pos in sorted(trails):
        if not visible(*pos):continue
        for nxt in grid.adjacent(pos):
            if nxt in trails and nxt>pos and visible(*nxt):
                c.create_line(*v.point(pos),*v.point(nxt),fill='#c5b590',dash=(3,2),width=1,tags='trail')
    for key in g.radiation:
        x,y=map(int,key.split(','))
        if visible(x,y):
            c.create_polygon(*v.polygon((x,y),.91),fill='#a4bf55',stipple='gray25',outline='#a4bf55',tags='radiation_hex')
            if not overview:c.create_text(*v.point((x,y)),text='☢',fill='#d0e775',font=('Segoe UI',max(8,round(v.radius*.6))),tags='radiation_hex')
    for pos in g.storm_cells():
        if visible(*pos):c.create_polygon(*v.polygon(pos),fill='#bad657',stipple='gray50',outline='#dfeb77',tags='storm')
    if g.storm and visible(*g.storm['pos']):
        c.create_text(*v.point(g.storm['pos']),text='☢',fill='#f3f5ad',font=('Segoe UI',max(8,round(v.radius*.7)),'bold'),tags='storm')
    draw_borders(c,g,v,visible)
    draw_areas(c,g,v)
    if overview:draw_metro(c,g,v,visible)
    from recovery_ui import draw_markers
    draw_markers(c,g,v.radius*2,0,0,visible,point=v.point)
    for cache in g.reputation_state.get('road_caches',[]):
        if not cache['opened'] and visible(*cache['pos']):
            c.create_text(*v.point(cache['pos']),text='▣',fill='#efc76b',font=('Segoe UI',10 if overview else 14,'bold'),tags='road_cache')
    for n,pos in enumerate(g.cities):
        if not v.visible(pos) or not app.map_city_known(n):continue
        px,py=v.point(pos)
        special=g.world[pos[1]][pos[0]]=='site'
        dash=(2,2) if overview else (4,3)
        outline=dict(fill='',dash=dash if special else (),tags='location_outline')
        # A dark under-stroke keeps the thin blue edge legible over bright art.
        c.create_polygon(*v.polygon(pos,.96),outline='#193b4b',width=3 if not overview else 2,**outline)
        c.create_polygon(*v.polygon(pos,.96),outline='#71d2ff',width=1.5 if not overview else 1,**outline)
        c.create_text(px,py-v.radius-3,text=g.city_name(n),fill=g.city_color(n,'#efe0b5'),
                      anchor='s',font=('Segoe UI',8),tags='city_name')
    for q in g.quests:
        if q['status']!='active':continue
        from quest_navigation import destination,edge_arrow
        ready=g.quest_ready(q);pos=destination(g,q)
        if pos is None:continue
        if not v.visible(pos):
            if not overview:
                arrow=edge_arrow(v,pos,(g.x,g.y))
                if arrow:
                    c.create_polygon(*arrow,fill='#ba8be5' if q.get('unique') else '#efd36f',outline='#28382c',width=1,tags='quest_edge_arrow')
            continue
        px,py=v.point(pos)
        if list(pos)==[g.x,g.y]:px+=v.radius*.6;py-=v.radius*.6
        size=6 if overview else v.radius*.5
        c.create_oval(px-size,py-size,px+size,py+size,fill='#ae7ed2' if q.get('unique') else '#c9a252',outline='#f9dd8d',tags='quest_marker')
        c.create_text(px,py,text='✓' if ready else '!',fill='#14291f',font=('Segoe UI',max(8,round(size*1.4)),'bold'),tags='quest_marker')
    if not overview:
        import sprites
        for npc in g.settlers():
            if npc['state'] in ('offered','active','permission') and visible(*npc['pos']):
                px,py=v.point(npc['pos']);size=v.radius*1.5
                sprites.draw(c,'npc:mayor' if npc['role']=='mayor' else 'npc_roamer_'+npc['role'],px-size/2,py-size/2,size)
        app.route.paint()
    px,py=v.point((g.x,g.y) if overview else app.route.position())
    size=4 if overview else v.radius*.6
    c.create_oval(px-size,py-size,px+size,py+size,fill='#cce4d0',outline='#ffffff',width=2,tags='world_player_ring')
    c.create_polygon(px,py-size*.75,px+size*.55,py+size*.55,px,py+size*.3,px-size*.55,py+size*.55,fill='#233a31',tags='world_player_arrow')
    if not overview:
        if g.coward_turns:c.create_text(px,py-v.radius*1.1,text='⚑',fill='#ed795c',font=('Segoe UI',12,'bold'),tags='coward_icon')
        if g.traveler and g.traveler['pos']==[g.x,g.y]:
            c.create_text(px+v.radius*.8,py-v.radius,text='¤',fill='#f1d383',font=('Segoe UI',16,'bold'))
        app.hint.config(text=HINT+('\nТут лежать ваші речі. E — відкрити надгробок.' if g.local_graves() else ''))
    c.finish()
    return v


def road_neighbors(g,pos):
    """Suppress the largest edge of each tiny triangle, preserving connectivity."""
    pos=tuple(pos)
    candidates={p for p in grid.neighbors(*pos,len(g.world[0]),len(g.world))
                if g.world[p[1]][p[0]] in ('road','city','site')}
    edge=lambda a,b:tuple(sorted((a,b)))
    return [p for p in sorted(candidates)
            if not any(edge(pos,p)==max(edge(pos,p),edge(pos,q),edge(p,q))
                       for q in candidates.intersection(grid.adjacent(p)))]


def draw_roads(c,g,v,revealed,overview=False):
    """One road layer above terrain; continuous strokes meet on shared edges."""
    paths=[];junctions=[]
    for y in range(v.vy,v.vy+v.rows):
        for x in range(v.vx,v.vx+v.cols):
            pos=(x,y);kind=g.world[y][x]
            # City and special-location art stays clear; roads end at the shared edge.
            if kind!='road' or not revealed(x,y):continue
            center=v.point(pos)
            neighbors=road_neighbors(g,pos)
            ends=[]
            for nxt in neighbors:
                other=v.point(nxt)
                ends.append(((center[0]+other[0])/2,(center[1]+other[1])/2))
            # On bends a quadratic spline is tangent to both adjoining segments.
            # Its endpoints remain exactly at the shared edge midpoints.
            if len(ends)==2:
                paths.append((*ends[0],*center,*ends[1]))
            else:
                paths.extend((*center,*end) for end in ends)
                if ends:junctions.append(center)
    # Draw the entire shoulder first, then the entire surface. Individual tile
    # caps can never cover another tile's asphalt or create dark seams.
    for color,width in (('#45463d',.67),('#777567',.49)):
        for points in paths:
            c.create_line(*points,fill=color,width=max(1,v.radius*width),
                          capstyle='butt',joinstyle='round',smooth=True,
                          splinesteps=16,tags='hex_road')
        radius=max(1,v.radius*width)/2
        for x,y in junctions:
            c.create_oval(x-radius,y-radius,x+radius,y+radius,fill=color,outline='',tags='hex_road')
    # Subtle solid center marking avoids restarting dash patterns at every hex.
    if not overview:
        for points in paths:
            c.create_line(*points,fill='#a39d80',width=max(1,v.radius*.035),
                          capstyle='butt',joinstyle='round',smooth=True,
                          splinesteps=16,tags='hex_road')


def draw_borders(c,g,v,visible):
    for a,b in g.border_edges():
        if not (visible(*a) or visible(*b)):continue
        line=v.edge(a,b)
        c.create_line(*line,fill='#111511',width=2,dash=(4,3),tags='border')
        if g.checkpoint(a,b):
            x,y=(line[0]+line[2])/2,(line[1]+line[3])/2;s=max(2,v.radius*.25)
            c.create_rectangle(x-s,y-s,x+s,y+s,fill='#79bd83' if g.border_open else '#d47554',outline='#111111',tags='checkpoint')


def draw_areas(c,g,v):
    for q in g.quests:
        if q['status']!='active':continue
        if q.get('kind')=='hunt':
            from expedition_ui import defense_cells
            cells=defense_cells(g,q);color='#e5b75b'
        elif q.get('area') and not g.quest_ready(q):
            cells=set(quest_area.cells(q))
            color='#8bc4e4' if q['kind']=='scout' else '#99dd9f'
        else:continue
        for pos in sorted(cells):
            if not v.visible(pos):continue
            for nxt in grid.adjacent(pos):
                if nxt not in cells:c.create_line(*v.edge(pos,nxt),fill=color,width=2,dash=(5,3),tags='quest_area')
        for pos in q.get('visited_cells',[]) if q['kind']=='scout' else q.get('searched_cells',[]):
            if v.visible(pos):c.create_text(*v.point(pos),text='✓' if q['kind']=='scout' else '×',fill=color,tags='quest_area')


def draw_metro(c,g,v,visible):
    from metro_routes import station_order
    order=station_order(g)
    for a,b in zip(order,order[1:]):
        pa,pb=v.point(g.cities[a]),v.point(g.cities[b]);steps=max(1,grid.distance(g.cities[a],g.cities[b])*8)
        bright=all(n in g.known_cities and n in g.metro_unlocked for n in (a,b));start=None
        def point(t):return tuple(pa[i]+(pb[i]-pa[i])*t for i in (0,1))
        for n in range(steps):
            shown=visible(*v.cell(*point((n+.5)/steps)))
            if shown and start is None:start=point(n/steps)
            if start is not None and (not shown or n==steps-1):
                c.create_line(*start,*point((n if not shown else n+1)/steps),fill='#58d9d1' if bright else '#47615d',width=2,dash=(7,4),tags='metro_route');start=None
    for n in order:
        if not visible(*g.cities[n]):continue
        x,y=v.point(g.cities[n]);color='#58d9d1' if n in g.metro_unlocked else '#658079'
        c.create_oval(x-5,y-5,x+5,y+5,fill='#173b3a',outline=color,tags='metro_station')
        c.create_text(x,y,text='M',fill=color,font=('Segoe UI',7,'bold'),tags='metro_station')


class OverlayCanvas:
    """Retain dynamic canvas items; update only changed geometry or options."""
    def __init__(self,canvas,reset=False):
        self.canvas=canvas;self.index=0;self.changed=False
        if reset or not hasattr(canvas,'_world_overlay_items'):canvas._world_overlay_items=[]
        self.items=canvas._world_overlay_items
    def __getattr__(self,name):
        method=getattr(self.canvas,name)
        if not name.startswith('create_'):return method
        def create(*args,**kwargs):
            tags=kwargs.get('tags',())
            if isinstance(tags,str):tags=(tags,)
            kwargs['tags']=tuple(tags)+('world_overlay',)
            index=self.index;self.index+=1
            if index<len(self.items):
                old_name,old_args,old_options,ident=self.items[index]
                if old_name==name:
                    if args!=old_args or any(t.startswith('world_player') for t in tags):self.canvas.coords(ident,*args)
                    options={k:v for k,v in kwargs.items() if old_options.get(k)!=v}
                    # Reset options that disappear when this slot represents another object.
                    if old_options.keys()!=kwargs.keys():
                        self.canvas.delete(ident);ident=method(*args,**kwargs);self.changed=True
                    elif options:self.canvas.itemconfigure(ident,**options)
                else:
                    self.canvas.delete(ident);ident=method(*args,**kwargs);self.changed=True
                self.items[index]=(name,args,kwargs,ident)
            else:
                ident=method(*args,**kwargs);self.items.append((name,args,kwargs,ident));self.changed=True
            return ident
        return create
    def finish(self):
        for _,_,_,ident in self.items[self.index:]:self.canvas.delete(ident)
        del self.items[self.index:]
        if self.changed:
            for _,_,_,ident in self.items:self.canvas.tag_raise(ident)
        for tag in ('world_player_ring','world_player_arrow','coward_icon','fx'):self.canvas.tag_raise(tag)
