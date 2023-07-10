from dataclasses import dataclass

@dataclass
class Config:
    Host: str
    Port: int
    Timeout: int
    MaxPlayers: int
    MaxConnections: int
    
    Anticheat: bool

    Keys: list[str]
    Bans: list[str]
    BadWords: list[str]

