import random,tempfile,unittest
from pathlib import Path

import game.model as r
import world_hex
from game.systems import torn_map as tm
from tests.fixtures.quest_offer import offer_for
from tests.fixtures.torn_map import solve_map


class TornMapTests(unittest.TestCase):
    def map_game(self,seed=4):
        g=r.Game(seed);q=offer_for(g,'torn_map');self.assertTrue(g.accept_quest(q['id']))
        return g,g.quests[-1]

    def state(self,cols=4,rows=3,rotate=1,ident='x'):
        rng=random.Random(ident)
        return tm.generate(rng,dict(cols=cols,rows=rows,rotate=rotate),[3,3,9,7])

    def test_real_world_window_holds_target_off_centre(self):
        g,q=self.map_game();state=g.map_puzzle(q['id']);vx,vy,cols,rows=state['window']
        tx,ty=q['stash_pos']
        self.assertEqual((cols,rows),tm.VIEW)
        self.assertTrue(vx+2<=tx<=vx+cols-3 or vx in (0,len(g.world[0])-cols))
        self.assertTrue(vy+2<=ty<=vy+rows-3 or vy in (0,len(g.world)-rows))
        self.assertTrue(0<=vx and vx+cols<=len(g.world[0]) and 0<=vy and vy+rows<=len(g.world))
        x,y=tm.target_point(state,q['stash_pos'])
        self.assertTrue(.3<x<state['cols']-.3 and .3<y<state['rows']-.3)
        self.assertIn(tuple(q['stash_pos']),tm.sheet_cells(g.world,state['window'],state['cols'],state['rows']))

    def test_deterministic_from_quest_id_and_saved(self):
        g,q=self.map_game();state=g.map_puzzle(q['id'])
        copy=r.Game(4);copy.quests=[dict(q,torn=None)]
        self.assertEqual(copy.map_puzzle(q['id']),state)
        self.assertEqual(tm.outlines(q['id'],4,3),tm.outlines(q['id'],4,3))
        self.assertEqual(len(tm.outlines(q['id'],5,4)),20)
        self.assertTrue(g.map_move(q['id'],0,2,2))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);loaded=r.Game.load(path)
        self.assertEqual(loaded.map_puzzle(q['id']),state)

    def test_old_save_layout_replaced(self):
        g,q=self.map_game();q.pop('torn',None);q['layout']=[1,0,2,3,4,5,6,7,8]
        state=g.map_puzzle(q['id'])
        self.assertNotIn('layout',q);self.assertEqual(len(state['pieces']),state['cols']*state['rows'])

    def test_true_neighbours_glue_only(self):
        s=self.state(rotate=0)
        for i,p in enumerate(s['pieces']):p[0],p[1],p[2]=.6+i%4*1.4,.6+i//4*1.4,0
        tm.move(s,0,2,2)
        self.assertFalse(tm.move(s,2,3+tm.SNAP*1.5,2));self.assertFalse(s['glued'])   # not a neighbour of 0
        self.assertFalse(tm.move(s,1,3+tm.SNAP*1.5,2));self.assertFalse(s['glued'])   # too far
        s['pieces'][1][2]=1
        self.assertFalse(tm.move(s,1,3,2));self.assertFalse(s['glued'])               # wrong rotation
        s['pieces'][1][2]=0
        self.assertTrue(tm.move(s,1,3.05,2.04));self.assertEqual(s['glued'],[[0,1]])
        self.assertEqual(s['pieces'][1][:2],[3,2]);self.assertEqual(s['pieces'][0][3],s['pieces'][1][3])

    def test_group_moves_and_turns_together(self):
        s=self.state(rotate=1)
        for p in s['pieces']:p[2]=0
        tm.move(s,0,2,2);tm.move(s,1,3,2);tm.move(s,4,2,3)
        group=s['pieces'][0][3];self.assertEqual(sorted(tm.members(s,group)),[0,1,4])
        tm.move(s,0,2.5,2.2)
        self.assertEqual([s['pieces'][1][:2],s['pieces'][4][:2]],[[3.5,2.2],[2.5,3.2]])
        tm.rotate(s,0)
        p0,p1,p4=(s['pieces'][i] for i in (0,1,4))
        self.assertEqual({p0[2],p1[2],p4[2]},{1})
        self.assertAlmostEqual(p1[0]-p0[0],0);self.assertAlmostEqual(p1[1]-p0[1],1)   # right neighbour now below
        self.assertAlmostEqual(p4[0]-p0[0],-1);self.assertAlmostEqual(p4[1]-p0[1],0)  # lower neighbour now left
        # Four turns restore the orientation.
        for _ in range(3):tm.rotate(s,0)
        self.assertEqual(s['pieces'][0][2],0)

    def test_pieces_stay_on_table(self):
        s=self.state()
        tm.move(s,0,-40,99);x,y=s['pieces'][0][:2]
        self.assertTrue(.5<=x<=tm.TABLE[0]-.5 and .5<=y<=tm.TABLE[1]-.5)

    def test_solve_reveals_sheet_and_marks_stash(self):
        g,q=self.map_game();ident=q['id'];g.explored=[]
        state=solve_map(g,ident)
        self.assertTrue(q['map_solved']);self.assertEqual(q['pos'],q['stash_pos']);self.assertTrue(tm.solved(state))
        self.assertEqual({p[2] for p in state['pieces']},{0})
        cells=tm.sheet_cells(g.world,state['window'],state['cols'],state['rows'])
        self.assertGreater(len(cells),40)
        self.assertTrue(all(g.revealed(x,y) for x,y in cells))
        self.assertTrue(any(i.get('art_id')=='restored_map_item' for i in g.bag if i.get('quest_id')==ident))
        self.assertFalse(g.map_move(ident,0,1,1))

    def test_rotation_can_be_disabled(self):
        g,q=self.map_game()
        q['torn']=tm.generate(random.Random(1),dict(cols=3,rows=3,rotate=0),[3,3,9,7])
        self.assertEqual({p[2] for p in q['torn']['pieces']},{0})
        self.assertFalse(g.map_rotate(q['id'],0))
        solve_map(g,q['id']);self.assertTrue(q['map_solved'])

    def test_profile_settings(self):
        import quest_minigames,quest_profiles
        self.assertEqual(quest_minigames.defaults('torn_map'),dict(cols=4,rows=3,rotate=1))
        self.assertTrue(quest_profiles.defaults('torn_map')['cols']==4)
        self.assertEqual(tm.validate_settings(dict(cols=4,rows=3,rotate=1)),[])
        self.assertEqual(len(tm.validate_settings(dict(cols=9,rows=2.5,rotate=True))),3)

    def test_geometry_for_every_sheet_size(self):
        g,q=self.map_game();target=q['stash_pos']
        for cols in (3,4,5):
            for rows in (3,4):
                s=tm.generate(random.Random(2),dict(cols=cols,rows=rows,rotate=1),
                              tm.choose_window(g.world,g.cities,target,random.Random(3)))
                x,y=tm.target_point(s,target)
                self.assertTrue(0<x<cols and 0<y<rows)
                radius=tm.geometry(s['window'],cols,rows)[0]
                self.assertTrue(.15<radius<.6)
                for i,p in enumerate(s['pieces']):self.assertTrue(0<p[0]<tm.TABLE[0] and 0<p[1]<tm.TABLE[1])


if __name__=='__main__':unittest.main()
