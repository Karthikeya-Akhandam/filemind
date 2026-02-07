# FileMind 🧠

**FileMind: A local-first file intelligence engine for deduplication and semantic search.**

FileMind is a powerful command-line tool that scans your local files, understands their content, and helps you find what you're looking for—no matter how it's named. It's fully offline, privacy-first, and designed to combat file redundancy and make discovery effortless.

## Key Features

- **Exact Duplicate Detection:** Finds files that are bit-for-bit identical, helping you clean up clutter.
- **Semantic Search:** Search for concepts, not just keywords. Find a document by describing what it's *about*.
- **Hybrid Search:** Combines the best of keyword and semantic search for the most relevant results.
- **Offline & Private:** Your files are never uploaded. All processing and indexing happens locally on your machine.
- **Cross-Platform:** Works on Windows, macOS, and Linux.

---

## Installation

### Recommended (Linux & macOS)

For Linux and macOS, you can install FileMind with a single command using `curl`. This will download the latest pre-built binary and place it in your system path.

```bash
curl -fsSL https://raw.githubusercontent.com/Karthikeya-Akhandam/filemind/main/install.sh | sh
```

After installation, you may need to open a new terminal for the `filemind` command to be available.

### Windows

For Windows, download the `filemind-windows-amd64.exe` file directly from the [latest release page](https://github.com/Karthikeya-Akhandam/filemind/releases/latest).

You can rename it to `filemind.exe` and place it in a directory that is part of your system's `PATH` for easier access.

### For Python Developers (pip)

If you are a Python developer, you can install the package via `pip`:

```bash
# Install the core application
pip install filemind

# To run the 'init' command, you need extra dependencies
pip install "filemind[init]"
```

---

## Quick Start Guide

1.  **Initialize FileMind:**
    Before you can use FileMind, you need to initialize it. This command downloads the AI model and sets up the local database. You only need to do this once.
    
    *(Requires an internet connection for the first run.)*

    ```bash
    filemind init
    ```

2.  **Scan a Directory:**
    Tell FileMind to scan a directory and index its contents.

    ```bash
    filemind scan "/path/to/your/documents"
    ```

3.  **Search Your Files:**
    Search for files based on their content.

    ```bash
    filemind search "financial report for Q3"
    ```

4.  **Find Duplicates:**
    Check for exact duplicate files in the directories you've scanned.

    ```bash
    filemind duplicates
    ```

## All Commands

- `filemind init`: Sets up the application environment.
- `filemind scan <directory>`: Scans a directory and indexes its files.
- `filemind search <query>`: Performs a hybrid search on your index.
- `filemind duplicates`: Finds and lists all exact duplicate files.
- `filemind uninstall`: Removes all data, models, and indexes created by FileMind.

---

## Contributing

Contributions are welcome! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) file for details on how to set up your development environment and submit your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
