"""Persistent fence passages and nearby arena exits."""
import hexgrid
import world_hex
import update047

FENCE_HOLE_CHANCE = .08

class Game(update047.Game):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.last_world_entry=None

    def fence_hole(self,a,b):
        edge=sorted([list(a),list(b)])
        return edge in self.reputation_state.get('fence_holes',[])

    def unlock_cache(self,ident,angle):
        import event_results
        context=self.lock_context(ident)
        before=event_results.snapshot(self);start=len(self._events)
        result=super().unlock_cache(ident,angle)
        if result is True:
            report=event_results.finish(self,(context or {}).get('title','Відкрито сховок'),
                                        (context or {}).get('art','stash'),start,before)
            report['rows'][:0]=[e for e in (context or {}).pop('event_feedback',[]) if e['kind']=='text']
        return result

    def can_cross(self,a,b):
        return (self.border_open and self.fence_hole(a,b)) or super().can_cross(a,b)

    def fence_candidates(self):
        a=(self.x,self.y)
        return [b for b in world_hex.neighbors(*a,len(self.world[0]),len(self.world))
                if self.border_edge(a,b) and not self.checkpoint(a,b)
                and self.passable(*b) and not self.fence_hole(a,b)]

    def step(self,dx,dy):
        before=(self.x,self.y)
        self._entering_world=(before,(self.x+dx,self.y+dy))
        try:result=super().step(dx,dy)
        finally:self._entering_world=None
        if before!=(self.x,self.y):self.last_world_entry=[list(before),[self.x,self.y]]
        if result and before!=(self.x,self.y) and self.border_open and not self.battle and not self.road_event:
            if self.fence_candidates() and self.rng.random()<FENCE_HOLE_CHANCE:
                self.make_road_event('fence_hole')
        return result

    def make_road_event(self,key=None):
        if key=='fence_hole' and (not self.border_open or not self.fence_candidates()):return False
        return super().make_road_event(key)

    def open_fence_hole(self):
        if not self.border_open:return False
        candidates=self.fence_candidates()
        if not candidates:return False
        edge=sorted([[self.x,self.y],list(self.rng.choice(candidates))])
        self.reputation_state.setdefault('fence_holes',[]).append(edge)
        self.log('Відкрито прохід у паркані.',color='#9cdda8')
        self.emit('Прохід відкрито',color='#9cdda8')
        return True

    def nearby_exit(self,b):
        occupied=set(map(tuple,b['walls']))|{tuple(e['pos']) for e in b['enemies']}
        floor=set(map(tuple,b.get('floor',[(x,y) for y in range(b['h']) for x in range(b['w'])])))
        choices=[p for p in hexgrid.neighbors(*b['pos'],b['w'],b['h']) if p in floor and p not in occupied]
        # If every neighbour is occupied, the current cell is always accessible.
        return list(choices[0]) if choices else b['pos'][:]

    def check_faction_victory(self):
        b=self.battle;was=bool(b and b.get('safe_exit047'))
        result=super().check_faction_victory()
        if b and self.battle is b and b.get('safe_exit047') and not was:b['exit']=self.nearby_exit(b)
        return result

    def victory(self):
        b=self.battle;was=bool(b and b.get('cleared'))
        result=super().victory()
        if b and self.battle is b and b.get('cleared') and not was:b['exit']=self.nearby_exit(b)
        __import__('battle_results').finish(self,b,'Перемога')
        return result

    def flee(self):
        b=self.battle
        __import__('battle_results').begin(self)
        result=super().flee()
        if result:__import__('battle_results').finish(self,b,'Перемога' if b and b.get('cleared') else 'Відступ')
        return result

    def defeat(self):
        b=self.battle
        __import__('battle_results').begin(self)
        result=super().defeat()
        __import__('battle_results').finish(self,b,'Поразка')
        return result

    def search(self):
        b=self.battle
        __import__('battle_results').begin(self)
        result=super().search()
        __import__('battle_results').finish(self,b,'Перемога')
        return result

    def gain_xp(self,amount):
        __import__('battle_results').begin(self)
        return super().gain_xp(amount)
