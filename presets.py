import json
import os
import re
from types import SimpleNamespace

import bpy

from . import core


# ------------------------------------------------------------
# Data
# ------------------------------------------------------------

class VI_CC_PM_PresetItem(bpy.types.PropertyGroup):
    control_type: bpy.props.EnumProperty(
        name="Control Type",
        items=[
            ("SHAPE_KEY", "Shape Key", "Shape key value"),
            ("BONE_SCALE", "Bone Scale", "Bone scale slider value"),
            ("BONE_PAIR_DISTANCE", "Bone Pair Distance", "Bone pair slider value"),
        ],
        default="SHAPE_KEY",
    )

    group_name: bpy.props.StringProperty(name="Group")
    display_name: bpy.props.StringProperty(name="Display Name")

    object_name: bpy.props.StringProperty(name="Object")
    armature_name: bpy.props.StringProperty(name="Armature")
    shape_key_name: bpy.props.StringProperty(name="Shape Key")
    bone_name: bpy.props.StringProperty(name="Bone")
    bone_a_name: bpy.props.StringProperty(name="Bone A")
    bone_b_name: bpy.props.StringProperty(name="Bone B")

    value: bpy.props.FloatProperty(name="Value", default=0.0)


class VI_CC_PM_CharacterPreset(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Preset Name", default="Character Preset")
    items: bpy.props.CollectionProperty(type=VI_CC_PM_PresetItem)


class VI_CC_PM_Settings(bpy.types.PropertyGroup):
    presets: bpy.props.CollectionProperty(type=VI_CC_PM_CharacterPreset)
    active_preset_index: bpy.props.IntProperty(default=0)

    new_preset_name: bpy.props.StringProperty(name="Preset Name", default="Character Preset")
    instance_name: bpy.props.StringProperty(name="Instance Name", default="Character_Instance")

    copy_object_data: bpy.props.BoolProperty(
        name="Make Single-User Object Data",
        description="Give duplicated meshes/armatures their own data blocks instead of sharing with the source creator",
        default=True,
    )

    clear_animation_data: bpy.props.BoolProperty(
        name="Clear Animation Data on Instance",
        description="Remove copied animation data from duplicated instance objects",
        default=False,
    )

    library_root_folder: bpy.props.StringProperty(
        name="Character Library Folder",
        description="Root folder containing Assets and Presets folders",
        subtype="DIR_PATH",
        default="",
    )

    asset_set_name: bpy.props.StringProperty(
        name="Template Name",
        description="Reusable character template name written to Templates/*.blend and referenced by preset JSON files",
        default="DefaultCharacterTemplate",
    )

    template_collection: bpy.props.PointerProperty(
        name="Template Collection",
        description="Collection to export as the complete character template. Put the armature, meshes, rig helpers, widgets, and required rig dependencies in this collection.",
        type=bpy.types.Collection,
    )

    import_preset_file: bpy.props.StringProperty(
        name="Import Preset JSON",
        description="Preset JSON file from the library Presets folder",
        subtype="FILE_PATH",
        default="",
    )


# ------------------------------------------------------------
# Basic Helpers
# ------------------------------------------------------------

def get_pm_settings(context):
    return context.scene.vi_cc_preset_manager


def get_creator_settings(context):
    return getattr(context.scene, "vi_character_creator", None)


def get_active_preset(pm_settings):
    if not pm_settings.presets:
        return None

    index = pm_settings.active_preset_index

    if index < 0 or index >= len(pm_settings.presets):
        return None

    return pm_settings.presets[index]


def make_unique_name(base_name, existing_names):
    name = base_name.strip() or "Character_Instance"

    if name not in existing_names:
        return name

    number = 1

    while True:
        candidate = f"{name}.{number:03d}"

        if candidate not in existing_names:
            return candidate

        number += 1


def sanitize_folder_name(name):
    safe = "".join(char if char.isalnum() or char in {" ", "_", "-", "."} else "_" for char in name.strip())
    safe = safe.strip(" .")
    return safe or "Character_Preset"


def ensure_library_folders(root_folder):
    root_folder = bpy.path.abspath(root_folder)
    templates_folder = os.path.join(root_folder, "Templates")
    presets_folder = os.path.join(root_folder, "Presets")
    assets_folder = os.path.join(root_folder, "Assets")  # Legacy folder from older builds.
    os.makedirs(templates_folder, exist_ok=True)
    os.makedirs(presets_folder, exist_ok=True)
    os.makedirs(assets_folder, exist_ok=True)
    return root_folder, templates_folder, presets_folder


def listify(value):
    return [float(v) for v in value]


def iter_collection_objects_recursive(collection):
    if not collection:
        return

    seen = set()

    def walk(col):
        for obj in col.objects:
            if obj.name not in seen:
                seen.add(obj.name)
                yield obj

        for child in col.children:
            yield from walk(child)

    yield from walk(collection)


def find_collection_containing_all(objects):
    objects = [obj for obj in objects if obj]

    if not objects:
        return None

    best_collection = None
    best_score = -1

    for collection in bpy.data.collections:
        collection_objects = set(iter_collection_objects_recursive(collection))
        score = sum(1 for obj in objects if obj in collection_objects)

        if score > best_score:
            best_collection = collection
            best_score = score

    return best_collection if best_score > 0 else None


def get_template_collection_for_export(context, creator_settings, pm_settings):
    if pm_settings.template_collection:
        return pm_settings.template_collection

    source_objects = list(iter_instance_source_objects(creator_settings))
    return find_collection_containing_all(source_objects)


def mark_asset_source_names(objects):
    previous = []

    for obj in objects:
        had_key = "vi_cc_asset_source_name" in obj
        old_value = obj.get("vi_cc_asset_source_name", "")
        previous.append((obj, had_key, old_value))
        obj["vi_cc_asset_source_name"] = obj.name

    return previous


def restore_asset_source_names(previous):
    for obj, had_key, old_value in previous:
        if not obj or obj.name not in bpy.data.objects:
            continue

        if had_key:
            obj["vi_cc_asset_source_name"] = old_value
        elif "vi_cc_asset_source_name" in obj:
            del obj["vi_cc_asset_source_name"]


# ------------------------------------------------------------
# Creator Matching / Values
# ------------------------------------------------------------

def find_matching_creator_item(creator_settings, preset_item):
    if not creator_settings:
        return None

    for group in creator_settings.groups:
        for item in group.items:
            if item.control_type != preset_item.control_type:
                continue

            if item.control_type == "SHAPE_KEY":
                obj_name = item.object.name if item.object else ""

                if obj_name == preset_item.object_name and item.shape_key_name == preset_item.shape_key_name:
                    return item

            elif item.control_type == "BONE_SCALE":
                armature_name = item.armature_object.name if item.armature_object else ""

                if armature_name == preset_item.armature_name and item.bone_name == preset_item.bone_name:
                    return item

            elif item.control_type == "BONE_PAIR_DISTANCE":
                armature_name = item.armature_object.name if item.armature_object else ""
                same_order = item.bone_a_name == preset_item.bone_a_name and item.bone_b_name == preset_item.bone_b_name
                flipped_order = item.bone_a_name == preset_item.bone_b_name and item.bone_b_name == preset_item.bone_a_name

                if armature_name == preset_item.armature_name and (same_order or flipped_order):
                    return item

    return None


def read_current_control_value(item):
    if item.control_type == "SHAPE_KEY":
        key = core.get_shape_key(item.object, item.shape_key_name)
        return key.value if key else None

    if item.control_type in {"BONE_SCALE", "BONE_PAIR_DISTANCE"}:
        return item.slider_value

    return None


def write_current_control_value(item, value):
    if item.control_type == "SHAPE_KEY":
        key = core.get_shape_key(item.object, item.shape_key_name)

        if not key:
            return False

        key.value = value
        return True

    if item.control_type in {"BONE_SCALE", "BONE_PAIR_DISTANCE"}:
        item.slider_value = value
        core.apply_group_item_control(item)
        return True

    return False


def capture_creator_state(creator_settings):
    state = []

    if not creator_settings:
        return state

    for group in creator_settings.groups:
        for item in group.items:
            value = read_current_control_value(item)

            if value is None:
                continue

            state.append((item, value))

    return state


def restore_creator_state(state):
    for item, value in state:
        write_current_control_value(item, value)


def apply_preset_to_creator(context, preset):
    creator_settings = get_creator_settings(context)

    if not creator_settings or not preset:
        return 0, 0

    applied = 0
    missing = 0

    for preset_item in preset.items:
        item = find_matching_creator_item(creator_settings, preset_item)

        if not item:
            missing += 1
            continue

        if write_current_control_value(item, preset_item.value):
            applied += 1
        else:
            missing += 1

    return applied, missing


# ------------------------------------------------------------
# Preset Serialization
# ------------------------------------------------------------

def save_item_to_preset(preset, group, item):
    value = read_current_control_value(item)

    if value is None:
        return False

    preset_item = preset.items.add()
    preset_item.control_type = item.control_type
    preset_item.group_name = group.name
    preset_item.display_name = core.item_display_label(item)
    preset_item.value = value

    if item.control_type == "SHAPE_KEY":
        preset_item.object_name = item.object.name if item.object else ""
        preset_item.shape_key_name = item.shape_key_name

    elif item.control_type == "BONE_SCALE":
        preset_item.armature_name = item.armature_object.name if item.armature_object else ""
        preset_item.bone_name = item.bone_name

    elif item.control_type == "BONE_PAIR_DISTANCE":
        preset_item.armature_name = item.armature_object.name if item.armature_object else ""
        preset_item.bone_a_name = item.bone_a_name
        preset_item.bone_b_name = item.bone_b_name

    return True


def preset_item_to_dict_from_saved_item(item):
    return {
        "control_type": item.control_type,
        "group_name": item.group_name,
        "display_name": item.display_name,
        "object_name": item.object_name,
        "armature_name": item.armature_name,
        "shape_key_name": item.shape_key_name,
        "bone_name": item.bone_name,
        "bone_a_name": item.bone_a_name,
        "bone_b_name": item.bone_b_name,
        "value": float(item.value),
    }


def creator_item_to_full_preset_dict(group, item):
    data = {
        "control_type": item.control_type,
        "group_name": group.name,
        "display_name": core.item_display_label(item),
        "value": float(read_current_control_value(item) or 0.0),
        "object_name": "",
        "armature_name": "",
        "shape_key_name": "",
        "bone_name": "",
        "bone_a_name": "",
        "bone_b_name": "",
    }

    if item.control_type == "SHAPE_KEY":
        data["object_name"] = item.object.name if item.object else ""
        data["shape_key_name"] = item.shape_key_name

    elif item.control_type == "BONE_SCALE":
        data["armature_name"] = item.armature_object.name if item.armature_object else ""
        data["bone_name"] = item.bone_name
        data["scale_mode"] = item.scale_mode
        data["min_scale"] = float(item.min_scale)
        data["max_scale"] = float(item.max_scale)
        data["base_location"] = listify(item.base_location)
        data["base_rotation"] = listify(item.base_rotation)
        data["base_scale"] = listify(item.base_scale)

    elif item.control_type == "BONE_PAIR_DISTANCE":
        data["armature_name"] = item.armature_object.name if item.armature_object else ""
        data["bone_a_name"] = item.bone_a_name
        data["bone_b_name"] = item.bone_b_name
        data["min_distance_factor"] = float(item.min_distance_factor)
        data["max_distance_factor"] = float(item.max_distance_factor)
        data["pair_apply_mode"] = item.pair_apply_mode
        data["base_location_a"] = listify(item.base_location_a)
        data["base_location_b"] = listify(item.base_location_b)
        data["base_rotation_a"] = listify(item.base_rotation_a)
        data["base_rotation_b"] = listify(item.base_rotation_b)
        data["base_scale_a"] = listify(item.base_scale_a)
        data["base_scale_b"] = listify(item.base_scale_b)
        data["base_matrix_a"] = listify(item.base_matrix_a)
        data["base_matrix_b"] = listify(item.base_matrix_b)
        data["base_rest_head_a"] = listify(item.base_rest_head_a)
        data["base_rest_head_b"] = listify(item.base_rest_head_b)

    return data



def preset_item_to_full_json_dict(item):
    return {
        "control_type": item.control_type,
        "group_name": item.group_name,
        "display_name": item.display_name,
        "object_name": item.object_name,
        "armature_name": item.armature_name,
        "shape_key_name": item.shape_key_name,
        "bone_name": item.bone_name,
        "bone_a_name": item.bone_a_name,
        "bone_b_name": item.bone_b_name,
        "value": item.value,
    }


def full_preset_snapshot_from_creator(context, preset, template_name, template_collection_name):
    creator_settings = get_creator_settings(context)

    return {
        "format": "ViCharacterLibrary.shared_character_preset",
        "version": 3,
        "preset_name": preset.name,
        "asset_set": template_name,  # Legacy key retained for older import code.
        "template": template_name,
        "template_blend": f"{template_name}.blend",
        "template_collection": template_collection_name,
        "items": [
            creator_item_to_full_preset_dict(group, item)
            for group in creator_settings.groups
            for item in group.items
        ],
    }


# ------------------------------------------------------------
# Object Duplication / Library Writing
# ------------------------------------------------------------

def iter_instance_source_objects(creator_settings):
    seen = set()

    for managed in creator_settings.managed_armatures:
        obj = managed.object

        if obj and obj.name not in seen:
            seen.add(obj.name)
            yield obj

    for managed in creator_settings.managed_objects:
        obj = managed.object

        if obj and obj.name not in seen:
            seen.add(obj.name)
            yield obj


def duplicate_creator_objects(context, collection_name, copy_object_data=True, clear_animation_data=False):
    creator_settings = get_creator_settings(context)

    if not creator_settings:
        return None, []

    collection_name = make_unique_name(collection_name, bpy.data.collections.keys())
    collection = bpy.data.collections.new(collection_name)
    context.scene.collection.children.link(collection)

    source_objects = list(iter_instance_source_objects(creator_settings))
    object_map = {}
    duplicates = []

    source_objects.sort(key=lambda obj: 0 if obj.type == "ARMATURE" else 1)

    for source in source_objects:
        duplicate = source.copy()
        duplicate.name = make_unique_name(f"{collection_name}_{source.name}", bpy.data.objects.keys())
        duplicate["vi_cc_asset_source_name"] = source.name

        if copy_object_data and source.data:
            duplicate.data = source.data.copy()

        if clear_animation_data:
            duplicate.animation_data_clear()

        duplicate.matrix_world = source.matrix_world.copy()
        collection.objects.link(duplicate)
        object_map[source] = duplicate
        duplicates.append(duplicate)

    for source, duplicate in object_map.items():
        if source.parent in object_map:
            duplicate.parent = object_map[source.parent]
            duplicate.matrix_parent_inverse = source.matrix_parent_inverse.copy()

        for modifier in duplicate.modifiers:
            if modifier.type == "ARMATURE" and getattr(modifier, "object", None) in object_map:
                modifier.object = object_map[modifier.object]

    return collection, duplicates


def remove_collection_and_objects(collection, objects):
    if collection and collection.name in bpy.data.collections:
        for parent_collection in bpy.data.collections:
            if collection.name in parent_collection.children:
                parent_collection.children.unlink(collection)

        if collection.name in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.unlink(collection)

    for obj in objects:
        if obj and obj.name in bpy.data.objects:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)

            if data and data.users == 0:
                if data.__class__.__name__ == "Mesh":
                    bpy.data.meshes.remove(data)
                elif data.__class__.__name__ == "Armature":
                    bpy.data.armatures.remove(data)

    if collection and collection.name in bpy.data.collections:
        bpy.data.collections.remove(collection)


