"""
Preferences Management Module
Handles Plex preferences and registry settings for cross-platform migration
"""

import os
import xml.etree.ElementTree as ET
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path

from .platform import PlatformDetector, OSType, get_platform
from .plex_paths import PlexPathFinder


@dataclass
class PlexPreferences:
    """Container for Plex preferences"""
    machine_identifier: str = ""
    friendly_name: str = ""
    process_token: str = ""
    plex_online_token: str = ""
    accepted_eula: bool = False
    local_app_data_path: str = ""
    transcoder_temp_directory: str = ""
    custom_connections: str = ""
    manual_port_mapping_port: int = 32400
    publish_server_on_plex: bool = True
    dlna_enabled: bool = True
    hardware_acceleration: bool = True

    # All preferences as dict
    all_preferences: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'machine_identifier': self.machine_identifier,
            'friendly_name': self.friendly_name,
            'accepted_eula': self.accepted_eula,
            'local_app_data_path': self.local_app_data_path,
            'transcoder_temp_directory': self.transcoder_temp_directory,
            'custom_connections': self.custom_connections,
            'manual_port_mapping_port': self.manual_port_mapping_port,
            'publish_server_on_plex': self.publish_server_on_plex,
            'dlna_enabled': self.dlna_enabled,
            'hardware_acceleration': self.hardware_acceleration,
            'all_preferences': self.all_preferences
        }


