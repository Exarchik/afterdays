"""Search rewards, quest counts and varied dungeon layouts."""
import math

def objective_count(rng,kind):
    if kind is None:return rng.randint(3,5)
    # Tough or unusual enemies require fewer kills/trophies.
    return rng.randint(2,3) if kind in (4,7,9,10,11) else rng.randint(3,4) if kind in (5,6,8) else rng.randint(4,5)

def dungeon_layout(rng):
    from organic_arenas import dungeon
    return dungeon(rng)
