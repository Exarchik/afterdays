import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import afterdays as r
import progression as p
from journey import world_route
from route_ui import RouteController

class JourneyTests(unittest.TestCase):
 def test_turnover_and_repair(self):
  """Перевіряє сценарій «turnover and repair» та очікувані результати."""
  g=r.Game(23);g.xp=p.xp_for_level(4);g.money=100000
  city=next(i for i in range(12) if g.region_at(*g.cities[i])>=3)
  g.x,g.y=g.cities[city];threshold=50*g.region_at(*g.cities[city])
  g.add_reputation(turnover=threshold-1);self.assertEqual(g.reputation(),0)
  g.add_reputation(turnover=2);self.assertEqual(g.reputation(),1);self.assertEqual(g.local_record()['turnover'],1)
  if city not in g.technicians:g.technicians.append(city)
  item=p.equipment('weapon_ash_pistol',level=10);item['durability']=0;g.bag.append(item)
  cost=g.repair_cost(item,100);before=g.money
  self.assertTrue(g.repair(item['id'],100));self.assertEqual(before-g.money,cost)
  points,remainder=divmod(1+cost,threshold)
  self.assertEqual(g.reputation(),1+points);self.assertEqual(g.local_record()['turnover'],remainder)
  record=dict(g.local_record());self.assertFalse(g.repair(item['id'],100));self.assertEqual(record,g.local_record())
 def test_saved_remainder_and_guide(self):
  """Перевіряє сценарій «saved remainder and guide» та очікувані результати."""
  g=r.Game(23);g.xp=p.xp_for_level(8);g.add_reputation(turnover=49);g.traveler=dict(guide=True,pos=[g.x,g.y],items=[])
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
  self.assertTrue(h.guide);self.assertFalse(h.available_merchant(3));self.assertEqual(h.local_record()['turnover'],49)
  h.xp=p.xp_for_level(15);h.add_reputation(turnover=1);self.assertEqual(h.reputation(),1)
 def test_traveler_uses_home_city_level(self):
  """Перевіряє сценарій «traveler uses home city level» та очікувані результати."""
  g=r.Game(23);g.xp=p.xp_for_level(15);g.money=10000
  city=next(i for i in range(12) if g.region_at(*g.cities[i])>=3)
  g.x,g.y=g.cities[city];g.x+=1
  item=p.supply('food',1);g.traveler=dict(pos=[g.x,g.y],items=[item])
  home=g.trading_city(3);threshold=50*g.region_at(*g.cities[home])
  g.local_record(home)['turnover']=threshold-g.price(item,3,True)
  self.assertTrue(g.buy(item['id'],3,1));self.assertEqual(g.reputation(home),1)
  self.assertEqual(g.local_record(home)['turnover'],0)
 def ready_guide(self):
  """Готує або імітує операцію «ready guide» для перевірок JourneyTests."""
  g=r.Game(19);g.known_cities=list(range(12));g.reputation_state['border_open']=True
  g.traveler=dict(guide=True,pos=[g.x,g.y],items=[]);return g
 def test_destinations(self):
  """Перевіряє сценарій «destinations» та очікувані результати."""
  g=self.ready_guide();choices=g.guide_destinations();self.assertEqual(len(choices),3)
  self.assertEqual([c['steps'] for c in choices],sorted(c['steps'] for c in choices))
  self.assertTrue(all(c['city']<12 and c['city']!=g.city for c in choices))
  g.known_cities=[0];self.assertEqual(g.guide_destinations(),[])
  g.known_cities=list(range(12));g.reputation_state['border_open']=False
  self.assertTrue(all(g.inside_border(g.cities[c['city']]) for c in g.guide_destinations()))
 def test_guided_trip(self):
  """Перевіряє сценарій «guided trip» та очікувані результати."""
  g=self.ready_guide();g.money=10000;g.rad_turns=999;g.bag.append(p.supply('food',100))
  choice=g.guide_destinations()[0];before=(g.money,g.turn,g.travel_steps)
  with patch.object(g,'start_battle') as combat,patch.object(g,'make_road_event') as event:
   self.assertTrue(g.guide_travel(choice['city']));combat.assert_not_called();event.assert_not_called()
  self.assertEqual(g.money,before[0]-choice['price']);self.assertEqual(g.turn,before[1]+choice['steps'])
  self.assertEqual(g.travel_steps,before[2]+choice['steps']);self.assertEqual([g.x,g.y],g.cities[choice['city']])
  self.assertFalse(g.guide_travel(choice['city']))
 def test_guide_rejection(self):
  """Перевіряє сценарій «guide rejection» та очікувані результати."""
  g=self.ready_guide();g.money=0;turn=g.turn
  self.assertFalse(g.guide_travel(g.guide_destinations()[0]['city']));self.assertFalse(g.guide_travel(99));self.assertEqual(g.turn,turn)

