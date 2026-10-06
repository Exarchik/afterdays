import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import progression as p
import damage_preview
import combat033
import test_update033 as arena


class SurvivalTests(unittest.TestCase):
    def game(self):
        g=r.Game(5);g._guided_trip=True;g.radiation={};g.special_sites=[];g.reputation_state['border_open']=True
        g.world=[['road']*112 for _ in range(32)];g.x,g.y=10,10
        return g

    def test_radiation_steps_cap_and_threshold(self):
        g=self.game();g.radiation={f'{x},10':4 for x in range(11,23)}
        base=g.healthy_max_hp
        for n in range(1,11):
            self.assertTrue(g.step(1,0));self.assertEqual(g.radiation_injury,n*5)
            self.assertEqual(g.max_hp,math.ceil(base*(100-n*5)/100));self.assertLessEqual(g.hp,g.max_hp)
            self.assertEqual(g.radiation_sickness,n>=10)
        self.assertEqual(g.outgoing_damage_multiplier,.7)

    def test_rad_cures_fifty_points_without_healing_wounds(self):
        g=self.game();g.add_radiation(75);g.hp=2;p.add_to(g.bag,p.supply('rad',3))
        self.assertTrue(g.use('rad'));self.assertEqual(g.radiation_injury,25)
        self.assertEqual(g.hp,2);self.assertFalse(g.radiation_sickness);self.assertEqual(g.rad_turns,0)
        self.assertTrue(g.use('rad'));self.assertEqual(g.radiation_injury,0)
        self.assertFalse(g.use('rad'));self.assertEqual(g.count('rad'),1)

    def test_med_and_event_heal_cannot_remove_radiation(self):
        import event_runtime
        g=self.game();g.add_radiation(50);g.hp=1
        self.assertTrue(g.use('med'));self.assertLessEqual(g.hp,g.max_hp)
        event_runtime.apply(g,dict(kind='heal',amount=999),dict(title='heal'))
        self.assertEqual(g.hp,g.max_hp);self.assertEqual(g.radiation_injury,50)

    def test_hunger_twenty_steps_autoeat_and_ten_satiety(self):
        g=self.game();before=g.count('food');g.hp=5
        for _ in range(19):g.step(1,0)
        self.assertEqual(g.hunger,1);self.assertEqual(g.count('food'),before)
        g.step(1,0);self.assertEqual(g.hunger,10);self.assertEqual(g.count('food'),before-1)
        self.assertEqual(g.hp,5)

    def test_starvation_ap_threshold_and_death(self):
        g=self.game();g.bag=[i for i in g.bag if i['kind']!='food'];ap=g.max_ap
        for _ in range(20):g.step(1,0)
        self.assertEqual(g.hunger,0);self.assertFalse(g.starving);self.assertEqual(g.max_ap,ap)
        g.step(1,0);self.assertTrue(g.starving);self.assertEqual(g.max_ap,ap-2)
        for _ in range(18):g.step(1,0)
        self.assertEqual(g.hunger,-19)
        with patch.object(g,'defeat',wraps=g.defeat) as defeat:
            g.step(1,0);defeat.assert_called_once()
        self.assertEqual(g.hunger,20);self.assertEqual([g.x,g.y],g.cities[0])

    def test_food_choice_stacks_manual_full_hp_and_ap(self):
        g=self.game();g.survival['hunger']=-1
        good=p.supply('food');good.update(type_id='food_deluxe',satiety=20,value=100)
        p.add_to(g.bag,good);self.assertEqual(len([i for i in g.bag if i['kind']=='food']),2)
        self.assertTrue(g.use('food'));self.assertEqual(g.hunger,9)
        self.assertFalse(g.starving);self.assertIn(good,g.bag)
        g.battle={'ap':1,'max_ap':g.max_ap,'pos':[1,1]}
        self.assertFalse(g.use('food'));self.assertEqual(g.hunger,9)
        g.battle['ap']=2;self.assertTrue(g.use('food'));self.assertEqual(g.battle['ap'],0)

    def test_sleep_refuses_any_radiation_or_negative_hunger(self):
        g=self.game();g.x,g.y=g.cities[0];g.hp=1;g.money=100
        g.add_radiation(5);before=(g.money,g.turn,g.hp)
        self.assertFalse(g.rest());self.assertEqual((g.money,g.turn,g.hp),before)
        g.survival['radiation']=0;g.survival['hunger']=-1
        self.assertFalse(g.rest());self.assertEqual((g.money,g.turn,g.hp),before)
        g.survival['hunger']=0;self.assertTrue(g.rest())

    def test_regen_distributed_over_thirty_steps(self):
        for regen in (1,10,30,45):
            g=self.game();g.perks['hardy']=30;g.hp=1;g.bag.append(p.supply('food',20))
            with patch.object(g,'protection_stat',side_effect=lambda key:regen if key=='regen' else 0):
                for n in range(1,31):
                    g.step(1,0);self.assertEqual(g.hp,1+n*regen//30)
            self.assertEqual(g.survival['regen_remainder'],0)

    def test_one_survival_tick_per_cell_including_diagonal(self):
        g=self.game();g.world_distance_remainder=.9;g.radiation['11,11']=4
        with patch.object(g,'protection_stat',return_value=0):g.step(1,1)
        self.assertEqual(g.turn,2);self.assertEqual(g.hunger,19);self.assertEqual(g.radiation_injury,5)
        state=copy.deepcopy(g.survival);g.world[11][12]='water'
        self.assertFalse(g.step(1,0));self.assertEqual(g.survival,state)

    def test_regen_not_on_battle_round_but_after_combat_once(self):
        g,w,b=arena.Update033Tests().arena();g.hp=1
        b['enemies'][0].update(pos=[15,15],speed=0,range=0)
        b['enemies']=b['enemies'][:1]
        original=g.protection_stat
        with patch.object(g,'protection_stat',side_effect=lambda key:10 if key=='regen' else original(key)):
            g.end_turn();self.assertEqual(g.hp,1)
            b['enemies']=[];g.victory();self.assertEqual(g.hp,11)
            g.victory();self.assertEqual(g.hp,11)

    def test_dungeon_regeneration_not_repeated_on_exit(self):
        g,w,b=arena.Update033Tests().arena();g.hp=1;b.update(dungeon=True,cleared=False,enemies=[],exit=b['pos'][:])
        original=g.protection_stat
        with patch.object(g,'protection_stat',side_effect=lambda key:10 if key=='regen' else original(key)):
            g.victory();self.assertEqual(g.hp,11);g.victory();self.assertEqual(g.hp,11)
            g.flee();self.assertEqual(g.hp,11)

    def test_sickness_damage_matches_preview_for_every_category(self):
        for weapon,mode in [('weapon_ash_pistol','single'),('weapon_rust_assault','burst'),('weapon_thunder_shotgun','single'),('weapon_horizon_sniper','aimed')]:
            g,w,b=arena.Update033Tests().arena(weapon,2 if weapon=='weapon_thunder_shotgun' else 4);w['fire_mode']=mode
            g.add_radiation(50);enemy=b['enemies'][0];damage_preview.remember_target(g,enemy)
            expected=damage_preview.estimate(g,w)['minimum'];hp=enemy['hp']
            count=6 if combat033.category(w)=='shotgun' else 5 if mode=='burst' else 1
            with patch.object(g.rng,'randrange',side_effect=[0,99]*count),patch.object(g.rng,'randint',return_value=-2),patch.object(g.rng,'random',return_value=.99):self.assertTrue(g.shoot(enemy['id']))
            self.assertEqual(hp-enemy['hp'],expected)

    def test_received_combat_damage_increases_and_regen_stays_capped(self):
        g,w,b=arena.Update033Tests().arena();g.perks['hardy']=20;g.hp=g.healthy_max_hp;g.add_radiation(50)
        self.assertEqual(g.incoming_combat_damage(10),13)
        self.assertEqual(g.regenerate(999),0)
        b['enemies']=b['enemies'][:1];b['enemies'][0].update(pos=[b['pos'][0]+1,b['pos'][1]],speed=0,range=20,damage=10)
        original=g.hp
        with patch('adventure.balance.damage',return_value=10),patch.object(g.rng,'randrange',return_value=99),patch.object(g,'protection_stat',return_value=0):g.end_turn()
        self.assertEqual(original-g.hp,13)

    def test_save_load_remainder_and_legacy_defaults(self):
        g=self.game();g.survival.update(radiation=55,hunger=-4,regen_remainder=20);g.hp=2
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);loaded=r.Game.load(path)
            self.assertEqual(loaded.survival,g.survival);self.assertEqual(loaded.hp,2)
            data=json.loads(path.read_text(encoding='utf-8'));del data['reputation_state']['survival040'];data['rad_turns']=8
            path.write_text(json.dumps(data),encoding='utf-8');old=r.Game.load(path)
            self.assertEqual(old.hunger,20);self.assertEqual(old.radiation_injury,0);self.assertEqual(old.rad_turns,0)

    def test_storm_and_static_radiation_dont_double_count(self):
        g=self.game();g._guided_trip=False;g.radiation[f'{g.x},{g.y}']=4
        with patch.object(g,'advance_storm'),patch.object(g,'storm_cells',return_value=[(g.x,g.y)]):g._world_time_tick()
        self.assertEqual(g.radiation_injury,5)

    def test_radiation_death_uses_existing_defeat(self):
        g=self.game();g.survival['radiation']=95;g.hp=1
        with patch.object(g,'defeat',wraps=g.defeat) as defeat:self.assertFalse(g.add_radiation());defeat.assert_called_once()
        self.assertEqual(g.hp,max(1,math.ceil(g.max_hp*.25)));self.assertEqual(g.radiation_injury,0)


if __name__=='__main__':unittest.main()
