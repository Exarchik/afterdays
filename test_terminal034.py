"""Data and hit-area regression checks for the field terminal."""
import unittest
from types import SimpleNamespace
import afterdays as r
import progression as p
from terminal034 import snapshot,sections,StatusBar

class TerminalTests(unittest.TestCase):
    def test_data_after_progression_and_weapon_change(self):
        """HUD derives XP from the current level and follows the active hand."""
        g=r.Game(3);g.xp=p.xp_for_level(5)+7
        d=snapshot(g)
        self.assertEqual(d['level'],5);self.assertEqual(d['xp'],7)
        self.assertEqual(d['xp_goal'],p.xp_for_level(6)-p.xp_for_level(5))
        self.assertEqual(d['rounds'],g.count('ammo',g.weapon['ammo_type']))
        g.active='weapon2';d=snapshot(g)
        self.assertIsNone(d['weapon']);self.assertEqual(d['cost'],0)
        self.assertEqual(d['rounds'],0)

    def test_effects_and_combat_points(self):
        """Effects and AP display remaining values without changing game state."""
        g=r.Game(3);g.rad_turns=8;g.reputation_state['coward_until']=g.turn+20
        g.battle={'ap':2,'max_ap':5}
        d=snapshot(g)
        self.assertEqual((d['ap'],d['max_ap'],d['rad'],d['coward']),(2,5,8,20))
        self.assertEqual(g.battle,{'ap':2,'max_ap':5})

    def test_columns_and_control_priority(self):
        """Columns fit the window and nested controls precede the weapon tooltip."""
        for w in (1042,1222,1882):
            cols=sections(w)
            self.assertEqual(cols[0][0],0);self.assertAlmostEqual(cols[-1][1],w)
            self.assertTrue(all(b>a for a,b in cols))
            self.assertTrue(all(cols[n][1]==cols[n+1][0] for n in range(5)))
        mock=SimpleNamespace(regions=[((20,10,30,20),'swap',None),((0,0,100,100),'weapon',None)])
        self.assertEqual(StatusBar.target(mock,SimpleNamespace(x=25,y=15)),0)
        self.assertEqual(StatusBar.target(mock,SimpleNamespace(x=50,y=50)),1)

    def test_paint_world_and_battle_at_window_sizes(self):
        """Exercise all rendering branches without a display server."""
        from unittest.mock import Mock,patch
        class Header(StatusBar):
            def __init__(self,g,width):
                self.game=g;self.app=SimpleNamespace(game=g);self.tip=Mock();self.fonts={};self.width=width
                self.create_line=Mock();self.create_polygon=Mock();self.create_rectangle=Mock();self.create_oval=Mock();self.create_text=Mock();self.delete=Mock()
            def winfo_width(self):return self.width
        g=r.Game(7)
        with patch('terminal034.tkfont.Font') as font,patch('terminal034.sprites.draw'),patch('terminal034.icon'):
            font.return_value.measure.side_effect=lambda text:len(text)*7
            for width in (1044,1224,1884):
                for combat in (False,True):
                    g.battle={'ap':2,'max_ap':5} if combat else None
                    g.rad_turns=10 if combat else 0;g.reputation_state['coward_until']=g.turn+20 if combat else 0
                    bar=Header(g,width);bar.paint()
                    self.assertGreater(len(bar.regions),5)
                    texts=[call.kwargs['text'] for call in bar.create_text.call_args_list]
                    self.assertIn('2/5',texts) if combat else self.assertIn('—',texts)
                    self.assertTrue(all(0<=box[0]<box[2]<=width for box,tip,action in bar.regions))

if __name__=='__main__':unittest.main()
