"""Editable special locations and their merchant assortments."""
import copy
import json
import math
import re
from pathlib import Path

PATH=Path(__file__).resolve().parent/'data/special_sites.json'
ROLES={'quest':'Видає квести','merchant':'Торгує','both':'Квести й торгівля'}
KINDS={'equipment':'Будь-яке спорядження','weapon':'Зброя','armor':'Броня','helmet':'Шоломи',
       'module':'Модулі','food':'Їжа','med':'Медикаменти','rad':'Радіопротектори',
       'repairkit':'Ремкомплекти','ammo':'Набої','parts':'Запчастини','fragments':'Фрагменти'}


def load():return json.loads(PATH.read_text(encoding='utf-8'))


def has_role(site,role):return site.get('role') in (role,'both')


def validate(data,art,equipment,modules,consumables):
    errors=[]
    if not isinstance(data,dict):return ['Локації мають бути словником.']
    if len(data)>32:errors.append('Мапа підтримує щонайбільше 32 особливі локації.')
    for ident,d in data.items():
        prefix=ident+': '
        if not re.fullmatch(r'[a-z][a-z0-9_]*',ident):errors.append(prefix+'некоректний ID')
        if not isinstance(d,dict):errors.append(prefix+'некоректна локація');continue
        for key in ('name','npc'):
            if not isinstance(d.get(key),str) or not d[key].strip():errors.append(prefix+'потрібні назва та ім’я мешканця')
        if d.get('npc_art') not in art:errors.append(prefix+'невідомий арт персонажа')
        if d.get('role') not in ROLES:errors.append(prefix+'невідомий тип персонажа')
        if type(d.get('refresh_turns')) is not int or not 1<=d['refresh_turns']<=100000:errors.append(prefix+'оновлення асортименту: 1–100000 ходів')
        if not isinstance(d.get('stock'),list):errors.append(prefix+'асортимент має бути списком');continue
        for row in d['stock']:
            if not isinstance(row,dict):errors.append(prefix+'некоректний товар');continue
            kind=row.get('kind');item=row.get('item_id')
            if kind not in KINDS:errors.append(prefix+'невідома категорія товару')
            if type(row.get('amount')) is not int or not 1<=row['amount']<=1000:errors.append(prefix+'кількість товару: 1–1000')
            chance=row.get('chance',1)
            if type(chance) not in (int,float) or not math.isfinite(chance) or not 0<=chance<=1:errors.append(prefix+'шанс товару: 0–100%')
            low,high=row.get('rarity_min',0),row.get('rarity_max',4)
            if type(low) is not int or type(high) is not int or not 0<=low<=high<=4:errors.append(prefix+'некоректні межі рідкісності')
            if item:
                definition=equipment.get(item) or modules.get(item) or consumables.get(item)
                actual='module' if item in modules else (definition or {}).get('kind')
                if not definition or (actual!=kind and not (kind=='equipment' and actual in ('weapon','armor','helmet'))):errors.append(prefix+'предмет не відповідає категорії')
    return errors


def generate_stock(game,definition):
    import content
    from game import items
    result=[];level=game.region_level
    for rule in definition['stock']:
        if rule.get('chance',1)<1 and game.rng.random()>=rule['chance']:continue
        kind=rule['kind'];specific=rule.get('item_id')
        low,high=rule.get('rarity_min',0),rule.get('rarity_max',4)
        if kind in ('equipment','weapon','armor','helmet','module'):
            catalog=content.MODULE_DATA if kind=='module' else content.EQUIPMENT
            pool=[key for key,d in catalog.items() if (not specific or specific==key)
                  and d.get('min_level',1)<=level and (kind in ('equipment','module') or d['kind']==kind)
                  and (kind!='module' or d.get('min_equipment_rarity',0)<=high)]
            for _ in range(rule['amount'] if pool else 0):
                key=game.rng.choice(pool);minimum=max(low,catalog[key].get('min_equipment_rarity',0) if kind=='module' else low)
                tier=game.rng.randint(minimum,high)
                result.append(items.module(tier,game.rng,key,level) if kind=='module' else items.equipment(key,tier,game.rng,level))
        else:
            pool=[key for key,d in content.CONSUMABLES.items() if d['kind']==kind and (not specific or key==specific)]
            if pool:items.add_to(result,items.supply(game.rng.choice(pool),rule['amount']))
    return result


def definition_for(site):
    definitions=load()
    if site.get('definition_id') in definitions:return definitions[site['definition_id']]
    if not site.get('definition_id'):
        return next((d for d in definitions.values() if site['name']==d.get('legacy_name',d['name'])),None)


def sync_saved(game):
    """Keep saved geography/quest city indices; apply edits to surviving templates."""
    definitions=load()
    for site in game.special_sites:
        ident=site.get('definition_id') or next((key for key,d in definitions.items() if site['name']==d.get('legacy_name',d['name'])),None)
        if ident not in definitions:continue
        d=definitions[ident];site.update(definition_id=ident,name=d['name'],npc=d['npc'],npc_art=d['npc_art'],role=d['role'])
        city=site.get('city_id')
        if city is not None:
            game.city_names[city]=site['name'];game.city_merchants[city]=[0] if has_role(site,'merchant') else []
            active=any(q.get('city')==city and q.get('status')=='active' for q in game.quests)
            if has_role(site,'quest') or active:
                if city not in game.mayors:game.mayors.append(city)
            elif city in game.mayors:game.mayors.remove(city)
