
from .commands import DEFINED_COMMANDS
from .instance import BotInstance

from datetime import datetime
import json
import logging
from os import path
import threading
import time


class BnetBot:
    def __init__(self, config=None, auto_load=True):
        self.log = logging.getLogger("bnetbot")

        # Load config
        self.config_path = config or "config.json"
        if path.isfile(self.config_path):
            with open(self.config_path, "r") as fh:
                self.config = json.load(fh)
        else:
            self.config = {}

        if self.config:
            self.log.debug("Config loaded: %s", self.config_path)
        else:
            self.log.debug("Config not found. Using defaults.")
        self.log.info("Global logging level set to: %s", logging.getLevelName(self.log.getEffectiveLevel()))

        # Load the configured instances.
        self.instances = {}
        self.running = False
        if auto_load:
            self.log.debug("Loading startup instances...")
            for name, cfg in self.config.get("instances", {}).items():
                if cfg.get("enabled", True) and name.lower() not in self.instances:
                    self.load_instance(BotInstance(name, cfg), False)

        # Create a connectivity monitoring thread
        self.monitor = threading.Thread(target=self._run_monitor)
        self.monitor.setDaemon(True)

    def load_instance(self, inst, save=True):
        if save:
            # Save the instance's config (used when creating new instances).
            cfg = self.config.get("instances")
            if not cfg:
                cfg = self.config["instances"] = {}
            cfg[inst.name] = inst.config

        key = inst.name.lower()
        if key not in self.instances:
            self.log.info("Loading instance: %s" % inst.name)
            inst.config["enabled"] = True
            self.instances[key] = inst

            # Register internally defined commands
            for command, permission, callback in DEFINED_COMMANDS:
                inst.register_command(command, permission, callback)
        else:
            raise Exception("An instance with that name is already loaded.")

        if self.running:
            inst.start()
        return inst

    def start(self):
        self.log.debug("Starting bot instances...")
        # Start the loaded instances.
        self.running = True
        for inst in self.instances.values():
            inst.start()

        # Start the connection monitor
        self.monitor.start()

    def stop(self, force=False):
        self.log.debug("Stopping bot instances (force: %s)...", force)
        self.running = False

        # Disconnect and stop the loaded instances.
        for inst in self.instances.values():
            inst.stop(force)

        self.save_config()

    def save_config(self, save_path=None):
        """Saves the bot config to disk."""
        with open(save_path or self.config_path, "w") as fh:
            json.dump(self.config, fh, sort_keys=True, indent=4)

    def _run_monitor(self):
        """ Checks each client at the configured interval. If no messages have been received since the last check,
          send a client ping (which should trigger a response). If still no message is received by the following
          check, forcibly reconnect the client.
        """

        connecting_instances = []
        keep_alive_interval = self.config.get("keep_alive", 10)
        while self.running:
            now = datetime.now()
            for inst in self.instances.values():
                # Check for inactive or offline clients
                last = inst.client.last_message
                diff = (now - last).total_seconds() if last else keep_alive_interval

                if diff >= (keep_alive_interval * 2) or not inst.client.connected():
                    if inst not in connecting_instances:
                        self.log.warning("Monitor has detected instance '%s' as down - attempting to reconnect..." % inst.name)
                        connecting_instances.append(inst)
                        inst.client.disconnect(True)

                    # Reconnect the client
                    if inst.client.connect():
                        self.log.info("Connection successful. Resuming...")
                        connecting_instances.remove(inst)
                elif diff >= keep_alive_interval and inst.client.connected():
                    # Send a ping
                    inst.client.ping(str(now))

            time.sleep(1)
