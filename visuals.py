from i18n import t as tr
"""Canvas art and drag-and-drop inventory. No external image files or packages."""
import math
import sprites
import content
import terrain_tiles
import tkinter as tk
from tkinter import ttk, messagebox
import afterdays as rules

BG, PANEL, TEXT, MUTED, GOLD = '#141c1a', '#202b27', '#e4e8d9', '#9baa9e', '#d7b77a'


def icon(c, item, x, y, size=48):
    """Deterministic vector pictograms; rarity outlines and class-specific silhouettes."""
    if item is None:
        return
    if sprites.draw(c,sprites.item_key(item),x,y,size):
        if item.get('kind')=='weapon' and size>=48:
            from adventure import damage_type
            sprites.draw(c,'damage:'+damage_type(item),x+size-16,y,16)
        for n,mod in enumerate(item.get('modules',[])):
            c.create_rectangle(x+size*(.08+n*.17),y+size*.90,x+size*(.20+n*.17),y+size*.97,fill=rules.RARITIES[mod['rarity']][1],outline='#18251c')
        return
    k, name = item['kind'], item['name']
    color = rules.RARITIES[item.get('rarity', 0)][1]
    metal, dark = '#a5b2a6', '#293b34'
    scale = size/64
    def coords(points):
        return [v*scale+(x if i % 2 == 0 else y) for i, v in enumerate(points)]
    def rect(*p, **kw):
        c.create_rectangle(*coords(p), **kw)
    def line(*p, **kw):
        c.create_line(*coords(p), **kw)
    def poly(*p, **kw):
        c.create_polygon(*coords(p), **kw)
    def oval(*p, **kw):
        c.create_oval(*coords(p), **kw)
    if k == 'weapon':
        laser = any(s in name for s in (tr('visuals.0001'), tr('visuals.0002'), tr('visuals.0003'), tr('visuals.0004')))
        pistol = any(s in name for s in (tr('visuals.0005'), tr('visuals.0006'), tr('visuals.0007')))
        if tr('visuals.0008') in name:
            line(8, 12, 23, 32, 8, 52, fill=color, width=max(2, size/16))
            line(8, 12, 8, 52, fill=metal)
            rect(8, 28, 60, 35, fill=metal, outline=color)
            poly(30, 35, 42, 35, 35, 53, 26, 53, fill='#785c47')
        else:
            rect(19, 23, 45 if pistol else 51, 35, fill=dark, outline=color, width=2)
            rect(40, 25, 58, 30, fill=metal, outline=color)
            poly(25, 35, 36, 35, 31, 52, 22, 52, fill='#715c4c', outline=color)
            if not pistol:
                poly(4, 26, 19, 25, 19, 35, 4, 42, fill='#736a52', outline=color)
                rect(39, 35, 46, 45, fill=metal, outline='')
                line(31, 19, 45, 19, fill=metal, width=3)
            if tr('visuals.0009') in name:
                line(41, 33, 61, 33, fill=metal, width=3)
            if tr('visuals.0010') in name:
                oval(27, 32, 47, 52, fill='#555f52', outline=color)
            if tr('visuals.0011') in name:
                oval(25, 23, 38, 36, fill=metal, outline=color)
            if laser:
                glow = '#72e3db' if tr('visuals.0012') not in name else '#eec670'
                rect(24, 26, 44, 31, fill=glow, outline='')
                oval(51, 21, 60, 34, fill=dark, outline=glow, width=2)
        for n, mod in enumerate(item.get('modules', [])):
            mx = x+size*(.10+.17*n)
            c.create_rectangle(mx, y+size*.90, mx+size*.12, y+size*.96,
                               fill=rules.RARITIES[mod['rarity']][1], outline='')
    elif k == 'armor':
        heavy = any(s in name for s in (tr('visuals.0013'), tr('visuals.0014'), tr('visuals.0015'), tr('visuals.0016')))
        if tr('visuals.0017') in name or tr('visuals.0018') in name:
            poly(18, 7, 46, 7, 59, 57, 5, 57, fill='#485548', outline=color, width=2)
        poly(19, 10, 27, 15, 37, 15, 45, 10, 57, 21, 47, 29, 46, 55, 18, 55, 17, 29, 7, 21,
             fill='#667260' if heavy else '#736d55', outline=color, width=2)
        rect(23, 23, 41, 44, fill='#344b40', outline=color)
        line(32, 23, 32, 51, fill=metal)
        if heavy:
            rect(5, 15, 18, 31, fill=metal, outline=color)
            rect(46, 15, 59, 31, fill=metal, outline=color)
        line(21, 49, 43, 49, fill='#bdab76', width=2)
    elif k == 'helmet':
        hood = tr('visuals.0019') in name
        poly(12, 30, 16, 14, 26, 7, 40, 7, 51, 17, 54, 42, 45, 55, 19, 55, 10, 43,
             fill='#696957' if hood else '#718178', outline=color, width=2)
        rect(16, 25, 48, 36, fill='#172824', outline=color)
        line(19, 29, 43, 29, fill='#90ccc4', width=2)
        if tr('visuals.0020') in name or tr('visuals.0021') in name:
            oval(24, 35, 41, 51, fill=dark, outline=metal)
            line(28, 38, 28, 47, 32, 47, 32, 38, 36, 38, 36, 47, fill=metal)
    elif k == 'ammo':
        energy=item.get('ammo_type')=='energy'
        for n in range(3):
            xx=12+n*15
            rect(xx,22,xx+10,52,fill='#638f89' if energy else '#b39b62',outline='#d1c08c')
            poly(xx,22,xx+5,10,xx+10,22,fill='#8edbd2' if energy else '#a6b0a2')
        line(8,55,58,55,fill=metal,width=2)
    elif k == 'fragments':
        poly(8,18,32,10,29,36,14,47,fill='#8a9d88',outline=color,width=2)
        poly(36,23,55,16,59,49,39,55,fill='#657c79',outline=color,width=2)
    elif k == 'rad':
        rect(15,12,49,55,fill='#c4cbaa',outline='#a6dc66',width=2)
        rect(13,8,51,19,fill='#658746',outline=color)
        oval(23,28,41,46,fill='#94bc51',outline='#263c29')
        line(24,30,40,44,fill='#263c29',width=3)
    elif k == 'parts':
        oval(10,12,40,42,fill='#6c7e70',outline=metal,width=3)
        oval(20,22,30,32,fill=dark,outline='')
        line(32,46,53,22,fill='#c0aa7c',width=5)
        poly(45,14,55,16,61,26,50,31,43,23,fill='#c0aa7c',outline=metal)
    elif k == 'sealed':
        rect(8,12,56,55,fill='#655945',outline='#b29d74',width=2)
        line(8,25,56,25,fill='#ac9369',width=3)
        line(30,12,30,55,fill='#ac9369',width=3)
        oval(24,28,40,43,fill='#243b30',outline='#c7b27b')
    elif k == 'module':
        code = sum(map(ord, name))
        stat = next(iter(item.get('stats', {})), '')
        rect(13, 13, 51, 51, fill='#30443c', outline=color, width=2)
        for n in range(4):
            v = 18+9*n
            line(v, 7, v, 13, fill=metal, width=2)
            line(v, 51, v, 57, fill=metal, width=2)
            line(7, v, 13, v, fill=metal, width=2)
            line(51, v, 57, v, fill=metal, width=2)
        if stat in ('range', 'accuracy'):
            oval(21, 21, 43, 43, outline=color, width=2)
            line(32, 16, 32, 48, fill=color)
            line(16, 32, 48, 32, fill=color)
        elif stat in ('defense', 'vitality'):
            poly(22, 21, 42, 21, 40, 36, 32, 44, 24, 36, fill=color)
        elif stat in ('regen', 'evasion'):
            line(19, 33, 26, 33, 30, 23, 35, 42, 39, 31, 46, 31, fill=color, width=2)
        elif stat == 'capacity':
            rect(23, 24, 41, 43, fill=color, outline='')
            line(27, 24, 27, 19, 37, 19, 37, 24, fill=color, width=2)
        else:
            poly(35, 18, 23, 34, 32, 34, 28, 47, 43, 28, 34, 28, fill=color)
        for n in range(1+(code % 3)):
            rect(16+n*5, 47, 18+n*5, 49, fill='#e8edd8', outline='')
    elif k == 'med':
        rect(9, 19, 55, 52, fill='#b8b9a1', outline='#e6e8d5', width=2)
        line(23, 19, 23, 12, 41, 12, 41, 19, fill=metal, width=3)
        rect(27, 25, 37, 46, fill='#b85449', outline='')
        rect(21, 31, 43, 40, fill='#b85449', outline='')
    elif k == 'food':
        rect(15, 17, 49, 50, fill='#8b9475', outline=metal)
        oval(15, 10, 49, 23, fill='#c7c9af', outline=metal)
        oval(15, 43, 49, 55, fill='#697963', outline=metal)
        rect(17, 27, 47, 40, fill='#b49c66', outline='')
        line(26, 15, 39, 15, fill='#4b5b4b', width=2)
    elif k == 'quest':
        rect(13, 6, 51, 58, fill='#7c785d', outline=GOLD, width=2)
        rect(18, 14, 46, 40, fill='#29433b', outline='#7ca490')
        line(22, 32, 30, 21, 40, 30, fill='#bfd38e', width=2)
        oval(28, 46, 36, 53, fill=GOLD, outline='')

    if k in ('armor','helmet'):
        for n,mod in enumerate(item.get('modules',[])):
            rect(6+n*11,58,14+n*11,63,fill=rules.RARITIES[mod['rarity']][1],outline='')


