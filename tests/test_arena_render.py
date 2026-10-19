"""Arena rendering: the floor is baked once into one image, frames only redraw units and markers."""
import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import arena_tiles
import hexgrid
import game.model as model
import ui.advanced as advanced_ui
import ui.adventure as adventure_ui
from organic_arenas import boundary_edges

BACKGROUND=(0x18,0x21,0x1d)


def block(n=5):
    return [(x,y) for x in range(n) for y in range(n)]


def pixel_at(image,left,top,pos,u):
    px,py=hexgrid.center(pos,u)
    return image.getpixel((int(px-left),int(py-top)))


def app_for(g,width=900,height=560):
    canvas=Mock();canvas.winfo_width.return_value=width;canvas.winfo_height.return_value=height
    canvas.cget.return_value='#18211d';canvas.bbox.return_value=None;canvas._arena_static=None
    return SimpleNamespace(game=g,canvas=canvas,map_title=Mock(),hint=Mock(),battle_hover=None)


class FloorBakingTests(unittest.TestCase):
    def test_image_covers_every_cell_and_keeps_background_outside(self):
        cells=block();rim=boundary_edges(set(cells));u=18.7
        image,left,top=arena_tiles.render_floor(cells,{p:'waste' for p in cells},rim,u,(),'#18211d')
        self.assertEqual(image.mode,'RGB')
        self.assertEqual((left,top,left+image.width,top+image.height),arena_tiles.floor_bounds(cells,rim,u))
        for pos in cells:self.assertNotEqual(pixel_at(image,left,top,pos,u),BACKGROUND)
        self.assertEqual(image.getpixel((0,0)),BACKGROUND)

    def test_adjacent_tiles_overlap_without_seams(self):
        cells=block(6);base=tuple(int(arena_tiles.PALETTES['forest'][0][i:i+2],16) for i in (1,3,5))
        for u in (14.0,17.3,19.3,21.7,24.9,31.2):
            image,left,top=arena_tiles.render_floor(cells,{p:'forest' for p in cells},[],u,(),'#18211d')
            for a in cells:
                for b in hexgrid.neighbors(*a,6,6):
                    ax,ay=hexgrid.center(a,u);bx,by=hexgrid.center(b,u)
                    point=(int((ax+bx)/2-left),int((ay+by)/2-top))
                    self.assertNotIn(image.getpixel(point),(base,BACKGROUND),(u,a,b))

    def test_water_is_tinted_and_render_is_deterministic(self):
        cells=block(4);kinds={p:'waste' for p in cells};u=20
        dry,left,top=arena_tiles.render_floor(cells,kinds,[],u,(),'#18211d')
        wet,_,_=arena_tiles.render_floor(cells,kinds,[],u,[[1,1]],'#18211d')
        self.assertNotEqual(pixel_at(dry,left,top,(1,1),u),pixel_at(wet,left,top,(1,1),u))
        self.assertEqual(pixel_at(dry,left,top,(2,2),u),pixel_at(wet,left,top,(2,2),u))
        again,_,_=arena_tiles.render_floor(cells,kinds,[],u,[[1,1]],'#18211d')
        self.assertEqual(wet.tobytes(),again.tobytes())

    def test_terrain_map_matches_per_cell_terrain_without_rng(self):
        g=model.Game(4);g.start_battle();b=g.battle;state=g.rng.getstate()
        cells=[tuple(p) for p in b['floor']];roads=arena_tiles.road_cells(b,arena_tiles.road_directions(g,b))
        kinds=arena_tiles.terrain_map(g,b,cells,roads)
        self.assertEqual(kinds,{p:arena_tiles.terrain(g,b,p,roads) for p in cells})
        self.assertEqual(state,g.rng.getstate())


