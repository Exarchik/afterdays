"""Track scanner contracts: one print group, heavy lens, drain/recharge, lair reveal, editor settings."""
import copy
import math
import tempfile
import unittest
from pathlib import Path

import world_hex
import quest_profiles
import quest_minigames
from game.model import Game
from game.systems import track_scanner as ts
from tests.fixtures.quest_offer import offer_for


def accepted(seed=4):
    g=Game(seed);offer=offer_for(g,ts.KIND)
    assert g.accept_quest(offer['id'])
    q=g.quests[-1];g.x,g.y=q['pos']
    return g,q


def opened(seed=4):
    g,q=accepted(seed)
    assert g.search() and g._scanner_request==q['id']
    g._scanner_request=None
    return g,q


def read_all(g,q):
    for p in q['scanner']['prints']:
        if q['scanner']['done']:break
        g.scanner_tick(q['id'],0,[p['x'],p['y']],False)
        g.scanner_tick(q['id'],.05,[p['x'],p['y']],True)


class TrackScannerTests(unittest.TestCase):
    def test_defaults_and_editor_block(self):
        spec=quest_profiles.defaults(ts.KIND)
        self.assertEqual(ts.settings_for(spec),{'needed':3,'drain':38,'recharge':16,'lens_speed':55})
        self.assertEqual(quest_profiles.validate_spec(spec),[])
        self.assertIn(ts.KIND,quest_minigames.MINIGAMES)
        self.assertEqual([k for k,_ in quest_minigames.MINIGAMES[ts.KIND]['fields']],list(ts.SETTINGS))
        bad=dict(spec,needed=9,drain='x')
        errors=ts.validate_settings(bad)
        self.assertEqual(len(errors),2)

    def test_search_opens_scanner_once_costing_one_turn(self):
        g,q=accepted();turn=g.turn
        self.assertTrue(g.search());self.assertEqual(g._scanner_request,q['id']);self.assertEqual(g.turn,turn+1)
        self.assertTrue(g.search());self.assertEqual(g.turn,turn+1)
        self.assertIsNone(g.battle)
        s=q['scanner'];self.assertEqual(len(s['prints']),ts.PRINTS);self.assertEqual(s['energy'],100)

    def test_field_is_one_deterministic_group(self):
        g,q=opened();field=copy.deepcopy(q['scanner'])
        other={'id':q['id']};ts.build_field(other,field['settings'])
        self.assertEqual(other['scanner']['prints'],field['prints'])
        cx,cy=field['center']
        for p in field['prints']:
            self.assertLess(math.hypot(p['x']-cx,p['y']-cy),90)
            self.assertTrue(0<=p['x']<=ts.WIDTH and 0<=p['y']<=ts.HEIGHT)

    def test_switched_off_lens_follows_hand_and_recharges(self):
        g,q=opened();s=q['scanner'];s['energy']=50.0
        g.scanner_tick(q['id'],.1,[10,20],False)
        self.assertEqual(s['lens'],[10,20]);self.assertAlmostEqual(s['energy'],50+.1*16/10)
        g.scanner_tick(q['id'],5,[10,20],False)  # dt is capped to 0.1 s per tick
        self.assertAlmostEqual(s['energy'],50+.2*16/10)

    def test_switched_on_lens_is_heavy_and_drains_twenty_percent_faster(self):
        g,q=opened();s=q['scanner'];s['lens']=[100.0,100.0]
        for _ in range(10):g.scanner_tick(q['id'],.1,[800,100],True)
        self.assertAlmostEqual(s['lens'][0],100+55,places=4)
        self.assertAlmostEqual(s['energy'],100-3.8,places=4)
        self.assertAlmostEqual(38/10/3.2,1.1875,places=3)  # prototype drained 3.2 %/s

    def test_empty_battery_stops_scanning(self):
        g,q=opened();s=q['scanner'];s['energy']=0.0;p=s['prints'][0]
        r=g.scanner_tick(q['id'],.1,[p['x'],p['y']],True)
        self.assertTrue(r['empty']);self.assertEqual(s['read'],0);self.assertGreater(s['energy'],0)

    def test_reading_prints_reveals_lair_and_battle_follows(self):
        g,q=opened();start=q['pos'][:]
        read_all(g,q);s=q['scanner']
        self.assertTrue(s['done']);self.assertGreaterEqual(s['read'],3)
        self.assertEqual(q['track_index'],1);self.assertEqual(q['pos'],s['lair']);self.assertEqual(q['track'],[start,s['lair']])
        self.assertNotEqual(q['pos'],start)
        self.assertIsNone(g.scanner_quest(q['id']))
        self.assertEqual(g.scanner_tick(q['id'],.1,[0,0],True),dict(read=0,located=False,empty=False))
        g.x,g.y=start;g._scanner_request=None;g.search();self.assertIsNone(g._scanner_request);g.battle=None
        g.x,g.y=q['pos'];self.assertTrue(g.search());self.assertIsNotNone(g.battle)
        self.assertEqual(g.battle['elite_quest'],q['id'])

    def test_lair_lies_in_print_direction_when_possible(self):
        for seed in (1,4,7,11):
            g,q=opened(seed);start=q['pos'][:];pool=g.lair_candidates(q)
            read_all(g,q);lair=q['scanner']['lair']
            if pool:
                self.assertIn(lair,pool)
                self.assertTrue(ts.LAIR_DISTANCE[0]<=world_hex.distance(tuple(start),tuple(lair))<=ts.LAIR_DISTANCE[1])
                best=min(ts.angle_gap(ts.world_angle(start,p),q['scanner']['direction']) for p in pool)
                self.assertAlmostEqual(ts.angle_gap(ts.world_angle(start,lair),q['scanner']['direction']),best)

    def test_profile_settings_are_used(self):
        g,q=accepted()
        spec=dict(quest_profiles.defaults(ts.KIND),needed=1,drain=100)
        import quest_catalog
        doc=copy.deepcopy(quest_catalog.DOCUMENT);doc.setdefault('native',{})[ts.KIND]={'normal':spec,'elite':spec}
        old=quest_catalog.DOCUMENT;quest_catalog.DOCUMENT=doc
        try:
            self.assertTrue(g.search())
            self.assertEqual(q['scanner']['settings']['needed'],1)
            p=q['scanner']['prints'][0];g.scanner_tick(q['id'],0,[p['x'],p['y']],False)
            self.assertTrue(g.scanner_tick(q['id'],.05,[p['x'],p['y']],True)['located'])
        finally:quest_catalog.DOCUMENT=old

    def test_old_saves_past_first_point_are_untouched(self):
        g,q=accepted();q['track_index']=1;q['pos']=q['track'][1][:];g.x,g.y=q['pos']
        self.assertIsNone(g.scanner_quest());self.assertNotIn('scanner',q)

    def test_scanner_state_survives_save(self):
        g,q=opened();g.scanner_tick(q['id'],.1,[300,300],True)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=Game.load(path)
        self.assertEqual(next(x for x in h.quests if x['id']==q['id'])['scanner'],q['scanner'])


if __name__=='__main__':unittest.main()
