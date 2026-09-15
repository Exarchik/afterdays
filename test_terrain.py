import unittest
import afterdays as r
from terrain_tiles import tile_key,INDEX
class TerrainTests(unittest.TestCase):
 def test_road_connections(self):
  g=r.Game(1);g.world=[['waste']*48 for _ in range(32)];g.radiation={};g.world[10][10]='road'
  for mask in range(16):
   for dx,dy,bit in [(0,-1,1),(1,0,2),(0,1,4),(-1,0,8)]:g.world[10+dy][10+dx]='road' if mask&bit else 'waste'
   self.assertEqual(tile_key(g,10,10),'road'+str(mask))
 def test_shores_radiation_and_purity(self):
  g=r.Game(2);state=g.rng.getstate();g.world=[['water']*48 for _ in range(32)];g.radiation={}
  self.assertEqual(tile_key(g,10,10),'water');g.world[10][9]='waste';self.assertEqual(tile_key(g,10,10),'shoreW')
  g.world[10][10]='forest';g.radiation['10,10']=3;self.assertEqual(tile_key(g,10,10),'rad1')
  g.world[10][10]='road';self.assertTrue(tile_key(g,10,10).startswith('road'))
  self.assertEqual(state,g.rng.getstate())
 def test_every_world_cell_supported(self):
  g=r.Game(3)
  for y in range(32):
   for x in range(48):self.assertIn(tile_key(g,x,y),INDEX)
