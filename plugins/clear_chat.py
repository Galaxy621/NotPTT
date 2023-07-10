import PTServer
import PTCommand

class ClearChat(PTCommand.Command):
    Name = "clear"
    Description = "Clears all chat messages"
    Args = []
    IsAdmin = False

    def run(self, args: list[str], client: PTServer.Client):
        client.Chat.clear()
        client.server_pm("Chat cleared")

def setup(server: PTServer.Server):
    server.register_command(ClearChat(server=server))