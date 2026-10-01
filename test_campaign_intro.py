import tempfile
import unittest
from pathlib import Path
import afterdays as r
import campaign_intro as intro
from entity_catalog import Store


class CampaignIntroTests(unittest.TestCase):
    def game(self,seed=5):
        game=r.Game(seed);game.prepare_campaign();return game

    def triggered(self):
        game=self.game();self.assertTrue(game.step(1,0));self.assertIsNone(intro.pending(game))
        self.assertTrue(game.step(1,0));self.assertEqual(intro.pending(game),intro.STORY_ID)
        return game

    def test_catalog_and_safe_start_across_seeds(self):
        self.assertEqual(Store(Path(__file__).parent).validate(),[])
        for seed in range(15):
            game=self.game(seed)
            self.assertEqual((game.x,game.y),(1,1));self.assertNotIn(0,game.known_cities)
            self.assertTrue(all(game.passable(x,y) for y in range(4) for x in range(4)))
            self.assertIn(tuple(game.cities[0]),game.player_reachable_world((game.x,game.y)))
            self.assertTrue(game.step(1,0));self.assertTrue(game.step(1,0))
            self.assertFalse(game.battle);self.assertFalse(game.road_event)
            self.assertEqual(intro.pending(game),intro.STORY_ID)

    def test_only_successful_world_moves_trigger_and_radio_blocks_more_steps(self):
        game=self.game();self.assertFalse(game.start_story(intro.STORY_ID))
        self.assertFalse(game.step(0,0));self.assertFalse(game.step(-2,0))
        self.assertEqual(game.reputation_state['campaign_intro']['moves'],0)
        game.step(1,0);game.step(1,0);pos=(game.x,game.y)
        self.assertFalse(game.step(1,0));self.assertEqual((game.x,game.y),pos)

    def test_all_answers_award_exact_xp_reveal_city_and_local_reputation(self):
        for reply,xp in [('trader',5),('supplies',1),('hands',1)]:
            game=self.triggered();session=game.story_session(intro.STORY_ID)
            old_xp=game.xp;old_rep=[game.reputation(i) for i in range(len(game.cities))]
            session.choose(reply)
            self.assertEqual(game.xp-old_xp,xp);self.assertIn(0,game.known_cities)
            self.assertTrue(game.revealed(*game.cities[0]));self.assertEqual(game.reputation(0),old_rep[0])
            session.choose('agree')
            self.assertEqual(game.reputation(0)-old_rep[0],5)
            self.assertEqual([game.reputation(i) for i in range(1,len(game.cities))],old_rep[1:])
            self.assertIsNone(intro.pending(game))
            self.assertEqual(game.story_states()[intro.STORY_ID]['index'],1)
            with self.assertRaises(ValueError):session.choose('agree')
            self.assertEqual(game.xp-old_xp,xp);self.assertEqual(game.reputation(0)-old_rep[0],5)

    def test_save_after_one_step_and_mid_dialogue(self):
        game=self.game();game.step(1,0)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'campaign.json';game.save(path);game=r.Game.load(path)
            self.assertEqual((game.x,game.y),(2,1));game.step(1,0)
            game.story_session(intro.STORY_ID).choose('trader');xp=game.xp
            game.save(path);game=r.Game.load(path)
            session=game.story_session(intro.STORY_ID);self.assertEqual(session.current,'invitation')
            session.choose('agree');self.assertEqual(game.xp,xp);self.assertEqual(game.reputation(0),5)
            game.save(path);game=r.Game.load(path)
            self.assertIsNone(intro.pending(game));self.assertFalse(game.start_story(intro.STORY_ID))

    def test_existing_save_keeps_position_and_does_not_auto_start(self):
        game=r.Game(5);position=(game.x,game.y)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'old.json';game.save(path);game=r.Game.load(path)
        self.assertEqual((game.x,game.y),position)
        self.assertNotIn('campaign_intro',game.reputation_state)
        self.assertIsNone(intro.pending(game))


if __name__=='__main__':unittest.main()