def export_collection_to_blend(collection, blend_path):
    bpy.data.libraries.write(blend_path, {collection}, fake_user=True, compress=True)


def write_asset_manifest(assets_folder, asset_set_name, collection_name, objects):
    manifest = {
        "format": "ViCharacterLibrary.shared_asset_manifest",
        "version": 1,
        "asset_set": asset_set_name,
        "blend_file": f"{asset_set_name}.blend",
        "collection_name": collection_name,
        "objects": [
            {
                "source_name": obj.get("vi_cc_asset_source_name", obj.name),
                "exported_name": obj.name,
                "type": obj.type,
            }
            for obj in objects
        ],
    }

    path = os.path.join(assets_folder, f"{asset_set_name}_manifest.json")

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=4)

    return path


def read_asset_manifest(root_folder, asset_set_name):
    path = os.path.join(root_folder, "Assets", f"{asset_set_name}_manifest.json")

    if not os.path.exists(path):
        return None, f"Missing asset manifest: {path}"

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return None, f"Could not read asset manifest: {exc}"

    if data.get("format") not in {"ViCharacterCreator.shared_asset_manifest", "ViCharacterLibrary.shared_asset_manifest"}:
        return None, "Selected asset manifest is not a Vi Character Creator shared asset manifest."

    return data, ""


