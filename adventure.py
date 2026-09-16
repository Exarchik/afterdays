"""v0.4 world encounters, combat feedback, damage profiles and shared storage."""
import road_additions
import balance
import copy
import json
import math
import os
from pathlib import Path
from collections import deque
import afterdays as r
import progression as p

DAMAGE_TYPES={'kinetic':('Кінетична','#e8c78c'),'piercing':('Пробивна','#d7e2bf'),
              'thermal':('Термічна','#ff9160'),'energy':('Енергетична','#88e3d9'),
              'electric':('Електрична','#bf9dff')}
WEAPON_DAMAGE={'Арбалет «Тиша»':'piercing','Снайперська «Горизонт»':'piercing',
               'Гаус-карабін «Імпульс»':'electric','Іонний пістолет «Іскра»':'electric',
               'Плазмомет «Сонце»':'thermal','Лазер «Промінь»':'energy'}
# Positive values resist damage; negative values increase damage taken.
RESISTANCES={0:{'thermal':-30},1:{'piercing':-20},2:{'thermal':-50,'energy':20},
             3:{'electric':-25},4:{'kinetic':50,'piercing':-35,'thermal':20},
             5:{'kinetic':25,'thermal':-40},6:{'thermal':-25,'electric':15},
             7:{'kinetic':35,'electric':-65,'thermal':30},8:{'thermal':-60,'energy':30},
             9:{'kinetic':30,'piercing':-30},10:{'electric':70,'kinetic':-25},
             11:{'energy':-45,'piercing':20}}
p.PERKS.update(tactician=('Тактик','+1 максимальна ОД за ранг; до +4 ОД.'),
               adrenaline=('Адреналін','+1 ОД на початку раунду при HP нижче 50%; до +2 ОД.'))
r.TERRAINS.update(water=('#254b59','Водойма'),cliff=('#62635d','Скелі'),site=('#537965','Особлива локація'))
BLOCKED={'water','cliff'}
SITES=[('Обсерваторія «Луна»','Астроном','quest'),('Вагон №13','Торговець Рейка','merchant'),
       ('Стара насосна','Інженер Лев','quest'),('Бункер «Кедр»','Архіваріус','merchant'),
       ('Самотня радіовежа','Радистка Ніка','quest'),('Скляна оранжерея','Садівник','merchant')]
ROAD_EVENTS=[
    ('wounded','Поранений біля дороги','Під уламком дорожнього знака сидить поранений розвідник.',
     [('help','Дати аптечку → +40 XP, +60 кр.'),('leave','Побажати удачі й піти')]),
    ('wreck','Перекинутий караван','У кузові чути скрегіт. Усередині могли залишитись запчастини.',
     [('search','Обшукати: деталі або ризик травми'),('leave','Обійти караван')]),
    ('camp','Вогонь серед пустки','Мандрівники запрошують до вогнища. Поділіться вечерею.',
     [('rest','Витратити консерви → +25 HP, +15 XP'),('leave','Продовжити шлях')]),
    ('mines','Старе мінне поле','Ви помітили дріт під пилом. Можна обійти або ризикнути.',
     [('careful','Обережно обійти → +15 XP'),('rush','Ризикнути заради припасів'),('leave','Відступити від небезпечного місця')]),
    ('signal','Сигнал невідомої станції','Радіоприймач упіймав координати забутого об’єкта.',
     [('follow','Розшифрувати координати → відкрити локацію'),('leave','Не реагувати')]),
    ('pilgrims','Голодні пілігрими','Двоє мандрівників пропонують оплатити вашу їжу.',
     [('share','Віддати консерви → +70 кр.'),('talk','Поговорити → +10 XP'),('leave','Пройти повз')]),
]


SITES.extend([('Підземна друкарня','Друкар','quest'),('Затоплена станція','Водолаз','merchant'),('Купол метеорологів','Метеоролог','quest'),('Старий елеватор','Комірник','merchant'),('Польовий шпиталь','Лікарка','quest'),('Забутий радар','Зв’язківець','quest'),('Тунель караванників','Провідник','merchant'),('Сонячна ферма','Енергетик','merchant'),('Архів під мостом','Картограф','quest'),('Майстерня в кар’єрі','Майстер','merchant')])

