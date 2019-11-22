
from .database import DatabaseItem

from datetime import datetime


# Command instance sources
SOURCE_PUBLIC = 1       # In channel
SOURCE_PRIVATE = 2      # From whisper
SOURCE_LOCAL = 3        # In bot console
SOURCE_INTERNAL = 4     # Automatic execution


class CommandDefinition:
    """Object linking a command name with its required permissions and function."""
    def __init__(self, command, permission, callback):
        self.name = command
        self.permission = permission
        self.callback = callback


class CommandInstance:
    """A request to execute a command.

        command: the name of the command
        args: a list of supplied command arguments
        source: the context from where the command was executed
        trigger: the trigger character or phrase used
        bot: the bot instance where the command was triggered
    """
    def __init__(self, command, bot, args=None, source=None, trigger=None):
        self.command = command
        self.args = args or []
        self.source = source or SOURCE_INTERNAL
        self.trigger = trigger
        self.response = []
        self.bot = bot
        self.user = None

    def respond(self, text=None):
        """Sends the response text to the command source."""
        if text:
            self.response.append(text)

        if len(self.response) == 0:
            raise Exception("Attempted to send empty command response. Command: %s, User: %s" %
                            (self.command, self.user.name))

        if self.source == SOURCE_LOCAL:
            for msg in self.response:
                print(msg)
        else:
            self.bot.send(self.response, self.user.name if self.source == SOURCE_PRIVATE else None)

    def is_console(self):
        """Returns if the command was executed from the bot console or internally."""
        return self.source in [SOURCE_LOCAL, SOURCE_INTERNAL]


class AdminCommands:
    def __init__(self):
        self.commands = [
            ("perms", "commands.admin.perms", AdminCommands.perms)
        ]

    @staticmethod
    def perms(c):
        """Manages database permissions for the bot instance."""
        syntax = "<group|user> <target> <add|remove|set> [value|permission] [allow|deny]"
        invalid_syntax_message = "Invalid syntax: %s%s %s" % (c.trigger, c.command, syntax)

        if len(c.args) < 3 or len(c.args) > 5:
            return c.respond(invalid_syntax_message)

        item_type = c.args[0].lower()
        target = c.args[1]
        oper = c.args[2].lower()
        value = c.args[3] if len(c.args) > 3 else None
        allow = c.args[4].lower() if len(c.args) > 4 else None

        # Verify type, operation, and allow/deny
        if item_type not in ["group", "user"] or oper not in ["add", "remove", "set"]:
            return c.respond(invalid_syntax_message)
        elif allow and allow not in ["true", "allow", "false", "deny", "none"]:
            return c.respond(invalid_syntax_message)

        db = c.bot.database
        item = db.user(target) if item_type == "user" else db.group(target)

        if oper == "remove":
            if not item:
                return c.respond("Target database item not found.")

            if value is None:
                # Remove the target from the database
                db.remove(item)
                c.respond("Removed %s '%s' from the database." % (item_type, item.name))
            elif allow is None and allow != "none":
                # Remove group from user. The correct way to call this is '/perm group <group> remove <user>', but
                #   it can also be called from the user as '/perm user <user> remove <group>'
                if item_type == "user":
                    user = item
                    item = db.group(value)
                    if not item:
                        return c.respond("Group '%s' not found." % value)
                else:
                    user = db.user(value)
                    if not item:
                        return c.respond("User '%s' not found." % value)

                key = item.name.lower()
                if key in user.groups:
                    del user.groups[key]
                    c.respond("Removed user '%s' from group '%s'." % (user.name, item.name))
                else:
                    c.respond("User '%s' is not a member of group '%s'." % (user.name, item.name))
            else:
                # Remove permission from user or group.
                if value.lower() in item.permissions:
                    del item.permissions[value.lower()]
                    c.respond("Removed permission '%s' from %s '%s'." % (value.lower(), item_type, item.name))
                else:
                    c.respond("%s '%s' does not have that permission. It may be inherited from a group or wildcard." %
                              (item_type.title(), item.name))
        elif oper == "add" and allow is None:
            # Adding a user to a group
            if item_type == "user":
                user = item
                item = db.group(value)
            else:
                user = db.user(value)
                if not user:
                    user = DatabaseItem(value, False)

            if not item:
                return c.respond("Group '%s' not found." % value)
            elif not db.user(user.name):
                # Add the user to the database.
                db.add(user)

            key = item.name.lower()
            if key in user.groups:
                c.respond("User '%s' is already a member of group '%s'." % (user.name, item.name))
            else:
                user.groups[key] = item
                c.respond("Added user '%s' to group '%s'." % (user.name, item.name))
        else:
            # Adding or setting permission for user or group.
            if not item:
                # This user isn't in the database, so add them.
                item = db.add(DatabaseItem(target, False))
            else:
                item.modified = datetime.now()
                item.modified_by = c.user.name

            allow = allow in [None, "true", "allow"]
            item.permissions[value.lower()] = allow
            c.respond("Set permission '%s' for %s '%s' to '%s'." %
                      (value.lower(), item_type, item.name, "ALLOW" if allow else "DENY"))

        # Save changes to the config
        c.bot.save()


