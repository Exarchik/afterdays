"""Offset-coordinate diagonals are unit-cost hex edges, not square diagonals."""
import unittest
from unittest.mock import patch
import afterdays
import world_hex
from route_ui import RouteController
from types import SimpleNamespace


class HexStepTests(unittest.TestCase):
    def game(self):
        g=afterdays.Game(47);g.x=g.y=5;g.special_sites=[];g.radiation={}
        g.reputation_state['border_open']=True;g._guided_trip=True
        for y in range(3,13):
            for x in range(3,13):g.world[y][x]='waste'
        return g

    def test_every_direction_consumes_one_turn_and_one_satiety(self):
        for y in (5,6):
            for target in world_hex.adjacent((5,y)):
                g=self.game();g.y=y;g.world_distance_remainder=.9
                before=(g.turn,g.travel_steps,g.hunger)
                self.assertTrue(g.step(target[0]-5,target[1]-y))
                self.assertEqual((g.x,g.y),target)
                self.assertEqual((g.turn,g.travel_steps,g.hunger),(before[0]+1,before[1]+1,before[2]-1))
                self.assertEqual(g.world_distance_remainder,0)

    def test_blocked_destination_spends_nothing(self):
        g=self.game();g.world[6][6]='cliff';before=(g.turn,g.hunger,g.x,g.y)
        self.assertFalse(g.step(1,1));self.assertEqual(before,(g.turn,g.hunger,g.x,g.y))

    def test_array_diagonal_that_does_not_share_edge_is_rejected(self):
        g=self.game();g.y=6;before=(g.turn,g.hunger,g.x,g.y)
        self.assertFalse(g.step(1,1));self.assertEqual(before,(g.turn,g.hunger,g.x,g.y))

    def test_radiation_applies_once_per_hex(self):
        g=self.game();g.radiation['6,6']=1;g.world_distance_remainder=.9
        self.assertTrue(g.step(1,1));self.assertEqual(g.radiation_injury,5)

    def test_route_animation_has_equal_duration_for_all_directions(self):
        controller=RouteController.__new__(RouteController)
        controller.app=SimpleNamespace(game=SimpleNamespace(x=5,y=5));controller.guided_city=None
        for pos in world_hex.adjacent((5,5)):
            controller.path=[pos];self.assertAlmostEqual(controller.segment_duration(),2/3)
        controller.guided_city=1;self.assertAlmostEqual(controller.segment_duration(),1/3)


if __name__=='__main__':unittest.main()
