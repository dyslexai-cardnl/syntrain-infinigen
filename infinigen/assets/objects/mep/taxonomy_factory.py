# Copyright (C) 2026, dyslexAI LLC.
# BSD 3-Clause License — see LICENSE
#
# syntrAIn Phase 1: TaxonomyAssetFactory
#
# Generic factory that loads ANY component from dyslexai-taxonomy + dyslexai-assets.
# Replaces the per-type factory pattern (OutletFactory, LightSwitchFactory, etc.)
# with a single factory parameterized by taxonomy category.
#
# Usage:
#   factory = TaxonomyAssetFactory.for_category("outlet", factory_seed=42)
#   placeholder = factory.create_placeholder()
#   asset = factory.create_asset(placeholder)
#
# The factory reads:
#   - Category dimensions from dyslexai-taxonomy (dimensions.yaml)
#   - .blend model path from dyslexai-assets (models/<category>/*.blend)
#   - Placement rules from dyslexai-taxonomy (placement.yaml)

import os
from pathlib import Path
from typing import Optional

import bpy
import numpy as np

from infinigen.assets.utils.object import new_bbox
from infinigen.core.placement.factory import AssetFactory
from infinigen.core.util import blender as butil
from infinigen.core.util.math import FixedSeed


# Default asset root — overridden by SYNTRAIN_ASSETS_ROOT env var
ASSETS_ROOT = Path(os.environ.get(
    "SYNTRAIN_ASSETS_ROOT",
    "/assets",
))


# Component catalog — loaded from taxonomy in production,
# hardcoded here for Phase 1 until taxonomy integration is complete.
# Format: category -> {dimensions (w, h, d in meters), blend_subdir, variants}
COMPONENT_CATALOG = {
    "outlet": {
        "width": 0.070,
        "height": 0.114,
        "depth": 0.020,
        "blend_subdir": "outlet",
        "material_type": "plastic",
        "material_color": (0.9, 0.9, 0.88, 1.0),
    },
    "switch": {
        "width": 0.070,
        "height": 0.114,
        "depth": 0.015,
        "blend_subdir": "switch",
        "material_type": "plastic",
        "material_color": (0.92, 0.92, 0.90, 1.0),
    },
    "vent": {
        "width": 0.254,
        "height": 0.152,
        "depth": 0.025,
        "blend_subdir": "vent",
        "material_type": "metal",
        "material_color": (0.85, 0.85, 0.83, 1.0),
    },
    "thermostat": {
        "width": 0.086,
        "height": 0.086,
        "depth": 0.025,
        "blend_subdir": "thermostat",
        "material_type": "plastic",
        "material_color": (0.95, 0.95, 0.95, 1.0),
    },
    "smoke_detector": {
        "width": 0.130,
        "height": 0.130,
        "depth": 0.040,
        "blend_subdir": "smoke_detector",
        "material_type": "plastic",
        "material_color": (0.95, 0.95, 0.93, 1.0),
    },
    "electrical_panel": {
        "width": 0.356,
        "height": 0.508,
        "depth": 0.100,
        "blend_subdir": "electrical_panel",
        "material_type": "metal",
        "material_color": (0.7, 0.7, 0.7, 1.0),
    },
}


def _find_blend_files(category: str) -> list[Path]:
    """Find all .blend files for a category in the asset library."""
    subdir = COMPONENT_CATALOG.get(category, {}).get("blend_subdir", category)
    asset_dir = ASSETS_ROOT / "models" / subdir
    if asset_dir.exists():
        return sorted(asset_dir.glob("*.blend"))
    return []


class TaxonomyAssetFactory(AssetFactory):
    """Generic factory that produces any MEP component from taxonomy + assets.

    Instead of one factory class per component type, this single factory
    is parameterized by category name. It reads dimensions from the catalog
    (eventually from dyslexai-taxonomy) and loads .blend models from
    dyslexai-assets.

    Use the `for_category()` classmethod to create specialized subclasses
    that the solver can distinguish between.
    """

    # Class-level category (set by for_category)
    _category: Optional[str] = None
    _catalog_entry: Optional[dict] = None

    def __init__(self, factory_seed, coarse=False):
        super().__init__(factory_seed, coarse)

        if self._category is None:
            raise ValueError(
                "TaxonomyAssetFactory must be created via for_category(). "
                "Direct instantiation is not supported."
            )

        cat = self._catalog_entry
        with FixedSeed(self.factory_seed):
            # Dimensions with slight manufacturing variation
            self.width = cat["width"] * np.random.uniform(0.97, 1.03)
            self.height = cat["height"] * np.random.uniform(0.97, 1.03)
            self.depth = cat["depth"]
            self.material_type = cat.get("material_type", "plastic")
            self.material_color = cat.get("material_color", (0.9, 0.9, 0.9, 1.0))

            # Pick a random .blend variant if available
            blend_files = _find_blend_files(self._category)
            if blend_files:
                self.blend_path = str(np.random.choice(blend_files))
                self.has_blend = True
            else:
                self.blend_path = None
                self.has_blend = False

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

        mat = bpy.data.materials.new(name=f"{self._category}_material")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = self.material_color
        if self.material_type == "metal":
            bsdf.inputs["Metallic"].default_value = 0.8
            bsdf.inputs["Roughness"].default_value = 0.3
        else:
            bsdf.inputs["Roughness"].default_value = 0.4
        obj.data.materials.append(mat)
        return obj

    @classmethod
    def for_category(cls, category: str) -> type:
        """Create a specialized factory subclass for a given category.

        Returns a new class (not an instance) that the solver can use
        to distinguish between different MEP component types.

        Example:
            OutletFactory = TaxonomyAssetFactory.for_category("outlet")
            SwitchFactory = TaxonomyAssetFactory.for_category("switch")

            # These are distinct classes the solver can reference independently
            used_as[Semantics.WallDecoration] = {OutletFactory, SwitchFactory}
        """
        if category not in COMPONENT_CATALOG:
            raise ValueError(
                f"Unknown category '{category}'. "
                f"Available: {list(COMPONENT_CATALOG.keys())}"
            )

        # Create a new subclass with the category baked in
        factory_name = f"{category.title().replace('_', '')}Factory"
        factory_cls = type(factory_name, (cls,), {
            "_category": category,
            "_catalog_entry": COMPONENT_CATALOG[category],
        })

        return factory_cls


# Pre-built factories for common MEP types (used in constraints)
# These are equivalent to the hardcoded OutletFactory, LightSwitchFactory, etc.
# but generated from the catalog.
TaxOutletFactory = TaxonomyAssetFactory.for_category("outlet")
TaxSwitchFactory = TaxonomyAssetFactory.for_category("switch")
TaxVentFactory = TaxonomyAssetFactory.for_category("vent")
TaxThermostatFactory = TaxonomyAssetFactory.for_category("thermostat")
TaxSmokeDetectorFactory = TaxonomyAssetFactory.for_category("smoke_detector")
TaxElectricalPanelFactory = TaxonomyAssetFactory.for_category("electrical_panel")
