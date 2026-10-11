import unittest
from unittest.mock import patch
import game.model as r
import event_runtime as runtime
import event_catalog as catalog

class EventRewardTests(unittest.TestCase):
    def test_event_costs_and_all_gains_are_logged_with_colors(self):
        import game.items as p
        g=r.Game(5);p.add_to(g.bag,p.parts(1));p.add_to(g.bag,p.fragments(1))
        g.road_event=dict(kind='test',definition=dict(title='Test',choices=[dict(id='yes',costs=[dict(kind='parts',amount=1),dict(kind='fragments',amount=1)],outcomes=[dict(chance=1,effects=[dict(kind='money',amount=45),dict(kind='xp',amount=5),dict(kind='parts',amount=2,destination='loot')])])]))
        g.pop_events();self.assertTrue(runtime.resolve(g,'yes'))
        notices=g.pop_events();self.assertEqual(len(notices),5)
        self.assertEqual([e['color'] for e in notices],['#e56860']*2+['#9cdda8']*3)
        for e in notices:
            index=g.messages.index(e['text']);self.assertEqual(g.message_colors[index],e['color'])
        self.assertIn('45',notices[2]['text']);self.assertIn('XP',notices[3]['text'])
        self.assertIn('(здобич)',notices[4]['text'])

    def test_actual_capped_values_and_old_log_alignment(self):
        g=r.Game(5);g.messages=['Old save entry'];g.__dict__.pop('message_colors',None)
        g.money=3;runtime.apply(g,dict(kind='money',amount=-10),{'title':'Test'})
        self.assertEqual(g.messages[-1],'-3 кредитів');self.assertEqual(g.message_colors,[None,'#e56860'])
        g.hp=g.max_hp-1;runtime.apply(g,dict(kind='heal',amount=10),{'title':'Test'})
        self.assertEqual(g.messages[-1],'+1 HP');self.assertEqual(g.message_colors[-1],'#9cdda8')

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
        notices=g.pop_events()
        self.assertEqual(len(notices),1)
        self.assertIn('(здобич)',notices[0]['text'])

    def test_wreck_damage_and_leave_do_not_announce_rewards(self):
        for choice in ('search','leave'):
            g=r.Game(5);g.make_road_event('wreck');g.pop_events();before=g.count('parts')
            with patch.object(g.rng,'random',return_value=0.9):g.resolve_event(choice)
            self.assertEqual(g.count('parts'),before)
            notices=g.pop_events()
            self.assertEqual(len(notices),1 if choice=='search' else 0)
            if notices:self.assertIn('8 HP',notices[0]['text'])
