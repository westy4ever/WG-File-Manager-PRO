"""
Hotkey Setup Screen for WGFileManager
Location: ui/hotkey_setup.py
"""
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.ScrollLabel import ScrollLabel
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigYesNo
from enigma import getDesktop, eTimer
import os
import json
import shutil

try:
    from ..utils.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class HotkeySetupScreen(Screen):
    """Hotkey Configuration Screen"""
    
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        
        # Try to import hotkey manager
        try:
            from ..core.hotkey_manager import HotkeyManager
            self.hotkey_manager = HotkeyManager(session)
        except ImportError as e:
            logger.error(f"Cannot import HotkeyManager: {e}")
            self.hotkey_manager = None
        
        self.current_profile = "default"
        self.editing_key = None
        self.editing_action = None
        
        # Setup UI
        self._setup_ui()
        self._setup_actions()
        
        # Initialize
        self.onLayoutFinish.append(self.startup)
    
    def _setup_ui(self):
        """Setup user interface"""
        w, h = getDesktop(0).size().width(), getDesktop(0).size().height()
        
        self.skin = """
        <screen name="HotkeySetupScreen" position="0,0" size="%d,%d" backgroundColor="#1a1a1a" flags="wfNoBorder">
            <!-- Header -->
            <eLabel position="0,0" size="%d,80" backgroundColor="#0055aa" />
            <eLabel text="🎮 HOTKEY SETTINGS" position="20,10" size="800,60" font="Regular;40" halign="left" valign="center" transparent="1" foregroundColor="#ffffff" />
            
            <!-- Profile Selection -->
            <eLabel position="20,100" size="%d,60" backgroundColor="#333333" />
            <eLabel text="PROFILE:" position="30,110" size="200,40" font="Regular;24" halign="left" transparent="1" foregroundColor="#ffff00" />
            <widget name="profile_label" position="250,110" size="400,40" font="Regular;28" halign="left" transparent="1" foregroundColor="#00ff00" />
            
            <!-- Hotkey List -->
            <eLabel position="20,180" size="%d,500" backgroundColor="#222222" />
            <eLabel text="HOTKEY MAPPINGS" position="30,190" size="400,30" font="Regular;22" halign="left" transparent="1" foregroundColor="#ffff00" />
            <widget name="hotkey_list" position="30,230" size="%d,430" itemHeight="45" scrollbarMode="showOnDemand" backgroundColor="#222222" foregroundColor="#ffffff" selectionBackground="#0055aa" />
            
            <!-- Action Info -->
            <eLabel position="20,700" size="%d,150" backgroundColor="#2a2a2a" />
            <eLabel text="SELECTED ACTION" position="30,710" size="400,30" font="Regular;22" halign="left" transparent="1" foregroundColor="#ffff00" />
            <widget name="action_info" position="30,750" size="%d,80" font="Regular;20" transparent="1" foregroundColor="#aaaaaa" />
            
            <!-- Button Bar -->
            <eLabel position="0,%d" size="%d,80" backgroundColor="#000000" />
            
            <!-- Button Icons -->
            <ePixmap pixmap="buttons/red.png" position="30,%d" size="30,30" alphatest="on" />
            <ePixmap pixmap="buttons/green.png" position="250,%d" size="30,30" alphatest="on" />
            <ePixmap pixmap="buttons/yellow.png" position="470,%d" size="30,30" alphatest="on" />
            <ePixmap pixmap="buttons/blue.png" position="690,%d" size="30,30" alphatest="on" />
            
            <!-- Button Labels -->
            <eLabel text="Change Key" position="70,%d" size="160,30" font="Regular;20" transparent="1" foregroundColor="#ffffff" />
            <eLabel text="Save" position="290,%d" size="160,30" font="Regular;20" transparent="1" foregroundColor="#ffffff" />
            <eLabel text="Change Profile" position="510,%d" size="160,30" font="Regular;20" transparent="1" foregroundColor="#ffffff" />
            <eLabel text="More" position="730,%d" size="160,30" font="Regular;20" transparent="1" foregroundColor="#ffffff" />
            
            <!-- Help Text -->
            <widget name="help_text" position="50,%d" size="%d,20" font="Regular;16" halign="center" transparent="1" foregroundColor="#aaaaaa" />
        </screen>""" % (
            w, h,  # screen size
            w,  # header width
            w-40,  # profile area width
            w-40,  # hotkey area width
            w-60,  # hotkey list width
            w-40,  # info area width
            w-60,  # action info width
            h-80, w,  # button bar
            h-60,  # red button
            h-60,  # green button
            h-60,  # yellow button
            h-60,  # blue button
            h-55,  # red label
            h-55,  # green label
            h-55,  # yellow label
            h-55,  # blue label
            h-25, w-100  # help text
        )
        
        # Widgets
        self["profile_label"] = Label("Default")
        self["hotkey_list"] = MenuList([])
        self["action_info"] = Label("Select a hotkey to view details")
        self["help_text"] = Label("OK:Select  RED:Change Key  GREEN:Save  YELLOW:Profile  BLUE:More  EXIT:Back")
    
    def _setup_actions(self):
        """Setup action map"""
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "ok": self.select_hotkey,
            "cancel": self.exit_screen,
            "red": self.change_key,
            "green": self.save_config,
            "yellow": self.change_profile,
            "blue": self.show_more_options,
        }, -1)
    
    def startup(self):
        """Initialize screen"""
        if self.hotkey_manager:
            self.update_profile_display()
            self.update_hotkey_list()
        else:
            self["profile_label"].setText("ERROR")
            self["hotkey_list"].setList([("Hotkey manager not available", None)])
            self["action_info"].setText("Cannot load hotkey configuration")
    
    def update_profile_display(self):
        """Update profile information display"""
        if not self.hotkey_manager:
            return
        
        profile_info = self.hotkey_manager.get_profile_info()
        profile_text = f"{profile_info.get('name', 'Unknown')} ({profile_info.get('hotkey_count', 0)} hotkeys)"
        self["profile_label"].setText(profile_text)
    
    def update_hotkey_list(self):
        """Update hotkey list display"""
        if not self.hotkey_manager:
            return
        
        try:
            profile_info = self.hotkey_manager.get_profile_info()
            hotkeys = profile_info.get("hotkeys", {})
            
            hotkey_items = []
            for action_id, config in hotkeys.items():
                key = config.get("key", "None")
                label = config.get("label", action_id)
                action = config.get("action", "")
                
                # Format display
                display_key = key.upper().replace("_", " ")
                display_text = f"{display_key:15} → {label}"
                
                hotkey_items.append((display_text, {
                    "action_id": action_id,
                    "key": key,
                    "label": label,
                    "action": action,
                    "description": config.get("description", "")
                }))
            
            # Sort by key
            hotkey_items.sort(key=lambda x: x[1]["key"])
            
            self["hotkey_list"].setList(hotkey_items)
            
        except Exception as e:
            logger.error(f"Error updating hotkey list: {e}")
            self["hotkey_list"].setList([("Error loading hotkeys", None)])
    
    def select_hotkey(self):
        """Select a hotkey for editing"""
        current = self["hotkey_list"].getCurrent()
        if not current or not current[1]:
            return
        
        hotkey_info = current[1]
        self.editing_action = hotkey_info["action_id"]
        
        # Update info display
        info_text = f"Action: {hotkey_info['label']}\n"
        info_text += f"Key: {hotkey_info['key']}\n"
        info_text += f"ID: {hotkey_info['action']}\n"
        
        if hotkey_info.get("description"):
            info_text += f"\n{hotkey_info['description']}"
        
        self["action_info"].setText(info_text)
        
        # Offer to change key
        self.session.openWithCallback(
            self._confirm_change_key,
            MessageBox,
            f"Change key for '{hotkey_info['label']}'?\n\nCurrent key: {hotkey_info['key']}",
            MessageBox.TYPE_YESNO
        )
    
    def _confirm_change_key(self, confirmed):
        """Confirm key change"""
        if confirmed and self.editing_action:
            self.show_key_selection()
    
    def change_key(self):
        """Change key for selected hotkey"""
        current = self["hotkey_list"].getCurrent()
        if not current or not current[1]:
            self.session.open(
                MessageBox,
                "Please select a hotkey first",
                MessageBox.TYPE_WARNING,
                timeout=2
            )
            return
        
        self.select_hotkey()
    
    def show_key_selection(self):
        """Show key selection dialog"""
        if not self.editing_action:
            return
        
        # Available keys for mapping
        available_keys = [
            ("Subtitle", "subtitle"),
            ("Text", "text"),
            ("Audio", "audio"),
            ("Info", "info"),
            ("EPG", "epg"),
            ("Radio", "radio"),
            ("TV", "tv"),
            ("Video", "video"),
            ("Menu", "menu"),
            ("Help", "help"),
            ("Red", "red"),
            ("Green", "green"),
            ("Yellow", "yellow"),
            ("Blue", "blue"),
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
            ("6", "6"),
            ("7", "7"),
            ("8", "8"),
            ("9", "9"),
            ("0", "0"),
        ]
        
        self.session.openWithCallback(
            self._key_selected,
            ChoiceBox,
            title="Select New Key",
            list=available_keys
        )
    
    def _key_selected(self, choice):
        """Handle key selection"""
        if not choice or not self.editing_action:
            return
        
        new_key = choice[1]
        
        # Update configuration
        if self.hotkey_manager and self.hotkey_manager.config:
            profile = self.hotkey_manager.config.get("hotkey_profiles", {}).get(self.current_profile, {})
            hotkeys = profile.get("hotkeys", {})
            
            if self.editing_action in hotkeys:
                hotkeys[self.editing_action]["key"] = new_key
                
                # Rebuild hotkey map
                self.hotkey_manager._build_hotkey_map()
                
                # Update display
                self.update_hotkey_list()
                
                self.session.open(
                    MessageBox,
                    f"Key changed to: {new_key.upper()}",
                    MessageBox.TYPE_INFO,
                    timeout=2
                )
        
        self.editing_action = None
    
    def change_profile(self):
        """Change hotkey profile"""
        if not self.hotkey_manager:
            self.session.open(
                MessageBox,
                "Hotkey manager not available",
                MessageBox.TYPE_ERROR,
                timeout=2
            )
            return
        
        profiles = self.hotkey_manager.get_available_profiles()
        
        if not profiles:
            self.session.open(
                MessageBox,
                "No profiles available",
                MessageBox.TYPE_WARNING,
                timeout=2
            )
            return
        
        profile_items = []
        for profile in profiles:
            display = f"{profile['name']} ({profile['hotkey_count']} hotkeys)"
            profile_items.append((display, profile["id"]))
        
        self.session.openWithCallback(
            self._profile_selected,
            ChoiceBox,
            title="Select Profile",
            list=profile_items
        )
    
    def _profile_selected(self, choice):
        """Handle profile selection"""
        if not choice:
            return
        
        profile_id = choice[1]
        
        if self.hotkey_manager.set_profile(profile_id):
            self.current_profile = profile_id
            self.update_profile_display()
            self.update_hotkey_list()
            
            self.session.open(
                MessageBox,
                f"Switched to profile: {choice[0]}",
                MessageBox.TYPE_INFO,
                timeout=2
            )
    
    def save_config(self):
        """Save hotkey configuration"""
        if not self.hotkey_manager:
            self.session.open(
                MessageBox,
                "Cannot save: Hotkey manager not available",
                MessageBox.TYPE_ERROR,
                timeout=2
            )
            return
        
        if self.hotkey_manager.save_config():
            self.session.open(
                MessageBox,
                "✅ Hotkey configuration saved!",
                MessageBox.TYPE_INFO,
                timeout=2
            )
        else:
            self.session.open(
                MessageBox,
                "Failed to save configuration",
                MessageBox.TYPE_ERROR,
                timeout=2
            )
    
    def show_more_options(self):
        """Show additional options"""
        options = [
            ("📋 Export Configuration", "export"),
            ("📥 Import Configuration", "import"),
            ("🔄 Reset to Defaults", "reset"),
            ("📊 View All Actions", "view_all"),
            ("🎨 Create New Profile", "new_profile"),
            ("🗑️ Delete Current Profile", "delete_profile"),
            ("ℹ️ Help / Instructions", "help"),
        ]
        
        self.session.openWithCallback(
            self._more_option_selected,
            ChoiceBox,
            title="More Options",
            list=options
        )
    
    def _more_option_selected(self, choice):
        """Handle more option selection"""
        if not choice:
            return
        
        option = choice[1]
        
        if option == "export":
            self.export_config()
        elif option == "import":
            self.import_config()
        elif option == "reset":
            self.reset_to_defaults()
        elif option == "view_all":
            self.view_all_actions()
        elif option == "new_profile":
            self.create_new_profile()
        elif option == "delete_profile":
            self.delete_current_profile()
        elif option == "help":
            self.show_help()
    
    def export_config(self):
        """Export configuration to file"""
        try:
            from Screens.LocationBox import LocationBox
            
            def location_selected(path):
                if not path:
                    return
                
                if not path.endswith(".json"):
                    path = path + ".json"
                
                if self.hotkey_manager and self.hotkey_manager.config:
                    try:
                        with open(path, 'w') as f:
                            json.dump(self.hotkey_manager.config, f, indent=2)
                        
                        self.session.open(
                            MessageBox,
                            f"✅ Configuration exported to:\n{path}",
                            MessageBox.TYPE_INFO,
                            timeout=3
                        )
                    except Exception as e:
                        self.session.open(
                            MessageBox,
                            f"Export failed:\n{e}",
                            MessageBox.TYPE_ERROR
                        )
            
            self.session.openWithCallback(
                location_selected,
                LocationBox,
                text="Export configuration to...",
                currDir="/media/",
                filename="wgfilemanager_hotkeys.json",
                minFree=0
            )
            
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            self.session.open(
                MessageBox,
                f"Export error:\n{e}",
                MessageBox.TYPE_ERROR
            )
    
    def import_config(self):
        """Import configuration from file"""
        try:
            from Screens.LocationBox import LocationBox
            
            def location_selected(path):
                if not path or not os.path.exists(path):
                    return
                
                try:
                    with open(path, 'r') as f:
                        imported_config = json.load(f)
                    
                    # Validate config structure
                    if "hotkey_profiles" in imported_config:
                        self.hotkey_manager.config = imported_config
                        self.hotkey_manager._build_hotkey_map()
                        
                        self.update_profile_display()
                        self.update_hotkey_list()
                        
                        self.session.open(
                            MessageBox,
                            "✅ Configuration imported successfully!",
                            MessageBox.TYPE_INFO,
                            timeout=2
                        )
                    else:
                        self.session.open(
                            MessageBox,
                            "Invalid configuration file",
                            MessageBox.TYPE_ERROR
                        )
                        
                except Exception as e:
                    self.session.open(
                        MessageBox,
                        f"Import failed:\n{e}",
                        MessageBox.TYPE_ERROR
                    )
            
            self.session.openWithCallback(
                location_selected,
                LocationBox,
                text="Select configuration file...",
                currDir="/media/",
                filename="",
                minFree=0
            )
            
        except Exception as e:
            logger.error(f"Error importing config: {e}")
            self.session.open(
                MessageBox,
                f"Import error:\n{e}",
                MessageBox.TYPE_ERROR
            )
    
    def reset_to_defaults(self):
        """Reset to default configuration"""
        self.session.openWithCallback(
            self._confirm_reset,
            MessageBox,
            "Reset to default configuration?\n\nAll custom changes will be lost!",
            MessageBox.TYPE_YESNO
        )
    
    def _confirm_reset(self, confirmed):
        """Confirm reset to defaults"""
        if not confirmed:
            return
        
        if self.hotkey_manager and self.hotkey_manager.reset_to_defaults():
            self.update_profile_display()
            self.update_hotkey_list()
            
            self.session.open(
                MessageBox,
                "✅ Reset to defaults completed!",
                MessageBox.TYPE_INFO,
                timeout=2
            )
        else:
            self.session.open(
                MessageBox,
                "Failed to reset to defaults",
                MessageBox.TYPE_ERROR
            )
    
    def view_all_actions(self):
        """View all available actions"""
        try:
            if not self.hotkey_manager or not self.hotkey_manager.config:
                return
            
            action_descriptions = self.hotkey_manager.config.get("action_descriptions", {})
            
            if not action_descriptions:
                self.session.open(
                    MessageBox,
                    "No action descriptions available",
                    MessageBox.TYPE_INFO,
                    timeout=2
                )
                return
            
            # Create formatted list
            action_list = []
            for action, description in sorted(action_descriptions.items()):
                action_list.append(f"• {action}: {description}")
            
            action_text = "📋 AVAILABLE ACTIONS\n\n" + "\n".join(action_list)
            
            # Use ScrollLabel for long text
            from Screens.ScrollLabel import ScrollLabel
            
            class ActionListView(ScrollLabel):
                def __init__(self, session, text):
                    ScrollLabel.__init__(self, session, text)
                    self["actions"] = ActionMap(["OkCancelActions"], {
                        "ok": self.close,
                        "cancel": self.close
                    }, -1)
            
            self.session.open(ActionListView, action_text)
            
        except Exception as e:
            logger.error(f"Error viewing actions: {e}")
    
    def create_new_profile(self):
        """Create a new hotkey profile"""
        try:
            from Screens.VirtualKeyBoard import VirtualKeyBoard
            
            def name_entered(name):
                if not name:
                    return
                
                # Check if profile already exists
                profiles = self.hotkey_manager.get_available_profiles()
                for profile in profiles:
                    if profile["name"].lower() == name.lower():
                        self.session.open(
                            MessageBox,
                            f"Profile '{name}' already exists!",
                            MessageBox.TYPE_ERROR
                        )
                        return
                
                # Create new profile based on current
                current_profile = self.hotkey_manager.get_profile_info()
                
                new_profile_id = name.lower().replace(" ", "_")
                new_profile = {
                    "name": name,
                    "description": f"Custom profile: {name}",
                    "hotkeys": current_profile.get("hotkeys", {}).copy()
                }
                
                # Add to config
                self.hotkey_manager.config["hotkey_profiles"][new_profile_id] = new_profile
                
                # Switch to new profile
                self.hotkey_manager.set_profile(new_profile_id)
                self.current_profile = new_profile_id
                
                self.update_profile_display()
                self.update_hotkey_list()
                
                self.session.open(
                    MessageBox,
                    f"✅ New profile created: {name}",
                    MessageBox.TYPE_INFO,
                    timeout=2
                )
            
            self.session.openWithCallback(
                name_entered,
                VirtualKeyBoard,
                title="Enter profile name:",
                text=""
            )
            
        except Exception as e:
            logger.error(f"Error creating profile: {e}")
            self.session.open(
                MessageBox,
                f"Error creating profile:\n{e}",
                MessageBox.TYPE_ERROR
            )
    
    def delete_current_profile(self):
        """Delete current profile"""
        if not self.hotkey_manager:
            return
        
        current_profile = self.hotkey_manager.get_profile_info()
        profile_name = current_profile.get("name", "Current")
        
        # Don't allow deleting default profile
        if self.current_profile == "default":
            self.session.open(
                MessageBox,
                "Cannot delete the default profile!",
                MessageBox.TYPE_ERROR
            )
            return
        
        self.session.openWithCallback(
            lambda confirmed: self._confirm_delete_profile(confirmed, profile_name),
            MessageBox,
            f"Delete profile '{profile_name}'?\n\nThis action cannot be undone!",
            MessageBox.TYPE_YESNO
        )
    
    def _confirm_delete_profile(self, confirmed, profile_name):
        """Confirm profile deletion"""
        if not confirmed:
            return
        
        try:
            # Delete profile
            if self.current_profile in self.hotkey_manager.config.get("hotkey_profiles", {}):
                del self.hotkey_manager.config["hotkey_profiles"][self.current_profile]
                
                # Switch to default profile
                self.hotkey_manager.set_profile("default")
                self.current_profile = "default"
                
                self.update_profile_display()
                self.update_hotkey_list()
                
                self.session.open(
                    MessageBox,
                    f"✅ Profile '{profile_name}' deleted!",
                    MessageBox.TYPE_INFO,
                    timeout=2
                )
                
        except Exception as e:
            logger.error(f"Error deleting profile: {e}")
            self.session.open(
                MessageBox,
                f"Error deleting profile:\n{e}",
                MessageBox.TYPE_ERROR
            )
    
    def show_help(self):
        """Show help information"""
        help_text = """
        🎮 HOTKEY CONFIGURATION HELP
        
        OVERVIEW:
        This screen allows you to customize hotkeys for the media player.
        Hotkeys are keyboard shortcuts that trigger actions during playback.
        
        BASIC USAGE:
        • Use ↑↓ to navigate hotkey list
        • Press OK to select a hotkey
        • Press RED to change the assigned key
        • Press GREEN to save changes
        • Press YELLOW to switch profiles
        • Press BLUE for more options
        
        PROFILES:
        • Different profiles for different users/needs
        • Create custom profiles for specific use cases
        • Switch between profiles easily
        
        KEY TYPES:
        • Standard keys: subtitle, text, audio, etc.
        • Color buttons: red, green, yellow, blue
        • Number keys: 0-9
        • Long press: Add 'long_' prefix (e.g., long_audio)
        
        ACTIONS:
        • Toggle subtitles on/off
        • Open subtitle/audio menus
        • Jump forward/backward
        • Open chapter/jump menus
        • Mark playback positions
        
        TIPS:
        • Export your configuration for backup
        • Create profiles for different family members
        • Test new key mappings in the player
        • Reset to defaults if you get confused
        
        NOTE:
        Changes are saved to /etc/enigma2/wgfilemanager_hotkeys.json
        """
        
        from Screens.ScrollLabel import ScrollLabel
        
        class HelpScreen(ScrollLabel):
            def __init__(self, session, text):
                ScrollLabel.__init__(self, session, text)
                self["actions"] = ActionMap(["OkCancelActions"], {
                    "ok": self.close,
                    "cancel": self.close
                }, -1)
        
        self.session.open(HelpScreen, help_text)
    
    def exit_screen(self):
        """Exit the setup screen"""
        # Check for unsaved changes
        self.session.openWithCallback(
            self._confirm_exit,
            MessageBox,
            "Exit hotkey setup?\n\nAny unsaved changes will be lost!",
            MessageBox.TYPE_YESNO
        )
    
    def _confirm_exit(self, confirmed):
        """Confirm exit"""
        if confirmed:
            self.close()