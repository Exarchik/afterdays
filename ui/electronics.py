"""Drag circuit modules onto matching sockets and rotate with the right button."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk,ImageOps,ImageFilter,ImageChops
from visuals import PANEL,TEXT,GOLD
from ui.inspection import window
from game.systems.electronics import KIND,TITLE
SOURCE=Path(__file__).resolve().parents[1]/'assets/custom/sources/chemes.png'
COLORS=('#e5ba61','#69d4db','#e39a82','#b0d47b')

def prepare_art(root):
    if hasattr(root,'_circuit_board_art'):return root._circuit_board_art
    photos={};pads={}
    with Image.open(SOURCE) as raw:
        source=raw.convert('RGBA')
        for i in range(16):
            x,y=i%4,i//4
            piece=source.crop((round(x*source.width/4),round(y*source.height/4),round((x+1)*source.width/4),round((y+1)*source.height/4)))
            bbox=piece.getbbox()
            if bbox:piece=piece.crop(bbox)
            fit=ImageOps.contain(piece,(130,130),Image.Resampling.LANCZOS)
            tile=Image.new('RGBA',(150,150));tile.alpha_composite(fit,((150-fit.width)//2,(150-fit.height)//2))
            alpha=tile.getchannel('A')
            # Contacts sit on the actual visible edge of this module, not on a generic rectangle.
            points=[]
            for number,(fraction,right) in enumerate(((.30,False),(.65,False),(.40,True),(.75,True))):
                yy=(150-fit.height)//2+round(fit.height*fraction)
                xs=[xx for xx in range(150) if alpha.getpixel((xx,yy))>180]
                xx=(max(xs)+2 if right else min(xs)-2) if xs else (142 if right else 8)
                points.append((max(4,min(146,xx)),yy))
            for angle in range(4):
                rotated=tile.rotate(-90*angle)
                contacts=[]
                for xx,yy in points:
                    for _ in range(angle):xx,yy=150-yy,xx
                    contacts.append((xx,yy))
                pads[i,angle]=contacts
                mask=rotated.getchannel('A').point(lambda a:255 if a>180 else 0)
                mask=mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
                edge=ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)),mask)
                socket=Image.new('RGBA',(150,150),(220,231,205,0));socket.putalpha(edge)
                for size in (100,150):photos[i,angle,size]=ImageTk.PhotoImage(rotated.resize((size,size),Image.Resampling.LANCZOS),master=root)
                photos[i,angle,'socket']=ImageTk.PhotoImage(socket,master=root)
    root._circuit_board_art=(photos,pads);return photos,pads

class CircuitBoard(tk.Frame):
    def __init__(self,parent,app,q):
        super().__init__(parent,bg=PANEL);self.app=app;self.q=q;self.drag=None;self.mouse=(0,0)
        self.photos,self.pads=prepare_art(app.root)
        tk.Label(self,text='Перетягніть модулі зліва на клеми плати. ПКМ — поворот на 90°.',bg=PANEL,fg=TEXT,font=('Segoe UI',11)).pack(pady=(8,3))
        tk.Label(self,text='Біла розмітка й золоті клеми мають збігатися з модулем. Квадратна клема — контакт 1. Модуль можна повернути в лоток зліва.',bg=PANEL,fg='#a4b2a4',wraplength=890).pack(pady=(0,8))
        self.canvas=tk.Canvas(self,width=900,height=505,bg='#10251e',highlightthickness=0);self.canvas.pack(padx=12)
        self.status=tk.Label(self,bg=PANEL,fg=GOLD);self.status.pack(pady=8)
        self.power=ttk.Button(self,text='Увімкнути схему',command=self.check);self.power.pack(pady=5)
        self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<B1-Motion>',self.motion)
        self.canvas.bind('<ButtonRelease-1>',self.release);self.canvas.bind('<Button-3>',self.rotate)
        self.draw()

    def contacts(self,piece,angle,x,y,size):
        c=self.canvas
        for number,(px,py) in enumerate(self.pads[piece,angle]):
            xx=x+(px-75)*size/150;yy=y+(py-75)*size/150
            r=4 if size==100 else 5
            shape=c.create_rectangle if number==0 else c.create_oval
            shape(xx-r,yy-r,xx+r,yy+r,fill='#d4a94b',outline='#f5d68a',width=1)
            c.create_oval(xx-2,yy-2,xx+2,yy+2,fill='#092d20',outline='#946c2c')
            if number==0:c.create_text(xx+8,yy-7,text='1',fill='#e2ead2',font=('Segoe UI',6,'bold'))

    def module(self,piece,x,y,size):
        angle=self.q['circuit_rotations'][str(piece)]
        self.canvas.create_image(x,y,image=self.photos[piece,angle,size])
        self.contacts(piece,angle,x,y,size)

    def draw(self):
        c=self.canvas;c.delete('all');q=self.q;self.hits=[];self.sockets=[]
        c.create_rectangle(8,8,278,497,fill='#1b2b24',outline='#536852',width=2)
        c.create_text(143,27,text='ДОСТУПНІ МІКРОСХЕМИ',fill=GOLD,font=('Segoe UI',10,'bold'))
        # One continuous solder-mask board with printed tracks and mounting holes.
        c.create_rectangle(293,8,892,497,fill='#075333',outline='#a1b98d',width=3)
        c.create_rectangle(301,16,884,489,outline='#2d8b57',width=2)
        c.create_text(590,29,text='AFTERDAYS  /  CONTROL PCB  /  REV.02',fill='#d4e8c9',font=('Segoe UI',9,'bold'))
        centers=[(402+i%3*190,156+i//3*218) for i in range(6)]
        for i,(x,y) in enumerate(centers):
            p=q['circuit_target'][i];angle=q['circuit_angles'][i]
            for n,(px,py) in enumerate(self.pads[p,angle]):
                xx=x+px-75;yy=y+py-75
                # Each track ends on an actual socket contact.
                side=-1 if px<75 else 1
                lane=x+side*(80+n*3)
                bus=(54+n*6) if i<3 else (467-n*6)
                end=324+n*14 if i<3 else 830-n*14
                points=(xx,yy,lane,yy,lane,bus,end,bus)
                c.create_line(*points,fill='#063c27',width=5)
                c.create_line(*points,fill='#20854a',width=2)
                c.create_oval(end-3,bus-3,end+3,bus+3,fill='#cca54e',outline='#efcf85')
                c.create_oval(end-1,bus-1,end+1,bus+1,fill='#133e29',outline='')
        for x in (313,872):
            for y in (28,477):
                c.create_oval(x-10,y-10,x+10,y+10,fill='#c7a24b',outline='#f1d386',width=2)
                c.create_oval(x-6,y-6,x+6,y+6,fill='#15251d',outline='#877a48')
        for i,x in enumerate((368,480,592,704,816)):
            y=274
            c.create_line(x-30,y,x+30,y,fill='#267d47',width=3)
            c.create_rectangle(x-15,y-6,x+15,y+6,outline='#d5e4cc',width=1)
            for xx in (x-24,x+24):
                c.create_oval(xx-4,y-4,xx+4,y+4,fill='#cfa34b',outline='#f0d28b')
                c.create_oval(xx-2,y-2,xx+2,y+2,fill='#0c3926',outline='')
            c.create_text(x,y-15,text=f'R{i+1}',fill='#d5e4cc',font=('Segoe UI',7))
        for i,(x,y) in enumerate(centers):
            p=q['circuit_target'][i];angle=q['circuit_angles'][i]
            self.sockets.append((x-87,y-87,x+87,y+87))
            c.create_image(x,y,image=self.photos[p,angle,'socket']);self.contacts(p,angle,x,y,150)
            c.create_text(x,y+100,text=f'U{i+1}',fill='#dbe8ce',font=('Segoe UI',9))
            installed=q['circuit_slots'][i]
            if installed is not None and installed!=self.drag:
                self.module(installed,x,y,150);self.hits.append((installed,(x-82,y-82,x+82,y+82)))
        tray=[p for p in q['circuit_inventory'] if p not in q['circuit_slots']]
        for i,p in enumerate(tray):
            x=77+i%2*132;y=116+i//2*151
            c.create_rectangle(x-60,y-62,x+60,y+62,fill='#20352a',outline='#415b45')
            if p!=self.drag:self.module(p,x,y,100)
            self.hits.append((p,(x-60,y-62,x+60,y+62)))
        if self.drag is not None:self.module(self.drag,*self.mouse,150)
        count=sum(p is not None for p in q['circuit_slots'])
        self.status.config(text='Схема працює! Поверніться до замовника.' if q.get('circuit_checked') else f'Встановлено модулів: {count}/6 · живлення вимкнено')
        self.power.config(state='normal' if count==6 and not q.get('circuit_checked') else 'disabled')

    def hit(self,x,y):return next((p for p,(a,b,r,d) in reversed(self.hits) if a<=x<=r and b<=y<=d),None)
    def press(self,e):
        if self.q.get('circuit_checked'):return
        self.drag=self.hit(e.x,e.y);self.mouse=(e.x,e.y);self.draw()
    def motion(self,e):
        if self.drag is not None:self.mouse=(e.x,e.y);self.draw()
    def release(self,e):
        if self.drag is None:return
        slot=next((i for i,(a,b,r,d) in enumerate(self.sockets) if a<=e.x<=r and b<=e.y<=d),None)
        if slot is not None or 8<=e.x<=278:
            self.app.game.place_circuit(self.q['id'],self.drag,slot)
        self.drag=None;self.draw()
    def rotate(self,e):
        piece=self.drag if self.drag is not None else self.hit(e.x,e.y)
        if piece is not None:
            self.app.game.rotate_circuit(self.q['id'],piece);self.draw()
        return 'break'
    def check(self):
        if self.app.game.check_circuits(self.q['id']):self.draw();self.app.refresh()
        else:self.status.config(text='Контакти не збігаються. Перевірте роз’єми й поворот модулів.',fg='#edb477')

def show(app,ident=None):
    g=app.game
    quests=[q for q in g.quests if q['kind']==KIND and g.electronics_available(q) and not q.get('circuit_checked')]
    if not quests:return
    if ident is None and len(quests)>1:
        app.route.pause();win=window(app,TITLE)
        for q in quests:
            def pick(ident=q['id']):win.close_dialog();show(app,ident)
            ttk.Button(win,text=q['title'],command=pick).pack(fill='x',padx=15,pady=8)
        return
    q=next((q for q in quests if ident is None or q['id']==ident),None)
    if not q:return
    app.route.pause();win=window(app,q['title']);win.geometry('960x740')
    board=CircuitBoard(win,app,q);board.pack(fill='both',expand=True);win.circuit_board=board
