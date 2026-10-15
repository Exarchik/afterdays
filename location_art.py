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