# Location filters are applied before the event is selected.
EXTRA_EVENTS={
 'berries':('forest','Схованка в чагарнику','Між колючими отруйними кущами видніється ящик консервів.', [('gather','Дістати: їжа або отруєння'),('leave','Не чіпати')]),
 'snare':('forest','Звір у пастці','Невеликий звір б’ється в старому дроті.', [('free','Звільнити → +25 XP, ризик укусу'),('leave','Пройти повз')]),
 'hermit':('forest','Лісовий самітник','Самітник обмінює знання про місцевість на вечерю.', [('meal','Консерва → карта околиць, +30 XP'),('leave','Попрощатись')]),
 'safe':('ruin','Забутий сейф','Під завалами зберігся старий сейф.', [('open','10 запчастин → 60–120 кредитів'),('leave','Залишити')]),
 'pharmacy':('ruin','Рештки аптеки','У шафах можуть бути ліки, але стеля ненадійна.', [('search','Обшукати: ліки або травма'),('leave','Не ризикувати')]),
 'terminal':('ruin','Термінал архіву','На екрані блимає карта довоєнного району.', [('read','Прочитати → карта околиць, +35 XP'),('leave','Відійти')]),
 'courier':('road','Велосипед кур’єра','Кур’єр просить допомогти відремонтувати колесо.', [('fix','5 запчастин → +45 кр., +20 XP'),('leave','Відмовитись')]),
 'toll':('road','Самозвані митники','Озброєні люди вимагають 20 кредитів.', [('pay','Заплатити 20 кредитів → +15 XP'),('detour','Обійти через колючки → −3 HP, +20 XP'),('leave','Відступити')]),
 'storm':('waste','Пилова стіна','Піщана буря насувається на ваш маршрут.', [('shelter','Сховатись → +20 XP'),('rush','Рушити крізь бурю → −4 HP, +30 XP'),('leave','Зачекати осторонь')]),
 'meteor':('waste','Уламок із неба','Серед випаленої землі лежить гарячий метал.', [('collect','Дістати 15 фрагментів → −3 HP'),('study','Оглянути здалеку → +25 XP'),('leave','Оминути')]),
}
ROAD_EVENTS.extend((key,title,body,choices) for key,(_,title,body,choices) in EXTRA_EVENTS.items())


SIMPLE_EVENTS={
 'donation':('Подарунок каравану','Караванники залишили вам 60 кредитів.','money',60),
 'aidbox':('Пакунок допомоги','Ви знайшли дві запечатані аптечки.','med',2),
 'pantry':('Запаси під каменем','У схованці лежать три консерви.','food',3),
 'lesson':('Порада розвідника','Корисна розмова: +35 XP.','xp',35),
 'clean_cache':('Захищений контейнер','Знайдено дві пігулки від радіації.','rad',2),
 'toxic_air':('Отруйний пил','Вдихнули токсичний пил: −4 HP.','damage',4),
 'torn_pocket':('Дірка в кишені','Загублено до 30 кредитів.','money',-30),
 'sand_lock':('Пісок у механізмі','Активна зброя втратила 8 пунктів стану.','wear',8),
 'spoiled_can':('Зіпсована консерва','Довелося викинути одну консерву, якщо вона була.','food',-1),
 'sharp_wire':('Дріт у траві','Подряпина від іржавого дроту: −3 HP.','damage',3),
}
ROAD_EVENTS.extend((k,title,body,[('leave','Продовжити')]) for k,(title,body,_,_) in SIMPLE_EVENTS.items())

ROAD_EVENTS.extend((key,title,story,[('act',action),('leave','Пройти повз')]) for key,terrain,title,story,action,*rest in road_additions.EVENTS)

def damage_type(item):return WEAPON_DAMAGE.get(item['name'],'kinetic')


def resistance_text(enemy):
    profile=enemy.get('resists',RESISTANCES.get(enemy['kind'],{}))
    return ' · '.join(f'{DAMAGE_TYPES[k][0]}: '+(f'опір {v}%' if v>0 else f'вразливість +{-v}%') for k,v in profile.items()) or 'Природних опорів немає.'


