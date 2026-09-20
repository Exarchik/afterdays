import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import progression as p
import adventure as a
import exploration
import road_additions
from inspection_ui import item_text,monster_text

class ExplorationTests(unittest.TestCase):
 def test_empty_search_is_final_and_costs_turn(self):
  g=r.Game(1);g.x,g.y=6,5;turn=g.turn
  with patch.object(g.rng,'random',return_value=.5):self.assertTrue(g.search())
  self.assertEqual(g.loot,[]);self.assertEqual(g.turn,turn+1);self.assertFalse(g.search());self.assertEqual(g.turn,turn+1)
 def test_search_loot_boundaries_and_location_level(self):
  for player in (1,14):
   g=r.Game(2);g.x,g.y=6,5;g.xp=p.xp_for_level(player)
   with patch.object(g.rng,'random',side_effect=[.039,.099]+[.9]*100):self.assertTrue(g.search())
   self.assertEqual(len(g.loot),1);self.assertIn(g.loot[0]['kind'],('weapon','armor','helmet','module'));self.assertEqual(g.loot[0]['level'],1)
  g=r.Game(2);g.x,g.y=6,5
  with patch.object(g.rng,'random',return_value=.04):
   with patch.object(g,'start_battle') as battle:g.search();self.assertEqual(g.loot,[]);battle.assert_called_once()
 def test_search_supplies_branch(self):
  g=r.Game(9);g.x,g.y=6,5
  with patch.object(g.rng,'random',side_effect=[.01,.10,.9]):self.assertTrue(g.search())
  self.assertNotIn(g.loot[0]['kind'],('weapon','armor','helmet','module'))
 def test_fence_chest_purchase_save_open_once(self):
  g=r.Game(3);g.money=100000;chest=g.stock(2)[0];content=copy.deepcopy(chest['contents']);weight=g.weight
  self.assertEqual(chest['kind'],'sealed');self.assertNotIn(content['name'],item_text(g,chest))
  self.assertTrue(g.buy(chest['id'],2));self.assertTrue(any(i['id']==chest['id'] for i in g.bag))
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);g=r.Game.load(path)
  before=g.weight;found=g.open_chest(chest['id']);self.assertEqual(found,content);self.assertAlmostEqual(before,g.weight)
  self.assertIsNone(g.open_chest(chest['id']));self.assertEqual(len([i for i in g.bag if i['id']==content['id']]),1)
 def test_chest_cannot_open_in_combat(self):
  g=r.Game(4);g.money=100000;chest=g.stock(2)[0];g.buy(chest['id'],2);g.start_battle();before=copy.deepcopy(g.bag)
  self.assertIsNone(g.open_chest(chest['id']));self.assertEqual(g.bag,before)
 def test_objectives_ignore_player_and_location_levels(self):
  for level in (1,10,20):
   g=r.Game(6);g.xp=p.xp_for_level(level)
   for city in (0,2,7):
    g.x,g.y=g.cities[city]
    for q in g.mayor_offers():
     if q['kind'] in ('hunt','trophies'):self.assertTrue(2<=q['goal']<=5)
  weak={exploration.objective_count(__import__('random').Random(n),0) for n in range(50)}
  strong={exploration.objective_count(__import__('random').Random(n),9) for n in range(50)}
  self.assertEqual(weak,{4,5});self.assertEqual(strong,{2,3})
 def test_varied_connected_dungeons(self):
  import random
  counts=set();layouts=set()
  for seed in range(60):
   w,h,rooms,floor,start,chest=exploration.dungeon_layout(random.Random(seed));counts.add(len(rooms));layouts.add(tuple(map(tuple,rooms)))
   blocked={(x,y) for x in range(w) for y in range(h) if (x,y) not in floor}
   self.assertTrue(all(0<x<w-1 and 0<y<h-1 for x,y in floor))
   for x,y,rw,rh in rooms:self.assertIsNotNone(__import__('hexgrid').path_to(tuple(start),(x,y),w,h,blocked))
   self.assertTrue(__import__('hexgrid').path_to(tuple(start),tuple(chest),w,h,blocked))
  self.assertGreaterEqual(len(counts),4);self.assertEqual(len(layouts),60)
 def test_twenty_events_resolve_once(self):
  self.assertEqual(len(road_additions.EVENTS),20);self.assertEqual(len({e[0] for e in a.ROAD_EVENTS}),51)
  for spec in road_additions.EVENTS:
   g=r.Game(2);g.bag.extend([p.parts(100),p.fragments(100),p.supply('food',10)]);g.money=1000
   self.assertTrue(g.make_road_event(spec[0]));self.assertTrue(g.resolve_event('act'))
   self.assertIsNone(g.road_event);before=copy.deepcopy((g.bag,g.loot,g.money,g.xp,g.hp));self.assertFalse(g.resolve_event('act'));self.assertEqual(before,(g.bag,g.loot,g.money,g.xp,g.hp))
 def test_monster_full_info(self):
  g=r.Game(8);g.start_battle();text=monster_text(g,g.battle['enemies'][0])
  for term in ('Атака','Захист','Здоров’я','Рух за раунд','ОПОРИ','Нагорода'):self.assertIn(term,text)

if __name__=='__main__':unittest.main()
