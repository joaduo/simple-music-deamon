from flask import request
import os
from os import path
import json
import androidhelper as android
import threading
from functools import wraps
import settings
import logging

PLAY_STAT = 'play'
PAUSE_STAT = 'pause'
STOP_STAT = 'stop'

droid = android.Android()
def do_player(status, url=None):
    logging.info('Setting %r %s', url, status)
    info = get_player_info()
    if status == PLAY_STAT and (not info.get('isplaying')
                                or info.get('url') != url):
        if info['loaded'] and info['url'] == url:
            droid.mediaPlayStart()
        else:
            droid.mediaPlay(url)
        secs = droid.mediaPlayInfo().result.get('duration',0) / 1000.
        logging.info('Playing: %r %ss', url, secs)
    elif status == PAUSE_STAT and info.get('isplaying'):
        droid.mediaPlayPause()
    elif status == STOP_STAT and info['loaded']:
        droid.mediaPlayClose()
    return droid.mediaPlayInfo().result

def get_player_info():
    info = droid.mediaPlayInfo().result
    if info['loaded'] and info['position'] == info['duration']:
        droid.mediaPlayClose()
        info = droid.mediaPlayInfo().result
    return info

def get_play_status():
    info = get_player_info()
    if info.get('isplaying'):
        return PLAY_STAT
    elif info['loaded']:
        return PAUSE_STAT
    else:
        return STOP_STAT
    
def get_volume():
    return droid.getMediaVolume()

def set_volume(volume):
    return droid.setMediaVolume(volume)

def mark_update(method):
    global update_counter
    @wraps(method)
    def marks(self, *args, **kwargs):
        self.update_counter += 1
        return method(self, *args, **kwargs)
    return marks

class PlayList(object):
    def __init__(self):
        droid.mediaPlayClose()
        self.status = get_play_status()
        self.songs = []
        self.current_idx = 0
        self._previous_song = None
        self._status = None
        self._timer = None
        self.update_counter = 0

    @property
    def volume(self):
        return get_volume()[1]

    @property
    def current_song(self):
        if self.current_idx < len(self.songs):
            return self.songs[self.current_idx]
        return ''

    def get_playlist(self):
        player_info = dict(changed=False)
        if self.current_song != self._previous_song:
            player_info = self._do_player()
        if self._status != self.status:
            player_info = self._do_player()
        return dict(
                    status=self.status,
                    volume=self.volume,
                    current_song=self.current_idx,
                    songs=self.songs,
                    player_info=player_info,
                    update_counter=self.update_counter,
                    err='',)

    def _do_player(self):
        self.cancel_timer()
        self._previous_song = self.current_song
        self._status = self.status
        if self.songs:
            url = 'file://'+ get_music_dir() + self.current_song
            info = do_player(self._status, url)
            self._schedule_next_song(info)
        else:
            info = do_player(STOP_STAT, None)
        info.update(changed=True)
        return info

    def _schedule_next_song(self, info):
        if self.status == PLAY_STAT:
            # remaining miliseconds
            remaining = info['duration'] - info['position']
            if remaining:
                def callback():
                    self.next_song()
                self._timer = threading.Timer(remaining/1000., callback)
                self._timer.start()

    def cancel_timer(self):
        return self._timer and self._timer.cancel()

    @mark_update
    def prev_song(self):
        logging.info('Previous song')
        if self.status == PAUSE_STAT:
            self.status = STOP_STAT
        if self.current_idx:
            self.current_idx -= 1
        return self.get_playlist()

    @mark_update
    def next_song(self):
        logging.info('Next song')
        if self.status == PAUSE_STAT:
            self.status = STOP_STAT
        self.current_idx = (self.current_idx + 1) % len(self.songs)
        return self.get_playlist()

    @mark_update
    def set_songs(self, songs, current_idx=0):
        self.songs[:] = songs
        if not songs:
            self.current_idx = 0
            self.status = STOP_STAT
        else:
            self.current_idx = current_idx % len(songs)
        return self.get_playlist()

    @mark_update
    def append_songs(self, songs):
        self.songs += songs
        return self.get_playlist()

    @mark_update
    def set_status(self, status):
        self.status = status
        return self.get_playlist()

    @mark_update
    def set_current_song(self, current_song, play=False): 
        self.current_idx = current_song
        if play:
            self.status = PLAY_STAT
        return self.get_playlist()

    def set_volume(self, volume):
        set_volume(volume)
        return self.volume

    def get_player_info(self):
        info = get_player_info()
        info.update(update_counter=self.update_counter)
        return info

    def was_updated(self):
        if get_play_status() != self.status:
            self.update_counter += 1
            self.status = get_play_status()
        return self.update_counter

def directory_rsrc():
    songs_list = []
    songs_dir = path.join(get_music_dir(), '')
    for s in os.listdir(songs_dir):
        s = s.decode('utf8')
        songs_list.append(dict(name=s, id=s
                               #path.join(songs_dir, s)
                               ))
    return json.dumps(songs_list)

def get_music_dir():
    return settings.MUSIC_DIR

cache = None
def index_rscr():
    global cache
    dirname = path.dirname(__file__)
    if not cache or settings.RELOAD_MODE:
        with open(path.join(dirname, 'player.html')) as fp:
                cache = fp.read()
    return cache

SL = PlayList()        
def playlist_rscr(action):
    if hasattr(SL, action):
        params = json.loads(request.data)
        val = getattr(SL, action)(**params)
        return json.dumps(val)

