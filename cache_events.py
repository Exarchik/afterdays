"""Persistent road caches reuse the quest lock minigame and location-level loot."""
import math
import afterdays as r
import adventure,settlements
import progression as p
from i18n import t as tr

CACHE_TYPES={'medical':'ruin','armory':'road','workshop':'ruin','provisions':'forest','research':'waste'}
for name,terrain in CACHE_TYPES.items():
    key='locked_'+name
    adventure.EXTRA_EVENTS[key]=(terrain,tr('cache_events.'+name+'.title'),tr('cache_events.'+name+'.story'),[('act',tr('cache_events.open')),('leave',tr('adventure.0135'))])
    adventure.ROAD_EVENTS.append((key,*adventure.EXTRA_EVENTS[key][1:]))

class Game(settlements.Game):
    @classmethod
    def load(cls,path):
        game=super().load(path)
        count=p.mr.migrate_game(game)
        if count:game.log(tr('modules.detached',count=count))
        return game

    def start_battle(self):
        super().start_battle()
        from organic_arenas import arena
        arena(self)

    def road_cache(self,ident=None):
        if self.battle or self.road_event:return None
        return next((c for c in self.reputation_state.get('road_caches',[]) if not c['opened'] and c['pos']==[self.x,self.y] and (ident is None or c['id']==ident)),None)

    def lock_context(self,ident):
        cache=self.road_cache(ident)
        if cache:return cache
        q=self.local_expedition()
        return q if q and q['id']==ident and q['kind']=='cache' and q.get('cache_pos')==[self.x,self.y] else None

    def cache_contents(self,theme,level):
        amount=1+min(3,(level-1)//4);ammo=6+2*level
        if theme=='medical':items=[p.supply('med',amount+1),p.supply('rad',amount)]
        elif theme=='armory':items=[p.ammunition(self.rng.choice(list(p.AMMO)),ammo*2),p.supply('repairkit')]
        elif theme=='workshop':items=[p.parts(5+level*3),p.fragments(5+level*2),p.supply('repairkit')]
        elif theme=='provisions':items=[p.supply('food',amount+2),p.supply('med',amount),p.ammunition(self.rng.choice(list(p.AMMO)),ammo)]
        else:items=[p.supply('rad',amount),p.ammunition('energy',ammo),p.fragments(5+level*2)]
        if self.rng.random()<.25:
            gear=self.reward_item(cap=min(3,1+level//4),level=self.rng.randint(max(1,level-2),level))
            if 'durability' in gear:gear['durability']=float(self.rng.randint(30,90))
            items.append(gear)
        return items

    def resolve_event(self,choice):
        event=self.road_event
        if not event or event['kind'] not in {'locked_'+k for k in CACHE_TYPES}:return super().resolve_event(choice)
        if choice not in ('act','leave'):return False
        if choice=='leave':self.road_event=None;return True
        self.road_event=None
        cache=self.road_cache()
        if cache is None:
            theme=event['kind'][7:];level=self.region_level
            cache=dict(id=r.uid(),kind='road_cache',title=event['title'],theme=theme,pos=[self.x,self.y],level=level,
                       lock_target=self.rng.randint(15,165),opened=False,contents=self.cache_contents(theme,level))
            self.reputation_state.setdefault('road_caches',[]).append(cache)
        self._lock_request=cache['id'];self.log(tr('cache_events.found'));return True

    def search(self):
        cache=self.road_cache()
        if cache:self._lock_request=cache['id'];return True
        return super().search()

    def unlock_cache(self,ident,angle):
        cache=self.road_cache(ident)
        if cache is None:return super().unlock_cache(ident,angle)
        if type(angle) not in (int,float) or not math.isfinite(angle) or not 0<=angle<=180 or self.count('parts')<1:return None
        if abs(angle-cache['lock_target'])>12:
            self.consume('parts');self.log(tr('update024.lock_fail'));return False
        cache['opened']=True
        for item in cache['contents']:p.add_to(self.loot,item)
        cache['contents']=[]
        self.log(tr('update024.lock_ok'));return True
