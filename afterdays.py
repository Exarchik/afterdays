"""Afterdays — standalone turn-based RPG. Python 3.10+, Tkinter, no pip packages."""
from __future__ import annotations
import json
import math
import os
import random
import sys
import uuid
from collections import deque
from pathlib import Path
sys.modules.setdefault('afterdays', sys.modules[__name__])

RARITIES = [('Звичайний', '#a8acaa'), ('Незвичний', '#53a9ff'),
            ('Рідкісний', '#f4cd55'), ('Унікальний', '#c58bfa'), ('Релікт', '#ff6570')]
STAT_NAMES = {'damage': 'Шкода', 'range': 'Дальність', 'defense': 'Захист', 'accuracy': 'Точність'}
SLOTS = {'weapon1': 'Зброя I', 'weapon2': 'Зброя II', 'armor': 'Броня', 'helmet': 'Шолом'}
GEAR = {
    'Пістолет «Попіл»': ('weapon', 11, 5, 0, 84, 1.6, 2),
    'Гвинтівка «Сторож»': ('weapon', 18, 9, 0, 88, 4.5, 3),
    'Автомат «Іржа»': ('weapon', 14, 6, 0, 82, 3.5, 2),
    'Дробовик «Грім»': ('weapon', 26, 3, 0, 94, 4.0, 3),
    'Лазер «Промінь»': ('weapon', 20, 8, 0, 95, 3.0, 3),
    'Куртка з пластинами': ('armor', 0, 0, 3, 0, 5.0, 0),
    'Бронекорпус «Бастіон»': ('armor', 0, 0, 6, 0, 8.0, 0),
    'Шолом «Шукач»': ('helmet', 0, 0, 2, 0, 1.5, 0),
}
MODULES = [
    ('Підсилювач', 'weapon', 'damage', 3), ('Оптика', 'weapon', 'range', 1),
    ('Стабілізатор', 'weapon', 'accuracy', 4), ('Бронепластина', 'protection', 'defense', 1),
]
CITY_NAMES = ['Сховище 17', 'Сухий Колодязь', 'Іржавий Порт', 'Нова Зоря', 'Рубіж']
MERCHANTS = ['Коваль', 'Торговець', 'Барига']
TERRAINS = {'waste': ('#333b34', 'Пустка'), 'forest': ('#253c34', 'Мертвий ліс'),
            'ruin': ('#484139', 'Руїни'), 'road': ('#625747', 'Стара дорога'),
            'city': ('#827346', 'Місто')}


def uid():
    return uuid.uuid4().hex


def equipment(name=None, tier=0, rng=None):
    rng = rng or random
    name = name or rng.choice(list(GEAR))
    kind, damage, reach, defense, accuracy, weight, cost = GEAR[name]
    return dict(id=uid(), name=name, kind=kind, rarity=tier, weight=weight,
                value=int((70 + weight * 15) * (1 + tier * .85)), slots=min(5, tier + 1),
                stats=dict(damage=damage + (tier * 2 if kind == 'weapon' else 0),
                           range=reach, defense=defense + (tier if kind != 'weapon' else 0),
                           accuracy=accuracy), modules=[], ap=cost)


def module(tier=0, rng=None, index=None):
    rng = rng or random
    name, target, stat, base = MODULES[rng.randrange(len(MODULES)) if index is None else index]
    return dict(id=uid(), name=name, kind='module', rarity=tier, weight=.3,
                value=30 * (tier + 1) ** 2, target=target, stats={stat: base * (tier + 1)})


def supply(kind):
    return dict(id=uid(), name='Аптечка' if kind == 'med' else 'Консерви', kind=kind,
                rarity=0, weight=.4 if kind == 'med' else .6, value=42 if kind == 'med' else 18)


def stats(item):
    result = dict(item.get('stats', {}))
    for mod in item.get('modules', []):
        for key, value in mod['stats'].items():
            result[key] = result.get(key, 0) + value
    return result


def item_weight(item):
    return item['weight'] + sum(item_weight(m) for m in item.get('modules', []))


def item_value(item):
    return item['value'] + sum(item_value(m) for m in item.get('modules', []))


