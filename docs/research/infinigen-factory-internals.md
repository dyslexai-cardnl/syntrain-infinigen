# Infinigen Factory & Solver Internals — Research Findings

**Date**: 2026-03-18
**Purpose**: Phase 0b spike — understand factory registration for syntrAIn

---

## Key Finding

**No solver modification needed.** Adding a custom factory requires:
1. A class inheriting `AssetFactory` with `create_placeholder()` and `create_asset()`
2. Registration in `home_asset_usage()` mapping in `semantics.py`
3. Constraints in `home.py`

The solver automatically discovers factories via semantic tag lookup.

---

## Factory Registration Flow

```
semantics.py: home_asset_usage()
  -> used_as[Semantics.WallDecoration] = {WallArtFactory, MirrorFactory, ...}

home.py: home_furniture_constraints()
  -> usage_lookup.initialize_from_dict(used_as)
  -> Populates global: tag -> set[factory_class] lookup

Solver: propose_addition_bound_gen()
  -> lookup_generator(tags={WallDecoration})
  -> Returns [WallArtFactory, MirrorFactory, ...]
  -> Randomly picks one, calls factory.spawn_placeholder()
```

## AssetFactory Interface

```python
class AssetFactory:
    def __init__(factory_seed, coarse=False)
    def create_placeholder(**kwargs) -> bpy.types.Object   # Lightweight proxy for solver
    def create_asset(placeholder, **params) -> bpy.types.Object  # Final hi-res asset
    def finalize_assets(assets)  # Optional post-processing
```

- Placeholder must have realistic dimensions (solver uses it for collision/spatial reasoning)
- Surface tagging is automatic (`tagging.tag_canonical_surfaces()`)
- Back surface must exist for `flush_wall` constraint to work

## Wall Placement Mechanism

```python
flush_wall = cl.StableAgainst(back, walltags, margin=0.02)
# back = {Subpart.Back, -Subpart.Top, -Subpart.Front}
# walltags = {Subpart.Wall, Subpart.Visible, -Subpart.SupportSurface, -Subpart.Ceiling}
```

Wall decorations are constrained to:
- Back surface flush against wall (margin 0.02m)
- Height > 0.6m from floor
- Vertical centering (soft)
- Distance from doors/windows > 0.1m
- Count per room (0-6 for art, 0-1 for mirrors)

## .blend Loading Pattern

Already exists in `infinigen/assets/static_assets/base.py`:

```python
with bpy.data.libraries.load(file_path, link=False) as (data_from, data_to):
    object_name = data_from.objects[0]

bpy.ops.wm.append(filepath=..., filename=object_name, directory=...)
```

Handles hierarchy collapse for multi-object .blend files.

## What We Need for OutletTestFactory

1. Inherit `AssetFactory`
2. `create_placeholder()`: `new_bbox()` with outlet dimensions (70x114x20mm)
3. `create_asset()`: Load `.blend` via `StaticAssetFactory` pattern
4. Register as `Semantics.WallDecoration` in semantics.py
5. Add outlet-specific constraints in home.py (height 0.3-0.5m, count 2-6 per room)

## Files to Modify in Fork

| File | Change | Impact |
|------|--------|--------|
| NEW `infinigen/assets/objects/mep/outlet.py` | OutletTestFactory class | None — new file |
| `infinigen_examples/constraints/semantics.py` | Add to WallDecoration set | 1 line |
| `infinigen_examples/constraints/home.py` | Add outlet constraints | ~15 lines |

Zero changes to solver core.
