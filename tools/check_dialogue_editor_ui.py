"""Exercise dialogue authoring and play testing with temporary project data."""
import sys,tempfile,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from content_editor import ContentEditor
from test_entity_editor import project_copy
from entity_catalog import Store
from dialogue_editor import ReplyDialog,RuleDialog,VariableDialog,ActorDialog

with tempfile.TemporaryDirectory() as folder:
    project=project_copy(folder);root=tk.Tk();ttk.Style(root).theme_use('clam')
    try:
        app=ContentEditor(root,project/'data/road_events.json',project);root.update()
        assert app.tabs.tab(0,'text')=='Квести' and app.tabs.tab(1,'text')=='Діалоги'
        assert len(app.tabs.tabs())==9
        panel=app.dialogues;app.tabs.select(panel);root.update()
        assert app.commit() and not app.store.dirty
        original=copy.deepcopy(panel.doc)
        tester=panel.test();root.update()
        assert tester.image
        tester.choose('help');assert tester.session.values['helped'] and tester.session.rewards['parts']==12
        tester.choose('secret');tester.choose();tester.dialogue.set('demo_trusted');tester.switch();assert tester.session.block
        assert panel.doc==original
        tester.reset();tester.choose('refuse');assert not tester.session.rewards
        tester.destroy()
        # Shared continuation appears once, with clickable references from other replies.
        panel.open('noise_in_the_wind_radio');root.update()
        assert len(panel.dialogue['nodes'])==2 and len(panel.links)==2
        panel.tree.selection_set(next(iter(panel.links)));panel.select_node();root.update()
        assert panel.current_node=='invitation'
        reply=panel.dialogue['nodes']['radio_call']['replies'][0]
        form=ReplyDialog(root,panel.doc,panel.quests,reply,panel.dialogue['nodes'])
        assert form.read()['next']=='invitation';form.destroy()
        # Create an NPC response and child block with conditions and effects.
        panel.open('demo_crossroads');panel.open_node('greeting')
        def reply_result(dialog):
            result=dict(dialog.original,text='Я повернуся пізніше.',conditions=[],actions=[dict(kind='add',variable='trust',value=2)],next='__new__')
            dialog.destroy();return result
        with patch.object(ReplyDialog,'show',reply_result):
            panel.add_reply()
        panel.actor.set('player — Головний герой');panel.text.delete('1.0','end');panel.text.insert('1.0','До зустрічі!');assert panel.commit()
        panel.add_next();assert panel.current_node
        panel.text.delete('1.0','end');panel.text.insert('1.0','Новий етап розмови.');assert panel.commit()
        # Actor and variable form values, including pending artwork library selection.
        actor=ActorDialog(root,dict(name='Сталкер',art='npc:traveler'));assert actor.read()['name']=='Сталкер';actor.destroy()
        var=VariableDialog(root);var.key.set('test_counter');var.kind.set('Ціле число');var.value.set('2');key,value=var.read();var.destroy()
        panel.doc['variables'][key]=value
        rule=RuleDialog(root,panel.doc,panel.quests,action=True);rule.variable.set(key);rule.kind.set('Додати до змінної');rule.value.set('3');assert rule.read()['value']==3;rule.destroy()
        assert app.save_all();loaded=Store(project);assert loaded.data['dialogues']==panel.doc
        panel.open('demo_crossroads');root.update()
        if len(sys.argv)>1:
            from PIL import ImageGrab
            root.lift();root.update();root.after(300,lambda:None);root.after(300,root.quit);root.mainloop();ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(sys.argv[1])
        # Reopen without introducing catalog changes.
        app.destroy();app=ContentEditor(root,project/'data/road_events.json',project);root.update();assert app.commit() and not app.store.dirty
        print('Dialogue UI passed: tree, actor art, variables, responses, isolated tester, branches, shared save/reload')
    finally:root.destroy()
