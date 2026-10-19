"""Disc lock picking: turn rings until every notch is under the bolt. The model validates everything."""
import math
import tkinter as tk
from tkinter import ttk
import ui.event as event_ui
from i18n import t as tr
from visuals import PANEL,TEXT,GOLD

W,H=640,470
CX,CY=W/2,H/2+22
R0,RW=50,32
FRAME_MS=30


def show(app,ident,win=None):
    g=app.game;context=g.lock_available(ident)
    if not context:return
    g.lock_state(context)
    win=win or app.popup(tr('update024.lock_title'),'720x640')
    event_ui.clear(win)
    sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
    w,h=min(720,sw-20),min(640,sh-60)
    win.geometry(f'{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2-20)}')
    DiscLock(app,win,ident,context)


class DiscLock:
    def __init__(self,app,win,ident,context):
        self.app,self.win,self.ident,self.context=app,win,ident,context
        self.game=app.game;self.state=self.game.lock_state(context);win._disc_lock=self
        self.shown=[p*360/self.state['positions'] for p in self.state['pos']]
        n=len(self.state['pos']);self.rw=min(RW,(CY-48-R0)/n)
        self.sel=n-1;self.timer=None;self.closed=False;self.flash=0;self.done=False
        tk.Label(win,text=tr('update024.lock_info'),bg=PANEL,fg=TEXT,wraplength=w_of(win)-50,justify='left').pack(padx=18,pady=(12,4))
        bottom=tk.Frame(win,bg=PANEL);bottom.pack(side='bottom',fill='x',padx=18,pady=(4,10))
        self.status=tk.Label(bottom,bg=PANEL,fg=GOLD,anchor='w',justify='left',wraplength=w_of(win)-60);self.status.pack(fill='x',pady=(0,6))
        self.open_button=ttk.Button(bottom,text=tr('update024.lock_try'),command=self.attempt);self.open_button.pack(side='right')
        self.undo_button=ttk.Button(bottom,text=tr('update024.lock_undo'),command=self.undo);self.undo_button.pack(side='right',padx=6)
        self.canvas=tk.Canvas(win,width=W,height=H,bg='#17201b',highlightthickness=0);self.canvas.pack(pady=2)
        self.canvas.bind('<Button-1>',self.click)
        for key,handler in (('<Left>',lambda e:self.turn(self.sel,-1)),('<Right>',lambda e:self.turn(self.sel,1)),
                            ('<Up>',lambda e:self.select(1)),('<Down>',lambda e:self.select(-1)),('<Return>',lambda e:self.attempt())):
            win.bind(key,handler)
        win.bind('<Destroy>',self.destroyed,add='+')
        self.say(tr('update024.lock_parts',qty=self.game.count('parts')))
        self.draw()

    # --- helpers ---
    def say(self,text,tone=GOLD):self.status.config(text=text,fg=tone)

    def ring_radius(self,i):return R0+i*self.rw

    def destroyed(self,event):
        if event.widget is not self.win:return
        self.closed=True
        if self.timer is not None:
            try:self.win.after_cancel(self.timer)
            except tk.TclError:pass
        self.timer=None

    # --- input ---
    def select(self,step):
        if self.done:return
        self.sel=max(0,min(len(self.state['pos'])-1,self.sel+step));self.draw()

    def click(self,event):
        d=math.hypot(event.x-CX,event.y-CY)
        ring=int((d-R0+self.rw/2)//self.rw)
        if 0<=ring<len(self.state['pos']) and d>=R0-self.rw/2:self.turn(ring,-1 if event.x<CX else 1)

    def turn(self,ring,direction):
        if self.done or self.closed:return
        result=self.game.lock_turn(self.ident,ring,direction)
        if result is None:
            self.say(tr('update024.lock_need'),'#edb477');return
        self.sel=ring
        if getattr(self.game,'_lock_pick_broke',False):
            self.flash=1;self.say(tr('update024.lock_worn')+' '+tr('update024.lock_parts',qty=self.game.count('parts')),'#edb477')
            self.app.refresh()
        else:
            aligned=sum(v==0 for v in self.state['pos'])
            self.say(f'Під засувкою: {aligned}/{len(self.state["pos"])} · '+tr('update024.lock_parts',qty=self.game.count('parts')))
        self.animate()

    def undo(self):
        if self.done:return
        if self.game.lock_undo(self.ident):self.animate()

    def attempt(self):
        if self.done or self.closed:return
        result=self.game.unlock_cache(self.ident)
        if result is None:self.say(tr('update024.lock_need'),'#edb477');return
        if not result:
            self.flash=1;self.say(tr('update024.lock_fail')+' '+tr('update024.lock_parts',qty=self.game.count('parts')),'#edb477')
            self.app.refresh();self.animate();return
        self.done=True;self.open_button.config(state='disabled');self.undo_button.config(state='disabled')
        self.say(tr('update024.lock_ok'),'#91d9aa');self.animate()
        self.win.after(700,self.finish)

    def finish(self):
        if self.closed:return
        reports=getattr(self.game,'_event_results',[])
        if reports:event_ui.show_result(self.app,reports.pop(0),win=self.win)
        else:self.win.close_dialog()
        self.app.refresh()

    # --- animation ---
    def animate(self):
        if self.timer is None and not self.closed:self.timer=self.win.after(FRAME_MS,self.frame)

    def frame(self):
        self.timer=None
        if self.closed:return
        moving=False;k=self.state['positions']
        for i,p in enumerate(self.state['pos']):
            goal=p*360/k;delta=((goal-self.shown[i])%360+540)%360-180
            if abs(delta)>.5:self.shown[i]+=delta*.35;moving=True
            else:self.shown[i]=goal
        self.flash=max(0,self.flash-.08)
        self.draw()
        if moving or self.flash>0:self.animate()

    # --- drawing ---
    def draw(self):
        c=self.canvas;c.delete('all');s=self.state;n=len(s['pos']);k=s['positions']
        outer=self.ring_radius(n)+14
        c.create_oval(CX-outer-12,CY-outer-12,CX+outer+12,CY+outer+12,fill='#3a3d36',outline='')
        c.create_oval(CX-outer,CY-outer,CX+outer,CY+outer,fill='#2b2d27',outline='')
        for j in range(8):
            a=j*math.pi/4;x,y=CX+math.cos(a)*(outer+6),CY+math.sin(a)*(outer+6)
            c.create_oval(x-3,y-3,x+3,y+3,fill='#5a5d55',outline='')
        # bolt above the lock; it slides up once everything lines up
        bolt=CY-outer-(36 if self.done else 10)
        c.create_rectangle(CX-9,bolt-34,CX+9,bolt+6,fill='#9aa0a4',outline='#5a5d55')
        for i in range(n-1,-1,-1):
            r=self.ring_radius(i)+self.rw/2-2;sel=i==self.sel and not self.done;ok=s['pos'][i]==0
            c.create_oval(CX-r,CY-r,CX+r,CY+r,fill='#8d8e84' if i%2 else '#a7a89c',outline=GOLD if sel else '#55574f',width=3 if sel else 2)
            base=math.radians(self.shown[i])
            for t in range(k):
                a=base+t*2*math.pi/k-math.pi/2
                c.create_line(CX+math.cos(a)*(r-6),CY+math.sin(a)*(r-6),CX+math.cos(a)*(r-12),CY+math.sin(a)*(r-12),fill='#4a4b44',width=2)
            # notch at the ring's local top, rotated with the ring
            a=base-math.pi/2;ux,uy=math.cos(a),math.sin(a);vx,vy=-uy,ux;depth=self.rw-4
            pts=[]
            for along,side in ((r,-10),(r,10),(r-depth,10),(r-depth,-10)):
                pts+=[CX+ux*along+vx*side,CY+uy*along+vy*side]
            c.create_polygon(*pts,fill='#1d3a26' if ok else '#141410',outline='')
            c.create_text(CX-r+9,CY-12,text=str(i+1)+('✓' if ok else ''),fill=GOLD if sel else '#2b2d27',font=('Segoe UI',8,'bold'))
        # gears on the seams between geared rings
        for j,(a,b,_) in enumerate(s['links']):
            seam=self.ring_radius(min(a,b))+self.rw/2-1;ang=math.radians(25+j*34)
            x,y=CX+math.cos(ang)*seam,CY+math.sin(ang)*seam
            for t in range(10):
                ta=t*math.pi/5;c.create_rectangle(x+math.cos(ta)*9-2,y+math.sin(ta)*9-2,x+math.cos(ta)*9+2,y+math.sin(ta)*9+2,fill='#c9a14e',outline='')
            c.create_oval(x-8,y-8,x+8,y+8,fill='#c9a14e',outline='')
        c.create_oval(CX-R0+8,CY-R0+8,CX+R0-8,CY+R0-8,fill='#3a3d36',outline='')
        c.create_rectangle(CX-13,CY-5,CX+13,CY+5,fill='#120c05',outline='')
        c.create_line(CX,CY-R0+8,CX,CY-outer-2,fill=GOLD,dash=(5,4),width=2)
        c.create_polygon(CX,CY-outer,CX-8,CY-outer-13,CX+8,CY-outer-13,fill=GOLD,outline='')
        # pick wear and spare parts
        c.create_text(16,22,text='Знос відмички',fill='#d8d2b2',font=('Segoe UI',9,'bold'),anchor='w')
        c.create_rectangle(16,32,156,40,fill='#0f120f',outline='')
        ratio=s['wear']/s['wear_max']
        c.create_rectangle(16,32,16+140*ratio,40,fill='#ef7a62' if ratio>.7 else '#e0a049',outline='')
        parts=self.game.count('parts')
        c.create_text(16,60,text=f'Відмички: {parts}',fill='#ef7a62' if parts<=1 else '#d8d2b2',font=('Segoe UI',9,'bold'),anchor='w')
        c.create_text(W-16,22,text=f'Поворотів: {s["turned"]}',fill='#d8d2b2',font=('Consolas',10,'bold'),anchor='e')
        if self.flash>0:c.create_rectangle(0,0,W,H,fill='#ef7a62',outline='',stipple='gray25')
        if self.done:c.create_text(CX,H-12,text='ВІДКРИТО',fill='#91d9aa',font=('Segoe UI',16,'bold'))


def w_of(win):
    win.update_idletasks();return max(520,win.winfo_width())
