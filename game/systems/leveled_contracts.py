"""Leveled contracts gameplay behavior."""
from game import catalog as game_catalog

import world_hex

from i18n import t as tr

def level_limit(delta):
    """Return the quest ceiling for player level minus city level."""
    if delta<=-3:return 0
    if delta==-2 or delta>=4:return 1
    if delta==-1 or delta==3:return 2
    if delta==2:return 3
    return 5


class LeveledContractsMixin:
    def quest_capacity(self,city):
        """Combine reputation capacity with city/player level difference."""
        cap=super().quest_capacity(city)
        return min(cap,level_limit(self.level-self.region_at(*self.cities[city]))) if city in self.mayors else cap

    def price_quest(self,q):
        """Honoured cities issue unaccepted contracts one level above the city to stronger players."""
        if q.get('status')=='offered' and not q.get('scribe') and q.get('city') in self.mayors:
            level=self.region_at(*self.cities[q['city']])
            if self.welcomed(q['city']) and self.level>level:
                if q.get('level')!=level+1:q.pop('reward_items',None)
                q['level']=q['zone']=level+1
        super().price_quest(q)

    @property
    def scribe(self):
        """Whether the current traveller is a quest-giving scribe."""
        return bool(not self.battle and self.traveler and self.traveler.get('scribe') and self.traveler.get('pos')==[self.x,self.y])

    def spawn_scribe(self):
        """Generate one to three persistent contracts returned to the nearest main town."""
        city=min(range(self.main_city_count),key=lambda n:world_hex.distance(self.cities[n],(self.x,self.y)))
        level=self.region_at(*self.cities[city]);offers=[]
        for kind in self.rng.sample(['hunt','supplies','scout'],self.rng.randint(1,3)):
            q=dict(id=game_catalog.uid(),kind=kind,city=city,status='offered',title=game_catalog.QUEST_LABELS[kind],progress=0,goal=self.rng.randint(2,5) if kind=='hunt' else 1,target_kind=None,pos=None,unique=False,level=level,zone=level,scribe=True,issuer_pos=[self.x,self.y],food_need=2,med_need=1,scaled=True,distance_scaled=True,cycle_named=True)
            self.price_quest(q);offers.append(q)
        self.traveler=dict(scribe=True,pos=[self.x,self.y],items=[],offers=offers)
        self.last_traveler_turn=self.turn
        self.reveal(*self.cities[city],1)
        if city not in self.known_cities:self.known_cities.append(city)
        self.log(tr('update032.scribe_found',city=self.city_name(city)))

    def spawn_traveler(self):
        """Add a scribe to the travelling encounter pool without removing existing travellers."""
        if self.rng.random()<.15:self.spawn_scribe()
        else:super().spawn_traveler()

    def available_merchant(self,m):
        """A scribe is a quest giver, not a travelling shop."""
        return False if self.scribe and m in (3,4) else super().available_merchant(m)

    def mayor_offers(self):
        """Expose scribe offers or apply final city limits, including special mayor offers."""
        if self.scribe:return [q for q in self.traveler['offers'] if q['status']=='offered']
        offers=super().mayor_offers()
        if self.city is None:return offers
        for q in offers:
            if q['status']=='offered':self.price_quest(q)
        slots=max(0,self.quest_capacity(self.city)-len(self.active_for(self.city)))
        return [q for q in offers if q['status']=='offered'][:slots]

    def quest_text(self,q):
        """Display the town where a travelling scribe's contract must be returned."""
        text=super().quest_text(q)
        return text+'\n'+tr('update032.scribe_return',city=self.city_name(q['city'])) if q.get('scribe') else text
