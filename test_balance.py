from tests_fixtures.quest_offer import offer_for
import json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import progression as p
import balance
from refinement_ui import description

class BalanceTests(unittest.TestCase):
 def test_xp_curve(self):
  total=0
  for level in range(1,100):
   self.assertEqual(p.xp_for_level(level),total);total+=balance.level_cost(level)
  self.assertEqual(p.xp_for_level(14),22080);self.assertEqual(balance.level_cost(13),4368)
 def test_monster_scaling_and_weapon_models(self):
  for kind in range(12):
   e=dict(kind=kind,level=5,grade='mythic');balance.set_monster(e)
   self.assertEqual(e['attack'],balance.MONSTER_STATS[kind][0]+12)
   self.assertEqual(e['defense'],balance.MONSTER_STATS[kind][1]+12)
  for name,minimum in p.GEAR_MIN_LEVEL.items():
   if r.GEAR[name][0]!='weapon':continue
   one=p.equipment(name,level=minimum);two=p.equipment(name,level=minimum+1)
   self.assertEqual(two['stats']['attack']-one['stats']['attack'],2)
  self.assertEqual(p.equipment('Гаус-карабін «Імпульс»',level=10)['stats']['attack'],36)
 def test_combat_both_directions(self):
  self.assertEqual(balance.damage(10,15,10),13);self.assertEqual(balance.damage(10,15,20),8)
  g=r.Game(8);g.start_battle();b=g.battle;b['walls']=[];b['pos']=[1,1];b['enemies']=b['enemies'][:1]
  e=b['enemies'][0];e.update(pos=[2,1],hp=1000,max_hp=1000,damage=10,attack=15,defense=20,resists={},speed=0,range=1)
  with patch.object(g.rng,'randrange',return_value=0),patch.object(g.rng,'randint',return_value=0):
   raw=p.stats(g.weapon)['damage']+2*(g.level-1);expected=balance.damage(raw*1.6,p.stats(g.weapon)['attack'],20)
   self.assertTrue(g.shoot(e['id']));self.assertEqual(e['hp'],1000-expected)
   hp=g.hp;expected=balance.damage(10,15,g.defense);g.end_turn();self.assertEqual(g.hp,hp-expected)
 def test_quest_reward_fixed_after_level_up(self):
  g=r.Game(4);q=offer_for(g,'retrieve',unique=True)
  g.accept_quest(q['id']);q=g.quests[-1];self.assertEqual(q['level'],1)
  reward=q['reward'];g.xp=p.xp_for_level(7);g.x,g.y=q['pos'];g.search();g.x,g.y=g.cities[0]
  before={i['id'] for i in g.bag+g.stash};xp=g.xp;self.assertTrue(g.turn_in(q['id']))
  awarded=[i for i in g.bag+g.stash if i['id'] not in before];self.assertTrue(awarded)
  self.assertTrue(all(i['level']==1 for i in awarded));self.assertEqual(g.xp-xp,80);self.assertEqual(q['reward'],reward)
  for i in awarded:self.assertTrue(all(m['level']==1 for m in i.get('modules',[])))
 def test_high_level_contract(self):
  g=r.Game(2);g.x,g.y=g.cities[2];q=g.mayor_offers()[0]
  self.assertEqual(q['level'],g.region_level);self.assertEqual(q['xp_reward'],(40+5*(q['level']-1))*(2 if q['unique'] else 1))
  for _ in range(10):self.assertEqual(g.reward_item(4,1,level=q['level'])['level'],q['level'])
 def test_traveler_distribution(self):
  g=r.Game(9);counts=[0]*5
  for _ in range(1500):
   p.Game.spawn_traveler(g)
   items=[i for i in g.traveler['items'] if i['kind'] in ('weapon','armor','helmet','module')]
   self.assertEqual(len(items),2)
   for item in items:counts[item['rarity']]+=1
  for count,expected in zip(counts,balance.TRAVELER_WEIGHTS):self.assertLess(abs(count/30-expected),3)
 def test_old_save_migration_once(self):
  g=r.Game(10);g.xp=60*13*14+780;g.hp=70
  g.weapon['stats'].pop('attack');mod=p.module(index=6);mod['stats']={'pierce':8};g.weapon['modules']=[mod]
  g.equipped['armor']=p.equipment('Куртка з пластинами',level=7);g.equipped['armor']['stats']['defense']=6
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);data=json.loads(path.read_text());data['version']=9;path.write_text(json.dumps(data))
   other=r.Game.load(path);self.assertEqual(other.level,14);self.assertEqual(other.xp,balance.migrate_xp(g.xp));self.assertEqual(other.hp,70)
   self.assertIn('attack',other.weapon['stats']);self.assertNotIn('pierce',other.weapon['modules'][0]['stats'])
   self.assertEqual(other.equipped['armor']['stats']['defense'],9)
   other.save(path);again=r.Game.load(path);self.assertEqual(other.xp,again.xp);self.assertEqual(other.equipped,again.equipped)
 def test_table_and_crafting(self):
  g=r.Game(2);item=p.equipment('Пістолет «Попіл»',level=2);text=description(g,item)
  self.assertIn('Характеристика\tЗначення\tРізниця',text);self.assertIn('Атака\t12',text);self.assertIn('[+]',text)
  g.bag.append(p.parts(150));before={i['id'] for i in g.bag};self.assertTrue(g.craft_module('parts',150));self.assertEqual(g.count('parts'),0)
  created=next(i for i in g.bag if i['id'] not in before);self.assertEqual(created['target'],'weapon');self.assertEqual(sum(g.craft_odds(150)),100)
  self.assertFalse(g.craft_module('parts',150))
if __name__=='__main__':unittest.main()
