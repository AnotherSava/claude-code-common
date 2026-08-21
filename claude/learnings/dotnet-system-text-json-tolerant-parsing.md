# System.Text.Json — parsing files written by someone else's tool

Notes from making a .NET reader tolerate JSON produced by two different emulators that disagree on types. All behaviours below were verified by running code on .NET 10, not inferred from docs.

## A wrong type anywhere kills the whole document

Deserializing `{"A": {"earned": 0}}` into a type whose `earned` is `bool` throws:

```
System.Text.Json.JsonException: The JSON value could not be converted to System.Boolean.
  Path: $.A.earned | LineNumber: 0 | BytePositionInLine: 25.
  Inner: System.InvalidOperationException: Cannot get the value of a token type 'Number' as a boolean.
```

The **entire** `Dictionary<string, T>` fails, not just the offending entry. If the call site swallows `JsonException` (a common shape for a file watcher), one surprise value anywhere in the file silently costs every record in it. When reading a format you don't control, consider deserializing to `Dictionary<string, JsonElement>` first and converting each value in its own `try`/`catch` — then one bad entry costs one entry. Aggregate the failures into a single log line; a per-entry warning turns a systematically-bad field into a log flood (and `AutoFlush = true` writers make that synchronous disk I/O).

## `JsonNumberHandling` will not help you

`JsonNumberHandling.AllowReadingFromString` governs number↔**string** only. It has no effect on number→bool — verified with all three flags OR'd together, byte-identical exception. A converter is the only option.

(It *does* fix the inverse case: a tool that emits `"hidden": "0"` — a quoted integer — into an `int` field.)

## Prefer a property-scoped converter over an options-scoped one

```csharp
public sealed class FlexibleBooleanConverter : JsonConverter<bool>
{
    public override bool Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
        => reader.TokenType switch
        {
            JsonTokenType.True => true,
            JsonTokenType.False or JsonTokenType.Null => false,
            JsonTokenType.Number => reader.TryGetInt64(out var n) ? n != 0 : reader.GetDouble() != 0,
            JsonTokenType.String => ParseString(reader.GetString()),
            _ => throw new JsonException($"Cannot convert token {reader.TokenType} to a boolean."),
        };

    public override void Write(Utf8JsonWriter writer, bool value, JsonSerializerOptions options)
        => writer.WriteBooleanValue(value);
}
```

Applied as an attribute — `[JsonConverter(typeof(FlexibleBooleanConverter))] public bool Earned { get; set; }` — it affects exactly that property and leaves the shared `JsonSerializerOptions` alone. Registering it in `options.Converters` instead hijacks **every** `bool` and `bool?` the app deserializes with those options, which is almost never what you want.

Keep the property typed `bool`, not `int` — every consumer and existing test stays untouched. Keep `Write` emitting a real boolean so round-tripping still produces the canonical format.

Decide deliberately what `null` means. Throwing is the strict reading; mapping it to `false` is usually better when the cost of an exception is losing the whole file.

### The exception: a *custom type* wants the converter on the type, not the property

The property-scoped advice above holds for converters that retype a **built-in** (`bool`, `long`) —
you only want to bend that one property. It is the wrong default for a converter that defines how
**your own type** is represented, because a property-scoped converter is consulted only when the value
is serialized *as that property*. Serialize the value on its own and the attribute is skipped
entirely and the type falls back to default member serialization:

```csharp
// Custom type with the converter on the PROPERTY of the settings model:
[JsonConverter(typeof(ScaleConverter))] public Scale Scale { get; set; }   // writes "15%"  ✓

// …but a partial-update helper boxes each changed value and serializes it alone:
dict[key] = JsonSerializer.SerializeToElement(value, options);  // value is object → Scale
// → writes {"Unit":0,"Value":15}, and the next read throws
//   "Cannot convert token StartObject to a scale."
```

Put it on the type instead — `[JsonConverter(typeof(ScaleConverter))] public readonly record struct Scale` —
and every path agrees: property, boxed, nested, collection element. This is still not
options-scoped, so nothing else is affected.

Two things make this bite hard and late:

