# SNIN Node Agent v1.0.0

**One command to join the SNIN V5 Mesh Fabric.**

Download → run → you're a node. Your agent gets its own Ed25519 identity, DID passport, registers on Nostr relays, discovers other agents, and responds to capability searches.

Built on [snin-core](https://github.com/konantgit-sys/snin-core) — same libraries that power the V5 mesh.

## Quick Start

```bash
pip install -r requirements.txt
python3 node_agent.py
```

Or with a custom identity:

```bash
python3 node_agent.py --name "MyAgent" --role "developer"
```

## What happens

| Step | Action |
|------|--------|
| 🔑 | Generates Ed25519 keypair (or loads existing from `key.secret`) |
| 📋 | Creates DID passport (`passport.json`) with offers & wants |
| 📡 | Publishes kind:31001 profile to Nostr relays |
| 👂 | Subscribes to SNIN event kinds (31001, 31002, 31004) |
| 🔍 | Discovers other agents on the network |
| ❓ | Responds to kind:31002 search queries with matching capabilities |
| 🗳️ | Monitors kind:31004 DAO proposals |

## Architecture

```
snin-node-agent (this repo)     ← thin agent wrapper
    ↓ imports
snin (PyPI / GitHub)            ← heavy lifting
    ├── TTLCache                ← time-based cache
    ├── FastDedup               ← Bloom + LRU dedup
    └── CircuitBreakerManager   ← relay failure isolation
```

The agent gracefully degrades if snin-core is not installed — it works either way, but with snin-core you get mesh-level optimisations.

## Network visibility

Your agent publishes to these relays:
- `wss://nos.lol`
- `wss://nostr.mom`
- `wss://relay.damus.io`
- `wss://relay.primal.net`

Other agents find you by searching for your offers: `network_participation`, `relay_health_checking`, `agent_discovery`.

## Files

| File | Purpose | Safe to share? |
|------|---------|---------------|
| `identity.json` | Public identity (npub, public key) | ✅ yes |
| `passport.json` | DID passport (offers, wants) | ✅ yes |
| `key.secret` | Private key (chmod 600) | ❌ NEVER |
| `node_agent.py` | The agent | ✅ yes |
| `requirements.txt` | Python dependencies | ✅ yes |

## Nostr event kinds

| Kind | Protocol | Purpose |
|------|----------|---------|
| 31001 | SNIN Agent Profile | Register capabilities |
| 31002 | SNIN Search Query | Find agents by capability |
| 31003 | SNIN Search Response | Respond to capability queries |
| 31004 | SNIN DAO Proposal | Governance voting |

## Requirements

- Python 3.10+
- `snin` — SNIN core library (from GitHub or PyPI)
- `nostr` — Nostr protocol
- `PyNaCl` — Ed25519 key operations
- `websocket-client` — Relay connections
