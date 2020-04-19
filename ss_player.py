"""

A simple player for VLC python bindings using PyQt5
Currently with support for Windows and Linux

by Gabriel Christo
02/2020

TODO:
- switch audio/subtitle track
- show metadata
- animation for audio player

"""

import platform
import os
import sys
import vlc

from PyQt5 import QtWidgets, QtGui, QtCore, uic
from PyQt5.QtWidgets import QFileDialog, QMainWindow, QApplication, QInputDialog
from PyQt5.QtCore import pyqtSlot, Qt, QTimer, QDir
from PyQt5.QtGui import QPalette, QColor, QKeyEvent

# Constants
VLC_YELLOW = 16776960
VLC_WHITE = 16777215
COLORS_LIST = [VLC_WHITE, VLC_YELLOW]
CMD_OPTIONS = '--freetype-fontsize={} --freetype-color={}'
PERCENT_LABEL = '{}%'
POSITION_LABEL = '{} / {}'
SUB_SIZE_START_VALUE = 75
VOLUME_START_VALUE = 70

class Player(QMainWindow):

    def __init__(self):
        super(__class__, self).__init__()
        uic.loadUi("./ss_player.ui", self)
        self.setWindowTitle("SS Player")
        self.path = QDir.currentPath()
        self.instance = vlc.Instance(CMD_OPTIONS.format(SUB_SIZE_START_VALUE, VLC_WHITE))
        self.mediaplayer = self.instance.media_player_new()
        self.media = None
        self.connects()

    def connects(self):
        # event to enter/quit fullscreen mode and play/pause
        self.keyPressEvent = self.manage_pressed_key
        # vlc frame background color
        self.palette = self.vlcFrame.palette()
        self.palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.vlcFrame.setPalette(self.palette)
        self.vlcFrame.setAutoFillBackground(True)
        # position slider
        self.positionSlider.valueChanged.connect(self.set_position)
        self.positionSlider.sliderReleased.connect(self.restart_timer)
        # buttons
        self.buttonPlay.clicked.connect(self.play)
        self.buttonPause.clicked.connect(self.pause)
        self.buttonStop.clicked.connect(self.stop)
        # volume slider
        self.volumeSlider.valueChanged.connect(self.set_volume)
        self.volumeSlider.setValue(VOLUME_START_VALUE)
        # load file action
        self.actionLoadMedia.triggered.connect(self.open_file)
        # load url action
        self.actionLoadURL.triggered.connect(self.open_url)
        # subtitle size spin box
        self.subtitleSizeSpinbox.setValue(SUB_SIZE_START_VALUE)
        self.subtitleSizeSpinbox.editingFinished.connect(self.update_subtitle)
        # timer to postion slider update
        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.update_position_slider)
        # subtitle color combo box
        self.subtitleColorCombobox.currentIndexChanged.connect(self.update_subtitle)

    @pyqtSlot(QKeyEvent)
    def manage_pressed_key(self, event):
        # in case of escape key
        if event.key() == Qt.Key_Escape:
            # showing full screen
            if self.windowState() == Qt.WindowNoState:
                self.menubar.hide()
                self.statusbar.hide()
                self.controlsWidget.hide()
                self.setWindowState(Qt.WindowFullScreen)
            # returning from fullscreen
            else:
                self.menubar.show()
                self.statusbar.show()
                self.controlsWidget.show()
                self.setWindowState(Qt.WindowNoState)
        # in case of P key -> play/pause switch
        elif event.key() == Qt.Key_P:
            if self.mediaplayer.is_playing(): self.pause()
            else: self.play()
        # otherwise we just accept the event
        event.accept()
        
    @pyqtSlot()
    def play(self):
        # no file selected
        if self.mediaplayer.play() == -1:
            self.open_file()
            return
        # playing media
        self.mediaplayer.play()
        self.timer.start()

    @pyqtSlot()
    def pause(self):
        # pausing media
        self.mediaplayer.set_pause(True)
        self.timer.stop()

    @pyqtSlot()
    def stop(self):
        # stopping player
        self.mediaplayer.stop()

    @pyqtSlot()
    def open_file(self):
        # opening and verifying file
        filename = QFileDialog.getOpenFileName(self, "Choose Media File", self.path)
        if not filename[0]: return
        # initializing media
        self.try_release_media()
        self.media = self.instance.media_new(filename[0])
        # updating path
        self.path = filename[0]
        # put the media in the media player
        self.mediaplayer.set_media(self.media)
        # parse the metadata of the file
        self.media.parse()
        # set the title of the track as window title
        self.setWindowTitle(self.media.get_meta(0))
        # checking o.s. to integrate mediaplayer on qframe
        self.set_player_on_qframe()
        # playing media
        self.mediaplayer.play()
        self.timer.start()
        # enable subtitle controls when playing local media
        self.set_subtitle_controls_state(True)

    @pyqtSlot(int)
    def set_volume(self, volume):
        # updating player volume
        self.mediaplayer.audio_set_volume(volume)
        # updating label
        self.volumePercentLabel.setText(PERCENT_LABEL.format(volume))

    @pyqtSlot()
    def update_subtitle(self):
        # current position
        pos = self.mediaplayer.get_position()
        # release media player
        self.mediaplayer.stop()
        self.mediaplayer.release()
        # release and new instance
        self.instance.release()
        self.instance = vlc.Instance(CMD_OPTIONS.format(self.subtitleSizeSpinbox.value(), COLORS_LIST[self.subtitleColorCombobox.currentIndex()]))
        # new media player
        self.mediaplayer = self.instance.media_player_new()
        # checking o.s. to set player on qframe
        self.set_player_on_qframe()
        # release and new media
        self.try_release_media()
        self.media = self.instance.media_new(self.path)
        self.mediaplayer.set_media(self.media)
        # update position and play
        self.play()
        self.mediaplayer.set_position(pos)
        
    @pyqtSlot(int)
    def set_position(self, pos):
        # set the media position to where the slider was dragged (converts to float between 0 and 1)
        self.timer.stop()
        self.mediaplayer.set_position(pos / 1000.0)

    @pyqtSlot()
    def restart_timer(self):
        self.timer.start()

    @pyqtSlot()
    def update_position_slider(self):
        # set the sliders position to its corresponding media position (qslider only accepts int)
        pos = int(self.mediaplayer.get_position() * 1000)
        # blocking signals and updating value
        self.positionSlider.blockSignals(True)
        self.positionSlider.setValue(pos)
        self.positionSlider.blockSignals(False)
        # updating position label
        self.update_position_label()

    def update_position_label(self):
        # media length in milliseconds
        length = self.mediaplayer.get_length()
        current = self.mediaplayer.get_time()
        # updating label
        self.positionLabel.setText(POSITION_LABEL.format(self.msToHMS(current), self.msToHMS(length)))

    @pyqtSlot()
    def open_url(self):
        # url dialog and checking
        url, ok = QInputDialog.getText(self, 'Open Stream', 'Put the media url:')
        if not ok or not url: return
        # release and new instances
        self.try_release_media()
        self.mediaplayer.release()
        self.mediaplayer = self.instance.media_player_new()
        self.mediaplayer.set_mrl(url, "network-caching=2000")
        self.set_player_on_qframe()
        self.mediaplayer.play()
        # getting media from opened url
        self.media = self.mediaplayer.get_media()
        self.media.parse()
        self.setWindowTitle(self.media.get_meta(0))
        self.timer.start()
        # disable subtitle controls when playing url media
        self.set_subtitle_controls_state(False)

    def try_release_media(self):
        if self.media is not None: self.media.release()

    def set_player_on_qframe(self):
        if platform.system() == "Linux": self.mediaplayer.set_xwindow(int(self.vlcFrame.winId()))
        elif platform.system() == "Windows": self.mediaplayer.set_hwnd(int(self.vlcFrame.winId()))

    def set_subtitle_controls_state(self, state):
        self.subtitleSizeSpinbox.setEnabled(state)
        self.subtitleColorCombobox.setEnabled(state)

    @staticmethod
    def msToHMS(value):
        seconds = int((value/1000)%60)
        minutes = int((value/(1000*60))%60)
        hours = int((value/(1000*60*60))%24)
        return ':'.join((str(hours), str(minutes), str(seconds)))
    
# main function
if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    player.show()
    sys.exit(app.exec_())
