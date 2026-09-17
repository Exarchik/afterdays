from i18n import t as tr
import sprites
"""Isometric arena, grid-based trading, technicians and perk selection."""
import math
import tkinter as tk
from tkinter import ttk, messagebox
from collections import deque
import afterdays as r
import progression as p
from visuals import ItemGrid, Drag, inside, icon, monster, BG, PANEL, TEXT, MUTED, GOLD


def region_color(color,x):
    ratio=min(.30,max(0,x-8)/39*.3)
    rgb=[int(color[i:i+2],16) for i in (1,3,5)]
    tint=(125,70,53)
    return '#'+''.join(f'{round(v*(1-ratio)+t*ratio):02x}' for v,t in zip(rgb,tint))


def draw_battle(app):
    c,g=app.canvas,app.game
    b=g.battle
    c.delete('all')
    width,height=max(c.winfo_width(),200),max(c.winfo_height(),200)
    w,h=b['w'],b['h']
    u=min((width-30)/(w+h+1),(height-45)/((w+h)/2+2))
    ox=(width-(w-h)*u)/2
    oy=max(40,(height-(w+h)*u/2)/2)
    app.iso=dict(u=u,ox=ox,oy=oy,sprites=[])
    def center(pos): return ox+(pos[0]-pos[1])*u,oy+(pos[0]+pos[1])*u/2
    kind=b.get('biome','waste')
    palette={'waste':('#555642','#444835'),'forest':('#304a37','#293e30'),
             'ruin':('#54574f','#434a43'),'road':('#665e49','#494e3a'),
             'city':('#585c4c','#444d41')}
    colors=palette.get(kind,palette['waste'])
    walls=set(map(tuple,b['walls']))
    occupied=walls|{tuple(e['pos']) for e in b['enemies']}
    costs={tuple(b['pos']):0};queue=deque(costs)
    while queue:
        pos=queue.popleft()
        if costs[pos]>=b['ap'] and not (b.get('dungeon') and b.get('cleared')):continue
        for q in r.neighbors(*pos,w,h):
            if q not in occupied and q not in costs:
                costs[q]=costs[pos]+1;queue.append(q)
    cells=sorted(((x,y) for y in range(h) for x in range(w)),key=lambda a:sum(a))
    for x,y in cells:
        px,py=center((x,y))
        color=colors[(x+y)%2]
        if kind=='road' and 4<=y<=6:color='#918060'
        reachable=(x,y) in costs
        c.create_polygon(px,py-u/2,px+u,py,px,py+u/2,px-u,py,fill=color,
                         outline='#849777' if reachable else '#35463a',width=1)
        if x==0 and not b.get('dungeon'):
            c.create_line(px-u,py,px,py+u/2,fill='#79d5b1',width=3)
        if (x*13+y*7)%9==0 and (x,y) not in walls:
            c.create_line(px-u*.3,py,px+u*.14,py+u*.1,fill='#a69e78' if kind!='forest' else '#698663')
    enemies={tuple(e['pos']):e for e in b['enemies']}
    for pos in cells:
        px,py=center(pos)
        for corpse in b.get('corpses',[]):
            if tuple(corpse['pos'])==pos:
                sprites.draw(c,'corpse',px-u*.6,py-u*.5,u*1.2)
                c.create_line(px-u*.32,py-u*.08,px+u*.30,py+u*.18,fill='#b4a080',width=2)
                c.create_line(px-u*.26,py+u*.18,px+u*.26,py-u*.09,fill='#b4a080',width=2)
        if pos in walls:
            if sprites.draw(c,'terrain:forest' if kind=='forest' else 'terrain:ruin' if kind in ('ruin','city') else 'terrain:cliff',px-u,py-u*1.65,2*u):pass
            elif kind=='forest':
                c.create_line(px,py,px,py-u*1.5,fill='#8a7f5d',width=max(2,int(u*.18)))
                c.create_line(px-u*.5,py-u*1.3,px,py-u*.8,px+u*.42,py-u*1.65,fill='#91a17a',width=2)
                c.create_polygon(px,py-u*2,px-u*.6,py-u*.9,px+u*.6,py-u*.9,fill='#3a5940',outline='#719264')
            else:
                z=u*(1.15 if kind in ('ruin','city') else .60)
                c.create_polygon(px-u*.8,py,px,py+u*.4,px,py+u*.4-z,px-u*.8,py-z,fill='#484d43',outline='#2f3d33')
                c.create_polygon(px,py+u*.4,px+u*.8,py,px+u*.8,py-z,px,py+u*.4-z,fill='#65685a',outline='#2f3d33')
                c.create_polygon(px,py-u*.4-z,px+u*.8,py-z,px,py+u*.4-z,px-u*.8,py-z,fill='#989681',outline='#c1b89b')
                if kind=='ruin':
                    c.create_line(px+u*.2,py-z*.45,px+u*.6,py-z*.62,fill='#263b32',width=3)
        if b.get('dungeon') and list(pos) in (b['exit'],b['chest']):
            is_exit=list(pos)==b['exit']
            color='#80e3b4' if is_exit else '#94876b' if b['chest_open'] else '#f4c86b'
            c.create_oval(px-u*.7,py-u*.35,px+u*.7,py+u*.35,outline=color,width=3)
            c.create_text(px,py-u*.65,text=tr('advanced_ui.0001') if is_exit else tr('advanced_ui.0002'),fill=color,font=('Segoe UI',8,'bold'))
        if list(pos)==b['pos']:
            if hasattr(getattr(app,'fx',None),'position'):px,py=center(app.fx.position('player',b['pos']))
            c.create_oval(px-u*.45,py-u*.1,px+u*.45,py+u*.3,fill='#253d33',outline='#c8efce',width=2)
            c.create_line(px-u*.18,py-u*.4,px-u*.25,py+u*.1,fill='#bdccb5',width=4)
            c.create_line(px+u*.18,py-u*.4,px+u*.25,py+u*.1,fill='#bdccb5',width=4)
            c.create_polygon(px-u*.3,py-u*1.05,px+u*.3,py-u*1.05,px+u*.25,py-u*.35,px-u*.25,py-u*.35,fill='#aebea4',outline='#edf0d6')
            c.create_oval(px-u*.23,py-u*1.52,px+u*.23,py-u*1.02,fill='#d6d9b9',outline='#edf0d6')
            c.create_line(px+u*.1,py-u*.75,px+u*.65,py-u*.85,fill='#b9d5c8',width=3)
        if pos in enemies:
            e=enemies[pos];valid,_,_=g.shot_info(e)
            px,py=center(app.fx.position(e['id'],e['pos'])) if hasattr(getattr(app,'fx',None),'position') else center(pos)
            if valid:c.create_oval(px-u*.55,py-u*.16,px+u*.55,py+u*.25,outline=GOLD,width=2)
            size=u*1.45
            monster(c,e,px-size/2,py-size+.15*u,size)
            app.iso['sprites'].append((px-size/2,py-size,px+size/2,py+.18*u,pos))
            top=py-size-u*.18
            c.create_rectangle(px-u*.5,top,px+u*.5,top+3,fill='#23392d',outline='')
            c.create_rectangle(px-u*.5,top,px-u*.5+u*e['hp']/e['max_hp'],top+3,fill='#d88667',outline='')
            c.create_text(px,top-7,text=f'L{e.get("level",1)}'+(' · z' if b.get('dungeon') and not e.get('awake') else ''),fill='#e6c18d',font=('Segoe UI',7))
    app.map_title.config(text=tr('advanced_ui.0003', v0=r.TERRAINS[kind][1].upper(), v1=b.get('region_level', 1), v2=b['ap'], v3=b.get('max_ap', 6)))
    weapon=g.weapon
    ammo=p.AMMO[weapon.get('ammo_type','pistol')][0] if weapon else '—'
    count=g.count('ammo',weapon.get('ammo_type','pistol')) if weapon else 0
    app.hint.config(text=tr('advanced_ui.0004', v0=ammo, v1=count))

    if b.get('dungeon'):
        app.map_title.config(text=tr('advanced_ui.0005', v0=b['dungeon_kind'], v1=len(b['enemies']), v2=b['ap'], v3=g.max_ap))
        app.hint.config(text=(tr('advanced_ui.0006') if b.get('cleared') else '')+tr('advanced_ui.0007'))


