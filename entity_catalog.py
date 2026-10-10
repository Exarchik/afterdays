"""Editable entity catalogs, safe multi-file persistence and gameplay previews."""
import copy
import json
import math
import os
from pathlib import Path
import re
import tempfile
import equipment_rules
import module_rules
import monster_rules

ROOT = Path(__file__).resolve().parent
SECTIONS = {'weapon':'Зброя','armor':'Броня','helmet':'Шоломи','module':'Модулі','monster':'Монстри'}
GROUPS = {'weapon':'equipment','armor':'equipment','helmet':'equipment','module':'modules','monster':'monsters'}
DAMAGE = {'kinetic':'Кінетична','piercing':'Пробивна','thermal':'Термічна','energy':'Енергетична','electric':'Електрична'}
AMMO = {'pistol':'Пістолетні','rifle':'Гвинтівкові','shell':'Дріб','energy':'Енергоосередки','heavy':'Важкі','bolt':'Болти'}
CATEGORIES = {'pistol':'Пістолет','rifle':'Гвинтівка','automatic':'Автоматична','shotgun':'Дробовик','sniper':'Снайперська'}
TARGETS = {'weapon':'Зброя','protection':'Броня та шоломи','armor':'Лише броня','helmet':'Лише шоломи'}
STATS = {
    'damage':'Шкода','range':'Дальність','accuracy':'Точність','attack':'Атака','pierce':'Пробиття (старий параметр)',
    'crit':'Критичний шанс','defense':'Захист','vitality':'Здоров’я','capacity':'Вантажність','evasion':'Ухилення',
    'regen':'Регенерація','damage_percent':'Шкода, %','defense_percent':'Захист гравця, %',
    'local_damage_percent':'Шкода предмета, %','local_defense_percent':'Захист предмета, %',
    'strength':'Міцність, %','weight_percent':'Вага, %','ammo_save_percent':'Економія набоїв, %',
    'reflect_percent':'Відбиття шкоди, %','damage_electric':'Електрична шкода','damage_piercing':'Пробивна шкода',
}
RARITIES = ('Звичайна','Незвична','Рідкісна','Унікальна','Міфічна')
GRADES = {'normal':'Звичайний','rare':'Рідкісний','mythic':'Міфічний'}
FIELDS = {
    'weapon': [('damage','Базова шкода',int),('attack','Базова атака',int),('range','Дальність',int),('accuracy','Точність, %',int),('weight','Вага, кг',float),('ap','Витрата ОД',int),('min_level','Мін. рівень появи',int),('ammo_type','Тип набоїв',AMMO),('damage_type','Тип шкоди',DAMAGE),('category','Клас зброї',CATEGORIES)],
    'armor': [('defense','Базовий захист',int),('weight','Вага, кг',float),('min_level','Мін. рівень появи',int)],
    'helmet': [('defense','Базовий захист',int),('weight','Вага, кг',float),('min_level','Мін. рівень появи',int)],
    'module': [('target','Для спорядження',TARGETS),('min_level','Мін. рівень появи',int),('stat','Основний параметр',STATS),('base','Базовий бонус',float),('weight','Вага, кг',float)],
    'monster': [('trophy_value','Базова вартість трофея, кр.',int),('base_level','Базовий рівень виду',int),('hp','Базове здоров’я',int),('damage','Базова шкода',int),('attack','Базова атака',int),('defense','Базовий захист',int),('range','Дальність',int),('speed','Швидкість',int),('regen','Регенерація за хід',int),('color','Колір без спрайта',str)],
}

