"""Persistent road caches reuse the quest lock minigame and location-level loot."""
import math
import afterdays as r
import adventure,settlements
import progression as p
from i18n import t as tr

import event_catalog
import event_runtime
CACHE_TYPES={e['id'][7:]:e['terrain'] for e in event_catalog.EVENTS if e.get('legacy_group')=='cache'}

class Game(settlements.Game):
    @classmethod
    def load(cls,path):
        """Завантажує збереження та застосовує міграції цієї версії."""
        game=super().load(path)
        count=p.mr.migrate_game(game)
        if count:game.log(tr('modules.detached',count=count))
        return game

    def start_battle(self):
        """Створює бойовий стан, ворогів та арену поточної зустрічі."""
        super().start_battle()
        from arena_layout import build
        build(self)
        __import__('battle_results').begin(self,fresh=True)

    def road_cache(self,ident=None):
        """Знаходить дорожній сховок на поточній клітинці."""
        if self.battle or self.road_event:return None
        return next((c for c in self.reputation_state.get('road_caches',[]) if not c['opened'] and c['pos']==[self.x,self.y] and (ident is None or c['id']==ident)),None)

    def lock_context(self,ident):
        """Визначає квестовий або дорожній замок для мінігри."""
        cache=self.road_cache(ident)
        if cache:return cache
        q=self.local_expedition()
        return q if q and q['id']==ident and q['kind']=='cache' and q.get('cache_pos')==[self.x,self.y] else None

    def cache_contents(self,theme,level):
        """Compatibility entry point for the five original cache themes."""
        return event_runtime.cache_contents(self,event_catalog.BY_ID['locked_'+theme]['cache'],level)

    def begin_event_cache(self,spec):
        """Persist a snapshot of rolled loot; repeated attempts cannot reroll it."""
        cache=self.road_cache()
        if cache is None:
            level=self.region_level
            cache=dict(id=r.uid(),kind='road_cache',title=spec['title'],art=spec.get('art','stash'),theme=spec['id'].removeprefix('locked_'),pos=[self.x,self.y],level=level,
                       lock_target=self.rng.randint(15,165),opened=False,
                       contents=event_runtime.cache_contents(self,spec['cache'],level))
            self.reputation_state.setdefault('road_caches',[]).append(cache)
        self._lock_request=cache['id'];self.log(tr('cache_events.found'))
        return True

    def search(self):
        """Виконує пошук на місцевості та перевіряє квестові цілі."""
        cache=self.road_cache()
        if cache:self._lock_request=cache['id'];return True
        return super().search()

    def unlock_cache(self,ident,angle):
        """Обробляє результат відкриття замкненого сховку."""
        cache=self.road_cache(ident)
        if cache is None:return super().unlock_cache(ident,angle)
        if type(angle) not in (int,float) or not math.isfinite(angle) or not 0<=angle<=180 or self.count('parts')<1:return None
        if abs(angle-cache['lock_target'])>12:
            self.consume('parts');self.log(tr('update024.lock_fail'));return False
        cache['opened']=True
        for item in cache['contents']:p.add_to(self.loot,item)
        cache['contents']=[]
        self.log(tr('update024.lock_ok'));return True
