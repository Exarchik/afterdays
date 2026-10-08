"""Reachable overworld routes and occasional travelling guides."""
import heapq
import world_hex
import math
from i18n import t as tr


def world_edge(game,a,b):
    """Only a shared hex edge can be crossed; there are no square corners."""
    if tuple(b) not in world_hex.adjacent(a) or not game.passable(*b):return False
    return getattr(game,'can_cross',lambda a,b:True)(a,b)



def route_distance(start,path):
    return sum(world_hex.distance(a,b) for a,b in zip([tuple(start)]+path,path))


def route_terrain_cost(game,pos):
    """Planning preference only: every actual move still consumes one turn."""
    world=getattr(game,'world',None)
    if world is None:return 1.0
    x,y=pos
    if world[y][x]=='road':return 1.0
    for nxt in world_hex.neighbors(x,y,len(world[0]),len(world)):
        if world[nxt[1]][nxt[0]]=='road' and world_edge(game,pos,nxt):return 1.15
    return 1.35


def world_route(game,destination,start=None):
    start=tuple(start or (game.x,game.y));destination=tuple(destination)
    if start==destination or not game.passable(*destination):return []
    # The minimum terrain cost is 1, so hex distance remains admissible.
    terrain_cost={}
    def estimate(p):return world_hex.distance(p,destination)
    previous={start:None};cost={start:0};queue=[(estimate(start),0,start)]
    while queue:
        _,distance,a=heapq.heappop(queue)
        if distance>cost[a]+1e-10:continue
        if a==destination:
            path=[]
            while a!=start:path.append(a);a=previous[a]
            return path[::-1]
        for b in world_hex.adjacent(a):
            if not world_edge(game,a,b):continue
            if b not in terrain_cost:terrain_cost[b]=route_terrain_cost(game,b)
            candidate=distance+terrain_cost[b]
            if candidate>=cost.get(b,float('inf'))-1e-10:continue
            cost[b]=candidate;previous[b]=a
            heapq.heappush(queue,(candidate+estimate(b),candidate,b))
    return []


class Guides:
    @property
    def guide(self):
        """Перевіряє доступність послуг провідника."""
        return bool(not self.battle and self.traveler and self.traveler.get('guide') and self.traveler['pos']==[self.x,self.y])

    def available_merchant(self,merchant):
        """Перевіряє доступність вказаного торговця у поточній локації."""
        if self.traveler and self.traveler.get('guide') and self.traveler.get('pos')==[self.x,self.y] and merchant in (3,4):return False
        return super().available_merchant(merchant)

    def guide_destinations(self):
        """Повертає доступні міста, маршрути й ціни провідника."""
        choices=[]
        for city in range(self.main_city_count):
            if city not in self.known_cities or self.cities[city]==[self.x,self.y]:continue
            route=world_route(self,self.cities[city])
            if route:
                distance=route_distance((self.x,self.y),route)
                choices.append(dict(city=city,distance=distance,steps=int(distance),price=min(100,20+2*math.ceil(distance)),route=route))
        return sorted(choices,key=lambda c:(c['distance'],c['city']))[:3]

    def spawn_traveler(self):
        """Обирає й створює випадкового мандрівника поблизу гравця."""
        if self.rng.random()<.30 and self.guide_destinations():
            self.traveler=dict(guide=True,pos=[self.x,self.y],items=[])
            self.last_traveler_turn=self.turn
            self.log(tr('journey.guide_found'));self.emit(tr('journey.guide'),color='#ecd594')
            return True
        return super().spawn_traveler()

    def guide_travel(self,city):
        """Оплачує безпечну подорож провідником і проходить маршрут."""
        if not self.guide or self.road_event:return False
        choice=next((c for c in self.guide_destinations() if c['city']==city),None)
        if choice is None:return False
        if self.money<choice['price']:self.log(tr('journey.no_money'));return False
        self.money-=choice['price']
        self._guided_trip=True
        try:
            for x,y in choice['route']:
                if not self.step(x-self.x,y-self.y) or (self.x,self.y)!=(x,y):return False
        finally:self._guided_trip=False
        self.log(tr('journey.arrived',city=self.city_name(city),steps=choice['steps']))
        return True
