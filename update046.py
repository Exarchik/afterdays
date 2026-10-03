"""Physical credits, level-aware quest XP and shared-storage access for v0.46."""
import math
import authored_quests
import progression as p
from consumable_rules import Consumables

def credit_item(qty):
    import afterdays,content
    return dict(id=afterdays.uid(),type_id='item_credits',kind='credits',name=content.CONSUMABLES['item_credits']['name'],qty=qty,weight=0,value=1,rarity=0,level=1)

def quest_multiplier(delta):
    return 1 if delta<2 else .8 if delta==2 else .6 if delta==3 else .25 if delta==4 else .01

class Game(Consumables,authored_quests.Game):
    def __init__(self,*args,**kwargs):
        self._physical_credits_ready=False
        super().__init__(*args,**kwargs)
        amount=self.__dict__.get('money',0);self._physical_credits_ready=True
        if amount:p.add_to(self.bag,credit_item(amount))
    @property
    def carried_money(self):return sum(i.get('qty',1) for i in self.bag if i['kind']=='credits')
    @property
    def stored_money(self):return sum(i.get('qty',1) for i in self.stash if i['kind']=='credits')
    @property
    def money(self):
        if not getattr(self,'_physical_credits_ready',False):return self.__dict__.get('money',0)
        return self.carried_money+self.stored_money
    @money.setter
    def money(self,value):
        value=max(0,int(value))
        if getattr(self,'_physical_credits_ready',False):
            difference=value-self.money
            if difference>0:p.add_to(self.bag,credit_item(difference))
            elif difference<0:
                remaining=-difference
                for source in (self.bag,self.stash):
                    for item in list(source):
                        if item['kind']!='credits':continue
                        count=min(remaining,item.get('qty',1));p.extract(source,item,count);remaining-=count
                        if not remaining:break
                    if not remaining:break
        self.__dict__['money']=value
    def save(self,path):
        self.__dict__['money']=self.money
        return super().save(path)
    @classmethod
    def load(cls,path):
        game=super().load(path)
        stacks=[i for i in game.bag+game.stash if i['kind']=='credits']
        if any(type(i.get('qty')) is not int or i['qty']<1 for i in stacks):raise ValueError('Invalid credit stack')
        if not stacks and game.__dict__.get('money',0)>0:p.add_to(game.bag,credit_item(game.__dict__['money']))
        game.__dict__['money']=game.money
        return game
    def step(self,*args,**kwargs):
        self._walking_reveal=True
        try:return super().step(*args,**kwargs)
        finally:self._walking_reveal=False
    def reveal(self,*args,**kwargs):
        before=set(getattr(self,'explored',[]))
        result=super().reveal(*args,**kwargs)
        if getattr(self,'_physical_credits_ready',False):self._reveal_notice(before)
        return result
    def buys_kind(self,item,merchant):
        if item['kind']=='credits':return False
        return super().buys_kind(item,merchant)
    def stock(self,merchant):
        """Roll extra consumables once per stock refresh, including existing saved shops."""
        import content
        items=super().stock(merchant)
        entry=next((v for v in self.shops.values() if v['items'] is items),None)
        if self.traveler and self.traveler.get('items') is items:entry=self.traveler
        if not items or entry is None or entry.get('consumables_variety'):return items
        for kind in ('food','med','rad','repairkit'):
            if not any(i['kind']==kind for i in items):continue
            pool=[ident for ident,d in content.CONSUMABLES.items() if d['kind']==kind and ident!='item_'+kind]
            if not pool:continue
            for ident in self.rng.sample(pool,self.rng.randint(1,min(3,len(pool)))):
                p.add_to(items,p.supply(ident,self.rng.randint(1,4)))
        entry['consumables_variety']=True
        return items
    @property
    def can_access_stash(self):
        if self.battle:return False
        site=self.current_site
        return self.regular_city or bool(site and self.record_at(site['pos'])['value']>=50)
    def quest_xp(self,q):
        amount=max(1,math.floor(q.get('xp_reward',0)*quest_multiplier(self.level-q.get('level',q.get('zone',1)))))
        return max(1,amount//(2 if self.coward_turns else 1))
    def turn_in(self,ident):
        q=next((q for q in self.quests if q['id']==ident),None)
        if q is None:return False
        original=q.get('xp_reward',0)
        q['xp_reward']=self.quest_xp(q)*(2 if self.coward_turns else 1)
        try:return super().turn_in(ident)
        finally:q['xp_reward']=original
    def quest_text(self,q):return super().quest_text(dict(q,xp_reward=self.quest_xp(q)))
