"""Damage shows on the arena when the projectile lands, and the result waits a second."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from tests import test_update033 as arena
from ui.adventure import Effects


def effects(g):
    app=SimpleNamespace(game=g,root=MagicMock(),dialog=None)
    fx=Effects(app)
    with patch('time.monotonic',return_value=100):fx.ingest()
    return fx


class HitSyncTests(unittest.TestCase):
    def arena(self,key='weapon_rust_assault',distance=2):
        g,w,b=arena.Update033Tests().arena(key,distance);g.pop_events();return g,w,b

    def test_damage_numbers_wait_for_their_bullet(self):
        g,w,b=self.arena();w['fire_mode']='burst';target=b['enemies'][0];before=target['hp']
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):g.shoot('0')
        fx=effects(g)
        shots=[e for e in fx.active if e['kind']=='attack'];texts=[e for e in fx.active if e.get('hit_target')=='0']
        self.assertEqual(len(shots),5);self.assertEqual(len(texts),5)
        for shot,text in zip(shots,texts):
            self.assertAlmostEqual(text['start'],shot['start']+shot['duration']*Effects.arrival(shot))
        self.assertGreater(texts[0]['start'],shots[0]['start'])
        with patch('time.monotonic',return_value=100):self.assertEqual(fx.hp_shown('0',target['hp']),before)
        with patch('time.monotonic',return_value=texts[2]['start']+.001):
            self.assertEqual(before-fx.hp_shown('0',target['hp']),sum(t['hit_amount'] for t in texts[:3]))
        with patch('time.monotonic',return_value=texts[-1]['start']+.01):self.assertEqual(fx.hp_shown('0',target['hp']),target['hp'])

    def test_killed_enemy_stays_until_the_shot_lands(self):
        g,w,b=self.arena('weapon_thunder_shotgun',1);b['enemies'][0]['hp']=1;b['enemies'][0]['max_hp']=1
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):g.shoot('0')
        self.assertNotIn('0',[e['id'] for e in b['enemies']])
        fx=effects(g);present={e['id'] for e in b['enemies']}
        landing=min(e['start'] for e in fx.active if e.get('hit_target')=='0')
        with patch('time.monotonic',return_value=100):self.assertEqual([e['id'] for e in fx.ghosts(present)],['0'])
        last=max(e['start'] for e in fx.active if e.get('hit_target')=='0')
        with patch('time.monotonic',return_value=last+.01):self.assertEqual(fx.ghosts(present),[])
        self.assertGreater(landing,100)

    def test_result_waits_a_second_after_the_last_hit(self):
        g,w,b=self.arena('weapon_thunder_shotgun',1);b['enemies']=b['enemies'][:1];b['enemies'][0]['hp']=1
        with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):g.shoot('0')
        self.assertIsNone(g.battle)
        fx=effects(g)
        last=max(e['start'] for e in fx.active if e.get('hit_target'))
        self.assertGreaterEqual(fx.until,last+1.0)
        with patch('time.monotonic',return_value=last+.5):self.assertTrue(fx.blocked)
        with patch('time.monotonic',return_value=fx.until+.01):self.assertFalse(fx.blocked)

    def test_player_health_waits_for_the_enemy_blow(self):
        g,w,b=self.arena();g.hp=500  # tough enough to survive the blow
        enemy=b['enemies'][0];enemy.update(pos=[b['pos'][0]+1,b['pos'][1]],range=1,speed=0,damage=3,attack=0,level=1)
        b['enemies']=[enemy]
        with patch.object(g.rng,'randrange',return_value=99),patch.object(g.rng,'random',return_value=.99),patch.object(g,'protection_stat',return_value=0):g.end_turn()
        fx=effects(g);hits=[e for e in fx.active if e.get('hit_target')=='player']
        self.assertIsNotNone(g.battle,'the player must survive this blow')
        self.assertEqual(len(hits),1);amount=hits[0]['hit_amount']
        with patch('time.monotonic',return_value=100):self.assertEqual(fx.hp_shown('player',g.hp),g.hp+amount)
        blow=next(e for e in fx.active if e['kind'] in ('attack','slash'))
        self.assertAlmostEqual(hits[0]['start'],blow['start']+blow['duration']*Effects.arrival(blow))
        with patch('time.monotonic',return_value=hits[0]['start']+.01):self.assertEqual(fx.hp_shown('player',g.hp),g.hp)


if __name__=='__main__':unittest.main()
