from i18n import t as tr
"""Short floating messages, combat traces, town service cards and shared storage."""
import copy
import sprites
from debug_config import TEST_MODE
import math
import time
import tkinter as tk
from tkinter import ttk
import afterdays as r
import progression as p
import adventure as a
from visuals import BG,PANEL,TEXT,MUTED,GOLD,icon,ItemGrid,Drag,inside


class Effects:
    def __init__(self,app):
        self.app=app;self.game=app.game;self.active=[];self.snapshot=None;self.until=0
        app.root.after(33,self.tick)

    @property
    def blocked(self):
        now=time.monotonic()
        return (self.snapshot is not None and now<self.until) or any(e['kind']=='move' and now<e['start']+e['duration'] for e in self.active)

    def ingest(self):
        g=self.app.game
        if g is not self.game:
            self.active=[];self.snapshot=None;self.game=g
        now=time.monotonic();timeline=0;texts=0
        for event in g.pop_events():
            event=dict(event);kind=event['kind']
            duration=min(.55,max(.12,.07*(len(event.get('path',[]))-1))) if kind=='move' else .4 if kind in ('attack','slash') else 1.0
            if kind in ('move','attack','slash'):
                delay=timeline;timeline+=duration if kind=='move' else .15
            else:
                delay=max(0,timeline-.15);event['offset']=(texts%3)*16;texts+=1
            event.update(start=now+delay,duration=duration);self.active.append(event)
        if g._last_battle is not None:
            self.snapshot=g._last_battle;g._last_battle=None
            self.until=now+max(1.15,timeline+1.0)

    def position(self,entity,fallback):
        now=time.monotonic()
        moves=[e for e in self.active if e['kind']=='move' and e.get('entity')==entity]
        for e in moves:
            if now<e['start']:return e['path'][0]
            if now<e['start']+e['duration']:
                path=e['path'];progress=(now-e['start'])/e['duration']*(len(path)-1)
                n=min(len(path)-2,int(progress));ratio=progress-n
                return [path[n][axis]+(path[n+1][axis]-path[n][axis])*ratio for axis in (0,1)]
        return fallback

    def point(self,pos,entity=None):
        app=self.app;b=self.snapshot if self.snapshot is not None and time.monotonic()<self.until else app.game.battle
        if b:
            if entity=='player':pos=self.position('player',b['pos'])
            iso=getattr(app,'iso',None)
            if iso:return iso['ox']+(pos[0]-pos[1])*iso['u'],iso['oy']+(pos[0]+pos[1])*iso['u']/2-iso['u']*.85
        if entity=='player':pos=[app.game.x,app.game.y]
        return app.ox+(pos[0]-app.vx+.5)*app.tile,app.oy+(pos[1]-app.vy+.25)*app.tile

    def render(self):
        c=self.app.canvas;c.delete('fx')
        now=time.monotonic();battle=bool(self.app.game.battle or self.blocked)
        for e in self.active:
            if e['kind']=='move':continue
            dt=now-e['start']
            if not 0<=dt<e['duration']:continue
            # Player notices follow the player when entering/leaving combat in the same action.
            if (e['scene']=='battle')!=battle and e.get('entity')!='player':continue
            px,py=self.point(e['pos'],e.get('entity'))
            if e['kind'] in ('attack','slash'):
                sx,sy=self.point(e['source']);t=dt/e['duration']
                if e['kind']=='slash':
                    c.create_line(px-14+t*20,py-12,px+14-t*10,py+10,fill=e['color'],width=4,tags='fx')
                else:
                    tx,ty=sx+(px-sx)*min(1,t*1.8),sy+(py-sy)*min(1,t*1.8)
                    c.create_line(sx,sy,tx,ty,fill=e['color'],width=2,tags='fx')
                    c.create_oval(tx-3,ty-3,tx+3,ty+3,fill=e['color'],outline='',tags='fx')
            else:
                y=py-18-dt*28-e.get('offset',0)
                c.create_text(px+1,y+1,text=e['text'],fill='#15251c',font=('Segoe UI',11,'bold'),tags='fx')
                c.create_text(px,y,text=e['text'],fill=e['color'],font=('Segoe UI',11,'bold'),tags='fx')

    def tick(self):
        now=time.monotonic()
        had_motion=any(e['kind']=='move' for e in self.active)
        self.active=[e for e in self.active if now<e['start']+e['duration']]
        if self.snapshot is not None and now>=self.until:
            self.snapshot=None;self.app.refresh()
        if had_motion:self.app.draw()
        else:self.render()
        self.app.root.after(33,self.tick)


