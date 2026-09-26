"""Reachable overworld routes and occasional travelling guides."""
import heapq
import math
from i18n import t as tr


def world_edge(game,a,b):
    """A diagonal requires both corner cells and all four border edges open."""
    dx,dy=b[0]-a[0],b[1]-a[1]
    if max(abs(dx),abs(dy))!=1 or not game.passable(*b):return False
    cross=getattr(game,'can_cross',lambda a,b:True)
    if not dx or not dy:return cross(a,b)
    c=(a[0]+dx,a[1]);d=(a[0],a[1]+dy)
    return (game.passable(*c) and game.passable(*d)
            and all(cross(p,q) for p,q in ((a,c),(c,b),(a,d),(d,b))))


def route_distance(start,path):
    return sum(math.dist(a,b) for a,b in zip([tuple(start)]+path,path))


def world_route(game,destination,start=None):
    start=tuple(start or (game.x,game.y));destination=tuple(destination)
    if start==destination or not game.passable(*destination):return []
    def estimate(p):
        dx,dy=abs(p[0]-destination[0]),abs(p[1]-destination[1])
        return max(dx,dy)+(math.sqrt(2)-1)*min(dx,dy)
    previous={start:None};cost={start:0};queue=[(estimate(start),0,start)]
    while queue:
        _,distance,a=heapq.heappop(queue)
        if distance>cost[a]+1e-10:continue
        if a==destination:
            path=[]
            while a!=start:path.append(a);a=previous[a]
            return path[::-1]
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            b=(a[0]+dx,a[1]+dy)
            if not world_edge(game,a,b):continue
            candidate=distance+math.hypot(dx,dy)
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
                choices.append(dict(city=city,distance=distance,steps=math.floor(distance+self.world_distance_remainder+1e-9),price=min(100,20+2*math.ceil(distance)),route=route))
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
