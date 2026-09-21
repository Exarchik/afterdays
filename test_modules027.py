import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import progression as p
import module_rules as mr
import content,balance
from refinement_ui import description

class ModuleBalanceTests(unittest.TestCase):
    def test_rarity_arrays_and_fixed_penalties(self):
        expected={0:('damage',[2,3,5,7,9]),1:('range',[1,2,3,4,5]),
          2:('accuracy',[3,6,8,10,12]),4:('damage',[3,6,9,12,15]),
          5:('accuracy',[4,8,12,16,20]),6:('attack',[1,2,3,4,5]),
          7:('crit',[2,4,7,10,12]),9:('damage_percent',[5,7,9,11,15]),
          10:('accuracy',[4,8,12,16,20]),11:('attack',[2,3,4,5,7]),
          13:('vitality',[3,5,8,10,15]),15:('evasion',[2,4,6,8,10]),
          17:('vitality',[5,10,15,20,25])}
        for idx,(key,values) in expected.items():
            for tier,value in enumerate(values):
                self.assertEqual(p.module(tier,index=idx)['stats'][key],value,(idx,tier))
        for tier in range(5):
            self.assertEqual(p.module(tier,index=8)['stats'],{'range':[1,1,1,2,2][tier],'attack':[1,1,2,2,3][tier]})
        for ident,data in content.MODULE_DATA.items():
            for tier in range(5):
                for lvl in (1,10):
                    for tradeoff in (False,True):
                        stats=mr.module_stats(ident,tier,lvl,tradeoff)
                        for k,v in data.get('fixed_penalties',{}).items():self.assertLessEqual(stats[k],v)

    def test_loose_modules_do_not_count_as_damaged_goods(self):
        g=r.Game(2)
        for idx in (4,10,12,19):
            mod=p.module(0,index=idx)
            self.assertEqual(mr.condition(mod),100)
            self.assertTrue(g.buys_kind(mod,0))

    def test_scaling_and_tradeoff(self):
        self.assertEqual(p.module(2,index=0,level=5)['stats']['damage'],6)
        self.assertEqual(p.module(2,index=9,level=15)['stats']['damage_percent'],9)
        self.assertEqual(p.module(4,index=11,level=15)['stats'],{'attack':7,'range':-2})
        stats=mr.module_stats('module_burst_core',2,1,True)
        self.assertEqual(stats,{'damage':15,'accuracy':-12,'max_condition_percent':-30})

    def test_compatibility_all_gear_categories(self):
        for name,idx in [('weapon_ash_pistol',0),('armor_plated_jacket',3),('helmet_seeker',3)]:
            gear=p.equipment(name,2,level=5)
            self.assertTrue(r.compatible(gear,p.module(2,index=idx,level=5)))
            self.assertTrue(r.compatible(gear,p.module(0,index=idx,level=1)))
            self.assertFalse(r.compatible(gear,p.module(3,index=idx,level=5)))
            self.assertFalse(r.compatible(gear,p.module(2,index=idx,level=6)))
            self.assertFalse(r.compatible(gear,p.module(0,index=3 if idx==0 else 0)))

    def test_install_replace_reject_without_mutation(self):
        g=r.Game(42);g.xp=p.xp_for_level(10)
        good=p.module(0,index=0);rare=p.module(1,index=0);high=p.module(0,index=0,level=2)
        g.bag.extend([good,rare,high]);self.assertTrue(g.install(g.weapon['id'],good['id']))
        before=copy.deepcopy((g.bag,g.equipped))
        for mod in (rare,high):
            self.assertFalse(g.install(g.weapon['id'],mod['id']))
            self.assertFalse(g.put_module(g.weapon['id'],mod['id'],0))
        self.assertEqual(before,(g.bag,g.equipped))

    def test_cap_removal_repair_and_repair_kit(self):
        g=r.Game(13);g.money=10000
        gear=g.weapon;mod=p.module(0,index=4);g.bag.append(mod)
        self.assertTrue(g.install(gear['id'],mod['id']))
        self.assertEqual(gear['durability'],70);self.assertEqual(mr.max_condition(gear),70)
        self.assertEqual(g.repair_cost(gear),0)
        gear['durability']=40;g.bag.append(p.supply('repairkit',2))
        self.assertTrue(g.repair_with_kit(gear['id']));self.assertEqual(gear['durability'],70)
        self.assertFalse(g.repair_with_kit(gear['id']));self.assertEqual(g.count('repairkit'),1)
        gear['durability']=10
        self.assertTrue(g.repair(gear['id'],25));self.assertEqual(gear['durability'],25)
        self.assertTrue(g.repair(gear['id'],50));self.assertEqual(gear['durability'],50)
        self.assertTrue(g.repair(gear['id'],100));self.assertEqual(gear['durability'],70)
        self.assertTrue(g.uninstall(gear['id'],mod['id']))
        self.assertEqual(mr.max_condition(gear),100);self.assertEqual(gear['durability'],70)

    def test_stacked_caps_and_armor_defense_penalty(self):
        gear=p.equipment('armor_plated_jacket',4)
        gear['modules']=[p.module(0,index=19) for _ in range(5)]
        self.assertEqual(mr.max_condition(gear),1)
        self.assertGreaterEqual(p.stats(gear)['defense'],1)
        g=r.Game(11);armor=g.equipped['armor'];helmet=g.equipped['helmet']
        base=g.defense
        armor['modules']=[p.module(0,index=17)];helmet['modules']=[p.module(0,index=17)]
        self.assertEqual(g.defense,round(base*.6))
        self.assertEqual(g.max_hp,35)

    def test_percentage_damage_in_actual_combat(self):
        g=r.Game(15);g.xp=p.xp_for_level(5)
        g.equipped['weapon1']=p.equipment('weapon_ash_pistol',4,level=5);w=g.weapon
        w['modules']=[p.module(4,index=9),p.module(0,index=5)]
        self.assertAlmostEqual(mr.damage_factor(w),1.05)
        g.start_battle();b=g.battle;b['walls']=[];b['pos']=[1,1];b['enemies']=b['enemies'][:1]
        e=b['enemies'][0];e.update(pos=[2,1],hp=1000,max_hp=1000,defense=0,resists={})
        raw=round((w['stats']['damage']+8)*1.05)
        self.assertEqual(mr.shot_damage(w,5),raw)
        with patch.object(g.rng,'randrange',return_value=0),patch.object(g.rng,'randint',return_value=0):
            self.assertTrue(g.shoot(e['id']))
        self.assertEqual(e['hp'],1000-balance.damage(raw*1.6,w['stats']['attack'],0))

    def test_migration_preserves_items_rng_and_roundtrip(self):
        g=r.Game(17);gear=p.equipment('weapon_ash_pistol',1,level=3)
        old=p.module(0,index=4,level=3);old.pop('module_balance_version');old['stats']={'damage':4}
        illegal=p.module(4,index=9,level=6);illegal.pop('module_balance_version')
        gear['modules']=[old,illegal];g.equipped['weapon1']=gear
        state=g.rng.getstate();ids={i['id'] for i in g.bag}
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
            self.assertEqual(h.rng.getstate(),state)
            self.assertEqual(h.weapon['modules'][0]['stats'],mr.module_stats(old['type_id'],0,3))
            self.assertEqual(h.weapon['durability'],70)
            self.assertEqual({i['id'] for i in h.bag},ids|{illegal['id']})
            h.save(path);j=r.Game.load(path)
            self.assertEqual(h.bag,j.bag);self.assertEqual(h.equipped,j.equipped)

    def test_generated_loot_is_compatible(self):
        g=r.Game(18);g.xp=p.xp_for_level(10)
        for _ in range(250):
            for item in (g.roll_item(),g.reward_item(level=10)):
                for mod in item.get('modules',[]):self.assertTrue(r.compatible(item,mod))
                if 'durability' in item:self.assertLessEqual(mr.condition(item),mr.max_condition(item))

    def test_descriptions_expose_caps_percentages_and_restrictions(self):
        g=r.Game(9);w=p.equipment('weapon_ash_pistol',2)
        w['modules']=[p.module(0,index=4),p.module(0,index=9)]
        text=description(g,w)
        self.assertIn('Максимальний стан\t70%',text)
        self.assertIn('Сумарна шкода\t5%',text)
        self.assertIn('рівень і рідкість',description(g,w['modules'][0]))
        self.assertIn('[-]',description(g,w['modules'][0]))

if __name__=='__main__':unittest.main()
