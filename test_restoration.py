import tempfile,unittest
from pathlib import Path
import game.model as r
from tests_fixtures.quest_offer import offer_for

class RestorationTests(unittest.TestCase):
    def reload(self,g):
        """Готує або імітує операцію «reload» для перевірок RestorationTests."""
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);return r.Game.load(path)

    def map_game(self):
        """Готує або імітує операцію «map game» для перевірок RestorationTests."""
        g=r.Game(4);q=offer_for(g,'torn_map');self.assertTrue(g.accept_quest(q['id']));return g,g.quests[-1]

    def solve(self,g,q):
        """Готує або імітує операцію «solve» для перевірок RestorationTests."""
        for i in range(9):
            if q['layout'][i]!=i:self.assertTrue(g.swap_map_pieces(q['id'],i,q['layout'].index(i)))

    def test_puzzle_saved_hidden_then_revealed_and_reward_once(self):
        """Перевіряє сценарій «puzzle saved hidden then revealed and reward once» та очікувані результати."""
        g,q=self.map_game();ident=q['id'];self.assertIsNone(q['pos']);self.assertFalse(g.quest_ready(q))
        self.assertLessEqual(g.region_at(*q['stash_pos']),q['level']+1)
        g=self.reload(g);q=g.map_quest(ident);self.solve(g,q)
        self.assertEqual(q['pos'],q['stash_pos']);self.assertTrue(g.revealed(*q['pos']))
        g.x,g.y=q['pos'];g.road_event=None;g.loot=[];self.assertTrue(g.search());loot=list(g.loot)
        self.assertTrue(g.quest_ready(q));self.assertEqual(q['contents'],[])
        self.assertFalse(g.swap_map_pieces(ident,0,1));self.assertEqual(g.loot,loot)
        g.x,g.y=g.cities[q['city']];self.assertTrue(g.turn_in(ident));money=g.money
        self.assertFalse(g.turn_in(ident));self.assertEqual(g.money,money)

    def test_invalid_moves_and_battle(self):
        """Перевіряє сценарій «invalid moves and battle» та очікувані результати."""
        g,q=self.map_game();original=q['layout'][:]
        for a,b in ((-1,2),(0,9),(True,2),(2.5,0)):
            self.assertFalse(g.swap_map_pieces(q['id'],a,b))
        g.battle={"active":True};self.assertFalse(g.swap_map_pieces(q['id'],0,1));self.assertEqual(q['layout'],original)

    def test_recruit_both_roles_permission_return_delay_save(self):
        """Перевіряє сценарій «recruit both roles permission return delay save» та очікувані результати."""
        for role in ('smith','tech'):
            g=r.Game(4);g.reputation_state['visited_cities'].append(g.eligible_settlements(role)[0]);g.x,g.y=g.cities[g.eligible_settlements(role)[0]];n=g.create_settler(role);self.assertIsNotNone(n)
            self.assertTrue(g.recruit(n['id']));q=g.quests[-1];ident=q['id'];pos=n['pos'][:]
            city=g.eligible_settlements(role)[0];g.x,g.y=g.cities[city]
            self.assertTrue(g.authorize_settlement(ident));self.assertNotIn(city,g.eligible_settlements(role))
            self.assertFalse(g.authorize_settlement(ident))
            g.x,g.y=pos;self.assertTrue(g.turn_in(ident));self.assertFalse(g.turn_in(ident))
            self.assertTrue(10<=n['arrival']-g.turn<=15)
            g=self.reload(g);n=g.settlers()[0]
            g.turn=n['arrival']-1;g.process_settlers();self.assertEqual(n['state'],'travelling')
            g.turn+=1;g.process_settlers();self.assertEqual(n['state'],'settled')
            self.assertTrue(0 in g.city_merchants[city] if role=='smith' else city in g.technicians)
            before=list(g.city_merchants[city]);g.process_settlers();self.assertEqual(before,g.city_merchants[city])

    def test_no_missing_service_no_encounter(self):
        """Перевіряє сценарій «no missing service no encounter» та очікувані результати."""
        g=r.Game(4)
        for city in range(12):
            if 0 not in g.city_merchants[city]:g.city_merchants[city].append(0)
            if city not in g.technicians:g.technicians.append(city)
        self.assertIsNone(g.create_settler('smith'));self.assertIsNone(g.create_settler('tech'))

    def test_abandon_releases_city_and_removes_permit(self):
        """Перевіряє сценарій «abandon releases city and removes permit» та очікувані результати."""
        g=r.Game(4);g.reputation_state['visited_cities'].append(g.eligible_settlements('smith')[0]);g.x,g.y=g.cities[g.eligible_settlements('smith')[0]];n=g.create_settler('smith');g.recruit(n['id']);q=g.quests[-1]
        city=g.eligible_settlements('smith')[0];g.x,g.y=g.cities[city];g.authorize_settlement(q['id'])
        self.assertTrue(g.abandon_quest(q['id']));self.assertIn(city,g.eligible_settlements('smith'))
        self.assertFalse(any(i.get('quest_id')==q['id'] for i in g.bag));self.assertEqual(n['state'],'offered')

class RestorationArtTests(unittest.TestCase):
    def test_coverage_for_quests_events_and_species(self):
        """Перевіряє сценарій «coverage for quests events and species» та очікувані результати."""
        import sprites
        import event_art
        import game.systems.adventure as adventure
        import content
        from tools.build_expansion029 import QUESTS,KEYS
        for kind in QUESTS:self.assertIn('quest:'+kind,sprites.MANIFEST)
        self.assertFalse({e[0] for e in adventure.ROAD_EVENTS}-event_art.EVENT_ART.keys())
        for key in event_art.EVENT_ART.values():self.assertIn(key,sprites.MANIFEST)
        for ident in content.MONSTER_IDS:self.assertIn('corpse:'+ident,sprites.MANIFEST)
        self.assertEqual(len(KEYS),73)
        for key in KEYS:
            entry=sprites.MANIFEST[key]
            self.assertTrue(0<=entry['index']<73)
            for size in sprites.SIZES:self.assertTrue((sprites.ROOT/f"{entry['sheet']}_{size}.png").is_file())
        self.assertEqual(sprites.npc_key('hunter'),'npc_hunter')
        self.assertEqual(sprites.quest_key({'kind':'retrieve','metro_city':1}),'quest:metro')

if __name__=='__main__':unittest.main()
