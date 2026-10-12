import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import entity_catalog
import special_sites
from game.model import Game


class SpecialSitesTests(unittest.TestCase):
    def definition(self,**updates):
        value=dict(name='Тестова крамниця',npc='Марта',npc_art='npc:mayor',role='both',refresh_turns=20,
                   stock=[dict(kind='food',item_id='item_food',amount=6,chance=1)])
        value.update(updates);return value

    def test_catalog_valid_and_new_game_add_delete_roles(self):
        store=entity_catalog.Store()
        self.assertEqual(special_sites.validate(store.data['special_sites'],store.art,store.data['equipment'],store.data['modules'],store.data['consumables']),[])
        with patch('special_sites.load',return_value={'test_site':self.definition()}):
            g=Game(5);self.assertEqual(len(g.special_sites),1)
            site=g.special_sites[0];g.discover(site['id']);g.x,g.y=site['pos']
            self.assertIn(g.city,g.mayors);self.assertIn(0,g.city_merchants[g.city])
            self.assertEqual(g.merchant_title(0),'Марта')
        with patch('special_sites.load',return_value={}):self.assertEqual(Game(5).special_sites,[])

    def test_exact_stock_stable_and_refreshes_after_config_edit(self):
        d=self.definition()
        with patch('special_sites.load',return_value={'test_site':d}):
            g=Game(5);site=g.special_sites[0];g.discover(site['id']);g.x,g.y=site['pos']
            stock=g.stock(0)
            self.assertEqual([(i['type_id'],i['qty']) for i in stock],[('item_food',6)])
            state=g.rng.getstate();self.assertIs(g.stock(0),stock);self.assertEqual(g.rng.getstate(),state)
            d['stock']=[dict(kind='med',item_id='item_med',amount=2,chance=1)]
            self.assertEqual([(i['type_id'],i['qty']) for i in g.stock(0)],[('item_med',2)])
            previous=copy.deepcopy(g.stock(0));g.turn+=20
            self.assertNotEqual(g.stock(0)[0]['id'],previous[0]['id'])

    def test_saved_positions_ids_progress_preserved_and_metadata_updates(self):
        d=self.definition()
        with patch('special_sites.load',return_value={'test_site':d}),tempfile.TemporaryDirectory() as folder:
            g=Game(5);site=g.special_sites[0];g.discover(site['id']);g.x,g.y=site['pos']
            before=copy.deepcopy(site);path=Path(folder)/'save.json';g.save(path)
            d.update(name='Нова назва',npc='Інший мешканець',role='quest')
            loaded=Game.load(path);site=loaded.special_sites[0]
            for key in ('id','pos','city_id','found'):self.assertEqual(site[key],before[key])
            self.assertEqual(site['name'],'Нова назва');self.assertEqual(loaded.city_merchants[site['city_id']],[])
            self.assertIn(site['city_id'],loaded.mayors)

    def test_random_categories_specific_gear_and_chance(self):
        g=Game(5)
        d=self.definition(stock=[dict(kind='food',amount=3,chance=1),dict(kind='weapon',item_id='weapon_ash_pistol',amount=2,rarity_min=1,rarity_max=1,chance=1),dict(kind='med',amount=9,chance=0)])
        stock=special_sites.generate_stock(g,d)
        self.assertEqual(len(stock),3)
        self.assertEqual(stock[0]['kind'],'food')
        self.assertTrue(all(i['type_id']=='weapon_ash_pistol' and i['rarity']==1 for i in stock[1:]))
