from __future__ import annotations

import json
import random
import socket
import time
import threading

from dataclasses import dataclass

import PTUtils
import PTCommand

from . import server
from .messages import CompactClient, CompactMessage, MessageType, Message

class Client:
    def __init__(self, id: int, conn: tuple, ip256: str, server: server.Server):
        self.ID: int = id
        self.Conn: socket.socket = conn
        self.Ip256: str = ip256
        self.Name: str = ""
        self.Admin: bool = False
        self.Active: bool = False
        self.Paused: bool = False
        self.LoggedIn: bool = False
        self.Lobby: str = ""

        self.ConnectedServer: server.Server = server
        self.Data: ClientData = ClientData()
        self.LastMessage: float = 0

        self.Queue: list[CompactMessage] = []
        self.QueueMutex: threading.Lock = threading.Lock()
        self.MsgTries: int = 0

        self.ParseFails: int = 0
        self.Color: str = ""
        self.Chat: list[Message] = []
        self.ChatMutex: threading.Lock = threading.Lock()

    def accept(self):
        print(f"New connection from: {self.Ip256}")

        previousConnections = 0

        with self.ConnectedServer.ClientMutex:
            for _, client in self.ConnectedServer.Clients.items():
                if client.Ip256 == self.Ip256:
                    previousConnections += 1

                if previousConnections >= self.ConnectedServer.MaxConnections:
                    self.ConnectedServer.ClientMutex.release()
                    self.close(MessageType.OmsgKick, "You are already connected with the max amount of connections.")
                    return

        self.Chat = []
        self.Active = True
        self.LastMessage = time.time()

        with self.ConnectedServer.ClientMutex:
            self.ConnectedServer.Clients[self.ID] = self

        self.loop()

    def loop(self):
        t = PTUtils.Ticker(1 / 60)

        while t.tick():
            if not self.Active:
                return
            
            try:
                raw = self.Conn.recv(2048)
                if not raw:
                    self.close(MessageType.MsgNone, "No data received.")
                    return
            except Exception as e:
                self.close(MessageType.MsgNone, f"{e}")
                return

            self.parse(raw)
            self.LastMessage = time.time()

            if self.ParseFails > 10:
                self.close(MessageType.OmsgKick, "Too many invalid packets.")
                return
            
            response_data = {}

            if len(self.Queue) > 0:
                with self.QueueMutex:
                    msg = self.Queue.pop(0)

                response_data["type"] = msg.Type.value
                response_data["msg"] = msg.Msg
                response = json.dumps(response_data).encode()

                try:
                    self.Conn.sendall(response)
                except Exception as e:
                    self.close(MessageType.MsgNone, f"{e}")
                    return
            else:
                clients: list[CompactClient] = []

                with self.ConnectedServer.ClientMutex:
                    for _, client in self.ConnectedServer.Clients.items():
                        if client.ID == self.ID or client.Lobby != self.Lobby or client.Data.Room != self.Data.Room:
                            continue

                        clients.append(CompactClient(
                            ID = client.ID,
                            X = client.Data.X,
                            Y = client.Data.Y,
                            Name = client.Name,
                            Admin = client.Admin,
                            Room = client.Data.Room,
                            Sprite = client.Data.Sprite,
                            Frame = client.Data.Frame,
                            Dir = client.Data.Dir,
                            Palette = client.Data.Palette,
                            PaletteSprite = client.Data.PaletteSprite,
                            PaletteTexture = client.Data.PaletteTexture,
                            Color = client.Data.Color
                        ))

                    response_data["clients"] = [client.to_json() for client in clients]

                with self.ChatMutex:
                    response_data["msgs"] = [msg.to_json() for msg in self.Chat]

                response_data["type"] = MessageType.OmsgDefault.value
                response_data["loggedIn"] = self.LoggedIn
                response_data["admin"] = self.Admin
                response_data["name"] = self.Name
                response_data["id"] = self.ID
                response_data["onlineCnt"] = self.ConnectedServer.lobby_count(self.Lobby)

                response = json.dumps(response_data).encode()

                try:
                    self.Conn.sendall(response)
                except Exception as e:
                    self.close(MessageType.MsgNone, f"{e}")
                    return
                


    def close(self, type: MessageType, msg: str):
        self.direct(
            CompactMessage(
                Type = type.value,
                Msg = msg
            )
        )

        if type == MessageType.MsgNone:
            print(f"Client {self.ID} disconnected: {msg}")

        # print(f"Client {self.ID} disconnected: {msg}")
        self.Conn.close()
        self.Active = False

        if self.ConnectedServer.Clients.get(self.ID, None):
            with self.ConnectedServer.ClientMutex:
                del self.ConnectedServer.Clients[self.ID]

    def parse(self, message):
        data_objects = []

        try:
            json_datas = message.decode().split("}\n{")
            if len(json_datas) > 1:
                json_datas[0] = json_datas[0] + "}"
                json_datas[-1] = "{" + json_datas[-1]

            for json_data in json_datas:
                try:
                    loded = json.loads(json_data)
                except:
                    continue

                data_objects.append(ClientData.from_dict(loded))

        except Exception as e:

            print(f"Client {self.ID} failed to parse message ({message}): {e}")

            self.ParseFails += 1
            if self.ParseFails > 10:
                self.close(MessageType.OmsgKick, "Too many parse fails.")

            return
        
        self.ParseFails = 0

        for data in data_objects:
            if self.ConnectedServer.Anticheat:
                data.Sprite = PTUtils.anticheat(data.Sprite)

            self.Paused = False

            # print(f"Client {self.ID} sent data: ({data.Type}) {data.__dict__}")
            # print(loded)

            match data.Type:
                case MessageType.ImsgLogin.value:
                    if self.LoggedIn:
                        return
                    
                    if self.ConnectedServer.check_key(data.Key):
                        self.Admin = True

                    if self.ConnectedServer.check_banned(self.Ip256):
                        self.close(MessageType.OmsgKick, "You are banned.")
                        return

                    if data.Ver != self.ConnectedServer.Version:
                        self.close(MessageType.OmsgKick, "Your client is outdated.")
                        return
                    
                    data.Name = PTUtils.clean_name(data.Name, self.ConnectedServer.BadWords)

                    # check if name is taken
                    should_close = None

                    with self.ConnectedServer.ClientMutex:
                        if self.Admin:
                            for id, client in self.ConnectedServer.Clients.items():
                                if client.Name == data.Name and client.ID != self.ID:
                                    should_close = client
                        else:
                            nm = data.Name

                            while True:
                                for _, client in self.ConnectedServer.Clients.items():
                                    if client.Name == nm:
                                        nm += str(random.randint(0, 9))
                                        break
                                else:
                                    data.Name = nm
                                    break

                    if should_close:
                        should_close.close(MessageType.MsgNone, "")

                    self.Data = data
                    self.Name = data.Name
                    self.Lobby = data.Lobby
                    self.LoggedIn = True
                    self.Color = data.Color

                    print(f"Client {self.ID} logged in as {self.Name} ({self.Ip256})")
                    self.ConnectedServer.broadcast(f"{self.Name} has entered the tower!", self.Lobby)
                    self.server_pm(f"Welcome to NotPTT, {self.Name}! Use /help for a list of commands.")

                case MessageType.ImsgDefault.value:
                    if not self.LoggedIn:
                        return
                    
                    self.Data = data
                
                case MessageType.ImsgPaused.value:
                    if not self.LoggedIn:
                        return
                    
                    self.Paused = True

                case MessageType.ImsgMessage.value:
                    if not self.LoggedIn:
                        return
                    
                    if data.Msg == "":
                        return
                    
                    if data.Msg.startswith("/"):
                        self.command(data.Msg)
                        return
                    
                    data.Msg = PTUtils.clean(data.Msg, 256, self.ConnectedServer.BadWords)
                    
                    with self.ConnectedServer.ClientMutex:
                        for id, client in self.ConnectedServer.Clients.items():
                            if client.Lobby == self.Lobby and client.Active and client.LoggedIn:
                                client.pm(Message(
                                    Body = data.Msg,
                                    Username = self.Name,
                                    Id = self.ID
                                ))
                            # else:
                            #     print(f"Client {self.ID} tried to send a message to {client.ID} but they are not in the same lobby.")


    def command(self, msg: str):
        arr = msg[1:].split(" ")
        cmd = arr[0]
        args = arr[1:]

        # First check if there's a custom implementation
        for command in self.ConnectedServer.Commands:
            if command.Name == cmd:
                failed = command._run(args, self)

                if failed:
                    match failed:
                        case (False, PTCommand.FailedCommand.InvalidArgs):
                            self.server_pm(f"Usage: /{command.Name} {' '.join(command.Args)}")
                        case (False, PTCommand.FailedCommand.NotAdmin):
                            self.server_pm("You are not an admin.")
                        case (False, PTCommand.FailedCommand.FailureExecuting):
                            self.server_pm("Failed to execute command.")

                return

        match cmd:
            case "help":
                self.server_pm("Command Help:")

                if self.Admin:
                    self.server_pm("  /ban <id> <reason> - Bans a user")
                    self.server_pm("  /kick <id> <reason> - Kicks a user")
                    self.server_pm("  /announce <msg> - Announces a message")

                # who - lists all users
                # pm <name> <msg> - sends a private message to a user
                # nick <name> - changes your name
                self.server_pm("  /help - Shows this message")
                self.server_pm("  /who - Lists all users")
                self.server_pm("  /pm <name> <msg> - Sends a private message to a user")
                self.server_pm("  /nick <name> - Changes your name")

                # Custom commands
                if len(self.ConnectedServer.Commands) > 0:
                    self.server_pm("The following custom commands are available:")
                    for command in self.ConnectedServer.Commands:
                        if command.IsAdmin and not self.Admin:
                            continue

                        self.server_pm(f"  {command}")

            case "login":
                # allow admins to login using a username and password
                if len(args) < 2:
                    self.server_pm("Usage: /login <username> <password>")
                    return
                
                username = args[0]
                password = args[1]

                if not self.ConnectedServer.auth_admin(username, password):
                    self.server_pm("Incorrect username or password.")
                    return
                
                self.Admin = True
                self.nickname(username)

                self.server_pm("You are now logged in.")

            case "password":
                if not self.Admin:
                    return
                
                if len(args) < 1:
                    self.server_pm("Usage: /password <password>")
                    return
                
                password = " ".join(args)
                self.ConnectedServer.change_password(self.Name, password)

            case "who":
                with self.ConnectedServer.ClientMutex:
                    for id, client in self.ConnectedServer.Clients.items():
                        if client.Lobby == self.Lobby and client.Active and client.LoggedIn:
                            self.server_pm(f"> {client.Name} ({client.ID})")

            case "pm":
                if len(args) < 2:
                    self.server_pm("Usage: /pm <name> <msg>")
                    return
                
                name = args[0]
                msg = " ".join(args[1:])
                found = False

                with self.ConnectedServer.ClientMutex:
                    for _, client in self.ConnectedServer.Clients.items():
                        if client.Name == name:
                            client.pm(Message(
                                Body = msg,
                                Username = self.Name,
                                Id = self.ID
                            ))
                            found = True
                            break

                if found:
                    self.pm(Message(
                        Body = msg,
                        Username = "You -> " + name,
                        Id = self.ID
                    ))
                else:
                    self.server_pm(f"User '{name}' not found.")

            case "nick":
                if self.Admin:
                    self.server_pm("You cannot change your name as an admin.")
                    return

                if len(args) < 1:
                    self.server_pm("Usage: /nick <name>")
                    return
                
                self.nickname(args[0])
                self.server_pm(f"Your name is now {self.Name}.")


            case "ban":
                if not self.Admin:
                    return
                
                if len(args) < 2:
                    self.server_pm("Usage: /ban <id> <reason>")
                    return
                
                id = int(args[0])
                reason = " ".join(args[1:])

                self.ConnectedServer.ban(id, reason)

            case "kick":
                if not self.Admin:
                    return
                
                if len(args) < 2:
                    self.server_pm("Usage: /kick <id> <reason>")
                    return
                
                id = int(args[0])
                reason = " ".join(args[1:])

                self.ConnectedServer.kick(id, reason)

            case "announce":
                if not self.Admin:
                    return
                
                if len(args) < 1:
                    self.server_pm("Usage: /announce <msg>")
                    return
                
                msg = " ".join(args)
                self.ConnectedServer.announce(f"{self.Name}: {msg}")

            case "reload":
                if not self.Admin:
                    return
                
                if not len(args) == 1:
                    self.server_pm("Usage: /reload <plugin path>")
                    return
                
                path = args[0]
                self.ConnectedServer.Commands.clear()
                self.ConnectedServer.load_plugins(path)
                

            case _:
                self.server_pm(f"Unknown command: {cmd}")

    def nickname(self, name: str):
        name = PTUtils.clean_name(name, self.ConnectedServer.BadWords)

        if name == self.Name:
            return
        
        should_close = None
        with self.ConnectedServer.ClientMutex:
            if self.Admin:
                for id, client in self.ConnectedServer.Clients.items():
                    if client.Name == name and client.ID != self.ID:
                        should_close = client
            else:
                nm = name

                while True:
                    for _, client in self.ConnectedServer.Clients.items():
                        if client.Name == nm:
                            nm += str(random.randint(0, 9))
                            break
                    else:
                        name = nm
                        break

        if should_close:
            should_close.close(MessageType.MsgNone, "")                        
        
        self.Name = name

    def append(self, msg: CompactMessage):
        with self.QueueMutex:
            self.Queue.append(msg)

    def direct(self, msg: CompactMessage):
        data = json.dumps(msg.to_json()).encode()
        try:
            self.Conn.sendall(data)
        except:
            pass

    def pm(self, msg: Message):
        msg.Mid = random.randint(0, 1000000)

        with self.ChatMutex:
            if len(self.Chat) > 32:
                self.Chat.pop(0)

            self.Chat.append(msg)

    def server_pm(self, msg: str):
        self.pm(Message(
            Body = msg,
            Username = "[NotPTT]",
            Id = -1
        ))

@dataclass
class ClientData:
    Type: int = MessageType.ImsgDefault.value
    Msg: str = ""
    Name: str = ""
    Version: str = ""
    Lobby: str = ""

    Key: str = ""
    X: float = 0
    Y: float = 0
    Room: int = 0

    Sprite: str = ""
    Frame: int = 0
    Dir: int = 0
    Palette: int = 0
    PaletteSprite: str = ""
    PaletteTexture: str = ""
    Color: str = ""

    MsgId: int = 0

    def to_json(self):
        return {
            "type": self.Type,
            "msg": self.Msg,
            "name": self.Name,
            "version": self.Version,
            "lobby": self.Lobby,
            "key": self.Key,
            "x": self.X,
            "y": self.Y,
            "room": self.Room,
            "sprite": self.Sprite,
            "frame": self.Frame,
            "dir": self.Dir,
            "palette": self.Palette,
            "paletteSprite": self.PaletteSprite,
            "paletteTexture": self.PaletteTexture,
            "color": self.Color,
            "msgId": self.MsgId
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, any]):
        template = cls()

        for key, value in data.items():
            trueKey = key[0].upper() + key[1:]
            setattr(template, trueKey, value)

        return template