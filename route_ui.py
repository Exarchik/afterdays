"""UI-only continuous travel; segment duration follows geometric distance."""
import time
import math
from journey import world_route
from i18n import t as tr

class RouteController:
    seconds_per_cell=2/3

    def __init__(self,app):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        self.app=app;self.game=app.game;self.path=[];self.running=False
        self.guided_city=None;self.started=None;self.origin=(self.game.x,self.game.y)
        app.root.after(33,self.tick)

    def update_button(self):
        """Узгоджує стан кнопки руху з поточним маршрутом."""
        button=getattr(self.app,'route_button',None)
        if button:button.config(text=tr('journey.pause') if self.running else tr('journey.resume'),state='normal' if self.path and not self.app.game.battle else 'disabled')

    def clear(self):
        """Очищує поточний маршрут або стан взаємодії."""
        self.path=[];self.running=False;self.started=None;self.guided_city=None;self.game=self.app.game
        self.origin=(self.game.x,self.game.y);self.update_button()

    def pause(self):
        """Призупиняє автоматичний рух на останній завершеній клітинці."""
        self.running=False;self.started=None;self.update_button()
        # Snap to the last completed cell. Unfinished distance costs no turn.
        self.position_player()

    def blocked(self):
        """Перевіряє, чи дозволяє поточний стан продовжувати рух."""
        a=self.app;g=a.game
        return bool(a.dialog or getattr(a,'_notice_open',False) or g.battle or g.road_event or a.fx.blocked)

    def set_target(self,target):
        """Будує маршрут до вибраної клітинки й починає рух."""
        if self.blocked():return False
        self.clear();self.path=world_route(self.game,target)
        if not self.path:
            if tuple(target)!=self.origin:self.game.log(tr('journey.no_route'))
            self.app.refresh();return False
        self.running=True;self.started=time.monotonic();self.update_button();self.app.draw();return True

    def toggle(self):
        """Перемикає паузу та продовження руху."""
        if self.running:self.pause()
        elif self.path and not self.blocked():
            if self.game is not self.app.game or self.origin!=(self.app.game.x,self.app.game.y):self.clear();return
            self.running=True;self.started=time.monotonic();self.update_button()

    def start_guide(self,city):
        """Оплачує маршрут провідника і запускає анімацію подорожі."""
        g=self.app.game
        if not g.guide or g.road_event or g.battle:return False
        choice=next((v for v in g.guide_destinations() if v['city']==city),None)
        if not choice or g.money<choice['price']:
            g.log(tr('journey.no_money'));return False
        self.clear();g.money-=choice['price'];g.traveler=None
        self.guided_city=city;self.path=[tuple(p) for p in choice['route']]
        self.running=True;self.started=time.monotonic();self.update_button()
        return True

    def segment_duration(self):
        """Обчислює час проходження відрізка маршруту."""
        return self.seconds_per_cell/(2 if getattr(self,'guided_city',None) is not None else 1)

    def position(self):
        """Повертає проміжну позицію для плавної анімації."""
        pos=(self.app.game.x,self.app.game.y)
        if not self.running or not self.path or self.started is None:return pos
        fraction=min(1,max(0,(time.monotonic()-self.started)/self.segment_duration()))
        return tuple(pos[i]+(self.path[0][i]-pos[i])*fraction for i in (0,1))

    def position_player(self):
        """Оновлює екранну позицію маркера гравця."""
        a=self.app
        if not hasattr(a,'tile') or a.game.battle:return
        x,y=self.position();t=a.tile
        px,py=a.world_view.point((x,y))
        a.canvas.coords('coward_icon',px,py-t*.55)
        a.canvas.coords('world_player_ring',px-t*.31,py-t*.31,px+t*.31,py+t*.31)
        a.canvas.coords('world_player_arrow',px,py-t*.22,px+t*.16,py+t*.17,px,py+t*.09,px-t*.16,py+t*.17)

    def paint(self):
        """Малює актуальне представлення даних на Canvas."""
        a=self.app;c=a.canvas;t=a.tile
        def point(p):return a.world_view.point(p)
        positions=[(a.game.x,a.game.y)]+self.path
        for p,q in zip(positions,positions[1:]):
            if all(a.world_view.visible(v) for v in (p,q)):
                c.create_line(*point(p),*point(q),fill='#e6cc8a',width=2,dash=(4,4),tags='route')
        if self.path:
            end=self.path[-1]
            if a.world_view.visible(end):
                c.create_polygon(*a.world_view.polygon(end,.85),fill='',outline='#e6cc8a',width=2,dash=(4,3),tags='route')

    def advance(self):
        """Просуває поточну анімацію або маршрут на наступний етап."""
        if self.game is not self.app.game or self.origin!=(self.app.game.x,self.app.game.y):self.clear();return
        if not self.running:return
        if self.blocked():self.pause();return
        if time.monotonic()-self.started<self.segment_duration():self.position_player();return
        g=self.game;next_pos=self.path[0]
        guided=getattr(self,'guided_city',None) is not None
        g._guided_trip=guided
        try:ok=self.app.world_step(next_pos[0]-g.x,next_pos[1]-g.y)
        finally:g._guided_trip=False
        if not ok or (g.x,g.y)!=next_pos:self.clear()
        else:
            self.path.pop(0);self.origin=(g.x,g.y);self.started=time.monotonic()
            if not self.path:
                if guided:g.log(tr('update024.guide_arrived',city=g.city_name(self.guided_city)))
                self.guided_city=None;self.pause()
            elif g.battle or g.road_event or (not guided and (g.traveler or g.city is not None or g.local_graves() or getattr(g,'local_settlers',lambda:[])())):self.pause()
        self.app.refresh()

    def tick(self):
        """Виконує черговий кадр оновлення та планує наступний."""
        self.advance();self.app.root.after(33,self.tick)
