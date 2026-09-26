"""Local reputation, persistent shop shelves and quest boards."""
import math
import afterdays as r
import progression as p
import economy
from i18n import t as tr

GEAR = {'weapon', 'armor', 'helmet', 'module'}

def buy_factor(rep):
    return 1.3-.006*rep if rep <= 50 else 1-.004*(rep-50)

def sell_factor(rep):
    return .5+.01*rep if rep <= 50 else 1+.005*(rep-50)

def reward_factor(rep):
    return .7+.006*rep if rep <= 50 else 1+.02*(rep-50)

class Reputation:
    def init_reputation(self):
        """Створює початкові записи локальної репутації."""
        if not hasattr(self, 'reputation_state'):
            self.reputation_state = dict(locations={}, boards={}, thanks_due=None, coordinate_keys=True)

    def location_key(self, pos):
        """Перетворює координати локації на ключ запису репутації."""
        return f"loc:{pos[0]},{pos[1]}"

    def migrate_reputation_keys(self):
        """Оновлює старі ключі репутації до поточного формату."""
        self.init_reputation()
        if self.reputation_state.get('coordinate_keys'):return
        old=self.reputation_state['locations'];converted={}
        for key,record in old.items():
            if key.startswith('loc:'):converted[key]=record
            elif key.isdigit() and int(key)<len(self.cities):converted[self.location_key(self.cities[int(key)])]=record
        self.reputation_state['locations']=converted
        self.reputation_state['coordinate_keys']=True

    def record_at(self,pos):
        """Повертає або створює запис репутації за координатами."""
        self.migrate_reputation_keys()
        return self.reputation_state['locations'].setdefault(self.location_key(pos),dict(value=0,turnover=0))

    def local_record(self, city=None):
        """Повертає запис репутації для поточного місця."""
        city = self.city if city is None else city
        return self.record_at(self.cities[city]) if city is not None else None

    def reputation(self, city=None):
        """Повертає значення репутації у вибраній локації."""
        city=self.city if city is None else city
        if city is None:return 50
        self.migrate_reputation_keys()
        return self.reputation_state['locations'].get(self.location_key(self.cities[city]),{}).get('value',0)

    def add_reputation(self, amount=0, turnover=0, city=None):
        """Нараховує репутацію за ігрову дію."""
        city=self.city if city is None else city
        if city is None:return
        origin=self.cities[city];record=self.local_record(city)
        threshold=50*max(1,self.region_at(*origin))
        points,record['turnover']=divmod(record['turnover']+max(0,turnover),threshold)
        gain=max(0,amount)+points
        # Direct neighbours only. Hidden sites have stable coordinate-based records.
        positions=set(map(tuple,self.cities))|{tuple(s['pos']) for s in self.special_sites}
        for pos in positions:
            if math.dist(origin,pos)<=10:
                target=self.record_at(pos)
                target['value']=min(100,target['value']+gain)
        self.schedule_thanks()
        self.check_border_quest()

    def price(self, item, merchant, buying=True):
        """Обчислює ціну купівлі або продажу предмета."""
        city=self.trading_city(merchant)
        rep = self.reputation(city) if city is not None else 50
        # Hunters pay twice face value; their own retail price has a matching spread.
        def purchase(at_rep):
            if item['kind']=='rad':return 2*self.price(p.supply('med'),merchant,True)
            if merchant == 4 and item['kind'] == 'trophy':
                base = round(item['value']*4.6*(1-min(.30,.05*self.rank('trader'))))
            else:base = super(Reputation, self).price(item, merchant, True)
            return max(2, round(base*buy_factor(at_rep)))
        if buying:return purchase(rep)
        value = max(1, int(super().price(item, merchant, False)*sell_factor(rep)))
        return min(value, purchase(rep)-1)

    def buy(self, item_id, merchant, qty=1):
        """Перевіряє ціну й місткість та купує вибрану кількість товару."""
        money = self.money
        ok = super().buy(item_id, merchant, qty)
        if ok:self.add_reputation(turnover=money-self.money,city=self.trading_city(merchant))
        return ok

    def sell(self, item_id, merchant, qty=1):
        """Продає дозволений товар і нараховує гроші."""
        money = self.money
        ok = super().sell(item_id, merchant, qty)
        if ok:self.add_reputation(turnover=self.money-money,city=self.trading_city(merchant))
        return ok

    def repair(self, item_id, target=100):
        """Виконує платний ремонт до вибраного рівня стану."""
        money=self.money
        ok=super().repair(item_id,target)
        if ok:self.add_reputation(turnover=money-self.money)
        return ok

    def repair_cost(self, item, target=100):
        """Обчислює ціну ремонту предмета до вибраного стану."""
        cost = super().repair_cost(item, target)
        return max(1, math.ceil(cost*.5)) if cost and self.city is not None and self.reputation()>=50 else cost

    def stock(self, merchant):
        """Повертає або оновлює асортимент торговця."""
        rep = self.reputation()
        if merchant == 4:
            if self.city is None or rep < 50 or not self.available_merchant(4):return []
            key = f'reputation:hunter:{self.city}'
            entry = self.shops.get(key)
            if entry is None or self.turn-entry['turn']>=40:
                kinds = self.rng.sample(range(len(r.MONSTERS)), 3+(rep>=75)+(rep>=100))
                entry = dict(turn=self.turn, items=[economy.trophy(k,self.rng.randint(1,4)) for k in kinds])
                self.shops[key] = entry
            return entry['items']
        items = super().stock(merchant)
        if merchant==3 and self.traveler and self.traveler['pos']==[self.x,self.y]:
            entry=self.traveler;rep=self.reputation(self.trading_city(merchant))
        else:
            if self.city is None:return items
            entry = next((v for v in self.shops.values() if v['items'] is items), None)
        if entry is None:return items
        if 'rep_reserve' not in entry:
            gear = [i for i in items if i['kind'] in GEAR or i['kind']=='sealed']
            self.rng.shuffle(gear)
            entry['rep_reserve'] = gear[:]
            entry['rep_total'] = len(gear)
            entry['rep_released'] = 0
            items[:] = [i for i in items if i not in gear]
        fraction = .35+.65*rep/100
        target = math.ceil(entry['rep_total']*fraction)
        count = max(0, target-entry['rep_released'])
        reserve = entry['rep_reserve']
        items.extend(reserve[:count]);del reserve[:count]
        entry['rep_released'] += count
        return items

    def price_quest(self, q):
        """Розраховує винагороду завдання з урахуванням його рівня."""
        super().price_quest(q)
        q['base_reward'] = q['reward']
        q['reward'] = max(1,round(q['base_reward']*reward_factor(self.reputation(q['city']))))

    def mayor_offers(self):
        """Повертає актуальний список доступних завдань квестодавця."""
        if self.city not in self.mayors or self.battle:return []
        self.init_reputation()
        key = str(self.city)
        board = self.reputation_state['boards'].get(key)
        if board is None or self.turn-board['turn']>=100:
            self.offers.pop(key,None)
            self.offer_refresh[key] = self.turn
            pool = self._raw_mayor_offers()
            self.rng.shuffle(pool)
            # Unique metro repairs remain an explicit progression exception.
            pool.sort(key=lambda q:'metro_city' not in q)
            for q in pool:
                if 'metro_city' not in q:
                    q['unique'] = False
                    if q['kind'] in r.QUEST_LABELS:q['title'] = r.QUEST_LABELS[q['kind']]
                q['rep_elite_roll'] = self.rng.random()
                self.price_quest(q)
            board = dict(turn=self.turn, ids=[q['id'] for q in pool])
            self.reputation_state['boards'][key] = board
        pool = self.offers.get(key, [])
        rep = self.reputation()
        limit = 2+(rep>=25)+(rep>=50)+(rep>=75)
        elite_limit = 0 if rep<50 else 1 if rep<75 else 2
        visible = []
        elite_count = 0
        by_id = {q['id']:q for q in pool}
        for ident in board['ids'][:limit]:
            q = by_id.get(ident)
            if q is None:continue
            if 'metro_city' not in q:
                elite = elite_count < elite_limit and q['rep_elite_roll'] < .30
                if q['status']=='offered' and q.get('unique') != elite:
                    q['unique'] = elite
                    self.price_quest(q)
                if q.get('unique'):elite_count += 1
            if q['status']=='offered':
                q['reward'] = max(1,round(q['base_reward']*reward_factor(rep)))
            visible.append(q)
        return visible

    def turn_in(self, quest_id):
        """Перевіряє умови здачі, видає нагороду й завершує завдання."""
        q = next((q for q in self.quests if q['id']==quest_id),None)
        if q and q['kind']=='thanks':
            if self.battle or self.city!=q['city'] or not self.quest_ready(q):return False
            q['status']='done';self.money+=q['reward'];self.gain_xp(q['xp_reward'])
            self.give_quest_items(q)
            self.log(tr('reputation.received', city=self.city_name(q['city']), money=q['reward'], xp=q['xp_reward']))
            self.add_reputation(4,city=q['city'])
            return True
        ok = super().turn_in(quest_id)
        if ok:self.add_reputation(8 if q.get('unique') else 4,city=q['city'])
        return ok

    def quest_text(self, q):
        """Формує опис цілі, прогресу й винагороди завдання."""
        if q['kind']=='thanks':
            return tr('reputation.quest', city=self.city_name(q['city']), money=q['reward'], xp=q['xp_reward'])
        return super().quest_text(q)

    def schedule_thanks(self):
        """Планує одноразові подяки міст із достатньою репутацією."""
        self.init_reputation()
        eligible = [i for i in range(12) if self.reputation(i)>=75 and not self.local_record(i).get('thanks_issued') and not any(q['kind']=='thanks' and q['city']==i for q in self.quests)]
        if eligible and self.reputation_state['thanks_due'] is None:
            self.reputation_state['thanks_due'] = self.turn+self.rng.randint(60,100)
        return eligible

    def check_thanks(self):
        """Перевіряє появу квесту подяки від міста."""
        eligible = self.schedule_thanks()
        due = self.reputation_state['thanks_due']
        if not eligible or due is None or self.turn<due or self.battle:return
        eligible = [i for i in eligible if len(self.active_for(i))<self.quest_capacity(i) and not any(q['kind']=='thanks' and q['city']==i and q['status']=='active' for q in self.quests)]
        self.reputation_state['thanks_due'] = self.turn+self.rng.randint(60,100)
        if not eligible:return
        city=self.rng.choice(eligible);level=self.region_at(*self.cities[city])
        q=dict(id=r.uid(),kind='thanks',city=city,status='active',title=tr('reputation.title'),
               progress=1,goal=1,target_kind=None,pos=self.cities[city][:],unique=False,level=level,
               reward=round(100*level**1.3*reward_factor(self.reputation(city))),xp_reward=60+10*level)
        self.quests.append(q)
        self.local_record(city)['thanks_issued']=True
        notice=tr('reputation.notice',city=self.city_name(city))
        self.log(notice);self.emit(tr('reputation.title'),color='#a5dabc')
        self._reputation_notice=notice

    def step(self, dx, dy):
        """Виконує крок світом і запускає пов’язані з ходом події."""
        ok=super().step(dx,dy)
        if ok:self.check_thanks()
        return ok
