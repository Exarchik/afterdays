from tests_fixtures.quest_offer import offer_for
import copy,json,tempfile,unittest
from pathlib import Path
import afterdays as r
import progression as p
from frontier_ui import player_text

class FrontierTests(unittest.TestCase):
 def dungeon(self,seed=71):
  g=r.Game(seed);q=offer_for(g,'purge');g.accept_quest(q['id']);q=g.quests[-1];g.x,g.y=q['pos'];g.search();return g,q
 def test_dungeon_connected_and_dormant(self):
  for seed in range(5):
   g,q=self.dungeon(seed);b=g.battle;self.assertTrue(b['dungeon']);self.assertTrue(6<=len(b['enemies'])<=10)
   self.assertTrue(all(e['base_level']<=g.region_level+int(e.get('weak',False)) for e in b['enemies']))
   for target in [b['chest']]+[e['pos'] for e in b['enemies']]:self.assertTrue(r.path_to(tuple(b['exit']),tuple(target),b['w'],b['h'],set(map(tuple,b['walls']))))
   before=copy.deepcopy(b['enemies']);g.end_turn();self.assertEqual(before,b['enemies'])
   e=b['enemies'][0];g.wake_enemies(e['pos']);self.assertTrue(e['awake'])
 def test_chest_exit_and_no_double_reward(self):
  g,q=self.dungeon();b=g.battle
  self.assertFalse(g.search());b['kills']=[dict(kind=e['kind'],grade=e['grade']) for e in b['enemies']];b['enemies']=[];g.victory()
  self.assertIs(g.battle,b);self.assertFalse(g.quest_ready(q));b['pos']=b['chest'][:]
  self.assertTrue(g.search());loot=copy.deepcopy(g.loot);self.assertFalse(g.search());self.assertEqual(loot,g.loot)
  med=next(i for i in g.loot if i['kind']=='med');self.assertTrue(g.collect(med['id']))
  b['pos']=b['exit'][:];self.assertTrue(g.search());self.assertIsNone(g.battle);self.assertTrue(g.quest_ready(q))
  money=g.money;g.victory();self.assertEqual(g.money,money)
 def test_market_level_and_purchase(self):
  g=r.Game(13);g.x,g.y=g.cities[9];level=g.region_level;items=g.stock(0);self.assertTrue(items)
  item=next(i for i in items if i['kind']=='weapon');self.assertEqual(item['level'],level);self.assertGreater(level,g.level)
  ids=[i['id'] for i in items];g.xp=p.xp_for_level(2);self.assertEqual(ids,[i['id'] for i in g.stock(0)])
  g.money=10**8;self.assertTrue(g.buy(item['id'],0));self.assertFalse(g.equip(item['id'],'weapon1'))
 def test_cartographer_atomic_exact_square(self):
  g=r.Game(8);self.assertTrue(g.spawn_cartographer());t=g.traveler;x,y,size=t['box'];self.assertTrue(3<=size<=6)
  old=set(g.explored);g.money=0;self.assertFalse(g.buy_map());self.assertEqual(old,set(g.explored))
  g.money=100;self.assertTrue(g.buy_map());self.assertEqual(set(g.explored),old|{f'{xx},{yy}' for xx in range(x,x+size) for yy in range(y,y+size)})
  money=g.money;self.assertFalse(g.buy_map());self.assertEqual(g.money,money);self.assertFalse(g.available_merchant(3))
 def test_save_dungeon_and_cartographer(self):
  for g in [self.dungeon()[0],r.Game(8)]:
   if not g.battle:g.spawn_cartographer()
   with tempfile.TemporaryDirectory() as td:
    path=Path(td)/'save.json';g.save(path);other=r.Game.load(path)
    self.assertEqual(g.battle,other.battle);self.assertEqual(g.traveler,other.traveler);self.assertEqual(g.rng.getstate(),other.rng.getstate())
 def test_migrate_radiation_preserve_progress(self):
  g=r.Game(1);g.radiation={'5,5':3};g.xp=400
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);data=json.loads(path.read_text());data['version']=7;path.write_text(json.dumps(data));other=r.Game.load(path)
   self.assertEqual(other.xp,400);self.assertTrue(all(not(int(k.split(',')[0])<24 and int(k.split(',')[1])<16) for k in other.radiation))
 def test_profile_live_stats(self):
  g=r.Game(9);g.perks={'tactician':2,'marksman':1};text=player_text(g)
  self.assertIn('Тактик · ранг 2',text);self.assertIn(f'ОД: {g.max_ap}/{g.max_ap}',text);self.assertIn('×1.6',text)

if __name__=='__main__':unittest.main()
