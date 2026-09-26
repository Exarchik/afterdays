"""Workshop upgrades, bulk module removal and city guides."""
import copy
import math
import random
import content
import progression as p
import update030
from journey import world_route,route_distance
from i18n import t as tr

GEAR_KINDS=('weapon','armor','helmet','module')

def upgraded(item):
    """Build the next-level preview without changing identity, modules, condition or RNG."""
    level=item.get('level',1)+1;tier=item.get('rarity',0)
    if item['kind']=='module':
        result=copy.deepcopy(item)
        result.update(level=level,value=round(30*(tier+1)**2*level**1.3),
                      stats=p.mr.module_stats(item['type_id'],tier,level,item.get('tradeoff',False)))
    else:
        fresh=p.equipment(item['type_id'],tier,random.Random(0),level)
        result=copy.deepcopy(item)
        for key in ('level','value','stats'):result[key]=fresh[key]
    result['upgrades']=item.get('upgrades',0)+1
    result['name']=content.name(item['type_id'])+' '+'★'*result['upgrades']
    return result

class Game(update030.Game):
    def upgrade_quote(self,ident):
        """Return the next item and base-price difference; only owned nonquest gear qualifies."""
        item=self.find(ident)
        if self.battle or self.road_event or self.city not in self.technicians or not item or item.get('kind') not in GEAR_KINDS or item.get('quest_id') or item.get('upgrades',0)>=3 or item.get('level',1)>=self.level:return None
        if not any(i and i['id']==ident for i in self.bag+list(self.equipped.values())):return None
        result=upgraded(item)
        return result,max(0,result['value']-item['value'])

    def upgrade_item(self,ident):
        """Pay once and replace owned item stats with the next-level preview, at most three times."""
        quote=self.upgrade_quote(ident)
        if not quote:return False
        result,cost=quote
        if self.money<cost:return False
        item=self.find(ident)
        def change():
            item.clear();item.update(result);return True
        if not self._change_gear(change):return False
        self.money-=cost
        self.log(tr('update031.upgraded',name=result['name'],level=result['level'],cost=cost))
        return True

    def remove_modules(self,ident):
        """Return every installed module to the bag atomically; reject overloads and combat."""
        item=self.find(ident)
        if self.battle or not item or item.get('kind') not in GEAR_KINDS[:3] or item.get('quest_id') or not item.get('modules'):return False
        def change():
            self.bag.extend(item['modules']);item['modules']=[];return True
        return self._change_gear(change)

    @property
    def city_guide(self):
        """Offer a guide in some towns for a stable 100-turn period without rolling on UI refresh."""
        return bool(not self.battle and self.regular_city and random.Random(f'city-guide:{self.cities[self.city]}:{self.turn//100}').random()<.25)

    @property
    def guide(self):
        """Allow the same paid-travel service at a travelling guide or an available town guide."""
        return super().guide or self.city_guide

    def guide_destinations(self):
        """Offer five nearest reachable towns from a town guide; travelling guides retain three known towns."""
        if not self.city_guide:return super().guide_destinations()
        choices=[]
        for city,pos in enumerate(self.cities[:self.main_city_count]):
            if city==self.city or city not in self.known_cities:continue
            route=world_route(self,pos)
            if not route:continue
            distance=route_distance((self.x,self.y),route)
            choices.append(dict(city=city,distance=distance,steps=math.floor(distance+self.world_distance_remainder+1e-9),price=min(100,20+2*math.ceil(distance)),route=route))
        return sorted(choices,key=lambda c:(c['distance'],c['city']))[:5]
