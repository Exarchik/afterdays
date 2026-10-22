"""Dosimeter contracts: sweeping, digging stray sources, carrying the device back, editor settings."""
import copy
import tempfile
import unittest
from pathlib import Path

import math
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


def device(q):
    return next(s for s in q['rad_sources'] if s['kind']=='device')


def find(g,q):
    s=device(q);return g.dig_radiation(q['id'],s['x'],s['y'])


class RadiationSourceTests(unittest.TestCase):
    def test_offer_is_a_native_editor_type(self):
        self.assertIn(rs.KIND,quest_catalog.TYPES)
        g=Game(4);offer=offer_for(g,rs.KIND)
        self.assertEqual(offer['title'],rs.TITLE);self.assertGreater(offer['reward'],0)
        spec=quest_profiles.defaults(rs.KIND)
        self.assertEqual(rs.settings_for(spec),{'grid_size':6,'isotopes':3,'max_dose':5,'device_radiation':1})
        self.assertEqual(rs.device_art(spec),'')
        self.assertEqual(quest_profiles.validate_spec(spec),[])

    def test_accept_plants_device_and_stray_sources(self):
        g,q=accepted()
        self.assertTrue(g.radiation_available(q))
        self.assertNotIn(q['pos'],g.cities)
        kinds=[s['kind'] for s in q['rad_sources']]
        self.assertEqual(kinds,['device','cs137','co60','sr90'])
        w,h=rs.area(q['rad_settings'])
        for s in q['rad_sources']:
            self.assertTrue(0<s['x']<w and 0<s['y']<h);self.assertFalse(s['found'])
        self.assertEqual(q['rad_holes'],[]);self.assertEqual(q['rad_dose'],0)
        g.x,g.y=g.cities[q['city']];self.assertFalse(g.radiation_available(q))
        self.assertIsNone(g.radiation_sweep(q['id'],1,1,.1));self.assertIsNone(g.dig_radiation(q['id'],1,1))

    def test_layout_is_deterministic_and_the_strongest_stray_masks_the_device(self):
        for seed in range(4,12):
            g,q=accepted(seed)
            self.assertEqual(rs.place_sources(q['id'],q['rad_attempt'],q['rad_settings']),
                             [dict(s,found=False) for s in q['rad_sources']])
            d=device(q);mask=q['rad_sources'][1]
            self.assertTrue(2.1<=math.dist((d['x'],d['y']),(mask['x'],mask['y']))<=3.05)
            # The device is barely a bump until the mask is lifted, then it stands out.
            ring=lambda:max(rs.reading(q,d['x']+math.cos(i/8*math.pi)*.6,d['y']+math.sin(i/8*math.pi)*.6) for i in range(16))
            masked=rs.reading(q,d['x'],d['y'])/ring()
            mask['found']=True;clear=rs.reading(q,d['x'],d['y'])/ring()
            self.assertLess(masked,1.25);self.assertGreater(clear,1.28);self.assertGreater(clear-masked,.1)

    def test_no_isotopes_leaves_only_the_device(self):
        sources=rs.place_sources('x',0,dict(grid_size=4,isotopes=0,max_dose=5,device_radiation=1))
        self.assertEqual([s['kind'] for s in sources],['device'])

    def test_sweeping_costs_radiation_over_time_and_validates_input(self):
        g,q=accepted();before=g.radiation_injury;mask=q['rad_sources'][1]
        self.assertIsNone(g.radiation_sweep(q['id'],-1,0,.1))
        self.assertIsNone(g.radiation_sweep(q['id'],0,'1',.1))
        self.assertIsNone(g.radiation_sweep(q['id'],True,1,.1))
        value=g.radiation_sweep(q['id'],mask['x'],mask['y'],0)
        self.assertGreater(value,40);self.assertEqual(g.radiation_injury,before)
        for _ in range(40):g.radiation_sweep(q['id'],mask['x'],mask['y'],.25)
        expected=q['rad_settings']['max_dose']*rs.SWEEP_RATE*value/rs.PEAK*10
        self.assertAlmostEqual(q['rad_dose']+q['rad_dose_left'],expected,places=6)
        self.assertEqual(g.radiation_injury-before,q['rad_dose'])
        # A huge time step from the UI is clamped.
        dose=q['rad_dose']+q['rad_dose_left'];g.radiation_sweep(q['id'],mask['x'],mask['y'],100)
        self.assertLessEqual(q['rad_dose']+q['rad_dose_left']-dose,q['rad_settings']['max_dose']*rs.SWEEP_RATE*rs.MAX_SWEEP*1.1)
        far=g.radiation_sweep(q['id'],0,0,0);self.assertLess(far,value)

    def test_digging_lifts_strays_and_lowers_the_field(self):
        g,q=accepted();mask=q['rad_sources'][1];d=device(q)
        before=g.radiation_injury
        miss=g.dig_radiation(q['id'],mask['x']+1,mask['y'])
        self.assertEqual(miss['result'],'empty');self.assertGreater(miss['dose'],0)
        self.assertEqual(g.radiation_injury-before,miss['dose']);self.assertEqual(len(q['rad_holes']),1)
        level=rs.reading(q,d['x'],d['y'])
        hit=g.dig_radiation(q['id'],mask['x']+.3,mask['y'])
        self.assertEqual((hit['result'],hit['name']),('isotope',rs.source_name(mask)))
        self.assertTrue(mask['found']);self.assertEqual(g.radiation_cleared(q),1)
        self.assertLess(rs.reading(q,d['x'],d['y']),level)
        self.assertEqual(g.dig_radiation(q['id'],mask['x'],mask['y'])['result'],'empty')
        self.assertTrue(g.radiation_available(q));self.assertEqual(q['progress'],0)

    def test_digging_the_device_finds_it(self):
        g,q=accepted();before=g.radiation_injury
        self.assertEqual(find(g,q)['result'],'device')
        self.assertEqual(g.radiation_injury,before)
        item=next(i for i in g.bag if rs.is_device(i,q))
        self.assertEqual((item['kind'],item['name'],item['weight']),('quest',rs.DEVICE_NAME,rs.DEVICE_WEIGHT))
        self.assertTrue(g.quest_ready(q));self.assertFalse(g.radiation_available(q))
        self.assertIsNone(g.dig_radiation(q['id'],1,1))
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
        self.assertIn('сторонніх джерел',g.quest_text(dict(q,status='offered')))
        find(g,q)
        self.assertEqual(list(quest_navigation.destination(g,q)),list(g.cities[q['city']]))
        self.assertEqual(g.quest_return_city(q),q['city'])
        self.assertIn('Віднесіть його замовнику',g.quest_text(q))

    def test_old_hex_probe_saves_are_replanted(self):
        g,q=accepted()
        for key in ('rad_sources','rad_holes','rad_dose_left'):q.pop(key)
        q.update(rad_source=[1,2],rad_probes=[dict(cell=[0,0],value=1.0)],rad_dose=7,rad_settings=dict(grid_size=5,max_dose=5,device_radiation=1))
        q=g.radiation_quest(q['id'])
        self.assertNotIn('rad_probes',q);self.assertNotIn('rad_source',q)
        self.assertEqual(q['rad_settings']['isotopes'],3);self.assertEqual(q['rad_dose'],7)
        self.assertEqual(find(g,q)['result'],'device');self.assertTrue(g.quest_ready(q))

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
            self.assertEqual(q['rad_settings'],{'grid_size':4,'isotopes':3,'max_dose':0,'device_radiation':2})
            before=g.radiation_injury
            find(g,q)
            self.assertEqual(g.radiation_injury,before)
            self.assertEqual(next(i for i in g.bag if rs.is_device(i,q))['sprite_id'],'quest:cache')
            g.survival['hunger']=20;g._world_time_tick()
            self.assertEqual(g.radiation_injury,before+2)
        finally:quest_catalog.DOCUMENT=original

    def test_state_survives_save_and_load(self):
        g,q=accepted();mask=q['rad_sources'][1];g.dig_radiation(q['id'],mask['x'],mask['y']);g.dig_radiation(q['id'],.5,.5)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);h=Game.load(path)
        other=h.radiation_quest(q['id'])
        self.assertEqual(other['rad_sources'],q['rad_sources']);self.assertEqual(other['rad_holes'],q['rad_holes'])
        self.assertIsNotNone(find(h,other))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';h.save(path);k=Game.load(path)
        self.assertTrue(k.quest_ready(k.radiation_quest(q['id'])))


if __name__=='__main__':unittest.main()
