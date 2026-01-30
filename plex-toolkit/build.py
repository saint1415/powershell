#!/usr/bin/env python3
"""
Build script for Plex Migration Toolkit
Creates distributable packages for Windows, Linux, and macOS
"""

import os
import sys
import shutil
import subprocess
import platform
import zipfile
import tarfile
from pathlib import Path


# Configuration
APP_NAME = "Plex Migration Toolkit"
APP_VERSION = "2.0.0"
APP_AUTHOR = "saint1415"
MAIN_SCRIPT = "plex_toolkit.py"

# Directories
ROOT_DIR = Path(__file__).parent
SRC_DIR = ROOT_DIR / "src"
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"


def clean():
    """Clean build directories"""
    print("Cleaning build directories...")

    for dir_path in [DIST_DIR, BUILD_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)

    # Remove PyInstaller spec file
    spec_file = ROOT_DIR / "plex_toolkit.spec"
    if spec_file.exists():
        spec_file.unlink()

    print("Clean complete")


def install_dependencies():
    """Install build dependencies"""
    print("Installing dependencies...")

    subprocess.run([
        sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
    ], check=True)

    subprocess.run([
        sys.executable, "-m", "pip", "install", "pyinstaller"
    ], check=True)

    print("Dependencies installed")


def build_executable():
    """Build standalone executable using PyInstaller"""
    print(f"Building executable for {platform.system()}...")

    # Determine platform-specific options
    system = platform.system().lower()
    icon = None

    if system == "windows":
        icon = ROOT_DIR / "assets" / "icon.ico"
        exe_name = "plex-toolkit.exe"
    elif system == "darwin":
        icon = ROOT_DIR / "assets" / "icon.icns"
        exe_name = "plex-toolkit"
    else:
        exe_name = "plex-toolkit"

    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "plex-toolkit",
        "--onefile",
        "--windowed" if system != "linux" else "--console",
        "--add-data", f"src{os.pathsep}src",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "sqlite3",
        "--hidden-import", "xml.etree.ElementTree",
        "--hidden-import", "zeroconf",
        "--hidden-import", "netifaces",
        "--hidden-import", "psutil",
        "--hidden-import", "paramiko",
        "--hidden-import", "rich",
        "--hidden-import", "tqdm",
        "--clean",
    ]

    if icon and icon.exists():
        cmd.extend(["--icon", str(icon)])

    cmd.append(MAIN_SCRIPT)

    subprocess.run(cmd, check=True)

    print(f"Executable built: dist/{exe_name}")


def create_portable_package():
    """Create portable ZIP/TAR package"""
    print("Creating portable package...")

    system = platform.system().lower()
    version = APP_VERSION

    # Create package directory
    if system == "windows":
        pkg_name = f"plex-toolkit-{version}-windows-portable"
        archive_name = f"{pkg_name}.zip"
    elif system == "darwin":
        pkg_name = f"plex-toolkit-{version}-macos-portable"
        archive_name = f"{pkg_name}.tar.gz"
    else:
        pkg_name = f"plex-toolkit-{version}-linux-portable"
        archive_name = f"{pkg_name}.tar.gz"

    pkg_dir = DIST_DIR / pkg_name
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    files_to_copy = [
        MAIN_SCRIPT,
        "requirements.txt",
        "README.md",
        "LICENSE"
    ]

    for file in files_to_copy:
        src = ROOT_DIR / file
        if src.exists():
            shutil.copy(src, pkg_dir)

    # Copy src directory
    shutil.copytree(SRC_DIR, pkg_dir / "src", dirs_exist_ok=True)

    # Copy assets if exists
    assets_dir = ROOT_DIR / "assets"
    if assets_dir.exists():
        shutil.copytree(assets_dir, pkg_dir / "assets", dirs_exist_ok=True)

    # Create archive
    archive_path = DIST_DIR / archive_name

    if system == "windows":
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(pkg_dir):
                for file in files:
                    file_path = Path(root) / file
                    arc_name = file_path.relative_to(DIST_DIR)
                    zf.write(file_path, arc_name)
    else:
        with tarfile.open(archive_path, 'w:gz') as tf:
            tf.add(pkg_dir, arcname=pkg_name)

    # Cleanup
    shutil.rmtree(pkg_dir)

    print(f"Portable package created: dist/{archive_name}")


def create_installer():
    """Create platform-specific installer"""
    system = platform.system().lower()

    if system == "windows":
        create_windows_installer()
    elif system == "darwin":
        create_macos_app()
    else:
        create_linux_package()


