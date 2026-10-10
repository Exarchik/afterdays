import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import game.model as r
import game.items as p
import game.progression as progression
import game.systems.consumables as consumable_rules
import entity_catalog
from game.systems.credits import credit_item


class Update046Tests(unittest.TestCase):
    def test_xp_scale_and_actual_reward(self):
        for delta,expected in [(0,100),(1,100),(2,80),(3,60),(4,25),(5,1),(9,1)]:
            g=r.Game(5);g.xp=progression.xp_for_level(12)
            q=dict(id='test',kind='supplies',status='active',city=0,title='Test',level=12-delta,xp_reward=100,reward=0,food_need=0,med_need=0)
            g.quests=[q];g.x,g.y=g.cities[0]
            self.assertEqual(g.quest_xp(q),expected)
            before=g.xp
            self.assertTrue(g.turn_in(q['id']));self.assertEqual(g.xp-before,expected)
            self.assertEqual(q['xp_reward'],100);self.assertFalse(g.turn_in(q['id']))

    def test_credit_stash_spending_and_death(self):
        g=r.Game(5);g.money=100
        coins=next(i for i in g.bag if i['kind']=='credits')
        self.assertTrue(g.stash_transfer(coins['id'],'deposit',60))
        self.assertEqual((g.carried_money,g.stored_money,g.money),(40,60,100))
        g.money-=55
        self.assertEqual((g.carried_money,g.stored_money),(0,45))
        g.money+=20;g.defeat()
        self.assertEqual((g.carried_money,g.stored_money,g.money),(0,45,45))
        self.assertFalse(g.buys_kind(credit_item(1),0))

    def test_credit_save_migration_and_empty_wallet(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g=r.Game(5);g.money=120;g.save(path)
            data=json.loads(path.read_text(encoding='utf-8'))
            data['bag']=[i for i in data['bag'] if i['kind']!='credits']
            path.write_text(json.dumps(data),encoding='utf-8')
            loaded=r.Game.load(path);self.assertEqual(loaded.carried_money,120)
            loaded.save(path);loaded=r.Game.load(path);self.assertEqual(loaded.carried_money,120)
            loaded.money=0;loaded.save(path);self.assertEqual(r.Game.load(path).money,0)

    def test_trade_draws_stash_after_inventory(self):
        g=r.Game(5);g.money=10000
        coins=next(i for i in g.bag if i['kind']=='credits')
        self.assertTrue(g.stash_transfer(coins['id'],'deposit',9999))
        g.x,g.y=g.cities[2]
        stock=g.stock(0)
        item=next(i for i in stock if i['kind']=='ammo')
        price=g.price(item,0,True)
        self.assertTrue(g.buy(item['id'],0,1))
        self.assertEqual(g.carried_money,0);self.assertEqual(g.stored_money,10000-price)

    def test_selected_repair_kit_uses_configured_amount(self):
        g=r.Game(5);g.weapon['durability']=40
        kit=p.supply('repairkit');kit['repair']=12;g.bag.append(kit)
        self.assertTrue(g.repair_with_kit(g.weapon['id'],kit['id']))
        self.assertEqual(g.weapon['durability'],52)
        self.assertNotIn(kit,g.bag)

    def test_special_stash_threshold(self):
        g=r.Game(5);site=g.special_sites[0];g.discover(site['id']);g.x,g.y=site['pos']
        record=g.record_at(site['pos']);record['value']=49;self.assertFalse(g.can_access_stash)
        record['value']=50;self.assertTrue(g.can_access_stash)
        coins=next(i for i in g.bag if i['kind']=='credits')
        self.assertTrue(g.stash_transfer(coins['id'],'deposit',1))
        g.battle={'ap':3};self.assertFalse(g.can_access_stash)

    def test_rest_satiety(self):
        g=r.Game(5);g.money=100;g.survival['hunger']=12
        self.assertTrue(g.rest());self.assertEqual(g.hunger,17)
        self.assertTrue(g.rest());self.assertEqual(g.hunger,20)

    def test_combined_item_and_ap(self):
        g=r.Game(5);g.hp=1;g.survival['hunger']=0
        item=p.supply('med');item.update(heal=7,heal_percent=0,satiety=4,ap_cost=1)
        g.bag.append(item);g.battle={'ap':1,'pos':[0,0]}
        self.assertTrue(g.can_use_consumable(item['id']));self.assertTrue(g.use(item['id']))
        self.assertEqual((g.hp,g.hunger,g.battle['ap']),(8,4,0))
        self.assertNotIn(item,g.bag)

    def test_editor_validation_and_custom_stack(self):
        store=entity_catalog.Store();self.assertEqual(store.validate(),[])
        a=p.supply('food');b=p.supply('food');b['satiety']=3
        bag=[];p.add_to(bag,a);p.add_to(bag,b);self.assertEqual(len(bag),2)
        data=copy.deepcopy(store.data['consumables']);data['item_food']['heal']=-1
        self.assertTrue(consumable_rules.validate(data,store.art))

    def test_reveal_once_and_event_notice(self):
        import event_runtime
        g=r.Game(5);g.pop_events();g.explored=[]
        event_runtime.apply(g,dict(kind='reveal',amount=2),dict(title='Test'))
        events=g.pop_events();self.assertEqual(sum(e['kind']=='reveal' for e in events),1)
        self.assertTrue(any('Відкриття мапи' in e.get('text','') for e in events))
        g.reveal(g.x,g.y,2);self.assertFalse(g.pop_events())