def module_group(data):
    return {'helmet':0,'armor':1,'protection':2,'weapon':3}[data.get('target','protection')]


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def validate_definition(section, ident, data, texts, art):
    errors=[]
    def need(ok,text):
        if not ok: errors.append(f'{ident}: {text}')
    def number(value): return type(value) in (int,float) and math.isfinite(value)
    need(isinstance(ident,str) and bool(re.fullmatch('[a-z][a-z0-9_]*',ident)), 'некоректний ID')
    need(isinstance(texts.get('name'),str) and bool(texts['name'].strip()), 'назва порожня')
    need(isinstance(texts.get('description'),str), 'опис має бути текстом')
    need(isinstance(data.get('sprite_id'),str) and data['sprite_id'] in art, 'невідомий асет')
    for field,label,kind in FIELDS[section]:
        value=data.get(field, 2*(4+data.get('legacy_index',0)) if section=='monster' and field=='trophy_value' else .3 if section=='module' and field=='weight' else 1 if section=='module' and field=='min_level' else None)
        if isinstance(kind,dict): need(isinstance(value,str) and value in kind, label+': невідоме значення')
        elif kind is str: need(isinstance(value,str),label+': потрібен текст')
        else:
            valid=number(value) and (kind is not int or type(value) is int)
            need(valid,label+': потрібне коректне число')
            if valid and field != 'base': need(value>=0,label+': має бути ≥ 0')
            if valid and field in ('min_level','base_level','hp','ap','range','speed'): need(value>=1,label+': має бути ≥ 1')
            if valid and field=='accuracy': need(value<=100,'точність має бути ≤ 100')
    if section in ('weapon','armor','helmet'):
        need(data.get('kind')==section,'тип спорядження не можна змінювати')
        for key in ('damage','range','defense','accuracy','ap','attack'):
            need(type(data.get(key)) is int and data[key]>=0,key+': має бути цілим ≥ 0')
    if section in ('module','monster'):
        need(type(data.get('legacy_index')) is int and data['legacy_index']>=0,'некоректний індекс')
    if section=='module':
        minimum=data.get('min_equipment_rarity',0)
        need(type(minimum) is int and 0<=minimum<5,'мінімальна рідкість спорядження: 0–4')
        categories=data.get('weapon_categories',list(CATEGORIES))
        need(isinstance(categories,list) and bool(categories) and all(isinstance(c,str) and c in CATEGORIES for c in categories),'виберіть хоча б один відомий клас зброї')
        for key,values in data.get('rarity_stats',{}).items():
            need(key in STATS,'невідомий параметр '+key)
            need(isinstance(values,list) and len(values)==5 and all(number(n) for n in values),'для '+key+' потрібні 5 чисел рідкості')
        for key,value in data.get('fixed_penalties',{}).items(): need(key in STATS and number(value),'некоректний постійний модифікатор '+key)
    if section=='monster':
        need(bool(re.fullmatch('#[0-9a-fA-F]{6}',str(data.get('color','')))), 'колір: #RRGGBB')
        for key,value in data.get('resists',{}).items(): need(key in DAMAGE and number(value) and -100<=value<=100,'опір має бути від −100 до 100%')
        need(isinstance(texts.get('trophy'),str) and bool(texts['trophy'].strip()),'назва трофея порожня')
        for field in ('corpse_sprite_id','trophy_sprite_id'):
            need(isinstance(data.get(field),str) and data[field] in art, 'невідомий асет '+field)
    return errors


