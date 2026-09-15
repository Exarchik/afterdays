"""Nested inspection/result dialogs with a short chest-opening animation."""
import tkinter as tk
from tkinter import ttk
import afterdays as r
import adventure as a
import progression as p
import balance
import sprites
from refinement_ui import Detail,description
from visuals import PANEL,TEXT,GOLD

def item_text(g,item):
    text=description(g,item)
    if item['kind']=='sealed':return text
    text+=f'\nБазова вартість\t{p.item_value(item)} кр.'
    for n,mod in enumerate(item.get('modules',[]),1):text+=f'\n\nМОДУЛЬ {n}\n'+description(g,mod)
    return text

def monster_text(g,e):
    lines=[e['name'],f'Рівень {e.get("level",1)} · '+{'normal':'Звичайний','rare':'Рідкісний','mythic':'Міфічний'}[e.get('grade','normal')],
      'Характеристика\tЗначення',f'Здоров’я\t{e["hp"]}/{e["max_hp"]}',f'Атака\t{e.get("attack",0)}',
      f'Захист\t{e.get("defense",e.get("armor",0))}',f'Базова шкода\t{e["damage"]}',
      f'Випадкова добавка\t−2…+2',f'Дальність\t{e["range"]}',f'Рух за раунд\t{e["speed"]} клітин',
      f'Регенерація\t{3 if e["kind"]==8 else 0} HP/раунд',f'Нагорода\t{g.enemy_xp(e)} XP',
      'Стан\t'+('Неактивний (пробудження в межах 5 клітин і видимості)' if g.battle.get('dungeon') and not e.get('awake') else 'Активний'),
      f'Проти вашого захисту\t×{balance.multiplier(e.get("attack",0),g.defense):.2f}',
      f'Ваше ухилення\t{min(45,g.protection_stat("evasion"))}%','\nОПОРИ ТИПАМ ШКОДИ']
    for key,(label,color) in a.DAMAGE_TYPES.items():
        value=e.get('resists',{}).get(key,0);lines.append(f'{label}\t'+(f'опір {value}%' if value>0 else f'вразливість +{-value}%' if value<0 else '0%'))
    if g.weapon:
        valid,why,chance=g.shot_info(e)
        lines += [f'Ваша Атака проти цілі\t×{balance.multiplier(p.stats(g.weapon).get("attack",0),e.get("defense",0)):.2f}',f'Ваш шанс влучання\t{chance}%' if valid else 'Постріл недоступний: '+why]
    return '\n'.join(lines)

def window(app,title):
    previous=app.dialog;parent=previous if previous and previous.winfo_exists() else app.root
    win=tk.Toplevel(parent);win.title(title);win.configure(bg=PANEL)
    w,h=min(650,win.winfo_screenwidth()-40),min(720,win.winfo_screenheight()-80)
    win.geometry(f'{w}x{h}+{max(0,(win.winfo_screenwidth()-w)//2)}+{max(0,(win.winfo_screenheight()-h)//2)}')
    win.transient(parent);win.grab_set();app.dialog=win
    def close():
        win.destroy();app.dialog=previous if previous and previous.winfo_exists() else None
        if app.dialog:app.dialog.grab_set()
    win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',lambda e:close())
    ttk.Button(win,text='Закрити',command=close).pack(side='bottom',fill='x',padx=12,pady=10)
    return win

def inspect_item(app,item):
    if not item:return
    win=window(app,'Предмет · '+item['name'])
    art=tk.Canvas(win,bg=PANEL,height=94,highlightthickness=0);art.pack(fill='x')
    from visuals import icon
    icon(art,item,18,5,80)
    detail=Detail(win,height=20);detail.pack(fill='both',expand=True,padx=12,pady=8);detail.config(text=item_text(app.game,item))

def inspect_monster(app,event):
    if not app.game.battle:return
    pos=app.cell(event);enemy=next((e for e in app.game.battle['enemies'] if tuple(e['pos'])==pos),None)
    if not enemy:return
    win=window(app,'Мутант · '+enemy['name']);art=tk.Canvas(win,bg=PANEL,height=96,highlightthickness=0);art.pack(fill='x')
    sprites.draw(art,'monster:'+str(enemy['kind']),18,5,86)
    detail=Detail(win,height=22);detail.pack(fill='both',expand=True,padx=12,pady=8);detail.config(text=monster_text(app.game,enemy))

def result(app,item,animate=False):
    win=window(app,'Вміст скрині' if animate else 'Створений модуль')
    art=tk.Canvas(win,bg=PANEL,height=130,highlightthickness=0);art.pack(fill='x',pady=10)
    heading=tk.Label(win,bg=PANEL,fg=GOLD,font=('Segoe UI',14,'bold'));heading.pack(pady=5)
    detail=Detail(win,height=20);detail.pack(fill='both',expand=True,padx=12,pady=8)
    def reveal():
        if not win.winfo_exists():return
        from visuals import icon
        art.delete('all');icon(art,item,30,10,105);heading.config(text='Ви отримали: '+item['name']);detail.config(text=item_text(app.game,item))
    def frame(n=0):
        if not win.winfo_exists():return
        art.delete('all');x=55+(3 if n%2 else -3)
        art.create_rectangle(x,38,x+100,100,fill='#715738',outline='#e2b66c',width=3)
        art.create_line(x,57-n*2,x+100,57-n*2,fill='#f4d390',width=6)
        art.create_rectangle(x+44,57,x+56,74,fill='#e2b66c',outline='')
        heading.config(text='Відкриваємо скриню…')
        if n<10:win.after(55,lambda:frame(n+1))
        else:reveal()
    if animate:frame()
    else:reveal()
