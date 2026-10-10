"""Faction catalog and human equipment generation, shared by game and editor."""
import copy
import math
import re
import uuid
from pathlib import Path
import json
import module_rules as mr
from game import items as p

ROOT=Path(__file__).resolve().parent
MIXED_CHANCE=.20

def encounter_weight(definition):return definition.get('encounter_weight',25)

def encounter_pools(document,monsters,level):
    humans=document['humans'];pools={}
    for faction,d in document['factions'].items():
        members=[k for k in d['members'] if k in humans and humans[k]['min_level']<=level or k in monsters and monsters[k]['base_level']<=level+1]
        if encounter_weight(d)>0 and members:pools[faction]=members
    return pools

def encounter_factions(rng,document,monsters,level,count):
    """Roll mixed first, then select factions independently of roster size."""
    mixed=rng.random()<MIXED_CHANCE
    pools=encounter_pools(document,monsters,level)
    if not pools:raise ValueError('Немає доступних фракцій із додатною вагою появи.')
    def choose(keys):return rng.choices(keys,weights=[encounter_weight(document['factions'][k]) for k in keys],k=1)[0]
    keys=list(pools);first=choose(keys)
    if not mixed or len(keys)<2 or count<2:return [first]*count,pools
    result=[first,choose([k for k in keys if k!=first])]
    result.extend(choose(keys) for _ in range(count-2))
    rng.shuffle(result)
    return result,pools

def defaults(monsters):
    return {'bandits':dict(name='Бандити',player='hostile',members=['human_bandit']),
            'settlers':dict(name='Поселенці',player='friendly',members=['human_settler']),
            'monsters':dict(name='Монстри',player='hostile',members=list(monsters)),
            'infected':dict(name='Заражені монстри',player='hostile',members=list(monsters))}

def human_defaults():
    base=dict(description='',min_level=1,hp=45,hp_per_level=9,attack=0,defense=0,speed=3,
              regen=0,max_rarity=2,module_chance=35,sprite_id='',corpse_sprite_id='')
    return {'human_bandit':dict(base,name='Бандит'),'human_settler':dict(base,name='Поселенець')}

def default_catalog(monsters):
    factions=defaults(monsters)
    for key,d in factions.items():d['relations']={k:('friendly' if k==key and key!='infected' else 'hostile') for k in factions}
    return dict(factions=factions,humans=human_defaults())

def load():
    import content
    path=ROOT/'data/factions.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default_catalog(content.MONSTER_DATA)

CATALOG=None
def catalog():
    global CATALOG
    if CATALOG is None:CATALOG=load()
    return CATALOG

def hostile(left,right,document=None):
    factions=(document or catalog())['factions']
    if left=='player' or right=='player':
        other=right if left=='player' else left
        return other!='player' and factions.get(other,{}).get('player','hostile')=='hostile'
    return factions.get(left,{}).get('relations',{}).get(right,'hostile')=='hostile'

def faction_of(actor):
    return actor.get('faction','infected' if actor.get('infected') else 'monsters')

