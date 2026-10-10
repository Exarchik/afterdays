"""Equipment upgrades gameplay behavior."""
from game import items as item_rules
import module_rules

import copy

import random
import content

from i18n import t as tr

GEAR_KINDS=('weapon','armor','helmet','module')

def upgraded(item):
    """Build the next-level preview without changing identity, modules, condition or RNG."""
    level=item.get('level',1)+1;tier=item.get('rarity',0)
    if item['kind']=='module':
        result=copy.deepcopy(item)
        result.update(level=level,value=round(30*(tier+1)**2*level**1.3),
                      stats=module_rules.module_stats(item['type_id'],tier,level,item.get('tradeoff',False)))
    else:
        fresh=item_rules.equipment(item['type_id'],tier,random.Random(0),level)
        result=copy.deepcopy(item)
        for key in ('level','value','stats'):result[key]=fresh[key]
    result['upgrades']=item.get('upgrades',0)+1
    result['name']=content.name(item['type_id'])+' '+'★'*result['upgrades']
    return result


class EquipmentUpgradesMixin:
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