- **Full-object load and save both look fine**, so tests over `Deserialize<Settings>` / `Serialize`
  pass. Only the partial-update path is broken, and that is usually the least-tested one.
- **A read-modify-write helper typically writes the file before re-reading it**, so the unreadable
  value is already on disk when the exception surfaces — the app then fails to *start*, not just to
  save. Validate the serialized form before writing if the config is load-bearing.

Regression test that actually catches it: drive the partial-update path (not the model round-trip) and
assert the file's literal text, e.g. `Assert.Contains("\"420px\"", File.ReadAllText(path))`.

## Encoding: the readers already handle BOMs — do not "fix" them

`File.ReadAllText` / `ReadAllTextAsync` use a `StreamReader` with `detectEncodingFromByteOrderMarks: true`, so BOMs are stripped before the JSON parser ever sees them. Passing raw bytes does not:

| File encoding | `ReadAllTextAsync` → `Deserialize` | `Deserialize(ReadAllBytes)` |
|---|---|---|
| UTF-8, no BOM | OK | OK |
| UTF-8 + BOM | **OK** | throws `'0xEF' is an invalid start of a value` |
| UTF-16LE + BOM (PowerShell 5.1 `Out-File` / `>` default) | **OK** | throws `'0xFF' is an invalid start of a value` |
| UTF-16BE + BOM | **OK** | throws `'0xFE' is an invalid start of a value` |
| UTF-16LE, no BOM | throws `'0x00' is an invalid start of a property name` | same |

The trap: "hardening" a working reader by pinning an explicit encoding (`new StreamReader(path, new UTF8Encoding(false), detectEncodingFromByteOrderMarks: false)`) or switching to a bytes overload **introduces** the BOM bug that wasn't there. Leave `ReadAllText` alone.

ANSI/cp1252 (PowerShell 5.1 `Set-Content` default) does **not** throw — it parses fine and silently mojibakes non-ASCII text (`"Café Zürich"` → `"Caf? Z?rich"`). No exception to catch; only wrong strings.

## Dictionary quirks

- **Duplicate keys: last one wins, silently.** No exception, and the count reflects the deduplicated set. Same for duplicate properties inside a single object.
- **`PropertyNameCaseInsensitive` does not apply to dictionary keys** — only to POCO property names. `{"ACH01": …, "ach01": …}` yields two entries. Worth knowing if the rest of your code matches those same names case-insensitively.
- **Unmapped members are skipped by default** (`JsonUnmappedMemberHandling.Skip`), including nested objects and arrays. Extra fields another tool writes into your record cost nothing. `Disallow` gives `The JSON property 'x' could not be mapped to any .NET member contained in type 'T'`.

## Writing JSON fixtures in C# tests

Raw string literals (`"""…"""`) are the right tool — no escaping of the JSON's own quotes. But the moment you interpolate a value, `$$"""…{{x}}…"""` collides with JSON's braces and fails to compile:

```csharp
// error CS9007: The interpolated raw string literal does not start with enough
// '$' characters to allow this many consecutive closing braces as content.
$$"""{"A": {"earned": {{value}}}}"""
```

The `}}}}` is ambiguous — the compiler can't tell the interpolation's closing `}}` from the JSON's two literal `}`. Adding another `$` works but is unreadable and breaks again at the next nesting level. Concatenate instead:

```csharp
"""{"A": {"earned": """ + value + "}}"
```

Keep the non-interpolated fixtures as raw literals; only the interpolated ones need splitting.

## Sniffing array-vs-object roots

When two producers disagree on whether the root is a list or a map, sniff before deserializing:

```csharp
using var doc = JsonDocument.Parse(json);
if (doc.RootElement.ValueKind == JsonValueKind.Array) { /* List<T> */ }
else { /* Dictionary<string, T> */ }
```

Deserializing an object into `List<T>` throws `The JSON value could not be converted to System.Collections.Generic.List\`1[T]. Path: $`.

Gotcha for the map form: if the values don't repeat their own key as a field, `T.Name` comes back `""` and any later lookup-by-name silently never matches. **Backfill the dictionary key into the object** right after deserializing.
