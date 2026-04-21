from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.ActionMap import ActionMap
from Components.config import config, configfile
from Components.FileList import FileList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from enigma import getDesktop, eTimer, eLabel, gFont, gRGB, RT_HALIGN_LEFT, RT_VALIGN_CENTER
import threading
import os
import time

from ..core.config import WGFileManagerConfig
from ..core.file_operations import FileOperations
from ..core.archive import ArchiveManager
from ..core.search import SearchEngine
from ..network.remote_manager import RemoteConnectionManager
from ..network.mount import MountManager
from ..utils.formatters import get_file_icon, format_size
from ..utils.logging_config import get_logger
from .context_menu import ContextMenuHandler
from .dialogs import Dialogs

from ..player.enigma_player import EnigmaPlayer

logger = get_logger(__name__)

class EnhancedFileList(FileList):
    """Enhanced FileList that always shows parent directory (..) with comprehensive debugging"""

    def __init__(self, directory, **kwargs):
        logger.debug(f"[EnhancedFileList] Initializing with directory: {directory}")
        try:
            FileList.__init__(self, directory, **kwargs)
            self.alwaysshow_parent = True
            self._debug_enabled = True
            self.inhibitDirs = []
            self.isTop = False
            logger.debug(f"[EnhancedFileList] Initialized successfully.")
        except Exception as e:
            logger.error(f"[EnhancedFileList] Init error: {e}")
            raise

    def changeDir(self, directory, select=None):
        logger.debug(f"[EnhancedFileList] changeDir called: {directory}, select={select}")
        try:
            old_dir = self.getCurrentDirectory()
            logger.debug(f"[EnhancedFileList] Changing from {old_dir} to {directory}")

            FileList.changeDir(self, directory, select)

            new_dir = self.getCurrentDirectory()
            is_root = (new_dir == "/")

            if not is_root and self.alwaysshow_parent:
                has_parent = False
                for item in self.list:
                    try:
                        item_path = item[0][0]
                        item_name = item[0][2] if len(item[0]) > 2 else ""
                        if ".." in str(item_path) or ".." in str(item_name):
                            has_parent = True
                            break
                    except Exception as e:
                        logger.debug(f"[EnhancedFileList] Error checking item: {e}")
                        continue

                if not has_parent:
                    try:
                        parent_dir = os.path.dirname(new_dir)
                        parent_entry = (
                            (parent_dir, True, "..", False),
                            ".."
                        )
                        self.list.insert(0, parent_entry)
                        self.l.setList(self.list)
                    except Exception as e:
                        logger.error(f"[EnhancedFileList] Error adding parent directory: {e}")

        except Exception as e:
            logger.error(f"[EnhancedFileList] Error in changeDir: {e}")
            raise

    def refresh(self):
        logger.debug(f"[EnhancedFileList] refresh() called")
        try:
            current_dir = self.getCurrentDirectory()
            result = FileList.refresh(self)
            if current_dir != "/" and self.alwaysshow_parent:
                self.changeDir(current_dir)
            return result
        except Exception as e:
            logger.error(f"[EnhancedFileList] Error in refresh: {e}")
            return False

    def getCurrentDirectory(self):
        try:
            dir_path = FileList.getCurrentDirectory(self)
            return dir_path
        except Exception as e:
            logger.error(f"[EnhancedFileList] Error getting current directory: {e}")
            return ""


