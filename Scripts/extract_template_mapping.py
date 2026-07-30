import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
# The in-game currency. Every template price and every shop price is denominated in it, so
# reading a price means picking this template out of the price's item list. Repeated here
# rather than imported: this script is standalone and does not depend on CH_Editor.
CREDITS_ID = "cb567810-cc82-424f-893f-299c704ffb12"
LOG_TEMPLATE_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)TemplateId=([0-9a-fA-F-]{36})",
    flags=re.IGNORECASE,
)
NAME_FIELD_HINTS = {
    "name",
    "displayname",
    "display_name",
    "title",
    "label",
    "itemname",
    "localizationkey",
    "localization_key",
    "key",
}


def bundles_dir_for_game(game_path: Path) -> Path:
    return (
        game_path
        / "CargoHunters_Data"
        / "StreamingAssets"
        / "aa"
        / "StandaloneWindows64"
    )


def is_guid(value: str) -> bool:
    return bool(GUID_RE.match(value.strip()))


def normalize_guid(value: str) -> str:
    return value.strip().lower()


def collect_save_template_usage(save_path: Path) -> dict[str, Any]:
    with save_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    usage = Counter()
    sections = defaultdict(Counter)

    def harvest_items(items: list[dict], section: str) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            tid = item.get("TemplateId")
            if not isinstance(tid, str) or not is_guid(tid):
                continue
            tid = normalize_guid(tid)
            usage[tid] += 1
            sections[tid][section] += 1

    equipment_items = data.get("EquipmentDto", {}).get("Items", [])
    if isinstance(equipment_items, list):
        harvest_items(equipment_items, "EquipmentDto.Items")

    shelter_items = data.get("ShelterItemDto", {}).get("Container", {}).get("Items", [])
    if isinstance(shelter_items, list):
        harvest_items(shelter_items, "ShelterItemDto.Container.Items")

    inventory_items = data.get("InventoryDto", {}).get("ItemsContainerDto", {}).get("Items", [])
    if isinstance(inventory_items, list):
        harvest_items(inventory_items, "InventoryDto.ItemsContainerDto.Items")

    return {
        "template_usage_count": dict(usage),
        "template_usage_sections": {k: dict(v) for k, v in sections.items()},
    }


def collect_log_template_hints(game_path: Path) -> dict[str, Any]:
    hints: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    files_scanned = []

    for log_file in sorted(game_path.glob("game*.log")):
        files_scanned.append(str(log_file))
        try:
            text = log_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for field_name, guid in LOG_TEMPLATE_RE.findall(text):
            hints[normalize_guid(guid)][field_name] += 1

    return {
        "log_files_scanned": files_scanned,
        "template_log_hints": {k: dict(v) for k, v in hints.items()},
    }


def derive_pretty_name_from_bundle_slug(slug: str) -> str:
    text = slug.replace("_", " ").strip()
    if not text:
        return slug
    return " ".join(part.capitalize() for part in text.split())


def collect_bundle_slug_hints(game_path: Path) -> dict[str, Any]:
    bundles_dir = bundles_dir_for_game(game_path)
    result = []

    if not bundles_dir.exists():
        return {"bundles_dir": str(bundles_dir), "bundle_slug_hints": result}

    for bundle in sorted(bundles_dir.glob("itemsgroup_assets_*.bundle")):
        name = bundle.name
        stem = name.removesuffix(".bundle")
        stem = stem.removeprefix("itemsgroup_assets_")
        stem = re.sub(r"_[0-9a-f]{32}$", "", stem)
        pretty = derive_pretty_name_from_bundle_slug(stem)
        result.append(
            {
                "bundle": name,
                "slug": stem,
                "display_name_guess": pretty,
            }
        )

    return {"bundles_dir": str(bundles_dir), "bundle_slug_hints": result}


def _extract_primary_alias(entry: dict[str, Any]) -> str | None:
    components = entry.get("_components")
    if not isinstance(components, list):
        return None
    for component in components:
        if not isinstance(component, dict):
            continue
        alias = component.get("Name")
        if isinstance(alias, str) and alias.strip():
            return alias.strip()
    return None


def _extract_items_table_entry_ref(entry: dict[str, Any]) -> int | None:
    components = entry.get("_components")
    if not isinstance(components, list):
        return None
    for component in components:
        if not isinstance(component, dict):
            continue
        data = component.get("_data")
        if not isinstance(data, dict):
            continue
        localized_name = data.get("LocalizedName")
        if not isinstance(localized_name, dict):
            continue
        if localized_name.get("TableReference") != "Items":
            continue
        entry_ref = localized_name.get("TableEntryReference")
        if isinstance(entry_ref, int):
            return entry_ref
    return None


def _extract_category_ids(entry: dict[str, Any]) -> tuple[int | None, int | None]:
    category_id: int | None = None
    sub_category_id: int | None = None

    def walk(obj: Any) -> None:
        nonlocal category_id, sub_category_id
        if category_id is not None and sub_category_id is not None:
            return
        if isinstance(obj, dict):
            raw_category = obj.get("CategoryId")
            raw_sub_category = obj.get("SubCategoryId")
            if category_id is None and isinstance(raw_category, int):
                category_id = raw_category
            if sub_category_id is None and isinstance(raw_sub_category, int):
                sub_category_id = raw_sub_category
            for value in obj.values():
                walk(value)
            return
        if isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(entry)
    return category_id, sub_category_id


def _extract_grid_size(entry: dict[str, Any]) -> tuple[int | None, int | None]:
    width: int | None = None
    height: int | None = None

    def walk(obj: Any) -> None:
        nonlocal width, height
        if width is not None and height is not None:
            return
        if isinstance(obj, dict):
            size = obj.get("Size")
            if isinstance(size, dict):
                w = size.get("Width")
                h = size.get("Height")
                if width is None and isinstance(w, int):
                    width = w
                if height is None and isinstance(h, int):
                    height = h
            for value in obj.values():
                walk(value)
            return
        if isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(entry)
    return width, height


def _extract_max_size(entry: dict[str, Any]) -> tuple[int | None, int | None, bool]:
    """(max_width, max_height, is_resizable) from the base component.

    A weapon carries a `Size` **and** a `MaxSize`, plus `IsResizable`: how far it can grow as
    attachments are added. Recorded for reference only - the editor does **not** place items
    by it. Measured against a real save, reserving `MaxSize` invents 80 overlapping cells
    inside five rifle cases, because a weapon there is stored at the 4x1 it really takes while
    its maximum is 6x3. See `tests/test_placement_real.py`.

    The base component is the one carrying `LocalizedName`; other components have a `Size`
    of their own that means something else entirely.
    """
    for component in entry.get("_components") or []:
        if not isinstance(component, dict):
            continue
        data = component.get("_data")
        if not isinstance(data, dict) or "LocalizedName" not in data:
            continue
        max_size = data.get("MaxSize")
        width = height = None
        if isinstance(max_size, dict):
            raw_w, raw_h = max_size.get("Width"), max_size.get("Height")
            width = raw_w if isinstance(raw_w, int) else None
            height = raw_h if isinstance(raw_h, int) else None
        return width, height, bool(data.get("IsResizable"))
    return None, None, False


def _extract_resize(entry: dict[str, Any]) -> dict[str, int] | None:
    """How much this part enlarges the item it is fitted to, or None when it does not.

    **This is the field that explains a grown weapon**, and it took a mailbox to find: a
    `Resize` component, on its own, carried by 132 templates. A Gaston 17 suppressor says
    `{"Width": 1}` and makes its host one cell wider; a drum magazine says `{"Height": 1}`.
    The six values in the bundle are (1,0), (2,0), (3,0), (0,1), (0,2) and one (6,2).

    Read for the same reason `MaxSize` is: to know how much room to keep free for an item that
    will grow. It is **not** the whole answer - summing it over every fitted part predicts the
    stored size of 139 of a real save's 162 grown items exactly and overshoots the rest, so it
    is an upper bound on the growth rather than the growth itself. Missing means no growth,
    which is the serializer's usual omission.
    """
    for component in entry.get("_components") or []:
        if not isinstance(component, dict):
            continue
        data = component.get("_data")
        if not isinstance(data, dict):
            continue
        resize = data.get("Resize")
        if not isinstance(resize, dict):
            continue
        width, height = resize.get("Width"), resize.get("Height")
        return {
            "width": width if isinstance(width, int) else 0,
            "height": height if isinstance(height, int) else 0,
        }
    return None


def _extract_container(entry: dict[str, Any]) -> dict[str, Any] | None:
    """The storage an item provides, or None if it holds nothing.

    Identified by the shape of each component's `_data` rather than by its `$t` id - those
    are numeric hashes and a game update can renumber them. Three kinds exist, matching the
    game's own component classes:

      simple - one free grid of Width x Height; a warehouse tab is 8x30
      split  - a list of sub-rectangles, each a Size at an optional Position. A cell outside
               every rectangle does not exist, which is the dead area in a rig or vest.
      slots  - named compartments taking one item each (weapon attachment points)

    The base component also carries a `Size` - the item's own footprint - so it is told apart
    by its `LocalizedName`. Deliberately not by `AllowExpand`: that field is omitted when it
    is False, the same way a zero `Position` or an empty equipment slot vanishes.
    """
    for component in entry.get("_components") or []:
        if not isinstance(component, dict):
            continue
        data = component.get("_data")

        # SplittedContainerComponent keeps a list of regions instead of a single size.
        if isinstance(data, list):
            regions = []
            for region in data:
                if not isinstance(region, dict) or not isinstance(region.get("Size"), dict):
                    continue
                w = region["Size"].get("Width")
                h = region["Size"].get("Height")
                if not isinstance(w, int) or not isinstance(h, int):
                    continue
                position = region.get("Position")
                position = position if isinstance(position, dict) else {}
                regions.append({
                    "i": int(position.get("I") or 0),
                    "j": int(position.get("J") or 0),
                    "width": w,
                    "height": h,
                })
            if regions:
                return {"kind": "split", "regions": regions}
            continue

        if not isinstance(data, dict) or "LocalizedName" in data:
            continue

        slots = data.get("ContainerSlots")
        if isinstance(slots, list) and slots:
            return {"kind": "slots", "slot_count": len(slots)}

        size = data.get("Size")
        if isinstance(size, dict):
            w, h = size.get("Width"), size.get("Height")
            if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
                return {
                    "kind": "simple",
                    "width": w,
                    "height": h,
                    "allow_expand": bool(data.get("AllowExpand")),
                }
    return None


