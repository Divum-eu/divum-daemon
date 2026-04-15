import hashlib
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator, ValidationError

# Config follows the documentation at: https://docker-minecraft-server.readthedocs.io/en/latest/variables/
class MinecraftServerITZGConfig(BaseModel):
    container_name: str = Field(..., min_length=3, max_length=50)

    # ---------------- GENERAL OPTIONS ----------------
    memory: int = Field(default=2, ge=1, le=16)
    cpu_cores: float = Field(default=1.0, gt=0.0, le=8.0)

    # ---------------- SERVER ----------------
    type: str = Field(default="PAPER")
    eula: bool = Field(default=True)
    version: str = Field(default="LATEST")
    motd: str = Field(default="Brought to you by Divum. Enjoy!")
    difficulty: str = Field(default="easy")
    mode: str = Field(default="survival")
    level: str = Field(default="world")
    online_mode: bool = Field(default=True)

    # ---------------- CUSTOM RESOURCE PACK ----------------
    resource_pack: str = Field(default="")
    resource_pack_sha1: str = Field(default="")
    resource_pack_enforce: bool = Field(default=False)

    # ---------------- WHITELIST ----------------
    enable_whitelist: bool = Field(default=False)
    whitelist: list[str] = Field(default=[])
    override_whitelist: bool = Field(default=False)

    # ---------------- RCON ----------------
    enable_rcon: bool = Field(default=True)
    rcon_password: str = Field(...)
    broadcast_rcon_to_ops: bool = Field(default=False)
    rcon_cmds_startup: str = Field(default="")
    rcon_cmds_on_connect: str = Field(default="")
    rcon_cmds_first_connect: str = Field(default="")
    rcon_cmds_on_disconnect: str = Field(default="")
    rcon_cmds_last_disconnect: str = Field(default="")

    # ---------------- SERVER PROPERTIES ----------------
    ops: list[str] = Field(default=[])
    op_permission_level: int = Field(default=0, ge=0, le=4)
    icon: str = Field(default="")
    override_icon: bool = Field(default=False)
    seed: str = Field(default="")
    level_type: str = Field(default="NORMAL")
    custom_server_properties: list[str] = Field(default=[])
    pvp: bool = Field(default=True)
    server_name: str = Field(...)

    # ---------------- FABRIC VARIABLES ----------------
    fabric_launcher_version: str = Field(default="LATEST")
    fabric_loader_version: str = Field(default="LATEST")

    # TODO: add support for all server types that are listed in SERVER_TYPES class variable

    # ---------------- CLASS VARIABLES ----------------

    # Detailed documentation about server types and their requirements: https://docker-minecraft-server.readthedocs.io/en/latest/types-and-platforms/
    # Server types are formatted for easy of use of the documentation so every line of types will be on the same page
    SERVER_TYPES: ClassVar[set[str]] = {
                                        # Under "Server types" in the documentation
                                        "VANILLA",
                                        "BUKKIT", "SPIGOT",
                                        "FABRIC",
                                        "FORGE", "NEOFORGE",
                                        "MAGMA", "MAGMA_MAINTAINED", "KETTING", "MOHIST", "YOUER", "BANNER", "ARCLIGHT",
                                        "SPONGEVANILLA", "LIMBO", "NANOLIMBO", "CRUCIBLE",
                                        "PAPER", "PUFFERFISH", "PURPUR", "LEAF", "FOLIA",
                                        "QUILT",

                                        # Under "Mod platforms" in the documentation
                                        "AUTO_CURSEFORGE",
                                        "FTBA",
                                        "GTNH",
                                        "MODRINTH"
                                        }

    DIFFICULTY_LEVELS: ClassVar[set[str]] = {"peaceful", "easy", "normal", "hard"}

    MODE_TYPES: ClassVar[set[str]] = {"creative", "survival", "adventure", "spectator"}

    LEVEL_TYPES: ClassVar[set[str]] = {"NORMAL", "FLAT", "LARGE_BIOMES", "AMPLIFIED", "SINGLE_BIOME_SURFACE"}

    # ---------------- FIELD VALIDATORS ----------------

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v.upper() not in cls.SERVER_TYPES:
            raise ValueError(f"Server type {v} is not supported.")

        return v

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        if v.lower() not in cls.DIFFICULTY_LEVELS:
            raise ValueError(f"Difficulty level {v} is not supported.")

        return v.lower()

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v.lower() not in cls.MODE_TYPES:
            raise ValueError(f"Server mode {v} is not supported.")

        return v.lower()

    @field_validator("level_type")
    @classmethod
    def validate_level_type(cls, v: str) -> str:
        if v.upper() not in cls.LEVEL_TYPES:
            raise ValueError(f"Level type {v} is not supported")

        return v.upper()

    @field_validator("server_name")
    @classmethod
    def validate_server_name(cls, v: str):
        if ":" in v:
            raise ValueError(f"Server name cannot contain ':'")

        return v

    @field_validator("rcon_password")
    @classmethod
    def validate_rcon_password(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("RCON password must be set")

        return v.strip()

    def to_docker_env(self) -> dict[str, str]:
        """Converts the config model into the environment dictionary expected by the itzg image."""

        # 1. Base required and formatted variables
        env = {
            "MEMORY": f"{self.memory}G",
            "TYPE": self.type.upper(),
            "EULA": "TRUE" if self.eula else "FALSE",
            "VERSION": self.version,
            "MOTD": self.motd,
            "DIFFICULTY": self.difficulty,
            "MODE": self.mode,
            "LEVEL": self.level,
            "LEVEL_TYPE": self.level_type,
            "SEED": self.seed,
            "ONLINE_MODE": "TRUE" if self.online_mode else "FALSE",
            "OP_PERMISSION_LEVEL": self.op_permission_level,
            "PVP": "TRUE" if self.pvp else "FALSE",
            "SERVER_NAME": self.server_name,

            # Booleans must be explicit strings for the bash scripts
            "RESOURCE_PACK_ENFORCE": "TRUE" if self.resource_pack_enforce else "FALSE",
            "ENABLE_WHITELIST": "TRUE" if self.enable_whitelist else "FALSE",
            "OVERRIDE_WHITELIST": "TRUE" if self.override_whitelist else "FALSE",
            "ENABLE_RCON": "TRUE" if self.enable_rcon else "FALSE",
            "BROADCAST_RCON_TO_OPS": "TRUE" if self.broadcast_rcon_to_ops else "FALSE",
        }

        # 2. Optional Strings (Only add them if they aren't empty to keep the container clean)
        if self.resource_pack:
            env["RESOURCE_PACK"] = self.resource_pack
        if self.resource_pack_sha1:
            env["RESOURCE_PACK_SHA1"] = self.resource_pack_sha1
        if self.resource_pack and self.resource_pack_sha1:
            self.resource_pack_enforce = True

        if self.rcon_password:
            env["RCON_PASSWORD"] = self.rcon_password
        if self.rcon_cmds_startup:
            env["RCON_CMDS_STARTUP"] = self.rcon_cmds_startup
        if self.rcon_cmds_on_connect:
            env["RCON_CMDS_ON_CONNECT"] = self.rcon_cmds_on_connect
        if self.rcon_cmds_first_connect:
            env["RCON_CMDS_FIRST_CONNECT"] = self.rcon_cmds_first_connect
        if self.rcon_cmds_on_disconnect:
            env["RCON_CMDS_ON_DISCONNECT"] = self.rcon_cmds_on_disconnect
        if self.rcon_cmds_last_disconnect:
            env["RCON_CMDS_LAST_DISCONNECT"] = self.rcon_cmds_last_disconnect

        # 3. List Conversions
        if self.whitelist and self.online_mode:
            # itzg image expects a comma-separated string for the whitelist
            env["WHITELIST"] = ",".join(self.whitelist)
            env["OVERRIDE_WHITELIST"] = "TRUE"
            # env["RCON_CMDS_STARTUP"] = '\n'.join([f"whitelist add {username}" for username in self.whitelist])

        if self.ops:
            # itzg image expects a comma-separated string for the ops
            env["OPS"] = ",".join(self.ops)

        if self.icon:
            env["ICON"] = self.icon
            env["OVERRIDE_ICON"] = "TRUE"

        if self.custom_server_properties:
            # itzg image expects a newline-separated string for the custom server properties
            env["CUSTOM_SERVER_PROPERTIES"] = '\n'.join(self.custom_server_properties)

        # 4. Conditional Platform Variables (Only inject Fabric vars if actually running Fabric)
        if self.type.upper() == "FABRIC":
            if self.fabric_launcher_version.upper() != "LATEST":
                env["FABRIC_LAUNCHER_VERSION"] = self.fabric_launcher_version
            if self.fabric_loader_version.upper() != "LATEST":
                env["FABRIC_LOADER_VERSION"] = self.fabric_loader_version

        return env