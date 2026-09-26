import json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
from journey import world_edge,world_route,route_distance
from test_journey import FakeGame
import test_journey as fixtures

class DiagonalTests(unittest.TestCase):
 def test_open_route_has_shortest_diagonals(self):
  """Перевіряє сценарій «open route has shortest diagonals» та очікувані результати."""
  g=FakeGame();route=world_route(g,(4,3))
  self.assertEqual(len(route),4);self.assertAlmostEqual(route_distance((0,0),route),1+3*math.sqrt(2))
 def test_no_corner_cutting(self):
  """Перевіряє сценарій «no corner cutting» та очікувані результати."""
  g=FakeGame()
  for blocked in [(1,0),(0,1)]:
   g.walls={blocked};self.assertFalse(world_edge(g,(0,0),(1,1)))
  g.walls=set()
  for edge in [((0,0),(1,0)),((1,0),(1,1)),((0,0),(0,1)),((0,1),(1,1))]:
   g.can_cross=lambda a,b,edge=edge:(a,b)!=edge
   self.assertFalse(world_edge(g,(0,0),(1,1)))
 def test_diagonal_speed_and_pause(self):
  """Перевіряє сценарій «diagonal speed and pause» та очікувані результати."""
  g,app,c=fixtures.RouteTests().controller()
  with patch('route_ui.time.monotonic',return_value=0):c.set_target((1,1))
  self.assertAlmostEqual(c.segment_duration(),math.sqrt(2)*2/3)
  with patch('route_ui.time.monotonic',return_value=.7):c.advance();self.assertEqual(g.turn,0)
  with patch('route_ui.time.monotonic',return_value=.95):c.advance()
  self.assertEqual((g.x,g.y,g.turn),(1,1,1))
 def game(self):
  """Готує або імітує операцію «game» для перевірок DiagonalTests."""
  g=r.Game(34);g.x=g.y=5;g.special_sites=[];g.radiation={};g._guided_trip=True
  for y in range(4,14):
   for x in range(4,14):g.world[y][x]='waste'
  g.reputation_state['border_open']=True
  return g
 def test_distance_ticks_survive_save_and_cardinal_steps(self):
  """Перевіряє сценарій «distance ticks survive save and cardinal steps» та очікувані результати."""
  g=self.game();g.rad_turns=10
  for _ in range(3):self.assertTrue(g.step(1,1))
  self.assertEqual(g.turn,4);self.assertEqual(g.travel_steps,4);self.assertEqual(g.rad_turns,6)
  self.assertAlmostEqual(g.world_distance_remainder,3*math.sqrt(2)-4)
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
   self.assertAlmostEqual(g.world_distance_remainder,h.world_distance_remainder)
   h._guided_trip=True;self.assertTrue(h.step(1,0));self.assertEqual(h.turn,5)
   self.assertAlmostEqual(g.world_distance_remainder,h.world_distance_remainder)
 def test_old_save_defaults_remainder(self):
  """Перевіряє сценарій «old save defaults remainder» та очікувані результати."""
  g=self.game()
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);data=json.loads(path.read_text());data['version']=15;data.pop('world_distance_remainder');path.write_text(json.dumps(data));h=r.Game.load(path)
   self.assertEqual(h.world_distance_remainder,0)
 def test_blocked_diagonal_spends_nothing(self):
  """Перевіряє сценарій «blocked diagonal spends nothing» та очікувані результати."""
  g=self.game();g.world[5][6]='cliff';before=(g.turn,g.x,g.y,g.world_distance_remainder)
  self.assertFalse(g.step(1,1));self.assertEqual(before,(g.turn,g.x,g.y,g.world_distance_remainder))
 def test_multiple_ticks_apply_food_and_radiation(self):
  """Перевіряє сценарій «multiple ticks apply food and radiation» та очікувані результати."""
  g=self.game();g.travel_steps=6;g.turn=6;g.world_distance_remainder=.9
  g.radiation['6,6']=1;before=g.hp
  with patch.object(g,'consume',return_value=False):self.assertTrue(g.step(1,1))
  self.assertEqual(g.turn,8);self.assertEqual(g.hp,before-7)
 def test_battle_does_not_gain_world_diagonals(self):
  """Перевіряє сценарій «battle does not gain world diagonals» та очікувані результати."""
  g=self.game();g.battle={'pos':[2,2]}
  with patch.object(g,'battle_move',return_value=False) as move:self.assertFalse(g.step(1,1));move.assert_called_once_with((3,3))
  self.assertEqual(g.world_distance_remainder,0);self.assertEqual(g.turn,0)
