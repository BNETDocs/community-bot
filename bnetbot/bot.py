
from bnetbot.capi import CapiClient
from bnetbot.commands import *
from bnetbot.database import load as load_database


class BotInstance:
    def __init__(self, name, config=None):
        self.name = name or "Unnamed"
        self.config = config or {}
        self.commands = {}
        self.database = load_database(self.config)

        self.client = CapiClient(self.config.get("api_key"))
        self.client.handle_joined_chat = lambda c, u: self.print("Entered chat as '%s' in channel '%s'" % (u.name, c))
        self.client.handle_user_joined = lambda u: self.print("%s has joined." % u.name)
        self.client.handle_user_left = lambda u: self.print("%s has left." % u.name)
        self.client.handle_user_talk = self._handle_user_talk
        self.client.handle_bot_message = self._handle_bot_message
        self.client.handle_whisper = self._handle_whisper
        self.client.handle_emote = lambda u, m: self.print("<%s %s>" % (u.name, m))
        self.client.handle_info = lambda m: self.print("INFO: %s" % m)
        self.client.handle_error = lambda m: self.print("ERROR: %s" % m)

    def start(self):
        self.print("Connecting...")
        if self.client.connect():
            self.print("Connected!")
            self.client.start()

    def stop(self):
        self.print("Stopping...")
        self.client.disconnect()

    def print(self, text):
        print("[%s] %s" % (self.name, text))

    def send(self, message, target=None):
        lines = message.replace('\r', '').split('\n')
        for line in lines:
            self.client.chat(line, target)

    def register_command(self, command, permission, callback):
        self.commands[command.lower()] = CommandDefinition(command, permission, callback)

    def parse_command(self, message, user=None, source=None):
        source = source or SOURCE_INTERNAL
        trigger = "/" if source in [SOURCE_LOCAL, SOURCE_INTERNAL] else self.config.get("trigger", "!")

        # Check for the correct trigger
        if message.startswith(trigger) and len(message) > len(trigger):
            args = message.split()
            cmd = args[0][len(trigger):]
            args = args[1:] if len(args) > 1 else []
            return CommandInstance(cmd, args, user, source)
        else:
            return None     # Not a valid command

    def execute_command(self, instance):
        command = self.commands.get(instance.command.lower())
        user = self.database.user(instance.user.name)
        if command:
            instance.bot = self
            if command.permission is None or \
                    (user is not None and user.check_permission(command.permission)):
                instance.has_permission = True
                command.callback(instance)
            return instance

    def _handle_user_talk(self, user, message):
        self.print("<%s> %s" % (user.name, message))

        cmd = self.parse_command(message, user, SOURCE_PUBLIC)
        if cmd:
            self.execute_command(cmd)

    def _handle_bot_message(self, message):
        self.print("<%s> %s" % (self.client.username, message))

    def _handle_whisper(self, user, message, received):
        self.print("<%s %s> %s" % ("From" if received else "To", user.name, message))
        if not received:
            return

        cmd = self.parse_command(message, user, SOURCE_PRIVATE)
        if cmd:
            self.execute_command(cmd)
