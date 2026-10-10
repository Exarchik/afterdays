"""Player-level quest limits, retreat, goods, world generation and new encounters."""
import copy,json,tempfile,unittest,math
from pathlib import Path
from unittest.mock import patch
import game.model as r
import game.progression as progression
import game.items as p
import game.systems.adventure as adventure
import road_additions
from game.systems.leveled_contracts import level_limit
from game.systems.loot import halve_new_loot

class Update032Tests(unittest.TestCase):
    def test_capacity_table(self):
        """Level ceilings combine with reputation rather than increasing it."""
        g=r.Game(3);g.record_at(g.cities[0])['value']=100
        with patch.object(type(g),'region_at',return_value=7):
            for level,expected in [(1,0),(4,0),(5,1),(6,2),(7,5),(8,5),(9,3),(10,2),(11,1),(15,1)]:
                g.xp=progression.xp_for_level(level);self.assertEqual(g.quest_capacity(0),expected)
    def test_actual_offer_limits_and_medal(self):
        """Mayors expose no more than the computed ceiling, and medal level is snapshotted."""
        g=r.Game(4);g.record_at(g.cities[0])['value']=100
        for level in (1,2,3,4,5,10):
            g.xp=progression.xp_for_level(level)
            self.assertLessEqual(len(g.mayor_offers()),g.quest_capacity(0))
        g.quests.append(dict(id='thanks',kind='thanks',status='done',city=0,progress=1,goal=1))
        q=g.mayor_offers()[0];self.assertEqual(q['level'],2)
        saved=copy.deepcopy(q);g.xp=progression.xp_for_level(3);g.price_quest(q);self.assertEqual(q['level'],2)
    def test_upgrade_and_known_guides(self):
        """Items cannot upgrade beyond player level and guides only offer known destinations."""
        g=r.Game(2);g.money=999999;self.assertIsNone(g.upgrade_quote(g.weapon['id']))
        g.xp=progression.xp_for_level(2);self.assertTrue(g.upgrade_item(g.weapon['id']));self.assertIsNone(g.upgrade_quote(g.weapon['id']))
        g.reputation_state['border_open']=True
        with patch.object(type(g),'city_guide',new_callable=__import__('unittest').mock.PropertyMock,return_value=True):
            g.known_cities=[0,2,3];choices=g.guide_destinations();self.assertTrue(all(x['city'] in (2,3) for x in choices));self.assertLessEqual(len(choices),2)
    def test_scribe_accept_return_and_save(self):
        """Scribe contracts can be accepted on the road and returned at their recorded nearest town."""
        g=r.Game(8);g.x,g.y=6,5;g.spawn_scribe();offers=g.mayor_offers()
        self.assertIn(len(offers),(1,2,3));self.assertTrue(g.scribe);self.assertFalse(g.available_merchant(3))
        q=next((q for q in offers if q['kind']=='supplies'),None)
        if q is None:
            q=offers[0];q.update(kind='supplies',food_need=2,med_need=1,goal=1);g.price_quest(q)
        self.assertTrue(g.accept_quest(q['id']));taken=g.quests[-1]
        self.assertEqual(taken['city'],min(range(g.main_city_count),key=lambda i:math.dist(g.cities[i],(6,5))))
        self.assertFalse(g.can_turn_in(taken));g.x,g.y=g.cities[taken['city']];g.traveler=None
        self.assertTrue(g.turn_in(taken['id']))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'s.json';g.save(path);h=r.Game.load(path);self.assertEqual(h.quests,g.quests)
    def test_retreat_xp_ap_sleep_expiry(self):
        """Retreat from the middle costs no exit-cell check; all debuff effects expire or clear on sleep."""
        g=r.Game(2);g.start_battle();g.battle['pos']=[3,3];g.battle['ap']=0
        self.assertTrue(g.flee());self.assertEqual(g.coward_turns,50);self.assertEqual(g.max_ap,5)
        before=g.xp;g.gain_xp(21);self.assertEqual(g.xp-before,10)
        g.turn+=50;self.assertEqual(g.coward_turns,0);self.assertEqual(g.max_ap,6)
        g.reputation_state['coward_until']=g.turn+50;self.assertTrue(g.rest());self.assertEqual(g.coward_turns,0)
    def test_quest_xp_penalty_and_save(self):
        """Direct quest rewards also receive the XP penalty and the timer survives reload."""
        g=r.Game(3);q=dict(id='s',title='Supplies',kind='supplies',city=0,status='active',progress=0,goal=1,food_need=1,med_need=1,reward=20,xp_reward=41,level=1,unique=False)
        g.quests=[q];g.reputation_state['coward_until']=g.turn+50;before=g.xp
        self.assertTrue(g.turn_in('s'));self.assertEqual(g.xp-before,20)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'s.json';g.save(path);h=r.Game.load(path);self.assertEqual(h.coward_turns,g.coward_turns)
    def test_dungeon_exit_no_new_debuff(self):
        """Dungeon exit requires its exact cell and never creates a retreat debuff."""
        g=r.Game(4);g.battle=dict(dungeon=True,pos=[1,1],exit=[0,0],cleared=False)
        self.assertFalse(g.flee());g.battle['pos']=[0,0];self.assertTrue(g.flee());self.assertEqual(g.coward_turns,0)
    def test_loot_preserves_previous_stacks(self):
        """Thinning never removes pre-existing loot, even when a new drop merged into its stack."""
        g=r.Game(1);old=p.supply('food',4);g.loot=[old];before={old['id']:4};old['qty']=10;g.loot.append(p.module())
        with patch.object(g.rng,'random',return_value=.9):halve_new_loot(g,before)
        self.assertEqual(g.loot,[old]);self.assertEqual(old['qty'],4)
    def test_rarity_all_sources(self):
        """Rewards, shops, sealed contents and crafting respect unlock thresholds."""
        g=r.Game(1)
        for level,cap in [(1,2),(4,2),(5,3),(6,3),(7,4)]:
            g.xp=progression.xp_for_level(level);self.assertEqual(g.rarity_cap,cap)
            for _ in range(10):self.assertLessEqual(g.reward_item(4,4)['rarity'],cap)
            for m in (0,1,2):
                for item in g.stock(m):self.assertLessEqual(item.get('contents',item).get('rarity',0),cap)
            self.assertEqual(sum(g.craft_odds(1000)[cap+1:]),0)
    def test_world_sizes_levels_and_margins(self):
        """New towns/sites stay inside a one-cell margin and level progression spans NW to SE."""
        for seed in range(4):
            g=r.Game(seed);self.assertEqual((len(g.world[0]),len(g.world),g.main_city_count),(112,32,15))
            for x,y in g.cities+[s['pos'] for s in g.special_sites]:self.assertTrue(1<=x<111 and 1<=y<31)
            self.assertEqual(g.region_at(5,5),1);self.assertEqual(g.region_at(111,31),15)
            self.assertEqual(g.region_at(0,31),5);self.assertEqual(g.region_at(5,31),5);self.assertEqual(g.region_at(111,0),11)
            self.assertTrue(all(g.region_at(x,y)<=5 for x in range(6) for y in range(32)))
            self.assertEqual([g.region_at(x,20) for x in range(112)],sorted(g.region_at(x,20) for x in range(112)))
    def test_twenty_events_and_promotion(self):
        """All twenty new events register; travellers can receive stable discounted stock."""
        g=r.Game(4);rows=[e for e in __import__('event_catalog').EVENTS if e.get('legacy_release')=='0.32'];self.assertEqual(len(rows),20)
        for row in rows:
            self.assertIn(row['id'],road_additions.BY_KEY);g.road_event=None;self.assertTrue(g.make_road_event(row['id']));self.assertTrue(g.resolve_event('leave'))
        g.road_event=None;g.x,g.y=6,5;g.record_at(g.cities[0])['value']=100
        g.traveler=dict(pos=[6,5],items=[p.equipment('weapon_ash_pistol')],rep_reserve=[],rep_total=0,rep_released=0)
        with patch.object(g.rng,'random',return_value=.1):items=g.stock(3)
        self.assertTrue(any(i.get('promotion') for i in items))
        item=next(i for i in items if i.get('promotion'));self.assertGreater(g.promotion(item,3),0)
        self.assertLess(g.price(item,3,False),g.price(item,3,True))

if __name__=='__main__':unittest.main()
