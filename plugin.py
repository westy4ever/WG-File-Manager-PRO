#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WG File Manager PRO v1.0 - Professional File Manager for Enigma2
Enhanced with Smart Context Menus & Remote Access
"""

import sys
import traceback
from .player.enigma_player import EnigmaMediaPlayer

# ===== ENIGMA2 IMPORTS =====
try:
    from Plugins.Plugin import PluginDescriptor  # <-- CRITICAL: This was missing!
    from Screens.MessageBox import MessageBox
except ImportError as e:
    print("[WGFileManager FATAL] Cannot import Enigma2 modules: %s" % str(e))
    print("[WGFileManager FATAL] This plugin only runs within Enigma2 environment")
    sys.exit(1)

# ===== FIX 1: Python 2 compatibility =====
PY2 = sys.version_info[0] == 2
if not PY2:
    print("[WGFileManager] WARNING: Enigma2 typically uses Python 2.7")

# ===== FIX 2: Safe translation setup =====
try:
    import language
    from Tools.Directories import resolveFilename, SCOPE_PLUGINS
    import gettext
    
    # Get language without overriding system env
    lang = language.getLanguage()[:2]
    
    # Setup translation properly
    domain = "enigma2"
    gettext.bindtextdomain(domain, resolveFilename(SCOPE_PLUGINS))
    gettext.textdomain(domain)
    
    # Create translation function
    def _(txt):
        if PY2:
            return gettext.gettext(txt).decode('utf-8')
        return gettext.gettext(txt)
        
except ImportError as e:
    print("[WGFileManager] Translation import error: %s" % str(e))
    # Fallback: no translation
    def _(txt):
        if PY2 and isinstance(txt, str):
            return txt.decode('utf-8', errors='ignore')
        return txt

# ===== FIX 3: Robust logging setup =====
try:
    # Try absolute import (installed mode)
    from Plugins.Extensions.WGFileManager.utils.logging_config import setup_logging, get_logger
    logger = get_logger(__name__)
    logger.debug("Using absolute import for logging")
    
except ImportError:
    try:
        # Try relative import (development mode)
        from .utils.logging_config import setup_logging, get_logger
        logger = get_logger(__name__)
        logger.debug("Using relative import for logging")
        
    except ImportError as e:
        # Ultimate fallback
        import logging
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='/tmp/wgfilemanager_fallback.log'
        )
        logger = logging.getLogger(__name__)
        logger.error("Failed to setup proper logging: %s" % str(e))

from Components.config import config
def main(session, **kwargs):
    """Main entry point for the plugin"""
    logger.info("=" * 50)
    logger.info("Starting WG File Manager PRO v1.0")
    logger.info("Python %s on %s" % (sys.version, sys.platform))
    
    try:
        # Initialize config to ensure all settings (like save_left_on_exit) are registered
        from Plugins.Extensions.WGFileManager.core.config import WGFileManagerConfig
        config_manager = WGFileManagerConfig()
        config_manager.setup_config()
        
        # Try to import main screen
        logger.info("Attempting to import WGFileManagerMain...")
        
        try:
            from Plugins.Extensions.WGFileManager.ui.main_screen import WGFileManagerMain
            logger.info("✓ Successfully imported WGFileManagerMain")
            
        except ImportError as ie:
            # Try relative import as fallback
            logger.warning("Absolute import failed, trying relative...")
            try:
                from .ui.main_screen import WGFileManagerMain
                logger.info("✓ Successfully imported WGFileManagerMain (relative)")
            except ImportError:
                logger.error("✗ ALL import attempts failed")
                logger.error("Import error details: %s" % str(ie))
                logger.error("Python path: %s" % str(sys.path))
                logger.error("Full traceback:\n%s" % traceback.format_exc())
                raise
        
        # Open the main screen
        logger.info("Opening WGFileManagerMain screen...")
        session.open(WGFileManagerMain)
        logger.info("✓ WGFileManager started successfully")
        
    except Exception as e:
        error_msg = "Failed to start WGFileManager: %s" % str(e)
        error_trace = traceback.format_exc()
        
        logger.error(error_msg)
        logger.error("Traceback:\n%s" % error_trace)
        
        # Show error to user
        try:
            session.open(
                MessageBox,
                _("Failed to start WGFileManager") + ":\n\n%s\n\n%s" % (
                    str(e)[:100], 
                    _("Check /tmp/wgfilemanager.log for details")
                ),
                MessageBox.TYPE_ERROR,
                timeout=10
            )
        except Exception as msg_error:
            logger.error("Could not show error message: %s" % str(msg_error))
        
        return None

def menu(menuid, **kwargs):
    """Plugin menu integration"""
    if menuid == "mainmenu":
        return [(_("WG File Manager PRO"), main, "wgfilemanager", 46)]
    return []

def Plugins(**kwargs):
    """Plugin descriptor"""
    description = _("WG File Manager PRO - Advanced File Management")
    
    # ===== FIX 4: Handle missing icon gracefully =====
    icon_path = None
    possible_icon_locations = [
        "/usr/lib/enigma2/python/Plugins/Extensions/WGFileManager/wgfilemanager.png",
        "/usr/share/enigma2/picon/wgfilemanager.png",
    ]
    
    for location in possible_icon_locations:
        try:
            import os
            if os.path.exists(location):
                icon_path = location
                logger.debug("Found icon at: %s" % location)
                break
        except:
            pass
    
    # Create plugin descriptors
    descriptors = []
    
    # Plugin menu entry
    descriptors.append(
        PluginDescriptor(
            name="WG File Manager PRO",
            description=description,
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon=icon_path,
            fnc=main
        )
    )
    
    # Main menu entry
    descriptors.append(
        PluginDescriptor(
            name="WG File Manager PRO",
            description=description,
            where=PluginDescriptor.WHERE_MENU,
            fnc=menu
        )
    )
    
    logger.info("Plugin descriptors created: %d entries" % len(descriptors))
    return descriptors

if __name__ == "__main__":
    # Test mode - only runs when executed directly
    print("=" * 50)
    print("WG File Manager PRO v1.0 - Test Mode")
    print("=" * 50)
    print("Python version: %s" % sys.version)
    print("This plugin is designed to run within Enigma2.")
    print("Install path should be: /usr/lib/enigma2/python/Plugins/Extensions/WGFileManager/")
    print("=" * 50)
    
    # Basic import test
    try:
        from utils.logging_config import get_logger
        print("✓ Can import logging_config")
    except ImportError as e:
        print("✗ Cannot import logging_config: %s" % str(e))
    
    print("Test complete.")