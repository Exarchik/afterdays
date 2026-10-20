"""Shotgun cone: pellets take the first hostile body on their way, fall off with range, push back."""
import math,random,unittest
from unittest.mock import patch
from game.systems import shotgun as sg
from tests import test_update033 as arena


class ShotgunTests(unittest.TestCase):
    def arena(self,distance=1):
        g,w,b=arena.Update033Tests().arena('weapon_thunder_shotgun',distance)
        g.pop_events();return g,w,b

    def test_geometry_is_unit_hex_plane(self):
        for d in ((1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)):
            self.assertAlmostEqual(math.hypot(*sg.point(d)),1)
        self.assertEqual(tuple(round(v,6) for v in sg.axial(*sg.point((3,-2)))),(3,-2))

    def test_dead_centre_shell_goes_into_adjacent_target(self):
        g,w,b=self.arena(1);target=b['enemies'][0];hp=target['hp']
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):
            self.assertTrue(g.shoot('0'))
        self.assertEqual(g._last_shell['hits'],{'0':6})
        shots=[e for e in g.pop_events() if e['kind']=='attack']
        self.assertEqual(len(shots),6);self.assertTrue(all(e['fire_mode']=='pellet' for e in shots))
        self.assertLess(target['hp'],hp)

    def test_front_body_shields_the_one_behind(self):
        g,w,b=self.arena(1);front,rear=b['enemies']   # rear stands right behind front
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):
            self.assertTrue(g.shoot(rear['id']))
        self.assertEqual(g._last_shell['hits'],{front['id']:6})
        self.assertEqual(rear['hp'],10000)

    def test_spread_splits_pellets_between_neighbours(self):
        g,w,b=self.arena(2);target,other=b['enemies'];other['pos']=[target['pos'][0],target['pos'][1]+1]
        result=sg.expected(g,target,94,3,w)
        self.assertIn(other['id'],result)
        self.assertGreater(result[target['id']][0],result[other['id']][0])
        self.assertLessEqual(sum(n for n,_ in result.values()),sg.PELLETS+1e-9)

    def test_walls_stop_pellets(self):
        g,w,b=self.arena(3);b['walls']=[[2,2]]
        angle=sg.aim(b['pos'],b['enemies'][0]['pos'])
        enemy,end,distance,wall=sg.trace(g,angle,3)
        self.assertIsNone(enemy);self.assertTrue(wall);self.assertLess(distance,1.6)

    def test_pellets_ignore_non_hostile_units(self):
        g,w,b=self.arena(1);front,rear=b['enemies'];front['faction']='settlers'
        self.assertFalse(g.hostile_to_player(front))
        angle=sg.aim(b['pos'],rear['pos'])
        self.assertIs(sg.trace(g,angle,3)[0],rear)

    def test_falloff_and_accuracy(self):
        w={}
        self.assertEqual(sg.falloff(w,1.5,4),1);self.assertEqual(sg.falloff(w,2,4),1)
        self.assertAlmostEqual(sg.falloff(w,4,4),.4);self.assertAlmostEqual(sg.falloff(w,3,4),.7)
        self.assertAlmostEqual(sg.falloff(dict(falloff=60),9,4),.6)
        self.assertLess(sg.spread(None,w,95),sg.spread(None,w,50))
        self.assertLess(sg.spread(None,dict(spread=10),80),sg.spread(None,w,80))

    def test_far_pellets_deal_less(self):
        near=self.arena(1);far=self.arena(3)
        for g,w,b in (near,far):
            b['enemies']=b['enemies'][:1]
            with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99),patch.object(g.rng,'randint',return_value=0):
                g.shoot('0')
        self.assertGreater(10000-near[2]['enemies'][0]['hp'],10000-far[2]['enemies'][0]['hp'])

    def test_point_blank_knockback(self):
        g,w,b=self.arena(1);b['enemies']=b['enemies'][:1];target=b['enemies'][0];start=list(target['pos'])
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):g.shoot('0')
        self.assertEqual(target['pos'],[2*start[0]-b['pos'][0],2*start[1]-b['pos'][1]])
        self.assertTrue(any(e['kind']=='move' and e.get('entity')=='0' for e in g.pop_events()))
        # A wall behind holds the target in place.
        g,w,b=self.arena(1);b['enemies']=b['enemies'][:1];target=b['enemies'][0];start=list(target['pos'])
        b['walls']=[[2*start[0]-b['pos'][0],2*start[1]-b['pos'][1]]]
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):g.shoot('0')
        self.assertEqual(target['pos'],start)

    def test_preview_uses_its_own_rng(self):
        g,w,b=self.arena(2);state=g.rng.getstate()
        first=sg.expected(g,b['enemies'][0],90,3,w);second=sg.expected(g,b['enemies'][0],90,3,w)
        self.assertEqual(first,second);self.assertEqual(g.rng.getstate(),state)
        cone=sg.cone(g,b['enemies'][0],90,3,w)
        self.assertEqual(len(cone),12);self.assertAlmostEqual(cone[0][0],b['pos'][0]);self.assertAlmostEqual(cone[0][1],b['pos'][1])

    def test_misfire_throws_the_shell_wide(self):
        g,w,b=self.arena(2)
        wide=sg.fan(g,b['enemies'][0],94,random.Random(1),3,w,wild=True)
        self.assertEqual(len(wide),sg.PELLETS)


if __name__=='__main__':unittest.main()
