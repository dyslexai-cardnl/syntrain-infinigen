# Copyright (C) 2026, dyslexAI LLC.
# BSD 3-Clause License — see LICENSE
#
# syntrAIn Phase 0c: Minimal OutletFactory proof of concept.
# Loads a .blend model and presents it to Infinigen's constraint solver
# as a wall-mounted object (like WallArtFactory).
#
# This is a hardcoded spike — the TaxonomyAssetFactory (Phase 1+) will
# generalize this pattern to load any component from dyslexai-taxonomy.

import os
from pathlib import Path

import bpy
import numpy as np

from infinigen.assets.utils.object import new_bbox
from infinigen.core.placement.factory import AssetFactory
from infinigen.core.util import blender as butil
from infinigen.core.util.math import FixedSeed
from infinigen.core.util.random import log_uniform


# Path to .blend model — hardcoded for spike, will come from dyslexai-assets later.
# Falls back to procedural generation if .blend not found.
OUTLET_BLEND_PATH = os.environ.get(
    "SYNTRAIN_OUTLET_BLEND",
    "/assets/mep/outlet_duplex/outlet_duplex.blend",
)

# Outlet dimensions per NEC / dyslexai-taxonomy
# Standard duplex outlet: 70mm wide x 114mm tall x 20mm deep (with faceplate)
OUTLET_WIDTH = 0.070   # meters
OUTLET_HEIGHT = 0.114  # meters
OUTLET_DEPTH = 0.020   # meters


class OutletFactory(AssetFactory):
    """Factory that produces wall-mounted electrical outlets.

    Phase 0 spike: loads a .blend model if available, otherwise generates
    a simple procedural placeholder. The constraint solver treats this
    identically to WallArtFactory — back surface flush against wall.

    Dimensions are fixed (real-world outlet dimensions) rather than
    randomly sampled like WallArtFactory, because outlets have standardized
    sizes per NEC.
    """

    def __init__(self, factory_seed, coarse=False):
        super().__init__(factory_seed, coarse)
        with FixedSeed(self.factory_seed):
            # Slight variation in faceplate style (future: multiple .blend variants)
            self.width = OUTLET_WIDTH
            self.height = OUTLET_HEIGHT
            self.depth = OUTLET_DEPTH

            # Small random variation to avoid all outlets looking identical
            # Real outlets vary by ~2mm due to different manufacturers
            self.width *= np.random.uniform(0.97, 1.03)
            self.height *= np.random.uniform(0.97, 1.03)

            self.blend_path = OUTLET_BLEND_PATH
            self.has_blend = os.path.isfile(self.blend_path)

    def create_placeholder(self, **params):
        """Create bounding box placeholder for constraint solver.

        The solver uses this to:
        - Check collisions with other objects
        - Verify wall placement (back surface detection)
        - Validate spatial constraints (height, spacing)

        Dimensions must match the actual asset for accurate placement.
        """
        # new_bbox(x_min, x_max, y_min, y_max, z_min, z_max)
        # Outlet is thin (depth along X), wide along Y, tall along Z
        # Back surface (X=0) faces wall, front (X=depth) faces room
        return new_bbox(
            0, self.depth,                    # X: depth (wall to front)
            -self.width / 2, self.width / 2,  # Y: width (centered)
            -self.height / 2, self.height / 2, # Z: height (centered)
        )

    def create_asset(self, placeholder=None, **params):
        """Create the actual outlet mesh.

        If a .blend file is available, load it. Otherwise, generate a
        simple procedural box as fallback (still useful for testing
        constraint placement without the full asset library).
        """
        if self.has_blend:
            return self._load_blend_asset()
        else:
            return self._create_procedural_fallback()

    def _load_blend_asset(self):
        """Load outlet from .blend file (StaticAssetFactory pattern)."""
        initial_objects = set(bpy.context.scene.objects)

        with bpy.data.libraries.load(self.blend_path, link=False) as (data_from, data_to):
            if not data_from.objects:
                raise ValueError(f"No objects in {self.blend_path}")
            object_name = data_from.objects[0]

        directory = os.path.join(self.blend_path, "Object")
        filepath = os.path.join(directory, object_name)
        bpy.ops.wm.append(
            filepath=filepath,
            filename=object_name,
            directory=directory,
        )

        new_objects = set(bpy.context.scene.objects) - initial_objects
        if not new_objects:
            raise RuntimeError(f"Failed to import from {self.blend_path}")

        # If multiple objects imported, join them
        obj = list(new_objects)[0]
        if len(new_objects) > 1:
            for other in new_objects:
                if other != obj:
                    other.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.join()

        # Scale to match our dimensions
        obj.dimensions = (self.depth, self.width, self.height)
        butil.apply_transform(obj, True)

        return obj

    def _create_procedural_fallback(self):
        """Simple box with outlet-like appearance (no .blend needed)."""
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.active_object
        obj.scale = (self.depth / 2, self.width / 2, self.height / 2)
        butil.apply_transform(obj, True)

        # Add a simple material (white plastic)
        mat = bpy.data.materials.new(name="outlet_plastic")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.9, 0.9, 0.88, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.4
        obj.data.materials.append(mat)

        return obj
