import socket
import time
import threading

import PTUtils
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

        self.Clients: dict[int, client.Client] = {}
        self.ClientMutex = threading.Lock()

        self.Keys = config.Keys
        self.Bans = config.Bans
        self.BadWords = config.BadWords

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
        self.Up = True

        threading.Thread(target=self.check_connections).start()

        # Create TCP Listner
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            sock.bind((self.Host, self.Port))
            sock.listen()
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