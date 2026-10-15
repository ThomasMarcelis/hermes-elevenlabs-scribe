# Development

The plugin checks for the host capabilities it needs and refuses to register, or
to migrate, if any are missing; the Hermes version number alone is not enough.
It is tested on Linux with Python 3.14. Host-isolated plugin execution and other
operating systems have not been tested.

## Offline tests

You need a checkout of the paired host, a Python interpreter with pytest and the
host and plugin dependencies, ffmpeg on `PATH`, and loopback networking. The tests
use synthetic audio and keys and only talk to local test servers.

```bash
HERMES_SOURCE=/path/to/hermes-agent
SCRIBE_SOURCE=/path/to/hermes-elevenlabs-scribe
HERMES_TEST_PYTHON=/path/to/hermes-test-venv/bin/python

TEST_ROOT=$(mktemp -d)
mkdir -p "$TEST_ROOT/home" "$TEST_ROOT/profile"
env HOME="$TEST_ROOT/home" HERMES_HOME="$TEST_ROOT/profile" HERMES_PYTHON="$HERMES_TEST_PYTHON" \
  bash "$HERMES_SOURCE/scripts/run_tests.sh" "$SCRIBE_SOURCE/tests" --file-retries 0 \
  -- --hermes-source "$HERMES_SOURCE"
```

The temporary home keeps the tests away from your real profiles, and
`--hermes-source` makes sure the tests import the host you selected.

To check that Hermes accepts the plugin package:

```bash
hermes plugins validate /path/to/hermes-elevenlabs-scribe
```
