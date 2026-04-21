# Rust serde config evolution

How to ship a Rust app with a gitignored **override config file** (e.g. `config/local.json` copied by the deploy script to the install dir) without re-writing that file every time the schema changes.

## The problem

You have a `Config` struct with a `Default` impl, and you want a per-machine override file that contains only the fields the user cares about (credentials, install-specific paths). Naively, if the deploy script just replaces the installed `config.json` wholesale, you either:

- ship a **full snapshot** (every field, matching defaults) — which goes stale the moment someone adds or renames a field in the Rust struct, and silently loses user creds when parsing fails;
- ship a **partial snapshot** — but without the right serde attributes, any missing required field makes parsing fail and the app falls back to full defaults, also losing creds.

## The pattern

Container-level `#[serde(default)]` on every Config-shaped struct, plus hand-written `Default` impls that return **populated** defaults (not `#[derive(Default)]`, which hands you empty `HashMap`s and `None`s).

```rust
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]                          // <-- the key attribute
pub struct Config {
    pub server_port: u16,
    pub always_on_top: bool,
    pub notifications: Option<NotificationsConfig>,
    // ... more fields, no per-field #[serde(default)] needed
}

impl Default for Config {
    fn default() -> Self {
        Self {
            server_port: 9077,
            always_on_top: true,
            notifications: Some(NotificationsConfig::default()),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct NotificationsConfig {
    pub telegram: Option<TelegramConfig>,
}

impl Default for NotificationsConfig {
    fn default() -> Self {
        // Manual impl — derive(Default) would give telegram: None, which is wrong.
        Self { telegram: Some(TelegramConfig::default()) }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct TelegramConfig {
    pub bot_token: Option<String>,
    pub chat_id: Option<String>,
    pub state_thresholds_ms: HashMap<String, u64>,
}

impl Default for TelegramConfig {
    fn default() -> Self {
        Self {
            bot_token: None,
            chat_id: None,
            state_thresholds_ms: [
                ("awaiting".to_string(), 60_000),
                ("error".to_string(), 60_000),
            ].into_iter().collect(),
        }
    }
}
```

With this in place, the user's override file can be minimal:

```json
{
  "notifications": {
    "telegram": {
      "bot_token": "...",
      "chat_id": "..."
    }
  }
}
```

Missing top-level fields (`server_port`, `always_on_top`) are filled from `Config::default()`. Missing nested fields (`state_thresholds_ms`) are filled from `TelegramConfig::default()`. Unknown fields are silently ignored.

## Why container-level, not per-field

`#[serde(default)]` at the **field** level uses `Default::default()` of the **field's type**, not of the container. So `#[serde(default)] pub context_window_tokens: HashMap<String, u64>` defaults to an *empty* HashMap — not the populated one you wanted.

`#[serde(default)]` at the **container** level uses `Default::default()` of the **container** to fill any missing field. That's what you want — as long as the container's `Default` impl is populated.

## Why not `#[derive(Default)]` on nested configs

`#[derive(Default)]` on a struct containing `HashMap<K, V>` gives you `HashMap::default()` → empty map. If your defaults include populated maps (like `state_thresholds_ms` above), derive is wrong and you need a manual impl.

Same for `Option<T>` fields where the non-`None` default matters — `#[derive(Default)]` always hands you `None`.

## Schema evolution survivable moves

- **Add a new field.** Add it to the struct, add a value to `Default`. Override files don't need to change; missing field backfills from default.
- **Remove a field.** Delete from struct and `Default`. Override files that still mention the old key — serde silently ignores unknown fields (the default; `#[serde(deny_unknown_fields)]` would break this).
- **Rename a field.** This is the one breaking move. Use `#[serde(alias = "old_name")]` on the new-named field during the transition so old override files still parse.
- **Change a field's type.** Breaking; no way around it. Use `#[serde(deserialize_with = "...")]` with a custom deserializer if you need backwards compatibility.

## Guardrails

Write tests that exercise the override-file shape directly, not just `Config::default()`:

```rust
#[test]
fn partial_json_backfills_everything_else() {
    let partial = r#"{
        "notifications": { "telegram": { "bot_token": "t", "chat_id": "c" } }
    }"#;
    let cfg: Config = serde_json::from_str(partial).expect("partial parse");
    assert_eq!(cfg.server_port, 9077, "top-level default survives");

    let tg = cfg.notifications.unwrap().telegram.unwrap();
    assert_eq!(tg.bot_token.as_deref(), Some("t"));
    assert_eq!(tg.state_thresholds_ms.get("awaiting"), Some(&60_000),
               "nested default survives when caller only supplies creds");
}

#[test]
fn empty_object_gives_full_defaults() {
    let cfg: Config = serde_json::from_str("{}").unwrap();
    // ... same assertions as Config::default()
}

#[test]
fn unknown_fields_are_silently_ignored() {
    let with_extra = r#"{ "this_key_does_not_exist": 42 }"#;
    let cfg: Config = serde_json::from_str(with_extra).unwrap();
    assert_eq!(cfg.server_port, 9077);
}
```

These tests catch the three classes of regression: missing-field no longer backfills, unknown-field suddenly errors, or a nested struct's `Default` quietly starts returning emptiness because someone switched to `#[derive(Default)]` on it.

## Related: the load-or-default fallback

A typical loader looks like:

```rust
pub fn load_or_default(path: &Path) -> Self {
    match std::fs::read_to_string(path) {
        Ok(s) => serde_json::from_str(&s).unwrap_or_else(|e| {
            eprintln!("[config] failed to parse {path:?}: {e}; using defaults");
            Config::default()
        }),
        Err(_) => Config::default(),
    }
}
```

With container-level `#[serde(default)]`, the `from_str` arm succeeds for partial and empty JSON. It only fails now for **syntactically invalid** JSON (trailing commas, unquoted keys). In that case the fallback to `Config::default()` is the right move — but any user creds in the malformed file are lost. That's acceptable; syntactically-broken JSON is a different problem from schema evolution.

## When this pattern doesn't fit

- **Config has required fields with no safe default** (e.g. a database URL). Then parsing must fail loudly if missing — either omit `#[serde(default)]` on that specific field, or make the type `Option<DatabaseUrl>` and check at use-site.
- **TOML configs** — the same pattern works; `#[serde(default)]` is format-agnostic. The override-file story depends on how your deploy pipeline layers them.
- **Configs that need migration, not just backfill.** If v2 splits a v1 field into two, a serde default can't do the split — you need a custom deserializer or a pre-load migration step.
