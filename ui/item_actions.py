"""Context-aware item menus shared by inventories, shops, storage and equipment."""
from game import catalog
from game import items
import module_rules as mr
import tkinter as tk
import ui.dialogs as messagebox
import game.items as p
from i18n import t as tr

def locate(widget):
    owner=widget
    while owner is not None:
        if hasattr(owner,'app'):return owner.app,owner
        owner=getattr(owner,'master',None)
    app=getattr(widget._root(),'_afterdays_app',None)
    return app,None

def personal_actions(g,item):
    """Pure availability query; operations still validate the state on execution."""
    if not item:return []
    ident=item['id'];kind=item['kind'];actions=[]
    bag=any(i['id']==ident for i in g.bag)
    slot=next((s for s,i in g.equipped.items() if i and i['id']==ident),None)
    if not bag and slot is None:return actions
    quest=item.get('quest_id') or kind=='quest'
    if kind in ('med','food','rad') and bag and g.can_use_consumable(ident):actions.append(('use',()))
    if g.battle:
        if slot in ('weapon1','weapon2') and slot!=g.active:actions.append(('switch',()))
        return actions
    if slot:actions.append(('unequip',(slot,)))
    if bag and kind in ('weapon','armor','helmet') and item.get('level',1)<=g.level:
        for target in ('weapon1','weapon2') if kind=='weapon' else (kind,):actions.append(('equip',(target,)))
    if kind=='sealed' and bag:actions.append(('open',()))
    if kind=='repairkit' and bag:actions.append(('use_kit',()))
    if kind in ('weapon','armor','helmet') and not quest:
        actions.append(('modify',()))
        if item.get('modules'):actions.append(('remove_modules',()))
    if (kind in ('weapon','armor','helmet') or item.get('quest_repair')) and mr.condition(item)<mr.max_condition(item):
        if g.can_repair_with_kit(item):actions.append(('repair_kit',()))
        if g.city in g.technicians:
            for target in (25,50,100):
                cost=g.repair_cost(item,target)
                if cost and cost<=g.money:actions.append(('repair',(target,cost)))
    if bag and not quest:
        if kind in ('weapon','armor','helmet'):actions.append(('dismantle',()))
        actions.append(('drop',()))
    return actions

def show(app,item,event,owner=None,grid=None):
    if app is None or item is None:return
    g=app.game;ident=item['id'];app.route.pause()
    menu=tk.Menu(event.widget,tearoff=False,bg='#24372c',fg='#e0eadc',activebackground='#48614d')
    import ui.inspection as inspection_ui
    menu.add_command(label=tr('update030.inspect'),command=lambda:inspection_ui.inspect_item(app,item))
    def refresh_owner():
        if owner is not None and hasattr(owner,'refresh') and owner.winfo_exists():
            if hasattr(owner,'item_id') and not g.find(owner.item_id):
                win=owner.winfo_toplevel();win.destroy();app.dialog=None
            else:owner.refresh()
    def run(fn):
        app.act(fn);refresh_owner()
    def choose():app.inv_panel.select(ident)
    def selected(fn):
        choose();fn();refresh_owner()
    merchant=getattr(owner,'merchant',None)
    stock=merchant is not None and (grid is getattr(owner,'stock_grid',None) or grid is None and getattr(owner,'source',None)=='stock')
    if stock:
        price=g.price(item,merchant,True)
        if g.available_merchant(merchant):
            for qty in sorted({1,item.get('qty',1)}):
                unit=dict(item,qty=qty)
                if price*qty<=g.money and g.weight+items.item_weight(unit)<=g.capacity+.0001:
                    menu.add_command(label=tr('update030.buy',qty=qty,price=price*qty),command=lambda qty=qty:run(lambda:g.buy(ident,merchant,qty)))
    elif any(i['id']==ident for i in g.loot):
        if not g.battle or g.battle.get('cleared'):
            menu.add_command(label=tr('update030.collect'),command=lambda:run(lambda:g.collect(ident)))
    elif any(i['id']==ident for i in g.stash):
        if g.can_access_stash and not item.get('quest_id'):
            for qty in sorted({1,item.get('qty',1)}):menu.add_command(label=tr('update030.withdraw',qty=qty),command=lambda qty=qty:run(lambda:g.stash_transfer(ident,'withdraw',qty)))
    else:
        for code,args in personal_actions(g,item):
            label=tr('update030.'+code)
            if code=='equip':label=tr('update030.equip_slot',slot=catalog.SLOTS[args[0]])
            if code=='repair':label=tr('update030.repair_to',target=min(args[0],mr.max_condition(item)),price=args[1])
            if code=='equip':fn=lambda slot=args[0]:run(lambda:g.equip(ident,slot))
            elif code=='unequip':fn=lambda slot=args[0]:run(lambda:g.unequip(slot))
            elif code=='switch':fn=lambda:run(g.switch)
            elif code in ('use','open','use_kit'):fn=lambda:selected(app.use_selected)
            elif code=='remove_modules':fn=lambda:run(lambda:g.remove_modules(ident))
            elif code=='modify':fn=lambda:selected(app.modify)
            elif code=='repair_kit':fn=lambda:run(lambda:g.repair_with_kit(ident))
            elif code=='repair':fn=lambda target=args[0]:run(lambda:g.repair(ident,target))
            elif code=='dismantle':fn=lambda:selected(app.dismantle_selected)
            else:fn=lambda:selected(app.drop_selected)
            menu.add_command(label=label,command=fn)
        carried=any(i['id']==ident for i in g.bag)
        if not g.battle:
            if carried and merchant is not None and g.available_merchant(merchant) and g.buys_kind(item,merchant):
                def sell(qty):
                    if item.get('modules') and not messagebox.askyesno(tr('advanced_ui.0026'),tr('advanced_ui.0027'),parent=owner):return
                    run(lambda:g.sell(ident,merchant,qty))
                for qty in sorted({1,item.get('qty',1)}):menu.add_command(label=tr('update030.sell',qty=qty,price=g.price(item,merchant,False)*qty),command=lambda qty=qty:sell(qty))
            if carried and hasattr(owner,'stored') and not item.get('quest_id') and item['kind']!='quest':
                for qty in sorted({1,item.get('qty',1)}):menu.add_command(label=tr('update030.deposit',qty=qty),command=lambda qty=qty:run(lambda:g.stash_transfer(ident,'deposit',qty)))
            gear=[i for i in g.bag+list(g.equipped.values()) if i and i.get('modules') is not None and not i.get('quest_id')]
            host=next((i for i in gear if any(m['id']==ident for m in i['modules'])),None)
            if host:menu.add_command(label=tr('update030.detach'),command=lambda:run(lambda:g.uninstall(host['id'],ident)))
            if carried and item['kind']=='module' and item.get('level',1)<=g.level:
                targets=[i for i in gear if i.get('slots',0)>0 and mr.compatible(i,item)]
                if targets:
                    sub=tk.Menu(menu,tearoff=False)
                    for target in targets:sub.add_command(label=target['name']+f" · L{target.get('level',1)}",command=lambda tid=target['id']:run(lambda:g.quick_module(tid,ident)))
                    menu.add_cascade(label=tr('update030.attach'),menu=sub)
    try:menu.tk_popup(event.x_root,event.y_root)
    finally:
        menu.grab_release()
        if app.dialog and app.dialog.winfo_exists():app.dialog.grab_set()
    return 'break'
