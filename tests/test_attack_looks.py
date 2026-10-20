"""Enemy attacks look like their weapon or the monster: event fields and drawing."""
import unittest
from unittest.mock import MagicMock,patch
import content
import game.items as p
from game.systems import attack_looks as looks
import ui.projectiles as projectiles
from tests import test_update033 as arena


class AttackLookTests(unittest.TestCase):
    def test_every_monster_has_a_style(self):
        for ident in content.MONSTER_DATA:
            self.assertIn(ident,looks.MONSTERS)
            style=looks.MONSTERS[ident]
            melee=content.MONSTER_DATA[ident]['range']<=1
            self.assertEqual(style in looks.MELEE,melee,ident)

    def test_custom_monsters_by_words_and_fallback(self):
        self.assertEqual(looks.style_of(dict(type_id='monster_acid_slug',name='Кислотний слимак',range=3)),'acid')
        self.assertEqual(looks.style_of(dict(type_id='monster_x',name='Болотний жах',range=2)),'mud')
        self.assertEqual(looks.style_of(dict(type_id='monster_x',name='Безіменний',range=1)),'claw')
        self.assertEqual(looks.style_of(dict(type_id='monster_x',name='Безіменний',range=4)),'spit')

    def test_people_use_their_weapon(self):
        w=p.equipment('weapon_ash_pistol')
        self.assertEqual(looks.look(dict(human=True,range=5,equipment=dict(weapon=w))),dict(damage_type='kinetic'))
        self.assertEqual(looks.look(dict(human=True,range=1,equipment={})),dict(attack_style='punch'))
        self.assertEqual(looks.look(dict(type_id='monster_spark',range=7)),dict(damage_type='electric'))
        self.assertEqual(looks.look(dict(type_id='monster_spitter',range=5)),dict(attack_style='spit'))

    def test_enemy_turn_tags_the_blow(self):
        g,w,b=arena.Update033Tests().arena('weapon_ash_pistol',1);g.pop_events()
        enemy=b['enemies'][0];enemy.update(type_id='monster_spitter',range=5,speed=0,damage=1,attack=0,level=1)
        b['enemies']=[enemy];g.hp=500
        with patch.object(g.rng,'randrange',return_value=99),patch.object(g.rng,'random',return_value=.99),patch.object(g,'protection_stat',return_value=0):g.end_turn()
        blow=next(e for e in g._events if e['kind'] in ('attack','slash'))
        self.assertEqual(blow['attack_style'],'spit')

    def test_all_styles_draw_at_every_phase(self):
        canvas=MagicMock()
        events=[dict(kind='attack',attack_style=s,hit=h,source=[0,0],pos=[3,1]) for s in projectiles.STYLE_ARRIVE for h in (True,False)]
        events+=[dict(kind='attack',damage_type=t,fire_mode=m,volley='v',projectile=1) for t in projectiles.ARRIVE for m in ('single','pellet','burst')]
        for event in events:
            for t in (0,.05,.3,.5,.7,.95):projectiles.draw(canvas,event,10,10,120,60,t,18)
        self.assertTrue(canvas.create_line.called and canvas.create_oval.called)
        self.assertEqual(projectiles.arrive(dict(attack_style='laser')),projectiles.STYLE_ARRIVE['laser'])
        self.assertEqual(projectiles.arrive(dict(damage_type='thermal')),projectiles.ARRIVE['thermal'])


if __name__=='__main__':unittest.main()
