"""Game application and explicit GUI entry point."""
import module_rules
import ui.event as event_ui
import ui.restoration as restoration_ui
import ui.widgets as widgets
import world_hex
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from debug_config import TEST_MODE, MapVisibility
from i18n import t as tr
from game.model import Game
from game.catalog import MERCHANTS, TERRAINS
import game.catalog as catalog
from game.systems.reputation import buy_factor
from game.systems.reputation import sell_factor
import ui.dialogs as messagebox
import visuals
import ui.advanced as advanced_ui
import game.systems.adventure as adventure
import ui.adventure as adventure_ui
import ui.refinement as refinement_ui
import sprites
import terrain_tiles

BG, PANEL, TEXT, MUTED, GOLD = '#141c1a', '#202b27', '#e4e8d9', '#a4b2a4', '#d7b77a'
save_path = Path.home() / 'Afterdays' / 'save.json'

class App(MapVisibility):
    def __init__(self, root):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        self.root = root
        root.app=self
        self.game = Game()
        self.game.prepare_campaign()
        self.show_full_map = False
        self.perk_prompted = -1
        self.mode = 'world'
        self.selection = None
        self.inventory_ids = []
        self.shop_ids = []
        self.merchant = 0
        self.dialog = None
        self.hover = None
        root.after_idle(lambda:sprites.decorate(root))
        root._afterdays_app=self
        root.title(tr('afterdays.0131'))
        sw,sh=root.winfo_screenwidth(),root.winfo_screenheight()
        root.geometry(f'1260x880+{max(0,(sw-1260)//2)}+{max(0,(sh-880)//2)}')
        root.minsize(1080, 760)
        root.configure(bg=BG)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background=PANEL, foreground=TEXT, font=('Segoe UI', 10))
        style.configure('TButton', padding=(9, 7), background='#344238', foreground=TEXT)
        style.map('TButton', background=[('active', '#536348')], foreground=[('disabled', '#68746a')])
        style.configure('TCombobox',fieldbackground='#263a2e',foreground=TEXT)
        style.configure('TSpinbox',fieldbackground='#263a2e',foreground=TEXT)
        style.configure('TNotebook.Tab', padding=(3, 8), font=('Segoe UI',9))
        style.map('TNotebook.Tab', background=[('selected', '#516044')])
        header = tk.Frame(root, bg=BG)
        header.pack(fill='x', padx=18, pady=(12, 6))
        tk.Label(header, text='A F T E R D A Y S', bg=BG, fg=GOLD, font=('Segoe UI', 18, 'bold')).pack(side='left')
        tk.Label(header, text=tr('afterdays.0132'), bg=BG, fg=MUTED, font=('Segoe UI', 10)).pack(side='left')
        from ui.hud import StatusBar, system_menu
        system_menu(header,self)
        self.status = StatusBar(root,self)
        self.status.pack(fill='x', padx=18)
        body = tk.Frame(root, bg=BG)
        body.pack(fill='both', expand=True, padx=18, pady=10)
        left = tk.Frame(body, bg=BG)
        body.columnconfigure(0, weight=2, uniform='halves')
        body.columnconfigure(1, weight=1, uniform='halves')
        body.rowconfigure(0,weight=1)
        left.grid(row=0,column=0,sticky='nsew',padx=(0,6))
        left.pack_propagate(False)
        self.map_title = tk.Label(left, bg=BG, fg=GOLD, anchor='w', font=('Segoe UI', 12, 'bold'))
        self.map_title.pack(fill='x', pady=(0, 6))
        self.canvas = tk.Canvas(left, bg='#17201c', highlightthickness=1, highlightbackground='#475244')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.canvas.bind('<Button-1>', self.map_click)
        self.canvas.bind('<Double-Button-1>', lambda e:self.map_click(e,start=True))
        self.canvas.bind('<Motion>', self.map_hover)
        self.canvas.bind('<Leave>',self.clear_battle_hover)
        import ui.inspection as inspection_ui
        self.canvas.bind('<Button-3>',lambda e:widgets.map_context(self,e))
        self.hint = tk.Label(left, bg=BG, fg=MUTED, anchor='w', justify='left', wraplength=680, height=4)
        self.hint.pack(fill='x', pady=5)
        controls = tk.Frame(left, bg=BG)
        controls.pack(fill='x')
        from ui.actions import ActionButton, styles
        styles(root)
        self.end_button = ActionButton(controls,'end','◷',tr('afterdays.0137'), command=lambda: self.act(self.game.end_turn))
        self.end_button.pack(side='left', padx=2)
        ActionButton(controls,'switch','⇄',tr('afterdays.0138'), command=lambda: self.act(self.game.switch)).pack(side='left', padx=2)
        ActionButton(controls,'med','✚',tr('afterdays.0139'), command=lambda: self.act(lambda: self.game.use('med'))).pack(side='left', padx=2)
        self.flee_button = ActionButton(controls,'flee','↪',tr('afterdays.0140'), command=lambda: self.act(self.game.flee))
        self.flee_button.pack(side='left', padx=2)
        from ui.route import RouteController
        self.route=RouteController(self)
        self.route_button=ActionButton(controls,'move','▶',tr('journey.resume'),command=self.route.toggle,state='disabled')
        self.route_button.pack(side='left',padx=2)
        ActionButton(controls,'search','⌕',tr('afterdays.0141'),command=lambda:self.act(self.game.search)).pack(side='left',padx=2)
        side = tk.Frame(body, bg=PANEL, width=380)
        side.grid(row=0,column=1,sticky='nsew',padx=(6,0))
        side.pack_propagate(False)
        buttons = controls.winfo_children()

        for button in buttons:
            button.pack_forget()

        for n, button in enumerate(buttons):
            button.grid(
                row=0, column=n,
                sticky='ew', padx=2, pady=2
            )
        controls.columnconfigure(tuple(range(6)),weight=1)
        self.root.after_idle(lambda:self.hint.config(wraplength=max(300,left.winfo_width()-10)))
        self.tabs = ttk.Notebook(side)
        self.tabs.pack(fill='both', expand=True)
        self.world_tab, self.inv_tab, self.loot_tab, self.quest_tab = [ttk.Frame(self.tabs) for _ in range(4)]
        for tab, title in [(self.world_tab, tr('afterdays.0142')), (self.inv_tab, tr('afterdays.0143')), (self.loot_tab, tr('afterdays.0144')), (self.quest_tab, tr('afterdays.0145'))]:
            key={self.world_tab:'site',self.inv_tab:'backpack',self.loot_tab:'loot',self.quest_tab:'journal'}[tab]
            art=sprites.photo(root,key,16)
            self.tabs.add(tab,text=title,**({'image':art,'compound':'left'} if art else {}))
        import ui.frontier as frontier_ui
        self.player_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.player_tab,text=tr('afterdays.0146'))
        self.player_panel=frontier_ui.PlayerPanel(self.player_tab,self)
        self.player_panel.pack(fill='both',expand=True)
        self.perks_tab=ttk.Frame(self.tabs)
        self.tabs.add(self.perks_tab,text=tr('update024.perks_tab'))
        self.perks_panel=refinement_ui.PerksPanel(self.perks_tab,self)
        self.perks_panel.pack(fill='both',expand=True)
        self.cartographer=lambda:frontier_ui.cartographer(self)
        self.guide=lambda:frontier_ui.guide(self)
        self.metro=lambda:frontier_ui.metro(self)
        world_page = self.world_tab
        world_canvas = tk.Canvas(world_page, bg=PANEL, highlightthickness=0)
        world_scroll = ttk.Scrollbar(world_page, command=world_canvas.yview)
        world_scroll.pack(side='right', fill='y')
        world_canvas.pack(side='left', fill='both', expand=True)
        world_canvas.configure(yscrollcommand=world_scroll.set)
        self.world_tab = ttk.Frame(world_canvas)
        world_window = world_canvas.create_window(0, 0, window=self.world_tab, anchor='nw')
        self.world_tab.bind('<Configure>', lambda e: world_canvas.configure(scrollregion=world_canvas.bbox('all')))
        world_canvas.bind('<Configure>', lambda e: world_canvas.itemconfigure(world_window, width=e.width))
        self.location = tk.Label(self.world_tab, bg=PANEL, fg=TEXT, font=('Segoe UI', 12, 'bold'), wraplength=335, justify='left')
        self.location.pack(fill='x', padx=12, pady=15)
        self.city_info = tk.Label(self.world_tab, bg=PANEL, fg=MUTED, justify='left', wraplength=340)
        self.city_info.pack(fill='x', padx=12, pady=8)
        self.services = adventure_ui.Services(self.world_tab,self)
        self.services.pack(fill='x',padx=6,pady=4)
        tk.Label(self.world_tab, text=tr('afterdays.0147'), bg=PANEL, fg=GOLD).pack(anchor='w', padx=12, pady=(20, 8))
        self.cities_label = tk.Label(self.world_tab, bg=PANEL, fg=MUTED, justify='left')
        self.cities_label.pack(anchor='w', padx=12)
        self.inv_panel = visuals.EquipmentPanel(self.inv_tab, self)
        self.inv_panel.pack(fill='both', expand=True)
        self.quest_panel = refinement_ui.QuestCards(self.quest_tab, self)
        self.quest_panel.pack(fill='both', expand=True)
        self.loot_list = visuals.ItemGrid(self.loot_tab,lambda i:self.loot_detail.config(text=self.description(next((x for x in self.game.loot if x['id']==i),None))),height=240)
        self.loot_list.pack(fill='both',expand=True,padx=6,pady=6)
        self.loot_detail=refinement_ui.Detail(self.loot_tab,height=8)
        self.loot_detail.pack(fill='x',padx=8)
        ttk.Button(self.loot_tab, text=tr('afterdays.0148'), command=self.collect_selected).pack(fill='x', padx=10, pady=5)
        ttk.Button(self.loot_tab, text=tr('afterdays.0149'), command=self.collect_all).pack(fill='x', padx=10, pady=5)
        ttk.Button(self.loot_tab,text='Відкрити сховок на локації',command=lambda:event_ui.show_loot(self)).pack(fill='x',padx=10,pady=5)
        tk.Label(self.loot_tab, text=tr('afterdays.0150'), bg=PANEL, fg=MUTED, justify='left').pack(padx=10, pady=12)
        logframe = tk.Frame(root, bg=PANEL)
        logframe.pack(fill='x', padx=18, pady=(0, 12))
        self.logbox = tk.Text(logframe, height=3, bg=PANEL, fg=MUTED, relief='flat', font=('Segoe UI', 10), padx=10, pady=6, state='disabled')
        self.logbox.pack(fill='x')
        root.bind_class('AfterdaysKeys', '<KeyPress>', self.key)
        def bind_keys(widget):
            widget.bindtags(('AfterdaysKeys',) + widget.bindtags())
            for child in widget.winfo_children():
                bind_keys(child)
        bind_keys(root)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root._afterdays_app=self
        self.fx=adventure_ui.Effects(self)
        self.refresh()

    def listbox(self, parent, height=14):
        """Створює список із прокручуванням для вибору елементів."""
        frame = tk.Frame(parent, bg=PANEL)
        frame.pack(fill='both', expand=True, padx=8, pady=8)
        scroll = ttk.Scrollbar(frame)
        scroll.pack(side='right', fill='y')
        box = tk.Listbox(frame, bg='#18211d', fg=TEXT, selectbackground='#4e5b42', selectforeground='white',
                         font=('Segoe UI', 10), relief='flat', highlightthickness=0, height=height,
                         exportselection=False, yscrollcommand=scroll.set)
        box.pack(side='left', fill='both', expand=True)
        scroll.config(command=box.yview)
        return box

    def act(self, fn):
        """Виконує ігрову дію та оновлює інтерфейс."""
        self.route.pause()
        if self.fx.blocked:
            return
        before_battle = self.game.battle is not None
        import event_results
        before_items=event_results.snapshot(self.game)
        before_events=len(self.game._events)
        before_reports=len(getattr(self.game,'_event_results',[]))
        fn()
        if (getattr(fn,'__name__','')=='search' and not before_battle and not self.game.battle and
            len(getattr(self.game,'_event_results',[]))==before_reports and
            any(i.get('qty',1)>before_items['loot'].get(i['id'],0) for i in self.game.loot)):
            event_results.finish(self.game,'Знахідка на локації','stash',before_events,before_items)
        self.refresh()
        map_request=getattr(self.game,'_metro_map_request',None)
        if map_request:
            self.game._metro_map_request=None
            restoration_ui.puzzle(self,map_request)
        request=getattr(self.game,'_radio_request',None)
        if request:
            self.game._radio_request=None
            import ui.radio as radio_ui
            radio_ui.show(self,request)
        generator=getattr(self.game,'_generator_request',None)
        if generator:
            self.game._generator_request=None
            import ui.generator as generator_ui
            generator_ui.show(self,generator)
        junk=getattr(self.game,'_junkyard_request',None)
        if getattr(self.game,'_grave_request',False):
            self.game._grave_request=False
            import ui.recovery as recovery_ui
            recovery_ui.show(self)
        if junk:
            self.game._junkyard_request=None
            import ui.junkyard as junkyard_ui
            junkyard_ui.show(self,junk)
        lock=getattr(self.game,'_lock_request',None)
        if lock:
            self.game._lock_request=None
            import ui.lock as lock_ui
            lock_ui.show(self,lock)
        if before_battle and not self.game.battle and self.game.loot:
            self.tabs.select(self.loot_tab)

    def refresh(self):
        """Оновлює віджети відповідно до поточного стану гри."""
        if self.route.game is not self.game:self.route.clear()
        self.route.update_button()
        self.fx.ingest()
        g = self.game
        g.process_settlers()
        g.check_thanks()
        if not self.dialog and not g.battle and not getattr(self,'_notice_open',False):
            notice_key=next((key for key in ('_border_notice','_mayor_notice','_reputation_notice','_settler_notice') if getattr(g,key,None)),None)
            if notice_key:
                notice=getattr(g,notice_key);setattr(g,notice_key,None);self._notice_open=True
                def show_notice(text=notice,key=notice_key):
                    try:event_ui.show_notice(self,text,key)
                    finally:self._notice_open=False;self.refresh()
                self.root.after_idle(show_notice)
        weapon = g.weapon
        ws = module_rules.weapon_stats(g,weapon) if weapon else {}
        self.status.refresh(g)
        combat = g.battle is not None
        self.end_button.config(state='normal' if combat else 'disabled')
        dungeon=combat and g.battle.get('dungeon')
        self.flee_button.config(text=tr('update032.leave') if dungeon else tr('afterdays.0140'),state='normal' if combat and (not dungeon or g.battle['pos']==g.battle['exit']) else 'disabled')
        self.tabs.tab(self.loot_tab, text=tr('afterdays.0152', v0=len(g.loot)))
        self.services.refresh()
        self.perks_panel.refresh()
        self.location.config(text=g.city_name(g.city) if g.city is not None else TERRAINS[g.world[g.y][g.x]][1],fg=g.city_color(g.city,TEXT))
        self.city_info.config(text=(tr('afterdays.0153', v0=g.current_site['npc']) if g.current_site else tr('afterdays.0154') if g.city is not None else
                                  tr('afterdays.0155')) +
                                  tr('afterdays.0157', v0=g.x, v1=g.y, v2=g.region_level, v3=weapon['name'] if weapon else tr('afterdays.0156'), v4=ws.get('damage', 0), v5=ws.get('range', 0), v6=weapon['ap'] if weapon else '—'))
        if g.city is not None:
            self.city_info.config(text=self.city_info.cget('text')+'\n'+tr('reputation.status', value=g.reputation(), buy=round((buy_factor(g.reputation())-1)*100), sell=round((sell_factor(g.reputation())-1)*100)))
        if weapon:
            ammo_type=weapon.get('ammo_type','pistol')
            self.city_info.config(text=self.city_info.cget('text')+tr('afterdays.0158', v0=catalog.AMMO[ammo_type][0], v1=g.count('ammo', ammo_type), v2=weapon.get('durability', 100)))
        self.city_info.config(text=self.city_info.cget('text')+'\n'+tr('survival040.sheet',rad=g.radiation_injury,hunger=g.hunger))
        near = sorted(((n,pos) for n,pos in enumerate(g.cities) if n in g.known_cities), key=lambda entry: world_hex.distance(entry[1], (g.x, g.y)))[:3]
        self.cities_label.config(text='\n'.join(f'◆ {self.game.city_name(n)} ({p[0]}, {p[1]})' for n,p in near))
        self.player_panel.refresh()
        self.inv_panel.refresh()
        self.quest_panel.refresh()
        self.tabs.tab(self.quest_tab, text=tr('afterdays.0160'))
        self.loot_list.set_items(g.loot)
        self.logbox.config(state='normal')
        self.logbox.delete('1.0', 'end')
        colors=([None]*len(g.messages)+getattr(g,'message_colors',[]))[-len(g.messages):] if g.messages else []
        for message,color in zip(g.messages,colors):
            tag=color or 'normal'
            self.logbox.tag_configure(tag,foreground=color or TEXT)
            self.logbox.insert('end',message+'\n',tag)
        self.logbox.see('end')
        self.logbox.config(state='disabled')
        self.draw()
        self.root.after_idle(self.offer_notices)

    def offer_notices(self):
        """Показує нові повідомлення про доступні події й завдання."""
        if self.dialog or getattr(self,'_notice_open',False):
            return
        reports=getattr(self.game,'_event_results',[])
        if reports:
            event_ui.show_result(self,reports.pop(0))
            return
        if self.game.road_event:
            self.road_dialog()
            return
        if self.fx.blocked:return
        from campaign_intro import pending
        story=pending(self.game)
        if story:
            self.route.pause()
            from ui.story import show
            show(self.quest_panel,story)
            return
        if self.game.pending_perks and self.perk_prompted != self.game.level//2:
            self.perk_prompted = self.game.level//2
            self.perks()

    def road_dialog(self):
        """Відкриває варіанти дії для поточної дорожньої події."""
        if not self.dialog and self.game.road_event:
            event_ui.loading(self,lambda win:adventure_ui.road_window(self,win))

    def storage(self):
        """Відкриває інтерфейс власного сховища."""
        if self.game.can_access_stash:
            win=self.popup(tr('afterdays.0161'),'940x680')
            adventure_ui.Storage(win,self).pack(fill='both',expand=True)

    def perks(self):
        """Відкриває вибір та перегляд перків."""
        if not self.dialog:
            self.tabs.select(self.perks_tab)

    def technician(self):
        """Відкриває вкладки послуг техніка."""
        if not self.game.battle and self.game.city in self.game.technicians:
            win=self.popup(tr('afterdays.0162'),'790x690')
            refinement_ui.Technician(win,self).pack(fill='both',expand=True)

    def description(self,item):
        """Формує читабельний опис предмета або стану."""
        return refinement_ui.description(self.game,item)

    def selected_id(self):
        """Повертає ідентифікатор поточного вибору."""
        return self.inv_panel.selection

    def describe_selection(self):
        """Оновлює інформацію про поточний вибір."""
        self.inv_panel.select(self.selected_id())

    def equip_selected(self):
        """Одягає вибраний предмет у вказаний слот."""
        if self.game.battle:
            self.act(lambda: self.game.log(tr('afterdays.0163')))
            return
        item_id = self.selected_id()
        item = self.game.find(item_id)
        if not item:
            return
        slot = next((s for s, i in self.game.equipped.items() if i and i['id'] == item_id), None)
        if slot:
            self.act(lambda: self.game.unequip(slot))
        elif item['kind'] == 'weapon':
            answer = messagebox.askyesnocancel(tr('afterdays.0164'), tr('afterdays.0165'), parent=self.root)
            if answer is not None:
                self.act(lambda: self.game.equip(item_id, 'weapon1' if answer else 'weapon2'))
        elif item['kind'] in ('armor', 'helmet'):
            self.act(lambda: self.game.equip(item_id, item['kind']))

    def use_selected(self):
        """Застосовує дію використання до вибраного предмета."""
        item = self.game.find(self.selected_id())
        if item and item['kind']=='repairkit':
            import ui.maintenance as maintenance_ui
            maintenance_ui.show(self,item['id']);return
        if item and item['kind']=='sealed':
            if self.fx.blocked:return
            found=self.game.open_chest(item['id'])
            if found:
                self.refresh()
                import ui.inspection as inspection_ui
                inspection_ui.result(self,found,animate=True)
            else:self.game.log(tr('afterdays.0166'));self.refresh()
            return
        if item and item['kind'] in ('med', 'food', 'rad'):
            self.act(lambda: self.game.use(item['id']))

    def drop_selected(self):
        """Викидає вибраний предмет після потрібних перевірок."""
        item = self.game.find(self.selected_id())
        if item and item['kind'] == 'quest':
            self.act(lambda: self.game.log(tr('afterdays.0167')))
        elif self.game.battle:
            self.act(lambda: self.game.log(tr('afterdays.0168')))
        elif item and item in self.game.bag and messagebox.askyesno(tr('afterdays.0169'), tr('afterdays.0170', v0=item['name']), parent=self.root):
            self.game.drop_item(item['id'])
            self.refresh()

    def dismantle_selected(self):
        """Запускає розбір вибраного спорядження."""
        item=self.game.find(self.selected_id())
        if self.game.battle or not item or item['kind'] not in ('weapon','armor','helmet'):
            return
        if item not in self.game.bag:
            self.act(lambda:self.game.log(tr('afterdays.0171')))
            return
        count=self.game.salvage_yield(item)
        if messagebox.askyesno(tr('afterdays.0172'),tr('afterdays.0175', v0=item['name'], v1=count, v2=tr('afterdays.0173') if item['kind'] == 'weapon' else tr('afterdays.0174'))+'\n'+tr('update033.salvage_kit'),parent=self.root):
            self.act(lambda:self.game.dismantle(item['id']))

    def popup(self, title, geometry):
        """Створює й центрує додаткове вікно інтерфейсу."""
        self.route.pause()
        self.root.after_idle(lambda:sprites.decorate(self.root))
        win = tk.Toplevel(self.root)
        win.title(title)
        width,height=map(int,geometry.split('x'))
        sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
        width,height=min(width,sw-40),min(height,sh-80)
        win.geometry(f'{width}x{height}+{max(0,(sw-width)//2)}+{max(0,(sh-height)//2)}')
        win.configure(bg=PANEL)
        win.transient(self.root)
        win.grab_set()
        self.dialog = win
        def close():
            self.dialog = None
            win.destroy()
            self.refresh()
        win.close_dialog = close
        win.protocol('WM_DELETE_WINDOW', close)
        win.bind('<Escape>', lambda e: close())
        return win

    def modify(self):
        """Відкриває встановлення та зняття модулів."""
        item = self.game.find(self.selected_id())
        if not item or 'slots' not in item:
            return
        if self.game.battle:
            self.act(lambda: self.game.log(tr('afterdays.0176')))
            return
        win = self.popup(tr('afterdays.0177') + item['name'], '770x730')
        panel = visuals.ModificationPanel(win, self, item['id'])
        panel.pack(fill='both', expand=True)

    def mayor(self):
        """Відкриває список пропозицій місцевого квестодавця."""
        recipient=any(q['status']=='active' and self.game.can_turn_in(q) for q in self.game.quests)
        if (self.game.city not in self.game.mayors and not self.game.regular_city and not recipient) or self.game.battle:return
        win=self.popup(tr('afterdays.0178')+self.game.city_name(self.game.city),'750x670')
        refinement_ui.QuestCards(win,self,mayor=True).pack(fill='both',expand=True)

    def atlas(self):
        """Відкриває оглядову карту світу."""
        import ui.frontier as frontier_ui
        win = self.popup(tr('afterdays.0179'), '1000x730')
        tk.Label(win, text=tr('afterdays.0180'), bg=PANEL, fg=GOLD,
                 font=('Segoe UI', 12, 'bold')).pack(pady=10)
        c = tk.Canvas(win, bg=BG, highlightthickness=0)
        c.pack(fill='both', expand=True, padx=12)
        detail = tk.Label(win, text=tr('afterdays.0181'),
                          bg=PANEL, fg=TEXT, wraplength=950, height=3)
        detail.pack(fill='x', padx=12, pady=8)
        layout = {}
        def paint(event=None):
            from world_map import draw
            layout['view']=draw(self,c,overview=True)
        def click(event):
            if 'view' not in layout:return
            pos=list(layout['view'].cell(event.x,event.y))
            if not (0<=pos[0]<len(self.game.world[0]) and 0<=pos[1]<len(self.game.world)):return
            if pos in self.game.cities and self.map_city_known(self.game.cities.index(pos)):
                n=self.game.cities.index(pos)
                detail.config(text=f'{self.game.city_name(n)} ({pos[0]}, {pos[1]}) · '+', '.join(MERCHANTS[m] for m in self.game.city_merchants[n])+(tr('afterdays.0182') if n in self.game.mayors else tr('afterdays.0183'))+(tr('afterdays.0184') if n in self.game.technicians else '')+tr('afterdays.0185', v0=self.game.region_at(pos[0], pos[1]))+tr('update024.reputation',value=self.game.reputation(n)),fg=self.game.city_color(n,TEXT))
            else:
                q=next((q for q in self.game.quests if q.get('pos') == pos and q['status'] == 'active'), None)
                detail.config(text=self.game.quest_text(q).replace('\n', ' · ') if q else tr('afterdays.0186', v0=pos[0], v1=pos[1], v2=self.game.region_at(pos[0], pos[1])))
        c.bind('<Configure>',paint)
        c.bind('<Button-1>',click)

        def toggle_atlas_visibility(event):
            self.toggle_test_map()
            paint()
            return 'break'

        if TEST_MODE:
            win.bind('<KeyPress-m>',toggle_atlas_visibility)
            win.bind('<KeyPress-M>',toggle_atlas_visibility)

    def shop(self, merchant):
        """Відкриває інтерфейс вибраного торговця."""
        if not self.game.available_merchant(merchant):
            return
        win=self.popup(self.game.merchant_title(merchant), '960x730')
        advanced_ui.TradingPanel(win,self,merchant).pack(fill='both',expand=True)

    def collect_selected(self):
        """Забирає вибраний предмет здобичі."""
        sel=self.loot_list.selection
        if sel:self.act(lambda:self.game.collect(sel))

    def collect_all(self):
        """Намагається забрати всі доступні предмети здобичі."""
        for item in list(self.game.loot):
            self.game.collect(item['id'])
        self.refresh()

    def draw(self):
        """Перемальовує карту або арену й видимі позначення."""
        c, g = self.canvas, self.game
        if self.fx.snapshot is not None and self.fx.blocked:
            adventure_ui.paint_snapshot(self)
            self.fx.render()
            return
        if g.battle:
            advanced_ui.draw_battle(self)
            self.fx.render()
            return
        from world_map import draw
        draw(self)
        self.fx.render()

    def cell(self, event):
        """Перетворює координати курсора на клітинку карти."""
        if self.game.battle:
            return advanced_ui.iso_cell(self,event)
        return self.world_view.cell(event.x,event.y)

    def clear_battle_hover(self,event=None):
        """Прибирає ціль наведення після виходу курсора з арени."""
        self.battle_hover=None
        if self.game.battle:self.draw()

    def map_hover(self, event):
        """Оновлює підсвічування й підказку клітинки під курсором."""
        if self.game.battle:
            pos = self.cell(event)
            if getattr(self,'battle_hover',None)!=pos:
                self.battle_hover=pos;self.draw()
            e = next((e for e in self.game.battle['enemies'] if tuple(e['pos']) == pos), None)
            if e:
                valid, reason, chance = self.game.shot_info(e)
                self.hint.config(text=tr('afterdays.0191', v0=e['name'], v1=e.get('level', 1), v2=e['hp'], v3=e['max_hp'], v4=e['damage'], v5=e.get('attack', 0), v6=e.get('defense', 0), v7=e['range']) +
                                 (tr('afterdays.0192', v0=chance, v1=self.game.weapon['ap']) if valid else reason+' ') + adventure.resistance_text(e)+tr('afterdays.0193', v0=self.game.enemy_xp(e)))

        else:
            pos=self.cell(event)
            if 0<=pos[0]<len(self.game.world[0]) and 0<=pos[1]<32:
                edges=[(pos,q) for q in world_hex.neighbors(*pos,len(self.game.world[0]),len(self.game.world)) if self.game.border_edge(pos,q)]
                if edges and self.map_revealed(*pos):
                    gate=any(self.game.checkpoint(a,b) for a,b in edges)
                    self.hint.config(text=tr('border.open_hint') if gate and self.game.border_open else tr('border.locked') if gate else tr('border.fence'))

    def world_step(self, dx, dy):
        """Передає команду переміщення гравця на карті."""
        g = self.game
        if not g.can_step(dx,dy):
            g.step(dx,dy)
            return False
        if g.loot:
            if not messagebox.askyesno(tr('afterdays.0194'), tr('afterdays.0195'), parent=self.root):
                return False
            g.loot.clear()
        return g.step(dx, dy)

    def map_click(self, event, *, start=False):
        """Обробляє натискання на клітинку карти або бойову ціль."""
        if self.dialog:
            return
        self.canvas.focus_set()
        x, y = self.cell(event)
        b = self.game.battle
        if b:
            if not (0 <= x < b['w'] and 0 <= y < b['h']):
                return
            enemy = next((e for e in b['enemies'] if e['pos'] == [x, y]), None)
            self.act(lambda: self.game.shoot(enemy['id']) if enemy else self.game.battle_move((x, y)))
        elif 0 <= x < len(self.game.world[0]) and 0 <= y < len(self.game.world):
            self.route.set_target((x,y),start=start)

    def key(self, event):
        """Обробляє гарячі клавіші гри."""
        if self.dialog:
            return
        key = event.keysym.lower()
        if not self.game.battle:
            from world_hex import key_delta
            delta=key_delta(key,self.game.y)
            if delta is not None:
                self.route.clear();self.act(lambda:self.world_step(*delta));return 'break'
        directions = {'w': (0,-1), 'up': (0,-1), 's': (0,1), 'down': (0,1),
                      'a': (-1,0), 'left': (-1,0), 'd': (1,0), 'right': (1,0)}
        if key in directions:
            if isinstance(event.widget, tk.Listbox) and key in ('up', 'down'):
                return
            dx, dy = directions[key]
            if not self.game.battle:self.route.clear()
            self.act(lambda: self.game.step(dx, dy) if self.game.battle else self.world_step(dx, dy))
        elif key == 'space':
            if self.game.battle:self.act(self.game.end_turn)
            else:self.route.toggle()
        elif key == 'tab':
            self.act(self.game.switch)
        elif key == 'h':
            self.act(lambda: self.game.use('med'))
        elif key == 'e':
            self.act(self.game.search)
        elif key == 'i':
            self.tabs.select(self.inv_tab)
        elif key == 'j':
            self.tabs.select(self.quest_tab)
        elif key == 'm':
            if TEST_MODE and not (event.state & 0x0001):
                self.toggle_test_map()
            else:
                self.atlas()
        elif key == 'f5':
            self.save()
        elif key == 'f9':
            self.load()
        else:
            return
        return 'break'

    def save(self):
        """Записує стан гри у файл збереження."""
        self.route.pause()
        try:
            self.game.save(save_path)
            self.game.log(tr('afterdays.0196'))
        except OSError as exc:
            messagebox.showerror(tr('afterdays.0197'), str(exc), parent=self.root)
        self.refresh()

    def load(self):
        """Завантажує збереження та застосовує міграції цієї версії."""
        self.route.pause()
        if not save_path.exists():
            messagebox.showinfo(tr('afterdays.0198'), tr('afterdays.0199'), parent=self.root)
            return
        if not messagebox.askyesno(tr('afterdays.0200'), tr('afterdays.0201'), parent=self.root):
            return
        try:
            loaded = Game.load(save_path)
            self.game = loaded
            self.perk_prompted = -1
            self.game.log(tr('afterdays.0202'))
            self.refresh()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            messagebox.showerror(tr('afterdays.0203'), str(exc), parent=self.root)

    def new(self):
        """Починає нову гру та скидає стан інтерфейсу."""
        self.route.pause()
        if messagebox.askyesno(tr('afterdays.0204'), tr('afterdays.0205'), parent=self.root):
            self.game = Game()
            self.game.prepare_campaign()
            self.perk_prompted = -1
            self.refresh()

    def close(self):
        """Завершує роботу вікна і пов’язаних таймерів."""
        self.route.pause()
        answer = messagebox.askyesnocancel('Afterdays', tr('afterdays.0206'), parent=self.root)
        if answer is None:
            return
        if answer:
            try:
                self.game.save(save_path)
            except OSError as exc:
                messagebox.showerror(tr('afterdays.0207'), str(exc), parent=self.root)
                return
        self.root.destroy()

    def help(self):
        """Показує довідку з керування."""
        messagebox.showinfo(tr('afterdays.0208'),
            tr('afterdays.0209'), parent=self.root)


def launch(test_hook=None):
    """Create the game window and schedule an optional integration hook."""
    root = tk.Tk()
    app = App(root)
    if test_hook:
        root.after(100, lambda: test_hook(root, app))
    root.mainloop()
