"""Quest capacity, cancellation, repair deliveries and reputation-aware travellers."""
import copy
import math
import afterdays as r
import progression as p
import economy
from i18n import t as tr

class QuestSystem:
    def quest_capacity(self,city):
        if city not in self.mayors:return 1
        rep=self.reputation(city)
        return 2+(rep>=25)+(rep>=50)+(rep>=75)

    def active_for(self,city):
        return [q for q in self.quests if q['city']==city and q['status']=='active']

    def mayor_offers(self):
        offers=super().mayor_offers() if self.city in self.mayors else self.bulletin_offers()
        if self.city is None or self.battle:return []
        slots=max(0,self.quest_capacity(self.city)-len(self.active_for(self.city)))
        available=[q for q in offers if q['status']=='offered']
        available=[q for q in available if q['kind'] not in ('delivery','repair_delivery') or any(s['id']==q['destination'] for s in self.delivery_sites(q))]
        return available[:slots]

    def bulletin_offers(self):
        if self.battle or not self.regular_city or self.city in self.mayors:return []
        key=f'bulletin:{self.city}';entry=self.reputation_state.setdefault('bulletins',{}).get(key)
        if entry is None or self.turn-entry['turn']>=100:
            entry=dict(turn=self.turn,items=[])
            if self.rng.random()<.5:
                kind=self.rng.choice(['hunt','scout','retrieve','supplies'])
                q=dict(id=r.uid(),kind=kind,city=self.city,status='offered',title=r.QUEST_LABELS[kind],progress=0,
                       goal=self.rng.randint(2,5) if kind=='hunt' else 1,target_kind=None,pos=None,unique=False,
                       level=self.region_level,food_need=3,med_need=2,bulletin=True)
                self.price_quest(q);entry['items'].append(q)
            self.reputation_state['bulletins'][key]=entry
        for q in entry['items']:
            if q['status']=='offered':self.price_quest(q)
        return entry['items']

    def trading_city(self,merchant):
        if merchant in (3,4) and self.traveler and self.traveler['pos']==[self.x,self.y] and (merchant==3 or self.traveler.get('hunter')):
            return min(range(12),key=lambda n:math.dist((self.x,self.y),self.cities[n]))
        return self.city

    def change_reputation(self,amount,city):
        origin=self.cities[city]
        positions=set(map(tuple,self.cities))|{tuple(s['pos']) for s in self.special_sites}
        for pos in positions:
            if math.dist(origin,pos)<=10:
                record=self.record_at(pos);record['value']=max(0,min(100,record['value']+amount))

    def abandon_quest(self,quest_id):
        q=next((q for q in self.quests if q['id']==quest_id and q['status']=='active'),None)
        if not q or self.battle:return False
        for items in (self.bag,self.stash,self.loot):items[:]=[i for i in items if i.get('quest_id')!=quest_id]
        for offers in self.offers.values():
            for offer in offers:
                if offer['id']==quest_id:offer['status']='cancelled'
        for entry in self.reputation_state.get('bulletins',{}).values():
            for offer in entry['items']:
                if offer['id']==quest_id:offer['status']='cancelled'
        self.quests.remove(q)
        if q['kind']=='permit':self.reputation_state['permit_retry']=self.turn+100
        if self.quest_battle==quest_id:self.quest_battle=None
        self.change_reputation(-5,q['city'])
        self.log(tr('quests.cancelled',title=q['title']));return True

    def quest_return_city(self,q):
        if q['kind']=='repair_delivery':
            site=next((s for s in self.special_sites if s['id']==q['destination']),None)
            return site['city_id'] if site else None
        return q['city']

    def quest_return_pos(self,q):
        return q['pos'] if q['kind']=='repair_delivery' else self.cities[q['city']]

    def can_turn_in(self,q):
        return not self.battle and self.quest_ready(q) and [self.x,self.y]==list(self.quest_return_pos(q))

    def quest_ready(self,q):
        if q['kind']=='repair_delivery':
            return q['status']=='active' and any(i.get('quest_id')==q['id'] and i.get('durability',0)>=100 for i in self.bag)
        return super().quest_ready(q)

    def stash_transfer(self,item_id,direction,qty=1):
        if any(i['id']==item_id and i.get('quest_id') for i in self.bag+self.stash):return False
        return super().stash_transfer(item_id,direction,qty)

    def quest_item_views(self,q):
        if q['kind']=='repair_delivery':
            item=next((i for i in self.bag if i.get('quest_id')==q['id']),q['repair_item'])
            return [item]
        if q['kind']=='supplies':return [p.supply('food',q.get('food_need',3)),p.supply('med',q.get('med_need',2))]
        if q['kind']=='trophies':return [economy.trophy(q['target_kind'],q['goal'])]
        if q['kind'] in ('retrieve','delivery'):
            return [next((i for i in self.bag if i.get('quest_id')==q['id']),dict(id='preview',kind='quest',name=q.get('part_name',q.get('destination_name',q['title'])),rarity=0,weight=0,value=0))]
        return []

    def prepare_quest_rewards(self,q):
        signature=bool(q.get('unique'))
        if 'reward_items' in q and q.get('reward_unique')==signature:return q['reward_items']
        gifts=[]
        if q['kind']=='thanks':
            if self.rng.random()<.5:
                kind=self.rng.choice(['ammo','med','food','rad'])
                gifts.append(p.ammunition((self.weapon or {}).get('ammo_type','pistol'),self.rng.randint(15,35)) if kind=='ammo' else p.supply(kind,self.rng.randint(1,3)))
            if self.rng.random()<.2:gifts.append(self.reward_item(4,1,level=self.level))
        elif q.get('unique'):
            for _ in range(1+(self.rng.random()<.1)):gifts.append(self.reward_item(4,1,level=q.get('level',1)))
        q['reward_items']=gifts;q['reward_unique']=signature
        return gifts

    def give_quest_items(self,q):
        for item in self.prepare_quest_rewards(q):
            if not self.accept(copy.deepcopy(item)):p.add_to(self.stash,copy.deepcopy(item))
            self.log(tr('reputation.gift',name=item['name']))

    def turn_in(self,quest_id):
        q=next((q for q in self.quests if q['id']==quest_id),None)
        if q and q['kind']=='repair_delivery':
            if not self.can_turn_in(q):return False
            self.bag[:]=[i for i in self.bag if i.get('quest_id')!=quest_id]
            q['status']='done';q['progress']=1;self.money+=q['reward'];self.gain_xp(q['xp_reward'])
            self.give_quest_items(q);self.add_reputation(8 if q.get('unique') else 4,city=q['city'])
            self.log(tr('quests.delivered',title=q['title']));return True
        return super().turn_in(quest_id)

    def repair(self,item_id,target=100):
        ok=super().repair(item_id,target)
        if ok:
            item=self.find(item_id)
            for q in self.quests:
                if q['kind']=='repair_delivery' and q['id']==item.get('quest_id'):q['progress']=int(item['durability']>=100)
        return ok
