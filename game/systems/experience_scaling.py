"""Experience scaling gameplay behavior."""
import math

def event_xp(amount):
    return 0 if amount<=0 else 5 if amount<=10 else 10 if amount<=20 else 15 if amount<=30 else 20

def kill_xp(previous):
    return max(5,5*math.floor(previous/10+.5))


class ExperienceScalingMixin:
    def enemy_xp(self,enemy):return kill_xp(super().enemy_xp(enemy))

    def resolve_event(self,choice):
        """Застосовує вибраний результат дорожньої події."""
        previous=getattr(self,'_event_xp_context',False)
        self._event_xp_context=False  # Catalog XP is already the final balanced amount.
        try:return super().resolve_event(choice)
        finally:self._event_xp_context=previous

    def gain_xp(self,amount):
        """Нараховує досвід і обробляє наслідки підвищення рівня."""
        return super().gain_xp(event_xp(amount) if getattr(self,'_event_xp_context',False) else amount)
