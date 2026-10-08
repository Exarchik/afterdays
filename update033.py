import world_hex
"""Shared-storage modules, maintenance costs and exploration updates for v0.33."""
import copy,math
import update032,combat033,storm033
import progression as p
from i18n import t as tr

class Game(combat033.Combat,storm033.Storms,update032.Game):
    def available_modules(self,item):
        """List compatible bag modules plus accessible shared-storage modules."""
        source=self.bag+(self.stash if self.regular_city and not self.battle else [])
        return [m for m in source if p.mr.compatible(item,m) and m.get('level',1)<=self.level]

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

    def can_repair_with_kit(self,item):
        """Damaged weapons at or below twenty percent require a technician."""
        return bool(not self.battle and item and (item['kind'] in ('weapon','armor','helmet') or item.get('quest_repair')) and p.mr.condition(item)<100 and self.count('repairkit') and not (item['kind']=='weapon' and p.mr.condition(item)<=20))

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
        return self.salvage_yield(item),max(1,math.ceil(item['value']*p.mr.condition(item)/100*.1))

    def technician_dismantle(self,ident):
        """Pay the workshop instead of consuming a kit; preserve installed modules."""
        quote=self.dismantle_quote(ident)
        if not quote or self.money<quote[1]:return False
        ok=super().dismantle(ident)
        if ok:self.money-=quote[1]
        return ok

    def _finish_enemy(self,enemy,weapon=None):
        """Finish monsters without equipment bonuses, including mythic creatures."""
        b=self.battle
        if not b or enemy not in b['enemies']:return
        return super()._finish_enemy(enemy,weapon)

    def _reveal_notice(self,before):
        """Queue one bounded, short highlight for newly discovered cells."""
        queued={tuple(c) for e in getattr(self,'_events',[]) if e['kind']=='reveal' for c in e.get('cells',[])}
        cells=[list(map(int,key.split(','))) for key in set(self.explored)-before if tuple(map(int,key.split(','))) not in queued]
        if cells:
            self.emit(kind='reveal',scene='world',pos=[self.x,self.y],color='#9de5b2')
            self._events[-1]['cells']=cells
            self._events[-1]['blocking']=not getattr(self,'_walking_reveal',False)
            if getattr(self,'_event_feedback_color',None):self.emit(f'Відкриття мапи: +{len(cells)} клітинок')

    def buy_map(self):
        """Animate newly opened map cells after a successful cartographer purchase."""
        before=set(self.explored);ok=super().buy_map()
        if ok:self._reveal_notice(before)
        return ok

    def resolve_event(self,choice):
        """Animate any terrain revealed by an accepted road-event outcome."""
        before=set(self.explored);ok=super().resolve_event(choice)
        if ok:self._reveal_notice(before)
        return ok

    def turn_in(self,ident):
        """Check mayor-map eligibility after the quest's reputation reward has been applied."""
        ok=super().turn_in(ident);city=self.city
        if ok and city is not None and city<self.main_city_count and city in self.mayors and city not in self.map_rewards and self.reputation(city)>50 and sum(q['status']=='done' and q['city']==city for q in self.quests)>5:
            nearby=sorted((n for n in range(self.main_city_count) if n not in self.known_cities),key=lambda n:world_hex.distance(self.cities[n],self.cities[city]))[:1]
            if nearby:
                self.map_rewards.append(city);self.reveal(*self.cities[nearby[0]],0)
                self._mayor_notice=tr('border.city_reveal',city=self.city_name(city),destination=self.city_name(nearby[0]));self.log(self._mayor_notice)
        return ok
