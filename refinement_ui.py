from i18n import t as tr
"""Dark card lists, readable comparisons and workshop controls."""
import tkinter as tk
import sprites
import content
from tkinter import ttk
import visuals as v
import progression as p
import afterdays as r
BG,PANEL,TEXT,MUTED,GOLD=v.BG,v.PANEL,v.TEXT,v.MUTED,v.GOLD

class Detail(tk.Frame):
    """Scrollable shared property table, also used for ordinary descriptions."""
    def __init__(self,parent,**kw):
        bg=kw.pop('bg',PANEL)
        for key in ('fg','wraplength','justify','anchor'):kw.pop(key,None)
        height=kw.pop('height',9);kw.pop('width',None)
        super().__init__(parent,bg=bg)
        self.text=tk.Text(self,bg=bg,fg=TEXT,wrap='word',height=height,width=1,relief='flat',font=('Segoe UI',9),padx=7,pady=4,**kw)
        scroll=ttk.Scrollbar(self,command=self.text.yview);scroll.pack(side='right',fill='y')
        self.text.pack(side='left',fill='both',expand=True);self.text.configure(yscrollcommand=scroll.set)
        self.text.tag_configure('good',foreground='#91e6ab');self.text.tag_configure('bad',foreground='#ff9687')
        self.text.tag_configure('title',foreground=GOLD,font=('Segoe UI',10,'bold'))
        self.text.tag_configure('header',foreground='#b9d8e9',background='#263d39')
        self.text.bind('<Configure>',lambda e:self.text.configure(tabs=(max(105,e.width*.43),max(180,e.width*.70))))
        self.text.configure(state='disabled')
    def config(self,cnf=None,**kw):
        value=kw.pop('text',None)
        if value is not None:
            self.text.configure(state='normal');self.text.delete('1.0','end')
            for n,line in enumerate(value.split('\n')):
                tag='header' if line.startswith(tr('refinement_ui.0001')) else 'good' if '[+]' in line else 'bad' if '[-]' in line else 'title' if n==0 else ''
                self.text.insert('end',line.replace('[+]','').replace('[-]','')+'\n',tag)
            self.text.configure(state='disabled')
        if cnf or kw:super().configure(cnf,**kw)


def description(game,item):
    if not item:return tr('refinement_ui.0002')
    if item['kind']=='sealed':return tr('refinement_ui.0003', v0=p.item_weight(item))
    kind=item['kind'];lines=[item['name'],(f'L{item.get("level",1)} · ' if kind in ('weapon','armor','helmet','module') else '')+r.RARITIES[item['rarity']][0]]
    ident=item.get('type_id')
    if ident:
        desc=content.t(ident+'.description')
        if desc and desc!=ident+'.description':lines.append(desc)
    current=game.weapon if kind=='weapon' else game.equipped.get(kind)
    compare=current is not None and current['id']!=item['id']
    if compare:lines.append(tr('refinement_ui.0004')+current['name'])
    def field(label,value,base=None,lower=False,unit=''):
        tail=''
        if compare and base is not None and value!=base:
            diff=value-base;good=(diff<0) if lower else (diff>0)
            tail=f'{diff:+g}{unit} '+('[+]' if good else '[-]')
        lines.append(f'{label}\t{value:g}{unit}\t'+(tail or '—'))
    lines.append(tr('refinement_ui.0005'))
    field(tr('refinement_ui.0006'),p.item_weight(item),p.item_weight(current) if current else None,True,tr('refinement_ui.0007'))
    if 'qty' in item:lines.append(tr('refinement_ui.0008', v0=item['qty']))
    if 'durability' in item:field(tr('refinement_ui.0009'),item['durability'],current.get('durability',100) if current else None,unit='%')
    if kind=='weapon':
        import adventure
        field(tr('refinement_ui.0010'),item['ap'],current['ap'] if current else None,True,tr('refinement_ui.0011'))
        lines.append(tr('refinement_ui.0012')+adventure.DAMAGE_TYPES[adventure.damage_type(item)][0])
        lines.append(tr('refinement_ui.0013')+p.AMMO[item.get('ammo_type','pistol')][0])
    values=p.stats(item);baseline=p.stats(current) if current else {}
    for key in dict.fromkeys(list(values)+list(baseline)):
        if values.get(key) or (compare and baseline.get(key)):
            field(r.STAT_NAMES.get(key,key),values.get(key,0),baseline.get(key,0),unit='%' if key in ('accuracy','crit','evasion') else '')
            if kind=='module':lines[-1]+=' [-]' if values.get(key,0)<0 else ' [+]'
    if 'slots' in item:
        field(tr('refinement_ui.0014'),item['slots'],current['slots'] if current else None)
        lines.append(tr('refinement_ui.0015', v0=len(item['modules']), v1=item['slots']))
        lines.extend('  • '+m['name']+' · '+r.RARITIES[m['rarity']][0] for m in item['modules'])
        if not item['modules']:lines.append(tr('refinement_ui.0016'))
    elif kind=='module':
        lines.append(tr('refinement_ui.0017')+(tr('refinement_ui.0018') if item['target']=='weapon' else tr('refinement_ui.0019')))
        if item.get('tradeoff'):lines.append(tr('refinement_ui.0020'))
    elif kind=='med':lines.append(tr('refinement_ui.0021', v0=__import__('math').ceil(game.max_hp * 0.5)))
    elif kind=='rad':lines.append(tr('refinement_ui.0022'))
    elif kind=='food':lines.append(tr('refinement_ui.0023'))
    elif kind=='trophy':lines.append(tr('refinement_ui.0024'))
    elif kind in ('parts','fragments'):lines.append(tr('refinement_ui.0025')+(tr('refinement_ui.0026') if kind=='parts' else tr('refinement_ui.0027'))+tr('refinement_ui.0028'))
    return '\n'.join(lines)