def monster(c, enemy, x, y, size):
    if sprites.draw(c,content.monster_id(enemy),x,y,size):
        if enemy.get('grade','normal')!='normal':
            c.create_oval(x,y,x+size,y+size,outline='#dc8ef5' if enemy['grade']=='mythic' else '#eac863',width=2)
        return
    if enemy.get('grade','normal')!='normal':
        c.create_oval(x,y,x+size,y+size,outline='#dc8ef5' if enemy['grade']=='mythic' else '#eac863',width=3)
    kind = enemy.get('kind', 0) % len(rules.MONSTERS)
    color = rules.MONSTERS[kind][-1]
    s = size
    def oval(a, b, d, e, **kw):
        c.create_oval(x+a*s, y+b*s, x+d*s, y+e*s, **kw)
    def line(*points, **kw):
        c.create_line(*[v*s+(x if i % 2 == 0 else y) for i, v in enumerate(points)], **kw)
    def poly(*points, **kw):
        c.create_polygon(*[v*s+(x if i % 2 == 0 else y) for i, v in enumerate(points)], **kw)
    if kind in (0, 3, 6):
        oval(.12, .34, .76, .74, fill=color, outline='#222c25')
        poly(.65, .32, .86, .18, .96, .47, .73, .58, fill=color)
        line(.25, .67, .19, .89, fill=color, width=3)
        line(.61, .67, .74, .88, fill=color, width=3)
        line(.15, .52, .01, .30, fill=color, width=2)
        oval(.82, .32, .88, .38, fill='#ffd576', outline='')
    elif kind in (5, 11):
        for n in range(4):
            yy = .24+n*.15
            line(.43, yy, .13, yy-.08, .04, yy+.1, fill=color, width=2)
            line(.57, yy, .87, yy-.08, .96, yy+.1, fill=color, width=2)
        oval(.25, .17, .75, .85, fill=color, outline='#292c24', width=2)
        oval(.36, .25, .45, .34, fill='#eece75', outline='')
        oval(.56, .25, .65, .34, fill='#eece75', outline='')
    elif kind in (7, 10):
        poly(.2, .27, .8, .27, .95, .58, .5, .79, .05, .58, fill=color, outline='#273638')
        oval(.37, .35, .64, .60, fill='#293939', outline='#c5f0dc')
        line(.04, .2, .96, .2, fill=color, width=2)
        line(.22, .08, .22, .35, fill=color, width=2)
        line(.78, .08, .78, .35, fill=color, width=2)
    else:
        oval(.33, .04, .67, .36, fill=color, outline='#34362c')
        poly(.27, .33, .73, .33, .83, .7, .62, .69, .66, .98, .48, .98,
             .44, .68, .4, .98, .24, .98, .30, .63, .15, .68, fill=color, outline='#34362c')
        if kind in (4, 9):
            poly(.17, .31, .38, .37, .34, .66, .08, .65, fill='#d0c6a0', outline='#54615b')
            poly(.64, .36, .86, .28, .94, .66, .7, .69, fill='#d0c6a0', outline='#54615b')
        if kind == 2:
            oval(.41, .24, .67, .47, fill='#b8d562', outline='')
        line(.41, .19, .47, .19, fill='#ffeeaf', width=2)
        line(.54, .19, .61, .19, fill='#ffeeaf', width=2)


