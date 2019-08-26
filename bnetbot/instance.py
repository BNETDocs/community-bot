
from .capi import CapiClient
from .commands import *
from .database import UserDatabase

import logging


class BotInstance:
    def __init__(self, name, config=None):
        self.name = name or "Unnamed"
        self.config = config or {}
        self.commands = {}
        self.database = UserDatabase.load(self.config)

        self.log = logging.getLogger("bnetbot." + self.name)
        if "log_level" in self.config and self.log.getEffectiveLevel() != logging.DEBUG:
            # If a custom log level is defined and we aren't in debug mode, use the configured level.
            self.log.setLevel(self.config["log_level"])

        # Create chat client and hook events
        self.client = CapiClient(self.config.get("api_key"))
        self.client.hook(self)

    def start(self):
        self.log.debug("Connecting to CAPI endpoint '%s' ..." % self.client.endpoint)
        if self.client.connect():
            self.log.debug("Connection established!")

    def stop(self, force=False):
        self.log.debug("Shutting down instance...")
        self.client.disconnect(force)
        self.database.save(self.config)

    def send(self, message, target=None):
        lines = message.replace('\r', '').split('\n') if isinstance(message, str) else message
        for line in lines:
            self.client.chat(line, target)

    def register_command(self, command, permission, callback):
        self.commands[command.lower()] = CommandDefinition(command, permission, callback)

    def parse_command(self, message, source=None):
        source = source or SOURCE_INTERNAL
        trigger = "/" if source in [SOURCE_LOCAL, SOURCE_INTERNAL] else self.config.get("trigger", "!")

        # Check for the correct trigger
        if message.startswith(trigger) and len(message) > len(trigger):
            args = message.split()
            cmd = args[0][len(trigger):]
            args = args[1:] if len(args) > 1 else []
            return CommandInstance(cmd, args, source, trigger, self)
        else:
            return None     # Not a valid command

    def execute_command(self, instance, run_as=None):
        if not run_as and instance.user:
            user = self.database.user(instance.user.name)
        elif isinstance(run_as, str):
            user = self.database.user(run_as)
        elif run_as and not isinstance(run_as, DatabaseItem):
            raise TypeError("Commands can only be run as a DatabaseItem object.")
        else:
            user = run_as

        instance.user = user
        command = self.commands.get(instance.command.lower())

        if command:
            self.log.info("Attempting to run command '%s' as user '%s' with arguments: %s." %
                          (instance.command, user.name if user else run_as, instance.args))

            if command.permission is None or (user and user.check_permission(command.permission)):
                command.callback(instance)
            elif user:
                instance.respond("You do not have permission to use that command.")
                self.log.warning("Access denied for user '%s' - missing required permission: %s." %
                                 (user.name, command.permission))
            else:
                self.log.warning("Access denied for user '%s' - no permissions" % run_as)
        else:
            instance.respond("Unrecognized command.")
        return instance

    def _handle_joined_chat(self, client, channel, user):
        self.log.info("Logged on as '%s' in channel '%s'" % (user.name, channel))

    def _handle_user_talk(self, client, user, message):
        cmd = self.parse_command(message, SOURCE_PUBLIC)
        if cmd:
            self.execute_command(cmd, user.name)

    def _handle_whisper_received(self, client, user, message):
        cmd = self.parse_command(message, SOURCE_PRIVATE)
        if cmd:
            self.execute_command(cmd, user.name)

    def _handle_left_chat(self, client):
        self.log.warning("Disconnected from chat.")

    def _handle_client_error(self, client, error):
        self.log.error("Client error: %s", error.message)

    def _handle_protocol_message_received(self, client, data):
        self.log.debug("Received message: %s", data)

    def _handle_protocol_message_sent(self, client, data):
        self.log.debug("Sent message: %s", data)
