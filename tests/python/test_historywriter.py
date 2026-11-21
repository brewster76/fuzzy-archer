import gzip
import json
import os
import stat
import subprocess
import sys

import pytest

from user import historywriter as hw

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'schemas')


def validator(name):
    jsonschema = pytest.importorskip('jsonschema')
    with open(os.path.join(SCHEMA_DIR, name)) as f:
        return jsonschema.Draft202012Validator(json.load(f))


def period_data(state='complete', counts=None, period='day', pid='20261120', week_start=None):
    counts = {'wx_binding/outTemp': 288, 'wx_binding/UV': 0} if counts is None else counts
    data = {'schema_version': 1, 'kind': 'calendar', 'period': period, 'period_id': pid, 'state': state,
            'observations': dict((k, {'count': c}) for k, c in counts.items())}
    if week_start is not None:
        data['week_start'] = week_start
    return data


def test_atomic_write_and_deterministic_gzip(tmp_path):
    path = str(tmp_path / 'a' / 'b.json.gz')
    rev1 = hw.write_json(path, {'x': 1}, compress=True)
    with open(path, 'rb') as f:
        raw = f.read()
    assert raw[:2] == b'\x1f\x8b'
    assert json.loads(gzip.decompress(raw)) == {'x': 1}
    assert rev1 == hw.rev_of(raw)
    assert len(rev1) == 12
    if os.name == 'posix':
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode & 0o444 == 0o444
        assert mode & 0o222 == 0o200
    assert hw.write_json(path, {'x': 1}, compress=True) == rev1
    assert hw.write_json(path, {'x': 2}, compress=True) != rev1
    assert [p for p in os.listdir(tmp_path / 'a')] == ['b.json.gz']  # no temp files left
    assert hw.read_json(path) == {'x': 2}
    assert hw.read_json(str(tmp_path / 'missing.json')) is None


def test_atomic_write_keeps_old_file_on_error(tmp_path):
    path = str(tmp_path / 'f.json')
    hw.write_json(path, {'ok': True})
    with pytest.raises(ValueError):
        hw.write_json(path, {'bad': float('nan')})
    assert hw.read_json(path) == {'ok': True}


def test_publish_period_states(tmp_path):
    root = str(tmp_path)
    required = ['wx_binding/outTemp', 'wx_binding/UV']
    entry = hw.publish_period(root, period_data(), required)
    assert entry['s'] == 'ok'
    assert entry['file'] == 'day/20261120.json.gz'
    assert entry['missing'] == ['wx_binding/UV']
    assert os.path.exists(os.path.join(root, 'day', '20261120.json.gz'))
    assert hw.publish_period(root, period_data('gaps', pid='20261121'), required)['s'] == 'gaps'
    nodata = hw.publish_period(root, period_data(counts={}, pid='20261122'), required)
    assert nodata == {'s': 'nodata'}
    assert not os.path.exists(os.path.join(root, 'day', '20261122.json.gz'))
    running_data = period_data('running')
    with pytest.raises(ValueError):
        hw.publish_period(root, running_data, required)
    invalid_id_data = period_data(pid='../../x')
    with pytest.raises(ValueError):
        hw.publish_period(root, invalid_id_data, required)


def test_manifest_segments_and_index(tmp_path):
    root = str(tmp_path)
    m = hw.Manifest(root, 6)
    m.set('day', '20251231', {'s': 'ok', 'rev': '0123456789ab', 'file': 'day/20251231.json.gz'})
    m.set('day', '20260101', {'s': 'error', 'tries': 3})
    m.set('year', '2025', {'s': 'nodata'})
    m.set_archive(100, 200)
    m.set_backfill('running', 1, 10, 1000)
    m.flush(now=1000)
    index = hw.read_json(os.path.join(root, 'manifest.json'))
    assert set(index['segments']['day']) == {'2025', '2026'}
    assert 'all' in index['segments']['year']
    seg = hw.read_json(os.path.join(root, 'manifest', 'day', '2026.json'))
    assert seg['entries'] == {'20260101': {'s': 'error', 'tries': 3}}
    v = validator('manifest-v1.schema.json')
    v.validate(index)
    v.validate(seg)
    # reload, unchanged segment keeps its rev, changed one gets a new rev
    m2 = hw.Manifest(root, 6)
    assert m2.get('day', '20251231')['s'] == 'ok'
    m2.set('day', '20260101', {'s': 'pending'})
    m2.flush(now=2000)
    index2 = hw.read_json(os.path.join(root, 'manifest.json'))
    assert index2['segments']['day']['2025'] == index['segments']['day']['2025']
    assert index2['segments']['day']['2026'] != index['segments']['day']['2026']
    assert set(m2.entries('day')) == {'20251231', '20260101'}
    with pytest.raises(ValueError):
        m2.set('day', '20260102', {'s': 'weird'})


