"""Decrypt a GenLayer keystore into a 0600 key file for the write scripts.

`genlayer account unlock` caches the key in an OS keychain, which does not
exist on WSL or a bare Linux container. The deploy and CLI scripts therefore
read a hex private key from a file instead. This writes that file without ever
printing the key.

    python3 scripts/extract_key.py ~/.genlayer/keystores/<name>.json <password> /tmp/omnicourt.key
    DEPLOY_KEY_FILE=/tmp/omnicourt.key node deploy/deployStudioNext.mjs

Treat the output as a secret: it is an unencrypted private key. Delete it when
you are done, and keep it out of the repository.
"""

import json
import os
import sys

from eth_account import Account


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 1

    keystore_path, password, out_path = sys.argv[1:4]

    with open(keystore_path) as handle:
        keystore = json.load(handle)

    private_key = Account.decrypt(keystore, password)

    # Create with 0600 from the start rather than chmod-ing afterwards, so the
    # key is never briefly world-readable.
    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write("0x" + private_key.hex())

    print(f"Wrote key for {Account.from_key(private_key).address} to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
