"""Afterdays — standalone turn-based RPG. Python 3.10+, Tkinter, no pip packages."""
from __future__ import annotations
import hexgrid
from i18n import t as tr
import content
from debug_config import TEST_MODE, MapVisibility
import json
import math
import os
import random
import sys
import uuid
from collections import deque
from pathlib import Path
sys.modules.setdefault('afterdays', sys.modules[__name__])

RARITIES = [(tr('afterdays.0001'), '#a8acaa'), (tr('afterdays.0002'), '#53a9ff'),
            (tr('afterdays.0003'), '#f4cd55'), (tr('afterdays.0004'), '#c58bfa'), (tr('afterdays.0005'), '#ff6570')]
STAT_NAMES = {'damage': tr('afterdays.0006'), 'range': tr('afterdays.0007'), 'defense': tr('afterdays.0008'), 'accuracy': tr('afterdays.0009')}
SLOTS = {'weapon1': tr('afterdays.0010'), 'weapon2': tr('afterdays.0011'), 'armor': tr('afterdays.0012'), 'helmet': tr('afterdays.0013')}
GEAR = content.GEAR
MODULES = content.MODULES
CITY_NAMES = [tr('afterdays.0014'), tr('afterdays.0015'), tr('afterdays.0016'), tr('afterdays.0017'), tr('afterdays.0018')]
MERCHANTS = [tr('afterdays.0019'), tr('afterdays.0020'), tr('afterdays.0021')]
TERRAINS = {'waste': ('#333b34', tr('afterdays.0022')), 'forest': ('#253c34', tr('afterdays.0023')),
            'ruin': ('#484139', tr('afterdays.0024')), 'road': ('#625747', tr('afterdays.0025')),
            'city': ('#827346', tr('afterdays.0026'))}


def uid():
    return uuid.uuid4().hex


def equipment(name=None, tier=0, rng=None):
    rng = rng or random
    name = content.entity_id(name) if name else rng.choice(list(GEAR))
    kind, damage, reach, defense, accuracy, weight, cost = GEAR[name]
    return dict(id=uid(), type_id=name, name=content.name(name), kind=kind, rarity=tier, weight=weight,
                value=int((70 + weight * 15) * (1 + tier * .85)), slots=min(5, tier + 1),
                stats=dict(damage=damage + (tier * 2 if kind == 'weapon' else 0),
                           range=reach, defense=defense + (tier if kind != 'weapon' else 0),
                           accuracy=accuracy), modules=[], ap=cost)


def module(tier=0, rng=None, index=None):
    rng = rng or random
    ident=content.module_id(rng.randrange(len(MODULES)) if index is None else index)
    data=content.MODULE_DATA[ident]
    name,target,stat,base=content.name(ident),data['target'],data['stat'],data['base']
    from module_rules import module_stats, VERSION
    return dict(id=uid(), type_id=ident, name=name, kind='module', rarity=tier, weight=data.get('weight',.3),
                value=30 * (tier + 1) ** 2, target=target, stats=module_stats(ident,tier,1),module_balance_version=VERSION)


def supply(kind):
    return dict(id=uid(),**content.consumable(kind))


def stats(item):
    from module_rules import gear_stats
    return gear_stats(item)


def item_weight(item):
    from module_rules import item_weight as effective_weight
    return effective_weight(item)


def item_value(item):
    return item['value'] + sum(item_value(m) for m in item.get('modules', []))


def compatible(item, mod):
    from module_rules import compatible as check
    return check(item, mod)


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


