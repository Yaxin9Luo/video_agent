import os
import json
from typing import Dict, List, Optional, Any
from agents import function_tool



@function_tool
def list_available_videos(video_dir: str) -> List[str]:
    """List all available videos in the video directory"""
    if video_dir is None:
        video_dir = os.path.join(os.getcwd(), "videos")
        
    if not os.path.exists(video_dir):
        return []
    
    videos = [f for f in os.listdir(video_dir) 
             if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    return videos

@function_tool
def get_video_info(video_name: str, video_dir: str) -> Dict[str, Any]:
    """Get information about a specific video"""
    if video_dir is None:
        video_dir = os.path.join(os.getcwd(), "videos")
        
    video_path = os.path.join(video_dir, video_name)
    if not os.path.exists(video_path):
        return {"error": f"Video {video_name} not found"}
    
    # In a real implementation, we would use a library like ffprobe to get video metadata
    # For now, we'll return some basic info
    file_size = os.path.getsize(video_path) / (1024 * 1024)  # Size in MB
    return {
        "name": video_name,
        "path": video_path,
        "size_mb": round(file_size, 2),
        "exists": True
    }


