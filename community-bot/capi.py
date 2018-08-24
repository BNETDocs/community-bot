
import ssl, json, websocket, sys
from threading import Thread

status_codes = {
    0: {
        0: None     # Success
    },
    6: {
        5: "Request timed out",
        8: "Hit rate limit"
    },
    8: {
        1: "Not connected to chat",
        2: "Bad request"
    }
}

class capi_client(object):
    def __init__(self, api_key, id=None, endpoint=None):
        self.api_key = api_key
        self.client_id = id         # Unique name or identifier for this client instance.
        self.endpoint = endpoint or "wss://connect-bot.classic.blizzard.com/v1/rpc/chat"

        self.debug_mode = False     # Set to True to print debugging information (packets, commands, etc)
        self.hide_chat = False      # Set to True to hide chat messages.
        self.hide_channel = False   # Set to True to hide user join, leave, and update messages.

        self.connected = False
        self.channel = None         # The name of the current chat channel, or None if not in one.
        self.last_request_id = 0    # The ID of the last request sent.

        self.handlers = {           # Message received handlers
            "Botapiauth.AuthenticateResponse": self.__handle_auth_response,
            "Botapichat.ConnectResponse": self.__handle_connect_response,
            "Botapichat.ConnectEventRequest": self.__handle_connect_event,
            "Botapichat.DisconnectRequest": self.__handle_disconnect_response,
            "Botapichat.DisconnectEventRequest": self.__handle_disconnect_event,
            "Botapichat.UserUpdateEventRequest": self.__handle_user_update_event,
            "Botapichat.UserLeaveEventRequest": self.__handle_user_leave_event,
            "Botapichat.MessageEventRequest": self.__handle_message_event,
            "Botapichat.SendMessageResponse": self.__handle_send_message_event,
            "Botapichat.SendWhisperResponse": self.__handle_send_whisper_response,
            "Botapichat.SendEmoteResponse": self.__handle_send_emote_response
        }

        self.open_requests = { }    # Tracks sent messages that haven't received a response.
        self.users = { }            # Maps user ID's to toon names
        self.received_users = False # True if the entire list of present users should've been received.

        self.socket = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_OPTIONAL})
        self.thread = Thread(target = self.__receive)

    def get_toon_name(self, user_id):
        return self.users[user_id]["toon_name"] if user_id in self.users else None

    def get_user_id(self, toon_name):
        for id, name in self.users.items():
            if name["toon_name"].lower() == toon_name.lower():
                return id
        return None

    def connect(self):
        self.__print("Connecting to %s ..." % self.endpoint)
        self.socket.connect(self.endpoint)
        self.connected = True
        self.__print("Connected. Authenticating ...")

        # Send the API key to authenticate
        self.send_command("Botapiauth.AuthenticateRequest", { "api_key": self.api_key })

        # Start receiving messages.
        self.thread.start()

    def disconnect(self, force=False):
        self.send_command("Botapichat.DisconnectRequest")

        if force:
            self.__disconnect_internal()
            self.__print("Connection forcibly closed.")

    def send_command(self, command, payload=None):
        id = self.last_request_id = (self.last_request_id + 1)

        # Build the header
        msg = {
            "command": command,         # Name of the command
            "request_id": id,           # Unique ID for the message
            "payload": payload or { }   # Message contents (optional)
        }

        # Send the message
        self.socket.send(json.dumps(msg), websocket.ABNF.OPCODE_TEXT)
        if self.debug_mode:
            self.__print("DEBUG - SENT: %s" % msg)

        # Add the message to be tracked.
        self.open_requests[id] = msg
        return id

    def send_chat(self, message):
        return self.send_command("Botapichat.SendMessageRequest", { "message": message })

    def send_emote(self, text):
        return self.send_command("Botapichat.SendEmoteRequest", { "message": text })

    def send_whisper(self, message, toon_name=None, user_id=None):
        id = user_id if user_id else self.get_user_id(toon_name)
        return self.send_command("Botapichat.SendWhisperRequest", { "message": message, "user_id": id }) if id > 0 else False


    def __print(self, text):
        print((("[%i] " % self.client_id) if self.client_id else '') + text)

    def __disconnect_internal(self):
        self.socket.close()
        self.connected = False
        self.channel = None
        self.users = { }
        self.open_requests = { }

    def __receive(self):
        global status_codes

        while self.socket.connected:
            msg = self.socket.recv()
            if self.debug_mode:
                self.__print("DEBUG - RECV: %s" % msg)

            obj = json.loads(msg)

            # Verify the message was decoded successfully.
            if not (obj and isinstance(obj, dict)):
                self.__print("ERROR: Received message could not be decoded. (%s)" % type(obj))
            else:
                # Parse the message
                id = obj.get("request_id", -1)
                command = obj.get("command")
                status = obj.get("status")
                payload = obj.get("payload")

                # If a status code was received, parse it, look it up, and replace it with the string form.
                if status:
                    area = status.get("area")
                    code = status.get("code")

                    status = status_codes.get(area)
                    status = status and status.get(code)
                    if not status:
                        status = "Unknown (%i-%i)" % (area, code)

                # Find the request associated with this response, if there should be one.
                request = None
                if not "Event" in command:
                    if id in self.open_requests:
                        request = self.open_requests[id].get("payload")
                        del self.open_requests[id]
                    else:
                        self.__print("NOTICE! Received an unexpected response to a request that wasn't tracked - ID: %i, Command: %s" % (id, command))

                # Find a handler for this command and pass off the payload.
                if command in self.handlers:
                    self.handlers[command](request, payload, status)
                else:
                    self.__print("Received unsupported server command: %s" % command)


    # Message handlers
    def __handle_auth_response(self, request, payload, status):
        if status:
            self.__print("Authentication failed: %s" % status)
        else:
            self.__print("Authentication successful.")

            self.send_command("Botapichat.ConnectRequest")

    def __handle_connect_response(self, request, payload, status):
        if status:
            self.__print("Chat connection failed: %s" % status)
        else:
            self.__print("Connected to chat.")

    def __handle_connect_event(self, request, payload, status):
        self.channel = payload.get("channel")
        if not self.channel:
            self.__print("ERROR! Received connect event with no channel name.")
        else:
            if not self.hide_channel: self.__print("Joined channel: %s" % self.channel)

    def __handle_disconnect_response(self, request, payload, status):
        self.__print("Connection closed.")
        self.__disconnect_internal()

    def __handle_disconnect_event(self, request, payload, status):
        if status: self.__print("Disconnected: %s" % status)
        self.__print("Server closed the connection.")
        self.__disconnect_internal()

    def __handle_user_update_event(self, request, payload, status):
        user_id = payload.get("user_id", -1)
        toon_name = payload.get("toon_name")

        # Are we in a channel?
        if not self.channel:
            # We aren't in a channel so this is our identity.
            self.__print("You are identified as '%s'." % toon_name)
        else:
            if not self.hide_channel:
                # Is this user already in the channel?
                if user_id in self.users:
                    # Does this update have new information?
                    if self.users[user_id] != payload:
                        # The only update I'm aware of is flags so if that's there, show it.
                        if "flag" in payload:
                            old = self.users[user_id].get("flag", [])
                            new = [ f for f in payload.get("flag") if not f in old ]
                            self.__print("'%s' has been given flag(s): %s" % (toon_name, ', '.join(new)))
                    elif user_id == 1:
                        # It's us, so we should've received all the present users by now.
                        self.__print("Users in channel: %s" % ', '.join([ self.get_toon_name(u) for u in self.users.keys() ]))
                        self.received_users = True
                else:
                    # Only show the join message if we've already received our own join event.
                    if self.received_users:
                        self.__print("%s has joined." % toon_name)

        self.users[user_id] = payload

    def __handle_user_leave_event(self, request, payload, status):
        user_id = payload.get("user_id", -1)
        toon_name = self.get_toon_name(user_id)
        if not self.hide_channel: self.__print("%s has left." % toon_name)
        del self.users[user_id]

    def __handle_message_event(self, request, payload, status):
        if self.hide_chat: return

        user_id = payload.get("user_id")
        mtype = payload.get("type")
        name = self.get_toon_name(user_id)

        if mtype.lower() == "whisper": name = "From " + name
        if mtype.lower() == "emote" and user_id == 1: return    # Ignore our own emotes (we use the command confirmation)

        self.__print("(%s) %s: %s" % (mtype, name, payload.get("message", "")))

    def __handle_send_message_event(self, request, payload, status):
        if self.hide_chat: return
        self.__print("(Channel) %s: %s" % (self.get_toon_name(1), request.get("message")))

    def __handle_send_whisper_response(self, request, payload, status):
        if self.hide_chat: return
        self.__print("(Whisper) To %s: %s" % (self.get_toon_name(request.get("user_id")), request.get("message")))

    def __handle_send_emote_response(self, request, payload, status):
        if self.hide_chat: return
        self.__print("(Emote) %s: %s" % (self.get_toon_name(1), request.get("message")))

