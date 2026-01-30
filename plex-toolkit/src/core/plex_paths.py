"""
Plex Path Finder Module
Discovers Plex Media Server data locations across all platforms
"""

import os
import glob
import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from .platform import PlatformDetector, OSType, get_platform


class PlexInstallType(Enum):
    """Types of Plex installations"""
    STANDARD = "standard"
    PORTABLE = "portable"
    DOCKER = "docker"
    NAS_PACKAGE = "nas_package"
    SNAP = "snap"
    FLATPAK = "flatpak"
    CUSTOM = "custom"


@dataclass
class PlexPaths:
    """Container for Plex Media Server paths"""
    data_dir: str  # Main data directory
    plugin_support: str  # Plugin Support folder
    databases_dir: str  # Databases folder
    metadata_dir: str  # Metadata folder
    media_dir: str  # Media folder (posters/art cache)
    cache_dir: str  # Cache folder
    logs_dir: str  # Logs folder
    preferences_file: str  # Preferences.xml location
    registry_file: Optional[str] = None  # Windows registry backup file
    install_type: PlexInstallType = PlexInstallType.STANDARD

    # Sizes (populated after scan)
    data_size: int = 0
    database_size: int = 0
    metadata_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'data_dir': self.data_dir,
            'plugin_support': self.plugin_support,
            'databases_dir': self.databases_dir,
            'metadata_dir': self.metadata_dir,
            'media_dir': self.media_dir,
            'cache_dir': self.cache_dir,
            'logs_dir': self.logs_dir,
            'preferences_file': self.preferences_file,
            'registry_file': self.registry_file,
            'install_type': self.install_type.value,
            'data_size': self.data_size,
            'database_size': self.database_size,
            'metadata_size': self.metadata_size
        }

    def exists(self) -> bool:
        """Check if the data directory exists"""
        return os.path.exists(self.data_dir)


@dataclass
class PlexLibrary:
    """Represents a Plex library"""
    id: int
    name: str
    type: str  # movie, show, music, photo
    location: str
    scanner: str
    agent: str
    created_at: Optional[str] = None
    scanned_at: Optional[str] = None