class WGFileManagerMain(Screen):
    def __init__(self, session):
        logger.info("[MainScreen] Initializing WGFileManagerMain")
        Screen.__init__(self, session)

        try:
            logger.debug("[MainScreen] Creating WGFileManagerConfig instance")
            self.config = WGFileManagerConfig()
            logger.debug("[MainScreen] Config created successfully")
        except Exception as e:
            logger.error(f"[MainScreen] Config init error: {e}")
            from Components.config import config as en_config
            self.config = en_config
            logger.warning("[MainScreen] Using global config as fallback")

        w, h = getDesktop(0).size().width(), getDesktop(0).size().height()
        pane_width = (w - 60) // 2
        pane_height = h - 320

        try:
            logger.debug("[MainScreen] Initializing core components")
            self.file_ops = FileOperations(self.config)
            self.archive_mgr = ArchiveManager(self.file_ops)
            self.search_engine = SearchEngine()
            self.remote_mgr = RemoteConnectionManager(self.config)
            self.mount_mgr = MountManager(self.config)
            logger.debug("[MainScreen] Core components initialized")
        except Exception as e:
            logger.error(f"[MainScreen] Error initializing core components: {e}")

        self.marked_files = set()
        self.active_pane = None

        logger.debug("[MainScreen] Initializing UI components")
        self.dialogs = Dialogs(self.session)
        self.context_menu = ContextMenuHandler(self, self.config)
        logger.debug("[MainScreen] UI components initialized")

        self.setup_ui(w, h, pane_width, pane_height)
        self.init_state()
        self.setup_actions()

        self.onLayoutFinish.append(self.startup)
        logger.info("[MainScreen] Initialization complete")

    def setup_ui(self, w, h, pane_width, pane_height):
        logger.debug("[MainScreen] Setting up UI")

        button_y = h - 60
        label_y = h - 45

        self.skin = f"""
        <screen name="WGFileManagerMain" position="0,0" size="{w},{h}" backgroundColor="#1a1a1a" flags="wfNoBorder">
            <eLabel position="0,0" size="{w},60" backgroundColor="#0055aa" />
            <eLabel text="WG FILE MANAGER PRO" position="20,8" size="600,44" font="Regular;30" halign="left" valign="center" transparent="1" foregroundColor="#ffffff" />
            <eLabel text="v1.0 Professional" position="{w-250},12" size="230,36" font="Regular;22" halign="right" valign="center" transparent="1" foregroundColor="#00ffff" />

            <widget name="left_banner" position="25,70" size="{pane_width},28" font="Regular;20" halign="left" valign="center" backgroundColor="#333333" foregroundColor="#ffff00" />
            <eLabel position="{pane_width + 30},70" size="10,28" backgroundColor="#555555" />
            <widget name="right_banner" position="{pane_width + 45},70" size="{pane_width},28" font="Regular;20" halign="left" valign="center" backgroundColor="#333333" foregroundColor="#aaaaaa" />

            <widget name="left_pane" position="25,110" size="{pane_width},{pane_height}" font="Regular;18" itemHeight="38" selectionColor="#FF5555" scrollbarMode="showOnDemand" />
            <widget name="right_pane" position="{pane_width + 45},110" size="{pane_width},{pane_height}" font="Regular;18" itemHeight="38" selectionColor="#FF5555" scrollbarMode="showOnDemand" />

            <widget name="progress_bar" position="20,{h-150}" size="{w-40},8" backgroundColor="#333333" foregroundColor="#00aaff" borderWidth="2" borderColor="#aaaaaa" />
            <widget name="info_panel" position="20,{h-135}" size="{w-40},30" font="Regular;20" foregroundColor="#ff8800" transparent="1" />
            <widget name="status_bar" position="20,{h-100}" size="{w-40},35" font="Regular;22" foregroundColor="#ffffff" transparent="1" />

            <eLabel position="0,{h-60}" size="{w},60" backgroundColor="#000000" />
            <ePixmap pixmap="buttons/red.png" position="20,{button_y}" size="30,30" alphatest="on" />
            <ePixmap pixmap="buttons/green.png" position="180,{button_y}" size="30,30" alphatest="on" />
            <ePixmap pixmap="buttons/yellow.png" position="340,{button_y}" size="30,30" alphatest="on" />
            <ePixmap pixmap="buttons/blue.png" position="500,{button_y}" size="30,30" alphatest="on" />

            <eLabel text="Delete" position="60,{label_y}" size="100,30" font="Regular;20" transparent="1" foregroundColor="#ffffff" />
            <eLabel text="Rename" position="220,{label_y}" size="100,30" font="Regular;20" transparent="1" foregroundColor="#ffffff" />
            <eLabel text="Select" position="380,{label_y}" size="100,30" font="Regular;20" transparent="1" foregroundColor="#ffffff" />
            <eLabel text="Copy/Move" position="540,{label_y}" size="150,30" font="Regular;20" transparent="1" foregroundColor="#ffffff" />
            <widget name="help_text" position="50,{h-80}" size="{w-100},30" font="Regular;18" halign="right" transparent="1" foregroundColor="#aaaaaa" />
        </screen>"""

        left_path = self.config.plugins.wgfilemanager.left_path.value
        right_path = self.config.plugins.wgfilemanager.right_path.value

        try:
            self["left_pane"] = EnhancedFileList(left_path, showDirectories=True, showFiles=True)
            self["right_pane"] = EnhancedFileList(right_path, showDirectories=True, showFiles=True)
            self["left_pane"].useSelection = True
            self["right_pane"].useSelection = True
        except Exception as e:
            logger.error(f"[MainScreen] Error creating EnhancedFileList: {e}")
            self["left_pane"] = FileList(left_path, showDirectories=True, showFiles=True)
            self["right_pane"] = FileList(right_path, showDirectories=True, showFiles=True)
            self["left_pane"].useSelection = True
            self["right_pane"].useSelection = True

        for pane_name, pane in [("left_pane", self["left_pane"]), ("right_pane", self["right_pane"])]:
            try:
                pane.inhibitDirs = []
                pane.isTop = False
            except Exception as e:
                logger.error(f"[MainScreen] Error configuring {pane_name}: {e}")

        self["progress_bar"] = ProgressBar()
        self["status_bar"] = Label("Loading...")
        self["info_panel"] = Label("")
        self["left_banner"] = Label("◀ LEFT PANE")
        self["right_banner"] = Label("RIGHT PANE ▶")
        self["help_text"] = Label("OK:Navigate(hold:Menu) 0:Menu YEL:Select MENU:Tools")

        try:
            for pane_name, pane in [("left_pane", self["left_pane"]), ("right_pane", self["right_pane"])]:
                try:
                    pane.itemHeight = 38
                    if hasattr(pane, "l"):
                        pane.l.setItemHeight(38)
                        pane.l.setFont(gFont("Regular", 18))
                except Exception as e:
                    logger.error(f"[MainScreen] Error applying styling to {pane_name}: {e}")
        except Exception as e:
            logger.error(f"[MainScreen] Error in UI styling: {e}")

    def init_state(self):
        logger.debug("[MainScreen] Initializing state")

        self.operation_in_progress = False
        self.operation_lock = threading.Lock()
        self.operation_timer = eTimer()
        self.operation_timer.callback.append(self.update_operation_progress)
        self.operation_current = 0
        self.operation_total = 0

        self.clipboard = []
        self.clipboard_mode = None

        self.bookmarks = self.config.load_bookmarks()

        starting_pane = self.config.plugins.wgfilemanager.starting_pane.value
        if starting_pane == "left":
            self.active_pane = self["left_pane"]
            self.inactive_pane = self["right_pane"]
        else:
            self.active_pane = self["right_pane"]
            self.inactive_pane = self["left_pane"]

        self.left_sort_mode = self.config.plugins.wgfilemanager.left_sort_mode.value
        self.right_sort_mode = self.config.plugins.wgfilemanager.right_sort_mode.value

        self.filter_pattern = None
        self.preview_in_progress = False
        self.marked_files = set()

    def setup_actions(self):
        logger.debug("[MainScreen] Setting up action map")
        self["actions"] = ActionMap([
            "WGFileManagerActions",
            "OkCancelActions", "ColorActions", "DirectionActions",
            "MenuActions", "NumberActions", "ChannelSelectBaseActions"
        ], {
            "ok": self.ok_pressed,
            "cancel": self.exit,
            "exit": self.exit,
            "up": self.up,
            "down": self.down,
            "left": self.focus_left,
            "right": self.focus_right,
            "red": self.delete_request,
            "green": self.rename_request,
            "yellow": self.toggle_selection,
            "yellow_long": self.unmark_all,
            "blue": self.quick_copy,
            "menu": self.open_tools,
            "0": self.zero_pressed,
            "1": lambda: self.quick_bookmark(1),
            "2": lambda: self.quick_bookmark(2),
            "3": lambda: self.quick_bookmark(3),
            "4": lambda: self.quick_bookmark(4),
            "5": lambda: self.quick_bookmark(5),
            "6": lambda: self.quick_bookmark(6),
            "7": lambda: self.quick_bookmark(7),
            "8": lambda: self.quick_bookmark(8),
            "9": lambda: self.quick_bookmark(9),
            "play": self.preview_media,
            "playpause": self.preview_media,
            "info": self.show_storage_quick_selector,
            "text": self.preview_file,
            "nextBouquet": self.next_sort,
            "prevBouquet": self.prev_sort,
            "channelUp": self.next_sort,
            "channelDown": self.prev_sort,
            "audio": self.show_storage_selector,
            "pageUp": lambda: self.page_up(),
            "pageDown": lambda: self.page_down(),
            "back": self.navigate_to_parent,
            "home": lambda: self.go_home(),
            "end": lambda: self.go_end(),
            "help": self.open_hotkey_settings,
        }, -1)

    def startup(self):
        logger.info("[MainScreen] Starting up...")
        self["status_bar"].setText("Initializing...")

        if not self.validate_config():
            self.dialogs.show_message(
                "Configuration issues detected!\n\nUsing default paths.",
                type="warning"
            )

        self.check_dependencies()
        self.update_ui()
        self.update_help_text()

        if self.config.plugins.wgfilemanager.show_dirs_first.value == "yes":
            self.apply_show_dirs_first()

        logger.info("[MainScreen] WGFileManager started successfully")
        self["status_bar"].setText("Ready")

    def validate_config(self):
        issues = []

        left_path = self.config.plugins.wgfilemanager.left_path.value
        if not os.path.isdir(left_path):
            issues.append(f"Left path not found: {left_path}")

        right_path = self.config.plugins.wgfilemanager.right_path.value
        if not os.path.isdir(right_path):
            issues.append(f"Right path not found: {right_path}")

        if issues:
            logger.warning(f"[MainScreen] Config issues: {issues}")
            return False
        return True

    # UI Update Methods

    def update_ui(self):
        try:
            self.update_banners()
            self.update_status_bar()
            self.update_info_panel()
        except Exception as e:
            logger.error(f"[MainScreen] Error updating UI: {e}")

    def update_banners(self):
        try:
            is_left_active = (self.active_pane == self["left_pane"])
            is_right_active = (self.active_pane == self["right_pane"])

            try:
                left_dir = self["left_pane"].getCurrentDirectory()
                right_dir = self["right_pane"].getCurrentDirectory()

                if is_left_active:
                    left_text = "◀ LEFT: " + left_dir
                    right_text = "RIGHT: " + right_dir
                else:
                    left_text = "LEFT: " + left_dir
                    right_text = "RIGHT: " + right_dir + " ▶"

                if len(left_text) > 50:
                    left_text = left_text[:47] + "..."
                if len(right_text) > 50:
                    right_text = right_text[:47] + "..."

            except Exception as e:
                left_text = "◀ LEFT" if is_left_active else "LEFT"
                right_text = "RIGHT ▶" if is_right_active else "RIGHT"

            self["left_banner"].setText(left_text)
            self["right_banner"].setText(right_text)

            try:
                ACTIVE_COLOR = gRGB(0xffff00)
                INACTIVE_COLOR = gRGB(0xaaaaaa)

                left_instance = self["left_banner"].instance
                right_instance = self["right_banner"].instance

                if left_instance:
                    left_instance.setForegroundColor(ACTIVE_COLOR if is_left_active else INACTIVE_COLOR)
                if right_instance:
                    right_instance.setForegroundColor(ACTIVE_COLOR if is_right_active else INACTIVE_COLOR)
            except Exception as e:
                logger.error(f"[MainScreen] Banner styling error: {e}")

        except Exception as e:
            logger.error(f"[MainScreen] Error updating banners: {e}")

    def update_status_bar(self):
        try:
            count = len(self.marked_files)

            sel = self.active_pane.getSelection()
            current_name = ""
            if sel and sel[0]:
                current_name = os.path.basename(sel[0])

            if count > 0:
                status_text = "✓ SELECTED: %d items | Current: %s" % (count, current_name)
            else:
                current_dir = self.active_pane.getCurrentDirectory()
                status_text = "Path: %s" % current_dir

            self["status_bar"].setText(status_text)
        except Exception as e:
            logger.error(f"[MainScreen] Error updating status bar: {e}")

    def update_info_panel(self):
        try:
            sel = self.active_pane.getSelection()
            if sel and sel[0]:
                path = sel[0]
                name = os.path.basename(path)
                icon = get_file_icon(path)

                is_marked = False
                for item in self.active_pane.list:
                    if item[0][0] == path and item[0][3]:
                        is_marked = True
                        break

                if os.path.isfile(path):
                    try:
                        size = os.path.getsize(path)
                        size_str = format_size(size)
                    except:
                        size_str = "?"
                else:
                    size_str = "DIR"

                if is_marked:
                    text = f"🔴 {icon} {name} | {size_str}"
                else:
                    text = f"{icon} {name} | {size_str}"

                self["info_panel"].setText(text)
                return
        except Exception as e:
            logger.debug(f"[MainScreen] Error updating info panel: {e}")

        self["info_panel"].setText("")

    def update_operation_progress(self):
        try:
            if self.operation_total > 0:
                progress = int((self.operation_current / self.operation_total) * 100)
                self["progress_bar"].setValue(progress)
            self.update_ui()
        except Exception as e:
            logger.error(f"[MainScreen] Error updating operation progress: {e}")

    def update_help_text(self):
        help_text = "OK:Play/Open 0:Menu INFO:Storage 1-9:BMark MENU:Tools"
        self["help_text"].setText(help_text)

    # OK Button

    def ok_pressed(self):
        self.execute_ok_navigation()

    def execute_ok_navigation(self):
        try:
            sel = self.active_pane.getSelection()
            if not sel or not sel[0]:
                return

            path = sel[0]

            if path.endswith("..") or os.path.basename(path) == "..":
                current_dir = self.active_pane.getCurrentDirectory()
                if current_dir != "/":
                    parent_dir = os.path.dirname(current_dir)
                    self.active_pane.changeDir(parent_dir)
                    self.update_ui()
                return

            if os.path.isdir(path):
                self.active_pane.changeDir(path)
                self.update_ui()
            else:
                ext = os.path.splitext(path)[1].lower()

                if ext in ['.mp4', '.mkv', '.avi', '.ts', '.m2ts', '.mov', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv']:
                    self.play_media_file(path)
                elif ext in ['.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma', '.ac3', '.dts']:
                    self.context_menu.show_smart_context_menu(path)
                elif ext in ['.sh', '.py', '.pl']:
                    self.context_menu.show_smart_context_menu(path)
                elif ext in ['.zip', '.tar', '.tar.gz', '.tgz', '.rar', '.7z', '.gz']:
                    self.context_menu.show_smart_context_menu(path)
                elif ext == '.ipk':
                    self.context_menu.show_smart_context_menu(path)
                elif ext in ['.txt', '.log', '.conf', '.cfg', '.ini', '.xml', '.json', '.md']:
                    self.preview_file()
                elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                    self.dialogs.preview_image(path, self.file_ops)
                else:
                    self.show_file_info()

        except Exception as e:
            logger.error(f"[MainScreen] Error in OK navigation: {e}")
            self.show_error("Navigation", e)

    def navigate_to_parent(self):
        try:
            current_dir = self.active_pane.getCurrentDirectory()

            if current_dir and current_dir != "/":
                parent_dir = os.path.dirname(current_dir)
                self["status_bar"].setText(f"↑ {parent_dir}")
                self.active_pane.changeDir(parent_dir)
                self.update_ui()
            else:
                self["status_bar"].setText("Already at root directory")

                def reset_msg():
                    time.sleep(1)
                    self.update_status_bar()
                threading.Thread(target=reset_msg, daemon=True).start()

        except Exception as e:
            logger.error(f"[MainScreen] Error navigating to parent: {e}")
            self.show_error("Navigate parent", e)

    def toggle_selection(self):
        try:
            pane = self.active_pane
            sel = pane.getSelection()

            if sel and sel[0]:
                pane.markSelected()
                path = sel[0]
                if path in self.marked_files:
                    self.marked_files.remove(path)
                else:
                    self.marked_files.add(path)

                self.update_info_panel()
                self.update_status_bar()
        except Exception as e:
            logger.error(f"[MainScreen] Error toggling selection: {e}")

    def unmark_all(self):
        if self.marked_files:
            self.marked_files.clear()
            self["left_pane"].refresh()
            self["right_pane"].refresh()
            self["status_bar"].setText("All selections cleared.")
        else:
            self["status_bar"].setText("Nothing was selected.")

    def up(self):
        try:
            self.active_pane.up()
            self.update_info_panel()
        except Exception as e:
            logger.error(f"[MainScreen] Error moving up: {e}")

    def down(self):
        try:
            self.active_pane.down()
            self.update_info_panel()
        except Exception as e:
            logger.error(f"[MainScreen] Error moving down: {e}")

    def page_up(self):
        try:
            for _ in range(10):
                self.active_pane.up()
            self.update_info_panel()
        except Exception as e:
            logger.error(f"[MainScreen] Error page up: {e}")

    def page_down(self):
        try:
            for _ in range(10):
                self.active_pane.down()
            self.update_info_panel()
        except Exception as e:
            logger.error(f"[MainScreen] Error page down: {e}")

    def go_home(self):
        try:
            self.active_pane.instance.moveSelection(self.active_pane.instance.moveTop)
            self.update_info_panel()
        except Exception as e:
            logger.error(f"[MainScreen] Error going home: {e}")

    def go_end(self):
        try:
            self.active_pane.instance.moveSelection(self.active_pane.instance.moveBottom)
            self.update_info_panel()
        except Exception as e:
            logger.error(f"[MainScreen] Error going end: {e}")

    def focus_left(self):
        try:
            self.active_pane = self["left_pane"]
            self.inactive_pane = self["right_pane"]
            self.update_ui()
            self.update_help_text()
        except Exception as e:
            logger.error(f"[MainScreen] Error focusing left pane: {e}")

    def focus_right(self):
        try:
            self.active_pane = self["right_pane"]
            self.inactive_pane = self["left_pane"]
            self.update_ui()
            self.update_help_text()
        except Exception as e:
            logger.error(f"[MainScreen] Error focusing right pane: {e}")

    # File Operations

    def delete_request(self):
        try:
            marked = [x for x in self.active_pane.list if x[0][3]]

            if marked:
                files = [x[0][0] for x in marked]
                self.dialogs.show_confirmation(
                    f"Delete {len(files)} selected items?\n\nThis cannot be undone!",
                    lambda res: self._execute_delete_multiple(res, files) if res else None
                )
            else:
                sel = self.active_pane.getSelection()
                if not sel or not sel[0]:
                    self.dialogs.show_message("No file selected!", type="info")
                    return

                item_path = sel[0]
                item_name = os.path.basename(item_path)
                is_dir = os.path.isdir(item_path)
                item_type = "folder" if is_dir else "file"

                self.dialogs.show_confirmation(
                    f"Delete {item_type} '{item_name}'?\n\nThis cannot be undone!",
                    lambda res: self._execute_delete(res, item_path, item_name) if res else None
                )
        except Exception as e:
            logger.error(f"[MainScreen] Error in delete request: {e}")
            self.show_error("Delete", e)

    def _execute_delete(self, confirmed, item_path, item_name):
        if not confirmed:
            return
        try:
            self.file_ops.delete(item_path)
            self.active_pane.refresh()
            self.update_ui()

            if self.config.plugins.wgfilemanager.trash_enabled.value == "yes":
                msg = f"Moved to trash: {item_name}"
            else:
                msg = f"Permanently deleted: {item_name}"

            self.dialogs.show_message(msg, type="info", timeout=2)
        except Exception as e:
            logger.error(f"[MainScreen] Error executing delete: {e}")
            self.show_error("Delete", e)

    def _execute_delete_multiple(self, confirmed, files):
        if not confirmed:
            return
        try:
            success = 0
            errors = []

            for item_path in files:
                try:
                    self.file_ops.delete(item_path)
                    success += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(item_path)}: {str(e)[:30]}")

            msg = f"Deleted: {success} items\n"
            if errors:
                msg += f"\nFailed: {len(errors)}\n"
                msg += "\n".join(errors[:3])
                if len(errors) > 3:
                    msg += f"\n... and {len(errors) - 3} more"

            self.active_pane.refresh()
            self.update_ui()
            self.dialogs.show_message(msg, type="info")
        except Exception as e:
            logger.error(f"[MainScreen] Error deleting multiple items: {e}")
            self.dialogs.show_message(f"Delete multiple failed: {e}", type="error")

    def rename_request(self):
        try:
            marked = [x for x in self.active_pane.list if x[0][3]]

            if len(marked) > 1:
                self.dialogs.show_message(
                    f"Multiple files selected ({len(marked)} items)\n\nUse MENU -> Tools -> Bulk Rename\nfor renaming multiple files",
                    type="info"
                )
                return

            sel = self.active_pane.getSelection()
            if not sel or not sel[0]:
                self.dialogs.show_message("No file selected!", type="info")
                return

            item_path = sel[0]
            current_name = os.path.basename(item_path)

            def rename_callback(new_name):
                if new_name and new_name != current_name:
                    self._execute_rename(new_name, item_path, current_name)

            keyboard_screen = self.session.instantiateDialog(
                VirtualKeyBoard,
                title="Rename: " + current_name[:30],
                text=current_name
            )

            if hasattr(keyboard_screen, 'text'):
                keyboard_screen.text = current_name
            if hasattr(keyboard_screen, 'Text'):
                keyboard_screen.Text = current_name

            self.session.openWithCallback(rename_callback, keyboard_screen)

        except Exception as e:
            logger.error(f"[MainScreen] Error in rename request: {e}")
            self.show_error("Rename", e)

    def _execute_rename(self, new_name, old_path, old_name):
        if not new_name or new_name == old_name:
            return
        try:
            new_path = self.file_ops.rename(old_path, new_name)
            self.active_pane.refresh()
            self.update_ui()
            self.dialogs.show_message(f"Renamed to: {new_name}", type="info", timeout=2)
        except Exception as e:
            logger.error(f"[MainScreen] Error executing rename: {e}")
            self.show_error("Rename", e)

    def quick_copy(self):
        try:
            if self.clipboard:
                self.paste_from_clipboard()
                return

            if self.active_pane == self["left_pane"]:
                dest_pane = self["right_pane"]
            else:
                dest_pane = self["left_pane"]

            dest = dest_pane.getCurrentDirectory()
            files = self.get_selected_files()

            if not files:
                self.dialogs.show_message("No files selected!", type="info")
                return

            self.dialogs.show_transfer_dialog(files, dest, self.execute_transfer)
        except Exception as e:
            logger.error(f"[MainScreen] Error in quick copy: {e}")
            self.show_error("Copy", e)

    def get_selected_files(self):
        files = []
        try:
            for item in self.active_pane.list:
                if item[0][3]:
                    files.append(item[0][0])

            if not files:
                sel = self.active_pane.getSelection()
                if sel and sel[0]:
                    files.append(sel[0])
        except Exception as e:
            logger.error(f"[MainScreen] Error getting selected files: {e}")
        return files

    def paste_from_clipboard(self):
        if not self.clipboard:
            return
        try:
            dest = self.active_pane.getCurrentDirectory()

            if not os.path.isdir(dest):
                self.dialogs.show_message(f"Invalid destination: {dest}", type="error")
                return

            mode = "cp" if self.clipboard_mode == "copy" else "mv"
            action = "Copy" if mode == "cp" else "Move"

            self.dialogs.show_confirmation(
                f"{action} {len(self.clipboard)} items to:\n{dest}?",
                lambda res: self.execute_paste(res, mode, self.clipboard[:], dest)
            )
        except Exception as e:
            logger.error(f"[MainScreen] Error pasting from clipboard: {e}")
            self.show_error("Paste", e)

    def execute_paste(self, confirmed, mode, files, dest):
        if not confirmed:
            return

        with self.operation_lock:
            if self.operation_in_progress:
                self.dialogs.show_message("Another operation is in progress!", type="warning")
                return
            self.operation_in_progress = True

        try:
            self.operation_current = 0
            self.operation_total = len(files)
            self.operation_timer.start(500)

            thread = threading.Thread(
                target=self._perform_paste,
                args=(mode, files, dest),
                daemon=True
            )
            thread.start()
        except Exception as e:
            logger.error(f"[MainScreen] Error starting paste operation: {e}")
            with self.operation_lock:
                self.operation_in_progress = False
            self.show_error("Paste", e)

    def _perform_paste(self, mode, files, dest):
        try:
            for i, src in enumerate(files):
                try:
                    if mode == "cp":
                        self.file_ops.copy(src, dest)
                    elif mode == "mv":
                        self.file_ops.move(src, dest)

                    with self.operation_lock:
                        self.operation_current = i + 1
                except Exception as e:
                    logger.error(f"[MainScreen] Paste failed for {src}: {e}")

            with self.operation_lock:
                self.operation_in_progress = False
                self.operation_timer.stop()

            if mode == "mv":
                self.clipboard = []
                self.clipboard_mode = None

            self.session.openWithCallback(
                lambda: None,
                MessageBox,
                "Paste complete!",
                type=MessageBox.TYPE_INFO,
                timeout=2
            )

            self.active_pane.refresh()
            self.inactive_pane.refresh()
            self.update_ui()

        except Exception as e:
            logger.error(f"[MainScreen] Paste operation failed: {e}")
            with self.operation_lock:
                self.operation_in_progress = False
                self.operation_timer.stop()

            self.session.openWithCallback(
                lambda: None,
                MessageBox,
                f"Paste failed:\n{e}",
                type=MessageBox.TYPE_ERROR
            )

    def execute_transfer(self, mode, files, dest):
        with self.operation_lock:
            if self.operation_in_progress:
                self.dialogs.show_message("Another operation is in progress!", type="warning")
                return
            self.operation_in_progress = True

        try:
            self.operation_current = 0
            self.operation_total = len(files)
            self.operation_timer.start(500)

            thread = threading.Thread(
                target=self._perform_transfer,
                args=(mode, files, dest),
                daemon=True
            )
            thread.start()
        except Exception as e:
            logger.error(f"[MainScreen] Error starting transfer operation: {e}")
            with self.operation_lock:
                self.operation_in_progress = False
            self.show_error("Transfer", e)

    def _perform_transfer(self, mode, files, dest):
        try:
            for i, src in enumerate(files):
                try:
                    if mode == "cp":
                        self.file_ops.copy(src, dest)
                    elif mode == "mv":
                        self.file_ops.move(src, dest)

                    with self.operation_lock:
                        self.operation_current = i + 1
                except Exception as e:
                    logger.error(f"[MainScreen] Transfer failed for {src}: {e}")

            with self.operation_lock:
                self.operation_in_progress = False
                self.operation_timer.stop()

            self.session.openWithCallback(
                lambda: None,
                MessageBox,
                "Transfer complete!",
                type=MessageBox.TYPE_INFO,
                timeout=2
            )

            self.active_pane.refresh()
            self.inactive_pane.refresh()
            self.update_ui()

        except Exception as e:
            logger.error(f"[MainScreen] Transfer operation failed: {e}")
            with self.operation_lock:
                self.operation_in_progress = False
                self.operation_timer.stop()

            self.session.openWithCallback(
                lambda: None,
                MessageBox,
                f"Transfer failed:\n{e}",
                type=MessageBox.TYPE_ERROR
            )

    # Tools and Features

    def open_tools(self):
        if self.operation_in_progress:
            self.dialogs.show_message("Please wait for current operation to complete!", type="info")
            return
        try:
            self.context_menu.show_tools_menu()
        except Exception as e:
            logger.error(f"[MainScreen] Error opening tools menu: {e}")
            self.show_error("Tools menu", e)

    def zero_pressed(self):
        try:
            if not self.config.plugins.wgfilemanager.enable_smart_context.value:
                self.show_file_info()
                return

            marked = [x for x in self.active_pane.list if x[0][3]]

            if marked:
                self.context_menu.show_multi_selection_context_menu(marked)
            else:
                self.context_menu.show_context_menu()
        except Exception as e:
            logger.error(f"[MainScreen] Error in zero pressed: {e}")
            self.show_error("Context menu", e)

    def quick_bookmark(self, num):
        try:
            key = str(num)

            if key in self.bookmarks:
                path = self.bookmarks[key]
                if os.path.isdir(path):
                    self.active_pane.changeDir(path)
                    self.update_ui()
                    self["status_bar"].setText(f"Jumped to bookmark {num}: {os.path.basename(path)}")
                else:
                    self.dialogs.show_message(f"Bookmark {num} path not found: {path}", type="error")
            else:
                current = self.active_pane.getCurrentDirectory()
                self.bookmarks[key] = current
                self.config.save_bookmarks(self.bookmarks)
                self.dialogs.show_message(f"Bookmark {num} set to:\n{current}", type="info", timeout=2)
        except Exception as e:
            logger.error(f"[MainScreen] Error in quick bookmark: {e}")
            self.show_error("Bookmark", e)

    def preview_file(self):
        try:
            sel = self.active_pane.getSelection()
            if not sel or not sel[0]:
                return

            file_path = sel[0]

            if os.path.isdir(file_path):
                self.dialogs.show_message("Cannot preview directory!\n\nPress OK to enter folder.", type="info")
                return

            try:
                size = self.file_ops.get_file_size(file_path)
                max_size = int(self.config.plugins.wgfilemanager.preview_size.value) * 1024
                if size > max_size:
                    self.dialogs.show_message(
                        f"File too large to preview!\n\nSize: {format_size(size)}\nLimit: {format_size(max_size)}",
                        type="info"
                    )
                    return
            except:
                pass

            self.dialogs.preview_file(file_path, self.file_ops, self.config)
        except Exception as e:
            logger.error(f"[MainScreen] Error previewing file: {e}")
            self.show_error("Preview", e)

    def preview_media(self):
        try:
            if self.preview_in_progress:
                self.dialogs.show_message("Media preview already in progress!", type="warning")
                return

            sel = self.active_pane.getSelection()
            if not sel or not sel[0]:
                return

            file_path = sel[0]

            if not self.can_play_file(file_path):
                self.dialogs.show_message(
                    "Not a playable media file!\n\nSupported: MP4, MKV, AVI, TS, MP3, FLAC, etc.",
                    type="info"
                )
                return

            self.preview_in_progress = True

            if self.config.plugins.wgfilemanager.use_internal_player.value:
                try:
                    self.play_media_file(file_path)
                except Exception as e:
                    logger.error(f"[MainScreen] Internal player failed: {e}")
                    if self.config.plugins.wgfilemanager.fallback_to_external.value:
                        self.play_with_external_player(file_path)
                    else:
                        self.dialogs.show_message(f"Media playback failed:\n{e}", type="error")
            else:
                self.play_with_external_player(file_path)

            self.preview_in_progress = False

        except Exception as e:
            logger.error(f"[MainScreen] Error previewing media: {e}")
            self.preview_in_progress = False
            self.show_error("Media preview", e)

    def can_play_file(self, path):
        if not os.path.exists(path):
            return False
        try:
            size = os.path.getsize(path)
            if size == 0:
                return False
        except:
            return False

        ext = os.path.splitext(path)[1].lower()
        supported = ['.mp4', '.mkv', '.avi', '.ts', '.m2ts', '.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a']
        return ext in supported

    def show_storage_quick_selector(self):
        try:
            mount_points = [
                ("/", "1. Root Filesystem"),
                ("/media/hdd", "2. Internal HDD"),
                ("/media/usb", "3. USB Storage"),
                ("/media/usb1", "4. USB Drive 1"),
                ("/media/usb2", "5. USB Drive 2"),
                ("/media/net", "6. Network Mounts"),
                ("/media/mmc", "7. Flash/MMC"),
                ("/media/sdcard", "8. SD Card"),
                ("/tmp", "9. Temporary Storage"),
            ]

            available_choices = []
            for path, label in mount_points:
                if os.path.isdir(path) and os.access(path, os.R_OK):
                    try:
                        st = os.statvfs(path)
                        total_gb = (st.f_blocks * st.f_frsize) / (1024**3)
                        free_gb = (st.f_bavail * st.f_frsize) / (1024**3)
                        if total_gb > 0.1 or path == "/":
                            display = f"{label}: {free_gb:.1f}GB free"
                            available_choices.append((display, path))
                    except:
                        available_choices.append((label, path))

            if not available_choices:
                self.dialogs.show_message("No storage devices found!", type="error")
                return

            from Screens.ChoiceBox import ChoiceBox

            def storage_selected(choice):
                if choice:
                    self.active_pane.changeDir(choice[1])
                    self.update_ui()

            self.session.openWithCallback(
                storage_selected,
                ChoiceBox,
                title="📂 Select Storage Device (Press 1-9)",
                list=available_choices
            )

        except Exception as e:
            logger.error(f"[MainScreen] Error showing storage quick selector: {e}")
            self.dialogs.show_message(f"Storage selector error: {e}", type="error")

    def show_storage_selector(self):
        if self.operation_in_progress:
            self.dialogs.show_message("Please wait for current operation to complete!", type="info")
            return
        try:
            def storage_selected_callback(selected_path):
                if selected_path:
                    try:
                        if os.path.isdir(selected_path):
                            self.active_pane.changeDir(selected_path)
                            self.update_ui()
                        else:
                            self.dialogs.show_message(f"Storage not found:\n{selected_path}", type="error")
                    except Exception as e:
                        self.show_error("Storage navigation", e)

            self.dialogs.show_storage_selector(storage_selected_callback, self.update_ui)

        except Exception as e:
            logger.error(f"[MainScreen] Error showing storage selector: {e}")
            self.show_error("Storage selector", e)

    def show_file_info(self):
        try:
            sel = self.active_pane.getSelection()
            if not sel or not sel[0]:
                return

            file_path = sel[0]
            info = self.file_ops.get_file_info(file_path)
            if info:
                text = f"File: {info['name']}\n"
                text += f"Path: {os.path.dirname(info['path'])}\n"
                text += f"Size: {info['size_formatted']}\n"
                text += f"Modified: {info['modified'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                text += f"Permissions: {info['permissions']}\n"

                if info['is_dir']:
                    text += f"Type: Directory\n"
                    if 'item_count' in info:
                        text += f"Items: {info['item_count']}\n"
                else:
                    text += f"Type: File\n"

                self.dialogs.show_message(text, type="info")
        except Exception as e:
            logger.error(f"[MainScreen] Error showing file info: {e}")
            self.show_error("File info", e)

    # Sorting

    def next_sort(self):
        try:
            if self.active_pane == self["left_pane"]:
                modes = ["name", "size", "date", "type"]
                current_idx = modes.index(self.left_sort_mode) if self.left_sort_mode in modes else 0
                self.left_sort_mode = modes[(current_idx + 1) % len(modes)]
                self.config.plugins.wgfilemanager.left_sort_mode.value = self.left_sort_mode
                self.config.plugins.wgfilemanager.left_sort_mode.save()
            else:
                modes = ["name", "size", "date", "type"]
                current_idx = modes.index(self.right_sort_mode) if self.right_sort_mode in modes else 0
                self.right_sort_mode = modes[(current_idx + 1) % len(modes)]
                self.config.plugins.wgfilemanager.right_sort_mode.value = self.right_sort_mode
                self.config.plugins.wgfilemanager.right_sort_mode.save()

            self.apply_sorting()
            self.update_ui()
            self.dialogs.show_message(
                f"Sort: {self.left_sort_mode if self.active_pane == self['left_pane'] else self.right_sort_mode.upper()}",
                type="info", timeout=1
            )
        except Exception as e:
            logger.error(f"[MainScreen] Error in next sort: {e}")

    def prev_sort(self):
        try:
            if self.active_pane == self["left_pane"]:
                modes = ["name", "size", "date", "type"]
                current_idx = modes.index(self.left_sort_mode) if self.left_sort_mode in modes else 0
                self.left_sort_mode = modes[(current_idx - 1) % len(modes)]
                self.config.plugins.wgfilemanager.left_sort_mode.value = self.left_sort_mode
                self.config.plugins.wgfilemanager.left_sort_mode.save()
            else:
                modes = ["name", "size", "date", "type"]
                current_idx = modes.index(self.right_sort_mode) if self.right_sort_mode in modes else 0
                self.right_sort_mode = modes[(current_idx - 1) % len(modes)]
                self.config.plugins.wgfilemanager.right_sort_mode.value = self.right_sort_mode
                self.config.plugins.wgfilemanager.right_sort_mode.save()

            self.apply_sorting()
            self.update_ui()
            self.dialogs.show_message(
                f"Sort: {self.left_sort_mode if self.active_pane == self['left_pane'] else self.right_sort_mode.upper()}",
                type="info", timeout=1
            )
        except Exception as e:
            logger.error(f"[MainScreen] Error in prev sort: {e}")

    def apply_sorting(self):
        try:
            items = self.active_pane.list
            if not items:
                return

            if self.active_pane == self["left_pane"]:
                current_sort = self.left_sort_mode
            else:
                current_sort = self.right_sort_mode

            if current_sort == "name":
                items.sort(key=lambda x: x[0][0].lower())
            elif current_sort == "size":
                items.sort(key=lambda x: self.file_ops.get_file_size(x[0][0]), reverse=True)
            elif current_sort == "date":
                items.sort(key=lambda x: os.path.getmtime(x[0][0]) if os.path.exists(x[0][0]) else 0, reverse=True)
            elif current_sort == "type":
                items.sort(key=lambda x: (not x[0][1], os.path.splitext(x[0][0])[1].lower()))

            if self.config.plugins.wgfilemanager.show_dirs_first.value == "yes":
                dirs = [item for item in items if item[0][1]]
                files = [item for item in items if not item[0][1]]
                items = dirs + files

            self.active_pane.list = items
            self.active_pane.l.setList(items)
        except Exception as e:
            logger.error(f"[MainScreen] Sorting failed: {e}")

    def apply_show_dirs_first(self):
        try:
            items = self.active_pane.list
            if not items:
                return

            dirs = [item for item in items if item[0][1]]
            files = [item for item in items if not item[0][1]]

            self.active_pane.list = dirs + files
            self.active_pane.l.setList(self.active_pane.list)
        except Exception as e:
            logger.error(f"[MainScreen] Show dirs first failed: {e}")

    # System Methods

    def check_dependencies(self):
        tools = {
            'rclone': 'Cloud sync',
            'zip': 'ZIP archives',
            'unzip': 'ZIP extraction',
            'tar': 'TAR archives',
            'cifs-utils': 'Network mounts',
            'smbclient': 'Network scanning',
            'curl': 'WebDAV support',
            'ftp': 'FTP client',
        }

        missing = []
        for tool, desc in tools.items():
            try:
                import subprocess
                result = subprocess.run(["which", tool], capture_output=True, timeout=2)
                if result.returncode != 0:
                    missing.append(f"{tool} ({desc})")
            except:
                missing.append(f"{tool} ({desc})")

        if missing:
            logger.warning(f"[MainScreen] Missing tools: {', '.join(missing)}")

    def play_media_file(self, path):
        """Play media file using EnigmaPlayer"""
        try:
            logger.info(f"[MainScreen] Playing with EnigmaPlayer: {path}")

            player = EnigmaPlayer(self.session)

            def player_closed():
                try:
                    self["left_pane"].refresh()
                    self["right_pane"].refresh()
                except:
                    pass

            player.play(path, resume_callback=player_closed)

        except ImportError as e:
            logger.warning(f"[MainScreen] EnigmaPlayer not available: {e}, using external")
            self.play_with_external_player(path)
        except Exception as e:
            logger.error(f"[MainScreen] Playback error: {e}")
            self.dialogs.show_message(
                f"Cannot play media file:\n{os.path.basename(path)}\n\nError: {e}",
                type="error"
            )

    def play_with_external_player(self, path):
        """Play with external player as fallback"""
        import subprocess

        def play_thread():
            players = [
                ['gst-launch-1.0', 'playbin', 'uri=file://' + path],
                ['ffplay', '-autoexit', '-nodisp', path],
                ['mplayer', '-quiet', path]
            ]

            for player_cmd in players:
                try:
                    subprocess.Popen(player_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.dialogs.show_message(
                        f"Playing with external player:\n{os.path.basename(path)}",
                        type="info",
                        timeout=3
                    )
                    return
                except FileNotFoundError:
                    continue

            self.dialogs.show_message(
                "No media player available!\n\nInstall: opkg install gstreamer1.0",
                type="error"
            )

        threading.Thread(target=play_thread, daemon=True).start()

    def open_hotkey_settings(self):
        try:
            from ..ui.hotkey_setup import HotkeySetupScreen
            self.session.open(HotkeySetupScreen)
        except ImportError as e:
            logger.error(f"[MainScreen] Hotkey settings not available: {e}")
            self.dialogs.show_message(
                f"Hotkey settings not available!\n\nError: {e}\n"
                "Access via: MENU → Tools → 🎮 Hotkey Settings",
                type="error",
                timeout=3
            )
        except Exception as e:
            logger.error(f"[MainScreen] Error opening hotkey settings: {e}")
            self.show_error("Hotkey settings", e)

    def show_error(self, context, error):
        error_msg = str(error)
        logger.error(f"[MainScreen] Error in {context}: {error_msg}")

        if "Permission denied" in error_msg:
            user_msg = f"{context}: Permission denied. Check file permissions."
        elif "No space left" in error_msg:
            user_msg = f"{context}: Disk full. Free up space and try again."
        elif "No such file" in error_msg:
            user_msg = f"{context}: File not found. It may have been moved or deleted."
        elif "Device or resource busy" in error_msg:
            user_msg = f"{context}: Device busy. Try again later."
        else:
            user_msg = f"{context}: {error_msg[:100]}"

        self.dialogs.show_message(user_msg, type="error")

    def cleanup(self):
        try:
            if self.operation_timer.isActive():
                self.operation_timer.stop()

            self.clipboard.clear()
            self.marked_files.clear()

            with self.operation_lock:
                self.operation_in_progress = False

        except Exception as e:
            logger.error(f"[MainScreen] Cleanup error: {e}")

    def close(self):
        try:
            self.cleanup()

            from Components.config import config
            p = config.plugins.wgfilemanager

            if p.save_left_on_exit.value == "yes":
                if hasattr(self, 'left_pane'):
                    current_left = self["left_pane"].getCurrentDirectory()
                    if current_left:
                        p.left_path.value = current_left
                        p.left_path.save()

            if p.save_right_on_exit.value == "yes":
                if hasattr(self, 'right_pane'):
                    current_right = self["right_pane"].getCurrentDirectory()
                    if current_right:
                        p.right_path.value = current_right
                        p.right_path.save()

            configfile.save()

        except Exception as e:
            logger.error(f"[MainScreen] Error during shutdown: {e}")

        Screen.close(self)

    def exit(self):
        self.close()

    def close_plugin(self):
        if self.operation_in_progress:
            self.dialogs.show_message("Operation in progress!\n\nPlease wait...", type="warning")
            return
        self.close()

    def createSummary(self):
        return None

    def getSummaryText(self):
        return "WGFileManager File Manager"
