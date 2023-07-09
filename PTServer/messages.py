from dataclasses import dataclass
from enum import Enum

class MessageType(Enum):
    MsgNone = 0
    ImsgLogin = 1
    ImsgDefault = 2
    ImsgPaused = 3
    ImsgMessage = 4

    OmsgDefault = 5
    OmsgAccepted = 6
    OmsgDisconnect = 7
    OmsgKick = 8
    OmsgAnnouncement = 9

@dataclass
class CompactMessage:
    Type: int
    Msg: str

    def to_json(self):
        return {
            "type": self.Type,
            "msg": self.Msg
        }

@dataclass
class CompactClient:
    ID: int
    X: float
    Y: float
    Name: str
    Admin: bool
    Room: int

    Sprite: str
    Frame: int
    Direction: int
    Palette: int
    PaletteSprite: str
    PaletteTexture: str
    Color: str

    def to_json(self):
        return {
            "id": self.ID,
            "x": self.X,
            "y": self.Y,
            "name": self.Name,
            "admin": self.Admin,
            "room": self.Room,
            "sprite": self.Sprite,
            "frame": self.Frame,
            "direction": self.Direction,
            "palette": self.Palette,
            "paletteSprite": self.PaletteSprite,
            "paletteTexture": self.PaletteTexture,
            "color": self.Color
        }

@dataclass
class Message:
    Body: str
    Username: str
    Id: int
    Mid: int = 0

    def to_json(self):
        return {
            "body": self.Body,
            "username": self.Username,
            "id": self.Id,
            "mid": self.Mid
        }