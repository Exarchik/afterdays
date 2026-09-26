from tests_fixtures.quest_offer import offer_for
"""v0.4 regression coverage: world topology, feedback, storage and event lifecycle."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import afterdays as r
import progression as p
import adventure as a


class AdventureTests(unittest.TestCase):
    def combat(self,kind=0):
        """Готує або імітує операцію «combat» для перевірок AdventureTests."""
        g=r.Game(41);g.start_battle();g.pop_events();g.battle['walls']=[]
        e=dict(id=0,name=r.MONSTERS[kind][0],kind=kind,hp=100,max_hp=100,damage=9,range=1,
               speed=1,pos=[3,5],armor=0,resists=copy.deepcopy(a.RESISTANCES[kind]),level=1)
        g.battle['enemies']=[e];return g,e

    def test_feedback_valid_shot_and_insufficient_ap(self):
        """Перевіряє сценарій «feedback valid shot and insufficient ap» та очікувані результати."""
        g,e=self.combat();g.battle['ap']=0
        before=g.count('ammo','pistol')
        self.assertFalse(g.shoot(0));events=g.pop_events()
        self.assertIn('Мало ОД',[n['text'] for n in events])
        self.assertEqual(g.count('ammo','pistol'),before)
        g.battle['ap']=6;g.rng.seed(1);self.assertTrue(g.shoot(0))
        events=g.pop_events();self.assertTrue(any(n['kind']=='attack' for n in events))
        self.assertTrue(any(n['text'].startswith('−') for n in events))

    def test_miss_and_corpse_last_attack_snapshot(self):
        """Перевіряє сценарій «miss and corpse last attack snapshot» та очікувані результати."""
        g,e=self.combat();g.rng.seed(23)  # This seed need not force a miss: use a bounded random stub.
        class Miss:
            # Готує або імітує операцію «randrange» для перевірок Miss.
            def randrange(self,*a):return 99
            # Готує або імітує операцію «randint» для перевірок Miss.
            def randint(self,a,b):return a
        g.rng=Miss();self.assertTrue(g.shoot(0))
        self.assertIn('Промах',[n['text'] for n in g.pop_events()])
        g,e=self.combat();e['hp']=1;g.rng.seed(1)
        self.assertTrue(g.shoot(0));self.assertIsNone(g.battle)
        self.assertEqual(g._last_battle['corpses'],[dict(pos=[3,5],kind=0,type_id='monster_rodent',grade='normal')])
        self.assertTrue(any(n['text'].endswith(' XP') for n in g.pop_events()))

    def test_enemy_attack_emits_trace_and_player_damage(self):
        """Перевіряє сценарій «enemy attack emits trace and player damage» та очікувані результати."""
        g,e=self.combat();e['pos']=[2,5]
        hp=g.hp;g.end_turn();self.assertLess(g.hp,hp)
        events=g.pop_events()
        self.assertTrue(any(n['kind']=='slash' and n['source']==[2,5] for n in events))
        self.assertTrue(any(n['entity']=='player' and n['text'].startswith('−') for n in events))

    def test_elemental_weakness_and_resistance_change_damage(self):
        """Перевіряє сценарій «elemental weakness and resistance change damage» та очікувані результати."""
        def shot(resistance):
            g,e=self.combat();e['resists']={'kinetic':resistance};g.rng.seed(1)
            g.shoot(0);return 100-e['hp']
        neutral=shot(0)
        self.assertGreater(shot(-60),neutral)
        self.assertLess(shot(60),neutral)
        self.assertIn('вразливість',a.resistance_text(dict(kind=7)))
        self.assertEqual(a.damage_type(dict(name='Плазмомет «Сонце»')),'thermal')
        self.assertEqual(a.damage_type(dict(name='Лазер «Промінь»')),'energy')

    def test_free_switch_and_ap_perks(self):
        """Перевіряє сценарій «free switch and ap perks» та очікувані результати."""
        g,e=self.combat();g.equipped['weapon2']=p.equipment('Пістолет «Попіл»')
        g.battle['ap']=0;self.assertTrue(g.switch());self.assertEqual(g.battle['ap'],0)
        g.xp=p.xp_for_level(2);self.assertTrue(g.choose_perk('tactician'))
        self.assertEqual(g.max_ap,7);self.assertEqual(g.battle['max_ap'],7)
        g.end_turn();self.assertEqual(g.battle['ap'],7)
        g.xp=p.xp_for_level(4);g.choose_perk('adrenaline');g.hp=5;e['pos']=[14,10];e['speed']=0
        g.end_turn();self.assertEqual(g.battle['ap'],8)

    def test_food_xp_and_quest_world_feedback(self):
        """Перевіряє сценарій «food xp and quest world feedback» та очікувані результати."""
        g=r.Game(4);g.hp=20;g.use('food')
        self.assertTrue(any(n['scene']=='world' and 'HP' in n['text'] for n in g.pop_events()))
        g.gain_xp(20);self.assertIn('+20 XP',[n['text'] for n in g.pop_events()])
        offer=offer_for(g,'scout');g.accept_quest(offer['id'])
        q=g.quests[-1];g.x,g.y=q['pos'];g._visit_objectives()
        self.assertIn('Розвідка: 1/9',[n['text'] for n in g.pop_events()])

    def test_road_event_required_items_atomic_and_persistent(self):
        """Перевіряє сценарій «road event required items atomic and persistent» та очікувані результати."""
        g=r.Game(5);g.x=6;g.make_road_event('wounded');g.consume('med',g.count('med'))
        self.assertFalse(g.resolve_event('help'));self.assertIsNotNone(g.road_event)
        old=(g.x,g.y,g.turn);self.assertFalse(g.step(1,0));self.assertEqual((g.x,g.y,g.turn),old)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'event.json';g.save(path);loaded=r.Game.load(path)
            self.assertEqual(loaded.road_event,g.road_event)
            self.assertTrue(loaded.resolve_event('leave'));self.assertIsNone(loaded.road_event)
        p.add_to(g.bag,p.supply('med'))
        xp=g.xp;self.assertTrue(g.resolve_event('help'));self.assertEqual(g.xp,xp+20)
        self.assertEqual(g.count('med'),0)

    def test_every_road_event_has_a_resolvable_choice(self):
        """Перевіряє сценарій «every road event has a resolvable choice» та очікувані результати."""
        for key,_,_,choices in a.ROAD_EVENTS:
            g=r.Game(6);g.make_road_event(key)
            self.assertTrue(g.resolve_event('leave'))
            self.assertIsNone(g.road_event)

    def test_mayor_refresh_does_not_replace_active_quests(self):
        """Перевіряє сценарій «mayor refresh does not replace active quests» та очікувані результати."""
        g=r.Game(7);offers=g.mayor_offers();ids={q['id'] for q in offers}
        g.accept_quest(offers[0]['id']);active=copy.deepcopy(g.quests[0])
        g.turn=99;self.assertEqual(ids-{active['id']},{q['id'] for q in g.mayor_offers()})
        g.turn=100;self.assertTrue(ids.isdisjoint({q['id'] for q in g.mayor_offers()}))
        self.assertEqual(g.quests[0],active)

    def test_shared_stash_stacks_and_withdrawal_are_atomic(self):
        """Перевіряє сценарій «shared stash stacks and withdrawal are atomic» та очікувані результати."""
        g=r.Game(8);food=next(i for i in g.bag if i['kind']=='food')
        self.assertTrue(g.stash_transfer(food['id'],'deposit',2));self.assertEqual(g.count('food'),1)
        g.x,g.y=g.cities[1];stack=g.stash[0]
        self.assertTrue(g.stash_transfer(stack['id'],'withdraw',1));self.assertEqual(g.count('food'),2)
        heavy=p.equipment('Куртка з пластинами');heavy['weight']=g.capacity-g.weight;g.bag.append(heavy)
        before=copy.deepcopy((g.stash,g.bag))
        self.assertFalse(g.stash_transfer(stack['id'],'withdraw',1))
        self.assertEqual((g.stash,g.bag),before)
        g.x,g.y=6,5;self.assertFalse(g.stash_transfer(stack['id'],'withdraw',1))

    def test_special_sites_only_appear_when_discovered_and_paths_avoid_blocks(self):
        """Перевіряє сценарій «special sites only appear when discovered and paths avoid blocks» та очікувані результати."""
        g=r.Game(9);self.assertEqual(len(g.cities),12);self.assertFalse(g.trails)
        for site in g.special_sites:
            self.assertNotEqual(g.world[site['pos'][1]][site['pos'][0]],'site')
        site=g.special_sites[0];self.assertTrue(g.discover(site['id']));self.assertFalse(g.discover(site['id']))
        self.assertEqual(len(g.cities),13);self.assertTrue(g.trails)
        self.assertTrue(all(g.passable(*p) for p in g.trails))
        self.assertEqual(g.city_name(12),site['name'])
        g.x,g.y=site['pos'];self.assertEqual(g.current_site['npc'],site['npc'])
        if site['role']=='quest':
            offers=g.mayor_offers();self.assertTrue(offers);self.assertIn(site['name'],g.quest_text(offers[0]))
        merchant=next(s for s in g.special_sites if s['role']=='merchant')
        g.discover(merchant['id']);g.x,g.y=merchant['pos']
        stock=g.stock(0);self.assertTrue(any(i['rarity']>=3 for i in stock));self.assertFalse(g.available_merchant(1))

    def test_world_obstacles_do_not_disconnect_cities_or_quest_targets(self):
        """Перевіряє сценарій «world obstacles do not disconnect cities or quest targets» та очікувані результати."""
        for seed in range(12):
            g=r.Game(seed);reachable=g.reachable_world((5,5))
            self.assertTrue(all(tuple(c) in reachable for c in g.cities))
            self.assertTrue(any(t=='water' for row in g.world for t in row))
            self.assertTrue(any(t=='cliff' for row in g.world for t in row))
            for offer in g.mayor_offers():
                if offer['kind'] in ('retrieve','scout','purge'):
                    g.accept_quest(offer['id']);self.assertIn(tuple(g.quests[-1]['pos']),reachable)

    def test_blocked_step_has_no_cost_and_radiation_hurts(self):
        """Перевіряє сценарій «blocked step has no cost and radiation hurts» та очікувані результати."""
        g=r.Game(10);g.world[5][6]='water';before=(g.x,g.y,g.turn,g.hp,g.count('food'))
        self.assertFalse(g.step(1,0));self.assertEqual((g.x,g.y,g.turn,g.hp,g.count('food')),before)
        g.world[5][6]='waste';g.radiation['6,5']=3;hp=g.hp
        self.assertTrue(g.step(1,0));self.assertEqual(g.hp,hp-3)
        self.assertTrue(any(n['text']=='−3 HP' for n in g.pop_events()))

    def test_save_preserves_stash_sites_paths_and_corpses_not_ephemeral_effects(self):
        """Перевіряє сценарій «save preserves stash sites paths and corpses not ephemeral effects» та очікувані результати."""
        g,e=self.combat();g.battle['corpses']=[dict(pos=[8,5],kind=1)]
        g.stash=[p.parts(15)];g.discover(g.special_sites[0]['id'])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);loaded=r.Game.load(path)
            self.assertEqual(loaded.stash,g.stash)
            self.assertEqual(loaded.trails,g.trails)
            self.assertEqual(loaded.special_sites,g.special_sites)
            self.assertEqual(loaded.battle['corpses'],g.battle['corpses'])
            self.assertEqual(loaded.pop_events(),[])


if __name__=='__main__':unittest.main(verbosity=2)