class PreferencesManager:
    """
    Manages Plex Media Server preferences across platforms
    Handles Preferences.xml and Windows Registry settings
    """

    # Preferences that contain paths and need remapping
    PATH_PREFERENCES = [
        'LocalAppDataPath',
        'TranscoderTempDirectory',
        'ButlerDatabaseBackupPath',
        'MetadataPath',
        'CachePath'
    ]

    # Preferences that should NOT be migrated (system-specific)
    SKIP_PREFERENCES = [
        'MachineIdentifier',  # Generated per installation
        'ProcessedMachineIdentifier',
        'AnonymousMachineIdentifier',
        'PlexOnlineToken',  # Re-authenticate on new system
        'PlexOnlineUsername',
        'PlexOnlineHome',
        'ManualPortMappingMode',  # Network specific
        'customConnections',  # Network specific
        'LastAutomaticMappedPort',
        'CertificateUUID',
        'CertificateVersion'
    ]

    # Preferences that may need adjustment for new OS
    ADJUST_PREFERENCES = {
        'TranscoderH264Preset': {
            # Map hardware acceleration settings
            OSType.WINDOWS: 'auto',
            OSType.LINUX: 'auto',
            OSType.MACOS: 'auto'
        }
    }

    def __init__(self,
                 platform: Optional[PlatformDetector] = None,
                 path_finder: Optional[PlexPathFinder] = None):
        self.platform = platform or get_platform()
        self.path_finder = path_finder or PlexPathFinder(self.platform)

    def get_preferences_path(self) -> Optional[str]:
        """Get path to Preferences.xml"""
        paths = self.path_finder.paths
        if paths and os.path.exists(paths.preferences_file):
            return paths.preferences_file
        return None

    def read_preferences(self) -> PlexPreferences:
        """Read Plex preferences from file"""
        prefs = PlexPreferences()
        prefs_path = self.get_preferences_path()

        if not prefs_path or not os.path.exists(prefs_path):
            return prefs

        try:
            tree = ET.parse(prefs_path)
            root = tree.getroot()

            # Store all preferences
            prefs.all_preferences = dict(root.attrib)

            # Parse specific preferences
            prefs.machine_identifier = root.get('MachineIdentifier', '')
            prefs.friendly_name = root.get('FriendlyName', '')
            prefs.process_token = root.get('PlexOnlineToken', '')
            prefs.accepted_eula = root.get('AcceptedEULA', '0') == '1'
            prefs.local_app_data_path = root.get('LocalAppDataPath', '')
            prefs.transcoder_temp_directory = root.get('TranscoderTempDirectory', '')
            prefs.custom_connections = root.get('customConnections', '')
            prefs.publish_server_on_plex = root.get('PublishServerOnPlexOnlineKey', '1') == '1'
            prefs.dlna_enabled = root.get('DlnaEnabled', '1') == '1'
            prefs.hardware_acceleration = root.get('HardwareAcceleratedCodecs', '1') == '1'

            try:
                prefs.manual_port_mapping_port = int(root.get('ManualPortMappingPort', '32400'))
            except ValueError:
                prefs.manual_port_mapping_port = 32400

        except ET.ParseError:
            pass

        return prefs

    def write_preferences(self, prefs: PlexPreferences, output_path: str) -> bool:
        """Write preferences to file"""
        try:
            root = ET.Element('Preferences')

            for key, value in prefs.all_preferences.items():
                root.set(key, str(value))

            tree = ET.ElementTree(root)

            # Write with XML declaration
            with open(output_path, 'wb') as f:
                tree.write(f, encoding='utf-8', xml_declaration=True)

            return True

        except Exception:
            return False

    def migrate_preferences(self,
                           source_prefs: PlexPreferences,
                           target_os: OSType,
                           path_mappings: Optional[Dict[str, str]] = None) -> PlexPreferences:
        """
        Create migrated preferences for target OS

        Args:
            source_prefs: Original preferences
            target_os: Target operating system
            path_mappings: Path remapping dictionary
        """
        migrated = PlexPreferences()
        migrated.all_preferences = source_prefs.all_preferences.copy()

        # Remove preferences that shouldn't migrate
        for skip_key in self.SKIP_PREFERENCES:
            migrated.all_preferences.pop(skip_key, None)

        # Remap path preferences
        if path_mappings:
            for path_key in self.PATH_PREFERENCES:
                if path_key in migrated.all_preferences:
                    old_path = migrated.all_preferences[path_key]
                    for old, new in path_mappings.items():
                        if old_path.startswith(old):
                            migrated.all_preferences[path_key] = old_path.replace(old, new)
                            break

        # Adjust OS-specific preferences
        for pref_key, os_values in self.ADJUST_PREFERENCES.items():
            if target_os in os_values:
                migrated.all_preferences[pref_key] = os_values[target_os]

        # Convert path separators
        source_os = self.platform.info.os_type
        if source_os == OSType.WINDOWS and target_os != OSType.WINDOWS:
            # Windows -> Unix: convert backslashes
            for key in self.PATH_PREFERENCES:
                if key in migrated.all_preferences:
                    migrated.all_preferences[key] = (
                        migrated.all_preferences[key].replace('\\', '/')
                    )
        elif source_os != OSType.WINDOWS and target_os == OSType.WINDOWS:
            # Unix -> Windows: convert forward slashes
            for key in self.PATH_PREFERENCES:
                if key in migrated.all_preferences:
                    migrated.all_preferences[key] = (
                        migrated.all_preferences[key].replace('/', '\\')
                    )

        return migrated

    def export_registry(self, output_file: str) -> bool:
        """Export Windows Registry Plex settings"""
        if self.platform.info.os_type != OSType.WINDOWS:
            return False

        try:
            # Export HKCU Plex settings
            result = subprocess.run(
                ['reg', 'export',
                 r'HKEY_CURRENT_USER\Software\Plex, Inc.\Plex Media Server',
                 output_file, '/y'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0

        except Exception:
            return False

    def import_registry(self, input_file: str) -> bool:
        """Import Windows Registry Plex settings"""
        if self.platform.info.os_type != OSType.WINDOWS:
            return False

        if not os.path.exists(input_file):
            return False

        try:
            result = subprocess.run(
                ['reg', 'import', input_file],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0

        except Exception:
            return False

    def registry_to_preferences(self, reg_file: str) -> Dict[str, str]:
        """Convert Windows Registry export to preferences dictionary"""
        prefs = {}

        if not os.path.exists(reg_file):
            return prefs

        try:
            # Read registry file (UTF-16 LE with BOM)
            with open(reg_file, 'r', encoding='utf-16-le') as f:
                content = f.read()

            # Parse registry entries
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('"') and '=' in line:
                    # Parse "key"="value" or "key"=dword:value
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip('"')
                        value = parts[1]

                        if value.startswith('"') and value.endswith('"'):
                            # String value
                            prefs[key] = value.strip('"')
                        elif value.startswith('dword:'):
                            # DWORD value
                            hex_val = value[6:]
                            prefs[key] = str(int(hex_val, 16))

        except Exception:
            pass

        return prefs

    def preferences_to_registry(self,
                               prefs: Dict[str, str],
                               output_file: str) -> bool:
        """Convert preferences dictionary to Windows Registry file"""
        try:
            lines = [
                'Windows Registry Editor Version 5.00',
                '',
                r'[HKEY_CURRENT_USER\Software\Plex, Inc.\Plex Media Server]'
            ]

            for key, value in prefs.items():
                if value.isdigit():
                    # Write as DWORD
                    hex_val = format(int(value), '08x')
                    lines.append(f'"{key}"=dword:{hex_val}')
                else:
                    # Write as string (escape backslashes)
                    escaped = value.replace('\\', '\\\\')
                    lines.append(f'"{key}"="{escaped}"')

            with open(output_file, 'w', encoding='utf-16-le') as f:
                # Write BOM
                f.write('\ufeff')
                f.write('\r\n'.join(lines))

            return True

        except Exception:
            return False

    def get_server_info(self) -> Dict[str, Any]:
        """Get Plex server information from preferences"""
        prefs = self.read_preferences()

        return {
            'machine_identifier': prefs.machine_identifier,
            'friendly_name': prefs.friendly_name,
            'accepted_eula': prefs.accepted_eula,
            'publish_to_plex': prefs.publish_server_on_plex,
            'dlna_enabled': prefs.dlna_enabled,
            'hardware_acceleration': prefs.hardware_acceleration,
            'port': prefs.manual_port_mapping_port
        }

    def backup_preferences(self, output_dir: str) -> bool:
        """Backup all Plex preferences"""
        os.makedirs(output_dir, exist_ok=True)

        prefs_path = self.get_preferences_path()
        if prefs_path and os.path.exists(prefs_path):
            shutil.copy2(prefs_path, os.path.join(output_dir, 'Preferences.xml'))

        # On Windows, also backup registry
        if self.platform.info.os_type == OSType.WINDOWS:
            self.export_registry(os.path.join(output_dir, 'plex_registry.reg'))

        # Export preferences as JSON for reference
        prefs = self.read_preferences()
        with open(os.path.join(output_dir, 'preferences.json'), 'w') as f:
            json.dump(prefs.to_dict(), f, indent=2)

        return True

    def restore_preferences(self,
                           source_dir: str,
                           target_path: Optional[str] = None) -> bool:
        """Restore Plex preferences from backup"""
        prefs_backup = os.path.join(source_dir, 'Preferences.xml')

        if not os.path.exists(prefs_backup):
            return False

        if not target_path:
            target_path = self.get_preferences_path()

        if not target_path:
            return False

        try:
            shutil.copy2(prefs_backup, target_path)

            # On Windows, also restore registry if available
            if self.platform.info.os_type == OSType.WINDOWS:
                reg_backup = os.path.join(source_dir, 'plex_registry.reg')
                if os.path.exists(reg_backup):
                    self.import_registry(reg_backup)

            return True

        except Exception:
            return False

    def generate_new_machine_id(self) -> str:
        """Generate a new unique machine identifier"""
        import uuid
        import hashlib

        unique_string = str(uuid.uuid4()) + str(uuid.getnode())
        return hashlib.sha256(unique_string.encode()).hexdigest()[:40]

    def update_machine_id(self, prefs_path: str, new_id: Optional[str] = None) -> bool:
        """Update machine identifier in preferences file"""
        if not os.path.exists(prefs_path):
            return False

        if not new_id:
            new_id = self.generate_new_machine_id()

        try:
            tree = ET.parse(prefs_path)
            root = tree.getroot()

            root.set('MachineIdentifier', new_id)
            root.set('ProcessedMachineIdentifier', new_id)

            tree.write(prefs_path, encoding='utf-8', xml_declaration=True)
            return True

        except Exception:
            return False
