# Plex Migration Toolkit

A powerful, cross-platform tool for backing up and migrating Plex Media Server data between machines and operating systems.

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

### Cross-Platform Support
- **Windows 10/11** - Full GUI and CLI support
- **Linux** - Ubuntu, Debian, Fedora, Arch, and NAS distributions
- **macOS** - Intel and Apple Silicon
- **NAS Devices** - Synology, QNAP, Unraid, TrueNAS

### Backup Modes
- **Hot Copy** - Backup while Plex is running (fastest, may miss locked files)
- **Cold Copy** - Stop Plex for most reliable backup
- **Smart Sync** - Hot copy + cold differential sync (recommended)
- **Incremental** - Only backup changed files since last backup
- **Database Only** - Quick backup of databases and preferences

### Network Migration
- **Auto-Discovery** - Find Plex servers on your network via mDNS
- **Direct Transfer** - Push/pull data between machines
- **SSH/SFTP Support** - Secure transfers to remote systems
- **Role-Based** - Source (old server) and Target (new server) roles

### Cross-OS Migration
- **Path Remapping** - Automatic conversion of media paths
- **Registry to XML** - Windows registry settings converted for Linux/macOS
- **Preferences Migration** - Intelligent handling of OS-specific settings

### Additional Features
- **Compression** - ZIP, TAR.GZ, TAR.XZ, 7-Zip support
- **Verification** - Database integrity checks after backup
- **Progress Tracking** - Real-time progress with ETA
- **Manifest Files** - Detailed backup metadata for easy restoration
- **CLI Mode** - Full automation and scripting support

## Installation

### Windows

