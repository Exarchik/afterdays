import unittest
import afterdays as r


class StartRoadTests(unittest.TestCase):
    def test_single_road_through_start_and_connected_city(self):
        for seed in range(40):
            game=r.Game(seed)
            protected={tuple(site['pos']):game.world[site['pos'][1]][site['pos'][0]] for site in game.special_sites}
            game.prepare_campaign()
            self.assertEqual({(x,y) for y in range(4) for x in range(4) if game.world[y][x]=='road' and (x,y) not in protected}, {(x,1) for x in range(4)}-protected.keys())
            for (x,y),terrain in protected.items():self.assertEqual(game.world[y][x],terrain)
            self.assertTrue(all(game.world[y][x]=='road' or (x,y) in protected for x,y in ((0,1),(2,1))))
            self.assertTrue(all(game.world[y][x]!='road' for x,y in ((1,0),(1,2))))
            cx,cy=game.cities[0]
            route=[(x,1) for x in range(cx+1)]+[(cx,y) for y in range(2,cy+1)]
            self.assertTrue(all(game.world[y][x] in ('road','city') or (x,y) in protected for x,y in route))
            self.assertTrue(all(f'{x},{y}' not in game.radiation for x,y in route))
            before=[row[:] for row in game.world];game.prepare_campaign();self.assertEqual(game.world,before)


if __name__=='__main__':unittest.main()
