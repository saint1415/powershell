"""
Main GUI Window for Plex Migration Toolkit
Cross-platform tkinter-based interface
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable
import webbrowser

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.platform import get_platform, OSType
from core.plex_paths import PlexPathFinder
from core.backup import BackupEngine, BackupMode, BackupStatus
from core.migration import MigrationManager, MigrationConfig, MigrationMode, MigrationPhase
from core.network import NetworkDiscovery, MachineRole
from core.compression import CompressionFormat


class PlexToolkitGUI:
    """
    Main application window for Plex Migration Toolkit
    Provides cross-platform GUI for backup and migration operations
    """

    # Color scheme (dark theme)
    COLORS = {
        'bg': '#1a1a2e',
        'bg_light': '#16213e',
        'bg_dark': '#0f0f1a',
        'accent': '#e94560',
        'accent_hover': '#ff6b6b',
        'text': '#ffffff',
        'text_dim': '#a0a0a0',
        'success': '#4ecca3',
        'warning': '#ffc107',
        'error': '#e94560',
        'border': '#2d2d44'
    }

    def __init__(self):
        self.platform = get_platform()
        self.path_finder = PlexPathFinder(self.platform)
        self.backup_engine = BackupEngine(self.platform, self.path_finder)
        self.migration = MigrationManager()
        self.network = NetworkDiscovery()

        self.root: Optional[tk.Tk] = None
        self._setup_window()
        self._create_styles()
        self._create_widgets()
        self._refresh_status()

    def _setup_window(self) -> None:
        """Initialize main window"""
        self.root = tk.Tk()
        self.root.title("Plex Migration Toolkit v2.0")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # Set icon if available
        try:
            if self.platform.info.os_type == OSType.WINDOWS:
                self.root.iconbitmap('assets/icon.ico')
            else:
                icon = tk.PhotoImage(file='assets/icon.png')
                self.root.iconphoto(True, icon)
        except:
            pass

        # Configure colors
        self.root.configure(bg=self.COLORS['bg'])

        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_styles(self) -> None:
        """Create custom ttk styles"""
        style = ttk.Style()

        # Use clam theme as base (works best for customization)
        style.theme_use('clam')

        # Configure colors
        style.configure('.',
                       background=self.COLORS['bg'],
                       foreground=self.COLORS['text'],
                       fieldbackground=self.COLORS['bg_light'])

        # Frame styles
        style.configure('TFrame', background=self.COLORS['bg'])
        style.configure('Card.TFrame', background=self.COLORS['bg_light'])

        # Label styles
        style.configure('TLabel',
                       background=self.COLORS['bg'],
                       foreground=self.COLORS['text'])
        style.configure('Header.TLabel',
                       font=('Segoe UI', 14, 'bold'),
                       foreground=self.COLORS['accent'])
        style.configure('Title.TLabel',
                       font=('Segoe UI', 24, 'bold'),
                       foreground=self.COLORS['text'])
        style.configure('Status.TLabel',
                       font=('Segoe UI', 10),
                       foreground=self.COLORS['text_dim'])
        style.configure('Success.TLabel',
                       foreground=self.COLORS['success'])
        style.configure('Error.TLabel',
                       foreground=self.COLORS['error'])

        # Button styles
        style.configure('TButton',
                       background=self.COLORS['bg_light'],
                       foreground=self.COLORS['text'],
                       padding=(20, 10),
                       font=('Segoe UI', 10))
        style.map('TButton',
                 background=[('active', self.COLORS['border']),
                            ('pressed', self.COLORS['bg_dark'])])

        style.configure('Accent.TButton',
                       background=self.COLORS['accent'],
                       foreground=self.COLORS['text'],
                       padding=(20, 10),
                       font=('Segoe UI', 10, 'bold'))
        style.map('Accent.TButton',
                 background=[('active', self.COLORS['accent_hover']),
                            ('pressed', self.COLORS['accent'])])

        # Progress bar
        style.configure('TProgressbar',
                       background=self.COLORS['accent'],
                       troughcolor=self.COLORS['bg_dark'],
                       borderwidth=0,
                       lightcolor=self.COLORS['accent'],
                       darkcolor=self.COLORS['accent'])

        # Notebook (tabs)
        style.configure('TNotebook',
                       background=self.COLORS['bg'],
                       borderwidth=0)
        style.configure('TNotebook.Tab',
                       background=self.COLORS['bg_light'],
                       foreground=self.COLORS['text'],
                       padding=(20, 10),
                       font=('Segoe UI', 10))
        style.map('TNotebook.Tab',
                 background=[('selected', self.COLORS['accent'])],
                 foreground=[('selected', self.COLORS['text'])])

        # Combobox
        style.configure('TCombobox',
                       fieldbackground=self.COLORS['bg_light'],
                       background=self.COLORS['bg_light'],
                       foreground=self.COLORS['text'],
                       arrowcolor=self.COLORS['text'])

        # Entry
        style.configure('TEntry',
                       fieldbackground=self.COLORS['bg_light'],
                       foreground=self.COLORS['text'],
                       insertcolor=self.COLORS['text'])

        # Radiobutton
        style.configure('TRadiobutton',
                       background=self.COLORS['bg'],
                       foreground=self.COLORS['text'])

        # Checkbutton
        style.configure('TCheckbutton',
                       background=self.COLORS['bg'],
                       foreground=self.COLORS['text'])

    def _create_widgets(self) -> None:
        """Create all GUI widgets"""
        # Main container
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        self._create_header()

        # Status bar
        self._create_status_bar()

        # Tab notebook
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        # Create tabs
        self._create_backup_tab()
        self._create_restore_tab()
        self._create_network_tab()
        self._create_settings_tab()

        # Progress section (below tabs)
        self._create_progress_section()

    def _create_header(self) -> None:
        """Create header section"""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        # Title
        title = ttk.Label(header_frame,
                         text="Plex Migration Toolkit",
                         style='Title.TLabel')
        title.pack(side=tk.LEFT)

        # Version
        version = ttk.Label(header_frame,
                           text="v2.0.0",
                           style='Status.TLabel')
        version.pack(side=tk.LEFT, padx=(10, 0), pady=(15, 0))

        # Help button
        help_btn = ttk.Button(header_frame,
                             text="?",
                             width=3,
                             command=self._show_help)
        help_btn.pack(side=tk.RIGHT)

    def _create_status_bar(self) -> None:
        """Create status information bar"""
        status_frame = ttk.Frame(self.main_frame, style='Card.TFrame', padding=15)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        # Platform info
        platform_frame = ttk.Frame(status_frame, style='Card.TFrame')
        platform_frame.pack(side=tk.LEFT)

        ttk.Label(platform_frame,
                 text="Platform:",
                 style='Status.TLabel').pack(side=tk.LEFT)
        self.platform_label = ttk.Label(platform_frame,
                                        text=str(self.platform),
                                        style='TLabel')
        self.platform_label.pack(side=tk.LEFT, padx=(5, 20))

        # Plex status
        plex_frame = ttk.Frame(status_frame, style='Card.TFrame')
        plex_frame.pack(side=tk.LEFT)

        ttk.Label(plex_frame,
                 text="Plex Data:",
                 style='Status.TLabel').pack(side=tk.LEFT)
        self.plex_status_label = ttk.Label(plex_frame,
                                           text="Checking...",
                                           style='TLabel')
        self.plex_status_label.pack(side=tk.LEFT, padx=(5, 20))

        # Data size
        size_frame = ttk.Frame(status_frame, style='Card.TFrame')
        size_frame.pack(side=tk.LEFT)

        ttk.Label(size_frame,
                 text="Size:",
                 style='Status.TLabel').pack(side=tk.LEFT)
        self.size_label = ttk.Label(size_frame,
                                    text="--",
                                    style='TLabel')
        self.size_label.pack(side=tk.LEFT, padx=(5, 0))

        # Refresh button
        refresh_btn = ttk.Button(status_frame,
                                text="Refresh",
                                command=self._refresh_status)
        refresh_btn.pack(side=tk.RIGHT)

    def _create_backup_tab(self) -> None:
        """Create backup tab"""
        backup_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(backup_frame, text="Backup")

        # Destination selection
        dest_frame = ttk.LabelFrame(backup_frame, text="Destination", padding=15)
        dest_frame.pack(fill=tk.X, pady=(0, 15))

        # Destination drive/path
        path_frame = ttk.Frame(dest_frame)
        path_frame.pack(fill=tk.X)

        ttk.Label(path_frame, text="Backup Location:").pack(side=tk.LEFT)

        self.dest_combo = ttk.Combobox(path_frame, width=50, state='readonly')
        self.dest_combo.pack(side=tk.LEFT, padx=(10, 10))

        browse_btn = ttk.Button(path_frame,
                               text="Browse...",
                               command=self._browse_destination)
        browse_btn.pack(side=tk.LEFT)

        # Populate destinations
        self._populate_destinations()

        # Backup mode selection
        mode_frame = ttk.LabelFrame(backup_frame, text="Backup Mode", padding=15)
        mode_frame.pack(fill=tk.X, pady=(0, 15))

        self.backup_mode = tk.StringVar(value="smart")

        modes = [
            ("Hot Copy", "hot", "Backup while Plex is running (faster, may miss locked files)"),
            ("Cold Copy", "cold", "Stop Plex for backup (most reliable, requires restart)"),
            ("Smart Sync", "smart", "Hot copy + cold sync for databases (recommended)"),
            ("Incremental", "incremental", "Only backup changed files since last backup"),
            ("Database Only", "database_only", "Backup databases and preferences only")
        ]

        for text, value, desc in modes:
            mode_row = ttk.Frame(mode_frame)
            mode_row.pack(fill=tk.X, pady=2)

            rb = ttk.Radiobutton(mode_row,
                                text=text,
                                variable=self.backup_mode,
                                value=value)
            rb.pack(side=tk.LEFT)

            ttk.Label(mode_row,
                     text=f"- {desc}",
                     style='Status.TLabel').pack(side=tk.LEFT, padx=(10, 0))

        # Options
        options_frame = ttk.LabelFrame(backup_frame, text="Options", padding=15)
        options_frame.pack(fill=tk.X, pady=(0, 15))

        # Compression
        comp_frame = ttk.Frame(options_frame)
        comp_frame.pack(fill=tk.X, pady=5)

        self.compress_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(comp_frame,
                       text="Compress backup",
                       variable=self.compress_var,
                       command=self._toggle_compression).pack(side=tk.LEFT)

        self.compress_format = ttk.Combobox(comp_frame,
                                           values=['ZIP', 'TAR.GZ', 'TAR.XZ', '7Z'],
                                           width=10,
                                           state='disabled')
        self.compress_format.set('ZIP')
        self.compress_format.pack(side=tk.LEFT, padx=(10, 0))

        # Verify
        self.verify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame,
                       text="Verify backup after completion",
                       variable=self.verify_var).pack(anchor=tk.W, pady=5)

        # Start button
        btn_frame = ttk.Frame(backup_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.backup_btn = ttk.Button(btn_frame,
                                    text="Start Backup",
                                    style='Accent.TButton',
                                    command=self._start_backup)
        self.backup_btn.pack(side=tk.RIGHT)

    def _create_restore_tab(self) -> None:
        """Create restore tab"""
        restore_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(restore_frame, text="Restore")

        # Source selection
        source_frame = ttk.LabelFrame(restore_frame, text="Backup Source", padding=15)
        source_frame.pack(fill=tk.X, pady=(0, 15))

        path_frame = ttk.Frame(source_frame)
        path_frame.pack(fill=tk.X)

        ttk.Label(path_frame, text="Backup Location:").pack(side=tk.LEFT)

        self.restore_source_entry = ttk.Entry(path_frame, width=50)
        self.restore_source_entry.pack(side=tk.LEFT, padx=(10, 10))

        browse_btn = ttk.Button(path_frame,
                               text="Browse...",
                               command=self._browse_restore_source)
        browse_btn.pack(side=tk.LEFT)

        # Backup info
        info_frame = ttk.LabelFrame(restore_frame, text="Backup Information", padding=15)
        info_frame.pack(fill=tk.X, pady=(0, 15))

        self.backup_info_label = ttk.Label(info_frame,
                                          text="Select a backup to see details",
                                          style='Status.TLabel')
        self.backup_info_label.pack(anchor=tk.W)

        # Path remapping
        remap_frame = ttk.LabelFrame(restore_frame, text="Path Remapping", padding=15)
        remap_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(remap_frame,
                 text="If your media paths have changed, add remapping rules:",
                 style='Status.TLabel').pack(anchor=tk.W)

        # Remap entries
        remap_entries = ttk.Frame(remap_frame)
        remap_entries.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(remap_entries, text="Old Path:").grid(row=0, column=0, padx=5)
        self.remap_old_entry = ttk.Entry(remap_entries, width=30)
        self.remap_old_entry.grid(row=0, column=1, padx=5)

        ttk.Label(remap_entries, text="New Path:").grid(row=0, column=2, padx=5)
        self.remap_new_entry = ttk.Entry(remap_entries, width=30)
        self.remap_new_entry.grid(row=0, column=3, padx=5)

        ttk.Button(remap_entries,
                  text="Add",
                  command=self._add_path_mapping).grid(row=0, column=4, padx=5)

        # Remap list
        self.remap_list = tk.Listbox(remap_frame, height=3)
        self.remap_list.pack(fill=tk.X, pady=(10, 0))

        # Options
        options_frame = ttk.LabelFrame(restore_frame, text="Options", padding=15)
        options_frame.pack(fill=tk.X, pady=(0, 15))

        self.preserve_id_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame,
                       text="Preserve machine identifier (for same-machine restore)",
                       variable=self.preserve_id_var).pack(anchor=tk.W)

        self.stop_plex_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame,
                       text="Stop Plex before restore",
                       variable=self.stop_plex_var).pack(anchor=tk.W)

        # Start button
        btn_frame = ttk.Frame(restore_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.restore_btn = ttk.Button(btn_frame,
                                     text="Start Restore",
                                     style='Accent.TButton',
                                     command=self._start_restore)
        self.restore_btn.pack(side=tk.RIGHT)

    def _create_network_tab(self) -> None:
        """Create network migration tab"""
        network_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(network_frame, text="Network Migration")

        # Role selection
        role_frame = ttk.LabelFrame(network_frame, text="This Machine Is", padding=15)
        role_frame.pack(fill=tk.X, pady=(0, 15))

        self.role_var = tk.StringVar(value="source")

        roles = [
            ("Source (Old Server)", "source", "This machine has the Plex data to migrate"),
            ("Target (New Server)", "target", "This machine will receive the Plex data")
        ]

        for text, value, desc in roles:
            role_row = ttk.Frame(role_frame)
            role_row.pack(fill=tk.X, pady=5)

            ttk.Radiobutton(role_row,
                           text=text,
                           variable=self.role_var,
                           value=value).pack(side=tk.LEFT)

            ttk.Label(role_row,
                     text=f"- {desc}",
                     style='Status.TLabel').pack(side=tk.LEFT, padx=(10, 0))

        # Discovery
        discovery_frame = ttk.LabelFrame(network_frame,
                                        text="Network Discovery",
                                        padding=15)
        discovery_frame.pack(fill=tk.X, pady=(0, 15))

        # Local info
        local_frame = ttk.Frame(discovery_frame)
        local_frame.pack(fill=tk.X)

        ttk.Label(local_frame, text="Local IP:").pack(side=tk.LEFT)
        self.local_ip_label = ttk.Label(local_frame, text="--")
        self.local_ip_label.pack(side=tk.LEFT, padx=(10, 30))

        ttk.Label(local_frame, text="Hostname:").pack(side=tk.LEFT)
        self.hostname_label = ttk.Label(local_frame,
                                        text=self.platform.info.hostname)
        self.hostname_label.pack(side=tk.LEFT, padx=(10, 0))

        # Discovered hosts
        ttk.Label(discovery_frame,
                 text="Discovered Machines:",
                 style='Header.TLabel').pack(anchor=tk.W, pady=(15, 5))

        self.hosts_listbox = tk.Listbox(discovery_frame, height=5)
        self.hosts_listbox.pack(fill=tk.X)

        # Discovery controls
        disc_btn_frame = ttk.Frame(discovery_frame)
        disc_btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.discover_btn = ttk.Button(disc_btn_frame,
                                      text="Start Discovery",
                                      command=self._toggle_discovery)
        self.discover_btn.pack(side=tk.LEFT)

        self.connect_btn = ttk.Button(disc_btn_frame,
                                     text="Connect",
                                     state='disabled',
                                     command=self._connect_to_host)
        self.connect_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Manual connection
        manual_frame = ttk.LabelFrame(network_frame, text="Manual Connection", padding=15)
        manual_frame.pack(fill=tk.X, pady=(0, 15))

        manual_row = ttk.Frame(manual_frame)
        manual_row.pack(fill=tk.X)

        ttk.Label(manual_row, text="Host:").pack(side=tk.LEFT)
        self.manual_host_entry = ttk.Entry(manual_row, width=30)
        self.manual_host_entry.pack(side=tk.LEFT, padx=(10, 10))

        ttk.Label(manual_row, text="Port:").pack(side=tk.LEFT)
        self.manual_port_entry = ttk.Entry(manual_row, width=8)
        self.manual_port_entry.insert(0, "52400")
        self.manual_port_entry.pack(side=tk.LEFT, padx=(10, 10))

        ttk.Button(manual_row,
                  text="Connect",
                  command=self._manual_connect).pack(side=tk.LEFT)

        # Start button
        btn_frame = ttk.Frame(network_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.network_btn = ttk.Button(btn_frame,
                                     text="Start Migration",
                                     style='Accent.TButton',
                                     state='disabled',
                                     command=self._start_network_migration)
        self.network_btn.pack(side=tk.RIGHT)

    def _create_settings_tab(self) -> None:
        """Create settings tab"""
        settings_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(settings_frame, text="Settings")

        # System info
        info_frame = ttk.LabelFrame(settings_frame, text="System Information", padding=15)
        info_frame.pack(fill=tk.X, pady=(0, 15))

        info = self.platform.info

        info_text = f"""
