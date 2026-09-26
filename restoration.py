"""Persistent torn-map puzzles and settlement recruitment contracts."""
import copy
import math
import afterdays as r
import cache_events
import economy
import progression as p
from i18n import t as tr
from journey import world_route

KINDS=('torn_map','recruit_smith','recruit_tech','recruit_mayor')
economy.BASE_REWARDS.update(torn_map=100,recruit_smith=90,recruit_tech=90,recruit_mayor=90)

class Game(cache_events.Game):
    def new_restoration_quest(self,kind,city):
        """Створює завдання відновлення або поселення фахівця."""
        level=self.region_at(*self.cities[city])
        q=dict(id=r.uid(),kind=kind,city=city,title=tr('restoration.'+kind),status='offered',
               progress=0,goal=2,pos=None,target_kind=None,unique=False,level=level,zone=level,
               scaled=True,distance_scaled=True,cycle_named=True)
        self.price_quest(q)
        return q

    def _raw_mayor_offers(self):
        """Формує набір кандидатів завдань до застосування обмежень репутації."""
        offers=super()._raw_mayor_offers()
        if self.city in self.mayors and not any(q['kind']=='torn_map' for q in offers):
            offers.append(self.new_restoration_quest('torn_map',self.city))
        return offers

    def map_quest(self,ident):
        """Знаходить активне завдання зі збирання розірваної мапи."""
        return next((q for q in self.quests if q['id']==ident and q['kind']=='torn_map' and q['status']=='active'),None)

    def quest_token(self,q,art):
        """Створює непокупний квестовий предмет із потрібною іконкою."""
        return dict(id=r.uid(),type_id='quest_item',kind='quest',quest_id=q['id'],art_id=art,
                    name=tr('restoration.'+art),rarity=1,weight=0,value=0)

    def accept_quest(self,ident):
        """Приймає завдання і створює його цілі та необхідні квестові предмети."""
        offer=next((q for q in self.mayor_offers() if q['id']==ident and q['status']=='offered'),None)
        if not offer or offer['kind']!='torn_map':return super().accept_quest(ident)
        if self.battle or sum(q['status']=='active' for q in self.quests)>=8:return False
        pool=self.quest_locations(offer)
        if not pool:return False
        q=copy.deepcopy(offer);layout=list(range(9))
        while layout==list(range(9)):self.rng.shuffle(layout)
        q.update(status='active',layout=layout,stash_pos=list(self.rng.choice(pool)),
                 contents=self.cache_contents('provisions',q['level']),map_solved=False)
        self.quests.append(q);offer.update(status='accepted',seen=True)
        self.bag.append(self.quest_token(q,'torn_map_item'))
        self.log(tr('restoration.map_received'));return True

    def swap_map_pieces(self,ident,a,b):
        """Міняє фрагменти пазла місцями й перевіряє завершення мапи."""
        q=self.map_quest(ident)
        if self.battle or self.road_event or not q or q['map_solved'] or any(type(v)!=int or not 0<=v<9 for v in (a,b)):return False
        q['layout'][a],q['layout'][b]=q['layout'][b],q['layout'][a]
        if q['layout']==list(range(9)):
            q.update(map_solved=True,progress=1,pos=q['stash_pos'][:])
            self.reveal(*q['pos'],1)
            route=world_route(self,q['pos'])
            self.trails=[list(pos) for pos in sorted(set(map(tuple,self.trails))|set(route))]
            for item in self.bag:
                if item.get('quest_id')==ident:item.update(art_id='restored_map_item',name=tr('restoration.restored_map_item'))
            self.log(tr('restoration.map_solved',x=q['pos'][0],y=q['pos'][1]))
        return True

    def search(self):
        """Виконує пошук на місцевості та перевіряє квестові цілі."""
        if not self.battle and not self.road_event:
            q=next((q for q in self.quests if q['kind']=='torn_map' and q['status']=='active' and q.get('map_solved') and q['progress']==1 and q['pos']==[self.x,self.y]),None)
            if q:
                self.turn+=1;self.rad_turns=max(0,self.rad_turns-1)
                for item in q['contents']:p.add_to(self.loot,item)
                q['contents']=[];q['progress']=2
                self.log(tr('restoration.cache_open'));return True
        return super().search()

    # Повертає збережений список мандрівних кандидатів на поселення.
    def settlers(self):return self.reputation_state.setdefault('settlers',[])

    def eligible_settlements(self,role,exclude=None):
        """Знаходить міста без потрібного фахівця, виключаючи зарезервовані."""
        reserved={n['city'] for n in self.settlers() if n['role']==role and n.get('city') is not None and n['state'] in ('permission','travelling') and n['id']!=exclude}
        return [i for i in range(min(12,len(self.cities))) if i not in reserved and
                (0 not in self.city_merchants[i] if role=='smith' else i not in self.mayors if role=='mayor' else i not in self.technicians)]

    def local_settlers(self):
        """Знаходить доступних для розмови кандидатів у поточній точці."""
        if self.battle or self.road_event:return []
        return [n for n in self.settlers() if n['pos']==[self.x,self.y] and n['state'] in ('offered','active','permission')]

    def create_settler(self,role):
        """Створює мандрівного кандидата на поселення та його завдання."""
        if role not in ('smith','tech','mayor') or not self.eligible_settlements(role) or any(n['role']==role and n['state']!='settled' for n in self.settlers()):return None
        city=min(range(12),key=lambda i:math.dist(self.cities[i],(self.x,self.y)))
        q=self.new_restoration_quest('recruit_'+role,city);q['pos']=[self.x,self.y];q['goal']=1
        n=dict(id=r.uid(),role=role,pos=[self.x,self.y],state='offered',city=None,quest=q)
        self.settlers().append(n)
        self._settler_notice=tr('restoration.encounter',name=tr('restoration.roamer_'+role),x=self.x,y=self.y)
        self.log(self._settler_notice)
        return n

    def spawn_traveler(self):
        """Обирає й створює випадкового мандрівника поблизу гравця."""
        roles=[role for role in ('smith','tech','mayor') if self.eligible_settlements(role) and not any(n['role']==role and n['state']!='settled' for n in self.settlers())]
        if roles and self.city is None and self.rng.random()<.25:
            self.create_settler(self.rng.choice(roles));self.last_traveler_turn=self.turn
        else:super().spawn_traveler()

    def recruit(self,ident):
        """Приймає завдання на пошук поселення для кандидата."""
        n=next((n for n in self.local_settlers() if n['id']==ident and n['state']=='offered'),None)
        if not n or not self.eligible_settlements(n['role']) or sum(q['status']=='active' for q in self.quests)>=8:return False
        q=copy.deepcopy(n['quest']);q.update(status='active',settler_id=ident)
        n['state']='active';self.quests.append(q);return True

    def settlement_requests(self):
        """Повертає завдання, для яких тут можна отримати дозвіл."""
        if self.battle or self.road_event or not self.regular_city:return []
        return [q for q in self.quests if q['kind'] in KINDS[1:] and q['status']=='active' and not q.get('settlement') and
                self.city in self.eligible_settlements(q['kind'][8:],q['settler_id'])]

    def authorize_settlement(self,ident):
        """Видає дозвіл і резервує місце фахівця у місті."""
        q=next((q for q in self.settlement_requests() if q['id']==ident),None)
        if not q:return False
        n=next(n for n in self.settlers() if n['id']==q['settler_id'])
        q.update(settlement=self.city+1,progress=1);n.update(city=self.city,state='permission')
        self.bag.append(self.quest_token(q,'settlement_permit'))
        self.log(tr('restoration.permission_received',city=self.city_name(self.city)));return True

    def process_settlers(self):
        """Поселяє кандидатів, для яких минув термін подорожі."""
        notices=[]
        for n in self.settlers():
            if n['state']!='travelling' or self.turn<n['arrival']:continue
            city=n['city']
            if n['role']=='smith':
                if 0 not in self.city_merchants[city]:self.city_merchants[city].append(0)
            elif n['role']=='mayor':
                if city not in self.mayors:self.mayors.append(city)
                self.offers.pop(str(city),None)
            elif city not in self.technicians:self.technicians.append(city)
            n['state']='settled'
            text=tr('update031.mayor_arrived',city=self.city_name(city)) if n['role']=='mayor' else tr('restoration.arrived',name=tr('restoration.roamer_'+n['role']),city=self.city_name(city))
            self.log(text);notices.append(text)
        if notices:self._settler_notice='\n'.join(notices)

    def available_merchant(self,m):
        """Перевіряє доступність вказаного торговця у поточній локації."""
        self.process_settlers();return super().available_merchant(m)

    def quest_return_pos(self,q):
        """Повертає координати місця здачі завдання."""
        if q['kind'] in KINDS[1:]:return q['pos']
        return super().quest_return_pos(q)

    def quest_ready(self,q):
        """Перевіряє виконання всіх умов для здачі завдання."""
        if q['kind'] in KINDS:
            return q['status']=='active' and q['progress']>=q['goal'] and any(i.get('quest_id')==q['id'] for i in self.bag)
        return super().quest_ready(q)

    def turn_in(self,ident):
        """Перевіряє умови здачі, видає нагороду й завершує завдання."""
        q=next((q for q in self.quests if q['id']==ident),None)
        if not q or q['kind'] not in KINDS[1:]:return super().turn_in(ident)
        if not self.can_turn_in(q) or self.road_event:return False
        if q['kind'] in KINDS[1:]:
            n=next(n for n in self.settlers() if n['id']==q['settler_id'])
            n.update(state='travelling',arrival=self.turn+self.rng.randint(10,15));q['arrival']=n['arrival']
        q['status']='done';self.money+=q['reward'];self.gain_xp(q['xp_reward'])
        self.give_quest_items(q);self.add_reputation(8 if q.get('unique') else 4,city=q['city'])
        self.clear_quest_items(ident);self.log(tr('restoration.completed',title=q['title']));return True

    def abandon_quest(self,ident):
        """Скасовує завдання, очищує його предмети та застосовує штраф."""
        q=next((q for q in self.quests if q['id']==ident),None)
        ok=super().abandon_quest(ident)
        if ok and q and q['kind'] in KINDS[1:]:
            n=next(n for n in self.settlers() if n['id']==q['settler_id']);n.update(state='offered',city=None)
            n['quest']=self.new_restoration_quest(q['kind'],q['city']);n['quest'].update(pos=n['pos'][:],goal=1)
        return ok

    def quest_item_views(self,q):
        """Повертає предмети для показу в описі завдання."""
        if q['kind'] in KINDS:
            return [next((i for i in self.bag if i.get('quest_id')==q['id']),self.quest_token(q,'torn_map_item' if q['kind']=='torn_map' else 'settlement_permit'))]
        items=super().quest_item_views(q)
        art='metro_component' if 'metro_city' in q else {'delivery':'courier_parcel','cache':'stash_parcel','retrieve':'relic_item','junkyard':'junk_component'}.get(q['kind'])
        if art:
            for item in items:
                if item.get('kind')=='quest' and not item.get('quest_repair'):item['art_id']=art
        return items

    def quest_text(self,q):
        """Формує опис цілі, прогресу й винагороди завдання."""
        if q['kind'] not in KINDS:return super().quest_text(q)
        desc=tr('restoration.desc_'+q['kind'])
        if q.get('pos'):desc+='\n'+tr('exp.point',x=q['pos'][0],y=q['pos'][1])
        if q.get('settlement'):desc+='\n'+tr('restoration.chosen_city',city=self.city_name(q['settlement']-1))
        if q.get('arrival'):desc+='\n'+tr('restoration.arrival_turn',turn=q['arrival'])
        return tr('exp.quest_text',title=q['title'],level=q['level'],desc=desc,progress=q['progress'],goal=q['goal'],city=self.city_name(q['city']),money=q['reward'],xp=q['xp_reward'])

    @classmethod
    def load(cls,path):
        """Завантажує збереження та застосовує міграції цієї версії."""
        game=super().load(path);game.process_settlers()
        for q in game.quests:game.quest_item_views(q)
        return game
