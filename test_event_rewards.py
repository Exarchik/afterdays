import unittest
from unittest.mock import patch
import afterdays as r
import event_runtime as runtime
import event_catalog as catalog

class EventRewardTests(unittest.TestCase):
    def test_all_inventory_reward_kinds_announce_received_quantity(self):
        g=r.Game(5)
        for kind in sorted(catalog.ITEM_KINDS|{'gear'}):
            with self.subTest(kind=kind):
                g.pop_events()
                effect=dict(kind=kind,amount=3,destination='bag',ammo='pistol')
                reward=runtime.item(g,effect,g.region_level)
                name,qty=reward['name'],reward.get('qty',1)
                with patch.object(runtime,'item',return_value=reward):
                    runtime.apply(g,effect,{'title':'Test'})
                notices=g.pop_events()
                self.assertEqual([e['text'] for e in notices],[f'+{qty} {name}'])
                self.assertEqual(notices[0]['entity'],'player')

    def test_wreck_reports_only_added_parts_even_when_stacking(self):
        g=r.Game(5);before=g.count('parts');g.make_road_event('wreck');g.pop_events()
        with patch.object(g.rng,'random',return_value=0.1):
            self.assertTrue(g.resolve_event('search'))
        delta=g.count('parts')-before
        self.assertGreaterEqual(delta,12);self.assertLessEqual(delta,35)
        name=next(i['name'] for i in g.bag if i['kind']=='parts')
        self.assertEqual([e['text'] for e in g.pop_events()],[f'+{delta} {name}'])

    def test_loot_zero_loss_and_skipped_rewards_do_not_announce_gains(self):
        g=r.Game(5);g.pop_events()
        for effect in (dict(kind='parts',amount=2),dict(kind='parts',amount=0,destination='bag'),
                       dict(kind='parts',amount=-1,destination='bag'),
                       dict(kind='parts',amount=2,destination='bag',chance=0)):
            runtime.apply(g,effect,{'title':'Test'})
        self.assertEqual(g.pop_events(),[])

    def test_wreck_damage_and_leave_do_not_announce_rewards(self):
        for choice in ('search','leave'):
            g=r.Game(5);g.make_road_event('wreck');g.pop_events();before=g.count('parts')
            with patch.object(g.rng,'random',return_value=0.9):g.resolve_event(choice)
            self.assertEqual(g.count('parts'),before)
            notices=g.pop_events()
            self.assertEqual(len(notices),1 if choice=='search' else 0)
            if notices:self.assertIn('8 HP',notices[0]['text'])
