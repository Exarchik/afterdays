"""Dosimeter minigame: probe hexes, read the needle, mark the hidden source."""
import math
import tkinter as tk
from tkinter import ttk

from visuals import PANEL,TEXT,GOLD,MUTED
from ui.inspection import window
from game.systems.radiation_source import KIND,TITLE

HOT,GOOD='#e56860','#91d9aa'
TERRAIN=('#26342a','#2b3a2e','#2f3b2c','#29372f')
TICKS=(0.1,0.3,1,3,10,30,100)


def reading_color(value):
    return '#c2493d' if value>=12 else '#c9a640' if value>=4 else '#7c8a32' if value>=1.2 else '#4f6b2c'


def needle_angle(value):
    """Logarithmic dial, 0.1–100 µSv/h across 250 degrees."""
    value=max(.1,min(100,value))
    return -125+(math.log10(value)+1)/3*250


class Dosimeter(tk.Frame):
    W,H=900,520

    def __init__(self,parent,app,q):
        super().__init__(parent,bg=PANEL);self.app=app;self.q=q;self.hover=None
        tk.Label(self,text='Клацніть гекс, щоб зробити замір. Що ближче джерело, то вище показник.',bg=PANEL,fg=TEXT,font=('Segoe UI',11)).pack(pady=(8,2))
        tk.Label(self,text='Заміри без обмежень, але кожен додає радіацію — що ближче до джерела, то більше. Замір на самому джерелі означає знахідку.',
                 bg=PANEL,fg=MUTED,wraplength=860).pack(pady=(0,6))
        self.canvas=tk.Canvas(self,width=self.W,height=self.H,bg='#121a15',highlightthickness=0);self.canvas.pack(padx=12)
        self.canvas.bind('<Button-1>',self.click);self.canvas.bind('<Motion>',self.motion)
        self.canvas.bind('<Leave>',lambda e:self.motion(None))
        self.draw()

    # Geometry: odd rows shifted right, as on the world map.
    def layout(self):
        size=self.q['rad_settings']['grid_size'];area_w,area_h=540,450
        radius=min(area_w/((size+.5)*math.sqrt(3)),area_h/(1.5*size+.5))
        width=math.sqrt(3)*radius
        ox=10+(area_w-(size+.5)*width)/2+width/2;oy=10+(area_h-(1.5*size+.5)*radius)/2+radius
        return size,radius,width,ox,oy

    def center(self,x,y):
        size,radius,width,ox,oy=self.layout()
        return ox+x*width+(width/2 if y&1 else 0),oy+y*1.5*radius

    def cell_at(self,px,py):
        size,radius,width,ox,oy=self.layout()
        best=min(((x,y) for y in range(size) for x in range(size)),key=lambda c:math.dist(self.center(*c),(px,py)))
        return best if math.dist(self.center(*best),(px,py))<=radius*.95 else None

    def hexagon(self,cx,cy,r):
        return [v for i in range(6) for v in (cx+r*math.cos(math.radians(60*i-30)),cy+r*math.sin(math.radians(60*i-30)))]

    def probes(self):return {tuple(p['cell']):p['value'] for p in self.q['rad_probes']}

    def draw(self):
        c=self.canvas;c.delete('all');q=self.q;settings=q['rad_settings']
        size,radius,width,ox,oy=self.layout();probes=self.probes();finished=q['status']!='active' or q['progress']>=q['goal']
        c.create_rectangle(4,4,556,516,fill='#151f19',outline='#3a4a3e',width=2)
        for y in range(size):
            for x in range(size):
                cx,cy=self.center(x,y);value=probes.get((x,y))
                fill=reading_color(value) if value is not None else TERRAIN[(x*7+y*13+len(q['id']))%len(TERRAIN)]
                marked=finished and q.get('rad_source')==[x,y]
                outline=GOLD if marked or (self.hover==(x,y) and not finished) else '#0d1310'
                c.create_polygon(self.hexagon(cx,cy,radius*.96),fill=fill,outline=outline,width=3 if marked else 2 if self.hover==(x,y) else 1)
                if value is not None and not marked:
                    c.create_text(cx,cy,text=f'{value:.1f}' if value<10 else f'{value:.0f}',fill='#10150f',font=('Consolas',max(8,int(radius*.32)),'bold'))
                elif value is None:c.create_oval(cx-2,cy-2,cx+2,cy+2,fill='#4b5a42',outline='')
        if finished and q.get('rad_source'):
            cx,cy=self.center(*q['rad_source']);r=radius*.55
            c.create_oval(cx-r,cy-r,cx+r,cy+r,outline='#a4bf55',width=2)
            for a in (0,120,240):
                c.create_arc(cx-r*.85,cy-r*.85,cx+r*.85,cy+r*.85,start=60+a,extent=60,fill='#a4bf55',outline='')
            c.create_oval(cx-r*.22,cy-r*.22,cx+r*.22,cy+r*.22,fill='#121a15',outline='')
        self.draw_device(probes)
        text,color=self.update_controls(finished)
        c.create_line(16,470,544,470,fill='#3a4a3e')
        c.create_text(280,492,text=text,fill=color,font=('Segoe UI',10,'bold'),width=520,justify='center')

    def draw_device(self,probes):
        c=self.canvas;q=self.q;settings=q['rad_settings']
        x0,y0,x1,y1=576,10,890,510
        c.create_rectangle(x0,y0,x1,y1,fill='#33382a',outline='#5b614a',width=2)
        c.create_text((x0+x1)/2,y0+18,text='ДКС-04 · ДОЗИМЕТР',fill='#b8b49a',font=('Segoe UI',9,'bold'))
        # Analogue dial.
        dx0,dy0,dx1,dy1=x0+16,y0+34,x1-16,y0+220
        c.create_rectangle(dx0,dy0,dx1,dy1,fill='#ece4c8',outline='#1d2016',width=2)
        R=100;cx,cy=(dx0+dx1)/2,dy1-64
        def polar(angle,r):
            a=math.radians(angle);return cx+r*math.sin(a),cy-r*math.cos(a)
        for low,high,color in ((0.1,1.2,'#7c8a32'),(1.2,12,'#c9a640'),(12,100,'#c2493d')):
            a,b=needle_angle(low),needle_angle(high)
            c.create_arc(cx-R,cy-R,cx+R,cy+R,start=90-b,extent=b-a,style='arc',outline=color,width=8)
        for t in TICKS:
            a=needle_angle(t);p=polar(a,R-8);s=polar(a,R-18);l=polar(a,R-32)
            c.create_line(*p,*s,fill='#1d2016',width=2)
            c.create_text(*l,text=f'{t:g}',fill='#1d2016',font=('Consolas',8,'bold'))
        c.create_text(cx,cy+26,text='мкЗв/год',fill='#5d5a47',font=('Segoe UI',8))
        last=q['rad_probes'][-1]['value'] if q['rad_probes'] else .12
        tip=polar(needle_angle(last),R-6)
        c.create_line(cx,cy,*tip,fill='#a3271c',width=3,capstyle='round');c.create_oval(cx-7,cy-7,cx+7,cy+7,fill='#1d2016',outline='')
        # Digital readout.
        c.create_rectangle(x0+16,y0+234,x1-16,y0+284,fill='#1d2414',outline='#10140b',width=2)
        c.create_text(x1-24,y0+259,text=f'{last:.2f}',anchor='e',fill='#c9d98a',font=('Consolas',22,'bold'))
        c.create_text(x0+24,y0+259,text='мкЗв/год',anchor='w',fill='#9aa86a',font=('Segoe UI',8))
        # Probes made and received dose.
        used=len(q['rad_probes'])
        c.create_text(x0+18,y0+306,text='Зроблено замірів',anchor='w',fill='#cfcab0',font=('Segoe UI',9))
        c.create_text(x1-18,y0+306,text=str(used),anchor='e',fill='#e2b34a',font=('Consolas',11,'bold'))
        c.create_text(x0+18,y0+332,text='Отримано радіації',anchor='w',fill='#cfcab0',font=('Segoe UI',9))
        c.create_text(x1-18,y0+332,text=f"+{q.get('rad_dose',0)}",anchor='e',fill=HOT,font=('Consolas',11,'bold'))
        # Probe log, newest first.
        c.create_text(x0+18,y0+360,text='Журнал замірів',anchor='w',fill=GOLD,font=('Segoe UI',9,'bold'))
        for n,p in enumerate(reversed(q['rad_probes'][-7:])):
            y=y0+382+n*17;number=used-n
            c.create_text(x0+18,y,text=f"#{number} · гекс {p['cell'][0]+1},{p['cell'][1]+1}",anchor='w',fill=TEXT,font=('Consolas',9))
            c.create_text(x1-18,y,text=f"{p['value']:.2f}",anchor='e',fill=reading_color(p['value']),font=('Consolas',9,'bold'))
        if not q['rad_probes']:c.create_text(x0+18,y0+382,text='Ще немає замірів.',anchor='w',fill=MUTED,font=('Segoe UI',9))

    def update_controls(self,finished):
        if finished:return 'Джерело знайдено! Радіоактивний прилад у рюкзаку — віднесіть його замовнику.',GOOD
        return 'Шукайте гекс із найвищим показником: замір на самому джерелі завершує пошук.',GOLD

    def motion(self,e):
        cell=self.cell_at(e.x,e.y) if e is not None else None
        if cell!=self.hover:self.hover=cell;self.draw()

    def click(self,e):
        cell=self.cell_at(e.x,e.y)
        if cell is None:return
        if self.app.game.probe_radiation(self.q['id'],*cell) is None:return
        self.draw();self.app.refresh()

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
    app.route.pause();win=window(app,q['title']);win.geometry('960x720')
    board=Dosimeter(win,app,q);board.pack(fill='both',expand=True);win.dosimeter=board
