"""End-to-end metro chains, persistence, repair and dungeon gates."""
import copy,math,tempfile,unittest
from pathlib import Path
import afterdays as r
import frontier,progression as p

class MetroTests(unittest.TestCase):
    def make(self,seed=2):
        """Accept a real generated metro offer at the station's appropriate level."""
        g=r.Game(seed);g.reputation_state['border_open']=True
        city=frontier.METRO_CITIES[1];g.x,g.y=g.cities[city]
        g.xp=p.xp_for_level(g.region_level);g.record_at(g.cities[city])['value']=100
        offer=next(q for q in g.mayor_offers() if 'metro_city' in q)
        self.assertTrue(g.accept_quest(offer['id']))
        return g,next(q for q in g.quests if q['id']==offer['id'])

    def solve(self,g,q):
        """Use actual search and minigame completion methods for one nested stage."""
        s=g.metro_step(q);g.x,g.y=s['pos'];g.road_event=None
        role=s['metro_role']
        if role=='archive':
            self.assertTrue(g.metro_action(q['id']))
            for a in range(9):
                if s['layout'][a]!=a:self.assertTrue(g.swap_map_pieces(s['id'],a,s['layout'].index(a)))
        elif role=='generator':
            p.add_to(g.bag,p.parts(20));p.add_to(g.bag,p.fragments(20))
            self.assertTrue(g.search());self.assertFalse(g.repair_generator(s['id']))
            for n in s['generator_order']:self.assertTrue(g.generator_toggle(s['id'],n))
            self.assertTrue(g.repair_generator(s['id']))
        elif role=='radio':
            self.assertTrue(g.search());self.assertTrue(g.tune_radio(s['id'],s['radio_target']))
        elif role=='cache':
            p.add_to(g.bag,p.parts(20));g.x,g.y=s['cache_pos']
            self.assertTrue(g.search());self.assertEqual(g.lock_context(s['id']),s)
            self.assertTrue(g.unlock_cache(s['id'],s['lock_target']))
        elif role=='hermit':
            self.assertTrue(g.metro_action(q['id']))
            if s['task']=='hunt':
                for _ in range(s['need']):g.monster_killed({},0,None)
            else:p.add_to(g.bag,p.parts(s['need']) if s['task']=='parts' else p.supply(s['task'],s['need']))
            self.assertTrue(g.metro_action(q['id']))
        elif role=='dungeon':self.dungeon(g,q)
        self.assertTrue(s['completed'])

    def dungeon(self,g,q):
        """Require a cleared vault and a chest interaction, then use the real exit."""
        self.assertTrue(g.metro_action(q['id']));b=g.battle
        self.assertTrue(b['enemies']);self.assertFalse(g.metro_chest())
        b['enemies']=[];g.victory();self.assertTrue(b['cleared'])
        b['pos']=b['chest'][:];self.assertTrue(g.search())
        b['pos']=b['exit'][:];self.assertTrue(g.flee());self.assertIsNone(g.battle)

    def test_all_stage_types_and_save_reload(self):
        """Generated chains survive reload at each stage and cannot finish early."""
        seen=set()
        for seed in range(8):
            g,q=self.make(seed);ident=q['id'];c=q['metro_chain']
            self.assertTrue(2<=len(c['steps'])<=5)
            for s in c['steps']:
                seen.add(s['metro_role']);self.assertLessEqual(math.dist(g.cities[q['city']],s['pos']),25)
                self.assertLessEqual(g.region_at(*s['pos']),q['level']+1)
                if q['level']>=3:self.assertGreaterEqual(g.region_at(*s['pos']),3)
                if s.get('area'):
                    a,b,c,d=s['area']
                    for x in range(a,c+1):
                        for y in range(b,d+1):
                            self.assertTrue(g.passable(x,y));self.assertLessEqual(math.dist(g.cities[q['city']],(x,y)),25)
            while q['metro_chain']['index']<len(q['metro_chain']['steps']):
                self.assertFalse(g.quest_ready(q));self.assertFalse(g.turn_in(q['id']))
                self.solve(g,q)
                with tempfile.TemporaryDirectory() as td:
                    path=Path(td)/'save.json';g.save(path);before=copy.deepcopy(q['metro_chain']);g=r.Game.load(path)
                    q=next(q for q in g.quests if q['id']==ident);self.assertEqual(q['metro_chain'],before)
            c=q['metro_chain'];part=g.metro_part(q);self.assertIsNotNone(part)
            g.x,g.y=g.cities[q['city']];c['infested']=False
            if part['durability']<100:
                self.assertFalse(g.metro_action(q['id']));p.add_to(g.bag,p.supply('repairkit',3))
                while part['durability']<100:self.assertTrue(g.repair_with_kit(part['id']))
            self.assertTrue(g.metro_action(q['id']));self.assertTrue(g.quest_ready(q))
            self.assertTrue(g.turn_in(q['id']));self.assertIn(q['metro_city'],g.metro_unlocked)
            self.assertFalse(g.turn_in(q['id']))
        self.assertEqual(seen,{'archive','generator','radio','cache','dungeon','hermit'})

    def test_station_repair_and_installation(self):
        """Final station unlock needs repaired part, monster clearance and installation."""
        g,q=self.make()
        while q['metro_chain']['index']<len(q['metro_chain']['steps']):self.solve(g,q)
        c=q['metro_chain'];c['infested']=True;part=g.metro_part(q);part['durability']=10
        g.x,g.y=g.cities[q['city']];self.assertFalse(g.metro_action(q['id']))
        if g.city not in g.technicians:g.technicians.append(g.city)
        g.money=10000;self.assertTrue(g.repair(part['id']))
        self.assertTrue(g.metro_action(q['id']));b=g.battle
        b['enemies']=[];g.victory();self.assertFalse(g.quest_ready(q))
        b['pos']=b['exit'][:];self.assertTrue(g.flee());self.assertFalse(c['installed'])
        self.assertTrue(g.metro_action(q['id']));self.assertTrue(g.battle['cleared'])
        g.battle['pos']=g.battle['exit'][:];before=(g.money,copy.deepcopy(g.loot));g.flee();self.assertEqual((g.money,g.loot),before)
        self.assertTrue(g.metro_action(q['id']))
        g.battle['pos']=g.battle['chest'][:];self.assertTrue(g.search());self.assertTrue(c['installed'])
        self.assertFalse(g.can_turn_in(q))
        g.battle['pos']=g.battle['exit'][:];g.flee();self.assertTrue(g.turn_in(q['id']))

    def test_legacy_active_contract_remains_completable(self):
        """An accepted pre-chain metro quest keeps its one-item workflow after loading."""
        g,q=self.make();q.pop('metro_chain');q.pop('area',None)
        q.update(pos=list(g.quest_locations(q)[0]),progress=0,goal=1)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);g=r.Game.load(path)
        q=next(q for q in g.quests if 'metro_city' in q)
        self.assertNotIn('metro_chain',q);g.x,g.y=q['pos'];self.assertTrue(g.search())
        self.assertTrue(g.quest_ready(q));g.x,g.y=g.cities[q['city']];self.assertTrue(g.turn_in(q['id']))

    def test_abandon_cleans_nested_tokens(self):
        """Abandoning clears map tokens attached to nested stages and keeps the normal penalty."""
        g,q=self.make(5);s=q['metro_chain']['steps'][0]
        g.bag.append(g.quest_token(s,'torn_map_item'))
        self.assertTrue(g.abandon_quest(q['id']))
        self.assertFalse(any(i.get('quest_id')==s['id'] for i in g.bag))

if __name__=='__main__':unittest.main()
