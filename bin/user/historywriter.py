# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
"""Atomic publication of period files, current.json and the segmented manifest; worker lock and retry state.

No WeeWX dependencies. See docs/historic-data-contract.md, sections 2, 4, 5 and 7.
"""

import gzip
import hashlib
import io
import json
import logging
import os
import socket
import tempfile
import time

from user.historyperiods import PERIODS, parse_period_id

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
DATA_DIR = 'historic_data'
ENTRY_STATES = ('ok', 'gaps', 'pending', 'nodata', 'error', 'incompatible')
LOCK_STALE_SECONDS = 1800


# ---------------------------------------------------------------------------------------------
# Encoding and atomic writes
# ---------------------------------------------------------------------------------------------

def to_json_bytes(obj):
    return json.dumps(obj, separators=(',', ':'), allow_nan=False, sort_keys=False).encode('utf-8')


def gzip_bytes(raw):
    """Deterministic gzip (mtime 0, no file name): identical content -> identical bytes -> identical rev."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buf, compresslevel=6, mtime=0) as f:
        f.write(raw)
    return buf.getvalue()


def rev_of(data):
    return hashlib.sha1(data).hexdigest()[:12]


def _fsync_dir(path):
    if os.name != 'posix':
        return
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write(path, data):
    """Write bytes to path: temp file in the same directory -> fsync -> os.replace."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.tmp-', suffix='.part', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _fsync_dir(directory)


def write_json(path, obj, compress=False):
    """Atomically write obj as JSON (optionally gzip); returns the rev of the written bytes."""
    data = to_json_bytes(obj)
    if compress:
        data = gzip_bytes(data)
    atomic_write(path, data)
    return rev_of(data)


def read_json(path):
    """Read plain or gzip JSON; None if the file does not exist."""
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        return None
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    return json.loads(data.decode('utf-8'))


# ---------------------------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------------------------

def data_root(html_root):
    return os.path.join(html_root, DATA_DIR)


def state_dir(config_dict, root, state_root=None):
    """Unpublished worker state directory for a data root (contract 2)."""
    if not state_root:
        weewx_root = config_dict.get('WEEWX_ROOT', '.')
        sqlite_root = config_dict.get('DatabaseTypes', {}).get('SQLite', {}).get('SQLITE_ROOT', '.')
        state_root = os.path.join(weewx_root, sqlite_root, 'fuzzy_archer')
    digest = hashlib.sha1(os.path.normcase(os.path.abspath(root)).encode('utf-8')).hexdigest()[:16]
    return os.path.join(state_root, digest)


def period_file(period, pid):
    parse_period_id(period, pid)
    return '%s/%s.json.gz' % (period, pid)


def segment_key(period, pid):
    return 'all' if period == 'year' else pid[:4]


def segment_file(period, key):
    return 'manifest/%s/%s.json' % (period, key)


def _abs(root, rel):
    return os.path.join(root, *rel.split('/'))


# ---------------------------------------------------------------------------------------------
# Period files
# ---------------------------------------------------------------------------------------------

def missing_observations(data, required_obs_keys):
    observations = data.get('observations', {})
    return sorted(k for k in required_obs_keys if not observations.get(k, {}).get('count'))


def has_any_data(data, required_obs_keys):
    observations = data.get('observations', {})
    return any(observations.get(k, {}).get('count') for k in required_obs_keys)


def publish_period(root, data, required_obs_keys):
    """Write a completed period file and return its manifest entry.

    Periods without any data of the required observations are not written (entry 'nodata').
    """
    if data['kind'] != 'calendar' or data['state'] not in ('complete', 'gaps'):
        raise ValueError("Only completed calendar periods can be published")
    if not has_any_data(data, required_obs_keys):
        return {'s': 'nodata'}
    rel = period_file(data['period'], data['period_id'])
    rev = write_json(_abs(root, rel), data, compress=True)
    entry = {'s': 'ok' if data['state'] == 'complete' else 'gaps', 'rev': rev, 'file': rel}
    missing = missing_observations(data, required_obs_keys)
    if missing:
        entry['missing'] = missing
    return entry


def remove_period_file(root, period, pid):
    try:
        os.unlink(_abs(root, period_file(period, pid)))
    except FileNotFoundError:
        pass


