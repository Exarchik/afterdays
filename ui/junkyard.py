"""Junkyard minigame: clear a top-down pile one free piece at a time; lifting costs satiety."""
import math
import tkinter as tk
from tkinter import ttk

from ui.inspection import window
from visuals import PANEL,TEXT,GOLD,MUTED
from junk_art import draw_piece
from junk_find_art import target_icon
import junk_physics as pile
from i18n import t as tr

GOOD,BAD='#91d9aa','#e56860'


def show(app,ident):
    g=app.game;q=g.junk_quest(ident)
    if q:Junkyard(app,g,q)


def plural(n,one,few,many):
    n=abs(n)%100
    return one if n%10==1 and n!=11 else few if 2<=n%10<=4 and not 12<=n<=14 else many


class Junkyard:
    def __init__(self,app,game,quest):
        self.app,self.game,self.quest=app,game,quest;self.ident=quest['id']
        self.closed=False;self.timer=None;self.hover=None;self.message=None;self.tone=GOLD
        self.scale=1;self.ox=self.oy=0;self.phase=0;self.fresh=None;self.shake=0
        self.win=window(app,tr('scav.junkyard'));self.win._junkyard=self
        w=min(1180,self.win.winfo_screenwidth()-40);h=min(820,self.win.winfo_screenheight()-80)
        self.win.geometry(f'{w}x{h}+{max(0,(self.win.winfo_screenwidth()-w)//2)}+{max(0,(self.win.winfo_screenheight()-h)//2)}')
        per=quest['junk_settings']['work_per_satiety']
        tk.Label(self.win,text=tr('scav.junk_help',work=f"{per} {plural(per,'очко','очки','очок')}"),bg=PANEL,fg=TEXT,wraplength=w-60,justify='left').pack(padx=16,pady=(12,6))
        body=tk.Frame(self.win,bg=PANEL);body.pack(fill='both',expand=True,padx=12,pady=6)
        side=tk.Frame(body,bg=PANEL,width=300);side.pack(side='left',fill='y',padx=(0,10));side.pack_propagate(False)
        self.info=tk.Canvas(side,width=300,height=150,bg='#1b2720',highlightthickness=0);self.info.pack(fill='x')
        tk.Label(side,text='Їжа в рюкзаку',bg=PANEL,fg=GOLD,font=('Segoe UI',10,'bold'),anchor='w').pack(fill='x',pady=(10,0))
        self.food_note=tk.Label(side,text='Їжа додає ситість як зазвичай.',bg=PANEL,fg=MUTED,anchor='w',justify='left',wraplength=290)
        self.food_note.pack(fill='x')
        self.food=tk.Frame(side,bg=PANEL);self.food.pack(fill='x',pady=4)
        self.costs=tk.Canvas(side,width=300,height=170,bg='#1b2720',highlightthickness=0);self.costs.pack(fill='x',side='bottom',pady=(6,0))
        self.canvas=tk.Canvas(body,bg='#343b2c',highlightthickness=0)
        self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.canvas.bind('<Motion>',self.motion);self.canvas.bind('<Leave>',lambda e:self.set_hover(None))
        self.canvas.bind('<Button-1>',self.click)
        self.win.bind('<Destroy>',self.destroyed,add='+')
        self.draw_costs();self.refresh_side();self.draw()
        self.timer=self.win.after(160,self.tick)

    # Model <-> screen coordinates.
    def coordinates(self,event):return ((event.x-self.ox)/self.scale,(event.y-self.oy)/self.scale)

    def settings(self):return self.quest['junk_settings']

    def capacity(self):return self.game.junk_capacity(self.quest)

    def describe(self,piece):
        name,cost=pile.MATERIALS[piece['material']][:2];left=self.capacity()
        above=pile.blockers(self.quest,piece)
        if above:
            first=pile.MATERIALS[above[0]['material']][0].lower()
            return (f'{name}: заблоковано — зверху лежить {first}.' if len(above)==1 else
                    f'{name}: заблоковано — зверху лежать {len(above)} уламки.'),BAD
        if cost>left:return f'{name}: вільний, важить {cost}, а ситості вистачить лише на {left}. З’їжте щось.',BAD
        return f'{name}: вільний. Вага {cost}.',GOOD

    def status(self):
        q=self.quest
        if self.message:return self.message,self.tone
        if self.hover:return self.describe(self.hover)
        if self.game.quest_ready(q):return 'Усі деталі знайдено — поверніться до квестодавця. Решту завалу можна розібрати заради запчастин.',GOOD
        if self.capacity()<=0:
            return ('Ситість на нулі. З’їжте щось із рюкзака, щоб копати далі.' if self.game.junk_foods() else
                    'Ситість на нулі, а їжі немає. Купіть їжу й поверніться — завал нікуди не дінеться.'),BAD
        return 'Наведіть на уламок: видно, чи він вільний і скільки важить. Блиск — край знахідки з-під сміття.',GOLD

    def draw(self):
        if self.closed:return
        c=self.canvas;c.delete('all');q=self.quest
        width,height=max(1,c.winfo_width()),max(1,c.winfo_height())
        self.scale=max(.01,min(width/pile.WIDTH,(height-46)/pile.HEIGHT))
        self.ox=(width-pile.WIDTH*self.scale)/2;self.oy=max(0,(height-46-pile.HEIGHT*self.scale)/2)
        c.create_rectangle(0,0,pile.WIDTH,pile.HEIGHT,fill='#343b2c',outline='')
        for n in range(420):
            x=(n*97)%pile.WIDTH;y=(n*61+n*n*7)%pile.HEIGHT
            c.create_rectangle(x,y,x+2,y+2,fill=('#4c503d','#454936','#2b3128','#565a45')[n%4],outline='')
        for f in q['junk_finds']:
            if f['found']:continue
            color=GOLD if f['kind']=='target' else '#8caf91'
            c.create_oval(f['x']-26,f['y']-26,f['x']+26,f['y']+26,fill='#243126',outline=color,width=2)
            target_icon(c,f['x'],f['y'],'chip' if f['kind']=='target' else 'wire' if f['kind']=='parts' else 'scrap' if f['kind']=='fragments' else 'ammo',color)
        left=self.capacity()
        for piece in sorted(pile.live(q),key=lambda p:p['z']):
            free=not pile.blockers(q,piece);cost=pile.MATERIALS[piece['material']][1]
            outline=None
            if piece is self.hover:outline=GOOD if free and cost<=left else BAD
            draw_piece(c,piece,outline)
            if free:
                fill,ring=('#5a2a26',BAD) if cost>left else ("#1b2720",GOOD)
                c.create_oval(piece['x']-13,piece['y']-13,piece['x']+13,piece['y']+13,fill=fill,outline=ring,width=2)
                c.create_text(piece['x'],piece['y'],text=str(cost),fill='#eee9d9',font=('Consolas',10,'bold'))
        if self.fresh and self.fresh[1]>0:
            piece=next((p for p in pile.live(q) if p['id']==self.fresh[0]),None)
            if piece:c.create_polygon(*[v for pt in pile.corners(piece) for v in pt],fill='',outline=GOLD,width=3,dash=(7,5))
        if self.hover and not self.hover['gone']:
            for above in pile.blockers(q,self.hover):
                c.create_polygon(*[v for pt in pile.corners(above) for v in pt],fill='',outline=BAD,width=3,dash=(6,4))
        size=6+2.5*math.sin(self.phase)
        for f in q['junk_finds']:
            if f['found'] or pile.find_free(q,f):continue
            point=pile.peek(q,f)
            if point:
                x,y=point;s=size
                c.create_polygon(x,y-s*1.7,x+s*.35,y-s*.35,x+s*1.7,y,x+s*.35,y+s*.35,x,y+s*1.7,x-s*.35,y+s*.35,x-s*1.7,y,x-s*.35,y-s*.35,fill='#fff6cf',outline='#ffe08a')
        c.scale('all',0,0,self.scale,self.scale)
        jolt=(4 if self.shake%2 else -4)*min(1,self.shake) if self.shake else 0
        c.move('all',self.ox+jolt,self.oy+(jolt/2 if self.shake%3 else 0))
        text,color=self.status()
        top=self.oy+pile.HEIGHT*self.scale+6
        c.create_rectangle(self.ox,top,self.ox+pile.WIDTH*self.scale,top+38,fill='#18221c',outline='#3a4a3e')
        c.create_text(self.ox+12,top+19,text=text,fill=color,anchor='w',font=('Segoe UI',10,'bold'),width=pile.WIDTH*self.scale-24)

    def refresh_side(self):
        q=self.quest;s=self.settings();c=self.info;c.delete('all')
        c.create_text(12,16,text='Квестові деталі',anchor='w',fill=TEXT,font=('Segoe UI',10))
        c.create_text(288,16,text=f"{q['progress']}/{q['goal']}",anchor='e',fill=TEXT,font=('Consolas',10,'bold'))
        for n in range(q['goal']):
            x=12+n*40;got=n<q['progress']
            c.create_rectangle(x,30,x+32,62,outline=GOLD if got else '#4b5a42',fill='#3a3220' if got else '',dash=() if got else (3,3))
            c.create_text(x+16,46,text='✓' if got else str(n+1),fill=GOLD if got else '#4b5a42',font=('Consolas',10,'bold'))
        satiety=max(0,self.game.hunger);per=s['work_per_satiety'];work=q['junk_work']
        c.create_text(12,84,text='Ситість',anchor='w',fill=TEXT,font=('Segoe UI',10))
        c.create_text(288,84,text=f'{satiety}/20',anchor='e',fill=TEXT,font=('Consolas',10,'bold'))
        c.create_rectangle(12,96,288,106,fill='#0e1411',outline='#2c3a30')
        if satiety>0:c.create_rectangle(13,97,13+274*min(1,satiety/20),105,fill='#65b3ed',outline='')
        c.create_text(12,122,text='Втома',anchor='w',fill=MUTED,font=('Segoe UI',9))
        for n in range(per):
            x=58+n*18;c.create_rectangle(x,118,x+14,125,fill='#c9a35a' if n<work else '#0e1411',outline='#c9a35a' if n<work else '#4a5a50')
        left=self.capacity()
        c.create_text(12,140,text=f"Вистачить ще на {left} {plural(left,'очко','очки','очок')} ваги." if left else 'Сил немає — поїжте.',anchor='w',fill=MUTED if left else BAD,font=('Segoe UI',9))
        self.food_note.config(text=f"1 очко ситості = {per} {plural(per,'очко','очки','очок')} ваги сміття. Їжа додає ситість як зазвичай.")
        for child in self.food.winfo_children():child.destroy()
        from game.systems.consumables import definition
        foods=self.game.junk_foods()
        if not foods:tk.Label(self.food,text='Їжі немає.',bg=PANEL,fg=MUTED,anchor='w').pack(fill='x')
        for item in foods:
            satiety=definition(item)['satiety'];gain=self.game.junk_food_gain(q,item)
            belt=any(i is item for i in getattr(self.game,'provisions',[]))
            label=f"{item['name']} ×{item.get('qty',1)}{' (провізія)' if belt else ''} · ситість +{satiety}"
            ttk.Button(self.food,text=label,command=lambda ident=item['id']:self.eat(ident),
                       state='normal' if gain else 'disabled').pack(fill='x',pady=2)

    def draw_costs(self):
        c=self.costs;c.delete('all')
        c.create_text(12,14,text='Скільки важить',anchor='w',fill=GOLD,font=('Segoe UI',10,'bold'))
        for n,(name,cost,_,_,colour) in enumerate(pile.MATERIALS):
            y=38+n*22
            c.create_rectangle(12,y-5,26,y+5,fill=colour,outline='#101410')
            c.create_text(34,y,text=name,anchor='w',fill=TEXT,font=('Segoe UI',9))
            c.create_text(288,y,text=str(cost),anchor='e',fill=TEXT,font=('Consolas',10,'bold'))

    def set_hover(self,piece):
        if piece is not self.hover:
            self.hover=piece
            if piece is not None:self.message=None
            self.draw()

    def motion(self,event):
        x,y=self.coordinates(event)
        self.set_hover(None if pile.find_at(self.quest,x,y) else pile.piece_at(self.quest,x,y))

    def click(self,event):
        x,y=self.coordinates(event);q=self.quest;g=self.game
        find=pile.find_at(q,x,y)
        if find and pile.find_free(q,find):
            if g.junk_collect(self.ident,find['id']):
                self.message=tr('scav.junk_progress',count=q['progress'],goal=q['goal']) if find['kind']=='target' else 'Знайдено бонус — він у здобичі на локації.'
                self.tone=GOOD;self.after_change()
            return
        piece=pile.piece_at(q,x,y)
        if not piece:return
        cost=pile.MATERIALS[piece['material']][1];before=g.hunger
        if g.junk_remove(self.ident,piece['id']):
            opened=sum(1 for f in q['junk_finds'] if not f['found'] and pile.find_free(q,f))
            spent=before-g.hunger
            self.message=f"{pile.ACCUSATIVE[piece['material']]} прибрано (вага {cost})."+(f' Ситість −{spent}.' if spent>0 else '')+(' Під ним щось є — клацніть, щоб забрати.' if opened else '')
            self.tone=GOOD if opened else GOLD;self.hover=None
            settled=getattr(g,'_junk_settled',None)
            if settled:
                new=next(p for p in q['junk_pieces'] if p['id']==settled['piece'])
                name=pile.MATERIALS[new['material']][0].lower()
                self.message+=(f' Звалище осіло: з-під сміття висунувся уламок ({name}).' if settled['between'] else
                               f' Звалище осіло: зверху сповз уламок ({name}).')+(' Він накрив знахідку.' if settled['covered'] else '')
                self.tone=GOLD;self.fresh=[new['id'],14];self.shake=6
            elif self.capacity()<=0:self.message=None
            self.after_change()
        else:
            self.message,self.tone=self.describe(piece);self.draw()

    def eat(self,ident):
        item=next((i for i in self.game.junk_foods() if i['id']==ident),None)
        gain=self.game.junk_eat(self.ident,ident)
        if gain and item:self.message,self.tone=f"{item['name']}: ситість +{gain}.",GOOD
        self.after_change()

    def after_change(self):
        self.refresh_side();self.draw();self.app.refresh()

    def tick(self):
        self.timer=None
        if self.closed:return
        busy=bool(self.shake) or bool(self.fresh and self.fresh[1]>0)
        if self.shake:self.shake-=1
        if self.fresh and self.fresh[1]>0:self.fresh[1]-=1
        if busy or any(not f['found'] and not pile.find_free(self.quest,f) and pile.peek(self.quest,f) for f in self.quest['junk_finds']):
            self.phase+=.9;self.draw()
        self.timer=self.win.after(160,self.tick)

    def destroyed(self,event):
        if event.widget is not self.win:return
        self.closed=True;self.hover=None
        if self.timer is not None:
            try:self.win.after_cancel(self.timer)
            except tk.TclError:pass
            self.timer=None
