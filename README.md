# Cargo Hunters Save Editor 🛠️

**English** · [Русский](README.ru.md)

Desktop save editor for the Steam game **Cargo Hunters** (`offline.save`, Steam App ID `4197990`) built with Python and Tkinter.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

---

## ☕ Support the Project

If you find this tool helpful and want to support its continued development:

* ☕ **[Buy me a coffee on Ko-fi](https://ko-fi.com/sirnr1)**
* ⭐ **Star this repository** on GitHub to help others find it!

---

## 📸 Screenshots

![Inventory](docs/screenshots/01-inventory.png)

| Game Items catalog | Hackerman's Lab |
| --- | --- |
| ![Game Items](docs/screenshots/02-game-items.png) | ![Hackerman's Lab](docs/screenshots/03-hackermans-lab.png) |

![Quests](docs/screenshots/07-quests.png)

| Mailbox | Counters |
| --- | --- |
| ![Mailbox](docs/screenshots/04-mailbox.png) | ![Counters](docs/screenshots/06-counters.png) |

| Item info | Offer at Trader |
| --- | --- |
| ![Item info](docs/screenshots/08-item-info.png) | ![Offer at Trader](docs/screenshots/05-offer-at-trader.png) |

---

## ✨ Features

* **🎒 Inventory & Equipment Management**:
  * Edit items across character equipment, shelter containers, and inventory tabs.
  * Stack-aware duplication (+ copy count).
  * Recursive item repair (weapons, durability, condition metrics).
  * **Repair Item to...** sets a value of your choosing instead of the maximum, and holds each item to **its own** ceiling — 250 is right for a shield and nonsense for a five-charge repair kit, so one value across a whole weapon does not overshoot on the small parts.
  * **Move Item...** takes an item to another container. Attachments come along, and an equipped item leaves its slot empty.
  * **Split Stack...** takes part of a stack into a second one, defaulting to half. At least one unit stays behind, since taking all of them is a move rather than a split.
  * Delete an item together with everything attached to it — or expand it and delete a single attachment, so a scope goes without touching the rifle.
* **🔍 Item Info**:
  * Right-click → **Item Info**, in the inventory and in the catalog both. Read-only.
  * Value in credits, weight, grid size (with the maximum for a weapon that grows), stack capacity, and which kind of condition the item can carry. From the inventory it also shows that particular one's condition, count and location.
  * **What recycling yields.** The output depends on how far your Recycler is built, so every stage is listed and the one you can actually reach is marked:

    ```
    Recycling                                    your recycler: level 1
      ▸ Level 1    2.5 h    10x Acid
        Level 2    2 h      500x Lead, 5x Acid
    ```

    Your Recycler's level is read from your save. If every recipe needs a better module than you have, it says so rather than marking a row you cannot use. 426 of 1595 items can be recycled at all; the rest say plainly that they cannot.
  * **What the item is used for** — the recipes it is an ingredient in, with how many units each wants. Worth a look before scrapping something.
* **📍 Choose Where a New Item Goes**:
  * Duplicating and spawning both ask first, and list every container that has room: `Tab 1 - 73 of 240 cells free`, `Hugger (carried) - 22 of 24`.
  * A free spot is then searched for inside that container, turning the item 90° only if it fits no other way. Spawning ten looks for ten spots, and says so if only part of the batch fits.
  * **Inbox** is always offered, also when everything is full — the game hands the item to you as mail.
  * The **shelter** is not offered: the game files do not describe its grid, so the editor does not guess at its size.
* **📦 Full Game Items Catalog**:
  * Browse the complete extracted item database by category.
  * Add catalog items directly into your inventory.
  * Stackable items are spawned as real stacks; the **Stack** column shows how many units fit in one.
  * Items that can wear out get one more field when spawned: the condition they start at. Left at the maximum they are spawned pristine, which is how the game stores an untouched item — it carries no condition field at all.
  * **Value** and **Weight** columns, straight from the game data. 1110 of 1595 items have a price and 1162 a weight; the rest show a dash rather than a zero, because "no price recorded" and "costs nothing" are different statements.
* **🤝 Trader Stock Swapping**:
  * Temporarily place any catalog item into a trader's shop stock for purchase in-game.
  * Reverts when the trader's stock refreshes in-game, or immediately via the dialog's **Undo** button (current editor session only).
* **📬 Mailbox Manager**:
  * View inbox messages, reward counts, read states, and NPC senders (`NpcBioId` resolution).
* **🗺️ Quests (read-only)**:
  * Every quest in the game against the ones your save has met — **302 against 179** in a real save, which is the point: a save only ever names the quests you have already come across, so the ones you have not can only come from the game's own files.
  * Grouped the way the developers group them, and inside that by active, completed, or never seen. The never-seen branches start open, so the question is answered when you open the tab. Pick one and the panel below shows the full briefing, what it wants finished first, who sends it, and what it pays.
  * Two caveats: **67 of the unseen ones are daily quests** from a rotating pool and 21 are marked obsolete — cut content that cannot appear. And **progress is not shown**, because it is not in the save: the game stores what a quest wants but not how far along you are.
* **☢️ Hackerman's Lab**:
  * Edit nickname, character level, XP, individual skill levels, trader shop levels, and balance.
  * Every ceiling is read from the game's own data instead of a hardcoded number: each skill has its **own** maximum (the `MAX` button uses it), the character level stops where the game stops, and a trader's balance stops at what that shop is allowed to hold — writing more than the game accepts just gets cut down silently on the next load.
  * XP is capped at the current level's goal, which is shown next to the field. Set the level first; changing it resets XP to 0.
  * **Unspent skill points** can be added, and are deliberately not capped.
  * A **Counters** sub-tab shows the account's sessions, last run and lifetime tallies, read-only.
  * One-click convenience boosts.
* **🛡️ Safe Staging & Auto-Backup**:
  * Edits are staged in memory.
  * **Apply Changes** saves to disk while creating a timestamped backup in the `backups/` directory.
  * **Discard Changes** reverts pending edits to the last saved state.
  * **Keep backups** in the bottom right caps how many are kept — 20 by default, 0 keeps every one. Only files the editor named itself are ever deleted, so your own copies in that folder are safe.
  * **Restore backup...** next to it puts one back without leaving the editor: pick it from the list by timestamp, reason and size, and the editor replaces your save and reloads. Your current save is copied aside as `before_restore` first, so undoing the undo is one more click. A file the editor did not write itself is never offered, and a pick that turns out not to be a save is refused **before** your save is touched rather than halfway through.
  * Auto-detects Steam `offline.save` files on Windows and Linux.
* **🌍 Multi-Language Support (i18n)**:
  * English, German (Deutsch), and Russian (Русский).

---

## 🚀 How to Run from Source

### Requirements
* Python 3.11+
* `tkinter` (included with standard Python installers on Windows)
* `UnityPy` — optional, and only for **Refresh Names from Game**, which re-reads item and NPC
  names from the game's asset bundles. A prebuilt mapping ships with the app, so everything
  else works without it.

```bash
pip install UnityPy   # only if you want to refresh the names yourself
```

### Run Command

```bash
python CH_Editor/gui_editor.py
```

Optional explicit save path:

```bash
python CH_Editor/gui_editor.py --save-path "/path/to/offline.save"
```

---

## 🔨 Building Portable Windows Executable (`.exe`)

You can build a standalone portable `.exe` folder using PyInstaller:

```bash
pip install pyinstaller UnityPy
pyinstaller cargo_hunters_editor.spec
```

The compiled portable app will be located at:
`dist/CargoHuntersEditor/`

---

## ⚠️ Windows will warn you the first time

The build is an unsigned PyInstaller executable, so two warnings are normal and neither means
something is wrong:

* **SmartScreen** — *"Windows protected your PC"*. Click **More info → Run anyway**. The
  warning appears because the file has no code-signing certificate, not because of anything
  it does.
* **Antivirus** — PyInstaller executables are a well-known source of false positives, since
  legitimate and malicious programs alike get packed with it. Defender occasionally flags one
  build and clears the next.

The app makes no network connections. The only files it writes are your save and the
timestamped copies in the `backups/` folder next to the executable.

If you would rather not trust a binary at all, run it from source — it is the same code, and
the section above tells you how.

---

## 📄 License & Terms

This project is licensed under the **[GNU General Public License v3.0](LICENSE)** (GPLv3).

* **Open Source**: You may freely use, modify, and distribute this software.
* **Copyleft**: If you distribute modified versions of this software, you must release your changes under the same GPLv3 license and provide the source code.
* **Keep the notices**: You must include the original copyright notice and a copy of the license with any distribution.

### Disclaimer
*This software is an unofficial, community-made fan tool and is NOT affiliated with, endorsed by, or associated with the developers or publishers of Cargo Hunters.*
