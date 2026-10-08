"""Quest-zone compatibility adapters; all rendering uses world hex geometry."""
import world_hex

def defense_cells(game,q):
    """Return cells where the active settlement-defense contract counts kills."""
    cx,cy=game.cities[q['city']]
    return {(x,y) for y in range(max(0,cy-10),min(len(game.world),cy+11))
            for x in range(max(0,cx-10),min(len(game.world[0]),cx+11)) if world_hex.distance((x,y),(cx,cy))<=10}


def draw_search_areas(canvas,game,t,ox,oy,viewport=None):
    from world_map import View,draw_areas
    vx,vy,w,h=viewport or (0,0,len(game.world[0]),len(game.world))
    draw_areas(canvas,game,View(t/2,ox,oy,vx,vy,w,h))


def draw_defense_areas(canvas,game,t,ox,oy,viewport=None):
    from types import SimpleNamespace
    proxy=SimpleNamespace(quests=[q for q in game.quests if q.get('kind')=='hunt'],
                          world=game.world,cities=game.cities,quest_ready=game.quest_ready)
    draw_search_areas(canvas,proxy,t,ox,oy,viewport)
