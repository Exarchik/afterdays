import unittest
from dialogue_text import Playback, Presentation, blocks, speak_reply
from types import SimpleNamespace
from unittest.mock import Mock


class Scheduler:
    def __init__(self):
        self.now=0;self.jobs={};self.serial=0
    def after(self,ms,fn):
        self.serial+=1;self.jobs[self.serial]=(self.now+ms/1000,fn);return self.serial
    def after_cancel(self,key):self.jobs.pop(key,None)
    def until(self,end):
        while self.jobs:
            key=min(self.jobs,key=lambda key:self.jobs[key][0]);at,fn=self.jobs[key]
            if at>end:break
            del self.jobs[key];self.now=at;fn()
        self.now=end


class TextTests(unittest.TestCase):
    def setUp(self):
        self.timer=Scheduler();self.player=Playback(self.timer,lambda:self.timer.now)
        self.text=[];self.finished=[];self.hints=[]
    def play(self,text,default=50):
        self.player.start(text,self.text.append,lambda:self.finished.append(True),default,self.hints.append)
    def test_default_speed(self):
        self.play('а'*100);self.timer.until(1.01);self.assertEqual(len(self.text[-1]),50)
        self.timer.until(2.01);self.assertEqual(len(self.text[-1]),100);self.assertTrue(self.finished)
    def test_speed_multipliers(self):
        for multiplier in (.5,1,2):
            self.setUp();self.play(f'[time={multiplier}]'+'а'*100)
            self.timer.until(.51);self.assertAlmostEqual(len(self.text[-1]),25*multiplier,delta=1)
            self.timer.until(100/(50*multiplier)+.01);self.assertTrue(self.finished)
    def test_markers(self):
        self.play('[time=0.5]АБ[space][clear]В[pause=1.5][line]Г')
        self.timer.until(10);self.assertEqual(self.text[-1],'АБ');self.assertTrue(self.player.waiting)
        self.player.space();self.assertEqual(self.text[-1],'')
        self.timer.until(11.51);self.assertEqual(self.text[-1],'В');self.assertFalse(self.finished)
        self.timer.until(11.55);self.assertEqual(self.text[-1],'В\nГ');self.assertTrue(self.finished)
    def test_cancel_restart(self):
        self.play('старе');self.timer.until(.03);self.player.cancel();before=list(self.text)
        self.timer.until(10);self.assertEqual(self.text,before);self.assertFalse(self.finished)
        self.play('нове');self.timer.until(10.09);self.assertEqual(self.text[-1],'нове')
    def test_duration_scope_and_invalid_tags(self):
        self.assertEqual(list(blocks('[time=0.5]а[line]б')), [('text','а',25),('line',),('text','б',50)])
        self.assertEqual(list(blocks('[time=-1][unknown]')), [('text','[time=-1][unknown]',50)])
        self.assertEqual(list(blocks('[time=0]')), [('text','[time=0]',50)])
    def test_space_only_resumes_wait(self):
        self.play('А[space]Б');self.player.space();self.timer.until(3)
        self.assertTrue(self.player.waiting);self.assertEqual(self.text[-1],'А')

    def test_selected_reply_respects_multiplier_then_waits(self):
        label=Mock()
        speak_reply(SimpleNamespace(player=self.player),'[time=0.5]'+'а'*50,label,self.hints.append,lambda:self.finished.append(True))
        self.timer.until(1.01);self.assertEqual(len(label.configure.call_args.kwargs['text']),25)
        self.timer.until(2.01);self.assertTrue(self.player.waiting);self.assertFalse(self.finished)
        self.player.space();self.assertTrue(self.finished)

    def test_phrase_and_response_options_share_default_speed(self):
        presentation=Presentation(Mock());presentation.player=self.player
        phrase=Mock();reply=Mock();button=Mock()
        presentation.show('а'*50,phrase,[(reply,'б'*50)],[button],lambda value:None)
        self.timer.until(.51);self.assertAlmostEqual(len(phrase.configure.call_args.kwargs['text']),25,delta=1)
        self.timer.until(1.51);self.assertAlmostEqual(len(reply.configure.call_args.kwargs['text']),25,delta=1)
        self.assertEqual(button.configure.call_args.kwargs['state'],'disabled')
        self.timer.until(2.01);self.assertEqual(button.configure.call_args.kwargs['state'],'normal')


if __name__=='__main__':unittest.main()
