bl_info = {
    "name": "Vi Character Creator",
    "author": "Vi",
    "version": (0, 3, 6),
    "blender": (4, 0, 0),
    "category": "Object",
}

import bpy
from mathutils import Matrix, Vector


# ------------------------------------------------------------
# Update Callbacks
# ------------------------------------------------------------

# These are referenced by PropertyGroup properties and must exist before the classes.
def update_bone_control_from_slider(self, context):
    apply_group_item_control(self)


# ------------------------------------------------------------
# Data
# ------------------------------------------------------------

class VI_CC_ManagedObject(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(name="Object", type=bpy.types.Object)


class VI_CC_ManagedArmature(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(name="Armature", type=bpy.types.Object)


class VI_CC_GroupItem(bpy.types.PropertyGroup):
    control_type: bpy.props.EnumProperty(
        name="Control Type",
        items=[
            ("SHAPE_KEY", "Shape Key", "A mesh shape key slider"),
            ("BONE_SCALE", "Bone Scale", "Scale one pose bone from a stored baseline"),
            ("BONE_PAIR_DISTANCE", "Bone Pair Distance", "Move two pose bones closer or farther apart from a stored baseline"),
        ],
        default="SHAPE_KEY"
    )

    display_name: bpy.props.StringProperty(name="Display Name")

    # Shape key control data.
    object: bpy.props.PointerProperty(name="Object", type=bpy.types.Object)
    shape_key_name: bpy.props.StringProperty(name="Shape Key")

    # Bone control data.
    armature_object: bpy.props.PointerProperty(name="Armature", type=bpy.types.Object)
    bone_name: bpy.props.StringProperty(name="Bone")
    bone_a_name: bpy.props.StringProperty(name="Bone A")
    bone_b_name: bpy.props.StringProperty(name="Bone B")

    slider_value: bpy.props.FloatProperty(
        name="Value",
        description="Creator slider value for this bone control",
        default=0.0,
        min=-1.0,
        max=1.0,
        update=update_bone_control_from_slider
    )

    scale_mode: bpy.props.EnumProperty(
        name="Scale Mode",
        items=[
            ("UNIFORM", "Uniform", "Scale X, Y, and Z together"),
            ("X", "X", "Scale local X only"),
            ("Y", "Y", "Scale local Y only"),
            ("Z", "Z", "Scale local Z only"),
        ],
        default="UNIFORM",
        update=update_bone_control_from_slider
    )

    min_scale: bpy.props.FloatProperty(
        name="Min Scale",
        description="Scale factor at slider value -1",
        default=0.5,
        min=0.001,
        update=update_bone_control_from_slider
    )

    max_scale: bpy.props.FloatProperty(
        name="Max Scale",
        description="Scale factor at slider value +1",
        default=1.5,
        min=0.001,
        update=update_bone_control_from_slider
    )

    min_distance_factor: bpy.props.FloatProperty(
        name="Min Pair Scale Offset",
        description="Pair scale offset at slider value -1. A value of -1.0 means 0x scale; 0.0 means neutral",
        default=-1.0,
        min=-0.999,
        max=100.0,
        update=update_bone_control_from_slider
    )

    max_distance_factor: bpy.props.FloatProperty(
        name="Max Pair Scale Offset",
        description="Pair scale offset at slider value +1. A value of 1.0 means 2x scale; 0.0 means neutral",
        default=1.0,
        min=-0.999,
        max=100.0,
        update=update_bone_control_from_slider
    )

    base_location: bpy.props.FloatVectorProperty(name="Base Location", size=3, default=(0.0, 0.0, 0.0))
    base_rotation: bpy.props.FloatVectorProperty(name="Base Rotation", size=3, default=(0.0, 0.0, 0.0))
    base_scale: bpy.props.FloatVectorProperty(name="Base Scale", size=3, default=(1.0, 1.0, 1.0))

    base_location_a: bpy.props.FloatVectorProperty(name="Base Location A", size=3, default=(0.0, 0.0, 0.0))
    base_location_b: bpy.props.FloatVectorProperty(name="Base Location B", size=3, default=(0.0, 0.0, 0.0))
    base_rotation_a: bpy.props.FloatVectorProperty(name="Base Rotation A", size=3, default=(0.0, 0.0, 0.0))
    base_rotation_b: bpy.props.FloatVectorProperty(name="Base Rotation B", size=3, default=(0.0, 0.0, 0.0))
    base_scale_a: bpy.props.FloatVectorProperty(name="Base Scale A", size=3, default=(1.0, 1.0, 1.0))
    base_scale_b: bpy.props.FloatVectorProperty(name="Base Scale B", size=3, default=(1.0, 1.0, 1.0))

    # Bone-pair distance controls need real pose-space positions, not just
    # pbone.location. Many rigs/control rigs have pbone.location = (0,0,0)
    # even though the visible controls are clearly separated in the armature.
    # Store each pose bone's full matrix so pair sliders can move controls
    # around their actual pose-space positions.
    base_matrix_a: bpy.props.FloatVectorProperty(
        name="Base Matrix A",
        size=16,
        default=(1.0, 0.0, 0.0, 0.0,
                 0.0, 1.0, 0.0, 0.0,
                 0.0, 0.0, 1.0, 0.0,
                 0.0, 0.0, 0.0, 1.0)
    )

    base_matrix_b: bpy.props.FloatVectorProperty(
        name="Base Matrix B",
        size=16,
        default=(1.0, 0.0, 0.0, 0.0,
                 0.0, 1.0, 0.0, 0.0,
                 0.0, 0.0, 1.0, 0.0,
                 0.0, 0.0, 0.0, 1.0)
    )

    # Rest-head positions give pair controls a stable distance vector even
    # when pose transforms are all zero. This is usually the important case
    # for control rigs: the control bones are visibly separated by rest pose,
    # but their pose location channels are still zero.
    base_rest_head_a: bpy.props.FloatVectorProperty(name="Base Rest Head A", size=3, default=(0.0, 0.0, 0.0))
    base_rest_head_b: bpy.props.FloatVectorProperty(name="Base Rest Head B", size=3, default=(0.0, 0.0, 0.0))

    pair_apply_mode: bpy.props.EnumProperty(
        name="Pair Apply Mode",
        description="How bone-pair distance controls are applied",
        items=[
            ("POSE_X_SCALE", "Pose X Scale", "Mimic selecting both pose bones and scaling them on X around their shared center; best for control rigs"),
            ("LOCATION_OFFSET", "Location Offset", "Offset pose location channels using the bones' rest-head distance vector"),
            ("MATRIX", "Pose Matrix", "Write full pose matrices; useful for simple rigs, but constraints may override it"),
        ],
        default="POSE_X_SCALE",
        update=update_bone_control_from_slider
    )


class VI_CC_Group(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Group Name", default="New Group")
    items: bpy.props.CollectionProperty(type=VI_CC_GroupItem)
    active_item_index: bpy.props.IntProperty(default=0)


class VI_CC_Settings(bpy.types.PropertyGroup):
    managed_objects: bpy.props.CollectionProperty(type=VI_CC_ManagedObject)
    active_managed_object_index: bpy.props.IntProperty(default=0)

    managed_armatures: bpy.props.CollectionProperty(type=VI_CC_ManagedArmature)
    active_managed_armature_index: bpy.props.IntProperty(default=0)

    groups: bpy.props.CollectionProperty(type=VI_CC_Group)
    active_group_index: bpy.props.IntProperty(default=0)

    search_filter: bpy.props.StringProperty(
        name="Search Shape Keys",
        description="Filter discovered shape keys by name",
        default=""
    )

    bone_search_filter: bpy.props.StringProperty(
        name="Search Bones",
        description="Filter discovered bones by name",
        default=""
    )

    selected_armature: bpy.props.PointerProperty(name="Armature", type=bpy.types.Object)
    selected_bone_name: bpy.props.StringProperty(name="Bone")
    selected_bone_a_name: bpy.props.StringProperty(name="Bone A")
    selected_bone_b_name: bpy.props.StringProperty(name="Bone B")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def get_settings(context):
    return context.scene.vi_character_creator


def object_has_shape_keys(obj):
    return (
        obj
        and obj.type == "MESH"
        and obj.data
        and obj.data.shape_keys
        and obj.data.shape_keys.key_blocks
    )


def is_valid_armature(obj):
    # Keep this deliberately loose for control rigs. Some rig setups expose
    # non-deforming/control bones or may not have an initialized pose object
    # until Blender evaluates the armature. For management/discovery, an
    # Armature object with armature data is enough.
    return bool(obj and obj.type == "ARMATURE" and getattr(obj, "data", None))


def is_object_managed(settings, obj):
    return any(item.object == obj for item in settings.managed_objects)


def is_armature_managed(settings, obj):
    return any(item.object == obj for item in settings.managed_armatures)


def get_active_group(settings):
    if not settings.groups:
        return None

    index = settings.active_group_index

    if index < 0 or index >= len(settings.groups):
        return None

    return settings.groups[index]


def get_active_group_item(group):
    if not group or not group.items:
        return None

    index = group.active_item_index

    if index < 0 or index >= len(group.items):
        return None

    return group.items[index]


def get_shape_key(obj, shape_key_name):
    if not object_has_shape_keys(obj):
        return None

    key_blocks = obj.data.shape_keys.key_blocks

    if shape_key_name not in key_blocks:
        return None

    return key_blocks[shape_key_name]


def bone_exists(armature, bone_name):
    if not armature or armature.type != "ARMATURE" or not bone_name:
        return False

    if getattr(armature, "pose", None) and armature.pose.bones.get(bone_name):
        return True

    if getattr(armature, "data", None) and armature.data.bones.get(bone_name):
        return True

    return False


def get_pose_bone(armature, bone_name):
    # Pose bones are what we actually manipulate, but validation should not
    # reject control-rig bones just because they are non-deforming or hidden.
    if not armature or armature.type != "ARMATURE" or not bone_name:
        return None

    if not getattr(armature, "pose", None):
        return None

    return armature.pose.bones.get(bone_name)


def lerp_float(a, b, t):
    return a + ((b - a) * t)


def factor_from_slider(value, min_factor, max_factor):
    if value < 0.0:
        return lerp_float(1.0, min_factor, abs(value))

    return lerp_float(1.0, max_factor, value)


def offset_from_centered_slider(value, min_offset, max_offset):
    # Used by bone-pair Pose X Scale controls. Unlike factor_from_slider,
    # this keeps slider value 0.0 truly neutral.
    if value < 0.0:
        return lerp_float(0.0, min_offset, abs(value))

    return lerp_float(0.0, max_offset, value)


def iter_discovered_shape_keys(settings):
    search = settings.search_filter.lower().strip()

    for managed in settings.managed_objects:
        obj = managed.object

        if not object_has_shape_keys(obj):
            continue

        for key in obj.data.shape_keys.key_blocks:
            if key.name == "Basis":
                continue

            label = f"{obj.name} {key.name}".lower()

            if search and search not in label:
                continue

            yield obj, key


def iter_discovered_bones(settings):
    search = settings.bone_search_filter.lower().strip()

    for managed in settings.managed_armatures:
        armature = managed.object

        if not is_valid_armature(armature):
            continue

        # Prefer pose bones because those are what sliders manipulate, but
        # fall back to armature data bones so loose/control-rig setups still
        # show up instead of failing discovery.
        bones = armature.pose.bones if getattr(armature, "pose", None) else armature.data.bones

        for bone in bones:
            label = f"{armature.name} {bone.name}".lower()

            if search and search not in label:
                continue

            yield armature, bone


def group_contains_shape_key(group, obj, shape_key_name):
    return any(
        item.control_type == "SHAPE_KEY"
        and item.object == obj
        and item.shape_key_name == shape_key_name
        for item in group.items
    )


def group_contains_bone_scale(group, armature, bone_name):
    return any(
        item.control_type == "BONE_SCALE"
        and item.armature_object == armature
        and item.bone_name == bone_name
        for item in group.items
    )


def group_contains_bone_pair(group, armature, bone_a_name, bone_b_name):
    return any(
        item.control_type == "BONE_PAIR_DISTANCE"
        and item.armature_object == armature
        and (
            (item.bone_a_name == bone_a_name and item.bone_b_name == bone_b_name)
            or (item.bone_a_name == bone_b_name and item.bone_b_name == bone_a_name)
        )
        for item in group.items
    )


def active_group_contains_shape_key(settings, obj, shape_key_name):
    group = get_active_group(settings)
    return bool(group and group_contains_shape_key(group, obj, shape_key_name))


def active_group_contains_bone_scale(settings, armature, bone_name):
    group = get_active_group(settings)
    return bool(group and group_contains_bone_scale(group, armature, bone_name))


def active_group_contains_bone_pair(settings, armature, bone_a_name, bone_b_name):
    group = get_active_group(settings)
    return bool(group and group_contains_bone_pair(group, armature, bone_a_name, bone_b_name))


def capture_single_bone_baseline(item):
    pbone = get_pose_bone(item.armature_object, item.bone_name)

    if not pbone:
        return False

    item.base_location = pbone.location
    item.base_rotation = pbone.rotation_euler
    item.base_scale = pbone.scale

    return True


def matrix_to_flat_tuple(matrix):
    return tuple(matrix[row][col] for row in range(4) for col in range(4))


def flat_tuple_to_matrix(values):
    return Matrix((
        (values[0], values[1], values[2], values[3]),
        (values[4], values[5], values[6], values[7]),
        (values[8], values[9], values[10], values[11]),
        (values[12], values[13], values[14], values[15]),
    ))


def capture_pair_bone_baseline(item):
    pbone_a = get_pose_bone(item.armature_object, item.bone_a_name)
    pbone_b = get_pose_bone(item.armature_object, item.bone_b_name)

    if not pbone_a or not pbone_b:
        return False

    matrix_a = pbone_a.matrix.copy()
    matrix_b = pbone_b.matrix.copy()

    # Store the actual editable pose channels as the slider baseline.
    # Do not use matrix translation for base_location_a/b, because many
    # control rigs keep pbone.location at zero while the rest bones are
    # visibly separated. The slider should add offsets to these channels.
    item.base_location_a = pbone_a.location
    item.base_location_b = pbone_b.location
    item.base_rotation_a = pbone_a.rotation_euler
    item.base_rotation_b = pbone_b.rotation_euler
    item.base_scale_a = pbone_a.scale
    item.base_scale_b = pbone_b.scale

    # Keep matrix baselines for the optional matrix-writing mode.
    item.base_matrix_a = matrix_to_flat_tuple(matrix_a)
    item.base_matrix_b = matrix_to_flat_tuple(matrix_b)

    # Store rest-head positions as the distance vector source. This makes
    # pair controls work when both pbone.location channels start at zero.
    item.base_rest_head_a = pbone_a.bone.head_local
    item.base_rest_head_b = pbone_b.bone.head_local

    return True


def apply_bone_scale_control(item):
    pbone = get_pose_bone(item.armature_object, item.bone_name)

    if not pbone:
        return False

    factor = factor_from_slider(item.slider_value, item.min_scale, item.max_scale)
    base_scale = Vector(item.base_scale)

    new_scale = Vector(base_scale)

    if item.scale_mode == "UNIFORM":
        new_scale = base_scale * factor
    elif item.scale_mode == "X":
        new_scale.x = base_scale.x * factor
    elif item.scale_mode == "Y":
        new_scale.y = base_scale.y * factor
    elif item.scale_mode == "Z":
        new_scale.z = base_scale.z * factor

    pbone.location = Vector(item.base_location)
    pbone.rotation_euler = Vector(item.base_rotation)
    pbone.scale = new_scale

    return True



def get_bone_selected_safe(bone):
    if hasattr(bone, "select_get"):
        try:
            return bool(bone.select_get())
        except Exception:
            pass

    return bool(getattr(bone, "select", False))


def set_bone_selected_safe(bone, selected):
    if hasattr(bone, "select_set"):
        try:
            bone.select_set(bool(selected))
            return
        except Exception:
            pass

    if hasattr(bone, "select"):
        try:
            bone.select = bool(selected)
        except Exception:
            pass


def get_bone_head_selected_safe(bone):
    return bool(getattr(bone, "select_head", get_bone_selected_safe(bone)))


def set_bone_head_selected_safe(bone, selected):
    if hasattr(bone, "select_head"):
        try:
            bone.select_head = bool(selected)
        except Exception:
            pass


def get_bone_tail_selected_safe(bone):
    return bool(getattr(bone, "select_tail", get_bone_selected_safe(bone)))


def set_bone_tail_selected_safe(bone, selected):
    if hasattr(bone, "select_tail"):
        try:
            bone.select_tail = bool(selected)
        except Exception:
            pass


def select_only_pose_bones(armature, bone_names):
    if not armature or armature.type != "ARMATURE":
        return False

    for bone in armature.data.bones:
        set_bone_selected_safe(bone, False)

    first_bone = None

    for bone_name in bone_names:
        bone = armature.data.bones.get(bone_name)

        if not bone:
            continue

        set_bone_selected_safe(bone, True)
        set_bone_head_selected_safe(bone, True)
        set_bone_tail_selected_safe(bone, True)

        if first_bone is None:
            first_bone = bone

    if first_bone:
        armature.data.bones.active = first_bone
        return True

    return False


def restore_pair_baseline_matrices(item, pbone_a, pbone_b):
    matrix_a = flat_tuple_to_matrix(item.base_matrix_a)
    matrix_b = flat_tuple_to_matrix(item.base_matrix_b)

    # Old controls may not have useful matrix baselines yet.
    if matrix_a.translation.length == 0.0 and matrix_b.translation.length == 0.0:
        capture_pair_bone_baseline(item)
        matrix_a = flat_tuple_to_matrix(item.base_matrix_a)
        matrix_b = flat_tuple_to_matrix(item.base_matrix_b)

    pbone_a.matrix = matrix_a
    pbone_b.matrix = matrix_b

    return matrix_a, matrix_b


def apply_pair_pose_x_scale(item, pbone_a, pbone_b, factor):
    armature = item.armature_object

    if not armature:
        return False

    old_active = bpy.context.view_layer.objects.active
    old_mode = old_active.mode if old_active else "OBJECT"
    old_selected_objects = list(bpy.context.selected_objects)

    old_bone_selection = []
    old_active_bone_name = None

    if armature.type == "ARMATURE":
        old_active_bone = armature.data.bones.active
        old_active_bone_name = old_active_bone.name if old_active_bone else None

        for bone in armature.data.bones:
            old_bone_selection.append((bone.name, get_bone_selected_safe(bone), get_bone_head_selected_safe(bone), get_bone_tail_selected_safe(bone)))

    try:
        if old_active and old_active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        matrix_a, matrix_b = restore_pair_baseline_matrices(item, pbone_a, pbone_b)
        bpy.context.view_layer.update()

        if not select_only_pose_bones(armature, [item.bone_a_name, item.bone_b_name]):
            return False

        center = (matrix_a.translation + matrix_b.translation) * 0.5

        # This intentionally uses Blender's own Pose Mode transform operator,
        # because control rigs often respond correctly to selected-bone X scale
        # while direct matrix/location edits are ignored or overwritten.
        bpy.ops.transform.resize(
            value=(factor, 1.0, 1.0),
            orient_type="GLOBAL",
            orient_matrix_type="GLOBAL",
            center_override=center,
            use_proportional_edit=False
        )

        bpy.context.view_layer.update()
        return True

    finally:
        if armature and armature.type == "ARMATURE":
            for bone_name, selected, selected_head, selected_tail in old_bone_selection:
                bone = armature.data.bones.get(bone_name)

                if bone:
                    set_bone_selected_safe(bone, selected)
                    set_bone_head_selected_safe(bone, selected_head)
                    set_bone_tail_selected_safe(bone, selected_tail)

            if old_active_bone_name and old_active_bone_name in armature.data.bones:
                armature.data.bones.active = armature.data.bones[old_active_bone_name]

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")

        for obj in old_selected_objects:
            if obj and obj.name in bpy.data.objects:
                obj.select_set(True)

        if old_active and old_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = old_active

            if old_mode != "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode=old_mode)
                except Exception:
                    pass


def apply_bone_pair_distance_control(item):
    pbone_a = get_pose_bone(item.armature_object, item.bone_a_name)
    pbone_b = get_pose_bone(item.armature_object, item.bone_b_name)

    if not pbone_a or not pbone_b:
        return False

    # Bone-pair controls use a centered scale-offset range:
    # - slider  0.0 = neutral pose scale factor 1.0
    # - slider -1.0 = 1.0 + Min Pair Scale Offset
    # - slider +1.0 = 1.0 + Max Pair Scale Offset
    # Default -1..+1 therefore maps to 0x..2x.
    # This must NOT use factor_from_slider(), because that helper treats
    # 1.0 as the neutral value and would make slider 0 become 2x scale.
    scale_offset = offset_from_centered_slider(
        item.slider_value,
        item.min_distance_factor,
        item.max_distance_factor
    )
    factor = max(0.001, 1.0 + scale_offset)

    if item.pair_apply_mode == "POSE_X_SCALE":
        return apply_pair_pose_x_scale(item, pbone_a, pbone_b, factor)

    if item.pair_apply_mode == "MATRIX":
        matrix_a = flat_tuple_to_matrix(item.base_matrix_a)
        matrix_b = flat_tuple_to_matrix(item.base_matrix_b)

        base_a = matrix_a.translation.copy()
        base_b = matrix_b.translation.copy()

        if (base_a - base_b).length == 0.0:
            if not capture_pair_bone_baseline(item):
                return False

            matrix_a = flat_tuple_to_matrix(item.base_matrix_a)
            matrix_b = flat_tuple_to_matrix(item.base_matrix_b)
            base_a = matrix_a.translation.copy()
            base_b = matrix_b.translation.copy()

        midpoint = (base_a + base_b) * 0.5
        matrix_a.translation = midpoint + ((base_a - midpoint) * factor)
        matrix_b.translation = midpoint + ((base_b - midpoint) * factor)

        pbone_a.matrix = matrix_a
        pbone_b.matrix = matrix_b
    else:
        rest_a = Vector(item.base_rest_head_a)
        rest_b = Vector(item.base_rest_head_b)

        if (rest_a - rest_b).length == 0.0:
            if not capture_pair_bone_baseline(item):
                return False

            rest_a = Vector(item.base_rest_head_a)
            rest_b = Vector(item.base_rest_head_b)

        midpoint = (rest_a + rest_b) * 0.5
        target_a = midpoint + ((rest_a - midpoint) * factor)
        target_b = midpoint + ((rest_b - midpoint) * factor)

        offset_a = target_a - rest_a
        offset_b = target_b - rest_b

        pbone_a.location = Vector(item.base_location_a) + offset_a
        pbone_b.location = Vector(item.base_location_b) + offset_b
        pbone_a.rotation_euler = Vector(item.base_rotation_a)
        pbone_b.rotation_euler = Vector(item.base_rotation_b)
        pbone_a.scale = Vector(item.base_scale_a)
        pbone_b.scale = Vector(item.base_scale_b)

    if item.armature_object:
        item.armature_object.update_tag(refresh={"OBJECT", "DATA"})
        bpy.context.view_layer.update()

    return True

def apply_group_item_control(item):
    if item.control_type == "BONE_SCALE":
        return apply_bone_scale_control(item)

    if item.control_type == "BONE_PAIR_DISTANCE":
        return apply_bone_pair_distance_control(item)

    return False


def reset_group_item(item):
    if item.control_type == "SHAPE_KEY":
        key = get_shape_key(item.object, item.shape_key_name)

        if key:
            key.value = 0.0
            return True

    elif item.control_type in {"BONE_SCALE", "BONE_PAIR_DISTANCE"}:
        item.slider_value = 0.0
        return apply_group_item_control(item)

    return False


def recapture_bone_control_baseline(item, reset_slider=True):
    success = False

    if item.control_type == "BONE_SCALE":
        success = capture_single_bone_baseline(item)
    elif item.control_type == "BONE_PAIR_DISTANCE":
        success = capture_pair_bone_baseline(item)

    if success and reset_slider:
        item.slider_value = 0.0

    return success


def item_display_label(item):
    if item.display_name:
        return item.display_name

    if item.control_type == "SHAPE_KEY":
        return item.shape_key_name

    if item.control_type == "BONE_SCALE":
        return item.bone_name

    if item.control_type == "BONE_PAIR_DISTANCE":
        return f"{item.bone_a_name} / {item.bone_b_name}"

    return "Control"


def item_source_label(item):
    if item.control_type == "SHAPE_KEY":
        obj_name = item.object.name if item.object else "Missing Object"
        return f"Shape Key: {obj_name} : {item.shape_key_name}"

    if item.control_type == "BONE_SCALE":
        armature_name = item.armature_object.name if item.armature_object else "Missing Armature"
        return f"Bone Scale: {armature_name} : {item.bone_name}"

    if item.control_type == "BONE_PAIR_DISTANCE":
        armature_name = item.armature_object.name if item.armature_object else "Missing Armature"
        return f"Bone Pair: {armature_name} : {item.bone_a_name} / {item.bone_b_name}"

    return "Unknown Control"


def select_only_active_object(context, obj):
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    context.view_layer.objects.active = obj


# ------------------------------------------------------------
# Managed Object Operators
# ------------------------------------------------------------

class VI_CC_OT_add_selected_object(bpy.types.Operator):
    bl_idname = "vi_cc.add_selected_object"
    bl_label = "Add Selected Mesh"
    bl_description = "Add the selected mesh object to the character creator"

    def execute(self, context):
        settings = get_settings(context)
        obj = context.object

        if not object_has_shape_keys(obj):
            self.report({"WARNING"}, "Selected object must be a mesh with shape keys.")
            return {"CANCELLED"}

        if is_object_managed(settings, obj):
            self.report({"INFO"}, "Object is already managed.")
            return {"CANCELLED"}

        item = settings.managed_objects.add()
        item.object = obj
        settings.active_managed_object_index = len(settings.managed_objects) - 1

        return {"FINISHED"}


class VI_CC_OT_remove_managed_object(bpy.types.Operator):
    bl_idname = "vi_cc.remove_managed_object"
    bl_label = "Remove Managed Mesh"
    bl_description = "Remove the active managed mesh"

    def execute(self, context):
        settings = get_settings(context)
        index = settings.active_managed_object_index

        if index < 0 or index >= len(settings.managed_objects):
            return {"CANCELLED"}

        obj = settings.managed_objects[index].object
        settings.managed_objects.remove(index)
        settings.active_managed_object_index = max(0, index - 1)

        if obj:
            for group in settings.groups:
                for i in reversed(range(len(group.items))):
                    if group.items[i].control_type == "SHAPE_KEY" and group.items[i].object == obj:
                        group.items.remove(i)

        return {"FINISHED"}


class VI_CC_OT_add_selected_armature(bpy.types.Operator):
    bl_idname = "vi_cc.add_selected_armature"
    bl_label = "Add Selected Armature"
    bl_description = "Add the selected armature to the character creator"

    def execute(self, context):
        settings = get_settings(context)
        obj = context.object

        if not is_valid_armature(obj):
            self.report({"WARNING"}, "Selected object must be an armature.")
            return {"CANCELLED"}

        if is_armature_managed(settings, obj):
            self.report({"INFO"}, "Armature is already managed.")
            return {"CANCELLED"}

        item = settings.managed_armatures.add()
        item.object = obj
        settings.active_managed_armature_index = len(settings.managed_armatures) - 1

        return {"FINISHED"}


class VI_CC_OT_remove_managed_armature(bpy.types.Operator):
    bl_idname = "vi_cc.remove_managed_armature"
    bl_label = "Remove Managed Armature"
    bl_description = "Remove the active managed armature and its bone controls"

    def execute(self, context):
        settings = get_settings(context)
        index = settings.active_managed_armature_index

        if index < 0 or index >= len(settings.managed_armatures):
            return {"CANCELLED"}

        armature = settings.managed_armatures[index].object
        settings.managed_armatures.remove(index)
        settings.active_managed_armature_index = max(0, index - 1)

        if armature:
            for group in settings.groups:
                for i in reversed(range(len(group.items))):
                    if group.items[i].armature_object == armature:
                        group.items.remove(i)

        if settings.selected_armature == armature:
            settings.selected_armature = None
            settings.selected_bone_name = ""
            settings.selected_bone_a_name = ""
            settings.selected_bone_b_name = ""

        return {"FINISHED"}


# ------------------------------------------------------------
# Group Operators
# ------------------------------------------------------------

class VI_CC_OT_add_group(bpy.types.Operator):
    bl_idname = "vi_cc.add_group"
    bl_label = "Add Group"
    bl_description = "Create a new control group"

    def execute(self, context):
        settings = get_settings(context)
        group = settings.groups.add()
        group.name = "New Group"
        settings.active_group_index = len(settings.groups) - 1
        return {"FINISHED"}


class VI_CC_OT_remove_group(bpy.types.Operator):
    bl_idname = "vi_cc.remove_group"
    bl_label = "Remove Group"
    bl_description = "Remove the active control group"

    def execute(self, context):
        settings = get_settings(context)
        index = settings.active_group_index

        if index < 0 or index >= len(settings.groups):
            return {"CANCELLED"}

        settings.groups.remove(index)
        settings.active_group_index = max(0, index - 1)
        return {"FINISHED"}


class VI_CC_OT_move_group_up(bpy.types.Operator):
    bl_idname = "vi_cc.move_group_up"
    bl_label = "Move Group Up"

    def execute(self, context):
        settings = get_settings(context)
        index = settings.active_group_index

        if index <= 0:
            return {"CANCELLED"}

        settings.groups.move(index, index - 1)
        settings.active_group_index = index - 1
        return {"FINISHED"}


class VI_CC_OT_move_group_down(bpy.types.Operator):
    bl_idname = "vi_cc.move_group_down"
    bl_label = "Move Group Down"

    def execute(self, context):
        settings = get_settings(context)
        index = settings.active_group_index

        if index < 0 or index >= len(settings.groups) - 1:
            return {"CANCELLED"}

        settings.groups.move(index, index + 1)
        settings.active_group_index = index + 1
        return {"FINISHED"}


# ------------------------------------------------------------
# Group Item Operators
# ------------------------------------------------------------

class VI_CC_OT_add_shape_key_to_active_group(bpy.types.Operator):
    bl_idname = "vi_cc.add_shape_key_to_active_group"
    bl_label = "Add Shape Key"
    bl_description = "Add this shape key to the active group"

    object_name: bpy.props.StringProperty()
    shape_key_name: bpy.props.StringProperty()

    def execute(self, context):
        settings = get_settings(context)
        group = get_active_group(settings)

        if not group:
            self.report({"WARNING"}, "Create or select a group first.")
            return {"CANCELLED"}

        obj = bpy.data.objects.get(self.object_name)

        if not obj:
            self.report({"WARNING"}, "Object no longer exists.")
            return {"CANCELLED"}

        if not get_shape_key(obj, self.shape_key_name):
            self.report({"WARNING"}, "Shape key no longer exists.")
            return {"CANCELLED"}

        if group_contains_shape_key(group, obj, self.shape_key_name):
            self.report({"INFO"}, "Shape key is already in this group.")
            return {"CANCELLED"}

        item = group.items.add()
        item.control_type = "SHAPE_KEY"
        item.object = obj
        item.shape_key_name = self.shape_key_name
        item.display_name = self.shape_key_name
        group.active_item_index = len(group.items) - 1

        return {"FINISHED"}


class VI_CC_OT_select_bone_for_control(bpy.types.Operator):
    bl_idname = "vi_cc.select_bone_for_control"
    bl_label = "Select Bone"
    bl_description = "Select this bone for bone control creation"

    armature_name: bpy.props.StringProperty()
    bone_name: bpy.props.StringProperty()

    def execute(self, context):
        settings = get_settings(context)
        armature = bpy.data.objects.get(self.armature_name)

        if not bone_exists(armature, self.bone_name):
            return {"CANCELLED"}

        settings.selected_armature = armature
        settings.selected_bone_name = self.bone_name

        return {"FINISHED"}


class VI_CC_OT_set_bone_pair_a(bpy.types.Operator):
    bl_idname = "vi_cc.set_bone_pair_a"
    bl_label = "Set Bone A"
    bl_description = "Use this bone as Bone A for a bone-pair distance control"

    armature_name: bpy.props.StringProperty()
    bone_name: bpy.props.StringProperty()

    def execute(self, context):
        settings = get_settings(context)
        armature = bpy.data.objects.get(self.armature_name)

        if not bone_exists(armature, self.bone_name):
            return {"CANCELLED"}

        settings.selected_armature = armature
        settings.selected_bone_a_name = self.bone_name

        return {"FINISHED"}


class VI_CC_OT_set_bone_pair_b(bpy.types.Operator):
    bl_idname = "vi_cc.set_bone_pair_b"
    bl_label = "Set Bone B"
    bl_description = "Use this bone as Bone B for a bone-pair distance control"

    armature_name: bpy.props.StringProperty()
    bone_name: bpy.props.StringProperty()

    def execute(self, context):
        settings = get_settings(context)
        armature = bpy.data.objects.get(self.armature_name)

        if not bone_exists(armature, self.bone_name):
            return {"CANCELLED"}

        settings.selected_armature = armature
        settings.selected_bone_b_name = self.bone_name

        return {"FINISHED"}


class VI_CC_OT_add_selected_bone_scale_to_group(bpy.types.Operator):
    bl_idname = "vi_cc.add_selected_bone_scale_to_group"
    bl_label = "Add Selected Bone Scale"
    bl_description = "Create a single-bone scale slider from the selected bone"

    def execute(self, context):
        settings = get_settings(context)
        group = get_active_group(settings)
        armature = settings.selected_armature
        bone_name = settings.selected_bone_name

        if not group:
            self.report({"WARNING"}, "Create or select a group first.")
            return {"CANCELLED"}

        if not bone_exists(armature, bone_name):
            self.report({"WARNING"}, "Select a valid bone first.")
            return {"CANCELLED"}

        if group_contains_bone_scale(group, armature, bone_name):
            self.report({"INFO"}, "Bone scale control is already in this group.")
            return {"CANCELLED"}

        item = group.items.add()
        item.control_type = "BONE_SCALE"
        item.armature_object = armature
        item.bone_name = bone_name
        item.display_name = bone_name
        item.slider_value = 0.0
        capture_single_bone_baseline(item)
        group.active_item_index = len(group.items) - 1

        return {"FINISHED"}


class VI_CC_OT_add_selected_bone_pair_to_group(bpy.types.Operator):
    bl_idname = "vi_cc.add_selected_bone_pair_to_group"
    bl_label = "Add Selected Bone Pair"
    bl_description = "Create a bone-pair distance slider from Bone A and Bone B"

    def execute(self, context):
        settings = get_settings(context)
        group = get_active_group(settings)
        armature = settings.selected_armature
        bone_a_name = settings.selected_bone_a_name
        bone_b_name = settings.selected_bone_b_name

        if not group:
            self.report({"WARNING"}, "Create or select a group first.")
            return {"CANCELLED"}

        if not armature or not bone_a_name or not bone_b_name:
            self.report({"WARNING"}, "Set Bone A and Bone B first.")
            return {"CANCELLED"}

        if bone_a_name == bone_b_name:
            self.report({"WARNING"}, "Bone A and Bone B must be different bones.")
            return {"CANCELLED"}

        if not bone_exists(armature, bone_a_name) or not bone_exists(armature, bone_b_name):
            self.report({"WARNING"}, "One or both bones no longer exist.")
            return {"CANCELLED"}

        if group_contains_bone_pair(group, armature, bone_a_name, bone_b_name):
            self.report({"INFO"}, "Bone pair control is already in this group.")
            return {"CANCELLED"}

        item = group.items.add()
        item.control_type = "BONE_PAIR_DISTANCE"
        item.pair_apply_mode = "POSE_X_SCALE"
        item.min_distance_factor = -1.0
        item.max_distance_factor = 1.0
        item.armature_object = armature
        item.bone_a_name = bone_a_name
        item.bone_b_name = bone_b_name
        item.display_name = f"{bone_a_name} / {bone_b_name}"
        item.slider_value = 0.0
        capture_pair_bone_baseline(item)
        group.active_item_index = len(group.items) - 1

        return {"FINISHED"}


class VI_CC_OT_remove_group_item(bpy.types.Operator):
    bl_idname = "vi_cc.remove_group_item"
    bl_label = "Remove Control"
    bl_description = "Remove the active control from the active group"

    def execute(self, context):
        settings = get_settings(context)
        group = get_active_group(settings)

        if not group:
            return {"CANCELLED"}

        index = group.active_item_index

        if index < 0 or index >= len(group.items):
            return {"CANCELLED"}

        group.items.remove(index)
        group.active_item_index = max(0, index - 1)
        return {"FINISHED"}


class VI_CC_OT_move_group_item_up(bpy.types.Operator):
    bl_idname = "vi_cc.move_group_item_up"
    bl_label = "Move Control Up"

    def execute(self, context):
        settings = get_settings(context)
        group = get_active_group(settings)

        if not group:
            return {"CANCELLED"}

        index = group.active_item_index

        if index <= 0:
            return {"CANCELLED"}

        group.items.move(index, index - 1)
        group.active_item_index = index - 1
        return {"FINISHED"}


class VI_CC_OT_move_group_item_down(bpy.types.Operator):
    bl_idname = "vi_cc.move_group_item_down"
    bl_label = "Move Control Down"

    def execute(self, context):
        settings = get_settings(context)
        group = get_active_group(settings)

        if not group:
            return {"CANCELLED"}

        index = group.active_item_index

        if index < 0 or index >= len(group.items) - 1:
            return {"CANCELLED"}

        group.items.move(index, index + 1)
        group.active_item_index = index + 1
        return {"FINISHED"}


class VI_CC_OT_reset_all_controls(bpy.types.Operator):
    bl_idname = "vi_cc.reset_all_controls"
    bl_label = "Reset All"
    bl_description = "Reset all character creator controls"

    def execute(self, context):
        settings = get_settings(context)

        for group in settings.groups:
            for item in group.items:
                reset_group_item(item)

        return {"FINISHED"}


class VI_CC_OT_reset_group_controls(bpy.types.Operator):
    bl_idname = "vi_cc.reset_group_controls"
    bl_label = "Reset Group"
    bl_description = "Reset all controls in this group"

    group_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = get_settings(context)

        if self.group_index < 0 or self.group_index >= len(settings.groups):
            return {"CANCELLED"}

        for item in settings.groups[self.group_index].items:
            reset_group_item(item)

        return {"FINISHED"}


class VI_CC_OT_reset_single_control(bpy.types.Operator):
    bl_idname = "vi_cc.reset_single_control"
    bl_label = "Reset Control"
    bl_description = "Reset this control"

    group_index: bpy.props.IntProperty()
    item_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = get_settings(context)

        if self.group_index < 0 or self.group_index >= len(settings.groups):
            return {"CANCELLED"}

        group = settings.groups[self.group_index]

        if self.item_index < 0 or self.item_index >= len(group.items):
            return {"CANCELLED"}

        reset_group_item(group.items[self.item_index])
        return {"FINISHED"}


class VI_CC_OT_recapture_active_bone_baseline(bpy.types.Operator):
    bl_idname = "vi_cc.recapture_active_bone_baseline"
    bl_label = "Re-Baseline Active Bone Control"
    bl_description = "Use the current pose transform as the new zero point for the active bone control"

    def execute(self, context):
        settings = get_settings(context)
        group = get_active_group(settings)
        item = get_active_group_item(group)

        if not item or item.control_type not in {"BONE_SCALE", "BONE_PAIR_DISTANCE"}:
            self.report({"WARNING"}, "Active control is not a bone control.")
            return {"CANCELLED"}

        if not recapture_bone_control_baseline(item, reset_slider=True):
            self.report({"WARNING"}, "Could not recapture baseline.")
            return {"CANCELLED"}

        return {"FINISHED"}


class VI_CC_OT_apply_creator_pose_as_rest_pose(bpy.types.Operator):
    bl_idname = "vi_cc.apply_creator_pose_as_rest_pose"
    bl_label = "Apply Bone Controls as Armature Rest Pose"
    bl_description = "Permanently rewrite affected armature rest poses from the current creator bone controls"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        settings = get_settings(context)
        armatures = []

        # Apply all bone controls first so the pose matches the creator sliders.
        for group in settings.groups:
            for item in group.items:
                if item.control_type in {"BONE_SCALE", "BONE_PAIR_DISTANCE"}:
                    apply_group_item_control(item)
                    if item.armature_object and item.armature_object not in armatures:
                        armatures.append(item.armature_object)

        if not armatures:
            self.report({"WARNING"}, "No bone controls found.")
            return {"CANCELLED"}

        original_active = context.view_layer.objects.active
        original_selected = list(context.selected_objects)
        original_mode = original_active.mode if original_active else "OBJECT"

        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            for armature in armatures:
                if not is_valid_armature(armature):
                    continue

                select_only_active_object(context, armature)
                bpy.ops.object.mode_set(mode="POSE")
                bpy.ops.pose.armature_apply(selected=False)
                bpy.ops.object.mode_set(mode="OBJECT")

            # After applying as rest pose, Blender resets the pose. Store that new zero point.
            for group in settings.groups:
                for item in group.items:
                    if item.control_type in {"BONE_SCALE", "BONE_PAIR_DISTANCE"}:
                        recapture_bone_control_baseline(item, reset_slider=True)

        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")

            for obj in original_selected:
                if obj and obj.name in bpy.data.objects:
                    obj.select_set(True)

            if original_active and original_active.name in bpy.data.objects:
                context.view_layer.objects.active = original_active
                try:
                    if original_mode in {"POSE", "EDIT", "OBJECT"}:
                        bpy.ops.object.mode_set(mode=original_mode)
                except Exception:
                    pass

        self.report({"INFO"}, "Applied creator bone controls as armature rest pose.")
        return {"FINISHED"}


# ------------------------------------------------------------
# UI Lists
# ------------------------------------------------------------

class VI_CC_UL_managed_objects(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        obj = item.object

        if obj:
            layout.label(text=obj.name, icon="MESH_DATA")
        else:
            layout.label(text="Missing Object", icon="ERROR")


class VI_CC_UL_managed_armatures(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        obj = item.object

        if obj:
            layout.label(text=obj.name, icon="ARMATURE_DATA")
        else:
            layout.label(text="Missing Armature", icon="ERROR")


class VI_CC_UL_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name", text="", emboss=False)


class VI_CC_UL_group_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon_name = "SHAPEKEY_DATA"

        if item.control_type == "BONE_SCALE":
            icon_name = "BONE_DATA"
        elif item.control_type == "BONE_PAIR_DISTANCE":
            icon_name = "CONSTRAINT_BONE"

        layout.label(text=item_display_label(item), icon=icon_name)


# ------------------------------------------------------------
# Panels
# ------------------------------------------------------------

class VI_CC_PT_creator(bpy.types.Panel):
    bl_label = "Character Creator"
    bl_idname = "VI_CC_PT_creator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Character Creator"

    def draw(self, context):
        layout = self.layout
        settings = get_settings(context)

        if not settings.groups:
            layout.label(text="No groups created yet.")
            layout.label(text="Use Character Creator Setup.")
            return

        row = layout.row()
        row.operator("vi_cc.reset_all_controls", icon="LOOP_BACK")

        for group_index, group in enumerate(settings.groups):
            box = layout.box()
            header = box.row(align=True)
            header.label(text=group.name, icon="GROUP")

            op = header.operator("vi_cc.reset_group_controls", text="", icon="LOOP_BACK")
            op.group_index = group_index

            if not group.items:
                box.label(text="Empty group.")
                continue

            for item_index, item in enumerate(group.items):
                label = item_display_label(item)
                row = box.row(align=True)

                if item.control_type == "SHAPE_KEY":
                    key = get_shape_key(item.object, item.shape_key_name)

                    if not key:
                        row.label(text=f"Missing: {item.shape_key_name}", icon="ERROR")
                        continue

                    row.prop(key, "value", text=label, slider=True)

                elif item.control_type == "BONE_SCALE":
                    if not get_pose_bone(item.armature_object, item.bone_name):
                        row.label(text=f"Missing Bone: {item.bone_name}", icon="ERROR")
                        continue

                    row.prop(item, "slider_value", text=label, slider=True)

                elif item.control_type == "BONE_PAIR_DISTANCE":
                    if not get_pose_bone(item.armature_object, item.bone_a_name) or not get_pose_bone(item.armature_object, item.bone_b_name):
                        row.label(text=f"Missing Pair: {item.bone_a_name} / {item.bone_b_name}", icon="ERROR")
                        continue

                    row.prop(item, "slider_value", text=label, slider=True)

                op = row.operator("vi_cc.reset_single_control", text="", icon="X")
                op.group_index = group_index
                op.item_index = item_index


class VI_CC_PT_setup(bpy.types.Panel):
    bl_label = "Character Creator Setup"
    bl_idname = "VI_CC_PT_setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Character Creator"

    def draw(self, context):
        layout = self.layout
        settings = get_settings(context)

        # Managed Meshes
        box = layout.box()
        box.label(text="Managed Meshes", icon="OUTLINER_OB_MESH")

        box.template_list(
            "VI_CC_UL_managed_objects",
            "",
            settings,
            "managed_objects",
            settings,
            "active_managed_object_index",
            rows=3
        )

        row = box.row(align=True)
        row.operator("vi_cc.add_selected_object", icon="ADD")
        row.operator("vi_cc.remove_managed_object", icon="REMOVE")

        # Managed Armatures
        box = layout.box()
        box.label(text="Managed Armatures", icon="ARMATURE_DATA")

        box.template_list(
            "VI_CC_UL_managed_armatures",
            "",
            settings,
            "managed_armatures",
            settings,
            "active_managed_armature_index",
            rows=3
        )

        row = box.row(align=True)
        row.operator("vi_cc.add_selected_armature", icon="ADD")
        row.operator("vi_cc.remove_managed_armature", icon="REMOVE")

        # Groups
        box = layout.box()
        box.label(text="Groups", icon="GROUP")

        box.template_list(
            "VI_CC_UL_groups",
            "",
            settings,
            "groups",
            settings,
            "active_group_index",
            rows=4
        )

        row = box.row(align=True)
        row.operator("vi_cc.add_group", icon="ADD")
        row.operator("vi_cc.remove_group", icon="REMOVE")

        row = box.row(align=True)
        row.operator("vi_cc.move_group_up", text="Up", icon="TRIA_UP")
        row.operator("vi_cc.move_group_down", text="Down", icon="TRIA_DOWN")

        group = get_active_group(settings)

        if group:
            layout.label(text=f"Adding to: {group.name}", icon="RIGHTARROW")
        else:
            layout.label(text="No active group selected.", icon="ERROR")

        # Shape Keys
        box = layout.box()
        box.label(text="Discovered Shape Keys", icon="SHAPEKEY_DATA")
        box.prop(settings, "search_filter", text="", icon="VIEWZOOM")

        discovered_any = False

        for obj, key in iter_discovered_shape_keys(settings):
            discovered_any = True
            row = box.row(align=True)

            already_added = active_group_contains_shape_key(settings, obj, key.name)
            icon = "CHECKMARK" if already_added else "ADD"

            sub = row.row()
            sub.enabled = not already_added and bool(group)

            op = sub.operator("vi_cc.add_shape_key_to_active_group", text="", icon=icon)
            op.object_name = obj.name
            op.shape_key_name = key.name

            row.label(text=f"{obj.name} : {key.name}")

        if not discovered_any:
            box.label(text="No shape keys found.")

        # Bones
        box = layout.box()
        box.label(text="Discovered Bones", icon="BONE_DATA")
        box.prop(settings, "bone_search_filter", text="", icon="VIEWZOOM")

        if settings.selected_armature:
            box.label(text=f"Active Armature: {settings.selected_armature.name}")
        else:
            box.label(text="No bone armature selected.")

        box.label(text=f"Bone Scale: {settings.selected_bone_name or 'None'}")
        row = box.row(align=True)
        row.label(text=f"Pair A: {settings.selected_bone_a_name or 'None'}")
        row.label(text=f"Pair B: {settings.selected_bone_b_name or 'None'}")

        row = box.row(align=True)
        row.enabled = bool(group)
        row.operator("vi_cc.add_selected_bone_scale_to_group", icon="ADD")
        row.operator("vi_cc.add_selected_bone_pair_to_group", icon="ADD")

        discovered_any = False

        for armature, pbone in iter_discovered_bones(settings):
            discovered_any = True
            row = box.row(align=True)

            scale_selected = settings.selected_armature == armature and settings.selected_bone_name == pbone.name
            pair_a_selected = settings.selected_armature == armature and settings.selected_bone_a_name == pbone.name
            pair_b_selected = settings.selected_armature == armature and settings.selected_bone_b_name == pbone.name

            op = row.operator("vi_cc.select_bone_for_control", text="S", icon="RADIOBUT_ON" if scale_selected else "RADIOBUT_OFF")
            op.armature_name = armature.name
            op.bone_name = pbone.name

            op = row.operator("vi_cc.set_bone_pair_a", text="A", icon="RADIOBUT_ON" if pair_a_selected else "RADIOBUT_OFF")
            op.armature_name = armature.name
            op.bone_name = pbone.name

            op = row.operator("vi_cc.set_bone_pair_b", text="B", icon="RADIOBUT_ON" if pair_b_selected else "RADIOBUT_OFF")
            op.armature_name = armature.name
            op.bone_name = pbone.name

            row.label(text=f"{armature.name} : {pbone.name}")

        if not discovered_any:
            box.label(text="No managed armature bones found.")

        # Active Group Contents
        box = layout.box()
        box.label(text="Active Group Contents", icon="PRESET")

        if group:
            box.template_list(
                "VI_CC_UL_group_items",
                "",
                group,
                "items",
                group,
                "active_item_index",
                rows=5
            )

            active_item = get_active_group_item(group)

            if active_item:
                box.prop(active_item, "display_name")
                box.label(text=item_source_label(active_item))

                if active_item.control_type == "BONE_SCALE":
                    box.prop(active_item, "scale_mode")
                    row = box.row(align=True)
                    row.prop(active_item, "min_scale")
                    row.prop(active_item, "max_scale")
                    box.operator("vi_cc.recapture_active_bone_baseline", icon="EMPTY_AXIS")

                elif active_item.control_type == "BONE_PAIR_DISTANCE":
                    box.prop(active_item, "pair_apply_mode")
                    box.label(text="Range is centered: 0 = neutral, -1/+1 = default min/max.")
                    row = box.row(align=True)
                    row.prop(active_item, "min_distance_factor")
                    row.prop(active_item, "max_distance_factor")
                    box.operator("vi_cc.recapture_active_bone_baseline", icon="EMPTY_AXIS")

            row = box.row(align=True)
            row.operator("vi_cc.remove_group_item", icon="REMOVE")
            row.operator("vi_cc.move_group_item_up", text="Up", icon="TRIA_UP")
            row.operator("vi_cc.move_group_item_down", text="Down", icon="TRIA_DOWN")
        else:
            box.label(text="Create or select a group first.")

        # Dangerous operations.
        box = layout.box()
        box.label(text="Bake / Dangerous", icon="ERROR")
        box.label(text="Rewrites affected armature rest poses.")
        box.label(text="Existing animation may deform differently.")
        box.operator("vi_cc.apply_creator_pose_as_rest_pose", icon="ARMATURE_DATA")


# ------------------------------------------------------------
# Registration
# ------------------------------------------------------------

classes = (
    VI_CC_ManagedObject,
    VI_CC_ManagedArmature,
    VI_CC_GroupItem,
    VI_CC_Group,
    VI_CC_Settings,

    VI_CC_OT_add_selected_object,
    VI_CC_OT_remove_managed_object,
    VI_CC_OT_add_selected_armature,
    VI_CC_OT_remove_managed_armature,

    VI_CC_OT_add_group,
    VI_CC_OT_remove_group,
    VI_CC_OT_move_group_up,
    VI_CC_OT_move_group_down,

    VI_CC_OT_add_shape_key_to_active_group,
    VI_CC_OT_select_bone_for_control,
    VI_CC_OT_set_bone_pair_a,
    VI_CC_OT_set_bone_pair_b,
    VI_CC_OT_add_selected_bone_scale_to_group,
    VI_CC_OT_add_selected_bone_pair_to_group,
    VI_CC_OT_remove_group_item,
    VI_CC_OT_move_group_item_up,
    VI_CC_OT_move_group_item_down,

    VI_CC_OT_reset_all_controls,
    VI_CC_OT_reset_group_controls,
    VI_CC_OT_reset_single_control,
    VI_CC_OT_recapture_active_bone_baseline,
    VI_CC_OT_apply_creator_pose_as_rest_pose,

    VI_CC_UL_managed_objects,
    VI_CC_UL_managed_armatures,
    VI_CC_UL_groups,
    VI_CC_UL_group_items,

    VI_CC_PT_creator,
    VI_CC_PT_setup,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.vi_character_creator = bpy.props.PointerProperty(
        type=VI_CC_Settings
    )


def unregister():
    if hasattr(bpy.types.Scene, "vi_character_creator"):
        del bpy.types.Scene.vi_character_creator

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
