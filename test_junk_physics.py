import copy,json,tempfile,unittest,math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import afterdays as r
import junk_physics as j
from junk_art import ScrapArt
from junkyard_ui import Junkyard
from tests_fixtures.quest_offer import offer_for

class JunkPhysicsTests(unittest.TestCase):
 def game(self):
  """Готує або імітує операцію «game» для перевірок JunkPhysicsTests."""
  g=r.Game(4);q=offer_for(g,'junkyard');self.assertTrue(g.accept_quest(q['id']));q=g.quests[-1];g.x,g.y=q['pos'];return g,q
 def test_mass_and_return_are_source_physics(self):
  """Перевіряє сценарій «mass and return are source physics» та очікувані результати."""
  def scrap(m):return j.Scrap(0,'',m,100,100,100,100,[[0,0]],'')
  light,heavy=scrap(.2),scrap(28)
  for _ in range(20):light.step(.016,(500,100));heavy.step(.016,(500,100))
  self.assertGreater(light.x,heavy.x);x=heavy.x
  heavy.step(.05);self.assertLess(heavy.x,x);self.assertGreater(heavy.x,100)
 def test_initial_finds_covered_by_two_fragments(self):
  """Перевіряє сценарій «initial finds covered by two fragments» та очікувані результати."""
  g,q=self.game()
  for target in q['junk_objects']:
   if target['kind']=='debris':continue
   x,y=target['x']+30,target['y']+30
   self.assertGreaterEqual(sum(j.covers(s,x,y) for s in q['junk_objects'] if s['kind']=='debris'),2)
   self.assertFalse(g.junk_collect(q['id'],x,y))
 def test_polygon_hit_does_not_use_bounding_rectangle(self):
  """Перевіряє сценарій «polygon hit does not use bounding rectangle» та очікувані результати."""
  obj=dict(kind='debris',x=100,y=100,points=[[0,-40],[40,0],[0,40],[-40,0]])
  self.assertTrue(j.covers(obj,100,100));self.assertFalse(j.covers(obj,135,135))
 def test_saved_motion_preserves_home_and_no_duplicate_targets(self):
  """Перевіряє сценарій «saved motion preserves home and no duplicate targets» та очікувані результати."""
  g,q=self.game();s=next(o for o in q['junk_objects'] if o['kind']=='debris');home=s['home_x'],s['home_y']
  for _ in range(40):g.junk_tick(q['id'],.016,s['id'],(425,280))
  self.assertNotEqual((s['x'],s['y']),home)
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
  self.assertEqual(q['junk_objects'],h.quests[-1]['junk_objects']);h.junk_tick(q['id'],.05)
  other=next(o for o in h.quests[-1]['junk_objects'] if o['id']==s['id'])
  self.assertLess(math.dist((other['x'],other['y']),home),math.dist((s['x'],s['y']),home))
 def test_old_quest_upgrade_retains_progress_and_rewards(self):
  """Перевіряє сценарій «old quest upgrade retains progress and rewards» та очікувані результати."""
  g,q=self.game();q.pop('junk_physics');targets=[o for o in q['junk_objects'] if o['kind']!='debris'];targets[0]['found']=True;q['progress']=1
  q['junk_objects']=targets+[dict(id='old',kind='debris',x=0,y=0,w=100,h=80,found=False)]
  reward=q['reward'];j.ensure(q);snapshot=copy.deepcopy(q);j.ensure(q)
  self.assertEqual(q,snapshot);self.assertTrue(q['junk_objects'][0]['found']);self.assertEqual(q['progress'],1);self.assertEqual(q['reward'],reward)
 def test_scrap_draw_has_no_weight_text(self):
  """Перевіряє сценарій «scrap draw has no weight text» та очікувані результати."""
  art=ScrapArt();art.canvas=MagicMock()
  for s in j.make_site(1)[1]:art.draw_scrap(s)
  art.canvas.create_polygon.assert_called();art.canvas.create_text.assert_not_called()
 def test_right_click_collects_without_releasing_held_scrap(self):
  """Перевіряє сценарій «right click collects without releasing held scrap» та очікувані результати."""
  g,q=self.game();target=q['junk_objects'][0]
  for s in list(q['junk_objects']):
   if s['kind']=='debris':g.junk_move(q['id'],s['id'],850,560)
  ui=Junkyard.__new__(Junkyard);ui.game=g;ui.quest=q;ui.ident=q['id'];ui.scale=1;ui.ox=ui.oy=0
  ui.drag='debris0';ui.canvas=MagicMock();ui.app=MagicMock();ui.status=MagicMock()
  ui.collect_right(SimpleNamespace(x=target['x']+30,y=target['y']+30))
  self.assertEqual(ui.drag,'debris0');self.assertEqual(q['progress'],1);ui.canvas.delete.assert_called_once_with(target['id'])
 def test_window_destroy_cancels_animation(self):
  """Перевіряє сценарій «window destroy cancels animation» та очікувані результати."""
  ui=Junkyard.__new__(Junkyard);ui.win=MagicMock();ui.timer='timer1';ui.closed=False;ui.drag='debris1'
  ui.destroyed(SimpleNamespace(widget=ui.win));self.assertTrue(ui.closed);self.assertIsNone(ui.timer);self.assertIsNone(ui.drag);ui.win.after_cancel.assert_called_once_with('timer1')

if __name__=='__main__':unittest.main()
