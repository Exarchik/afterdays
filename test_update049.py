import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import arena_tiles
import hexgrid
import event_catalog

class Update049Tests(unittest.TestCase):
    def test_entry_direction_survives_save_and_older_saves_load(self):
        import update047
        g=r.Game(4)
        def move(game,dx,dy):
            game.x+=dx;game.y+=dy;return True
        before=[g.x,g.y]
        with patch.object(update047.Game,'step',move):g.step(1,0)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path)
            loaded=r.Game.load(path)
            self.assertEqual(loaded.last_world_entry,[before,[g.x,g.y]])
            data=json.loads(path.read_text(encoding='utf-8'))
            data.pop('last_world_entry')
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertIsNone(r.Game.load(path).last_world_entry)
            data['unexpected_field']=True
            path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):r.Game.load(path)

    def test_walk_can_trigger_hole_from_either_side(self):
        import update047
        g=r.Game(4);a,b=self.edge(g);g.reputation_state['border_open']=True
        def move(game,dx,dy):
            game.x+=dx;game.y+=dy;return True
        for target in (a,b):
            g.road_event=None;g.x,g.y=target[0]-1,target[1]
            with patch.object(update047.Game,'step',move), patch.object(g.rng,'random',return_value=0):
                self.assertTrue(g.step(1,0))
            self.assertEqual(g.road_event['kind'],'fence_hole')

    def edge(self,g):
        return next((a,b) for a,b in g.border_edges() if g.passable(*a) and g.passable(*b) and not g.checkpoint(a,b))

    def test_hole_requires_permission_and_survives_save(self):
        g=r.Game(4);a,b=self.edge(g);g.x,g.y=a
        self.assertFalse(g.make_road_event('fence_hole'))
        g.reputation_state['border_open']=True
        self.assertTrue(g.make_road_event('fence_hole'))
        with patch.object(g.rng,'choice',return_value=b):self.assertTrue(g.resolve_event('open'))
        self.assertTrue(g.can_cross(a,b));self.assertTrue(g.can_cross(b,a))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
            self.assertTrue(h.fence_hole(a,b));self.assertTrue(h.can_cross(b,a))
        g.x,g.y=b
        self.assertNotIn(a,g.fence_candidates())
        self.assertEqual(event_catalog.validate(event_catalog.DOCUMENT),[])

    def test_adjacent_exit_avoids_walls_actors_and_missing_floor(self):
        g=r.Game(4)
        b=dict(w=8,h=8,pos=[3,3],walls=[[4,3]],enemies=[dict(pos=[2,3])],floor=[[3,3],[4,3],[2,3],[3,4]])
        self.assertEqual(g.nearby_exit(b),[3,4])
        b['walls'].append([3,4]);self.assertEqual(g.nearby_exit(b),[3,3])

    def test_safe_exit_appears_next_to_current_position(self):
        g=r.Game(4);g.start_battle();b=g.battle
        b.pop('safe_exit047',None);b['cleared']=False
        b['enemies']=[dict(pos=[0,0],faction='player')]
        b['pos']=[3,3];b['walls']=[];b.pop('floor',None)
        self.assertTrue(g.check_faction_victory())
        self.assertEqual(hexgrid.distance(b['pos'],b['exit']),1)
        previous=b['exit'][:];g.check_faction_victory();self.assertEqual(b['exit'],previous)

    def test_arena_neighbours_and_render_do_not_consume_game_rng(self):
        import world_hex
        g=r.Game(4);g.x,g.y=10,10;g.world[10][10]='waste'
        for x,y in world_hex.neighbors(10,10,len(g.world[0]),len(g.world)):g.world[y][x]='forest'
        b=dict(w=15,h=15,biome='waste');state=g.rng.getstate()
        kinds={arena_tiles.terrain(g,b,(x,y)) for x in range(15) for y in range(15)}
        self.assertEqual(kinds,{'forest','waste'});self.assertEqual(state,g.rng.getstate())
        b['dungeon']=True;self.assertEqual(arena_tiles.terrain(g,b,(7,7)),'ruin')

if __name__=='__main__':unittest.main()
