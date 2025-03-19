from typing import Any, Dict, Optional
import time
from rich.console import Console, Group
from rich.live import Live
from rich.spinner import Spinner
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, TaskID
from rich.table import Table

class VideoPrinter:
    """
    A printer for displaying real-time progress of the VideoAgent system.
    Uses rich library to create a dynamic console interface.
    """
    
    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the VideoPrinter.
        
        Args:
            console: Optional Console instance. If not provided, a new one will be created.
        """
        self.console = console or Console()
        self.live = Live(console=self.console, refresh_per_second=4)
        self.items: Dict[str, tuple[str, bool, str]] = {}  # id -> (content, is_done, category)
        self.hide_done_ids: set[str] = set()
        self.progress = Progress()
        self.progress_tasks: Dict[str, TaskID] = {}
        self.download_progress: Optional[TaskID] = None
        self.start_time = time.time()
        
    def start(self) -> None:
        """Start the live display"""
        self.live.start()
        self.update_item("system", "🎬 Video Agent System Initialized", category="system")
        
    def end(self) -> None:
        """Stop the live display and show final summary"""
        elapsed_time = time.time() - self.start_time
        self.update_item(
            "system_end", 
            f"✨ Processing completed in {elapsed_time:.2f} seconds", 
            is_done=True,
            category="system"
        )
        self.flush()
        self.live.stop()
        
    def hide_done_checkmark(self, item_id: str) -> None:
        """Hide the checkmark for a completed item"""
        self.hide_done_ids.add(item_id)
        
    def update_item(
        self, 
        item_id: str, 
        content: str, 
        is_done: bool = False, 
        hide_checkmark: bool = False,
        category: str = "default"
    ) -> None:
        """
        Update or add an item to the display.
        
        Args:
            item_id: Unique identifier for the item
            content: Text content to display
            is_done: Whether the item is completed
            hide_checkmark: Whether to hide the checkmark when done
            category: Category of the item (system, search, download, transcribe, etc.)
        """
        self.items[item_id] = (content, is_done, category)
        if hide_checkmark:
            self.hide_done_ids.add(item_id)
        self.flush()
        
    def mark_item_done(self, item_id: str) -> None:
        """Mark an item as completed"""
        if item_id in self.items:
            content, _, category = self.items[item_id]
            self.items[item_id] = (content, True, category)
            self.flush()
            
    def add_progress_task(self, task_id: str, description: str, total: float = 100.0) -> None:
        """
        Add a progress bar task.
        
        Args:
            task_id: Unique identifier for the task
            description: Description of the task
            total: Total steps for completion
        """
        task = self.progress.add_task(description, total=total)
        self.progress_tasks[task_id] = task
        self.flush()
        
    def update_progress(self, task_id: str, advance: float = 1.0, description: Optional[str] = None) -> None:
        """
        Update a progress bar task.
        
        Args:
            task_id: Identifier of the task to update
            advance: Amount to advance the progress
            description: New description (optional)
        """
        if task_id in self.progress_tasks:
            if description:
                self.progress.update(self.progress_tasks[task_id], description=description, advance=advance)
            else:
                self.progress.update(self.progress_tasks[task_id], advance=advance)
            self.flush()
            
    def start_download(self, video_title: str, size_mb: float) -> None:
        """
        Start tracking a video download.
        
        Args:
            video_title: Title of the video being downloaded
            size_mb: Size of the video in MB
        """
        self.download_progress = self.progress.add_task(f"Downloading: {video_title}", total=size_mb)
        self.update_item("download", f"📥 Downloading video: {video_title}", category="download")
        self.flush()
        
    def update_download(self, advance: float, percentage: float) -> None:
        """Update the download progress"""
        if self.download_progress is not None:
            self.progress.update(self.download_progress, advance=advance)
            self.flush()
            
    def complete_download(self, video_path: str) -> None:
        """Mark a download as complete"""
        if self.download_progress is not None:
            self.progress.update(self.download_progress, completed=True)
            self.update_item("download", f"✅ Download complete: {video_path}", is_done=True, category="download")
            self.download_progress = None
            self.flush()
    
    def add_agent_message(self, agent_name: str, message: str) -> None:
        """
        Add a message from an agent.
        
        Args:
            agent_name: Name of the agent
            message: The message content
        """
        item_id = f"{agent_name}_{int(time.time() * 1000)}"
        prefix = {
            "Manager Agent": "🧠",
            "Searcher Agent": "🔍",
            "Transcriber Agent": "🎤",
            "Segmenter Agent": "✂️",
            "Summarizer Agent": "📝",
            "Editor Agent": "🎞️"
        }.get(agent_name, "🤖")
        
        self.update_item(
            item_id,
            f"{prefix} {agent_name}: {message}",
            category=agent_name.lower().replace(" ", "_")
        )
    
    def flush(self) -> None:
        """Update the display with current items"""
        # Group items by category
        categories = {}
        for item_id, (content, is_done, category) in self.items.items():
            if category not in categories:
                categories[category] = []
                
            if is_done:
                prefix = "✅ " if item_id not in self.hide_done_ids else ""
                categories[category].append(prefix + content)
            else:
                categories[category].append(Spinner("dots", text=content))
        
        # Create panels for each category
        panels = []
        
        # System panel always first
        if "system" in categories:
            system_panel = Panel(
                Group(*categories["system"]),
                title="System",
                border_style="bright_blue"
            )
            panels.append(system_panel)
            
        # Agent panels
        agent_categories = [
            "manager_agent", "searcher_agent", "transcriber_agent", 
            "segmenter_agent", "summarizer_agent", "editor_agent"
        ]
        
        for category in agent_categories:
            if category in categories and categories[category]:
                title = " ".join(word.capitalize() for word in category.split("_"))
                panels.append(
                    Panel(
                        Group(*categories[category]),
                        title=title,
                        border_style="green"
                    )
                )
        
        # Other categories
        for category, items in categories.items():
            if category != "system" and category not in agent_categories and items:
                title = " ".join(word.capitalize() for word in category.split("_"))
                panels.append(
                    Panel(
                        Group(*items),
                        title=title,
                        border_style="yellow"
                    )
                )
        
        # Add progress bars if any
        if self.progress_tasks or self.download_progress is not None:
            panels.append(self.progress)
            
        # Update the live display
        self.live.update(Group(*panels)) 