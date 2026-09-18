"""Stable entity identifiers and data catalogs, independent of display names."""
import json
from pathlib import Path
from i18n import t
ROOT=Path(__file__).resolve().parent

def read(name):return json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
EQUIPMENT=read('equipment.json');MODULE_DATA=read('modules.json');MONSTER_DATA=read('monsters.json');ALIASES=read('legacy_aliases.json')
CONSUMABLES=read('consumables.json')
MODULE_IDS=[key for key,value in sorted(MODULE_DATA.items(),key=lambda pair:pair[1]['legacy_index'])]
MONSTER_IDS=[key for key,value in sorted(MONSTER_DATA.items(),key=lambda pair:pair[1]['legacy_index'])]
for data in (MODULE_DATA,MONSTER_DATA):
    indices=[v['legacy_index'] for v in data.values()]
    if sorted(indices)!=list(range(len(indices))):raise ValueError('Invalid legacy index map')

def entity_id(value,group='gear'):
    data={'gear':EQUIPMENT,'modules':MODULE_DATA,'monsters':MONSTER_DATA}[group]
    if value in data:return value
    if value in ALIASES[group]:return ALIASES[group][value]
    return next((key for key in data if t(key+'.name')==value),value)

def monster_id(value):
    if isinstance(value,dict):return value.get('type_id') or monster_id(value['kind'])
    if isinstance(value,int):return MONSTER_IDS[value]
    return entity_id(value,'monsters')

def module_id(value):return MODULE_IDS[value] if isinstance(value,int) else entity_id(value,'modules')
def name(ident):return t(ident+'.name')

class AliasDict(dict):
    """Old names are accepted on input; iteration always yields stable IDs."""
    def __getitem__(self,key):return super().__getitem__(entity_id(key))
    def get(self,key,default=None):return super().get(entity_id(key),default)
    def __contains__(self,key):return super().__contains__(entity_id(key))

GEAR=AliasDict({key:tuple(value[k] for k in ('kind','damage','range','defense','accuracy','weight','ap')) for key,value in EQUIPMENT.items()})
GEAR_MIN_LEVEL=AliasDict({k:v['min_level'] for k,v in EQUIPMENT.items()})
AMMO_BY_WEAPON=AliasDict({k:v['ammo_type'] for k,v in EQUIPMENT.items() if v['kind']=='weapon'})
WEAPON_ATTACK=AliasDict({k:v['attack'] for k,v in EQUIPMENT.items() if v['kind']=='weapon'})
WEAPON_DAMAGE=AliasDict({k:v['damage_type'] for k,v in EQUIPMENT.items() if v['kind']=='weapon'})
MODULES=[(name(k),v['target'],v['stat'],v['base']) for k in MODULE_IDS for v in [MODULE_DATA[k]]]
class Monsters:
    def __len__(self):return len(MONSTER_IDS)
    def __iter__(self):return (self[k] for k in MONSTER_IDS)
    def __getitem__(self,key):
        ident=monster_id(key);v=MONSTER_DATA[ident]
        return (name(ident),)+tuple(v[k] for k in ('hp','damage','range','speed','armor','color'))
MONSTERS=Monsters()
MONSTER_STATS=[(MONSTER_DATA[k]['attack'],MONSTER_DATA[k]['defense']) for k in MONSTER_IDS]
RESISTANCES={i:MONSTER_DATA[k]['resists'] for i,k in enumerate(MONSTER_IDS)}

def identify_item(item):
    kind=item.get('kind');ident=item.get('type_id')
    if not ident:
        if kind in ('weapon','armor','helmet'):ident=entity_id(item.get('name',''))
        elif kind=='module':ident=entity_id(item.get('name',''),'modules')
        elif kind=='ammo':ident='ammo_'+item.get('ammo_type','pistol')
        elif kind=='trophy':ident='trophy_'+monster_id(item.get('monster_kind',0))
        elif kind=='quest':ident='quest_parcel' if item.get('delivery') else 'quest_item'
        else:ident='item_'+str(kind)
        item['type_id']=ident
    if ident in EQUIPMENT or ident in MODULE_DATA or ident in CONSUMABLES:item['name']=name(ident)
    if kind=='trophy':item['monster_type_id']=monster_id(item.get('monster_kind',0));item['name']=t(item['monster_type_id']+'.trophy')
    for mod in item.get('modules',[]):identify_item(mod)
    if item.get('contents'):identify_item(item['contents'])
    return item

def identify_monster(enemy):
    ident=monster_id(enemy);enemy['type_id']=ident
    enemy['kind']=MONSTER_DATA[ident]['legacy_index']
    return enemy

def migrate(game):
    """Preserve rolled stats, IDs, durability, RNG and progress; only add identity/name data."""
    items=game.bag+game.loot+game.stash+[i for i in game.equipped.values() if i]
    for shop in game.shops.values():items+=shop['items']+shop.get('rep_reserve',[])
    if game.traveler:items+=game.traveler.get('items',[])+game.traveler.get('rep_reserve',[])
    for q in game.quests+[q for offers in game.offers.values() for q in offers]:
        items+=q.get('reward_items',[])
        if q.get('repair_item'):items.append(q['repair_item'])
    for item in items:identify_item(item)
    for q in game.quests+[q for offers in game.offers.values() for q in offers]:
        if q.get('target_kind') is not None:q['target_type_id']=monster_id(q['target_kind'])
    if game.battle:
        for enemy in game.battle.get('enemies',[]):
            identify_monster(enemy);enemy['name']=(t('monster.grade.'+enemy['grade']) if enemy.get('grade','normal')!='normal' else '')+name(enemy['type_id'])
        for group in ('kills','corpses'):
            for enemy in game.battle.get(group,[]):identify_monster(enemy)

AMMO={v['ammo_type']:(name(k),v['value'],v['weight']) for k,v in CONSUMABLES.items() if v['kind']=='ammo'}
def consumable(kind):
    ident='item_'+kind;v=CONSUMABLES[ident]
    return dict(type_id=ident,name=name(ident),kind=kind,rarity=0,weight=v['weight'],value=v['value'])
