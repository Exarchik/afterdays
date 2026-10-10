"""State migrations gameplay behavior."""
import random; import re
import content

from i18n import t as tr
from world_layout import WIDTH
from game.systems.experience_scaling import event_xp


class StateMigrationsMixin:
    def __init__(self,seed=None):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        super().__init__(seed)
        self.remember_visit()
        self.reputation_state['rules030']=True

    def accept_quest(self,ident):
        """Приймає завдання і створює його цілі та необхідні квестові предмети."""
        ok=super().accept_quest(ident)
        if ok:
            q=next(q for q in self.quests if q['id']==ident)
            if q.get('target_kind') is not None:q['target_type_id']=content.monster_id(q['target_kind'])
        return ok

    @classmethod
    def load(cls,path):
        """Завантажує збереження та застосовує міграції цієї версії."""
        game=super().load(path)
        if not game.reputation_state.get('rules030'):
            if game.road_event:
                def update_text(value):
                    return re.sub(r'([0-9]+) XP',lambda m:f'{event_xp(int(m[1]))} XP',value)
                for key in ('body','title'):game.road_event[key]=update_text(game.road_event[key])
                game.road_event['choices']=[[key,update_text(label)] for key,label in game.road_event['choices']]
            game.reputation_state['rules030']=True
        old=len(game.world[0])
        if old<WIDTH:
            # Saved coordinates, cities, quests and combat RNG stay intact.
            rng=random.Random('east-extension:'+repr(game.rng.getstate()))
            for row in game.world:row.extend(rng.choices(('waste','forest','ruin','cliff','water'),(65,20,10,3,2),k=WIDTH-old))
            reachable=game.reachable_world((5,5))
            if not any(x>=old for x,y in reachable):
                x,y=max(reachable,key=lambda pos:pos[0])
                for xx in range(x+1,WIDTH):
                    if game.world[y][xx] in ('water','cliff') or xx>=old:game.world[y][xx]='road'
            else:
                x,y=next((x,y) for x,y in sorted(reachable) if x==old)
                for xx in range(old,WIDTH):game.world[y][xx]='road'
            if hasattr(game,'_border_edges'):del game._border_edges
            game.log(tr('update030.world_extended'))
        game.remember_visit()
        return game
