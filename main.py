import os
import asyncio
import argparse
from agents import set_default_openai_key, RunConfig
from utils.agent_printer import setup_printer, create_agent_hooks
from pydantic import BaseModel
from agents import Agent, handoff, Runner, trace, WebSearchTool
from components.search_tool import *
from components.code_tool import *
from components.manager_tool import *
from components.video_process_tool import *
from agents.model_settings import ModelSettings
from openai import OpenAI
import tempfile
import json
import datetime
import subprocess
from typing import Optional, List, Dict, Any
import re

class codeagentoutput(BaseModel):
    video_path: str
    audio_path: str
    video_exists: bool
    audio_exists: bool

class videounderstandingoutput(BaseModel):
    summary: str
    key_steps: Optional[List[Dict[str, Any]]] = None
    frames_dir: str

class videoeditingoutput(BaseModel):
    output_video_path: str
    duration: int
    frame_count: int

# Remove ASR agent since we'll use direct API calls
code_agent = Agent(
    name="Code Agent",
    instructions="""
    You are a Code Agent responsible for generating and executing Python code.
    Your job is to:
    1. Take a task description and input data
    2. Generate Python code to accomplish the task
    3. Execute the code using the execute_python_code tool and return the results
    
    For video downloading tasks:
    - Use yt-dlp library for downloading videos
    - Create a 'videos' directory in the CURRENT WORKING DIRECTORY if it doesn't exist
    - Download the video to the 'videos' directory in the CURRENT WORKING DIRECTORY
    - Use a SIMPLE and SHORT filename based on the video content type (e.g., "steak_cooking.mp4", "guitar_tutorial.mp4")
    - EXTRACT the AUDIO from the video and save it as an MP3 file with the same base name
    - Handle errors gracefully
    - Provide detailed output information including the saved file paths for both video and audio
    
    IMPORTANT:
    - When you receive a video URL, IMMEDIATELY generate code to download it
    - DO NOT ask for additional information or clarification
    - ALWAYS use the execute_python_code tool to run your code
    - After executing the code, IMMEDIATELY return the results
    - Include the full paths to the downloaded video AND audio files in your response
    - ALWAYS use os.path.abspath() to get the absolute path of the current working directory
    - Use a SIMPLE filename format like "content_type.mp4" instead of the full video title
    - For audio extraction, PREFER using yt-dlp's built-in functionality directly rather than ffmpeg
    
    WORKFLOW:
    1. Generate Python code to download the video and extract audio
    2. Use execute_python_code tool to run the code
    3. Return the results from the tool
    
    SAMPLE CODE FOR DOWNLOADING VIDEOS AND EXTRACTING AUDIO:
    ```python
    import os
    import subprocess
    import re
    
    # Get the current working directory
    current_dir = os.path.abspath(os.getcwd())
    
    # Create videos directory if it doesn't exist
    videos_dir = os.path.join(current_dir, "videos")
    os.makedirs(videos_dir, exist_ok=True)
    
    # Download video using yt-dlp
    video_url = "[URL]"
    
    # Use a simple filename based on video content
    video_type = "cooking_video"  # This should be determined based on the video content
    video_filename = f"{video_type}.mp4"
    audio_filename = f"{video_type}.mp3"
    video_path = os.path.join(videos_dir, video_filename)
    audio_path = os.path.join(videos_dir, audio_filename)
    
    try:
        # Check if yt-dlp is installed
        subprocess.run(["yt-dlp", "--version"], check=True, capture_output=True)
        
        # Download the video with a specific filename
        print(f"Downloading video to {video_path}...")
        video_result = subprocess.run(
            ["yt-dlp", "-o", video_path, "--format", "mp4", video_url],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Download audio separately using yt-dlp
        print(f"Extracting audio to {audio_path}...")
        audio_result = subprocess.run(
            ["yt-dlp", "-o", audio_path, "--extract-audio", "--audio-format", "mp3", video_url],
            check=True,
            capture_output=True,
            text=True
        )
        audio_extracted = True
        
        # Get the output file paths
        video_file_path = video_path
        audio_file_path = audio_path
        
        # Check if files exist
        video_exists = os.path.exists(video_path)
        audio_exists = os.path.exists(audio_path)
        
        status = "success"
        message = f"Video downloaded: {video_exists}, Audio extracted: {audio_exists}"
        
        # Add file information to the result
        file_info = {
            "video_path": video_file_path if video_exists else None,
            "audio_path": audio_file_path if audio_exists else None,
            "video_exists": video_exists,
            "audio_exists": audio_exists
        }
            
    except subprocess.CalledProcessError as e:
        status = "error"
        message = f"Failed to process media: {e.stderr}"
        error = str(e)
        file_info = {"error": error}
    except Exception as e:
        status = "error"
        message = f"Error: {str(e)}"
        error = str(e)
        file_info = {"error": error}
    ```
    
    Always check if required packages are installed before using them.
    Write clean, efficient, and well-documented code.
    """,
    handoff_description="An agent that generates and executes Python code for tasks like video downloading and audio extraction.",
    tools=[execute_python_code, get_installed_packages],
    model_settings=ModelSettings(tool_choice="auto"),
    model="o3-mini",
    output_type=codeagentoutput
) 

