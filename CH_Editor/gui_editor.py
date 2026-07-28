import argparse
import json
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from core_utils import (
    BACKUP_KEEP_DEFAULT,
    SaveDataManager,
    container_cells,
    find_placement,
)
from main_editor import build_entries, describe_entry, repair_item_logic

STEAM_APP_ID = "4197990"

# Pixel width the Hackerman warning text wraps at; keeps the banner narrow and tall
# regardless of how long the translated strings are.
WARNING_WRAPLENGTH = 280


def get_system_language() -> str:
    lang = "en"
    try:
        import locale
        loc = None
        try:
            loc = locale.getlocale()[0]
        except Exception:
            pass
        if not loc:
            try:
                loc = locale.getdefaultlocale()[0]
            except Exception:
                pass
        if loc:
            loc = loc.lower()
            if "de" in loc:
                lang = "de"
            elif "ru" in loc:
                lang = "ru"
    except Exception:
        pass

    if lang == "en":
        import os
        for var in ["LANG", "LC_ALL", "LC_MESSAGES"]:
            val = os.environ.get(var)
            if val:
                val = val.lower()
                if val.startswith("de"):
                    lang = "de"
                    break
                elif val.startswith("ru"):
                    lang = "ru"
                    break
    return lang


def get_config_path() -> Path:
    try:
        config_dir = Path.home() / ".config" / "cargo_hunters_save_editor"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"
    except Exception:
        return Path(__file__).resolve().parent / "config.json"


def load_config_lang() -> str:
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                lang = data.get("language")
                if lang in TRANSLATIONS:
                    return lang
        except Exception:
            pass
    return get_system_language()


def save_config_lang(lang: str) -> None:
    path = get_config_path()
    try:
        data = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["language"] = lang
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass


def load_config_backup_keep() -> int:
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                keep = json.load(f).get("backup_keep")
            if isinstance(keep, int) and keep >= 0:
                return keep
        except Exception:
            pass
    return BACKUP_KEEP_DEFAULT


def save_config_backup_keep(keep: int) -> None:
    path = get_config_path()
    try:
        data = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["backup_keep"] = int(keep)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass


TRANSLATIONS = {
    "en": {
        "title": "★ Cargo Hunters Save Editor ★",
        "active_session": "[Active Session]",
        "tab_inventory": "Inventory",
        "tab_mailbox": "Mailbox",
        "tab_catalog": "Game Items",
        "tab_hackerman": "☢ Hackerman's Lab ☢",
        "tab_help": "Help / How to Use",
        "btn_refresh": "🔄 Refresh Names from Game",
        "btn_apply": "Apply Changes",
        "btn_discard": "Discard Changes",
        "lbl_scope": "Scope:",
        "lbl_search": "Search:",
        "btn_search": "Search",
        "btn_delete_mail": "Delete selected letter",
        "lbl_category": "Category:",
        "lbl_subcategory": "SubCategory:",
        "ctx_add_to_inv": "Add to Inventory",
        "lbl_warn_title": "☠ WARNING: HACKERMAN'S DANGER ZONE ☠",
        "lbl_warn_desc": "Manipulating character stats, skills, or traders can completely corrupt (brick) your save file!\nUse these features at your own risk.",
        "lf_profile": " Profile Details ",
        "lbl_nickname": "Nickname:",
        "lbl_level": "Level:",
        "lbl_xp": "Experience Points:",
        "lf_cheats": " One-Click Cheats ",
        "btn_cheat_max": "⚡ Max Out All Skills",
        "btn_cheat_fill": "💰 Fill Trader Balances",
        "btn_cheat_repair": "🔧 Repair All Items",
        "lbl_selected_skill": "Selected Skill Level:",
        "btn_set_skill": "Set Level",
        "lbl_selected_trader": "Selected Trader Level:",
        "btn_set_trader": "Set Stats",
        "col_skill_id": "Skill ID",
        "col_skill_name": "Skill Name",
        "col_skill_level": "Level",
        "col_trader_name": "Trader Name",
        "col_trader_level": "Trader Level",
        "col_trader_balance": "Balance (Credits)",
        "col_trader_instance_id": "Trader Instance ID",
        "col_trader_type_id": "Trader Type ID",
        "msg_discard_title": "Discard changes",
        "msg_discard_text": "Discard all unsaved edits?",
        "msg_success_title": "Success",
        "msg_save_success": "Save file successfully updated.",
        "msg_refresh_success": "Mapping refreshed successfully.",
        "msg_refresh_failed": "Mapping refresh failed.",
        "msg_refresh_empty": "Game folder path is empty.",
        "msg_refresh_prompt": "Refresh mappings from game assets?\nThis requires UnityPy and path to Cargo Hunters game folder.",
        "msg_no_item_selected": "No item selected.",
        "msg_item_spawned": "Successfully spawned {name} into {scope}.",
        "msg_spawn_failed": "Could not spawn item: {error}",
        "btn_mute": "🔇 Mute",
        "btn_unmute": "🔊 Unmute",
        "status_welcome": "Welcome to Cargo Hunters Save Editor",
        "status_ready": "Ready",
        "status_pending_changes": "Pending changes: {desc}",
        "status_no_pending": "No pending changes",
        "status_refreshed": "Mapping refreshed from: {path}",
        "ctx_repair": "Repair Item",
        "ctx_duplicate": "Duplicate Item",
        "ctx_delete": "Delete Item",
        "tab_skills": "Skills",
        "tab_trader_balances": "Trader Balances",
        "lbl_balance": "Balance:",
        "pending_label": "PENDING CHANGES | ",
        "names_status": " | Names: {total_names} loaded ({alias_names} manual aliases)",
        "col_mail_index": "#",
        "col_mail_sender": "Sender",
        "col_mail_subject": "Message",
        "col_mail_rewards": "Rewards",
        "col_mail_read": "Read",
        "col_mail_id": "Letter ID",
        "col_cat_name": "Name",
        "col_cat_template_id": "TemplateId",
        "col_cat_category": "Category",
        "col_cat_subcategory": "SubCategory",
        "col_cat_size": "Size",
        "col_cat_stack": "Stack",
        "all_categories": "All",
        "scope_equipment": "Character Equipment",
        "scope_tab": "Tab {idx}",
        "scope_shelter": "Shelter",
        "msg_cheats_repair": "Success! Repaired all {count} items to 100%!",
        "msg_cheats_skills": "Success! Raised {count} skills, each to its own maximum level!",
        "msg_cheats_traders": "Success! Credited 1,000,000 to {count} traders!",
        "status_cheat_repaired": "Repaired all {count} repairable items in save",
        "status_cheat_maxed_skills": "Maxed out all skill levels",
        "status_cheat_filled_traders": "Filled all trader balances to 1,000,000",
        "status_skill_set": "Set skill {skill_id} level to {level}",
        "status_trader_set": "Set trader stats level={level} balance={balance}",
        "status_mail_deleted": "Deleted letter index {index}",
        "msg_mapping_updated": "Name mapping updated.\nKnown names: {old_count} -> {new_count}{details}",
        "msg_err_game_folder_not_found": "Game folder not found:\n{game_dir}",
        "msg_prompt_game_folder": "Path to Cargo Hunters game folder:",
        "msg_game_folder_title": "Game folder",
        "msg_discard_confirm": "Discard all unsaved changes since last apply?",
        "msg_reload_failed": "Failed to reload save from disk:\n{exc}",
        "msg_unsaved_changes_title": "Unsaved changes",
        "msg_unsaved_changes_prompt": "You have unsaved changes.\n\nYes: Apply changes and exit\nNo: Discard changes and exit\nCancel: keep editor open",
        "status_changes_applied": "Changes applied to save file",
        "status_changes_applied_backup": "Changes applied. Backup: backups\\{name}",
        "status_changes_applied_backup_pruned": "Changes applied. Backup: backups\\{name} ({count} older backups removed)",
        "backups_keep_label": "Keep backups:",
        "backups_keep_hint": "How many timestamped backups to keep in the backups folder. 0 keeps all of them.",
        "status_changes_discarded": "Unsaved changes discarded",
        "msg_err_save_not_found": "--save-path does not exist:\n{candidate}",
        "msg_title_save_not_found": "Save file not found",
        "msg_multiple_saves_title": "Multiple save files found",
        "msg_multiple_saves_prompt": "Found {count} candidate save files.\n\nUse newest automatically?\n{newest}\n\nYes = use this file\nNo = choose manually",
        "msg_load_save_failed_title": "Failed to load save file",
        "msg_select_save_title": "Select Cargo Hunters offline.save",
        "col_mail_count": "Letters: {count}",
        "status_scope_info": "Scope: {scope} | Save: {path}",
        "status_refreshing": "Refreshing names from game assets... this may take a moment",
        "status_catalog_added": "Added {added} catalog item(s) (not saved yet)",
        "status_item_edited": "Edited item {item_id} (not saved yet)",
        "status_skill_edited": "Edited skill {skill_id} (not saved yet)",
        "status_duplicated": "Duplicated {mode}: created {count}{failure}",
        "mode_stack_items": "stack items",
        "mode_item_copies": "item copies",
        "status_mail_deleted_pending": "Deleted one mailbox letter (not saved yet)",
        "scope_char_eq": "Character Equipment",
        "msg_catalog_row_invalid": "Selected catalog row is invalid.",
        "msg_no_template_id": "Selected row has no TemplateId.",
        "msg_add_item_title": "Add item",
        "msg_add_item_prompt": "How many copies should be added?",
        "msg_add_stack_prompt": "How many units should be added?\nOne stack holds {capacity}; larger amounts are split into several stacks.",
        "msg_no_inv_tab_found": "No inventory tab found for insertion.",
        "ctx_offer_at_trader": "Offer at Trader...",
        "shop_offer_title": "Offer at trader",
        "shop_offer_intro": "Puts {name} into one of the trader's existing offer slots.\nThe trader's next stock refresh undoes this by itself.",
        "shop_offer_trader": "Trader:",
        "shop_offer_slot": "Offer slot to overwrite:",
        "shop_offer_price": "Price (credits):",
        "shop_offer_count": "Amount for sale:",
        "btn_shop_offer_confirm": "Overwrite offer",
        "btn_shop_offer_restore": "Undo ({count})",
        "msg_shop_no_offers": "No trader in this save has an offer list that could be edited.",
        "msg_shop_slot_needed": "Select the offer slot that should be overwritten.",
        "msg_shop_bad_numbers": "Price and amount must be whole numbers above zero.",
        "msg_shop_slot_gone": "That offer slot is no longer in the save.",
        "msg_shop_restore_none": "Nothing to undo.",
        "status_shop_offer_set": "{trader} now offers {name} x{count} for {price} (not saved yet)",
        "status_shop_offer_restored": "Undid {restored} offer slot(s); {gone} were already gone through a stock refresh (not saved yet)",
        "msg_no_selection_title": "No selection",
        "msg_row_no_item_data": "Selected tree row has no item data.",
        "msg_item_not_found": "Item not found: {item_id}",
        "msg_duplicate_failed": "Failed to duplicate selection.{failed_hint}",
        "msg_delete_title": "Delete item",
        "msg_delete_confirm": "Delete this item?",
        "msg_delete_confirm_many": "Delete these {count} items? This one row stands for all of them.",
        "msg_delete_attachments": "{count} attached item(s) will be deleted with it.",
        "msg_delete_equipped": "It sits in an equipment slot. The slot will be left empty.",
        "msg_delete_revert_hint": "Discard Changes still undoes this until you apply.",
        "msg_delete_structural": "This row is a storage container of the save itself, not an item, and cannot be deleted.",
        "status_items_deleted": "Deleted {count} item(s) (not saved yet)",
        "msg_search_empty": "Please enter a search query.",
        "msg_skill_level_range": "Invalid level. This skill goes from 0 to {max_level}.",
        "msg_trader_level_range": "Invalid level. A trader goes from {min_level} to {max_level}.",
        "btn_level_max": "MAX",
        "lbl_skill_points": "Unspent skill points:",
        "tab_counters": "Counters",
        "col_counter_group": "Group",
        "col_counter_stat": "Statistic",
        "col_counter_value": "Value",
        "col_counter_updated": "Last set (UTC)",
        "counters_sessions": "Sessions",
        "counters_last_run": "Last run",
        "counters_lifetime": "Lifetime",
        "counters_hint": "Read-only: the account's own tally, kept by the game. Nothing here is written back.",
        "counters_empty": "This save carries no counters.",
        "msg_select_search_result": "Select a search result first.",
        "msg_select_letter": "Please select a letter first.",
        "msg_err_resolve_letter": "Could not resolve selected letter index.",
        "msg_err_letter_out_of_range": "Selected letter is out of range.",
        "msg_err_save_failed": "Failed to save changes:\n{exc}",
        "search_results_title": "Search Results ({count})",
        "search_found_count": "Found {count} matching items",
        "col_id": "Id",
        "col_condition": "Condition",
        "btn_ok": "OK",
        "btn_cancel": "Cancel",
        "msg_place_prompt": "Where should it go?",
        "msg_place_hint": "A free spot is searched for in the container you pick. The item is "
                          "turned 90° only if it fits no other way.",
        "msg_place_no_targets": "No container with a known grid was found. Use Refresh Names "
                                "from Game so the editor knows how big the containers are.",
        "msg_place_no_space": "No free space in {target} for this item ({width}x{height}).",
        "msg_place_partial": "Only {placed} of {wanted} fitted; {target} then had no room "
                             "left.",
        "target_same_container": "Same container as the original",
        "target_inbox": "Inbox - collect it in the game yourself",
        "msg_place_inbox_hint": "Inbox: the item is stored without a grid position. The game "
                                "cannot place it, so it hands it to you as mail - which is "
                                "where anything without room ends up anyway. Pick this when "
                                "the containers are full or you want to sort it yourself.",
        "target_tab": "Tab {idx} - {free} of {total} cells free",
        "target_carried": "{name} (carried) - {free} of {total} cells free",
        "target_container": "Container",
        "btn_close": "Close"
    },
    "de": {
        "title": "★ Cargo Hunters Save Editor ★",
        "active_session": "[Aktive Sitzung]",
        "tab_inventory": "Inventar",
        "tab_mailbox": "Mailbox",
        "tab_catalog": "Gegenstände",
        "tab_hackerman": "☢ Hackermans Labor ☢",
        "tab_help": "Hilfe / Anleitung",
        "btn_refresh": "🔄 Spielnamen aktualisieren",
        "btn_apply": "Änderungen übernehmen",
        "btn_discard": "Änderungen verwerfen",
        "lbl_scope": "Bereich:",
        "lbl_search": "Suche:",
        "btn_search": "Suchen",
        "btn_delete_mail": "Ausgewählten Brief löschen",
        "lbl_category": "Kategorie:",
        "lbl_subcategory": "Unterkategorie:",
        "ctx_add_to_inv": "Ins Inventar spawnen",
        "lbl_warn_title": "☠ WARNUNG: HACKERMANS GEFAHRENZONE ☠",
        "lbl_warn_desc": "Das Manipulieren von Charakterwerten, Skills oder Händlern kann deinen Spielstand komplett zerschießen (bricken)!\nNutze diese Funktionen auf eigene Gefahr.",
        "lf_profile": " Profildetails ",
        "lbl_nickname": "Nickname:",
        "lbl_level": "Level:",
        "lbl_xp": "Erfahrungspunkte:",
        "lf_cheats": " One-Click Cheats ",
        "btn_cheat_max": "⚡ Alle Skills maximieren",
        "btn_cheat_fill": "💰 Händlerguthaben auffüllen",
        "btn_cheat_repair": "🔧 Alle Gegenstände reparieren",
        "lbl_selected_skill": "Gewähltes Skill-Level:",
        "btn_set_skill": "Level setzen",
        "lbl_selected_trader": "Gewähltes Händler-Level:",
        "btn_set_trader": "Werte setzen",
        "col_skill_id": "Skill-ID",
        "col_skill_name": "Skill-Name",
        "col_skill_level": "Level",
        "col_trader_name": "Händlername",
        "col_trader_level": "Händlerlevel",
        "col_trader_balance": "Guthaben (Credits)",
        "col_trader_instance_id": "Händler-Instanz-ID",
        "col_trader_type_id": "Händler-Typ-ID",
        "msg_discard_title": "Änderungen verwerfen",
        "msg_discard_text": "Alle ungespeicherten Änderungen verwerfen?",
        "msg_success_title": "Erfolg",
        "msg_save_success": "Spielstand erfolgreich aktualisiert.",
        "msg_refresh_success": "Datenmapping erfolgreich aktualisiert.",
        "msg_refresh_failed": "Aktualisierung des Datenmappings fehlgeschlagen.",
        "msg_refresh_empty": "Pfad zum Spielverzeichnis ist leer.",
        "msg_refresh_prompt": "Datenmapping aus den Spieldateien aktualisieren?\nDies erfordert UnityPy und den Pfad zum Cargo Hunters Spielverzeichnis.",
        "msg_no_item_selected": "Kein Gegenstand ausgewählt.",
        "msg_item_spawned": "Erfolgreich {name} in {scope} gespawnt.",
        "msg_spawn_failed": "Gegenstand konnte nicht gespawnt werden: {error}",
        "btn_mute": "🔇 Stumm",
        "btn_unmute": "🔊 Ton an",
        "status_welcome": "Willkommen im Cargo Hunters Save Editor",
        "status_ready": "Bereit",
        "status_pending_changes": "Ausstehende Änderungen: {desc}",
        "status_no_pending": "Keine ausstehenden Änderungen",
        "status_refreshed": "Datenmapping aktualisiert von: {path}",
        "ctx_repair": "Gegenstand reparieren",
        "ctx_duplicate": "Gegenstand duplizieren",
        "ctx_delete": "Gegenstand löschen",
        "tab_skills": "Skills",
        "tab_trader_balances": "Händlerguthaben",
        "lbl_balance": "Guthaben:",
        "pending_label": "AUSSTEHENDE ÄNDERUNGEN | ",
        "names_status": " | Namen: {total_names} geladen ({alias_names} manuelle Aliase)",
        "col_mail_index": "#",
        "col_mail_sender": "Absender",
        "col_mail_subject": "Brief",
        "col_mail_rewards": "Belohnungen",
        "col_mail_read": "Gelesen",
        "col_mail_id": "Brief-ID",
        "col_cat_name": "Name",
        "col_cat_template_id": "TemplateId",
        "col_cat_category": "Kategorie",
        "col_cat_subcategory": "Unterkategorie",
        "col_cat_size": "Größe",
        "col_cat_stack": "Stapel",
        "all_categories": "Alle",
        "scope_equipment": "Charakter-Ausrüstung",
        "scope_tab": "Reiter {idx}",
        "scope_shelter": "Lager",
        "msg_cheats_repair": "Erfolg! Alle {count} Gegenstände auf 100% repariert!",
        "msg_cheats_skills": "Erfolg! {count} Skills auf ihr jeweiliges Maximum gesetzt!",
        "msg_cheats_traders": "Erfolg! 1.000.000 Credits an {count} Händler übertragen!",
        "status_cheat_repaired": "Alle {count} reparierbaren Gegenstände im Spielstand repariert",
        "status_cheat_maxed_skills": "Alle Skill-Level maximiert",
        "status_cheat_filled_traders": "Alle Händlerguthaben auf 1.000.000 aufgefüllt",
        "status_skill_set": "Skill {skill_id} Level auf {level} gesetzt",
        "status_trader_set": "Händlerwerte gesetzt: Level={level} Guthaben={balance}",
        "status_mail_deleted": "Brief an Index {index} gelöscht",
        "msg_mapping_updated": "Datenmapping aktualisiert.\nBekannte Namen: {old_count} -> {new_count}{details}",
        "msg_err_game_folder_not_found": "Spielverzeichnis nicht gefunden:\n{game_dir}",
        "msg_prompt_game_folder": "Pfad zum Cargo Hunters Spielverzeichnis:",
        "msg_game_folder_title": "Spielverzeichnis",
        "msg_discard_confirm": "Alle ungespeicherten Änderungen seit dem letzten Speichern verwerfen?",
        "msg_reload_failed": "Laden des Spielstands von Festplatte fehlgeschlagen:\n{exc}",
        "msg_unsaved_changes_title": "Ungespeicherte Änderungen",
        "msg_unsaved_changes_prompt": "Du hast ungespeicherte Änderungen.\n\nJa: Änderungen speichern und beenden\nNein: Änderungen verwerfen und beenden\nAbbrechen: Editor geöffnet lassen",
        "status_changes_applied": "Änderungen am Spielstand angewendet",
        "status_changes_applied_backup": "Änderungen angewendet. Backup: backups\\{name}",
        "status_changes_applied_backup_pruned": "Änderungen angewendet. Backup: backups\\{name} ({count} ältere Backups entfernt)",
        "backups_keep_label": "Backups behalten:",
        "backups_keep_hint": "Wie viele Backups im Ordner backups aufbewahrt werden. 0 behält alle.",
        "status_changes_discarded": "Ungespeicherte Änderungen verworfen",
        "msg_err_save_not_found": "--save-path existiert nicht:\n{candidate}",
        "msg_title_save_not_found": "Spielstand nicht gefunden",
        "msg_multiple_saves_title": "Mehrere Spielstände gefunden",
        "msg_multiple_saves_prompt": "Es wurden {count} mögliche Spielstände gefunden.\n\nAutomatisch den neuesten verwenden?\n{newest}\n\nJa = diese Datei verwenden\nNein = manuell auswählen",
        "msg_load_save_failed_title": "Laden des Spielstands fehlgeschlagen",
        "msg_select_save_title": "Wähle Cargo Hunters offline.save",
        "col_mail_count": "Briefe: {count}",
        "status_scope_info": "Bereich: {scope} | Spielstand: {path}",
        "status_refreshing": "Spielnamen werden aus den Spieldateien aktualisiert... dies kann einen Moment dauern",
        "status_catalog_added": "Katalog-Gegenstand/Gegenstände hinzugefügt: {added} (noch nicht gespeichert)",
        "status_item_edited": "Gegenstand {item_id} bearbeitet (noch nicht gespeichert)",
        "status_skill_edited": "Skill {skill_id} bearbeitet (noch nicht gespeichert)",
        "status_duplicated": "Dupliziert ({mode}): {count} erstellt{failure}",
        "mode_stack_items": "Stapel-Gegenstände",
        "mode_item_copies": "Gegenstands-Kopien",
        "status_mail_deleted_pending": "Ein Brief gelöscht (noch nicht gespeichert)",
        "scope_char_eq": "Charakter-Ausrüstung",
        "msg_catalog_row_invalid": "Ausgewählte Katalogzeile ist ungültig.",
        "msg_no_template_id": "Ausgewählte Zeile hat keine TemplateId.",
        "msg_add_item_title": "Gegenstand hinzufügen",
        "msg_add_item_prompt": "Wie viele Kopien sollen hinzugefügt werden?",
        "msg_add_stack_prompt": "Wie viele Einheiten sollen hinzugefügt werden?\nEin Stapel fasst {capacity}; größere Mengen werden auf mehrere Stapel verteilt.",
        "msg_no_inv_tab_found": "Kein Inventar-Reiter für das Einfügen gefunden.",
        "ctx_offer_at_trader": "Beim Händler anbieten...",
        "shop_offer_title": "Beim Händler anbieten",
        "shop_offer_intro": "Legt {name} in einen bestehenden Angebots-Slot des Händlers.\nDas nächste Sortiments-Update des Händlers macht das von selbst rückgängig.",
        "shop_offer_trader": "Händler:",
        "shop_offer_slot": "Zu überschreibender Angebots-Slot:",
        "shop_offer_price": "Preis (Credits):",
        "shop_offer_count": "Verkaufsmenge:",
        "btn_shop_offer_confirm": "Angebot überschreiben",
        "btn_shop_offer_restore": "Rückgängig ({count})",
        "msg_shop_no_offers": "Kein Händler in diesem Save hat eine bearbeitbare Angebotsliste.",
        "msg_shop_slot_needed": "Bitte den Angebots-Slot auswählen, der überschrieben werden soll.",
        "msg_shop_bad_numbers": "Preis und Menge müssen ganze Zahlen größer als null sein.",
        "msg_shop_slot_gone": "Dieser Angebots-Slot ist nicht mehr im Save vorhanden.",
        "msg_shop_restore_none": "Es gibt nichts rückgängig zu machen.",
        "status_shop_offer_set": "{trader} bietet jetzt {name} x{count} für {price} an (noch nicht gespeichert)",
        "status_shop_offer_restored": "{restored} Angebots-Slot(s) zurückgesetzt; {gone} waren durch ein Sortiments-Update schon weg (noch nicht gespeichert)",
        "msg_no_selection_title": "Keine Auswahl",
        "msg_row_no_item_data": "Ausgewählte Zeile hat keine Gegenstandsdaten.",
        "msg_item_not_found": "Gegenstand nicht gefunden: {item_id}",
        "msg_duplicate_failed": "Duplizieren der Auswahl fehlgeschlagen.{failed_hint}",
        "msg_delete_title": "Gegenstand löschen",
        "msg_delete_confirm": "Diesen Gegenstand löschen?",
        "msg_delete_confirm_many": "Diese {count} Gegenstände löschen? Die eine Zeile steht für alle davon.",
        "msg_delete_attachments": "{count} angebaute Gegenstände werden mit gelöscht.",
        "msg_delete_equipped": "Er steckt in einem Ausrüstungsslot. Der Slot bleibt danach leer.",
        "msg_delete_revert_hint": "Bis zum Anwenden macht Änderungen verwerfen das wieder rückgängig.",
        "msg_delete_structural": "Diese Zeile ist ein Lagerbehälter des Saves selbst und kein Gegenstand. Sie lässt sich nicht löschen.",
        "status_items_deleted": "{count} Gegenstand/Gegenstände gelöscht (noch nicht gespeichert)",
        "msg_search_empty": "Bitte geben Sie einen Suchbegriff ein.",
        "msg_skill_level_range": "Ungültige Stufe. Dieser Skill geht von 0 bis {max_level}.",
        "msg_trader_level_range": "Ungültige Stufe. Ein Händler geht von {min_level} bis {max_level}.",
        "btn_level_max": "MAX",
        "lbl_skill_points": "Freie Skillpunkte:",
        "tab_counters": "Statistik",
        "col_counter_group": "Gruppe",
        "col_counter_stat": "Wert",
        "col_counter_value": "Zahl",
        "col_counter_updated": "Zuletzt (UTC)",
        "counters_sessions": "Sitzungen",
        "counters_last_run": "Letzte Runde",
        "counters_lifetime": "Gesamt",
        "counters_hint": "Nur zur Ansicht: die Zähler des Spiels. Hier wird nichts zurückgeschrieben.",
        "counters_empty": "Dieser Spielstand enthält keine Zähler.",
        "msg_select_search_result": "Bitte wählen Sie zuerst ein Suchergebnis aus.",
        "msg_select_letter": "Bitte wählen Sie zuerst einen Brief aus.",
        "msg_err_resolve_letter": "Index des ausgewählten Briefs konnte nicht aufgelöst werden.",
        "msg_err_letter_out_of_range": "Ausgewählter Brief liegt außerhalb des Bereichs.",
        "msg_err_save_failed": "Änderungen konnten nicht gespeichert werden:\n{exc}",
        "search_results_title": "Suchergebnisse ({count})",
        "search_found_count": "Es wurden {count} übereinstimmende Gegenstände gefunden",
        "col_id": "Id",
        "col_condition": "Zustand",
        "btn_ok": "OK",
        "btn_cancel": "Abbrechen",
        "msg_place_prompt": "Wohin soll es?",
        "msg_place_hint": "Im gewählten Behälter wird ein freier Platz gesucht. Gedreht wird "
                          "der Gegenstand nur, wenn er sonst nicht passt.",
        "msg_place_no_targets": "Kein Behälter mit bekanntem Raster gefunden. Führe "
                                "Spielnamen aktualisieren aus, damit der Editor die "
                                "Behältergrößen kennt.",
        "msg_place_no_space": "In {target} ist kein Platz für diesen Gegenstand "
                              "({width}x{height}).",
        "msg_place_partial": "Nur {placed} von {wanted} haben gepasst, danach war in "
                             "{target} kein Platz mehr.",
        "target_same_container": "Derselbe Behälter wie das Original",
        "target_inbox": "Posteingang - im Spiel selbst abholen",
        "msg_place_inbox_hint": "Posteingang: der Gegenstand wird ohne Rasterposition "
                                "abgelegt. Das Spiel kann ihn nicht platzieren und gibt ihn "
                                "dir als Post - dort landet ohnehin alles, was keinen Platz "
                                "findet. Nimm das, wenn die Behälter voll sind oder du selbst "
                                "einsortieren willst.",
        "target_tab": "Reiter {idx} - {free} von {total} Feldern frei",
        "target_carried": "{name} (am Körper) - {free} von {total} Feldern frei",
        "target_container": "Behälter",
        "btn_close": "Schließen"
    },
    "ru": {
        "title": "★ Cargo Hunters Save Editor ★",
        "active_session": "[Активная сессия]",
        "tab_inventory": "Инвентарь",
        "tab_mailbox": "Почта",
        "tab_catalog": "Предметы",
        "tab_hackerman": "☢ Лаборатория Хакера ☢",
        "tab_help": "Справка / Инструкция",
        "btn_refresh": "🔄 Обновить имена из игры",
        "btn_apply": "Применить изменения",
        "btn_discard": "Сбросить изменения",
        "lbl_scope": "Область:",
        "lbl_search": "Поиск:",
        "btn_search": "Найти",
        "btn_delete_mail": "Удалить выбранное письмо",
        "lbl_category": "Категория:",
        "lbl_subcategory": "Подкатегория:",
        "ctx_add_to_inv": "Добавить в инвентарь",
        "lbl_warn_title": "☠ ВНИМАНИЕ: ОПАСНАЯ ЗОНА ХАКЕРА ☠",
        "lbl_warn_desc": "Редактирование характеристик персонажа, навыков или торговцев может полностью повредить (сломать) ваше сохранение!\nИспользуйте эти функции на свой страх и риск.",
        "lf_profile": " Детали профиля ",
        "lbl_nickname": "Никнейм:",
        "lbl_level": "Уровень:",
        "lbl_xp": "Очки опыта:",
        "lf_cheats": " Читы в один клик ",
        "btn_cheat_max": "⚡ Макс. все навыки",
        "btn_cheat_fill": "💰 Заполнить баланс торговцев",
        "btn_cheat_repair": "🔧 Починить все вещи",
        "lbl_selected_skill": "Уровень навыка:",
        "btn_set_skill": "Задать уровень",
        "lbl_selected_trader": "Уровень торговца:",
        "btn_set_trader": "Задать параметры",
        "col_skill_id": "ID Навыка",
        "col_skill_name": "Название навыка",
        "col_skill_level": "Уровень",
        "col_trader_name": "Имя торговца",
        "col_trader_level": "Уровень торговца",
        "col_trader_balance": "Баланс (Кредиты)",
        "col_trader_instance_id": "ID инстанса торговца",
        "col_trader_type_id": "ID типа торговца",
        "msg_discard_title": "Сбросить изменения",
        "msg_discard_text": "Отменить все несохраненные изменения?",
        "msg_success_title": "Успешно",
        "msg_save_success": "Файл сохранения успешно обновлен.",
        "msg_refresh_success": "Маппинг данных успешно обновлен.",
        "msg_refresh_failed": "Не удалось обновить маппинг данных.",
        "msg_refresh_empty": "Путь к папке игры пуст.",
        "msg_refresh_prompt": "Обновить маппинг из игровых файлов?\nДля этого требуется UnityPy и путь к папке игры Cargo Hunters.",
        "msg_no_item_selected": "Элемент не выбран.",
        "msg_item_spawned": "Успешно добавлено {name} в {scope}.",
        "msg_spawn_failed": "Не удалось добавить предмет: {error}",
        "btn_mute": "🔇 Выкл. звук",
        "btn_unmute": "🔊 Вкл. звук",
        "status_welcome": "Добро пожаловать в Cargo Hunters Save Editor",
        "status_ready": "Готово",
        "status_pending_changes": "Ожидающие изменения: {desc}",
        "status_no_pending": "Нет ожидающих изменений",
        "status_refreshed": "Маппинг обновлен из: {path}",
        "ctx_repair": "Починить предмет",
        "ctx_duplicate": "Дублировать предмет",
        "ctx_delete": "Удалить предмет",
        "tab_skills": "Навыки",
        "tab_trader_balances": "Баланс торговцев",
        "lbl_balance": "Баланс:",
        "pending_label": "ОЖИДАЮЩИЕ ИЗМЕНЕНИЯ | ",
        "names_status": " | Имен: {total_names} загружено ({alias_names} ручных алиасов)",
        "col_mail_index": "#",
        "col_mail_sender": "Отправитель",
        "col_mail_subject": "Письмо",
        "col_mail_rewards": "Награды",
        "col_mail_read": "Прочитано",
        "col_mail_id": "ID письма",
        "col_cat_name": "Название",
        "col_cat_template_id": "TemplateId",
        "col_cat_category": "Категория",
        "col_cat_subcategory": "Подкатегория",
        "col_cat_size": "Размер",
        "col_cat_stack": "Стак",
        "all_categories": "Все",
        "scope_equipment": "Снаряжение персонажа",
        "scope_tab": "Вкладка {idx}",
        "scope_shelter": "Убежище",
        "msg_cheats_repair": "Успешно! Починено предметов: {count} (до 100%)!",
        "msg_cheats_skills": "Успешно! Навыков поднято: {count}, каждый до своего максимума!",
        "msg_cheats_traders": "Успешно! Начислено 1 000 000 кредитов {count} торговцам!",
        "status_cheat_repaired": "Починено предметов: {count} (до 100%) в файле сохранения",
        "status_cheat_maxed_skills": "Максимизированы все уровни навыков",
        "status_cheat_filled_traders": "Балансы всех торговцев заполнены до 1 000 000",
        "status_skill_set": "Установлен уровень навыка {skill_id} на {level}",
        "status_trader_set": "Заданы параметры торговца: уровень={level} баланс={balance}",
        "status_mail_deleted": "Удалено письмо с индексом {index}",
        "msg_mapping_updated": "Маппинг имен обновлен.\nИзвестные имена: {old_count} -> {new_count}{details}",
        "msg_err_game_folder_not_found": "Папка игры не найдена:\n{game_dir}",
        "msg_prompt_game_folder": "Путь к папке игры Cargo Hunters:",
        "msg_game_folder_title": "Папка игры",
        "msg_discard_confirm": "Отменить все несохраненные изменения с момента последнего применения?",
        "msg_reload_failed": "Не удалось перезагрузить сохранение с диска:\n{exc}",
        "msg_unsaved_changes_title": "Несохраненные изменения",
        "msg_unsaved_changes_prompt": "У вас есть несохраненные изменения.\n\nДа: применить изменения и выйти\nНет: сбросить изменения и выйти\nОтмена: оставить редактор открытым",
        "status_changes_applied": "Изменения применены к файлу сохранения",
        "status_changes_applied_backup": "Изменения применены. Резервная копия: backups\\{name}",
        "status_changes_applied_backup_pruned": "Изменения применены. Резервная копия: backups\\{name} (удалено старых копий: {count})",
        "backups_keep_label": "Хранить копий:",
        "backups_keep_hint": "Сколько резервных копий хранить в папке backups. 0 — хранить все.",
        "status_changes_discarded": "Несохраненные изменения сброшены",
        "msg_err_save_not_found": "--save-path не существует:\n{candidate}",
        "msg_title_save_not_found": "Файл сохранения не найден",
        "msg_multiple_saves_title": "Найдено несколько сохранений",
        "msg_multiple_saves_prompt": "Найдено {count} файлов сохранения.\n\nИспользовать самый новый автоматически?\n{newest}\n\nДа = использовать этот файл\nНет = выбрать вручную",
        "msg_load_save_failed_title": "Не удалось загрузить сохранение",
        "msg_select_save_title": "Выберите offline.save для Cargo Hunters",
        "col_mail_count": "Писем: {count}",
        "status_scope_info": "Область: {scope} | Сохранение: {path}",
        "status_refreshing": "Обновление имен из ресурсов игры... это может занять некоторое время",
        "status_catalog_added": "Добавлено {added} предметов из каталога (еще не сохранено)",
        "status_item_edited": "Изменен предмет {item_id} (еще не сохранено)",
        "status_skill_edited": "Изменен навык {skill_id} (еще не сохранено)",
        "status_duplicated": "Дублировано ({mode}): создано {count}{failure}",
        "mode_stack_items": "стопки предметов",
        "mode_item_copies": "копии предметов",
        "status_mail_deleted_pending": "Удалено одно письмо из почты (еще не сохранено)",
        "scope_char_eq": "Снаряжение персонажа",
        "msg_catalog_row_invalid": "Некорректная строка в каталоге.",
        "msg_no_template_id": "У выбранной строки нет TemplateId.",
        "msg_add_item_title": "Добавить предмет",
        "msg_add_item_prompt": "Сколько копий добавить?",
        "msg_add_stack_prompt": "Сколько единиц добавить?\nВ один стак входит {capacity}; большее количество будет разбито на несколько стаков.",
        "msg_no_inv_tab_found": "Вкладка инвентаря для вставки не найдена.",
        "ctx_offer_at_trader": "Предложить у торговца...",
        "shop_offer_title": "Предложить у торговца",
        "shop_offer_intro": "Помещает {name} в существующий слот предложения торговца.\nСледующее обновление ассортимента отменит это само.",
        "shop_offer_trader": "Торговец:",
        "shop_offer_slot": "Перезаписываемый слот предложения:",
        "shop_offer_price": "Цена (кредиты):",
        "shop_offer_count": "Количество для продажи:",
        "btn_shop_offer_confirm": "Перезаписать предложение",
        "btn_shop_offer_restore": "Отменить ({count})",
        "msg_shop_no_offers": "Ни у одного торговца в этом сохранении нет редактируемого списка предложений.",
        "msg_shop_slot_needed": "Выберите слот предложения для перезаписи.",
        "msg_shop_bad_numbers": "Цена и количество должны быть целыми числами больше нуля.",
        "msg_shop_slot_gone": "Этот слот предложения больше не существует в сохранении.",
        "msg_shop_restore_none": "Отменять нечего.",
        "status_shop_offer_set": "{trader} теперь предлагает {name} x{count} за {price} (ещё не сохранено)",
        "status_shop_offer_restored": "Возвращено слотов: {restored}; уже исчезло после обновления ассортимента: {gone} (ещё не сохранено)",
        "msg_no_selection_title": "Ничего не выбрано",
        "msg_row_no_item_data": "Выбранная строка не содержит данных предмета.",
        "msg_item_not_found": "Предмет не найден: {item_id}",
        "msg_duplicate_failed": "Не удалось дублировать выделенное.{failed_hint}",
        "msg_delete_title": "Удаление предмета",
        "msg_delete_confirm": "Удалить этот предмет?",
        "msg_delete_confirm_many": "Удалить эти предметы ({count})? Одна строка означает все из них.",
        "msg_delete_attachments": "Вместе с ним будет удалено вложенных предметов: {count}.",
        "msg_delete_equipped": "Он находится в слоте снаряжения. Слот останется пустым.",
        "msg_delete_revert_hint": "До применения изменений «Отменить изменения» вернёт всё назад.",
        "msg_delete_structural": "Эта строка — контейнер самого сохранения, а не предмет. Её нельзя удалить.",
        "status_items_deleted": "Удалено предметов: {count} (ещё не сохранено)",
        "msg_search_empty": "Пожалуйста, введите поисковый запрос.",
        "msg_skill_level_range": "Неверный уровень. У этого навыка диапазон 0-{max_level}.",
        "msg_trader_level_range": "Неверный уровень. У торговца диапазон {min_level}-{max_level}.",
        "btn_level_max": "МАКС",
        "lbl_skill_points": "Свободные очки навыков:",
        "tab_counters": "Статистика",
        "col_counter_group": "Группа",
        "col_counter_stat": "Показатель",
        "col_counter_value": "Значение",
        "col_counter_updated": "Обновлено (UTC)",
        "counters_sessions": "Сессии",
        "counters_last_run": "Последний рейд",
        "counters_lifetime": "Всего",
        "counters_hint": "Только для просмотра: счётчики игры. Здесь ничего не записывается.",
        "counters_empty": "В этом сохранении нет счётчиков.",
        "msg_select_search_result": "Сначала выберите результат поиска.",
        "msg_select_letter": "Сначала выберите письмо.",
        "msg_err_resolve_letter": "Не удалось определить индекс выбранного письма.",
        "msg_err_letter_out_of_range": "Выбранное письмо находится вне диапазона.",
        "msg_err_save_failed": "Не удалось сохранить изменения:\n{exc}",
        "search_results_title": "Результаты поиска ({count})",
        "search_found_count": "Найдено {count} совпадающих предметов",
        "col_id": "Id",
        "col_condition": "Состояние",
        "btn_ok": "ОК",
        "btn_cancel": "Отмена",
        "msg_place_prompt": "Куда положить?",
        "msg_place_hint": "В выбранном контейнере будет найдено свободное место. Предмет "
                          "поворачивается только если иначе он не помещается.",
        "msg_place_no_targets": "Не найдено контейнеров с известной сеткой. Выполните "
                                "«Обновить названия из игры», чтобы редактор узнал размеры "
                                "контейнеров.",
        "msg_place_no_space": "В {target} нет места для этого предмета ({width}x{height}).",
        "msg_place_partial": "Поместилось только {placed} из {wanted}; после этого в "
                             "{target} не осталось места.",
        "target_same_container": "Тот же контейнер, что у оригинала",
        "target_inbox": "Входящие - забрать в игре самому",
        "msg_place_inbox_hint": "Входящие: предмет сохраняется без позиции в сетке. Игра не "
                                "может его разместить и выдаёт его вам письмом - туда и так "
                                "попадает всё, чему не хватило места. Выбирайте это, когда "
                                "контейнеры полны или вы хотите разложить сами.",
        "target_tab": "Вкладка {idx} - свободно {free} из {total} клеток",
        "target_carried": "{name} (при себе) - свободно {free} из {total} клеток",
        "target_container": "Контейнер",
        "btn_close": "Закрыть"
    }
}
SKILL_NAMES = {
    "1": "Pistols (Disabled)",
    "2": "SMGs (Disabled)",
    "3": "ARs (Disabled)",
    "4": "Shotguns (Disabled)",
    "5": "Sniper Rifles (Disabled)",
    "6": "Marksm. Rifles (Disabled)",
    "7": "Machine Guns (Disabled)",
    "9": "Throwables (Disabled)",
    "10": "Item Find",
    "11": "First Aid",
    "12": "Combat",
    "13": "Mobility",
    "14": "Melee (Disabled)",
    "16": "Logistics",
    "17": "Angle Grinder (Disabled)",
    "18": "Pistols",
    "19": "ARs",
    "20": "Shotguns",
    "21": "Sniper Rifles",
    "22": "Marksm. Rifles",
    "23": "SMGs",
    "24": "Melee",
    "25": "2 Primary",
    "26": "Sound locator",
    "27": "Lockpicker"
}

