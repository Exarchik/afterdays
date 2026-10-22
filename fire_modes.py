"""Weapon fire modes: names, trade-offs and which modes a weapon offers.

The weapon class (category) gives the default set; a weapon model may list its own
`fire_modes` in data/equipment.json (edited in the content editor). Pure data: no game state.
"""

# Canonical order: the first available mode is the default one in battle.
MODES={
    'single':dict(name='Одиночний',
                  pros='Базова витрата ОД і точність, один набій. Дробовик стріляє віялом із 6 дробин.',
                  cons='Жодних бонусів до влучання чи критичного удару.'),
    'burst':dict(name='Черга',
                 pros='5 куль віялом, що ширшає: більше влучань, хвіст черги може зачепити сусіда.',
                 cons='+1 ОД, витрачає 5 набоїв, точність −15%. Дробовик чергою не стріляє.'),
    'aimed':dict(name='Прицільний',
                 pros='Від 4 гексів точність +10%, критичний шанс +15%.',
                 cons='+1 ОД; ближче ніж на 4 гекси точність −30%.'),
}
DEFAULTS={'automatic':('single','burst'),'sniper':('aimed',)}
# Modes a weapon class cannot fire, whatever the data says.
FORBIDDEN={'shotgun':{'burst'}}


def defaults(category):
    return DEFAULTS.get(category,('single',))


def allowed(category,explicit=None):
    """Modes a weapon offers, in canonical order. Invalid or empty lists fall back to the class."""
    if isinstance(explicit,(list,tuple)):
        chosen=tuple(m for m in MODES if m in explicit and m not in FORBIDDEN.get(category,()))
        if chosen:return chosen
    return defaults(category)


def problems(category,explicit):
    """Editor validation of an explicit list; empty list of messages when it is fine."""
    if not isinstance(explicit,list) or not explicit:return ['виберіть хоча б один режим атаки']
    errors=[]
    if any(not isinstance(m,str) or m not in MODES for m in explicit):errors.append('невідомий режим атаки')
    if len(set(map(str,explicit)))!=len(explicit):errors.append('режим атаки повторюється')
    for m in FORBIDDEN.get(category,()):
        if m in explicit:errors.append(f'клас зброї не підтримує режим «{MODES[m]["name"]}»')
    return errors


def describe(mode):
    m=MODES[mode];return f"{m['name']}: + {m['pros']} − {m['cons']}"
