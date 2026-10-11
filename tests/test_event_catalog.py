"""Catalog integration: arbitrary authored events, persistence and transactional edits."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import game.model as r
import game.items as p
import event_catalog as c
import event_runtime


def custom():
    return dict(id='custom_test', category='exploration', terrain='forest', title='Тестова подія',
                description='Опис', enabled=True, weight=1, art='event_theme:camp',
                choices=[dict(id='act', text='Дослідити', costs=[], outcomes=[dict(chance=1, effects=[])])])


class CatalogTests(unittest.TestCase):
    def test_catalog_complete_and_unique(self):
        self.assertEqual(c.validate(c.DOCUMENT), [])
        self.assertGreaterEqual(len(c.EVENTS), 71); self.assertEqual(len(c.BY_ID), len(c.EVENTS))
        self.assertGreaterEqual(sum('cache' in e for e in c.EVENTS), 5)
        self.assertEqual(c.EVENTS, c.ordered(c.EVENTS))

    def test_authored_event_rewards_exact_xp_and_art(self):
        spec=custom(); spec['choices'][0]['outcomes'][0]['effects']=[dict(kind='xp',amount=37),dict(kind='ammo',amount=9,ammo='bolt'),dict(kind='money',amount=-50000)]
        with patch.dict(c.BY_ID, {spec['id']:spec}):
            g=r.Game(1); before=g.xp
            self.assertTrue(g.make_road_event(spec['id'])); self.assertEqual(g.road_event['art'],spec['art'])
            self.assertEqual(g.road_event['choices'][0][1],'Дослідити'); self.assertTrue(g.resolve_event('act'))
            self.assertEqual(g.xp-before,37); self.assertEqual(g.money,0)
            self.assertTrue(any(i.get('ammo_type')=='bolt' and i['qty']==9 for i in g.loot))
            state=copy.deepcopy((g.money,g.xp,g.loot)); self.assertFalse(g.resolve_event('act')); self.assertEqual(state,(g.money,g.xp,g.loot))

    def test_active_event_snapshot_survives_catalog_changes_and_save(self):
        spec=custom(); spec['choices'][0]['outcomes'][0]['effects']=[dict(kind='money',amount=43)]
        with patch.dict(c.BY_ID,{spec['id']:spec}):
            g=r.Game(1); g.make_road_event(spec['id']); spec['choices'][0]['outcomes'][0]['effects'][0]['amount']=900
            with tempfile.TemporaryDirectory() as folder:
                g.road_event['choices'][0][1]=c.choice_text(g.road_event['definition']['choices'][0])
                path=Path(folder)/'save.json'; g.save(path); h=r.Game.load(path)
            self.assertEqual(event_runtime.display_choices(h.road_event),[('act','Дослідити')])
            before=h.money; self.assertTrue(h.resolve_event('act')); self.assertEqual(h.money,before)
            self.assertEqual(sum(i['qty'] for i in h.loot if i['kind']=='credits'),43)

    def test_old_active_event_without_definition(self):
        g=r.Game(1); g.road_event=dict(kind='wounded',title='Old title',body='Old text',choices=[['help','Help'],['leave','Leave']],pos=[g.x,g.y])
        before=g.xp; self.assertTrue(g.resolve_event('help')); self.assertEqual(g.xp-before,20)

    def test_terrain_weight_disabled_and_empty_pool(self):
        spec=custom(); other=copy.deepcopy(spec); other.update(id='other',terrain='road')
        disabled=copy.deepcopy(spec); disabled.update(id='disabled',enabled=False)
        g=r.Game(1); g.world[g.y][g.x]='forest'
        with patch.object(c,'EVENTS',[spec,other,disabled]), patch.object(g.rng,'choices',return_value=[spec]) as choose:
            self.assertTrue(g.make_road_event()); self.assertEqual(choose.call_args.args[0],[spec]); self.assertEqual(choose.call_args.kwargs['weights'],[1])
        g.road_event=None
        with patch.object(c,'EVENTS',[]): self.assertFalse(g.make_road_event())
        with patch.dict(c.BY_ID,{'disabled':disabled}): self.assertFalse(g.make_road_event('disabled'))

    def test_costs_checked_together_before_mutation(self):
        spec=custom(); spec['choices'][0]['costs']=[dict(kind='money',amount=30),dict(kind='money',amount=30)]
        with patch.dict(c.BY_ID,{spec['id']:spec}):
            g=r.Game(1); g.money=50; g.make_road_event(spec['id']); before=g.rng.getstate()
            self.assertFalse(g.resolve_event('act')); self.assertEqual(g.money,50); self.assertIsNotNone(g.road_event); self.assertEqual(g.rng.getstate(),before)

    def test_outcomes_and_independent_effect_chance(self):
        spec=custom(); spec['choices'][0]['outcomes']=[dict(chance=.25,effects=[dict(kind='money',amount=100)]),dict(chance=.75,effects=[dict(kind='money',amount=5),dict(kind='money',amount=2,chance=.5)])]
        with patch.dict(c.BY_ID,{spec['id']:spec}):
            g=r.Game(1); g.make_road_event(spec['id']); before=g.money
            with patch.object(g.rng,'random',side_effect=[.8,.2]): self.assertTrue(g.resolve_event('act'))
            self.assertEqual(g.money,before)
            self.assertEqual(sum(i['qty'] for i in g.loot if i['kind']=='credits'),7)

    def test_custom_cache_persists_contents_and_rewards_once(self):
        spec=custom(); spec['choices'][0]['outcomes'][0]['effects']=[dict(kind='cache')]
        spec['cache']=[dict(kind='parts',amount=5,per_level=3)]
        with patch.dict(c.BY_ID,{spec['id']:spec}):
            g=r.Game(1); g.make_road_event(spec['id']); g.resolve_event('act'); cache=copy.deepcopy(g.road_cache())
            self.assertEqual(cache['contents'][0]['qty'],5+3*g.region_level)
            spec['cache'][0]['amount']=1000; g.make_road_event(spec['id']); g.resolve_event('act'); self.assertEqual(cache,g.road_cache())
            p.add_to(g.bag,p.parts(1))
            self.assertTrue(g.unlock_cache(cache['id'],cache['lock_target'])); before=copy.deepcopy(g.loot)
            self.assertIsNone(g.unlock_cache(cache['id'],cache['lock_target'])); self.assertEqual(g.loot,before)

    def test_damage_stops_effects_on_defeat_even_at_spawn(self):
        spec=custom(); spec['choices'][0]['outcomes'][0]['effects']=[dict(kind='damage',amount=999),dict(kind='xp',amount=999)]
        with patch.dict(c.BY_ID,{spec['id']:spec}):
            g=r.Game(1); before=g.xp; g.make_road_event(spec['id']); g.resolve_event('act'); self.assertEqual(g.xp,before)

    def test_xp_penalty_still_applies(self):
        g=r.Game(1); g.reputation_state['coward_until']=g.turn+50; before=g.xp
        g.make_road_event('wounded'); g.resolve_event('help'); self.assertEqual(g.xp-before,10)

    def test_cache_formula_levels(self):
        effect=dict(kind='food',amount=3,step=4,step_cap=3)
        g=r.Game(1)
        self.assertEqual([c.amount(effect,L,g.rng) for L in (1,4,5,9,13,99)],[3,3,4,5,6,6])

    def test_safe_credits_persist_and_collect_once(self):
        spec=custom();spec['choices'][0]['outcomes'][0]['effects']=[dict(kind='cache')]
        spec['cache']=[dict(kind='money',amount=100,maximum=150,per_level=5)]
        self.assertEqual(c.validate(dict(version=1,events=[spec])),[])
        with patch.dict(c.BY_ID,{spec['id']:spec}),tempfile.TemporaryDirectory() as folder:
            g=r.Game(1);before=g.money
            g.make_road_event(spec['id']);g.resolve_event('act');cache=copy.deepcopy(g.road_cache())
            coins=cache['contents'][0];self.assertEqual(coins['kind'],'credits')
            self.assertTrue(100+5*g.region_level<=coins['qty']<=150+5*g.region_level)
            self.assertEqual(g.money,before)
            path=Path(folder)/'save.json';g.save(path);g=r.Game.load(path)
            self.assertEqual(g.road_cache()['contents'],cache['contents'])
            p.add_to(g.bag,p.parts(2))
            wrong=0 if cache['lock_target']>90 else 180
            self.assertFalse(g.unlock_cache(cache['id'],wrong));self.assertEqual(g.money,before)
            self.assertTrue(g.unlock_cache(cache['id'],cache['lock_target']))
            self.assertEqual(g.money,before);self.assertTrue(g.collect(coins['id']))
            self.assertEqual(g.money,before+coins['qty'])
            self.assertIsNone(g.unlock_cache(cache['id'],cache['lock_target']))
            self.assertFalse(g.collect(coins['id']));self.assertEqual(g.money,before+coins['qty'])
        for amount in (0,-1):
            spec['cache'][0]['amount']=amount
            self.assertTrue(c.validate(dict(version=1,events=[spec])))

    def test_atomic_save_validation_backup_and_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'events.json'; doc=dict(version=1,events=[custom()]); c.save(doc,path)
            before=path.read_bytes(); doc['events'][0]['title']='Інша назва'; c.save(doc,path)
            self.assertEqual(path.with_suffix('.json.bak').read_bytes(),before)
            self.assertEqual(c.load(path)['events'][0]['title'],'Інша назва')
            before=path.read_bytes(); doc['events'][0]['weight']=float('nan')
            with self.assertRaises(ValueError): c.save(doc,path)
            self.assertEqual(path.read_bytes(),before)

    def test_invalid_probabilities_art_ids_and_cache_rewards(self):
        for field,value in [('art','missing'),('weight',0),('id','BAD ID'),('terrain','sea')]:
            spec=custom(); spec[field]=value; self.assertTrue(c.validate(dict(version=1,events=[spec])))
        spec=custom(); spec['choices'][0]['outcomes'][0]['chance']=.8
        self.assertTrue(c.validate(dict(version=1,events=[spec])))
        spec=custom(); spec['cache']=[dict(kind='med',amount=-1)]
        self.assertTrue(c.validate(dict(version=1,events=[spec])))


if __name__=='__main__': unittest.main()
