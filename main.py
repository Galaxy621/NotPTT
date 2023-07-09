import PTServer

from PTConfig import Config

if __name__ == '__main__':
    # Create Server
    config = Config(
        Host="localhost",
        Port=6666,
        Timeout=10,
        MaxPlayers=128,
        MaxConnections=3,
        Anticheat=True,
        Keys = [],
        Bans = [],
        BadWords = ['fart']
    )

    server = PTServer.Server(config=config)
    server.start()