# Add Video Editing Agent
video_editing_agent = Agent(
    name="Video Editing Agent",
    instructions="""
    You are a Video Editing Agent responsible for creating a short video from key frames extracted from a longer video.
    Your job is to:
    1. Take a directory of key frames and transcript information
    2. Create a short video that highlights the key steps in the process
    3. Add text overlays to explain each step
    4. Return information about the created video
    
    For video editing tasks:
    - Use the create_video_from_frames tool to combine frames into a video with text overlays
    - Create a smooth, professional-looking video
    - Keep the output video concise (typically 30-60 seconds)
    
    IMPORTANT:
    - When you receive a frames directory and key steps information, IMMEDIATELY use the create_video_from_frames tool
    - You MUST specify ALL parameters when calling create_video_from_frames:
      * frames_dir: The directory containing the frames
      * output_path: Set to null to use default output path
      * fps: Set to 1 for standard slideshow speed
      * duration_per_frame: Set to 3 seconds per frame
      * text_overlays: Array of objects with text for each frame
      * add_transitions: Set to true to add smooth transitions
    - Use the key steps information to determine what text to overlay on each frame
    - Make sure the text is readable (appropriate font size, color, and position)
    - Include a brief title at the beginning of the video
    - Use transitions between frames for a professional look
    - Return the path to the created video and information about its duration and frame count
    
    WORKFLOW:
    1. Read the key frames from the provided directory
    2. Generate a script for the video based on the key steps
    3. Use the create_video_from_frames tool to create a video with text overlays
    4. Return information about the created video
    """,
    handoff_description="An agent that creates short videos from key frames with text overlays.",
    tools=[execute_python_code, create_video_from_frames],
    model_settings=ModelSettings(tool_choice="auto"),
    model="o3-mini",
    output_type=videoeditingoutput
)

# Add Video Understanding Agent
video_understanding_agent = Agent(
    name="Video Understanding Agent",
    instructions="""
    You are a Video Understanding Agent responsible for extracting key frames and summarizing the process shown in a video.
    Your job is to:
    1. Take a video file path and transcript information
    2. Extract frames from key timestamps in the video
    3. Analyze the frames and transcript to understand the process shown
    4. Create a comprehensive summary of the steps shown in the video
    5. Return the summary and key steps with timestamps and frame references
    
    For video analysis tasks:
    - Use the read_transcript_json tool to read the transcript data from the JSON file
    - Use the extract_video_frames tool to extract frames at key timestamps
    - Use the transcript and key points from the audio processing to identify important moments
    - Create a detailed summary of the process shown in the video
    - Identify and list the key steps in chronological order
    - Include timestamps for each key step
    
    IMPORTANT:
    - When you receive a video path and transcript data, IMMEDIATELY read the transcript JSON file
    - You MUST specify ALL parameters when calling extract_video_frames:
      * video_path: The path to the video file
      * timestamps: Array of timestamps in MM:SS format
      * output_dir: Set to null to use default output directory
    - Use the key points and timestamps from the transcript to identify important moments
    - Extract frames at those key timestamps
    - Focus on understanding the PROCESS being demonstrated in the video
    - For cooking videos, identify ingredients, techniques, and important steps
    - Create a summary that would help someone learn how to perform the process
    - Include specific timestamps for each key step
    - Reference the extracted frames in your summary
    - If you can't identify any key steps, you can return an empty list for key_steps
    
    WORKFLOW:
    1. Read the transcript and key points from the provided JSON file using read_transcript_json
    2. Identify key timestamps where important steps occur
    3. Use extract_video_frames to capture frames at those timestamps
    4. Analyze the frames and transcript together
    5. Create a comprehensive summary and list of key steps
    6. Return the results with at minimum a summary and frames_dir, and optionally key_steps if you identified any
    """,
    handoff_description="An agent that extracts key frames and summarizes the process shown in a video.",
    tools=[execute_python_code, extract_video_frames, read_transcript_json],
    model_settings=ModelSettings(tool_choice="auto"),
    model="gpt-4o",
    output_type=videounderstandingoutput
)

