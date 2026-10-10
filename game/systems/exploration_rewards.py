"""Exploration rewards gameplay behavior."""
import world_hex

from i18n import t as tr


class ExplorationRewardsMixin:
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