def read_asset_manifest(root_folder, asset_set_name):
    path = os.path.join(root_folder, "Assets", f"{asset_set_name}_manifest.json")

    if not os.path.exists(path):
        return None, f"Missing asset manifest: {path}"

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return None, f"Could not read asset manifest: {exc}"

    if data.get("format") not in {"ViCharacterCreator.shared_asset_manifest", "ViCharacterLibrary.shared_asset_manifest"}:
        return None, "Selected asset manifest is not a Vi Character Library shared asset manifest."

    return data, ""


def append_template_collection(context, root_folder, preset_data, instance_name):
    template_name = preset_data.get("template") or preset_data.get("asset_set", "")
    template_blend = preset_data.get("template_blend") or f"{template_name}.blend"
    template_collection = preset_data.get("template_collection") or template_name

    candidate_paths = [
        os.path.join(root_folder, "Templates", template_blend),
        os.path.join(root_folder, "Assets", template_blend),  # Legacy fallback.
    ]

    blend_path = next((path for path in candidate_paths if os.path.exists(path)), "")

    # Legacy manifest fallback from older shared-asset exports.
    if not blend_path and template_name:
        manifest, error = read_asset_manifest(root_folder, template_name)

        if not error and manifest:
            blend_path = os.path.join(root_folder, "Assets", manifest.get("blend_file", f"{template_name}.blend"))
            template_collection = manifest.get("collection_name", template_collection)

    if not blend_path or not os.path.exists(blend_path):
        return None, {}, f"Missing template blend file. Checked: {candidate_paths}"

    directory = blend_path + os.sep + "Collection" + os.sep
    before_collections = set(bpy.data.collections.keys())

    try:
        bpy.ops.wm.append(directory=directory, filename=template_collection)
    except Exception as exc:
        return None, {}, f"Could not append template collection '{template_collection}': {exc}"

    after_collections = set(bpy.data.collections.keys())
    new_collection_names = list(after_collections - before_collections)
    collection = bpy.data.collections[new_collection_names[0]] if new_collection_names else bpy.data.collections.get(template_collection)

    if not collection:
        return None, {}, "Could not append the character template collection."

    if collection.name not in context.scene.collection.children:
        context.scene.collection.children.link(collection)

    collection.name = make_unique_name(instance_name or collection.name, bpy.data.collections.keys())

    object_map = {}

    for obj in iter_collection_objects_recursive(collection):
        source_name = obj.get("vi_cc_asset_source_name", "") or obj.name

        if source_name:
            object_map[source_name] = obj

    return collection, object_map, ""


