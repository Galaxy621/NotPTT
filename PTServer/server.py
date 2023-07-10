import importlib
import json
import os
import socket
import time
import threading

import PTUtils
import PTCommand

from PTConfig import Config
from . import client
from .messages import CompactMessage, MessageType

VERSION = "1.2.4"

class Server:
    def __init__(self, config: Config):
        self.Up = False
        self.Version = VERSION

        self.Host: str = config.Host
        self.Port: int = config.Port
        self.Timeout: int = config.Timeout
        self.MaxPlayers: int = config.MaxPlayers
        self.MaxConnections: int = config.MaxConnections
        self.Anticheat: bool = config.Anticheat

        self.Commands: list[PTCommand.Command] = []
        self.Clients: dict[int, client.Client] = {}
        self.ClientMutex = threading.Lock()

        self.Keys = config.Keys
        self.Bans = config.Bans
        self.BadWords = config.BadWords

        self.Admins = []
        self.AdminPath = "admins.json"
        self.AdminMutex = threading.Lock()

    def load_plugins(self, plugins_path: str):
        """ Loads plugins from the specified directory. """
        for file in os.listdir(plugins_path):
            if file.endswith(".py"):
                name = file[:-3]
                try:
                    module = importlib.import_module(f"{plugins_path}.{name}")
                    module.setup(self)
                except Exception as e:
                    print(f"Failed to load plugin {name}: {e}")
                    continue

    def load_admins(self, admin_path: str = None):
        """ Loads admins from the specified file. """
        if admin_path is not None:
            self.AdminPath = admin_path

        with self.AdminMutex:
            with open(self.AdminPath, "r") as f:
                self.Admins = json.load(f)
        
    def save_admins(self):
        """ Saves admins to the specified file. """
        with self.AdminMutex:
            with open(self.AdminPath, "w") as f:
                json.dump(self.Admins, f)

    def auth_admin(self, username: str, password: str) -> bool:
        """ Authenticates the given username and password. """
        with self.AdminMutex:
            for admin in self.Admins:
                if admin["username"] == username and admin["password"] == PTUtils.sha256(password):
                    return True
                
        return False

    def change_password(self, username: str, new_password: str) -> bool:
        """ Changes the password of the given username. """
        with self.AdminMutex:
            for admin in self.Admins:
                if admin["username"] == username:
                    admin["password"] = PTUtils.sha256(new_password)
                    self.save_admins(self.AdminPath)
                    return True
        
        return False
    
    def check_connections(self):
        # Every second, check for clients that have timed out
        t = PTUtils.Ticker(1)

        while t.tick():
            if not self.Up:
                return

            to_remove = []
            with self.ClientMutex:
                for _, client in self.Clients.items():
                    if time.time() - client.LastMessage > self.Timeout:
                        to_remove.append(client.ID)

            for id in to_remove:
                client = self.Clients[id]
                client.close(MessageType.OmsgDisconnect, "Timed out")


    def start(self):
        print(f"Starting server on {self.Host}:{self.Port}...")

        self.load_admins()

        if len(self.Admins) == 0:
            print("Warning: No admins present. Would you like to add one? (y/n)")
            if input().lower() == "y":
                print("Enter username:")
                username = input()
                print("Enter password:")
                password = input()
                self.Admins.append({
                    "username": username,
                    "password": PTUtils.sha256(password)
                })
                self.save_admins()

        self.Up = True

        threading.Thread(target=self.check_connections).start()

        # Create TCP Listner
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            sock.bind((self.Host, self.Port))
            sock.listen(1)
        except Exception as e:
            print(f"Failed to bind to {self.Host}:{self.Port}: {e}")
            self.Up = False
            return
        
        print(f"Server started on {self.Host}:{self.Port}")

        # Main loop
        while self.Up:
            try:
                conn, addr = sock.accept()

                c = client.Client(
                    id = PTUtils.generate_unique_id(self.Clients),
                    conn = conn,
                    ip256 = PTUtils.sha256(addr[0]),
                    server = self
                )

                threading.Thread(target=c.accept).start() 
                

            except Exception as e:
                print(f"Failed to accept connection: {e}")
                continue

    def stop(self):
        self.Up = False

        with self.ClientMutex:
            for _, client in self.Clients.items():
                client.close(MessageType.OmsgDisconnect, "Server shutting down")

    def broadcast(self, msg: str, lobby: str = None):
        with self.ClientMutex:
            for _, client in self.Clients.items():
                if lobby is None or client.Lobby == lobby:
                    client.append(CompactMessage(MessageType.OmsgDefault, msg))

    def announce(self, msg: str):
        with self.ClientMutex:
            for _, client in self.Clients.items():
                client.append(CompactMessage(MessageType.OmsgAnnouncement, msg))

    def kick(self, id: int, reason: str):
        with self.ClientMutex:
            if id in self.Clients:
                client = self.Clients[id]
            else:
                return
            
        if client.Admin:
            return
        
        client.close(MessageType.OmsgKick, reason)

    def ban(self, id: int, reason: str):
        with self.ClientMutex:
            if id in self.Clients:
                client = self.Clients[id]
            else:
                return
            
        if client.Admin:
            return
        
        self.Bans.append(client.Ip256)
        client.close(MessageType.OmsgKick, reason)


    def check_key(self, key: str):
        return key in self.Keys
    
    def check_banned(self, ip256: str):
        return ip256 in self.Bans
    
    def lobby_count(self, lobby: str):
        count = 0

        with self.ClientMutex:
            for _, client in self.Clients.items():
                if client.Lobby == lobby:
                    count += 1


        return count
    
    def register_command(self, command: PTCommand.Command):
        self.Commands.append(command)