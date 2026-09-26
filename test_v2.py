from tests_fixtures.quest_offer import offer_for
"""Regression tests for expansion, quest lifecycle and drag/drop transactions."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from afterdays import Game, LegacyGame, GEAR, MODULES, MONSTERS, equipment, module, item_value, stats


class ExpansionTests(unittest.TestCase):
    def accept(self, g, kind):
        """Перевіряє можливість отримання предмета і додає його до сумки."""
        q = offer_for(g,kind)
        self.assertTrue(g.accept_quest(q['id']))
        return g.quests[-1]

    def test_content_and_guaranteed_city_supplies(self):
        """Перевіряє сценарій «content and guaranteed city supplies» та очікувані результати."""
        self.assertEqual((len(GEAR), len(MODULES), len(MONSTERS)), (30, 29, 12))
        g = Game(0)
        self.assertEqual(len(g.cities), 12)
        profiles = set()
        for n, p in enumerate(g.cities):
            g.x,g.y=p
            profiles.add(tuple(g.city_merchants[n]))
            self.assertTrue(g.available_merchant(1))
            self.assertEqual({i['kind'] for i in g.stock(1)}, {'med', 'food', 'rad'})
            for m in (0, 2):
                if m not in g.city_merchants[n]:
                    self.assertEqual(g.stock(m), [])
        self.assertGreater(len(profiles), 1)

    def test_traveler_discount_identity_and_expiry(self):
        """Перевіряє сценарій «traveler discount identity and expiry» та очікувані результати."""
        g = Game(1)
        g.x,g.y=6,5
        # Test the regular merchant explicitly, not a seed-dependent hunter/cartographer.
        from progression import Game as ProgressionGame
        ProgressionGame.spawn_traveler(g)
        stock = g.stock(3)
        self.assertEqual(len([i for i in stock if i['kind'] in ('weapon','armor','helmet','module')]),1)
        self.assertTrue({'food','med'}.issubset({i['kind'] for i in stock}))
        item = next(i for i in stock if i['kind'] in ('weapon','armor','helmet','module'))
        self.assertEqual(g.price(item,3), round(round(item_value(item)*.5)*1.3))
        g.money=10000
        credits=g.money
        self.assertTrue(g.buy(item['id'],3))
        self.assertEqual(credits-g.money, round(round(item_value(item)*.5)*1.3))
        self.assertNotIn(item,g.stock(3))
        g.step(1,0)
        self.assertFalse(g.available_merchant(3))

    def test_retrieval_spawn_collection_and_single_reward(self):
        """Перевіряє сценарій «retrieval spawn collection and single reward» та очікувані результати."""
        g=Game(2)
        self.assertFalse(any(i['kind']=='quest' for i in g.bag))
        self.assertFalse(any(i['kind']=='quest' for m in range(3) for i in g.stock(m)))
        q=self.accept(g,'retrieve')
        self.assertNotIn(q['pos'],g.cities)
        self.assertEqual(q['status'],'active')
        g.x,g.y=q['relic_pos']
        g.searched.append(q['pos'])
        self.assertTrue(g.search())  # Prior exploration cannot block a spawned objective.
        item=next(i for i in g.bag if i.get('quest_id')==q['id'])
        self.assertTrue(g.quest_ready(q))
        g.x,g.y=g.cities[q['city']]
        for m in (0,1,2):
            self.assertFalse(g.sell(item['id'],m))
        before=g.money
        self.assertTrue(g.turn_in(q['id']))
        self.assertEqual(g.money,before+q['reward'])
        self.assertFalse(any(i.get('quest_id')==q['id'] for i in g.bag))
        self.assertFalse(g.turn_in(q['id']))
        self.assertEqual(g.money,before+q['reward'])

    def test_hunt_counts_only_after_acceptance_and_correct_type(self):
        """Перевіряє сценарій «hunt counts only after acceptance and correct type» та очікувані результати."""
        g=Game(3)
        g._kill_objectives(0)
        q=self.accept(g,'hunt')
        self.assertEqual(q['progress'],0)
        q['target_kind']=2;q['level']=4
        g._kill_objectives(0)
        self.assertEqual(q['progress'],0)
        for _ in range(q['goal']+2):
            g._kill_objectives(2)
        self.assertEqual(q['progress'],q['goal'])
        self.assertTrue(g.quest_ready(q))

    def test_scout_and_unique_markers(self):
        """Перевіряє сценарій «scout and unique markers» та очікувані результати."""
        g=Game(4)
        a=self.accept(g,'retrieve')
        b=self.accept(g,'scout')
        self.assertNotEqual(a['pos'],b['pos'])
        g.x,g.y=b['pos']
        g._visit_objectives()
        self.assertFalse(g.quest_ready(b))
        x,y,xx,yy=b['area']
        for cy in range(y,yy+1):
            for cx in range(x,xx+1):g.x,g.y=cx,cy;g._visit_objectives()
        self.assertTrue(g.quest_ready(b))
        self.assertFalse(g.turn_in(b['id']))  # Must return to originating city.

    def test_purge_requires_its_own_victory_and_can_retry(self):
        """Перевіряє сценарій «purge requires its own victory and can retry» та очікувані результати."""
        g=Game(5)
        q=self.accept(g,'purge')
        g.start_battle()
        g.victory()
        self.assertFalse(g.quest_ready(q))
        g.x,g.y=q['pos']
        self.assertTrue(g.search())
        self.assertEqual(g.quest_battle,q['id'])
        g.battle['pos']=g.battle['exit'][:]
        self.assertTrue(g.flee())
        self.assertFalse(g.quest_ready(q))
        self.assertIsNone(g.quest_battle)
        self.assertTrue(g.search())
        g.battle['enemies']=[]
        g.victory()
        self.assertFalse(g.quest_ready(q))
        g.battle['pos']=g.battle['exit'][:]
        self.assertTrue(g.search())
        self.assertTrue(g.quest_ready(q))

    def test_supply_delivery_is_atomic_and_consumes_exactly(self):
        """Перевіряє сценарій «supply delivery is atomic and consumes exactly» та очікувані результати."""
        g=Game(6)
        q=self.accept(g,'supplies')
        q['unique']=False  # This regression exercises the ordinary supply contract.
        g.bag=[i for i in g.bag if i['kind']!='med']
        before=list(g.bag)
        self.assertFalse(g.turn_in(q['id']))
        self.assertEqual(g.bag,before)
        from afterdays import supply
        g.bag.extend([supply('med'),supply('med')])
        self.assertTrue(g.turn_in(q['id']))
        self.assertEqual(sum(i['kind'] in ('med','food') for i in g.bag),0)

    def test_capacity_module_removal_and_replacement_rollback(self):
        """Перевіряє сценарій «capacity module removal and replacement rollback» та очікувані результати."""
        g=Game(7)
        armor=g.equipped['armor'];armor['rarity']=4
        capacity=module(4,index=18)
        g.bag.append(capacity)
        self.assertTrue(g.install(armor['id'],capacity['id']))
        heavy=equipment('Кулемет «Молот»')
        heavy['weight']=g.capacity-g.weight
        g.bag.append(heavy)
        weight=g.weight
        self.assertFalse(g.uninstall(armor['id'],capacity['id']))
        self.assertEqual(g.weight,weight)
        self.assertTrue(any(m['id']==capacity['id'] for m in g.find(armor['id'])['modules']))
        # Replacement uses an existing module, so total carried weight stays unchanged.
        defense=next(i for i in g.bag if i['kind']=='module' and i['target']=='protection')
        self.assertFalse(g.put_module(armor['id'],defense['id'],0))
        self.assertEqual(g.weight,weight)
        self.assertTrue(any(i['id']==defense['id'] for i in g.bag))
        self.assertFalse(g.unequip('armor'))
        self.assertIsNotNone(g.equipped['armor'])

    def test_module_drop_replaces_without_duplication(self):
        """Перевіряє сценарій «module drop replaces without duplication» та очікувані результати."""
        g=Game(8);g.weapon['rarity']=3
        a=module(1,index=0)
        b=module(3,index=6)
        g.bag.extend([a,b])
        g.install(g.weapon['id'],a['id'])
        before=g.weight
        self.assertTrue(g.put_module(g.weapon['id'],b['id'],0))
        self.assertEqual(g.weight,before)
        self.assertIn(a,g.bag)
        self.assertNotIn(b,g.bag)
        self.assertEqual(g.weapon['modules'][0]['id'],b['id'])
        self.assertEqual(stats(g.weapon)['attack'],14)

    def test_quest_item_survives_defeat_and_save_roundtrip(self):
        """Перевіряє сценарій «quest item survives defeat and save roundtrip» та очікувані результати."""
        g=Game(9)
        q=self.accept(g,'retrieve')
        g.x,g.y=q['relic_pos']
        g.search()
        g.defeat()
        self.assertTrue(g.quest_ready(q))
        g.spawn_traveler()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'save.json'
            g.save(p)
            loaded=Game.load(p)
            self.assertEqual(loaded.quests,g.quests)
            self.assertEqual(loaded.traveler,g.traveler)
            self.assertTrue(loaded.quest_ready(loaded.quests[0]))

    def test_v1_migration_preserves_items_and_adds_cities(self):
        """Перевіряє сценарій «v1 migration preserves items and adds cities» та очікувані результати."""
        old=LegacyGame(10)
        old.money=733
        old.start_battle()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'old.json'
            old.save(p)
            new=Game.load(p)
            self.assertEqual(new.money,733)
            self.assertEqual(new.equipped,old.equipped)
            self.assertEqual(new.battle['pos'],old.battle['pos'])
            self.assertEqual(new.battle['ap'],old.battle['ap'])
            self.assertEqual(new.battle['walls'],old.battle['walls'])
            self.assertEqual(len(new.cities),12)
            self.assertEqual(len(new.city_merchants),12)
            new.save(p)
            self.assertEqual(json.loads(p.read_text())['version'],18)

    def test_equipment_mouse_drop_routes(self):
        """Перевіряє сценарій «equipment mouse drop routes» та очікувані результати."""
        from visuals import EquipmentPanel
        class Widget:
            # Ініціалізує об’єкт, його початковий стан і потрібні залежності.
            def __init__(self,x,y,w,h): self.coords=x,y,w,h
            # Готує або імітує операцію «winfo rootx» для перевірок Widget.
            def winfo_rootx(self): return self.coords[0]
            # Готує або імітує операцію «winfo rooty» для перевірок Widget.
            def winfo_rooty(self): return self.coords[1]
            # Готує або імітує операцію «winfo width» для перевірок Widget.
            def winfo_width(self): return self.coords[2]
            # Готує або імітує операцію «winfo height» для перевірок Widget.
            def winfo_height(self): return self.coords[3]
        g=Game(11)
        item=equipment('Лазер «Промінь»')
        g.bag.append(item)
        panel=SimpleNamespace(app=SimpleNamespace(game=g,act=lambda f:f(),refresh=lambda:None),
                              paper=Widget(0,0,380,220), grid=SimpleNamespace(canvas=Widget(0,240,380,180)),
                              slots={'weapon1':(8,65,110,154)})
        EquipmentPanel.drop(panel,dict(item=item,slot=None),50,100)
        self.assertEqual(g.weapon['id'],item['id'])
        EquipmentPanel.drop(panel,dict(item=item,slot='weapon1'),50,300)
        self.assertIsNone(g.weapon)
        self.assertIn(item,g.bag)


if __name__=='__main__':
    unittest.main(verbosity=2)
