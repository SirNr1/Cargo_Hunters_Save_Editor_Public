import argparse
import json
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from collections import Counter
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, simpledialog, ttk

try:
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from core_utils import (
    BACKUP_KEEP_DEFAULT,
    CREDITS_TEMPLATE_ID,
    SaveDataManager,
    build_entries,
    container_cells,
    container_regions,
    describe_entry,
    diff_is_empty,
    diff_saves,
    find_placement,
    item_data,
    list_backups,
    prune_item_data,
    repair_item_logic,
    restore_backup,
    writable_item_data,
)

from help_text import HELP_TEXT_DE, HELP_TEXT_EN, HELP_TEXT_RU

# Welche Liste zu welcher Sprache gehoert. Frueher eine if/elif-Kette in
# `_populate_help_text`; als Woerterbuch steht die Zuordnung an einer Stelle und der Ruckfall
# auf Englisch ist derselbe wie bei `TRANSLATIONS`.
HELP_TEXTE = {"en": HELP_TEXT_EN, "de": HELP_TEXT_DE, "ru": HELP_TEXT_RU}

STEAM_APP_ID = "4197990"

# The build of Cargo Hunters this release was developed and tested against - the same
# statement the trainer makes with its own BUILD constant, and for the same reason: an item
# catalog and a save layout are only ever right for a version of the game. Maintained by
# hand on release, never derived from whatever the user has installed. Which build the
# *names* came from is a different question, answered by `game_version` in the mapping
# report - a user can hold a newer game than this editor was tested with, and the help text
# below says what to do then.
GAME_BUILD_TESTED = "0.26.38.59"

# Die beiden Preset-Zahlen des getesteten Builds. Sie standen als Prosa an acht Stellen -
# "53" in beiden Hilfetexten und drei Sprachen, "17 der 53" ebenso - und keine davon wusste
# etwas von den anderen. Gerechnet wird jetzt aus `presets_meta`; diese Werte sind nur der
# Rueckfall fuer den Fall, dass noch kein Bericht vorliegt (frischer Klon, nie extrahiert).
# Dann eine Zahl auszugeben, die es gerade nicht gibt, waere schlechter als die aus dem Build.
PRESET_COUNT_SHIPPED = 53
PRESET_OUTGROWN_SHIPPED = 17
GAME_BUILD_TESTED_STEAM = "24834221"
GAME_BUILD_TESTED_DATE = "2026-08-22"

# "Quests and Keys", a community guide on Steam - where quest objectives and key spawns are,
# mostly as screenshots. Linked from the Quests tab rather than imported: it is someone else's
# work with no reuse licence, and it carries no per-section anchors, so there is nothing to
# link *into* even for the quests whose names match ours.
QUEST_GUIDE_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id=3686288040"

# Pixel width the Hackerman warning text wraps at; keeps the banner narrow and tall
# regardless of how long the translated strings are.
WARNING_WRAPLENGTH = 280

# **Menueeintraege, die nur auf einem Gegenstand eine sinnvolle Frage stellen.** Eine
# Stapelgroesse oder ein Anbauteil-Slot gilt fuer ein Stueck; ein Wert ueber Gegenstaende mit
# verschiedenen Obergrenzen ist Unsinn - die 250 eines Schilds sind keine Angabe fuer einen
# Reparaturkit mit fuenf Ladungen. Bei Mehrfachauswahl werden sie ausgegraut, statt
# stillschweigend nur den ersten zu nehmen.
#
# Es sind Positionen, und ein Separator belegt eine davon. Sie stehen hier, weil sie sonst
# beim naechsten eingeschobenen Eintrag still auf die falsche Aktion zeigen; die Reihenfolge
# selbst wird von tests/test_tabs_buttons.py gepinnt.
CTX_SINGLE_ONLY = (5, 6, 7, 8)          # aufteilen, Stapelgroesse, Anbauteile, Info
CATALOG_SINGLE_ONLY = (1, 2, 3)         # zusammengebaut spawnen, beim Haendler anbieten, Info


def enable_high_dpi_awareness() -> None:
    """Tells Windows this process draws at the monitor's real resolution.

    Without it Windows renders the window at 96 DPI and stretches the bitmap, which is
    exactly what the blur on a scaled display is. Must run **before** the first Tk window
    exists - afterwards the process-wide setting no longer takes.

    Three APIs, newest first, because each one only exists from a certain Windows version
    on. The first that reports success wins; a machine with none of them keeps the old
    behaviour rather than failing to start, which is why every failure is swallowed.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
    except ImportError:
        return

    # SetProcessDpiAwarenessContext returns a BOOL, SetProcessDpiAwareness an HRESULT
    # where 0 is success - so each attempt states for itself what "it worked" means.
    attempts = (
        # Per-Monitor V2, Windows 10 1703 and later
        lambda: bool(ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))),
        # Per-Monitor, Windows 8.1 up to 10 before 1703
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0,
        # System DPI aware, Windows Vista / 7 / 8
        lambda: bool(ctypes.windll.user32.SetProcessDPIAware()),
    )
    for attempt in attempts:
        try:
            if attempt():
                return
        except Exception:
            continue


def apply_simulated_dpi(root: tk.Tk, factor: float) -> float:
    """Make Tk report a scaled display, so the layout can be seen without a scaled monitor.

    **This exists because the development machine measures exactly 1.0**, while the app is
    used at 1.5x and 2.0x. A layout that only breaks on a scaled display can otherwise
    neither be reproduced nor confirmed here - every attempt has to travel through a
    screenshot from somebody else, which is how an afternoon goes into guessing arrow sizes.

    `tk scaling` is points per pixel, and `winfo_fpixels("1i")` returns 72 x that - which is
    the number `_get_dpi_scale` divides by 96. So a factor of 2.0 needs a scaling of
    2 x 96 / 72. Call it **before** the GUI is built; every size is read once at construction.

    **It scales the arithmetic, not the fonts.** The default fonts are already built by the
    time `tk.Tk()` returns, so raising the scaling afterwards does not resize them the way a
    real display would: measured on this machine, a window built this way reports a
    `TkDefaultFont` linespace of 45 at scaling 2.666, while the running app reports 32 at the
    same scaling. So anything derived from `_scale_px` - row height, minimum size, arrow
    sizes - is faithful here, and anything whose width comes from text is not. Control bar
    widths belong in `tests/test_window_size.py`, at the scale the machine actually runs.
    """
    root.tk.call("tk", "scaling", factor * 96.0 / 72.0)
    return root.winfo_fpixels("1i") / 96.0


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


def _read_config_key(key: str, default=None):
    """Ein Schluessel aus der config.json, oder `default`, wenn irgendetwas im Weg ist.

    "Irgendetwas" heisst hier absichtlich alles: keine Datei, kaputtes JSON, kein solcher
    Schluessel, oben drin steht eine Liste statt eines Objekts. Eine Einstellungsdatei darf
    den Editor nicht am Starten hindern - was nicht lesbar ist, gilt als nicht gesetzt.

    Ob der gelesene Wert *brauchbar* ist, entscheidet der jeweilige Leser: die Sprache muss in
    TRANSLATIONS stehen, `backup_keep` eine Zahl >= 0 sein. Das ist je Schluessel verschieden
    und steht deshalb nicht hier.
    """
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get(key, default)
        except Exception:
            pass
    return default


def _write_config_key(key: str, value) -> None:
    """Ein Schluessel in die config.json, ohne die anderen zu verlieren.

    Deshalb erst lesen, dann den einen Wert setzen, dann alles zurueckschreiben: die Datei
    haelt Sprache, Sicherungsanzahl, neue Vorlagen und Kategoriefarben nebeneinander, und wer
    sie einfach ueberschreibt, loescht die drei anderen Einstellungen mit.

    Schlaegt das Schreiben fehl, passiert nichts weiter. Eine nicht gespeicherte Einstellung
    ist ein Aergernis, ein Absturz beim Sprachwechsel waere einer mehr.
    """
    path = get_config_path()
    try:
        data = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data[key] = value
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass


def load_config_lang() -> str:
    lang = _read_config_key("language")
    return lang if lang in TRANSLATIONS else get_system_language()


def save_config_lang(lang: str) -> None:
    _write_config_key("language", lang)


def _trim_float(value: float) -> str:
    """`5` rather than `5.0`, but `3.8` kept. Condition values are stored as floats and
    most are whole numbers; the trailing zero reads like precision that is not there."""
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text or "0"


def load_config_backup_keep() -> int:
    keep = _read_config_key("backup_keep")
    return keep if isinstance(keep, int) and keep >= 0 else BACKUP_KEEP_DEFAULT


def save_config_backup_keep(keep: int) -> None:
    _write_config_key("backup_keep", int(keep))


def load_config_new_templates() -> set[str]:
    """The template ids the last refresh added, so the catalog can mark them.

    It lives in the config and not beside the report on purpose: it records what *this
    user* has not looked at yet, which is not game data and has no business travelling
    into a build. A report copied from another machine therefore arrives unmarked.
    """
    ids = _read_config_key("new_template_ids")
    if isinstance(ids, list):
        return {str(i).strip().lower() for i in ids if str(i).strip()}
    return set()


def save_config_new_templates(ids: set[str]) -> None:
    # Lowercased on the way in as well as on the way out. The ids always arrive that way
    # from the catalog, so this is only for a hand-edited config - but a file whose
    # contents do not match what the reader compares against is a trap for later.
    _write_config_key("new_template_ids",
                      sorted({str(i).strip().lower() for i in ids if str(i).strip()}))


def newly_added_templates(before: set[str], after: set[str]) -> set[str]:
    """What a refresh added, or nothing at all when the question cannot be answered.

    **An empty `before` means there is no baseline, not that everything is new.** On a
    first run - fresh clone, no report yet - every one of the ~1600 templates would
    otherwise light up, which says nothing and buries the handful that a game update
    really brings. The same guard covers an extraction that came back with no catalog:
    a run that resolved nothing cannot report what changed.
    """
    if not before or not after:
        return set()
    return {t for t in after if t not in before}


def load_config_category_colors() -> bool:
    return bool(_read_config_key("category_colors", False))


def save_config_category_colors(enabled: bool) -> None:
    _write_config_key("category_colors", bool(enabled))


# --- Die Farben der Oberflaeche ---------------------------------------------------------
# Acht Werte tragen das ganze Aussehen und standen als Hexzahl an 140 Stellen. Die Namen sind
# nicht geraten: sie kommen daher, an welchen Optionsnamen jede Farbe wirklich haengt -
# #1e1e1e siebzehnmal an `background`/`bg`, #3c3c3c siebenmal an `bordercolor`, #252526 an
# `fieldbackground`, und so fort.
#
# Die uebrigen 62 Farben der Datei bleiben Hexzahlen: sie kommen ein- bis viermal vor, meist
# fuer eine einzelne Sache (das Warnbanner, die Abzeichen-Animation, die Flaggen), und ein
# Name dafuer erfindet eine Rolle, die es nicht gibt.
#
# **Am Aussehen aendert sich nichts.** Belegt, nicht behauptet: die neun README-Ansichten
# davor und danach sind unterhalb der Titelleiste Pixel fuer Pixel gleich.
COLOR_BG = "#1e1e1e"             # Fensterhintergrund
COLOR_PANEL = "#252526"          # Eingabefelder und Flaechen darin
COLOR_BG_RAISED = "#2d2d2d"      # eine Stufe heller, fuer abgesetzte Flaechen
COLOR_BORDER = "#3c3c3c"         # Raender
COLOR_TEXT = "#d4d4d4"           # Schrift auf dem Hintergrund
COLOR_WHITE = "#ffffff"          # Schrift auf einer eingefaerbten Flaeche
COLOR_ACCENT = "#3794ff"         # das Blau der Ueberschriften, Pfeile und Verweise
COLOR_SELECTED = "#0e639c"       # die ausgewaehlte oder aktive Zeile


CATEGORY_COLORS: dict[str, str] = {
    "cat_1": "#ff7675",         # Firearm — soft red / coral
    "cat_3": "#e5c07b",         # Standard Ammo — warm brass
    "cat_3_ap": "#7fa060",      # Armor Piercing Ammo — tactical olive
    "cat_3_e": "#e0af68",       # Expansive Ammo — warm amber
    "cat_3_special": "#b48ead", # Special Ammo — muted plum, apart from the warm three
    "cat_5": "#d19a66",         # Backpack — tan / warm leather
    "cat_6": "#b5bd68",         # Chest Rig — olive / khaki
    "cat_7": "#56b6c2",         # Helmet / Headgear — steel cyan
    "cat_8": "#9aa2b0",         # SpawnBoxes / Crates — muted steel
    "cat_9": "#61afef",         # Armor Vest — steel blue
    "cat_10": "#ffaa54",        # Grenades — soft orange
    "cat_11": "#e27878",        # Melee Tool — salmon / steel
    "cat_12": "#7f848e",        # Internal components — dim gray
    "cat_13": "#4ec9b0",        # Body Part — medical mint / bionic cyan
    "cat_14": "#98c379",        # Aid Kit / Meds — soft green
    "cat_17": "#c678dd",        # Materials / Valuables — soft orchid / lavender
    "cat_18": "#ffd700",        # Quest item — gold / amber
    "cat_20": "#82aaff",        # Weapon Mod — slate / light periwinkle
    "cat_21": "#73d216",        # Money / Credits — cash green
    "cat_22": "#abb2bf",        # Case / Container Box — pewter / silver
    "cat_23": "#f6c177",        # Key — warm brass
    "cat_24": "#a3846b",        # Tools / Hardware — walnut, darker than the ammo brass
    "cat_29": "#00e5ff",        # Authenticator chip — electric cyan
    "cat_31": "#8fbcbb",        # Bodymod — pale frost, beside Body Part but not it
    "cat_37": "#74b9ff",        # Blueprints — blueprint blue
}


def category_tag_for_cat_id(category_id: object, subcategory_id: object = None) -> str | None:
    """Returns the Treeview tag name for a given category and subcategory, or None."""
    if not isinstance(category_id, int):
        return None
    if category_id == 3:
        if subcategory_id == 24:
            return "cat_3_ap"
        elif subcategory_id == 25:
            return "cat_3_e"
        elif subcategory_id == 101:
            return "cat_3_special"
        return "cat_3"
    tag = f"cat_{category_id}"
    return tag if tag in CATEGORY_COLORS else None


TRANSLATIONS = {
    "en": {
        "title": "★ Cargo Hunters Save Editor ★",
        "active_session": "[Active Session]",
        "tab_inventory": "Inventory",
        "tab_mailbox": "Mailbox",
        "tab_catalog": "Game Items",
        "tab_hackerman": "☢ Hackerman's Lab ☢",
        "tab_help": "Help / How to Use",
        "tab_raw_json": "Raw JSON",
        "btn_copy_json": "📋 Copy JSON",
        "msg_json_copied": "Copied!",
        "lbl_no_matches": "No matches",
        "btn_find_next": "Next",
        "btn_find_prev": "Prev",
        "chk_json_wrap": "Wrap lines",
        "lbl_json_staged": "● Unsaved (In-Memory)",
        "lbl_json_saved": "Saved",
        "lbl_json_size": "Size: {size}",
        "btn_refresh": "🔄 Refresh Names from Game",
        "btn_reload": "📂 Reload",
        "msg_reload_title": "Reload save",
        "msg_reload_discards": ("Reloading reads the file on disk again.\n\n"
                                "Your unsaved changes describe the version currently "
                                "loaded and cannot be carried over - they will be lost.\n\n"
                                "Reload anyway?"),
        "status_reloaded": "Save reloaded from disk",
        "btn_apply": "Apply Changes",
        "btn_discard": "Discard Changes",
        "lbl_scope": "Scope:",
        "lbl_search": "Search:",
        "btn_search": "Search",
        "status_search": "Search: '{query}' - {count} matching items",
        "btn_delete_mail": "Delete selected letter",
        "lbl_category": "Category:",
        "lbl_subcategory": "SubCategory:",
        "ctx_add_to_inv": "Add to Inventory...",
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
        "col_cat_price": "Value",
        "col_cat_mass": "Weight",
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
        "msg_mapping_new_items": "{count} items are new since the last refresh.\nThe catalog marks them; \"Only new\" filters down to them.",
        "cat_only_new": "Only new ({count})",
        "target_no_room": "  -- no room for this item",
        "place_size": "Space needed: {w} x {h} cells",
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
        "msg_skill_level_range": "Invalid level. This skill goes from 0 to {max_level}.",
        "msg_trader_level_range": "Invalid level. A trader goes from {min_level} to {max_level}.",
        "msg_trader_balance_range": "Invalid balance. This trader holds 0 to {max_balance} - the game cuts anything above that down on load.",
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
        "tab_quests": "Quests",
        "tab_crafting": "Crafting",
        "craft_count": "{modules} workbenches, {recipes} recipes, {ready} ready to craft",
        "quest_counts_filtered": "{count} of {total} quests match '{query}'",
        "craft_count_filtered": "{recipes} recipes match '{query}', {ready} of them ready",
        "craft_no_data": "No crafting data. Use Refresh Names from Game to read it.",
        "craft_module_row": "{name}  -  built {level} of {max}  ({count} recipes)",
        "craft_level_row": "Needs level {level}  ({count})",
        "craft_col_recipe": "Recipe",
        "craft_col_needs": "Takes",
        "craft_col_time": "Time",
        "craft_col_state": "Status",
        "craft_state_ready": "ready",
        "craft_state_missing": "ingredients short",
        "craft_state_locked": "level too low",
        "craft_state_unbuildable": "not in the game yet",
        "craft_detail_makes": "Makes",
        "craft_detail_needs": "Takes (in store / needed)",
        "craft_detail_where": "Workbench",
        "craft_detail_where_value": "{name}, needs level {needed} - built {level} of {max}",
        "craft_detail_time": "Time",
        "craft_detail_internal": "Internal name",
        "craft_hint": "Read-only: the editor does not craft. Recycling is not listed here - it "
                      "is the same recipe list seen from the item, and the item info window "
                      "shows it. A recipe marked as not in the game asks for a workbench level "
                      "the game has no build step for.",
        "col_quest_status": "Status",
        "col_quest_flags": "Flags",
        "col_quest_sender": "Sender",
        "col_quest_reward": "Reward",
        "quest_status_active": "Active",
        "quest_status_done": "Completed",
        "quest_status_unseen": "Never seen",
        "quest_flag_hidden": "not listed",
        "quest_flag_shadow": "shadow",
        "quest_group_none": "Ungrouped",
        "quests_hint": "Read-only. What the game ships against what this save has met. The progress of a running quest is not in the save at all, so it cannot be shown. Where to go and what to look for is not in the game files either — the button above opens a community guide on Steam, written by another player, in your browser.",
        "quests_guide_btn": "Community guide ↗",
        "quests_empty": "No quest data. Use Refresh Names from Game to read it from the game files.",
        "quest_pick": "Pick a quest to see its full text.",
        "quest_detail_alias": "Internal name",
        "quest_detail_status": "Status",
        "quest_detail_task": "Task",
        "quest_detail_requires": "Needs first",
        "quest_detail_level": "Account level",
        "quest_detail_sender": "Sent by",
        "quest_detail_rewards": "Rewards",
        "quest_detail_none": "none",
        "quest_reward_xp": "{xp} XP",
        "quest_level_range": "{min} to {max}",
        "quest_counts": "{total} quests in the game, {seen} met, {unseen} never seen",
        "msg_single_only": "{action} works on one row at a time - the selection holds several.",
        "msg_inbox_offer": "Not placed: {names}. Send them to the mailbox instead? You collect them in the game.",
        "msg_inbox_needs_parts": "These need fitted parts and would arrive as a loose pile, so they are left for you to place: {names}.",
        "cb_category_colors": "Category Colors",
        "btn_restore_backup": "Restore backup...",
        "restore_title": "Restore a backup",
        "restore_prompt": "Which backup should replace your save?",
        "restore_hint": "The current save is copied aside first, so this is undoable too. Nothing in the backups folder is deleted.",
        "diff_apply_title": "Confirm changes",
        "diff_apply_intro": "This is what will be written to the save file. A timestamped "
                            "backup of the current file is made first.",
        "diff_restore_title": "Confirm restore",
        "diff_restore_intro": "This is what putting {name} back would change in your current "
                              "save. The current file is copied aside first.",
        "diff_compare_title": "Compare with backup",
        "diff_compare_intro": "How {name} differs from the save on disk. Nothing is written.",
        "diff_btn_compare": "Compare...",
        "diff_intro": "The difference between the two saves.",
        "diff_col_what": "What",
        "diff_col_before": "Before",
        "diff_col_after": "After",
        "diff_added": "New items ({count})",
        "diff_removed": "Removed items ({count})",
        "diff_changed": "Changed items ({count})",
        "diff_fields": "Other changes ({count})",
        "diff_more": "... and {count} more",
        "diff_nothing": "No differences.",
        "diff_absent": "- not set -",
        "diff_unreadable": "The save on disk cannot be read, so the changes cannot be listed. "
                           "Write them anyway?",
        "diff_unreadable_compare": "One of the two files cannot be read as a save, so there is "
                                   "nothing to compare.",
        "restore_col_when": "Taken",
        "restore_col_label": "Reason",
        "restore_col_size": "Size",
        "restore_none": "There are no backups yet. One is written every time you apply changes.",
        "restore_pending": "You have unsaved changes. Restoring a backup discards them.\n\nContinue?",
        "restore_confirm": "Replace your save with this backup?\n\n{name}\n\nThe current save is copied to the backups folder first.",
        "btn_restore": "Restore",
        "status_restored": "Restored {name} (current save kept as {backup})",
        "msg_restore_failed": "Could not restore the backup:\n{exc}",
        "ctx_repair_custom": "Repair Item to...",
        "ctx_duplicate_custom": "Duplicate Item...",
        "custom_title_repair": "Repair to a value",
        "custom_repair_prompt": "{name} carries {field}. Set it to:",
        "custom_repair_children": "Apply to attached items too",
        "mint_checkbox": "Make it factory fresh instead",
        "mint_hint": "Factory fresh strips the wear record instead of setting a number: the game only calls an item mint while it carries no condition data at all, and a repair to maximum still reads as repaired.",
        "status_mint": "{count} item(s) are factory fresh now (not saved yet)",
        "status_mint_nothing": "Nothing to do - this carries no wear at all, which is exactly what factory fresh means.",
        "btn_cheat_mint": "\u2728 Make Everything Factory Fresh",
        "msg_mint_all_confirm": "Make all {count} items in the save factory fresh?\n\nEvery condition and durability record is removed, which is how the game stores an item that has never been used.",
        "msg_cheats_mint": "Done. {count} item(s) carry no wear any more.",
        "custom_repair_none": "This item carries no condition data, and neither does anything attached to it. The game only stores those fields once an item stops being pristine, so there is nothing to set.",
        "custom_repair_field_cond": "condition (0 to {max})",
        "custom_repair_field_dur": "charges (0 to {max})",
        "custom_title_duplicate": "Duplicate",
        "custom_count": "How many copies:",
        "custom_units": "Units per stack (max {capacity}):",
        "custom_target": "Where it goes:",
        "custom_condition": "Starting {field}:",
        "custom_condition_hint": "At the maximum the item is spawned pristine, which is how the game stores an untouched item - it carries no condition field at all. A lower value spawns it worn.",
        "custom_nothing_else": "This item does not stack and carries no condition, so there is nothing else to set for it.",
        "custom_value_range": "Value must be between {low} and {high}.",
        "ctx_move": "Move Item...",
        "move_title": "Move item",
        "move_prompt": "Move {name} to:",
        "move_hint": "Attachments come along, and an equipped item leaves its slot empty. "
                     "The cell it vacates stays free rather than being filled by its "
                     "neighbours.",
        "move_structural": "Warehouse tabs and the storage roots are part of the save's "
                           "layout rather than items, so they cannot be moved.",
        "move_no_space": "No free space in {target} for this item ({width}x{height}).",
        "move_failed": "The item could not be moved.",
        "status_moved": "Moved {count} item(s) to {target} (not saved yet)",
        "ctx_split": "Split Stack...",
        "ctx_stack_size": "Set Stack Size...",
        "stack_title": "Stack size",
        "stack_not_stackable": "This item is not a stack, so it has no size to set.",
        "stack_prompt": "How many units should this stack hold? It holds {current} of at most {max}.",
        "stack_prompt_nomax": "How many units should this stack hold? It holds {current}; the game data names no maximum for it.",
        "status_stack_set": "{name} now holds {count} units (not saved yet)",
        "btn_cheat_stacks": "\U0001f4e6 Fill All Stacks",
        "msg_cheats_stacks": "Filled {count} stack(s), {units} units added.",
        "msg_cheats_stacks_none": "Every stack is already full.",
        "status_cheat_stacks": "Filled {count} stacks, {units} units added (not saved yet)",
        "split_title": "Split stack",
        "split_prompt": "Take how many of the {quantity} units:",
        "split_hint": "The units taken become a second stack; the rest stays where it is. "
                      "Taking all of them would be a move, not a split, so at least one "
                      "unit has to stay behind.",
        "split_not_stackable": "This item is not a stack. Only an item that carries a "
                               "quantity can be split, and this one holds a single unit.",
        "split_no_space": "No free space in {target} for the second stack.",
        "status_split": "Split {amount} of {quantity} units off (not saved yet)",
        "ctx_attachments": "Attachments...",
        "attach_title": "Attachments",
        "attach_for": "Attachments for {name}",
        "attach_nothing": "This item has no attachment points, and none of your items takes "
                          "it. Only weapons, weapon parts, body parts and helmets have slots.",
        "attach_own_slots": "Slots on this item",
        "attach_hosts": "Your items this one fits",
        "attach_col_slot": "Slot",
        "attach_col_fitted": "Fitted part",
        "attach_col_host": "Item",
        "attach_col_where": "Location",
        "attach_free": "- free -",
        "attach_required": "required",
        "attach_btn_fit": "Fit part...",
        "attach_btn_detach": "Take off...",
        "attach_btn_fit_here": "Fit into this slot",
        "attach_select_slot": "Select a slot first.",
        "attach_select_host": "Select an item first.",
        "attach_slot_taken": "That slot already holds {name}. Take it off first.",
        "attach_none_owned": "You own no part that fits {slot}. The item info window lists "
                             "what the game allows there.",
        "attach_pick_title": "Choose a part",
        "attach_pick_prompt": "Which of your parts goes into {slot}?",
        "attach_failed": "The part could not be fitted.",
        "attach_hint": "A fitted part records its slot, and the parts already on it come "
                       "along. The game works out how much room the assembled item needs on "
                       "its own, and moves anything it cannot place into your mailbox - so "
                       "leave space around a weapon you are building up.",
        "attach_cramped": "{name} has no room left to grow where it stands. Tested in play: "
                          "the game keeps the weapon where it is and puts the part it could "
                          "not fit - {part} - into your mailbox. Move the weapon somewhere "
                          "with space around it first, or fit the part anyway and look in the "
                          "mailbox.\n\nFit it anyway?",
        "status_attached": "Fitted {part} into {slot} (not saved yet)",
        "ctx_spawn_preset": "Spawn Assembled...",
        "preset_title": "Assembled item",
        "preset_none": "The game ships no assembled configuration for this item. Only the "
                       "{total} firearm presets have one; everything else is spawned as "
                       "the bare item.",

        "preset_prompt": "The game ships more than one configuration for this weapon.",
        "preset_col_variant": "Configuration",
        "preset_col_parts": "Parts fitted",
        "preset_no_space": "No free space for the weapon in the container you picked.",
        "preset_partial": "{skipped} part(s) were left out: their slot was already taken.",
        "status_preset": "Spawned {name} with {parts} part(s) fitted (not saved yet)",
        "preset_outgrown": "This configuration of {name} grows to about {grown}, and the game "
                           "data says the weapon only grows to {ceiling}. Tested in play: the "
                           "game refuses such an item wherever it is put and delivers it to "
                           "your mailbox in pieces - no item in a real save sits at its own "
                           "maximum. {outgrown} of the {total} configurations are like "
                           "this.\n\nSpawn it "
                           "anyway?",
        "ctx_info": "Item Info",
        "info_title": "Item info",
        "info_value": "Value",
        "info_mass": "Weight",
        "info_size": "Size",
        "info_size_max": "{width}x{height}  (max {max_width}x{max_height})",
        "info_stack": "Stack",
        "info_stack_units": "up to {capacity} units",
        "info_wear": "Condition",
        "info_wear_cond": "wears out, 0 to 4",
        "info_wear_dur": "{max} charges",
        "info_none": "-",
        "info_credits": "{amount} Credits",
        "info_section_this_one": "This one",
        "info_where": "Location",
        "info_where_cell": "cell ({i}, {j})",
        "info_attachments": "{count} attached",
        "info_equipped": "equipped",
        "info_section_recycle": "Recycling",
        "info_recycle_your_level": "your recycler: level {level}",
        "info_recycle_no_module": "you have not built a recycler yet",
        "info_recycle_level": "Level {level}",
        "info_recycle_none": "Not recyclable. There is no recycler recipe for this item.",
        "info_recycle_above_you": "Every recipe for this item needs a higher recycler level "
                                  "than yours.",
        "info_section_used_in": "Used for",
        "info_used_in_none": "Not an ingredient in any recipe.",
        "info_used_in_row": "{name}   {count}x",
        "info_template": "Template",
        "info_copy": "Copy ID",
        "info_copied": "Template ID copied.",
        "info_no_game_data": "No game data for this template. Run Refresh Names from Game.",
        "info_hours": "{hours} h",
        "info_minutes": "{minutes} min",
        "info_seconds": "{seconds} s",
        "info_section_ammo": "Ammunition",
        "info_ammo_takes": "This weapon takes",
        "info_ammo_fits": "Fits these weapons",
        "info_ammo_none": "No weapon in the game data takes this cartridge.",
        "info_section_mods": "Attachments",
        "info_mods_none": "This item has no attachment points.",
        "info_mods_fitted": "fitted by default",
        "info_mods_required": "required",
        "info_section_fits_on": "Fits on",
        "info_fits_on_none": "Nothing in the game data has a slot for this item.",
        "info_fits_on_row": "{name}   {slot}",
        "info_fits_on_more": "... and {count} more",
        "info_slot_fallback": "Slot {type}",
        "status_repaired_custom": "Set condition on {count} item(s) (not saved yet)",
        "msg_select_letter": "Please select a letter first.",
        "msg_err_resolve_letter": "Could not resolve selected letter index.",
        "msg_err_letter_out_of_range": "Selected letter is out of range.",
        "msg_err_save_failed": "Failed to save changes:\n{exc}",
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
        "info_tab": "Tab {idx}",
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
        "tab_raw_json": "Raw JSON",
        "btn_copy_json": "📋 JSON kopieren",
        "msg_json_copied": "Kopiert!",
        "lbl_no_matches": "Keine Treffer",
        "btn_find_next": "Weiter",
        "btn_find_prev": "Zurück",
        "chk_json_wrap": "Zeilenumbruch",
        "lbl_json_staged": "● Ungespeichert (In-Memory)",
        "lbl_json_saved": "Gespeichert",
        "lbl_json_size": "Größe: {size}",
        "btn_refresh": "🔄 Spielnamen aktualisieren",
        "btn_reload": "📂 Neu laden",
        "msg_reload_title": "Spielstand neu laden",
        "msg_reload_discards": ("Beim Neuladen wird die Datei erneut von der Platte "
                                "gelesen.\n\nDeine ungespeicherten Änderungen beziehen "
                                "sich auf den gerade geladenen Stand und lassen sich nicht "
                                "übertragen - sie gehen verloren.\n\nTrotzdem neu laden?"),
        "status_reloaded": "Spielstand neu von der Platte gelesen",
        "btn_apply": "Änderungen übernehmen",
        "btn_discard": "Änderungen verwerfen",
        "lbl_scope": "Bereich:",
        "lbl_search": "Suche:",
        "btn_search": "Suchen",
        "status_search": "Suche: '{query}' - {count} Treffer",
        "btn_delete_mail": "Ausgewählten Brief löschen",
        "lbl_category": "Kategorie:",
        "lbl_subcategory": "Unterkategorie:",
        "ctx_add_to_inv": "Zum Inventar hinzufügen...",
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
        "col_cat_price": "Wert",
        "col_cat_mass": "Gewicht",
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
        "msg_mapping_new_items": "{count} Items sind seit der letzten Auffrischung neu.\nDer Katalog hebt sie hervor; \"Nur neue\" zeigt nur sie.",
        "cat_only_new": "Nur neue ({count})",
        "target_no_room": "  -- kein Platz für dieses Objekt",
        "place_size": "Benötigter Platz: {w} x {h} Felder",
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
        "msg_skill_level_range": "Ungültige Stufe. Dieser Skill geht von 0 bis {max_level}.",
        "msg_trader_level_range": "Ungültige Stufe. Ein Händler geht von {min_level} bis {max_level}.",
        "msg_trader_balance_range": "Ungültiges Guthaben. Dieser Händler hält 0 bis {max_balance} - alles darüber stutzt das Spiel beim Laden zurecht.",
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
        "tab_quests": "Quests",
        "tab_crafting": "Herstellung",
        "craft_count": "{modules} Werkbänke, {recipes} Rezepte, {ready} sofort herstellbar",
        "quest_counts_filtered": "{count} von {total} Quests passen zu '{query}'",
        "craft_count_filtered": "{recipes} Rezepte passen zu '{query}', {ready} davon machbar",
        "craft_no_data": "Keine Herstellungsdaten. Bitte Namen aus dem Spiel aktualisieren.",
        "craft_module_row": "{name}  —  Stufe {level} von {max}  ({count} Rezepte)",
        "craft_level_row": "Braucht Stufe {level}  ({count})",
        "craft_col_recipe": "Rezept",
        "craft_col_needs": "Braucht",
        "craft_col_time": "Dauer",
        "craft_col_state": "Status",
        "craft_state_ready": "machbar",
        "craft_state_missing": "Zutaten fehlen",
        "craft_state_locked": "Stufe zu niedrig",
        "craft_state_unbuildable": "noch nicht im Spiel",
        "craft_detail_makes": "Ergibt",
        "craft_detail_needs": "Braucht (im Lager / nötig)",
        "craft_detail_where": "Werkbank",
        "craft_detail_where_value": "{name}, braucht Stufe {needed} — gebaut {level} von {max}",
        "craft_detail_time": "Dauer",
        "craft_detail_internal": "Interner Name",
        "craft_hint": "Nur zur Ansicht — der Editor stellt nichts her. Das Recyceln steht "
                      "nicht hier: es ist dieselbe Rezeptliste von der Gegenstandsseite, und "
                      "das Infofenster zeigt sie. „Noch nicht im Spiel“ heißt, das Rezept "
                      "verlangt eine Werkbankstufe, für die es keinen Bauschritt gibt.",
        "col_quest_status": "Status",
        "col_quest_flags": "Merkmale",
        "col_quest_sender": "Absender",
        "col_quest_reward": "Belohnung",
        "quest_status_active": "Aktiv",
        "quest_status_done": "Erledigt",
        "quest_status_unseen": "Nie gesehen",
        "quest_flag_hidden": "nicht gelistet",
        "quest_flag_shadow": "verdeckt",
        "quest_group_none": "Ohne Gruppe",
        "quests_hint": "Nur zur Ansicht. Was das Spiel mitbringt, gegen das, was dieser Spielstand kennt. Der Fortschritt einer laufenden Quest steht gar nicht im Spielstand und kann deshalb nicht angezeigt werden. Wohin man muss und worauf man achten sollte, steht ebenso wenig in den Spieldateien — der Knopf oben öffnet einen Community-Guide auf Steam, geschrieben von einem anderen Spieler, in deinem Browser.",
        "quests_guide_btn": "Community-Guide ↗",
        "quests_empty": "Keine Questdaten. Mit „Refresh Names from Game“ aus den Spieldateien lesen.",
        "quest_pick": "Wähle eine Quest, um den vollen Text zu sehen.",
        "quest_detail_alias": "Interner Name",
        "quest_detail_status": "Status",
        "quest_detail_task": "Aufgabe",
        "quest_detail_requires": "Setzt voraus",
        "quest_detail_level": "Accountlevel",
        "quest_detail_sender": "Geschickt von",
        "quest_detail_rewards": "Belohnung",
        "quest_detail_none": "keine",
        "quest_reward_xp": "{xp} EP",
        "quest_level_range": "{min} bis {max}",
        "quest_counts": "{total} Quests im Spiel, {seen} begegnet, {unseen} nie gesehen",
        "msg_single_only": "{action} geht nur mit einer Zeile - ausgewaehlt sind mehrere.",
        "msg_inbox_offer": "Nicht platziert: {names}. Stattdessen ins Postfach schicken? Abgeholt wird im Spiel.",
        "msg_inbox_needs_parts": "Diese brauchen eingebaute Teile und kaemen als loser Haufen an, deshalb bleiben sie fuer dich zum Platzieren: {names}.",
        "cb_category_colors": "Kategorie-Farben",
        "btn_restore_backup": "Backup zurückspielen...",
        "restore_title": "Backup zurückspielen",
        "restore_prompt": "Welches Backup soll deinen Spielstand ersetzen?",
        "restore_hint": "Der aktuelle Spielstand wird vorher weggesichert, das hier ist also ebenfalls umkehrbar. Im Backup-Ordner wird nichts gelöscht.",
        "diff_apply_title": "Änderungen bestätigen",
        "diff_apply_intro": "Das wird in die Spielstanddatei geschrieben. Vorher entsteht eine "
                            "Sicherung der aktuellen Datei mit Zeitstempel.",
        "diff_restore_title": "Zurückspielen bestätigen",
        "diff_restore_intro": "Das würde sich in Ihrem aktuellen Spielstand ändern, wenn "
                              "{name} zurückgespielt wird. Die aktuelle Datei wird vorher "
                              "weggesichert.",
        "diff_compare_title": "Mit Sicherung vergleichen",
        "diff_compare_intro": "Wie sich {name} von der Datei auf der Platte unterscheidet. Es "
                              "wird nichts geschrieben.",
        "diff_btn_compare": "Vergleichen...",
        "diff_intro": "Der Unterschied zwischen den beiden Spielständen.",
        "diff_col_what": "Was",
        "diff_col_before": "Vorher",
        "diff_col_after": "Nachher",
        "diff_added": "Neue Gegenstände ({count})",
        "diff_removed": "Entfernte Gegenstände ({count})",
        "diff_changed": "Geänderte Gegenstände ({count})",
        "diff_fields": "Weitere Änderungen ({count})",
        "diff_more": "... und {count} weitere",
        "diff_nothing": "Keine Unterschiede.",
        "diff_absent": "— nicht gesetzt —",
        "diff_unreadable": "Der Spielstand auf der Platte ist nicht lesbar, die Änderungen "
                           "lassen sich also nicht auflisten. Trotzdem schreiben?",
        "diff_unreadable_compare": "Eine der beiden Dateien ist nicht als Spielstand lesbar, "
                                   "es gibt also nichts zu vergleichen.",
        "restore_col_when": "Erstellt",
        "restore_col_label": "Anlass",
        "restore_col_size": "Größe",
        "restore_none": "Es gibt noch keine Backups. Eines entsteht bei jedem Übernehmen.",
        "restore_pending": "Du hast nicht übernommene Änderungen. Beim Zurückspielen gehen sie verloren.\n\nFortfahren?",
        "restore_confirm": "Deinen Spielstand durch dieses Backup ersetzen?\n\n{name}\n\nDer aktuelle Stand wird vorher in den Backup-Ordner kopiert.",
        "btn_restore": "Zurückspielen",
        "status_restored": "{name} zurückgespielt (bisheriger Stand als {backup} gesichert)",
        "msg_restore_failed": "Backup konnte nicht zurückgespielt werden:\n{exc}",
        "ctx_repair_custom": "Gegenstand setzen auf...",
        "ctx_duplicate_custom": "Gegenstand duplizieren...",
        "custom_title_repair": "Auf einen Wert setzen",
        "custom_repair_prompt": "{name} trägt {field}. Setzen auf:",
        "custom_repair_children": "Auch auf Anbauteile anwenden",
        "mint_checkbox": "Stattdessen auf fabrikneu setzen",
        "mint_hint": "Fabrikneu entfernt den Verschleiß-Eintrag, statt eine Zahl zu setzen: Das Spiel nennt einen Gegenstand nur mint, solange er gar keine Zustandsdaten trägt - eine Reparatur auf Maximum bleibt eine Reparatur.",
        "status_mint": "{count} Gegenstände sind jetzt fabrikneu (noch nicht gespeichert)",
        "status_mint_nothing": "Nichts zu tun - hier steht überhaupt kein Verschleiß drin, und genau das heißt fabrikneu.",
        "btn_cheat_mint": "\u2728 Alles auf fabrikneu",
        "msg_mint_all_confirm": "Alle {count} Gegenstände im Spielstand auf fabrikneu setzen?\n\nJeder Zustands- und Haltbarkeitseintrag wird entfernt - so speichert das Spiel einen nie benutzten Gegenstand.",
        "msg_cheats_mint": "Fertig. {count} Gegenstände tragen keinen Verschleiß mehr.",
        "custom_repair_none": "Dieser Gegenstand trägt keine Zustandsdaten, und seine Anbauteile auch nicht. Das Spiel legt diese Felder erst an, wenn ein Gegenstand nicht mehr makellos ist — es gibt hier also nichts zu setzen.",
        "custom_repair_field_cond": "Zustand (0 bis {max})",
        "custom_repair_field_dur": "Ladungen (0 bis {max})",
        "custom_title_duplicate": "Duplizieren",
        "custom_count": "Wie viele Kopien:",
        "custom_units": "Stück pro Stapel (max. {capacity}):",
        "custom_target": "Wohin:",
        "custom_condition": "Anfangs-{field}:",
        "custom_condition_hint": "Beim Maximum entsteht der Gegenstand makellos - so legt das Spiel einen unberührten Gegenstand ab, ganz ohne Zustandsfeld. Ein kleinerer Wert erzeugt ihn abgenutzt.",
        "custom_nothing_else": "Dieser Gegenstand stapelt nicht und trägt keinen Zustand - mehr gibt es hier nicht einzustellen.",
        "custom_value_range": "Der Wert muss zwischen {low} und {high} liegen.",
        "ctx_move": "Gegenstand verschieben...",
        "move_title": "Gegenstand verschieben",
        "move_prompt": "{name} verschieben nach:",
        "move_hint": "Anbauteile kommen mit, und ein ausgerüsteter Gegenstand lässt seinen "
                     "Platz leer zurück. Die freigewordene Zelle bleibt frei — es rückt "
                     "nichts nach.",
        "move_structural": "Lagerreiter und die Wurzelbehälter gehören zum Aufbau des "
                           "Spielstands und sind keine Gegenstände. Sie lassen sich nicht "
                           "verschieben.",
        "move_no_space": "In {target} ist kein Platz für diesen Gegenstand "
                         "({width}x{height}).",
        "move_failed": "Der Gegenstand konnte nicht verschoben werden.",
        "status_moved": "{count} Gegenstand/Gegenstände nach {target} verschoben (noch nicht gespeichert)",
        "ctx_split": "Stapel teilen...",
        "ctx_stack_size": "Stapelgröße setzen...",
        "stack_title": "Stapelgröße",
        "stack_not_stackable": "Dieser Gegenstand ist kein Stapel, es gibt also keine Größe zu setzen.",
        "stack_prompt": "Wie viele Einheiten soll der Stapel enthalten? Aktuell {current} von höchstens {max}.",
        "stack_prompt_nomax": "Wie viele Einheiten soll der Stapel enthalten? Aktuell {current}; die Spieldaten nennen kein Maximum dafür.",
        "status_stack_set": "{name} enthält jetzt {count} Einheiten (noch nicht gespeichert)",
        "btn_cheat_stacks": "\U0001f4e6 Alle Stapel auffüllen",
        "msg_cheats_stacks": "{count} Stapel aufgefüllt, {units} Einheiten dazugekommen.",
        "msg_cheats_stacks_none": "Alle Stapel sind bereits voll.",
        "status_cheat_stacks": "{count} Stapel aufgefüllt, {units} Einheiten dazugekommen (noch nicht gespeichert)",
        "split_title": "Stapel teilen",
        "split_prompt": "Wie viele der {quantity} Stück abtrennen:",
        "split_hint": "Die abgetrennten Stück werden ein zweiter Stapel, der Rest bleibt "
                      "liegen. Alles abzutrennen wäre ein Verschieben und kein Teilen — "
                      "mindestens ein Stück muss zurückbleiben.",
        "split_not_stackable": "Dieser Gegenstand ist kein Stapel. Teilen lässt sich nur, "
                               "was eine Stückzahl trägt, und dieser hier ist ein einzelnes "
                               "Stück.",
        "split_no_space": "In {target} ist kein Platz für den zweiten Stapel.",
        "status_split": "{amount} von {quantity} Stück abgetrennt (noch nicht gespeichert)",
        "ctx_attachments": "Anbauteile...",
        "attach_title": "Anbauteile",
        "attach_for": "Anbauteile für {name}",
        "attach_nothing": "Dieser Gegenstand hat keine Aufnahmen, und keiner Ihrer "
                          "Gegenstände nimmt ihn auf. Slots haben nur Waffen, Waffenteile, "
                          "Körperteile und Helme.",
        "attach_own_slots": "Aufnahmen an diesem Gegenstand",
        "attach_hosts": "Ihre Gegenstände, auf die dieser passt",
        "attach_col_slot": "Aufnahme",
        "attach_col_fitted": "Verbautes Teil",
        "attach_col_host": "Gegenstand",
        "attach_col_where": "Ort",
        "attach_free": "— frei —",
        "attach_required": "erforderlich",
        "attach_btn_fit": "Teil montieren...",
        "attach_btn_detach": "Abnehmen...",
        "attach_btn_fit_here": "In diese Aufnahme montieren",
        "attach_select_slot": "Bitte zuerst eine Aufnahme auswählen.",
        "attach_select_host": "Bitte zuerst einen Gegenstand auswählen.",
        "attach_slot_taken": "In dieser Aufnahme sitzt schon {name}. Nehmen Sie es zuerst ab.",
        "attach_none_owned": "Sie besitzen kein Teil, das in {slot} passt. Das Infofenster "
                             "zeigt, was das Spiel dort erlaubt.",
        "attach_pick_title": "Teil auswählen",
        "attach_pick_prompt": "Welches Ihrer Teile soll in {slot}?",
        "attach_failed": "Das Teil konnte nicht montiert werden.",
        "attach_hint": "Ein montiertes Teil merkt sich seine Aufnahme, und die Teile daran "
                       "kommen mit. Wie viel Platz der zusammengebaute Gegenstand braucht, "
                       "rechnet das Spiel selbst aus — was es nicht platzieren kann, landet in "
                       "deinem Postfach. Lass um eine Waffe, die du aufbaust, also Platz.",
        "attach_cramped": "{name} hat an seinem Platz keinen Raum zum Wachsen. Im Spiel "
                          "getestet: die Waffe bleibt liegen, und das Teil, das nicht mehr "
                          "hineinpasst — {part} — landet in deinem Postfach. Verschiebe die "
                          "Waffe erst dorthin, wo Platz drumherum ist, oder montiere trotzdem "
                          "und sieh ins Postfach.\n\nTrotzdem montieren?",
        "status_attached": "{part} in {slot} montiert (noch nicht gespeichert)",
        "ctx_spawn_preset": "Fertig aufgebaut spawnen...",
        "preset_title": "Fertig aufgebauter Gegenstand",
        "preset_none": "Für diesen Gegenstand liefert das Spiel keine fertige Konfiguration. "
                       "Nur die {total} Schusswaffen-Presets haben eine; alles andere entsteht als "
                       "nackter Gegenstand.",
        "preset_prompt": "Das Spiel liefert für diese Waffe mehr als eine Konfiguration.",
        "preset_col_variant": "Konfiguration",
        "preset_col_parts": "Verbaute Teile",
        "preset_no_space": "Im gewählten Behälter ist kein Platz für die Waffe.",
        "preset_partial": "{skipped} Teil(e) blieben weg: ihre Aufnahme war schon belegt.",
        "status_preset": "{name} mit {parts} Teil(en) gespawnt (noch nicht gespeichert)",
        "preset_outgrown": "Diese Konfiguration der {name} wächst auf etwa {grown}, und laut "
                           "Spieldaten wächst die Waffe nur bis {ceiling}. Im Spiel getestet: "
                           "das Spiel lehnt so einen Gegenstand überall ab und legt ihn in "
                           "Einzelteilen in dein Postfach — kein Gegenstand in einem echten "
                           "Spielstand steht auf seinem eigenen Maximum. {outgrown} der {total} "
                           "Konfigurationen sind so.\n\nTrotzdem spawnen?",
        "ctx_info": "Info zum Gegenstand",
        "info_title": "Gegenstandsinfo",
        "info_value": "Wert",
        "info_mass": "Gewicht",
        "info_size": "Größe",
        "info_size_max": "{width}x{height}  (max. {max_width}x{max_height})",
        "info_stack": "Stapel",
        "info_stack_units": "bis {capacity} Stück",
        "info_wear": "Zustand",
        "info_wear_cond": "nutzt sich ab, 0 bis 4",
        "info_wear_dur": "{max} Ladungen",
        "info_none": "-",
        "info_credits": "{amount} Credits",
        "info_section_this_one": "Dieses Exemplar",
        "info_where": "Ort",
        "info_where_cell": "Zelle ({i}, {j})",
        "info_attachments": "{count} Anbauteile",
        "info_equipped": "ausgerüstet",
        "info_section_recycle": "Recyceln",
        "info_recycle_your_level": "dein Recycler: Stufe {level}",
        "info_recycle_no_module": "du hast noch keinen Recycler gebaut",
        "info_recycle_level": "Stufe {level}",
        "info_recycle_none": "Nicht recycelbar. Für diesen Gegenstand gibt es kein "
                             "Recycler-Rezept.",
        "info_recycle_above_you": "Alle Rezepte für diesen Gegenstand brauchen einen höher "
                                  "ausgebauten Recycler als deinen.",
        "info_section_used_in": "Wird gebraucht für",
        "info_used_in_none": "Ist in keinem Rezept Zutat.",
        "info_used_in_row": "{name}   {count}x",
        "info_template": "Vorlage",
        "info_copy": "ID kopieren",
        "info_copied": "Vorlagen-ID kopiert.",
        "info_no_game_data": "Keine Spieldaten zu dieser Vorlage. Führe Spielnamen "
                             "aktualisieren aus.",
        "info_hours": "{hours} Std.",
        "info_minutes": "{minutes} Min.",
        "info_seconds": "{seconds} Sek.",
        "info_section_ammo": "Munition",
        "info_ammo_takes": "Diese Waffe nimmt",
        "info_ammo_fits": "Passt in diese Waffen",
        "info_ammo_none": "Keine Waffe in den Spieldaten nimmt diese Patrone.",
        "info_section_mods": "Anbauteile",
        "info_mods_none": "Dieser Gegenstand hat keine Anbaupunkte.",
        "info_mods_fitted": "standardmäßig verbaut",
        "info_mods_required": "erforderlich",
        "info_section_fits_on": "Passt an",
        "info_fits_on_none": "Nichts in den Spieldaten hat einen Slot für diesen Gegenstand.",
        "info_fits_on_row": "{name}   {slot}",
        "info_fits_on_more": "... und {count} weitere",
        "info_slot_fallback": "Slot {type}",
        "status_repaired_custom": "Zustand an {count} Gegenstand/Gegenständen gesetzt (noch nicht gespeichert)",
        "msg_select_letter": "Bitte wählen Sie zuerst einen Brief aus.",
        "msg_err_resolve_letter": "Index des ausgewählten Briefs konnte nicht aufgelöst werden.",
        "msg_err_letter_out_of_range": "Ausgewählter Brief liegt außerhalb des Bereichs.",
        "msg_err_save_failed": "Änderungen konnten nicht gespeichert werden:\n{exc}",
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
        "info_tab": "Reiter {idx}",
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
        "tab_raw_json": "Raw JSON",
        "btn_copy_json": "📋 Копировать JSON",
        "msg_json_copied": "Скопировано!",
        "lbl_no_matches": "Нет совпадений",
        "btn_find_next": "Далее",
        "btn_find_prev": "Назад",
        "chk_json_wrap": "Перенос строк",
        "lbl_json_staged": "● Не сохранено (В памяти)",
        "lbl_json_saved": "Сохранено",
        "lbl_json_size": "Размер: {size}",
        "btn_refresh": "🔄 Обновить имена из игры",
        "btn_reload": "📂 Перечитать",
        "msg_reload_title": "Перезагрузка сохранения",
        "msg_reload_discards": ("При перезагрузке файл будет прочитан заново.\n\n"
                                "Несохранённые изменения относятся к текущей версии "
                                "и будут потеряны.\n\nВсё равно перезагрузить?"),
        "status_reloaded": "Сохранение перечитано с диска",
        "btn_apply": "Применить изменения",
        "btn_discard": "Сбросить изменения",
        "lbl_scope": "Область:",
        "lbl_search": "Поиск:",
        "btn_search": "Найти",
        "status_search": "Поиск: '{query}' - совпадений: {count}",
        "btn_delete_mail": "Удалить выбранное письмо",
        "lbl_category": "Категория:",
        "lbl_subcategory": "Подкатегория:",
        "ctx_add_to_inv": "Добавить в инвентарь...",
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
        "col_cat_price": "Цена",
        "col_cat_mass": "Вес",
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
        "msg_mapping_new_items": "Новых предметов с прошлого обновления: {count}.\nВ каталоге они выделены; «Только новые» покажет только их.",
        "cat_only_new": "Только новые ({count})",
        "target_no_room": "  -- нет места для этого предмета",
        "place_size": "Требуется места: {w} x {h} клеток",
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
        "msg_skill_level_range": "Неверный уровень. У этого навыка диапазон 0-{max_level}.",
        "msg_trader_level_range": "Неверный уровень. У торговца диапазон {min_level}-{max_level}.",
        "msg_trader_balance_range": "Неверный баланс. У этого торговца диапазон 0-{max_balance} - всё сверх игра урезает при загрузке.",
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
        "tab_quests": "Квесты",
        "tab_crafting": "Крафт",
        "craft_count": "Верстаков: {modules}, рецептов: {recipes}, готово к крафту: {ready}",
        "quest_counts_filtered": "\u041f\u043e '{query}': {count} \u0438\u0437 {total} \u043a\u0432\u0435\u0441\u0442\u043e\u0432",
        "craft_count_filtered": "\u041f\u043e '{query}': {recipes} \u0440\u0435\u0446\u0435\u043f\u0442\u043e\u0432, \u0433\u043e\u0442\u043e\u0432\u043e {ready}",
        "craft_no_data": "Нет данных о крафте. Обновите названия из игры.",
        "craft_module_row": "{name}  —  построено {level} из {max}  (рецептов: {count})",
        "craft_level_row": "Нужен уровень {level}  ({count})",
        "craft_col_recipe": "Рецепт",
        "craft_col_needs": "Требует",
        "craft_col_time": "Время",
        "craft_col_state": "Статус",
        "craft_state_ready": "готово",
        "craft_state_missing": "не хватает",
        "craft_state_locked": "уровень мал",
        "craft_state_unbuildable": "ещё нет в игре",
        "craft_detail_makes": "Даёт",
        "craft_detail_needs": "Требует (в наличии / нужно)",
        "craft_detail_where": "Верстак",
        "craft_detail_where_value": "{name}, нужен уровень {needed} — построено {level} из {max}",
        "craft_detail_time": "Время",
        "craft_detail_internal": "Внутреннее имя",
        "craft_hint": "Только просмотр: редактор не крафтит. Переработка здесь не показана — "
                      "это тот же список рецептов со стороны предмета, и его показывает окно "
                      "информации. «Ещё нет в игре» значит, что рецепт требует уровня "
                      "верстака, для которого в игре нет шага постройки.",
        "col_quest_status": "Статус",
        "col_quest_flags": "Признаки",
        "col_quest_sender": "Отправитель",
        "col_quest_reward": "Награда",
        "quest_status_active": "Активные",
        "quest_status_done": "Завершённые",
        "quest_status_unseen": "Ни разу не встречались",
        "quest_flag_hidden": "нет в списке",
        "quest_flag_shadow": "скрытый",
        "quest_group_none": "Без группы",
        "quests_hint": "Только для просмотра. Что есть в игре против того, что встречалось в этом сохранении. Прогресса активного квеста в сохранении нет вовсе, поэтому показать его нельзя. Куда идти и на что смотреть, в файлах игры тоже не записано — кнопка выше открывает в браузере руководство сообщества на Steam, написанное другим игроком.",
        "quests_guide_btn": "Руководство сообщества ↗",
        "quests_empty": "Нет данных о квестах. Нажмите Refresh Names from Game.",
        "quest_pick": "Выберите квест, чтобы увидеть полный текст.",
        "quest_detail_alias": "Внутреннее имя",
        "quest_detail_status": "Статус",
        "quest_detail_task": "Задание",
        "quest_detail_requires": "Требует",
        "quest_detail_level": "Уровень аккаунта",
        "quest_detail_sender": "Отправитель",
        "quest_detail_rewards": "Награда",
        "quest_detail_none": "нет",
        "quest_reward_xp": "{xp} опыта",
        "quest_level_range": "от {min} до {max}",
        "quest_counts": "в игре квестов: {total}, встречено: {seen}, ни разу: {unseen}",
        "msg_single_only": "{action}: только для одной строки — выбрано несколько.",
        "msg_inbox_offer": "Не размещено: {names}. Отправить их в почту? Забрать можно в игре.",
        "msg_inbox_needs_parts": "Этим нужны установленные детали, они пришли бы россыпью, поэтому остаются вам для размещения: {names}.",
        "cb_category_colors": "Цвета категорий",
        "btn_restore_backup": "Восстановить копию...",
        "restore_title": "Восстановление из копии",
        "restore_prompt": "Какая копия должна заменить сохранение?",
        "restore_hint": "Текущее сохранение сначала копируется, так что действие обратимо. В папке копий ничего не удаляется.",
        "diff_apply_title": "Подтверждение изменений",
        "diff_apply_intro": "Это будет записано в файл сохранения. Сначала создаётся копия "
                            "текущего файла с отметкой времени.",
        "diff_restore_title": "Подтверждение восстановления",
        "diff_restore_intro": "Вот что изменится в текущем сохранении, если вернуть {name}. "
                              "Текущий файл сначала копируется.",
        "diff_compare_title": "Сравнение с копией",
        "diff_compare_intro": "Чем {name} отличается от файла на диске. Ничего не пишется.",
        "diff_btn_compare": "Сравнить...",
        "diff_intro": "Разница между двумя сохранениями.",
        "diff_col_what": "Что",
        "diff_col_before": "До",
        "diff_col_after": "После",
        "diff_added": "Новые предметы ({count})",
        "diff_removed": "Удалённые предметы ({count})",
        "diff_changed": "Изменённые предметы ({count})",
        "diff_fields": "Прочие изменения ({count})",
        "diff_more": "... и ещё {count}",
        "diff_nothing": "Различий нет.",
        "diff_absent": "— не задано —",
        "diff_unreadable": "Сохранение на диске не читается, перечислить изменения нельзя. "
                           "Всё равно записать?",
        "diff_unreadable_compare": "Один из двух файлов не читается как сохранение, сравнивать "
                                   "нечего.",
        "restore_col_when": "Создана",
        "restore_col_label": "Повод",
        "restore_col_size": "Размер",
        "restore_none": "Копий пока нет. Они создаются при каждом применении изменений.",
        "restore_pending": "Есть несохранённые изменения. При восстановлении они пропадут.\n\nПродолжить?",
        "restore_confirm": "Заменить сохранение этой копией?\n\n{name}\n\nТекущее сохранение сначала попадёт в папку копий.",
        "btn_restore": "Восстановить",
        "status_restored": "Восстановлено {name} (прежнее сохранено как {backup})",
        "msg_restore_failed": "Не удалось восстановить копию:\n{exc}",
        "ctx_repair_custom": "Задать состояние...",
        "ctx_duplicate_custom": "Дублировать предмет...",
        "custom_title_repair": "Задать значение",
        "custom_repair_prompt": "{name} имеет {field}. Задать:",
        "custom_repair_children": "Применить и к присоединённым предметам",
        "mint_checkbox": "\u0412\u043c\u0435\u0441\u0442\u043e \u044d\u0442\u043e\u0433\u043e \u0441\u0434\u0435\u043b\u0430\u0442\u044c \u043d\u043e\u0432\u044b\u043c",
        "mint_hint": "\u041d\u043e\u0432\u044b\u0439 \u0432\u0438\u0434 \u0443\u0431\u0438\u0440\u0430\u0435\u0442 \u0437\u0430\u043f\u0438\u0441\u044c \u043e\u0431 \u0438\u0437\u043d\u043e\u0441\u0435, \u0430 \u043d\u0435 \u0441\u0442\u0430\u0432\u0438\u0442 \u0447\u0438\u0441\u043b\u043e: \u0438\u0433\u0440\u0430 \u0441\u0447\u0438\u0442\u0430\u0435\u0442 \u0432\u0435\u0449\u044c \u043d\u043e\u0432\u043e\u0439, \u043f\u043e\u043a\u0430 \u0443 \u043d\u0435\u0451 \u0432\u043e\u043e\u0431\u0449\u0435 \u043d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u043e \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0438.",
        "status_mint": "\u041d\u043e\u0432\u044b\u043c\u0438 \u0441\u0442\u0430\u043b\u0438: {count} (\u0435\u0449\u0451 \u043d\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e)",
        "status_mint_nothing": "\u041d\u0435\u0447\u0435\u0433\u043e \u0434\u0435\u043b\u0430\u0442\u044c - \u0438\u0437\u043d\u043e\u0441\u0430 \u043d\u0435\u0442 \u0432\u043e\u0432\u0441\u0435, \u044d\u0442\u043e \u0438 \u0435\u0441\u0442\u044c \u043d\u043e\u0432\u043e\u0435 \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435.",
        "btn_cheat_mint": "\u2728 \u0412\u0441\u0451 \u043a\u0430\u043a \u043d\u043e\u0432\u043e\u0435",
        "msg_mint_all_confirm": "\u0421\u0434\u0435\u043b\u0430\u0442\u044c \u0432\u0441\u0435 {count} \u043f\u0440\u0435\u0434\u043c\u0435\u0442\u043e\u0432 \u043d\u043e\u0432\u044b\u043c\u0438?\n\n\u0412\u0441\u0435 \u0437\u0430\u043f\u0438\u0441\u0438 \u043e \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0438 \u0438 \u043f\u0440\u043e\u0447\u043d\u043e\u0441\u0442\u0438 \u0443\u0434\u0430\u043b\u044f\u044e\u0442\u0441\u044f.",
        "msg_cheats_mint": "\u0413\u043e\u0442\u043e\u0432\u043e. \u0411\u0435\u0437 \u0438\u0437\u043d\u043e\u0441\u0430: {count}.",
        "custom_repair_none": "У этого предмета нет данных о состоянии, как и у его навесок. Игра создаёт эти поля, лишь когда предмет перестаёт быть идеальным.",
        "custom_repair_field_cond": "состояние (от 0 до {max})",
        "custom_repair_field_dur": "заряды (от 0 до {max})",
        "custom_title_duplicate": "Дублирование",
        "custom_count": "Сколько копий:",
        "custom_units": "Штук в стаке (макс. {capacity}):",
        "custom_target": "Куда:",
        "custom_condition": "Начальное значение — {field}:",
        "custom_condition_hint": "При максимуме предмет создаётся идеальным: именно так игра хранит нетронутый предмет — без поля состояния вообще. Меньшее значение даёт потрёпанный предмет.",
        "custom_nothing_else": "Этот предмет не стакается и не имеет состояния — больше здесь нечего настраивать.",
        "custom_value_range": "Значение должно быть от {low} до {high}.",
        "ctx_move": "Переместить предмет...",
        "move_title": "Перемещение предмета",
        "move_prompt": "Переместить {name} в:",
        "move_hint": "Навески перемещаются вместе с предметом, а надетый предмет освобождает "
                     "свой слот. Освободившаяся ячейка так и остаётся пустой — соседи не "
                     "сдвигаются.",
        "move_structural": "Вкладки склада и корневые контейнеры — часть структуры "
                           "сохранения, а не предметы, поэтому переместить их нельзя.",
        "move_no_space": "В {target} нет места для этого предмета ({width}x{height}).",
        "move_failed": "Не удалось переместить предмет.",
        "status_moved": "Перемещено предметов: {count} → {target} (ещё не сохранено)",
        "ctx_split": "Разделить стак...",
        "ctx_stack_size": "\u0417\u0430\u0434\u0430\u0442\u044c \u0440\u0430\u0437\u043c\u0435\u0440 \u0441\u0442\u0430\u043a\u0430...",
        "stack_title": "\u0420\u0430\u0437\u043c\u0435\u0440 \u0441\u0442\u0430\u043a\u0430",
        "stack_not_stackable": "\u042d\u0442\u043e \u043d\u0435 \u0441\u0442\u0430\u043a, \u0440\u0430\u0437\u043c\u0435\u0440 \u0437\u0430\u0434\u0430\u0432\u0430\u0442\u044c \u043d\u0435\u0447\u0435\u043c\u0443.",
        "stack_prompt": "\u0421\u043a\u043e\u043b\u044c\u043a\u043e \u0435\u0434\u0438\u043d\u0438\u0446 \u0432 \u0441\u0442\u0430\u043a\u0435? \u0421\u0435\u0439\u0447\u0430\u0441 {current} \u0438\u0437 {max}.",
        "stack_prompt_nomax": "\u0421\u043a\u043e\u043b\u044c\u043a\u043e \u0435\u0434\u0438\u043d\u0438\u0446 \u0432 \u0441\u0442\u0430\u043a\u0435? \u0421\u0435\u0439\u0447\u0430\u0441 {current}; \u043c\u0430\u043a\u0441\u0438\u043c\u0443\u043c \u0432 \u0434\u0430\u043d\u043d\u044b\u0445 \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d.",
        "status_stack_set": "\u0412 {name} \u0442\u0435\u043f\u0435\u0440\u044c {count} \u0435\u0434\u0438\u043d\u0438\u0446 (\u0435\u0449\u0451 \u043d\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e)",
        "btn_cheat_stacks": "\U0001f4e6 \u0417\u0430\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0432\u0441\u0435 \u0441\u0442\u0430\u043a\u0438",
        "msg_cheats_stacks": "\u0417\u0430\u043f\u043e\u043b\u043d\u0435\u043d\u043e \u0441\u0442\u0430\u043a\u043e\u0432: {count}, \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043e {units}.",
        "msg_cheats_stacks_none": "\u0412\u0441\u0435 \u0441\u0442\u0430\u043a\u0438 \u0443\u0436\u0435 \u043f\u043e\u043b\u043d\u044b\u0435.",
        "status_cheat_stacks": "\u0417\u0430\u043f\u043e\u043b\u043d\u0435\u043d\u043e {count}, \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043e {units} (\u0435\u0449\u0451 \u043d\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e)",
        "split_title": "Разделение стака",
        "split_prompt": "Сколько штук отделить из {quantity}:",
        "split_hint": "Отделённые штуки станут вторым стаком, остальное останется на месте. "
                      "Отделить всё — это перемещение, а не разделение, поэтому хотя бы одна "
                      "штука должна остаться.",
        "split_not_stackable": "Этот предмет не стак. Разделить можно только то, что несёт "
                               "количество, а здесь всего одна штука.",
        "split_no_space": "В {target} нет места для второго стака.",
        "status_split": "Отделено {amount} из {quantity} шт. (ещё не сохранено)",
        "ctx_attachments": "Навесное...",
        "attach_title": "Навесное оборудование",
        "attach_for": "Навесное для {name}",
        "attach_nothing": "У этого предмета нет посадочных мест, и ни один из ваших предметов "
                          "его не принимает. Слоты есть только у оружия, частей оружия, частей "
                          "тела и шлемов.",
        "attach_own_slots": "Посадочные места этого предмета",
        "attach_hosts": "Ваши предметы, на которые он подходит",
        "attach_col_slot": "Слот",
        "attach_col_fitted": "Установленная часть",
        "attach_col_host": "Предмет",
        "attach_col_where": "Место",
        "attach_free": "— свободно —",
        "attach_required": "обязательно",
        "attach_btn_fit": "Установить часть...",
        "attach_btn_detach": "Снять...",
        "attach_btn_fit_here": "Установить в этот слот",
        "attach_select_slot": "Сначала выберите слот.",
        "attach_select_host": "Сначала выберите предмет.",
        "attach_slot_taken": "В этом слоте уже стоит {name}. Сначала снимите её.",
        "attach_none_owned": "У вас нет части, подходящей в {slot}. Окно информации "
                             "показывает, что игра там допускает.",
        "attach_pick_title": "Выбор части",
        "attach_pick_prompt": "Какую из ваших частей поставить в {slot}?",
        "attach_failed": "Не удалось установить часть.",
        "attach_hint": "Установленная часть запоминает свой слот, и части на ней переходят "
                       "вместе с ней. Сколько места занимает собранный предмет, игра считает "
                       "сама, а то, что она не может разместить, попадает в почтовый ящик — "
                       "оставляйте место вокруг оружия, которое собираете.",
        "attach_cramped": "{name} негде расти на своём месте. Проверено в игре: оружие "
                          "остаётся на месте, а часть, которая не поместилась — {part} — "
                          "попадает в ваш почтовый ящик. Сначала переставьте оружие туда, где "
                          "вокруг есть место, либо установите всё равно и посмотрите в "
                          "ящик.\n\nВсё равно установить?",
        "status_attached": "{part} установлена в {slot} (ещё не сохранено)",
        "ctx_spawn_preset": "Создать в сборе...",
        "preset_title": "Предмет в сборе",
        "preset_none": "Для этого предмета игра не содержит готовой сборки. Она есть только у "
                       "{total} пресетов огнестрельного оружия; всё остальное создаётся без частей.",
        "preset_prompt": "Игра содержит для этого оружия несколько сборок.",
        "preset_col_variant": "Сборка",
        "preset_col_parts": "Установленные части",
        "preset_no_space": "В выбранном контейнере нет места для оружия.",
        "preset_partial": "Частей пропущено: {skipped} — их слот уже был занят.",
        "status_preset": "{name} создан, частей установлено: {parts} (ещё не сохранено)",
        "preset_outgrown": "Эта сборка {name} вырастает примерно до {grown}, а по данным игры "
                           "оружие растёт только до {ceiling}. Проверено в игре: игра "
                           "отказывается от такого предмета в любом месте и присылает его в "
                           "почтовый ящик по частям — ни один предмет в реальном сохранении не "
                           "стоит на своём максимуме. Таких сборок {outgrown} из {total}.\n\n"
                           "Всё равно "
                           "создать?",
        "ctx_info": "Информация о предмете",
        "info_title": "Информация о предмете",
        "info_value": "Цена",
        "info_mass": "Вес",
        "info_size": "Размер",
        "info_size_max": "{width}x{height}  (макс. {max_width}x{max_height})",
        "info_stack": "Стак",
        "info_stack_units": "до {capacity} шт.",
        "info_wear": "Состояние",
        "info_wear_cond": "изнашивается, от 0 до 4",
        "info_wear_dur": "зарядов: {max}",
        "info_none": "-",
        "info_credits": "{amount} кредитов",
        "info_section_this_one": "Этот экземпляр",
        "info_where": "Где",
        "info_where_cell": "ячейка ({i}, {j})",
        "info_attachments": "навесок: {count}",
        "info_equipped": "надет",
        "info_section_recycle": "Переработка",
        "info_recycle_your_level": "ваш переработчик: уровень {level}",
        "info_recycle_no_module": "переработчик ещё не построен",
        "info_recycle_level": "Уровень {level}",
        "info_recycle_none": "Не перерабатывается. Рецепта переработки для этого предмета "
                             "нет.",
        "info_recycle_above_you": "Всем рецептам для этого предмета нужен переработчик "
                                  "выше вашего уровня.",
        "info_section_used_in": "Используется для",
        "info_used_in_none": "Не входит ни в один рецепт.",
        "info_used_in_row": "{name}   {count}x",
        "info_template": "Шаблон",
        "info_copy": "Копировать ID",
        "info_copied": "ID шаблона скопирован.",
        "info_no_game_data": "Нет игровых данных для этого шаблона. Выполните «Обновить "
                             "названия из игры».",
        "info_hours": "{hours} ч",
        "info_minutes": "{minutes} мин",
        "info_seconds": "{seconds} с",
        "info_section_ammo": "Патроны",
        "info_ammo_takes": "Оружие принимает",
        "info_ammo_fits": "Подходит к оружию",
        "info_ammo_none": "В игровых данных нет оружия под этот патрон.",
        "info_section_mods": "Модификации",
        "info_mods_none": "У этого предмета нет точек крепления.",
        "info_mods_fitted": "установлено по умолчанию",
        "info_mods_required": "обязательно",
        "info_section_fits_on": "Ставится на",
        "info_fits_on_none": "В игровых данных нет предмета со слотом под это.",
        "info_fits_on_row": "{name}   {slot}",
        "info_fits_on_more": "... и ещё {count}",
        "info_slot_fallback": "Слот {type}",
        "status_repaired_custom": "Состояние задано для {count} предметов (ещё не сохранено)",
        "msg_select_letter": "Сначала выберите письмо.",
        "msg_err_resolve_letter": "Не удалось определить индекс выбранного письма.",
        "msg_err_letter_out_of_range": "Выбранное письмо находится вне диапазона.",
        "msg_err_save_failed": "Не удалось сохранить изменения:\n{exc}",
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
        "info_tab": "Вкладка {idx}",
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

# How many "used for" rows the info window shows at once. Anything beyond scrolls - the list
# is never cut short, because the templates with the most uses are the crafting staples and
# they are exactly what someone opens this section to look up.
INFO_USED_IN_ROWS = 8

# Marks the recycler stage that applies to the player's own module. Named rather than
# inlined so the tests can look for it without repeating the character.
INFO_MARKER = "▸ "

# Visible rows of the attachment tree before it scrolls. Kept low on purpose: an assault rifle
# resolves to a 19-row tree, and showing it whole pushed the window to 835px, which clips the
# Close button on a 768px screen.
INFO_MOD_ROWS = 8

# The change list groups by section and shows this many rows per group before it says how many
# more there are. A trader stock refresh rewrites some 1400 leaves on its own - measured on two
# real saves a day apart - and a flat list of those buries the two changes the user made.
DIFF_SECTION_LIMIT = 40

# Groups this small start open; bigger ones stay collapsed so the window opens on a summary.
DIFF_OPEN_ROWS = 12

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
        # Answers "does this item or anything under it match", filled while a filtered tree
        # is built and dropped again afterwards: a match depends on the query.
        self._search_match_cache: dict[str, bool] = {}
        # One item's searchable text, built once per populate run instead of once per
        # question about the item. Query-independent on purpose - the expand path can ask
        # with a fresher query than the tree was built with, so caching the *match* here
        # would hand it a stale answer. Same lifecycle as the match cache above.
        self._search_haystack_cache: dict[str, str] = {}
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
        # What the last "Refresh Names from Game" added. Persisted, so the answer to "what
        # did the update bring" survives closing the editor - which is when it is usually
        # asked. Cleared and rewritten by the next refresh.
        self.new_template_ids: set[str] = load_config_new_templates()

        self.dpi_scale = self._get_dpi_scale()
        self.root.title("Cargo Hunters Save Editor")
        self._set_window_icon()
        # **Both numbers are measured, and 1100x680 was too small.** `tests/test_window_size.py`
        # walks every tab in all three languages and compares each control bar's requested
        # width against what the window actually leaves it; at 1100x680 it fails on:
        #
        #   the header, 1112px in Russian against 1084 available - the two header buttons
        #   the height, 702px in German against 680 - the Hackerman tab's left column
        #
        # 1140 leaves the Russian header 12px of air, 710 leaves German 8. The old 680 was
        # chosen for that same German column when it needed 487px; it has grown since, and
        # nothing was measuring it.
        #
        # Two things had to be fixed before any number could be right, both in this file:
        # the status label no longer asks for the width of the save path (see `width=1` on
        # it), and the catalog toolbar is two rows, because on one it wanted 1276px in
        # Russian and threw Apply and Discard off the edge.
        #
        # Both are pixel counts at 96 DPI, so they scale with the display - at 200% the same
        # layout needs twice the room. Capped at the screen size, because a minimum larger
        # than the panel it sits on cannot be satisfied at all.
        base_min_w, base_min_h = 1140, 710
        min_w = min(self._scale_px(base_min_w), self.root.winfo_screenwidth())
        min_h = min(self._scale_px(base_min_h), self.root.winfo_screenheight())
        self.root.minsize(min_w, min_h)
        # Opens with a little air above the minimum rather than exactly at it - a window that
        # starts at its own floor looks broken the first time anything is resized.
        self._center_window(1180, 760)

        self._configure_ttk_styles()


        self.status_var = tk.StringVar(value=f"Save: {self.save_path}")
        self.scope_var = tk.StringVar()
        self.catalog_search_var = tk.StringVar()
        self.catalog_category_var = tk.StringVar(value="All")
        self.catalog_subcategory_var = tk.StringVar(value="All")
        self.catalog_only_new_var = tk.BooleanVar(value=False)
        self.category_colors_var = tk.BooleanVar(value=load_config_category_colors())
        self.music_playing = False
        self.music_process = None

        self.current_lang = load_config_lang()

        self._load_template_name_map()
        self._build_layout()
        self._load_scope_options()
        self._refresh_mailbox()
        self._refresh_quests_tree()
        self._refresh_crafting_tree()
        self.root.bind("<Control-s>", self._on_shortcut_save)
        self.root.bind("<Control-S>", self._on_shortcut_save)
        self.root.bind("<Control-f>", self._on_shortcut_find)
        self.root.bind("<Control-F>", self._on_shortcut_find)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_requested)
        self._start_music()

    def _build_layout(self) -> None:
        """Builds the whole window: header, the eight notebook pages, the status bar.

        The eight tab builders now stand in one list, which makes the one surprising thing
        about them readable: **they do not run in tab order.** Help, Hackerman, Quests,
        Crafting and Raw JSON are built before Inventory, Mailbox and Catalog, exactly as
        they were - the three at the end were written inline here while the five had
        methods already. Nothing depends on it, but changing it would move every Tk widget
        path in the window, so it stays.

        Three things have to stay at the end, in this order: the Apply/Discard pairs can
        only be collected once every tab that has one exists, `_refresh_pending_buttons`
        reads those lists, and `_update_ui_language` is what puts the first text on all of
        it - every widget above is created without a label.

        One line changed rather than moved: the three tabs that were built inline here
        named their page as `self.tab_inventory` / `_mailbox` / `_catalog`, and their
        builders take it as `parent` instead, the way the five older ones already did.
        """
        self._build_header()
        self._build_notebook()

        self._build_help_tab(self.tab_help)
        self._build_char_tab(self.tab_char)
        self._build_quests_tab(self.tab_quests)
        self._build_crafting_tab(self.tab_crafting)
        self._build_raw_json_tab(self.tab_raw_json)
        self._build_inventory_tab(self.tab_inventory)
        self._build_mailbox_tab(self.tab_mailbox)
        self._build_catalog_tab(self.tab_catalog)

        self._build_status_bar()

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

    def _build_header(self) -> None:
        """The strip above the notebook: title, subtitle, avatar, badge and two buttons.

        Its own method because it is the only part of the window outside the notebook and
        the status bar, and because it holds the one widget that may fail to appear - the
        avatar is loaded from a file that a stripped build need not have, so everything
        after it is packed on the right and lines up either way.
        """
        # Header Title
        header_frame = tk.Frame(self.root, bg=COLOR_BG)
        header_frame.pack(fill="x", padx=8, pady=(8, 2))

        self.title_label = tk.Label(
            header_frame,
            font=("TkDefaultFont", 12, "bold"),
            fg=COLOR_ACCENT,
            bg=COLOR_BG
        )
        self.title_label.pack(side="left")

        self.subtitle_label = tk.Label(
            header_frame,
            font=("TkDefaultFont", 9, "italic"),
            fg="#969696",
            bg=COLOR_BG
        )
        self.subtitle_label.pack(side="left", padx=10)

        # Hackerman avatar image on the far right
        image_path = self._asset_path("hackerman.png")
        if image_path.exists():
            try:
                self.hackerman_img = tk.PhotoImage(file=str(image_path))
                img_label = tk.Label(header_frame, image=self.hackerman_img, bg=COLOR_BG)
                img_label.pack(side="right", padx=(5, 10))
            except Exception as e:
                print(f"Could not load image: {e}")

        # Hackerman quote badge sits directly next to the Hackerman avatar
        self.badge_label = tk.Label(
            header_frame,
            text="[ HACKERMAN: I'm hacking you back in time! ]",
            font=("Consolas", 10, "bold"),
            fg="#ff007f",
            bg=COLOR_BG
        )
        self.badge_label.pack(side="right", padx=(10, 5))

        # Global Refresh Names button
        self.refresh_btn = ttk.Button(
            header_frame,
            command=self._refresh_names_from_game,
        )
        self.refresh_btn.pack(side="right", padx=(10, 5))

        # Re-read the save. It sits next to Refresh Names because both answer the same
        # question - "the data underneath has moved on, catch up" - one for the game's
        # assets, one for the save itself.
        self.reload_btn = ttk.Button(
            header_frame,
            command=self._reload_save_from_disk,
        )
        self.reload_btn.pack(side="right", padx=(0, 5))

    def _build_notebook(self) -> None:
        """The notebook and its eight pages, created empty.

        Separate from the builders that fill them because this is where the **tab order**
        is decided, and it is not the order of the frames above it: Catalog is added
        second although its frame is created third. `_update_ui_language` names its
        captions by frame rather than by index, so the two can differ without breaking -
        which is exactly why the difference needs a place where it is visible.
        """
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.tab_inventory = ttk.Frame(self.notebook)
        self.tab_mailbox = ttk.Frame(self.notebook)
        self.tab_catalog = ttk.Frame(self.notebook)
        self.tab_quests = ttk.Frame(self.notebook)
        self.tab_crafting = ttk.Frame(self.notebook)
        self.tab_char = ttk.Frame(self.notebook)
        self.tab_raw_json = ttk.Frame(self.notebook)
        self.tab_help = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_inventory)
        self.notebook.add(self.tab_catalog)
        self.notebook.add(self.tab_mailbox)
        self.notebook.add(self.tab_quests)
        self.notebook.add(self.tab_crafting)
        self.notebook.add(self.tab_char)
        self.notebook.add(self.tab_raw_json)
        self.notebook.add(self.tab_help)

    def _build_inventory_tab(self, parent: ttk.Frame) -> None:
        """The Inventory tab, in the same three parts every tab here has: a toolbar, a
        tree, and the menu that acts on the tree.

        It takes its page as an argument like the five tab builders that already existed,
        so all eight now read the same way from `_build_layout`. The menu takes none - it
        hangs off `self.root`, not off this page.
        """
        self._build_inventory_toolbar(parent)
        self._build_inventory_tree(parent)
        self._build_item_context_menu()

    def _build_inventory_toolbar(self, parent: ttk.Frame) -> None:
        """The inventory toolbar: scope, search, the colour switch, Apply and Discard.

        Its own block because the pack order is the layout: everything is
        `pack(side=...)`, so the two buttons on the right are the ones that get cut when
        a translation runs long - which is why they are packed before nothing else and
        why the toolbar is measured at the window's minimum width.
        """
        toolbar = ttk.Frame(parent)
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
        self.search_entry.bind("<Return>", lambda _: self._apply_search())
        self.search_btn = ttk.Button(toolbar, command=self._apply_search)
        self.search_btn.pack(side="left")
        self.category_colors_cb = ttk.Checkbutton(
            toolbar,
            variable=self.category_colors_var,
            command=self._on_category_colors_toggled,
        )
        self.category_colors_cb.pack(side="left", padx=(12, 0))
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

    def _build_inventory_tree(self, parent: ttk.Frame) -> None:
        """The item tree and every key that acts on it.

        Kept as one block because that is the list of keyboard shortcuts scoped to the
        tree: each is bound twice, lower and upper case, since Tk sees a different keysym
        with Caps Lock on. The scope is the point - these fire on the tree and nowhere
        else, so typing in a search field never deletes an item.
        """
        tree_wrap = ttk.Frame(parent)
        tree_wrap.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        tree_scroll = ttk.Scrollbar(tree_wrap, orient="vertical")
        tree_scroll.pack(side="right", fill="y")

        self.tree = ttk.Treeview(tree_wrap, show="tree", yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.tree.bind("<Delete>", lambda _e: self._delete_selected_items())
        self.tree.bind("<Control-d>", lambda _e: self._duplicate_selected())
        self.tree.bind("<Control-D>", lambda _e: self._duplicate_selected())
        self.tree.bind("<Control-r>", lambda _e: self._repair_selected())
        self.tree.bind("<Control-R>", lambda _e: self._repair_selected())
        self.tree.bind("<Control-m>", lambda _e: self._move_selected())
        self.tree.bind("<Control-M>", lambda _e: self._move_selected())
        self.tree.bind("<Control-i>", lambda _e: self._show_info_for_selected_item())
        self.tree.bind("<Control-I>", lambda _e: self._show_info_for_selected_item())
        self.tree.bind("<Control-a>", self._on_tree_select_all)
        self.tree.bind("<Control-A>", self._on_tree_select_all)
        tree_scroll.configure(command=self.tree.yview)
        self._apply_category_color_tags(self.tree)

    def _build_item_context_menu(self) -> None:
        """The inventory tree's right-click menu, eleven entries in a fixed order.

        A method of its own precisely because that order is a contract: the entries carry
        no labels here - `_update_ui_language` writes them **by index**, separator
        included - so adding a command anywhere but at the end moves a label onto the
        wrong action, and the wrong one deletes things. Three test files pin the shape.
        """
        self.context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            activebackground=COLOR_SELECTED,
            activeforeground=COLOR_WHITE
        )
        # Each action twice: the plain entry does the obvious thing without asking, the
        # "..." one opens a dialog. Keeping both means the common case stays one click.
        self.context_menu.add_command(command=self._repair_selected, accelerator="Ctrl+R")
        self.context_menu.add_command(command=self._repair_selected_custom)
        self.context_menu.add_command(command=self._duplicate_selected, accelerator="Ctrl+D")
        self.context_menu.add_command(command=self._duplicate_selected_custom)
        self.context_menu.add_command(command=self._move_selected, accelerator="Ctrl+M")
        self.context_menu.add_command(command=self._split_selected)
        self.context_menu.add_command(command=self._set_stack_size_selected)
        self.context_menu.add_command(command=self._open_attachments_dialog)
        self.context_menu.add_command(command=self._show_info_for_selected_item, accelerator="Ctrl+I")
        # The separator keeps the one destructive entry away from the rest. It occupies
        # index 9, so Delete is relabelled as index 10. Every label below is applied by
        # position, so inserting an entry above one of them moves a label onto the wrong
        # action - which is why the tests assert the order.
        self.context_menu.add_separator()
        self.context_menu.add_command(command=self._delete_selected_items, accelerator="Del")

    def _build_mailbox_tab(self, parent: ttk.Frame) -> None:
        """The Mailbox tab: a toolbar with the letter count, and a six-column list.

        The only one of the eight with no menu and no search, so it stays a single method
        rather than being split the way Inventory and Catalog are - the toolbar and the
        list are the whole tab.
        """
        mailbox_toolbar = ttk.Frame(parent)
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

        mailbox_wrap = ttk.Frame(parent)
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
        self.mail_tree.column("index", width=self._scale_px(60), anchor="center")
        self.mail_tree.column("sender", width=self._scale_px(220), anchor="w")
        self.mail_tree.column("message_ref", width=self._scale_px(230), anchor="w")
        self.mail_tree.column("rewards", width=self._scale_px(70), anchor="center")
        self.mail_tree.column("read", width=self._scale_px(70), anchor="center")
        self.mail_tree.column("mail_id", width=self._scale_px(360), anchor="w")
        self.mail_tree.pack(side="left", fill="both", expand=True)

    def _build_catalog_tab(self, parent: ttk.Frame) -> None:
        """The Game Items tab, in the same three parts as the Inventory tab.

        The toolbar is two rows rather than one, which is the one thing this tab does
        differently and the reason the toolbars have a method to themselves.
        """
        self._build_catalog_toolbars(parent)
        self._build_catalog_tree(parent)
        self._build_catalog_context_menu()

    def _build_catalog_toolbars(self, parent: ttk.Frame) -> None:
        """Both catalog toolbar rows, built as one block because the split between them
        **is** the decision this code records - see the measurement below.

        Note that the two rows are not filled in order: Apply and Discard belong to the
        first row and are created last, after everything on the second, so they end up on
        the right of the top row. Splitting this into a method per row would put that
        detail on a seam.
        """
        # **Two rows, and that is a measurement rather than taste.** On one row the filters
        # plus Apply/Discard ask for 1155px in English, 1262 in German and 1276 in Russian,
        # against the 1076 a 1100px-wide window leaves - so German and Russian were clipping
        # Apply and Discard off the right edge before the "only new" box was ever added, and
        # English was 26px from doing the same. Everything here is pack(side=...), so what
        # gets cut is whatever was packed last: exactly the two buttons that write to disk.
        #
        # Splitting by kind rather than evenly: the two dropdowns are the widest things in
        # here (160px each) and the search is what people use most, so it gets its own row
        # with room to spare. Worst case after the split is 845px, in Russian.
        catalog_toolbar = ttk.Frame(parent)
        catalog_toolbar.pack(fill="x", padx=4, pady=(4, 0))
        catalog_toolbar2 = ttk.Frame(parent)
        catalog_toolbar2.pack(fill="x", padx=4, pady=(2, 4))
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
        # Second row: the search and the "only new" filter.
        self.cat_search_lbl = ttk.Label(catalog_toolbar2)
        self.cat_search_lbl.pack(side="left", padx=(0, 6))
        self.cat_search_entry = ttk.Entry(
            catalog_toolbar2,
            textvariable=self.catalog_search_var,
            width=22,
        )
        self.cat_search_entry.pack(side="left", padx=(0, 6))
        self.cat_search_entry.bind("<Return>", lambda _event: self._refresh_catalog_tree())
        self.cat_search_btn = ttk.Button(
            catalog_toolbar2,
            command=self._refresh_catalog_tree,
        )
        self.cat_search_btn.pack(side="left")
        # A colour alone would mean scrolling ~1600 rows to find three dozen. The checkbox
        # is what makes the marking answer a question instead of decorating a list; its
        # label carries the count, so the number is readable without ticking it.
        self.cat_only_new_cb = ttk.Checkbutton(
            catalog_toolbar2,
            variable=self.catalog_only_new_var,
            command=self._refresh_catalog_tree,
        )
        self.cat_only_new_cb.pack(side="left", padx=(12, 0))
        self.cat_category_colors_cb = ttk.Checkbutton(
            catalog_toolbar2,
            variable=self.category_colors_var,
            command=self._on_category_colors_toggled,
        )
        self.cat_category_colors_cb.pack(side="left", padx=(12, 0))
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

    def _build_catalog_tree(self, parent: ttk.Frame) -> None:
        """The catalog list: eight columns, measured against the minimum window width.

        Its own block because the widths are that measurement and have to be read
        together - they add up to what fits, which is why the template id is cut to 150px
        instead of the 290 a full GUID needs. The two tag setups at the end are why a row
        can be coloured at all: the magenta for a template a game update brought, and the
        category colours the checkbox on the toolbar switches.
        """
        catalog_wrap = ttk.Frame(parent)
        catalog_wrap.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        catalog_scroll = ttk.Scrollbar(
            catalog_wrap,
            orient="vertical"
        )
        catalog_scroll.pack(side="right", fill="y")

        self.catalog_tree = ttk.Treeview(
            catalog_wrap,
            columns=("name", "template_id", "category", "subcategory", "size", "stack",
                     "price", "mass"),
            show="headings",
            height=14,
            yscrollcommand=catalog_scroll.set
        )
        catalog_scroll.configure(command=self.catalog_tree.yview)
        self.catalog_tree.column("name", width=self._scale_px(260), anchor="w")
        # 150, not the 290 a full GUID needs. Value and Weight pushed the eight columns to
        # 1190px against the window's 1100px minimum, so at the smallest size the last column
        # fell off the right edge with no way to scroll to it. This is the column worth
        # shortening: the full id is in the item info window, with a button to copy it.
        self.catalog_tree.column("template_id", width=self._scale_px(150), anchor="w")
        self.catalog_tree.column("category", width=self._scale_px(160), anchor="w")
        self.catalog_tree.column("subcategory", width=self._scale_px(170), anchor="w")
        self.catalog_tree.column("size", width=self._scale_px(70), anchor="center")
        self.catalog_tree.column("stack", width=self._scale_px(80), anchor="center")
        self.catalog_tree.column("price", width=self._scale_px(90), anchor="e")
        self.catalog_tree.column("mass", width=self._scale_px(70), anchor="e")
        self.catalog_tree.pack(side="left", fill="both", expand=True)
        # The app's accent, the same magenta the Help tab highlights with. Colour alone is
        # not the feature - the "only new" checkbox is - so it never has to be the only way
        # a row is recognised.
        self.catalog_tree.tag_configure("new_template", foreground="#ff007f")
        self._apply_category_color_tags(self.catalog_tree)
        self.catalog_tree.bind("<Button-3>", self._on_catalog_right_click)

    def _build_catalog_context_menu(self) -> None:
        """The catalog tree's right-click menu, four entries.

        Apart for the same reason as the item menu: it hangs off `self.root` rather than
        off the tab, and its labels are written by index later, so the order is a contract
        the tests pin. Both catalog actions live here rather than on the toolbar because
        their translated labels clipped at the window's minimum width.
        """
        self.catalog_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            activebackground=COLOR_SELECTED,
            activeforeground=COLOR_WHITE
        )
        self.catalog_menu.add_command(command=self._add_selected_catalog_item_to_inventory)
        self.catalog_menu.add_command(command=self._spawn_preset_for_selected_catalog_row)
        self.catalog_menu.add_command(command=self._offer_selected_catalog_item_at_trader)
        self.catalog_menu.add_command(command=self._show_info_for_selected_catalog_row)

    def _build_status_bar(self) -> None:
        """The bottom strip: the three app-wide settings on the right, the status text on
        the left.

        One block because the packing order is what puts them there: language, mute,
        retention and Restore are packed `side="right"` in that sequence, so each new one
        lands to the left of the last, and the status label is packed last with
        `expand=True` to take whatever is left. They sit here rather than on a tab toolbar
        because the German and Russian labels already crowd those at the minimum width.
        """
        status_bar_frame = ttk.Frame(self.root)
        status_bar_frame.pack(fill="x", padx=8, pady=(0, 8))

        # Language Selector dropdown menu next to the mute button (packed first to preserve right-side placement)
        self.lang_btn = ttk.Menubutton(
            status_bar_frame,
            direction="below",
        )
        self.lang_btn.pack(side="right", padx=(6, 0))

        self.lang_menu = tk.Menu(
            self.lang_btn,
            tearoff=0,
            bg=COLOR_PANEL,
            fg=COLOR_WHITE,
            activebackground=COLOR_SELECTED,
            activeforeground=COLOR_WHITE,
            bd=1,
            relief="solid",
            font=("TkDefaultFont", 9),
        )
        self.lang_btn["menu"] = self.lang_menu

        for code, label in (("en", "US"), ("de", "DE"), ("ru", "RU")):
            flag_img = self.flags.get(code)
            self.lang_menu.add_command(
                label=f"  {label}    ",
                image=flag_img,
                compound="left",
                hidemargin=True,
                command=lambda c=code: self._set_language(c),
            )

        self.mute_button = ttk.Button(
            status_bar_frame,
            # The emoji renders wider than a character cell, so 8 cut the German "Stumm"
            # down to "Stumr". Measured against the longest of the six labels.
            width=11,
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

        # Next to the retention field, because both are about the same folder.
        self.restore_button = ttk.Button(
            status_bar_frame,
            command=self._open_restore_backup_dialog,
        )
        self.restore_button.pack(side="right", padx=(12, 0))

        # `width=1` is not a typo and not a size - it is what stops the status text from
        # deciding how wide the window has to be. A ttk.Label asks for as many pixels as its
        # text needs, and this text carries the **save path**: measured at 740px for
        # `C:\Program Files (x86)\Steam\userdata\...\remote\offline.save`, which dragged the
        # whole window's requested width to 1290 and made the declared minimum unreachable.
        # A longer path would have asked for more, so no fixed minsize could ever have been
        # right. With a minimal request and `expand=True` the label still gets every pixel
        # that is left over; only its *demand* is bounded, and long text is cut at the edge.
        status_bar = ttk.Label(status_bar_frame, textvariable=self.status_var, anchor="w",
                               relief="flat", style="Status.TLabel", width=1)
        status_bar.pack(side="left", fill="x", expand=True)

    def _get_dpi_scale(self) -> float:
        try:
            dpi = self.root.winfo_fpixels("1i")
            if dpi > 0:
                return max(1.0, round(dpi / 96.0, 2))
        except Exception:
            pass
        return 1.0

    def _scale_px(self, val: int) -> int:
        return int(round(val * getattr(self, "dpi_scale", 1.0)))

    def _init_language_flags(self) -> None:
        """Generates crisp, high-DPI scaled flag bitmaps for US, Germany, and Russia."""
        scale = getattr(self, "dpi_scale", 1.0)
        w = max(int(round(20 * scale)), 20)
        h = max(int(round(14 * scale)), 14)

        if HAS_PIL:
            def make_bands(top: str, mid: str, bot: str) -> tk.PhotoImage:
                """Eine Flagge aus drei waagerechten Streifen - Deutschland und Russland.

                Stand zweimal nebeneinander, Wort fuer Wort gleich bis auf die drei Farben.
                Die Ersatzfassung ohne PIL weiter unten war laengst parametrisiert; hier war
                es nur nicht nachgezogen worden.
                """
                im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                h3 = h / 3.0
                d.rectangle([0, 0, w, int(round(h3))], fill=top)
                d.rectangle([0, int(round(h3)), w, int(round(2 * h3))], fill=mid)
                d.rectangle([0, int(round(2 * h3)), w, h], fill=bot)
                d.rectangle([0, 0, w - 1, h - 1], outline="#555555", width=1)
                return ImageTk.PhotoImage(im, master=self.root)

            def make_us() -> tk.PhotoImage:
                im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                for i in range(13):
                    y0 = int(round(i * h / 13.0))
                    y1 = int(round((i + 1) * h / 13.0))
                    col = "#b22234" if i % 2 == 0 else COLOR_WHITE
                    d.rectangle([0, y0, w, y1], fill=col)
                cw = int(round(w * 0.44))
                ch = int(round(7.0 * h / 13.0))
                d.rectangle([0, 0, cw, ch], fill="#3c3b6e")
                for r in range(3):
                    for c in range(4):
                        sx = int(round((c + 0.8) * cw / 4.6))
                        sy = int(round((r + 0.8) * ch / 3.6))
                        if scale >= 1.8:
                            d.rectangle([sx, sy, sx + 1, sy + 1], fill=COLOR_WHITE)
                        else:
                            d.point((sx, sy), fill=COLOR_WHITE)
                d.rectangle([0, 0, w - 1, h - 1], outline="#555555", width=1)
                return ImageTk.PhotoImage(im, master=self.root)

            self.flags = {
                "en": make_us(),
                "de": make_bands("#111111", "#dd0000", "#ffce00"),
                "ru": make_bands(COLOR_WHITE, "#0039a6", "#d52b1e"),
            }
        else:
            def make_fallback(color_top: str, color_mid: str, color_bot: str) -> tk.PhotoImage:
                img = tk.PhotoImage(master=self.root, width=w, height=h)
                h3 = h // 3
                img.put(color_top, to=(0, 0, w, h3))
                img.put(color_mid, to=(0, h3, w, 2 * h3))
                img.put(color_bot, to=(0, 2 * h3, w, h))
                return img

            def make_fallback_us() -> tk.PhotoImage:
                img = tk.PhotoImage(master=self.root, width=w, height=h)
                for i in range(7):
                    y0 = i * h // 7
                    y1 = (i + 1) * h // 7
                    col = "#b22234" if i % 2 == 0 else COLOR_WHITE
                    img.put(col, to=(0, y0, w, y1))
                cw = w * 4 // 10
                ch = h * 4 // 7
                img.put("#3c3b6e", to=(0, 0, cw, ch))
                return img

            self.flags = {
                "en": make_fallback_us(),
                "de": make_fallback("#111111", "#dd0000", "#ffce00"),
                "ru": make_fallback(COLOR_WHITE, "#0039a6", "#d52b1e"),
            }

    def _init_checkbox_style(self) -> None:
        """Configures a crisp, high-DPI scaled dark-mode checkbutton indicator.

        clam's built-in tick box is hardcoded to 96 DPI and uses coarse, jagged lines.
        This generates clean rounded indicators with custom hover, selected, and active
        states that match the editor's retro cyberpunk dark theme.
        """
        scale = getattr(self, "dpi_scale", 1.0)
        box_size = max(int(round(16 * scale)), 16)
        gap = max(int(round(6 * scale)), 6)
        total_w = box_size + gap
        total_h = box_size

        def make_indicator_image(bg_color: str, border_color: str, check: bool = False,
                                 disabled: bool = False) -> tk.PhotoImage:
            if HAS_PIL:
                im = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                radius = max(int(round(3 * scale)), 2)
                border_w = max(int(round(1 * scale)), 1)
                d.rounded_rectangle(
                    [0, 0, box_size - 1, box_size - 1],
                    radius=radius,
                    fill=bg_color,
                    outline=border_color,
                    width=border_w,
                )
                if check:
                    p1 = (int(round(box_size * 0.26)), int(round(box_size * 0.50)))
                    p2 = (int(round(box_size * 0.44)), int(round(box_size * 0.72)))
                    p3 = (int(round(box_size * 0.76)), int(round(box_size * 0.26)))
                    check_w = max(int(round(2 * scale)), 2)
                    check_col = (110, 110, 110, 255) if disabled else (255, 255, 255, 255)
                    d.line([p1, p2, p3], fill=check_col, width=check_w, joint="round")
                return ImageTk.PhotoImage(im, master=self.root)
            else:
                img = tk.PhotoImage(master=self.root, width=total_w, height=total_h)
                img.put(COLOR_BG, to=(0, 0, total_w, total_h))
                img.put(border_color, to=(0, 0, box_size, box_size))
                img.put(bg_color, to=(1, 1, box_size - 1, box_size - 1))
                img.put(COLOR_BG, to=(0, 0, 1, 1))
                img.put(COLOR_BG, to=(box_size - 1, 0, box_size, 1))
                img.put(COLOR_BG, to=(0, box_size - 1, 1, box_size))
                img.put(COLOR_BG, to=(box_size - 1, box_size - 1, box_size, box_size))
                if check:
                    p1 = (int(round(box_size * 0.26)), int(round(box_size * 0.50)))
                    p2 = (int(round(box_size * 0.44)), int(round(box_size * 0.72)))
                    p3 = (int(round(box_size * 0.76)), int(round(box_size * 0.26)))
                    thick = max(1, int(round(1.5 * scale)))
                    check_col = "#707070" if disabled else COLOR_WHITE

                    def draw_line(x0: int, y0: int, x1: int, y1: int) -> None:
                        steps = max(abs(x1 - x0), abs(y1 - y0)) * 3
                        for s in range(steps + 1):
                            t = s / max(steps, 1)
                            cx = int(round(x0 + t * (x1 - x0)))
                            cy = int(round(y0 + t * (y1 - y0)))
                            for dx in range(thick):
                                for dy in range(thick):
                                    if 0 <= cx + dx < box_size and 0 <= cy + dy < box_size:
                                        img.put(check_col, to=(cx + dx, cy + dy, cx + dx + 1, cy + dy + 1))
                    draw_line(p1[0], p1[1], p2[0], p2[1])
                    draw_line(p2[0], p2[1], p3[0], p3[1])
                return img

        self._checkbox_images = {
            "unchecked": make_indicator_image("#252528", "#4e4e52"),
            "unchecked_hover": make_indicator_image("#2d2d32", COLOR_ACCENT),
            "checked": make_indicator_image(COLOR_SELECTED, COLOR_ACCENT, check=True),
            "checked_hover": make_indicator_image("#1177bb", "#5aa9ff", check=True),
            "disabled": make_indicator_image(COLOR_BG, "#383838", disabled=True),
        }

        try:
            self.style.element_create(
                "Checkbutton.custom_indicator", "image", self._checkbox_images["unchecked"],
                ("disabled", self._checkbox_images["disabled"]),
                ("selected", "active", self._checkbox_images["checked_hover"]),
                ("selected", self._checkbox_images["checked"]),
                ("active", self._checkbox_images["unchecked_hover"]),
            )
        except tk.TclError:
            pass

        self.style.layout(
            "TCheckbutton", [
                ("Checkbutton.padding", {
                    "sticky": "nswe",
                    "children": [
                        ("Checkbutton.custom_indicator", {"side": "left", "sticky": ""}),
                        ("Checkbutton.focus", {
                            "side": "left",
                            "sticky": "w",
                            "children": [
                                ("Checkbutton.label", {"sticky": "nswe"})
                            ]
                        })
                    ]
                })
            ]
        )
        self.style.configure(
            "TCheckbutton",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            padding=[max(self._scale_px(4), 4), max(self._scale_px(3), 3)],
        )
        self.style.map(
            "TCheckbutton",
            foreground=[("disabled", "#6a6a6a"), ("active", COLOR_WHITE)],
            background=[("active", COLOR_BG)],
        )

    def _configure_ttk_styles(self) -> None:
        """Das ganze Aussehen: Farben, Schriften, Raender fuer jedes ttk-Element.

        Stand als 183 Zeilen mitten in `__init__`, zwischen der Fenstergroesse und den
        Tk-Variablen. Nichts davon liest oder schreibt etwas ausser `self.style` und
        `self.root` - keine Closure, keine Reihenfolge, die nach aussen wirkt -, und genau
        deshalb ist es der eine Block dieser Datei, den man ohne Risiko herausnehmen kann.

        Woertlich verschoben: der Koerper ist Zeile fuer Zeile derselbe wie vorher, samt der
        Kommentare, die einzelne Messungen festhalten. Wer hier etwas aendert, aendert das
        Aussehen - und das ist eine Entscheidung des Nutzers, keine Nebenwirkung.
        """
        # Style Setup (Premium Dark Mode)
        self.root.configure(bg=COLOR_BG)
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.style.configure(".", 
            background=COLOR_BG, 
            foreground=COLOR_TEXT,
            fieldbackground=COLOR_PANEL,
            troughcolor=COLOR_BG,
            bordercolor=COLOR_BORDER,
            lightcolor=COLOR_BORDER,
            darkcolor=COLOR_BG
        )
        
        self.style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", 
            background=COLOR_BG_RAISED, 
            foreground="#969696", 
            padding=[14, 6], 
            font=("TkDefaultFont", 9, "bold")
        )
        self.style.map("TNotebook.Tab", 
            background=[("selected", COLOR_BG), ("active", COLOR_BORDER)],
            foreground=[("selected", COLOR_ACCENT), ("active", COLOR_WHITE)]
        )
        
        self.style.configure("TFrame", background=COLOR_BG)
        self.style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        
        self.style.configure("TButton", 
            background=COLOR_BG_RAISED, 
            foreground=COLOR_TEXT, 
            bordercolor=COLOR_BORDER, 
            relief="flat", 
            padding=[8, 4]
        )
        self.style.map("TButton", 
            background=[("active", COLOR_SELECTED), ("pressed", "#094771")],
            foreground=[("active", COLOR_WHITE), ("pressed", COLOR_WHITE)]
        )
        
        self.style.configure("TEntry", 
            fieldbackground=COLOR_PANEL, 
            foreground=COLOR_WHITE, 
            insertcolor=COLOR_ACCENT,
            bordercolor=COLOR_BORDER
        )
        
        self.style.configure("TCombobox", 
            fieldbackground=COLOR_PANEL, 
            background=COLOR_BG, 
            foreground=COLOR_WHITE, 
            arrowcolor=COLOR_ACCENT,
            bordercolor=COLOR_BORDER,
            arrowsize=max(self._scale_px(14), 14),
        )
        self.style.map("TCombobox", 
            fieldbackground=[("readonly", COLOR_PANEL), ("active", COLOR_BG_RAISED)],
            background=[("readonly", COLOR_PANEL), ("active", COLOR_BG_RAISED)],
            foreground=[("readonly", COLOR_WHITE), ("active", COLOR_WHITE)]
        )
        self.root.option_add("*TCombobox*Listbox.background", COLOR_PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", COLOR_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", COLOR_SELECTED)
        self.root.option_add("*TCombobox*Listbox.selectForeground", COLOR_WHITE)
        
        self.style.configure("TMenubutton",
            fieldbackground=COLOR_PANEL,
            background=COLOR_PANEL,
            foreground=COLOR_WHITE,
            bordercolor=COLOR_BORDER,
            arrowcolor=COLOR_ACCENT,
            # **`arrowsize` is the triangle's radius here, not its box.** In `clam` a
            # `TMenubutton` draws an arrow twice this wide, which is why the numbers look
            # small next to `TScrollbar`, where the same option means the outer box. Copying
            # one across produced a 56px arrow once.
            #
            # Measured on this display at 2.0x: 3.5 gives a 7px radius, so a 14px arrow, and
            # the button asks for 109px. Every further unit widens the button by 2px - 7
            # would make it 123px, 14 would make it 151px, as wide as the Music button beside
            # it. The floor of 3 keeps the triangle visible at 1.0x.
            arrowsize=max(self._scale_px(3.5), 3),
            arrowpadding=max(self._scale_px(0.5), 1),
            width=0,
            padding=[max(self._scale_px(1.5), 2), max(self._scale_px(2), 2)],
        )
        self.style.map("TMenubutton",
            background=[("pressed", COLOR_SELECTED), ("active", COLOR_BG_RAISED)],
            arrowcolor=[("pressed", COLOR_WHITE), ("active", "#5aa9ff")],
        )

        # High-DPI flag icons for the language dropdown
        self._init_language_flags()

        # Bespoke high-DPI checkbox indicator matching the retro cyberpunk aesthetic
        self._init_checkbox_style()

        tree_indic_sz = max(self._scale_px(10), 10)
        tree_indic_margins = [self._scale_px(2), self._scale_px(2), self._scale_px(4), self._scale_px(2)]
        self.style.configure("Treeview", 
            background=COLOR_PANEL, 
            fieldbackground=COLOR_PANEL, 
            foreground=COLOR_TEXT,
            rowheight=max(self._scale_px(24), 24),
            indicatorsize=tree_indic_sz,
            indicatormargins=tree_indic_margins,
            borderwidth=0
        )
        self.style.configure("Treeview.Item",
            indicatorsize=tree_indic_sz,
            indicatormargins=tree_indic_margins,
        )
        self.style.map("Treeview", 
            background=[("selected", "#094771")],
            foreground=[("selected", COLOR_WHITE)]
        )
        self.style.configure("Heading", 
            background=COLOR_BG_RAISED, 
            foreground=COLOR_ACCENT, 
            font=("TkDefaultFont", 10, "bold"),
            borderwidth=0
        )
        
        self.style.configure("TScrollbar", 
            troughcolor=COLOR_BG, 
            background=COLOR_BG_RAISED, 
            arrowcolor=COLOR_ACCENT,
            bordercolor=COLOR_BORDER,
            width=max(self._scale_px(16), 16),
            arrowsize=max(self._scale_px(14), 14),
        )
        self.style.map("TScrollbar",
            background=[("pressed", COLOR_SELECTED), ("active", COLOR_BORDER)],
            arrowcolor=[("pressed", COLOR_WHITE), ("active", "#5aa9ff")],
        )
        
        # The level controls on the Skills and Traders tabs: a readout with its own arrows
        # next to a MAX button, sized to match the plain button beside them. The paddings
        # below are tuned so all three render the same height - measured, not guessed.
        self.style.configure("Level.TSpinbox",
            fieldbackground=COLOR_PANEL,
            foreground=COLOR_ACCENT,
            insertcolor=COLOR_ACCENT,
            arrowsize=max(self._scale_px(13), 13),
            arrowcolor=COLOR_ACCENT,
            bordercolor=COLOR_BORDER,
            padding=[2, 4]
        )
        # Same font family as a plain button so that a width in characters means the same
        # number of pixels on both; only the weight and the colour differ.
        self.style.configure("Step.TButton",
            background=COLOR_BG_RAISED,
            foreground=COLOR_ACCENT,
            font=("TkDefaultFont", 9, "bold"),
            relief="flat",
            padding=[8, 5]
        )
        self.style.map("Step.TButton",
            background=[("active", COLOR_SELECTED), ("pressed", "#094771")],
            foreground=[("active", COLOR_WHITE), ("pressed", COLOR_WHITE)]
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
        self.style.configure("Hint.TLabel", background=COLOR_BG, foreground="#9a9a9a")
        # The item info window's two headings. Bigger and brighter than the body, so the
        # sections read as sections without needing rules between them.
        self.style.configure("InfoTitle.TLabel", background=COLOR_BG, foreground="#e8e8e8",
                             font=("Segoe UI", 13, "bold"))
        self.style.configure("InfoSection.TLabel", background=COLOR_BG,
                             foreground="#c8c8c8", font=("Segoe UI", 10, "bold"))
        self.style.configure("Status.TLabel",
            foreground="#969696"
        )

    def _center_window(self, width: int = 1180, height: int = 760) -> None:
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        w = self._scale_px(width)
        h = self._scale_px(height)

        avail_w = max(400, screen_width - self._scale_px(40))
        avail_h = max(300, screen_height - self._scale_px(80))
        w = min(w, avail_w)
        h = min(h, avail_h)

        x = max(0, (screen_width - w) // 2)
        y = max(0, (screen_height - h - self._scale_px(40)) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _new_dialog(self, title: str) -> tk.Toplevel:
        """Ein leeres Dialogfenster im Aussehen des Editors.

        Die vier Zeilen standen vor jedem der elf Dialoge einzeln, in drei Schreibweisen -
        mal `transient` vor `configure`, mal andersherum, einmal mit einem Kommentar
        dazwischen. Wer den zwoelften baut, schreibt sonst eine vierte.

        `transient` haengt das Fenster an das Hauptfenster: es bekommt keinen eigenen Eintrag
        in der Taskleiste und verschwindet mit ihm. Und ohne `configure(bg=...)` behaelt das
        Toplevel den Systemhintergrund, sodass die dunklen Beschriftungen auf einem hellen
        Rechteck sitzen.

        **Was hier bewusst nicht steht, ist das Ende.** Die Dialoge schliessen in zwei
        Familien - sechs zentrieren ueber `_center_toplevel` auf dem Bildschirm, fuenf ueber
        `_center_over_root` auf dem Hauptfenster - und das ist ein sichtbarer Unterschied,
        keine Wiederholung, die man still zusammenlegen darf.
        """
        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        win.configure(bg=COLOR_BG)
        return win

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
        colors = ["#ff007f", COLOR_ACCENT, "#00f0ff", "#a020f0", "#39ff14"]
        if not hasattr(self, 'badge_color_idx'):
            self.badge_color_idx = 0

        self.badge_label.configure(fg=colors[self.badge_color_idx])
        self.badge_color_idx = (self.badge_color_idx + 1) % len(colors)

        # The handle exists so _shutdown can cancel this before destroy() - a callback
        # firing after the root is gone dies with "invalid command name".
        self._badge_after_id = self.root.after(400, self._animate_badge)

    def _populate_help_text(self) -> None:
        """Fuellt den Hilfereiter mit dem Text der aktuellen Sprache.

        Zweimal gebraucht - beim Aufbau des Reiters und bei jedem Sprachwechsel - und stand
        deshalb zweimal da, fast Zeile fuer Zeile gleich. Fast: die Aufbaustelle raeumte den
        Textbereich nicht vor dem Fuellen, weil er da noch leer ist, und holte die Sprache
        ueber einen `hasattr`-Rueckfall auf die Systemsprache.

        **Dieser Rueckfall war unerreichbar.** `__init__` setzt `self.current_lang` drei Zeilen
        vor `_build_layout`, und `_build_help_tab` wird von nirgends sonst gerufen. Er ist mit
        dieser Zusammenlegung weg, und mit ihm der einzige Aufrufer der Methode
        `_get_system_language`; die Funktion `get_system_language` auf Modulebene, die sie nur
        weiterreichte, bleibt und wird von `load_config_lang` gebraucht.

        Leeren vor dem Fuellen schadet beim Aufbau nicht: `delete` auf einem leeren Textfeld
        tut nichts, und `state="normal"` ist der Zustand, in dem es dort ohnehin steht.
        """
        self.help_text_area.configure(state="normal")
        self.help_text_area.delete("1.0", "end")
        help_text = HELP_TEXTE.get(self.current_lang, HELP_TEXT_EN)
        # `str.replace` statt `.format`: die Hilfetexte enthalten geschweifte Klammern in
        # Beispielen, und `.format` wuerde daran scheitern oder sie stillschweigend fressen.
        gesamt, ueber = self._preset_counts()
        einsetzen = {
            "{preset_total}": str(gesamt),
            "{preset_outgrown}": str(ueber),
            # Der getestete Build stand frueher als f-String im Text selbst. Seit die Texte
            # ein eigenes Modul ohne Importe sind, kommt er hier hinein - derselbe Weg wie
            # die Preset-Zahlen, und einer weniger, an den man denken muss.
            "{game_build}": GAME_BUILD_TESTED,
            "{game_build_steam}": GAME_BUILD_TESTED_STEAM,
            "{game_build_date}": GAME_BUILD_TESTED_DATE,
        }
        for text, tag in help_text:
            for platzhalter, wert in einsetzen.items():
                text = text.replace(platzhalter, wert)
            self.help_text_area.insert("end", text, tag)
        self.help_text_area.configure(state="disabled")

    def _set_language(self, new_lang: str) -> None:
        if new_lang in TRANSLATIONS and new_lang != self.current_lang:
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

    def _apply_category_color_tags(self, tree: ttk.Treeview | None = None) -> None:
        """Writes the category colours into one tree's tags, or into both when none is named.

        Switching the feature is exactly this call and nothing else: changing a tag's colour
        repaints every row already carrying it, so no row has to be inserted again and the
        scroll position and open branches survive. An empty foreground is how a tag says
        "no opinion" - the row falls back to the Treeview's own colour.
        """
        enabled = bool(self.category_colors_var.get())
        targets = [tree] if tree is not None else [getattr(self, "tree", None),
                                                   getattr(self, "catalog_tree", None)]
        for target in targets:
            if target is None:
                continue
            for tag, color in CATEGORY_COLORS.items():
                target.tag_configure(tag, foreground=color if enabled else "")

    def _on_category_colors_toggled(self) -> None:
        save_config_category_colors(bool(self.category_colors_var.get()))
        self._apply_category_color_tags()

    def _update_ui_language(self) -> None:
        """Relabels the whole window in `self.current_lang`, in a fixed order.

        The author's numbered blocks are the cut: 1-8 and 13 are methods below, in the
        order they had. The order is not cosmetic. Three of the blocks do not relabel
        widgets at all but **rebuild trees** - quests, crafting and the counters list -
        because the group, module and status names live inside the rows, so relabelling
        the headings alone leaves the rows in the old language. And block 5 deliberately
        does *not* refresh the subcategory chooser, because block 11 below ends in it.

        Blocks 9 to 12 stay here: each is already a single call or the four-line status
        line, and wrapping those in a method of their own would only hide the sequence.
        `t` is passed to every block instead of each one looking it up again - one lookup,
        one language, and the moved lines read exactly as they did.
        """
        t = TRANSLATIONS[self.current_lang]

        self._relabel_header(t)
        self._relabel_notebook_tabs(t)
        self._relabel_inventory_tab(t)
        self._relabel_mailbox_tab(t)
        self._relabel_catalog_tab(t)
        self._relabel_quests_tab(t)
        self._relabel_crafting_tab(t)
        self._relabel_catalog_columns(t)
        self._relabel_hackerman_tab(t)
        self._relabel_help_and_options(t)
        self._relabel_json_tab(t)

        # 9. Mute Button Text
        self._label_mute_button()

        # 10. Load scope options with the current selection kept
        self._load_scope_options()

        # 11. Update catalog category combobox
        self._refresh_catalog_filters()

        # 12. Refresh current status line
        if hasattr(self, "last_status_raw"):
            self._set_status(self.last_status_raw)
        else:
            self._set_status("status_welcome")

        self._relabel_language_button()

    def _relabel_header(self, t: dict[str, str]) -> None:
        """Block 1: the four widgets above the notebook.

        Its own method because the header is the one strip that belongs to no tab - it
        keeps the title and the two "the data underneath moved on" buttons, which are the
        only widgets outside the notebook that carry text.
        """
        # 1. Header Frame
        self.title_label.configure(text=t["title"])
        self.subtitle_label.configure(text=t["active_session"])
        self.refresh_btn.configure(text=t["btn_refresh"])
        self.reload_btn.configure(text=t["btn_reload"])

    def _relabel_notebook_tabs(self, t: dict[str, str]) -> None:
        """Block 2: the eight tab captions.

        Stands alone because it is the list of tabs, in tab order: a new tab is missing
        from the window's language the moment it is missing from these eight lines, and
        that is easier to see against nothing else.
        """
        # 2. Main Notebook Tabs
        self.notebook.tab(self.tab_inventory, text=t["tab_inventory"])
        self.notebook.tab(self.tab_mailbox, text=t["tab_mailbox"])
        self.notebook.tab(self.tab_catalog, text=t["tab_catalog"])
        self.notebook.tab(self.tab_quests, text=t["tab_quests"])
        self.notebook.tab(self.tab_crafting, text=t["tab_crafting"])
        self.notebook.tab(self.tab_char, text=t["tab_hackerman"])
        self.notebook.tab(self.tab_raw_json, text=t["tab_raw_json"])
        self.notebook.tab(self.tab_help, text=t["tab_help"])

    def _relabel_inventory_tab(self, t: dict[str, str]) -> None:
        """Block 3: the inventory toolbar, every Apply/Discard pair, and the item menu.

        The three belong together because two of them are not the inventory tab's alone:
        the Apply/Discard loops cover the pairs on Game Items, Mailbox and Hackerman as
        well, and the menu below them is relabelled **by position**, separator included.
        Splitting the menu off would leave those indices somewhere that does not say what
        they are indices into.
        """
        # 3. Inventory Tab
        self.scope_lbl.configure(text=t["lbl_scope"])
        self.search_lbl.configure(text=t["lbl_search"])
        self.search_btn.configure(text=t["btn_search"])
        # Covers the copies on the Game Items, Mailbox and Hackerman tabs as well.
        for button in self.apply_buttons:
            button.configure(text=t["btn_apply"])
        for button in self.discard_buttons:
            button.configure(text=t["btn_discard"])

        # Update context menu items. The indices are positional, so they move whenever an
        # entry is inserted above them.
        self.context_menu.entryconfigure(0, label=t["ctx_repair"])
        self.context_menu.entryconfigure(1, label=t["ctx_repair_custom"])
        self.context_menu.entryconfigure(2, label=t["ctx_duplicate"])
        self.context_menu.entryconfigure(3, label=t["ctx_duplicate_custom"])
        self.context_menu.entryconfigure(4, label=t["ctx_move"])
        self.context_menu.entryconfigure(5, label=t["ctx_split"])
        self.context_menu.entryconfigure(6, label=t["ctx_stack_size"])
        self.context_menu.entryconfigure(7, label=t["ctx_attachments"])
        self.context_menu.entryconfigure(8, label=t["ctx_info"])
        # Index 9 is the separator.
        self.context_menu.entryconfigure(10, label=t["ctx_delete"])

    def _relabel_mailbox_tab(self, t: dict[str, str]) -> None:
        """Block 4: the mailbox button and its six column headings.

        One tab, one method - the headings are the tab's only other text, and a column
        added to the tree is a heading missing here.
        """
        # 4. Mailbox Tab
        self.mail_delete_btn.configure(text=t["btn_delete_mail"])

        # Mailbox Table Headings
        self.mail_tree.heading("index", text=t["col_mail_index"])
        self.mail_tree.heading("sender", text=t["col_mail_sender"])
        self.mail_tree.heading("message_ref", text=t["col_mail_subject"])
        self.mail_tree.heading("rewards", text=t["col_mail_rewards"])
        self.mail_tree.heading("read", text=t["col_mail_read"])
        self.mail_tree.heading("mail_id", text=t["col_mail_id"])

    def _relabel_catalog_tab(self, t: dict[str, str]) -> None:
        """Block 5: the three search toolbars and the catalog's own right-click menu.

        It is one block although the Quests and Crafting search boxes are not on this tab:
        all three were built from the catalog's, share `lbl_search` and `btn_search`, and
        the author kept them in one place for exactly that reason. The catalog menu is
        relabelled by position like the item menu.

        What it deliberately does **not** do is refresh the subcategory chooser - see the
        comment below, and block 11 in `_update_ui_language`, which ends in it.
        """
        # 5. Catalog Tab
        self.cat_scope_lbl.configure(text=t["lbl_category"])
        self.cat_subscope_lbl.configure(text=t["lbl_subcategory"])
        # Nicht hier auffrischen: Punkt 11 weiter unten ruft `_refresh_catalog_filters`, und
        # das endet selbst mit `_refresh_subcategory_filter`. Zwischen den beiden Stellen
        # zeichnet nichts, der Waehler wurde also nur zweimal fuer denselben Wechsel gebaut.
        self.cat_search_lbl.configure(text=t["lbl_search"])
        self.cat_search_btn.configure(text=t["btn_search"])
        self._relabel_only_new()
        self.quest_search_lbl.configure(text=t["lbl_search"])
        self.quest_search_btn.configure(text=t["btn_search"])
        self.quests_guide_btn.configure(text=t["quests_guide_btn"])
        self.craft_search_lbl.configure(text=t["lbl_search"])
        self.craft_search_btn.configure(text=t["btn_search"])
        self.catalog_menu.entryconfigure(0, label=t["ctx_add_to_inv"])
        self.catalog_menu.entryconfigure(1, label=t["ctx_spawn_preset"])
        self.catalog_menu.entryconfigure(2, label=t["ctx_offer_at_trader"])
        self.catalog_menu.entryconfigure(3, label=t["ctx_info"])

    def _relabel_quests_tab(self, t: dict[str, str]) -> None:
        """Block 5b: five headings **and** a full rebuild of the rows.

        Kept as its own block because of that last line: the group and status names sit
        inside the rows, so this is one of the three places where switching language is
        not relabelling but redrawing. Dropping `_refresh_quests_tree` leaves the tab
        rendering the previous language.
        """
        # 5b. Quests Tab. The group and status names sit inside the tree rows, so
        # relabelling the widgets is not enough - the rows have to be rebuilt.
        self.quests_tree.heading("#0", text=t["tab_quests"])
        self.quests_tree.heading("status", text=t["col_quest_status"])
        self.quests_tree.heading("flags", text=t["col_quest_flags"])
        self.quests_tree.heading("sender", text=t["col_quest_sender"])
        self.quests_tree.heading("reward", text=t["col_quest_reward"])
        self._refresh_quests_tree()

    def _relabel_crafting_tab(self, t: dict[str, str]) -> None:
        """Block 5c: four headings and the same rebuild, for the same reason.

        Separate from the Quests block although the shape is identical - the two trees are
        rebuilt by different methods over different data, and a shared one would have to
        take both as arguments to say nothing more than these two lines do.
        """
        # 5c. Crafting Tab. Same rule as the Quests tab: the module and level names live in
        # the rows, so relabelling the headings alone leaves them in the old language.
        self.crafting_tree.heading("#0", text=t["craft_col_recipe"])
        self.crafting_tree.heading("needs", text=t["craft_col_needs"])
        self.crafting_tree.heading("time", text=t["craft_col_time"])
        self.crafting_tree.heading("state", text=t["craft_col_state"])
        self._refresh_crafting_tree()

    def _relabel_catalog_columns(self, t: dict[str, str]) -> None:
        """The catalog tree's eight column headings.

        The one block the author left unnumbered, and it sits **after** 5b and 5c rather
        than with block 5 - which is why it is a method of its own instead of being folded
        into `_relabel_catalog_tab`: the call order is the contract here, so the seam stays
        where it was.
        """
        # Catalog Table Headings
        self.catalog_tree.heading("name", text=t["col_cat_name"])
        self.catalog_tree.heading("template_id", text=t["col_cat_template_id"])
        self.catalog_tree.heading("category", text=t["col_cat_category"])
        self.catalog_tree.heading("subcategory", text=t["col_cat_subcategory"])
        self.catalog_tree.heading("size", text=t["col_cat_size"])
        self.catalog_tree.heading("stack", text=t["col_cat_stack"])
        self.catalog_tree.heading("price", text=t["col_cat_price"])
        self.catalog_tree.heading("mass", text=t["col_cat_mass"])

    def _relabel_hackerman_tab(self, t: dict[str, str]) -> None:
        """Block 6: the whole Hackerman tab - warning, profile, cheats, and the three
        panes of its subnotebook with their controls.

        It is one method because it is one tab and the author numbered it as one block.
        The subnotebook is the reason not to cut it further: its pages are addressed by
        index (`right_nb.tab(0..2)`), the counters page is relabelled before the two next
        to it, and its list is **rebuilt** rather than relabelled - the third of the three
        rebuild sites, for the same reason as Quests and Crafting.
        """
        # 6. Hackerman Tab Warning Frame
        self.warning_title.configure(text=t["lbl_warn_title"])
        self.warning_desc.configure(text=t["lbl_warn_desc"])

        # Profile Frame
        self.profile_lf.configure(text=t["lf_profile"])
        self.nickname_lbl.configure(text=t["lbl_nickname"])
        self.level_lbl.configure(text=t["lbl_level"])
        self.xp_lbl.configure(text=t["lbl_xp"])

        # Cheats Frame
        self.cheats_lf.configure(text=t["lf_cheats"])
        self.cheat_repair_all_btn.configure(text=t["btn_cheat_repair"])
        self.cheat_mint_all_btn.configure(text=t["btn_cheat_mint"])
        self.cheat_fill_stacks_btn.configure(text=t["btn_cheat_stacks"])
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

    def _relabel_help_and_options(self, t: dict[str, str]) -> None:
        """Block 7: the Help text, plus the four controls that were left under its heading.

        The block's comment names only the first line. The four below it live elsewhere -
        the retention label and the Restore button in the status bar, the category-colour
        checkbox on the inventory toolbar and its twin on the catalog toolbar - and are
        kept here rather than moved, because the block boundary is what this refactoring
        preserves; the call order is the contract, the comment is not.

        The Help text is rebuilt, not relabelled: it is a whole document per language.
        """
        # 7. Help Tab - Re-populate the Help text box
        self._populate_help_text()

        self.backup_keep_label.configure(text=t["backups_keep_label"])
        self.restore_button.configure(text=t["btn_restore_backup"])
        self.category_colors_cb.configure(text=t["cb_category_colors"])
        if hasattr(self, "cat_category_colors_cb"):
            self.cat_category_colors_cb.configure(text=t["cb_category_colors"])

    def _relabel_json_tab(self, t: dict[str, str]) -> None:
        """Block 8: the Raw JSON toolbar, all of it behind one `hasattr` guard.

        Its own method because it is the only block that may have nothing to do: the tab
        is built lazily, so every widget here can be absent. Two more conditions inside
        say the same thing in smaller: the Copy button keeps its "copied" text while its
        timer runs, and the "no matches" label is only re-stated while a query with no
        hits is still standing.
        """
        # 8. Raw JSON Tab controls
        if hasattr(self, "json_search_lbl"):
            self.json_search_lbl.configure(text=t["lbl_search"])
            self.json_find_prev_btn.configure(text=t["btn_find_prev"])
            self.json_find_next_btn.configure(text=t["btn_find_next"])
            self.json_wrap_cb.configure(text=t["chk_json_wrap"])
            if getattr(self, "_copy_timer_id", None) is None:
                self.json_copy_btn.configure(text=t["btn_copy_json"])
            self._update_json_status_lbl()
            if getattr(self, "_last_json_query", "") and not self._json_matches:
                self.json_match_lbl.configure(text=t["lbl_no_matches"], foreground="#e06c75")

    def _relabel_language_button(self) -> None:
        """Block 13: the flag and the two-letter code on the language selector.

        The only block that takes no `t`: it names the language rather than speaking it,
        so the codes are the same in all three and stay a literal here instead of three
        entries in the translation tables. Guarded because the flags are loaded from files
        that may be missing.
        """
        # 13. Update Language Selector dropdown
        lang_names = {"en": "US", "de": "DE", "ru": "RU"}
        if hasattr(self, "lang_btn") and hasattr(self, "flags"):
            flag_img = self.flags.get(self.current_lang)
            self.lang_btn.configure(
                image=flag_img,
                text=f" {lang_names.get(self.current_lang, 'US')}",
                compound="left",
            )

    def _build_raw_json_tab(self, parent: ttk.Frame) -> None:
        self._json_dirty = True
        self._json_matches: list[tuple[str, str]] = []
        self._json_match_idx = -1
        self._last_json_query = ""
        self._copy_timer_id = None
        self._json_search_timer_id = None

        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", padx=4, pady=4)

        self.json_search_lbl = ttk.Label(toolbar)
        self.json_search_lbl.pack(side="left", padx=(0, 6))

        self.json_search_var = tk.StringVar()
        self.json_search_entry = ttk.Entry(toolbar, textvariable=self.json_search_var, width=30)
        self.json_search_entry.pack(side="left", padx=(0, 6))
        self.json_search_entry.bind("<Return>", lambda _e: self._json_find_next())
        self.json_search_entry.bind("<Shift-Return>", lambda _e: self._json_find_prev())

        self.json_find_prev_btn = ttk.Button(toolbar, command=self._json_find_prev)
        self.json_find_prev_btn.pack(side="left", padx=(0, 4))

        self.json_find_next_btn = ttk.Button(toolbar, command=self._json_find_next)
        self.json_find_next_btn.pack(side="left", padx=(0, 10))

        self.json_match_lbl = ttk.Label(toolbar, text="", foreground="#808080")
        self.json_match_lbl.pack(side="left", padx=(0, 12))

        self.json_wrap_var = tk.BooleanVar(value=False)
        self.json_wrap_cb = ttk.Checkbutton(
            toolbar,
            variable=self.json_wrap_var,
            command=self._on_json_wrap_toggled,
        )
        self.json_wrap_cb.pack(side="left", padx=(0, 12))

        # Right-side controls
        self.json_copy_btn = ttk.Button(toolbar, command=self._copy_raw_json)
        self.json_copy_btn.pack(side="right", padx=(6, 0))

        self.json_status_lbl = ttk.Label(toolbar, text="", foreground="#808080")
        self.json_status_lbl.pack(side="right", padx=(10, 6))

        # Text area with scrollbars
        text_frame = ttk.Frame(parent)
        text_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        v_scroll = ttk.Scrollbar(text_frame, orient="vertical")
        v_scroll.pack(side="right", fill="y")

        self.json_h_scroll = ttk.Scrollbar(text_frame, orient="horizontal")
        self.json_h_scroll.pack(side="bottom", fill="x")

        font_family = "Consolas" if sys.platform == "win32" else "Courier"
        self.json_text = tk.Text(
            text_frame,
            wrap="none",
            bg=COLOR_BG,
            fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT,
            selectbackground="#264f78",
            selectforeground=COLOR_WHITE,
            font=(font_family, 10),
            padx=8,
            pady=8,
            bd=0,
            highlightthickness=0,
            xscrollcommand=self.json_h_scroll.set,
            yscrollcommand=v_scroll.set,
            state="disabled",
        )
        self.json_text.pack(side="left", fill="both", expand=True)
        v_scroll.configure(command=self.json_text.yview)
        self.json_h_scroll.configure(command=self.json_text.xview)

        self.json_text.tag_configure("search_hit", background="#3e4451", foreground=COLOR_WHITE)
        self.json_text.tag_configure("search_active", background="#528bff", foreground=COLOR_WHITE)
        self.json_text.bind("<Control-a>", self._on_json_select_all)
        self.json_text.bind("<Control-A>", self._on_json_select_all)

        self._update_json_status_lbl()

    def _on_json_select_all(self, _event: tk.Event | None = None) -> str:
        self.json_text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _update_json_status_lbl(self) -> None:
        if not hasattr(self, "json_status_lbl"):
            return
        t = TRANSLATIONS[self.current_lang]
        if hasattr(self, "json_text") and not getattr(self, "_json_dirty", True):
            content = self.json_text.get("1.0", "end-1c")
            size_bytes = len(content.encode("utf-8"))
        else:
            try:
                size_bytes = len(json.dumps(self.manager.data, indent=2, ensure_ascii=False).encode("utf-8"))
            except Exception:
                size_bytes = 0
        size_kb = size_bytes / 1024.0
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024.0:.2f} MB"
        if self.has_pending_changes:
            self.json_status_lbl.configure(
                text=f"{t['lbl_json_staged']}  |  {t['lbl_json_size'].format(size=size_str)}",
                foreground="#e5c07b",
            )
        else:
            self.json_status_lbl.configure(
                text=f"{t['lbl_json_saved']}  |  {t['lbl_json_size'].format(size=size_str)}",
                foreground="#98c379",
            )

    def _on_json_wrap_toggled(self) -> None:
        if self.json_wrap_var.get():
            self.json_text.configure(wrap="word")
            self.json_h_scroll.pack_forget()
        else:
            self.json_text.configure(wrap="none")
            self.json_h_scroll.pack(side="bottom", fill="x", before=self.json_text)

    def _copy_raw_json(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        if getattr(self, "_copy_timer_id", None) is not None:
            try:
                self.root.after_cancel(self._copy_timer_id)
            except tk.TclError:
                pass
            self._copy_timer_id = None
        try:
            if hasattr(self, "json_text") and not getattr(self, "_json_dirty", True):
                content = self.json_text.get("1.0", "end-1c")
            else:
                content = json.dumps(self.manager.data, indent=2, ensure_ascii=False)
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.root.update()
            self.json_copy_btn.configure(text=t["msg_json_copied"])

            def _reset_btn() -> None:
                self._copy_timer_id = None
                t_curr = TRANSLATIONS[self.current_lang]
                self.json_copy_btn.configure(text=t_curr["btn_copy_json"])

            self._copy_timer_id = self.root.after(1500, _reset_btn)
            self._set_status(t["msg_json_copied"])
        except Exception as exc:
            self._set_status(f"Copy failed: {exc}")

    def _invalidate_json_tab(self) -> None:
        """The Raw JSON view no longer matches `manager.data` - say so, and repaint only if
        it is on screen.

        Called from everything that changes the data underneath it. **The cheap part is the
        point**: rebuilding the dump means serialising the whole save, measured at 46 ms on
        a real one, and an edit must not pay that for a tab nobody is looking at. So the
        view is marked stale here and rebuilt in `_on_tab_changed` when it is next opened.
        The one case that cannot wait is the tab already being the visible one, because then
        "stale" is what the user is reading.

        This lives in one place because it used to live in three - `_mark_pending_changes`,
        `_clear_pending_changes` and `_repopulate_after_reload` carried the same five lines,
        and the copies had already started to drift apart.
        """
        self._json_dirty = True
        if not getattr(self, "notebook", None) or not self.notebook.select():
            return
        if self.notebook.nametowidget(self.notebook.select()) is getattr(self, "tab_raw_json", None):
            self._refresh_json_tab()

    def _refresh_json_tab(self) -> None:
        try:
            content = json.dumps(self.manager.data, indent=2, ensure_ascii=False)
        except Exception as exc:
            content = f"// Error serializing save data: {exc}"

        self.json_text.configure(state="normal")
        self.json_text.delete("1.0", "end")
        self.json_text.insert("1.0", content)
        self.json_text.configure(state="disabled")

        self._json_dirty = False
        self._update_json_status_lbl()

        # The old hits describe a text that has just been replaced, so they are dropped
        # rather than kept: an index like "4711.8" still resolves after the rebuild and
        # would quietly jump to the wrong line. Dropping them also makes "Next" re-search
        # immediately if it is pressed before the deferred pass below runs.
        self._json_matches.clear()
        self._json_match_idx = -1
        self._schedule_json_search()

    def _schedule_json_search(self, delay_ms: int = 250) -> None:
        """Re-tag the standing search, but at most once per burst of edits.

        `_refresh_json_tab` runs after every change while the tab is open, and tagging every
        hit in a one-megabyte dump is not free: measured against a real save with `e` left in
        the search box, 33,943 hits cost **467 ms**, paid on every single click. So the pass
        is coalesced - each edit cancels the pending one and starts a new one, and ten quick
        edits cost one search instead of ten.

        250 ms because it only has to outlast a burst, not a keystroke; nothing in this app
        searches while typing. A search the user asks for directly - Return, Next, Prev -
        does not come through here and still happens at once.
        """
        if self._json_search_timer_id is not None:
            try:
                self.root.after_cancel(self._json_search_timer_id)
            except tk.TclError:
                pass
            self._json_search_timer_id = None
        if not self.json_search_var.get().strip():
            return

        def _run() -> None:
            self._json_search_timer_id = None
            self._json_search_all()

        self._json_search_timer_id = self.root.after(delay_ms, _run)

    def _json_search_all(self) -> None:
        # Whatever the reason for searching now, a pass waiting behind a timer would only
        # repeat this work a moment later - so it is dropped rather than left to fire.
        if getattr(self, "_json_search_timer_id", None) is not None:
            try:
                self.root.after_cancel(self._json_search_timer_id)
            except tk.TclError:
                pass
            self._json_search_timer_id = None

        query = self.json_search_var.get()
        self.json_text.tag_remove("search_hit", "1.0", "end")
        self.json_text.tag_remove("search_active", "1.0", "end")
        self._json_matches.clear()
        self._json_match_idx = -1
        if not query:
            self.json_match_lbl.configure(text="")
            return

        start = "1.0"
        while True:
            pos = self.json_text.search(query, start, stopindex="end", nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self._json_matches.append((pos, end))
            self.json_text.tag_add("search_hit", pos, end)
            start = end

        total = len(self._json_matches)
        t = TRANSLATIONS[self.current_lang]
        if total == 0:
            self.json_match_lbl.configure(text=t["lbl_no_matches"], foreground="#e06c75")
        else:
            self._json_match_idx = 0
            self._json_highlight_current()

    def _json_highlight_current(self) -> None:
        self.json_text.tag_remove("search_active", "1.0", "end")
        if not self._json_matches or self._json_match_idx < 0:
            return
        pos, end = self._json_matches[self._json_match_idx]
        self.json_text.tag_add("search_active", pos, end)
        self.json_text.see(pos)
        total = len(self._json_matches)
        curr = self._json_match_idx + 1
        self.json_match_lbl.configure(text=f"{curr} / {total}", foreground="#abb2bf")

    def _json_find_next(self) -> None:
        query = self.json_search_var.get()
        if query != getattr(self, "_last_json_query", ""):
            self._last_json_query = query
            self._json_search_all()
            return
        if not self._json_matches:
            return
        self._json_match_idx = (self._json_match_idx + 1) % len(self._json_matches)
        self._json_highlight_current()

    def _json_find_prev(self) -> None:
        query = self.json_search_var.get()
        if query != getattr(self, "_last_json_query", ""):
            self._last_json_query = query
            self._json_search_all()
            return
        if not self._json_matches:
            return
        self._json_match_idx = (self._json_match_idx - 1) % len(self._json_matches)
        self._json_highlight_current()


    def _build_help_tab(self, parent: ttk.Frame) -> None:
        # The scrollbar needs its own place next to the text, not inside it. Parented to the
        # Text widget it floats on top and swallows the last word of every line that reaches
        # the right edge - invisible until a paragraph was long enough to get there.
        wrap_frame = ttk.Frame(parent)
        wrap_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.help_text_area = tk.Text(
            wrap_frame,
            wrap="word",
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT,
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
        
        self.help_text_area.tag_configure("header", font=("TkDefaultFont", 11, "bold"), foreground=COLOR_ACCENT)
        self.help_text_area.tag_configure("highlight", font=("TkDefaultFont", 10, "bold"), foreground="#ff007f")
        self.help_text_area.tag_configure("bullet", font=("TkDefaultFont", 10))
        self.help_text_area.tag_configure("link", font=("TkDefaultFont", 10, "underline", "bold"), foreground=COLOR_ACCENT)
        self.help_text_area.tag_bind("link", "<Button-1>", lambda _: webbrowser.open("https://ko-fi.com/sirnr1"))
        self.help_text_area.tag_bind("link", "<Enter>", lambda _: self.help_text_area.configure(cursor="hand2"))
        self.help_text_area.tag_bind("link", "<Leave>", lambda _: self.help_text_area.configure(cursor=""))
        


        
        self._populate_help_text()

    def _build_char_tab(self, parent: ttk.Frame) -> None:
        """Builds Hackerman's Lab: a toolbar strip, then two columns side by side.

        What is left here is the only thing the blocks below have in common - the two
        panes. They share nothing else: each block builds into one of them and hangs its
        widgets on `self`, so the panes are passed in as arguments rather than kept as
        attributes nobody would read again. The three subnotebook pages read
        `self.tab_skills` / `_traders` / `_counters`, which the pane before them creates,
        so their order is the one they had.
        """
        self._build_char_toolbar(parent)

        # Create left pane for warning, profile, and cheats
        left_pane = ttk.Frame(parent)
        left_pane.pack(side="left", fill="both", expand=False, padx=10, pady=10)

        # Create right pane for skills/traders notebook
        right_pane = ttk.Frame(parent)
        right_pane.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self._build_char_warning_banner(left_pane)
        self._build_char_profile_frame(left_pane)
        self._build_char_cheats_frame(left_pane)
        self._build_char_subnotebook(right_pane)
        self._build_skills_pane()
        self._build_traders_pane()
        self._build_counters_pane()

    def _build_char_toolbar(self, parent: ttk.Frame) -> None:
        """The tab's own Apply/Discard pair, above both columns.

        Its own method because it is the one thing on this tab that is not in a column,
        and because the pack order is load-bearing: it takes the top strip only as long as
        it is packed before the panes, which is why it is the first call in the builder.
        The pair is a separate widget instance from every other tab's - a Tk widget has one
        parent - and is registered in `apply_buttons`/`discard_buttons` elsewhere.
        """
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

    def _build_char_warning_banner(self, left_pane: ttk.Frame) -> None:
        """Block 1: the red banner that says this tab can brick a save.

        Stands alone because it is the only part of the window built from raw `tk` widgets
        rather than `ttk` - a themed label cannot carry its own background - so the three
        colours and the wrap width live here and nowhere else.
        """
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
            wraplength=self._scale_px(WARNING_WRAPLENGTH),
            padx=10,
            pady=5
        )
        self.warning_title.pack(fill="x")

        self.warning_desc = tk.Label(
            self.warning_frame,
            text="",
            font=("TkDefaultFont", 9),
            fg=COLOR_WHITE,
            bg="#4a1515",
            justify="left",
            anchor="w",
            wraplength=self._scale_px(WARNING_WRAPLENGTH),
            padx=10,
            pady=5
        )
        self.warning_desc.pack(fill="x")

    def _build_char_profile_frame(self, left_pane: ttk.Frame) -> None:
        """Block 2: nickname, level, XP and unspent skill points.

        One method because it is one grid - four rows of label, field and a hint in the
        third column - and because all four fields share one trace, `_on_char_profile_changed`.
        A field added here without that trace stages nothing, which is the mistake this
        block being one piece makes visible.
        """
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

    def _build_char_cheats_frame(self, left_pane: ttk.Frame) -> None:
        """Block 3: the five cheat buttons, in two columns.

        Kept together because the layout is a measurement, not a preference: five stacked
        buttons run past the bottom of the pane at the window's minimum size in German, so
        the two `uniform` columns and the last button's `columnspan` belong to the same
        decision as the buttons themselves.
        """
        # 3. Cheats Frame
        self.cheats_lf = ttk.LabelFrame(left_pane, padding=10)
        self.cheats_lf.pack(fill="x")

        # Two columns, because five stacked buttons run past the bottom of the pane at the
        # window's 1100x680 minimum - measured in German, which is the long case for labels.
        self.cheats_lf.columnconfigure(0, weight=1, uniform="cheat")
        self.cheats_lf.columnconfigure(1, weight=1, uniform="cheat")

        self.cheat_repair_all_btn = ttk.Button(self.cheats_lf, command=self._cheat_repair_all)
        self.cheat_repair_all_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=4)

        self.cheat_mint_all_btn = ttk.Button(self.cheats_lf, command=self._cheat_mint_all)
        self.cheat_mint_all_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=4)

        self.cheat_fill_stacks_btn = ttk.Button(self.cheats_lf, command=self._cheat_fill_stacks)
        self.cheat_fill_stacks_btn.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=4)

        self.cheat_max_skills_btn = ttk.Button(self.cheats_lf, command=self._cheat_max_skills)
        self.cheat_max_skills_btn.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=4)

        self.cheat_fill_trader_btn = ttk.Button(self.cheats_lf, command=self._cheat_fill_trader_balances)
        self.cheat_fill_trader_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)

    def _build_char_subnotebook(self, right_pane: ttk.Frame) -> None:
        """Block 4: the right column's notebook and its three empty pages.

        Separate from the three panes that fill them because it is what fixes their
        **order**: `_update_ui_language` addresses these pages by index (`right_nb.tab(0)`
        to `(2)`), so adding a page anywhere but at the end moves a caption onto the wrong
        one. The pages are created empty and filled by the three builders after it.
        """
        # 4. Right Pane Subnotebook (Skills & Traders)
        self.right_nb = ttk.Notebook(right_pane)
        self.right_nb.pack(fill="both", expand=True)

        self.tab_skills = ttk.Frame(self.right_nb)
        self.tab_traders = ttk.Frame(self.right_nb)
        self.tab_counters = ttk.Frame(self.right_nb)

        self.right_nb.add(self.tab_skills, text="")
        self.right_nb.add(self.tab_traders, text="")
        self.right_nb.add(self.tab_counters, text="")

    def _build_skills_pane(self) -> None:
        """The Skills page: a scrolled list over a row of level controls.

        Its own method because it is a page of the subnotebook, built into
        `self.tab_skills` - it needs no argument, since the pane before it stored the page
        it fills. The three controls at the bottom are one measured set: same width, same
        rendered height, and the spinbox arrows as the only stepper.
        """
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

        self.skills_tree.column("id", width=self._scale_px(60), anchor="center")
        self.skills_tree.column("name", width=self._scale_px(200), anchor="w")
        self.skills_tree.column("level", width=self._scale_px(80), anchor="center")

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
                                        style="Step.TButton",
                                        command=self._set_selected_skill_level)
        self.set_skill_btn.pack(side="left")

    def _build_traders_pane(self) -> None:
        """The Traders page: the same shape as the skills page, plus a balance field.

        Deliberately not shared with `_build_skills_pane` although the top halves look
        alike: the columns differ, three of the five are hidden by `displaycolumns`, and
        the level spinbox reads its ceiling from the extraction report. A common builder
        would take every one of those as an argument and read worse than the two do.
        """
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

        self.traders_tree.column("id", width=self._scale_px(80), anchor="w")
        self.traders_tree.column("template_id", width=self._scale_px(80), anchor="w")
        self.traders_tree.column("name", width=self._scale_px(180), anchor="w")
        self.traders_tree.column("trader_level", width=self._scale_px(100), anchor="center")
        self.traders_tree.column("balance", width=self._scale_px(150), anchor="e")

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

    def _build_counters_pane(self) -> None:
        """The Counters page: the account's own tallies, read-only.

        The shortest of the three and the only one with no control row at all, which is
        the reason it is a block of its own rather than a variant of the other two -
        nothing here writes, so there is nothing to stage and no Apply to reach.
        """
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

        self.counters_tree.column("group", width=self._scale_px(130), anchor="w")
        self.counters_tree.column("stat", width=self._scale_px(200), anchor="w")
        self.counters_tree.column("value", width=self._scale_px(120), anchor="e")
        self.counters_tree.column("updated", width=self._scale_px(170), anchor="w")

        self.counters_hint = ttk.Label(self.tab_counters, style="Hint.TLabel",
                                       wraplength=self._scale_px(520), justify="left")
        self.counters_hint.pack(anchor="w", padx=5, pady=(0, 5))

    # --- Quests ------------------------------------------------------------------------

    def _build_quests_tab(self, parent: ttk.Frame) -> None:
        """A read-only view of every quest the game ships, against what this save has met.

        Which quests exist cannot be answered from a save - it only ever names the ones it
        has seen. The list therefore comes from the mapping report, and the save only
        decides which of three buckets a quest lands in.
        """
        quests_bar = ttk.Frame(parent)
        quests_bar.pack(fill="x", padx=10, pady=(10, 4))
        self.quests_count_lbl = ttk.Label(quests_bar, style="Status.TLabel")
        self.quests_count_lbl.pack(side="left")

        # A link, not an import. The guide is another player's work on Steam: 225 screenshots
        # of where things are, plus notes on the keys. Two things ruled out bringing any of it
        # into the tab - it carries no reuse licence, and it has **no section anchors**, so
        # there is nothing to deep-link to even for the 21 quests whose names match ours. So
        # the honest form is a door, clearly marked as leading outside.
        self.quests_guide_btn = ttk.Button(
            quests_bar, command=lambda: webbrowser.open(QUEST_GUIDE_URL))
        self.quests_guide_btn.pack(side="left", padx=(12, 0))

        # Same shape as the catalog's and the inventory's: type, press Return, the tree keeps
        # what matches. 302 rows across nine groups is more than anyone scrolls.
        self.quest_search_btn = ttk.Button(quests_bar, command=self._refresh_quests_tree)
        self.quest_search_btn.pack(side="right")
        self.quest_search_var = tk.StringVar()
        self.quest_search_entry = ttk.Entry(
            quests_bar, textvariable=self.quest_search_var, width=26)
        self.quest_search_entry.pack(side="right", padx=(6, 6))
        self.quest_search_entry.bind("<Return>", lambda _event: self._refresh_quests_tree())
        self.quest_search_lbl = ttk.Label(quests_bar)
        self.quest_search_lbl.pack(side="right")

        # A paned window so the detail text can be dragged larger; long quest briefings run
        # to several hundred characters and a fixed split would either waste space or clip.
        panes = ttk.PanedWindow(parent, orient="vertical")
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        tree_frame = ttk.Frame(panes)
        panes.add(tree_frame, weight=3)

        quests_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        quests_scroll.pack(side="right", fill="y")

        self.quests_tree = ttk.Treeview(
            tree_frame,
            columns=("status", "flags", "sender", "reward"),
            show="tree headings",
            selectmode="browse",
            yscrollcommand=quests_scroll.set,
        )
        quests_scroll.configure(command=self.quests_tree.yview)
        self.quests_tree.pack(side="left", fill="both", expand=True)

        self.quests_tree.column("#0", width=self._scale_px(430), anchor="w", stretch=True)
        self.quests_tree.column("status", width=self._scale_px(110), anchor="w")
        self.quests_tree.column("flags", width=self._scale_px(130), anchor="w")
        self.quests_tree.column("sender", width=self._scale_px(150), anchor="w")
        self.quests_tree.column("reward", width=self._scale_px(190), anchor="w")
        self.quests_tree.bind("<<TreeviewSelect>>", self._on_quest_selected)

        detail_frame = ttk.Frame(panes)
        panes.add(detail_frame, weight=1)

        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical")
        detail_scroll.pack(side="right", fill="y")
        self.quest_detail = tk.Text(
            detail_frame,
            height=7,
            wrap="word",
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            relief="flat",
            padx=8,
            pady=6,
            yscrollcommand=detail_scroll.set,
        )
        detail_scroll.configure(command=self.quest_detail.yview)
        self.quest_detail.pack(side="left", fill="both", expand=True)
        self.quest_detail.tag_configure("field", foreground=COLOR_ACCENT)
        self.quest_detail.tag_configure("dim", foreground="#9a9a9a")
        self.quest_detail.configure(state="disabled")

        self.quests_hint = ttk.Label(parent, style="Hint.TLabel",
                                     wraplength=900, justify="left")
        self.quests_hint.pack(anchor="w", padx=10, pady=(0, 6))

    def _quest_status_of(self, quest_id: str) -> str:
        """One of "active", "done", "unseen" for a quest id."""
        if quest_id in self._save_quest_ids()[0]:
            return "active"
        if quest_id in self._save_quest_ids()[1]:
            return "done"
        return "unseen"

    def _save_quest_ids(self) -> tuple[set[str], set[str]]:
        """The active and completed quest ids in the save, lowercased.

        Two different key names for the same thing: an active quest carries `DataId`, a
        completed one `QuestDataId`. Both are the quest template's id.
        """
        quests = self.manager.data.get("AccountQuests")
        if not isinstance(quests, dict):
            return set(), set()

        def ids(rows: object, key: str) -> set[str]:
            if not isinstance(rows, list):
                return set()
            return {
                str(row.get(key)).strip().lower()
                for row in rows
                if isinstance(row, dict) and isinstance(row.get(key), str)
            }

        return (
            ids(quests.get("ActiveQuests"), "DataId"),
            ids(quests.get("CompletedQuests"), "QuestDataId"),
        )

    def _quest_label(self, meta: dict) -> str:
        """The quest's name, or its internal one when the game ships no readable name.

        88 of 302 have no resolvable name - mostly `OTHER/ANALYTICS/*` telemetry quests
        that were never meant to be shown. The alias is what the developers call them.
        """
        name = meta.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        alias = str(meta.get("alias") or "").strip()
        return alias.rsplit("/", 1)[-1] if alias else "?"

    def _quest_reward_text(self, meta: dict) -> str:
        t = TRANSLATIONS[self.current_lang]
        rewards = meta.get("rewards") or {}
        parts: list[str] = []
        xp = rewards.get("xp")
        if isinstance(xp, int) and xp > 0:
            parts.append(t["quest_reward_xp"].format(xp=f"{xp:,}".replace(",", " ")))
        items = rewards.get("items") or []
        if items:
            first = items[0]
            name = self._template_name_for_template_id(first.get("template_id")) or "?"
            count = first.get("count") or 1
            label = f"{name} x{count}" if count and count > 1 else name
            if len(items) > 1:
                label = f"{label} +{len(items) - 1}"
            parts.append(label)
        return ", ".join(parts)

    def _refresh_quests_tree(self) -> None:
        """Group -> status -> quest, with the never-seen branches open.

        The counts live in the node labels, so the answer the tab exists for is readable
        without expanding anything.
        """
        if not hasattr(self, "quests_tree"):
            return
        for row in self.quests_tree.get_children(""):
            self.quests_tree.delete(row)
        self._quest_row_ids = {}

        t = TRANSLATIONS[self.current_lang]
        meta_all = getattr(self, "quests_meta", {}) or {}
        active_ids, done_ids = self._save_quest_ids()

        if not meta_all:
            self.quests_hint.configure(text=t["quests_empty"])
            self.quests_count_lbl.configure(text="")
            self._set_quest_detail(None)
            return

        # Sorted by how many quests a group holds, so MISSIONS and OTHER come before the
        # one-off folders instead of alphabetically burying them.
        by_group: dict[str, list[tuple[str, dict]]] = {}
        for quest_id, meta in meta_all.items():
            group = str(meta.get("group") or "").strip() or t["quest_group_none"]
            by_group.setdefault(group, []).append((quest_id, meta))

        status_order = [
            ("unseen", t["quest_status_unseen"]),
            ("active", t["quest_status_active"]),
            ("done", t["quest_status_done"]),
        ]

        query = self.quest_search_var.get().strip().lower() if hasattr(
            self, "quest_search_var") else ""
        matched = 0

        for group, rows in sorted(by_group.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            if query:
                rows = [row for row in rows if self._quest_matches(row[0], row[1], query)]
                if not rows:
                    continue
            matched += len(rows)
            group_node = self.quests_tree.insert(
                "", "end", text=f"{group}  ({len(rows)})", open=bool(query))

            buckets: dict[str, list[tuple[str, dict]]] = {"unseen": [], "active": [], "done": []}
            for quest_id, meta in rows:
                if quest_id in active_ids:
                    buckets["active"].append((quest_id, meta))
                elif quest_id in done_ids:
                    buckets["done"].append((quest_id, meta))
                else:
                    buckets["unseen"].append((quest_id, meta))

            for status_key, status_label in status_order:
                bucket = buckets[status_key]
                if not bucket:
                    continue
                status_node = self.quests_tree.insert(
                    group_node, "end",
                    text=f"{status_label}  ({len(bucket)})",
                    open=bool(query) or status_key == "unseen",
                )
                for quest_id, meta in sorted(bucket, key=lambda kv: self._quest_label(kv[1]).lower()):
                    flags = []
                    if meta.get("hidden"):
                        flags.append(t["quest_flag_hidden"])
                    if meta.get("shadow"):
                        flags.append(t["quest_flag_shadow"])
                    sender = self._npc_name_for_npc_bio_id(meta.get("sender_npc_id")) or ""
                    row_id = self.quests_tree.insert(
                        status_node, "end",
                        text=self._quest_label(meta),
                        values=(status_label, ", ".join(flags), sender,
                                self._quest_reward_text(meta)),
                    )
                    self._quest_row_ids[row_id] = quest_id

        seen = len(active_ids | done_ids)
        self.quests_count_lbl.configure(text=(
            t["quest_counts_filtered"].format(count=matched, total=len(meta_all), query=
                                              self.quest_search_var.get().strip())
            if query else
            t["quest_counts"].format(total=len(meta_all), seen=seen,
                                     unseen=len(meta_all) - seen)))
        self.quests_hint.configure(text=t["quests_hint"])
        self._set_quest_detail(None)

    def _quest_matches(self, quest_id: str, meta: dict, query: str) -> bool:
        """Name, alias, group, briefing, sender and the quest's own id.

        The alias is in there because that is what the 88 quests with no readable name are
        listed under, and the briefing because "the one about the toymaker" is how anyone
        actually remembers a quest.
        """
        sender = self._npc_name_for_npc_bio_id(meta.get("sender_npc_id")) or ""
        haystack = " ".join(str(part) for part in (
            self._quest_label(meta), meta.get("name") or "", meta.get("alias") or "",
            meta.get("group") or "", meta.get("description") or "", sender, quest_id,
        )).lower()
        return query in haystack

    def _on_quest_selected(self, _event=None) -> None:
        selection = self.quests_tree.selection()
        quest_id = getattr(self, "_quest_row_ids", {}).get(selection[0]) if selection else None
        self._set_quest_detail(quest_id)

    def _set_quest_detail(self, quest_id: str | None) -> None:
        t = TRANSLATIONS[self.current_lang]
        self.quest_detail.configure(state="normal")
        self.quest_detail.delete("1.0", "end")

        meta = (getattr(self, "quests_meta", {}) or {}).get(quest_id or "")
        if not meta:
            self.quest_detail.insert("end", t["quest_pick"], "dim")
            self.quest_detail.configure(state="disabled")
            return

        def field(label: str, value: str) -> None:
            self.quest_detail.insert("end", f"{label}: ", "field")
            self.quest_detail.insert("end", f"{value}\n")

        self.quest_detail.insert("end", f"{self._quest_label(meta)}\n\n")

        description = meta.get("description")
        if isinstance(description, str) and description.strip():
            field(t["quest_detail_task"], description.strip())

        field(t["quest_detail_alias"], str(meta.get("alias") or "?"))
        field(t["quest_detail_status"], {
            "active": t["quest_status_active"],
            "done": t["quest_status_done"],
            "unseen": t["quest_status_unseen"],
        }[self._quest_status_of(quest_id or "")])

        required = meta.get("requires_quest_ids") or []
        if required:
            names = [
                self._quest_label((getattr(self, "quests_meta", {}) or {}).get(rid, {"alias": rid}))
                for rid in required
            ]
            field(t["quest_detail_requires"], ", ".join(names))

        low, high = meta.get("min_account_level"), meta.get("max_account_level")
        # -1 is the game's "no limit" on both ends, so a range of -1 to -1 says nothing.
        if isinstance(low, int) and isinstance(high, int) and (low > 0 or high > 0):
            field(t["quest_detail_level"], t["quest_level_range"].format(
                min=low if low > 0 else 1, max=high if high > 0 else "-"))

        sender = self._npc_name_for_npc_bio_id(meta.get("sender_npc_id"))
        if sender:
            field(t["quest_detail_sender"], sender)

        rewards = self._quest_reward_text(meta)
        field(t["quest_detail_rewards"], rewards or t["quest_detail_none"])

        self.quest_detail.configure(state="disabled")

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
        top = self._max_xp_for_level(self.manager.get_experience().get("Level", 0))
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
            level = self.manager.get_experience().get("Level", 0)
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
        exp_dto = self.manager.get_experience(create=True)
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

        account_dto = self.manager.get_account(create=True)
        exp_dto = self.manager.get_experience(create=True)

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

        account_dto = self.manager.get_account()
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

        skills_list = self.manager.get_skills()
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

        counters = self.manager.get_counters()
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

        shops_list = self.manager.get_shops()
        for shop in shops_list:
            instance_id = shop.get("Id")
            template_id = shop.get("ShopTemplateId")
            trader_level = shop.get("AccountLevel", 1)

            balance_dict = shop.get("Balance", {})
            currency_key = CREDITS_TEMPLATE_ID
            balance = balance_dict.get(currency_key, 0)

            trader_name = self.traders_name_map.get(template_id, "Unknown Trader")

            self.traders_tree.insert(
                "",
                "end",
                values=(instance_id, template_id, trader_name, trader_level, balance)
            )

    def _on_skill_selected(self, _event=None) -> None:
        selected = self.skills_tree.selection()
        if not selected:
            return
        values = self.skills_tree.item(selected[0], "values")
        if values:
            # The level column reads "3 / 5" - only the level goes into the spinbox, and the
            # spinbox stops at that skill's own ceiling rather than a shared 10.
            self.skill_level_var.set(str(values[2]).split("/")[0].strip())
            self.skill_spin.configure(to=self._max_level_for_skill(int(values[0])))

    def _on_trader_selected(self, _event=None) -> None:
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

    def _write_skill_level(self, skill_id: int, new_level: int) -> None:
        """Stages the level, refills the readout and puts the selection back on the row."""
        t = TRANSLATIONS[self.current_lang]
        skills_list = self.manager.get_skills(create=True)
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
            new_balance = None

        shop = self.manager.get_shop(trader_id)
        if not shop:
            messagebox.showerror(t["title"], f"Trader {trader_id} not found in save data.")
            return

        currency_key = CREDITS_TEMPLATE_ID
        # Refused above the cap rather than clamped, like the level field above: the game
        # cuts the balance down to its template's ShopBalance on load (confirmed in-game
        # 2026-07-28 - wrote a million, read 500000 back), so a bigger number in the save
        # is a value the user never gets. The check needs the shop, hence after the lookup.
        max_balance = self._balance_for_shop(shop, currency_key)
        if new_balance is None or new_balance > max_balance:
            messagebox.showerror(
                t["title"], t["msg_trader_balance_range"].format(max_balance=max_balance))
            return

        shop["AccountLevel"] = new_level

        balance_dict = shop.setdefault("Balance", {})
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

        self._refresh_scope_keeping_open()

        messagebox.showinfo(
            t["msg_success_title"],
            t["msg_cheats_repair"].format(count=repaired_count),
            parent=self.root
        )
        self._mark_pending_changes(t["status_cheat_repaired"].format(count=repaired_count))

    def _cheat_mint_all(self) -> None:
        """Every item in the save the way the game hands out a new one.

        Asks first, because it rewrites a field on well over a thousand items - the repair
        cheat next to it only touches the few that carry condition data.
        """
        t = TRANSLATIONS[self.current_lang]
        all_items = self.manager.get_all_items_flat()
        if not messagebox.askyesno(
                t["title"], t["msg_mint_all_confirm"].format(count=len(all_items)),
                parent=self.root):
            return

        # One item at a time and without the subtree: the loop covers every item anyway.
        cleared = sum(
            len(self.manager.make_pristine(str(item.get("Id")), include_parts=False))
            for item in all_items
        )

        if not cleared:
            messagebox.showinfo(t["msg_success_title"], t["status_mint_nothing"],
                                parent=self.root)
            return

        self._refresh_scope_keeping_open()
        messagebox.showinfo(
            t["msg_success_title"],
            t["msg_cheats_mint"].format(count=cleared),
            parent=self.root,
        )
        self._mark_pending_changes(t["status_mint"].format(count=cleared))

    def _cheat_fill_stacks(self) -> None:
        """Every partial stack up to its own capacity. Nothing is created, only counted up.

        Measured on a real save: 135 stacks sit below capacity with 11,464 units of headroom
        between them, and none of that can be reached by duplicating - a copy needs a cell.
        """
        t = TRANSLATIONS[self.current_lang]
        filled = units = 0
        for item in self.manager.get_all_items_flat():
            inner = item_data(item)
            quantity = inner.get("StackableComponent_quantity")
            if not isinstance(quantity, int) or isinstance(quantity, bool):
                continue
            capacity = self._stack_capacity_for_template(item.get("TemplateId"))
            if not capacity or quantity >= capacity:
                continue
            inner["StackableComponent_quantity"] = capacity
            units += capacity - quantity
            filled += 1

        if not filled:
            messagebox.showinfo(t["msg_success_title"], t["msg_cheats_stacks_none"],
                                parent=self.root)
            return

        self._refresh_scope_keeping_open()
        messagebox.showinfo(t["msg_success_title"],
                            t["msg_cheats_stacks"].format(count=filled, units=units),
                            parent=self.root)
        self._mark_pending_changes(
            t["status_cheat_stacks"].format(count=filled, units=units))

    def _cheat_max_skills(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        skills_list = self.manager.get_skills(create=True)
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
        shops_list = self.manager.get_shops()
        trader_count = len(shops_list)

        currency_key = CREDITS_TEMPLATE_ID
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
        self._invalidate_json_tab()

    def _clear_pending_changes(self, status_text: str) -> None:
        self.has_pending_changes = False
        self._refresh_pending_buttons()
        self._set_status(status_text)
        self._invalidate_json_tab()

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
        """Fills every name and meta field from the first usable extraction report.

        What stays here is the part that cannot be moved out: which candidate wins, and
        the rule that makes that decision safe - a candidate contributes everything or
        nothing. Every `continue` above happens before the first write, so a report that
        turns out to be unusable leaves the defaults from `_reset_template_name_state`
        rather than half of itself. The blocks that read one section of the report each
        follow below.
        """
        self._reset_template_name_state()

        for path in self._mapping_candidates():
            if not path.exists():
                continue
            report = self._read_mapping_report(path)
            if report is None:
                continue

            mapping = report.get("mapping", [])
            if not isinstance(mapping, list):
                mapping = []
            catalog_rows = report.get("item_catalog")
            has_catalog = isinstance(catalog_rows, list) and bool(catalog_rows)
            # `mapping` used to be the implicit validity check before the loop committed
            # to a candidate. Newer reports no longer carry it - it duplicated
            # `item_catalog` name for name - so the check is explicit now: a report with
            # neither block is not a report, and the next candidate gets its turn instead
            # of this one silently yielding an empty name map.
            if not mapping and not has_catalog:
                continue

            self._apply_report_npc_names(report)
            self._apply_report_skills(report)
            self._apply_report_trader_meta(report)
            self._apply_report_quest_and_craft_meta(report)
            self._apply_report_presets(report)
            self._apply_report_item_catalog(report)
            # The one block that built a local instead of writing to `self`, so it hands
            # `loaded` back here - the manual overrides are layered on top afterwards,
            # which is what keeps them winning over the report.
            loaded = self._template_names_from_report(mapping, catalog_rows, has_catalog)

            for key, value in self.manual_alias_map.items():
                loaded[key] = value

            self.template_name_map = loaded
            self.template_map_source = str(path)
            game_path = report.get("game_path")
            if isinstance(game_path, str) and game_path.strip():
                self.last_game_path = game_path.strip()
            return

        # **Kein Kandidat war brauchbar.** Nur `template_name_map` wird hier gesetzt: es ist
        # das einzige Feld, das `_reset_template_name_state` nicht kennt. Alle anderen stehen
        # dort schon auf ihrer Vorgabe, und jedes `continue` der Schleife oben liegt **vor**
        # dem ersten Schreibzugriff - ein Kandidat schreibt also alles oder nichts. Fuenf
        # weitere Zuweisungen standen hier bis zum 11.09.2026 und konnten nie etwas tun.
        self.template_name_map = dict(self.manual_alias_map)

    def _reset_template_name_state(self) -> None:
        """The opening block of `_load_template_name_map`: every field a report can fill,
        back to its built-in default.

        It stands on its own because it is the state contract of the load - the full list
        of what a report reaches, in one place, so a new report section cannot be added
        without its default beside it. Two of these are merges rather than blanks:
        `skills_name_map` and `traders_name_map` start from the constants in this file, so
        a report that names only some of them leaves the rest readable.
        """
        self.manual_alias_map = self._load_manual_aliases()
        self.npc_name_map = {}
        self.game_item_catalog = []
        self.game_item_meta_by_template_id = {}
        self.skills_name_map = dict(SKILL_NAMES)
        self.skills_meta = {}
        self.shops_meta = {}
        self.max_account_level = TRADER_LEVEL_MAX_FALLBACK
        self.level_progress = {}
        self.quests_meta = {}
        self.craft_meta = {}
        self.crafting_meta = {}
        self.presets_meta = []
        self.traders_name_map = dict(TRADER_NAMES)

    def _read_mapping_report(self, path: Path) -> dict | None:
        """Parses one candidate report; `None` says "not this file, try the next".

        Its own method because that is the whole of it: the caller loops over candidates,
        and returning `None` means exactly what the `continue` it replaces meant. The
        broad `except` is the original one - a half-written or foreign file must not stop
        the editor from starting. A file that parses to something other than an object
        still comes back as it is and fails at the caller's first `.get`, unchanged from
        before; no report has ever had that shape.
        """
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _apply_report_npc_names(self, report: dict) -> None:
        """The report's `npc_name_mapping` block.

        Apart from the other name blocks because it normalises both halves of a pair
        differently - the id lowercased because it is looked up against a save, the name
        only trimmed - and because it drops a pair where either half is missing rather
        than storing an empty label.
        """
        npc_mapping = report.get("npc_name_mapping", {})
        if isinstance(npc_mapping, dict):
            for npc_id, npc_name in npc_mapping.items():
                if not isinstance(npc_id, str) or not isinstance(npc_name, str):
                    continue
                npc_id = npc_id.strip().lower()
                npc_name = npc_name.strip()
                if npc_id and npc_name:
                    self.npc_name_map[npc_id] = npc_name

    def _apply_report_skills(self, report: dict) -> None:
        """The two skill blocks, `skills_mapping` and `skills_meta`.

        Together and separate from the traders because the two halves of "skill" behave
        differently: the names are merged **into** the built-in ones the reset put there,
        while the meta replaces whatever was in it. Keeping both in one method is what
        makes that difference visible.
        """
        skills_mapping = report.get("skills_mapping", {})
        meta = report.get("skills_meta")
        if isinstance(meta, dict):
            self.skills_meta = meta
        if isinstance(skills_mapping, dict):
            for k, v in skills_mapping.items():
                self.skills_name_map[str(k)] = str(v)

    def _apply_report_trader_meta(self, report: dict) -> None:
        """Everything the report says about traders: `trader_mapping`, `shops_meta`,
        `max_account_level` and `level_progress`.

        One method because Hackerman's Lab reads all four as one answer - a trader's level
        is capped by `max_account_level`, and `level_progress` is where that ceiling is
        read from - so a report missing one of them raises a question about this group
        rather than about four unrelated fields.
        """
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

    def _apply_report_quest_and_craft_meta(self, report: dict) -> None:
        """The three blocks the Quests and Crafting tabs live on: `quests_meta`,
        `craft_meta` and `crafting_meta`.

        Together because only the first of them is keyed and the contrast is the point:
        quest ids are looked up against a save, so they are lowercased once here and rows
        that are not objects are dropped, while the two craft blocks are handed on exactly
        as the extractor grouped them - the recycling half and the workbench half.
        """
        quests_meta = report.get("quests_meta")
        if isinstance(quests_meta, dict):
            self.quests_meta = {
                str(k).strip().lower(): v
                for k, v in quests_meta.items()
                if isinstance(v, dict)
            }

        craft_meta = report.get("craft_meta")
        if isinstance(craft_meta, dict):
            self.craft_meta = craft_meta

        crafting_meta = report.get("crafting_meta")
        if isinstance(crafting_meta, dict):
            self.crafting_meta = crafting_meta

    def _apply_report_presets(self, report: dict) -> None:
        """The `presets_meta` block, the assembled weapons the spawner walks.

        On its own because it is the one block that rewrites its rows on the way in rather
        than storing them: a preset without a root is not a preset and is dropped here, so
        no caller has to ask again.
        """
        presets_meta = report.get("presets_meta")
        if isinstance(presets_meta, list):
            # Keyed lookups happen per template, so the roots are lowercased once here
            # rather than at every call site.
            self.presets_meta = [
                dict(row, root=str(row.get("root") or "").strip().lower())
                for row in presets_meta
                if isinstance(row, dict) and row.get("root")
            ]

    def _apply_report_item_catalog(self, report: dict) -> None:
        """The `item_catalog` block, which fills two views of the same rows: the list the
        catalog tab renders in order, and the by-template lookup everything else asks.

        Its own method because those two must not drift apart - a row is appended to the
        list and stored under its key in the same pass, so every template the catalog
        shows is one the meta lookup can answer for.
        """
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

    def _template_names_from_report(self, mapping: list, catalog_rows: object,
                                    has_catalog: bool) -> dict[str, str]:
        """The report's two name sources, reduced to one `template id -> name` map.

        The only block that built a local instead of writing to `self`, which is why it
        returns one: the caller layers the manual aliases over the result and commits it
        in a single assignment, so `template_name_map` is never briefly missing the
        overrides. `catalog_rows` and `has_catalog` come in as parameters for the same
        reason - they are the caller's decision about which candidate is being read.
        """
        # Names come from `item_catalog` (`name`), which the app reads anyway. Old
        # reports carried the identical names a second time under `mapping`
        # (`name_guess`) - measured name for name across all 1596 templates - which
        # is why newer reports drop that block and old ones still load here.
        loaded: dict[str, str] = {}

        def harvest_names(rows: list, name_key: str) -> None:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                tid = row.get("template_id")
                name = row.get(name_key)
                if not isinstance(tid, str) or not isinstance(name, str):
                    continue
                name = name.strip()
                if not name:
                    continue
                loaded[tid.lower()] = name

        harvest_names(catalog_rows if has_catalog else [], "name")
        if not loaded:
            harvest_names(mapping, "name_guess")
        return loaded

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

    def _catalog_template_ids(self) -> set[str]:
        """The catalog's own template ids, lowercased like every other id lookup here."""
        return {
            str(row.get("template_id", "")).strip().lower()
            for row in self.game_item_catalog
            if str(row.get("template_id", "")).strip()
        }

    def _relabel_only_new(self) -> None:
        """Put the count in the label, and switch the filter off when there is nothing.

        A checkbox that reduces ~1600 rows to none is a dead end which only answers after it
        has been ticked - the same reason a container with no free cell is not offered as a
        placement target. Disabling it also makes "nothing new" readable at a glance.
        """
        t = TRANSLATIONS[self.current_lang]
        count = len(self.new_template_ids)
        self.cat_only_new_cb.configure(text=t["cat_only_new"].format(count=count))
        if count:
            self.cat_only_new_cb.state(["!disabled"])
        else:
            self.catalog_only_new_var.set(False)
            self.cat_only_new_cb.state(["disabled"])

    # Zwischenspeicher, die aus dem Katalog gebaut werden und ihn deshalb ueberdauern, wenn
    # er ausgetauscht wird. Alle drei entstehen faul beim ersten Zugriff und werden nie wieder
    # angefasst - nach "Refresh Names from Game" zeigten sie den Rest der Sitzung den alten
    # Stand, waehrend Katalog und Inventarbaum daneben schon den neuen zeigten.
    CATALOG_CACHES = ("_fits_on_index", "_subcat_labels", "_slot_type_labels")

    def _drop_catalog_caches(self) -> None:
        """Wirft weg, was aus dem alten Katalog gebaut wurde, damit es neu entsteht.

        Wie bei `TIMER_ATTRIBUTES` ist die Liste das Empfindliche: wer einen vierten
        `hasattr`-gestuetzten Zwischenspeicher aus Katalogdaten anlegt und ihn hier nicht
        eintraegt, hat denselben Fehler wieder. `tests/test_new_templates.py` haelt die Liste
        deshalb gegen den Quelltext.
        """
        for name in self.CATALOG_CACHES:
            if hasattr(self, name):
                delattr(self, name)

    def _on_extraction_success(
        self,
        game_dir: Path,
        output_info: str = "",
        report: dict | None = None,
    ) -> None:
        old_count = len(self.template_name_map)
        ids_before = self._catalog_template_ids()
        self.last_game_path = str(game_dir)
        self._load_template_name_map()
        self._drop_catalog_caches()
        # Both of these have to happen *before* the views are rebuilt: the catalog reads
        # `new_template_ids` while it inserts its rows, and `_relabel_only_new` may clear
        # the filter when nothing is new. Setting them afterwards leaves the first render
        # showing the previous refresh's marks.
        self.new_template_ids = newly_added_templates(ids_before, self._catalog_template_ids())
        save_config_new_templates(self.new_template_ids)
        self._relabel_only_new()
        self._refresh_catalog_view()
        new_count = len(self.template_name_map)
        self._refresh_scope_keeping_open()

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
        # Say the number here rather than only colouring rows on a tab the user may not be
        # looking at. Silence when nothing was added is the honest answer to "what did the
        # update bring", and is also what a first run reports - it has no baseline.
        if self.new_template_ids:
            output_info = (
                f"{output_info}\n\n{t['msg_mapping_new_items'].format(count=len(self.new_template_ids))}"
            ).strip()
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

        # Closing the window while an extraction thread is still running destroys the Tk
        # root under it; `root.after` then raises, the failure handler's own `root.after`
        # raises again, and the thread dies on an unhandled exception. There is no UI left
        # to report to at that point, so the result is deliberately dropped instead.
        def post_to_ui(callback) -> None:
            try:
                self.root.after(0, callback)
            except tk.TclError:
                pass

        try:
            # Resolvable only after Scripts/ was put on sys.path above, so a checker
            # reading the file statically cannot find it.
            import extract_template_mapping  # type: ignore[import-not-found]

            def thread_target():
                try:
                    report = extract_template_mapping.run_extraction(
                        game_path_str=str(game_dir),
                        save_path_str=save_path_str,
                        out_dir_str=out_dir_str,
                        locale=locale_str,
                    )
                    post_to_ui(
                        lambda r=report: self._on_extraction_success(game_dir, report=r)
                    )
                except Exception as ex:
                    # Bind the message now: `ex` is unbound once the except block exits,
                    # so a closure over it would raise NameError inside the Tk callback.
                    message = f"Error in-process: {ex}"
                    post_to_ui(lambda m=message: self._on_extraction_failure(m))

            threading.Thread(target=thread_target, daemon=True).start()

        except ImportError:
            # Fallback to subprocess
            extractor_script = self._extractor_script_path()
            if not extractor_script.exists():
                messagebox.showerror(
                    "Mapping refresh",
                    "Extractor script not found and could not be imported.",
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
                        post_to_ui(
                            lambda: self._on_extraction_success(game_dir, result.stdout)
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
                        post_to_ui(
                            lambda: self._on_extraction_failure(
                                f"Extractor failed (exit {result.returncode}).\n\n{details}"
                            )
                        )
                except Exception as ex:
                    message = f"Failed to run extractor subprocess:\n{ex}"
                    post_to_ui(lambda m=message: self._on_extraction_failure(m))

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

    def _category_tag_for_members(self, members: list[str]) -> str | None:
        if not members:
            return None
        item = self.manager.get_item(members[0])
        if not item:
            return None
        template_id = str(item.get("TemplateId") or "").strip().lower()
        if not template_id:
            return None
        meta = self.game_item_meta_by_template_id.get(template_id, {})
        cid = meta.get("category_id")
        sid = meta.get("subcategory_id")
        return category_tag_for_cat_id(cid, sid)

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
        inner = item_data(item)
        if inner:
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
        inner = item_data(item)
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
        inner = item_data(item)
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

    # --- Crafting ----------------------------------------------------------------------
    # Read-only, like the Quests tab, and for the same reason: what a workbench can make comes
    # from the game data, and the save only decides how far the bench is built and what is in
    # store. Recycling is deliberately absent - it is the same recipe list read from the item's
    # end, and the item info window already answers it.

    def _owned_unit_counts(self) -> dict[str, int]:
        """Template id -> how many units of it the save holds, stacks counted by quantity.

        A stack is one item carrying `StackableComponent_quantity`, so counting items would
        report 1 for a stack of sixty. An item with no quantity field counts as one unit.
        """
        counts: dict[str, int] = {}
        for item in self.manager.get_all_items_flat():
            template_id = str(item.get("TemplateId") or "").strip().lower()
            if not template_id:
                continue
            inner = item_data(item)
            quantity = inner.get("StackableComponent_quantity")
            units = (
                quantity if isinstance(quantity, int) and not isinstance(quantity, bool)
                and quantity > 0 else 1
            )
            counts[template_id] = counts.get(template_id, 0) + units
        return counts

    def _recipe_state(self, recipe: dict, module: dict, owned: dict[str, int]) -> str:
        """One of "ready", "missing", "locked", "unbuildable" for one recipe.

        The last one is not a shortcoming of the save: a recipe can ask for a module level the
        module has no build step for - `MinLevel` 9, 333 and 999 appear against ceilings of 2
        and 3 - so the recipe exists in the data while the workbench to run it does not.
        """
        min_level = recipe.get("min_level")
        min_level = min_level if isinstance(min_level, int) else 1
        max_level = module.get("max_level")
        max_level = max_level if isinstance(max_level, int) else 0
        if max_level and min_level > max_level:
            return "unbuildable"
        if min_level > int(module.get("_level") or 0):
            return "locked"
        for row in recipe.get("inputs") or []:
            template_id = str(row.get("template_id") or "").strip().lower()
            needed = row.get("count") if isinstance(row.get("count"), int) else 1
            if owned.get(template_id, 0) < needed:
                return "missing"
        return "ready"

    def _build_crafting_tab(self, parent: ttk.Frame) -> None:
        """Every workbench recipe, grouped by module and by the level it needs."""
        crafting_bar = ttk.Frame(parent)
        crafting_bar.pack(fill="x", padx=10, pady=(10, 4))
        self.crafting_count_lbl = ttk.Label(crafting_bar, style="Status.TLabel")
        self.crafting_count_lbl.pack(side="left")

        self.craft_search_btn = ttk.Button(crafting_bar, command=self._refresh_crafting_tree)
        self.craft_search_btn.pack(side="right")
        self.craft_search_var = tk.StringVar()
        self.craft_search_entry = ttk.Entry(
            crafting_bar, textvariable=self.craft_search_var, width=26)
        self.craft_search_entry.pack(side="right", padx=(6, 6))
        self.craft_search_entry.bind("<Return>", lambda _event: self._refresh_crafting_tree())
        self.craft_search_lbl = ttk.Label(crafting_bar)
        self.craft_search_lbl.pack(side="right")

        panes = ttk.PanedWindow(parent, orient="vertical")
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        tree_frame = ttk.Frame(panes)
        panes.add(tree_frame, weight=3)

        scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        scroll.pack(side="right", fill="y")
        self.crafting_tree = ttk.Treeview(
            tree_frame,
            columns=("needs", "time", "state"),
            show="tree headings",
            selectmode="browse",
            yscrollcommand=scroll.set,
        )
        scroll.configure(command=self.crafting_tree.yview)
        self.crafting_tree.pack(side="left", fill="both", expand=True)
        self.crafting_tree.column("#0", width=self._scale_px(300), anchor="w", stretch=True)
        # No "makes" column: all 150 recipes have exactly one output, so the row title already
        # names it and a second column would repeat every row word for word.
        self.crafting_tree.column("needs", width=self._scale_px(520), anchor="w")
        self.crafting_tree.column("time", width=self._scale_px(90), anchor="w")
        self.crafting_tree.column("state", width=self._scale_px(130), anchor="w")
        self.crafting_tree.bind("<<TreeviewSelect>>", self._on_recipe_selected)

        detail_frame = ttk.Frame(panes)
        panes.add(detail_frame, weight=1)
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical")
        detail_scroll.pack(side="right", fill="y")
        self.recipe_detail = tk.Text(
            detail_frame, height=7, wrap="word", bg=COLOR_PANEL, fg=COLOR_TEXT,
            relief="flat", padx=8, pady=6, yscrollcommand=detail_scroll.set,
        )
        detail_scroll.configure(command=self.recipe_detail.yview)
        self.recipe_detail.pack(side="left", fill="both", expand=True)
        self.recipe_detail.tag_configure("field", foreground=COLOR_ACCENT)
        self.recipe_detail.tag_configure("dim", foreground="#9a9a9a")
        self.recipe_detail.tag_configure("short", foreground="#f48771")
        self.recipe_detail.configure(state="disabled")

        self.crafting_hint = ttk.Label(parent, style="Hint.TLabel",
                                       wraplength=900, justify="left")
        self.crafting_hint.pack(anchor="w", padx=10, pady=(0, 6))
        # iid -> (module index, recipe index), because a Treeview row carries no payload.
        self.crafting_rows: dict[str, tuple[int, int]] = {}

    def _refresh_crafting_tree(self) -> None:
        """Rebuilds the tree. Called on load, on a language switch and after a restore."""
        t = TRANSLATIONS[self.current_lang]
        if not hasattr(self, "crafting_tree"):
            return
        self.crafting_tree.delete(*self.crafting_tree.get_children())
        self.crafting_rows = {}

        modules = [m for m in ((self.crafting_meta or {}).get("modules") or [])
                   if isinstance(m, dict)]
        self.crafting_hint.configure(text=t["craft_hint"])
        if not modules:
            self.crafting_count_lbl.configure(text=t["craft_no_data"])
            return

        levels = self._shelter_module_levels()
        owned = self._owned_unit_counts()
        state_labels = {
            "ready": t["craft_state_ready"],
            "missing": t["craft_state_missing"],
            "locked": t["craft_state_locked"],
            "unbuildable": t["craft_state_unbuildable"],
        }

        query = self.craft_search_var.get().strip().lower() if hasattr(
            self, "craft_search_var") else ""

        total = ready = 0
        for module_index, module in enumerate(modules):
            module["_level"] = levels.get(
                str(module.get("foundation_id") or "").strip().lower(), 0)
            label = str(module.get("name") or module.get("alias") or "")

            recipes = list(enumerate(module.get("recipes") or []))
            if query:
                recipes = [(index, recipe) for index, recipe in recipes
                           if self._recipe_matches(recipe, label, query)]
                if not recipes:
                    continue

            node = self.crafting_tree.insert(
                "", "end",
                text=t["craft_module_row"].format(
                    name=label, level=module["_level"], max=module.get("max_level") or 0,
                    count=len(recipes)),
                open=bool(query) or bool(module["_level"]),
            )

            by_level: dict[int, list[tuple[int, dict]]] = {}
            for recipe_index, recipe in recipes:
                min_level = recipe.get("min_level")
                by_level.setdefault(min_level if isinstance(min_level, int) else 1, []).append(
                    (recipe_index, recipe))

            for min_level in sorted(by_level):
                level_node = self.crafting_tree.insert(
                    node, "end",
                    text=t["craft_level_row"].format(
                        level=min_level, count=len(by_level[min_level])),
                    open=bool(query) or min_level <= int(module["_level"] or 0),
                )
                for recipe_index, recipe in by_level[min_level]:
                    state = self._recipe_state(recipe, module, owned)
                    total += 1
                    ready += state == "ready"
                    needs = ", ".join(
                        self._recipe_part_text(row) for row in recipe.get("inputs") or [])
                    iid = self.crafting_tree.insert(
                        level_node, "end",
                        text=self._recipe_title(recipe),
                        values=(needs,
                                self._format_duration(recipe.get("duration_seconds")),
                                state_labels[state]),
                    )
                    self.crafting_rows[iid] = (module_index, recipe_index)

        self.crafting_count_lbl.configure(
            text=(t["craft_count_filtered"].format(
                recipes=total, ready=ready, query=self.craft_search_var.get().strip())
                if query else
                t["craft_count"].format(
                    modules=len(modules), recipes=total, ready=ready)))

    def _recipe_matches(self, recipe: dict, module_label: str, query: str) -> bool:
        """What it makes, what it takes, its internal name, and the workbench it runs on.

        The ingredients are in there on purpose: "what can I do with duct tape" is the
        question this list answers best, and 254 recipe names are internal identifiers.
        """
        parts = [module_label, str(recipe.get("name") or ""), self._recipe_title(recipe)]
        for side in ("inputs", "outputs"):
            for row in recipe.get(side) or []:
                parts.append(self._template_name_for_template_id(row.get("template_id")) or "")
        return query in " ".join(parts).lower()

    def _recipe_part_text(self, row: dict) -> str:
        """"3x Acid" for one side of a recipe, with the count left out when it is one."""
        template_id = str(row.get("template_id") or "")
        name = self._template_name_for_template_id(template_id) or template_id
        count = row.get("count")
        return f"{count}x {name}" if isinstance(count, int) and count > 1 else name

    def _recipe_title(self, recipe: dict) -> str:
        """What to call the recipe: what it makes, since its own name is often internal.

        254 of the recipe names read like `Head_01_Model_05`. The first output resolved
        through the catalog is the useful label; the raw name stays as the fallback and is
        shown in the detail pane either way.
        """
        outputs = recipe.get("outputs") or []
        if outputs:
            name = self._template_name_for_template_id(outputs[0].get("template_id"))
            if name:
                count = outputs[0].get("count")
                return f"{count}x {name}" if isinstance(count, int) and count > 1 else name
        return str(recipe.get("name") or "")

    def _on_recipe_selected(self, _event=None) -> None:
        """Fills the detail pane: what it takes, what is in store, what it makes."""
        t = TRANSLATIONS[self.current_lang]
        selection = self.crafting_tree.selection()
        self.recipe_detail.configure(state="normal")
        self.recipe_detail.delete("1.0", "end")

        found = self.crafting_rows.get(selection[0]) if selection else None
        if found is None:
            self.recipe_detail.configure(state="disabled")
            return

        module_index, recipe_index = found
        modules = (self.crafting_meta or {}).get("modules") or []
        module = modules[module_index]
        recipe = (module.get("recipes") or [])[recipe_index]
        owned = self._owned_unit_counts()

        def line(label: str, value: str, tag: str = "") -> None:
            self.recipe_detail.insert("end", f"{label}: ", "field")
            self.recipe_detail.insert("end", f"{value}\n", tag or ())

        line(t["craft_detail_makes"],
             ", ".join(self._recipe_part_text(row) for row in recipe.get("outputs") or []))
        line(t["craft_detail_where"],
             t["craft_detail_where_value"].format(
                 name=str(module.get("name") or module.get("alias") or ""),
                 needed=recipe.get("min_level"), level=module.get("_level") or 0,
                 max=module.get("max_level") or 0))
        line(t["craft_detail_time"], self._format_duration(recipe.get("duration_seconds")))

        self.recipe_detail.insert("end", f"{t['craft_detail_needs']}:\n", "field")
        for row in recipe.get("inputs") or []:
            template_id = str(row.get("template_id") or "").strip().lower()
            needed = row.get("count") if isinstance(row.get("count"), int) else 1
            have = owned.get(template_id, 0)
            name = self._template_name_for_template_id(template_id) or template_id
            self.recipe_detail.insert(
                "end", f"   {name}: {have} / {needed}\n",
                "dim" if have >= needed else "short")

        internal = str(recipe.get("name") or "")
        if internal:
            line(t["craft_detail_internal"], internal, "dim")
        self.recipe_detail.configure(state="disabled")

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

    def _required_parts_growth(self, template_id: str | None, _tiefe: int = 0,
                               _gesehen: frozenset = frozenset()) -> tuple[int, int]:
        """Wie viel die Pflichtteile zusammen anbauen, die `_fill_required_slots` gleich anlegt.

        Dieselbe Rekursion wie dort und aus demselben Grund: die Anforderung setzt sich fort -
        eine SR93 braucht einen Schaft, und der Schaft braucht einen Lauf. Jeder Pflichtplatz
        im Bericht nennt sein `default_template_id`, es ist also nichts zu raten.
        """
        tid = str(template_id or "").strip().lower()
        if not tid or tid in _gesehen or _tiefe > 6:
            return 0, 0
        _gesehen = _gesehen | {tid}
        breite = hoehe = 0
        meta = self.game_item_meta_by_template_id.get(tid, {})
        for slot in (meta.get("mod_slots") or []):
            if not slot.get("required"):
                continue
            standard = str(slot.get("default_template_id") or "").strip().lower()
            if not standard or standard not in self.game_item_meta_by_template_id:
                continue
            resize = self.game_item_meta_by_template_id[standard].get("resize")
            if isinstance(resize, dict):
                breite += int(resize.get("width") or 0)
                hoehe += int(resize.get("height") or 0)
            weiter = self._required_parts_growth(standard, _tiefe + 1, _gesehen)
            breite += weiter[0]
            hoehe += weiter[1]
        return breite, hoehe

    def _spawn_footprint_for_template(self, template_id: str | None, rotated: bool = False):
        """Was ein frisch gespawnter Gegenstand braucht - **mit den Pflichtteilen daran.**

        `_footprint_for_template` gibt die nackte Vorlage zurueck, und beim Spawnen ist das die
        falsche Frage: der Editor haengt unmittelbar danach `_fill_required_slots` an, und die
        Waffe ist ab diesem Moment groesser. Gefragt wurde vorher, gelegt wird nachher.

        **Gemessen im Spiel am 10.09.2026.** Eine Neckar SR93 aus dem Katalog: gefragt wurde nach
        ihrer Vorlage 1x1, dann kamen Schaft (+3) und daran der Lauf (+1). Der Editor legte sie
        auf Spalte 6 eines acht Spalten breiten Reiters - dort ist rechts fuer zwei Zellen Platz.
        Das Spiel konnte sie nicht zeichnen: **unsichtbar, und eine Zelle blockiert, in die
        nichts mehr geht.** Es hat ihr selbst `BaseComponent_width: 4` eingetragen, Vorlage plus
        Schaft; den Lauf am Schaft hat es nicht mitgezaehlt.

        **24 der 35 wachsenden Schusswaffen sind betroffen**, und nicht knapp: eine Ronnie B4
        fragt nach 1x1 und ist mit ihren Pflichtteilen 6x2, eine LM39 fragt 3x1 und ist 6x2.

        Gedeckelt durch `MaxSize`, wie ueberall - die Teilesumme schaetzt nach oben.
        """
        vorlage = self._footprint_for_template(template_id)
        if vorlage is None:
            return None
        zuwachs = self._required_parts_growth(template_id)
        breite, hoehe = vorlage[0] + zuwachs[0], vorlage[1] + zuwachs[1]
        meta = self.game_item_meta_by_template_id.get(str(template_id or "").strip().lower(), {})
        if isinstance(meta.get("max_width"), int):
            breite = min(breite, meta["max_width"])
        if isinstance(meta.get("max_height"), int):
            hoehe = min(hoehe, meta["max_height"])
        breite, hoehe = max(breite, vorlage[0]), max(hoehe, vorlage[1])
        return (hoehe, breite) if rotated else (breite, hoehe)

    def _catalog_spawn_need(self, template_ids) -> tuple[int, int] | None:
        """Was die Zielliste eines Katalog-Spawns als Bedarf melden muss.

        Die pessimistische Box aus groesster Breite und groesster Hoehe ueber alle gewaehlten
        Vorlagen: jedes Stueck braucht seinen eigenen Platz, also ist das die ehrliche Auskunft.
        Leicht zu gross fuer die kleineren, aber nie zu klein - und zu klein ist die Richtung,
        die im Postfach endet.

        Gefragt wird mit `_spawn_footprint_for_template`, also **mit den Pflichtteilen**, die
        gleich danach angelegt werden. Sonst meldet der Dialog Platz fuer eine Waffe, die es in
        dieser Groesse nie gibt.

        Eine eigene Methode und keine drei Zeilen im Dialog, damit ein Test das Ergebnis messen
        kann - im Dialog eingebaut blieb eine Mutation gruen, die hier auf die nackte Vorlage
        zurueckdrehte. Dieselbe Lehre wie bei `_placement_combo_width`.
        """
        flaechen = [f for f in (self._spawn_footprint_for_template(tid)
                                for tid in template_ids) if f]
        if not flaechen:
            return None
        return (max(f[0] for f in flaechen), max(f[1] for f in flaechen))

    def _footprint_for_item(self, item_id: str):
        """(w, h) of an item as it occupies cells, `BaseComponent_rotated` swapping the axes.

        Four steps, in this order:

        1. **Start at what the save says.** A missing half means "as the template", because the
           serializer omits what equals the default - not "unknown". Discarding both because one
           was absent turned an Eliphalet 700 stored at width 5 into a 1x1.
        2. **Grow it by the fitted parts.** Every attachment that enlarges its host carries a
           `Resize` in the game data; 132 templates do, and a missing field means no growth.
        3. **Cap that at `MaxSize`.** That is the size with *every* slot filled, so a weapon
           with empty slots must not be given it.
        4. **Never go below step 1.** The save's number is a floor, never the answer.

        **Why both halves of steps 2 and 3 are needed**, read off the screen from the weapon
        cases on 2026-09-09:

            Saigak-13   2x1 + parts = 6x2, MaxSize 6x2 -> 6x2   in game 6x2, save says 4x1
            MA17        2x1 + parts = 5x2, MaxSize 6x3 -> 5x2   in game 5x2, save says 3x1
            SVS         2x1 + parts = 6x4, MaxSize 5x2 -> 5x2   in game 5x2, save says 3x1

        The sum alone is too big for the SVS, `MaxSize` alone too big for the MA17, and the
        stored size too small for all three. The smaller of the two, floored by the save, fits
        all six weapons that were read. Modelling the seven cases went from 164 claimed cells
        to 338 with no overlap appearing.

        A **container** is skipped: `collect_subtree` cannot tell an attached part from a stored
        one, and a backpack does not grow because something is in it.

        **Nothing overrides this any more.** Until 2026-09-10 a fourth step did:
        `_own_placed_footprint` modelled an item this editor had assembled at the largest size
        the data mentions, recognising it by a stored size equal to its template's. The game
        wrote that exact shape itself the same evening - MKP, M420 and LM39 came back from a
        game start carrying their template's 3x1 - so the signature marked the game's own items
        as the editor's and blocked six cells too many. The game's counter settles it: with the
        override a tab read 211, without it 205, and 205 is what the game shows.

        The room a neighbour might still need was reserved by `_keep_out_cells` for a day
        after that; on 2026-09-11 the game refused that too. Nothing is held clear around an
        item any more - see `_placement_in` for the two game starts that settled it.
        """
        item = self.manager.get_item(item_id) or {}
        data = item_data(item)
        rotated = bool(data.get("BaseComponent_rotated"))

        template_id = str(item.get("TemplateId") or "").lower()
        width = data.get("BaseComponent_width")
        height = data.get("BaseComponent_height")
        # **Eine fehlende Zahl heisst "wie die Vorlage", nicht "unbekannt".** Der Serialisierer
        # laesst Vorgabewerte weg, und beide zu verwerfen, weil eine fehlt, macht aus einer
        # Waffe ihre Vorlage: eine Eliphalet 700 steht im Save mit Breite 5 und ohne Hoehe und
        # wurde als 1x1 gerechnet - fuenffach zu schmal. Im Koffer liegt sie sichtbar quer
        # ueber fuenf Zellen. 39 Gegenstaende eines echten Saves tragen nur eine der beiden
        # Zahlen; der Fehler faellt in `test_placement_real.py` nicht auf, weil dieselbe
        # Funktion auch die Nachbarn kleinrechnet und dadurch keine Ueberlappung entsteht.
        template = self._footprint_for_template(template_id)
        if not isinstance(width, int):
            if template is None:
                return None
            width = template[0]
        if not isinstance(height, int):
            if template is None:
                return None
            height = template[1]
        # **Was die angebauten Teile daraus machen, gedeckelt durch `MaxSize`.** Das ist die
        # Regel des Spiels, und sie wurde am 09.09.2026 an den Waffenkoffern belegt, nachdem
        # die Groessen im Spiel abgelesen worden waren:
        #
        #   Saigak-13  Vorlage 2x1 + Teile (4,1) = 6x2, MaxSize 6x2 -> 6x2   im Spiel 6x2
        #   MA17       Vorlage 2x1 + Teile (3,1) = 5x2, MaxSize 6x3 -> 5x2   im Spiel 5x2
        #   SVS        Vorlage 2x1 + Teile (4,3) = 6x4, MaxSize 5x2 -> 5x2   im Spiel 5x2
        #
        # `MaxSize` ist die Groesse mit voller Bestueckung, die Summe die mit der jetzigen -
        # keine der beiden allein stimmt, das Kleinere von beiden trifft alle sechs abgelesenen
        # Waffen. Der eingetragene Wert bleibt Untergrenze: das Spiel fuehrt ihn nicht nach,
        # dieselbe Saigak steht dort mit 4x1.
        #
        # Gemessen: in den sieben Waffenkoffern belegt das 338 Zellen ohne eine einzige
        # Ueberlappung, gegen 164 mit dem eingetragenen Wert allein. Ueber das ganze Save
        # 3091 Zellen, ebenfalls ohne Ueberlappung.
        #
        # Ein Behaelter ist ausgenommen: `collect_subtree` unterscheidet nicht zwischen
        # angebaut und eingelegt, und ein Rucksack waechst nicht durch seinen Inhalt.
        if not self._container_cells_for(item_id):
            template = self._footprint_for_template(template_id)
            if template:
                zuwachs = self._parts_resize_sum(item_id)
                gewachsen_b = template[0] + zuwachs[0]
                gewachsen_h = template[1] + zuwachs[1]
                meta = self.game_item_meta_by_template_id.get(template_id, {})
                hoechst_b, hoechst_h = meta.get("max_width"), meta.get("max_height")
                if isinstance(hoechst_b, int):
                    gewachsen_b = min(gewachsen_b, hoechst_b)
                if isinstance(hoechst_h, int):
                    gewachsen_h = min(gewachsen_h, hoechst_h)
                width, height = max(width, gewachsen_b), max(height, gewachsen_h)

        if rotated:
            return height, width
        return width, height

    def _size_to_record(self, template_id: str) -> tuple[int | None, int | None]:
        """Die Groesse, die beim Anlegen in den Spielstand gehoert - oder (None, None).

        **Ein dehnbarer Gegenstand traegt seine Basisgroesse nie.** Gezaehlt in einem echten
        Spielstand von 1887 Gegenstaenden: 63 dehnbare tragen eine Groesse, die von der
        Vorlage **abweicht** (die sind wirklich gewachsen), 11 tragen gar keine - und **0**
        tragen ihre Basisgroesse. Das Spiel rechnet sie sich aus, wenn sie nicht dasteht.

        Der Editor schrieb sie trotzdem, und zwar mit Absicht: `_own_placed_footprint` hat
        genau diese Signatur als Erkennungszeichen fuer "das habe ich gelegt" benutzt, weil
        kein echter Gegenstand sie haben sollte. Beides ist widerlegt - die Signatur schreibt
        das Spiel selbst (deshalb ist jene Methode weg), und die Groesse hier zu schreiben
        schickt die Waffe ins Postfach. Kontrollierter Versuch mit vier Gesterby, die sich in
        je einer Eigenschaft unterschieden:

            mit Groesse an der Waffe   -> Postfach
            ohne Groesse an der Waffe  -> bleibt liegen
            Groesse nur am Magazin     -> bleibt liegen
            ohne Magazin               -> Postfach (der Steckplatz ist Pflicht)

        Zweimal wiederholt, jedes Mal gleich. Die Groesse **am Anbauteil** ist harmlos; das
        Spiel schreibt sie dort selbst 224-mal.

        Nicht restlos verstanden: SPS und STR38 tragen dieselbe Form und bleiben liegen,
        Gesterby und RAMB nicht. Was die beiden unterscheidet, ist offen - lange Waffen mit
        Pflicht-Steckplatz, und Gesterby kann als einzige gar nicht wachsen (Vorlage =
        MaxSize). Der Fix hilft, wo es klemmt, und aendert nichts, wo es geht: er bringt den
        Editor auf eine Form, die im Spielstand des Spiels 0 Gegenbeispiele hat.
        """
        meta = self.game_item_meta_by_template_id.get(str(template_id or "").strip().lower(), {})
        breite, hoehe = meta.get("width"), meta.get("height")
        if not isinstance(breite, int) or not isinstance(hoehe, int):
            return None, None
        if not meta.get("is_resizable"):
            # Starr: die Groesse aendert sich nie, und das Spiel schreibt sie hier selbst.
            return breite, hoehe
        # Dehnbar: nur die **gewachsene** Groesse gehoert hinein. Sie entsteht erst mit den
        # Teilen, die gleich angebaut werden - beim Anlegen ist sie also noch die Basis.
        return None, None

    def _parts_resize_sum(self, item_id: str) -> tuple[int, int]:
        """Wie viel die angebauten Teile zusammen an Breite und Hoehe hinzufuegen.

        Die Zahlen stehen in den Spieldaten je Teil unter `resize`. Gemessen an einem echten
        Save: eine DVS mit FOXTROT-U (+0/+1), Lauf (+1/+0) und Schalldaempfer (+1/+0) waechst
        von 3x1 auf 5x2.
        """
        breite = hoehe = 0
        for part_id in self.manager.collect_subtree(str(item_id))[1:]:
            part = self.manager.get_item(part_id) or {}
            resize = self.game_item_meta_by_template_id.get(
                str(part.get("TemplateId") or "").strip().lower(), {}).get("resize")
            if isinstance(resize, dict):
                breite += int(resize.get("width") or 0)
                hoehe += int(resize.get("height") or 0)
        return breite, hoehe

    def _footprint_for_placing(self, item_id: str):
        """Wie viel Platz ein Gegenstand **beim Hinlegen** braucht: dasselbe, in Vorlagenlage.

        Dass das zwei Funktionen sind, hat einen Grund, und es ist nicht mehr der urspruengliche.
        Gemeldet am 09.09.2026: eine vollstaendig zusammengebaute DVS liess sich aus der
        Charakterausruestung in Reiter 4 schieben, wo vier freie Zellen nebeneinander lagen - und
        das Spiel schickte sie ins Postfach. Damals rechnete `_footprint_for_item` nur den
        eingetragenen Wert und hier stand die Wachstumsrechnung daneben. Inzwischen rechnet
        `_footprint_for_item` die echte Groesse selbst - Vorlage plus die `resize`-Summe der
        Teile, gedeckelt durch `MaxSize`, nie unter dem Eingetragenen - und aus dem Spiel ist
        bestaetigt, dass das Spiel genau diese Flaeche sperrt und keinen Rand darum haelt.

        Damit bleibt **ein** Unterschied, und der ist der ganze Zweck dieser Funktion: die Lage.

        **In der Orientierung der Vorlage, ohne die aktuelle Drehung.** `find_placement` probiert
        ohnehin beide Lagen und meldet zurueck, ob es drehen musste - und dieses "gedreht" wird als
        `BaseComponent_rotated` geschrieben. Gaebe man die bereits gedrehten Maße hinein, waere die
        Meldung relativ zur alten Drehung und die Flagge danach falsch herum. Gemessen am
        09.09.2026 an einer Ramon 1891, die gedreht in einem Reiter lag: der Editor prueft 3x5,
        legt sie dann ungedreht ab, wo sie 4x1 belegt - Spalte 3 hat nie jemand angesehen.
        `_footprint_for_item` behaelt den Tausch, weil es beschreibt, was bedeckt ist, statt
        wonach zu suchen ist.

        **Hier stand bis zum 10.09.2026 eine zweite Wachstumsrechnung**, und die hob den Deckel
        von `_footprint_for_item` wieder auf: sie addierte die `resize`-Summe ein zweites Mal,
        ohne `MaxSize`. Die Summe schaetzt aber nach oben - sie trifft 139 von 162 gewachsenen
        Gegenstaenden genau und liegt beim Rest darueber, eine SVS bei 6x4 gegen ein gemessenes
        und angegebenes 5x2. Am echten Save verlangten dadurch **36 Gegenstaende mehr, als sie
        belegen, 22 davon ueber ihrem eigenen MaxSize**: zusammen 91 Zellen, im schlimmsten Fall
        eine Ronnie B4 mit 7x4 statt 6x2. Mit Deckel gerechnet aendert der Nachschlag bei keinem
        einzigen der 1882 Gegenstaende noch etwas - er war nur noch der Weg, den Deckel zu
        umgehen, und ist deshalb weg statt gedeckelt.

        **Auch ein Behaelter geht durch die Drehung.** Er hatte einen eigenen Kurzausstieg, der
        die schon gedrehten Maße zurueckgab - derselbe Fehler wie bei der Ramon, an 14 gedrehten
        Item boxes im echten Save. Was ihn noetig gemacht hatte, ist die Wachstumsrechnung
        gewesen: `collect_subtree` kennt den Unterschied zwischen angebautem Teil und eingelegtem
        Gegenstand nicht, und ohne diese Grenze schlug eine Waffe im Waffenkoffer dem Koffer ihre
        Groesse zu (Rifle case, 4x2 auf 6x4). Diese Grenze zieht `_footprint_for_item` inzwischen
        selbst, also braucht es hier keine zweite.
        """
        grund = self._footprint_for_item(item_id)
        if grund is None:
            return None
        daten = item_data(self.manager.get_item(item_id))
        return (grund[1], grund[0]) if daten.get("BaseComponent_rotated") else grund

    def _container_cells_for(self, container_id: str):
        item = self.manager.get_item(container_id)
        if item is None:
            return None
        meta = self.game_item_meta_by_template_id.get(
            str(item.get("TemplateId") or "").lower(), {}
        )
        return container_cells(meta.get("container"))

    def _container_regions_for(self, container_id: str):
        """Die Faecher eines Behaelters, oder None wenn seine Form nicht modelliert ist.

        Getrennt von `_container_cells_for`, weil die beiden verschiedene Fragen beantworten:
        wie viel Platz ist da (Zellen zaehlen) und wo darf etwas hin (Faecher). Beim CARTER
        sind das 20 Zellen in fuenf Fachern, von denen das groesste 2x3 ist.
        """
        item = self.manager.get_item(container_id)
        if item is None:
            return None
        meta = self.game_item_meta_by_template_id.get(
            str(item.get("TemplateId") or "").lower(), {}
        )
        return container_regions(meta.get("container"))

    def _placement_in(self, container_id: str, width: int, height: int):
        """(I, J, rotated) for a free spot, or None when the container has no room.

        **What is taken is what is drawn, and nothing beyond it.** Two answers to "but does a
        neighbour need room to grow into?" have stood here and both are gone:
        `_own_placed_footprint` on 2026-09-10, `_keep_out_cells` on 2026-09-11. Each was built
        on a weapon that came back as mail, and each of those weapons is explained by the shape
        defects fixed on 2026-09-10 - an editor that wrote a base size onto every spawned weapon
        mails it whatever the spacing.

        Settled by two game starts. On 2026-09-11, thirteen 1x1 parts were laid into cells the
        editor was holding clear - around fully fitted weapons and around weapons carrying only
        their required parts, one of them a cell *beyond* the ceiling, the exact cell the old
        note claimed the game blocked. **All thirteen stayed, the mail counter never moved**, and
        92 weapons already in the save served as controls. The game's own tab counter agrees: it
        matches the drawn occupancy cell for cell (217/203/205/236), which it could not if the
        game held anything clear around a weapon.
        """
        cells = self._container_cells_for(container_id)
        if not cells:
            return None
        occupied = self.manager.occupied_cells(container_id, self._footprint_for_item)
        return find_placement(cells, occupied, width, height,
                              self._container_regions_for(container_id))

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

    def _placement_targets(self, need: tuple[int, int] | None = None) -> list[tuple[str, str]]:
        """(container id, label) for the containers an item can be placed into.

        The warehouse tabs plus the containers carried on the character - a backpack, a rig,
        a safe box. Deliberately nothing else: a weapon case in a tab is left alone, which
        also keeps the editor out of the one place where an item's real footprint is least
        certain. Anything whose grid the report does not describe is left out rather than
        guessed at - weapon attachment points have their own item filters, and the shelter
        root is not an item at all, so it has no template to read a size from.

        A container with no free cell is left out too. Offering one is offering a dead end -
        the choice is accepted and then answered with "no space", which reads like a bug.

        **`need` marks, it does not remove.** Spawning an assembled EMERKIT SMG offered
        "Tab 1 - 40 of 240 cells free" and then refused, because the weapon needs 6x3
        *contiguous* cells and that tab has no such rectangle in either orientation - so the
        list has to say something about the footprint. The first version said it by dropping
        those containers, and that was wrong twice over: it takes away the overview, and it
        hides destinations on the strength of a **reservation** that is itself an upper bound
        with an open question in it. If the reservation is too
        cautious, removing the entry turns a guess into a verdict. A label leaves the choice
        where it belongs and still answers the question before the choice is made.

        The advertised count is simply the cells no item covers. It used to subtract a margin
        around neighbours that could still grow, which is what turned 15 usable cells into an
        advertised 40 - but that margin is gone since 2026-09-11 (see `_placement_in`), so the
        two numbers agree again by having nothing between them.
        """
        t = TRANSLATIONS[self.current_lang]
        targets: list[tuple[str, str]] = []

        def free_cells(container_id: str):
            """(free, total, takes_it) or None when the container is no target at all."""
            if self._is_bookkeeping_container(container_id):
                return None
            cells = self._container_cells_for(container_id)
            if not cells:
                return None
            occupied = self.manager.occupied_cells(container_id, self._footprint_for_item)
            blocked = {c for c in occupied if c in cells}
            free = len(cells) - len(blocked)
            if free <= 0:
                return None
            takes = (not need
                     or find_placement(cells, blocked, need[0], need[1],
                                       self._container_regions_for(container_id)) is not None)
            return (free, len(cells), takes)

        def beschriften(label: str, takes: bool) -> str:
            return label if takes else label + t["target_no_room"]

        for idx, tab_id in enumerate(self.manager.get_inventory_tabs(), 1):
            room = free_cells(tab_id)
            if room is None:
                continue
            targets.append((tab_id, beschriften(t["target_tab"].format(
                idx=idx, free=room[0], total=room[1]), room[2])))

        for item_id in self.manager.get_character_items():
            room = free_cells(item_id)
            if room is None:
                continue
            name = self._template_name_for_item_id(item_id) or t["target_container"]
            targets.append((item_id, beschriften(t["target_carried"].format(
                name=name, free=room[0], total=room[1]), room[2])))

        return targets

    def _target_label(self, target: str) -> str:
        """Ein lesbarer Name fuer ein Platzierungsziel, auch nachtraeglich.

        **`_placement_targets` laesst volle Behaelter weg** - einen ohne freie Zelle
        anzubieten waere eine Sackgasse. Genau das macht die Liste aber als Nachschlagewerk
        unbrauchbar, sobald man selbst hineingeraeumt hat: nach vier verschobenen
        Gegenstaenden ist der Reiter voll, faellt aus der Liste, und die Meldung nennt
        statt "Reiter 4" die nackte GUID. Genau so ist es gemeldet worden.

        Deshalb zuerst die Liste, und wenn der Eintrag fehlt, der Name aus dem Bestand -
        die Reiternummer aus ihrer Reihenfolge, ein getragener Behaelter aus seiner Vorlage.
        """
        t = TRANSLATIONS[self.current_lang]
        if target == "inbox":
            return t["target_inbox"]
        if target == "same":
            return t["target_same_container"]
        for cid, label in self._placement_targets():
            if cid == target:
                return label
        for idx, tab_id in enumerate(self.manager.get_inventory_tabs(), 1):
            if tab_id == target:
                return t["target_tab"].format(idx=idx, free=0, total=0)
        return (self._template_name_for_item_id(target)
                or t["target_container"])

    #: Untergrenze und Obergrenze der Zielliste, in Zeichenbreiten. Die Obergrenze haelt den
    #: Dialog unter der Mindestbreite des Hauptfensters von 1140px - bei 13px je Einheit sind
    #: das 1040px. Was dann noch ueberhaengt, ist ein Vorlagenname und keine Warnung.
    PLATZ_LISTE_MIN, PLATZ_LISTE_MAX = 54, 80

    def _placement_combo_width(self, labels: list[str]) -> int:
        """Wie breit die Zielliste sein muss, damit ihr laengster Eintrag hineinpasst.

        **Eine feste Zahl kann hier nicht stimmen.** Mit den urspruenglichen 54 Einheiten -
        702px auf diesem Schirm - wurde in *allen drei* Sprachen abgeschnitten: englisch um
        86px, deutsch um 231, russisch um 311. Weg war dabei ausgerechnet das angehaengte
        "kein Platz", und uebrig blieb eine Zeile, die sich wie ein gueltiges Ziel liest.
        Gemeldet aus der Nutzung, und zwar an genau dieser Zeile.

        Die Namen kommen aus den Spieldaten und aus drei Sprachen, koennen sich also mit einem
        Spiel-Update aendern - deshalb gemessen statt gesetzt. Eigene Methode, damit
        `tests/test_placement_gui.py` das Ergebnis pruefen kann, statt die Formel nachzubauen
        und sich selbst zu messen.
        """
        schrift = tkfont.nametofont("TkDefaultFont")
        einheit = max(1, schrift.measure("0"))
        noetig = max((schrift.measure(label) for label in labels), default=0)
        return max(self.PLATZ_LISTE_MIN,
                   min(noetig // einheit + 2, self.PLATZ_LISTE_MAX))

    def _ask_placement_target(
        self,
        title: str,
        same_container_id: str | None = None,
        allow_inbox: bool = True,
        need: tuple[int, int] | None = None,
    ):
        """Lets the user pick where a new item goes. Returns a container id, the string
        "same" for the original's own container, or None when cancelled.

        A Combobox rather than a Listbox on purpose: a Listbox alongside entry fields
        silently loses its selection unless exportselection is off, and there is no reason
        to walk into that here.

        `allow_inbox=False` is for an item that arrives with parts already fitted. The inbox
        works by writing no position at all and letting the game deliver the item as mail,
        and **the game delivers the parts one by one** - measured in play on 2026-09-09 by
        mailing a complete weapon: it arrived as a loose pile, not as the weapon. So an
        assembled item put in the inbox stops being assembled, which is the whole reason the
        preset spawner does not offer it.
        """
        t = TRANSLATIONS[self.current_lang]
        targets = self._placement_targets(need)
        options: list[tuple[str, str]] = []
        if same_container_id:
            options.append(("same", t["target_same_container"]))
        options.extend(targets)
        # Always available, and the only option left once everything is full: an item with no
        # grid position cannot be placed by the game, so it arrives as mail instead.
        if allow_inbox:
            options.append(("inbox", t["target_inbox"]))
        if not options:
            messagebox.showwarning(title, t["msg_place_no_targets"], parent=self.root)
            return None

        win = self._new_dialog(title)
        chosen: list[str | None] = [None]

        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=t["msg_place_prompt"]).pack(anchor="w", pady=(0, 6))
        # The size the choice is about, right where the choice is made. Without it the only
        # way to know why a container is marked "no room" is to remember the catalog row.
        if need:
            ttk.Label(body, text=t["place_size"].format(w=need[0], h=need[1]),
                      style="Hint.TLabel").pack(anchor="w", pady=(0, 6))
        beschriftungen = [label for _cid, label in options]
        combo = ttk.Combobox(body, state="readonly",
                             width=self._placement_combo_width(beschriftungen),
                             values=beschriftungen)
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
        elif selected_widget == self.tab_crafting:
            # Rebuilt on opening rather than after every item edit: what changes underneath it
            # is what the store holds, and walking every item on each repair is wasted work.
            self._refresh_crafting_tree()
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
        elif selected_widget == self.tab_raw_json:
            if getattr(self, "_json_dirty", True):
                self._refresh_json_tab()

    def _on_scope_changed(self, _event: tk.Event) -> None:
        self._populate_scope_view()

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
        only_new = bool(self.catalog_only_new_var.get())
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
            if only_new and template_id not in self.new_template_ids:
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
            # A missing price or weight stays blank rather than becoming 0. 485 templates
            # have no price at all - 21 of them carry an empty price list, which is the
            # game's way of saying "not for sale" - and zero credits would be a claim the
            # data does not make.
            price = row.get("price")
            price_text = (
                f"{int(price):,}".replace(",", " ")
                if isinstance(price, (int, float)) and not isinstance(price, bool)
                else "-"
            )
            mass = row.get("mass")
            mass_text = (
                _trim_float(float(mass))
                if isinstance(mass, (int, float)) and not isinstance(mass, bool)
                else "-"
            )
            # **Magenta wins by being the only tag, not by Tk's tag precedence.** Which of
            # two tags decides a colour is not something this file should have to know -
            # it depends on the order they were configured in and is not part of the
            # documented Treeview interface. A template that is both new and a firearm is
            # shown as new: that is the state the user just asked to be shown.
            if template_id in self.new_template_ids:
                row_tags: tuple[str, ...] = ("new_template",)
            else:
                cat_tag = category_tag_for_cat_id(category_id, subcategory_id)
                row_tags = (cat_tag,) if cat_tag else ()
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
                    price_text,
                    mass_text,
                ),
                tags=row_tags,
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

    def _selected_catalog_templates(self) -> list[tuple[str, str]] | None:
        """Jede gewaehlte Katalogzeile als (Template-Id, Anzeigename).

        Die Einzahl-Fassung darueber liest `selection()[0]` und ist damit blind fuer alles,
        was der Nutzer per Strg+Klick dazugewaehlt hat - genau der gemeldete Fall, in dem
        nur ein Gegenstand gespawnt wurde. Zeilen ohne brauchbare Template-Id werden
        uebersprungen statt den ganzen Vorgang abzubrechen; gemeldet wird erst, wenn keine
        einzige uebrig bleibt.
        """
        t = TRANSLATIONS[self.current_lang]
        selected = self.catalog_tree.selection()
        if not selected:
            messagebox.showwarning(t["tab_catalog"], t["msg_no_item_selected"], parent=self.root)
            return None
        vorlagen: list[tuple[str, str]] = []
        for row in selected:
            values = self.catalog_tree.item(row, "values")
            if not values or len(values) < 2:
                continue
            template_id = str(values[1]).strip().lower()
            if template_id:
                vorlagen.append((template_id, str(values[0])))
        if not vorlagen:
            messagebox.showerror(t["tab_catalog"], t["msg_catalog_row_invalid"], parent=self.root)
            return None
        return vorlagen

    def _add_selected_catalog_item_to_inventory(self) -> None:
        """One dialog for spawning, rather than a chain of prompts.

        This used to be two menu entries: a plain one asking count and destination in two
        consecutive dialogs, and a "..." one asking the same in a single window plus a
        starting condition. Measured against the catalog, the plain path offered nothing the
        other did not - the extra fields only apply to some 590 of the ~1600 templates, and for the
        other 1009 the two were the same two questions in a different number of windows.
        So there is one entry now. The dialog shows only the fields a template can use.
        """
        t = TRANSLATIONS[self.current_lang]
        vorlagen = self._selected_catalog_templates()
        if not vorlagen:
            return

        # **Der Dialog zeigt nur, was auf jede gewaehlte Vorlage passt.** Stapelgroesse und
        # Startzustand gibt es nicht ueberall - eine Zahl, die bei zwei von drei Vorlagen
        # verpufft, waere eine Einstellung, die luegt. Bei einer einzigen Vorlage aendert
        # das nichts, dort tragen beide Felder wie bisher.
        kapazitaeten = [self._stack_capacity_for_template(tid) for tid, _n in vorlagen]
        capacity = min(kapazitaeten) if all(k for k in kapazitaeten) else None

        zustaende = [self._condition_ceiling_for_template(tid) for tid, _n in vorlagen]
        felder = {f for f, _m in zustaende}
        if len(felder) == 1 and all(f for f, _m in zustaende):
            condition_field = zustaende[0][0]
            condition_max = min(m for _f, m in zustaende if m is not None)
        else:
            condition_field, condition_max = None, None

        need = self._catalog_spawn_need([tid for tid, _n in vorlagen])

        result = self._ask_amount_and_target(
            title=t["msg_add_item_title"],
            count_label=t["custom_count"],
            # Stackables default to one full stack, which is what you almost always want.
            count_default=1,
            capacity=capacity,
            condition_max=condition_max,
            condition_field=condition_field,
            need=need,
        )
        if result is None:
            return
        copy_count, units, condition, target = result

        mehrere = len(vorlagen) > 1
        gesamt = 0
        gescheitert: list[str] = []
        for template_id, name in vorlagen:
            n = self._add_catalog_template(
                template_id, [units] * copy_count, target,
                condition=None if condition is None else (condition_field, condition),
                quiet=mehrere,
            ) or 0
            gesamt += n
            if mehrere and n < copy_count:
                gescheitert.append((template_id, name))

        if not mehrere:
            return

        # Einmal melden, mit den Namen der Vorlagen, die keinen Platz fanden - eine blosse
        # Zahl liesse offen, welche der drei fehlt.
        target_label = self._target_label(target)
        if gescheitert:
            # **Das Postfach ist der Ausweg, aber nicht fuer alles.** Gemessen im Spiel am
            # 09.09.2026: eine komplette Waffe kommt dort als loser Haufen an, Teil fuer
            # Teil. Wer Pflichtteile mitbringt, wuerde also zerlegt geliefert - genau
            # deshalb bietet der Preset-Spawner das Postfach gar nicht erst an. Angeboten
            # wird es hier nur fuer die Vorlagen, bei denen nichts zerfaellt.
            zerfaellt, ganz = [], []
            for template_id, name in gescheitert:
                if any(s.get("required") for s in self._mod_slots_of(template_id)):
                    zerfaellt.append((template_id, name))
                else:
                    ganz.append((template_id, name))

            hinweis = t["msg_place_partial"].format(
                placed=gesamt, wanted=copy_count * len(vorlagen), target=target_label)
            if zerfaellt:
                hinweis += chr(10) + chr(10) + t["msg_inbox_needs_parts"].format(
                    names=", ".join(n for _i, n in zerfaellt))

            if ganz and messagebox.askyesno(
                    t["tab_catalog"],
                    hinweis + chr(10) + chr(10) + t["msg_inbox_offer"].format(
                        names=", ".join(n for _i, n in ganz)),
                    parent=self.root):
                for template_id, _name in ganz:
                    gesamt += self._add_catalog_template(
                        template_id, [units] * copy_count, "inbox",
                        condition=None if condition is None else (condition_field, condition),
                        quiet=True,
                    ) or 0
            else:
                messagebox.showinfo(t["tab_catalog"], hinweis, parent=self.root)

        self._refresh_scope_keeping_open()
        self._mark_pending_changes(f"Added {gesamt} catalog item(s) (not saved yet)")

    def _condition_ceiling_for_template(
        self, template_id: str | None
    ) -> tuple[str | None, float | None]:
        """Which condition a *newly spawned* item of this template could carry.

        The instance-level `_condition_fields_of` cannot answer this: a spawned item has no
        condition field yet, and its absence is exactly what pristine means. So the question
        has to be put to the template. Charges come with a `max_durability`; the 0-4 wear
        scale has no per-template ceiling and is flagged by `has_wear_condition`.
        """
        meta = self.game_item_meta_by_template_id.get(
            str(template_id or "").strip().lower(), {})
        ceiling = meta.get("max_durability")
        if isinstance(ceiling, (int, float)) and ceiling > 0:
            return "DurabilityComponent_durability", float(ceiling)
        if meta.get("has_wear_condition"):
            return "Condition_d", 4.0
        return None, None

    def _add_catalog_template(
        self,
        template_id: str,
        quantities: list[int | None],
        parent_id: str,
        condition: tuple[str | None, float] | None = None,
        quiet: bool = False,
    ) -> int:
        """Spawns one item per entry in `quantities`, each carrying that stack size.

        A list rather than a count, because the two entry points mean different things by
        "how many": the plain one takes a total number of units and splits it into stacks,
        the "..." one takes a number of stacks and a size for each.

        `condition` writes a starting wear value. Left out, the item is spawned pristine -
        which is no field at all, the way the game stores an untouched item.
        """
        t = TRANSLATIONS[self.current_lang]
        if not quantities:
            return

        meta = self.game_item_meta_by_template_id.get(template_id, {})

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
                return 0
            inbox_host = tabs[0]

        footprint = self._spawn_footprint_for_template(template_id)
        if footprint is None:
            # Without a footprint there is no way to know what the item covers, and a wrong
            # guess is what sends it to the mailbox.
            messagebox.showerror(t["tab_catalog"], t["msg_place_no_targets"],
                                 parent=self.root)
            return 0
        item_width, item_height = footprint

        # Each spawned item takes cells away from the next one, so the free spot is looked
        # up again per item rather than once up front.
        eigene_breite, eigene_hoehe = self._size_to_record(template_id)

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
                width=eigene_breite,
                height=eigene_hoehe,
                quantity=quantity,
                position=(i, j),
            )
            # A weapon the game will not accept bare gets the parts its required slots
            # demand - measured in play, a Gaston without its slide goes to the mailbox.
            self._fill_required_slots(str(created["Id"]))
            if rotated or condition:
                inner = writable_item_data(created)
                if rotated:
                    inner["BaseComponent_rotated"] = True
                if condition:
                    field, value = condition
                    inner[field] = float(value)
                    # The ceiling a repair kit can restore to. Left at the template maximum
                    # it would let the item be repaired past what it was spawned at, which
                    # is fine - but the field only exists once durability does.
                    if field == "DurabilityComponent_durability":
                        ceiling = meta.get("max_durability")
                        if isinstance(ceiling, (int, float)) and ceiling > 0:
                            inner["DurabilityComponent_md"] = float(ceiling)
            return True

        added = 0
        wanted = len(quantities)
        for quantity in quantities:
            if not place_one(quantity):
                break
            added += 1

        # **`quiet` gehoert dem Aufrufer, der mehrere Vorlagen hintereinander spawnt.**
        # Sonst meldet jede einzelne fuer sich, und drei gewaehlte Vorlagen ergeben bis zu
        # drei Fenster, die man wegklicken muss - nach einem Dialog, der einmal gefragt hat.
        # Die Zahl kommt stattdessen zurueck, und gemeldet wird einmal am Ende.
        if quiet:
            return added

        if not added:
            messagebox.showwarning(
                t["tab_catalog"],
                t["msg_place_no_space"].format(
                    target=target_label, width=item_width, height=item_height),
                parent=self.root,
            )
            return 0
        if added < wanted:
            messagebox.showinfo(
                t["tab_catalog"],
                t["msg_place_partial"].format(
                    placed=added, wanted=wanted, target=target_label),
                parent=self.root,
            )

        self._refresh_scope_keeping_open()
        self._mark_pending_changes(f"Added {added} catalog item(s) (not saved yet)")
        return added

    # --- Assembled items from the game's own presets -----------------------------------
    # `item_presets` is where the game keeps a weapon the way it ships it: the receiver, the
    # barrel, the magazine, each in its slot. Spawning one is the catalog spawner plus the
    # attachment logic - which is why this sits below both.

    def _presets_for_template(self, template_id: str) -> list[dict]:
        """The game's factory configurations for one template, `_Default` first.

        Only 53 templates have any, all of them firearms, and 35 weapons share those 53 - a
        `_Default` plus one or two `_MK*` variants.
        """
        key = str(template_id or "").strip().lower()
        if not key:
            return []
        rows = [row for row in (self.presets_meta or []) if row.get("root") == key]
        rows.sort(key=lambda row: (
            "default" not in str(row.get("alias") or "").lower(),
            str(row.get("alias") or "").lower(),
        ))
        return rows

    def _preset_label(self, preset: dict) -> str:
        """A preset's alias without the weapon's own name, which the row already carries."""
        alias = str(preset.get("alias") or "").strip()
        name = self._template_name_for_template_id(preset.get("root")) or ""
        trimmed = alias.replace(" ", "")
        compact = name.replace(" ", "").replace("-", "")
        if compact and trimmed.lower().startswith(compact.lower()):
            trimmed = trimmed[len(compact):].lstrip("_-") or alias
        return trimmed.replace("_", " ").strip() or alias

    def _free_slot_for_part(self, host_id: str, part_template_id: str) -> int | None:
        """The first slot on this host that permits the part and is not taken yet.

        A preset can name two parts a single slot type would accept, so the search has to look
        at what is already fitted rather than at the template alone.
        """
        wanted = str(part_template_id or "").strip().lower()
        host_template = str((self.manager.get_item(host_id) or {}).get("TemplateId") or "")
        for index, slot in enumerate(self._mod_slots_of(host_template)):
            allows = {str(a).strip().lower() for a in (slot.get("allows") or [])}
            if wanted not in allows:
                continue
            if self.manager.slot_occupant(host_id, index) is None:
                return index
        return None

    def _preset_grown_size(self, preset: dict) -> tuple[int, int] | None:
        """What a preset's weapon will measure once its parts are on it, as an upper bound.

        `resize` is the game's own statement of how much a part enlarges its host - a Gaston 17
        suppressor is `{"width": 1}`, a drum magazine `{"height": 1}` - and summing it over the
        fitted parts is the only expression of growth the data offers. It **overshoots**: across
        a real save it predicts 139 of 162 grown items exactly and is too large for the rest, so
        it is a ceiling on the growth and not the growth itself.

        **Uncapped on purpose.** For 8 of the 53 presets the sum lands above the root's own
        `MaxSize` (LM39, M420, MKP, PRO90 MK1 and MK2, Ronnie B4, SVS twice), and saying so is
        this function's other job: `_preset_outgrows_its_ceiling` is what warns that 17 of the
        53 configurations reach or pass the standard size. The capping belongs to
        `_preset_reservation`, because reserving room is a different question from describing
        what the parts add up to.
        """
        wurzel = str(preset.get("root") or "").strip().lower()
        base = self._footprint_for_template(wurzel)
        if base is None:
            return None
        width, height = base
        for part in preset.get("parts") or []:
            meta = self.game_item_meta_by_template_id.get(
                str(part.get("template_id") or "").strip().lower(), {})
            grow = meta.get("resize")
            if isinstance(grow, dict):
                width += int(grow.get("width") or 0)
                height += int(grow.get("height") or 0)

        return width, height

    def _preset_counts(self) -> tuple[int, int]:
        """Wie viele Bausaetze es gibt und wie viele davon ueber ihre Decke wachsen.

        Beide Zahlen standen als Prosa in den Texten und veralteten dort still: sie haengen am
        Katalog des Spielers, nicht am Editor. Ohne Bericht - frischer Klon, nie extrahiert -
        gaebe `len(self.presets_meta)` eine ehrliche, aber nutzlose 0 aus; dann sind
        `PRESET_COUNT_SHIPPED`/`PRESET_OUTGROWN_SHIPPED` des getesteten Builds die bessere
        Auskunft.

        Der Durchlauf ueber `_preset_outgrows_its_ceiling` kostet einen Gang durch rund 50
        Zeilen und laeuft nur, wenn ein Text die Zahl braucht - beim Sprachwechsel und beim
        Oeffnen des Bausatz-Dialogs, nicht im Zeichentakt.
        """
        rows = self.presets_meta or []
        if not rows:
            return PRESET_COUNT_SHIPPED, PRESET_OUTGROWN_SHIPPED
        return len(rows), sum(1 for row in rows if self._preset_outgrows_its_ceiling(row))

    def _preset_outgrows_its_ceiling(self, preset: dict) -> bool:
        """True when the finished weapon would be at or past what its template says it can grow to.

        **The game refuses to place such an item and hands it over as mail, in pieces** -
        measured in play on 2026-07-30 with `Gaston17_MK3`, whose parts add exactly its own
        3x2 ceiling. The data agrees that this is a property of the configuration rather than of
        the spot: **no item in a real save sits at its own `MaxSize`** - 0 of 19 that carry both
        numbers - and 17 of the 53 presets predict a size at or above it.

        So this is not a placement problem the editor can solve by looking harder for a spot,
        and the dialog says so before spawning instead of letting it fail silently.

        **Over on an axis, or level on both** - 17 of the 53. Touching the ceiling on only one
        axis is deliberately not flagged, and that line is where the evidence runs out: the
        prediction overshoots (see `_preset_grown_size`), so a single axis reading "level" may
        really be under, and the configuration that failed had *both* axes level. Flagging one
        axis would warn on 33 of 53, including variants of the 1A4M whose plain version spawned
        cleanly in play. Warning about two thirds of the list on a hunch is its own kind of lie.
        """
        grown = self._preset_grown_size(preset)
        meta = self.game_item_meta_by_template_id.get(
            str(preset.get("root") or "").strip().lower(), {})
        ceiling = (meta.get("max_width"), meta.get("max_height"))
        if grown is None or not all(isinstance(value, int) for value in ceiling):
            return False
        if grown[0] > ceiling[0] or grown[1] > ceiling[1]:
            return True
        return grown[0] == ceiling[0] and grown[1] == ceiling[1]

    def _assembled_reservation(self, template_id: str) -> tuple[int, int] | None:
        """How much room to keep free for a weapon that will arrive with parts on it.

        **`MaxSize`, not the template size** - and this is the one place that reads it, against
        the rule everywhere else. The first version reserved the template size and the game put
        every spawned weapon in the mailbox, which is what it does with an item it cannot place:
        it computes the assembled size itself and found the neighbouring cells taken.

        That size cannot be computed here. Measured across a real save's 26 hosts that carry
        one: it is **deterministic per (weapon, parts) combination** - 24 combinations, none
        contradicting another - so the game does derive it, but no simple rule reproduces it.
        The template size matches 7 of 26, the bounding box of the parts 7, and "base width plus
        the parts' widths" **0**. A 1A4M assembled is 3x1 against a 2x1 template, a Herstal SH
        4x1, a Neckar SR93 5x1 against a 1x1 template.

        `MaxSize` is above every observed value, so it is a safe ceiling even though it is not
        the answer, because in play a bare Gaston blocked one
        cell more than its own ceiling. Nothing false is written into the save; this is only how
        much space the search keeps clear.
        """
        meta = self.game_item_meta_by_template_id.get(
            str(template_id or "").strip().lower(), {})
        width, height = meta.get("max_width"), meta.get("max_height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return width, height
        # One preset root (template 6x2) carries no MaxSize at all. Its own size is then the
        # best statement available.
        return self._footprint_for_template(template_id)

    def _preset_reservation(self, preset: dict) -> tuple[int, int] | None:
        """Der zusammenhaengende Platz, den ein zusammengebauter Bausatz braucht.

        **Das Groesste aus Fertiggroesse und `MaxSize`** - also bewusst zu viel, und das ist
        seit dem 10.09.2026 eine Messung und keine Vorsicht.

        Die Geschichte in drei Schritten, weil die mittlere Fassung ueberzeugend aussah und
        falsch war:

        1. Anfangs stand hier `MaxSize`, die Groesse mit allen Steckplaetzen belegt.
        2. Am 11.08.2026 auf die **Fertiggroesse** verkleinert, und dafuer gab es Zahlen: ueber
           die 34 zusammengebauten Waffen, die das Spiel selbst gebaut hat, ist keine hoeher als
           2 Zellen oder breiter als 5, waehrend `MaxSize` 6x3 bis 7x4 verlangte - vier- bis
           neunmal die Flaeche. Ein 1A4M, das das Spiel mit 3x1 fuehrt, bekam 28 Zellen.
        3. Am 10.09.2026 schien das Spiel es zu widerlegen. Ein **DVS_MK3, fertig 4x1**, wurde
           in eine Luecke von genau 4x1 gespawnt und kam **ins Postfach** - zerlegt, die Teile
           lagen einzeln im Reiter. Also zurueck auf `max(Fertiggroesse, MaxSize)`.
        4. Am 11.09.2026 stellte sich heraus, dass Schritt 3 die falsche Ursache benannt hatte.
           Am selben 10.09. kam heraus, dass der Editor damals die **Basisgroesse** an jede
           gespawnte Waffe schrieb - eine Form, die das Spiel nie erzeugt, und die **jede** so
           gespawnte Waffe ins Postfach schickt. Die DVS_MK3 war also doppelt erklaert, und die
           falsche Erklaerung kostete in jedem Reiter Platz.

        **Der Versuch, der es entschieden hat** (11.09.2026, ein Spielstart): drei Bausaetze in
        eine Luecke von genau ihrer Fertiggroesse gesetzt - darunter dieselbe DVS_MK3 -, und in
        die Zellen, die `MaxSize` freigehalten haette, sechs 1x1-Plastikteile gelegt.

            DVS_MK3      fertig 4x1, MaxSize 6x2, 3 Teile in der Sperrflaeche -> alles bleibt
            1A4M         fertig 5x2, MaxSize 6x3, 2 Teile in der Sperrflaeche -> alles bleibt
            Neckar SR93  fertig 5x1, MaxSize 6x2, 1 Teil  in der Sperrflaeche -> alles bleibt

        Nichts hat sich bewegt, der Postfachzaehler blieb bei 63, und die 15 grosszuegig
        gesetzten Waffen vom Vortag - 15 Kontrollen - lagen unveraendert da. **Die Fertiggroesse
        reicht.**

        Sie ist eine Obergrenze auf das Wachstum und keine knappe Zahl: `_preset_grown_size`
        ueberschaetzt (139 von 162 gewachsenen Gegenstaenden genau, den Rest zu gross), und
        `_footprint_for_item` deckelt danach noch bei `MaxSize`. Reserviert wird also nie
        weniger, als die Waffe hinterher belegt.

        **Was dabei auffiel und einen Tag spaeter erledigt war.** Vier der sechs Plastikteile
        lagen in Zellen, die `_keep_out_cells` sperrte - das Spiel hat auch die akzeptiert. Der
        Nachschlag mit knapp bestueckten Waffen bestaetigte es, und die Sperrflaeche ist seither
        weg.
        """
        fertig = self._preset_grown_size(preset)
        if fertig is not None:
            return fertig
        return self._assembled_reservation(str(preset.get("root") or ""))

    def _fill_required_slots(self, item_id: str, _depth: int = 0) -> int:
        """Puts the parts a template's **required** slots demand into a freshly created item.

        A weapon spawned bare is not a thing the game accepts. Measured in play on 2026-07-30:
        an assembled Gaston 17 stays where it is put, while the same pistol spawned with no parts
        lands in the mailbox even with room to spare - and the data says why. Its slide slot
        carries `IsRequiredToEquip`, so a Gaston without a slide is missing something the game
        insists on. **75 templates have such a slot, and 52 of the 53 preset roots are among
        them**, which is exactly why the assembled presets work and a bare spawn does not.

        Recursive, because the requirement chains: a Gaston needs a slide, and the slide needs a
        barrel. Every required slot in the report names a `default_template_id` - 0 of them do
        not - so what to put in is never a guess. Depth is capped anyway; the data is not
        trusted to be free of a loop just because it currently is.

        Returns how many parts were created. Slots that are already filled are left alone, which
        is what makes it safe to run over a preset that has done most of the work already.
        """
        if _depth > 4:
            return 0
        item = self.manager.get_item(item_id) or {}
        created = 0
        for index, slot in enumerate(self._mod_slots_of(str(item.get("TemplateId") or ""))):
            if not slot.get("required"):
                continue
            # A fast path rather than a rule: `attach_item` refuses an occupied slot anyway and
            # the part created for it is deleted again, so no test can tell the difference. It
            # is here to skip that churn when running over a preset that filled most slots.
            if self.manager.slot_occupant(str(item_id), index) is not None:
                continue
            default = str(slot.get("default_template_id") or "").strip().lower()
            if not default:
                continue
            teil_breite, teil_hoehe = self._size_to_record(default)
            part = self.manager.add_inventory_item(
                parent_id=str(item_id),
                template_id=default,
                width=teil_breite,
                height=teil_hoehe,
            )
            if not self.manager.attach_item(str(part["Id"]), str(item_id), index):
                self.manager.delete_item(str(part["Id"]))
                continue
            created += 1 + self._fill_required_slots(str(part["Id"]), _depth + 1)
        return created

    def _spawn_preset(self, preset: dict, parent_id: str) -> tuple[str | None, int, int]:
        """Creates the whole preset. Returns (root item id, parts fitted, parts skipped).

        The root is placed like any spawned item except for how much room is kept free - see
        `_assembled_reservation`. Each part is then created inside its host and attached to the
        slot that takes it. A part whose host has no free slot for it is counted and skipped
        rather than left lying loose inside the weapon, where the game would have to deal with
        a child at a cell that is not a slot.
        """
        root_template = str(preset.get("root") or "")
        wurzel_breite, wurzel_hoehe = self._size_to_record(root_template)
        footprint = self._footprint_for_template(root_template)
        reservation = self._preset_reservation(preset)
        if footprint is None or reservation is None:
            return None, 0, 0
        spot = self._placement_in(parent_id, reservation[0], reservation[1])
        if spot is None:
            return None, 0, 0

        i, j, rotated = spot
        root = self.manager.add_inventory_item(
            parent_id=parent_id,
            template_id=root_template,
            width=wurzel_breite,
            height=wurzel_hoehe,
            position=(i, j),
        )
        self._write_rotation(root, rotated)

        # `parent` in the report is an index into the parts list, -1 for the root itself.
        ids: dict[int, str] = {-1: str(root["Id"])}
        fitted = skipped = 0
        for index, part in enumerate(preset.get("parts") or []):
            host_id = ids.get(int(part.get("parent", -1)))
            template_id = str(part.get("template_id") or "").strip().lower()
            if not host_id or not template_id:
                skipped += 1
                continue
            slot_index = self._free_slot_for_part(host_id, template_id)
            if slot_index is None:
                skipped += 1
                continue
            teil_breite, teil_hoehe = self._size_to_record(template_id)
            created = self.manager.add_inventory_item(
                parent_id=host_id,
                template_id=template_id,
                width=teil_breite,
                height=teil_hoehe,
            )
            # Already a child of its host, so this only writes the slot - and writes it the
            # way the game does, which for slot 0 means no Position at all.
            if not self.manager.attach_item(str(created["Id"]), host_id, slot_index):
                self.manager.delete_item(str(created["Id"]))
                skipped += 1
                continue
            ids[index] = str(created["Id"])
            fitted += 1

        # The preset fills the weapon's own required slots; a part it brought may still have one
        # of its own standing empty, and the game is as strict about those.
        fitted += self._fill_required_slots(str(root["Id"]))
        return str(root["Id"]), fitted, skipped

    def _spawn_preset_for_selected_catalog_row(self) -> None:
        """Spawns a catalog template as the game builds it, parts included."""
        t = TRANSLATIONS[self.current_lang]
        selection = self._selected_catalog_template()
        if not selection:
            return
        template_id = selection[0]

        presets = self._presets_for_template(template_id)
        if not presets:
            messagebox.showinfo(
                t["preset_title"],
                t["preset_none"].format(total=self._preset_counts()[0]),
                parent=self.root)
            return

        preset = presets[0]
        if len(presets) > 1:
            chosen = self._pick_preset(presets)
            if chosen is None:
                return
            preset = chosen

        if self._preset_outgrows_its_ceiling(preset):
            gesamt, ueber = self._preset_counts()
            grown = self._preset_grown_size(preset)
            meta = self.game_item_meta_by_template_id.get(str(preset.get("root") or ""), {})
            if not messagebox.askyesno(
                    t["preset_title"],
                    t["preset_outgrown"].format(
                        name=self._template_name_for_template_id(template_id) or template_id,
                        grown=f"{grown[0]}x{grown[1]}" if grown else "?",
                        ceiling=f"{meta.get('max_width')}x{meta.get('max_height')}",
                        total=gesamt, outgrown=ueber),
                    parent=self.root):
                return

        # No inbox: an assembled weapon is a subtree, and mail delivery of a subtree is
        # untested. Every other destination is a real container with a real grid.
        #
        # `need` is the reservation, not the weapon's drawn size: this is the dialog that
        # offered a tab with 40 free cells and then refused, because none of them formed the
        # 6x3 rectangle the finished weapon claims.
        target = self._ask_placement_target(
            t["preset_title"], allow_inbox=False, need=self._preset_reservation(preset))
        if not target:
            return

        root_id, fitted, skipped = self._spawn_preset(preset, target)
        if root_id is None:
            messagebox.showwarning(t["preset_title"], t["preset_no_space"], parent=self.root)
            return

        self._refresh_scope_keeping_open()
        name = self._template_name_for_template_id(template_id) or template_id
        self._mark_pending_changes(
            t["status_preset"].format(name=name, parts=fitted))
        if skipped:
            messagebox.showinfo(
                t["preset_title"], t["preset_partial"].format(skipped=skipped),
                parent=self.root)

    def _pick_preset(self, presets: list[dict]) -> dict | None:
        """Which configuration is meant, when a weapon ships more than one."""
        t = TRANSLATIONS[self.current_lang]
        win = self._new_dialog(t["preset_title"])

        ttk.Label(win, text=t["preset_prompt"], wraplength=520).pack(
            anchor="w", padx=12, pady=(12, 6))
        tree = ttk.Treeview(win, columns=("parts",), show="tree headings",
                            height=min(max(len(presets), 3), 10), selectmode="browse")
        tree.heading("#0", text=t["preset_col_variant"])
        tree.heading("parts", text=t["preset_col_parts"])
        tree.column("#0", width=self._scale_px(260), anchor="w")
        tree.column("parts", width=self._scale_px(300), anchor="w")
        for index, preset in enumerate(presets):
            parts = [
                self._template_name_for_template_id(part.get("template_id"))
                or str(part.get("template_id"))
                for part in preset.get("parts") or []
            ]
            tree.insert("", "end", iid=str(index), text=self._preset_label(preset),
                        values=(", ".join(parts),))
        tree.selection_set("0")
        tree.pack(fill="both", expand=True, padx=12)

        chosen: list[dict] = []

        def confirm() -> None:
            selection = tree.selection()
            if selection:
                chosen.append(presets[int(selection[0])])
            win.destroy()

        buttons = ttk.Frame(win)
        buttons.pack(fill="x", padx=12, pady=12)
        ttk.Button(buttons, text=t["btn_ok"], command=confirm).pack(side="right")
        ttk.Button(buttons, text=t["btn_cancel"], command=win.destroy).pack(
            side="right", padx=(0, 8))
        tree.bind("<Double-Button-1>", lambda _e: confirm())

        self._center_toplevel(win)
        win.grab_set()
        win.wait_window()
        return chosen[0] if chosen else None

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

        win = self._new_dialog(t["shop_offer_title"])
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
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            selectbackground=COLOR_ACCENT,
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
        self._search_match_cache.clear()
        self._search_haystack_cache.clear()

        scope, start_ids = self._scope_start_ids()
        query = self._search_query()
        self._insert_entries("", start_ids, query)

        if reopen_member_ids:
            for root_iid in self.tree.get_children(""):
                self._restore_open_nodes(root_iid, reopen_member_ids)

        status = f"Scope: {scope} | Save: {self.save_path}"
        if query:
            matches = sum(
                1
                for start in start_ids
                for member in self.manager.collect_subtree(start)
                if self._item_matches_search(member, query)
            )
            search_text = TRANSLATIONS[self.current_lang]["status_search"].format(
                query=self.search_var.get().strip(), count=matches,
            )
            status = f"Scope: {scope} | {search_text} | Save: {self.save_path}"
        self._set_status(status)

    def _insert_entries(self, parent_iid: str, item_ids: list[str], query: str = "") -> None:
        if query:
            item_ids = [
                item_id for item_id in item_ids
                if self._subtree_matches_search(item_id, query)
            ]
        entries = build_entries(self.manager, item_ids)
        for members in entries:
            display_text = self._render_entry_text(members)
            cat_tag = self._category_tag_for_members(members)
            iid = self.tree.insert(parent_iid, "end", text=display_text,
                                   tags=(cat_tag,) if cat_tag else ())
            self.entry_members[iid] = members

            if len(members) > 1:
                # A grouped row stands for several separate items, so it opens into them.
                # Before this the only way to reach one was the "which of the five" prompt,
                # which asked for an index into a list nobody could see.
                self.tree.insert(iid, "end", text="")
                continue

            children = self.manager.get_children(members[0])
            if not children:
                continue
            if query and not self._item_matches_search(members[0], query):
                # This row survived the filter only because something inside it matched, so
                # that branch is shown open. A lazy placeholder would hide the actual hit
                # behind a container the user has no reason to suspect.
                self._insert_entries(iid, children, query)
                self.loaded_nodes.add(iid)
                self.tree.item(iid, open=True)
            else:
                self.tree.insert(iid, "end", text="")

    def _on_tree_open(self, _event: tk.Event) -> None:
        node = self.tree.focus()
        self._ensure_node_loaded(node)

    def _ensure_node_loaded(self, node: str) -> None:
        if not node or node in self.loaded_nodes:
            return
        members = self.entry_members.get(node)
        if not members:
            return

        children_nodes = self.tree.get_children(node)
        if not children_nodes:
            return

        first_child = children_nodes[0]
        if len(children_nodes) == 1 and self.tree.item(first_child, "text") == "":
            self.tree.delete(first_child)
            if len(members) == 1:
                self._insert_entries(node, self.manager.get_children(members[0]))
            else:
                # One row per member, each standing for exactly that item - so every action
                # below works on the stack the user pointed at instead of asking for a number.
                for member in members:
                    cat_tag = self._category_tag_for_members([member])
                    child = self.tree.insert(
                        node, "end", text=self._render_entry_text([member]),
                        tags=(cat_tag,) if cat_tag else (),
                    )
                    self.entry_members[child] = [member]
            self.loaded_nodes.add(node)

    def _restore_open_nodes(self, node: str, member_ids: set[str]) -> None:
        # Keyed by the row's first member, so a grouped row that was open reopens too.
        members = self.entry_members.get(node, [])
        if members and members[0] in member_ids:
            self.tree.item(node, open=True)
            self._ensure_node_loaded(node)

        for child in self.tree.get_children(node):
            self._restore_open_nodes(child, member_ids)

    def _capture_open_member_ids(self) -> set[str]:
        open_ids: set[str] = set()
        for iid, members in self.entry_members.items():
            if members and self.tree.item(iid, "open"):
                open_ids.add(members[0])
        return open_ids

    def _refresh_scope_keeping_open(self) -> None:
        """Baut die Inventarliste neu auf und laesst offen, was offen war.

        Nach jeder Aenderung am Baum muss die Ansicht neu gefuellt werden, und ohne diesen
        Handgriff klappt dabei jeder aufgeklappte Gegenstand wieder zu - wer eine Waffe
        aufgeklappt hat, um ein Anbauteil abzunehmen, sucht sie danach von vorn.

        Stand an **19 Stellen** wortgleich daneben, mal zweizeilig ueber eine Variable
        `reopen`, mal einzeilig verschachtelt. Zwei Schreibweisen fuer denselben Handgriff
        heissen: beim naechsten Mal schreibt jemand eine dritte, oder vergisst ihn.
        """
        self._populate_scope_view(reopen_member_ids=self._capture_open_member_ids())

    def _on_tree_right_click(self, event: tk.Event) -> None:
        row = self.tree.identify_row(event.y)
        if not row:
            return
        # **Eine bestehende Mehrfachauswahl ueberlebt den Rechtsklick.** `selection_set`
        # ersetzt die Auswahl, und das hat sie hier bis jetzt jedes Mal auf eine Zeile
        # eingedampft - drei per Strg+Klick gewaehlte Zeilen wurden zu einer, und die Aktion
        # traf nur noch die angeklickte. Auf eine Zeile *ausserhalb* der Auswahl zu klicken
        # soll sie weiterhin ersetzen; das ist das Verhalten aus jedem Dateimanager.
        if row not in self.tree.selection():
            self.tree.selection_set(row)
        self.tree.focus(row)
        # **Gezaehlt werden Zeilen, nicht Gegenstaende.** Eine Gruppenzeile buendelt mehrere
        # gleiche Gegenstaende, und dafuer gibt es die Rueckfrage "welcher davon" - ein
        # gewolltes, funktionierendes Verhalten (siehe *Stack grouping*). Was fehlte, war der
        # Fall mehrerer *Zeilen*: dort gibt es keine sinnvolle Frage mehr, weil die
        # Obergrenzen auseinandergehen.
        zustand = "normal" if self._nur_eine_zeile() else "disabled"
        for index in CTX_SINGLE_ONLY:
            self.context_menu.entryconfigure(index, state=zustand)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _on_tree_select_all(self, _event: tk.Event | None = None) -> str:
        def collect_visible(parent: str = "") -> list[str]:
            items: list[str] = []
            for child in self.tree.get_children(parent):
                items.append(child)
                if self.tree.item(child, "open"):
                    items.extend(collect_visible(child))
            return items

        visible = collect_visible()
        if visible:
            self.tree.selection_set(visible)
        return "break"

    def _on_shortcut_save(self, _event: tk.Event | None = None) -> str:
        if self.has_pending_changes:
            self._apply_pending_changes()
        return "break"

    def _on_shortcut_find(self, _event: tk.Event | None = None) -> str:
        if not getattr(self, "notebook", None) or not self.notebook.select():
            return "break"
        selected = self.notebook.nametowidget(self.notebook.select())
        entry = None
        if selected == self.tab_inventory:
            entry = getattr(self, "search_entry", None)
        elif selected == self.tab_catalog:
            entry = getattr(self, "cat_search_entry", None)
        elif selected == self.tab_quests:
            entry = getattr(self, "quest_search_entry", None)
        elif selected == self.tab_crafting:
            entry = getattr(self, "craft_search_entry", None)
        elif selected == getattr(self, "tab_raw_json", None):
            entry = getattr(self, "json_search_entry", None)

        if entry:
            entry.focus_set()
            entry.selection_range(0, "end")
        return "break"

    def _on_catalog_right_click(self, event: tk.Event) -> None:
        row = self.catalog_tree.identify_row(event.y)
        if not row:
            return
        # **Eine bestehende Mehrfachauswahl ueberlebt den Rechtsklick.** `selection_set`
        # ersetzt die Auswahl, und das hat sie hier bis jetzt jedes Mal auf eine Zeile
        # eingedampft - drei per Strg+Klick gewaehlte Zeilen wurden zu einer, und die Aktion
        # traf nur noch die angeklickte. Auf eine Zeile *ausserhalb* der Auswahl zu klicken
        # soll sie weiterhin ersetzen; das ist das Verhalten aus jedem Dateimanager.
        if row not in self.catalog_tree.selection():
            self.catalog_tree.selection_set(row)
        self.catalog_tree.focus(row)
        zustand = "normal" if len(self.catalog_tree.selection()) <= 1 else "disabled"
        for index in CATALOG_SINGLE_ONLY:
            self.catalog_menu.entryconfigure(index, state=zustand)
        self.catalog_menu.tk_popup(event.x_root, event.y_root)

    # Die Felder, in denen sich zwei Gegenstaende derselben Zeile unterscheiden koennen.
    # **Die Zelle steht bewusst nicht dabei:** zwei Stueck einer Zeile liegen fast immer auf
    # verschiedenen Feldern, und wer das als Unterschied wertet, fragt wieder jedes Mal.
    STAPEL_UNTERSCHIEDE = ("Condition_d", "DurabilityComponent_durability",
                           "DurabilityComponent_md", "StackableComponent_quantity")

    def _nur_eine_zeile(self) -> bool:
        """Ob genau eine Zeile gewaehlt ist - die Regel hinter CTX_SINGLE_ONLY."""
        return len(self.tree.selection()) <= 1

    def _blockiert_bei_mehreren(self, textschluessel: str) -> bool:
        """True, wenn die Aktion wegen Mehrfachauswahl nicht laufen darf. Sagt es dabei.

        **Eine Regel, zwei Wege.** Das Kontextmenue graut diese Eintraege aus, aber das
        Tastenkuerzel geht am Menue vorbei - `Strg+I` bei fuenf Zeilen lief frueher trotzdem.
        Deshalb fragen beide dieselbe Stelle, statt die Sperre zweimal zu formulieren und
        auseinanderlaufen zu lassen.

        Gemeldet wird ueber die Statuszeile, nicht ueber ein Fenster: ein Dialog als Antwort
        auf einen Tastendruck ist zu schwer fuer "geht hier nicht".
        """
        if self._nur_eine_zeile():
            return False
        t = TRANSLATIONS[self.current_lang]
        self._set_status(t["msg_single_only"].format(action=t[textschluessel]))
        return True

    def _stack_members_differ(self, members: list[str]) -> bool:
        """Ob sich die Gegenstaende einer Zeile ueberhaupt unterscheiden.

        Gruppiert wird allein nach TemplateId, Zustand und Haltbarkeit spielen dabei keine
        Rolle - ein beschaedigtes Stueck bleibt also in der Zeile der heilen. Gemessen an
        einem echten Save: von 17 Gruppenzeilen weicht **eine** ab, und nur in der
        Stapelmenge. In den anderen 16 fragt eine Auswahl nach einem Unterschied, den es
        nicht gibt.
        """
        gesehen = set()
        for item_id in members:
            daten = item_data(self.manager.get_item(item_id))
            gesehen.add(tuple(daten.get(feld) for feld in self.STAPEL_UNTERSCHIEDE))
            if len(gesehen) > 1:
                return True
        return False

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
        """Every item behind the selected rows, in the order they appear in the tree.

        **A row is not an item and the selection is not a row.** One row can bundle several
        items (`entry_members`, see *Stack grouping*), and the user can hold Ctrl and pick
        several rows. Reading only `selection()[0]` - which this did - meant an action hit
        the first row and silently ignored the rest, which looked like "only the ones next
        to each other worked": those were members of one row, not several rows.

        Duplicates are dropped: a row and a member row below it can name the same item, and
        repairing or deleting it twice is at best wasted work.
        """
        selected = self.tree.selection()
        t = TRANSLATIONS[self.current_lang]
        if not selected:
            messagebox.showwarning(t["msg_no_selection_title"], t["msg_no_item_selected"])
            return None
        members: list[str] = []
        gesehen: set[str] = set()
        for row in selected:
            for member in self.entry_members.get(row, []):
                if member not in gesehen:
                    gesehen.add(member)
                    members.append(member)
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

    def _make_mint(self, item_ids: list[str], include_parts: bool = True) -> int:
        """Puts items back into the state the game gives a brand-new one, and counts them.

        This is **not** a repair. Repairing writes `Condition_d: 4.0`, and the game keeps
        that as "was damaged, restored" - a DORA the game shows as mint carries no condition
        data at all, while a repaired KA74 next to it sits at 4.0 and is not mint. So factory
        fresh removes the fields instead of writing into them.
        """
        return sum(len(self.manager.make_pristine(item_id, include_parts=include_parts))
                   for item_id in item_ids)

    def _apply_mint(self, item_ids: list[str], include_parts: bool = True) -> None:
        """The dialog's factory-fresh path: write, refresh, report.

        Says so out loud when there was nothing to do - an item that is already fresh looked
        exactly like a broken feature the first time this shipped.
        """
        t = TRANSLATIONS[self.current_lang]
        cleared = self._make_mint(item_ids, include_parts=include_parts)
        if not cleared:
            messagebox.showinfo(t["custom_title_repair"], t["status_mint_nothing"],
                                parent=self.root)
            self._set_status(t["status_mint_nothing"])
            return

        self._refresh_scope_keeping_open()
        self._mark_pending_changes(t["status_mint"].format(count=cleared))

    def _repair_item_id(self, item_id: str) -> None:
        item = self.manager.get_item(item_id)
        t = TRANSLATIONS[self.current_lang]
        if not item:
            messagebox.showerror(t["msg_discard_title"], t["msg_item_not_found"].format(item_id=item_id))
            return

        if not self._repair_subtree(item_id):
            self._set_status(f"Nothing to repair on item {item_id}")
            return

        self._refresh_scope_keeping_open()
        self._mark_pending_changes(f"Edited item {item_id} (not saved yet)")

    def _duplicate_members(
        self,
        members: list[str],
        copy_count: int,
        target: str | None = None,
    ) -> list[str]:
        """Copies the given items and returns the ids of the copies.

        `target` skips the placement prompt, for the caller that has already asked.
        """
        t = TRANSLATIONS[self.current_lang]

        # Where the copies go. "same" keeps each copy in its original's container, which is
        # what the action used to do - except it also kept the original's cell, so the copy
        # landed on top of it and the game moved it to the mailbox.
        if target is None:
            origin_parent = str((self.manager.get_item(members[0]) or {}).get("ParentId") or "")
            target = self._ask_placement_target(
                t["ctx_duplicate"], same_container_id=origin_parent or None,
                need=self._footprint_for_placing(members[0]))
        if not target:
            return []

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
                    footprint = self._footprint_for_placing(item_id)
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
                self._write_rotation(clone, rotated)
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
            footprint = self._footprint_for_placing(members[0]) or (1, 1)
            messagebox.showwarning(
                t["ctx_duplicate"],
                t["msg_place_no_space"].format(
                    target=target_label, width=footprint[0], height=footprint[1]),
                parent=self.root,
            )
            return []
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
            return []

        self._refresh_scope_keeping_open()
        failure_note = f", failed: {len(failures)}" if failures else ""
        mode_label = "stack items" if len(members) > 1 else "item copies"
        self._mark_pending_changes(
            f"Duplicated {mode_label}: created {len(created_ids)}{failure_note}"
        )
        return created_ids

    def _repair_selected(self) -> None:
        item_id = self._selected_item_id()
        if not item_id:
            return
        self._repair_item_id(item_id)

    def _duplicate_selected(self) -> None:
        """One copy, same container, no questions asked.

        The fast path. It used to ask for a count and then for a destination, which made it
        indistinguishable from the "..." entry beside it - two prompts either way. Anything
        other than a single copy next to the original goes through that one now.
        """
        members = self._selected_members()
        if not members:
            return
        self._duplicate_members(members, 1, target="same")

    # --- The "..." variants ---------------------------------------------------------------
    # Same actions, one dialog instead of a chain of prompts. The plain entries stay for the
    # common case; these exist for when the defaults are not what you want.

    def _duplicate_selected_custom(self) -> None:
        members = self._selected_members()
        if not members:
            return
        t = TRANSLATIONS[self.current_lang]

        capacity = self._stack_capacity_for_template(
            (self.manager.get_item(members[0]) or {}).get("TemplateId"))
        origin_parent = str((self.manager.get_item(members[0]) or {}).get("ParentId") or "")

        # No condition field here: a copy keeps whatever the original carries, and offering
        # to change it would quietly do two different things at once.
        result = self._ask_amount_and_target(
            title=t["custom_title_duplicate"],
            count_label=t["custom_count"],
            count_default=1,
            capacity=capacity,
            same_container_id=origin_parent or None,
            # A copy covers exactly what the original covers - and needs exactly as much
            # room, attachments included, which is why this asks the placing question.
            need=self._footprint_for_placing(members[0]),
        )
        if result is None:
            return
        copy_count, units, _condition, target = result

        created = self._duplicate_members(members, copy_count, target=target)
        if units is not None and created:
            # The copies only. The original keeps its own count, which is what you want when
            # duplicating a half-empty stack into full ones.
            for item_id in created:
                item = self.manager.get_item(item_id)
                if not item:
                    continue
                # Kein `writable_...`: geschrieben wird nur in ein Feld, das es schon
                # gibt, und ein Gegenstand ohne Block hat keins - er bekaeme sonst einen
                # leeren, siehe `prune_item_data`.
                inner = item_data(item)
                if "StackableComponent_quantity" in inner:
                    inner["StackableComponent_quantity"] = units
            self._refresh_scope_keeping_open()

    def _repair_selected_custom(self) -> None:
        members = self._selected_members()
        if not members:
            return
        self._open_set_condition_dialog(members[0])

    # --- Moving and splitting ---------------------------------------------------------

    def _move_selected(self) -> None:
        """Moves everything that is selected into one container, asked for once.

        This used to move a single item and ask which one when the row covered several -
        "choose index 0-4" over rows the user could not see. Half-succeeding was the reason:
        three stacks need three free spots. That is still true, but the answer is now to
        place what fits and say what did not, rather than to refuse the question.
        """
        members = self._selected_members()
        if not members:
            return
        self._move_members_interactive(members)

    def _move_members_interactive(self, members: list[str]) -> int:
        """Asks once for a destination and moves every given item there. Returns how many.

        Same shape as `_duplicate_members`, deliberately: one question, then a spot looked up
        **per item**, because each one takes cells from the next - see *Placing items*. An
        item that finds no room is counted and the run carries on, so a selection that half
        fits leaves the half that fit where the user asked for it, instead of nothing.
        """
        t = TRANSLATIONS[self.current_lang]

        beweglich = [m for m in members if not self.manager.is_structural(m)]
        if not beweglich:
            messagebox.showwarning(t["move_title"], t["move_structural"], parent=self.root)
            return 0

        # **Die Zielliste wird nach dem groessten Stueck beschriftet.** Jedes braucht seinen
        # eigenen Platz, also ist die pessimistische Box aus groesster Breite und groesster
        # Hoehe die ehrliche Auskunft - sie kann einen Behaelter als zu klein ausweisen, der
        # die kleineren noch nehmen wuerde, aber nie umgekehrt.
        flaechen = [f for f in (self._footprint_for_placing(m) for m in beweglich) if f]
        need = (max((f[0] for f in flaechen), default=1),
                max((f[1] for f in flaechen), default=1))

        target = self._ask_placement_target(t["move_title"], need=need)
        if not target:
            return 0

        bewegt = 0
        ohne_platz: list[str] = []
        fehler: list[str] = []
        for item_id in beweglich:
            origin_parent = str((self.manager.get_item(item_id) or {}).get("ParentId") or "")
            if target == "inbox":
                # Das Postfach ist kein Behaelter: der Gegenstand behaelt seinen Elternteil
                # und verliert stattdessen seine Position.
                parent_id, spot = origin_parent, (-1, -1, False)
                if not parent_id:
                    fehler.append(item_id)
                    continue
            else:
                parent_id = target
                footprint = self._footprint_for_placing(item_id)
                if footprint is None:
                    fehler.append(item_id)
                    continue
                spot = self._placement_in(parent_id, footprint[0], footprint[1])
                if spot is None:
                    ohne_platz.append(item_id)
                    continue

            i, j, rotated = spot
            moved = self.manager.move_item(item_id, parent_id, position=(i, j))
            if not moved:
                fehler.append(item_id)
                continue
            self._write_rotation(self.manager.get_item(item_id) or {}, rotated)
            bewegt += 1

        target_label = self._target_label(target)

        # **Der Fehlerfall kommt nach der Rueckfrage, nicht davor.** Wenn gar nichts passt,
        # ist das Postfach der einzige Ausweg - genau dann darf die Meldung nicht schon
        # abgebrochen haben. Ein blosser Fehler bleibt fuer den Fall, in dem es nichts
        # anzubieten gibt.
        if ohne_platz or fehler:
            # **Bei einem Stueck die alte, genauere Meldung.** "0 von 1 hat gepasst" ist die
            # Sprache einer Stapelverarbeitung und laesst weg, was man hier wissen will:
            # wie gross das Ding ist. Der Einzelfall nennt die Grundflaeche wieder, wie vor
            # dem Umbau auf mehrere Zeilen - gemeldet, weil genau diese Auskunft fehlte.
            einzeln = (len(beweglich) == 1 and len(ohne_platz) == 1)
            flaeche = self._footprint_for_placing(ohne_platz[0]) if einzeln else None
            if flaeche:
                hinweis = t["move_no_space"].format(
                    target=target_label, width=flaeche[0], height=flaeche[1])
            else:
                hinweis = t["msg_place_partial"].format(
                    placed=bewegt, wanted=len(beweglich), target=target_label)

            # **Das Postfach als Ausweg, aber nur wo nichts zerfaellt.** Gemessen im Spiel
            # am 09.09.2026: was dorthin geht, kommt Teil fuer Teil an. Ein Gegenstand mit
            # Anbauteilen wuerde also zerlegt geliefert - der wird benannt und bleibt liegen.
            zerfaellt, ganz = [], []
            for item_id in ohne_platz:
                name = self._template_name_for_item_id(item_id) or item_id
                if self.manager.children_map.get(item_id):
                    zerfaellt.append((item_id, name))
                else:
                    ganz.append((item_id, name))
            if zerfaellt:
                hinweis += chr(10) + chr(10) + t["msg_inbox_needs_parts"].format(
                    names=", ".join(n for _i, n in zerfaellt))

            nachgereicht = 0
            if ganz and messagebox.askyesno(
                    t["move_title"],
                    hinweis + chr(10) + chr(10) + t["msg_inbox_offer"].format(
                        names=", ".join(n for _i, n in ganz)),
                    parent=self.root):
                for item_id, _name in ganz:
                    eltern = str((self.manager.get_item(item_id) or {}).get("ParentId") or "")
                    if eltern and self.manager.move_item(item_id, eltern, position=(-1, -1)):
                        nachgereicht += 1
                bewegt += nachgereicht
            elif not ganz:
                messagebox.showinfo(t["move_title"], hinweis, parent=self.root)

        if not bewegt:
            if not (ohne_platz or fehler):
                messagebox.showerror(t["move_title"], t["move_failed"], parent=self.root)
            return 0

        # Einmal neu aufbauen, nicht je Gegenstand - der Baum wird sonst bei zehn
        # Gegenstaenden zehnmal verworfen und neu gefuellt.
        self._refresh_scope_keeping_open()
        self._mark_pending_changes(
            t["status_moved"].format(count=bewegt, target=target_label))
        return bewegt

    def _write_rotation(self, item: dict, rotated: bool) -> None:
        """Setzt oder loescht `BaseComponent_rotated`, ohne einen leeren Block zu hinterlassen.

        Stand dreimal wortgleich da - beim Verschieben eines Stuecks, beim Verschieben mehrerer
        und beim Aufteilen -, und alle drei legten den Block **vor** der Fallunterscheidung an.
        Beim Nicht-Drehen wurde danach nur etwas herausgenommen, was gar nicht drin war: zurueck
        blieb `{"_data": {}}`, eine Form, die das Spiel nie erzeugt und die es beim naechsten
        Laden ins Postfach fuehrt. Siehe `prune_item_data`.
        """
        if rotated:
            writable_item_data(item)["BaseComponent_rotated"] = True
        else:
            item_data(item).pop("BaseComponent_rotated", None)
            prune_item_data(item)

    def _move_item_interactive(self, item_id: str) -> bool:
        """Asks for a destination container and moves one item there.

        Returns True when something moved. Split out from `_move_selected` because taking a
        part off a weapon is the same question once the part has been named - the alternative
        was a second copy of the placement handling, which is where the interesting mistakes
        live.
        """
        t = TRANSLATIONS[self.current_lang]

        if self.manager.is_structural(item_id):
            messagebox.showwarning(t["move_title"], t["move_structural"], parent=self.root)
            return False

        origin_parent = str((self.manager.get_item(item_id) or {}).get("ParentId") or "")
        target = self._ask_placement_target(
            t["move_title"], need=self._footprint_for_placing(item_id))
        if not target:
            return False

        # The inbox is not a container: an item with no valid cell is what the game hands
        # you as mail, so it keeps its parent and loses its position instead.
        if target == "inbox":
            parent_id, spot = origin_parent, (-1, -1, False)
            if not parent_id:
                messagebox.showerror(t["move_title"], t["move_failed"], parent=self.root)
                return False
        else:
            parent_id = target
            footprint = self._footprint_for_placing(item_id)
            if footprint is None:
                messagebox.showerror(t["move_title"], t["move_failed"], parent=self.root)
                return False
            # The item's own cells are still counted as taken while the spot is searched.
            # Harmless for a move into another container, and for a move inside the same one
            # it only means the item never lands on the spot it already occupies.
            spot = self._placement_in(parent_id, footprint[0], footprint[1])
            if spot is None:
                target_label = next(
                    (label for cid, label in self._placement_targets() if cid == target),
                    target,
                )
                messagebox.showwarning(
                    t["move_title"],
                    t["move_no_space"].format(
                        target=target_label, width=footprint[0], height=footprint[1]),
                    parent=self.root,
                )
                return False

        i, j, rotated = spot
        moved = self.manager.move_item(item_id, parent_id, position=(i, j))
        if not moved:
            messagebox.showerror(t["move_title"], t["move_failed"], parent=self.root)
            return False

        item = self.manager.get_item(item_id) or {}
        self._write_rotation(item, rotated)

        target_label = t["target_inbox"] if target == "inbox" else next(
            (label for cid, label in self._placement_targets() if cid == target), target)
        self._refresh_scope_keeping_open()
        self._mark_pending_changes(
            t["status_moved"].format(count=len(moved), target=target_label))
        return True

    def _set_stack_size_selected(self) -> None:
        """Sets how many units one stack holds, without needing a free cell for it.

        The editor could raise a count before this only by duplicating stacks, and a copy
        needs somewhere to go: a real save has a tab with 21 free cells and no room for a
        2x2. Writing the number costs no space at all.

        Only an item that **already** carries `StackableComponent_quantity` is offered one.
        Adding the field to something the game never stacked would invent a stack.
        """
        if self._blockiert_bei_mehreren("ctx_stack_size"):
            return
        item_id = self._selected_item_id()
        if not item_id:
            return
        t = TRANSLATIONS[self.current_lang]

        item = self.manager.get_item(item_id)
        quantity = self._stack_quantity_of_item(item)
        if not quantity:
            messagebox.showinfo(t["stack_title"], t["stack_not_stackable"], parent=self.root)
            return

        capacity = self._stack_capacity_for_template((item or {}).get("TemplateId"))
        value = self._ask_stack_size(quantity, capacity)
        if value is None or value == quantity:
            return

        inner = writable_item_data(item)
        inner["StackableComponent_quantity"] = value
        self._refresh_scope_keeping_open()
        self._mark_pending_changes(t["status_stack_set"].format(
            name=self._template_name_for_item_id(item_id) or "?", count=value))

    def _ask_stack_size(self, current: int, capacity: int | None) -> int | None:
        """One number, refused rather than clamped when it is out of range.

        The same `Invalid.TEntry` treatment level and XP already use: silently storing
        something other than what the box shows is worse than saying no.
        """
        t = TRANSLATIONS[self.current_lang]
        top = capacity if isinstance(capacity, int) and capacity > 0 else None

        win = self._new_dialog(t["stack_title"])
        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(
            body,
            text=(t["stack_prompt"].format(current=current, max=top) if top
                  else t["stack_prompt_nomax"].format(current=current)),
            wraplength=380,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        var = tk.StringVar(value=str(top or current))
        entry = ttk.Entry(body, textvariable=var, width=12, justify="center")
        entry.pack(anchor="w")

        answer: list[int | None] = [None]

        def confirm() -> None:
            raw = var.get().strip()
            if not raw.isdigit() or int(raw) < 1 or (top is not None and int(raw) > top):
                entry.configure(style="Invalid.TEntry")
                return
            entry.configure(style="TEntry")
            answer[0] = int(raw)
            win.destroy()

        buttons = ttk.Frame(body)
        buttons.pack(anchor="e", pady=(14, 0))
        ttk.Button(buttons, text=t["btn_cancel"], command=win.destroy).pack(side="right")
        ttk.Button(buttons, text=t["btn_ok"], command=confirm).pack(side="right", padx=(0, 6))

        entry.focus_set()
        entry.select_range(0, "end")
        win.bind("<Return>", lambda _e: confirm())
        win.bind("<Escape>", lambda _e: win.destroy())
        self._center_over_root(win)
        win.grab_set()
        self.root.wait_window(win)
        return answer[0]

    def _split_selected(self) -> None:
        """Takes part of a stack off into a second stack."""
        if self._blockiert_bei_mehreren("ctx_split"):
            return
        item_id = self._selected_item_id()
        if not item_id:
            return
        t = TRANSLATIONS[self.current_lang]

        item = self.manager.get_item(item_id)
        quantity = self._stack_quantity_of_item(item)
        # One unit is stored as a stack of one in some saves and as no quantity at all in
        # others; neither can be split, and both mean the same thing to the user.
        if not quantity or quantity < 2:
            messagebox.showinfo(t["split_title"], t["split_not_stackable"], parent=self.root)
            return

        origin_parent = str((item or {}).get("ParentId") or "")
        result = self._ask_amount_and_target(
            title=t["split_title"],
            count_label=t["split_prompt"].format(quantity=quantity),
            count_default=quantity // 2,
            count_max=quantity - 1,
            capacity=None,
            same_container_id=origin_parent or None,
            hint=t["split_hint"],
            # The split-off part is the same kind of item, so it covers the same cells.
            need=self._footprint_for_placing(item_id),
        )
        if result is None:
            return
        amount, _units, _condition, target = result

        if target == "inbox":
            parent_id, spot = origin_parent, (-1, -1, False)
        else:
            parent_id = origin_parent if target == "same" else target
            footprint = self._footprint_for_placing(item_id) or (1, 1)
            spot = self._placement_in(parent_id, footprint[0], footprint[1])
            if spot is None:
                target_label = next(
                    (label for cid, label in self._placement_targets() if cid == target),
                    t["target_same_container"] if target == "same" else target,
                )
                messagebox.showwarning(
                    t["split_title"], t["split_no_space"].format(target=target_label),
                    parent=self.root)
                return

        i, j, rotated = spot
        clone = self.manager.split_stack(item_id, amount, parent_id=parent_id, position=(i, j))
        if clone is None:
            messagebox.showerror(t["split_title"], t["move_failed"], parent=self.root)
            return

        self._write_rotation(clone, rotated)

        self._refresh_scope_keeping_open()
        self._mark_pending_changes(
            t["status_split"].format(amount=amount, quantity=quantity))

    # --- Attachments ------------------------------------------------------------------
    # The item info window already answers "what fits here" and "where does this go". These
    # turn the same data into an edit: the slot a part sits in is its `Position.I`, so fitting
    # a part is a move that also names a slot.

    def _own_items_for_slot(self, host_id: str, slot: dict) -> list[str]:
        """The player's own items that a slot permits, minus the host's own subtree.

        A part already fitted to *another* weapon is deliberately included - taking a scope
        off one gun and onto the next is the same operation, and `attach_item` carries the
        dicts between origin lists on the way.
        """
        allows = {str(a).strip().lower() for a in (slot.get("allows") or [])}
        if not allows:
            return []
        forbidden = set(self.manager.collect_subtree(str(host_id)))
        found = [
            str(item.get("Id"))
            for item in self.manager.get_all_items_flat()
            if str(item.get("Id") or "") not in forbidden
            and str(item.get("TemplateId") or "").strip().lower() in allows
        ]
        found.sort(key=lambda i: ((self._template_name_for_item_id(i) or "").lower(), i))
        return found

    def _own_hosts_for(self, item_id: str) -> list[tuple[str, int, str]]:
        """(host id, slot index, slot name) for each owned item with a free slot this fits.

        The index is the slot's position in the host template's own slot list, which is what
        the save records in `Position.I`. An occupied slot is left out rather than offered and
        then refused - except where this very item is the occupant, so a part can be shown in
        the slot it already sits in.
        """
        template_id = str(
            (self.manager.get_item(item_id) or {}).get("TemplateId") or "").strip().lower()
        if not template_id:
            return []
        subtree = set(self.manager.collect_subtree(str(item_id)))
        out: list[tuple[str, int, str]] = []
        for host in self.manager.get_all_items_flat():
            host_id = str(host.get("Id") or "")
            if not host_id or host_id in subtree:
                continue
            for index, slot in enumerate(
                    self._mod_slots_of(str(host.get("TemplateId") or ""))):
                allows = {str(a).strip().lower() for a in (slot.get("allows") or [])}
                if template_id not in allows:
                    continue
                occupant = self.manager.slot_occupant(host_id, index)
                if occupant is not None and occupant != str(item_id):
                    continue
                out.append((host_id, index, self._slot_label(slot)))
        out.sort(key=lambda row: (
            (self._template_name_for_item_id(row[0]) or "").lower(), row[1]))
        return out

    def _grown_host_is_cramped(self, host_id: str, incoming: str | None = None) -> bool:
        """True when a host has no room left to grow into where it sits.

        **Confirmed in play on 2026-07-30, and not the way round I had assumed**: fitting a part
        onto a weapon that cannot grow puts *the part* in the mailbox, not the weapon. The game
        keeps the host where it is and evicts what it could not fit. So this is asked **before**
        anything is staged, and the answer decides whether the user wants to go ahead.

        `incoming` is the part about to be fitted. Its own cells are excluded, because it stops
        occupying them the moment it goes into the slot - without that, a scope lying next to the
        rifle in the same tab would raise a false alarm about itself.

        `MaxSize` is the yardstick, so this errs towards asking too often: it is a ceiling rather
        than the real assembled size (see `_assembled_reservation`). That is the acceptable
        direction - the other one loses the part to the mail.

        Returns False whenever the question cannot be asked, and **one check covers every such
        case**: `_container_cells_for` answers None for an id that is not an item at all (an
        equipped host has no parent), and None for a host that is itself fitted into something,
        because a weapon's attachment points are not a modelled grid. Guards for those two were
        written first and both turned out to be unreachable - a mutation run proved it by
        removing them without a single test noticing.
        """
        host = self.manager.get_item(host_id) or {}
        parent_id = str(host.get("ParentId") or "")
        cells = self._container_cells_for(parent_id)
        reservation = self._assembled_reservation(str(host.get("TemplateId") or ""))
        if not cells or reservation is None:
            return False

        anchor = self.manager.cell_of(host_id)
        own = set(self.manager.collect_subtree(host_id))
        if incoming:
            own |= set(self.manager.collect_subtree(str(incoming)))
        # The neighbours' cells are unioned one item at a time rather than read out of
        # `occupied_cells`, which keeps a single holder per cell: once the host is modelled
        # generously its own area overwrites a neighbour's entry, and filtering by holder then
        # drops the very overlap this is looking for. Found by a test that would not go red.
        taken: set[tuple[int, int]] = set()
        for sibling in self.manager.get_children(parent_id):
            if sibling in own:
                continue
            footprint = self._footprint_for_item(sibling)
            if footprint is None:
                continue
            base = self.manager.cell_of(sibling)
            taken |= {
                (base[0] + di, base[1] + dj)
                for di in range(footprint[0]) for dj in range(footprint[1])
            }
        wanted = {
            (anchor[0] + di, anchor[1] + dj)
            for di in range(reservation[0]) for dj in range(reservation[1])
        }
        return bool(wanted - cells or wanted & taken)

    def _confirm_cramped_host(self, host_id: str, part_id: str) -> bool:
        """Asks before fitting a part onto a host with no room to grow. True to go ahead.

        A question rather than a refusal, because the yardstick is a ceiling: plenty of cramped
        spots still work, and the user is the one who can see the grid.
        """
        t = TRANSLATIONS[self.current_lang]
        if not self._grown_host_is_cramped(host_id, incoming=part_id):
            return True
        return bool(messagebox.askyesno(
            t["attach_title"],
            t["attach_cramped"].format(
                name=self._template_name_for_item_id(host_id) or host_id,
                part=self._template_name_for_item_id(part_id) or part_id),
            parent=self.root,
        ))

    def _attach_and_report(
        self, item_id: str, host_id: str, slot_index: int, slot_label: str
    ) -> bool:
        """Fits one part and tells the user, or says why it did not happen."""
        t = TRANSLATIONS[self.current_lang]
        part_name = self._template_name_for_item_id(item_id) or item_id
        moved = self.manager.attach_item(item_id, host_id, slot_index)
        if not moved:
            messagebox.showerror(t["attach_title"], t["attach_failed"], parent=self.root)
            return False
        self._refresh_scope_keeping_open()
        self._mark_pending_changes(
            t["status_attached"].format(part=part_name, slot=slot_label))
        return True

    def _pick_owned_item(self, title: str, prompt: str, candidates: list[str]) -> str | None:
        """Asks which of the player's own items is meant, naming where each one sits.

        Two items of the same template are told apart by their location, which is the only
        thing that differs - a scope in the warehouse and the same scope on a rifle.
        """
        t = TRANSLATIONS[self.current_lang]
        win = self._new_dialog(title)

        ttk.Label(win, text=prompt, wraplength=520).pack(anchor="w", padx=12, pady=(12, 6))
        # exportselection=False: without it the selection is dropped the moment anything
        # else in the app takes the system selection, and curselection() comes back empty.
        box = tk.Listbox(
            win, height=min(max(len(candidates), 4), 14), width=70, exportselection=False,
            bg=COLOR_PANEL, fg=COLOR_TEXT, selectbackground=COLOR_SELECTED, activestyle="none",
        )
        for candidate in candidates:
            name = self._template_name_for_item_id(candidate) or candidate
            box.insert("end", f"{name}   ({self._item_location_text(candidate)})")
        if candidates:
            box.selection_set(0)
        box.pack(fill="both", expand=True, padx=12)

        chosen: list[str] = []

        def confirm() -> None:
            selection = box.curselection()
            if selection:
                chosen.append(candidates[selection[0]])
            win.destroy()

        buttons = ttk.Frame(win)
        buttons.pack(fill="x", padx=12, pady=12)
        ttk.Button(buttons, text=t["btn_ok"], command=confirm).pack(side="right")
        ttk.Button(buttons, text=t["btn_cancel"], command=win.destroy).pack(
            side="right", padx=(0, 8))
        box.bind("<Double-Button-1>", lambda _e: confirm())

        self._center_toplevel(win)
        win.grab_set()
        win.wait_window()
        return chosen[0] if chosen else None

    def _open_attachments_dialog(self) -> None:
        """Fit parts into an item's slots, and take fitted parts off again.

        One window for both directions, because one item is often both: a receiver carries
        slots *and* goes into a weapon. Each half is shown only when it applies, the same rule
        the amount/target dialog follows.
        """
        if self._blockiert_bei_mehreren("ctx_attachments"):
            return
        item_id = self._selected_item_id()
        if not item_id:
            return
        t = TRANSLATIONS[self.current_lang]
        template_id = str((self.manager.get_item(item_id) or {}).get("TemplateId") or "")

        if not self._mod_slots_of(template_id) and not self._own_hosts_for(item_id):
            messagebox.showinfo(t["attach_title"], t["attach_nothing"], parent=self.root)
            return

        win = self._new_dialog(t["attach_title"])

        header = ttk.Label(
            win,
            text=t["attach_for"].format(
                name=self._template_name_for_item_id(item_id) or item_id),
            style="InfoTitle.TLabel",
        )
        header.pack(anchor="w", padx=12, pady=(12, 4))
        ttk.Label(win, text=t["attach_hint"], wraplength=560, justify="left").pack(
            anchor="w", padx=12, pady=(0, 8))

        body = ttk.Frame(win)
        body.pack(fill="both", expand=True)

        def render() -> None:
            """Rebuilt after every change, because fitting a part moves it between both
            lists - the slot fills and the item stops being loose."""
            for child in body.winfo_children():
                child.destroy()

            slots = self._mod_slots_of(template_id)
            if slots:
                ttk.Label(body, text=t["attach_own_slots"],
                          style="InfoSection.TLabel").pack(anchor="w", padx=12)
                tree = ttk.Treeview(body, columns=("slot", "fitted", "note"), show="headings",
                                    height=min(max(len(slots), 3), INFO_MOD_ROWS),
                                    selectmode="browse")
                for column, title, width in (
                    ("slot", t["attach_col_slot"], self._scale_px(200)),
                    ("fitted", t["attach_col_fitted"], self._scale_px(250)),
                    ("note", "", self._scale_px(90)),
                ):
                    tree.heading(column, text=title)
                    tree.column(column, width=width, anchor="w")

                for index, slot in enumerate(slots):
                    occupant = self.manager.slot_occupant(item_id, index)
                    fitted = (
                        self._template_name_for_item_id(occupant) or occupant
                        if occupant else t["attach_free"]
                    )
                    tree.insert("", "end", iid=str(index), values=(
                        self._slot_label(slot),
                        fitted,
                        t["attach_required"] if slot.get("required") else "",
                    ))
                tree.pack(fill="both", expand=True, padx=12, pady=(4, 6))

                def selected_slot() -> int | None:
                    selection = tree.selection()
                    if not selection:
                        messagebox.showinfo(t["attach_title"], t["attach_select_slot"],
                                            parent=win)
                        return None
                    return int(selection[0])

                def fit_part() -> None:
                    index = selected_slot()
                    if index is None:
                        return
                    slot = slots[index]
                    label = self._slot_label(slot)
                    occupant = self.manager.slot_occupant(item_id, index)
                    if occupant:
                        messagebox.showinfo(
                            t["attach_title"],
                            t["attach_slot_taken"].format(
                                name=self._template_name_for_item_id(occupant) or occupant),
                            parent=win)
                        return
                    candidates = self._own_items_for_slot(item_id, slot)
                    if not candidates:
                        messagebox.showinfo(
                            t["attach_title"],
                            t["attach_none_owned"].format(slot=label), parent=win)
                        return
                    part = self._pick_owned_item(
                        t["attach_pick_title"],
                        t["attach_pick_prompt"].format(slot=label),
                        candidates,
                    )
                    if not part or not self._confirm_cramped_host(item_id, part):
                        return
                    if self._attach_and_report(part, item_id, index, label):
                        render()

                def detach_part() -> None:
                    index = selected_slot()
                    if index is None:
                        return
                    occupant = self.manager.slot_occupant(item_id, index)
                    if not occupant:
                        return
                    # Taking a part off is a move into a container, so it asks the same
                    # question and reuses the same placement handling.
                    if self._move_item_interactive(occupant):
                        render()

                row = ttk.Frame(body)
                row.pack(fill="x", padx=12, pady=(0, 10))
                ttk.Button(row, text=t["attach_btn_fit"], command=fit_part).pack(side="left")
                ttk.Button(row, text=t["attach_btn_detach"], command=detach_part).pack(
                    side="left", padx=(8, 0))

            hosts = self._own_hosts_for(item_id)
            if hosts:
                ttk.Separator(body, orient="horizontal").pack(fill="x", padx=12, pady=(2, 8))
                ttk.Label(body, text=t["attach_hosts"],
                          style="InfoSection.TLabel").pack(anchor="w", padx=12)
                host_tree = ttk.Treeview(
                    body, columns=("host", "slot", "where"), show="headings",
                    height=min(max(len(hosts), 3), INFO_MOD_ROWS), selectmode="browse")
                for column, title, width in (
                    ("host", t["attach_col_host"], self._scale_px(200)),
                    ("slot", t["attach_col_slot"], self._scale_px(150)),
                    ("where", t["attach_col_where"], self._scale_px(190)),
                ):
                    host_tree.heading(column, text=title)
                    host_tree.column(column, width=width, anchor="w")
                for position, (host_id, index, label) in enumerate(hosts):
                    host_tree.insert("", "end", iid=str(position), values=(
                        self._template_name_for_item_id(host_id) or host_id,
                        label,
                        self._item_location_text(host_id),
                    ))
                host_tree.pack(fill="both", expand=True, padx=12, pady=(4, 6))

                def fit_here() -> None:
                    selection = host_tree.selection()
                    if not selection:
                        messagebox.showinfo(t["attach_title"], t["attach_select_host"],
                                            parent=win)
                        return
                    host_id, index, label = hosts[int(selection[0])]
                    if not self._confirm_cramped_host(host_id, item_id):
                        return
                    if self._attach_and_report(item_id, host_id, index, label):
                        render()

                ttk.Button(body, text=t["attach_btn_fit_here"], command=fit_here).pack(
                    anchor="w", padx=12, pady=(0, 10))

        render()
        ttk.Button(win, text=t["btn_close"], command=win.destroy).pack(pady=(0, 12))
        self._center_toplevel(win)
        win.grab_set()
        win.wait_window()

    # --- Item info --------------------------------------------------------------------
    # Read-only throughout. Nothing in this dialog writes to the save; the one button that
    # does anything puts the template id on the clipboard.

    def _shelter_module_levels(self) -> dict[str, int]:
        """Foundation id -> how far that module is built, for every module in the save.

        The save records shelter modules as items carrying two abbreviated fields:
        `ShelterModuleComponent_smf` names the foundation, `ShelterModuleComponent_cl` the
        level. The level is missing on six of a real save's 24 modules, which by the
        serializer's own rule means zero - an unbuilt foundation rather than an unknown one -
        so a missing value is recorded as 0 rather than left out.
        """
        levels: dict[str, int] = {}
        for item in self.manager.get_all_items_flat():
            inner = item_data(item)
            foundation = str(inner.get("ShelterModuleComponent_smf") or "").strip().lower()
            if not foundation:
                continue
            level = inner.get("ShelterModuleComponent_cl")
            levels[foundation] = (
                level if isinstance(level, int) and not isinstance(level, bool) else 0
            )
        return levels

    def _recycler_level(self) -> int | None:
        """How far the player's own Recycler is built, or None when it is not built at all.

        A zero is reported as "not built", the same as no module: the recycling section says
        so rather than marking a stage the player cannot reach.
        """
        foundation = str((self.craft_meta or {}).get("recycler_foundation_id") or "")
        if not foundation:
            return None
        level = self._shelter_module_levels().get(foundation)
        return level if isinstance(level, int) and level > 0 else None

    def _caliber_of(self, template_id: str) -> dict | None:
        meta = self.game_item_meta_by_template_id.get(str(template_id or "").strip().lower())
        caliber = (meta or {}).get("caliber")
        return caliber if isinstance(caliber, dict) else None

    def _caliber_partners(self, template_id: str) -> tuple[str, list[str]]:
        """The other side of a caliber: cartridges for a weapon, weapons for a cartridge.

        Returns `(role, template_ids)` where role is the *queried* item's own role, so the
        caller knows which way round to label it. Built by scanning the catalog rather than
        stored in the report - 131 rows is nothing to walk, and a second index in the report
        would be one more thing to keep in step.
        """
        own = self._caliber_of(template_id)
        if not own:
            return "", []
        wanted = "cartridge" if own.get("role") == "weapon" else "weapon"
        partners = [
            str(row.get("template_id"))
            for row in self.game_item_catalog
            if isinstance(row.get("caliber"), dict)
            and row["caliber"].get("type") == own.get("type")
            and row["caliber"].get("role") == wanted
        ]
        partners.sort(key=lambda tid: (self._template_name_for_template_id(tid) or tid).lower())
        return str(own.get("role") or ""), partners

    def _subcategory_label_for_id(self, subcategory_id: object) -> str | None:
        if not isinstance(subcategory_id, int):
            return None
        if not hasattr(self, "_subcat_labels"):
            self._subcat_labels = {
                row["subcategory_id"]: row["subcategory_label"]
                for row in self.game_item_catalog
                if isinstance(row.get("subcategory_id"), int) and row.get("subcategory_label")
            }
        return self._subcat_labels.get(subcategory_id)

    def _slot_own_label(self, slot: dict) -> str | None:
        """A slot's name from the data, or None when nothing names it.

        The game's own word wins where there is one: `ContainerSlots` entries on body parts
        carry a `LocalizedName`, so an arm's slots are called "Hydraulics" and "Structure"
        rather than being described by what fits in them. Weapon slots have no such name and
        fall through to their contents.
        """
        own = slot.get("name")
        if isinstance(own, str) and own.strip():
            return own.strip()

        labels: list[str] = []
        for template_id in list(slot.get("allows") or []) + [slot.get("default_template_id")]:
            meta = self.game_item_meta_by_template_id.get(
                str(template_id or "").strip().lower(), {})
            label = meta.get("subcategory_label")
            if isinstance(label, str) and label.strip():
                labels.append(label.strip())
        if labels:
            # The commonest one: a slot occasionally permits a stray part from elsewhere.
            return Counter(labels).most_common(1)[0][0]
        for subcategory_id in slot.get("allows_subcategories") or []:
            label = self._subcategory_label_for_id(subcategory_id)
            if label:
                return label
        return None

    def _slot_label(self, slot: dict) -> str:
        """A name for an attachment point, taken from what it accepts.

        Deliberately **not** a hardcoded table of `Type` numbers. The subcategory of the parts
        a slot permits already names it - type 5 accepts Barrels, type 9 Receivers, type 2
        Sights - and reading that from the data means a game update renumbering the types
        cannot silently mislabel anything.

        Three steps, because 27 of the 195 slots name no parts at all:

        1. the slot's own permitted parts, or the subcategory it permits
        2. **what slots of the same type accept elsewhere.** 18 sight mounts filter only by
           tags, which the game files do not name - but other type-2 slots do name Sights, so
           the type itself is nameable even where one slot is not. Still derived from the data.
        3. the bare type number, if no slot of that type is nameable anywhere
        """
        t = TRANSLATIONS[self.current_lang]
        own = self._slot_own_label(slot)
        if own:
            return own

        if not hasattr(self, "_slot_type_labels"):
            votes: dict[object, Counter] = {}
            for row in self.game_item_catalog:
                for other in row.get("mod_slots") or []:
                    if not isinstance(other, dict):
                        continue
                    label = self._slot_own_label(other)
                    if label:
                        votes.setdefault(other.get("type"), Counter())[label] += 1
            self._slot_type_labels = {
                slot_type: counter.most_common(1)[0][0]
                for slot_type, counter in votes.items()
            }
        inferred = self._slot_type_labels.get(slot.get("type"))
        if inferred:
            return inferred
        return t["info_slot_fallback"].format(type=slot.get("type"))

    def _mod_slots_of(self, template_id: str) -> list[dict]:
        meta = self.game_item_meta_by_template_id.get(str(template_id or "").strip().lower())
        slots = (meta or {}).get("mod_slots")
        return [s for s in slots if isinstance(s, dict)] if isinstance(slots, list) else []

    def _format_duration(self, seconds: int | None) -> str:
        """A craft or recycle time. Seconds matter: 139 of the 150 workbench recipes and 96
        recycling rows are set to 3 or 5 seconds - the developers' "instant" - and rounding
        those to minutes showed every one of them as "0 min"."""
        t = TRANSLATIONS[self.current_lang]
        if not isinstance(seconds, int) or seconds <= 0:
            return t["info_none"]
        if seconds >= 3600:
            return t["info_hours"].format(hours=_trim_float(seconds / 3600.0))
        if seconds < 60:
            return t["info_seconds"].format(seconds=seconds)
        return t["info_minutes"].format(minutes=int(round(seconds / 60.0)))

    def _item_location_text(self, item_id: str) -> str:
        """Which container the item sits in, and where in it."""
        t = TRANSLATIONS[self.current_lang]
        item = self.manager.get_item(item_id) or {}
        parent_id = str(item.get("ParentId") or "")

        where = None
        for index, tab_id in enumerate(self.manager.get_inventory_tabs(), 1):
            if tab_id == parent_id:
                where = t["info_tab"].format(idx=index)
                break
        if where is None and parent_id:
            where = (
                self._template_name_for_item_id(parent_id)
                or (t["scope_shelter"] if parent_id == self.manager.section_roots.get(
                    "ShelterItemDto") else None)
            )
        parts = [where] if where else []

        position = item.get("Position")
        if isinstance(position, dict):
            i, j = int(position.get("I") or 0), int(position.get("J") or 0)
            # (-1, -1) is what an item with no place looks like; the game hands those to you
            # as mail rather than drawing them in a grid.
            if i >= 0 and j >= 0:
                parts.append(t["info_where_cell"].format(i=i, j=j))

        if self.manager.is_equipped(item_id):
            parts.append(t["info_equipped"])
        attached = len(self.manager.collect_subtree(item_id)) - 1
        if attached > 0:
            parts.append(t["info_attachments"].format(count=attached))

        return "   ".join(parts) if parts else t["info_none"]

    def _show_info_for_selected_item(self) -> None:
        """Zeigt die Info zum gewaehlten Gegenstand.

        **Gefragt wird nur, wenn die Antwort einen Unterschied macht.** Info ist der einzige
        Menuepunkt, der nur liest - bei einer Zeile aus gleichen Gegenstaenden gibt es nichts
        zu waehlen, und die Abfrage war dort reine Reibung. Unterscheiden sie sich, bleibt
        sie: dann ist es der einzige Weg an das beschaedigte Stueck heran.
        """
        if self._blockiert_bei_mehreren("ctx_info"):
            return
        members = self._selected_members()
        if not members:
            return
        item_id = (members[0] if not self._stack_members_differ(members)
                   else self._resolve_target_item_id(members))
        if not item_id:
            return
        item = self.manager.get_item(item_id) or {}
        self._open_item_info_dialog(
            str(item.get("TemplateId") or ""), item_id=item_id)

    def _show_info_for_selected_catalog_row(self) -> None:
        selected = self.catalog_tree.selection()
        t = TRANSLATIONS[self.current_lang]
        if not selected:
            messagebox.showwarning(t["msg_no_selection_title"], t["msg_no_item_selected"])
            return
        values = self.catalog_tree.item(selected[0], "values")
        if len(values) < 2:
            return
        self._open_item_info_dialog(str(values[1]))

    def _open_item_info_dialog(self, template_id: str, item_id: str | None = None) -> None:
        """Everything the editor knows about one item, in one read-only window.

        Two callers with slightly different knowledge: from the catalog only the template is
        known, from the inventory there is also a concrete item, which adds a section of its
        own. Everything else is identical, so it is one window rather than two.
        """
        t = TRANSLATIONS[self.current_lang]
        key = str(template_id or "").strip().lower()
        meta = self.game_item_meta_by_template_id.get(key) or {}
        name = self._template_name_for_template_id(key) or key or t["info_none"]

        win = self._new_dialog(t["info_title"])

        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)

        header = ttk.Frame(body)
        header.pack(fill="x")
        ttk.Label(header, text=name, style="InfoTitle.TLabel").pack(side="left")
        category = " › ".join(
            part for part in (meta.get("category_label"), meta.get("subcategory_label"))
            if isinstance(part, str) and part.strip()
        )
        if category:
            ttk.Label(header, text=category, style="Hint.TLabel").pack(side="right")

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(8, 10))

        if not meta:
            ttk.Label(body, text=t["info_no_game_data"], wraplength=520,
                      style="Hint.TLabel", justify="left").pack(anchor="w")

        facts = ttk.Frame(body)
        facts.pack(fill="x")

        def fact(row: int, column: int, label: str, value: str) -> None:
            ttk.Label(facts, text=label, style="Hint.TLabel").grid(
                row=row, column=column * 2, sticky="w", padx=(0, 10), pady=2)
            ttk.Label(facts, text=value).grid(
                row=row, column=column * 2 + 1, sticky="w", padx=(0, 34), pady=2)

        price = meta.get("price")
        fact(0, 0, t["info_value"],
             t["info_credits"].format(amount=f"{int(price):,}".replace(",", " "))
             if isinstance(price, (int, float)) and not isinstance(price, bool)
             else t["info_none"])

        width, height = meta.get("width"), meta.get("height")
        max_width, max_height = meta.get("max_width"), meta.get("max_height")
        if isinstance(width, int) and isinstance(height, int):
            size_text = (
                t["info_size_max"].format(width=width, height=height,
                                          max_width=max_width, max_height=max_height)
                if meta.get("is_resizable")
                and isinstance(max_width, int) and isinstance(max_height, int)
                else f"{width}x{height}"
            )
        else:
            size_text = t["info_none"]
        fact(0, 1, t["info_size"], size_text)

        mass = meta.get("mass")
        fact(1, 0, t["info_mass"],
             _trim_float(float(mass))
             if isinstance(mass, (int, float)) and not isinstance(mass, bool)
             else t["info_none"])

        capacity = meta.get("stack_capacity")
        fact(1, 1, t["info_stack"],
             t["info_stack_units"].format(capacity=int(capacity))
             if isinstance(capacity, (int, float)) and capacity > 0
             else t["info_none"])

        # The two condition mechanisms are separate and never both present: charges have a
        # per-template ceiling, wear is always the 0-4 scale.
        max_durability = meta.get("max_durability")
        if isinstance(max_durability, (int, float)) and max_durability > 0:
            wear_text = t["info_wear_dur"].format(max=_trim_float(float(max_durability)))
        elif meta.get("has_wear_condition"):
            wear_text = t["info_wear_cond"]
        else:
            wear_text = t["info_none"]
        fact(2, 0, t["info_wear"], wear_text)

        if item_id:
            ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(12, 8))
            ttk.Label(body, text=t["info_section_this_one"],
                      style="InfoSection.TLabel").pack(anchor="w")
            this_one = ttk.Frame(body)
            this_one.pack(fill="x", pady=(4, 0))
            line = []
            parts = self._item_condition_parts(self.manager.get_item(item_id))
            if parts:
                line.append(self._format_condition_text(parts))
            quantity = self._stack_quantity_of_item(self.manager.get_item(item_id))
            if quantity:
                line.append(f"×{quantity}")
            line.append(self._item_location_text(item_id))
            ttk.Label(this_one, text="   ".join(p for p in line if p)).pack(anchor="w")

        self._build_ammo_section(body, key)
        self._build_mod_slots_section(body, key)
        self._build_fits_on_section(body, key)
        self._build_recycling_section(body, key)
        self._build_used_in_section(body, key)

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(12, 8))
        footer = ttk.Frame(body)
        footer.pack(fill="x")
        ttk.Label(footer, text=t["info_template"], style="Hint.TLabel").pack(side="left")
        ttk.Label(footer, text=key or t["info_none"]).pack(side="left", padx=(10, 0))

        def copy_id() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(key)
            messagebox.showinfo(t["info_title"], t["info_copied"], parent=win)

        ttk.Button(footer, text=t["btn_close"], command=win.destroy).pack(side="right")
        if key:
            ttk.Button(footer, text=t["info_copy"], command=copy_id).pack(
                side="right", padx=(0, 6))

        win.bind("<Escape>", lambda _e: win.destroy())
        self._center_over_root(win)
        win.grab_set()
        self.root.wait_window(win)

    def _build_ammo_section(self, body: ttk.Frame, template_id: str) -> None:
        """Which cartridges a weapon takes, or which weapons take a cartridge.

        The section is absent entirely for the 1464 templates that are neither - a "no
        ammunition" line on a backpack is noise.
        """
        t = TRANSLATIONS[self.current_lang]
        role, partners = self._caliber_partners(template_id)
        if not role:
            return

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(12, 8))
        head = ttk.Frame(body)
        head.pack(fill="x")
        ttk.Label(head, text=t["info_section_ammo"],
                  style="InfoSection.TLabel").pack(side="left")
        ttk.Label(head, text=(t["info_ammo_takes"] if role == "weapon"
                              else t["info_ammo_fits"]),
                  style="Hint.TLabel").pack(side="right")

        if not partners:
            # Measured as impossible for weapons - every one has a matching cartridge - but a
            # cartridge for a weapon that was cut would land here.
            ttk.Label(body, text=t["info_ammo_none"], wraplength=520,
                      style="Hint.TLabel", justify="left").pack(anchor="w", pady=(4, 0))
            return

        names = [self._template_name_for_template_id(tid) or tid for tid in partners]
        ttk.Label(body, text=", ".join(names), wraplength=520, justify="left").pack(
            anchor="w", pady=(4, 0))

    def _build_mod_slots_section(self, body: ttk.Frame, template_id: str) -> None:
        """The attachment points, as a tree, because that is what they are.

        Slots hang off components rather than off the weapon: a muzzle device fits the barrel,
        the barrel fits the receiver, the receiver fits the weapon. Walking that chain is what
        turns 195 flat slot records into an answer to "what goes on this gun".
        """
        t = TRANSLATIONS[self.current_lang]
        slots = self._mod_slots_of(template_id)
        if not slots:
            return

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(12, 8))
        ttk.Label(body, text=t["info_section_mods"],
                  style="InfoSection.TLabel").pack(anchor="w")

        wrap = ttk.Frame(body)
        wrap.pack(fill="both", expand=True, pady=(4, 0))
        tree = ttk.Treeview(wrap, columns=("note",), show="tree headings", height=10,
                            selectmode="none")
        tree.heading("#0", text="")
        tree.heading("note", text="")
        tree.column("#0", width=self._scale_px(300), anchor="w")
        tree.column("note", width=self._scale_px(170), anchor="w")

        rows = 0

        def add(parent: str, owner_id: str, depth: int, seen: set[str]) -> None:
            """One node per slot, and under it the parts that fit; recurse into each part
            that carries slots of its own. `seen` guards against a part that permits an
            ancestor, which would otherwise recurse forever."""
            nonlocal rows
            if depth > 4:
                return
            for slot in self._mod_slots_of(owner_id):
                note = []
                if slot.get("required"):
                    note.append(t["info_mods_required"])
                node = tree.insert(parent, "end", text=self._slot_label(slot),
                                   values=("  ".join(note),), open=depth < 2)
                rows += 1

                for part_id in slot.get("allows") or []:
                    is_default = part_id == slot.get("default_template_id")
                    child = tree.insert(
                        node, "end",
                        text=self._template_name_for_template_id(part_id) or part_id,
                        values=(t["info_mods_fitted"] if is_default else "",),
                        open=False,
                    )
                    rows += 1
                    if part_id not in seen:
                        add(child, part_id, depth + 1, seen | {part_id})

        add("", template_id, 0, {template_id})
        # Measured across every template that has slots: at 12 visible rows the tallest window
        # (Ramon 1891, KA74, 1A4M) came to 835px, which clips the Close button on a 768px
        # screen. At INFO_MOD_ROWS the same window fits with room to spare, and the tree
        # scrolls for the rest.
        tree.configure(height=min(max(rows, 3), INFO_MOD_ROWS))
        if rows > INFO_MOD_ROWS:
            scroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

    def _fits_on(self, template_id: str) -> list[tuple[str, str]]:
        """(host template id, slot name) for every item this one can end up on.

        The reverse of `mod_slots`, and the direction you want when holding a scope rather than
        a rifle. The answer is deliberately the **topmost** host, not the immediate one: a
        scope's slot sits on a receiver, and "fits on 1A4M receiver" is precise but unhelpful -
        worse for a host called `Pistol_06_Barrel_04`. Walking up gives the gun.

        The top is not always a weapon. Since body parts and helmets carry slots too, hydraulics
        come out as arms and legs and a visor as its helmet - which is the useful answer there
        for exactly the same reason.

        Cached, because it is a full pass over ~1600 catalog rows and the window reopens often.
        """
        key = str(template_id or "").strip().lower()
        if not key:
            return []

        if not hasattr(self, "_fits_on_index"):
            direct: dict[str, list[tuple[str, str]]] = {}
            for row in self.game_item_catalog:
                host = str(row.get("template_id") or "").lower()
                for slot in row.get("mod_slots") or []:
                    if not isinstance(slot, dict):
                        continue
                    label = self._slot_label(slot)
                    for part in slot.get("allows") or []:
                        direct.setdefault(str(part).lower(), []).append((host, label))
            self._fits_on_index = direct
            self._fits_on_roots: dict[str, set[str]] = {}

        def roots_of(part: str, seen: frozenset) -> set[str]:
            """The topmost hosts above this part - a gun, a body part or a helmet. `seen`
            breaks the cycle a part that permits one of its own ancestors would create."""
            if part in self._fits_on_roots:
                return self._fits_on_roots[part]
            above = self._fits_on_index.get(part, [])
            if not above:
                return {part}
            found: set[str] = set()
            for host, _label in above:
                if host in seen:
                    found.add(host)
                    continue
                found |= roots_of(host, seen | {host}) or {host}
            if len(seen) <= 1:
                self._fits_on_roots[part] = found
            return found

        pairs = {
            (root, label)
            for host, label in self._fits_on_index.get(key, [])
            for root in (roots_of(host, frozenset({key, host})) or {host})
        }
        return sorted(
            pairs,
            key=lambda pair: ((self._template_name_for_template_id(pair[0]) or pair[0]).lower(),
                              pair[1]),
        )

    def _build_fits_on_section(self, body: ttk.Frame, template_id: str) -> None:
        """Where an attachment goes. Only shown for items something actually accepts."""
        t = TRANSLATIONS[self.current_lang]
        hosts = self._fits_on(template_id)
        if not hosts:
            return

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(12, 8))
        ttk.Label(body, text=t["info_section_fits_on"],
                  style="InfoSection.TLabel").pack(anchor="w")

        wrap = ttk.Frame(body)
        wrap.pack(fill="both", expand=True, pady=(4, 0))
        tree = ttk.Treeview(wrap, columns=("slot",), show="tree headings",
                            height=min(len(hosts), INFO_MOD_ROWS), selectmode="none")
        tree.heading("#0", text="")
        tree.heading("slot", text="")
        tree.column("#0", width=self._scale_px(300), anchor="w")
        tree.column("slot", width=self._scale_px(170), anchor="w")
        for host_id, slot_label in hosts:
            tree.insert("", "end",
                        text=self._template_name_for_template_id(host_id) or host_id,
                        values=(slot_label,))
        if len(hosts) > INFO_MOD_ROWS:
            scroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

    def _build_recycling_section(self, body: ttk.Frame, template_id: str) -> None:
        """What the item turns into, one row per recycler stage, the player's own marked."""
        t = TRANSLATIONS[self.current_lang]
        rows = ((self.craft_meta or {}).get("recycling") or {}).get(template_id) or []

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(12, 8))
        head = ttk.Frame(body)
        head.pack(fill="x")
        ttk.Label(head, text=t["info_section_recycle"],
                  style="InfoSection.TLabel").pack(side="left")

        if not rows:
            ttk.Label(body, text=t["info_recycle_none"], wraplength=520,
                      style="Hint.TLabel", justify="left").pack(anchor="w", pady=(4, 0))
            return

        level = self._recycler_level()
        ttk.Label(
            head,
            text=(t["info_recycle_your_level"].format(level=level) if level
                  else t["info_recycle_no_module"]),
            style="Hint.TLabel",
        ).pack(side="right")

        # The stage that applies is the highest one at or below the player's level, because
        # a built module can still run the recipes of the stages beneath it.
        applies = None
        if level:
            eligible = [row for row in rows
                        if isinstance(row.get("min_level"), int) and row["min_level"] <= level]
            if eligible:
                applies = max(eligible, key=lambda row: row["min_level"])

        table = ttk.Frame(body)
        table.pack(fill="x", pady=(4, 0))
        for index, row in enumerate(rows):
            outputs = ", ".join(
                f"{part.get('count')}x "
                f"{self._template_name_for_template_id(part.get('template_id')) or part.get('template_id')}"
                for part in row.get("outputs") or []
            )
            current = row is applies
            style = "TLabel" if current else "Hint.TLabel"
            ttk.Label(table, text=(INFO_MARKER if current else "   ")
                      + t["info_recycle_level"].format(level=row.get("min_level")),
                      style=style).grid(row=index, column=0, sticky="w", padx=(0, 12))
            ttk.Label(table, text=self._format_duration(row.get("duration_seconds")),
                      style=style).grid(row=index, column=1, sticky="w", padx=(0, 12))
            ttk.Label(table, text=outputs, style=style, wraplength=380,
                      justify="left").grid(row=index, column=2, sticky="w")

        if level and applies is None:
            ttk.Label(body, text=t["info_recycle_above_you"], wraplength=520,
                      style="Hint.TLabel", justify="left").pack(anchor="w", pady=(4, 0))

    def _build_used_in_section(self, body: ttk.Frame, template_id: str) -> None:
        """The recipes this item is an ingredient for - what you lose by scrapping it."""
        t = TRANSLATIONS[self.current_lang]
        rows = ((self.craft_meta or {}).get("used_in") or {}).get(template_id) or []

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(12, 8))
        ttk.Label(body, text=t["info_section_used_in"],
                  style="InfoSection.TLabel").pack(anchor="w")

        if not rows:
            ttk.Label(body, text=t["info_used_in_none"], style="Hint.TLabel").pack(
                anchor="w", pady=(4, 0))
            return

        # Scrollable rather than truncated. An earlier version showed twelve rows and a
        # "... and N more", which cut exactly the cases the section exists for: the eight
        # templates over that limit are the crafting staples, and 9x19 ammo feeds 92 recipes.
        # Hiding 80 of them to keep the window short answered the wrong question.
        table = ttk.Frame(body)
        table.pack(fill="both", expand=True, pady=(4, 0))
        height = min(len(rows), INFO_USED_IN_ROWS)
        tree = ttk.Treeview(table, columns=("makes", "count"), show="", height=height,
                            selectmode="none")
        tree.column("makes", width=340, anchor="w")
        tree.column("count", width=60, anchor="e")
        for row in rows:
            # What the recipe produces, by name. Its EditorName is the fallback rather than
            # the first choice: a third of them are internal identifiers like
            # "Head_01_Model_05", which tells the reader nothing about what they would lose.
            label = (
                self._template_name_for_template_id(row.get("makes"))
                or str(row.get("name") or "-")
            )
            tree.insert("", "end", values=(label, f"{row.get('count')}x"))
        if len(rows) > height:
            scroll = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

    def _ask_amount_and_target(
        self,
        title: str,
        count_label: str,
        count_default: int,
        capacity: int | None,
        same_container_id: str | None = None,
        condition_max: float | None = None,
        condition_field: str | None = None,
        count_max: int = 9999,
        hint: str | None = None,
        need: tuple[int, int] | None = None,
    ) -> tuple[int, int | None, float | None, str] | None:
        """Count, stack size, starting condition and destination in one window.

        The plain entries ask these one after another, which is fine when you accept the
        defaults and tedious when you do not. Returns None when cancelled.

        `condition_max` adds a wear field; leaving it at the maximum returns None for it,
        because a pristine item carries no condition field at all - that absence *is* the
        pristine state, and writing the maximum would only make the save larger.

        `count_max` caps the first field. Splitting a stack needs a real ceiling - one unit
        has to stay behind - where duplicating only needs a sane upper bound. `hint` replaces
        the explanatory line for callers whose ceiling needs explaining.
        """
        t = TRANSLATIONS[self.current_lang]

        targets: list[tuple[str, str]] = []
        if same_container_id:
            targets.append(("same", t["target_same_container"]))
        # `need` is the footprint the caller is about to place. Without it this list offers
        # containers that hold a free cell somewhere but no room for *this* item, and the
        # spawn then answers "no space" after the destination has been chosen - reported from
        # play for a 3x2 into a tab whose 15 free cells all sat inside the area a growable
        # neighbour already claims. See `_placement_targets`.
        targets.extend(self._placement_targets(need))
        targets.append(("inbox", t["target_inbox"]))

        win = self._new_dialog(title)
        result: list[tuple[int, int | None, str] | None] = [None]

        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=count_label).grid(row=0, column=0, sticky="w", pady=(0, 6))
        count_var = tk.StringVar(value=str(count_default))
        count_entry = ttk.Entry(body, textvariable=count_var, width=12, justify="center")
        count_entry.grid(row=0, column=1, sticky="w", pady=(0, 6), padx=(10, 0))

        row_index = 1

        units_var: tk.StringVar | None = None
        units_entry: ttk.Entry | None = None
        if capacity:
            ttk.Label(body, text=t["custom_units"].format(capacity=capacity)).grid(
                row=row_index, column=0, sticky="w", pady=(0, 6))
            units_var = tk.StringVar(value=str(capacity))
            units_entry = ttk.Entry(body, textvariable=units_var, width=12, justify="center")
            units_entry.grid(row=row_index, column=1, sticky="w", pady=(0, 6), padx=(10, 0))
            row_index += 1

        condition_var: tk.StringVar | None = None
        condition_entry: ttk.Entry | None = None
        if condition_max:
            label = (
                t["custom_repair_field_cond"].format(max=int(condition_max))
                if condition_field == "Condition_d"
                else t["custom_repair_field_dur"].format(max=_trim_float(condition_max))
            )
            ttk.Label(body, text=t["custom_condition"].format(field=label)).grid(
                row=row_index, column=0, sticky="w", pady=(0, 6))
            condition_var = tk.StringVar(value=_trim_float(condition_max))
            condition_entry = ttk.Entry(body, textvariable=condition_var, width=12,
                                        justify="center")
            condition_entry.grid(row=row_index, column=1, sticky="w", pady=(0, 6), padx=(10, 0))
            row_index += 1

        # The size the destination has to accommodate, next to the destination itself - the
        # same reason the placement dialog shows it.
        if need:
            ttk.Label(body, text=t["place_size"].format(w=need[0], h=need[1]),
                      style="Hint.TLabel").grid(row=row_index, column=0, columnspan=2,
                                                sticky="w", pady=(6, 0))
            row_index += 1

        ttk.Label(body, text=t["custom_target"]).grid(
            row=row_index, column=0, sticky="w", pady=(6, 0))
        combo = ttk.Combobox(body, state="readonly", width=48,
                             values=[label for _cid, label in targets])
        combo.current(0)
        combo.grid(row=row_index + 1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        # Which hint to show. An item that neither stacks nor wears has genuinely nothing
        # else to set, and saying so beats leaving the window looking half-built.
        if hint is not None:
            hint_text = hint
        elif condition_max:
            hint_text = t["custom_condition_hint"]
        elif capacity:
            hint_text = t["msg_place_hint"]
        else:
            hint_text = t["custom_nothing_else"]
        hint_label = ttk.Label(body, text=hint_text, wraplength=420,
                               style="Hint.TLabel", justify="left")
        hint_label.grid(row=row_index + 2, column=0, columnspan=2, sticky="w", pady=(10, 0))
        row_index += 3

        def read_int(var: tk.StringVar, entry: ttk.Entry, low: int, high: int) -> int | None:
            """Refuses a value out of range and reddens the field, as the character tab does.
            A popup per keystroke would be unusable, and silently clamping hides the refusal.
            """
            try:
                value = int(var.get().strip())
            except ValueError:
                entry.configure(style="Invalid.TEntry")
                return None
            if not (low <= value <= high):
                entry.configure(style="Invalid.TEntry")
                messagebox.showerror(
                    title, t["custom_value_range"].format(low=low, high=high), parent=win)
                return None
            entry.configure(style="TEntry")
            return value

        def confirm() -> None:
            count = read_int(count_var, count_entry, 1, count_max)
            if count is None:
                return
            units = None
            if units_var is not None and units_entry is not None:
                units = read_int(units_var, units_entry, 1, capacity or 1)
                if units is None:
                    return
            condition = None
            if condition_var is not None and condition_entry is not None:
                try:
                    value = float(condition_var.get().strip().replace(",", "."))
                except ValueError:
                    condition_entry.configure(style="Invalid.TEntry")
                    return
                if not (0 <= value <= condition_max):
                    condition_entry.configure(style="Invalid.TEntry")
                    messagebox.showerror(
                        title,
                        t["custom_value_range"].format(
                            low=0, high=_trim_float(condition_max)),
                        parent=win,
                    )
                    return
                condition_entry.configure(style="TEntry")
                # At the maximum the item stays pristine, which the game stores as no field
                # at all rather than as the maximum value.
                condition = None if value >= condition_max else value
            result[0] = (count, units, condition, targets[combo.current()][0])
            win.destroy()

        buttons = ttk.Frame(body)
        buttons.grid(row=row_index, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text=t["btn_cancel"], command=win.destroy).pack(side="right")
        ttk.Button(buttons, text=t["btn_ok"], command=confirm).pack(side="right", padx=(0, 6))

        body.columnconfigure(1, weight=1)
        count_entry.focus_set()
        win.bind("<Return>", lambda _e: confirm())
        win.bind("<Escape>", lambda _e: win.destroy())
        self._center_over_root(win)
        win.grab_set()
        self.root.wait_window(win)
        return result[0]

    def _condition_fields_of(self, item_id: str) -> tuple[str, float] | None:
        """Which condition field an item carries and its ceiling, or None for neither.

        `DurabilityComponent_durability` counts charges and its maximum comes from the game
        data; `Condition_d` is the 0-4 wear scale. An item has one or the other, and most
        have neither until the game first writes one.
        """
        item = self.manager.get_item(item_id)
        if not item:
            return None
        inner = item_data(item)
        if "DurabilityComponent_durability" in inner:
            ceiling = self._template_max_durability_for_item(item)
            if ceiling is None:
                own = inner.get("DurabilityComponent_md")
                ceiling = float(own) if isinstance(own, (int, float)) and own > 0 else None
            if ceiling is None:
                return None
            return "DurabilityComponent_durability", float(ceiling)
        if "Condition_d" in inner:
            return "Condition_d", 4.0
        return None

    def _open_set_condition_dialog(self, item_id: str) -> None:
        t = TRANSLATIONS[self.current_lang]

        # The row itself may carry nothing while an attachment does, so the whole subtree is
        # searched before telling the user there is nothing to set.
        subtree = self.manager.collect_subtree(item_id)
        carriers = [member for member in subtree if self._condition_fields_of(member)]

        # Both halves of this window need a condition field to work on: setting a value
        # writes into one, and factory fresh removes it. An item that carries none is already
        # as fresh as the save can express, so there is nothing to offer.
        if not carriers:
            messagebox.showinfo(t["custom_title_repair"], t["custom_repair_none"],
                                parent=self.root)
            return

        anchor = item_id if self._condition_fields_of(item_id) else carriers[0]
        field, ceiling = self._condition_fields_of(anchor)  # type: ignore[misc]
        field_label = (
            t["custom_repair_field_cond"].format(max=int(ceiling))
            if field == "Condition_d"
            else t["custom_repair_field_dur"].format(max=_trim_float(ceiling))
        )

        win = self._new_dialog(t["custom_title_repair"])

        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(
            body,
            text=t["custom_repair_prompt"].format(
                name=self._template_name_for_item_id(anchor) or "?", field=field_label),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        value_var = tk.StringVar(value=_trim_float(ceiling))
        entry = ttk.Entry(body, textvariable=value_var, width=14, justify="center")
        entry.pack(anchor="w")

        children_var = tk.BooleanVar(value=len(carriers) > 1 or len(subtree) > 1)
        if len(carriers) > 1 or len(subtree) > 1:
            ttk.Checkbutton(body, text=t["custom_repair_children"],
                            variable=children_var).pack(anchor="w", pady=(10, 0))

        # Factory fresh is not a condition value - it removes the field rather than writing
        # one - so it takes the value box out of play instead of pretending to read it.
        mint_var = tk.BooleanVar(value=False)

        def on_mint_toggled() -> None:
            entry.configure(state="disabled" if mint_var.get() else "normal")

        ttk.Checkbutton(body, text=t["mint_checkbox"], variable=mint_var,
                        command=on_mint_toggled).pack(anchor="w", pady=(6, 0))
        ttk.Label(body, text=t["mint_hint"], wraplength=420, justify="left",
                  style="Hint.TLabel").pack(anchor="w", pady=(4, 0))
        on_mint_toggled()

        def confirm() -> None:
            if mint_var.get():
                win.destroy()
                self._apply_mint([item_id], include_parts=children_var.get())
                return
            try:
                value = float(value_var.get().strip().replace(",", "."))
            except ValueError:
                entry.configure(style="Invalid.TEntry")
                return
            if not (0 <= value <= ceiling):
                entry.configure(style="Invalid.TEntry")
                messagebox.showerror(
                    t["custom_title_repair"],
                    t["custom_value_range"].format(low=0, high=_trim_float(ceiling)),
                    parent=win,
                )
                return
            entry.configure(style="TEntry")
            win.destroy()
            self._write_condition(
                [anchor] if not children_var.get() else carriers, value)

        buttons = ttk.Frame(body)
        buttons.pack(anchor="e", pady=(14, 0))
        ttk.Button(buttons, text=t["btn_cancel"], command=win.destroy).pack(side="right")
        ttk.Button(buttons, text=t["btn_ok"], command=confirm).pack(side="right", padx=(0, 6))

        entry.focus_set()
        entry.select_range(0, "end")
        win.bind("<Return>", lambda _e: confirm())
        win.bind("<Escape>", lambda _e: win.destroy())
        self._center_over_root(win)
        win.grab_set()
        self.root.wait_window(win)

    def _write_condition(self, item_ids: list[str], value: float) -> None:
        """Sets the condition each item actually carries, clamped to that item's own ceiling.

        A value valid for the item the dialog was opened on can exceed an attachment's
        maximum - a rifle's 5 charges against a scope's 4 - so each item is capped by its
        own. `DurabilityComponent_md` is lifted along with the value when it would otherwise
        sit below it, because that field caps how far a repair kit can restore the item.
        """
        changed = 0
        for item_id in item_ids:
            fields = self._condition_fields_of(item_id)
            if not fields:
                continue
            field, ceiling = fields
            item = self.manager.get_item(item_id)
            if not item:
                continue
            inner = writable_item_data(item)
            target = min(float(value), float(ceiling))
            if inner.get(field) == target:
                continue
            inner[field] = target
            if field == "DurabilityComponent_durability":
                current_md = inner.get("DurabilityComponent_md")
                if isinstance(current_md, (int, float)) and current_md < target:
                    inner["DurabilityComponent_md"] = target
            changed += 1

        if not changed:
            return
        t = TRANSLATIONS[self.current_lang]
        self._refresh_scope_keeping_open()
        self._mark_pending_changes(t["status_repaired_custom"].format(count=changed))

    def _center_over_root(self, win: tk.Toplevel) -> None:
        """Puts a dialog over the main window instead of at the screen's top left."""
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 3
        win.geometry(f"+{max(0, x)}+{max(0, y)}")

    # --- The change list ----------------------------------------------------------------
    # One view, three uses: confirming an apply, previewing a restore, and comparing the save
    # against a backup. All three are the same question - what is the difference between these
    # two saves - so they share `core_utils.diff_saves` and the tree below.

    def _read_save_file(self, path: Path) -> dict | None:
        """A save from disk as a plain dict, or None when it cannot be read.

        Used for the "before" side of every comparison, so it must not raise into a dialog:
        the answer "the file cannot be read" is itself worth showing.
        """
        try:
            with Path(path).open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _diff_against_disk(self) -> dict | None:
        """What the staged edits would change in the file on disk."""
        on_disk = self._read_save_file(Path(self.manager.save_path))
        if on_disk is None:
            return None
        return diff_saves(on_disk, self.manager.data)

    def _diff_row_text(self, row: dict) -> str:
        """One item row: its name, and where it is."""
        name = (
            self._template_name_for_template_id(row.get("template_id"))
            or str(row.get("template_id") or "")
        )
        parent = self._template_name_for_item_id(row.get("parent_id"))
        return f"{name}  ({parent})" if parent else name

    def _diff_value_text(self, value: object) -> str:
        """A field value for display. `None` means the key is absent, which is a value in this
        save format - the game omits any field holding its type's default - so it gets a word
        of its own rather than being printed as "None"."""
        t = TRANSLATIONS[self.current_lang]
        if value is None:
            return t["diff_absent"]
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _fill_diff_tree(self, tree: ttk.Treeview, diff: dict) -> int:
        """Fills a tree with the four groups. Returns how many rows it wrote."""
        t = TRANSLATIONS[self.current_lang]
        tree.delete(*tree.get_children())
        written = 0

        for key, label in (("added", t["diff_added"]), ("removed", t["diff_removed"])):
            rows = diff.get(key) or []
            if not rows:
                continue
            node = tree.insert("", "end", text=label.format(count=len(rows)), open=True)
            for row in rows:
                tree.insert(node, "end", text=self._diff_row_text(row), values=("", ""))
                written += 1

        changed = diff.get("changed") or []
        if changed:
            node = tree.insert("", "end", text=t["diff_changed"].format(count=len(changed)),
                               open=True)
            # Grouped per item: one move writes ParentId and Position, and reading those as two
            # unrelated lines makes a single action look like two.
            per_item: dict[str, list[dict]] = {}
            for row in changed:
                per_item.setdefault(str(row.get("id")), []).append(row)
            for item_id, rows in per_item.items():
                item_node = tree.insert(node, "end", text=self._diff_row_text(rows[0]),
                                        open=True)
                for row in rows:
                    tree.insert(item_node, "end", text=str(row.get("field")), values=(
                        self._diff_value_text(row.get("before")),
                        self._diff_value_text(row.get("after")),
                    ))
                    written += 1

        fields = diff.get("fields") or []
        if fields:
            node = tree.insert("", "end", text=t["diff_fields"].format(count=len(fields)),
                               open=len(fields) <= DIFF_OPEN_ROWS)
            # Grouped by the section the path starts in. A trader stock refresh alone rewrites
            # some 1400 leaves, and a flat list of those buries the two the user made.
            per_section: dict[str, list[dict]] = {}
            for row in fields:
                per_section.setdefault(str(row.get("path") or "").split(".")[0].split("[")[0],
                                       []).append(row)
            for section, rows in sorted(per_section.items()):
                section_node = tree.insert(
                    node, "end", text=f"{section}  ({len(rows)})",
                    open=len(rows) <= DIFF_OPEN_ROWS)
                for row in rows[:DIFF_SECTION_LIMIT]:
                    tree.insert(section_node, "end", text=str(row.get("path")), values=(
                        self._diff_value_text(row.get("before")),
                        self._diff_value_text(row.get("after")),
                    ))
                    written += 1
                if len(rows) > DIFF_SECTION_LIMIT:
                    tree.insert(section_node, "end", values=("", ""), text=t["diff_more"].format(
                        count=len(rows) - DIFF_SECTION_LIMIT))
        return written

    def _show_diff_dialog(self, title: str, diff: dict, confirm_label: str | None = None,
                          intro: str | None = None) -> bool:
        """Shows a change list. With `confirm_label` it asks, and returns True when confirmed.

        Without it the dialog is a read-only comparison and the return value is False, which
        no caller reads.
        """
        t = TRANSLATIONS[self.current_lang]
        win = self._new_dialog(title)

        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=intro or t["diff_intro"], wraplength=640,
                  justify="left").pack(anchor="w", pady=(0, 8))

        wrap = ttk.Frame(body)
        wrap.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(wrap, orient="vertical")
        scroll.pack(side="right", fill="y")
        tree = ttk.Treeview(wrap, columns=("before", "after"), show="tree headings",
                            height=16, selectmode="browse", yscrollcommand=scroll.set)
        scroll.configure(command=tree.yview)
        tree.pack(side="left", fill="both", expand=True)
        tree.heading("#0", text=t["diff_col_what"])
        tree.heading("before", text=t["diff_col_before"])
        tree.heading("after", text=t["diff_col_after"])
        tree.column("#0", width=self._scale_px(420), anchor="w", stretch=True)
        tree.column("before", width=self._scale_px(160), anchor="w")
        tree.column("after", width=self._scale_px(160), anchor="w")

        self._fill_diff_tree(tree, diff)
        if diff_is_empty(diff):
            tree.insert("", "end", text=t["diff_nothing"], values=("", ""))

        answer: list[bool] = [False]

        def accept() -> None:
            answer[0] = True
            win.destroy()

        buttons = ttk.Frame(body)
        buttons.pack(anchor="e", pady=(12, 0))
        if confirm_label:
            ttk.Button(buttons, text=t["btn_cancel"], command=win.destroy).pack(
                side="right", padx=(8, 0))
            ttk.Button(buttons, text=confirm_label, command=accept).pack(side="right")
        else:
            ttk.Button(buttons, text=t["btn_close"], command=win.destroy).pack(side="right")

        self._center_toplevel(win)
        win.grab_set()
        win.wait_window()
        return answer[0]

    # --- Restoring a backup -------------------------------------------------------------

    def _open_restore_backup_dialog(self) -> None:
        """Puts a timestamped backup back in place of the save.

        The editor has written one on every apply since it existed, but getting one back
        meant renaming files in Explorer. The current save is copied aside first, so this is
        as reversible as everything else here.
        """
        t = TRANSLATIONS[self.current_lang]
        backups = list_backups(self.manager.backup_dir)
        if not backups:
            messagebox.showinfo(t["restore_title"], t["restore_none"], parent=self.root)
            return

        win = self._new_dialog(t["restore_title"])

        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=t["restore_prompt"]).pack(anchor="w", pady=(0, 8))

        tree_wrap = ttk.Frame(body)
        tree_wrap.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(tree_wrap, orient="vertical")
        scroll.pack(side="right", fill="y")
        tree = ttk.Treeview(
            tree_wrap,
            columns=("when", "label", "size"),
            show="headings",
            selectmode="browse",
            height=12,
            yscrollcommand=scroll.set,
        )
        scroll.configure(command=tree.yview)
        tree.pack(side="left", fill="both", expand=True)
        tree.heading("when", text=t["restore_col_when"])
        tree.heading("label", text=t["restore_col_label"])
        tree.heading("size", text=t["restore_col_size"])
        tree.column("when", width=self._scale_px(170), anchor="w")
        tree.column("label", width=self._scale_px(170), anchor="w")
        tree.column("size", width=self._scale_px(100), anchor="e")

        rows: dict[str, Path] = {}
        for entry in backups:
            row_id = tree.insert("", "end", values=(
                entry["taken_at"].strftime("%Y-%m-%d %H:%M:%S"),
                entry["label"],
                f"{entry['size'] / 1024:,.0f} KB".replace(",", " "),
            ))
            rows[row_id] = entry["path"]
        first = tree.get_children("")
        if first:
            tree.selection_set(first[0])

        ttk.Label(body, text=t["restore_hint"], wraplength=470, style="Hint.TLabel",
                  justify="left").pack(anchor="w", pady=(10, 0))

        def diff_for(chosen: Path) -> dict | None:
            """What restoring this backup would change in the save that is on disk now."""
            current = self._read_save_file(Path(self.manager.save_path))
            backup = self._read_save_file(chosen)
            if current is None or backup is None:
                return None
            return diff_saves(current, backup)

        def compare() -> None:
            selection = tree.selection()
            if not selection:
                return
            chosen = rows[selection[0]]
            diff = diff_for(chosen)
            if diff is None:
                messagebox.showerror(t["restore_title"], t["diff_unreadable_compare"],
                                     parent=win)
                return
            self._show_diff_dialog(
                t["diff_compare_title"], diff,
                intro=t["diff_compare_intro"].format(name=chosen.name))

        def confirm() -> None:
            selection = tree.selection()
            if not selection:
                return
            chosen = rows[selection[0]]
            if self.has_pending_changes and not messagebox.askyesno(
                    t["restore_title"], t["restore_pending"], parent=win):
                return
            # The same list the apply shows, in the other direction: what putting this file
            # back would undo. A file name and a timestamp say nothing about that.
            diff = diff_for(chosen)
            if diff is None:
                if not messagebox.askyesno(
                        t["restore_title"],
                        t["restore_confirm"].format(name=chosen.name), parent=win):
                    return
            elif not self._show_diff_dialog(
                    t["diff_restore_title"], diff, confirm_label=t["btn_restore"],
                    intro=t["diff_restore_intro"].format(name=chosen.name)):
                return
            win.destroy()
            self._restore_backup(chosen)

        buttons = ttk.Frame(body)
        buttons.pack(anchor="e", pady=(14, 0))
        ttk.Button(buttons, text=t["btn_cancel"], command=win.destroy).pack(side="right")
        ttk.Button(buttons, text=t["btn_restore"], command=confirm).pack(side="right", padx=(0, 6))
        ttk.Button(buttons, text=t["diff_btn_compare"], command=compare).pack(
            side="right", padx=(0, 6))

        tree.bind("<Double-1>", lambda _e: confirm())
        win.bind("<Escape>", lambda _e: win.destroy())
        self._center_over_root(win)
        win.grab_set()
        self.root.wait_window(win)

    def _restore_backup(self, backup_path: Path) -> None:
        t = TRANSLATIONS[self.current_lang]
        try:
            # Through save() rather than a plain copy, so the safety copy lands in the same
            # folder under the same naming scheme and is pruned with the rest.
            safety = self.manager.save(backup_name="before_restore")
            restore_backup(Path(self.manager.save_path), backup_path)
            self.manager.reload_from_disk()
        except Exception as exc:
            messagebox.showerror(
                t["restore_title"],
                t["msg_restore_failed"].format(exc=exc),
                parent=self.root,
            )
            return

        # Every view holds data from the old file.
        self._repopulate_after_reload()
        # Offer edits from before the restore describe a file that is no longer on disk.
        self.shop_offer_undo = {}
        self._clear_pending_changes(t["status_restored"].format(
            name=backup_path.name, backup=safety.name if safety else "-"))

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

        self._refresh_scope_keeping_open()
        self._mark_pending_changes(f"Deleted {deleted} item(s) (not saved yet)")

    def _search_query(self) -> str:
        return self.search_var.get().strip().lower()

    def _apply_search(self) -> None:
        """Rebuild the inventory tree through the current filter.

        The same shape the catalog search has: the tree itself is filtered, an empty box
        shows everything again, and there is nothing to close. The popup this replaced
        matched ids only, so a search for a name the rows themselves display found nothing.
        """
        self._refresh_scope_keeping_open()

    def _search_haystack(self, item_id: str) -> str:
        """Everything about one item worth searching: its name, both ids, its categories.

        Deliberately the same set of fields the catalog filter reads, plus the item id,
        which only a save has. Cached per populate run: with a filter active, the tree
        build and the status-line count each used to reassemble this for every item in
        the scope - name resolution, five meta lookups and a join, twice over.
        """
        cached = self._search_haystack_cache.get(item_id)
        if cached is not None:
            return cached
        item = self.manager.get_item(item_id) or {}
        template_id = str(item.get("TemplateId") or "")
        meta = self.game_item_meta_by_template_id.get(template_id.lower(), {})
        parts = (
            self._template_name_for_template_id(template_id) or "",
            template_id,
            str(item.get("Id") or ""),
            str(meta.get("name") or ""),
            str(meta.get("alias") or ""),
            str(meta.get("category_label") or ""),
            str(meta.get("subcategory_label") or ""),
        )
        haystack = " ".join(parts).lower()
        self._search_haystack_cache[item_id] = haystack
        return haystack

    def _item_matches_search(self, item_id: str, query: str) -> bool:
        # The empty-query guard cannot be reached through any caller - every one of them is
        # already inside an `if query` - so no test can see it fail. It stays because
        # "everything matches nothing" is the wrong answer to give a future caller.
        return bool(query) and query in self._search_haystack(item_id)

    def _subtree_matches_search(self, item_id: str, query: str) -> bool:
        """The item itself or anything attached to it.

        A scope sits inside a weapon inside a case, so a filter that only looked at the
        rows currently on screen would answer "no matches" for an item three levels down.
        """
        cached = self._search_match_cache.get(item_id)
        if cached is None:
            cached = any(
                self._item_matches_search(member, query)
                for member in self.manager.collect_subtree(item_id)
            )
            self._search_match_cache[item_id] = cached
        return cached

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

        # Die Liste selbst anzufassen hiesse, im Save zu schneiden: `get_mail_items` gibt die
        # echte Liste heraus, nicht eine Kopie. Genau das stand hier bis zum 10.09.2026.
        if not self.manager.delete_mail(idx):
            messagebox.showerror(t["tab_mailbox"], t["msg_err_letter_out_of_range"])
            return

        self._refresh_mailbox()
        self._mark_pending_changes("Deleted one mailbox letter (not saved yet)")

    def _apply_pending_changes(self) -> None:
        if not self.has_pending_changes:
            return
        t = TRANSLATIONS[self.current_lang]

        # Say what is about to be written before writing it. The diff is against the file on
        # disk, so it also catches anything the game itself changed since the editor read it.
        diff = self._diff_against_disk()
        if diff is None:
            if not messagebox.askyesno(t["title"], t["diff_unreadable"], parent=self.root):
                return
        elif not self._show_diff_dialog(
                t["diff_apply_title"], diff, confirm_label=t["btn_apply"],
                intro=t["diff_apply_intro"]):
            return

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

    def _repopulate_after_reload(self) -> None:
        """Refill every view from the manager after the file underneath has been replaced.

        Three callers need exactly this - discarding, restoring a backup, and reloading -
        and it used to be written out at each of them. The copies had already drifted:
        discarding did not refresh the quests tree, so a discard left that one tab showing
        the file that was no longer loaded. One helper is what keeps the next one honest.
        """
        current_scope = self.scope_var.get()
        self._load_scope_options()
        if current_scope in self.scope_labels:
            self.scope_var.set(current_scope)
            self._populate_scope_view()
        self._refresh_mailbox()
        self._refresh_char_tab()
        self._refresh_quests_tree()
        self._refresh_crafting_tree()
        self._invalidate_json_tab()

    def _reload_save_from_disk(self) -> None:
        """Read the save again, so the editor shows what the game has written since.

        The game writes `offline.save` when a raid ends. An editor left open beside it
        therefore holds a picture that is one raid old, and until now the only way to catch
        up was to close and reopen it.

        Staged edits cannot survive this - they describe items in a file that has just been
        replaced - so the question says so instead of dropping them quietly. Without pending
        changes there is nothing to lose and nothing to ask.
        """
        t = TRANSLATIONS[self.current_lang]
        if self.has_pending_changes and not messagebox.askyesno(
            t["msg_reload_title"],
            t["msg_reload_discards"],
            parent=self.root,
        ):
            return
        try:
            self.manager.reload_from_disk()
        except Exception as exc:
            messagebox.showerror(
                t["msg_reload_title"],
                t["msg_reload_failed"].format(exc=exc),
                parent=self.root,
            )
            return
        self._repopulate_after_reload()
        # Every offer record describes a slot in the file that was just replaced - and the
        # game regenerates the whole Commodities list on a stock refresh anyway.
        self.shop_offer_undo = {}
        self._clear_pending_changes(t["status_reloaded"])

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
        self._repopulate_after_reload()
        # Trader offer edits that were never applied are gone with the reload, so only the
        # records for edits that did reach disk are still worth anything.
        self.shop_offer_undo = {
            key: record for key, record in self.shop_offer_undo.items()
            if record.get("applied")
        }
        self._clear_pending_changes("Unsaved changes discarded")

    # Every `after()` id the window keeps, so `_shutdown` can cancel all of them. A timer
    # that outlives the root fires against destroyed widgets and dies with "invalid command
    # name" - and until 2026-09-10 only the first of these three was cancelled, although the
    # docstring below had named the danger since the day it was written. The other two belong
    # to the Raw JSON tab: use its search or its copy button, close the window inside the next
    # second and a half, and the callback fires into nothing.
    #
    # `test_shutdown_timers.py` compares this tuple against every `self.X = self.root.after(...)`
    # in this file, so a fourth timer cannot be added without being listed here.
    TIMER_ATTRIBUTES = ("_badge_after_id", "_copy_timer_id", "_json_search_timer_id")

    def _shutdown(self) -> None:
        """The one way out. Cancels every pending timer before destroy() - a pending after()
        callback outliving the root dies with "invalid command name" - and stops the
        music. One helper instead of three copies, so the close paths cannot drift; not
        in _stop_music, which also runs on mute and must not touch the animation."""
        for name in self.TIMER_ATTRIBUTES:
            after_id = getattr(self, name, None)
            if after_id is None:
                continue
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                # Already fired or already cancelled - nothing left to call off.
                pass
            setattr(self, name, None)
        self._stop_music()
        self.root.destroy()

    def _on_close_requested(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        if not self.has_pending_changes:
            self._shutdown()
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
            self._shutdown()
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
        self._shutdown()

    def _asset_path(self, filename: str) -> Path:
        if getattr(sys, 'frozen', False):
            # PyInstaller creates _MEIPASS at runtime; it does not exist in the module's
            # type information, which is why a checker cannot see it here.
            base_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        else:
            base_dir = Path(__file__).resolve().parent
        return base_dir / filename

    def _set_window_icon(self) -> None:
        """Ersetzt Tks Federlogo im Fensterrahmen und in der Taskleiste.

        Ohne das hier zeigt Tk sein eigenes Standardsymbol - die Feder, die man in jedem
        ungestylten Tk-Programm sieht. Die Datei traegt sieben Groessen von 16 bis 256 px,
        jede einzeln gezeichnet (siehe `Scripts/make_app_icon.py`); Windows sucht sich die
        passende heraus, statt eine grosse herunterzurechnen.

        `iconbitmap(default=...)` statt `iconbitmap(...)`: das `default` vererbt das Symbol
        an jedes weitere Toplevel, und davon macht der Editor viele auf - Verschieben,
        Aufteilen, Anbauteile, Hackerman. Ohne `default` traegt jeder dieser Dialoge wieder
        die Feder.

        Fehlt die Datei oder kennt die Plattform kein .ico, bleibt es beim alten Symbol.
        Ein fehlendes Bild ist kein Grund, den Editor nicht zu starten.
        """
        pfad = self._asset_path("app_icon.ico")
        if not pfad.exists():
            return
        try:
            self.root.iconbitmap(default=str(pfad))
        except tk.TclError:
            # Nicht-Windows: dort kennt Tk nur `iconphoto`, und .ico liest es nicht.
            pass

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
                self._label_mute_button()
            except Exception:
                pass
        else:
            try:
                self.music_playing = True
                self._label_mute_button()
                
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
                # aplay missing or unusable. One failed attempt answers the question for
                # the whole session - retrying every second for the app's lifetime would
                # poll for a player that is not going to appear. Only the flag is touched:
                # this is a worker thread, and widgets belong to the Tk thread.
                self.music_playing = False
                break

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

        self._label_mute_button()

    def _label_mute_button(self) -> None:
        """Beschriftet den Musikknopf nach dem Zustand, in der aktuellen Sprache.

        Stand an drei Stellen, und keine davon stimmte ganz:

        - `_start_music` schrieb zweimal fest `"\U0001f507 Mute"`, auf Englisch, in jeder Sprache.
        - `_stop_music` schrieb `"\U0001f50a Music"` - ein Wort, das in **keiner** der drei
          Uebersetzungstabellen vorkommt.
        - `_update_ui_language` nahm die richtigen Schluessel, entschied aber an
          `self.music_muted` - einem Namen, der nirgends im ganzen Baum gesetzt wird. Der
          Zweig war damit tot, und nach jedem Sprachwechsel stand "Stumm" da, auch wenn der
          Ton laengst aus war.

        Der Zustand heisst `self.music_playing`, und der ist die einzige Quelle hier.
        """
        button = getattr(self, "mute_button", None)
        if not button:
            return
        t = TRANSLATIONS[self.current_lang]
        button.configure(text=t["btn_mute"] if self.music_playing else t["btn_unmute"])

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


def set_taskbar_identity() -> None:
    """Gibt dem Prozess eine eigene Kennung fuer die Windows-Taskleiste.

    Beim Start aus der Quelle laeuft der Editor in python.exe, und die Taskleiste gruppiert
    nach der AppUserModelID des Prozesses - ohne eigene erbt sie die von Python und zeigt
    dessen Symbol, obwohl der Fensterrahmen laengst den Container traegt. Muss gesetzt sein,
    **bevor** das erste Fenster entsteht.

    Die gefrorene .exe bringt ihre Kennung selbst mit; der Aufruf schadet dort nicht.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes          # lokal, wie in `enable_high_dpi_awareness` daneben
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "VeldinGenworks.CargoHuntersSaveEditor")
    except Exception:
        # Aeltere Windows-Fassungen kennen den Aufruf nicht. Dann bleibt es beim Symbol von
        # python.exe - haesslich, aber kein Grund, nicht zu starten.
        pass


def main() -> None:
    enable_high_dpi_awareness()
    set_taskbar_identity()
    parser = argparse.ArgumentParser(description="Cargo Hunters Save Editor GUI")
    parser.add_argument(
        "--save-path",
        default=None,
        help="Optional path to offline.save. If omitted, the GUI auto-detects Steam userdata remote paths.",
    )
    parser.add_argument(
        "--dpi-scale",
        type=float,
        default=None,
        metavar="FACTOR",
        help="Pretend the display runs at this scale (1.5, 2.0) to check the layout without "
             "a scaled monitor. Affects nothing but this run.",
    )
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()
    if args.dpi_scale:
        apply_simulated_dpi(root, args.dpi_scale)

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
