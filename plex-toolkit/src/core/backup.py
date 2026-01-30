"""
Backup Engine Module
Handles backup and restore operations for Plex Media Server data
"""

import os
import shutil
import subprocess
import threading
import time
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Set
from enum import Enum
from datetime import datetime

from .platform import PlatformDetector, OSType, get_platform
from .plex_paths import PlexPathFinder, PlexPaths
from .compression import CompressionManager, CompressionFormat


class BackupMode(Enum):
    """Backup operation modes"""
    HOT = "hot"  # Copy while Plex is running
    COLD = "cold"  # Stop Plex, copy, restart
    SMART = "smart"  # Hot copy, then cold differential sync
    INCREMENTAL = "incremental"  # Only changed files since last backup
    DATABASE_ONLY = "database_only"  # Just databases


class BackupStatus(Enum):
    """Status of backup operation"""
    IDLE = "idle"
    PREPARING = "preparing"
    STOPPING_PLEX = "stopping_plex"
    COPYING = "copying"
    VERIFYING = "verifying"
    COMPRESSING = "compressing"
    STARTING_PLEX = "starting_plex"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackupProgress:
    """Progress information for backup operation"""
    status: BackupStatus = BackupStatus.IDLE
    phase: str = ""
    current_file: str = ""
    files_total: int = 0
    files_done: int = 0
    bytes_total: int = 0
    bytes_done: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def percent(self) -> float:
        if self.bytes_total == 0:
            return 0
        return (self.bytes_done / self.bytes_total) * 100

    @property
    def elapsed_seconds(self) -> float:
        if not self.start_time:
            return 0
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def speed_bps(self) -> float:
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0
        return self.bytes_done / elapsed

    @property
    def eta_seconds(self) -> float:
        if self.speed_bps == 0:
            return 0
        remaining = self.bytes_total - self.bytes_done
        return remaining / self.speed_bps


@dataclass
class BackupManifest:
    """Manifest describing a backup"""
    version: str = "2.0.0"
    created_at: str = ""
    source_platform: str = ""
    source_hostname: str = ""
    machine_identifier: str = ""
    server_name: str = ""
    backup_mode: str = ""
    plex_version: str = ""
    total_size: int = 0
    file_count: int = 0
    files: Dict[str, Dict] = field(default_factory=dict)
    checksums: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'created_at': self.created_at,
            'source_platform': self.source_platform,
            'source_hostname': self.source_hostname,
            'machine_identifier': self.machine_identifier,
            'server_name': self.server_name,
            'backup_mode': self.backup_mode,
            'plex_version': self.plex_version,
            'total_size': self.total_size,
            'file_count': self.file_count,
            'files': self.files,
            'checksums': self.checksums
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackupManifest':
        return cls(**data)

    def save(self, filepath: str) -> None:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> 'BackupManifest':
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))


