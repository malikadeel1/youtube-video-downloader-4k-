# Import necessary libraries
from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
import yt_dlp  # The library that does the actual video downloading
import os      # For operating system operations like creating folders
import uuid    # For generating unique IDs for each download session
import json    # For handling JSON data
import time    # For adding delays (sleeping)
import threading # For running downloads in the background so the site doesn't freeze

# Initialize the Flask application
app = Flask(__name__)

# Configure where downloads will be saved
DOWNLOAD_FOLDER = 'downloads'
# Check if the folder exists, if not, create it
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Global dictionary to store progress of active downloads
# Key: session_id, Value: dict with status, percentage, speed, etc.
progress_data = {}

# Route for the home page
@app.route('/')
def index():
    # Renders the HTML file located in templates/index.html
    return render_template('index.html')

# Function that creates a "hook" to track download progress
# This is called by yt-dlp periodically during the download
def progress_hook(session_id):
    """Create a progress hook function for yt-dlp"""
    def hook(d):
        # 'd' is a dictionary provided by yt-dlp with download status
        if d['status'] == 'downloading':
            # Calculate percentage completed
            # total_bytes might be None if unknown, so we check estimates too
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            
            if total > 0:
                percentage = (downloaded / total) * 100
            else:
                percentage = 0
            
            # Get current download speed and estimated time remaining (ETA)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            
            # Update the global progress_data dictionary for this session
            progress_data[session_id] = {
                'status': 'downloading',
                'percentage': round(percentage, 1), # Round to 1 decimal place
                'downloaded': downloaded,
                'total': total,
                'speed': speed,
                'eta': eta
            }
        elif d['status'] == 'finished':
            # When download is complete, mark it as finished
            progress_data[session_id] = {
                'status': 'finished',
                'percentage': 100,
                'downloaded': d.get('downloaded_bytes', 0),
                'total': d.get('downloaded_bytes', 0),
                'speed': 0,
                'eta': 0
            }
    return hook

# Route to stream progress updates to the frontend
# This uses Server-Sent Events (SSE) to push data to the browser
@app.route('/progress/<session_id>')
def stream_progress(session_id):
    """Stream progress updates via Server-Sent Events"""
    def generate():
        while True:
            # Check if we have data for this session
            if session_id in progress_data:
                data = progress_data[session_id]
                # Yield data in SSE format: "data: <json_string>\n\n"
                yield f"data: {json.dumps(data)}\n\n"
                
                # If finished, wait a bit then stop streaming
                if data.get('status') == 'finished':
                    time.sleep(0.5)
                    # Clean up memory by removing old progress data
                    if session_id in progress_data:
                        del progress_data[session_id]
                    break
            # Wait 0.5 seconds before sending the next update
            time.sleep(0.5)
    
    # Return a streaming response
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

# Route to get available video formats (resolutions)
@app.route('/formats', methods=['POST'])
def get_formats():
    try:
        # Get data sent from frontend
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Options for yt-dlp just to get info, not download
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract video information
            info = ydl.extract_info(url, download=False)
            
            # Extract unique video resolutions
            formats = info.get('formats', [])
            quality_map = {}
            
            for fmt in formats:
                try:
                    # Filter for formats that have video codec (not audio only) and height info
                    if fmt.get('vcodec') != 'none' and fmt.get('height'):
                        height = fmt.get('height')
                        quality = f"{height}p"
                        filesize = fmt.get('filesize') or fmt.get('filesize_approx') or 0
                        
                        # Handle case where filesize is None
                        if filesize is None:
                            filesize = 0
                        
                        # We want the best file size (highest quality) for each resolution
                        current_size = quality_map.get(quality, {}).get('filesize', 0) or 0
                        if quality not in quality_map or filesize > current_size:
                            quality_map[quality] = {
                                'quality': quality,
                                'format_id': fmt.get('format_id'),
                                'ext': fmt.get('ext', 'mp4'),
                                'filesize': filesize,
                                'height': height
                            }
                except Exception:
                    continue
            
            # Sort formats by height (resolution) from high to low
            available_formats = sorted(quality_map.values(), key=lambda x: x['height'], reverse=True)
            
        return jsonify({
            'success': True,
            'formats': available_formats
        })
        
    except Exception as e:
        import traceback
        print(f"Error in /formats: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Route to handle the actual download request
@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json()
        url = data.get('url')
        quality = data.get('quality', 'best')  # Default to 'best' if not specified
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Generate a unique ID for this download session
        session_id = str(uuid.uuid4())
        
        # Initialize the progress data for this session
        progress_data[session_id] = {
            'status': 'starting',
            'percentage': 0,
            'downloaded': 0,
            'total': 0,
            'speed': 0,
            'eta': 0
        }
        
        # Inner function to perform the download in a background thread
        def perform_download():
            try:
                # Determine which format to download based on user choice
                if quality == 'best':
                    format_string = 'best'
                elif quality == 'audio':
                    format_string = 'bestaudio/best'
                else:
                    # For specific resolutions like '720p'
                    resolution = quality.replace('p', '')
                    # Try to get exact resolution, fallback to best available
                    format_string = f'best[height<={resolution}]/bestvideo[height<={resolution}]+bestaudio/best'
                
                # Configure download options
                ydl_opts = {
                    'format': format_string,
                    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'), # Save path template
                    'merge_output_format': 'mp4',
                    'restrictfilenames': True,  # Remove special chars from filename
                    'progress_hooks': [progress_hook(session_id)],  # Attach our progress tracker
                    'ignoreerrors': False,
                }
                
                # Start the download
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    
                    # Update progress to show completion
                    progress_data[session_id]['filename'] = os.path.basename(filename)
                    progress_data[session_id]['message'] = f'Download completed in {quality} quality!'
                    
            except Exception as e:
                # If error occurs, update status so frontend knows
                progress_data[session_id] = {
                    'status': 'error',
                    'error': str(e),
                    'percentage': 0
                }
        
        # Create and start the background thread
        # This allows the server to respond immediately while download happens in background
        download_thread = threading.Thread(target=perform_download)
        download_thread.daemon = True # Thread will close when main program closes
        download_thread.start()
        
        # Return success immediately with the session ID
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Download started',
            'filename': 'Processing...'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to get basic video info (title, thumbnail, etc.)
@app.route('/info', methods=['POST'])
def get_info():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        ydl_opts = {'quiet': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info with download=False just gets metadata
            info = ydl.extract_info(url, download=False)
            
        return jsonify({
            'title': info.get('title'),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail'),
            'uploader': info.get('uploader'),
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Start the Flask server
if __name__ == '__main__':
    app.run(debug=True)
