from i18n import t as tr
"""Afterdays v0.3: progression, stacks, economy, ammunition and maintenance."""
import content
import copy
import balance
import json
import math
import os
from pathlib import Path
from collections import deque
import afterdays as r

_base_equipment, _base_module, _base_supply, _base_stats = r.equipment, r.module, r.supply, r.stats
GEAR_MIN_LEVEL = content.GEAR_MIN_LEVEL
AMMO = content.AMMO
AMMO_BY_WEAPON = content.AMMO_BY_WEAPON
PERKS = {
    'marksman':(tr('progression.0007'),tr('progression.0008')),
    'carrier':(tr('progression.0009'),tr('progression.0010')),
    'hardy':(tr('progression.0011'),tr('progression.0012')),
    'armorer':(tr('progression.0013'),tr('progression.0014')),
    'medic':(tr('progression.0015'),tr('progression.0016')),
    'engineer':(tr('progression.0017'),tr('progression.0018')),
    'trader':(tr('progression.0019'),tr('progression.0020')),
    'scavenger':(tr('progression.0021'),tr('progression.0022')),
}
STACK_KINDS = {'food','med','ammo','parts','fragments','rad','repairkit'}
TECHNICIANS = [0,2,4,7,10]


def xp_for_level(level):
    return balance.xp_threshold(level)


def equipment(name=None, tier=0, rng=None, level=1):
    rng = rng or r.random
    level=max(1,int(level))
    if name is not None:name=content.entity_id(name)
    eligible=[n for n in r.GEAR if GEAR_MIN_LEVEL[n] <= level]
    if name not in eligible:
        # Preserve requested equipment category when possible.
        kind=r.GEAR[name][0] if name in r.GEAR else None
        pool=[n for n in eligible if kind is None or r.GEAR[n][0] == kind]
        name=rng.choice(pool or eligible)
    item=_base_equipment(name,tier,rng)
    item.update(level=level,durability=100.0)
    if item['kind']=='weapon':
        base=r.GEAR[name][1]
        item['stats']['damage']=round(base*(1+.13*(level-1)))+tier*2
        item['stats']['attack']=balance.attack_for(name,level)
        item['ammo_type']=AMMO_BY_WEAPON.get(name,'rifle')
    else:
        item['stats']['defense']=r.GEAR[name][3]+(level-1)+tier
    base=70+r.GEAR[name][5]*15
    item['value']=round(base*level**1.3*[1,1.8,3.5,7,14][tier])
    return item


