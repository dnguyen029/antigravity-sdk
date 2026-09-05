# 🛰️ Swarm Live Execution Monitor

This dashboard displays the active execution phase and handoff flows of the Antigravity Swarm.

---

## ⚡ Active Task
*   **Task**: Swarm Idle (No active session)
*   **Active Agent**: None
*   **Current Phase**: Idle

---

## 📊 Live Flow Monitor

```mermaid
graph TD
    Discovery(🔍 Discovery) --> Planning(📋 Planning)
    Planning --> Correction{🔄 Self-Correction}
    Correction -->|Flawed Plan| Planning
    Correction -->|Valid Plan| Approval(🛑 Approval Gate)
    Approval --> Execution(💻 Execution)
    Execution --> Verification(🛡️ Verification)
    Verification --> Escalation{🛑 Escalation Gate}
    Escalation -->|Failed| Rollback(⚠️ Rollback)
    Escalation -->|Passed| Success(🎉 Success)
    style Discovery fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#999
    style Planning fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#999
    style Correction fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#999
    style Approval fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#999
    style Execution fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#999
    style Verification fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#999
    style Escalation fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#999
    style Rollback fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#999
    style Success fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#999
```
