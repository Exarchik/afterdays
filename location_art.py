"""Persistent city illustration choices, independent of gameplay randomness."""
import random
import content


def assign_city_art(game,manifest=None):
    manifest=content.read('sprites.json') if manifest is None else manifest
    pool=sorted(k for k,v in manifest.items() if v.get('art_category')=='cities')
    if not pool:return
    game.init_reputation()
    saved=game.reputation_state.setdefault('city_art',{})
    # A separate generator keeps encounters, quests and loot unchanged.
    rng=random.Random(repr(game.rng.getstate()))
    for x,y in game.cities:
        if game.world[y][x]!='city':continue
        key=f'{x},{y}'
        if saved.get(key) not in manifest:saved[key]=rng.choice(pool)


def city_art(game,x,y):
    return getattr(game,'reputation_state',{}).get('city_art',{}).get(f'{x},{y}')


def location_art(game,x,y,definitions=None,manifest=None):
    """Persist one independent random illustration per visited terrain hex."""
    if game.world[y][x]=='city':return city_art(game,x,y)
    import location_rules
    kind=location_rules.terrain_type(game,x,y)
    if kind is None:return None
    definitions=location_rules.catalog() if definitions is None else definitions
    if manifest is None:
        import sprites
        manifest=sprites.MANIFEST
    pool=[key for key in definitions.get(kind,[]) if key in manifest]
    if not pool:pool=[key for key in definitions.get(game.world[y][x],[]) if key in manifest]
    if not pool:return None
    game.init_reputation()
    saved=game.reputation_state.setdefault('location_art',{})
    key=f'{x},{y}'
    if saved.get(key) not in pool:
        rng=random.Random(repr(game.rng.getstate())+':location:'+key)
        saved[key]=rng.choice(pool)
    return saved[key]
