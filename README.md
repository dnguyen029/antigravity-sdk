# Antigravity Swarm Python SDK

This repository contains the standalone, terminal-based multi-agent Python SDK swarm setup. It has been moved here to keep the main workspace clean and decoupled.

## Contents

- `native_orchestrator.py`: The main entrypoint for executing swarm-based agent tasks from the command line.
- `librarian.md`: Swarm documentation and context logs.
- `agents/`: Profiles and configuration files for all active swarm agents:
  - Orchestrator (`orchestrator.txt`)
  - Builder (`builder.txt`)
  - Auditor (`auditor.txt`)
  - SRE (`sre.txt`)
  - Receptionist & Sub-agents (`receptionist.txt`, `router.txt`, `faq_receptionist.txt`, `wismo_receptionist.txt`)
  - Librarian (`librarian.txt`)

## Usage

This SDK is intended to be run outside of the Antigravity IDE application space (e.g. directly in your terminal) using your Python virtual environment.
