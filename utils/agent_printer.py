from typing import Dict, Any, Optional, List, Callable
from agents import Agent, RunHooks, RunContextWrapper, RunItem, trace
from .printer import VideoPrinter

class AgentPrinterHooks(RunHooks):
    """
    Hooks for integrating VideoPrinter with the Agent system.
    This class captures agent events and displays them in the printer.
    """
    
    def __init__(self, printer: VideoPrinter):
        """
        Initialize the hooks with a printer.
        
        Args:
            printer: The VideoPrinter instance to use
        """
        self.printer = printer
        self.current_agent: Optional[str] = None
        
    async def on_run_begin(self, agent: Agent, context: RunContextWrapper, input_list: List[Dict[str, Any]]) -> None:
        """Called when an agent run begins"""
        self.current_agent = agent.name
        self.printer.add_agent_message(agent.name, f"Starting processing")
        
    async def on_run_end(self, agent: Agent, context: RunContextWrapper, result: Any) -> None:
        """Called when an agent run ends"""
        if hasattr(result, 'final_output') and result.final_output:
            output = result.final_output
            if isinstance(output, str) and len(output) > 100:
                output = output[:97] + "..."
            self.printer.add_agent_message(agent.name, f"Completed: {output}")
        else:
            self.printer.add_agent_message(agent.name, "Completed processing")
            
        self.printer.mark_item_done(f"{agent.name}_processing")
        
    async def on_llm_begin(self, agent: Agent, context: RunContextWrapper, messages: List[Dict[str, Any]]) -> None:
        """Called when LLM processing begins"""
        self.printer.update_item(
            f"{agent.name}_llm",
            f"🤔 {agent.name} is thinking...",
            category=agent.name.lower().replace(" ", "_")
        )
        
    async def on_llm_end(self, agent: Agent, context: RunContextWrapper, response: Dict[str, Any]) -> None:
        """Called when LLM processing ends"""
        self.printer.mark_item_done(f"{agent.name}_llm")
        
    async def on_tool_call_begin(self, agent: Agent, context: RunContextWrapper, tool_name: str, tool_input: Dict[str, Any]) -> None:
        """Called when a tool call begins"""
        input_str = str(tool_input)
        if len(input_str) > 50:
            input_str = input_str[:47] + "..."
            
        self.printer.update_item(
            f"{agent.name}_tool_{tool_name}_{hash(str(tool_input)) % 10000}",
            f"🔧 Using tool: {tool_name} with input: {input_str}",
            category=agent.name.lower().replace(" ", "_")
        )
        
    async def on_tool_call_end(self, agent: Agent, context: RunContextWrapper, tool_name: str, tool_input: Dict[str, Any], tool_output: Any) -> None:
        """Called when a tool call ends"""
        output_str = str(tool_output)
        if len(output_str) > 50:
            output_str = output_str[:47] + "..."
            
        item_id = f"{agent.name}_tool_{tool_name}_{hash(str(tool_input)) % 10000}"
        self.printer.mark_item_done(item_id)
        
        # Special handling for specific tools
        if tool_name == "download_video" and isinstance(tool_output, dict) and tool_output.get("status") == "success":
            self.printer.complete_download(tool_output.get("video_path", "unknown"))
            
        if tool_name == "search_youtube_videos" and isinstance(tool_output, list) and len(tool_output) > 0:
            self.printer.update_item(
                f"{agent.name}_search_results",
                f"🔍 Found {len(tool_output)} videos",
                is_done=True,
                category="search"
            )
            
    async def on_handoff_begin(self, agent: Agent, context: RunContextWrapper, target_agent: Agent) -> None:
        """Called when a handoff begins"""
        self.printer.add_agent_message(
            agent.name, 
            f"Handing off to {target_agent.name}"
        )
        
    async def on_handoff_end(self, agent: Agent, context: RunContextWrapper, target_agent: Agent) -> None:
        """Called when a handoff ends"""
        self.printer.add_agent_message(
            target_agent.name, 
            f"Received handoff from {agent.name}"
        )
        
    async def on_new_message(self, agent: Agent, context: RunContextWrapper, message: Dict[str, Any]) -> None:
        """Called when a new message is added"""
        if message.get("role") == "assistant" and message.get("content"):
            content = message["content"]
            if len(content) > 100:
                content = content[:97] + "..."
            self.printer.add_agent_message(agent.name, f"Said: {content}")


def setup_printer() -> tuple[VideoPrinter, Callable]:
    """
    Set up the printer and return it along with a cleanup function.
    
    Returns:
        A tuple containing the printer instance and a cleanup function
    """
    printer = VideoPrinter()
    printer.start()
    
    def cleanup():
        printer.end()
        
    return printer, cleanup


def create_agent_hooks(printer: VideoPrinter) -> AgentPrinterHooks:
    """
    Create agent hooks for the given printer.
    
    Args:
        printer: The VideoPrinter instance
        
    Returns:
        An AgentPrinterHooks instance
    """
    return AgentPrinterHooks(printer) 