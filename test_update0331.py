"""Quest radius and flat-top projection regression checks."""
import math,unittest
from unittest.mock import patch
import afterdays as r,hexgrid,quest_limits
from organic_arenas import boundary_edges

class Update0331Tests(unittest.TestCase):
    def test_flat_top_projection_and_inverse(self):
        """Flat horizontal edges, six touching neighbors and accurate interior clicks."""
        for x in range(-5,20):
            for y in range(-5,20):
                px,py=hexgrid.center((x,y),17,13,-37)
                self.assertEqual(hexgrid.cell(px,py,17,13,-37),(x,y))
                points=hexgrid.polygon(px,py,17)
                vertices=list(zip(points[::2],points[1::2]))
                self.assertEqual(vertices[1][1],vertices[2][1])
                self.assertEqual(vertices[4][1],vertices[5][1])
                for vx,vy in vertices:
                    self.assertEqual(hexgrid.cell(px+.95*(vx-px),py+.95*(vy-py),17,13,-37),(x,y))
        for neighbor in hexgrid.DIRECTIONS:
            self.assertEqual(len(boundary_edges({(0,0),neighbor})),10)

    def test_all_candidate_types_stay_in_radius(self):
        """Destinations and every cell in a search area respect the same giver radius."""
        for seed in (2,4,7):
            g=r.Game(seed);g.reputation_state['border_open']=True
            for city in range(g.main_city_count):
                origin=g.cities[city];q=dict(id='test',city=city,level=g.region_at(*origin),kind='scout')
                for pos in g.quest_locations(q):self.assertLessEqual(math.dist(origin,pos),25)
                for x,y in g.area_candidates(q):
                    for a in range(x-1,x+2):
                        for b in range(y-1,y+2):self.assertLessEqual(math.dist(origin,(a,b)),25)
                for site in g.delivery_sites(q):self.assertLessEqual(math.dist(origin,site['pos']),25)

    def test_no_remote_fallback_and_wandering_origin(self):
        """When only distant cells exist, no remote fallback is returned; scribes use their own position."""
        g=r.Game(2);g.reputation_state['border_open']=True
        q=dict(id='test',city=0,level=15,kind='radio')
        with patch.object(g,'reachable_world',return_value={(100,20)}),patch.object(g,'player_reachable_world',return_value={(100,20)}):self.assertEqual(g.quest_locations(q),[])
        q['issuer_pos']=[100,20]
        self.assertTrue(quest_limits.nearby(g,q,(100,31)));self.assertFalse(quest_limits.nearby(g,q,(5,5)))
        self.assertTrue(quest_limits.nearby(g,q,(75,20)));self.assertFalse(quest_limits.nearby(g,q,(74,20)))

if __name__=='__main__':unittest.main()