if __name__ == "__main__":
    api_key = None
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        print("You must specify an API key.")
        sys.exit(2)

    client = capi_client(api_key)
    client.connect()

    print("Type /disconnect at any time to disconnect.")

    while client.connected:
        msg = input()
        cmd = msg.lower().split(' ')[0]

        if cmd == "/disconnect":
            client.disconnect()
        elif cmd == "/debug":
            client.debug_mode = not client.debug_mode
            print("Debug mode: %s" % "Enabled" if client.debug_mode else "Disabled")
        elif cmd in [ "/w", "/msg", "/whisper", "/message" ]:
            m = msg.split(maxsplit=2)
            if len(m) != 3:
                print("You must specify a user and a message to whisper.")
            else:
                client.send_whisper(m[2], m[1])
        elif cmd in [ "/me", "/emote" ]:
            m = msg.split(maxsplit=1)
            if len(m) != 2:
                print("You must specify an action to emote.")
            else:
                client.send_emote(m[1])
        elif cmd == "/send":
            m = msg.split(maxsplit=2)
            if len(m) < 2:
                print("You must specify a command to send.")
            else:
                client.send_command(m[1], json.loads(m[2]) if len(m) > 2 else { })
        else:
            client.send_chat(msg)

    print("All connections closed. Press RETURN to close the program.")
    input()

