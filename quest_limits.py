import world_hex
"""World-space distance limit for generated quest objectives."""
import math
MAX_DISTANCE=25

def origin(game,quest):
    return quest.get('issuer_pos',game.cities[quest['city']])

def nearby(game,quest,pos):
    return world_hex.distance(origin(game,quest),pos)<=MAX_DISTANCE