def _extract_max_durability(entry: dict[str, Any]) -> float | None:
    """Ceiling for `DurabilityComponent_durability`, e.g. 5 charges for a repair kit.

    The save omits the value entirely while an item is untouched, so percentages are
    only meaningful with this number from the game data.
    """
    found: float | None = None

    def walk(obj: Any) -> None:
        nonlocal found
        if found is not None:
            return
        if isinstance(obj, dict):
            value = obj.get("MaxDurability")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                found = float(value)
                return
            for nested in obj.values():
                walk(nested)
            return
        if isinstance(obj, list):
            for nested in obj:
                walk(nested)

    walk(entry)
    return found


def _extract_has_wear_condition(entry: dict[str, Any]) -> bool:
    """Whether the template uses the 0-4 `Condition_d` wear scale.

    The other condition field, `DurabilityComponent_durability`, is covered by
    `max_durability` above - a template carries one mechanism or the other, never both, and
    a weapon uses this one. Without this flag there is no way to tell a rifle (wears out,
    ceiling 4) from a magazine (no condition at all), because both come out with no
    `max_durability`.

    Identified by the fields the component carries, not by its numeric `$t`, which a game
    update renumbers. 150 templates at the time of writing.
    """
    found = False

    def walk(obj: Any) -> None:
        nonlocal found
        if found:
            return
        if isinstance(obj, dict):
            if "MinMaxConditionToRepair" in obj or "DecreaseByType" in obj:
                found = True
                return
            for nested in obj.values():
                walk(nested)
            return
        if isinstance(obj, list):
            for nested in obj:
                walk(nested)

    walk(entry)
    return found


def _extract_stack_capacity(entry: dict[str, Any]) -> int | None:
    """How many units fit into one stack, e.g. 60 rounds or 10000 credits.

    Only stackable templates carry it, so its presence doubles as the stackable flag.
    """
    found: int | None = None

    def walk(obj: Any) -> None:
        nonlocal found
        if found is not None:
            return
        if isinstance(obj, dict):
            value = obj.get("StackCapacity")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                found = int(value)
                return
            for nested in obj.values():
                walk(nested)
            return
        if isinstance(obj, list):
            for nested in obj:
                walk(nested)

    walk(entry)
    return found


def _extract_price(entry: dict[str, Any]) -> int | None:
    """The template's own value in credits, as the game's base price.

    Stored the way every shop price is - a list of item stacks rather than a number - so the
    currency is read out of it rather than assumed: `{"Price": {"Items": [{"ItemTemplateId":
    "<credits>", "Count": 4800}]}}`. 1131 of 1595 templates carry one; the rest genuinely
    have no price, which is not the same as a price of zero.

    Only a price denominated in credits is returned. Nothing else was seen in the data, and
    a price in some other item would be a quantity of that item, not a number of credits.
    """
    found: int | None = None

    def walk(obj: Any) -> None:
        nonlocal found
        if found is not None:
            return
        if isinstance(obj, dict):
            price = obj.get("Price")
            if isinstance(price, dict) and isinstance(price.get("Items"), list):
                for part in price["Items"]:
                    if not isinstance(part, dict):
                        continue
                    if normalize_guid(str(part.get("ItemTemplateId") or "")) != CREDITS_ID:
                        continue
                    count = part.get("Count")
                    if isinstance(count, (int, float)) and not isinstance(count, bool):
                        found = int(count)
                        return
            for nested in obj.values():
                walk(nested)
            return
        if isinstance(obj, list):
            for nested in obj:
                walk(nested)

    walk(entry)
    return found


def _extract_mass(entry: dict[str, Any]) -> float | None:
    """How heavy one unit is. Sits in the same component as `Size` and `LocalizedName`.

    1162 of 1595 templates carry it. A missing value stays missing rather than becoming 0.0:
    the game omits the field on templates that have no weight at all, and a blueprint
    weighing zero and a blueprint with no weight recorded are different statements.
    """
    found: float | None = None

    def walk(obj: Any) -> None:
        nonlocal found
        if found is not None:
            return
        if isinstance(obj, dict):
            value = obj.get("Mass")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                found = float(value)
                return
            for nested in obj.values():
                walk(nested)
            return
        if isinstance(obj, list):
            for nested in obj:
                walk(nested)

    walk(entry)
    return found


def _clean_category_label(label: str) -> str:
    """A category label with runtime placeholders removed.

    One of the 89 labels is a template the game fills in per item: `Sight x{magnification}`,
    since each optic has its own. We cannot know the value, so the placeholder goes - and with
    it the multiplier letter left dangling in front of it, which would otherwise read
    "Sight x". A trailing one-character token after a removed placeholder is always that kind
    of leftover.
    """
    cleaned = _LOCALIZED_PLACEHOLDER.sub("", str(label or "")).strip()
    parts = cleaned.split()
    # A lone letter or punctuation mark at the end is leftover; a lone digit is not, so
    # something like "Tier 2" keeps its 2.
    while parts and len(parts[-1]) == 1 and not parts[-1].isdigit():
        parts.pop()
    return " ".join(parts).strip(" :-–—,;.")


def _extract_caliber(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Which cartridge a weapon fires, or which one a round is - as `{"type", "role"}`.

    The same `CaliberType` field appears on two different components and means the same thing
    from opposite ends, so the role is decided by what travels with it: firing behaviour
    (`FireModes`, `ShotDuration`) makes it a weapon, ballistics (`DamageData`,
    `MuzzleVelocity`) make it a cartridge. Told apart by fields rather than by the numeric
    `$t`, which a game update renumbers.

    Measured across the bundle: 36 weapons and 95 cartridges over 15 calibers, and **no weapon
    is left without a matching cartridge** - which is what makes the pairing worth showing.
    """
    for component in entry.get("_components") or []:
        data = component.get("_data") if isinstance(component, dict) else None
        if not isinstance(data, dict) or "CaliberType" not in data:
            continue
        caliber = data.get("CaliberType")
        if not isinstance(caliber, int) or isinstance(caliber, bool):
            continue
        if "FireModes" in data or "ShotDuration" in data:
            return {"type": caliber, "role": "weapon"}
        if "DamageData" in data or "MuzzleVelocity" in data:
            return {"type": caliber, "role": "cartridge"}
    return None


def _filter_template_ids(node: Any, depth: int = 0) -> tuple[set[str], set[int], set[int]]:
    """Every template a slot filter permits, plus the subcategory ids and tag ids it names.

    Returns `(template_ids, subcategory_ids, tag_ids)`. The tags come back as numbers rather
    than a flag because the items carry their own `Tags`, so membership answers the filter
    without needing a table of tag names - see `_resolve_slot_filters`.

    **`_filterPolicy` is deliberately ignored.** It looks like an allow/deny switch and is not:
    the barrel slot of an `ETA 5 receiver` carries policy 0 with a one-element list holding
    exactly its own `DefaultItemTemplateId`, and a deny-list forbidding the only part meant to
    go there is nonsense. Across the bundle the slot's own default sits *inside* its own list
    in 147 of 149 cases regardless of policy. So both values carry permitted templates, and
    what the flag really distinguishes - most likely how a composite filter combines its
    children - is unresolved and not needed to answer "what fits here".

    """
    templates: set[str] = set()
    subcategories: set[int] = set()
    tags: set[int] = set()
    if not isinstance(node, dict) or depth > 6:
        return templates, subcategories, tags

    for value in node.get("_templateIds") or []:
        if isinstance(value, str) and value.strip():
            templates.add(normalize_guid(value))
    for value in node.get("_itemSubCategoryIds") or []:
        if isinstance(value, int) and not isinstance(value, bool):
            subcategories.add(value)
    for value in node.get("_tagList") or []:
        if isinstance(value, int) and not isinstance(value, bool):
            tags.add(value)

    for child in node.get("_filtersList") or []:
        sub_t, sub_s, sub_tags = _filter_template_ids(child, depth + 1)
        templates |= sub_t
        subcategories |= sub_s
        tags |= sub_tags
    return templates, subcategories, tags


def _extract_tags(entry: dict[str, Any]) -> list[int] | None:
    """The item's own tag numbers, carried by 1427 of the 1595 templates.

    These are what makes a tag-filtered attachment slot answerable. The bundle ships no table
    of tag *names* - checked, no asset has "tag" in its name - but names are not needed:
    a slot filtering on tag 36 wants the items whose own `Tags` contain 36. Membership is the
    whole question, so `_resolve_slot_filters` builds the index and expands the slots.
    """
    for component in entry.get("_components") or []:
        data = component.get("_data") if isinstance(component, dict) else None
        if isinstance(data, dict) and isinstance(data.get("Tags"), list):
            tags = [v for v in data["Tags"] if isinstance(v, int) and not isinstance(v, bool)]
            return tags or None
    return None


def _resolve_slot_filters(template_meta: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Turns tag and subcategory filters into concrete template lists, in place.

    A second pass, because a slot can only be answered once every template's own tags and
    subcategory are known. Both kinds of filter turn out to describe **small** sets - the three
    tags slots use hold 11, 4 and 9 items, all of them sights, and the two subcategories hold 4
    and 6 - so expanding them beats showing "any Sight" and leaving the reader to go looking.

    Returns counts for the report, and leaves `allows_tags` / `allows_subcategories` in place so
    a later reader can see where an entry came from.
    """
    by_tag: dict[int, list[str]] = defaultdict(list)
    by_subcategory: dict[int, list[str]] = defaultdict(list)
    for template_id, meta in template_meta.items():
        for tag in meta.get("tags") or []:
            by_tag[tag].append(template_id)
        subcategory = meta.get("subcategory_id")
        if isinstance(subcategory, int):
            by_subcategory[subcategory].append(template_id)

    stats = Counter()
    for meta in template_meta.values():
        for slot in meta.get("mod_slots") or []:
            gained: set[str] = set()
            for tag in slot.get("allows_tags") or []:
                gained |= set(by_tag.get(tag, ()))
            for subcategory in slot.get("allows_subcategories") or []:
                gained |= set(by_subcategory.get(subcategory, ()))
            if not gained:
                continue
            before = set(slot.get("allows") or [])
            slot["allows"] = sorted(before | gained)
            stats["slots_expanded"] += 1
            stats["templates_added"] += len(gained - before)
    stats["tags_indexed"] = len(by_tag)
    return dict(stats)


_EMPTY_GUID = "00000000-0000-0000-0000-000000000000"


def _extract_mod_slots(
    entry: dict[str, Any],
    items_table: dict[int, str] | None = None,
) -> list[dict[str, Any]] | None:
    """Every slot an item offers, and what each one accepts.

    **Two different components mean the same thing**, and both are read here so the GUI has one
    field to work with:

    - `ModificationSlots` - weapons and weapon parts, 109 templates. These hang off
      *components* rather than the weapon: a muzzle device fits the barrel, the barrel fits the
      receiver, the receiver fits the weapon, so one gun is a tree.
    - `ContainerSlots` - body parts, helmets and a few internals, 27 templates. An
      `L.Arm Nobunaga` has two, filtered to "Modified hydraulics" and "Modified Structure",
      which is the game's way of saying hydraulics and a structure go in an arm. A `GP` helmet
      has one, filtered to its own `GP Visor`.

    `ContainerSlots` entries carry a **`LocalizedName` of their own**, which beats any label
    derived from their contents, so it is resolved here when the items table is available.
    """
    slots: list[dict[str, Any]] = []

    def add(raw: dict[str, Any], source: str) -> None:
        templates, subcategories, tags = _filter_template_ids(raw.get("ItemsFilter") or {})
        # The all-zero GUID is the data's "nothing" placeholder - two helmet slots use it - and
        # naming it as a permitted part would put an unresolvable row in the UI.
        templates = {t for t in templates if t != _EMPTY_GUID}

        # **A container slot is only an attachment point if it says what fits.** Reading
        # `ContainerSlots` wholesale also picks up ordinary compartments: 24 slots on Valuable
        # deposits and 43 on internal objects carry no filter at all, and showing those would
        # promise an attachment point where the game just has a pocket. Body parts filter on
        # every one of their 25 slots, helmets on 6 of 9 - so the filter is the discriminator,
        # not the category. Weapon slots are kept regardless; all 195 of them filter anyway.
        if source == "container" and not (templates or subcategories or tags):
            return
        default = raw.get("DefaultItemTemplateId")
        name = None
        reference = raw.get("LocalizedName")
        if isinstance(reference, dict) and isinstance(items_table, dict):
            entry_id = reference.get("TableEntryReference")
            if isinstance(entry_id, int):
                raw_name = items_table.get(entry_id)
                if isinstance(raw_name, str) and raw_name.strip():
                    name = _clean_category_label(raw_name)
        slots.append({
            "type": raw.get("Type") if isinstance(raw.get("Type"), int) else None,
            "required": bool(raw.get("IsRequiredToEquip")),
            "default_template_id": (
                normalize_guid(default)
                if isinstance(default, str) and default.strip()
                and normalize_guid(default) != _EMPTY_GUID
                else None
            ),
            "allows": sorted(templates),
            # Kept alongside the expanded `allows` so a reader can see where an entry came
            # from. `_resolve_slot_filters` folds both into `allows` in a second pass.
            "allows_subcategories": sorted(subcategories),
            "allows_tags": sorted(tags),
            "name": name,
            "source": source,
        })

    for component in entry.get("_components") or []:
        data = component.get("_data") if isinstance(component, dict) else None
        if not isinstance(data, dict):
            continue
        for field, source in (("ModificationSlots", "weapon"), ("ContainerSlots", "container")):
            if isinstance(data.get(field), list):
                for raw in data[field]:
                    if isinstance(raw, dict):
                        add(raw, source)
    return slots or None


_LOCALIZED_MARKUP = re.compile(r"<[^>]*>")
_LOCALIZED_LINK = re.compile(r"\{link\.([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\}")
_LOCALIZED_PLACEHOLDER = re.compile(r"\{[^}]*\}")


def _build_all_localization_tables(localization_env: Any) -> dict[str, dict[int, str]]:
    """Every string table in the bundle at once, keyed by its full name.

    Link placeholders point at arbitrary tables - a quest name pulls from `Quests`,
    `UI_Common` and `Shelter` - so resolving them needs all of them, not one prefix.
    """
    tables: dict[str, dict[int, str]] = {}
    for obj in localization_env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict):
            continue
        name = tree.get("m_Name")
        data = tree.get("m_TableData")
        if not isinstance(name, str) or not isinstance(data, list):
            continue
        entries: dict[int, str] = {}
        for row in data:
            if not isinstance(row, dict):
                continue
            entry_id = row.get("m_Id")
            text = row.get("m_Localized")
            if isinstance(entry_id, int) and isinstance(text, str):
                entries[entry_id] = text
        if entries:
            tables[name] = entries
    return tables


