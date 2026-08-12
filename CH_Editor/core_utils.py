import json
import copy
import os
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple


# The in-game currency ("credits"), used as ItemTemplateId in every shop price.
CREDITS_TEMPLATE_ID = "cb567810-cc82-424f-893f-299c704ffb12"

# How many timestamped backups to keep. 0 or less keeps every one, which is what the
# editor did before this was configurable.
BACKUP_KEEP_DEFAULT = 20

# What the game writes on an item once it stops being factory fresh, and therefore what has
# to go for it to be fresh again. **A mint item carries none of these**: confirmed in play on
# 2026-07-30 against a DORA that the game shows as mint and that has no condition data at all,
# while a repaired weapon sits at `Condition_d: 4.0` and is not mint. Repairing lifts the value
# and leaves the record that the item deviated; only removing it undoes that.
PRISTINE_FIELDS = (
    "Condition_d",                      # current condition, 0-4
    "Condition_mt",                     # the condition it arrived with
    "DurabilityComponent_durability",   # remaining charges
    "DurabilityComponent_md",           # the ceiling those charges can be restored to
)


def default_backup_dir() -> Path:
    """`backups` folder next to the application itself.

    Frozen builds anchor on the executable so backups land beside the EXE rather than
    inside PyInstaller's `_internal`, which is replaced on every rebuild.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    return base / "backups"


# offline_<date>_<time>_<label>[_<n>].save - the shape `save()` writes below.
_BACKUP_NAME = re.compile(r"^offline_(\d{4}-\d{2}-\d{2}_\d{6})_(.+?)(?:_(\d+))?\.save$")

# Where each origin's items live inside the save, for code that has an origin in hand.
_ORIGIN_LIST_PATH = {
    "EquipmentDto": ("EquipmentDto", "Items"),
    "ShelterItemDto": ("ShelterItemDto", "Container", "Items"),
    "InventoryDto": ("InventoryDto", "ItemsContainerDto", "Items"),
}


# --- Comparing two saves -----------------------------------------------------------------
# What the editor is about to write, said out loud. Two rules carry the whole thing:
#
#   - **Items are matched by their Id, never by position in a list.** They live in three
#     parallel lists and a move across sections carries the dict from one into another, so an
#     index-based comparison would report every move as a deletion plus an addition.
#   - **Any other list of dicts that all carry an `Id` is matched by that `Id` too.** Deleting
#     the first of 59 letters shifts the 58 behind it; by index that reads as 58 changes, and
#     by Id it reads as the one deletion it is.
#
# Everything left over is compared leaf by leaf, so a change the categories have no name for
# still shows up as its own path rather than being silently dropped. A confirmation dialog
# that can quietly omit something is worse than none.

_DIFF_ITEM_LISTS = tuple(_ORIGIN_LIST_PATH.values())


def _leaf_paths(node: Any, path: str, out: Dict[str, Any], skip: Set[str]) -> None:
    """Every scalar in the document, keyed by a readable path.

    A list whose entries all carry an `Id` is keyed by that id (`Letters[abc]`), so inserting
    or removing one entry does not shift everything behind it.
    """
    if path in skip:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            _leaf_paths(value, f"{path}.{key}" if path else str(key), out, skip)
        return
    if isinstance(node, list):
        entries = [entry for entry in node if isinstance(entry, dict)]
        by_id = len(entries) == len(node) and node and all(
            isinstance(entry.get("Id"), (str, int)) for entry in entries
        )
        for index, value in enumerate(node):
            key = str(value.get("Id")) if by_id else str(index)
            _leaf_paths(value, f"{path}[{key}]", out, skip)
        if not node:
            out[path] = "[]"
        return
    out[path] = node


def _items_by_id(data: Dict[str, Any]) -> Dict[str, Tuple[str, dict]]:
    """Every item in the save as `id -> (origin, item)`, across all three lists."""
    found: Dict[str, Tuple[str, dict]] = {}
    for origin, path in _ORIGIN_LIST_PATH.items():
        node: Any = data
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        for entry in node if isinstance(node, list) else []:
            if isinstance(entry, dict) and entry.get("Id") is not None:
                found[str(entry["Id"])] = (origin, entry)
    return found


def _item_fields(item: dict) -> Dict[str, Any]:
    """The parts of an item worth naming in a change list."""
    inner = (item.get("AdditionalData") or {}).get("_data")
    fields = {
        "TemplateId": item.get("TemplateId"),
        "ParentId": item.get("ParentId"),
        "Position": json.dumps(item.get("Position"), sort_keys=True),
    }
    if isinstance(inner, dict):
        for key, value in inner.items():
            fields[key] = value
    return fields


def diff_saves(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """What changed between two saves, in terms a person can check.

    Returns four lists. `added` and `removed` are items, each with its template so the caller
    can put a name to it; `changed` is one row per changed field of a surviving item, with the
    origin list included because a move between sections is the one change that is invisible
    in the item itself; `fields` is everything outside the item lists, by path.

    Deliberately not a text diff of the JSON. The save is written with `indent=2` from a dict
    whose key order follows insertion, so a textual comparison reports formatting as content.
    """
    old_items, new_items = _items_by_id(before), _items_by_id(after)

    added = [
        {"id": item_id, "template_id": str(item.get("TemplateId") or ""),
         "parent_id": str(item.get("ParentId") or ""), "origin": origin}
        for item_id, (origin, item) in new_items.items() if item_id not in old_items
    ]
    removed = [
        {"id": item_id, "template_id": str(item.get("TemplateId") or ""),
         "parent_id": str(item.get("ParentId") or ""), "origin": origin}
        for item_id, (origin, item) in old_items.items() if item_id not in new_items
    ]

    changed: List[Dict[str, Any]] = []
    for item_id, (new_origin, new_item) in new_items.items():
        if item_id not in old_items:
            continue
        old_origin, old_item = old_items[item_id]
        old_fields, new_fields = _item_fields(old_item), _item_fields(new_item)
        template = str(new_item.get("TemplateId") or old_item.get("TemplateId") or "")
        if old_origin != new_origin:
            changed.append({"id": item_id, "template_id": template, "field": "origin",
                            "before": old_origin, "after": new_origin})
        for key in sorted(set(old_fields) | set(new_fields)):
            if old_fields.get(key) != new_fields.get(key):
                changed.append({"id": item_id, "template_id": template, "field": key,
                                "before": old_fields.get(key), "after": new_fields.get(key)})

    skip = {".".join(path) for path in _DIFF_ITEM_LISTS}
    old_leaves: Dict[str, Any] = {}
    new_leaves: Dict[str, Any] = {}
    _leaf_paths(before, "", old_leaves, skip)
    _leaf_paths(after, "", new_leaves, skip)
    fields = [
        {"path": path, "before": old_leaves.get(path), "after": new_leaves.get(path)}
        for path in sorted(set(old_leaves) | set(new_leaves))
        if old_leaves.get(path) != new_leaves.get(path)
    ]

    return {"added": added, "removed": removed, "changed": changed, "fields": fields}


def diff_is_empty(diff: Dict[str, Any]) -> bool:
    return not any(diff.get(key) for key in ("added", "removed", "changed", "fields"))


def _backup_order(path: Path) -> Optional[Tuple[datetime, int]]:
    """Creation order taken from the file name, or None for a name this editor did not write.

    The name is authoritative and the modification time is not: a PyInstaller rebuild wipes
    `dist/`, so the backups folder has to be copied aside and back, which stamps every file
    with the same mtime while the names still carry the real order.
    """
    match = _BACKUP_NAME.match(path.name)
    if not match:
        return None
    try:
        stamp = datetime.strptime(match.group(1), "%Y-%m-%d_%H%M%S")
    except ValueError:
        return None
    return stamp, int(match.group(3) or 1)


def prune_backups(
    backup_dir: Path,
    keep: int,
    protect: Optional[Path] = None,
) -> List[Path]:
    """Deletes the oldest backups until at most `keep` remain. Returns what was deleted.

    Only files whose names this editor produced are candidates, so anything else living in
    the folder is left alone. `protect` - the backup the caller just wrote - counts towards
    the limit but is never deleted. `keep` of 0 or less prunes nothing.
    """
    if keep <= 0 or not backup_dir.is_dir():
        return []

    protected = protect.resolve() if protect else None
    candidates: List[Tuple[Tuple[datetime, int], Path]] = []
    total = 0
    for path in backup_dir.glob("offline_*.save"):
        order = _backup_order(path)
        if order is None:
            continue
        total += 1
        if protected is not None and path.resolve() == protected:
            continue
        candidates.append((order, path))

    candidates.sort()
    removed: List[Path] = []
    for _, path in candidates[: max(0, total - keep)]:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            # A backup held open by another program is not worth failing the save over.
            pass
    return removed


def list_backups(backup_dir: Path) -> List[Dict[str, Any]]:
    """The backups this editor wrote, newest first.

    Same name filter as `prune_backups`: a file the editor did not name is not offered for
    restoring, because nothing is known about what it holds. Each entry carries the parsed
    timestamp and the label from the name - `manual_apply`, `before_restore` - so the list
    can say why a backup exists without opening it.
    """
    if not backup_dir.is_dir():
        return []

    found: List[Dict[str, Any]] = []
    for path in backup_dir.glob("offline_*.save"):
        order = _backup_order(path)
        if order is None:
            continue
        match = _BACKUP_NAME.match(path.name)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        found.append({
            "path": path,
            "name": path.name,
            "taken_at": order[0],
            "label": match.group(2) if match else "",
            "size": size,
        })

    found.sort(key=lambda row: (row["taken_at"], row["name"]), reverse=True)
    return found


def restore_backup(save_path: Path, backup_path: Path) -> None:
    """Copies a backup over the save file.

    Deliberately does not take a backup of the current state itself - the caller does that
    through `save()`, so the copy lands in the same folder under the same naming scheme and
    is pruned along with the rest. Doing it here would either duplicate that logic or
    bypass the pruning.
    """
    backup_path = Path(backup_path)
    save_path = Path(save_path)
    if not backup_path.is_file():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    if backup_path.resolve() == save_path.resolve():
        raise ValueError("Backup and save are the same file")

    # Reject a file that is not a save before overwriting anything. A truncated or
    # unrelated file would otherwise replace a working save and only fail on the reload,
    # by which point the original is gone.
    with backup_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or "AccountDto" not in payload:
        raise ValueError(f"{backup_path.name} does not look like a Cargo Hunters save")

    shutil.copyfile(backup_path, save_path)


# --- Container geometry --------------------------------------------------------------
# An item's Position is the game's `Cell {int I, int J}` and a size is its
# `ItemSize {int Width, int Height}`, with **Width on I and Height on J**. Measured rather
# than assumed: across four warehouse tabs of a real save that mapping produced zero
# footprint overlaps and the other one produced 126.
#
# A container's grid is not in the save. It comes from the template's own component, which
# `extract_template_mapping.py` writes into each catalog row as `container`.


def container_cells(spec: Any) -> Optional[Set[Tuple[int, int]]]:
    """Every cell a container offers, or None when its shape is not modelled.

    `spec` is the `container` entry of a row in the generated mapping report:

      simple - one free grid of Width x Height (a warehouse tab is 8x30 or 8x15)
      split  - a union of sub-rectangles at given cells. A cell outside every rectangle does
               not exist, which is the dead area in a rig or vest.
      slots  - fixed compartments, each with its own item filter. None: choosing a
               compartment for an arbitrary item is not a geometry question.

    A `simple` container can carry AllowExpand, meaning the game grows it past that size.
    The base size is used anyway - staying inside it is provably accepted, and two internal
    containers in a real save had already expanded well beyond their 1x1 base.
    """
    if not isinstance(spec, dict):
        return None

    kind = spec.get("kind")
    if kind == "simple":
        width, height = spec.get("width"), spec.get("height")
        if (isinstance(width, int) and isinstance(height, int)
                and width > 0 and height > 0):
            return {(i, j) for i in range(width) for j in range(height)}
        return None

    if kind == "split":
        cells: Set[Tuple[int, int]] = set()
        for region in spec.get("regions") or []:
            if not isinstance(region, dict):
                continue
            width, height = region.get("width"), region.get("height")
            if not isinstance(width, int) or not isinstance(height, int):
                continue
            i0, j0 = int(region.get("i") or 0), int(region.get("j") or 0)
            cells.update((i0 + di, j0 + dj)
                         for di in range(width) for dj in range(height))
        return cells or None

    return None


def find_free_cell(
    cells: Optional[Set[Tuple[int, int]]],
    occupied: Any,
    width: int,
    height: int,
) -> Optional[Tuple[int, int]]:
    """The topmost, leftmost cell where a width x height item fits with nothing in the way.

    Scans J before I so a container fills the way its grid reads. `cells` is what the
    container offers, `occupied` anything already standing in it - a dict or set of cells.
    """
    if not cells or width <= 0 or height <= 0:
        return None

    max_i = max(i for i, _ in cells)
    max_j = max(j for _, j in cells)
    for j in range(max_j + 1):
        for i in range(max_i + 1):
            if all(
                (i + di, j + dj) in cells and (i + di, j + dj) not in occupied
                for di in range(width)
                for dj in range(height)
            ):
                return i, j
    return None


def find_placement(
    cells: Optional[Set[Tuple[int, int]]],
    occupied: Any,
    width: int,
    height: int,
) -> Optional[Tuple[int, int, bool]]:
    """(I, J, rotated) for a width x height item, turned 90 degrees only if it fits no other
    way. Rotation swaps the two axes and is what `BaseComponent_rotated` records."""
    cell = find_free_cell(cells, occupied, width, height)
    if cell:
        return cell[0], cell[1], False
    if width != height:
        cell = find_free_cell(cells, occupied, height, width)
        if cell:
            return cell[0], cell[1], True
    return None


class SaveDataManager:
    def __init__(self, save_path: str, backup_dir: Optional[str] = None):
        self.save_path = Path(save_path)
        self.backup_dir = (
            Path(backup_dir).resolve()
            if backup_dir
            else default_backup_dir()
        )
        self.backup_keep = BACKUP_KEEP_DEFAULT
        # What the last save() pruned, for the caller to report. Never read back here.
        self.last_pruned: List[Path] = []
        self.data: Dict[str, Any] = {}
        self.item_tree: Dict[str, Any] = {}
        self.item_origin: Dict[str, str] = {}  # Id -> 'EquipmentDto' | 'ShelterItemDto' | 'InventoryDto'
        self.section_roots: Dict[str, str] = {}  # 'ShelterItemDto'/'InventoryDto' -> root container Id
        self.children_map: Dict[str, List[str]] = {}
        self._load_data()

    def _load_data(self) -> None:
        with self.save_path.open("r", encoding="utf-8") as f:
            self.data = json.load(f)

        self.item_tree = {}
        self.item_origin = {}
        self.section_roots = {}
        self.children_map = {}

        def harvest(items: List[dict], origin: str) -> None:
            for item in items:
                if not isinstance(item, dict) or "Id" not in item:
                    continue
                s_id = str(item["Id"])
                self.item_tree[s_id] = item
                self.item_origin[s_id] = origin

        equipment = self.data.get("EquipmentDto", {})
        harvest(equipment.get("Items", []), "EquipmentDto")

        shelter = self.data.get("ShelterItemDto", {})
        shelter_root = shelter.get("Item", {}).get("Id")
        if shelter_root:
            self.section_roots["ShelterItemDto"] = str(shelter_root)
        harvest(shelter.get("Container", {}).get("Items", []), "ShelterItemDto")

        inventory = self.data.get("InventoryDto", {})
        inventory_root = inventory.get("ItemDto", {}).get("Id")
        if inventory_root:
            self.section_roots["InventoryDto"] = str(inventory_root)
        harvest(inventory.get("ItemsContainerDto", {}).get("Items", []), "InventoryDto")

        for s_id, item in self.item_tree.items():
            p_id = item.get("ParentId")
            if p_id:
                self.children_map.setdefault(str(p_id), []).append(s_id)

    def get_item(self, item_id: str) -> Optional[dict]:
        return self.item_tree.get(str(item_id))

    def get_children(self, item_id: str) -> List[str]:
        return self.children_map.get(str(item_id), [])

    def get_backpack_id(self) -> Optional[str]:
        """Id of the backpack item, anchored via its stable equipment slot (Index 2)."""
        slots = self.data.get("EquipmentDto", {}).get("SlotsInfo", [])
        slot = next((s for s in slots if s.get("Index") == 2), None)
        return str(slot["ItemId"]) if slot and slot.get("ItemId") else None

    def get_character_items(self) -> List[str]:
        """Ids of items equipped directly on the character (no parent)."""
        return [
            s_id for s_id, item in self.item_tree.items()
            if self.item_origin.get(s_id) == "EquipmentDto" and not item.get("ParentId")
        ]

    def get_shelter_items(self) -> List[str]:
        """Ids of items sitting directly in the shelter's single storage grid."""
        root = self.section_roots.get("ShelterItemDto")
        if not root:
            return []
        return [
            s_id for s_id, item in self.item_tree.items()
            if self.item_origin.get(s_id) == "ShelterItemDto" and str(item.get("ParentId")) == root
        ]

    def get_inventory_tabs(self) -> List[str]:
        """Ids of the top-level tab containers in the main warehouse (InventoryDto), in tab order.

        Read from `children_map` rather than by scanning every item: `is_structural` calls
        this from the bulk mutation paths, where the full scan turned a pass over all items
        quadratic - 0.43 s for one "everything factory fresh" over ~2000 items, measured.
        `children_map` is kept current by every mutating method, so the answer is the same.
        """
        root = self.section_roots.get("InventoryDto")
        if not root:
            return []
        tab_ids = [
            s_id for s_id in self.children_map.get(root, [])
            if self.item_origin.get(s_id) == "InventoryDto"
        ]

        def sort_key(s_id: str):
            pos = self.item_tree[s_id].get("Position") or {}
            return pos.get("I", -1) if isinstance(pos, dict) else -1

        tab_ids.sort(key=sort_key)
        return tab_ids

    def get_all_items_flat(self) -> List[dict]:
        return list(self.item_tree.values())

    def _inventory_origin_list(self) -> List[dict]:
        return (
            self.data.setdefault("InventoryDto", {})
            .setdefault("ItemsContainerDto", {})
            .setdefault("Items", [])
        )

    def cell_of(self, item_id: str) -> Tuple[int, int]:
        """The item's own (I, J) cell. A missing key means zero - the serializer drops a
        field holding its type's default, the same rule that hides an empty equipment slot."""
        item = self.get_item(item_id) or {}
        position = item.get("Position")
        if not isinstance(position, dict):
            return 0, 0
        return int(position.get("I") or 0), int(position.get("J") or 0)

    def occupied_cells(self, parent_id: str, footprint_of) -> Dict[Tuple[int, int], str]:
        """Which cells of a container its children already take, mapped to the child's id.

        `footprint_of(item_id)` returns the child's (width, height) with rotation already
        applied, or None when the size is unknown. An unknown child still blocks its own
        anchor cell - something is standing there even if its extent is a guess.
        """
        taken: Dict[Tuple[int, int], str] = {}
        for child_id in self.get_children(parent_id):
            i, j = self.cell_of(child_id)
            size = footprint_of(child_id)
            width, height = size if size else (1, 1)
            for di in range(max(1, int(width))):
                for dj in range(max(1, int(height))):
                    taken.setdefault((i + di, j + dj), child_id)
        return taken

    def origin_for_parent(self, parent_id: str) -> str:
        """Which of the three item lists a new child of this container belongs in."""
        p_id = str(parent_id)
        origin = self.item_origin.get(p_id)
        if origin:
            return origin
        for key, root in self.section_roots.items():
            if str(root) == p_id:
                return key
        return "InventoryDto"

    def add_inventory_item(
        self,
        parent_id: str,
        template_id: str,
        width: int | None = None,
        height: int | None = None,
        quantity: int | None = None,
        position: Optional[Tuple[int, int]] = None,
    ) -> dict:
        """Creates one item. `quantity` makes it a stack of that many units, which is how
        the game stores stackables: a single item carrying StackableComponent_quantity,
        not one item per unit. Keep it within the template's StackCapacity.

        `position` is the (I, J) cell inside the parent container; callers that want the item
        to survive should get one from `find_placement`, because the game moves an item it
        cannot place into the mailbox. Without one the item lands on (0, 0).

        The item is appended to the list its parent lives in, so this also spawns into
        equipment and shelter containers, not only the warehouse.
        """
        i, j = position if position else (0, 0)
        item: dict = {
            "Id": str(uuid.uuid4()),
            "TemplateId": str(template_id),
            "ParentId": str(parent_id),
            "IsInspected": True,
            "Position": {"I": int(i), "J": int(j)},
        }

        inner: Dict[str, Any] = {}
        if isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0:
            inner["BaseComponent_width"] = width
            inner["BaseComponent_height"] = height
        if isinstance(quantity, int) and quantity > 0:
            inner["StackableComponent_quantity"] = quantity
        if inner:
            item["AdditionalData"] = {"_data": inner}

        origin = self.origin_for_parent(parent_id)
        target_list = self._origin_list(origin)
        if target_list is None:
            target_list = self._inventory_origin_list()
            origin = "InventoryDto"
        target_list.append(item)

        item_id = str(item["Id"])
        self.item_tree[item_id] = item
        self.item_origin[item_id] = origin
        self.children_map.setdefault(str(parent_id), []).append(item_id)
        return item

    def duplicate_item(
        self,
        item_id: str,
        parent_id: Optional[str] = None,
        position: Optional[Tuple[int, int]] = None,
    ) -> Optional[dict]:
        """Clones an item, by default into the same container next to its original.

        `parent_id` moves the copy into a different container and `position` sets its (I, J)
        cell there. Without a position the copy keeps the original's, which puts it exactly
        on top of the item it was cloned from - the game then relocates it to the mailbox.
        Callers should pass a cell from `find_placement`.

        Attachments are not cloned: the copy is the item alone.
        """
        item = self.get_item(item_id)
        if not item:
            return None

        clone = copy.deepcopy(item)
        clone["Id"] = str(uuid.uuid4())
        if parent_id is not None:
            clone["ParentId"] = str(parent_id)
        if position is not None:
            clone["Position"] = {"I": int(position[0]), "J": int(position[1])}

        target_parent = str(clone.get("ParentId") or "")
        origin = (
            self.origin_for_parent(target_parent) if target_parent
            else self.item_origin.get(str(item_id))
        )
        target_list = self._origin_list(origin) if origin else None
        if target_list is None:
            return None
        target_list.append(clone)

        c_id = str(clone["Id"])
        self.item_tree[c_id] = clone
        self.item_origin[c_id] = origin
        if target_parent:
            self.children_map.setdefault(target_parent, []).append(c_id)

        return clone

    # --- Deleting -----------------------------------------------------------------

    def _origin_list(self, origin: Optional[str]) -> Optional[List[dict]]:
        """The list in `self.data` that an origin's items live in, or None if absent.

        Read-only on purpose, unlike the `setdefault` chains above: a save that never had
        one of these lists must not gain an empty one just because something was deleted.
        """
        node: Any = self.data
        for key in _ORIGIN_LIST_PATH.get(origin or "", ()):
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node if isinstance(node, list) else None

    def collect_subtree(self, item_id: str) -> List[str]:
        """The item plus everything attached to it, the item itself first.

        Attachments are separate items linked by ParentId, so a weapon's scope and that
        scope's own parts only come along if the hierarchy is walked. Tolerates a cycle
        and ids that are not in the tree, which a hand-edited save can contain.
        """
        order: List[str] = []
        seen: set[str] = set()
        stack = [str(item_id)]
        while stack:
            current = stack.pop()
            if current in seen or current not in self.item_tree:
                continue
            seen.add(current)
            order.append(current)
            stack.extend(self.get_children(current))
        return order

    def is_pristine(self, item_id: str) -> bool:
        """True when the item carries no wear at all - which is how the game stores a mint one."""
        item = self.item_tree.get(str(item_id))
        if not item:
            return False
        inner = (item.get("AdditionalData") or {}).get("_data") or {}
        if not isinstance(inner, dict):
            return True
        return not any(field in inner for field in PRISTINE_FIELDS)

    def make_pristine(self, item_id: str, include_parts: bool = True) -> List[str]:
        """Removes every trace of wear and returns the ids that changed.

        **Factory fresh is an absence, not a value.** Repairing writes `Condition_d: 4.0`,
        which says "this was damaged and has been restored" - the game keeps that record and
        no longer calls the item mint. An item it does call mint carries no condition data
        whatsoever: measured on a DORA in a rifle case that the game shows as mint, against a
        repaired KA74 sitting at 4.0 next to it.

        `DurabilityComponent_*` goes with it for the same reason: a fresh consumable has no
        charge count, because absence is what "untouched" looks like in this format.
        """
        root = str(item_id)
        # Same refusal the other writers make: a warehouse tab is layout, not an item.
        if root not in self.item_tree or self.is_structural(root):
            return []

        changed: List[str] = []
        for member in (self.collect_subtree(root) if include_parts else [root]):
            item = self.item_tree.get(member)
            if not item:
                continue
            inner = (item.get("AdditionalData") or {}).get("_data")
            if not isinstance(inner, dict):
                continue
            # Every field, not `any(...)`: that short-circuits on the first hit and leaves
            # `Condition_mt` sitting behind the value it belongs to.
            removed = [field for field in PRISTINE_FIELDS
                       if inner.pop(field, None) is not None]
            if not removed:
                continue
            # And nothing empty is left behind: the game writes no empty `_data` anywhere -
            # 0 of them in a real save, while 638 of its 1901 items carry no `AdditionalData`
            # at all. An item with nothing left to record simply has no such key.
            if not inner:
                item.pop("AdditionalData", None)
            changed.append(member)
        return changed

    def is_structural(self, item_id: str) -> bool:
        """True for the containers the save's layout rests on rather than ordinary items:
        the shelter and inventory roots, and the warehouse tabs. Each one holds a whole
        grid the game expects to find."""
        s_id = str(item_id)
        return s_id in set(self.section_roots.values()) or s_id in self.get_inventory_tabs()

    def is_equipped(self, item_id: str) -> bool:
        """True if an equipment slot holds this item, so deleting it empties that slot."""
        slots = self.data.get("EquipmentDto", {}).get("SlotsInfo", [])
        return any(
            isinstance(slot, dict) and str(slot.get("ItemId")) == str(item_id)
            for slot in slots
        )

    def delete_item(self, item_id: str) -> List[str]:
        """Removes an item and everything attached to it. Returns the ids that went.

        The attachments have to go too: one left behind would keep a ParentId pointing at
        an item that no longer exists. An equipment slot holding the item is dropped along
        with it, because the save lists a SlotsInfo entry only for an occupied slot - 17
        entries for 31 slot types in a real save, every one of them carrying an ItemId. A
        missing entry is what an empty slot looks like.

        Positions are deliberately left alone. A container's slots are fixed compartments,
        so the freed Position.J is simply an empty one; renumbering the survivors would
        move items the user did not touch.

        Returns an empty list for an unknown id and for the structural containers that
        `is_structural` names.
        """
        root = str(item_id)
        if root not in self.item_tree or self.is_structural(root):
            return []

        doomed = self.collect_subtree(root)
        gone = set(doomed)
        parent_id = str(self.item_tree[root].get("ParentId") or "")

        # One pass per affected list. A subtree could in principle span two of them, so
        # the origins come from the doomed items rather than from the root alone.
        for origin in {self.item_origin.get(i) for i in gone}:
            origin_list = self._origin_list(origin)
            if origin_list is None:
                continue
            origin_list[:] = [
                entry for entry in origin_list
                if not (isinstance(entry, dict) and str(entry.get("Id")) in gone)
            ]

        slots = self.data.get("EquipmentDto", {}).get("SlotsInfo")
        if isinstance(slots, list):
            slots[:] = [
                slot for slot in slots
                if not (isinstance(slot, dict) and str(slot.get("ItemId")) in gone)
            ]

        for i in doomed:
            self.item_tree.pop(i, None)
            self.item_origin.pop(i, None)
            self.children_map.pop(i, None)

        siblings = self.children_map.get(parent_id)
        if siblings is not None:
            siblings[:] = [child for child in siblings if child != root]
            if not siblings:
                del self.children_map[parent_id]

        return doomed

    # --- Moving, attaching and splitting ------------------------------------------

    def move_item(
        self,
        item_id: str,
        parent_id: str,
        position: Optional[Tuple[int, int]] = None,
    ) -> List[str]:
        """Moves an item and everything attached to it into another container.

        Returns the ids that moved, the item itself first, or an empty list when the move
        was refused. Refused for an unknown id, for the structural containers
        `is_structural` names, for an unknown destination, and for a destination inside the
        item's own subtree - a backpack cannot be put into itself, and the resulting cycle
        would strand every item under it.

        Three things have to travel together, and only the first is obvious:

        - `ParentId` and `Position`, on the moved item alone. Attachments hang off the item,
          not off the container, so their own ParentId is already right.
        - **The list the dicts live in.** An item is stored in one of three lists depending
          on its section, so moving from the warehouse into a carried backpack means moving
          every dict of the subtree from `InventoryDto` into `EquipmentDto` - the ParentId
          alone would leave the game looking for it in the wrong place.
        - The equipment slot, if the item was in one. A slot entry exists only while it is
          occupied, so an item that leaves the character leaves its slot behind, the same
          way `delete_item` empties it.

        The vacated cells are deliberately left as they are. A container's slots are fixed
        compartments, so a freed one is simply empty; renumbering the neighbours would move
        items the user never touched.
        """
        root = str(item_id)
        target_parent = str(parent_id)
        if root not in self.item_tree or self.is_structural(root):
            return []
        if target_parent not in self.item_tree and target_parent not in set(
            self.section_roots.values()
        ):
            return []

        moving = self.collect_subtree(root)
        if target_parent in set(moving):
            return []

        target_origin = self.origin_for_parent(target_parent)
        target_list = self._origin_list(target_origin)
        if target_list is None:
            return []

        # One pass per source list, because a subtree could in principle span two of them.
        # The dicts themselves are carried over rather than rebuilt: every other reference
        # to them - item_tree above all - has to keep pointing at the same object.
        relocating = {
            i for i in moving if self.item_origin.get(i) != target_origin
        }
        if relocating:
            carried: List[dict] = []
            for origin in {self.item_origin.get(i) for i in relocating}:
                origin_list = self._origin_list(origin)
                if origin_list is None:
                    continue
                keep: List[dict] = []
                for entry in origin_list:
                    if isinstance(entry, dict) and str(entry.get("Id")) in relocating:
                        carried.append(entry)
                    else:
                        keep.append(entry)
                origin_list[:] = keep
            target_list.extend(carried)
            for i in relocating:
                self.item_origin[i] = target_origin

        item = self.item_tree[root]
        old_parent = str(item.get("ParentId") or "")
        item["ParentId"] = target_parent
        if position is not None:
            item["Position"] = {"I": int(position[0]), "J": int(position[1])}

        siblings = self.children_map.get(old_parent)
        if siblings is not None:
            siblings[:] = [child for child in siblings if child != root]
            if not siblings:
                del self.children_map[old_parent]
        self.children_map.setdefault(target_parent, []).append(root)

        gone = set(moving)
        slots = self.data.get("EquipmentDto", {}).get("SlotsInfo")
        if isinstance(slots, list):
            slots[:] = [
                slot for slot in slots
                if not (isinstance(slot, dict) and str(slot.get("ItemId")) in gone)
            ]

        return moving

    def slot_occupant(self, host_id: str, slot_index: int) -> Optional[str]:
        """Which item is fitted in one of a host's attachment slots, or None while it is free.

        **A fitted part records its slot in `Position.I`.** Measured across a real save: all
        196 parts hanging off an item with attachment points sit at an index whose slot
        permits exactly that part, and no host carries two parts at the same index. A part
        with no `Position` at all is in slot 0 - the same default-omission rule that makes a
        missing `Index` an empty equipment slot.

        The index counts through the host template's own slot list, which is why this stays
        in the data layer while "does this part belong in that slot" is a question for the
        game data upstairs.
        """
        wanted = int(slot_index)
        for child_id in self.get_children(str(host_id)):
            position = (self.item_tree.get(child_id) or {}).get("Position")
            index = int(position.get("I") or 0) if isinstance(position, dict) else 0
            if index == wanted:
                return child_id
        return None

    def attach_item(self, item_id: str, host_id: str, slot_index: int) -> List[str]:
        """Fits an item into one of a host's attachment slots.

        Returns the ids that moved, the item first, or an empty list when refused. Attaching
        is a move plus one number: everything `move_item` carries - the subtree, the origin
        list, the equipment slot the item may be leaving - applies unchanged, and the slot is
        written as `Position.I`.

        Slot 0 is written by **removing** the key rather than storing a zero, because that is
        what the game itself writes: 108 of a real save's 196 fitted parts carry no `Position`
        at all. `BaseComponent_rotated` goes for a related reason - a slot has one orientation,
        so a part that was lying sideways in a grid must not claim to be sideways in a scope
        mount.

        Refused on top of everything `move_item` refuses when the slot is already taken by a
        different item. Whether the slot *permits* this part is decided by the caller from the
        game data; the save alone cannot answer it.
        """
        root, host = str(item_id), str(host_id)
        if isinstance(slot_index, bool) or not isinstance(slot_index, int) or slot_index < 0:
            return []
        if root not in self.item_tree or host not in self.item_tree:
            return []
        if self.is_structural(host):
            return []

        occupant = self.slot_occupant(host, slot_index)
        if occupant is not None and occupant != root:
            return []

        moved = self.move_item(root, host)
        if not moved:
            return []

        item = self.item_tree[root]
        if slot_index:
            item["Position"] = {"I": slot_index}
        else:
            item.pop("Position", None)
        inner = (item.get("AdditionalData") or {}).get("_data")
        if isinstance(inner, dict):
            inner.pop("BaseComponent_rotated", None)
        return moved

    def split_stack(
        self,
        item_id: str,
        amount: int,
        parent_id: Optional[str] = None,
        position: Optional[Tuple[int, int]] = None,
    ) -> Optional[dict]:
        """Takes `amount` units off a stack into a second stack, and returns the new item.

        A stack is one item carrying `StackableComponent_quantity`, not one item per unit,
        so splitting is arithmetic on that field plus a copy of the item to hold the part
        that left. The copy keeps everything else the original had - its size, its rotation -
        because it is the same kind of item.

        Refused unless the stack really holds more than `amount`: taking all of it is a move,
        not a split, and would leave an empty stack behind that the game has no use for.
        """
        item = self.get_item(item_id)
        if not item or not isinstance(amount, int) or amount < 1:
            return None

        inner = (item.get("AdditionalData") or {}).get("_data", {})
        quantity = inner.get("StackableComponent_quantity") if isinstance(inner, dict) else None
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            return None
        if amount >= quantity:
            return None

        clone = self.duplicate_item(item_id, parent_id=parent_id, position=position)
        if clone is None:
            return None

        clone.setdefault("AdditionalData", {}).setdefault("_data", {})[
            "StackableComponent_quantity"
        ] = amount
        inner["StackableComponent_quantity"] = quantity - amount
        return clone

    # --- Trader stock -------------------------------------------------------------
    # Shop offers live in AccountShops / AccountPricelists, outside the three item lists,
    # so none of them appear in item_tree and none of the bookkeeping above applies.

    def get_shops(self) -> List[dict]:
        shops = self.data.get("AccountShops")
        return [s for s in shops if isinstance(s, dict)] if isinstance(shops, list) else []

    def get_shop(self, shop_id: str) -> Optional[dict]:
        return next((s for s in self.get_shops() if str(s.get("Id")) == str(shop_id)), None)

    def get_shop_commodities(self, shop_id: str) -> List[dict]:
        """The trader's offer list, or [] for a shop that only buys."""
        shop = self.get_shop(shop_id)
        if not shop:
            return []
        pricelists = self.data.get("AccountPricelists")
        if not isinstance(pricelists, list):
            return []
        pricelist = next(
            (p for p in pricelists
             if isinstance(p, dict) and str(p.get("Id")) == str(shop.get("PricelistId"))),
            None,
        )
        if not pricelist:
            return []
        commodities = pricelist.get("Commodities")
        return commodities if isinstance(commodities, list) else []

    def replace_shop_commodity(
        self,
        shop_id: str,
        commodity_id: str,
        template_id: str,
        price: int,
        count: int,
        width: int | None = None,
        height: int | None = None,
    ) -> Optional[dict]:
        """Puts a different item into one of a trader's existing offer slots and returns a
        deep copy of what the slot held before, so the edit can be undone.

        Id, DataId and PositionViewPriority stay untouched: they come from the shop's preset,
        and the game rebuilds the whole Commodities list on its next stock refresh - which is
        also when this edit disappears on its own. Returns None if the slot no longer exists.
        """
        commodity = next(
            (c for c in self.get_shop_commodities(shop_id)
             if isinstance(c, dict) and str(c.get("Id")) == str(commodity_id)),
            None,
        )
        if not commodity:
            return None

        original = copy.deepcopy(commodity)

        item: Dict[str, Any] = {
            "Id": str(uuid.uuid4()),
            "ParentId": str(shop_id),  # offer items hang off the shop, not the pricelist
            "TemplateId": str(template_id),
            "IsInspected": True,
            "Position": {"I": -1, "J": -1},
        }
        if isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0:
            item["AdditionalData"] = {
                "_data": {"BaseComponent_width": width, "BaseComponent_height": height}
            }

        commodity["ItemDto"] = item
        commodity["Count"] = int(count)
        commodity["Price"] = {
            "Items": [{"ItemTemplateId": CREDITS_TEMPLATE_ID, "Count": int(price)}]
        }
        # Any attachments belonged to the item we just replaced; the container's
        # OwnerItemId would now point at an item that is no longer in the offer.
        commodity.pop("ItemsContainerDto", None)
        return original

    def restore_shop_commodity(self, shop_id: str, original: dict) -> bool:
        """Puts a saved offer slot back where it was. False means the slot is gone, which is
        what a stock refresh does - the edit is then already undone by the game itself."""
        commodities = self.get_shop_commodities(shop_id)
        for idx, commodity in enumerate(commodities):
            if isinstance(commodity, dict) and str(commodity.get("Id")) == str(original.get("Id")):
                commodities[idx] = copy.deepcopy(original)
                return True
        return False

    def save(self, backup_name: Optional[str] = None) -> Optional[Path]:
        """Writes the save file, first copying the current one aside if `backup_name` is
        given. `backup_name` is a label; the stored file gets a timestamp so backups
        accumulate instead of overwriting each other. Returns the backup path."""
        bak_path: Optional[Path] = None
        self.last_pruned = []
        if backup_name:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            bak_path = self.backup_dir / f"offline_{stamp}_{backup_name}.save"
            # Two saves in the same second would otherwise land on the same name.
            counter = 2
            while bak_path.exists():
                bak_path = self.backup_dir / f"offline_{stamp}_{backup_name}_{counter}.save"
                counter += 1
            shutil.copyfile(self.save_path, bak_path)
            # Prune after the copy, so a failure here cannot cost the caller their backup.
            self.last_pruned = prune_backups(
                self.backup_dir, self.backup_keep, protect=bak_path
            )

        # Written to a sibling file and swapped in with os.replace, so a failure mid-write
        # - full disk, crash, a cloud sync grabbing the file - cannot leave a truncated
        # save behind: the original stays untouched until the swap, and the swap is atomic.
        # The name ends in neither `.save` nor the backup shape, so no glob here or in the
        # gitignore can mistake the leftover of a failed write for a save or a backup.
        tmp_path = self.save_path.with_name(f"{self.save_path.name}.tmp-{os.getpid()}")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.save_path)
        except BaseException:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise

        return bak_path

    def reload_from_disk(self) -> None:
        self._load_data()

    def get_mail_count(self) -> int:
        mailbox = self.data.get("MailboxDto")
        if isinstance(mailbox, dict):
            letters = mailbox.get("Letters", [])
            return len(letters) if isinstance(letters, list) else 0
        return 0

    def get_mail_items(self) -> List[dict]:
        mailbox = self.data.get("MailboxDto")
        if isinstance(mailbox, dict):
            return mailbox.get("Letters", [])
        return []
