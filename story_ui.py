"""Story journal and playable dialogue presentation."""
import tkinter as tk
from tkinter import ttk
import game_dialogs as messagebox
import quest_catalog
import sprites


def show(panel,auto_story=None):
    if auto_story:
        from dialogue_overlay import show as show_dialogue
        return show_dialogue(panel,auto_story)
    from inspection_ui import window
    app=panel.app;win=window(app,'Головний сюжет')
    canvas=tk.Canvas(win,highlightthickness=0);scroll=ttk.Scrollbar(win,command=canvas.yview)
    scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
    body=ttk.Frame(canvas,padding=14);item=canvas.create_window(0,0,window=body,anchor='nw')
    body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
    def clear():
        for child in body.winfo_children():child.destroy()
    def journal():
        clear();g=app.game;g.story_sync();states=g.story_states()
        available={s['id']:s for s in quest_catalog.DOCUMENT.get('stories',[]) if s['enabled']}
        available.update({key:value['definition'] for key,value in states.items()})
        if not available:ttk.Label(body,text='Сюжетних ліній поки немає. Створіть їх у редакторі: Квести → Сюжетні лінії.',wraplength=550).pack(pady=15)
        for ident,spec in available.items():
            ttk.Label(body,text=spec['title'],font=('Segoe UI',15,'bold'),wraplength=550).pack(anchor='w',pady=(15,5))
            state=states.get(ident)
            if state is None:
                if spec.get('start_after_moves'):
                    ttk.Label(body,text=f"Починається автоматично після {spec['start_after_moves']} кроків у новій грі.",wraplength=550).pack(anchor='w')
                else:ttk.Button(body,text='Розпочати сюжет',command=lambda key=ident:start(key)).pack(fill='x')
                continue
            if state['status']=='done':ttk.Label(body,text='Сюжет завершено').pack(anchor='w');continue
            step=spec['stages'][state['index']]
            ttk.Label(body,text=f"Етап {state['index']+1} із {len(spec['stages'])}").pack(anchor='w')
            if step['kind']=='dialogue':ttk.Button(body,text='Розпочати / продовжити розмову',command=lambda key=ident:talk(key)).pack(fill='x',pady=8)
            elif step['kind']=='visit':ttk.Label(body,text=f"Прибудьте до міста {g.city_name(step['ref'])} ({', '.join(map(str,g.cities[step['ref']]))}).",wraplength=550).pack(anchor='w')
            else:
                q=state['quests'][step['ref']]
                ttk.Label(body,text='Виконайте та здайте квест: '+q['title']+'\nПропозиція доступна у мера за умовами цього квесту.',wraplength=550).pack(anchor='w',pady=8)
        ttk.Button(body,text='Оновити',command=journal).pack(fill='x',pady=20)
        panel.refresh()
    def start(ident):
        if not app.game.start_story(ident):messagebox.showinfo('Сюжет недоступний','Перевірте визначення сюжету; початок недоступний під час бою або дорожньої події.',parent=win)
        journal()
    def talk(ident):
        from dialogue_overlay import show as show_dialogue
        try:show_dialogue(panel,ident)
        except ValueError as exc:messagebox.showinfo('Розмова недоступна',str(exc),parent=win)
    journal()
