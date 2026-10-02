import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from adventure_ui import Effects

class EventNoticeTests(unittest.TestCase):
    def setup_effects(self,scene='world'):
        event=dict(kind='text',scene=scene,text='Reward',pos=[1,1],entity='player',color='white')
        game=SimpleNamespace(road_event={'kind':'event'},battle=None,_last_battle=None,
                             pop_events=Mock(return_value=[event]),x=1,y=1)
        app=SimpleNamespace(game=game,root=Mock(),canvas=Mock(),dialog=None,
                            ox=0,oy=0,vx=0,vy=0,tile=32,refresh=Mock(),draw=Mock())
        fx=Effects(app)
        app.canvas.winfo_width.return_value=420;app.canvas.winfo_height.return_value=320
        app.canvas.bbox.return_value=(10,10,160,30)
        with patch('adventure_ui.time.monotonic',return_value=100):fx.ingest()
        game.pop_events.return_value=[]
        return app,fx

    def test_pending_event_keeps_notice_hidden_and_alive_until_choice(self):
        app,fx=self.setup_effects()
        with patch('adventure_ui.time.monotonic',return_value=130):fx.tick()
        self.assertEqual(len(fx.active),1)
        app.canvas.create_text.assert_not_called()
        self.assertFalse(fx.blocked)
        app.game.road_event=None
        with patch('adventure_ui.time.monotonic',return_value=140):fx.tick()
        self.assertEqual(fx.active[0]['start'],140)
        self.assertEqual(app.canvas.create_text.call_count,2)
        with patch('adventure_ui.time.monotonic',return_value=143.6):fx.tick()
        self.assertFalse(fx.active)

    def test_followup_modal_keeps_results_paused(self):
        app,fx=self.setup_effects();app.game.road_event=None;app.dialog=object()
        with patch('adventure_ui.time.monotonic',return_value=120):fx.tick()
        app.canvas.create_text.assert_not_called()
        app.dialog=None
        with patch('adventure_ui.time.monotonic',return_value=150):fx.tick()
        self.assertEqual(fx.active[0]['start'],150)
        self.assertEqual(app.canvas.create_text.call_count,2)

    def test_combat_text_is_not_paused(self):
        app,fx=self.setup_effects('battle')
        self.assertNotIn('paused_at',fx.active[0])
        with patch('adventure_ui.time.monotonic',return_value=102):fx.tick()
        self.assertFalse(fx.active)

    def test_loading_another_game_discards_paused_notices(self):
        app,fx=self.setup_effects()
        app.game=SimpleNamespace(road_event=None,_last_battle=None,pop_events=lambda:[])
        fx.ingest()
        self.assertFalse(fx.active)

    def test_world_notices_are_serial_across_batches_and_pause(self):
        app,fx=self.setup_effects()
        app.game.pop_events.return_value=[dict(kind='text',scene='world',text='Second',pos=[1,1],entity='player',color='green')]
        with patch('adventure_ui.time.monotonic',return_value=120):fx.ingest()
        app.game.pop_events.return_value=[];app.game.road_event=None
        with patch('adventure_ui.time.monotonic',return_value=140):fx.tick()
        first,second=fx.active
        self.assertGreaterEqual(first['duration'],2.0)
        self.assertLessEqual(first['duration'],4.0)
        self.assertGreaterEqual(second['start']-first['start'],first['duration']+.34)
        self.assertEqual(app.canvas.create_text.call_count,2)

    def test_world_text_is_shifted_inside_map_edges(self):
        app,fx=self.setup_effects();app.game.road_event=None
        app.canvas.bbox.return_value=(-55,-35,100,-5)
        with patch('adventure_ui.time.monotonic',return_value=100):fx.render()
        self.assertEqual(app.canvas.move.call_args.args[1:],(63,43))
        self.assertEqual(app.canvas.create_text.call_args.kwargs['width'],396)