def paint_snapshot(app):
    import advanced_ui
    proxy=copy.copy(app.game);proxy.battle=app.fx.snapshot
    actual=app.game
    try:
        app.game=proxy;advanced_ui.draw_battle(app)
    finally:app.game=actual


def service_picture(c,key,x,y,npc=None):
    sprite=('npc:'+npc if npc else 'npc:'+key) if key in ('smith','food','fence','tech','mayor','traveler','hunter') else {'stash':'stash','rest':'rest','search':'loot','perks':'perk:tactician','atlas':'site','board':'journal'}.get(key)
    if sprites.draw(c,sprite,x,y,52):return
    samples={'hunter':dict(name=tr('adventure_ui.0001'),kind='sealed',rarity=0),'smith':dict(name=tr('adventure_ui.0002'),kind='weapon',rarity=1),
             'food':p.supply('food'),'fence':dict(name=tr('adventure_ui.0003'),kind='sealed',rarity=0),
             'tech':p.parts(1),'mayor':dict(name=tr('adventure_ui.0004'),kind='helmet',rarity=3),
             'stash':dict(name=tr('adventure_ui.0005'),kind='sealed',rarity=2),
             'rest':p.supply('med'),'traveler':dict(name=tr('adventure_ui.0006'),kind='armor',rarity=3),
             'search':dict(name=tr('adventure_ui.0007'),kind='module',rarity=0,stats={'range':1}),
             'perks':dict(name=tr('adventure_ui.0008'),kind='module',rarity=3,stats={'crit':5}),
             'atlas':dict(name=tr('adventure_ui.0009'),kind='quest',rarity=2)}
    icon(c,samples.get(key,dict(kind='quest',name=tr('quests.board'),rarity=0)),x,y,52)


