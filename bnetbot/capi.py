
from datetime import datetime

import json
import ssl
import threading
import traceback
import websocket


STATUS_CODES = {
    0: {
        0: None
    },
    6: {
        5: "Request timed out",
        8: "Rate limit exceeded"
    },
    8: {
        1: "Not connected to chat",
        2: "Bad request"
    }
}

OPCODES = {
    0: "Continue",
    1: "Text",
    2: "Binary",
    8: "Close",
    9: "Ping",
    10: "Pong"
}


class CapiUser:
    def __init__(self, user_id, name, flags=None, attributes=None):
        self.id = user_id
        self.name = name
        self.flags = flags or []
        self.attributes = {}
        if attributes:
            self.update(attributes)

    def update(self, attr):
        if isinstance(attr, list):
            for item in attr:
                if isinstance(item, dict):
                    key, value = item.get("key"), item.get("value")
                    self.attributes[key] = value
                else:
                    raise ValueError("Unexpected attribute item format: %s" % type(item).__name__)
        elif isinstance(attr, dict):
            self.attributes.update(attr)
        else:
            raise ValueError("Unexpected attribute format: %s" % type(attr).__name__)

    def has_flag(self, flag):
        for f in self.flags:
            if f.lower() == flag.lower():
                return True
        return False


class CapiClient(threading.Thread):
    def __init__(self, api_key):
        self.api_key = api_key
        self.channel = None
        self.username = None
        self.last_message = None
        self.users = {}
        self.debug_on = False

        self._authenticating = False
        self._connected = False
        self._disconnecting = False
        self._endpoint = "wss://connect-bot.classic.blizzard.com/v1/rpc/chat"
        self._requests = {}
        self._received_users = False
        self._socket = None
        self._thread = None

        self._handlers = {
            "Botapiauth.AuthenticateResponse": self._handle_auth_response,
            "Botapichat.ConnectResponse": self._handle_connect_response,
            "Botapichat.ConnectEventRequest": self._handle_connect_event,
            "Botapichat.DisconnectEventRequest": self._handle_disconnect_event,
            "Botapichat.UserUpdateEventRequest": self._handle_user_update_event,
            "Botapichat.UserLeaveEventRequest": self._handle_user_leave_event,
            "Botapichat.MessageEventRequest": self._handle_message_event,
            "Botapichat.SendMessageResponse": self._handle_message_response,
            "Botapichat.SendWhisperResponse": self._handle_whisper_response
        }

        self.handle_joined_chat = None      # channel, user
        self.handle_user_joined = None      # user
        self.handle_user_update = None      # user, flags, attributes
        self.handle_user_left = None        # user name
        self.handle_user_talk = None        # user, message
        self.handle_bot_message = None      # message
        self.handle_whisper = None          # user, message, received
        self.handle_emote = None            # user, message
        self.handle_info = None             # message
        self.handle_error = None            # message
        super().__init__()

    def error(self, text):
        if self.handle_error:
            self.handle_error(text)
        else:
            print("ERROR: %s" % text)

    def debug(self, text):
        if self.debug_on:
            print("DEBUG: %s" % text)

    def connected(self):
        return self._connected and self._socket is not None and self._socket.connected

    def connect(self, endpoint=None):
        self._socket = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
        self._endpoint = (endpoint or self._endpoint)

        try:
            self._socket.connect(self._endpoint)
            self._connected = True
            self.last_message = datetime.now()
        except (websocket.WebSocketException, TimeoutError, ConnectionError) as ex:
            self.debug("Connection failed: %s" % ex)
            return False
        return True

    def disconnect(self, force=False):
        if force:
            self.debug("Forcing disconnect.")
            self._socket.close()
            self._authenticating = False
            self._connected = False
            self.channel = None
            self._disconnecting = False
            self.last_message = None
            self.users = {}
            self._requests = {}
        else:
            self._disconnecting = True
            self.request("Botapichat.DisconnectRequest")

    def get_user(self, name):
        if isinstance(name, int):
            return self.users.get(name)
        elif isinstance(name, str):
            if name[0] == '*':
                name = name[1:]

            for user in self.users.values():
                if user.name.lower() == name.lower():
                    return user
        return None

    def ping(self, payload=None):
        self._socket.ping(str(datetime.now() if payload is None else payload))
        self.debug("Sent websocket PING")

    def request(self, command, payload=None):
        # Find the next available request ID. Values are reused as long as there isn't a pending request with that ID.
        request_id = 1
        while request_id in self._requests:
            request_id += 1

        data = {
            "command": command,
            "request_id": request_id,
            "payload": payload or {}
        }

        self._socket.send(json.dumps(data), websocket.ABNF.OPCODE_TEXT)
        self.debug("Sent command: %s" % command)
        self._requests[request_id] = data
        return request_id

    def chat(self, message, target=None):
        command = "Botapichat.SendMessageRequest"
        payload = {"message": message}

        if target:
            if isinstance(target, (str, int)):
                target = self.get_user(target)
            elif not isinstance(target, CapiUser):
                return self.error("Send message failed - target user not found")

            if target.name.lower() == self.username.lower():
                # Target is ourselves, so this should be an emote.
                command = "Botapichat.SendEmoteRequest"
            else:
                command = "Botapichat.SendWhisperRequest"
                payload["user_id"] = target.id

        return self.request(command, payload)

    def ban(self, target, kick=False):
        user = self.get_user(target)
        if user is None:
            self.error("Kick/ban failed - user not found")
        else:
            command = "Botapichat.KickUserRequest" if kick else "Botapichat.BanUserRequest"
            return self.request(command, {"user_id": user.id})

    def unban(self, user):
        return self.request("Botapichat.UnbanUserRequest", {"toon_name": user})

    def set_moderator(self, target):
        user = self.get_user(target)
        if user is None:
            self.error("Set moderator failed - user not found")
        else:
            return self.request("Botapichat.SendSetModeratorRequest", {"user_id": user.id})

    def run(self):
        global STATUS_CODES, OPCODES

        if not self.connected():
            if not self.connect():
                return

        self._authenticating = True
        self.request("Botapiauth.AuthenticateRequest", {"api_key": self.api_key})

        # Receive and process incoming messages
        while self.connected():
            try:
                opcode, data = self._socket.recv_data(True)
            except (websocket.WebSocketException, TimeoutError, ConnectionError) as ex:
                if isinstance(ex, websocket.WebSocketPayloadException):
                    # The API sometimes sends messages with invalid UTF-8. Ignore them.
                    continue
                else:
                    # Unknown error - force close socket
                    return self.disconnect(True)

            # Record the message received time
            self.last_message = datetime.now()
            if opcode != websocket.ABNF.OPCODE_TEXT:
                self.debug("Received opcode: %s (%i)" % (OPCODES.get(opcode, "Unknown"), opcode))
                # These are just control messages and can be ignored.
                continue

            # Decode the message
            try:
                message = data.decode('utf-8')
                data = json.loads(message)
            except json.JSONDecodeError:
                # Possibly corrupt message but just ignore it (the API is in alpha after all!)
                continue

            if isinstance(data, dict):
                request_id = data.get("request_id")
                command = data.get("command")
                status = data.get("status")
                payload = data.get("payload")

                self.debug("Received command: %s" % command)

                # Parse the status code if given
                if status and isinstance(status, dict):
                    area = status.get("area")
                    code = status.get("code")

                    status = STATUS_CODES.get(area)
                    status = status and status.get(code)
                    if not status:
                        status = "Unknown (%i-%i)" % (area, code)

                # Find the request that triggered this response
                request = None
                if "Event" not in command:
                    if request_id in self._requests:
                        request = self._requests.get(request_id)
                        del self._requests[request_id]

                if command in self._handlers:
                    try:
                        self._handlers.get(command)(request, payload, status)
                    except Exception as ex:
                        print("ERROR! Something happened while processing received command '%s': %s" % (command, ex))
                        print(traceback.format_exc())

    def _handle_auth_response(self, request, response, status):
        self._authenticating = False
        if status:
            self.error("Authentication failed: %s" % status)
        else:
            self.request("Botapichat.ConnectRequest")

    def _handle_connect_response(self, request, response, status):
        if status:
            self.error("Failed to connect to chat: %s" % status)

    def _handle_connect_event(self, request, response, status):
        self.channel = response.get("channel")
        if self.handle_joined_chat:
            self.handle_joined_chat(self.channel, self.get_user(self.username))

    def _handle_disconnect_event(self, request, response, status):
        self.error("Disconnected from chat API.")

    def _handle_user_update_event(self, request, response, status):
        user_id = response.get("user_id")
        toon_name = response.get("toon_name")
        attributes = response.get("attribute")  # [{"key":1,"value":2}, etc]
        flags = response.get("flag")

        # Find or create the user described by this event.
        user = self.get_user(user_id) or CapiUser(user_id, toon_name, flags, attributes)

        if not self.channel:
            # We aren't yet in channel, so this should be our own info.
            self.username = user.name
        else:
            if user.id in self.users:
                changes = False     # Make sure something has actually changed

                if flags or attributes:
                    if flags and user.flags != flags:
                        changes = True
                    elif attributes:
                        old = user.attributes
                        user.update(attributes)
                        if user.attributes != old:
                            changes = True
                elif user.id == 1 and not self._received_users:
                    self._received_users = True
                    changes = True
                    self.debug("Users in channel: %s" % ", ".join(u.name for u in self.users.values()))

                if changes and self.handle_user_update:
                    self.handle_user_update(user, flags, attributes)
            else:
                if self._received_users:
                    if self.handle_user_joined:
                        self.handle_user_joined(user)
                else:
                    if self.handle_user_update:
                        self.handle_user_update(user, flags, attributes)

        self.users[user.id] = user

        # The attributes system isn't complete yet so alert the user to any abnormalities.
        if user.attributes and len(user.attributes) > 0:
            pgm = user.attributes.get("ProgramId")
            if pgm and pgm != "W2BN":
                print("NOTICE! Detected new ProgramID: %s" % pgm)
            if len(user.attributes) > 1 or pgm is None:
                print("NOTICE! Detected new attributes: %s" % user.attributes)

    def _handle_user_leave_event(self, request, response, status):
        user = self.get_user(response.get("user_id"))
        del self.users[user.id]
        if self.handle_user_left:
            self.handle_user_left(user)

    def _handle_message_event(self, request, response, status):
        user = self.get_user(response.get("user_id"))
        mtype = response.get("type")
        message = response.get("message")

        handlers = {
            "channel": self.handle_user_talk,
            "emote": self.handle_emote,
            "whisper": self.handle_whisper,
            "serverinfo": self.handle_info,
            "servererror": self.handle_error
        }
        event = handlers.get(mtype.lower())
        if event:
            if mtype.lower() in ["serverinfo", "servererror"]:
                event(message)
            elif mtype.lower() == "whisper":
                event(user, message, True)
            else:
                event(user, message)

    def _handle_message_response(self, request, response, status):
        if status:
            self.error("Failed to send message: %s" % status)
        else:
            payload = request.get("payload", {})
            if self.handle_bot_message:
                self.handle_bot_message(payload.get("message"))

    def _handle_whisper_response(self, request, response, status):
        if status:
            self.error("Failed to send whisper: %s" % status)
        else:
            payload = request.get("payload", {})
            target = self.get_user(payload.get("user_id"))
            message = payload.get("message")

            if self.handle_whisper:
                self.handle_whisper(target, message, False)
