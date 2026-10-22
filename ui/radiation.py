"""Dosimeter minigame: sweep the probe over the plot, lift every source, find the lost device."""
import math
import random
import time
import tkinter as tk
from tkinter import ttk

from visuals import PANEL,TEXT,GOLD,MUTED
from ui.inspection import window
from game.systems import radiation_source as rs
from game.systems.radiation_source import KIND,TITLE

HOT,GOOD='#e56860','#91d9aa'
TICKS=(0.1,0.3,1,3,10,30,100)
DIG_SECONDS=1.1
TICK_MS=40
COLORS={'device':'#a4bf55','cs137':'#e8b04a','co60':'#5ec4d6','sr90':'#e07aa8','ra226':'#b49cf0'}


def reading_color(value):
    return '#c2493d' if value>=12 else '#c9a640' if value>=4 else '#7c8a32' if value>=1.2 else '#4f6b2c'


def needle_angle(value):
    """Logarithmic dial, 0.1–100 µSv/h across 250 degrees."""
    value=max(.1,min(100,value))
    return -125+(math.log10(value)+1)/3*250


# Ground of the plot: world tiles of the quest location's terrain, with ruins and rocks mixed in.
GROUND={'forest':((1,8),(1,8),(0,8),(2,3)),'cliff':((4,8),(4,8),(0,8),(2,3)),'ruin':((2,3),(0,8),(0,8),(4,8)),
        'city':((2,3),(0,8),(0,8),(2,3)),'water':((0,8),(0,8),(1,8),(4,8))}
DEFAULT_GROUND=((0,8),(0,8),(0,8),(1,8),(2,3),(4,8))


def ground_image(game,q,width,height):
    from PIL import Image,ImageDraw,ImageChops
    import world_hex_art
    x,y=q.get('pos') or (0,0)
    kind=game.world[y][x] if 0<=y<len(game.world) and 0<=x<len(game.world[0]) else 'waste'
    pool=GROUND.get(kind,DEFAULT_GROUND)+DEFAULT_GROUND
    rng=random.Random('radiation-ground:'+str(q['id']))
    radius=height/5.2;tw,th=round(math.sqrt(3)*radius),round(2*radius)
    image=Image.new('RGBA',(width,height),(42,40,31,255))
    mask=Image.new('L',(tw,th),0)
    ImageDraw.Draw(mask).polygon([(tw/2,0),(tw-1,th/4),(tw-1,th*3/4),(tw/2,th-1),(0,th*3/4),(0,th/4)],fill=255)
    rows=int(height/(1.5*radius))+2;cols=int(width/tw)+2
    for row in range(-1,rows):
        for col in range(-1,cols):
            r,count=rng.choice(pool);tile=world_hex_art._source_tile(r,rng.randrange(count)).resize((tw,th),Image.Resampling.LANCZOS)
            tile.putalpha(ImageChops.multiply(tile.getchannel('A'),mask))
            image.alpha_composite(tile,(round(col*tw+(tw/2 if row&1 else 0)-tw/2),round(row*1.5*radius-radius)))
    # Soft vignette: the plot fades into the wasteland.
    shade=Image.new('L',(width,height),0);draw=ImageDraw.Draw(shade)
    for i in range(24):
        draw.rectangle((i,i,width-1-i,height-1-i),outline=int(140*(1-i/24)**2))
    dark=Image.new('RGBA',(width,height),(8,10,8,0));dark.putalpha(shade)
    image.alpha_composite(dark)
    return image.convert('RGB')


