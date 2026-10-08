import random
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
import world_hex as grid
from world_map import OverlayCanvas
from storm033 import Storms
import quest_limits


class HexCompletionTests(unittest.TestCase):
    def test_storm_radius_and_world_clipping(self):
        class Weather(Storms):
            def __init__(self):
                self.world=[['waste']*30 for _ in range(30)]
                self.reputation_state={'storm033':dict(pos=[15,15],radius=1)}
        g=Weather()
        for radius,count in ((1,7),(2,19),(3,37)):
            g.storm['radius']=radius
            self.assertEqual(len(g.storm_cells()),count)
            self.assertTrue(all(grid.distance((15,15),p)<=radius for p in g.storm_cells()))
        g.storm['pos']=[-1,0]
        self.assertTrue(all(0<=x<30 and 0<=y<30 for x,y in g.storm_cells()))

    def test_quest_radius_uses_hex_steps(self):
        game=SimpleNamespace(cities=[[0,0]])
        self.assertTrue(quest_limits.nearby(game,{'city':0},(25,0)))
        self.assertFalse(quest_limits.nearby(game,{'city':0},(22,10)))

    def test_generated_road_paths_are_shortest_and_bounded(self):
        rng=random.Random(18)
        for _ in range(100):
            a=(rng.randrange(112),rng.randrange(32));b=(rng.randrange(112),rng.randrange(32))
            path=grid.line_path(a,b)
            self.assertEqual(len(path)-1,grid.distance(a,b))
            self.assertEqual((path[0],path[-1]),(a,b))
            self.assertTrue(all(q in grid.adjacent(p) for p,q in zip(path,path[1:])))
            self.assertTrue(all(0<=x<112 and 0<=y<32 for x,y in path))

    def test_overlay_reuses_and_updates_items_without_recreation(self):
        canvas=MagicMock();canvas.create_text.return_value=11
        frame=OverlayCanvas(canvas,reset=True)
        frame.create_text(10,20,text='old',fill='green');frame.finish()
        canvas.reset_mock()
        frame=OverlayCanvas(canvas)
        frame.create_text(10,20,text='old',fill='green');frame.finish()
        canvas.create_text.assert_not_called();canvas.delete.assert_not_called()
        canvas.itemconfigure.assert_not_called();canvas.coords.assert_not_called()
        frame=OverlayCanvas(canvas)
        frame.create_text(12,20,text='new',fill='green');frame.finish()
        canvas.coords.assert_called_once_with(11,12,20)
        canvas.itemconfigure.assert_called_once_with(11,text='new')
        frame=OverlayCanvas(canvas);frame.finish();canvas.delete.assert_called_with(11)

    def test_overlay_rebuild_does_not_reuse_deleted_items(self):
        canvas=MagicMock()
        frame=OverlayCanvas(canvas,reset=True);frame.create_polygon(1,2,3,4);frame.finish()
        canvas.reset_mock()
        frame=OverlayCanvas(canvas,reset=True);frame.create_polygon(1,2,3,4);frame.finish()
        canvas.create_polygon.assert_called_once()

    def test_road_triangle_cleanup_keeps_network_connected(self):
        import world_layout
        from world_map import road_neighbors
        for seed in range(5):
            cities,world=world_layout.build(random.Random(seed).getstate())
            g=SimpleNamespace(world=world);seen={tuple(cities[0])};queue=list(seen)
            for pos in queue:
                linked=road_neighbors(g,pos)
                for p in linked:
                    self.assertIn(pos,road_neighbors(g,p))
                    for q in linked:
                        if p!=q:self.assertFalse(q in road_neighbors(g,p))
                    if p not in seen:seen.add(p);queue.append(p)
            self.assertTrue(set(map(tuple,cities))<=seen)