def _build_shared_key_maps(shared_env: Any) -> dict[str, dict[str, int]]:
    """`KEY -> entry id` per table, read from the `<Table> Shared Data` assets.

    The same mechanism the category labels already go through, just not restricted to one
    table: a link names a table and a key, and only the shared data can turn that key into
    the numeric id the string tables are indexed by.
    """
    key_maps: dict[str, dict[str, int]] = {}
    for obj in shared_env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict):
            continue
        name = tree.get("m_Name")
        entries = tree.get("m_Entries")
        if not isinstance(name, str) or not name.endswith(" Shared Data"):
            continue
        if not isinstance(entries, list):
            continue
        table_base = name.removesuffix(" Shared Data")
        mapping: dict[str, int] = {}
        for row in entries:
            if not isinstance(row, dict):
                continue
            key = row.get("m_Key")
            entry_id = row.get("m_Id")
            if isinstance(key, str) and isinstance(entry_id, int):
                mapping[key.strip().upper()] = entry_id
        if mapping:
            key_maps[table_base] = mapping
    return key_maps


def _resolve_localized_links(
    text: str,
    locale: str,
    tables: dict[str, dict[int, str]],
    key_maps: dict[str, dict[str, int]],
    depth: int = 0,
) -> str:
    """Substitutes `{link.Table.KEY}` with the text it points at.

    Without this, 74 quest names strip down to husks like `":  1"`, because everything
    that carries meaning sits inside the placeholders - the real name is
    `{link.Quests.…_NAME}: {link.UI_Common.UI_COMMON_PART} 2`, "Life is a Shooting Range:
    Part 2". Depth is capped because a link may contain another one.
    """
    if depth >= 4:
        return text

    def substitute(match: re.Match) -> str:
        table_base, key = match.group(1), match.group(2)
        entry_id = (key_maps.get(table_base) or {}).get(key.strip().upper())
        if entry_id is None:
            return ""
        for table_name in (f"{table_base}_{locale}", f"{table_base}_en"):
            value = (tables.get(table_name) or {}).get(entry_id)
            if isinstance(value, str) and value.strip():
                return _resolve_localized_links(value, locale, tables, key_maps, depth + 1)
        return ""

    return _LOCALIZED_LINK.sub(substitute, text)


def _clean_localized(
    text: Any,
    locale: str = "en",
    tables: dict[str, dict[int, str]] | None = None,
    key_maps: dict[str, dict[str, int]] | None = None,
) -> str | None:
    """A localized string with links resolved and TextMeshPro markup removed.

    Anything that still has no two consecutive letters afterwards is reported as unusable
    rather than shown - the caller then falls back to the developers' own alias, which is
    always there.
    """
    if not isinstance(text, str):
        return None
    cleaned = text
    if tables is not None and key_maps is not None:
        cleaned = _resolve_localized_links(cleaned, locale, tables, key_maps)
    cleaned = _LOCALIZED_MARKUP.sub("", cleaned)
    cleaned = _LOCALIZED_PLACEHOLDER.sub("", cleaned)
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # A resolved link that came back empty leaves the punctuation that joined it, e.g.
    # a leading ": ".
    cleaned = cleaned.strip(" :-–—,;.")
    if not re.search(r"[^\W\d_]{2}", cleaned):
        return None
    return cleaned


def _extract_quests_meta(
    repo_env: Any,
    locale: str,
    tables: dict[str, dict[int, str]],
    key_maps: dict[str, dict[str, int]],
) -> dict[str, dict[str, Any]]:
    """Every quest the game ships, keyed by its id.

    A save only ever names the quests it has met, so the count of what exists cannot come
    from a save at all - the same reason the item maxima are read from here. 302 templates
    against 179 ids in a real save is what makes "never seen" answerable.

    A name reference names its own table, `Quests` or `DailyQuests`, so the lookup follows
    the reference rather than guessing.
    """
    quests_text = None
    for obj in repo_env.objects:
        if obj.type.name != "TextAsset":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if isinstance(tree, dict) and tree.get("m_Name") == "quests":
            script = tree.get("m_Script")
            if isinstance(script, str) and script.strip():
                quests_text = script
                break

    if not quests_text:
        return {}

    try:
        quests_json = json.loads(quests_text)
    except Exception:
        return {}
    if not isinstance(quests_json, list):
        return {}

    def resolve(reference: Any) -> str | None:
        if not isinstance(reference, dict):
            return None
        table_base = reference.get("TableReference")
        entry_id = reference.get("TableEntryReference")
        if not isinstance(table_base, str) or not isinstance(entry_id, int):
            return None
        for table_name in (f"{table_base}_{locale}", f"{table_base}_en"):
            raw = (tables.get(table_name) or {}).get(entry_id)
            if isinstance(raw, str) and raw.strip():
                return _clean_localized(raw, locale, tables, key_maps)
        return None

    meta: dict[str, dict[str, Any]] = {}
    for quest in quests_json:
        if not isinstance(quest, dict):
            continue
        quest_id = quest.get("Id")
        if not isinstance(quest_id, str) or not quest_id.strip():
            continue

        alias = str(quest.get("Alias") or "").strip()
        # The developers' own folders: MISSIONS, DAILY, OTHER, _OBSOLETE and a few one-offs.
        # 87 quests have no resolvable name, so the alias is also the fallback label.
        group = alias.split("/", 1)[0] if alias else ""

        display = quest.get("DisplayInfo") if isinstance(quest.get("DisplayInfo"), dict) else {}
        availability = (
            quest.get("AvailabilityInfo")
            if isinstance(quest.get("AvailabilityInfo"), dict)
            else {}
        )
        unlock = (
            availability.get("UnlockRequirement")
            if isinstance(availability.get("UnlockRequirement"), dict)
            else {}
        )

        required = [
            str(value).strip().lower()
            for value in (unlock.get("_completedQuestIds") or [])
            if isinstance(value, str) and value.strip()
        ]

        sender = quest.get("LetterSender") if isinstance(quest.get("LetterSender"), dict) else {}
        npc_id = sender.get("NpcBioId")

        meta[quest_id.strip().lower()] = {
            "alias": alias,
            "group": group,
            "name": resolve(quest.get("LocalizedName")),
            "description": resolve(quest.get("LocalizedDescription")),
            # Two different flags, and they do not overlap: `HideInOrdersList` keeps a quest
            # out of the in-game list, `IsShadowQuest` is the game's own word for one that
            # runs without announcing itself.
            "hidden": bool(display.get("HideInOrdersList")),
            "shadow": bool(availability.get("IsShadowQuest")),
            "tutorial": bool(availability.get("IsTutorialQuest")),
            "sender_npc_id": npc_id.strip().lower() if isinstance(npc_id, str) else None,
            "requires_quest_ids": required,
            "min_account_level": unlock.get("_minAccountLevel"),
            "max_account_level": unlock.get("_maxAccountLevel"),
            "rewards": _quest_rewards(quest),
        }

    return meta


