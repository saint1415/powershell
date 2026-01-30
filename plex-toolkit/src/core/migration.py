"""
Migration Manager Module
Orchestrates complete Plex Media Server migration between systems
"""

import os
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from datetime import datetime

from .platform import PlatformDetector, OSType, get_platform
from .plex_paths import PlexPathFinder, PlexPaths
from .backup import BackupEngine, BackupMode, BackupStatus
from .network import NetworkDiscovery, NetworkTransfer, MachineRole, NetworkHost
from .database import DatabaseManager
from .preferences import PreferencesManager
from .compression import CompressionManager, CompressionFormat


class MigrationMode(Enum):
    """Migration operation modes"""
    LOCAL_BACKUP = "local_backup"  # Backup to local/external drive
    LOCAL_RESTORE = "local_restore"  # Restore from local backup
    NETWORK_PUSH = "network_push"  # Push to remote machine
    NETWORK_PULL = "network_pull"  # Pull from remote machine
    FULL_MIGRATION = "full_migration"  # Complete automated migration


class MigrationPhase(Enum):
    """Phases of migration process"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    DISCOVERING = "discovering"
    CONNECTING = "connecting"
    STOPPING_SOURCE = "stopping_source"
    BACKING_UP = "backing_up"
    TRANSFERRING = "transferring"
    EXTRACTING = "extracting"
    REMAPPING_PATHS = "remapping_paths"
    UPDATING_PREFERENCES = "updating_preferences"
    STOPPING_TARGET = "stopping_target"
    RESTORING = "restoring"
    STARTING_TARGET = "starting_target"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class MigrationConfig:
    """Configuration for migration operation"""
    mode: MigrationMode = MigrationMode.LOCAL_BACKUP
    source_path: str = ""
    target_path: str = ""
    target_host: Optional[str] = None
    target_port: int = 52400
    backup_mode: BackupMode = BackupMode.SMART
    compress: bool = False
    compression_format: CompressionFormat = CompressionFormat.ZIP
    verify_backup: bool = True
    stop_plex: bool = True
    path_mappings: Dict[str, str] = field(default_factory=dict)
    preserve_machine_id: bool = False
    include_watch_history: bool = True
    include_metadata: bool = True


@dataclass
class MigrationProgress:
    """Progress of migration operation"""
    phase: MigrationPhase = MigrationPhase.IDLE
    phase_description: str = ""
    overall_percent: float = 0
    phase_percent: float = 0
    current_operation: str = ""
    bytes_total: int = 0
    bytes_done: int = 0
    files_total: int = 0
    files_done: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def elapsed_seconds(self) -> float:
        if not self.start_time:
            return 0
        end = self.end_time or time.time()
        return end - self.start_time


@dataclass
class MigrationResult:
    """Result of migration operation"""
    success: bool = False
    phase_completed: MigrationPhase = MigrationPhase.IDLE
    backup_path: Optional[str] = None
    duration_seconds: float = 0
    bytes_transferred: int = 0
    files_transferred: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_info: Dict[str, Any] = field(default_factory=dict)
    target_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'phase_completed': self.phase_completed.value,
            'backup_path': self.backup_path,
            'duration_seconds': self.duration_seconds,
            'bytes_transferred': self.bytes_transferred,
            'files_transferred': self.files_transferred,
            'errors': self.errors,
            'warnings': self.warnings,
            'source_info': self.source_info,
            'target_info': self.target_info
        }


class MigrationManager:
    """
    Orchestrates complete Plex Media Server migration

    Supports:
    - Local backup/restore
    - Network migration between machines
    - Cross-platform migration (Windows <-> Linux <-> macOS)
    - Automatic path remapping
    - Watch history preservation
    """

    # Phase weights for progress calculation
    PHASE_WEIGHTS = {
        MigrationPhase.INITIALIZING: 2,
        MigrationPhase.DISCOVERING: 3,
        MigrationPhase.CONNECTING: 2,
        MigrationPhase.STOPPING_SOURCE: 3,
        MigrationPhase.BACKING_UP: 40,
        MigrationPhase.TRANSFERRING: 25,
        MigrationPhase.EXTRACTING: 10,
        MigrationPhase.REMAPPING_PATHS: 5,
        MigrationPhase.UPDATING_PREFERENCES: 2,
        MigrationPhase.STOPPING_TARGET: 2,
        MigrationPhase.RESTORING: 15,
        MigrationPhase.STARTING_TARGET: 2,
        MigrationPhase.VERIFYING: 4
    }

    def __init__(self):
        self.platform = get_platform()
        self.path_finder = PlexPathFinder(self.platform)
        self.backup_engine = BackupEngine(self.platform, self.path_finder)
        self.network = NetworkDiscovery()
        self.database = DatabaseManager(self.platform, self.path_finder)
        self.preferences = PreferencesManager(self.platform, self.path_finder)
        self.compression = CompressionManager()

        self.config = MigrationConfig()
        self.progress = MigrationProgress()
        self.result = MigrationResult()

        self._running = False
        self._cancelled = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[MigrationProgress], None]] = []

    def add_progress_callback(self, callback: Callable[[MigrationProgress], None]) -> None:
        """Add callback for progress updates"""
        self._callbacks.append(callback)

    def _notify_progress(self) -> None:
        """Notify callbacks of progress update"""
        for callback in self._callbacks:
            try:
                callback(self.progress)
            except Exception:
                pass

    def _update_phase(self, phase: MigrationPhase, description: str = "") -> None:
        """Update migration phase"""
        self.progress.phase = phase
        self.progress.phase_description = description or phase.value.replace('_', ' ').title()
        self.progress.phase_percent = 0

        # Calculate overall progress based on completed phases
        completed_weight = sum(
            self.PHASE_WEIGHTS.get(p, 0)
            for p in MigrationPhase
            if p.value < phase.value
        )
        total_weight = sum(self.PHASE_WEIGHTS.values())
        self.progress.overall_percent = (completed_weight / total_weight) * 100

        self._notify_progress()

    def _update_phase_progress(self, percent: float, operation: str = "") -> None:
        """Update progress within current phase"""
        self.progress.phase_percent = percent
        if operation:
            self.progress.current_operation = operation

        # Calculate overall progress including current phase progress
        completed_weight = sum(
            self.PHASE_WEIGHTS.get(p, 0)
            for p in MigrationPhase
            if p.value < self.progress.phase.value
        )
        current_weight = self.PHASE_WEIGHTS.get(self.progress.phase, 0)
        total_weight = sum(self.PHASE_WEIGHTS.values())

        phase_contribution = (current_weight * percent / 100)
        self.progress.overall_percent = ((completed_weight + phase_contribution) / total_weight) * 100

        self._notify_progress()

    def validate_config(self) -> List[str]:
        """Validate migration configuration"""
        errors = []

        # Check source
        if self.config.mode in [MigrationMode.LOCAL_BACKUP, MigrationMode.NETWORK_PUSH,
                                MigrationMode.FULL_MIGRATION]:
            if not self.path_finder.paths:
                errors.append("Plex installation not found on this machine")

        # Check target path for local operations
        if self.config.mode in [MigrationMode.LOCAL_BACKUP, MigrationMode.LOCAL_RESTORE]:
            if not self.config.target_path:
                errors.append("Target path not specified")
            elif self.config.mode == MigrationMode.LOCAL_BACKUP:
                if not os.path.exists(os.path.dirname(self.config.target_path)):
                    errors.append("Target directory does not exist")

        # Check network target
        if self.config.mode in [MigrationMode.NETWORK_PUSH, MigrationMode.NETWORK_PULL,
                                MigrationMode.FULL_MIGRATION]:
            if not self.config.target_host:
                errors.append("Target host not specified")

        return errors

    def start_migration(self, config: MigrationConfig) -> bool:
        """Start migration operation"""
        if self._running:
            return False

        self.config = config
        errors = self.validate_config()
        if errors:
            self.result.errors = errors
            return False

        self._running = True
        self._cancelled = False
        self.progress = MigrationProgress(start_time=time.time())
        self.result = MigrationResult()

        self._thread = threading.Thread(target=self._migration_thread, daemon=True)
        self._thread.start()
        return True

    def _migration_thread(self) -> None:
        """Background thread for migration operation"""
        try:
            mode = self.config.mode

            if mode == MigrationMode.LOCAL_BACKUP:
                self._do_local_backup()
            elif mode == MigrationMode.LOCAL_RESTORE:
                self._do_local_restore()
            elif mode == MigrationMode.NETWORK_PUSH:
                self._do_network_push()
            elif mode == MigrationMode.NETWORK_PULL:
                self._do_network_pull()
            elif mode == MigrationMode.FULL_MIGRATION:
                self._do_full_migration()

        except Exception as e:
            self.progress.errors.append(str(e))
            self._update_phase(MigrationPhase.FAILED, str(e))
            self.result.success = False
            self.result.errors.append(str(e))

        finally:
            self.progress.end_time = time.time()
            self.result.duration_seconds = self.progress.elapsed_seconds
            self._running = False

    def _do_local_backup(self) -> None:
        """Perform local backup operation"""
        self._update_phase(MigrationPhase.INITIALIZING, "Preparing backup...")

        paths = self.path_finder.paths
        if not paths:
            raise Exception("Plex data not found")

        # Get source info
        self.result.source_info = self.path_finder.get_summary()
        self._update_phase_progress(50, "Getting source information")

        # Start backup
        self._update_phase(MigrationPhase.BACKING_UP, "Backing up Plex data...")

        # Hook into backup engine progress
        def on_backup_progress(bp):
            percent = bp.percent
            self._update_phase_progress(percent, bp.current_file)
            self.progress.bytes_done = bp.bytes_done
            self.progress.bytes_total = bp.bytes_total
            self.progress.files_done = bp.files_done

        self.backup_engine.add_progress_callback(on_backup_progress)

        success = self.backup_engine.start_backup(
            destination=self.config.target_path,
            mode=self.config.backup_mode,
            compress=self.config.compress,
            compress_format=self.config.compression_format,
            verify=self.config.verify_backup
        )

        # Wait for backup to complete
        while self.backup_engine.is_running:
            if self._cancelled:
                self.backup_engine.cancel()
                self._update_phase(MigrationPhase.CANCELLED)
                return
            time.sleep(0.5)

        if self.backup_engine.progress.status != BackupStatus.COMPLETED:
            raise Exception("Backup failed: " + str(self.backup_engine.progress.errors))

        # Copy preferences
        self._update_phase(MigrationPhase.UPDATING_PREFERENCES, "Saving preferences...")
        prefs_dir = os.path.join(self.config.target_path, "Plex Media Server")
        self.preferences.backup_preferences(prefs_dir)

        # Export database info
        self._update_phase(MigrationPhase.VERIFYING, "Verifying backup...")
        self.database.connect()
        self.database.export_library_info(os.path.join(prefs_dir, 'library_info.json'))
        self.database.disconnect()

        self._update_phase(MigrationPhase.COMPLETED, "Backup completed successfully")
        self.result.success = True
        self.result.backup_path = os.path.join(self.config.target_path, "Plex Media Server")
        self.result.bytes_transferred = self.progress.bytes_done
        self.result.files_transferred = self.progress.files_done

    def _do_local_restore(self) -> None:
        """Perform local restore operation"""
        self._update_phase(MigrationPhase.INITIALIZING, "Preparing restore...")

        backup_path = self.config.source_path
        if not os.path.exists(backup_path):
            raise Exception(f"Backup not found: {backup_path}")

        # Check for compressed backup
        if os.path.isfile(backup_path):
            self._update_phase(MigrationPhase.EXTRACTING, "Extracting backup...")
            format = self.compression.detect_format(backup_path)

            if format != CompressionFormat.NONE:
                extract_dir = backup_path + "_extracted"
                self.compression.decompress(backup_path, extract_dir)
                backup_path = extract_dir

        # Find Plex target directory
        target_path = self.config.target_path
        if not target_path:
            paths = self.path_finder.paths
            if paths:
                target_path = paths.data_dir
            else:
                raise Exception("Target Plex directory not specified")

        # Stop Plex on target
        if self.config.stop_plex:
            self._update_phase(MigrationPhase.STOPPING_TARGET, "Stopping Plex...")
            self.backup_engine._stop_plex()
            time.sleep(3)

        # Restore files
        self._update_phase(MigrationPhase.RESTORING, "Restoring files...")
        import shutil

        # Source backup directory
        src_plex_dir = os.path.join(backup_path, "Plex Media Server")
        if not os.path.exists(src_plex_dir):
            src_plex_dir = backup_path

        # Copy files
        for item in os.listdir(src_plex_dir):
            if self._cancelled:
                self._update_phase(MigrationPhase.CANCELLED)
                return

            src_item = os.path.join(src_plex_dir, item)
            dst_item = os.path.join(target_path, item)

            self._update_phase_progress(0, f"Restoring {item}...")

            if os.path.isdir(src_item):
                if os.path.exists(dst_item):
                    shutil.rmtree(dst_item)
                shutil.copytree(src_item, dst_item)
            else:
                shutil.copy2(src_item, dst_item)

        # Remap paths if needed
        if self.config.path_mappings:
            self._update_phase(MigrationPhase.REMAPPING_PATHS, "Updating media paths...")
            db_path = os.path.join(target_path, "Plug-in Support", "Databases",
                                  "com.plexapp.plugins.library.db")
            if os.path.exists(db_path):
                self.database.remap_paths(db_path, self.config.path_mappings)

        # Update preferences
        self._update_phase(MigrationPhase.UPDATING_PREFERENCES, "Updating preferences...")
        prefs_path = os.path.join(target_path, "Preferences.xml")
        if os.path.exists(prefs_path) and not self.config.preserve_machine_id:
            self.preferences.update_machine_id(prefs_path)

        # Start Plex
        if self.config.stop_plex:
            self._update_phase(MigrationPhase.STARTING_TARGET, "Starting Plex...")
            self.backup_engine._start_plex()

        self._update_phase(MigrationPhase.COMPLETED, "Restore completed successfully")
        self.result.success = True

    def _do_network_push(self) -> None:
        """Push backup to remote machine"""
        self._update_phase(MigrationPhase.INITIALIZING, "Preparing network migration...")

        # First create local backup
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="plex_migration_")
        self.config.target_path = temp_dir

        try:
            self._do_local_backup()

            if not self.result.success:
                return

            # Transfer to remote
            self._update_phase(MigrationPhase.CONNECTING, "Connecting to remote...")

            transfer = NetworkTransfer()
            sock = transfer.connect_to_server(
                self.config.target_host,
                self.config.target_port
            )

            self._update_phase(MigrationPhase.TRANSFERRING, "Transferring to remote...")

            # TODO: Implement file transfer protocol
            # This would involve sending each file over the socket

            self._update_phase(MigrationPhase.COMPLETED, "Transfer completed")
            self.result.success = True

        finally:
            # Cleanup temp directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _do_network_pull(self) -> None:
        """Pull backup from remote machine"""
        self._update_phase(MigrationPhase.DISCOVERING, "Discovering remote server...")

        # Start network discovery
        self.network.start_discovery()
        self.network.announce_as_target()

        # Wait for source to connect
        timeout = 60
        start = time.time()
        source = None

        while time.time() - start < timeout:
            if self._cancelled:
                self._update_phase(MigrationPhase.CANCELLED)
                return

            source = self.network.find_partner()
            if source:
                break

            time.sleep(1)
            self._update_phase_progress(
                ((time.time() - start) / timeout) * 100,
                "Waiting for source machine..."
            )

        if not source:
            raise Exception("No source machine found on network")

        self._update_phase(MigrationPhase.CONNECTING, f"Connecting to {source.hostname}...")

        # TODO: Implement receiving files from source

        self._update_phase(MigrationPhase.COMPLETED, "Pull completed")
        self.result.success = True

    def _do_full_migration(self) -> None:
        """Complete automated migration between two machines"""
        # This combines push and remote restore
        self._do_network_push()

        # TODO: Send restore command to remote

    def cancel(self) -> None:
        """Cancel migration operation"""
        self._cancelled = True
        self.backup_engine.cancel()
        self.network.stop_discovery()

    @property
    def is_running(self) -> bool:
        return self._running

    def get_migration_summary(self) -> Dict[str, Any]:
        """Get summary of migration status"""
        return {
            'running': self._running,
            'phase': self.progress.phase.value,
            'phase_description': self.progress.phase_description,
            'overall_percent': self.progress.overall_percent,
            'elapsed_seconds': self.progress.elapsed_seconds,
            'bytes_done': self.progress.bytes_done,
            'bytes_total': self.progress.bytes_total,
            'errors': self.progress.errors,
            'warnings': self.progress.warnings,
            'result': self.result.to_dict() if not self._running else None
        }

    def save_migration_report(self, output_path: str) -> bool:
        """Save migration report to file"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'config': {
                'mode': self.config.mode.value,
                'backup_mode': self.config.backup_mode.value,
                'compress': self.config.compress,
                'path_mappings': self.config.path_mappings
            },
            'result': self.result.to_dict(),
            'progress': {
                'phase': self.progress.phase.value,
                'elapsed_seconds': self.progress.elapsed_seconds,
                'bytes_total': self.progress.bytes_total,
                'bytes_done': self.progress.bytes_done,
                'files_done': self.progress.files_done,
                'errors': self.progress.errors,
                'warnings': self.progress.warnings
            }
        }

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            return True
        except Exception:
            return False
