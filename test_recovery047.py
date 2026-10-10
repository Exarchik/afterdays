import copy,math,random,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import game.model as r
import game.items as p
import faction_rules as f
import monster_rules
from game.systems.credits import credit_item

class RecoveryTests(unittest.TestCase):
    def test_successful_rest_changes_checkpoint_even_at_full_health(self):
        g=r.Game(4);g.money=500;g.x,g.y=g.cities[1];g.hp=g.max_hp
        self.assertTrue(g.rest());self.assertEqual(g.respawn_pos,g.cities[1])
        g.x,g.y=g.cities[2];g.survival['radiation']=5
        self.assertFalse(g.rest());self.assertEqual(g.respawn_pos,g.cities[1])

    def test_death_split_money_durability_and_respawn(self):
        g=r.Game(4);g.reputation_state['respawn047']=g.cities[1][:];g.x,g.y=g.cities[2]
        weapon=p.equipment('weapon_ash_pistol');module=p.module(0,random.Random(4));food=p.supply('food',4)
        quest=dict(id='quest',kind='quest',name='Quest',qty=1,weight=0,value=0,level=1)
        quest_weapon=p.equipment('weapon_ash_pistol');quest_weapon['quest_id']='test'
        ammo=p.ammunition('pistol',10);parts=p.parts(4);fragments=p.fragments(3)
        g.bag=[weapon,module,food,quest,quest_weapon,ammo,parts,fragments,credit_item(101)]
        g.stash=[credit_item(90),p.supply('med',2)];stash=copy.deepcopy(g.stash)
        equipped=[i for i in g.equipped.values() if i]
        for i in equipped:i['durability']=70
        g.defeat()
        self.assertEqual([g.x,g.y],g.cities[1]);self.assertEqual(g.hp,max(1,math.ceil(g.max_hp*.25)))
        self.assertEqual(g.stash,stash);self.assertEqual(g.carried_money,0)
        self.assertEqual({i['id'] for i in g.bag},{i['id'] for i in (quest,quest_weapon,ammo,parts,fragments)})
        self.assertTrue(all(i['durability']==35 for i in equipped))
        grave=g.graves[0];self.assertEqual(grave['pos'],g.cities[2])
        self.assertEqual(sum(i['qty'] for i in grave['items'] if i['kind']=='credits'),70)
        self.assertTrue({weapon['id'],module['id'],food['id']}<={i['id'] for i in grave['items']})

    def test_grave_persists_and_only_local_collection(self):
        g=r.Game(4);g.x,g.y=g.cities[1];g.bag=[credit_item(100),p.supply('med',1)];g.defeat()
        first=copy.deepcopy(g.graves[0]);self.assertFalse(g.collect_grave(first['id'],first['items'][0]['id']))
        g.x,g.y=g.cities[2];g.bag.append(p.supply('food'));g.defeat();self.assertEqual(len(g.graves),2)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'save.json';g.save(path);g=r.Game.load(path)
        self.assertEqual(g.graves[0],first)
        g.x,g.y=first['pos'];self.assertTrue(g.search());self.assertTrue(g._grave_request)
        self.assertTrue(g.collect_all_graves());self.assertEqual(g.carried_money,70)
        self.assertFalse(any(v['id']==first['id'] for v in g.graves));self.assertFalse(g.collect_all_graves())
        self.assertEqual(g.carried_money,70)

    def test_full_bag_keeps_grave_contents(self):
        g=r.Game(4);item=p.supply('med',10000)
        g.graves.append(dict(id='grave',pos=[g.x,g.y],items=[item],turn=0))
        old_loot=[p.parts(3)];g.loot=old_loot
        self.assertTrue(g.collect_grave('grave',item['id']))
        self.assertTrue(g.graves[0]['items']);self.assertLess(g.graves[0]['items'][0]['qty'],10000)
        self.assertNotIn(g.graves[0]['items'][0]['id'],{i['id'] for i in g.bag})
        left=g.graves[0]['items'][0]['qty'];self.assertFalse(g.collect_grave('grave',item['id']))
        self.assertEqual(g.graves[0]['items'][0]['qty'],left);self.assertIs(g.loot,old_loot)

    def test_armor_half_probability(self):
        count=0
        for seed in range(1000):
            e=f.make_human(random.Random(seed),'human_bandit','bandits',1,[0,0])
            count+='armor' in e['equipment'];self.assertIn('weapon',e['equipment'])
        self.assertAlmostEqual(count/1000,.5,delta=.05)

    def arena(self):
        g=r.Game(47);g.battle=dict(pos=[0,0],w=12,h=12,walls=[],enemies=[],kills=[],corpses=[],ap=6,max_ap=6,round=1,region_level=1)
        return g

    def actor(self,pos,faction='monsters'):
        e=monster_rules.make(random.Random(3),0,1,pos);e.update(faction=faction,awake=False,sight=5);return e

    def test_resting_enemy_sees_hostile_npc_not_friendly_player(self):
        g=self.arena();sleeper=self.actor([6,6],'settlers');enemy=self.actor([6,7],'bandits');g.battle['enemies']=[sleeper,enemy]
        g.wake_enemies();self.assertTrue(sleeper['awake']);self.assertTrue(enemy['awake'])
        sleeper['awake']=False;g.battle['enemies']=[sleeper];g.battle['pos']=[6,5]
        g.wake_enemies();self.assertFalse(sleeper['awake'])

    def test_resting_enemy_sight_and_walls(self):
        g=self.arena();e=self.actor([8,8]);g.battle['enemies']=[e]
        pos=e['pos'][:];g.end_turn();self.assertFalse(e['awake']);self.assertEqual(e['pos'],pos)
        g.battle['pos']=[5,8];g.battle['walls']=[[6,8],[7,8]];g.wake_enemies();self.assertFalse(e['awake'])
        g.battle['walls']=[];g.wake_enemies();self.assertTrue(e['awake'])

    def test_monsters_no_gear_ammo_or_money_even_mythic(self):
        g=self.arena();e=self.actor([6,6]);e['grade']='mythic';g.battle['enemies']=[e];money=g.money
        with patch.object(g.rng,'random',return_value=0):
            g._finish_enemy(e);self.assertFalse(g.battle.get('mythic_bonus'));g.victory()
        self.assertTrue(g.loot);self.assertEqual(g.money,money)
        self.assertFalse({i['kind'] for i in g.loot}&{'weapon','armor','helmet','module','credits','ammo'})

    def test_mixed_battle_keeps_human_equipment_drops(self):
        g=self.arena();monster=self.actor([6,6]);human=f.make_human(random.Random(4),'human_bandit','bandits',1,[7,7]);g.battle['enemies']=[monster,human]
        item=copy.deepcopy(human['equipment']['weapon'])
        with patch('faction_rules.human_loot',return_value=[item,credit_item(10)]):g._finish_enemy(human)
        g._finish_enemy(monster);g.victory()
        self.assertIn(item,g.loot);self.assertTrue(any(i['kind']=='credits' for i in g.loot))

    def test_lethal_arena_attack_leaves_grave_on_world_cell(self):
        g=self.arena();g.x,g.y=g.cities[2];g.reputation_state['respawn047']=g.cities[1][:]
        e=self.actor([1,0]);e.update(awake=True,damage=10000,range=2)
        g.battle['enemies']=[e];g.hp=1;g.bag=[credit_item(100)]
        with patch.object(g.rng,'randrange',return_value=99):g.end_turn()
        self.assertIsNone(g.battle);self.assertEqual(g.graves[0]['pos'],g.cities[2])
        self.assertEqual([g.x,g.y],g.cities[1]);self.assertEqual(g.hp,max(1,math.ceil(g.max_hp*.25)))

if __name__=='__main__':unittest.main()
