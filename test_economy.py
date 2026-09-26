import unittest,copy,tempfile,json
from pathlib import Path
from unittest.mock import patch
import afterdays as r, progression as p
from economy import loot_rules,trophy,Game
class EconomyTests(unittest.TestCase):
 def test_roll_rules(self):
  """Перевіряє сценарій «roll rules» та очікувані результати."""
  make=lambda n,rare,myth:[dict(kind=0,grade=k) for k,count in [('normal',n),('rare',rare),('mythic',myth)] for _ in range(count)]
  for counts,chance,rolls,cap in [((3,0,0),.25,2,1),((2,1,0),.30,3,3),((2,1,1),.55,5,4),((0,0,5),1,12,4)]:
   actual=loot_rules(make(*counts));self.assertAlmostEqual(actual[0],chance*.25);self.assertEqual(actual[1:],(rolls,cap))
 def test_caps_and_player_level(self):
  """Перевіряє сценарій «caps and player level» та очікувані результати."""
  g=Game(6)
  for cap in (1,3,4):
   rarities=set();categories=set()
   for _ in range(300):
    item=g.reward_item(cap);rarities.add(item['rarity']);categories.add(item['kind']);self.assertLessEqual(item['level'],g.level)
    self.assertTrue(all(m['rarity']<=cap for m in item.get('modules',[])))
   self.assertTrue(max(rarities)<=cap);self.assertEqual(len(categories),4)
  for _ in range(30):self.assertGreater(g.reward_item(4,1)['rarity'],0)
 def test_prices_and_quests(self):
  """Перевіряє сценарій «prices and quests» та очікувані результати."""
  self.assertEqual(p.equipment('Пістолет «Попіл»',level=2)['value'],231)
  g=Game(6);q=dict(kind='hunt',city=0,zone=10,unique=False);g.price_quest(q);self.assertEqual(q['reward'],1397)
  g.xp=p.xp_for_level(20);g.price_quest(q);self.assertEqual(q['reward'],1397)
  q=dict(kind='supplies',city=0,zone=1,unique=False,food_need=3,med_need=2);g.price_quest(q);self.assertEqual(q['reward'],40+21*3+48*2)
 def test_trophy_trade_stacks(self):
  """Перевіряє сценарій «trophy trade stacks» та очікувані результати."""
  g=Game(4);a=trophy(0,2);b=trophy(1,3);p.add_to(g.bag,a);p.add_to(g.bag,b);p.add_to(g.bag,trophy(0,2))
  self.assertEqual(g.trophy_count(0),4);self.assertEqual(g.trophy_count(1),3)
  self.assertEqual(g.price(a,4,False),2*g.price(a,1,False))
  money=g.money;self.assertTrue(g.sell(a['id'],4,2));self.assertEqual(g.money,money+32);self.assertEqual(g.trophy_count(0),2)
  self.assertFalse(g.buys_kind(g.weapon,4))
 def test_trophy_contract_and_unique_reward(self):
  """Перевіряє сценарій «trophy contract and unique reward» та очікувані результати."""
  g=Game(3);offer=next(q for q in g.mayor_offers() if q['kind']=='trophies');offer['unique']=True;g.price_quest(offer)
  self.assertTrue(g.accept_quest(offer['id']));q=g.quests[-1]
  self.assertFalse(g.turn_in(q['id']));p.add_to(g.bag,trophy(q['target_kind'],q['goal']))
  baseline={i['id'] for i in g.bag+g.stash};money=g.money
  self.assertTrue(g.turn_in(q['id']));self.assertEqual(g.money,money+q['reward']);self.assertEqual(g.trophy_count(q['target_kind']),0)
  rewards=[i for i in g.bag+g.stash if i['id'] not in baseline];self.assertIn(len(rewards),(1,2));self.assertTrue(all(i['rarity']>=1 for i in rewards))
  self.assertFalse(g.turn_in(q['id']))
 def test_unique_full_bag_keeps_reward(self):
  """Перевіряє сценарій «unique full bag keeps reward» та очікувані результати."""
  g=Game(5);q=dict(id='test',kind='hunt',title='test',city=0,status='active',unique=True,goal=1,progress=1,target_kind=None,reward=100,pos=None);g.quests.append(q)
  g.bag.append(dict(id='heavy',kind='food',qty=1,name='heavy',weight=100,value=1,rarity=0))
  self.assertTrue(g.turn_in('test'));self.assertGreaterEqual(len(g.stash),1)
 def test_kill_records_save_and_zero_gear(self):
  """Перевіряє сценарій «kill records save and zero gear» та очікувані результати."""
  g=Game(3);g.start_battle();g.battle['kills']=[dict(kind=0,grade='rare')]
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);other=Game.load(path);self.assertEqual(other.battle['kills'],g.battle['kills'])
  with patch.object(g.rng,'random',return_value=.999):g.victory()
  self.assertFalse(g.loot);self.assertIsNone(g.battle)
 def test_old_save_reprices_preserves_contract(self):
  """Перевіряє сценарій «old save reprices preserves contract» та очікувані результати."""
  g=Game(4);g.weapon['value']=9999;g.quests.append(dict(id='contract',kind='hunt',city=0,status='active',reward=777,goal=4,progress=0,title='old',target_kind=None,pos=None))
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);data=json.loads(path.read_text());data['version']=6;path.write_text(json.dumps(data));other=Game.load(path)
   self.assertEqual(other.weapon['value'],94);self.assertEqual(other.quests[0]['reward'],777);self.assertTrue(other.available_merchant(4))
