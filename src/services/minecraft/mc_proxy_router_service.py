import os

import aiohttp

from services.minecraft.proxy_router import ProxyRouter


ROUTER_API_ADDRESS = os.getenv("MC_ROUTER_API_ADDRESS", "")


class MCProxyRouterService(ProxyRouter):

    async def add(self, server_address: str, server_host: str) -> bool:
        """Add an entry to the itzg/mc-router hosts"""
        print("add to router")

        if server_address.strip() == "" or server_host.strip() == "":
            return False

        # Check if the given server_address is already registered to avoid record override
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ROUTER_API_ADDRESS}/routes") as response:
                if 200 <= response.status < 300:
                    records: dict[str, dict[str, str]] = await response.json()
                    if server_address in records.keys():
                        return False # TODO: implement internal codes
                else:
                    return False

        # Register the record
            async with session.post(f"{ROUTER_API_ADDRESS}/routes",
                                    json={"serverAddress": server_address, "backend": server_host}) as response:

                return 200 <= response.status < 300

    async def remove(self, server_host: str) -> bool:

        # Find the server address of the given server host
        server_address: str | None = None
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ROUTER_API_ADDRESS}/routes") as response:
                if 200 <= response.status < 300:
                    records: dict[str, dict[str, str]] = await response.json()
                    for address, data in records.items():
                        if data["backend"] == server_host:
                            server_address = address

        if not server_address:
            return False

        # Delete the found server address
        async with session.delete(f"{ROUTER_API_ADDRESS}/routes/{server_address}") as response:
            return 200 <= response.status < 300
