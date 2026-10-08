import copy
import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
import spread048,quest_navigation,world_map
import test_update033,test_journey
from adventure_ui import Effects


class Update048Tests(unittest.TestCase):
    def arena(self,burst=False):
        g,w,b=test_update033.Update033Tests().arena('weapon_rust_assault' if burst else 'weapon_thunder_shotgun')
        w['fire_mode']='burst' if burst else 'single'
        b['enemies'][1]['pos']=[3,3]
        g.pop_events();return g,w,b

    def test_shotgun_reserves_two_or_three_and_burst_two(self):
        for burst in (False,True):
            g,w,b=self.arena(burst);target=b['enemies'][0]
            for _ in range(20):
                shots=spread048.allocate(g,target,5 if burst else 6,not burst,burst)
                self.assertEqual(len(shots),5 if burst else 6)
                self.assertIn(sum(s is not target for s in shots),(2,) if burst else (2,3))

    def test_no_secondary_all_shots_go_to_primary(self):
        for burst in (False,True):
            g,w,b=self.arena(burst);target=b['enemies'][0];b['enemies']=b['enemies'][:1]
            self.assertEqual(spread048.allocate(g,target,5 if burst else 6,not burst,burst),[target]*(5 if burst else 6))

    def test_allies_walls_range_and_rear_are_excluded(self):
        g,w,b=self.arena();other=b['enemies'][1];target=b['enemies'][0]
        other['faction']='settlers';self.assertEqual(spread048.candidates(g,target),[])
        other['faction']='bandits';other['pos']=[15,2];self.assertEqual(spread048.candidates(g,target),[])
        other['pos']=[0,2];self.assertEqual(spread048.candidates(g,target),[])
        other['pos']=[3,3]
        with patch('spread048.hexgrid.visible',return_value=False):self.assertEqual(spread048.candidates(g,target),[])

    def test_two_secondary_enemies_share_fixed_budget(self):
        g,w,b=self.arena();extra=copy.deepcopy(b['enemies'][1]);extra.update(id='2',pos=[3,1]);b['enemies'].append(extra)
        for _ in range(10):
            shots=spread048.allocate(g,b['enemies'][0],6,True)
            counts=Counter(s['id'] for s in shots)
            self.assertEqual(set(counts),{'0','1','2'});self.assertEqual(sum(counts.values()),6)

    def test_actual_shots_cost_and_delivery(self):
        for burst in (False,True):
            g,w,b=self.arena(burst);ammo=g.count('ammo',w['ammo_type']);ap=b['ap']
            with patch.object(g.rng,'randrange',return_value=0),patch.object(g,'_projectile_damage') as damage:
                self.assertTrue(g.shoot('0'))
            self.assertEqual(len(damage.call_args_list),5 if burst else 6)
            diverted=sum(call.args[0]['id']!='0' for call in damage.call_args_list)
            self.assertIn(diverted,(2,) if burst else (2,3))
            self.assertEqual(ammo-g.count('ammo',w['ammo_type']),5 if burst else 1)
            self.assertEqual(ap-b['ap'],g.shot_ap())

    def test_pellets_simultaneous_burst_sequential(self):
        for burst in (False,True):
            g,w,b=self.arena(burst)
            with patch.object(g.rng,'randrange',return_value=99):g.shoot('0')
            app=SimpleNamespace(game=g,root=MagicMock(),dialog=None)
            fx=Effects(app)
            with patch('adventure_ui.time.monotonic',return_value=100):fx.ingest()
            shots=[e for e in fx.active if e['kind']=='attack']
            self.assertEqual(len(shots),5 if burst else 6)
            starts=[e['start'] for e in shots]
            if burst:self.assertTrue(all(b>a for a,b in zip(starts,starts[1:])))
            else:self.assertEqual(len(set(starts)),1)

    def test_plan_waits_for_move_button(self):
        g,app,route=test_journey.RouteTests().controller();app.route_button=MagicMock()
        with patch('route_ui.time.monotonic',return_value=0):self.assertTrue(route.set_target((3,0)))
        with patch('route_ui.time.monotonic',return_value=5):route.advance()
        self.assertFalse(route.running);self.assertEqual((g.x,g.turn),(0,0))
        self.assertEqual(app.route_button.config.call_args.kwargs['style'],'RouteReady048.TButton')
        with patch('route_ui.time.monotonic',return_value=5):route.toggle()
        with patch('route_ui.time.monotonic',return_value=6):route.advance()
        self.assertEqual((g.x,g.turn),(1,1))

    def test_quest_destination_and_hidden_target(self):
        game=SimpleNamespace(quest_ready=lambda q:q.get('ready',False),quest_return_pos=lambda q:[5,5],metro_step=lambda q:{'pos':[9,9]})
        q={'status':'active','pos':[10,10],'cache_pos':[11,10]}
        self.assertEqual(quest_navigation.destination(game,q),[10,10])
        q['metro_chain']={};self.assertEqual(quest_navigation.destination(game,q),[10,10])
        q['metro_chain']={'index':0};self.assertEqual(quest_navigation.destination(game,q),[9,9])
        q['ready']=True;self.assertEqual(quest_navigation.destination(game,q),[5,5])
        q['status']='done';self.assertIsNone(quest_navigation.destination(game,q))

    def test_edge_arrows_fit_and_point_to_all_sides(self):
        v=world_map.layout(800,500,112,32,(55,16));origin=(55,16);ox,oy=v.point(origin)
        for target in ((0,16),(111,16),(55,0),(55,31)):
            points=quest_navigation.edge_arrow(v,target,origin);tx,ty=v.point(target)
            self.assertTrue(all(0<=n<=800 for n in points[::2]));self.assertTrue(all(0<=n<=500 for n in points[1::2]))
            self.assertGreater((points[0]-ox)*(tx-ox)+(points[1]-oy)*(ty-oy),0)
