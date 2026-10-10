import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import game.model as r
import event_catalog as ec
import event_runtime as er
import test_survival040 as survival_tests


class EventBuffTests(unittest.TestCase):
    def game(self):return survival_tests.SurvivalTests().game()
    def apply(self,g,kind,amount=1,**extra):return er.apply(g,dict(kind=kind,amount=amount,**extra),dict(title='Тест'))
    def catalog(self,effect):
        doc=copy.deepcopy(ec.DOCUMENT);doc['events']=doc['events'][:1]
        doc['events'][0]['choices'][0]['outcomes']=[dict(chance=1,effects=[effect])]
        return doc

    def test_new_effects_and_duration_validation(self):
        for kind in ('wear_armor','radiation','radiation_heal','satiety_gain','satiety_loss','buff_regen','buff_satiety','buff_stealth'):
            effect=dict(kind=kind,amount=10)
            if kind in ec.TIMED_EFFECTS:effect['duration']=12
            self.assertEqual(ec.validate(self.catalog(effect)),[])
            self.assertIn(ec.EFFECTS[kind][0],ec.describe(effect))
        for duration in (None,0,-1,1.5,True,1000001):
            self.assertTrue(ec.validate(self.catalog(dict(kind='buff_regen',amount=10,duration=duration))))

    def test_damage_radiation_cure_and_satiety(self):
        g=self.game();armor=g.equipped['armor'];before=armor['durability']
        self.apply(g,'wear_armor',12);self.assertLess(armor['durability'],before)
        self.apply(g,'radiation',55);self.assertTrue(g.radiation_sickness);hp=g.hp
        self.apply(g,'radiation_heal',10);self.assertEqual(g.radiation_injury,45);self.assertFalse(g.radiation_sickness);self.assertEqual(g.hp,hp)
        self.apply(g,'satiety_loss',22);self.assertEqual(g.hunger,-2);self.assertTrue(g.starving)
        self.apply(g,'satiety_gain',10);self.assertEqual(g.hunger,8);self.assertFalse(g.starving)
        self.apply(g,'satiety_gain',100);self.assertEqual(g.hunger,20)
        g.equipped['armor']=None;self.apply(g,'wear_armor',10)

    def test_gluttony_holds_twenty_for_exact_number_of_steps(self):
        g=self.game();g.survival['hunger']=-5;food=g.count('food')
        self.apply(g,'buff_satiety',duration=2);self.assertEqual(g.hunger,20)
        self.apply(g,'satiety_loss',100);self.assertEqual(g.hunger,20)
        for _ in range(2):self.assertTrue(g.step(1,0));self.assertEqual(g.hunger,20)
        self.assertFalse(g.buff_active('buff_satiety'));g.step(1,0);self.assertEqual(g.hunger,19)
        self.assertEqual(g.count('food'),food)

    def test_regen_bonus_duration_and_refresh(self):
        g=self.game();g.hp=1;base=g.protection_stat('regen')
        self.apply(g,'buff_regen',30,duration=2);self.assertEqual(g.protection_stat('regen'),base+30)
        self.apply(g,'buff_regen',60,duration=2);self.assertEqual(g.protection_stat('regen'),base+60)
        g.step(1,0);self.assertEqual(g.hp,3)
        g.step(1,0);self.assertEqual(g.hp,5);self.assertEqual(g.protection_stat('regen'),base)
        g.step(1,0);self.assertEqual(g.hp,5)

    def test_stealth_reduces_only_random_attack_chance_on_last_step(self):
        g=self.game();g._guided_trip=False;g.last_event_turn=1000;g.last_traveler_turn=1000
        self.apply(g,'buff_stealth',duration=1)
        self.assertAlmostEqual(g.encounter_multiplier,1/3)
        with patch.object(g.rng,'random',return_value=.03),patch.object(g,'start_battle') as attack:
            g.step(1,0);attack.assert_not_called()
            g.step(1,0);attack.assert_called_once()
        self.assertEqual(g.encounter_multiplier,1)

    def test_failed_moves_and_battle_moves_dont_consume_duration(self):
        g=self.game();self.apply(g,'buff_regen',30,duration=2)
        g.world[g.y][g.x+1]='water';self.assertFalse(g.step(1,0));self.assertEqual(g.buffs['buff_regen']['remaining'],2)
        g.battle={'pos':[1,1]}
        with patch.object(g,'battle_move',return_value=True):self.assertTrue(g.step(1,0))
        self.assertEqual(g.buffs['buff_regen']['remaining'],2)

    def test_save_load_and_legacy_survival_without_buffs(self):
        g=self.game();self.apply(g,'buff_regen',30,duration=8);self.apply(g,'buff_stealth',duration=5);g.step(1,0)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);other=r.Game.load(path)
            self.assertEqual(other.buffs,g.buffs);self.assertEqual(other.protection_stat('regen'),g.protection_stat('regen'))
            data=json.loads(path.read_text(encoding='utf-8'));del data['reputation_state']['survival040']['buffs']
            path.write_text(json.dumps(data),encoding='utf-8');old=r.Game.load(path);self.assertEqual(old.buffs,{})

    def test_lethal_effect_stops_event_and_death_removes_buffs(self):
        for kind,amount in [('radiation',100),('satiety_loss',40)]:
            g=self.game();self.apply(g,'buff_stealth',duration=10)
            doc=self.catalog(dict(kind=kind,amount=amount));event=doc['events'][0]
            event['choices'][0]['outcomes'][0]['effects'].append(dict(kind='money',amount=999))
            g.road_event=dict(kind=event['id'],definition=event);money=g.money
            self.assertTrue(er.resolve(g,event['choices'][0]['id']))
            self.assertLess(g.money,money);self.assertEqual(g.buffs,{})


if __name__=='__main__':unittest.main()
