# Video Agent

A multi-agent system that extracts key steps from cooking videos and creates short summary videos with text overlays.

## Features

- Extracts key steps from cooking videos
- Transcribes speech to text with timestamps
- Identifies important segments in the video
- Creates concise text summaries for each step
- Combines key segments into a short video with text overlays

## Architecture

The system uses a multi-agent approach with the following specialized agents:

1. **Manager Agent**: Coordinates the entire workflow
2. **Searcher Agent**: Finds and downloads videos (if needed)
3. **Transcriber Agent**: Converts speech to text with timestamps
4. **Segmenter Agent**: Identifies key steps in the video
5. **Summarizer Agent**: Creates concise text summaries
6. **Editor Agent**: Cuts and combines video segments with text overlays

## Installation

1. Clone the repository
2. Install the dependencies:

```bash
pip install -r requirements.txt
```

3. Set your OpenAI API key:

```bash
export OPENAI_API_KEY=your_api_key_here
```

## Usage

Run the main script with a query or video file:

```bash
# Search for a video and process it
python main.py --query "salt and pepper chicken"

# Process an existing video
python main.py --video "grill_steak.mp4"

# Specify maximum duration of the output video
python main.py --query "salt and pepper chicken" --max-duration 20
```

## Example

```bash
python main.py --video "grill_steak.mp4" --max-duration 30
```

This will:
1. Process the video "grill_steak.mp4"
2. Extract the key steps (approximately 5-7 steps)
3. Create a short video (max 30 seconds) with text overlays
4. Return the path to the generated video and a summary of the steps

## Requirements

- Python 3.8+
- OpenAI API key
- FFmpeg (for video processing) 