# ------------------------------------------------------------
# Applying Preset JSON to Imported Assets
# ------------------------------------------------------------

def make_temp_item_for_import(data, object_map):
    temp = SimpleNamespace()
    temp.control_type = data.get("control_type", "")
    temp.slider_value = float(data.get("value", 0.0))

    if temp.control_type == "BONE_SCALE":
        temp.armature_object = object_map.get(data.get("armature_name", ""))
        temp.bone_name = data.get("bone_name", "")
        temp.scale_mode = data.get("scale_mode", "UNIFORM")
        temp.min_scale = float(data.get("min_scale", 0.5))
        temp.max_scale = float(data.get("max_scale", 1.5))
        temp.base_location = data.get("base_location", [0.0, 0.0, 0.0])
        temp.base_rotation = data.get("base_rotation", [0.0, 0.0, 0.0])
        temp.base_scale = data.get("base_scale", [1.0, 1.0, 1.0])

    elif temp.control_type == "BONE_PAIR_DISTANCE":
        temp.armature_object = object_map.get(data.get("armature_name", ""))
        temp.bone_a_name = data.get("bone_a_name", "")
        temp.bone_b_name = data.get("bone_b_name", "")
        temp.min_distance_factor = float(data.get("min_distance_factor", -1.0))
        temp.max_distance_factor = float(data.get("max_distance_factor", 1.0))
        temp.pair_apply_mode = data.get("pair_apply_mode", "POSE_X_SCALE")
        temp.base_location_a = data.get("base_location_a", [0.0, 0.0, 0.0])
        temp.base_location_b = data.get("base_location_b", [0.0, 0.0, 0.0])
        temp.base_rotation_a = data.get("base_rotation_a", [0.0, 0.0, 0.0])
        temp.base_rotation_b = data.get("base_rotation_b", [0.0, 0.0, 0.0])
        temp.base_scale_a = data.get("base_scale_a", [1.0, 1.0, 1.0])
        temp.base_scale_b = data.get("base_scale_b", [1.0, 1.0, 1.0])
        temp.base_matrix_a = data.get("base_matrix_a", [1.0, 0.0, 0.0, 0.0,
                                                          0.0, 1.0, 0.0, 0.0,
                                                          0.0, 0.0, 1.0, 0.0,
                                                          0.0, 0.0, 0.0, 1.0])
        temp.base_matrix_b = data.get("base_matrix_b", [1.0, 0.0, 0.0, 0.0,
                                                          0.0, 1.0, 0.0, 0.0,
                                                          0.0, 0.0, 1.0, 0.0,
                                                          0.0, 0.0, 0.0, 1.0])
        temp.base_rest_head_a = data.get("base_rest_head_a", [0.0, 0.0, 0.0])
        temp.base_rest_head_b = data.get("base_rest_head_b", [0.0, 0.0, 0.0])

    return temp


def lookup_imported_object(object_map, name):
    if not name:
        return None

    if name in object_map:
        return object_map[name]

    # Blender may append objects as Name.001. Prefer a source-name custom
    # property, but fall back to stripped Blender duplicate suffix matching.
    stripped = re.sub(r"\.\d{3}$", "", name)

    for key, obj in object_map.items():
        if key == stripped or re.sub(r"\.\d{3}$", "", key) == stripped:
            return obj

        if obj and re.sub(r"\.\d{3}$", "", obj.name) == stripped:
            return obj

    return None


def apply_preset_data_to_object_map(context, preset_data, object_map):
    applied = 0
    missing = 0

    for item in preset_data.get("items", []):
        control_type = item.get("control_type", "")

        if control_type == "SHAPE_KEY":
            obj = lookup_imported_object(object_map, item.get("object_name", ""))
            key_name = item.get("shape_key_name", "")

            if not obj:
                missing += 1
                continue

            key = core.get_shape_key(obj, key_name)

            if not key:
                missing += 1
                continue

            key.value = float(item.get("value", 0.0))
            applied += 1

        elif control_type == "BONE_SCALE":
            temp = make_temp_item_for_import(item, object_map)
            temp.armature_object = lookup_imported_object(object_map, item.get("armature_name", ""))

            if temp.armature_object and core.apply_bone_scale_control(temp):
                applied += 1
            else:
                missing += 1

        elif control_type == "BONE_PAIR_DISTANCE":
            temp = make_temp_item_for_import(item, object_map)
            temp.armature_object = lookup_imported_object(object_map, item.get("armature_name", ""))

            if temp.armature_object and core.apply_bone_pair_distance_control(temp):
                applied += 1
            else:
                missing += 1

    if context:
        context.view_layer.update()

    return applied, missing


