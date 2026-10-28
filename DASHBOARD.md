# 🛸 Antigravity Multi-Agent SDK Dashboard

This dashboard serves as the central documentation and governance hub for the **Antigravity Multi-Agent Orchestrator**. It connects the different layers of the development workflow, governance rules, and runtime status.

---

### 🗄️ Multi-Agent Architecture
The SDK implements a governed, cooperative 6-agent harness consisting of:
1. **Orchestrator**: Product Manager & System Architect. Authors plans and coordinates agent handoffs.
2. **Researcher**: Diagnostic Investigator. Grounds plans and code in live documentation (`Context7`, `Google Modern Web Guidance`, `Google Developer Knowledge`, `Exa`) and historical Supabase memory.
3. **Builder**: Software Engineer. Implements doc-grounded logic and integrates components.
4. **Auditor**: QA & Security Audit Engineer. Runs syntax verification, security checks, and manages rollback triggers.
5. **SRE**: DevOps & Environment Master. Manages dependencies and runtime health.
6. **Librarian**: Technical Writer. Archives context and synchronizes Supabase vector memory.

---

## 🏛️ Governance & Verification Gates
The orchestrator and `.agents/hooks.json` lifecycle bundle enforce execution boundaries to maintain codebase stability:
*   **4-Stage Lifecycle Hooks**: `PreInvocation` (`bundle_pre_invocation.py`), `PreToolUse` (`safety_gate.py`), `PostToolUse` (`bundle_quality_gate.py`), and `Stop` (`bundle_teardown.py`).
*   **Plan Approval & SHA-256 Fingerprinting Gate**: Pauses the execution loop until the specification/plan is reviewed and approved, then records a SHA-256 hash of the plan.
*   **Documentation Lookup Gate**: Checks that `Context7`, `Google Modern Web Guidance`, or `Google Developer Knowledge` was queried prior to modifying code files.
*   **Root Cause Analysis (RCA)**: Required validation check in the plan explaining the error symptoms, technical cause, and permanent fix.
*   **Self-Correction Checks**: Automatically compiles and validates plan syntax up to 3 times before requesting approval.
*   **Rollback Engine**: If automated compilation or verification checks fail during execution, the system dynamically resets the modified files to restore codebase stability.

---

## 📋 System Documents
*   [README.md](README.md): Installation instructions and CLI options.
*   [Librarian Profile](librarian.md): Memory lookup and lessons archiving guidelines.
*   [Agent Playbooks](agents/): Profile prompt files defining roles and rules for each agent.

---

## ⚡ Task Board & Simulation Mode
*   **Active Checklist**: [task.md](task.md) *(Generated dynamically on run)*
*   **Session Walkthrough**: [walkthrough.md](walkthrough.md) *(Generated dynamically on run)*
*   **Live Agent Monitor**: [agent_live.md](agent_live.md) *(View real-time agent activity)*

> [!TIP]
> **Mock Demo Mode**: Running the orchestrator with the `--mock` flag simulates all execution stages, writes dummy implementation tasks, and drives the `agent_live.md` monitor state graph locally, allowing developers to test and preview the orchestrator's visual tracking systems out of the box.
