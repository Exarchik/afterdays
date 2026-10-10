import world_hex
import hexgrid
from i18n import t as tr
"""v0.4 world encounters, combat feedback, damage profiles and shared storage."""
import content
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

DAMAGE_TYPES={'kinetic':(tr('adventure.0001'),'#e8c78c'),'piercing':(tr('adventure.0002'),'#d7e2bf'),
              'thermal':(tr('adventure.0003'),'#ff9160'),'energy':(tr('adventure.0004'),'#88e3d9'),
              'electric':(tr('adventure.0005'),'#bf9dff')}
WEAPON_DAMAGE = content.WEAPON_DAMAGE
# Positive values resist damage; negative values increase damage taken.
RESISTANCES = content.RESISTANCES
p.PERKS.update(tactician=(tr('adventure.0006'),tr('adventure.0007')),
               adrenaline=(tr('adventure.0008'),tr('adventure.0009')))
r.TERRAINS.update(water=('#254b59',tr('adventure.0010')),cliff=('#62635d',tr('adventure.0011')),site=('#537965',tr('adventure.0012')))
BLOCKED={'water','cliff'}
SITES=[(tr('adventure.0013'),tr('adventure.0014'),'quest'),(tr('adventure.0015'),tr('adventure.0016'),'merchant'),
       (tr('adventure.0017'),tr('adventure.0018'),'quest'),(tr('adventure.0019'),tr('adventure.0020'),'merchant'),
       (tr('adventure.0021'),tr('adventure.0022'),'quest'),(tr('adventure.0023'),tr('adventure.0024'),'merchant')]
SITES.extend([(tr('adventure.0051'),tr('adventure.0052'),'quest'),(tr('adventure.0053'),tr('adventure.0054'),'merchant'),(tr('adventure.0055'),tr('adventure.0056'),'quest'),(tr('adventure.0057'),tr('adventure.0058'),'merchant'),(tr('adventure.0059'),tr('adventure.0060'),'quest'),(tr('adventure.0061'),tr('adventure.0062'),'quest'),(tr('adventure.0063'),tr('adventure.0064'),'merchant'),(tr('adventure.0065'),tr('adventure.0066'),'merchant'),(tr('adventure.0067'),tr('adventure.0068'),'quest'),(tr('adventure.0069'),tr('adventure.0070'),'merchant')])

SITES.extend((tr('update024.site_'+str(n)),tr('update024.npc_'+str(n)), 'quest' if n%2==0 else 'merchant') for n in range(8))

# Compatibility views; all definitions and gameplay now come from one catalog.
import event_catalog
import event_runtime
ROAD_EVENTS=[(e['id'],e['title'],e['description'],[(c['id'],c['text']) for c in e['choices']]) for e in event_catalog.EVENTS]
EXTRA_EVENTS={e['id']:(e['terrain'],e['title'],e['description'],[(c['id'],c['text']) for c in e['choices']]) for e in event_catalog.EVENTS if e.get('legacy_group') in ('terrain','cache')}
SIMPLE_EVENTS={e['id']:(e['title'],e['description'],e['choices'][0]['outcomes'][0]['effects'][0]['kind'],e['choices'][0]['outcomes'][0]['effects'][0]['amount']) for e in event_catalog.EVENTS if e.get('legacy_group')=='simple'}

def damage_type(item):return WEAPON_DAMAGE.get(item.get('type_id',item['name']),'kinetic')


def resistance_text(enemy):
    profile=enemy.get('resists',RESISTANCES.get(enemy['kind'],{}))
    return ' · '.join(f'{DAMAGE_TYPES[k][0]}: '+(tr('adventure.0136', v0=v) if v>0 else tr('adventure.0137', v0=-v)) for k,v in profile.items()) or tr('adventure.0138')


