"""Modal, icon-rich quest confirmation; no transaction before explicit confirmation."""
import tkinter as tk
from tkinter import ttk
from i18n import t as tr
from visuals import PANEL,TEXT,GOLD,icon

def confirm(panel,q,action):
    from ui.inspection import window
    from ui.refinement import Detail
    app=panel.app;g=app.game
    if action=='accept' and q['status']!='offered':return
    if action=='abandon' and q['status']!='active':return
    if action=='turn_in' and not g.can_turn_in(q):return
    if q['status']=='offered':q['seen']=True
    title=tr('quests.confirm_'+action)
    win=window(app,title)
    tk.Label(win,text=q['title'],bg=PANEL,fg=GOLD,font=('Segoe UI',13,'bold'),wraplength=580).pack(padx=12,pady=8)
    detail=Detail(win,height=11);detail.pack(fill='both',expand=True,padx=12)
    text=g.quest_text(q)
    if action=='turn_in':text=tr('quests.completed_objectives')+'\n'+text
    if action=='abandon':text+='\n\n'+tr('quests.abandon_warning')
    detail.config(text=text)
    def items_section(label,items):
        if not items:return
        tk.Label(win,text=label,bg=PANEL,fg=GOLD).pack(anchor='w',padx=14,pady=(8,0))
        art=tk.Canvas(win,bg=PANEL,height=95,highlightthickness=0);art.pack(fill='x',padx=12)
        def draw(event=None):
            art.delete('all');width=max(260,art.winfo_width());cell=width/max(1,len(items))
            for n,item in enumerate(items):
                x=n*cell+cell/2;icon(art,item,x-25,2,50)
                qty=item.get('qty',1)
                art.create_text(x,57,text=item['name']+(f' ×{qty}' if qty>1 else ''),fill=TEXT,width=cell-8,anchor='n',font=('Segoe UI',8))
        art.bind('<Configure>',draw);draw()
    items_section(tr('quests.required_items'),g.quest_item_views(q))
    if action!='abandon':
        gifts=g.prepare_quest_rewards(q)
        items_section(tr('quests.reward_items'),gifts)
        tk.Label(win,text=tr('quests.reward_summary',money=q.get('reward',0),xp=g.quest_xp(q)),bg=PANEL,fg=GOLD).pack(pady=6)
    def commit():
        if not win.winfo_exists():return
        operation={'accept':g.accept_quest,'turn_in':g.turn_in,'abandon':g.abandon_quest}[action]
        if operation(q['id']):
            win.close_dialog();panel.refresh();app.refresh()
        else:detail.config(text=g.quest_text(q)+'\n'+tr('quests.action_failed'))
    ttk.Button(win,text=title,command=commit).pack(fill='x',padx=12,pady=8)