def iso_cell(app,event):
    info=app.iso
    for a,b,d,e,pos in reversed(info['sprites']):
        if a<=event.x<=d and b<=event.y<=e:return pos
    dx=(event.x-info['ox'])/info['u']
    dy=2*(event.y-info['oy'])/info['u']
    return math.floor((dx+dy)/2+.5),math.floor((dy-dx)/2+.5)


class TradingPanel(tk.Frame):
    def __init__(self,parent,app,merchant):
        super().__init__(parent,bg=PANEL)
        self.app,self.merchant=app,merchant
        self.selection=None;self.source=None
        self.title=tk.Label(self,bg=PANEL,fg=GOLD,font=('Segoe UI',12,'bold'))
        self.title.pack(pady=10)
        rules=tr('advanced_ui.0008')
        if merchant==4:rules=tr('advanced_ui.0009')
        if merchant==2:rules+=tr('advanced_ui.0010')
        if merchant==3:rules+=tr('advanced_ui.0011')
        tk.Label(self,text=rules,bg=PANEL,fg=MUTED,wraplength=880).pack(padx=12,pady=6)
        row=tk.Frame(self,bg=PANEL);row.pack(fill='both',expand=True,padx=8)
        a,b=tk.Frame(row,bg=PANEL),tk.Frame(row,bg=PANEL)
        a.pack(side='left',fill='both',expand=True);b.pack(side='left',fill='both',expand=True)
        tk.Label(a,text=tr('advanced_ui.0012'),bg=PANEL,fg=GOLD).pack(pady=4)
        tk.Label(b,text=tr('advanced_ui.0013'),bg=PANEL,fg=GOLD).pack(pady=4)
        self.stock_grid=ItemGrid(a,lambda i:self.select(i,'stock'),height=310,columns=5)
        self.stock_grid.pack(fill='both',expand=True,padx=4)
        self.bag_grid=ItemGrid(b,lambda i:self.select(i,'bag'),height=310,columns=5)
        self.bag_grid.pack(fill='both',expand=True,padx=4)
        controls=tk.Frame(self,bg=PANEL);controls.pack(fill='x',padx=15,pady=8)
        tk.Label(controls,text=tr('advanced_ui.0014'),bg=PANEL,fg=TEXT).pack(side='left')
        self.qty=tk.StringVar(value='1')
        self.spin=ttk.Spinbox(controls,from_=1,to=999999,width=8,textvariable=self.qty,command=self.describe)
        self.spin.pack(side='left',padx=5)
        self.qty.trace_add('write',lambda *a:self.describe())
        for label,n in [('1',1),('10',10),(tr('advanced_ui.0015'),None)]:
            ttk.Button(controls,text=label,command=lambda n=n:self.set_qty(n)).pack(side='left',padx=2)
        ttk.Button(controls,text=tr('advanced_ui.0016'),command=lambda:self.trade('stock')).pack(side='right',padx=3)
        ttk.Button(controls,text=tr('advanced_ui.0017'),command=lambda:self.trade('bag')).pack(side='right',padx=3)
        bottom=tk.Frame(self,bg=PANEL);bottom.pack(fill='x',padx=12,pady=5)
        self.preview=tk.Canvas(bottom,width=82,height=90,bg=PANEL,highlightthickness=0)
        self.preview.pack(side='left')
        from refinement_ui import Detail
        self.detail=Detail(bottom,height=8)
        self.detail.pack(side='left',fill='both',expand=True)
        self.result=tk.Label(self,bg=PANEL,fg=GOLD,wraplength=880,height=2)
        self.result.pack(fill='x',padx=10,pady=5)
        self.drag=Drag(self,self.drop)
        for grid,source in ((self.stock_grid,'stock'),(self.bag_grid,'bag')):
            grid.canvas.bind('<Button-1>',lambda e,g=grid,s=source:self.press(e,g,s))
            grid.canvas.bind('<B1-Motion>',self.drag.move)
            grid.canvas.bind('<ButtonRelease-1>',self.drag.end)
        self.refresh()

    def item(self):
        items=self.app.game.stock(self.merchant) if self.source=='stock' else self.app.game.bag
        return next((i for i in items if i['id']==self.selection),None)

    def amount(self,item):
        if p.stack_key(item) is None:return 1
        try:return max(1,min(int(self.qty.get()),item.get('qty',1)))
        except ValueError:return 1

    def set_qty(self,n):
        item=self.item()
        if item:self.qty.set(str(item.get('qty',1) if n is None else min(n,item.get('qty',1))))

    def select(self,item_id,source):
        self.selection,self.source=item_id,source
        self.describe()

    def describe(self):
        if not hasattr(self,'preview'):return
        item=self.item()
        self.preview.delete('all')
        if not item:self.detail.config(text=tr('advanced_ui.0018'));return
        qty=self.amount(item)
        price=self.app.game.price(item,self.merchant,self.source=='stock')
        hidden=self.merchant==2 and self.source=='stock'
        shown=dict(item,kind='sealed',name=tr('advanced_ui.0019'),rarity=0) if hidden else item
        icon(self.preview,shown,2,5,76)
        if item['kind']=='weapon' and not hidden:
            from adventure import damage_type
            sprites.draw(self.preview,'damage:'+damage_type(item),52,60,24)
        desc=tr('advanced_ui.0020') if hidden else self.app.description(item)
        allowed=self.source=='stock' or self.app.game.buys_kind(item,self.merchant)
        self.detail.config(text=desc+tr('advanced_ui.0021', v0=price, v1=qty, v2=price * qty)+('' if allowed else tr('advanced_ui.0022')))

    def refresh(self):
        g=self.app.game
        items=g.stock(self.merchant)
        if self.merchant==2:
            items=[dict(id=i['id'],kind='sealed',name=tr('advanced_ui.0023'),rarity=0,weight=0) for i in items]
        self.stock_grid.set_items(items)
        self.bag_grid.set_items(g.bag)
        self.title.config(text=tr('advanced_ui.0024', v0=g.merchant_title(self.merchant), v1=g.money, v2=g.weight, v3=g.capacity))
        if g.city is not None:self.title.config(text=self.title.cget('text')+' · '+tr('reputation.short', value=g.reputation()))
        self.describe()
        self.app.refresh()

    def press(self,event,grid,source):
        grid.select_event(event)
        item=self.item()
        if item:
            shown=dict(item,kind='sealed',name=tr('advanced_ui.0025'),rarity=0) if self.merchant==2 and source=='stock' else item
            self.drag.begin(event,dict(item=shown,source=source))

    def trade(self,source,item_id=None):
        if item_id is not None:self.selection,self.source=item_id,source
        if self.source!=source:return
        item=self.item()
        if not item:return
        if source=='bag' and item.get('modules') and not messagebox.askyesno(tr('advanced_ui.0026'),tr('advanced_ui.0027'),parent=self):return
        qty=self.amount(item)
        g=self.app.game
        ok=g.buy(item['id'],self.merchant,qty) if source=='stock' else g.sell(item['id'],self.merchant,qty)
        self.refresh()
        self.result.config(text=g.messages[-1])
        if ok and source=='stock':
            self.preview.delete('all');icon(self.preview,item,2,5,76)
            self.detail.config(text=self.app.description(item))
        else:self.describe()

    def drop(self,payload,xr,yr):
        source=payload['source']
        target=self.bag_grid.canvas if source=='stock' else self.stock_grid.canvas
        if inside(target,xr,yr):self.trade(source,payload['item']['id'])


