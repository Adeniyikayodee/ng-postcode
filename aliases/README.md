# Alias packages

Two names on PyPI that people reach for by mistake. Each installs the real package and
holds no code of its own, so the name cannot be taken by someone else.

| Alias | Installs | Why someone types it |
| --- | --- | --- |
| `ng-address` | [`ng-address-resolver`](../agent) | `ng_address` is the name the resolver is imported by |
| `ng-postcode-js` | [`ng-postcode`](../python) | It is the name of the JavaScript library on npm |

They are not part of CI or the release workflows. To publish one, which is rarely needed:

```sh
cd aliases/ng-address && uv build && uv publish
```