class LegacyGame:
    def __init__(self, seed=None):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        self.rng = random.Random(seed)
        self.messages = []
        self.turn = 0
        self.x, self.y = 5, 5
        self.hp = 100
        self.money = 180
        self.xp = 0
        self.active = 'weapon1'
        self.equipped = {'weapon1': equipment('weapon_ash_pistol', 1),
                         'weapon2': equipment('weapon_watch_rifle'),
                         'armor': equipment('armor_plated_jacket'),
                         'helmet': equipment('helmet_seeker')}
        self.bag = [module(index=0), module(index=3), supply('med'), supply('med'),
                    supply('food'), supply('food'), supply('food')]
        self.loot = []
        self.battle = None
        self.cities = [[5, 5], [19, 8], [36, 6], [12, 25], [40, 26]]
        self.world = [[self.rng.choices(['waste', 'forest', 'ruin'], [65, 23, 12])[0]
                       for _ in range(48)] for _ in range(32)]
        for a, b in zip(self.cities, self.cities[1:]):
            for x in range(min(a[0], b[0]), max(a[0], b[0])+1):
                self.world[a[1]][x] = 'road'
            for y in range(min(a[1], b[1]), max(a[1], b[1])+1):
                self.world[y][b[0]] = 'road'
        for x, y in self.cities:
            self.world[y][x] = 'city'
        self.shops = {}
        self.searched = []
        self.log(tr('afterdays.0029'))

    @property
    def level(self):
        """Обчислює поточний рівень гравця за накопиченим досвідом."""
        return 1 + self.xp // 100

    @property
    def max_hp(self):
        """Обчислює максимальне здоров’я з рівня, перків і спорядження."""
        return 100 + (self.level - 1) * 8

    @property
    def weight(self):
        """Підсумовує вагу предметів, які несе гравець."""
        return round(sum(item_weight(i) for i in self.bag) +
                     sum(item_weight(i) for i in self.equipped.values() if i), 2)

    @property
    def capacity(self):
        """Обчислює максимальну вагу з урахуванням бонусів."""
        return 35.0

    @property
    def defense(self):
        """Обчислює сумарний захист екіпіровки й перків."""
        return sum(stats(i).get('defense', 0) for i in self.equipped.values() if i)

    @property
    def weapon(self):
        """Повертає зброю з активної руки."""
        return self.equipped[self.active]

    @property
    def city(self):
        """Визначає поселення під поточною позицією гравця."""
        return self.cities.index([self.x, self.y]) if [self.x, self.y] in self.cities else None

    def log(self, msg, color=None):
        """Додає повідомлення до журналу гри."""
        colors=getattr(self,'message_colors',[])
        colors=([None]*len(self.messages)+colors)[-len(self.messages):] if self.messages else []
        colors.append(color or getattr(self,'_event_feedback_color',None))
        self.message_colors=colors[-80:]
        self.messages.append(msg)
        self.messages = self.messages[-80:]

    def find(self, item_id):
        """Знаходить предмет за ідентифікатором."""
        return next((i for i in self.bag + [v for v in self.equipped.values() if v]
                     if i['id'] == item_id), None)

    def accept(self, item):
        """Перевіряє можливість отримання предмета і додає його до сумки."""
        if self.weight + item_weight(item) > self.capacity + .0001:
            self.log(tr('afterdays.0030'))
            return False
        self.bag.append(item)
        return True

    def equip(self, item_id, slot):
        """Одягає предмет у відповідний слот спорядження."""
        if self.battle:
            self.log(tr('afterdays.0031'))
            return False
        item = self.find(item_id)
        if not item or item not in self.bag or slot not in SLOTS:
            return False
        expected = 'weapon' if slot.startswith('weapon') else slot
        if item['kind'] != expected:
            return False
        old = self.equipped[slot]
        self.bag.remove(item)
        if old:
            self.bag.append(old)
        self.equipped[slot] = item
        self.log(tr('afterdays.0032', v0=item['name']))
        return True

    def unequip(self, slot):
        """Знімає предмет зі слота назад у сумку."""
        if self.battle or not self.equipped[slot]:
            return False
        self.bag.append(self.equipped[slot])
        self.equipped[slot] = None
        return True

    def install(self, item_id, mod_id):
        """Встановлює сумісний модуль у вільний слот спорядження."""
        if self.battle:
            return False
        item, mod = self.find(item_id), self.find(mod_id)
        if not item or not mod or mod not in self.bag or not compatible(item, mod):
            return False
        if len(item['modules']) >= item['slots']:
            self.log(tr('afterdays.0033'))
            return False
        self.bag.remove(mod)
        item['modules'].append(mod)
        self.log(f"{mod['name']} → {item['name']}.")
        return True

    def uninstall(self, item_id, mod_id):
        """Знімає модуль і повертає його в інвентар."""
        if self.battle:
            return False
        item = self.find(item_id)
        if not item:
            return False
        mod = next((m for m in item.get('modules', []) if m['id'] == mod_id), None)
        if not mod:
            return False
        item['modules'].remove(mod)
        self.bag.append(mod)
        return True

    def use(self, kind):
        """Застосовує ефект розхідника і зменшує його кількість."""
        item = next((i for i in self.bag if i['kind'] == kind), None)
        if not item:
            self.log(tr('afterdays.0034') if kind == 'med' else tr('afterdays.0035'))
            return False
        if self.hp >= self.max_hp:
            self.log(tr('afterdays.0036'))
            return False
        if self.battle and self.battle['ap'] < 2:
            self.log(tr('afterdays.0037'))
            return False
        self.bag.remove(item)
        healing = min(self.max_hp - self.hp, 40 if kind == 'med' else 14)
        self.hp += healing
        if self.battle:
            self.battle['ap'] -= 2
        self.log(tr('afterdays.0038', v0=item['name'], v1=healing))
        return True

    def step(self, dx, dy):
        """Виконує крок світом і запускає пов’язані з ходом події."""
        if self.battle:
            return self.battle_move((self.battle['pos'][0]+dx, self.battle['pos'][1]+dy))
        if abs(dx) + abs(dy) != 1 or not (0 <= self.x+dx < len(self.world[0]) and 0 <= self.y+dy < 32):
            return False
        self.x += dx
        self.y += dy
        self.turn += 1
        if self.turn % 8 == 0:
            food = next((i for i in self.bag if i['kind'] == 'food'), None)
            if food:
                self.bag.remove(food)
                self.hp = min(self.max_hp, self.hp + 10)
                self.log(tr('afterdays.0039'))
            else:
                self.hp = max(1, self.hp - 5)
                self.log(tr('afterdays.0040'))
        terrain = self.world[self.y][self.x]
        if self.city is not None:
            self.log(tr('afterdays.0041', v0=CITY_NAMES[self.city]))
        elif self.rng.random() < {'road': .06, 'waste': .12, 'forest': .20, 'ruin': .24}[terrain]:
            self.start_battle()
        return True

    def search(self):
        """Виконує пошук на місцевості та перевіряє квестові цілі."""
        if self.battle or self.city is not None:
            return False
        key = [self.x, self.y]
        if key in self.searched:
            self.log(tr('afterdays.0042'))
            return False
        self.searched.append(key)
        self.turn += 1
        self.loot.extend([self.roll_item(), supply(self.rng.choice(['food', 'med']))])
        self.log(tr('afterdays.0043'))
        if self.rng.random() < .35:
            self.start_battle()
        return True

    def roll_item(self):
        """Генерує випадковий предмет за поточними правилами."""
        tier = self.rng.choices(range(5), [50, 28, 14, 6, 2])[0]
        return module(tier, self.rng) if self.rng.random() < .65 else equipment(tier=tier, rng=self.rng)

    def start_battle(self):
        """Створює бойовий стан, ворогів та арену поточної зустрічі."""
        w, h = 15, 11
        pos = (1, 5)
        walls = {(x, y) for y in range(h) for x in range(3, w-1)
                 if self.rng.random() < .16}
        reachable = {pos}
        q = deque([pos])
        while q:
            for p in neighbors(*q.popleft(), w, h):
                if p not in walls and p not in reachable:
                    reachable.add(p)
                    q.append(p)
        candidates = sorted(p for p in reachable if p[0] >= 9)
        if len(candidates) < 4:
            walls = {p for p in walls if p[1] != 5}
            candidates = [(x, 5) for x in range(9, 14)]
        self.rng.shuffle(candidates)
        enemies = []
        danger = min(5, __import__('world_hex').distance((self.x,self.y),(5,5)) // 9)
        for n in range(self.rng.randint(2, 3)):
            kind = self.rng.randrange(3)
            name, hp, damage, reach, speed = [
                (tr('afterdays.0044'), 23, 8, 1, 3), (tr('afterdays.0045'), 36, 11, 1, 2),
                (tr('afterdays.0046'), 26, 9, 5, 2)][kind]
            hp += int(danger * 5)
            enemies.append(dict(id=n, name=name, hp=hp, max_hp=hp, damage=damage+int(danger),
                                range=reach, speed=speed, pos=list(candidates[n]), kind=kind))
        self.battle = dict(w=w, h=h, walls=[list(p) for p in sorted(walls)], pos=list(pos),
                           enemies=enemies, ap=6, round=1)
        self.log(tr('afterdays.0047'))

    def battle_move(self, target):
        """Переміщує гравця по арені й витрачає необхідні ОД."""
        b = self.battle
        if not b:
            return False
        occupied = set(map(tuple, b['walls'])) | {tuple(e['pos']) for e in b['enemies']}
        route = hexgrid.path_to(tuple(b['pos']), tuple(target), b['w'], b['h'], occupied)
        if not route or len(route) > b['ap']:
            self.log(tr('afterdays.0048'))
            return False
        b['pos'] = list(target)
        b['ap'] -= len(route)
        return True

    def shot_info(self, enemy):
        """Повертає допустимість пострілу, причину відмови та шанс влучання."""
        b, weapon = self.battle, self.weapon
        if not b or not weapon:
            return False, tr('afterdays.0049'), 0
        s = __import__('module_rules').weapon_stats(self,weapon)
        distance = hexgrid.distance(b['pos'], enemy['pos'])
        if distance > s['range']:
            return False, tr('afterdays.0050'), 0
        if not hexgrid.visible(tuple(b['pos']), tuple(enemy['pos']), b['walls']):
            return False, tr('afterdays.0051'), 0
        chance = max(45, min(98, s['accuracy'] - int(max(0, distance-3)*3)))
        return True, '', chance

    def shoot(self, enemy_id):
        """Перевіряє можливість пострілу та обробляє його наслідки."""
        b = self.battle
        if not b:
            return False
        e = next((e for e in b['enemies'] if e['id'] == enemy_id), None)
        if not e:
            return False
        valid, reason, chance = self.shot_info(e)
        if not valid:
            self.log(reason)
            return False
        if b['ap'] < self.weapon['ap']:
            self.log(tr('afterdays.0052', v0=self.weapon['ap']))
            return False
        b['ap'] -= self.weapon['ap']
        if self.rng.randrange(100) < chance:
            damage = max(1, stats(self.weapon)['damage'] + (self.level-1)*2 + self.rng.randint(-2, 2))
            e['hp'] -= damage
            self.log(tr('afterdays.0053', v0=e['name'], v1=damage, v2=chance))
            if e['hp'] <= 0:
                b['enemies'].remove(e)
                self.xp += 20//(2 if getattr(self,'coward_turns',0) else 1)
                self.log(tr('afterdays.0054', v0=e['name']))
            if not b['enemies']:
                self.victory()
        else:
            self.log(tr('afterdays.0055', v0=chance))
        return True

    def switch(self):
        """Перемикає активну руку зі зброєю."""
        other = 'weapon2' if self.active == 'weapon1' else 'weapon1'
        if not self.equipped[other]:
            self.log(tr('afterdays.0056'))
            return False
        if self.battle:
            if self.battle['ap'] < 1:
                self.log(tr('afterdays.0057'))
                return False
            self.battle['ap'] -= 1
        self.active = other
        self.hp = min(self.hp,self.max_hp)
        return True

    def end_turn(self):
        """Передає хід ворогам і відновлює ОД наступного ходу."""
        b = self.battle
        if not b:
            return
        for e in b['enemies']:
            for _ in range(e['speed']):
                if math.dist(e['pos'], b['pos']) <= e['range'] and visible(tuple(e['pos']), tuple(b['pos']), b['walls']):
                    break
                blocked = set(map(tuple, b['walls'])) | {tuple(other['pos']) for other in b['enemies'] if other is not e}
                route = hexgrid.path_to(tuple(e['pos']), tuple(b['pos']), b['w'], b['h'], blocked)
                if route and route[0] != tuple(b['pos']):
                    e['pos'] = list(route[0])
            if math.dist(e['pos'], b['pos']) <= e['range'] and visible(tuple(e['pos']), tuple(b['pos']), b['walls']):
                damage = max(1, e['damage'] + self.rng.randint(-2, 2) - self.defense)
                self.hp -= damage
                self.log(tr('afterdays.0058', v0=e['name'], v1=damage))
                if self.hp <= 0:
                    self.defeat()
                    return
        b['ap'] = 6
        b['round'] += 1
        self.log(tr('afterdays.0059', v0=b['round']))

    def victory(self):
        """Завершує переможний бій і нараховує його результати."""
        self.battle = None
        reward = self.rng.randint(45, 85)
        self.money += reward
        self.loot.extend([self.roll_item(), self.roll_item(), supply('med')])
        self.log(tr('afterdays.0060', v0=reward))

    def flee(self):
        """Намагається вивести гравця з бою."""
        if not self.battle:
            return False
        if self.battle['pos'][0] != 0 or self.battle['ap'] < 2:
            self.log(tr('afterdays.0061'))
            return False
        self.battle = None
        self.log(tr('afterdays.0062'))
        return True

    def defeat(self):
        """Обробляє поразку гравця і завершує бойовий стан."""
        loss = getattr(self,'carried_money',self.money)
        self.money -= loss
        self.x, self.y = self.cities[0]
        self.hp = self.max_hp
        self.battle = None
        self.loot.clear()
        if not getattr(self,'_grave_death',False):self.log(tr('afterdays.0063', v0=loss))

    def rest(self):
        """Відновлює гравця під час відпочинку в поселенні."""
        if self.city is None or self.battle:
            return False
        if self.hp == self.max_hp and not getattr(self,'coward_turns',0) and getattr(self,'hunger',20)>=20 and [self.x,self.y]==getattr(self,'respawn_pos',self.cities[0]):
            self.log(tr('afterdays.0064'))
            return False
        if self.money < 15:
            self.log(tr('afterdays.0065'))
            return False
        self.money -= 15
        self.hp = self.max_hp
        self.turn += 4
        self.log(tr('afterdays.0066'))
        return True

    def stock(self, merchant):
        """Повертає або оновлює асортимент торговця."""
        if self.city is None or self.battle:
            return []
        key = f'{self.city}:{merchant}'
        entry = self.shops.get(key)
        if entry is None or self.turn - entry['turn'] >= 40:
            if merchant == 0:
                items = [equipment(name, self.rng.randrange(3), self.rng) for name in GEAR]
                items += [module(t, self.rng, idx) for t in range(5) for idx in range(4)]
            elif merchant == 1:
                items = [supply('med') for _ in range(5)] + [supply('food') for _ in range(8)]
            else:
                items = [self.roll_item() for _ in range(10)]
            entry = self.shops[key] = dict(turn=self.turn, items=items)
        return entry['items']

    def price(self, item, merchant, buying=True):
        """Обчислює ціну купівлі або продажу предмета."""
        if buying:
            return 85 if merchant == 2 else int(item_value(item)*1.15)
        return max(1, int(item_value(item) * (.22 if merchant == 2 else .50)))

    def buys_kind(self, item, merchant):
        """Перевіряє, чи приймає торговець цей предмет."""
        return merchant == 2 or item['kind'] in (('weapon', 'armor', 'helmet', 'module') if merchant == 0 else ('food', 'med'))

    def buy(self, item_id, merchant):
        """Перевіряє ціну й місткість та купує вибрану кількість товару."""
        items = self.stock(merchant)
        item = next((i for i in items if i['id'] == item_id), None)
        if not item:
            return False
        price = self.price(item, merchant)
        if self.money < price:
            self.log(tr('afterdays.0067'))
            return False
        if not self.accept(item):
            return False
        self.money -= price
        items.remove(item)
        self.log(tr('afterdays.0068', v0=item['name'], v1=RARITIES[item['rarity']][0]))
        return True

    def sell(self, item_id, merchant):
        """Продає дозволений товар і нараховує гроші."""
        if self.city is None or self.battle:
            return False
        item = next((i for i in self.bag if i['id'] == item_id), None)
        if not item or not self.buys_kind(item, merchant):
            self.log(tr('afterdays.0069'))
            return False
        price = self.price(item, merchant, False)
        self.bag.remove(item)
        self.money += price
        self.log(tr('afterdays.0070', v0=item['name'], v1=price))
        return True

    def collect(self, item_id):
        """Переносить доступний предмет зі здобичі до сумки."""
        if self.battle:
            return False
        item = next((i for i in self.loot if i['id'] == item_id), None)
        if item and self.accept(item):
            self.loot.remove(item)
            return True
        return False

    def save(self, path):
        """Записує стан гри у файл збереження."""
        data = {key: value for key, value in vars(self).items() if key != 'rng'}
        data['version'] = 1
        data['rng_state'] = self.rng.getstate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, path)

    @classmethod
    def load(cls, path):
        """Завантажує збереження та застосовує міграції цієї версії."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if data.pop('version', None) != 1:
            raise ValueError(tr('afterdays.0071'))
        def tuples(value):
            return tuple(tuples(i) for i in value) if isinstance(value, list) else value
        state = tuples(data.pop('rng_state'))
        game = cls(0)
        required = set(vars(game)) - {'rng'}
        if set(data) != required or len(data['world']) != 32 or set(data['equipped']) != set(SLOTS):
            raise ValueError(tr('afterdays.0072'))
        game.__dict__.update(data)
        game.rng.setstate(state)
        return game



# Expanded content. All sprites are drawn locally with Canvas in visuals.py.
STAT_NAMES.update({key:tr('modules.'+key) for key in ('weight_percent','ammo_save_percent','reflect_percent','damage_electric','damage_piercing')})
STAT_NAMES.update(strength=tr('update031.strength'),local_damage_percent=tr('update031.local_damage'),local_defense_percent=tr('update031.local_defense'))
STAT_NAMES.update(damage_percent=tr('modules.damage_percent'),defense_percent=tr('modules.defense_percent'),max_condition_percent=tr('modules.max_condition_percent'))
STAT_NAMES.update(attack=tr('afterdays.0073'), pierce=tr('afterdays.0074'), crit=tr('afterdays.0075'), vitality=tr('afterdays.0076'),
                  capacity=tr('afterdays.0077'), evasion=tr('afterdays.0078'), regen=tr('afterdays.0079'))
CITY_NAMES.extend([tr('afterdays.0080'), tr('afterdays.0081'), tr('afterdays.0082'), tr('afterdays.0083'),
                   tr('afterdays.0084'), tr('afterdays.0085'), tr('afterdays.0086')])
MERCHANTS.append(tr('afterdays.0087'))
MONSTERS = content.MONSTERS
EXTRA_CITIES = [[5, 15], [27, 4], [28, 16], [4, 28], [44, 15], [24, 28], [17, 17]]
MAYORS = [0, 2, 3, 5, 7, 9, 11]
QUEST_KINDS = ['hunt', 'retrieve', 'scout', 'supplies', 'purge']
QUEST_LABELS = {'hunt': tr('afterdays.0088'), 'retrieve': tr('afterdays.0089'),
                'scout': tr('afterdays.0090'), 'supplies': tr('afterdays.0091'), 'purge': tr('afterdays.0092')}


class ExpansionGame(LegacyGame):
    def __init__(self, seed=None):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        super().__init__(seed)
        self.cities.extend([p[:] for p in EXTRA_CITIES])
        self.city_merchants = [[0, 1, 2] if i == 0 else [1] +
                               ([0] if i % 3 != 1 else []) + ([2] if i % 2 == 0 else [])
                               for i in range(len(self.cities))]
        self.mayors = MAYORS[:]
        self.quests = []
        self.offers = {}
        self.traveler = None
        self.last_traveler_turn = -20
        self.quest_battle = None
        self._connect_cities()

    def _connect_cities(self):
        """Прокладає дороги між основними поселеннями."""
        for point in self.cities[5:]:
            near = min(self.cities[:5], key=lambda p: __import__('world_hex').distance(p,point))
            for x in range(min(near[0], point[0]), max(near[0], point[0])+1):
                self.world[point[1]][x] = 'road'
            for y in range(min(near[1], point[1]), max(near[1], point[1])+1):
                self.world[y][near[0]] = 'road'
        for x, y in self.cities:
            self.world[y][x] = 'city'

    def protection_stat(self, key):
        """Підсумовує вказаний бонус захисного спорядження."""
        return sum(stats(i).get(key, 0) for i in self.equipped.values() if i and i['kind'] != 'weapon')

    @property
    def capacity(self):
        """Обчислює максимальну вагу з урахуванням бонусів."""
        return 35.0 + self.protection_stat('capacity')

    @property
    def max_hp(self):
        """Обчислює максимальне здоров’я з рівня, перків і спорядження."""
        return 100 + (self.level-1)*8 + self.protection_stat('vitality')

    def _change_gear(self, fn):
        # Transactional rollback if removing a load-bearing item would overload the player.
        """Атомарно змінює спорядження з відкатом при перевищенні місткості."""
        import copy
        before = copy.deepcopy((self.bag, self.equipped))
        ok = fn()
        if ok and self.weight > self.capacity + .0001:
            self.bag, self.equipped = before
            self.log(tr('afterdays.0093'))
            return False
        self.hp = min(self.hp, self.max_hp)
        return ok

    def equip(self, item_id, slot):
        """Одягає предмет у відповідний слот спорядження."""
        return self._change_gear(lambda: super(ExpansionGame, self).equip(item_id, slot))

    def unequip(self, slot):
        """Знімає предмет зі слота назад у сумку."""
        return self._change_gear(lambda: super(ExpansionGame, self).unequip(slot))

    def uninstall(self, item_id, mod_id):
        """Знімає модуль і повертає його в інвентар."""
        return self._change_gear(lambda: super(ExpansionGame, self).uninstall(item_id, mod_id))

    def put_module(self, item_id, mod_id, slot_index):
        """Встановлює модуль у конкретний слот із заміною попереднього."""
        item = self.find(item_id)
        mod = self.find(mod_id)
        if self.battle or not item or not mod or mod not in self.bag or not compatible(item, mod):
            return False
        if not 0 <= slot_index < item['slots']:
            return False
        if slot_index >= len(item['modules']):
            return self.install(item_id, mod_id)
        def replace():
            old = item['modules'][slot_index]
            self.bag.remove(mod)
            self.bag.append(old)
            item['modules'][slot_index] = mod
            self.log(tr('afterdays.0094', v0=old['name'], v1=mod['name']))
            return True
        return self._change_gear(replace)

    def available_merchant(self, merchant):
        """Перевіряє доступність вказаного торговця у поточній локації."""
        if self.battle:
            return False
        if merchant == 3:
            return bool(self.traveler and self.traveler['pos'] == [self.x, self.y])
        return self.city is not None and merchant in self.city_merchants[self.city]

    def stock(self, merchant):
        """Повертає або оновлює асортимент торговця."""
        if not self.available_merchant(merchant):
            return []
        if merchant == 3:
            return self.traveler['items']
        key = f'{self.city}:{merchant}'
        entry = self.shops.get(key)
        if entry is None or self.turn-entry['turn'] >= 40:
            if merchant == 0:
                names = self.rng.sample(list(GEAR), 12)
                items = [equipment(n, self.rng.randrange(3), self.rng) for n in names]
                items += [module(self.rng.choices(range(5), [25, 30, 25, 15, 5])[0], self.rng, i) for i in range(len(MODULES))]
            elif merchant == 1:
                items = [supply('med') for _ in range(7)] + [supply('food') for _ in range(12)]
            else:
                items = [self.roll_item() for _ in range(10)]
            entry = self.shops[key] = dict(turn=self.turn, items=items)
        return entry['items']

    def price(self, item, merchant, buying=True):
        """Обчислює ціну купівлі або продажу предмета."""
        if merchant == 3:
            return max(1, int(item_value(item) * (.5 if buying else .3)))
        return super().price(item, merchant, buying)

    def buys_kind(self, item, merchant):
        """Перевіряє, чи приймає торговець цей предмет."""
        if item['kind'] == 'quest':
            return False
        return merchant == 3 or super().buys_kind(item, merchant)

    def sell(self, item_id, merchant):
        """Продає дозволений товар і нараховує гроші."""
        if not self.available_merchant(merchant):
            return False
        item = next((i for i in self.bag if i['id'] == item_id), None)
        if not item or not self.buys_kind(item, merchant):
            return False
        self.money += self.price(item, merchant, False)
        self.bag.remove(item)
        self.log(tr('afterdays.0095', v0=item['name']))
        return True

    def spawn_traveler(self):
        """Обирає й створює випадкового мандрівника поблизу гравця."""
        rare = equipment(tier=self.rng.choice([3, 4]), rng=self.rng)
        self.traveler = dict(pos=[self.x, self.y], items=[rare, module(4, self.rng)] +
                             [supply('food') for _ in range(5)] + [supply('med') for _ in range(3)])
        self.last_traveler_turn = self.turn
        self.log(tr('afterdays.0096'))

    def step(self, dx, dy):
        """Виконує крок світом і запускає пов’язані з ходом події."""
        in_battle = bool(self.battle)
        old = [self.x, self.y]
        ok = super().step(dx, dy)
        if ok and not in_battle and old != [self.x, self.y]:
            self.traveler = None
            self._visit_objectives()
            if not self.battle and self.city is None and self.turn-self.last_traveler_turn >= 7 and self.rng.random() < .09:
                self.spawn_traveler()
        return ok

    def _visit_objectives(self):
        """Оновлює завдання, пов’язані з відвідуванням поточної клітинки."""
        for q in self.quests:
            if q['status'] == 'active' and q['kind'] == 'scout' and not q.get('area') and q['pos'] == [self.x, self.y]:
                q['progress'] = 1
                self.log(tr('afterdays.0097'))

    def start_battle(self):
        """Створює бойовий стан, ворогів та арену поточної зустрічі."""
        super().start_battle()
        danger = min(5, int(__import__('world_hex').distance((self.x,self.y),(5,5))//9))
        for e in self.battle['enemies']:
            kind = self.rng.randrange(min(len(MONSTERS), 6 + danger*2))
            name, hp, damage, reach, speed, armor, color = MONSTERS[kind]
            hp += danger*4
            e.update(name=name, hp=hp, max_hp=hp, damage=damage+danger, range=reach,
                     speed=speed, armor=armor, kind=kind)

    def shoot(self, enemy_id):
        """Перевіряє можливість пострілу та обробляє його наслідки."""
        b = self.battle
        if not b:
            return False
        e = next((e for e in b['enemies'] if e['id'] == enemy_id), None)
        if e is None:
            return False
        valid, reason, chance = self.shot_info(e)
        if not valid:
            self.log(reason)
            return False
        if b['ap'] < self.weapon['ap']:
            self.log(tr('afterdays.0098', v0=self.weapon['ap']))
            return False
        b['ap'] -= self.weapon['ap']
        if self.rng.randrange(100) < chance:
            s = stats(self.weapon)
            critical = self.rng.randrange(100) < min(65, 5+s.get('crit', 0))
            raw = s['damage'] + (self.level-1)*2 + self.rng.randint(-2, 2)
            damage = max(1, int(raw*(1.6 if critical else 1))-max(0, e.get('armor', 0)-s.get('pierce', 0)))
            e['hp'] -= damage
            self.log(f"{tr('afterdays.0099') if critical else ''}{e['name']}: −{damage} HP.")
            if e['hp'] <= 0:
                b['enemies'].remove(e)
                self.xp += 20//(2 if getattr(self,'coward_turns',0) else 1)
                self._kill_objectives(e['kind'])
                self.log(tr('afterdays.0100', v0=e['name']))
            if not b['enemies']:
                self.victory()
        else:
            self.log(tr('afterdays.0101', v0=chance))
        return True

    def end_turn(self):
        """Передає хід ворогам і відновлює ОД наступного ходу."""
        b = self.battle
        if not b:
            return
        for e in b['enemies']:
            if e['kind'] == 8:
                e['hp'] = min(e['max_hp'], e['hp']+3)
            for _ in range(e['speed']):
                if math.dist(e['pos'], b['pos']) <= e['range'] and visible(tuple(e['pos']), tuple(b['pos']), b['walls']):
                    break
                blocked = set(map(tuple, b['walls'])) | {tuple(other['pos']) for other in b['enemies'] if other is not e}
                route = hexgrid.path_to(tuple(e['pos']), tuple(b['pos']), b['w'], b['h'], blocked)
                if route and route[0] != tuple(b['pos']):
                    e['pos'] = list(route[0])
            if math.dist(e['pos'], b['pos']) <= e['range'] and visible(tuple(e['pos']), tuple(b['pos']), b['walls']):
                if self.rng.randrange(100) < min(45, self.protection_stat('evasion')):
                    self.log(tr('afterdays.0102', v0=e['name']))
                    continue
                damage = max(1, e['damage'] + self.rng.randint(-2, 2) - self.defense)
                self.hp -= damage
                self.log(tr('afterdays.0103', v0=e['name'], v1=damage))
                if self.hp <= 0:
                    self.defeat()
                    return
        healing = min(self.max_hp-self.hp, self.protection_stat('regen'))
        if healing:
            self.hp += healing
            self.log(tr('afterdays.0104', v0=healing))
        b['ap'] = 6
        b['round'] += 1
        self.log(tr('afterdays.0105', v0=b['round']))

    def victory(self):
        """Завершує переможний бій і нараховує його результати."""
        quest_id = self.quest_battle
        super().victory()
        if quest_id:
            q = next((q for q in self.quests if q['id'] == quest_id and q['status'] == 'active'), None)
            if q:
                q['progress'] = 1
                self.log(tr('afterdays.0106'))
        self.quest_battle = None

    def flee(self):
        """Намагається вивести гравця з бою."""
        ok = super().flee()
        if ok:
            self.quest_battle = None
        return ok

    def defeat(self):
        """Обробляє поразку гравця і завершує бойовий стан."""
        super().defeat()
        self.quest_battle = None
        self.traveler = None

    def mayor_offers(self):
        """Повертає актуальний список доступних завдань квестодавця."""
        if self.city not in self.mayors or self.battle:
            return []
        key = str(self.city)
        if key not in self.offers:
            kinds = QUEST_KINDS[:] if self.city == 0 else self.rng.sample(QUEST_KINDS, 3)
            result = []
            for kind in kinds:
                target_kind = self.rng.choice([0, 1, 2, 3, 4, 5])
                result.append(dict(id=uid(), kind=kind, city=self.city, status='offered',
                                   title=QUEST_LABELS[kind], progress=0, goal=4 if kind == 'hunt' else 1,
                                   target_kind=target_kind if self.city % 2 else None,
                                   reward=210 if kind in ('retrieve', 'purge') else 150,
                                   pos=None))
            self.offers[key] = result
        return self.offers[key]

    def accept_quest(self, quest_id):
        """Приймає завдання і створює його цілі та необхідні квестові предмети."""
        offer = next((q for q in self.mayor_offers() if q['id'] == quest_id and q['status'] == 'offered'), None)
        if not offer:
            return False
        if sum(q['status'] == 'active' for q in self.quests) >= 8:
            self.log(tr('afterdays.0107'))
            return False
        q = dict(offer)
        q['status'] = 'active'
        if q['kind'] in ('retrieve', 'scout', 'purge'):
            occupied = {tuple(t['pos']) for t in self.quests if t.get('pos') and t['status'] == 'active'}
            candidates = [(x, y) for y in range(32) for x in range(len(self.world[0]))
                          if 4 <= abs(x-self.x)+abs(y-self.y) <= 12 and [x, y] not in self.cities and (x, y) not in occupied]
            if hasattr(self, 'quest_locations'):candidates=self.quest_locations(q)
            if not candidates:
                self.log(tr('afterdays.0108'))
                return False
            q['pos'] = list(self.rng.choice(candidates))
        offer['status'] = 'accepted'
        self.quests.append(q)
        self.log(tr('afterdays.0109', v0=q['title']))
        return True

    def _kill_objectives(self, kind):
        """Оновлює завдання на вбивство з перевіркою типу ворога і зони."""
        for q in self.quests:
            if q['status'] == 'active' and q['kind'] == 'hunt' and (q['target_kind'] is None or content.monster_id(q.get('target_type_id') or q['target_kind']) == content.monster_id(kind)):
                q['progress'] = min(q['goal'], q['progress']+1)

    def quest_ready(self, q):
        """Перевіряє виконання всіх умов для здачі завдання."""
        if q['status'] != 'active':
            return False
        if q['kind'] == 'supplies':
            return sum(i['kind'] == 'food' for i in self.bag) >= 3 and sum(i['kind'] == 'med' for i in self.bag) >= 2
        if q['kind'] == 'retrieve':
            return any(i.get('quest_id') == q['id'] for i in self.bag)
        return q['progress'] >= q['goal']

    def quest_text(self, q):
        """Формує опис цілі, прогресу й винагороди завдання."""
        kind = q['kind']
        if kind == 'hunt':
            target = tr('afterdays.0110') if q['target_kind'] is None else MONSTERS[q['target_kind']][0]
            desc = tr('afterdays.0111', v0=target, v1=q['progress'], v2=q['goal'])
        elif kind == 'retrieve':
            desc = tr('afterdays.0112')
        elif kind == 'scout':
            desc = tr('afterdays.0113')
        elif kind == 'supplies':
            food = sum(i['kind'] == 'food' for i in self.bag)
            med = sum(i['kind'] == 'med' for i in self.bag)
            desc = tr('afterdays.0114', v0=food, v1=med)
        else:
            desc = tr('afterdays.0115')
        if q.get('pos'):
            desc += tr('afterdays.0116', v0=q['pos'][0], v1=q['pos'][1])
        state = tr('afterdays.0117') if q['status'] == 'offered' else (tr('afterdays.0118') if q['status'] == 'done' else (tr('afterdays.0119') if self.quest_ready(q) else tr('afterdays.0120')))
        return tr('afterdays.0121', v0=q['title'], v1=desc, v2=CITY_NAMES[q['city']], v3=q['reward'], v4=state)

    def turn_in(self, quest_id):
        """Перевіряє умови здачі, видає нагороду й завершує завдання."""
        q = next((q for q in self.quests if q['id'] == quest_id), None)
        if self.battle or not q or self.city != q['city'] or not self.quest_ready(q):
            self.log(tr('afterdays.0122'))
            return False
        if q['kind'] == 'retrieve':
            self.bag[:] = [i for i in self.bag if i.get('quest_id') != q['id']]
        elif q['kind'] == 'supplies':
            for kind, count in [('food', 3), ('med', 2)]:
                for _ in range(count):
                    self.bag.remove(next(i for i in self.bag if i['kind'] == kind))
        q['status'] = 'done'
        self.money += q['reward']
        self.xp += 40//(2 if getattr(self,'coward_turns',0) else 1)
        self.log(tr('afterdays.0123', v0=q['title'], v1=q['reward']))
        return True

    def search(self):
        """Виконує пошук на місцевості та перевіряє квестові цілі."""
        if self.battle or self.city is not None:
            return False
        for q in self.quests:
            if q['status'] != 'active' or q.get('pos') != [self.x, self.y] or self.quest_ready(q):
                continue
            if q['kind'] == 'retrieve':
                item = dict(id=uid(), name=tr('afterdays.0124'), kind='quest', type_id='quest_item', rarity=2,
                            weight=0, value=0, quest_id=q['id'])
                self.bag.append(item)
                q['progress'] = 1
                self.turn += 1
                self.log(tr('afterdays.0125'))
                return True
            if q['kind'] == 'purge':
                self.start_battle()
                self.quest_battle = q['id']
                for e in self.battle['enemies']:
                    e['max_hp'] += 12
                    e['hp'] += 12
                self.log(tr('afterdays.0126'))
                return True
        return super().search()

    def save(self, path):
        """Записує стан гри у файл збереження."""
        data = {key: value for key, value in vars(self).items() if key != 'rng'}
        data['version'] = 2
        data['rng_state'] = self.rng.getstate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, path)

    @classmethod
    def load(cls, path):
        """Завантажує збереження та застосовує міграції цієї версії."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        version = data.pop('version', None)
        if version not in (1, 2):
            raise ValueError(tr('afterdays.0127'))
        def tuples(v):
            return tuple(tuples(x) for x in v) if isinstance(v, list) else v
        state = tuples(data.pop('rng_state'))
        game = cls(0)
        allowed = set(vars(game))-{'rng'}
        if set(data)-allowed or len(data['world']) != 32 or set(data['equipped']) != set(SLOTS):
            raise ValueError(tr('afterdays.0128'))
        if version == 2 and set(data) != allowed:
            raise ValueError(tr('afterdays.0129'))
        game.__dict__.update(data)
        if version == 1:
            game.cities.extend([p[:] for p in EXTRA_CITIES])
            game._connect_cities()
            game.shops = {}
            game.log(tr('afterdays.0130'))
        game.rng.setstate(state)
        return game


