import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import progression as p
import economy
from reputation import buy_factor,sell_factor,reward_factor

class ReputationTests(unittest.TestCase):
    def game(self,rep=0):
        """Готує або імітує операцію «game» для перевірок ReputationTests."""
        g=r.Game(4);g.local_record()['value']=rep;return g

    def test_gradient(self):
        """Перевіряє сценарій «gradient» та очікувані результати."""
        for rep,b,s,q in [(0,1.3,.5,.7),(50,1,1,1),(100,.8,1.25,2)]:
            self.assertAlmostEqual(buy_factor(rep),b)
            self.assertAlmostEqual(sell_factor(rep),s)
            self.assertAlmostEqual(reward_factor(rep),q)

    def test_local_turnover_and_cap(self):
        """Перевіряє сценарій «local turnover and cap» та очікувані результати."""
        g=self.game();g.add_reputation(turnover=49);self.assertEqual(g.reputation(),0)
        g.add_reputation(turnover=52);self.assertEqual(g.reputation(),2);self.assertEqual(g.local_record()['turnover'],1)
        g.x,g.y=g.cities[1];self.assertEqual(g.reputation(),0)
        g.add_reputation(200);self.assertEqual(g.reputation(),100)
        site=g.special_sites[0];g.discover(site['id']);g.x,g.y=site['pos'];g.xp=__import__('progression').xp_for_level(g.region_level);before=g.reputation();g.add_reputation(7);self.assertEqual(g.reputation(),min(100,before+7))
        self.assertEqual(g.reputation(0),9)

    def test_all_prices_no_resale_profit(self):
        """Перевіряє сценарій «all prices no resale profit» та очікувані результати."""
        g=self.game();items=[p.equipment(level=5),p.module(4,level=5),p.supply('med'),p.supply('rad'),p.supply('food')]
        items += [p.ammunition(k) for k in p.AMMO]+[economy.trophy(i) for i in range(12)]
        for rep in (0,25,49,50,75,99,100):
            g.local_record()['value']=rep
            for rank in (0,1,3,6):
                g.perks['trader']=rank
                for merchant in range(5):
                    for item in items:
                        self.assertLess(g.price(item,merchant,False),g.price(item,merchant,True))

    def test_completed_transactions_only(self):
        """Перевіряє сценарій «completed transactions only» та очікувані результати."""
        g=self.game();g.money=100000;item=next(i for i in g.stock(0) if i['kind']=='ammo')
        price=g.price(item,0)*30
        self.assertTrue(g.buy(item['id'],0,30));self.assertEqual(g.reputation(),price//50)
        before=dict(g.local_record());self.assertFalse(g.buy('missing',0));self.assertEqual(g.local_record(),before)
        owned=next(i for i in g.bag if i['kind']=='ammo' and i['ammo_type']==item['ammo_type'])
        old=g.local_record()['turnover']+50*g.reputation();sell=g.price(owned,0,False)
        self.assertTrue(g.sell(owned['id'],0));self.assertEqual(g.local_record()['turnover']+50*g.reputation(),old+sell)

    def test_board_limits_and_stability(self):
        """Перевіряє сценарій «board limits and stability» та очікувані результати."""
        for rep,count,elites in [(0,2,0),(25,3,0),(50,4,1),(75,5,2),(100,5,2)]:
            g=self.game(rep);offers=g.mayor_offers()
            self.assertEqual(len(offers),count)
            self.assertLessEqual(sum(bool(q.get('unique')) for q in offers),elites)
            snapshot=json.dumps(offers,sort_keys=True);self.assertEqual(snapshot,json.dumps(g.mayor_offers(),sort_keys=True))
            ids={q['id'] for q in offers};g.turn+=100;self.assertFalse(ids & {q['id'] for q in g.mayor_offers()})

    def test_rewards_freeze_and_rep_once(self):
        """Перевіряє сценарій «rewards freeze and rep once» та очікувані результати."""
        g=self.game(50);offer=g.mayor_offers()[0]
        self.assertTrue(g.accept_quest(offer['id']));q=g.quests[-1];reward=q['reward']
        g.add_reputation(10);g.mayor_offers();self.assertEqual(q['reward'],reward)
        # Isolate turn-in behavior from each quest's objective implementation.
        q.update(kind='hunt',progress=1,goal=1,unique=False)
        self.assertTrue(g.turn_in(q['id']));self.assertEqual(g.reputation(),64)
        self.assertFalse(g.turn_in(q['id']));self.assertEqual(g.reputation(),64)
        q2=dict(q,id='elite',status='active',unique=True);g.quests.append(q2)
        self.assertTrue(g.turn_in('elite'));self.assertEqual(g.reputation(),72)

    def test_stock_unlock_and_no_refill(self):
        """Перевіряє сценарій «stock unlock and no refill» та очікувані результати."""
        g=self.game();items=g.stock(0);gear=[i for i in items if i['kind'] in ('weapon','armor','helmet','module')];n=len(gear)
        removed=gear[0];items.remove(removed);self.assertNotIn(removed,g.stock(0))
        g.add_reputation(100);more=g.stock(0);self.assertGreater(len([i for i in more if i['kind'] in ('weapon','armor','helmet','module')]),n)
        self.assertNotIn(removed,more)
        self.assertTrue(any(i['kind']=='ammo' for i in more))

    def test_hunter_and_repairs(self):
        """Перевіряє сценарій «hunter and repairs» та очікувані результати."""
        g=self.game(49);self.assertEqual(g.stock(4),[])
        g.weapon['durability']=0;cost=g.repair_cost(g.weapon)
        g.add_reputation(1);self.assertTrue(g.stock(4));self.assertEqual(g.repair_cost(g.weapon),(cost+1)//2)
        item=g.stock(4)[0];g.money=10000;self.assertTrue(g.buy(item['id'],4))

    def test_thanks_notification_rewards_once(self):
        """Перевіряє сценарій «thanks notification rewards once» та очікувані результати."""
        g=self.game(75);g.check_thanks();due=g.reputation_state['thanks_due'];self.assertTrue(60<=due-g.turn<=100)
        g.turn=due;g.check_thanks();q=g.quests[-1];self.assertEqual(q['kind'],'thanks');self.assertTrue(g._reputation_notice)
        g.turn=g.reputation_state['thanks_due'];g.check_thanks();self.assertEqual(sum(t['kind']=='thanks' for t in g.quests),1)
        g.x,g.y=g.cities[1];self.assertFalse(g.turn_in(q['id']));g.x,g.y=g.cities[0]
        before={i['id'] for i in g.bag+g.stash};money=g.money
        with patch.object(g.rng,'random',return_value=0):self.assertTrue(g.turn_in(q['id']))
        self.assertEqual(g.money,money+q['reward']);self.assertFalse(g.turn_in(q['id']))
        gifts=[i for i in g.bag+g.stash if i['id'] not in before and i['kind'] in ('weapon','armor','helmet','module')]
        self.assertTrue(gifts);self.assertGreaterEqual(gifts[0]['rarity'],1);self.assertEqual(gifts[0]['level'],g.level)

    def test_save_load_and_old_save(self):
        """Перевіряє сценарій «save load and old save» та очікувані результати."""
        g=self.game(75);g.add_reputation(turnover=37);offers=g.mayor_offers();g.stock(0);g.check_thanks()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
            self.assertEqual(g.reputation_state,h.reputation_state);self.assertEqual(g.shops,h.shops)
            self.assertEqual([q['id'] for q in offers],[q['id'] for q in h.mayor_offers()])
            data=json.loads(path.read_text());data['version']=12;data.pop('reputation_state');path.write_text(json.dumps(data))
            old=r.Game.load(path);self.assertEqual(old.reputation(),0);self.assertEqual(old.money,g.money)
        fixture=Path(__file__).parent/'tests_fixtures/save_v0151.json'
        self.assertEqual(r.Game.load(fixture).reputation(),0)

    def test_buy_then_sell_after_reputation_gain(self):
        """Перевіряє сценарій «buy then sell after reputation gain» та очікувані результати."""
        for rep in (0,49,50,99,100):
            g=self.game(rep);g.money=10000000
            item=next(i for i in g.stock(0) if i['kind']=='module')
            initial=g.money
            self.assertTrue(g.buy(item['id'],0));self.assertTrue(g.sell(item['id'],0))
            self.assertLess(g.money,initial)

    def test_metro_exception_and_special_quest_giver(self):
        """Перевіряє сценарій «metro exception and special quest giver» та очікувані результати."""
        g=self.game();g.x,g.y=g.cities[2];g.xp=__import__('progression').xp_for_level(g.region_level)
        offers=g.mayor_offers();self.assertEqual(len(offers),2)
        metro=next(q for q in offers if q.get('metro_city')==2)
        self.assertTrue(metro['unique']);self.assertTrue(g.accept_quest(metro['id']))
        site=next(s for s in g.special_sites if s['role']=='quest');g.discover(site['id']);g.x,g.y=site['pos'];g.xp=__import__('progression').xp_for_level(g.region_level)
        offers=g.mayor_offers();self.assertEqual(len(offers),2);self.assertFalse(any(q['unique'] for q in offers))
        g.add_reputation(100);self.assertEqual(g.reputation(),100);self.assertEqual(g.reputation(0),100 if __import__('math').dist(site['pos'],g.cities[0])<=10 else 0)
