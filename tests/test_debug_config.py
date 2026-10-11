import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import game.model as r
import debug_config as d
class View(d.MapVisibility):
 # Ініціалізує об’єкт, його початковий стан і потрібні залежності.
 def __init__(self,g):self.game=g;self.show_full_map=False;self.refresh_count=0
 # Оновлює віджети відповідно до поточного стану гри.
 def refresh(self):self.refresh_count+=1
class DebugTests(unittest.TestCase):
 def test_optional_config(self):
  """Перевіряє сценарій «optional config» та очікувані результати."""
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'config.ini';self.assertFalse(d.read_test_mode(p))
   for data,expected in [('[debug]\ntestmode=true',True),('[debug]\ntestmode=false',False),('[debug]\ntestmode=wrong',False),('bad syntax',False),('[other]\nx=true',False)]:
    p.write_text(data,encoding='utf-8-sig');self.assertEqual(d.read_test_mode(p),expected)
 def test_toggle_preserves_progress_and_saves(self):
  """Перевіряє сценарій «toggle preserves progress and saves» та очікувані результати."""
  g=r.Game(7);view=View(g);before=copy.deepcopy(vars(g));hidden=next((x,y) for y in range(32) for x in range(48) if not g.revealed(x,y))
  with patch.object(d,'TEST_MODE',True):
   self.assertFalse(view.map_revealed(*hidden));view.toggle_test_map()
   self.assertTrue(view.map_revealed(*hidden));self.assertTrue(view.map_city_known(11))
   self.assertEqual(g.explored,before['explored']);self.assertEqual(g.known_cities,before['known_cities'])
   with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'save.json';g.save(p);h=r.Game.load(p)
    self.assertFalse(h.revealed(*hidden));self.assertNotIn('show_full_map',vars(h))
   g.reveal(*hidden,0);view.toggle_test_map();self.assertTrue(view.map_revealed(*hidden))
   self.assertEqual(view.map_city_known(11),11 in g.known_cities)
 def test_disabled_mode_cannot_reveal(self):
  """Перевіряє сценарій «disabled mode cannot reveal» та очікувані результати."""
  g=r.Game(7);view=View(g)
  with patch.object(d,'TEST_MODE',False):
   view.toggle_test_map();self.assertFalse(view.show_full_map);self.assertEqual(view.refresh_count,0)
   view.show_full_map=True;self.assertEqual(view.map_revealed(47,31),g.revealed(47,31))
