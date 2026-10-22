"""Fire modes per weapon: class defaults, editor overrides, cycling and validation."""
import copy
import unittest
from unittest.mock import patch

import content
import entity_catalog
import fire_modes
from game.systems import combat


class FireModeTests(unittest.TestCase):
    def setUp(self):
        self.saved=copy.deepcopy(content.EQUIPMENT)

    def tearDown(self):
        content.EQUIPMENT.clear();content.EQUIPMENT.update(self.saved)

    def test_class_defaults_are_unchanged(self):
        self.assertEqual(fire_modes.allowed('automatic'),('single','burst'))
        self.assertEqual(fire_modes.allowed('sniper'),('aimed',))
        for category in ('pistol','rifle','shotgun'):self.assertEqual(fire_modes.allowed(category),('single',))
        self.assertEqual(combat.modes({'type_id':'weapon_rust_assault'}),('single','burst'))
        self.assertEqual(combat.modes({'type_id':'weapon_horizon_sniper'}),('aimed',))

    def test_every_mode_has_a_name_and_trade_offs(self):
        self.assertEqual(list(fire_modes.MODES),['single','burst','aimed'])
        for mode in fire_modes.MODES.values():
            self.assertTrue(mode['name'] and mode['pros'] and mode['cons'])

    def test_weapon_list_overrides_its_class_in_canonical_order(self):
        content.EQUIPMENT['weapon_ash_pistol']['fire_modes']=['aimed','single']
        self.assertEqual(combat.modes({'type_id':'weapon_ash_pistol'}),('single','aimed'))
        content.EQUIPMENT['weapon_ash_pistol']['fire_modes']=[]
        self.assertEqual(combat.modes({'type_id':'weapon_ash_pistol'}),('single',))
        content.EQUIPMENT['weapon_thunder_shotgun']['fire_modes']=['burst']
        self.assertEqual(combat.modes({'type_id':'weapon_thunder_shotgun'}),('single',))
        content.EQUIPMENT['weapon_thunder_shotgun']['fire_modes']=['single','aimed','burst']
        self.assertEqual(combat.modes({'type_id':'weapon_thunder_shotgun'}),('single','aimed'))

    def test_cost_follows_the_chosen_mode(self):
        content.EQUIPMENT['weapon_ash_pistol']['fire_modes']=['single','aimed']
        w={'type_id':'weapon_ash_pistol','ap':2}
        self.assertEqual(combat.shot_cost(w),2)
        self.assertEqual(combat.shot_cost(dict(w,fire_mode='aimed')),3)
        self.assertEqual(combat.shot_cost(dict(w,fire_mode='burst')),2)

    def test_cycling_walks_every_available_mode(self):
        from tests import test_update033 as arena
        content.EQUIPMENT['weapon_rust_assault']['fire_modes']=['single','burst','aimed']
        g,w,b=arena.Update033Tests().arena('weapon_rust_assault',5)
        seen=[g.fire_mode()]
        for _ in range(3):
            self.assertTrue(g.cycle_fire_mode());seen.append(g.fire_mode())
        self.assertEqual(seen,['single','burst','aimed','single'])
        content.EQUIPMENT['weapon_rust_assault']['fire_modes']=['aimed']
        self.assertFalse(g.cycle_fire_mode());self.assertEqual(g.fire_mode(),'aimed')

    def test_aimed_pistol_shot_uses_aimed_rules(self):
        from tests import test_update033 as arena
        content.EQUIPMENT['weapon_ash_pistol']['fire_modes']=['single','aimed']
        g,w,b=arena.Update033Tests().arena('weapon_ash_pistol',5);g.pop_events()
        g.cycle_fire_mode();self.assertEqual(g.fire_mode(),'aimed')
        ap=b['ap']
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):
            self.assertTrue(g.shoot('0'))
        self.assertEqual(ap-b['ap'],w['ap']+1)
        self.assertTrue(all(e['fire_mode']=='aimed' for e in g.pop_events() if e['kind']=='attack'))

    def test_editor_validation(self):
        ident='weapon_thunder_shotgun';data=copy.deepcopy(content.EQUIPMENT[ident])
        texts={'name':'Дробовик','description':''};art={data['sprite_id']}
        check=lambda modes:entity_catalog.validate_definition('weapon',ident,dict(data,fire_modes=modes),texts,art)
        self.assertEqual(entity_catalog.validate_definition('weapon',ident,data,texts,art),[])
        self.assertEqual(check(['single','aimed']),[])
        self.assertTrue(check([]));self.assertTrue(check(['rocket']));self.assertTrue(check(['single','single']))
        self.assertTrue(any('Черга' in e for e in check(['single','burst'])))
        self.assertEqual(entity_catalog.validate_definition('weapon','weapon_rust_assault',
            dict(copy.deepcopy(content.EQUIPMENT['weapon_rust_assault']),fire_modes=['burst','aimed']),texts,
            {content.EQUIPMENT['weapon_rust_assault']['sprite_id']}),[])


if __name__=='__main__':unittest.main()
