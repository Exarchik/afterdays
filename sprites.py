"""PNG atlas access for Tkinter. No Pillow or image processing at runtime."""
from pathlib import Path
import json
import tkinter as tk
ROOT=Path(__file__).resolve().parent/'assets'
MANIFEST=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8')) if (ROOT/'manifest.json').exists() else {}
SIZES=(16,24,32,48,64,96,144,192)

def item_key(item):
    kind=item.get('kind')
    if kind=='trophy':return 'corpse'
    if kind=='sealed':return 'sealed'
    if kind=='ammo':return 'ammo:'+item.get('ammo_type','pistol')
    if kind=='quest':return 'quest_item'
    return item['name'] if item.get('name') in MANIFEST else kind

NPC_ALIASES={'hunter':'traveler','Друкар':'Архіваріус','Водолаз':'Інженер Лев','Метеоролог':'Астроном','Комірник':'Торговець Рейка','Лікарка':'food','Зв’язківець':'Радистка Ніка','Провідник':'traveler','Енергетик':'tech','Картограф':'Астроном','Майстер':'smith'}
def photo(widget,key,size=48):
    if key and key.startswith('npc:'):key='npc:'+NPC_ALIASES.get(key[4:],key[4:])
    if key not in MANIFEST or not hasattr(widget,'tk'):return None
    root=widget._root()
    if not hasattr(root,'_sprite_cache'):root._sprite_cache={};root._sprite_sheets={}
    size=max(16,min(192,int(size)))
    size=max(s for s in SIZES if s<=size)
    cache=(key,size)
    if cache not in root._sprite_cache:
        try:
            if size not in root._sprite_sheets:root._sprite_sheets[size]=tk.PhotoImage(master=root,file=str(ROOT/f'atlas_{size}.png'))
            image=tk.PhotoImage(master=root,width=size,height=size)
            index=MANIFEST[key]['index'];x=index%16*size;y=index//16*size
            image.tk.call(str(image),'copy',str(root._sprite_sheets[size]),'-from',x,y,x+size,y+size,'-to',0,0)
            root._sprite_cache[cache]=image
        except (OSError,tk.TclError):return None
    return root._sprite_cache[cache]

def draw(canvas,key,x,y,size=48):
    image=photo(canvas,key,size)
    if image is None:return False
    canvas.create_image(x+size/2,y+size/2,image=image,anchor='center')
    return True

BUTTONS=[('Модифікац','modify'),('Розібрати','dismantle'),('Створити модуль','craft'),('Ремонт','repair'),('Забрати','loot'),('Сховище','stash'),('Атлас','site'),('Перки','perk:tactician'),('Аптечка','med'),('Зброя','damage:kinetic'),('Взяти','journal'),('Здати','quest:supplies')]
def decorate(widget):
    for child in widget.winfo_children():
        if child.winfo_class() in ('TButton','Button'):
            text=str(child.cget('text'));key=next((k for word,k in BUTTONS if word in text),None)
            image=photo(child,key,24) if key else None
            if image:child.configure(image=image,compound='left')
        decorate(child)

def gallery(app):
    from tkinter import ttk
    win=app.popup('Арти Afterdays · 128 іконок','960x700')
    canvas=tk.Canvas(win,bg='#202b27',highlightthickness=0);scroll=ttk.Scrollbar(win,command=canvas.yview)
    scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
    canvas.bind('<MouseWheel>',lambda e:canvas.yview_scroll(-1 if e.delta>0 else 1,'units'))
    def render(event=None):
        canvas.delete('all');w=max(500,canvas.winfo_width());cols=max(4,int(w/115));cell=w/cols
        for n,key in enumerate(MANIFEST):
            x=n%cols*cell;y=n//cols*112
            draw(canvas,key,x+(cell-80)/2,y+2,80)
            canvas.create_text(x+cell/2,y+88,text=key,fill='#d7b77a',width=cell-6,font=('Segoe UI',8))
        canvas.configure(scrollregion=(0,0,w,((len(MANIFEST)+cols-1)//cols)*112))
    canvas.bind('<Configure>',render);render()
