import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import game.model as r
import quest_catalog as qc
import dialogue_system as ds
import game.systems.story as ss


class StoryTests(unittest.TestCase):
    def setUp(self):
        self.quest=qc.draft('story_job');self.quest.update(kind='supplies',food_need=0,med_need=0,reward=123,xp_reward=0)
        self.story=dict(id='main_story',title='Головний сюжет',enabled=True,stages=[dict(kind='dialogue',ref='intro'),dict(kind='quest',ref='story_job'),dict(kind='visit',ref=1)])
        self.doc=dict(version=1,quests=[self.quest],stories=[self.story])
        self.dialogs=dict(version=1,actors={'player':dict(name='Герой',art='npc:traveler')},variables={},dialogues=[dict(id='intro',title='Вступ',root='first',conditions=[],nodes={'first':dict(ds.node(text='Перша фраза'),next='last'),'last':ds.node(text='Остання фраза')})])
        self.catalog=patch.object(qc,'DOCUMENT',self.doc);self.catalog.start();self.addCleanup(self.catalog.stop)
        self.read=patch('content.read',return_value=self.dialogs)
        self.g=r.Game(5)

    def start(self):
        with self.read:self.assertTrue(self.g.start_story('main_story'))

    def test_order_resume_snapshot_and_exactly_once_reward(self):
        self.assertFalse(qc.eligible(self.g,self.quest));self.start()
        self.assertFalse(self.g.start_story('main_story'))
        s=self.g.story_session('main_story');s.choose()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';self.g.save(path);self.g=r.Game.load(path)
        qc.DOCUMENT=dict(version=1,quests=[],stories=[])
        s=self.g.story_session('main_story');self.assertEqual(s.current,'last');s.choose()
        with self.assertRaises(ValueError):s.choose()
        offer=next(q for q in self.g.mayor_offers() if q.get('authored_id')=='story_job')
        self.assertTrue(self.g.accept_quest(offer['id']))
        self.assertFalse(self.g.abandon_quest(offer['id']))
        money=self.g.money;self.assertTrue(self.g.turn_in(offer['id']))
        self.assertEqual(self.g.money-money,123);self.assertFalse(self.g.turn_in(offer['id']))
        self.g.story_sync();self.assertEqual(self.g.story_states()['main_story']['index'],2)
        self.g.x,self.g.y=self.g.cities[1];self.g.story_sync()
        self.assertEqual(self.g.story_states()['main_story']['status'],'done')
        self.assertEqual(self.g.story_states()['main_story']['history'],[0,1,2])

    def test_cancel_dialogue_does_not_complete_and_stale_session_rejected(self):
        self.start();first=self.g.story_session('main_story');second=self.g.story_session('main_story')
        self.assertEqual(self.g.story_states()['main_story']['index'],0)
        first.choose()
        with self.assertRaises(ValueError):second.choose()
        self.assertEqual(self.g.story_session('main_story').current,'last')
        self.g.battle={'active':True}
        with self.assertRaises(ValueError):first.choose()

    def test_validation_and_legacy_save(self):
        self.assertEqual(ss.validate(self.doc,self.dialogs),[])
        for stage in (dict(kind='quest',ref='absent'),dict(kind='dialogue',ref='absent'),dict(kind='visit',ref=-1),dict(kind='unknown',ref=0)):
            doc=copy.deepcopy(self.doc);doc['stories'][0]['stages']=[stage]
            self.assertTrue(ss.validate(doc,self.dialogs))
        doc=copy.deepcopy(self.doc);doc['stories'][0]['stages'].append(dict(kind='quest',ref='story_job'))
        self.assertTrue(ss.validate(doc,self.dialogs))
        self.assertEqual(self.g.story_states(),{})
        with patch.object(qc,'DOCUMENT',dict(version=1,quests=[self.quest])):
            self.assertTrue(qc.eligible(self.g,self.quest))

    def test_dialogue_rewards_are_not_replayed_after_resume(self):
        self.dialogs['actors']['npc']=dict(name='Провідник',art='npc:traveler')
        n=self.dialogs['dialogues'][0]['nodes']['first'];n.update(actor='npc',next=None,replies=[dict(id='yes',text='Так',conditions=[],next='last',actions=[dict(kind='reward',reward='money',amount=17)])])
        self.start();money=self.g.money
        self.g.story_session('main_story').choose('yes')
        self.assertEqual(self.g.money-money,17)
        self.g.story_session('main_story').choose()
        self.assertEqual(self.g.money-money,17)


if __name__=='__main__':unittest.main()
