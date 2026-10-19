"""Drag circuit modules onto the contact pads of the board; right button or R rotates by 90°."""
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk
from visuals import PANEL,TEXT,GOLD
from ui.inspection import window
import circuit_art
from game.systems.electronics import KIND,TITLE,SLOTS,contacts_at,pads

W,H=900,505
TRAY=(8,8,278,497)
CENTERS=[(402+i%3*190,148+i//3*206) for i in range(SLOTS)]
BUS=(46,462)
TRAY_SIZE,BOARD_SIZE=92,150
PAD,PAD_LIGHT,HIT,MISS='#d4a94b','#f5d68a','#5fd27e','#e0614c'
FLOW='#ffd76a'


def prepare_art(root):
    """Rotated module photos at tray and board size, shared by every repair window."""
    if hasattr(root,'_circuit_module_art'):return root._circuit_module_art
    photos={}
    for piece in range(circuit_art.PIECES):
        tile=circuit_art.tile(piece)
        for angle in range(4):
            rotated=tile.rotate(-90*angle)
            for size in (TRAY_SIZE,BOARD_SIZE):
                photos[piece,angle,size]=ImageTk.PhotoImage(rotated.resize((size,size),Image.Resampling.LANCZOS),master=root)
    root._circuit_module_art=photos;return photos


def scaled(points,x,y,size):
    k=size/circuit_art.TILE
    return [(x+(px-circuit_art.TILE/2)*k,y+(py-circuit_art.TILE/2)*k) for px,py in points]


class CircuitBoard(tk.Frame):
    def __init__(self,parent,app,q):
        super().__init__(parent,bg=PANEL);self.app=app;self.q=q;self.drag=None;self.mouse=(0,0)
        self.flow_job=None;self.flow_offset=0;self.spark_job=None
        self.photos=prepare_art(app.root)
        tk.Label(self,text='Перетягніть мікросхему з лотка на гніздо так, щоб її контакти лягли на золоті клеми.',bg=PANEL,fg=TEXT,font=('Segoe UI',11)).pack(pady=(6,2))
        tk.Label(self,text='Квадратний контакт 1 — на квадратну клему. ПКМ або R — поворот на 90°, навіть під час перетягування. У лотку можуть бути зайві модулі.',
                 bg=PANEL,fg='#a4b2a4',wraplength=890).pack(pady=(0,4))
        # Status and power share one row packed before the board: on short screens the board
        # loses its lower edge instead of the power button disappearing.
        row=tk.Frame(self,bg=PANEL);row.pack(side='bottom',fill='x',padx=12,pady=(6,8))
        self.power=ttk.Button(row,text='Увімкнути схему',command=self.check);self.power.pack(side='right')
        self.status=tk.Label(row,bg=PANEL,fg=GOLD,anchor='w',justify='left',wraplength=700);self.status.pack(side='left',fill='x',expand=True)
        self.canvas=tk.Canvas(self,width=W,height=H,bg='#10251e',highlightthickness=0);self.canvas.pack(padx=12)
        c=self.canvas
        c.bind('<ButtonPress-1>',self.press);c.bind('<B1-Motion>',self.motion);c.bind('<Motion>',self.hover)
        c.bind('<ButtonRelease-1>',self.release);c.bind('<Button-3>',self.rotate)
        self.bind_all_keys()
        self.bind('<Destroy>',self.destroyed)
        self.draw()

    def bind_all_keys(self):
        top=self.winfo_toplevel()
        for key in ('<KeyPress-r>','<KeyPress-R>','<KeyPress-Cyrillic_ka>','<KeyPress-Cyrillic_KA>'):
            top.bind(key,lambda e:self.rotate(None))

    def destroyed(self,event):
        if event.widget is not self:return
        for job in (self.flow_job,self.spark_job):
            if job:
                try:self.after_cancel(job)
                except tk.TclError:pass
        self.flow_job=self.spark_job=None

    # --- geometry ---
    def rotation(self,piece):return self.q['circuit_rotations'][str(piece)]

    def tray_cells(self):
        tray=[p for p in self.q['circuit_inventory'] if p not in self.q['circuit_slots']]
        return [(p,77+i%2*132,96+i//2*114) for i,p in enumerate(tray)]

    def hover_slot(self):
        if self.drag is None:return None
        mx,my=self.mouse
        return next((i for i,(x,y) in enumerate(CENTERS) if abs(mx-x)<88 and abs(my-y)<88 and self.q['circuit_slots'][i] in (None,self.drag)),None)

    def hit(self,x,y):
        for i,(cx,cy) in enumerate(CENTERS):
            p=self.q['circuit_slots'][i]
            if p is not None and abs(x-cx)<80 and abs(y-cy)<80:return p
        return next((p for p,cx,cy in self.tray_cells() if abs(x-cx)<60 and abs(y-cy)<54),None)

    # --- drawing ---
    def pad(self,x,y,first,fill):
        c=self.canvas;r=6
        shape=c.create_rectangle if first else c.create_oval
        shape(x-r,y-r,x+r,y+r,fill=fill,outline=PAD_LIGHT,width=1)
        c.create_oval(x-2,y-2,x+2,y+2,fill='#092d20',outline='')

    def module(self,piece,x,y,size):
        c=self.canvas;angle=self.rotation(piece);r=4 if size<BOARD_SIZE else 5
        c.create_image(x,y,image=self.photos[piece,angle,size])
        for n,(px,py) in enumerate(scaled(contacts_at(self.q,piece,angle),x,y,size)):
            shape=c.create_rectangle if n==0 else c.create_oval
            shape(px-r,py-r,px+r,py+r,fill=PAD,outline='#fff0c0',width=1)
            if n==0:c.create_text(px+7,py-7,text='1',fill='#f3f6ea',font=('Segoe UI',7,'bold'))

    def draw(self):
        c=self.canvas;c.delete('all');q=self.q
        done=q.get('circuit_checked');bad=set(q.get('circuit_bad',[]))
        hints=q.get('circuit_settings',{}).get('hints',1)
        c.create_rectangle(*TRAY,fill='#1b2b24',outline='#536852',width=2)
        c.create_text(143,27,text='ДОСТУПНІ МІКРОСХЕМИ',fill=GOLD,font=('Segoe UI',10,'bold'))
        c.create_rectangle(293,8,892,497,fill='#075333',outline='#a1b98d',width=3)
        c.create_rectangle(301,16,884,489,outline='#2d8b57',width=2)
        c.create_text(590,32,text='AFTERDAYS  /  CONTROL PCB  /  REV.03',fill='#d4e8c9',font=('Segoe UI',9,'bold'))
        for x in (313,872):
            for y in (28,477):
                c.create_oval(x-9,y-9,x+9,y+9,fill='#c7a24b',outline='#f1d386',width=2)
                c.create_oval(x-5,y-5,x+5,y+5,fill='#15251d',outline='')
        for y in BUS:
            c.create_line(318,y,866,y,fill='#063c27',width=7);c.create_line(318,y,866,y,fill='#20854a',width=3)
        target=self.hover_slot()
        live=self.q['circuit_slots'] and target is not None and hints
        for i,(x,y) in enumerate(CENTERS):
            board=scaled(pads(q,i),x,y,BOARD_SIZE);bus=BUS[0] if i<3 else BUS[1]
            for n,(px,py) in enumerate(board):
                lane=x-84-n*3 if px<x else x+84+n*3
                points=(px,py,lane,py,lane,bus)
                c.create_line(*points,fill='#063c27',width=5)
                if done:c.create_line(*points,fill=FLOW,width=2,dash=(6,6),tags='flow')
                else:c.create_line(*points,fill='#20854a',width=2)
            # Silkscreen corners only: the module outline is not printed.
            s,k=82,14
            for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1)):
                c.create_line(x+sx*s,y+sy*(s-k),x+sx*s,y+sy*s,x+sx*(s-k),y+sy*s,fill='#cfe3c4',width=1.5)
            c.create_text(x-74,y-62,text=f'U{i+1}',fill='#dbe8ce',font=('Segoe UI',9,'bold'),anchor='w')
            info=self.app.game.circuit_fit(q,self.drag,i) if live and i==target else None
            for n,(px,py) in enumerate(board):
                fill=(HIT if info['pads'][n] else MISS) if info else MISS if i in bad else PAD
                self.pad(px,py,n==0,fill)
            placed=q['circuit_slots'][i]
            if placed is not None and placed!=self.drag:self.module(placed,x,y,BOARD_SIZE)
            if i in bad:c.create_rectangle(x-86,y-86,x+86,y+86,outline='#ef7a62',width=2,dash=(5,4))
            if done:c.create_oval(x+65,y-75,x+75,y-65,fill='#9dff9a',outline='')
        for p,x,y in self.tray_cells():
            c.create_rectangle(x-60,y-54,x+60,y+54,fill='#20352a',outline='#415b45')
            if p!=self.drag:self.module(p,x,y,TRAY_SIZE)
        if self.drag is not None:
            mx,my=self.mouse;self.module(self.drag,mx,my,BOARD_SIZE)
            if live:
                info=self.app.game.circuit_fit(q,self.drag,target)
                for hit_,(px,py) in zip(info['contacts'],scaled(contacts_at(q,self.drag,self.rotation(self.drag)),mx,my,BOARD_SIZE)):
                    if not hit_:c.create_oval(px-9,py-9,px+9,py+9,outline='#ef7a62',width=2)
        count=sum(p is not None for p in q['circuit_slots'])
        if done:self.status.config(text='Схема працює! Поверніться до замовника.',fg='#91d9aa')
        elif bad:self.status.config(text='Іскра на '+', '.join(f'U{i+1}' for i in sorted(bad))+': контакти не лягли на клеми. Перевірте модуль і поворот.',fg='#edb477')
        else:self.status.config(text=f'Встановлено модулів: {count}/{SLOTS} · живлення вимкнено',fg=GOLD)
        self.power.config(state='normal' if count==SLOTS and not done else 'disabled')
        if done and self.flow_job is None:self.flow()

    def flow(self):
        """Current running along the tracks after a successful power-on."""
        self.flow_job=None
        if not self.winfo_exists():return
        self.flow_offset=(self.flow_offset+2)%12
        self.canvas.itemconfigure('flow',dashoffset=self.flow_offset)
        self.flow_job=self.after(60,self.flow)

    def sparks(self,step=0):
        self.spark_job=None
        c=self.canvas;c.delete('spark')
        if step>=8 or not self.winfo_exists():return
        for i in self.q.get('circuit_bad',[]):
            x,y=CENTERS[i];r=10+step*6
            c.create_oval(x-r,y-r,x+r,y+r,outline=FLOW,width=max(1,4-step//2),tags='spark')
        self.spark_job=self.after(50,lambda:self.sparks(step+1))

    # --- input ---
    def editable(self):return not self.q.get('circuit_checked')

    def press(self,e):
        if not self.editable():return
        self.drag=self.hit(e.x,e.y);self.mouse=(e.x,e.y)
        if self.drag is not None:self.draw()

    def motion(self,e):
        self.mouse=(e.x,e.y)
        if self.drag is not None:self.draw()

    def hover(self,e):self.mouse=(e.x,e.y)

    def release(self,e):
        if self.drag is None:return
        self.mouse=(e.x,e.y);slot=self.hover_slot()
        if slot is not None or TRAY[0]<=e.x<=TRAY[2]:
            self.app.game.place_circuit(self.q['id'],self.drag,slot)
        self.drag=None;self.draw()

    def rotate(self,e):
        if not self.editable():return 'break'
        if e is not None:self.mouse=(e.x,e.y)
        piece=self.drag if self.drag is not None else self.hit(*self.mouse)
        if piece is not None:
            self.app.game.rotate_circuit(self.q['id'],piece);self.draw()
        return 'break'

    def check(self):
        ok=self.app.game.check_circuits(self.q['id'])
        self.draw()
        if ok:self.app.refresh()
        else:
            self.sparks()
            if self.q.get('circuit_settings',{}).get('shock'):self.app.refresh()


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
    g.init_circuit_board(q)
    app.route.pause();win=window(app,q['title'])
    sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
    w,h=min(960,sw-20),min(770,sh-60)
    win.geometry(f'{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2-20)}')
    board=CircuitBoard(win,app,q);board.pack(fill='both',expand=True);win.circuit_board=board
