"""
Compression Module
Handles backup compression and decompression
"""

import os
import shutil
import zipfile
import tarfile
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Callable, Generator
from enum import Enum


class CompressionFormat(Enum):
    """Supported compression formats"""
    NONE = "none"
    ZIP = "zip"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TAR_XZ = "tar.xz"
    SEVEN_ZIP = "7z"


@dataclass
class CompressionProgress:
    """Progress of compression operation"""
    status: str = "idle"
    current_file: str = ""
    files_total: int = 0
    files_done: int = 0
    bytes_total: int = 0
    bytes_done: int = 0

    @property
    def percent(self) -> float:
        if self.files_total == 0:
            return 0
        return (self.files_done / self.files_total) * 100


class CompressionManager:
    """
    Handles compression and decompression of Plex backups
    Supports ZIP, TAR.GZ, TAR.BZ2, TAR.XZ, and 7-Zip formats
    """

    EXTENSIONS = {
        CompressionFormat.ZIP: ".zip",
        CompressionFormat.TAR_GZ: ".tar.gz",
        CompressionFormat.TAR_BZ2: ".tar.bz2",
        CompressionFormat.TAR_XZ: ".tar.xz",
        CompressionFormat.SEVEN_ZIP: ".7z"
    }

    def __init__(self):
        self.progress = CompressionProgress()
        self._callbacks: List[Callable[[CompressionProgress], None]] = []
        self._cancelled = False

    def add_progress_callback(self, callback: Callable[[CompressionProgress], None]) -> None:
        """Add callback for progress updates"""
        self._callbacks.append(callback)

    def _notify_progress(self) -> None:
        """Notify callbacks of progress"""
        for callback in self._callbacks:
            try:
                callback(self.progress)
            except Exception:
                pass

    def get_extension(self, format: CompressionFormat) -> str:
        """Get file extension for format"""
        return self.EXTENSIONS.get(format, "")

    def detect_format(self, filepath: str) -> CompressionFormat:
        """Detect compression format from file path"""
        lower = filepath.lower()
        if lower.endswith('.zip'):
            return CompressionFormat.ZIP
        elif lower.endswith('.tar.gz') or lower.endswith('.tgz'):
            return CompressionFormat.TAR_GZ
        elif lower.endswith('.tar.bz2') or lower.endswith('.tbz2'):
            return CompressionFormat.TAR_BZ2
        elif lower.endswith('.tar.xz') or lower.endswith('.txz'):
            return CompressionFormat.TAR_XZ
        elif lower.endswith('.7z'):
            return CompressionFormat.SEVEN_ZIP
        return CompressionFormat.NONE

    def _count_files(self, directory: str) -> tuple:
        """Count files and total size in directory"""
        count = 0
        size = 0
        for root, _, files in os.walk(directory):
            for file in files:
                count += 1
                try:
                    size += os.path.getsize(os.path.join(root, file))
                except OSError:
                    pass
        return count, size

    def compress_directory(self,
                          source_dir: str,
                          output_path: str,
                          format: CompressionFormat,
                          compression_level: int = 6) -> bool:
        """
        Compress a directory

        Args:
            source_dir: Directory to compress
            output_path: Output archive path
            format: Compression format
            compression_level: Compression level (1-9, where 9 is max)

        Returns:
            True if successful
        """
        self._cancelled = False
        self.progress = CompressionProgress(status="counting")
        self._notify_progress()

        # Count files
        self.progress.files_total, self.progress.bytes_total = self._count_files(source_dir)
        self.progress.status = "compressing"
        self._notify_progress()

        try:
            if format == CompressionFormat.ZIP:
                return self._compress_zip(source_dir, output_path, compression_level)
            elif format in (CompressionFormat.TAR_GZ, CompressionFormat.TAR_BZ2,
                          CompressionFormat.TAR_XZ):
                return self._compress_tar(source_dir, output_path, format, compression_level)
            elif format == CompressionFormat.SEVEN_ZIP:
                return self._compress_7z(source_dir, output_path, compression_level)
            else:
                return False

        except Exception as e:
            self.progress.status = f"error: {str(e)}"
            self._notify_progress()
            return False

    def _compress_zip(self, source_dir: str, output_path: str,
                     compression_level: int) -> bool:
        """Compress using ZIP format"""
        compression = zipfile.ZIP_DEFLATED

        with zipfile.ZipFile(output_path, 'w', compression,
                            compresslevel=compression_level) as zf:
            for root, _, files in os.walk(source_dir):
                if self._cancelled:
                    return False

                for file in files:
                    if self._cancelled:
                        return False

                    filepath = os.path.join(root, file)
                    arcname = os.path.relpath(filepath, source_dir)

                    self.progress.current_file = file
                    self._notify_progress()

                    try:
                        zf.write(filepath, arcname)
                        self.progress.files_done += 1
                        self.progress.bytes_done += os.path.getsize(filepath)
                    except (PermissionError, OSError):
                        pass

                    self._notify_progress()

        self.progress.status = "completed"
        self._notify_progress()
        return True

    def _compress_tar(self, source_dir: str, output_path: str,
                     format: CompressionFormat, compression_level: int) -> bool:
        """Compress using TAR format with various compression"""
        mode_map = {
            CompressionFormat.TAR_GZ: f"w:gz",
            CompressionFormat.TAR_BZ2: f"w:bz2",
            CompressionFormat.TAR_XZ: f"w:xz"
        }

        mode = mode_map.get(format, "w:gz")

        with tarfile.open(output_path, mode) as tf:
            for root, _, files in os.walk(source_dir):
                if self._cancelled:
                    return False

                for file in files:
                    if self._cancelled:
                        return False

                    filepath = os.path.join(root, file)
                    arcname = os.path.relpath(filepath, source_dir)

                    self.progress.current_file = file
                    self._notify_progress()

                    try:
                        tf.add(filepath, arcname)
                        self.progress.files_done += 1
                        self.progress.bytes_done += os.path.getsize(filepath)
                    except (PermissionError, OSError):
                        pass

                    self._notify_progress()

        self.progress.status = "completed"
        self._notify_progress()
        return True

    def _compress_7z(self, source_dir: str, output_path: str,
                    compression_level: int) -> bool:
        """Compress using 7-Zip format"""
        try:
            import py7zr

            with py7zr.SevenZipFile(output_path, 'w') as sz:
                for root, _, files in os.walk(source_dir):
                    if self._cancelled:
                        return False

                    for file in files:
                        if self._cancelled:
                            return False

                        filepath = os.path.join(root, file)
                        arcname = os.path.relpath(filepath, source_dir)

                        self.progress.current_file = file
                        self._notify_progress()

                        try:
                            sz.write(filepath, arcname)
                            self.progress.files_done += 1
                            self.progress.bytes_done += os.path.getsize(filepath)
                        except (PermissionError, OSError):
                            pass

                        self._notify_progress()

            self.progress.status = "completed"
            self._notify_progress()
            return True

        except ImportError:
            self.progress.status = "error: py7zr not installed"
            self._notify_progress()
            return False

    def decompress(self, archive_path: str, output_dir: str) -> bool:
        """
        Decompress an archive

        Args:
            archive_path: Path to archive file
            output_dir: Directory to extract to

        Returns:
            True if successful
        """
        self._cancelled = False
        format = self.detect_format(archive_path)

        self.progress = CompressionProgress(status="extracting")
        self._notify_progress()

        try:
            os.makedirs(output_dir, exist_ok=True)

            if format == CompressionFormat.ZIP:
                return self._decompress_zip(archive_path, output_dir)
            elif format in (CompressionFormat.TAR_GZ, CompressionFormat.TAR_BZ2,
                          CompressionFormat.TAR_XZ):
                return self._decompress_tar(archive_path, output_dir)
            elif format == CompressionFormat.SEVEN_ZIP:
                return self._decompress_7z(archive_path, output_dir)
            else:
                self.progress.status = "error: unknown format"
                return False

        except Exception as e:
            self.progress.status = f"error: {str(e)}"
            self._notify_progress()
            return False

    def _decompress_zip(self, archive_path: str, output_dir: str) -> bool:
        """Decompress ZIP archive"""
        with zipfile.ZipFile(archive_path, 'r') as zf:
            members = zf.namelist()
            self.progress.files_total = len(members)
            self._notify_progress()

            for member in members:
                if self._cancelled:
                    return False

                self.progress.current_file = os.path.basename(member)
                self._notify_progress()

                zf.extract(member, output_dir)
                self.progress.files_done += 1
                self._notify_progress()

        self.progress.status = "completed"
        self._notify_progress()
        return True

    def _decompress_tar(self, archive_path: str, output_dir: str) -> bool:
        """Decompress TAR archive"""
        with tarfile.open(archive_path, 'r:*') as tf:
            members = tf.getmembers()
            self.progress.files_total = len(members)
            self._notify_progress()

            for member in members:
                if self._cancelled:
                    return False

                self.progress.current_file = os.path.basename(member.name)
                self._notify_progress()

                tf.extract(member, output_dir)
                self.progress.files_done += 1
                self._notify_progress()

        self.progress.status = "completed"
        self._notify_progress()
        return True

    def _decompress_7z(self, archive_path: str, output_dir: str) -> bool:
        """Decompress 7-Zip archive"""
        try:
            import py7zr

            with py7zr.SevenZipFile(archive_path, 'r') as sz:
                self.progress.files_total = len(sz.getnames())
                self._notify_progress()

                sz.extractall(output_dir)
                self.progress.files_done = self.progress.files_total

            self.progress.status = "completed"
            self._notify_progress()
            return True

        except ImportError:
            self.progress.status = "error: py7zr not installed"
            self._notify_progress()
            return False

    def cancel(self) -> None:
        """Cancel current operation"""
        self._cancelled = True

    def get_archive_info(self, archive_path: str) -> dict:
        """Get information about an archive"""
        format = self.detect_format(archive_path)
        info = {
            'path': archive_path,
            'format': format.value,
            'size': os.path.getsize(archive_path) if os.path.exists(archive_path) else 0,
            'files': [],
            'total_uncompressed': 0
        }

        try:
            if format == CompressionFormat.ZIP:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    for zi in zf.infolist():
                        info['files'].append({
                            'name': zi.filename,
                            'size': zi.file_size,
                            'compressed': zi.compress_size
                        })
                        info['total_uncompressed'] += zi.file_size

            elif format in (CompressionFormat.TAR_GZ, CompressionFormat.TAR_BZ2,
                          CompressionFormat.TAR_XZ):
                with tarfile.open(archive_path, 'r:*') as tf:
                    for ti in tf.getmembers():
                        if ti.isfile():
                            info['files'].append({
                                'name': ti.name,
                                'size': ti.size
                            })
                            info['total_uncompressed'] += ti.size

            elif format == CompressionFormat.SEVEN_ZIP:
                try:
                    import py7zr
                    with py7zr.SevenZipFile(archive_path, 'r') as sz:
                        for entry in sz.list():
                            info['files'].append({
                                'name': entry.filename,
                                'size': entry.uncompressed
                            })
                            info['total_uncompressed'] += entry.uncompressed
                except ImportError:
                    pass

        except Exception:
            pass

        return info


def estimate_compressed_size(uncompressed_size: int,
                            format: CompressionFormat) -> int:
    """Estimate compressed size based on format and typical compression ratios"""
    ratios = {
        CompressionFormat.NONE: 1.0,
        CompressionFormat.ZIP: 0.6,
        CompressionFormat.TAR_GZ: 0.55,
        CompressionFormat.TAR_BZ2: 0.5,
        CompressionFormat.TAR_XZ: 0.45,
        CompressionFormat.SEVEN_ZIP: 0.4
    }
    ratio = ratios.get(format, 1.0)
    return int(uncompressed_size * ratio)
