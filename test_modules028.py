import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import afterdays as r
import progression as p
import adventure,balance,content,sprites,module_rules as mr
from refinement_ui import description

class NewModulesTests(unittest.TestCase):
    # Готує або імітує операцію «mod» для перевірок NewModulesTests.
    def mod(self,name,tier=0,level=1):return p.module(tier,index='module_'+name,level=level)
    def battle(self,seed=47):
        """Готує або імітує операцію «battle» для перевірок NewModulesTests."""
        g=r.Game(seed);g.start_battle();b=g.battle;b['pos']=[1,1];b['walls']=[];b['enemies']=b['enemies'][:1]
        e=b['enemies'][0];e.update(pos=[2,1],hp=1000,max_hp=1000,damage=12,defense=0,attack=10,resists={},speed=0,range=1,kind=0,type_id='monster_rodent')
        # Retain the canonical identifier, independent of its spelling in catalogs.
        e['type_id']=content.MONSTER_IDS[0]
        return g,b,e
    def test_all_rarity_curves_and_fixed_percent_levels(self):
        """Перевіряє сценарій «all rarity curves and fixed percent levels» та очікувані результати."""
        self.assertEqual(len(content.MODULE_DATA),29)
        for ident in content.MODULE_IDS[20:]:
            definition=content.MODULE_DATA[ident]
            for tier in range(5):
                mod=p.module(tier,index=ident)
                for key,curve in definition['rarity_stats'].items():self.assertEqual(mod['stats'][key],curve[tier])
                for key,value in definition.get('fixed_penalties',{}).items():self.assertEqual(mod['stats'][key],value)
                higher=p.module(tier,index=ident,level=10)
                for key in mr.PERCENT_STATS&definition['rarity_stats'].keys():self.assertEqual(mod['stats'][key],higher['stats'][key])
                for tradeoff in (False,True):
                    rolled=mr.module_stats(ident,tier,10,tradeoff)
                    if definition['rarity_stats'].get('weight_percent',[0]*5)[tier]<0:self.assertLess(rolled['weight_percent'],0)
    def test_weight_in_inventory_and_no_base_mutation(self):
        """Перевіряє сценарій «weight in inventory and no base mutation» та очікувані результати."""
        g=r.Game(4);w=g.weapon;w['rarity']=4;w['slots']=5
        base=w['weight'];before=g.weight
        m=self.mod('carbon_grip',4);g.bag.append(m)
        self.assertTrue(g.install(w['id'],m['id']))
        self.assertAlmostEqual(p.item_weight(w),(base+.1)*.75)
        self.assertLess(g.weight,before);self.assertEqual(w['weight'],base)
        w['modules']=[self.mod('carbon_grip',4) for _ in range(5)]
        self.assertAlmostEqual(p.item_weight(w),(base+.5)*.1)
        armor=p.equipment('armor_plated_jacket');armor['modules']=[self.mod('lead_fibers')]
        self.assertAlmostEqual(p.item_weight(armor),armor['weight']+1.5)
        self.assertEqual(p.stats(armor)['defense'],armor['stats']['defense']+3)
    def test_weight_removal_cannot_overload(self):
        """Перевіряє сценарій «weight removal cannot overload» та очікувані результати."""
        g=r.Game(5);armor=g.equipped['armor'];armor['rarity']=4
        mod=self.mod('polyfiber',4);g.bag.append(mod);self.assertTrue(g.install(armor['id'],mod['id']))
        heavy=p.equipment('weapon_ash_pistol');heavy['weight']=g.capacity-g.weight;g.bag.append(heavy)
        self.assertFalse(g.uninstall(armor['id'],mod['id']))
        self.assertTrue(any(m['id']==mod['id'] for m in g.equipped['armor']['modules']))
    def test_ammo_saved_even_on_miss_and_no_free_shot_without_ammo(self):
        """Перевіряє сценарій «ammo saved even on miss and no free shot without ammo» та очікувані результати."""
        g,b,e=self.battle();w=g.weapon;w['modules']=[self.mod('electronic_compensator',4)]
        ammo=g.count('ammo','pistol');ap=b['ap']
        with patch.object(g.rng,'random',return_value=0),patch.object(g.rng,'randrange',return_value=99):
            self.assertTrue(g.shoot(e['id']))
        self.assertEqual(g.count('ammo','pistol'),ammo);self.assertEqual(b['ap'],ap-w['ap']);self.assertEqual(e['hp'],1000)
        with patch.object(g.rng,'random',return_value=.99),patch.object(g.rng,'randrange',return_value=99):self.assertTrue(g.shoot(e['id']))
        self.assertEqual(g.count('ammo','pistol'),ammo-1)
        g.consume('ammo',g.count('ammo','pistol'),'pistol');ap=b['ap']
        self.assertFalse(g.shoot(e['id']));self.assertEqual(b['ap'],ap)
    def test_typed_damage_uses_individual_resistances(self):
        """Перевіряє сценарій «typed damage uses individual resistances» та очікувані результати."""
        g,b,e=self.battle();w=g.weapon
        w['modules']=[self.mod('phase_approximator',2),self.mod('gauss_accelerator',2)]
        e['resists']={'kinetic':0,'electric':-50,'piercing':50}
        parts=mr.shot_components(w,g.level,0,'kinetic');self.assertEqual(parts['electric'],5);self.assertEqual(parts['piercing'],5)
        attack=p.stats(w)['attack'];expected=sum(max(1,round(balance.damage(v*1.6,attack,0)*(1-e['resists'].get(k,0)/100))) for k,v in parts.items())
        with patch.object(g.rng,'randrange',return_value=0),patch.object(g.rng,'randint',return_value=0):self.assertTrue(g.shoot(e['id']))
        self.assertEqual(e['hp'],1000-expected)
        w=p.equipment('weapon_spark_ion',level=5);w['modules']=[self.mod('phase_approximator')]
        parts=mr.shot_components(w,5,0,'electric');self.assertEqual(set(parts),{'electric'})
        self.assertEqual(parts['electric'],mr.shot_damage(w,5)+2)
    def test_reflection_prevents_damage_and_wear(self):
        """Перевіряє сценарій «reflection prevents damage and wear» та очікувані результати."""
        g,b,e=self.battle();g.equipped['armor']['modules']=[self.mod('quantum_mirror',4)]
        hp=g.hp;dur=g.equipped['armor']['durability'];damage=balance.damage(e['damage'],e['attack'],g.defense)
        with patch.object(g.rng,'random',return_value=0),patch.object(g.rng,'randrange',return_value=99),patch.object(g.rng,'randint',return_value=0):g.end_turn()
        self.assertEqual(g.hp,hp);self.assertEqual(e['hp'],1000-damage);self.assertEqual(g.equipped['armor']['durability'],dur)
        with patch.object(g.rng,'random',return_value=.99),patch.object(g.rng,'randrange',return_value=99),patch.object(g.rng,'randint',return_value=0):g.end_turn()
        self.assertLess(g.hp,hp)
    def test_reflection_kill_rewards_once_without_weapon_test(self):
        """Перевіряє сценарій «reflection kill rewards once without weapon test» та очікувані результати."""
        g,b,e=self.battle();g.equipped['armor']['modules']=[self.mod('quantum_mirror',4)];e['hp']=1
        with patch.object(g.rng,'random',return_value=0),patch.object(g.rng,'randrange',return_value=99),patch.object(g.rng,'randint',return_value=0),patch.object(g,'monster_killed',wraps=g.monster_killed) as killed:
            xp=g.xp;g.end_turn();self.assertGreater(g.xp,xp);self.assertEqual(killed.call_count,1);self.assertIsNone(killed.call_args.args[2])
        self.assertEqual(len(b['corpses']),1);self.assertEqual(len(b['kills']),1);self.assertIsNone(g.battle)
    def test_reflection_does_not_skip_next_attacker(self):
        """Перевіряє сценарій «reflection does not skip next attacker» та очікувані результати."""
        g,b,e=self.battle();g.equipped['armor']['modules']=[self.mod('quantum_mirror',4)]
        other=copy.deepcopy(e);other.update(id='second',pos=[1,2]);b['enemies'].append(other);e['hp']=1
        with patch.object(g.rng,'random',return_value=0),patch.object(g.rng,'randrange',return_value=99),patch.object(g.rng,'randint',return_value=0):g.end_turn()
        self.assertNotIn(e,b['enemies']);self.assertLess(other['hp'],1000)
    def test_save_and_descriptions(self):
        """Перевіряє сценарій «save and descriptions» та очікувані результати."""
        g=r.Game(9);g.weapon.update(rarity=4,slots=5)
        g.weapon['modules']=[self.mod('tactical_grip'),self.mod('phase_approximator'),self.mod('electronic_compensator')]
        text=description(g,g.weapon)
        for label in ('Електрична шкода','Збереження набою','Вага'):self.assertIn(label,text)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'s.json';g.save(path);h=r.Game.load(path);self.assertEqual(h.equipped,g.equipped);self.assertEqual(h.weight,g.weight)
    def test_all_new_sprites_and_npc_bindings(self):
        """Перевіряє сценарій «all new sprites and npc bindings» та очікувані результати."""
        root=Path(__file__).parent/'assets'
        for ident in content.MODULE_IDS[20:]:
            entry=sprites.MANIFEST[ident];self.assertEqual(entry['sheet'],'expansion028')
            for size in sprites.SIZES:
                with Image.open(root/f'expansion028_{size}.png') as im:
                    n=entry['index'];tile=im.crop((n%6*size,n//6*size,n%6*size+size,n//6*size+size))
                    self.assertIsNotNone(tile.getchannel('A').getbbox())
        for _,npc,_ in adventure.SITES:self.assertIn(sprites.npc_key(npc),sprites.MANIFEST)
        names=['Водолаз','Комірник','Провідник','Енергетик','Майстер','Слюсар','Міняйло','Інтендант','Дозорний']
        self.assertEqual(len({sprites.npc_key(n) for n in names}),9)
        for width in (48,56,64,80,96,128):
            with Image.open(root/f'inventory_expansion028_{width}.png') as im:self.assertEqual(im.size,(16*width,144))

if __name__=='__main__':unittest.main()
