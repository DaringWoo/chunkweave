# Configuration

All configs validate at construction and raise `ConfigError` on bad input.
`engine.chunk()` accepts `FlatConfig`/`HierarchicalConfig` objects or their
equivalent dicts.

## Strategy configs

### sliding_window

| field | required | default | notes |
| --- | --- | --- | --- |
| `chunk_size` | yes | — | int > 0, Unicode code points |
| `overlap` | no | `0` | `0 <= overlap < chunk_size`; `0` = fixed-size chunks |

### recursive

| field | required | default | notes |
| --- | --- | --- | --- |
| `chunk_size` | yes | — | int > 0; maximum chunk length |
| `separators` | no | `["\n\n","\n","。","！","？","；","，",""]` | `str` literals and/or `re.Pattern`, highest priority first; `""` or an exhausted list falls back to code points; `[]` means fallback only |
| `overlap` | no | `0` | `>= 0`; clamped to `prev_len - 1`, never crosses `keep_separator="none"` gaps |
| `keep_separator` | no | `"previous"` | `"previous"`/`"next"`/`"none"` |
| `max_depth` | no | `None` | positive int; deeper fragments get char fallback |

### semantic

| field | required | default | notes |
| --- | --- | --- | --- |
| `threshold` | yes | — | float in `[0,1]`; `score < threshold` marks a boundary |
| `chunk_size` | yes | — | int > 0; maximum chunk length |
| `unit_separators` | no | `["\n\n","\n","。","！","？"]` | same separator forms as `recursive` |

The provider is injected (`engine.set_provider()` / per-call `provider=`)
and is never part of the serialized config.

## Organization configs

```python
{"organization": "flat",
 "strategy": "recursive",
 "config": {"chunk_size": 500},
 "custom": {"doc_id": "x"}}          # optional engine-level custom metadata
```

```python
{"organization": "hierarchical",
 "levels": [                         # non-empty
   {"name": "chapter",               # optional label
    "strategy": "recursive",
    "config": {"chunk_size": 5000},
    "metadata": {"kind": "chapter"}  # optional level metadata, inherited
   },
   {"strategy": "sliding_window",
    "config": {"chunk_size": 300}},
 ],
 "custom": {"doc_id": "x"},
 "provider": my_provider}            # optional per-call provider override
```

`level.metadata` lands on that level's chunks and is inherited by their
descendants; nearer levels override. Reserved-field collisions (common
fields, `parent_id`/`level`/`sequence`, and each strategy's `metadata_keys`)
raise `MetadataConflictError` before any chunking runs.

## Serialization

Every config supports `to_dict()/from_dict()/to_json()/from_json()`. Regex
separators serialize as `{"value": "<pattern>", "regex": true}`; plain
strings are also accepted on load and treated as literals.
`ChunkResult.to_json()`/`from_json()` round-trips results including the
four metadata groups.
