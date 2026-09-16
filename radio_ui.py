from i18n import t as tr
"""Radio tuning: persistent sliders, live signal and explicit one-turn attempts."""
import tkinter as tk
from tkinter import ttk
from inspection_ui import window
from visuals import PANEL,TEXT,GOLD,MUTED

def show(app,quest_id):
    g=app.game;q=g.destination_quest()
    if not q or q['id']!=quest_id or q['kind']!='radio':return
    win=window(app,tr('radio_ui.0001'))
    tk.Label(win,text=tr('radio_ui.0002'),bg=PANEL,fg=GOLD,font=('Segoe UI',17,'bold')).pack(pady=18)
    tk.Label(win,text=tr('radio_ui.0003'),bg=PANEL,fg=TEXT,justify='center').pack(pady=10)
    signal=tk.Label(win,bg=PANEL,fg='#91e6ab',font=('Segoe UI',15,'bold'));signal.pack(pady=8)
    progress=ttk.Progressbar(win,maximum=100,length=420);progress.pack(pady=6)
    values=[tk.IntVar(value=v) for v in q['radio_values']];meters=[]
    def update(*args):
        numbers=[v.get() for v in values];q['radio_values']=numbers
        strength=g.radio_signal(q,numbers);signal.config(text=tr('radio_ui.0004', v0=strength));progress['value']=strength
        for i,m in enumerate(meters):
            error=abs(numbers[i]-q['radio_target'][i]);m.config(text=tr('radio_ui.0005') if error<=1 else tr('radio_ui.0006') if error>7 else tr('radio_ui.0007') if error>3 else tr('radio_ui.0008'))
    for i,name in enumerate((tr('radio_ui.0009'),tr('radio_ui.0010'),tr('radio_ui.0011'))):
        row=tk.Frame(win,bg=PANEL);row.pack(fill='x',padx=28,pady=10)
        tk.Label(row,text=name,bg=PANEL,fg=GOLD,anchor='w').pack(fill='x')
        tk.Scale(row,from_=0,to=20,orient='horizontal',variable=values[i],command=update,bg=PANEL,fg=TEXT,highlightthickness=0,troughcolor='#182920',length=450).pack(fill='x')
        meter=tk.Label(row,bg=PANEL,fg=MUTED);meter.pack();meters.append(meter)
    result=tk.Label(win,bg=PANEL,fg=TEXT);result.pack(pady=10)
    def confirm():
        if g.tune_radio(q['id'],[v.get() for v in values]):
            result.config(text=tr('radio_ui.0012'),fg='#91e6ab');button.config(state='disabled')
            for child in win.winfo_children():
                for control in child.winfo_children():
                    if isinstance(control,tk.Scale):control.config(state='disabled')
        else:result.config(text=tr('radio_ui.0013', v0=q['radio_attempts']),fg='#e9ad83')
        app.refresh()
    button=ttk.Button(win,text=tr('radio_ui.0014'),command=confirm);button.pack(pady=8)
    update()
