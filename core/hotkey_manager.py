"""
Hotkey Manager for WGFileManager
Handles hotkey configuration, mapping, and execution
Location: core/hotkey_manager.py
"""
import os
import json
import time
from collections import defaultdict
from threading import Timer

try:
    from ..utils.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class HotkeyManager:
    """Central hotkey management system"""
    
    def __init__(self, session):
        self.session = session
        self.config = None
        self.current_profile = "default"
        self.hotkey_map = {}
        self.long_press_timers = {}
        self.long_press_delay = 0.5  # 500ms for long press
        
        # Load configuration
        self._load_config()
        
        # Initialize hotkey map
        self._build_hotkey_map()
    
    def _load_config(self):
        """Load hotkey configuration from files"""
        try:
            # Default configuration path
            default_config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "default_hotkeys.json"
            )
            
            # User configuration path
            user_config_path = "/etc/enigma2/wgfilemanager_hotkeys.json"
            
            # Try to load user config first
            if os.path.exists(user_config_path):
                with open(user_config_path, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded user hotkey config from {user_config_path}")
            elif os.path.exists(default_config_path):
                # Fallback to default config
                with open(default_config_path, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded default hotkey config from {default_config_path}")
            else:
                # Create minimal config
                self.config = self._create_minimal_config()
                logger.warning("Created minimal hotkey config")
                
        except Exception as e:
            logger.error(f"Error loading hotkey config: {e}")
            self.config = self._create_minimal_config()
    
    def _create_minimal_config(self):
        """Create minimal configuration if files don't exist"""
        return {
            "version": "1.0",
            "hotkey_profiles": {
                "default": {
                    "name": "Default",
                    "hotkeys": {
                        "subtitle_toggle": {
                            "key": "subtitle",
                            "action": "toggle_subtitle",
                            "label": "Toggle Subtitles"
                        }
                    }
                }
            }
        }
    
    def _build_hotkey_map(self):
        """Build hotkey to action mapping"""
        self.hotkey_map = defaultdict(list)
        
        try:
            profile = self.config.get("hotkey_profiles", {}).get(self.current_profile, {})
            hotkeys = profile.get("hotkeys", {})
            
            for action_id, action_config in hotkeys.items():
                key = action_config.get("key")
                if key:
                    self.hotkey_map[key].append({
                        "action_id": action_id,
                        "action": action_config.get("action"),
                        "label": action_config.get("label", action_id),
                        "description": action_config.get("description", "")
                    })
            
            logger.info(f"Built hotkey map with {len(hotkeys)} actions")
            
        except Exception as e:
            logger.error(f"Error building hotkey map: {e}")
    
    def set_profile(self, profile_name):
        """Switch to a different hotkey profile"""
        try:
            if profile_name in self.config.get("hotkey_profiles", {}):
                self.current_profile = profile_name
                self._build_hotkey_map()
                logger.info(f"Switched to hotkey profile: {profile_name}")
                return True
            else:
                logger.error(f"Hotkey profile not found: {profile_name}")
                return False
        except Exception as e:
            logger.error(f"Error setting profile: {e}")
            return False
    
    def get_available_profiles(self):
        """Get list of available hotkey profiles"""
        try:
            profiles = self.config.get("hotkey_profiles", {})
            return [
                {
                    "id": profile_id,
                    "name": data.get("name", profile_id),
                    "description": data.get("description", ""),
                    "hotkey_count": len(data.get("hotkeys", {}))
                }
                for profile_id, data in profiles.items()
            ]
        except Exception as e:
            logger.error(f"Error getting profiles: {e}")
            return []
    
    def get_profile_info(self, profile_id=None):
        """Get information about a specific profile"""
        if profile_id is None:
            profile_id = self.current_profile
        
        try:
            profile = self.config.get("hotkey_profiles", {}).get(profile_id, {})
            return {
                "id": profile_id,
                "name": profile.get("name", profile_id),
                "description": profile.get("description", ""),
                "hotkeys": profile.get("hotkeys", {}),
                "hotkey_count": len(profile.get("hotkeys", {}))
            }
        except Exception as e:
            logger.error(f"Error getting profile info: {e}")
            return {}
    
    def get_hotkey_for_action(self, action):
        """Get hotkey assigned to a specific action"""
        try:
            profile = self.config.get("hotkey_profiles", {}).get(self.current_profile, {})
            hotkeys = profile.get("hotkeys", {})
            
            for action_id, config in hotkeys.items():
                if config.get("action") == action:
                    return {
                        "key": config.get("key"),
                        "label": config.get("label", action_id),
                        "description": config.get("description", "")
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting hotkey for action: {e}")
            return None
    
    def handle_key_press(self, key, player_instance=None):
        """Handle a key press event"""
        try:
            # Start long press timer
            self._start_long_press_timer(key, player_instance)
            
            # Immediate action for short press
            actions = self.hotkey_map.get(key, [])
            if actions:
                # For now, take first action
                action_config = actions[0]
                return self._execute_action(action_config, player_instance)
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling key press: {e}")
            return False
    
    def handle_key_release(self, key, player_instance=None):
        """Handle key release event"""
        try:
            # Cancel long press timer
            self._cancel_long_press_timer(key)
            
            # Check if this was a long press (timer would have fired)
            # For now, we handle long press in timer callback
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling key release: {e}")
            return False
    
    def _start_long_press_timer(self, key, player_instance):
        """Start timer for long press detection"""
        try:
            # Cancel existing timer for this key
            self._cancel_long_press_timer(key)
            
            # Check if there are long press actions for this key
            long_key = f"long_{key}"
            long_actions = self.hotkey_map.get(long_key, [])
            
            if long_actions:
                # Start timer for long press
                timer = Timer(self.long_press_delay, self._handle_long_press, [long_key, player_instance])
                timer.daemon = True
                self.long_press_timers[key] = timer
                timer.start()
                logger.debug(f"Started long press timer for {key}")
                
        except Exception as e:
            logger.error(f"Error starting long press timer: {e}")
    
    def _cancel_long_press_timer(self, key):
        """Cancel long press timer"""
        try:
            timer = self.long_press_timers.pop(key, None)
            if timer:
                timer.cancel()
                logger.debug(f"Cancelled long press timer for {key}")
        except Exception as e:
            logger.error(f"Error cancelling long press timer: {e}")
    
    def _handle_long_press(self, long_key, player_instance):
        """Handle long press action"""
        try:
            actions = self.hotkey_map.get(long_key, [])
            if actions:
                action_config = actions[0]
                logger.info(f"Long press detected: {long_key} -> {action_config['action']}")
                self._execute_action(action_config, player_instance)
        except Exception as e:
            logger.error(f"Error handling long press: {e}")
    
    def _execute_action(self, action_config, player_instance):
        """Execute a hotkey action"""
        try:
            action = action_config.get("action")
            action_id = action_config.get("action_id")
            
            logger.info(f"Executing hotkey action: {action_id} -> {action}")
            
            if not player_instance:
                logger.warning("No player instance for hotkey execution")
                return False
            
            # Map actions to player methods
            action_map = {
                "toggle_subtitle": player_instance.toggle_subtitles,
                "open_subtitle_menu": player_instance.show_subtitle_menu,
                "open_subtitle_settings": player_instance.open_subtitle_settings,
                "open_subtitle_quick_menu": player_instance.show_quick_subtitle_menu,
                "open_audio_menu": player_instance.hotkey_audio_selection,
                "open_delay_settings": lambda: player_instance.player_ref.subtitle_manager.open_delay_settings() if hasattr(player_instance, 'player_ref') else None,
                "open_style_settings": lambda: player_instance.player_ref.subtitle_manager.open_style_settings() if hasattr(player_instance, 'player_ref') else None,
                "open_embedded_tools": lambda: player_instance.player_ref.subtitle_manager.open_embedded_subtitle_tools() if hasattr(player_instance, 'player_ref') else None,
                "open_chapter_menu": player_instance.show_chapter_menu,
                "open_jump_menu": player_instance.show_chapter_menu,  # Alias
                "download_subtitles": player_instance.open_subtitle_download,
                "mark_position": player_instance.mark_position,
                "jump_back_30": lambda: player_instance._jump_by_seconds(-30),
                "jump_forward_30": lambda: player_instance._jump_by_seconds(30),
                "jump_back_10": lambda: player_instance._jump_by_seconds(-10),
                "jump_forward_10": lambda: player_instance._jump_by_seconds(10),
            }
            
            if action in action_map:
                action_map[action]()
                return True
            else:
                logger.error(f"Unknown action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing action {action_config}: {e}")
            return False
    
    def save_config(self, config_path=None):
        """Save current configuration to file"""
        try:
            if config_path is None:
                config_path = "/etc/enigma2/wgfilemanager_hotkeys.json"
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            logger.info(f"Saved hotkey config to {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        try:
            default_config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "default_hotkeys.json"
            )
            
            if os.path.exists(default_config_path):
                with open(default_config_path, 'r') as f:
                    self.config = json.load(f)
                self._build_hotkey_map()
                logger.info("Reset hotkey config to defaults")
                return True
            else:
                logger.error("Default config file not found")
                return False
                
        except Exception as e:
            logger.error(f"Error resetting to defaults: {e}")
            return False


class SubtitleHotkeyManager(HotkeyManager):
    """Specialized hotkey manager for subtitle actions"""
    
    def __init__(self, session, player_ref):
        super().__init__(session)
        self.player_ref = player_ref
    
    def handle_hotkey(self, key):
        """Handle subtitle-specific hotkey"""
        try:
            # Map common keys to actions
            key_map = {
                "subtitles": "toggle_subtitle",
                "text": "open_subtitle_menu",
                "audio": "open_audio_menu",
                "long_audio": "jump_back_30",
                "long_text": "open_subtitle_quick_menu",
            }
            
            action = key_map.get(key)
            if action:
                return self._execute_subtitle_action(action)
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling subtitle hotkey: {e}")
            return False
    
    def _execute_subtitle_action(self, action):
        """Execute subtitle-specific action"""
        try:
            if action == "toggle_subtitle":
                if hasattr(self.player_ref, 'subtitle_manager'):
                    result = self.player_ref.subtitle_manager.toggle_subtitles()
                    return f"Subtitles: {result}"
                return "Subtitle manager not available"
                
            elif action == "open_subtitle_menu":
                if hasattr(self.player_ref, 'subtitle_manager'):
                    self.player_ref.subtitle_manager._fallback_menu()
                    return "Subtitle menu opened"
                return "Subtitle manager not available"
                
            elif action == "open_audio_menu":
                # This would open audio selection
                return "Audio selection"
                
            elif action == "jump_back_30":
                # This would trigger a jump
                return "Jump back 30s"
                
            elif action == "open_subtitle_quick_menu":
                # This would open quick menu
                return "Quick menu"
                
            return f"Unknown action: {action}"
            
        except Exception as e:
            logger.error(f"Error executing subtitle action: {e}")
            return f"Error: {e}"