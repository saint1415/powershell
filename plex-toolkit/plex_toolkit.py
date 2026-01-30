#!/usr/bin/env python3
"""
Plex Migration Toolkit
Cross-platform backup and migration tool for Plex Media Server

Usage:
    python plex_toolkit.py              # Launch GUI
    python plex_toolkit.py --cli        # Launch CLI
    python plex_toolkit.py --help       # Show help

For CLI usage:
    python plex_toolkit.py --cli backup /path/to/backup
    python plex_toolkit.py --cli restore /path/to/backup
    python plex_toolkit.py --cli status
    python plex_toolkit.py --cli discover
"""

import sys
import os

# Add src to path
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, src_path)


def main():
    """Main entry point"""
    # Check if CLI mode
    if len(sys.argv) > 1 and sys.argv[1] == '--cli':
        # Remove --cli from args and run CLI
        sys.argv.pop(1)
        from cli.main import main as cli_main
        cli_main()
    elif len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print(__doc__)
        print("\nFor CLI commands, use: python plex_toolkit.py --cli --help")
    else:
        # Launch GUI
        try:
            from gui.main_window import PlexToolkitGUI
            app = PlexToolkitGUI()
            app.run()
        except ImportError as e:
            print(f"GUI not available: {e}")
            print("Falling back to CLI...")
            print("Run with --cli for command-line interface")
            from cli.main import main as cli_main
            cli_main()
        except Exception as e:
            print(f"Error launching GUI: {e}")
            print("Use --cli for command-line interface")
            sys.exit(1)


if __name__ == "__main__":
    main()
