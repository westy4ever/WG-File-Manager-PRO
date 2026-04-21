class WGFileManagerError(Exception):
    """Base exception for WGFileManager"""
    pass

class FileOperationError(WGFileManagerError):
    """File operation failed"""
    pass

class NetworkError(WGFileManagerError):
    """Network operation failed"""
    pass

class PermissionError(WGFileManagerError):
    """Permission denied"""
    pass

class DiskSpaceError(WGFileManagerError):
    """Insufficient disk space"""
    pass

class CacheError(WGFileManagerError):
    """Cache operation failed"""
    pass

class RemoteConnectionError(WGFileManagerError):
    """Remote connection failed"""
    pass

class InvalidInputError(WGFileManagerError):
    """Invalid user input"""
    pass

class ArchiveError(WGFileManagerError):
    """Archive operation failed"""
    pass

class MediaPlaybackError(WGFileManagerError):
    """Media playback failed"""
    pass