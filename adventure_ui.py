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
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        self.app=app;self.game=app.game;self.active=[];self.snapshot=None;self.until=0
        app.root.after(33,self.tick)

    @property
    def blocked(self):
        """Перевіряє, чи дозволяє поточний стан продовжувати рух."""
        now=time.monotonic()
        return (self.snapshot is not None and now<self.until) or any((e['kind']=='move' or e['kind']=='reveal' and e.get('blocking',True)) and 'paused_at' not in e and now<e['start']+e['duration'] for e in self.active)

    def pause_world_notices(self,now):
        """Keep map notices readable after a pending event or modal closes."""
        hidden=bool(getattr(self.app.game,'road_event',None) or
                    getattr(self.app,'dialog',None) or getattr(self.app,'_notice_open',False))
        for event in self.active:
            if event['kind'] not in ('text','reveal') or event['scene']!='world':continue
            if hidden:
                if now<event['start']+event['duration']:
                    event.setdefault('paused_at',now)
            elif 'paused_at' in event:
                event['start']+=now-event.pop('paused_at')

    def ingest(self):
        """Приймає нові ігрові події для показу анімацій."""
        g=self.app.game
        if g is not self.game:
            self.active=[];self.snapshot=None;self.game=g
        now=time.monotonic();timeline=0;texts=0;volleys={}
        self.pause_world_notices(now)
        world_end=max([now]+[e['start']+e['duration']+.35+(now-e['paused_at'] if 'paused_at' in e else 0)
                            for e in self.active if e['kind']=='text' and e['scene']=='world'])
        for event in g.pop_events():
            event=dict(event);kind=event['kind']
            duration=min(.55,max(.12,.07*(len(event.get('path',[]))-1))) if kind=='move' else .65 if event.get('fire_mode')=='aimed' else .4 if kind in ('attack','slash') else 2.8 if kind=='reveal' else 1.0
            if kind in ('move','attack','slash'):
                if kind=='attack' and event.get('volley'):
                    ident=event['volley']
                    if ident not in volleys:
                        volleys[ident]=timeline
                        timeline+=duration if event.get('fire_mode')=='pellet' else duration+.09*(event.get('volley_count',1)-1)
                    delay=volleys[ident]+(0 if event.get('fire_mode')=='pellet' else .09*event.get('projectile',0))
                else:
                    delay=timeline;timeline+=duration if kind=='move' else .09 if event.get('fire_mode')=='burst' else .15
            else:
                delay=max(0,timeline-.15);event['offset']=(texts%3)*16;texts+=1
            if kind=='text' and event['scene']=='world':
                duration=max(1.0,min(2.0,len(event['text'])/30))
                delay=max(delay,world_end-now);event['offset']=0
                world_end=now+delay+duration+.35
            event.update(start=now+delay,duration=duration);self.active.append(event)
        if g._last_battle is not None:
            self.snapshot=g._last_battle;g._last_battle=None
            self.until=now+max(1.15,timeline+1.0)
        self.pause_world_notices(now)

    def reveal_focus(self):
        """Focus briefly on a newly revealed patch even when it is outside the player's viewport."""
        now=time.monotonic()
        event=next((e for e in reversed(self.active) if e['kind']=='reveal' and 'paused_at' not in e and e.get('blocking',True) and e['start']<=now<e['start']+e['duration']),None)
        if event and event.get('cells'):
            return tuple(round(sum(c[n] for c in event['cells'])/len(event['cells'])) for n in (0,1))
        return self.app.game.x,self.app.game.y

    def position(self,entity,fallback):
        """Повертає проміжну позицію для плавної анімації."""
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
        """Перетворює логічну позицію на екранні координати."""
        app=self.app;b=self.snapshot if self.snapshot is not None and time.monotonic()<self.until else app.game.battle
        if b:
            if entity=='player':pos=self.position('player',b['pos'])
            iso=getattr(app,'iso',None)
            if iso:
                import hexgrid
                x,y=hexgrid.center(pos,iso['u'],iso['ox'],iso['oy'])
                return x,y-iso['u']*.85
        if entity=='player':pos=app.route.position() if hasattr(app,'route') else [app.game.x,app.game.y]
        if hasattr(app,'world_view'):
            x,y=app.world_view.point(pos);return x,y-app.tile*.25
        return app.ox+(pos[0]-app.vx+.5)*app.tile,app.oy+(pos[1]-app.vy+.25)*app.tile

    def render(self):
        """Відображає поточний кадр візуальних ефектів."""
        c=self.app.canvas;c.delete('fx')
        now=time.monotonic();battle=bool(self.app.game.battle or (self.snapshot is not None and now<self.until))
        self.pause_world_notices(now)
        for e in self.active:
            if e['kind']=='move' or 'paused_at' in e:continue
            dt=now-e['start']
            if not 0<=dt<e['duration']:continue
            # Player notices follow the player when entering/leaving combat in the same action.
            if (e['scene']=='battle')!=battle and e.get('entity')!='player':continue
            if e['kind']=='reveal':
                a=self.app;t=a.tile
                for x,y in e['cells']:
                    if hasattr(a,"world_view") and a.world_view.visible((x,y)):
                        if hasattr(a,'world_view'):
                            c.create_polygon(*a.world_view.polygon((x,y),.94),outline=e['color'],width=2 if int(dt*7)%2 else 4,fill=e['color'],stipple='gray75',tags='fx')
                continue
            px,py=self.point(e['pos'],e.get('entity'))
            if e['kind'] in ('attack','slash'):
                sx,sy=self.point(e['source']);t=dt/e['duration']
                if e['kind']=='slash':
                    c.create_line(px-14+t*20,py-12,px+14-t*10,py+10,fill=e['color'],width=4,tags='fx')
                else:
                    mode=e.get('fire_mode')
                    if mode=='aimed':
                        c.create_oval(px-12,py-12,px+12,py+12,outline=e['color'],width=2,tags='fx')
                        c.create_line(px-18,py,px+18,py,fill=e['color'],tags='fx')
                        if t<.4:continue
                        t=(t-.4)/.6
                    if mode=='pellet':
                        offset=(e.get('projectile',0)-2.5)*3;px+=offset;py+=offset*.4
                    tx,ty=sx+(px-sx)*min(1,t*1.8),sy+(py-sy)*min(1,t*1.8)
                    c.create_line(sx,sy,tx,ty,fill=e['color'],width=2,tags='fx')
                    c.create_oval(tx-3,ty-3,tx+3,ty+3,fill=e['color'],outline='',tags='fx')
            else:
                world=e['scene']=='world'
                y=py-18-dt*(4 if world else 28)-e.get('offset',0)
                options=dict(text=e['text'],font=('Segoe UI',11,'bold'),tags='fx')
                if world:options['width']=max(40,c.winfo_width()-24)
                shadow=c.create_text(px+1,y+1,fill='#15251c',**options)
                label=c.create_text(px,y,fill=e['color'],**options)
                if world:
                    box=c.bbox(label)
                    if box:
                        x1,y1,x2,y2=box;w=c.winfo_width();h=c.winfo_height()
                        dx=max(8-x1,min(0,w-9-x2));dy=max(8-y1,min(0,h-9-y2))
                        c.move(label,dx,dy);c.move(shadow,dx,dy)

    def tick(self):
        """Виконує черговий кадр оновлення та планує наступний."""
        now=time.monotonic()
        self.pause_world_notices(now)
        had_motion=any(e['kind'] in ('move','reveal') for e in self.active)
        self.active=[e for e in self.active if 'paused_at' in e or now<e['start']+e['duration']]
        if self.snapshot is not None and now>=self.until:
            self.snapshot=None;self.app.refresh()
        focus=self.reveal_focus()
        previous=getattr(self,'_last_reveal_focus',None);self._last_reveal_focus=focus
        if had_motion and (self.app.game.battle or self.snapshot is not None or focus!=previous):self.app.draw()
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
    sprite={'settlers':'npc_roamer_smith','torn_map':'quest:torn_map','board':'service_board','metro':'service_metro','cartographer':'npc_cartographer','guide':'npc_guide','action_delivery':'action_delivery','action_radio':'action_radio'}.get(key,sprite)
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
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        super().__init__(parent,bg=PANEL)
        self.app=app;self.entries=[];self.rects=[]
        self.canvas=tk.Canvas(self,bg=PANEL,height=300,highlightthickness=0,cursor='hand2')
        self.canvas.pack(fill='x')
        self.canvas.bind('<Configure>',lambda e:self.paint())
        self.canvas.bind('<Button-1>',self.click)

    def refresh(self):
        """Оновлює віджети відповідно до поточного стану гри."""
        app=self.app;g=app.game;items=[]
        if not g.battle:
            import restoration_ui
            for mq in g.metro_local():
                items.append(('metro',tr('metro035.service'),lambda ident=mq['id']:__import__('metro035_ui').show(app,ident)))
            if g.scribe:items.append(('cartographer',tr('update032.scribe'),lambda:__import__('interface032').scribe(app)))
            if g.local_settlers():items.append(('settlers',tr('restoration.settlers'),lambda:restoration_ui.settlers(app)))
            if any(q['kind']=='torn_map' and q['status']=='active' and not q['map_solved'] for q in g.quests):items.append(('torn_map',tr('restoration.assemble'),lambda:restoration_ui.maps(app)))
            for m,key in enumerate(('smith','food','fence')):
                if g.available_merchant(m):items.append((key,g.merchant_title(m),lambda m=m:app.shop(m)))
            if g.city in g.metro_unlocked:items.append(('metro',tr('adventure_ui.0010'),app.metro))
            if getattr(g,'guide',False):items.append(('guide',tr('journey.guide'),app.guide))
            if getattr(g,'cartographer',False):items.append(('cartographer',tr('adventure_ui.0011'),app.cartographer))
            if g.available_merchant(4):items.append(('hunter',tr('adventure_ui.0012'),lambda:app.shop(4)))
            if g.available_merchant(3):items.append(('traveler',tr('adventure_ui.0013'),lambda:app.shop(3)))
            if g.city in g.technicians:items.append(('tech',tr('adventure_ui.0014'),app.technician))
            if g.city in g.mayors:items.append(('mayor',g.current_site['npc'] if g.current_site else tr('adventure_ui.0015'),app.mayor))
            if g.regular_city and g.city not in g.mayors:items.append(('board',tr('quests.board'),app.mayor))
            if any(q['kind'] in ('repair_delivery','delivery') and q['status']=='active' and g.quest_return_city(q)==g.city for q in g.quests):items.append(('board',tr('quests.recipient'),lambda:app.tabs.select(app.quest_tab)))
            if g.regular_city:
                items.extend([('stash',tr('adventure_ui.0016'),app.storage),('rest',tr('adventure_ui.0017'),lambda:app.act(g.rest))])
            elif g.city is None:
                items.append(('search',tr('adventure_ui.0018'),lambda:app.act(g.search)))
            if not g.regular_city and g.can_access_stash:items.append(('stash',tr('adventure_ui.0016'),app.storage))
            if hasattr(g,'destination_quest') and g.destination_quest():
                q=g.destination_quest();items.append(('action_delivery' if q['kind']=='delivery' else 'action_radio',tr('adventure_ui.0019') if q['kind']=='delivery' else tr('adventure_ui.0020'),lambda:app.act(g.search)))
            if getattr(g,'local_expedition',lambda:None)() and g.city is not None:items.append(('search',tr('adventure_ui.0018'),lambda:app.act(g.search)))
            if g.road_event:items.append(('traveler',tr('adventure_ui.0021'),app.road_dialog))
        items.extend([('atlas',tr('debug.atlas_button') if TEST_MODE else tr('adventure_ui.0023'),app.atlas)])
        self.entries=items;self.paint()

    def paint(self):
        """Малює актуальне представлення даних на Canvas."""
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
        """Обробляє натискання на елемент панелі за координатами курсора."""
        for (x,y,d,f),fn in self.rects:
            if x<=e.x<=d and y<=e.y<=f:fn();break


