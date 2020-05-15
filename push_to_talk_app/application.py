#!/usr/bin/python

# Copyright (c) 2015 Paranox
#
# Based on the work done by Adam Coddington
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import os.path
import logging
import shlex
import subprocess

from multiprocessing import Process, Queue
from gi.repository import GObject, Gtk, Gdk, Gio, GLib
from interfaces import SkypeInterface, PulseAudioInterface
from key_monitor import KeyMonitor
from optparse import OptionParser

class PushToTalk(Gtk.Window):
    INTERVAL = 100
    INTERFACES = [
            PulseAudioInterface,
            SkypeInterface,
            ]

    def __init__(self):
        self.logger = logging.getLogger('push_to_talk_app')

        saved_interface = self.get_saved_interface()
        #self.selected_audio_interface = saved_interface if saved_interface else self.INTERFACES[0]
        if saved_interface:
            self.logger.debug("Loaded saved interface")
            self.selected_audio_interface = saved_interface
        else:
            self.logger.debug("Setting default interface")
            self.selected_audio_interface = self.INTERFACES[0]

        self.audio_interface = self.selected_audio_interface()
        self.audio_interface.mute()
        
        self.ffmpegVideoMuted = False #'/home/gpunktschmitz/Videos/thisisfine.mp4'
        self.ffmpegVideoUnmuted = False #'/home/gpunktschmitz/Videos/nyancat.mp4'
        self.ffmpegCommand = False #'ffmpeg -re -i %s -map 0:v -f v4l2 /dev/video0'
        self.ffmpegProcess = False
        self.ffmpegState = KeyMonitor.MUTED
        self.state = KeyMonitor.MUTED
        
        if self.ffmpegCommand:
            self.playvideo()
        
        self.setup_menu()

        self.start()

    def setup_menu(self):
        Gtk.Window.__init__(self, title="Push-To-Talk")

        self.set_default_size(200, 200)

        action_group = Gtk.ActionGroup("my_actions")

        self.add_file_menu_actions(action_group)
        self.add_edit_menu_actions(action_group)
        self.add_interface_menu_actions(action_group)

        uimanager = self.create_ui_manager()
        uimanager.insert_action_group(action_group)

        menubar = uimanager.get_widget("/MenuBar")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(menubar, False, False, 0)

        toolbar = uimanager.get_widget("/ToolBar")
        box.pack_start(toolbar, False, False, 0)

        eventbox = Gtk.EventBox()
        eventbox.connect("button-press-event", self.on_button_press_event)
        box.pack_start(eventbox, True, True, 0)

        self.LABEL = Gtk.Label("Placeholder text")
        self.LABEL.set_text("Right-click to see popup menu.")
        eventbox.add(self.LABEL)

        self.popup = uimanager.get_widget("/PopupMenu")

        self.add(box)

    def add_file_menu_actions(self, action_group):
        action_filemenu = Gtk.Action("FileMenu", "File", None, None)
        action_group.add_action(action_filemenu)

        action_filequit = Gtk.Action("FileQuit", "Quit", None, Gtk.STOCK_QUIT)
        action_filequit.connect("activate", self.on_menu_file_quit)
        action_group.add_action(action_filequit)

    def add_edit_menu_actions(self, action_group):
        action_editmenu = Gtk.Action("EditMenu", "Edit", None, None)
        action_group.add_action(action_editmenu)

        action_talk = Gtk.Action("Talk", "Talk", None, Gtk.STOCK_MEDIA_RECORD)
        action_talk.connect("activate", self.on_tool_talk)
        action_group.add_action(action_talk)

        action_mute = Gtk.Action("Mute", "Mute", None, Gtk.STOCK_MEDIA_PAUSE)
        action_mute.connect("activate", self.on_tool_mute)
        action_group.add_action(action_mute)

        action_setkey = Gtk.Action("SetKey", "Set Key", None, Gtk.STOCK_PREFERENCES)
        action_setkey.connect("activate", self.on_tool_set_key)
        action_group.add_action(action_setkey)

    def add_interface_menu_actions(self, action_group):
        action_interfacemenu = Gtk.Action("InterfaceMenu", "Interfaces", None, None)
        action_group.add_action(action_interfacemenu)

        #verbs = []
        for interface in self.INTERFACES:
            #self.logger.debug("Evaluating '%s'" % interface.verb)
            #if self.selected_audio_interface.verb != interface.verb:
            self.logger.debug("Setting interface action '%s'" % interface.verb)
            action_selectinterface = Gtk.Action(interface.verb, interface.verb, None, None)
            action_selectinterface.connect("activate", self.on_menu_interface_changed)
            action_group.add_action(action_selectinterface)
        #        verbs.append((
        #                        interface.verb, 
        #                        interface.verb, 
        #                        None, 
        #                        Gtk.STOCK_MEDIA_PLAY, 
        #                        self.on_menu_interface_changed, 
        #                ),)
        #
        #action_group.add_actions(verbs)

    def create_ui_manager(self):
        uimanager = Gtk.UIManager()

        # Throws exception if something went wrong
        uimanager.add_ui_from_string(self.menu_xml)

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)
        return uimanager
    
    def playvideo(self):
        if self.ffmpegCommand:
            if self.state == KeyMonitor.MUTED:
                ffmpegCommand = self.ffmpegCommand % self.ffmpegVideoMuted
            else:
                ffmpegCommand = self.ffmpegCommand % self.ffmpegVideoUnmuted
            if not self.ffmpegProcess:
                ffmpegArgs = shlex.split(ffmpegCommand)
                self.ffmpegProcess = subprocess.Popen(ffmpegArgs, shell=False)
            else:
                if self.ffmpegState != self.state:
                    self.ffmpegState = self.state
                    if self.ffmpegProcess.pid:
                        subprocess.call(["kill", "-9", "%d" % self.ffmpegProcess.pid])
                    ffmpegArgs = shlex.split(ffmpegCommand)
                    self.ffmpegProcess = subprocess.Popen(ffmpegArgs, shell=False)
                if self.ffmpegProcess.poll() != None:
                    ffmpegArgs = shlex.split(ffmpegCommand)
                    self.ffmpegProcess = subprocess.Popen(ffmpegArgs, shell=False)
        return True

    def start(self):
        self.pipe = Queue()
        self.return_pipe = Queue()

        self.p = Process(
                target=self.process,
                args=(self.pipe, self.return_pipe, )
            )
        self.p.start()

        self.logger.debug("Process spawned")
        GObject.timeout_add(PushToTalk.INTERVAL, self.read_incoming_pipe)
        GObject.timeout_add(PushToTalk.INTERVAL, self.playvideo)

    def stop(self):
        self.logger.debug("Killing process...")
        if self.ffmpegProcess:
            subprocess.call(["kill", "-9", "%d" % self.ffmpegProcess.pid])
        self.p.terminate()
        self.p.join()
        if (self.audio_interface):
            self.audio_interface.unmute()
        Gtk.main_quit()

    def process(self, pipe, return_pipe):
        monitor = KeyMonitor(
                self.audio_interface, 
                pipe,
                return_pipe,
                test=False
            )
        monitor.start()

    def reset_process(self):
        self.logger.debug("Restarting process...")
        self.p.terminate()
        self.start()

    def read_incoming_pipe(self):
        while not self.pipe.empty():
            data_object = self.pipe.get_nowait()
            data_type = data_object[0]
            data = data_object[1]
            self.logger.debug("Incoming Data -- %s" % str(data_object))
            if data_type == "MUTED":
                if data == KeyMonitor.UNMUTED:
                    self.set_talk()
                elif data == KeyMonitor.MUTED:
                    self.set_mute()
        return True

    def get_saved_interface(self):
        try:
            name = self.get_saved_interface_name()
            for interface in self.INTERFACES:
                if interface.__name__ == name:
                    return interface
        except:
            pass
        return None

    def get_saved_interface_name(self):
        with open(self.preferences_file, "r") as infile:
            interface = infile.read()
        return interface

    def set_saved_interface_name(self, name):
        with open(self.preferences_file, "w") as outfile:
            outfile.write(name)
        return name

    @property
    def preferences_file(self):
        return os.path.expanduser(
                    "~/.push_to_talk_saved",
                )

    @property
    def menu_xml(self):
        audio_xml = self.get_audio_xml()
        start_xml = """
            <ui>
                <menubar name='MenuBar'>
                    <menu action='FileMenu'>
                        <menuitem action='FileQuit' />
                    </menu>
                    <menu action='EditMenu'>
                        <menuitem action='Talk' />
                        <menuitem action='Mute' />
                        <menuitem action='SetKey' />
                    </menu>
                    <menu action='InterfaceMenu'>
                        """
        #for audio_source_verb, audio_item in audio_xml.items():
        #    if self.selected_audio_interface.verb == audio_source_verb:
        #        del(audio_xml[audio_source_verb])
        end_xml = """
                    </menu>
                </menubar>
                <toolbar name='ToolBar'>
                    <toolitem action='Talk' />
                    <toolitem action='Mute' />
                    <toolitem action='SetKey' />
                    <toolitem action='FileQuit' />
                </toolbar>
                <popup name='PopupMenu'>
                    <menuitem action='Talk' />
                    <menuitem action='Mute' />
                    <menuitem action='SetKey' />
                    <menuitem action='FileQuit' />
                </popup>
            </ui>
            """
        final_xml = start_xml + "".join(audio_xml.values()) + end_xml
        #final_xml = start_xml + end_xml
        self.logger.debug(final_xml)
        return final_xml

    def get_audio_xml(self):
        xml_strings = {}
        for interface in self.INTERFACES:
            xml_strings[interface.verb] = "<menuitem action=\'%s\' />" % (
                                interface.verb,
                            )
        return xml_strings

    def set_talk(self):
        self.logger.debug("Unmuted")
        self.LABEL.set_text("Microphone activated")
        self.state = KeyMonitor.UNMUTED

    def set_mute(self):
        self.logger.debug("Muted")
        self.LABEL.set_text("Microphone muted")
        self.state = KeyMonitor.MUTED

    def set_key(self):
        self.logger.debug("Attempting to set key...")
        self.LABEL.set_text("Press a key to bind")
        self.return_pipe.put(("SET", 1, ))

    def on_menu_file_quit(self, widget):
        self.stop()

    def on_menu_interface_changed(self, action):
        verb = action.get_name()
        self.logger.debug("Setting to verb '%s'" % verb)
        for interface in self.INTERFACES:
            if interface.verb == verb:
                self.logger.debug("Interface is set!")
                self.set_saved_interface_name(interface.__name__)
                self.selected_audio_interface = interface
        self.audio_interface = self.selected_audio_interface()
        self.setup_menu()
        self.reset_process()

    def on_menu_choices_toggled(self, widget):
        if widget.get_active():
            print(widget.get_name() + " activated")
        else:
            print(widget.get_name() + " deactivated")

    def on_tool_talk(self, *arguments):
        self.audio_interface.unmute()
        self.set_talk()

    def on_tool_mute(self, *arguments):
        self.audio_interface.mute()
        self.set_mute()

    def on_tool_set_key(self, *arguments):
        self.set_key()

    def on_app_delete_event(self, widget, event):
        self.stop()
        return True

    def on_button_press_event(self, widget, event):
        # Check if right mouse button was preseed
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            self.popup.popup(None, None, None, None, event.button, event.time)
            return True # event has been handled

def run_from_cmdline():
    parser = OptionParser()
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False)
    (opts, args, ) = parser.parse_args()

    logging.basicConfig(
            level=logging.DEBUG if opts.verbose else logging.WARNING
        )

    window = PushToTalk()
    window.connect("delete-event", window.on_app_delete_event)
    window.show_all()
    Gtk.main()
