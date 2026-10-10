"""Quick modules gameplay behavior."""
import module_rules

from i18n import t as tr


class QuickModulesMixin:
    def quick_module(self,item_id,mod_id):
        """Вставляє модуль першим, повертаючи останній із заповненого спорядження."""
        item,mod=self.find(item_id),self.find(mod_id)
        if self.battle or not item or item.get('kind') not in ('weapon','armor','helmet') or item.get('quest_id') or not mod or mod not in self.bag or mod.get('quest_id') or item.get('slots',0)<1:return False
        if not self._module_allowed(item_id,mod_id):return False
        def change():
            self.bag.remove(mod)
            if len(item['modules'])>=item['slots']:self.bag.append(item['modules'].pop())
            item['modules'].insert(0,mod)
            module_rules.clamp_condition(item)
            self.log(tr('update030.module_added',name=mod['name'],item=item['name']))
            return True
        return self._change_gear(change)
