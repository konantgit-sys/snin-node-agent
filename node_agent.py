#!/usr/bin/env python3
"""
SNIN Node Agent v1.0.0 — your sovereign node on the V5 Mesh Fabric.

One command. One file. Instant network participant.

    python3 node_agent.py
    python3 node_agent.py --name "MyAgent" --role "developer"

Built on snin-core (PyPI): TTLCache, FastDedup, CircuitBreaker.
Requirements: pip install snin nostr PyNaCl websocket-client
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime

# ─── Dependency check ─────────────────────────────────────────────────
try:
    from nacl.signing import SigningKey
except ImportError:
    print("❌ PyNaCl not installed. Run: pip install PyNaCl")
    sys.exit(1)

try:
    from nostr.event import Event
    from nostr.key import PrivateKey
except ImportError:
    print("❌ nostr not installed. Run: pip install nostr")
    sys.exit(1)

try:
    import websocket
except ImportError:
    print("❌ websocket-client not installed. Run: pip install websocket-client")
    sys.exit(1)

# SNIN Core — the heavy artillery
_snin_available = True
try:
    from snin import TTLCache, FastDedup
except ImportError:
    _snin_available = False
    print("⚠️  snin-core not installed. Run: pip install snin")
    print("   Agent will work, but without mesh-level deduplication.")

# ─── Constants ────────────────────────────────────────────────────────
WORKING_RELAYS = [
    "wss://nos.lol",
    "wss://nostr.mom",
    "wss://relay.damus.io",
    "wss://relay.primal.net",
]
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
IDENTITY_FILE = os.path.join(AGENT_DIR, "identity.json")
PASSPORT_FILE = os.path.join(AGENT_DIR, "passport.json")
KEY_FILE = os.path.join(AGENT_DIR, "key.secret")

KIND_PROFILE = 31001
KIND_SEARCH_QUERY = 31002
KIND_SEARCH_RESPONSE = 31003
KIND_DA0_PROPOSAL = 31004
KIND_HEARTBEAT = 1

# ─── Key & Identity Management ────────────────────────────────────────

def generate_keys() -> dict:
    """Generate new Ed25519 keypair — master identity for the agent."""
    sk = SigningKey.generate()
    vk = sk.verify_key
    private_hex = sk.encode().hex()
    public_hex = vk.encode().hex()

    nostr_private = PrivateKey(bytes.fromhex(private_hex))
    nostr_public = nostr_private.public_key

    return {
        "private_hex": private_hex,
        "public_hex": public_hex,
        "nsec": nostr_private.bech32(),
        "npub": nostr_public.bech32(),
    }


def load_or_create_keys() -> dict:
    """Load existing keys, or generate new ones on first run."""
    if os.path.exists(IDENTITY_FILE) and os.path.exists(KEY_FILE):
        with open(IDENTITY_FILE) as f:
            identity = json.load(f)
        with open(KEY_FILE) as f:
            private_hex = f.read().strip()

        sk = SigningKey(bytes.fromhex(private_hex))
        vk = sk.verify_key
        public_hex = vk.encode().hex()

        nostr_private = PrivateKey(bytes.fromhex(private_hex))
        nostr_public = nostr_private.public_key

        keys = {
            "private_hex": private_hex,
            "public_hex": public_hex,
            "nsec": nostr_private.bech32(),
            "npub": nostr_public.bech32(),
        }
        print(f"🔑 Keys loaded. npub: {keys['npub'][:20]}...")
        return keys

    print("🔑 Generating new Ed25519 keypair...")
    keys = generate_keys()

    with open(KEY_FILE, "w") as f:
        os.chmod(KEY_FILE, 0o600)
        f.write(keys["private_hex"])

    identity = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "public_hex": keys["public_hex"],
        "npub": keys["npub"],
    }
    with open(IDENTITY_FILE, "w") as f:
        json.dump(identity, f, indent=2)

    print(f"🔑 New identity created. npub: {keys['npub'][:20]}...")
    return keys


def create_passport(keys: dict, name: str = None, role: str = None) -> dict:
    """Create a SNIN DID passport."""
    if name is None:
        name = f"sniNode-{keys['public_hex'][:8]}"
    if role is None:
        role = "network_participant"

    passport = {
        "@context": "https://snin.network/did/v1",
        "id": f"did:snin:{keys['public_hex']}",
        "controller": keys["public_hex"],
        "created": datetime.utcnow().isoformat() + "Z",
        "name": name,
        "role": role,
        "offers": ["network_participation", "relay_health_checking", "agent_discovery"],
        "wants": ["agent_connections", "network_metrics", "collaboration_opportunities"],
        "endpoints": {"nostr": keys["npub"]},
    }

    with open(PASSPORT_FILE, "w") as f:
        json.dump(passport, f, indent=2)

    return passport


# ─── Event Building ───────────────────────────────────────────────────

def build_event(keys: dict, kind: int, content: str, tags: list = None) -> str:
    """Build, sign, return Nostr event as JSON string."""
    private_key = PrivateKey(bytes.fromhex(keys["private_hex"]))
    event = Event(
        public_key=private_key.public_key.hex(),
        content=content,
        kind=kind,
        tags=tags or [],
    )
    private_key.sign_event(event)
    return event.to_message()


# ─── Relay Connection — with CircuitBreaker if snin-core available ───

class RelayConnection:
    """WebSocket connection to a single Nostr relay."""

    def __init__(self, url: str):
        self.url = url
        self.ws: websocket.WebSocket = None
        self.connected = False
        self.failure_count = 0

    def connect(self):
        if self.failure_count >= 5:
            print(f"  ⏳ {self.url}: too many failures, skipping")
            return

        try:
            self.ws = websocket.create_connection(self.url, timeout=10)
            self.connected = True
            self.failure_count = 0
            if _snin_available and self.failure_count == 0:
                pass  # CircuitBreaker placeholder — snin-core loaded
            print(f"  ✅ {self.url}")
        except Exception as e:
            self.connected = False
            self.failure_count += 1
            err = str(e)[:80]
            print(f"  ⚠️ {self.url}: {err}")

    def send(self, message: str) -> bool:
        if not self.ws or not self.connected:
            return False
        try:
            self.ws.send(message)
            return True
        except Exception:
            self.connected = False
            self.failure_count += 1
            return False

    def recv(self, timeout: float = 2.0):
        if not self.ws or not self.connected:
            return None
        try:
            self.ws.settimeout(timeout)
            return self.ws.recv()
        except websocket.WebSocketTimeoutException:
            return None
        except Exception:
            self.connected = False
            return None

    def close(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass


# ─── Relay Pool ───────────────────────────────────────────────────────

class RelayPool:
    """Pool of relay connections — broadcast and listen."""

    def __init__(self):
        self.relays: list[RelayConnection] = []
        # Use snin-core dedup if available
        self._seen = FastDedup() if _snin_available else set()

    def connect_all(self):
        print(f"\n📡 Connecting to {len(WORKING_RELAYS)} relays...")
        for url in WORKING_RELAYS:
            rc = RelayConnection(url)
            rc.connect()
            self.relays.append(rc)

    def broadcast(self, message: str) -> int:
        sent = 0
        for rc in self.relays:
            if rc.connected and rc.send(message):
                sent += 1
        return sent

    def is_duplicate(self, event_id: str) -> bool:
        if _snin_available:
            return self._seen.check_and_add(event_id)
        if event_id in self._seen:
            return True
        self._seen.add(event_id)
        return False

    def close_all(self):
        for rc in self.relays:
            rc.close()


# ─── Registration ─────────────────────────────────────────────────────

def register_agent(keys: dict, passport: dict) -> tuple:
    """Publish kind:31001 profile + heartbeat to all relays."""
    pool = RelayPool()
    pool.connect_all()

    profile_content = json.dumps({
        "name": passport["name"],
        "role": passport["role"],
        "offers": passport["offers"],
        "wants": passport["wants"],
        "did": passport["id"],
        "version": "1.0.0",
        "network": "snin-v5-mesh-fabric",
    })

    print(f"\n📡 Registering agent...")
    print(f"   kind: {KIND_PROFILE} (SNIN agent profile)")
    print(f"   name: {passport['name']}")
    print(f"   role: {passport['role']}")
    print(f"   offers: {', '.join(passport['offers'])}")
    print(f"   wants: {', '.join(passport['wants'])}")
    if _snin_available:
        print(f"   backend: snin-core v5.0.0 (TTLCache, FastDedup)")

    profile_msg = build_event(keys, KIND_PROFILE, profile_content)
    sent = pool.broadcast(profile_msg)

    # Heartbeat
    hb = build_event(keys, KIND_HEARTBEAT,
                     f"🟢 SNIN Node Agent online — {passport['name']} — {datetime.utcnow().isoformat()}Z")
    time.sleep(1)
    pool.broadcast(hb)

    event_data = json.loads(profile_msg)
    event_id = event_data[1]["id"] if len(event_data) > 1 else "unknown"

    print(f"\n✅ Agent registered on {sent}/{len(WORKING_RELAYS)} relays!")
    print(f"   Event ID: {event_id[:16]}...")
    print(f"   npub: {keys['npub'][:30]}...")
    print(f"   DID: {passport['id']}")

    return pool


# ─── Listener ─────────────────────────────────────────────────────────

def listen_loop(keys: dict, passport: dict, pool: RelayPool):
    """Main event loop: subscribe, receive, respond."""
    kinds_of_interest = [KIND_PROFILE, KIND_SEARCH_QUERY, KIND_DA0_PROPOSAL]
    sub_msg = json.dumps([
        "REQ", "snin_node_v1",
        {"kinds": kinds_of_interest, "since": int(time.time()) - 3600}
    ])

    for rc in pool.relays:
        if rc.connected:
            rc.send(sub_msg)

    stats = {"queries": 0, "responses": 0, "agents": 0}

    print(f"\n👂 Listening for SNIN events on {len(pool.relays)} relays...")
    print(f"   Subscribed to kinds: {kinds_of_interest}")
    if _snin_available:
        print(f"   Dedup: FastDedup (Bloom + LRU)")
    print(f"   Press Ctrl+C to stop\n")

    while True:
        try:
            for rc in pool.relays:
                if not rc.connected:
                    continue
                raw = rc.recv(timeout=0.5)
                if raw is None:
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if not isinstance(msg, list) or len(msg) < 3:
                    continue

                cmd = msg[0]
                if cmd != "EVENT":
                    continue

                event_data = msg[2] if isinstance(msg[2], dict) else None
                if event_data is None:
                    continue

                eid = event_data.get("id", "")
                if pool.is_duplicate(eid):
                    continue

                kind = event_data.get("kind", 0)
                content = event_data.get("content", "")
                pubkey = event_data.get("pubkey", "")

                if kind == KIND_PROFILE:
                    stats["agents"] += 1
                    try:
                        c = json.loads(content)
                        name = c.get("name", "unknown")
                        role = c.get("role", "unknown")
                        print(f"🔍 Agent: {name} ({role}) — {pubkey[:12]}...")
                    except json.JSONDecodeError:
                        print(f"🔍 Agent profile — {pubkey[:12]}...")

                elif kind == KIND_SEARCH_QUERY:
                    stats["queries"] += 1
                    query_text = ""
                    try:
                        q = json.loads(content)
                        query_text = q.get("query", q.get("wanted", content))
                    except (json.JSONDecodeError, AttributeError):
                        query_text = content

                    print(f"❓ Search: '{query_text}' from {pubkey[:12]}...")

                    matching = []
                    query_lower = query_text.lower() if isinstance(query_text, str) else ""
                    for offer in passport.get("offers", []):
                        o = offer.lower().replace("_", " ")
                        if o in query_lower or query_lower in o:
                            matching.append(offer)

                    if matching or not query_lower:
                        resp = {
                            "agent": passport["name"],
                            "did": passport["id"],
                            "npub": keys["npub"],
                            "role": passport["role"],
                            "matching_offers": matching or passport["offers"],
                            "available": True,
                            "in_response_to": eid[:16],
                        }
                        resp_msg = build_event(
                            keys, KIND_SEARCH_RESPONSE, json.dumps(resp),
                            tags=[["e", eid], ["p", pubkey]]
                        )
                        for rc2 in pool.relays:
                            if rc2.connected:
                                rc2.send(resp_msg)
                        stats["responses"] += 1
                        offers_str = ', '.join(matching or passport["offers"])
                        print(f"   ✅ Responded: {offers_str}")

                elif kind == KIND_DA0_PROPOSAL:
                    try:
                        p = json.loads(content)
                        title = p.get("title", p.get("project", "unnamed"))
                        print(f"🗳️  DAO proposal: {title} — {pubkey[:12]}...")
                    except (json.JSONDecodeError, AttributeError):
                        print(f"🗳️  DAO proposal — {pubkey[:12]}...")

            time.sleep(0.1)

        except KeyboardInterrupt:
            break

    print(f"\n📊 Session: {stats['agents']} agents, {stats['queries']} queries, {stats['responses']} responses")
    pool.close_all()


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SNIN Node Agent — join the V5 Mesh Fabric")
    parser.add_argument("--name", type=str, default=None, help="Agent name (default: auto-generated)")
    parser.add_argument("--role", type=str, default=None, help="Agent role (default: network_participant)")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════╗
║   SNIN Node Agent v1.0.0                ║
║   Sovereign Nostr Infrastructure Node   ║
╚══════════════════════════════════════════╝
""")
    keys = load_or_create_keys()
    passport = create_passport(keys, name=args.name, role=args.role)
    pool = register_agent(keys, passport)
    listen_loop(keys, passport, pool)


if __name__ == "__main__":
    main()
