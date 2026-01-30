# Plex Migration Toolkit

A powerful, cross-platform tool for backing up and migrating Plex Media Server data between machines and operating systems.

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Overview

This repository contains two versions of the Plex Migration Toolkit:

### 1. Plex Migration Toolkit (Cross-Platform Python) - **Recommended**

Located in the [`plex-toolkit/`](plex-toolkit/) directory.

A complete rewrite in Python with:
- **Cross-platform support** - Windows, Linux, macOS, and NAS devices
- **Modern GUI** - Dark-themed tkinter interface
- **Full CLI** - Automation and scripting support
- **Network Migration** - Auto-discovery and direct transfer between machines
- **Cross-OS Migration** - Automatic path remapping for Windows↔Linux↔macOS
- **Multiple backup modes** - Hot, Cold, Smart Sync, Incremental
- **Compression** - ZIP, TAR.GZ, TAR.XZ, 7-Zip
- **NAS Support** - Synology, QNAP, Unraid, TrueNAS

See [`plex-toolkit/README.md`](plex-toolkit/README.md) for full documentation.

#### Quick Start (Python)

```bash
# Clone the repository
git clone https://github.com/saint1415/powershell.git
cd powershell/plex-toolkit

# Install dependencies
pip install -r requirements.txt

# Launch GUI
python plex_toolkit.py

# Or use CLI
python plex_toolkit.py --cli backup /path/to/backup
```

### 2. Original PowerShell GUI (Windows Only)

The original Windows PowerShell version with Windows Forms GUI.

- Simple, single-file script
- Windows-only
- Hot Copy, Cold Copy, Smart Sync modes
- Perfect for quick Windows-to-Windows backups

#### Quick Start (PowerShell)

```powershell
# Download and run
.\plex_migration_gui.ps1
```

## Downloads

### Pre-built Releases

Download ready-to-use packages from the [Releases](https://github.com/saint1415/powershell/releases) page:

| Platform | File | Description |
|----------|------|-------------|
| Windows | `plex-toolkit.exe` | Standalone executable |
| Windows | `plex-toolkit-*-windows-portable.zip` | Portable package |
| Linux | `plex-toolkit-*-linux-amd64.deb` | Debian/Ubuntu package |
| Linux | `plex-toolkit-*-linux-portable.tar.gz` | Portable package |
| macOS | `plex-toolkit-*-macos.dmg` | macOS disk image |
| macOS | `plex-toolkit-*-macos-portable.tar.gz` | Portable package |

## Features Comparison

| Feature | Python Toolkit | PowerShell |
|---------|---------------|------------|
| Windows Support | Yes | Yes |
| Linux Support | Yes | No |
| macOS Support | Yes | No |
| NAS Support | Yes | No |
| GUI | Yes | Yes |
| CLI | Yes | Limited |
| Network Migration | Yes | No |
| Cross-OS Migration | Yes | No |
| Compression | Yes | No |
| Incremental Backup | Yes | No |
| Auto-discovery | Yes | No |

## Migration Scenarios

### Local Backup
1. Launch the toolkit
2. Select destination drive
3. Choose backup mode
4. Click Start Backup

### Windows to Linux Migration
```bash
# On Windows: Create backup
python plex_toolkit.py --cli backup -m cold -c zip E:\backup

# Copy to Linux, then restore with path remapping
python3 plex_toolkit.py --cli restore /path/to/backup \
    -r "D:\\Media" "/mnt/media"
```

### Network Migration
1. Run toolkit on both machines
2. Set roles (Source/Target)
3. Auto-discovery finds both
4. Click Start Migration

## Documentation

- [Full Python Toolkit Documentation](plex-toolkit/README.md)
- [Building from Source](plex-toolkit/README.md#building-from-source)
- [CLI Reference](plex-toolkit/README.md#cli-mode)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## Support

- **Issues:** [GitHub Issues](https://github.com/saint1415/powershell/issues)
- **Discussions:** [GitHub Discussions](https://github.com/saint1415/powershell/discussions)

## License

MIT License - See [LICENSE](plex-toolkit/LICENSE) for details.

---

**Note:** This tool is not affiliated with Plex Inc. Always maintain multiple backups.