def compatible(item, mod):
    return mod['kind'] == 'module' and (mod['target'] == item['kind'] or
           mod['target'] == 'protection' and item['kind'] in ('armor', 'helmet'))


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
        self.rng = random.Random(seed)
        self.messages = []
        self.turn = 0
        self.x, self.y = 5, 5
        self.hp = 100
        self.money = 180
        self.xp = 0
        self.active = 'weapon1'
        self.equipped = {'weapon1': equipment('Пістолет «Попіл»', 1),
                         'weapon2': equipment('Гвинтівка «Сторож»'),
                         'armor': equipment('Куртка з пластинами'),
                         'helmet': equipment('Шолом «Шукач»')}
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
        self.log('Ви прокинулись у Сховищі 17. Спорядження готове. Пустка чекає.')

    @property
    def level(self):
        return 1 + self.xp // 100

    @property
    def max_hp(self):
        return 100 + (self.level - 1) * 8

    @property
    def weight(self):
        return round(sum(item_weight(i) for i in self.bag) +
                     sum(item_weight(i) for i in self.equipped.values() if i), 2)

    @property
    def capacity(self):
        return 35.0

    @property
    def defense(self):
        return sum(stats(i).get('defense', 0) for i in self.equipped.values() if i)

    @property
    def weapon(self):
        return self.equipped[self.active]

    @property
    def city(self):
        return self.cities.index([self.x, self.y]) if [self.x, self.y] in self.cities else None

    def log(self, msg):
        self.messages.append(msg)
        self.messages = self.messages[-80:]

    def find(self, item_id):
        return next((i for i in self.bag + [v for v in self.equipped.values() if v]
                     if i['id'] == item_id), None)

    def accept(self, item):
        if self.weight + item_weight(item) > self.capacity + .0001:
            self.log('Замало місця за вагою. Звільніть рюкзак.')
            return False
        self.bag.append(item)
        return True

    def equip(self, item_id, slot):
        if self.battle:
            self.log('Екіпіровку можна змінювати лише поза боєм.')
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
        self.log(f"Екіпіровано: {item['name']}.")
        return True

    def unequip(self, slot):
        if self.battle or not self.equipped[slot]:
            return False
        self.bag.append(self.equipped[slot])
        self.equipped[slot] = None
        return True

    def install(self, item_id, mod_id):
        if self.battle:
            return False
        item, mod = self.find(item_id), self.find(mod_id)
        if not item or not mod or mod not in self.bag or not compatible(item, mod):
            return False
        if len(item['modules']) >= item['slots']:
            self.log('Усі слоти зайняті. Спочатку зніміть один модуль.')
            return False
        self.bag.remove(mod)
        item['modules'].append(mod)
        self.log(f"{mod['name']} → {item['name']}.")
        return True

    def uninstall(self, item_id, mod_id):
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
        item = next((i for i in self.bag if i['kind'] == kind), None)
        if not item:
            self.log('Немає аптечки.' if kind == 'med' else 'Немає консервів.')
            return False
        if self.hp >= self.max_hp:
            self.log('Здоров’я вже повне.')
            return False
        if self.battle and self.battle['ap'] < 2:
            self.log('Потрібно 2 ОД.')
            return False
        self.bag.remove(item)
        healing = min(self.max_hp - self.hp, 40 if kind == 'med' else 14)
        self.hp += healing
        if self.battle:
            self.battle['ap'] -= 2
        self.log(f"{item['name']}: +{healing} здоров’я.")
        return True

    def step(self, dx, dy):
        if self.battle:
            return self.battle_move((self.battle['pos'][0]+dx, self.battle['pos'][1]+dy))
        if abs(dx) + abs(dy) != 1 or not (0 <= self.x+dx < 48 and 0 <= self.y+dy < 32):
            return False
        self.x += dx
        self.y += dy
        self.turn += 1
        if self.turn % 8 == 0:
            food = next((i for i in self.bag if i['kind'] == 'food'), None)
            if food:
                self.bag.remove(food)
                self.hp = min(self.max_hp, self.hp + 10)
                self.log('Дорожній привал: витрачено консерви, +10 здоров’я.')
            else:
                self.hp = max(1, self.hp - 5)
                self.log('Немає харчів: виснаження забрало 5 здоров’я.')
        terrain = self.world[self.y][self.x]
        if self.city is not None:
            self.log(f'Ви прибули: {CITY_NAMES[self.city]}. Тут безпечно.')
        elif self.rng.random() < {'road': .06, 'waste': .12, 'forest': .20, 'ruin': .24}[terrain]:
            self.start_battle()
        return True

    def search(self):
        if self.battle or self.city is not None:
            return False
        key = [self.x, self.y]
        if key in self.searched:
            self.log('Цю ділянку вже обшукано.')
            return False
        self.searched.append(key)
        self.turn += 1
        self.loot.extend([self.roll_item(), supply(self.rng.choice(['food', 'med']))])
        self.log('Знайдено припаси. Відкрийте «Здобич».')
        if self.rng.random() < .35:
            self.start_battle()
        return True

    def roll_item(self):
        tier = self.rng.choices(range(5), [50, 28, 14, 6, 2])[0]
        return module(tier, self.rng) if self.rng.random() < .65 else equipment(tier=tier, rng=self.rng)

    def start_battle(self):
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
        danger = min(5, math.hypot(self.x-5, self.y-5) // 9)
        for n in range(self.rng.randint(2, 3)):
            kind = self.rng.randrange(3)
            name, hp, damage, reach, speed = [
                ('Гризун', 23, 8, 1, 3), ('Здичавілий', 36, 11, 1, 2),
                ('Плювач', 26, 9, 5, 2)][kind]
            hp += int(danger * 5)
            enemies.append(dict(id=n, name=name, hp=hp, max_hp=hp, damage=damage+int(danger),
                                range=reach, speed=speed, pos=list(candidates[n]), kind=kind))
        self.battle = dict(w=w, h=h, walls=[list(p) for p in sorted(walls)], pos=list(pos),
                           enemies=enemies, ap=6, round=1)
        self.log('Засідка! Натисніть на ворога, щоб стріляти; на землю — щоб рухатись.')

    def battle_move(self, target):
        b = self.battle
        if not b:
            return False
        occupied = set(map(tuple, b['walls'])) | {tuple(e['pos']) for e in b['enemies']}
        route = path_to(tuple(b['pos']), tuple(target), b['w'], b['h'], occupied)
        if not route or len(route) > b['ap']:
            self.log('Немає шляху або замало очок дій.')
            return False
        b['pos'] = list(target)
        b['ap'] -= len(route)
        return True

    def shot_info(self, enemy):
        b, weapon = self.battle, self.weapon
        if not b or not weapon:
            return False, 'В активному слоті немає зброї.', 0
        s = stats(weapon)
        distance = math.dist(b['pos'], enemy['pos'])
        if distance > s['range']:
            return False, 'Ціль поза дальністю.', 0
        if not visible(tuple(b['pos']), tuple(enemy['pos']), b['walls']):
            return False, 'Перепона перекриває лінію вогню.', 0
        chance = max(45, min(98, s['accuracy'] - int(max(0, distance-3)*3)))
        return True, '', chance

    def shoot(self, enemy_id):
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
            self.log(f"Для пострілу потрібно {self.weapon['ap']} ОД.")
            return False
        b['ap'] -= self.weapon['ap']
        if self.rng.randrange(100) < chance:
            damage = max(1, stats(self.weapon)['damage'] + (self.level-1)*2 + self.rng.randint(-2, 2))
            e['hp'] -= damage
            self.log(f"{e['name']}: −{damage} HP ({chance}% влучання).")
            if e['hp'] <= 0:
                b['enemies'].remove(e)
                self.xp += 20
                self.log(f"{e['name']} знищено. +20 досвіду.")
            if not b['enemies']:
                self.victory()
        else:
            self.log(f'Промах ({chance}% влучання).')
        return True

    def switch(self):
        other = 'weapon2' if self.active == 'weapon1' else 'weapon1'
        if not self.equipped[other]:
            self.log('Другий слот порожній.')
            return False
        if self.battle:
            if self.battle['ap'] < 1:
                self.log('Для зміни зброї потрібно 1 ОД.')
                return False
            self.battle['ap'] -= 1
        self.active = other
        return True

    def end_turn(self):
        b = self.battle
        if not b:
            return
        for e in b['enemies']:
            for _ in range(e['speed']):
                if math.dist(e['pos'], b['pos']) <= e['range'] and visible(tuple(e['pos']), tuple(b['pos']), b['walls']):
                    break
                blocked = set(map(tuple, b['walls'])) | {tuple(other['pos']) for other in b['enemies'] if other is not e}
                route = path_to(tuple(e['pos']), tuple(b['pos']), b['w'], b['h'], blocked)
                if route and route[0] != tuple(b['pos']):
                    e['pos'] = list(route[0])
            if math.dist(e['pos'], b['pos']) <= e['range'] and visible(tuple(e['pos']), tuple(b['pos']), b['walls']):
                damage = max(1, e['damage'] + self.rng.randint(-2, 2) - self.defense)
                self.hp -= damage
                self.log(f"{e['name']} атакує: −{damage} HP.")
                if self.hp <= 0:
                    self.defeat()
                    return
        b['ap'] = 6
        b['round'] += 1
        self.log(f"Раунд {b['round']}. Ваш хід.")

    def victory(self):
        self.battle = None
        reward = self.rng.randint(45, 85)
        self.money += reward
        self.loot.extend([self.roll_item(), self.roll_item(), supply('med')])
        self.log(f'Перемога! +{reward} кредитів. Здобич чекає у відповідній вкладці.')

    def flee(self):
        if not self.battle:
            return False
        if self.battle['pos'][0] != 0 or self.battle['ap'] < 2:
            self.log('Для втечі дістаньтесь лівого краю арени й залиште 2 ОД.')
            return False
        self.battle = None
        self.log('Ви відірвались від переслідувачів.')
        return True

    def defeat(self):
        loss = min(self.money, max(25, self.money // 4))
        self.money -= loss
        self.x, self.y = self.cities[0]
        self.hp = self.max_hp
        self.battle = None
        self.loot.clear()
        self.log(f'Вас витягнув караван. Сховище 17. Втрачено {loss} кредитів і незабрану здобич.')

    def rest(self):
        if self.city is None or self.battle:
            return False
        if self.hp == self.max_hp:
            self.log('Ви вже відпочили.')
            return False
        if self.money < 15:
            self.log('Ночівля коштує 15 кредитів.')
            return False
        self.money -= 15
        self.hp = self.max_hp
        self.turn += 4
        self.log('Ночівля: здоров’я повністю відновлено.')
        return True

    def stock(self, merchant):
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
        if buying:
            return 85 if merchant == 2 else int(item_value(item)*1.15)
        return max(1, int(item_value(item) * (.22 if merchant == 2 else .50)))

    def buys_kind(self, item, merchant):
        return merchant == 2 or item['kind'] in (('weapon', 'armor', 'helmet', 'module') if merchant == 0 else ('food', 'med'))

    def buy(self, item_id, merchant):
        items = self.stock(merchant)
        item = next((i for i in items if i['id'] == item_id), None)
        if not item:
            return False
        price = self.price(item, merchant)
        if self.money < price:
            self.log('Недостатньо кредитів.')
            return False
        if not self.accept(item):
            return False
        self.money -= price
        items.remove(item)
        self.log(f"Куплено: {item['name']} · {RARITIES[item['rarity']][0]}.")
        return True

    def sell(self, item_id, merchant):
        if self.city is None or self.battle:
            return False
        item = next((i for i in self.bag if i['id'] == item_id), None)
        if not item or not self.buys_kind(item, merchant):
            self.log('Цей торговець не купує такий товар.')
            return False
        price = self.price(item, merchant, False)
        self.bag.remove(item)
        self.money += price
        self.log(f"Продано {item['name']} за {price} кр.")
        return True

    def collect(self, item_id):
        if self.battle:
            return False
        item = next((i for i in self.loot if i['id'] == item_id), None)
        if item and self.accept(item):
            self.loot.remove(item)
            return True
        return False

    def save(self, path):
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
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if data.pop('version', None) != 1:
            raise ValueError('Невідома версія збереження.')
        def tuples(value):
            return tuple(tuples(i) for i in value) if isinstance(value, list) else value
        state = tuples(data.pop('rng_state'))
        game = cls(0)
        required = set(vars(game)) - {'rng'}
        if set(data) != required or len(data['world']) != 32 or set(data['equipped']) != set(SLOTS):
            raise ValueError('Збереження пошкоджене або несумісне.')
        game.__dict__.update(data)
        game.rng.setstate(state)
        return game



# Expanded content. All sprites are drawn locally with Canvas in visuals.py.
GEAR.update({
    'Револьвер «Ворон»': ('weapon', 22, 5, 0, 87, 2.2, 3),
    'ПП «Шершень»': ('weapon', 12, 4, 0, 90, 2.4, 2),
    'Карабін «Пілігрим»': ('weapon', 17, 7, 0, 90, 3.7, 2),
    'Снайперська «Горизонт»': ('weapon', 30, 12, 0, 94, 5.8, 4),
    'Кулемет «Молот»': ('weapon', 32, 7, 0, 76, 7.2, 4),
    'Плазмомет «Сонце»': ('weapon', 29, 5, 0, 90, 5.1, 3),
    'Гаус-карабін «Імпульс»': ('weapon', 25, 10, 0, 96, 4.6, 3),
    'Іонний пістолет «Іскра»': ('weapon', 15, 5, 0, 94, 1.9, 2),
    'Арбалет «Тиша»': ('weapon', 24, 7, 0, 92, 3.2, 3),
    'Плащ розвідника': ('armor', 0, 0, 2, 0, 2.6, 0),
    'Кевларова жилетка': ('armor', 0, 0, 4, 0, 4.0, 0),
    'Костюм «Сталкер»': ('armor', 0, 0, 5, 0, 5.5, 0),
    'Панцир «Черепаха»': ('armor', 0, 0, 9, 0, 10.5, 0),
    'Екзокаркас «Атлант»': ('armor', 0, 0, 11, 0, 12.0, 0),
    'Костюм «Фантом»': ('armor', 0, 0, 5, 0, 3.6, 0),
    'Композит «Світанок»': ('armor', 0, 0, 7, 0, 6.4, 0),
    'Каптур вигнанця': ('helmet', 0, 0, 1, 0, .7, 0),
    'Каска рейнджера': ('helmet', 0, 0, 3, 0, 2.0, 0),
    'Шолом «Циклоп»': ('helmet', 0, 0, 4, 0, 2.5, 0),
    'Маска «Привид»': ('helmet', 0, 0, 2, 0, 1.1, 0),
    'Важкий шолом «Форт»': ('helmet', 0, 0, 5, 0, 3.2, 0),
    'Візор «Обрій»': ('helmet', 0, 0, 3, 0, 1.7, 0),
})
MODULES.extend([
    ('Розривний осердок', 'weapon', 'damage', 4),
    ('Далекомір', 'weapon', 'accuracy', 5),
    ('Прискорювач', 'weapon', 'pierce', 2),
    ('Критичний процесор', 'weapon', 'crit', 5),
    ('Фокусувальна лінза', 'weapon', 'range', 1),
    ('Магнітна котушка', 'weapon', 'damage', 5),
    ('Балістичний комп’ютер', 'weapon', 'accuracy', 6),
    ('Вольфрамовий канал', 'weapon', 'pierce', 3),
    ('Керамічні вставки', 'protection', 'defense', 2),
    ('Медична підкладка', 'protection', 'vitality', 8),
    ('Сервопривід', 'protection', 'capacity', 2),
    ('Камуфляжний екран', 'protection', 'evasion', 3),
    ('Регенератор', 'protection', 'regen', 1),
    ('Аварійний каркас', 'protection', 'vitality', 10),
    ('Розвантажувальна система', 'protection', 'capacity', 3),
    ('Реактивні пластини', 'protection', 'defense', 3),
])
STAT_NAMES.update(attack='Атака', pierce='Атака', crit='Крит. шанс', vitality='Макс. HP',
                  capacity='Вантажність', evasion='Ухилення', regen='Регенерація')
CITY_NAMES.extend(['Тиха Балка', 'Мідні Ворота', 'Станція Омега', 'Глиняний Брід',
                   'Чорний Маяк', 'Останній Сад', 'Бурштин'])
MERCHANTS.append('Мандрівний торговець')
MONSTERS = [
    ('Гризун', 23, 8, 1, 3, 0, '#b68a63'),
    ('Здичавілий', 36, 11, 1, 2, 1, '#b97667'),
    ('Плювач', 26, 9, 5, 2, 0, '#b7bd66'),
    ('Сліпий гончак', 30, 10, 1, 4, 0, '#bca28b'),
    ('Панцирник', 45, 13, 1, 1, 6, '#94a19a'),
    ('Кислотний кліщ', 25, 12, 4, 2, 2, '#9bc560'),
    ('Попелястий вовк', 40, 14, 1, 3, 1, '#c4c3b7'),
    ('Сторожовий дрон', 33, 13, 6, 2, 4, '#93bbc5'),
    ('Болотяник', 48, 12, 2, 2, 2, '#669b77'),
    ('Кістяний велет', 76, 19, 1, 1, 5, '#d9c9aa'),
    ('Іскровик', 38, 15, 7, 2, 2, '#ad94de'),
    ('Химерний павук', 44, 15, 3, 3, 3, '#ce917b'),
]
EXTRA_CITIES = [[5, 15], [27, 4], [28, 16], [4, 28], [44, 15], [24, 28], [17, 17]]
MAYORS = [0, 2, 3, 5, 7, 9, 11]
QUEST_KINDS = ['hunt', 'retrieve', 'scout', 'supplies', 'purge']
QUEST_LABELS = {'hunt': 'Захист поселення', 'retrieve': 'Загублена реліквія',
                'scout': 'Розвідка території', 'supplies': 'Запаси для лікарні', 'purge': 'Зачистка підземелля'}


class ExpansionGame(LegacyGame):
    def __init__(self, seed=None):
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
        for point in self.cities[5:]:
            near = min(self.cities[:5], key=lambda p: math.dist(p, point))
            for x in range(min(near[0], point[0]), max(near[0], point[0])+1):
                self.world[point[1]][x] = 'road'
            for y in range(min(near[1], point[1]), max(near[1], point[1])+1):
                self.world[y][near[0]] = 'road'
        for x, y in self.cities:
            self.world[y][x] = 'city'

    def protection_stat(self, key):
        return sum(stats(i).get(key, 0) for i in self.equipped.values() if i and i['kind'] != 'weapon')

    @property
    def capacity(self):
        return 35.0 + self.protection_stat('capacity')

    @property
    def max_hp(self):
        return 100 + (self.level-1)*8 + self.protection_stat('vitality')

    def _change_gear(self, fn):
        # Transactional rollback if removing a load-bearing item would overload the player.
        import copy
        before = copy.deepcopy((self.bag, self.equipped))
        ok = fn()
        if ok and self.weight > self.capacity + .0001:
            self.bag, self.equipped = before
            self.log('Спершу зменште вагу: цей предмет підтримує вантажність.')
            return False
        self.hp = min(self.hp, self.max_hp)
        return ok

    def equip(self, item_id, slot):
        return self._change_gear(lambda: super(ExpansionGame, self).equip(item_id, slot))

    def unequip(self, slot):
        return self._change_gear(lambda: super(ExpansionGame, self).unequip(slot))

    def uninstall(self, item_id, mod_id):
        return self._change_gear(lambda: super(ExpansionGame, self).uninstall(item_id, mod_id))

    def put_module(self, item_id, mod_id, slot_index):
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
            self.log(f"Замінено: {old['name']} → {mod['name']}.")
            return True
        return self._change_gear(replace)

    def available_merchant(self, merchant):
        if self.battle:
            return False
        if merchant == 3:
            return bool(self.traveler and self.traveler['pos'] == [self.x, self.y])
        return self.city is not None and merchant in self.city_merchants[self.city]

    def stock(self, merchant):
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
        if merchant == 3:
            return max(1, int(item_value(item) * (.5 if buying else .3)))
        return super().price(item, merchant, buying)

    def buys_kind(self, item, merchant):
        if item['kind'] == 'quest':
            return False
        return merchant == 3 or super().buys_kind(item, merchant)

    def sell(self, item_id, merchant):
        if not self.available_merchant(merchant):
            return False
        item = next((i for i in self.bag if i['id'] == item_id), None)
        if not item or not self.buys_kind(item, merchant):
            return False
        self.money += self.price(item, merchant, False)
        self.bag.remove(item)
        self.log(f"Продано: {item['name']}.")
        return True

    def spawn_traveler(self):
        rare = equipment(tier=self.rng.choice([3, 4]), rng=self.rng)
        self.traveler = dict(pos=[self.x, self.y], items=[rare, module(4, self.rng)] +
                             [supply('food') for _ in range(5)] + [supply('med') for _ in range(3)])
        self.last_traveler_turn = self.turn
        self.log('На дорозі мандрівний торговець! Рідкісні речі та припаси за 50% базової вартості.')

    def step(self, dx, dy):
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
        for q in self.quests:
            if q['status'] == 'active' and q['kind'] == 'scout' and q['pos'] == [self.x, self.y]:
                q['progress'] = 1
                self.log('Розвідку завершено. Поверніться до мера.')

    def start_battle(self):
        super().start_battle()
        danger = min(5, int(math.hypot(self.x-5, self.y-5)//9))
        for e in self.battle['enemies']:
            kind = self.rng.randrange(min(len(MONSTERS), 6 + danger*2))
            name, hp, damage, reach, speed, armor, color = MONSTERS[kind]
            hp += danger*4
            e.update(name=name, hp=hp, max_hp=hp, damage=damage+danger, range=reach,
                     speed=speed, armor=armor, kind=kind)

    def shoot(self, enemy_id):
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
            self.log(f"Для пострілу потрібно {self.weapon['ap']} ОД.")
            return False
        b['ap'] -= self.weapon['ap']
        if self.rng.randrange(100) < chance:
            s = stats(self.weapon)
            critical = self.rng.randrange(100) < min(65, 5+s.get('crit', 0))
            raw = s['damage'] + (self.level-1)*2 + self.rng.randint(-2, 2)
            damage = max(1, int(raw*(1.6 if critical else 1))-max(0, e.get('armor', 0)-s.get('pierce', 0)))
            e['hp'] -= damage
            self.log(f"{'КРИТ! ' if critical else ''}{e['name']}: −{damage} HP.")
            if e['hp'] <= 0:
                b['enemies'].remove(e)
                self.xp += 20
                self._kill_objectives(e['kind'])
                self.log(f"{e['name']} знищено. +20 XP.")
            if not b['enemies']:
                self.victory()
        else:
            self.log(f'Промах ({chance}% влучання).')
        return True

    def end_turn(self):
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
                route = path_to(tuple(e['pos']), tuple(b['pos']), b['w'], b['h'], blocked)
                if route and route[0] != tuple(b['pos']):
                    e['pos'] = list(route[0])
            if math.dist(e['pos'], b['pos']) <= e['range'] and visible(tuple(e['pos']), tuple(b['pos']), b['walls']):
                if self.rng.randrange(100) < min(45, self.protection_stat('evasion')):
                    self.log(f"Ухилення від атаки: {e['name']}.")
                    continue
                damage = max(1, e['damage'] + self.rng.randint(-2, 2) - self.defense)
                self.hp -= damage
                self.log(f"{e['name']} атакує: −{damage} HP.")
                if self.hp <= 0:
                    self.defeat()
                    return
        healing = min(self.max_hp-self.hp, self.protection_stat('regen'))
        if healing:
            self.hp += healing
            self.log(f'Регенерація: +{healing} HP.')
        b['ap'] = 6
        b['round'] += 1
        self.log(f"Раунд {b['round']}. Ваш хід.")

    def victory(self):
        quest_id = self.quest_battle
        super().victory()
        if quest_id:
            q = next((q for q in self.quests if q['id'] == quest_id and q['status'] == 'active'), None)
            if q:
                q['progress'] = 1
                self.log('Гніздо знищено. Поверніться до мера по нагороду.')
        self.quest_battle = None

    def flee(self):
        ok = super().flee()
        if ok:
            self.quest_battle = None
        return ok

    def defeat(self):
        super().defeat()
        self.quest_battle = None
        self.traveler = None

    def mayor_offers(self):
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
        offer = next((q for q in self.mayor_offers() if q['id'] == quest_id and q['status'] == 'offered'), None)
        if not offer:
            return False
        if sum(q['status'] == 'active' for q in self.quests) >= 8:
            self.log('Спочатку завершіть частину завдань (ліміт 8 активних).')
            return False
        q = dict(offer)
        q['status'] = 'active'
        if q['kind'] in ('retrieve', 'scout', 'purge'):
            occupied = {tuple(t['pos']) for t in self.quests if t.get('pos') and t['status'] == 'active'}
            candidates = [(x, y) for y in range(32) for x in range(48)
                          if 4 <= abs(x-self.x)+abs(y-self.y) <= 12 and [x, y] not in self.cities and (x, y) not in occupied]
            if not candidates:
                self.log('Немає вільної локації для завдання.')
                return False
            q['pos'] = list(self.rng.choice(candidates))
        offer['status'] = 'accepted'
        self.quests.append(q)
        self.log(f"Взято завдання: {q['title']}. Відкрийте «Завдання».")
        return True

    def _kill_objectives(self, kind):
        for q in self.quests:
            if q['status'] == 'active' and q['kind'] == 'hunt' and (q['target_kind'] is None or q['target_kind'] == kind):
                q['progress'] = min(q['goal'], q['progress']+1)

    def quest_ready(self, q):
        if q['status'] != 'active':
            return False
        if q['kind'] == 'supplies':
            return sum(i['kind'] == 'food' for i in self.bag) >= 3 and sum(i['kind'] == 'med' for i in self.bag) >= 2
        if q['kind'] == 'retrieve':
            return any(i.get('quest_id') == q['id'] for i in self.bag)
        return q['progress'] >= q['goal']

    def quest_text(self, q):
        kind = q['kind']
        if kind == 'hunt':
            target = 'будь-яких мутантів' if q['target_kind'] is None else MONSTERS[q['target_kind']][0]
            desc = f"Знищити {target}: {q['progress']}/{q['goal']}. Рахуються лише вбивства після взяття."
        elif kind == 'retrieve':
            desc = 'Знайти довоєнний навігатор. Він з’явиться лише після взяття завдання; купити його неможливо.'
        elif kind == 'scout':
            desc = 'Дістатися позначеної точки та повернутися з розвідданими.'
        elif kind == 'supplies':
            food = sum(i['kind'] == 'food' for i in self.bag)
            med = sum(i['kind'] == 'med' for i in self.bag)
            desc = f'Принести 3 консерви ({food}/3) та 2 аптечки ({med}/2). Їх буде передано лікарні.'
        else:
            desc = 'Дістатися гнізда, обшукати ділянку [E] і виграти спеціальний бій. Втеча не завершує завдання.'
        if q.get('pos'):
            desc += f"\nПозначка на мапі: {q['pos'][0]}, {q['pos'][1]}."
        state = 'ДОСТУПНЕ' if q['status'] == 'offered' else ('ВИКОНАНО' if q['status'] == 'done' else ('ГОТОВО ДО ЗДАЧІ' if self.quest_ready(q) else 'У ПРОЦЕСІ'))
        return f"{q['title']}\n{desc}\nЗамовник: мер · {CITY_NAMES[q['city']]}\nНагорода: {q['reward']} кр. + 40 XP\n{state}"

    def turn_in(self, quest_id):
        q = next((q for q in self.quests if q['id'] == quest_id), None)
        if self.battle or not q or self.city != q['city'] or not self.quest_ready(q):
            self.log('Виконайте умови та поверніться до мера міста-замовника.')
            return False
        if q['kind'] == 'retrieve':
            self.bag[:] = [i for i in self.bag if i.get('quest_id') != q['id']]
        elif q['kind'] == 'supplies':
            for kind, count in [('food', 3), ('med', 2)]:
                for _ in range(count):
                    self.bag.remove(next(i for i in self.bag if i['kind'] == kind))
        q['status'] = 'done'
        self.money += q['reward']
        self.xp += 40
        self.log(f"Завдання виконано: {q['title']}. +{q['reward']} кр., +40 XP.")
        return True

    def search(self):
        if self.battle or self.city is not None:
            return False
        for q in self.quests:
            if q['status'] != 'active' or q.get('pos') != [self.x, self.y] or self.quest_ready(q):
                continue
            if q['kind'] == 'retrieve':
                item = dict(id=uid(), name='Довоєнний навігатор', kind='quest', rarity=2,
                            weight=0, value=0, quest_id=q['id'])
                self.bag.append(item)
                q['progress'] = 1
                self.turn += 1
                self.log('Знайдено квестовий навігатор! Він захищений від продажу та втрати.')
                return True
            if q['kind'] == 'purge':
                self.start_battle()
                self.quest_battle = q['id']
                for e in self.battle['enemies']:
                    e['max_hp'] += 12
                    e['hp'] += 12
                self.log('Гніздо пробудилося! Для завдання потрібно перемогти.')
                return True
        return super().search()

    def save(self, path):
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
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        version = data.pop('version', None)
        if version not in (1, 2):
            raise ValueError('Невідома версія збереження.')
        def tuples(v):
            return tuple(tuples(x) for x in v) if isinstance(v, list) else v
        state = tuples(data.pop('rng_state'))
        game = cls(0)
        allowed = set(vars(game))-{'rng'}
        if set(data)-allowed or len(data['world']) != 32 or set(data['equipped']) != set(SLOTS):
            raise ValueError('Збереження пошкоджене.')
        if version == 2 and set(data) != allowed:
            raise ValueError('Неповне збереження.')
        game.__dict__.update(data)
        if version == 1:
            game.cities.extend([p[:] for p in EXTRA_CITIES])
            game._connect_cities()
            game.shops = {}
            game.log('Збереження v1 оновлено: нові міста, торговці й квести доступні.')
        game.rng.setstate(state)
        return game


from progression import equipment, module, supply, stats, item_weight, item_value
from frontier import Game

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

    class App:
        def __init__(self, root):
            self.root = root
            root.app=self
            self.game = Game()
            self.perk_prompted = -1
            self.mode = 'world'
            self.selection = None
            self.inventory_ids = []
            self.shop_ids = []
            self.merchant = 0
            self.dialog = None
            self.hover = None
            root.after_idle(lambda:sprites.decorate(root))
            root.title('AFTERDAYS v0.13 — Після останнього світанку')
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
            tk.Label(header, text='A F T E R D A Y S', bg=BG, fg=GOLD, font=('Segoe UI', 23, 'bold')).pack(side='left')
            tk.Label(header, text='  /  ПІСЛЯ ОСТАННЬОГО СВІТАНКУ', bg=BG, fg=MUTED, font=('Segoe UI', 10)).pack(side='left')
            for title, fn in [('Арти',lambda:sprites.gallery(self)),('?', self.help), ('Нова гра', self.new), ('Завантажити', self.load), ('Зберегти', self.save)]:
                ttk.Button(header, text=title, command=fn).pack(side='right', padx=3)
            self.status = tk.Label(root, bg=PANEL, fg=TEXT, anchor='w', padx=16, pady=10, font=('Segoe UI', 11))
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
            self.canvas.bind('<Motion>', self.map_hover)
            import inspection_ui
            self.canvas.bind('<Button-3>',lambda e:inspection_ui.inspect_monster(self,e))
            self.hint = tk.Label(left, bg=BG, fg=MUTED, anchor='w', justify='left', wraplength=680, height=4)
            self.hint.pack(fill='x', pady=5)
            controls = tk.Frame(left, bg=BG)
            controls.pack(fill='x')
            self.end_button = ttk.Button(controls, text='Завершити хід [Space]', command=lambda: self.act(self.game.end_turn))
            self.end_button.pack(side='left', padx=2)
            ttk.Button(controls, text='Зброя [Tab]', command=lambda: self.act(self.game.switch)).pack(side='left', padx=2)
            ttk.Button(controls, text='Аптечка [H]', command=lambda: self.act(lambda: self.game.use('med'))).pack(side='left', padx=2)
            self.flee_button = ttk.Button(controls, text='Втеча', command=lambda: self.act(self.game.flee))
            self.flee_button.pack(side='left', padx=2)
            ttk.Button(controls,text='Дія [E]',command=lambda:self.act(self.game.search)).pack(side='left',padx=2)
            side = tk.Frame(body, bg=PANEL, width=380)
            side.grid(row=0,column=1,sticky='nsew',padx=(6,0))
            side.pack_propagate(False)
            buttons = controls.winfo_children()

            for button in buttons:
                button.pack_forget()

            for n, button in enumerate(buttons):
                button.grid(
                    row=n//3, column=n%3,
                    sticky='ew', padx=2, pady=2
                )
            controls.columnconfigure((0,1,2),weight=1)
            self.root.after_idle(lambda:self.hint.config(wraplength=max(300,left.winfo_width()-10)))
            self.tabs = ttk.Notebook(side)
            self.tabs.pack(fill='both', expand=True)
            self.world_tab, self.inv_tab, self.loot_tab, self.quest_tab = [ttk.Frame(self.tabs) for _ in range(4)]
            for tab, title in [(self.world_tab, 'Місцевість'), (self.inv_tab, 'Екіпіровка'), (self.loot_tab, 'Здобич'), (self.quest_tab, 'Завдання')]:
                key={self.world_tab:'site',self.inv_tab:'backpack',self.loot_tab:'loot',self.quest_tab:'journal'}[tab]
                art=sprites.photo(root,key,16)
                self.tabs.add(tab,text=title,**({'image':art,'compound':'left'} if art else {}))
            import frontier_ui
            self.player_tab = ttk.Frame(self.tabs)
            self.tabs.add(self.player_tab,text='Гравець')
            self.player_panel=frontier_ui.PlayerPanel(self.player_tab,self)
            self.player_panel.pack(fill='both',expand=True)
            self.cartographer=lambda:frontier_ui.cartographer(self)
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
            tk.Label(self.world_tab, text='НАЙБЛИЖЧІ МІСТА', bg=PANEL, fg=GOLD).pack(anchor='w', padx=12, pady=(20, 8))
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
            ttk.Button(self.loot_tab, text='Забрати вибране', command=self.collect_selected).pack(fill='x', padx=10, pady=5)
            ttk.Button(self.loot_tab, text='Забрати все, що вміститься', command=self.collect_all).pack(fill='x', padx=10, pady=5)
            tk.Label(self.loot_tab, text='Здобич доступна після бою. Незабране\nвтрачається при наступному переході.\nМожна звільнити вагу в інвентарі.', bg=PANEL, fg=MUTED, justify='left').pack(padx=10, pady=12)
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
            if self.fx.blocked:
                return
            before_battle = self.game.battle is not None
            fn()
            self.refresh()
            if before_battle and not self.game.battle and self.game.loot:
                self.tabs.select(self.loot_tab)

        def refresh(self):
            self.fx.ingest()
            g = self.game
            weapon = g.weapon
            ws = stats(weapon) if weapon else {}
            self.status.config(text=f'HP {g.hp}/{g.max_hp}    |    Захист {g.defense}    |    Вага {g.weight:.1f}/{g.capacity:.0f} кг    |    {g.money} кр.    |    Рівень {g.level} · XP {g.xp}/{progression.xp_for_level(g.level+1)}    |    Хід {g.turn}')
            combat = g.battle is not None
            self.end_button.config(state='normal' if combat else 'disabled')
            self.flee_button.config(state='normal' if combat else 'disabled')
            self.tabs.tab(self.loot_tab, text=f'Здобич {len(g.loot)}')
            self.services.refresh()
            self.location.config(text=g.city_name(g.city) if g.city is not None else TERRAINS[g.world[g.y][g.x]][1])
            self.city_info.config(text=(f'Особлива локація. Тут вас чекає {g.current_site["npc"]}.' if g.current_site else 'Безпечна зона. Торгівля, сховище та відпочинок.\nНові доручення — кожні 100 ходів.' if g.city is not None else
                                      'Обшук може дати спорядження та припаси,\nале шум приваблює мутантів.\nКожні 8 переходів витрачаються консерви.') +
                                      f'\n\nКоординати: {g.x}, {g.y} · зона L{g.region_level}\nАктивна: {weapon["name"] if weapon else "немає зброї"}\nШкода {ws.get("damage", 0)} · дальність {ws.get("range", 0)}\nПостріл: {weapon["ap"] if weapon else "—"} ОД')
            if weapon:
                ammo_type=weapon.get('ammo_type','pistol')
                self.city_info.config(text=self.city_info.cget('text')+f'\n{progression.AMMO[ammo_type][0]}: {g.count("ammo",ammo_type)} · стан {weapon.get("durability",100):.0f}%')
            self.city_info.config(text=self.city_info.cget('text')+f'\n☢ Захист: {g.rad_turns} ходів')
            near = sorted(((n,pos) for n,pos in enumerate(g.cities) if n in g.known_cities), key=lambda entry: math.dist(entry[1], (g.x, g.y)))[:3]
            self.cities_label.config(text='\n'.join(f'◆ {self.game.city_name(n)} ({p[0]}, {p[1]})' for n,p in near))
            self.player_panel.refresh()
            self.inv_panel.refresh()
            self.quest_panel.refresh()
            self.tabs.tab(self.quest_tab, text='Завдання')
            self.loot_list.set_items(g.loot)
            self.logbox.config(state='normal')
            self.logbox.delete('1.0', 'end')
            self.logbox.insert('end', '\n'.join(g.messages[-5:]))
            self.logbox.see('end')
            self.logbox.config(state='disabled')
            self.draw()
            self.root.after_idle(self.offer_notices)

        def offer_notices(self):
            if self.dialog or self.fx.blocked:
                return
            if self.game.road_event:
                self.road_dialog()
            elif self.game.pending_perks and self.perk_prompted != self.game.level//2:
                self.perk_prompted = self.game.level//2
                self.perks()

        def road_dialog(self):
            if not self.dialog and self.game.road_event:
                adventure_ui.road_window(self)

        def storage(self):
            if self.game.regular_city and not self.game.battle:
                win=self.popup('Власне сховище','940x680')
                adventure_ui.Storage(win,self).pack(fill='both',expand=True)

        def perks(self):
            if not self.dialog:
                refinement_ui.perks(self)

        def technician(self):
            if not self.game.battle and self.game.city in self.game.technicians:
                win=self.popup('Технік · майстерня','790x690')
                refinement_ui.Technician(win,self).pack(fill='both',expand=True)

        def description(self,item):
            return refinement_ui.description(self.game,item)

        def selected_id(self):
            return self.inv_panel.selection

        def describe_selection(self):
            self.inv_panel.select(self.selected_id())

        def equip_selected(self):
            if self.game.battle:
                self.act(lambda: self.game.log('Зміна екіпіровки недоступна під час бою.'))
                return
            item_id = self.selected_id()
            item = self.game.find(item_id)
            if not item:
                return
            slot = next((s for s, i in self.game.equipped.items() if i and i['id'] == item_id), None)
            if slot:
                self.act(lambda: self.game.unequip(slot))
            elif item['kind'] == 'weapon':
                answer = messagebox.askyesnocancel('Слот зброї', 'Встановити у слот I?\n«Ні» — у слот II.', parent=self.root)
                if answer is not None:
                    self.act(lambda: self.game.equip(item_id, 'weapon1' if answer else 'weapon2'))
            elif item['kind'] in ('armor', 'helmet'):
                self.act(lambda: self.game.equip(item_id, item['kind']))

        def use_selected(self):
            item = self.game.find(self.selected_id())
            if item and item['kind']=='sealed':
                if self.fx.blocked:return
                found=self.game.open_chest(item['id'])
                if found:
                    self.refresh()
                    import inspection_ui
                    inspection_ui.result(self,found,animate=True)
                else:self.game.log('Скриню можна відкрити поза боєм.');self.refresh()
                return
            if item and item['kind'] in ('med', 'food', 'rad'):
                self.act(lambda: self.game.use(item['kind']))

        def drop_selected(self):
            item = self.game.find(self.selected_id())
            if item and item['kind'] == 'quest':
                self.act(lambda: self.game.log('Квестові предмети захищені від втрати.'))
            elif self.game.battle:
                self.act(lambda: self.game.log('Викидати спорядження можна поза боєм.'))
            elif item and item in self.game.bag and messagebox.askyesno('Викинути', f'Викинути {item["name"]} разом із модулями?', parent=self.root):
                self.game.drop_item(item['id'])
                self.refresh()

        def dismantle_selected(self):
            item=self.game.find(self.selected_id())
            if self.game.battle or not item or item['kind'] not in ('weapon','armor','helmet'):
                return
            if item not in self.game.bag:
                self.act(lambda:self.game.log('Спочатку зніміть предмет у рюкзак.'))
                return
            count=self.game.salvage_yield(item)
            if messagebox.askyesno('Розібрати спорядження',f'Розібрати {item["name"]} на {count} одиниць матеріалу ({"запчастини" if item["kind"]=="weapon" else "фрагменти"})? Корпус зникне, модулі повернуться.',parent=self.root):
                self.act(lambda:self.game.dismantle(item['id']))

        def popup(self, title, geometry):
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
            win.protocol('WM_DELETE_WINDOW', close)
            win.bind('<Escape>', lambda e: close())
            return win

        def modify(self):
            item = self.game.find(self.selected_id())
            if not item or 'slots' not in item:
                return
            if self.game.battle:
                self.act(lambda: self.game.log('Модифікації доступні лише поза боєм.'))
                return
            win = self.popup('Модифікації · ' + item['name'], '770x730')
            panel = visuals.ModificationPanel(win, self, item['id'])
            panel.pack(fill='both', expand=True)

        def mayor(self):
            if self.game.city not in self.game.mayors or self.game.battle:return
            win=self.popup('Доручення · '+self.game.city_name(self.game.city),'750x670')
            refinement_ui.QuestCards(win,self,mayor=True).pack(fill='both',expand=True)

        def atlas(self):
            import frontier_ui
            win = self.popup('Атлас Пустки · міста й відкриті локації', '1000x730')
            tk.Label(win, text='АТЛАС / ДАЛІ ВІД СХОВИЩА 17 → НЕБЕЗПЕЧНІШЕ / ! ЗАВДАННЯ / ★ УНІКАЛЬНЕ', bg=PANEL, fg=GOLD,
                     font=('Segoe UI', 12, 'bold')).pack(pady=10)
            c = tk.Canvas(win, bg=BG, highlightthickness=0)
            c.pack(fill='both', expand=True, padx=12)
            detail = tk.Label(win, text='Бірюзові лінії — відкрита мережа метро. Клік на місто — торговці й мер. Клік на позначку — завдання. Переміщення тут немає.',
                              bg=PANEL, fg=TEXT, wraplength=950, height=3)
            detail.pack(fill='x', padx=12, pady=8)
            layout = {}
            def paint(event=None):
                c.delete('all');c._terrain_refs=[]
                t = min(c.winfo_width()/48, c.winfo_height()/32)
                ox, oy = (c.winfo_width()-48*t)/2, (c.winfo_height()-32*t)/2
                layout.update(t=t, ox=ox, oy=oy)
                for y in range(32):
                    for x in range(48):
                        if not self.game.revealed(x,y):
                            c.create_rectangle(ox+x*t,oy+y*t,ox+(x+1)*t,oy+(y+1)*t,fill='#101714',outline='')
                            continue
                        kind = self.game.world[y][x]
                        c.create_rectangle(ox+x*t,oy+y*t,ox+(x+1)*t,oy+(y+1)*t,fill=TERRAINS[kind][0],outline='')
                for x,y in self.game.trails:
                    if not self.game.revealed(x,y):continue
                    c.create_oval(ox+(x+.35)*t,oy+(y+.35)*t,ox+(x+.65)*t,oy+(y+.65)*t,fill='#c8b17c',outline='')
                for key in self.game.radiation:
                    x,y=map(int,key.split(','))
                    if not self.game.revealed(x,y):continue
                    c.create_rectangle(ox+x*t,oy+y*t,ox+(x+1)*t,oy+(y+1)*t,outline='#9fba51')
                frontier_ui.draw_metro(c,self.game,t,ox,oy)
                for n,(x,y) in enumerate(self.game.cities):
                    if n not in self.game.known_cities:continue
                    px,py = ox+(x+.5)*t, oy+(y+.5)*t
                    c.create_rectangle(px-t*.4,py-t*.4,px+t*.4,py+t*.4,outline=GOLD)
                    c.create_text(px+8,py-9,text=self.game.city_name(n), fill=TEXT, anchor='w', font=('Segoe UI', 8))
                for q in self.game.quests:
                    if q['status'] != 'active':
                        continue
                    pos = self.game.cities[q['city']] if self.game.quest_ready(q) else q.get('pos')
                    if pos:
                        px,py = ox+(pos[0]+.5)*t, oy+(pos[1]+.5)*t
                        c.create_oval(px-8,py-8,px+8,py+8,fill='#a674cd' if q.get('unique') else '#b48b40',outline='#ffe6a3')
                        c.create_text(px,py,text='✓' if self.game.quest_ready(q) else '!',fill='#19271e',font=('Segoe UI',11,'bold'))
                px,py = ox+(self.game.x+.5)*t, oy+(self.game.y+.5)*t
                c.create_oval(px-5,py-5,px+5,py+5,fill='#d8fae2',outline='#ffffff',width=2)
            def click(event):
                t,ox,oy = layout['t'],layout['ox'],layout['oy']
                pos=[int((event.x-ox)//t), int((event.y-oy)//t)]
                if pos in self.game.cities and self.game.cities.index(pos) in self.game.known_cities:
                    n=self.game.cities.index(pos)
                    detail.config(text=f'{self.game.city_name(n)} ({pos[0]}, {pos[1]}) · '+', '.join(MERCHANTS[m] for m in self.game.city_merchants[n])+(' · Мер: є' if n in self.game.mayors else ' · Мера немає')+(' · Технік: є' if n in self.game.technicians else '')+f' · Зона L{self.game.region_at(pos[0],pos[1])}')
                else:
                    q=next((q for q in self.game.quests if q.get('pos') == pos and q['status'] == 'active'), None)
                    detail.config(text=self.game.quest_text(q).replace('\n', ' · ') if q else f'Координати: {pos[0]}, {pos[1]} · Зона L{self.game.region_at(pos[0],pos[1])}')
            c.bind('<Configure>',paint)
            c.bind('<Button-1>',click)

        def shop(self, merchant):
            if not self.game.available_merchant(merchant):
                return
            win=self.popup(self.game.merchant_title(merchant), '960x730')
            advanced_ui.TradingPanel(win,self,merchant).pack(fill='both',expand=True)

        def collect_selected(self):
            sel=self.loot_list.selection
            if sel:self.act(lambda:self.game.collect(sel))

        def collect_all(self):
            for item in list(self.game.loot):
                self.game.collect(item['id'])
            self.refresh()

        def draw(self):
            c, g = self.canvas, self.game
            if self.fx.snapshot is not None and self.fx.blocked:
                adventure_ui.paint_snapshot(self)
                self.fx.render()
                return
            if g.battle:
                advanced_ui.draw_battle(self)
                self.fx.render()
                return
            c.delete('all');c._terrain_refs=[]
            width, height = max(c.winfo_width(), 200), max(c.winfo_height(), 200)
            b = g.battle
            cols, rows = (15, 11) if b else (23, 17)
            self.tile = max(8, min(width/cols, height/rows))
            t = self.tile
            self.ox, self.oy = (width-cols*t)/2, (height-rows*t)/2
            self.vx, self.vy = (0, 0) if b else (max(0, min(48-cols, g.x-cols//2)), max(0, min(32-rows, g.y-rows//2)))
            walls = set(map(tuple, b['walls'])) if b else set()
            reachable = {}
            if b:
                occupied = walls | {tuple(e['pos']) for e in b['enemies']}
                reachable = {tuple(b['pos']): 0}
                queue = deque([tuple(b['pos'])])
                while queue:
                    p = queue.popleft()
                    if reachable[p] >= b['ap']:
                        continue
                    for q in neighbors(*p, cols, rows):
                        if q not in occupied and q not in reachable:
                            reachable[q] = reachable[p]+1
                            queue.append(q)
                self.map_title.config(text=f'БОЙОВА ЗОНА  /  РАУНД {b["round"]}   /   ОД {b["ap"]}/6')
            else:
                self.map_title.config(text='ПУСТКА / ☢ РАДІАЦІЯ / M — АТЛАС')
            for sy in range(rows):
                for sx in range(cols):
                    x, y = sx+self.vx, sy+self.vy
                    px, py = self.ox+sx*t, self.oy+sy*t
                    if not b and not g.revealed(x,y):
                        c.create_rectangle(px,py,px+t,py+t,fill='#101714',outline='#1b2721')
                        continue
                    kind = None if b else g.world[y][x]
                    color = ('#3b4939' if (x, y) in reachable else '#29332c') if b else advanced_ui.region_color(TERRAINS[kind][0],x)
                    c.create_rectangle(px, py, px+t, py+t, fill=color, outline='#28332c')
                    if b and (x, y) in walls:
                        c.create_rectangle(px+3, py+3, px+t-3, py+t-3, fill='#656457', outline='#99927c')
                        c.create_line(px+5, py+t-6, px+t-6, py+5, fill='#454b41')
                    else:
                        visuals.terrain(c, kind, px, py, t, x, y, g, bool(b))
                    if b and x == 0:
                        c.create_line(px+2, py+2, px+2, py+t-2, fill='#72ad91', width=3)
            adventure_ui.paint_world_extras(self)
            def center(pos):
                return self.ox+(pos[0]-self.vx+.5)*t, self.oy+(pos[1]-self.vy+.5)*t
            if b:
                for e in b['enemies']:
                    px, py = center(e['pos'])
                    valid, _, chance = g.shot_info(e)
                    if valid:
                        c.create_oval(px-t*.44, py-t*.44, px+t*.44, py+t*.44, outline='#c8b475', dash=(3,2))
                    visuals.monster(c, e, px-t*.39, py-t*.42, t*.78)
                    c.create_rectangle(px-t*.36, py+t*.36, px+t*.36, py+t*.43, fill='#191c17', outline='')
                    c.create_rectangle(px-t*.36, py+t*.36, px-t*.36+t*.72*e['hp']/e['max_hp'], py+t*.43, fill='#d8876c', outline='')
            px, py = center(b['pos'] if b else (g.x, g.y))
            c.create_oval(px-t*.31, py-t*.31, px+t*.31, py+t*.31, fill='#cce4d0', outline='#ffffff', width=2)
            c.create_polygon(px, py-t*.22, px+t*.16, py+t*.17, px, py+t*.09, px-t*.16, py+t*.17, fill='#233a31')
            if not b:
                for idx, pos in enumerate(g.cities):
                    if idx not in g.known_cities:continue
                    if self.vx <= pos[0] < self.vx+cols and self.vy <= pos[1] < self.vy+rows:
                        px, py = center(pos)
                        c.create_text(px, py-t*.67, text=g.city_name(idx), fill='#efe0b5', font=('Segoe UI', 8), anchor='s')
            if not b:
                for q in g.quests:
                    if q['status'] != 'active':
                        continue
                    pos = g.cities[q['city']] if g.quest_ready(q) else q.get('pos')
                    if pos and self.vx <= pos[0] < self.vx+cols and self.vy <= pos[1] < self.vy+rows:
                        px,py = center(pos)
                        if pos == [g.x, g.y]:
                            px += t*.30
                            py -= t*.30
                        c.create_oval(px-t*.3,py-t*.3,px+t*.3,py+t*.3,fill='#ae7ed2' if q.get('unique') else '#c9a252',outline='#f9dd8d',width=2)
                        c.create_text(px,py,text='✓' if g.quest_ready(q) else '!',fill='#14291f',font=('Segoe UI',max(10,int(t*.45)),'bold'))
                if g.traveler and g.traveler['pos'] == [g.x,g.y]:
                    px,py=center((g.x,g.y))
                    c.create_text(px+t*.4,py-t*.5,text='¤',fill='#f1d383',font=('Segoe UI',16,'bold'))
            self.hint.config(text=('Клік на землю — рух · клік на ворога — постріл · підсвічені клітинки доступні за ОД\nЛівий край — евакуація. Наведіть на ворога, щоб побачити шанс влучання.' if b else
                                   'WASD / стрілки — крок · клік на мапу — один крок у вибраному напрямку\nE — обшук · I — інвентар · ◆ — міста. Дороги безпечніші за руїни.'))

        def cell(self, event):
            if self.game.battle:
                return advanced_ui.iso_cell(self,event)
            return int((event.x-self.ox)//self.tile)+self.vx, int((event.y-self.oy)//self.tile)+self.vy

        def map_hover(self, event):
            if self.game.battle:
                pos = self.cell(event)
                e = next((e for e in self.game.battle['enemies'] if tuple(e['pos']) == pos), None)
                if e:
                    valid, reason, chance = self.game.shot_info(e)
                    self.hint.config(text=f'{e["name"]} · L{e.get("level",1)} · HP {e["hp"]}/{e["max_hp"]} · шкода {e["damage"]} · Атака {e.get("attack",0)} · Захист {e.get("defense",0)} · дальність {e["range"]}\n' +
                                     (f'Шанс: {chance}%. Постріл: {self.game.weapon["ap"]} ОД. ' if valid else reason+' ') + adventure.resistance_text(e)+f' · Нагорода: {self.game.enemy_xp(e)} XP')

        def world_step(self, dx, dy):
            g = self.game
            if not g.can_step(dx,dy):
                g.step(dx,dy)
                return
            if g.loot:
                if not messagebox.askyesno('Залишити здобич?', 'Незабрана здобич залишиться тут і буде втрачена. Продовжити?', parent=self.root):
                    return
                g.loot.clear()
            g.step(dx, dy)

        def map_click(self, event):
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
            elif 0 <= x < 48 and 0 <= y < 32:
                dx, dy = x-self.game.x, y-self.game.y
                if dx or dy:
                    self.act(lambda: self.world_step((1 if dx > 0 else -1) if abs(dx) >= abs(dy) else 0,
                                                     (1 if dy > 0 else -1) if abs(dy) > abs(dx) else 0))

        def key(self, event):
            if self.dialog:
                return
            key = event.keysym.lower()
            directions = {'w': (0,-1), 'up': (0,-1), 's': (0,1), 'down': (0,1),
                          'a': (-1,0), 'left': (-1,0), 'd': (1,0), 'right': (1,0)}
            if key in directions:
                if isinstance(event.widget, tk.Listbox) and key in ('up', 'down'):
                    return
                dx, dy = directions[key]
                self.act(lambda: self.game.step(dx, dy) if self.game.battle else self.world_step(dx, dy))
            elif key == 'space':
                self.act(self.game.end_turn)
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
                self.atlas()
            elif key == 'f5':
                self.save()
            elif key == 'f9':
                self.load()
            else:
                return
            return 'break'

        def save(self):
            try:
                self.game.save(save_path)
                self.game.log('Гру збережено. F9 — завантажити.')
            except OSError as exc:
                messagebox.showerror('Не вдалося зберегти', str(exc), parent=self.root)
            self.refresh()

        def load(self):
            if not save_path.exists():
                messagebox.showinfo('Збереження', 'Збереженої гри ще немає.', parent=self.root)
                return
            if not messagebox.askyesno('Завантажити', 'Замінити поточну гру збереженою?', parent=self.root):
                return
            try:
                loaded = Game.load(save_path)
                self.game = loaded
                self.perk_prompted = -1
                self.game.log('Збереження завантажено.')
                self.refresh()
            except (OSError, ValueError, KeyError, TypeError) as exc:
                messagebox.showerror('Не вдалося завантажити', str(exc), parent=self.root)

        def new(self):
            if messagebox.askyesno('Нова гра', 'Почати нову гру? Незбережений прогрес буде втрачено.', parent=self.root):
                self.game = Game()
                self.perk_prompted = -1
                self.refresh()

        def close(self):
            answer = messagebox.askyesnocancel('Afterdays', 'Зберегти гру перед виходом?', parent=self.root)
            if answer is None:
                return
            if answer:
                try:
                    self.game.save(save_path)
                except OSError as exc:
                    messagebox.showerror('Не вдалося зберегти', str(exc), parent=self.root)
                    return
            self.root.destroy()

        def help(self):
            messagebox.showinfo('Afterdays · Керування',
                'НОВЕ У v0.5\n25 HP на старті; +5 за рівень. Аптечка: 50% максимуму.\n'
                'Технік: модулі з матеріалів, ремонт до 25/50/100%.\n'
                'Радіопротектор: 10 ходів захисту. Мапу приховує туман.\n'
                'Перки кожні 2 рівні. Tab у бою без витрати ОД.\n'
                'Міста: сховище й ілюстровані розділи. Квести оновлюються кожні 100 ходів.\n'
                'Водойми й скелі непрохідні. Радіація завдає шкоди.\n\n'
                'СПОРЯДЖЕННЯ\nНабої продає коваль; стеки й торгівля підтримують кількість.\n'
                'Техніки ремонтують; корпуси можна розбирати. Перки: кожен 2-й рівень.\n'
                'Далі від старту небезпечніше, спорядження обмежене вашим рівнем.\n\n'
                'ЕКІПІРОВКА\nI — екіпіровка з перетягуванням; J — завдання; M — атлас.\n'
                'Модулі перетягуються у слоти та назад у нижню панель.\n'
                'Мери дають завдання, мандрівні торговці — знижку 50%.\n\n'
                'ПОДОРОЖ\nWASD / стрілки або клік — один крок. E — обшук, I — інвентар.\n'
                'Кожні 8 переходів: консерви дають +10 HP; без їжі −5 HP.\n'
                'У містах є коваль, торговець, барига та ночівля.\n\n'
                'БІЙ\nБаза 6 ОД + перки. Рух: 1 ОД/клітинка; постріл: 2–4 ОД.\n'
                'Клік на ворога — стріляти. Перепони блокують постріли.\n'
                'Tab — інша зброя (безкоштовно). H — аптечка (2 ОД).\n'
                'Space — хід ворогів. Втеча: лівий край + 2 ОД.\n\n'
                'СПОРЯДЖЕННЯ\nВиберіть предмет в інвентарі → Модифікації.\n'
                'Бонуси модулів складаються. Вага екіпіровки входить у ліміт 35 кг.\n'
                'Після перемоги заберіть здобич перед переходом.\n\n'
                'F5 — зберегти; F9 — завантажити.\n'
                'Це sandbox-прототип: набої витрачаються, сюжетного фіналу немає.', parent=self.root)

    root = tk.Tk()
    app = App(root)
    if test_hook:
        root.after(100, lambda: test_hook(root, app))
    root.mainloop()


if __name__ == '__main__':
    try:
        launch()
    except ImportError:
        print('Потрібен Tkinter. Windows: перевстановіть Python з компонентом Tcl/Tk. Linux: установіть python3-tk.')
        sys.exit(1)
