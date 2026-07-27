import json
import copy
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


# The in-game currency ("credits"), used as ItemTemplateId in every shop price.
CREDITS_TEMPLATE_ID = "cb567810-cc82-424f-893f-299c704ffb12"


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


class SaveDataManager:
    def __init__(self, save_path: str, backup_dir: Optional[str] = None):
        self.save_path = Path(save_path)
        self.backup_dir = (
            Path(backup_dir).resolve()
            if backup_dir
            else default_backup_dir()
        )
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
        """Ids of the top-level tab containers in the main warehouse (InventoryDto), in tab order."""
        root = self.section_roots.get("InventoryDto")
        if not root:
            return []
        tab_ids = [
            s_id for s_id, item in self.item_tree.items()
            if self.item_origin.get(s_id) == "InventoryDto" and str(item.get("ParentId")) == root
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

    def next_position_for_parent(self, parent_id: str) -> int:
        used: List[int] = []
        for child_id in self.get_children(parent_id):
            item = self.get_item(child_id)
            if not item:
                continue
            pos = item.get("Position")
            if isinstance(pos, dict):
                j = pos.get("J")
                if isinstance(j, int):
                    used.append(j)
        return max(used) + 1 if used else 0

    def add_inventory_item(
        self,
        parent_id: str,
        template_id: str,
        width: int | None = None,
        height: int | None = None,
        quantity: int | None = None,
    ) -> dict:
        """Creates one item. `quantity` makes it a stack of that many units, which is how
        the game stores stackables: a single item carrying StackableComponent_quantity,
        not one item per unit. Keep it within the template's StackCapacity."""
        item: dict = {
            "Id": str(uuid.uuid4()),
            "TemplateId": str(template_id),
            "ParentId": str(parent_id),
            "IsInspected": True,
            "Position": {"J": self.next_position_for_parent(parent_id)},
        }

        inner: Dict[str, Any] = {}
        if isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0:
            inner["BaseComponent_width"] = width
            inner["BaseComponent_height"] = height
        if isinstance(quantity, int) and quantity > 0:
            inner["StackableComponent_quantity"] = quantity
        if inner:
            item["AdditionalData"] = {"_data": inner}

        target_list = self._inventory_origin_list()
        target_list.append(item)

        item_id = str(item["Id"])
        self.item_tree[item_id] = item
        self.item_origin[item_id] = "InventoryDto"
        self.children_map.setdefault(str(parent_id), []).append(item_id)
        return item

    def duplicate_item(self, item_id: str) -> Optional[dict]:
        """Clones an item into the same container list it came from, next to its original."""
        item = self.get_item(item_id)
        origin = self.item_origin.get(str(item_id))
        if not item or not origin:
            return None

        clone = copy.deepcopy(item)
        clone["Id"] = str(uuid.uuid4())

        if origin == "EquipmentDto":
            target_list = self.data.setdefault("EquipmentDto", {}).setdefault("Items", [])
        elif origin == "ShelterItemDto":
            target_list = self.data.setdefault("ShelterItemDto", {}).setdefault("Container", {}).setdefault("Items", [])
        else:
            target_list = self.data.setdefault("InventoryDto", {}).setdefault("ItemsContainerDto", {}).setdefault("Items", [])
        target_list.append(clone)

        c_id = str(clone["Id"])
        self.item_tree[c_id] = clone
        self.item_origin[c_id] = origin
        p_id = clone.get("ParentId")
        if p_id:
            self.children_map.setdefault(str(p_id), []).append(c_id)

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

        with self.save_path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

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
