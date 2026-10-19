"""Disc lock: geared rings, pick wear, premature attempts, determinism, editor settings, old saves."""
import copy
import random
import tempfile
import unittest
from pathlib import Path

import quest_catalog
import quest_minigames
import quest_profiles
import game.items as items
from game.model import Game
from game.systems import disc_lock as dl
from tests.fixtures.quest_offer import offer_for
from tests.fixtures.disc_lock import moves,solve,align


def quest_lock(seed=4,parts=5):
    g=Game(seed);offer=offer_for(g,'cache');assert g.accept_quest(offer['id'])
    q=g.quests[-1];g.x,g.y=q['cache_pos'];g.bag[:]=[i for i in g.bag if i['kind']!='parts']
    if parts:items.add_to(g.bag,items.parts(parts))
    assert g.search() and g._lock_request==q['id'];g._lock_request=None
    return g,q


class GenerationTests(unittest.TestCase):
    def test_defaults_validation_and_editor_block(self):
        spec=quest_profiles.defaults('cache')
        self.assertEqual(dl.settings_for(spec),dict(rings=4,positions=8,wear=10,depth=3))
        self.assertEqual(quest_profiles.validate_spec(spec),[])
        self.assertEqual([k for k,_ in quest_minigames.MINIGAMES['cache']['fields']],list(dl.SETTINGS))
        self.assertEqual(len(dl.validate_settings(dict(spec,rings=9,wear='x'))),2)

    def test_start_is_far_enough_and_always_solvable(self):
        for rings in (3,4,5):
            for seed in range(6):
                state=dl.generate(random.Random(seed),dl.settings_for(dict(rings=rings)))
                self.assertEqual(len(state['pos']),rings);self.assertFalse(dl.aligned(state))
                self.assertTrue(state['links']);self.assertGreaterEqual(state['best'],rings)
                path=moves(state);self.assertEqual(len(path),state['best'])
                probe=copy.deepcopy(state)
                for ring,direction in path:dl.apply(probe,ring,direction)
                self.assertTrue(dl.aligned(probe))

    def test_geared_rings_turn_together(self):
        state=dict(positions=8,links=[[0,1,1],[1,2,-1]],pos=[0,0,0])
        dl.apply(state,0,1);self.assertEqual(state['pos'],[1,1,0])
        dl.apply(state,1,1);self.assertEqual(state['pos'],[1,2,7])
        dl.apply(state,2,-1);self.assertEqual(state['pos'],[1,2,6])


class QuestCacheTests(unittest.TestCase):
    def test_lock_is_deterministic_and_does_not_touch_game_rng(self):
        g,q=quest_lock();state=copy.deepcopy(q['lock_disc']);rng=g.rng.getstate()
        q.pop('lock_disc');self.assertEqual(g.lock_state(q),state);self.assertEqual(rng,g.rng.getstate())

    def test_turns_wear_the_pick_and_break_it(self):
        g,q=quest_lock(parts=2);state=q['lock_disc'];state['wear_max']=3
        for _ in range(2):self.assertTrue(g.lock_turn(q['id'],0,1));self.assertFalse(g._lock_pick_broke)
        self.assertTrue(g.lock_turn(q['id'],0,1));self.assertTrue(g._lock_pick_broke)
        self.assertEqual(g.count('parts'),1);self.assertEqual(state['wear'],0);self.assertEqual(state['turned'],3)
        for _ in range(3):g.lock_turn(q['id'],0,-1)
        self.assertEqual(g.count('parts'),0);self.assertIsNone(g.lock_turn(q['id'],0,1))

    def test_undo_restores_position_but_not_wear(self):
        g,q=quest_lock();state=q['lock_disc'];start=state['pos'][:]
        g.lock_turn(q['id'],1,1);g.lock_turn(q['id'],2,-1)
        self.assertTrue(g.lock_undo(q['id']));self.assertTrue(g.lock_undo(q['id']))
        self.assertEqual(state['pos'],start);self.assertEqual(state['wear'],2);self.assertFalse(g.lock_undo(q['id']))

    def test_premature_open_breaks_a_pick_then_solving_opens(self):
        g,q=quest_lock(parts=3)
        self.assertFalse(g.unlock_cache(q['id']));self.assertEqual(g.count('parts'),2);self.assertFalse(g.quest_ready(q))
        solve(g,q['id']);self.assertTrue(g.unlock_cache(q['id']))
        self.assertTrue(q['lock_open']);self.assertTrue(g.quest_ready(q))
        self.assertIsNone(g.lock_turn(q['id'],0,1));self.assertIsNone(g.unlock_cache(q['id']))

    def test_editor_profile_controls_rings(self):
        g=Game(4);offer=offer_for(g,'cache')
        spec=dict(quest_profiles.defaults('cache'),rings=5,positions=6,wear=20)
        doc=copy.deepcopy(quest_catalog.DOCUMENT);doc.setdefault('native',{})['cache']={'normal':spec,'elite':spec}
        old=quest_catalog.DOCUMENT;quest_catalog.DOCUMENT=doc
        try:
            self.assertTrue(g.accept_quest(offer['id']));q=g.quests[-1];g.x,g.y=q['cache_pos'];g.search()
        finally:quest_catalog.DOCUMENT=old
        state=q['lock_disc'];self.assertEqual(len(state['pos']),5);self.assertEqual(state['positions'],6);self.assertEqual(state['wear_max'],20)

    def test_old_angle_saves_get_a_disc_lock(self):
        g,q=quest_lock();q.pop('lock_disc');q.pop('lock_found');q['lock_target']=77
        self.assertIsNotNone(g.lock_available(q['id']))
        self.assertTrue(g.lock_turn(q['id'],0,1));self.assertEqual(q['lock_disc']['version'],dl.VERSION)

    def test_state_survives_save(self):
        g,q=quest_lock();g.lock_turn(q['id'],0,1)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=Game.load(path)
        self.assertEqual(next(x for x in h.quests if x['id']==q['id'])['lock_disc'],q['lock_disc'])


class RoadCacheTests(unittest.TestCase):
    def test_road_cache_rings_scale_with_level(self):
        g=Game(1)
        for level,rings in ((1,3),(5,4),(12,5)):
            ctx=dict(id=f'road{level}',kind='road_cache',level=level)
            self.assertEqual(len(g.lock_state(ctx)['pos']),rings)


if __name__=='__main__':unittest.main()
