# Session: 2026-03-18 — syntrAIn Phase 0 + Phase 1

**Duration**: Full day
**Repos**: spatial-vision-app, kubric-stair, syntrain-infinigen (NEW), dyslexai-assets

---

## Phase 0 Spike: COMPLETE — GO

### Validated
- Forked Infinigen → `dyslexai-cardnl/syntrain-infinigen`
- OutletFactory registered as WallDecoration in `semantics.py`
- Constraint solver placed 2-4 MEP objects per room (outlet, switch, vent)
- **Zero solver modifications needed** — only 3 files changed (~25 lines)
- Docker image builds and runs (`syntrain-infinigen:dev`, 7.4GB)

### Key Finding
Infinigen's factory registration is a dict entry. The solver discovers factories
via semantic tag lookup. No internal changes required.

---

## Phase 1: Partial — Architecture Works, Rendering Blocked

### Completed
- LightSwitchFactory + VentRegisterFactory (same pattern as Outlet)
- TaxonomyAssetFactory — generic `for_category()` pattern
- dyslexai-assets repo: 20 `.blend` models extracted from kubric-stair
- Packed PBR textures into `.blend` files (color, normal, roughness)
- 3-MEP scene generation: 4 components placed alongside 66-76 native objects
- Confirmed MEP objects exist in Blender scene graph with correct collections/visibility

### Blocked: MEP Objects Not Visible in Renders

**Status**: Objects are in the scene, in `unique_assets` collection, `hide_render=False`,
materials assigned, textures packed — but they don't appear in Cycles renders.

**Debug experiments run**:

| Test | Result |
|------|--------|
| Room-scale render (15mm ultrawide) | No visible MEP objects |
| Red emissive material on MEP objects | Still not visible |
| 30cm red debug cube at outlet location | VISIBLE (red cube + white outlet surround at 10x scale) |
| 10x scaled outlet | Visible — white rectangle protruding from wall |
| 1x scaled outlet, packed textures | Not visible |
| Protrusion gradient test (20-200mm) | Not visible — camera likely facing wrong direction |
| Protrusion test v2, furniture hidden | Bare green L-shaped wall, no cubes visible — cubes probably around corner |

**Root cause hypothesis**: Camera direction calculation is wrong for Infinigen's
coordinate system. The test cubes are being placed correctly but the camera
isn't pointing at them. The L-shaped wall geometry suggests the objects are
around a corner from the camera's view.

**What needs investigation next session**:
1. **Infinigen's coordinate system** — Which axis points into the room from each wall?
   The `flush_wall` constraint uses wall surface normals. We need to understand
   how to position a camera looking at a specific wall.
2. **Wall normal extraction** — Instead of guessing camera direction, extract the
   wall surface normal at the outlet location and position camera along that vector.
3. **Blender viewport test** — Open the `.blend` in Blender GUI interactively and
   visually confirm where the MEP objects are. This would immediately resolve the
   camera direction question.

**The 10x scale test proves the pipeline works** — outlets render when large enough
to see. The issue is camera positioning + possibly outlet depth relative to wall
surface geometry at 1x scale.

---

## Architecture Decisions

- **ADR-028 ACCEPTED**: syntrAIn replaces kubric-stair for synthetic data
- **Thin fork strategy**: 3 files changed in Infinigen, periodic upstream merges
- **dyslexai-assets**: Separate package for 3D models (20 models, 11 categories)
- **TaxonomyAssetFactory**: Generic factory using `for_category()` — replaces per-type pattern
- `real_geometry_with_bump.gin`: 83% crash rate, dropped for now

---

## Commits

### syntrain-infinigen (8 commits ahead of upstream)
- `be8a618c`: OutletFactory + solver registration + Dockerfile
- `dc2a73c3`: X11 lib fix for Blender
- `1ac9107c`: Constraint syntax fix
- `8204c79f`: Phase 0 spike results
- `85cc78bb`: LightSwitchFactory + VentRegisterFactory
- `17d12dbf`: TaxonomyAssetFactory
- (uncommitted: packed textures in dyslexai-assets)

### spatial-vision-app
- `377f5c8`: ADR-028, Phase 0 spike plan, session doc

### kubric-stair
- `cbb4750`: Exp8 results, tiered viewpoints, batch render scripts

### dyslexai-assets
- `52dc8fa`: 20 .blend models from kubric-stair

---

## Next Session Priority

### P0: Fix camera/rendering issue
1. Open `.blend` in Blender GUI to visually locate MEP objects relative to walls
2. Extract wall surface normals at outlet positions programmatically
3. Position camera using wall normal vector (not guessing Y direction)
4. Confirm 1x outlets render when camera is correctly aimed at them
5. If still invisible at 1x: investigate wall geometry thickness vs outlet depth

### P1: Once rendering works
1. Multi-viewpoint render (tiered cameras from Phase 28b)
2. COCO annotation export
3. Batch scene generation (50+ scenes)
4. Training run on syntrAIn-generated data

---

## Key Learnings

1. **Infinigen's factory system is more extensible than expected** — adding new
   object types is a data problem (semantics + constraints), not a code problem.

2. **kubric-stair `.blend` models are bounding boxes** — 8 vertices with PBR
   textures. Visual detail comes from normal maps, not mesh geometry. This is
   fine for training but makes debugging render issues harder.

3. **Infinigen's coordinate system is non-trivial** — rooms have complex
   L-shaped geometry, walls have thickness, and determining "which way is into
   the room" requires understanding wall normals, not just axis directions.

4. **The 10x scale test was the key debug step** — proved objects render,
   narrowed the problem to scale/positioning, not pipeline issues.