class Store:
    def __init__(self, root=ROOT):
        self.root=Path(root)
        self.paths={group:self.root/'data'/f'{group}.json' for group in ('equipment','modules','monsters','sprites','quests','dialogues','consumables','factions')}
        self.paths['texts']=self.root/'locales/uk/entities.json'
        self.data={key:read(path) for key,path in self.paths.items()}
        self.baseline=copy.deepcopy(self.data)
        self.disk={key:path.read_bytes() for key,path in self.paths.items()}
        self.base_art=read(self.root/'assets/manifest.json')
        self.pending_assets={}
        self.refresh_art()

    def refresh_art(self):
        self.art=dict(self.base_art);self.art.update(self.data['sprites'])

    def items(self, section):
        values=self.data[GROUPS[section]]
        return [(key,d) for key,d in values.items() if section in ('module','monster') or d['kind']==section]

    def draft(self, section, ident):
        data=copy.deepcopy(self.data[GROUPS[section]][ident]);texts=self.data['texts']
        names={field:texts.get(ident+'.'+field,'') for field in ('name','description','trophy')}
        if section=='module':
            data.setdefault('weight',.3);data.setdefault('min_level',1)
            data.setdefault('min_equipment_rarity',0)
            data.setdefault('weapon_categories',list(CATEGORIES))
        if section=='monster':
            data.setdefault('trophy_value',2*(4+data['legacy_index']))
            data.setdefault('corpse_sprite_id','corpse:'+ident)
            data.setdefault('trophy_sprite_id','trophy_'+ident)
        return data,names

    def put(self, section, ident, data, texts):
        errors=validate_definition(section,ident,data,texts,self.art)
        if errors: raise ValueError('\n'.join(errors))
        old=self.baseline[GROUPS[section]].get(ident)
        if old and section in ('module','monster') and old['legacy_index']!=data['legacy_index']:
            raise ValueError('Індекс наявного запису не можна змінювати.')
        self.data[GROUPS[section]][ident]=copy.deepcopy(data)
        for field in ('name','description')+ (('trophy',) if section=='monster' else ()):
            self.data['texts'][ident+'.'+field]=texts[field]
        self.data['sprites'][ident]=copy.deepcopy(self.art[data['sprite_id']])
        if section=='monster':
            self.data['sprites']['corpse:'+ident]=copy.deepcopy(self.art[data['corpse_sprite_id']])
            self.data['sprites']['trophy_'+ident]=copy.deepcopy(self.art[data['trophy_sprite_id']])
        self.refresh_art()

    def add(self, section, name, source=None):
        if not name.strip(): raise ValueError('Додайте назву.')
        if source is None: source=self.items(section)[0][0]
        data,texts=self.draft(section,source)
        n=1
        while f'{section}_custom_{n:03}' in self.data[GROUPS[section]]: n+=1
        ident=f'{section}_custom_{n:03}'
        if section in ('module','monster'): data['legacy_index']=len(self.data[GROUPS[section]])
        texts['name']=name.strip()
        if section=='monster': texts['trophy']='Трофей: '+name.strip()
        self.put(section,ident,data,texts)
        return ident

    def validate(self):
        import quest_catalog
        import game.systems.consumables as consumable_rules
        import faction_rules
        errors=faction_rules.validate(self.data['factions'],self.data['monsters'],self.art)
        errors+=consumable_rules.validate(self.data['consumables'],self.art)
        errors+=quest_catalog.validate(self.data['quests'])
        if not errors:
            import game.systems.story as story_system
            errors+=story_system.validate(self.data['quests'],self.data['dialogues'])
        import dialogue_system
        errors+=dialogue_system.validate(self.data['dialogues'],self.art,{q['id']:q for q in self.data['quests']['quests']})
        for section in SECTIONS:
            for ident,_ in self.items(section):
                data,texts=self.draft(section,ident)
                errors.extend(validate_definition(section,ident,data,texts,self.art))
        for group in ('modules','monsters'):
            indices=[v['legacy_index'] for v in self.data[group].values()]
            if sorted(indices)!=list(range(len(indices))): errors.append(group+': порушена послідовність індексів')
        if not any(d.get('min_level',1)==1 for d in self.data['modules'].values()): errors.append('Потрібен хоча б один модуль рівня 1.')
        # Generation always needs an entry available in the starting region.
        if not any(d['base_level']<=2 for d in self.data['monsters'].values()): errors.append('Потрібен хоча б один монстр рівня 1–2.')
        if not any(d['min_level']==1 for d in self.data['equipment'].values()): errors.append('Потрібен хоча б один предмет рівня 1.')
        return errors

    @property
    def dirty(self): return self.data!=self.baseline or bool(self.pending_assets)

    def check_disk(self):
        for key,path in self.paths.items():
            if path.read_bytes()!=self.disk[key]: raise ValueError(f'{path.name} змінено іншою програмою. Перезапустіть редактор перед збереженням.')

    def save(self, extra=None):
        import custom_atlases
        self.check_disk()
        original=copy.deepcopy(self.data);pending=dict(self.pending_assets)
        try:
            sprites,backup,assets=custom_atlases.pack(self)
            self.data['sprites']=sprites;self.pending_assets=assets
            self._packed_backup=backup
            self.refresh_art();self._save(extra)
        except Exception:
            self.data=original;self.pending_assets=pending;self.refresh_art()
            raise
        finally:self.__dict__.pop('_packed_backup',None)
        self.refresh_art()
        self.asset_cleanup_warning=''
        try:self.removed_asset_files=custom_atlases.cleanup(self.root)
        except (OSError,ValueError) as exc:self.asset_cleanup_warning='Атласи збережено; очищення старих файлів відкладено: '+str(exc)

    def _save(self, extra=None):
        errors=self.validate()
        if errors: raise ValueError('\n'.join(errors))
        self.check_disk()
        changed=[key for key in self.paths if self.data[key]!=self.baseline[key]]
        paths=dict(self.paths);payloads=dict(self.data);before=dict(self.disk)
        if extra is not None:
            path,document,expected=extra
            path=Path(path)
            if path.read_bytes()!=expected:raise ValueError('Каталог подій змінено іншою програмою.')
            paths['events']=path;payloads['events']=document;before['events']=expected;changed.append('events')
        asset_keys=[]
        for relative,blob in self.pending_assets.items():
            path=(self.root/relative).resolve()
            if not path.is_relative_to((self.root/'assets/custom').resolve()):raise ValueError('Некоректний шлях нового асета.')
            if path.exists():
                if path.read_bytes()==blob:continue
                raise ValueError('Файл нового асета вже існує з іншим вмістом: '+str(path))
            key='asset:'+relative;paths[key]=path;payloads[key]=blob;before[key]=None;asset_keys.append(key)
        # Backups participate in the same rollback as catalogs, and reference packed pages.
        catalog_keys=list(changed)
        for key in catalog_keys:
            backup_key='backup:'+key;backup_path=paths[key].with_suffix(paths[key].suffix+'.bak')
            paths[backup_key]=backup_path
            payloads[backup_key]=(json.dumps(self._packed_backup,ensure_ascii=False,indent=2)+'\n').encode('utf-8') if key=='sprites' else before[key]
            before[backup_key]=backup_path.read_bytes() if backup_path.exists() else None
            changed.append(backup_key)
        changed=asset_keys+changed
        staged={};replaced=[]
        try:
            for key in changed:
                path=paths[key]
                path.parent.mkdir(parents=True,exist_ok=True)
                fd,temp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
                staged[key]=Path(temp)
                with os.fdopen(fd,'wb') as stream:
                    stream.write(payloads[key] if isinstance(payloads[key],bytes) else (json.dumps(payloads[key],ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
            for key in changed:
                os.replace(staged[key],paths[key]);replaced.append(key)
        except OSError:
            for key in reversed(replaced):
                if before[key] is None:paths[key].unlink()
                else:paths[key].write_bytes(before[key])
            raise
        finally:
            for path in staged.values():
                if path.exists(): path.unlink()
        self.disk={key:path.read_bytes() for key,path in self.paths.items()}
        self.baseline=copy.deepcopy(self.data)
        self.pending_assets.clear()


def preview(section, data, level, tier=0, condition=100, player_level=1, tradeoff=False, grade='normal', weak=False):
    """No global mutation or RNG: preview unsaved values with actual game formulas."""
    if section in ('weapon','armor','helmet'):
        item=equipment_rules.values(data,tier,level);item['modules']=[];item['durability']=condition
        values=module_rules.gear_stats(item)
        values.update(weight=module_rules.item_weight(item),value=item['value'],slots=item['slots'],ap=item['ap'])
        if section=='weapon': values['shot_damage']=module_rules.shot_damage(item,player_level)
        return values
    if section=='module':
        result=module_rules.definition_stats(data,tier,level,tradeoff)
        return dict(result,weight=data.get('weight',.3),value=round(30*(tier+1)**2*level**1.3))
    simulated=dict(data,base_level=level)
    values=monster_rules.definition_values(simulated,grade,weak)
    return {key:values[key] for key in ('level','hp','damage','attack','defense','range','speed')} | {'regen':data['regen']}
