# Architecture

The agent is split into core, planning, execution, tools, safety, verification, review, context, memory, storage, events and UI layers. LLM output is treated as a proposal and must pass schema validation, safety checks and approval before a tool is invoked.

