# Copyright (C) 2026, dyslexAI LLC.
# BSD 3-Clause License — see LICENSE
#
# syntrAIn Phase 1: VentRegisterFactory
# Wall/floor-mounted HVAC vent register.

import os

import bpy
import numpy as np

from infinigen.assets.utils.object import new_bbox
from infinigen.core.placement.factory import AssetFactory
from infinigen.core.util import blender as butil
from infinigen.core.util.math import FixedSeed


VENT_BLEND_PATH = os.environ.get(
    "SYNTRAIN_VENT_BLEND",
    "/assets/mep/vent/hvac_vent_register.blend",
)

# Standard floor register: 254mm wide x 152mm tall x 25mm deep
VENT_WIDTH = 0.254
VENT_HEIGHT = 0.152
VENT_DEPTH = 0.025


class VentRegisterFactory(AssetFactory):
    """HVAC vent register. Placed low on walls or at floor level."""

    def __init__(self, factory_seed, coarse=False):
        super().__init__(factory_seed, coarse)
        with FixedSeed(self.factory_seed):
            # Vents come in more size variations than outlets/switches
            self.width = np.random.choice([0.152, 0.254, 0.305]) * np.random.uniform(0.95, 1.05)
            self.height = np.random.choice([0.102, 0.152, 0.254]) * np.random.uniform(0.95, 1.05)
            self.depth = VENT_DEPTH
            self.blend_path = VENT_BLEND_PATH
            self.has_blend = os.path.isfile(self.blend_path)

    def create_placeholder(self, **params):
        return new_bbox(
            0, self.depth,
            -self.width / 2, self.width / 2,
            -self.height / 2, self.height / 2,
        )

    def create_asset(self, placeholder=None, **params):
        if self.has_blend:
            return self._load_blend_asset()
        return self._create_procedural_fallback()

    def _load_blend_asset(self):
        initial_objects = set(bpy.context.scene.objects)
        with bpy.data.libraries.load(self.blend_path, link=False) as (data_from, data_to):
            if not data_from.objects:
                raise ValueError(f"No objects in {self.blend_path}")
            object_name = data_from.objects[0]

        directory = os.path.join(self.blend_path, "Object")
        filepath = os.path.join(directory, object_name)
        bpy.ops.wm.append(filepath=filepath, filename=object_name, directory=directory)

        new_objects = set(bpy.context.scene.objects) - initial_objects
        if not new_objects:
            raise RuntimeError(f"Failed to import from {self.blend_path}")

        obj = list(new_objects)[0]
        if len(new_objects) > 1:
            for other in new_objects:
                other.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.join()

        obj.dimensions = (self.depth, self.width, self.height)
        butil.apply_transform(obj, True)
        return obj

    def _create_procedural_fallback(self):
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.active_object
        obj.scale = (self.depth / 2, self.width / 2, self.height / 2)
        butil.apply_transform(obj, True)

        mat = bpy.data.materials.new(name="vent_metal")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.85, 0.85, 0.83, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.8
        bsdf.inputs["Roughness"].default_value = 0.3
        obj.data.materials.append(mat)
        return obj
