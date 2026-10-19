"""Generator repair: switches with different (some negative) loads balanced into a green zone."""
import copy
import random
import unittest

import quest_catalog
import quest_minigames
import quest_profiles
import game.items as items
from game.model import Game
from game.systems import generator_balance as balance
from tests.fixtures.quest_offer import offer_for
from tests.fixtures.generator import solution,solve


def accepted(seed=4):
    g=Game(seed);offer=offer_for(g,balance.KIND)
    assert g.accept_quest(offer['id'])
    q=g.quests[-1];g.x,g.y=q['pos']
    return g,q


class GenerationTests(unittest.TestCase):
    def test_defaults_validation_and_editor_block(self):
        spec=quest_profiles.defaults(balance.KIND)
        self.assertEqual(balance.settings_for(spec),dict(switches=5,negatives=2,zone=5,show_weights=0,shock_chance=35,shock_max=5))
        self.assertEqual(quest_profiles.validate_spec(spec),[])
        self.assertEqual([k for k,_ in quest_minigames.MINIGAMES[balance.KIND]['fields']],list(balance.SETTINGS))
        self.assertEqual(len(balance.validate_settings(dict(spec,switches=9,zone='x'))),2)
        self.assertEqual(len(balance.validate_settings(dict(spec,switches=3,negatives=3))),1)

    def test_default_boards_need_a_negative_switch_and_cannot_all_be_on(self):
        settings=balance.settings_for({})
        for seed in range(60):
            weights,(lo,hi)=balance.generate(random.Random(seed),settings)
            self.assertEqual(len(weights),5);self.assertEqual(hi-lo,10)
            self.assertTrue(1<=sum(w<0 for w in weights)<=2)
            self.assertGreater(sum(w for w in weights if w>0),balance.RED)
            hits=[mask for mask,total in balance.subset_sums(weights) if lo<=total<=hi]
            self.assertTrue(1<=len(hits)<=2,(seed,weights,lo,hits))
            for mask in hits:self.assertTrue(any(mask>>i&1 and w<0 for i,w in enumerate(weights)))
            self.assertTrue(all(abs(a-b)>=4 for i,a in enumerate(weights) for b in weights[i+1:]))

    def test_every_editor_combination_is_solvable(self):
        for n in range(3,8):
            for neg in range(0,min(3,n-1)+1):
                for seed in range(4):
                    settings=balance.settings_for(dict(switches=n,negatives=neg))
                    weights,(lo,hi)=balance.generate(random.Random(seed),settings)
                    self.assertEqual(len(weights),n)
                    self.assertTrue(any(lo<=total<=hi for _,total in balance.subset_sums(weights)),(n,neg,seed))
                    if neg==0:self.assertTrue(all(w>0 for w in weights))


class QuestTests(unittest.TestCase):
    def test_board_is_deterministic_per_quest(self):
        g,q=accepted();state=g.rng.getstate()
        copy_q=dict(q,generator_version=0);g.init_generator(copy_q)
        self.assertEqual(copy_q['generator_weights'],q['generator_weights']);self.assertEqual(copy_q['generator_zone'],q['generator_zone'])
        self.assertEqual(state,g.rng.getstate())

    def test_overload_trips_everything_and_order_matters(self):
        g,q=accepted();w=q['generator_weights']
        positive=sorted((i for i in range(5) if w[i]>0),key=lambda i:-w[i])
        total=0
        for i in positive:
            g.generator_toggle(q['id'],i);total+=w[i]
            if total>balance.RED:break
        self.assertTrue(g._generator_overload);self.assertEqual(q['generator_on'],[False]*5)
        self.assertEqual(balance.load(q),0)

    def test_repair_requires_green_zone_and_materials(self):
        g,q=accepted();self.assertFalse(g.repair_generator(q['id']))
        solve(g,q);g.bag[:]=[i for i in g.bag if i['kind']!=q['material']]
        self.assertFalse(g.repair_generator(q['id']))
        items.add_to(g.bag,items.supply(q['material'],q['material_qty']))
        self.assertTrue(g.repair_generator(q['id']));self.assertTrue(g.quest_ready(q))
        self.assertFalse(g.generator_toggle(q['id'],0))

    def test_only_at_the_generator(self):
        g,q=accepted();g.x,g.y=g.cities[q['city']]
        self.assertFalse(g.generator_toggle(q['id'],0));self.assertFalse(g.repair_generator(q['id']))

    def test_editor_profile_controls_board(self):
        g=Game(4);offer=offer_for(g,balance.KIND)
        spec=dict(quest_profiles.defaults(balance.KIND),switches=7,negatives=0,zone=3,show_weights=1)
        doc=copy.deepcopy(quest_catalog.DOCUMENT);doc.setdefault('native',{})[balance.KIND]={'normal':spec,'elite':spec}
        old=quest_catalog.DOCUMENT;quest_catalog.DOCUMENT=doc
        try:self.assertTrue(g.accept_quest(offer['id']))
        finally:quest_catalog.DOCUMENT=old
        q=g.quests[-1]
        self.assertEqual(len(q['generator_weights']),7);self.assertEqual(q['generator_zone'][1]-q['generator_zone'][0],6)
        self.assertTrue(all(w>0 for w in q['generator_weights']));self.assertEqual(q['generator_settings']['show_weights'],1)
        self.assertIsNotNone(solution(q))

    def test_old_orders_upgrade_but_finished_repairs_stay(self):
        g,q=accepted()
        old=copy.deepcopy(q)
        for key in ('generator_weights','generator_zone','generator_on','generator_version','generator_settings'):old.pop(key)
        old.update(id=q['id']+'x',generator_order=[0,1,2,3,4],generator_input=[0,1])
        done=dict(copy.deepcopy(old),id=q['id']+'y',progress=1)
        g.quests+= [old,done]
        g.x,g.y=old['pos'];g.ensure_generator(old)
        self.assertEqual(old['generator_version'],balance.VERSION);self.assertNotIn('generator_order',old)
        self.assertTrue(g.quest_ready(done))


if __name__=='__main__':unittest.main()
