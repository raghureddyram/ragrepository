from pathlib import Path
import pdb
import time


def is_binary_file(file_path, chunk_size=1024):
    """
    Check if a file is binary by reading the first chunk and checking for non-text characters.
    
    :param file_path: The path to the file.
    :param chunk_size: Number of bytes to read for binary check.
    :return: True if the file is binary, False otherwise.
    """
    try:
        with open(file_path, 'rb') as file:
            chunk = file.read(chunk_size)
            if b'\0' in chunk:  # Null byte indicates binary file
                return True
    except Exception as e:
        print(f"Error checking if file is binary: {e}")
    return False

def create_metadata_tree(repo_path: str):
    """
    Recursively maps the folder structure of the repository and creates three metadata hashes
    for folders, files, and lines, while safely skipping binary files.

    :param repo_path: The root directory of the repository.
    :return: Three dictionaries representing files, folders, and lines.
    """
    files_hash = {}
    folders_hash = {}
    lines_hash = {}
    repo_root = Path(repo_path)

    # Recursively traverse the directory
    for root in repo_root.rglob('*'):
        if root.is_dir():
            # Folder metadata
            folder_metadata = {
                "folder_path": str(root),
                "folder_content_summary": f"Folder contains {len(list(root.iterdir()))} items",
                "files": [str(file) for file in root.iterdir() if file.is_file()]
            }
            folders_hash[str(root)] = folder_metadata

            # Process files in the current directory
            for file_path in root.iterdir():
                if file_path.is_file():
                    # Check if the file is binary
                    if is_binary_file(file_path):
                        print(f"Skipping binary file: {file_path}")
                        continue

                    # File metadata
                    try:
                        with file_path.open('r', encoding='utf-8', errors='ignore') as f:
                            file_lines = f.readlines()
                        file_metadata = {
                            "file_path": str(file_path),
                            "file_content": "".join(file_lines),
                            "metadata": {
                                "last_modified": time.ctime(file_path.stat().st_mtime),
                                "file_type": file_path.suffix,
                                "lines_of_code": len(file_lines)
                            }
                        }
                        files_hash[str(file_path)] = file_metadata

                        # Line metadata for each file
                        for line_num, line_content in enumerate(file_lines, 1):
                            line_metadata = {
                                "file_path": str(file_path),
                                "line_number": line_num,
                                "line_content": line_content.strip(),
                                "surrounding_context": [
                                    {"line_number": line_num - 1, "line_content": file_lines[line_num - 2].strip()} if line_num > 1 else None,
                                    {"line_number": line_num + 1, "line_content": file_lines[line_num].strip()} if line_num < len(file_lines) else None
                                ]
                            }
                            lines_hash[f"{file_path}:{line_num}"] = line_metadata
                    except Exception as e:
                        print(f"Error reading file {file_path}: {e}")

    return files_hash, folders_hash, lines_hash



files_hash, folders_hash, lines_hash = create_metadata_tree('../readme-bot')