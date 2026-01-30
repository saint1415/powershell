"""
Database Management Module
Handles Plex database operations for migration
"""

import os
import sqlite3
import shutil
import json
import hashlib
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from .platform import PlatformDetector, OSType, get_platform
from .plex_paths import PlexPathFinder


@dataclass
class LibrarySection:
    """Represents a Plex library section"""
    id: int
    name: str
    type: int
    type_name: str
    agent: str
    scanner: str
    root_path: str
    created_at: str
    scanned_at: str
    uuid: str


@dataclass
class MediaLocation:
    """Represents a media location path"""
    id: int
    library_section_id: int
    root_path: str
    available: bool = True


@dataclass
class DatabaseStats:
    """Statistics about Plex databases"""
    main_db_size: int = 0
    blobs_db_size: int = 0
    total_libraries: int = 0
    total_items: int = 0
    total_watched: int = 0
    total_collections: int = 0
    total_playlists: int = 0


class DatabaseManager:
    """
    Manages Plex Media Server database operations
    Handles path remapping for cross-platform migration
    """

    # Database file names
    MAIN_DB = "com.plexapp.plugins.library.db"
    BLOBS_DB = "com.plexapp.plugins.library.blobs.db"

    def __init__(self,
                 platform: Optional[PlatformDetector] = None,
                 path_finder: Optional[PlexPathFinder] = None):
        self.platform = platform or get_platform()
        self.path_finder = path_finder or PlexPathFinder(self.platform)
        self._conn: Optional[sqlite3.Connection] = None

    def get_database_path(self) -> Optional[str]:
        """Get path to main Plex database"""
        paths = self.path_finder.paths
        if not paths:
            return None

        db_path = os.path.join(paths.databases_dir, self.MAIN_DB)
        return db_path if os.path.exists(db_path) else None

    def connect(self, readonly: bool = True) -> bool:
        """Connect to Plex database"""
        db_path = self.get_database_path()
        if not db_path:
            return False

        try:
            if readonly:
                self._conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            else:
                self._conn = sqlite3.connect(db_path)

            self._conn.row_factory = sqlite3.Row
            return True

        except sqlite3.Error:
            return False

    def disconnect(self) -> None:
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def get_stats(self) -> DatabaseStats:
        """Get database statistics"""
        stats = DatabaseStats()
        paths = self.path_finder.paths

        if paths:
            main_db = os.path.join(paths.databases_dir, self.MAIN_DB)
            blobs_db = os.path.join(paths.databases_dir, self.BLOBS_DB)

            if os.path.exists(main_db):
                stats.main_db_size = os.path.getsize(main_db)
            if os.path.exists(blobs_db):
                stats.blobs_db_size = os.path.getsize(blobs_db)

        if self._conn:
            try:
                cursor = self._conn.cursor()

                # Count libraries
                cursor.execute("SELECT COUNT(*) FROM library_sections")
                stats.total_libraries = cursor.fetchone()[0]

                # Count items
                cursor.execute("SELECT COUNT(*) FROM metadata_items")
                stats.total_items = cursor.fetchone()[0]

                # Count watched items
                cursor.execute("""
                    SELECT COUNT(*) FROM metadata_item_settings
                    WHERE view_count > 0
                """)
                stats.total_watched = cursor.fetchone()[0]

                # Count collections
                cursor.execute("""
                    SELECT COUNT(*) FROM metadata_items
                    WHERE metadata_type = 18
                """)
                stats.total_collections = cursor.fetchone()[0]

                # Count playlists
                cursor.execute("SELECT COUNT(*) FROM play_queue_generators")
                stats.total_playlists = cursor.fetchone()[0]

            except sqlite3.Error:
                pass

        return stats

    def get_library_sections(self) -> List[LibrarySection]:
        """Get all library sections"""
        sections = []

        if not self._conn:
            if not self.connect():
                return sections

        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT id, name, section_type, agent, scanner,
                       root_path, created_at, scanned_at, uuid
                FROM library_sections
                ORDER BY id
            """)

            type_names = {
                1: "movie",
                2: "show",
                3: "music",
                4: "photo",
                8: "artist",
                13: "clip"
            }

            for row in cursor.fetchall():
                sections.append(LibrarySection(
                    id=row['id'],
                    name=row['name'],
                    type=row['section_type'],
                    type_name=type_names.get(row['section_type'], 'unknown'),
                    agent=row['agent'] or '',
                    scanner=row['scanner'] or '',
                    root_path=row['root_path'] or '',
                    created_at=row['created_at'] or '',
                    scanned_at=row['scanned_at'] or '',
                    uuid=row['uuid'] or ''
                ))

        except sqlite3.Error:
            pass

        return sections

    def get_media_locations(self) -> List[MediaLocation]:
        """Get all media location paths"""
        locations = []

        if not self._conn:
            if not self.connect():
                return locations

        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT id, library_section_id, root_path, available
                FROM section_locations
                ORDER BY library_section_id, id
            """)

            for row in cursor.fetchall():
                locations.append(MediaLocation(
                    id=row['id'],
                    library_section_id=row['library_section_id'],
                    root_path=row['root_path'] or '',
                    available=bool(row['available'])
                ))

        except sqlite3.Error:
            pass

        return locations

    def get_unique_paths(self) -> List[str]:
        """Get all unique media paths from database"""
        paths = set()
        locations = self.get_media_locations()
        for loc in locations:
            if loc.root_path:
                paths.add(loc.root_path)
        return sorted(list(paths))

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify database integrity"""
        result = {
            'main_db': {'exists': False, 'integrity': None, 'size': 0},
            'blobs_db': {'exists': False, 'integrity': None, 'size': 0}
        }

        paths = self.path_finder.paths
        if not paths:
            return result

        main_db = os.path.join(paths.databases_dir, self.MAIN_DB)
        blobs_db = os.path.join(paths.databases_dir, self.BLOBS_DB)

        for db_key, db_path in [('main_db', main_db), ('blobs_db', blobs_db)]:
            if os.path.exists(db_path):
                result[db_key]['exists'] = True
                result[db_key]['size'] = os.path.getsize(db_path)

                try:
                    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check")
                    check = cursor.fetchone()[0]
                    result[db_key]['integrity'] = check
                    conn.close()
                except sqlite3.Error as e:
                    result[db_key]['integrity'] = f"error: {str(e)}"

        return result

    def backup_database(self, output_dir: str) -> bool:
        """
        Create a safe backup of Plex databases

        Uses SQLite backup API for consistency
        """
        paths = self.path_finder.paths
        if not paths:
            return False

        os.makedirs(output_dir, exist_ok=True)

        for db_name in [self.MAIN_DB, self.BLOBS_DB]:
            src_path = os.path.join(paths.databases_dir, db_name)
            dst_path = os.path.join(output_dir, db_name)

            if not os.path.exists(src_path):
                continue

            try:
                # Use SQLite backup API for consistency
                src_conn = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
                dst_conn = sqlite3.connect(dst_path)

                src_conn.backup(dst_conn)

                src_conn.close()
                dst_conn.close()

                # Also copy WAL and SHM files if they exist
                for ext in ['-wal', '-shm']:
                    wal_src = src_path + ext
                    wal_dst = dst_path + ext
                    if os.path.exists(wal_src):
                        shutil.copy2(wal_src, wal_dst)

            except Exception:
                # Fall back to simple copy
                try:
                    shutil.copy2(src_path, dst_path)
                except Exception:
                    return False

        return True

    def remap_paths(self,
                   db_path: str,
                   path_mappings: Dict[str, str],
                   backup: bool = True) -> bool:
        """
        Remap media paths in database for migration

        Args:
            db_path: Path to database file
            path_mappings: Dict of old_path -> new_path
            backup: Create backup before modification
        """
        if not os.path.exists(db_path):
            return False

        # Create backup
        if backup:
            backup_path = db_path + '.backup'
            shutil.copy2(db_path, backup_path)

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Update section_locations
            for old_path, new_path in path_mappings.items():
                cursor.execute("""
                    UPDATE section_locations
                    SET root_path = REPLACE(root_path, ?, ?)
                    WHERE root_path LIKE ?
                """, (old_path, new_path, f"{old_path}%"))

            # Update media_parts
            for old_path, new_path in path_mappings.items():
                cursor.execute("""
                    UPDATE media_parts
                    SET file = REPLACE(file, ?, ?)
                    WHERE file LIKE ?
                """, (old_path, new_path, f"{old_path}%"))

            conn.commit()
            conn.close()
            return True

        except sqlite3.Error:
            # Restore backup on error
            if backup and os.path.exists(db_path + '.backup'):
                shutil.copy2(db_path + '.backup', db_path)
            return False

    def generate_path_mappings(self,
                              source_os: OSType,
                              target_os: OSType,
                              custom_mappings: Optional[Dict[str, str]] = None
                              ) -> Dict[str, str]:
        """
        Generate path mappings for cross-platform migration

        Args:
            source_os: Source operating system
            target_os: Target operating system
            custom_mappings: Additional custom path mappings
        """
        mappings = custom_mappings.copy() if custom_mappings else {}

        # Get current paths from database
        source_paths = self.get_unique_paths()

        for src_path in source_paths:
            if src_path in mappings:
                continue

            # Generate automatic mapping
            if source_os == OSType.WINDOWS and target_os != OSType.WINDOWS:
                # Windows -> Unix
                # C:\Media -> /mnt/media or /media
                if len(src_path) > 2 and src_path[1] == ':':
                    drive_letter = src_path[0].lower()
                    unix_path = src_path[2:].replace('\\', '/')

                    # Common mapping patterns
                    mappings[src_path] = f"/mnt/{drive_letter}{unix_path}"

            elif source_os != OSType.WINDOWS and target_os == OSType.WINDOWS:
                # Unix -> Windows
                # /mnt/media -> D:\Media
                if src_path.startswith('/mnt/') and len(src_path) > 5:
                    # /mnt/d/something -> D:\something
                    parts = src_path[5:].split('/', 1)
                    if len(parts[0]) == 1:  # Single letter = drive
                        drive = parts[0].upper()
                        rest = parts[1] if len(parts) > 1 else ''
                        mappings[src_path] = f"{drive}:\\{rest.replace('/', '\\')}"

        return mappings

    def export_library_info(self, output_file: str) -> bool:
        """Export library information to JSON file"""
        info = {
            'sections': [],
            'locations': [],
            'stats': None
        }

        # Get sections
        for section in self.get_library_sections():
            info['sections'].append({
                'id': section.id,
                'name': section.name,
                'type': section.type_name,
                'agent': section.agent,
                'scanner': section.scanner,
                'created_at': section.created_at,
                'scanned_at': section.scanned_at
            })

        # Get locations
        for loc in self.get_media_locations():
            info['locations'].append({
                'id': loc.id,
                'library_section_id': loc.library_section_id,
                'root_path': loc.root_path,
                'available': loc.available
            })

        # Get stats
        stats = self.get_stats()
        info['stats'] = {
            'main_db_size': stats.main_db_size,
            'blobs_db_size': stats.blobs_db_size,
            'total_libraries': stats.total_libraries,
            'total_items': stats.total_items,
            'total_watched': stats.total_watched,
            'total_collections': stats.total_collections,
            'total_playlists': stats.total_playlists
        }

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2)
            return True
        except Exception:
            return False

    def get_watch_history(self) -> List[Dict[str, Any]]:
        """Get watch history for all items"""
        history = []

        if not self._conn:
            if not self.connect():
                return history

        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT
                    mi.title,
                    mi.metadata_type,
                    mis.view_count,
                    mis.last_viewed_at,
                    mis.view_offset
                FROM metadata_item_settings mis
                JOIN metadata_items mi ON mi.id = mis.metadata_item_id
                WHERE mis.view_count > 0
                ORDER BY mis.last_viewed_at DESC
                LIMIT 1000
            """)

            for row in cursor.fetchall():
                history.append({
                    'title': row['title'],
                    'type': row['metadata_type'],
                    'view_count': row['view_count'],
                    'last_viewed': row['last_viewed_at'],
                    'offset': row['view_offset']
                })

        except sqlite3.Error:
            pass

        return history

    def calculate_checksum(self, db_path: str) -> str:
        """Calculate MD5 checksum of database file"""
        hash_md5 = hashlib.md5()
        try:
            with open(db_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""

    def vacuum_database(self, db_path: str) -> bool:
        """Vacuum database to optimize size"""
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("VACUUM")
            conn.close()
            return True
        except sqlite3.Error:
            return False
