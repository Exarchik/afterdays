"""Elite hunt minigame: sweep the ground with a heavy hand scanner to find one group of prints."""
import math
import random
import time
import tkinter as tk

from PIL import Image,ImageDraw,ImageFilter,ImageTk

from ui.inspection import window
from visuals import PANEL,TEXT,GOLD,MUTED
import game.systems.track_scanner as scan

GOOD,BAD,ON,OFF='#91d9aa','#e56860','#7cf0a4','#9aa39a'
TICK=33
HELP=('Затисніть ліву кнопку миші, щоб увімкнути сканер. Увімкнений він ледь повзе за рукою й витрачає заряд, '
      'зате під лінзою видно відбитки. Вимкнений — рухається вільно й потроху підзаряджається. '
      'На ділянці лише одна група слідів; індикатор сигналу підкаже, чи ви близько.')


def show(app,ident):
    q=app.game.scanner_quest(ident)
    if q:Scanner(app,app.game,q)


def paw(draw,x,y,angle,fill,scale=1.0):
    """A four-toed print pointing along angle."""
    c,s=math.cos(angle),math.sin(angle)
    def at(dx,dy):return x+dx*c-dy*s,y+dx*s+dy*c
    px,py=at(-2*scale,0);r=5.5*scale
    draw.ellipse((px-r,py-r*.9,px+r,py+r*.9),fill=fill)
    for dx,dy in ((6,-6),(9,-2),(9,2.5),(6,6.5)):
        tx,ty=at(dx*scale,dy*scale);t=2.3*scale
        draw.ellipse((tx-t,ty-t,tx+t,ty+t),fill=fill)


