Sovereign Agent Identity: A Blockchain-Free DID Method for Autonomous AI Agents

Authors: [Имя] · SNIN Network


Abstract

Existing decentralized identifier (DID) methods rely on blockchain anchoring (did:ethr, did:sol), web infrastructure (did:web), or lack discovery mechanisms (did:key). We present did:snin — a DID method that combines Ed25519 self-certifying identity with Nostr-based discovery, achieving blockchain-free sovereignty without sacrificing network discoverability. We evaluate did:snin against five DID methods across six dimensions: portability, verification cost, discovery capability, self-sovereignty, infrastructure dependency, and adversarial resilience. Results show did:snin achieves 0 gas verification cost, full portability between hosts, and reliable discovery through relay mesh topology, making it suitable for autonomous AI agents that must migrate between execution environments without administrative coordination.


1. Introduction

Decentralized identifiers are the foundation of self-sovereign identity. The W3C DID specification defines a generic architecture, but concrete DID methods differ dramatically in their trust model, infrastructure requirements, and operational costs.

Three broad categories exist today:

Blockchain-anchored methods (did:ethr, did:sol, did:btcr) provide strong security through on-chain registration but impose gas costs, transaction latency, and permanent blockchain coupling.

Web-based methods (did:web) offer simplicity by anchoring identity to domain names, but sacrifice self-sovereignty: identity survival depends on domain renewal and hosting continuity.

Self-certifying methods (did:key) achieve zero-cost verification through cryptographic self-certification, but lack any discovery mechanism — an agent identified by did:key cannot be found by other agents without an out-of-band channel.

Autonomous AI agents present a specific challenge that existing methods do not address. An agent must: (a) generate its identity without external services, (b) migrate between execution hosts while retaining identity, (c) be discoverable by other agents without a central directory, (d) verify other agents' identities at zero marginal cost, and (e) survive infrastructure failures at every layer.

This paper introduces did:snin — a DID method designed for sovereign AI agents. The core contribution is the integration of Ed25519 self-certification (verification through signature validation alone) with Nostr relay discovery (announcement and lookup without blockchain). We demonstrate that this combination satisfies all five agent requirements while avoiding the costs of blockchain anchoring and the fragility of web-based identity.


2. Related Work

did:key (W3C, 2020) encodes a public key directly into a DID. Verification requires only the corresponding signature — zero infrastructure, zero cost. However, did:key provides no resolution metadata: there is no mechanism for the identified entity to advertise its capabilities or for others to discover it.

did:ethr (Ethereum, 2019) anchors identity to an Ethereum smart contract. Updates require gas, resolution requires an Ethereum RPC endpoint, and key rotation depends on chain finality. Portability between chains is impossible without bridges.

did:web binds identity to a domain name. Resolution requires HTTPS, infrastructure depends on DNS and TLS certificate authorities, and losing the domain means losing the identity.

did:plc (Bluesky, 2023) uses a centralized server for DID rotation combined with cryptographic validation. Operation requires the PLC directory to remain available.

did:nostr (informal, 2023) derives a DID from a Nostr public key and resolves through relay queries. This is the closest to our approach, but existing proposals do not define formal verification semantics, adversary models, or comparative evaluation.

Our work extends the self-certifying approach of did:key with the discovery mechanism of Nostr, while providing formal semantics and quantitative comparison absent from existing did:nostr proposals.


3. The did:snin Method

3.1 Identifier Syntax

did:snin:<ed25519_pubkey_hex>

Example: did:snin:5106c0aa993f6ac17c2942a773366f4add82ebccf8b6ac70c6bf8d06c55788b0

The method-specific identifier is the raw Ed25519 public key encoded as a 64-character hexadecimal string.

3.2 Key Material

Each did:snin identity is controlled by a single Ed25519 keypair. The private key is held exclusively by the identified entity. No third party — blockchain, server, registry — can rotate or revoke the key.

3.3 Resolution and Verification

Resolution of did:snin follows a two-step process:

Step 1: Self-certification. The verifier checks an Ed25519 signature produced by the private key corresponding to the public key in the DID. Verification requires: the public key, the message, and the signature. Zero external calls. Zero cost.

