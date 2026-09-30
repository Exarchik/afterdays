"""Deterministic weapon damage against the last enemy fired at; never consumes RNG."""
import copy
import combat033
import module_rules as mr


def remember_target(game,enemy):
    from adventure import RESISTANCES
    target=dict(name=enemy.get('name','Монстр'),defense=enemy.get('defense',enemy.get('armor',0)),
                resists=copy.deepcopy(enemy.get('resists',RESISTANCES.get(enemy.get('kind'),{}))))
    # This extensible state is already persisted, including in older saves.
    if hasattr(game,'reputation_state'):game.reputation_state['last_damage_target']=target
    else:game._last_damage_target=target


def attack_range(game,weapon,target):
    if mr.condition(weapon)<=0:return (0,0)
    mode=game.fire_mode(weapon)
    crit=min(65,5+mr.gear_stats(weapon).get('crit',0))+(15 if mode=='aimed' else 0)
    criticals=([False] if crit<100 else [])+([True] if crit>0 else [])
    pellets=range(6) if combat033.category(weapon)=='shotgun' else [None]*(5 if mode=='burst' else 1)
    low=high=0
    for pellet in pellets:
        amounts=[sum(combat033.projectile_components(weapon,game.level,target,v,c,pellet).values())
                 for v in range(-2,3) for c in criticals]
        low+=min(amounts);high+=max(amounts)
    return low,high


def estimate(game,weapon):
    target=getattr(game,'reputation_state',{}).get('last_damage_target',getattr(game,'_last_damage_target',None))
    reference=target or dict(name='Без попереднього пострілу',defense=0,resists={})
    ap=game.battle.get('max_ap',game.max_ap) if game.battle else game.max_ap
    cost=game.shot_ap(weapon)
    attacks=max(0,int(ap//cost)) if cost>0 else 0
    low,high=attack_range(game,weapon,reference)
    total_low=total_high=0
    simulated=copy.deepcopy(weapon)
    mode=game.fire_mode(weapon)
    wear=.6*(5 if mode=='burst' else 1)*(2 if mode=='aimed' else 1)
    wear*=max(.1,1-mr.aggregate(weapon).get('strength',0)/100)*(1-min(.7,.15*game.rank('engineer')))
    for _ in range(attacks):
        a,b=attack_range(game,simulated,reference);total_low+=a;total_high+=b
        if 'durability' in simulated:simulated['durability']=round(max(0,mr.condition(simulated)-wear),2)
    return dict(minimum=low,maximum=high,total_minimum=total_low,total_maximum=total_high,
                ap=ap,attacks=attacks,target=reference,has_target=target is not None)


def format_value(result):
    return f"{result['minimum']}–{result['maximum']} ({result['total_minimum']}–{result['total_maximum']} за {result['ap']} ОД)"


def description(game,weapon):
    result=estimate(game,weapon);target=result['target']
    reference=f"Остання ціль пострілу: {target['name']}; захист {target['defense']}." if result['has_target'] else 'До першого пострілу: захист і опори цілі = 0.'
    return ('Розрахункова шкода: '+format_value(result)+'\n'+reference+'\n'
            'За одну атаку в поточному режимі; у дужках — за повну шкалу ОД. '
            'Усі кулі/дробини влучають в одну ціль; максимум включає критичні влучання. '
            'Враховано опори, модулі та зношення. Без промахів, осічок, руху й обмеження набоїв.')
