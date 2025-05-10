"""In specified folders, sanitize all files names."""

import re
import argparse
import sys
from pathlib import Path


# Regex: remove leading non-alphanumeric (English/Greek) characters, including spaces
pattern = re.compile(r'^[^a-zA-Z0-9\u0370-\u03FF]+')

def clean_filename(filename: str) -> str:
    """Remove leading unwanted characters (including spaces) from filename."""
    return pattern.sub('', filename)

def process_folder(folder_path: Path) -> None:
    """Rename files in the folder by removing leading unwanted characters."""
    ctr = 0
    for file_path in folder_path.iterdir():
        if file_path.is_file():
            new_name = clean_filename(file_path.name)
            if new_name and new_name != file_path.name:
                new_path = file_path.with_name(new_name)
                if not new_path.exists():
                    file_path.rename(new_path)
                    ctr += 1
                    print(f"Renamed: '{file_path.name}' -> '{new_name}'")
                else:
                    print(f"Skipped (target exists): '{new_name}'")
    print(f"Rename {ctr} files in folder '{folder_path}'")

def validate_folder(folder_path: Path, label: str) -> None:
    """Abort if the folder does not exist or is not a directory."""
    if not folder_path.exists():
        print(f"Error: {label} '{folder_path}' does not exist.")
        sys.exit(1)
    if not folder_path.is_dir():
        print(f"Error: {label} '{folder_path}' is not a directory.")
        sys.exit(1)

def main() -> None:
    home = Path.home()
    default_base = home / "Apps" / "yt-dlp"
    parser = argparse.ArgumentParser(
        description="Rename files in folders by removing leading non-alphanumeric (English/Greek) characters."
    )
    parser.add_argument("--base-dir", type=Path, default=default_base,
                        help=f"Base directory (default: '{default_base}')")
    parser.add_argument("folder1", type=str,
                        help="First folder under base directory (mandatory)")
    parser.add_argument("folder2", type=str, nargs="?", default=None,
                        help="Second folder under base directory (optional)")
    args = parser.parse_args()

    folder1_path = args.base_dir / args.folder1
    validate_folder(folder1_path, "folder1")
    print(f"Processing folder1: {folder1_path}")
    process_folder(folder1_path)

    if args.folder2:
        folder2_path = args.base_dir / args.folder2
        validate_folder(folder2_path, "folder2")
        print(f"Processing folder2: {folder2_path}")
        process_folder(folder2_path)

if __name__ == "__main__":
    main()
