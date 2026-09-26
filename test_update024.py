import copy,math,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import afterdays as r
import progression as p
import hexgrid,site_layout
from route_ui import RouteController
from tests_fixtures.quest_offer import offer_for

class Update024Tests(unittest.TestCase):
 def contract(self,kind):
  """Готує або імітує операцію «contract» для перевірок Update024Tests."""
  g=r.Game(4);q=offer_for(g,kind);self.assertTrue(g.accept_quest(q['id']));return g,g.quests[-1]
 def test_hex_six_neighbors_and_ap(self):
  """Перевіряє сценарій «hex six neighbors and ap» та очікувані результати."""
  g=r.Game(1);g.start_battle();b=g.battle;b.update(pos=[3,3],walls=[],ap=6);b['enemies'][0]['pos']=[10,8]
  self.assertEqual(len(hexgrid.neighbors(3,3,15,11)),6)
  for pos in hexgrid.neighbors(3,3,15,11):self.assertEqual(hexgrid.distance((3,3),pos),1)
  b['enemies']=b['enemies'][:1]
  self.assertTrue(g.battle_move((4,2)));self.assertEqual(b['ap'],5)
  self.assertFalse(g.battle_move((-1,2)));self.assertEqual(b['ap'],5)
  b['walls']=[[5,2]];self.assertFalse(g.battle_move((5,2)))
 def test_hex_shot_range_and_occlusion(self):
  """Перевіряє сценарій «hex shot range and occlusion» та очікувані результати."""
  g=r.Game(1);g.start_battle();b=g.battle;b.update(pos=[2,2],walls=[])
  enemy=b['enemies'][0];enemy['pos']=[4,2];self.assertTrue(g.shot_info(enemy)[0])
  b['walls']=[[3,2]];self.assertFalse(g.shot_info(enemy)[0]);self.assertFalse(hexgrid.visible((4,2),(2,2),b['walls']))
  self.assertEqual(hexgrid.distance((0,0),(3,3)),6)
  for x in range(12):
   for y in range(12):self.assertEqual(hexgrid.cell(*hexgrid.center((x,y),31,25,-90),31,25,-90),(x,y))
 def test_hex_enemy_moves_one_adjacent_hex(self):
  """Перевіряє сценарій «hex enemy moves one adjacent hex» та очікувані результати."""
  g=r.Game(1);g.start_battle();b=g.battle;b.update(pos=[2,2],walls=[]);e=b['enemies'][0];b['enemies']=[e];e.update(pos=[7,2],speed=1,range=1)
  old=e['pos'][:];g.end_turn();self.assertEqual(hexgrid.distance(old,e['pos']),1)
 def test_sites_spacing_reachability_and_fixed_start(self):
  """Перевіряє сценарій «sites spacing reachability and fixed start» та очікувані результати."""
  for seed in range(24):
   g=r.Game(seed);sites=g.special_sites;self.assertEqual(len(sites),24);self.assertEqual(g.cities[0],[5,5]);reachable=g.reachable_world((5,5))
   for n,s in enumerate(sites):
    self.assertIn(tuple(s['pos']),reachable)
    for other in sites[n+1:]:self.assertGreaterEqual(math.dist(s['pos'],other['pos']),7)
 def test_site_trail_ends_at_nearest_road(self):
  """Перевіряє сценарій «site trail ends at nearest road» та очікувані результати."""
  g=r.Game(2)
  for site in g.special_sites[:5]:
   route=site_layout.road_path(g,site['pos']);self.assertTrue(route);self.assertEqual(g.world[route[-1][1]][route[-1][0]],'road')
   self.assertTrue(all(math.dist(a,b)==1 for a,b in zip(route,route[1:])))
   self.assertTrue(g.discover(site['id']));self.assertTrue(set(route)<=set(map(tuple,g.trails)))
 def test_repair_quest_kits_and_random_condition(self):
  """Перевіряє сценарій «repair quest kits and random condition» та очікувані результати."""
  seen=set()
  for seed in range(8):
   g=r.Game(seed);q=offer_for(g,'repair_delivery');self.assertTrue(g.accept_quest(q['id']));q=g.quests[-1];item=g.quest_equipment(q)
   self.assertTrue(0<=item['durability']<=50);seen.add(item['durability']);p.add_to(g.bag,p.supply('repairkit',4));before=item['durability']
   self.assertTrue(g.repair_with_kit(item['id']));self.assertEqual(item['durability'],min(100,before+35))
   while item['durability']<100:self.assertTrue(g.repair_with_kit(item['id']))
   left=g.count('repairkit');self.assertFalse(g.repair_with_kit(item['id']));self.assertEqual(left,g.count('repairkit'))
  self.assertGreater(len(seen),1)
 def test_thanks_once_and_medal_persist(self):
  """Перевіряє сценарій «thanks once and medal persist» та очікувані результати."""
  g=r.Game(1);g.local_record(0)['value']=80;g.schedule_thanks();g.turn=g.reputation_state['thanks_due'];g.check_thanks()
  q=next(q for q in g.quests if q['kind']=='thanks');self.assertEqual(q['city'],0);self.assertTrue(g.turn_in(q['id']));self.assertTrue(g.welcomed(0));self.assertIn('🏅',g.city_name(0))
  for _ in range(4):g.turn+=101;g.check_thanks()
  self.assertEqual(len([q for q in g.quests if q['kind']=='thanks' and q['city']==0]),1)
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'s.json';g.save(path);h=r.Game.load(path)
  self.assertTrue(h.welcomed(0));self.assertNotIn(0,h.schedule_thanks())
 def test_abandoned_thanks_never_reissued(self):
  """Перевіряє сценарій «abandoned thanks never reissued» та очікувані результати."""
  g=r.Game(1);g.local_record(0)['value']=80;g.schedule_thanks();g.turn=g.reputation_state['thanks_due'];g.check_thanks();q=next(q for q in g.quests if q['kind']=='thanks')
  self.assertTrue(g.abandon_quest(q['id']));g.local_record(0)['value']=100;g.turn+=200;g.check_thanks();self.assertFalse(any(q['kind']=='thanks' for q in g.quests))
 def test_defense_radius_exact_boundary(self):
  """Перевіряє сценарій «defense radius exact boundary» та очікувані результати."""
  g=r.Game(1);q=dict(id='radius',kind='hunt',city=0,level=3,progress=0,goal=5,status='active',target_kind=None);g.quests.append(q)
  g.x,g.y=16,5;g._kill_objectives(0);self.assertEqual(q['progress'],0)
  g.x,g.y=15,5;g._kill_objectives(0);self.assertEqual(q['progress'],1)
 def test_cache_lock_failure_success_and_reentry(self):
  """Перевіряє сценарій «cache lock failure success and reentry» та очікувані результати."""
  g,q=self.contract('cache');g.x,g.y=q['cache_pos'];self.assertTrue(g.search());self.assertFalse(g.quest_ready(q));self.assertFalse(g.loot)
  g.bag[:]=[i for i in g.bag if i['kind']!='parts'];self.assertIsNone(g.unlock_cache(q['id'],q['lock_target']))
  p.add_to(g.bag,p.parts(3));wrong=180 if q['lock_target']<90 else 0
  self.assertFalse(g.unlock_cache(q['id'],wrong));self.assertEqual(g.count('parts'),2);self.assertFalse(g.quest_ready(q))
  target=q['lock_target'];self.assertTrue(g.search());self.assertEqual(target,q['lock_target'])
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'s.json';g.save(path);g=r.Game.load(path)
  q=next(v for v in g.quests if v['id']==q['id']);self.assertEqual(target,q['lock_target'])
  self.assertTrue(g.unlock_cache(q['id'],target));self.assertEqual(g.count('parts'),2);self.assertTrue(g.quest_ready(q));loot=copy.deepcopy(g.loot)
  self.assertIsNone(g.unlock_cache(q['id'],target));self.assertEqual(loot,g.loot)
 def test_all_goods_discount_stacking_and_no_arbitrage(self):
  """Перевіряє сценарій «all goods discount stacking and no arbitrage» та очікувані результати."""
  from visuals import item_sort_key
  g=r.Game(4);g.money=100000;g.local_record()['value']=80
  for merchant,kind in [(0,'ammo'),(1,'food'),(1,'med'),(1,'rad'),(0,'repairkit')]:
   for old in g.stock(merchant):old.pop('promotion',None)
   item=next(i for i in g.stock(merchant) if i['kind']==kind);item['promotion']=dict(city=0,merchant=merchant,discount=75);qty=item['qty'];price=g.price(item,merchant)
   self.assertEqual(sorted(g.stock(merchant),key=item_sort_key)[0]['id'],item['id'])
   self.assertTrue(g.buy(item['id'],merchant,1));self.assertEqual(item['qty'],qty-1);self.assertIn('promotion',item)
   bought=next(i for i in g.bag if i['kind']==kind and i.get('paid_sale_cap')==price-1)
   self.assertNotIn('promotion',bought)
   for m in (0,1,2,3,4):self.assertLess(g.price(bought,m,False),price)
   self.assertTrue(g.buy(item['id'],merchant,1));self.assertEqual(bought['qty'],2)
 def test_guide_animation_double_speed_safe_and_paid_once(self):
  """Перевіряє сценарій «guide animation double speed safe and paid once» та очікувані результати."""
  g=r.Game(3);g.reputation_state['border_open']=True;g.known_cities=list(range(12));g.traveler=dict(pos=[g.x,g.y],guide=True,items=[]);g.money=10000;g.rad_turns=9999;p.add_to(g.bag,p.supply('food',100))
  app=SimpleNamespace(game=g,root=Mock(),dialog=None,fx=SimpleNamespace(blocked=False),refresh=Mock(),draw=Mock(),world_step=g.step)
  controller=RouteController(app);choice=g.guide_destinations()[0];money=g.money;turn=g.turn
  self.assertTrue(controller.start_guide(choice['city']));self.assertEqual(g.money,money-choice['price']);self.assertNotEqual([g.x,g.y],g.cities[choice['city']])
  self.assertAlmostEqual(controller.segment_duration(),math.dist((g.x,g.y),controller.path[0])/3)
  controller.pause();controller.toggle()
  with patch.object(g,'start_battle') as combat,patch.object(g,'make_road_event') as event:
   for _ in range(len(choice['route'])):
    with patch('route_ui.time.monotonic',return_value=controller.started+controller.segment_duration()+.01):controller.advance()
   combat.assert_not_called();event.assert_not_called()
  self.assertEqual([g.x,g.y],g.cities[choice['city']]);self.assertEqual(g.turn,turn+choice['steps']);self.assertEqual(g.money,money-choice['price']);self.assertFalse(controller.running)
