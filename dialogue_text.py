"""Shared, cancellable dialogue text playback for Tk views."""
import math
import re
import time

TAG = re.compile(r'\[(space|line|clear|(?:time|pause)=\d+(?:\.\d+)?)\]')


def blocks(text, default=50.0):
    """A time marker multiplies the base speed for the next text run only."""
    speed = default
    pos = 0
    for match in TAG.finditer(text):
        if match.start() > pos:
            yield ('text', text[pos:match.start()], speed)
            speed = default
        tag = match[1]
        if tag.startswith('time='):
            multiplier = float(tag[5:])
            if multiplier > 0 and math.isfinite(default * multiplier):
                speed = default * multiplier
            else:
                yield ('text', match[0], default)
        elif tag.startswith('pause='):
            yield ('pause', float(tag[6:]))
        else:
            yield (tag,)
        pos = match.end()
    if pos < len(text):
        yield ('text', text[pos:], speed)


class Playback:
    def __init__(self, owner, clock=time.monotonic):
        self.owner = owner
        self.clock = clock
        self.job = None
        self.waiting = False
        self.active = False
        self.hint = lambda value: None

    def cancel(self):
        if self.job is not None:
            self.owner.after_cancel(self.job)
            self.job = None
        self.active = self.waiting = False

    def start(self, text, update, done=lambda: None, default=50.0, hint=lambda value: None):
        self.cancel()
        self.update, self.done, self.hint = update, done, hint
        self.tokens = iter(blocks(text, default))
        self.output = ''
        self.active = True
        update('');hint(False)
        self.advance()

    def later(self, seconds, callback):
        def run():
            self.job = None
            callback()
        self.job = self.owner.after(max(1, min(2147483647, round(seconds * 1000))), run)

    def advance(self):
        while self.active:
            token = next(self.tokens, None)
            if token is None:
                self.active = False
                self.done()
                return
            kind = token[0]
            if kind == 'text':
                self.run_text, speed = token[1:]
                self.duration = len(self.run_text) / speed
                self.started = self.clock()
                self.prefix = self.output
                self.tick()
                return
            if kind == 'pause':
                self.later(token[1], self.advance)
                return
            if kind == 'space':
                self.waiting = True
                self.hint(True)
                return
            self.output = '' if kind == 'clear' else self.output + '\n'
            self.update(self.output)

    def tick(self):
        elapsed = self.clock() - self.started
        count = len(self.run_text) if self.duration == 0 else min(len(self.run_text), int(elapsed / self.duration * len(self.run_text)))
        self.output = self.prefix + self.run_text[:count]
        self.update(self.output)
        if count == len(self.run_text):
            self.advance()
        else:
            self.later(min(.016, max(.001, self.duration - elapsed)), self.tick)

    def space(self, event=None):
        if self.waiting:
            self.waiting = False
            self.hint(False)
            self.advance()
        return 'break'


class Presentation:
    """Play a phrase, then each reply; enable choices only after all finish."""
    def __init__(self, owner):
        self.player = Playback(owner)
        self.owner=owner
        self.input_tag='DialogueContinue:'+str(owner)
        self.held=set()
        for sequence in ('<KeyPress>','<ButtonPress>'):
            owner.bind_class(self.input_tag,sequence,self.press)
        for sequence in ('<KeyRelease>','<ButtonRelease>'):
            owner.bind_class(self.input_tag,sequence,self.release)
        owner.bind('<Destroy>',self.destroy,add='+')

    def destroy(self,event):
        if event.widget is not self.owner:return
        self.cancel()
        for sequence in ('<KeyPress>','<ButtonPress>','<KeyRelease>','<ButtonRelease>'):
            self.owner.unbind_class(self.input_tag,sequence)

    def bind_inputs(self,*roots):
        # Run before widget/class handlers so a continuation click cannot choose a reply.
        def attach(widget):
            tags=widget.bindtags()
            if self.input_tag not in tags:widget.bindtags((self.input_tag,)+tags)
            for child in widget.winfo_children():attach(child)
        for root in roots:attach(root)

    def input_key(self,event):
        return ('key',event.keycode) if str(event.type) in ('2','3') else ('mouse',event.num)

    def press(self,event):
        key=self.input_key(event)
        if key in self.held:return 'break'
        if self.player.waiting:
            self.held.add(key)
            self.player.space()
            return 'break'

    def release(self,event):
        key=self.input_key(event)
        if key in self.held:
            self.held.discard(key)
            return 'break'


    def cancel(self):
        self.player.cancel()

    def show(self, phrase, label, replies, controls, hint, changed=lambda: None):
        self.cancel()
        for widget in controls:
            widget.configure(state='disabled')
        for widget, text in replies:
            widget.configure(text='')
        pending = iter(replies)
        def update(widget, text):
            widget.configure(text=text)
            changed()
        def next_reply():
            item = next(pending, None)
            if item is None:
                for widget in controls:
                    widget.configure(state='normal')
                return
            widget, text = item
            self.player.start(text, lambda text: update(widget, text), next_reply, hint=hint)
        self.player.start(phrase, lambda text: update(label, text), next_reply, hint=hint)


def hero(session):
    return dict(name=session.player_name, art=session.player_art or session.doc['actors']['player']['art'])


def speak_reply(presentation, text, label, hint, done, changed=lambda: None):
    def update(value):
        label.configure(text=value)
        changed()
    presentation.player.start(text + '[space]', update, done, hint=hint)
