"""Generator repair: switch a set of loads (some negative) so the gauge needle stands in the green zone."""
import math
import tkinter as tk
from tkinter import ttk
from game import items
from ui.inspection import window
from visuals import PANEL,TEXT,GOLD,icon
from game.systems import generator_balance as balance
from i18n import t as tr

W,H=820,380
GAUGE=(410,170,112)          # centre x, centre y, radius
FACE,INK,NEEDLE='#e7e0c4','#22231d','#b1301f'
ZONE,REDZONE='#5fbf72','#d8553f'
FRAME_MS=30


def show(app,ident):
    g=app.game;q=g.local_expedition()
    if not q or q['id']!=ident or q['kind']!='generator':return
    g.ensure_generator(q)
    Panel(app,g,q)


class Panel:
    def __init__(self,app,game,quest):
        self.app,self.game,self.q=app,game,quest;self.ident=quest['id']
        self.shown=float(balance.load(quest));self.spark=None;self.flash_on=[];self.timer=None;self.closed=False;self.busy=False
        self.win=win=window(app,tr('exp.generator'));win._generator=self
        sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
        w,h=min(880,sw-20),min(720,sh-60)
        win.geometry(f'{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2-20)}')
        tk.Label(win,text=tr('scav.generator_help'),bg=PANEL,fg=TEXT,wraplength=w-60,justify='left').pack(padx=16,pady=(10,4))
        bottom=tk.Frame(win,bg=PANEL);bottom.pack(side='bottom',fill='x',padx=16,pady=(4,8))
        item=items.parts(quest['material_qty']) if quest['material']=='parts' else items.fragments(quest['material_qty'])
        art=tk.Canvas(bottom,bg=PANEL,width=48,height=48,highlightthickness=0);art.pack(side='left');icon(art,item,0,0,48)
        tk.Label(bottom,text=tr('exp.material',name=item['name'],qty=quest['material_qty']),bg=PANEL,fg=GOLD,wraplength=420,justify='left').pack(side='left',padx=8)
        self.finish=ttk.Button(bottom,text=tr('exp.repair_button'),command=self.confirm);self.finish.pack(side='right')
        self.status=tk.Label(win,bg=PANEL,fg=GOLD,wraplength=w-60,justify='left');self.status.pack(side='bottom',fill='x',padx=16)
        self.canvas=tk.Canvas(win,width=W,height=H,bg='#2a2c24',highlightthickness=0);self.canvas.pack(pady=4)
        self.canvas.bind('<Button-1>',self.click)
        for n in range(len(quest['generator_on'])):
            win.bind(f'<KeyPress-{n+1}>',lambda e,n=n:self.toggle(n))
        win.bind('<Destroy>',self.destroyed,add='+')
        self.refresh();self.draw()

    # --- geometry ---
    def lever_x(self,i):
        n=len(self.q['generator_on']);return 30+(W-60)/(n+1)*(i+1)

    def angle(self,value):
        return math.pi*(1+max(0,min(balance.MAX,value))/balance.MAX)

    # --- input ---
    def click(self,e):
        for i in range(len(self.q['generator_on'])):
            x=self.lever_x(i)
            if abs(e.x-x)<36 and 250<=e.y<=360:self.toggle(i);return

    def toggle(self,i):
        if self.busy or self.closed or self.q.get('progress'):return
        before=self.q['generator_on'][:]
        if not self.game.generator_toggle(self.ident,i):return
        if getattr(self.game,'_generator_overload',False):
            # Show the overload on the gauge for a moment, then the protection drops every switch.
            self.busy=True;self.spark=i;self.overload_value=balance.MAX
            before[i]=True;self.flash_on=before   # levers as they were when the protection tripped
            shock=getattr(self.game,'_generator_shock',0)
            self.status.config(text=tr('scav.generator_reset')+(f' −{shock} HP' if shock else ''),fg='#ef7a62')
            self.finish.config(state='disabled')
            self.win.after(650,self.recover)
            self.app.refresh()
        else:self.refresh()
        self.animate()

    def recover(self):
        if self.closed:return
        self.busy=False;self.spark=None;self.refresh();self.animate()
        if self.game.local_expedition() is not self.q:self.win.close_dialog()

    def confirm(self):
        if self.game.repair_generator(self.ident):self.finish.config(state='disabled')
        self.status.config(text=self.game.messages[-1],fg='#91d9aa' if self.q.get('progress') else '#edb477')
        self.app.refresh();self.draw()

    def destroyed(self,event):
        if event.widget is not self.win:return
        self.closed=True
        if self.timer is not None:
            try:self.win.after_cancel(self.timer)
            except tk.TclError:pass
        self.timer=None

    # --- state text ---
    def refresh(self):
        q=self.q;value=balance.load(q);lo,hi=q['generator_zone'];ok=lo<=value<=hi
        done=bool(q.get('progress'))
        self.finish.config(state='normal' if ok and not done else 'disabled')
        if done:self.status.config(text=tr('exp.generator_done'),fg='#91d9aa')
        elif ok:self.status.config(text=f'Навантаження {value} — у зеленій зоні. Можна завершити ремонт.',fg='#91d9aa')
        elif not any(q['generator_on']):self.status.config(text=f'Зелена зона: {lo}–{hi}. Увімкніть рубильники.',fg=GOLD)
        else:self.status.config(text=f'Навантаження {value}: {"замало" if value<lo else "забагато"} для зеленої зони {lo}–{hi}.',fg=GOLD)

    # --- animation ---
    def target(self):
        return getattr(self,'overload_value',balance.MAX) if self.spark is not None else balance.load(self.q)

    def animate(self):
        if self.timer is None and not self.closed:self.timer=self.win.after(FRAME_MS,self.frame)

    def frame(self):
        self.timer=None
        if self.closed:return
        goal=self.target();self.shown+=(goal-self.shown)*.25
        if abs(goal-self.shown)<.3:self.shown=float(goal)
        self.draw()
        if self.shown!=goal or self.spark is not None:self.animate()

    # --- drawing ---
    def draw(self):
        c=self.canvas;c.delete('all');q=self.q;cx,cy,r=GAUGE
        c.create_rectangle(4,4,W-4,H-4,outline='#4b4f40',width=3)
        for x,y in ((16,16),(W-16,16),(16,H-16),(W-16,H-16)):
            c.create_oval(x-5,y-5,x+5,y+5,fill='#8d8f7b',outline='');c.create_line(x-3,y,x+3,y,fill='#2c2e26')
        c.create_text(W/2,26,text='ГЕНЕРАТОР ДГ-12 · БАЛАНС НАВАНТАЖЕННЯ',fill='#d8d2b2',font=('Segoe UI',11,'bold'))
        # half-dial gauge
        c.create_arc(cx-r-10,cy-r-10,cx+r+10,cy+r+10,start=0,extent=180,fill='#1d1e19',outline='')
        c.create_arc(cx-r,cy-r,cx+r,cy+r,start=0,extent=180,fill=FACE,outline='')
        band=r-14
        def arc(lo,hi,color):
            a0=180-lo/balance.MAX*180;a1=180-hi/balance.MAX*180
            c.create_arc(cx-band,cy-band,cx+band,cy+band,start=a1,extent=a0-a1,style='arc',outline=color,width=13)
        lo,hi=q['generator_zone']
        arc(max(0,lo),min(balance.MAX,hi),ZONE);arc(balance.RED,balance.MAX,REDZONE)
        for v in range(0,balance.MAX+1,10):
            a=self.angle(v);big=v%50==0;inner=r-(26 if big else 12)
            c.create_line(cx+math.cos(a)*(r-2),cy+math.sin(a)*(r-2),cx+math.cos(a)*inner,cy+math.sin(a)*inner,fill=INK,width=2 if big else 1)
            if big:c.create_text(cx+math.cos(a)*(r-42),min(cy-10,cy+math.sin(a)*(r-42)+4),text=str(v),fill=INK,font=('Consolas',10))
        c.create_text(cx,cy-46,text='НАВАНТАЖЕННЯ',fill=INK,font=('Segoe UI',8,'bold'))
        a=self.angle(self.shown)
        c.create_line(cx,cy,cx+math.cos(a)*(r-18),cy+math.sin(a)*(r-18),fill=NEEDLE,width=4,capstyle='round')
        c.create_oval(cx-7,cy-7,cx+7,cy+7,fill='#2b2d25',outline='')
        value=balance.load(q);ok=lo<=value<=hi and self.spark is None
        c.create_rectangle(cx-80,cy+14,cx+80,cy+44,fill='#11120f',outline='#4b4f40')
        shown=sum(w for w,on in zip(q['generator_weights'],self.flash_on) if on) if self.spark is not None else value
        c.create_text(cx,cy+29,text=f'{shown} / зона {lo}–{hi}',fill='#b9e07a',font=('Consolas',12))
        for x,label,on,color in ((cx-160,'ПЕРЕВАНТ.',self.spark is not None,'#ef7a62'),(cx+160,'НОРМА',ok,'#8fdc9f')):
            c.create_oval(x-9,cy-14,x+9,cy+4,fill=color if on else '#3a3d32',outline='#1d1e19',width=2)
            c.create_text(x,cy+18,text=label,fill='#d8d2b2',font=('Consolas',8))
        # levers
        weights=q['generator_weights'];marks=q.get('generator_settings',{}).get('show_weights',0)
        levers=self.flash_on if self.spark is not None else q['generator_on']
        for i,on in enumerate(levers):
            x=self.lever_x(i);y=300
            c.create_rectangle(x-32,y-44,x+32,y+44,fill='#191a16',outline='#4b4f40',width=2)
            c.create_rectangle(x-5,y-32,x+5,y+34,fill='#0f100d',outline='')
            hy=y-32 if on else y+12
            c.create_rectangle(x-3,min(hy+20,y),x+3,max(hy,y),fill='#8d8f7b',outline='')
            c.create_rectangle(x-20,hy,x+20,hy+20,fill='#4c8a55' if on else '#7a3a2b',outline='#1d1e19',width=2)
            label=(f'+{weights[i]}' if weights[i]>0 else f'−{-weights[i]}') if marks else ('ВВІМК' if on else 'ВИМК')
            c.create_text(x,y-54,text=label,fill='#8fdc9f' if on else '#a3a690',font=('Consolas',9))
            c.create_text(x,y+60,text=str(i+1),fill='#e3e3d4',font=('Segoe UI',12,'bold'))
            if self.spark==i:
                c.create_oval(x-28,y-28,x+28,y+28,fill='',outline='#ffd76a',width=3)
                c.create_line(x-8,y-62,x+6,y-46,x-4,y-46,x+8,y-28,fill='#ffd76a',width=3)
