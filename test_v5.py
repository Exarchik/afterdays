import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import progression as p
import adventure as a
from refinement_ui import description

class RefinementTests(unittest.TestCase):
    def test_health_and_medkit(self):
        """Перевіряє сценарій «health and medkit» та очікувані результати."""
        g=r.Game(5);self.assertEqual((g.hp,g.max_hp),(25,25))
        g.xp=p.xp_for_level(5);self.assertEqual(g.max_hp,45)
        g.choose_perk('hardy');self.assertEqual(g.max_hp,55)
        g.hp=1;g.perks['medic']=3;self.assertTrue(g.use('med'));self.assertEqual(g.hp,29)
        g.hp=g.max_hp;count=g.count('med');self.assertFalse(g.use('med'));self.assertEqual(g.count('med'),count)

    def test_salvage_types_and_modules_return(self):
        """Перевіряє сценарій «salvage types and modules return» та очікувані результати."""
        g=r.Game(5);p.add_to(g.bag,p.supply('repairkit',3))
        for name in ['Пістолет «Попіл»','Куртка з пластинами','Шолом «Шукач»']:
            item=p.equipment(name);mod=p.module(index=0 if item['kind']=='weapon' else 3);item['modules']=[mod];g.bag.append(item)
            kind='parts' if item['kind']=='weapon' else 'fragments';before=g.count(kind);expected=g.salvage_yield(item)
            self.assertTrue(g.dismantle(item['id']));self.assertEqual(g.count(kind),before+expected);self.assertIn(mod,g.bag)
        self.assertEqual(p.item_weight(p.fragments(9999)),0)
        self.assertTrue(g.buys_kind(p.fragments(2),1))

    def test_crafting_atomic_and_correct_target(self):
        """Перевіряє сценарій «crafting atomic and correct target» та очікувані результати."""
        g=r.Game(10)
        for kind,fn,target in [('parts',p.parts,'weapon'),('fragments',p.fragments,'protection')]:
            p.add_to(g.bag,fn(300));before=g.count(kind)
            self.assertFalse(g.craft_module(kind,301));self.assertEqual(g.count(kind),before)
            self.assertFalse(g.craft_module(kind,-2));self.assertEqual(g.count(kind),before)
            self.assertTrue(g.craft_module(kind,150));self.assertEqual(g.count(kind),before-150)
            self.assertEqual(g.bag[-1]['target'],target);self.assertEqual(g.bag[-1]['level'],g.level)
        weights=[g.craft_odds(n) for n in (10,30,75,150)]
        self.assertTrue(all(sum(w)==100 for w in weights))
        expected=[sum(i*x for i,x in enumerate(w)) for w in weights];self.assertEqual(expected,sorted(expected))
        p.add_to(g.bag,p.parts(100));g.bag.append(dict(id='heavy',kind='food',name='heavy',rarity=0,value=1,weight=100,qty=1))
        state=g.rng.getstate();before=g.count('parts');self.assertFalse(g.craft_module('parts',10));self.assertEqual(g.rng.getstate(),state);self.assertEqual(before,g.count('parts'))

    def test_partial_repairs(self):
        """Перевіряє сценарій «partial repairs» та очікувані результати."""
        g=r.Game(3);item=g.weapon;item['durability']=10;g.money=10000
        self.assertLess(g.repair_cost(item,25),g.repair_cost(item,100))
        for t in (25,50,100):
            before=g.money;cost=g.repair_cost(item,t);self.assertTrue(g.repair(item['id'],t));self.assertEqual(item['durability'],t);self.assertEqual(g.money,before-cost)
            self.assertFalse(g.repair(item['id'],t))
        self.assertFalse(g.repair(item['id'],35))
        item['durability']=5;g.money=0;self.assertFalse(g.repair(item['id'],25));self.assertEqual(item['durability'],5)

    def test_monster_xp_scaling(self):
        """Перевіряє сценарій «monster xp scaling» та очікувані результати."""
        g=r.Game(5);weak=dict(kind=0,level=1);strong=dict(kind=9,level=1)
        self.assertGreater(g.enemy_xp(strong),g.enemy_xp(weak))
        self.assertGreater(g.enemy_xp(dict(weak,grade='rare')),g.enemy_xp(weak))
        self.assertGreater(g.enemy_xp(dict(weak,grade='mythic')),g.enemy_xp(dict(weak,grade='rare')))
        xp=g.enemy_xp(dict(weak,grade='mythic'));g.xp=p.xp_for_level(5);self.assertLess(g.enemy_xp(dict(weak,grade='mythic')),xp)
        g.xp=p.xp_for_level(30);self.assertEqual(g.enemy_xp(weak),5)

    def test_monster_grades_have_stats(self):
        """Перевіряє сценарій «monster grades have stats» та очікувані результати."""
        import monster_rules
        g=r.Game(2);seen={grade:monster_rules.make(g.rng,0,1,[1,1],grade=grade) for grade in ('normal','rare','mythic')}
        self.assertEqual(set(seen),{'normal','rare','mythic'})
        for grade in ('rare','mythic'):
            e=seen[grade];self.assertGreater(e['max_hp'],r.MONSTERS[e['kind']][1]);self.assertGreater(e['damage'],r.MONSTERS[e['kind']][2])

    def test_fog_discovery_and_save(self):
        """Перевіряє сценарій «fog discovery and save» та очікувані результати."""
        g=r.Game(1);self.assertEqual(g.known_cities,[0]);self.assertLess(len(g.explored),20)
        self.assertFalse(g.revealed(*g.cities[1]));g.reveal(*g.cities[1],2);self.assertIn(1,g.known_cities)
        old=set(g.explored);g.reveal(30,20,2);self.assertTrue(old.issubset(g.explored))
        site=g.special_sites[0];g.discover(site['id']);self.assertIn(site['city_id'],g.known_cities)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'save.json';g.save(path);loaded=r.Game.load(path);self.assertEqual(g.explored,loaded.explored);self.assertEqual(g.known_cities,loaded.known_cities)

    def test_mayor_map_reward_once(self):
        """Перевіряє сценарій «mayor map reward once» та очікувані результати."""
        g=r.Game(1);g.local_record()['value']=51
        for n in range(6):
            q=dict(id=f'q{n}',kind='hunt',city=0,status='active',title='Test',progress=1,goal=1,target_kind=None,reward=10,pos=None)
            g.quests.append(q);self.assertTrue(g.turn_in(q['id']))
            if n<5:self.assertEqual(g.known_cities,[0])
        self.assertEqual(len(g.known_cities),2);self.assertEqual(g.map_rewards,[0])
        self.assertFalse(g.turn_in('q2'));self.assertEqual(len(g.known_cities),2)

    def test_radiation_treatment_and_price(self):
        """Перевіряє сценарій «rad protection exact duration and price» та очікувані результати."""
        g=r.Game(8);p.add_to(g.bag,p.supply('rad',2));g.add_radiation(75)
        self.assertTrue(g.use('rad'));self.assertEqual(g.radiation_injury,25);self.assertEqual(g.rad_turns,0)
        self.assertTrue(g.use('rad'));self.assertEqual(g.radiation_injury,0)
        self.assertFalse(g.use('rad'))
        g.x,g.y=g.cities[0]
        for rank in (0,3,7):
            g.perks['trader']=rank;self.assertEqual(g.price(p.supply('rad'),1),2*g.price(p.supply('med'),1))
        self.assertIn('rad',{i['kind'] for i in g.stock(1)})

    def test_extra_events_filters_and_transaction(self):
        """Перевіряє сценарій «extra events filters and transaction» та очікувані результати."""
        g=r.Game(2);g.x,g.y=6,5
        for terrain in ('road','forest','ruin','waste'):
            g.world[g.y][g.x]=terrain
            for _ in range(30):
                g.make_road_event();event=g.road_event['kind'];self.assertTrue(event not in a.EXTRA_EVENTS or a.EXTRA_EVENTS[event][0]==terrain);g.resolve_event('leave')
        g.make_road_event('safe');before=copy.deepcopy(g.road_event);self.assertFalse(g.resolve_event('open'));self.assertEqual(before,g.road_event)
        p.add_to(g.bag,p.parts(10));money=g.money;self.assertTrue(g.resolve_event('open'));self.assertEqual(g.count('parts'),0);self.assertGreater(g.money,money)
        self.assertEqual(len(a.EXTRA_EVENTS),15)

    def test_preinstalled_modules_and_comparison(self):
        """Перевіряє сценарій «preinstalled modules and comparison» та очікувані результати."""
        g=r.Game(9);g.xp=p.xp_for_level(12);counts=[]
        for _ in range(1600):
            item=g.roll_item();self.assertLessEqual(item.get('level',1),g.level)
            if 'modules' in item:
                counts.append(len(item['modules']));self.assertLessEqual(len(item['modules']),item['slots'])
                self.assertTrue(all(r.compatible(item,m) for m in item['modules']))
        self.assertIn(1,counts);self.assertGreater(counts.count(0),counts.count(1))
        base=p.equipment('Пістолет «Попіл»',tier=3,level=12)
        with patch.object(p.Game,'roll_item',return_value=base),patch.object(g.rng,'random',side_effect=[1,0,0,.5,.5,.5,.5]):
            fitted=g.roll_item()
        self.assertEqual(len(fitted['modules']),2)
        item=p.equipment('Пістолет «Попіл»',tier=3);text=description(g,item);self.assertIn('[+]',text);self.assertIn('Постріл\t',text)
        item['durability']=1;self.assertIn('[-]',description(g,item))

    def test_migrate_v4_health(self):
        """Перевіряє сценарій «migrate v4 health» та очікувані результати."""
        g=r.Game(4);g.hp=50
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'save.json';g.save(path);data=json.loads(path.read_text());data['version']=4
            for key in ('explored','known_cities','map_rewards','rad_turns'):data.pop(key)
            path.write_text(json.dumps(data));loaded=r.Game.load(path);self.assertEqual(loaded.hp,13);self.assertEqual(loaded.max_hp,25)
