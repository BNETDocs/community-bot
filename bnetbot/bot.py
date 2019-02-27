
from bnetbot.instance import BotInstance

from datetime import datetime
import json
from os import path
import threading
import time


class BnetBot:
    def __init__(self, config=None, debug=False):
        # Load config
        self.config_path = config or "config.json"
        if path.isfile(self.config_path):
            with open(self.config_path, "r") as fh:
                self.config = json.load(fh)
        else:
            self.config = {}
        self.debug = debug

        # Load the configured instances.
        self.instances = {}
        self.running = False
        for name, cfg in self.config.get("instances", {}).items():
            if cfg.get("enabled", True) and name.lower() not in self.instances:
                self.load_instance(BotInstance(name, cfg), False)

    def load_instance(self, inst, save=True):
        # Add to the config
        if save:
            cfg = self.config.get("instances")
            if not cfg:
                cfg = self.config["instances"] = {}
            cfg[inst.name] = inst.config

        key = inst.name.lower()
        if key not in self.instances:
            print("Loading instance: %s" % inst.name)
            inst.config["enabled"] = True
            self.instances[key] = inst
            inst.client.debug_on = self.debug

            inst.register_command("ping", "commands.internal.ping", lambda c: c.respond("pong"))
            inst.register_command("whoami", "commands.internal.whoamai",
                                  lambda c: c.respond("You are the bot console." if c.is_console() else
                                                      "You are %s. Flags: %s, Attributes: %s, Groups: %s" % (
                                                         c.user.name, c.user.flags, c.user.attributes,
                                                         [g.name for g in inst.database.user(c.user.name).groups.values()])
                                                      ))
        else:
            raise Exception("An instance with that name is already loaded.")

        if self.running:
            inst.start()
        return inst

    def start(self):
        # Start the loaded instances.
        self.running = True
        for inst in self.instances.values():
            inst.start()

    def stop(self):
        self.running = False

        # Disconnect and stop the loaded instances.
        for inst in self.instances.values():
            inst.stop()

        # Save the config
        with open(self.config_path, "w") as fh:
            json.dump(self.config, fh)
