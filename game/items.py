"""Item factories and stack operations, with no dependency on a game instance."""
import copy
import random

import content
import equipment_rules
import module_rules as mr
from game.catalog import (AMMO, GEAR, GEAR_MIN_LEVEL, MODULES, STACK_KINDS, uid)


def _base_equipment(name=None, tier=0, rng=None):
    rng = rng or random
    name = content.entity_id(name) if name else rng.choice(list(GEAR))
    kind, damage, reach, defense, accuracy, weight, cost = GEAR[name]
    return dict(id=uid(), type_id=name, name=content.name(name), kind=kind, rarity=tier, weight=weight,
                value=int((70 + weight * 15) * (1 + tier * .85)), slots=min(5, tier + 1),
                stats=dict(damage=damage + (tier * 2 if kind == 'weapon' else 0),
                           range=reach, defense=defense + (tier if kind != 'weapon' else 0),
                           accuracy=accuracy), modules=[], ap=cost)


def _base_module(tier=0, rng=None, index=None):
    rng = rng or random
    ident=content.module_id(rng.randrange(len(MODULES)) if index is None else index)
    data=content.MODULE_DATA[ident]
    name,target,stat,base=content.name(ident),data['target'],data['stat'],data['base']
    from module_rules import module_stats, VERSION
    return dict(id=uid(), type_id=ident, name=name, kind='module', rarity=tier, weight=data.get('weight',.3),
                value=30 * (tier + 1) ** 2, target=target, stats=module_stats(ident,tier,1),module_balance_version=VERSION)


def equipment(name=None, tier=0, rng=None, level=1):
    rng = rng or random
    level=max(1,int(level))
    if name is not None:name=content.entity_id(name)
    eligible=[n for n in GEAR if GEAR_MIN_LEVEL[n] <= level]
    if name not in eligible:
        # Preserve requested equipment category when possible.
        kind=GEAR[name][0] if name in GEAR else None
        pool=[n for n in eligible if kind is None or GEAR[n][0] == kind]
        name=rng.choice(pool or eligible)
    item=_base_equipment(name,tier,rng)
    item.update(equipment_rules.values(content.EQUIPMENT[name],tier,level))
    return item


def module(tier=0,rng=None,index=None,level=1):
    level=max(1,int(level))
    if index is None:
        eligible=[k for k in content.MODULE_IDS if content.MODULE_DATA[k].get('min_level',1)<=level]
        index=(rng or random).choice(eligible or content.MODULE_IDS)
    item=_base_module(tier,rng,index)
    item['level']=max(level,content.MODULE_DATA[item['type_id']].get('min_level',1))
    item['value']=round(30*(tier+1)**2*item['level']**1.3)
    item['tradeoff']=bool(rng is not None and rng.random()<.20)
    item['stats']=mr.module_stats(item['type_id'],tier,item['level'],item['tradeoff'])
    item['module_balance_version']=mr.VERSION
    return item


def supply(kind,qty=1):
    return dict(id=uid(),qty=int(qty),level=1,**content.consumable(kind))


def ammunition(kind,qty=1):
    name,value,weight=AMMO[kind]
    return dict(id=uid(),name=name,type_id='ammo_'+kind,kind='ammo',ammo_type=kind,rarity=0,
                weight=weight,value=value,qty=int(qty),level=1)


def fragments(qty):return supply('fragments',qty)


def parts(qty):return supply('parts',qty)


def stats(item):
    return mr.gear_stats(item)


def item_weight(item):
    return mr.item_weight(item)


def item_value(item):
    return item['value']*item.get('qty',1)+sum(item_value(m) for m in item.get('modules',[]))


def stack_key(item):
    if item['kind'] in ('food','med','rad','repairkit'):
        import game.systems.consumables as consumable_rules
        return (item['kind'],item.get('type_id'),tuple(sorted(consumable_rules.definition(item).items())),item.get('paid_sale_cap'))
    return (item['kind'],item.get('monster_kind') if item['kind']=='trophy' else item.get('ammo_type'),item.get('paid_sale_cap')) if item['kind'] in STACK_KINDS else None


def add_to(items,item):
    key=stack_key(item)
    if key:
        existing=next((i for i in items if stack_key(i)==key),None)
        if existing:
            existing['qty']=existing.get('qty',1)+item.get('qty',1)
            return existing
        item.setdefault('qty',1)
    items.append(item)
    return item


def normalize(items):
    result=[]
    for i in items:
        add_to(result,i)
    return result


def extract(items,item,qty=1):
    available=item.get('qty',1)
    if qty < 1 or qty > available or item not in items:
        return None
    if qty==available:
        items.remove(item)
        return item
    result=copy.deepcopy(item)
    result['id']=uid()
    result['qty']=qty
    item['qty']-=qty
    return result
