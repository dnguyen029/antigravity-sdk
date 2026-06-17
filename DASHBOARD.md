# 🛸 Antigravity Swarm SDK Dashboard

This dashboard serves as the central documentation and governance hub for the **Antigravity Multi-Agent Swarm**. It connects the different layers of the development workflow, governance rules, and runtime status.

---

### 🗄️ Swarm Architecture
The SDK implements a governed, cooperative multi-agent system consisting of:
1. **Orchestrator**: Product Manager & System Architect. Authors plans and coordinates agent handoffs.
2. **Builder**: Software Engineer. Implements logic and integrates components.
3. **Auditor**: QA & Security Audit Engineer. Runs syntax verification, security checks, and manages rollback triggers.
4. **SRE**: DevOps & Environment Master. Manages dependencies and runtime health.
5. **Librarian**: Technical Writer. Archives context and reads database memories.

---

## 🏛️ Swarm Governance & Verification Gates
The orchestrator enforces strict execution boundaries to maintain codebase stability:
*   **Plan Approval Gate**: A programmatic block that pauses the execution loop until `implementation_plan.md` is reviewed and approved.
*   **Root Cause Analysis (RCA)**: Required validation check in the plan explaining the error symptoms, technical cause, and permanent fix.
*   **Self-Correction Checks**: Automatically compiles and validates plan syntax up to 3 times before requesting approval.
*   **Rollback Engine**: If automated compilation or verification checks fail during execution, the system dynamically resets the modified files to restore codebase stability.

---

## 📋 System Documents
*   [README.md](file:///home/dnguyen029/antigravity-sdk/README.md): Installation instructions and CLI options.
*   [Librarian Profile](file:///home/dnguyen029/antigravity-sdk/librarian.md): Memory lookup and lessons archiving guidelines.
*   [Agent Playbooks](file:///home/dnguyen029/antigravity-sdk/agents/): Profile prompt files defining roles and rules for each agent.

---

## ⚡ Task Board
*   **Active Checklist**: [task.md](file:///home/dnguyen029/antigravity-sdk/task.md) *(Generated dynamically on run)*
*   **Swarm Walkthrough**: [walkthrough.md](file:///home/dnguyen029/antigravity-sdk/walkthrough.md) *(Generated dynamically on run)*
*   **Live Swarm Monitor**: [agent_live.md](file:///home/dnguyen029/antigravity-sdk/agent_live.md) *(View real-time agent activity)*