def load_shared_preset_json(path):
    if not os.path.exists(path):
        return None, f"Missing preset JSON: {path}"

    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception as exc:
        return None, f"Could not read preset JSON: {exc}"

    file_format = data.get("format", "")

    valid_formats = {
        "ViCharacterCreator.shared_character_preset",
        "ViCharacterLibrary.shared_character_preset",
    }

    if file_format in valid_formats:
        return data, ""

    if file_format in {
        "ViCharacterCreator.shared_asset_manifest",
        "ViCharacterLibrary.shared_asset_manifest",
    }:
        return None, "That JSON is an asset manifest, not a character preset. Choose a file from the Presets folder."

    return None, f"Selected JSON is not a Vi Character Library shared character preset. Found format: {file_format or 'missing'}"


def collection_contains_object_recursive(collection, obj):
    if not collection or not obj:
        return False

    for candidate in iter_collection_objects_recursive(collection):
        if candidate == obj:
            return True

    return False


def ensure_creator_managed_links_for_collection(creator_settings, collection):
    for obj in iter_collection_objects_recursive(collection):
        if obj.type == "MESH":
            if not any(entry.object == obj for entry in creator_settings.managed_objects):
                entry = creator_settings.managed_objects.add()
                entry.object = obj

        elif obj.type == "ARMATURE":
            if not any(entry.object == obj for entry in creator_settings.managed_armatures):
                entry = creator_settings.managed_armatures.add()
                entry.object = obj


def find_or_create_imported_group(creator_settings, collection, source_group_name):
    group_name = f"{collection.name} / {source_group_name or 'Controls'}"

    for group in creator_settings.groups:
        if group.name == group_name:
            return group

    group = creator_settings.groups.add()
    group.name = group_name
    creator_settings.active_group_index = len(creator_settings.groups) - 1
    return group


def assign_vector_property(item, prop_name, values):
    try:
        setattr(item, prop_name, values)
    except Exception:
        # FloatVectorProperty assignment is picky in some Blender contexts.
        current = getattr(item, prop_name)
        for i, value in enumerate(values):
            if i < len(current):
                current[i] = float(value)


def rebuild_creator_controls_from_preset_data(context, preset_data, collection, object_map):
    creator_settings = get_creator_settings(context)

    if not creator_settings:
        return 0, 0

    ensure_creator_managed_links_for_collection(creator_settings, collection)

    created = 0
    missing = 0

    for data in preset_data.get("items", []):
        control_type = data.get("control_type", "")
        group = find_or_create_imported_group(creator_settings, collection, data.get("group_name", ""))

        item = group.items.add()
        item.control_type = control_type
        item.display_name = data.get("display_name", "")

        if control_type == "SHAPE_KEY":
            obj = lookup_imported_object(object_map, data.get("object_name", ""))

            if not obj or not core.get_shape_key(obj, data.get("shape_key_name", "")):
                group.items.remove(len(group.items) - 1)
                missing += 1
                continue

            item.object = obj
            item.shape_key_name = data.get("shape_key_name", "")
            key = core.get_shape_key(obj, item.shape_key_name)
            key.value = float(data.get("value", 0.0))

        elif control_type == "BONE_SCALE":
            armature = lookup_imported_object(object_map, data.get("armature_name", ""))

            if not armature or not core.bone_exists(armature, data.get("bone_name", "")):
                group.items.remove(len(group.items) - 1)
                missing += 1
                continue

            item.armature_object = armature
            item.bone_name = data.get("bone_name", "")
            item.scale_mode = data.get("scale_mode", "UNIFORM")
            item.min_scale = float(data.get("min_scale", 0.5))
            item.max_scale = float(data.get("max_scale", 1.5))
            assign_vector_property(item, "base_location", data.get("base_location", [0.0, 0.0, 0.0]))
            assign_vector_property(item, "base_rotation", data.get("base_rotation", [0.0, 0.0, 0.0]))
            assign_vector_property(item, "base_scale", data.get("base_scale", [1.0, 1.0, 1.0]))
            item.slider_value = float(data.get("value", 0.0))
            core.apply_group_item_control(item)

        elif control_type == "BONE_PAIR_DISTANCE":
            armature = lookup_imported_object(object_map, data.get("armature_name", ""))

            if (
                not armature
                or not core.bone_exists(armature, data.get("bone_a_name", ""))
                or not core.bone_exists(armature, data.get("bone_b_name", ""))
            ):
                group.items.remove(len(group.items) - 1)
                missing += 1
                continue

            item.armature_object = armature
            item.bone_a_name = data.get("bone_a_name", "")
            item.bone_b_name = data.get("bone_b_name", "")
            item.min_distance_factor = float(data.get("min_distance_factor", -1.0))
            item.max_distance_factor = float(data.get("max_distance_factor", 1.0))
            item.pair_apply_mode = data.get("pair_apply_mode", "POSE_X_SCALE")
            assign_vector_property(item, "base_location_a", data.get("base_location_a", [0.0, 0.0, 0.0]))
            assign_vector_property(item, "base_location_b", data.get("base_location_b", [0.0, 0.0, 0.0]))
            assign_vector_property(item, "base_rotation_a", data.get("base_rotation_a", [0.0, 0.0, 0.0]))
            assign_vector_property(item, "base_rotation_b", data.get("base_rotation_b", [0.0, 0.0, 0.0]))
            assign_vector_property(item, "base_scale_a", data.get("base_scale_a", [1.0, 1.0, 1.0]))
            assign_vector_property(item, "base_scale_b", data.get("base_scale_b", [1.0, 1.0, 1.0]))
            assign_vector_property(item, "base_matrix_a", data.get("base_matrix_a", [1.0, 0.0, 0.0, 0.0,
                                                                                      0.0, 1.0, 0.0, 0.0,
                                                                                      0.0, 0.0, 1.0, 0.0,
                                                                                      0.0, 0.0, 0.0, 1.0]))
            assign_vector_property(item, "base_matrix_b", data.get("base_matrix_b", [1.0, 0.0, 0.0, 0.0,
                                                                                      0.0, 1.0, 0.0, 0.0,
                                                                                      0.0, 0.0, 1.0, 0.0,
                                                                                      0.0, 0.0, 0.0, 1.0]))
            assign_vector_property(item, "base_rest_head_a", data.get("base_rest_head_a", [0.0, 0.0, 0.0]))
            assign_vector_property(item, "base_rest_head_b", data.get("base_rest_head_b", [0.0, 0.0, 0.0]))
            item.slider_value = float(data.get("value", 0.0))
            core.apply_group_item_control(item)

        else:
            group.items.remove(len(group.items) - 1)
            missing += 1
            continue

        group.active_item_index = len(group.items) - 1
        created += 1

    if context:
        context.view_layer.update()

    return created, missing


