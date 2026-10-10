"""Themed event loading, results and location-loot transfer."""
from game import items
import tkinter as tk
from tkinter import ttk
import sprites
from visuals import PANEL,TEXT,GOLD,icon


def loading(app,build):
    if app.dialog or getattr(app,'_event_loading',False):return
    app.route.pause();app._event_loading=True
    event=app.game.road_event
    win=app.popup(event['title'],'760x650')
    cover=tk.Frame(win,bg=PANEL,cursor='watch');cover.pack(fill='both',expand=True)
    center=tk.Frame(cover,bg='#17221d');center.place(relx=.5,rely=.5,anchor='center')
    wheel=tk.Canvas(center,width=64,height=64,bg='#17221d',highlightthickness=0);wheel.pack()
    tk.Label(center,text='Відкриваємо подію…',bg='#17221d',fg=GOLD,font=('Segoe UI',14)).pack(pady=12)
    job=[None]
    def tick(angle=0):
        wheel.delete('all');wheel.create_arc(10,10,54,54,start=angle,extent=265,style='arc',outline=GOLD,width=4)
        job[0]=cover.after(70,lambda:tick((angle+30)%360))
    tick()
    def ready():
        if not win.winfo_exists():return
        try:
            sprites.photo(win,event.get('art','event_theme:camp'),max(sprites.SIZES))
            if job[0]:cover.after_cancel(job[0]);job[0]=None
            cover.destroy()
            build(win)
        finally:
            app._event_loading=False
    task=win.after(40,ready)
    original_close=win.close_dialog
    def close():
        win.after_cancel(task)
        if job[0]:win.after_cancel(job[0])
        app._event_loading=False;original_close()
    win.close_dialog=close;win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',lambda e:close())


def clear(win):
    for child in win.winfo_children():child.destroy()


def reward_icon(canvas,row):
    if row.get('item'):
        icon(canvas,row['item'],0,0,48);return
    kind=row.get('effect_kind','')
    import game.items as p
    if kind in ('money','credits','food','med','rad','repairkit','parts','fragments','ammo'):
        sample=(items.supply('credits') if kind in ('money','credits') else
                items.parts(1) if kind=='parts' else items.fragments(1) if kind=='fragments' else
                items.ammunition('pistol',1) if kind=='ammo' else items.supply(kind))
        icon(canvas,sample,0,0,48);return
    symbol={'xp':'XP','heal':'+','damage':'♥','damage_dealt':'⚔','radiation':'☢','radiation_heal':'☢',
            'satiety_gain':'♨','satiety_loss':'♨','reveal':'⌖','discover':'⌖',
            'wear':'⚒','wear_armor':'⚒','repair_weapon':'⚒','repair_armor':'⚒'}.get(kind,'◆')
    canvas.create_oval(5,5,43,43,fill='#344238',outline=GOLD)
    canvas.create_text(24,24,text=symbol,fill=GOLD,font=('Segoe UI',13,'bold'))


def show_result(app,report,win=None):
    win=win or app.popup(report['title'],'760x650')
    clear(win);win.title(report['title'])
    head=tk.Frame(win,bg=PANEL);head.pack(fill='x',padx=18,pady=14)
    picture=tk.Canvas(head,width=144,height=144,bg=PANEL,highlightthickness=0);picture.pack(side='left',padx=(0,18))
    if not sprites.draw(picture,report.get('art'),0,0,144):sprites.draw(picture,'stash',0,0,144)
    tk.Label(head,text=report['title'],bg=PANEL,fg=GOLD,font=('Segoe UI',17,'bold'),wraplength=440,justify='left').pack(anchor='w',pady=12)
    tk.Label(head,text='Результати битви' if report.get('battle') else 'Результати події',bg=PANEL,fg=TEXT).pack(anchor='w')
    if report.get('partial'):tk.Label(head,text='Статистика від першої дії після оновлення гри.',bg=PANEL,fg=TEXT,wraplength=420).pack(anchor='w',pady=6)
    footer=tk.Frame(win,bg=PANEL);footer.pack(side='bottom',fill='x',padx=18,pady=12)
    scroll=tk.Canvas(win,bg=PANEL,highlightthickness=0)
    bar=ttk.Scrollbar(win,command=scroll.yview);bar.pack(side='right',fill='y')
    scroll.pack(fill='both',expand=True,padx=18);scroll.configure(yscrollcommand=bar.set)
    body=tk.Frame(scroll,bg=PANEL);node=scroll.create_window(0,0,window=body,anchor='nw')
    body.bind('<Configure>',lambda e:scroll.configure(scrollregion=scroll.bbox('all')))
    scroll.bind('<Configure>',lambda e:scroll.itemconfigure(node,width=e.width))
    from event_results import groups
    for title,rows in zip(('Стани','Предмети'),groups(report)):
        tk.Label(body,text=title,bg=PANEL,fg=GOLD,font=('Segoe UI',13,'bold')).pack(anchor='w',pady=(12,4))
        if not rows:tk.Label(body,text='Немає змін' if title=='Стани' else 'Немає предметів',bg=PANEL,fg=TEXT).pack(anchor='w',pady=5)
        for row in rows:
            line=tk.Frame(body,bg=PANEL);line.pack(fill='x',pady=4)
            art=tk.Canvas(line,width=48,height=48,bg=PANEL,highlightthickness=0);art.pack(side='left',padx=(0,12));reward_icon(art,row)
            label=tk.Label(line,text=row['text'],bg=PANEL,fg=row.get('color',TEXT),wraplength=570,justify='left',anchor='w');label.pack(side='left',fill='x',expand=True)
            label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(80,e.width)))
    local=any(row.get('destination')=='loot' for row in report['rows'])
    def close():
        if not win.winfo_exists():return
        app.dialog=None;win.destroy()
        if local and app.game.loot and not app.game.battle:show_loot(app)
        app.refresh()
    win.close_dialog=close;win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',lambda e:close())
    ttk.Button(footer,text='До сховку на локації' if local else 'Продовжити',command=close).pack(side='right')


def show_loot(app):
    from ui.adventure import Storage
    if app.dialog or app.game.battle:return
    win=app.popup('Сховок на локації','940x680')
    Storage(win,app,source='loot').pack(fill='both',expand=True)


def show_notice(app,text,key):
    import ui.dialogs as game_dialogs
    art={'_border_notice':'npc:mayor','_mayor_notice':'npc:mayor',
         '_reputation_notice':'npc:mayor','_settler_notice':'npc_roamer_smith'}.get(key,'journal')
    game_dialogs.showinfo('Повідомлення',text,parent=app.root,art=art)
