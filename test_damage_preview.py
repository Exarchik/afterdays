import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r,progression as p,content
import damage_preview as dp
import test_update033 as arena

class DamagePreviewTests(unittest.TestCase):
    def test_ranges_match_live_attacks_and_full_ap_with_wear(self):
        for key,mode in [('weapon_ash_pistol','single'),('weapon_rust_assault','burst'),
                         ('weapon_thunder_shotgun','single'),('weapon_horizon_sniper','aimed')]:
            for maximum in (False,True):
                with self.subTest(weapon=key,maximum=maximum):
                    g,w,b=arena.Update033Tests().arena(key,2 if key=='weapon_thunder_shotgun' else 4)
                    w['fire_mode']=mode;w['durability']=50.2;g.perks['engineer']=2
                    w['modules']=[p.module(index='module_phase_approximator')]
                    b['max_ap']=b['ap']=12;b['enemies']=b['enemies'][:1]
                    enemy=b['enemies'][0];enemy.update(defense=15,resists={'kinetic':30,'electric':-20})
                    dp.remember_target(g,enemy)
                    estimate=dp.estimate(g,w);before=enemy['hp']
                    count=6 if key=='weapon_thunder_shotgun' else 5 if mode=='burst' else 1
                    for attack in range(estimate['attacks']):
                        hp=enemy['hp']
                        with patch.object(g.rng,'randrange',side_effect=[0,0 if maximum else 99]*count),patch.object(g.rng,'randint',return_value=2 if maximum else -2),patch.object(g.rng,'random',return_value=.99):
                            self.assertTrue(g.shoot(enemy['id']))
                        if attack==0:self.assertEqual(hp-enemy['hp'],estimate['maximum' if maximum else 'minimum'])
                    self.assertEqual(before-enemy['hp'],estimate['total_maximum' if maximum else 'total_minimum'])

    def test_shot_updates_reference_before_kill_and_survives_save_load(self):
        g,w,b=arena.Update033Tests().arena()
        enemy=b['enemies'][0];enemy.update(defense=27,resists={'kinetic':55})
        with patch.object(g.rng,'randrange',side_effect=[0,99]),patch.object(g.rng,'randint',return_value=0):
            self.assertTrue(g.shoot(enemy['id']))
        self.assertGreater(enemy['hp'],0)
        saved=copy.deepcopy(g.reputation_state['last_damage_target'])
        enemy['resists']['kinetic']=0
        self.assertEqual(g.reputation_state['last_damage_target'],saved)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);other=r.Game.load(path)
            self.assertEqual(dp.estimate(other,other.weapon)['target'],saved)
        second=b['enemies'][1];second['defense']=48
        # A missed shot still selects the enemy we fired at.
        with patch.object(g.rng,'randrange',return_value=99):
            self.assertTrue(g.shoot(second['id']))
        self.assertEqual(second['hp'],10000)
        self.assertEqual(dp.estimate(g,w)['target']['defense'],48)
        # Death of another enemy (e.g. reflection or stray pellets) cannot replace it.
        g._finish_enemy(enemy,w)
        self.assertEqual(dp.estimate(g,w)['target']['defense'],48)

    def test_rejected_shot_does_not_change_reference(self):
        g,w,b=arena.Update033Tests().arena()
        dp.remember_target(g,b['enemies'][0]);before=copy.deepcopy(dp.estimate(g,w)['target'])
        b['enemies'][1]['defense']=99;b['ap']=0
        self.assertFalse(g.shoot(b['enemies'][1]['id']))
        self.assertEqual(dp.estimate(g,w)['target'],before)

    def test_fallback_all_descriptions_and_no_game_mutation(self):
        from refinement_ui import description
        from inspection_ui import item_text
        from frontier_ui import player_text
        from terminal034 import snapshot
        g=r.Game(5)
        state=copy.deepcopy({k:v for k,v in vars(g).items() if k!='rng'});rng=g.rng.getstate()
        self.assertFalse(dp.estimate(g,g.weapon)['has_target'])
        for key,d in content.EQUIPMENT.items():
            if d['kind']!='weapon':continue
            w=p.equipment(key,level=d['min_level'])
            self.assertIn('Розрахункова шкода:',description(g,w))
            self.assertIn('Розрахункова шкода:',item_text(g,w))
        self.assertIn('Розрахункова шкода:',player_text(g))
        self.assertEqual(snapshot(g)['calculated_damage'],dp.format_value(dp.estimate(g,g.weapon)))
        self.assertEqual(state,{k:v for k,v in vars(g).items() if k!='rng'});self.assertEqual(rng,g.rng.getstate())

    def test_broken_weapon_insufficient_ap_and_current_ap_independence(self):
        g=r.Game(5);w=g.weapon;w['durability']=0
        e=dp.estimate(g,w);self.assertEqual((e['minimum'],e['maximum'],e['total_maximum']),(0,0,0))
        w['durability']=100;g.battle={'ap':0,'max_ap':g.shot_ap(w)-1}
        self.assertEqual(dp.estimate(g,w)['total_maximum'],0)
        g.battle['max_ap']=12;a=dp.estimate(g,w);g.battle['ap']=12
        self.assertEqual(a,dp.estimate(g,w))
