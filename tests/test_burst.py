"""Automatic burst: five bullets in a widening fan; the first hostile body on the way takes each."""
import random,unittest
from unittest.mock import patch
from game.systems import burst,shotgun
from tests import test_update033 as arena


class BurstTests(unittest.TestCase):
    def arena(self,distance=2):
        g,w,b=arena.Update033Tests().arena('weapon_rust_assault',distance)
        w['fire_mode']='burst';g.pop_events();return g,w,b

    def test_recoil_widens_each_bullet_and_accuracy_narrows(self):
        widths=[burst.half(i,80) for i in range(burst.BULLETS)]
        self.assertEqual(widths,sorted(widths));self.assertLess(widths[0],widths[-1])
        self.assertLess(burst.half(4,95),burst.half(4,50))

    def test_dead_centre_burst_hits_the_target_five_times(self):
        g,w,b=self.arena();target=b['enemies'][0]
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):
            self.assertTrue(g.shoot('0'))
        self.assertEqual(g._last_burst['hits'],{'0':5})
        shots=[e for e in g.pop_events() if e['kind']=='attack']
        self.assertEqual([e['projectile'] for e in shots],[0,1,2,3,4])
        self.assertTrue(all(e['fire_mode']=='burst' and e['damage_type']=='kinetic' and e['hit'] for e in shots))
        self.assertLess(target['hp'],10000)

    def test_front_body_takes_the_burst(self):
        g,w,b=self.arena(1);front,rear=b['enemies']
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):
            self.assertTrue(g.shoot(rear['id']))
        self.assertEqual(g._last_burst['hits'],{front['id']:5});self.assertEqual(rear['hp'],10000)

    def test_tail_of_the_burst_can_reach_a_neighbour(self):
        g,w,b=self.arena(2);target,other=b['enemies'];other['pos']=[target['pos'][0],target['pos'][1]+1]
        _,_,chance=g.shot_info(target)
        result=burst.expected(g,target,chance,6)
        self.assertGreater(result[target['id']],result.get(other['id'],0))
        self.assertIn(other['id'],result)
        self.assertLessEqual(sum(result.values()),burst.BULLETS+1e-9)

    def test_misses_are_real_flight_ends_and_walls_stop(self):
        g,w,b=self.arena(3);b['walls']=[[2,2]]
        with patch.object(g.rng,'random',return_value=.5):g.shoot('0')
        shots=[e for e in g.pop_events() if e['kind']=='attack']
        self.assertTrue(all(e['wall'] and not e['hit'] for e in shots))
        self.assertEqual(b['enemies'][0]['hp'],10000)

    def test_preview_has_its_own_rng_and_cone(self):
        g,w,b=self.arena();state=g.rng.getstate()
        self.assertEqual(burst.expected(g,b['enemies'][0],80,6),burst.expected(g,b['enemies'][0],80,6))
        self.assertEqual(g.rng.getstate(),state)
        self.assertEqual(len(burst.cone(g,b['enemies'][0],80,6)),10)
        self.assertEqual(len(burst.volley(g,b['enemies'][0],80,random.Random(1),6,wild=True)),burst.BULLETS)

    def test_single_shot_still_rolls_the_hit_chance(self):
        g,w,b=self.arena();w['fire_mode']='single'
        with patch.object(g.rng,'randrange',return_value=99):self.assertTrue(g.shoot('0'))
        self.assertEqual(b['enemies'][0]['hp'],10000)
        self.assertFalse(hasattr(g,'_last_burst'))


if __name__=='__main__':unittest.main()
