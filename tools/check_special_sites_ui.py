"""Check editable locations without writing the user's catalogs."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from unittest.mock import patch
from content_editor import ContentEditor
from site_editor import StockDialog
root=tk.Tk();app=ContentEditor(root);app.tabs.select(app.sites);root.update()
panel=app.sites
with patch('site_editor.simpledialog.askstring',return_value='Тест UI'):
    panel.add()
ident=panel.current;panel.npc.set('Тестовий мешканець');panel.role.set('Квести й торгівля')
panel.preset(('food','med'));assert panel.commit()
assert app.store.data['special_sites'][ident]['npc']=='Тестовий мешканець'
dialog=StockDialog(root,app.store,dict(kind='food',item_id='item_food',amount=4,chance=.5))
assert dialog.read()['item_id']=='item_food';dialog.destroy()
root.update()
from PIL import ImageGrab
ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save('artifacts/special-sites-editor.png')
with patch('site_editor.messagebox.askyesno',return_value=True):panel.delete()
assert ident not in app.store.data['special_sites']
root.destroy();print('PASS: special site add/edit/delete, role, art preview and stock rule dialog')
