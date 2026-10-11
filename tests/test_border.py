import json
import math
import tempfile
import unittest
from pathlib import Path
import game.model as r
from ui.border import draw_border

class BorderTests(unittest.TestCase):
    def test_hidden_reputation_radius_no_cascade(self):
        """Перевіряє сценарій «hidden reputation radius no cascade» та очікувані результати."""
        g=r.Game(10)
        # Near (10), just outside (11), and chain-connected but outside the source radius.
        g.cities[1:4]=[[15,5],[16,5],[24,5]]
        hidden=g.special_sites[0];hidden['pos']=[5,14]
        g.add_reputation(4)
        self.assertEqual(g.reputation(0),4);self.assertEqual(g.reputation(1),4)
        self.assertEqual(g.reputation(2),0);self.assertEqual(g.reputation(3),0)
        self.assertEqual(g.record_at(hidden['pos'])['value'],4);self.assertFalse(hidden['found'])
        self.assertNotIn(1,g.known_cities)
        g.discover(hidden['id']);self.assertEqual(g.reputation(hidden['city_id']),4)
        # One source has full reputation, neighbours still benefit from its actions.
        g.local_record(0)['value']=100;g.add_reputation(turnover=50,city=0)
        self.assertEqual(g.reputation(0),100);self.assertEqual(g.reputation(1),5)

    def test_zone_is_sealed_for_multiple_worlds(self):
        """Перевіряє сценарій «zone is sealed for multiple worlds» та очікувані результати."""
        for seed in range(15):
            g=r.Game(seed);inside=g.player_reachable_world(g.cities[0])
            self.assertTrue(all(g.region_at(*pos)<=2 for pos in inside))
            gates=[(a,b) for a,b in g.border_edges() if g.checkpoint(a,b)]
            self.assertTrue(gates)
            reachable_gates=[(a,b) for a,b in gates if (a if g.inside_border(a) else b) in inside]
            self.assertTrue(reachable_gates)
            for a,b in gates:
                if not g.inside_border(a):a,b=b,a
                self.assertFalse(g.can_cross(a,b))
            g.add_reputation(75,city=0);permit=next(q for q in g.quests if q['kind']=='permit')
            self.assertFalse(g.border_open);self.assertTrue(g.turn_in(permit['id']))
            self.assertTrue(g.border_open);self.assertFalse(g.turn_in(permit['id']))
            outside=g.player_reachable_world(g.cities[0]);self.assertTrue(set(map(tuple,g.cities[:12]))<=outside)
            for a,b in g.border_edges():self.assertEqual(g.can_cross(a,b),g.checkpoint(a,b))

    def test_blocked_step_does_not_spend_turn(self):
        """Перевіряє сценарій «blocked step does not spend turn» та очікувані результати."""
        g=r.Game(3)
        a,b=next((a,b) for a,b in g.border_edges() if g.checkpoint(a,b))
        if not g.inside_border(a):a,b=b,a
        g.x,g.y=a;turn=g.turn
        self.assertFalse(g.step(b[0]-a[0],b[1]-a[1]));self.assertEqual(g.turn,turn);self.assertEqual((g.x,g.y),a)
        g.add_reputation(75,city=0);q=next(q for q in g.quests if q['kind']=='permit')
        self.assertFalse(g.turn_in(q['id']));g.x,g.y=g.cities[q['city']];self.assertTrue(g.turn_in(q['id']))
        self.assertTrue(g.can_cross(a,b))

    def test_metro_cannot_bypass_gate(self):
        """Перевіряє сценарій «metro cannot bypass gate» та очікувані результати."""
        g=r.Game(4);g.quests.append(dict(kind='retrieve',metro_city=2,status='done'))
        self.assertIsNone(g.metro_cost(2))
        g.reputation_state['border_open']=True;self.assertIsNotNone(g.metro_cost(2))

    def test_new_quest_targets_are_accessible(self):
        """Перевіряє сценарій «new quest targets are accessible» та очікувані результати."""
        for seed in range(8):
            g=r.Game(seed)
            for level in (1,2):
                q=dict(id='candidate',city=0,level=level)
                self.assertTrue(g.quest_locations(q))
                self.assertTrue(all(g.inside_border(p) for p in g.quest_locations(q)))
                self.assertTrue(all(g.inside_border(s['pos']) for s in g.delivery_sites(q)))

    def test_old_reputation_keys_and_permit_save(self):
        """Перевіряє сценарій «old reputation keys and permit save» та очікувані результати."""
        g=r.Game(4);g.reputation_state['locations']={'0':dict(value=77,turnover=23)}
        g.reputation_state.pop('coordinate_keys')
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
            self.assertEqual(h.reputation(0),77);self.assertEqual(h.local_record(0)['turnover'],23)
            h.check_thanks();q=next(q for q in h.quests if q['kind']=='permit');h.turn_in(q['id'])
            h.save(path);j=r.Game.load(path);self.assertTrue(j.border_open)
            before=len(j.quests);j.check_border_quest();self.assertEqual(len(j.quests),before)

    def test_mayor_reveals_exactly_one_with_notice(self):
        """Перевіряє сценарій «mayor reveals exactly one with notice» та очікувані результати."""
        g=r.Game(2);g.local_record()['value']=51
        before=set(g.known_cities)
        for i in range(6):
            q=dict(id=str(i),kind='hunt',city=0,status='active',title='test',progress=1,goal=1,target_kind=None,reward=1,xp_reward=0,unique=False)
            g.quests.append(q);self.assertTrue(g.turn_in(q['id']))
        self.assertEqual(len(set(g.known_cities)-before),1)
        self.assertIn(g.city_name(0),g._mayor_notice)
        self.assertEqual(g.map_rewards,[0])

    def test_border_renderer_respects_fog(self):
        """Перевіряє сценарій «border renderer respects fog» та очікувані результати."""
        class Canvas:
            # Ініціалізує об’єкт, його початковий стан і потрібні залежності.
            def __init__(self):self.lines=[];self.gates=[]
            # Готує або імітує операцію «create line» для перевірок Canvas.
            def create_line(self,*a,**k):self.lines.append((a,k))
            # Готує або імітує операцію «create rectangle» для перевірок Canvas.
            def create_rectangle(self,*a,**k):self.gates.append((a,k))
        g=r.Game(1);c=Canvas();draw_border(c,g,20,0,0,lambda x,y:False)
        self.assertFalse(c.lines)
        draw_border(c,g,20,0,0,lambda x,y:True)
        self.assertEqual(len(c.lines),len(g.border_edges()));self.assertTrue(c.gates)
        self.assertTrue(all(k['fill']=='#000000' and k['dash'] for a,k in c.lines))

    def test_large_quest_cards_keep_all_entries_scrollable(self):
        """Великі іконки вміщаються в картках; усі квести доступні прокручуванням."""
        from types import SimpleNamespace
        from unittest.mock import patch
        import ui.refinement as refinement
        class Canvas:
            # Готує або імітує операцію «delete» для перевірок Canvas.
            def delete(self,*a):pass
            # Готує або імітує операцію «winfo width» для перевірок Canvas.
            def winfo_width(self):return 420
            # Готує або імітує операцію «winfo height» для перевірок Canvas.
            def winfo_height(self):return 424
            # Готує або імітує операцію «create rectangle» для перевірок Canvas.
            def create_rectangle(self,*a,**k):pass
            # Готує або імітує операцію «create text» для перевірок Canvas.
            def create_text(self,*a,**k):pass
            # Оновлює властивості віджета та форматований текст.
            def config(self,**k):self.options=k
        g=r.Game(4)
        quests=[dict(id=str(i),kind='hunt',status='active',title='Quest',city=0,progress=0,goal=1,level=1,reward=10) for i in range(8)]
        panel=SimpleNamespace(canvas=Canvas(),entries=quests,open_done=False,selection=None,app=SimpleNamespace(game=g))
        with patch('sprites.draw',return_value=False) as draw:refinement.QuestCards.paint(panel)
        cards=[(a,b) for a,b,key in panel.rects if key!='done']
        self.assertEqual(len(cards),8)
        self.assertGreater(cards[-1][1],424)
        self.assertGreater(panel.canvas.options['scrollregion'][3],cards[-1][1])
        for call,(top,bottom) in zip(draw.call_args_list,cards):
            self.assertEqual(call.args[-1],64)
            self.assertGreaterEqual(call.args[-2],top)
            self.assertLessEqual(call.args[-2]+64,bottom)
