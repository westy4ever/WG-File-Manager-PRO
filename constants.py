# Paths
# Dynamic trash path - uses /media/hdd if available, else /tmp
import os as _os
if _os.path.isdir("/media/hdd"):
    TRASH_PATH = "/media/hdd/.wgfilemanager_trash"
else:
    TRASH_PATH = "/tmp/.wgfilemanager_trash"
del _os  # Clean up namespace
BOOKMARKS_FILE = "/etc/enigma2/wgfilemanager_bookmarks.json"
HISTORY_FILE = "/tmp/wgfilemanager_history.json"
CACHE_FILE = "/tmp/wgfilemanager_cache.json"
REMOTE_CONNECTIONS_FILE = "/etc/enigma2/wgfilemanager_remotes.json"
LOG_FILE = "/tmp/wgfilemanager.log"

# Limits
MAX_PREVIEW_SIZE = 1024 * 1024  # 1MB default
MAX_CACHE_SIZE = 1000
MAX_HISTORY_ITEMS = 50

# Icons
ICON_FOLDER = "📁"
ICON_VIDEO = "🎬"
ICON_AUDIO = "🎵"
ICON_IMAGE = "🖼️"
ICON_ARCHIVE = "📦"
ICON_TEXT = "📄"
ICON_BINARY = "🔢"

# File extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.ts', '.m2ts', '.mov', '.m4v']
AUDIO_EXTENSIONS = ['.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.ac3', '.dts']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
ARCHIVE_EXTENSIONS = ['.zip', '.tar', '.tar.gz', '.tgz', '.rar', '.7z', '.gz']
TEXT_EXTENSIONS = ['.txt', '.log', '.conf', '.cfg', '.ini', '.xml', '.json', '.py', '.sh', '.md']

# Network
DEFAULT_FTP_PORT = 21
DEFAULT_SFTP_PORT = 22
DEFAULT_WEBDAV_PORT = 80
DEFAULT_CIFS_VERSION = "3.0"
DEFAULT_TIMEOUT = 10

# UI
DEFAULT_ITEM_HEIGHT = 45
DEFAULT_FONT_SIZE = 20
PANEL_SPACING = 20