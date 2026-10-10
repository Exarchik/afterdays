"""Rarity gates gameplay behavior."""
from game import items as item_rules
import module_rules

import random


class RarityGatesMixin:
    @property
    def rarity_cap(self):
        """Elite items unlock at player level five and mythic items at seven."""
        return 2 if self.level<5 else 3 if self.level<7 else 4

    def cap_item(self,item):
        """Normalize newly generated goods and their modules to unlocked rarity tiers."""
        if item.get('kind') in ('weapon','armor','helmet','module') and item.get('rarity',0)>self.rarity_cap:
            tier=self.rarity_cap;level=item.get('level',1)
            if item['kind']=='module':
                item.update(rarity=tier,value=round(30*(tier+1)**2*level**1.3),stats=module_rules.module_stats(item['type_id'],tier,level,item.get('tradeoff',False)))
            else:
                fresh=item_rules.equipment(item['type_id'],tier,random.Random(0),level)
                for key in ('rarity','value','stats','slots'):item[key]=fresh[key]
                item['modules']=item.get('modules',[])[:item['slots']]
        for mod in item.get('modules',[]):self.cap_item(mod)
        if item.get('contents'):self.cap_item(item['contents'])
        return item

    def reward_item(self,cap=4,minimum=0,level=None):
        """Constrain reward generation before rolling rarity."""
        cap=min(cap,self.rarity_cap)
        return super().reward_item(cap,min(minimum,cap),level)

    def roll_item(self):
        """Apply rarity unlocks to ordinary random item generation."""
        return self.cap_item(super().roll_item())

    def stock(self,merchant):
        """Gate newly displayed market goods, including sealed contents."""
        items=super().stock(merchant)
        for item in items:self.cap_item(item)
        return items

    def craft_odds(self,amount):
        """Move locked crafting rarity weight to the highest unlocked rarity."""
        odds=list(super().craft_odds(amount));cap=self.rarity_cap
        odds[cap]+=sum(odds[cap+1:])
        for i in range(cap+1,5):odds[i]=0
        return odds
