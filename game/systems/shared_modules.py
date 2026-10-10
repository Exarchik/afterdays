"""Shared modules gameplay behavior."""
import module_rules

import copy


class SharedModulesMixin:
    def available_modules(self,item):
        """List compatible bag modules plus accessible shared-storage modules."""
        source=self.bag+(self.stash if self.regular_city and not self.battle else [])
        return [m for m in source if module_rules.compatible(item,m) and m.get('level',1)<=self.level]

    def module_source_item(self,ident):
        """Resolve a module in accessible storage without exposing it to unrelated inventory actions."""
        return self.find(ident) or next((m for m in self.stash if m['id']==ident and m['kind']=='module'),None) if self.regular_city and not self.battle else self.find(ident)

    def _install_from_source(self,item_id,mod_id,slot=None):
        """Atomically transfer a storage module and install it, restoring all containers on failure."""
        mod=self.module_source_item(mod_id)
        operation=super().install if slot is None else super().put_module
        if not mod or mod not in self.stash:return operation(item_id,mod_id) if slot is None else operation(item_id,mod_id,slot)
        before=copy.deepcopy((self.bag,self.stash,self.equipped,self.hp))
        self.stash.remove(mod);self.bag.append(mod)
        ok=operation(item_id,mod_id) if slot is None else operation(item_id,mod_id,slot)
        if not ok:self.bag,self.stash,self.equipped,self.hp=before
        return ok

    def install(self,item_id,mod_id):
        """Install a module from the bag or locally accessible storage."""
        return self._install_from_source(item_id,mod_id)

    def put_module(self,item_id,mod_id,slot_index):
        """Replace a module using either accessible source; displaced modules return to the bag."""
        return self._install_from_source(item_id,mod_id,slot_index)
