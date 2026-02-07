# Contributing to FileMind

First off, thank you for considering contributing to FileMind! It's people like you that make open source such a great community.

## How to Contribute

There are many ways to contribute, from writing code and documentation to submitting bug reports and feature requests.

### Reporting Bugs

If you find a bug, please create an issue in our [GitHub Issues](https://github.com/Karthikeya-Akhandam/filemind/issues) tracker. Please provide as much detail as possible, including:
- Your operating system.
- The command you ran.
- The full output and any error messages.
- Steps to reproduce the issue.

### Suggesting Enhancements

If you have an idea for a new feature, feel free to create an issue to discuss it. This is the best way to ensure your suggestion aligns with the project's goals before you put in a lot of work.

## Setting up the Development Environment

To get started with development, you'll need Python 3.8+ and `pip`.

1.  **Fork and Clone the Repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/filemind.git
    cd filemind
    ```

2.  **Install in Editable Mode with All Dependencies:**
    We use `pyproject.toml` to manage dependencies. To install the project in editable mode along with all development and optional dependencies (`init`, `dev`), run the following command from the root of the repository:

    ```bash
    pip install -e ".[init,dev]"
    ```
    This command allows you to edit the source code and have your changes immediately reflected when you run the `filemind` command.

3.  **Initialize FileMind:**
    To download the AI model and set up the local database for testing, run the `init` command:
    ```bash
    filemind init
    ```

## Running Tests (Placeholder)

Once tests are added to the project, you will be able to run them using `pytest`:

```bash
pytest
```

## Pull Request Process

1.  Ensure any new dependencies are added to `pyproject.toml`.
2.  Update the `README.md` with details of changes to the interface, if applicable.
3.  Make sure your code lints (we use `ruff` and `black`).
4.  Create a pull request with a clear description of your changes.

## Code of Conduct

This project and everyone participating in it is governed by the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/ ). By participating, you are expected to uphold this code. Please report unacceptable behavior.
