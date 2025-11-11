# Contributing to vscode-node-red-tools

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/vscode-node-red-tools.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Install dependencies: `pip install -r requirements.txt`

## Development Workflow

### Making Changes

1. Make your changes in your feature branch
2. Test your changes thoroughly:
   ```bash
   # Test explode/rebuild cycle
   python3 vscode-node-red-tools.py verify flows/flows.json

   # Test specific functionality
   python3 vscode-node-red-tools.py explode flows/flows.json
   python3 vscode-node-red-tools.py rebuild flows/flows.json
   ```

3. Ensure your code follows the existing style:
   - Use descriptive variable names
   - Add docstrings to functions and classes
   - Keep functions focused and modular
   - Comment complex logic

### Testing Plugins

If you're developing a plugin:

1. Place it in the `plugins/` directory with a numeric prefix (e.g., `300_my_plugin.py`)
2. Test with `list-plugins` command:
   ```bash
   python3 vscode-node-red-tools.py list-plugins
   ```

3. Test round-trip consistency:
   ```bash
   python3 vscode-node-red-tools.py verify flows/flows.json
   ```

See [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) for detailed plugin development guidelines.

## Submitting Changes

1. Commit your changes with clear, descriptive messages:
   ```bash
   git commit -m "Add feature: description of what you added"
   ```

2. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

3. Create a Pull Request:
   - Provide a clear description of the changes
   - Reference any related issues
   - Explain why the change is needed
   - Include examples if applicable

## Pull Request Guidelines

- **Title**: Use a clear, descriptive title
- **Description**: Explain what changes you made and why
- **Testing**: Describe how you tested the changes
- **Breaking Changes**: Clearly note any breaking changes
- **Documentation**: Update relevant documentation

## Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Keep lines under 100 characters when reasonable
- Use meaningful variable and function names

## Plugin Development

When creating plugins:

- Follow the existing plugin patterns
- Use numeric prefixes to control execution order
- Document plugin behavior in docstrings
- Handle errors gracefully
- Return appropriate status indicators

## Bug Reports

When reporting bugs, please include:

- A clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version)
- Relevant logs or error messages
- Sample flows.json (if applicable)

## Feature Requests

When requesting features:

- Explain the use case
- Describe the desired behavior
- Consider how it fits with existing functionality
- Note any potential breaking changes

## Questions

- Check existing documentation in the `docs/` folder
- Search existing issues
- Open a new issue with the "question" label

## License

By contributing, you agree that your contributions will be licensed under the Historical license reference removed; see current LICENSE (BSL-1.1 → AGPL-3.0).
