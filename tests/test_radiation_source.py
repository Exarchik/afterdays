"""Dosimeter contracts: offers, unlimited probing, carrying the device back, editor settings."""
import copy
import tempfile
import unittest
from pathlib import Path

import world_hex
import quest_catalog
import quest_profiles
from game.model import Game
from game.systems import radiation_source as rs
from tests.fixtures.quest_offer import offer_for


def accepted(seed=4):
    g=Game(seed);offer=offer_for(g,rs.KIND)
    assert g.accept_quest(offer['id'])
    q=g.radiation_quest(offer['id']);g.x,g.y=q['pos']
    return g,q


def cells(q):
    size=q['rad_settings']['grid_size']
    return [(x,y) for y in range(size) for x in range(size)]


def find(g,q):
    return g.probe_radiation(q['id'],*q['rad_source'])


class RadiationSourceTests(unittest.TestCase):
    def test_offer_is_a_native_editor_type(self):
        self.assertIn(rs.KIND,quest_catalog.TYPES)
        g=Game(4);offer=offer_for(g,rs.KIND)
        self.assertEqual(offer['title'],rs.TITLE);self.assertGreater(offer['reward'],0)
        spec=quest_profiles.defaults(rs.KIND)
        self.assertEqual(rs.settings_for(spec),{'grid_size':6,'max_dose':5,'device_radiation':1})
        self.assertEqual(rs.device_art(spec),'')
        self.assertEqual(quest_profiles.validate_spec(spec),[])

    def test_accept_places_quest_and_board(self):
        g,q=accepted()
        self.assertTrue(g.radiation_available(q))
        self.assertNotIn(q['pos'],g.cities)
        self.assertIn(tuple(q['rad_source']),cells(q))
        self.assertEqual(q['rad_probes'],[]);self.assertEqual(q['rad_dose'],0)
        g.x,g.y=g.cities[q['city']];self.assertFalse(g.radiation_available(q))
        self.assertIsNone(g.probe_radiation(q['id'],0,0))

    def test_readings_fall_off_with_distance_and_are_deterministic(self):
        g,q=accepted()
        values={c:rs.reading_at(q,c) for c in cells(q)}
        source=tuple(q['rad_source'])
        self.assertEqual(max(values,key=values.get),source)
        by_distance={}
        for c,v in values.items():by_distance.setdefault(world_hex.distance(c,source),[]).append(v)
        ranges=[(min(v),max(v)) for _,v in sorted(by_distance.items())]
        for (low,_),(_,high) in zip(ranges,ranges[1:]):self.assertGreater(low,high)
        self.assertEqual(values,{c:rs.reading_at(q,c) for c in cells(q)})

    def test_probes_are_unlimited_and_cost_only_radiation(self):
        g,q=accepted();before=g.radiation_injury
        self.assertIsNone(g.probe_radiation(q['id'],-1,0))
        self.assertIsNone(g.probe_radiation(q['id'],0,'1'))
        others=[c for c in cells(q) if c!=tuple(q['rad_source'])]
        for c in others:self.assertIsNotNone(g.probe_radiation(q['id'],*c))
        self.assertEqual(len(q['rad_probes']),len(others))
        self.assertIsNone(g.probe_radiation(q['id'],*others[0]))
        self.assertTrue(g.radiation_available(q));self.assertEqual(q['progress'],0)
        self.assertEqual(g.radiation_injury-before,q['rad_dose'])
        self.assertGreater(q['rad_dose'],0)
        self.assertLessEqual(max(round(q['rad_settings']['max_dose']*p['value']/rs.PEAK) for p in q['rad_probes']),q['rad_settings']['max_dose'])
        self.assertIsNotNone(find(g,q));self.assertTrue(g.quest_ready(q))

    def test_probing_the_source_finds_the_device(self):
        g,q=accepted();before=g.radiation_injury
        self.assertIsNotNone(find(g,q))
        self.assertEqual(g.radiation_injury-before,q['rad_settings']['max_dose'])
        device=next(i for i in g.bag if rs.is_device(i,q))
        self.assertEqual((device['kind'],device['name'],device['weight']),('quest',rs.DEVICE_NAME,rs.DEVICE_WEIGHT))
        self.assertFalse(g.radiation_available(q))
        self.assertIsNone(g.probe_radiation(q['id'],0,0))
        self.assertEqual(sum(rs.is_device(i) for i in g.bag),1)

    def test_device_must_be_returned_to_giver(self):
        g,q=accepted();money=g.money;rep=g.reputation(q['city'])
        find(g,q);device=next(i for i in g.bag if rs.is_device(i,q))
        self.assertEqual(q['status'],'active');self.assertTrue(g.quest_ready(q))
        self.assertFalse(g.can_turn_in(q));self.assertFalse(g.turn_in(q['id']))
        self.assertFalse(g.stash_transfer(device['id'],'to_stash'))
        g.x,g.y=g.cities[q['city']];self.assertTrue(g.can_turn_in(q));self.assertTrue(g.turn_in(q['id']))
        self.assertEqual(q['status'],'done');self.assertEqual(g.money,money+q['reward'])
        self.assertGreaterEqual(g.reputation(q['city']),rep)
        self.assertFalse(any(rs.is_device(i) for i in g.bag+g.stash+g.loot))

    def test_device_irradiates_each_world_step(self):
        g,q=accepted();find(g,q)
        g.survival['hunger']=20;before=g.radiation_injury
        self.assertTrue(g._world_time_tick())
        self.assertEqual(g.radiation_injury-before,q['rad_settings']['device_radiation'])
        g.rad_turns=3;before=g.radiation_injury
        g._world_time_tick();self.assertEqual(g.radiation_injury,before)
        g.rad_turns=0;g.bag[:]=[i for i in g.bag if not rs.is_device(i)];before=g.radiation_injury
        g._world_time_tick();self.assertEqual(g.radiation_injury,before)
        self.assertFalse(g.quest_ready(q))

    def test_abandon_removes_device(self):
        g,q=accepted();find(g,q)
        self.assertTrue(g.abandon_quest(q['id']))
        self.assertFalse(any(rs.is_device(i) for i in g.bag+g.stash+g.loot))

    def test_journal_points_to_plot_then_to_giver(self):
        import quest_navigation
        g,q=accepted()
        self.assertEqual(quest_navigation.destination(g,q),q['pos'])
        self.assertEqual(g.quest_item_views(q)[0]['name'],rs.DEVICE_NAME)
        self.assertIn('без обмежень',g.quest_text(dict(q,status='offered')))
        find(g,q)
        self.assertEqual(list(quest_navigation.destination(g,q)),list(g.cities[q['city']]))
        self.assertEqual(g.quest_return_city(q),q['city'])
        self.assertIn('Віднесіть його замовнику',g.quest_text(q))

    def test_old_saves_with_attempt_limits_keep_working(self):
        g,q=accepted()
        q['rad_settings']['probes']=1;q['rad_retry_turn']=g.turn+50;q['rad_probes'].append(dict(cell=[9,9],value=1.0))
        self.assertTrue(g.radiation_available(q))
        self.assertIsNotNone(find(g,q));self.assertTrue(g.quest_ready(q))

    def test_profile_settings_are_used_and_validated(self):
        doc=copy.deepcopy(quest_catalog.DOCUMENT)
        spec=dict(quest_profiles.defaults(rs.KIND),grid_size=4,max_dose=0,device_radiation=2,device_art='quest:cache')
        doc.setdefault('native',{})[rs.KIND]={'normal':spec}
        self.assertEqual(quest_profiles.validate(doc),[])
        doc['native'][rs.KIND]['normal']=dict(spec,grid_size=12)
        self.assertTrue(quest_profiles.validate(doc))
        original=quest_catalog.DOCUMENT
        quest_catalog.DOCUMENT=dict(original,native={rs.KIND:{'normal':spec}})
        try:
            g,q=accepted()
            self.assertEqual(q['rad_settings'],{'grid_size':4,'max_dose':0,'device_radiation':2})
            before=g.radiation_injury
            find(g,q)
            self.assertEqual(g.radiation_injury,before)
            self.assertEqual(next(i for i in g.bag if rs.is_device(i,q))['sprite_id'],'quest:cache')
            g.survival['hunger']=20;g._world_time_tick()
            self.assertEqual(g.radiation_injury,before+2)
        finally:quest_catalog.DOCUMENT=original

    def test_state_survives_save_and_load(self):
        g,q=accepted();g.probe_radiation(q['id'],*next(c for c in cells(q) if c!=tuple(q['rad_source'])))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);h=Game.load(path)
        other=h.radiation_quest(q['id'])
        self.assertEqual(other['rad_probes'],q['rad_probes']);self.assertEqual(other['rad_source'],q['rad_source'])
        self.assertIsNotNone(find(h,other))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';h.save(path);k=Game.load(path)
        self.assertTrue(k.quest_ready(k.radiation_quest(q['id'])))


if __name__=='__main__':unittest.main()
