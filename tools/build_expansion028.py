"""Slice the generated companion atlas; offline Pillow only, never needed to play."""
from pathlib import Path
import json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
KEYS=['module_carbon_grip','module_tactical_grip','module_electronic_compensator','module_phase_approximator','module_gauss_accelerator','module_polyfiber','module_quantum_mirror','module_synthetic_fiber','module_lead_fibers','npc_diver','npc_storekeeper','npc_guide','npc_energy_engineer','npc_master','npc_locksmith','npc_money_changer','npc_quartermaster','npc_guard']

def build():
    source=Image.open(ROOT/'assets/expansion028_source.png').convert('RGBA')
    # Reviewed source gutters: row three begins above the nominal uniform grid.
    # Preserve complete heads/objects instead of cutting at a guessed square boundary.
    xs=[0,295,591,887,1183,1479,1774];ys=[0,297,575,887]
    tiles=[]
    for i in range(18):
        x,y=i%6,i//6;tile=source.crop((xs[x],ys[y],xs[x+1],ys[y+1]))
        box=tile.getchannel('A').getbbox();tiles.append(tile.crop(box) if box else tile)
    for size in (16,24,32,48,64,96,144,192):
        sheet=Image.new('RGBA',(6*size,3*size))
        for i,tile in enumerate(tiles):
            pic=tile.copy();pad=max(1,round(size*.04));pic.thumbnail((size-2*pad,size-2*pad),Image.Resampling.LANCZOS)
            sheet.alpha_composite(pic,(i%6*size+(size-pic.width)//2,i//6*size+(size-pic.height)//2))
        sheet.save(ROOT/f'assets/expansion028_{size}.png',optimize=True)
    for width in (48,56,64,80,96,128):
        sheet=Image.new('RGBA',(16*width,2*72));shade=Image.new('RGBA',(width,72))
        for y in range(72):
            alpha=round(215*max(0,(y-37)/34))
            if alpha:shade.paste((12,18,17,alpha),(0,y,width,y+1))
        for i,tile in enumerate(tiles):
            pic=tile.copy();pic.thumbnail((width-2,70),Image.Resampling.LANCZOS)
            cell=Image.new('RGBA',(width,72));cell.alpha_composite(pic,((width-pic.width)//2,(72-pic.height)//2));cell.alpha_composite(shade)
            sheet.alpha_composite(cell,(i%16*width,i//16*72))
        sheet.save(ROOT/f'assets/inventory_expansion028_{width}.png',optimize=True)
    p=ROOT/'data/sprites.json';data=json.loads(p.read_text())
    data.update({k:dict(index=i,sheet='expansion028',columns=6,inventory_sheet='inventory_expansion028') for i,k in enumerate(KEYS)})
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':build()