def is_compatible(header, week_start):
    """False for files that must be regenerated (schema version or week boundaries changed)."""
    if not header or header.get('schema_version') != SCHEMA_VERSION:
        return False
    if header.get('period') == 'week' and header.get('week_start') != week_start:
        return False
    return True


def write_current_file(root, kind, period, data):
    """Write current/<period>.json.gz or rolling/<period>.json.gz; returns (relative file, rev)."""
    if kind not in ('current', 'rolling') or period not in PERIODS:
        raise ValueError("Invalid mutable file %s/%s" % (kind, period))
    rel = '%s/%s.json.gz' % (kind, period)
    return rel, write_json(_abs(root, rel), data, compress=True)


def write_current_index(root, generated, week_start, current, rolling):
    """Write current.json last (after the referenced files)."""
    index = {'schema_version': SCHEMA_VERSION, 'generated': int(generated), 'week_start': int(week_start),
             'current': current, 'rolling': rolling}
    return write_json(os.path.join(root, 'current.json'), index)


def read_current_index(root):
    try:
        index = read_json(os.path.join(root, 'current.json'))
    except (OSError, ValueError) as e:
        log.warning("Ignoring unreadable current.json: %s", e)
        return None
    if not index or index.get('schema_version') != SCHEMA_VERSION:
        return None
    return index


# ---------------------------------------------------------------------------------------------
# Manifest (single writer: the worker)
# ---------------------------------------------------------------------------------------------

class Manifest(object):
    """Segmented manifest. Changes are buffered and written by flush(): segments first, index last."""

    def __init__(self, root, week_start):
        self.root = root
        self.week_start = int(week_start)
        self._segments = {}
        self._dirty = set()
        index = None
        try:
            index = read_json(os.path.join(root, 'manifest.json'))
        except (OSError, ValueError) as e:
            log.warning("Unreadable manifest.json, rebuilding: %s", e)
        if not index or index.get('schema_version') != SCHEMA_VERSION:
            index = None
        self.previous_week_start = index.get('week_start') if index else None
        self.index = index or {
            'schema_version': SCHEMA_VERSION, 'generated': 0, 'week_start': self.week_start,
            'archive': {'first': None, 'last': None},
            'backfill': {'state': 'idle', 'done': 0, 'total': 0, 'updated': 0},
            'segments': {},
        }
        self.index['week_start'] = self.week_start

    def segment(self, period, key):
        cache_key = (period, key)
        if cache_key not in self._segments:
            segment = None
            if key in self.index['segments'].get(period, {}):
                try:
                    segment = read_json(_abs(self.root, segment_file(period, key)))
                except (OSError, ValueError) as e:
                    log.warning("Unreadable manifest segment %s/%s, rebuilding: %s", period, key, e)
            if not segment or segment.get('schema_version') != SCHEMA_VERSION:
                segment = {'schema_version': SCHEMA_VERSION, 'period': period, 'segment': key, 'entries': {}}
            self._segments[cache_key] = segment
        return self._segments[cache_key]

    def get(self, period, pid):
        return self.segment(period, segment_key(period, pid))['entries'].get(pid)

    def set(self, period, pid, entry):
        if entry.get('s') not in ENTRY_STATES:
            raise ValueError("Invalid manifest state %s" % entry)
        key = segment_key(period, pid)
        entries = self.segment(period, key)['entries']
        if entries.get(pid) != entry:
            entries[pid] = dict(entry)
            self._dirty.add((period, key))

    def remove(self, period, pid):
        key = segment_key(period, pid)
        entries = self.segment(period, key)['entries']
        if pid in entries:
            del entries[pid]
            self._dirty.add((period, key))

    def entries(self, period):
        """All (pid, entry) of a period type, loading every listed segment."""
        result = {}
        for key in list(self.index['segments'].get(period, {})):
            result.update(self.segment(period, key)['entries'])
        for (p, key), segment in self._segments.items():
            if p == period:
                result.update(segment['entries'])
        return result

    def set_archive(self, first, last):
        self.index['archive'] = {'first': first, 'last': last}

    def set_backfill(self, state, done, total, now):
        self.index['backfill'] = {'state': state, 'done': int(done), 'total': int(total), 'updated': int(now)}

    def flush(self, now=None):
        for period, key in sorted(self._dirty):
            segment = self._segments[(period, key)]
            segment['entries'] = dict(sorted(segment['entries'].items()))
            rev = write_json(_abs(self.root, segment_file(period, key)), segment)
            self.index['segments'].setdefault(period, {})[key] = rev
        self._dirty.clear()
        self.index['generated'] = int(now if now is not None else time.time())
        self.index['segments'] = dict((p, dict(sorted(self.index['segments'][p].items())))
                                      for p in PERIODS if p in self.index['segments'])
        return write_json(os.path.join(self.root, 'manifest.json'), self.index)


