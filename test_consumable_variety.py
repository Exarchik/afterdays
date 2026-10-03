import copy,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import content
import progression as p
import event_catalog as catalog
import event_runtime
from test_event_catalog import custom


class VarietyTests(unittest.TestCase):
    def test_shop_variety_stable_saved_and_restocks(self):
        g=r.Game(5);stock=g.stock(1)
        self.assertTrue(any(i.get('type_id','').startswith('item_custom_') and i['kind']=='food' for i in stock))
        self.assertTrue(any(i.get('type_id','').startswith('item_custom_') and i['kind']=='med' for i in stock))
        baseline=copy.deepcopy(stock);state=g.rng.getstate()
        self.assertEqual(g.stock(1),baseline);self.assertEqual(g.rng.getstate(),state)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);g=r.Game.load(path)
            self.assertEqual(g.stock(1),baseline)
        g.turn+=41
        self.assertNotEqual(g.stock(1),baseline)

    def test_traveler_variety(self):
        g=r.Game(5);p.Game.spawn_traveler(g)
        items=g.stock(3)
        self.assertTrue(any(i.get('type_id','').startswith('item_custom_') for i in items))
        before=copy.deepcopy(items);self.assertEqual(g.stock(3),before)

    def test_food_damage_manual_auto_and_death(self):
        g=r.Game(5);g.bag=[p.supply('item_custom_002',2)];g.survival['hunger']=0
        self.assertFalse(g.eat(automatic=True))
        g.hp=g.max_hp;before=g.hp
        self.assertTrue(g.use(g.bag[0]['id']))
        self.assertEqual(g.hp,before-math.ceil(g.max_hp*.1));self.assertEqual(g.hunger,5)
        self.assertEqual(g.bag[0]['qty'],1)
        g.hp=1;g.money=15
        self.assertTrue(g.use(g.bag[0]['id']));self.assertEqual(g.carried_money,0)
        self.assertGreater(g.hp,0);self.assertFalse(any(i['kind']=='food' for i in g.bag))

    def test_specific_random_and_legacy_rewards(self):
        g=r.Game(5)
        for kind,ident in [('food','item_custom_002'),('med','item_custom_006')]:
            item=event_runtime.item(g,dict(kind=kind,item_id=ident,amount=3),1)
            self.assertEqual((item['type_id'],item['qty']),(ident,3))
            self.assertEqual(event_runtime.item(g,dict(kind=kind,amount=1),1)['type_id'],'item_'+kind)
            pool=[k for k,v in content.CONSUMABLES.items() if v['kind']==kind]
            with patch.object(g.rng,'choice',side_effect=lambda items:items[-1]) as choice:
                item=event_runtime.item(g,dict(kind=kind,item_id='random',amount=4),1)
                self.assertEqual(choice.call_args.args[0],pool)
                self.assertEqual((item['type_id'],item['qty']),(pool[-1],4))

    def test_selection_validation_and_targeted_loss(self):
        spec=custom();effect=dict(kind='food',item_id='item_custom_002',amount=2)
        spec['cache']=[effect]
        self.assertEqual(catalog.validate(dict(version=1,events=[spec])),[])
        effect['item_id']='item_custom_006'
        self.assertTrue(catalog.validate(dict(version=1,events=[spec])))
        effect['item_id']='random';self.assertEqual(catalog.validate(dict(version=1,events=[spec])),[])
        g=r.Game(5);g.bag=[p.supply('food',3),p.supply('item_custom_002',2)]
        event_runtime.apply(g,dict(kind='food',item_id='item_custom_002',amount=-1),spec)
        self.assertEqual([i['qty'] for i in g.bag],[3,1])

    def test_random_safe_roll_survives_failed_attempt_and_save(self):
        g=r.Game(5);spec=custom();spec['cache']=[dict(kind='med',item_id='random',amount=2)]
        g.begin_event_cache(spec);cache=copy.deepcopy(g.road_cache())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);g=r.Game.load(path)
            self.assertEqual(g.road_cache()['contents'],cache['contents'])
            g.begin_event_cache(spec);self.assertEqual(g.road_cache()['contents'],cache['contents'])
