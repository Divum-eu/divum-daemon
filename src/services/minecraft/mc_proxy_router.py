import os

import aiohttp

from services.minecraft.proxy_router import ProxyRouter


ROUTER_API_ADDRESS = os.getenv("MC_ROUTER_API_ADDRESS", "")


class MCProxyRouter(ProxyRouter):

    async def add(self, server_address: str, server_host: str) -> bool:
        """Add an entry to the itzg/mc-router hosts"""

        if server_address.strip() == "" or server_host.strip() == "":
            return False

        # Check if the given server_address is already registered to avoid record override
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ROUTER_API_ADDRESS}/routes") as response:
                records: dict[str, dict[str, str]] = await response.json()
                if server_address in records.keys():
                    return False # TODO: implement internal codes

        # Register the record
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{ROUTER_API_ADDRESS}/routes",
                                    json={"serverAddress": server_address, "backend": server_host}) as response:

                return 200 <= response.status < 300

    async def remove(self, server_address: str) -> bool:
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{ROUTER_API_ADDRESS}/routes/{server_address}") as response:
                return 200 <= response.status < 300
