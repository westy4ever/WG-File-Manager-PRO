import os
import shutil
import time
import random
import stat
from datetime import datetime
from ..constants import TRASH_PATH
from ..exceptions import FileOperationError, DiskSpaceError
from ..utils.formatters import format_size
from ..utils.validators import validate_path

class FileOperations:
    def __init__(self, config, cache=None):
        self.config = config
        self.cache = cache
        self.init_trash()
    
    def init_trash(self):
        """Initialize trash directory"""
        try:
            os.makedirs(TRASH_PATH, exist_ok=True)
            return True
        except Exception as e:
            raise FileOperationError(f"Failed to initialize trash: {e}")
    
    def copy(self, source, destination, overwrite=False):
        """Copy file or directory"""
        try:
            validate_path(source)
            validate_path(destination)
            
            if not os.path.exists(source):
                raise FileOperationError(f"Source does not exist: {source}")
            
            if os.path.isdir(source):
                return self._copy_directory(source, destination, overwrite)
            else:
                return self._copy_file(source, destination, overwrite)
                
        except Exception as e:
            raise FileOperationError(f"Copy failed: {e}")
    
    def _copy_file(self, source, destination, overwrite=False):
        """Copy single file"""
        dest_path = self._get_unique_path(source, destination)
        
        if not overwrite and os.path.exists(dest_path):
            raise FileOperationError(f"File already exists: {dest_path}")
        
        # Check disk space
        self._check_disk_space(source, os.path.dirname(dest_path))
        
        shutil.copy2(source, dest_path)
        
        # Clear cache entry if exists
        if self.cache:
            self.cache.delete(f"file_size_{hash(source)}")
        
        return dest_path
    
    def _copy_directory(self, source, destination, overwrite=False):
        """Copy directory recursively"""
        dest_path = self._get_unique_path(source, destination)
        
        if os.path.exists(dest_path):
            if overwrite:
                shutil.rmtree(dest_path)
            else:
                raise FileOperationError(f"Directory already exists: {dest_path}")
        
        # Check disk space
        self._check_disk_space(source, os.path.dirname(dest_path))
        
        shutil.copytree(source, dest_path, symlinks=True)
        return dest_path
    
    def move(self, source, destination, use_trash=False):
        """Move file or directory"""
        try:
            validate_path(source)
            validate_path(destination)
            
            if not os.path.exists(source):
                raise FileOperationError(f"Source does not exist: {source}")
            
            if use_trash and self.config.plugins.wgfilemanager.trash_enabled.value == "yes":
                return self._move_to_trash(source)
            
            dest_path = self._get_unique_path(source, destination)
            
            # Check disk space if moving to different device
            try:
                src_device = os.stat(source).st_dev
                dest_device = os.stat(os.path.dirname(dest_path)).st_dev
                if src_device != dest_device:
                    self._check_disk_space(source, os.path.dirname(dest_path))
            except:
                pass  # If we can't check devices, proceed anyway
            
            shutil.move(source, dest_path)
            
            # Clear cache
            if self.cache:
                self.cache.delete(f"file_size_{hash(source)}")
            
            return dest_path
            
        except Exception as e:
            raise FileOperationError(f"Move failed: {e}")
    
    def _move_to_trash(self, source):
        """Move file to trash"""
        try:
            timestamp = int(time.time())
            random_suffix = random.randint(1000, 9999)
            name = os.path.basename(source)
            trash_name = f"{name}_{timestamp}_{random_suffix}"
            trash_path = os.path.join(TRASH_PATH, trash_name)
            
            shutil.move(source, trash_path)
            return trash_path
        except Exception as e:
            raise FileOperationError(f"Failed to move to trash: {e}")
    
    def delete(self, path, permanent=False):
        """Delete file or directory"""
        try:
            validate_path(path)
            
            if not os.path.exists(path):
                raise FileOperationError(f"Path does not exist: {path}")
            
            if permanent or self.config.plugins.wgfilemanager.trash_enabled.value != "yes":
                return self._permanent_delete(path)
            else:
                return self._move_to_trash(path)
                
        except Exception as e:
            raise FileOperationError(f"Delete failed: {e}")
    
    def _permanent_delete(self, path):
        """Permanently delete file or directory"""
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            
            # Clear cache
            if self.cache:
                self.cache.delete(f"file_size_{hash(path)}")
            
            return True
        except Exception as e:
            raise FileOperationError(f"Permanent delete failed: {e}")
    
    def rename(self, old_path, new_name):
        """Rename file or directory"""
        try:
            validate_path(old_path)
            
            if not os.path.exists(old_path):
                raise FileOperationError(f"Path does not exist: {old_path}")
            
            parent_dir = os.path.dirname(old_path)
            new_path = os.path.join(parent_dir, new_name)
            
            if os.path.exists(new_path):
                raise FileOperationError(f"Destination already exists: {new_path}")
            
            os.rename(old_path, new_path)
            
            # Update cache
            if self.cache:
                old_key = f"file_size_{hash(old_path)}"
                if self.cache and old_key in self.cache:
                    size = self.cache.get(old_key)
                    self.cache.delete(old_key)
                    self.cache.set(f"file_size_{hash(new_path)}", size)
            
            return new_path
            
        except Exception as e:
            raise FileOperationError(f"Rename failed: {e}")
    
    def create_directory(self, path, name):
        """Create new directory"""
        try:
            validate_path(path)
            
            new_path = os.path.join(path, name)
            
            if os.path.exists(new_path):
                raise FileOperationError(f"Directory already exists: {new_path}")
            
            os.makedirs(new_path, exist_ok=True)
            return new_path
            
        except Exception as e:
            raise FileOperationError(f"Create directory failed: {e}")
    
    def create_file(self, path, name, content=""):
        """Create new file"""
        try:
            validate_path(path)
            
            new_path = os.path.join(path, name)
            
            if os.path.exists(new_path):
                raise FileOperationError(f"File already exists: {new_path}")
            
            with open(new_path, 'w') as f:
                f.write(content)
            
            return new_path
            
        except Exception as e:
            raise FileOperationError(f"Create file failed: {e}")
    
    def get_file_size(self, path, use_cache=True):
        """Get file or directory size - OPTIMIZED for UI"""
        try:
            if not os.path.exists(path):
                return 0
            
            # For directories, return 0 immediately (too slow to calculate for UI)
            if os.path.isdir(path):
                return 0
            
            # For files, just get the size directly
            return os.path.getsize(path)
            
        except Exception:
            return 0
    
    def _get_directory_size(self, path):
        """Calculate directory size recursively"""
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self._get_directory_size(entry.path)
        except Exception:
            pass
        return total
    
    def get_file_info(self, path):
        """Get detailed file information"""
        try:
            if not os.path.exists(path):
                return None
            
            stat_info = os.stat(path)
            
            info = {
                'path': path,
                'name': os.path.basename(path),
                'is_dir': os.path.isdir(path),
                'size': self.get_file_size(path),
                'size_formatted': format_size(self.get_file_size(path)),
                'modified': datetime.fromtimestamp(stat_info.st_mtime),
                'accessed': datetime.fromtimestamp(stat_info.st_atime),
                'created': datetime.fromtimestamp(stat_info.st_ctime),
                'permissions': oct(stat_info.st_mode)[-3:],
                'owner': stat_info.st_uid,
                'group': stat_info.st_gid,
            }
            
            if info['is_dir']:
                try:
                    info['item_count'] = len(os.listdir(path))
                except:
                    info['item_count'] = 0
            
            return info
            
        except Exception as e:
            raise FileOperationError(f"Get file info failed: {e}")
    
    def change_permissions(self, path, mode):
        """Change file permissions"""
        try:
            validate_path(path)
            
            if not os.path.exists(path):
                raise FileOperationError(f"Path does not exist: {path}")
            
            # Convert string mode to octal if needed
            if isinstance(mode, str):
                mode = int(mode, 8)
            
            os.chmod(path, mode)
            return True
            
        except Exception as e:
            raise FileOperationError(f"Change permissions failed: {e}")
    
    def _check_disk_space(self, source, destination):
        """Check if enough disk space is available"""
        try:
            if not os.path.exists(destination):
                return True
            
            st = os.statvfs(destination)
            free = st.f_bavail * st.f_frsize
            
            # For directories, estimate size more efficiently
            if os.path.isdir(source):
                # Don't calculate exact directory size (too slow)
                # Just check if there's at least 1GB free
                if free < (1024**3):  # 1GB
                    raise DiskSpaceError(
                        f"Insufficient space for large directory! Free: {free / (1024**3):.2f} GB"
                    )
                return True
            else:
                needed = os.path.getsize(source)
            
            if needed > free:
                needed_gb = needed / (1024**3)
                free_gb = free / (1024**3)
                raise DiskSpaceError(
                    f"Insufficient space! Needed: {needed_gb:.2f} GB, Free: {free_gb:.2f} GB"
                )
            return True
            
        except Exception as e:
            if isinstance(e, DiskSpaceError):
                raise
            # Don't fail if we can't check disk space
            return True
    
    def _get_unique_path(self, source, destination):
        """Generate unique path if destination exists"""
        base = os.path.basename(source)
        
        # If destination is a directory, create path inside it
        if os.path.isdir(destination):
            dest_dir = destination
            dest_path = os.path.join(destination, base)
        else:
            # Destination is a file path
            dest_dir = os.path.dirname(destination)
            dest_path = destination
        
        if not os.path.exists(dest_path):
            return dest_path
        
        # Generate unique name
        name, ext = os.path.splitext(base)
        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, f"{name}_{counter}{ext}")
            counter += 1
        
        return dest_path
    
    def empty_trash(self):
        """Empty trash directory"""
        try:
            if os.path.exists(TRASH_PATH):
                shutil.rmtree(TRASH_PATH)
                os.makedirs(TRASH_PATH, exist_ok=True)
                return True
            return False
        except Exception as e:
            raise FileOperationError(f"Empty trash failed: {e}")
    
    def restore_from_trash(self, trash_item, destination=None):
        """Restore item from trash"""
        try:
            if not os.path.exists(trash_item):
                raise FileOperationError(f"Trash item not found: {trash_item}")
            
            if not destination:
                destination = "/media/hdd"
            
            # Extract original name from trash filename
            name = os.path.basename(trash_item)
            if "_" in name:
                original_name = name.split("_")[0]
            else:
                original_name = name
            
            dest_path = os.path.join(destination, original_name)
            
            # Make unique if exists
            counter = 1
            while os.path.exists(dest_path):
                base, ext = os.path.splitext(original_name)
                dest_path = os.path.join(destination, f"{base}_{counter}{ext}")
                counter += 1
            
            shutil.move(trash_item, dest_path)
            return dest_path
            
        except Exception as e:
            raise FileOperationError(f"Restore from trash failed: {e}")
    
    # New method for compatibility with updated main_screen.py
    def can_play_file(self, path):
        """Check if file can be played - for compatibility with main_screen.py"""
        try:
            if not os.path.exists(path):
                return False
            
            # Check file size
            try:
                size = os.path.getsize(path)
                if size == 0:
                    return False
            except:
                return False
            
            # Check extension
            ext = os.path.splitext(path)[1].lower()
            supported = ['.mp4', '.mkv', '.avi', '.ts', '.m2ts', '.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a']
            return ext in supported
        except:
            return False