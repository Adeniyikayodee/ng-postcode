# Contributing to ng-postcode

Thank you for helping make Nigeria's digital postcode easy to use from any
language. Contributions of every size are welcome: a new language, a case the
shared spec misses, a difference between the live API and its documentation, a
fix, or a clearer sentence in the docs.

## Getting set up

You only need the toolchain for the package you are changing.

| Package | Needs | Run the tests |
| --- | --- | --- |
| Rust crate | Rust 1.85+ | `cargo test --all-features` |
| Python library | [uv](https://docs.astral.sh/uv/), Python 3.10+ | `cd python && uv run --group dev pytest` |
| MCP server | uv | `cd mcp && uv run --group dev pytest` |
| Address resolver | uv | `cd agent && uv run --group dev pytest` |
| JavaScript library and Node MCP server | Node 22.12+ | `cd js && npm ci && npm test` |
| Java libraries | JDK 17+ | `cd java && ./mvnw verify` |

```sh
git clone https://github.com/Adeniyikayodee/ng-postcode.git && cd ng-postcode
```

Every suite runs offline in seconds. No test calls the NIPOST API, so no key
is needed.

## Where things live

| Path | Role |
| --- | --- |
| `spec/` | The shared cases every implementation must pass. Start here. |
| `src/`, `tests/` | Rust crate |
| `python/` | Python library |
| `js/packages/ng-postcode-js` | JavaScript and TypeScript library |
| `java/core`, `java/api` | Java libraries: the offline core, and the API client |
| `mcp/` | MCP server (Python), the source of `spec/mcp.json` |
| `js/packages/ng-postcode-mcp` | MCP server (Node), built from `spec/mcp.json` |
| `agent/` | Address resolver |
| `scripts/` | Live API check and spec generation |
| `docs/` | The project site and the postcode reference schema |

## The shared spec

Rust, Python, JavaScript, and Java are four implementations of one behaviour.
The files in `spec/` define that behaviour, and each implementation's tests
read them directly.

| File | Defines |
| --- | --- |
| `vectors.json` | Parsing, lenient parsing, building from segments, and prefixes |
| `requests.json` | What each API request sends, or that it is refused |
| `responses.json` | Bodies captured from the live API, which all must decode |
| `tolerance.json` | Bodies the API may one day send, and the outcome each must reach |
| `mcp.json` | The MCP tools, generated from the Python server |
| `mcp-calls.json` | Tool calls that need no network, and what both MCP servers must answer |

A change in behaviour starts in `spec/`:

1. Add or change the case in `spec/`.
2. Run every suite. The implementations that disagree now fail.
3. Fix them in the same pull request, so `main` never holds a case that one
   language fails.

If you find two implementations that disagree and no case covers it, that is a
gap in the spec. A pull request that adds the missing case is welcome even
before the fix is agreed.

`spec/mcp.json` is generated. After changing a tool in `mcp/`, run
`cd mcp && uv run --group dev python ../scripts/mcp_spec.py`, then copy the
result to `js/packages/ng-postcode-mcp/src/contract.generated.json`. Tests in
both servers fail while the three are out of step.

## Adding a language

1. Implement the offline core first: parse, lenient parse, build from
   segments, format, and prefix. It should have no dependencies.
2. Read `spec/vectors.json` from the tests and pass every case. Do not copy
   the cases into the new language.
3. Add the API layer as a separate, optional part: request builders, a decoder
   that takes a status and a body, and a thin HTTP client. Pass
   `requests.json`, `responses.json`, and `tolerance.json`.
4. Add a CI job, a Dependabot entry, and a README for the package.

These have caught real bugs in earlier ports, so check each one deliberately:

- Case conversion and digit tests that depend on locale or accept non-ASCII
  characters.
- Indexes counted in bytes or UTF-16 units where the spec counts characters.
- Numbers written in scientific notation or with a trailing `.0`.
- A decoder that reads a missing boolean as `false`.
- An HTTP client that follows redirects, which would send the key to another
  host, or that has no timeout over the whole exchange.

## Working with the live API

`scripts/live_check.py` compares the live API with what the libraries expect.
It reads the key from `NG_POSTCODE_API_KEY` or `~/.nipost_key`, never prints
it, and makes only free calls unless you pass `--paid`.

- Never commit a key, and never put one in an issue or a pull request.
- Level 2 and above return a person's address. Do not commit captured
  responses that contain one.
- When the live API differs from its documentation, record it in the README
  under "Where the live API differs from its docs", with the date observed,
  and capture the body in `spec/responses.json` if it holds no personal data.

## Branches and pull requests

`main` is always releasable: every release is tagged from it. It is protected,
so a direct push is rejected for everyone, maintainers included. Every change
reaches it through a pull request.

1. Branch from an up-to-date `main`. If you do not have write access, fork the
   repository and branch there.
2. Name the branch `type/short-description`, using the commit types below:
   `fix/java-client-timeout`, `feat/go-core`, `docs/contributing`.
3. Keep the branch to one purpose. Unrelated fixes go in their own branch and
   their own pull request, which keeps each one quick to review and safe to
   revert.
4. Open the pull request against `main`. If `main` moves while yours is open,
   rebase onto it; do not merge `main` into your branch.
5. A maintainer merges by rebase once every check is green, and the branch is
   deleted.

There is no long-lived `dev` branch. Topic branches are short, and work that
is not ready stays in its pull request, as a draft if you want early feedback.

## Before you open a pull request

- The suite for every package you touched passes, with its formatter, linter,
  and type checker: `cargo fmt` and `clippy`, `ruff` and `mypy`, `biome`, or
  `javac -Xlint:all -Werror`. CI runs the same commands and all its jobs are
  required.
- A fix comes with a test that fails without it.
- A claim about how the live API behaves includes the request and the date.
- Commits follow the standards below. Because pull requests are merged by
  rebase, each commit lands on `main` as written.

## Engineering principles

The goal is predictable, testable code that behaves the same in every
language.

1. **Keep the core pure.** Parsing, validation, request building, and decoding
   compute their output only from their inputs. They perform no I/O and hold
   no state.
2. **Push side effects to the edges.** Each library has one small module that
   touches the network (`client`). Everything else can be tested without it.
3. **Treat errors as values.** An expected failure, such as a malformed code,
   a rejected key, or a timeout, is returned and typed so the caller must
   handle it. Exceptions are for programming errors, such as constructing a
   request with a level outside 1 to 5.
4. **Never be more precise than the evidence.** A well-formed code is not an
   assigned one. A missing field is not `false`. The resolver gives an area
   when it cannot justify a building.
5. **Be careful with other people's money and keys.** Nothing corrects a
   mistyped code into a paid call, follows a redirect with a key attached, or
   logs a key or an address.
6. **Prefer data to machinery.** Requests and responses are plain immutable
   values. Small functions transform them and compose.

## Working with AI coding agents

Use them, but verify. Run the tests and read the diff before you push.

## Commit standards

Commit messages are the permanent record of engineering decisions.

1. **Say what the change does for the reader.** The subject states the new
   behaviour in plain words. Add a body only when the reason is not obvious
   from the subject and the diff.
2. **Keep commits atomic.** One logical change per commit, with its test.
3. **No external metadata.** Never include links to AI chat sessions, prompt
   logs, or personal tracking links.
4. **Format.** `type(scope): action`, in the imperative, under 72 characters.
   Types are `feat`, `fix`, `docs`, `test`, `ci`, `build`, `refactor`, and
   `chore`. Scopes are `crate`, `python`, `js`, `java`, `mcp`, `agent`,
   `spec`, `readme`, and `site`. Add `!` for a breaking change. Examples from
   this repository:
   - `fix(crate): refuse redirects so the key stays on one host`
   - `fix(spec): reject a lookup without valid, a reverse without found`
   - `feat(java): add offline postcode core`
   - `build(js)!: require Node 22.12 now that Node 20 is end of life`

## Releases

Maintainers release from tags, one package at a time: a `chore(scope): release
x.y.z` commit, then a tag (`v*`, `py-v*`, `js-v*`, `js-mcp-v*`, `java-v*`,
`mcp-v*`, or `agent-v*`). Each release workflow checks the tag against the
package version, runs the tests, and waits for a maintainer's approval before
it publishes. Contributors do not need to bump versions.

## Reporting a security problem

Please do not open a public issue for a vulnerability, such as a way to leak
an API key. Use **Report a vulnerability** under the repository's
[Security tab](https://github.com/Adeniyikayodee/ng-postcode/security), which
opens a private report that only the maintainers can see.

## License

By contributing, you agree that your work is released under the
[MIT License](LICENSE).
