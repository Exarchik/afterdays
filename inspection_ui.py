from i18n import t as tr
"""Nested inspection/result dialogs with a short chest-opening animation."""
import content
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
    text+=tr('inspection_ui.0001', v0=p.item_value(item))
    for n,mod in enumerate(item.get('modules',[]),1):text+=tr('inspection_ui.0002', v0=n)+description(g,mod)
    return text

def monster_text(g,e):
    lines=[e['name'],tr('inspection_ui.0003', v0=e.get('level', 1))+{'normal':tr('inspection_ui.0004'),'rare':tr('inspection_ui.0005'),'mythic':tr('inspection_ui.0006')}[e.get('grade','normal')],
      tr('inspection_ui.0007'),tr('inspection_ui.0008', v0=e['hp'], v1=e['max_hp']),tr('inspection_ui.0009', v0=e.get('attack', 0)),
      tr('inspection_ui.0010', v0=e.get('defense', e.get('armor', 0))),tr('inspection_ui.0011', v0=e['damage']),
      tr('inspection_ui.0012'),tr('inspection_ui.0013', v0=e['range']),tr('inspection_ui.0014', v0=e['speed']),
      tr('inspection_ui.0015', v0=3 if e['kind'] == 8 else 0),tr('inspection_ui.0016', v0=g.enemy_xp(e)),
      tr('inspection_ui.0017')+(tr('inspection_ui.0018') if g.battle.get('dungeon') and not e.get('awake') else tr('inspection_ui.0019')),
      tr('inspection_ui.0020', v0=balance.multiplier(e.get('attack', 0), g.defense)),
      tr('inspection_ui.0021', v0=min(45, g.protection_stat('evasion'))),tr('inspection_ui.0022')]
    for key,(label,color) in a.DAMAGE_TYPES.items():
        value=e.get('resists',{}).get(key,0);lines.append(f'{label}\t'+(tr('inspection_ui.0023', v0=value) if value>0 else tr('inspection_ui.0024', v0=-value) if value<0 else '0%'))
    desc=content.t(content.monster_id(e)+'.description')
    if desc:lines.append(desc)
    if g.weapon:
        valid,why,chance=g.shot_info(e)
        lines += [tr('inspection_ui.0025', v0=balance.multiplier(p.stats(g.weapon).get('attack', 0), e.get('defense', 0))),tr('inspection_ui.0026', v0=chance) if valid else tr('inspection_ui.0027')+why]
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
    ttk.Button(win,text=tr('inspection_ui.0028'),command=close).pack(side='bottom',fill='x',padx=12,pady=10)
    return win

def inspect_item(app,item):
    if not item:return
    win=window(app,tr('inspection_ui.0029')+item['name'])
    art=tk.Canvas(win,bg=PANEL,height=94,highlightthickness=0);art.pack(fill='x')
    from visuals import icon
    icon(art,item,18,5,80)
    detail=Detail(win,height=20);detail.pack(fill='both',expand=True,padx=12,pady=8);detail.config(text=item_text(app.game,item))

def inspect_monster(app,event):
    if not app.game.battle:return
    pos=app.cell(event);enemy=next((e for e in app.game.battle['enemies'] if tuple(e['pos'])==pos),None)
    if not enemy:return
    win=window(app,tr('inspection_ui.0030')+enemy['name']);art=tk.Canvas(win,bg=PANEL,height=96,highlightthickness=0);art.pack(fill='x')
    sprites.draw(art,'monster:'+str(enemy['kind']),18,5,86)
    detail=Detail(win,height=22);detail.pack(fill='both',expand=True,padx=12,pady=8);detail.config(text=monster_text(app.game,enemy))

def result(app,item,animate=False):
    win=window(app,tr('inspection_ui.0031') if animate else tr('inspection_ui.0032'))
    art=tk.Canvas(win,bg=PANEL,height=130,highlightthickness=0);art.pack(fill='x',pady=10)
    heading=tk.Label(win,bg=PANEL,fg=GOLD,font=('Segoe UI',14,'bold'));heading.pack(pady=5)
    detail=Detail(win,height=20);detail.pack(fill='both',expand=True,padx=12,pady=8)
    def reveal():
        if not win.winfo_exists():return
        from visuals import icon
        art.delete('all');icon(art,item,30,10,105);heading.config(text=tr('inspection_ui.0033')+item['name']);detail.config(text=item_text(app.game,item))
    def frame(n=0):
        if not win.winfo_exists():return
        art.delete('all');x=55+(3 if n%2 else -3)
        art.create_rectangle(x,38,x+100,100,fill='#715738',outline='#e2b66c',width=3)
        art.create_line(x,57-n*2,x+100,57-n*2,fill='#f4d390',width=6)
        art.create_rectangle(x+44,57,x+56,74,fill='#e2b66c',outline='')
        heading.config(text=tr('inspection_ui.0034'))
        if n<10:win.after(55,lambda:frame(n+1))
        else:reveal()
    if animate:frame()
    else:reveal()
