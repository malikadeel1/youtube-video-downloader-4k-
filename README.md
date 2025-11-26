# YouTube Downloader - Flask App

A simple and elegant YouTube video downloader built with Flask and yt-dlp.

## Features

- 🎥 Download YouTube videos
- 📊 Get video information (title, duration, thumbnail, uploader)
- 🎨 Modern and responsive UI
- ⚡ Fast and efficient using yt-dlp

## Setup Instructions

### 1. Activate Virtual Environment

```powershell
.\venv\Scripts\Activate
```

### 2. Install Dependencies (Already Installed)

If you need to reinstall:
```powershell
pip install -r requirements.txt
```

### 3. Run the Application

```powershell
python app.py
```

The application will start on `http://127.0.0.1:5000/`

## Usage

1. Open your browser and navigate to `http://127.0.0.1:5000/`
2. Paste a YouTube URL in the input field
3. Click "Get Info" to preview video details
4. Click "Download Video" to download the video
5. Downloaded videos will be saved in the `downloads/` folder

## Project Structure

```
yt_downwload_app_in_flask/
├── venv/                  # Virtual environment
├── templates/
│   └── index.html        # Frontend interface
├── downloads/            # Downloaded videos (created automatically)
├── app.py                # Main Flask application
├── requirements.txt      # Python dependencies
├── .gitignore           # Git ignore file
└── README.md            # This file
```

## Technologies Used

- **Flask** - Web framework
- **yt-dlp** - YouTube video downloader
- **HTML/CSS/JavaScript** - Frontend

## Notes

- Make sure you have a stable internet connection
- Some videos may not be downloadable due to copyright restrictions
- The download folder is automatically created when you first download a video

## Deactivating Virtual Environment

When you're done working, deactivate the virtual environment:
```powershell
deactivate
```
