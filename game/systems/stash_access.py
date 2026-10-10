"""Stash access gameplay behavior."""


class StashAccessMixin:
    @property
    def can_access_stash(self):
        if self.battle:return False
        site=self.current_site
        return self.regular_city or bool(site and self.record_at(site['pos'])['value']>=50)