def create_windows_installer():
    """Create Windows installer using NSIS or Inno Setup"""
    print("Creating Windows installer...")

    # Check for Inno Setup
    inno_path = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")

    if not inno_path.exists():
        print("Inno Setup not found. Skipping installer creation.")
        print("Install Inno Setup for Windows installer support.")
        return

    # Create Inno Setup script
    iss_script = f"""
#define MyAppName "{APP_NAME}"
#define MyAppVersion "{APP_VERSION}"
#define MyAppPublisher "{APP_AUTHOR}"
#define MyAppExeName "plex-toolkit.exe"

[Setup]
AppId={{{{B7E8D123-4567-89AB-CDEF-0123456789AB}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=plex-toolkit-{APP_VERSION}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\\plex-toolkit.exe"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "Launch {{#MyAppName}}"; Flags: nowait postinstall skipifsilent
    """

    iss_path = ROOT_DIR / "installer.iss"
    iss_path.write_text(iss_script)

    # Run Inno Setup
    subprocess.run([str(inno_path), str(iss_path)], check=True)

    # Cleanup
    iss_path.unlink()

    print(f"Windows installer created: dist/plex-toolkit-{APP_VERSION}-setup.exe")


def create_macos_app():
    """Create macOS .app bundle"""
    print("Creating macOS app bundle...")

    # PyInstaller should have created the .app
    app_path = DIST_DIR / "plex-toolkit.app"

    if not app_path.exists():
        print("App bundle not found. Building...")
        subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--name", "Plex Migration Toolkit",
            "--onedir",
            "--windowed",
            "--add-data", f"src{os.pathsep}src",
            "--osx-bundle-identifier", "com.saint1415.plextoolkit",
            MAIN_SCRIPT
        ], check=True)

    # Create DMG
    dmg_name = f"plex-toolkit-{APP_VERSION}-macos.dmg"
    dmg_path = DIST_DIR / dmg_name

    try:
        subprocess.run([
            "hdiutil", "create",
            "-volname", APP_NAME,
            "-srcfolder", str(app_path),
            "-ov", "-format", "UDZO",
            str(dmg_path)
        ], check=True)
        print(f"macOS DMG created: dist/{dmg_name}")
    except Exception as e:
        print(f"Could not create DMG: {e}")


def create_linux_package():
    """Create Linux packages (DEB, RPM, AppImage)"""
    print("Creating Linux packages...")

    # Create .deb package structure
    deb_name = f"plex-toolkit_{APP_VERSION}_amd64"
    deb_dir = BUILD_DIR / deb_name

    # DEBIAN control directory
    debian_dir = deb_dir / "DEBIAN"
    debian_dir.mkdir(parents=True)

    # Control file
    control = f"""Package: plex-toolkit
Version: {APP_VERSION}
Section: utils
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.8), python3-tk
Maintainer: {APP_AUTHOR}
Description: Plex Migration Toolkit
 Cross-platform backup and migration tool for Plex Media Server.
 Supports local backup, network migration, and cross-OS transfers.
"""

    (debian_dir / "control").write_text(control)

    # Install directory
    install_dir = deb_dir / "usr" / "share" / "plex-toolkit"
    install_dir.mkdir(parents=True)

    # Copy files
    shutil.copy(ROOT_DIR / MAIN_SCRIPT, install_dir)
    shutil.copy(ROOT_DIR / "requirements.txt", install_dir)
    shutil.copytree(SRC_DIR, install_dir / "src", dirs_exist_ok=True)

    # Create wrapper script
    bin_dir = deb_dir / "usr" / "bin"
    bin_dir.mkdir(parents=True)

    wrapper = """#!/bin/bash
python3 /usr/share/plex-toolkit/plex_toolkit.py "$@"
"""
    wrapper_path = bin_dir / "plex-toolkit"
    wrapper_path.write_text(wrapper)
    wrapper_path.chmod(0o755)

    # Build .deb
    try:
        subprocess.run(["dpkg-deb", "--build", str(deb_dir)], check=True)
        shutil.move(str(BUILD_DIR / f"{deb_name}.deb"),
                   str(DIST_DIR / f"plex-toolkit-{APP_VERSION}-linux-amd64.deb"))
        print(f"Debian package created: dist/plex-toolkit-{APP_VERSION}-linux-amd64.deb")
    except Exception as e:
        print(f"Could not create .deb: {e}")

    # Also create tar.gz for other distros
    create_portable_package()


def build_all():
    """Build all distribution packages"""
    print(f"Building {APP_NAME} v{APP_VERSION}")
    print("=" * 50)

    # Create dist directory
    DIST_DIR.mkdir(exist_ok=True)

    # Install dependencies
    install_dependencies()

    # Build executable
    build_executable()

    # Create portable package
    create_portable_package()

    # Create platform-specific installer
    create_installer()

    print("\n" + "=" * 50)
    print("Build complete! Packages available in dist/")
    print("=" * 50)

    # List created files
    for file in DIST_DIR.iterdir():
        size = file.stat().st_size / (1024 * 1024)
        print(f"  {file.name} ({size:.2f} MB)")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Build Plex Migration Toolkit")
    parser.add_argument('command', nargs='?', default='all',
                       choices=['all', 'clean', 'deps', 'exe', 'portable', 'installer'],
                       help='Build command')

    args = parser.parse_args()

    os.chdir(ROOT_DIR)

    if args.command == 'clean':
        clean()
    elif args.command == 'deps':
        install_dependencies()
    elif args.command == 'exe':
        build_executable()
    elif args.command == 'portable':
        create_portable_package()
    elif args.command == 'installer':
        create_installer()
    else:
        build_all()


if __name__ == "__main__":
    main()
