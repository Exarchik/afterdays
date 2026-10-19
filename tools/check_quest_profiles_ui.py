"""Edit native variants and authored quests; save/reload a temporary project only."""
import sys,tempfile,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from content_editor import ContentEditor
from entity_catalog import Store
from tests.test_entity_editor import project_copy
import quest_catalog
errors=[]
with tempfile.TemporaryDirectory() as folder:
    project=project_copy(folder);root=tk.Tk();root.geometry('1200x850')
    root.report_callback_exception=lambda *args:errors.append(''.join(traceback.format_exception(*args)))
    app=ContentEditor(root,project/'data/road_events.json',project);root.update()
    panel=app.quests
    for kind in {**quest_catalog.TYPES,**quest_catalog.SPECIAL}:
        panel.tree.selection_set('type:'+kind);root.update()
        assert panel.native.kind==kind and panel.native.winfo_ismapped()
        assert panel.commit()
    panel.tree.selection_set('type:hunt');root.update()
    panel.native.vars['title'].set('Полювання редактора')
    panel.native.vars['min_level'].set('7')
    panel.native.vars['reward'].set('200')
    panel.native.vars['art'].set('quest:cache')
    panel.native.variant_var.set('Елітний');panel.native.switch()
    panel.native.vars['reward'].set('600');panel.native.vars['min_level'].set('10')
    assert panel.commit()
    # Dosimeter minigame settings are edited only for their own quest type.
    panel.tree.selection_set('type:radiation_source');root.update()
    assert panel.native.extras['radiation_source'].winfo_ismapped() and not panel.native.extras['junkyard'].winfo_ismapped()
    panel.native.vars['grid_size'].set('5');panel.native.vars['max_dose'].set('3')
    panel.native.vars['device_radiation'].set('2');panel.native.vars['device_art'].set('quest:cache')
    assert panel.commit()
    panel.tree.selection_set('type:radiation_source');root.update()
    panel.native.vars['grid_size'].set('12')
    with patch('quest_profile_editor.messagebox.showerror') as error:
        assert not panel.native.commit();error.assert_called_once()
    panel.native.vars['grid_size'].set('5')
    panel.tree.selection_set('type:junkyard');root.update()
    assert panel.native.extras['junkyard'].winfo_ismapped() and not panel.native.extras['radiation_source'].winfo_ismapped()
    assert panel.native.vars['max_stamina'].get()=='30'
    panel.native.vars['parts'].set('4');panel.native.vars['max_stamina'].set('40');panel.native.vars['stamina_per_satiety'].set('2')
    assert panel.commit()
    panel.tree.selection_set('type:elite_hunt');root.update()
    assert panel.native.extras['elite_hunt'].winfo_ismapped() and not panel.native.extras['junkyard'].winfo_ismapped()
    assert panel.native.vars['drain'].get()=='38'
    panel.native.vars['needed'].set('4');panel.native.vars['drain'].set('45');panel.native.vars['recharge'].set('20');panel.native.vars['lens_speed'].set('60')
    assert panel.commit()
    panel.tree.selection_set('type:electronics_repair');root.update()
    assert panel.native.extras['electronics_repair'].winfo_ismapped() and not panel.native.extras['elite_hunt'].winfo_ismapped()
    assert panel.native.vars['contacts_max'].get()=='5'
    panel.native.vars['contacts_min'].set('5');panel.native.vars['contacts_max'].set('4')
    with patch('quest_profile_editor.messagebox.showerror') as error:
        assert not panel.native.commit();error.assert_called_once()
    panel.native.vars['contacts_min'].set('3');panel.native.vars['contacts_max'].set('4');panel.native.vars['decoys'].set('2');panel.native.vars['shock'].set('1')
    assert panel.commit()
    panel.tree.selection_set('type:delivery');root.update()
    assert not any(frame.winfo_ismapped() for frame in panel.native.extras.values())
    panel.add();root.update();panel.vars['elite'].set(True);panel.vars['art'].set('quest:hunt')
    panel.vars['xp_step'].set('8');panel.vars['money_power'].set('1.3')
    with patch('content_editor.messagebox.showerror') as error:
        assert app.save_all();error.assert_not_called()
    doc=Store(project).data['quests'];assert doc['native']['hunt']['normal']['min_level']==7
    assert doc['native']['hunt']['elite']['reward']==600
    assert doc['quests'][-1]['elite'] and doc['quests'][-1]['xp_step']==8
    radiation=doc['native']['radiation_source']['normal']
    junk=doc['native']['junkyard']['normal']
    assert (junk['parts'],junk['max_stamina'],junk['stamina_per_satiety'])==(4,40,2),junk
    repair=doc['native']['electronics_repair']['normal']
    assert (repair['contacts_min'],repair['contacts_max'],repair['decoys'],repair['hints'],repair['shock'])==(3,4,2,1,1),repair
    hunt=doc['native']['elite_hunt']['normal']
    assert (hunt['needed'],hunt['drain'],hunt['recharge'],hunt['lens_speed'])==(4,45,20,60),hunt
    assert (radiation['grid_size'],radiation['max_dose'],radiation['device_radiation'],radiation['device_art'])==(5,3,2,'quest:cache'),radiation
    panel.tree.selection_set('type:radiation_source' if '--radiation' in sys.argv else 'type:junkyard' if '--junkyard' in sys.argv else 'type:elite_hunt' if '--scanner' in sys.argv else 'type:electronics_repair' if '--electronics' in sys.argv else 'type:hunt');root.update()
    if '--screenshot' in sys.argv:
        root.lift();root.attributes('-topmost',True);root.update()
        def capture():
            from PIL import ImageGrab
            name='quest-profiles-radiation.png' if '--radiation' in sys.argv else 'quest-profiles-junkyard.png' if '--junkyard' in sys.argv else 'quest-profiles-scanner.png' if '--scanner' in sys.argv else 'quest-profiles-electronics.png' if '--electronics' in sys.argv else 'quest-profiles-editor.png'
            ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save('artifacts/'+name)
            root.quit()
        root.after(600,capture);root.mainloop()
    root.destroy()
assert not errors,'\n'.join(errors)
print('PASS: all native types editable, separate elite profile, art, dosimeter, junkyard, scanner and circuit settings, authored fields, atomic save and reload')
