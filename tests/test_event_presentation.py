import unittest
from unittest.mock import patch
import game.model as r
import game.items as p
import event_runtime


def event(effects,costs=None):
    return dict(kind='presentation_test',title='Тестова подія',art='event_theme:camp',
                definition=dict(title='Тестова подія',choices=[dict(id='yes',costs=costs or [],
                    outcomes=[dict(chance=1,effects=effects)])]))


class EventPresentationTests(unittest.TestCase):
    def test_report_has_actual_rewards_losses_and_custom_item_art(self):
        g=r.Game(5);g.pop_events();g.hp=g.max_hp-1
        money=g.money
        g.road_event=event([dict(kind='money',amount=7),dict(kind='xp',amount=3),
                           dict(kind='heal',amount=20),dict(kind='med',amount=2,destination='loot')],
                          [dict(kind='money',amount=2)])
        self.assertTrue(g.resolve_event('yes'))
        report=g._event_results[0]
        self.assertEqual(report['title'],'Тестова подія')
        self.assertEqual([row['effect_kind'] for row in report['rows']],['money','money','xp','heal','med'])
        self.assertEqual(report['rows'][3]['text'],'+1 HP')
        self.assertEqual(report['rows'][-1]['item']['type_id'],'item_med')
        self.assertEqual(report['rows'][-1]['item']['qty'],2)
        self.assertEqual(report['rows'][-1]['destination'],'loot')
        self.assertEqual(g.money,money-2)
        states,items=__import__('event_results').groups(report)
        self.assertEqual([row['item']['kind'] for row in items],['credits','med'])
        self.assertEqual(items[0]['destination'],'loot')
        self.assertEqual(len(states),3)
        g.loot[-1]['qty']=50
        self.assertEqual(report['rows'][-1]['item']['qty'],2)

    def test_failed_choice_has_no_result_or_reward(self):
        g=r.Game(5);g.money=0
        g.road_event=event([dict(kind='money',amount=99)],[dict(kind='money',amount=2)])
        self.assertFalse(g.resolve_event('yes'))
        self.assertFalse(getattr(g,'_event_results',[]));self.assertEqual(g.money,0)

    def test_chance_zero_and_leave_have_no_invented_rewards(self):
        g=r.Game(5);g.road_event=event([dict(kind='med',amount=2,chance=0)])
        with patch.object(g.rng,'random',return_value=.5):self.assertTrue(g.resolve_event('yes'))
        self.assertEqual(g._event_results[0]['rows'],[])

    def test_cache_defers_report_and_reports_only_new_stack_quantity(self):
        g=r.Game(5);p.add_to(g.bag,p.parts(2));p.add_to(g.loot,p.parts(4))
        g.road_event=event([dict(kind='cache')],[dict(kind='money',amount=2)])
        spec=g.road_event['definition'];spec.update(id='locked_test',cache=[dict(kind='parts',amount=3)])
        self.assertTrue(g.resolve_event('yes'));self.assertFalse(getattr(g,'_event_results',[]))
        ident=g._lock_request;g._lock_request=None;cache=g.lock_context(ident)
        self.assertTrue(g.unlock_cache(ident,cache['lock_target']))
        rows=g._event_results[0]['rows']
        self.assertEqual(rows[0]['effect_kind'],'money')
        items=[row for row in rows if row.get('item')]
        self.assertEqual(len(items),1);self.assertEqual(items[0]['item']['qty'],3)
        self.assertEqual(items[0]['destination'],'loot')
        self.assertIsNot(g.unlock_cache(ident,90),True)
        self.assertEqual(len(g._event_results),1)

    def test_location_collect_respects_quantity_capacity_and_invalid_input(self):
        g=r.Game(5);g.bag=[];g.loot=[]
        item=p.parts(10);p.add_to(g.loot,item)
        self.assertTrue(g.collect(item['id'],3));self.assertEqual(g.count('parts'),3)
        self.assertEqual(g.loot[0]['qty'],7)
        self.assertFalse(g.collect(g.loot[0]['id'],-1))
        g.bag.append(dict(id='heavy',kind='quest',name='Heavy',weight=g.capacity,rarity=0))
        self.assertFalse(g.collect(g.loot[0]['id'],2));self.assertEqual(g.loot[0]['qty'],7)


if __name__=='__main__':unittest.main()
