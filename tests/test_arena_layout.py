import random
import unittest
from types import SimpleNamespace
import arena_layout
import arena_tiles
import hexgrid
import world_hex
from organic_arenas import connected

class ArenaLayoutTests(unittest.TestCase):
    def test_outdoor_floor_has_exactly_twenty_rows(self):
        g=self.game();arena_layout.build(g)
        rows={y for x,y in g.battle['floor']}
        self.assertEqual(len(rows),20)
        self.assertEqual(max(rows)-min(rows)+1,20)
        columns={x for x,y in g.battle['floor']}
        self.assertEqual(max(columns)-min(columns)+1,13)
        self.assertEqual(g.battle['arena_extent'][0],16)

    def game(self,y=6):
        return SimpleNamespace(x=6,y=y,world=[['forest']*15 for _ in range(15)],rng=random.Random(4),
            battle=dict(biome='forest',enemies=[dict(pos=[0,0]) for _ in range(8)]))

    def test_all_entry_directions_both_row_parities(self):
        for y in (6,7):
            for origin in world_hex.adjacent((6,y)):
                g=self.game(y);g._entering_world=(origin,(6,y));arena_layout.build(g);b=g.battle
                dx,dy=b['entry_direction'];cx,cy=b['arena_center'];rx,ry=b['arena_extent']
                def projection(p):
                    x,y=hexgrid.center(p,1);return (x-cx)/rx*dx+(y-cy)/ry*dy
                self.assertGreater(projection(b['pos']),.6)
                self.assertTrue(all(projection(e['pos'])<-.35 for e in b['enemies']))
                self.assertEqual(len({tuple(e['pos']) for e in b['enemies']}),8)
                floor=set(map(tuple,b['floor']));walk=floor-set(map(tuple,b['walls']))
                self.assertEqual(connected(walk,tuple(b['pos'])),walk)
                for p in floor:
                    px,py=hexgrid.center(p,1)
                    self.assertLessEqual(abs(px-cx)/rx,1)
                    self.assertLessEqual(abs(py-cy)/ry+.5*abs(px-cx)/rx,1)

    def test_water_on_correct_side_no_water_spawns_or_roads(self):
        g=self.game();g.world[6][7]='water';g.world[6][6]='road';g.world[6][5]='road'
        g.battle['biome']='road';g.last_world_entry=[[5,6],[6,6]]
        arena_layout.build(g);b=g.battle
        water=set(map(tuple,b['water_cells']));self.assertTrue(water)
        self.assertTrue(all(hexgrid.center(p,1)[0]>b['arena_center'][0] for p in water))
        self.assertTrue(water<=set(map(tuple,b['walls'])))
        self.assertNotIn(tuple(b['pos']),water)
        self.assertTrue(all(tuple(e['pos']) not in water for e in b['enemies']))
        self.assertFalse(water & arena_tiles.road_cells(b,arena_tiles.road_directions(g,b)))
        self.assertTrue(b['shore_cells'])

    def test_dungeon_is_unchanged(self):
        g=self.game();g.battle['dungeon']=True;before=repr(g.battle)
        arena_layout.build(g);self.assertEqual(repr(g.battle),before)

if __name__=='__main__':unittest.main()
