"""Starter-zone edge barriers and a permanent mayor-issued checkpoint permit."""
from collections import deque
import afterdays as r
from i18n import t as tr

class Border:
    @property
    def border_open(self):
        self.init_reputation()
        return self.reputation_state.get('border_open',False)

    def inside_border(self,pos):
        return self.region_at(*pos)<=2

    def border_edge(self,a,b):
        return self.inside_border(a)!=self.inside_border(b)

    def checkpoint(self,a,b):
        return self.border_edge(a,b) and all(self.world[y][x] in ('road','city') for x,y in (a,b))

    def can_cross(self,a,b):
        if not self.border_edge(a,b):return True
        # Returning players from older saves outside the fence can come home.
        return self.checkpoint(a,b) and (self.border_open or self.inside_border(b))

    def border_edges(self):
        if not hasattr(self,'_border_edges'):
            self._border_edges=[]
            for y in range(32):
                for x in range(48):
                    for b in ((x+1,y),(x,y+1)):
                        if b[0]<48 and b[1]<32 and self.border_edge((x,y),b):self._border_edges.append(((x,y),b))
        return self._border_edges

    def can_step(self,dx,dy):
        return super().can_step(dx,dy) and self.can_cross((self.x,self.y),(self.x+dx,self.y+dy))

    def step(self,dx,dy):
        a=(self.x,self.y);b=(self.x+dx,self.y+dy)
        if not self.battle and abs(dx)+abs(dy)==1 and self.passable(*b) and not self.can_cross(a,b):
            text=tr('border.locked') if self.checkpoint(a,b) else tr('border.fence')
            self.log(text);self.emit(text,color='#eea18b');return False
        return super().step(dx,dy)

    def player_reachable_world(self,start):
        seen={tuple(start)};queue=deque(seen)
        while queue:
            a=queue.popleft()
            for b in r.neighbors(*a,48,32):
                if b not in seen and self.passable(*b) and self.can_cross(a,b):seen.add(b);queue.append(b)
        return seen

    def quest_locations(self,q):
        reachable=self.player_reachable_world(self.cities[q['city']])
        return [pos for pos in super().quest_locations(q) if pos in reachable]

    def metro_cost(self,destination):
        if not self.border_open and destination in range(len(self.cities)) and self.inside_border((self.x,self.y)) and not self.inside_border(self.cities[destination]):return None
        return super().metro_cost(destination)

    def check_border_quest(self):
        if self.border_open or any(q['kind']=='permit' for q in self.quests):return
        eligible=[i for i in range(12) if self.reputation(i)>=75]
        if not eligible:return
        city=self.city if self.city in eligible else min(eligible,key=lambda i:(i not in self.known_cities,abs(self.cities[i][0]-self.x)+abs(self.cities[i][1]-self.y)))
        if city not in self.mayors:self.mayors.append(city)
        self.quests.append(dict(id=r.uid(),kind='permit',city=city,status='active',title=tr('border.title'),
            progress=1,goal=1,target_kind=None,pos=self.cities[city][:],unique=False,level=self.region_at(*self.cities[city]),reward=0,xp_reward=0))
        self._border_notice=tr('border.invitation',city=self.city_name(city))
        self.log(self._border_notice)

    def check_thanks(self):
        self.check_border_quest()
        return super().check_thanks()

    def turn_in(self,quest_id):
        q=next((q for q in self.quests if q['id']==quest_id),None)
        if q and q['kind']=='permit':
            if self.battle or self.city!=q['city'] or not self.quest_ready(q):return False
            q['status']='done';self.reputation_state['border_open']=True
            self.add_reputation(4,city=q['city'])
            self._border_notice=tr('border.granted',city=self.city_name(q['city']))
            self.log(self._border_notice);return True
        return super().turn_in(quest_id)

    def quest_text(self,q):
        if q['kind']=='permit':return tr('border.quest_done') if q['status']=='done' else tr('border.quest',city=self.city_name(q['city']))
        return super().quest_text(q)
