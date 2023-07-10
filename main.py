import PTServer

from PTConfig import Config

if __name__ == '__main__':
    # Create Server
    config = Config(
        Host="",
        Port=25565,
        Timeout=10,
        MaxPlayers=128,
        MaxConnections=3,
        Anticheat=True,
        Keys = [],
        Bans = [],
        BadWords = ['fart']
    )

    server = PTServer.Server(config=config)
    server.load_plugins("plugins")
    server.start()

