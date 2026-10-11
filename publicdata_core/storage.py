"""Disk-footprint helpers: copy-on-write file clones and browser-profile pruning."""

from __future__ import annotations

import ctypes
import os
import shutil
import sys
from pathlib import Path

DEFAULT_CHUNK_BYTES = 1024 * 1024

# Linux reflink ioctl (btrfs, xfs, bcachefs); macOS uses clonefile(2) on APFS.
_FICLONE = 0x40049409
_CLONE_NOFOLLOW = 0x0001

_clonefile = None
if sys.platform == "darwin":
    try:
        _libc = ctypes.CDLL(None, use_errno=True)
        _clonefile = _libc.clonefile
        _clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
        _clonefile.restype = ctypes.c_int
    except (OSError, AttributeError):
        _clonefile = None


def try_clone(source: Path, destination: Path) -> bool:
    """Create ``destination`` as a copy-on-write clone of ``source``.

    The clone is an independent file with identical bytes that shares disk
    blocks until either side is modified. Returns False (leaving no
    destination behind) when the filesystem cannot clone, e.g. across devices.
    ``destination`` must not exist.
    """
    source, destination = Path(source), Path(destination)
    if _clonefile is not None:
        rc = _clonefile(os.fsencode(source), os.fsencode(destination), _CLONE_NOFOLLOW)
        return rc == 0
    if sys.platform.startswith("linux"):
        import fcntl

        try:
            with source.open("rb") as src, destination.open("xb") as dst:
                fcntl.ioctl(dst.fileno(), _FICLONE, src.fileno())
            return True
        except OSError:
            destination.unlink(missing_ok=True)
            return False
    return False


def clone_or_copy(source: Path, destination: Path, *, replace: bool = False) -> bool:
    """Clone ``source`` to a new ``destination`` file, falling back to a durable copy.

    With ``replace=True`` an existing destination is overwritten (like
    ``shutil.copy2``). Returns True when a clone was made (no extra disk blocks).
    """
    if replace:
        Path(destination).unlink(missing_ok=True)
    if try_clone(source, destination):
        return True
    with Path(source).open("rb") as src, Path(destination).open("xb") as dst:
        shutil.copyfileobj(src, dst, length=DEFAULT_CHUNK_BYTES)
        dst.flush()
        os.fsync(dst.fileno())
    return False


# Chromium profile entries that are pure caches / downloaded models. Cookies,
# Local Storage and other session state needed to reuse WAF clearance are kept.
BROWSER_PROFILE_CACHE_ENTRIES = (
    "optimization_guide_model_store",
    "GraphiteDawnCache",
    "GrShaderCache",
    "ShaderCache",
    "BrowserMetrics",
    "BrowserMetrics-spare.pma",
    "component_crx_cache",
    "extensions_crx_cache",
    "Crashpad",
    "Safe Browsing",
    "Default/Cache",
    "Default/Code Cache",
    "Default/GPUCache",
    "Default/DawnWebGPUCache",
    "Default/DawnGraphiteCache",
    "Default/Service Worker/CacheStorage",
    "Default/Service Worker/ScriptCache",
    "Default/History",
    "Default/History-journal",
)


def _tree_bytes(path: Path) -> int:
    if path.is_file() or path.is_symlink():
        return path.lstat().st_size
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def prune_browser_profile(profile_dir: Path) -> int:
    """Delete cache-only entries from a Chromium user-data dir; return bytes freed.

    Safe to run after the browser context is closed. Session state (cookies,
    local storage) is preserved so the profile can still be reused.
    """
    profile_dir = Path(profile_dir)
    if not profile_dir.is_dir():
        return 0
    freed = 0
    for rel in BROWSER_PROFILE_CACHE_ENTRIES:
        entry = profile_dir / rel
        if not (entry.exists() or entry.is_symlink()):
            continue
        freed += _tree_bytes(entry)
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
    return freed
