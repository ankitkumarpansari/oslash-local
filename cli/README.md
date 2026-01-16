# OSlash CLI

Terminal client for OSlash Local - search your files from the command line.

## Installation

```bash
cd cli
pip install -e .
```

## Usage

### Interactive TUI

```bash
# Launch interactive interface
oslash

# Or explicitly
oslash tui
```

### Quick Search

```bash
# Search for documents
oslash search "quarterly report"

# Limit results
oslash search "budget" -n 3

# Filter by source
oslash search "meeting notes" -s slack
```

### Chat Mode

```bash
# Ask a question
oslash chat "What was our Q4 revenue?"

# Interactive chat
oslash chat
```

### Status & Sync

```bash
# Check server status
oslash status

# Trigger sync
oslash sync

# Sync specific source
oslash sync -s gdrive
```

## Keyboard Shortcuts (TUI)

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `c` | Enter chat mode |
| `s` | Trigger sync |
| `↑↓` | Navigate results |
| `Enter` | Open selected |
| `Escape` | Back to search |
| `q` | Quit |

## Requirements

- Python 3.11+
- OSlash Local server running on localhost:8000

