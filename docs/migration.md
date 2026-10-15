# Migrating from the extended built-in provider

The earlier Hermes fork added keyterms and related controls to the built-in
`elevenlabs` provider. The paired host no longer has them; this plugin does. The
`migrate.py` helper writes a new configuration for you to review. It never edits
your configuration, installs anything or restarts Hermes.

## Before you start

- **No streaming.** Scribe transcribes complete files only. The helper refuses a
  configuration with `stt.streaming: true`. If you need live partial transcripts,
  keep the current provider; turning streaming off is a separate decision.
- **Desktop audio goes through the gateway.** Desktop audio that may have gone
  straight to ElevenLabs now goes Desktop → Hermes gateway → ElevenLabs. The helper
  needs `--accept-gateway-relay`; pass it only if that path is acceptable.
- **Language.** The plugin inherits your Hermes language setting (English by
  default), not automatic detection. See [Language](configuration.md#language).

## Steps

1. **Prepare.** Set up the paired host and the plugin next to your current
   installation, and leave the running one unchanged. Copy the current
   `config.yaml` to a private staging directory. If the old Hermes process had
   `STT_ELEVENLABS_MODEL` set, set it when you run the helper too.

2. **Preview, then write a candidate.** Use the new host's Hermes-managed Python
   and a throwaway home, so the helper cannot touch a live profile:

   ```bash
   NEW_HERMES=/path/to/new/hermes-agent              # paired host checkout
   NEW_PYTHON=/path/to/new/hermes-runtime/bin/python # its managed interpreter
   SCRIBE=/path/to/hermes-elevenlabs-scribe          # plugin checkout
   STAGING=/path/to/private/staging                  # holds the copied config.yaml
   TMP_HOME=$(mktemp -d)

   env HOME="$TMP_HOME" HERMES_HOME="$TMP_HOME/profile" PYTHONPATH="$NEW_HERMES" \
     "$NEW_PYTHON" "$SCRIBE/migrate.py" --config "$STAGING/config.yaml" \
     --accept-gateway-relay --dry-run

   env HOME="$TMP_HOME" HERMES_HOME="$TMP_HOME/profile" PYTHONPATH="$NEW_HERMES" \
     "$NEW_PYTHON" "$SCRIBE/migrate.py" --config "$STAGING/config.yaml" \
     --accept-gateway-relay --output "$STAGING/config.scribe-candidate.yaml"
   ```

3. **Review the candidate** against your original. The helper:
   - sets `stt.provider: elevenlabs-scribe` and adds the plugin to `plugins.enabled`;
   - copies `stt.elevenlabs` to `stt.elevenlabs-scribe`;
   - sets `model` to the model the old provider used: `model_id`, else
     `STT_ELEVENLABS_MODEL`, else `scribe_v2`;
   - sets `language` from `language`, else `language_code`;
   - keeps everything else, including comments, vocabulary and the original
     `stt.elevenlabs` section for rollback.

   It prints no configuration values. The candidate is a new file with `0600`
   permissions; the helper never overwrites an existing file or symlink and leaves
   no partial file if it fails.

4. **Switch over** between sessions. Back up the current configuration and the old
   host and plugin. Install the pinned plugin in the target profile, then deploy the
   paired host and the reviewed configuration together, and start the next session.
   Don't run the new host's built-in `elevenlabs` provider with the old extended
   settings in between.

## When the helper refuses

The helper stops, without writing anything, when:

- `stt.provider` is not explicitly `elevenlabs`;
- streaming is on, or `--accept-gateway-relay` is missing (see
  [Before you start](#before-you-start));
- `stt.elevenlabs-scribe` already exists, or `stt.providers` has an
  `elevenlabs-scribe` entry;
- the plugin is listed in `plugins.disabled`.

Reconcile the other cases by hand in the staging copy, then run it again.

## Rolling back

Restore the previous host and the original configuration together. Switching
`stt.provider` back to `elevenlabs` on the new host alone does not bring back the
extended controls.
