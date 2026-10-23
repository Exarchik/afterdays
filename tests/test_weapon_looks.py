"""Weapon attack animations chosen in the editor: data field, events, enemy shots, drawing hooks."""
import unittest

import content
import entity_catalog
from game.systems import adventure,attack_looks
from ui import projectiles


class WeaponLookTests(unittest.TestCase):
    def setUp(self):
        self.saved=dict(adventure.WEAPON_LOOK)

    def tearDown(self):
        adventure.WEAPON_LOOK.clear();adventure.WEAPON_LOOK.update(self.saved)

    def test_editor_offers_every_drawable_look(self):
        choices=entity_catalog.PROJECTILES
        self.assertEqual(choices[''],'За типом шкоди')
        self.assertEqual(set(choices)-{''},set(projectiles.ARRIVE)|set(projectiles.LOOKS))
        self.assertIn(('projectile','Анімація атаки',choices),entity_catalog.FIELDS['weapon'])

    def test_validation_accepts_missing_and_known_looks_only(self):
        ident='weapon_ray_laser';data=dict(content.EQUIPMENT[ident]);data.pop('projectile',None)
        texts={'name':'Лазер','description':''};art={data['sprite_id']}
        self.assertEqual(entity_catalog.validate_definition('weapon',ident,data,texts,art),[])
        for look in ('railgun','laser_bolt','plasma_red','heavy','thermal'):
            self.assertEqual(entity_catalog.validate_definition('weapon',ident,dict(data,projectile=look),texts,art),[])
        self.assertTrue(entity_catalog.validate_definition('weapon',ident,dict(data,projectile='rocket'),texts,art))

    def test_attack_look_follows_the_weapon(self):
        w={'type_id':'weapon_ray_laser','name':'x'}
        adventure.WEAPON_LOOK['weapon_ray_laser']=''
        self.assertEqual(adventure.attack_look(w),{})
        adventure.WEAPON_LOOK['weapon_ray_laser']='laser_bolt'
        self.assertEqual(adventure.attack_look(w),{'look':'laser_bolt'})

    def test_shots_carry_the_look(self):
        from unittest.mock import patch
        from tests import test_update033 as arena
        for ident,mode,count in (('weapon_ash_pistol',None,1),('weapon_rust_assault','burst',5),('weapon_thunder_shotgun',None,6)):
            adventure.WEAPON_LOOK[ident]='heavy'
            g,w,b=arena.Update033Tests().arena(ident,2)
            if mode:w['fire_mode']=mode
            g.pop_events()
            with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):
                self.assertTrue(g.shoot('0'))
            shots=[e for e in g.pop_events() if e['kind']=='attack']
            self.assertEqual(len(shots),count,ident)
            self.assertTrue(all(e.get('look')=='heavy' for e in shots),ident)
            adventure.WEAPON_LOOK[ident]=''
            g,w,b=arena.Update033Tests().arena(ident,2);g.pop_events()
            with patch.object(g.rng,'random',return_value=.5),patch.object(g.rng,'randrange',return_value=99):g.shoot('0')
            self.assertFalse(any('look' in e for e in g.pop_events()),ident)

    def test_armed_enemies_use_their_weapon_look(self):
        adventure.WEAPON_LOOK['weapon_watch_rifle']='railgun'
        enemy=dict(range=6,human=True,equipment={'weapon':{'type_id':'weapon_watch_rifle','name':'x'}})
        self.assertEqual(attack_looks.look(enemy),{'damage_type':'kinetic','look':'railgun'})
        enemy['equipment']['weapon']['type_id']='weapon_ash_pistol'
        self.assertEqual(attack_looks.look(enemy),{'damage_type':'kinetic'})

    def test_drawing_hooks(self):
        self.assertEqual(projectiles.look({'damage_type':'thermal'}),'thermal')
        self.assertEqual(projectiles.look({'damage_type':'thermal','look':'railgun'}),'railgun')
        self.assertEqual(projectiles.look({'damage_type':'thermal','look':'unknown'}),'thermal')
        self.assertEqual(projectiles.arrive({'damage_type':'kinetic','look':'plasma_red'}),projectiles.LOOKS['plasma_red'])
        self.assertEqual(projectiles.duration({'look':'railgun'},.4),.8)
        self.assertEqual(projectiles.duration({'look':'heavy'},.65),.65)

    def test_every_look_draws_through_the_whole_event(self):
        class Canvas:
            def __init__(self):self.items=0
            def __getattr__(self,name):
                def item(*args,**kwargs):self.items+=1
                return item
        for look in projectiles.LOOKS:
            for mode in ('single','pellet'):
                c=Canvas()
                for i in range(41):
                    projectiles.draw(c,dict(damage_type='kinetic',look=look,fire_mode=mode,hit=i%2==0),10,10,200,60,i/40,20)
                self.assertGreater(c.items,40,look)


if __name__=='__main__':unittest.main()
