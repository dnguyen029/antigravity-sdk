# Antigravity Swarm Python SDK

This repository contains the standalone, terminal-based multi-agent Python SDK swarm setup. It provides a complete template for running a cooperative group of autonomous agents (Orchestrator, Builder, Auditor, SRE, Librarian) directly from your terminal.

---

## 📂 Repository Contents

*   `native_orchestrator.py`: The main Python runtime engine to trigger tasks and execute multi-agent workflows.
*   `requirements.txt`: Package dependencies for the SDK.
*   `.env.template`: Template configuration for required API keys and cloud settings.
*   `pyrightconfig.json`: Configuration for static type checkers.
*   `librarian.md`: Profile guidelines for the Technical Writer/Librarian agent.
*   `agents/`: Playbook configuration files for all active swarm agents:
    *   Orchestrator (`orchestrator.txt`)
    *   Builder (`builder.txt`)
    *   Auditor (`auditor.txt`)
    *   SRE (`sre.txt`)
    *   Receptionist & Router (`receptionist.txt`, `router.txt`, `faq_receptionist.txt`, `wismo_receptionist.txt`)
    *   Librarian (`librarian.txt`)

---

## 🚀 Local Setup

### 1. Install Dependencies
Set up your virtual environment and install the required packages:
```bash
# Initialize virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment variables
Copy the environment variables template to `.env` and fill in your keys:
```bash
cp .env.template .env
```

Required keys include:
*   `PROJECT_ID`: Your Google Cloud Project ID.
*   `GOOGLE_CLOUD_LOCATION`: The location for Vertex AI services (e.g., `us-central1`).
*   `SUPABASE_URL` / `SUPABASE_ACCESS_TOKEN`: Configuration for the Supabase memory vault.
*   `EXA_API_KEY`: Exa.ai API token (optional, for web search capabilities).

### 3. Setup MCP configurations
Ensure you have `mcp_config.json` in your running directory to authorize Model Context Protocol (MCP) servers used by your agents.

---

## 💻 Run Swarm Workflows

To run a governed swarm task through the native orchestrator, execute:

```bash
python native_orchestrator.py "your task description here"
```

### Handoff Sequence
1.  **Discovery (Librarian)**: Queries Supabase memory banks to check for past learnings.
2.  **Planning (Architect)**: Generates an implementation plan and checklists in `implementation_plan.md` and `task.md`.
3.  **Execution (Builder)**: Implements the requested changes.
4.  **Verification (Librarian)**: Validates syntax compiling, runs tests, and archives lessons learned back to Supabase.