class Services(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL)
        self.app=app;self.entries=[];self.rects=[]
        self.canvas=tk.Canvas(self,bg=PANEL,height=300,highlightthickness=0,cursor='hand2')
        self.canvas.pack(fill='x')
        self.canvas.bind('<Configure>',lambda e:self.paint())
        self.canvas.bind('<Button-1>',self.click)

    def refresh(self):
        app=self.app;g=app.game;items=[]
        if not g.battle:
            for m,key in enumerate(('smith','food','fence')):
                if g.available_merchant(m):items.append((key,g.merchant_title(m),lambda m=m:app.shop(m)))
            if g.city in g.metro_unlocked:items.append(('atlas',tr('adventure_ui.0010'),app.metro))
            if getattr(g,'cartographer',False):items.append(('atlas',tr('adventure_ui.0011'),app.cartographer))
            if g.available_merchant(4):items.append(('hunter',tr('adventure_ui.0012'),lambda:app.shop(4)))
            if g.available_merchant(3):items.append(('traveler',tr('adventure_ui.0013'),lambda:app.shop(3)))
            if g.city in g.technicians:items.append(('tech',tr('adventure_ui.0014'),app.technician))
            if g.city in g.mayors:items.append(('mayor',g.current_site['npc'] if g.current_site else tr('adventure_ui.0015'),app.mayor))
            if g.regular_city and g.city not in g.mayors:items.append(('board',tr('quests.board'),app.mayor))
            if any(q['kind']=='repair_delivery' and q['status']=='active' and g.quest_return_city(q)==g.city for q in g.quests):items.append(('board',tr('quests.recipient'),lambda:app.tabs.select(app.quest_tab)))
            if g.regular_city:
                items.extend([('stash',tr('adventure_ui.0016'),app.storage),('rest',tr('adventure_ui.0017'),lambda:app.act(g.rest))])
            elif g.city is None:
                items.append(('search',tr('adventure_ui.0018'),lambda:app.act(g.search)))
            if hasattr(g,'destination_quest') and g.destination_quest():
                q=g.destination_quest();items.append(('search',tr('adventure_ui.0019') if q['kind']=='delivery' else tr('adventure_ui.0020'),lambda:app.act(g.search)))
            if g.road_event:items.append(('traveler',tr('adventure_ui.0021'),app.road_dialog))
        items.extend([('perks',tr('adventure_ui.0022', v0=g.pending_perks),app.perks),('atlas',tr('debug.atlas_button') if TEST_MODE else tr('adventure_ui.0023'),app.atlas)])
        self.entries=items;self.paint()

    def paint(self):
        c=self.canvas;c.delete('all');self.rects=[]
        width=max(320,c.winfo_width());cell=width/3;h=102
        c.config(height=math.ceil(len(self.entries)/3)*h)
        for n,(key,label,fn) in enumerate(self.entries):
            x,y=n%3*cell,n//3*h
            rect=(x+4,y+4,x+cell-4,y+h-4);self.rects.append((rect,fn))
            c.create_rectangle(*rect,fill='#2b3b30',outline='#63745a',width=1)
            service_picture(c,key,x+cell/2-26,y+7,self.app.game.current_site['npc'] if self.app.game.current_site and key in ('smith','mayor') else None)
            c.create_text(x+cell/2,y+74,text=label,fill=GOLD if key in ('mayor','stash') else TEXT,font=('Segoe UI',9),width=cell-12)

    def click(self,e):
        for (x,y,d,f),fn in self.rects:
            if x<=e.x<=d and y<=e.y<=f:fn();break


