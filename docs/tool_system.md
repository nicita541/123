# Tool System

Every tool implements `BaseTool`, declares its name, description, risk level and whether it mutates state. Tool calls are routed through `ToolRegistry`.

