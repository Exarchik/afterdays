"""Quest experience gameplay behavior."""
import math

def quest_multiplier(delta):
    return 1 if delta<2 else .8 if delta==2 else .6 if delta==3 else .25 if delta==4 else .01


class QuestExperienceMixin:
    def quest_xp(self,q):
        amount=max(1,math.floor(q.get('xp_reward',0)*quest_multiplier(self.level-q.get('level',q.get('zone',1)))))
        return max(1,amount//(2 if self.coward_turns else 1))

    def turn_in(self,ident):
        q=next((q for q in self.quests if q['id']==ident),None)
        if q is None:return False
        original=q.get('xp_reward',0)
        q['xp_reward']=self.quest_xp(q)*(2 if self.coward_turns else 1)
        try:return super().turn_in(ident)
        finally:q['xp_reward']=original

    def quest_text(self,q):return super().quest_text(dict(q,xp_reward=self.quest_xp(q)))
