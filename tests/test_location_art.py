import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from game.model import Game
import location_art
from ui.location_panel import location_details


class LocationArtTests(unittest.TestCase):
    manifest={'town_a':{'art_category':'cities'},'town_b':{'art_category':'cities'},'event':{'art_category':'events'}}
    def test_category_and_stable_choice_without_rng_consumption(self):
        import art_library
        self.assertEqual(art_library.GROUPS['cities'],'Міста')
        g=Game(11);rng=g.rng.getstate()
        location_art.assign_city_art(g,self.manifest)
        saved=copy.deepcopy(g.reputation_state['city_art'])
        self.assertTrue(saved);self.assertTrue(set(saved.values())<={'town_a','town_b'})
        self.assertEqual(g.rng.getstate(),rng)
        location_art.assign_city_art(g,self.manifest)
        self.assertEqual(saved,g.reputation_state['city_art'])
        for x,y in g.cities:
            if g.world[y][x]!='city':self.assertNotIn(f'{x},{y}',saved)

    def test_new_game_and_save_load(self):
        import content
        original=content.read
        with patch.object(content,'read',side_effect=lambda name:self.manifest if name=='sprites.json' else original(name)):
            g=Game(13);saved=copy.deepcopy(g.reputation_state['city_art'])
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'save.json';g.save(path);loaded=Game.load(path)
                self.assertEqual(saved,loaded.reputation_state['city_art'])

    def test_missing_art_replaced_and_empty_category_safe(self):
        g=Game(12);location_art.assign_city_art(g,self.manifest)
        location_art.assign_city_art(g,{'town_c':{'art_category':'cities'}})
        self.assertEqual(set(g.reputation_state['city_art'].values()),{'town_c'})
        location_art.assign_city_art(g,{})
        self.assertTrue(g.reputation_state['city_art'])

    def test_location_details_exclude_player_equipment_and_survival(self):
        g=Game(4);g.x,g.y=g.cities[0]
        title,details=location_details(g)
        self.assertEqual(title,g.city_name(g.city));self.assertIn('Репутація',details)
        self.assertNotIn(g.weapon['name'],details);self.assertNotIn('Голод',details)
        self.assertIn(f'[{g.x}; {g.y}]',details)


if __name__=='__main__':unittest.main()
