import copy,math,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import afterdays as r
import adventure,hexgrid,progression as p
from cache_events import CACHE_TYPES
from advanced_ui import battle_camera
from visuals import condition_bar,condition_color

class Update025Tests(unittest.TestCase):
 def test_projection_parallel_edges_and_flattening(self):
  a,b,c,d=[hexgrid.center(pos,1) for pos in ((0,0),(12,0),(12,8),(0,8))]
  for axis in (0,1):self.assertAlmostEqual(b[axis]-a[axis],c[axis]-d[axis])
  for axis in (0,1):self.assertAlmostEqual(d[axis]-a[axis],c[axis]-b[axis])
  points=hexgrid.polygon(0,0,10);self.assertAlmostEqual(max(points[1::2])-min(points[1::2]),15*.9)
  self.assertTrue(25<math.degrees(math.atan2(b[1],b[0]))<35)
 def test_projected_hexes_share_edges(self):
  def vertices(pos):
   xy=hexgrid.polygon(*hexgrid.center(pos,12),12);return {(round(x,6),round(y,6)) for x,y in zip(xy[::2],xy[1::2])}
  main=vertices((5,5))
  for neighbor in hexgrid.neighbors(5,5,12,12):self.assertEqual(len(main&vertices(neighbor)),2)
 def test_camera_fit_click_roundtrip_and_zoom(self):
  for w,h in ((15,11),(31,27),(9,15)):
   b=dict(w=w,h=h,pos=[4,6]);u,ox,oy=battle_camera(b,800,600)
   for x in range(w):
    for y in range(h):
     self.assertEqual(hexgrid.cell(*hexgrid.center((x,y),u,ox,oy),u,ox,oy),(x,y))
     points=hexgrid.polygon(*hexgrid.center((x,y),u,ox,oy),u)
     self.assertTrue(all(0<=xx<=800 for xx in points[::2]));self.assertTrue(all(0<=yy<=600 for yy in points[1::2]))
   b['dungeon']=True;u,ox,oy=battle_camera(b,800,600)
   self.assertAlmostEqual(u,.9*.85*max(24,min(46,800/18,600/13)))
   x,y=hexgrid.center(b['pos'],u,ox,oy);self.assertAlmostEqual(x,400);self.assertAlmostEqual(y,330)
 def make_cache(self,theme):
  g=r.Game(1);g.x,g.y=20,18;g.world[18][20]=CACHE_TYPES[theme]
  self.assertTrue(g.make_road_event('locked_'+theme));self.assertTrue(g.resolve_event('act'));return g,g.road_cache()
 def test_five_events_persist_and_rewards_once(self):
  self.assertEqual(len(adventure.ROAD_EVENTS),51)
  for theme in CACHE_TYPES:
   g,c=self.make_cache(theme);self.assertEqual(c['level'],g.region_level);self.assertTrue(c['contents']);self.assertFalse(g.loot)
   content=copy.deepcopy(c['contents']);angle=c['lock_target'];ident=c['id']
   with tempfile.TemporaryDirectory() as td:
    path=Path(td)/'s.json';g.save(path);g=r.Game.load(path)
   self.assertTrue(g.search());self.assertEqual(g._lock_request,ident);self.assertEqual(g.lock_context(ident)['contents'],content)
   g.bag[:]=[i for i in g.bag if i['kind']!='parts'];self.assertIsNone(g.unlock_cache(ident,angle));p.add_to(g.bag,p.parts(2))
   self.assertFalse(g.unlock_cache(ident,0 if angle>90 else 180));self.assertEqual(g.count('parts'),1)
   self.assertTrue(g.unlock_cache(ident,angle));self.assertEqual(g.count('parts'),1);self.assertTrue(g.loot)
   loot=copy.deepcopy(g.loot);self.assertIsNone(g.unlock_cache(ident,angle));self.assertEqual(g.loot,loot);self.assertIsNone(g.road_cache())
 def test_wrong_position_and_invalid_attempt_atomic(self):
  g,c=self.make_cache('medical');p.add_to(g.bag,p.parts(2));before=copy.deepcopy(c)
  for angle in (-1,181,float('nan'),True):self.assertIsNone(g.unlock_cache(c['id'],angle))
  g.x+=1;self.assertIsNone(g.unlock_cache(c['id'],c['lock_target']));self.assertEqual(g.count('parts'),2);self.assertEqual(c,before)
 def test_rewards_use_location_not_player_level(self):
  g=r.Game(8);g.xp=p.xp_for_level(20)
  for level in (1,4,9):
   for theme in CACHE_TYPES:
    with patch.object(g.rng,'random',return_value=0):items=g.cache_contents(theme,level)
    gear=[i for i in items if i['kind'] in ('weapon','armor','helmet','module')];self.assertTrue(gear)
    for item in gear:self.assertTrue(max(1,level-2)<=item['level']<=level)
 def test_leave_and_reopen_no_reroll(self):
  g=r.Game(2);g.make_road_event('locked_armory');g.resolve_event('leave');self.assertFalse(g.reputation_state.get('road_caches'))
  g.make_road_event('locked_armory');g.resolve_event('act');c=copy.deepcopy(g.road_cache());g.search();self.assertEqual(c,g.road_cache())
  g.make_road_event('locked_armory');g.resolve_event('act');self.assertEqual(c,g.road_cache());self.assertEqual(len(g.reputation_state['road_caches']),1)
 def test_condition_thresholds_and_fill(self):
  for value,color in [(0,'#e66d63'),(25,'#e66d63'),(26,'#e3c159'),(69,'#e3c159'),(70,'#75ce83'),(100,'#75ce83')]:
   self.assertEqual(condition_color(value),color);c=Mock();condition_bar(c,dict(durability=value),10,20,100)
   self.assertEqual(c.create_rectangle.call_args_list[0].kwargs['outline'],color)
   if value:self.assertEqual(c.create_rectangle.call_args.args,(10,20,10+value,24))
   else:self.assertEqual(c.create_rectangle.call_count,1)
  c=Mock();condition_bar(c,dict(kind='food'),0,0,100);c.create_rectangle.assert_not_called()
