import world_hex
"""Persistent radiation storms advance by world turns and eventually leave the map."""
import random
from i18n import t as tr

class Storms:
    def __init__(self,*args,**kwargs):
        """Initialize the weather clock without changing existing generation randomness."""
        super().__init__(*args,**kwargs)
        self.reputation_state.setdefault('storm033_turn',self.turn)

    @classmethod
    def load(cls,path):
        """Add the weather clock to old saves without retroactively simulating storms."""
        game=super().load(path)
        game.reputation_state.setdefault('storm033_turn',game.turn)
        return game

    @property
    def storm(self):
        """Return the active storm without introducing new top-level save fields."""
        return getattr(self,'reputation_state',{}).get('storm033')

    def storm_cells(self):
        """Return clipped cells in the storm's small circular footprint."""
        s=self.storm
        if not s:return []
        x,y=s['pos'];r=s['radius']
        return [(a,b) for a,b in world_hex.disk((x,y),r) if 0<=a<len(self.world[0]) and 0<=b<len(self.world)]

    def advance_storm(self):
        """Advance once per elapsed turn; spawn occasionally and drift one hex edge per tick."""
        state=self.reputation_state;last=state.get('storm033_turn',self.turn-1)
        for tick in range(last+1,self.turn+1):
            rng=random.Random(f'storm033:{self.cities[:self.main_city_count]}:{tick}')
            s=self.storm
            if not s:
                if rng.random()<.006:
                    direction=rng.choice([-1,1]);radius=rng.randint(1,2)
                    s=dict(pos=[0 if direction==1 else len(self.world[0])-1,rng.randrange(len(self.world))],radius=radius,direction=direction,age=0)
                    state['storm033']=s;self.log(tr('update033.storm_found'))
                continue
            s['age']+=1
            if s['age']>2*(len(self.world)+len(self.world[0])) or rng.random()<.7:s['pos'][0]+=s['direction']
            else:s['pos']=list(world_hex.adjacent(s['pos'])[rng.choice((1,5) if s['direction']==1 else (2,4))])
            x,y=s['pos'];r=s['radius']
            if x < -r or y < -r or x>=len(self.world[0])+r or y>=len(self.world)+r:state.pop('storm033',None)
        state['storm033_turn']=self.turn

    def _world_time_tick(self):
        """Move the storm with world time and apply radiation unless protected or travelling safely."""
        protected=self.rad_turns>0
        ok=super()._world_time_tick();self.advance_storm()
        if ok and not self.regular_city and not getattr(self,'_guided_trip',False) and not protected and (self.x,self.y) in self.storm_cells():return self.hurt_world(2,tr('update033.storm_hit'))
        return ok

    def search(self):
        """Advance storms for turns consumed while searching a world location."""
        before=self.turn;protected=self.rad_turns>0;ok=super().search()
        if self.turn>before:
            self.advance_storm()
            if ok and not self.battle and not self.regular_city and not protected and (self.x,self.y) in self.storm_cells():self.hurt_world(2,tr('update033.storm_hit'))
        return ok

    def rest(self):
        """Let weather advance during sleep without damaging a sheltered player."""
        ok=super().rest()
        if ok:self.advance_storm()
        return ok

    def metro_travel(self,city):
        """Advance weather during safe underground travel."""
        ok=super().metro_travel(city)
        if ok:self.advance_storm()
        return ok
