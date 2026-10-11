import json
import math
import tempfile
import unittest
from pathlib import Path

from game.model import Game
from game import items


class ProvisionsTests(unittest.TestCase):
    def setUp(self):
        self.g = Game(5)
        self.g.bag = [items.supply('food', 2), items.supply('food'), items.supply('food')]
        self.g.survival['hunger'] = 0

    def test_bag_is_never_automatically_eaten_but_manual_use_works(self):
        self.assertFalse(self.g.eat(automatic=True))
        self.assertTrue(self.g.use(self.g.bag[0]['id']))

    def test_lower_empty_slot_compacts_and_top_stack_finishes_first(self):
        g = self.g
        first, second = g.bag[:2]
        self.assertTrue(g.pack_provision(first['id'], 2))
        self.assertTrue(g.pack_provision(second['id'], 2))
        self.assertEqual(g.provisions, [first, second])
        self.assertTrue(g.eat(automatic=True))
        self.assertEqual(first['qty'], 1)
        g.survival['hunger'] = 0
        self.assertTrue(g.eat(automatic=True))
        self.assertEqual(g.provisions, [second])

    def test_transfer_reorder_replace_merge_and_weight(self):
        g = self.g
        original = g.weight
        ids = [i['id'] for i in g.bag]
        for ident in ids:self.assertTrue(g.pack_provision(ident))
        self.assertEqual(g.weight, original)
        self.assertTrue(g.pack_provision(ids[2], 0))
        self.assertEqual([i['id'] for i in g.provisions], [ids[2],ids[0],ids[1]])
        self.assertTrue(g.unpack_provision(ids[0]))
        self.assertEqual(g.weight, original)
        self.assertTrue(g.pack_provision(ids[0], 0))
        self.assertEqual(g.provisions[0]['qty'], 3)
        extra=items.supply('food');extra['satiety']=7;g.bag.append(extra)
        self.assertTrue(g.pack_provision(extra['id'],0))
        self.assertEqual(g.provisions[0]['id'],extra['id'])
        self.assertEqual(g.bag[0]['qty'],3)

    def test_invalid_food_and_combat_changes_rejected(self):
        g=self.g
        med=items.supply('med');g.bag.append(med)
        self.assertFalse(g.pack_provision(med['id']))
        self.assertFalse(g.pack_provision(g.bag[0]['id'],3))
        g.battle={'ap':6}
        self.assertFalse(g.pack_provision(g.bag[0]['id']))

    def test_single_piece_split_merge_and_replace_preserve_food(self):
        g=self.g;food=g.bag[0];food['qty']=6;weight=g.weight
        self.assertTrue(g.pack_provision(food['id'],2,qty=1))
        self.assertEqual(food['qty'],5)
        self.assertEqual(g.provisions[0]['qty'],1)
        self.assertNotEqual(food['id'],g.provisions[0]['id'])
        self.assertTrue(g.pack_provision(food['id'],0,qty=1))
        self.assertEqual(food['qty'],4)
        self.assertEqual(g.provisions[0]['qty'],2)
        other=items.supply('food',3);other['satiety']=7;g.bag.append(other)
        weight=g.weight
        self.assertTrue(g.pack_provision(other['id'],0,qty=1))
        self.assertEqual(other['qty'],2)
        self.assertEqual(g.provisions[0]['qty'],1)
        self.assertEqual(food['qty'],6)
        self.assertEqual(g.weight,weight)

    def test_single_piece_last_item_moves_without_duplicate(self):
        g=self.g;food=g.bag[1]
        self.assertTrue(g.pack_provision(food['id'],2,qty=1))
        self.assertNotIn(food,g.bag)
        self.assertEqual(g.provisions,[food])

    def test_negative_food_effect_and_death_follow_carried_food_rules(self):
        g=self.g;food=g.bag[0];food['damage_percent']=10
        g.pack_provision(food['id']);before=g.hp
        self.assertTrue(g.eat(automatic=True))
        self.assertEqual(g.hp,before-math.ceil(g.max_hp*.1))
        g.defeat()
        self.assertEqual(g.provisions,[])
        self.assertTrue(any(i['id']==food['id'] for i in g.graves[-1]['items']))

    def test_save_roundtrip_and_old_save_empty_queue(self):
        g=self.g;g.pack_provision(g.bag[0]['id'])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path)
            restored=Game.load(path)
            self.assertEqual(restored.provisions,g.provisions)
            self.assertEqual(restored.weight,g.weight)
            data=json.loads(path.read_text(encoding='utf-8'))
            data.pop('provisions');path.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(Game.load(path).provisions,[])


if __name__=='__main__':unittest.main()