# ------------------------------------------------------------
# Operators: Scene Presets
# ------------------------------------------------------------

class VI_CC_PM_OT_save_current_as_preset(bpy.types.Operator):
    bl_idname = "vi_cc_pm.save_current_as_preset"
    bl_label = "Save Current as Preset"
    bl_description = "Save the current character creator shape key values and slider values as a preset in this .blend"

    def execute(self, context):
        creator_settings = get_creator_settings(context)
        pm_settings = get_pm_settings(context)

        if not creator_settings:
            self.report({"WARNING"}, "Vi Character Library data was not found on this scene.")
            return {"CANCELLED"}

        preset = pm_settings.presets.add()
        preset.name = pm_settings.new_preset_name.strip() or "Character Preset"
        pm_settings.active_preset_index = len(pm_settings.presets) - 1

        saved = 0

        for group in creator_settings.groups:
            for item in group.items:
                if save_item_to_preset(preset, group, item):
                    saved += 1

        if saved == 0:
            pm_settings.presets.remove(pm_settings.active_preset_index)
            pm_settings.active_preset_index = max(0, len(pm_settings.presets) - 1)
            self.report({"WARNING"}, "No usable controls were found to save.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved preset '{preset.name}' with {saved} controls.")
        return {"FINISHED"}


class VI_CC_PM_OT_apply_preset_to_current(bpy.types.Operator):
    bl_idname = "vi_cc_pm.apply_preset_to_current"
    bl_label = "Apply Preset to Current Creator"
    bl_description = "Apply the selected in-scene preset to the live character creator controls"

    def execute(self, context):
        pm_settings = get_pm_settings(context)
        preset = get_active_preset(pm_settings)

        if not preset:
            self.report({"WARNING"}, "Select a preset first.")
            return {"CANCELLED"}

        applied, missing = apply_preset_to_creator(context, preset)

        if applied == 0:
            self.report({"WARNING"}, "No preset controls could be matched.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Applied {applied} controls. Missing: {missing}.")
        return {"FINISHED"}


class VI_CC_PM_OT_delete_preset(bpy.types.Operator):
    bl_idname = "vi_cc_pm.delete_preset"
    bl_label = "Delete Preset"
    bl_description = "Delete the selected in-scene character preset"

    def execute(self, context):
        pm_settings = get_pm_settings(context)
        index = pm_settings.active_preset_index

        if index < 0 or index >= len(pm_settings.presets):
            return {"CANCELLED"}

        pm_settings.presets.remove(index)
        pm_settings.active_preset_index = max(0, min(index, len(pm_settings.presets) - 1))
        return {"FINISHED"}


class VI_CC_PM_OT_create_instance_from_preset(bpy.types.Operator):
    bl_idname = "vi_cc_pm.create_instance_from_preset"
    bl_label = "Create Instance from Preset"
    bl_description = "Duplicate the managed creator objects into a named collection using the selected in-scene preset values"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        creator_settings = get_creator_settings(context)
        pm_settings = get_pm_settings(context)
        preset = get_active_preset(pm_settings)

        if not creator_settings:
            self.report({"WARNING"}, "Vi Character Library data was not found on this scene.")
            return {"CANCELLED"}

        if not preset:
            self.report({"WARNING"}, "Select a preset first.")
            return {"CANCELLED"}

        previous_state = capture_creator_state(creator_settings)
        collection = None
        duplicates = []

        try:
            applied, missing = apply_preset_to_creator(context, preset)

            if applied == 0:
                self.report({"WARNING"}, "No preset controls could be matched.")
                return {"CANCELLED"}

            collection, duplicates = duplicate_creator_objects(
                context,
                pm_settings.instance_name,
                copy_object_data=pm_settings.copy_object_data,
                clear_animation_data=pm_settings.clear_animation_data,
            )

            if not collection or not duplicates:
                self.report({"WARNING"}, "No managed objects were available to duplicate.")
                return {"CANCELLED"}

        finally:
            restore_creator_state(previous_state)

        self.report({"INFO"}, f"Created instance '{collection.name}' with {len(duplicates)} objects. Applied: {applied}. Missing: {missing}.")
        return {"FINISHED"}


# ------------------------------------------------------------
# Operators: Shared Library
# ------------------------------------------------------------

class VI_CC_PM_OT_export_shared_assets(bpy.types.Operator):
    bl_idname = "vi_cc_pm.export_shared_assets"
    bl_label = "Export Template Collection"
    bl_description = "Export a complete working character template collection into CharacterLibrary/Templates"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        creator_settings = get_creator_settings(context)
        pm_settings = get_pm_settings(context)

        if not creator_settings:
            self.report({"WARNING"}, "Vi Character Library data was not found on this scene.")
            return {"CANCELLED"}

        if not pm_settings.library_root_folder:
            self.report({"WARNING"}, "Choose a Character Library Folder first.")
            return {"CANCELLED"}

        template_name = sanitize_folder_name(pm_settings.asset_set_name)
        root_folder, templates_folder, _presets_folder = ensure_library_folders(pm_settings.library_root_folder)
        blend_path = os.path.join(templates_folder, f"{template_name}.blend")
        previous_state = capture_creator_state(creator_settings)
        template_collection = get_template_collection_for_export(context, creator_settings, pm_settings)

        if not template_collection:
            self.report({"WARNING"}, "Choose a Template Collection, or put the managed character objects inside one collection.")
            return {"CANCELLED"}

        template_objects = list(iter_collection_objects_recursive(template_collection))

        if not template_objects:
            self.report({"WARNING"}, "Template Collection is empty.")
            return {"CANCELLED"}

        source_name_state = mark_asset_source_names(template_objects)

        try:
            for group in creator_settings.groups:
                for item in group.items:
                    core.reset_group_item(item)

            export_collection_to_blend(template_collection, blend_path)

        finally:
            restore_creator_state(previous_state)
            restore_asset_source_names(source_name_state)

        self.report({"INFO"}, f"Exported template collection: {os.path.join(root_folder, 'Templates', template_name + '.blend')}")
        return {"FINISHED"}