def _quest_rewards(quest: dict[str, Any]) -> dict[str, Any]:
    """XP and item templates a quest pays out.

    Rewards sit in two places: a flat `Rewards` list and `CompletionTypeToReward`, which
    splits them by how the quest was finished. Both are walked, and the entries are told
    apart by the fields they carry rather than by their numeric `$t`, which a game update
    renumbers.
    """
    experience = 0
    items: list[dict[str, Any]] = []

    def take(reward_list: Any) -> None:
        nonlocal experience
        if not isinstance(reward_list, list):
            return
        for reward in reward_list:
            if not isinstance(reward, dict):
                continue
            points = reward.get("ExperiencePoints")
            if isinstance(points, (int, float)) and not isinstance(points, bool):
                experience += int(points)
            for entry in reward.get("ItemRewards") or []:
                if not isinstance(entry, dict):
                    continue
                template_id = entry.get("ItemTemplateId")
                count = entry.get("Count")
                if isinstance(template_id, str) and template_id.strip():
                    items.append({
                        "template_id": template_id.strip().lower(),
                        "count": int(count) if isinstance(count, (int, float)) else 1,
                    })

    take(quest.get("Rewards"))
    by_completion = quest.get("CompletionTypeToReward")
    if isinstance(by_completion, dict):
        for outcome in by_completion.values():
            if isinstance(outcome, dict):
                take(outcome.get("Rewards"))

    return {"xp": experience, "items": items}


def _read_repo_text_asset(repo_env: Any, name: str) -> Any:
    """The parsed JSON of one named TextAsset in the repository bundle, or None."""
    for obj in repo_env.objects:
        if obj.type.name != "TextAsset":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict) or tree.get("m_Name") != name:
            continue
        script = tree.get("m_Script")
        if not isinstance(script, str) or not script.strip():
            return None
        try:
            return json.loads(script)
        except Exception:
            return None
    return None


def _recycler_foundation_id(repo_env: Any) -> str | None:
    """Id of the Recycler shelter module, found by its `Alias` rather than by a hardcoded GUID.

    The alias is the developers' own name for the foundation and is stable across updates in
    a way a GUID in this file would not be checkable against.
    """
    foundations = _read_repo_text_asset(repo_env, "shelter_module_foundations")
    if not isinstance(foundations, list):
        return None
    for entry in foundations:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("Alias") or "").strip().lower() != "recycler":
            continue
        found_id = entry.get("Id")
        if isinstance(found_id, str) and found_id.strip():
            return normalize_guid(found_id)
    return None


def _extract_craft_meta(repo_env: Any) -> dict[str, Any]:
    """What an item turns into when recycled, and what it is an ingredient for.

    Recycling is not a separate system in the data: it is `craft_recipes` sitting on the
    Recycler shelter module. Measured across the 1150 recipes - 976 are on the Recycler, and
    975 of those take exactly one unit of exactly one item, which is what makes "recycle this
    item" a well-defined question with a table for an answer.

    The output depends on how far the module is built: `MinLevel` runs 1, 2, 3, 5 and a
    single item can have up to six recipes, one per stage. They are kept as a list rather
    than collapsed, because the right one to show depends on the player's own module level.

    `used_in` is the other direction, and covers **all** recipes rather than only the
    Recycler's: 440 templates are the sole input of something, and knowing what an item feeds
    into is what stops it being scrapped by mistake.
    """
    recipes = _read_repo_text_asset(repo_env, "craft_recipes")
    if not isinstance(recipes, list):
        return {"recycler_foundation_id": None, "recycling": {}, "used_in": {}}

    recycler_id = _recycler_foundation_id(repo_env)
    recycling: dict[str, list[dict[str, Any]]] = defaultdict(list)
    used_in: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue
        # The developers' own scratch prefix: 24 recipes named `xyz_template_*` or
        # `xyzOBSOLETE_*`, carrying placeholder ingredients - one wants 604 rounds of 9x19 to
        # make 9x19. Listing them promises a recipe nobody can craft, and they were most of
        # what made 9x19 look like an ingredient in 92 things.
        #
        # A tempting alternative is `ShowInModuleScreen`, which is absent on all 24 - the
        # serializer's usual omission, so absent means false. It is **not** used here because
        # it is absent on 121 further recipes that have not been examined, and filtering those
        # out would drop content on a guess. The prefix is narrow and checkable: none of the 24
        # sit on the Recycler, so recycling is provably untouched by this.
        if str(recipe.get("EditorName") or "").lower().startswith("xyz"):
            continue
        inputs = recipe.get("Inputs")
        outputs = recipe.get("Outputs")
        if not isinstance(inputs, list) or not isinstance(outputs, list) or not inputs:
            continue

        module = (
            recipe.get("MainBuiltLeveledShelterModule")
            if isinstance(recipe.get("MainBuiltLeveledShelterModule"), dict)
            else {}
        )
        foundation = normalize_guid(str(module.get("ShelterModuleFoundationId") or ""))
        min_level = module.get("MinLevel")
        duration = recipe.get("CraftDuration")

        def parts(entries: Any) -> list[dict[str, Any]]:
            """One entry per template, with the counts summed.

            Some recipes express a quantity by **repeating the entry** rather than by setting
            `Count`: `xyzOBSOLETE_ServoCure+` lists 9x19 four times at Count 1. Taking the
            list as-is produced four identical rows, which turned 26 real uses of 9x19 into 92
            duplicates in the UI. 20 of the 1150 recipes do this; none of them are the
            Recycler's, so recycling is unaffected either way - verified by counting both
            rules against the bundle: 975 recipes qualify under each.
            """
            merged: dict[str, int] = {}
            for entry in entries if isinstance(entries, list) else []:
                if not isinstance(entry, dict):
                    continue
                template_id = entry.get("ItemTemplateId")
                if not isinstance(template_id, str) or not template_id.strip():
                    continue
                count = entry.get("Count")
                key = normalize_guid(template_id)
                merged[key] = merged.get(key, 0) + (
                    int(count) if isinstance(count, (int, float)) else 1
                )
            return [{"template_id": key, "count": value} for key, value in merged.items()]

        input_parts = parts(inputs)
        output_parts = parts(outputs)
        if not input_parts or not output_parts:
            continue

        name = str(recipe.get("EditorName") or "").strip()

        # Only a single-input recipe on the Recycler answers "what do I get for this item".
        # A multi-input one is a craft that happens to consume it, and belongs in `used_in`.
        is_recycling = (
            recycler_id is not None
            and foundation == recycler_id
            and len(input_parts) == 1
            and input_parts[0]["count"] == 1
        )
        if is_recycling:
            recycling[input_parts[0]["template_id"]].append({
                "min_level": int(min_level) if isinstance(min_level, int) else 1,
                "duration_seconds": (
                    int(duration) if isinstance(duration, (int, float)) else None
                ),
                "outputs": output_parts,
            })
            # Deliberately not also recorded as a use. It is the same recipe shown twice, and
            # 976 of the 1150 recipes are the Recycler's - listing them in both directions
            # doubled the report for nothing.
            continue

        # `makes` is the template of the **first** output, and it is here because the recipe's
        # own EditorName is often an internal identifier: 230 of 659 read like
        # "Head_01_Model_05" rather than like an item. Resolved through the catalog it becomes
        # the item's real name, and one id per row costs about 33 KB. The full output list is
        # still left out - that is what cost a megabyte - and `name` stays as the fallback for
        # rows whose output has no resolvable name.
        for part in input_parts:
            used_in[part["template_id"]].append({
                "name": name,
                "count": part["count"],
                "makes": output_parts[0]["template_id"],
            })

    for rows in recycling.values():
        rows.sort(key=lambda row: row["min_level"])

    return {
        "recycler_foundation_id": recycler_id,
        "recycling": dict(recycling),
        "used_in": dict(used_in),
    }


