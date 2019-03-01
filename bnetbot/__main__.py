
from bnetbot import commands, instance
from bnetbot.bot import BnetBot
from bnetbot.events import *

import argparse
import atexit
from datetime import datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apikey", help="An API key to create a bot instance with.")
    parser.add_argument("--config", help="The path to a config file to use.")
    parser.add_argument("--debug", help="Prints debugging messages.", action="store_true")

    # Parse program arguments and create the main bot instance.
    p_args = parser.parse_args()
    should_load = p_args.apikey is None         # Only load instances if no API key given.
    bot = BnetBot(p_args.config, p_args.debug, should_load)

    # Clean shutdown the bot on termination
    def shutdown(b):
        print("Shutting down...")
        if b.running:
            b.stop(True)
    atexit.register(shutdown, bot)

    print("Debug mode enabled: %s" % bot.debug)

    # If an API key is given in the command-line args, create+run a profile with that key only.
    if p_args.apikey:
        inst = None

        # Find an instance with a matching API key
        instances = bot.config.get("instances", {})
        for name, cfg in instances.values():
            if cfg.get("api_key").lower() == p_args.apikey.lower():
                inst = instance.BotInstance(name, cfg)
                break

        # If no matching instance was found, create a new one.
        if inst is None:
            time_based_number = str(datetime.now().timestamp()).split('.')[1]
            instance_name = ("Temp" + time_based_number) if len(instances) > 0 else "Main"
            print("Creating instance: %s" % instance_name)
            inst = instance.BotInstance(instance_name, {"api_key": p_args.apikey})

            def handle_first_login(c, u):
                # If name has already been changed, ignore.
                if not inst.name.startswith("Temp"):
                    return

                # Update the instance name to a more friendly one.
                old_name = inst.name
                new_name = base_name = c.title().replace(' ', '')
                modifier = 2
                while new_name.lower() in instances:
                    new_name = base_name + str(modifier)
                    modifier += 1
                inst.name = new_name

                # Remove the old one and assign the new
                print("Updating instance name for '%s' to '%s'." % (old_name, new_name))
                del instances[old_name]
                instances[inst.name] = inst.config
                bot.config["instances"] = instances

            inst.handle_joined_chat.register(handle_first_login, PRIORITY_HIGH)     # Update name on login

        # Load the instance.
        bot.load_instance(inst)

    if len(bot.instances) == 1:
        # Only one instance is running, so make it interactive.
        inst = list(bot.instances.values())[0]
        print("Only one profile loaded - running in interactive mode")

        inst.handle_user_joined.register(lambda u: inst.print("%s has joined." % u.name))
        inst.handle_user_left.register(lambda u: inst.print("%s has left." % u.name))
        inst.handle_user_talk.register(lambda u, m: inst.print("<%s> %s" % (u.name, m)))
        inst.handle_bot_message.register(lambda m: inst.print("<%s> %s" % (inst.client.username, m)))
        inst.handle_whisper.register(
            lambda u, m, r: inst.print("<%s %s> %s" % ("From" if r else "To", u.name, m)))
        inst.handle_emote.register(lambda u, m: inst.print("<%s %s>" % (u.name, m)))
        inst.handle_info.register(lambda m: inst.print("INFO: %s" % m))

        bot.start()
        client = inst.client
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
                else:
                    obj = inst.parse_command(ip, commands.SOURCE_LOCAL)
                    if obj:
                        inst.execute_command(obj, "%root%")   # Run as root
            else:
                client.chat(ip)
    else:
        print("Loaded %i profiles - running in limited mode" % len(bot.instances))

        bot.start()
        while bot.running:
            if input() != "/quit":
                print("Local commands are not supported when more than one instance is running.")
            else:
                bot.stop()

    print("All connections closed.")


if __name__ == "__main__":
    main()
