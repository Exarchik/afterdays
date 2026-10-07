import copy
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
import quest_area
import world_hex
import world_map
import test_scavenging
import test_expeditions
import test_metro035


class QuestHexAreaTests(unittest.TestCase):
    def test_both_row_parities(self):
        for y in (10,11):
            q={'area':[9,y-1,11,y+1]}
            zone=quest_area.cells(q)
            self.assertEqual(len(set(zone)),7)
            self.assertTrue(all(world_hex.distance((10,y),p)<=1 for p in zone))
            self.assertEqual(sum(quest_area.contains(q,x,yy) for x in range(9,12) for yy in range(y-1,y+2)),7)

    def test_scout_counts_only_seven_and_draws_hex_perimeter(self):
        g,q=test_scavenging.ScavengingTests().quest('scout')
        zone=quest_area.cells(q);a,b,c,d=q['area']
        for y in range(b,d+1):
            for x in range(a,c+1):
                if (x,y) not in zone:g.x,g.y=x,y;g._visit_objectives()
        self.assertEqual(q['progress'],0)
        canvas=MagicMock();view=world_map.layout(800,600,112,32,q['pos'])
        world_map.draw_areas(canvas,g,view)
        self.assertEqual(canvas.create_line.call_count,18)
        for n,pos in enumerate(zone):
            g.x,g.y=pos;g._visit_objectives();g._visit_objectives()
            self.assertEqual(q['progress'],n+1)
        self.assertEqual(q['goal'],7);self.assertTrue(g.quest_ready(q))

    def test_search_targets_and_access(self):
        for kind in ('retrieve','cache'):
            fixture=test_scavenging.ScavengingTests()
            g,q=fixture.quest(kind);zone=quest_area.cells(q)
            target=q['relic_pos' if kind=='retrieve' else 'cache_pos']
            self.assertIn(tuple(target),zone)
            a,b,c,d=q['area']
            for x,y in ((x,y) for y in range(b,d+1) for x in range(a,c+1)):
                g.x,g.y=x,y
                self.assertEqual(g.local_expedition() is q,(x,y) in zone)
            self.assertTrue(all(p in g.player_reachable_world(g.cities[q['city']]) for p in zone))

    def test_old_targets_relocated_and_migration_idempotent(self):
        for kind,key in (('retrieve','relic_pos'),('cache','cache_pos')):
            fixture=test_scavenging.ScavengingTests();g,q=fixture.quest(kind)
            q.pop('area_shape');a,b,c,d=q['area'];zone=quest_area.cells(q)
            excluded=next([x,y] for y in range(b,d+1) for x in range(a,c+1) if (x,y) not in zone)
            q[key]=excluded;q['searched_cells']=list(map(list,zone))+[excluded]
            h=fixture.save_reload(g);converted=h.quests[-1]
            self.assertIn(tuple(converted[key]),zone)
            self.assertNotIn(converted[key],converted['searched_cells'])
            before=copy.deepcopy(converted);quest_area.migrate(converted);self.assertEqual(before,converted)
            h.x,h.y=converted[key];self.assertTrue(h.search())

    def test_completed_old_scout_stays_complete(self):
        fixture=test_scavenging.ScavengingTests();g,q=fixture.quest('scout')
        q.pop('area_shape');q.update(goal=9,progress=9)
        h=fixture.save_reload(g);q=h.quests[-1]
        self.assertEqual(q['progress'],7);self.assertEqual(q['goal'],7)
        self.assertTrue(h.quest_ready(q))

    def test_nested_metro_cache_migration(self):
        q=dict(kind='cache',area=[9,9,11,11],cache_pos=[11,9],searched_cells=[],progress=0,goal=1)
        parent={'metro_chain':{'steps':[q]}}
        quest_area.migrate_game(SimpleNamespace(quests=[parent]))
        self.assertIn(tuple(q['cache_pos']),quest_area.cells(q))
        for seed in range(3):
            g,parent=test_metro035.MetroTests().make(seed+2)
            for step in parent['metro_chain']['steps']:
                if step.get('area'):
                    self.assertEqual(len(quest_area.cells(step)),7)
                    self.assertIn(tuple(step['cache_pos']),quest_area.cells(step))
