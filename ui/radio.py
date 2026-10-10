"""Visual waveform matching; no accuracy percentages or warmer/colder hints."""
import math,time
from radio_interference import Interference
import tkinter as tk
from tkinter import ttk
from ui.inspection import window
from visuals import PANEL,TEXT,GOLD
from i18n import t as tr

def waveform(values,width=520,height=175):
    freq,amp,phase=1+values[0]/4,.12+values[1]/24,values[2]*math.pi/20
    return [coordinate for x in range(8,width-8,2) for coordinate in (x,height/2-math.sin((x-8)/(width-16)*2*math.pi*freq+phase)*amp*height*.42)]

def show(app,quest_id):
    g=app.game;q=g.destination_quest()
    if not q or q['id']!=quest_id or q['kind']!='radio':return
    win=window(app,tr('radio_ui.0001'))
    tk.Label(win,text=tr('exp.radio_help'),bg=PANEL,fg=TEXT,wraplength=540).pack(pady=12)
    canvas=tk.Canvas(win,width=520,height=175,bg='#10221b',highlightthickness=0);canvas.pack(fill='x',padx=18)
    tk.Label(win,text=tr('exp.wave_target')+' — ━   '+tr('exp.wave_current')+' — ┄',bg=PANEL,fg=GOLD).pack()
    values=[tk.IntVar(value=v) for v in q['radio_values']];sliders=[]
    interference=Interference(time.monotonic());state={'noise':False,'timer':None,'closed':False,'done':False}
    def update(*args):
        numbers=[v.get() for v in values];q['radio_values']=numbers;canvas.delete('all')
        width=max(200,canvas.winfo_width());height=175
        for y in range(15,height,25):canvas.create_line(0,y,width,y,fill='#294237')
        reference=interference.trace(width,height) if state['noise'] else waveform(q['radio_target'],width,height)
        canvas.create_line(*reference,fill='#e8c886',width=3)
        if state['noise']:canvas.create_text(width/2,12,text=tr('settlements.noise'),fill='#e8c886',font=('Segoe UI',9))
        canvas.create_line(*waveform(numbers,width,height),fill='#70ddd3',width=2,dash=(5,3))
    for i,key in enumerate(('frequency','amplitude','phase')):
        row=tk.Frame(win,bg=PANEL);row.pack(fill='x',padx=24,pady=3)
        tk.Label(row,text=tr('exp.'+key),bg=PANEL,fg=GOLD).pack(anchor='w')
        slider=tk.Scale(row,from_=0,to=20,orient='horizontal',variable=values[i],command=update,bg=PANEL,fg=TEXT,highlightthickness=0);slider.pack(fill='x');sliders.append(slider)
    result=tk.Label(win,bg=PANEL,fg=TEXT);result.pack(pady=5)
    def confirm():
        if g.tune_radio(q['id'],[v.get() for v in values]):
            state['done']=True;state['noise']=False;update()
            result.config(text=tr('radio_ui.0012'));button.config(state='disabled')
            for slider in sliders:slider.config(state='disabled')
        else:result.config(text=tr('radio_ui.0013',v0=q['radio_attempts']))
        app.refresh()
    button=ttk.Button(win,text=tr('radio_ui.0014'),command=confirm);button.pack(pady=8)
    def tick():
        state['timer']=None
        if state['closed'] or state['done']:return
        state['noise']=interference.advance(time.monotonic())
        update();state['timer']=win.after(100,tick)
    def destroyed(event):
        if event.widget is not win:return
        state['closed']=True
        if state['timer'] is not None:
            try:win.after_cancel(state['timer'])
            except tk.TclError:pass
    win.bind('<Destroy>',destroyed,add='+')
    canvas.bind('<Configure>',update);update();state['timer']=win.after(100,tick)
