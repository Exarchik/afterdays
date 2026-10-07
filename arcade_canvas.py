"""Arcade/OpenGL map surface hosted in the existing Windows UI.

Only the widget container is Tk. Images, shapes and text are drawn directly
into a native OpenGL child window; there is no framebuffer readback to Tk.
The editor never imports this module. Legacy canvas commands are retained in
Python and compiled to GPU batches, allowing UI migration without rule changes.
"""
from collections import OrderedDict
from pathlib import Path
import ctypes
from ctypes import wintypes
import sys
import time
import tkinter as tk
from tkinter import font as tkfont

from arcade_scene import Scene, geometry


class ArcadeUnavailable(RuntimeError):
    pass


def load_arcade():
    if sys.platform != 'win32':
        raise ArcadeUnavailable('Вбудований Arcade-рендерер поки підтримує Windows. Використайте --renderer=tk.')
    try:
        import arcade
        import pyglet
    except ImportError as exc:
        raise ArcadeUnavailable('Встановіть залежності: python -m pip install -r requirements-game.txt') from exc
    return arcade, pyglet


class ArcadeCanvas(tk.Canvas):
    renderer_name = 'Arcade / OpenGL'

    def __init__(self, master, **options):
        self.arcade, self.pyglet = load_arcade()
        super().__init__(master, **options)
        self.scene = Scene()
        self.window = None
        self._closed = False
        self._job = None
        self._textures = {}
        self._sheets = OrderedDict()
        self._batches = OrderedDict()
        self._text_cache = OrderedDict()
        self._fonts = {}
        self._colors = {}
        self._drawn_revision = -1
        self._force_draw = True
        self._clip_signature = None
        self.metrics = dict(frames=0, frame_ms=0., batches=0, textures=0, renderer='')
        # Use a separate bindtag: application bind('<Configure>') must not replace it.
        tag = 'ArcadeHost'+str(self)
        self.bindtags((tag,)+self.bindtags())
        self.bind_class(tag, '<Configure>', self._resize)
        self.bind_class(tag, '<Map>', self._map)
        self.bind_class(tag, '<Unmap>', self._unmap)
        self.bind_class(tag, '<Destroy>', self._destroy_event)
        self._host_tag = tag
        self.after_idle(self._start)

    def _start(self):
        if self._closed or self.window:
            return
        arcade, host = self.arcade, self

        class Surface(arcade.Window):
            def on_mouse_press(self, x, y, button, modifiers):
                host._mouse('ButtonPress', x, y, button)

            def on_mouse_release(self, x, y, button, modifiers):
                host._mouse('ButtonRelease', x, y, button)

            def on_mouse_motion(self, x, y, dx, dy):
                host._mouse('Motion', x, y)

            def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
                host._mouse('Motion', x, y, state=256 if buttons & 1 else 0)

            def on_mouse_leave(self, x, y):
                host._mouse('Leave', x, y)

            def on_mouse_scroll(self, x, y, sx, sy):
                host.event_generate('<MouseWheel>', x=int(x), y=int(host.winfo_height()-y), delta=int(sy*120))

            def on_key_press(self, symbol, modifiers):
                host._key(symbol, modifiers, 'KeyPress')

            def on_key_release(self, symbol, modifiers):
                host._key(symbol, modifiers, 'KeyRelease')

            def on_draw(self):
                # Tk drives scheduling. Pyglet's paint message just invalidates.
                host._force_draw = True

            def on_expose(self):
                host._force_draw = True

            def on_close(self):
                # Closing the application remains the host's save/confirm action.
                pass

        try:
            self.window = Surface(max(1,self.winfo_width()), max(1,self.winfo_height()),
                                  'Afterdays GPU', style=arcade.Window.WINDOW_STYLE_BORDERLESS,
                                  visible=False, vsync=False, antialiasing=False)
            # Tk owns the only event loop. Arcade's default timer would draw and
            # swap a second time, even while our retained scene is unchanged.
            self.pyglet.clock.unschedule(self.window._dispatch_frame)
            self.pyglet.clock.unschedule(self.window._dispatch_updates)
            self.window.switch_to()
            self._embed()
            self.metrics['renderer'] = str(self.window.ctx.info.VENDOR)+' / '+str(self.window.ctx.info.RENDERER)
            self._resize()
            self._tick()
        except Exception as exc:
            if self.window:
                self.window.close()
                self.window = None
            self._root()._renderer_error = exc
            self._root().destroy()

    def _embed(self):
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.SetParent.argtypes = [wintypes.HWND,wintypes.HWND]
        user.SetParent.restype = wintypes.HWND
        user.GetWindowLongPtrW.argtypes = [wintypes.HWND,ctypes.c_int]
        user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.SetWindowLongPtrW.argtypes = [wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t]
        user.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.SetWindowPos.argtypes = [wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        user.ShowWindow.argtypes = [wintypes.HWND,ctypes.c_int]
        user.RedrawWindow.argtypes = [wintypes.HWND,ctypes.c_void_p,ctypes.c_void_p,wintypes.UINT]
        user.SetWindowRgn.argtypes = [wintypes.HWND,wintypes.HANDLE,wintypes.BOOL]
        gdi = ctypes.WinDLL('gdi32',use_last_error=True)
        gdi.CreateRectRgn.argtypes = [ctypes.c_int]*4
        gdi.CreateRectRgn.restype = wintypes.HANDLE
        gdi.CombineRgn.argtypes = [wintypes.HANDLE,wintypes.HANDLE,wintypes.HANDLE,ctypes.c_int]
        gdi.DeleteObject.argtypes = [wintypes.HANDLE]
        self._gdi32 = gdi
        hwnd = self.window._hwnd
        style = user.GetWindowLongPtrW(hwnd,-16)
        # WS_CHILD | WS_CLIPSIBLINGS; remove WS_POPUP and all window chrome.
        style = (style & ~0x80CF0000) | 0x44000000
        user.SetWindowLongPtrW(hwnd,-16,style)
        self.window._ws_style = style
        ctypes.set_last_error(0)
        user.SetParent(hwnd,self.winfo_id())
        if ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        self._user32 = user
        for widget in (self,self.master):
            hwnd_host=widget.winfo_id()
            user.SetWindowLongPtrW(hwnd_host,-16,user.GetWindowLongPtrW(hwnd_host,-16)|0x06000000)
        user.SetWindowPos(hwnd,None,0,0,max(1,self.winfo_width()),max(1,self.winfo_height()),0x0034)
        user.ShowWindow(hwnd,5)

    def _resize(self, event=None):
        if not self.window or self._closed:
            return
        width,height = max(1,self.winfo_width()),max(1,self.winfo_height())
        self.window.switch_to()
        self.window.set_size(width,height)
        self._user32.SetWindowPos(self.window._hwnd,None,0,0,width,height,0x0014)
        self._batches.clear()
        self._text_cache.clear()
        self._force_draw = True
        self.after_idle(self._repaint_host)

    def _sync_clip(self):
        """Exclude Tk sibling overlays from the native GL window's region.

        Tk's logical stacking alone cannot clip a foreign OpenGL child when
        SwapBuffers presents a new frame. Windows owns this region after set.
        """
        x,y=self.winfo_rootx(),self.winfo_rooty()
        width,height=self.winfo_width(),self.winfo_height()
        holes=[]
        for sibling in self.master.winfo_children():
            if sibling is self or not sibling.winfo_ismapped():
                continue
            left,top=sibling.winfo_rootx()-x,sibling.winfo_rooty()-y
            right,bottom=left+sibling.winfo_width(),top+sibling.winfo_height()
            if left<width and top<height and right>0 and bottom>0:
                holes.append((max(0,left),max(0,top),min(width,right),min(height,bottom)))
        signature=(width,height,tuple(holes))
        if signature==self._clip_signature:
            return
        self._clip_signature=signature
        gdi=self._gdi32
        region=gdi.CreateRectRgn(0,0,width,height)
        for rect in holes:
            hole=gdi.CreateRectRgn(*rect)
            gdi.CombineRgn(region,region,hole,4)  # RGN_DIFF
            gdi.DeleteObject(hole)
        if not self._user32.SetWindowRgn(self.window._hwnd,region,True):
            gdi.DeleteObject(region)
            raise ctypes.WinError(ctypes.get_last_error())
        self._force_draw=True

    def _repaint_host(self):
        if not self._closed:
            # Reparented GL children do not share Tk's backing-store damage.
            # Invalidate the host after layout so old child bounds are erased.
            self._user32.RedrawWindow(self._root().winfo_id(),None,None,0x0085)
            # Tk frames may retain pixels from a child that moved during a
            # resize beside a foreign GL window. Explicitly dirty their fill.
            def repaint(widget):
                if widget.winfo_class() in ('Tk','Frame','Labelframe'):
                    widget.configure(background=widget.cget('background'))
                for child in widget.winfo_children():
                    repaint(child)
            repaint(self._root())

    def _map(self, event=None):
        if self.window:
            self._user32.ShowWindow(self.window._hwnd,5)
            self._force_draw = True

    def _unmap(self, event=None):
        if self.window:
            self._user32.ShowWindow(self.window._hwnd,0)

    def _mouse(self, kind, x, y, button=None, state=0):
        if self._closed:
            return
        root = self._root()
        grab = root.grab_current()
        if grab and grab is not self:
            return
        options = dict(x=round(x),y=round(self.winfo_height()-y),state=state)
        if button is not None:
            options['button'] = {1:1,2:2,4:3}.get(button,button)
        if kind == 'ButtonPress':
            self.focus_set()
        self.event_generate('<'+kind+'>', **options)

    def _key(self, symbol, modifiers, kind):
        key = self.pyglet.window.key
        name = key.symbol_string(symbol)
        names = {'ESCAPE':'Escape','SPACE':'space','ENTER':'Return','RETURN':'Return',
                 'BACKSPACE':'BackSpace','TAB':'Tab','LEFT':'Left','RIGHT':'Right',
                 'UP':'Up','DOWN':'Down','DELETE':'Delete','HOME':'Home','END':'End',
                 'PAGEUP':'Prior','PAGEDOWN':'Next'}
        name = names.get(name,name if name.startswith('F') and name[1:].isdigit() else name.lower().lstrip('_'))
        state = (1 if modifiers & key.MOD_SHIFT else 0) | (4 if modifiers & key.MOD_CTRL else 0) | (8 if modifiers & key.MOD_ALT else 0)
        target = self._root().grab_current() or self
        try:
            target.event_generate('<'+kind+'>',keysym=name,state=state)
        except tk.TclError:
            pass  # Pyglet also reports media keys with no Tk keysym.

    def _tick(self):
        if self._closed or not self.window:
            return
        self._sync_clip()
        # Tk already pumps Win32 messages. Only drain this window's queued
        # pyglet callbacks, never consume messages belonging to Tk widgets.
        self.window.dispatch_pending_events()
        if self._closed or not self.window:
            return
        if self.winfo_ismapped() and (self._force_draw or self.scene.revision != self._drawn_revision):
            self.render_now()
        self._job = self.after(16,self._tick)

    def render_now(self):
        if not self.window:
            return
        started = time.perf_counter()
        self.window.switch_to()
        self.window.clear(self.color(self.cget('background')))
        groups = []
        for command in self.scene.items.values():
            if command.options.get('state') == 'hidden':
                continue
            kind = command.kind if command.kind in ('image','text') else 'shape'
            if groups and groups[-1][0] == kind and kind != 'text':
                groups[-1][1].append(command)
            else:
                groups.append((kind,[command]))
        height = self.winfo_height()
        for kind, commands in groups:
            if kind == 'text':
                self._label(commands[0]).draw()
                continue
            signature = (height,kind,tuple(c.key() for c in commands))
            batch = self._batches.get(signature)
            if batch is None:
                if kind == 'image':
                    batch = self.arcade.SpriteList()
                    for c in commands:
                        texture = self._textures[c.options['texture_key']]
                        x,y = c.points
                        w,h = c.options['size']
                        anchor = c.options.get('anchor','center')
                        cx = x+w/2 if 'w' in anchor else x-w/2 if 'e' in anchor and anchor != 'center' else x
                        cy = y+h/2 if 'n' in anchor and anchor != 'center' else y-h/2 if 's' in anchor else y
                        sprite = self.arcade.Sprite(texture,center_x=cx,center_y=height-cy)
                        sprite.width,sprite.height = w,h
                        batch.append(sprite)
                else:
                    from arcade.shape_list import ShapeElementList, create_triangles_filled_with_colors
                    vertices,colors = [],[]
                    for c in commands:
                        for points,color in geometry(c):
                            rgba = self.color(color)
                            if c.options.get('stipple'):
                                alpha = {'gray12':32,'gray25':64,'gray50':128,'gray75':192}.get(c.options['stipple'],128)
                                rgba = rgba[:3]+(alpha,)
                            vertices.extend((x,height-y) for x,y in points)
                            colors.extend([rgba]*len(points))
                    batch = ShapeElementList()
                    if vertices:
                        batch.append(create_triangles_filled_with_colors(vertices,colors))
                self._batches[signature] = batch
            self._batches.move_to_end(signature)
            batch.draw()
        while len(self._batches) > 128:
            self._batches.popitem(last=False)
        self.window.flip()
        self._drawn_revision = self.scene.revision
        self._force_draw = False
        self.metrics.update(frames=self.metrics['frames']+1,frame_ms=(time.perf_counter()-started)*1000,
                            batches=len(groups),textures=len(self._textures))

    def color(self, value):
        if isinstance(value,(tuple,list)):
            return tuple(value)+(255,) if len(value)==3 else tuple(value)
        if value not in self._colors:
            self._colors[value] = tuple(v//257 for v in self.winfo_rgb(value))+(255,)
        return self._colors[value]

    def _label(self, c):
        signature = (self.winfo_height(),c.key())
        if signature not in self._text_cache:
            o = c.options
            font = o.get('font',('Segoe UI',10))
            if isinstance(font,str):
                actual = tkfont.nametofont(font).actual()
                font = (actual['family'],actual['size'],actual['weight'])
            anchor = o.get('anchor','center')
            ax = 'left' if 'w' in anchor else 'right' if 'e' in anchor and anchor != 'center' else 'center'
            ay = 'top' if 'n' in anchor and anchor != 'center' else 'bottom' if 's' in anchor else 'center'
            width = int(o.get('width',0)) or None
            text = str(o.get('text',''))
            multiline = bool(width or '\n' in text)
            if multiline and not width:
                width = max(1,self._font(font).measure(max(text.split('\n'),key=len,default=''))+2)
            self._text_cache[signature] = self.arcade.Text(text,c.points[0],self.winfo_height()-c.points[1],
                color=self.color(o.get('fill','black')),font_size=abs(float(font[1])),font_name=font[0],
                bold='bold' in font[2:],anchor_x=ax,anchor_y=ay,width=width,multiline=multiline,
                align=o.get('justify','left'))
        self._text_cache.move_to_end(signature)
        while len(self._text_cache)>512:
            self._text_cache.popitem(last=False)
        return self._text_cache[signature]

    def _font(self, font):
        key = tuple(font) if isinstance(font,(tuple,list)) else font
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(root=self,font=font)
        return self._fonts[key]

    def texture(self, path, index, columns, tile_size):
        """Decode a source cell once. Resizing never creates another texture."""
        path = Path(path)
        key = (str(path),int(index),int(columns),int(tile_size))
        if key not in self._textures:
            from PIL import Image
            if path not in self._sheets:
                with Image.open(path) as source:
                    self._sheets[path] = source.convert('RGBA')
            self._sheets.move_to_end(path)
            sheet = self._sheets[path]
            x,y = index%columns*tile_size,index//columns*tile_size
            if x+tile_size>sheet.width or y+tile_size>sheet.height:
                raise ValueError('Invalid atlas cell: '+str(key))
            self._textures[key] = self.arcade.Texture(sheet.crop((x,y,x+tile_size,y+tile_size)),hash=str(key))
            while len(self._sheets)>4:
                self._sheets.popitem(last=False)[1].close()
        return key

    def draw_terrain(self, game, gx, gy, x, y, size):
        import terrain_tiles
        key = terrain_tiles.tile_key(game,gx,gy)
        texture = self.texture(terrain_tiles.ROOT/'terrain_v2.png',terrain_tiles.INDEX[key],32,64)
        self.scene.add('image',(x,y),dict(texture_key=texture,size=(size,size),anchor='nw'))
        return True

    def draw_sprite(self, key, x, y, size):
        import sprites
        if key and key.startswith('npc:'):
            key = sprites.npc_key(key[4:])
        entry = sprites.MANIFEST.get(key)
        if entry is None:
            return False
        resolution = max(s for s in sprites.SIZES if s<=max(16,min(192,int(size))))
        path = sprites.ROOT/f"{entry.get('sheet','atlas')}_{resolution}.png"
        try:
            texture = self.texture(path,entry['index'],entry.get('columns',16),resolution)
        except (OSError,ValueError):
            return False
        self.scene.add('image',(x,y),dict(texture_key=texture,size=(resolution,resolution),anchor='nw'))
        # Legacy sprites use native-size artwork centered in the requested box.
        self.scene.coords(self.scene.serial,x+(size-resolution)/2,y+(size-resolution)/2)
        return True

    def create_rectangle(self,*points,**options):
        return self.scene.add('rectangle',points,options)

    def create_polygon(self,*points,**options):
        return self.scene.add('polygon',points,options)

    def create_line(self,*points,**options):
        return self.scene.add('line',points,options)

    def create_oval(self,*points,**options):
        return self.scene.add('oval',points,options)

    def create_text(self,*points,**options):
        return self.scene.add('text',points,options)

    def delete(self,*selectors):
        self.scene.delete(*selectors)

    def coords(self,selector,*points):
        return self.scene.coords(selector,*points)

    def move(self,selector,dx,dy):
        self.scene.move(selector,dx,dy)

    def itemconfigure(self,selector,cnf=None,**options):
        self.scene.configure(selector,**(cnf or {}),**options)

    itemconfig = itemconfigure

    def find_withtag(self,selector):
        return self.scene.ids(selector)

    def find_all(self):
        return self.scene.ids('all')

    def tag_lower(self,selector,below=None):
        self.scene.reorder(selector,below,above=False)

    def tag_raise(self,selector,above=None):
        self.scene.reorder(selector,above,above=True)

    def bbox(self,*selectors):
        boxes = []
        for selector in selectors:
            for i in self.scene.ids(selector):
                c = self.scene.items[i]
                if c.kind == 'text':
                    # Tk font metrics work before the GL context is initialized.
                    o = c.options
                    font = self._font(o.get('font',('Segoe UI',10)))
                    text = str(o.get('text',''))
                    lines = text.split('\n')
                    natural = max((font.measure(line) for line in lines),default=0)
                    width = min(natural,int(o.get('width',0)) or natural)
                    count = sum(max(1,(font.measure(line)+max(1,width)-1)//max(1,width)) for line in lines)
                    height = count*font.metrics('linespace')
                    x,y = c.points
                    anchor = o.get('anchor','center')
                    left = x if 'w' in anchor else x-width if 'e' in anchor and anchor!='center' else x-width/2
                    top = y if 'n' in anchor and anchor!='center' else y-height if 's' in anchor else y-height/2
                    boxes.append((left,top,left+width,top+height))
                else:
                    p = c.points
                    if p:
                        boxes.append((min(p[::2]),min(p[1::2]),max(p[::2]),max(p[1::2])))
        if not boxes:
            return None
        return tuple(round(fn(b[n] for b in boxes)) for n,fn in enumerate((min,min,max,max)))

    def _destroy_event(self,event):
        if event.widget is self:
            self._shutdown()

    def _shutdown(self):
        if self._closed:
            return
        self._closed = True
        if self._job:
            self.after_cancel(self._job)
        if self.window:
            self.window.switch_to()
            self._batches.clear()
            self._text_cache.clear()
            self._textures.clear()
            self.window.close()
            self.window = None
        for sheet in self._sheets.values():
            sheet.close()
        self._sheets.clear()

    def destroy(self):
        self._shutdown()
        super().destroy()


def canvas_class(renderer):
    if renderer == 'tk':
        return tk.Canvas
    if renderer != 'arcade':
        raise ValueError('Unknown renderer: '+renderer)
    load_arcade()
    return ArcadeCanvas