def ground(seed):
    """Pre-rendered field and its scanner view (prints only visible through the lens)."""
    rng=random.Random(seed);w,h=scan.WIDTH,scan.HEIGHT
    img=Image.new('RGB',(w,h),(74,66,48));d=ImageDraw.Draw(img)
    for _ in range(2600):
        x,y=rng.uniform(0,w),rng.uniform(0,h);r=rng.uniform(4,26);v=rng.randint(-14,14)
        d.ellipse((x-r,y-r*.7,x+r,y+r*.7),fill=(74+v,66+v,46+v//2))
    img=img.filter(ImageFilter.GaussianBlur(5));d=ImageDraw.Draw(img)
    for _ in range(420):
        x,y=rng.uniform(0,w),rng.uniform(0,h);g=rng.randint(70,110)
        for _ in range(rng.randint(3,7)):
            a=rng.uniform(-2.4,-.7);l=rng.uniform(5,13)
            d.line((x,y,x+math.cos(a)*l,y+math.sin(a)*l),fill=(g-20,g,40),width=1)
    for _ in range(170):
        x,y=rng.uniform(0,w),rng.uniform(0,h);r=rng.uniform(2,7);v=rng.randint(95,140)
        d.ellipse((x-r,y-r*.8,x+r,y+r*.8),fill=(v,v-6,v-18),outline=(50,46,36))
    return img


def scan_view(base,prints,direction):
    view=Image.eval(base.convert('L'),lambda v:min(255,int(v*1.25))).convert('RGB')
    view=Image.merge('RGB',(view.getchannel('R').point(lambda v:v//4),view.getchannel('G'),view.getchannel('B').point(lambda v:v//3)))
    d=ImageDraw.Draw(view)
    for p in prints:paw(d,p['x'],p['y'],direction,(225,255,190),1.15)
    return view


class Scanner:
    def __init__(self,app,game,quest):
        self.app,self.game,self.quest=app,game,quest;self.ident=quest['id']
        self.closed=False;self.timer=None;self.scanning=False;self.located=False;self.blink=0
        s=quest['scanner'];self.target=list(s['lens']);self.last=time.monotonic()
        self.win=window(app,'Сканер слідів');self.win._scanner=self
        sw,sh=self.win.winfo_screenwidth(),self.win.winfo_screenheight()
        w,h=min(scan.WIDTH+40,sw-20),min(scan.HEIGHT+260,sh-60)
        self.win.geometry(f'{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}')
        tk.Label(self.win,text=HELP,bg=PANEL,fg=TEXT,wraplength=w-50,justify='left').pack(padx=16,pady=(10,4))
        self.hud=tk.Canvas(self.win,width=scan.WIDTH,height=54,bg='#141b16',highlightthickness=0);self.hud.pack(pady=(2,4))
        self.canvas=tk.Canvas(self.win,width=scan.WIDTH,height=scan.HEIGHT,bg='#2b281e',highlightthickness=0,cursor='crosshair')
        self.canvas.pack()
        self.base=ground(s['seed']);self.view=scan_view(self.base,s['prints'],s['direction'])
        self.base_tk=ImageTk.PhotoImage(self.base);self.lens_tk=None
        self.mask=Image.new('L',(scan.LENS*2,scan.LENS*2),0)
        ImageDraw.Draw(self.mask).ellipse((0,0,scan.LENS*2-1,scan.LENS*2-1),fill=235)
        self.canvas.create_image(0,0,image=self.base_tk,anchor='nw')
        self.canvas.bind('<Motion>',self.move);self.canvas.bind('<B1-Motion>',self.move)
        self.canvas.bind('<ButtonPress-1>',lambda e:self.press(e,True))
        self.canvas.bind('<ButtonRelease-1>',lambda e:self.press(e,False))
        self.win.bind('<Destroy>',self.destroyed,add='+')
        self.draw();self.schedule()

    # --- input ---
    def move(self,event):self.target=[event.x,event.y]

    def press(self,event,on):
        if self.located:return
        self.target=[event.x,event.y];self.scanning=on

    def destroyed(self,event):
        if event.widget is self.win:
            self.closed=True
            if self.timer:
                try:self.win.after_cancel(self.timer)
                except tk.TclError:pass
            self.timer=None

    # --- loop ---
    def schedule(self):
        if not self.closed and not self.located:self.timer=self.win.after(TICK,self.tick)

    def tick(self):
        if self.timer:
            try:self.win.after_cancel(self.timer)
            except tk.TclError:pass
        self.timer=None
        if self.closed:return
        now=time.monotonic();dt=now-self.last;self.last=now;self.blink+=dt
        result=self.game.scanner_tick(self.ident,dt,self.target,self.scanning)
        if result['empty']:self.scanning=False
        if result['located']:self.finish()
        self.draw();self.schedule()

    def finish(self):
        self.located=True;self.scanning=False
        self.app.refresh()

    # --- drawing ---
    def draw(self):
        c=self.canvas;s=self.quest['scanner'];x,y=s['lens'];L=scan.LENS
        c.delete('dyn')
        if self.scanning:
            box=(int(x)-L,int(y)-L,int(x)+L,int(y)+L)
            patch=self.view.crop(box).convert('RGBA');patch.putalpha(self.mask)
            self.lens_tk=ImageTk.PhotoImage(patch)
            c.create_image(box[0],box[1],image=self.lens_tk,anchor='nw',tags='dyn')
        for p in s['prints']:
            if p['found']:
                c.create_oval(p['x']-11,p['y']-11,p['x']+11,p['y']+11,outline=GOLD,width=2,tags='dyn')
        if self.located:self.draw_result(s)
        else:
            col=ON if self.scanning else OFF
            c.create_oval(x-L,y-L,x+L,y+L,outline=col,width=3,tags='dyn')
            c.create_oval(x-scan.READ_RADIUS,y-scan.READ_RADIUS,x+scan.READ_RADIUS,y+scan.READ_RADIUS,outline=col,dash=(3,5),tags='dyn')
            c.create_line(x-L-8,y,x-L+10,y,fill=col,width=2,tags='dyn');c.create_line(x+L-10,y,x+L+8,y,fill=col,width=2,tags='dyn')
            c.create_line(x,y-L-8,x,y-L+10,fill=col,width=2,tags='dyn');c.create_line(x,y+L-10,x,y+L+8,fill=col,width=2,tags='dyn')
            if not self.scanning:
                tx,ty=self.target
                c.create_text(x,y+L+16,text='вимкнено',fill=OFF,font=('Segoe UI',9),tags='dyn')
            elif abs(self.target[0]-x)+abs(self.target[1]-y)>4:
                tx,ty=self.target
                c.create_line(x,y,tx,ty,fill=ON,dash=(2,6),tags='dyn')
        self.draw_hud(s)

    def draw_result(self,s):
        c=self.canvas;cx,cy=s['center'];a=s['direction']
        c.create_rectangle(0,0,scan.WIDTH,scan.HEIGHT,fill='#101410',stipple='gray50',outline='',tags='dyn')
        x0,y0=cx-math.cos(a)*90,cy-math.sin(a)*90;x1,y1=cx+math.cos(a)*130,cy+math.sin(a)*130
        c.create_line(x0,y0,x1,y1,fill=GOLD,width=5,arrow='last',arrowshape=(22,26,9),tags='dyn')
        for p in s['prints']:
            c.create_oval(p['x']-6,p['y']-6,p['x']+6,p['y']+6,fill=GOLD if p['found'] else MUTED,outline='',tags='dyn')
        top=24 if cy>scan.HEIGHT/2 else scan.HEIGHT-96
        c.create_rectangle(scan.WIDTH/2-300,top,scan.WIDTH/2+300,top+72,fill='#1b2720',outline=GOLD,width=2,tags='dyn')
        c.create_text(scan.WIDTH/2,top+22,text='Сліди прочитано!',fill=GOLD,font=('Segoe UI',14,'bold'),tags='dyn')
        c.create_text(scan.WIDTH/2,top+50,text='Лігво елітного мутанта позначено на мапі. Ідіть туди й використайте «Пошук».',
                      fill=TEXT,font=('Segoe UI',10),tags='dyn')

    def draw_hud(self,s):
        h=self.hud;h.delete('all');cfg=s['settings'];e=s['energy']
        h.create_text(14,16,text='Заряд',fill=MUTED,anchor='w',font=('Segoe UI',9))
        h.create_rectangle(70,8,290,24,outline='#3c4a40',fill='#0d120f')
        col=GOOD if e>35 else GOLD if e>12 else BAD
        h.create_rectangle(71,9,71+218*e/100,23,outline='',fill=col)
        h.create_text(300,16,text=f'{e:.0f}%',fill=TEXT,anchor='w',font=('Segoe UI',9,'bold'))
        signal=self.game.scanner_signal(self.quest) if not self.located else 1.0
        h.create_text(14,40,text='Сигнал',fill=MUTED,anchor='w',font=('Segoe UI',9))
        for i in range(10):
            lit=self.scanning and signal*10>i
            h.create_rectangle(70+i*22,33,88+i*22,47,outline='#3c4a40',fill=(ON if i<6 else GOLD if i<9 else BAD) if lit else '#0d120f')
        period=max(.08,.9-signal*.8)
        led=self.scanning and signal>0 and (self.blink%period)<period/2
        h.create_oval(300,32,316,48,fill=ON if led else '#203026',outline='#3c4a40')
        h.create_text(470,16,text=f'Відбитків прочитано: {s["read"]}/{cfg["needed"]}',fill=GOLD,anchor='w',font=('Segoe UI',11,'bold'))
        if self.located:status,tone='Напрям знайдено — лігво на мапі.',GOOD
        elif e<=0:status,tone='Заряд вичерпано — відпустіть кнопку, щоб підзарядити.',BAD
        elif self.scanning:status,tone='Сканування… сканер важкий, ведіть повільно.',ON
        else:status,tone='Сканер вимкнено: підзаряджається. Затисніть ЛКМ, щоб сканувати.',MUTED
        h.create_text(470,40,text=status,fill=tone,anchor='w',font=('Segoe UI',9))
