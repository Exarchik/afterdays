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


# Result semantics differ from the art IDs used by the content editor.
EFFECT_ART = {
    'damage_dealt':'damage_to_enemies', 'damage':'damage_to_player',
    'xp':'get_xp', 'heal':'healed',
    'radiation_heal':'radiation_heal', 'radiation':'radiation_damage',
    'satiety_gain':'food_full', 'satiety_loss':'lost_satiety',
    'cache':'find_hideout', 'money_paid':'money_paid',
    'reveal':'open_map', 'discover':'open_location',
    'repair_armor':'repair_armor', 'wear_armor':'damage_armor',
    'repair_weapon':'repair_weapon', 'wear':'damage_weapon',
    'fence_hole':'fence_shortcut', 'buff_stealth':'invisibility',
    'buff_regen':'regeneration', 'buff_satiety':'food_full',
    'ambush':'ambush',
}


def reward_icon(canvas,row):
    kind=row.get('effect_kind','')
    art=EFFECT_ART.get(kind)
    # Granted items retain their own art; these state rows describe spending/loss.
    if not row.get('destination'):
        if kind in ('money','credits'):art='lost_money'
        elif kind=='food':art='lost_food'
    if art and sprites.draw(canvas,'effects:'+art,0,0,48):return
    if row.get('item'):
        icon(canvas,row['item'],0,0,48);return
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


class ResultGroup(tk.Frame):
    """Responsive rows of icon/label pairs, shared by states and loot."""
    def __init__(self,parent,rows):
        super().__init__(parent,bg=PANEL)
        self.cards=[]
        self.columns=0
        for row in rows:
            card=tk.Frame(self,bg=PANEL)
            card.columnconfigure(1,weight=1)
            art=tk.Canvas(card,width=48,height=48,bg=PANEL,highlightthickness=0)
            art.grid(row=0,column=0,padx=(0,10));reward_icon(art,row)
            label=tk.Label(card,text=row['text'],bg=PANEL,fg=row.get('color',TEXT),
                           width=1,justify='left',anchor='w')
            label.grid(row=0,column=1,sticky='ew')
            self.cards.append((card,label))
        self.bind('<Configure>',self.reflow)

    def reflow(self,event):
        columns=max(1,min(len(self.cards),event.width//220))
        for column in range(max(self.columns,columns)):
            self.columnconfigure(column,weight=1 if column<columns else 0,
                                 uniform='result' if column<columns else '')
        self.columns=columns
        for index,(card,label) in enumerate(self.cards):
            label.configure(wraplength=max(1,event.width//columns-74))
            card.grid(row=index//columns,column=index%columns,sticky='ew',padx=(0,12),pady=6)


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
    viewport=tk.Frame(win,bg=PANEL);viewport.pack(fill='both',expand=True,padx=18)
    viewport.rowconfigure(0,weight=1);viewport.columnconfigure(0,weight=1)
    scroll=tk.Canvas(viewport,bg=PANEL,highlightthickness=0)
    bar=ttk.Scrollbar(viewport,orient='vertical',command=scroll.yview)
    scroll.grid(row=0,column=0,sticky='nsew');bar.grid(row=0,column=1,sticky='ns')
    from ui.scrolling import auto_scrollbar
    auto_scrollbar(scroll,bar,grid=True)
    body=tk.Frame(scroll,bg=PANEL);node=scroll.create_window(0,0,window=body,anchor='nw')
    body.columnconfigure(0,weight=1)
    body.bind('<Configure>',lambda e:scroll.configure(scrollregion=scroll.bbox('all')))
    def resize(event):
        scroll.itemconfigure(node,width=event.width)
    scroll.bind('<Configure>',resize)
    def wheel(event):
        if event.num==4:step=-1
        elif event.num==5:step=1
        else:step=-1 if event.delta>0 else 1
        scroll.yview_scroll(step,'units')
        return 'break'
    # A reused event window still has bindings to its destroyed narrative canvas.
    for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):win.bind(sequence,wheel)
    from event_results import groups
    index=0
    for title,rows in zip(('Стани','Предмети'),groups(report)):
        tk.Label(body,text=title,bg=PANEL,fg=GOLD,font=('Segoe UI',13,'bold')).grid(row=index,column=0,sticky='w',pady=(12,4))
        index+=1
        if not rows:
            tk.Label(body,text='Немає змін' if title=='Стани' else 'Немає предметів',bg=PANEL,fg=TEXT).grid(row=index,column=0,sticky='w',pady=5)
            index+=1
        else:
            ResultGroup(body,rows).grid(row=index,column=0,sticky='ew',pady=(0,16))
            index+=1
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