Operating System: {info.os_name} {info.os_version}
Architecture: {info.architecture.value}
Python Version: {info.python_version}
Admin/Root: {'Yes' if info.is_admin else 'No'}
Container: {info.container_type.value}
        """

        ttk.Label(info_frame, text=info_text.strip()).pack(anchor=tk.W)

        # Plex info
        plex_frame = ttk.LabelFrame(settings_frame, text="Plex Information", padding=15)
        plex_frame.pack(fill=tk.X, pady=(0, 15))

        paths = self.path_finder.paths
        if paths:
            plex_text = f"""
Data Directory: {paths.data_dir}
Install Type: {paths.install_type.value}
Server Name: {self.path_finder.get_server_name() or 'Unknown'}
Machine ID: {self.path_finder.get_machine_identifier() or 'Unknown'}
            """
        else:
            plex_text = "Plex installation not found"

        ttk.Label(plex_frame, text=plex_text.strip()).pack(anchor=tk.W)

        # Actions
        actions_frame = ttk.LabelFrame(settings_frame, text="Actions", padding=15)
        actions_frame.pack(fill=tk.X, pady=(0, 15))

        btn_row = ttk.Frame(actions_frame)
        btn_row.pack(fill=tk.X)

        ttk.Button(btn_row,
                  text="Open Plex Data Folder",
                  command=self._open_plex_folder).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(btn_row,
                  text="Export Preferences",
                  command=self._export_preferences).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(btn_row,
                  text="Export Library Info",
                  command=self._export_library_info).pack(side=tk.LEFT)

        # About
        about_frame = ttk.LabelFrame(settings_frame, text="About", padding=15)
        about_frame.pack(fill=tk.X, pady=(0, 15))

        about_text = """
