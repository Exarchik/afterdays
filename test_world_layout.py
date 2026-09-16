import unittest,tempfile
from pathlib import Path
import afterdays as r
class WorldLayoutTests(unittest.TestCase):
 def test_random_positions_roads_and_reachability(self):
  positions=set();networks=set()
  for seed in range(40):
   g=r.Game(seed);self.assertEqual(g.cities[0],[5,5]);self.assertEqual((g.x,g.y),(5,5))
   self.assertEqual(len(set(map(tuple,g.cities))),12)
   reachable=g.reachable_world((5,5))
   for x,y in g.cities:self.assertEqual(g.world[y][x],'city');self.assertIn((x,y),reachable)
   road_cells={(x,y) for y,row in enumerate(g.world) for x,k in enumerate(row) if k in ('road','city')}
   seen={(5,5)};queue=list(seen)
   for x,y in queue:
    for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
     if p in road_cells and p not in seen:seen.add(p);queue.append(p)
   self.assertTrue(set(map(tuple,g.cities))<=seen)
   positions.add(tuple(map(tuple,g.cities)));networks.add(frozenset(road_cells))
  self.assertEqual(len(positions),40);self.assertEqual(len(networks),40)
 def test_seed_and_save_preserve_layout(self):
  g=r.Game(55);h=r.Game(55);self.assertEqual(g.cities,h.cities);self.assertEqual(g.world,h.world)
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
   self.assertEqual(g.cities,h.cities);self.assertEqual(g.world,h.world);self.assertEqual(g.city_names,h.city_names)