QUEST_ICONS={'delivery':'✉','radio':'◉','trophies':'♜','hunt':'◎','retrieve':'▣','scout':'◈','supplies':'✚','purge':'⚑'}
class QuestCards(tk.Frame):
    def __init__(self,parent,app,mayor=False):
        super().__init__(parent,bg=PANEL);self.app=app;self.mayor=mayor;self.selection=None;self.open_done=False;self.entries=[];self.rects=[]
        self.canvas=tk.Canvas(self,bg='#17231e',height=235,highlightthickness=0)
        scroll=ttk.Scrollbar(self,command=self.canvas.yview);scroll.pack(side='right',fill='y')
        self.canvas.pack(fill='both',expand=True,padx=6,pady=6);self.canvas.config(yscrollcommand=scroll.set)
        self.canvas.bind('<Configure>',lambda e:self.paint());self.canvas.bind('<Button-1>',self.click)
        self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-1 if e.delta>0 else 1,'units'))
        self.detail=Detail(self,height=9);self.detail.pack(fill='x',padx=8)
        if mayor:ttk.Button(self,text=tr('refinement_ui.0029'),command=self.accept).pack(fill='x',padx=8,pady=3)
        ttk.Button(self,text=tr('refinement_ui.0030'),command=self.turn_in).pack(fill='x',padx=8,pady=3)
        if not mayor:ttk.Button(self,text=tr('refinement_ui.0031'),command=app.atlas).pack(fill='x',padx=8,pady=3)
        self.refresh()
    def selected(self):return next((q for q in self.entries if q['id']==self.selection),None)
    def refresh(self):
        g=self.app.game
        self.entries=([q for q in g.mayor_offers() if q['status']=='offered']+[q for q in g.quests if q['city']==g.city]) if self.mayor else list(g.quests)
        if not self.selected():self.selection=next((q['id'] for q in self.entries if q['status']!='done'),None)
        self.paint();self.describe()
    def paint(self):
        c=self.canvas;c.delete('all');self.rects=[];w=max(280,c.winfo_width());y=4
        active=[q for q in self.entries if q['status']!='done'];done=[q for q in self.entries if q['status']=='done']
        for q in active+[None]+(done if self.open_done else []):
            if q is None:
                c.create_rectangle(5,y,w-5,y+34,fill='#2a3c32',outline='#566955')
                c.create_text(15,y+17,text=('▾' if self.open_done else '▸')+tr('refinement_ui.0032', v0=len(done)),fill=MUTED,anchor='w')
                self.rects.append((y,y+34,'done'));y+=40;continue
            color='#d0a0f5' if q.get('unique') else '#8aa78e' if q['status']=='done' else GOLD
            c.create_rectangle(5,y,w-5,y+89,fill='#334a3d' if q['id']==self.selection else '#22332b',outline=color)
            c.create_oval(13,y+13,53,y+53,fill='#17241e',outline=color,width=2)
            if not sprites.draw(c,'quest:'+q['kind'],12,y+12,42):c.create_text(33,y+33,text=QUEST_ICONS[q['kind']],fill=color,font=('Segoe UI',21))
            c.create_text(64,y+9,text=('★ ' if q.get('unique') else '')+f'L{q.get("level",q.get("zone",1))} · '+q['title'],width=w-80,anchor='nw',fill=color,font=('Segoe UI',10,'bold'))
            state=tr('refinement_ui.0033') if q['status']=='offered' else tr('refinement_ui.0034') if q['status']=='done' else tr('refinement_ui.0035') if self.app.game.quest_ready(q) else tr('refinement_ui.0036', v0=q['progress'], v1=q['goal'])
            c.create_text(64,y+49,text=state,anchor='nw',fill=TEXT,font=('Segoe UI',9))
            c.create_text(16,y+75,text=tr('refinement_ui.0037', v0=q.get('money', q.get('reward', 0)), v1=q.get('xp_reward', 80 if q.get('unique') else 40)),anchor='w',fill=MUTED,font=('Segoe UI',9))
            self.rects.append((y,y+89,q['id']));y+=96
        c.config(scrollregion=(0,0,w,y))
    def click(self,e):
        y=self.canvas.canvasy(e.y);key=next((key for a,b,key in self.rects if a<=y<=b),None)
        if key=='done':self.open_done=not self.open_done
        else:self.selection=key
        self.paint();self.describe()
    def describe(self):
        q=self.selected();self.detail.config(text=self.app.game.quest_text(q) if q else tr('refinement_ui.0038'))
    def accept(self):
        q=self.selected()
        if q:self.app.game.accept_quest(q['id']);self.refresh();self.app.refresh()
    def turn_in(self):
        q=self.selected()
        if q:self.app.game.turn_in(q['id']);self.refresh();self.app.refresh()