def _extract_presets_meta(
    repo_env: Any, template_meta: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """The game's own factory configurations: a finished item with the parts already fitted.

    `item_presets` ships 1049 entries and most of them are **loot tables**, not configurations:
    971 carry dice of some kind - a `Chance` below 1, a `MinCount`/`MaxCount` range, a `Weight`
    for a random draw, a nested `ItemsPresetId`, a durability range. Those answer "what might
    spawn in this crate", which is a different question from "give me this gun the way the game
    builds it", so they are left out rather than resolved by rolling for the user.

    Two further filters, both narrow and both measured:

    - an alias beginning with DELETE is the developers' own marker (`DELETE_ASAP_Oscar590A1_
      Modified_GripX_Supressor`); there are two.
    - the root template must **have attachment points**. That rule drops six of the remaining
      59: five scenery placeholders whose contents are grid items in a container the player
      never carries (a Toolbox holding junk, two invisible lockers, a PC with wires) and
      `Quest_DeadMonster_01_Loot`, a monster's head with nothing to fit into it.

    What remains is 53 presets, every one a firearm, covering 35 distinct weapons with one to
    seven parts each: `Oscar590A1_Default` is the shotgun with its magazine, barrel, grip and
    receiver, and `DVS_MK2` the same gun with an extended magazine and the X parts.

    Parts are stored **flat with a parent index** rather than nested, because that is the shape
    the spawner walks: create the root, then each part into the host it belongs to. `parent` is
    an index into the same list, or -1 for a part sitting directly on the root.
    """
    presets = _read_repo_text_asset(repo_env, "item_presets")
    if not isinstance(presets, list):
        return []

    dice_keys = ("RandomPresets", "MinCount", "MaxCount", "Weight", "ItemsPresetId",
                 "MinDurability", "MaxDurability", "Modificators")

    def deterministic(node: Any) -> bool:
        """True when nothing anywhere in the entry leaves the outcome to chance."""
        if isinstance(node, dict):
            if node.get("Chance") not in (None, 1.0):
                return False
            if any(node.get(key) not in (None, [], {}) for key in dice_keys):
                return False
            return all(deterministic(value) for value in node.values())
        if isinstance(node, list):
            return all(deterministic(value) for value in node)
        return True

    def template_of(node: Any) -> str:
        """A preset entry names its template directly, or through `Container` when it is one."""
        if not isinstance(node, dict):
            return ""
        container = node.get("Container") if isinstance(node.get("Container"), dict) else {}
        raw = container.get("ItemItemplateId") or node.get("ItemItemplateId")
        return normalize_guid(str(raw)) if isinstance(raw, str) and raw.strip() else ""

    def collect(node: Any, parent: int, parts: list[dict[str, Any]]) -> None:
        content = node.get("Content") if isinstance(node.get("Content"), dict) else {}
        for wrapper in content.get("Items") or []:
            if not isinstance(wrapper, dict):
                continue
            item = wrapper.get("Item")
            template_id = template_of(item)
            if not template_id:
                continue
            parts.append({"template_id": template_id, "parent": parent})
            collect(item, len(parts) - 1, parts)

    out: list[dict[str, Any]] = []
    for preset in presets:
        if not isinstance(preset, dict):
            continue
        alias = str(preset.get("Alias") or "").strip()
        if alias.upper().startswith("DELETE") or not deterministic(preset):
            continue
        spawn = preset.get("ItemsAtSpawnPoint")
        # One entry means one item. Two would be a spawn point holding several things, which is
        # a scene rather than a configuration.
        if not isinstance(spawn, list) or len(spawn) != 1:
            continue
        root = template_of(spawn[0])
        if not root or not (template_meta.get(root) or {}).get("mod_slots"):
            continue

        parts: list[dict[str, Any]] = []
        collect(spawn[0], -1, parts)
        out.append({
            "id": normalize_guid(str(preset.get("Id") or "")),
            "alias": alias,
            "root": root,
            "parts": parts,
        })

    out.sort(key=lambda row: row["alias"].lower())
    return out


def _extract_shelter_crafting_meta(
    repo_env: Any,
    locale: str,
    tables: dict[str, dict[int, str]],
    key_maps: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """What each shelter workbench can make, and how far it has to be built to make it.

    The same `craft_recipes` list recycling comes from, read from the other end: a recipe names
    its module in `MainBuiltLeveledShelterModule` and the level that module needs. Of the 1150
    recipes, 976 are the Recycler's - already in `craft_meta.recycling`, and repeating them
    here would cost about a megabyte for a second view of the same rows - and **150 survive on
    the seven workbenches** once the scratch recipes are dropped: Body Crafter 46, Laboratory
    46, Armor and textile 23, Ammo 10, 3D Printer 9, Items Crafter 9, Aid 7.

    Each module also carries `max_level`, the number of build steps in
    `BuildPerLevelRequirements`. That number is what makes an unreachable recipe visible:
    `MinLevel` values of 9, 333 and 999 appear on recipes whose module stops at 2 or 3, so the
    content exists in the data while the workbench to run it does not. Marking those beats
    listing them as though they were craftable.
    """
    recipes = _read_repo_text_asset(repo_env, "craft_recipes")
    foundations = _read_repo_text_asset(repo_env, "shelter_module_foundations")
    if not isinstance(recipes, list) or not isinstance(foundations, list):
        return {"modules": []}

    recycler_id = _recycler_foundation_id(repo_env)

    def resolve(reference: Any) -> str | None:
        if not isinstance(reference, dict):
            return None
        table_base = reference.get("TableReference")
        entry_id = reference.get("TableEntryReference")
        if not isinstance(table_base, str) or not isinstance(entry_id, int):
            return None
        for table_name in (f"{table_base}_{locale}", f"{table_base}_en"):
            raw = (tables.get(table_name) or {}).get(entry_id)
            if isinstance(raw, str) and raw.strip():
                return _clean_localized(raw, locale, tables, key_maps)
        return None

    modules: dict[str, dict[str, Any]] = {}
    for entry in foundations:
        if not isinstance(entry, dict):
            continue
        found_id = entry.get("Id")
        if not isinstance(found_id, str) or not found_id.strip():
            continue
        key = normalize_guid(found_id)
        if recycler_id is not None and key == recycler_id:
            continue
        levels = entry.get("BuildPerLevelRequirements")
        modules[key] = {
            "foundation_id": key,
            # The alias is the developers' own English name and always present; the localized
            # name is preferred where the Shelter table has one.
            "alias": str(entry.get("Alias") or "").strip(),
            "name": resolve(entry.get("LocalizedName")),
            "max_level": len(levels) if isinstance(levels, list) else 0,
            "recipes": [],
        }

    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue
        # Same scratch-recipe rule as `_extract_craft_meta`: `xyz*` are the developers' own
        # placeholders, one of them asking for 604 rounds of 9x19 to make 9x19.
        if str(recipe.get("EditorName") or "").lower().startswith("xyz"):
            continue
        module = (
            recipe.get("MainBuiltLeveledShelterModule")
            if isinstance(recipe.get("MainBuiltLeveledShelterModule"), dict)
            else {}
        )
        foundation = normalize_guid(str(module.get("ShelterModuleFoundationId") or ""))
        target = modules.get(foundation)
        if target is None:
            continue

        def parts(entries: Any) -> list[dict[str, Any]]:
            """One row per template with the counts summed - 20 recipes state a quantity by
            repeating the entry instead of setting `Count`."""
            merged: dict[str, int] = {}
            for item in entries if isinstance(entries, list) else []:
                if not isinstance(item, dict):
                    continue
                template_id = item.get("ItemTemplateId")
                if not isinstance(template_id, str) or not template_id.strip():
                    continue
                count = item.get("Count")
                normalized = normalize_guid(template_id)
                merged[normalized] = merged.get(normalized, 0) + (
                    int(count) if isinstance(count, (int, float)) else 1
                )
            return [{"template_id": k, "count": v} for k, v in merged.items()]

        inputs = parts(recipe.get("Inputs"))
        outputs = parts(recipe.get("Outputs"))
        if not inputs or not outputs:
            continue

        min_level = module.get("MinLevel")
        duration = recipe.get("CraftDuration")
        target["recipes"].append({
            "name": str(recipe.get("EditorName") or "").strip(),
            "min_level": int(min_level) if isinstance(min_level, int) else 1,
            "duration_seconds": int(duration) if isinstance(duration, (int, float)) else None,
            "inputs": inputs,
            "outputs": outputs,
        })

    for module in modules.values():
        module["recipes"].sort(key=lambda row: (row["min_level"], row["name"].lower()))
    # A workbench with nothing on it says nothing; the shelter has 16 such foundations.
    kept = [m for m in modules.values() if m["recipes"]]
    kept.sort(key=lambda module: (module.get("name") or module["alias"]).lower())
    return {"modules": kept}


def _build_localization_items_table(localization_env: Any, locale: str) -> tuple[str | None, dict[int, str]]:
    return _build_localization_table(
        localization_env=localization_env,
        table_prefix="Items_",
        locale=locale,
        english_fallback="Items_en",
    )


def _build_localization_table(
    localization_env: Any,
    table_prefix: str,
    locale: str,
    english_fallback: str,
) -> tuple[str | None, dict[int, str]]:
    items_tables: dict[str, dict[int, str]] = {}

    for obj in localization_env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict):
            continue

        table_name = tree.get("m_Name")
        table_data = tree.get("m_TableData")
        if not isinstance(table_name, str) or not table_name.startswith(table_prefix):
            continue
        if not isinstance(table_data, list):
            continue

        entries: dict[int, str] = {}
        for row in table_data:
            if not isinstance(row, dict):
                continue
            entry_id = row.get("m_Id")
            entry_text = row.get("m_Localized")
            if isinstance(entry_id, int) and isinstance(entry_text, str):
                entries[entry_id] = entry_text
        items_tables[table_name] = entries

    preferred = f"{table_prefix}{locale}"
    if preferred in items_tables:
        return preferred, items_tables[preferred]
    if english_fallback in items_tables:
        return english_fallback, items_tables[english_fallback]
    if items_tables:
        selected = sorted(items_tables.keys())[0]
        return selected, items_tables[selected]
    return None, {}


def collect_repository_localized_names(game_path: Path, locale: str) -> dict[str, Any]:
    try:
        import UnityPy  # type: ignore
    except Exception as exc:
        return {
            "enabled": False,
            "reason": f"UnityPy unavailable: {exc}",
            "candidates": {},
            "candidate_sources": {},
        }

    bundles_dir = bundles_dir_for_game(game_path)
    repo_bundle = next(
        iter(sorted(bundles_dir.glob("repositoriesgroup_assets_all*.bundle"))), None
    )
    localization_bundle = next(
        iter(sorted(bundles_dir.glob("localization-stringtables_assets_all*.bundle"))), None
    )
    if not repo_bundle:
        return {
            "enabled": False,
            "reason": "repositoriesgroup bundle not found",
            "candidates": {},
            "candidate_sources": {},
        }
    if not localization_bundle:
        return {
            "enabled": False,
            "reason": "localization stringtable bundle not found",
            "candidates": {},
            "candidate_sources": {},
        }

    localization_env = UnityPy.load(str(localization_bundle))
    items_table_name, items_table = _build_localization_items_table(localization_env, locale)
    if not items_table_name or not items_table:
        return {
            "enabled": False,
            "reason": "no Items_* string table found in localization bundle",
            "candidates": {},
            "candidate_sources": {},
            "npc_candidates": {},
        }
    npc_table_name, npc_table = _build_localization_table(
        localization_env=localization_env,
        table_prefix="Npc_",
        locale=locale,
        english_fallback="Npc_en",
    )
    item_categories_table_name, item_categories_table = _build_localization_table(
        localization_env=localization_env,
        table_prefix="Item_Categories_",
        locale=locale,
        english_fallback="Item_Categories_en",
    )
    skills_table_name, skills_table = _build_localization_table(
        localization_env=localization_env,
        table_prefix="Skills_",
        locale=locale,
        english_fallback="Skills_en",
    )
    # Which quest table the run actually used. Quests ship in en, ja and ru only, so a
    # German UI shows the English names - exactly as it already does for items. The tables
    # themselves are read wholesale further down, because a quest name links into others.
    quests_table_name, _quests_table = _build_localization_table(
        localization_env=localization_env,
        table_prefix="Quests_",
        locale=locale,
        english_fallback="Quests_en",
    )

    repo_env = UnityPy.load(str(repo_bundle))
    item_templates_text = None
    for obj in repo_env.objects:
        if obj.type.name != "TextAsset":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict) or tree.get("m_Name") != "item_templates":
            continue
        script = tree.get("m_Script")
        if isinstance(script, str) and script.strip():
            item_templates_text = script
            break

    if not item_templates_text:
        return {
            "enabled": False,
            "reason": "item_templates TextAsset not found",
            "candidates": {},
            "candidate_sources": {},
            "npc_candidates": {},
        }

    category_label_by_id: dict[int, str] = {}
    subcategory_label_by_id: dict[int, str] = {}
    shared_bundle = next(
        iter(sorted(bundles_dir.glob("localization-assets-shared_assets_all*.bundle"))),
        None,
    )
    # Loaded once and used twice: the category labels below, and the link resolution the
    # quest names need.
    shared_env = None
    if shared_bundle:
        try:
            shared_env = UnityPy.load(str(shared_bundle))
        except Exception:
            shared_env = None

    if shared_env is not None and item_categories_table:
        try:
            for obj in shared_env.objects:
                if obj.type.name != "MonoBehaviour":
                    continue
                tree = obj.read_typetree()
                if tree.get("m_Name") != "Item_Categories Shared Data":
                    continue
                entries = tree.get("m_Entries")
                if not isinstance(entries, list):
                    break
                for row in entries:
                    if not isinstance(row, dict):
                        continue
                    key = row.get("m_Key")
                    entry_id = row.get("m_Id")
                    if not isinstance(key, str) or not isinstance(entry_id, int):
                        continue
                    label = item_categories_table.get(entry_id)
                    if not isinstance(label, str) or not label.strip():
                        continue
                    label = _clean_category_label(label)
                    if not label:
                        continue
                    key = key.strip().upper()
                    if key.startswith("ITEM_CATEGORY_"):
                        suffix = key.removeprefix("ITEM_CATEGORY_")
                        if suffix.isdigit():
                            category_label_by_id[int(suffix)] = label
                    elif key.startswith("ITEM_SUBCATEGORY_"):
                        suffix = key.removeprefix("ITEM_SUBCATEGORY_")
                        if suffix.isdigit():
                            subcategory_label_by_id[int(suffix)] = label
                break
        except Exception:
            pass

    npc_bios_text = None
    for obj in repo_env.objects:
        if obj.type.name != "TextAsset":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict) or tree.get("m_Name") != "npc_bios":
            continue
        script = tree.get("m_Script")
        if isinstance(script, str) and script.strip():
            npc_bios_text = script
            break

    parsed = json.loads(item_templates_text)
    if not isinstance(parsed, list):
        return {
            "enabled": False,
            "reason": "item_templates JSON payload has unexpected format",
            "candidates": {},
            "candidate_sources": {},
            "npc_candidates": {},
        }

    candidates: dict[str, str] = {}
    candidate_sources: dict[str, str] = {}
    template_meta: dict[str, dict[str, Any]] = {}
    npc_candidates: dict[str, str] = {}
    unresolved_link_count = 0
    fallback_alias_count = 0

    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        template_id = entry.get("_id")
        if not isinstance(template_id, str) or not is_guid(template_id):
            continue
        template_id = normalize_guid(template_id)
        alias = _extract_primary_alias(entry)
        entry_ref = _extract_items_table_entry_ref(entry)
        category_id, sub_category_id = _extract_category_ids(entry)
        width, height = _extract_grid_size(entry)
        max_width, max_height, is_resizable = _extract_max_size(entry)
        template_meta[template_id] = {
            "alias": alias,
            "category_id": category_id,
            "subcategory_id": sub_category_id,
            "width": width,
            "height": height,
            "max_durability": _extract_max_durability(entry),
            "has_wear_condition": _extract_has_wear_condition(entry),
            "stack_capacity": _extract_stack_capacity(entry),
            "container": _extract_container(entry),
            "max_width": max_width,
            "max_height": max_height,
            "is_resizable": is_resizable,
            "price": _extract_price(entry),
            "mass": _extract_mass(entry),
            "caliber": _extract_caliber(entry),
            "resize": _extract_resize(entry),
            "mod_slots": _extract_mod_slots(entry, items_table),
            "tags": _extract_tags(entry),
        }

        resolved_name = None
        source = None
        if isinstance(entry_ref, int) and entry_ref in items_table:
            localized_name = items_table[entry_ref].strip()
            if localized_name:
                if "{link." in localized_name and alias:
                    resolved_name = alias
                    source = "item_templates.alias_fallback_for_localization_links"
                    unresolved_link_count += 1
                    fallback_alias_count += 1
                else:
                    resolved_name = localized_name
                    source = f"{items_table_name}.m_TableData"

        if not resolved_name and alias:
            resolved_name = alias
            source = "item_templates.alias"
            fallback_alias_count += 1

        if resolved_name:
            candidates[template_id] = resolved_name
            candidate_sources[template_id] = source or "repository_unknown"

    if npc_bios_text:
        try:
            npc_bios = json.loads(npc_bios_text)
        except Exception:
            npc_bios = []
        if isinstance(npc_bios, list):
            for row in npc_bios:
                if not isinstance(row, dict):
                    continue
                npc_id = row.get("Id")
                if not isinstance(npc_id, str) or not is_guid(npc_id):
                    continue
                npc_id = normalize_guid(npc_id)
                localized = row.get("LocalizedName")
                alias = row.get("Alias")
                if (
                    isinstance(localized, dict)
                    and localized.get("TableReference") == "Npc"
                    and isinstance(localized.get("TableEntryReference"), int)
                    and npc_table
                ):
                    ref = localized["TableEntryReference"]
                    resolved = npc_table.get(ref)
                    if isinstance(resolved, str) and resolved.strip():
                        npc_candidates[npc_id] = resolved.strip()
                        continue
                if isinstance(alias, str) and alias.strip():
                    npc_candidates[npc_id] = alias.strip()

    # Extract Skills
    skills_text = None
    for obj in repo_env.objects:
        if obj.type.name == "TextAsset":
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            if isinstance(tree, dict) and tree.get("m_Name") == "skills":
                script = tree.get("m_Script")
                if isinstance(script, str) and script.strip():
                    skills_text = script
                    break
            
    skills_mapping = {}
    skills_meta = {}
    if skills_text:
        try:
            skills_json = json.loads(skills_text)
            for skill in skills_json:
                skill_id = skill.get("Id")
                alias = skill.get("Alias")
                table_ref = skill.get("LocalizedName", {}).get("TableEntryReference")
                localized_name = None
                if table_ref and skills_table:
                    localized_name = skills_table.get(table_ref)

                name = localized_name or alias
                if name:
                    if alias and "Disabled" in alias:
                        name = f"{name} (Disabled)"
                    skills_mapping[str(skill_id)] = name

                # `MaxVersion` is the skill's maximum level despite the name - measured
                # in-game against a real save: Combat and ItemFind stop at 6 and carry 6,
                # Lockpick stops at 5 and carries 5. It is the only field that fits all
                # three. On a disabled skill the value is meaningless.
                max_level = skill.get("MaxVersion")
                skills_meta[str(skill_id)] = {
                    "alias": alias,
                    "name": name,
                    "max_level": max_level if isinstance(max_level, int) else None,
                    "is_disabled": bool(skill.get("IsDisabled")),
                    "order": skill.get("Order"),
                }
        except Exception:
            pass

    # Extract Trader templates
    shop_templates_text = None
    for obj in repo_env.objects:
        if obj.type.name == "TextAsset":
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            if isinstance(tree, dict) and tree.get("m_Name") == "shop_templates":
                script = tree.get("m_Script")
                if isinstance(script, str) and script.strip():
                    shop_templates_text = script
                    break
            
    trader_mapping = {}
    shops_meta = {}
    if shop_templates_text:
        try:
            shop_templates_json = json.loads(shop_templates_text)
            for shop in shop_templates_json:
                shop_id = shop.get("Id")
                npc_id = shop.get("NpcBioId")
                alias = shop.get("Alias")

                name = None
                if npc_id:
                    name = npc_candidates.get(npc_id.strip().lower())
                if not name:
                    name = alias
                if name:
                    if name == "BasePrice":
                        name = "Base Shop (BasePrice)"
                    elif "RaidShop" in name or "YellowVan" in name:
                        if "Warehouse" in name:
                            name = "Raid Shop (Warehouse)"
                        elif "Port" in name:
                            name = "Raid Shop (Port)"
                        else:
                            name = "Raid Shop (Yellow Van)"
                    trader_mapping[shop_id.strip().lower()] = name

                # `ShopBalance` is what the game itself gives this trader: 500000 for the two
                # that sell and for QuickSell, 100 for the price-reference shop, and nothing
                # at all for the two raid shops. A currency -> amount map, in practice always
                # credits. Whether the game caps a balance above it is unknown - no Max field
                # exists anywhere - but writing the game's own number can never be too much,
                # and it follows a game update on its own.
                balance = shop.get("ShopBalance")
                if isinstance(shop_id, str) and shop_id.strip():
                    shops_meta[shop_id.strip().lower()] = {
                        "alias": alias,
                        "name": name,
                        "balance": balance if isinstance(balance, dict) else {},
                        "order": shop.get("OrderNumber"),
                    }
        except Exception:
            pass

    # Account progression: the level ceiling, and the coefficients the XP goal is built from.
    max_account_level = None
    level_progress = {}
    for obj in repo_env.objects:
        if obj.type.name != "TextAsset":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict) or tree.get("m_Name") != "level_progress_settings":
            continue
        try:
            progress = json.loads(tree.get("m_Script") or "")
        except Exception:
            break
        if not isinstance(progress, dict):
            break
        value = progress.get("MaxLevel")
        if isinstance(value, int) and value > 0:
            max_account_level = value

        # `NextLevelExperienceGoal` for a level is `level * Multiply + Sum`, with both
        # coefficients taken from the band the level falls into. Checked against a real save:
        # a level 25 character carries 62000, and 24 * 3000 - 10000 is exactly that.
        def _bands(key):
            out = []
            for band in progress.get(key) or []:
                if not isinstance(band, dict):
                    continue
                lo, hi = band.get("MinLevel"), band.get("MaxLevel")
                coefficient = band.get("Coefficient")
                if isinstance(lo, int) and isinstance(hi, int) and isinstance(coefficient, (int, float)):
                    out.append({"min_level": lo, "max_level": hi, "coefficient": coefficient})
            return out

        level_progress = {
            "max_level": max_account_level,
            "xp_multiply": _bands("NextLevelMultiplyCoefficients"),
            "xp_sum": _bands("NextLevelSumCoefficients"),
        }
        break

    # Second pass: a tag or subcategory filter can only be turned into parts once every
    # template's own tags are known.
    slot_filter_stats = _resolve_slot_filters(template_meta)

    all_tables = _build_all_localization_tables(localization_env)
    shared_key_maps = _build_shared_key_maps(shared_env) if shared_env is not None else {}
    quests_meta = _extract_quests_meta(repo_env, locale, all_tables, shared_key_maps)
    craft_meta = _extract_craft_meta(repo_env)
    crafting_meta = _extract_shelter_crafting_meta(
        repo_env, locale, all_tables, shared_key_maps)
    presets_meta = _extract_presets_meta(repo_env, template_meta)

    return {
        "enabled": True,
        "reason": None,
        "repo_bundle": str(repo_bundle),
        "localization_bundle": str(localization_bundle),
        "items_table": items_table_name,
        "item_templates_count": len(parsed),
        "npc_bios_count": len(npc_candidates),
        "npc_table": npc_table_name,
        "item_categories_table": item_categories_table_name,
        "category_label_count": len(category_label_by_id),
        "subcategory_label_count": len(subcategory_label_by_id),
        "unresolved_link_count": unresolved_link_count,
        "fallback_alias_count": fallback_alias_count,
        "candidates": candidates,
        "candidate_sources": candidate_sources,
        "template_meta": template_meta,
        "npc_candidates": npc_candidates,
        "category_label_by_id": category_label_by_id,
        "subcategory_label_by_id": subcategory_label_by_id,
        "skills_mapping": skills_mapping,
        "skills_meta": skills_meta,
        "trader_mapping": trader_mapping,
        "shops_meta": shops_meta,
        "max_account_level": max_account_level,
        "level_progress": level_progress,
        "quests_table": quests_table_name,
        "quests_meta": quests_meta,
        "craft_meta": craft_meta,
        "crafting_meta": crafting_meta,
        "presets_meta": presets_meta,
        "slot_filter_stats": slot_filter_stats,
    }


