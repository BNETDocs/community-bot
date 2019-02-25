
from bnetbot import bot, commands
import json
import os
import sys


CONFIG_FILE = "config.json"

# Check for a config file
config = None
if os.path.isfile(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as fh:
        config = json.load(fh)
else:
    # Use supplied command-line argument or prompt user for API key.
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = input("Enter your API key: ")

    config = {
        "instances": {
            "Main": {
                "api_key": api_key
            }
        }
    }

    # Save the config
    with open(CONFIG_FILE, "w") as fh:
        json.dump(config, fh, sort_keys=True, indent=4)

# Create the client and register commands
bots = []
for name, inst_config in config.get("instances", {}).items():
    print("Loading instance: %s" % name)
    bot = bot.BotInstance(name, inst_config)
    bot.register_command("ping", "commands.internal.ping", lambda c: c.respond("pong"))
    bot.register_command("whoami", "commands.internal.whoami",
                         lambda c: c.respond("You are the bot console." if c.is_console() else
                                             "You are %s. Flags: %s, Attributes: %s, Groups: %s" % (
                                                c.user.name, c.user.flags, c.user.attributes,
                                                [g.name for g in bot.database.user(c.user.name).groups.values()])
                                             )
                         )

    # Start and connect the bot.
    bot.start()
    bots.append(bot)

# If more than one instance is defined, only allow quit command.
if len(bots) > 1:
    while True:
        if input() != "/quit":
            print("Local commands are not supported when more than one instance is running.")
        else:
            for bot in bots:
                bot.stop()
            print("All connections closed.")
            sys.exit(0)

# Handle user input for single-instance mode.
client = bot.client
while client.connected():
    ip = input()
    if ip[0] == '/' and len(ip) > 1:
        args = ip.split()
        cmd = args[0][1:].lower()

        if cmd == "quit":
            client.disconnect(True)
        elif cmd in ["w", "whisper", "m", "msg"]:
            if len(args) > 2:
                client.chat(' '.join(args[2:]), args[1])
            else:
                client.error("Invalid syntax, use: /%s <user> <message>" % args[0])
        elif cmd in ["me", "emote"]:
            if len(args) > 1:
                client.chat(' '.join(args[1:]), client.username)
            else:
                client.error("Invalid syntax, use /%s <message>" % args[0])
        elif cmd == "ban":
            if len(args) > 1:
                client.ban(args[1])
            else:
                client.error("Invalid syntax, use /ban <user>")
        elif cmd == "unban":
            if len(args) > 1:
                client.unban(args[1])
            else:
                client.error("Invalid syntax, use /unban <user>")
        elif cmd == "kick":
            if len(args) > 1:
                client.ban(args[1], True)
            else:
                client.error("Invalid syntax, use /kick <user>")
        elif cmd in ["op", "designate"]:
            if len(args) > 1:
                client.set_moderator(args[1])
            else:
                client.error("Invalid syntax, use /%s <user>" % args[0])
        else:
            inst = bot.parse_command(ip, None, commands.SOURCE_LOCAL)
            if inst:
                bot.execute_command(inst)
            else:
                client.error("Unrecognized command.")
    else:
        client.chat(ip)

print("All connections closed.")
