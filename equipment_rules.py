"""Equipment model scaling shared by the game and content-editor previews."""

def values(data, tier, level):
    level = max(1, int(level))
    weapon = data['kind'] == 'weapon'
    stats = dict(damage=data['damage'], range=data['range'], defense=data['defense'], accuracy=data['accuracy'])
    if weapon:
        stats.update(damage=round(data['damage']*(1+.13*(level-1)))+tier*2,
                     attack=data['attack']+2*(level-1))
    else:
        stats['defense'] += level-1+tier
    result = dict(kind=data['kind'], rarity=tier, level=level, durability=100.0,
                  stats=stats, weight=data['weight'], ap=data['ap'], slots=min(5,tier+1),
                  value=round((70+data['weight']*15)*level**1.3*[1,1.8,3.5,7,14][tier]))
    if weapon: result['ammo_type'] = data['ammo_type']
    return result
