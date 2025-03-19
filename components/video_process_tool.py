import os
import requests
import urllib.parse
import tempfile
import subprocess
import json
import re
import glob
from typing import Dict, Any, Optional, List
from agents import function_tool
# Add function for extracting video frames
@function_tool
def extract_video_frames(video_path: str, timestamps: List[str], output_dir: Optional[str]) -> Dict[str, Any]:
    """
    Extract frames from a video at specific timestamps.
    
    Args:
        video_path: Path to the video file
        timestamps: List of timestamps in MM:SS format
        output_dir: Directory to save the extracted frames (optional)
        
    Returns:
        Dictionary with information about the extracted frames
    """
    try:
        # Set default values inside the function
        if output_dir is None:
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_dir = os.path.join(os.path.dirname(video_path), f"{video_name}_frames")
        
        # Create directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert timestamps to seconds
        timestamp_seconds = []
        for ts in timestamps:
            parts = ts.split(':')
            if len(parts) == 2:
                minutes, seconds = map(int, parts)
                timestamp_seconds.append(minutes * 60 + seconds)
            else:
                # Handle case where timestamp might be in seconds only
                timestamp_seconds.append(int(ts))
        
        # Extract frames using ffmpeg
        extracted_frames = []
        for i, seconds in enumerate(timestamp_seconds):
            output_file = os.path.join(output_dir, f"frame_{i+1:02d}_{seconds}s.jpg")
            
            cmd = [
                "ffmpeg",
                "-ss", str(seconds),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                output_file,
                "-y"
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            if os.path.exists(output_file):
                extracted_frames.append({
                    "timestamp": timestamps[i],
                    "seconds": seconds,
                    "path": output_file
                })
        
        return {
            "status": "success",
            "frames_dir": output_dir,
            "extracted_frames": extracted_frames,
            "total_frames": len(extracted_frames)
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "frames_dir": output_dir if 'output_dir' in locals() else None
        }

@function_tool
def read_transcript_json(json_path: str) -> Dict[str, Any]:
    """
    Read a transcript JSON file and return its contents.
    
    Args:
        json_path: Path to the JSON file containing transcript data
        
    Returns:
        Dictionary with transcript data
    """
    try:
        if not os.path.exists(json_path):
            return {
                "status": "error",
                "message": f"File not found: {json_path}"
            }
        
        with open(json_path, 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
        
        return {
            "status": "success",
            "transcript_data": transcript_data
        }
    
    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": f"Invalid JSON file: {json_path}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@function_tool
def create_video_from_frames(
    frames_dir: str,
    output_path: Optional[str],
    fps: int,
    duration_per_frame: int,
    text_overlays: Optional[List[Dict[str, str]]],
    add_transitions: bool
) -> Dict[str, Any]:
    """
    Create a video from a directory of frames using ffmpeg.
    
    Args:
        frames_dir: Directory containing the frames
        output_path: Path to save the output video (optional)
        fps: Frames per second for the output video
        duration_per_frame: Duration in seconds to show each frame
        text_overlays: List of dictionaries with text to overlay on each frame
        add_transitions: Whether to add transitions between frames
        
    Returns:
        Dictionary with information about the created video
    """
    try:
        # Set default values inside the function instead of in the parameters
        if output_path is None:
            output_dir = os.path.join(os.path.dirname(frames_dir), "output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "summary_video.mp4")
        
        if fps is None:
            fps = 1
            
        if duration_per_frame is None:
            duration_per_frame = 3
            
        if add_transitions is None:
            add_transitions = True
        
        # Check if frames directory exists
        if not os.path.exists(frames_dir):
            return {
                "status": "error",
                "message": f"Frames directory not found: {frames_dir}"
            }
        
        # Get list of frames
        frames = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))
        if not frames:
            frames = sorted(glob.glob(os.path.join(frames_dir, "*.png")))
        
        if not frames:
            return {
                "status": "error",
                "message": f"No frames found in directory: {frames_dir}"
            }
        
        # Create a temporary directory for the ffmpeg script
        temp_dir = tempfile.mkdtemp()
        script_path = os.path.join(temp_dir, "ffmpeg_script.txt")
        
        # Calculate total duration
        total_frames = len(frames)
        total_duration = total_frames * duration_per_frame
        
        # Create ffmpeg script
        with open(script_path, "w") as f:
            for i, frame in enumerate(frames):
                # Extract timestamp from filename if available
                timestamp_match = re.search(r'(\d+)s\.', os.path.basename(frame))
                timestamp = timestamp_match.group(1) if timestamp_match else str(i)
                
                # Get text overlay for this frame
                text = ""
                if text_overlays and i < len(text_overlays):
                    text = text_overlays[i].get("text", "")
                
                # Calculate start and end times for this frame
                start_time = i * duration_per_frame
                end_time = (i + 1) * duration_per_frame
                
                # Add frame to script with fade in/out if transitions are enabled
                if add_transitions:
                    fade_duration = min(0.5, duration_per_frame / 4)
                    f.write(f"file '{frame}'\n")
                    f.write(f"duration {duration_per_frame}\n")
                    if i < total_frames - 1:  # Don't add outpoint for last frame
                        f.write(f"outpoint {end_time}\n")
                else:
                    f.write(f"file '{frame}'\n")
                    f.write(f"duration {duration_per_frame}\n")
        
        # Create video using ffmpeg
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", script_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-vf", "fps=25",  # Force 25fps for smooth playback
            output_path,
            "-y"  # Overwrite existing file
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Add text overlays if provided
        if text_overlays:
            temp_output = os.path.join(temp_dir, "temp_output.mp4")
            
            # Create filter complex for text overlays
            filter_complex = []
            for i, overlay in enumerate(text_overlays):
                if i >= total_frames:
                    break
                    
                text = overlay.get("text", "")
                if not text:
                    continue
                    
                start_time = i * duration_per_frame
                end_time = (i + 1) * duration_per_frame
                
                # Escape special characters
                text = text.replace("'", "\\'").replace(":", "\\:")
                
                # Add text overlay
                filter_complex.append(
                    f"drawtext=text='{text}':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:"
                    f"boxborderw=5:x=(w-text_w)/2:y=h-text_h-20:enable='between(t,{start_time},{end_time})'"
                )
            
            if filter_complex:
                # Apply text overlays
                text_cmd = [
                    "ffmpeg",
                    "-i", output_path,
                    "-vf", ",".join(filter_complex),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    temp_output,
                    "-y"
                ]
                
                subprocess.run(text_cmd, check=True, capture_output=True)
                
                # Replace original output with the one with text overlays
                os.replace(temp_output, output_path)
        
        # Get video information
        info_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration,nb_frames",
            "-of", "json",
            output_path
        ]
        
        info_result = subprocess.run(info_cmd, check=True, capture_output=True, text=True)
        info_json = json.loads(info_result.stdout)
        
        # Extract video information
        stream_info = info_json.get("streams", [{}])[0]
        width = stream_info.get("width", 0)
        height = stream_info.get("height", 0)
        duration = float(stream_info.get("duration", total_duration))
        frame_count = int(stream_info.get("nb_frames", total_frames))
        
        # Clean up temporary files
        try:
            os.remove(script_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        return {
            "status": "success",
            "output_path": output_path,
            "duration": int(duration),
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "total_frames_used": total_frames
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "output_path": output_path if 'output_path' in locals() else None
        }

@function_tool
def extract_audio_from_video(video_path: str, output_path: Optional[str]) -> Dict[str, Any]:
    """
    Extract audio from a video file.
    
    Args:
        video_path: Path to the video file
        output_path: Path to save the output audio file (optional)
        
    Returns:
        Dictionary with information about the extracted audio
    """
    try:
        # Set default values inside the function
        if output_path is None:
            output_dir = os.path.dirname(video_path)
            output_basename = os.path.splitext(os.path.basename(video_path))[0] + ".mp3"
            output_path = os.path.join(output_dir, output_basename)
        
        # Check if video file exists
        if not os.path.exists(video_path):
            return {
                "status": "error",
                "message": f"Video file not found: {video_path}"
            }
        
        # Extract audio using ffmpeg
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-q:a", "0",
            "-map", "a",
            output_path,
            "-y"  # Overwrite existing file
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Check if output file exists
        if not os.path.exists(output_path):
            return {
                "status": "error",
                "message": f"Failed to extract audio: output file not created"
            }
        
        # Get audio information
        info_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=duration,sample_rate,channels",
            "-of", "json",
            output_path
        ]
        
        info_result = subprocess.run(info_cmd, check=True, capture_output=True, text=True)
        info_json = json.loads(info_result.stdout)
        
        # Extract audio information
        stream_info = info_json.get("streams", [{}])[0]
        duration = float(stream_info.get("duration", 0))
        sample_rate = int(stream_info.get("sample_rate", 0))
        channels = int(stream_info.get("channels", 0))
        
        return {
            "status": "success",
            "output_path": output_path,
            "duration": int(duration),
            "sample_rate": sample_rate,
            "channels": channels
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "output_path": output_path if 'output_path' in locals() else None
        }