# Account levels. The real ceiling is `MaxLevel` in the game's level_progress_settings and
# arrives through the mapping report as `max_account_level`; these are only what applies when
# no report is there. Measured at 25 on 2026-07-28 - the same 25 that used to be hardcoded in
# three places. Read them through `_max_level_for_account()`, never directly.
TRADER_LEVEL_MIN = 1
TRADER_LEVEL_MAX_FALLBACK = 25

# One-click "fill trader balances" without a report. Each shop's own `ShopBalance` from the
# game data is preferred; this is the flat value the cheat wrote before that existed.
TRADER_BALANCE_FALLBACK = 1000000

# The level controls on the Skills and Traders tabs all render at one size, 120x31 px, taken
# from the plain button next to them. Both values are widths in characters: 14 of the button
# font and 11 of the spinbox's wider Consolas digits come out the same. The paddings and
# arrowsize in Level.TSpinbox / Step.TButton are part of that fit and were measured, not
# guessed - test_skill_levels.py checks the three widgets still match.
LEVEL_CONTROL_WIDTH = 14
LEVEL_SPIN_WIDTH = 11
LEVEL_SPIN_FONT = ("Consolas", 12, "bold")

TRADER_NAMES = {
    "381e554d-0ab7-4111-9e8c-3710bd05d086": "Spider.net",
    "e2874df4-6a8c-4539-ace0-926d4f43766a": "Delivery Guy",
    "a1d0c214-f707-4975-9d64-b8e6405fceec": "Delivery Guy",
    "41000937-3218-4d9b-9aa9-b3a62343ca4f": "Base Shop (BasePrice)",
    "179d4947-5320-4d86-9f4d-f5706c4745fb": "QuickSell",
    "101db923-b828-417d-9103-c0ea7ac65713": "Pedlar"
}


