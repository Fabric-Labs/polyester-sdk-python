# Polyester Python SDK

Python SDK for the Polyester public API.

Generated protobuf types and ConnectRPC clients live in `src/polyester/gen/`.
The `polyester` package root contains SDK entry points and helper APIs.

This SDK is maintained by Fabric Labs and updated as the public API evolves.

## Install

Package publishing is not enabled yet. Until the first release, consume this
repository from GitHub or a local checkout.

## Development

```bash
python -m pip install -e .
python -m compileall src/polyester
python -m build
```
