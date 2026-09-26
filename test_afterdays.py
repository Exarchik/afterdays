"""Meaningful model regression checks, runnable without a graphical display."""
import json
import tempfile
import unittest
from pathlib import Path
from afterdays import Game, equipment, module, stats, item_weight, item_value, path_to, visible


class AfterdaysTests(unittest.TestCase):
    def test_modules_roundtrip_preserves_identity_weight_and_stats(self):
        """Перевіряє сценарій «modules roundtrip preserves identity weight and stats» та очікувані результати."""
        g = Game(1)
        weapon = g.weapon
        mod = next(i for i in g.bag if i['kind'] == 'module' and i['target'] == 'weapon')
        base = stats(weapon)
        weight = g.weight
        self.assertTrue(g.install(weapon['id'], mod['id']))
        self.assertEqual(stats(weapon)['damage'], base['damage'] + 2)
        self.assertNotIn(mod, g.bag)
        self.assertEqual(g.weight, weight)
        self.assertTrue(g.uninstall(weapon['id'], mod['id']))
        self.assertEqual(stats(weapon), base)
        self.assertEqual(sum(i['id'] == mod['id'] for i in g.bag), 1)
        self.assertEqual(g.weight, weight)

    def test_module_compatibility_capacity_and_combat_lock(self):
        """Перевіряє сценарій «module compatibility capacity and combat lock» та очікувані результати."""
        g = Game(2)
        weapon = g.weapon
        armor_mod = next(i for i in g.bag if i['kind'] == 'module' and i['target'] == 'protection')
        self.assertFalse(g.install(weapon['id'], armor_mod['id']))
        for _ in range(weapon['slots']):
            m = module(index=0)
            g.bag.append(m)
            self.assertTrue(g.install(weapon['id'], m['id']))
        m = module(index=0)
        g.bag.append(m)
        self.assertFalse(g.install(weapon['id'], m['id']))
        g.start_battle()
        self.assertFalse(g.uninstall(weapon['id'], weapon['modules'][0]['id']))
        self.assertFalse(g.unequip('weapon1'))

    def test_equipment_swap_preserves_total_weight(self):
        """Перевіряє сценарій «equipment swap preserves total weight» та очікувані результати."""
        g = Game(3)
        new = equipment('Лазер «Промінь»', 4)
        self.assertTrue(g.accept(new))
        old, weight = g.weapon, g.weight
        self.assertTrue(g.equip(new['id'], 'weapon1'))
        self.assertIs(g.weapon, new)
        self.assertIn(old, g.bag)
        self.assertEqual(g.weight, weight)
        self.assertTrue(g.unequip('weapon1'))
        self.assertEqual(g.weight, weight)

    def test_buy_overweight_is_atomic(self):
        """Перевіряє сценарій «buy overweight is atomic» та очікувані результати."""
        g = Game(4)
        target = g.stock(0)[0]
        g.money = 10000
        heavy = equipment('Бронекорпус «Бастіон»')
        heavy['weight'] = g.capacity - g.weight
        g.bag.append(heavy)
        money, count = g.money, len(g.bag)
        self.assertFalse(g.buy(target['id'], 0))
        self.assertEqual(g.money, money)
        self.assertEqual(len(g.bag), count)
        self.assertIn(target, g.stock(0))

    def test_merchants_and_installed_module_value(self):
        """Перевіряє сценарій «merchants and installed module value» та очікувані результати."""
        g = Game(5)
        g.local_record()['value']=50
        armor = g.equipped['armor']
        mod = next(i for i in g.bag if i['kind'] == 'module' and i['target'] == 'protection')
        self.assertTrue(g.install(armor['id'], mod['id']))
        self.assertEqual(item_value(armor), armor['value'] + mod['value'])
        g.unequip('armor')
        self.assertFalse(g.sell(armor['id'], 1))
        money = g.money
        self.assertTrue(g.sell(armor['id'], 0))
        self.assertEqual(g.money - money, int(item_value(armor)*.5))
        self.assertIsNone(g.find(armor['id']))
        self.assertIsNone(g.find(mod['id']))

    def test_generated_enemies_always_reachable(self):
        """Перевіряє сценарій «generated enemies always reachable» та очікувані результати."""
        for seed in range(100):
            g = Game(seed)
            g.start_battle()
            b = g.battle
            walls = set(map(tuple, b['walls']))
            positions = [tuple(e['pos']) for e in b['enemies']]
            self.assertEqual(len(positions), len(set(positions)))
            for pos in positions:
                self.assertTrue(__import__('hexgrid').path_to(tuple(b['pos']), pos, b['w'], b['h'], walls))

    def test_line_of_sight_including_corners(self):
        """Перевіряє сценарій «line of sight including corners» та очікувані результати."""
        self.assertTrue(visible((0, 0), (4, 3), []))
        self.assertFalse(visible((0, 0), (4, 0), [(2, 0)]))
        self.assertFalse(visible((0, 0), (2, 2), [(1, 0)]))
        for a, b in [((0, 0), (4, 3)), ((4, 3), (1, 6)), ((0, 5), (7, 5))]:
            self.assertEqual(visible(a, b, [(2, 2)]), visible(b, a, [(2, 2)]))

    def test_blocked_shot_does_not_spend_ap(self):
        """Перевіряє сценарій «blocked shot does not spend ap» та очікувані результати."""
        g = Game(6)
        g.start_battle()
        b = g.battle
        b['pos'] = [1, 5]
        b['enemies'][0]['pos'] = [3, 5]
        b['walls'] = [[2, 5]]
        self.assertFalse(g.shoot(b['enemies'][0]['id']))
        self.assertEqual(b['ap'], 6)
        self.assertFalse(g.battle_move((2, 5)))
        self.assertEqual(b['ap'], 6)

    def test_turn_heal_switch_flee(self):
        """Перевіряє сценарій «turn heal switch flee» та очікувані результати."""
        g = Game(7)
        g.equipped['weapon2'] = equipment('Пістолет «Попіл»')
        g.start_battle()
        b = g.battle
        b['walls'] = []
        g.hp = 5
        self.assertTrue(g.use('med'))
        self.assertEqual(g.hp, 18)
        self.assertEqual(b['ap'], 4)
        self.assertTrue(g.switch())
        self.assertEqual(b['ap'], 4)
        self.assertTrue(g.battle_move((0, 5)))
        self.assertTrue(g.flee())
        self.assertIsNone(g.battle)

    def test_victory_loot_capacity_and_defeat(self):
        """Перевіряє сценарій «victory loot capacity and defeat» та очікувані результати."""
        g = Game(8)
        g.start_battle()
        money = g.money
        from unittest.mock import patch
        with patch.object(g.rng,'random',return_value=0):g.victory()
        self.assertGreater(g.money, money)
        self.assertGreaterEqual(len(g.loot), 1)
        item = g.loot[0]
        self.assertTrue(g.collect(item['id']))
        self.assertIn(item, g.bag)
        self.assertNotIn(item, g.loot)
        g.start_battle()
        g.defeat()
        self.assertEqual([g.x, g.y], g.cities[0])
        self.assertEqual(g.hp, g.max_hp)
        self.assertFalse(g.loot)
        self.assertIsNone(g.battle)

    def test_save_load_preserves_items_battle_stock_and_rng(self):
        """Перевіряє сценарій «save load preserves items battle stock and rng» та очікувані результати."""
        g = Game(9)
        stock = g.stock(2)
        mod = g.bag[0]
        g.install(g.weapon['id'], mod['id'])
        g.start_battle()
        g.battle['ap'] = 3
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'save.json'
            g.save(path)
            loaded = Game.load(path)
            loaded.save(Path(folder) / 'other.json')
            self.assertEqual(json.loads(path.read_text()), json.loads((Path(folder)/'other.json').read_text()))
        self.assertEqual(loaded.weight, g.weight)
        self.assertEqual(loaded.battle, g.battle)
        self.assertEqual(loaded.shops['0:2']['items'], stock)
        self.assertEqual(loaded.rng.random(), g.rng.random())

    def test_enemy_turn_and_stock_refresh(self):
        """Перевіряє сценарій «enemy turn and stock refresh» та очікувані результати."""
        g = Game(10)
        first = [i['id'] for i in g.stock(2)]
        self.assertEqual(first, [i['id'] for i in g.stock(2)])
        g.turn += 40
        self.assertNotEqual(first, [i['id'] for i in g.stock(2)])
        g.start_battle()
        g.battle['walls'] = []
        g.battle['enemies'] = [dict(id=0, name='test', hp=10, max_hp=10,
                                  damage=10, range=1, speed=2, pos=[4, 5], kind=0)]
        hp = g.hp
        g.end_turn()
        self.assertLess(g.hp, hp)
        self.assertEqual(g.battle['round'], 2)
        self.assertEqual(g.battle['ap'], 6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