def validate(doc,monsters,art):
    errors=[]
    if not isinstance(doc,dict) or not isinstance(doc.get('factions'),dict) or not isinstance(doc.get('humans'),dict):return ['Некоректний каталог фракцій.']
    factions=doc['factions'];humans=doc['humans']
    if not factions:errors.append('Потрібна хоча б одна фракція.')
    for ident,d in list(factions.items())+list(humans.items()):
        if not re.fullmatch('[a-z][a-z0-9_]*',ident) or ident=='player':errors.append(f'{ident}: некоректний ID.')
        if not isinstance(d,dict) or not isinstance(d.get('name'),str) or not d['name'].strip():errors.append(f'{ident}: потрібна назва.')
    for ident,d in humans.items():
        for key,minimum,maximum in [('min_level',1,10000),('hp',1,1000000),('hp_per_level',0,100000),('attack',0,10000),('defense',0,10000),('speed',1,50),('regen',0,100000),('max_rarity',0,4),('module_chance',0,100)]:
            value=d.get(key)
            if type(value) is not int or not minimum<=value<=maximum:errors.append(f'{ident}: {key} має бути цілим від {minimum} до {maximum}.')
        for key in ('sprite_id','corpse_sprite_id'):
            if not isinstance(d.get(key),str) or d[key] and d[key] not in art:errors.append(f'{ident}: невідомий арт {key}.')
        if not isinstance(d.get('description'),str):errors.append(f'{ident}: потрібен текст опису.')
    for ident,d in factions.items():
        weight=encounter_weight(d)
        if type(weight) not in (int,float) or not math.isfinite(weight) or not 0<=weight<=1000000:errors.append(f'{ident}: вага появи має бути числом від 0 до 1000000.')
        if d.get('player') not in ('friendly','hostile'):errors.append(f'{ident}: невідомі відносини з гравцем.')
        if not isinstance(d.get('members'),list) or any(k not in monsters and k not in humans for k in d.get('members',[])):errors.append(f'{ident}: невідома істота.')
        for other in factions:
            value=d.get('relations',{}).get(other)
            if value not in ('friendly','hostile') or value!=factions[other].get('relations',{}).get(ident):errors.append(f'{ident} / {other}: відносини мають бути взаємними.')
    available={k for d in factions.values() for k in d.get('members',[])}
    if not any(k in available and d.get('base_level',999)<=2 for k,d in monsters.items()) and not any(k in available and d.get('min_level',999)==1 for k,d in humans.items()):
        errors.append('Призначте хоча б одну істоту, доступну у стартовій локації, до фракції.')
    if not errors and len(encounter_pools(doc,monsters,1))<2:
        errors.append('Для 20% змішаних зустрічей потрібні щонайменше дві фракції з вагою > 0 та істотами, доступними від стартової локації.')
    return errors

def human_values(d,level):
    return dict(hp=d['hp']+d['hp_per_level']*(level-1),attack=d['attack']+2*(level-1),defense=d['defense']+2*(level-1))


def make_human(rng,ident,faction,level,pos,document=None):
    import content
    doc=document or catalog();d=doc['humans'][ident];gear={}
    level=max(1,int(level))
    for slot in ('weapon','armor','helmet'):
        if slot=='armor' and rng.random()<.5:continue
        pool=[k for k,v in content.EQUIPMENT.items() if v['kind']==slot and v['min_level']<=level]
        if not pool:continue
        item=p.equipment(rng.choice(pool),rng.randint(0,d['max_rarity']),rng,level)
        candidates=mr.eligible_modules(item)
        for _ in range(item.get('slots',0)):
            if candidates and rng.random()*100<d['module_chance']:
                mod=p.module(rng.randint(0,item['rarity']),rng,content.MODULE_IDS.index(rng.choice(candidates)),level)
                if mr.compatible(item,mod):item['modules'].append(mod)
        gear[slot]=item
    values=human_values(d,level)
    values['hp']+=sum(p.stats(i).get('vitality',0) for i in gear.values())
    values['hp']=max(1,values['hp'])
    weapon=gear.get('weapon');stats=p.stats(weapon) if weapon else {}
    values['attack']+=stats.get('attack',0)
    values['defense']+=sum(p.stats(i).get('defense',0) for k,i in gear.items() if k!='weapon')
    values['defense']=max(0,round(values['defense']*(1+sum(p.stats(i).get('defense_percent',0) for k,i in gear.items() if k!='weapon')/100)))
    return dict(id=uuid.uuid4().hex,kind='human',human=True,type_id=ident,faction=faction,name=d['name'],description=d['description'],
                level=level,grade='normal',pos=list(pos),max_hp=values['hp'],**values,armor=values['defense'],
                damage=mr.shot_damage(weapon,level) if weapon else max(1,3+level),range=stats.get('range',1),speed=d['speed'],
                regen=d['regen']+sum(p.stats(i).get('regen',0) for i in gear.values()),resists={},equipment=gear,
                sprite_id=d['sprite_id'],corpse_sprite_id=d['corpse_sprite_id'],awake=True)

def human_loot(rng,actor):
    from game.systems.credits import credit_item
    items=[copy.deepcopy(item) for item in actor.get('equipment',{}).values() if rng.random()<.25]
    weapon=actor.get('equipment',{}).get('weapon')
    if weapon and rng.random()<.5:items.append(p.ammunition(weapon.get('ammo_type','pistol'),rng.randint(2,12)))
    if rng.random()<.35:items.append(p.parts(rng.randint(1,6)))
    if rng.random()<.25:items.append(p.fragments(rng.randint(1,4)))
    if rng.random()<.5:items.append(credit_item(rng.randint(5,25)*actor.get('level',1)))
    return items
