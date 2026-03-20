#!/usr/bin/env python3
"""Render targeted viewpoints of MEP components from a solved scene.

Reads solve_state.json to find MEP object positions, then creates
camera viewpoints aimed directly at each component at close range.

Runs INSIDE Blender (via --python flag), not standalone.

Usage:
    blender --background scene.blend --python render_mep_targeted.py -- \
        --solve-state solve_state.json \
        --output renders_mep/ \
        --samples 64
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector, Euler


# Viewpoint tiers — matching Phase 28b research
TIERS = {
    "closeup": {"distance": (0.4, 0.8), "weight": 0.4},
    "midrange": {"distance": (1.0, 2.0), "weight": 0.35},
    "overview": {"distance": (2.5, 4.0), "weight": 0.25},
}

VIEWPOINTS_PER_OBJECT = 4
LENS_MM = 35  # Normal lens, not ultrawide
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720


def find_mep_objects():
    """Find MEP spawn_asset objects in the current Blender scene."""
    mep = []
    mep_keywords = ["OutletFactory", "LightSwitchFactory", "VentRegisterFactory"]
    for obj in bpy.data.objects:
        if "spawn_asset" in obj.name and any(k in obj.name for k in mep_keywords):
            mep.append(obj)
    return mep


def get_room_bounds():
    """Get the interior bounds of the room from wall geometry.

    Finds all wall objects and computes the bounding box of wall vertices
    to determine room interior bounds.
    """
    all_xs, all_ys, all_zs = [], [], []
    for obj in bpy.data.objects:
        if "wall" in obj.name.lower() and obj.type == "MESH":
            for v in obj.data.vertices:
                wv = obj.matrix_world @ v.co
                all_xs.append(wv.x)
                all_ys.append(wv.y)
                all_zs.append(wv.z)

    if not all_xs:
        # Fallback: use scene bounds
        return {
            "min": Vector((-5, -5, 0)),
            "max": Vector((5, 5, 3)),
            "center": Vector((0, 0, 1.5)),
        }

    return {
        "min": Vector((min(all_xs), min(all_ys), min(all_zs))),
        "max": Vector((max(all_xs), max(all_ys), max(all_zs))),
        "center": Vector((
            (min(all_xs) + max(all_xs)) / 2,
            (min(all_ys) + max(all_ys)) / 2,
            (min(all_zs) + max(all_zs)) / 2,
        )),
    }


def identify_nearest_wall_edge(obj_pos, room_bounds):
    """Determine which room boundary edge the object is nearest to.

    Returns the axis ('x' or 'y'), the direction (-1 or +1), and the
    wall coordinate. This tells us which wall the object is on.

    Pattern from kubric-stair: don't use wall normals for camera math.
    Just know which wall edge the object is near and step away from it.
    """
    rmin = room_bounds["min"]
    rmax = room_bounds["max"]

    edges = [
        ("x", -1, rmin.x, abs(obj_pos.x - rmin.x)),  # west wall (X min)
        ("x", +1, rmax.x, abs(obj_pos.x - rmax.x)),  # east wall (X max)
        ("y", -1, rmin.y, abs(obj_pos.y - rmin.y)),  # south wall (Y min)
        ("y", +1, rmax.y, abs(obj_pos.y - rmax.y)),  # north wall (Y max)
    ]

    return min(edges, key=lambda e: e[3])


def create_viewpoint(obj, room_bounds, tier_name, tier_config, seed_offset):
    """Create a camera viewpoint aimed at an MEP object.

    Uses kubric-stair's proven approach:
    - Identify which wall the object is on
    - Position camera AWAY from that wall, TOWARD room center
    - look_at the object
    - Clamp camera inside room bounds
    """
    import random
    rng = random.Random(hash(obj.name) + seed_offset)

    dist_min, dist_max = tier_config["distance"]
    distance = rng.uniform(dist_min, dist_max)

    obj_pos = obj.matrix_world.translation.copy()
    axis, direction, wall_coord, wall_dist = identify_nearest_wall_edge(obj_pos, room_bounds)

    # Camera position: step away from the wall INTO the room
    # "Away from wall" means the opposite direction of the wall edge
    cam_pos = obj_pos.copy()

    lateral_offset = rng.uniform(-0.3, 0.3) * distance
    vertical_offset = rng.uniform(-0.2, 0.2)

    if axis == "x":
        # Object on X wall — step in -direction along X (into room)
        cam_pos.x += -direction * distance
        cam_pos.y += lateral_offset  # lateral along Y
    else:
        # Object on Y wall — step in -direction along Y (into room)
        cam_pos.y += -direction * distance
        cam_pos.x += lateral_offset  # lateral along X

    cam_pos.z = obj_pos.z + vertical_offset

    # Clamp camera to room interior (with margin from walls)
    margin = 0.3
    rmin = room_bounds["min"]
    rmax = room_bounds["max"]
    cam_pos.x = max(rmin.x + margin, min(rmax.x - margin, cam_pos.x))
    cam_pos.y = max(rmin.y + margin, min(rmax.y - margin, cam_pos.y))
    cam_pos.z = max(rmin.z + 0.5, min(rmax.z - 0.2, cam_pos.z))

    actual_dist = (cam_pos - obj_pos).length

    return {
        "position": cam_pos,
        "target": obj_pos,
        "tier": tier_name,
        "distance": round(actual_dist, 2),
        "object_name": obj.name,
        "wall": f"{axis}={wall_coord:.1f} (dir={direction})",
    }


def setup_gpu():
    """Configure Cycles GPU rendering."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.refresh_devices()
    prefs.compute_device_type = "CUDA"
    for d in prefs.devices:
        d.use = d.type == "CUDA"
    bpy.context.scene.cycles.device = "GPU"


