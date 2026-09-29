"""Offline art preparation; the game still loads ordinary pre-rendered PNG sheets."""
import copy
import io
from pathlib import Path
import re
import hashlib
import sys

SIZES=(16,24,32,48,64,96,144,192)
WIDTHS=(48,56,64,80,96,128)
GROUPS={'events':'Події','weapons':'Зброя','armor':'Броня та шоломи','modules':'Модулі',
        'monsters':'Монстри','corpses':'Рештки','trophies':'Трофеї','other':'Інше'}
DEFAULTS=dict(fit='contain',padding=4,trim=True,rotation=0,mirror=False,crop=None)

def pillow():
    try:
        from PIL import Image,ImageOps
    except ImportError as exc:
        raise ValueError(
            'Не вдалося завантажити Pillow для імпорту й обробки артів.\n'
            f'Python редактора: {sys.executable}\n'
            f'Встановіть Pillow для цього Python (команда для PowerShell):\n'
            f'& "{sys.executable}" -m pip install Pillow\n\n'
            f'Причина: {exc}'
        ) from exc
    return Image,ImageOps

def decode(source):
    Image,ImageOps=pillow()
    try:
        with Image.open(source) as image:
            if image.width*image.height>40_000_000:raise ValueError('Зображення завелике: максимум 40 мегапікселів.')
            if getattr(image,'n_frames',1)>1:raise ValueError('Виберіть статичне зображення, а не анімацію.')
            return ImageOps.exif_transpose(image).convert('RGBA')
    except Image.DecompressionBombError as exc:raise ValueError('Зображення завелике: максимум 40 мегапікселів.') from exc

def encode(image):
    stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()

def transformed(source,settings):
    Image,_=pillow();image=source.copy();crop=settings.get('crop')
    if crop is not None:
        if len(crop)!=4 or any(type(n) is not int for n in crop):raise ValueError('Обрізання: потрібні чотири цілі координати.')
        x,y,right,bottom=crop
        if not (0<=x<right<=image.width and 0<=y<bottom<=image.height):raise ValueError('Область обрізання виходить за зображення.')
        image=image.crop(crop)
    rotation=settings.get('rotation',0)
    if rotation not in (0,90,180,270):raise ValueError('Поворот: 0, 90, 180 або 270°.')
    if rotation:image=image.rotate(rotation,expand=True)
    if settings.get('mirror'):image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if settings.get('trim',True):
        box=image.getchannel('A').getbbox()
        if box:image=image.crop(box)
    if not image.getchannel('A').getbbox():raise ValueError('Зображення повністю прозоре.')
    return image

