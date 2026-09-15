"""Live character sheet and cartographer service."""
import tkinter as tk
from tkinter import ttk
import progression as p
import adventure as a
from visuals import PANEL, TEXT, GOLD

def player_text(g):
    w=g.weapon;s=p.stats(w) if w else {};base=s.get('damage',0)+2*(g.level-1) if w else 0
    lines=[f'РІВЕНЬ {g.level} · {g.money} кр.',f'Здоров’я: {g.hp}/{g.max_hp}',
           f'ОД: {g.battle["ap"] if g.battle else g.max_ap}/{g.max_ap}',
           f'Захист: {g.defense} · ухилення: {min(45,g.protection_stat("evasion"))}%',
           f'Регенерація: {g.protection_stat("regen")} HP/раунд',
           f'Вага: {g.weight:.1f}/{g.capacity:.0f} кг',f'Радіозахист: {g.rad_turns} ходів',
           '', 'АКТИВНА ЗБРОЯ',w['name'] if w else 'Не екіпірована']
    if w:
        lines += [f'Шкода до захисту цілі: {max(1,base-2)}–{base+2}',
                  f'Тип: {a.DAMAGE_TYPES[a.damage_type(w)][0]}',
                  f'Критичний шанс: {min(65,5+s.get("crit",0))}% · множник ×1.6',
                  f'Точність зброї: {s.get("accuracy",0)}% · перки +{4*g.rank("marksman")} п.п.',
                  'Фінальна точність залежить від відстані.',
                  f'Дальність: {s.get("range",0)} · Атака: {s.get("attack",0)}',
                  f'Постріл: {w["ap"]} ОД · стан: {w.get("durability",100):.0f}%',
                  f'{p.AMMO[w.get("ammo_type","pistol")][0]}: {g.count("ammo",w.get("ammo_type","pistol"))}']
    lines+=['','ПЕРКИ',f'Доступно для вибору: {g.pending_perks}']
    for key,rank in g.perks.items():
        name,desc=p.PERKS[key];lines += [f'{name} · ранг {rank}',desc]
    if not g.perks:lines+=['Поки що немає. Новий вибір кожні 2 рівні.']
    labels={'damage':'шкода','range':'дальність','accuracy':'точність','crit':'крит. шанс','attack':'Атака',
            'defense':'захист','evasion':'ухилення','vitality':'макс. HP','capacity':'вантажність','regen':'регенерація'}
    lines+=['','МОДУЛІ ЕКІПІРОВАНИХ РЕЧЕЙ']
    for item in g.equipped.values():
        if not item:continue
        for module in item.get('modules',[]):
            lines += [item['name']+' → '+module['name'],', '.join(f'{labels.get(k,k)} {v:+g}' for k,v in module['stats'].items())]
    return '\n'.join(lines)

class PlayerPanel(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL);self.app=app
        self.xp=tk.Label(self,bg=PANEL,fg=GOLD);self.xp.pack(pady=(12,4))
        self.bar=ttk.Progressbar(self);self.bar.pack(fill='x',padx=12,pady=4)
        body=tk.Frame(self,bg=PANEL);body.pack(fill='both',expand=True,padx=8,pady=8)
        scroll=ttk.Scrollbar(body);scroll.pack(side='right',fill='y')
        self.text=tk.Text(body,bg=PANEL,fg=TEXT,wrap='word',font=('Segoe UI',10),relief='flat',width=30,yscrollcommand=scroll.set)
        self.text.pack(fill='both',expand=True);scroll.config(command=self.text.yview)
    def refresh(self):
        g=self.app.game;low=p.xp_for_level(g.level);high=p.xp_for_level(g.level+1)
        self.xp.config(text=f'Досвід: {g.xp-low}/{high-low} · до рівня: {high-g.xp}')
        self.bar.config(maximum=high-low,value=g.xp-low)
        pos=self.text.yview()[0];self.text.config(state='normal');self.text.delete('1.0','end')
        self.text.insert('end',player_text(g));self.text.config(state='disabled');self.text.yview_moveto(pos)

def cartographer(app):
    g=app.game
    if not g.cartographer:return
    window=app.popup('Картограф','420x240');t=g.traveler;size=t['box'][2]
    tk.Label(window,text=f'Фрагмент мапи {size}×{size}\nПоруч із вами · {t["price"]} кр.',bg=PANEL,fg=TEXT,font=('Segoe UI',13),pady=24).pack()
    status=tk.Label(window,text='Цей фрагмент уже придбано.' if t['purchased'] else 'Відкриває туман на мапі та в атласі.',bg=PANEL,fg=GOLD);status.pack()
    def buy():
        if g.buy_map():status.config(text='Мапу відкрито!');button.config(state='disabled')
        else:status.config(text=g.messages[-1])
        app.refresh()
    button=ttk.Button(window,text='Придбати мапу',command=buy,state='disabled' if t['purchased'] else 'normal');button.pack(pady=16)


def draw_metro(canvas,g,t,ox,oy):
    stations=g.metro_unlocked
    def point(n):
        x,y=g.cities[n];return ox+(x+.5)*t,oy+(y+.5)*t
    for city in stations[1:]:
        canvas.create_line(*point(0),*point(city),fill='#58d9d1',width=3,dash=(7,4))
    for city in stations:
        x,y=point(city)
        canvas.create_oval(x-7,y-7,x+7,y+7,fill='#173b3a',outline='#58d9d1',width=2)
        canvas.create_text(x,y,text='М',fill='#9afbf2',font=('Segoe UI',8,'bold'))


def metro(app):
    g=app.game
    if g.battle or g.city not in g.metro_unlocked:return
    window=app.popup('Метро · підземна дрезина','540x380')
    tk.Label(window,text='МЕТРО / '+g.city_name(g.city),bg=PANEL,fg=GOLD,font=('Segoe UI',14,'bold')).pack(pady=18)
    tk.Label(window,text='50 кредитів за поїздку · без боїв і радіації\nЧас: наземний маршрут ÷ 5, округлено вгору.',bg=PANEL,fg=TEXT).pack(pady=8)
    destinations=[n for n in g.metro_unlocked if n!=g.city]
    status=tk.Label(window,text='' if destinations else 'Інші станції ще не відремонтовані.\nЗнайдіть їхні міста та зверніться до мерів.',bg=PANEL,fg=GOLD,wraplength=490)
    status.pack(pady=8)
    def travel(destination):
        if g.metro_travel(destination):
            app.dialog=None;window.destroy();app.refresh()
        else:status.config(text=g.messages[-1])
    for city in destinations:
        cost=g.metro_cost(city)
        if cost:
            ttk.Button(window,text=f'{g.city_name(city)} · {cost[1]} ходів · 50 кр.',command=lambda city=city:travel(city)).pack(fill='x',padx=24,pady=6)
