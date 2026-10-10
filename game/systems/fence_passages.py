"""Fence passages gameplay behavior."""
import world_hex

FENCE_HOLE_CHANCE = .08


class FencePassagesMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.last_world_entry=None

    def fence_hole(self,a,b):
        edge=sorted([list(a),list(b)])
        return edge in self.reputation_state.get('fence_holes',[])

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
