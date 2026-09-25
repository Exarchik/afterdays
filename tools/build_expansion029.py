"""Offline atlas packing (Pillow). Runtime uses cached Tk PNG sheets only."""
from pathlib import Path
import json,sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import content
QUESTS=['junkyard','field_test','generator','cache','elite_hunt','repair_delivery','permit','thanks','delivery','radio','trophies','metro','torn_map','recruit_smith','recruit_tech','settlement_permission']
ITEMS=['repairkit','courier_parcel','stash_parcel','relic_item','junk_component','metro_component','torn_map_item','restored_map_item','settlement_permit','service_metro','service_board','service_cartographer','action_delivery','action_radio','dungeon_chest','dungeon_exit']
PEOPLE=['npc_printer','npc_meteorologist','npc_doctor','npc_communications','npc_hunter','npc_roamer_smith','npc_cartographer','npc_roamer_tech','npc_wounded']
EVENTS=['wounded','wreck','camp','mines','signal','pilgrims','provisions','snare','safe','pharmacy','terminal','courier','toll','storm','meteor','water']
KEYS=['quest:'+k for k in QUESTS]+ITEMS+PEOPLE+['event_theme:'+k for k in EVENTS]+['corpse:monster_'+k for k in ['rodent','feral','blind_hound','spitter','ash_wolf','acid_tick','shellback','swamp_mutant','sentry_drone','chimera_spider','spark','bone_giant']]+['obstacle:forest','obstacle:ruin','obstacle:cliff','obstacle:barricade']
CUTS={'quests':([0,314,627,940,1254],[0,314,627,931,1254]),'items':([0,341,634,951,1268],[0,314,620,928,1240]),'people':([0,418,836,1254],[0,418,834,1254]),'events':([0,321,634,952,1269],[0,310,629,907,1240]),'corpses':([0,314,627,940,1254],[0,314,627,940,1254])}
def build():
 tiles=[]
 for group,(xs,ys) in CUTS.items():
  source=Image.open(ROOT/f'assets/expansion029_{group}_source.png').convert('RGBA')
  for y in range(len(ys)-1):
   for x in range(len(xs)-1):
    tile=source.crop((xs[x],ys[y],xs[x+1],ys[y+1]));box=tile.getchannel('A').getbbox();tiles.append(tile.crop(box) if box else tile)
 assert len(tiles)==len(KEYS)
 for size in (16,24,32,48,64,96,144,192):
  sheet=Image.new('RGBA',(8*size,((len(tiles)+7)//8)*size))
  for i,tile in enumerate(tiles):
   pic=tile.copy();pad=max(1,round(size*.04));pic.thumbnail((size-2*pad,size-2*pad),Image.Resampling.LANCZOS)
   sheet.alpha_composite(pic,(i%8*size+(size-pic.width)//2,i//8*size+(size-pic.height)//2))
  sheet.save(ROOT/f'assets/expansion029_{size}.png',optimize=True)
 for width in (48,56,64,80,96,128):
  sheet=Image.new('RGBA',(16*width,((len(tiles)+15)//16)*72));shade=Image.new('RGBA',(width,72))
  for y in range(38,72):shade.paste((12,18,17,round(215*(y-37)/34)),(0,y,width,y+1))
  for i,tile in enumerate(tiles):
   pic=tile.copy();pic.thumbnail((width-2,70),Image.Resampling.LANCZOS)
   cell=Image.new('RGBA',(width,72));cell.alpha_composite(pic,((width-pic.width)//2,(72-pic.height)//2));cell.alpha_composite(shade)
   sheet.alpha_composite(cell,(i%16*width,i//16*72))
  sheet.save(ROOT/f'assets/inventory_expansion029_{width}.png',optimize=True)
 path=ROOT/'data/sprites.json';data=json.loads(path.read_text());data.update({key:dict(index=i,sheet='expansion029',columns=8,inventory_sheet='inventory_expansion029') for i,key in enumerate(KEYS)})
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':build()