class BackupEngine:
    """
    Cross-platform backup engine for Plex Media Server
    Supports Windows, Linux, macOS, and NAS devices
    """

    # Directories/files to exclude from backup
    EXCLUDE_PATTERNS = [
        "Cache",
        "Crash Reports",
        "Diagnostics",
        "Logs",
        "Updates",
        "*.tmp",
        "*.log",
        "Transcode",
        "plexmediaserver.pid",
        ".plex.pid"
    ]

    # Critical files that must be backed up
    CRITICAL_FILES = [
        "Preferences.xml",
        "Plug-in Support/Databases/com.plexapp.plugins.library.db",
        "Plug-in Support/Databases/com.plexapp.plugins.library.blobs.db"
    ]

    def __init__(self,
                 platform: Optional[PlatformDetector] = None,
                 path_finder: Optional[PlexPathFinder] = None):
        self.platform = platform or get_platform()
        self.path_finder = path_finder or PlexPathFinder(self.platform)
        self.progress = BackupProgress()
        self._running = False
        self._cancelled = False
        self._callbacks: List[Callable[[BackupProgress], None]] = []
        self._thread: Optional[threading.Thread] = None

    def add_progress_callback(self, callback: Callable[[BackupProgress], None]) -> None:
        """Add callback for progress updates"""
        self._callbacks.append(callback)

    def _notify_progress(self) -> None:
        """Notify callbacks of progress update"""
        for callback in self._callbacks:
            try:
                callback(self.progress)
            except Exception:
                pass

    def _update_status(self, status: BackupStatus, phase: str = "") -> None:
        """Update backup status"""
        self.progress.status = status
        self.progress.phase = phase
        self._notify_progress()

    def get_source_paths(self) -> Optional[PlexPaths]:
        """Get Plex source paths"""
        return self.path_finder.paths

    def estimate_backup_size(self) -> int:
        """Estimate total backup size in bytes"""
        paths = self.get_source_paths()
        if not paths:
            return 0

        total = 0
        for root, dirs, files in os.walk(paths.data_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not self._should_exclude(d)]

            for file in files:
                if not self._should_exclude(file):
                    try:
                        filepath = os.path.join(root, file)
                        total += os.path.getsize(filepath)
                    except OSError:
                        pass

        return total

    def _should_exclude(self, name: str) -> bool:
        """Check if file/directory should be excluded"""
        import fnmatch
        for pattern in self.EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    def get_excluded_dirs(self) -> List[str]:
        """Get list of directories to exclude"""
        return [p for p in self.EXCLUDE_PATTERNS if not p.startswith('*')]

    def start_backup(self,
                    destination: str,
                    mode: BackupMode = BackupMode.HOT,
                    compress: bool = False,
                    compress_format: CompressionFormat = CompressionFormat.ZIP,
                    verify: bool = True) -> bool:
        """
        Start backup operation

        Args:
            destination: Backup destination path
            mode: Backup mode (hot, cold, smart, incremental)
            compress: Whether to compress the backup
            compress_format: Compression format if compressing
            verify: Whether to verify backup after completion
        """
        if self._running:
            return False

        self._running = True
        self._cancelled = False
        self.progress = BackupProgress(start_time=time.time())

        self._thread = threading.Thread(
            target=self._backup_thread,
            args=(destination, mode, compress, compress_format, verify),
            daemon=True
        )
        self._thread.start()
        return True

    def _backup_thread(self,
                       destination: str,
                       mode: BackupMode,
                       compress: bool,
                       compress_format: CompressionFormat,
                       verify: bool) -> None:
        """Background thread for backup operation"""
        try:
            self._update_status(BackupStatus.PREPARING, "Preparing backup...")

            paths = self.get_source_paths()
            if not paths:
                raise Exception("Plex data directory not found")

            # Create destination directory
            backup_dir = os.path.join(destination, "Plex Media Server")
            os.makedirs(backup_dir, exist_ok=True)

            # Calculate total size
            self.progress.bytes_total = self.estimate_backup_size()

            # Handle based on mode
            if mode == BackupMode.COLD:
                self._cold_backup(paths, backup_dir)
            elif mode == BackupMode.HOT:
                self._hot_backup(paths, backup_dir)
            elif mode == BackupMode.SMART:
                self._smart_backup(paths, backup_dir)
            elif mode == BackupMode.INCREMENTAL:
                self._incremental_backup(paths, backup_dir)
            elif mode == BackupMode.DATABASE_ONLY:
                self._database_backup(paths, backup_dir)

            if self._cancelled:
                self._update_status(BackupStatus.CANCELLED)
                return

            # Verify backup
            if verify and not self._cancelled:
                self._update_status(BackupStatus.VERIFYING, "Verifying backup...")
                self._verify_backup(paths, backup_dir)

            # Compress if requested
            if compress and not self._cancelled:
                self._update_status(BackupStatus.COMPRESSING, "Compressing backup...")
                compressor = CompressionManager()
                archive_path = backup_dir + compressor.get_extension(compress_format)
                compressor.compress_directory(backup_dir, archive_path, compress_format)

            # Create manifest
            self._create_manifest(paths, backup_dir, mode)

            self.progress.end_time = time.time()
            self._update_status(BackupStatus.COMPLETED, "Backup completed successfully")

        except Exception as e:
            self.progress.errors.append(str(e))
            self._update_status(BackupStatus.FAILED, f"Backup failed: {str(e)}")

        finally:
            self._running = False

    def _cold_backup(self, paths: PlexPaths, destination: str) -> None:
        """Perform cold backup (Plex stopped)"""
        plex_was_running = self._is_plex_running()

        if plex_was_running:
            self._update_status(BackupStatus.STOPPING_PLEX, "Stopping Plex...")
            self._stop_plex()
            time.sleep(3)  # Wait for graceful shutdown

        try:
            self._update_status(BackupStatus.COPYING, "Copying files...")
            self._copy_files(paths.data_dir, destination)
        finally:
            if plex_was_running:
                self._update_status(BackupStatus.STARTING_PLEX, "Starting Plex...")
                self._start_plex()

    def _hot_backup(self, paths: PlexPaths, destination: str) -> None:
        """Perform hot backup (Plex running)"""
        self._update_status(BackupStatus.COPYING, "Copying files (hot)...")
        self._copy_files(paths.data_dir, destination)

    def _smart_backup(self, paths: PlexPaths, destination: str) -> None:
        """Perform smart backup (hot copy + cold differential)"""
        # First, hot copy
        self._update_status(BackupStatus.COPYING, "Hot copy phase...")
        self._copy_files(paths.data_dir, destination)

        if self._cancelled:
            return

        # Then, cold differential for databases
        plex_was_running = self._is_plex_running()

        if plex_was_running:
            self._update_status(BackupStatus.STOPPING_PLEX, "Stopping Plex for sync...")
            self._stop_plex()
            time.sleep(3)

        try:
            self._update_status(BackupStatus.COPYING, "Cold sync phase...")
            # Just sync the critical files
            for critical in self.CRITICAL_FILES:
                src = os.path.join(paths.data_dir, critical)
                dst = os.path.join(destination, critical)
                if os.path.exists(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
        finally:
            if plex_was_running:
                self._update_status(BackupStatus.STARTING_PLEX, "Starting Plex...")
                self._start_plex()

    def _incremental_backup(self, paths: PlexPaths, destination: str) -> None:
        """Perform incremental backup (changed files only)"""
        manifest_path = os.path.join(destination, "backup_manifest.json")

        # Load previous manifest if exists
        prev_manifest = None
        if os.path.exists(manifest_path):
            try:
                prev_manifest = BackupManifest.load(manifest_path)
            except Exception:
                pass

        self._update_status(BackupStatus.COPYING, "Copying changed files...")
        self._copy_files(paths.data_dir, destination, incremental=True,
                        prev_manifest=prev_manifest)

    def _database_backup(self, paths: PlexPaths, destination: str) -> None:
        """Backup databases only"""
        plex_was_running = self._is_plex_running()

        if plex_was_running:
            self._update_status(BackupStatus.STOPPING_PLEX, "Stopping Plex...")
            self._stop_plex()
            time.sleep(3)

        try:
            self._update_status(BackupStatus.COPYING, "Copying databases...")

            # Copy databases
            db_dest = os.path.join(destination, "Plug-in Support", "Databases")
            os.makedirs(db_dest, exist_ok=True)

            for db_file in os.listdir(paths.databases_dir):
                if db_file.endswith('.db') or db_file.endswith('.db-wal') or db_file.endswith('.db-shm'):
                    src = os.path.join(paths.databases_dir, db_file)
                    dst = os.path.join(db_dest, db_file)
                    shutil.copy2(src, dst)
                    self.progress.files_done += 1

            # Copy preferences
            if os.path.exists(paths.preferences_file):
                shutil.copy2(paths.preferences_file, destination)

        finally:
            if plex_was_running:
                self._update_status(BackupStatus.STARTING_PLEX, "Starting Plex...")
                self._start_plex()

    def _copy_files(self,
                   source: str,
                   destination: str,
                   incremental: bool = False,
                   prev_manifest: Optional[BackupManifest] = None) -> None:
        """Copy files from source to destination"""
        os_type = self.platform.info.os_type

        # Use robocopy on Windows for better performance
        if os_type == OSType.WINDOWS and not incremental:
            self._robocopy(source, destination)
        else:
            self._python_copy(source, destination, incremental, prev_manifest)

    def _robocopy(self, source: str, destination: str) -> None:
        """Use Windows robocopy for fast copying"""
        exclude_dirs = self.get_excluded_dirs()

        cmd = [
            'robocopy',
            source,
            destination,
            '/MIR',  # Mirror mode
            '/MT:8',  # 8 threads
            '/R:3',  # 3 retries
            '/W:5',  # 5 second wait
            '/NP',  # No progress (we handle it)
            '/NDL',  # No directory list
            '/NFL',  # No file list
            '/NJH',  # No job header
            '/NJS',  # No job summary
            '/XD', *exclude_dirs,  # Exclude directories
            '/XF', '*.tmp', '*.log'  # Exclude files
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Monitor progress
            while process.poll() is None:
                if self._cancelled:
                    process.terminate()
                    return

                # Update progress based on estimated time
                self.progress.bytes_done = min(
                    self.progress.bytes_done + 1024 * 1024,
                    self.progress.bytes_total
                )
                self._notify_progress()
                time.sleep(1)

            # Robocopy returns codes 0-7 for success
            if process.returncode > 7:
                stderr = process.stderr.read()
                raise Exception(f"Robocopy failed: {stderr}")

        except FileNotFoundError:
            # Robocopy not available, fall back to Python copy
            self._python_copy(source, destination)

    def _python_copy(self,
                    source: str,
                    destination: str,
                    incremental: bool = False,
                    prev_manifest: Optional[BackupManifest] = None) -> None:
        """Python-based file copying"""
        for root, dirs, files in os.walk(source):
            if self._cancelled:
                return

            # Skip excluded directories
            dirs[:] = [d for d in dirs if not self._should_exclude(d)]

            # Calculate relative path
            rel_path = os.path.relpath(root, source)
            dest_dir = os.path.join(destination, rel_path)
            os.makedirs(dest_dir, exist_ok=True)

            for file in files:
                if self._cancelled:
                    return

                if self._should_exclude(file):
                    continue

                src_file = os.path.join(root, file)
                dst_file = os.path.join(dest_dir, file)
                rel_file = os.path.join(rel_path, file)

                # For incremental, check if file changed
                if incremental and prev_manifest:
                    if rel_file in prev_manifest.files:
                        prev_info = prev_manifest.files[rel_file]
                        try:
                            stat = os.stat(src_file)
                            if (stat.st_mtime == prev_info.get('mtime') and
                                stat.st_size == prev_info.get('size')):
                                continue
                        except OSError:
                            pass

                # Copy file
                try:
                    self.progress.current_file = file
                    shutil.copy2(src_file, dst_file)
                    self.progress.files_done += 1
                    self.progress.bytes_done += os.path.getsize(src_file)
                    self._notify_progress()
                except (PermissionError, OSError) as e:
                    self.progress.warnings.append(f"Could not copy {file}: {e}")

    def _verify_backup(self, paths: PlexPaths, backup_dir: str) -> bool:
        """Verify backup integrity"""
        # Check critical files exist
        for critical in self.CRITICAL_FILES:
            backup_file = os.path.join(backup_dir, critical)
            if not os.path.exists(backup_file):
                self.progress.errors.append(f"Critical file missing: {critical}")
                return False

        # Verify database integrity
        db_backup = os.path.join(backup_dir, "Plug-in Support", "Databases",
                                "com.plexapp.plugins.library.db")
        if os.path.exists(db_backup):
            try:
                import sqlite3
                conn = sqlite3.connect(f"file:{db_backup}?mode=ro", uri=True)
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                conn.close()

                if result[0] != 'ok':
                    self.progress.warnings.append("Database integrity check warning")
            except Exception as e:
                self.progress.warnings.append(f"Could not verify database: {e}")

        return len(self.progress.errors) == 0

    def _create_manifest(self, paths: PlexPaths, backup_dir: str,
                        mode: BackupMode) -> None:
        """Create backup manifest"""
        manifest = BackupManifest(
            created_at=datetime.now().isoformat(),
            source_platform=self.platform.info.os_type.value,
            source_hostname=self.platform.info.hostname,
            machine_identifier=self.path_finder.get_machine_identifier() or "",
            server_name=self.path_finder.get_server_name() or "",
            backup_mode=mode.value
        )

        # Catalog files
        for root, _, files in os.walk(backup_dir):
            rel_root = os.path.relpath(root, backup_dir)
            for file in files:
                rel_path = os.path.join(rel_root, file)
                full_path = os.path.join(root, file)
                try:
                    stat = os.stat(full_path)
                    manifest.files[rel_path] = {
                        'size': stat.st_size,
                        'mtime': stat.st_mtime
                    }
                    manifest.total_size += stat.st_size
                    manifest.file_count += 1
                except OSError:
                    pass

        manifest.save(os.path.join(backup_dir, "backup_manifest.json"))

    def _is_plex_running(self) -> bool:
        """Check if Plex is running"""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                name = proc.info['name'].lower()
                if 'plex' in name and 'media' in name:
                    return True
        except Exception:
            pass

        return False

    def _stop_plex(self) -> bool:
        """Stop Plex Media Server"""
        commands = self.platform.get_plex_service_commands()
        try:
            subprocess.run(
                commands['stop'],
                shell=True,
                capture_output=True,
                timeout=60
            )
            return True
        except Exception:
            return False

    def _start_plex(self) -> bool:
        """Start Plex Media Server"""
        commands = self.platform.get_plex_service_commands()
        try:
            subprocess.run(
                commands['start'],
                shell=True,
                capture_output=True,
                timeout=60
            )
            return True
        except Exception:
            return False

    def cancel(self) -> None:
        """Cancel backup operation"""
        self._cancelled = True

    @property
    def is_running(self) -> bool:
        """Check if backup is running"""
        return self._running

    def get_available_destinations(self) -> List[Dict[str, Any]]:
        """Get list of available backup destinations (drives)"""
        destinations = []

        if self.platform.info.os_type == OSType.WINDOWS:
            # Windows: Get all drives
            import string
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    try:
                        usage = shutil.disk_usage(drive)
                        destinations.append({
                            'path': drive,
                            'label': f"Drive {letter}:",
                            'total': usage.total,
                            'free': usage.free,
                            'used': usage.used
                        })
                    except OSError:
                        pass
        else:
            # Unix: Check common mount points
            mount_points = ['/mnt', '/media', '/Volumes', '/home', '/']
            checked = set()

            for mount in mount_points:
                if os.path.exists(mount):
                    try:
                        # Get actual mount point
                        stat = os.statvfs(mount)
                        device = os.stat(mount).st_dev

                        if device not in checked:
                            checked.add(device)
                            usage = shutil.disk_usage(mount)
                            destinations.append({
                                'path': mount,
                                'label': mount,
                                'total': usage.total,
                                'free': usage.free,
                                'used': usage.used
                            })
                    except OSError:
                        pass

        return destinations