class Storage(tk.Frame):
    def __init__(self,parent,app):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
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
        """Знаходить предмет, обраний у поточній панелі."""
        source=self.app.game.stash if self.direction=='withdraw' else self.app.game.bag
        return next((i for i in source if i['id']==self.selection),None)

    def select(self,item_id,direction):
        """Обробляє вибір елемента та оновлює його опис."""
        self.selection,self.direction=item_id,direction
        item=self.item()
        if item:self.detail.config(text=self.app.description(item))

    def all(self):
        """Застосовує операцію до всіх доступних предметів."""
        item=self.item()
        if item:self.qty.set(str(item.get('qty',1)))

    def refresh(self):
        """Оновлює віджети відповідно до поточного стану гри."""
        g=self.app.game;self.stored.set_items(g.stash);self.bag.set_items(g.bag)
        self.label.config(text=tr('adventure_ui.0030', v0=g.weight, v1=g.capacity))
        self.app.refresh()

    def transfer(self):
        """Переносить вибраний предмет між контейнерами."""
        item=self.item()
        if not item:return
        try:qty=max(1,min(int(self.qty.get()),item.get('qty',1)))
        except ValueError:qty=1
        ok=self.app.game.stash_transfer(item['id'],self.direction,qty)
        self.refresh()
        self.detail.config(text=self.app.game.messages[-1] if ok else tr('adventure_ui.0031'))

    def press(self,e,grid,direction):
        """Запам’ятовує початок натискання чи перетягування."""
        grid.select_event(e);item=self.item()
        if item:self.drag.begin(e,dict(item=item,direction=direction))

    def drop(self,payload,xr,yr):
        """Обробляє відпускання предмета над ціллю перетягування."""
        if payload['direction']=='deposit' and payload['item'].get('kind')=='module' and inside(self.bag.canvas,xr,yr):
            ident=self.bag.hit(xr-self.bag.canvas.winfo_rootx(),yr-self.bag.canvas.winfo_rooty())
            self.app.act(lambda:self.app.game.quick_module(ident,payload['item']['id']));self.refresh();return
        direction=payload['direction'];target=self.bag.canvas if direction=='withdraw' else self.stored.canvas
        if inside(target,xr,yr):self.select(payload['item']['id'],direction);self.transfer()


