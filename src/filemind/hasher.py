import hashlib
from pathlib import Path

def generate_file_hash(file_path: Path, chunk_size: int = 65536) -> str:
    """
    Generates the SHA256 hash of a file.

    Args:
        file_path: The path to the file.
        chunk_size: The size of chunks to read the file in (for large files).

    Returns:
        The SHA256 hash of the file as a hexadecimal string.
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash string in chunks
        for byte_block in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

if __name__ == "__main__":
    # Example usage: create a dummy file and hash it
    dummy_file_path = Path("temp_dummy_file.txt")
    with open(dummy_file_path, "w") as f:
        f.write("This is a test file for hashing.\n")
        f.write("It has multiple lines.\n")
    
    file_hash = generate_file_hash(dummy_file_path)
    print(f"Hash of '{dummy_file_path}': {file_hash}")
    
    # Clean up dummy file
    dummy_file_path.unlink()

    # Test with a slight change
    with open(dummy_file_path, "w") as f:
        f.write("This is a test file for hashing.\n")
        f.write("It has multiple lines. (changed)\n")
    
    file_hash_changed = generate_file_hash(dummy_file_path)
    print(f"Hash of '{dummy_file_path}' (changed): {file_hash_changed}")
    
    # Clean up dummy file
    dummy_file_path.unlink()

