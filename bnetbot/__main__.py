
from bnetbot import commands, instance
from bnetbot.bot import BnetBot

import argparse
from datetime import datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apikey", help="An API key to create a bot instance with.")
    parser.add_argument("--config", help="The path to a config file to use.")
    parser.add_argument("--debug", help="Prints debugging messages.", action="store_true")

    # Parse program arguments and create the main bot instance.
    p_args = parser.parse_args()
    bot = BnetBot(p_args.config, p_args.debug)
    print("Debug mode enabled: %s" % bot.debug)

    # Create a new profile with the API key
    if p_args.apikey:
        inst = instance.BotInstance("Temp" + str(datetime.now().timestamp()).split('.')[1], {"api_key": p_args.apikey})
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