#### Option 1: Standalone Executable
Download `plex-toolkit-x.x.x-windows.zip` from [Releases](https://github.com/saint1415/powershell/releases).

#### Option 2: Python Installation
```powershell
# Clone repository
git clone https://github.com/saint1415/powershell.git
cd powershell/plex-toolkit

# Install dependencies
pip install -r requirements.txt

# Run
python plex_toolkit.py
```

### Linux

#### Option 1: Debian/Ubuntu Package
```bash
wget https://github.com/saint1415/powershell/releases/download/vX.X.X/plex-toolkit-x.x.x-linux-amd64.deb
sudo dpkg -i plex-toolkit-x.x.x-linux-amd64.deb
```

#### Option 2: Python Installation
```bash
# Clone repository
git clone https://github.com/saint1415/powershell.git
cd powershell/plex-toolkit

# Install dependencies
pip3 install -r requirements.txt

# Run GUI
python3 plex_toolkit.py

# Or run CLI
python3 plex_toolkit.py --cli
```

### macOS

```bash
# Clone repository
git clone https://github.com/saint1415/powershell.git
cd powershell/plex-toolkit

# Install dependencies
pip3 install -r requirements.txt

# Run
python3 plex_toolkit.py
```

## Usage

### GUI Mode

Launch the graphical interface:

```bash
python plex_toolkit.py
```

The GUI provides tabs for:
- **Backup** - Create local backups with various modes
- **Restore** - Restore from backup with path remapping
- **Network Migration** - Discover and migrate between machines
- **Settings** - View system info and export data

### CLI Mode

For automation and scripting:

```bash
# Show status
python plex_toolkit.py --cli status

# Create backup
python plex_toolkit.py --cli backup /path/to/backup

# Cold backup with compression
python plex_toolkit.py --cli backup -m cold -c zip /path/to/backup

# Restore from backup
python plex_toolkit.py --cli restore /path/to/backup

# Restore with path remapping
python plex_toolkit.py --cli restore /path/to/backup \
    -r "/mnt/media" "D:\Media" \
    -r "/mnt/movies" "E:\Movies"

# Discover Plex servers on network
python plex_toolkit.py --cli discover

# Export library info
python plex_toolkit.py --cli export library library_info.json

# Full help
python plex_toolkit.py --cli --help
```

## Migration Scenarios

### Same Machine Backup/Restore

1. Launch the toolkit
2. Go to **Backup** tab
3. Select destination drive
4. Choose backup mode (Smart Sync recommended)
5. Click **Start Backup**

### Windows to Linux Migration

1. **On Windows (Source):**
   ```bash
   python plex_toolkit.py --cli backup -m cold -c zip E:\plex_backup
   ```

2. **Copy backup to Linux machine**

3. **On Linux (Target):**
   ```bash
   # Install Plex Media Server but don't configure it
   sudo systemctl stop plexmediaserver

   # Restore with path remapping
   python3 plex_toolkit.py --cli restore /path/to/backup \
       -r "D:\\Media" "/mnt/media" \
       -r "E:\\Movies" "/mnt/movies"

   # Start Plex
   sudo systemctl start plexmediaserver
   ```

### Network Migration

1. **Run toolkit on BOTH machines**

2. **On old server:** Select "Source" role
3. **On new server:** Select "Target" role
4. **Discovery will find both machines**
5. **Click Connect, then Start Migration**

### Synology NAS Migration

1. **Backup from current system:**
   ```bash
   python plex_toolkit.py --cli backup -m cold /volume1/backup
   ```

2. **On new Synology:**
   ```bash
   # Stop Plex package
   synopkg stop PlexMediaServer

   # Restore
   python3 plex_toolkit.py --cli restore /volume1/backup \
       --target /volume1/PlexMediaServer/AppData/Plex\ Media\ Server

   # Start Plex
   synopkg start PlexMediaServer
   ```

## Configuration

### Environment Variables

```bash
# Custom Plex data directory
export PLEX_HOME=/custom/path/to/plex

# Disable GUI (CLI only)
export PLEX_TOOLKIT_CLI=1
```

### Path Mappings File

Create `path_mappings.json` for complex migrations:

```json
{
    "D:\\Media": "/mnt/media",
    "E:\\Movies": "/mnt/movies",
    "F:\\TV Shows": "/mnt/tv"
}
```

Use with:
```bash
python plex_toolkit.py --cli restore /backup --mappings path_mappings.json
```

## What Gets Backed Up

### Included
- Plex databases (libraries, watch history, ratings)
- Metadata and artwork
- Plugin configurations
- User preferences
- Playlists and collections
- Watch history and on-deck status

### Excluded (by default)
- Transcoder cache
- Temporary files
- Log files
- Cache directory
- Updates folder

## Requirements

### System Requirements
- Python 3.8 or later
- 1GB RAM minimum
- Storage for backup (varies by library size)

### Dependencies
- tkinter (for GUI)
- psutil
- zeroconf (for network discovery)
- paramiko (for SSH transfers)
- rich (for CLI output)

## Building from Source

### Prerequisites

```bash
pip install pyinstaller
```

### Build Commands

```bash
# Build everything
python build.py all

# Build executable only
python build.py exe

# Build portable package
python build.py portable

# Clean build files
python build.py clean
```

### Output

Build artifacts are created in the `dist/` directory:
- `plex-toolkit.exe` - Windows executable
- `plex-toolkit-x.x.x-windows-portable.zip` - Portable Windows package
- `plex-toolkit-x.x.x-linux-amd64.deb` - Debian package
- `plex-toolkit-x.x.x-linux-portable.tar.gz` - Portable Linux package
- `plex-toolkit-x.x.x-macos.dmg` - macOS disk image

## Troubleshooting

### Plex Not Found

The toolkit automatically searches common installation paths. If not found:

1. Set the `PLEX_HOME` environment variable
2. Check if Plex has been run at least once
3. Verify installation path in Plex settings

### Permission Errors

- **Windows:** Run as Administrator
- **Linux/macOS:** Run with sudo or ensure user has access to Plex data

### Database Locked

If backup fails due to locked files:

1. Use **Cold Copy** mode to stop Plex during backup
2. Or use **Smart Sync** for hot copy + cold database sync

### Network Discovery Not Working

1. Ensure both machines are on the same network
2. Check firewall allows UDP port 52401
3. Try manual connection with IP address

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- Original PowerShell version by saint1415
- Community feedback from Reddit r/PleX
- Plex Media Server documentation

## Support

- **Issues:** [GitHub Issues](https://github.com/saint1415/powershell/issues)
- **Discussions:** [GitHub Discussions](https://github.com/saint1415/powershell/discussions)

---

**Note:** This tool is not affiliated with Plex Inc. Always maintain multiple backups of important data.
