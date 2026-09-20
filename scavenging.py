"""Maintenance, area contracts and persistent draggable junkyard searches."""
import copy, math
import junk_physics
import afterdays as r
import expeditions, economy
import progression as p
from i18n import t as tr

economy.BASE_REWARDS['junkyard']=100


def in_area(q,x,y):
    a,b,c,d=q['area'];return a<=x<=c and b<=y<=d

def contains(obj,x,y):return obj['x']<=x<=obj['x']+obj['w'] and obj['y']<=y<=obj['y']+obj['h']

class Game(expeditions.Game):
    def salvage_yield(self,item):
        # Item level and condition only: rarity, price, modules and perks cannot inflate it.
        level=max(1,int(item.get('level',1)))
        condition=max(0,min(100,item.get('durability',100)))/100
        return max(1,min(100,math.floor(min(100,level*5)*(.2+.8*condition))))

    def repair_with_kit(self,ident):
        item=self.find(ident)
        if self.battle or not item or item['kind'] not in ('weapon','armor','helmet') or item.get('durability',100)>=100 or self.count('repairkit')<1:return False
        self.consume('repairkit');item['durability']=min(100,item.get('durability',0)+35)
        self.hp=min(self.hp,self.max_hp)
        self.log(tr('scav.repaired',name=item['name'],condition=round(item['durability'])));return True

    def buys_kind(self,item,merchant):
        if item['kind']=='repairkit':return merchant in (0,1,2,3)
        return super().buys_kind(item,merchant)

    def stock(self,merchant):
        items=super().stock(merchant)
        if not self.available_merchant(merchant) or merchant not in (0,2,3):return items
        entry=self.traveler if merchant==3 else next((v for v in self.shops.values() if v['items'] is items),None)
        if entry is not None and not entry.get('repairkit_stocked'):
            entry['repairkit_stocked']=True
            if merchant!=3 or self.rng.random()<.4:p.add_to(items,p.supply('repairkit',self.rng.randint(2,5)))
        return items

    def craft_failure(self,amount):
        if amount<=10:return .70
        if amount<75:return .70-(amount-10)*.45/65
        if amount<150:return .25-(amount-75)*.25/75
        return 0.0

    def craft_odds(self,amount):
        # Conditional rarity, given a successful craft; interpolate smoothly to 1000.
        points=[(10,[80,18,2,0,0]),(75,[15,30,35,18,2]),(150,[5,15,35,35,10]),(500,[0,5,20,45,30]),(1000,[0,0,10,40,50])]
        if amount<=10:return points[0][1]
        for (lo,a),(hi,b) in zip(points,points[1:]):
            if amount<=hi:return [x+(y-x)*(amount-lo)/(hi-lo) for x,y in zip(a,b)]
        return points[-1][1]

    def craft_module(self,kind,amount):
        self._craft_failed=False
        if self.battle or self.city not in self.technicians or kind not in ('parts','fragments') or type(amount)!=int or not 10<=amount<=1000 or self.count(kind)<amount or self.weight+.3>self.capacity:return False
        self.consume(kind,amount)
        if self.rng.random()<self.craft_failure(amount):
            self._craft_failed=True;self.log(tr('scav.craft_failed',amount=amount));return False
        pool=[n for n,m in enumerate(r.MODULES) if m[1]==('weapon' if kind=='parts' else 'protection')]
        tier=self.rng.choices(range(5),self.craft_odds(amount))[0]
        item=p.module(tier,self.rng,self.rng.choice(pool),self.level);p.add_to(self.bag,item)
        self.log(tr('adventure.0229')+item['name']+' · '+r.RARITIES[tier][0]);return True

    def _raw_mayor_offers(self):
        offers=super()._raw_mayor_offers()
        if self.city in self.mayors and not any(q['kind']=='junkyard' for q in offers):
            q=dict(id=r.uid(),kind='junkyard',title=tr('scav.junkyard'),city=self.city,status='offered',progress=0,goal=3,pos=None,target_kind=None,
                   level=self.region_level,zone=self.region_level,unique=False,scaled=True,distance_scaled=True,cycle_named=True)
            self.price_quest(q);offers.append(q)
        return offers

    def mayor_offers(self):
        offers=super().mayor_offers()
        for q in offers:
            if q['kind']=='scout' and q['status']=='offered':q['goal']=9
        return offers

    def area_candidates(self,q):
        reachable=self.player_reachable_world(self.cities[q['city']]);minimum=3 if q['level']>=3 else 1
        def valid(pos):
            x,y=pos
            return all((xx,yy) in reachable and [xx,yy] not in self.cities and minimum<=self.region_at(xx,yy)<=q['level']+1 for yy in range(y-1,y+2) for xx in range(x-1,x+2))
        nearby=[pos for pos in self.quest_locations(q) if valid(pos)]
        if nearby:return nearby
        occupied={tuple(t['pos']) for t in self.quests if t.get('pos') and t['status']=='active' and t['id']!=q['id']}
        return [pos for pos in sorted(reachable & self.reachable_world(tuple(self.cities[q['city']]))) if pos not in occupied and valid(pos)]

    def setup_area(self,q,candidates):
        x,y=self.rng.choice(candidates);q.update(pos=[x,y],area=[x-1,y-1,x+1,y+1],searched_cells=[],visited_cells=[])
        q['goal']=9 if q['kind']=='scout' else 1;q['progress']=0
        if q['kind']=='retrieve':q['relic_pos']=[self.rng.randint(x-1,x+1),self.rng.randint(y-1,y+1)]

    def init_generator(self,q):
        q['generator_order']=self.rng.sample(list(range(5)),5);q['generator_input']=[]
        q.pop('generator_board',None)

    def init_junkyard(self,q):
        # Rectangles are both the visible drawing and hit-test bounds; all debris can be moved.
        objects=[]
        for n in range(q['goal']):
            objects.append(dict(id='target'+str(n),kind='target',x=110+n*115,y=190+n%2*60,w=36,h=36,found=False))
        for n in range(3):
            if self.rng.random()>=.5:continue
            kind=self.rng.choice(['parts','fragments','ammo'])
            objects.append(dict(id='bonus'+str(n),kind=kind,x=130+n*145,y=320,w=32,h=32,found=False,
                                qty=self.rng.randint(2,6),ammo_type=self.rng.choice(list(p.AMMO))))
        for n in range(15):
            objects.append(dict(id='debris'+str(n),kind='debris',x=80+(n%5)*82+self.rng.randint(-10,10),y=150+(n//5)*70+self.rng.randint(-10,10),w=120,h=90,found=False,style=n%3))
        q['junk_objects']=objects
        junk_physics.ensure(q)

    def accept_quest(self,ident):
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
        super()._visit_objectives()
        for q in self.quests:
            if q['kind']=='scout' and q['status']=='active' and q.get('area') and in_area(q,self.x,self.y):
                pos=[self.x,self.y]
                if pos not in q['visited_cells']:
                    q['visited_cells'].append(pos);q['progress']=len(q['visited_cells']);self.emit(tr('scav.scout_progress',count=q['progress']))

    def local_expedition(self):
        if not self.battle and not self.road_event:
            for q in self.quests:
                if q['status']!='active' or (self.quest_ready(q) and q['kind']!='junkyard'):continue
                if q['kind']=='retrieve' and q.get('area') and in_area(q,self.x,self.y):return q
                if q['kind']=='junkyard' and q.get('pos')==[self.x,self.y]:return q
        return super().local_expedition()

    def search(self):
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
        return dict(id=r.uid(),type_id='quest_item',kind='quest',name=tr('scav.relic'),quest_id=q['id'],rarity=2,weight=0,value=0)

    def generator_toggle(self,ident,index):
        q=self.local_expedition()
        if not q or q['id']!=ident or q['kind']!='generator' or type(index)!=int or not 0<=index<5:return False
        entered=q['generator_input']
        if len(entered)==5:return False
        if index==q['generator_order'][len(entered)]:entered.append(index)
        else:q['generator_input']=[];self.log(tr('scav.generator_reset'))
        return True

    def repair_generator(self,ident):
        q=self.local_expedition()
        if not q or q['id']!=ident or q['kind']!='generator':return False
        if q['generator_input']!=q['generator_order']:self.log(tr('exp.generator_unsolved'));return False
        if self.count(q['material'])<q['material_qty']:self.log(tr('exp.no_material'));return False
        self.consume(q['material'],q['material_qty']);self.turn+=1;self.rad_turns=max(0,self.rad_turns-1);q['progress']=1
        self.log(tr('exp.generator_done'));return True

    def junk_quest(self,ident):
        q=self.local_expedition()
        if q and q['id']==ident and q['kind']=='junkyard':
            junk_physics.ensure(q);return q
        return None

    def junk_top(self,q,x,y):
        junk_physics.ensure(q)
        return next((o for o in reversed(q['junk_objects']) if not o['found'] and junk_physics.covers(o,x,y)),None)

    def junk_move(self,ident,obj_id,x,y):
        q=self.junk_quest(ident)
        if not q or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (x,y)):return False
        obj=next((o for o in q['junk_objects'] if o['id']==obj_id and o['kind']=='debris'),None)
        if not obj:return False
        obj['x'],obj['y']=junk_physics.clamp(obj,x,y)
        q['junk_objects'].remove(obj);q['junk_objects'].append(obj);return True

    def junk_tick(self,ident,dt,held=None,destination=None):
        q=self.junk_quest(ident)
        return junk_physics.tick(q,dt,held,destination) if q else []

    def junk_collect(self,ident,x,y):
        q=self.junk_quest(ident)
        if not q:return False
        obj=self.junk_top(q,x,y)
        if not obj or obj['kind']=='debris':return False
        obj['found']=True
        if obj['kind']=='target':
            self.bag.append(dict(id=r.uid(),type_id='quest_item',kind='quest',name=tr('scav.junk_part'),quest_id=q['id'],rarity=0,weight=0,value=0))
            q['progress']+=1;self.emit(tr('scav.junk_progress',count=q['progress'],goal=q['goal']))
        else:
            item=p.ammunition(obj['ammo_type'],obj['qty']) if obj['kind']=='ammo' else p.supply(obj['kind'],obj['qty'])
            p.add_to(self.loot,item);self.log(tr('scav.bonus',name=item['name'],qty=item['qty']))
        return True

    def quest_ready(self,q):
        if q['kind']=='junkyard':return q['status']=='active' and q['progress']>=q['goal'] and sum(i.get('quest_id')==q['id'] for i in self.bag)>=q['goal']
        return super().quest_ready(q)

    def quest_item_views(self,q):
        if q['kind']=='junkyard':return [dict(kind='quest',name=tr('scav.junk_part'),rarity=0,qty=q['goal'])]
        if q['kind']=='retrieve' and 'metro_city' not in q:return [self.quest_equipment(q) or self.relic_item(q)]
        return super().quest_item_views(q)

    def quest_text(self,q):
        if q['kind']=='junkyard' or (q['kind'] in ('scout','retrieve') and 'metro_city' not in q):
            desc=tr('scav.desc_'+q['kind'])
            if q.get('area'):desc+='\n'+tr('exp.area',x=q['area'][0],y=q['area'][1],xx=q['area'][2],yy=q['area'][3])
            elif q.get('pos'):desc+='\n'+tr('exp.point',x=q['pos'][0],y=q['pos'][1])
            return tr('exp.quest_text',title=q['title'],level=q['level'],desc=desc,progress=q['progress'],goal=9 if q['kind']=='scout' else q['goal'],city=self.city_name(q['city']),money=q['reward'],xp=q['xp_reward'])
        return super().quest_text(q)

    @classmethod
    def load(cls,path):
        game=super().load(path)
        for q in game.quests:
            if q['status']!='active':continue
            if q['kind']=='junkyard':junk_physics.ensure(q)
            if q['kind']=='generator' and 'generator_order' not in q:game.init_generator(q)
            if q['kind'] in ('scout','retrieve') and 'metro_city' not in q and not q.get('area') and not game.quest_ready(q):
                pool=game.area_candidates(q)
                if pool:game.setup_area(q,pool)
        return game
