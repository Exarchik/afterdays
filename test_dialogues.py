import copy,json,tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch
import afterdays as r,dialogue_system as ds,quest_catalog as qc
from entity_catalog import Store
from test_entity_editor import project_copy

class DialogueTests(unittest.TestCase):
    def setUp(self):self.doc=json.loads((Path(__file__).parent/'data/dialogues.json').read_text(encoding='utf-8'))
    def test_branches_unlock_dialogue_and_no_reward_replay(self):
        original=copy.deepcopy(self.doc);s=ds.Session(self.doc,'demo_crossroads')
        with self.assertRaises(ValueError):s.switch('demo_trusted')
        s.choose('help');self.assertEqual(s.rewards,{'parts':12});self.assertTrue(s.values['helped'])
        s.choose('secret');s.choose();self.assertIsNone(s.block)
        s.switch('demo_trusted');self.assertIsNotNone(s.block)
        s.switch('demo_crossroads');s.choose('help');self.assertEqual(s.rewards,{'parts':12});self.assertEqual(s.values['trust'],1)
        self.assertEqual(self.doc,original)
        other=ds.Session(self.doc,'demo_crossroads');other.choose('refuse');self.assertEqual(other.block['actor'],'player');self.assertFalse(other.values['helped'])
        self.assertFalse(other.rewards)
    def test_hidden_reply_cannot_be_selected_and_player_identity(self):
        s=ds.Session(self.doc,'demo_crossroads',player_name='Тарас',player_art='npc:traveler');s.choose('help');s.values['trust']=0
        self.assertEqual(s.replies(),[])
        with self.assertRaises(ValueError):s.choose('secret')
        s.switch('demo_crossroads');s.choose('refuse');self.assertEqual(s.actor()['name'],'Тарас')
    def test_invalid_tree_types_and_references_rejected(self):
        d=copy.deepcopy(self.doc);d['dialogues'][0]['nodes']['secret']['next']='greeting';self.assertTrue(ds.validate(d))
        d=copy.deepcopy(self.doc);d['dialogues'][0]['nodes']['secret']['actor']='missing';self.assertTrue(ds.validate(d))
        d=copy.deepcopy(self.doc);d['dialogues'][0]['nodes']['greeting']['actor']='player';self.assertTrue(ds.validate(d))
        d=copy.deepcopy(self.doc);d['dialogues'][0]['nodes']['greeting']['replies'][0]['actions'][0]['value']='wrong';self.assertTrue(ds.validate(d))
    def test_game_rewards_persist_and_replay_is_safe(self):
        g=r.Game(5);before=g.count('parts');s=ds.Session(self.doc,'demo_crossroads',game=g);s.choose('help')
        self.assertEqual(g.count('parts')-before,12)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);g=r.Game.load(path)
        ds.Session(self.doc,'demo_trusted',game=g)
        ds.Session(self.doc,'demo_crossroads',game=g).choose('help');self.assertEqual(g.count('parts')-before,12)
    def test_quest_start_and_failed_start_are_atomic(self):
        spec=qc.draft('dialogue_job');spec['kind']='supplies'
        self.doc['dialogues'][0]['nodes']['greeting']['replies'][0]['actions'].append(dict(kind='quest',quest=spec['id']))
        with patch.object(qc,'DOCUMENT',dict(version=1,quests=[spec])):
            g=r.Game(5);s=ds.Session(self.doc,'demo_crossroads',{spec['id']:spec},g)
            s.choose('help');self.assertTrue(any(q.get('authored_id')==spec['id'] and q['status']=='active' for q in g.quests))
            spec['min_level']=99;g=r.Game(5);before=copy.deepcopy({k:v for k,v in vars(g).items() if k!='rng'});rng=g.rng.getstate()
            s=ds.Session(self.doc,'demo_crossroads',{spec['id']:spec},g)
            with self.assertRaises(ValueError):s.choose('help')
            self.assertEqual(before,{k:v for k,v in vars(g).items() if k!='rng'});self.assertEqual(rng,g.rng.getstate())
            self.assertEqual(s.current,'greeting');self.assertFalse(s.values['helped']);self.assertFalse(s.rewards)
    def test_store_save_reload_and_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(project_copy(folder));store.data['dialogues']['actors']['guide']['name']='Змінений актор'
            store.data['texts']['weapon_ash_pistol.name']='Змінена назва';before={k:p.read_bytes() for k,p in store.paths.items()};replace=os.replace
            def fail(source,target):
                if Path(target)==store.paths['texts']:raise OSError('simulated failure')
                return replace(source,target)
            with patch('entity_catalog.os.replace',side_effect=fail):
                with self.assertRaises(OSError):store.save()
            self.assertEqual(before,{k:p.read_bytes() for k,p in store.paths.items()});store.save()
            self.assertEqual(Store(folder).data['dialogues']['actors']['guide']['name'],'Змінений актор')
