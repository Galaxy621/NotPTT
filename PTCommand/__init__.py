from __future__ import annotations

from enum import Enum

import PTServer

class FailedCommand(Enum):
    """Enum for failed command reasons."""
    InvalidArgs = 0
    NotAdmin = 1
    FailureExecuting = 2

class Command:
    """Base class for commands."""
    # self.name = name
    # self.description = description
    # self.args = args
    # self.is_admin = is_admin

    Name: str
    Description: str
    Args: list[str]
    IsAdmin: bool

    def __init__(self, server: PTServer.Server):
        self.Server = server

    def count_args(self) -> tuple(int, int):
        """Returns the number of required and optional args."""
        optional = 0
        required = 0

        for arg in self.Args:
            if arg.startswith("[") and arg.endswith("]"):
                optional += 1
            else:
                required += 1

        return required, optional

    def check_args(self, args: list[str]) -> bool:
        required_count, optional_count = self.count_args()

        if len(args) not in range(required_count, required_count + optional_count + 1):
            return False
        
        return True

    def run(self, args: list[str], client: PTServer.Client):
        """Run the command with the given args."""
        raise NotImplementedError()
    
    def _run(self, args: list[str], client: PTServer.Client) -> tuple[bool, FailedCommand] | None:
        """Run the command with the given args. Checks if args are valid."""
        if not self.check_args(args):
            return False, FailedCommand.InvalidArgs
        
        if self.IsAdmin and not client.Admin:
            return False, FailedCommand.NotAdmin
        
        try:
            return self.run(args, client)
        except Exception as e:
            print(e)
            return False, FailedCommand.FailureExecuting

    def __str__(self):
        # Example: '  /nick <name> - Changes your name"'
        return f"/{self.Name} {' '.join(self.Args)} - {self.Description}"
    
    def __repr__(self):
        return str(self)