def _walk_for_template_candidates(obj: Any, found: list[tuple[str, str]]) -> None:
    if isinstance(obj, dict):
        normalized = {str(k).lower(): v for k, v in obj.items()}
        guid_values = [
            str(v).strip()
            for v in normalized.values()
            if isinstance(v, str) and is_guid(v)
        ]
        name_values = [
            str(v).strip()
            for k, v in normalized.items()
            if k in NAME_FIELD_HINTS and isinstance(v, str) and v.strip()
        ]
        if guid_values and name_values:
            for guid in guid_values:
                for name in name_values:
                    found.append((normalize_guid(guid), name))

        for value in obj.values():
            _walk_for_template_candidates(value, found)
        return

    if isinstance(obj, list):
        for value in obj:
            _walk_for_template_candidates(value, found)


def collect_unitypy_candidates(game_path: Path) -> dict[str, Any]:
    try:
        import UnityPy  # type: ignore
    except Exception as exc:
        return {
            "enabled": False,
            "reason": f"UnityPy unavailable: {exc}",
            "candidates": {},
        }

    bundles_dir = (
        bundles_dir_for_game(game_path)
    )
    template_to_names: dict[str, Counter] = defaultdict(Counter)
    scanned = 0
    failed = 0

    for bundle in sorted(bundles_dir.glob("itemsgroup_assets_*.bundle")):
        scanned += 1
        try:
            env = UnityPy.load(str(bundle))
            for obj in env.objects:
                try:
                    tree = obj.read_typetree()
                except Exception:
                    continue

                found: list[tuple[str, str]] = []
                _walk_for_template_candidates(tree, found)
                for guid, name in found:
                    template_to_names[guid][name] += 1
        except Exception:
            failed += 1
            continue

    return {
        "enabled": True,
        "bundles_scanned": scanned,
        "bundles_failed": failed,
        "candidates": {k: dict(v) for k, v in template_to_names.items()},
    }


