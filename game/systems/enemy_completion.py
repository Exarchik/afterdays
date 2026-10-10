"""Enemy completion gameplay behavior."""


class EnemyCompletionMixin:
    def _finish_enemy(self,enemy,weapon=None):
        """Finish monsters without equipment bonuses, including mythic creatures."""
        b=self.battle
        if not b or enemy not in b['enemies']:return
        return super()._finish_enemy(enemy,weapon)
