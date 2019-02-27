
from bnetbot.capi import CapiClient
from bnetbot.commands import *
from bnetbot.database import load as load_database
from bnetbot.events import *


def raise_event(e, *args):
    if isinstance(e, PriorityDispatcher):
        e.dispatch(*args)
    elif e is not None:
        e(*args)


class BotInstance:
    def __init__(self, name, config=None):
        self.name = name or "Unnamed"
        self.config = config or {}
        self.commands = {}
        self.database = load_database(self.config)

        # Create chat client and hook events
        self.client = CapiClient(self.config.get("api_key"))
        self._hook_events(self.client)

        # Create dispatchers for relayed client events.
        self.handle_joined_chat = PriorityDispatcher()
        self.handle_user_joined = PriorityDispatcher()
        self.handle_user_update = PriorityDispatcher()
        self.handle_user_left = PriorityDispatcher()
        self.handle_user_talk = PriorityDispatcher()
        self.handle_bot_message = PriorityDispatcher()
        self.handle_whisper = PriorityDispatcher()
        self.handle_emote = PriorityDispatcher()
        self.handle_info = PriorityDispatcher()
        self.handle_error = PriorityDispatcher()

    def start(self):
        self.print("Connecting...")
        if self.client.connect():
            self.print("Connected!")
            self.client.start()

    def stop(self, force=False):
        self.print("Stopping...")
        self.client.disconnect(force)

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

    def _handle_joined_chat(self, channel, user):
        self.print("Logged on as '%s' in channel '%s'" % (user.name, channel))
        raise_event(self.handle_joined_chat, channel, user)

    def _handle_user_joined(self, user):
        raise_event(self.handle_user_joined, user)

    def _handle_user_update(self, user, flags, attributes):
        raise_event(self.handle_user_update, user, flags, attributes)

    def _handle_user_left(self, username):
        raise_event(self.handle_user_left, username)

    def _handle_user_talk(self, user, message):
        if not raise_event(self.handle_user_talk, user, message):
            return

        cmd = self.parse_command(message, user, SOURCE_PUBLIC)
        if cmd:
            self.execute_command(cmd)

    def _handle_bot_message(self, message):
        raise_event(self.handle_bot_message, message)

    def _handle_whisper(self, user, message, received):
        if not raise_event(self.handle_whisper, user, message, received):
            return

        # For our own outgoing whispers, nothing further needs to be done.
        if not received:
            return

        cmd = self.parse_command(message, user, SOURCE_PRIVATE)
        if cmd:
            self.execute_command(cmd)

    def _handle_emote(self, user, message):
        raise_event(self.handle_emote, user, message)

    def _handle_info(self, message):
        raise_event(self.handle_info, message)

    def _handle_error(self, message):
        self.print("ERROR: %s" % message)
        raise_event(self.handle_error, message)

    def _hook_events(self, client):
        if not isinstance(client, CapiClient):
            return

        client.handle_joined_chat = self._handle_joined_chat
        client.handle_user_joined = self._handle_user_joined
        client.handle_user_update = self._handle_user_update
        client.handle_user_left = self._handle_user_left
        client.handle_user_talk = self._handle_user_talk
        client.handle_bot_message = self._handle_bot_message
        client.handle_whisper = self._handle_whisper
        client.handle_emote = self._handle_emote
        client.handle_info = self._handle_info
        client.handle_error = self._handle_error