def build_final_mapping(
    save_usage: dict[str, Any],
    log_hints: dict[str, Any],
    repository_names: dict[str, Any],
    unitypy_data: dict[str, Any],
) -> list[dict[str, Any]]:
    usage_count: dict[str, int] = save_usage["template_usage_count"]
    usage_sections: dict[str, dict[str, int]] = save_usage["template_usage_sections"]
    log_data: dict[str, dict[str, int]] = log_hints["template_log_hints"]
    repo_candidates: dict[str, str] = repository_names.get("candidates", {})
    repo_sources: dict[str, str] = repository_names.get("candidate_sources", {})
    repo_meta: dict[str, dict[str, Any]] = repository_names.get("template_meta", {})
    category_label_by_id: dict[int, str] = repository_names.get("category_label_by_id", {})
    subcategory_label_by_id: dict[int, str] = repository_names.get("subcategory_label_by_id", {})
    unity_candidates: dict[str, dict[str, int]] = unitypy_data.get("candidates", {})

    all_template_ids = sorted(
        set(usage_count.keys())
        | set(log_data.keys())
        | set(repo_candidates.keys())
        | set(unity_candidates.keys())
    )

    mapping = []
    for tid in all_template_ids:
        name_guess = None
        name_source = None
        name_hits = 0

        if tid in repo_candidates:
            name_guess = repo_candidates[tid]
            name_source = repo_sources.get(tid, "repository")
            name_hits = 1
        elif tid in unity_candidates and unity_candidates[tid]:
            name_guess, name_hits = max(
                unity_candidates[tid].items(), key=lambda kv: kv[1]
            )
            name_source = "UnityPy_typetree"

        record = {
            "template_id": tid,
            "save_count": usage_count.get(tid, 0),
            "save_sections": usage_sections.get(tid, {}),
            "log_hints": log_data.get(tid, {}),
            "name_guess": name_guess,
            "name_guess_source": name_source,
            "name_guess_hits": name_hits,
            "category_id": repo_meta.get(tid, {}).get("category_id"),
            "subcategory_id": repo_meta.get(tid, {}).get("subcategory_id"),
            "category_label": None,
            "subcategory_label": None,
            "width": repo_meta.get(tid, {}).get("width"),
            "height": repo_meta.get(tid, {}).get("height"),
            "max_durability": repo_meta.get(tid, {}).get("max_durability"),
            "has_wear_condition": repo_meta.get(tid, {}).get("has_wear_condition"),
            "stack_capacity": repo_meta.get(tid, {}).get("stack_capacity"),
            "price": repo_meta.get(tid, {}).get("price"),
            "mass": repo_meta.get(tid, {}).get("mass"),
            "caliber": repo_meta.get(tid, {}).get("caliber"),
            "mod_slots": repo_meta.get(tid, {}).get("mod_slots"),
            "tags": repo_meta.get(tid, {}).get("tags"),
            # The storage this item provides, for placing something inside it. `width`/
            # `height` above are the item's own footprint and a different thing entirely.
            "container": repo_meta.get(tid, {}).get("container"),
            # The developer's own name for the template. 55 localized names are shared by
            # several templates - eight items all read "Bodypart Blueprint" - and the alias
            # tells 54 of those 55 groups apart (Bp_LeftArm_02_Model_03, Bp_Head_01_Model_03).
            "alias": repo_meta.get(tid, {}).get("alias"),
            # A resizable item keeps the cells up to MaxSize unusable even while it is drawn
            # at `width`/`height`, so MaxSize is what has to be reserved for it.
            "max_width": repo_meta.get(tid, {}).get("max_width"),
            "max_height": repo_meta.get(tid, {}).get("max_height"),
            "is_resizable": repo_meta.get(tid, {}).get("is_resizable"),
            "resize": repo_meta.get(tid, {}).get("resize"),
            "confidence": (
                "high"
                if name_guess and tid in repo_candidates
                else (
                    "medium"
                    if name_guess or log_data.get(tid)
                    else "low"
                )
            ),
        }
        if isinstance(record["category_id"], int):
            record["category_label"] = category_label_by_id.get(record["category_id"])
        if isinstance(record["subcategory_id"], int):
            record["subcategory_label"] = subcategory_label_by_id.get(record["subcategory_id"])
        mapping.append(record)

    mapping.sort(key=lambda x: (-x["save_count"], x["template_id"]))
    return mapping


