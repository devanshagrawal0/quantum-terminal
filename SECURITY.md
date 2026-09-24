# Security

## What this code can and cannot do

- **Read-only by construction.** There is no private key, no signing code, no call to
  Hyperliquid's `/exchange` endpoint and no Lighter `sendTx` anywhere in the repository.
  Account views use a public wallet address; Lighter uses a read-only token.
- **Paper trading only.** Every trade the system "makes" lives in a local SQLite book
  (`data/paper.db`) or a local JSON run file (`data/desk_calls/`). Nothing reaches an exchange.
- **Model-written code runs sandboxed.** In the desk's raw mode, Python written by the model is
  executed in an isolated interpreter (`python -I`) inside a session folder, with the socket
  layer monkey-patched to refuse every connection and a hard time limit.

## Secrets

- `.env` is gitignored. Only `.env.example` (empty values) is committed.
- `data/` (databases, logs, model session transcripts) is gitignored.
- Before every push the tree is scanned for the `.env` values themselves, EVM addresses,
  API-key and token shapes, bearer tokens and private-key headers.

## Reporting

Open a GitHub issue without including any key material, or contact the owner through GitHub.
