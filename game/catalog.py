"""Shared game catalog and legacy geometry; independent of model and UI."""
import uuid
from collections import deque

import content
from i18n import t as tr

RARITIES = [(tr('afterdays.0001'), '#a8acaa'), (tr('afterdays.0002'), '#53a9ff'),
            (tr('afterdays.0003'), '#f4cd55'), (tr('afterdays.0004'), '#c58bfa'), (tr('afterdays.0005'), '#ff6570')]
STAT_NAMES = {'damage': tr('afterdays.0006'), 'range': tr('afterdays.0007'), 'defense': tr('afterdays.0008'), 'accuracy': tr('afterdays.0009')}
SLOTS = {'weapon1': tr('afterdays.0010'), 'weapon2': tr('afterdays.0011'), 'armor': tr('afterdays.0012'), 'helmet': tr('afterdays.0013')}
GEAR = content.GEAR
MODULES = content.MODULES
CITY_NAMES = [tr('afterdays.0014'), tr('afterdays.0015'), tr('afterdays.0016'), tr('afterdays.0017'), tr('afterdays.0018')]
MERCHANTS = [tr('afterdays.0019'), tr('afterdays.0020'), tr('afterdays.0021'),
             tr('afterdays.0087'), tr('economy.0001')]
TERRAINS = {'waste': ('#333b34', tr('afterdays.0022')), 'forest': ('#253c34', tr('afterdays.0023')),
            'ruin': ('#484139', tr('afterdays.0024')), 'road': ('#625747', tr('afterdays.0025')),
            'city': ('#827346', tr('afterdays.0026')),
            'water': ('#254b59', tr('adventure.0010')),
            'cliff': ('#62635d', tr('adventure.0011')),
            'site': ('#537965', tr('adventure.0012'))}
STAT_NAMES.update({key:tr('modules.'+key) for key in ('weight_percent','ammo_save_percent','reflect_percent','damage_electric','damage_piercing')})
STAT_NAMES.update(strength=tr('update031.strength'),local_damage_percent=tr('update031.local_damage'),local_defense_percent=tr('update031.local_defense'))
STAT_NAMES.update(damage_percent=tr('modules.damage_percent'),defense_percent=tr('modules.defense_percent'),max_condition_percent=tr('modules.max_condition_percent'))
STAT_NAMES.update(attack=tr('afterdays.0073'), pierce=tr('afterdays.0074'), crit=tr('afterdays.0075'), vitality=tr('afterdays.0076'),
                  capacity=tr('afterdays.0077'), evasion=tr('afterdays.0078'), regen=tr('afterdays.0079'))
CITY_NAMES.extend([tr('afterdays.0080'), tr('afterdays.0081'), tr('afterdays.0082'), tr('afterdays.0083'),
                   tr('afterdays.0084'), tr('afterdays.0085'), tr('afterdays.0086')])
MONSTERS = content.MONSTERS
EXTRA_CITIES = [[5, 15], [27, 4], [28, 16], [4, 28], [44, 15], [24, 28], [17, 17]]
MAYORS = [0, 2, 3, 5, 7, 9, 11]
QUEST_KINDS = ['hunt', 'retrieve', 'scout', 'supplies', 'purge']
QUEST_LABELS = {'hunt': tr('afterdays.0088'), 'retrieve': tr('afterdays.0089'),
                'scout': tr('afterdays.0090'), 'supplies': tr('afterdays.0091'), 'purge': tr('afterdays.0092')}

GEAR_MIN_LEVEL = content.GEAR_MIN_LEVEL
AMMO = content.AMMO
AMMO_BY_WEAPON = content.AMMO_BY_WEAPON
PERKS = {
    'marksman':(tr('progression.0007'),tr('progression.0008')),
    'carrier':(tr('progression.0009'),tr('progression.0010')),
    'hardy':(tr('progression.0011'),tr('progression.0012')),
    'armorer':(tr('progression.0013'),tr('progression.0014')),
    'medic':(tr('progression.0015'),tr('progression.0016')),
    'engineer':(tr('progression.0017'),tr('progression.0018')),
    'trader':(tr('progression.0019'),tr('progression.0020')),
    'scavenger':(tr('progression.0021'),tr('progression.0022')),
    'tactician': (tr('adventure.0006'), tr('adventure.0007')),
    'adrenaline': (tr('adventure.0008'), tr('adventure.0009')),
}
STACK_KINDS = {'food','med','ammo','parts','fragments','rad','repairkit','credits','trophy'}
TECHNICIANS = [0,2,4,7,10]
BASE_REWARDS = {
    'scout': 45, 'hunt': 70, 'retrieve': 85, 'purge': 110, 'supplies': 40,
    'trophies': 60, 'delivery': 90, 'radio': 100, 'repair_delivery': 130,
    'field_test': 95, 'generator': 100, 'cache': 85, 'elite_hunt': 150,
    'junkyard': 100, 'torn_map': 100, 'recruit_smith': 90,
    'recruit_tech': 90, 'recruit_mayor': 90,
}

def uid():
    return uuid.uuid4().hex


def neighbors(x, y, w, h):
    return [(nx, ny) for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1))
            if 0 <= nx < w and 0 <= ny < h]


def path_to(start, goal, w, h, blocked):
    queue = deque([start])
    prev = {start: None}
    while queue:
        p = queue.popleft()
        if p == goal:
            route = []
            while prev[p] is not None:
                route.append(p)
                p = prev[p]
            return route[::-1]
        for q in neighbors(*p, w, h):
            if q not in blocked and q not in prev:
                prev[q] = p
                queue.append(q)
    return []


def visible(a, b, walls):
    """Supercover ray: walls touched at a corner also block a shot."""
    x, y = a
    dx, dy = b[0] - x, b[1] - y
    nx, ny = abs(dx), abs(dy)
    sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
    ix = iy = 0
    walls = set(map(tuple, walls))
    while ix < nx or iy < ny:
        cross = (1 + 2 * ix) * ny - (1 + 2 * iy) * nx
        if cross == 0:
            if (x + sx, y) in walls or (x, y + sy) in walls:
                return False
            x += sx
            y += sy
            ix += 1
            iy += 1
        elif cross < 0:
            x += sx
            ix += 1
        else:
            y += sy
            iy += 1
        if (x, y) in walls:
            return False
    return True
