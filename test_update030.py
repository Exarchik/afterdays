import copy,json,math,random,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
import afterdays as r
import progression as p
import monster_rules,content
from update030 import event_xp,kill_xp
from item_actions import personal_actions

class Update030Tests(unittest.TestCase):
    def test_world_size_cap_and_east_reachability(self):
        """Перевіряє сценарій «world size cap and east reachability» та очікувані результати."""
        for seed in range(6):
            g=r.Game(seed)
            self.assertEqual(len(g.world),32);self.assertEqual({len(row) for row in g.world},{112})
            self.assertEqual(g.cities[0],[5,5]);self.assertTrue(any(x>=48 for x,y in g.cities[:12]))
            self.assertEqual(max(g.region_at(x,y) for y in range(32) for x in range(112)),15)
            reachable=g.reachable_world((5,5))
            self.assertTrue(set(map(tuple,g.cities))<=reachable)
            self.assertTrue(any(x==61 for x,y in reachable))
            self.assertFalse(g.passable(112,10));self.assertFalse(g.passable(-1,10))

    def test_old_save_extends_once_without_moving_cities_or_consuming_rng(self):
        """Перевіряє сценарій «old save extends once without moving cities or consuming rng» та очікувані результати."""
        path=Path(__file__).parent/'tests_fixtures/save_v029.json';data=json.loads(path.read_text())
        g=r.Game.load(path)
        self.assertEqual(g.cities,data['cities']);self.assertEqual([row[:48] for row in g.world],data['world'])
        self.assertEqual(g.xp,data['xp']);self.assertEqual(g.explored,data['explored'])
        def tuples(v):return tuple(tuples(i) for i in v) if isinstance(v,list) else v
        self.assertEqual(g.rng.getstate(),tuples(data['rng_state']))
        self.assertTrue(g.border_edges())
        self.assertEqual(g.reputation_state['visited_cities'],[0])
        with tempfile.TemporaryDirectory() as tmp:
            save=Path(tmp)/'save.json';g.save(save);h=r.Game.load(save)
        self.assertEqual(g.world,h.world);self.assertEqual(g.rng.getstate(),h.rng.getstate())
        self.assertEqual(len(h.world[0]),112)

    def test_exploration_and_path_to_far_east(self):
        """Перевіряє сценарій «exploration and path to far east» та очікувані результати."""
        from journey import world_route
        from site_layout import road_path
        g=r.Game(4);g.reputation_state['border_open']=True
        g.reveal(61,15,2);self.assertTrue(g.revealed(61,15))
        pos=max(g.reachable_world((5,5)),key=lambda q:q[0]);self.assertEqual(pos[0],111)
        self.assertTrue(world_route(g,pos))
        self.assertTrue(road_path(g,pos))

    def test_xp_buckets_and_actual_event_rewards(self):
        """Перевіряє сценарій «xp buckets and actual event rewards» та очікувані результати."""
        self.assertEqual([event_xp(n) for n in (0,10,15,20,25,30,35,40,100)],[0,5,10,10,15,15,20,20,20])
        g=r.Game(4);before=g.xp;g.make_road_event('wounded')
        self.assertIn('20 XP',str(g.road_event['choices']))
        self.assertTrue(g.resolve_event('help'));self.assertEqual(g.xp-before,20)
        before=g.xp;g.gain_xp(40);self.assertEqual(g.xp-before,40)
        g.make_road_event('dust_archive');before=g.xp
        self.assertTrue(g.resolve_event('act'));self.assertEqual(g.xp-before,15)
        self.assertFalse(g._event_xp_context)

    def test_monster_xp_halved_and_rounded_to_five(self):
        """Перевіряє сценарій «monster xp halved and rounded to five» та очікувані результати."""
        self.assertEqual([kill_xp(n) for n in (1,12,21,22,26,41,59,70,86,125)],[5,5,10,10,15,20,30,35,45,65])
        g=r.Game(4)
        for ident in content.MONSTER_IDS:
            for grade in ('normal','rare','mythic'):
                e=monster_rules.make(g.rng,ident,15,[1,1],grade=grade)
                self.assertEqual(g.enemy_xp(e)%5,0);self.assertGreaterEqual(g.enemy_xp(e),5)
        g.xp=p.xp_for_level(100);self.assertEqual(g.enemy_xp(e),5)

    def test_discovered_town_does_not_enable_settler_but_visit_does(self):
        """Перевіряє сценарій «discovered town does not enable settler but visit does» та очікувані результати."""
        for role in ('smith','tech'):
            g=r.Game(4);city=next(c for c in g.eligible_settlements(role) if c!=0)
            g.reveal(*g.cities[city],1);self.assertIn(city,g.known_cities)
            self.assertFalse(g.recruit_candidates(role));self.assertIsNone(g.create_settler(role))
            g.x,g.y=g.cities[city];g._visit_objectives()
            self.assertIn(city,g.recruit_candidates(role));self.assertIsNotNone(g.create_settler(role))

    def gear(self,slots=3):
        """Готує або імітує операцію «gear» для перевірок Update030Tests."""
        g=r.Game(4);w=g.weapon;w.update(rarity=2,slots=slots,modules=[])
        mods=[p.module(tier=0,rng=random.Random(n),index=0,level=1) for n in range(4)]
        g.bag.extend(mods)
        return g,w,mods

    def test_quick_module_prepends_and_ejects_last_only(self):
        """Перевіряє сценарій «quick module prepends and ejects last only» та очікувані результати."""
        g,w,mods=self.gear()
        for m in mods[:3]:self.assertTrue(g.quick_module(w['id'],m['id']))
        self.assertEqual([m['id'] for m in w['modules']],[m['id'] for m in mods[2::-1]])
        self.assertTrue(g.quick_module(w['id'],mods[3]['id']))
        self.assertEqual([m['id'] for m in w['modules']],[mods[n]['id'] for n in (3,2,1)])
        self.assertEqual(sum(i['id']==mods[0]['id'] for i in g.bag),1)
        ids=[i['id'] for i in g.bag]+[i['id'] for i in w['modules']]
        self.assertEqual(len(ids),len(set(ids)))

    def test_quick_module_restrictions_and_atomic_weight_rollback(self):
        """Перевіряє сценарій «quick module restrictions and atomic weight rollback» та очікувані результати."""
        g,w,mods=self.gear();before=copy.deepcopy((g.bag,g.equipped))
        mods[0]['level']=2;self.assertFalse(g.quick_module(w['id'],mods[0]['id']));mods[0]['level']=1
        mods[0]['rarity']=4;self.assertFalse(g.quick_module(w['id'],mods[0]['id']));mods[0]['rarity']=0
        w['quest_id']='locked';self.assertFalse(g.quick_module(w['id'],mods[0]['id']));del w['quest_id']
        g.start_battle();self.assertFalse(g.quick_module(w['id'],mods[0]['id']));g.battle=None
        armor=g.equipped['armor'];armor.update(slots=1,rarity=2)
        old=dict(mods[0],id='capacity-module',target='protection',stats={'capacity':100})
        armor['modules']=[old]
        new=dict(mods[1],id='new-protection-module',target='protection',stats={'defense':2})
        g.bag.extend([new,dict(id='ballast',kind='parts',name='ballast',weight=1,qty=60,value=0)])
        before=copy.deepcopy((g.bag,g.equipped))
        self.assertFalse(g.quick_module(armor['id'],new['id']))
        self.assertEqual((g.bag,g.equipped),before)

    def test_context_actions_obey_ownership_combat_and_quest_locks(self):
        """Перевіряє сценарій «context actions obey ownership combat and quest locks» та очікувані результати."""
        g=r.Game(4);w=g.weapon
        codes=lambda item:{code for code,args in personal_actions(g,item)}
        self.assertIn('unequip',codes(w));self.assertIn('modify',codes(w));self.assertNotIn('drop',codes(w))
        loose=p.equipment(level=1);g.bag.append(loose)
        self.assertIn('equip',codes(loose));self.assertIn('dismantle',codes(loose))
        loose['quest_id']='test';self.assertNotIn('dismantle',codes(loose));self.assertNotIn('modify',codes(loose))
        self.assertEqual(personal_actions(g,dict(id='not-owned',kind='weapon')),[])
        g.start_battle();self.assertNotIn('unequip',codes(w));self.assertNotIn('equip',codes(loose))
        med=next(i for i in g.bag if i['kind']=='med');g.hp=1;g.battle['ap']=2;self.assertIn('use',codes(med))
        g.battle['ap']=1;self.assertNotIn('use',codes(med))

    def test_hud_points_colors_and_weapon_switch_cost(self):
        """Перевіряє сценарій «hud points colors and weapon switch cost» та очікувані результати."""
        from combat_hud import CombatHUD
        g=r.Game(4);g.equipped['weapon2']=p.equipment('weapon_ash_pistol',level=1);g.start_battle()
        before=g.battle['ap'];g.switch();self.assertEqual(g.battle['ap'],before)
        g.battle['ap']=2;canvas=MagicMock();canvas.winfo_width.return_value=220
        panel=SimpleNamespace(app=SimpleNamespace(game=g),points=canvas)
        CombatHUD.paint_points(panel)
        colors=[call.kwargs['fill'] for call in canvas.create_rectangle.call_args_list]
        self.assertEqual(colors.count('#69ce85'),2);self.assertEqual(colors.count('#59615e'),g.battle['max_ap']-2)

if __name__=='__main__':unittest.main()
