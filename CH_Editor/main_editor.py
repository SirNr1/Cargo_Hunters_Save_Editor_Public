# Cleaned Import
import sys
import os
from core_utils import (
    SaveDataManager,
    build_entries,
    describe_entry,
    repair_item_logic,
)

def main():
    # Robust pathing to ensure the save is found no matter where you run the script from
    base_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(base_dir, "..", "Scripts", "offline.save")

    if not os.path.exists(save_path):
        # Fallop for different directory depths
        save_path = os.path.join(base_dir, "Scripts", "offline.save")

    manager = SaveDataManager(save_path)

    while True:
        print("\n" + "="*40)
        print("   CARGO HUNTERS SAVE EDITOR")
        print("="*40)
        print("1. Manage Inventory (Backpack & Home)")
        print("2. Manage Mailbox")
        print("3. Exit")

        choice = input("\nSelect an option: ")

        if choice == "1":
            manage_inventory(manager)
        elif choice == "2":
            manage_mailbox(manager)
        elif choice == "3":
            print("Exiting...")
            sys.exit()
        else:
            print("Invalid option. Please enter 1, 2, or 3.")

def manage_inventory(manager):
    while True:
        print("\n--- Inventory Management ---")
        print("1. Character Equipment (Backpack & Gear)")
        print("                (Items on your person/slots)")
        print("2. Home/Shelter Inventory (Storage)")
        print("                (Items in containers/shelter)")
        print("3. Search/Filter All Items")
        print("4. Back to main menu")

        scope_choice = input("\nSelect a scope: ")

        if scope_choice == "1":
            browse_container(manager, "Character Equipment", manager.get_character_items())
        elif scope_choice == "2":
            browse_home(manager)
        elif scope_choice == "3":
            search_and_action(manager)
        elif scope_choice == "4":
            break
        else:
            print("Invalid option.")

def perform_item_actions(item, manager):
    while True:
        print("\n--- Item Actions ---")
        print("1. Repair Item")
        print("2. Duplicate Item")
        print("3. Back")
        choice = input("\nAction: ")
        if choice == "1":
            # No mapping data here, so repair falls back to the item's own ceiling and
            # may not be able to determine a target at all.
            if repair_item_logic(item):
                manager.save(backup_name="manual_repair")
                print("Success: Item repaired.")
            else:
                print("Nothing to repair on this item.")
        elif choice == "2":
            manager.duplicate_item(item.get("Id"))
            manager.save(backup_name="manual_duplicate")
            print("Success: Item duplicated.")
        elif choice == "3":
            break
        else:
            print("Invalid option.")

def handle_entry_actions(manager, members):
    if len(members) == 1:
        perform_item_actions(manager.get_item(members[0]), manager)
        return

    print(f"\nThis is a stack of {len(members)} identical items.")
    choice = input(f"Enter index (0-{len(members)-1}) to act on one, or press Enter to cancel: ")
    if choice.isdigit() and int(choice) < len(members):
        perform_item_actions(manager.get_item(members[int(choice)]), manager)

def browse_home(manager):
    while True:
        tabs = manager.get_inventory_tabs()

        print("\n--- Home/Shelter Inventory ---")
        for idx in range(len(tabs)):
            print(f"  {idx + 1}. Tab {idx + 1}")
        shelter_choice = len(tabs) + 1
        print(f"  {shelter_choice}. Shelter")
        print("  0. Back")

        choice = input("\nSelect: ")

        if choice == "0":
            return
        if not choice.isdigit():
            print("Invalid option.")
            continue

        n = int(choice)
        if 1 <= n <= len(tabs):
            tab_id = tabs[n - 1]
            browse_container(manager, f"Tab {n}", manager.get_children(tab_id))
        elif n == shelter_choice:
            browse_container(manager, "Shelter", manager.get_shelter_items())
        else:
            print("Invalid option.")

def browse_container(manager, title, start_ids):
    nav_stack = []
    current_label = title
    current_ids = start_ids

    while True:
        entries = build_entries(manager, current_ids)

        print(f"\n--- {current_label} ---")
        if not entries:
            print("(empty)")
        for idx, members in enumerate(entries):
            label, note = describe_entry(manager, members)
            print(f"  {idx + 1}. {label} {note}".rstrip())
        print("  0. Back")

        choice = input("\nSelect an entry: ")

        if choice == "0":
            if nav_stack:
                current_label, current_ids = nav_stack.pop()
                continue
            return

        if not choice.isdigit() or not (1 <= int(choice) <= len(entries)):
            print("Invalid option.")
            continue

        members = entries[int(choice) - 1]
        children = manager.get_children(members[0]) if len(members) == 1 else []

        if children:
            sub = input("1. View contents  2. Item actions  3. Cancel: ")
            if sub == "1":
                label, _ = describe_entry(manager, members)
                nav_stack.append((current_label, current_ids))
                current_label = f"{label} contents"
                current_ids = children
            elif sub == "2":
                handle_entry_actions(manager, members)
        else:
            handle_entry_actions(manager, members)

def manage_mailbox(manager):
    count = manager.get_mail_count()
    print("\n--- Mailbox ---")
    print(f"Items: {count}")
    mails = manager.get_mail_items()
    if mails:
        for i, m in enumerate(mails):
            print(f"{i}. ID: {m.get('Id')}")
        choice = input("\nEnter index to delete (or 'b'): ")
        # Ueber den Manager, nicht an der Liste vorbei: `get_mail_items` gibt die echte Liste
        # des Saves heraus, ein `pop` darauf aendert es also schon, und das Zurueckschreiben
        # danach tat nie etwas. `delete_mail` lehnt ausserdem einen Index ab, den es nicht
        # gibt, statt `pop(-1)` den letzten Brief nehmen zu lassen.
        if choice.isdigit() and manager.delete_mail(int(choice)):
            manager.save(backup_name="mail_delete")
            print("Success.")
    input("\nPress Enter to continue...")

def search_and_action(manager):
    all_items = manager.get_all_items_flat()
    query = input("Enter filter (ID, part of type, or any key word): ").lower()
    filtered = [i for i in all_items if query in str(i.get('Id')).lower() or query in str(i.get('TemplateId', '')).lower()]
    print(f"Found {len(filtered)} results:")
    for i, item in enumerate(filtered):
        print(f"{i}. ID: {item.get('Id')} | Type: {item.get('TemplateId')}")
    idx = input("\nEnter the index of the result to select (or press Enter to skip): ")
    if idx.isdigit() and int(idx) < len(filtered):
        selected = filtered[int(idx)]
        perform_item_actions(selected, manager)
    else:
        print("Selection cancelled.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit.")