class FakeGame:
 def __init__(self):
  """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
  self.x=self.y=self.turn=0;self.battle=None;self.road_event=None;self.traveler=None;self.city=None;self.walls=set();self.log=Mock()
 # Перевіряє прохідність клітинки місцевості.
 def passable(self,x,y):return 0<=x<5 and 0<=y<4 and (x,y) not in self.walls
 # Перевіряє можливість перетину ребра між клітинками.
 def can_cross(self,a,b):return True
 # Виконує крок світом і запускає пов’язані з ходом події.
 def step(self,dx,dy):self.x+=dx;self.y+=dy;self.turn+=1;return True

class RouteTests(unittest.TestCase):
 def controller(self):
  """Готує або імітує операцію «controller» для перевірок RouteTests."""
  g=FakeGame();app=SimpleNamespace(game=g,root=Mock(),dialog=None,fx=SimpleNamespace(blocked=False),refresh=Mock(),draw=Mock(),world_step=g.step)
  return g,app,RouteController(app)
 def test_path(self):
  """Перевіряє сценарій «path» та очікувані результати."""
  g=FakeGame();g.walls={(1,0)};path=world_route(g,(3,0));self.assertEqual(len(path),4);self.assertNotIn((1,0),path)
  g.can_cross=lambda a,b:b[0]==0
  self.assertEqual(world_route(g,(3,0)),[])
 def test_speed_pause_resume(self):
  """Перевіряє сценарій «speed pause resume» та очікувані результати."""
  g,app,c=self.controller()
  with patch('route_ui.time.monotonic',return_value=0):self.assertTrue(c.set_target((3,0)))
  with patch('route_ui.time.monotonic',return_value=.3):
   c.advance();self.assertEqual(g.turn,0);self.assertAlmostEqual(c.position()[0],.45);c.pause()
  self.assertEqual(c.position(),(0,0));self.assertEqual(g.turn,0)
  with patch('route_ui.time.monotonic',return_value=1):c.toggle()
  with patch('route_ui.time.monotonic',return_value=1.67):c.advance()
  self.assertEqual((g.x,g.turn),(1,1))
  with patch('route_ui.time.monotonic',return_value=2.34):c.advance()
  with patch('route_ui.time.monotonic',return_value=3.01):c.advance()
  self.assertEqual((g.x,g.turn),(3,3));self.assertFalse(c.running);self.assertEqual(c.path,[])
 def test_interruptions(self):
  """Перевіряє сценарій «interruptions» та очікувані результати."""
  for attr in ('dialog','battle','road_event'):
   g,app,c=self.controller()
   with patch('route_ui.time.monotonic',return_value=0):c.set_target((3,0))
   setattr(app if attr=='dialog' else g,attr,True)
   with patch('route_ui.time.monotonic',return_value=1):c.advance()
   self.assertFalse(c.running);self.assertEqual(g.turn,0);self.assertEqual(len(c.path),3)
  g,app,c=self.controller()
  with patch('route_ui.time.monotonic',return_value=0):c.set_target((3,0))
  def encounter(dx,dy):g.step(dx,dy);g.traveler={'guide':True};return True
  app.world_step=encounter
  with patch('route_ui.time.monotonic',return_value=1):c.advance()
  self.assertFalse(c.running);self.assertEqual(g.turn,1);self.assertEqual(len(c.path),2)
 def test_stale_and_failed_routes(self):
  """Перевіряє сценарій «stale and failed routes» та очікувані результати."""
  g,app,c=self.controller();c.set_target((3,0));app.game=FakeGame();c.advance();self.assertFalse(c.path)
  c.set_target((3,0));app.game.x=4;c.advance();self.assertFalse(c.path)
  g,app,c=self.controller()
  with patch('route_ui.time.monotonic',return_value=0):c.set_target((3,0))
  app.world_step=lambda dx,dy:False
  with patch('route_ui.time.monotonic',return_value=1):c.advance()
  self.assertEqual(g.turn,0);self.assertFalse(c.running)