class TechnicianPanel(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL)
        self.app=app
        self.label=tk.Label(self,bg=PANEL,fg=GOLD,font=('Segoe UI',13,'bold'));self.label.pack(pady=12)
        self.grid=ItemGrid(self,self.describe,height=290,columns=7);self.grid.pack(fill='both',expand=True,padx=10)
        self.detail=tk.Label(self,bg=PANEL,fg=TEXT,wraplength=700,justify='left',height=5);self.detail.pack(padx=12,pady=8)
        ttk.Button(self,text=tr('advanced_ui.0028'),command=self.repair).pack(fill='x',padx=20,pady=12)
        self.refresh()

    def refresh(self):
        g=self.app.game
        self.label.config(text=tr('advanced_ui.0029', v0=g.money))
        self.grid.set_items([i for i in list(g.equipped.values())+g.bag if i and 'durability' in i])
        self.app.refresh()

    def describe(self,item_id):
        item=self.app.game.find(item_id)
        if item:self.detail.config(text=self.app.description(item)+tr('advanced_ui.0030', v0=self.app.game.repair_cost(item)))

    def repair(self):
        if self.grid.selection:
            self.app.game.repair(self.grid.selection)
            self.refresh()
            self.detail.config(text=self.app.game.messages[-1])


def perk_window(app):
    win=app.popup(tr('advanced_ui.0031'),'760x750')
    tk.Label(win,text=tr('advanced_ui.0032', v0=app.game.pending_perks),bg=PANEL,fg=GOLD,font=('Segoe UI',14,'bold')).pack(pady=15)
    def choose(key):
        if app.game.choose_perk(key):
            app.dialog=None;win.destroy();app.perk_prompted=-1;app.refresh()
    for key,(name,desc) in p.PERKS.items():
        text=tr('advanced_ui.0033', v0=name, v1=app.game.rank(key), v2=desc)
        ttk.Button(win,text=text,command=lambda key=key:choose(key),state='normal' if app.game.pending_perks else 'disabled').pack(fill='x',padx=16,pady=4)
    tk.Label(win,text=tr('advanced_ui.0034'),bg=PANEL,fg=MUTED).pack(pady=10)
