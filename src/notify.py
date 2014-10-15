#!coding:utf-8
import os
from twisted.application import internet
from twisted.internet import inotify
from twisted.python import filepath
from chips.readers import AUDIO_TAG, VIDEO_TAG, META_DATA
from chips.fragment import FlvFragment
from chips import logging
from chips import config
from readers import pack_head, pack_tag


logger = logging.getLogger('binder.chips')


def get_channel(path):
    channel = os.path.basename(path)
    suffix = config.GROWING_FILE_SUFFIX
    if channel.endswith(suffix):
        channel = channel.rstrip(suffix)
    return channel


class Notify(object):
    
    def __init__(self, watch_dir, shared_dict):
        if not os.path.exists(watch_dir):
            logger.error('Directory not found %s' % (watch_dir,))
            raise IOError(watch_dir)
        
        self._shared_dict = shared_dict
        notifier = inotify.INotify()
        mask = inotify.IN_CREATE | inotify.IN_DELETE
        notifier.startReading() 
        notifier.watch(filepath.FilePath(watch_dir), mask=mask, callbacks=[self.notify])
        logger.info('watch dir %s' % (watch_dir,))
        self.timers = {}

    def add(self, path):
        self.notify(None, filepath.FilePath(path), inotify.IN_CREATE)

    def exists(self, path):
        return self.timers.has_key(path)
        
    def watch(self, fragment):
        fragment.advance()
        if fragment.inactive_times > config.MAX_INACTIVE_TIMES and fragment.mode:
            fragment.incr(config.TIMER_INTERVAL)

    def notify(self, unknown, filepath, mask):
        logger.debug('event %s on %s' % (
            ', '.join(inotify.humanReadableMask(mask)), filepath))

        basename = filepath.basename()
        if not basename.endswith(config.GROWING_FILE_SUFFIX):
            return
        path = os.path.join(filepath.dirname(), basename)
        if mask == inotify.IN_CREATE:
            self.handle_in_create(path)
        elif mask == inotify.IN_DELETE:
            self.handle_in_delete(path)
        
    def handle_in_create(self, path):
        if path not in self.timers:
            logger.info('path add to timers %s' % (path,))
            frag = FlvFragment(path)
            self._shared_dict[get_channel(path)] = frag
            timer = internet.TimerService(config.TIMER_INTERVAL, self.watch, frag)
            self.timers[path] = timer
            timer.startService()

    def stop_watching(self, path):
        if path in self.timers:
            logger.info('path remove from timers %s' % (path,))
            timer = self.timers[path]
            timer.stopService()
            del self.timers[path]

    def handle_in_delete(self, path):
        self.stop_watching(path)
        channel = get_channel(path)
        #delete data in shared dict when the growing file has been deleted.
        if self._shared_dict.has_key(channel):
            del self._shared_dict[channel]
