from tests_fixtures.quest_offer import offer_for
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import content
import game.model as r
import game.progression as progression
import game.items as p
from ui.refinement import description
class NewContractTests(unittest.TestCase):
 # Готує або імітує операцію «offer» для перевірок NewContractTests.
 def offer(self,g,kind):return offer_for(g,kind)
 def test_delivery_flow_and_protection(self):
  """Перевіряє сценарій «delivery flow and protection» та очікувані результати."""
  g=r.Game(4);q=self.offer(g,'delivery');self.assertLessEqual(g.region_at(*q['pos']),q['level']+1)
  self.assertTrue(g.accept_quest(q['id']));q=g.quests[-1]
  parcel=next(i for i in g.bag if i.get('quest_id')==q['id'])
  self.assertFalse(g.buys_kind(parcel,2));self.assertFalse(g.can_turn_in(q));self.assertFalse(g.turn_in(q['id']))
  self.assertTrue(next(s for s in g.special_sites if s['id']==q['destination'])['found'])
  self.assertEqual(list(g.quest_return_pos(q)),list(q['pos']))
  money=g.money;g.x,g.y=q['pos'];self.assertFalse(g.search());self.assertIn(parcel,g.bag)
  self.assertTrue(g.turn_in(q['id']));self.assertNotIn(parcel,g.bag)
  # The recipient closes the quest immediately; no return to the quest giver.
  self.assertEqual(q['status'],'done');self.assertEqual(g.money,money+q['reward'])
  self.assertFalse(g.turn_in(q['id']));g.x,g.y=g.cities[q['city']];self.assertFalse(g.turn_in(q['id']))
 def test_delivery_rewards_and_legacy_save(self):
  for legacy in (False,True):
   with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as td:
    g=r.Game(4);q=self.offer(g,'delivery');g.accept_quest(q['id']);q=g.quests[-1]
    q['unique']=True
    gift=p.equipment('Пістолет «Попіл»',level=1)
    q.update(reward_items=[gift],reward_unique=True)
    g.xp=progression.xp_for_level(q['level']+5)
    if legacy:
     g.bag[:]=[i for i in g.bag if i.get('quest_id')!=q['id']]
     q['progress']=q['goal']
    path=Path(td)/'save.json';g.save(path);g=r.Game.load(path)
    q=next(v for v in g.quests if v['id']==q['id'])
    money,xp,rep=g.money,g.xp,g.reputation(q['city']);expected_xp=g.quest_xp(q)
    self.assertFalse(g.turn_in(q['id']))
    g.x,g.y=q['pos']
    with patch.object(g,'emit',wraps=g.emit) as emit:
     self.assertTrue(g.turn_in(q['id']))
     self.assertEqual(sum(c.args[0]==f'+{expected_xp} XP' for c in emit.call_args_list),1)
    self.assertEqual(g.money,money+q['reward']);self.assertEqual(g.xp,xp+expected_xp)
    self.assertEqual(g.reputation(q['city']),rep+8)
    self.assertEqual(sum(i['id']==gift['id'] for i in g.bag+g.stash),1)
    self.assertIn(f'+{q["reward"]} кр.',g.messages[-1]);self.assertIn(f'+{expected_xp} XP',g.messages[-1])
    self.assertEqual(g.message_colors[-1],'#99dca5')
    snapshot=(g.money,g.xp,g.reputation(q['city']),len(g.bag+g.stash))
    self.assertFalse(g.turn_in(q['id']))
    self.assertEqual(snapshot,(g.money,g.xp,g.reputation(q['city']),len(g.bag+g.stash)))
 def test_radio_cancel_retry_success_and_save(self):
  """Перевіряє сценарій «radio cancel retry success and save» та очікувані результати."""
  g=r.Game(4);q=self.offer(g,'radio');g.accept_quest(q['id']);q=g.quests[-1]
  self.assertLessEqual(g.region_at(*q['pos']),q['level']+1)
  self.assertFalse(g.tune_radio(q['id'],q['radio_target']))
  g.x,g.y=q['pos'];turn=g.turn;g.search();self.assertEqual(g.turn,turn)
  self.assertFalse(g.tune_radio(q['id'],[99,2,3]));self.assertEqual(g.turn,turn)
  self.assertFalse(g.tune_radio(q['id'],[0,0,0]));self.assertEqual(g.turn,turn+1)
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
   other=h.quests[-1];self.assertEqual(other['radio_values'],[0,0,0]);self.assertEqual(other['radio_attempts'],1)
   self.assertTrue(h.tune_radio(q['id'],other['radio_target']));self.assertFalse(h.tune_radio(q['id'],other['radio_target']))
   h.x,h.y=h.cities[q['city']];self.assertTrue(h.turn_in(q['id']))
 def test_monster_level_limits_not_player(self):
  """Перевіряє сценарій «monster level limits not player» та очікувані результати."""
  g=r.Game(3)
  for player in (1,20):
   g.xp=progression.xp_for_level(player)
   for level in (1,3,12):
    for _ in range(30):
     item=g.reward_item(level=g.monster_loot_level([dict(level=level)]))
     self.assertLessEqual(item['level'],level);self.assertGreaterEqual(item['level'],max(1,level-2))
 def test_victory_preserves_faction_loot_level(self):
  """Prepared equipment keeps its level regardless of the player's level."""
  g=r.Game(3);g.xp=progression.xp_for_level(20);g.start_battle();g.battle['kills']=[dict(kind=0,grade='normal',level=2)]
  item=p.equipment('Пістолет «Попіл»',level=2)
  g.battle['enemies']=[];g.battle['faction_loot']=[item]
  g.victory()
  gear=[i for i in g.loot if i['kind'] in ('weapon','armor','helmet','module')]
  self.assertEqual([i['id'] for i in gear],[item['id']]);self.assertEqual(gear[0]['level'],2)
 def test_kill_record_has_level(self):
  """Перевіряє сценарій «kill record has level» та очікувані результати."""
  g=r.Game(8);g.start_battle();b=g.battle;b['walls']=[];b['pos']=[1,1]
  e=b['enemies'][0];e.update(pos=[2,1],hp=1,level=7,defense=0,resists={})
  with patch.object(g.rng,'randrange',return_value=0):self.assertTrue(g.shoot(e['id']))
  self.assertEqual(b['kills'][-1]['level'],7)
 def test_city_names_and_saved_world(self):
  """Перевіряє сценарій «city names and saved world» та очікувані результати."""
  keys=content.read('city_names.json');self.assertEqual(len(set(keys)),1000)
  bank=[content.t(key) for key in keys]
  g=r.Game();h=r.Game();self.assertNotEqual(g.world,h.world);self.assertNotEqual(g.city_names,h.city_names)
  self.assertEqual(len(set(g.city_names)),15);self.assertTrue(set(g.city_names)<=set(bank))
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);loaded=r.Game.load(path)
   self.assertEqual(g.city_names,loaded.city_names);self.assertEqual(g.world,loaded.world)
 def test_consumable_description_has_no_level(self):
  """Перевіряє сценарій «consumable description has no level» та очікувані результати."""
  g=r.Game(1)
  for item in (p.supply('food'),p.supply('med'),p.supply('rad'),p.ammunition('pistol',3)):
   self.assertNotIn('L1',description(g,item))
  self.assertIn('L1',description(g,p.equipment('Пістолет «Попіл»',level=1)))
