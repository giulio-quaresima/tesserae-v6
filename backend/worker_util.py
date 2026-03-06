"""Memory-aware worker count for multiprocessing pools."""

import os

MAX_WORKERS = 4
MIN_WORKERS = 2
LOW_MEMORY_GB = 16


def safe_worker_count(max_workers=MAX_WORKERS):
    """Return a worker count that respects available memory.

    Caps at MAX_WORKERS (4) by default. Drops to MIN_WORKERS (2)
    when available RAM is below LOW_MEMORY_GB (16 GB).
    """
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    avail_kb = int(line.split()[1])
                    avail_gb = avail_kb / (1024 * 1024)
                    if avail_gb < LOW_MEMORY_GB:
                        return MIN_WORKERS
                    break
    except (OSError, ValueError):
        pass
    return min(max_workers, os.cpu_count() or 2)
