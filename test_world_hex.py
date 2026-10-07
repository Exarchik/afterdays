import math,unittest,tempfile
from pathlib import Path
from collections import deque
import world_hex as grid
from world_map import layout
from journey import world_edge,world_route,route_distance
import afterdays


class Board:
    x=y=4
    def __init__(self):self.walls=set();self.closed=set()
    def passable(self,x,y):return 0<=x<12 and 0<=y<12 and (x,y) not in self.walls
    def can_cross(self,a,b):return frozenset((tuple(a),tuple(b))) not in self.closed


class WorldHexTests(unittest.TestCase):
    def test_six_reciprocal_neighbors_and_equal_screen_lengths(self):
        for y in range(2,9):
            a=(4,y);neighbors=grid.adjacent(a)
            self.assertEqual(len(set(neighbors)),6)
            for b in neighbors:
                self.assertIn(a,grid.adjacent(b));self.assertEqual(grid.distance(a,b),1)
                self.assertAlmostEqual(math.dist(grid.center(a),grid.center(b)),math.sqrt(3))

    def test_hit_testing_at_centers_and_inside_edges(self):
        for y in range(12):
            for x in range(12):
                px,py=grid.center((x,y),17,35,-51)
                self.assertEqual(grid.cell(px,py,17,35,-51),(x,y))
                for b in grid.adjacent((x,y)):
                    bx,by=grid.center(b,17,35,-51)
                    self.assertEqual(grid.cell(px+(bx-px)*.49,py+(by-py)*.49,17,35,-51),(x,y))

    def test_shared_edge_is_identical_both_directions(self):
        for a in ((4,4),(4,5)):
            for b in grid.adjacent(a):
                edge=grid.edge(a,b);reverse=grid.edge(b,a)
                points=lambda e:sorted((round(e[i],8),round(e[i+1],8)) for i in (0,2))
                self.assertEqual(points(edge),points(reverse))

    def test_camera_contains_full_hexes_and_clamps_world_edges(self):
        for focus in ((0,0),(111,31),(55,15)):
            v=layout(820,540,112,32,focus)
            for y in range(v.vy,v.vy+v.rows):
                for x in range(v.vx,v.vx+v.cols):
                    p=v.polygon((x,y))
                    self.assertTrue(all(0<=n<=820 for n in p[::2]))
                    self.assertTrue(all(0<=n<=540 for n in p[1::2]))
                    self.assertEqual(v.cell(*v.point((x,y))),(x,y))

    def test_hex_a_star_matches_breadth_first_cost(self):
        g=Board();g.walls={(5,y) for y in range(10) if y!=8}
        goal=(9,4);queue=deque([((g.x,g.y),0)]);seen={(g.x,g.y)}
        while queue:
            pos,cost=queue.popleft()
            if pos==goal:break
            for nxt in grid.adjacent(pos):
                if nxt not in seen and world_edge(g,pos,nxt):seen.add(nxt);queue.append((nxt,cost+1))
        route=world_route(g,goal)
        self.assertEqual(len(route),cost)
        self.assertEqual(route_distance((g.x,g.y),route),cost)
        for a,b in zip([(g.x,g.y)]+route,route):self.assertTrue(world_edge(g,a,b))

    def test_non_neighbors_and_closed_edges_are_rejected(self):
        g=Board();self.assertFalse(world_edge(g,(4,4),(5,5)))
        g.closed.add(frozenset(((4,5),(5,6))))
        self.assertFalse(world_edge(g,(4,5),(5,6)))
        self.assertFalse(world_edge(g,(5,6),(4,5)))
        # This is a shared edge, so square "corner" cells do not obstruct it.
        g.closed.clear();g.walls={(5,5),(4,6)}
        self.assertTrue(world_edge(g,(4,5),(5,6)))

    def test_keys_cover_exactly_six_neighbors_on_both_parities(self):
        for y in (4,5):
            moves=[grid.key_delta(k,y) for k in 'qwadzx']
            self.assertEqual({(4+dx,y+dy) for dx,dy in moves},set(grid.adjacent((4,y))))
        self.assertIsNone(grid.key_delta('e',4))

    def test_interpolation_is_straight_between_hex_centers(self):
        for a in ((4,4),(4,5)):
            for b in grid.adjacent(a):
                midpoint=tuple((a[i]+b[i])/2 for i in (0,1))
                projected=grid.center(midpoint)
                expected=tuple((grid.center(a)[i]+grid.center(b)[i])/2 for i in (0,1))
                for x,y in zip(projected,expected):self.assertAlmostEqual(x,y)

    def test_fog_reveal_is_hex_disk(self):
        g=afterdays.Game(47);g.explored=[];g.reveal(20,15,2)
        cells={tuple(map(int,key.split(','))) for key in g.explored}
        self.assertEqual(len(cells),19)
        self.assertTrue(all(grid.distance((20,15),p)<=2 for p in cells))

    def test_all_cities_remain_reachable_and_border_edges_complete(self):
        for seed in (1,47,200):
            g=afterdays.Game(seed);reachable=g.reachable_world(g.cities[0])
            self.assertTrue(all(tuple(p) in reachable for p in g.cities))
            actual={frozenset((a,b)) for a,b in g.border_edges()}
            expected={frozenset(((x,y),b)) for y in range(len(g.world)) for x in range(len(g.world[0]))
                      for b in grid.neighbors(x,y,len(g.world[0]),len(g.world)) if g.border_edge((x,y),b)}
            self.assertEqual(actual,expected)

    def test_save_round_trip_preserves_coordinates_and_drops_old_fraction(self):
        g=afterdays.Game(47);g.world_distance_remainder=.8
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'save.json';g.save(path);h=afterdays.Game.load(path)
        self.assertEqual((g.x,g.y),(h.x,h.y));self.assertEqual(g.cities,h.cities)
        self.assertEqual(g.explored,h.explored);self.assertEqual(g.world,h.world)
        self.assertEqual(h.world_distance_remainder,0)


if __name__=='__main__':unittest.main()
