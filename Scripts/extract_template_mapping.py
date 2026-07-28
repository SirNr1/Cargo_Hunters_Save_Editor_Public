import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
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
    if shared_bundle and item_categories_table:
        try:
            shared_env = UnityPy.load(str(shared_bundle))
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
                    key = key.strip().upper()
                    if key.startswith("ITEM_CATEGORY_"):
                        suffix = key.removeprefix("ITEM_CATEGORY_")
                        if suffix.isdigit():
                            category_label_by_id[int(suffix)] = label.strip()
                    elif key.startswith("ITEM_SUBCATEGORY_"):
                        suffix = key.removeprefix("ITEM_SUBCATEGORY_")
                        if suffix.isdigit():
                            subcategory_label_by_id[int(suffix)] = label.strip()
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
            "stack_capacity": _extract_stack_capacity(entry),
            "container": _extract_container(entry),
            "max_width": max_width,
            "max_height": max_height,
            "is_resizable": is_resizable,
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
            "stack_capacity": repo_meta.get(tid, {}).get("stack_capacity"),
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
                "stack_capacity": row.get("stack_capacity"),
                "container": row.get("container"),
                "alias": row.get("alias"),
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
        f.write(
            "category_id,category_label,subcategory_id,subcategory_label,name,template_id,width,height,name_source,confidence\n"
        )
        for row in item_catalog:
            name = (row.get("name") or "").replace('"', '""')
            category_label = (row.get("category_label") or "").replace('"', '""')
            subcategory_label = (row.get("subcategory_label") or "").replace('"', '""')
            f.write(
                f"{row.get('category_id') if row.get('category_id') is not None else ''},\"{category_label}\",{row.get('subcategory_id') if row.get('subcategory_id') is not None else ''},\"{subcategory_label}\",\"{name}\",{row.get('template_id') or ''},{row.get('width') if row.get('width') is not None else ''},{row.get('height') if row.get('height') is not None else ''},{row.get('name_source') or ''},{row.get('confidence') or ''}\n"
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
