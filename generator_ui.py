"""Persistent 3×3 Lights Out circuit repair."""
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
    tk.Label(win,text=tr('exp.generator_help'),bg=PANEL,fg=TEXT,wraplength=530).pack(padx=20,pady=14)
    board=tk.Frame(win,bg=PANEL);board.pack(pady=8);buttons=[]
    def refresh():
        for n,button in enumerate(buttons):button.config(text='●' if q['generator_board'][n] else '○',bg='#346c49' if q['generator_board'][n] else '#624532')
    def toggle(n):
        if g.generator_toggle(ident,n):refresh()
    for n in range(9):
        button=tk.Button(board,text='○',font=('Segoe UI',24),width=4,fg='#ebead5',command=lambda n=n:toggle(n));button.grid(row=n//3,column=n%3,padx=3,pady=3);buttons.append(button)
    item=p.parts(q['material_qty']) if q['material']=='parts' else p.fragments(q['material_qty'])
    art=tk.Canvas(win,bg=PANEL,width=64,height=64,highlightthickness=0);art.pack();icon(art,item,0,0,64)
    tk.Label(win,text=tr('exp.material',name=item['name'],qty=q['material_qty']),bg=PANEL,fg=GOLD,wraplength=530).pack(pady=8)
    status=tk.Label(win,bg=PANEL,fg=TEXT);status.pack()
    def confirm():
        if g.repair_generator(ident):
            finish.config(state='disabled')
            for button in buttons:button.config(state='disabled')
        status.config(text=g.messages[-1]);app.refresh()
    finish=ttk.Button(win,text=tr('exp.repair_button'),command=confirm);finish.pack(pady=12);refresh()
