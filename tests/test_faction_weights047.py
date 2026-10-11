import copy,random,unittest
from unittest.mock import patch
import game.model as afterdays
import content
import faction_rules as f

class WeightTests(unittest.TestCase):
    def test_exact_mixed_boundary_and_distinct_groups(self):
        doc=f.default_catalog(content.MONSTER_DATA)
        for level in (1,2):
            for roll,mixed in ((.199999,True),(.2,False),(.99,False)):
                rng=random.Random(7)
                with patch.object(rng,'random',return_value=roll):groups,_=f.encounter_factions(rng,doc,content.MONSTER_DATA,level,3)
                self.assertEqual(len(set(groups))>=2,mixed)

    def test_distribution_and_disabled_faction(self):
        doc=f.default_catalog(content.MONSTER_DATA)
        for key,weight in dict(bandits=60,settlers=30,monsters=10,infected=0).items():doc['factions'][key]['encounter_weight']=weight
        rng=random.Random(123);mixed=0;counts=dict(bandits=0,settlers=0,monsters=0)
        for _ in range(20000):
            groups,_=f.encounter_factions(rng,doc,content.MONSTER_DATA,2,3)
            self.assertNotIn('infected',groups)
            if len(set(groups))>1:mixed+=1
            else:counts[groups[0]]+=1
        self.assertAlmostEqual(mixed/20000,.2,delta=.015)
        for key,expected in dict(bandits=.48,settlers=.24,monsters=.08).items():self.assertAlmostEqual(counts[key]/20000,expected,delta=.015)

    def test_level_filter_and_legacy_defaults(self):
        doc=f.default_catalog(content.MONSTER_DATA);doc['humans']['human_bandit']['min_level']=2
        self.assertNotIn('bandits',f.encounter_pools(doc,content.MONSTER_DATA,1))
        self.assertIn('bandits',f.encounter_pools(doc,content.MONSTER_DATA,2))
        self.assertEqual(f.encounter_weight({}),25)

    def test_friendly_arena_exit_immediately_no_reward(self):
        g=afterdays.Game(47)
        def settlers(rng,doc,monsters,level,count):return ['settlers']*count,f.encounter_pools(doc,monsters,level)
        before=g.money
        with patch('faction_rules.encounter_factions',side_effect=settlers):g.start_battle()
        self.assertTrue(g.battle['safe_exit047']);self.assertEqual({e['faction'] for e in g.battle['enemies']},{'settlers'})
        self.assertTrue(g.flee());self.assertEqual(g.coward_turns,0);self.assertEqual(g.money,before)

    def test_arena_preserves_selected_factions(self):
        g=afterdays.Game(47)
        for _ in range(100):
            g.start_battle();groups={e['faction'] for e in g.battle['enemies']}
            self.assertGreaterEqual(len(groups),1)
            if groups=={'settlers'}:self.assertTrue(g.battle['safe_exit047'])
            else:self.assertFalse(g.battle.get('safe_exit047',False))

    def test_invalid_weights_and_insufficient_groups(self):
        import entity_catalog
        store=entity_catalog.Store()
        for weight in (-1,float('nan'),float('inf'),'20',True):
            doc=copy.deepcopy(store.data['factions']);doc['factions']['bandits']['encounter_weight']=weight
            self.assertTrue(f.validate(doc,store.data['monsters'],store.art))
        doc=copy.deepcopy(store.data['factions'])
        for key,d in doc['factions'].items():d['encounter_weight']=1 if key=='settlers' else 0
        self.assertTrue(f.validate(doc,store.data['monsters'],store.art))

if __name__=='__main__':unittest.main()