def test_manifest_index_without_segments_is_migrated(tmp_path):
    root = str(tmp_path)
    hw.write_json(os.path.join(root, 'manifest.json'), {
        'schema_version': 1, 'generated': 100, 'week_start': 6,
        'archive': {'first': None, 'last': None},
        'backfill': {'state': 'idle', 'done': 0, 'total': 0, 'updated': 100},
    })

    manifest = hw.Manifest(root, 6)
    assert manifest.entries('week') == {}
    manifest.flush(now=200)

    index = hw.read_json(os.path.join(root, 'manifest.json'))
    assert index['segments'] == {}
    validator('manifest-v1.schema.json').validate(index)


def test_current_index(tmp_path):
    root = str(tmp_path)
    rel, rev = hw.write_current_file(root, 'current', 'day', {'a': 1})
    rel2, rev2 = hw.write_current_file(root, 'rolling', 'week', {'b': 1})
    hw.write_current_index(root, 1000, 6,
                           {'day': {'period_id': '20261121', 'file': rel, 'rev': rev, 'generated': 1000,
                                    'refresh': 300}},
                           {'week': {'file': rel2, 'rev': rev2, 'generated': 1000, 'refresh': 3600}})
    index = hw.read_current_index(root)
    validator('current-v1.schema.json').validate(index)
    with pytest.raises(ValueError):
        hw.write_current_file(root, 'rolling', '../x', {})


def test_compatibility():
    assert hw.is_compatible(period_data(), 6)
    assert not hw.is_compatible(period_data(period='week', pid='20261115', week_start=6), 0)
    assert not hw.is_compatible(dict(period_data(), schema_version=2), 6)
    assert not hw.is_compatible(None, 6)


def test_retry_state(tmp_path):
    r = hw.RetryState(str(tmp_path), max_retries=3, retry_backoff=600)
    assert r.due('day', '20261120', 0)
    assert r.failure('day', '20261120', 1000, 'boom') == 1
    assert not r.due('day', '20261120', 1599)
    assert r.due('day', '20261120', 1600)
    r.failure('day', '20261120', 1600, 'boom')
    assert not r.due('day', '20261120', 2799)
    assert r.due('day', '20261120', 2800)
    r.failure('day', '20261120', 2800, 'boom')
    assert r.exhausted('day', '20261120')
    assert not r.due('day', '20261120', 10 ** 9)
    r2 = hw.RetryState(str(tmp_path), max_retries=3)
    assert r2.tries('day', '20261120') == 3
    r2.clear('day')
    assert hw.RetryState(str(tmp_path)).tries('day', '20261120') == 0


def test_worker_lock(tmp_path):
    lock = hw.WorkerLock(str(tmp_path))
    with lock:
        duplicate_lock = hw.WorkerLock(str(tmp_path))
        with pytest.raises(hw.LockBusy):
            duplicate_lock.acquire()
        lock.refresh()
    assert not os.path.exists(lock.path)


def test_worker_lock_stale_dead_pid(tmp_path):
    proc = subprocess.Popen([sys.executable, '-c', 'pass'])
    proc.wait()
    lock_path = os.path.join(str(tmp_path), 'worker.lock')
    with open(lock_path, 'w') as f:
        json.dump({'pid': proc.pid, 'host': hw.socket.gethostname(), 'start': 0}, f)
    with hw.WorkerLock(str(tmp_path)) as lock:
        assert hw.read_json(lock_path)['pid'] == os.getpid()


def test_worker_lock_stale_by_age(tmp_path):
    lock_path = os.path.join(str(tmp_path), 'worker.lock')
    with open(lock_path, 'w') as f:
        json.dump({'pid': os.getpid(), 'host': 'other-host', 'start': 0}, f)
    lock = hw.WorkerLock(str(tmp_path))
    with pytest.raises(hw.LockBusy):
        lock.acquire()
    old = os.path.getmtime(lock_path) - 3600
    os.utime(lock_path, (old, old))
    hw.WorkerLock(str(tmp_path)).acquire().release()


def test_state_dir():
    config = {'WEEWX_ROOT': '/home/weewx', 'DatabaseTypes': {'SQLite': {'SQLITE_ROOT': 'archive'}}}
    d = hw.state_dir(config, '/var/www/html/historic_data')
    assert d.startswith(os.path.join('/home/weewx', 'archive', 'fuzzy_archer'))
    assert d != hw.state_dir(config, '/var/www/other/historic_data')
    assert hw.state_dir(config, '/x', state_root='/state').startswith('/state')
