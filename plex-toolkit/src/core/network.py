"""
Network Discovery Module
Discovers Plex servers and enables network-based migration
"""

import socket
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import struct

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ServiceInfo
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

try:
    import netifaces
    NETIFACES_AVAILABLE = True
except ImportError:
    NETIFACES_AVAILABLE = False


class MachineRole(Enum):
    """Role of machine in migration"""
    SOURCE = "source"  # Old server (sending data)
    TARGET = "target"  # New server (receiving data)
    STANDALONE = "standalone"  # Not in migration mode


class ConnectionStatus(Enum):
    """Connection status between machines"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    TRANSFERRING = "transferring"
    ERROR = "error"


@dataclass
class NetworkHost:
    """Represents a discovered network host"""
    ip: str
    hostname: str
    port: int = 32400
    machine_id: Optional[str] = None
    server_name: Optional[str] = None
    platform: Optional[str] = None
    version: Optional[str] = None
    is_plex: bool = False
    toolkit_port: Optional[int] = None  # Port for migration toolkit
    toolkit_version: Optional[str] = None
    role: MachineRole = MachineRole.STANDALONE
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'ip': self.ip,
            'hostname': self.hostname,
            'port': self.port,
            'machine_id': self.machine_id,
            'server_name': self.server_name,
            'platform': self.platform,
            'version': self.version,
            'is_plex': self.is_plex,
            'toolkit_port': self.toolkit_port,
            'toolkit_version': self.toolkit_version,
            'role': self.role.value,
            'last_seen': self.last_seen
        }


@dataclass
class TransferProgress:
    """Progress of a network transfer"""
    total_bytes: int = 0
    transferred_bytes: int = 0
    current_file: str = ""
    files_total: int = 0
    files_done: int = 0
    speed_bps: float = 0
    eta_seconds: float = 0
    status: str = "idle"

    @property
    def percent(self) -> float:
        if self.total_bytes == 0:
            return 0
        return (self.transferred_bytes / self.total_bytes) * 100


class PlexServiceListener(ServiceListener):
    """Listener for Plex mDNS service discovery"""

    def __init__(self, on_found: Callable[[NetworkHost], None]):
        self.on_found = on_found

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            self._process_service(info)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            self._process_service(info)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def _process_service(self, info: ServiceInfo) -> None:
        addresses = info.parsed_addresses()
        if not addresses:
            return

        host = NetworkHost(
            ip=addresses[0],
            hostname=info.server or addresses[0],
            port=info.port,
            is_plex=True
        )

        # Extract properties
        props = info.properties
        if props:
            host.machine_id = props.get(b'Resource-Identifier', b'').decode('utf-8', errors='ignore')
            host.server_name = props.get(b'Name', b'').decode('utf-8', errors='ignore')
            host.version = props.get(b'Version', b'').decode('utf-8', errors='ignore')
            host.platform = props.get(b'Platform', b'').decode('utf-8', errors='ignore')

        self.on_found(host)


class NetworkDiscovery:
    """
    Discovers Plex servers and migration toolkit instances on the network
    Supports mDNS/DNS-SD, UDP broadcast, and direct IP scanning
    """

    PLEX_SERVICE_TYPE = "_plexmediasvr._tcp.local."
    TOOLKIT_SERVICE_TYPE = "_plextoolkit._tcp.local."
    TOOLKIT_PORT = 52400  # Default port for toolkit communication
    BROADCAST_PORT = 52401  # UDP broadcast port

    def __init__(self):
        self.discovered_hosts: Dict[str, NetworkHost] = {}
        self.local_ip: Optional[str] = None
        self.local_hostname: str = socket.gethostname()
        self.instance_id: str = str(uuid.uuid4())[:8]
        self.role: MachineRole = MachineRole.STANDALONE
        self._zeroconf: Optional[Zeroconf] = None
        self._browser: Optional[ServiceBrowser] = None
        self._running: bool = False
        self._discovery_thread: Optional[threading.Thread] = None
        self._server_socket: Optional[socket.socket] = None
        self._callbacks: List[Callable[[NetworkHost], None]] = []

    def add_callback(self, callback: Callable[[NetworkHost], None]) -> None:
        """Add callback for when hosts are discovered"""
        self._callbacks.append(callback)

    def _notify_callbacks(self, host: NetworkHost) -> None:
        """Notify all callbacks of discovered host"""
        for callback in self._callbacks:
            try:
                callback(host)
            except Exception:
                pass

    def get_local_ip(self) -> str:
        """Get local IP address"""
        if self.local_ip:
            return self.local_ip

        try:
            # Try using netifaces for more reliable results
            if NETIFACES_AVAILABLE:
                for interface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            ip = addr['addr']
                            if not ip.startswith('127.'):
                                self.local_ip = ip
                                return ip
        except Exception:
            pass

        # Fallback: connect to external host to find local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.local_ip = s.getsockname()[0]
            s.close()
            return self.local_ip
        except Exception:
            self.local_ip = "127.0.0.1"
            return self.local_ip

    def get_network_interfaces(self) -> List[Dict[str, str]]:
        """Get list of network interfaces"""
        interfaces = []

        if NETIFACES_AVAILABLE:
            for iface in netifaces.interfaces():
                try:
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            interfaces.append({
                                'name': iface,
                                'ip': addr['addr'],
                                'netmask': addr.get('netmask', ''),
                                'broadcast': addr.get('broadcast', '')
                            })
                except Exception:
                    pass

        return interfaces

    def start_discovery(self) -> bool:
        """Start network discovery"""
        if self._running:
            return True

        self._running = True
        self._discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self._discovery_thread.start()

        # Start mDNS discovery if available
        if ZEROCONF_AVAILABLE:
            try:
                self._zeroconf = Zeroconf()
                listener = PlexServiceListener(self._on_host_discovered)
                self._browser = ServiceBrowser(
                    self._zeroconf,
                    [self.PLEX_SERVICE_TYPE, self.TOOLKIT_SERVICE_TYPE],
                    listener
                )
            except Exception:
                pass

        return True

    def stop_discovery(self) -> None:
        """Stop network discovery"""
        self._running = False

        if self._browser:
            self._browser.cancel()
            self._browser = None

        if self._zeroconf:
            self._zeroconf.close()
            self._zeroconf = None

        if self._server_socket:
            self._server_socket.close()
            self._server_socket = None

    def _discovery_loop(self) -> None:
        """Main discovery loop"""
        while self._running:
            # Send broadcast announcement
            self._send_broadcast()

            # Listen for responses
            self._listen_broadcasts()

            # Scan common Plex ports on local subnet
            self._scan_subnet()

            # Clean up stale hosts
            self._cleanup_stale_hosts()

            time.sleep(5)

    def _send_broadcast(self) -> None:
        """Send UDP broadcast to announce presence"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(1)

            message = json.dumps({
                'type': 'plex_toolkit_announce',
                'version': '2.0.0',
                'instance_id': self.instance_id,
                'hostname': self.local_hostname,
                'ip': self.get_local_ip(),
                'port': self.TOOLKIT_PORT,
                'role': self.role.value
            }).encode('utf-8')

            sock.sendto(message, ('<broadcast>', self.BROADCAST_PORT))
            sock.close()
        except Exception:
            pass

    def _listen_broadcasts(self) -> None:
        """Listen for broadcast announcements from other instances"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(2)
            sock.bind(('', self.BROADCAST_PORT))

            try:
                while self._running:
                    try:
                        data, addr = sock.recvfrom(1024)
                        message = json.loads(data.decode('utf-8'))

                        if message.get('type') == 'plex_toolkit_announce':
                            if message.get('instance_id') != self.instance_id:
                                host = NetworkHost(
                                    ip=message.get('ip', addr[0]),
                                    hostname=message.get('hostname', addr[0]),
                                    toolkit_port=message.get('port'),
                                    toolkit_version=message.get('version'),
                                    role=MachineRole(message.get('role', 'standalone')),
                                    last_seen=time.time()
                                )
                                self._on_host_discovered(host)
                    except socket.timeout:
                        break
                    except json.JSONDecodeError:
                        continue
            finally:
                sock.close()
        except Exception:
            pass

    def _scan_subnet(self) -> None:
        """Scan local subnet for Plex servers"""
        local_ip = self.get_local_ip()
        if local_ip == "127.0.0.1":
            return

        # Get subnet (assuming /24)
        parts = local_ip.split('.')
        if len(parts) != 4:
            return

        subnet = '.'.join(parts[:3])

        # Scan a subset of IPs to avoid being too slow
        for i in range(1, 255, 10):  # Check every 10th IP
            if not self._running:
                break
            ip = f"{subnet}.{i}"
            if ip != local_ip:
                self._check_plex_port(ip)

    def _check_plex_port(self, ip: str, port: int = 32400) -> None:
        """Check if IP has Plex running"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((ip, port))
            sock.close()

            if result == 0:
                # Port is open, try to verify it's Plex
                host = NetworkHost(
                    ip=ip,
                    hostname=ip,
                    port=port,
                    is_plex=True,
                    last_seen=time.time()
                )
                self._on_host_discovered(host)
        except Exception:
            pass

    def _on_host_discovered(self, host: NetworkHost) -> None:
        """Handle discovered host"""
        key = f"{host.ip}:{host.port or host.toolkit_port or 32400}"

        # Update or add host
        if key in self.discovered_hosts:
            existing = self.discovered_hosts[key]
            existing.last_seen = time.time()
            # Update with new info if available
            if host.server_name:
                existing.server_name = host.server_name
            if host.machine_id:
                existing.machine_id = host.machine_id
            if host.toolkit_port:
                existing.toolkit_port = host.toolkit_port
            if host.role != MachineRole.STANDALONE:
                existing.role = host.role
        else:
            self.discovered_hosts[key] = host
            self._notify_callbacks(host)

    def _cleanup_stale_hosts(self) -> None:
        """Remove hosts not seen recently"""
        cutoff = time.time() - 60  # 60 seconds timeout
        stale_keys = [
            key for key, host in self.discovered_hosts.items()
            if host.last_seen < cutoff
        ]
        for key in stale_keys:
            del self.discovered_hosts[key]

    def get_discovered_hosts(self) -> List[NetworkHost]:
        """Get list of discovered hosts"""
        return list(self.discovered_hosts.values())

    def get_plex_servers(self) -> List[NetworkHost]:
        """Get discovered Plex servers"""
        return [h for h in self.discovered_hosts.values() if h.is_plex]

    def get_toolkit_instances(self) -> List[NetworkHost]:
        """Get discovered toolkit instances"""
        return [h for h in self.discovered_hosts.values() if h.toolkit_port]

    def set_role(self, role: MachineRole) -> None:
        """Set the role of this machine"""
        self.role = role

    def find_partner(self) -> Optional[NetworkHost]:
        """Find a compatible partner for migration"""
        for host in self.get_toolkit_instances():
            if host.role != self.role and host.role != MachineRole.STANDALONE:
                return host
        return None

    def announce_as_source(self) -> None:
        """Announce this machine as the source (old server)"""
        self.set_role(MachineRole.SOURCE)
        self._send_broadcast()

    def announce_as_target(self) -> None:
        """Announce this machine as the target (new server)"""
        self.set_role(MachineRole.TARGET)
        self._send_broadcast()


