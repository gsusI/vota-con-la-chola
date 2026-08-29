"""Kernel, path, and immutable-evidence safety for the identity companion."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import stat
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_ROOT = PROJECT_ROOT / "etl/data/derived/.identity-companion-writer-locks"
LEASE_SCHEMA_VERSION = "outcome_pair_identity_companion_lease_v1"
MAX_PACKAGE_INVENTORY_FILES = 8_192
MAX_PACKAGE_INVENTORY_DIRECTORIES = 8_192
MAX_PACKAGE_INVENTORY_DEPTH = 64
MAX_PACKAGE_RELATIVE_PATH_BYTES = 4_096


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int

    @classmethod
    def from_stat(cls, value: os.stat_result) -> "FileIdentity":
        return cls(
            device=int(value.st_dev),
            inode=int(value.st_ino),
            size=int(value.st_size),
            modified_ns=int(value.st_mtime_ns),
            changed_ns=int(value.st_ctime_ns),
        )


@dataclass
class BoundRegularFile:
    path: Path
    handle: BinaryIO
    identity: FileIdentity

    def sha256(self) -> str:
        self.handle.seek(0)
        digest = hashlib.sha256()
        for chunk in iter(lambda: self.handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
        self.handle.seek(0)
        return digest.hexdigest()

    def read_bytes(self, *, max_bytes: int) -> bytes:
        if self.identity.size < 1 or self.identity.size > max_bytes:
            raise RuntimeError("immutable evidence size exceeds hard contract")
        self.handle.seek(0)
        payload = self.handle.read(max_bytes + 1)
        self.handle.seek(0)
        if len(payload) != self.identity.size or len(payload) > max_bytes:
            raise RuntimeError("immutable evidence bytes changed during read")
        return payload


def _resolved_regular_path(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError("immutable evidence path is a symlink")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise RuntimeError("required immutable evidence is missing") from exc
    if resolved.is_symlink():
        raise RuntimeError("immutable evidence resolved to a symlink")
    return resolved


def _reject_database_wal(resolved: Path) -> None:
    wal = Path(f"{resolved}-wal")
    if wal.exists() or wal.is_symlink():
        wal_stat = wal.lstat()
        if not stat.S_ISREG(wal_stat.st_mode) or wal_stat.st_size:
            raise RuntimeError("database has an unsafe or non-empty WAL")


@contextmanager
def bound_regular_file(
    path: Path,
    *,
    database: bool = False,
) -> Iterator[BoundRegularFile]:
    """Open one immutable regular file without following its final component."""

    resolved = _resolved_regular_path(Path(path))
    if database:
        _reject_database_wal(resolved)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(resolved, flags)
    handle = os.fdopen(descriptor, "rb", closefd=True)
    try:
        descriptor_stat = os.fstat(handle.fileno())
        path_stat = resolved.lstat()
        identity = FileIdentity.from_stat(descriptor_stat)
        if (
            not stat.S_ISREG(descriptor_stat.st_mode)
            or descriptor_stat.st_nlink != 1
            or FileIdentity.from_stat(path_stat) != identity
        ):
            raise RuntimeError("immutable evidence inode is unsafe")
        bound = BoundRegularFile(path=resolved, handle=handle, identity=identity)
        yield bound
        final_descriptor = os.fstat(handle.fileno())
        final_path = resolved.lstat()
        if (
            FileIdentity.from_stat(final_descriptor) != identity
            or FileIdentity.from_stat(final_path) != identity
            or final_descriptor.st_nlink != 1
            or not stat.S_ISREG(final_descriptor.st_mode)
        ):
            raise RuntimeError("immutable evidence changed while bound")
        if database:
            _reject_database_wal(resolved)
    finally:
        handle.close()


def stable_regular_file_fact(
    path: Path,
    *,
    database: bool = False,
) -> tuple[dict[str, Any], FileIdentity]:
    with bound_regular_file(path, database=database) as bound:
        digest = bound.sha256()
        identity = bound.identity
        resolved = bound.path
    return {
        "bytes": identity.size,
        "sha256": digest,
        "resolved": resolved,
    }, identity


def assert_regular_file_stable(
    path: Path,
    identity: FileIdentity,
    *,
    database: bool = False,
) -> None:
    with bound_regular_file(path, database=database) as bound:
        if bound.identity != identity:
            raise RuntimeError("immutable evidence changed during operation")


def require_exact_int(name: str, value: Any, expected: int) -> int:
    if type(value) is not int or value != expected:
        raise ValueError(f"{name} must equal the hard contract value {expected}")
    return value


def require_bounded_int(
    name: str,
    value: Any,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise ValueError(f"{name} is outside the hard integer contract")
    return value


def require_bounded_finite_float(
    name: str,
    value: Any,
    *,
    minimum_exclusive: float,
    maximum: float,
) -> float:
    if type(value) not in {int, float}:
        raise ValueError(f"{name} must be a finite JSON number")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= minimum_exclusive or parsed > maximum:
        raise ValueError(f"{name} is outside the hard finite resource contract")
    return parsed


def paths_overlap(left: Path, right: Path) -> bool:
    left = Path(left).resolve(strict=False)
    right = Path(right).resolve(strict=False)
    try:
        left.relative_to(right)
        return True
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return True
    except ValueError:
        return False


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _open_secure_lock_root() -> int:
    project_root = PROJECT_ROOT.resolve()
    relative = LOCK_ROOT.relative_to(PROJECT_ROOT)
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    current = os.open(project_root, flags)
    try:
        for component in relative.parts:
            try:
                os.mkdir(component, 0o700, dir_fd=current)
            except FileExistsError:
                pass
            following = os.open(component, flags, dir_fd=current)
            following_stat = os.fstat(following)
            if (
                not stat.S_ISDIR(following_stat.st_mode)
                or following_stat.st_uid != os.geteuid()
            ):
                os.close(following)
                raise RuntimeError("identity lease root is unsafe")
            os.close(current)
            current = following
        root_stat = os.fstat(current)
        if stat.S_IMODE(root_stat.st_mode) != 0o700:
            os.fchmod(current, 0o700)
        os.fsync(current)
        return current
    except BaseException:
        os.close(current)
        raise


def identity_lease_path(target: Path, *, namespace: str) -> Path:
    if namespace not in {"build", "command", "evidence"}:
        raise ValueError("unsupported identity lease namespace")
    resolved = Path(target).resolve(strict=False)
    identity = hashlib.sha256(resolved.as_posix().encode("utf-8")).hexdigest()
    return LOCK_ROOT / f"{identity}.lock"


@contextmanager
def identity_companion_leases(
    targets: Sequence[Path],
    *,
    namespace: str,
) -> Iterator[tuple[Path, ...]]:
    """Acquire deterministic cross-process exclusive leases for all targets."""

    lock_paths = sorted(
        {identity_lease_path(Path(target), namespace=namespace) for target in targets},
        key=lambda path: path.name,
    )
    root_descriptor = _open_secure_lock_root()
    acquired: list[tuple[int, Path]] = []
    try:
        for lock_path in lock_paths:
            flags = os.O_CREAT | os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(lock_path.name, flags, 0o600, dir_fd=root_descriptor)
            descriptor_stat = os.fstat(descriptor)
            if not (
                stat.S_ISREG(descriptor_stat.st_mode)
                and descriptor_stat.st_uid == os.geteuid()
                and descriptor_stat.st_nlink == 1
                and stat.S_IMODE(descriptor_stat.st_mode) == 0o600
            ):
                os.close(descriptor)
                raise RuntimeError("identity lease inode is unsafe")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                os.close(descriptor)
                raise RuntimeError(
                    "another identity companion command holds a lease"
                ) from exc
            acquired.append((descriptor, lock_path))
        os.fsync(root_descriptor)
        for descriptor, lock_path in acquired:
            owner = {
                "schema_version": LEASE_SCHEMA_VERSION,
                "state": "held",
                "namespace": namespace,
                "target_identity_sha256": lock_path.stem,
                "pid": os.getpid(),
                "acquired_at": _now_iso(),
                "stale_recovery": "kernel_releases_flock_after_process_exit",
            }
            encoded = (
                json.dumps(
                    owner,
                    allow_nan=False,
                    ensure_ascii=True,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            os.ftruncate(descriptor, 0)
            os.lseek(descriptor, 0, os.SEEK_SET)
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        yield tuple(lock_paths)
        for descriptor, lock_path in acquired:
            released = {
                "schema_version": LEASE_SCHEMA_VERSION,
                "state": "released",
                "namespace": namespace,
                "target_identity_sha256": lock_path.stem,
                "pid": os.getpid(),
                "released_at": _now_iso(),
                "stale_recovery": "kernel_releases_flock_after_process_exit",
            }
            encoded = (
                json.dumps(
                    released,
                    allow_nan=False,
                    ensure_ascii=True,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            os.ftruncate(descriptor, 0)
            os.lseek(descriptor, 0, os.SEEK_SET)
            os.write(descriptor, encoded)
            os.fsync(descriptor)
    finally:
        for descriptor, _lock_path in reversed(acquired):
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        os.close(root_descriptor)


def _regular_control_target(path: Path) -> None:
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError("control target is a symlink")
    if not path.exists():
        return
    target_stat = path.lstat()
    if not stat.S_ISREG(target_stat.st_mode) or target_stat.st_nlink != 1:
        raise RuntimeError("control target is not a private regular file")


def preflight_control_target(path: Path) -> Path:
    """Resolve one writable control path without accepting linked final inodes."""

    path = Path(path)
    if path.is_symlink():
        raise RuntimeError("control target is a symlink")
    parent = path.parent.resolve(strict=False)
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise RuntimeError("control target parent is unsafe")
    resolved = parent / path.name
    _regular_control_target(resolved)
    return resolved


def preflight_output_root(path: Path) -> Path:
    """Resolve a not-yet-created package root and reject dangling links."""

    path = Path(path)
    if path.is_symlink():
        raise RuntimeError("package output target is a symlink")
    parent = path.parent.resolve(strict=False)
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise RuntimeError("package output parent is unsafe")
    resolved = parent / path.name
    if resolved.is_symlink():
        raise RuntimeError("package output target is a symlink")
    if resolved.exists() and not resolved.is_dir():
        raise RuntimeError("package output target is not a directory")
    return resolved


def secure_unlink_regular(path: Path) -> bool:
    path = preflight_control_target(path)
    _regular_control_target(path)
    if not path.exists():
        return False
    path.unlink()
    fsync_directory(path.parent)
    return True


def secure_atomic_write_bytes(path: Path, payload: bytes) -> None:
    path = preflight_control_target(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        temporary_stat = os.fstat(descriptor)
        if not stat.S_ISREG(temporary_stat.st_mode) or temporary_stat.st_nlink != 1:
            raise RuntimeError("temporary control inode is unsafe")
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        final_stat = path.lstat()
        if not stat.S_ISREG(final_stat.st_mode) or final_stat.st_nlink != 1:
            raise RuntimeError("published control inode is unsafe")
        fsync_directory(path.parent)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def secure_atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    secure_atomic_write_bytes(path, encoded)


def fsync_regular_file(path: Path) -> None:
    resolved = _resolved_regular_path(Path(path))
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(resolved, flags)
    try:
        descriptor_stat = os.fstat(descriptor)
        if not stat.S_ISREG(descriptor_stat.st_mode) or descriptor_stat.st_nlink != 1:
            raise RuntimeError("file to fsync is unsafe")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fsync_directory(path: Path) -> None:
    resolved = Path(path).resolve(strict=True)
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(resolved, flags)
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise RuntimeError("directory to fsync is unsafe")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def exact_regular_inventory(
    root: Path,
    *,
    max_files: int = MAX_PACKAGE_INVENTORY_FILES,
    max_directories: int = MAX_PACKAGE_INVENTORY_DIRECTORIES,
    max_depth: int = MAX_PACKAGE_INVENTORY_DEPTH,
    max_path_bytes: int = MAX_PACKAGE_RELATIVE_PATH_BYTES,
) -> tuple[set[str], set[str]]:
    """Stream a hard-bounded inode inventory; reject special/link inodes."""

    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("package root is not a real directory")
    if (
        type(max_files) is not int
        or type(max_directories) is not int
        or type(max_depth) is not int
        or type(max_path_bytes) is not int
        or max_files < 1
        or max_directories < 1
        or max_depth < 1
        or max_path_bytes < 1
        or max_files > MAX_PACKAGE_INVENTORY_FILES
        or max_directories > MAX_PACKAGE_INVENTORY_DIRECTORIES
        or max_depth > MAX_PACKAGE_INVENTORY_DEPTH
        or max_path_bytes > MAX_PACKAGE_RELATIVE_PATH_BYTES
    ):
        raise ValueError("package inventory bounds exceed the hard contract")
    files: set[str] = set()
    directories: set[str] = {"."}
    inode_ids: set[tuple[int, int]] = set()
    pending_directories = [root]
    while pending_directories:
        current = pending_directories.pop()
        current_stat = current.lstat()
        if not stat.S_ISDIR(current_stat.st_mode) or current.is_symlink():
            raise RuntimeError("package contains an unsafe directory")
        with os.scandir(current) as entries:
            for entry in entries:
                path = current / entry.name
                path_stat = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(path_stat.st_mode):
                    if entry.is_symlink():
                        raise RuntimeError(
                            "package contains a special or linked directory"
                        )
                    relative = path.relative_to(root).as_posix()
                    if (
                        len(Path(relative).parts) > max_depth
                        or len(relative.encode("utf-8")) > max_path_bytes
                    ):
                        raise RuntimeError(
                            "package directory depth or path bytes exceed the hard bound"
                        )
                    if relative in directories:
                        raise RuntimeError("package contains a duplicate directory")
                    if len(directories) >= max_directories:
                        raise RuntimeError(
                            "package directory inventory exceeds the hard bound"
                        )
                    directories.add(relative)
                    pending_directories.append(path)
                    continue
                inode = (int(path_stat.st_dev), int(path_stat.st_ino))
                if (
                    not stat.S_ISREG(path_stat.st_mode)
                    or entry.is_symlink()
                    or path_stat.st_nlink != 1
                    or inode in inode_ids
                ):
                    raise RuntimeError(
                        "package contains a special, linked, or aliased file"
                    )
                relative = path.relative_to(root).as_posix()
                if (
                    len(Path(relative).parts) > max_depth
                    or len(relative.encode("utf-8")) > max_path_bytes
                ):
                    raise RuntimeError(
                        "package file depth or path bytes exceed the hard bound"
                    )
                if relative in files:
                    raise RuntimeError("package contains a duplicate file path")
                if len(files) >= max_files:
                    raise RuntimeError("package file inventory exceeds the hard bound")
                inode_ids.add(inode)
                files.add(relative)
    return files, directories


__all__ = [
    "BoundRegularFile",
    "FileIdentity",
    "LOCK_ROOT",
    "MAX_PACKAGE_INVENTORY_DIRECTORIES",
    "MAX_PACKAGE_INVENTORY_DEPTH",
    "MAX_PACKAGE_INVENTORY_FILES",
    "MAX_PACKAGE_RELATIVE_PATH_BYTES",
    "assert_regular_file_stable",
    "bound_regular_file",
    "exact_regular_inventory",
    "fsync_directory",
    "fsync_regular_file",
    "identity_companion_leases",
    "identity_lease_path",
    "paths_overlap",
    "preflight_control_target",
    "preflight_output_root",
    "require_bounded_finite_float",
    "require_bounded_int",
    "require_exact_int",
    "secure_atomic_write_bytes",
    "secure_atomic_write_json",
    "secure_unlink_regular",
    "stable_regular_file_fact",
]
