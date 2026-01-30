#!/usr/bin/env python3
"""
Plex Migration Toolkit CLI
Command-line interface for backup and migration operations
"""

import os
import sys
import argparse
import time
import json
from typing import Optional, List, Dict, Any

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.platform import get_platform, OSType
from core.plex_paths import PlexPathFinder
from core.backup import BackupEngine, BackupMode, BackupStatus
from core.migration import MigrationManager, MigrationConfig, MigrationMode, MigrationPhase
from core.network import NetworkDiscovery, MachineRole
from core.compression import CompressionFormat, CompressionManager
from core.database import DatabaseManager
from core.preferences import PreferencesManager

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class PlexToolkitCLI:
    """
    Command-line interface for Plex Migration Toolkit
    Supports all backup and migration operations
    """

    def __init__(self):
        self.platform = get_platform()
        self.path_finder = PlexPathFinder(self.platform)
        self.backup_engine = BackupEngine(self.platform, self.path_finder)
        self.migration = MigrationManager()
        self.network = NetworkDiscovery()
        self.database = DatabaseManager(self.platform, self.path_finder)
        self.preferences = PreferencesManager(self.platform, self.path_finder)

        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

    def print(self, message: str, style: str = None) -> None:
        """Print message with optional styling"""
        if self.console and style:
            self.console.print(message, style=style)
        else:
            print(message)

    def print_header(self) -> None:
        """Print application header"""
        header = """
╔══════════════════════════════════════════════════════════════╗
║           Plex Migration Toolkit v2.0.0                      ║
║     Cross-platform Backup & Migration for Plex Media Server  ║
╚══════════════════════════════════════════════════════════════╝
        """
        if self.console:
            self.console.print(Panel(header.strip(), style="bold blue"))
        else:
            print(header)

    def print_status(self) -> None:
        """Print system status"""
        info = self.platform.info
        paths = self.path_finder.paths

        if self.console:
            table = Table(title="System Status")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Platform", f"{info.os_name} {info.os_version}")
            table.add_row("Architecture", info.architecture.value)
            table.add_row("Admin/Root", "Yes" if info.is_admin else "No")

            if paths:
                table.add_row("Plex Data", paths.data_dir)
                table.add_row("Install Type", paths.install_type.value)
                table.add_row("Server Name", self.path_finder.get_server_name() or "Unknown")

                size = self.backup_engine.estimate_backup_size()
                table.add_row("Data Size", self.path_finder.format_size(size))
            else:
                table.add_row("Plex Data", "[red]Not Found[/red]")

            self.console.print(table)
        else:
            print(f"Platform: {info.os_name} {info.os_version}")
            print(f"Architecture: {info.architecture.value}")
            print(f"Admin/Root: {'Yes' if info.is_admin else 'No'}")

            if paths:
                print(f"Plex Data: {paths.data_dir}")
                print(f"Install Type: {paths.install_type.value}")
                print(f"Server Name: {self.path_finder.get_server_name() or 'Unknown'}")
                size = self.backup_engine.estimate_backup_size()
                print(f"Data Size: {self.path_finder.format_size(size)}")
            else:
                print("Plex Data: Not Found")

    def do_backup(self,
                 destination: str,
                 mode: str = "smart",
                 compress: bool = False,
                 compress_format: str = "zip",
                 verify: bool = True,
                 quiet: bool = False) -> bool:
        """
        Perform backup operation

        Args:
            destination: Backup destination path
            mode: Backup mode (hot, cold, smart, incremental, database_only)
            compress: Whether to compress backup
            compress_format: Compression format
            verify: Verify backup after completion
            quiet: Suppress progress output
        """
        # Validate
        if not self.path_finder.paths:
            self.print("Error: Plex data not found", "red")
            return False

        # Map mode
        mode_map = {
            'hot': BackupMode.HOT,
            'cold': BackupMode.COLD,
            'smart': BackupMode.SMART,
            'incremental': BackupMode.INCREMENTAL,
            'database_only': BackupMode.DATABASE_ONLY
        }
        backup_mode = mode_map.get(mode, BackupMode.SMART)

        # Map compression
        format_map = {
            'zip': CompressionFormat.ZIP,
            'tar.gz': CompressionFormat.TAR_GZ,
            'tar.xz': CompressionFormat.TAR_XZ,
            '7z': CompressionFormat.SEVEN_ZIP
        }
        comp_format = format_map.get(compress_format.lower(), CompressionFormat.ZIP)

        if not quiet:
            self.print(f"Starting {mode} backup to {destination}...", "blue")

        # Progress tracking
        if RICH_AVAILABLE and not quiet:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("Backing up...", total=100)

                def on_progress(bp):
                    progress.update(task,
                                   completed=bp.percent,
                                   description=f"[cyan]{bp.phase}[/cyan] {bp.current_file[:30]}")

                self.backup_engine.add_progress_callback(on_progress)

                self.backup_engine.start_backup(
                    destination=destination,
                    mode=backup_mode,
                    compress=compress,
                    compress_format=comp_format,
                    verify=verify
                )

                while self.backup_engine.is_running:
                    time.sleep(0.5)

        else:
            def on_progress(bp):
                if not quiet:
                    print(f"\r{bp.phase}: {bp.percent:.1f}% - {bp.current_file[:40]}", end="")

            self.backup_engine.add_progress_callback(on_progress)

            self.backup_engine.start_backup(
                destination=destination,
                mode=backup_mode,
                compress=compress,
                compress_format=comp_format,
                verify=verify
            )

            while self.backup_engine.is_running:
                time.sleep(0.5)

            if not quiet:
                print()

        # Result
        status = self.backup_engine.progress.status
        if status == BackupStatus.COMPLETED:
            if not quiet:
                self.print("Backup completed successfully!", "green")
            return True
        else:
            self.print(f"Backup failed: {self.backup_engine.progress.errors}", "red")
            return False

    def do_restore(self,
                  source: str,
                  target: Optional[str] = None,
                  path_mappings: Optional[Dict[str, str]] = None,
                  preserve_id: bool = False,
                  stop_plex: bool = True,
                  quiet: bool = False) -> bool:
        """
        Perform restore operation

        Args:
            source: Backup source path
            target: Target Plex data path (auto-detect if not specified)
            path_mappings: Path remapping dictionary
            preserve_id: Preserve machine identifier
            stop_plex: Stop Plex before restore
            quiet: Suppress progress output
        """
        if not os.path.exists(source):
            self.print(f"Error: Source not found: {source}", "red")
            return False

        if not quiet:
            self.print(f"Starting restore from {source}...", "blue")

        config = MigrationConfig(
            mode=MigrationMode.LOCAL_RESTORE,
            source_path=source,
            target_path=target or (self.path_finder.paths.data_dir if self.path_finder.paths else ""),
            path_mappings=path_mappings or {},
            preserve_machine_id=preserve_id,
            stop_plex=stop_plex
        )

        if RICH_AVAILABLE and not quiet:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("Restoring...", total=100)

                def on_progress(mp):
                    progress.update(task,
                                   completed=mp.overall_percent,
                                   description=f"[cyan]{mp.phase_description}[/cyan]")

                self.migration.add_progress_callback(on_progress)
                self.migration.start_migration(config)

                while self.migration.is_running:
                    time.sleep(0.5)
        else:
            def on_progress(mp):
                if not quiet:
                    print(f"\r{mp.phase_description}: {mp.overall_percent:.1f}%", end="")

            self.migration.add_progress_callback(on_progress)
            self.migration.start_migration(config)

            while self.migration.is_running:
                time.sleep(0.5)

            if not quiet:
                print()

        if self.migration.progress.phase == MigrationPhase.COMPLETED:
            if not quiet:
                self.print("Restore completed successfully!", "green")
            return True
        else:
            self.print(f"Restore failed: {self.migration.progress.errors}", "red")
            return False

    def do_discover(self, timeout: int = 30) -> List[Dict]:
        """
        Discover Plex servers on network

        Args:
            timeout: Discovery timeout in seconds

        Returns:
            List of discovered hosts
        """
        self.print("Discovering Plex servers on network...", "blue")

        self.network.start_discovery()

        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Scanning...", total=timeout)

                for i in range(timeout):
                    progress.update(task, completed=i + 1)
                    time.sleep(1)

        else:
            for i in range(timeout):
                print(f"\rScanning... {i + 1}/{timeout}s", end="")
                time.sleep(1)
            print()

        self.network.stop_discovery()

        hosts = self.network.get_discovered_hosts()

        if self.console:
            table = Table(title="Discovered Hosts")
            table.add_column("IP", style="cyan")
            table.add_column("Hostname")
            table.add_column("Server Name")
            table.add_column("Platform")
            table.add_column("Toolkit")

            for host in hosts:
                table.add_row(
                    host.ip,
                    host.hostname,
                    host.server_name or "-",
                    host.platform or "-",
                    "Yes" if host.toolkit_port else "No"
                )

            self.console.print(table)
        else:
            for host in hosts:
                print(f"{host.ip} - {host.hostname} - {host.server_name or 'Unknown'}")

        return [h.to_dict() for h in hosts]

    def do_info(self, output_file: Optional[str] = None) -> Dict:
        """
        Get Plex installation information

        Args:
            output_file: Optional file to write JSON info

        Returns:
            Information dictionary
        """
        info = {
            'platform': self.platform.info.to_dict(),
            'plex': None,
            'database': None,
            'preferences': None
        }

        if self.path_finder.paths:
            info['plex'] = self.path_finder.get_summary()

            self.database.connect()
            info['database'] = {
                'stats': {
                    'main_db_size': self.database.get_stats().main_db_size,
                    'blobs_db_size': self.database.get_stats().blobs_db_size,
                    'total_libraries': self.database.get_stats().total_libraries,
                    'total_items': self.database.get_stats().total_items,
                    'total_watched': self.database.get_stats().total_watched
                },
                'integrity': self.database.verify_integrity()
            }
            self.database.disconnect()

            info['preferences'] = self.preferences.get_server_info()

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(info, f, indent=2)
            self.print(f"Info written to {output_file}", "green")

        if self.console:
            self.console.print_json(data=info)
        else:
            print(json.dumps(info, indent=2))

        return info

    def do_export_prefs(self, output_dir: str) -> bool:
        """Export Plex preferences"""
        if self.preferences.backup_preferences(output_dir):
            self.print(f"Preferences exported to {output_dir}", "green")
            return True
        else:
            self.print("Failed to export preferences", "red")
            return False

    def do_export_library(self, output_file: str) -> bool:
        """Export library information"""
        self.database.connect()
        result = self.database.export_library_info(output_file)
        self.database.disconnect()

        if result:
            self.print(f"Library info exported to {output_file}", "green")
            return True
        else:
            self.print("Failed to export library info", "red")
            return False


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        prog='plex-toolkit',
        description='Plex Migration Toolkit - Cross-platform backup and migration tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  plex-toolkit status                     Show system and Plex status
  plex-toolkit backup /mnt/backup         Backup to specified location
  plex-toolkit backup -m cold /mnt/backup Cold backup (stops Plex)
  plex-toolkit backup -c zip /mnt/backup  Backup with ZIP compression
  plex-toolkit restore /mnt/backup        Restore from backup
  plex-toolkit discover                   Find Plex servers on network
  plex-toolkit info -o info.json          Export system info to JSON
        """
    )

    parser.add_argument('--version', action='version', version='Plex Migration Toolkit v2.0.0')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress progress output')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show system and Plex status')

    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup Plex data')
    backup_parser.add_argument('destination', help='Backup destination path')
    backup_parser.add_argument('-m', '--mode', choices=['hot', 'cold', 'smart', 'incremental', 'database_only'],
                               default='smart', help='Backup mode (default: smart)')
    backup_parser.add_argument('-c', '--compress', choices=['none', 'zip', 'tar.gz', 'tar.xz', '7z'],
                               default='none', help='Compression format')
    backup_parser.add_argument('--no-verify', action='store_true', help='Skip backup verification')

    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore Plex data from backup')
    restore_parser.add_argument('source', help='Backup source path')
    restore_parser.add_argument('-t', '--target', help='Target Plex data path')
    restore_parser.add_argument('-r', '--remap', action='append', nargs=2, metavar=('OLD', 'NEW'),
                                help='Path remapping (can be specified multiple times)')
    restore_parser.add_argument('--preserve-id', action='store_true', help='Preserve machine identifier')
    restore_parser.add_argument('--no-stop', action='store_true', help="Don't stop Plex before restore")

    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover Plex servers on network')
    discover_parser.add_argument('-t', '--timeout', type=int, default=30, help='Discovery timeout in seconds')

    # Info command
    info_parser = subparsers.add_parser('info', help='Show detailed Plex information')
    info_parser.add_argument('-o', '--output', help='Output JSON file')

    # Export commands
    export_parser = subparsers.add_parser('export', help='Export Plex data')
    export_subparsers = export_parser.add_subparsers(dest='export_type')

    prefs_parser = export_subparsers.add_parser('preferences', help='Export preferences')
    prefs_parser.add_argument('output_dir', help='Output directory')

    library_parser = export_subparsers.add_parser('library', help='Export library info')
    library_parser.add_argument('output_file', help='Output JSON file')

    # GUI command
    gui_parser = subparsers.add_parser('gui', help='Launch graphical interface')

    return parser


def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()

    cli = PlexToolkitCLI()

    if not args.command:
        cli.print_header()
        cli.print_status()
        return

    if args.command == 'status':
        cli.print_header()
        cli.print_status()

    elif args.command == 'backup':
        compress = args.compress != 'none'
        compress_format = args.compress if compress else 'zip'

        success = cli.do_backup(
            destination=args.destination,
            mode=args.mode,
            compress=compress,
            compress_format=compress_format,
            verify=not args.no_verify,
            quiet=getattr(args, 'quiet', False)
        )
        sys.exit(0 if success else 1)

    elif args.command == 'restore':
        path_mappings = {}
        if args.remap:
            for old, new in args.remap:
                path_mappings[old] = new

        success = cli.do_restore(
            source=args.source,
            target=args.target,
            path_mappings=path_mappings,
            preserve_id=args.preserve_id,
            stop_plex=not args.no_stop,
            quiet=getattr(args, 'quiet', False)
        )
        sys.exit(0 if success else 1)

    elif args.command == 'discover':
        cli.do_discover(timeout=args.timeout)

    elif args.command == 'info':
        cli.do_info(output_file=args.output)

    elif args.command == 'export':
        if args.export_type == 'preferences':
            success = cli.do_export_prefs(args.output_dir)
        elif args.export_type == 'library':
            success = cli.do_export_library(args.output_file)
        else:
            parser.print_help()
            sys.exit(1)
        sys.exit(0 if success else 1)

    elif args.command == 'gui':
        try:
            from gui.main_window import PlexToolkitGUI
            app = PlexToolkitGUI()
            app.run()
        except ImportError as e:
            cli.print(f"GUI not available: {e}", "red")
            cli.print("Install tkinter or run without GUI", "yellow")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