class Technician(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL);self.app=app
        tk.Label(self,text=tr('refinement_ui.0039'),bg=PANEL,fg=GOLD,font=('Segoe UI',16,'bold')).pack(pady=10)
        self.resources=tk.Label(self,bg=PANEL,fg=TEXT);self.resources.pack(pady=5)
        tabs=ttk.Notebook(self);tabs.pack(fill='both',expand=True,padx=10,pady=8)
        craft=tk.Frame(tabs,bg=PANEL);repair=tk.Frame(tabs,bg=PANEL)
        tabs.add(craft,text=tr('refinement_ui.0040'));tabs.add(repair,text=tr('refinement_ui.0041'))
        self.material=tk.StringVar(value='parts');self.amount=tk.StringVar(value='10')
        tk.Label(craft,text=tr('refinement_ui.0042'),bg=PANEL,fg=GOLD,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=12,pady=12)
        row=tk.Frame(craft,bg=PANEL);row.pack(fill='x',padx=12)
        for kind,title in [('parts',tr('refinement_ui.0043')),('fragments',tr('refinement_ui.0044'))]:
            ttk.Radiobutton(row,text=title,variable=self.material,value=kind,command=self.chances).pack(anchor='w',pady=6)
        tk.Label(craft,text=tr('refinement_ui.0045'),bg=PANEL,fg=GOLD,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=12,pady=(15,6))
        row=tk.Frame(craft,bg=PANEL);row.pack(fill='x',padx=12)
        ttk.Spinbox(row,from_=10,to=150,textvariable=self.amount,width=8).pack(side='left',padx=(0,10))
        for n in (10,30,75,150):ttk.Button(row,text=str(n),command=lambda n=n:self.amount.set(str(n))).pack(side='left',padx=4)
        self.odds_frame=tk.Frame(craft,bg=PANEL);self.odds_frame.pack(fill='x',padx=12,pady=12)
        self.chance_labels=[]
        for n,(name,color) in enumerate(r.RARITIES):
            label=tk.Label(self.odds_frame,bg='#1b2922',fg=color,text=name,font=('Segoe UI',10),padx=6,pady=9)
            label.pack(side='left',fill='x',expand=True,padx=2);self.chance_labels.append(label)
        self.preview=tk.Label(craft,bg=PANEL,fg=TEXT,justify='left',wraplength=650);self.preview.pack(fill='x',padx=12,pady=5)
        self.craft_button=ttk.Button(craft,text=tr('refinement_ui.0046'),command=self.craft);self.craft_button.pack(fill='x',padx=12,pady=12)
        self.result=Detail(craft,height=8);self.result.pack(fill='both',expand=True,padx=12,pady=8)
        self.grid=v.ItemGrid(repair,self.describe,height=150,columns=7);self.grid.pack(fill='both',expand=True,padx=10,pady=6)
        self.detail=Detail(repair,height=10);self.detail.pack(fill='x',padx=10)
        row=tk.Frame(repair,bg=PANEL);row.pack(fill='x',padx=10,pady=10)
        for target in (25,50,100):ttk.Button(row,text=tr('refinement_ui.0047', v0=target),command=lambda t=target:self.repair(t)).pack(side='left',expand=True,fill='x',padx=3)
        self.repair_status=tk.Label(repair,bg=PANEL,fg=GOLD);self.repair_status.pack(pady=5)
        self.amount.trace_add('write',lambda *a:self.chances());self.refresh()
    def chances(self):
        g=self.app.game;kind=self.material.get()
        try:amount=int(self.amount.get())
        except ValueError:amount=0
        odds=g.craft_odds(amount) if amount>=10 else [0]*5
        for n,label in enumerate(self.chance_labels):label.config(text=f'{r.RARITIES[n][0]}\n{odds[n]}%')
        available=g.count(kind);space=g.capacity-g.weight
        valid=10<=amount<=150 and amount<=available and space>=.3
        self.craft_button.config(state='normal' if valid else 'disabled')
        reason=tr('refinement_ui.0048') if valid else tr('refinement_ui.0049') if not 10<=amount<=150 else tr('refinement_ui.0050') if amount>available else tr('refinement_ui.0051')
        self.preview.config(text=tr('refinement_ui.0052', v0=available, v1=amount, v2=max(0, available - amount), v3=g.level, v4=reason))
    def refresh(self):
        g=self.app.game;self.grid.set_items([i for i in list(g.equipped.values())+g.bag if i and 'durability' in i])
        self.resources.config(text=tr('refinement_ui.0053', v0=g.money, v1=g.count('parts'), v2=g.count('fragments')))
        self.chances();self.describe(self.grid.selection)
    def describe(self,i):
        item=self.app.game.find(i)
        self.detail.config(text=description(self.app.game,item)+ (tr('refinement_ui.0054')+ ' · '.join(tr('refinement_ui.0055', v0=t, v1=self.app.game.repair_cost(item, t)) for t in (25,50,100)) if item else ''))
    def repair(self,t):
        ok=self.app.game.repair(self.grid.selection,t)
        self.repair_status.config(text=self.app.game.messages[-1] if ok else tr('refinement_ui.0056'));self.refresh();self.app.refresh()
    def craft(self):
        g=self.app.game
        try:amount=int(self.amount.get())
        except ValueError:return
        if not 10<=amount<=150:return
        before={i['id'] for i in g.bag}
        ok=g.craft_module(self.material.get(),amount)
        item=next((i for i in g.bag if i['id'] not in before),None)
        self.result.config(text=(tr('refinement_ui.0057')+description(g,item)) if ok else tr('refinement_ui.0058'))
        self.refresh();self.app.refresh()
        if ok:
            import inspection_ui
            inspection_ui.result(self.app,item)


