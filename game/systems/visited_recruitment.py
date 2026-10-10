"""Visited recruitment gameplay behavior."""
from game.systems import restoration


class VisitedRecruitmentMixin:
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
            super(restoration.RestorationMixin,self).spawn_traveler()