class PlexPathFinder:
    """
    Discovers Plex Media Server installation and data paths
    Supports Windows, Linux, macOS, Synology, QNAP, Unraid, TrueNAS
    """

    # Default paths by platform
    DEFAULT_PATHS = {
        OSType.WINDOWS: [
            r"%LOCALAPPDATA%\Plex Media Server",
            r"%USERPROFILE%\AppData\Local\Plex Media Server",
            r"C:\Users\*\AppData\Local\Plex Media Server",
        ],
        OSType.MACOS: [
            "~/Library/Application Support/Plex Media Server",
            "/Users/*/Library/Application Support/Plex Media Server",
        ],
        OSType.LINUX: [
            "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server",
            "~/.local/share/Plex Media Server",
            "/home/*/.local/share/Plex Media Server",
            "/var/snap/plexmediaserver/common/Library/Application Support/Plex Media Server",
            "/var/lib/flatpak/app/tv.plex.PlexMediaServer/*/active/files/share/Plex Media Server",
        ],
        OSType.SYNOLOGY: [
            "/volume1/PlexMediaServer/AppData/Plex Media Server",
            "/volume1/Plex/Library/Application Support/Plex Media Server",
            "/volume*/PlexMediaServer/AppData/Plex Media Server",
            "/volume*/@appdata/PlexMediaServer",
        ],
        OSType.QNAP: [
            "/share/CACHEDEV1_DATA/.qpkg/PlexMediaServer/Library/Plex Media Server",
            "/share/PlexData/Library/Plex Media Server",
        ],
        OSType.UNRAID: [
            "/mnt/user/appdata/plex/Library/Application Support/Plex Media Server",
            "/mnt/cache/appdata/plex/Library/Application Support/Plex Media Server",
        ],
        OSType.TRUENAS: [
            "/mnt/*/iocage/jails/plex/root/usr/local/plexdata/Plex Media Server",
            "/mnt/*/iocage/jails/plexmediaserver/root/Plex Media Server",
        ],
        OSType.FREEBSD: [
            "/usr/local/plexdata/Plex Media Server",
            "/var/db/plexdata/Plex Media Server",
        ],
    }

    # Registry keys for Windows
    WINDOWS_REGISTRY_KEYS = [
        r"HKEY_CURRENT_USER\Software\Plex, Inc.\Plex Media Server",
        r"HKEY_LOCAL_MACHINE\SOFTWARE\Plex, Inc.\Plex Media Server",
    ]

    def __init__(self, platform: Optional[PlatformDetector] = None):
        self.platform = platform or get_platform()
        self._paths: Optional[PlexPaths] = None
        self._libraries: List[PlexLibrary] = []

    @property
    def paths(self) -> Optional[PlexPaths]:
        """Get discovered Plex paths"""
        if self._paths is None:
            self._paths = self.discover_paths()
        return self._paths

    def discover_paths(self) -> Optional[PlexPaths]:
        """Discover Plex Media Server data paths"""
        os_type = self.platform.info.os_type

        # Get potential paths for this platform
        potential_paths = self.DEFAULT_PATHS.get(os_type, [])

        # Also check unknown platforms with Linux paths
        if os_type == OSType.UNKNOWN:
            potential_paths = self.DEFAULT_PATHS[OSType.LINUX]

        # Expand environment variables and wildcards
        for path_template in potential_paths:
            expanded = self._expand_path(path_template)

            for path in expanded:
                if os.path.isdir(path):
                    return self._build_paths(path)

        # Try to find via environment variable
        plex_home = os.environ.get('PLEX_HOME')
        if plex_home and os.path.isdir(plex_home):
            return self._build_paths(plex_home)

        # Windows: Try registry
        if os_type == OSType.WINDOWS:
            reg_path = self._find_from_registry()
            if reg_path:
                return self._build_paths(reg_path)

        return None

    def _expand_path(self, path_template: str) -> List[str]:
        """Expand environment variables and wildcards in path"""
        # Expand environment variables
        path = os.path.expandvars(path_template)
        path = os.path.expanduser(path)

        # Handle wildcards
        if '*' in path:
            return glob.glob(path)

        return [path] if path else []

    def _build_paths(self, data_dir: str) -> PlexPaths:
        """Build complete paths structure from data directory"""
        data_dir = os.path.normpath(data_dir)

        paths = PlexPaths(
            data_dir=data_dir,
            plugin_support=os.path.join(data_dir, "Plug-in Support"),
            databases_dir=os.path.join(data_dir, "Plug-in Support", "Databases"),
            metadata_dir=os.path.join(data_dir, "Metadata"),
            media_dir=os.path.join(data_dir, "Media"),
            cache_dir=os.path.join(data_dir, "Cache"),
            logs_dir=os.path.join(data_dir, "Logs"),
            preferences_file=os.path.join(data_dir, "Preferences.xml"),
            install_type=self._detect_install_type(data_dir)
        )

        # Calculate sizes
        self._calculate_sizes(paths)

        return paths

    def _detect_install_type(self, data_dir: str) -> PlexInstallType:
        """Detect the type of Plex installation"""
        path_lower = data_dir.lower()

        if '/docker/' in path_lower or '/appdata/plex' in path_lower:
            return PlexInstallType.DOCKER
        elif '/snap/' in path_lower:
            return PlexInstallType.SNAP
        elif '/flatpak/' in path_lower:
            return PlexInstallType.FLATPAK
        elif '/volume' in path_lower or '/@appdata/' in path_lower:
            return PlexInstallType.NAS_PACKAGE
        elif '/iocage/' in path_lower or '/jails/' in path_lower:
            return PlexInstallType.NAS_PACKAGE
        elif os.path.exists(os.path.join(data_dir, "..", "Plex Media Server.exe")):
            return PlexInstallType.PORTABLE
        else:
            return PlexInstallType.STANDARD

    def _calculate_sizes(self, paths: PlexPaths) -> None:
        """Calculate sizes of Plex data directories"""
        try:
            if os.path.exists(paths.databases_dir):
                paths.database_size = self._get_dir_size(paths.databases_dir)

            if os.path.exists(paths.metadata_dir):
                paths.metadata_size = self._get_dir_size(paths.metadata_dir)

            if os.path.exists(paths.data_dir):
                # Estimate total without full scan (can be slow)
                paths.data_size = paths.database_size + paths.metadata_size
                if os.path.exists(paths.media_dir):
                    paths.data_size += self._get_dir_size(paths.media_dir)
        except Exception:
            pass

    def _get_dir_size(self, path: str) -> int:
        """Get total size of directory in bytes"""
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self._get_dir_size(entry.path)
        except (PermissionError, OSError):
            pass
        return total

    def _find_from_registry(self) -> Optional[str]:
        """Find Plex data path from Windows registry"""
        try:
            import winreg

            for key_path in self.WINDOWS_REGISTRY_KEYS:
                try:
                    # Parse key path
                    if key_path.startswith("HKEY_CURRENT_USER"):
                        root = winreg.HKEY_CURRENT_USER
                        subkey = key_path.replace("HKEY_CURRENT_USER\\", "")
                    else:
                        root = winreg.HKEY_LOCAL_MACHINE
                        subkey = key_path.replace("HKEY_LOCAL_MACHINE\\", "")

                    with winreg.OpenKey(root, subkey) as key:
                        value, _ = winreg.QueryValueEx(key, "LocalAppDataPath")
                        if value and os.path.isdir(value):
                            return value
                except WindowsError:
                    continue
        except ImportError:
            pass

        return None

    def export_registry(self, output_file: str) -> bool:
        """Export Windows Plex registry settings to file"""
        if self.platform.info.os_type != OSType.WINDOWS:
            return False

        try:
            import subprocess
            for key_path in self.WINDOWS_REGISTRY_KEYS:
                result = subprocess.run(
                    ['reg', 'export', key_path.replace("HKEY_", ""), output_file, '/y'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return True
        except Exception:
            pass

        return False

    def get_preferences(self) -> Dict[str, Any]:
        """Read Plex preferences from Preferences.xml"""
        if not self.paths or not os.path.exists(self.paths.preferences_file):
            return {}

        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(self.paths.preferences_file)
            root = tree.getroot()

            prefs = {}
            for key, value in root.attrib.items():
                prefs[key] = value

            return prefs
        except Exception:
            return {}

    def get_machine_identifier(self) -> Optional[str]:
        """Get the Plex server machine identifier"""
        prefs = self.get_preferences()
        return prefs.get('MachineIdentifier')

    def get_server_name(self) -> Optional[str]:
        """Get the Plex server friendly name"""
        prefs = self.get_preferences()
        return prefs.get('FriendlyName')

    def get_libraries(self) -> List[PlexLibrary]:
        """Get list of Plex libraries from database"""
        if self._libraries:
            return self._libraries

        if not self.paths:
            return []

        db_path = os.path.join(self.paths.databases_dir, "com.plexapp.plugins.library.db")
        if not os.path.exists(db_path):
            return []

        try:
            import sqlite3
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, section_type, root_path, scanner, agent,
                       created_at, scanned_at
                FROM library_sections
                ORDER BY id
            """)

            for row in cursor.fetchall():
                self._libraries.append(PlexLibrary(
                    id=row[0],
                    name=row[1],
                    type=self._section_type_to_string(row[2]),
                    location=row[3] or "",
                    scanner=row[4] or "",
                    agent=row[5] or "",
                    created_at=row[6],
                    scanned_at=row[7]
                ))

            conn.close()
        except Exception:
            pass

        return self._libraries

    def _section_type_to_string(self, section_type: int) -> str:
        """Convert section type number to string"""
        types = {
            1: "movie",
            2: "show",
            3: "music",
            4: "photo",
            8: "artist",
            13: "clip"
        }
        return types.get(section_type, "unknown")

    def validate_installation(self) -> Dict[str, bool]:
        """Validate Plex installation completeness"""
        if not self.paths:
            return {"found": False}

        return {
            "found": True,
            "data_dir_exists": os.path.exists(self.paths.data_dir),
            "databases_exist": os.path.exists(self.paths.databases_dir),
            "preferences_exist": os.path.exists(self.paths.preferences_file),
            "has_libraries": len(self.get_libraries()) > 0,
            "main_db_exists": os.path.exists(
                os.path.join(self.paths.databases_dir, "com.plexapp.plugins.library.db")
            ),
            "blobs_db_exists": os.path.exists(
                os.path.join(self.paths.databases_dir, "com.plexapp.plugins.library.blobs.db")
            )
        }

    @staticmethod
    def convert_path(path: str, source_os: OSType, target_os: OSType) -> str:
        """Convert a path from one OS format to another"""
        if source_os == target_os:
            return path

        # Normalize to forward slashes
        normalized = path.replace("\\", "/")

        # Windows -> Unix
        if source_os == OSType.WINDOWS and target_os != OSType.WINDOWS:
            # Remove drive letter
            if len(normalized) > 1 and normalized[1] == ':':
                normalized = normalized[2:]
            # Handle UNC paths
            if normalized.startswith("//"):
                normalized = "/mnt" + normalized[1:]
            return normalized

        # Unix -> Windows
        if source_os != OSType.WINDOWS and target_os == OSType.WINDOWS:
            # Add drive letter if not present
            if normalized.startswith("/"):
                normalized = "C:" + normalized
            return normalized.replace("/", "\\")

        return path

    def format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of Plex installation"""
        if not self.paths:
            return {"status": "not_found"}

        return {
            "status": "found",
            "data_dir": self.paths.data_dir,
            "install_type": self.paths.install_type.value,
            "server_name": self.get_server_name(),
            "machine_id": self.get_machine_identifier(),
            "library_count": len(self.get_libraries()),
            "data_size": self.format_size(self.paths.data_size),
            "database_size": self.format_size(self.paths.database_size),
            "metadata_size": self.format_size(self.paths.metadata_size),
            "validation": self.validate_installation()
        }
