"""Dark card lists, readable comparisons and workshop controls."""
import tkinter as tk
import sprites
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
                tag='header' if line.startswith('Характеристика\t') else 'good' if '[+]' in line else 'bad' if '[-]' in line else 'title' if n==0 else ''
                self.text.insert('end',line.replace('[+]','').replace('[-]','')+'\n',tag)
            self.text.configure(state='disabled')
        if cnf or kw:super().configure(cnf,**kw)


def description(game,item):
    if not item:return 'Виберіть предмет.'
    if item['kind']=='sealed':return f'Запечатана скриня\nВміст і його стан невідомі.\nВага\t{p.item_weight(item):g} кг\nВиберіть у рюкзаку й натисніть «Використати» поза боєм.'
    kind=item['kind'];lines=[item['name'],(f'L{item.get("level",1)} · ' if kind in ('weapon','armor','helmet','module') else '')+r.RARITIES[item['rarity']][0]]
    current=game.weapon if kind=='weapon' else game.equipped.get(kind)
    compare=current is not None and current['id']!=item['id']
    if compare:lines.append('Порівняння: '+current['name'])
    def field(label,value,base=None,lower=False,unit=''):
        tail=''
        if compare and base is not None and value!=base:
            diff=value-base;good=(diff<0) if lower else (diff>0)
            tail=f'{diff:+g}{unit} '+('[+]' if good else '[-]')
        lines.append(f'{label}\t{value:g}{unit}\t'+(tail or '—'))
    lines.append('Характеристика\tЗначення\tРізниця')
    field('Вага',p.item_weight(item),p.item_weight(current) if current else None,True,' кг')
    if 'qty' in item:lines.append(f'У стеку: {item["qty"]}')
    if 'durability' in item:field('Стан',item['durability'],current.get('durability',100) if current else None,unit='%')
    if kind=='weapon':
        import adventure
        field('Постріл',item['ap'],current['ap'] if current else None,True,' ОД')
        lines.append('Тип шкоди\t'+adventure.DAMAGE_TYPES[adventure.damage_type(item)][0])
        lines.append('Набої\t'+p.AMMO[item.get('ammo_type','pistol')][0])
    values=p.stats(item);baseline=p.stats(current) if current else {}
    for key in dict.fromkeys(list(values)+list(baseline)):
        if values.get(key) or (compare and baseline.get(key)):
            field(r.STAT_NAMES.get(key,key),values.get(key,0),baseline.get(key,0),unit='%' if key in ('accuracy','crit','evasion') else '')
            if kind=='module':lines[-1]+=' [-]' if values.get(key,0)<0 else ' [+]'
    if 'slots' in item:
        field('Слоти',item['slots'],current['slots'] if current else None)
        lines.append(f'Модулі ({len(item["modules"])}/{item["slots"]}):')
        lines.extend('  • '+m['name']+' · '+r.RARITIES[m['rarity']][0] for m in item['modules'])
        if not item['modules']:lines.append('  Порожньо')
    elif kind=='module':
        lines.append('Для: '+('зброї' if item['target']=='weapon' else 'броні / шоломів'))
        if item.get('tradeoff'):lines.append('Посилений модуль із побічним ефектом')
    elif kind=='med':lines.append(f'Лікує 50% максимальних HP: {__import__("math").ceil(game.max_hp*.5)} HP')
    elif kind=='rad':lines.append('100% захисту від радіації на 10 ходів мапи. Повторне вживання оновлює термін.')
    elif kind=='food':lines.append('Лікує 14 HP + бонус медика.')
    elif kind=='trophy':lines.append('Мисливець платить подвійну базову ціну; за квестом — ще вигідніше.')
    elif kind in ('parts','fragments'):lines.append('Матеріал для модулів '+('зброї' if kind=='parts' else 'броні')+' у техніка. Не важить.')
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
        if mayor:ttk.Button(self,text='Взяти вибране завдання',command=self.accept).pack(fill='x',padx=8,pady=3)
        ttk.Button(self,text='Здати вибране завдання',command=self.turn_in).pack(fill='x',padx=8,pady=3)
        if not mayor:ttk.Button(self,text='Атлас [M]',command=app.atlas).pack(fill='x',padx=8,pady=3)
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
                c.create_text(15,y+17,text=('▾' if self.open_done else '▸')+f' Завершені завдання ({len(done)})',fill=MUTED,anchor='w')
                self.rects.append((y,y+34,'done'));y+=40;continue
            color='#d0a0f5' if q.get('unique') else '#8aa78e' if q['status']=='done' else GOLD
            c.create_rectangle(5,y,w-5,y+89,fill='#334a3d' if q['id']==self.selection else '#22332b',outline=color)
            c.create_oval(13,y+13,53,y+53,fill='#17241e',outline=color,width=2)
            if not sprites.draw(c,'quest:'+q['kind'],12,y+12,42):c.create_text(33,y+33,text=QUEST_ICONS[q['kind']],fill=color,font=('Segoe UI',21))
            c.create_text(64,y+9,text=('★ ' if q.get('unique') else '')+f'L{q.get("level",q.get("zone",1))} · '+q['title'],width=w-80,anchor='nw',fill=color,font=('Segoe UI',10,'bold'))
            state='Нове' if q['status']=='offered' else 'Виконано' if q['status']=='done' else 'Можна здати' if self.app.game.quest_ready(q) else f'Прогрес: {q["progress"]}/{q["goal"]}'
            c.create_text(64,y+49,text=state,anchor='nw',fill=TEXT,font=('Segoe UI',9))
            c.create_text(16,y+75,text=f'{q.get("money",q.get("reward",0))} кр. · {q.get('xp_reward',80 if q.get('unique') else 40)} XP',anchor='w',fill=MUTED,font=('Segoe UI',9))
            self.rects.append((y,y+89,q['id']));y+=96
        c.config(scrollregion=(0,0,w,y))
    def click(self,e):
        y=self.canvas.canvasy(e.y);key=next((key for a,b,key in self.rects if a<=y<=b),None)
        if key=='done':self.open_done=not self.open_done
        else:self.selection=key
        self.paint();self.describe()
    def describe(self):
        q=self.selected();self.detail.config(text=self.app.game.quest_text(q) if q else 'Виберіть картку завдання. Після 3 виконаних завдань у місті мер відкриває найближчі міста.')
    def accept(self):
        q=self.selected()
        if q:self.app.game.accept_quest(q['id']);self.refresh();self.app.refresh()
    def turn_in(self):
        q=self.selected()
        if q:self.app.game.turn_in(q['id']);self.refresh();self.app.refresh()

