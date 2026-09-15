import copy,math,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import afterdays as r
from frontier import METRO_CITIES
from adventure_ui import Effects
from frontier_ui import draw_metro

class MetroTests(unittest.TestCase):
 def repair(self,g,city):
  g.x,g.y=g.cities[city];offers=g.mayor_offers();q=next(q for q in offers if q.get('metro_city')==city)
  self.assertTrue(q['unique']);self.assertIsNone(q['pos']);self.assertTrue(g.accept_quest(q['id']))
  q=g.quests[-1];self.assertNotIn(city,g.metro_unlocked);self.assertIn('генератора метро',g.quest_text(q))
  self.assertFalse(g.turn_in(q['id']));g.x,g.y=q['pos'];self.assertTrue(g.search())
  item=next(i for i in g.bag if i.get('quest_id')==q['id']);self.assertEqual(item['name'],q['part_name'])
  self.assertTrue(g.quest_ready(q));self.assertFalse(g.turn_in(q['id']))
  g.x,g.y=g.cities[city];self.assertTrue(g.turn_in(q['id']));self.assertIn(city,g.metro_unlocked)
  self.assertFalse(any(i.get('quest_id')==q['id'] for i in g.bag));return q
 def test_unlock_contracts_and_refresh(self):
  g=r.Game(19);self.assertEqual(g.metro_unlocked,[0]);self.assertFalse(g.metro_travel(2))
  self.assertFalse(any('metro_city' in q for q in g.mayor_offers()))
  for city in METRO_CITIES[1:]:
   q=self.repair(g,city);g.turn+=100
   self.assertFalse(any('metro_city' in q and q['status']=='offered' for q in g.mayor_offers()))
   self.assertFalse(g.turn_in(q['id']))
  self.assertEqual(g.metro_unlocked,list(METRO_CITIES))
 def test_safe_travel_cost_and_atomic_failure(self):
  g=r.Game(23);self.repair(g,2);g.money=49;before=(g.money,g.turn,g.x,g.y)
  self.assertFalse(g.metro_travel(0));self.assertEqual(before,(g.money,g.turn,g.x,g.y))
  fare,turns,steps=g.metro_cost(0);self.assertEqual(turns,math.ceil(steps/5))
  g.money=100;beforeturn=g.turn;hp=g.hp;g.rad_turns=10;g.radiation={f'{x},{y}':100 for x in range(48) for y in range(32)}
  with patch.object(g,'start_battle',side_effect=AssertionError('Travel must be safe')):
   self.assertTrue(g.metro_travel(0))
  self.assertEqual(g.money,50);self.assertEqual(g.turn,beforeturn+turns);self.assertEqual(g.hp,hp)
  self.assertEqual(g.rad_turns,max(0,10-turns));self.assertEqual(g.city,0);self.assertIsNone(g.battle)
  self.assertFalse(g.metro_travel(0));self.assertFalse(g.metro_travel(3))
 def test_active_contract_and_unlocked_save(self):
  g=r.Game(27);self.repair(g,2);g.x,g.y=g.cities[3];q=next(q for q in g.mayor_offers() if 'metro_city' in q);g.accept_quest(q['id'])
  g.turn+=100;self.assertFalse(any(q.get('metro_city')==3 for q in g.mayor_offers()))
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);other=r.Game.load(path)
   self.assertEqual(other.metro_unlocked,[0,2]);self.assertEqual(other.quests,g.quests)
 def test_atlas_only_draws_unlocked_stations(self):
  class Canvas:
   def __init__(self):self.lines=[];self.stations=[]
   def create_line(self,*args,**kw):self.lines.append(args)
   def create_oval(self,*args,**kw):self.stations.append(args)
   def create_text(self,*args,**kw):pass
  g=r.Game(8);c=Canvas();draw_metro(c,g,10,0,0);self.assertEqual(len(c.stations),1);self.assertFalse(c.lines)
  self.repair(g,2);c=Canvas();draw_metro(c,g,10,0,0);self.assertEqual(len(c.stations),2);self.assertEqual(len(c.lines),1)
 def test_free_movement_only_after_clear(self):
  g=r.Game(71);q=next(q for q in g.mayor_offers() if q['kind']=='purge');g.accept_quest(q['id']);q=g.quests[-1];g.x,g.y=q['pos'];g.search();b=g.battle
  b['ap']=0;self.assertFalse(g.battle_move((2,4)))
  b['enemies']=[];g.victory();round=b['round'];self.assertTrue(g.battle_move(b['chest']));self.assertEqual(b['ap'],0)
  self.assertTrue(g.search());self.assertTrue(g.battle_move(b['exit']));self.assertEqual(b['round'],round)
  self.assertFalse(g.battle_move((0,0)));self.assertTrue(g.search());self.assertTrue(g.quest_ready(q))
 def test_movement_interpolation_and_input_block(self):
  g=r.Game(5);g.start_battle();g.pop_events();app=SimpleNamespace(game=g,root=SimpleNamespace(after=lambda *args:None))
  fx=Effects(app)
  g.emit_move([[1,1],[2,1],[2,2]],'player')
  g.emit_move([[8,8],[8,7]],'enemy')
  with patch('adventure_ui.time.monotonic',return_value=100):
   fx.ingest();self.assertTrue(fx.blocked);self.assertEqual(fx.position('player',[2,2]),[1,1]);self.assertEqual(fx.position('enemy',[8,7]),[8,8])
  with patch('adventure_ui.time.monotonic',return_value=100.105):
   x,y=fx.position('player',[2,2]);self.assertAlmostEqual(x,2);self.assertAlmostEqual(y,1.5)
  with patch('adventure_ui.time.monotonic',return_value=101):
   self.assertFalse(fx.blocked);self.assertEqual(fx.position('player',[2,2]),[2,2])
 def test_monster_motion_records_actual_path(self):
  g=r.Game(12);g.start_battle();b=g.battle;b['walls']=[];b['pos']=[1,1];b['enemies']=b['enemies'][:1]
  e=b['enemies'][0];e.update(pos=[8,1],speed=2,range=1);g.pop_events();g.end_turn()
  moves=[event for event in g.pop_events() if event['kind']=='move'];self.assertEqual(len(moves),1)
  self.assertEqual(moves[0]['entity'],e['id']);self.assertEqual(moves[0]['path'][0],[8,1]);self.assertEqual(moves[0]['path'][-1],e['pos'])
  for a,b in zip(moves[0]['path'],moves[0]['path'][1:]):self.assertEqual(math.dist(a,b),1)

if __name__=='__main__':unittest.main()
