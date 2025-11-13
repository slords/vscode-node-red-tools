# Installation Guide

This guide covers installing and setting up vscode-node-red-tools.

## Requirements

### Python

- **Python 3.8 or later** is required
- Check your version:
  ```bash
  python3 --version
  ```

### Node.js

- **Node.js and npm** are required for prettier formatting
- Check your version:
  ```bash
  node --version
  npm --version
  ```
- If not installed, download from [nodejs.org](https://nodejs.org/)

## Docker/Container Support

You can run vscode-node-red-tools in a container using Docker:

### Build the Docker image

```bash
docker build -t vscode-node-red-tools .
```

### Run the tool in a container

Mount your project directory to `/data` (the container's working directory):

```bash
docker run --rm -it \
  -v "$(pwd)":/data \
  vscode-node-red-tools --help
```

To run the watch command (recommended):

```bash
docker run --rm -it \
  -v "$(pwd)":/data \
  vscode-node-red-tools watch --server <server-url> [other options]
```

Any CLI arguments after the image name are passed to the tool. Your project files will be accessible in `/data` inside the container.

---

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/vscode-node-red-tools.git
cd vscode-node-red-tools
```

### 2. Install Python Dependencies

Install required Python packages using pip:

```bash
pip install -r requirements.txt
```

This installs:

- **rich** (>=13.0.0) - Progress bars and terminal UI
- **watchdog** (>=3.0.0) - File system monitoring for watch mode
- **requests** (>=2.31.0) - HTTP client for watch mode
- **textual** (>=0.60.0) - Optional TUI dashboard

#### Using a Virtual Environment (Recommended)

For better isolation, use a virtual environment:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install Node.js Dependencies

Install prettier globally for code formatting:

```bash
npm install -g prettier
```

Verify installation:

```bash
npx prettier --version
```

### 4. Verify Installation

Test that the tool runs:

```bash
python3 vscode-node-red-tools.py --version
```

You should see version information displayed.

## Optional Configuration

### Create Configuration File

Create `.vscode-node-red-tools.json` to customize behavior:

```bash
cp .vscode-node-red-tools.example.json .vscode-node-red-tools.json
```

Edit the file to configure:

- Default flows and src paths
- Plugin enable/disable
- Watch mode polling intervals

See [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration options.

### Shell Completion

For tab-completion of commands and options, install the optional dependency:

```bash
pip install argcomplete
```

Then activate completion for your shell:

#### Bash (add to ~/.bashrc or ~/.bash_profile)

```bash
eval "$(register-python-argcomplete vscode-node-red-tools.py)"
```

#### Zsh (add to ~/.zshrc)

```bash
eval "$(register-python-argcomplete vscode-node-red-tools.py)"
```

#### Fish

```bash
register-python-argcomplete vscode-node-red-tools.py | source
```

You can also generate a static completion script:

```bash
register-python-argcomplete vscode-node-red-tools.py > completion.sh
# Then source completion.sh in your shell config
```

Shell completion is optional but highly recommended for a better CLI experience.

## Platform-Specific Notes

### Linux

No special requirements. Python 3 and Node.js are typically available via package managers:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip nodejs npm

# Fedora
sudo dnf install python3 python3-pip nodejs npm
```

### macOS

Use Homebrew for easy installation:

```bash
brew install python3 node
```

### Windows

1. Download Python from [python.org](https://www.python.org/)
2. Download Node.js from [nodejs.org](https://nodejs.org/)
3. Make sure to check "Add to PATH" during installation
4. Use Command Prompt or PowerShell for commands

## Next Steps

- Read [USAGE.md](USAGE.md) to learn how to use the tool
- Review [CONFIGURATION.md](CONFIGURATION.md) for configuration options
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you encounter issues

## Updating

To update to the latest version:

```bash
cd vscode-node-red-tools
git pull origin main
pip install -r requirements.txt  # Update Python packages
npm install -g prettier           # Update prettier
```

## Uninstallation

To remove the tool:

```bash
# Remove the directory
rm -rf vscode-node-red-tools

# Optionally remove Python packages
pip uninstall rich watchdog requests textual

# Optionally remove prettier
npm uninstall -g prettier
```
