"""Foundational game state and world rules, independent of the application."""
from __future__ import annotations

import json
import math
import os
import random
from collections import deque
from pathlib import Path

import content
import hexgrid
from i18n import t as tr
from game.catalog import (CITY_NAMES, EXTRA_CITIES, GEAR, MAYORS, MODULES, MONSTERS,
                          QUEST_KINDS, QUEST_LABELS, RARITIES, SLOTS, neighbors, uid, visible)
from game.items import equipment, module, supply, stats, item_weight, item_value
from module_rules import compatible


class BaseGame:
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


class WorldGame(BaseGame):
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
        return self._change_gear(lambda: super(WorldGame, self).equip(item_id, slot))

    def unequip(self, slot):
        """Знімає предмет зі слота назад у сумку."""
        return self._change_gear(lambda: super(WorldGame, self).unequip(slot))

    def uninstall(self, item_id, mod_id):
        """Знімає модуль і повертає його в інвентар."""
        return self._change_gear(lambda: super(WorldGame, self).uninstall(item_id, mod_id))

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