def terrain(c, kind, x, y, t, gx, gy, game, battle=False):
    """Stable detail from coordinates; painting never advances the gameplay RNG."""
    if not battle and terrain_tiles.draw(c,game,gx,gy,x,y,t):return
    key='site' if kind=='site' else 'terrain:'+str(kind)
    if not battle and kind=='road':sprites.draw(c,'terrain:road',x,y,t)
    if not battle and kind!='road' and sprites.draw(c,key,x,y,t):return
    seed = (gx*73856093 ^ gy*19349663) & 0xffff
    if kind == 'water':
        for offset in (.3,.55,.8):
            c.create_line(x+t*.1,y+t*offset,x+t*.4,y+t*(offset-.08),x+t*.85,y+t*offset,fill='#568694')
    elif kind == 'cliff':
        c.create_polygon(x+t*.08,y+t*.88,x+t*.45,y+t*.1,x+t*.64,y+t*.47,x+t*.78,y+t*.3,x+t*.97,y+t*.88,fill='#9a9d90',outline='#c0beaa')
        c.create_line(x+t*.45,y+t*.1,x+t*.5,y+t*.85,fill='#666e66')
    elif kind == 'site':
        c.create_rectangle(x+t*.2,y+t*.38,x+t*.8,y+t*.85,fill='#70927c',outline='#b4d4aa')
        c.create_polygon(x+t*.1,y+t*.4,x+t*.5,y+t*.08,x+t*.9,y+t*.4,fill='#a7bd91')
    elif kind == 'waste' or battle:
        for n in range(3):
            px = x+t*((seed >> (n*3) & 7)+1)/10
            py = y+t*((seed >> (n*3+2) & 7)+1)/10
            c.create_line(px, py, px+t*.08, py-t*.035, fill='#4d5947')
    elif kind == 'forest':
        for ox, oy in ((.28, .55), (.7, .75)):
            c.create_line(x+t*ox, y+t*(oy-.4), x+t*ox, y+t*oy, fill='#6e7c59', width=2)
            c.create_line(x+t*(ox-.17), y+t*(oy-.3), x+t*ox, y+t*(oy-.17), x+t*(ox+.14), y+t*(oy-.38), fill='#556c50')
    elif kind == 'ruin':
        for a, b, h in ((.12, .2, .6), (.55, .35, .4)):
            c.create_rectangle(x+t*a, y+t*b, x+t*(a+.28), y+t*(b+h), fill='#5f6052', outline='#85826a')
            c.create_rectangle(x+t*(a+.06), y+t*(b+.13), x+t*(a+.15), y+t*(b+.25), fill='#28332c', outline='')
        c.create_line(x+t*.14, y+t*.9, x+t*.8, y+t*.88, fill='#827960')
    elif kind == 'road':
        cx, cy = x+t/2, y+t/2
        for nx, ny in rules.neighbors(gx, gy, len(game.world[0]), len(game.world)):
            if game.world[ny][nx] in ('road', 'city'):
                c.create_line(cx, cy, cx+(nx-gx)*t/2, cy+(ny-gy)*t/2, fill='#9b8967', width=max(2, int(t*.23)))
                c.create_line(cx, cy, cx+(nx-gx)*t/2, cy+(ny-gy)*t/2, fill='#c1ae7c', dash=(2, 4))
    elif kind == 'city':
        c.create_rectangle(x+t*.08, y+t*.2, x+t*.9, y+t*.88, fill='#544f3d', outline=GOLD)
        for a, b, w, h in ((.15, .38, .25, .38), (.46, .25, .22, .5), (.72, .47, .13, .3)):
            c.create_rectangle(x+t*a, y+t*b, x+t*(a+w), y+t*(b+h), fill='#a19067', outline='#ccba8e')
            c.create_rectangle(x+t*(a+.05), y+t*(b+.09), x+t*(a+.10), y+t*(b+.18), fill='#f5d881', outline='')
        c.create_line(x+t*.55, y+t*.07, x+t*.55, y+t*.3, fill='#c5c5a9')
        c.create_polygon(x+t*.55, y+t*.07, x+t*.83, y+t*.12, x+t*.55, y+t*.18, fill='#ba765d')


