"""Focused tests for firing, workshop transactions, rewards and dynamic weather."""
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import game.model as r
import game.items as p
import game.catalog as catalog
import module_rules as mr
import game.systems.combat as combat
import content
from ui.workshop import upgrade_description

class Update033Tests(unittest.TestCase):
    def arena(self,key='weapon_ash_pistol',distance=2):
        """Create a deterministic unobstructed arena with two durable targets."""
        g=r.Game(3);g.start_battle();w=p.equipment(key,level=catalog.GEAR_MIN_LEVEL[key]);g.equipped[g.active]=w
        g.bag.append(p.ammunition(w['ammo_type'],100));b=g.battle
        b.update(pos=[1,2],walls=[],ap=20,w=20,h=12,enemies=[dict(id=str(n),kind=0,pos=[1+distance+n,2],hp=10000,max_hp=10000,defense=0,armor=0,name='Target',level=5,grade='normal',resists={},awake=False) for n in range(2)])
        return g,w,b
    def test_categories_and_modes(self):
        """Every weapon belongs to exactly one requested category."""
        from collections import Counter
        self.assertEqual(Counter(v['category'] for v in content.EQUIPMENT.values() if v['kind']=='weapon'),dict(pistol=3,rifle=3,shotgun=1,automatic=3,sniper=4))
        g,w,b=self.arena('weapon_rust_assault');ap=b['ap'];self.assertTrue(g.cycle_fire_mode());self.assertEqual(b['ap'],ap);self.assertEqual(g.fire_mode(),'burst')
    def test_burst_atomic_and_costs(self):
        """Burst spends five bullets and one AP surcharge; insufficient ammo costs nothing."""
        g,w,b=self.arena('weapon_rust_assault');g.cycle_fire_mode();ammo=g.count('ammo',w['ammo_type']);ap=b['ap']
        with patch.object(g.rng,'randrange',return_value=0):self.assertTrue(g.shoot('0'))
        self.assertEqual(ammo-g.count('ammo',w['ammo_type']),5);self.assertEqual(ap-b['ap'],w['ap']+1);self.assertEqual(w['durability'],97)
        self.assertEqual(len([e for e in g._events if e.get('fire_mode')=='burst']),5)
        g.consume('ammo',g.count('ammo',w['ammo_type'])-4,w['ammo_type']);before=(b['ap'],w['durability'],g.count('ammo',w['ammo_type']))
        self.assertFalse(g.shoot('0'));self.assertEqual(before,(b['ap'],w['durability'],g.count('ammo',w['ammo_type'])))
    def test_aimed_accuracy_and_wear(self):
        """Aimed fire applies range-sensitive accuracy and doubles base wear."""
        g,w,b=self.arena('weapon_horizon_sniper',4);far=g.shot_info(b['enemies'][0])[2]
        b['enemies'][0]['pos']=[3,2];near=g.shot_info(b['enemies'][0])[2]
        self.assertGreater(far,near);self.assertEqual(g.fire_mode(),'aimed');self.assertFalse(g.cycle_fire_mode())
        self.assertTrue(g.shoot('0'));self.assertAlmostEqual(w['durability'],98.8)
    def test_shotgun_secondary_out_of_range(self):
        """Out-of-range enemies cannot receive reserved pellets."""
        g,w,b=self.arena('weapon_thunder_shotgun',3)
        primary,secondary=b['enemies']
        with patch.object(g.rng,'randrange',return_value=0):self.assertTrue(g.shoot('0'))
        self.assertLess(primary['hp'],10000);self.assertEqual(secondary['hp'],10000)
    def test_condition_and_misfire(self):
        """Condition bands are exact; total damage including elemental modules approaches one."""
        g,w,b=self.arena();w['modules']=[p.module(index='module_phase_approximator')]
        for state,chance in [(100,0),(75,0),(74,.02),(50,.02),(49,.05),(1,.05)]:
            w['durability']=state;self.assertEqual(combat.misfire_chance(w),chance)
        self.assertEqual(sum(mr.shot_components(w,15,2,'kinetic').values()),1)
        w['durability']=60
        with patch.object(g.rng,'random',return_value=0),patch.object(g.rng,'randrange',return_value=0):self.assertTrue(g.shoot('0'))
        self.assertEqual(b['enemies'][0]['hp'],10000);self.assertLess(b['enemies'][1]['hp'],10000)
    def test_storage_module_transaction(self):
        """Storage installs preserve IDs and roll back inaccessible or overweight transfers."""
        g=r.Game(2);w=g.weapon;m=p.module(index=0);g.stash=[m]
        self.assertIn(m,g.available_modules(w));self.assertTrue(g.install(w['id'],m['id']));self.assertEqual(w['modules'][0]['id'],m['id']);self.assertFalse(g.stash)
        m=p.module(index=1);g.stash=[m];g.x,g.y=6,5
        self.assertNotIn(m,g.available_modules(w));self.assertFalse(g.install(w['id'],m['id']));self.assertEqual(g.stash,[m])
        g.x,g.y=g.cities[0];w['modules']=[];m['weight']=999;before=copy.deepcopy((g.bag,g.stash,g.equipped))
        self.assertFalse(g.install(w['id'],m['id']));self.assertEqual((g.bag,g.stash,g.equipped),before)
    def test_maintenance_and_salvage(self):
        """Broken weapons require technicians; self-disassembly consumes a kit, workshop consumes money."""
        g=r.Game(2);w=g.weapon;w['durability']=20;p.add_to(g.bag,p.supply('repairkit',2));self.assertFalse(g.repair_with_kit(w['id']))
        w['durability']=20.1;self.assertTrue(g.repair_with_kit(w['id']))
        spare=p.equipment('weapon_ash_pistol',level=10);g.bag.append(spare);self.assertEqual(g.salvage_yield(spare),100)
        self.assertTrue(g.dismantle(spare['id']));self.assertEqual(g.count('repairkit'),0);self.assertEqual(g.count('parts'),100)
        spare=p.equipment('weapon_ash_pistol');g.bag.append(spare);self.assertFalse(g.dismantle(spare['id']));g.money=10000;quote=g.dismantle_quote(spare['id']);before=g.money
        self.assertTrue(g.technician_dismantle(spare['id']));self.assertEqual(g.money,before-quote[1])
    def test_upgrade_preview_and_quest_xp(self):
        """Upgrade preview compares the exact item, and base quest XP starts at twenty-five."""
        import game.systems.equipment_upgrades as update031
        g=r.Game(3);w=p.equipment('weapon_watch_rifle',level=2);preview=upgrade_description(w,update031.upgraded(w));self.assertIn('До\tПісля',preview);self.assertIn('Рівень\t2\t3',preview)
        for level in (1,5,15):
            q=dict(kind='hunt',city=0,status='offered',unique=False,level=level);g.price_quest(q);self.assertEqual(q['xp_reward'],25+5*(level-1))
    def test_mythic_no_equipment_bonus(self):
        """Mythic monsters no longer drop gear; duplicate death gives no extra XP."""
        g,w,b=self.arena();enemy=b['enemies'][0];enemy.update(grade='mythic',level=5)
        with patch.object(g.rng,'random',return_value=.29):g._finish_enemy(enemy,w)
        self.assertFalse(b.get('mythic_bonus'));xp=g.xp
        g._finish_enemy(enemy,w);self.assertEqual(g.xp,xp)
        g,w,b=self.arena();enemy=b['enemies'][0];enemy['grade']='mythic'
        with patch.object(g.rng,'random',return_value=.30):g._finish_enemy(enemy,w)
        self.assertFalse(b.get('mythic_bonus'))
    def test_weather_persistence_motion_and_immunity(self):
        """Storm motion is one cell per turn, survives reload and ends beyond an edge."""
        g=r.Game(3);g.x,g.y=20,10;g.reputation_state['storm033']=dict(pos=[19,10],radius=1,direction=1,age=0);g.rad_turns=2;hp=g.hp
        with patch('random.Random.random',return_value=.2):g._world_time_tick()
        self.assertEqual(g.storm['pos'],[20,10]);self.assertEqual(g.radiation_injury,5);self.assertEqual(g.hp,g.max_hp)
        g.rad_turns=0
        with patch('random.Random.random',return_value=.2):g._world_time_tick()
        self.assertEqual(g.radiation_injury,10);self.assertEqual(g.hp,g.max_hp)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=r.Game.load(path);self.assertEqual(g.storm,h.storm)
        g.storm['pos']=[112,10]
        with patch('random.Random.random',return_value=.2):g.turn+=1;g.advance_storm()
        self.assertIsNone(g.storm)
    def test_mayor_strict_thresholds(self):
        """Exactly fifty reputation or five quests is insufficient; the sixth can reveal one town."""
        g=r.Game(1);g.known_cities=[0];g.local_record()['value']=27
        for n in range(6):
            q=dict(id=f'm{n}',kind='hunt',city=0,status='active',title='Mayor',progress=1,goal=1,target_kind=None,reward=0,xp_reward=0,unique=False)
            g.quests.append(q);self.assertTrue(g.turn_in(q['id']))
            if n<5:self.assertEqual(g.map_rewards,[])
        self.assertEqual(g.reputation(0),51);self.assertEqual(g.map_rewards,[0]);self.assertEqual(len(g.known_cities),2)

    def test_burst_mode_saved(self):
        """Weapon mode survives save/load without requiring new top-level save fields."""
        g,w,b=self.arena('weapon_rust_assault');g.cycle_fire_mode()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'s.json';g.save(path);h=r.Game.load(path);self.assertEqual(h.fire_mode(),'burst')

    def test_reveal_animation_is_world_scene(self):
        """Reveal highlights block travel briefly and render as world cells, not battle effects."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from ui.adventure import Effects
        g=r.Game(2);app=SimpleNamespace(game=g,root=MagicMock(),canvas=MagicMock(),tile=20,ox=0,oy=0,vx=29,vy=9)
        from world_map import layout
        app.world_view=layout(800,600,112,32,(30,10))
        fx=Effects(app);app.fx=fx;g.emit(kind='reveal',scene='world');g._events[-1]['cells']=[[30,10],[31,10]]
        fx.ingest();self.assertTrue(fx.blocked);self.assertEqual(fx.reveal_focus(),(30,10));fx.render();self.assertEqual(app.canvas.create_polygon.call_count,2)

    def test_cartographer_highlight(self):
        """Map buying emits exactly the newly revealed cells."""
        g=r.Game(2);g.traveler=dict(pos=[5,5],cartographer=True,purchased=False,box=[30,10,3],price=5);g.money=100
        self.assertTrue(g.buy_map());event=next(e for e in g._events if e['kind']=='reveal');self.assertEqual(len(event['cells']),9)

if __name__=='__main__':unittest.main()
