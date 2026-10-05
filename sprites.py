from i18n import t as tr
"""PNG atlas access for Tkinter. No Pillow or image processing at runtime."""
from pathlib import Path
import json
import content
import tkinter as tk
ROOT=Path(__file__).resolve().parent/'assets'
MANIFEST=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8')) if (ROOT/'manifest.json').exists() else {}
MANIFEST.update(content.read('sprites.json'))
NPC_TEXT_BINDINGS=content.read('sprite_text_bindings.json')
SIZES=(16,24,32,48,64,96,144,192)
WEAPON_BADGE_TYPES=('kinetic','piercing','energy','electric','thermal')

def weapon_badge_key(item):
    if item.get('kind')!='weapon':return None
    from adventure import damage_type
    return f'weapon_badge:{damage_type(item)}:{max(0,min(4,int(item.get("rarity",0))))}'

def weapon_badge(canvas,item,x,y,size=24):
    return draw(canvas,weapon_badge_key(item),x,y,size)

def item_key(item):
    if item.get('kind')=='credits':return content.CONSUMABLES.get('item_credits',{}).get('sprite_id') or 'credits'
    if item.get('sprite_id') in MANIFEST:return item['sprite_id']
    if item.get('art_id') in MANIFEST:return item['art_id']
    kind=item.get('kind')
    if kind=='trophy':return 'trophy_'+content.monster_id(item.get('monster_type_id',item.get('monster_kind',0)))
    if kind=='repairkit':return 'repairkit'
    if kind=='sealed':return 'sealed'
    if kind=='ammo':return 'ammo:'+item.get('ammo_type','pistol')
    if kind=='quest' and not item.get('quest_repair'):
        if item.get('delivery') or item.get('type_id')=='quest_parcel':return 'courier_parcel'
        key={tr('exp.parcel'):'stash_parcel',tr('scav.relic'):'relic_item',tr('scav.junk_part'):'junk_component'}.get(item.get('name'))
        return key or 'quest_item'
    ident=item.get('type_id')
    data=content.EQUIPMENT.get(ident) or content.MODULE_DATA.get(ident)
    if data:return data['sprite_id']
    return item['name'] if item.get('name') in MANIFEST else kind

NPC_ALIASES={'hunter':'traveler',tr('sprites.0001'):tr('sprites.0011'),tr('sprites.0002'):tr('sprites.0012'),tr('sprites.0003'):tr('sprites.0013'),tr('sprites.0004'):tr('sprites.0014'),tr('sprites.0005'):'food',tr('sprites.0006'):tr('sprites.0015'),tr('sprites.0007'):'traveler',tr('sprites.0008'):'tech',tr('sprites.0009'):tr('sprites.0016'),tr('sprites.0010'):'smith'}
def npc_key(name):
    if name=='hunter':return 'npc_hunter'
    # Prefer a dedicated portrait before the legacy shared-portrait aliases.
    direct=next((asset for token,asset in NPC_TEXT_BINDINGS.items() if tr(token)==name),None)
    if direct:return direct
    return 'npc:'+NPC_ALIASES.get(name,name)


def photo(widget,key,size=48):
    if key and key.startswith('npc:'):key=npc_key(key[4:])
    if not hasattr(widget,'tk'):return None
    root=widget._root()
    library=getattr(root,'_editor_art_library',None)
    if library is not None:
        image=library.photo(widget,key,size)
        if image is not None:return image
    if key not in MANIFEST:return None
    if not hasattr(root,'_sprite_cache'):root._sprite_cache={};root._sprite_sheets={}
    size=max(16,min(192,int(size)))
    size=max(s for s in SIZES if s<=size)
    cache=(key,size)
    if cache not in root._sprite_cache:
        try:
            entry=MANIFEST[key];sheet=entry.get('sheet','atlas');sheet_key=(sheet,size);columns=entry.get('columns',16)
            if sheet_key not in root._sprite_sheets:root._sprite_sheets[sheet_key]=tk.PhotoImage(master=root,file=str(ROOT/f'{sheet}_{size}.png'))
            image=tk.PhotoImage(master=root,width=size,height=size)
            index=entry['index'];x=index%columns*size;y=index//columns*size
            image.tk.call(str(image),'copy',str(root._sprite_sheets[sheet_key]),'-from',x,y,x+size,y+size,'-to',0,0)
            root._sprite_cache[cache]=image
        except (OSError,tk.TclError):return None
    return root._sprite_cache[cache]

def draw(canvas,key,x,y,size=48):
    image=photo(canvas,key,size)
    if image is None:return False
    canvas.create_image(x+size/2,y+size/2,image=image,anchor='center')
    return True

BUTTONS=[(tr('sprites.0017'),'modify'),(tr('sprites.0018'),'dismantle'),(tr('sprites.0019'),'craft'),(tr('sprites.0020'),'repair'),(tr('sprites.0021'),'loot'),(tr('sprites.0022'),'stash'),(tr('sprites.0023'),'site'),(tr('sprites.0024'),'perk:tactician'),(tr('sprites.0025'),'med'),(tr('sprites.0026'),'damage:kinetic'),(tr('sprites.0027'),'journal'),(tr('sprites.0028'),'quest:supplies')]
def decorate(widget):
    for child in widget.winfo_children():
        if child.winfo_class() in ('TButton','Button'):
            text=str(child.cget('text'));key=next((k for word,k in BUTTONS if word in text),None)
            image=photo(child,key,24) if key else None
            if image:child.configure(image=image,compound='left')
        decorate(child)

def gallery(app):
    from tkinter import ttk
    win=app.popup(tr('sprites.0029'),'960x700')
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


def inventory_photo(widget,item,width):
    """Fitted artwork with a pre-rendered alpha gradient; stdlib Tk runtime."""
    key=item_key(item)
    if key not in MANIFEST or width<48:return None
    entry=MANIFEST[key];index=entry['index']+(128 if entry.get('sheet')=='trophies' else 0)
    width=max(w for w in (48,56,64,80,96,128) if w<=width)
    root=widget._root()
    if not hasattr(root,'_inventory_images'):root._inventory_images={};root._inventory_sheets={}
    sheet=entry.get('inventory_sheet','inventory')
    cache=(sheet,index,width)
    if cache not in root._inventory_images:
        try:
            sheet_key=(sheet,width)
            if sheet_key not in root._inventory_sheets:root._inventory_sheets[sheet_key]=tk.PhotoImage(master=root,file=str(ROOT/f'{sheet}_{width}.png'))
            image=tk.PhotoImage(master=root,width=width,height=72)
            columns=entry.get('inventory_columns',16)
            x,y=index%columns*width,index//columns*72
            image.tk.call(str(image),'copy',str(root._inventory_sheets[sheet_key]),'-from',x,y,x+width,y+72,'-to',0,0)
            root._inventory_images[cache]=image
        except (OSError,tk.TclError):return None
    return root._inventory_images[cache]


def quest_key(q):
    if q.get("kind")=="recruit_mayor":return "quest:recruit_tech"
    return "quest:metro" if "metro_city" in q else "quest:"+q["kind"]

def corpse_key(corpse):
    return "corpse:"+content.monster_id(corpse.get("type_id",corpse.get("kind",0)))
