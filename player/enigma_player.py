"""
Unified Enigma2 Player for WGFileManager
Location: player/enigma_player.py
"""
from Screens.InfoBar import MoviePlayer
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.AudioSelection import AudioSelection
from Components.ActionMap import ActionMap
from enigma import eServiceReference, iPlayableService
import os
import time
import json
import threading

# Handle imports for both installed and development mode
try:
    from ..utils.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class EnigmaPlayer:
    """
    Unified Enigma2 Player with advanced features:
    - Resume point support
    - Custom controls
    """

    def __init__(self, session):
        self.session = session
        self.current_file = None
        self.resume_points = self._load_resume_points()

    def play(self, file_path, resume_callback=None):
        """Play media file - alias for play_file for compatibility"""
        return self.play_file(file_path, resume_callback)

    def play_file(self, file_path, resume_callback=None):
        """
        Play media file with full feature support

        Args:
            file_path: Path to media file
            resume_callback: Callback when player closes
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False

            if not self._is_playable(file_path):
                logger.error(f"File not playable: {file_path}")
                return False

            self.current_file = file_path

            # Check for resume point
            resume_position = self.get_resume_point(file_path)

            if resume_position and resume_position.get('position', 0) > 10:
                from enigma import eTimer

                def show_delayed_resume():
                    self._show_resume_dialog(file_path, resume_position['position'], resume_callback)

                self.resume_delay_timer = eTimer()
                self.resume_delay_timer.callback.append(show_delayed_resume)
                self.resume_delay_timer.start(300, True)
            else:
                self._start_playback(file_path, 0, resume_callback)

            return True

        except Exception as e:
            logger.error(f"Error playing file: {e}")
            return False

    def _is_playable(self, file_path):
        """Check if file can be played"""
        playable_extensions = [
            '.mp4', '.mkv', '.avi', '.ts', '.m2ts', '.mov', '.m4v',
            '.mpg', '.mpeg', '.wmv', '.flv', '.mp3', '.flac', '.wav',
            '.aac', '.ogg', '.m4a', '.wma', '.ac3', '.dts'
        ]
        ext = os.path.splitext(file_path)[1].lower()
        return ext in playable_extensions

    def _show_resume_dialog(self, file_path, position, resume_callback):
        """Show resume playback dialog"""
        try:
            minutes = int(position / 60)
            seconds = int(position % 60)

            message = f"Resume playback?\n\n"
            message += f"File: {os.path.basename(file_path)}\n"
            message += f"Last position: {minutes}m {seconds}s\n\n"
            message += f"YES = Resume from {minutes}m {seconds}s\n"
            message += f"NO = Start from beginning"

            def handle_resume_choice(confirmed):
                if confirmed:
                    logger.info(f"Resume: YES - seeking to {position}s")
                    self._start_playback(file_path, position, resume_callback)
                else:
                    logger.info(f"Resume: NO - starting from beginning")
                    self.clear_resume_point(file_path)
                    self.clear_system_cuts(file_path)
                    time.sleep(0.1)
                    self.clear_system_cuts(file_path)

                    try:
                        for ext in [".cuts", ".ap", ".sc"]:
                            f = file_path + ext
                            if os.path.exists(f):
                                os.remove(f)
                                logger.debug(f"Deleted: {f}")
                    except Exception as e:
                        logger.debug(f"Extra cleanup failed: {e}")

                    self._start_playback(file_path, 0, resume_callback)

            self.session.openWithCallback(
                handle_resume_choice,
                MessageBox,
                message,
                MessageBox.TYPE_YESNO
            )

        except Exception as e:
            logger.error(f"Error showing resume dialog: {e}")
            self._start_playback(file_path, 0, resume_callback)

    def _start_playback(self, file_path, start_position, resume_callback):
        """Start media playback with custom player"""
        try:
            if start_position == 0:
                logger.warning("FORCING START FROM BEGINNING")
                self.clear_resume_point(file_path)
                self.clear_system_cuts(file_path)

                for ext in [".cuts", ".ap", ".sc"]:
                    cache_file = file_path + ext
                    if os.path.exists(cache_file):
                        try:
                            os.remove(cache_file)
                            logger.debug(f"Deleted: {cache_file}")
                        except:
                            pass

                time.sleep(0.2)
                self.clear_system_cuts(file_path)

            ref = eServiceReference(4097, 0, file_path)
            ref.setName(os.path.basename(file_path))
            ref.flags = 0

            def player_closed_callback():
                if resume_callback:
                    resume_callback()

            self.session.openWithCallback(
                player_closed_callback,
                CustomMoviePlayer,
                ref,
                self,
                file_path,
                start_position
            )

            return True

        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            return False

    def delete_all_resume_points(self, file_path):
        """Complete wipe of all resume data for a specific file"""
        try:
            self.clear_resume_point(file_path)
            self.clear_system_cuts(file_path)
            logger.info(f"All resume points deleted for: {file_path}")
        except Exception as e:
            logger.error(f"Error in delete_all_resume_points: {e}")

    # ===== RESUME POINT MANAGEMENT =====

    def get_resume_point(self, file_path):
        """Get resume point for file"""
        return self.resume_points.get(file_path)

    def save_resume_point(self, file_path, position):
        """Save resume point for file"""
        try:
            if position < 10:
                self.clear_all_resume_data(file_path)
                return

            self.resume_points[file_path] = {
                'position': position,
                'timestamp': time.time(),
                'filename': os.path.basename(file_path)
            }

            self._persist_resume_points()
            logger.info(f"Saved resume point: {position}s for {os.path.basename(file_path)}")

        except Exception as e:
            logger.error(f"Error saving resume point: {e}")

    def clear_resume_point(self, file_path):
        """Clear resume point from JSON database"""
        if file_path in self.resume_points:
            del self.resume_points[file_path]
            self._persist_resume_points()
            logger.info(f"Cleared resume point for: {file_path}")

    def clear_system_cuts(self, file_path):
        """Delete the Enigma2 system's internal .cuts file"""
        try:
            cuts_file = file_path + ".cuts"
            if os.path.exists(cuts_file):
                os.remove(cuts_file)
                logger.info(f"Deleted system cuts file: {cuts_file}")
        except Exception as e:
            logger.error(f"Error clearing system cuts: {e}")

    def clear_all_resume_data(self, file_path):
        """Wipe both systems to ensure 'Start from Beginning' works"""
        self.clear_resume_point(file_path)
        self.clear_system_cuts(file_path)

    def _load_resume_points(self):
        """Load resume points from file"""
        try:
            resume_file = "/tmp/wgfilemanager_resume.json"
            if os.path.exists(resume_file):
                with open(resume_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading resume points: {e}")
        return {}

    def _persist_resume_points(self):
        """Save resume points to file"""
        try:
            resume_file = "/tmp/wgfilemanager_resume.json"
            with open(resume_file, 'w') as f:
                json.dump(self.resume_points, f, indent=2)
        except Exception as e:
            logger.error(f"Error persisting resume points: {e}")


# ===== CUSTOM MOVIE PLAYER CLASS =====

class CustomMoviePlayer(MoviePlayer):
    def __init__(self, session, service, player_ref, file_path, start_position=0):
        self.file_path = file_path
        self.start_position = start_position
        self.player_ref = player_ref
        self.seek_done = False
        self.seek_thread = None

        if start_position == 0:
            logger.info(f"CustomMoviePlayer: FORCING start from beginning for {os.path.basename(file_path)}")

            cuts_file = file_path + ".cuts"
            if os.path.exists(cuts_file):
                try:
                    os.remove(cuts_file)
                    logger.info(f"Pre-init cleanup: {cuts_file}")
                except Exception as e:
                    logger.debug(f"Pre-init cleanup failed: {e}")

            self.read_bookmarks = False
            self.save_after_close = False
        else:
            logger.info(f"CustomMoviePlayer: Resume to {start_position}s for {os.path.basename(file_path)}")
            self.read_bookmarks = False
            self.save_after_close = False

        MoviePlayer.__init__(self, session, service)

        # Initialize hotkey manager
        self.hotkey_manager = None
        try:
            from ..core.hotkey_manager import SubtitleHotkeyManager
            self.hotkey_manager = SubtitleHotkeyManager(session, player_ref)
            logger.info("Hotkey manager initialized successfully")
        except ImportError as e:
            logger.debug(f"Hotkey manager not available: {e}")
        except Exception as e:
            logger.error(f"Error initializing hotkey manager: {e}")

        self.onClose.append(self.__cleanup)

        self["actions"] = ActionMap([
            "MoviePlayerActions",
            "OkCancelActions",
            "InfobarMenuActions",
        ], {
            "cancel": self.ask_exit,
            "exit": self.ask_exit,
            "leavePlayer": self.ask_exit,
        }, -1)

        # Color button label placeholders
        from Components.Label import Label
        self["red"] = Label("")
        self["green"] = Label("")
        self["yellow"] = Label("")
        self["blue"] = Label("")

        self.onFirstExecBegin.append(self.execute_initial_seek)

        logger.info(f"CustomMoviePlayer initialized for: {os.path.basename(file_path)}")

    def __cleanup(self):
        """Standard cleanup when player closes"""
        try:
            if self.seek_thread and self.seek_thread.is_alive():
                pass

            self.player_ref.clear_system_cuts(self.file_path)

            if self.hotkey_manager:
                self.hotkey_manager.long_press_timers.clear()

            logger.info("Player cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def execute_initial_seek(self):
        """Forces the player to stay at the chosen position without crashing"""
        if self.seek_done:
            return

        self.seek_done = True

        def brute_force_seek():
            is_start_from_beginning = (self.start_position == 0)
            target_ticks = int(self.start_position * 90000)

            if is_start_from_beginning:
                logger.warning("IMMEDIATE SEEK TO 0")
                for i in range(3):
                    try:
                        service = self.session.nav.getCurrentService()
                        if service:
                            seek = service.seek()
                            if seek:
                                seek.seekTo(0)
                                time.sleep(0.05)
                    except:
                        pass

            time.sleep(0.2 if is_start_from_beginning else 0.5)

            max_attempts = 25 if is_start_from_beginning else 8
            retry_delay = 0.1 if is_start_from_beginning else 0.3

            logger.info(f"Starting seek loop: target={self.start_position}s, attempts={max_attempts}")

            for i in range(max_attempts):
                try:
                    if not self.session or not self.session.nav:
                        logger.warning("Session/nav became invalid")
                        break

                    service = self.session.nav.getCurrentService()
                    if service:
                        seek = service.seek()
                        if seek is not None:
                            try:
                                current_pos = seek.getPlayPosition()
                                if current_pos and current_pos[1]:
                                    current_seconds = current_pos[1] / 90000
                                    if abs(current_seconds - self.start_position) < 2.0:
                                        logger.info(f"Already at target: {current_seconds:.1f}s")
                                        break
                            except:
                                pass

                            seek.seekTo(target_ticks)
                            logger.debug(f"Seek attempt {i+1}/{max_attempts}")

                            time.sleep(0.05)
                            verify_pos = seek.getPlayPosition()
                            if verify_pos and verify_pos[1]:
                                actual_seconds = verify_pos[1] / 90000
                                if abs(actual_seconds - self.start_position) < 2.0:
                                    logger.info(f"Seek verified at {actual_seconds:.1f}s on attempt {i+1}")
                                    break
                            else:
                                if i >= 5:
                                    break
                        else:
                            logger.debug(f"Seek object not ready, attempt {i+1}/{max_attempts}")
                    else:
                        logger.debug(f"Service not available, attempt {i+1}/{max_attempts}")
                except Exception as e:
                    logger.debug(f"Seek attempt {i+1} error: {e}")

                time.sleep(retry_delay)

            logger.info(f"Initial seek completed")

            if is_start_from_beginning:
                time.sleep(1.5)
                try:
                    service = self.session.nav.getCurrentService()
                    if service:
                        seek = service.seek()
                        if seek:
                            pos = seek.getPlayPosition()
                            if pos and pos[1]:
                                current = pos[1] / 90000
                                if current > 5.0:
                                    logger.error(f"STILL AT {current:.1f}s - NUCLEAR FIX")
                                    for _ in range(10):
                                        seek.seekTo(0)
                                        time.sleep(0.08)
                                    logger.warning("Applied nuclear correction")
                                else:
                                    logger.info(f"Final position: {current:.1f}s - OK")
                except Exception as e:
                    logger.debug(f"Verification error: {e}")

        self.seek_thread = threading.Thread(target=brute_force_seek, daemon=True)
        self.seek_thread.start()

    def ask_exit(self):
        """Show exit confirmation dialog"""
        self.session.openWithCallback(
            self.exit_confirmed,
            MessageBox,
            "Exit media player?\n\n(Resume point will be saved)",
            MessageBox.TYPE_YESNO
        )

    def exit_confirmed(self, confirmed):
        """Handle exit confirmation"""
        if confirmed:
            try:
                service = self.session.nav.getCurrentService()
                if service:
                    seek = service.seek()
                    if seek:
                        pos = seek.getPlayPosition()
                        if pos and pos[1] > 0:
                            position_seconds = pos[1] / 90000
                            self.player_ref.save_resume_point(self.file_path, position_seconds)

                self.session.nav.stopService()
            except Exception as e:
                logger.error(f"Exit save error: {e}")

            self.close()

    def mark_position(self):
        """Mark current position with timestamp"""
        try:
            service = self.session.nav.getCurrentService()
            if service:
                seek = service.seek()
                if seek:
                    pos = seek.getPlayPosition()
                    if pos and pos[1] > 0:
                        position_seconds = pos[1] / 90000
                        minutes = int(position_seconds // 60)
                        seconds = int(position_seconds % 60)

                        self._show_notification(
                            f"Position marked:\n{minutes}:{seconds:02d}",
                            timeout=2
                        )
                        self._save_bookmark(position_seconds)
        except Exception as e:
            logger.error(f"Error marking position: {e}")

    def show_chapter_menu(self):
        """Show chapter/jump menu"""
        try:
            jumps = [
                ("⏪ -30 seconds", -30),
                ("⏪ -10 seconds", -10),
                ("⏩ +10 seconds", 10),
                ("⏩ +30 seconds", 30),
                ("⏭️ Next minute", 60),
                ("⏮️ Previous minute", -60),
                ("📖 Chapters...", "chapters"),
            ]

            self.session.openWithCallback(
                self._handle_jump_selection,
                ChoiceBox,
                title="Jump to Position",
                list=jumps
            )

        except Exception as e:
            logger.error(f"Error showing chapter menu: {e}")

    def _handle_jump_selection(self, choice):
        """Handle jump selection"""
        if not choice:
            return

        if choice[1] == "chapters":
            self._show_chapters()
        else:
            self._jump_by_seconds(choice[1])

    def _jump_by_seconds(self, seconds):
        """Jump forward/backward by seconds"""
        try:
            service = self.session.nav.getCurrentService()
            if service:
                seek = service.seek()
                if seek:
                    pos = seek.getPlayPosition()
                    if pos and pos[1] > 0:
                        current_ticks = pos[1]
                        jump_ticks = int(seconds * 90000)
                        new_ticks = max(0, current_ticks + jump_ticks)

                        seek.seekTo(new_ticks)

                        direction = "+" if seconds > 0 else ""
                        self._show_notification(
                            f"Jumped {direction}{abs(seconds)} seconds",
                            timeout=1
                        )
        except Exception as e:
            logger.error(f"Error jumping: {e}")

    def _show_chapters(self):
        """Show chapter list if available"""
        try:
            chapters = [
                ("Chapter 1: Start", 0),
                ("Chapter 2: Intro", 60),
                ("Chapter 3: Main", 300),
                ("Chapter 4: End", 600),
            ]

            self.session.openWithCallback(
                self._handle_chapter_selection,
                ChoiceBox,
                title="Select Chapter",
                list=chapters
            )

        except Exception as e:
            logger.error(f"Error showing chapters: {e}")
            self._show_notification("No chapters found", timeout=1)

    def _handle_chapter_selection(self, choice):
        """Handle chapter selection"""
        if not choice:
            return

        seconds = choice[1]
        try:
            service = self.session.nav.getCurrentService()
            if service:
                seek = service.seek()
                if seek:
                    seek.seekTo(int(seconds * 90000))
                    self._show_notification(
                        f"Jumped to chapter:\n{choice[0]}",
                        timeout=2
                    )
        except Exception as e:
            logger.error(f"Error jumping to chapter: {e}")

    def _save_bookmark(self, position_seconds):
        """Save bookmark position"""
        try:
            bookmarks_dir = "/tmp/wgfilemanager_bookmarks/"
            os.makedirs(bookmarks_dir, exist_ok=True)

            bookmark_file = os.path.join(
                bookmarks_dir,
                f"{os.path.basename(self.file_path)}.bookmarks"
            )

            bookmarks = []
            if os.path.exists(bookmark_file):
                with open(bookmark_file, 'r') as f:
                    bookmarks = json.load(f)

            bookmarks.append({
                'position': position_seconds,
                'time': time.time(),
                'human_time': time.strftime("%H:%M:%S", time.localtime(time.time()))
            })

            if len(bookmarks) > 10:
                bookmarks = bookmarks[-10:]

            with open(bookmark_file, 'w') as f:
                json.dump(bookmarks, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving bookmark: {e}")

    def _show_notification(self, message, timeout=2):
        """Show notification message"""
        try:
            self.session.open(MessageBox, message, MessageBox.TYPE_INFO, timeout=timeout)
        except:
            pass

    def hotkey_audio_selection(self):
        """Open audio selection"""
        try:
            self.session.open(AudioSelection)
        except:
            pass

    def leavePlayer(self):
        """Ensure we call the original leave logic"""
        try:
            MoviePlayer.leavePlayer(self)
        except Exception as e:
            logger.error(f"Leave player error: {e}")


# ===== COMPATIBILITY ALIASES =====
WGFileManagerMediaPlayer = EnigmaPlayer
EnigmaMediaPlayer = EnigmaPlayer
