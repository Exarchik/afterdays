import copy,json,math,random,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
import afterdays as r
import progression as p
import frontier,metro_routes,refinement_ui
from radio_interference import Interference
from tests_fixtures.quest_offer import offer_for

class SettlementTests(unittest.TestCase):
 def test_nearest_chain_has_five_unique_stations(self):
  for seed in range(10):
   g=r.Game(seed);order=metro_routes.station_order(g);self.assertEqual(order[0],0);self.assertEqual(set(order),set(frontier.METRO_CITIES));self.assertEqual(len(order),5)
   for n in range(1,5):self.assertEqual(order[n],min(order[n:],key=lambda k:(math.dist(g.cities[order[n-1]],g.cities[k]),k)))
   self.assertIn(10,g.mayors)
 def test_fog_masks_segments_and_unknown_branch_dim(self):
  g=r.Game(2);c=MagicMock();metro_routes.draw(c,g,1,0,0,lambda x,y:False);c.create_line.assert_not_called();c.create_oval.assert_not_called()
  metro_routes.draw(c,g,1,0,0,lambda x,y:True);self.assertEqual(c.create_line.call_count,4);self.assertEqual(c.create_oval.call_count,5)
  self.assertTrue(all(call.kwargs['fill']=='#47615d' for call in c.create_line.call_args_list))
  pieces=list(metro_routes.visible_segments([0,0],[10,0],lambda x,y:x<3 or x>=7))
  self.assertEqual(len(pieces),2);self.assertLessEqual(pieces[0][2],3);self.assertGreaterEqual(pieces[1][0],7)
 def test_city_neighbors_safe_and_saved_world_changes_only_there(self):
  fixture=Path(__file__).parent/'tests_fixtures/save_v0151.json';old=json.loads(fixture.read_text());g=r.Game.load(fixture)
  safe={(x,y) for cx,cy in g.cities[:12] for x in range(max(0,cx-1),min(48,cx+2)) for y in range(max(0,cy-1),min(32,cy+2))}
  for y,row in enumerate(old['world']):
   for x,tile in enumerate(row):self.assertEqual(g.world[y][x],'waste' if (x,y) in safe and tile=='cliff' else tile)
  for seed in range(5):
   g=r.Game(seed);g.build_radiation()
   for cx,cy in g.cities[:12]:
    for x in range(cx-1,cx+2):
     for y in range(cy-1,cy+2):
      if 0<=x<48 and 0<=y<32:self.assertNotEqual(g.world[y][x],'cliff');self.assertNotIn(f'{x},{y}',g.radiation)
 def test_sale_stability_threshold_and_no_resale_profit(self):
  g=r.Game(4);g.money=100000;g.local_record()['value']=59;items=g.stock(0)
  self.assertFalse(any(i.get('promotion') for i in items));g.local_record()['value']=60
  with patch.object(g.rng,'random',return_value=0):items=g.stock(0)
  item=next(i for i in items if i.get('promotion'));snapshot=copy.deepcopy(item)
  for _ in range(10):g.stock(0)
  self.assertEqual(item,snapshot)
  for discount in (30,50,75):
   item['promotion']['discount']=discount;base=super(type(g),g).price(item,0,True)
   self.assertEqual(g.price(item,0),max(2,round(base*(1-discount/100))))
   self.assertLess(g.price(item,0,False),g.price(item,0,True))
  cost=g.price(item,0);before=g.money;self.assertTrue(g.buy(item['id'],0));self.assertEqual(before-g.money,cost);self.assertNotIn('promotion',item)
  g.local_record()['value']=100
  self.assertLess(g.price(item,0,False),cost);self.assertTrue(g.sell(item['id'],0));self.assertLess(g.money,before)
 def test_sale_purchase_failure_and_reload(self):
  g=r.Game(4);g.local_record()['value']=60;g.stock(0)
  entry=next(v for v in g.shops.values() if 'special_checked' in v);item=next(i for i in entry['items'] if i['kind']=='module');item['promotion']=dict(city=0,merchant=0,discount=75)
  g.money=0;self.assertFalse(g.buy(item['id'],0));self.assertIn('promotion',item);self.assertNotIn('paid_sale_cap',item)
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);h=r.Game.load(path)
  self.assertEqual(g.shops,h.shops);self.assertEqual(g.price(item,0),h.price(item,0))
 def test_chest_contents_keep_paid_sale_cap(self):
  g=r.Game(3);g.local_record()['value']=100;g.money=100000
  item=next(i for i in g.stock(2) if i['kind']=='sealed');item['promotion']=dict(city=0,merchant=2,discount=75);cost=g.price(item,2)
  self.assertTrue(g.buy(item['id'],2));gear=g.open_chest(item['id']);self.assertIsNotNone(gear);self.assertLess(g.price(gear,0,False),cost)
 def test_generator_wrong_only_can_shock_and_failure_uses_normal_defeat(self):
  g=r.Game(4);offer=offer_for(g,'generator');g.accept_quest(offer['id']);q=g.quests[-1];g.x,g.y=q['pos'];good=q['generator_order'][0];wrong=(good+1)%5
  with patch.object(g.rng,'random',return_value=0),patch.object(g.rng,'randint',return_value=5):
   hp=g.hp;g.generator_toggle(q['id'],good);self.assertEqual(g.hp,hp)
   g.generator_toggle(q['id'],good);self.assertEqual(g.hp,hp-5);self.assertEqual(q['generator_input'],[])
   g.hp=1;g.generator_toggle(q['id'],wrong);self.assertGreater(g.hp,0);self.assertEqual([g.x,g.y],g.cities[0]);self.assertFalse(g.quest_ready(q))
 def test_generator_error_without_shock(self):
  g=r.Game(4);offer=offer_for(g,'generator');g.accept_quest(offer['id']);q=g.quests[-1];g.x,g.y=q['pos'];hp=g.hp
  with patch.object(g.rng,'random',return_value=.9):g.generator_toggle(q['id'],(q['generator_order'][0]+1)%5)
  self.assertEqual(g.hp,hp);self.assertEqual(g._generator_shock,0)
 def test_noise_is_temporary_and_trace_changes(self):
  noise=Interference(0,random.Random(4));self.assertFalse(noise.advance(0));self.assertTrue(7<=noise.next<=13)
  now=noise.next;self.assertTrue(noise.advance(now));self.assertTrue(2<=noise.next-now<=4)
  first=noise.trace(520,175);self.assertNotEqual(first,noise.trace(520,175));self.assertEqual(len(first)%2,0)
  self.assertFalse(noise.advance(noise.next))
 def test_trade_price_next_to_title_and_colors(self):
  from advanced_ui import TradingPanel
  g=r.Game(4);item=p.equipment('weapon_ash_pistol');panel=SimpleNamespace(app=SimpleNamespace(game=g,description=lambda i:refinement_ui.description(g,i)),merchant=0,source='stock',item=lambda:item,amount=lambda i:1,preview=MagicMock(),detail=MagicMock())
  with patch('advanced_ui.icon'),patch('advanced_ui.sprites.draw'):
   g.money=0;TradingPanel.describe(panel);self.assertEqual(panel.detail.text.insert.call_args.args[0],'1.end');self.assertEqual(panel.detail.text.insert.call_args.args[-1],'bad')
   g.money=100000;TradingPanel.describe(panel);self.assertEqual(panel.detail.text.insert.call_args.args[-1],'good')
   panel.source='bag';item['quest_id']='test';TradingPanel.describe(panel);self.assertEqual(panel.detail.text.insert.call_args.args[-1],'bad')

if __name__=='__main__':unittest.main()
