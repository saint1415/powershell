#!/usr/bin/env python3
"""
Setup script for Plex Migration Toolkit
"""

from setuptools import setup, find_packages
import os

# Read README
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="plex-migration-toolkit",
    version="2.0.0",
    author="saint1415",
    author_email="",
    description="Cross-platform backup and migration tool for Plex Media Server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/saint1415/powershell",
    project_urls={
        "Bug Tracker": "https://github.com/saint1415/powershell/issues",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: X11 Applications :: GTK",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "gui": ["tkinter-tooltip>=2.0.0"],
        "ssh": ["paramiko>=3.4.0", "scp>=0.14.0"],
        "rich": ["rich>=13.0.0", "tqdm>=4.65.0"],
        "all": [
            "tkinter-tooltip>=2.0.0",
            "paramiko>=3.4.0",
            "scp>=0.14.0",
            "rich>=13.0.0",
            "tqdm>=4.65.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "plex-toolkit=cli.main:main",
        ],
        "gui_scripts": [
            "plex-toolkit-gui=gui.main_window:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