class VI_CC_PM_OT_export_preset_json(bpy.types.Operator):
    bl_idname = "vi_cc_pm.export_preset_json"
    bl_label = "Export Preset JSON"
    bl_description = "Export the selected preset as a lightweight JSON file that references the shared asset set"

    def execute(self, context):
        creator_settings = get_creator_settings(context)
        pm_settings = get_pm_settings(context)
        preset = get_active_preset(pm_settings)

        if not creator_settings:
            self.report({"WARNING"}, "Vi Character Library data was not found on this scene.")
            return {"CANCELLED"}

        if not preset:
            self.report({"WARNING"}, "Select a preset first.")
            return {"CANCELLED"}

        if not pm_settings.library_root_folder:
            self.report({"WARNING"}, "Choose a Character Library Folder first.")
            return {"CANCELLED"}

        template_name = sanitize_folder_name(pm_settings.asset_set_name)
        root_folder, _templates_folder, presets_folder = ensure_library_folders(pm_settings.library_root_folder)
        preset_path = os.path.join(presets_folder, f"{sanitize_folder_name(preset.name)}.json")
        previous_state = capture_creator_state(creator_settings)
        template_collection = get_template_collection_for_export(context, creator_settings, pm_settings)
        template_collection_name = template_collection.name if template_collection else template_name

        try:
            applied, missing = apply_preset_to_creator(context, preset)

            if applied == 0:
                self.report({"WARNING"}, "No preset controls could be matched.")
                return {"CANCELLED"}

            data = full_preset_snapshot_from_creator(context, preset, template_name, template_collection_name)

            with open(preset_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)

        finally:
            restore_creator_state(previous_state)

        self.report({"INFO"}, f"Exported preset JSON: {preset_path}")
        return {"FINISHED"}


class VI_CC_PM_OT_import_instance_from_library(bpy.types.Operator):
    bl_idname = "vi_cc_pm.import_instance_from_library"
    bl_label = "Import Instance from Library Preset"
    bl_description = "Append the shared asset set referenced by a preset JSON, apply the preset, and create a named collection"

    def execute(self, context):
        pm_settings = get_pm_settings(context)
        preset_path = bpy.path.abspath(pm_settings.import_preset_file)

        if not preset_path:
            self.report({"WARNING"}, "Choose an Import Preset JSON first.")
            return {"CANCELLED"}

        preset_data, error = load_shared_preset_json(preset_path)

        if error:
            self.report({"WARNING"}, error)
            return {"CANCELLED"}

        template_name = preset_data.get("template") or preset_data.get("asset_set", "")

        if not template_name:
            self.report({"WARNING"}, "Preset JSON does not specify a template.")
            return {"CANCELLED"}

        root_folder = bpy.path.abspath(pm_settings.library_root_folder)

        if not root_folder:
            # Common case: selected file is CharacterLibrary/Presets/Name.json.
            root_folder = os.path.dirname(os.path.dirname(preset_path))

        instance_name = pm_settings.instance_name.strip() or preset_data.get("preset_name", "Character_Instance")
        collection, object_map, error = append_template_collection(context, root_folder, preset_data, instance_name)

        if error:
            self.report({"WARNING"}, error)
            return {"CANCELLED"}

        rebuilt, rebuild_missing = rebuild_creator_controls_from_preset_data(context, preset_data, collection, object_map)

        # Fallback: even if the slider UI could not be rebuilt, try directly applying values.
        applied, missing = apply_preset_data_to_object_map(context, preset_data, object_map)

        if rebuilt == 0 and applied == 0:
            self.report({"WARNING"}, "Imported assets, but no preset controls could be rebuilt or applied.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Imported '{collection.name}'. Sliders: {rebuilt}. Applied: {applied}. Missing: {rebuild_missing + missing}.")
        return {"FINISHED"}





def snapshot_current_creator_to_preset(creator_settings, preset):
    preset.items.clear()

    for group in creator_settings.groups:
        for item in group.items:
            preset_item = preset.items.add()
            preset_item.group_name = group.name
            preset_item.control_type = item.control_type
            preset_item.display_name = core.item_display_label(item)

            if item.control_type == "SHAPE_KEY":
                preset_item.object_name = item.object.name if item.object else ""
                preset_item.shape_key_name = item.shape_key_name
                key = core.get_shape_key(item.object, item.shape_key_name)
                preset_item.value = key.value if key else 0.0

            elif item.control_type == "BONE_SCALE":
                preset_item.armature_name = item.armature_object.name if item.armature_object else ""
                preset_item.bone_name = item.bone_name
                preset_item.value = item.slider_value

            elif item.control_type == "BONE_PAIR_DISTANCE":
                preset_item.armature_name = item.armature_object.name if item.armature_object else ""
                preset_item.bone_a_name = item.bone_a_name
                preset_item.bone_b_name = item.bone_b_name
                preset_item.value = item.slider_value

    return len(preset.items)


