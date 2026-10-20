"""Maintenance, area contracts and persistent draggable junkyard searches."""
from game import catalog as game_catalog
from game import items as item_rules
import module_rules
import quest_area

import copy; import math
import junk_physics
import random
from game.systems import generator_balance

from game.systems import economy

from i18n import t as tr


def in_area(q,x,y):
    return quest_area.contains(q,x,y)

def contains(obj,x,y):return obj['x']<=x<=obj['x']+obj['w'] and obj['y']<=y<=obj['y']+obj['h']


class ScavengingMixin:
    def salvage_yield(self,item):
        # Item level and condition only: rarity, price, modules and perks cannot inflate it.
        """Обчислює кількість матеріалів, яку дасть розбір предмета."""
        level=max(1,int(item.get('level',1)))
        condition=module_rules.condition(item)/100
        return max(1,min(100,math.floor(min(100,level*5)*(.2+.8*condition))))

    def repair_with_kit(self,ident):
        """Витрачає ремкомплект і відновлює стан обраного спорядження."""
        item=self.find(ident)
        if self.battle or not item or not (item['kind'] in ('weapon','armor','helmet') or item.get('quest_repair')) or module_rules.condition(item)>=module_rules.max_condition(item) or self.count('repairkit')<1:return False
        self.consume('repairkit');item['durability']=min(module_rules.max_condition(item),module_rules.condition(item)+35)
        self.hp=min(self.hp,self.max_hp)
        self.log(tr('scav.repaired',name=item['name'],condition=round(item['durability'])));return True

    def buys_kind(self,item,merchant):
        """Перевіряє, чи приймає торговець цей предмет."""
        if item['kind']=='repairkit':return merchant in (0,1,2,3)
        return super().buys_kind(item,merchant)

    def stock(self,merchant):
        """Повертає або оновлює асортимент торговця."""
        items=super().stock(merchant)
        if not self.available_merchant(merchant) or merchant not in (0,2,3):return items
        entry=self.traveler if merchant==3 else next((v for v in self.shops.values() if v['items'] is items),None)
        if entry is not None and not entry.get('repairkit_stocked'):
            entry['repairkit_stocked']=True
            if merchant!=3 or self.rng.random()<.4:item_rules.add_to(items,item_rules.supply('repairkit',self.rng.randint(2,5)))
        return items

    def craft_failure(self,amount):
        """Обчислює ймовірність невдалого створення модуля за кількістю матеріалів."""
        if amount<=10:return .70
        if amount<75:return .70-(amount-10)*.45/65
        if amount<150:return .25-(amount-75)*.25/75
        return 0.0

    def craft_odds(self,amount):
        # Conditional rarity, given a successful craft; interpolate smoothly to 1000.
        """Повертає розподіл рідкості модуля залежно від кількості матеріалів."""
        points=[(10,[80,18,2,0,0]),(75,[15,30,35,18,2]),(150,[5,15,35,35,10]),(500,[0,5,20,45,30]),(1000,[0,0,10,40,50])]
        if amount<=10:return points[0][1]
        for (lo,a),(hi,b) in zip(points,points[1:]):
            if amount<=hi:return [x+(y-x)*(amount-lo)/(hi-lo) for x,y in zip(a,b)]
        return points[-1][1]

    def craft_module(self,kind,amount):
        """Перевіряє ресурси, розігрує результат і створює модуль у техніка."""
        self._craft_failed=False
        if self.battle or self.city not in self.technicians or kind not in ('parts','fragments') or type(amount)!=int or not 10<=amount<=1000 or self.count(kind)<amount:return False
        if self.weight>self.capacity:
            self.log(tr('update031.no_space'));return False
        state=self.rng.getstate()
        if self.rng.random()<self.craft_failure(amount):
            self.consume(kind,amount);self._craft_failed=True;self.log(tr('scav.craft_failed',amount=amount));return False
        pool=[n for n,m in enumerate(game_catalog.MODULES) if m[1]==('weapon' if kind=='parts' else 'protection')]
        tier=self.rng.choices(range(5),self.craft_odds(amount))[0]
        item=item_rules.module(tier,self.rng,self.rng.choice(pool),self.region_level)
        if self.weight+item_rules.item_weight(item)>self.capacity+.0001:
            self.rng.setstate(state);self.log(tr('update031.no_space'));return False
        self.consume(kind,amount);item_rules.add_to(self.bag,item)
        self.log(tr('adventure.0229')+item['name']+' · '+game_catalog.RARITIES[tier][0]);return True

    def _raw_mayor_offers(self):
        """Формує набір кандидатів завдань до застосування обмежень репутації."""
        offers=super()._raw_mayor_offers()
        if self.city in self.mayors and not any(q['kind']=='junkyard' for q in offers):
            q=dict(id=game_catalog.uid(),kind='junkyard',title=tr('scav.junkyard'),city=self.city,status='offered',progress=0,goal=3,pos=None,target_kind=None,
                   level=self.region_level,zone=self.region_level,unique=False,scaled=True,distance_scaled=True,cycle_named=True)
            q['goal']=self.junk_settings(q)['parts']
            self.price_quest(q);offers.append(q)
        return offers

    def mayor_offers(self):
        """Повертає актуальний список доступних завдань квестодавця."""
        offers=super().mayor_offers()
        for q in offers:
            if q['kind']=='scout' and q['status']=='offered':q['goal']=7
        return offers

    def area_candidates(self,q):
        """Знаходить допустимі ділянки для області квестового пошуку."""
        reachable=self.player_reachable_world(self.cities[q['city']]);minimum=3 if q['level']>=3 else 1
        def valid(pos):
            x,y=pos
            return all(__import__('quest_limits').nearby(self,q,(xx,yy)) and (xx,yy) in reachable and [xx,yy] not in self.cities and minimum<=self.region_at(xx,yy)<=q['level']+1 for xx,yy in quest_area.around((x,y)))
        nearby=[pos for pos in self.quest_locations(q) if valid(pos)]
        if nearby:return nearby
        occupied={tuple(t['pos']) for t in self.quests if t.get('pos') and t['status']=='active' and t['id']!=q['id']}
        return [pos for pos in sorted(reachable & self.reachable_world(tuple(self.cities[q['city']]))) if pos not in occupied and valid(pos)]

    def setup_area(self,q,candidates):
        """Призначає область пошуку та початковий стан її дослідження."""
        x,y=self.rng.choice(candidates);q.update(pos=[x,y],area=[x-1,y-1,x+1,y+1],searched_cells=[],visited_cells=[],area_shape='hex7')
        q['goal']=7 if q['kind']=='scout' else 1;q['progress']=0
        if q['kind']=='retrieve':q['relic_pos']=list(self.rng.choice(quest_area.around((x,y))))

    def generator_settings(self,q):
        """Balance settings from the quest's native profile (regular or elite) or defaults."""
        import quest_profiles
        spec=quest_profiles.profile(q) or quest_profiles.defaults('generator',bool(q.get('unique')))
        return generator_balance.settings_for(spec)

    def init_generator(self,q):
        """Готує рубильники з різною вагою та зелену зону датчика."""
        settings=self.generator_settings(q)
        weights,zone=generator_balance.generate(random.Random('generator:'+q['id']),settings)
        q.update(generator_weights=weights,generator_zone=zone,generator_on=[False]*len(weights),
                 generator_settings=settings,generator_version=generator_balance.VERSION)
        for key in ('generator_order','generator_input','generator_board'):q.pop(key,None)

    def ensure_generator(self,q):
        """Old saves (switch order or 3×3 board) get a balance board; a finished repair stays finished."""
        if q.get('generator_version')!=generator_balance.VERSION:self.init_generator(q)
        return q

    def junk_settings(self,q):
        """Pile settings from the quest's native profile (regular or elite) or defaults."""
        import quest_profiles
        spec=quest_profiles.profile(q) or quest_profiles.defaults('junkyard',bool(q.get('unique')))
        return junk_physics.settings_for(spec)

    def init_junkyard(self,q):
        """Builds the pile: quest parts and optional bonus finds under layered debris."""
        settings=q['junk_settings']=self.junk_settings(q)
        q['goal']=settings['parts'];q['progress']=0;q['junk_work']=0;q['junk_settles']=0
        junk_physics.next_settle(q,junk_physics.settle_rng(q))
        bonus=[]
        for _ in range(3):
            if self.rng.random()>=.5:continue
            bonus.append(dict(kind=self.rng.choice(['parts','fragments','ammo']),qty=self.rng.randint(2,6),ammo_type=self.rng.choice(list(game_catalog.AMMO))))
        junk_physics.build(q,['target']*q['goal'],bonus)

    def ensure_junkyard(self,q):
        """Old saves: dragging physics gets a new pile with only the missing parts; stamina gives way to satiety."""
        if 'work_per_satiety' not in q.get('junk_settings',{}):
            q['junk_settings']=self.junk_settings(q);q.pop('junk_stamina',None)
        if 'junk_settle_at' not in q:
            q.update(junk_work=0,junk_settles=0);junk_physics.next_settle(q,junk_physics.settle_rng(q))
        if q.get('junk_version')==junk_physics.VERSION:return
        junk_physics.build(q,['target']*max(0,q['goal']-q['progress']))

    def accept_quest(self,ident):
        """Приймає завдання і створює його цілі та необхідні квестові предмети."""
        offer=next((q for q in self.mayor_offers() if q['id']==ident and q['status']=='offered'),None)
        area=offer and offer['kind'] in ('scout','retrieve') and 'metro_city' not in offer
        if offer and (area or offer['kind']=='junkyard'):
            if sum(q['status']=='active' for q in self.quests)>=8:return False
            pool=self.area_candidates(offer) if area else self.quest_locations(offer)
            if not pool:self.log(tr('exp.no_location'));return False
            q=copy.deepcopy(offer)
            if area:self.setup_area(q,pool)
            else:q['pos']=list(self.rng.choice(pool));self.init_junkyard(q)
            q['status']='active';offer.update(status='accepted',seen=True);self.quests.append(q)
            self.log(tr('exp.accepted',title=q['title']));self._visit_objectives();return True
        ok=super().accept_quest(ident)
        if ok:
            q=next(q for q in self.quests if q['id']==ident)
            if q['kind']=='generator':self.init_generator(q)
        return ok

    def _visit_objectives(self):
        """Оновлює завдання, пов’язані з відвідуванням поточної клітинки."""
        super()._visit_objectives()
        for q in self.quests:
            if q['kind']=='scout' and q['status']=='active' and q.get('area') and in_area(q,self.x,self.y):
                pos=[self.x,self.y]
                if pos not in q['visited_cells']:
                    q['visited_cells'].append(pos);q['progress']=len(q['visited_cells']);self.emit(tr('scav.scout_progress',count=q['progress']))

    def local_expedition(self):
        """Знаходить активне завдання з мінігрою на поточній клітинці."""
        if not self.battle and not self.road_event:
            for q in self.quests:
                if q['status']!='active' or (self.quest_ready(q) and q['kind']!='junkyard'):continue
                if q['kind']=='retrieve' and q.get('area') and in_area(q,self.x,self.y):return q
                if q['kind']=='junkyard' and q.get('pos')==[self.x,self.y]:return q
        return super().local_expedition()

    def search(self):
        """Виконує пошук на місцевості та перевіряє квестові цілі."""
        q=self.local_expedition()
        if q and q['kind']=='junkyard':
            if not q.get('junk_opened'):
                q['junk_opened']=True;self.turn+=1;self.rad_turns=max(0,self.rad_turns-1)
            self._junkyard_request=q['id'];return True
        if q and q['kind']=='retrieve' and q.get('area'):
            pos=[self.x,self.y]
            if pos in q['searched_cells']:self.log(tr('exp.already_searched'));return False
            q['searched_cells'].append(pos);self.turn+=1;self.rad_turns=max(0,self.rad_turns-1)
            if pos==q['relic_pos']:
                self.bag.append(self.relic_item(q));q['progress']=1;self.emit(tr('scav.relic_found'));self.log(tr('scav.relic_found'))
            else:self.log(tr('exp.cache_empty'))
            return True
        return super().search()

    def relic_item(self,q):
        """Створює предмет реліквії для відповідного завдання."""
        return dict(id=game_catalog.uid(),type_id='quest_item',kind='quest',name=tr('scav.relic'),quest_id=q['id'],rarity=2,weight=0,value=0)

    def generator_quest(self,ident):
        q=self.local_expedition()
        if not q or q['id']!=ident or q['kind']!='generator' or q.get('progress'):return None
        return self.ensure_generator(q)

    def generator_toggle(self,ident,index):
        """Перемикає рубильник; перевантаження вибиває всі рубильники."""
        self._generator_overload=False
        q=self.generator_quest(ident)
        if not q or type(index)!=int or not 0<=index<len(q['generator_on']):return False
        q['generator_on'][index]=not q['generator_on'][index]
        if generator_balance.load(q)>generator_balance.RED:
            q['generator_on']=[False]*len(q['generator_on']);self._generator_overload=True
            self.log(tr('scav.generator_reset'))
        return True

    def repair_generator(self,ident):
        """Перевіряє, що навантаження в зеленій зоні, і списує матеріали."""
        q=self.generator_quest(ident)
        if not q:return False
        if not generator_balance.in_zone(q):self.log(tr('exp.generator_unsolved'));return False
        if self.count(q['material'])<q['material_qty']:self.log(tr('exp.no_material'));return False
        self.consume(q['material'],q['material_qty']);self.turn+=1;self.rad_turns=max(0,self.rad_turns-1);q['progress']=1
        self.log(tr('exp.generator_done'));return True

    def junk_quest(self,ident):
        """Повертає доступне завдання звалища за ідентифікатором."""
        q=self.local_expedition()
        if q and q['id']==ident and q['kind']=='junkyard':
            self.ensure_junkyard(q);return q
        return None

    def junk_capacity(self,q):
        """Weight the player can still lift before satiety runs out."""
        return max(0,self.hunger)*q['junk_settings']['work_per_satiety']-q['junk_work']

    def junk_remove(self,ident,piece_id):
        """Takes one free piece off the pile; its weight is paid for with satiety.

        Every `work_per_satiety` points of lifted weight cost one satiety point. Once enough
        weight has been removed the pile may settle (self._junk_settled describes it).
        """
        self._junk_settled=None
        q=self.junk_quest(ident)
        piece=next((p for p in junk_physics.live(q) if p['id']==piece_id),None) if q else None
        if not piece or junk_physics.blockers(q,piece):return False
        cost=junk_physics.MATERIALS[piece['material']][1]
        if cost>self.junk_capacity(q):return False
        piece['gone']=True;q['junk_work']+=cost
        per=q['junk_settings']['work_per_satiety'];spent=q['junk_work']//per
        if spent:
            q['junk_work']-=spent*per
            self.change_satiety(-spent)
        q['junk_since']+=cost
        if q['junk_since']>=q['junk_settle_at']:
            rng=junk_physics.settle_rng(q);q['junk_settles']+=1
            junk_physics.next_settle(q,rng)
            if rng.randrange(100)<q['junk_settings']['settle_chance']:
                new,between=junk_physics.settle(q,rng)
                covered=sum(1 for f in q['junk_finds'] if not f['found'] and junk_physics.overlap(junk_physics.octagon(f),junk_physics.corners(new)))
                self._junk_settled=dict(piece=new['id'],between=between,covered=covered)
        return True

    def junk_collect(self,ident,find_id):
        """Збирає відкриту знахідку і оновлює прогрес завдання."""
        q=self.junk_quest(ident)
        find=next((f for f in q['junk_finds'] if f['id']==find_id and not f['found']),None) if q else None
        if not find or not junk_physics.find_free(q,find):return False
        find['found']=True
        if find['kind']=='target':
            self.bag.append(dict(id=game_catalog.uid(),type_id='quest_item',kind='quest',name=tr('scav.junk_part'),quest_id=q['id'],rarity=0,weight=0,value=0))
            q['progress']+=1;self.emit(tr('scav.junk_progress',count=q['progress'],goal=q['goal']))
        else:
            item=item_rules.ammunition(find['ammo_type'],find['qty']) if find['kind']=='ammo' else item_rules.supply(find['kind'],find['qty'])
            item_rules.add_to(self.loot,item);self.log(tr('scav.bonus',name=item['name'],qty=item['qty']))
        return True

    def junk_foods(self):
        """Food the player can eat at the pile: backpack and provisions."""
        from game.systems.consumables import definition
        sources=list(self.bag)+list(getattr(self,'provisions',[]))
        return [i for i in sources if i['kind']=='food' and not i.get('quest_id') and i.get('qty',1)>0 and definition(i)['satiety']>0]

    def junk_food_gain(self,q,item):
        """Satiety the food would add right now (capped at full)."""
        from game.systems.consumables import definition
        return max(0,min(20-self.hunger,definition(item)['satiety']))

    def junk_eat(self,ident,item_id):
        """Eat one portion at the pile; returns the satiety gained."""
        q=self.junk_quest(ident)
        item=next((i for i in self.junk_foods() if i['id']==item_id),None) if q else None
        if not item:return 0
        gain=self.junk_food_gain(q,item)
        if gain<=0:return 0
        before=self.hunger
        source=self.bag if any(i is item for i in self.bag) else self.provisions
        if not self.apply_consumable(item,source=source,force=True):return 0
        return self.hunger-before

    def quest_ready(self,q):
        """Перевіряє виконання всіх умов для здачі завдання."""
        if q['kind']=='junkyard':return q['status']=='active' and q['progress']>=q['goal'] and sum(i.get('quest_id')==q['id'] for i in self.bag)>=q['goal']
        return super().quest_ready(q)

    def quest_item_views(self,q):
        """Повертає предмети для показу в описі завдання."""
        if q['kind']=='junkyard':return [dict(kind='quest',name=tr('scav.junk_part'),rarity=0,qty=q['goal'])]
        if q['kind']=='retrieve' and 'metro_city' not in q:return [self.quest_equipment(q) or self.relic_item(q)]
        return super().quest_item_views(q)

    def quest_text(self,q):
        """Формує опис цілі, прогресу й винагороди завдання."""
        if q['kind']=='junkyard' or (q['kind'] in ('scout','retrieve') and 'metro_city' not in q):
            desc=tr('scav.desc_'+q['kind'])
            if q.get('area'):desc+='\n'+tr('exp.area',x=q['area'][0],y=q['area'][1],xx=q['area'][2],yy=q['area'][3])
            elif q.get('pos'):desc+='\n'+tr('exp.point',x=q['pos'][0],y=q['pos'][1])
            return tr('exp.quest_text',title=q['title'],level=q['level'],desc=desc,progress=q['progress'],goal=7 if q['kind']=='scout' else q['goal'],city=self.city_name(q['city']),money=q['reward'],xp=q['xp_reward'])
        return super().quest_text(q)

    @classmethod
    def load(cls,path):
        """Завантажує збереження та застосовує міграції цієї версії."""
        game=super().load(path)
        for q in game.quests:
            if q['status']!='active':continue
            if q['kind']=='junkyard':game.ensure_junkyard(q)
            if q['kind']=='generator' and not q.get('progress'):game.ensure_generator(q)
            if q['kind'] in ('scout','retrieve') and 'metro_city' not in q and not q.get('area') and not game.quest_ready(q):
                pool=game.area_candidates(q)
                if pool:game.setup_area(q,pool)
        quest_area.migrate_game(game)
        return game
