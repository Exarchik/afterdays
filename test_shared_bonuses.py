import copy
import unittest
from unittest.mock import patch
import game.model as r
import game.items as p
import module_rules as mr
import game.systems.combat as combat
import damage_preview


def add(item,**stats):
    item['modules'].append(dict(kind='module',stats=stats))


class SharedBonusesTests(unittest.TestCase):
    def game(self):
        g=r.Game(42)
        for item in g.equipped.values():
            if item:item['modules']=[];item['durability']=100
        return g

    def arena(self):
        g=self.game();g.start_battle();b=g.battle
        b.update(pos=[1,1],walls=[],ap=100,max_ap=100)
        enemy=b['enemies'][0]
        enemy.update(pos=[2,1],faction='bandits',human=False,hp=10000,max_hp=10000,defense=0,resists={},awake=True)
        b['enemies']=[enemy]
        g.bag.append(p.ammunition(g.weapon['ammo_type'],200))
        return g,enemy

    def test_every_offensive_bonus_transfers_and_local_bonuses_do_not(self):
        g=self.game();w=g.weapon
        values=dict(damage=10,damage_percent=15,attack=8,accuracy=7,crit=9,range=3,damage_electric=4,damage_piercing=5,ammo_save_percent=12)
        before=mr.aggregate(w)
        add(g.equipped['armor'],**values,local_damage_percent=100,strength=50,weight_percent=-50)
        actual=mr.aggregate(mr.effective_weapon(g,w))
        for key,value in values.items():self.assertEqual(actual[key],before.get(key,0)+value,key)
        for key in ('strength','weight_percent'):self.assertEqual(actual.get(key,0),before.get(key,0))
        self.assertEqual(mr.aggregate(w),before)

    def test_local_damage_is_applied_before_external_flat_bonus(self):
        g=self.game();w=g.weapon
        add(w,local_damage_percent=100)
        add(g.equipped['helmet'],damage=7,local_damage_percent=300)
        effective=mr.effective_weapon(g,w)
        self.assertEqual(mr.aggregate(effective)['damage'],mr.aggregate(w)['damage']*2+7)
        self.assertNotIn('local_damage_percent',mr.aggregate(effective))

    def test_weapon_passive_bonuses_and_holstered_exclusion(self):
        g=self.game();hp,cap,defense=g.max_hp,g.capacity,g.defense
        add(g.weapon,vitality=10,capacity=6,defense=4,defense_percent=20,regen=9,evasion=7,reflect_percent=8)
        self.assertEqual(g.max_hp,hp+10);self.assertEqual(g.capacity,cap+6)
        self.assertEqual(g.defense,round((defense+4)*1.2))
        for key,value in dict(regen=9,evasion=7,reflect_percent=8).items():self.assertEqual(g.protection_stat(key),value)
        other=p.equipment('weapon_ash_pistol');add(other,vitality=50,defense=100,regen=100)
        g.equipped['weapon2']=other
        self.assertEqual(g.max_hp,hp+10);self.assertEqual(g.protection_stat('regen'),9)
        g.hp=g.max_hp;g.switch()
        self.assertEqual(g.max_hp,hp+50);self.assertEqual(g.protection_stat('regen'),100)
        g.hp=g.max_hp;g.switch();self.assertEqual(g.hp,g.max_hp)

    def test_negative_bonuses_and_broken_items(self):
        g=self.game();base=mr.weapon_stats(g,g.weapon)
        add(g.equipped['armor'],accuracy=-12,attack=-4,range=-100)
        stats=mr.weapon_stats(g,g.weapon)
        self.assertEqual(stats['accuracy'],base['accuracy']-12);self.assertEqual(stats['attack'],base.get('attack',0)-4)
        self.assertEqual(stats['range'],1)
        g.equipped['armor']['durability']=0
        self.assertEqual(mr.weapon_stats(g,g.weapon),base)
        add(g.weapon,vitality=10,capacity=5,regen=20);hp=g.max_hp
        g.weapon['durability']=0
        self.assertEqual(g.max_hp,hp-10);self.assertEqual(g.protection_stat('regen'),0)
        self.assertEqual(g.protection_stat('capacity'),5)

    def test_shoot_uses_shared_damage_and_ammo_saving(self):
        g,e=self.arena()
        add(g.equipped['helmet'],damage=20,attack=10,ammo_save_percent=100,accuracy=100)
        weapon=g.weapon;before=g.count('ammo',weapon['ammo_type'])
        expected=sum(combat.projectile_components(mr.effective_weapon(g,weapon),g.level,e,0,False).values())
        hp=e['hp']
        with patch.object(g.rng,'randrange',return_value=50),patch.object(g.rng,'randint',return_value=0),patch.object(g.rng,'random',return_value=.5):
            self.assertTrue(g.shoot(e['id']))
        self.assertEqual(hp-e['hp'],expected)
        self.assertEqual(g.count('ammo',weapon['ammo_type']),before)

    def test_accuracy_and_range_use_shared_bonuses(self):
        g,e=self.arena();w=g.weapon;reach=mr.weapon_stats(g,w)['range']
        e['pos']=[1+reach+1,1];g.battle['w']=max(g.battle['w'],e['pos'][0]+1)
        self.assertFalse(g.shot_info(e)[0])
        add(g.equipped['armor'],range=2,accuracy=20)
        self.assertTrue(g.shot_info(e)[0])

    def test_preview_matches_combat_formula_without_mutation_or_rng(self):
        g=self.game();add(g.equipped['helmet'],damage=10,damage_percent=20,attack=7,damage_electric=8)
        target=dict(defense=5,resists={'electric':25})
        before=copy.deepcopy(g.equipped);rng=g.rng.getstate()
        expected=[sum(combat.projectile_components(mr.effective_weapon(g,g.weapon),g.level,target,v,c).values()) for v in range(-2,3) for c in (False,True)]
        self.assertEqual(damage_preview.attack_range(g,g.weapon,target),(min(expected),max(expected)))
        damage_preview.estimate(g,g.weapon)
        self.assertEqual(g.equipped,before);self.assertEqual(g.rng.getstate(),rng)

    def test_preview_other_weapon_does_not_add_active_weapon_bonuses(self):
        g=self.game();other=p.equipment('weapon_ash_pistol')
        add(g.weapon,damage=100);add(g.equipped['armor'],damage=3)
        self.assertEqual(mr.aggregate(mr.effective_weapon(g,other))['damage'],mr.aggregate(other)['damage']+3)

    def test_negative_curve_preserves_sign_and_zero(self):
        definition=dict(target='protection',rarity_stats={'accuracy':[-3,0,1,2,3]})
        self.assertLess(mr.definition_stats(definition,0,10)['accuracy'],0)
        self.assertEqual(mr.definition_stats(definition,1,10)['accuracy'],0)

    def test_weapon_regeneration_and_reflection_in_gameplay(self):
        g,e=self.arena();add(g.weapon,regen=10,reflect_percent=100)
        g.hp=1;g.battle['enemies']=[];g.victory()
        self.assertEqual(g.hp,11)
        g,e=self.arena();add(g.weapon,reflect_percent=100)
        e.update(damage=10,attack=0,equipment={})
        hp,enemy_hp=g.hp,e['hp']
        with patch.object(g.rng,'randrange',return_value=99),patch.object(g.rng,'randint',return_value=0),patch.object(g.rng,'random',return_value=0):
            g.faction_attack(e,dict(pos=g.battle['pos'],defense=g.defense),True)
        self.assertEqual(g.hp,hp);self.assertLess(e['hp'],enemy_hp)

    def test_full_ap_preview_with_armor_bonuses_all_fire_modes(self):
        from test_update033 import Update033Tests
        for key,mode in [('weapon_ash_pistol','single'),('weapon_rust_assault','burst'),('weapon_thunder_shotgun','single'),('weapon_horizon_sniper','aimed')]:
            g,w,b=Update033Tests().arena(key,4 if mode=='aimed' else 2)
            b['enemies']=b['enemies'][:1];e=b['enemies'][0]
            w['fire_mode']=mode;w['durability']=50.2
            add(g.equipped['armor'],damage=7,damage_percent=13,damage_electric=6,accuracy=10)
            add(g.equipped['helmet'],attack=9,damage_piercing=4)
            g.add_radiation(50);damage_preview.remember_target(g,e)
            expected=damage_preview.estimate(g,w);hp=e['hp']
            count=6 if key=='weapon_thunder_shotgun' else 5 if mode=='burst' else 1
            for _ in range(expected['attacks']):
                with patch.object(g.rng,'randrange',side_effect=[0,99]*count),patch.object(g.rng,'randint',return_value=-2),patch.object(g.rng,'random',return_value=.99):
                    self.assertTrue(g.shoot(e['id']))
            self.assertEqual(hp-e['hp'],expected['total_minimum'],key)


if __name__=='__main__':unittest.main()