class NetworkTransfer:
    """Handles network transfer of Plex data between machines"""

    CHUNK_SIZE = 1024 * 1024  # 1MB chunks

    def __init__(self, source_host: Optional[NetworkHost] = None,
                 target_host: Optional[NetworkHost] = None):
        self.source_host = source_host
        self.target_host = target_host
        self.progress = TransferProgress()
        self._running = False
        self._callbacks: List[Callable[[TransferProgress], None]] = []

    def add_progress_callback(self, callback: Callable[[TransferProgress], None]) -> None:
        """Add callback for progress updates"""
        self._callbacks.append(callback)

    def _notify_progress(self) -> None:
        """Notify callbacks of progress update"""
        for callback in self._callbacks:
            try:
                callback(self.progress)
            except Exception:
                pass

    def estimate_transfer_time(self, total_bytes: int, speed_mbps: float = 100) -> float:
        """Estimate transfer time in seconds"""
        speed_bps = speed_mbps * 1024 * 1024 / 8
        return total_bytes / speed_bps

    def start_server(self, port: int = 52400) -> socket.socket:
        """Start transfer server"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', port))
        server.listen(1)
        return server

    def connect_to_server(self, host: str, port: int) -> socket.socket:
        """Connect to transfer server"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        return sock

    def send_file(self, sock: socket.socket, filepath: str) -> bool:
        """Send a file over the network"""
        try:
            import os

            filesize = os.path.getsize(filepath)
            filename = os.path.basename(filepath)

            # Send header
            header = json.dumps({
                'type': 'file',
                'name': filename,
                'size': filesize
            }).encode('utf-8')

            sock.send(struct.pack('!I', len(header)))
            sock.send(header)

            # Send file data
            self.progress.current_file = filename
            sent = 0

            with open(filepath, 'rb') as f:
                while sent < filesize:
                    data = f.read(self.CHUNK_SIZE)
                    if not data:
                        break
                    sock.sendall(data)
                    sent += len(data)
                    self.progress.transferred_bytes += len(data)
                    self._notify_progress()

            self.progress.files_done += 1
            return True

        except Exception as e:
            self.progress.status = f"Error: {str(e)}"
            return False

    def receive_file(self, sock: socket.socket, output_dir: str) -> Optional[str]:
        """Receive a file from the network"""
        try:
            import os

            # Receive header length
            header_len_data = sock.recv(4)
            if not header_len_data:
                return None

            header_len = struct.unpack('!I', header_len_data)[0]

            # Receive header
            header_data = sock.recv(header_len)
            header = json.loads(header_data.decode('utf-8'))

            if header.get('type') != 'file':
                return None

            filename = header['name']
            filesize = header['size']

            filepath = os.path.join(output_dir, filename)
            self.progress.current_file = filename

            # Receive file data
            received = 0
            with open(filepath, 'wb') as f:
                while received < filesize:
                    chunk_size = min(self.CHUNK_SIZE, filesize - received)
                    data = sock.recv(chunk_size)
                    if not data:
                        break
                    f.write(data)
                    received += len(data)
                    self.progress.transferred_bytes += len(data)
                    self._notify_progress()

            self.progress.files_done += 1
            return filepath

        except Exception as e:
            self.progress.status = f"Error: {str(e)}"
            return None

    def cancel(self) -> None:
        """Cancel current transfer"""
        self._running = False
        self.progress.status = "Cancelled"