def render_viewpoint(cam, viewpoint, output_dir, samples, index):
    """Position camera and render one viewpoint."""
    scene = bpy.context.scene

    # Clear parent/constraints
    if cam.parent:
        world_matrix = cam.matrix_world.copy()
        cam.parent = None
        cam.matrix_world = world_matrix
    for c in list(cam.constraints):
        cam.constraints.remove(c)

    # Position camera
    cam.location = viewpoint["position"]

    # Use Blender's track_to constraint for reliable look-at
    # Create an empty at the target location
    target_name = f"_cam_target_{index}"
    if target_name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[target_name], do_unlink=True)
    bpy.ops.object.empty_add(location=viewpoint["target"])
    target_empty = bpy.context.active_object
    target_empty.name = target_name

    constraint = cam.constraints.new(type="TRACK_TO")
    constraint.target = target_empty
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"

    # Bake the constraint to actual rotation
    bpy.context.view_layer.update()
    cam.rotation_euler = cam.matrix_world.to_euler()
    cam.constraints.remove(constraint)
    bpy.data.objects.remove(target_empty, do_unlink=True)

    # Set lens
    cam.data.lens = LENS_MM
    cam.data.sensor_width = 36.0

    # Render settings
    scene.render.resolution_x = IMAGE_WIDTH
    scene.render.resolution_y = IMAGE_HEIGHT
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.cycles.samples = samples

    # Output path
    tier = viewpoint["tier"]
    obj_type = viewpoint["object_name"].split("(")[0].replace("Factory", "").lower()
    filename = f"mep_{index:04d}_{obj_type}_{tier}.png"
    scene.render.filepath = str(output_dir / filename)

    bpy.ops.render.render(write_still=True)
    return filename


def main():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Render MEP-targeted viewpoints")
    parser.add_argument("--output", "-o", type=Path, default=Path("/output/renders_mep"))
    parser.add_argument("--samples", "-s", type=int, default=64)
    parser.add_argument("--viewpoints", type=int, default=VIEWPOINTS_PER_OBJECT)
    args = parser.parse_args(argv)

    print("=" * 60)
    print("MEP Targeted Camera Renderer")
    print("=" * 60)

    # Find MEP objects
    mep_objects = find_mep_objects()
    print(f"Found {len(mep_objects)} MEP objects:")
    for obj in mep_objects:
        print(f"  {obj.name}: {[round(x, 2) for x in obj.matrix_world.translation]}")

    if not mep_objects:
        print("No MEP objects found!")
        return

    # Get room bounds for camera clamping
    room_bounds = get_room_bounds()
    print(f"\nRoom bounds:")
    print(f"  min: ({room_bounds['min'].x:.1f}, {room_bounds['min'].y:.1f}, {room_bounds['min'].z:.1f})")
    print(f"  max: ({room_bounds['max'].x:.1f}, {room_bounds['max'].y:.1f}, {room_bounds['max'].z:.1f})")
    print(f"  center: ({room_bounds['center'].x:.1f}, {room_bounds['center'].y:.1f}, {room_bounds['center'].z:.1f})")

    # Generate viewpoints
    viewpoints = []
    import random
    rng = random.Random(42)

    for obj in mep_objects:
        axis, direction, wall_coord, wall_dist = identify_nearest_wall_edge(
            obj.matrix_world.translation, room_bounds
        )
        print(f"  {obj.name}: on {axis}={wall_coord:.1f} wall (dist={wall_dist*1000:.0f}mm)")

        for v in range(args.viewpoints):
            # Pick tier by weight
            r = rng.random()
            cumulative = 0
            chosen_tier = "midrange"
            for tier_name, tier_config in TIERS.items():
                cumulative += tier_config["weight"]
                if r <= cumulative:
                    chosen_tier = tier_name
                    break

            vp = create_viewpoint(obj, room_bounds, chosen_tier, TIERS[chosen_tier], v)
            viewpoints.append(vp)

    print(f"\nGenerated {len(viewpoints)} viewpoints")

    # Setup
    args.output.mkdir(parents=True, exist_ok=True)
    setup_gpu()

    cam = bpy.context.scene.camera
    if cam is None:
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        bpy.context.scene.camera = cam

    # Add fill light at room center to prevent dark renders
    room_center = room_bounds["center"]
    bpy.ops.object.light_add(type="AREA", location=room_center)
    fill_light = bpy.context.active_object
    fill_light.name = "_mep_fill_light"
    fill_light.data.energy = 200
    fill_light.data.size = 3.0
    fill_light.location.z = room_bounds["max"].z - 0.3  # Near ceiling
    print(f"Added fill light at {[round(x,1) for x in fill_light.location]}")

    # Render
    results = []
    for i, vp in enumerate(viewpoints):
        print(f"\n[{i + 1}/{len(viewpoints)}] {vp['object_name']} ({vp['tier']}, {vp['distance']:.1f}m)")
        filename = render_viewpoint(cam, vp, args.output, args.samples, i)
        results.append({
            "filename": filename,
            "object": vp["object_name"],
            "tier": vp["tier"],
            "distance": round(vp["distance"], 2),
            "camera_location": [round(x, 4) for x in vp["position"]],
            "target_location": [round(x, 4) for x in vp["target"]],
        })
        print(f"  Saved: {filename}")

    # Save metadata
    meta_path = args.output / "viewpoints.json"
    with open(str(meta_path), "w") as f:
        json.dump({"viewpoints": results, "lens_mm": LENS_MM}, f, indent=2)
    print(f"\nMetadata: {meta_path}")
    print(f"Total: {len(results)} renders")


if __name__ == "__main__":
    main()
