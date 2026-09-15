import unittest,copy,tempfile,json
from pathlib import Path
from unittest.mock import patch
import afterdays as r,progression as p,adventure as a
from visuals import item_sort_key,TYPE_COLORS
class RevisionTests(unittest.TestCase):
 def test_radial(self):
  g=r.Game(1)
  self.assertEqual(g.region_at(5,20),g.region_at(20,5))
  self.assertEqual(g.region_at(5,5),1)
  self.assertGreater(g.region_at(40,28),g.region_at(20,10))
 def test_southeast_radiation(self):
  west=east=0
  for seed in range(10):
   g=r.Game(seed)
   for key in g.radiation:
    x,y=map(int,key.split(','));west+=x<24;east+=x>=24
    self.assertFalse(x<24 and y<16)
  self.assertGreater(east,west*2)
 def test_sites_reachable(self):
  g=r.Game(2);self.assertEqual(len(g.special_sites),16);reachable=g.reachable_world((5,5))
  self.assertTrue(all(tuple(s['pos']) in reachable for s in g.special_sites))
  self.assertEqual(len({tuple(s['pos']) for s in g.special_sites}),16)
 def test_tradeoff_effects(self):
  g=r.Game(3)
  with patch.object(g.rng,'random',return_value=0):mod=p.module(0,g.rng,index=0)
  self.assertGreater(mod['stats']['damage'],3);self.assertLess(mod['stats']['accuracy'],0)
  before=p.stats(g.weapon);g.weapon['modules']=[mod];after=p.stats(g.weapon)
  self.assertGreater(after['damage'],before['damage']);self.assertLess(after['accuracy'],before['accuracy'])
 def test_simple_events_once(self):
  for key,(_,_,effect,value) in a.SIMPLE_EVENTS.items():
   g=r.Game(4);g.make_road_event(key);before=g.money
   self.assertTrue(g.resolve_event('leave'));self.assertFalse(g.resolve_event('leave'))
   if effect=='money':self.assertEqual(g.money,max(0,before+value))
  self.assertEqual(len(a.ROAD_EVENTS),46)
 def test_sort_preserves_ids(self):
  items=[p.supply('food',3),p.module(),p.equipment('Пістолет «Попіл»'),p.supply('med')]
  before=copy.deepcopy(items);ordered=sorted(items,key=item_sort_key)
  self.assertEqual([i['kind'] for i in ordered],['weapon','module','med','food']);self.assertEqual(items,before)
  self.assertEqual(len(set(TYPE_COLORS.values())),len(TYPE_COLORS))
 def test_distant_quest_requirements(self):
  g=r.Game(8);g.x,g.y=g.cities[2]
  quests=g.mayor_offers();hunt=next((q for q in quests if q['kind']=='hunt'),None)
  for q in quests:self.assertEqual(q['zone'],g.region_level)
  if hunt:self.assertGreater(hunt['goal'],4)
 def test_migration_once(self):
  g=r.Game(1)
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);data=json.loads(path.read_text());data['version']=5;data['special_sites']=data['special_sites'][:6];path.write_text(json.dumps(data))
   loaded=r.Game.load(path);self.assertEqual(len(loaded.special_sites),16);loaded.save(path);again=r.Game.load(path)
   self.assertEqual(again.radiation,loaded.radiation);self.assertEqual(again.special_sites,loaded.special_sites)