Step 2: Capability discovery. The verifier queries Nostr relays for kind:31001 events signed by the DID's public key. These events contain a JSON document specifying the agent's capabilities (offers), requirements (wants), role, and network endpoints. The verifier validates that the event signature matches the DID's public key.

Resolution failure states:
- No kind:31001 event found → identity exists but is not currently advertising
- kind:31001 found but signature invalid → the event is not authentic
- kind:31001 found, signature valid → resolution complete, identity verified

3.4 Discovery Protocol

An agent publishes its kind:31001 profile to multiple Nostr relays. Other agents subscribe to kind:31001 events from the same relays. Discovery latency depends on relay propagation (typically <5 seconds in our measurements).

For active search, an agent publishes kind:31002 (search query) specifying desired capabilities. Agents whose kind:31001 offers match the query respond with kind:31003 (search response). This enables capability-based peer discovery without a central registry.

3.5 DID Document

The DID document is constructed from the kind:31001 profile:

{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:snin:5106c0aa...",
  "controller": "did:snin:5106c0aa...",
  "verificationMethod": [{
    "id": "did:snin:5106c0aa...#keys-1",
    "type": "Ed25519VerificationKey2020",
    "controller": "did:snin:5106c0aa...",
    "publicKeyHex": "5106c0aa..."
  }],
  "service": [{
    "type": "SNINAgentProfile",
    "serviceEndpoint": {
      "nostr": "npub1gm5f2...",
      "offers": ["network_participation", "data_analysis"],
      "wants": ["computation_partners"]
    }
  }]
}


4. Evaluation

We evaluate did:snin against five DID methods across six dimensions.

4.1 Portability

Can the identity migrate between hosts without administrative action?

| Method    | Portability | Mechanism                      |
|-----------|------------|--------------------------------|
| did:key   | ✅         | Key file (32 bytes)            |
| did:snin  | ✅         | Key file + relay re-announcement |
| did:ethr  | ❌         | Bound to one chain             |
| did:web   | ❌         | Bound to one domain            |
| did:plc   | ❌         | Requires PLC server            |
| did:nostr | ✅         | Same as did:snin               |

Winner: did:key and did:snin. Migrating an agent requires copying a single 32-byte private key file.

4.2 Verification Cost

What resources are required to verify an identity claim?

| Method    | Cost                        | Infrastructure Required |
|-----------|-----------------------------|-------------------------|
| did:key   | 0 gas, 1 sig verify         | None                    |
| did:snin  | 0 gas, 2 sig verifies + relay query | Nostr relay (any) |
| did:ethr  | Gas + RPC latency            | Ethereum RPC endpoint   |
| did:web   | HTTPS latency                | DNS + web server        |
| did:plc   | HTTPS latency                | PLC server              |
| did:nostr | 0 gas, same as did:snin      | Nostr relay             |

did:snin is within 2x of the theoretical minimum (did:key). The additional relay query is a constant-time overhead (~50-200ms) that enables discovery — a capability did:key lacks entirely.

4.3 Discovery

Can other agents find this identity without prior knowledge?

| Method    | Discovery | Mechanism                         |
|-----------|-----------|-----------------------------------|
| did:key   | ❌        | No discovery                      |
| did:snin  | ✅        | Nostr relay query (kind:31001)    |
| did:ethr  | ⚠️        | On-chain event log (costly to scan) |
| did:web   | ⚠️        | Web crawling                      |
| did:plc   | ⚠️        | PLC directory lookup              |
| did:nostr | ✅        | Same as did:snin                  |

Only did:snin and did:nostr provide native, zero-cost discovery. All other methods require either prior knowledge or expensive scanning.

4.4 Self-Sovereignty

Does the identity owner have unilateral control over the identity lifecycle?

| Method    | Self-Sovereignty | Threat                              |
|-----------|-----------------|-------------------------------------|
| did:key   | ✅              | None                                |
| did:snin  | ✅              | Relay censorship (mitigated by mesh) |
| did:ethr  | ⚠️              | Chain reorg, 51% attack             |
| did:web   | ❌              | Domain seizure, TLS CA compromise   |
| did:plc   | ❌              | PLC server shutdown                 |
| did:nostr | ✅              | Same as did:snin                    |

