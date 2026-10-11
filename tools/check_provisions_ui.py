"""Render the inventory and exercise food dragging without opening a save."""
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from PIL import ImageGrab
from game.model import Game
from game import items
from visuals import EquipmentPanel
from ui.refinement import description

root=tk.Tk();root.geometry('620x720+40+40')
g=Game(5);g.bag=[items.supply('food',6),items.supply('item_custom_002',2),items.supply('med',3)]
app=SimpleNamespace(game=g,description=lambda i:description(g,i),modify=lambda:None,equip_selected=lambda:None)
panel=EquipmentPanel(root,app);panel.pack(fill='both',expand=True)
app.refresh=panel.refresh
def act(fn):fn();panel.refresh()
app.act=act
panel.refresh();root.update()
def put(item,slot,source=None):
    x,y,d,e=panel.provision_slots[slot]
    panel.drop(dict(item=item,slot=source),panel.paper.winfo_rootx()+(x+d)/2,panel.paper.winfo_rooty()+(y+e)/2)
first,second=g.bag[:2]
put(first,2);put(second,2)
assert first['qty']==5 and second['qty']==1
assert [i['qty'] for i in g.provisions]==[1,1]
second_bag=second
first,second=g.provisions
put(second,0,'provision');assert g.provisions==[second,first]
panel.drop(dict(item=second,slot='provision'),panel.grid.canvas.winfo_rootx()+10,panel.grid.canvas.winfo_rooty()+10)
assert g.provisions==[first] and second_bag['qty']==2
put(second_bag,2)
root.update()
ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save('artifacts/provisions-preview.png')
root.destroy()
print('Provision UI: drag, reorder, return and rendering OK')
