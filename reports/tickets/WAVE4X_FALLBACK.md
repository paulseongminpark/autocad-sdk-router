# WAVE4X_FALLBACK

- branch: `cados/w4x-fallback-com-ole`
- status: `implemented_with_remaining_hard_blocks`
- implemented ops: `automate.com.get_app`, `automate.com.get_document`, `automate.com.get_for_command`, `automate.com.get_winapp`, `automate.com.wrapper_for_object`, `module.load.lisp`
- still hard-blocked ops: `automate.com.send_command`, `command.invoke.coroutine`, `command.invoke.sync`, `command.invoke.sync.resbuf`, `command.menu.invoke`, `command.queue.post`, `embed.ole.frame`, `module.lifecycle.on_ole_unload`
- raw command exposed: `false`
- pytest: `495 passed, 20 skipped`
- coverage: `implemented 463 / blocked 54 / gate_pass true`
- cadctl registry coverage: `wired_count 463 / consistent true`

## Notes

- COM fallback is metadata-only (`get_app`, `get_document`, `get_for_command`, `get_winapp`, `wrapper_for_object`).
- `module.load.lisp` is a router-authored `safe_status` AutoLISP adapter only and returns the allow-listed managed `.NET` command map.
- `automate.com.send_command` and all raw command dispatch surfaces remain blocked.
- OLE embed mutation and OLE unload lifecycle callback remain honestly blocked.