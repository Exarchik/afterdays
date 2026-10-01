import copy,json,tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch
import afterdays as r,quest_catalog as catalog
from entity_catalog import Store
from test_entity_editor import project_copy

class QuestEditorTests(unittest.TestCase):
    def spec(self,ident='custom_test',**values):
        spec=catalog.draft(ident);spec.update(values);return spec

    def test_conditions_and_dependencies(self):
        g=r.Game(5);s=self.spec();self.assertTrue(catalog.eligible(g,s))
        for values in (dict(enabled=False),dict(min_level=g.level+1),dict(max_level=0),dict(min_reputation=101),
                       dict(max_reputation=-1),dict(min_turn=g.turn+1),dict(cities=[999]),dict(requires=['before'])):
            self.assertFalse(catalog.eligible(g,dict(s,**values)),values)
        g.quests.append(dict(id='old',authored_id='before',status='done',kind='hunt',city=0))
        self.assertTrue(catalog.eligible(g,dict(s,requires=['before'])))

    def test_validation_rejects_cycles_and_bad_parameters(self):
        a=self.spec('a',requires=['b']);b=self.spec('b',requires=['a'])
        self.assertTrue(catalog.validate(dict(version=1,quests=[a,b])))
        for values in (dict(reward=-1),dict(kind='unknown'),dict(cities=['0']),dict(requires=['missing']),dict(min_level=10,max_level=1)):
            self.assertTrue(catalog.validate(dict(version=1,quests=[self.spec(**values)])))

    def test_accept_save_reload_and_turn_in_snapshot_with_exact_rewards(self):
        g=r.Game(5);s=self.spec(kind='supplies',food_need=1,med_need=1,reward=321,xp_reward=55,description='Авторський опис')
        with patch.object(catalog,'DOCUMENT',dict(version=1,quests=[s])):
            offer=next(q for q in g.mayor_offers() if q.get('authored_id'));ident=offer['id']
            self.assertEqual(g.mayor_offers()[0]['id'],ident)
            self.assertTrue(g.accept_quest(ident));self.assertFalse(g.accept_quest(ident))
            q=next(q for q in g.quests if q['id']==ident)
            self.assertIn(s['description'],g.quest_text(q))
            # Catalog edits/deletion do not change an accepted quest.
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'save.json';g.save(path);g=r.Game.load(path)
            catalog.DOCUMENT=dict(version=1,quests=[])
            money,xp=g.money,g.xp
            self.assertTrue(g.turn_in(ident));self.assertEqual(g.money-money,321);self.assertEqual(g.xp-xp,55)
            self.assertFalse(g.turn_in(ident));self.assertFalse(catalog.eligible(g,s))

    def test_repeat_cooldown_active_dedup_and_capacity(self):
        g=r.Game(5);s=self.spec(kind='supplies',repeatable=True,cooldown=10)
        with patch.object(catalog,'DOCUMENT',dict(version=1,quests=[s])):
            q=next(q for q in g.mayor_offers() if q.get('authored_id'));self.assertTrue(g.accept_quest(q['id']))
            self.assertFalse(catalog.eligible(g,s));self.assertTrue(g.abandon_quest(q['id']))
            self.assertFalse(catalog.eligible(g,s));g.turn+=10;self.assertTrue(catalog.eligible(g,s))
            new=next(q for q in g.mayor_offers() if q.get('authored_id'))
            self.assertNotEqual(q['id'],new['id']);self.assertLessEqual(len(g.mayor_offers()),g.quest_capacity(g.city))

    def test_native_types_can_create_and_accept_authored_variants(self):
        for kind in catalog.TYPES:
            with self.subTest(kind=kind):
                g=r.Game(5);s=self.spec(kind=kind)
                with patch.object(catalog,'DOCUMENT',dict(version=1,quests=[s])):
                    custom=[q for q in g.mayor_offers() if q.get('authored_id')]
                    self.assertTrue(custom,kind)
                    self.assertTrue(g.accept_quest(custom[0]['id']),kind)
                    q=next(q for q in g.quests if q.get('authored_id'))
                    self.assertEqual(q['title'],s['title'])
                    self.assertIsInstance(g.quest_text(q),str)

    def test_store_atomic_save_and_external_edit_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(project_copy(folder));store.data['quests']['quests'].append(self.spec())
            store.data['texts']['weapon_ash_pistol.name']='Changed'
            before={k:p.read_bytes() for k,p in store.paths.items()};replace=os.replace
            def fail(source,target):
                if Path(target)==store.paths['texts']:raise OSError('simulated failure')
                return replace(source,target)
            with patch('entity_catalog.os.replace',side_effect=fail):
                with self.assertRaises(OSError):store.save()
            self.assertEqual(before,{k:p.read_bytes() for k,p in store.paths.items()})
            store.save();self.assertEqual(Store(folder).data['quests'],store.data['quests'])
            store.paths['quests'].write_text('{"external":true}',encoding='utf-8')
            with self.assertRaises(ValueError):store.save()
