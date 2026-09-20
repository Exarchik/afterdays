"""Quest-integrated version of the user's weighted, returning-scrap minigame."""
import random,time
from types import SimpleNamespace
import tkinter as tk
from inspection_ui import window
from visuals import PANEL,TEXT,GOLD
from junk_art import ScrapArt
import junk_physics as physics
from i18n import t as tr


def show(app,ident):
    g=app.game;q=g.junk_quest(ident)
    if q:Junkyard(app,g,q)


class Junkyard(ScrapArt):
    def __init__(self,app,game,quest):
        self.app,self.game,self.quest=app,game,quest;self.ident=quest['id']
        self.closed=False;self.timer=None;self.drag=None;self.pointer=(0,0);self.offset=(0,0)
        self.scale=1;self.ox=self.oy=0;self.last_tick=time.monotonic()
        self.win=window(app,tr('scav.junkyard'))
        w=min(1000,self.win.winfo_screenwidth()-40);h=min(800,self.win.winfo_screenheight()-80)
        self.win.geometry(f'{w}x{h}+{max(0,(self.win.winfo_screenwidth()-w)//2)}+{max(0,(self.win.winfo_screenheight()-h)//2)}')
        tk.Label(self.win,text=tr('scav.junk_help'),bg=PANEL,fg=TEXT,wraplength=w-40,justify='left').pack(padx=16,pady=12)
        self.status=tk.Label(self.win,bg=PANEL,fg=GOLD,wraplength=w-40);self.status.pack(pady=5)
        self.canvas=tk.Canvas(self.win,bg='#343b2c',highlightthickness=0,height=560)
        self.canvas.pack(fill='both',expand=True,padx=12,pady=10)
        self.canvas.bind('<Configure>',self.draw)
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<Motion>',self.motion);self.canvas.bind('<B1-Motion>',self.motion)
        self.canvas.bind('<Button-3>',self.collect_right)
        self.win.bind('<ButtonRelease-1>',self.release,add='+')
        self.win.bind('<FocusOut>',self.focus_out,add='+')
        self.win.bind('<Destroy>',self.destroyed,add='+')
        self.draw();self.timer=self.win.after(16,self.tick)

    def coordinates(self,event):return ((event.x-self.ox)/self.scale,(event.y-self.oy)/self.scale)

    def update_status(self,message=''):
        q=self.quest
        value=tr('scav.junk_progress',count=q['progress'],goal=q['goal'])
        value+=tr('scav.return_giver') if self.game.quest_ready(q) else ''
        self.status.config(text=value+(' · '+message if message else ''))

    def draw(self,event=None):
        if self.closed:return
        c=self.canvas;c.delete('all');c._junk_refs=[]
        # Draw in the source game's coordinate space, then fit uniformly to this window.
        self.scale=max(.01,min(c.winfo_width()/physics.WIDTH,c.winfo_height()/physics.HEIGHT))
        self.ox=(c.winfo_width()-physics.WIDTH*self.scale)/2;self.oy=(c.winfo_height()-physics.HEIGHT*self.scale)/2
        rng=random.Random(81)
        for _ in range(460):
            x,y=rng.randrange(physics.WIDTH),rng.randrange(physics.HEIGHT)
            c.create_oval(x,y,x+2,y+2,fill=rng.choice(['#4c503d','#454936','#292f26']),outline='')
        # Targets use scalable vector icons and tags for removal on collection.
        for obj in self.quest['junk_objects']:
            if obj['found']:continue
            if obj['kind']=='debris':
                self.draw_scrap(SimpleNamespace(tag=obj['id'],name=physics.MATERIALS[obj['material']][0],**{k:obj[k] for k in ('x','y','points','color')}))
            else:
                x,y=obj['x'],obj['y'];color=GOLD if obj['kind']=='target' else '#8caf91'
                before=set(c.find_all());c.create_oval(x,y,x+60,y+60,fill='#243126',outline=color,width=2)
                # Native inventory images cannot be scaled by Canvas.scale: use vector symbols here.
                from junk_find_art import target_icon
                target_icon(c,x+30,y+30,'chip' if obj['kind']=='target' else 'wire' if obj['kind']=='parts' else 'scrap' if obj['kind']=='fragments' else 'ammo',color)
                for item in set(c.find_all())-before:c.addtag_withtag(obj['id'],item)
        c.scale('all',0,0,self.scale,self.scale);c.move('all',self.ox,self.oy)
        if self.drag:c.itemconfigure('body'+self.drag,outline=GOLD,width=3)
        self.update_status()

    def press(self,event):
        self.canvas.focus_set();self.pointer=self.coordinates(event)
        obj=self.game.junk_top(self.quest,*self.pointer)
        if obj is None:return
        if obj['kind']!='debris':self.collect(*self.pointer);return
        self.drag=obj['id'];self.offset=(obj['x']-self.pointer[0],obj['y']-self.pointer[1])
        self.quest['junk_objects'].remove(obj);self.quest['junk_objects'].append(obj)
        self.canvas.tag_raise(obj['id']);self.canvas.itemconfigure('body'+obj['id'],outline=GOLD,width=3)
        self.canvas.config(cursor='fleur');self.update_status(tr('scav.junk_drag'))

    def motion(self,event):self.pointer=self.coordinates(event)

    def release(self,event=None):
        if self.closed:return
        if self.drag:self.canvas.itemconfigure('body'+self.drag,outline='#222a23',width=2)
        self.drag=None;self.canvas.config(cursor='')

    def focus_out(self,event):
        if not self.closed:self.win.after_idle(self.check_focus)

    def check_focus(self):
        if not self.closed and self.win.focus_displayof() is None:self.release()

    def collect_right(self,event):self.collect(*self.coordinates(event))

    def collect(self,x,y):
        obj=self.game.junk_top(self.quest,x,y)
        if not obj or obj['kind']=='debris':self.update_status(tr('scav.junk_blocked'));return
        if self.game.junk_collect(self.ident,x,y):
            self.canvas.delete(obj['id']);self.update_status();self.app.refresh()

    def tick(self):
        self.timer=None
        if self.closed:return
        now=time.monotonic();dt=min(.05,now-self.last_tick);self.last_tick=now
        destination=(self.pointer[0]+self.offset[0],self.pointer[1]+self.offset[1]) if self.drag else None
        for ident,dx,dy in self.game.junk_tick(self.ident,dt,self.drag,destination):
            self.canvas.move(ident,dx*self.scale,dy*self.scale)
        self.timer=self.win.after(16,self.tick)

    def destroyed(self,event):
        if event.widget is not self.win:return
        self.closed=True;self.drag=None
        if self.timer is not None:
            try:self.win.after_cancel(self.timer)
            except tk.TclError:pass
            self.timer=None
