"""One application with independent event and entity editing sections."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox
import event_catalog
import entity_catalog
from event_editor import Editor
from entity_editor import EntityPanel
from consumable_editor import ConsumablePanel
from art_library import Library
from art_editor import ArtPanel
from quest_editor import QuestPanel
from dialogue_editor import DialoguePanel
from faction_editor import FactionPanel, HumanPanel


class ContentEditor(ttk.Frame):
    def __init__(self,root,event_path=event_catalog.PATH,project_root=entity_catalog.ROOT):
        super().__init__(root);self.pack(fill='both',expand=True);self.root=root
        root.title('Afterdays — редактор контенту');root.geometry('1320x860');root.minsize(1100,720)
        self.store=entity_catalog.Store(project_root)
        self.library=Library(self.store);root._editor_art_library=self.library
        self.tabs=ttk.Notebook(self);self.tabs.pack(fill='both',expand=True)
        self.quests=QuestPanel(self.tabs,self.store,self.save_all)
        self.tabs.add(self.quests,text='Квести')
        self.dialogues=DialoguePanel(self.tabs,self.store,self.save_all)
        self.tabs.add(self.dialogues,text='Діалоги')
        event_tab=ttk.Frame(self.tabs);self.tabs.add(event_tab,text='Випадкові події')
        self.events=Editor(event_tab,event_path,embedded=True)
        self.events.save_handler=self.save_all
        self.panels={}
        for section,title in entity_catalog.SECTIONS.items():
            panel=EntityPanel(self.tabs,self.store,section,self.save_all)
            self.tabs.add(panel,text=title);self.panels[section]=panel
            if section=='module':
                self.items=ConsumablePanel(self.tabs,self.store,self.save_all);self.tabs.add(self.items,text='Предмети')
        self.humans=HumanPanel(self.tabs,self.store,self.save_all);self.tabs.add(self.humans,text='Люди')
        self.factions=FactionPanel(self.tabs,self.store,self.save_all);self.tabs.add(self.factions,text='Фракції')
        self.tabs.bind('<<NotebookTabChanged>>',lambda e:self.factions.refresh_choices() if self.tabs.select()==str(self.factions) else None)
        self.arts=ArtPanel(self.tabs,self.library,self.commit,self.refresh_assets,self.save_all,lambda:self.events.document['events'])
        self.tabs.add(self.arts,text='Арти')
        root.bind('<Control-s>',lambda e:self.save_all())
        root.protocol('WM_DELETE_WINDOW',self.close)

    def refresh_assets(self):
        self.humans.show_art()
        self.items.refresh_preview()
        self.events.refresh_art()
        self.dialogues.show_art()
        for panel in self.panels.values():
            if panel.current:panel.open(panel.current)

    def commit(self):
        if not self.humans.commit():self.tabs.select(self.humans);return False
        self.factions.refresh_choices()
        if not self.factions.commit():self.tabs.select(self.factions);return False
        if not self.items.commit():self.tabs.select(self.items);return False
        if not self.quests.commit():self.tabs.select(self.quests);return False
        if not self.dialogues.commit():self.tabs.select(self.dialogues);return False
        if not self.events.commit():self.tabs.select(2);return False
        for section,panel in self.panels.items():
            if not panel.commit():self.tabs.select(panel);return False
        return True

    def save_all(self):
        if not self.commit():return False
        try:
            errors=event_catalog.validate(self.events.document,art=self.store.art,consumables=self.store.data['consumables'])+self.store.validate()
            if errors:raise ValueError('\n'.join(errors))
            self.store.check_disk()
            if self.events.path.read_bytes()!=self.events.disk:
                raise ValueError('Каталог подій змінено іншою програмою. Перезапустіть редактор.')
            # Catalogs and localized names/sprites roll back together on an I/O failure.
            extra=None
            if self.events.document!=self.events.baseline:
                document=copy.deepcopy(self.events.document)
                document['events']=event_catalog.ordered(document['events'])
                extra=(self.events.path,document,self.events.disk)
            self.store.save(extra)
            self.events.disk=self.events.path.read_bytes();self.events.baseline=copy.deepcopy(self.events.document)
            self.events.rebuild();self.events.status.set('Збережено · Перезапустіть гру')
        except (ValueError,OSError) as exc:
            messagebox.showerror('Зміни не збережено',str(exc),parent=self.root);return False
        for panel in self.panels.values():panel.rebuild();panel.status.set('Збережено · Перезапустіть гру; уже створені предмети в сейві зберігають свої характеристики')
        self.items.rebuild()
        self.humans.rebuild();self.factions.rebuild()
        self.humans.status.set('Збережено · Перезапустіть гру')
        self.factions.status.set('Збережено · Перезапустіть гру')
        self.dialogues.rebuild();self.dialogues.status.set('Діалоги збережено')
        self.quests.rebuild();self.quests.status.set('Квести збережено · Перезапустіть гру')
        self.arts.rebuild();self.arts.status.set('Арти збережено · Перезапустіть гру')
        self.items.refresh_preview()
        if self.store.asset_cleanup_warning:self.arts.status.set(self.store.asset_cleanup_warning)
        return True

    def close(self):
        if not self.commit():
            if messagebox.askyesno('Незбережені зміни','Закрити й відкинути незбережені зміни?',parent=self.root):self.root.destroy()
            return
        if self.store.dirty or self.events.document!=self.events.baseline:
            answer=messagebox.askyesnocancel('Незбережені зміни','Зберегти зміни в усіх розділах?',parent=self.root)
            if answer is None or (answer and not self.save_all()):return
        self.root.destroy()
