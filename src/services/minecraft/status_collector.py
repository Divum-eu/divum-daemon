import asyncio
import re
from docker.models.containers import Container
from services.minecraft.docker_server_manager import DockerServerManager

async def collect_status(server_manager: DockerServerManager, server_id: str) -> dict:
    container: Container | None = await server_manager._get_container(server_id)
    if not container:
        return {
            "server_id": server_id,
            "status": "unreachable",
            "cpu_percent": 0.0,
            "memory_usage_mb": 0,
            "memory_limit_mb": 0,
            "player_count": None,
            "player_max": None
        }

    status_val = container.status
    is_running = (status_val == "running")

    if not is_running:
        return {
            "server_id": server_id,
            "status": status_val,
            "cpu_percent": 0.0,
            "memory_usage_mb": 0,
            "memory_limit_mb": 0,
            "player_count": None,
            "player_max": None
        }

    # If running, calculate stats
    try:
        stats = await asyncio.to_thread(container.stats, stream=False)
        
        # Memory
        mem_usage = stats.get('memory_stats', {}).get('usage', 0)
        cache = stats.get('memory_stats', {}).get('stats', {}).get('inactive_file', 0)
        limit = stats.get('memory_stats', {}).get('limit', 0)
        
        working_set_mem = max(0, mem_usage - cache)
        memory_usage_mb = int(working_set_mem / (1024 * 1024))
        memory_limit_mb = int(limit / (1024 * 1024))
        
        # CPU
        cpu_usage = stats.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
        precpu_usage = stats.get('precpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
        system_cpu = stats.get('cpu_stats', {}).get('system_cpu_usage', 0)
        presystem_cpu = stats.get('precpu_stats', {}).get('system_cpu_usage', 0)
        
        cpu_delta = cpu_usage - precpu_usage
        system_delta = system_cpu - presystem_cpu
        percpu_usage = stats.get('cpu_stats', {}).get('cpu_usage', {}).get('percpu_usage')
        online_cpus = stats.get('cpu_stats', {}).get('online_cpus', len(percpu_usage) if percpu_usage else 1)
        
        if system_delta > 0.0 and cpu_delta > 0.0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
        else:
            cpu_percent = 0.0
            
    except Exception as e:
        print(f"Error fetching stats for {server_id}: {e}")
        memory_usage_mb = 0
        memory_limit_mb = 0
        cpu_percent = 0.0

    # Player count via RCON
    player_count = None
    player_max = None
    try:
        async def run_rcon():
            return await asyncio.to_thread(container.exec_run, "rcon-cli list")
            
        exit_code, output = await asyncio.wait_for(run_rcon(), timeout=1.5)
        
        if exit_code == 0:
            output_str = output.decode("utf-8")
            # Parse count: "There are 3 of a max of 20 players online: Player1, Player2, Player3"
            match = re.search(r"There are (\d+) of a max of (\d+)", output_str)
            if match:
                player_count = int(match.group(1))
                player_max = int(match.group(2))
    except Exception as e:
        print(f"Error fetching rcon for {server_id}: {e}")
        pass
        
    return {
        "server_id": server_id,
        "status": status_val,
        "cpu_percent": round(cpu_percent, 2),
        "memory_usage_mb": memory_usage_mb,
        "memory_limit_mb": memory_limit_mb,
        "player_count": player_count,
        "player_max": player_max
    }
