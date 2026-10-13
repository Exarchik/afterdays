import copy,unittest
from unittest.mock import patch
import quest_catalog,quest_profiles
from game.model import Game
from game.systems.reputation import reward_factor

class QuestProfilesTests(unittest.TestCase):
    def doc(self,kind,**values):
        spec=quest_profiles.defaults(kind);spec.update(values)
        return dict(version=1,quests=[],native={kind:{'normal':spec,'elite':dict(spec,reward=spec['reward']*3,xp_reward=spec['xp_reward']*2)}})

    def test_validation_and_all_defaults(self):
        for kind in {**quest_catalog.TYPES,**quest_catalog.SPECIAL}:
            for elite in (False,True):self.assertEqual(quest_profiles.validate_spec(quest_profiles.defaults(kind,elite)),[])
        for field,value in [('min_level',0),('money_power',float('nan')),('xp_step',-1),('reward',-1)]:
            self.assertTrue(quest_catalog.validate(self.doc('hunt',**{field:value})))

    def test_native_scaling_variants_no_compounding_and_snapshot(self):
        g=Game(5);doc=self.doc('supplies',reward=120,xp_reward=30,xp_step=7,money_power=1,title='Нові припаси',art='quest:cache')
        with patch.object(quest_catalog,'DOCUMENT',doc):
            for elite in (False,True):
                q=dict(id='test',kind='supplies',city=0,status='offered',level=3,unique=elite,food_need=3,med_need=2,scribe=True)
                g.price_quest(q);before=copy.deepcopy(q)
                for _ in range(3):g.price_quest(q);g.apply_quest_profile(q)
                self.assertEqual(q,before)
                fee=(360 if elite else 120)*3
                self.assertEqual(q['base_reward'],fee+21*3+48*2)
                self.assertEqual(q['reward'],round(q['base_reward']*reward_factor(g.reputation(0))))
                self.assertEqual(q['xp_reward'],(60 if elite else 30)+14)
                self.assertEqual(q['quest_art'],'quest:cache')
                q['status']='active';snapshot=copy.deepcopy(q)
                doc['native']['supplies']['elite' if elite else 'normal']['reward']=999
                g.price_quest(q);self.assertEqual(q,snapshot)

    def test_player_gate_filters_cached_offers_and_scribe(self):
        g=Game(5)
        native={kind:{variant:dict(quest_profiles.defaults(kind,variant=='elite'),min_level=100) for variant in ('normal','elite')}
                for kind in {**quest_catalog.TYPES,**quest_catalog.SPECIAL}}
        with patch.object(quest_catalog,'DOCUMENT',dict(version=1,quests=[],native=native)):
            self.assertEqual(g.mayor_offers(),[])
            g.spawn_scribe();self.assertEqual(g.mayor_offers(),[])
            self.assertFalse(g.accept_quest(g.traveler['offers'][0]['id']))
            for variants in native.values():
                for spec in variants.values():spec['min_level']=1
            self.assertTrue(g.mayor_offers())

    def test_authored_scaled_elite_art(self):
        g=Game(5);spec=quest_catalog.draft('scaled');spec.update(reward=100,xp_reward=20,money_power=1,xp_step=4,elite=True,art='quest:cache')
        with patch.object(quest_catalog,'DOCUMENT',dict(version=1,quests=[spec])):
            q=next(q for q in g.mayor_offers() if q.get('authored_id'))
            self.assertTrue(q['unique']);self.assertEqual(q['quest_art'],'quest:cache')
            self.assertEqual(q['reward'],100*q['level']);self.assertEqual(q['xp_reward'],20+4*(q['level']-1))
            self.assertTrue(g.accept_quest(q['id']))