class Technician(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL);self.app=app
        tk.Label(self,text='МАЙСТЕРНЯ',bg=PANEL,fg=GOLD,font=('Segoe UI',16,'bold')).pack(pady=10)
        self.resources=tk.Label(self,bg=PANEL,fg=TEXT);self.resources.pack(pady=5)
        tabs=ttk.Notebook(self);tabs.pack(fill='both',expand=True,padx=10,pady=8)
        craft=tk.Frame(tabs,bg=PANEL);repair=tk.Frame(tabs,bg=PANEL)
        tabs.add(craft,text='⚒ Створення модулів');tabs.add(repair,text='Ремонт спорядження')
        self.material=tk.StringVar(value='parts');self.amount=tk.StringVar(value='10')
        tk.Label(craft,text='1. Оберіть, який модуль створити',bg=PANEL,fg=GOLD,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=12,pady=12)
        row=tk.Frame(craft,bg=PANEL);row.pack(fill='x',padx=12)
        for kind,title in [('parts','Модуль зброї · запчастини'),('fragments','Модуль броні / шолома · фрагменти')]:
            ttk.Radiobutton(row,text=title,variable=self.material,value=kind,command=self.chances).pack(anchor='w',pady=6)
        tk.Label(craft,text='2. Кількість матеріалу',bg=PANEL,fg=GOLD,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=12,pady=(15,6))
        row=tk.Frame(craft,bg=PANEL);row.pack(fill='x',padx=12)
        ttk.Spinbox(row,from_=10,to=150,textvariable=self.amount,width=8).pack(side='left',padx=(0,10))
        for n in (10,30,75,150):ttk.Button(row,text=str(n),command=lambda n=n:self.amount.set(str(n))).pack(side='left',padx=4)
        self.odds_frame=tk.Frame(craft,bg=PANEL);self.odds_frame.pack(fill='x',padx=12,pady=12)
        self.chance_labels=[]
        for n,(name,color) in enumerate(r.RARITIES):
            label=tk.Label(self.odds_frame,bg='#1b2922',fg=color,text=name,font=('Segoe UI',10),padx=6,pady=9)
            label.pack(side='left',fill='x',expand=True,padx=2);self.chance_labels.append(label)
        self.preview=tk.Label(craft,bg=PANEL,fg=TEXT,justify='left',wraplength=650);self.preview.pack(fill='x',padx=12,pady=5)
        self.craft_button=ttk.Button(craft,text='СТВОРИТИ МОДУЛЬ',command=self.craft);self.craft_button.pack(fill='x',padx=12,pady=12)
        self.result=Detail(craft,height=8);self.result.pack(fill='both',expand=True,padx=12,pady=8)
        self.grid=v.ItemGrid(repair,self.describe,height=150,columns=7);self.grid.pack(fill='both',expand=True,padx=10,pady=6)
        self.detail=Detail(repair,height=10);self.detail.pack(fill='x',padx=10)
        row=tk.Frame(repair,bg=PANEL);row.pack(fill='x',padx=10,pady=10)
        for target in (25,50,100):ttk.Button(row,text=f'Ремонт до {target}%',command=lambda t=target:self.repair(t)).pack(side='left',expand=True,fill='x',padx=3)
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
        reason='Готово до створення.' if valid else 'Вкажіть ціле число від 10 до 150.' if not 10<=amount<=150 else 'Недостатньо матеріалів.' if amount>available else 'Потрібно 0,3 кг вільної ваги.'
        self.preview.config(text=f'Наявно: {available} · витрата: {amount} · залишиться: {max(0,available-amount)}\nМодуль рівня {g.level} · вага 0,3 кг · без оплати кредитами.\n{reason} Більше матеріалів — вищі шанси рідкісного модуля; гарантії немає.')
    def refresh(self):
        g=self.app.game;self.grid.set_items([i for i in list(g.equipped.values())+g.bag if i and 'durability' in i])
        self.resources.config(text=f'{g.money} кр. · Запчастини: {g.count("parts")} · Фрагменти: {g.count("fragments")}')
        self.chances();self.describe(self.grid.selection)
    def describe(self,i):
        item=self.app.game.find(i)
        self.detail.config(text=description(self.app.game,item)+ ('\nРемонт: '+ ' · '.join(f'{t}%: {self.app.game.repair_cost(item,t)} кр.' for t in (25,50,100)) if item else ''))
    def repair(self,t):
        ok=self.app.game.repair(self.grid.selection,t)
        self.repair_status.config(text=self.app.game.messages[-1] if ok else 'Перевірте стан предмета й кошти.');self.refresh();self.app.refresh()
    def craft(self):
        g=self.app.game
        try:amount=int(self.amount.get())
        except ValueError:return
        if not 10<=amount<=150:return
        before={i['id'] for i in g.bag}
        ok=g.craft_module(self.material.get(),amount)
        item=next((i for i in g.bag if i['id'] not in before),None)
        self.result.config(text=('СТВОРЕНО\n'+description(g,item)) if ok else 'Створення недоступне: перевірте матеріали та вільну вагу.')
        self.refresh();self.app.refresh()
        if ok:
            import inspection_ui
            inspection_ui.result(self.app,item)


def perks(app):
    win=app.popup('Перки · розвиток персонажа','780x720')
    tk.Label(win,text=f'ПЕРКИ / доступно: {app.game.pending_perks}',bg=PANEL,fg=GOLD,font=('Segoe UI',15,'bold')).pack(pady=12)
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
        tk.Label(text,text=f'{name} · ранг {app.game.rank(key)}',bg='#293b31',fg=TEXT,font=('Segoe UI',11,'bold'),anchor='w').pack(fill='x',pady=(8,3))
        tk.Label(text,text=desc,bg='#293b31',fg=MUTED,wraplength=500,justify='left',anchor='w').pack(fill='x',pady=(0,8))
        ttk.Button(card,text='Вивчити',command=lambda k=key:choose(k),state='normal' if app.game.pending_perks else 'disabled').pack(side='right',padx=10)