class Dosimeter(tk.Frame):
    W,H=620,385
    DW,DH=290,470

    def __init__(self,parent,app,q):
        super().__init__(parent,bg=PANEL);self.app=app;self.q=q
        self.probe=None;self.inside=False;self.dig=None;self.value=rs.BACKGROUND;self.shown=rs.BACKGROUND
        self.last=time.monotonic();self.click_at=0;self.closed=False
        w,h=rs.area(q['rad_settings']);self.scale=self.W/w;self.H=round(h*self.scale)
        self.bg0=self.site_background() or 1
        tk.Label(self,text='Ведіть щуп по землі: стрілка й лічильник реагують одразу. Затисніть кнопку миші на місці, щоб копати.',
                 bg=PANEL,fg=TEXT,font=('Segoe UI',11)).pack(pady=(14,8))
        body=tk.Frame(self,bg=PANEL);body.pack(padx=12)
        left=tk.Frame(body,bg=PANEL);left.pack(side='left',anchor='n')
        self.canvas=tk.Canvas(left,width=self.W,height=self.H,bg='#121a15',highlightthickness=1,highlightbackground='#3a4a3e',cursor='none')
        self.canvas.pack()
        from PIL import ImageTk
        self.ground=ImageTk.PhotoImage(ground_image(app.game,q,self.W,self.H),master=self.canvas)
        self.canvas.create_image(0,0,image=self.ground,anchor='nw')
        self.canvas.bind('<Motion>',self.motion);self.canvas.bind('<Leave>',self.leave)
        self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<ButtonRelease-1>',self.release)
        row=tk.Frame(left,bg=PANEL);row.pack(fill='x',pady=(8,0))
        self.dig_button=ttk.Button(row,text='Копати тут',command=lambda:self.start_dig(button=True));self.dig_button.pack(side='left')
        self.message=tk.Label(left,text='Поки щуп у полі, набігає радіація. Сильні джерела засвічують слабкі: вилучайте все, що фонить, і знайдете прилад.',bg=PANEL,fg=GOLD,font=('Segoe UI',10,'bold'),wraplength=self.W,justify='left',anchor='w')
        self.message.pack(fill='x',pady=(8,0))
        self.device=tk.Canvas(body,width=self.DW,height=self.DH,bg=PANEL,highlightthickness=0);self.device.pack(side='left',anchor='n',padx=(14,0))
        self.draw_field();self.draw_device_static();self.update_device()
        self.bind('<Destroy>',lambda e:setattr(self,'closed',True) if e.widget is self else None)
        self.after(TICK_MS,self.tick)

    # --- state helpers ---------------------------------------------------
    def finished(self):return self.q['status']!='active' or self.q['progress']>=self.q['goal']

    def to_field(self,px,py):return px/self.scale,py/self.scale

    def to_screen(self,x,y):return x*self.scale,y*self.scale

    def site_background(self):
        w,h=rs.area(self.q['rad_settings']);total=n=0
        for i in range(12):
            for j in range(8):total+=rs.reading(self.q,(i+.5)*w/12,(j+.5)*h/8);n+=1
        return total/n

    def say(self,text,color=GOLD):self.message.configure(text=text,fg=color)

    # --- input ------------------------------------------------------------
    def motion(self,e):
        self.probe=(e.x,e.y);self.inside=True
        if self.dig and not self.dig['button'] and math.dist(self.probe,self.dig['at'])>12:self.dig=None
        self.draw_probe()

    def leave(self,e):
        self.inside=False
        if self.dig and not self.dig['button']:self.dig=None
        self.draw_probe()

    def press(self,e):self.probe=(e.x,e.y);self.inside=True;self.start_dig()

    def release(self,e):
        if self.dig and not self.dig['button']:self.dig=None;self.draw_probe()

    def start_dig(self,button=False):
        if self.finished() or self.probe is None or self.dig:return
        self.dig=dict(t0=time.monotonic(),at=self.probe,button=button);self.draw_probe()

    def finish_dig(self):
        at=self.dig['at'];self.dig=None
        result=self.app.game.dig_radiation(self.q['id'],*self.to_field(*at))
        if result is None:return
        if result['result']=='device':
            self.say(f"Ось він! {rs.DEVICE_NAME} у рюкзаку — віднесіть його замовнику. Вилучено сторонніх джерел: {self.app.game.radiation_cleared(self.q)}.",GOOD)
        elif result['result']=='isotope':
            self.say(f"Дістали: {result['name']}. Не те, що шукали, — у свинцевий контейнер. Фон ділянки впав.",GOLD)
        else:
            near=self.value>=4
            self.say(('Порожньо, але фонить поруч.' if near else 'Порожньо.')+(f" +{result['dose']} радіації." if result['dose'] else ''),HOT if result['dose'] else MUTED)
        self.draw_field();self.update_device();self.app.refresh()

    # --- loop -----------------------------------------------------------------
    def tick(self):
        if self.closed or not self.winfo_exists():return
        now=time.monotonic();dt=min(rs.MAX_SWEEP,now-self.last);self.last=now
        g=self.app.game;before=self.q.get('rad_dose',0)
        if self.probe and (self.inside or self.dig) and not self.finished():
            value=g.radiation_sweep(self.q['id'],*self.to_field(*self.probe),dt)
            self.value=(value if value is not None else rs.BACKGROUND)*random.uniform(.96,1.04)
        else:self.value=.2 if self.finished() else rs.BACKGROUND
        self.shown+=(self.value-self.shown)*min(1,dt*(9 if self.value>self.shown else 4))
        if random.random()<min(70,.5+self.value*1.6)*dt:self.click_at=now
        if self.dig and now-self.dig['t0']>=DIG_SECONDS:self.finish_dig()
        if self.q.get('rad_dose',0)!=before:self.app.refresh()
        if self.closed or not self.winfo_exists():return
        self.draw_probe();self.update_device()
        self.after(TICK_MS,self.tick)

    # --- drawing: field ----------------------------------------------------------
    def draw_field(self):
        c=self.canvas;c.delete('field')
        for x,y in self.q.get('rad_holes',[]):
            px,py=self.to_screen(x,y)
            c.create_oval(px-13,py-7,px+13,py+7,fill='#1c140c',outline='#78603f',width=2,tags='field')
        for s in self.q['rad_sources']:
            if not s['found']:continue
            px,py=self.to_screen(s['x'],s['y']);r=15 if s['kind']=='device' else 11;color=COLORS.get(s['kind'],GOLD)
            c.create_oval(px-r-4,py-r-4,px+r+4,py+r+4,fill='#10150f',outline='',tags='field')
            for a in (0,120,240):c.create_arc(px-r,py-r,px+r,py+r,start=60+a,extent=60,fill=color,outline='',tags='field')
            c.create_oval(px-r*.22,py-r*.22,px+r*.22,py+r*.22,fill='#10150f',outline='',tags='field')
            if s['kind']=='device':c.create_oval(px-r-9,py-r-9,px+r+9,py+r+9,outline=color,width=2,tags='field')

    def draw_probe(self):
        c=self.canvas;c.delete('probe')
        if self.probe is None or self.finished() and not self.inside:return
        px,py=self.probe;dim=not self.inside and not self.dig
        handle='#555a4b' if dim else '#3d4235';ring='#8b8873' if dim else '#d8d2b4'
        c.create_line(px+5,py+7,px+60,py+56,fill='#1a1d16',width=6,tags='probe')
        c.create_line(px,py,px+55,py+50,fill=handle,width=4,tags='probe')
        lit=time.monotonic()-self.click_at<.05 and not dim
        c.create_oval(px-18,py-9,px+18,py+9,outline=ring,width=3,fill='#e8cf6a' if lit else '',stipple='gray50' if lit else '',tags='probe')
        if self.dig:
            k=min(1,(time.monotonic()-self.dig['t0'])/DIG_SECONDS)
            c.create_arc(px-26,py-26,px+26,py+26,start=90,extent=-359.9*k,style='arc',outline=GOLD,width=4,tags='probe')

    # --- drawing: device -----------------------------------------------------------
    def draw_device_static(self):
        c=self.device;x0,y0,x1,y1=4,4,self.DW-4,self.DH-4
        c.create_rectangle(x0,y0,x1,y1,fill='#33382a',outline='#5b614a',width=2)
        c.create_text((x0+x1)/2,y0+18,text='ДКС-04 · ДОЗИМЕТР',fill='#b8b49a',font=('Segoe UI',9,'bold'))
        dx0,dy0,dx1,dy1=x0+14,y0+34,x1-14,y0+200
        c.create_rectangle(dx0,dy0,dx1,dy1,fill='#ece4c8',outline='#1d2016',width=2)
        R=96;cx,cy=(dx0+dx1)/2,dy1-52;self.dial=(cx,cy,R)
        for low,high,color in ((0.1,1.2,'#7c8a32'),(1.2,4,'#b9b13a'),(4,12,'#c9a640'),(12,100,'#c2493d')):
            a,b=needle_angle(low),needle_angle(high)
            c.create_arc(cx-R,cy-R,cx+R,cy+R,start=90-b,extent=b-a,style='arc',outline=color,width=8)
        for t in TICKS:
            a=needle_angle(t);p=self.polar(a,R-8);s=self.polar(a,R-18);l=self.polar(a,R-32)
            c.create_line(*p,*s,fill='#1d2016',width=2)
            c.create_text(*l,text=f'{t:g}',fill='#1d2016',font=('Consolas',8,'bold'))
        c.create_text(cx,cy+24,text='мкЗв/год',fill='#5d5a47',font=('Segoe UI',8))
        c.create_rectangle(x0+14,y0+212,x1-14,y0+262,fill='#1d2414',outline='#10140b',width=2)
        c.create_text(x0+22,y0+237,text='мкЗв/год',anchor='w',fill='#9aa86a',font=('Segoe UI',8))
        c.create_text(x0+44,y0+290,text='лічильник',anchor='w',fill='#cfcab0',font=('Segoe UI',9))
        c.create_text(x0+18,y0+322,text='Фон ділянки',anchor='w',fill='#cfcab0',font=('Segoe UI',9))
        c.create_rectangle(x0+120,y0+315,x1-18,y0+329,fill='#1a2018',outline='#10140b')
        c.create_text(x0+18,y0+354,text='Контейнер',anchor='w',fill='#cfcab0',font=('Segoe UI',9))
        c.create_text(x0+18,y0+388,text='Отримано радіації',anchor='w',fill='#cfcab0',font=('Segoe UI',9))
        c.create_text((x0+x1)/2,y1-26,text='Свинцевий контейнер гасить вилучене.',fill=MUTED,font=('Segoe UI',8))

    def polar(self,angle,r):
        cx,cy,_=self.dial;a=math.radians(angle);return cx+r*math.sin(a),cy-r*math.cos(a)

    def update_device(self):
        c=self.device;c.delete('live');x0,y0,x1=4,4,self.DW-4
        cx,cy,R=self.dial;tip=self.polar(needle_angle(self.shown),R-6)
        c.create_line(cx,cy,*tip,fill='#a3271c',width=3,capstyle='round',tags='live')
        c.create_oval(cx-7,cy-7,cx+7,cy+7,fill='#1d2016',outline='',tags='live')
        hot=self.shown>=12 and not self.finished()
        c.create_text(x1-22,y0+237,text=f'{self.shown:.2f}',anchor='e',fill='#ff7a64' if hot else '#c9d98a',font=('Consolas',22,'bold'),tags='live')
        lit=time.monotonic()-self.click_at<.05
        c.create_oval(x0+20,y0+281,x0+36,y0+297,fill='#ffde6a' if lit else '#4a4430',outline='#22231c',width=2,tags='live')
        k=max(0,min(1,self.site_background()/self.bg0))
        color='#c9a640' if k>.5 else '#b9b13a' if k>.2 else '#7c8a32'
        if k>0:c.create_rectangle(x0+121,y0+316,x0+121+(x1-18-x0-121)*k,y0+328,fill=color,outline='',tags='live')
        found=sorted((s for s in self.q['rad_sources'] if s['found']),key=lambda s:s.get('order',0))
        for i in range(len(self.q['rad_sources'])):
            fill=COLORS.get(found[i]['kind'],GOLD) if i<len(found) else '#3a3e31'
            c.create_rectangle(x0+120+i*24,y0+346,x0+136+i*24,y0+362,fill=fill,outline='#1d2016',tags='live')
        c.create_text(x1-18,y0+388,text=f"+{self.q.get('rad_dose',0)}",anchor='e',fill=HOT,font=('Consolas',11,'bold'),tags='live')
        if self.finished():
            c.create_text((x0+x1)/2,y0+420,text='Прилад у рюкзаку',fill=GOOD,font=('Segoe UI',10,'bold'),tags='live')
        self.dig_button.state(['disabled'] if self.finished() or self.probe is None else ['!disabled'])


def show(app,ident=None):
    g=app.game
    quests=[q for q in g.quests if q['kind']==KIND and g.radiation_available(q)]
    if not quests:return
    if ident is None and len(quests)>1:
        app.route.pause();win=window(app,TITLE)
        for q in quests:
            def pick(ident=q['id']):win.close_dialog();show(app,ident)
            ttk.Button(win,text=q['title'],command=pick).pack(fill='x',padx=15,pady=8)
        return
    q=next((q for q in quests if ident is None or q['id']==ident),None)
    if not q:return
    q=g.radiation_quest(q['id'])
    app.route.pause();win=window(app,q['title']);win.geometry('970x700')
    board=Dosimeter(win,app,q);board.pack(fill='both',expand=True);win.dosimeter=board
