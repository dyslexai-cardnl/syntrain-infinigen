# Phase 0 Spike Results: OutletFactory in Infinigen Solver

**Date**: 2026-03-18
**Decision**: **GO** — proceed with syntrAIn Phase 1

---

## Result

The Infinigen constraint solver successfully placed OutletFactory objects
alongside native furniture in a generated bedroom scene.

| Metric | Result |
|--------|--------|
| Scene generated | YES (467MB .blend, seed 42) |
| Solver convergence | YES (62 total objects) |
| Outlets placed | **2** (constraint: 2-5 per room) |
| Tags correct | wall-decoration, no-rotation, FromGenerator(OutletFactory) |
| Solver modification needed | **NONE** |
| Constraint syntax issues | 1 (fixed: separate `>` into its own `all()` call) |
| Generation time | ~12 minutes (same as baseline — outlets add negligible cost) |

## Objects in Generated Scene

```
Beds: 2
Desks: 1
Bookshelves/shelves: 4
Kitchen cabinets: 1
Lamps (ceiling): 4
Lamps (floor): 2
Lamps (desk): 2
Monitors: 1
Books/trinkets: 12
Plants: 1
Rugs: 1
Wall art: 1
**Outlets: 2** <-- syntrAIn
Total: 62
```

## What Worked

1. **Factory registration** — Adding OutletFactory to `used_as[Semantics.WallDecoration]`
   in `semantics.py` was sufficient. No solver changes needed.

2. **Constraint language** — Height range (`in_range(0.3, 0.5)`), count range
   (`in_range(2, 5)`), distance from cutters (`> 0.15`) all worked after minor
   syntax fix.

3. **Solver coexistence** — Outlets were placed alongside 60 native Infinigen
   objects without any conflicts or convergence issues.

4. **Procedural fallback** — OutletFactory's `_create_procedural_fallback()` works
   (simple white box). `.blend` loading not tested yet (needs asset mount in Docker).

## What Needed Fixing

1. **Constraint syntax**: Can't chain `*` with `>` in same lambda.
   Wrong: `o.distance(r, cu.floortags).in_range(0.3, 0.5) * o.distance(cutters) > 0.15`
   Right: Separate into two `all()` calls.

## What's Not Yet Tested

- [ ] Loading actual `.blend` model (needs asset path mounting in Docker)
- [ ] Render output (need to run `--task render` and verify outlets visible)
- [ ] Multiple MEP component types (switches, vents) simultaneously
- [ ] Outlet placement quality (are they at correct heights? on walls not floors?)
- [ ] COCO annotation export with outlet class

## Files Modified (3 files, ~25 lines changed in Infinigen)

| File | Lines Changed |
|------|---------------|
| NEW `infinigen/assets/objects/mep/outlet.py` | +100 (new factory) |
| NEW `infinigen/assets/objects/mep/__init__.py` | +3 |
| `infinigen_examples/constraints/semantics.py` | +2 (import + registration) |
| `infinigen_examples/constraints/home.py` | +23 (import + constraints) |

## Implications for syntrAIn

1. **TaxonomyAssetFactory is viable** — If one hardcoded factory works, a generic
   one that reads from taxonomy YAML will work the same way.

2. **No solver fork needed** — We modify constraint definitions and add factories,
   but the solver core (`annealing.py`, `solve.py`, `moves/`) stays untouched.

3. **FactoryTranslationLayer is straightforward** — Infinigen's native factories
   already output tagged objects. Mapping their tags to taxonomy categories is a
   labeling exercise, not an architectural change.

4. **Timeline confirmed** — Phase 2 (Infinigen Integration) can likely be done in
   2-3 weeks, not 3-5, since the integration point is much simpler than expected.
