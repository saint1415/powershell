"""
Plex Migration Toolkit
Cross-platform backup and migration tool for Plex Media Server
"""

__version__ = "2.0.0"
__author__ = "saint1415"
__license__ = "MIT"

from .core.platform import PlatformDetector
from .core.plex_paths import PlexPathFinder
from .core.backup import BackupEngine
from .core.network import NetworkDiscovery
from .core.migration import MigrationManager

__all__ = [
    'PlatformDetector',
    'PlexPathFinder',
    'BackupEngine',
    'NetworkDiscovery',
    'MigrationManager'
]