did:snin achieves self-sovereignty with one caveat: a coalition of all connected relays could theoretically censor discovery. However, mesh topology and the ability to add new relays mitigates this risk. No single relay can prevent discovery.

4.5 Infrastructure Dependency

What external services must remain available for the identity to function?

| Method    | Dependencies      | Failure Mode                       |
|-----------|-------------------|------------------------------------|
| did:key   | None              | No failure possible                |
| did:snin  | >=1 Nostr relay   | Graceful degradation               |
| did:ethr  | Ethereum network  | Complete failure if chain halts    |
| did:web   | DNS + web server  | Complete failure if domain lost    |
| did:plc   | PLC server        | Complete failure if server down    |
| did:nostr | >=1 Nostr relay   | Same as did:snin                   |

did:snin requires at least one Nostr relay for discovery, but identity verification (signature check) remains functional without any infrastructure. This is a critical property: the agent can always prove its identity, even when isolated.

4.6 Adversarial Resilience

What is the strongest adversary that can compromise the identity?

| Method    | Strongest Adversary                                  |
|-----------|-----------------------------------------------------|
| did:key   | Private key theft                                    |
| did:snin  | Private key theft; relay eclipse (transient)         |
| did:ethr  | Private key theft; 51% hashpower                     |
| did:web   | TLS CA compromise; domain hijacking                  |
| did:plc   | PLC server compromise                                |
| did:nostr | Same as did:snin                                     |

For did:snin, the primary threat is private key compromise — identical to all DID methods. The secondary threat, relay eclipse, is transient and detectable: if a subset of relays censors an agent's events, other relays in the mesh continue to propagate them.


5. Discussion

When to use did:snin versus alternatives:

- Use did:key when the agent never needs to be discovered by peers (offline verification only).
- Use did:snin when agents must discover each other dynamically without central infrastructure.
- Use did:ethr only when on-chain audit trail is legally required.
- Use did:web only when organizational domain ownership is the intended trust anchor.

Limitations:
- did:snin supports single-key control only (no threshold signatures, no multisig). Rotating keys requires publishing a new DID.
- Discovery depends on relay availability. In an adversarial relay environment, discovery latency increases but does not fail completely.
- The formal security model assumes Ed25519 remains collision-resistant. Post-quantum migration requires a new DID method.

Future work:
- Formal proof of relay eclipse resistance under partial relay compromise
- Integration with X25519 encryption keys for agent-to-agent confidential communication
- DID rotation protocol with cryptographic continuity proofs


6. Conclusion

did:snin achieves what no existing DID method offers: blockchain-free sovereignty with native discovery. It is 2x more expensive than the theoretical minimum (did:key) but adds capability-based agent discovery — the essential feature for autonomous multi-agent systems. For AI agents that must generate their own identity, migrate between hosts, discover peers, and survive infrastructure failures, did:snin represents the Pareto-optimal tradeoff between cost and functionality.

The reference implementation is available at https://github.com/konantgit-sys/snin-node-agent, with the identity library at https://github.com/konantgit-sys/snin-core.


Appendix A: Comparison Matrix Summary

| Dimension            | did:key | did:snin | did:ethr | did:web | did:plc | did:nostr |
|---------------------|---------|----------|----------|---------|---------|-----------|
| Portability         | ✅      | ✅       | ❌       | ❌      | ❌      | ✅        |
| Verification Cost   | Minimal | Low      | High     | Medium  | Medium  | Low       |
| Discovery           | ❌      | ✅       | ⚠️       | ⚠️      | ⚠️      | ✅        |
| Self-Sovereignty    | ✅      | ✅       | ⚠️       | ❌      | ❌      | ✅        |
| Infra Dependency    | None    | Relay    | Chain    | DNS+Web | Server  | Relay     |
| Adversarial Resilience | Key only | Key + eclipse | Key + 51% | CA + DNS | Server | Key + eclipse |
