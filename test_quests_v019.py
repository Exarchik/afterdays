import copy,json,math,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
import afterdays as r
import progression as p
import sprites
from tests_fixtures.quest_offer import offer_for
from advanced_ui import battle_camera,iso_cell

class QuestRevisionTests(unittest.TestCase):
    def test_total_active_plus_offered_across_refresh(self):
        """Перевіряє сценарій «total active plus offered across refresh» та очікувані результати."""
        g=r.Game(7)
        first=g.mayor_offers()[0];self.assertTrue(g.accept_quest(first['id']))
        self.assertLessEqual(len(g.active_for(0))+len(g.mayor_offers()),2)
        for turn in (100,200,300):
            g.turn=turn
            self.assertLessEqual(len(g.active_for(0))+len(g.mayor_offers()),2)
        g.local_record()['value']=75
        self.assertLessEqual(len(g.active_for(0))+len(g.mayor_offers()),5)

    def test_abandon_removes_parcel_and_penalizes_neighbours(self):
        """Перевіряє сценарій «abandon removes parcel and penalizes neighbours» та очікувані результати."""
        g=r.Game(4);q=offer_for(g,'delivery');self.assertTrue(g.accept_quest(q['id']));q=g.quests[-1]
        near=g.special_sites[0];g.record_at(near['pos'])['value']=20
        source=g.reputation(0);qcopy=copy.deepcopy(q)
        self.assertTrue(g.abandon_quest(q['id']));self.assertNotIn(q,g.quests)
        self.assertFalse(any(i.get('quest_id')==q['id'] for i in g.bag+g.stash))
        self.assertEqual(g.reputation(0),source-5)
        if math.dist(near['pos'],g.cities[0])<=10:self.assertEqual(g.record_at(near['pos'])['value'],15)
        self.assertFalse(g.abandon_quest(q['id']));self.assertEqual(g.reputation(0),source-5)
        self.assertFalse(g.accept_quest(qcopy['id']))

    def test_penalty_clamps_zero_and_no_cascade(self):
        """Перевіряє сценарій «penalty clamps zero and no cascade» та очікувані результати."""
        g=r.Game(4);g.cities[1:4]=[[15,5],[16,5],[24,5]]
        for city in range(4):g.local_record(city)['value']=3
        g.change_reputation(-5,0)
        self.assertEqual([g.reputation(i) for i in range(4)],[0,0,3,3])

    def test_roaming_merchant_uses_nearest_town(self):
        """Перевіряє сценарій «roaming merchant uses nearest town» та очікувані результати."""
        g=r.Game(3);g.x,g.y=7,5;p.Game.spawn_traveler(g)
        city=g.trading_city(3);self.assertEqual(city,min(range(12),key=lambda n:math.dist((7,5),g.cities[n])))
        item=next(i for i in g.stock(3) if i['kind']=='food');g.local_record(city)['value']=0
        high=g.price(item,3);g.local_record(city)['value']=100;low=g.price(item,3);self.assertGreater(high,low)
        g.local_record(city)['value']=0;g.money=10000;g.local_record(city)['turnover']=49
        self.assertTrue(g.buy(item['id'],3));self.assertGreaterEqual(g.reputation(city),1)
        self.assertEqual(g.city,None)

    def test_high_level_quest_destinations_stay_outside(self):
        """Перевіряє сценарій «high level quest destinations stay outside» та очікувані результати."""
        g=r.Game(8);g.reputation_state['border_open']=True
        city=next(i for i in range(12) if g.region_at(*g.cities[i])>=3)
        level=g.region_at(*g.cities[city]);q=dict(id='q',city=city,level=level)
        self.assertTrue(g.quest_locations(q))
        self.assertTrue(all(3<=g.region_at(*pos)<=level+1 for pos in g.quest_locations(q)))
        self.assertTrue(all(3<=g.region_at(*s['pos'])<=level+1 for s in g.delivery_sites(q)))

    def repair_contract(self):
        """Готує або імітує операцію «repair contract» для перевірок QuestRevisionTests."""
        g=r.Game(4);q=offer_for(g,'repair_delivery');self.assertTrue(g.accept_quest(q['id']));q=g.quests[-1]
        return g,q,next(i for i in g.bag if i.get('quest_id')==q['id'])

    def test_repair_delivery_full_lifecycle(self):
        """Перевіряє сценарій «repair delivery full lifecycle» та очікувані результати."""
        g,q,item=self.repair_contract();g.money=100000
        self.assertFalse(g.equip(item['id'],'weapon1'));self.assertFalse(g.dismantle(item['id']))
        self.assertFalse(g.sell(item['id'],2));self.assertFalse(g.stash_transfer(item['id'],'deposit'))
        self.assertTrue(g.repair(item['id'],50));self.assertFalse(g.quest_ready(q))
        self.assertTrue(g.repair(item['id'],100));self.assertTrue(g.quest_ready(q));self.assertFalse(g.turn_in(q['id']))
        rep=g.reputation(q['city']);g.x,g.y=q['pos'];money=g.money
        self.assertTrue(g.can_turn_in(q));self.assertTrue(g.turn_in(q['id']))
        self.assertEqual(g.money,money+q['reward']);self.assertNotIn(item,g.bag)
        self.assertEqual(g.reputation(q['city']),min(100,rep+4));self.assertFalse(g.turn_in(q['id']))

    def test_repair_and_reward_plan_survive_save(self):
        """Перевіряє сценарій «repair and reward plan survive save» та очікувані результати."""
        g,q,item=self.repair_contract();g.money=100000;g.repair(item['id'],50)
        q['unique']=True;g.prepare_quest_rewards(q)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'s.json';g.save(path);h=r.Game.load(path)
            other=next(t for t in h.quests if t['id']==q['id'])
            self.assertEqual(other['reward_items'],q['reward_items'])
            self.assertEqual(next(i for i in h.bag if i.get('quest_id')==q['id'])['durability'],50)

    def test_unique_reward_preview_matches_award(self):
        """Перевіряє сценарій «unique reward preview matches award» та очікувані результати."""
        g=r.Game(4);q=offer_for(g,'retrieve',unique=True);preview=copy.deepcopy(g.prepare_quest_rewards(q))
        self.assertEqual(preview,g.prepare_quest_rewards(q));g.accept_quest(q['id']);q=g.quests[-1]
        q.update(kind='hunt',progress=1,goal=1)
        self.assertTrue(g.turn_in(q['id']))
        owned={i['id'] for i in g.bag+g.stash}
        self.assertTrue(all(i['id'] in owned for i in preview))

    def test_bulletin_at_mayorless_city(self):
        """Перевіряє сценарій «bulletin at mayorless city» та очікувані результати."""
        g=r.Game(2);city=next(i for i in range(12) if i not in g.mayors);g.x,g.y=g.cities[city]
        with patch.object(g.rng,'random',return_value=0):offers=g.mayor_offers()
        self.assertEqual(len(offers),1);self.assertNotIn(city,g.mayors)
        self.assertTrue(g.accept_quest(offers[0]['id']));g.turn+=100
        with patch.object(g.rng,'random',return_value=0):self.assertEqual(g.mayor_offers(),[])
        q=g.active_for(city)[0];g.abandon_quest(q['id']);g.turn+=100
        with patch.object(g.rng,'random',return_value=1):self.assertEqual(g.mayor_offers(),[])
        self.assertEqual(g.quest_capacity(city),1)

    def test_camera_follows_and_picking_uses_same_transform(self):
        """Перевіряє сценарій «camera follows and picking uses same transform» та очікувані результати."""
        b=dict(w=31,h=27,dungeon=True,pos=[2,4]);u,ox,oy=battle_camera(b,800,600)
        self.assertGreater(u,20)
        import hexgrid
        px,py=hexgrid.center((2,4),u,ox,oy);self.assertAlmostEqual(px,400);self.assertAlmostEqual(py,330)
        self.assertAlmostEqual(u,.7071*.9*.85*max(24,min(46,800/18,600/13)))
        b['pos']=[19,22];u2,ox2,oy2=battle_camera(b,800,600);self.assertEqual(u,u2);self.assertNotEqual((ox,oy),(ox2,oy2))
        app=SimpleNamespace(iso=dict(u=u2,ox=ox2,oy=oy2,sprites=[]))
        self.assertEqual(iso_cell(app,SimpleNamespace(x=400,y=330)),(19,22))

    def test_all_trophies_have_distinct_existing_icons(self):
        """Перевіряє сценарій «all trophies have distinct existing icons» та очікувані результати."""
        import economy
        keys=[sprites.item_key(economy.trophy(i)) for i in range(12)]
        self.assertEqual(len(set(keys)),12)
        for key in keys:self.assertEqual(sprites.MANIFEST[key]['sheet'],'trophies')
        from PIL import Image
        for size in sprites.SIZES:
            im=Image.open(sprites.ROOT/f'trophies_{size}.png');self.assertEqual(im.size,(size*4,size*3));self.assertEqual(im.mode,'RGBA')
            for i in range(12):self.assertTrue(im.crop((i%4*size,i//4*size,(i%4+1)*size,(i//4+1)*size)).getchannel('A').getbbox())

    def test_confirmation_requires_explicit_commit(self):
        """Перевіряє сценарій «confirmation requires explicit commit» та очікувані результати."""
        import quest_dialog
        g=r.Game(4);q=g.mayor_offers()[0];app=SimpleNamespace(game=g,refresh=MagicMock());panel=SimpleNamespace(app=app,refresh=MagicMock())
        win=MagicMock();win.winfo_exists.return_value=True
        def close():win.winfo_exists.return_value=False
        win.close_dialog.side_effect=close
        buttons=[]
        def button(*a,**kw):buttons.append(kw);return MagicMock()
        canvas=MagicMock();canvas.winfo_width.return_value=600
        with patch('inspection_ui.window',return_value=win),patch('refinement_ui.Detail'),patch('quest_dialog.tk.Label'),patch('quest_dialog.tk.Canvas',return_value=canvas),patch('quest_dialog.icon'),patch('quest_dialog.ttk.Button',side_effect=button):
            quest_dialog.confirm(panel,q,'accept')
        self.assertFalse(g.quests)
        buttons[-1]['command']();self.assertTrue(any(t['id']==q['id'] for t in g.quests))
        count=len(g.quests);buttons[-1]['command']();self.assertEqual(len(g.quests),count)

    def test_quest_order_blue_cards_and_inline_button(self):
        """Перевіряє сценарій «quest order blue cards and inline button» та очікувані результати."""
        from refinement_ui import QuestCards
        g=r.Game(4)
        def quest(ident,city,progress,status='active'):
            return dict(id=ident,kind='hunt',city=city,progress=progress,goal=1,status=status,title=ident,reward=1,xp_reward=0)
        g.quests=[quest('away',1,1),quest('unfinished',0,0),quest('done',0,1,'done'),quest('here',0,1)]
        panel=SimpleNamespace(app=SimpleNamespace(game=g),mayor=False,rep_label=MagicMock(),selected=lambda:None,paint=MagicMock(),describe=MagicMock())
        QuestCards.refresh(panel)
        self.assertEqual([q['id'] for q in panel.entries],['here','away','unfinished','done'])
        canvas=MagicMock();canvas.winfo_width.return_value=420;canvas.winfo_height.return_value=424
        panel.canvas=canvas;panel.open_done=False;panel.selection=None
        with patch('refinement_ui.sprites.draw',return_value=False):QuestCards.paint(panel)
        self.assertEqual([ident for rect,ident in panel.turnin_rects],['here'])
        fills=[c.kwargs.get('fill') for c in canvas.create_rectangle.call_args_list]
        self.assertEqual(fills.count('#102c4a'),2)