class Storage(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL);self.app=app;self.selection=None;self.direction='withdraw'
        self.label=tk.Label(self,bg=PANEL,fg=GOLD,font=('Segoe UI',13,'bold'));self.label.pack(pady=12)
        tk.Label(self,text=tr('adventure_ui.0024'),bg=PANEL,fg=MUTED).pack()
        body=tk.Frame(self,bg=PANEL);body.pack(fill='both',expand=True,padx=8,pady=10)
        left,right=tk.Frame(body,bg=PANEL),tk.Frame(body,bg=PANEL)
        left.pack(side='left',fill='both',expand=True);right.pack(side='left',fill='both',expand=True)
        tk.Label(left,text=tr('adventure_ui.0025'),bg=PANEL,fg=TEXT).pack()
        tk.Label(right,text=tr('adventure_ui.0026'),bg=PANEL,fg=TEXT).pack()
        self.stored=ItemGrid(left,lambda i:self.select(i,'withdraw'),height=310);self.stored.pack(fill='both',expand=True,padx=4)
        self.bag=ItemGrid(right,lambda i:self.select(i,'deposit'),height=310);self.bag.pack(fill='both',expand=True,padx=4)
        from refinement_ui import Detail
        self.detail=Detail(self,height=7);self.detail.pack(fill='x',padx=12)
        bar=tk.Frame(self,bg=PANEL);bar.pack(fill='x',padx=12,pady=10)
        self.qty=tk.StringVar(value='1')
        ttk.Label(bar,text=tr('adventure_ui.0027')).pack(side='left')
        ttk.Spinbox(bar,from_=1,to=999999,width=8,textvariable=self.qty).pack(side='left',padx=6)
        ttk.Button(bar,text=tr('adventure_ui.0028'),command=self.all).pack(side='left',padx=5)
        ttk.Button(bar,text=tr('adventure_ui.0029'),command=self.transfer).pack(side='right')
        self.drag=Drag(self,self.drop)
        for grid,direction in ((self.stored,'withdraw'),(self.bag,'deposit')):
            grid.canvas.bind('<Button-1>',lambda e,g=grid,d=direction:self.press(e,g,d))
            grid.canvas.bind('<B1-Motion>',self.drag.move);grid.canvas.bind('<ButtonRelease-1>',self.drag.end)
        self.refresh()

    def item(self):
        source=self.app.game.stash if self.direction=='withdraw' else self.app.game.bag
        return next((i for i in source if i['id']==self.selection),None)

    def select(self,item_id,direction):
        self.selection,self.direction=item_id,direction
        item=self.item()
        if item:self.detail.config(text=self.app.description(item).replace('\n',' · '))

    def all(self):
        item=self.item()
        if item:self.qty.set(str(item.get('qty',1)))

    def refresh(self):
        g=self.app.game;self.stored.set_items(g.stash);self.bag.set_items(g.bag)
        self.label.config(text=tr('adventure_ui.0030', v0=g.weight, v1=g.capacity))
        self.app.refresh()

    def transfer(self):
        item=self.item()
        if not item:return
        try:qty=max(1,min(int(self.qty.get()),item.get('qty',1)))
        except ValueError:qty=1
        ok=self.app.game.stash_transfer(item['id'],self.direction,qty)
        self.refresh()
        self.detail.config(text=self.app.game.messages[-1] if ok else tr('adventure_ui.0031'))

    def press(self,e,grid,direction):
        grid.select_event(e);item=self.item()
        if item:self.drag.begin(e,dict(item=item,direction=direction))

    def drop(self,payload,xr,yr):
        direction=payload['direction'];target=self.bag.canvas if direction=='withdraw' else self.stored.canvas
        if inside(target,xr,yr):self.select(payload['item']['id'],direction);self.transfer()


def road_window(app):
    event=app.game.road_event
    if not event:return
    win=app.popup(event['title'],'660x410')
    picture=tk.Canvas(win,height=90,bg=PANEL,highlightthickness=0);picture.pack(fill='x')
    service_picture(picture,'traveler',295,18)
    tk.Label(win,text=event['title'],bg=PANEL,fg=GOLD,font=('Segoe UI',15,'bold')).pack(pady=8)
    tk.Label(win,text=event['body'],bg=PANEL,fg=TEXT,wraplength=600).pack(padx=20,pady=8)
    result=tk.Label(win,bg=PANEL,fg='#eaa58c');result.pack()
    def choose(key):
        if app.game.resolve_event(key):
            app.dialog=None;win.destroy();app.refresh()
        else:result.config(text=app.game.messages[-1])
    for key,label in event['choices']:
        ttk.Button(win,text=label,command=lambda key=key:choose(key)).pack(fill='x',padx=22,pady=4)


def paint_world_extras(app):
    c,g=app.canvas,app.game
    trails=set(map(tuple,g.trails))
    for y in range(app.vy,min(32,app.vy+17)):
        for x in range(app.vx,min(48,app.vx+23)):
            if not app.map_revealed(x,y):continue
            px,py=app.ox+(x-app.vx+.5)*app.tile,app.oy+(y-app.vy+.5)*app.tile;t=app.tile
            if (x,y) in trails:
                for q in r.neighbors(x,y,48,32):
                    if q in trails:c.create_line(px,py,px+(q[0]-x)*t*.5,py+(q[1]-y)*t*.5,fill='#c5b590',dash=(3,2),width=2)
            if f'{x},{y}' in g.radiation:
                c.create_rectangle(px-t*.42,py-t*.42,px+t*.42,py+t*.42,outline='#8dae56')
                c.create_text(px,py,text='☢',fill='#b9d95b',font=('Segoe UI',max(9,int(t*.5))))
