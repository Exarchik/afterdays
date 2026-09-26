from tests_fixtures.quest_offer import offer_for
"""Behavioral regressions for v0.3, including transactional stack trading."""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import afterdays as r
import progression as p


class ProgressionTests(unittest.TestCase):
    def test_drops_and_all_merchants_never_exceed_player_level(self):
        """Перевіряє сценарій «drops and all merchants never exceed player level» та очікувані результати."""
        for level in (1,2,3,6,10,15):
            g=r.Game(level);g.xp=p.xp_for_level(level)
            generated=[g.roll_item() for _ in range(80)]
            for m in (0,1,2): generated+=g.stock(m)
            g.spawn_traveler();generated+=g.stock(3)
            self.assertTrue(all(i.get('level',1)<=level for i in generated))
            for i in generated:
                if i['kind'] in ('weapon','armor','helmet'):
                    self.assertLessEqual(p.GEAR_MIN_LEVEL[i['name']],i['level'])
        self.assertIsNone(r.Game(0).equipped['weapon2'])

    def test_higher_level_item_can_be_collected_but_not_equipped(self):
        """Перевіряє сценарій «higher level item can be collected but not equipped» та очікувані результати."""
        g=r.Game(0)
        item=p.equipment('Пістолет «Попіл»',level=5)
        g.loot.append(item)
        self.assertTrue(g.collect(item['id']))
        self.assertNotIn(item,g.loot)
        self.assertIn(item,g.bag)
        self.assertFalse(g.equip(item['id'],'weapon1'))

    def test_distance_controls_danger(self):
        """Перевіряє сценарій «distance controls danger» та очікувані результати."""
        g=r.Game(1)
        g.x,g.y=5,5;a=g.region_level
        g.y=30;self.assertGreater(g.region_level,a)
        g.x=44;self.assertGreater(g.region_level,a)
        g.start_battle()
        for e in g.battle['enemies']:
            base=r.MONSTERS[e['kind']]
            self.assertLessEqual(e['level'],g.region_level)
            self.assertEqual(e['level'],e['base_level']-int(e.get('weak',False)))
            self.assertGreaterEqual(e['hp'],base[1])
            self.assertGreaterEqual(e['damage'],base[2])

    def test_perk_choices_every_two_levels_are_persistent(self):
        """Перевіряє сценарій «perk choices every two levels are persistent» та очікувані результати."""
        g=r.Game(2)
        self.assertEqual(g.pending_perks,0)
        g.xp=p.xp_for_level(2);self.assertEqual(g.pending_perks,1)
        g.xp=p.xp_for_level(3);self.assertEqual(g.pending_perks,1)
        cap=g.capacity
        self.assertTrue(g.choose_perk('carrier'))
        self.assertEqual(g.capacity,cap+5)
        self.assertFalse(g.choose_perk('carrier'))
        g.xp=p.xp_for_level(7);self.assertEqual(g.pending_perks,2)
        self.assertTrue(g.choose_perk('carrier'))
        self.assertTrue(g.choose_perk('medic'))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'save.json';g.save(path);loaded=r.Game.load(path)
            self.assertEqual(loaded.perks,g.perks)
            self.assertEqual(loaded.pending_perks,0)

    def test_food_med_ammo_stack_and_consume_one(self):
        """Перевіряє сценарій «food med ammo stack and consume one» та очікувані результати."""
        g=r.Game(3)
        before=g.count('med')
        self.assertTrue(g.accept(p.supply('med',3)))
        self.assertEqual(g.count('med'),before+3)
        self.assertEqual(sum(i['kind']=='med' for i in g.bag),1)
        g.hp=1;self.assertTrue(g.use('med'))
        self.assertEqual(g.count('med'),before+2)
        food=g.count('food');g.travel_steps=7
        g.step(0,1)
        self.assertEqual(g.count('food'),food-1)

    def test_stack_buy_sell_is_atomic_and_quantity_based(self):
        """Перевіряє сценарій «stack buy sell is atomic and quantity based» та очікувані результати."""
        g=r.Game(4);g.money=10000
        item=next(i for i in g.stock(0) if i['kind']=='ammo' and i['ammo_type']=='pistol')
        stockqty=item['qty'];bagqty=g.count('ammo','pistol');gold=g.money;weight=g.weight
        cost=g.price(item,0)*10
        self.assertTrue(g.buy(item['id'],0,10))
        self.assertEqual(item['qty'],stockqty-10)
        self.assertEqual(g.count('ammo','pistol'),bagqty+10)
        self.assertEqual(g.money,gold-cost)
        self.assertAlmostEqual(g.weight,weight+.12,places=2)
        stack=next(i for i in g.bag if i['kind']=='ammo')
        price=g.price(stack,0,False)*7
        gold=g.money
        self.assertTrue(g.sell(stack['id'],0,7))
        self.assertEqual(g.money,gold+price)
        self.assertEqual(g.count('ammo','pistol'),bagqty+3)
        snapshot=copy.deepcopy((g.money,g.bag,g.stock(0)))
        self.assertFalse(g.buy(item['id'],0,100000))
        self.assertEqual((g.money,g.bag,g.stock(0)),snapshot)

    def test_buy_overweight_or_insufficient_money_leaves_both_stacks(self):
        """Перевіряє сценарій «buy overweight or insufficient money leaves both stacks» та очікувані результати."""
        g=r.Game(5)
        item=next(i for i in g.stock(0) if i['kind']=='ammo' and i['ammo_type']=='heavy')
        g.money=0;snapshot=copy.deepcopy((g.bag,g.stock(0)))
        self.assertFalse(g.buy(item['id'],0,10))
        self.assertEqual((g.bag,g.stock(0)),snapshot)
        g.money=100000
        heavy=p.equipment('Куртка з пластинами');heavy['weight']=g.capacity-g.weight;g.bag.append(heavy)
        snapshot=copy.deepcopy((g.money,g.bag,g.stock(0)))
        self.assertFalse(g.buy(item['id'],0,1))
        self.assertEqual((g.money,g.bag,g.stock(0)),snapshot)

    def test_ammunition_consumed_only_on_valid_shot(self):
        """Перевіряє сценарій «ammunition consumed only on valid shot» та очікувані результати."""
        g=r.Game(6);g.start_battle();b=g.battle
        b['walls']=[];e=b['enemies'][0];e['pos']=[3,5];e['hp']=1000
        ammo=g.count('ammo','pistol');dur=g.weapon['durability']
        self.assertTrue(g.shoot(e['id']))
        self.assertEqual(g.count('ammo','pistol'),ammo-1)
        self.assertLess(g.weapon['durability'],dur)
        b['walls']=[[2,5]];before=(b['ap'],g.count('ammo','pistol'),g.weapon['durability'])
        self.assertFalse(g.shoot(e['id']))
        self.assertEqual((b['ap'],g.count('ammo','pistol'),g.weapon['durability']),before)
        b['walls']=[];g.consume('ammo',g.count('ammo','pistol'),'pistol')
        self.assertFalse(g.shoot(e['id']))
        self.assertEqual(b['ap'],before[0])

    def test_broken_weapon_and_worn_armor(self):
        """Перевіряє сценарій «broken weapon and worn armor» та очікувані результати."""
        g=r.Game(7);g.weapon['durability']=0;g.start_battle()
        self.assertFalse(g.shoot(g.battle['enemies'][0]['id']))
        self.assertEqual(g.battle['ap'],6)
        g.battle['walls']=[]
        g.battle['enemies']=[dict(id=0,name='Гризун',kind=0,hp=30,max_hp=30,damage=9,range=1,speed=2,pos=[2,5])]
        armor=g.equipped['armor'];dur=armor['durability']
        g.end_turn();self.assertLess(armor['durability'],dur)
        armor['durability']=0;self.assertEqual(p.stats(armor)['defense'],0)

    def test_dismantle_returns_mods_and_weightless_lower_value_parts(self):
        """Перевіряє сценарій «dismantle returns mods and weightless lower value parts» та очікувані результати."""
        g=r.Game(8);weapon=g.weapon
        mod=g.bag[0];g.install(weapon['id'],mod['id'])
        g.unequip('weapon1');before=g.weight
        qty=g.salvage_yield(weapon)
        self.assertTrue(g.dismantle(weapon['id']))
        self.assertIsNone(g.find(weapon['id']))
        self.assertIsNotNone(g.find(mod['id']))
        self.assertEqual(g.count('parts'),qty)
        self.assertLess(g.weight,before)
        stack=next(i for i in g.bag if i['kind']=='parts')
        self.assertEqual(p.item_weight(stack),0)
        self.assertLess(p.item_value(stack),weapon['value'])
        other=p.equipment('Куртка з пластинами');g.bag.append(other);g.dismantle(other['id'])
        self.assertEqual(sum(i['kind']=='parts' for i in g.bag),1)

    def test_low_condition_refused_and_technician_repairs(self):
        """Перевіряє сценарій «low condition refused and technician repairs» та очікувані результати."""
        g=r.Game(9);item=g.weapon;g.unequip('weapon1');item['durability']=15
        for m in (0,1,2):self.assertFalse(g.sell(item['id'],m))
        cost=g.repair_cost(item);self.assertGreater(cost,0)
        g.money=cost-1;self.assertFalse(g.repair(item['id']));self.assertEqual(item['durability'],15)
        g.money=cost;self.assertTrue(g.repair(item['id']));self.assertEqual(item['durability'],100)
        self.assertEqual(g.money,0);self.assertTrue(g.sell(item['id'],0))
        g.x,g.y=g.cities[1];self.assertNotIn(1,g.technicians)
        armor=g.equipped['armor'];armor['durability']=80;g.money=10000
        self.assertFalse(g.repair(armor['id']))

    def test_fence_often_has_worn_gear_and_rare_quest_rewards(self):
        """Перевіряє сценарій «fence often has worn gear and rare quest rewards» та очікувані результати."""
        damaged=total=0
        for seed in range(15):
            g=r.Game(seed)
            for chest in g.stock(2):
                if chest['kind']!='sealed':continue
                i=chest['contents']
                if 'durability' in i:
                    total+=1;damaged+=i['durability']<=30
        self.assertGreater(damaged/total,.6)
        g=r.Game(10);offers=g.mayor_offers()
        unique=offer_for(g,'retrieve',unique=True)
        normal=offer_for(g,'hunt')
        self.assertGreater(unique['reward'],normal['reward'])
        self.assertTrue(g.accept_quest(unique['id']))
        q=g.quests[-1];g.x,g.y=q['relic_pos'];g.search();g.x,g.y=g.cities[0]
        xp=g.xp;self.assertTrue(g.turn_in(q['id']));self.assertEqual(g.xp,xp+80)

    def test_progressive_prices_and_biome_arenas(self):
        """Перевіряє сценарій «progressive prices and biome arenas» та очікувані результати."""
        prices=[p.equipment('Пістолет «Попіл»',level=lv)['value'] for lv in (1,2,3,4)]
        increments=[b-a for a,b in zip(prices,prices[1:])]
        self.assertEqual(increments,sorted(increments))
        self.assertGreater(prices[-1],prices[0]*4)
        for biome in ('road','forest','ruin','waste'):
            g=r.Game(11);g.x,g.y=6,6;g.world[6][6]=biome;g.start_battle();b=g.battle
            self.assertEqual(b['biome'],biome)
            walls=set(map(tuple,b['walls']))
            for e in b['enemies']:self.assertTrue(r.path_to(tuple(b['pos']),tuple(e['pos']),15,11,walls))
            if biome=='road':self.assertTrue(all(not 4<=y<=6 for x,y in walls))

    def test_iso_coordinate_roundtrip(self):
        """Перевіряє сценарій «iso coordinate roundtrip» та очікувані результати."""
        from advanced_ui import iso_cell
        app=SimpleNamespace(iso=dict(u=23,ox=350,oy=50,sprites=[]))
        for x in range(15):
            for y in range(11):
                import hexgrid
                px,py=hexgrid.center((x,y),23,350,50);e=SimpleNamespace(x=px,y=py)
                self.assertEqual(iso_cell(app,e),(x,y))

    def test_partial_loot_stack_pickup_fits_capacity(self):
        """Перевіряє сценарій «partial loot stack pickup fits capacity» та очікувані результати."""
        g=r.Game(12)
        filler=p.equipment('Куртка з пластинами');filler['weight']=g.capacity-g.weight-.8;g.bag.append(filler)
        item=p.supply('med',8);g.loot.append(item)
        before=g.count('med')
        self.assertTrue(g.collect(item['id']))
        self.assertEqual(g.count('med'),before+2)
        self.assertEqual(item['qty'],6)
        self.assertLessEqual(g.weight,g.capacity)


if __name__=='__main__':unittest.main(verbosity=2)