def build_item_catalog(mapping: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog = []
    for row in mapping:
        catalog.append(
            {
                "template_id": row.get("template_id"),
                "name": row.get("name_guess"),
                "name_source": row.get("name_guess_source"),
                "category_id": row.get("category_id"),
                "subcategory_id": row.get("subcategory_id"),
                "category_label": row.get("category_label"),
                "subcategory_label": row.get("subcategory_label"),
                "width": row.get("width"),
                "height": row.get("height"),
                "max_durability": row.get("max_durability"),
                "has_wear_condition": row.get("has_wear_condition"),
                "stack_capacity": row.get("stack_capacity"),
                "price": row.get("price"),
                "mass": row.get("mass"),
                "caliber": row.get("caliber"),
                "mod_slots": row.get("mod_slots"),
                "tags": row.get("tags"),
                "container": row.get("container"),
                "alias": row.get("alias"),
                "resize": row.get("resize"),
                "max_width": row.get("max_width"),
                "max_height": row.get("max_height"),
                "is_resizable": row.get("is_resizable"),
                "confidence": row.get("confidence"),
            }
        )
    catalog.sort(
        key=lambda row: (
            row["category_id"] if isinstance(row.get("category_id"), int) else 999999,
            row["subcategory_id"]
            if isinstance(row.get("subcategory_id"), int)
            else 999999,
            (row.get("name") or "").lower(),
            row.get("template_id") or "",
        )
    )
    return catalog


def run_extraction(
    game_path_str: str,
    save_path_str: str,
    out_dir_str: str,
    locale: str = "en",
) -> dict[str, Any]:
    game_path = Path(game_path_str)
    save_path = Path(save_path_str)
    out_dir = Path(out_dir_str)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not game_path.exists():
        raise FileNotFoundError(f"Game path not found: {game_path}")
    if not save_path.exists():
        raise FileNotFoundError(f"Save path not found: {save_path}")

    save_usage = collect_save_template_usage(save_path)
    log_hints = collect_log_template_hints(game_path)
    bundle_hints = collect_bundle_slug_hints(game_path)
    repository_names = collect_repository_localized_names(game_path, locale=locale)
    unitypy_data = collect_unitypy_candidates(game_path)
    mapping = build_final_mapping(save_usage, log_hints, repository_names, unitypy_data)
    item_catalog = build_item_catalog(mapping)

    # A run that resolved no names at all would replace a working report with nothing but
    # GUIDs, so bail out before any output file is touched.
    if not any(row["name_guess"] for row in mapping):
        reason = (
            repository_names.get("reason")
            or unitypy_data.get("reason")
            or "no item names could be read from the game assets"
        )
        raise RuntimeError(
            "Extraction resolved 0 item names, so the existing mapping was kept.\n"
            f"Reason: {reason}\n"
            f"Bundles expected in: {bundles_dir_for_game(game_path)}"
        )

    report = {
        "game_path": str(game_path),
        # File name only. The report is committed, and the usual place to read a save from is
        # Steam's userdata/<id64>/4197990/remote - a full path would publish that id. Nothing
        # reads this field; it exists to say which save the run was measured against.
        "save_path": save_path.name,
        "unitypy_enabled": bool(unitypy_data.get("enabled")),
        "unitypy_reason": unitypy_data.get("reason"),
        "repository_mapping_enabled": bool(repository_names.get("enabled")),
        "repository_mapping_reason": repository_names.get("reason"),
        "repository_mapping_meta": {
            "repo_bundle": repository_names.get("repo_bundle"),
            "localization_bundle": repository_names.get("localization_bundle"),
            "items_table": repository_names.get("items_table"),
            "item_templates_count": repository_names.get("item_templates_count"),
            "npc_table": repository_names.get("npc_table"),
            "npc_bios_count": repository_names.get("npc_bios_count"),
            "item_categories_table": repository_names.get("item_categories_table"),
            "category_label_count": repository_names.get("category_label_count"),
            "subcategory_label_count": repository_names.get("subcategory_label_count"),
            "unresolved_link_count": repository_names.get("unresolved_link_count"),
            "fallback_alias_count": repository_names.get("fallback_alias_count"),
            "quests_table": repository_names.get("quests_table"),
            "quests_count": len(repository_names.get("quests_meta") or {}),
            "slot_filter_stats": repository_names.get("slot_filter_stats"),
            "recycler_foundation_id": (
                repository_names.get("craft_meta") or {}).get("recycler_foundation_id"),
            "recyclable_count": len(
                (repository_names.get("craft_meta") or {}).get("recycling") or {}),
            "used_in_count": len(
                (repository_names.get("craft_meta") or {}).get("used_in") or {}),
            "crafting_modules": len(
                (repository_names.get("crafting_meta") or {}).get("modules") or []),
            "crafting_recipes": sum(
                len(module.get("recipes") or [])
                for module in (
                    (repository_names.get("crafting_meta") or {}).get("modules") or [])),
            "presets_count": len(repository_names.get("presets_meta") or []),
        },
        "summary": {
            "template_ids_in_save": len(save_usage["template_usage_count"]),
            "template_ids_with_log_hints": len(log_hints["template_log_hints"]),
            "template_ids_with_name_guess": sum(1 for r in mapping if r["name_guess"]),
            "template_ids_with_repository_name": len(repository_names.get("candidates", {})),
            "npc_ids_with_name_guess": len(repository_names.get("npc_candidates", {})),
            "category_labels": len(repository_names.get("category_label_by_id", {})),
            "subcategory_labels": len(repository_names.get("subcategory_label_by_id", {})),
            "item_bundle_slug_count": len(bundle_hints["bundle_slug_hints"]),
            "catalog_items_total": len(item_catalog),
        },
        "mapping": mapping,
        "item_catalog": item_catalog,
        "npc_name_mapping": repository_names.get("npc_candidates", {}),
        "skills_mapping": repository_names.get("skills_mapping", {}),
        "skills_meta": repository_names.get("skills_meta", {}),
        "trader_mapping": repository_names.get("trader_mapping", {}),
        "shops_meta": repository_names.get("shops_meta", {}),
        "max_account_level": repository_names.get("max_account_level"),
        "level_progress": repository_names.get("level_progress", {}),
        "quests_meta": repository_names.get("quests_meta", {}),
        "craft_meta": repository_names.get("craft_meta", {}),
        "crafting_meta": repository_names.get("crafting_meta", {}),
        "presets_meta": repository_names.get("presets_meta", []),
        "bundle_slug_hints": bundle_hints["bundle_slug_hints"],
    }

    json_path = out_dir / "template_mapping_report.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    csv_path = out_dir / "template_mapping.csv"
    with csv_path.open("w", encoding="utf-8") as f:
        f.write(
            "template_id,save_count,confidence,name_guess,name_guess_source,category_id,category_label,subcategory_id,subcategory_label,log_hint_fields\n"
        )
        for row in mapping:
            fields = "|".join(sorted(row["log_hints"].keys()))
            name = (row["name_guess"] or "").replace('"', '""')
            category_label = (row.get("category_label") or "").replace('"', '""')
            subcategory_label = (row.get("subcategory_label") or "").replace('"', '""')
            f.write(
                f"{row['template_id']},{row['save_count']},{row['confidence']},\"{name}\",{row['name_guess_source'] or ''},{row.get('category_id') if row.get('category_id') is not None else ''},\"{category_label}\",{row.get('subcategory_id') if row.get('subcategory_id') is not None else ''},\"{subcategory_label}\",\"{fields}\"\n"
            )

    catalog_csv_path = out_dir / "item_catalog.csv"
    with catalog_csv_path.open("w", encoding="utf-8") as f:
        # No code reads this file - the app reads the JSON report. It exists to be opened in a
        # spreadsheet, which is why price and mass are in it: looking up what something is
        # worth is the reason someone opens a catalog. An empty cell means the game records no
        # value, which is not the same as zero.
        f.write(
            "category_id,category_label,subcategory_id,subcategory_label,name,template_id,width,height,price,mass,name_source,confidence\n"
        )
        for row in item_catalog:
            name = (row.get("name") or "").replace('"', '""')
            category_label = (row.get("category_label") or "").replace('"', '""')
            subcategory_label = (row.get("subcategory_label") or "").replace('"', '""')
            f.write(
                f"{row.get('category_id') if row.get('category_id') is not None else ''},\"{category_label}\",{row.get('subcategory_id') if row.get('subcategory_id') is not None else ''},\"{subcategory_label}\",\"{name}\",{row.get('template_id') or ''},{row.get('width') if row.get('width') is not None else ''},{row.get('height') if row.get('height') is not None else ''},{row.get('price') if row.get('price') is not None else ''},{row.get('mass') if row.get('mass') is not None else ''},{row.get('name_source') or ''},{row.get('confidence') or ''}\n"
            )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract best-effort TemplateId mapping hints from Cargo Hunters installation."
    )
    parser.add_argument(
        "--game-path",
        required=True,
        help="Path to the Cargo Hunters game folder, e.g. "
        r'"C:\Program Files (x86)\Steam\steamapps\common\Cargo Hunters". '
        "There is no sensible default, so it has to be given.",
    )
    parser.add_argument(
        "--save-path",
        default=str(Path(__file__).with_name("offline.save")),
        help="Path to offline.save.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).with_name("generated")),
        help="Output directory for generated reports.",
    )
    parser.add_argument(
        "--locale",
        default="en",
        help="Preferred localization suffix for item names (e.g. en, de, ru).",
    )
    args = parser.parse_args()

    report = run_extraction(
        game_path_str=args.game_path,
        save_path_str=args.save_path,
        out_dir_str=args.out_dir,
        locale=args.locale,
    )

    out_dir = Path(args.out_dir)
    print(f"Wrote report: {out_dir / 'template_mapping_report.json'}")
    print(f"Wrote table : {out_dir / 'template_mapping.csv'}")
    print(f"Wrote catalog: {out_dir / 'item_catalog.csv'}")
    print(f"UnityPy mode: {'enabled' if report['unitypy_enabled'] else 'disabled'}")
    if report.get("unitypy_reason"):
        print(f"Reason      : {report['unitypy_reason']}")
    print(
        "Repository mapping:",
        "enabled" if report["repository_mapping_enabled"] else "disabled",
    )
    if report.get("repository_mapping_reason"):
        print(f"Repository reason: {report['repository_mapping_reason']}")
    print(f"Templates in save: {report['summary']['template_ids_in_save']}")
    print(f"Templates with name guess: {report['summary']['template_ids_with_name_guess']}")



if __name__ == "__main__":
    main()
