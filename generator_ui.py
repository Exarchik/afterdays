"""Five switches: discover a persistent order, resetting on a wrong choice."""
import tkinter as tk
from tkinter import ttk
import progression as p
from inspection_ui import window
from visuals import PANEL,TEXT,GOLD,icon
from i18n import t as tr

def show(app,ident):
    g=app.game;q=g.local_expedition()
    if not q or q['id']!=ident or q['kind']!='generator':return
    win=window(app,tr('exp.generator'))
    tk.Label(win,text=tr('scav.generator_help'),bg=PANEL,fg=TEXT,wraplength=540).pack(padx=20,pady=20)
    board=tk.Frame(win,bg=PANEL);board.pack(pady=16);buttons=[]
    status=tk.Label(win,bg=PANEL,fg=GOLD,wraplength=540);status.pack(pady=10)
    def refresh():
        for n,button in enumerate(buttons):
            on=n in q['generator_input'];button.config(text=f'{n+1}\n'+('┃' if on else '╱'),bg='#346c49' if on else '#624532',state='disabled' if q['progress'] or on else 'normal')
        status.config(text=tr('scav.switch_progress',count=len(q['generator_input'])))
    def toggle(n):
        if g.generator_toggle(ident,n):refresh()
    for n in range(5):
        button=tk.Button(board,font=('Segoe UI',22),width=3,fg='#ebead5',command=lambda n=n:toggle(n));button.grid(row=0,column=n,padx=4);buttons.append(button)
    item=p.parts(q['material_qty']) if q['material']=='parts' else p.fragments(q['material_qty'])
    art=tk.Canvas(win,bg=PANEL,width=64,height=64,highlightthickness=0);art.pack();icon(art,item,0,0,64)
    tk.Label(win,text=tr('exp.material',name=item['name'],qty=q['material_qty']),bg=PANEL,fg=GOLD).pack(pady=12)
    def confirm():
        if g.repair_generator(ident):finish.config(state='disabled')
        refresh();status.config(text=g.messages[-1]);app.refresh()
    finish=ttk.Button(win,text=tr('exp.repair_button'),command=confirm);finish.pack(pady=14);refresh()
