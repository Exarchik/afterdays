"""Module balance v0.27: compatibility, fixed penalties and save migration."""
import content

VERSION = 2
PERCENT_STATS = {'local_damage_percent','local_defense_percent','damage_percent', 'defense_percent', 'strength','weight_percent','ammo_save_percent','reflect_percent'}
DRAWBACKS = {'weight_percent':('strength',-10), 'ammo_save_percent':('accuracy',-5),
    'reflect_percent':('evasion',-3), 'damage_electric':('accuracy',-6), 'damage_piercing':('range',-1), 'damage':('accuracy',-6), 'damage_percent':('accuracy',-6),
    'range':('damage',-2), 'accuracy':('range',-1), 'attack':('accuracy',-5),
    'crit':('accuracy',-5), 'defense':('capacity',-2), 'vitality':('evasion',-3),
    'capacity':('defense',-1), 'evasion':('vitality',-4), 'regen':('capacity',-2)}

def module_stats(ident, tier, level, tradeoff=False):
    return definition_stats(content.MODULE_DATA[ident],tier,level,tradeoff)

def definition_stats(data, tier, level, tradeoff=False):
    """Calculate an unsaved model with the same rules used by generated modules."""
    curves=data.get('rarity_stats') or {data['stat']:[data['base']*(n+1) for n in range(5)]}
    result={key:(values[tier] if key in PERCENT_STATS or key=='attack' else
                 max(1,round(values[tier]*(1+.06*(level-1))))) for key,values in curves.items()}
    if tradeoff:
        key=next(iter(result));result[key]=round(result[key]*1.7)
        result[key]=min(-1,result[key]) if curves[key][tier]<0 else max(1,result[key])
        bad,amount=DRAWBACKS.get(key,('accuracy',-5) if data['target']=='weapon' else ('evasion',-3))
        result[bad]=result.get(bad,0)+amount*(1+tier//2)
    for key,value in data.get('fixed_penalties',{}).items():result[key]=result.get(key,0)+value
    return result

def compatible(item, mod):
    return bool(item and mod and mod.get('kind')=='module' and
        (mod.get('target')==item.get('kind') or mod.get('target')=='protection' and item.get('kind') in ('armor','helmet')) and
        mod.get('rarity',0)<=item.get('rarity',0) and mod.get('level',1)<=item.get('level',1))

def aggregate(item):
    result=dict(item.get('stats',{}))
    for mod in item.get('modules',[]):
        for key,value in mod.get('stats',{}).items():result[key]=result.get(key,0)+value
    return result

def max_condition(item):
    if item.get('kind')=='module':return 100
    # Strength changes wear, never the repair ceiling.
    return 100

def condition(item):return max(0,min(max_condition(item),item.get('durability',100)))

def clamp_condition(item):
    if 'durability' in item:item['durability']=float(condition(item))

def damage_factor(item):return max(0,1+aggregate(item).get('damage_percent',0)/100)

def gear_stats(item):
    result=aggregate(item)
    if item.get('kind')=='module':return result
    for key in ('damage','damage_electric','damage_piercing'):
        if key in result:result[key]=max(0,round(result[key]*damage_factor(item)*max(0,1+result.get('local_damage_percent',0)/100)))
    if 'defense' in result:result['defense']=max(0,round(result['defense']*(1+result.get('local_defense_percent',0)/100)))
    if 'range' in result and item.get('kind')=='weapon':result['range']=max(1,result['range'])
    if 'durability' in item:
        value=condition(item)/100
        for key in ('damage','defense','damage_electric','damage_piercing'):
            if result.get(key):
                result[key]=degraded_damage(result[key],item) if item.get('kind')=='weapon' and key!='defense' else max(1,round(result[key]*(.5+.5*value))) if value else 0
    return result

def degraded_damage(value,item):
    """Keep full weapon damage at 50%+, then interpolate down to one at 1%."""
    state=condition(item)
    if state<=0:return 0
    if state>=50:return max(0,round(value))
    return max(1,round(1+(max(1,value)-1)*max(0,state-1)/49))

def shot_damage(item,level,variation=0):
    raw=aggregate(item)
    base=round(raw.get('damage',0)*max(0,1+raw.get('local_damage_percent',0)/100))
    return degraded_damage((base+2*(level-1)+variation)*damage_factor(item),item)

def item_weight(item):
    weight=item.get('weight',0)*item.get('qty',1)+sum(item_weight(m) for m in item.get('modules',[]))
    if item.get('kind') in ('weapon','armor','helmet'):
        weight*=max(.10,1+aggregate(item).get('weight_percent',0)/100)
    return max(0,weight)


def chance(value):return max(0,min(100,value))


def shot_components(item,level,variation,element):
    """Apply condition to total shot damage once, including elemental modules and level."""
    raw=aggregate(item);local=max(0,1+raw.get('local_damage_percent',0)/100)
    components={element:max(0,round((round(raw.get('damage',0)*local)+2*(level-1)+variation)*damage_factor(item)))}
    for kind,key in (('electric','damage_electric'),('piercing','damage_piercing')):
        value=max(0,round(raw.get(key,0)*damage_factor(item)*local))
        if value:components[kind]=components.get(kind,0)+value
    total=sum(components.values());target=degraded_damage(total,item)
    if not total:return {element:0}
    scaled={kind:int(value*target/total) for kind,value in components.items()}
    for kind in sorted(components,key=lambda k:components[k]*target/total-scaled[k],reverse=True)[:target-sum(scaled.values())]:scaled[kind]+=1
    return {k:v for k,v in scaled.items() if v} or {element:0}


def migrate_game(game):
    """Rebalance once without consuming RNG; return detached modules to their container."""
    seen=set();detached=0
    def walk(obj,container):
        nonlocal detached
        if not isinstance(obj,(dict,list)) or id(obj) in seen:return
        seen.add(id(obj))
        if isinstance(obj,list):
            for value in list(obj):walk(value,obj)
            return
        if obj.get('kind')=='module':
            ident=content.module_id(obj.get('type_id',obj.get('name','')))
            if ident in content.MODULE_DATA and obj.get('module_balance_version')!=VERSION:
                obj['stats']=module_stats(ident,obj.get('rarity',0),obj.get('level',1),obj.get('tradeoff',False))
                obj['module_balance_version']=VERSION
                obj['weight']=content.MODULE_DATA[ident].get('weight',.3)
        for key,value in list(obj.items()):
            if key!='modules':walk(value,container)
        if 'modules' in obj:
            for mod in list(obj['modules']):
                walk(mod,container)
                if not compatible(obj,mod):
                    obj['modules'].remove(mod);container.append(mod);detached+=1
            clamp_condition(obj)
    for key,value in vars(game).items():
        if not key.startswith('_') and key!='rng':walk(value,game.bag)
    game.hp=min(game.hp,game.max_hp)
    return detached