class Game(p.Game):
    def __init__(self,seed=None):
        super().__init__(seed)
        self.city_names=list(r.CITY_NAMES)
        self.stash=[]
        self.offer_refresh={}
        self.road_event=None
        self.last_event_turn=-20
        self.radiation={}
        self.special_sites=[]
        self.trails=[]
        self._events=[]
        self._last_battle=None
        self._build_world()
        self.explored=[]
        self.known_cities=[0]
        self.map_rewards=[]
        self.rad_turns=0
        self.reveal(self.x,self.y,2)

    def city_name(self,index):return self.city_names[index]

    @property
    def regular_city(self):return self.city is not None and self.city<12

    @property
    def current_site(self):
        return next((s for s in self.special_sites if s['found'] and s['pos']==[self.x,self.y]),None)

    def merchant_title(self,m):
        site=self.current_site
        return site['npc'] if site and site['role']=='merchant' else r.MERCHANTS[m]

    @property
    def pending_perks(self):return max(0,self.level//2-sum(self.perks.values()))

    @property
    def max_ap(self):
        return 6+min(4,self.rank('tactician'))+(min(2,self.rank('adrenaline')) if self.hp<self.max_hp/2 else 0)

    def choose_perk(self,key):
        before=self.max_ap
        ok=super().choose_perk(key)
        if ok and self.battle:
            change=max(0,self.max_ap-before)
            self.battle['ap']+=change
            self.battle['max_ap']=self.battle.get('max_ap',6)+change
        return ok

    def emit(self,text='',kind='text',pos=None,scene=None,color='#ecd598',source=None,entity=None):
        if not hasattr(self,'_events'):self._events=[]
        scene=scene or ('battle' if self.battle else 'world')
        if pos is None:
            pos=self.battle['pos'] if self.battle else [self.x,self.y]
            entity='player'
        self._events.append(dict(text=text,kind=kind,pos=list(pos),scene=scene,color=color,
                                 source=list(source) if source else None,entity=entity))

    def emit_move(self,path,entity):
        if len(path)<2:return
        self.emit(kind='move',pos=path[-1],source=path[0],entity=entity,scene='battle')
        self._events[-1]['path']=[list(pos) for pos in path]

    def pop_events(self):
        events=self._events[:];self._events.clear();return events

    def _build_world(self):
        for kind,count in [('water',8),('cliff',7)]:
            for _ in range(count):
                cx,cy=self.rng.randrange(2,46),self.rng.randrange(2,30)
                rx,ry=self.rng.randint(1,5),self.rng.randint(1,4)
                for y in range(max(0,cy-ry),min(32,cy+ry+1)):
                    for x in range(max(0,cx-rx),min(48,cx+rx+1)):
                        if ((x-cx)/rx)**2+((y-cy)/ry)**2<=1 and self.world[y][x] not in ('road','city') and math.dist((x,y),(5,5))>2:
                            self.world[y][x]=kind
        reachable=self.reachable_world((5,5))
        self.build_radiation()
        self.add_sites()

    def build_radiation(self):
        self.radiation={}
        for _ in range(10):
            cx=self.rng.choices(range(2,46),weights=[x**2 for x in range(2,46)])[0]
            cy=self.rng.choices(range(2,30),weights=[y**2 for y in range(2,30)])[0];radius=self.rng.randint(1,5)
            for y in range(max(0,cy-radius),min(32,cy+radius+1)):
                for x in range(max(0,cx-radius),min(48,cx+radius+1)):
                    if not (x<24 and y<16) and math.dist((x,y),(cx,cy))<=radius and self.passable(x,y) and [x,y] not in self.cities and math.dist((x,y),(5,5))>2:
                        self.radiation[f'{x},{y}']=self.rng.randint(2,4)

    def add_sites(self):
        reachable=self.reachable_world((5,5));used=set(map(tuple,self.cities))|{tuple(s['pos']) for s in self.special_sites}
        existing={s['name'] for s in self.special_sites}
        for n,(name,npc,role) in enumerate(SITES):
            if name in existing:continue
            pool=[pos for pos in sorted(reachable) if pos not in used and self.world[pos[1]][pos[0]] not in ('road','city','site') and all(math.dist(pos,c)>2 for c in self.cities) and (3<=math.dist(pos,(5,5))<=6 if n==0 else True)]
            if not pool:continue
            pos=self.rng.choice(pool);used.add(pos)
            self.special_sites.append(dict(id=r.uid(),name=name,npc=npc,role=role,pos=list(pos),found=False,city_id=None))

    def passable(self,x,y):return 0<=x<48 and 0<=y<32 and self.world[y][x] not in BLOCKED

    def reachable_world(self,start):
        seen={tuple(start)};queue=deque(seen)
        while queue:
            for q in r.neighbors(*queue.popleft(),48,32):
                if q not in seen and self.passable(*q):seen.add(q);queue.append(q)
        return seen

    def can_step(self,dx,dy):
        return not self.road_event and abs(dx)+abs(dy)==1 and self.passable(self.x+dx,self.y+dy)

    def discover(self,site_id=None):
        hidden=[s for s in self.special_sites if not s['found']]
        site=next((s for s in hidden if s['id']==site_id),None) if site_id else min(hidden,key=lambda s:math.dist(s['pos'],(self.x,self.y)),default=None)
        if not site:return False
        site['found']=True;site['city_id']=len(self.cities)
        self.cities.append(site['pos'][:]);self.city_names.append(site['name'])
        self.city_merchants.append([0] if site['role']=='merchant' else [])
        if site['role']=='quest':self.mayors.append(site['city_id'])
        blocked={(x,y) for y in range(32) for x in range(48) if not self.passable(x,y)}
        paths=[r.path_to(tuple(site['pos']),tuple(city),48,32,blocked) for city in self.cities[:12]]
        route=min((path for path in paths if path),key=len,default=[])
        self.trails=[list(p) for p in sorted(set(map(tuple,self.trails))|set(route)|{tuple(site['pos'])})]
        self.world[site['pos'][1]][site['pos'][0]]='site'
        self.reveal(*site['pos'],2)
        self.radiation.pop(f'{site["pos"][0]},{site["pos"][1]}',None)
        self.log(f"Відкрито: {site['name']}. На мапі з’явилася стежка.")
        self.emit('Нова локація!',color='#92deb7')
        return True

    def step(self,dx,dy):
        if self.battle:return self.battle_move((self.battle['pos'][0]+dx,self.battle['pos'][1]+dy))
        if not self.can_step(dx,dy):
            self.log('Спочатку завершіть дорожню подію.' if self.road_event else 'Шлях перекритий водоймою, скелями або краєм мапи.')
            self.emit('Подія чекає' if self.road_event else 'Непрохідно',color='#eea18b');return False
        self.x+=dx;self.y+=dy;self.turn+=1;self.travel_steps+=1;self.traveler=None
        self.reveal(self.x,self.y,2)
        if self.travel_steps%8==0:
            if self.consume('food'):
                before=self.hp;self.hp=min(self.max_hp,self.hp+10)
                self.emit(f'Їжа −1 · +{self.hp-before} HP',color='#9edba2')
                self.log('Дорожній привал: витрачено консерви.')
            else:self.hurt_world(5,'Голод')
        radiation=self.radiation.get(f'{self.x},{self.y}',0)
        protected=self.rad_turns>0
        self.rad_turns=max(0,self.rad_turns-1)
        if radiation and protected:self.emit('☢ Захищено',color='#b9e876')
        elif radiation and not self.hurt_world(radiation,'Радіація'):return True
        self._visit_objectives()
        for site in list(self.special_sites):
            if not site['found'] and math.dist(site['pos'],(self.x,self.y))<=1.5:self.discover(site['id'])
        if self.city is not None:self.log(f'Прибуття: {self.city_name(self.city)}.');return True
        terrain=self.world[self.y][self.x]
        if self.rng.random()<{'road':.06,'waste':.12,'forest':.20,'ruin':.24}.get(terrain,.1):self.start_battle()
        elif self.turn-self.last_event_turn>=8 and self.rng.random()<.12:self.make_road_event()
        elif self.turn-self.last_traveler_turn>=7 and self.rng.random()<.09:self.spawn_traveler()
        return True

    def hurt_world(self,damage,label='Шкода'):
        if label=='Голод':damage=min(damage,max(0,self.hp-1))
        self.hp-=damage;self.emit(f'−{damage} HP',color='#ff927c')
        self.log(f'{label}: −{damage} HP.')
        if self.hp<=0:self.defeat();return False
        return True

    def use(self,kind):
        if kind=='rad':
            if not self.count('rad') or (self.battle and self.battle['ap']<2):return False
            self.consume('rad');self.rad_turns=10
            if self.battle:self.battle['ap']-=2
            self.emit('☢ Захист: 10 ходів',color='#b9e876');return True
        before=self.hp
        if self.battle and self.battle['ap']<2:self.emit('Мало ОД',color='#ffcb79')
        ok=super().use(kind)
        if ok:self.emit(f'+{self.hp-before} HP',color='#9cdda8')
        return ok

    def _visit_objectives(self):
        previous={q['id']:q['progress'] for q in self.quests}
        super()._visit_objectives()
        for q in self.quests:
            if q['progress']!=previous[q['id']]:self.emit('Розвідка ✓',color='#b3d794')

    def _kill_objectives(self,kind):
        previous={q['id']:q['progress'] for q in self.quests}
        super()._kill_objectives(kind)
        for q in self.quests:
            if q['progress']!=previous[q['id']]:self.emit(f'Ціль {q["progress"]}/{q["goal"]}',color='#c7a0f1')

    def gain_xp(self,amount):
        self.xp+=amount;self.emit(f'+{amount} XP',color='#99c9ff')

    def make_road_event(self,key=None):
        if self.battle or self.road_event:return False
        data=next((e for e in ROAD_EVENTS if e[0]==key),None) if key else self.rng.choice([e for e in ROAD_EVENTS if (e[0] not in EXTRA_EVENTS or EXTRA_EVENTS[e[0]][0]==self.world[self.y][self.x]) and (e[0] not in road_additions.BY_KEY or road_additions.BY_KEY[e[0]][1]==self.world[self.y][self.x])])
        if not data:return False
        name,title,body,choices=data
        self.road_event=dict(kind=name,title=title,body=body,choices=[list(c) for c in choices],pos=[self.x,self.y])
        self.last_event_turn=self.turn;self.log(title);return True

    def resolve_event(self,choice):
        event=self.road_event
        if not event or choice not in [c[0] for c in event['choices']]:return False
        kind=event['kind']
        if kind in road_additions.BY_KEY:return road_additions.resolve(self,choice)
        if kind in SIMPLE_EVENTS:
            self.road_event=None
            _,_,effect,value=SIMPLE_EVENTS[kind]
            if effect=='money':self.money=max(0,self.money+value);self.emit(f'{value:+} кр.')
            elif effect=='xp':self.gain_xp(value)
            elif effect=='damage':self.hurt_world(value,event['title'])
            elif effect=='wear':
                if self.weapon:self.wear(self.weapon,value)
            elif value<0:self.consume(effect,min(self.count(effect),-value))
            else:p.add_to(self.loot,p.supply(effect,value));self.emit('Припаси знайдено')
            return True
        if kind in EXTRA_EVENTS:return self.resolve_extra_event(kind,choice)
        required='med' if choice=='help' else 'food' if choice in ('rest','share') else None
        if required and not self.count(required):self.log('Немає потрібного припасу.');return False
        if required:self.consume(required)
        self.road_event=None
        if choice=='leave':self.emit('Далі в дорогу');return True
        if kind=='wounded':self.gain_xp(40);self.money+=60;self.emit('+60 кр.')
        elif kind=='wreck':
            if self.rng.random()<.7:p.add_to(self.bag,p.parts(self.rng.randint(12,35)));self.emit('Запчастини +',color='#d2cb9b')
            else:self.hurt_world(8,'Уламки')
        elif kind=='camp':
            old=self.hp;self.hp=min(self.max_hp,self.hp+25);self.emit(f'+{self.hp-old} HP',color='#9cdda8');self.gain_xp(15)
        elif kind=='mines':
            if choice=='careful':self.gain_xp(15)
            elif self.rng.random()<.5:self.hurt_world(self.rng.randint(6,14),'Міна')
            else:p.add_to(self.loot,p.supply('med',2));self.emit('Аптечки +2')
        elif kind=='signal':
            if not self.discover():self.gain_xp(20)
        elif kind=='pilgrims':
            if choice=='share':self.money+=70;self.emit('+70 кр.')
            else:self.gain_xp(10)
        return True

    def stock(self,merchant):
        site=self.current_site
        if site and site['role']=='merchant' and merchant==0 and not self.battle:
            key=f'site:{site["id"]}'
            entry=self.shops.get(key)
            if entry is None or entry.get('level')!=self.region_level or self.turn-entry['turn']>=100:
                items=[p.equipment(tier=3,rng=self.rng,level=self.region_level),p.module(4,self.rng,level=self.region_level),p.supply('food',8),p.supply('med',5)]
                self.shops[key]=entry=dict(level=self.region_level,turn=self.turn,items=items)
            return entry['items']
        return super().stock(merchant)

    def buys_kind(self,item,merchant):
        if self.current_site and self.current_site['role']=='merchant' and item['kind'] in ('food','med'):return True
        return super().buys_kind(item,merchant)

    def rest(self):
        before=self.turn
        ok=super().rest() if self.regular_city else False
        self.rad_turns=max(0,self.rad_turns-(self.turn-before))
        return ok

    def stash_transfer(self,item_id,direction,qty=1):
        if not self.regular_city or self.battle:return False
        if direction not in ('deposit','withdraw'):return False
        source=self.bag if direction=='deposit' else self.stash
        item=next((i for i in source if i['id']==item_id),None)
        if not item or item['kind']=='quest' or not isinstance(qty,int) or not 1<=qty<=item.get('qty',1):return False
        preview=copy.deepcopy(item)
        if p.stack_key(preview):preview['qty']=qty
        if direction=='withdraw' and (self.weight+p.item_weight(preview)>self.capacity+.0001 or item.get('level',1)>self.level):
            self.log('Не вміщується в рюкзак або зависокий рівень.');return False
        moved=p.extract(source,item,qty)
        p.add_to(self.stash if direction=='deposit' else self.bag,moved)
        self.log('Предмет перенесено до сховища.' if direction=='deposit' else 'Предмет забрано зі сховища.')
        return True

    def mayor_offers(self):
        if self.city not in self.mayors or self.battle:return []
        key=str(self.city)
        if key not in self.offer_refresh:self.offer_refresh[key]=self.turn
        if self.turn-self.offer_refresh[key]>=100:
            self.offers.pop(key,None);self.offer_refresh[key]=self.turn
        offers=super().mayor_offers()
        for q in offers:
            if q['status']=='offered' and not q.get('distance_scaled'):
                q['distance_scaled']=True;q['zone']=self.region_level
                q['reward']=round(q['reward']*(1+.25*(self.region_level-1)))
                if q['kind']=='hunt':q['goal']+=self.region_level-1
                if q['kind']=='supplies':
                    q['food_need']=(5 if q.get('unique') else 3)+(self.region_level-1)//2
                    q['med_need']=(3 if q.get('unique') else 2)+(self.region_level-1)//3
        variants={'hunt':['Зачистити околиці','Небезпека на дорозі','Захист каравану'],
                  'retrieve':['Загублений передавач','Сигнал довоєнного приладу','Пошук навігатора'],
                  'scout':['Дослідити сектор','Перевірка маршруту','Розвідати аномалію'],
                  'supplies':['Поповнити запаси','Допомога лікарні','Їжа для вартових'],
                  'purge':['Гніздо біля поселення','Лігво мутантів','Загроза з руїн']}
        for q in offers:
            if not q.get('cycle_named'):
                q['cycle_named']=True
                if not q.get('unique'):q['title']=self.rng.choice(variants[q['kind']])
        return offers

    def quest_locations(self,q):
        origin=tuple(self.cities[q['city']])
        ceiling=q.get('level',q.get('zone',self.region_at(*origin)))+1
        occupied={tuple(t['pos']) for t in self.quests if t.get('pos') and t['status']=='active' and t['id']!=q['id']}
        pool=[pos for pos in sorted(self.reachable_world(origin))
              if pos not in occupied and list(pos) not in self.cities and self.region_at(*pos)<=ceiling]
        nearby=[pos for pos in pool if 4<=abs(pos[0]-origin[0])+abs(pos[1]-origin[1])<=12]
        return nearby or pool

    def accept_quest(self,quest_id):
        ok=super().accept_quest(quest_id)
        if ok:self.emit('Завдання взято',color='#c7a0f1')
        return ok

    def quest_text(self,q):
        k=q['kind'];unique=q.get('unique',False)
        if k=='hunt':
            target='мутантів' if q['target_kind'] is None else r.MONSTERS[q['target_kind']][0]
            desc=f'Знищити {target}: {q["progress"]}/{q["goal"]} після взяття завдання.'
        elif k=='retrieve':desc='Знайти '+('чорну скриньку «Геліос».' if unique else 'довоєнний навігатор.')+' Дійдіть до позначки й натисніть E.'
        elif k=='scout':desc='Дійти до позначеної точки та повернутися з розвідданими.'
        elif k=='supplies':desc=f'Принести консерви {self.count("food")}/{q.get('food_need',5 if unique else 3)} та аптечки {self.count("med")}/{q.get('med_need',3 if unique else 2)}.'
        else:desc='Дійти до гнізда, натиснути E й виграти спеціальний бій.'
        if q.get('pos'):desc+=f'\nКоординати: {q["pos"][0]}, {q["pos"][1]}.'
        state='ВИКОНАНО' if q['status']=='done' else 'ДОСТУПНЕ' if q['status']=='offered' else 'ГОТОВО ДО ЗДАЧІ' if self.quest_ready(q) else 'У ПРОЦЕСІ'
        return ('★ УНІКАЛЬНЕ\n' if unique else '')+f'{q["title"]}\n{desc}\nЗамовник: {self.city_name(q["city"])}\nНагорода: {q["reward"]} кр. + {80 if unique else 40} XP\n{state}'

    def turn_in(self,quest_id):
        xp=self.xp
        ok=super().turn_in(quest_id)
        if ok:
            self.emit('Завдання ✓',color='#c7a0f1');self.emit(f'+{self.xp-xp} XP',color='#99c9ff')
            city=self.city
            if city is not None and city<12 and city not in self.map_rewards and sum(q['status']=='done' and q['city']==city for q in self.quests)>=3:
                self.map_rewards.append(city)
                nearby=sorted((n for n in range(12) if n not in self.known_cities),key=lambda n:math.dist(self.cities[n],self.cities[city]))[:3]
                for n in nearby:self.reveal(*self.cities[n],2)
                self.log('Мер передав карту найближчих міст: '+', '.join(self.city_name(n) for n in nearby))
                self.emit('Карта міст +',color='#a5dabc')
        return ok

    def search(self):
        if self.road_event:self.log('Спочатку завершіть дорожню подію.');return False
        old={q['id']:q['progress'] for q in self.quests}
        before=self.turn
        ok=super().search()
        self.rad_turns=max(0,self.rad_turns-(self.turn-before))
        for q in self.quests:
            if q['progress']!=old[q['id']]:self.emit('Предмет знайдено ✓',color='#c7a0f1')
        return ok

    def switch(self):
        other='weapon2' if self.active=='weapon1' else 'weapon1'
        if not self.equipped[other]:self.emit('Порожній слот');return False
        self.active=other;self.emit('Зброю змінено');return True

    def start_battle(self):
        super().start_battle()
        self.battle.update(ap=self.max_ap,max_ap=self.max_ap,corpses=[])
        for e in self.battle['enemies']:
            e['resists']=copy.deepcopy(RESISTANCES[e['kind']])
            grade=self.rng.choices(['normal','rare','mythic'],[91,8,1])[0]
            e['grade']=grade
            factor={'normal':1,'rare':1.5,'mythic':2.5}[grade]
            e['hp']=e['max_hp']=round(e['max_hp']*factor)
            e['damage']=round(e['damage']*({'normal':1,'rare':1.3,'mythic':1.8}[grade]))
            balance.set_monster(e)
            if grade!='normal':e['name']=('Рідкісний · ' if grade=='rare' else 'Міфічний · ')+e['name']

    def battle_move(self,target):
        if not self.battle:return False
        ok=super().battle_move(target)
        if not ok:
            b=self.battle
            blocked=set(map(tuple,b['walls']))|{tuple(e['pos']) for e in b['enemies']}
            path=r.path_to(tuple(b['pos']),tuple(target),b['w'],b['h'],blocked)
            self.emit('Мало ОД' if path and len(path)>b['ap'] else 'Немає шляху',color='#ffcb79')
        return ok

    def shoot(self,enemy_id):
        b=self.battle;w=self.weapon
        if not b or not w:return False
        e=next((e for e in b['enemies'] if e['id']==enemy_id),None)
        if not e:return False
        reason=None
        valid,why,chance=self.shot_info(e)
        if w.get('durability',100)<=0:reason='Зламана зброя'
        elif not self.count('ammo',w.get('ammo_type','pistol')):reason='Немає набоїв'
        elif b['ap']<w['ap']:reason='Мало ОД'
        elif not valid:reason='Немає пострілу'
        if reason:self.log(reason if not why else why);self.emit(reason,color='#ffcb79');return False
        b['ap']-=w['ap'];self.consume('ammo',1,w.get('ammo_type','pistol'))
        element=damage_type(w);color=DAMAGE_TYPES[element][1]
        self.emit(kind='attack',pos=e['pos'],source=b['pos'],color=color)
        if self.rng.randrange(100)<chance:
            s=p.stats(w);critical=self.rng.randrange(100)<min(65,5+s.get('crit',0))
            raw=s['damage']+(self.level-1)*2+self.rng.randint(-2,2)
            base=balance.damage(raw*(1.6 if critical else 1),s.get('attack',0),e.get('defense',e.get('armor',0)))
            resist=e.get('resists',RESISTANCES.get(e['kind'],{})).get(element,0)
            amount=max(1,round(base*(1-resist/100)))
            e['hp']-=amount
            self.emit(('КРИТ ' if critical else '')+f'−{amount}',pos=e['pos'],color='#ffbf82' if critical else '#ff9d84')
            self.log(f'{e["name"]}: −{amount} HP ({DAMAGE_TYPES[element][0]}).')
            if e['hp']<=0:
                b.setdefault('corpses',[]).append(dict(pos=e['pos'][:],kind=e['kind'],grade=e.get('grade','normal')))
                b.setdefault('kills',[]).append(dict(kind=e['kind'],grade=e.get('grade','normal')))
                b['enemies'].remove(e);self.gain_xp(self.enemy_xp(e));self._kill_objectives(e['kind'])
            if not b['enemies']:self.victory()
        else:self.emit('Промах',color='#d7d4c0');self.log('Промах.')
        self.wear(w,.6)
        return True

    def end_turn(self):
        b=self.battle
        if not b:return
        for e in b['enemies']:
            if b.get('dungeon') and not e.get('awake'):continue
            if e['kind']==8:e['hp']=min(e['max_hp'],e['hp']+3)
            motion=[e['pos'][:]]
            for _ in range(e['speed']):
                if math.dist(e['pos'],b['pos'])<=e['range'] and r.visible(tuple(e['pos']),tuple(b['pos']),b['walls']):break
                blocked=set(map(tuple,b['walls']))|{tuple(o['pos']) for o in b['enemies'] if o is not e}
                route=r.path_to(tuple(e['pos']),tuple(b['pos']),b['w'],b['h'],blocked)
                if route and route[0]!=tuple(b['pos']):
                    e['pos']=list(route[0]);motion.append(e['pos'][:])
            self.emit_move(motion,e['id'])
            if math.dist(e['pos'],b['pos'])<=e['range'] and r.visible(tuple(e['pos']),tuple(b['pos']),b['walls']):
                self.emit(kind='slash' if e['range']<=1 else 'attack',pos=b['pos'],source=e['pos'],color='#ff976f')
                if self.rng.randrange(100)<min(45,self.protection_stat('evasion')):
                    self.emit('Ухилення',color='#b8dcb0');self.emit('Промах',pos=e['pos'],color='#d7d4c0');continue
                damage=balance.damage(e['damage']+self.rng.randint(-2,2),e.get('attack',0),self.defense)
                self.hp-=damage;self.emit(f'−{damage}',color='#ff8f79')
                self.wear(self.equipped['armor'],.5);self.wear(self.equipped['helmet'],.25)
                self.log(f'{e["name"]}: −{damage} HP.')
                if self.hp<=0:self.defeat();return
        heal=min(self.max_hp-self.hp,self.protection_stat('regen'))
        self.hp+=heal
        if heal:self.emit(f'+{heal} HP',color='#9cdda8')
        b['ap']=self.max_ap;b['max_ap']=self.max_ap;b['round']+=1
        self.log(f'Раунд {b["round"]}. Ваш хід.')

    def victory(self):
        if self.battle:self._last_battle=copy.deepcopy(self.battle)
        qid=self.quest_battle
        super().victory()
        if qid:self.emit('Гніздо знищено ✓',color='#c7a0f1')

    def defeat(self):
        if self.battle:self._last_battle=copy.deepcopy(self.battle)
        super().defeat();self.road_event=None

    def save(self,path):
        data={k:v for k,v in vars(self).items() if k!='rng' and not k.startswith('_')}
        data.update(version=11,rng_state=self.rng.getstate())
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');os.replace(tmp,path)

    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'));version=data.get('version')
        if version not in (1,2,3,4,5,6,7,8,9,10,11):raise ValueError('Невідома версія збереження.')
        game=cls(0)
        if version<4:
            old=p.Game.load(path)
            game.__dict__.update(copy.deepcopy({k:v for k,v in vars(old).items() if k!='rng'}))
            game.rng.setstate(old.rng.getstate())
            game.city_names=list(r.CITY_NAMES);game.radiation={};game.special_sites=[];game.trails=[]
            game._build_world()
            # Existing quests and the player's position remain accessible after world migration.
            for pos in [[game.x,game.y]]+[q['pos'] for q in game.quests if q.get('pos') and q['status']=='active']:
                if not game.passable(*pos):game.world[pos[1]][pos[0]]='waste'
                # Carve a short connector only if the old position is isolated by new obstacles.
                if tuple(pos) not in game.reachable_world(tuple(game.cities[0])):
                    x,y=pos;cx,cy=min(game.cities[:12],key=lambda c:math.dist(c,pos))
                    while x!=cx:
                        x+=1 if cx>x else -1
                        if not game.passable(x,y):game.world[y][x]='waste'
                    while y!=cy:
                        y+=1 if cy>y else -1
                        if not game.passable(x,y):game.world[y][x]='waste'
            game.log('Оновлення v0.4: нові перки, рельєф і події. Старий прогрес збережено.')
        else:
            data.pop('version');state=data.pop('rng_state')
            expected={k for k in vars(game) if k!='rng' and not k.startswith('_')}
            if version==4:expected-= {'explored','known_cities','map_rewards','rad_turns'}
            if set(data)!=expected:raise ValueError('Неповне збереження.')
            game.__dict__.update(data)
            def tuples(v):return tuple(tuples(i) for i in v) if isinstance(v,list) else v
            game.rng.setstate(tuples(state))
        if version<5:
            game.explored=[];game.known_cities=[0];game.map_rewards=[];game.rad_turns=0
            game.reveal(*game.cities[0],2);game.reveal(game.x,game.y,2)
            oldmax=100+(game.level-1)*8+game.protection_stat('vitality')+game.rank('hardy')*10
            game.hp=max(1,min(game.max_hp,math.ceil(game.hp/oldmax*game.max_hp)))
            for entry in game.shops.values():entry['turn']=-1000
        if version<6:
            game.build_radiation();game.add_sites()
            game.offers={};game.offer_refresh={}
            game.log('Оновлення: небезпека за відстанню, нові локації та західні радіаційні поля.')
        game._events=[];game._last_battle=None
        if game.battle:
            game.battle.setdefault('corpses',[]);game.battle.setdefault('max_ap',game.max_ap)
            for e in game.battle['enemies']:e.setdefault('resists',copy.deepcopy(RESISTANCES.get(e['kind'],{})))
        return game

    def revealed(self,x,y):return f'{x},{y}' in self.explored

    def reveal(self,x,y,radius=2):
        known=set(self.explored)
        for yy in range(max(0,y-radius),min(32,y+radius+1)):
            for xx in range(max(0,x-radius),min(48,x+radius+1)):
                if math.dist((x,y),(xx,yy))<=radius:known.add(f'{xx},{yy}')
        self.explored=sorted(known)
        for n,pos in enumerate(self.cities):
            if self.revealed(*pos) and n not in self.known_cities:
                self.known_cities.append(n);self.emit('Місто відкрито',color='#d8c38e')

    def enemy_xp(self,enemy):
        _,hp,damage,reach,speed,armor,_=r.MONSTERS[enemy['kind']]
        base=round(hp*.35+damage*1.5+armor*2+reach+speed)
        level=enemy.get('level',1)
        multiplier={'normal':1,'rare':2,'mythic':5}.get(enemy.get('grade','normal'),1)
        gap=max(0,self.level-level-1)
        return max(2,round(base*(1+.25*(level-1))*multiplier*(.6**gap)))

    def roll_item(self):
        if self.rng.random()<.06:return p.supply('rad')
        item=super().roll_item()
        if item['kind'] in ('weapon','armor','helmet') and self.rng.random()<.08:
            count=1+(self.rng.random()<.04)
            pool=[n for n,m in enumerate(r.MODULES) if m[1]==('weapon' if item['kind']=='weapon' else 'protection')]
            for _ in range(min(count,item['slots'])):
                item['modules'].append(p.module(self.rng.choices(range(5),[65,24,8,2.5,.5])[0],self.rng,self.rng.choice(pool),item['level']))
        return item

    def craft_odds(self,amount):
        return [80,18,2,0,0] if amount<30 else [45,35,17,3,0] if amount<75 else [15,30,35,18,2] if amount<150 else [5,15,35,35,10]

    def craft_module(self,kind,amount):
        if self.battle or self.city not in self.technicians or kind not in ('parts','fragments') or not isinstance(amount,int) or amount<10 or self.count(kind)<amount:return False
        target='weapon' if kind=='parts' else 'protection'
        pool=[n for n,m in enumerate(r.MODULES) if m[1]==target]
        # All modules weigh the same; check space before consuming materials or RNG.
        if self.weight+.3>self.capacity:return False
        tier=self.rng.choices(range(5),self.craft_odds(amount))[0]
        item=p.module(tier,self.rng,self.rng.choice(pool),self.level)
        if self.weight+p.item_weight(item)>self.capacity:return False
        self.consume(kind,amount);p.add_to(self.bag,item)
        self.log('Створено: '+item['name']+' · '+r.RARITIES[tier][0]);return True

    def resolve_extra_event(self,kind,choice):
        cost={'meal':('food',1),'open':('parts',10),'fix':('parts',5)}.get(choice)
        if cost and self.count(cost[0])<cost[1]:self.log('Недостатньо припасів.');return False
        if choice=='pay' and self.money<20:self.log('Недостатньо кредитів.');return False
        if cost:self.consume(*cost)
        self.road_event=None
        if choice=='leave':return True
        if kind=='berries':
            if self.rng.random()<.75:p.add_to(self.loot,p.supply('food',2));self.emit('Консерви +2')
            else:self.hurt_world(4,'Отруйні ягоди')
        elif kind=='snare':
            self.gain_xp(25)
            if self.rng.random()<.25:self.hurt_world(3,'Укус')
        elif kind in ('hermit','terminal'):
            self.reveal(self.x,self.y,6);self.gain_xp(30 if kind=='hermit' else 35);self.emit('Мапу доповнено')
        elif kind=='safe':
            amount=self.rng.randint(60,120);self.money+=amount;self.emit(f'+{amount} кр.')
        elif kind=='pharmacy':
            if self.rng.random()<.8:p.add_to(self.loot,p.supply(self.rng.choice(['med','rad']),2));self.emit('Ліки знайдено')
            else:self.hurt_world(5,'Обвал')
        elif kind=='courier':self.money+=45;self.gain_xp(20);self.emit('+45 кр.')
        elif kind=='toll':
            if choice=='pay':self.money-=20;self.gain_xp(15)
            else:self.gain_xp(20);self.hurt_world(3,'Колючки')
        elif kind=='storm':
            self.gain_xp(20 if choice=='shelter' else 30)
            if choice=='rush':self.hurt_world(4,'Буря')
        elif kind=='meteor':
            if choice=='collect':p.add_to(self.bag,p.fragments(15));self.emit('Фрагменти +15');self.hurt_world(3,'Гарячий метал')
            else:self.gain_xp(25)
        return True

    def price(self,item,merchant,buying=True):
        if item['kind']=='rad' and buying:return 2*super().price(p.supply('med'),merchant,True)
        return super().price(item,merchant,buying)
