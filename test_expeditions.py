import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import afterdays as r
import progression as p
import content,monster_rules,economy
from expeditions import toggle_cells
from tests_fixtures.quest_offer import offer_for

class ExpeditionTests(unittest.TestCase):
 def contract(self,kind,seed=4):
  g=r.Game(seed);q=offer_for(g,kind);self.assertTrue(g.accept_quest(q['id']),kind);return g,g.quests[-1]
 def return_to_giver(self,g,q):
  g.battle=None;g.x,g.y=g.cities[q['city']]
  money=g.money;self.assertTrue(g.turn_in(q['id']));self.assertEqual(g.money,money+q['reward']);self.assertFalse(g.turn_in(q['id']))
 def test_species_levels_and_wilderness(self):
  levels=[monster_rules.base_level(i) for i in range(12)];self.assertEqual(sorted(levels),list(range(1,13)))
  g=r.Game(1)
  for level in range(1,16):
   for _ in range(30):
    kind=monster_rules.choose(g.rng,level);e=monster_rules.make(g.rng,kind,level,[1,1])
    self.assertLessEqual(e['level'],level);self.assertEqual(e['level'],e['base_level']-int(e['weak']))
  g=r.Game(3)
  for _ in range(15):
   g.start_battle();self.assertTrue(all(e['kind'] in (0,1) for e in g.battle['enemies']))
   self.assertTrue(all(e['weak'] for e in g.battle['enemies'] if e['kind']==1))
 def test_quest_targets_cannot_exceed_quest_level(self):
  for seed in range(5):
   g=r.Game(seed);g.mayor_offers()
   for q in g.offers[str(g.city)]:
    if q['kind'] in ('hunt','trophies','elite_hunt') and q['target_kind'] is not None:self.assertLessEqual(monster_rules.base_level(q['target_kind']),q['level'])
 def test_kill_xp_halved_and_local_rep_no_cascade(self):
  g=r.Game(4);e=monster_rules.make(g.rng,0,1,[2,2],grade='normal');old=round(23*.35+8*1.5+0*2+1+3)
  self.assertEqual(g.enemy_xp(e),old//2)
  g.cities[:3]=[[5,5],[15,5],[16,5]];g.x=g.y=5
  for _ in range(4):g.monster_killed(e,10,None)
  self.assertEqual(g.reputation(0),1);self.assertEqual(g.reputation(1),1);self.assertEqual(g.reputation(2),0)
  g.gain_xp(100);self.assertEqual(g.reputation(0),1)
 def test_rep_fraction_save_and_different_level(self):
  g=r.Game(4);g.monster_killed({},20,None);self.assertEqual(g.reputation(),0)
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
  self.assertAlmostEqual(h.local_record()['combat_fraction'],.5)
  with patch.object(h,'region_at',return_value=2):h.monster_killed({},40,None)
  self.assertEqual(h.reputation(),1)
 def test_field_armor_and_return_equipped(self):
  g=r.Game(4);offer=offer_for(g,'field_test');item=p.equipment('armor_plate_jacket' if 'armor_plate_jacket' in r.GEAR else next(k for k,v in r.GEAR.items() if v[0]=='armor'),level=1)
  item.update(field_test=True,quest_id=offer['id'],value=0,weight=0,modules=[],slots=0);offer['test_item']=item
  self.assertTrue(g.accept_quest(offer['id']));q=g.quests[-1];gear=g.quest_equipment(q)
  self.assertTrue(g.equip(gear['id'],'armor'));g.test_armor_hit(0);self.assertFalse(g.quest_ready(q));g.test_armor_hit(1);self.assertTrue(g.quest_ready(q))
  self.assertFalse(g.buys_kind(gear,0));self.assertFalse(g.dismantle(gear['id']));self.assertFalse(g.drop_item(gear['id']))
  self.return_to_giver(g,q);self.assertIsNone(g.equipped['armor']);self.assertIsNone(g.quest_equipment(q))
 def test_field_weapon_requires_actual_kill_with_test_weapon(self):
  g=r.Game(4);offer=offer_for(g,'field_test');item=p.equipment('weapon_ash_pistol',level=1)
  item.update(field_test=True,quest_id=offer['id'],value=0,weight=0,modules=[],slots=0);offer['test_item']=item
  self.assertTrue(g.accept_quest(offer['id']));q=g.quests[-1];gear=g.quest_equipment(q)
  g.monster_killed({},1,g.weapon);self.assertFalse(g.quest_ready(q))
  self.assertTrue(g.equip(gear['id'],'weapon1'));g.active='weapon1';g.start_battle();b=g.battle;b['walls']=[];b['pos']=[1,1];e=b['enemies'][0];e.update(pos=[2,1],hp=1,defense=0,resists={})
  with patch.object(g.rng,'randrange',return_value=0):self.assertTrue(g.shoot(e['id']))
  self.assertTrue(g.quest_ready(q));g.battle=None;self.assertTrue(g.abandon_quest(q['id']));self.assertIsNone(g.quest_equipment(q))
 def test_generator_solvable_consumes_materials_once(self):
  g,q=self.contract('generator');g.x,g.y=q['pos'];self.assertTrue(g.search());self.assertEqual(g._generator_request,q['id'])
  self.assertFalse(g.repair_generator(q['id']))
  for n in q['generator_order']:self.assertTrue(g.generator_toggle(q['id'],n))
  g.bag[:]=[i for i in g.bag if i['kind']!=q['material']];self.assertFalse(g.repair_generator(q['id']))
  p.add_to(g.bag,p.parts(q['material_qty']) if q['material']=='parts' else p.fragments(q['material_qty']))
  self.assertTrue(g.repair_generator(q['id']));self.assertEqual(g.count(q['material']),0);self.assertFalse(g.repair_generator(q['id']));self.return_to_giver(g,q)
 def test_cache_all_nine_cells_once_and_return(self):
  g,q=self.contract('cache');a,b,c,d=q['area'];target=q['cache_pos']
  self.assertEqual((c-a+1)*(d-b+1),9)
  for y in range(b,d+1):
   for x in range(a,c+1):
    if [x,y]==target:continue
    g.x,g.y=x,y;self.assertTrue(g.search());self.assertFalse(g.search());self.assertFalse(g.quest_ready(q))
  g.x,g.y=target;self.assertTrue(g.search());self.assertFalse(g.quest_ready(q));p.add_to(g.bag,p.parts(1));self.assertTrue(g.unlock_cache(q['id'],q['lock_target']));self.assertTrue(g.quest_ready(q));self.assertTrue(g.loot)
  before=copy.deepcopy(g.loot);self.assertIsNone(g.local_expedition());self.return_to_giver(g,q);self.assertEqual(before,g.loot);self.assertIsNone(g.quest_equipment(q))
 def test_elite_tracks_boss_minions_and_victory(self):
  g,q=self.contract('elite_hunt');self.assertIn(len(q['track']),(2,3))
  for pos in q['track']:
   g.x,g.y=pos;self.assertTrue(g.search())
  b=g.battle;self.assertIn(len(b['enemies']),(3,4));self.assertEqual(len({e['kind'] for e in b['enemies']}),1)
  self.assertIn(b['enemies'][0]['grade'],('rare','mythic'));self.assertTrue(all(e['grade']=='normal' for e in b['enemies'][1:]))
  b['kills']=[dict(kind=e['kind'],grade=e['grade'],level=e['level']) for e in b['enemies']];b['enemies']=[];g.victory();self.assertTrue(g.quest_ready(q));self.return_to_giver(g,q)
 def test_new_quest_state_survives_save(self):
  for kind in ('field_test','generator','cache','elite_hunt'):
   g,q=self.contract(kind)
   self.assertIn(q['title'],g.quest_text(q));self.assertIsInstance(g.quest_item_views(q),list)
   with tempfile.TemporaryDirectory() as td:
    path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
   self.assertEqual(q,next(x for x in h.quests if x['id']==q['id']))
 def test_trophy_values_and_drop_rules(self):
  for n in range(12):self.assertEqual(economy.trophy(n)['value'],2*(4+n))
  self.assertAlmostEqual(economy.loot_rules([dict(grade='normal')])[0],.0375)
 def test_radio_waveform_has_visual_parameters(self):
  from radio_ui import waveform
  ref=waveform([10,10,10])
  for values in ([11,10,10],[10,11,10],[10,10,11]):self.assertNotEqual(ref,waveform(values))
 def test_metro_single_chain(self):
  from frontier_ui import draw_metro
  g=r.Game(1);g.quests.extend(dict(metro_city=c,status='done',kind='retrieve') for c in (2,3,7))
  c=MagicMock();draw_metro(c,g,1,0,0,lambda x,y:True)
  lines=c.create_line.call_args_list;self.assertEqual(len(lines),4)
  from metro_routes import station_order
  order=station_order(g);expected=list(zip(order,order[1:]))
  for line,(a,b) in zip(lines,expected):self.assertEqual(line.args,tuple(v+.5 for v in g.cities[a]+g.cities[b]))
 def test_drop_damage_and_half_ammo(self):
  g=r.Game(7);g.start_battle();g.battle['kills']=[dict(kind=0,grade='normal',level=1)]
  with patch.object(g.rng,'random',return_value=0):g.victory()
  gear=[i for i in g.loot if i['kind'] in ('weapon','armor','helmet')]
  self.assertTrue(all(10<=i['durability']<=95 for i in gear))
  self.assertLessEqual(sum(i['qty'] for i in g.loot if i['kind']=='ammo'),12)
 def test_unseen_badge_and_green_offers(self):
  from refinement_ui import QuestCards
  from types import SimpleNamespace
  g=r.Game(4);q=offer_for(g,'generator');q.pop('seen',None)
  c=MagicMock();c.winfo_width.return_value=420;c.winfo_height.return_value=424
  panel=SimpleNamespace(canvas=c,entries=[q],app=SimpleNamespace(game=g),open_done=False,selection=None)
  with patch('refinement_ui.sprites.draw',return_value=False):QuestCards.paint(panel)
  texts=[call.kwargs for call in c.create_text.call_args_list]
  self.assertTrue(any(t.get('text')=='[нове]' for t in texts));self.assertTrue(any(t.get('fill')=='#8fdda0' for t in texts))
  q['seen']=True;c.reset_mock()
  with patch('refinement_ui.sprites.draw',return_value=False):QuestCards.paint(panel)
  self.assertFalse(any(call.kwargs.get('text')=='[нове]' for call in c.create_text.call_args_list))
  self.assertTrue(any(call.kwargs.get('fill')=='#8fdda0' for call in c.create_text.call_args_list))
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
  self.assertTrue(next(x for x in h.offers['0'] if x['id']==q['id'])['seen'])
 def test_cache_does_not_reveal_exact_target_on_map(self):
  from expedition_ui import draw_search_areas
  g,q=self.contract('cache');c=MagicMock();draw_search_areas(c,g,10,0,0)
  self.assertEqual(c.create_rectangle.call_count,1);self.assertEqual(c.create_oval.call_count,0)
  self.assertNotIn(str(tuple(q['cache_pos'])),g.quest_text(q))
