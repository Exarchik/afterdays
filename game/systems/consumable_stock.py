"""Consumable stock gameplay behavior."""
from game import items as item_rules


class ConsumableStockMixin:
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
                item_rules.add_to(items,item_rules.supply(ident,self.rng.randint(1,4)))
        entry['consumables_variety']=True
        return items
