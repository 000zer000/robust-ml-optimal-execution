# Event-Schema Evolution Policy

## Compatibility rule

The Step 5 event schema uses semantic major/minor versions.

- **Major change:** any change that can alter interpretation, ordering, units,
  required fields, event meaning, or an existing validator outcome. Major changes
  require an explicit migration and cannot be read as the old schema.
- **Minor change:** an optional, backward-compatible field whose absence preserves
  the exact previous meaning.

Renaming a field, changing an enum value, changing signedness or units, converting an
absolute depth update into a delta, or changing hash material is always major.

## Change process

1. State the concrete implementation need.
2. Show why the existing schema cannot represent it.
3. Assess replay, audit, data, model-feature, and paper consequences.
4. Obtain explicit approval before changing a frozen research contract.
5. Add a new schema file rather than silently editing an already released schema.
6. Add migration code and golden fixtures.
7. Run old-reader/new-reader compatibility tests where the change is minor.
8. Record the decision and regenerate manifests.

## Source-adapter rule

Raw venue messages are never made the canonical internal schema by convenience.
Adapters preserve raw bytes separately and map them into the versioned normalized
model. Unmappable or ambiguous messages are quarantined with provenance; they are not
silently coerced.
