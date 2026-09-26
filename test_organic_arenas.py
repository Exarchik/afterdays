import copy,random,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import afterdays as r
import hexgrid,organic_arenas as o,advanced_ui
from tests_fixtures.quest_offer import offer_for

class OrganicTests(unittest.TestCase):
 def test_connected_diverse_floors(self):
  """Перевіряє сценарій «connected diverse floors» та очікувані результати."""
  layouts=set()
  for seed in range(100):
   w,h,rooms,floor,start,chest=o.dungeon(random.Random(seed));self.assertEqual(o.connected(floor,tuple(start)),floor)
   self.assertIn(tuple(chest),floor);self.assertTrue(all(0<x<w-1 and 0<y<h-1 for x,y in floor))
   for x,y,_,_ in rooms:self.assertIn((x,y),floor)
   self.assertLess(len(floor),w*h*.7);layouts.add(frozenset(floor))
  self.assertEqual(len(layouts),100)
 def test_arena_reachable_and_escape_preserved(self):
  """Перевіряє сценарій «arena reachable and escape preserved» та очікувані результати."""
  for seed in range(24):
   g=r.Game(seed);g.start_battle();b=g.battle;floor=set(map(tuple,b['floor']));walls=set(map(tuple,b['walls']));walk=floor-walls
   self.assertEqual(o.connected(walk,tuple(b['pos'])),walk);self.assertIn((0,5),walk)
   self.assertLess(len(floor),b['w']*b['h']);self.assertTrue(all(tuple(e['pos']) in walk for e in b['enemies']))
   blocked=(set((x,y) for x in range(b['w']) for y in range(b['h']))-floor);self.assertTrue(blocked<=walls)
 def test_void_move_rejected(self):
  """Перевіряє сценарій «void move rejected» та очікувані результати."""
  g=r.Game(9);g.start_battle();b=g.battle;floor=set(map(tuple,b['floor']));target=next((x,y) for y in range(b['h']) for x in range(b['w']) if (x,y) not in floor)
  pos=b['pos'][:];ap=b['ap'];self.assertFalse(g.battle_move(target));self.assertEqual(b['pos'],pos);self.assertEqual(b['ap'],ap)
 def test_dungeon_spawn_clear_and_exit(self):
  """Перевіряє сценарій «dungeon spawn clear and exit» та очікувані результати."""
  for seed in range(8):
   g=r.Game(seed);q=offer_for(g,'purge');g.accept_quest(q['id']);q=g.quests[-1];g.x,g.y=q['pos'];g.search();b=g.battle;floor=set(map(tuple,b['floor']))
   self.assertEqual(set(map(tuple,b['walls'])),{(x,y) for y in range(b['h']) for x in range(b['w'])}-floor)
   self.assertEqual(len(b['enemies']),len({tuple(e['pos']) for e in b['enemies']}))
   for e in b['enemies']:self.assertTrue(hexgrid.path_to(tuple(b['pos']),tuple(e['pos']),b['w'],b['h'],b['walls']))
   b['enemies']=[];g.victory();b['ap']=0;self.assertTrue(g.battle_move(b['chest']));self.assertTrue(g.search());self.assertTrue(g.battle_move(b['exit']));self.assertTrue(g.flee());self.assertIsNone(g.battle)
 def test_rim_removes_shared_edges(self):
  """Перевіряє сценарій «rim removes shared edges» та очікувані результати."""
  self.assertEqual(len(o.boundary_edges({(2,2)})),6)
  for pos in hexgrid.neighbors(2,2,8,8):self.assertEqual(len(o.boundary_edges({(2,2),pos})),10)
 def test_renderer_and_floor_save_roundtrip(self):
  """Перевіряє сценарій «renderer and floor save roundtrip» та очікувані результати."""
  g=r.Game(7);g.start_battle();before=copy.deepcopy(g.battle)
  canvas=Mock();canvas.winfo_width.return_value=800;canvas.winfo_height.return_value=600
  app=SimpleNamespace(game=g,canvas=canvas,map_title=Mock(),hint=Mock(),battle_hover=(1,5))
  with patch('sprites.draw',return_value=True):advanced_ui.draw_battle(app)
  self.assertTrue(canvas.create_polygon.called);self.assertEqual(g.battle,before)
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
  self.assertEqual(h.battle,before)
