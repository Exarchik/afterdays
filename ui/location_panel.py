"""Current location only: illustration on the left, compact facts on the right."""
import tkinter as tk
from game.catalog import TERRAINS
from visuals import PANEL,TEXT,MUTED
import sprites
import location_art

CITY_ART_SIZE=144

def location_details(game):
    city=game.city;site=game.current_site
    kind=game.world[game.y][game.x]
    import location_rules
    variant=location_rules.terrain_type(game,game.x,game.y)
    title=game.city_name(city) if city is not None else location_rules.TYPES.get(variant,TERRAINS[kind][1])
    lines=[f'[{game.x}; {game.y}] · Рівень {game.region_level}']
    if site:lines.append(site['npc'])
    elif city is not None:lines.append('Поселення')
    if city is not None:lines.append(f'Репутація: {game.reputation():g}')
    return title,'\n'.join(lines)


class LocationPanel(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL)
        self.app=app;self.photo=None;self.art_key=None
        self.picture=tk.Label(self,bg=PANEL,width=CITY_ART_SIZE,height=CITY_ART_SIZE)
        self.picture.grid(row=0,column=0,rowspan=2,sticky='nw',padx=(0,10))
        self.title=tk.Label(self,bg=PANEL,fg=TEXT,font=('Segoe UI',11,'bold'),anchor='w',justify='left',wraplength=230)
        self.title.grid(row=0,column=1,sticky='ew')
        self.info=tk.Label(self,bg=PANEL,fg=MUTED,font=('Segoe UI',10),anchor='nw',justify='left',wraplength=230)
        self.info.grid(row=1,column=1,sticky='new',pady=(3,0))
        self.columnconfigure(1,weight=1)
        self.bind('<Configure>',self.resize)

    def resize(self,event):
        width=max(90,event.width-158)
        self.title.config(wraplength=width);self.info.config(wraplength=width)

    def refresh(self):
        game=self.app.game;title,details=location_details(game)
        self.title.config(text=title,fg=game.city_color(game.city,TEXT))
        self.info.config(text=details)
        art=location_art.location_art(game,game.x,game.y)
        key=(id(game),game.x,game.y,game.world[game.y][game.x],art)
        if key!=self.art_key:
            self.art_key=key
            self.photo=sprites.photo(self,art,CITY_ART_SIZE) if art else None
            if self.photo is None:
                import world_hex_art
                self.photo=world_hex_art.photo(self,game,game.x,game.y,72)
            self.picture.config(image=self.photo,width=CITY_ART_SIZE,height=CITY_ART_SIZE)
