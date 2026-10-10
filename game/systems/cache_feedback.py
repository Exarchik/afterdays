"""Cache feedback gameplay behavior."""


class CacheFeedbackMixin:
    def unlock_cache(self,ident,angle):
        import event_results
        context=self.lock_context(ident)
        before=event_results.snapshot(self);start=len(self._events)
        result=super().unlock_cache(ident,angle)
        if result is True:
            report=event_results.finish(self,(context or {}).get('title','Відкрито сховок'),
                                        (context or {}).get('art','stash'),start,before)
            report['rows'][:0]=[e for e in (context or {}).pop('event_feedback',[]) if e['kind']=='text']
        return result