TYPE_ORDER=['weapon','armor','helmet','module','ammo','med','food','rad','parts','fragments','quest','sealed']
TYPE_COLORS=dict(zip(TYPE_ORDER,['#323f53','#344c3b','#3f4c42','#453957','#504831','#50333b','#475032','#345249','#49433c','#424750','#514c35','#423c46']))
TYPE_ORDER.insert(TYPE_ORDER.index('quest'),'trophy')
TYPE_ORDER.insert(TYPE_ORDER.index('parts'),'repairkit')
TYPE_COLORS['repairkit']='#4d4935'
TYPE_COLORS['trophy']='#503e32'
def item_sort_key(item):
    kind=item['kind'];return (0 if item.get('promotion') else 1,TYPE_ORDER.index(kind) if kind in TYPE_ORDER else 99,-item.get('rarity',0),-item.get('level',1),item['name'],item['id'])

def condition_color(value):
    return '#75ce83' if value>=70 else '#e3c159' if value>25 else '#e66d63'

def condition_bar(canvas,item,x,y,width,height=4):
    if not item or 'durability' not in item:return
    from module_rules import condition
    value=condition(item);color=condition_color(value)
    canvas.create_rectangle(x,y,x+width,y+height,fill='#18201b',outline=color,width=1)
    if value>0:canvas.create_rectangle(x,y,x+width*value/100,y+height,fill=color,outline='')