class VI_CC_PM_OT_save_character_to_library(bpy.types.Operator):
    bl_idname = "vi_cc_pm.save_character_to_library"
    bl_label = "Save Character to Library"
    bl_description = "Export the current template collection and write a linked lightweight character preset JSON"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        creator_settings = get_creator_settings(context)
        pm_settings = get_pm_settings(context)

        if not creator_settings:
            self.report({"WARNING"}, "Vi Character Library data was not found on this scene.")
            return {"CANCELLED"}

        if not pm_settings.library_root_folder:
            self.report({"WARNING"}, "Choose a Character Library Folder first.")
            return {"CANCELLED"}

        character_name = sanitize_folder_name(pm_settings.new_preset_name or pm_settings.instance_name or "Character")
        template_name = sanitize_folder_name(pm_settings.asset_set_name or "DefaultCharacterTemplate")
        root_folder, templates_folder, presets_folder = ensure_library_folders(pm_settings.library_root_folder)

        template_collection = get_template_collection_for_export(context, creator_settings, pm_settings)

        if not template_collection:
            self.report({"WARNING"}, "Choose a Template Collection, or put the managed character objects inside one collection.")
            return {"CANCELLED"}

        template_objects = list(iter_collection_objects_recursive(template_collection))

        if not template_objects:
            self.report({"WARNING"}, "Template Collection is empty.")
            return {"CANCELLED"}

        # Capture the visible character state as full JSON BEFORE neutralizing the template.
        # This keeps shape-key values, bone-slider values, pair-bone ranges, baselines,
        # base matrices, and pair apply modes. The older streamlined build accidentally
        # saved only the simple in-scene preset fields, so imported characters loaded
        # the model but not the creator values.
        preset = pm_settings.presets.add()
        preset.name = character_name

        for group in creator_settings.groups:
            for item in group.items:
                save_item_to_preset(preset, group, item)

        data = full_preset_snapshot_from_creator(
            context,
            preset,
            template_name,
            template_collection.name
        )

        previous_state = capture_creator_state(creator_settings)
        source_name_state = mark_asset_source_names(template_objects)

        template_path = os.path.join(templates_folder, f"{template_name}.blend")
        preset_path = os.path.join(presets_folder, f"{character_name}.json")

        try:
            # Export the reusable template in neutral creator state.
            for group in creator_settings.groups:
                for item in group.items:
                    core.reset_group_item(item)

            export_collection_to_blend(template_collection, template_path)

            with open(preset_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)

        finally:
            restore_creator_state(previous_state)
            restore_asset_source_names(source_name_state)

            # Keep the in-scene preset useful instead of deleting it.
            pm_settings.active_preset_index = len(pm_settings.presets) - 1

        self.report({"INFO"}, f"Saved character '{character_name}' using template '{template_name}'.")
        return {"FINISHED"}


class VI_CC_PM_OT_apply_library_preset_to_current(bpy.types.Operator):
    bl_idname = "vi_cc_pm.apply_library_preset_to_current"
    bl_label = "Load Preset Onto Current Creator"
    bl_description = "Load a preset JSON only and apply its slider values to the currently open creator/template"

    def execute(self, context):
        creator_settings = get_creator_settings(context)
        pm_settings = get_pm_settings(context)
        preset_path = bpy.path.abspath(pm_settings.import_preset_file)

        if not creator_settings:
            self.report({"WARNING"}, "Vi Character Library data was not found on this scene.")
            return {"CANCELLED"}

        if not preset_path:
            self.report({"WARNING"}, "Choose a Preset JSON first.")
            return {"CANCELLED"}

        preset_data, error = load_shared_preset_json(preset_path)

        if error:
            self.report({"WARNING"}, error)
            return {"CANCELLED"}

        object_map = {}

        for managed in creator_settings.managed_objects:
            if managed.object:
                object_map[managed.object.name] = managed.object

        for managed in creator_settings.managed_armatures:
            if managed.object:
                object_map[managed.object.name] = managed.object

        applied, missing = apply_preset_data_to_object_map(context, preset_data, object_map)

        if applied == 0:
            self.report({"WARNING"}, "No preset controls could be matched to the current creator.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Loaded preset onto current creator. Applied: {applied}. Missing: {missing}.")
        return {"FINISHED"}

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------

class VI_CC_PM_UL_presets(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name", text="", emboss=False, icon="PRESET")


class VI_CC_PM_PT_presets(bpy.types.Panel):
    bl_label = "Vi Character Library"
    bl_idname = "VI_CC_PM_PT_presets"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Character Creator"

    def draw(self, context):
        layout = self.layout
        pm_settings = get_pm_settings(context)
        creator_settings = get_creator_settings(context)

        box = layout.box()
        box.label(text="Export / Save Character", icon="FILE_TICK")
        box.prop(pm_settings, "library_root_folder")
        box.prop(pm_settings, "new_preset_name", text="Character Name")
        box.prop(pm_settings, "asset_set_name", text="Template Name")
        box.prop(pm_settings, "template_collection")
        row = box.row()
        row.enabled = bool(creator_settings)
        row.operator("vi_cc_pm.save_character_to_library", text="Export Character to Library", icon="EXPORT")
        box.label(text="Writes Templates/*.blend and Presets/*.json together.")

        box = layout.box()
        box.label(text="Import / Load Character", icon="IMPORT")
        box.prop(pm_settings, "import_preset_file", text="Preset JSON")
        box.prop(pm_settings, "instance_name", text="Instance Name")

        row = box.row(align=True)
        row.enabled = bool(creator_settings)
        row.operator("vi_cc_pm.apply_library_preset_to_current", text="Load Preset Only", icon="PRESET")

        row = box.row(align=True)
        row.operator("vi_cc_pm.import_instance_from_library", text="Load Template + Preset", icon="OUTLINER_COLLECTION")

        box.label(text="Preset Only uses the current open creator.")
        box.label(text="Template + Preset appends the saved template collection.")

# ------------------------------------------------------------
# Registration
# ------------------------------------------------------------

classes = (
    VI_CC_PM_PresetItem,
    VI_CC_PM_CharacterPreset,
    VI_CC_PM_Settings,
    VI_CC_PM_OT_save_current_as_preset,
    VI_CC_PM_OT_apply_preset_to_current,
    VI_CC_PM_OT_delete_preset,
    VI_CC_PM_OT_create_instance_from_preset,
    VI_CC_PM_OT_export_shared_assets,
    VI_CC_PM_OT_export_preset_json,
    VI_CC_PM_OT_import_instance_from_library,
    VI_CC_PM_OT_save_character_to_library,
    VI_CC_PM_OT_apply_library_preset_to_current,
    VI_CC_PM_UL_presets,
    VI_CC_PM_PT_presets,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.vi_cc_preset_manager = bpy.props.PointerProperty(type=VI_CC_PM_Settings)


def unregister():
    if hasattr(bpy.types.Scene, "vi_cc_preset_manager"):
        del bpy.types.Scene.vi_cc_preset_manager

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