from progression import equipment, module, supply, stats, item_weight, item_value
from update047 import Game
from reputation import buy_factor, sell_factor

# GUI imports are delayed so the model and tests work without a display.
def launch(test_hook=None):
    import tkinter as tk
    from tkinter import ttk, messagebox
    import visuals
    import advanced_ui
    import progression
    import adventure
    import adventure_ui
    import refinement_ui
    import sprites
    import terrain_tiles

    BG, PANEL, TEXT, MUTED, GOLD = '#141c1a', '#202b27', '#e4e8d9', '#a4b2a4', '#d7b77a'
    save_path = Path.home() / 'Afterdays' / 'save.json'

    class App(MapVisibility):
        def __init__(self, root):
            """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
            self.root = root
            root.app=self
            self.game = Game()
            self.game.prepare_campaign()
            self.show_full_map = False
            self.perk_prompted = -1
            self.mode = 'world'
            self.selection = None
            self.inventory_ids = []
            self.shop_ids = []
            self.merchant = 0
            self.dialog = None
            self.hover = None
            root.after_idle(lambda:sprites.decorate(root))
            root._afterdays_app=self
            root.title(tr('afterdays.0131'))
            sw,sh=root.winfo_screenwidth(),root.winfo_screenheight()
            root.geometry(f'1260x880+{max(0,(sw-1260)//2)}+{max(0,(sh-880)//2)}')
            root.minsize(1080, 760)
            root.configure(bg=BG)
            style = ttk.Style()
            style.theme_use('clam')
            style.configure('.', background=PANEL, foreground=TEXT, font=('Segoe UI', 10))
            style.configure('TButton', padding=(9, 7), background='#344238', foreground=TEXT)
            style.map('TButton', background=[('active', '#536348')], foreground=[('disabled', '#68746a')])
            style.configure('TCombobox',fieldbackground='#263a2e',foreground=TEXT)
            style.configure('TSpinbox',fieldbackground='#263a2e',foreground=TEXT)
            style.configure('TNotebook.Tab', padding=(3, 8), font=('Segoe UI',9))
            style.map('TNotebook.Tab', background=[('selected', '#516044')])
            header = tk.Frame(root, bg=BG)
            header.pack(fill='x', padx=18, pady=(12, 6))
            tk.Label(header, text='A F T E R D A Y S', bg=BG, fg=GOLD, font=('Segoe UI', 18, 'bold')).pack(side='left')
            tk.Label(header, text=tr('afterdays.0132'), bg=BG, fg=MUTED, font=('Segoe UI', 10)).pack(side='left')
            from terminal034 import StatusBar,system_menu
            system_menu(header,self)
            self.status = StatusBar(root,self)
            self.status.pack(fill='x', padx=18)
            body = tk.Frame(root, bg=BG)
            body.pack(fill='both', expand=True, padx=18, pady=10)
            left = tk.Frame(body, bg=BG)
            body.columnconfigure(0, weight=2, uniform='halves')
            body.columnconfigure(1, weight=1, uniform='halves')
            body.rowconfigure(0,weight=1)
            left.grid(row=0,column=0,sticky='nsew',padx=(0,6))
            left.pack_propagate(False)
            self.map_title = tk.Label(left, bg=BG, fg=GOLD, anchor='w', font=('Segoe UI', 12, 'bold'))
            self.map_title.pack(fill='x', pady=(0, 6))
            self.canvas = tk.Canvas(left, bg='#17201c', highlightthickness=1, highlightbackground='#475244')
            self.canvas.pack(fill='both', expand=True)
            self.canvas.bind('<Configure>', lambda e: self.draw())
            self.canvas.bind('<Button-1>', self.map_click)
            self.canvas.bind('<Double-Button-1>', lambda e:self.map_click(e,start=True))
            self.canvas.bind('<Motion>', self.map_hover)
            self.canvas.bind('<Leave>',self.clear_battle_hover)
            import inspection_ui
            self.canvas.bind('<Button-3>',lambda e:__import__('interface032').map_context(self,e))
            self.hint = tk.Label(left, bg=BG, fg=MUTED, anchor='w', justify='left', wraplength=680, height=4)
            self.hint.pack(fill='x', pady=5)
            controls = tk.Frame(left, bg=BG)
            controls.pack(fill='x')
            from action_ui048 import ActionButton,styles
            styles(root)
            self.end_button = ActionButton(controls,'end','◷',tr('afterdays.0137'), command=lambda: self.act(self.game.end_turn))
            self.end_button.pack(side='left', padx=2)
            ActionButton(controls,'switch','⇄',tr('afterdays.0138'), command=lambda: self.act(self.game.switch)).pack(side='left', padx=2)
            ActionButton(controls,'med','✚',tr('afterdays.0139'), command=lambda: self.act(lambda: self.game.use('med'))).pack(side='left', padx=2)
            self.flee_button = ActionButton(controls,'flee','↪',tr('afterdays.0140'), command=lambda: self.act(self.game.flee))
            self.flee_button.pack(side='left', padx=2)
            from route_ui import RouteController
            self.route=RouteController(self)
            self.route_button=ActionButton(controls,'move','▶',tr('journey.resume'),command=self.route.toggle,state='disabled')
            self.route_button.pack(side='left',padx=2)
            ActionButton(controls,'search','⌕',tr('afterdays.0141'),command=lambda:self.act(self.game.search)).pack(side='left',padx=2)
            side = tk.Frame(body, bg=PANEL, width=380)
            side.grid(row=0,column=1,sticky='nsew',padx=(6,0))
            side.pack_propagate(False)
            buttons = controls.winfo_children()

            for button in buttons:
                button.pack_forget()

            for n, button in enumerate(buttons):
                button.grid(
                    row=0, column=n,
                    sticky='ew', padx=2, pady=2
                )
            controls.columnconfigure(tuple(range(6)),weight=1)
            self.root.after_idle(lambda:self.hint.config(wraplength=max(300,left.winfo_width()-10)))
            self.tabs = ttk.Notebook(side)
            self.tabs.pack(fill='both', expand=True)
            self.world_tab, self.inv_tab, self.loot_tab, self.quest_tab = [ttk.Frame(self.tabs) for _ in range(4)]
            for tab, title in [(self.world_tab, tr('afterdays.0142')), (self.inv_tab, tr('afterdays.0143')), (self.loot_tab, tr('afterdays.0144')), (self.quest_tab, tr('afterdays.0145'))]:
                key={self.world_tab:'site',self.inv_tab:'backpack',self.loot_tab:'loot',self.quest_tab:'journal'}[tab]
                art=sprites.photo(root,key,16)
                self.tabs.add(tab,text=title,**({'image':art,'compound':'left'} if art else {}))
            import frontier_ui
            self.player_tab = ttk.Frame(self.tabs)
            self.tabs.add(self.player_tab,text=tr('afterdays.0146'))
            self.player_panel=frontier_ui.PlayerPanel(self.player_tab,self)
            self.player_panel.pack(fill='both',expand=True)
            self.perks_tab=ttk.Frame(self.tabs)
            self.tabs.add(self.perks_tab,text=tr('update024.perks_tab'))
            self.perks_panel=refinement_ui.PerksPanel(self.perks_tab,self)
            self.perks_panel.pack(fill='both',expand=True)
            self.cartographer=lambda:frontier_ui.cartographer(self)
            self.guide=lambda:frontier_ui.guide(self)
            self.metro=lambda:frontier_ui.metro(self)
            world_page = self.world_tab
            world_canvas = tk.Canvas(world_page, bg=PANEL, highlightthickness=0)
            world_scroll = ttk.Scrollbar(world_page, command=world_canvas.yview)
            world_scroll.pack(side='right', fill='y')
            world_canvas.pack(side='left', fill='both', expand=True)
            world_canvas.configure(yscrollcommand=world_scroll.set)
            self.world_tab = ttk.Frame(world_canvas)
            world_window = world_canvas.create_window(0, 0, window=self.world_tab, anchor='nw')
            self.world_tab.bind('<Configure>', lambda e: world_canvas.configure(scrollregion=world_canvas.bbox('all')))
            world_canvas.bind('<Configure>', lambda e: world_canvas.itemconfigure(world_window, width=e.width))
            self.location = tk.Label(self.world_tab, bg=PANEL, fg=TEXT, font=('Segoe UI', 12, 'bold'), wraplength=335, justify='left')
            self.location.pack(fill='x', padx=12, pady=15)
            self.city_info = tk.Label(self.world_tab, bg=PANEL, fg=MUTED, justify='left', wraplength=340)
            self.city_info.pack(fill='x', padx=12, pady=8)
            self.services = adventure_ui.Services(self.world_tab,self)
            self.services.pack(fill='x',padx=6,pady=4)
            tk.Label(self.world_tab, text=tr('afterdays.0147'), bg=PANEL, fg=GOLD).pack(anchor='w', padx=12, pady=(20, 8))
            self.cities_label = tk.Label(self.world_tab, bg=PANEL, fg=MUTED, justify='left')
            self.cities_label.pack(anchor='w', padx=12)
            self.inv_panel = visuals.EquipmentPanel(self.inv_tab, self)
            self.inv_panel.pack(fill='both', expand=True)
            self.quest_panel = refinement_ui.QuestCards(self.quest_tab, self)
            self.quest_panel.pack(fill='both', expand=True)
            self.loot_list = visuals.ItemGrid(self.loot_tab,lambda i:self.loot_detail.config(text=self.description(next((x for x in self.game.loot if x['id']==i),None))),height=240)
            self.loot_list.pack(fill='both',expand=True,padx=6,pady=6)
            self.loot_detail=refinement_ui.Detail(self.loot_tab,height=8)
            self.loot_detail.pack(fill='x',padx=8)
            ttk.Button(self.loot_tab, text=tr('afterdays.0148'), command=self.collect_selected).pack(fill='x', padx=10, pady=5)
            ttk.Button(self.loot_tab, text=tr('afterdays.0149'), command=self.collect_all).pack(fill='x', padx=10, pady=5)
            tk.Label(self.loot_tab, text=tr('afterdays.0150'), bg=PANEL, fg=MUTED, justify='left').pack(padx=10, pady=12)
            logframe = tk.Frame(root, bg=PANEL)
            logframe.pack(fill='x', padx=18, pady=(0, 12))
            self.logbox = tk.Text(logframe, height=3, bg=PANEL, fg=MUTED, relief='flat', font=('Segoe UI', 10), padx=10, pady=6, state='disabled')
            self.logbox.pack(fill='x')
            root.bind_class('AfterdaysKeys', '<KeyPress>', self.key)
            def bind_keys(widget):
                widget.bindtags(('AfterdaysKeys',) + widget.bindtags())
                for child in widget.winfo_children():
                    bind_keys(child)
            bind_keys(root)
            root.protocol('WM_DELETE_WINDOW', self.close)
            self.fx=adventure_ui.Effects(self)
            self.refresh()

        def listbox(self, parent, height=14):
            """Створює список із прокручуванням для вибору елементів."""
            frame = tk.Frame(parent, bg=PANEL)
            frame.pack(fill='both', expand=True, padx=8, pady=8)
            scroll = ttk.Scrollbar(frame)
            scroll.pack(side='right', fill='y')
            box = tk.Listbox(frame, bg='#18211d', fg=TEXT, selectbackground='#4e5b42', selectforeground='white',
                             font=('Segoe UI', 10), relief='flat', highlightthickness=0, height=height,
                             exportselection=False, yscrollcommand=scroll.set)
            box.pack(side='left', fill='both', expand=True)
            scroll.config(command=box.yview)
            return box

        def act(self, fn):
            """Виконує ігрову дію та оновлює інтерфейс."""
            self.route.pause()
            if self.fx.blocked:
                return
            before_battle = self.game.battle is not None
            fn()
            self.refresh()
            map_request=getattr(self.game,'_metro_map_request',None)
            if map_request:
                self.game._metro_map_request=None
                __import__('restoration_ui').puzzle(self,map_request)
            request=getattr(self.game,'_radio_request',None)
            if request:
                self.game._radio_request=None
                import radio_ui
                radio_ui.show(self,request)
            generator=getattr(self.game,'_generator_request',None)
            if generator:
                self.game._generator_request=None
                import generator_ui
                generator_ui.show(self,generator)
            junk=getattr(self.game,'_junkyard_request',None)
            if getattr(self.game,'_grave_request',False):
                self.game._grave_request=False
                import recovery_ui
                recovery_ui.show(self)
            if junk:
                self.game._junkyard_request=None
                import junkyard_ui
                junkyard_ui.show(self,junk)
            lock=getattr(self.game,'_lock_request',None)
            if lock:
                self.game._lock_request=None
                import lock_ui
                lock_ui.show(self,lock)
            if before_battle and not self.game.battle and self.game.loot:
                self.tabs.select(self.loot_tab)

        def refresh(self):
            """Оновлює віджети відповідно до поточного стану гри."""
            if self.route.game is not self.game:self.route.clear()
            self.route.update_button()
            self.fx.ingest()
            g = self.game
            g.process_settlers()
            g.check_thanks()
            if not self.dialog and not g.battle and not getattr(self,'_notice_open',False):
                notice_key=next((key for key in ('_border_notice','_mayor_notice','_reputation_notice','_settler_notice') if getattr(g,key,None)),None)
                if notice_key:
                    notice=getattr(g,notice_key);setattr(g,notice_key,None);self._notice_open=True
                    def show_notice(text=notice):
                        try:messagebox.showinfo('Afterdays',text,parent=root)
                        finally:self._notice_open=False;self.refresh()
                    root.after_idle(show_notice)
            weapon = g.weapon
            ws = __import__('module_rules').weapon_stats(g,weapon) if weapon else {}
            self.status.refresh(g)
            combat = g.battle is not None
            self.end_button.config(state='normal' if combat else 'disabled')
            dungeon=combat and g.battle.get('dungeon')
            self.flee_button.config(text=tr('update032.leave') if dungeon else tr('afterdays.0140'),state='normal' if combat and (not dungeon or g.battle['pos']==g.battle['exit']) else 'disabled')
            self.tabs.tab(self.loot_tab, text=tr('afterdays.0152', v0=len(g.loot)))
            self.services.refresh()
            self.perks_panel.refresh()
            self.location.config(text=g.city_name(g.city) if g.city is not None else TERRAINS[g.world[g.y][g.x]][1],fg=g.city_color(g.city,TEXT))
            self.city_info.config(text=(tr('afterdays.0153', v0=g.current_site['npc']) if g.current_site else tr('afterdays.0154') if g.city is not None else
                                      tr('afterdays.0155')) +
                                      tr('afterdays.0157', v0=g.x, v1=g.y, v2=g.region_level, v3=weapon['name'] if weapon else tr('afterdays.0156'), v4=ws.get('damage', 0), v5=ws.get('range', 0), v6=weapon['ap'] if weapon else '—'))
            if g.city is not None:
                self.city_info.config(text=self.city_info.cget('text')+'\n'+tr('reputation.status', value=g.reputation(), buy=round((buy_factor(g.reputation())-1)*100), sell=round((sell_factor(g.reputation())-1)*100)))
            if weapon:
                ammo_type=weapon.get('ammo_type','pistol')
                self.city_info.config(text=self.city_info.cget('text')+tr('afterdays.0158', v0=progression.AMMO[ammo_type][0], v1=g.count('ammo', ammo_type), v2=weapon.get('durability', 100)))
            self.city_info.config(text=self.city_info.cget('text')+'\n'+tr('survival040.sheet',rad=g.radiation_injury,hunger=g.hunger))
            near = sorted(((n,pos) for n,pos in enumerate(g.cities) if n in g.known_cities), key=lambda entry: __import__('world_hex').distance(entry[1], (g.x, g.y)))[:3]
            self.cities_label.config(text='\n'.join(f'◆ {self.game.city_name(n)} ({p[0]}, {p[1]})' for n,p in near))
            self.player_panel.refresh()
            self.inv_panel.refresh()
            self.quest_panel.refresh()
            self.tabs.tab(self.quest_tab, text=tr('afterdays.0160'))
            self.loot_list.set_items(g.loot)
            self.logbox.config(state='normal')
            self.logbox.delete('1.0', 'end')
            colors=([None]*len(g.messages)+getattr(g,'message_colors',[]))[-len(g.messages):] if g.messages else []
            for message,color in zip(g.messages,colors):
                tag=color or 'normal'
                self.logbox.tag_configure(tag,foreground=color or TEXT)
                self.logbox.insert('end',message+'\n',tag)
            self.logbox.see('end')
            self.logbox.config(state='disabled')
            self.draw()
            self.root.after_idle(self.offer_notices)

        def offer_notices(self):
            """Показує нові повідомлення про доступні події й завдання."""
            if self.dialog or self.fx.blocked:
                return
            from campaign_intro import pending
            story=pending(self.game)
            if story:
                self.route.pause()
                from story_ui import show
                show(self.quest_panel,story)
                return
            if self.game.road_event:
                self.road_dialog()
            elif self.game.pending_perks and self.perk_prompted != self.game.level//2:
                self.perk_prompted = self.game.level//2
                self.perks()

        def road_dialog(self):
            """Відкриває варіанти дії для поточної дорожньої події."""
            if not self.dialog and self.game.road_event:
                adventure_ui.road_window(self)

        def storage(self):
            """Відкриває інтерфейс власного сховища."""
            if self.game.can_access_stash:
                win=self.popup(tr('afterdays.0161'),'940x680')
                adventure_ui.Storage(win,self).pack(fill='both',expand=True)

        def perks(self):
            """Відкриває вибір та перегляд перків."""
            if not self.dialog:
                self.tabs.select(self.perks_tab)

        def technician(self):
            """Відкриває вкладки послуг техніка."""
            if not self.game.battle and self.game.city in self.game.technicians:
                win=self.popup(tr('afterdays.0162'),'790x690')
                refinement_ui.Technician(win,self).pack(fill='both',expand=True)

        def description(self,item):
            """Формує читабельний опис предмета або стану."""
            return refinement_ui.description(self.game,item)

        def selected_id(self):
            """Повертає ідентифікатор поточного вибору."""
            return self.inv_panel.selection

        def describe_selection(self):
            """Оновлює інформацію про поточний вибір."""
            self.inv_panel.select(self.selected_id())

        def equip_selected(self):
            """Одягає вибраний предмет у вказаний слот."""
            if self.game.battle:
                self.act(lambda: self.game.log(tr('afterdays.0163')))
                return
            item_id = self.selected_id()
            item = self.game.find(item_id)
            if not item:
                return
            slot = next((s for s, i in self.game.equipped.items() if i and i['id'] == item_id), None)
            if slot:
                self.act(lambda: self.game.unequip(slot))
            elif item['kind'] == 'weapon':
                answer = messagebox.askyesnocancel(tr('afterdays.0164'), tr('afterdays.0165'), parent=self.root)
                if answer is not None:
                    self.act(lambda: self.game.equip(item_id, 'weapon1' if answer else 'weapon2'))
            elif item['kind'] in ('armor', 'helmet'):
                self.act(lambda: self.game.equip(item_id, item['kind']))

        def use_selected(self):
            """Застосовує дію використання до вибраного предмета."""
            item = self.game.find(self.selected_id())
            if item and item['kind']=='repairkit':
                import maintenance_ui
                maintenance_ui.show(self,item['id']);return
            if item and item['kind']=='sealed':
                if self.fx.blocked:return
                found=self.game.open_chest(item['id'])
                if found:
                    self.refresh()
                    import inspection_ui
                    inspection_ui.result(self,found,animate=True)
                else:self.game.log(tr('afterdays.0166'));self.refresh()
                return
            if item and item['kind'] in ('med', 'food', 'rad'):
                self.act(lambda: self.game.use(item['id']))

        def drop_selected(self):
            """Викидає вибраний предмет після потрібних перевірок."""
            item = self.game.find(self.selected_id())
            if item and item['kind'] == 'quest':
                self.act(lambda: self.game.log(tr('afterdays.0167')))
            elif self.game.battle:
                self.act(lambda: self.game.log(tr('afterdays.0168')))
            elif item and item in self.game.bag and messagebox.askyesno(tr('afterdays.0169'), tr('afterdays.0170', v0=item['name']), parent=self.root):
                self.game.drop_item(item['id'])
                self.refresh()

        def dismantle_selected(self):
            """Запускає розбір вибраного спорядження."""
            item=self.game.find(self.selected_id())
            if self.game.battle or not item or item['kind'] not in ('weapon','armor','helmet'):
                return
            if item not in self.game.bag:
                self.act(lambda:self.game.log(tr('afterdays.0171')))
                return
            count=self.game.salvage_yield(item)
            if messagebox.askyesno(tr('afterdays.0172'),tr('afterdays.0175', v0=item['name'], v1=count, v2=tr('afterdays.0173') if item['kind'] == 'weapon' else tr('afterdays.0174'))+'\n'+tr('update033.salvage_kit'),parent=self.root):
                self.act(lambda:self.game.dismantle(item['id']))

        def popup(self, title, geometry):
            """Створює й центрує додаткове вікно інтерфейсу."""
            self.route.pause()
            self.root.after_idle(lambda:sprites.decorate(self.root))
            win = tk.Toplevel(self.root)
            win.title(title)
            width,height=map(int,geometry.split('x'))
            sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
            width,height=min(width,sw-40),min(height,sh-80)
            win.geometry(f'{width}x{height}+{max(0,(sw-width)//2)}+{max(0,(sh-height)//2)}')
            win.configure(bg=PANEL)
            win.transient(self.root)
            win.grab_set()
            self.dialog = win
            def close():
                self.dialog = None
                win.destroy()
                self.refresh()
            win.close_dialog = close
            win.protocol('WM_DELETE_WINDOW', close)
            win.bind('<Escape>', lambda e: close())
            return win

        def modify(self):
            """Відкриває встановлення та зняття модулів."""
            item = self.game.find(self.selected_id())
            if not item or 'slots' not in item:
                return
            if self.game.battle:
                self.act(lambda: self.game.log(tr('afterdays.0176')))
                return
            win = self.popup(tr('afterdays.0177') + item['name'], '770x730')
            panel = visuals.ModificationPanel(win, self, item['id'])
            panel.pack(fill='both', expand=True)

        def mayor(self):
            """Відкриває список пропозицій місцевого квестодавця."""
            if (self.game.city not in self.game.mayors and not self.game.regular_city) or self.game.battle:return
            win=self.popup(tr('afterdays.0178')+self.game.city_name(self.game.city),'750x670')
            refinement_ui.QuestCards(win,self,mayor=True).pack(fill='both',expand=True)

        def atlas(self):
            """Відкриває оглядову карту світу."""
            import frontier_ui
            win = self.popup(tr('afterdays.0179'), '1000x730')
            tk.Label(win, text=tr('afterdays.0180'), bg=PANEL, fg=GOLD,
                     font=('Segoe UI', 12, 'bold')).pack(pady=10)
            c = tk.Canvas(win, bg=BG, highlightthickness=0)
            c.pack(fill='both', expand=True, padx=12)
            detail = tk.Label(win, text=tr('afterdays.0181'),
                              bg=PANEL, fg=TEXT, wraplength=950, height=3)
            detail.pack(fill='x', padx=12, pady=8)
            layout = {}
            def paint(event=None):
                from world_map import draw
                layout['view']=draw(self,c,overview=True)
            def click(event):
                if 'view' not in layout:return
                pos=list(layout['view'].cell(event.x,event.y))
                if not (0<=pos[0]<len(self.game.world[0]) and 0<=pos[1]<len(self.game.world)):return
                if pos in self.game.cities and self.map_city_known(self.game.cities.index(pos)):
                    n=self.game.cities.index(pos)
                    detail.config(text=f'{self.game.city_name(n)} ({pos[0]}, {pos[1]}) · '+', '.join(MERCHANTS[m] for m in self.game.city_merchants[n])+(tr('afterdays.0182') if n in self.game.mayors else tr('afterdays.0183'))+(tr('afterdays.0184') if n in self.game.technicians else '')+tr('afterdays.0185', v0=self.game.region_at(pos[0], pos[1]))+tr('update024.reputation',value=self.game.reputation(n)),fg=self.game.city_color(n,TEXT))
                else:
                    q=next((q for q in self.game.quests if q.get('pos') == pos and q['status'] == 'active'), None)
                    detail.config(text=self.game.quest_text(q).replace('\n', ' · ') if q else tr('afterdays.0186', v0=pos[0], v1=pos[1], v2=self.game.region_at(pos[0], pos[1])))
            c.bind('<Configure>',paint)
            c.bind('<Button-1>',click)

            def toggle_atlas_visibility(event):
                self.toggle_test_map()
                paint()
                return 'break'

            if TEST_MODE:
                win.bind('<KeyPress-m>',toggle_atlas_visibility)
                win.bind('<KeyPress-M>',toggle_atlas_visibility)

        def shop(self, merchant):
            """Відкриває інтерфейс вибраного торговця."""
            if not self.game.available_merchant(merchant):
                return
            win=self.popup(self.game.merchant_title(merchant), '960x730')
            advanced_ui.TradingPanel(win,self,merchant).pack(fill='both',expand=True)

        def collect_selected(self):
            """Забирає вибраний предмет здобичі."""
            sel=self.loot_list.selection
            if sel:self.act(lambda:self.game.collect(sel))

        def collect_all(self):
            """Намагається забрати всі доступні предмети здобичі."""
            for item in list(self.game.loot):
                self.game.collect(item['id'])
            self.refresh()

        def draw(self):
            """Перемальовує карту або арену й видимі позначення."""
            c, g = self.canvas, self.game
            if self.fx.snapshot is not None and self.fx.blocked:
                adventure_ui.paint_snapshot(self)
                self.fx.render()
                return
            if g.battle:
                advanced_ui.draw_battle(self)
                self.fx.render()
                return
            from world_map import draw
            draw(self)
            self.fx.render()

        def cell(self, event):
            """Перетворює координати курсора на клітинку карти."""
            if self.game.battle:
                return advanced_ui.iso_cell(self,event)
            return self.world_view.cell(event.x,event.y)

        def clear_battle_hover(self,event=None):
            """Прибирає ціль наведення після виходу курсора з арени."""
            self.battle_hover=None
            if self.game.battle:self.draw()

        def map_hover(self, event):
            """Оновлює підсвічування й підказку клітинки під курсором."""
            if self.game.battle:
                pos = self.cell(event)
                if getattr(self,'battle_hover',None)!=pos:
                    self.battle_hover=pos;self.draw()
                e = next((e for e in self.game.battle['enemies'] if tuple(e['pos']) == pos), None)
                if e:
                    valid, reason, chance = self.game.shot_info(e)
                    self.hint.config(text=tr('afterdays.0191', v0=e['name'], v1=e.get('level', 1), v2=e['hp'], v3=e['max_hp'], v4=e['damage'], v5=e.get('attack', 0), v6=e.get('defense', 0), v7=e['range']) +
                                     (tr('afterdays.0192', v0=chance, v1=self.game.weapon['ap']) if valid else reason+' ') + adventure.resistance_text(e)+tr('afterdays.0193', v0=self.game.enemy_xp(e)))

            else:
                pos=self.cell(event)
                if 0<=pos[0]<len(self.game.world[0]) and 0<=pos[1]<32:
                    edges=[(pos,q) for q in __import__('world_hex').neighbors(*pos,len(self.game.world[0]),len(self.game.world)) if self.game.border_edge(pos,q)]
                    if edges and self.map_revealed(*pos):
                        gate=any(self.game.checkpoint(a,b) for a,b in edges)
                        self.hint.config(text=tr('border.open_hint') if gate and self.game.border_open else tr('border.locked') if gate else tr('border.fence'))

        def world_step(self, dx, dy):
            """Передає команду переміщення гравця на карті."""
            g = self.game
            if not g.can_step(dx,dy):
                g.step(dx,dy)
                return False
            if g.loot:
                if not messagebox.askyesno(tr('afterdays.0194'), tr('afterdays.0195'), parent=self.root):
                    return False
                g.loot.clear()
            return g.step(dx, dy)

        def map_click(self, event, *, start=False):
            """Обробляє натискання на клітинку карти або бойову ціль."""
            if self.dialog:
                return
            self.canvas.focus_set()
            x, y = self.cell(event)
            b = self.game.battle
            if b:
                if not (0 <= x < b['w'] and 0 <= y < b['h']):
                    return
                enemy = next((e for e in b['enemies'] if e['pos'] == [x, y]), None)
                self.act(lambda: self.game.shoot(enemy['id']) if enemy else self.game.battle_move((x, y)))
            elif 0 <= x < len(self.game.world[0]) and 0 <= y < len(self.game.world):
                self.route.set_target((x,y),start=start)

        def key(self, event):
            """Обробляє гарячі клавіші гри."""
            if self.dialog:
                return
            key = event.keysym.lower()
            if not self.game.battle:
                from world_hex import key_delta
                delta=key_delta(key,self.game.y)
                if delta is not None:
                    self.route.clear();self.act(lambda:self.world_step(*delta));return 'break'
            directions = {'w': (0,-1), 'up': (0,-1), 's': (0,1), 'down': (0,1),
                          'a': (-1,0), 'left': (-1,0), 'd': (1,0), 'right': (1,0)}
            if key in directions:
                if isinstance(event.widget, tk.Listbox) and key in ('up', 'down'):
                    return
                dx, dy = directions[key]
                if not self.game.battle:self.route.clear()
                self.act(lambda: self.game.step(dx, dy) if self.game.battle else self.world_step(dx, dy))
            elif key == 'space':
                if self.game.battle:self.act(self.game.end_turn)
                else:self.route.toggle()
            elif key == 'tab':
                self.act(self.game.switch)
            elif key == 'h':
                self.act(lambda: self.game.use('med'))
            elif key == 'e':
                self.act(self.game.search)
            elif key == 'i':
                self.tabs.select(self.inv_tab)
            elif key == 'j':
                self.tabs.select(self.quest_tab)
            elif key == 'm':
                if TEST_MODE and not (event.state & 0x0001):
                    self.toggle_test_map()
                else:
                    self.atlas()
            elif key == 'f5':
                self.save()
            elif key == 'f9':
                self.load()
            else:
                return
            return 'break'

        def save(self):
            """Записує стан гри у файл збереження."""
            self.route.pause()
            try:
                self.game.save(save_path)
                self.game.log(tr('afterdays.0196'))
            except OSError as exc:
                messagebox.showerror(tr('afterdays.0197'), str(exc), parent=self.root)
            self.refresh()

        def load(self):
            """Завантажує збереження та застосовує міграції цієї версії."""
            self.route.pause()
            if not save_path.exists():
                messagebox.showinfo(tr('afterdays.0198'), tr('afterdays.0199'), parent=self.root)
                return
            if not messagebox.askyesno(tr('afterdays.0200'), tr('afterdays.0201'), parent=self.root):
                return
            try:
                loaded = Game.load(save_path)
                self.game = loaded
                self.perk_prompted = -1
                self.game.log(tr('afterdays.0202'))
                self.refresh()
            except (OSError, ValueError, KeyError, TypeError) as exc:
                messagebox.showerror(tr('afterdays.0203'), str(exc), parent=self.root)

        def new(self):
            """Починає нову гру та скидає стан інтерфейсу."""
            self.route.pause()
            if messagebox.askyesno(tr('afterdays.0204'), tr('afterdays.0205'), parent=self.root):
                self.game = Game()
                self.game.prepare_campaign()
                self.perk_prompted = -1
                self.refresh()

        def close(self):
            """Завершує роботу вікна і пов’язаних таймерів."""
            self.route.pause()
            answer = messagebox.askyesnocancel('Afterdays', tr('afterdays.0206'), parent=self.root)
            if answer is None:
                return
            if answer:
                try:
                    self.game.save(save_path)
                except OSError as exc:
                    messagebox.showerror(tr('afterdays.0207'), str(exc), parent=self.root)
                    return
            self.root.destroy()

        def help(self):
            """Показує довідку з керування."""
            messagebox.showinfo(tr('afterdays.0208'),
                tr('afterdays.0209'), parent=self.root)

    root = tk.Tk()
    app = App(root)
    if test_hook:
        root.after(100, lambda: test_hook(root, app))
    root.mainloop()


if __name__ == '__main__':
    try:
        launch()
    except ImportError as exc:
        if exc.name in ('tkinter', '_tkinter'):
            print(tr('afterdays.0210'))
        elif exc.name == 'PIL' or (exc.name or '').startswith('PIL.'):
            print('Потрібен Pillow для зображень мапи. Команда для PowerShell:')
            print(f'& "{sys.executable}" -m pip install Pillow')
        else:
            raise
        print(f'Python: {sys.executable}\nПричина: {exc}')
        sys.exit(1)
