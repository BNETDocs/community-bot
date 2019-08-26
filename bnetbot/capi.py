
from .util.events import EventSource

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


class CapiError:
    def __init__(self, message):
        self.message = message
        self.area = None
        self.code = None

    def get_reason(self):
        return STATUS_CODES.get(self.area, {}).get(self.code) or ("Unknown (%i-%i)" % (self.area, self.code))

    @classmethod
    def from_status(cls, status, message=None):
        ex = cls(None)
        ex.area = status.get("area")
        ex.code = status.get("code")
        ex.message = message or ex.get_reason()
        return ex


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


class CapiClient(EventSource):
    def __init__(self, api_key):
        self._api_key = api_key
        self.channel = None
        self.username = None
        self.last_message = None
        self.users = {}
        self.endpoint = "wss://connect-bot.classic.blizzard.com/v1/rpc/chat"

        self._authenticating = False
        self._connected = False
        self._disconnecting = False
        self._requests = {}
        self._received_users = False
        self._socket = None
        self._thread = None

        self.message_handlers = {
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

        client_events = ['joined_chat', 'user_joined', 'user_update', 'user_left', 'user_talk', 'bot_talk',
                         'whisper_sent', 'whisper_received', 'user_emote', 'server_info', 'server_error',
                         'protocol_message_received', 'protocol_message_sent', 'left_chat', 'client_error']
        super().__init__(client_events)

    def connected(self):
        return self._connected and self._socket is not None and self._socket.connected

    def connect(self, endpoint=None):
        self._socket = websocket.WebSocket(timeout=10, sslopt={"cert_reqs": ssl.CERT_NONE})
        self.endpoint = (endpoint or self.endpoint)

        try:
            self._socket.connect(self.endpoint)
            self._connected = True

            self._thread = threading.Thread(target=self._receive)
            self._thread.setDaemon(True)
            self._thread.start()
            return True
        except (websocket.WebSocketException, TimeoutError, ConnectionError) as ex:
            self.events['client_error'](self, ex)
            return False

    def disconnect(self, force=False):
        if force:
            self._socket.shutdown()
            self._authenticating = False
            self._connected = False
            self._disconnecting = False

            self.last_message = None
            self.channel = None
            self.users = {}
            self._requests = {}
        else:
            self._disconnecting = True
            self.send("Botapichat.DisconnectRequest")

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
        try:
            self._socket.ping(str(datetime.now() if payload is None else payload))
            return True
        except (websocket.WebSocketException, TimeoutError, ConnectionError) as ex:
            self.events['client_error'](self, ex)
            return False

    def send(self, command, payload=None):
        # Find the next available request ID.
        # Values are reused once a response has been received with the same ID.
        request_id = 1
        while request_id in self._requests:
            request_id += 1

        data = {
            "command": command,
            "request_id": request_id,
            "payload": payload or {}
        }

        self._socket.send(json.dumps(data), websocket.ABNF.OPCODE_TEXT)
        self.events['protocol_message_sent'](self, data)
        self._requests[request_id] = data
        return request_id

    def chat(self, message, target=None):
        command = "Botapichat.SendMessageRequest"
        payload = {"message": message}

        if target:
            if isinstance(target, (str, int)):
                user = self.get_user(target)
                if not user:
                    self.events['client_error'](self, CapiError("Chat target not found: %s" % target))
                    return False
                target = user
            elif not isinstance(target, CapiUser):
                raise TypeError("Chat target must be user name, numeric ID, or object.")

            if target.name.lower() == self.username.lower():
                # Target is ourselves, so this should be an emote.
                command = "Botapichat.SendEmoteRequest"
            else:
                command = "Botapichat.SendWhisperRequest"
                payload["user_id"] = target.id

        return self.send(command, payload)

    def ban(self, target, kick=False):
        user = self.get_user(target)
        if user:
            command = "Botapichat.KickUserRequest" if kick else "Botapichat.BanUserRequest"
            return self.send(command, {"user_id": user.id})

    def unban(self, user):
        if isinstance(user, CapiUser):
            # This isn't normal since banned users aren't in the channel, but just in case the object was stored..
            user = user.name
        elif not isinstance(user, str):
            raise TypeError("Unban target must be user name or object.")

        return self.send("Botapichat.UnbanUserRequest", {"toon_name": user})

    def set_moderator(self, target):
        user = self.get_user(target)
        if user:
            return self.send("Botapichat.SendSetModeratorRequest", {"user_id": user.id})

    def _receive(self):
        global STATUS_CODES, OPCODES

        if not self.connected():
            if not self.connect():
                return

        self._authenticating = True
        self.send("Botapiauth.AuthenticateRequest", {"api_key": self._api_key})

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

            # Record the message received time for keep-alive tracking
            self.last_message = datetime.now()

            if opcode != websocket.ABNF.OPCODE_TEXT:
                # These are just control messages and can be ignored.
                continue

            try:
                message = data.decode('utf-8')
                data = json.loads(message)
                self.events['protocol_message_received'](self, data)
            except json.JSONDecodeError:
                # Corrupt message but just ignore it (the API is in alpha after all!)
                continue

            if isinstance(data, dict):
                request_id = data.get("request_id")
                command = data.get("command")
                status = data.get("status")
                payload = data.get("payload")

                # Parse the optionally returned error status
                error = None
                if status and isinstance(status, dict):
                    error = CapiError.from_status(status)

                # Match this response to a sent request
                request = None
                if "Event" not in command:
                    if request_id in self._requests:
                        request = self._requests.get(request_id)
                        del self._requests[request_id]

                if command in self.message_handlers:
                    try:
                        self.message_handlers.get(command)(request, payload, error)
                    except Exception as ex:
                        print("ERROR! Something happened while processing received command '%s': %s" % (command, ex))
                        print(traceback.format_exc())

    def _handle_auth_response(self, request, response, error):
        self._authenticating = False
        if error:
            error.message = "Authentication failed."
            self.events['client_error'](self, error)
        else:
            self.send("Botapichat.ConnectRequest")

    def _handle_connect_response(self, request, response, error):
        if error:
            error.message = "Failed to connect to chat"
            self.events['client_error'](self, error)

    def _handle_connect_event(self, request, response, error):
        self.channel = response.get("channel")
        self.events['joined_chat'](self, self.channel, self.get_user(self.username))

    def _handle_disconnect_event(self, request, response, error):
        self.events['left_chat'](self)
        self.disconnect(True)

    def _handle_user_update_event(self, request, response, error):
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

                if changes:
                    self.events['user_update'](self, user, flags, attributes)
            else:
                if self._received_users:
                    self.events['user_joined'](self, user)
                else:
                    self.events['user_update'](self, user, flags, attributes)

        self.users[user.id] = user

        # The attributes system isn't complete yet so alert the user to any abnormalities.
        if user.attributes and len(user.attributes) > 0:
            pgm = user.attributes.get("ProgramId")
            if pgm and pgm not in ["W2BN", "SEXP"]:
                print("NOTICE! Detected new ProgramID: %s" % pgm)
            if len(user.attributes) > 1 or pgm is None:
                print("NOTICE! Detected new attributes: %s" % user.attributes)

    def _handle_user_leave_event(self, request, response, error):
        user = self.get_user(response.get("user_id"))
        del self.users[user.id]
        self.events['user_left'](self, user)

    def _handle_message_event(self, request, response, error):
        user = self.get_user(response.get("user_id"))
        mtype = response.get("type")
        message = response.get("message")

        handlers = {
            "channel": 'user_talk',
            "emote": 'user_emote',
            "whisper": 'whisper_received',
            "serverinfo": 'server_info',
            "servererror": 'server_error'
        }
        event = handlers.get(mtype.lower())
        if event:
            if mtype.lower() in ["serverinfo", "serverror"]:
                self.events[event](self, message)
            elif mtype.lower() == "whisper":
                self.events[event](self, user, message)
            else:
                self.events[event](self, user, message)

    def _handle_message_response(self, request, response, error):
        if error:
            error.message = "Failed to send message."
            self.events['client_error'](self, error)
        else:
            payload = request.get("payload", {})
            self.events['bot_talk'](self, payload.get("message"))

    def _handle_whisper_response(self, request, response, error):
        if error:
            error.message = "Failed to send whisper."
            self.events['client_error'](self, error)
        else:
            payload = request.get("payload", {})
            target = self.get_user(payload.get("user_id"))
            message = payload.get("message")

            self.events['whisper_sent'](self, target, message)