class Game(p.Game):
    def __init__(self,seed=None):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        super().__init__(seed)
        self.city_names=r.random.Random(repr(self.rng.getstate())).sample([content.t(key) for key in content.read('city_names.json')],len(self.cities))
        self.world_distance_remainder=0.0
        self.stash=[]
        self.offer_refresh={}
        self.road_event=None
        self.last_event_turn=-20
        self.radiation={}
        self.special_sites=[]
        self.trails=[]
        self._events=[]
        self._last_battle=None
        from world_layout import build
        self.cities,self.world=build(self.rng.getstate())
        self.city_names=r.random.Random(repr(self.rng.getstate())).sample([content.t(key) for key in content.read('city_names.json')],len(self.cities))
        self.city_merchants=[[0,1,2] if i==0 else [1]+([0] if i%3!=1 else [])+([2] if i%2==0 else []) for i in range(len(self.cities))]
        self.mayors.extend(i for i in range(12,len(self.cities)) if i%2==0)
        self.technicians.extend(i for i in range(12,len(self.cities)) if i%3==0)
        self._build_world()
        self.explored=[]
        self.known_cities=[0]
        self.map_rewards=[]
        self.rad_turns=0
        self.reveal(self.x,self.y,2)

    @property
    def main_city_count(self):
        """Кількість основних міст; старі індекси особливих локацій зберігаються."""
        ids=[s['city_id'] for s in getattr(self,'special_sites',[]) if s.get('city_id') is not None]
        return min(ids) if ids else len(self.cities)

    # Повертає назву міста з відповідними статусними позначками.
    def city_name(self,index):return self.city_names[index]

    # Перевіряє, чи перебуває гравець у звичайному місті.
    @property
    def regular_city(self):return self.city is not None and self.city<self.main_city_count

    @property
    def current_site(self):
        """Повертає поточну особливу локацію."""
        return next((s for s in self.special_sites if s['found'] and s['pos']==[self.x,self.y]),None)

    def merchant_title(self,m):
        """Повертає назву торговця для інтерфейсу."""
        site=self.current_site
        return site['npc'] if site and site['role']=='merchant' else r.MERCHANTS[m]

    # Обчислює кількість ще не витрачених виборів перків.
    @property
    def pending_perks(self):return max(0,self.level//2-sum(self.perks.values()))

    @property
    def max_ap(self):
        """Обчислює максимальний запас очок дії."""
        return 6+min(4,self.rank('tactician'))+(min(2,self.rank('adrenaline')) if self.hp<self.max_hp/2 else 0)

    def choose_perk(self,key):
        """Перевіряє доступність і вивчає черговий ранг перка."""
        before=self.max_ap
        ok=super().choose_perk(key)
        if ok and self.battle:
            change=max(0,self.max_ap-before)
            self.battle['ap']+=change
            self.battle['max_ap']=self.battle.get('max_ap',6)+change
        return ok

    def emit(self,text='',kind='text',pos=None,scene=None,color='#ecd598',source=None,entity=None):
        """Ставить коротке повідомлення або ефект у чергу відображення."""
        if not hasattr(self,'_events'):self._events=[]
        if kind=='text' and getattr(self,'_event_feedback_color',None):
            color=self._event_feedback_color
            self.log(text,color=color)
        scene=scene or ('battle' if self.battle else 'world')
        if pos is None:
            pos=self.battle['pos'] if self.battle else [self.x,self.y]
            entity='player'
        self._events.append(dict(text=text,kind=kind,pos=list(pos),scene=scene,color=color,
                                 source=list(source) if source else None,entity=entity))

    def emit_move(self,path,entity):
        """Додає подію руху для плавної анімації."""
        if len(path)<2:return
        self.emit(kind='move',pos=path[-1],source=path[0],entity=entity,scene='battle')
        self._events[-1]['path']=[list(pos) for pos in path]

    def pop_events(self):
        """Забирає накопичені візуальні події та очищує чергу."""
        events=self._events[:];self._events.clear();return events

    def _build_world(self):
        """Генерує місцевість, міста та пов’язані елементи світу."""
        for kind,count in [('water',8),('cliff',7)]:
            for _ in range(count):
                cx,cy=self.rng.randrange(2,len(self.world[0])-2),self.rng.randrange(2,30)
                rx,ry=self.rng.randint(1,5),self.rng.randint(1,4)
                for y in range(max(0,cy-ry),min(32,cy+ry+1)):
                    for x in range(max(0,cx-rx),min(len(self.world[0]),cx+rx+1)):
                        if ((x-cx)/rx)**2+((y-cy)/ry)**2<=1 and self.world[y][x] not in ('road','city') and world_hex.distance((x,y),(5,5))>2:
                            self.world[y][x]=kind
        reachable=self.reachable_world((5,5))
        self.build_radiation()
        self.add_sites()

    def build_radiation(self):
        """Розподіляє радіаційні поля за географічними правилами."""
        self.radiation={}
        for _ in range(10):
            cx=self.rng.choices(range(2,len(self.world[0])-2),weights=[x**2 for x in range(2,len(self.world[0])-2)])[0]
            cy=self.rng.choices(range(2,30),weights=[y**2 for y in range(2,30)])[0];radius=self.rng.randint(1,5)
            for y in range(max(0,cy-radius),min(32,cy+radius+1)):
                for x in range(max(0,cx-radius),min(len(self.world[0]),cx+radius+1)):
                    if not (x<len(self.world[0])//2 and y<16) and world_hex.distance((x,y),(cx,cy))<=radius and self.passable(x,y) and [x,y] not in self.cities and world_hex.distance((x,y),(5,5))>2:
                        self.radiation[f'{x},{y}']=self.rng.randint(2,4)

    def add_sites(self):
        """Розміщує особливі локації та під’єднує їх до доріг."""
        if self.special_sites:
            reachable=self.reachable_world((5,5));existing={s['name'] for s in self.special_sites}
            for name,npc,role in SITES[:16]:
                if name in existing:continue
                pool=[p for p in sorted(reachable) if 1<=p[0]<len(self.world[0])-1 and 1<=p[1]<len(self.world)-1 and self.world[p[1]][p[0]] not in ('city','road','site') and all(world_hex.distance(p,c)>2 for c in self.cities) and all(world_hex.distance(p,s['pos'])>=7 for s in self.special_sites)]
                if not pool:break
                pos=self.rng.choice(pool)
                self.special_sites.append(dict(id=r.uid(),name=name,npc=npc,role=role,pos=list(pos),found=False,city_id=None))
            return
        from site_layout import place
        for (name,npc,role),pos in zip(SITES,place(self,len(SITES))):
            self.special_sites.append(dict(id=r.uid(),name=name,npc=npc,role=role,pos=list(pos),found=False,city_id=None))

    # Перевіряє прохідність клітинки місцевості.
    def passable(self,x,y):return 0<=x<len(self.world[0]) and 0<=y<32 and self.world[y][x] not in BLOCKED

    def reachable_world(self,start):
        """Знаходить зв’язану область прохідних клітинок від заданого старту."""
        seen={tuple(start)};queue=deque(seen)
        while queue:
            for q in world_hex.neighbors(*queue.popleft(),len(self.world[0]),len(self.world)):
                if q not in seen and self.passable(*q):seen.add(q);queue.append(q)
        return seen

    def can_step(self,dx,dy):
        """Перевіряє допустимість одного переміщення гравця."""
        from journey import world_edge
        return not self.road_event and world_edge(self,(self.x,self.y),(self.x+dx,self.y+dy))

    def discover(self,site_id=None):
        """Відкриває найближчі локації й оновлює туман війни."""
        hidden=[s for s in self.special_sites if not s['found']]
        site=next((s for s in hidden if s['id']==site_id),None) if site_id else min(hidden,key=lambda s:world_hex.distance(s['pos'],(self.x,self.y)),default=None)
        if not site:return False
        site['found']=True;site['city_id']=len(self.cities)
        self.cities.append(site['pos'][:]);self.city_names.append(site['name'])
        self.city_merchants.append([0] if site['role']=='merchant' else [])
        if site['role']=='quest':self.mayors.append(site['city_id'])
        from site_layout import road_path
        route=road_path(self,site['pos'])
        self.trails=[list(p) for p in sorted(set(map(tuple,self.trails))|set(route)|{tuple(site['pos'])})]
        self.world[site['pos'][1]][site['pos'][0]]='site'
        self.reveal(*site['pos'],2)
        self.radiation.pop(f'{site["pos"][0]},{site["pos"][1]}',None)
        self.log(tr('adventure.0139', v0=site['name']))
        self.emit(tr('adventure.0140'),color='#92deb7')
        return True

    def step(self,dx,dy):
        """Виконує крок світом і запускає пов’язані з ходом події."""
        if self.battle:return self.battle_move((self.battle['pos'][0]+dx,self.battle['pos'][1]+dy))
        if not self.can_step(dx,dy):
            self.log(tr('adventure.0141') if self.road_event else tr('adventure.0142'))
            self.emit(tr('adventure.0143') if self.road_event else tr('adventure.0144'),color='#eea18b');return False
        self.x+=dx;self.y+=dy;self.traveler=None
        # Array diagonals can be ordinary hex edges: exactly one turn per cell.
        ticks=1
        self.world_distance_remainder=0.0
        self.reveal(self.x,self.y,2)
        for _ in range(ticks):
            if not self._world_time_tick():return True
        self._visit_objectives()
        for site in list(self.special_sites):
            if not site['found'] and world_hex.distance(site['pos'],(self.x,self.y))<=1:self.discover(site['id'])
        if self.city is not None:self.log(tr('adventure.0150', v0=self.city_name(self.city)));return True
        if getattr(self,'_guided_trip',False):return True
        terrain=self.world[self.y][self.x]
        for _ in range(ticks):
            if self.rng.random()<{'road':.06,'waste':.12,'forest':.20,'ruin':.24}.get(terrain,.1)*getattr(self,'encounter_multiplier',1):self.start_battle()
            elif self.turn-self.last_event_turn>=8 and self.rng.random()<.13:self.make_road_event()
            elif self.turn-self.last_traveler_turn>=7 and self.rng.random()<.09:self.spawn_traveler()
            if self.battle or self.road_event or self.traveler:break
        return True

    def _world_time_tick(self):
        """Оновлює залежні від часу ефекти та події світу."""
        self.turn+=1;self.travel_steps+=1
        if self.travel_steps%8==0:
            if self.consume('food'):
                before=self.hp;self.hp=min(self.max_hp,self.hp+10)
                self.emit(tr('adventure.0145', v0=self.hp - before),color='#9edba2')
                self.log(tr('adventure.0146'))
            elif not self.hurt_world(5,tr('adventure.0147')):return False
        radiation=self.radiation.get(f'{self.x},{self.y}',0)
        protected=self.rad_turns>0
        self.rad_turns=max(0,self.rad_turns-1)
        if radiation and protected:self.emit(tr('adventure.0148'),color='#b9e876')
        elif radiation and not self.hurt_world(radiation,tr('adventure.0149')):return False
        return True

    def hurt_world(self,damage,label=tr('adventure.0151')):
        """Наносить шкоду поза боєм і показує її причину."""
        if label==tr('adventure.0152'):damage=min(damage,max(0,self.hp-1))
        self.hp-=damage;self.emit(f'−{damage} HP',color='#ff927c')
        if not getattr(self,'_event_feedback_color',None):self.log(f'{label}: −{damage} HP.')
        if self.hp<=0:self.defeat();return False
        return True

    def use(self,kind):
        """Застосовує ефект розхідника і зменшує його кількість."""
        if kind=='rad':
            if not self.count('rad') or (self.battle and self.battle['ap']<2):return False
            self.consume('rad');self.rad_turns=10
            if self.battle:self.battle['ap']-=2
            self.emit(tr('adventure.0153'),color='#b9e876');return True
        before=self.hp
        if self.battle and self.battle['ap']<2:self.emit(tr('adventure.0154'),color='#ffcb79')
        ok=super().use(kind)
        if ok:self.emit(f'+{self.hp-before} HP',color='#9cdda8')
        return ok

    def _visit_objectives(self):
        """Оновлює завдання, пов’язані з відвідуванням поточної клітинки."""
        previous={q['id']:q['progress'] for q in self.quests}
        super()._visit_objectives()
        for q in self.quests:
            if q['progress']!=previous[q['id']]:self.emit(tr('adventure.0155'),color='#b3d794')

    def _kill_objectives(self,kind):
        """Оновлює завдання на вбивство з перевіркою типу ворога і зони."""
        previous={q['id']:q['progress'] for q in self.quests}
        super()._kill_objectives(kind)
        for q in self.quests:
            if q['progress']!=previous[q['id']]:self.emit(tr('adventure.0156', v0=q['progress'], v1=q['goal']),color='#c7a0f1')

    def gain_xp(self,amount):
        """Нараховує досвід і обробляє наслідки підвищення рівня."""
        if getattr(self,'coward_turns',0):amount=max(0,amount//2)
        self.xp+=amount;self.emit(f'+{amount} XP',color='#99c9ff')

    def make_road_event(self,key=None):
        """Create a terrain-filtered event from the shared catalog."""
        return event_runtime.make(self,key)

    def resolve_event(self,choice):
        """Apply the catalog's final rewards and penalties."""
        return event_runtime.resolve(self,choice)

    def stock(self,merchant):
        """Повертає або оновлює асортимент торговця."""
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
        """Перевіряє, чи приймає торговець цей предмет."""
        if self.current_site and self.current_site['role']=='merchant' and item['kind'] in ('food','med'):return True
        return super().buys_kind(item,merchant)

    def rest(self):
        """Відновлює гравця під час відпочинку в поселенні."""
        before=self.turn
        ok=super().rest() if self.regular_city else False
        self.rad_turns=max(0,self.rad_turns-(self.turn-before))
        return ok

    def stash_transfer(self,item_id,direction,qty=1):
        """Переміщує предмети між сумкою і сховищем із перевіркою обмежень."""
        if not self.can_access_stash:return False
        if direction not in ('deposit','withdraw'):return False
        source=self.bag if direction=='deposit' else self.stash
        item=next((i for i in source if i['id']==item_id),None)
        if not item or item['kind']=='quest' or not isinstance(qty,int) or not 1<=qty<=item.get('qty',1):return False
        preview=copy.deepcopy(item)
        if p.stack_key(preview):preview['qty']=qty
        if direction=='withdraw' and (self.weight+p.item_weight(preview)>self.capacity+.0001):
            self.log(tr('adventure.0167'));return False
        moved=p.extract(source,item,qty)
        p.add_to(self.stash if direction=='deposit' else self.bag,moved)
        self.log(tr('adventure.0168') if direction=='deposit' else tr('adventure.0169'))
        return True

    def mayor_offers(self):
        """Повертає актуальний список доступних завдань квестодавця."""
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
        variants={'hunt':[tr('adventure.0170'),tr('adventure.0171'),tr('adventure.0172')],
                  'retrieve':[tr('adventure.0173'),tr('adventure.0174'),tr('adventure.0175')],
                  'scout':[tr('adventure.0176'),tr('adventure.0177'),tr('adventure.0178')],
                  'supplies':[tr('adventure.0179'),tr('adventure.0180'),tr('adventure.0181')],
                  'purge':[tr('adventure.0182'),tr('adventure.0183'),tr('adventure.0184')]}
        for q in offers:
            if not q.get('cycle_named'):
                q['cycle_named']=True
                if not q.get('unique'):q['title']=self.rng.choice(variants[q['kind']])
        return offers

    def quest_locations(self,q):
        """Обирає допустимі клітинки для цілі завдання."""
        origin=tuple(self.cities[q['city']])
        ceiling=q.get('level',q.get('zone',self.region_at(*origin)))+1
        occupied={tuple(t['pos']) for t in self.quests if t.get('pos') and t['status']=='active' and t['id']!=q['id']}
        pool=[pos for pos in sorted(self.reachable_world(origin))
              if pos not in occupied and list(pos) not in self.cities and self.region_at(*pos)<=ceiling and __import__('quest_limits').nearby(self,q,pos)]
        nearby=[pos for pos in pool if 4<=abs(pos[0]-origin[0])+abs(pos[1]-origin[1])<=12]
        return nearby or pool

    def accept_quest(self,quest_id):
        """Приймає завдання і створює його цілі та необхідні квестові предмети."""
        ok=super().accept_quest(quest_id)
        if ok:self.emit(tr('adventure.0185'),color='#c7a0f1')
        return ok

    def quest_text(self,q):
        """Формує опис цілі, прогресу й винагороди завдання."""
        k=q['kind'];unique=q.get('unique',False)
        if k=='hunt':
            target=tr('adventure.0186') if q['target_kind'] is None else r.MONSTERS[q['target_kind']][0]
            desc=tr('adventure.0187', v0=target, v1=q['progress'], v2=q['goal'])
        elif k=='retrieve':desc=tr('adventure.0188')+(tr('adventure.0189') if unique else tr('adventure.0190'))+tr('adventure.0191')
        elif k=='scout':desc=tr('adventure.0192')
        elif k=='supplies':desc=tr('adventure.0193', v0=self.count('food'), v1=q.get('food_need', 5 if unique else 3), v2=self.count('med'), v3=q.get('med_need', 3 if unique else 2))
        else:desc=tr('adventure.0194')
        if q.get('pos'):desc+=tr('adventure.0195', v0=q['pos'][0], v1=q['pos'][1])
        state=tr('adventure.0196') if q['status']=='done' else tr('adventure.0197') if q['status']=='offered' else tr('adventure.0198') if self.quest_ready(q) else tr('adventure.0199')
        return (tr('adventure.0200') if unique else '')+tr('adventure.0201', v0=q['title'], v1=desc, v2=self.city_name(q['city']), v3=q['reward'], v4=80 if unique else 40, v5=state)

    def turn_in(self,quest_id):
        """Перевіряє умови здачі, видає нагороду й завершує завдання."""
        xp=self.xp
        ok=super().turn_in(quest_id)
        if ok:
            self.emit(tr('adventure.0202'),color='#c7a0f1');self.emit(f'+{self.xp-xp} XP',color='#99c9ff')
        return ok

    def search(self):
        """Виконує пошук на місцевості та перевіряє квестові цілі."""
        if self.road_event:self.log(tr('adventure.0205'));return False
        old={q['id']:q['progress'] for q in self.quests}
        before=self.turn
        ok=super().search()
        self.rad_turns=max(0,self.rad_turns-(self.turn-before))
        for q in self.quests:
            if q['progress']!=old[q['id']]:self.emit(tr('adventure.0206'),color='#c7a0f1')
        return ok

    def switch(self):
        """Перемикає активну руку зі зброєю."""
        other='weapon2' if self.active=='weapon1' else 'weapon1'
        if not self.equipped[other]:self.emit(tr('adventure.0207'));return False
        self.active=other;self.hp=min(self.hp,self.max_hp);self.emit(tr('adventure.0208'));return True

    def start_battle(self):
        """Створює бойовий стан, ворогів та арену поточної зустрічі."""
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
            if grade!='normal':e['name']=(tr('adventure.0209') if grade=='rare' else tr('adventure.0210'))+e['name']

    def battle_move(self,target):
        """Переміщує гравця по арені й витрачає необхідні ОД."""
        if not self.battle:return False
        ok=super().battle_move(target)
        if not ok:
            b=self.battle
            blocked=set(map(tuple,b['walls']))|{tuple(e['pos']) for e in b['enemies']}
            path=hexgrid.path_to(tuple(b['pos']),tuple(target),b['w'],b['h'],blocked)
            self.emit(tr('adventure.0211') if path and len(path)>b['ap'] else tr('adventure.0212'),color='#ffcb79')
        return ok

    def _finish_enemy(self,e,weapon=None):
        """Завершує смерть ворога й обробляє пов’язані нагороди."""
        b=self.battle
        if not b or e not in b['enemies']:return
        b.setdefault('corpses',[]).append(dict(pos=e['pos'][:],kind=e['kind'],type_id=content.monster_id(e),grade=e.get('grade','normal')))
        b.setdefault('kills',[]).append(dict(kind=e['kind'],type_id=content.monster_id(e),grade=e.get('grade','normal'),level=e.get('level',b.get('region_level',1))))
        b['enemies'].remove(e)
        earned=self.enemy_xp(e);self.gain_xp(earned)
        if hasattr(self,'monster_killed'):self.monster_killed(e,earned,weapon)
        self._kill_objectives(e['kind'])

    def shoot(self,enemy_id):
        """Перевіряє можливість пострілу та обробляє його наслідки."""
        b=self.battle;w=self.weapon
        if not b or not w:return False
        e=next((e for e in b['enemies'] if e['id']==enemy_id),None)
        if not e:return False
        reason=None
        valid,why,chance=self.shot_info(e)
        if w.get('durability',100)<=0:reason=tr('adventure.0213')
        elif not self.count('ammo',w.get('ammo_type','pistol')):reason=tr('adventure.0214')
        elif b['ap']<w['ap']:reason=tr('adventure.0215')
        elif not valid:reason=tr('adventure.0216')
        if reason:self.log(reason if not why else why);self.emit(reason,color='#ffcb79');return False
        b['ap']-=w['ap']
        saved=p.mr.chance(p.stats(w).get('ammo_save_percent',0))
        if saved and self.rng.random()*100<saved:self.emit(tr('modules.ammo_saved'),color='#9cdcd8')
        else:self.consume('ammo',1,w.get('ammo_type','pistol'))
        element=damage_type(w);color=DAMAGE_TYPES[element][1]
        self.emit(kind='attack',pos=e['pos'],source=b['pos'],color=color)
        if self.rng.randrange(100)<chance:
            s=p.stats(w);critical=self.rng.randrange(100)<min(65,5+s.get('crit',0))
            components=p.mr.shot_components(w,self.level,self.rng.randint(-2,2),element)
            dealt={}
            for kind,raw in components.items():
                base=balance.damage(raw*(1.6 if critical else 1),s.get('attack',0),e.get('defense',e.get('armor',0)))
                resist=e.get('resists',RESISTANCES.get(e['kind'],{})).get(kind,0)
                dealt[kind]=max(1,round(base*(1-resist/100)))
            amount=sum(dealt.values())
            e['hp']-=amount
            self.emit((tr('adventure.0217') if critical else '')+f'−{amount}',pos=e['pos'],color='#ffbf82' if critical else '#ff9d84')
            self.log(f'{e["name"]}: −{amount} HP ('+', '.join(f'{DAMAGE_TYPES[k][0]}: {v}' for k,v in dealt.items())+').')
            if e['hp']<=0:self._finish_enemy(e,w)
            if not b['enemies']:self.victory()
        else:self.emit(tr('adventure.0218'),color='#d7d4c0');self.log(tr('adventure.0219'))
        self.wear(w,.6)
        return True

    def end_turn(self):
        """Передає хід ворогам і відновлює ОД наступного ходу."""
        b=self.battle
        if not b:return
        if hasattr(self,'faction_turn'):return self.faction_turn()
        for e in list(b['enemies']):
            if b.get('dungeon') and not e.get('awake'):continue
            if content.MONSTER_DATA[content.monster_id(e)]['regen']:e['hp']=min(e['max_hp'],e['hp']+content.MONSTER_DATA[content.monster_id(e)]['regen'])
            motion=[e['pos'][:]]
            for _ in range(e['speed']):
                if hexgrid.distance(e['pos'],b['pos'])<=e['range'] and hexgrid.visible(tuple(e['pos']),tuple(b['pos']),b['walls']):break
                blocked=set(map(tuple,b['walls']))|{tuple(o['pos']) for o in b['enemies'] if o is not e}
                route=hexgrid.path_to(tuple(e['pos']),tuple(b['pos']),b['w'],b['h'],blocked)
                if route and route[0]!=tuple(b['pos']):
                    e['pos']=list(route[0]);motion.append(e['pos'][:])
            self.emit_move(motion,e['id'])
            if hexgrid.distance(e['pos'],b['pos'])<=e['range'] and hexgrid.visible(tuple(e['pos']),tuple(b['pos']),b['walls']):
                self.emit(kind='slash' if e['range']<=1 else 'attack',pos=b['pos'],source=e['pos'],color='#ff976f')
                if self.rng.randrange(100)<min(45,self.protection_stat('evasion')):
                    self.emit(tr('adventure.0220'),color='#b8dcb0');self.emit(tr('adventure.0221'),pos=e['pos'],color='#d7d4c0');continue
                damage=balance.damage(e['damage']+self.rng.randint(-2,2),e.get('attack',0),self.defense)
                reflected=p.mr.chance(self.protection_stat('reflect_percent'))
                if reflected and self.rng.random()*100<reflected:
                    self.emit(tr('modules.reflected'),color='#c7a8ff')
                    self.emit(kind='attack',pos=e['pos'],source=b['pos'],color='#c7a8ff')
                    e['hp']-=damage;self.emit(f'−{damage}',pos=e['pos'],color='#c7a8ff')
                    self.log(tr('modules.reflected_log',name=e['name'],damage=damage))
                    if e['hp']<=0:self._finish_enemy(e)
                    if not b['enemies']:self.victory();return
                    continue
                damage=self.incoming_combat_damage(damage) if hasattr(self,'incoming_combat_damage') else damage
                self.hp-=damage;self.emit(f'−{damage}',color='#ff8f79')
                if hasattr(self,'test_armor_hit'):self.test_armor_hit(damage)
                self.wear(self.equipped['armor'],.5);self.wear(self.equipped['helmet'],.25)
                self.log(f'{e["name"]}: −{damage} HP.')
                if self.hp<=0:self.defeat();return
        b['ap']=self.max_ap;b['max_ap']=self.max_ap;b['round']+=1
        self.log(tr('adventure.0222', v0=b['round']))

    def victory(self):
        """Завершує переможний бій і нараховує його результати."""
        if self.battle:self._last_battle=copy.deepcopy(self.battle)
        qid=self.quest_battle
        super().victory()
        if qid:self.emit(tr('adventure.0223'),color='#c7a0f1')

    def defeat(self):
        """Обробляє поразку гравця і завершує бойовий стан."""
        if self.battle:self._last_battle=copy.deepcopy(self.battle)
        super().defeat();self.road_event=None

    def save(self,path):
        """Записує стан гри у файл збереження."""
        content.migrate(self)
        data={k:v for k,v in vars(self).items() if k!='rng' and not k.startswith('_')}
        data.update(version=18,rng_state=self.rng.getstate())
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');os.replace(tmp,path)

    @classmethod
    def load(cls,path):
        """Завантажує збереження та застосовує міграції цієї версії."""
        data=json.loads(Path(path).read_text(encoding='utf-8'));version=data.get('version')
        if version not in (1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18):raise ValueError(tr('adventure.0224'))
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
                    x,y=pos;cx,cy=min(game.cities[:game.main_city_count],key=lambda c:world_hex.distance(c,pos))
                    while x!=cx:
                        x+=1 if cx>x else -1
                        if not game.passable(x,y):game.world[y][x]='waste'
                    while y!=cy:
                        y+=1 if cy>y else -1
                        if not game.passable(x,y):game.world[y][x]='waste'
            game.log(tr('adventure.0225'))
        else:
            data.pop('version');state=data.pop('rng_state')
            expected={k for k in vars(game) if k!='rng' and not k.startswith('_')}
            # Saves made before directional arena entry have no previous step.
            if 'last_world_entry' in expected:data.setdefault('last_world_entry',None)
            if version<16 and 'world_distance_remainder' not in data:expected.discard('world_distance_remainder')
            if version<13 and 'reputation_state' not in data:expected.discard('reputation_state')
            if version==4:expected-= {'explored','known_cities','map_rewards','rad_turns'}
            if 'message_colors' not in data:data['message_colors']=[None]*len(data.get('messages',[]))
            if set(data)!=expected:raise ValueError(tr('adventure.0226'))
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
            game.log(tr('adventure.0227'))
        remainder=game.world_distance_remainder
        if not isinstance(remainder,(int,float)) or not 0<=remainder<1:raise ValueError(tr('adventure.0226'))
        game.world_distance_remainder=0.0  # Retire legacy square-diagonal fractions.
        game._events=[];game._last_battle=None
        if game.battle:
            game.battle.setdefault('corpses',[]);game.battle.setdefault('max_ap',game.max_ap)
            for e in game.battle['enemies']:e.setdefault('resists',copy.deepcopy(RESISTANCES.get(e['kind'],{})))
        return game

    # Перевіряє, чи була клітинка відкрита гравцем.
    def revealed(self,x,y):return f'{x},{y}' in self.explored

    def reveal(self,x,y,radius=2):
        """Відкриває клітинки карти у заданій області."""
        known=set(self.explored)
        for yy in range(max(0,y-radius),min(32,y+radius+1)):
            for xx in range(max(0,x-radius),min(len(self.world[0]),x+radius+1)):
                if world_hex.distance((x,y),(xx,yy))<=radius:known.add(f'{xx},{yy}')
        self.explored=sorted(known)
        for n,pos in enumerate(self.cities):
            if self.revealed(*pos) and n not in self.known_cities:
                self.known_cities.append(n);self.emit(tr('adventure.0228'),color='#d8c38e')

    def enemy_xp(self,enemy):
        """Обчислює досвід за конкретного ворога."""
        _,hp,damage,reach,speed,armor,_=r.MONSTERS[content.monster_id(enemy)]
        base=round(hp*.35+damage*1.5+armor*2+reach+speed)
        level=enemy.get('level',1)
        multiplier={'normal':1,'rare':2,'mythic':5}.get(enemy.get('grade','normal'),1)
        gap=max(0,self.level-level-1)
        return max(1,max(2,round(base*(1+.25*(level-1))*multiplier*(.6**gap)))//2)

    def roll_item(self):
        """Генерує випадковий предмет за поточними правилами."""
        if self.rng.random()<.06:return p.supply('rad')
        item=super().roll_item()
        if item['kind'] in ('weapon','armor','helmet') and self.rng.random()<.08:
            count=1+(self.rng.random()<.04)
            pool=p.mr.eligible_modules(item)
            for _ in range(min(count,item['slots']) if pool else 0):
                item['modules'].append(p.module(self.rng.choices(range(item['rarity']+1),[65,24,8,2.5,.5][:item['rarity']+1])[0],self.rng,self.rng.choice(pool),item['level']))
        p.mr.clamp_condition(item)
        return item

    def craft_odds(self,amount):
        """Повертає розподіл рідкості модуля залежно від кількості матеріалів."""
        return [80,18,2,0,0] if amount<30 else [45,35,17,3,0] if amount<75 else [15,30,35,18,2] if amount<150 else [5,15,35,35,10]

    def craft_module(self,kind,amount):
        """Перевіряє ресурси, розігрує результат і створює модуль у техніка."""
        if self.battle or self.city not in self.technicians or kind not in ('parts','fragments') or not isinstance(amount,int) or amount<10 or self.count(kind)<amount:return False
        target='weapon' if kind=='parts' else 'protection'
        pool=[n for n,m in enumerate(r.MODULES) if m[1]==target]
        # All modules weigh the same; check space before consuming materials or RNG.
        if self.weight+.3>self.capacity:return False
        tier=self.rng.choices(range(5),self.craft_odds(amount))[0]
        item=p.module(tier,self.rng,self.rng.choice(pool),self.level)
        if self.weight+p.item_weight(item)>self.capacity:return False
        self.consume(kind,amount);p.add_to(self.bag,item)
        self.log(tr('adventure.0229')+item['name']+' · '+r.RARITIES[tier][0]);return True

    def price(self,item,merchant,buying=True):
        """Обчислює ціну купівлі або продажу предмета."""
        if item['kind']=='rad' and buying:return 2*super().price(p.supply('med'),merchant,True)
        return super().price(item,merchant,buying)
