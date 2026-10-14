import copy
import unittest
from game.model import Game
from game import items
from ui.item_inspection import can_detach,detach,summary


class ItemInspectionTests(unittest.TestCase):
    def fixture(self):
        game=Game(13);item=game.weapon;item['modules']=[]
        mod=items.module(index='module_amplifier');item['modules'].append(mod)
        return game,item,mod

    def test_condition_first_and_summary_uses_damage_preview(self):
        from damage_preview import estimate
        game,item,_=self.fixture();rows=summary(game,item)
        self.assertEqual(rows[0][0],'Стан');self.assertEqual(rows[1][0],'Шкода пострілу')
        result=estimate(game,item)
        self.assertEqual(rows[1][1],f"{result['minimum']}–{result['maximum']}")

    def test_detach_moves_exact_module_and_recalculates_stats(self):
        game,item,mod=self.fixture();before=copy.deepcopy(mod)
        self.assertTrue(can_detach(game,item,mod));self.assertTrue(detach(game,item,mod))
        self.assertNotIn(mod,item['modules']);self.assertEqual(sum(i['id']==mod['id'] for i in game.bag),1)
        self.assertEqual(mod,before);self.assertFalse(detach(game,item,mod))

    def test_combat_quest_and_foreign_items_cannot_be_detached(self):
        for mode in ('battle','quest','foreign'):
            game,item,mod=self.fixture()
            if mode=='battle':game.battle={'ap':5}
            elif mode=='quest':item['quest_id']='test'
            else:
                item=items.equipment('weapon_ash_pistol');item['modules']=[mod]
            before=copy.deepcopy((game.bag,item))
            self.assertFalse(can_detach(game,item,mod));self.assertFalse(detach(game,item,mod))
            self.assertEqual((game.bag,item),before)

    def test_summary_all_catalog_items_and_consumables_does_not_mutate(self):
        import content
        game=Game(3)
        examples=[items.equipment(k,level=d['min_level']) for k,d in content.EQUIPMENT.items()]
        examples += [items.module(index=k) for k in content.MODULE_IDS]
        examples += [items.supply(k) for k in ('food','med','rad','repairkit','parts','credits')]
        for item in examples:
            before=copy.deepcopy(item);rng=game.rng.getstate();rows=summary(game,item)
            self.assertTrue(rows);self.assertEqual(item,before);self.assertEqual(game.rng.getstate(),rng)


if __name__=='__main__':unittest.main()
