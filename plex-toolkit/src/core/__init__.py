"""
Core modules for Plex Migration Toolkit
"""

from .platform import PlatformDetector
from .plex_paths import PlexPathFinder
from .backup import BackupEngine
from .network import NetworkDiscovery
from .migration import MigrationManager
from .compression import CompressionManager
from .database import DatabaseManager
from .preferences import PreferencesManager

__all__ = [
    'PlatformDetector',
    'PlexPathFinder',
    'BackupEngine',
    'NetworkDiscovery',
    'MigrationManager',
    'CompressionManager',
    'DatabaseManager',
    'PreferencesManager'
]
