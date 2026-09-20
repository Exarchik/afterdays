import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import afterdays as r
import progression as p
import monster_rules,economy,frontier_ui,sprites
from tests_fixtures.quest_offer import offer_for
from expedition_ui import draw_search_areas

class ScavengingTests(unittest.TestCase):
 def quest(self,kind,seed=4):
  g=r.Game(seed);offer=offer_for(g,kind);self.assertTrue(g.accept_quest(offer['id']));return g,g.quests[-1]
 def save_reload(self,g):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);return r.Game.load(path)
 def test_repairkit_stacks_zero_weight_and_exact_repair(self):
  g=r.Game(4);w=g.weapon;weight=g.weight;w['durability']=40
  p.add_to(g.bag,p.supply('repairkit',2));p.add_to(g.bag,p.supply('repairkit',3))
  self.assertEqual(g.count('repairkit'),5);self.assertEqual(g.weight,weight)
  kit=next(i for i in g.bag if i['kind']=='repairkit');self.assertEqual(kit['value'],50)
  self.assertTrue(g.repair_with_kit(w['id']));self.assertEqual(w['durability'],75)
  self.assertTrue(g.repair_with_kit(w['id']));self.assertEqual(w['durability'],100)
  self.assertFalse(g.repair_with_kit(w['id']));self.assertEqual(g.count('repairkit'),3)
  w['durability']=0;g.start_battle();self.assertFalse(g.repair_with_kit(w['id']));self.assertEqual(g.count('repairkit'),3)
  g.battle=None;self.assertTrue(g.repair_with_kit(w['id']));self.assertEqual(w['durability'],35)
 def test_kits_all_equipment_and_save(self):
  g=r.Game(2);p.add_to(g.bag,p.supply('repairkit',3))
  for category in ('weapon','armor','helmet'):
   key=next(k for k,v in r.GEAR.items() if v[0]==category and p.GEAR_MIN_LEVEL[k]==1)
   item=p.equipment(key);item['durability']=25;g.bag.append(item)
   self.assertTrue(g.repair_with_kit(item['id']));self.assertEqual(item['durability'],60)
  self.assertEqual(g.count('repairkit'),0);h=self.save_reload(g);self.assertEqual(g.bag,h.bag)
 def test_shop_kits_are_visible_and_not_infinite(self):
  g=r.Game(4);g.money=100000
  for merchant in (0,2):
   items=g.stock(merchant);kit=next(i for i in items if i['kind']=='repairkit');qty=kit['qty']
   self.assertEqual(sprites.item_key(kit),'repair');self.assertLess(g.price(kit,merchant,False),g.price(kit,merchant,True))
   self.assertTrue(g.buy(kit['id'],merchant,qty));self.assertFalse(any(i['kind']=='repairkit' for i in g.stock(merchant)))
   self.assertTrue(all(i['kind']=='sealed' for i in g.stock(2))) if merchant==2 else None
  g.turn+=40;self.assertTrue(any(i['kind']=='repairkit' for i in g.stock(2)))
 def test_traveler_optional_kits(self):
  for roll,expected in ((.1,True),(.9,False)):
   g=r.Game(2);g.traveler=dict(pos=[g.x,g.y],items=[p.supply('food')])
   with patch.object(g.rng,'random',return_value=roll):items=g.stock(3)
   self.assertEqual(any(i['kind']=='repairkit' for i in items),expected)
   self.assertEqual(g.stock(3),items)
 def test_salvage_price_rarity_modules_do_not_change_yield(self):
  g=r.Game(4);item=p.equipment('weapon_ash_pistol',level=10);self.assertEqual(g.salvage_yield(item),50)
  other=copy.deepcopy(item);other.update(value=999999,rarity=4,modules=[p.module(4)])
  self.assertEqual(g.salvage_yield(item),g.salvage_yield(other))
  item['durability']=50;self.assertEqual(g.salvage_yield(item),30)
  item['durability']=0;self.assertEqual(g.salvage_yield(item),10)
  item.update(level=100,durability=100);self.assertEqual(g.salvage_yield(item),100)
 def test_craft_failure_interpolation_and_consumption(self):
  g=r.Game(1)
  for amount,expected in [(10,.7),(75,.25),(150,0),(1000,0),(42.5,.475),(112.5,.125)]:self.assertAlmostEqual(g.craft_failure(amount),expected)
  p.add_to(g.bag,p.parts(1000));before={i['id'] for i in g.bag}
  with patch.object(g.rng,'random',return_value=0):self.assertFalse(g.craft_module('parts',10))
  self.assertEqual(g.count('parts'),990);self.assertTrue(g._craft_failed);self.assertEqual(before,{i['id'] for i in g.bag})
  state=g.rng.getstate();self.assertFalse(g.craft_module('parts',1001));self.assertEqual(g.rng.getstate(),state);self.assertEqual(g.count('parts'),990)
  self.assertTrue(g.craft_module('parts',150));self.assertEqual(g.count('parts'),840)
  p.add_to(g.bag,p.fragments(1000));self.assertTrue(g.craft_module('fragments',1000));self.assertEqual(g.count('fragments'),0)
  for n in (10,75,150,500,1000):self.assertAlmostEqual(sum(g.craft_odds(n)),100)
  self.assertLess(g.craft_odds(150)[4],g.craft_odds(1000)[4])
 def test_scout_visits_nine_distinct_cells(self):
  g,q=self.quest('scout');x,y,xx,yy=q['area'];self.assertEqual(q['goal'],9)
  g.x,g.y=q['pos'];g._visit_objectives();g._visit_objectives();self.assertEqual(q['progress'],1);self.assertFalse(g.quest_ready(q))
  for cy in range(y,yy+1):
   for cx in range(x,xx+1):g.x,g.y=cx,cy;g._visit_objectives()
  self.assertTrue(g.quest_ready(q));g.x,g.y=g.cities[q['city']];self.assertTrue(g.turn_in(q['id']))
 def test_relic_search_no_fixed_center_shortcut(self):
  g,q=self.quest('retrieve');x,y,xx,yy=q['area'];self.assertFalse(any(i.get('quest_id')==q['id'] for i in g.bag))
  for cy in range(y,yy+1):
   for cx in range(x,xx+1):
    if [cx,cy]==q['relic_pos']:continue
    g.x,g.y=cx,cy;before=g.turn;self.assertTrue(g.search());self.assertEqual(g.turn,before+1);self.assertFalse(g.quest_ready(q));self.assertFalse(g.search())
  g.x,g.y=q['relic_pos'];self.assertTrue(g.search());self.assertTrue(g.quest_ready(q));self.assertEqual(sum(i.get('quest_id')==q['id'] for i in g.bag),1)
  g.x,g.y=g.cities[q['city']];self.assertTrue(g.turn_in(q['id']));self.assertFalse(g.quest_equipment(q))
 def test_area_cells_obey_location_bounds(self):
  for kind in ('scout','retrieve'):
   g,q=self.quest(kind);reachable=g.player_reachable_world(g.cities[q['city']]);x,y,xx,yy=q['area']
   for cy in range(y,yy+1):
    for cx in range(x,xx+1):self.assertIn((cx,cy),reachable);self.assertLessEqual(g.region_at(cx,cy),q['level']+1)
 def test_generator_wrong_order_resets_and_saves(self):
  g,q=self.quest('generator');g.x,g.y=q['pos'];order=q['generator_order'][:];self.assertEqual(sorted(order),list(range(5)))
  self.assertTrue(g.generator_toggle(q['id'],order[0]));self.assertEqual(len(q['generator_input']),1)
  self.assertTrue(g.generator_toggle(q['id'],order[2]));self.assertEqual(q['generator_input'],[])
  self.assertFalse(g.generator_toggle(q['id'],5));self.assertFalse(g.repair_generator(q['id']))
  g.generator_toggle(q['id'],order[0]);h=self.save_reload(g);q=h.quests[-1];self.assertEqual(q['generator_input'],order[:1]);self.assertEqual(q['generator_order'],order)
  for n in order[1:]:h.generator_toggle(q['id'],n)
  h.bag[:]=[i for i in h.bag if i['kind']!=q['material']];self.assertFalse(h.repair_generator(q['id']))
  p.add_to(h.bag,p.supply(q['material'],q['material_qty']));self.assertTrue(h.repair_generator(q['id']));self.assertFalse(h.repair_generator(q['id']))
 def test_junk_covered_targets_and_once_only_bonus(self):
  g,q=self.quest('junkyard');g.x,g.y=q['pos'];g.search();self.assertEqual(g._junkyard_request,q['id'])
  target=next(o for o in q['junk_objects'] if o['kind']=='target');self.assertFalse(g.junk_collect(q['id'],target['x']+10,target['y']+10))
  for obj in list(q['junk_objects']):
   if obj['kind']=='debris':self.assertTrue(g.junk_move(q['id'],obj['id'],850,560))
  for obj in q['junk_objects'][:]:
   if obj['kind']=='debris':continue
   for scrap in list(q['junk_objects']):
    if scrap['kind']=='debris':g.junk_move(q['id'],scrap['id'],850 if obj['x']<425 else 0,560 if obj['y']<280 else 0)
   self.assertTrue(g.junk_collect(q['id'],obj['x']+10,obj['y']+10));self.assertFalse(g.junk_collect(q['id'],obj['x']+10,obj['y']+10))
  self.assertTrue(g.quest_ready(q));self.assertTrue(g.loot);g.x,g.y=g.cities[q['city']];self.assertTrue(g.turn_in(q['id']));self.assertFalse(g.quest_equipment(q))
 def test_junk_state_persists_and_cancel_cleans_items(self):
  g,q=self.quest('junkyard');g.x,g.y=q['pos'];g.search()
  for obj in list(q['junk_objects']):
   if obj['kind']=='debris':g.junk_move(q['id'],obj['id'],850,560)
  target=next(o for o in q['junk_objects'] if o['kind']=='target');g.junk_collect(q['id'],target['x']+10,target['y']+10)
  h=self.save_reload(g);self.assertEqual(h.quests[-1]['junk_objects'],q['junk_objects']);self.assertEqual(h.quests[-1]['progress'],1)
  self.assertTrue(h.abandon_quest(q['id']));self.assertFalse(h.quest_equipment(q))
 def test_spawn_weights_favor_close_species(self):
  kinds=monster_rules.eligible(5);normal=sorted((monster_rules.base_level(k),monster_rules.spawn_weight(k,5)) for k in kinds if monster_rules.base_level(k)<=5)
  self.assertTrue(all(a[1]<b[1] for a,b in zip(normal,normal[1:])))
  g=r.Game(4);counts={k:0 for k in kinds}
  for _ in range(5000):counts[monster_rules.choose(g.rng,5)]+=1
  nearest=next(k for k in kinds if monster_rules.base_level(k)==5);weak=next(k for k in kinds if monster_rules.base_level(k)==6)
  self.assertGreater(counts[nearest],2500);self.assertLess(counts[weak],500)
 def test_loot_reduction_and_ammo_probability(self):
  self.assertAlmostEqual(economy.loot_rules([{'grade':'normal'}])[0],.0375)
  g=r.Game(4);g.start_battle();g.battle['kills']=[];g.loot=[]
  with patch.object(g.rng,'random',return_value=.3):g.victory()
  self.assertFalse(any(i['kind'] in ('ammo','weapon','armor','helmet','module') for i in g.loot))
 def test_xp_and_area_rendering(self):
  g,q=self.quest('scout');text=frontier_ui.player_text(g);self.assertIn(str(p.xp_for_level(g.level+1)-g.xp)+' XP',text)
  canvas=MagicMock();draw_search_areas(canvas,g,20,0,0);self.assertEqual(canvas.create_rectangle.call_count,1)
 def test_old_generator_and_quests_migrate_without_losing_rewards(self):
  g,q=self.quest('generator');q.pop('generator_order');q.pop('generator_input');q['generator_board']=[1]*9;reward=q['reward']
  h=self.save_reload(g);self.assertEqual(len(h.quests[-1]['generator_order']),5);self.assertEqual(h.quests[-1]['reward'],reward)
  g,q=self.quest('scout');q.pop('area');q.pop('visited_cells');q['goal']=1
  h=self.save_reload(g);self.assertEqual(h.quests[-1]['goal'],9);self.assertEqual(len(h.quests[-1]['area']),4)

if __name__=='__main__':unittest.main()
