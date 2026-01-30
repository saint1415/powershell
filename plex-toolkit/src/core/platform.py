"""
Platform Detection Module
Detects operating system and architecture for cross-platform compatibility
"""

import platform
import os
import sys
import subprocess
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class OSType(Enum):
    """Operating system types"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    FREEBSD = "freebsd"
    SYNOLOGY = "synology"
    QNAP = "qnap"
    UNRAID = "unraid"
    TRUENAS = "truenas"
    UNKNOWN = "unknown"


class Architecture(Enum):
    """CPU architecture types"""
    X86_64 = "x86_64"
    X86 = "x86"
    ARM64 = "arm64"
    ARM = "arm"
    UNKNOWN = "unknown"


class ContainerType(Enum):
    """Container/virtualization types"""
    NONE = "none"
    DOCKER = "docker"
    LXC = "lxc"
    VM = "vm"
    JAIL = "jail"
    UNKNOWN = "unknown"


@dataclass
class PlatformInfo:
    """Complete platform information"""
    os_type: OSType
    os_name: str
    os_version: str
    architecture: Architecture
    container_type: ContainerType
    hostname: str
    is_admin: bool
    python_version: str
    home_dir: str
    temp_dir: str
    plex_user: Optional[str] = None
    nas_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'os_type': self.os_type.value,
            'os_name': self.os_name,
            'os_version': self.os_version,
            'architecture': self.architecture.value,
            'container_type': self.container_type.value,
            'hostname': self.hostname,
            'is_admin': self.is_admin,
            'python_version': self.python_version,
            'home_dir': self.home_dir,
            'temp_dir': self.temp_dir,
            'plex_user': self.plex_user,
            'nas_type': self.nas_type
        }


class PlatformDetector:
    """
    Detects and provides information about the current platform
    Supports Windows, Linux, macOS, and NAS devices (Synology, QNAP, Unraid, TrueNAS)
    """

    def __init__(self):
        self._info: Optional[PlatformInfo] = None

    @property
    def info(self) -> PlatformInfo:
        """Get platform information (cached)"""
        if self._info is None:
            self._info = self._detect_platform()
        return self._info

    def _detect_platform(self) -> PlatformInfo:
        """Detect comprehensive platform information"""
        os_type = self._detect_os_type()

        return PlatformInfo(
            os_type=os_type,
            os_name=platform.system(),
            os_version=platform.release(),
            architecture=self._detect_architecture(),
            container_type=self._detect_container(),
            hostname=platform.node(),
            is_admin=self._check_admin(),
            python_version=platform.python_version(),
            home_dir=os.path.expanduser("~"),
            temp_dir=self._get_temp_dir(),
            plex_user=self._detect_plex_user(os_type),
            nas_type=self._detect_nas_type() if os_type == OSType.LINUX else None
        )

    def _detect_os_type(self) -> OSType:
        """Detect the operating system type"""
        system = platform.system().lower()

        if system == "windows":
            return OSType.WINDOWS
        elif system == "darwin":
            return OSType.MACOS
        elif system == "linux":
            # Check for NAS distributions
            nas_type = self._detect_nas_type()
            if nas_type:
                return OSType[nas_type.upper()]
            return OSType.LINUX
        elif system == "freebsd":
            # Could be TrueNAS/FreeNAS
            if self._is_truenas():
                return OSType.TRUENAS
            return OSType.FREEBSD
        else:
            return OSType.UNKNOWN

    def _detect_nas_type(self) -> Optional[str]:
        """Detect if running on a NAS device"""
        # Check for Synology
        if os.path.exists("/etc/synoinfo.conf"):
            return "synology"

        # Check for QNAP
        if os.path.exists("/etc/config/qpkg.conf"):
            return "qnap"

        # Check for Unraid
        if os.path.exists("/boot/config/ident.cfg"):
            return "unraid"

        # Check for TrueNAS/FreeNAS via version file
        for path in ["/etc/version", "/etc/truenas_version"]:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        content = f.read().lower()
                        if 'truenas' in content or 'freenas' in content:
                            return "truenas"
                except:
                    pass

        return None

    def _is_truenas(self) -> bool:
        """Check if running on TrueNAS"""
        return self._detect_nas_type() == "truenas"

    def _detect_architecture(self) -> Architecture:
        """Detect CPU architecture"""
        machine = platform.machine().lower()

        if machine in ('x86_64', 'amd64'):
            return Architecture.X86_64
        elif machine in ('i386', 'i686', 'x86'):
            return Architecture.X86
        elif machine in ('aarch64', 'arm64'):
            return Architecture.ARM64
        elif machine.startswith('arm'):
            return Architecture.ARM
        else:
            return Architecture.UNKNOWN

    def _detect_container(self) -> ContainerType:
        """Detect if running inside a container"""
        # Check for Docker
        if os.path.exists("/.dockerenv"):
            return ContainerType.DOCKER

        # Check cgroup for Docker
        try:
            with open("/proc/1/cgroup", 'r') as f:
                if 'docker' in f.read():
                    return ContainerType.DOCKER
        except:
            pass

        # Check for LXC
        try:
            with open("/proc/1/environ", 'rb') as f:
                if b'container=lxc' in f.read():
                    return ContainerType.LXC
        except:
            pass

        # Check for FreeBSD jail
        if platform.system().lower() == "freebsd":
            try:
                result = subprocess.run(['sysctl', 'security.jail.jailed'],
                                       capture_output=True, text=True)
                if 'security.jail.jailed: 1' in result.stdout:
                    return ContainerType.JAIL
            except:
                pass

        # Check for VM (basic detection)
        try:
            if os.path.exists("/sys/class/dmi/id/product_name"):
                with open("/sys/class/dmi/id/product_name", 'r') as f:
                    product = f.read().lower()
                    if any(vm in product for vm in ['vmware', 'virtualbox', 'kvm', 'qemu', 'hyper-v']):
                        return ContainerType.VM
        except:
            pass

        return ContainerType.NONE

    def _check_admin(self) -> bool:
        """Check if running with admin/root privileges"""
        if platform.system().lower() == "windows":
            try:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except:
                return False
        else:
            return os.geteuid() == 0

    def _get_temp_dir(self) -> str:
        """Get temporary directory path"""
        import tempfile
        return tempfile.gettempdir()

    def _detect_plex_user(self, os_type: OSType) -> Optional[str]:
        """Detect the Plex user on the system"""
        if os_type == OSType.WINDOWS:
            return os.environ.get('USERNAME')

        # Linux/macOS - check for plex user
        try:
            import pwd
            for user in ['plex', 'plexmediaserver']:
                try:
                    pwd.getpwnam(user)
                    return user
                except KeyError:
                    continue
            # Fall back to current user
            return os.environ.get('USER')
        except:
            return os.environ.get('USER')

    def get_service_manager(self) -> str:
        """Determine the service manager used on the system"""
        if self.info.os_type == OSType.WINDOWS:
            return "windows_service"
        elif self.info.os_type == OSType.MACOS:
            return "launchctl"
        elif self.info.os_type == OSType.SYNOLOGY:
            return "synopkg"
        elif self.info.os_type == OSType.QNAP:
            return "qpkg"
        elif self.info.os_type == OSType.UNRAID:
            return "unraid_docker"
        elif self.info.os_type == OSType.TRUENAS:
            return "truenas_jail"
        else:
            # Check for systemd
            if os.path.exists("/run/systemd/system"):
                return "systemd"
            # Check for init.d
            elif os.path.exists("/etc/init.d"):
                return "sysvinit"
            else:
                return "unknown"

    def get_plex_service_commands(self) -> Dict[str, str]:
        """Get platform-specific Plex service commands"""
        service_manager = self.get_service_manager()

        commands = {
            "windows_service": {
                "start": "net start PlexService",
                "stop": "net stop PlexService",
                "status": "sc query PlexService",
                "service_name": "PlexService"
            },
            "launchctl": {
                "start": "launchctl load /Library/LaunchDaemons/com.plexapp.plexmediaserver.plist",
                "stop": "launchctl unload /Library/LaunchDaemons/com.plexapp.plexmediaserver.plist",
                "status": "launchctl list | grep plex",
                "service_name": "com.plexapp.plexmediaserver"
            },
            "systemd": {
                "start": "systemctl start plexmediaserver",
                "stop": "systemctl stop plexmediaserver",
                "status": "systemctl status plexmediaserver",
                "service_name": "plexmediaserver"
            },
            "sysvinit": {
                "start": "/etc/init.d/plexmediaserver start",
                "stop": "/etc/init.d/plexmediaserver stop",
                "status": "/etc/init.d/plexmediaserver status",
                "service_name": "plexmediaserver"
            },
            "synopkg": {
                "start": "synopkg start PlexMediaServer",
                "stop": "synopkg stop PlexMediaServer",
                "status": "synopkg status PlexMediaServer",
                "service_name": "PlexMediaServer"
            },
            "qpkg": {
                "start": "/etc/init.d/plex.sh start",
                "stop": "/etc/init.d/plex.sh stop",
                "status": "/etc/init.d/plex.sh status",
                "service_name": "PlexMediaServer"
            },
            "unraid_docker": {
                "start": "docker start plex",
                "stop": "docker stop plex",
                "status": "docker ps | grep plex",
                "service_name": "plex"
            },
            "truenas_jail": {
                "start": "iocage exec plex service plexmediaserver_plexpass start",
                "stop": "iocage exec plex service plexmediaserver_plexpass stop",
                "status": "iocage exec plex service plexmediaserver_plexpass status",
                "service_name": "plexmediaserver_plexpass"
            }
        }

        return commands.get(service_manager, commands["systemd"])

    def is_compatible(self) -> bool:
        """Check if platform is compatible with this tool"""
        return self.info.os_type != OSType.UNKNOWN

    def __str__(self) -> str:
        """String representation of platform"""
        return (f"{self.info.os_name} {self.info.os_version} "
                f"({self.info.architecture.value}) - "
                f"{'Admin' if self.info.is_admin else 'User'}")


# Singleton instance
_detector: Optional[PlatformDetector] = None

def get_platform() -> PlatformDetector:
    """Get the platform detector singleton"""
    global _detector
    if _detector is None:
        _detector = PlatformDetector()
    return _detector