Plex Migration Toolkit v2.0.0
Cross-platform backup and migration tool for Plex Media Server

GitHub: github.com/saint1415/powershell

This tool is not affiliated with Plex Inc.
        """

        ttk.Label(about_frame, text=about_text.strip()).pack(anchor=tk.W)

        ttk.Button(about_frame,
                  text="View on GitHub",
                  command=lambda: webbrowser.open("https://github.com/saint1415/powershell")).pack(anchor=tk.W, pady=(10, 0))

    def _create_progress_section(self) -> None:
        """Create progress section at bottom"""
        progress_frame = ttk.Frame(self.main_frame, padding=(0, 20, 0, 0))
        progress_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Status text
        self.progress_status = ttk.Label(progress_frame,
                                         text="Ready",
                                         style='Status.TLabel')
        self.progress_status.pack(anchor=tk.W)

        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame,
                                           mode='determinate',
                                           maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))

        # Details
        details_frame = ttk.Frame(progress_frame)
        details_frame.pack(fill=tk.X, pady=(5, 0))

        self.progress_details = ttk.Label(details_frame,
                                         text="",
                                         style='Status.TLabel')
        self.progress_details.pack(side=tk.LEFT)

        self.progress_time = ttk.Label(details_frame,
                                      text="",
                                      style='Status.TLabel')
        self.progress_time.pack(side=tk.RIGHT)

        # Cancel button (hidden by default)
        self.cancel_btn = ttk.Button(progress_frame,
                                    text="Cancel",
                                    command=self._cancel_operation)

    def _refresh_status(self) -> None:
        """Refresh Plex status information"""
        paths = self.path_finder.paths

        if paths and paths.exists():
            self.plex_status_label.configure(text="Found", style='Success.TLabel')

            # Calculate size
            size_bytes = self.backup_engine.estimate_backup_size()
            size_str = self.path_finder.format_size(size_bytes)
            self.size_label.configure(text=size_str)
        else:
            self.plex_status_label.configure(text="Not Found", style='Error.TLabel')
            self.size_label.configure(text="--")

        # Update network info
        self.local_ip_label.configure(text=self.network.get_local_ip())

    def _populate_destinations(self) -> None:
        """Populate destination dropdown"""
        destinations = self.backup_engine.get_available_destinations()

        values = []
        for dest in destinations:
            free_gb = dest['free'] / (1024 ** 3)
            total_gb = dest['total'] / (1024 ** 3)
            values.append(f"{dest['path']} ({free_gb:.1f} GB free / {total_gb:.1f} GB)")

        self.dest_combo['values'] = values
        if values:
            self.dest_combo.current(0)

    def _browse_destination(self) -> None:
        """Browse for backup destination"""
        path = filedialog.askdirectory(title="Select Backup Destination")
        if path:
            self.dest_combo.set(path)

    def _browse_restore_source(self) -> None:
        """Browse for restore source"""
        # Allow folder or file (for compressed backups)
        path = filedialog.askdirectory(title="Select Backup Folder")
        if path:
            self.restore_source_entry.delete(0, tk.END)
            self.restore_source_entry.insert(0, path)
            self._update_backup_info(path)

    def _update_backup_info(self, path: str) -> None:
        """Update backup information display"""
        manifest_path = os.path.join(path, "Plex Media Server", "backup_manifest.json")
        if os.path.exists(manifest_path):
            try:
                import json
                with open(manifest_path) as f:
                    manifest = json.load(f)

                info = f"""
