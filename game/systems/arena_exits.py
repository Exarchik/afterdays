"""Arena exits gameplay behavior."""
import hexgrid


class ArenaExitsMixin:
    def nearby_exit(self,b):
        occupied=set(map(tuple,b['walls']))|{tuple(e['pos']) for e in b['enemies']}
        floor=set(map(tuple,b.get('floor',[(x,y) for y in range(b['h']) for x in range(b['w'])])))
        choices=[p for p in hexgrid.neighbors(*b['pos'],b['w'],b['h']) if p in floor and p not in occupied]
        # If every neighbour is occupied, the current cell is always accessible.
        return list(choices[0]) if choices else b['pos'][:]

    def check_faction_victory(self):
        b=self.battle;was=bool(b and b.get('safe_exit047'))
        result=super().check_faction_victory()
        if b and self.battle is b and b.get('safe_exit047') and not was:b['exit']=self.nearby_exit(b)
        return result

    def victory(self):
        b=self.battle;was=bool(b and b.get('cleared'))
        result=super().victory()
        if b and self.battle is b and b.get('cleared') and not was:b['exit']=self.nearby_exit(b)
        return result