class SaveEditorGUI:
    def __init__(self, root: tk.Tk, manager: SaveDataManager, save_path: str):
        self.root = root
        self.manager = manager
        self.save_path = save_path

        self.entry_members: dict[str, list[str]] = {}
        self.loaded_nodes: set[str] = set()
        self.scope_labels: list[str] = []
        self.mail_index_map: dict[str, int] = {}
        self.template_name_map: dict[str, str] = {}
        self.npc_name_map: dict[str, str] = {}
        self.game_item_catalog: list[dict] = []
        self.game_item_meta_by_template_id: dict[str, dict] = {}
        self.manual_alias_map: dict[str, str] = {}
        self.template_map_source: str | None = None
        self.alias_map_source: str | None = None
        self.last_game_path: str | None = None
        self.has_pending_changes = False
        # Overwritten trader offer slots, keyed "<shop id>:<commodity id>", each holding the
        # slot as it was before. Deliberately session-only - see _drop_shop_offer_undo_file.
        self.shop_offer_undo: dict[str, dict] = {}
        self._drop_shop_offer_undo_file()
        # Read before the layout, which shows the value in the status bar.
        self.manager.backup_keep = load_config_backup_keep()

        self.root.title("Cargo Hunters Save Editor")
        # 680, not 650: the Hackerman tab's left column - warning, profile, three cheat
        # buttons - needs 487px in German at the minimum, and 650 leaves only 468. Measured
        # in all three languages; English and Russian were clipping by a few pixels too.
        self.root.minsize(1100, 680)
        self._center_window(1100, 720)

        # Style Setup (Premium Dark Mode)
        self.root.configure(bg="#1e1e1e")
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.style.configure(".", 
            background="#1e1e1e", 
            foreground="#d4d4d4",
            fieldbackground="#252526",
            troughcolor="#1e1e1e",
            bordercolor="#3c3c3c",
            lightcolor="#3c3c3c",
            darkcolor="#1e1e1e"
        )
        
        self.style.configure("TNotebook", background="#1e1e1e", borderwidth=0)
        self.style.configure("TNotebook.Tab", 
            background="#2d2d2d", 
            foreground="#969696", 
            padding=[14, 6], 
            font=("TkDefaultFont", 9, "bold")
        )
        self.style.map("TNotebook.Tab", 
            background=[("selected", "#1e1e1e"), ("active", "#3c3c3c")],
            foreground=[("selected", "#3794ff"), ("active", "#ffffff")]
        )
        
        self.style.configure("TFrame", background="#1e1e1e")
        self.style.configure("TLabel", background="#1e1e1e", foreground="#d4d4d4")
        
        self.style.configure("TButton", 
            background="#2d2d2d", 
            foreground="#d4d4d4", 
            bordercolor="#3c3c3c", 
            relief="flat", 
            padding=[8, 4]
        )
        self.style.map("TButton", 
            background=[("active", "#0e639c"), ("pressed", "#094771")],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")]
        )
        
        self.style.configure("TEntry", 
            fieldbackground="#252526", 
            foreground="#ffffff", 
            insertcolor="#3794ff",
            bordercolor="#3c3c3c"
        )
        
        self.style.configure("TCombobox", 
            fieldbackground="#252526", 
            background="#1e1e1e", 
            foreground="#ffffff", 
            arrowcolor="#3794ff",
            bordercolor="#3c3c3c"
        )
        self.style.map("TCombobox", 
            fieldbackground=[("readonly", "#252526"), ("active", "#2d2d2d")],
            background=[("readonly", "#252526"), ("active", "#2d2d2d")],
            foreground=[("readonly", "#ffffff"), ("active", "#ffffff")]
        )
        self.root.option_add("*TCombobox*Listbox.background", "#252526")
        self.root.option_add("*TCombobox*Listbox.foreground", "#d4d4d4")
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#0e639c")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        
        self.style.configure("Treeview", 
            background="#252526", 
            fieldbackground="#252526", 
            foreground="#d4d4d4",
            rowheight=24,
            borderwidth=0
        )
        self.style.map("Treeview", 
            background=[("selected", "#094771")],
            foreground=[("selected", "#ffffff")]
        )
        self.style.configure("Heading", 
            background="#2d2d2d", 
            foreground="#3794ff", 
            font=("TkDefaultFont", 10, "bold"),
            borderwidth=0
        )
        
        self.style.configure("TScrollbar", 
            troughcolor="#1e1e1e", 
            background="#2d2d2d", 
            arrowcolor="#3794ff",
            bordercolor="#3c3c3c"
        )
        
        # The level controls on the Skills and Traders tabs: a readout with its own arrows
        # next to a MAX button, sized to match the plain button beside them. The paddings
        # below are tuned so all three render the same height - measured, not guessed.
        self.style.configure("Level.TSpinbox",
            fieldbackground="#252526",
            foreground="#3794ff",
            insertcolor="#3794ff",
            arrowsize=13,
            arrowcolor="#3794ff",
            bordercolor="#3c3c3c",
            padding=[2, 4]
        )
        # Same font family as a plain button so that a width in characters means the same
        # number of pixels on both; only the weight and the colour differ.
        self.style.configure("Step.TButton",
            background="#2d2d2d",
            foreground="#3794ff",
            font=("TkDefaultFont", 9, "bold"),
            relief="flat",
            padding=[8, 5]
        )
        self.style.map("Step.TButton",
            background=[("active", "#0e639c"), ("pressed", "#094771")],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")]
        )

        # A value the editor refuses to write. Red field, not a popup: the character fields
        # are typed into and a dialog per keystroke would be unusable.
        self.style.configure("Invalid.TEntry",
            fieldbackground="#3a1d1d",
            foreground="#ff8a8a",
            insertcolor="#ff8a8a",
            bordercolor="#c05050"
        )

        # Explanatory text in dialogs: dimmed, on the same background as everything else.
        self.style.configure("Hint.TLabel", background="#1e1e1e", foreground="#9a9a9a")
        self.style.configure("Status.TLabel",
            foreground="#969696"
        )

        self.status_var = tk.StringVar(value=f"Save: {self.save_path}")
        self.scope_var = tk.StringVar()
        self.catalog_search_var = tk.StringVar()
        self.catalog_category_var = tk.StringVar(value="All")
        self.catalog_subcategory_var = tk.StringVar(value="All")
        self.music_playing = False
        self.music_process = None

        self.current_lang = load_config_lang()

        self._load_template_name_map()
        self._build_layout()
        self._load_scope_options()
        self._refresh_mailbox()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_requested)
        self._start_music()

    def _build_layout(self) -> None:
        # Header Title
        header_frame = tk.Frame(self.root, bg="#1e1e1e")
        header_frame.pack(fill="x", padx=8, pady=(8, 2))
        
        self.title_label = tk.Label(
            header_frame, 
            font=("TkDefaultFont", 12, "bold"),
            fg="#3794ff",
            bg="#1e1e1e"
        )
        self.title_label.pack(side="left")
        
        self.subtitle_label = tk.Label(
            header_frame, 
            font=("TkDefaultFont", 9, "italic"),
            fg="#969696",
            bg="#1e1e1e"
        )
        self.subtitle_label.pack(side="left", padx=10)

        # Hackerman avatar image on the far right
        image_path = self._asset_path("hackerman.png")
        if image_path.exists():
            try:
                self.hackerman_img = tk.PhotoImage(file=str(image_path))
                img_label = tk.Label(header_frame, image=self.hackerman_img, bg="#1e1e1e")
                img_label.pack(side="right", padx=(5, 10))
            except Exception as e:
                print(f"Could not load image: {e}")

        # Hackerman quote badge
        self.badge_label = tk.Label(
            header_frame,
            text="[ HACKERMAN: I'm hacking you back in time! ]",
            font=("Consolas", 10, "bold"),
            fg="#ff007f",
            bg="#1e1e1e"
        )
        self.badge_label.pack(side="right", padx=(0, 5))

        # Global Refresh Names button
        self.refresh_btn = ttk.Button(
            header_frame,
            command=self._refresh_names_from_game,
        )
        self.refresh_btn.pack(side="right", padx=(10, 5))

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.tab_inventory = ttk.Frame(self.notebook)
        self.tab_mailbox = ttk.Frame(self.notebook)
        self.tab_catalog = ttk.Frame(self.notebook)
        self.tab_char = ttk.Frame(self.notebook)
        self.tab_help = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_inventory)
        self.notebook.add(self.tab_catalog)
        self.notebook.add(self.tab_mailbox)
        self.notebook.add(self.tab_char)
        self.notebook.add(self.tab_help)

        self._build_help_tab(self.tab_help)
        self._build_char_tab(self.tab_char)

        toolbar = ttk.Frame(self.tab_inventory)
        toolbar.pack(fill="x", padx=4, pady=4)

        self.scope_lbl = ttk.Label(toolbar)
        self.scope_lbl.pack(side="left", padx=(0, 6))
        self.scope_combo = ttk.Combobox(
            toolbar,
            textvariable=self.scope_var,
            state="readonly",
            width=28,
        )
        self.scope_combo.pack(side="left", padx=(0, 12))
        self.scope_combo.bind("<<ComboboxSelected>>", self._on_scope_changed)

        self.search_lbl = ttk.Label(toolbar)
        self.search_lbl.pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=36)
        self.search_entry.pack(side="left", padx=(0, 6))
        self.search_entry.bind("<Return>", lambda _: self._search_items())
        self.search_btn = ttk.Button(toolbar, command=self._search_items)
        self.search_btn.pack(side="left")
        self.discard_button = ttk.Button(
            toolbar,
            command=self._discard_pending_changes,
        )
        self.discard_button.pack(side="right", padx=(6, 0))
        self.apply_button = ttk.Button(
            toolbar,
            command=self._apply_pending_changes,
        )
        self.apply_button.pack(side="right")

        tree_wrap = ttk.Frame(self.tab_inventory)
        tree_wrap.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        tree_scroll = ttk.Scrollbar(tree_wrap, orient="vertical")
        tree_scroll.pack(side="right", fill="y")

        self.tree = ttk.Treeview(tree_wrap, show="tree", yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        tree_scroll.configure(command=self.tree.yview)

        self.context_menu = tk.Menu(
            self.root, 
            tearoff=0, 
            bg="#252526", 
            fg="#d4d4d4", 
            activebackground="#0e639c", 
            activeforeground="#ffffff"
        )
        self.context_menu.add_command(command=self._repair_selected)
        self.context_menu.add_command(command=self._duplicate_selected)
        # The separator keeps the one destructive entry away from Duplicate, which sits
        # directly above it. It occupies index 2, so Delete is relabelled as index 3.
        self.context_menu.add_separator()
        self.context_menu.add_command(command=self._delete_selected_items)

        mailbox_toolbar = ttk.Frame(self.tab_mailbox)
        mailbox_toolbar.pack(fill="x", padx=4, pady=4)
        self.mail_delete_btn = ttk.Button(
            mailbox_toolbar, command=self._delete_selected_mail
        )
        self.mail_delete_btn.pack(side="left")
        self.mail_count_var = tk.StringVar(value="Letters: 0")
        ttk.Label(mailbox_toolbar, textvariable=self.mail_count_var).pack(side="left", padx=(12, 0))
        self.mail_discard_button = ttk.Button(
            mailbox_toolbar,
            command=self._discard_pending_changes,
        )
        self.mail_discard_button.pack(side="right", padx=(6, 0))
        self.mail_apply_button = ttk.Button(
            mailbox_toolbar,
            command=self._apply_pending_changes,
        )
        self.mail_apply_button.pack(side="right")

        mailbox_wrap = ttk.Frame(self.tab_mailbox)
        mailbox_wrap.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        mail_scroll = ttk.Scrollbar(mailbox_wrap, orient="vertical")
        mail_scroll.pack(side="right", fill="y")

        self.mail_tree = ttk.Treeview(
            mailbox_wrap,
            columns=("index", "sender", "message_ref", "rewards", "read", "mail_id"),
            show="headings",
            height=10,
            yscrollcommand=mail_scroll.set
        )
        mail_scroll.configure(command=self.mail_tree.yview)
        self.mail_tree.column("index", width=60, anchor="center")
        self.mail_tree.column("sender", width=220, anchor="w")
        self.mail_tree.column("message_ref", width=230, anchor="w")
        self.mail_tree.column("rewards", width=70, anchor="center")
        self.mail_tree.column("read", width=70, anchor="center")
        self.mail_tree.column("mail_id", width=360, anchor="w")
        self.mail_tree.pack(side="left", fill="both", expand=True)

        catalog_toolbar = ttk.Frame(self.tab_catalog)
        catalog_toolbar.pack(fill="x", padx=4, pady=4)
        self.cat_scope_lbl = ttk.Label(catalog_toolbar)
        self.cat_scope_lbl.pack(side="left", padx=(0, 6))
        self.catalog_category_combo = ttk.Combobox(
            catalog_toolbar,
            textvariable=self.catalog_category_var,
            state="readonly",
            # The labels carry an id and a name ("24: Weapon Mod"); at 12 they were cut off.
            width=20,
        )
        self.catalog_category_combo.pack(side="left", padx=(0, 12))
        self.catalog_category_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_category_selected(),
        )
        self.cat_subscope_lbl = ttk.Label(catalog_toolbar)
        self.cat_subscope_lbl.pack(side="left", padx=(0, 6))
        self.catalog_subcategory_combo = ttk.Combobox(
            catalog_toolbar,
            textvariable=self.catalog_subcategory_var,
            state="readonly",
            width=20,
        )
        self.catalog_subcategory_combo.pack(side="left", padx=(0, 12))
        self.catalog_subcategory_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_catalog_tree(),
        )
        self.cat_search_lbl = ttk.Label(catalog_toolbar)
        self.cat_search_lbl.pack(side="left", padx=(0, 6))
        catalog_search_entry = ttk.Entry(
            catalog_toolbar,
            textvariable=self.catalog_search_var,
            width=22,
        )
        catalog_search_entry.pack(side="left", padx=(0, 6))
        catalog_search_entry.bind("<Return>", lambda _event: self._refresh_catalog_tree())
        self.cat_search_btn = ttk.Button(
            catalog_toolbar,
            command=self._refresh_catalog_tree,
        )
        self.cat_search_btn.pack(side="left")
        # Both catalog actions live in the tree's right-click menu, so Apply/Discard are
        # the only buttons here - same position as on the inventory toolbar.
        self.cat_discard_button = ttk.Button(
            catalog_toolbar,
            command=self._discard_pending_changes,
        )
        self.cat_discard_button.pack(side="right", padx=(6, 0))
        self.cat_apply_button = ttk.Button(
            catalog_toolbar,
            command=self._apply_pending_changes,
        )
        self.cat_apply_button.pack(side="right")

        catalog_wrap = ttk.Frame(self.tab_catalog)
        catalog_wrap.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        
        catalog_scroll = ttk.Scrollbar(
            catalog_wrap,
            orient="vertical"
        )
        catalog_scroll.pack(side="right", fill="y")

        self.catalog_tree = ttk.Treeview(
            catalog_wrap,
            columns=("name", "template_id", "category", "subcategory", "size", "stack"),
            show="headings",
            height=14,
            yscrollcommand=catalog_scroll.set
        )
        catalog_scroll.configure(command=self.catalog_tree.yview)
        self.catalog_tree.column("name", width=260, anchor="w")
        self.catalog_tree.column("template_id", width=290, anchor="w")
        self.catalog_tree.column("category", width=160, anchor="w")
        self.catalog_tree.column("subcategory", width=170, anchor="w")
        self.catalog_tree.column("size", width=70, anchor="center")
        self.catalog_tree.column("stack", width=80, anchor="center")
        self.catalog_tree.pack(side="left", fill="both", expand=True)
        self.catalog_tree.bind("<Button-3>", self._on_catalog_right_click)

        self.catalog_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#252526",
            fg="#d4d4d4",
            activebackground="#0e639c",
            activeforeground="#ffffff"
        )
        self.catalog_menu.add_command(command=self._add_selected_catalog_item_to_inventory)
        self.catalog_menu.add_command(command=self._offer_selected_catalog_item_at_trader)

        status_bar_frame = ttk.Frame(self.root)
        status_bar_frame.pack(fill="x", padx=8, pady=(0, 8))

        # Language Selector combobox next to the mute button (packed first to preserve right-side placement)
        self.lang_var = tk.StringVar()
        self.lang_combo = ttk.Combobox(
            status_bar_frame,
            textvariable=self.lang_var,
            values=["🇬🇧", "🇩🇪", "🇷🇺"],
            state="readonly",
            width=6
        )
        self.lang_combo.pack(side="right", padx=(6, 0))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        self.mute_button = ttk.Button(
            status_bar_frame,
            width=8,
            command=self._toggle_music,
        )
        self.mute_button.pack(side="right", padx=(6, 0))

        # Backup retention sits with the other two app-wide settings rather than on a tab
        # toolbar: the German and Russian labels already crowd those at the 1100px minimum.
        self.backup_keep_var = tk.StringVar(value=str(self.manager.backup_keep))
        # Same colours and arrows as the two level controls, but not their font: the status
        # bar already crowds at the 1100px window minimum in German and Russian.
        self.backup_keep_spin = ttk.Spinbox(
            status_bar_frame,
            from_=0,
            to=999,
            width=4,
            justify="center",
            style="Level.TSpinbox",
            textvariable=self.backup_keep_var,
            command=self._on_backup_keep_changed,
        )
        self.backup_keep_spin.pack(side="right", padx=(6, 0))
        self.backup_keep_spin.bind("<FocusOut>", lambda _: self._on_backup_keep_changed())
        self.backup_keep_spin.bind("<Return>", lambda _: self._on_backup_keep_changed())

        self.backup_keep_label = ttk.Label(status_bar_frame)
        self.backup_keep_label.pack(side="right", padx=(12, 0))

        status_bar = ttk.Label(status_bar_frame, textvariable=self.status_var, anchor="w", relief="flat", style="Status.TLabel")
        status_bar.pack(side="left", fill="x", expand=True)

        self.lang_map = {
            "🇬🇧": "en",
            "🇩🇪": "de",
            "🇷🇺": "ru"
        }
        self.lang_map_rev = {v: k for k, v in self.lang_map.items()}
        self.lang_var.set(self.lang_map_rev.get(self.current_lang, "🇬🇧"))

        # Every tab that can stage an edit gets its own Apply/Discard pair (all but Help);
        # these lists keep their enabled state and labels in sync.
        self.apply_buttons = [
            self.apply_button,
            self.cat_apply_button,
            self.mail_apply_button,
            self.char_apply_button,
        ]
        self.discard_buttons = [
            self.discard_button,
            self.cat_discard_button,
            self.mail_discard_button,
            self.char_discard_button,
        ]

        self._refresh_pending_buttons()
        self._animate_badge()
        self._update_ui_language()

    def _center_window(self, width: int = 1100, height: int = 700) -> None:
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _center_toplevel(self, win: tk.Toplevel) -> None:
        """Centers a dialog on screen at its natural size. Call this only once the contents
        are packed - the size is taken from the finished layout."""
        win.update_idletasks()
        width = win.winfo_reqwidth()
        height = win.winfo_reqheight()
        x = max(0, (win.winfo_screenwidth() - width) // 2)
        y = max(0, (win.winfo_screenheight() - height) // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")

    def _animate_badge(self) -> None:
        colors = ["#ff007f", "#3794ff", "#00f0ff", "#a020f0", "#39ff14"]
        if not hasattr(self, 'badge_color_idx'):
            self.badge_color_idx = 0
        
        self.badge_label.configure(fg=colors[self.badge_color_idx])
        self.badge_color_idx = (self.badge_color_idx + 1) % len(colors)
        
        self.root.after(400, self._animate_badge)

    def _get_system_language(self) -> str:
        return get_system_language()

    def _on_language_changed(self, event=None) -> None:
        selected = self.lang_var.get()
        new_lang = self.lang_map.get(selected, "en")
        if new_lang != self.current_lang:
            self.current_lang = new_lang
            save_config_lang(new_lang)
            self._update_ui_language()

    def _on_backup_keep_changed(self) -> None:
        """Stores the new retention limit. Deliberately does not delete anything yet -
        pruning happens when the next backup is written, so a stray click on the spinner
        cannot destroy backups."""
        try:
            keep = max(0, int(self.backup_keep_var.get().strip()))
        except ValueError:
            self.backup_keep_var.set(str(self.manager.backup_keep))
            return
        if keep == self.manager.backup_keep:
            return
        self.manager.backup_keep = keep
        self.backup_keep_var.set(str(keep))
        save_config_backup_keep(keep)

    def _update_ui_language(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        
        # 1. Header Frame
        self.title_label.configure(text=t["title"])
        self.subtitle_label.configure(text=t["active_session"])
        self.refresh_btn.configure(text=t["btn_refresh"])
        
        # 2. Main Notebook Tabs
        self.notebook.tab(self.tab_inventory, text=t["tab_inventory"])
        self.notebook.tab(self.tab_mailbox, text=t["tab_mailbox"])
        self.notebook.tab(self.tab_catalog, text=t["tab_catalog"])
        self.notebook.tab(self.tab_char, text=t["tab_hackerman"])
        self.notebook.tab(self.tab_help, text=t["tab_help"])
        
        # 3. Inventory Tab
        self.scope_lbl.configure(text=t["lbl_scope"])
        self.search_lbl.configure(text=t["lbl_search"])
        self.search_btn.configure(text=t["btn_search"])
        # Covers the copies on the Game Items, Mailbox and Hackerman tabs as well.
        for button in self.apply_buttons:
            button.configure(text=t["btn_apply"])
        for button in self.discard_buttons:
            button.configure(text=t["btn_discard"])
        
        # Update context menu items
        self.context_menu.entryconfigure(0, label=t["ctx_repair"])
        self.context_menu.entryconfigure(1, label=t["ctx_duplicate"])
        # Index 2 is the separator.
        self.context_menu.entryconfigure(3, label=t["ctx_delete"])
        
        # 4. Mailbox Tab
        self.mail_delete_btn.configure(text=t["btn_delete_mail"])
        
        # Mailbox Table Headings
        self.mail_tree.heading("index", text=t["col_mail_index"])
        self.mail_tree.heading("sender", text=t["col_mail_sender"])
        self.mail_tree.heading("message_ref", text=t["col_mail_subject"])
        self.mail_tree.heading("rewards", text=t["col_mail_rewards"])
        self.mail_tree.heading("read", text=t["col_mail_read"])
        self.mail_tree.heading("mail_id", text=t["col_mail_id"])
        
        # 5. Catalog Tab
        self.cat_scope_lbl.configure(text=t["lbl_category"])
        self.cat_subscope_lbl.configure(text=t["lbl_subcategory"])
        self._refresh_subcategory_filter()
        self.cat_search_lbl.configure(text=t["lbl_search"])
        self.cat_search_btn.configure(text=t["btn_search"])
        self.catalog_menu.entryconfigure(0, label=t["ctx_add_to_inv"])
        self.catalog_menu.entryconfigure(1, label=t["ctx_offer_at_trader"])
        
        # Catalog Table Headings
        self.catalog_tree.heading("name", text=t["col_cat_name"])
        self.catalog_tree.heading("template_id", text=t["col_cat_template_id"])
        self.catalog_tree.heading("category", text=t["col_cat_category"])
        self.catalog_tree.heading("subcategory", text=t["col_cat_subcategory"])
        self.catalog_tree.heading("size", text=t["col_cat_size"])
        self.catalog_tree.heading("stack", text=t["col_cat_stack"])
        
        # 6. Hackerman Tab Warning Frame
        self.warning_title.configure(text=t["lbl_warn_title"])
        self.warning_desc.configure(text=t["lbl_warn_desc"])
        self.last_warn_data = {
            "title": t["lbl_warn_title"],
            "desc": t["lbl_warn_desc"]
        }
        
        # Profile Frame
        self.profile_lf.configure(text=t["lf_profile"])
        self.nickname_lbl.configure(text=t["lbl_nickname"])
        self.level_lbl.configure(text=t["lbl_level"])
        self.xp_lbl.configure(text=t["lbl_xp"])
        
        # Cheats Frame
        self.cheats_lf.configure(text=t["lf_cheats"])
        self.cheat_repair_all_btn.configure(text=t["btn_cheat_repair"])
        self.cheat_max_skills_btn.configure(text=t["btn_cheat_max"])
        self.cheat_fill_trader_btn.configure(text=t["btn_cheat_fill"])
        
        # Skills/Traders/Counters Subnotebook Tabs
        self.right_nb.tab(2, text=t["tab_counters"])
        self.counters_tree.heading("group", text=t["col_counter_group"])
        self.counters_tree.heading("stat", text=t["col_counter_stat"])
        self.counters_tree.heading("value", text=t["col_counter_value"])
        self.counters_tree.heading("updated", text=t["col_counter_updated"])
        # The group names and the hint are translated *content*, not widget labels, so
        # relabelling the headings is not enough - the rows have to be rebuilt.
        self._refresh_counters_list()
        self.skill_points_lbl.configure(text=t["lbl_skill_points"])
        self.right_nb.tab(0, text=t["tab_skills"])
        self.right_nb.tab(1, text=t["tab_trader_balances"])
        
        # Skills Control
        self.skill_level_lbl.configure(text=t["lbl_selected_skill"])
        self.set_skill_btn.configure(text=t["btn_set_skill"])
        self.skill_max_btn.configure(text=t["btn_level_max"])
        self.trader_max_btn.configure(text=t["btn_level_max"])
        
        # Skills Table Headings
        self.skills_tree.heading("id", text=t["col_skill_id"])
        self.skills_tree.heading("name", text=t["col_skill_name"])
        self.skills_tree.heading("level", text=t["col_skill_level"])
        
        # Traders Table Headings
        self.traders_tree.heading("id", text=t["col_trader_instance_id"])
        self.traders_tree.heading("template_id", text=t["col_trader_type_id"])
        self.traders_tree.heading("name", text=t["col_trader_name"])
        self.traders_tree.heading("trader_level", text=t["col_trader_level"])
        self.traders_tree.heading("balance", text=t["col_trader_balance"])
        
        # Traders Control
        self.trader_level_lbl.configure(text=t["lbl_selected_trader"])
        self.trader_balance_lbl.configure(text=t["lbl_balance"])
        self.set_trader_btn.configure(text=t["btn_set_trader"])
        
        # 7. Help Tab - Re-populate the Help text box
        self.help_text_area.configure(state="normal")
        self.help_text_area.delete("1.0", "end")
        
        # Load localized help texts
        if self.current_lang == "de":
            help_text = self.help_text_de
        elif self.current_lang == "ru":
            help_text = self.help_text_ru
        else:
            help_text = self.help_text_en
            
        for text, tag in help_text:
            self.help_text_area.insert("end", text, tag)
        self.help_text_area.configure(state="disabled")
        
        self.backup_keep_label.configure(text=t["backups_keep_label"])

        # 8. Mute Button Text
        if hasattr(self, "music_muted") and self.music_muted:
            self.mute_button.configure(text=t["btn_unmute"])
        else:
            self.mute_button.configure(text=t["btn_mute"])
            
        # 9. Load scope options with the current selection kept
        self._load_scope_options()
        
        # 10. Update catalog category combobox
        self._refresh_catalog_filters()
        
        # 11. Refresh current status line
        if hasattr(self, "last_status_raw"):
            self._set_status(self.last_status_raw)
        else:
            self._set_status("status_welcome")

    def _build_help_tab(self, parent: ttk.Frame) -> None:
        # The scrollbar needs its own place next to the text, not inside it. Parented to the
        # Text widget it floats on top and swallows the last word of every line that reaches
        # the right edge - invisible until a paragraph was long enough to get there.
        wrap_frame = ttk.Frame(parent)
        wrap_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.help_text_area = tk.Text(
            wrap_frame,
            wrap="word",
            bg="#252526",
            fg="#d4d4d4",
            insertbackground="#3794ff",
            font=("TkDefaultFont", 10),
            padx=16,
            pady=16,
            bd=0,
            highlightthickness=0
        )
        scroll = ttk.Scrollbar(wrap_frame, orient="vertical", command=self.help_text_area.yview)
        scroll.pack(side="right", fill="y")
        self.help_text_area.pack(side="left", fill="both", expand=True)
        self.help_text_area.configure(yscrollcommand=scroll.set)
        
        self.help_text_area.tag_configure("header", font=("TkDefaultFont", 11, "bold"), foreground="#3794ff")
        self.help_text_area.tag_configure("highlight", font=("TkDefaultFont", 10, "bold"), foreground="#ff007f")
        self.help_text_area.tag_configure("bullet", font=("TkDefaultFont", 10))
        self.help_text_area.tag_configure("link", font=("TkDefaultFont", 10, "underline", "bold"), foreground="#3794ff")
        self.help_text_area.tag_bind("link", "<Button-1>", lambda _: webbrowser.open("https://ko-fi.com/sirnr1"))
        self.help_text_area.tag_bind("link", "<Enter>", lambda _: self.help_text_area.configure(cursor="hand2"))
        self.help_text_area.tag_bind("link", "<Leave>", lambda _: self.help_text_area.configure(cursor=""))
        
        self.help_text_en = [
            ("★ UPDATE NAMES FROM GAME ★\n\n", "header"),
            ("• Scan Assets: ", "bullet"),
            ("Click ", "bullet"),
            ("Refresh Names from Game", "highlight"),
            (" in the top-right corner. This parses game files to resolve encrypted IDs into readable item, skill, and trader names.\n\n\n", "bullet"),

            ("★ INVENTORY EDITOR ★\n\n", "header"),
            ("• Expand Folders: ", "bullet"),
            ("Double-click", "highlight"),
            (" on category/tab folders to expand their items.\n", "bullet"),
            ("• Item Management: ", "bullet"),
            ("Right-click", "highlight"),
            (" on any item to open the action context menu:\n", "bullet"),
            ("  - Repair Item: ", "highlight"),
            ("Restores item durability back to 100%.\n", "bullet"),
            ("  - Duplicate Item: ", "highlight"),
            ("Creates a clone and asks which container it goes into; the original's own container is the default and Inbox is always available.\n", "bullet"),
            ("  - Delete Item: ", "highlight"),
            ("Removes the item and everything attached to it. To drop a single attachment "
             "instead, expand the item and right-click that attachment's own row. Warehouse "
             "tabs and storage roots are refused - they are part of the save's layout, not "
             "items.\n\n\n", "bullet"),
            
            ("★ GAME ITEMS (SPAWNER CATALOG) ★\n\n", "header"),
            ("• Search & Filter: ", "bullet"),
            ("Filter by item categories or search for specific item names.\n", "bullet"),
            ("• Spawn Items: ", "bullet"),
            ("Right-click an item template in the list and pick ", "bullet"),
            ("Add to Inventory", "highlight"),
            (" and the editor then asks where it should go.\n", "bullet"),
            ("• Where it goes: ", "bullet"),
            ("The list names every container with room and how much of it. A free spot is searched for there, and the item is turned 90° only if it fits no other way. Several items are placed one by one, so you are told if only part of a batch fits.\n", "bullet"),
            ("• Inbox: ", "bullet"),
            ("Always offered, also when everything is full. The item is stored without a grid position, so the game cannot place it and hands it to you as mail - which is where anything without room ends up anyway.\n", "bullet"),
            ("• Weapons reserve more than they show: ", "bullet"),
            ("a rifle drawn 2x1 can keep a 6x2 area unusable. That is the game's own behaviour; the editor reserves the full area so nothing lands on top of it.\n", "bullet"),
            ("• Sell at a Trader: ", "bullet"),
            ("Right-click and pick ", "bullet"),
            ("Offer at Trader...", "highlight"),
            (" to put the item into one of a trader's existing offer slots at your own price. "
             "The trader's next stock refresh undoes it; the same dialog can undo it sooner.\n\n\n", "bullet"),

            ("★ MAILBOX EDITOR ★\n\n", "header"),
            ("• View & Read: ", "bullet"),
            ("Check list of messages, senders, read-status, and attached rewards.\n", "bullet"),
            ("• Delete Letter: ", "bullet"),
            ("Select a letter and click ", "bullet"),
            ("Delete selected letter", "highlight"),
            (" to permanently remove it.\n\n\n", "bullet"),

            ("★ ☢ HACKERMAN'S LAB ☢ ★\n\n", "header"),
            ("• Profile Settings: ", "bullet"),
            ("Edit nickname, level, and experience points in the left pane.\n", "bullet"),
            ("Unspent skill points sit there too, and are deliberately not capped - the level itself is, at 25. A Counters sub-tab shows the account's sessions, last run and lifetime totals, read-only.\n", "bullet"),
            ("Set the level first, then the experience points if you want them: changing the level resets them to 0, so doing it the other way round throws your entry away. The most you can enter is one below the next level's goal - landing on it would level you up. The number beside each field is its limit.\n", "bullet"),
            ("• Character Skills: ", "bullet"),
            ("Select a skill from the list, input level, and click ", "bullet"),
            ("Set Level", "highlight"),
            (". The list shows level and maximum, and every skill has its own ceiling taken from the game data - Combat stops at 6, Lockpicking at 5. Higher values are refused because the game would not accept them.\n", "bullet"),
            ("• Trader Balances: ", "bullet"),
            ("Select a trader, adjust level or balance, and click ", "bullet"),
            ("Set Stats", "highlight"),
            (".\n", "bullet"),
            ("• Cheats: ", "bullet"),
            ("Use one-click buttons to max out all skills, credit 1,000,000 to all traders, or fully repair all items in the save.\n\n\n", "bullet"),
            
            ("★ SAVING YOUR CHANGES ★\n\n", "header"),
            ("• Apply Edits: ", "bullet"),
            ("Click ", "bullet"),
            ("Apply Changes", "highlight"),
            (" at the top right to save all edits to your file.\n", "bullet"),
            ("• Undo Edits: ", "bullet"),
            ("Click ", "bullet"),
            ("Discard Changes", "highlight"),
            (" to revert any unsaved modifications.\n", "bullet"),
            ("• Backups: ", "bullet"),
            ("Every apply first copies your save, with a timestamp, into the ", "bullet"),
            ("backups", "highlight"),
            (" folder next to this program. Nothing there is ever overwritten. ", "bullet"),
            ("Keep backups", "highlight"),
            (" in the bottom right sets how many are kept - once the next one is written, "
             "anything older than that is deleted. Set it to 0 to keep every backup.\n\n\n", "bullet"),

            ("★ SUPPORT THE PROJECT ★\n\n", "header"),
            ("• Support on Ko-fi: ", "bullet"),
            ("If you enjoy using this free save editor, consider supporting development on Ko-fi:\n", "bullet"),
            ("https://ko-fi.com/sirnr1\n", "link"),
        ]

        self.help_text_de = [
            ("★ SPIELNAMEN AKTUALISIEREN ★\n\n", "header"),
            ("• Assets scannen: ", "bullet"),
            ("Klicke auf ", "bullet"),
            ("Spielnamen aktualisieren", "highlight"),
            (" in der oberen rechten Ecke. Dies analysiert die Spieldateien, um kryptische IDs in lesbare Gegenstands-, Skill- und Händlernamen aufzulösen.\n\n\n", "bullet"),

            ("★ INVENTAR-EDITOR ★\n\n", "header"),
            ("• Ordner erweitern: ", "bullet"),
            ("Doppelklicke", "highlight"),
            (" auf Kategorie- oder Reiter-Ordner, um deren Inhalt anzuzeigen.\n", "bullet"),
            ("• Gegenstandsverwaltung: ", "bullet"),
            ("Klicke mit der rechten Maustaste", "highlight"),
            (" auf einen beliebigen Gegenstand, um das Kontextmenü zu öffnen:\n", "bullet"),
            ("  - Gegenstand reparieren: ", "highlight"),
            ("Setzt die Haltbarkeit des Gegenstands auf 100% zurück.\n", "bullet"),
            ("  - Gegenstand duplizieren: ", "highlight"),
            ("Erstellt eine Kopie und fragt, in welchen Behälter sie soll; vorgegeben ist der Behälter des Originals, der Posteingang steht immer zur Wahl.\n", "bullet"),
            ("  - Gegenstand löschen: ", "highlight"),
            ("Entfernt den Gegenstand samt allem, was daran hängt. Um nur einen einzelnen "
             "Anbauteil zu entfernen, klappe den Gegenstand auf und mache den Rechtsklick auf "
             "die Zeile des Anbauteils. Lagerreiter und Container-Wurzeln werden abgelehnt - "
             "sie gehören zum Aufbau des Saves und sind keine Gegenstände.\n\n\n", "bullet"),
            
            ("★ GEGENSTANDSSPAWNER (KATALOG) ★\n\n", "header"),
            ("• Suchen & Filtern: ", "bullet"),
            ("Filtere nach Kategorien oder suche nach bestimmten Namen.\n", "bullet"),
            ("• Gegenstände spawnen: ", "bullet"),
            ("Rechtsklick auf einen Gegenstand in der Liste, dann ", "bullet"),
            ("Ins Inventar spawnen", "highlight"),
            (" - der Editor fragt dann, wohin er soll.\n", "bullet"),
            ("• Wohin es kommt: ", "bullet"),
            ("Die Liste nennt jeden Behälter mit Platz und wie viel davon frei ist. Dort wird ein freier Platz gesucht, gedreht wird nur, wenn es sonst nicht passt. Mehrere Gegenstände werden einzeln platziert; passt nur ein Teil, wird es dir gesagt.\n", "bullet"),
            ("• Posteingang: ", "bullet"),
            ("Steht immer zur Wahl, auch wenn alles voll ist. Der Gegenstand wird ohne Rasterposition abgelegt, das Spiel kann ihn nicht platzieren und gibt ihn dir als Post - dort landet ohnehin alles, was keinen Platz findet.\n", "bullet"),
            ("• Waffen belegen mehr als sie zeigen: ", "bullet"),
            ("ein als 2x1 gezeichnetes Gewehr kann 6x2 sperren. Das macht das Spiel so; der Editor reserviert die volle Fläche, damit nichts darauf landet.\n", "bullet"),
            ("• Beim Händler verkaufen: ", "bullet"),
            ("Rechtsklick, dann ", "bullet"),
            ("Beim Händler anbieten...", "highlight"),
            (" legt den Gegenstand zu deinem Preis in einen bestehenden Angebots-Slot eines "
             "Händlers. Das nächste Sortiments-Update des Händlers macht das rückgängig, "
             "derselbe Dialog kann es auch früher.\n\n\n", "bullet"),

            ("★ POSTFACH-EDITOR ★\n\n", "header"),
            ("• Anzeigen & Lesen: ", "bullet"),
            ("Überprüfe Nachrichten, Absender, Lesestatus und angehängte Belohnungen.\n", "bullet"),
            ("• Brief löschen: ", "bullet"),
            ("Wähle einen Brief aus und klicke auf ", "bullet"),
            ("Ausgewählten Brief löschen", "highlight"),
            (" um ihn dauerhaft zu entfernen.\n\n\n", "bullet"),

            ("★ ☢ HACKERMANS LABOR ☢ ★\n\n", "header"),
            ("• Profileinstellungen: ", "bullet"),
            ("Bearbeite Nickname, Level und Erfahrungspunkte im linken Bereich.\n", "bullet"),
            ("Dort stehen auch die freien Skillpunkte, die bewusst unbegrenzt sind - das Level selbst ist es nicht, bei 25 ist Schluss. Der Reiter Statistik zeigt Sitzungen, letzte Runde und Gesamtwerte des Kontos, nur zur Ansicht.\n", "bullet"),
            ("Setze zuerst das Level und danach die Erfahrungspunkte, falls du sie willst: ein Levelwechsel setzt sie auf 0, umgekehrt wirfst du deine Eingabe also weg. Mehr als eins unter dem Ziel der nächsten Stufe geht nicht - genau darauf würdest du aufsteigen. Die Zahl neben jedem Feld ist dessen Grenze.\n", "bullet"),
            ("• Charakterskills: ", "bullet"),
            ("Wähle einen Skill aus, gib das Level ein und klicke auf ", "bullet"),
            ("Level setzen", "highlight"),
            (". Die Liste zeigt Stufe und Maximum, und jeder Skill hat seine eigene Obergrenze aus den Spieldaten - Kampf endet bei 6, Schlossknacken bei 5. Höhere Werte werden abgelehnt, weil das Spiel sie nicht annehmen würde.\n", "bullet"),
            ("• Händlerguthaben: ", "bullet"),
            ("Wähle einen Händler aus, passe Level oder Guthaben an und klicke auf ", "bullet"),
            ("Werte setzen", "highlight"),
            (".\n", "bullet"),
            ("• Cheats: ", "bullet"),
            ("Nutze One-Click-Cheats, um alle Skills zu maximieren, 1.000.000 Credits an alle Händler zu übertragen oder alle Gegenstände vollständig zu reparieren.\n\n\n", "bullet"),
            
            ("★ ÄNDERUNGEN SPEICHERN ★\n\n", "header"),
            ("• Änderungen übernehmen: ", "bullet"),
            ("Klicke oben rechts auf ", "bullet"),
            ("Änderungen übernehmen", "highlight"),
            (" um deine Datei zu aktualisieren.\n", "bullet"),
            ("• Änderungen verwerfen: ", "bullet"),
            ("Klicke auf ", "bullet"),
            ("Änderungen verwerfen", "highlight"),
            (" um alle ungespeicherten Änderungen rückgängig zu machen.\n", "bullet"),
            ("• Backups: ", "bullet"),
            ("Jedes Übernehmen kopiert deinen Spielstand vorher mit Zeitstempel in den Ordner ", "bullet"),
            ("backups", "highlight"),
            (" neben diesem Programm. Dort wird nie etwas überschrieben. ", "bullet"),
            ("Backups behalten", "highlight"),
            (" unten rechts legt fest, wie viele aufbewahrt werden - sobald das nächste "
             "geschrieben wird, verschwindet alles Ältere darüber hinaus. Mit 0 bleibt "
             "jedes Backup erhalten.\n\n\n", "bullet"),

            ("★ PROJEKT UNTERSTÜTZEN ★\n\n", "header"),
            ("• Auf Ko-fi unterstützen: ", "bullet"),
            ("Wenn dir dieser kostenlose Speicherstand-Editor gefällt, kannst du die Entwicklung auf Ko-fi unterstützen:\n", "bullet"),
            ("https://ko-fi.com/sirnr1\n", "link"),
        ]

        self.help_text_ru = [
            ("★ ОБНОВЛЕНИЕ ИГРОВЫХ ИМЕН ★\n\n", "header"),
            ("• Сканирование ресурсов: ", "bullet"),
            ("Нажмите кнопку ", "bullet"),
            ("Обновить имена из игры", "highlight"),
            (" в правом верхнем углу окна. Это просканирует файлы игры для сопоставления зашифрованных ID с реальными именами предметов, навыков и торговцев.\n\n\n", "bullet"),

            ("★ РЕДАКТОР ИНВЕНТАРЯ ★\n\n", "header"),
            ("• Развернуть папки: ", "bullet"),
            ("Дважды щелкните", "highlight"),
            (" по папкам категорий, чтобы показать их содержимое.\n", "bullet"),
            ("• Управление предметами: ", "bullet"),
            ("Нажмите правой кнопкой мыши", "highlight"),
            (" по любому предмету для открытия контекстного меню:\n", "bullet"),
            ("  - Починить предмет: ", "highlight"),
            ("Восстанавливает прочность предмета до 100%.\n", "bullet"),
            ("  - Дублировать предмет: ", "highlight"),
            ("Создаёт копию и спрашивает, в какой контейнер её поместить; по умолчанию — контейнер оригинала, Входящие доступны всегда.\n", "bullet"),
            ("  - Удалить предмет: ", "highlight"),
            ("Удаляет предмет вместе со всем, что к нему присоединено. Чтобы снять только "
             "одно вложение, разверните предмет и нажмите правой кнопкой по строке самого "
             "вложения. Вкладки склада и корневые контейнеры удалить нельзя - они часть "
             "структуры сохранения, а не предметы.\n\n\n", "bullet"),
            
            ("★ СПАВН ПРЕДМЕТОВ (КАТАЛОГ) ★\n\n", "header"),
            ("• Поиск и фильтрация: ", "bullet"),
            ("Фильтруйте по категориям или ищите предметы по названию.\n", "bullet"),
            ("• Спавн предметов: ", "bullet"),
            ("Щёлкните предмет в списке правой кнопкой и выберите ", "bullet"),
            ("Добавить в инвентарь", "highlight"),
            (" - редактор спросит, куда его положить.\n", "bullet"),
            ("• Куда попадёт: ", "bullet"),
            ("В списке указан каждый контейнер со свободным местом. Там ищется свободная ячейка; поворот на 90° — только если иначе не влезает.\n", "bullet"),
            ("• Входящие: ", "bullet"),
            ("Доступно всегда, даже когда всё заполнено. Предмет сохраняется без позиции, и игра выдаёт его письмом.\n", "bullet"),
            ("• Оружие занимает больше, чем кажется: ", "bullet"),
            ("винтовка 2x1 может блокировать 6x2. Редактор резервирует всю площадь.\n", "bullet"),
            ("• Продажа у торговца: ", "bullet"),
            ("Правый щелчок, затем ", "bullet"),
            ("Предложить у торговца...", "highlight"),
            (" помещает предмет в существующий слот предложения торговца по вашей цене. "
             "Следующее обновление ассортимента отменит это; тот же диалог может отменить раньше.\n\n\n", "bullet"),

            ("★ РЕДАКТОР ПОЧТОВОГО ЯЩИКА ★\n\n", "header"),
            ("• Просмотр и чтение: ", "bullet"),
            ("Проверяйте сообщения, отправителей, статус прочтения и прикрепленные награды.\n", "bullet"),
            ("• Удалить письмо: ", "bullet"),
            ("Выберите письмо и нажмите ", "bullet"),
            ("Удалить выбранное письмо", "highlight"),
            (" для его безвозвратного удаления.\n\n\n", "bullet"),

            ("★ ☢ ЛАБОРАТОРИЯ ХАКЕРА ☢ ★\n\n", "header"),
            ("• Настройки профиля: ", "bullet"),
            ("Редактируйте никнейм, уровень и опыт в левой панели.\n", "bullet"),
            ("Там же свободные очки навыков - они намеренно без предела, а вот уровень ограничен 25. Вкладка Статистика показывает сессии, последний рейд и общие итоги аккаунта, только для просмотра.\n", "bullet"),
            ("Сначала задайте уровень, потом опыт, если он вам нужен: смена уровня обнуляет его, поэтому в обратном порядке ввод пропадёт. Больше, чем на единицу ниже цели следующего уровня, ввести нельзя - ровно на ней вы бы поднялись. Число рядом с полем - его предел.\n", "bullet"),
            ("• Навыки персонажа: ", "bullet"),
            ("Выберите навык из списка, введите уровень и нажмите ", "bullet"),
            ("Задать уровень", "highlight"),
            (". В списке показаны уровень и максимум: у каждого навыка свой предел из данных игры - бой заканчивается на 6, взлом на 5. Более высокие значения отклоняются, потому что игра их не примет.\n", "bullet"),
            ("• Управление торговцами: ", "bullet"),
            ("Выберите торговца, измените его уровень или баланс и нажмите ", "bullet"),
            ("Задать параметры", "highlight"),
            (".\n", "bullet"),
            ("• Читы: ", "bullet"),
            ("Используйте читы в один клик для максимизации навыков, заполнения баланса торговцев (+1млн кредитов) или полной починки вещей.\n\n\n", "bullet"),
            
            ("★ СОХРАНЕНИЕ ИЗМЕНЕНИЙ ★\n\n", "header"),
            ("• Применить изменения: ", "bullet"),
            ("Нажмите ", "bullet"),
            ("Применить изменения", "highlight"),
            (" в верхнем правом углу для сохранения файла.\n", "bullet"),
            ("• Сбросить изменения: ", "bullet"),
            ("Нажмите ", "bullet"),
            ("Сбросить изменения", "highlight"),
            (" для отмены всех несохраненных изменений.\n", "bullet"),
            ("• Резервные копии: ", "bullet"),
            ("Каждое применение сначала копирует сохранение с отметкой времени в папку ", "bullet"),
            ("backups", "highlight"),
            (" рядом с программой. Там ничего никогда не перезаписывается. ", "bullet"),
            ("Хранить копий", "highlight"),
            (" в правом нижнем углу задаёт, сколько копий остаётся: как только будет "
             "записана следующая, всё более старое сверх этого числа удаляется. "
             "Значение 0 сохраняет все копии.\n\n\n", "bullet"),

            ("★ ПОДДЕРЖАТЬ ПРОЕКТ ★\n\n", "header"),
            ("• Поддержать на Ko-fi: ", "bullet"),
            ("Если вам нравится этот бесплатный редактор, вы можете поддержать разработку по ссылке:\n", "bullet"),
            ("https://ko-fi.com/sirnr1\n", "link"),
        ]
        
        # Determine current language and populate text area
        lang = self.current_lang if hasattr(self, "current_lang") else self._get_system_language()
        if lang == "de":
            help_text = self.help_text_de
        elif lang == "ru":
            help_text = self.help_text_ru
        else:
            help_text = self.help_text_en

        for text, tag in help_text:
            self.help_text_area.insert("end", text, tag)
            
        self.help_text_area.configure(state="disabled")

    def _build_char_tab(self, parent: ttk.Frame) -> None:
        # Packed before the panes so it claims the top strip.
        char_toolbar = ttk.Frame(parent)
        char_toolbar.pack(side="top", fill="x", padx=10, pady=(10, 0))
        self.char_discard_button = ttk.Button(
            char_toolbar,
            command=self._discard_pending_changes,
        )
        self.char_discard_button.pack(side="right", padx=(6, 0))
        self.char_apply_button = ttk.Button(
            char_toolbar,
            command=self._apply_pending_changes,
        )
        self.char_apply_button.pack(side="right")

        # Create left pane for warning, profile, and cheats
        left_pane = ttk.Frame(parent)
        left_pane.pack(side="left", fill="both", expand=False, padx=10, pady=10)

        # Create right pane for skills/traders notebook
        right_pane = ttk.Frame(parent)
        right_pane.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # 1. Warning Banner Frame
        self.warning_frame = tk.Frame(
            left_pane,
            bg="#4a1515",
            highlightbackground="#ff3333",
            highlightthickness=1
        )
        self.warning_frame.pack(fill="x", pady=(0, 10))

        # Wrapped to a fixed width so the banner grows downwards instead of stretching the
        # whole left column - the untranslated text is a single long line.
        self.warning_title = tk.Label(
            self.warning_frame,
            text="",
            font=("TkDefaultFont", 10, "bold"),
            fg="#ff5555",
            bg="#4a1515",
            justify="left",
            anchor="w",
            wraplength=WARNING_WRAPLENGTH,
            padx=10,
            pady=5
        )
        self.warning_title.pack(fill="x")

        self.warning_desc = tk.Label(
            self.warning_frame,
            text="",
            font=("TkDefaultFont", 9),
            fg="#ffffff",
            bg="#4a1515",
            justify="left",
            anchor="w",
            wraplength=WARNING_WRAPLENGTH,
            padx=10,
            pady=5
        )
        self.warning_desc.pack(fill="x")

        # Initialize last_warn_data for unit tests
        self.last_warn_data = {
            "title": "",
            "desc": ""
        }

        # 2. Profile Details Frame
        self.profile_lf = ttk.LabelFrame(left_pane, padding=10)
        self.profile_lf.pack(fill="x", pady=(0, 10))

        self.nickname_lbl = ttk.Label(self.profile_lf)
        self.nickname_lbl.grid(row=0, column=0, sticky="w", pady=5)

        self.char_nickname_var = tk.StringVar()
        self.char_nickname_var.trace_add("write", self._on_char_profile_changed)
        self.nickname_entry = ttk.Entry(self.profile_lf, textvariable=self.char_nickname_var, width=25)
        # Avoid autofocus - do not focus/autofocus the entry widget
        self.nickname_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        self.level_lbl = ttk.Label(self.profile_lf)
        self.level_lbl.grid(row=1, column=0, sticky="w", pady=5)

        self.char_level_var = tk.StringVar()
        self.char_level_var.trace_add("write", self._on_char_profile_changed)
        self.level_entry = ttk.Entry(self.profile_lf, textvariable=self.char_level_var, width=10)
        self.level_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.level_entry.bind("<FocusOut>", self._snap_char_level)
        self.level_entry.bind("<Return>", self._snap_char_level)

        # The ceiling, spelled out next to the field it applies to - the same "3 / 5" idiom
        # the skills list already uses. It also answers why a typed 900 turns red.
        self.level_max_lbl = ttk.Label(self.profile_lf, style="Hint.TLabel")
        self.level_max_lbl.grid(row=1, column=2, sticky="w", padx=(0, 5))

        self.xp_lbl = ttk.Label(self.profile_lf)
        self.xp_lbl.grid(row=2, column=0, sticky="w", pady=5)

        self.char_xp_var = tk.StringVar()
        self.char_xp_var.trace_add("write", self._on_char_profile_changed)
        self.xp_entry = ttk.Entry(self.profile_lf, textvariable=self.char_xp_var, width=15)
        self.xp_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        self.xp_entry.bind("<FocusOut>", self._snap_char_xp)
        self.xp_entry.bind("<Return>", self._snap_char_xp)

        # The XP needed for the next level. Blank when no mapping report is loaded, because
        # then there is nothing to compute it from and the field is unbounded.
        self.xp_goal_lbl = ttk.Label(self.profile_lf, style="Hint.TLabel")
        self.xp_goal_lbl.grid(row=2, column=2, sticky="w", padx=(0, 5))

        # Unspent skill points. Deliberately **not** capped at what the level grants (24 at
        # level 25, one per level-up): "Max Out All Skills" already costs 62 and blows that
        # budget wide open, so limiting the field next to that button would be for show. The
        # tab carries a brick warning; this is what it is for.
        self.skill_points_lbl = ttk.Label(self.profile_lf)
        self.skill_points_lbl.grid(row=3, column=0, sticky="w", pady=5)

        self.char_skill_points_var = tk.StringVar()
        self.char_skill_points_var.trace_add("write", self._on_char_profile_changed)
        self.skill_points_entry = ttk.Entry(
            self.profile_lf, textvariable=self.char_skill_points_var, width=10)
        self.skill_points_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)

        # 3. Cheats Frame
        self.cheats_lf = ttk.LabelFrame(left_pane, padding=10)
        self.cheats_lf.pack(fill="x")

        self.cheat_repair_all_btn = ttk.Button(self.cheats_lf, command=self._cheat_repair_all)
        self.cheat_repair_all_btn.pack(fill="x", pady=5)

        self.cheat_max_skills_btn = ttk.Button(self.cheats_lf, command=self._cheat_max_skills)
        self.cheat_max_skills_btn.pack(fill="x", pady=5)

        self.cheat_fill_trader_btn = ttk.Button(self.cheats_lf, command=self._cheat_fill_trader_balances)
        self.cheat_fill_trader_btn.pack(fill="x", pady=5)

        # 4. Right Pane Subnotebook (Skills & Traders)
        self.right_nb = ttk.Notebook(right_pane)
        self.right_nb.pack(fill="both", expand=True)

        self.tab_skills = ttk.Frame(self.right_nb)
        self.tab_traders = ttk.Frame(self.right_nb)
        self.tab_counters = ttk.Frame(self.right_nb)

        self.right_nb.add(self.tab_skills, text="")
        self.right_nb.add(self.tab_traders, text="")
        self.right_nb.add(self.tab_counters, text="")

        # Skills Layout
        skills_tree_frame = ttk.Frame(self.tab_skills)
        skills_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        skills_scroll = ttk.Scrollbar(skills_tree_frame, orient="vertical")
        skills_scroll.pack(side="right", fill="y")

        self.skills_tree = ttk.Treeview(
            skills_tree_frame,
            columns=("id", "name", "level"),
            show="headings",
            selectmode="browse",
            yscrollcommand=skills_scroll.set
        )
        skills_scroll.configure(command=self.skills_tree.yview)
        self.skills_tree.pack(side="left", fill="both", expand=True)

        self.skills_tree.column("id", width=60, anchor="center")
        self.skills_tree.column("name", width=200, anchor="w")
        self.skills_tree.column("level", width=80, anchor="center")

        self.skills_tree.bind("<<TreeviewSelect>>", self._on_skill_selected)

        skills_control_frame = ttk.Frame(self.tab_skills, padding=(5, 8))
        skills_control_frame.pack(fill="x", pady=5)

        self.skill_level_lbl = ttk.Label(skills_control_frame)
        self.skill_level_lbl.pack(side="left", padx=(5, 10))

        # Three controls of one size, taking their measurements from the widest of them.
        # LEVEL_CONTROL_WIDTH is in characters and the styles are tuned so all three render
        # the same height - a row of differently sized boxes was the complaint that started
        # this. The spinbox arrows are the only stepper; separate minus and plus buttons were
        # tried and removed as redundant.
        self.skill_level_var = tk.StringVar(value="0")
        self.skill_spin = ttk.Spinbox(
            skills_control_frame,
            from_=0,
            to=10,
            textvariable=self.skill_level_var,
            width=LEVEL_SPIN_WIDTH,
            justify="center",
            font=LEVEL_SPIN_FONT,
            style="Level.TSpinbox",
            command=self._apply_skill_spin,
        )
        self.skill_spin.pack(side="left")
        # Typing a level and pressing Return applies it too - the button is for the mouse.
        self.skill_spin.bind("<Return>", lambda _e: self._set_selected_skill_level())

        self.skill_max_btn = ttk.Button(skills_control_frame, width=LEVEL_CONTROL_WIDTH,
                                        style="Step.TButton",
                                        command=self._max_selected_skill_level)
        self.skill_max_btn.pack(side="left", padx=8)

        self.set_skill_btn = ttk.Button(skills_control_frame, width=LEVEL_CONTROL_WIDTH,
                                        command=self._set_selected_skill_level)
        self.set_skill_btn.pack(side="left")

        # Traders Layout
        traders_tree_frame = ttk.Frame(self.tab_traders)
        traders_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        traders_scroll = ttk.Scrollbar(traders_tree_frame, orient="vertical")
        traders_scroll.pack(side="right", fill="y")

        self.traders_tree = ttk.Treeview(
            traders_tree_frame,
            columns=("id", "template_id", "name", "trader_level", "balance"),
            show="headings",
            selectmode="browse",
            yscrollcommand=traders_scroll.set
        )
        traders_scroll.configure(command=self.traders_tree.yview)
        self.traders_tree.pack(side="left", fill="both", expand=True)

        self.traders_tree.column("id", width=80, anchor="w")
        self.traders_tree.column("template_id", width=80, anchor="w")
        self.traders_tree.column("name", width=180, anchor="w")
        self.traders_tree.column("trader_level", width=100, anchor="center")
        self.traders_tree.column("balance", width=150, anchor="e")

        self.traders_tree.configure(displaycolumns=("name", "trader_level", "balance"))
        self.traders_tree.bind("<<TreeviewSelect>>", self._on_trader_selected)

        traders_control_frame = ttk.Frame(self.tab_traders, padding=(5, 8))
        traders_control_frame.pack(fill="x", pady=5)

        self.trader_level_lbl = ttk.Label(traders_control_frame)
        self.trader_level_lbl.pack(side="left", padx=(5, 10))

        # Same control as the skills tab, down to the sizes - the two tabs sit in the same
        # notebook and a level is a level.
        self.trader_level_var = tk.StringVar(value="1")
        self.trader_level_spin = ttk.Spinbox(
            traders_control_frame,
            from_=TRADER_LEVEL_MIN,
            # _load_template_name_map() runs before the widgets are built, so the report's
            # ceiling is already known here; _refresh_traders_list re-applies it after a
            # "Refresh Names from Game" run has replaced the report underneath.
            to=self._max_level_for_account(),
            textvariable=self.trader_level_var,
            width=LEVEL_SPIN_WIDTH,
            justify="center",
            font=LEVEL_SPIN_FONT,
            style="Level.TSpinbox",
        )
        self.trader_level_spin.pack(side="left")

        self.trader_max_btn = ttk.Button(traders_control_frame, width=LEVEL_CONTROL_WIDTH,
                                         style="Step.TButton",
                                         command=self._max_trader_level)
        self.trader_max_btn.pack(side="left", padx=8)

        self.trader_balance_lbl = ttk.Label(traders_control_frame)
        self.trader_balance_lbl.pack(side="left", padx=5)

        self.trader_balance_var = tk.StringVar(value="0")
        self.trader_balance_entry = ttk.Entry(
            traders_control_frame,
            textvariable=self.trader_balance_var,
            width=12
        )
        self.trader_balance_entry.pack(side="left", padx=5)

        self.set_trader_btn = ttk.Button(traders_control_frame, command=self._set_selected_trader_stats)
        self.set_trader_btn.pack(side="left", padx=5)

        # Counters Layout - read-only. Nothing in here changes what the game does; it is the
        # account's own record of sessions, kills, distance and loot.
        counters_tree_frame = ttk.Frame(self.tab_counters)
        counters_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        counters_scroll = ttk.Scrollbar(counters_tree_frame, orient="vertical")
        counters_scroll.pack(side="right", fill="y")

        self.counters_tree = ttk.Treeview(
            counters_tree_frame,
            columns=("group", "stat", "value", "updated"),
            show="headings",
            selectmode="browse",
            yscrollcommand=counters_scroll.set,
        )
        counters_scroll.configure(command=self.counters_tree.yview)
        self.counters_tree.pack(side="left", fill="both", expand=True)

        self.counters_tree.column("group", width=130, anchor="w")
        self.counters_tree.column("stat", width=200, anchor="w")
        self.counters_tree.column("value", width=120, anchor="e")
        self.counters_tree.column("updated", width=170, anchor="w")

        self.counters_hint = ttk.Label(self.tab_counters, style="Hint.TLabel",
                                       wraplength=520, justify="left")
        self.counters_hint.pack(anchor="w", padx=5, pady=(0, 5))

    def _max_xp_for_level(self, level: int) -> int | None:
        """The highest XP this level may hold, or None without the coefficients.

        One below the goal: landing exactly on the goal is a level-up, and XP is not allowed
        to move the level. At the ceiling there is no next level to trigger, so the goal
        itself is fine - and it is what a real save carries there, 62000 of 62000.
        """
        goal = self._xp_goal_for_level(level)
        if goal is None:
            return None
        if int(level) >= self._max_level_for_account():
            return goal
        return max(0, goal - 1)

    def _update_char_bounds(self) -> None:
        """Writes the two ceilings beside their fields. Skill points get none on purpose -
        they have no ceiling, and the missing hint is the difference made visible."""
        self.level_max_lbl.configure(text=f"/ {self._max_level_for_account()}")
        top = self._max_xp_for_level(
            self.manager.data.get("AccountDto", {}).get("ExperienceDto", {}).get("Level", 0))
        self.xp_goal_lbl.configure(text="" if top is None else f"/ {top}")

    def _snap_char_level(self, _event=None) -> None:
        """Pulls an out-of-range level back into range when the field is left.

        Clamping on every keystroke would make the field unusable - typing "25" passes
        through "2", and typing "9" of an intended "9" is already over the ceiling. So the
        value is refused while it is being typed and corrected once the user is done.
        """
        ceiling = self._max_level_for_account()
        try:
            level = int(self.char_level_var.get())
        except ValueError:
            level = self.manager.data.get("AccountDto", {}).get("ExperienceDto", {}).get("Level", 0)
        snapped = max(0, min(ceiling, int(level)))
        if self.char_level_var.get() != str(snapped):
            self.char_level_var.set(str(snapped))
        self.level_entry.configure(style="TEntry")

        # A changed level makes the old XP meaningless - it counted towards a different goal -
        # so the bar restarts at zero. Untouched level, untouched XP: tabbing through the form
        # must not rewrite it.
        if snapped != getattr(self, "_char_level_before_edit", snapped):
            self.char_xp_var.set("0")
        self._char_level_before_edit = snapped
        self.xp_entry.configure(style="TEntry")
        self._update_char_bounds()

    def _snap_char_xp(self, _event=None) -> None:
        """Pulls the typed XP into 0..goal. The level is left alone.

        Letting XP roll over into levels was tried and dropped: the level is the value that
        matters, and having the two fields push each other around made the order of editing
        matter in a way nobody should have to think about. Set the level, then the XP - which
        is what the Help tab says.
        """
        exp_dto = self.manager.data.setdefault("AccountDto", {}).setdefault("ExperienceDto", {})
        top = self._max_xp_for_level(exp_dto.get("Level", 0))
        try:
            xp = max(0, int(self.char_xp_var.get()))
        except ValueError:
            xp = max(0, int(exp_dto.get("ExperiencePoints", 0) or 0))
        if top is not None:
            xp = min(xp, top)

        if self.char_xp_var.get() != str(xp):
            self.char_xp_var.set(str(xp))
        self.xp_entry.configure(style="TEntry")
        self._update_char_bounds()

    def _on_char_profile_changed(self, *args) -> None:
        if getattr(self, "_updating_char_fields", False):
            return

        account_dto = self.manager.data.setdefault("AccountDto", {})
        exp_dto = account_dto.setdefault("ExperienceDto", {})

        nickname = self.char_nickname_var.get()
        account_dto["Nickname"] = nickname

        # The level is capped at `MaxLevel` from the game data, 25 at the time of writing.
        # Out of range, nothing is written and the field goes red: silently storing 25 while
        # the box still read 900 meant applying a different value than the one on screen.
        # Leaving the field snaps it to the ceiling - see _snap_char_level.
        try:
            level = int(self.char_level_var.get())
        except ValueError:
            level = None
        if level is not None and 0 <= level <= self._max_level_for_account():
            exp_dto["Level"] = level
            self.level_entry.configure(style="TEntry")
        else:
            self.level_entry.configure(style="Invalid.TEntry")

        # The goal follows the level rather than being typed: it is computable from the game
        # data, and a level changed without it leaves the XP bar measuring against the old one.
        goal = self._xp_goal_for_level(exp_dto.get("Level", 0))
        if goal is not None:
            exp_dto["NextLevelExperienceGoal"] = goal

        # XP is progress *within* the level, not a running total, and it may not reach the
        # goal: that would be a level-up, and XP is not allowed to move the level. Same
        # treatment as the level field - refused and marked while typing, snapped on leaving.
        top = self._max_xp_for_level(exp_dto.get("Level", 0))
        try:
            xp = int(self.char_xp_var.get())
        except ValueError:
            xp = None
        if xp is not None and xp >= 0 and (top is None or xp <= top):
            exp_dto["ExperiencePoints"] = xp
            self.xp_entry.configure(style="TEntry")
        else:
            self.xp_entry.configure(style="Invalid.TEntry")

        self._update_char_bounds()

        skills_dto = account_dto.setdefault("SkillsDto", {})
        try:
            points = max(0, int(self.char_skill_points_var.get()))
            # Zero means "no such key". The game omits any field holding its type's default,
            # which is exactly why this one was invisible until six points were freed up -
            # the same rule that hides a zero Position and an empty equipment slot.
            if points:
                skills_dto["SkillPointsCount"] = points
            else:
                skills_dto.pop("SkillPointsCount", None)
        except ValueError:
            pass

        self._mark_pending_changes("Modified character profile (not saved yet)")

    def _refresh_char_tab(self) -> None:
        self._updating_char_fields = True

        account_dto = self.manager.data.get("AccountDto", {})
        nickname = account_dto.get("Nickname", "")
        self.char_nickname_var.set(nickname)

        exp_dto = account_dto.get("ExperienceDto", {})
        level = exp_dto.get("Level", 0)
        self.char_level_var.set(str(level))

        xp = exp_dto.get("ExperiencePoints", 0)
        self.char_xp_var.set(str(xp))

        # Absent means zero here, not "unknown" - see _on_char_profile_changed.
        skills_dto = account_dto.get("SkillsDto", {})
        self.char_skill_points_var.set(str(skills_dto.get("SkillPointsCount", 0)))
        # What the level was before the user touched it, so leaving the field can tell an
        # actual change from a pass-through.
        self._char_level_before_edit = level

        self._updating_char_fields = False

        self._update_char_bounds()
        self._refresh_skills_list()
        self._refresh_traders_list()
        self._refresh_counters_list()

    # Skill ids as a last resort. The list is only used when the generated report carries no
    # skill data; `_active_skill_ids` prefers the game's own, which also knows which ones are
    # switched off instead of hardcoding an unexplained gap at 8 and 15.
    FALLBACK_SKILL_IDS = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14,
                          16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]

    def _active_skill_ids(self) -> list[int]:
        meta = getattr(self, "skills_meta", {})
        active = sorted(
            int(sid) for sid, row in meta.items()
            if isinstance(row, dict) and not row.get("is_disabled") and str(sid).isdigit()
        )
        return active or list(self.FALLBACK_SKILL_IDS)

    def _max_level_for_skill(self, skill_id: int) -> int:
        """The skill's own ceiling. `MaxVersion` in the game data despite the name - measured
        in-game: Combat and ItemFind stop at 6 and carry 6, Lockpick stops at 5 and carries 5.
        Falls back to 10, which is what the editor allowed for every skill before."""
        row = getattr(self, "skills_meta", {}).get(str(skill_id))
        if isinstance(row, dict) and isinstance(row.get("max_level"), int):
            if row["max_level"] > 0:
                return row["max_level"]
        return 10

    def _refresh_skills_list(self) -> None:
        for item in self.skills_tree.get_children():
            self.skills_tree.delete(item)

        skills_list = self.manager.data.get("AccountDto", {}).get("SkillsDto", {}).get("Skills", [])
        all_skill_ids = self._active_skill_ids()

        save_levels = {}
        for s in skills_list:
            s_id = s.get("Id")
            if s_id is not None:
                save_levels[int(s_id)] = s.get("Level", 0)

        for s_id in all_skill_ids:
            level = save_levels.get(s_id, 0)
            skill_name = self.skills_name_map.get(str(s_id), f"Skill {s_id}")
            self.skills_tree.insert(
                "",
                "end",
                values=(s_id, skill_name, f"{level} / {self._max_level_for_skill(s_id)}")
            )

    def _counter_group_label(self, group: dict) -> str:
        """A name for a counter group, derived from what it contains.

        The group's own `$t` is a numeric type hash - the same kind the item components use,
        which a game update can renumber, so it is not something to switch on. What the group
        holds is stable: one carries the session tally, and of the two run counters the one
        the game stamped with `LastSetAtUtc` is the run that just ended.
        """
        t = TRANSLATIONS[self.current_lang]
        stats = group.get("All") if isinstance(group.get("All"), dict) else {}
        if "SessionNumber" in stats:
            return t["counters_sessions"]
        if group.get("LastSetAtUtc"):
            return t["counters_last_run"]
        return t["counters_lifetime"]

    def _refresh_counters_list(self) -> None:
        for item in self.counters_tree.get_children():
            self.counters_tree.delete(item)

        counters = (self.manager.data.get("AccountDto", {}).get("Counters", {}) or {})
        groups = counters.get("Counters")
        if not isinstance(groups, list):
            groups = []

        rows = 0
        for group in groups:
            if not isinstance(group, dict):
                continue
            stats = group.get("All")
            if not isinstance(stats, dict):
                continue
            label = self._counter_group_label(group)
            stamp = str(group.get("LastSetAtUtc") or "").replace("T", " ")[:19]
            for name, value in stats.items():
                shown = f"{value:,}".replace(",", " ") if isinstance(value, int) else str(value)
                self.counters_tree.insert(
                    "", "end", values=(label, name, shown, stamp))
                rows += 1

        t = TRANSLATIONS[self.current_lang]
        self.counters_hint.configure(
            text=t["counters_hint"] if rows else t["counters_empty"])

    def _refresh_traders_list(self) -> None:
        # "Refresh Names from Game" can replace the report while the window is open, so the
        # ceiling is re-applied here rather than only at build time.
        self.trader_level_spin.configure(to=self._max_level_for_account())
        for item in self.traders_tree.get_children():
            self.traders_tree.delete(item)

        shops_list = self.manager.data.get("AccountShops", [])
        for shop in shops_list:
            instance_id = shop.get("Id")
            template_id = shop.get("ShopTemplateId")
            trader_level = shop.get("AccountLevel", 1)

            balance_dict = shop.get("Balance", {})
            currency_key = "cb567810-cc82-424f-893f-299c704ffb12"
            balance = balance_dict.get(currency_key, 0)

            trader_name = self.traders_name_map.get(template_id, "Unknown Trader")

            self.traders_tree.insert(
                "",
                "end",
                values=(instance_id, template_id, trader_name, trader_level, balance)
            )

    def _on_skill_selected(self, event=None) -> None:
        selected = self.skills_tree.selection()
        if not selected:
            return
        values = self.skills_tree.item(selected[0], "values")
        if values:
            # The level column reads "3 / 5" - only the level goes into the spinbox, and the
            # spinbox stops at that skill's own ceiling rather than a shared 10.
            self.skill_level_var.set(str(values[2]).split("/")[0].strip())
            self.skill_spin.configure(to=self._max_level_for_skill(int(values[0])))

    def _on_trader_selected(self, event=None) -> None:
        selected = self.traders_tree.selection()
        if not selected:
            return
        values = self.traders_tree.item(selected[0], "values")
        if values:
            self.trader_level_var.set(values[3])
            self.trader_balance_var.set(values[4])

    def _selected_skill_id(self) -> int | None:
        selected = self.skills_tree.selection()
        if not selected:
            return None
        values = self.skills_tree.item(selected[0], "values")
        return int(values[0]) if values else None

    def _skill_level_in_save(self, skill_id: int) -> int:
        """The level as staged, which is what minus and plus step from.

        Deliberately not the spinbox: it is refilled by <<TreeviewSelect>>, and Tk delivers
        that on the next idle rather than during the call that re-selects the row. Stepping
        from the widget would work in the running app and be one behind anywhere else.
        """
        skills = (self.manager.data.get("AccountDto", {})
                  .get("SkillsDto", {}).get("Skills", []))
        for skill in skills:
            if skill.get("Id") == skill_id:
                try:
                    return int(skill.get("Level") or 0)
                except (TypeError, ValueError):
                    return 0
        return 0

    def _write_skill_level(self, skill_id: int, new_level: int) -> None:
        """Stages the level, refills the readout and puts the selection back on the row."""
        t = TRANSLATIONS[self.current_lang]
        skills_list = self.manager.data.setdefault("AccountDto", {}).setdefault("SkillsDto", {}).setdefault("Skills", [])
        skill_item = next((s for s in skills_list if s.get("Id") == skill_id), None)
        if not skill_item:
            skill_item = {"Id": skill_id}
            skills_list.append(skill_item)

        skill_item["Level"] = new_level
        if "NextLevelExperienceGoal" not in skill_item:
            skill_item["NextLevelExperienceGoal"] = 2000

        self._refresh_skills_list()
        self.skill_level_var.set(str(new_level))
        for item in self.skills_tree.get_children():
            val = self.skills_tree.item(item, "values")
            if val and int(val[0]) == skill_id:
                self.skills_tree.selection_set(item)
                break

        self._mark_pending_changes(t["status_skill_set"].format(skill_id=skill_id, level=new_level))

    def _max_selected_skill_level(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        skill_id = self._selected_skill_id()
        if skill_id is None:
            messagebox.showwarning(t["title"], t["msg_no_item_selected"])
            return
        self._write_skill_level(skill_id, self._max_level_for_skill(skill_id))

    def _apply_skill_spin(self) -> None:
        """The spinbox's own arrows. They stay usable, they are just no longer the only way."""
        if self._selected_skill_id() is not None:
            self._set_selected_skill_level()

    def _set_selected_skill_level(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        skill_id = self._selected_skill_id()
        if skill_id is None:
            messagebox.showwarning(t["title"], t["msg_no_item_selected"])
            return

        # Each skill has its own ceiling from the game data, not a shared 10.
        max_level = self._max_level_for_skill(skill_id)
        try:
            new_level = int(self.skill_level_var.get())
            if not (0 <= new_level <= max_level):
                raise ValueError()
        except ValueError:
            messagebox.showerror(
                t["title"],
                t["msg_skill_level_range"].format(max_level=max_level),
            )
            return

        self._write_skill_level(skill_id, new_level)

    def _xp_goal_for_level(self, level: int) -> int | None:
        """`NextLevelExperienceGoal` for a character at this level, or None without the data.

        The game builds it as `level * Multiply + Sum`, both coefficients from the band the
        level falls into (1-4, 5-10, 11-28, 29-50). Checked against a real save: a level 25
        character carries 62000, and 24 * 3000 - 10000 is exactly that.

        Which is also the one uncertainty here. At the ceiling there is no next level, so the
        stored goal is the one that was needed to *reach* it - hence `level - 1` at the top.
        Whether a mid-level character carries `goal(level)` or `goal(level - 1)` could not be
        told apart from a single save that happens to sit at 25.
        """
        progress = getattr(self, "level_progress", {}) or {}
        multiply, summed = progress.get("xp_multiply"), progress.get("xp_sum")
        if not isinstance(multiply, list) or not isinstance(summed, list):
            return None

        ceiling = self._max_level_for_account()
        effective = min(max(int(level), 1), max(1, ceiling - 1))

        def band(bands):
            for entry in bands:
                if not isinstance(entry, dict):
                    continue
                lo, hi = entry.get("min_level"), entry.get("max_level")
                if isinstance(lo, int) and isinstance(hi, int) and lo <= effective <= hi:
                    return entry.get("coefficient")
            return None

        factor, offset = band(multiply), band(summed)
        if not isinstance(factor, (int, float)) or not isinstance(offset, (int, float)):
            return None
        return int(effective * factor + offset)

    def _max_level_for_account(self) -> int:
        """The account level ceiling, from the game data when the report carries it."""
        level = getattr(self, "max_account_level", None)
        if isinstance(level, int) and level > 0:
            return level
        return TRADER_LEVEL_MAX_FALLBACK

    def _balance_for_shop(self, shop: dict, currency_id: str) -> int:
        """This trader's maximum balance: `ShopBalance` in its template.

        **The game caps a balance at that value** - confirmed in-game on 2026-07-28 by
        writing a million and reading 500000 back. So the old flat million was never
        actually granted; it was silently cut down. 500000 for the two traders that sell and
        for QuickSell, 100 for the price-reference shop, nothing for the two raid shops.

        Reading it from the report rather than hardcoding it means the cheat follows a game
        update. A shop the report does not know falls back to the old flat value.
        """
        meta = getattr(self, "shops_meta", {}).get(
            str(shop.get("ShopTemplateId") or "").strip().lower(), {}
        )
        balance = meta.get("balance") if isinstance(meta, dict) else None
        if isinstance(balance, dict):
            amount = balance.get(currency_id)
            if isinstance(amount, (int, float)) and amount > 0:
                return int(amount)
        return TRADER_BALANCE_FALLBACK

    def _max_trader_level(self) -> None:
        """Unlike the skills tab this only moves the readout - the level and the balance are
        written together by Set Stats, so applying one straight through would half-apply the
        pair. The spinbox arrows behave the same way."""
        self.trader_level_var.set(str(self._max_level_for_account()))

    def _set_selected_trader_stats(self) -> None:
        selected = self.traders_tree.selection()
        t = TRANSLATIONS[self.current_lang]
        if not selected:
            messagebox.showwarning(t["title"], t["msg_no_item_selected"])
            return

        values = self.traders_tree.item(selected[0], "values")
        trader_id = values[0]

        try:
            new_level = int(self.trader_level_var.get())
            if not (TRADER_LEVEL_MIN <= new_level <= self._max_level_for_account()):
                raise ValueError()
        except ValueError:
            messagebox.showerror(t["title"], t["msg_trader_level_range"].format(
                min_level=TRADER_LEVEL_MIN, max_level=self._max_level_for_account()))
            return

        try:
            new_balance = int(self.trader_balance_var.get())
            if new_balance < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror(t["title"], "Invalid balance. Must be a non-negative integer.")
            return

        shops_list = self.manager.data.setdefault("AccountShops", [])
        shop = next((s for s in shops_list if s.get("Id") == trader_id), None)
        if not shop:
            messagebox.showerror(t["title"], f"Trader {trader_id} not found in save data.")
            return

        shop["AccountLevel"] = new_level

        balance_dict = shop.setdefault("Balance", {})
        currency_key = "cb567810-cc82-424f-893f-299c704ffb12"
        balance_dict[currency_key] = new_balance

        self._refresh_traders_list()
        for item in self.traders_tree.get_children():
            val = self.traders_tree.item(item, "values")
            if val and val[0] == trader_id:
                self.traders_tree.selection_set(item)
                break

        self._mark_pending_changes(t["status_trader_set"].format(level=new_level, balance=new_balance))

    def _cheat_repair_all(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        all_items = self.manager.get_all_items_flat()
        repaired_count = 0
        for item in all_items:
            if repair_item_logic(item, self._template_max_durability_for_item(item)):
                repaired_count += 1

        reopen = self._capture_open_member_ids()
        self._populate_scope_view(reopen_member_ids=reopen)

        messagebox.showinfo(
            t["msg_success_title"],
            t["msg_cheats_repair"].format(count=repaired_count),
            parent=self.root
        )
        self._mark_pending_changes(t["status_cheat_repaired"].format(count=repaired_count))

    def _cheat_max_skills(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        skills_list = self.manager.data.setdefault("AccountDto", {}).setdefault("SkillsDto", {}).setdefault("Skills", [])
        active_ids = self._active_skill_ids()
        for s_id in active_ids:
            skill_item = next((s for s in skills_list if s.get("Id") == s_id), None)
            if not skill_item:
                skill_item = {"Id": s_id}
                skills_list.append(skill_item)
            # Each skill has its own ceiling; a flat 10 would write a level the game does
            # not allow - Lockpick stops at 5.
            skill_item["Level"] = self._max_level_for_skill(s_id)
            if "NextLevelExperienceGoal" not in skill_item:
                skill_item["NextLevelExperienceGoal"] = 2000

        self._refresh_skills_list()

        messagebox.showinfo(
            t["msg_success_title"],
            t["msg_cheats_skills"].format(count=len(active_ids)),
            parent=self.root
        )
        self._mark_pending_changes(t["status_cheat_maxed_skills"])

    def _cheat_fill_trader_balances(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        shops_list = self.manager.data.setdefault("AccountShops", [])
        trader_count = len(shops_list)

        currency_key = "cb567810-cc82-424f-893f-299c704ffb12"
        for shop in shops_list:
            shop["AccountLevel"] = self._max_level_for_account()
            balance_dict = shop.setdefault("Balance", {})
            balance_dict[currency_key] = self._balance_for_shop(shop, currency_key)

        self._refresh_traders_list()

        messagebox.showinfo(
            t["msg_success_title"],
            t["msg_cheats_traders"].format(count=trader_count),
            parent=self.root
        )
        self._mark_pending_changes(t["status_cheat_filled_traders"])

    def _load_scope_options(self) -> None:
        # Keep track of current selection index if possible
        current_idx = self.scope_combo.current()
        if current_idx < 0:
            current_idx = 0

        t = TRANSLATIONS[self.current_lang]
        self.scope_labels = [t["scope_char_eq"]]
        tab_count = len(self.manager.get_inventory_tabs())
        self.scope_labels.extend([t["scope_tab"].format(idx=idx + 1) for idx in range(tab_count)])
        self.scope_labels.append(t["scope_shelter"])

        self.scope_combo["values"] = self.scope_labels
        if self.scope_labels:
            if current_idx >= len(self.scope_labels):
                current_idx = 0
            self.scope_var.set(self.scope_labels[current_idx])
            self._populate_scope_view()
        self._refresh_catalog_view()

    def _get_localized_status(self, raw_status: str) -> str:
        if not raw_status:
            return ""
            
        t = TRANSLATIONS[self.current_lang]
        
        # 1. status_welcome
        if raw_status == "status_welcome":
            return t["status_welcome"]
            
        # 2. Scope info
        if raw_status.startswith("Scope: ") and " | Save: " in raw_status:
            # "Scope: {scope} | Save: {self.save_path}"
            parts = raw_status.split(" | Save: ", 1)
            scope = parts[0][7:]
            path = parts[1]
            return t.get("status_scope_info", "Scope: {scope} | Save: {path}").format(scope=scope, path=path)
            
        # 3. Mapping refreshed
        if raw_status.startswith("Mapping refreshed from: "):
            path = raw_status[len("Mapping refreshed from: "):]
            return t["status_refreshed"].format(path=path)
            
        # 4. Mapping refresh failed
        if raw_status == "Mapping refresh failed":
            return t["msg_refresh_failed"]
            
        # 5. Refreshing names
        if raw_status == "Refreshing names from game assets... this may take a moment":
            return t.get("status_refreshing", raw_status)
            
        # 6. Added catalog items
        if raw_status.startswith("Added ") and " catalog item(s)" in raw_status:
            try:
                added = raw_status.split("Added ", 1)[1].split(" catalog item", 1)[0]
                return t.get("status_catalog_added", "Added {added} catalog item(s) (not saved yet)").format(added=added)
            except Exception:
                pass
                
        # 7. Edited item
        if raw_status.startswith("Edited item ") and " (not saved yet)" in raw_status:
            item_id = raw_status[len("Edited item "):-len(" (not saved yet)")]
            return t.get("status_item_edited", "Edited item {item_id} (not saved yet)").format(item_id=item_id)
            
        # 8. Edited skill
        if raw_status.startswith("Edited skill ") and " (not saved yet)" in raw_status:
            skill_id = raw_status[len("Edited skill "):-len(" (not saved yet)")]
            return t.get("status_skill_edited", "Edited skill {skill_id} (not saved yet)").format(skill_id=skill_id)
            
        # 9. Duplicated
        if raw_status.startswith("Duplicated "):
            try:
                rest = raw_status[len("Duplicated "):]
                mode, created_part = rest.split(": created ", 1)
                if mode == "stack items":
                    mode_trans = t.get("mode_stack_items", "stack items")
                else:
                    mode_trans = t.get("mode_item_copies", "item copies")
                return t.get("status_duplicated", "Duplicated {mode}: created {count}{failure}").format(
                    mode=mode_trans, count=created_part, failure=""
                )
            except Exception:
                pass
                
        # 10. Deleted letter
        if raw_status == "Deleted one mailbox letter (not saved yet)":
            return t.get("status_mail_deleted_pending", "Deleted one mailbox letter (not saved yet)")

        # 10b. Deleted items
        suffix = " item(s) (not saved yet)"
        if raw_status.startswith("Deleted ") and raw_status.endswith(suffix):
            count = raw_status[len("Deleted "):-len(suffix)]
            return t.get(
                "status_items_deleted",
                "Deleted {count} item(s) (not saved yet)",
            ).format(count=count)


        # 11. Changes applied
        prefix = "Changes applied to save file (backup: "
        # Checked before the plain variant below, which would otherwise swallow the suffix
        # into the file name. A backup name can never contain "; pruned ".
        if raw_status.startswith(prefix) and "; pruned " in raw_status and raw_status.endswith(")"):
            name, _, count = raw_status[len(prefix):-1].rpartition("; pruned ")
            return t.get(
                "status_changes_applied_backup_pruned",
                "Changes applied. Backup: {name} ({count} older backups removed)",
            ).format(name=name, count=count)
        if raw_status.startswith(prefix) and raw_status.endswith(")"):
            name = raw_status[len(prefix):-1]
            return t.get(
                "status_changes_applied_backup",
                "Changes applied. Backup: {name}",
            ).format(name=name)
        if raw_status == "Changes applied to save file":
            return t["status_changes_applied"]
            
        # 12. Changes discarded
        if raw_status == "Unsaved changes discarded":
            return t["status_changes_discarded"]
            
        # Fallback to key lookup in TRANSLATIONS
        if raw_status in t:
            return t[raw_status]
            
        return raw_status

    def _set_status(self, text: str) -> None:
        self.last_status_raw = text
        localized_text = self._get_localized_status(text)
        total_names = len(self.template_name_map)
        alias_names = len(self.manual_alias_map)
        
        t = TRANSLATIONS[self.current_lang]
        pending_label = t["pending_label"] if self.has_pending_changes else ""
        if total_names:
            names_status = t["names_status"].format(total_names=total_names, alias_names=alias_names)
            self.status_var.set(f"{pending_label}{localized_text}{names_status}")
            return
        self.status_var.set(f"{pending_label}{localized_text}")

    def _refresh_pending_buttons(self) -> None:
        state = "normal" if self.has_pending_changes else "disabled"
        for button in self.apply_buttons + self.discard_buttons:
            button.configure(state=state)

    def _mark_pending_changes(self, status_text: str) -> None:
        self.has_pending_changes = True
        self._refresh_pending_buttons()
        self._set_status(status_text)

    def _clear_pending_changes(self, status_text: str) -> None:
        self.has_pending_changes = False
        self._refresh_pending_buttons()
        self._set_status(status_text)

    def _alias_candidates(self) -> list[Path]:
        base_dir = Path(__file__).resolve().parent
        return [
            base_dir.parent / "Scripts" / "template_aliases.json",
            base_dir / "template_aliases.json",
        ]

    def _mapping_candidates(self) -> list[Path]:
        base_dir = Path(__file__).resolve().parent
        if getattr(sys, "frozen", False):
            return [base_dir / "generated" / "template_mapping_report.json"]
        return [
            base_dir.parent / "Scripts" / "generated" / "template_mapping_report.json",
            base_dir / "generated" / "template_mapping_report.json",
        ]

    def _load_manual_aliases(self) -> dict[str, str]:
        for path in self._alias_candidates():
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                continue

            aliases_obj = payload.get("aliases", payload) if isinstance(payload, dict) else {}
            if not isinstance(aliases_obj, dict):
                continue

            loaded: dict[str, str] = {}
            for key, value in aliases_obj.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    continue
                key = key.strip().lower()
                value = value.strip()
                if not key or not value:
                    continue
                loaded[key] = value

            self.alias_map_source = str(path)
            return loaded
        return {}

    def _load_template_name_map(self) -> None:
        self.manual_alias_map = self._load_manual_aliases()
        self.npc_name_map = {}
        self.game_item_catalog = []
        self.game_item_meta_by_template_id = {}
        self.skills_name_map = dict(SKILL_NAMES)
        self.skills_meta = {}
        self.shops_meta = {}
        self.max_account_level = TRADER_LEVEL_MAX_FALLBACK
        self.level_progress = {}
        self.traders_name_map = dict(TRADER_NAMES)

        for path in self._mapping_candidates():
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    report = json.load(f)
            except Exception:
                continue

            mapping = report.get("mapping", [])
            if not isinstance(mapping, list):
                continue

            npc_mapping = report.get("npc_name_mapping", {})
            if isinstance(npc_mapping, dict):
                for npc_id, npc_name in npc_mapping.items():
                    if not isinstance(npc_id, str) or not isinstance(npc_name, str):
                        continue
                    npc_id = npc_id.strip().lower()
                    npc_name = npc_name.strip()
                    if npc_id and npc_name:
                        self.npc_name_map[npc_id] = npc_name

            skills_mapping = report.get("skills_mapping", {})
            meta = report.get("skills_meta")
            if isinstance(meta, dict):
                self.skills_meta = meta
            if isinstance(skills_mapping, dict):
                for k, v in skills_mapping.items():
                    self.skills_name_map[str(k)] = str(v)

            trader_mapping = report.get("trader_mapping", {})
            if isinstance(trader_mapping, dict):
                for k, v in trader_mapping.items():
                    self.traders_name_map[str(k)] = str(v)

            shops_meta = report.get("shops_meta")
            if isinstance(shops_meta, dict):
                self.shops_meta = shops_meta
            max_level = report.get("max_account_level")
            if isinstance(max_level, int) and max_level > 0:
                self.max_account_level = max_level
            level_progress = report.get("level_progress")
            if isinstance(level_progress, dict):
                self.level_progress = level_progress

            item_catalog = report.get("item_catalog", [])
            if isinstance(item_catalog, list):
                for row in item_catalog:
                    if not isinstance(row, dict):
                        continue
                    template_id = row.get("template_id")
                    if not isinstance(template_id, str):
                        continue
                    template_id = template_id.strip().lower()
                    if not template_id:
                        continue
                    self.game_item_catalog.append(row)
                    self.game_item_meta_by_template_id[template_id] = row

            loaded: dict[str, str] = {}
            for row in mapping:
                if not isinstance(row, dict):
                    continue
                tid = row.get("template_id")
                name = row.get("name_guess")
                if not isinstance(tid, str) or not isinstance(name, str):
                    continue
                name = name.strip()
                if not name:
                    continue
                loaded[tid.lower()] = name

            for key, value in self.manual_alias_map.items():
                loaded[key] = value

            self.template_name_map = loaded
            self.template_map_source = str(path)
            game_path = report.get("game_path")
            if isinstance(game_path, str) and game_path.strip():
                self.last_game_path = game_path.strip()
            return

        self.template_name_map = dict(self.manual_alias_map)
        self.game_item_catalog = []
        self.game_item_meta_by_template_id = {}

    def _extractor_script_path(self) -> Path:
        base_dir = Path(__file__).resolve().parent
        return base_dir.parent / "Scripts" / "extract_template_mapping.py"

    def _extractor_out_dir(self) -> Path:
        base_dir = Path(__file__).resolve().parent
        if getattr(sys, "frozen", False):
            return base_dir / "generated"
        return self._extractor_script_path().with_name("generated")

    def _detect_default_game_path(self) -> str:
        """Prefill for the game folder prompt: the path a previous extraction used, else a
        detected install, else empty so the field does not suggest a wrong path."""
        if self.last_game_path:
            return self.last_game_path
        detected = discover_game_dir()
        return str(detected) if detected else ""

    def _resolve_python_for_extractor(self) -> str:
        return sys.executable

    def _on_extraction_success(
        self,
        game_dir: Path,
        output_info: str = "",
        report: dict | None = None,
    ) -> None:
        old_count = len(self.template_name_map)
        self.last_game_path = str(game_dir)
        self._load_template_name_map()
        self._refresh_catalog_view()
        new_count = len(self.template_name_map)
        reopen = self._capture_open_member_ids()
        self._populate_scope_view(reopen_member_ids=reopen)

        # The extractor degrades to guesses instead of failing, so say when the official
        # asset names were unavailable rather than reporting a clean success.
        if report is not None and not report.get("repository_mapping_enabled"):
            reason = (
                report.get("repository_mapping_reason")
                or report.get("unitypy_reason")
                or "game asset names unavailable"
            )
            output_info = f"{output_info}\n\nWarning: {reason}\nNames may be incomplete.".strip()

        t = TRANSLATIONS[self.current_lang]
        details = f"\n\n{output_info.strip()}" if output_info.strip() else ""
        messagebox.showinfo(
            t["msg_success_title"],
            t["msg_mapping_updated"].format(old_count=old_count, new_count=new_count, details=details),
            parent=self.root,
        )
        self._set_status(f"Mapping refreshed from: {game_dir}")

    def _on_extraction_failure(self, error_message: str) -> None:
        t = TRANSLATIONS[self.current_lang]
        messagebox.showerror(
            t["msg_refresh_failed"],
            error_message,
            parent=self.root,
        )
        self._set_status("Mapping refresh failed")

    def _refresh_names_from_game(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        game_path = simpledialog.askstring(
            t["msg_game_folder_title"],
            t["msg_prompt_game_folder"],
            initialvalue=self._detect_default_game_path(),
            parent=self.root,
        )
        if game_path is None:
            return

        game_path = game_path.strip()
        if not game_path:
            messagebox.showerror(t["msg_refresh_failed"], t["msg_refresh_empty"], parent=self.root)
            return

        game_dir = Path(game_path)
        if not game_dir.exists():
            messagebox.showerror(
                t["msg_refresh_failed"],
                t["msg_err_game_folder_not_found"].format(game_dir=game_dir),
                parent=self.root,
            )
            return

        save_path_str = self.save_path
        out_dir_str = str(self._extractor_out_dir())
        locale_str = "en"

        self._set_status("Refreshing names from game assets... this may take a moment")
        self.root.update_idletasks()

        import threading

        scripts_dir = Path(__file__).resolve().parent.parent / "Scripts"
        if scripts_dir.exists() and str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        try:
            import extract_template_mapping

            def thread_target():
                try:
                    report = extract_template_mapping.run_extraction(
                        game_path_str=str(game_dir),
                        save_path_str=save_path_str,
                        out_dir_str=out_dir_str,
                        locale=locale_str,
                    )
                    self.root.after(
                        0,
                        lambda r=report: self._on_extraction_success(game_dir, report=r),
                    )
                except Exception as ex:
                    # Bind the message now: `ex` is unbound once the except block exits,
                    # so a closure over it would raise NameError inside the Tk callback.
                    message = f"Error in-process: {ex}"
                    self.root.after(
                        0,
                        lambda m=message: self._on_extraction_failure(m),
                    )

            threading.Thread(target=thread_target, daemon=True).start()

        except ImportError:
            # Fallback to subprocess
            extractor_script = self._extractor_script_path()
            if not extractor_script.exists():
                messagebox.showerror(
                    "Mapping refresh",
                    f"Extractor script not found and could not be imported.",
                    parent=self.root,
                )
                self._set_status("Mapping refresh failed")
                return

            command = [
                self._resolve_python_for_extractor(),
                str(extractor_script),
                "--game-path",
                str(game_dir),
                "--save-path",
                self.save_path,
                "--out-dir",
                out_dir_str,
                "--locale",
                locale_str,
            ]

            def subprocess_target():
                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        check=False,
                    )
                    if result.returncode == 0:
                        self.root.after(
                            0,
                            lambda: self._on_extraction_success(game_dir, result.stdout),
                        )
                    else:
                        details = "\n\n".join(
                            part
                            for part in [
                                (result.stdout or "").strip(),
                                (result.stderr or "").strip(),
                            ]
                            if part
                        )
                        self.root.after(
                            0,
                            lambda: self._on_extraction_failure(
                                f"Extractor failed (exit {result.returncode}).\n\n{details}"
                            ),
                        )
                except Exception as ex:
                    message = f"Failed to run extractor subprocess:\n{ex}"
                    self.root.after(
                        0,
                        lambda m=message: self._on_extraction_failure(m),
                    )

            threading.Thread(target=subprocess_target, daemon=True).start()

    def _template_name_for_template_id(self, template_id: str | None) -> str | None:
        if not template_id:
            return None
        return self.template_name_map.get(str(template_id).lower())

    def _template_name_for_item_id(self, item_id: str | None) -> str | None:
        if not item_id:
            return None
        item = self.manager.get_item(item_id)
        if not item:
            return None
        return self._template_name_for_template_id(item.get("TemplateId"))

    def _npc_name_for_npc_bio_id(self, npc_bio_id: str | None) -> str | None:
        if not npc_bio_id:
            return None
        return self.npc_name_map.get(str(npc_bio_id).strip().lower())

    def _max_durability_for_item(self, item: dict) -> float:
        """Ceiling for DurabilityComponent_durability, or 0.0 when unknown.

        Varies per item (5 charges for a repair kit, 1600 for a Major MedKit), so it
        comes from the extracted game data. The save's own `_md` wins when present, as
        that is the instance's current ceiling. 0.0 makes the caller omit the percentage
        rather than compute one against a made-up number.
        """
        inner = item.get("AdditionalData", {}).get("_data", {})
        if isinstance(inner, dict):
            instance_max = inner.get("DurabilityComponent_md")
            if isinstance(instance_max, (int, float)) and instance_max > 0:
                return float(instance_max)

        meta = self.game_item_meta_by_template_id.get(
            str(item.get("TemplateId", "")).strip().lower(), {}
        )
        template_max = meta.get("max_durability")
        if isinstance(template_max, (int, float)) and template_max > 0:
            return float(template_max)
        return 0.0

    def _stack_capacity_for_template(self, template_id: str | None) -> int | None:
        """Units per stack from the game data, or None when the item is not stackable."""
        if not template_id:
            return None
        meta = self.game_item_meta_by_template_id.get(str(template_id).strip().lower(), {})
        capacity = meta.get("stack_capacity")
        if isinstance(capacity, (int, float)) and capacity > 0:
            return int(capacity)
        return None

    def _stack_quantity_of_item(self, item: dict | None) -> int | None:
        """Units held by a single stacked item, as stored in the save."""
        if not isinstance(item, dict):
            return None
        inner = item.get("AdditionalData", {}).get("_data", {})
        if not isinstance(inner, dict):
            return None
        quantity = inner.get("StackableComponent_quantity")
        if isinstance(quantity, (int, float)) and not isinstance(quantity, bool):
            return int(quantity)
        return None

    def _template_max_durability_for_item(self, item: dict) -> float | None:
        """The template ceiling, ignoring the item's degraded `_md`.

        Repairing has to lift `_md` back to this value, so unlike the display path it
        must not prefer the instance's current ceiling.
        """
        meta = self.game_item_meta_by_template_id.get(
            str(item.get("TemplateId", "")).strip().lower(), {}
        )
        template_max = meta.get("max_durability")
        if isinstance(template_max, (int, float)) and template_max > 0:
            return float(template_max)
        return None

    def _item_condition_parts(self, item: dict | None) -> tuple[str, float, float] | None:
        if not isinstance(item, dict):
            return None
        inner = item.get("AdditionalData", {}).get("_data", {})
        if not isinstance(inner, dict):
            return None
        durability = inner.get("DurabilityComponent_durability")
        if isinstance(durability, (int, float)):
            return ("DUR", float(durability), self._max_durability_for_item(item))
        condition = inner.get("Condition_d")
        if isinstance(condition, (int, float)):
            return ("COND", float(condition), 4.0)
        return None

    def _format_condition_text(self, parts: tuple[str, float, float]) -> str:
        label, value, max_value = parts
        if max_value <= 0:
            return f"{label} {value:.1f}"
        percent = max(0.0, min(999.0, (value / max_value) * 100.0))
        # `:g` so a ceiling of 2.9 is not rounded to 3 while the percentage uses 2.9.
        return f"{label} {value:.1f}/{max_value:g} ({percent:.0f}%)"

    def _condition_text_for_members(self, members: list[str]) -> str | None:
        points = []
        for item_id in members:
            item = self.manager.get_item(item_id)
            parts = self._item_condition_parts(item)
            if parts:
                points.append(parts)
        if not points:
            return None

        labels = {label for label, _, _ in points}
        if len(labels) > 1:
            return "COND mixed"

        label = points[0][0]
        max_value = points[0][2]
        values = [value for _, value, _ in points]
        min_v, max_v = min(values), max(values)
        if abs(min_v - max_v) < 1e-6:
            return self._format_condition_text((label, min_v, max_value))

        if max_value <= 0:
            return f"{label} {min_v:.1f}..{max_v:.1f}"
        min_pct = max(0.0, min(999.0, (min_v / max_value) * 100.0))
        max_pct = max(0.0, min(999.0, (max_v / max_value) * 100.0))
        return (
            f"{label} {min_v:.1f}..{max_v:.1f}/{max_value:g} "
            f"({min_pct:.0f}..{max_pct:.0f}%)"
        )

    def _render_entry_text(self, members: list[str]) -> str:
        label, note = describe_entry(self.manager, members)
        # A stacked item holds its count in the save, so one row can be many units.
        quantities = [
            q for q in (
                self._stack_quantity_of_item(self.manager.get_item(member))
                for member in members
            )
            if q
        ]
        if len(members) > 1:
            name = self._template_name_for_item_id(members[0])
            if quantities:
                label = f"{name or 'Stack'} ({len(members)} stacks, {sum(quantities)} units)"
            elif name:
                label = f"{name} (Stack of {len(members)} units)"
            else:
                label = f"Stack of {len(members)} units"
        else:
            # Show the real item name for the backpack too; "Backpack" stays as the
            # fallback for when the TemplateId has no resolved name.
            name = self._template_name_for_item_id(members[0])
            if name:
                label = name
            if quantities:
                capacity = self._stack_capacity_for_template(
                    (self.manager.get_item(members[0]) or {}).get("TemplateId")
                )
                label = (
                    f"{label} ×{quantities[0]}/{capacity}"
                    if capacity
                    else f"{label} ×{quantities[0]}"
                )

        # "(empty)" means "nothing attached", which says nothing useful about a stack.
        if quantities:
            note = ""

        text = f"{label} {note}".rstrip()
        condition = self._condition_text_for_members(members)
        if condition:
            text = f"{text} | {condition}"
        return text

    # --- Placement ------------------------------------------------------------------
    # A container's grid is not in the save; it comes from the template's own component,
    # which the extractor writes into each catalog row as `container`. Without it nothing
    # can be placed reliably, and the game moves an item it cannot place into the mailbox.

    def _footprint_for_template(self, template_id: str | None, rotated: bool = False):
        """(w, h) a fresh item of this template needs.

        Deliberately **not** MaxSize, even for a resizable weapon. Reserving the maximum
        looked like the only footprint that could not overlap, and measuring a real save
        showed the opposite: against the game's own layout it invents 80 overlapping cells
        across five rifle cases, because a weapon in a case is stored at the size it really
        takes (4x1) while its maximum is 6x3. See `_footprint_for_item`.
        """
        meta = self.game_item_meta_by_template_id.get(
            str(template_id or "").lower(), {}
        )
        width, height = meta.get("width"), meta.get("height")
        if not isinstance(width, int) or not isinstance(height, int):
            return None
        return (height, width) if rotated else (width, height)

    def _footprint_for_item(self, item_id: str):
        """(w, h) of an item as it occupies cells, `BaseComponent_rotated` swapping the axes.

        The size stored on the item wins, because it is the game's own record of what the
        item currently covers - a weapon that has grown with its attachments carries 4x1
        while its template says 2x1, which is exactly the "shows smaller than it blocks"
        effect visible in-game. Only an item that carries no size falls back to its template.
        Measured across a real save: this and the plain template size both give zero
        overlaps, and MaxSize gives 80.
        """
        item = self.manager.get_item(item_id) or {}
        data = (item.get("AdditionalData") or {}).get("_data") or {}
        rotated = bool(data.get("BaseComponent_rotated"))

        template_id = str(item.get("TemplateId") or "").lower()
        width = data.get("BaseComponent_width")
        height = data.get("BaseComponent_height")
        if not isinstance(width, int) or not isinstance(height, int):
            template = self._footprint_for_template(template_id)
            if template is None:
                return None
            width, height = template
        if rotated:
            return height, width
        return width, height

    def _container_cells_for(self, container_id: str):
        item = self.manager.get_item(container_id)
        if item is None:
            return None
        meta = self.game_item_meta_by_template_id.get(
            str(item.get("TemplateId") or "").lower(), {}
        )
        return container_cells(meta.get("container"))

    def _placement_in(self, container_id: str, width: int, height: int):
        """(I, J, rotated) for a free spot, or None when the container has no room."""
        cells = self._container_cells_for(container_id)
        if not cells:
            return None
        occupied = self.manager.occupied_cells(container_id, self._footprint_for_item)
        return find_placement(cells, occupied, width, height)

    def _is_bookkeeping_container(self, container_id: str) -> bool:
        """A container the game keeps for itself rather than one the player fills.

        Told apart by its modelled grid holding a **single cell**. That is not a heuristic
        about names: all 90 such templates in the report are internal - shelter modules, NPCs,
        exit zones, highlights - and three of them sit on the character in a real save
        (Phantom Items, Buff And Modifier, CraftRecipe Blueprints), two holding far more than
        the one cell they claim. Their real size is therefore unknown, and a container whose
        size is unknown must not be offered. No carried container is 1x1: a Hugger backpack is
        24 cells and the smallest real one, a Safe Box, is 2. Category is empty for all of
        them, so there is nothing else to separate them by.
        """
        item = self.manager.get_item(container_id) or {}
        spec = self.game_item_meta_by_template_id.get(
            str(item.get("TemplateId") or "").lower(), {}
        ).get("container")
        cells = container_cells(spec)
        return bool(cells) and len(cells) == 1

    def _placement_targets(self) -> list[tuple[str, str]]:
        """(container id, label) for the containers an item can be placed into.

        The warehouse tabs plus the containers carried on the character - a backpack, a rig,
        a safe box. Deliberately nothing else: a weapon case in a tab is left alone, which
        also keeps the editor out of the one place where an item's real footprint is least
        certain. Anything whose grid the report does not describe is left out rather than
        guessed at - weapon attachment points have their own item filters, and the shelter
        root is not an item at all, so it has no template to read a size from.

        A container with no free cell is left out too. Offering one is offering a dead end -
        the choice is accepted and then answered with "no space", which reads like a bug.
        """
        t = TRANSLATIONS[self.current_lang]
        targets: list[tuple[str, str]] = []

        def free_cells(container_id: str):
            if self._is_bookkeeping_container(container_id):
                return None
            cells = self._container_cells_for(container_id)
            if not cells:
                return None
            occupied = self.manager.occupied_cells(container_id, self._footprint_for_item)
            free = len(cells) - len([c for c in occupied if c in cells])
            return (free, len(cells)) if free > 0 else None

        for idx, tab_id in enumerate(self.manager.get_inventory_tabs(), 1):
            room = free_cells(tab_id)
            if room is None:
                continue
            targets.append((tab_id, t["target_tab"].format(
                idx=idx, free=room[0], total=room[1])))

        for item_id in self.manager.get_character_items():
            room = free_cells(item_id)
            if room is None:
                continue
            name = self._template_name_for_item_id(item_id) or t["target_container"]
            targets.append((item_id, t["target_carried"].format(
                name=name, free=room[0], total=room[1])))

        return targets

    def _ask_placement_target(self, title: str, same_container_id: str | None = None):
        """Lets the user pick where a new item goes. Returns a container id, the string
        "same" for the original's own container, or None when cancelled.

        A Combobox rather than a Listbox on purpose: a Listbox alongside entry fields
        silently loses its selection unless exportselection is off, and there is no reason
        to walk into that here.
        """
        t = TRANSLATIONS[self.current_lang]
        targets = self._placement_targets()
        options: list[tuple[str, str]] = []
        if same_container_id:
            options.append(("same", t["target_same_container"]))
        options.extend(targets)
        # Always available, and the only option left once everything is full: an item with no
        # grid position cannot be placed by the game, so it arrives as mail instead.
        options.append(("inbox", t["target_inbox"]))

        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        # Without this the Toplevel keeps the system background and the dark labels sit on a
        # pale rectangle.
        win.configure(bg="#1e1e1e")
        chosen: list[str | None] = [None]

        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=t["msg_place_prompt"]).pack(anchor="w", pady=(0, 6))
        combo = ttk.Combobox(body, state="readonly", width=54,
                             values=[label for _cid, label in options])
        combo.current(0)
        combo.pack(fill="x")

        hint = ttk.Label(body, text=t["msg_place_hint"], wraplength=430,
                         style="Hint.TLabel", justify="left")
        hint.pack(anchor="w", pady=(10, 0))
        # Only shown while the inbox is actually selected - it explains one choice out of
        # several and is noise the rest of the time.
        inbox_hint = ttk.Label(body, text=t["msg_place_inbox_hint"], wraplength=430,
                               style="Hint.TLabel", justify="left")

        def on_choice(_event=None) -> None:
            if options[combo.current()][0] == "inbox":
                hint.pack_forget()
                inbox_hint.pack(anchor="w", pady=(10, 0))
            else:
                inbox_hint.pack_forget()
                hint.pack(anchor="w", pady=(10, 0))

        combo.bind("<<ComboboxSelected>>", on_choice)
        on_choice()

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(14, 0))

        def confirm() -> None:
            chosen[0] = options[combo.current()][0]
            win.destroy()

        ttk.Button(buttons, text=t["btn_ok"], command=confirm).pack(side="right")
        ttk.Button(buttons, text=t["btn_cancel"],
                   command=win.destroy).pack(side="right", padx=(0, 6))

        self._center_toplevel(win)
        win.grab_set()
        win.wait_window()
        return chosen[0]

    def _on_tab_changed(self, event: tk.Event) -> None:
        selected_widget = event.widget.nametowidget(event.widget.select())
        if selected_widget == self.tab_mailbox:
            self._refresh_mailbox()
        elif selected_widget == self.tab_catalog:
            self._refresh_catalog_tree()
        elif selected_widget == self.tab_char:
            # Park focus on the notebook *before* refreshing. Tk's own tab activation
            # focuses the first entry in the pane (the nickname field) unless the
            # notebook already holds focus, so a refresh that raises must not be able
            # to skip this.
            self.notebook.focus_set()
            try:
                self._refresh_char_tab()
            except Exception as exc:
                # A windowed build has nowhere to print a traceback, so surface it.
                self._set_status(f"Could not read character data: {exc}")

    def _on_scope_changed(self, _event: tk.Event) -> None:
        self._populate_scope_view()

    def _target_inventory_tab_parent_id(self) -> str | None:
        tabs = self.manager.get_inventory_tabs()
        scope = self.scope_var.get().strip()
        if scope.startswith("Tab "):
            try:
                idx = int(scope.split()[1]) - 1
            except (ValueError, IndexError):
                idx = -1
            if 0 <= idx < len(tabs):
                return tabs[idx]
        if tabs:
            return tabs[0]
        return None

    def _refresh_catalog_filters(self) -> None:
        categories: set[tuple[int, str]] = set()
        for row in self.game_item_catalog:
            cid = row.get("category_id")
            if isinstance(cid, int):
                label = str(row.get("category_label") or "").strip() or f"Category {cid}"
                categories.add((cid, label))
        all_text = TRANSLATIONS[self.current_lang]["all_categories"]
        values = [all_text] + [
            f"{cid}: {label}" for cid, label in sorted(categories, key=lambda pair: pair[0])
        ]
        self.catalog_category_combo["values"] = values
        if self.catalog_category_var.get() not in values:
            self.catalog_category_var.set(all_text)
        self._refresh_subcategory_filter()

    def _selected_category_id(self) -> int | None:
        raw = self.catalog_category_var.get().strip()
        if raw and raw != TRANSLATIONS[self.current_lang]["all_categories"] and ":" in raw:
            head = raw.split(":", 1)[0].strip()
            if head.isdigit():
                return int(head)
        return None

    def _refresh_subcategory_filter(self) -> None:
        """Only the subcategories of the chosen category, and only those that hold something.

        The game's own labels are not unique - ids 95 to 100 are all called "Blueprint" and
        several have no label at all. So each entry carries how many items are in it, and a
        duplicated label is qualified by the name its items **all** share: subcategory 95
        holds eight "Bodypart Blueprint", so that is what it is called.

        Deliberately not an example item. Picking the first one made 95 read as
        "Bp_LeftArm_02_Model_03" although it also holds heads, torsos and legs - a single
        member describes the member, not the group. Where the names disagree, nothing is
        added rather than something misleading.
        """
        category_id = self._selected_category_id()
        labels: dict[int, str] = {}
        counts: dict[int, int] = {}
        item_names: dict[int, set[str]] = {}
        for row in self.game_item_catalog:
            if category_id is not None and row.get("category_id") != category_id:
                continue
            sid = row.get("subcategory_id")
            if not isinstance(sid, int):
                continue
            labels.setdefault(
                sid, str(row.get("subcategory_label") or "").strip() or f"SubCategory {sid}")
            counts[sid] = counts.get(sid, 0) + 1
            name = str(row.get("name") or "").strip()
            if name:
                item_names.setdefault(sid, set()).add(name)

        repeated = {
            label for label, seen in
            {lab: sum(1 for other in labels.values() if other == lab)
             for lab in labels.values()}.items()
            if seen > 1
        }

        all_text = TRANSLATIONS[self.current_lang]["all_categories"]
        values = [all_text]
        for sid in sorted(labels):
            text = f"{sid}: {labels[sid]}"
            shared = item_names.get(sid, set())
            if labels[sid] in repeated and len(shared) == 1:
                only = next(iter(shared))
                if only != labels[sid]:
                    text = f"{text} - {only}"
            values.append(f"{text} ({counts[sid]})")
        self.catalog_subcategory_combo["values"] = values
        if self.catalog_subcategory_var.get() not in values:
            self.catalog_subcategory_var.set(all_text)

    def _on_category_selected(self) -> None:
        self._refresh_subcategory_filter()
        self._refresh_catalog_tree()

    def _refresh_catalog_tree(self) -> None:
        for iid in self.catalog_tree.get_children(""):
            self.catalog_tree.delete(iid)

        all_text = TRANSLATIONS[self.current_lang]["all_categories"]
        category_filter_id = self._selected_category_id()
        subcategory_filter_id = None
        raw_sub = self.catalog_subcategory_var.get().strip()
        if raw_sub and raw_sub != all_text and ":" in raw_sub:
            head = raw_sub.split(":", 1)[0].strip()
            if head.isdigit():
                subcategory_filter_id = int(head)
        search_filter = self.catalog_search_var.get().strip().lower()
        # 164 templates share a localized name with another one - eight of them all read
        # "Bodypart Blueprint". Those get the developer's own name appended, which tells 54
        # of the 55 groups apart. Names that are already unique stay clean.
        name_counts: dict[str, int] = {}
        for row in self.game_item_catalog:
            label = str(row.get("name") or "").strip()
            if label:
                name_counts[label] = name_counts.get(label, 0) + 1

        for row in self.game_item_catalog:
            template_id = str(row.get("template_id", "")).strip().lower()
            if not template_id:
                continue
            name = str(row.get("name") or "").strip() or "(unnamed)"
            alias = str(row.get("alias") or "").strip()
            if alias and name_counts.get(name, 0) > 1:
                name = f"{name} - {alias}"
            category_id = row.get("category_id")
            subcategory_id = row.get("subcategory_id")
            category_label = str(row.get("category_label") or "").strip()
            subcategory_label = str(row.get("subcategory_label") or "").strip()
            width = row.get("width")
            height = row.get("height")

            if isinstance(category_filter_id, int) and category_id != category_filter_id:
                continue
            if isinstance(subcategory_filter_id, int) and subcategory_id != subcategory_filter_id:
                continue
            if search_filter:
                haystack = (
                    f"{name} {template_id} {category_id} {subcategory_id} "
                    f"{category_label} {subcategory_label}"
                ).lower()
                if search_filter not in haystack:
                    continue

            size_text = (
                f"{width}x{height}"
                if isinstance(width, int) and isinstance(height, int)
                else "-"
            )
            category_text = (
                category_label if category_label else
                (f"Category {category_id}" if isinstance(category_id, int) else "-")
            )
            subcategory_text = (
                subcategory_label if subcategory_label else
                (f"SubCategory {subcategory_id}" if isinstance(subcategory_id, int) else "-")
            )
            capacity = row.get("stack_capacity")
            stack_text = (
                str(int(capacity))
                if isinstance(capacity, (int, float)) and capacity > 0
                else "-"
            )
            self.catalog_tree.insert(
                "",
                "end",
                values=(
                    name,
                    template_id,
                    category_text,
                    subcategory_text,
                    size_text,
                    stack_text,
                ),
            )

    def _refresh_catalog_view(self) -> None:
        self._refresh_catalog_filters()
        self._refresh_catalog_tree()

    def _selected_catalog_template(self) -> tuple[str, str] | None:
        """(template id, display name) for the selected catalog row, or None after telling
        the user what was wrong with the selection."""
        t = TRANSLATIONS[self.current_lang]
        selected = self.catalog_tree.selection()
        if not selected:
            messagebox.showwarning(t["tab_catalog"], t["msg_no_item_selected"], parent=self.root)
            return None

        values = self.catalog_tree.item(selected[0], "values")
        if not values or len(values) < 2:
            messagebox.showerror(t["tab_catalog"], t["msg_catalog_row_invalid"], parent=self.root)
            return None
        template_id = str(values[1]).strip().lower()
        if not template_id:
            messagebox.showerror(t["tab_catalog"], t["msg_no_template_id"], parent=self.root)
            return None
        return template_id, str(values[0])

    def _add_selected_catalog_item_to_inventory(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        selection = self._selected_catalog_template()
        if not selection:
            return
        template_id = selection[0]

        capacity = self._stack_capacity_for_template(template_id)
        if capacity:
            # Stackables default to a full stack, which is what you almost always want.
            copy_count = simpledialog.askinteger(
                t["msg_add_item_title"],
                t["msg_add_stack_prompt"].format(capacity=capacity),
                minvalue=1,
                initialvalue=capacity,
                parent=self.root,
            )
        else:
            copy_count = simpledialog.askinteger(
                t["msg_add_item_title"],
                t["msg_add_item_prompt"],
                minvalue=1,
                initialvalue=1,
                parent=self.root,
            )
        if copy_count is None:
            return

        meta = self.game_item_meta_by_template_id.get(template_id, {})
        width = meta.get("width")
        height = meta.get("height")

        parent_id = self._ask_placement_target(t["msg_add_item_title"])
        if not parent_id:
            return

        to_inbox = parent_id == "inbox"
        target_label = t["target_inbox"] if to_inbox else ""
        if not to_inbox:
            for cid, label in self._placement_targets():
                if cid == parent_id:
                    target_label = label
                    break

        # The item still has to live in one of the three lists, so it is written into the
        # first warehouse tab - only without a position, which is what sends it to the mail.
        inbox_host = ""
        if to_inbox:
            tabs = self.manager.get_inventory_tabs()
            if not tabs:
                messagebox.showerror(t["tab_catalog"], t["msg_no_inv_tab_found"],
                                     parent=self.root)
                return
            inbox_host = tabs[0]

        footprint = self._footprint_for_template(template_id)
        if footprint is None:
            # Without a footprint there is no way to know what the item covers, and a wrong
            # guess is what sends it to the mailbox.
            messagebox.showerror(t["tab_catalog"], t["msg_place_no_targets"],
                                 parent=self.root)
            return
        item_width, item_height = footprint

        # Each spawned item takes cells away from the next one, so the free spot is looked
        # up again per item rather than once up front.
        def place_one(quantity: int | None) -> bool:
            if to_inbox:
                # No grid position at all. The game cannot place it and hands it over as
                # mail, the same route anything without room takes by itself.
                spot = (-1, -1, False)
            else:
                spot = self._placement_in(parent_id, item_width, item_height)
            if spot is None:
                return False
            i, j, rotated = spot
            created = self.manager.add_inventory_item(
                parent_id=inbox_host if to_inbox else parent_id,
                template_id=template_id,
                width=width if isinstance(width, int) else None,
                height=height if isinstance(height, int) else None,
                quantity=quantity,
                position=(i, j),
            )
            if rotated:
                inner = created.setdefault("AdditionalData", {}).setdefault("_data", {})
                inner["BaseComponent_rotated"] = True
            return True

        added = 0
        wanted = 0
        if capacity:
            # Split the requested amount into full stacks plus a remainder, since the
            # game refuses quantities above StackCapacity.
            remaining = copy_count
            while remaining > 0:
                chunk = min(remaining, capacity)
                wanted += 1
                if not place_one(chunk):
                    break
                remaining -= chunk
                added += 1
        else:
            wanted = copy_count
            for _ in range(copy_count):
                if not place_one(None):
                    break
                added += 1

        if not added:
            messagebox.showwarning(
                t["tab_catalog"],
                t["msg_place_no_space"].format(
                    target=target_label, width=item_width, height=item_height),
                parent=self.root,
            )
            return
        if added < wanted:
            messagebox.showinfo(
                t["tab_catalog"],
                t["msg_place_partial"].format(
                    placed=added, wanted=wanted, target=target_label),
                parent=self.root,
            )

        reopen = self._capture_open_member_ids()
        self._populate_scope_view(reopen_member_ids=reopen)
        self._mark_pending_changes(f"Added {added} catalog item(s) (not saved yet)")

    # --- Trader offers ----------------------------------------------------------------
    # An offer slot is overwritten rather than added, because the game rebuilds a trader's
    # whole Commodities list from its preset on every stock refresh - which is also what
    # eventually undoes the edit. The slot's previous contents are kept so it can be undone
    # sooner than that, but only for the current session: tracking them indefinitely just
    # collects records for slots the game has long since regenerated. Once the editor is
    # closed, the timestamped backup is the way back.

    def _drop_shop_offer_undo_file(self) -> None:
        """Removes the undo file an older version left behind. Nothing reads it any more."""
        try:
            path = self.manager.backup_dir / "shop_offer_undo.json"
            if path.exists():
                path.unlink()
        except OSError:
            pass  # a leftover file is cosmetic; never let it stop the editor from starting

    def _trader_name_for_shop(self, shop: dict) -> str:
        template_id = str(shop.get("ShopTemplateId") or "")
        return (
            self.traders_name_map.get(template_id)
            or self.traders_name_map.get(template_id.lower())
            or "Unknown Trader"
        )

    def _shops_with_offers(self) -> list[tuple[dict, str, list[dict]]]:
        """(shop, trader name, offers) for every trader that sells something. Base Shop and
        QuickSell hold no offers at all - they only buy."""
        result: list[tuple[dict, str, list[dict]]] = []
        for shop in self.manager.get_shops():
            commodities = self.manager.get_shop_commodities(shop.get("Id"))
            if commodities:
                result.append((shop, self._trader_name_for_shop(shop), commodities))
        return result

    def _shop_offer_label(self, commodity: dict) -> str:
        item = commodity.get("ItemDto") or {}
        name = self._template_name_for_template_id(item.get("TemplateId")) or "(unnamed)"
        price_items = (commodity.get("Price") or {}).get("Items") or [{}]
        priority = str(commodity.get("PositionViewPriority", "?"))
        count = str(commodity.get("Count", 1))
        price = str(price_items[0].get("Count", 0))
        return f"#{priority:<4}{name[:34]:<36}x{count:<7}{price}"

    def _offer_selected_catalog_item_at_trader(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        selection = self._selected_catalog_template()
        if not selection:
            return
        template_id, item_name = selection

        shops = self._shops_with_offers()
        if not shops:
            messagebox.showerror(t["shop_offer_title"], t["msg_shop_no_offers"], parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title(t["shop_offer_title"])
        win.configure(bg="#1e1e1e")
        win.transient(self.root)
        win.resizable(False, False)

        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(
            body,
            text=t["shop_offer_intro"].format(name=item_name),
            justify="left",
            wraplength=430,
        ).pack(anchor="w", pady=(0, 10))

        trader_row = ttk.Frame(body)
        trader_row.pack(fill="x", pady=(0, 10))
        ttk.Label(trader_row, text=t["shop_offer_trader"], width=20).pack(side="left")
        trader_combo = ttk.Combobox(
            trader_row,
            state="readonly",
            width=38,
            values=[f"{name} ({len(offers)})" for _shop, name, offers in shops],
        )
        trader_combo.pack(side="left")

        ttk.Label(body, text=t["shop_offer_slot"]).pack(anchor="w")
        list_wrap = ttk.Frame(body)
        list_wrap.pack(fill="both", expand=True, pady=(2, 10))
        slot_scroll = ttk.Scrollbar(list_wrap, orient="vertical")
        slot_scroll.pack(side="right", fill="y")
        slot_list = tk.Listbox(
            list_wrap,
            height=12,
            width=62,
            activestyle="none",
            # Without this the slot deselects itself as soon as the price or amount field
            # claims the selection, and confirming then reports no slot chosen.
            exportselection=False,
            font=("TkFixedFont", 9),
            bg="#252526",
            fg="#d4d4d4",
            selectbackground="#3794ff",
            highlightthickness=0,
            yscrollcommand=slot_scroll.set,
        )
        slot_scroll.configure(command=slot_list.yview)
        slot_list.pack(side="left", fill="both", expand=True)

        price_var = tk.StringVar()
        count_var = tk.StringVar()
        for label_key, variable in (("shop_offer_price", price_var), ("shop_offer_count", count_var)):
            row = ttk.Frame(body)
            row.pack(fill="x", pady=(0, 6))
            ttk.Label(row, text=t[label_key], width=20).pack(side="left")
            ttk.Entry(row, textvariable=variable, width=12).pack(side="left")

        def current_offers() -> list[dict]:
            return shops[max(trader_combo.current(), 0)][2]

        def fill_slots(_event=None) -> None:
            slot_list.delete(0, "end")
            for commodity in current_offers():
                slot_list.insert("end", self._shop_offer_label(commodity))
            price_var.set("")
            count_var.set("")

        def on_slot_selected(_event=None) -> None:
            chosen = slot_list.curselection()
            if not chosen:
                return
            commodity = current_offers()[chosen[0]]
            price_items = (commodity.get("Price") or {}).get("Items") or [{}]
            price_var.set(str(price_items[0].get("Count", 0)))
            count_var.set(str(commodity.get("Count", 1)))

        def confirm() -> None:
            chosen = slot_list.curselection()
            if not chosen:
                messagebox.showwarning(t["shop_offer_title"], t["msg_shop_slot_needed"], parent=win)
                return
            try:
                price = int(price_var.get().strip())
                count = int(count_var.get().strip())
            except ValueError:
                messagebox.showerror(t["shop_offer_title"], t["msg_shop_bad_numbers"], parent=win)
                return
            if price <= 0 or count <= 0:
                messagebox.showerror(t["shop_offer_title"], t["msg_shop_bad_numbers"], parent=win)
                return

            shop, trader_name, offers = shops[max(trader_combo.current(), 0)]
            shop_id = str(shop.get("Id"))
            commodity_id = str(offers[chosen[0]].get("Id"))
            meta = self.game_item_meta_by_template_id.get(template_id, {})
            width = meta.get("width")
            height = meta.get("height")

            original = self.manager.replace_shop_commodity(
                shop_id=shop_id,
                commodity_id=commodity_id,
                template_id=template_id,
                price=price,
                count=count,
                width=width if isinstance(width, int) else None,
                height=height if isinstance(height, int) else None,
            )
            if original is None:
                messagebox.showerror(t["shop_offer_title"], t["msg_shop_slot_gone"], parent=win)
                return

            # Editing the same slot twice must keep the first original, not the previous edit.
            self.shop_offer_undo.setdefault(
                f"{shop_id}:{commodity_id}",
                {"shop_id": shop_id, "trader": trader_name, "original": original,
                 "applied": False},
            )
            win.destroy()
            # Already localized, so _get_localized_status passes it through untouched.
            self._mark_pending_changes(t["status_shop_offer_set"].format(
                trader=trader_name, name=item_name, count=count, price=price,
            ))

        def undo_all() -> None:
            if not self.shop_offer_undo:
                messagebox.showinfo(t["shop_offer_title"], t["msg_shop_restore_none"], parent=win)
                return
            restored = gone = 0
            for record in list(self.shop_offer_undo.values()):
                if self.manager.restore_shop_commodity(
                    str(record.get("shop_id")), record.get("original") or {}
                ):
                    restored += 1
                else:
                    gone += 1
            self.shop_offer_undo.clear()
            win.destroy()
            self._mark_pending_changes(t["status_shop_offer_restored"].format(
                restored=restored, gone=gone,
            ))

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(buttons, text=t["btn_close"], command=win.destroy).pack(side="right")
        ttk.Button(buttons, text=t["btn_shop_offer_confirm"], command=confirm).pack(
            side="right", padx=(0, 6)
        )
        ttk.Button(
            buttons,
            text=t["btn_shop_offer_restore"].format(count=len(self.shop_offer_undo)),
            command=undo_all,
        ).pack(side="left")

        trader_combo.bind("<<ComboboxSelected>>", fill_slots)
        slot_list.bind("<<ListboxSelect>>", on_slot_selected)
        # "am besten bei pedlar" - preselect that trader whenever the save has one.
        trader_combo.current(next(
            (i for i, (_shop, name, _offers) in enumerate(shops) if "pedlar" in name.lower()),
            0,
        ))
        fill_slots()

        self._center_toplevel(win)
        win.grab_set()
        win.wait_window()

    def _scope_start_ids(self) -> tuple[str, list[str]]:
        idx = self.scope_combo.current()
        if idx < 0:
            idx = 0

        scope = self.scope_var.get()
        tab_count = len(self.manager.get_inventory_tabs())

        if idx == 0:
            return scope, self.manager.get_character_items()
        elif idx == tab_count + 1:
            return scope, self.manager.get_shelter_items()
        else:
            tabs = self.manager.get_inventory_tabs()
            tab_idx = idx - 1
            if 0 <= tab_idx < len(tabs):
                return scope, self.manager.get_children(tabs[tab_idx])
        return scope, []

    def _populate_scope_view(self, reopen_member_ids: set[str] | None = None) -> None:
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        self.entry_members.clear()
        self.loaded_nodes.clear()

        scope, start_ids = self._scope_start_ids()
        self._insert_entries("", start_ids)

        if reopen_member_ids:
            for root_iid in self.tree.get_children(""):
                self._restore_open_nodes(root_iid, reopen_member_ids)

        self._set_status(f"Scope: {scope} | Save: {self.save_path}")

    def _insert_entries(self, parent_iid: str, item_ids: list[str]) -> None:
        entries = build_entries(self.manager, item_ids)
        for members in entries:
            display_text = self._render_entry_text(members)
            iid = self.tree.insert(parent_iid, "end", text=display_text)
            self.entry_members[iid] = members

            if len(members) == 1 and self.manager.get_children(members[0]):
                self.tree.insert(iid, "end", text="")

    def _on_tree_open(self, _event: tk.Event) -> None:
        node = self.tree.focus()
        self._ensure_node_loaded(node)

    def _ensure_node_loaded(self, node: str) -> None:
        if not node or node in self.loaded_nodes:
            return
        members = self.entry_members.get(node)
        if not members or len(members) != 1:
            return

        children_nodes = self.tree.get_children(node)
        if not children_nodes:
            return

        first_child = children_nodes[0]
        if len(children_nodes) == 1 and self.tree.item(first_child, "text") == "":
            self.tree.delete(first_child)
            children = self.manager.get_children(members[0])
            self._insert_entries(node, children)
            self.loaded_nodes.add(node)

    def _restore_open_nodes(self, node: str, member_ids: set[str]) -> None:
        members = self.entry_members.get(node, [])
        if len(members) == 1 and members[0] in member_ids:
            self.tree.item(node, open=True)
            self._ensure_node_loaded(node)

        for child in self.tree.get_children(node):
            self._restore_open_nodes(child, member_ids)

    def _capture_open_member_ids(self) -> set[str]:
        open_ids: set[str] = set()
        for iid, members in self.entry_members.items():
            if len(members) == 1 and self.tree.item(iid, "open"):
                open_ids.add(members[0])
        return open_ids

    def _on_tree_right_click(self, event: tk.Event) -> None:
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.selection_set(row)
        self.tree.focus(row)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _on_catalog_right_click(self, event: tk.Event) -> None:
        row = self.catalog_tree.identify_row(event.y)
        if not row:
            return
        self.catalog_tree.selection_set(row)
        self.catalog_tree.focus(row)
        self.catalog_menu.tk_popup(event.x_root, event.y_root)

    def _resolve_target_item_id(self, members: list[str]) -> str | None:
        if len(members) == 1:
            return members[0]

        idx = simpledialog.askinteger(
            "Select stack member",
            f"This is a stack of {len(members)} items.\nChoose index (0-{len(members)-1}):",
            minvalue=0,
            maxvalue=len(members) - 1,
            parent=self.root,
        )
        if idx is None:
            return None
        return members[idx]

    def _selected_members(self) -> list[str] | None:
        selected = self.tree.selection()
        t = TRANSLATIONS[self.current_lang]
        if not selected:
            messagebox.showwarning(t["msg_no_selection_title"], t["msg_no_item_selected"])
            return None
        members = self.entry_members.get(selected[0], [])
        if not members:
            messagebox.showwarning(t["msg_no_selection_title"], t["msg_row_no_item_data"])
            return None
        return members

    def _selected_item_id(self) -> str | None:
        members = self._selected_members()
        if not members:
            return None
        return self._resolve_target_item_id(members)

    def _repair_subtree(self, item_id: str) -> int:
        """Repairs an item and everything attached to it, returning how many changed.

        Attachments are separate items linked by ParentId, so repairing a limb has to
        cover its hydraulics and structure too. Parts without condition data - weapon
        receivers, barrels, magazines - are skipped by repair_item_logic rather than
        gaining a fabricated field.
        """
        repaired = 0
        visited: set[str] = set()
        stack = [str(item_id)]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            item = self.manager.get_item(current)
            if not item:
                continue
            if repair_item_logic(item, self._template_max_durability_for_item(item)):
                repaired += 1
            stack.extend(self.manager.get_children(current))
        return repaired

    def _repair_item_id(self, item_id: str) -> None:
        item = self.manager.get_item(item_id)
        t = TRANSLATIONS[self.current_lang]
        if not item:
            messagebox.showerror(t["msg_discard_title"], t["msg_item_not_found"].format(item_id=item_id))
            return

        if not self._repair_subtree(item_id):
            self._set_status(f"Nothing to repair on item {item_id}")
            return

        reopen = self._capture_open_member_ids()
        self._populate_scope_view(reopen_member_ids=reopen)
        self._mark_pending_changes(f"Edited item {item_id} (not saved yet)")

    def _prompt_duplicate_count(self, is_stack: bool, stack_size: int) -> int | None:
        if is_stack:
            prompt = (
                f"This is a stack with {stack_size} items.\n"
                "How many full-stack copies should be created?"
            )
            title = "Duplicate stack"
        else:
            prompt = "How many copies should be created for this item?"
            title = "Duplicate item"
        return simpledialog.askinteger(
            title,
            prompt,
            minvalue=1,
            initialvalue=1,
            parent=self.root,
        )

    def _duplicate_members(self, members: list[str], copy_count: int) -> None:
        t = TRANSLATIONS[self.current_lang]

        # Where the copies go. "same" keeps each copy in its original's container, which is
        # what the action used to do - except it also kept the original's cell, so the copy
        # landed on top of it and the game moved it to the mailbox.
        origin_parent = str((self.manager.get_item(members[0]) or {}).get("ParentId") or "")
        target = self._ask_placement_target(
            t["ctx_duplicate"], same_container_id=origin_parent or None)
        if not target:
            return

        created_ids: list[str] = []
        failures: list[str] = []
        no_space = False
        for _ in range(copy_count):
            for item_id in members:
                parent_id = target
                if target == "same":
                    parent_id = str(
                        (self.manager.get_item(item_id) or {}).get("ParentId") or "")
                    if not parent_id:
                        failures.append(item_id)
                        continue

                if target == "inbox":
                    # No grid position: the game cannot place it and delivers it as mail.
                    parent_id = str(
                        (self.manager.get_item(item_id) or {}).get("ParentId") or "")
                    spot = (-1, -1, False)
                else:
                    footprint = self._footprint_for_item(item_id)
                    if footprint is None:
                        failures.append(item_id)
                        continue
                    spot = self._placement_in(parent_id, footprint[0], footprint[1])
                if spot is None:
                    no_space = True
                    break

                i, j, rotated = spot
                clone = self.manager.duplicate_item(
                    item_id, parent_id=parent_id, position=(i, j))
                if not clone:
                    failures.append(item_id)
                    continue
                inner = clone.setdefault("AdditionalData", {}).setdefault("_data", {})
                if rotated:
                    inner["BaseComponent_rotated"] = True
                else:
                    inner.pop("BaseComponent_rotated", None)
                clone_id = clone.get("Id")
                if isinstance(clone_id, str):
                    created_ids.append(clone_id)
            if no_space:
                break

        target_label = t["target_same_container"]
        if target == "inbox":
            target_label = t["target_inbox"]
        elif target != "same":
            target_label = next(
                (label for cid, label in self._placement_targets() if cid == target),
                target,
            )

        if no_space and not created_ids:
            footprint = self._footprint_for_item(members[0]) or (1, 1)
            messagebox.showwarning(
                t["ctx_duplicate"],
                t["msg_place_no_space"].format(
                    target=target_label, width=footprint[0], height=footprint[1]),
                parent=self.root,
            )
            return
        if no_space:
            messagebox.showinfo(
                t["ctx_duplicate"],
                t["msg_place_partial"].format(
                    placed=len(created_ids),
                    wanted=copy_count * len(members),
                    target=target_label,
                ),
                parent=self.root,
            )
        if not created_ids:
            failed_hint = f" First failed item: {failures[0]}" if failures else ""
            messagebox.showerror(t["title"], t["msg_duplicate_failed"].format(failed_hint=failed_hint))
            return

        reopen = self._capture_open_member_ids()
        self._populate_scope_view(reopen_member_ids=reopen)
        failure_note = f", failed: {len(failures)}" if failures else ""
        mode_label = "stack items" if len(members) > 1 else "item copies"
        self._mark_pending_changes(
            f"Duplicated {mode_label}: created {len(created_ids)}{failure_note}"
        )

    def _repair_selected(self) -> None:
        item_id = self._selected_item_id()
        if not item_id:
            return
        self._repair_item_id(item_id)

    def _duplicate_selected(self) -> None:
        members = self._selected_members()
        if not members:
            return
        copy_count = self._prompt_duplicate_count(
            is_stack=len(members) > 1,
            stack_size=len(members),
        )
        if copy_count is None:
            return
        self._duplicate_members(members, copy_count)

    def _delete_selected_items(self) -> None:
        """Deletes the selected row - an item with its attachments, or a single attachment
        when that attachment's own row is the one selected."""
        members = self._selected_members()
        if not members:
            return
        t = TRANSLATIONS[self.current_lang]

        # Warehouse tabs are not rows in this tree, but the guard is what makes that a
        # property of the code rather than of the current layout.
        if any(self.manager.is_structural(member) for member in members):
            messagebox.showwarning(t["msg_delete_title"], t["msg_delete_structural"])
            return

        total = sum(len(self.manager.collect_subtree(member)) for member in members)
        # A grouped row covers several separate items, so the question has to say so - "this
        # item" over two of them is exactly the wrong wording in a delete dialog.
        question = (
            t["msg_delete_confirm"] if len(members) == 1
            else t["msg_delete_confirm_many"].format(count=len(members))
        )
        lines = [question, self._render_entry_text(members)]
        if total > len(members):
            lines.append(t["msg_delete_attachments"].format(count=total - len(members)))
        if any(self.manager.is_equipped(member) for member in members):
            lines.append(t["msg_delete_equipped"])
        lines.append(t["msg_delete_revert_hint"])

        if not messagebox.askyesno(t["msg_delete_title"], "\n\n".join(lines)):
            return

        deleted = sum(len(self.manager.delete_item(member)) for member in members)
        if not deleted:
            return

        reopen = self._capture_open_member_ids()
        self._populate_scope_view(reopen_member_ids=reopen)
        self._mark_pending_changes(f"Deleted {deleted} item(s) (not saved yet)")

    def _search_items(self) -> None:
        query = self.search_var.get().strip().lower()
        t = TRANSLATIONS[self.current_lang]
        if not query:
            messagebox.showwarning(t["title"], t["msg_search_empty"])
            return

        all_items = self.manager.get_all_items_flat()
        filtered = [
            item
            for item in all_items
            if query in str(item.get("Id", "")).lower()
            or query in str(item.get("TemplateId", "")).lower()
        ]

        popup = tk.Toplevel(self.root)
        popup.title(t["search_results_title"].format(count=len(filtered)))
        popup.geometry("900x420")
        popup.transient(self.root)

        ttk.Label(popup, text=t["search_found_count"].format(count=len(filtered))).pack(anchor="w", padx=8, pady=(8, 4))

        wrap = ttk.Frame(popup)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        result_tree = ttk.Treeview(
            wrap,
            columns=("item_id", "template_id", "name", "condition"),
            show="headings",
        )
        result_tree.heading("item_id", text=t["col_id"])
        result_tree.heading("template_id", text="TemplateId")
        result_tree.heading("name", text=t["col_cat_name"])
        result_tree.heading("condition", text=t["col_condition"])
        result_tree.column("item_id", width=380, anchor="w")
        result_tree.column("template_id", width=250, anchor="w")
        result_tree.column("name", width=170, anchor="w")
        result_tree.column("condition", width=140, anchor="w")
        result_tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(wrap, orient="vertical", command=result_tree.yview)
        scroll.pack(side="right", fill="y")
        result_tree.configure(yscrollcommand=scroll.set)

        for item in filtered:
            template_id = str(item.get("TemplateId", ""))
            result_tree.insert(
                "",
                "end",
                values=(
                    str(item.get("Id", "")),
                    template_id,
                    self._template_name_for_template_id(template_id) or "",
                    self._condition_text_for_members([str(item.get("Id", ""))]) or "",
                ),
            )

        buttons = ttk.Frame(popup)
        buttons.pack(fill="x", padx=8, pady=(0, 8))

        def selected_popup_item_id() -> str | None:
            selected = result_tree.selection()
            if not selected:
                messagebox.showwarning(t["msg_no_selection_title"], t["msg_select_search_result"], parent=popup)
                return None
            values = result_tree.item(selected[0], "values")
            return str(values[0]) if values else None

        def popup_repair() -> None:
            item_id = selected_popup_item_id()
            if not item_id:
                return
            self._repair_item_id(item_id)

        def popup_duplicate() -> None:
            item_id = selected_popup_item_id()
            if not item_id:
                return
            copy_count = self._prompt_duplicate_count(is_stack=False, stack_size=1)
            if copy_count is None:
                return
            self._duplicate_members([item_id], copy_count)

        result_tree.bind("<Double-1>", lambda _evt: popup_repair())

        ttk.Button(buttons, text=t["ctx_repair"], command=popup_repair).pack(side="left")
        ttk.Button(buttons, text=t["ctx_duplicate"], command=popup_duplicate).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text=t["btn_close"], command=popup.destroy).pack(side="right")

    def _refresh_mailbox(self) -> None:
        for iid in self.mail_tree.get_children(""):
            self.mail_tree.delete(iid)
        self.mail_index_map.clear()

        mails = self.manager.get_mail_items()
        for idx, mail in enumerate(mails):
            sender = self._mail_sender_label(mail)
            message_ref = self._mail_message_reference(mail)
            rewards_count = len(mail.get("Rewards", [])) if isinstance(mail.get("Rewards"), list) else 0
            read_flag = "yes" if mail.get("IsRead") else "no"
            iid = self.mail_tree.insert(
                "",
                "end",
                values=(
                    idx,
                    sender,
                    message_ref,
                    rewards_count,
                    read_flag,
                    str(mail.get("Id", "")),
                ),
            )
            self.mail_index_map[iid] = idx

        self.mail_count_var.set(TRANSLATIONS[self.current_lang]["col_mail_count"].format(count=len(mails)))

    def _mail_sender_label(self, mail: dict) -> str:
        description = mail.get("LetterDescription")
        if not isinstance(description, dict):
            return "Unknown"

        sender = description.get("From")
        if isinstance(sender, str) and sender.strip():
            return sender.strip()
        if not isinstance(sender, dict):
            return "Unknown"

        for key in ("Name", "DisplayName", "Alias"):
            value = sender.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        npc_bio_id = sender.get("NpcBioId")
        if isinstance(npc_bio_id, str) and npc_bio_id.strip():
            npc_name = self._npc_name_for_npc_bio_id(npc_bio_id)
            if npc_name:
                return npc_name
            short_id = npc_bio_id[:8]
            return f"NPC {short_id}"

        return "Unknown"

    def _mail_message_reference(self, mail: dict) -> str:
        description = mail.get("LetterDescription")
        if not isinstance(description, dict):
            return "-"
        message = description.get("Message")
        if not isinstance(message, dict):
            return "-"
        text_ref = message.get("Text")
        if not isinstance(text_ref, dict):
            return "-"

        table = text_ref.get("TableReference")
        entry = text_ref.get("TableEntryReference")
        if isinstance(table, str) and table.strip() and entry is not None:
            return f"{table}:{entry}"
        if isinstance(table, str) and table.strip():
            return table
        return "-"

    def _delete_selected_mail(self) -> None:
        selected = self.mail_tree.selection()
        t = TRANSLATIONS[self.current_lang]
        if not selected:
            messagebox.showwarning(t["tab_mailbox"], t["msg_select_letter"])
            return

        idx = self.mail_index_map.get(selected[0])
        if idx is None:
            messagebox.showerror(t["tab_mailbox"], t["msg_err_resolve_letter"])
            return

        mails = self.manager.get_mail_items()
        if idx < 0 or idx >= len(mails):
            messagebox.showerror(t["tab_mailbox"], t["msg_err_letter_out_of_range"])
            return

        mails.pop(idx)
        self.manager.data["MailboxDto"]["Letters"] = mails
        self._refresh_mailbox()
        self._mark_pending_changes("Deleted one mailbox letter (not saved yet)")

    def _apply_pending_changes(self) -> None:
        if not self.has_pending_changes:
            return
        t = TRANSLATIONS[self.current_lang]
        try:
            backup_path = self.manager.save(backup_name="manual_apply")
        except Exception as exc:
            messagebox.showerror(t["title"], t["msg_err_save_failed"].format(exc=exc), parent=self.root)
            return
        # The overwritten trader offers are on disk now, so discarding later must not throw
        # their undo records away - only the ones that never got written.
        for record in self.shop_offer_undo.values():
            record["applied"] = True
        if backup_path and self.manager.last_pruned:
            self._clear_pending_changes(
                f"Changes applied to save file (backup: {backup_path.name}"
                f"; pruned {len(self.manager.last_pruned)})"
            )
        elif backup_path:
            self._clear_pending_changes(f"Changes applied to save file (backup: {backup_path.name})")
        else:
            self._clear_pending_changes("Changes applied to save file")
        self._refresh_char_tab()

    def _discard_pending_changes(self) -> None:
        if not self.has_pending_changes:
            return
        t = TRANSLATIONS[self.current_lang]
        discard = messagebox.askyesno(
            t["msg_discard_title"],
            t["msg_discard_confirm"],
            parent=self.root,
        )
        if not discard:
            return
        try:
            self.manager.reload_from_disk()
        except Exception as exc:
            messagebox.showerror(
                t["msg_discard_title"],
                t["msg_reload_failed"].format(exc=exc),
                parent=self.root,
            )
            return
        current_scope = self.scope_var.get()
        self._load_scope_options()
        if current_scope in self.scope_labels:
            self.scope_var.set(current_scope)
            self._populate_scope_view()
        self._refresh_mailbox()
        self._refresh_char_tab()
        # Trader offer edits that were never applied are gone with the reload, so only the
        # records for edits that did reach disk are still worth anything.
        self.shop_offer_undo = {
            key: record for key, record in self.shop_offer_undo.items()
            if record.get("applied")
        }
        self._clear_pending_changes("Unsaved changes discarded")

    def _on_close_requested(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        if not self.has_pending_changes:
            self._stop_music()
            self.root.destroy()
            return

        decision = messagebox.askyesnocancel(
            t["msg_unsaved_changes_title"],
            t["msg_unsaved_changes_prompt"],
            parent=self.root,
        )
        if decision is None:
            return
        if decision:
            self._apply_pending_changes()
            if self.has_pending_changes:
                return
            self._stop_music()
            self.root.destroy()
            return

        try:
            self.manager.reload_from_disk()
        except Exception as exc:
            messagebox.showerror(
                t["msg_discard_title"],
                t["msg_reload_failed"].format(exc=exc),
                parent=self.root,
            )
            return
        self._stop_music()
        self.root.destroy()

    def _asset_path(self, filename: str) -> Path:
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys._MEIPASS)
        else:
            base_dir = Path(__file__).resolve().parent
        return base_dir / filename

    def _music_file_path(self) -> Path:
        return self._asset_path("music.wav")

    def _start_music(self) -> None:
        music_path = self._music_file_path()
        if not music_path.exists():
            return

        if sys.platform.startswith("win"):
            try:
                import winsound
                winsound.PlaySound(str(music_path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
                self.music_playing = True
                if hasattr(self, 'mute_button') and self.mute_button:
                    self.mute_button.configure(text="🔇 Mute")
            except Exception:
                pass
        else:
            try:
                self.music_playing = True
                if hasattr(self, 'mute_button') and self.mute_button:
                    self.mute_button.configure(text="🔇 Mute")
                
                import threading
                self.music_thread = threading.Thread(
                    target=self._linux_music_thread_loop,
                    args=(str(music_path),),
                    daemon=True
                )
                self.music_thread.start()
            except Exception:
                pass

    def _linux_music_thread_loop(self, music_path_str: str) -> None:
        import time
        while self.music_playing:
            try:
                self.music_process = subprocess.Popen(
                    ["aplay", "-q", music_path_str],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                while self.music_playing and self.music_process.poll() is None:
                    time.sleep(0.1)
                
                if self.music_process.poll() is None:
                    try:
                        self.music_process.terminate()
                        self.music_process.wait(timeout=0.5)
                    except Exception:
                        pass
            except Exception:
                time.sleep(1.0)

    def _stop_music(self) -> None:
        self.music_playing = False
        
        if sys.platform.startswith("win"):
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        else:
            if hasattr(self, 'music_process') and self.music_process:
                try:
                    self.music_process.terminate()
                except Exception:
                    pass
                self.music_process = None

        if hasattr(self, 'mute_button') and self.mute_button:
            self.mute_button.configure(text="🔊 Music")

    def _toggle_music(self) -> None:
        if self.music_playing:
            self._stop_music()
        else:
            self._start_music()


def discover_game_dir() -> Path | None:
    """Best-effort search for the game install, mirroring discover_save_candidates.

    Confirmed by the `CargoHunters_Data` folder, so a same-named directory elsewhere is
    not mistaken for the install.
    """
    roots: list[Path] = []

    home = Path.home()
    roots.extend(
        [
            home / ".local" / "share" / "Steam" / "steamapps" / "common",
            home / ".steam" / "steam" / "steamapps" / "common",
        ]
    )
    for env_var in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(env_var)
        if base:
            roots.append(Path(base) / "Steam" / "steamapps" / "common")
    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        roots.extend(
            [
                Path(f"{drive}:/Program Files (x86)/Steam/steamapps/common"),
                Path(f"{drive}:/Program Files/Steam/steamapps/common"),
                Path(f"{drive}:/SteamLibrary/steamapps/common"),
                Path(f"{drive}:/Games/SteamLibrary/steamapps/common"),
            ]
        )
    media_root = Path("/media")
    if media_root.exists():
        for pattern in ("*/SteamLibrary/steamapps/common", "*/*/SteamLibrary/steamapps/common"):
            roots.extend(media_root.glob(pattern))

    for root in roots:
        candidate = root / "Cargo Hunters"
        try:
            if (candidate / "CargoHunters_Data").is_dir():
                return candidate
        except OSError:
            continue
    return None


def discover_save_candidates() -> list[Path]:
    base_dir = Path(__file__).resolve().parent
    found: set[Path] = set()

    local_candidates = [
        base_dir.parent / "Scripts" / "offline.save",
        base_dir / "Scripts" / "offline.save",
        base_dir / "offline.save",
    ]
    for candidate in local_candidates:
        if candidate.exists():
            found.add(candidate.resolve())

    home = Path.home()
    steam_userdata_roots = [
        home / ".local" / "share" / "Steam" / "userdata",
        home / ".steam" / "steam" / "userdata",
    ]
    windows_env_roots = [
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("PROGRAMFILES"),
        os.environ.get("LOCALAPPDATA"),
    ]
    for root in windows_env_roots:
        if not root:
            continue
        root_path = Path(root)
        steam_userdata_roots.extend(
            [
                root_path / "Steam" / "userdata",
                root_path / "Valve" / "Steam" / "userdata",
            ]
        )
    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        steam_userdata_roots.extend(
            [
                Path(f"{drive}:/Program Files (x86)/Steam/userdata"),
                Path(f"{drive}:/Program Files/Steam/userdata"),
            ]
        )
    for root in steam_userdata_roots:
        if not root.exists():
            continue
        for pattern in [
            f"*/{STEAM_APP_ID}/remote/offline.save",
            f"*/{STEAM_APP_ID}/remote_bkp/offline.save",
        ]:
            for candidate in root.glob(pattern):
                if candidate.exists():
                    found.add(candidate.resolve())

    media_root = Path("/media")
    if media_root.exists():
        media_patterns = [
            f"*/Steam/userdata/*/{STEAM_APP_ID}/remote/offline.save",
            f"*/*/Steam/userdata/*/{STEAM_APP_ID}/remote/offline.save",
            f"*/Steam/userdata/*/{STEAM_APP_ID}/remote_bkp/offline.save",
            f"*/*/Steam/userdata/*/{STEAM_APP_ID}/remote_bkp/offline.save",
        ]
        for pattern in media_patterns:
            for candidate in media_root.glob(pattern):
                if candidate.exists():
                    found.add(candidate.resolve())

    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)


def ask_user_for_save_path(parent: tk.Tk, initial_path: Path | None = None) -> str | None:
    t = TRANSLATIONS[load_config_lang()]
    initial_dir = str(initial_path.parent) if initial_path else str(Path.home())
    selected = filedialog.askopenfilename(
        parent=parent,
        title=t["msg_select_save_title"],
        initialdir=initial_dir,
        initialfile="offline.save",
        filetypes=[("Cargo Hunters save", "offline.save"), ("All files", "*")],
    )
    if not selected:
        return None
    return str(Path(selected).resolve())


def resolve_save_path(parent: tk.Tk, explicit_path: str | None = None) -> str | None:
    t = TRANSLATIONS[load_config_lang()]
    if explicit_path:
        candidate = Path(explicit_path).expanduser()
        if candidate.exists():
            return str(candidate.resolve())
        messagebox.showerror(
            t["msg_title_save_not_found"],
            t["msg_err_save_not_found"].format(candidate=candidate),
            parent=parent,
        )
        return None

    candidates = discover_save_candidates()
    if candidates:
        newest = candidates[0]
        if len(candidates) == 1:
            return str(newest)

        use_auto = messagebox.askyesno(
            t["msg_multiple_saves_title"],
            t["msg_multiple_saves_prompt"].format(count=len(candidates), newest=newest),
            parent=parent,
        )
        if use_auto:
            return str(newest)
        chosen = ask_user_for_save_path(parent=parent, initial_path=newest)
        return chosen

    return ask_user_for_save_path(parent=parent)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargo Hunters Save Editor GUI")
    parser.add_argument(
        "--save-path",
        default=None,
        help="Optional path to offline.save. If omitted, the GUI auto-detects Steam userdata remote paths.",
    )
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()

    save_path = resolve_save_path(parent=root, explicit_path=args.save_path)
    if not save_path:
        root.destroy()
        return

    try:
        manager = SaveDataManager(save_path)
    except Exception as exc:
        t = TRANSLATIONS[load_config_lang()]
        messagebox.showerror(t["msg_load_save_failed_title"], f"{exc}")
        root.destroy()
        return

    root.deiconify()
    SaveEditorGUI(root, manager, save_path)
    root.mainloop()


if __name__ == "__main__":
    main()
