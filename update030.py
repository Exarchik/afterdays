"""Combat XP, physically visited settlements and atomic quick module insertion."""
import math,random,re
import content
import restoration
import progression as p
from i18n import t as tr
from world_layout import WIDTH

def event_xp(amount):
    return 0 if amount<=0 else 5 if amount<=10 else 10 if amount<=20 else 15 if amount<=30 else 20

def kill_xp(previous):
    return max(5,5*math.floor(previous/10+.5))

class Game(restoration.Game):
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

    def remember_visit(self):
        """Зберігає факт фізичного відвідування основного міста."""
        if not hasattr(self,'reputation_state'):return
        visits=self.reputation_state.setdefault('visited_cities',[0])
        if self.city is not None and self.city<self.main_city_count and self.city not in visits:visits.append(self.city)

    def _visit_objectives(self):
        """Оновлює завдання, пов’язані з відвідуванням поточної клітинки."""
        super()._visit_objectives();self.remember_visit()

    def eligible_settlements(self,role,exclude=None):
        """Знаходить міста без потрібного фахівця, виключаючи зарезервовані."""
        cities=super().eligible_settlements(role,exclude)
        # Permission can be requested in any eligible town after the quest is taken.
        # Only the initial encounter requires a physically visited eligible town.
        return cities

    def recruit_candidates(self,role):
        """Обмежує кандидатів поселення містами, які гравець уже відвідав."""
        self.remember_visit()
        visits=self.reputation_state.get('visited_cities',[0])
        return [city for city in self.eligible_settlements(role) if city in visits]

    def create_settler(self,role):
        """Створює мандрівного кандидата на поселення та його завдання."""
        if not self.recruit_candidates(role):return None
        return super().create_settler(role)

    def spawn_traveler(self):
        """Обирає й створює випадкового мандрівника поблизу гравця."""
        roles=[role for role in ('smith','tech','mayor') if self.recruit_candidates(role) and not any(n['role']==role and n['state']!='settled' for n in self.settlers())]
        if roles and self.city is None and self.rng.random()<.25:
            self.create_settler(self.rng.choice(roles));self.last_traveler_turn=self.turn
        else:
            # Skip restoration's broader eligibility check, keep ordinary travellers.
            super(restoration.Game,self).spawn_traveler()

    # Обчислює досвід за конкретного ворога.
    def enemy_xp(self,enemy):return kill_xp(super().enemy_xp(enemy))

    def resolve_event(self,choice):
        """Застосовує вибраний результат дорожньої події."""
        previous=getattr(self,'_event_xp_context',False)
        self._event_xp_context=bool(self.road_event)
        try:return super().resolve_event(choice)
        finally:self._event_xp_context=previous

    def gain_xp(self,amount):
        """Нараховує досвід і обробляє наслідки підвищення рівня."""
        return super().gain_xp(event_xp(amount) if getattr(self,'_event_xp_context',False) else amount)

    def quick_module(self,item_id,mod_id):
        """Вставляє модуль першим, повертаючи останній із заповненого спорядження."""
        item,mod=self.find(item_id),self.find(mod_id)
        if self.battle or not item or item.get('kind') not in ('weapon','armor','helmet') or item.get('quest_id') or not mod or mod not in self.bag or mod.get('quest_id') or item.get('slots',0)<1:return False
        if not self._module_allowed(item_id,mod_id):return False
        def change():
            self.bag.remove(mod)
            if len(item['modules'])>=item['slots']:self.bag.append(item['modules'].pop())
            item['modules'].insert(0,mod)
            p.mr.clamp_condition(item)
            self.log(tr('update030.module_added',name=mod['name'],item=item['name']))
            return True
        return self._change_gear(change)

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