def module(tier=0,rng=None,index=None,level=1):
    item=_base_module(tier,rng,index)
    item['level']=max(1,int(level))
    item['value']=round(30*(tier+1)**2*item['level']**1.3)
    item['stats']={k:max(1,round(v*(1+.06*(item['level']-1)))) for k,v in item['stats'].items()}
    if 'pierce' in item['stats']:
        item['stats'].pop('pierce');item['stats']['attack']=tier+1
    if rng is not None and rng.random()<.20:
        key=next(iter(item['stats']));item['stats'][key]=max(1,round(item['stats'][key]*1.7))
        drawback={'damage':('accuracy',-6),'range':('damage',-2),'accuracy':('range',-1),'attack':('accuracy',-5),'crit':('accuracy',-5),'defense':('capacity',-2),'vitality':('evasion',-3),'capacity':('defense',-1),'evasion':('vitality',-4),'regen':('capacity',-2)}[key]
        item['stats'][drawback[0]]=drawback[1]*(1+tier//2);item['tradeoff']=True
    return item


def supply(kind,qty=1):
    return dict(id=r.uid(),qty=int(qty),level=1,**content.consumable(kind))


def ammunition(kind,qty=1):
    name,value,weight=AMMO[kind]
    return dict(id=r.uid(),name=name,type_id='ammo_'+kind,kind='ammo',ammo_type=kind,rarity=0,
                weight=weight,value=value,qty=int(qty),level=1)


def fragments(qty):return supply('fragments',qty)

def parts(qty):return supply('parts',qty)


def stats(item):
    result=_base_stats(item)
    if 'durability' in item:
        condition=max(0,min(100,item['durability']))/100
        for key in ('damage','defense'):
            if result.get(key):
                result[key]=max(1,round(result[key]*(.5+.5*condition))) if condition else 0
    return result


def item_weight(item):
    return item['weight']*item.get('qty',1)+sum(item_weight(m) for m in item.get('modules',[]))


def item_value(item):
    return item['value']*item.get('qty',1)+sum(item_value(m) for m in item.get('modules',[]))


def stack_key(item):
    return (item['kind'],item.get('monster_kind') if item['kind']=='trophy' else item.get('ammo_type')) if item['kind'] in STACK_KINDS else None


def add_to(items,item):
    key=stack_key(item)
    if key:
        existing=next((i for i in items if stack_key(i)==key),None)
        if existing:
            existing['qty']=existing.get('qty',1)+item.get('qty',1)
            return existing
        item.setdefault('qty',1)
    items.append(item)
    return item


def normalize(items):
    result=[]
    for i in items:
        add_to(result,i)
    return result


def extract(items,item,qty=1):
    available=item.get('qty',1)
    if qty < 1 or qty > available or item not in items:
        return None
    if qty==available:
        items.remove(item)
        return item
    result=copy.deepcopy(item)
    result['id']=r.uid()
    result['qty']=qty
    item['qty']-=qty
    return result


class Game(r.ExpansionGame):
    def __init__(self,seed=None):
        super().__init__(seed)
        self.perks={}
        self.technicians=TECHNICIANS[:]
        self.travel_steps=0
        self.equipped={'weapon1':equipment('weapon_ash_pistol'), 'weapon2':None,
                        'armor':equipment('armor_plated_jacket'), 'helmet':equipment('helmet_seeker')}
        self.bag=[module(index=0),module(index=3),supply('med',2),supply('food',3),ammunition('pistol',60)]
        self.money=160
        self.hp=self.max_hp
        self.messages=[]
        self.log(tr('progression.0026'))

    @property
    def level(self):
        level=1
        while self.xp >= xp_for_level(level+1):
            level+=1
        return level

    def rank(self,key):
        return getattr(self,'perks',{}).get(key,0)

    @property
    def pending_perks(self):
        return max(0,self.level//3-sum(self.perks.values()))

    def choose_perk(self,key):
        if key not in PERKS or not self.pending_perks:
            return False
        self.perks[key]=self.rank(key)+1
        self.log(tr('progression.0027', v0=PERKS[key][0], v1=self.rank(key)))
        return True

    @property
    def capacity(self):
        return max(1,35+self.protection_stat('capacity')+self.rank('carrier')*5)

    @property
    def max_hp(self):
        return max(1,25+(self.level-1)*5+self.protection_stat('vitality')+self.rank('hardy')*10)

    @property
    def defense(self):
        return max(0,sum(stats(i).get('defense',0) for i in self.equipped.values() if i)+self.rank('armorer'))

    def protection_stat(self,key):
        return sum(stats(i).get(key,0) for i in self.equipped.values()
                   if i and i['kind']!='weapon' and (i.get('durability',100)>0 or key=='capacity'))

    @property
    def region_level(self):
        return self.region_at(self.x,self.y)

    @staticmethod
    def region_at(x,y=5):
        return 1+max(0,int((math.hypot(x-5,y-5)-3)//3))

    def count(self,kind,ammo_type=None):
        return sum(i.get('qty',1) for i in self.bag if i['kind']==kind and
                   (ammo_type is None or i.get('ammo_type')==ammo_type))

    def consume(self,kind,qty=1,ammo_type=None):
        if self.count(kind,ammo_type)<qty:
            return False
        left=qty
        for item in list(self.bag):
            if item['kind']==kind and (ammo_type is None or item.get('ammo_type')==ammo_type):
                n=min(left,item.get('qty',1))
                extract(self.bag,item,n)
                left-=n
                if left==0:
                    return True
        return True

    def accept(self,item):
        if self.weight+item_weight(item)>self.capacity+.0001:
            self.log(tr('progression.0028'))
            return False
        add_to(self.bag,item)
        return True

    def equip(self,item_id,slot):
        item=self.find(item_id)
        if item and item.get('level',1)>self.level:
            self.log(tr('progression.0029'))
            return False
        return super().equip(item_id,slot)

    def install(self,item_id,mod_id):
        mod=self.find(mod_id)
        if mod and mod.get('level',1)>self.level:
            return False
        return super().install(item_id,mod_id)

    def put_module(self,item_id,mod_id,slot_index):
        mod=self.find(mod_id)
        if mod and mod.get('level',1)>self.level:
            return False
        return super().put_module(item_id,mod_id,slot_index)

    def use(self,kind):
        if kind not in ('med','food') or not self.count(kind):
            self.log(tr('progression.0030'))
            return False
        if self.hp>=self.max_hp:
            self.log(tr('progression.0031'))
            return False
        if self.battle and self.battle['ap']<2:
            self.log(tr('progression.0032'))
            return False
        self.consume(kind)
        heal=min(self.max_hp-self.hp,math.ceil(self.max_hp*.5) if kind=='med' else round(14*(1+.1*self.rank('medic'))))
        self.hp+=heal
        if self.battle:
            self.battle['ap']-=2
        self.log(tr('progression.0033', v0=heal))
        return True

    def step(self,dx,dy):
        if self.battle:
            return self.battle_move((self.battle['pos'][0]+dx,self.battle['pos'][1]+dy))
        if abs(dx)+abs(dy)!=1 or not (0<=self.x+dx<48 and 0<=self.y+dy<32):
            return False
        self.x+=dx; self.y+=dy
        self.turn+=1; self.travel_steps+=1
        self.traveler=None
        if self.travel_steps%8==0:
            if self.consume('food'):
                self.hp=min(self.max_hp,self.hp+10)
                self.log(tr('progression.0034'))
            else:
                self.hp=max(1,self.hp-5)
                self.log(tr('progression.0035'))
        self._visit_objectives()
        if self.city is not None:
            self.log(tr('progression.0036', v0=self.city_name(self.city)))
        elif self.rng.random()<{'road':.06,'waste':.12,'forest':.20,'ruin':.24}[self.world[self.y][self.x]]:
            self.start_battle()
        elif self.turn-self.last_traveler_turn>=7 and self.rng.random()<.09:
            self.spawn_traveler()
        return True

    def roll_item(self):
        max_tier=min(4,self.level//3)
        tier=self.rng.choices(list(range(max_tier+1)),[55,27,12,5,1][:max_tier+1])[0]
        level=self.rng.randint(max(1,self.level-2),self.level)
        return module(tier,self.rng,level=level) if self.rng.random()<.55 else equipment(tier=tier,rng=self.rng,level=level)

    def stock(self,merchant):
        if not self.available_merchant(merchant):
            return []
        if merchant==3:
            return self.traveler['items']
        key=f'{self.city}:{merchant}'
        entry=self.shops.get(key)
        if entry is None or self.turn-entry['turn']>=40 or entry.get('level')!=self.region_level:
            if merchant==0:
                names=[n for n in r.GEAR if GEAR_MIN_LEVEL[n]<=self.region_level]
                names=self.rng.sample(names,min(12,len(names)))
                cap=min(4,1+self.region_level//4)
                items=[equipment(n,self.rng.randrange(cap+1),self.rng,self.region_level) for n in names]
                items += [module(self.rng.randrange(cap+1),self.rng,i,self.region_level) for i in range(len(r.MODULES))]
                items += [ammunition(kind,200) for kind in AMMO]
            elif merchant==1:
                items=[supply('med',12),supply('food',24),supply('rad',8)]
            else:
                items=[]
                for _ in range(10):
                    level=self.rng.randint(max(1,self.region_level-1),self.region_level)
                    tier=self.rng.choices(range(5),[35,30,20,12,3])[0]
                    item=equipment(tier=tier,rng=self.rng,level=level) if self.rng.random()<.8 else module(tier,self.rng,level=level)
                    if 'durability' in item:
                        item['durability']=float(self.rng.randint(5,30) if self.rng.random()<.75 else self.rng.randint(40,100))
                    item['sealed_price']=round(85*self.region_level**1.3)
                    items.append(item)
            self.shops[key]=entry=dict(turn=self.turn,level=self.region_level,items=items)
        return entry['items']

    def spawn_traveler(self):
        item=equipment(tier=self.rng.choices(range(5),balance.TRAVELER_WEIGHTS)[0],rng=self.rng,level=self.region_level)
        self.traveler=dict(pos=[self.x,self.y],items=[item,module(self.rng.choices(range(5),balance.TRAVELER_WEIGHTS)[0],self.rng,level=self.region_level),
                           supply('food',8),supply('med',5),ammunition('pistol',60)])
        self.last_traveler_turn=self.turn
        self.log(tr('progression.0037'))

    def price(self,item,merchant,buying=True):
        base=item_value(item)/item.get('qty',1)
        if buying:
            amount=item.get('sealed_price',round(85*self.level**1.3)) if merchant==2 and item['kind']!='repairkit' else base*(.5 if merchant==3 else 1.15)
            return max(1,round(amount*(1-min(.30,.05*self.rank('trader')))))
        condition=.25+.75*item.get('durability',100)/100
        return max(1,int(base*condition*(.22 if merchant==2 else .30 if merchant==3 else .50)))

    def buys_kind(self,item,merchant):
        if item['kind']=='quest' or item.get('durability',100)<25:
            return False
        if item['kind'] in ('parts','fragments'):
            return True
        if item['kind']=='ammo':
            return merchant in (0,2,3)
        if item['kind']=='rad':return merchant in (1,2,3)
        return super().buys_kind(item,merchant)

    def buy(self,item_id,merchant,qty=1):
        stock=self.stock(merchant)
        item=next((i for i in stock if i['id']==item_id),None)
        if not item or not isinstance(qty,int) or not 1<=qty<=item.get('qty',1):
            return False
        price=self.price(item,merchant)*qty
        preview=copy.deepcopy(item)
        if stack_key(preview): preview['qty']=qty
        if price>self.money:
            self.log(tr('progression.0038', v0=price))
            return False
        if self.weight+item_weight(preview)>self.capacity+.0001:
            self.log(tr('progression.0039'))
            return False
        bought=extract(stock,item,qty)
        self.money-=price
        add_to(self.bag,bought)
        self.log(tr('progression.0040', v0=bought['name'], v1=qty, v2=price))
        return True

    def sell(self,item_id,merchant,qty=1):
        if not self.available_merchant(merchant): return False
        item=next((i for i in self.bag if i['id']==item_id),None)
        if not item or not isinstance(qty,int) or not 1<=qty<=item.get('qty',1): return False
        if not self.buys_kind(item,merchant):
            self.log(tr('progression.0041'))
            return False
        price=self.price(item,merchant,False)*qty
        extract(self.bag,item,qty)
        self.money+=price
        self.log(tr('progression.0042', v0=item['name'], v1=qty, v2=price))
        return True

    def salvage_yield(self,item):
        return max(1,int(item['value']*.12*(.25+.75*item.get('durability',100)/100)/2))

    def dismantle(self,item_id):
        if self.battle: return False
        item=next((i for i in self.bag if i['id']==item_id),None)
        if not item or item['kind'] not in ('weapon','armor','helmet'):
            self.log(tr('progression.0043'))
            return False
        count=self.salvage_yield(item)
        self.bag.remove(item)
        for mod in item.get('modules',[]): add_to(self.bag,mod)
        add_to(self.bag,parts(count) if item['kind']=='weapon' else fragments(count))
        self.log(tr('progression.0044', v0=count))
        return True

    def drop_item(self,item_id,qty=None):
        if self.battle: return False
        item=next((i for i in self.bag if i['id']==item_id),None)
        if not item or item['kind']=='quest': return False
        obj=extract(self.bag,item,item.get('qty',1) if qty is None else qty)
        if obj:
            add_to(self.loot,obj)
            return True
        return False

    def collect(self,item_id):
        if self.battle and not (self.battle.get('dungeon') and self.battle.get('cleared')): return False
        item=next((i for i in self.loot if i['id']==item_id),None)
        if not item: return False
        qty=item.get('qty',1)
        if stack_key(item) and item['weight']>0:
            qty=min(qty,max(0,int((self.capacity-self.weight+.00001)/item['weight'])))
        if qty<1:
            self.log(tr('progression.0045'))
            return False
        obj=copy.deepcopy(item)
        if stack_key(obj): obj['qty']=qty
        if not self.accept(obj): return False
        extract(self.loot,item,qty)
        return True

    def repair_cost(self,item,target=100):
        if target not in (25,50,100) or 'durability' not in item or item['durability']>=target: return 0
        return max(1,math.ceil(item['value']*.22*((target-item['durability'])/100)*(1-min(.3,.05*self.rank('trader')))))

    def repair(self,item_id,target=100):
        if self.battle or self.city not in self.technicians:
            self.log(tr('progression.0046'))
            return False
        item=self.find(item_id)
        if not item or 'durability' not in item: return False
        cost=self.repair_cost(item,target)
        if not cost:
            self.log(tr('progression.0047'))
            return False
        if cost>self.money:
            self.log(tr('progression.0048', v0=cost))
            return False
        self.money-=cost
        item['durability']=float(target)
        self.log(tr('progression.0049', v0=item['name'], v1=cost))
        return True

    def wear(self,item,amount):
        if item and 'durability' in item:
            item['durability']=round(max(0,item['durability']-amount*(1-min(.7,.15*self.rank('engineer')))),2)
            self.hp=min(self.hp,self.max_hp)

    def shot_info(self,enemy):
        valid,reason,chance=super().shot_info(enemy)
        return valid,reason,min(98,chance+self.rank('marksman')*4) if valid else chance

    def shoot(self,enemy_id):
        w=self.weapon
        if not self.battle or not w: return False
        if w.get('durability',100)<=0:
            self.log(tr('progression.0050'))
            return False
        ammo_type=w.get('ammo_type','pistol')
        if not self.count('ammo',ammo_type):
            self.log(tr('progression.0051', v0=AMMO[ammo_type][0]))
            return False
        ok=super().shoot(enemy_id)
        if ok:
            self.consume('ammo',1,ammo_type)
            self.wear(w,.6)
        return ok

    def start_battle(self):
        super().start_battle()
        b=self.battle
        kind=self.world[self.y][self.x]
        b['biome']=kind
        b['region_level']=self.region_level
        w,h=b['w'],b['h']
        density={'waste':.09,'forest':.23,'ruin':.27,'road':.14,'city':.18}.get(kind,.12)
        walls=set()
        for y in range(h):
            for x in range(3,w-1):
                if kind=='road' and 4<=y<=6: continue
                if self.rng.random()<density: walls.add((x,y))
        # Ensure a connected corridor even in dense ruins and woods.
        walls={p for p in walls if p[1]!=5}
        reachable={(1,5)}; queue=deque([(1,5)])
        while queue:
            for p in r.neighbors(*queue.popleft(),w,h):
                if p not in walls and p not in reachable:
                    reachable.add(p); queue.append(p)
        candidates=sorted(p for p in reachable if p[0]>=9)
        self.rng.shuffle(candidates)
        b['walls']=[list(p) for p in sorted(walls)]
        for n,e in enumerate(b['enemies']):
            kind_id=self.rng.randrange(min(len(r.MONSTERS),5+self.region_level))
            name,hp,damage,reach,speed,armor,_=r.MONSTERS[kind_id]
            lv=self.region_level
            hp=round(hp*(1+.24*(lv-1)))
            e.update(kind=kind_id,name=name,hp=hp,max_hp=hp,damage=damage+3*(lv-1),
                     range=reach,speed=speed,armor=armor+(lv-1)//2,level=lv,pos=list(candidates[n]))
        self.log(tr('progression.0052', v0=self.region_level, v1=r.TERRAINS[b['biome']][1]))

    def end_turn(self):
        b=self.battle
        if not b: return
        for e in b['enemies']:
            if e['kind']==8: e['hp']=min(e['max_hp'],e['hp']+3)
            for _ in range(e['speed']):
                if math.dist(e['pos'],b['pos'])<=e['range'] and r.visible(tuple(e['pos']),tuple(b['pos']),b['walls']): break
                blocked=set(map(tuple,b['walls']))|{tuple(o['pos']) for o in b['enemies'] if o is not e}
                route=r.path_to(tuple(e['pos']),tuple(b['pos']),b['w'],b['h'],blocked)
                if route and route[0]!=tuple(b['pos']): e['pos']=list(route[0])
            if math.dist(e['pos'],b['pos'])<=e['range'] and r.visible(tuple(e['pos']),tuple(b['pos']),b['walls']):
                if self.rng.randrange(100)<min(45,self.protection_stat('evasion')):
                    self.log(tr('progression.0053')); continue
                damage=max(1,e['damage']+self.rng.randint(-2,2)-self.defense)
                self.hp-=damage
                self.wear(self.equipped['armor'],.5)
                self.wear(self.equipped['helmet'],.25)
                self.log(f"{e['name']}: −{damage} HP.")
                if self.hp<=0:
                    self.defeat(); return
        self.hp=min(self.max_hp,self.hp+self.protection_stat('regen'))
        b['ap']=6; b['round']+=1
        self.log(tr('progression.0054', v0=b['round']))

    def victory(self):
        region=self.battle.get('region_level',self.region_level) if self.battle else self.region_level
        quest_id=self.quest_battle
        self.battle=None; self.quest_battle=None
        reward=round(self.rng.randint(40,65)*(1+.35*(region-1))*(1+.15*self.rank('scavenger')))
        self.money+=reward
        for item in (self.roll_item(),self.roll_item(),supply('med'),ammunition(self.weapon.get('ammo_type','pistol') if self.weapon else 'pistol',self.rng.randint(4,9))):
            add_to(self.loot,item)
        if quest_id:
            q=next((q for q in self.quests if q['id']==quest_id and q['status']=='active'),None)
            if q: q['progress']=1
        self.log(tr('progression.0055', v0=reward))

    def mayor_offers(self):
        offers=super().mayor_offers()
        for n,q in enumerate(offers):
            if q.get('scaled'): continue
            q['scaled']=True
            q['unique']=(self.city==0 and q['kind']=='retrieve') or self.rng.random()<.18
            q['reward']=round(q['reward']*self.level**1.6*(3 if q['unique'] else 1))
            if q['unique']:
                q['title']={'hunt':tr('progression.0056'),'retrieve':tr('progression.0057'),
                            'scout':tr('progression.0058'),'supplies':tr('progression.0059'),
                            'purge':tr('progression.0060')}[q['kind']]
                if q['kind']=='hunt': q['goal']=8
        return offers

    def quest_ready(self,q):
        if q['status']!='active': return False
        if q['kind']=='supplies':
            return self.count('food') >= q.get('food_need',5 if q.get('unique') else 3) and self.count('med') >= q.get('med_need',3 if q.get('unique') else 2)
        return super().quest_ready(q)

    def quest_text(self,q):
        text=super().quest_text(q)
        if q['kind']=='supplies':
            f,m=(5,3) if q.get('unique') else (3,2)
            a=text.find('\n'); b=text.find(tr('progression.0061'))
            text=text[:a]+tr('progression.0062', v0=self.count('food'), v1=f, v2=self.count('med'), v3=m)+text[b:]
        if q.get('unique'):
            text=tr('progression.0063')+text.replace('+ 40 XP','+ 80 XP').replace(tr('progression.0064'),tr('progression.0065'))
        return text

    def turn_in(self,quest_id):
        q=next((q for q in self.quests if q['id']==quest_id),None)
        if self.battle or not q or self.city!=q['city'] or not self.quest_ready(q):
            self.log(tr('progression.0066')); return False
        if q['kind']=='supplies':
            self.consume('food',q.get('food_need',5 if q.get('unique') else 3))
            self.consume('med',q.get('med_need',3 if q.get('unique') else 2))
        elif q['kind']=='retrieve':
            self.bag[:]=[i for i in self.bag if i.get('quest_id')!=q['id']]
        q['status']='done'; self.money+=q['reward']; self.xp+=q.get('xp_reward',80 if q.get('unique') else 40)
        self.log(tr('progression.0067', v0=q['title'], v1=q['reward']))
        return True

    def search(self):
        before=self.battle
        ok=super().search()
        self.loot=normalize(self.loot)
        if ok and not before and self.quest_battle:
            q=next(q for q in self.quests if q['id']==self.quest_battle)
            if q.get('unique'):
                for e in self.battle['enemies']:
                    e['hp']=e['max_hp']=round(e['max_hp']*1.5)
                    e['damage']=round(e['damage']*1.2)
        for i in self.bag:
            if i['kind']=='quest':
                q=next((q for q in self.quests if q['id']==i.get('quest_id')),None)
                if q and q['kind']=='retrieve' and q.get('unique'): i['name']=tr('progression.0068'); i['rarity']=3
        return ok

    def save(self,path):
        data={k:v for k,v in vars(self).items() if k!='rng'}
        data.update(version=3,rng_state=self.rng.getstate())
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        os.replace(temp,path)

    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        version=data.pop('version',None)
        if version not in (1,2,3): raise ValueError(tr('progression.0069'))
        def tuples(v): return tuple(tuples(x) for x in v) if isinstance(v,list) else v
        state=tuples(data.pop('rng_state'))
        game=cls(0)
        allowed=set(vars(game))-{'rng'}
        if set(data)-allowed or len(data['world'])!=32 or set(data['equipped'])!=set(r.SLOTS):
            raise ValueError(tr('progression.0070'))
        if version==3 and set(data)!=allowed: raise ValueError(tr('progression.0071'))
        game.__dict__.update(data)
        if version==1:
            game.cities.extend([p[:] for p in r.EXTRA_CITIES]); game._connect_cities()
        if version<3:
            oldlevel=1+game.xp//100
            game.xp=xp_for_level(oldlevel)
            def migrate(item):
                item.setdefault('level',min(oldlevel,GEAR_MIN_LEVEL.get(item['name'],oldlevel)))
                if item['kind'] in ('weapon','armor','helmet'):
                    item.setdefault('durability',100.0)
                    base=70+item['weight']*15
                    item['value']=round(base*item['level']**1.3*[1,1.8,3.5,7,14][item['rarity']])
                    if item['kind']=='weapon': item['ammo_type']=AMMO_BY_WEAPON.get(item['name'],'rifle')
                if item['kind'] in STACK_KINDS: item.setdefault('qty',1)
                for mod in item.get('modules',[]): migrate(mod)
            for item in game.bag+game.loot+[i for i in game.equipped.values() if i]: migrate(item)
            game.bag=normalize(game.bag); game.loot=normalize(game.loot)
            game.shops={}; game.traveler=None
            for ammo_type in {i.get('ammo_type','pistol') for i in game.equipped.values() if i and i['kind']=='weapon'}:
                unit=AMMO[ammo_type][2]
                fits=min(40,max(0,int((game.capacity-game.weight+.00001)/unit)))
                if fits: add_to(game.bag,ammunition(ammo_type,fits))
                if fits<40: add_to(game.loot,ammunition(ammo_type,40-fits))
            game.log(tr('progression.0072'))
        if game.battle:
            game.battle.setdefault('biome',game.world[game.y][game.x])
            game.battle.setdefault('region_level',game.region_level)
            for e in game.battle['enemies']: e.setdefault('level',game.region_level)
        game.rng.setstate(state)
        return game