# ---------------------------------------------------------------------------------------------
# Retry state (unpublished)
# ---------------------------------------------------------------------------------------------

class RetryState(object):
    """Failure counters per period with exponential backoff (contract 5: max_retries, retry_backoff)."""

    def __init__(self, directory, max_retries=3, retry_backoff=600):
        self.path = os.path.join(directory, 'retries.json')
        self.max_retries = int(max_retries)
        self.retry_backoff = int(retry_backoff)
        try:
            self.data = read_json(self.path) or {}
        except (OSError, ValueError):
            self.data = {}

    def _key(self, period, pid):
        return '%s/%s' % (period, pid)

    def tries(self, period, pid):
        return self.data.get(self._key(period, pid), {}).get('tries', 0)

    def exhausted(self, period, pid):
        return self.tries(period, pid) >= self.max_retries

    def due(self, period, pid, now):
        item = self.data.get(self._key(period, pid))
        if not item:
            return True
        return not self.exhausted(period, pid) and now >= item.get('next', 0)

    def failure(self, period, pid, now, error):
        item = self.data.setdefault(self._key(period, pid), {'tries': 0})
        item['tries'] += 1
        item['next'] = int(now + self.retry_backoff * 2 ** (item['tries'] - 1))
        item['error'] = str(error)[:500]
        self.save()
        return item['tries']

    def clear(self, period, pid=None):
        if pid is None:
            prefix = period + '/'
            keys = [k for k in self.data if k.startswith(prefix)] if period else list(self.data)
        else:
            keys = [self._key(period, pid)]
        changed = False
        for k in keys:
            if self.data.pop(k, None) is not None:
                changed = True
        if changed:
            self.save()

    def save(self):
        write_json(self.path, self.data)


# ---------------------------------------------------------------------------------------------
# Worker lock (shared by backfill and historyregen)
# ---------------------------------------------------------------------------------------------

def _pid_alive(pid):
    if pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return code.value == 259  # STILL_ACTIVE
            return True
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class LockBusy(Exception):
    pass


class WorkerLock(object):
    """O_CREAT|O_EXCL lock file with pid/host/start; stale if the process is gone or not refreshed for 30 min."""

    def __init__(self, directory, stale_seconds=LOCK_STALE_SECONDS):
        self.path = os.path.join(directory, 'worker.lock')
        self.stale_seconds = stale_seconds
        self.owned = False

    def _info(self):
        try:
            with open(self.path, 'r') as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def is_stale(self, now=None):
        now = time.time() if now is None else now
        info = self._info()
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            return True
        if now - mtime > self.stale_seconds:
            return True
        if info and info.get('host') == socket.gethostname() and not _pid_alive(int(info.get('pid', 0))):
            return True
        return info is None and now - mtime > 60

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                if self.is_stale():
                    log.info("Removing stale worker lock %s (%s)", self.path, self._info())
                    try:
                        os.unlink(self.path)
                    except FileNotFoundError:
                        pass
                    continue
                raise LockBusy(self._info())
            with os.fdopen(fd, 'w') as f:
                json.dump({'pid': os.getpid(), 'host': socket.gethostname(), 'start': int(time.time())}, f)
            self.owned = True
            return self
        raise LockBusy(self._info())

    def refresh(self):
        if self.owned:
            os.utime(self.path, None)

    def release(self):
        if self.owned:
            self.owned = False
            try:
                os.unlink(self.path)
            except FileNotFoundError:
                pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False