Created: {manifest.get('created_at', 'Unknown')}
Source: {manifest.get('source_hostname', 'Unknown')} ({manifest.get('source_platform', 'Unknown')})
Server: {manifest.get('server_name', 'Unknown')}
Size: {self.path_finder.format_size(manifest.get('total_size', 0))}
Files: {manifest.get('file_count', 0)}
                """
                self.backup_info_label.configure(text=info.strip())
            except:
                self.backup_info_label.configure(text="Could not read backup manifest")
        else:
            self.backup_info_label.configure(text="No manifest found (may be older backup)")

    def _toggle_compression(self) -> None:
        """Toggle compression format dropdown"""
        if self.compress_var.get():
            self.compress_format.configure(state='readonly')
        else:
            self.compress_format.configure(state='disabled')

    def _add_path_mapping(self) -> None:
        """Add path mapping to list"""
        old = self.remap_old_entry.get().strip()
        new = self.remap_new_entry.get().strip()

        if old and new:
            self.remap_list.insert(tk.END, f"{old} -> {new}")
            self.remap_old_entry.delete(0, tk.END)
            self.remap_new_entry.delete(0, tk.END)

    def _toggle_discovery(self) -> None:
        """Toggle network discovery"""
        if self.network._running:
            self.network.stop_discovery()
            self.discover_btn.configure(text="Start Discovery")
        else:
            self.network.add_callback(self._on_host_discovered)
            self.network.start_discovery()
            self.discover_btn.configure(text="Stop Discovery")

            # Update local IP
            self.local_ip_label.configure(text=self.network.get_local_ip())

    def _on_host_discovered(self, host) -> None:
        """Handle discovered host"""
        self.root.after(0, lambda: self._add_host_to_list(host))

    def _add_host_to_list(self, host) -> None:
        """Add host to listbox (on main thread)"""
        entry = f"{host.hostname} ({host.ip})"
        if host.server_name:
            entry += f" - {host.server_name}"
        if host.toolkit_port:
            entry += " [Toolkit]"

        # Check if already in list
        existing = self.hosts_listbox.get(0, tk.END)
        if entry not in existing:
            self.hosts_listbox.insert(tk.END, entry)
            self.connect_btn.configure(state='normal')

    def _connect_to_host(self) -> None:
        """Connect to selected host"""
        selection = self.hosts_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a host to connect to")
            return

        # TODO: Implement connection
        messagebox.showinfo("Connect", "Connection functionality coming soon!")
        self.network_btn.configure(state='normal')

    def _manual_connect(self) -> None:
        """Connect to manually specified host"""
        host = self.manual_host_entry.get().strip()
        port = self.manual_port_entry.get().strip()

        if not host:
            messagebox.showwarning("Missing Host", "Please enter a host address")
            return

        # TODO: Implement connection
        messagebox.showinfo("Connect", f"Connecting to {host}:{port}...")
        self.network_btn.configure(state='normal')

    def _start_backup(self) -> None:
        """Start backup operation"""
        # Get destination
        dest = self.dest_combo.get()
        if not dest:
            messagebox.showwarning("No Destination", "Please select a backup destination")
            return

        # Extract path from combo text
        if ' (' in dest:
            dest = dest.split(' (')[0]

        # Get mode
        mode_map = {
            'hot': BackupMode.HOT,
            'cold': BackupMode.COLD,
            'smart': BackupMode.SMART,
            'incremental': BackupMode.INCREMENTAL,
            'database_only': BackupMode.DATABASE_ONLY
        }
        mode = mode_map.get(self.backup_mode.get(), BackupMode.SMART)

        # Get compression
        compress = self.compress_var.get()
        format_map = {
            'ZIP': CompressionFormat.ZIP,
            'TAR.GZ': CompressionFormat.TAR_GZ,
            'TAR.XZ': CompressionFormat.TAR_XZ,
            '7Z': CompressionFormat.SEVEN_ZIP
        }
        compress_format = format_map.get(self.compress_format.get(), CompressionFormat.ZIP)

        # Hook progress callback
        def on_progress(progress):
            self.root.after(0, lambda: self._update_progress(progress))

        self.backup_engine.add_progress_callback(on_progress)

        # Disable button and show cancel
        self.backup_btn.configure(state='disabled')
        self.cancel_btn.pack(side=tk.RIGHT, pady=(10, 0))

        # Start backup
        self.backup_engine.start_backup(
            destination=dest,
            mode=mode,
            compress=compress,
            compress_format=compress_format,
            verify=self.verify_var.get()
        )

        # Start monitoring
        self._monitor_backup()

    def _monitor_backup(self) -> None:
        """Monitor backup progress"""
        if self.backup_engine.is_running:
            self.root.after(500, self._monitor_backup)
        else:
            # Backup completed
            self.backup_btn.configure(state='normal')
            self.cancel_btn.pack_forget()

            if self.backup_engine.progress.status == BackupStatus.COMPLETED:
                messagebox.showinfo("Backup Complete",
                                   "Backup completed successfully!")
            elif self.backup_engine.progress.status == BackupStatus.CANCELLED:
                messagebox.showinfo("Cancelled", "Backup was cancelled")
            else:
                errors = '\n'.join(self.backup_engine.progress.errors)
                messagebox.showerror("Backup Failed",
                                    f"Backup failed:\n{errors}")

    def _update_progress(self, progress) -> None:
        """Update progress display"""
        self.progress_status.configure(text=progress.phase or progress.status.value)
        self.progress_bar['value'] = progress.percent
        self.progress_details.configure(text=progress.current_file[:50] if progress.current_file else "")

        elapsed = progress.elapsed_seconds
        if elapsed > 0:
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            self.progress_time.configure(text=f"Elapsed: {mins}:{secs:02d}")

    def _start_restore(self) -> None:
        """Start restore operation"""
        source = self.restore_source_entry.get().strip()
        if not source:
            messagebox.showwarning("No Source", "Please select a backup source")
            return

        if not os.path.exists(source):
            messagebox.showerror("Not Found", "Backup source not found")
            return

        # Get path mappings
        path_mappings = {}
        for item in self.remap_list.get(0, tk.END):
            if ' -> ' in item:
                old, new = item.split(' -> ', 1)
                path_mappings[old] = new

        # Create config
        config = MigrationConfig(
            mode=MigrationMode.LOCAL_RESTORE,
            source_path=source,
            path_mappings=path_mappings,
            preserve_machine_id=self.preserve_id_var.get(),
            stop_plex=self.stop_plex_var.get()
        )

        # Confirm
        if not messagebox.askyesno("Confirm Restore",
                                  "This will overwrite your current Plex data. Continue?"):
            return

        # Hook progress
        def on_progress(progress):
            self.root.after(0, lambda: self._update_migration_progress(progress))

        self.migration.add_progress_callback(on_progress)

        # Start
        self.restore_btn.configure(state='disabled')
        self.cancel_btn.pack(side=tk.RIGHT, pady=(10, 0))
        self.migration.start_migration(config)
        self._monitor_migration()

    def _start_network_migration(self) -> None:
        """Start network migration"""
        role = self.role_var.get()

        if role == 'source':
            mode = MigrationMode.NETWORK_PUSH
        else:
            mode = MigrationMode.NETWORK_PULL

        # TODO: Get target from selection
        config = MigrationConfig(mode=mode)

        messagebox.showinfo("Network Migration",
                           "Network migration coming soon!")

    def _monitor_migration(self) -> None:
        """Monitor migration progress"""
        if self.migration.is_running:
            self.root.after(500, self._monitor_migration)
        else:
            self.restore_btn.configure(state='normal')
            self.cancel_btn.pack_forget()

            if self.migration.progress.phase == MigrationPhase.COMPLETED:
                messagebox.showinfo("Restore Complete",
                                   "Restore completed successfully!")
            elif self.migration.progress.phase == MigrationPhase.CANCELLED:
                messagebox.showinfo("Cancelled", "Restore was cancelled")
            else:
                errors = '\n'.join(self.migration.progress.errors)
                messagebox.showerror("Restore Failed",
                                    f"Restore failed:\n{errors}")

    def _update_migration_progress(self, progress) -> None:
        """Update migration progress display"""
        self.progress_status.configure(text=progress.phase_description)
        self.progress_bar['value'] = progress.overall_percent
        self.progress_details.configure(
            text=progress.current_operation[:50] if progress.current_operation else ""
        )

    def _cancel_operation(self) -> None:
        """Cancel current operation"""
        if self.backup_engine.is_running:
            self.backup_engine.cancel()
        if self.migration.is_running:
            self.migration.cancel()

    def _open_plex_folder(self) -> None:
        """Open Plex data folder in file explorer"""
        paths = self.path_finder.paths
        if not paths:
            messagebox.showwarning("Not Found", "Plex data folder not found")
            return

        if self.platform.info.os_type == OSType.WINDOWS:
            os.startfile(paths.data_dir)
        elif self.platform.info.os_type == OSType.MACOS:
            os.system(f'open "{paths.data_dir}"')
        else:
            os.system(f'xdg-open "{paths.data_dir}"')

    def _export_preferences(self) -> None:
        """Export Plex preferences"""
        path = filedialog.askdirectory(title="Select Export Location")
        if path:
            from core.preferences import PreferencesManager
            prefs_mgr = PreferencesManager(self.platform, self.path_finder)
            if prefs_mgr.backup_preferences(path):
                messagebox.showinfo("Exported", f"Preferences exported to {path}")
            else:
                messagebox.showerror("Error", "Failed to export preferences")

    def _export_library_info(self) -> None:
        """Export library information"""
        path = filedialog.asksaveasfilename(
            title="Save Library Info",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if path:
            from core.database import DatabaseManager
            db_mgr = DatabaseManager(self.platform, self.path_finder)
            db_mgr.connect()
            if db_mgr.export_library_info(path):
                messagebox.showinfo("Exported", f"Library info exported to {path}")
            else:
                messagebox.showerror("Error", "Failed to export library info")
            db_mgr.disconnect()

    def _show_help(self) -> None:
        """Show help dialog"""
        help_text = """
Plex Migration Toolkit Help

BACKUP TAB:
- Hot Copy: Fast backup while Plex runs (may miss locked files)
- Cold Copy: Stops Plex for reliable backup
- Smart Sync: Best of both - hot copy + cold database sync
- Incremental: Only copies changed files

RESTORE TAB:
- Select your backup folder or archive
- Add path mappings if media locations changed
- Optionally preserve machine ID for same-machine restore

NETWORK MIGRATION:
- Run toolkit on both machines
- Set one as Source, one as Target
- Use discovery or manual connection
- Data transfers directly between machines

For more help, visit:
github.com/saint1415/powershell
        """
        messagebox.showinfo("Help", help_text.strip())

    def _on_close(self) -> None:
        """Handle window close"""
        if self.backup_engine.is_running or self.migration.is_running:
            if not messagebox.askyesno("Operation Running",
                                      "An operation is in progress. Cancel and exit?"):
                return
            self._cancel_operation()

        self.network.stop_discovery()
        self.root.destroy()

    def run(self) -> None:
        """Run the application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    app = PlexToolkitGUI()
    app.run()


if __name__ == "__main__":
    main()
