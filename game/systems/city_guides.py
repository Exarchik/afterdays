"""City guides gameplay behavior."""
import math
import random

from game.systems.journey import world_route,route_distance


class CityGuidesMixin:
    @property
    def city_guide(self):
        """Offer a guide in some towns for a stable 100-turn period without rolling on UI refresh."""
        return bool(not self.battle and self.regular_city and random.Random(f'city-guide:{self.cities[self.city]}:{self.turn//100}').random()<.25)

    @property
    def guide(self):
        """Allow the same paid-travel service at a travelling guide or an available town guide."""
        return super().guide or self.city_guide

    def guide_destinations(self):
        """Offer five nearest reachable towns from a town guide; travelling guides retain three known towns."""
        if not self.city_guide:return super().guide_destinations()
        choices=[]
        for city,pos in enumerate(self.cities[:self.main_city_count]):
            if city==self.city or city not in self.known_cities:continue
            route=world_route(self,pos)
            if not route:continue
            distance=route_distance((self.x,self.y),route)
            choices.append(dict(city=city,distance=distance,steps=math.floor(distance+self.world_distance_remainder+1e-9),price=min(100,20+2*math.ceil(distance)),route=route))
        return sorted(choices,key=lambda c:(c['distance'],c['city']))[:5]
