"""Restoration dialogs: settlers, permissions and the torn-map entry point."""
import tkinter as tk
from tkinter import ttk
import ui.dialogs as messagebox
import sprites
from i18n import t as tr
from visuals import PANEL,TEXT
from ui.inspection import window

def dialog(app,title):
    app.route.pause()
    return window(app,title)


def choice(app,title,entries):
    win=dialog(app,title)
    for label,key,description,action in entries:
        frame=tk.Frame(win,bg=PANEL);frame.pack(fill='x',padx=15,pady=8)
        image=sprites.photo(frame,key,48)
        if image:tk.Label(frame,image=image,bg=PANEL).pack(side='left',padx=8)
        def invoke(action=action,description=description,key=key):
            if messagebox.askyesno(title,description,parent=win,art=key):
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
        entries.append((label,'npc:mayor' if n['role']=='mayor' else 'npc_roamer_'+n['role'],g.quest_text(q),action))
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
    """Open the torn-map minigame (ragged pieces of the real world map)."""
    import ui.torn_map as torn_map_ui
    return torn_map_ui.show(app,ident)
