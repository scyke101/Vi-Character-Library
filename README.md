# Vi's Character Library

Vi's Character Library is a Blender add-on for creating, organizing, and reusing customizable characters.

Characters are built using a unified slider interface that supports shape keys and optional bone-based controls. Controls can be organized into custom groups, saved as presets, and reused across projects through the built-in Character Library system.

The goal is simple: create a character once, save it, and use it wherever you need it.

---

# Features

## Character Creation

Build customizable characters using a simple slider-based workflow.

Character Library supports:

* Shape key controls
* Bone-based controls
* Custom control groups
* Character presets
* Shared character libraries

Controls can be mixed and matched to create anything from subtle facial adjustments to broad body-shape variations.

---

## Shape Key Controls

Create sliders for any shape key and expose them directly in the Character Library interface.

Examples:

* Facial features
* Musculature
* Creature morphs
* Stylized proportions
* Clothing variations

Shape keys can be organized into custom groups to keep large character setups manageable.

---

## Bone-Based Controls

Character Library includes support for bone-based customization controls.

These can be used for proportional adjustments and other rig-driven character modifications alongside traditional shape keys.

---

## Control Groups

Organize controls into custom categories.

Example:

```text
Face
Body
Arms
Legs
Hair
Equipment
Creature Features
```

Groups make it easier to work with large character setups containing many sliders.

---

## Character Presets

Save the current state of a character and restore it later.

Presets store:

* Shape key values
* Bone control values
* Character customization settings

Use presets to quickly switch between different character variants.

Examples:

```text
Bandit
Merchant
Knight
Noble
Guard
```

---

## Rest Pose Baking

Customized characters can be converted into a new armature rest pose.

This allows a modified character to become the new baseline for animation, rigging, and future customization.

---

## Character Library

Save characters for reuse across Blender projects.

Character Library stores:

### Templates

Reusable character assets including:

* Meshes
* Armatures
* Shape keys
* Rig controls
* Supporting data

### Presets

Character-specific customization values.

This allows many different characters to share the same underlying template without duplicating assets.

---

# Typical Workflow

## Create a Character

1. Add shape key and optional bone-based controls.
2. Organize controls into groups.
3. Adjust sliders to create a character.
4. Save the result as a preset.

---

## Save to the Character Library

1. Select the collection containing the complete character setup.
2. Choose a library folder.
3. Enter a character name.
4. Enter a template name.
5. Click **Export Character to Library**.

Character Library automatically creates:

```text
Templates/YourTemplate.blend
Presets/YourCharacter.json
```

---

## Reuse a Character

Open another Blender project and choose:

```text
Load Template + Preset
```

Character Library will:

1. Load the associated template.
2. Create a new character instance.
3. Apply the saved customization settings.

---

# Library Structure

```text
CharacterLibrary/
│
├── Templates/
│   ├── HumanMale.blend
│   ├── HumanFemale.blend
│   └── Monster.blend
│
└── Presets/
    ├── Bandit_A.json
    ├── Merchant_A.json
    ├── Noble_A.json
    └── Guard_A.json
```

A single template can support any number of character presets.

---

# Installation

## Blender Version

Targeted for:

```text
Blender 4.4.3+
```

## Install

1. Download the ZIP file.
2. Open Blender.
3. Go to **Edit → Preferences → Add-ons**.
4. Click **Install from Disk**.
5. Select the ZIP file.
6. Enable **Vi's Character Library**.

---

# Use Cases

* RPG NPC libraries
* Character customization systems
* Creature creation
* Modular character workflows
* Shared asset libraries
* Cross-project character reuse
* Rapid character iteration

---

# Notes

Character Library is designed around non-destructive character creation.

Templates store reusable assets.

Presets store customization data.

Characters can be edited, resaved, and expanded at any point in the workflow.

---

# License

See the provided file.
