import unittest
from types import SimpleNamespace
import arena_tiles as tiles
import hexgrid
import world_hex

class ArenaRoadTests(unittest.TestCase):
    def game(self,y=4):
        return SimpleNamespace(x=4,y=y,world=[['forest']*10 for _ in range(10)])

    def test_world_links_and_row_parity(self):
        from world_map import road_neighbors
        for y in (4,5):
            g=self.game(y);g.world[y][4]='road'
            for x,ny in world_hex.neighbors(4,y,10,10):g.world[ny][x]='road'
            cx,cy=world_hex.center((4,y))
            expected=tuple((world_hex.center(p)[0]-cx,world_hex.center(p)[1]-cy) for p in road_neighbors(g,(4,y)))
            self.assertEqual(tiles.road_directions(g,{}),expected)
            self.assertEqual(tiles.road_directions(g,{'dungeon':True}),())

    def test_straight_bend_junction_and_obstacles(self):
        b=dict(w=15,h=15,walls=[[7,6],[7,8],[8,7]])
        for directions in (((1,0),(-1,0)),((1,0),(0,1)),((1,0),(-1,0),(0,1))):
            roads=tiles.road_cells(b,directions)
            self.assertGreater(len(roads),4)
            self.assertFalse(roads.intersection(map(tuple,b['walls'])))
            start=min(roads)
            for end in roads:
                blocked={(x,y) for y in range(15) for x in range(15)}-roads
                self.assertIsNotNone(hexgrid.path_to(start,end,15,15,blocked))
        straight=tiles.road_cells(dict(w=15,h=15,walls=[]),((1,0),(-1,0)))
        centers=[hexgrid.center(p,1) for p in straight]
        self.assertGreater(max(p[0] for p in centers)-min(p[0] for p in centers),20)
        self.assertLess(max(p[1] for p in centers)-min(p[1] for p in centers),5)

    def test_only_path_is_asphalt(self):
        g=self.game();g.world[4][4]='road';b=dict(w=15,h=15,biome='road',walls=[])
        roads=tiles.road_cells(b,((1,0),(-1,0)))
        for x in range(15):
            for y in range(15):self.assertEqual(tiles.terrain(g,b,(x,y),roads)=='road',(x,y) in roads)

    def test_void_and_empty_road(self):
        b=dict(w=10,h=10,floor=[[2,2],[3,2],[4,2],[8,8]],walls=[])
        self.assertEqual(tiles.road_cells(b,()),frozenset())
        self.assertTrue(tiles.road_cells(b,((1,0),))<=set(map(tuple,b['floor'])))

if __name__=='__main__':unittest.main()
