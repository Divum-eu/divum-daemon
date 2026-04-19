import requests

VALID_MINECRAFT_VERSIONS: set[str] = {"LATEST", "SNAPSHOT"}

def fetch_mojang_versions() -> None:
    """Hits the Mojang API and updates the in-memory cache."""
    try:
        response = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest.json", timeout=5)
        response.raise_for_status()
        data = response.json()

        # Add the newly fetched versions to global set
        for version in data.get("versions", []):
            # for version in version_list:
                VALID_MINECRAFT_VERSIONS.add(version["id"])

        # TODO: log the update
        print(f"[Cache] Updated Mojang versions. Total known: {len(VALID_MINECRAFT_VERSIONS)}")

    except Exception as e:
        # If Mojang is down, just print log the error and continue using whatever is already in the cache.
        # TODO: log the error
        print(f"[Warning] Failed to fetch Mojang version manifest: {e}")

fetch_mojang_versions()
