"""Canvas-only map puzzle; no generated minigame artwork."""
import tkinter as tk
from tkinter import ttk, messagebox
import sprites
from i18n import t as tr
from visuals import PANEL,TEXT,GOLD
from inspection_ui import window

def dialog(app,title):
    app.route.pause()
    return window(app,title)


def choice(app,title,entries):
    win=dialog(app,title)
    for label,key,description,action in entries:
        frame=tk.Frame(win,bg=PANEL);frame.pack(fill='x',padx=15,pady=8)
        image=sprites.photo(frame,key,48)
        if image:tk.Label(frame,image=image,bg=PANEL).pack(side='left',padx=8)
        def invoke(action=action,description=description):
            if messagebox.askyesno(title,description,parent=win):
                app.act(action)
                if win.winfo_exists():win.close_dialog()
        ttk.Button(frame,text=label,command=invoke).pack(fill='x')
        tk.Label(frame,text=description,bg=PANEL,fg=TEXT,wraplength=480,justify='left').pack(fill='x')


def settlers(app):
    g=app.game;entries=[]
    for n in g.local_settlers():
        q=next((q for q in g.quests if q.get('settler_id')==n['id'] and q['status']=='active'),n['quest'])
        action=(lambda ident=n['id']:g.recruit(ident)) if n['state']=='offered' else (lambda ident=q['id']:g.turn_in(ident))
        label=tr('restoration.roamer_'+n['role'])+' · '+tr('restoration.accept' if n['state']=='offered' else 'restoration.return')
        if n['state']=='active':
            action=lambda:None;label=tr('restoration.seek_city')
        entries.append((label,'npc_roamer_'+n['role'],g.quest_text(q),action))
    choice(app,tr('restoration.settlers'),entries)


def permission(app):
    g=app.game
    choice(app,tr('restoration.permission'),[(q['title'],'settlement_permit',tr('restoration.permission_info',city=g.city_name(g.city),role=tr('restoration.roamer_'+q['kind'][8:])),lambda ident=q['id']:g.authorize_settlement(ident)) for q in g.settlement_requests()])


def maps(app):
    g=app.game
    qs=[q for q in g.quests if q['kind']=='torn_map' and q['status']=='active' and not q['map_solved']]
    if len(qs)==1:return puzzle(app,qs[0]['id'])
    win=dialog(app,tr('restoration.assemble'))
    for q in qs:
        def open_map(ident=q['id']):win.close_dialog();puzzle(app,ident)
        ttk.Button(win,text=q['title']+' · '+g.city_name(q['city']),command=open_map).pack(fill='x',padx=20,pady=8)


def puzzle(app,ident):
    g=app.game;q=g.map_quest(ident)
    if not q or q['map_solved'] or g.battle:return
    win=dialog(app,tr('restoration.assemble'))
    tk.Label(win,text=tr('restoration.puzzle_help'),bg=PANEL,fg=TEXT,wraplength=550).pack(padx=15,pady=12)
    c=tk.Canvas(win,width=540,height=500,bg='#17231e',highlightthickness=0);c.pack(fill='both',expand=True,padx=15)
    status=tk.Label(win,text='',bg=PANEL,fg=GOLD);status.pack(pady=10)
    held=[None];rects=[]
    # Continuous hand-drawn paths are clipped to each paper piece. Their joins,
    # coast and landmarks form the puzzle; no numeric solution labels.
    paths=[('#477d80',6,[(0,.2),(.22,.28),(.35,.17),(.44,.35),(.38,.56),(.55,.68),(.64,.91),(.85,1)]),
           ('#875c38',4,[(0,.77),(.18,.67),(.31,.75),(.52,.54),(.76,.6),(.83,.38),(1,.26)]),
           ('#7c8654',3,[(.08,0),(.15,.15),(.37,.1),(.6,.2),(.88,.12),(1,.16)])]
    def clip(a,b,x0,y0,x1,y1):
        dx,dy=b[0]-a[0],b[1]-a[1];lo,hi=0.,1.
        for p,v in ((-dx,a[0]-x0),(dx,x1-a[0]),(-dy,a[1]-y0),(dy,y1-a[1])):
            if p==0:
                if v<0:return
            elif p<0:lo=max(lo,v/p)
            else:hi=min(hi,v/p)
        if lo<=hi:return (a[0]+dx*lo,a[1]+dy*lo,a[0]+dx*hi,a[1]+dy*hi)
    def draw():
        c.delete('all');rects.clear();size=min(c.winfo_width()-30,c.winfo_height()-25)/3
        size=max(60,size);ox=(c.winfo_width()-size*3)/2;oy=10
        for slot,piece in enumerate(q['layout']):
            x,y=ox+slot%3*size,oy+slot//3*size;rects.append((x,y,x+size,y+size))
            c.create_rectangle(x+2,y+2,x+size-2,y+size-2,fill='#c1aa79',outline=GOLD if held[0]==slot else '#695a3d',width=3)
            sx,sy=piece%3/3,piece//3/3
            for color,width,points in paths:
                for a,b in zip(points,points[1:]):
                    line=clip(a,b,sx,sy,sx+1/3,sy+1/3)
                    if line:c.create_line(*[x+(v-sx)*size*3 if i%2==0 else y+(v-sy)*size*3 for i,v in enumerate(line)],fill=color,width=width)
            for xx,yy in ((.08,.08),(.75,.85),(.87,.48),(.26,.52)):
                if sx<=xx<sx+1/3 and sy<=yy<sy+1/3:
                    px,py=x+(xx-sx)*size*3,y+(yy-sy)*size*3
                    c.create_polygon(px-7,py+5,px,py-9,px+8,py+5,fill='#66563d')
        if q['map_solved']:status.config(text=tr('restoration.map_solved',x=q['pos'][0],y=q['pos'][1]))
    def at(e):return next((i for i,(a,b,d,f) in enumerate(rects) if a<=e.x<d and b<=e.y<f),None)
    def press(e):held[0]=at(e);draw()
    def release(e):
        dest=at(e)
        if held[0] is not None and dest is not None:g.swap_map_pieces(ident,held[0],dest)
        held[0]=None;draw();app.refresh()
    c.bind('<Configure>',lambda e:draw());c.bind('<Button-1>',press);c.bind('<ButtonRelease-1>',release)
    ttk.Button(win,text=tr('restoration.close'),command=win.close_dialog).pack(pady=8)
