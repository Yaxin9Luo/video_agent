import os
import requests
import urllib.parse
import tempfile
import subprocess
import json
import re
from typing import Dict, Any, Optional, List
from agents import function_tool

@function_tool
def search_youtube_videos(query: str, max_results: int) -> List[Dict[str, Any]]:
    """
    Search for videos on YouTube related to the query.
    
    Args:
        query: The search query
        max_results: Maximum number of results to return
        
    Returns:
        List of dictionaries containing video information
    """
    try:
        # Check if yt-dlp is installed
        try:
            subprocess.run(["yt-dlp", "--version"], check=True, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            return [{
                "status": "error",
                "message": "yt-dlp is not installed. Please install it with 'pip install yt-dlp'"
            }]
        
        # Use yt-dlp to search for videos
        search_query = f"ytsearch{max_results}:{query}"
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-json",
            search_query
        ]
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Parse the JSON output (one JSON object per line)
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                video_info = json.loads(line)
                videos.append({
                    "title": video_info.get("title", "Unknown title"),
                    "url": video_info.get("webpage_url", ""),
                    "id": video_info.get("id", ""),
                    "duration": video_info.get("duration", 0),
                    "uploader": video_info.get("uploader", "Unknown uploader"),
                    "description": video_info.get("description", ""),
                    "view_count": video_info.get("view_count", 0)
                })
        
        return videos
    except subprocess.CalledProcessError as e:
        return [{
            "status": "error",
            "message": f"Failed to search videos: {e.stderr}",
            "error": str(e)
        }]
    except Exception as e:
        return [{
            "status": "error",
            "message": f"Failed to search videos: {str(e)}",
            "error": str(e)
        }]

@function_tool
def verify_video_url(video_url: str) -> Dict[str, Any]:
    """
    Verify if a video URL is valid and accessible.
    
    Args:
        video_url: The URL of the video to verify
        
    Returns:
        Dictionary with information about the video
    """
    try:
        # Check if yt-dlp is installed
        try:
            subprocess.run(["yt-dlp", "--version"], check=True, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            return {
                "status": "error",
                "message": "yt-dlp is not installed. Please install it with 'pip install yt-dlp'",
                "error": "yt-dlp not found"
            }
        
        # Extract video ID from URL if it's a YouTube URL
        youtube_id = None
        youtube_pattern = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
        match = re.search(youtube_pattern, video_url)
        if match:
            youtube_id = match.group(1)
        
        # Check if video exists (for YouTube videos)
        if youtube_id:
            check_cmd = ["yt-dlp", "--skip-download", "--playlist-items", "1", f"https://www.youtube.com/watch?v={youtube_id}"]
            try:
                subprocess.run(check_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError:
                return {
                    "status": "error",
                    "message": f"Video unavailable or has been removed: {video_url}",
                    "error": "Video unavailable",
                    "video_id": youtube_id
                }
        
        # Get video info
        info_cmd = ["yt-dlp", "--dump-json", video_url]
        info_result = subprocess.run(info_cmd, check=True, capture_output=True, text=True)
        video_info = json.loads(info_result.stdout)
        
        return {
            "status": "success",
            "message": "Video is available",
            "url": video_url,
            "title": video_info.get("title"),
            "uploader": video_info.get("uploader"),
            "duration": video_info.get("duration"),
            "view_count": video_info.get("view_count", 0),
            "description": video_info.get("description", "")
        }
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "message": f"Failed to verify video: {e.stderr}",
            "error": str(e),
            "command_output": e.stderr
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to verify video: {str(e)}",
            "error": str(e)
        }