class SSHTransfer:
    """Transfer files using SSH/SCP"""

    def __init__(self, host: str, username: str,
                 password: Optional[str] = None,
                 key_file: Optional[str] = None):
        self.host = host
        self.username = username
        self.password = password
        self.key_file = key_file
        self._client = None
        self._sftp = None

    def connect(self) -> bool:
        """Establish SSH connection"""
        try:
            import paramiko

            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if self.key_file:
                key = paramiko.RSAKey.from_private_key_file(self.key_file)
                self._client.connect(self.host, username=self.username, pkey=key)
            else:
                self._client.connect(self.host, username=self.username,
                                   password=self.password)

            self._sftp = self._client.open_sftp()
            return True

        except Exception:
            return False

    def disconnect(self) -> None:
        """Close SSH connection"""
        if self._sftp:
            self._sftp.close()
        if self._client:
            self._client.close()

    def upload_file(self, local_path: str, remote_path: str,
                   callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """Upload file via SFTP"""
        if not self._sftp:
            return False

        try:
            self._sftp.put(local_path, remote_path, callback=callback)
            return True
        except Exception:
            return False

    def download_file(self, remote_path: str, local_path: str,
                     callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """Download file via SFTP"""
        if not self._sftp:
            return False

        try:
            self._sftp.get(remote_path, local_path, callback=callback)
            return True
        except Exception:
            return False

    def execute_command(self, command: str) -> tuple:
        """Execute remote command"""
        if not self._client:
            return (None, None, None)

        try:
            stdin, stdout, stderr = self._client.exec_command(command)
            return (
                stdin,
                stdout.read().decode('utf-8'),
                stderr.read().decode('utf-8')
            )
        except Exception:
            return (None, None, None)