class InternalCommands:
    def __init__(self):
        self.commands = [
            ("ping", "commands.internal.ping", InternalCommands.ping),
            ("time", "commands.internal.time", InternalCommands.time),
            ("uptime", "commands.internal.uptime", InternalCommands.uptime),
            ("whoami", "commands.internal.whoami", InternalCommands.whoami),
            ("whois", "commands.internal.whois", InternalCommands.whois)
        ]

    @staticmethod
    def ping(c):
        """Checks if the bot is alive and responsive."""
        c.respond("pong")

    @staticmethod
    def time(c):
        """Gets the bot's local time."""
        c.respond("Local time: %s" % datetime.now().strftime("%A, %B %w %Y at %I:%M %p"))

    @staticmethod
    def uptime(c):
        """Gets the time since the bot connected."""
        seconds = int(c.bot.uptime.total_seconds())
        hours, rem = divmod(seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        days, hours = divmod(hours, 24)

        c.respond("Connection uptime: %i days, %i hours, %i minutes, %i seconds (since %s UTC)" %
                  (days, hours, minutes, seconds, c.bot.client.uptime .strftime("%a, %b %w %Y at %I:%M %p")))

    @staticmethod
    def whoami(c):
        """Identifies the user issuing the command."""
        if c.is_console():
            c.respond("You are the bot console%s" %
                      (", in chat as '%s'." % c.bot.client.username) if c.bot.client.connected() else ".")
        else:
            # This command is equivalent to '/whois <user>' for the user issuing the command
            c.command = "whois"
            c.args = [c.user.name]
            InternalCommands.whois(c)

    @staticmethod
    def whois(c):
        """Identifies a user."""
        if len(c.args) != 1:
            return c.respond("Invalid syntax: %s%s <user>" % (c.trigger, c.command))

        target = c.args[0]
        ch_user = c.bot.client.get_user(target)
        db_user = c.bot.database.user(target)

        if ch_user and ch_user.name.lower() == c.bot.client.username.lower():
            c.respond("That's me!")
        else:
            if ch_user is None and db_user is None:
                c.respond("User not found.")
            elif db_user is None:
                # User in the channel but not in the database.
                c.respond("Found '%s' in the channel with flags %s and attributes %s." %
                          (ch_user.name, ch_user.flags, ch_user.attributes))
            else:
                # User is in the database.
                perms = len(db_user.get_permissions())
                groups = db_user.group_list()

                if ch_user is None:
                    # User in database but not the channel.
                    c.respond("Found '%s' in the database with groups %s and %i permission(s)." %
                              (db_user.name, groups, perms))
                else:
                    # User both in the channel and database.
                    c.response.append("Found '%s' in the channel with flags %s, attributes %s, and in the database " %
                                      (ch_user.name, ch_user.flags, ch_user.attributes))
                    c.response[0] += "with groups %s and %i permission(s)." % (groups, perms)
                    c.respond()


class ModerationCommands:
    def __init__(self):
        self.commands = [
            ("ban", "commands.moderation.ban", ModerationCommands.ban),
            ("designate", "commands.moderation.designate", ModerationCommands.designate),
            ("kick", "commands.moderation.kick", ModerationCommands.kick),
            ("unban", "commands.moderation.unban", ModerationCommands.unban)
        ]

    @staticmethod
    def ban(c):
        """Bans one or more users from the channel."""
        failed = []
        for target in c.args:
            if not c.bot.client.ban(target, False):
                failed.append(target)
        if len(failed) > 0:
            c.respond("Failed to ban %i users not found in channel." % len(failed))

    @staticmethod
    def designate(c):
        """Designates another user to be a channel operator."""
        if len(c.args) != 1:
            c.respond("Invalid syntax: %s%s <user>" % (c.trigger, c.command))
        elif not c.bot.client.set_moderator(c.args[0]):
            c.respond("Moderator designation failed - user '%s' not found." % c.args[0])

    @staticmethod
    def kick(c):
        """Kicks one or more users from the channel."""
        failed = []
        for target in c.args:
            if not c.bot.client.ban(target, True):
                failed.append(target)
        if len(failed) > 0:
            c.respond("Failed to kick %i users not found in channel." % len(failed))

    @staticmethod
    def unban(c):
        """Unbans one or more users from the channel."""
        for target in c.args:
            c.bot.client.unban(target)


DEFINED_COMMANDS = AdminCommands().commands + InternalCommands().commands + ModerationCommands().commands