def road_window(app):
    event=app.game.road_event
    if not event:return
    win=app.popup(event['title'],'760x620')
    scroll=tk.Canvas(win,bg=PANEL,highlightthickness=0)
    bar=ttk.Scrollbar(win,orient='vertical',command=scroll.yview);bar.pack(side='right',fill='y')
    scroll.pack(fill='both',expand=True);scroll.configure(yscrollcommand=bar.set)
    body=tk.Frame(scroll,bg=PANEL);body_id=scroll.create_window(0,0,window=body,anchor='nw')
    body.bind('<Configure>',lambda e:scroll.configure(scrollregion=scroll.bbox('all')))
    scroll.bind('<Configure>',lambda e:scroll.itemconfigure(body_id,width=e.width))
    win.bind('<MouseWheel>',lambda e:scroll.yview_scroll(-1 if e.delta>0 else 1,'units'))
    introduction=tk.Frame(body,bg=PANEL);introduction.pack(fill='x',padx=22,pady=16)
    introduction.columnconfigure(1,weight=1)
    art_size=max(sprites.SIZES)
    picture=tk.Canvas(introduction,width=art_size,height=art_size,bg=PANEL,highlightthickness=0)
    picture.grid(row=0,column=0,sticky='nw')
    from event_art import EVENT_ART
    sprites.draw(picture,event.get('art',EVENT_ART.get(event['kind'],'event_theme:camp')),0,0,art_size)
    narrative=tk.Frame(introduction,bg=PANEL);narrative.grid(row=0,column=1,sticky='new',padx=(20,0))
    title=tk.Label(narrative,text=event['title'],bg=PANEL,fg=GOLD,font=('Segoe UI',15,'bold'),wraplength=460,anchor='w',justify='left')
    title.pack(fill='x',pady=(0,12))
    description=tk.Label(narrative,text=event['body'],bg=PANEL,fg=TEXT,wraplength=460,anchor='w',justify='left')
    description.pack(fill='x')
    def wrap_narrative(event):
        width=max(1,event.width)
        title.configure(wraplength=width);description.configure(wraplength=width)
    narrative.bind('<Configure>',wrap_narrative)
    result=tk.Label(body,bg=PANEL,fg='#eaa58c',wraplength=690);result.pack()
    def choose(key):
        if app.game.resolve_event(key):
            app.dialog=None;win.destroy();app.refresh()
            ident=getattr(app.game,'_lock_request',None)
            if ident:
                app.game._lock_request=None
                import lock_ui
                lock_ui.show(app,ident)
        else:result.config(text=app.game.messages[-1])
    from event_runtime import display_choices
    for key,label in display_choices(event):
        tk.Button(body,text=label,command=lambda key=key:choose(key),wraplength=660,
                  justify='left',anchor='w',bg=PANEL,fg=TEXT,activebackground=PANEL,
                  activeforeground=GOLD,padx=12,pady=8).pack(fill='x',padx=22,pady=4)
