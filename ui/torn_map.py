"""Torn map minigame: ragged pieces of the real world map on a table.

Drag a piece to move it (with everything glued to it); a click, right click or the
mouse wheel turns it by 90°. The model glues true neighbours and decides the solution.
"""
import math
import tkinter as tk

from i18n import t as tr
from visuals import PANEL,TEXT,GOLD
from game.systems import torn_map as model

TABLE_BG='#26352d'
W,H=940,780


def show(app,ident,win=None):
    g=app.game;q=g.map_quest(ident)
    if not q or q['map_solved'] or g.battle:return
    if win is None:
        from ui.restoration import dialog
        win=dialog(app,tr('restoration.assemble'))
        w,h=min(W,win.winfo_screenwidth()-40),min(H,win.winfo_screenheight()-80)
        win.geometry(f'{w}x{h}+{max(0,(win.winfo_screenwidth()-w)//2)}+{max(0,(win.winfo_screenheight()-h)//2)}')
    win._torn_map=TornMap(app,win,ident)
    return win._torn_map


class TornMap:
    def __init__(self,app,win,ident):
        self.app,self.win,self.ident=app,win,ident
        g=app.game;self.q=g.map_quest(ident);self.state=g.map_puzzle(ident)
        self.target=list(g.map_target(self.q))
        self.shapes=model.outlines(ident,self.state['cols'],self.state['rows'])
        tk.Label(win,text=tr('restoration.puzzle_help'),bg=PANEL,fg=TEXT,wraplength=860,justify='left').pack(padx=15,pady=(12,6),fill='x')
        info=tk.Frame(win,bg=PANEL);info.pack(side='bottom',fill='x',padx=15)
        self.status=tk.Label(info,bg=PANEL,fg=GOLD,anchor='w');self.status.pack(side='left',fill='x',expand=True)
        self.seams=tk.Label(info,bg=PANEL,fg=TEXT,anchor='e');self.seams.pack(side='right')
        self.c=tk.Canvas(win,bg=TABLE_BG,highlightthickness=0,width=880,height=600)
        self.c.pack(fill='both',expand=True,padx=15,pady=4)
        self.S=0;self.ox=self.oy=0;self.items={};self.cache={};self.tapes={};self.z={i:i for i in range(len(self.state['pieces']))}
        self.drag=None;self.pending=None;self.solved_shown=False
        self.c.bind('<Configure>',lambda e:self.schedule())
        self.c.bind('<ButtonPress-1>',self.press);self.c.bind('<B1-Motion>',self.motion)
        self.c.bind('<ButtonRelease-1>',self.release)
        self.c.bind('<Button-3>',lambda e:self.turn_at(e.x,e.y))
        self.c.bind('<MouseWheel>',lambda e:self.turn_at(e.x,e.y))
        self.c.bind('<Button-4>',lambda e:self.turn_at(e.x,e.y))
        self.status.config(text='')
        self.update_seams()

    # ---------- images ----------
    def schedule(self):
        if self.pending:self.win.after_cancel(self.pending)
        self.pending=self.win.after(80,self.layout)

    def layout(self):
        self.pending=None
        if not self.win.winfo_exists():return
        cw,ch=self.c.winfo_width(),self.c.winfo_height()
        if cw<50 or ch<50:return
        tw,th=model.TABLE;S=max(40,int(min(cw/tw,ch/th)))
        self.ox,self.oy=(cw-tw*S)/2,(ch-th*S)/2
        if S!=self.S:self.build(S)
        self.sync()

    def build(self,S):
        import map_fragment
        from PIL import ImageOps
        self.S=S;self.cache={};self.tapes={}
        sheet,self.target_px,self.hex_px=map_fragment.render(self.app.game,self.state,self.ident,S,self.target)
        self.pad=pad=int(S*.22)
        self.sheet=ImageOps.expand(sheet,border=pad,fill=(205,185,138)).convert('RGBA')

    def piece_image(self,i,r):
        key=(i,r)
        if key not in self.cache:
            from PIL import Image,ImageDraw,ImageFilter,ImageTk
            S,pad,cols=self.S,self.pad,self.state['cols'];gx,gy=i%cols,i//cols
            size=S+2*pad
            piece=self.sheet.crop((gx*S,gy*S,gx*S+size,gy*S+size))
            points=[(pad+S/2+x*S,pad+S/2+y*S) for x,y in self.shapes[i]]
            mask=Image.new('L',(size,size),0);ImageDraw.Draw(mask).polygon(points,fill=255)
            piece.putalpha(mask)
            ImageDraw.Draw(piece).line(points+[points[0]],fill=(244,232,204,235),width=max(2,S//55),joint='curve')
            piece=piece.rotate(-90*r,resample=Image.Resampling.BICUBIC)
            shadow=Image.new('RGBA',(size,size),(0,0,0,0))
            alpha=piece.getchannel('A').point(lambda a:a*110//255).filter(ImageFilter.GaussianBlur(max(2,S//28)))
            shadow.paste((5,10,8,255),(0,0),alpha)
            out=Image.new('RGBA',(size,size),(0,0,0,0))
            out.alpha_composite(shadow,(0,max(2,S//40)));out.alpha_composite(piece)
            self.cache[key]=(ImageTk.PhotoImage(out,master=self.c),piece.getchannel('A'))
        return self.cache[key]

    def tape_image(self,angle):
        key=round(angle)%180
        if key not in self.tapes:
            from PIL import Image,ImageDraw,ImageTk
            w,h=max(12,int(self.S*.26)),max(7,int(self.S*.13))
            im=Image.new('RGBA',(w,h),(232,222,190,115));ImageDraw.Draw(im).rectangle((0,0,w-1,h-1),outline=(140,122,84,110))
            self.tapes[key]=ImageTk.PhotoImage(im.rotate(-key,expand=True,resample=Image.Resampling.BICUBIC),master=self.c)
        return self.tapes[key]

    # ---------- drawing ----------
    def point(self,p):return self.ox+p[0]*self.S,self.oy+p[1]*self.S

    def sync(self):
        if not self.S:return
        self.c.delete('table');self.items={}
        pieces=self.state['pieces']
        groups={}
        for i in sorted(range(len(pieces)),key=lambda i:self.z[i]):groups.setdefault(pieces[i][3],[]).append(i)
        for group,ids in sorted(groups.items(),key=lambda kv:max(self.z[i] for i in kv[1])):
            for i in ids:
                photo,_=self.piece_image(i,pieces[i][2])
                self.items[i]=self.c.create_image(*self.point(pieces[i]),image=photo,tags=('table','piece',f'g{group}'))
            for a,b in self.state['glued']:
                if pieces[a][3]!=group:continue
                (ax,ay),(bx,by)=self.point(pieces[a]),self.point(pieces[b])
                jitter=((a*7+b*13)%9-4)*3
                angle=math.degrees(math.atan2(by-ay,bx-ax))+jitter
                self.c.create_image((ax+bx)/2,(ay+by)/2,image=self.tape_image(angle),tags=('table','tape',f'g{group}'))
        if model.solved(self.state):self.show_solved()

    def update_seams(self):
        cols,rows=self.state['cols'],self.state['rows']
        self.seams.config(text=tr('restoration.map_seams',n=len(self.state['glued']),total=cols*(rows-1)+rows*(cols-1)))

    def show_solved(self):
        x0,y0=self.point(self.state['pieces'][0]);x0-=self.S/2;y0-=self.S/2
        x,y=x0+self.target_px[0],y0+self.target_px[1];hr=self.hex_px*.92
        pts=[v for n in range(6) for v in (x+hr*math.cos(math.radians(-90+60*n)),y+hr*math.sin(math.radians(-90+60*n)))]
        self.c.create_polygon(*pts,outline='#a8261e',fill='',dash=(5,4),width=2,tags=('table','stash'))
        self.status.config(text=tr('restoration.map_solved',x=self.target[0],y=self.target[1]),fg='#8fc67a')
        if self.solved_shown:
            self.cross(x,y,1);return
        self.solved_shown=True
        def step(k=1):
            if not self.win.winfo_exists():return
            self.c.delete('cross');self.cross(x,y,k/12)
            if k<12:self.win.after(40,lambda:step(k+1))
        step()

    def cross(self,x,y,k):
        d=self.S*.1;w=max(3,self.S//28)
        a=min(1,k*2);self.c.create_line(x-d,y-d,x-d+2*d*a,y-d+2*d*a,fill='#b0261c',width=w,capstyle='round',tags=('table','cross'))
        if k>.5:
            b=min(1,(k-.5)*2);self.c.create_line(x+d,y-d,x+d-2*d*b,y-d+2*d*b,fill='#b0261c',width=w,capstyle='round',tags=('table','cross'))
        if k>=1:
            self.c.create_text(x+d*1.4,y-d*1.3,text=f'({self.target[0]}, {self.target[1]})',anchor='w',
                               fill='#962018',font=('Segoe Print',max(10,self.S//11)),tags=('table','cross'))

    # ---------- input ----------
    def hit(self,x,y):
        pieces=self.state['pieces']
        for i in sorted(self.items,key=lambda i:-self.z[i]):
            _,alpha=self.piece_image(i,pieces[i][2])
            cx,cy=self.point(pieces[i]);lx,ly=int(x-cx+alpha.width/2),int(y-cy+alpha.height/2)
            if 0<=lx<alpha.width and 0<=ly<alpha.height and alpha.getpixel((lx,ly))>40:return i
        return None

    def raise_group(self,i):
        top=max(self.z.values())+1;group=self.state['pieces'][i][3]
        for j,p in enumerate(self.state['pieces']):
            if p[3]==group:self.z[j]=top
        self.c.tag_raise(f'g{group}')

    def press(self,e):
        if model.solved(self.state) or not self.S:return
        i=self.hit(e.x,e.y)
        if i is None:return
        self.raise_group(i)
        self.drag=dict(i=i,x=e.x,y=e.y,sx=e.x,sy=e.y,moved=False,group=self.state['pieces'][i][3])

    def motion(self,e):
        d=self.drag
        if not d:return
        if math.hypot(e.x-d['sx'],e.y-d['sy'])>5:d['moved']=True
        if d['moved']:
            self.c.move(f"g{d['group']}",e.x-d['x'],e.y-d['y']);d['x'],d['y']=e.x,e.y

    def release(self,e):
        d=self.drag;self.drag=None
        if not d:return
        if not d['moved']:return self.turn(d['i'])
        p=self.state['pieces'][d['i']]
        cx,cy=self.point(p);x=(cx+e.x-d['sx']-self.ox)/self.S;y=(cy+e.y-d['sy']-self.oy)/self.S
        self.act(lambda:self.app.game.map_move(self.ident,d['i'],x,y))

    def turn_at(self,x,y):
        if model.solved(self.state) or not self.S:return
        i=self.hit(x,y)
        if i is not None:self.raise_group(i);self.turn(i)

    def turn(self,i):
        if not self.state['rotate']:return
        self.act(lambda:self.app.game.map_rotate(self.ident,i))

    def act(self,call):
        before=len(self.state['glued'])
        call()
        if len(self.state['glued'])>before and not model.solved(self.state):
            self.status.config(text=tr('restoration.map_glued'),fg=GOLD)
        self.update_seams();self.sync()
        if model.solved(self.state):self.app.refresh()