search_agent = Agent(
    name="Search Agent",
    instructions="""
    You are a Searcher Agent responsible for finding high-quality videos.
    Your job is to:
    1. Take a search query for a specific type of video
    2. Search for relevant videos online using the web search tool
    3. Use search_youtube_videos to find specific videos on YouTube
    4. Prioritize videos with high view counts (popular videos)
    5. Verify the video URLs to ensure they are valid and accessible
    6. Return the best video URL and information
    
    Focus on finding high-quality, relevant videos that match the user's request.
    When searching for cooking videos, look for clear instructional content from reputable channels.
    
    IMPORTANT: 
    - Find ONE best video with high view count
    - Verify the video URL ONLY ONCE before returning it
    - After verification is successful, IMMEDIATELY return the result to the Code Agent WITHOUT USING ANY MORE TOOLS
    - Format your final response clearly as:
      "I found this video: [TITLE] by [UPLOADER]. The video is [DURATION] seconds long with [VIEW_COUNT] views. Please download this video from [URL]"
    - DO NOT verify the same URL multiple times
    - DO NOT continue searching after finding a suitable video
    - DO NOT use any tools after verification is successful
    
    WORKFLOW:
    1. Search for videos using search_youtube_videos
    2. Select the best video based on relevance and view count
    3. Verify the video URL ONCE using verify_video_url
    4. If verification is successful, STOP using tools and RETURN your final response to the Code Agent using handoff()
    """,
    handoff_description="An agent that searches for high-quality videos and returns their URLs.",
    tools=[WebSearchTool(), search_youtube_videos, verify_video_url],
    model_settings=ModelSettings(tool_choice="auto"),
    handoffs=[handoff(code_agent)]
)

# Create the Manager Agent
manager_agent = Agent(
    name="Manager Agent",
    instructions="""
    You are a Manager Agent responsible for coordinating the video processing workflow.
    Your job is to:
    1. Understand the user's request for searching for a video
    2. Check if the requested video is available or needs to be searched
    3. Coordinate with specialized agents to process the video:
       - Searcher Agent: For finding high-quality videos and returning their URLs
       - Code Agent: For generating and executing code to download videos
       - Video Understanding Agent: For extracting key frames and summarizing the process
       - Video Editing Agent: For creating a short video from key frames with text overlays
    4. Present the final result to the user
    
    Always maintain a clear workflow and delegate tasks appropriately.
    
    IMPORTANT WORKFLOW:
    1. If the user doesn't specify a video file, use the Searcher Agent to find a suitable video by calling transfer_to_searcher_agent()
    2. Once the Searcher Agent returns a video URL, IMMEDIATELY extract the URL from the response
    3. IMMEDIATELY transfer to the Code Agent by calling transfer_to_code_agent() with EXPLICIT instructions to download the video
    4. After the video is downloaded, finish the workflow and return a summary to the user
    
    HANDLING SEARCH AGENT RESULTS:
    - When the Searcher Agent returns results, DO NOT ask for more information or clarification
    - The Searcher Agent will return a response like: "I found this video: [TITLE] by [UPLOADER]. The video is [DURATION] seconds long with [VIEW_COUNT] views. Please download this video from [URL]"
    - IMMEDIATELY extract the video URL from this response - it will be in parentheses or at the end of the response
    - IMMEDIATELY call transfer_to_code_agent() with the extracted URL
    - Example: transfer_to_code_agent("Please download this video: https://www.youtube.com/watch?v=nsw0Px-Pho8 and save it to the videos directory")
    
    HANDLING CODE AGENT RESULTS:
    - When the Code Agent returns results, check if the download was successful
    - If successful, return the path to the downloaded video and a success message
    - If unsuccessful, explain the error and suggest alternatives
    
    IMPORTANT: 
    - DO NOT get stuck in loops or continue asking for information after receiving results from agents
    - After receiving a response from the Search Agent, you MUST call transfer_to_code_agent()
    - DO NOT try to download the video yourself - that is the Code Agent's job
    - DO NOT ask the user for more information after the Search Agent returns results
    
    EXAMPLE WORKFLOW:
    1. User asks to find and download a cooking video
    2. Call transfer_to_searcher_agent() to find a video
    3. Searcher Agent returns: "I found this video: 'How to Cook Steak' by Chef John. The video is 300 seconds long with 1,000,000 views. Please download this video from (https://www.youtube.com/watch?v=example)"
    4. Extract URL: https://www.youtube.com/watch?v=example
    5. Call transfer_to_code_agent("Please download this video: https://www.youtube.com/watch?v=example and save it to the videos directory")
    6. Code Agent downloads the video and returns the results
    7. Return a summary to the user
    """,
    handoffs=[
        handoff(search_agent),
        handoff(code_agent)
    ],
    tools=[list_available_videos, get_video_info]
)

