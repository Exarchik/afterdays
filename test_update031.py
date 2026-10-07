"""Regression coverage for workshop, durability, settlement and map changes."""
import copy,math,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock
import afterdays as r
import progression as p
import module_rules as mr
import content,world_layout,frontier,expedition_ui,item_actions

class Update031Tests(unittest.TestCase):
    def test_upgrade_cost_limit_and_save(self):
        """Upgrades preserve identity/modules/condition and cannot be bought a fourth time."""
        g=r.Game(1);g.xp=p.xp_for_level(4);g.money=999999;w=g.weapon;w['durability']=43
        mod=p.module(index=0);w['modules']=[mod];uid=w['id'];before=copy.deepcopy(w)
        for n in range(1,4):
            old=w['value'];cash=g.money;self.assertTrue(g.upgrade_item(uid))
            self.assertEqual(w['level'],n+1);self.assertEqual(w['upgrades'],n)
            self.assertEqual(w['durability'],43);self.assertEqual(w['modules'],[mod])
            self.assertEqual(cash-g.money,w['value']-old)
            fresh=p.equipment(before['type_id'],before['rarity'],level=n+1)
            self.assertEqual(w['stats'],fresh['stats'])
        self.assertFalse(g.upgrade_item(uid))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
            self.assertEqual(h.weapon,w)
    def test_upgrade_restrictions_and_module_bonus(self):
        """Invalid purchases are atomic; a module retains its rarity and tradeoff."""
        g=r.Game(2);g.xp=p.xp_for_level(5);m=p.module(2,index=0,level=4);g.bag.append(m)
        g.money=0;before=copy.deepcopy(m);self.assertFalse(g.upgrade_item(m['id']));self.assertEqual(m,before)
        g.money=100000;self.assertTrue(g.upgrade_item(m['id']))
        self.assertEqual(m['stats'],mr.module_stats(m['type_id'],2,5,m['tradeoff']))
        m['quest_id']='test';self.assertIsNone(g.upgrade_quote(m['id']))
        g.start_battle();self.assertIsNone(g.upgrade_quote(g.weapon['id']))
    def test_craft_location_level(self):
        """Successful crafts inherit workshop location level, not player level."""
        g=r.Game(4);g.xp=p.xp_for_level(12);g.bag=[p.parts(150)]
        self.assertTrue(g.craft_module('parts',150));self.assertEqual(g.bag[-1]['level'],g.region_level)
        self.assertNotEqual(g.bag[-1]['level'],g.level)
    def test_remove_all_atomic(self):
        """Bulk removal keeps module identity and rejects capacity-breaking changes."""
        g=r.Game(2);w=g.weapon;mods=[p.module(index=0),p.module(index=1)];w['modules']=mods[:]
        self.assertIn(('remove_modules',()),item_actions.personal_actions(g,w))
        self.assertTrue(g.remove_modules(w['id']));self.assertEqual(w['modules'],[])
        self.assertTrue(all(m in g.bag for m in mods))
        a=g.equipped['armor'];a['modules']=[p.module(4,index='module_polyfiber')]
        heavy=p.equipment('weapon_ash_pistol');heavy['weight']=g.capacity-g.weight;g.bag.append(heavy)
        before=copy.deepcopy((g.bag,g.equipped));self.assertFalse(g.remove_modules(a['id']))
        self.assertEqual((g.bag,g.equipped),before)
    def test_strength_wear_and_local_defense(self):
        """Strength changes wear, while an emergency frame penalizes only its own armor."""
        g=r.Game(3);armor=g.equipped['armor'];armor['modules']=[p.module(index=12)]
        self.assertEqual(mr.max_condition(armor),100)
        for rank in range(4):
            g.perks['engineer']=rank;armor['durability']=100
            g.wear(armor,1);self.assertEqual(armor['durability'],round(100-1.2*(1-.15*rank),2))
        helmet=g.equipped['helmet'];armor['modules']=[p.module(index=17)]
        armor['durability']=100
        self.assertEqual(g.defense,round(armor['stats']['defense']*.8)+helmet['stats']['defense'])
    def test_local_damage_excludes_player_bonus(self):
        """Rangefinder penalty affects weapon damage, not the player-level contribution."""
        w=p.equipment('weapon_ash_pistol',2,level=5);w['modules']=[p.module(index=5)]
        self.assertEqual(mr.shot_damage(w,10),round(w['stats']['damage']*.85)+18)
    def test_weights_and_module_curves(self):
        """New weights, attack and defense curves match the requested module definitions."""
        for key,weight in [('carbon_grip',.1),('tactical_grip',1.5),('lead_fibers',1.5),('polyfiber',.05),('synthetic_fiber',.05)]:
            m=p.module(index='module_'+key);self.assertEqual(m['weight'],weight)
        for tier in range(5):
            self.assertEqual(p.module(tier,index='module_carbon_grip')['stats']['attack'],tier+1)
            self.assertEqual(p.module(tier,index='module_polyfiber')['stats']['defense'],tier+1)
        self.assertNotIn('weight_percent',p.module(index='module_tactical_grip')['stats'])
        self.assertNotIn('weight_percent',p.module(index='module_lead_fibers')['stats'])
    def test_stash_high_level_withdrawal(self):
        """High-level gear may be retrieved, while equipping it is still level-restricted."""
        g=r.Game(2);w=p.equipment('weapon_ash_pistol',level=12);g.stash=[w]
        self.assertTrue(g.stash_transfer(w['id'],'withdraw'));self.assertIn(w,g.bag)
        self.assertFalse(g.equip(w['id'],'weapon2'))
    def test_mayor_recruit_lifecycle(self):
        """Only a visited town without a mayor enables recruitment; arrival replaces its board."""
        g=r.Game(3);city=next(i for i in range(12) if i not in g.mayors)
        self.assertIsNone(g.create_settler('mayor'))
        g.x,g.y=g.cities[city];g.remember_visit();n=g.create_settler('mayor')
        self.assertIsNotNone(n);self.assertTrue(g.recruit(n['id']))
        q=g.quests[-1];self.assertTrue(g.authorize_settlement(q['id']))
        self.assertTrue(g.turn_in(q['id']));self.assertNotIn(city,g.mayors)
        g.turn=n['arrival'];g.process_settlers();self.assertIn(city,g.mayors)
        self.assertEqual(n['state'],'settled')
    def test_city_guides_and_metro_distribution(self):
        """City guides offer five reachable towns and metro covers the map length."""
        for seed in range(10):
            g=r.Game(seed);xs=sorted(g.cities[i][0] for i in frontier.METRO_CITIES)
            self.assertEqual(len(xs),5);self.assertLessEqual(xs[0],5)
            self.assertGreaterEqual(xs[-1],world_layout.WIDTH*.8)
            self.assertLessEqual(max(b-a for a,b in zip(xs,xs[1:])),world_layout.WIDTH*.4)
        g.reputation_state['border_open']=True;g.known_cities=list(range(g.main_city_count))
        for city in range(12):
            g.x,g.y=g.cities[city]
            if g.city_guide:break
        self.assertTrue(g.city_guide);self.assertEqual(len(g.guide_destinations()),5)
        self.assertEqual(g.guide_destinations(),sorted(g.guide_destinations(),key=lambda c:c['distance']))
    def test_defense_boundary(self):
        """The drawn perimeter encloses exactly the cells accepted by defense quest distance checks."""
        g=r.Game(1);q=dict(kind='hunt',city=0,status='active',progress=0,goal=5,target_kind=None,level=1)
        g.quests=[q];cells=expedition_ui.defense_cells(g,q)
        self.assertIn((15,5),cells);self.assertIn((15,6),cells);self.assertNotIn((16,5),cells)
        c=MagicMock();expedition_ui.draw_search_areas(c,g,10,0,0)
        self.assertTrue(c.create_line.called)
        q['status']='done';c.reset_mock();expedition_ui.draw_search_areas(c,g,10,0,0);c.create_line.assert_not_called()

if __name__=='__main__':unittest.main()
