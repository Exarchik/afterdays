import tempfile
import unittest
from pathlib import Path
import event_catalog
import event_runtime
from game.model import Game
from tests.test_event_presentation import event


class AmbushTests(unittest.TestCase):
    def test_every_faction_and_mixed_are_hostile_with_exact_count(self):
        factions,_=event_catalog.ambush_catalog()
        for faction in [*factions['factions'],'mixed']:
            with self.subTest(faction=faction):
                g=Game(5)
                event_runtime.apply(g,dict(kind='ambush',faction=faction,amount=4),{'title':'Test'})
                actors=g.battle['enemies']
                self.assertEqual(len(actors),4)
                self.assertTrue(all(g.hostile_to_player(e) for e in actors))
                if faction=='mixed':self.assertGreater(len({e['faction'] for e in actors}),1)
                else:self.assertEqual({e['faction'] for e in actors},{faction})

    def test_monster_positions_report_rewards_and_saved_battle(self):
        g=Game(5)
        g.road_event=event([dict(kind='ambush',monster_id='monster_rodent',amount=30),dict(kind='money',amount=7),dict(kind='xp',amount=5)])
        self.assertTrue(g.resolve_event('yes'))
        actors=g.battle['enemies'];positions={tuple(e['pos']) for e in actors}
        self.assertEqual(g.battle['result_stats']['xp_start'],g.xp)
        self.assertEqual(len(positions),30)
        self.assertFalse(positions & set(map(tuple,g.battle['walls'])))
        self.assertNotIn(tuple(g.battle['pos']),positions)
        self.assertTrue(all(e['type_id']=='monster_rodent' for e in actors))
        self.assertTrue(any(r.get('effect_kind')=='ambush' for r in g._event_results[0]['rows']))
        self.assertTrue(any(i['kind']=='credits' and i['qty']==7 for i in g.loot))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);loaded=Game.load(path)
            self.assertEqual(loaded.battle['enemies'],actors)
            self.assertTrue(all(loaded.hostile_to_player(e) for e in loaded.battle['enemies']))

    def test_zero_chance_and_invalid_choices(self):
        g=Game(5)
        event_runtime.apply(g,dict(kind='ambush',faction='mixed',amount=3,chance=0),{'title':'Test'})
        self.assertIsNone(g.battle)
        for effect in [dict(faction='bad',amount=2),dict(monster_id='bad',amount=2),
                       dict(faction='mixed',amount=1),dict(faction='bandits',amount=0),
                       dict(faction='bandits',amount=31)]:
            self.assertTrue(event_catalog.ambush_error(effect))
