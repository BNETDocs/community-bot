
from bnetbot import capi

import sys


if len(sys.argv) > 1:
    api_key = sys.argv[1]
else:
    api_key = input("Enter your API key: ")

# Create the client and setup event handlers
client = capi.CapiClient(api_key)
client.debug_on = True
client.handle_joined_chat = lambda c, u: print("Entered chat as '%s' in channel '%s'" % (u.name, c))
client.handle_user_joined = lambda u: print("%s has joined." % u.name)
client.handle_user_left = lambda u: print("%s has left." % u.name)
client.handle_user_talk = lambda u, m: print("<%s> %s" % (u.name, m))
client.handle_whisper = lambda u, m, r: print("<%s %s> %s" % ("From" if r else "To", u.name, m))
client.handle_emote = lambda u, m: print("<%s %s>" % (u.name, m))
client.handle_info = lambda m: print("INFO: %s" % m)
client.handle_error = lambda m: print("ERROR: %s" % m)

# Connect.
print("Connecting...")
if client.connect():
    print("Connected!")
    client.start()
else:
    sys.exit(1)

# Process input while connected
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
            client.error("Unrecognized commands. Try: quit, msg, emote, ban, unban, kick, designate")
    else:
        client.chat(ip)

print("Disconnected.")