# Add functions for direct audio transcription
def format_timestamp(seconds: float) -> str:
    """
    Format seconds into MM:SS format.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"

def transcribe_audio(audio_path: str, client: OpenAI) -> str:
    """
    Transcribe audio using OpenAI's Audio API directly.
    
    Args:
        audio_path: Path to the audio file
        client: OpenAI client
        
    Returns:
        Transcribed text with timestamps
    """
    print(f"Transcribing audio file: {audio_path}")
    
    try:
        with open(audio_path, "rb") as audio_file:
            # Use the OpenAI Audio API to transcribe the audio
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
            
            # Format the response with timestamps
            formatted_transcript = ""
            for segment in response.segments:
                start_time = format_timestamp(segment.start)
                end_time = format_timestamp(segment.end)
                text = segment.text.strip()
                formatted_transcript += f"[{start_time}] - [{end_time}] - {text}\n"
            
            return formatted_transcript.strip()
    
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return f"Error transcribing audio: {str(e)}"

def extract_key_points(transcript: str) -> List[str]:
    """
    Extract key information points from the transcript.
    
    Args:
        transcript: Transcript text with timestamps
        
    Returns:
        List of key information points
    """
    key_points = []
    
    # Split transcript by lines
    lines = transcript.strip().split('\n')
    
    # List of keywords that might indicate important information
    key_words = [
        "important", "key", "step", "first", "second", "third", "next", 
        "finally", "remember", "note", "tip", "trick", "essential",
        "must", "crucial", "critical", "necessary", "vital"
    ]
    
    for line in lines:
        # Check if line contains any keywords
        if any(word in line.lower() for word in key_words):
            key_points.append(line)
        # Or if it contains numbered steps
        elif re.search(r'\d+\s*[\.:]', line):
            key_points.append(line)
    
    return key_points

def save_transcript_to_json(audio_path: str, transcript: str, key_points: Optional[List[str]] = None) -> str:
    """
    Save the transcript results to a JSON file.
    
    Args:
        audio_path: Path to the audio file
        transcript: Transcribed text
        key_points: List of extracted key points
        
    Returns:
        Path to the JSON file
    """
    # Create transcripts directory
    transcripts_dir = os.path.join(os.path.dirname(audio_path), "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)
    
    # Generate JSON filename
    audio_basename = os.path.basename(audio_path)
    json_filename = os.path.splitext(audio_basename)[0] + "_transcript.json"
    json_path = os.path.join(transcripts_dir, json_filename)
    
    # Prepare data
    transcript_data = {
        "audio_path": audio_path,
        "transcript": transcript,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # Add key points if available
    if key_points:
        transcript_data["key_points"] = key_points
    
    # Save as JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)
    
    return json_path

def convert_audio_to_mp3(audio_path: str, max_duration: Optional[int] = 120) -> str:
    """
    Convert audio file to MP3 format and limit its length.
    
    Args:
        audio_path: Path to the original audio file
        max_duration: Maximum duration in seconds
        
    Returns:
        Path to the converted MP3 file
    """
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Generate output filename
        output_basename = "converted_audio.mp3"
        output_path = os.path.join(temp_dir, output_basename)
        
        # Conversion command
        cmd = [
            "ffmpeg",
            "-i", audio_path,
            "-t", str(max_duration),  # Limit length
            "-ac", "1",  # Mono
            "-ar", "16000",  # 16kHz sampling rate
            "-ab", "64k",  # 64kbps bitrate
            output_path,
            "-y"  # Overwrite existing file
        ]
        
        # Execute command
        subprocess.run(cmd, capture_output=True)
        
        print(f"Audio converted and saved to: {output_path}")
        return output_path
    
    except Exception as e:
        print(f"Error converting audio: {e}")
        return audio_path

async def process_audio(audio_path: str) -> Dict[str, Any]:
    """
    Process audio file using direct OpenAI API calls.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Dictionary with transcript and key points
    """
    try:
        # Check if file exists
        if not os.path.exists(audio_path):
            return {"error": f"Audio file does not exist: {audio_path}"}
        
        # Convert audio file to smaller MP3
        print("Converting audio file...")
        converted_audio = convert_audio_to_mp3(audio_path, max_duration=600)  # 10 minutes max
        
        # Initialize OpenAI client
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Transcribe audio
        print("Transcribing audio...")
        transcript = transcribe_audio(converted_audio, client)
        
        # Extract key points
        key_points = extract_key_points(transcript)
        
        # Save as JSON
        json_path = save_transcript_to_json(audio_path, transcript, key_points)
        print(f"Transcription results saved to: {json_path}")
        
        # Clean up temporary files
        try:
            os.remove(converted_audio)
            os.rmdir(os.path.dirname(converted_audio))
            print("Temporary files cleaned up")
        except:
            pass
        
        return {
            "transcript": transcript,
            "key_points": key_points,
            "json_path": json_path
        }
        
    except Exception as e:
        print(f"Error processing audio: {e}")
        return {"error": str(e)}

# Function to process user requests
async def process_request(user_request: str, run_config: Optional[RunConfig] = None, hooks = None) -> str:
    """
    Process a user request to create a short video with key steps.
    
    Args:
        user_request: The user's request string
        run_config: Optional RunConfig for customizing the run
        hooks: Optional hooks for the run
        
    Returns:
        A response string with the result of the processing
    """
    with trace("Video Processing Workflow"):
        # Run the manager agent to coordinate the workflow
        manager_result = await Runner.run(manager_agent, user_request, run_config=run_config, hooks=hooks, max_turns=20)
        
        manager_output = manager_result.final_output
        
        # Check if the output contains information about downloaded video/audio
        if isinstance(manager_output, codeagentoutput):
            # Try to extract audio path from the output
            audio_path = manager_output.audio_path
            video_path = manager_output.video_path
            
            if audio_path and os.path.exists(audio_path):
                print(f"Found audio path in output: {audio_path}. Processing audio using direct API calls...")
                
                # Process audio using direct API calls
                audio_result = await process_audio(audio_path)
                
                if "error" in audio_result:
                    return f"{manager_output}\n\nAudio transcription failed: {audio_result['error']}"
                
                # Get the JSON path from the audio processing result
                json_path = audio_result.get("json_path")
                
                # Only proceed with video understanding if not skipped
                if json_path and os.path.exists(json_path) and video_path and os.path.exists(video_path):
                    print(f"Found transcript JSON at {json_path}. Transferring to Video Understanding Agent...")
                    
                    # Transfer to Video Understanding Agent
                    video_understanding_request = f"Please analyze this video: {video_path} and use the transcript data from {json_path} to extract key frames and summarize the process."
                    
                    video_understanding_result = await Runner.run(
                        video_understanding_agent, 
                        video_understanding_request, 
                        run_config=run_config, 
                        hooks=hooks, 
                        max_turns=10
                    )
                    
                    video_understanding_output = video_understanding_result.final_output
                    
                    if isinstance(video_understanding_output, videounderstandingoutput):
                        # Format the key steps
                        key_steps_text = ""
                        key_steps_list = []
                        
                        if video_understanding_output.key_steps:
                            for i, step in enumerate(video_understanding_output.key_steps):
                                step_text = step.get('description', 'Step')
                                key_steps_text += f"\n{i+1}. {step_text}"
                                
                                if 'timestamp' in step:
                                    key_steps_text += f" (at {step['timestamp']})"
                                    step_text += f" (at {step['timestamp']})"
                                
                                if 'frame' in step:
                                    key_steps_text += f" - Frame: {step['frame']}"
                                
                                key_steps_list.append(step_text)
                        else:
                            key_steps_text = "\n(No key steps identified)"
                        
                        # Transfer to Video Editing Agent
                        if video_understanding_output.frames_dir and os.path.exists(video_understanding_output.frames_dir):
                            print(f"Found frames directory at {video_understanding_output.frames_dir}. Transferring to Video Editing Agent...")
                            
                            # Format key steps for the Video Editing Agent
                            formatted_key_steps = ", ".join([f'"{step}"' for step in key_steps_list])
                            
                            # Transfer to Video Editing Agent
                            video_editing_request = f"Please create a short video from the frames in {video_understanding_output.frames_dir} with the following key steps: [{formatted_key_steps}]. The summary of the video is: {video_understanding_output.summary}"
                            
                            video_editing_result = await Runner.run(
                                video_editing_agent, 
                                video_editing_request, 
                                run_config=run_config, 
                                hooks=hooks, 
                                max_turns=10
                            )
                            
                            video_editing_output = video_editing_result.final_output
                            
                            if isinstance(video_editing_output, videoeditingoutput):
                                final_output = f"Video Creation Summary:\n\n" \
                                              f"Created a short video highlighting the key steps.\n" \
                                              f"Output video: {video_editing_output.output_video_path}\n" \
                                              f"Duration: {video_editing_output.duration} seconds\n" \
                                              f"Frame count: {video_editing_output.frame_count}\n\n" \
                                              f"Video Analysis Summary:\n\n{video_understanding_output.summary}\n\n" \
                                              f"Key Steps:{key_steps_text}\n\n" \
                                              f"Frames extracted to: {video_understanding_output.frames_dir}"
                                return final_output
                        
                        # If we couldn't process with the Video Editing Agent, return the Video Understanding Agent results
                        final_output = f"Video Analysis Summary:\n\n{video_understanding_output.summary}\n\nKey Steps:{key_steps_text}\n\nFrames extracted to: {video_understanding_output.frames_dir}"
                        return final_output
                
                # If we couldn't process with the Video Understanding Agent or it was skipped, return the audio processing results
                transcript = audio_result["transcript"]
                key_points = audio_result["key_points"]
                
                key_points_text = "\n".join([f"- {point}" for point in key_points])
                
                final_output = f"{manager_output}\n\n--- TRANSCRIPT ---\n{transcript}\n\n--- KEY POINTS ---\n{key_points_text}"
                
                return final_output
        
        # If we couldn't extract audio path or process it, just return the original output
        return str(manager_output)

async def main():
    parser = argparse.ArgumentParser(description="Video Agent - Extract key steps from cooking videos")
    parser.add_argument("--query", type=str, help="The query to search for a video")
    parser.add_argument("--video", type=str, help="The name of an existing video file")
    parser.add_argument("--max-duration", type=int, default=300, help="Maximum duration of the output video in seconds")
    parser.add_argument("--no-pretty", action="store_true", 
                        help="Disable pretty printing and use simple console output")
    args = parser.parse_args()
    
    user_request = "I want to see the key steps of how play squash in a short video, " \
                      "find a video for me (max duration 5 minutes) and download it and then teach me how to do it, give me the key steps short video back."
    
    printer, cleanup = setup_printer()
    hooks = create_agent_hooks(printer)
    
    # Create a run config with the hooks
    run_config = RunConfig(
        workflow_name="Video Processing Workflow"
    )
    
    try:
        # Process the request with the run config
        printer.update_item("request", f"Processing request: {user_request}", category="system")
        response = await process_request(user_request, run_config, hooks=hooks)
        printer.update_item("response", f"Response: {response}", is_done=True, category="system")
    finally:
        # Clean up the printer
        cleanup()


if __name__ == "__main__":
    # Set OpenAI API key from environment variable
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        exit(1)
    
    set_default_openai_key(openai_api_key)
    asyncio.run(main()) 