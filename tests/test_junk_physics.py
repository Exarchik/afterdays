"""Junkyard pile: mikado rule, satiety as the cost of lifting, settling, saves and old-quest migration."""
import copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import game.model as r
import game.items as items
import junk_physics as pile
import quest_catalog
import quest_profiles
from junk_art import draw_piece
import ui.junkyard as junkyard
from tests.fixtures.quest_offer import offer_for


def full(g,satiety=20):
    g.survival['hunger']=satiety;g.survival['buffs']={}


def free_pieces(q):
    return [p for p in pile.live(q) if not pile.blockers(q,p)]


class JunkPileTests(unittest.TestCase):
    def game(self,seed=4):
        g=r.Game(seed);offer=offer_for(g,'junkyard');self.assertTrue(g.accept_quest(offer['id']))
        q=g.quests[-1];g.x,g.y=q['pos'];full(g);return g,q

    def test_new_quest_builds_a_layered_pile(self):
        g,q=self.game()
        self.assertEqual(q['junk_version'],pile.VERSION)
        self.assertEqual(q['goal'],3);self.assertNotIn('junk_stamina',q);self.assertEqual(q['junk_work'],0)
        self.assertTrue(15<=q['junk_settle_at']<=20);self.assertEqual(q['junk_since'],0)
        self.assertEqual(sum(f['kind']=='target' for f in q['junk_finds']),3)
        self.assertTrue(all(not pile.find_free(q,f) for f in q['junk_finds']))
        self.assertTrue(free_pieces(q));self.assertTrue(any(pile.blockers(q,p) for p in pile.live(q)))
        self.assertNotIn('junk_objects',q)
        for f in q['junk_finds']:
            self.assertTrue(0<=f['x']<=pile.WIDTH and 0<=f['y']<=pile.HEIGHT)

    def test_pile_is_deterministic_for_a_quest(self):
        g,q=self.game();copy_q=dict(id=q['id'])
        pile.build(copy_q,['target']*3,[])
        self.assertEqual([p['id'] for p in copy_q['junk_pieces']][:5],[p['id'] for p in q['junk_pieces']][:5])

    def test_overlap_and_inside_geometry(self):
        a=dict(x=100,y=100,w=100,h=40,a=0);b=dict(x=180,y=100,w=100,h=40,a=0);c=dict(x=260,y=100,w=40,h=40,a=0)
        self.assertTrue(pile.overlap(pile.corners(a),pile.corners(b)))
        self.assertFalse(pile.overlap(pile.corners(a),pile.corners(c)))
        diamond=pile.corners(dict(x=0,y=0,w=40,h=40,a=0.785398))
        self.assertTrue(pile.inside(0,0,diamond));self.assertFalse(pile.inside(19,19,diamond))

    def test_only_free_pieces_can_be_removed_for_satiety(self):
        g,q=self.game();q['junk_settings']['settle_chance']=0
        blocked=next(p for p in pile.live(q) if pile.blockers(q,p))
        self.assertFalse(g.junk_remove(q['id'],blocked['id']))
        self.assertEqual(g.junk_capacity(q),80)
        piece=free_pieces(q)[0];cost=pile.MATERIALS[piece['material']][1]
        self.assertTrue(g.junk_remove(q['id'],piece['id']))
        self.assertTrue(piece['gone']);self.assertEqual(g.hunger,20-cost//4);self.assertEqual(q['junk_work'],cost%4)
        self.assertEqual(g.junk_capacity(q),80-cost)
        self.assertFalse(g.junk_remove(q['id'],piece['id']))
        g.x,g.y=g.cities[q['city']];self.assertFalse(g.junk_remove(q['id'],free_pieces(q)[0]['id']))

    def test_every_four_weight_points_cost_one_satiety(self):
        g,q=self.game();q['junk_settings']['settle_chance']=0;removed=0
        while removed<30:
            piece=max(free_pieces(q),key=lambda p:p['z']);removed+=pile.MATERIALS[piece['material']][1]
            self.assertTrue(g.junk_remove(q['id'],piece['id']))
            self.assertEqual(g.hunger,20-removed//4);self.assertEqual(q['junk_work'],removed%4)

    def test_no_lifting_beyond_satiety_then_eat(self):
        g,q=self.game();full(g,1);q['junk_work']=2;q['junk_settings']['settle_chance']=0
        self.assertEqual(g.junk_capacity(q),2)
        heavy=[p for p in free_pieces(q) if pile.MATERIALS[p['material']][1]>2]
        if heavy:self.assertFalse(g.junk_remove(q['id'],heavy[0]['id']))
        full(g,0);q['junk_work']=0;self.assertEqual(g.junk_capacity(q),0)
        self.assertFalse(any(g.junk_remove(q['id'],p['id']) for p in free_pieces(q)))
        full(g,-5);self.assertEqual(g.junk_capacity(q),0)
        g.bag[:]=[i for i in g.bag if i['kind']!='food'];g.provisions=[]
        food=items.supply('food',1);g.bag.append(food);full(g,0)
        self.assertEqual(g.junk_eat(q['id'],food['id']),10);self.assertEqual(g.junk_capacity(q),40)

    def test_pile_settles_after_enough_weight(self):
        g,q=self.game();q['junk_settings'].update(settle_chance=100);count=len(q['junk_pieces']);seen=[]
        removed=0;at=q['junk_settle_at']
        while not seen:
            piece=max(free_pieces(q),key=lambda p:p['z']);removed+=pile.MATERIALS[piece['material']][1]
            self.assertTrue(g.junk_remove(q['id'],piece['id']))
            if g._junk_settled:seen.append(g._junk_settled)
            else:self.assertLess(removed,at)
        self.assertGreaterEqual(removed,at)
        self.assertEqual(len(q['junk_pieces']),count+1);self.assertEqual(q['junk_since'],0)
        self.assertTrue(15<=q['junk_settle_at']<=20);self.assertEqual(q['junk_settles'],1)
        new=q['junk_pieces'][-1];self.assertEqual(seen[0]['piece'],new['id'])
        zs=sorted(p['z'] for p in pile.live(q));self.assertEqual(zs,list(range(len(zs))))
        if not seen[0]['between']:self.assertEqual(new['z'],max(zs))

    def test_settling_between_layers_and_chance(self):
        g,q=self.game()
        kinds=set()
        for n in range(12):
            other=copy.deepcopy(q);other['junk_settles']=n
            new,between=pile.settle(other,pile.settle_rng(other));kinds.add(between)
            if between:self.assertLess(new['z'],max(p['z'] for p in pile.live(other)))
        self.assertEqual(kinds,{True,False})
        q['junk_settings']['settle_chance']=0;count=len(q['junk_pieces'])
        for _ in range(8):
            g.junk_remove(q['id'],max(free_pieces(q),key=lambda p:p['z'])['id'])
        self.assertEqual(len(q['junk_pieces']),count)

    def test_finds_open_only_when_uncovered(self):
        g,q=self.game();q['junk_settings']['settle_chance']=0;g.survival['buffs']={'buff_satiety':{'remaining':10**6,'amount':0}}
        target=next(f for f in q['junk_finds'] if f['kind']=='target')
        self.assertFalse(g.junk_collect(q['id'],target['id']))
        while not pile.find_free(q,target):
            piece=max(free_pieces(q),key=lambda p:p['z']);g.junk_remove(q['id'],piece['id'])
        self.assertTrue(g.junk_collect(q['id'],target['id']))
        self.assertEqual(q['progress'],1)
        self.assertEqual(sum(i.get('quest_id')==q['id'] for i in g.bag),1)
        self.assertFalse(g.junk_collect(q['id'],target['id']))

    def test_eating_adds_satiety(self):
        g,q=self.game();full(g,4)
        g.bag[:]=[i for i in g.bag if i['kind']!='food'];g.provisions=[]
        self.assertEqual(g.junk_foods(),[])
        food=items.supply('food',2);g.bag.append(food)
        self.assertEqual(g.junk_food_gain(q,food),10)
        self.assertEqual(g.junk_eat(q['id'],food['id']),10);self.assertEqual(g.hunger,14);self.assertEqual(food['qty'],1)
        self.assertEqual(g.junk_food_gain(q,food),6)
        self.assertEqual(g.junk_eat(q['id'],food['id']),6);self.assertEqual(g.hunger,20);self.assertNotIn(food,g.bag)

    def test_provisions_food_can_be_eaten(self):
        g,q=self.game();full(g,0)
        g.bag[:]=[i for i in g.bag if i['kind']!='food']
        food=items.supply('food',1);g.provisions=[food]
        self.assertEqual(g.junk_eat(q['id'],food['id']),10);self.assertEqual(g.provisions,[])

    def test_profile_settings_change_pile(self):
        spec=dict(quest_profiles.defaults('junkyard'),parts=5,work_per_satiety=2,settle_min=8,settle_max=9)
        doc=copy.deepcopy(quest_catalog.DOCUMENT);doc.setdefault('native',{})['junkyard']={'normal':spec}
        self.assertEqual(quest_profiles.validate(doc),[])
        doc['native']['junkyard']['normal']=dict(spec,parts=0);self.assertTrue(quest_profiles.validate(doc))
        doc['native']['junkyard']['normal']=dict(spec,settle_min=30,settle_max=20);self.assertTrue(quest_profiles.validate(doc))
        original=quest_catalog.DOCUMENT;quest_catalog.DOCUMENT=dict(original,native={'junkyard':{'normal':spec}})
        try:
            g,q=self.game()
            self.assertEqual(q['goal'],5);self.assertTrue(8<=q['junk_settle_at']<=9)
            self.assertEqual(g.junk_capacity(q),40)
            self.assertEqual(sum(f['kind']=='target' for f in q['junk_finds']),5)
        finally:quest_catalog.DOCUMENT=original

    def test_state_survives_save_and_load(self):
        g,q=self.game();g.junk_remove(q['id'],free_pieces(q)[0]['id'])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
        other=h.quests[-1]
        self.assertEqual(other['junk_pieces'],q['junk_pieces'])
        for key in ('junk_work','junk_since','junk_settle_at','junk_settles'):self.assertEqual(other[key],q[key])

    def test_old_dragging_quest_gets_new_pile_with_missing_parts(self):
        g,q=self.game()
        for key in ('junk_pieces','junk_finds','junk_version','junk_settings','junk_work','junk_since','junk_settle_at','junk_settles'):q.pop(key)
        q.update(junk_physics=1,progress=1,junk_objects=[dict(id='target0',kind='target',found=True,x=0,y=0)])
        g.bag.append(dict(id='old',type_id='quest_item',kind='quest',name='x',quest_id=q['id'],rarity=0,weight=0,value=0))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
        other=h.quests[-1]
        self.assertEqual(other['junk_version'],pile.VERSION);self.assertNotIn('junk_objects',other)
        self.assertEqual(sum(f['kind']=='target' for f in other['junk_finds']),2)
        self.assertEqual(other['progress'],1);self.assertEqual(other['junk_work'],0);self.assertTrue(15<=other['junk_settle_at']<=20)

    def test_stamina_save_moves_to_satiety(self):
        g,q=self.game();q.pop('junk_work');q.pop('junk_since');q.pop('junk_settle_at');q.pop('junk_settles')
        q['junk_stamina']=12;q['junk_settings']=dict(parts=3,max_stamina=30,stamina_per_satiety=3)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
        other=h.quests[-1]
        self.assertNotIn('junk_stamina',other);self.assertEqual(other['junk_settings']['work_per_satiety'],4)
        self.assertEqual(other['junk_pieces'],q['junk_pieces']);self.assertEqual(other['junk_work'],0)

    def test_piece_drawing_has_no_text(self):
        canvas=MagicMock()
        g,q=self.game()
        for p in q['junk_pieces']:draw_piece(canvas,p)
        canvas.create_polygon.assert_called();canvas.create_text.assert_not_called()

    def test_window_destroy_cancels_animation(self):
        ui=junkyard.Junkyard.__new__(junkyard.Junkyard);ui.win=MagicMock();ui.timer='timer1';ui.closed=False;ui.hover='x'
        ui.destroyed(SimpleNamespace(widget=ui.win));self.assertTrue(ui.closed);self.assertIsNone(ui.timer)
        ui.win.after_cancel.assert_called_once_with('timer1')


if __name__=='__main__':unittest.main()
