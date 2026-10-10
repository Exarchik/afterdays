import copy
import random
import unittest
from unittest.mock import patch
import game.model as r
import game.items as p
import content
import entity_catalog as catalog
import module_rules as rules


class ModuleOptionsTests(unittest.TestCase):
    def test_default_legacy_compatibility(self):
        mod=dict(kind='module',target='protection',rarity=0,level=1)
        for kind in ('armor','helmet'):
            self.assertTrue(rules.compatible(dict(kind=kind,rarity=0,level=1),mod))
        self.assertFalse(rules.compatible(dict(kind='weapon'),mod))

    def test_catalog_changes_apply_to_old_module_instances(self):
        ident='module_amplifier';mod=p.module(index=ident)
        definition=copy.deepcopy(content.MODULE_DATA[ident])
        definition.update(target='helmet',min_equipment_rarity=3)
        with patch.dict(content.MODULE_DATA,{ident:definition}):
            for kind in ('armor','helmet','weapon'):
                for rarity in range(5):
                    self.assertEqual(rules.compatible(dict(kind=kind,rarity=rarity,level=1),mod),kind=='helmet' and rarity>=3)
            mod['rarity']=4
            self.assertFalse(rules.compatible(dict(kind='helmet',rarity=3,level=1),mod))

    def test_weapon_categories_and_level_restrictions(self):
        mod=dict(kind='module',target='weapon',weapon_categories=['shotgun','sniper'],min_equipment_rarity=2,rarity=0,level=3)
        for ident,data in content.EQUIPMENT.items():
            if data['kind']!='weapon':continue
            item=dict(kind='weapon',type_id=ident,rarity=2,level=3)
            self.assertEqual(rules.compatible(item,mod),data.get('category','pistol') in ('shotgun','sniper'))
            item['level']=2;self.assertFalse(rules.compatible(item,mod))

    def test_editor_defaults_validation_and_group_order(self):
        store=catalog.Store();ident=content.MODULE_IDS[0]
        data,text=store.draft('module',ident)
        self.assertEqual(data['min_equipment_rarity'],0)
        self.assertEqual(data['weapon_categories'],list(catalog.CATEGORIES))
        self.assertEqual(catalog.validate_definition('module',ident,data,text,store.art),[])
        for value in (-1,5,True,'3'):
            bad=dict(data,min_equipment_rarity=value)
            self.assertTrue(catalog.validate_definition('module',ident,bad,text,store.art))
        for cats in ([],['unknown'],'pistol'):
            self.assertTrue(catalog.validate_definition('module',ident,dict(data,weapon_categories=cats),text,store.art))
        values=[dict(target=t,min_level=l) for t,l in [('protection',1),('armor',1),('helmet',9),('helmet',2),('weapon',1)]]
        self.assertEqual([(d['target'],d['min_level']) for d in sorted(values,key=lambda d:(catalog.module_group(d),d['min_level']))], [('helmet',2),('helmet',9),('armor',1),('protection',1),('weapon',1)])

    def test_install_rejects_catalog_restriction_without_losing_module(self):
        game=r.Game(11);mod=p.module(index='module_amplifier');game.bag.append(mod)
        definition=dict(content.MODULE_DATA[mod['type_id']],min_equipment_rarity=4)
        before=copy.deepcopy((game.bag,game.equipped))
        with patch.dict(content.MODULE_DATA,{mod['type_id']:definition}):
            self.assertFalse(game.install(game.weapon['id'],mod['id']))
        self.assertEqual((game.bag,game.equipped),before)

    def test_min_level_filters_random_generation(self):
        ident=content.MODULE_IDS[0]
        definition=dict(content.MODULE_DATA[ident],min_level=10)
        with patch.dict(content.MODULE_DATA,{ident:definition}):
            rng=random.Random(48)
            self.assertTrue(all(p.module(rng=rng,level=1)['type_id']!=ident for _ in range(150)))
            self.assertEqual(p.module(index=ident,level=1)['level'],10)

    def test_generated_equipment_pool_respects_all_restrictions(self):
        defs={k:dict(d,min_equipment_rarity=4,weapon_categories=['sniper']) for k,d in content.MODULE_DATA.items()}
        with patch.dict(content.MODULE_DATA,defs):
            for ident,d in content.EQUIPMENT.items():
                for tier in (0,4):
                    item=p.equipment(ident,tier,level=30)
                    pool=rules.eligible_modules(item)
                    if tier==0 or d['kind']=='weapon' and d.get('category')!='sniper':self.assertEqual(pool,[])
                    for mid in pool:self.assertTrue(rules.compatible(item,p.module(tier,index=mid,level=30)))

    def test_changed_restrictions_detach_installed_modules_safely(self):
        game=r.Game(21);mod=p.module(index='module_amplifier')
        game.weapon['modules'].append(mod)
        definition=dict(content.MODULE_DATA[mod['type_id']],min_equipment_rarity=4)
        with patch.dict(content.MODULE_DATA,{mod['type_id']:definition}):rules.migrate_game(game)
        self.assertNotIn(mod,game.weapon['modules']);self.assertIn(mod,game.bag)

    def test_custom_restrictions_persist(self):
        import tempfile
        from test_entity_editor import project_copy
        with tempfile.TemporaryDirectory() as folder:
            store=catalog.Store(project_copy(folder));ident=content.MODULE_IDS[0]
            data,text=store.draft('module',ident)
            data.update(target='helmet',min_equipment_rarity=3,weapon_categories=['sniper'],min_level=7)
            store.put('module',ident,data,text);store.save()
            saved,_=catalog.Store(folder).draft('module',ident)
            self.assertEqual(saved,data)


if __name__=='__main__':unittest.main()
