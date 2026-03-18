# Copyright (C) 2026, dyslexAI LLC.
# BSD 3-Clause License — see LICENSE
#
# syntrAIn Phase 1: LightSwitchFactory
# Wall-mounted light switch, placed near doors per NEC.

import os

import bpy
import numpy as np

from infinigen.assets.utils.object import new_bbox
from infinigen.core.placement.factory import AssetFactory
from infinigen.core.util import blender as butil
from infinigen.core.util.math import FixedSeed


SWITCH_BLEND_PATH = os.environ.get(
    "SYNTRAIN_SWITCH_BLEND",
    "/assets/mep/switch/light_switch_rocker.blend",
)

# Standard single-gang switch: 70mm wide x 114mm tall x 15mm deep
SWITCH_WIDTH = 0.070
SWITCH_HEIGHT = 0.114
SWITCH_DEPTH = 0.015


class LightSwitchFactory(AssetFactory):
    """Wall-mounted light switch. Placed at chest height near doors."""

    def __init__(self, factory_seed, coarse=False):
        super().__init__(factory_seed, coarse)
        with FixedSeed(self.factory_seed):
            self.width = SWITCH_WIDTH * np.random.uniform(0.97, 1.03)
            self.height = SWITCH_HEIGHT * np.random.uniform(0.97, 1.03)
            self.depth = SWITCH_DEPTH
            self.blend_path = SWITCH_BLEND_PATH
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

        mat = bpy.data.materials.new(name="switch_plastic")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.92, 0.92, 0.90, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.35
        obj.data.materials.append(mat)
        return obj
