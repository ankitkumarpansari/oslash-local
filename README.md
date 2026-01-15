# OSlash Local

A local-first RAG-powered file search system with browser extension trigger (`o/`), multi-source integrations, and conversational Q&A capabilities.

## 🎯 Overview

OSlash Local lets you type `o/ {query}` anywhere in your browser to instantly find relevant files across your connected tools using RAG (Retrieval-Augmented Generation).

## ✨ Features

- **Universal Search Trigger**: Type `o/` in any text input to search
- **Multi-Source Integration**: Google Drive, Gmail, Slack, HubSpot
- **Semantic Search**: AI-powered search using embeddings
- **Q&A Chat**: Ask follow-up questions about found documents
- **Local-First**: All data stays on your machine
- **Multiple Clients**: Browser extension, CLI, and more

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OSlash Local                              │
├─────────────────────────────────────────────────────────────┤
│  CLIENTS                                                    │
│  ├── Chrome Extension (o/ trigger + overlay)               │
│  ├── CLI/TUI (Textual)                                     │
│  └── [Future] Slack Bot, Raycast                           │
├─────────────────────────────────────────────────────────────┤
│  API SERVER (FastAPI)                                       │
│  ├── /search - RAG search endpoint                         │
│  ├── /chat - Q&A with context                              │
│  └── /sync - Background sync management                    │
├─────────────────────────────────────────────────────────────┤
│  CORE                                                       │
│  ├── Embeddings (OpenAI text-embedding-3-small)            │
│  ├── Vector Store (ChromaDB)                               │
│  ├── Semantic Chunking                                      │
│  └── Chat Engine (GPT-4o-mini)                             │
├─────────────────────────────────────────────────────────────┤
│  CONNECTORS                                                 │
│  ├── Google Drive                                           │
│  ├── Gmail                                                  │
│  ├── Slack                                                  │
│  └── HubSpot                                                │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Server | FastAPI (Python 3.11+) |
| Vector DB | ChromaDB |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | GPT-4o-mini |
| Extension | Chrome Manifest V3 + Preact |
| CLI | Textual |

## 📦 Project Structure

```
oslash-local/
├── server/              # FastAPI backend
│   ├── oslash/
│   │   ├── api/         # REST endpoints
│   │   ├── core/        # RAG engine
│   │   ├── connectors/  # Data source integrations
│   │   ├── models/      # Data models
│   │   └── db/          # Database layer
│   └── tests/
├── extension/           # Chrome extension
│   ├── src/
│   └── public/
├── cli/                 # Terminal client
└── docs/
```

## 🚀 Getting Started

*Coming soon - see GitHub Issues for development progress*

## 📋 Development

This project is being built incrementally. Check the [GitHub Issues](../../issues) for the complete roadmap organized by epics:

- **Epic 1**: Project Foundation & Infrastructure
- **Epic 2**: Core RAG Engine
- **Epic 3**: Data Connectors
- **Epic 4**: Browser Extension
- **Epic 5**: CLI/TUI Client
- **Epic 6**: Authentication & Security
- **Epic 7**: Testing & Documentation

## 📄 License

Proprietary - All rights reserved © Ankit Pansari

## 🙏 Acknowledgments

- Inspired by [OSlash.com](https://oslash.com)
- Architecture patterns from [Ramp's Inspect](https://builders.ramp.com/post/why-we-built-our-background-agent)

