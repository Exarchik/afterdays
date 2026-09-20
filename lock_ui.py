"""Animated lock picking. The model validates position, quest and material use."""
import math
import tkinter as tk
from tkinter import ttk
from i18n import t as tr
from visuals import PANEL,TEXT,GOLD

def show(app,ident):
    g=app.game;q=g.local_expedition()
    if not q or q['id']!=ident or q['kind']!='cache' or 'lock_target' not in q:return
    win=app.popup(tr('update024.lock_title'),'580x490')
    tk.Label(win,text=tr('update024.lock_info'),bg=PANEL,fg=TEXT,wraplength=530,justify='left').pack(padx=20,pady=15)
    c=tk.Canvas(win,width=540,height=250,bg='#17221d',highlightthickness=0);c.pack(fill='both',expand=True,padx=15)
    angle=tk.DoubleVar(value=90);busy=[False];closed=[False]
    slider=ttk.Scale(win,from_=0,to=180,variable=angle,command=lambda value:paint());slider.pack(fill='x',padx=30,pady=10)
    status=tk.Label(win,bg=PANEL,fg=GOLD);status.pack(pady=6)
    def paint(rotation=0,broken=False):
        if not win.winfo_exists():return
        c.delete('all');x=max(270,c.winfo_width()/2);y=140
        c.create_arc(x-100,y-115,x+100,y+85,start=0,extent=180,outline='#6f8777',style='arc',width=2)
        for a in range(0,181,15):
            r=math.radians(a);c.create_line(x+94*math.cos(r),y-15-94*math.sin(r),x+101*math.cos(r),y-15-101*math.sin(r),fill='#a9b5a2')
        c.create_oval(x-52,y-52,x+52,y+52,fill='#555e56',outline=GOLD,width=4)
        c.create_oval(x-30,y-30,x+30,y+30,fill='#26372d',outline='#839784',width=3)
        r=math.radians(rotation)
        c.create_line(x-23*math.sin(r),y-23*math.cos(r),x+23*math.sin(r),y+23*math.cos(r),fill='#d4d0a4',width=7)
        r=math.radians(angle.get());length=55 if broken else 112
        c.create_line(x,y,x+length*math.cos(r),y-length*math.sin(r),fill='#e48969' if broken else '#d5e3cf',width=4)
    def attempt():
        if busy[0] or closed[0]:return
        if g.count('parts')<1:status.config(text=tr('update024.lock_need'));return
        selected=angle.get();result=g.unlock_cache(ident,selected)
        if result is None:status.config(text=tr('update024.lock_need'));return
        busy[0]=True;button.config(state='disabled');slider.state(['disabled'])
        reach=90 if result else max(8,65-abs(selected-q['lock_target'])*.4)
        def frame(n=0):
            if not win.winfo_exists():return
            phase=n/24
            rotation=reach*min(1,phase*2) if result else reach*math.sin(math.pi*phase)
            paint(rotation,not result and n>17)
            if n<24:win.after(25,lambda:frame(n+1));return
            busy[0]=False;closed[0]=bool(result)
            status.config(text=tr('update024.lock_ok') if result else tr('update024.lock_fail')+' '+tr('update024.lock_parts',qty=g.count('parts')))
            if not result:slider.state(['!disabled']);button.config(state='normal')
            app.refresh()
        frame()
    button=ttk.Button(win,text=tr('update024.lock_try'),command=attempt);button.pack(fill='x',padx=25,pady=10)
    status.config(text=tr('update024.lock_parts',qty=g.count('parts')));paint()
