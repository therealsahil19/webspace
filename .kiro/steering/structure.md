# Project Structure

## Current Organization

```
/
├── .kiro/                 # Kiro AI assistant configuration
│   └── steering/          # AI guidance documents
│       ├── product.md     # Product overview and philosophy
│       ├── tech.md        # Technology stack and commands
│       └── structure.md   # This file - project organization
└── .vscode/               # VS Code workspace settings
    └── settings.json      # Editor configuration
```

## Directory Conventions

### Configuration Directories
- `.kiro/` - Kiro AI assistant configuration and steering rules
- `.vscode/` - VS Code workspace-specific settings

### Future Structure Guidelines
As the project grows, consider organizing with:

```
/
├── src/                   # Source code
├── tests/                 # Test files
├── docs/                  # Documentation
├── config/                # Configuration files
├── scripts/               # Build and utility scripts
└── assets/                # Static assets (images, etc.)
```

## File Naming Conventions
- Use lowercase with hyphens for directories: `my-feature/`
- Use descriptive names that indicate purpose
- Group related files in appropriate directories
- Keep the root directory clean and organized

## Best Practices
- Maintain a flat structure initially, add depth as needed
- Use consistent naming patterns
- Document significant structural changes
- Keep configuration files at appropriate levels