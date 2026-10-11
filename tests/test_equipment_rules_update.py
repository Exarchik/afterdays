import random
import unittest
from unittest.mock import patch
import content
import faction_rules
import module_rules
import sprites
from game import items
from game.model import Game


class EquipmentUpdateTests(unittest.TestCase):
    def test_module_floor_updates_price_and_stats_for_every_definition(self):
        for ident,data in content.MODULE_DATA.items():
            for tier in range(5):
                item=items.module(tier,index=ident,level=4)
                actual=max(tier,data.get('min_equipment_rarity',0))
                self.assertEqual(item['rarity'],actual)
                self.assertEqual(item['stats'],module_rules.module_stats(ident,actual,item['level']))
                self.assertEqual(item['value'],round(30*(actual+1)**2*item['level']**1.3))

    def test_existing_module_upgrades_once_without_rng_changes(self):
        g=Game(5);ident=content.MODULE_IDS[0]
        item=items.module(0,index=ident);item.update(rarity=0,value=30)
        g.bag.append(item);state=g.rng.getstate()
        with patch.dict(content.MODULE_DATA[ident],min_equipment_rarity=3):
            module_rules.migrate_game(g)
            self.assertEqual(item['rarity'],3)
            self.assertEqual(item['stats'],module_rules.module_stats(ident,3,item['level']))
            before=dict(item);module_rules.migrate_game(g);self.assertEqual(item,before)
        self.assertEqual(g.rng.getstate(),state)

    def test_human_gear_spans_one_to_location_level(self):
        seen={k:set() for k in ('weapon','armor','helmet')}
        for seed in range(80):
            actor=faction_rules.make_human(random.Random(seed),'human_bandit','bandits',7,[1,1])
            for kind,item in actor['equipment'].items():
                self.assertTrue(1<=item['level']<=7)
                self.assertLessEqual(content.EQUIPMENT[item['type_id']]['min_level'],item['level'])
                seen[kind].add(item['level'])
                for mod in item['modules']:self.assertTrue(module_rules.compatible(item,mod))
        for values in seen.values():self.assertEqual(values,set(range(1,8)))

    def test_armor_and_helmet_badges_exist_at_all_rarities(self):
        for kind in ('armor','helmet'):
            for tier in range(5):
                key=sprites.weapon_badge_key(dict(kind=kind,rarity=tier))
                self.assertEqual(key,f'weapon_badge:{kind}:{tier}')
                self.assertIn(key,sprites.MANIFEST)
