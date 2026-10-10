"""Five switches: discover a persistent order, resetting on a wrong choice."""
from game import items
import tkinter as tk
from tkinter import ttk
import game.items as p
from ui.inspection import window
from visuals import PANEL,TEXT,GOLD,icon
from i18n import t as tr

def show(app,ident):
    g=app.game;q=g.local_expedition()
    if not q or q['id']!=ident or q['kind']!='generator':return
    win=window(app,tr('exp.generator'))
    tk.Label(win,text=tr('scav.generator_help'),bg=PANEL,fg=TEXT,wraplength=540).pack(padx=20,pady=20)
    board=tk.Frame(win,bg=PANEL);board.pack(pady=16);buttons=[];animation={'busy':False,'timer':None,'closed':False}
    status=tk.Label(win,bg=PANEL,fg=GOLD,wraplength=540);status.pack(pady=10)
    def refresh():
        for n,button in enumerate(buttons):
            on=n in q['generator_input'];button.config(text=f'{n+1}\n'+('┃' if on else '╱'),bg='#346c49' if on else '#624532',state='disabled' if q['progress'] or on else 'normal')
        status.config(text=tr('scav.switch_progress',count=len(q['generator_input'])))
    def toggle(n):
        if animation['busy']:return
        if not g.generator_toggle(ident,n):return
        animation['busy']=True
        wrong=not q['generator_input'];shock=getattr(g,'_generator_shock',0)
        for button in buttons:button.config(state='disabled')
        finish.config(state='disabled')
        def frame(step=0):
            animation['timer']=None
            if animation['closed']:return
            if step<5:
                if wrong:
                    for button in buttons:button.config(bg='#b34935' if step%2==0 else '#624532',text='ϟ' if shock else '○')
                else:buttons[n].config(text=str(n+1)+'\n'+['╱','─','╲','│','┃'][step],bg='#a89840' if step<3 else '#346c49')
                animation['timer']=win.after(70,lambda:frame(step+1));return
            animation['busy']=False;refresh();app.refresh()
            if g.local_expedition() is not q:win.close_dialog();return
            if wrong:status.config(text=tr('scav.generator_reset')+(f' −{shock} HP' if shock else ''))
            finish.config(state='normal')
        frame()
    def destroyed(event):
        if event.widget is not win:return
        animation['closed']=True
        if animation['timer'] is not None:
            try:win.after_cancel(animation['timer'])
            except tk.TclError:pass
    win.bind('<Destroy>',destroyed,add='+')
    for n in range(5):
        button=tk.Button(board,font=('Segoe UI',22),width=3,fg='#ebead5',command=lambda n=n:toggle(n));button.grid(row=0,column=n,padx=4);buttons.append(button)
    item=items.parts(q['material_qty']) if q['material']=='parts' else items.fragments(q['material_qty'])
    art=tk.Canvas(win,bg=PANEL,width=64,height=64,highlightthickness=0);art.pack();icon(art,item,0,0,64)
    tk.Label(win,text=tr('exp.material',name=item['name'],qty=q['material_qty']),bg=PANEL,fg=GOLD).pack(pady=12)
    def confirm():
        if g.repair_generator(ident):finish.config(state='disabled')
        refresh();status.config(text=g.messages[-1]);app.refresh()
    finish=ttk.Button(win,text=tr('exp.repair_button'),command=confirm);finish.pack(pady=14);refresh()