class ItemGrid(tk.Frame):
    def __init__(self, parent, on_select=None, height=160, columns=5):
        super().__init__(parent, bg=PANEL)
        self.items, self.rects, self.selection = [], {}, None
        self.on_select = on_select
        self.columns = columns
        self.canvas = tk.Canvas(self, bg='#17231e', height=height, highlightthickness=0)
        scroll = ttk.Scrollbar(self, command=self.canvas.yview)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.bind('<Configure>', lambda e: self.render())
        self.canvas.bind('<Button-1>', self.select_event)
        self.canvas.bind('<Button-3>',self.inspect_event)
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        self.canvas.bind('<Button-4>', lambda e: self.canvas.yview_scroll(-1, 'units'))
        self.canvas.bind('<Button-5>', lambda e: self.canvas.yview_scroll(1, 'units'))

    def inspect_event(self,event):
        item=next((i for i in self.items if i['id']==self.hit(event.x,event.y)),None)
        import item_actions
        app,owner=item_actions.locate(self)
        return item_actions.show(app,item,event,owner,self)

    def set_items(self, items):
        self.items = sorted(items,key=item_sort_key)
        if not any(i['id'] == self.selection for i in self.items):
            self.selection = None
        self.render()

    def hit(self, x, y):
        x, y = self.canvas.canvasx(x), self.canvas.canvasy(y)
        return next((i for i, (a,b,d,e) in self.rects.items() if a <= x <= d and b <= y <= e), None)

    def select_event(self, event):
        self.selection = self.hit(event.x, event.y)
        self.render()
        if self.on_select:
            self.on_select(self.selection)

    def render(self):
        c = self.canvas
        c.delete('all')
        self.rects = {}
        width = max(100, c.winfo_width())
        cell = width/self.columns
        h = 78
        for n, item in enumerate(self.items):
            x, y = (n % self.columns)*cell, (n//self.columns)*h
            r = (x+2, y+2, x+cell-3, y+h-3)
            self.rects[item['id']] = r
            color = rules.RARITIES[item.get('rarity', 0)][1]
            c.create_rectangle(*r, fill=TYPE_COLORS.get(item['kind'],'#233229'),outline=color,width=3 if item['id']==self.selection else 1)
            art=sprites.inventory_photo(c,item,int(cell-6))
            if art:c.create_image(x+cell/2,y+3,image=art,anchor='n')
            else:icon(c,item,x+(cell-min(cell-8,72))/2,y+3,min(cell-8,72))
            for slot,mod in enumerate(item.get('modules',[])):
                c.create_rectangle(x+7+slot*9,y+46,x+13+slot*9,y+49,fill=rules.RARITIES[mod['rarity']][1],outline='#14201b')
            if item['kind'] in ('weapon','armor','helmet','module'):
                c.create_rectangle(x+4,y+3,x+28,y+17,fill='#17201c',outline='')
                c.create_text(x+6,y+9,text=f'L{item.get("level",1)}',fill=TEXT,font=('Segoe UI',8,'bold'),anchor='w')
            if item['kind']=='quest' or item.get('quest_id'):
                c.create_rectangle(x+4,y+3,x+24,y+18,fill='#17201c',outline='')
                broken=item.get('quest_repair') and item.get('durability',0)<100
                c.create_text(x+14,y+10,text='?' if broken else '✓',fill='#f2cb62' if broken else '#76e89a',font=('Segoe UI',11,'bold'))
            if item['kind']=='weapon' or item.get('qty',1)>1:
                c.create_rectangle(x+cell-36,y+3,x+cell-4,y+17,fill='#17201c',outline='')
            if item['kind']=='weapon':c.create_text(x+cell-6,y+9,text=tr('visuals.0022', v0=item.get('ap', 2)),fill=TEXT,font=('Segoe UI',8,'bold'),anchor='e')
            elif item.get('qty',1)>1:c.create_text(x+cell-6,y+9,text=f'×{item["qty"]}',fill=TEXT,font=('Segoe UI',8,'bold'),anchor='e')
            if item['id']==self.selection:c.create_rectangle(x+5,y+16,x+9,y+20,fill='#ffffff',outline='')
            if item.get('promotion'):
                c.create_rectangle(x+4,y+19,x+45,y+34,fill='#28573d',outline='')
                c.create_text(x+24,y+26,text=f"−{item['promotion']['discount']}%",fill='#b0f2a7',font=('Segoe UI',8,'bold'))
            short = item['name'][:10] + ('…' if len(item['name']) > 10 else '')
            c.create_text(x+cell/2, y+59, text=short, fill=color, font=('Segoe UI', 8))
            condition_bar(c,item,x+7,y+69,cell-14)
            if item['kind']=='sealed':c.create_text(x+cell/2,y+71,text='?',fill=MUTED,font=('Segoe UI',7))
        c.configure(scrollregion=(0, 0, width, max(h, math.ceil(len(self.items)/self.columns)*h)))


def inside(widget, xr, yr):
    return widget.winfo_rootx() <= xr < widget.winfo_rootx()+widget.winfo_width() and widget.winfo_rooty() <= yr < widget.winfo_rooty()+widget.winfo_height()


class Drag:
    def __init__(self, owner, callback):
        self.owner, self.callback = owner, callback
        self.payload = self.start = self.ghost = None

    def begin(self, event, payload):
        self.cancel()
        self.payload = payload
        self.start = (event.x_root, event.y_root)

    def move(self, event):
        if not self.payload or math.dist(self.start, (event.x_root, event.y_root)) < 6:
            return
        if self.ghost is None:
            self.ghost = tk.Toplevel(self.owner)
            self.ghost.overrideredirect(True)
            self.ghost.attributes('-topmost', True)
            c = tk.Canvas(self.ghost, width=58, height=58, bg='#263e31', highlightthickness=1, highlightbackground=GOLD)
            c.pack()
            icon(c, self.payload['item'], 4, 4, 48)
        self.ghost.geometry(f'+{event.x_root+16}+{event.y_root+16}')

    def end(self, event):
        payload, dragging = self.payload, self.ghost is not None
        self.cancel()
        if payload and dragging:
            self.callback(payload, event.x_root, event.y_root)

    def cancel(self):
        if self.ghost:
            self.ghost.destroy()
        self.ghost = self.payload = self.start = None


class EquipmentPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=PANEL)
        self.app = app
        self.selection = None
        self.slots = {}
        self.paper = tk.Canvas(self, height=218, bg='#17221d', highlightthickness=0)
        self.paper.pack(fill='x', padx=6, pady=(5, 0))
        self.paper.bind('<Configure>', lambda e: self.draw())
        tk.Label(self, text=tr('visuals.0023'), bg=PANEL, fg=MUTED, font=('Segoe UI', 8)).pack(pady=2)
        self.grid = ItemGrid(self, self.select, height=104)
        self.grid.pack(fill='both', expand=True, padx=6)
        from refinement_ui import Detail
        self.details = Detail(self,height=7)
        self.details.pack(fill='x', padx=8, pady=3)
        bar = tk.Frame(self, bg=PANEL)
        bar.pack(fill='x', padx=4, pady=4)
        for n, (label, fn) in enumerate([(tr('visuals.0024'), app.equip_selected), (tr('visuals.0025'), app.modify),
                                       (tr('visuals.0026'), app.use_selected), (tr('visuals.0027'), app.drop_selected),
                                       (tr('visuals.0028'), app.dismantle_selected),
                                       (tr('scav.repair_menu'), lambda: __import__('maintenance_ui').show(app))]):
            ttk.Button(bar, text=label, command=fn).grid(row=n//3, column=n%3, sticky='ew', padx=2, pady=2)
        bar.columnconfigure((0, 1, 2), weight=1)
        self.drag = Drag(self, self.drop)
        self.paper.bind('<Button-1>', self.press_paper)
        self.paper.bind('<Button-3>',self.inspect_paper)
        self.paper.bind('<B1-Motion>', self.drag.move)
        self.paper.bind('<ButtonRelease-1>', self.drag.end)
        self.paper.bind('<Double-Button-1>', lambda e: app.modify())
        self.grid.canvas.bind('<Button-1>', self.press_bag)
        self.grid.canvas.bind('<B1-Motion>', self.drag.move)
        self.grid.canvas.bind('<ButtonRelease-1>', self.drag.end)
        self.grid.canvas.bind('<Double-Button-1>', lambda e: app.equip_selected())

    def select(self, item_id):
        self.selection = item_id
        item = self.app.game.find(item_id)
        self.details.config(text=self.app.description(item))
        self.draw()

    def refresh(self):
        self.grid.set_items(self.app.game.bag)
        if not self.app.game.find(self.selection):
            self.selection = None
        self.select(self.selection)

    def draw(self):
        c, g = self.paper, self.app.game
        c.delete('all')
        w = max(340, c.winfo_width())
        mid = w/2
        if not sprites.draw(c,'player',mid-99,4,198):
            # Anatomical silhouette beneath actual helmet, torso armor and carried weapons.
            c.create_oval(mid-19, 12, mid+19, 52, fill='#536257', outline='#8a9886')
            c.create_polygon(mid-28, 56, mid+28, 56, mid+43, 116, mid+29, 148,
                             mid+19, 202, mid+3, 202, mid, 148, mid-3, 202,
                             mid-19, 202, mid-29, 148, mid-43, 116,
                             fill='#435649', outline='#81927e', width=2)
            c.create_line(mid-25, 60, mid-62, 112, fill='#697b68', width=13)
            c.create_line(mid+25, 60, mid+62, 112, fill='#697b68', width=13)
        self.slots = {'helmet': (mid-31, 1, mid+31, 62), 'armor': (mid-43, 66, mid+43, 149),
                      'weapon1': (8, 65, 110, 154), 'weapon2': (w-110, 65, w-8, 154)}
        for slot, (x,y,d,e) in self.slots.items():
            item = g.equipped[slot]
            selected = item and item['id'] == self.selection
            color = rules.RARITIES[item['rarity']][1] if item else '#526352'
            c.create_rectangle(x,y,d,e, outline=GOLD if selected else color, width=2, dash=() if item else (3,3))
            if item:
                size = min(d-x-5, e-y-5)
                icon(c, item, (x+d-size)/2, y+2, size)
                condition_bar(c,item,x+4,e-7,d-x-8)
            else:
                c.create_text((x+d)/2, (y+e)/2, text='+', fill='#708573', font=('Segoe UI', 20))
            if slot.startswith('weapon'):
                c.create_text((x+d)/2, e+12, text=('▶ ' if g.active == slot else '')+rules.SLOTS[slot], fill=color, font=('Segoe UI', 9))
        c.create_text(mid, 215, text=tr('visuals.0030', v0=g.defense, v1=g.weight, v2=g.capacity), fill=MUTED, font=('Segoe UI', 8))

    def inspect_paper(self,event):
        slot=next((s for s,(a,b,d,e) in self.slots.items() if a<=event.x<=d and b<=event.y<=e),None)
        import item_actions
        return item_actions.show(self.app,self.app.game.equipped.get(slot),event,self)

    def press_paper(self, event):
        slot = next((s for s,(a,b,d,e) in self.slots.items() if a <= event.x <= d and b <= event.y <= e), None)
        item = self.app.game.equipped.get(slot)
        self.select(item['id'] if item else None)
        if item:
            self.drag.begin(event, dict(item=item, slot=slot))

    def press_bag(self, event):
        self.grid.select_event(event)
        item = self.app.game.find(self.grid.selection)
        if item:
            self.drag.begin(event, dict(item=item, slot=None))

    def drop(self, payload, xr, yr):
        g = self.app.game
        if g.battle:
            self.app.act(lambda: g.log(tr('visuals.0031')))
            return
        if payload['item'].get('kind')=='module':
            target_item=None
            if inside(self.paper,xr,yr):
                x,y=xr-self.paper.winfo_rootx(),yr-self.paper.winfo_rooty()
                target=next((slot for slot,(a,b,c,d) in self.slots.items() if a<=x<=c and b<=y<=d),None)
                target_item=g.equipped.get(target)
            elif inside(self.grid.canvas,xr,yr):
                ident=self.grid.hit(xr-self.grid.canvas.winfo_rootx(),yr-self.grid.canvas.winfo_rooty())
                target_item=g.find(ident)
            if target_item:self.app.act(lambda:g.quick_module(target_item['id'],payload['item']['id']))
            return
        if inside(self.paper, xr, yr):
            x, y = xr-self.paper.winfo_rootx(), yr-self.paper.winfo_rooty()
            target = next((s for s,(a,b,d,e) in self.slots.items() if a <= x <= d and b <= y <= e), None)
            if target and not payload['slot']:
                self.app.act(lambda: g.equip(payload['item']['id'], target))
            elif target and payload['slot'] and target != payload['slot'] and target.startswith('weapon') and payload['slot'].startswith('weapon'):
                a = payload['slot']
                g.equipped[a], g.equipped[target] = g.equipped[target], g.equipped[a]
                self.app.refresh()
        elif inside(self.grid.canvas, xr, yr) and payload['slot']:
            self.app.act(lambda: g.unequip(payload['slot']))


class ModificationPanel(tk.Frame):
    def __init__(self, parent, app, item_id):
        super().__init__(parent, bg=PANEL)
        self.app, self.item_id = app, item_id
        self.slot_rects = []
        self.selected_mod = None
        self.top = tk.Canvas(self, height=260, bg='#16221c', highlightthickness=0)
        self.top.pack(fill='x', padx=10, pady=8)
        self.top.bind('<Configure>', lambda e: self.draw())
        self.top.bind('<Button-3>',self.inspect_top)
        from refinement_ui import Detail
        self.summary = Detail(self,height=4)
        self.summary.pack(fill='x', padx=12, pady=5)
        tk.Label(self, text=tr('visuals.0032'), bg=PANEL, fg=GOLD).pack(pady=6)
        self.grid = ItemGrid(self, self.select, height=175, columns=8)
        self.grid.pack(fill='both', expand=True, padx=10)
        self.preview = tk.Label(self, bg=PANEL, fg=TEXT, height=2, wraplength=710, justify='left')
        self.preview.pack(fill='x', padx=12, pady=5)
        bar = tk.Frame(self, bg=PANEL)
        bar.pack(fill='x', padx=10, pady=8)
        ttk.Button(bar, text=tr('visuals.0033'), command=self.install_selected).pack(side='left', padx=4)
        ttk.Button(bar, text=tr('visuals.0034'), command=self.remove_selected).pack(side='left', padx=4)
        self.drag = Drag(self, self.drop)
        self.grid.canvas.bind('<Button-1>', self.press_bag)
        self.grid.canvas.bind('<B1-Motion>', self.drag.move)
        self.grid.canvas.bind('<ButtonRelease-1>', self.drag.end)
        self.top.bind('<Button-1>', self.press_slot)
        self.top.bind('<B1-Motion>', self.drag.move)
        self.top.bind('<ButtonRelease-1>', self.drag.end)
        self.refresh()

    @property
    def item(self):
        return self.app.game.find(self.item_id)

    def refresh(self):
        self.grid.set_items([m for m in self.app.game.bag if rules.compatible(self.item, m)])
        self.summary.config(text=self.app.description(self.item))
        self.draw()
        self.app.refresh()

    def draw(self):
        c, item = self.top, self.item
        c.delete('all')
        w = max(600, c.winfo_width())
        icon(c, item, w/2-80, 3, 145)
        c.create_text(w/2, 152, text=item['name'], fill=GOLD, font=('Segoe UI', 13, 'bold'))
        self.slot_rects = []
        start = (w-item['slots']*100)/2
        for n in range(item['slots']):
            x, y = start+n*100, 174
            r = (x+4, y, x+94, y+80)
            self.slot_rects.append(r)
            mod = item['modules'][n] if n < len(item['modules']) else None
            color = rules.RARITIES[mod['rarity']][1] if mod else '#617363'
            c.create_line(w/2, 135, x+49, y, fill='#465946')
            c.create_rectangle(*r, fill='#26382d', outline=color, dash=() if mod else (4,3), width=2)
            if mod:
                icon(c, mod, x+25, y+2, 48)
                c.create_text(x+49, y+62, text=mod['name'][:12], fill=color, font=('Segoe UI', 8))
            else:
                c.create_text(x+49, y+31, text='+', fill=color, font=('Segoe UI', 23))
                c.create_text(x+49, y+65, text=tr('visuals.0035', v0=n + 1), fill=MUTED, font=('Segoe UI', 8))

    def select(self, item_id, sign=1):
        self.selected_mod = item_id
        mod = self.app.game.find(item_id)
        if not mod:
            mod = next((m for m in self.item['modules'] if m['id'] == item_id), None)
        if mod:
            import copy,progression as p
            candidate=copy.deepcopy(self.item)
            if sign>0:
                candidate['modules'].append(copy.deepcopy(mod))
            else:
                candidate['modules']=[m for m in candidate['modules'] if m['id']!=mod['id']]
            old,new=p.stats(self.item),p.stats(candidate)
            keys=[k for k in dict.fromkeys([*old,*new]) if old.get(k,0)!=new.get(k,0)]
            rows=[f"{rules.STAT_NAMES.get(k,k)}: {old.get(k,0):g} → {new.get(k,0):g}" for k in keys]
            rows.append(tr('modules.condition_preview',before=p.mr.max_condition(self.item),after=p.mr.max_condition(candidate)))
            self.preview.config(text=mod['name']+'\n'+' · '.join(rows))

    def inspect_top(self,event):
        n=next((n for n,(x,y,d,f) in enumerate(self.slot_rects) if x<=event.x<=d and y<=event.y<=f),None)
        item=self.item['modules'][n] if n is not None and n<len(self.item['modules']) else self.item if n is None else None
        import item_actions
        return item_actions.show(self.app,item,event,self)

    def press_bag(self, e):
        self.grid.select_event(e)
        mod = self.app.game.find(self.grid.selection)
        if mod:
            self.drag.begin(e, dict(item=mod, source='bag'))

    def press_slot(self, e):
        idx = next((i for i,(a,b,d,f) in enumerate(self.slot_rects) if a <= e.x <= d and b <= e.y <= f), None)
        if idx is not None and idx < len(self.item['modules']):
            mod = self.item['modules'][idx]
            self.select(mod['id'], -1)
            self.drag.begin(e, dict(item=mod, source='slot'))

    def install_selected(self):
        if self.selected_mod:
            self.app.game.install(self.item_id, self.selected_mod)
            self.refresh()

    def remove_selected(self):
        if self.selected_mod:
            self.app.game.uninstall(self.item_id, self.selected_mod)
            self.refresh()

    def drop(self, payload, xr, yr):
        g = self.app.game
        if payload['source'] == 'bag' and inside(self.top, xr, yr):
            x,y = xr-self.top.winfo_rootx(), yr-self.top.winfo_rooty()
            idx = next((i for i,(a,b,d,e) in enumerate(self.slot_rects) if a <= x <= d and b <= y <= e), None)
            if idx is not None:
                g.put_module(self.item_id, payload['item']['id'], idx)
        elif payload['source'] == 'slot' and inside(self.grid.canvas, xr, yr):
            g.uninstall(self.item_id, payload['item']['id'])
        self.refresh()


class QuestPanel(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL)
        self.app=app
        self.tree=ttk.Treeview(self,show='tree',height=10,selectmode='browse')
        self.tree.pack(fill='both',expand=True,padx=8,pady=8)
        self.tree.tag_configure('unique',foreground='#cf98ef')
        self.tree.tag_configure('done',foreground='#8fa58e')
        self.tree.tag_configure('ready',foreground=GOLD)
        self.tree.bind('<<TreeviewSelect>>',lambda e:self.describe())
        self.tree.bind('<Button-1>',self.click)
        self.detail=tk.Label(self,bg=PANEL,fg=TEXT,wraplength=345,justify='left',anchor='nw',height=12)
        self.detail.pack(fill='x',padx=10,pady=8)
        ttk.Button(self,text=tr('visuals.0036'),command=self.turn_in).pack(fill='x',padx=8,pady=5)
        ttk.Button(self,text=tr('visuals.0037'),command=app.atlas).pack(fill='x',padx=8,pady=5)

    def selected(self):
        selection=self.tree.selection()
        return next((q for q in self.app.game.quests if selection and q['id']==selection[0]),None)

    def click(self,event):
        if self.tree.identify_row(event.y)=='completed':
            self.tree.item('completed',open=not self.tree.item('completed','open'))
            return 'break'

    def refresh(self):
        old=self.selected()
        opened=self.tree.item('completed','open') if self.tree.exists('completed') else False
        for i in self.tree.get_children():self.tree.delete(i)
        g=self.app.game
        for q in g.quests:
            if q['status']=='done':continue
            mark='✓' if g.quest_ready(q) else '◇'
            tag='unique' if q.get('unique') else 'ready' if g.quest_ready(q) else ''
            self.tree.insert('','end',iid=q['id'],text=f'{"★ " if q.get("unique") else ""}{mark} {q["title"]}',tags=(tag,))
        done=[q for q in g.quests if q['status']=='done']
        self.tree.insert('','end',iid='completed',text=tr('visuals.0038', v0=len(done)),open=opened,tags=('done',))
        for q in done:self.tree.insert('completed','end',iid=q['id'],text='✓ '+q['title'],tags=('done',))
        if old and self.tree.exists(old['id']):self.tree.selection_set(old['id'])
        elif any(q['status']!='done' for q in g.quests):self.tree.selection_set(next(q['id'] for q in g.quests if q['status']!='done'))
        self.describe()

    def describe(self):
        q=self.selected()
        self.detail.config(text=self.app.game.quest_text(q) if q else tr('visuals.0039'))

    def turn_in(self):
        q=self.selected()
        if q:self.app.act(lambda:self.app.game.turn_in(q['id']))
