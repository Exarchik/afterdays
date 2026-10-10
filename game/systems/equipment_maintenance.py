"""Equipment maintenance gameplay behavior."""
import module_rules

import math

from i18n import t as tr


class EquipmentMaintenanceMixin:
    def can_repair_with_kit(self,item):
        """Damaged weapons at or below twenty percent require a technician."""
        return bool(not self.battle and item and (item['kind'] in ('weapon','armor','helmet') or item.get('quest_repair')) and module_rules.condition(item)<100 and self.count('repairkit') and not (item['kind']=='weapon' and module_rules.condition(item)<=20))

    def repair_with_kit(self,ident):
        """Validate the condition threshold before consuming the kit."""
        if not self.can_repair_with_kit(self.find(ident)):
            self.log(tr('update033.kit_limit'));return False
        return super().repair_with_kit(ident)

    def salvage_yield(self,item):
        """Double the existing level/condition-based material return (up to 200)."""
        return 2*super().salvage_yield(item)

    def dismantle(self,ident):
        """Consume one repair kit only when carried nonquest gear is successfully dismantled."""
        if self.count('repairkit')<1:self.log(tr('update033.no_kit'));return False
        ok=super().dismantle(ident)
        if ok:self.consume('repairkit')
        return ok

    def dismantle_quote(self,ident):
        """Return technician material yield and ten percent of condition-adjusted base value."""
        item=next((i for i in self.bag if i['id']==ident),None)
        if self.battle or self.road_event or self.city not in self.technicians or not item or item['kind'] not in ('weapon','armor','helmet') or item.get('quest_id'):return None
        return self.salvage_yield(item),max(1,math.ceil(item['value']*module_rules.condition(item)/100*.1))

    def technician_dismantle(self,ident):
        """Pay the workshop instead of consuming a kit; preserve installed modules."""
        quote=self.dismantle_quote(ident)
        if not quote or self.money<quote[1]:return False
        ok=super().dismantle(ident)
        if ok:self.money-=quote[1]
        return ok
