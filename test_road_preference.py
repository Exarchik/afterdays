import heapq
import random
import unittest
from unittest.mock import MagicMock

import world_hex
from journey import world_route, world_edge, route_terrain_cost, route_distance
from world_map import View, draw_roads


class Board:
    x, y = 0, 3

    def __init__(self, width=15, height=8):
        self.world = [['waste'] * width for _ in range(height)]
        self.closed = set()

    def passable(self, x, y):
        return (0 <= y < len(self.world) and 0 <= x < len(self.world[0])
                and self.world[y][x] != 'water')

    def can_cross(self, a, b):
        return frozenset((a, b)) not in self.closed


class RoadPreferenceTests(unittest.TestCase):
    def test_short_detour_follows_road(self):
        g = Board()
        for x in range(15):g.world[1][x] = 'road'
        route = world_route(g, (14, 3))
        self.assertTrue(any(g.world[y][x] == 'road' for x, y in route))
        self.assertEqual(route_distance((g.x, g.y), route), len(route))
        self.assertLessEqual(len(route), 18)

    def test_distant_road_does_not_cause_large_detour(self):
        g = Board()
        for x in range(15):g.world[7][x] = 'road'
        route = world_route(g, (4, 3))
        self.assertEqual(len(route), 4)

    def test_nearby_roads_require_accessible_edge(self):
        g = Board()
        g.world[3][1] = 'road'
        self.assertEqual(route_terrain_cost(g, (1, 3)), 1)
        self.assertEqual(route_terrain_cost(g, (0, 3)), 1.15)
        g.closed.add(frozenset(((0, 3), (1, 3))))
        self.assertEqual(route_terrain_cost(g, (0, 3)), 1.35)

    def test_weighted_astar_matches_dijkstra(self):
        rng = random.Random(48)
        for _ in range(20):
            g = Board()
            for row in g.world:
                for x in range(len(row)):row[x] = rng.choice(['waste']*5 + ['road', 'water'])
            start, end = (g.x, g.y), (14, 3)
            g.world[3][0] = g.world[3][14] = 'waste'
            costs = {start: 0}; queue = [(0, start)]
            while queue:
                cost, pos = heapq.heappop(queue)
                if cost > costs[pos]:continue
                for nxt in world_hex.adjacent(pos):
                    if not world_edge(g, pos, nxt):continue
                    value = cost + route_terrain_cost(g, nxt)
                    if value < costs.get(nxt, float('inf')):
                        costs[nxt] = value; heapq.heappush(queue, (value, nxt))
            route = world_route(g, end)
            if end not in costs:self.assertEqual(route, [])
            else:
                self.assertAlmostEqual(sum(route_terrain_cost(g, p) for p in route), costs[end])
                self.assertTrue(all(world_edge(g, a, b) for a, b in zip([start]+route, route)))

    def test_roads_stop_at_city_and_special_location_edges(self):
        for kind in ('city', 'site'):
            g = Board(2, 1); g.world[0] = ['road', kind]
            view = View(20, 30, 30, 0, 0, 2, 1)
            canvas = MagicMock()
            draw_roads(canvas, g, view, lambda x, y: True)
            middle = tuple((a+b)/2 for a, b in zip(view.point((0, 0)), view.point((1, 0))))
            self.assertEqual(canvas.create_line.call_count, 3)
            for call in canvas.create_line.call_args_list:
                self.assertEqual(call.args, (*view.point((0, 0)), *middle))
            g.world[0][0] = 'waste'; canvas.reset_mock()
            draw_roads(canvas, g, view, lambda x, y: True)
            canvas.create_line.assert_not_called()
            canvas.create_oval.assert_not_called()


if __name__ == '__main__':unittest.main()