def tile(source,settings,size):
    Image,ImageOps=pillow();image=transformed(source,settings)
    padding=settings.get('padding',4)
    if not isinstance(padding,(int,float)) or not 0<=padding<=40:raise ValueError('Відступ має бути від 0 до 40%.')
    pad=round(size*padding/100);side=max(1,size-2*pad)
    fit=settings.get('fit','contain')
    if fit=='contain':image.thumbnail((side,side),Image.Resampling.LANCZOS)
    elif fit=='cover':image=ImageOps.fit(image,(side,side),method=Image.Resampling.LANCZOS)
    else:raise ValueError('Невідомий спосіб підгонки.')
    result=Image.new('RGBA',(size,size));result.alpha_composite(image,((size-image.width)//2,(size-image.height)//2))
    return result

def inventory(source,settings,width):
    Image,_=pillow();image=tile(source,settings,192);box=image.getchannel('A').getbbox()
    if box:image=image.crop(box)
    image.thumbnail((width-2,70),Image.Resampling.LANCZOS)
    result=Image.new('RGBA',(width,72));result.alpha_composite(image,((width-image.width)//2,(72-image.height)//2))
    shade=Image.new('RGBA',(width,72))
    for y in range(38,72):shade.paste((12,18,17,round(215*(y-37)/34)),(0,y,width,y+1))
    result.alpha_composite(shade);return result

def category(key,entry):
    if entry.get('art_category') in GROUPS:return entry['art_category']
    for prefix,group in [('event_theme:','events'),('weapon_','weapons'),('armor_','armor'),('helmet_','armor'),
                         ('module_','modules'),('monster_','monsters'),('corpse:','corpses'),('trophy_','trophies')]:
        if key.startswith(prefix):return group
    return 'other'


class Library:
    def __init__(self,store):self.store=store;self.cache={};self.revision=0
    @property
    def entries(self):return self.store.art
    def next_id(self):
        n=1
        while f'art_custom_{n:03}' in self.entries:n+=1
        return f'art_custom_{n:03}'
    def file_bytes(self,relative):
        path=(self.store.root/relative).resolve()
        if not path.is_relative_to((self.store.root/'assets').resolve()):raise ValueError('Асет має знаходитися всередині assets.')
        return self.store.pending_assets.get(relative) or path.read_bytes()
    def image_file(self,relative):return decode(io.BytesIO(self.file_bytes(relative)))
    def source(self,key):
        entry=self.entries[key]
        if entry.get('editor_source'):return self.image_file('assets/'+entry['editor_source'])
        size=max(SIZES);sheet=entry.get('sheet','atlas');columns=entry.get('columns',16);index=entry['index']
        image=self.image_file(f'assets/{sheet}_{size}.png')
        x=index%columns*size;y=index//columns*size
        if x+size>image.width or y+size>image.height:raise ValueError('Некоректний індекс спрайта в атласі.')
        return image.crop((x,y,x+size,y+size))
    def settings(self,key):return copy.deepcopy(self.entries[key].get('editor_settings',dict(DEFAULTS,padding=0,trim=False)))
    def stage(self,key,name,group,source,settings):
        if key not in self.entries and not re.fullmatch(r'[a-z][a-z0-9_]*',key):raise ValueError('Некоректний ID арту.')
        if not name.strip():raise ValueError('Додайте назву арту.')
        if group not in GROUPS:raise ValueError('Невідома категорія арту.')
        # Content-addressed, immutable originals and rendered bundles are shared by all arts.
        original=encode(source)
        source_path='custom/sources/'+hashlib.sha256(original).hexdigest()+'.png'
        custom=self.store.root/'assets/custom'
        rendered={f'sprite_{size}.png':encode(tile(source,settings,size)) for size in SIZES}
        rendered.update({f'inventory_{width}.png':encode(inventory(source,settings,width)) for width in WIDTHS})
        digest=hashlib.sha256()
        for filename,blob in sorted(rendered.items()):
            digest.update(filename.encode());digest.update(len(blob).to_bytes(8,'big'));digest.update(blob)
        folder='custom/variants/'+digest.hexdigest()
        for candidate in sorted(custom.glob('*/sprite_192.png')):
            if all((candidate.parent/name).is_file() and (candidate.parent/name).read_bytes()==blob for name,blob in rendered.items()):
                folder=candidate.parent.relative_to(self.store.root/'assets').as_posix();break
        files={f'assets/{source_path}':original}
        files.update({f'assets/{folder}/{name}':blob for name,blob in rendered.items()})
        pending={}
        for relative,blob in files.items():
            path=self.store.root/relative
            existing=self.store.pending_assets.get(relative)
            if existing is None and path.exists():existing=path.read_bytes()
            if existing is not None:
                if existing!=blob:raise ValueError('Вміст спільного асета не відповідає його адресі: '+relative)
            else:pending[relative]=blob
        entry=dict(index=0,columns=1,sheet=folder+'/sprite',inventory_sheet=folder+'/inventory',
                   art_label=name.strip(),art_category=group,editor_source=source_path,editor_settings=copy.deepcopy(settings))
        self.store.data['sprites'][key]=entry
        # Sprite aliases used by monsters and legacy callers must follow their model's art.
        for group_name in ('equipment','modules','monsters'):
            for ident,data in self.store.data[group_name].items():
                if ident==key:data['sprite_id']=key
                if data.get('sprite_id')==key:self.store.data['sprites'][ident]=copy.deepcopy(entry)
                if group_name=='monsters':
                    for field,alias in [('corpse_sprite_id','corpse:'+ident),('trophy_sprite_id','trophy_'+ident)]:
                        if alias==key:data[field]=key
                        if data.get(field)==key:self.store.data['sprites'][alias]=copy.deepcopy(entry)
        self.store.pending_assets.update(pending);self.store.refresh_art();self.revision+=1;self.cache.clear()
        return key
    def photo(self,widget,key,size):
        if key not in self.entries:return None
        try:
            from PIL import ImageTk
            size=max(s for s in SIZES if s<=max(16,min(192,int(size))))
            entry=self.entries[key];token=(str(widget._root()),key,size,self.revision,str(entry))
            if token not in self.cache:
                columns=entry.get('columns',16);index=entry['index'];image=self.image_file(f"assets/{entry.get('sheet','atlas')}_{size}.png")
                x=index%columns*size;y=index//columns*size
                self.cache[token]=ImageTk.PhotoImage(image.crop((x,y,x+size,y+size)),master=widget._root())
            return self.cache[token]
        except (ImportError,OSError,ValueError):return None
    def usage(self,key,events):
        uses=[]
        for e in events:
            if e.get('art')==key:uses.append('Подія: '+e['title'])
        for group in ('equipment','modules','monsters'):
            for ident,d in self.store.data[group].items():
                for field in ('sprite_id','corpse_sprite_id','trophy_sprite_id'):
                    if d.get(field)==key:uses.append(self.store.data['texts'].get(ident+'.name',ident)+' · '+field)
        return uses
