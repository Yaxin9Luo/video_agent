"""
Video Downloader Template

This template provides a structure for downloading videos using yt-dlp.
The Code Agent can use this as a reference when generating code.
"""

import os
import subprocess
import json
import re
from typing import Dict, Any, Optional

def download_video(
    video_url: str, 
    output_dir: str = "videos",
    video_title: Optional[str] = None,
    max_height: int = 720
) -> Dict[str, Any]:
    """
    Download a video from a URL using yt-dlp.
    
    Args:
        video_url: The URL of the video to download
        output_dir: Directory to save the video (default: "videos")
        video_title: Optional title to use for the saved file
        max_height: Maximum height of the video in pixels (default: 720)
        
    Returns:
        Dictionary with information about the downloaded video
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate a filename from the URL if title is not provided
    if not video_title:
        # Extract video ID from URL if it's a YouTube URL
        youtube_pattern = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
        match = re.search(youtube_pattern, video_url)
        if match:
            video_id = match.group(1)
            video_title = f"youtube_{video_id}"
        else:
            # Use a hash of the URL as the filename
            video_title = f"video_{hash(video_url) % 10000}"
    
    # Clean the filename (remove special characters)
    video_title = "".join(c for c in video_title if c.isalnum() or c in "._- ").strip()
    if not video_title:
        video_title = f"video_{hash(video_url) % 10000}"
    
    # Full path to save the video (without extension, yt-dlp will add it)
    output_template = os.path.join(output_dir, video_title)
    
    try:
        # Check if video exists before downloading (for YouTube videos)
        youtube_id = None
        match = re.search(youtube_pattern, video_url)
        if match:
            youtube_id = match.group(1)
            check_cmd = ["yt-dlp", "--skip-download", "--playlist-items", "1", f"https://www.youtube.com/watch?v={youtube_id}"]
            try:
                subprocess.run(check_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError:
                return {
                    "status": "error",
                    "message": f"Video unavailable or has been removed: {video_url}",
                    "error": "Video unavailable"
                }
        
        # Download the video using yt-dlp
        cmd = [
            "yt-dlp",
            "-f", f"best[height<={max_height}]",
            "-o", f"{output_template}.%(ext)s",
            "--restrict-filenames",
            "--print", "filename",
            video_url
        ]
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        downloaded_file = result.stdout.strip()
        
        # Get video info
        info_cmd = ["yt-dlp", "--dump-json", video_url]
        info_result = subprocess.run(info_cmd, check=True, capture_output=True, text=True)
        video_info = json.loads(info_result.stdout)
        
        return {
            "status": "success",
            "message": "Video downloaded successfully",
            "video_path": downloaded_file,
            "video_title": os.path.basename(downloaded_file),
            "source_url": video_url,
            "duration": video_info.get("duration"),
            "title": video_info.get("title"),
            "uploader": video_info.get("uploader"),
            "view_count": video_info.get("view_count", 0)
        }
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "message": f"Failed to download video: {e.stderr}",
            "error": str(e),
            "command_output": e.stderr
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to download video: {str(e)}",
            "error": str(e)
        }

# Example usage:
if __name__ == "__main__":
    # Download a video
    result = download_video(
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        output_dir="videos",
        max_height=720
    )
    
    # Print the result
    print(json.dumps(result, indent=2)) 