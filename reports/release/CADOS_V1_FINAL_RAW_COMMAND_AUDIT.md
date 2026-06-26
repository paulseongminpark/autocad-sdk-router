# CAD OS v1 Final Raw Command Audit

- Packet: CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF
- Status: PASS
- Raw command agent exposure: 0

| operation | status | agent_exposed | blocker_code |
|---|---:|---:|---|
| automate.com.send_command | blocked | False | SAFETY_FORBIDDEN |
| command.invoke.coroutine | blocked | False | SAFETY_FORBIDDEN |
| command.invoke.sync | blocked | False | SAFETY_FORBIDDEN |
| command.invoke.sync.resbuf | blocked | False | SAFETY_FORBIDDEN |
| command.queue.post | blocked | False | SAFETY_FORBIDDEN |
| doc.sendstring | blocked | False | SAFETY_FORBIDDEN |
