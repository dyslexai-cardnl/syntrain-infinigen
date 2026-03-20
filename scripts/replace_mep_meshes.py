"""Replace MEP placeholder boxes with realistic meshes in an existing scene.

Runs inside Blender. Finds OutletFactory/SwitchFactory/VentFactory spawn_asset
objects and replaces their 8-vertex box meshes with proper geometry from .blend files.

Usage:
    blender --background scene.blend --python replace_mep_meshes.py -- \
        --outlet /assets/mep/outlet/outlet_realistic.blend \
        --switch /assets/mep/switch/switch_realistic.blend \
        --vent /assets/mep/vent/vent_realistic.blend
"""

import argparse
import os
import sys

import bpy
from mathutils import Vector


def replace_mesh(target_obj, blend_path):
    """Replace target object's mesh data with mesh from .blend file."""
    if not os.path.isfile(blend_path):
        print(f"  SKIP: {blend_path} not found")
        return False

    # Load the new mesh from .blend
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if not data_from.objects:
            print(f"  SKIP: no objects in {blend_path}")
            return False
        data_to.objects = [data_from.objects[0]]

    new_obj = data_to.objects[0]
    if new_obj is None:
        print(f"  SKIP: failed to load from {blend_path}")
        return False

    # Store original transform
    orig_location = target_obj.location.copy()
    orig_rotation = target_obj.rotation_euler.copy()
    orig_scale = target_obj.scale.copy()
    orig_dimensions = target_obj.dimensions.copy()
    orig_collections = list(target_obj.users_collection)

    # Replace mesh data
    old_mesh = target_obj.data
    target_obj.data = new_obj.data.copy()

    # Copy materials from new object
    target_obj.data.materials.clear()
    for mat in new_obj.data.materials:
        target_obj.data.materials.append(mat)

    # Models are pre-rotated to Infinigen convention (+X=front/depth, +Z=top/height).
    # Uniform scale to match the placeholder's height (Z, largest dim).
    if all(d > 0 for d in new_obj.dimensions):
        # Match height (Z axis, the largest dimension for both)
        uniform_scale = orig_dimensions.z / new_obj.dimensions.z if new_obj.dimensions.z > 0 else 1
        target_obj.scale = (uniform_scale, uniform_scale, uniform_scale)
        print(f"  Scale: {uniform_scale:.3f} (matching height {orig_dimensions.z*1000:.0f}mm)")

    # Restore location and rotation (keep solver's placement)
    target_obj.location = orig_location
    target_obj.rotation_euler = orig_rotation

    # Clean up imported object
    bpy.data.objects.remove(new_obj, do_unlink=True)

    # Clean up old mesh if no longer used
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

    return True


def main():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser()
    parser.add_argument("--outlet", default=os.environ.get("SYNTRAIN_OUTLET_BLEND", ""))
    parser.add_argument("--switch", default=os.environ.get("SYNTRAIN_SWITCH_BLEND", ""))
    parser.add_argument("--vent", default=os.environ.get("SYNTRAIN_VENT_BLEND", ""))
    args = parser.parse_args(argv)

    factory_map = {
        "OutletFactory": args.outlet,
        "LightSwitchFactory": args.switch,
        "VentRegisterFactory": args.vent,
    }

    print("=" * 60)
    print("MEP Mesh Replacement")
    print("=" * 60)

    replaced = 0
    for obj in bpy.data.objects:
        if "spawn_asset" not in obj.name:
            continue

        for factory_name, blend_path in factory_map.items():
            if factory_name in obj.name and blend_path:
                old_verts = len(obj.data.vertices)
                print(f"\n{obj.name}:")
                print(f"  Old mesh: {old_verts} verts")
                print(f"  Source: {os.path.basename(blend_path)}")

                if replace_mesh(obj, blend_path):
                    new_verts = len(obj.data.vertices)
                    print(f"  New mesh: {new_verts} verts")
                    print(f"  Materials: {[m.name for m in obj.data.materials]}")
                    replaced += 1
                break

    # Delete ALL bbox_placeholder objects for MEP components
    deleted = 0
    for obj in list(bpy.data.objects):
        if "bbox_placeholder" in obj.name:
            for factory_name in factory_map:
                if factory_name in obj.name:
                    bpy.data.objects.remove(obj, do_unlink=True)
                    deleted += 1
                    break

    # Hide ALL furniture so MEP objects aren't occluded
    # Keep: walls, floors, ceilings, cameras, lights, MEP objects, skirting
    hidden = 0
    mep_keywords = list(factory_map.keys()) + ["TEST_", "DEBUG"]
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        name = obj.name.lower()
        is_structure = any(k in name for k in ["wall", "floor", "ceiling", "skirting", "door", "window"])
        is_mep = any(k in obj.name for k in mep_keywords)
        is_camera = "camera" in name
        if not is_structure and not is_mep and not is_camera:
            obj.hide_render = True
            hidden += 1

    print(f"\nReplaced {replaced} MEP objects, deleted {deleted} placeholders, hidden {hidden} furniture")

    # Save modified scene
    bpy.ops.wm.save_mainfile()
    print("Scene saved.")


if __name__ == "__main__":
    main()
