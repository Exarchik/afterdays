"""Walking reveal gameplay behavior."""


class WalkingRevealMixin:
    def step(self,*args,**kwargs):
        self._walking_reveal=True
        try:return super().step(*args,**kwargs)
        finally:self._walking_reveal=False

    def reveal(self,*args,**kwargs):
        before=set(getattr(self,'explored',[]))
        result=super().reveal(*args,**kwargs)
        if getattr(self,'_physical_credits_ready',False):self._reveal_notice(before)
        return result
