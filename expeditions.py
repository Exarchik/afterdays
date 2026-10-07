import world_hex
import hexgrid
"""Field tests, cache searches, generator repairs and tracked elite hunts."""
import copy,math,json
from pathlib import Path
import afterdays as r
import contracts,content,economy,monster_rules
import progression as p
from i18n import t as tr

KINDS=('field_test','generator','cache','elite_hunt')
economy.BASE_REWARDS.update(field_test=95,generator=100,cache=85,elite_hunt=150)

def toggle_cells(board,index):
    result=list(board);x,y=index%3,index//3
    for xx,yy in ((x,y),(x-1,y),(x+1,y),(x,y-1),(x,y+1)):
        if 0<=xx<3 and 0<=yy<3:result[yy*3+xx]=1-result[yy*3+xx]
    return result

class Game(contracts.Game):
    def start_battle(self):
        """Створює бойовий стан, ворогів та арену поточної зустрічі."""
        super().start_battle()
        for n,old in enumerate(self.battle['enemies']):
            kind=monster_rules.choose(self.rng,self.region_level)
            self.battle['enemies'][n]=monster_rules.make(self.rng,kind,self.region_level,old['pos'])

    def monster_killed(self,enemy,xp,weapon):
        # Independent fractional points at each nearby location: never cascade to neighbours.
        """Обробляє смерть ворога, досвід і квестовий прогрес."""
        earned=xp/(40*max(1,self.region_level))
        positions=set(map(tuple,self.cities))|{tuple(s['pos']) for s in self.special_sites}
        for pos in positions:
            if world_hex.distance(pos,(self.x,self.y))>10:continue
            record=self.record_at(pos);total=record.get('combat_fraction',0)+earned
            gain=math.floor(total+1e-9);record['combat_fraction']=max(0,total-gain)
            record['value']=min(100,record['value']+gain)
        self.schedule_thanks();self.check_border_quest()
        if weapon and weapon.get('field_test'):
            q=next((q for q in self.quests if q['id']==weapon.get('quest_id') and q['status']=='active'),None)
            if q:q['progress']=1;self.emit(tr('exp.test_done'),color='#9edba2')

    def test_armor_hit(self,damage):
        """Зараховує отриману шкоду для випробування квестового захисту."""
        if damage<=0:return
        for slot in ('armor','helmet'):
            item=self.equipped.get(slot)
            if not item or not item.get('field_test'):continue
            q=next((q for q in self.quests if q['id']==item.get('quest_id') and q['status']=='active'),None)
            if q:q['progress']=1;self.emit(tr('exp.test_done'),color='#9edba2')

    def _kill_objectives(self,kind):
        """Оновлює завдання на вбивство з перевіркою типу ворога і зони."""
        for q in self.quests:
            if q['status']=='active' and q['kind']=='hunt' and world_hex.distance((self.x,self.y),self.cities[q['city']])<=10 and monster_rules.base_level(kind)<=q.get('level',1) and (q['target_kind'] is None or content.monster_id(q['target_kind'])==content.monster_id(kind)):
                q['progress']=min(q['goal'],q['progress']+1)

    def constrain_targets(self,offers):
        """Обмежує квестові цілі допустимими рівнями монстрів."""
        for q in offers:
            if q['kind'] not in ('hunt','trophies'):continue
            if q.get('target_kind') is not None and monster_rules.base_level(q['target_kind'])>q.get('level',self.region_at(*self.cities[q['city']])):
                q['target_kind']=self.rng.choice(monster_rules.eligible(q.get('level',1),weak=False))
                q['target_type_id']=content.monster_id(q['target_kind'])
                if q['status']=='active':q['progress']=0
                if q['status']=='offered':self.price_quest(q)
        return offers

    def _raw_mayor_offers(self):
        """Формує набір кандидатів завдань до застосування обмежень репутації."""
        offers=super()._raw_mayor_offers()
        if self.city not in self.mayors:return offers
        self.constrain_targets(offers)
        for kind in KINDS:
            if any(q['kind']==kind for q in offers):continue
            q=dict(id=r.uid(),kind=kind,city=self.city,status='offered',title=tr('exp.'+kind),progress=0,goal=1,target_kind=None,pos=None,
                   unique=False,scaled=True,distance_scaled=True,cycle_named=True,zone=self.region_level,level=self.region_level)
            self.price_quest(q)
            if kind=='field_test':
                category=self.rng.choice(['weapon','armor','helmet'])
                pool=[k for k,v in r.GEAR.items() if v[0]==category and p.GEAR_MIN_LEVEL[k]<=q['level']]
                item=p.equipment(self.rng.choice(pool),rng=self.rng,level=q['level'])
                item.update(field_test=True,quest_id=q['id'],value=0,weight=0,modules=[],slots=0)
                q['test_item']=item
            if kind=='generator':q.update(material=self.rng.choice(['parts','fragments']),material_qty=self.rng.randint(3,7))
            if kind=='elite_hunt':q['target_kind']=self.rng.choice(monster_rules.eligible(q['level'],False));q['goal']=1
            offers.append(q)
        return offers

    # Повертає актуальний список доступних завдань квестодавця.
    def mayor_offers(self):return self.constrain_targets(super().mayor_offers())

    def quest_equipment(self,q):
        """Знаходить виданий квестовий предмет спорядження."""
        return next((i for i in self.bag+[i for i in self.equipped.values() if i] if i.get('quest_id')==q['id']),None)

    def accept_quest(self,ident):
        """Приймає завдання і створює його цілі та необхідні квестові предмети."""
        offer=next((q for q in self.mayor_offers() if q['id']==ident and q['status']=='offered'),None)
        if not offer or offer['kind'] not in KINDS:return super().accept_quest(ident)
        if sum(q['status']=='active' for q in self.quests)>=8:return False
        q=copy.deepcopy(offer);kind=q['kind']
        if kind=='field_test':
            if q['test_item']['level']>self.level:self.log(tr('exp.level_required',level=q['test_item']['level']));return False
        else:
            candidates=self.quest_locations(q)
            if kind=='cache':
                reachable=self.player_reachable_world(self.cities[q['city']]);minimum=3 if q['level']>=3 else 1
                candidates=[(x,y) for x,y in candidates if all(__import__('quest_limits').nearby(self,q,(xx,yy)) and (xx,yy) in reachable and [xx,yy] not in self.cities and minimum<=self.region_at(xx,yy)<=q['level']+1 for yy in range(y-1,y+2) for xx in range(x-1,x+2))]
            if not candidates:self.log(tr('exp.no_location'));return False
            q['pos']=list(self.rng.choice(candidates))
            if kind=='cache':
                x,y=q['pos'];q['area']=[x-1,y-1,x+1,y+1];q['cache_pos']=[self.rng.randint(x-1,x+1),self.rng.randint(y-1,y+1)];q['searched_cells']=[]
            elif kind=='generator':
                board=[1]*9
                for _ in range(6):board=toggle_cells(board,self.rng.randrange(9))
                if all(board):board=toggle_cells(board,4)
                q['generator_board']=board
            elif kind=='elite_hunt':
                # The fight must be at a location supporting the boss species.
                candidates=[pos for pos in candidates if self.region_at(*pos)>=monster_rules.base_level(q['target_kind'])]
                if len(candidates)<3:self.log(tr('exp.no_location'));return False
                q['track']=list(map(list,self.rng.sample(candidates,self.rng.choice([2,3]))));q['track_index']=0;q['pos']=q['track'][0][:]
        q['status']='active';offer['status']='accepted';offer['seen']=True;self.quests.append(q)
        if kind=='field_test':
            self.bag.append(copy.deepcopy(q['test_item']))
            if q['test_item']['kind']=='weapon':p.add_to(self.bag,p.ammunition(q['test_item']['ammo_type'],12))
        self.log(tr('exp.accepted',title=q['title']));return True

    def local_expedition(self):
        """Знаходить активне завдання з мінігрою на поточній клітинці."""
        if self.battle or self.road_event:return None
        for q in self.quests:
            if q['status']!='active' or q['kind'] not in ('generator','cache','elite_hunt') or self.quest_ready(q):continue
            if q['kind']=='cache':
                a,b,c,d=q['area']
                if a<=self.x<=c and b<=self.y<=d:return q
            elif q.get('pos')==[self.x,self.y]:return q
        return None

    def unlock_cache(self,ident,angle):
        """Обробляє результат відкриття замкненого сховку."""
        q=self.local_expedition()
        if self.battle or not q or q['id']!=ident or q['kind']!='cache' or q.get('lock_open') or [self.x,self.y]!=q['cache_pos'] or 'lock_target' not in q or self.count('parts')<1:return None
        if not isinstance(angle,(int,float)) or not math.isfinite(angle) or not 0<=angle<=180:return None
        if abs(angle-q['lock_target'])>12:
            self.consume('parts');self.log(tr('update024.lock_fail'));return False
        q['lock_open']=True
        self.bag.append(dict(id=r.uid(),type_id='quest_item',kind='quest',name=tr('exp.parcel'),quest_id=q['id'],weight=0,value=0,rarity=0))
        q['progress']=1
        item=p.supply('food',self.rng.randint(1,3)) if self.rng.random()<.5 else p.ammunition(self.rng.choice(list(p.AMMO)),self.rng.randint(3,8))
        p.add_to(self.loot,item)
        if self.rng.random()<.05:
            names=[k for k,v in r.GEAR.items() if v[0] in ('weapon','armor','helmet') and p.GEAR_MIN_LEVEL[k]<=q['level']]
            p.add_to(self.loot,p.equipment(self.rng.choice(names),self.rng.choice([0,1]),self.rng,q['level']))
        self.log(tr('exp.cache_found'));self.emit(tr('exp.cache_found'));return True

    def search(self):
        """Виконує пошук на місцевості та перевіряє квестові цілі."""
        q=self.local_expedition()
        if not q:return super().search()
        if q['kind']=='generator':self._generator_request=q['id'];return True
        if q['kind']=='cache':
            pos=[self.x,self.y]
            if pos in q['searched_cells']:
                if pos==q['cache_pos'] and not q.get('lock_open'):
                    if 'lock_target' not in q:q['lock_target']=self.rng.randint(15,165)
                    self._lock_request=q['id'];return True
                self.log(tr('exp.already_searched'));return False
            q['searched_cells'].append(pos);self.turn+=1;self.rad_turns=max(0,self.rad_turns-1)
            if pos!=q['cache_pos']:self.log(tr('exp.cache_empty'));return True
            q['lock_target']=self.rng.randint(15,165)
            self._lock_request=q['id'];self.log(tr('update024.lock_found'));return True
        if q['kind']=='elite_hunt':
            self.turn+=1;self.rad_turns=max(0,self.rad_turns-1)
            if q['track_index']<len(q['track'])-1:
                q['track_index']+=1;q['pos']=q['track'][q['track_index']][:];self.log(tr('exp.next_track'));return True
            self.start_battle();b=self.battle;needed=1+self.rng.randint(2,3)
            occupied={tuple(b['pos'])}|set(map(tuple,b['walls']))
            # All selected positions must be connected to the player.
            pool=[(x,y) for y in range(b['h']) for x in range(5,b['w']) if (x,y) not in occupied and hexgrid.path_to(tuple(b['pos']),(x,y),b['w'],b['h'],occupied-{tuple(b['pos'])})]
            if len(pool)<needed:self.battle=None;self.log(tr('exp.no_location'));return False
            positions=self.rng.sample(pool,needed);enemies=[]
            for n,pos in enumerate(positions):
                e=monster_rules.make(self.rng,q['target_kind'],self.region_level,pos,grade=('mythic' if q.get('unique') else 'rare') if n==0 else 'normal',weak=False if n==0 else self.rng.random()<.5)
                e['hunt_boss']=n==0;enemies.append(e)
            b['enemies']=enemies;b['elite_quest']=q['id'];self.quest_battle=q['id'];return True
        return False

    def generator_toggle(self,ident,index):
        """Перемикає рубильник, перевіряє порядок і застосовує наслідки помилки."""
        q=self.local_expedition()
        if not q or q['id']!=ident or q['kind']!='generator' or type(index)!=int or not 0<=index<9:return False
        q['generator_board']=toggle_cells(q['generator_board'],index);return True

    def repair_generator(self,ident):
        """Перевіряє завершення ремонту генератора та оновлює завдання."""
        q=self.local_expedition()
        if not q or q['id']!=ident or q['kind']!='generator':return False
        if not all(q['generator_board']):self.log(tr('exp.generator_unsolved'));return False
        if self.count(q['material'])<q['material_qty']:self.log(tr('exp.no_material'));return False
        self.consume(q['material'],q['material_qty']);self.turn+=1;self.rad_turns=max(0,self.rad_turns-1);q['progress']=1
        self.log(tr('exp.generator_done'));return True

    def quest_ready(self,q):
        """Перевіряє виконання всіх умов для здачі завдання."""
        if q['kind'] in ('field_test','cache'):
            return q['status']=='active' and q['progress']>=q['goal'] and bool(self.quest_equipment(q))
        return super().quest_ready(q)

    def clear_quest_items(self,ident):
        """Прибирає предмети, що належать завершеному або скасованому завданню."""
        for items in (self.bag,self.stash,self.loot):items[:]=[i for i in items if i.get('quest_id')!=ident]
        for slot,item in self.equipped.items():
            if item and item.get('quest_id')==ident:self.equipped[slot]=None
        if not self.equipped.get(self.active):
            self.active='weapon1' if self.equipped.get('weapon1') else 'weapon2'
        self.hp=min(self.hp,self.max_hp)

    def turn_in(self,ident):
        """Перевіряє умови здачі, видає нагороду й завершує завдання."""
        ok=super().turn_in(ident)
        if ok:self.clear_quest_items(ident)
        return ok

    def abandon_quest(self,ident):
        """Скасовує завдання, очищує його предмети та застосовує штраф."""
        ok=super().abandon_quest(ident)
        if ok:self.clear_quest_items(ident)
        return ok

    def buys_kind(self,item,merchant):
        """Перевіряє, чи приймає торговець цей предмет."""
        return False if item.get('quest_id') else super().buys_kind(item,merchant)
    def dismantle(self,ident):
        """Розбирає спорядження й повертає матеріали у сумку."""
        item=self.find(ident)
        return False if item and item.get('quest_id') else super().dismantle(ident)
    def drop_item(self,ident,qty=None):
        """Викидає дозволений предмет з інвентаря."""
        item=self.find(ident)
        return False if item and item.get('quest_id') else super().drop_item(ident,qty)
    def install(self,ident,mod_id):
        """Встановлює сумісний модуль у вільний слот спорядження."""
        item=self.find(ident)
        return False if item and item.get('quest_id') else super().install(ident,mod_id)
    def uninstall(self,ident,mod_id):
        """Знімає модуль і повертає його в інвентар."""
        item=self.find(ident)
        return False if item and item.get('quest_id') else super().uninstall(ident,mod_id)
    def put_module(self,ident,mod_id,slot_index):
        """Встановлює модуль у конкретний слот із заміною попереднього."""
        item=self.find(ident)
        return False if item and item.get('quest_id') else super().put_module(ident,mod_id,slot_index)

    def quest_item_views(self,q):
        """Повертає предмети для показу в описі завдання."""
        if q['kind']=='field_test':return [self.quest_equipment(q) or q['test_item']]
        if q['kind']=='generator':return [p.parts(q['material_qty']) if q['material']=='parts' else p.fragments(q['material_qty'])]
        if q['kind']=='cache':return [self.quest_equipment(q) or dict(name=tr('exp.parcel'),kind='quest',rarity=0)]
        return super().quest_item_views(q)

    def quest_text(self,q):
        """Формує опис цілі, прогресу й винагороди завдання."""
        if q['kind'] not in KINDS:return super().quest_text(q)
        kind=q['kind'];desc=tr('exp.desc_'+kind)
        if kind=='field_test':desc+='\n'+q['test_item']['name']+' · '+tr('exp.test_weapon' if q['test_item']['kind']=='weapon' else 'exp.test_armor')
        if kind=='generator':desc+='\n'+tr('exp.material',name=p.parts(1)['name'] if q['material']=='parts' else p.fragments(1)['name'],qty=q['material_qty'])
        if kind=='cache' and q.get('area'):desc+='\n'+tr('exp.area',x=q['area'][0],y=q['area'][1],xx=q['area'][2],yy=q['area'][3])
        if kind=='elite_hunt':desc+='\n'+content.name(content.monster_id(q['target_kind']))
        if kind!='cache' and q.get('pos'):desc+='\n'+tr('exp.point',x=q['pos'][0],y=q['pos'][1])
        return tr('exp.quest_text',title=q['title'],level=q['level'],desc=desc,progress=q['progress'],goal=q['goal'],city=self.city_name(q['city']),money=q['reward'],xp=q['xp_reward'])

    @classmethod
    def load(cls,path):
        """Завантажує збереження та застосовує міграції цієї версії."""
        game=super().load(path)
        if json.loads(Path(path).read_text(encoding='utf-8'))['version']<17:
            for offers in game.offers.values():
                for q in offers:q['seen']=True
        game.constrain_targets(game.quests+[q for offers in game.offers.values() for q in offers])
        # Existing trophies gain the new base price too, exactly once per model value.
        items=game.bag+game.stash+game.loot
        for entry in game.shops.values():items+=entry['items']+entry.get('rep_reserve',[])
        if game.traveler:items+=game.traveler.get('items',[])
        for item in items:
            if item['kind']=='trophy':item['value']=economy.trophy(item['monster_kind'])['value']
        return game
