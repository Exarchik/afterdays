"""Content editing is persisted independently, and previews match generated entities."""
import copy
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import afterdays as game
import content
import progression
import module_rules
import monster_rules
import entity_catalog as catalog


def project_copy(folder, with_code=False):
    root=Path(folder)
    for directory in ('data','locales'):
        shutil.copytree(catalog.ROOT/directory,root/directory,dirs_exist_ok=True)
    (root/'assets').mkdir(exist_ok=True)
    shutil.copy2(catalog.ROOT/'assets/manifest.json',root/'assets/manifest.json')
    if (catalog.ROOT/'assets/custom').exists():shutil.copytree(catalog.ROOT/'assets/custom',root/'assets/custom',dirs_exist_ok=True)
    if with_code:
        for path in catalog.ROOT.glob('*.py'):
            if not path.name.startswith('test_'):shutil.copy2(path,root/path.name)
    return root


class EntityEditorTests(unittest.TestCase):
    def test_existing_catalog_is_valid(self):
        store=catalog.Store();self.assertEqual(store.validate(),[]);self.assertFalse(store.dirty)

    def test_equipment_previews_match_actual_items_and_condition(self):
        for ident,data in content.EQUIPMENT.items():
            for level in (data['min_level'],15):
                for tier in (0,2,4):
                    item=progression.equipment(ident,tier,level=level)
                    for condition in (0,25,100):
                        item['durability']=condition
                        values=catalog.preview(data['kind'],data,level,tier,condition,player_level=7)
                        for key,value in progression.stats(item).items():self.assertEqual(values[key],value,(ident,key))
                        self.assertEqual(values['value'],item['value']);self.assertEqual(values['weight'],progression.item_weight(item))
                        if data['kind']=='weapon':self.assertEqual(values['shot_damage'],module_rules.shot_damage(item,7))

    def test_module_and_monster_previews_match_runtime(self):
        for ident,data in content.MODULE_DATA.items():
            for L in (1,15):
                for tier in (0,4):
                    for tradeoff in (False,True):
                        values=catalog.preview('module',data,L,tier,tradeoff=tradeoff)
                        for key,value in module_rules.module_stats(ident,tier,L,tradeoff).items():self.assertEqual(values[key],value)
        for ident,data in content.MONSTER_DATA.items():
            for grade in catalog.GRADES:
                for weak in (False,True):
                    enemy=monster_rules.make(random.Random(1),ident,15,[0,0],grade,weak)
                    values=catalog.preview('monster',data,data['base_level'],grade=grade,weak=weak)
                    for key,value in values.items():self.assertEqual(value,data['regen'] if key=='regen' else enemy[key])

    def test_unsaved_draft_changes_preview_without_mutating_runtime(self):
        data=copy.deepcopy(content.EQUIPMENT['weapon_ash_pistol']);before=copy.deepcopy(content.EQUIPMENT)
        normal=catalog.preview('weapon',data,10);data['damage']+=20;edited=catalog.preview('weapon',data,10)
        self.assertGreater(edited['damage'],normal['damage']);self.assertEqual(content.EQUIPMENT,before)
        self.assertGreater(catalog.preview('weapon',data,11)['damage'],edited['damage'])

    def test_custom_module_curves_fixed_penalties_and_new_primary_stat(self):
        data=copy.deepcopy(content.MODULE_DATA['module_amplifier'])
        data.update(rarity_stats={'local_damage_percent':[3,4,5,6,7],'crit':[2,4,6,8,10]},fixed_penalties={'strength':-10})
        values=catalog.preview('module',data,15,2)
        self.assertEqual(values['local_damage_percent'],5);self.assertEqual(values['crit'],11);self.assertEqual(values['strength'],-10)
        enhanced=catalog.preview('module',data,15,2,tradeoff=True)
        self.assertEqual(enhanced['local_damage_percent'],8);self.assertEqual(enhanced['accuracy'],-10)

    def test_add_every_kind_roundtrip_and_stable_indices(self):
        with tempfile.TemporaryDirectory() as folder:
            store=catalog.Store(project_copy(folder));before=copy.deepcopy(store.data)
            ids={section:store.add(section,'Нова '+label) for section,label in catalog.SECTIONS.items()}
            store.save();loaded=catalog.Store(folder)
            for section,ident in ids.items():
                data,texts=loaded.draft(section,ident);self.assertEqual(texts['name'],'Нова '+catalog.SECTIONS[section]);self.assertIn(ident,loaded.art)
                if section=='monster':self.assertIn('corpse:'+ident,loaded.art);self.assertIn('trophy_'+ident,loaded.art)
            for group in ('modules','monsters'):
                for ident,data in before[group].items():self.assertEqual(loaded.data[group][ident]['legacy_index'],data['legacy_index'])
            self.assertTrue((Path(folder)/'data/equipment.json.bak').exists())

    def test_conflict_and_invalid_values_do_not_write(self):
        with tempfile.TemporaryDirectory() as folder:
            store=catalog.Store(project_copy(folder));store.add('weapon','Test')
            path=store.paths['equipment'];path.write_bytes(path.read_bytes()+b'\n');before=path.read_bytes()
            with self.assertRaises(ValueError):store.save()
            self.assertEqual(path.read_bytes(),before)
            ident=store.items('module')[0][0];data,names=store.draft('module',ident);data['rarity_stats']={'damage':[1,2]}
            with self.assertRaises(ValueError):store.put('module',ident,data,names)

    def test_partial_io_failure_rolls_back_catalog_and_names(self):
        with tempfile.TemporaryDirectory() as folder:
            store=catalog.Store(project_copy(folder));store.add('weapon','Test');before={k:p.read_bytes() for k,p in store.paths.items()}
            replace=os.replace;calls=0
            def fail_second(src,dst):
                nonlocal calls
                calls+=1
                if calls==2:raise OSError('simulated write failure')
                return replace(src,dst)
            with patch('entity_catalog.os.replace',side_effect=fail_second):
                with self.assertRaises(OSError):store.save()
            self.assertEqual({k:p.read_bytes() for k,p in store.paths.items()},before)
            self.assertTrue(store.dirty)

    def test_save_all_rolls_back_entities_if_event_write_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            store=catalog.Store(project_copy(folder));store.add('weapon','Test')
            event_path=Path(folder)/'data/road_events.json';events=catalog.read(event_path);old_event=event_path.read_bytes()
            events['events'][0]['title']='Changed'
            before={k:p.read_bytes() for k,p in store.paths.items()};replace=os.replace
            def fail_event(src,dst):
                if Path(dst)==event_path:raise OSError('simulated event write failure')
                return replace(src,dst)
            with patch('entity_catalog.os.replace',side_effect=fail_event):
                with self.assertRaises(OSError):store.save((event_path,events,old_event))
            self.assertEqual({k:p.read_bytes() for k,p in store.paths.items()},before)
            self.assertEqual(event_path.read_bytes(),old_event)

    def test_fresh_game_imports_new_models_sprites_and_trophies(self):
        with tempfile.TemporaryDirectory() as folder:
            store=catalog.Store(project_copy(folder,True))
            ids={section:store.add(section,'Тест '+section) for section in catalog.SECTIONS};store.save()
            code="""
import json,random
import afterdays,progression,content,monster_rules,sprites,economy
ids=json.loads(__import__('sys').argv[1])
for section in ('weapon','armor','helmet'):
    ident=ids[section];item=progression.equipment(ident,level=30)
    assert item['type_id']==ident and item['name']=='Тест '+section
    assert sprites.item_key(item) in sprites.MANIFEST
module=progression.module(index=ids['module'],level=10)
assert module['type_id']==ids['module']
enemy=monster_rules.make(random.Random(1),ids['monster'],30,[0,0])
assert enemy['type_id']==ids['monster'] and enemy['kind'] in monster_rules.eligible(30)
assert ids['monster'] in sprites.MANIFEST and sprites.corpse_key(enemy) in sprites.MANIFEST
trophy=economy.trophy(ids['monster']);assert trophy['name']=='Трофей: Тест monster'
assert sprites.item_key(trophy) in sprites.MANIFEST
g=afterdays.Game(1)
g.bag.extend([module,item,trophy]);g.save('check_save.json')
h=afterdays.Game.load('check_save.json');assert h.bag==g.bag
print('Fresh runtime OK')
"""
            output=subprocess.check_output([sys.executable,'-B','-X','utf8','-c',code,json.dumps(ids)],cwd=folder,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
            self.assertIn('Fresh runtime OK',output)


if __name__=='__main__':unittest.main()
