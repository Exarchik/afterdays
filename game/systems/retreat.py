"""Retreat gameplay behavior."""
from i18n import t as tr


class RetreatMixin:
    @property
    def coward_turns(self):
        """Remaining overworld turns of the persistent retreat debuff."""
        return max(0,getattr(self,'reputation_state',{}).get('coward_until',0)-self.turn)

    @property
    def max_ap(self):
        """Apply the retreat penalty to the usual action point calculation."""
        return max(1,super().max_ap-bool(self.coward_turns))

    def flee(self):
        """Leave dungeons only at the exit; ordinary retreat is allowed from any cell."""
        b=self.battle
        if not b:return False
        if b.get('dungeon'):return super().flee()
        self.battle=None;self.quest_battle=None
        self.reputation_state['coward_until']=self.turn+50
        self.log(tr('update032.fled'));return True

    def rest(self):
        """Successful sleep removes the retreat debuff."""
        ok=super().rest()
        if ok:self.reputation_state.pop('coward_until',None)
        return ok
