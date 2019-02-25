

# Command instance sources
SOURCE_PUBLIC = 1       # In channel
SOURCE_PRIVATE = 2      # From whisper
SOURCE_LOCAL = 3        # In bot console
SOURCE_INTERNAL = 4     # Automatic execution


class CommandDefinition:
    def __init__(self, command, permission, callback):
        self.name = command
        self.permission = permission
        self.callback = callback


class CommandInstance:
    def __init__(self, command, args=None, user=None, source=None):
        self.command = command
        self.args = args or []
        self.user = user
        self.source = source or SOURCE_INTERNAL
        self.response = []
        self.bot = None
        self.has_permission = self.is_console()

    def respond(self, text):
        if self.source == SOURCE_LOCAL:
            self.bot.print(text)
        else:
            self.bot.send(text, self.user if self.source == SOURCE_PRIVATE else None)

    def is_console(self):
        return self.source in [SOURCE_LOCAL, SOURCE_INTERNAL]
