import unittest
from arcade_scene import Scene,Command,geometry,triangles,stroke


class SceneTests(unittest.TestCase):
    def test_tags_delete_only_effects(self):
        s=Scene()
        tile=s.add('rectangle',(0,0,10,10),{})
        fx=s.add('text',(5,5),{'tags':'fx'})
        s.delete('fx')
        self.assertEqual(s.ids('all'),(tile,))
        self.assertNotIn(fx,s.items)

    def test_route_position_updates_all_coordinates(self):
        s=Scene()
        i=s.add('polygon',((1,2,3,4,5,6),),{'tags':('player','route')})
        s.move('player',10,-1)
        self.assertEqual(s.coords(i),[11,1,13,3,15,5])
        s.coords('route',0,1,2,3,4,5)
        self.assertEqual(s.coords(i),[0,1,2,3,4,5])

    def test_background_is_lowered_beneath_text(self):
        s=Scene()
        floor=s.add('rectangle',(0,0,1,1),{})
        label=s.add('text',(0,0),{})
        backdrop=s.add('rectangle',(0,0,1,1),{})
        s.reorder(backdrop,label,above=False)
        self.assertEqual(s.ids('all'),(floor,backdrop,label))

    def test_concave_polygon_area(self):
        points=[(0,0),(4,4),(2,3),(0,4)]
        result=triangles(points)
        area=sum(abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2 for a,b,c in zip(result[::3],result[1::3],result[2::3]))
        expected=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2
        self.assertAlmostEqual(area,expected)

    def test_dash_has_gap(self):
        result=stroke([(0,0),(10,0)],2,(2,2))
        self.assertEqual(len(result),18)
        self.assertEqual(sorted(set(p[0] for p in result)),[0,2,4,6,8,10])

    def test_outline_and_fill_keep_order(self):
        runs=geometry(Command('rectangle',(0,0,10,5),{'fill':'red','outline':'blue'}))
        self.assertEqual([color for _,color in runs],['red','blue'])
        self.assertEqual(len(runs[0][0]),6)

    def test_empty_delete_does_not_invalidate_static_scene(self):
        s=Scene()
        s.add('text',(1,2),{'text':'Україна','font':('Segoe UI',10)})
        revision=s.revision
        s.delete('fx')
        self.assertEqual(s.revision,revision)


if __name__=='__main__':unittest.main()
