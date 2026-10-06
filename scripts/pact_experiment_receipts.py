"""Atomic lifecycle receipts and resource observations; no search policy."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path, data, immutable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        raise ValueError('Immutable receipt already exists: '+str(path))
    fd, temporary = tempfile.mkstemp(prefix='.'+path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            os.link(temporary, path)
            os.unlink(temporary)
        else:
            os.replace(temporary, path)
        if os.name != 'nt':
            try:
                directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError:
                pass  # Mounted Windows volumes may not support directory fsync.
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def resources(disk_paths=None):
    record = dict(observed_utc=now(), PID=os.getpid(), disks={})
    paths = {'workspace': Path.cwd()} if disk_paths is None else disk_paths
    for label, path in paths.items():
        if Path(path).exists():
            usage = shutil.disk_usage(path)
            record['disks'][label] = dict(total=usage.total, free=usage.free)
    if os.name == 'nt':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                        ('physical_total', ctypes.c_ulonglong), ('physical_available', ctypes.c_ulonglong),
                        ('page_total', ctypes.c_ulonglong), ('page_available', ctypes.c_ulonglong),
                        ('virtual_total', ctypes.c_ulonglong), ('virtual_available', ctypes.c_ulonglong),
                        ('extended_available', ctypes.c_ulonglong)]
        value = Memory()
        value.length = ctypes.sizeof(value)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            record['host_memory'] = dict(total_bytes=value.physical_total, available_bytes=value.physical_available)
        ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        record['Windows_uptime_ms'] = ctypes.windll.kernel32.GetTickCount64()
    else:
        record['Linux_boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        record['host_memory'] = {row.split(':')[0]: row.split(':')[1].strip()
                                 for row in Path('/proc/meminfo').read_text().splitlines()
                                 if row.startswith(('MemTotal:', 'MemAvailable:', 'SwapTotal:', 'SwapFree:'))}
    return record


class LaneReceipts:
    """Completion requires a complete search receipt, never worker disappearance."""
    terminal = {'COMPLETED', 'FAILED', 'INTERRUPTED'}

    def __init__(self, root, inputs, disk_paths=None):
        self.root, self.inputs = Path(root), inputs
        self.disk_paths = disk_paths
        self.active = None

    def transition(self, epsilon, state, **fields):
        path = self.root/f'budget_{epsilon:.2f}'/'lifecycle.json'
        previous = json.loads(path.read_text()) if path.exists() else {}
        if previous.get('state') in self.terminal:
            raise ValueError('Terminal lane evidence is immutable')
        if state == 'COMPLETED' and not fields.get('completion_receipt'):
            raise ValueError('Completion requires a bound complete search receipt')
        record = dict(previous, **self.inputs, **fields, state=state, epsilon=epsilon,
                      updated_utc=now(), resources=resources(self.disk_paths))
        record.setdefault('registered_utc', record['updated_utc'])
        record.setdefault('exit_code', None)
        record.setdefault('end_utc', None)
        record.setdefault('last_checkpoint', None)
        record.setdefault('completion_reason', None)
        if state == 'STARTED':
            record['start_utc'] = record['updated_utc']
            record['PID'] = os.getpid()
            self.active = epsilon
        if state in self.terminal:
            record['end_utc'] = record['updated_utc']
            if self.active == epsilon:
                self.active = None
        sequence = previous.get('sequence', 0)+1
        record['sequence'] = sequence
        atomic_write(path.parent/'events'/f'{sequence:05d}_{state}.json', record, immutable=True)
        atomic_write(path, record)
        return record

    def interrupt_active(self, reason, exit_code, **fields):
        for path in self.root.glob('budget_*/lifecycle.json'):
            previous = json.loads(path.read_text())
            if previous['state'] in ('STARTED', 'CHECKPOINTED'):
                self.transition(previous['epsilon'], 'INTERRUPTED' if fields.get('timed_out') or fields.get('interrupted') else 'FAILED',
                                completion_reason=reason, exit_code=exit_code, **fields)
