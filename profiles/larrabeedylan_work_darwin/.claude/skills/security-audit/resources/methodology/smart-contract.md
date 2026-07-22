# Smart contract methodology

Loaded for `smart-contract` project class — Solidity/EVM, Vyper, Solana/Anchor, CosmWasm, NEAR.

Primary focus below is Solidity/EVM; other ecosystems have analogues.

## Reentrancy

Classic: DAO-style, ERC-777 callback hooks, cross-contract.

```solidity
function withdraw() external {
    uint256 bal = balances[msg.sender];
    (bool ok, ) = msg.sender.call{value: bal}("");   // external call first
    require(ok);
    balances[msg.sender] = 0;                         // state mutation after
}
```

Defenses:
- **Checks-Effects-Interactions** ordering.
- `ReentrancyGuard` (OpenZeppelin) on functions with external calls.
- Pull-pattern withdrawals (user calls separately after accounting).
- Care with ERC-777, ERC-1155, ERC-721 `onERC…Received` callbacks — these are reentrancy surfaces even in "read" flows.

Cross-function reentrancy: attacker re-enters a *different* function that reads the still-unmutated state.

## Integer issues

- Solidity ≥ 0.8 has built-in overflow/underflow checks. Pre-0.8, must use SafeMath.
- `unchecked { ... }` blocks opt out. Review every usage.
- Casts: `uint256 → uint128` truncates silently in `unchecked`.
- Sign: `int` casts can flip sign on overflow.

## Access control

- Every privileged function has `onlyOwner` / `onlyRole(X)` / equivalent modifier.
- Role separation — no single role that can do everything (admin separation).
- Multi-sig on irreversible operations (upgrade, treasury withdrawals).
- Initializer on upgradeable contracts — `initializer` modifier, `_disableInitializers()` in constructor for implementations.

## `tx.origin` auth

```solidity
require(tx.origin == owner);   // WRONG — phishable via intermediary contract
```
Use `msg.sender`.

## Unchecked calls

```solidity
target.call(data);   // return value ignored
```

Always check return:
```solidity
(bool ok, bytes memory ret) = target.call(data);
require(ok);
```

For ERC-20 `transfer` / `transferFrom` / `approve`: use `SafeERC20` wrappers because non-compliant tokens return no value.

## Delegatecall / proxy patterns

- Storage collisions: proxy and implementation must agree on storage layout. Use storage-gaps (`uint256[50] private __gap;`) or ERC-7201 namespaced storage.
- `delegatecall` to attacker-influenced target → attacker code runs in proxy's storage context.
- Initializer missing after upgrade → attacker takes ownership.
- Fallback `delegatecall` proxying without function-selector guards.

## Signature handling

- Signature malleability: ECDSA `s` values in the upper half are non-canonical; use `OpenZeppelin ECDSA.recover` which rejects.
- Replay across chainId: EIP-712 domain separator MUST include `chainId`; otherwise signatures from fork can be replayed.
- Replay across contracts: include contract address in domain separator.
- Nonce handling: ever-increasing nonce, or a bitmap of used nonces.
- Front-running of permit: attacker can submit a victim's `permit` signature before victim intends, DoSing them; use try/catch patterns.

## Oracle manipulation

- Time-weighted average price (TWAP) vs spot: spot prices from DEX pools are cheap to manipulate in a single tx (flash-loan + swap + action + swap-back).
- Chainlink feed staleness: check `updatedAt`; reject if older than threshold.
- Chainlink feed deprecation: `answeredInRound` vs `roundId`.
- Multiple-source oracles (median of N) for critical values.

## Front-running / MEV

Public mempool + deterministic execution = attacker can:
- Sandwich trades (buy before, sell after).
- Snipe liquidations.
- Replace-by-fee for cheaper positioning.

Mitigations:
- Commit-reveal for sensitive operations.
- Batched auctions (CoW Swap pattern).
- Flashbots private mempool / MEV-share for users.
- Minimum output guards on swaps (already standard).

## Gas griefing

- Unbounded loops in admin / accounting — one bad actor fills an array, admin function runs out of gas.
- External calls with tight gas stipend (2300) for `.transfer` — fine for EOAs, breaks for smart wallets with receive hooks. Prefer `.call` with return-value check.
- `require` with string in inner loop — string reverts cost more than errors.

## Upgrade patterns

- Transparent proxy vs UUPS: UUPS puts upgrade logic in implementation — a buggy impl can brick upgrades.
- `_authorizeUpgrade` (UUPS) must be protected.
- Initialization: disabled in implementation constructor (`_disableInitializers()`).
- Storage gaps for future fields.
- Rollback plan: test an upgrade and a subsequent downgrade in the test harness.

## DoS via revert

Unstopping action on a user operation that depends on another user's contract:
```solidity
(bool ok, ) = prevBidder.call{value: prevBid}("");
require(ok);   // prevBidder is a malicious contract that always reverts → auction bricked
```
Fix: pull payments.

## Flash loan attacks

- Oracle manipulation as above.
- Governance flash-loan vote: borrow tokens, vote, return. Mitigation: snapshot-based voting (`ERC20Votes`).

## Token-standard-specific

### ERC-20
- Approve race: attacker sees `approve(X, 100)` tx, front-runs and uses 100, victim's tx lands setting to 200; use `increaseAllowance` / `safeIncreaseAllowance`.
- Fee-on-transfer tokens: `balanceOf` change != amount; accounting must measure post-transfer delta.
- Rebasing tokens: balances mutate between interactions.
- Missing return value on transfer — USDT legacy; wrap with `SafeERC20`.

### ERC-721
- Receiver hook reentrancy on `safeMint` / `safeTransferFrom`.
- `tokenURI` returning manipulable content → XSS in marketplace UIs (not a contract-layer vuln but document).

### ERC-1155
- Same receiver-hook reentrancy.
- Batch functions: ensure array lengths match.

## Tooling

- `slither . --json slither.json` — fast, wide static analysis.
- `mythril analyze contracts/X.sol` — symbolic.
- `halmos` — bounded symbolic with invariants.
- `echidna` or `foundry` invariant fuzzing — write properties, fuzz.
- `forge test --fuzz-runs 10000`.
- Manual audit: read every external function, read every `unchecked` block, read every upgrade path, read every oracle read.

## Cross-chain specifics

- Bridge verification: signature thresholds, replay protection across chains.
- Message ordering guarantees — most cross-chain systems don't order; handle idempotency.
- chainId validation on replay-guards.

## Deploy-time checklist

- Deploy with a multi-sig owner from block one, not a single EOA that transfers ownership later.
- Verify source on explorer.
- Renounce roles you don't need (or make it clear which roles are still active).
- Publish a security contact (security.txt).
- Bug bounty program with clear scope.
