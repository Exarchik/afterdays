import tempfile,unittest
from pathlib import Path
import afterdays as r
class QuestLocationTests(unittest.TestCase):
 def test_all_destination_types_and_cities(self):
  for seed in range(10):
   g=r.Game(seed)
   for city in (0,2,3,7):
    g.x,g.y=g.cities[city];g.quests=[]
    for kind in ('retrieve','scout','purge'):
     q=dict(id=r.uid(),kind=kind,city=city,status='offered',title='Test',progress=0,goal=1,target_kind=None,pos=None,unique=False)
     g.price_quest(q);g.offers[str(city)]=[q]
     self.assertTrue(g.accept_quest(q['id']))
     accepted=g.quests[-1];pos=tuple(accepted['pos'])
     self.assertLessEqual(g.region_at(*pos),q['level']+1)
     self.assertIn(pos,g.reachable_world(tuple(g.cities[city])))
    self.assertEqual(len({tuple(q['pos']) for q in g.quests}),3)
 def test_save_migrates_unsafe_target_once(self):
  g=r.Game(4);offer=next(q for q in g.mayor_offers() if q['kind']=='retrieve')
  self.assertTrue(g.accept_quest(offer['id']));q=g.quests[-1];q['pos']=[46,30];reward=q['reward']
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
   self.assertLessEqual(h.region_at(*h.quests[-1]['pos']),q['level']+1)
   self.assertEqual(h.quests[-1]['reward'],reward)
   h.save(path);j=r.Game.load(path);self.assertEqual(h.quests,j.quests)
 def test_no_valid_destination_does_not_accept(self):
  g=r.Game(4);offer=next(q for q in g.mayor_offers() if q['kind']=='retrieve')
  g.reachable_world=lambda start:{tuple(g.cities[0])}
  self.assertFalse(g.accept_quest(offer['id']));self.assertEqual(offer['status'],'offered');self.assertFalse(g.quests)