def perks(app):
    win=app.popup(tr('refinement_ui.0059'),'780x720')
    tk.Label(win,text=tr('refinement_ui.0060', v0=app.game.pending_perks),bg=PANEL,fg=GOLD,font=('Segoe UI',15,'bold')).pack(pady=12)
    holder=tk.Canvas(win,bg=PANEL,highlightthickness=0);scroll=ttk.Scrollbar(win,command=holder.yview);scroll.pack(side='right',fill='y');holder.pack(fill='both',expand=True);holder.config(yscrollcommand=scroll.set)
    body=tk.Frame(holder,bg=PANEL);window=holder.create_window(0,0,window=body,anchor='nw')
    holder.bind('<Configure>',lambda e:holder.itemconfigure(window,width=e.width));body.bind('<Configure>',lambda e:holder.config(scrollregion=holder.bbox('all')))
    holder.bind('<MouseWheel>',lambda e:holder.yview_scroll(-1 if e.delta>0 else 1,'units'))
    symbols=['◎','▣','♥','⬡','✚','⚒','¤','◈','⚑','ϟ']
    def choose(key):
        if app.game.choose_perk(key):app.dialog=None;win.destroy();app.perk_prompted=-1;app.refresh()
    for n,(key,(name,desc)) in enumerate(p.PERKS.items()):
        card=tk.Frame(body,bg='#293b31',highlightbackground='#536957',highlightthickness=1);card.pack(fill='x',padx=14,pady=5)
        art=tk.Canvas(card,width=62,height=78,bg='#293b31',highlightthickness=0);art.pack(side='left')
        sprites.draw(art,'perk:'+key,2,9,58)
        text=tk.Frame(card,bg='#293b31');text.pack(side='left',fill='both',expand=True)
        tk.Label(text,text=tr('refinement_ui.0061', v0=name, v1=app.game.rank(key)),bg='#293b31',fg=TEXT,font=('Segoe UI',11,'bold'),anchor='w').pack(fill='x',pady=(8,3))
        tk.Label(text,text=desc,bg='#293b31',fg=MUTED,wraplength=500,justify='left',anchor='w').pack(fill='x',pady=(0,8))
        ttk.Button(card,text=tr('refinement_ui.0062'),command=lambda k=key:choose(k),state='normal' if app.game.pending_perks else 'disabled').pack(side='right',padx=10)
