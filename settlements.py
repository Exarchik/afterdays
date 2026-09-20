"""Settlement clearances, market specials and generator hazards."""
import math
import scavenging,frontier
from i18n import t as tr

class Game(scavenging.Game):
    def __init__(self,seed=None):
        super().__init__(seed);self.ensure_settlements()

    def clear_city_edges(self):
        for cx,cy in self.cities[:12]:
            for y in range(max(0,cy-1),min(32,cy+2)):
                for x in range(max(0,cx-1),min(48,cx+2)):
                    if self.world[y][x]=='cliff':self.world[y][x]='waste'
                    self.radiation.pop(f'{x},{y}',None)

    def ensure_settlements(self):
        self.clear_city_edges()
        for city in frontier.METRO_CITIES:
            if city not in self.mayors:self.mayors.append(city)

    def build_radiation(self):
        super().build_radiation();self.clear_city_edges()

    def stock(self,merchant):
        items=super().stock(merchant)
        if self.city is None or merchant==3 or self.reputation()<60:return items
        entry=next((v for v in self.shops.values() if v['items'] is items),None)
        if entry is None or entry.get('special_checked'):return items
        entry['special_checked']=True
        pool=[i for i in items if i['kind'] in ('weapon','armor','helmet','module','sealed')]
        if pool and self.rng.random()<.08:
            item=self.rng.choice(pool)
            item['promotion']=dict(discount=self.rng.choices([30,50,75],[70,25,5])[0],city=self.city,merchant=merchant)
        return items

    def promotion(self,item,merchant):
        sale=item.get('promotion',{})
        return sale.get('discount',0) if self.city is not None and self.reputation()>=60 and sale.get('city')==self.city and sale.get('merchant')==merchant else 0

    def price(self,item,merchant,buying=True):
        base=super().price(item,merchant,buying)
        if buying:return max(2,round(base*(1-self.promotion(item,merchant)/100)))
        # Includes discounts and paid-price cap, even after reputation or merchant changes.
        return max(1,min(base,self.price(item,merchant,True)-1,item.get('paid_sale_cap',base)))

    def buy(self,ident,merchant,qty=1):
        item=next((i for i in self.stock(merchant) if i['id']==ident),None)
        promo=item and self.promotion(item,merchant)
        price=self.price(item,merchant,True) if item else 0
        ok=super().buy(ident,merchant,qty)
        if ok and promo:
            def cap(obj):
                obj['paid_sale_cap']=max(1,price-1);obj.pop('promotion',None)
                if obj.get('contents'):cap(obj['contents'])
            cap(item)
        return ok

    def generator_toggle(self,ident,index):
        self._generator_shock=0
        q=self.local_expedition()
        wrong=bool(q and q['id']==ident and q['kind']=='generator' and type(index)==int and 0<=index<5 and len(q['generator_input'])<5 and index!=q['generator_order'][len(q['generator_input'])])
        ok=super().generator_toggle(ident,index)
        if ok and wrong and self.rng.random()<.35:
            self._generator_shock=self.rng.randint(1,5)
            self.hurt_world(self._generator_shock,tr('settlements.shock'))
        return ok

    @classmethod
    def load(cls,path):
        game=super().load(path);game.ensure_settlements();return game