class ArenaFrameTests(unittest.TestCase):
    def draw(self,app,times=1):
        with patch('sprites.draw',return_value=True),patch('PIL.ImageTk.PhotoImage'):
            for _ in range(times):advanced_ui.draw_battle(app)

    def test_floor_is_baked_once_and_reused_between_frames(self):
        g=model.Game(4);g.start_battle();app=app_for(g)
        with patch('arena_tiles.render_floor',wraps=arena_tiles.render_floor) as render:
            self.draw(app,3)
            self.assertEqual(render.call_count,1)
            app.canvas.winfo_width.return_value=1300;app.canvas.winfo_height.return_value=900   # window resized: zoom changes
            self.draw(app)
            self.assertEqual(render.call_count,2)
            g.battle['water_cells']=[g.battle['floor'][0]]   # different arena content
            self.draw(app)
            self.assertEqual(render.call_count,3)

    def test_frame_clears_everything_except_the_floor(self):
        g=model.Game(4);g.start_battle();app=app_for(g);c=app.canvas
        self.draw(app)
        c.addtag_all.assert_called_with('arena_old');c.dtag.assert_called_with('arena_static','arena_old')
        c.delete.assert_any_call('arena_old')
        self.assertNotIn(('all',),[call.args for call in c.delete.call_args_list])
        # Units and markers are a small number of items; tiles are not created per cell any more.
        self.assertLess(c.create_polygon.call_count+c.create_oval.call_count+c.create_line.call_count,150)
        self.assertEqual(c.create_image.call_count,1)

    def test_hover_redraws_only_its_marker(self):
        g=model.Game(4);g.start_battle();app=app_for(g);c=app.canvas
        self.draw(app);c.reset_mock()
        reach=next(iter(app.iso['reach']-{tuple(g.battle['pos'])}))
        far=next(p for p in app.iso['floor'] if p not in app.iso['reach'])
        with patch('arena_tiles.render_floor') as render:
            for pos,color in ((reach,'#bee5a6'),(far,'#d7866d')):
                app.battle_hover=pos;advanced_ui.draw_hover(app)
                self.assertEqual(c.create_polygon.call_args.kwargs['outline'],color)
            render.assert_not_called()
        self.assertEqual(c.create_polygon.call_count,2)
        self.assertFalse(c.create_image.called or c.addtag_all.called)
        c.delete.assert_any_call('hover')
        app.battle_hover=(-5,-5);c.reset_mock();advanced_ui.draw_hover(app)
        self.assertFalse(c.create_polygon.called)

    def test_camera_bounds_cached_match_fresh_computation(self):
        g=model.Game(4);g.start_battle();b=g.battle
        self.assertEqual(advanced_ui.battle_camera(b,900,560),advanced_ui.battle_camera(b,900,560,bounds=advanced_ui.unit_bounds(b)))


class FrameTimingTests(unittest.TestCase):
    def test_next_frame_accounts_for_work_time(self):
        clock=[100.0];after=[]
        fx=adventure_ui.Effects.__new__(adventure_ui.Effects)
        fx.app=SimpleNamespace(root=SimpleNamespace(after=lambda ms,fn:after.append(ms)))
        def frame():clock[0]+=.020
        fx.frame=frame
        with patch('ui.adventure.time.monotonic',side_effect=lambda:clock[0]):
            fx.tick()
            self.assertEqual(after[-1],adventure_ui.FRAME_MS-20)
            fx.frame=lambda:clock.__setitem__(0,clock[0]+.050)
            fx.tick()
            self.assertEqual(after[-1],1)

    def test_failed_frame_still_schedules_the_next(self):
        after=[];fx=adventure_ui.Effects.__new__(adventure_ui.Effects)
        fx.app=SimpleNamespace(root=SimpleNamespace(after=lambda ms,fn:after.append(ms)))
        def broken():raise RuntimeError('frame')
        fx.frame=broken
        with self.assertRaises(RuntimeError):fx.tick()
        self.assertEqual(len(after),1)


if __name__=='__main__':unittest.main()
