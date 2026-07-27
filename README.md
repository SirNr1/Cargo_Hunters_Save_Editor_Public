# Cargo Hunters Save Editor 🛠️

Desktop save editor for the Steam game **Cargo Hunters** (`offline.save`, Steam App ID `4197990`) built with Python and Tkinter.

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)

---

## ☕ Support the Project

If you find this tool helpful and want to support its continued development:

* ☕ **[Buy me a coffee on Ko-fi](https://ko-fi.com/sirnr1)**
* ⭐ **Star this repository** on GitHub to help others find it!

---

## ✨ Features

* **🎒 Inventory & Equipment Management**:
  * Edit items across character equipment, shelter containers, and inventory tabs.
  * Stack-aware duplication (+ copy count).
  * Recursive item repair (weapons, durability, condition metrics).
* **📦 Full Game Items Catalog**:
  * Browse the complete extracted item database by category.
  * Add catalog items directly into your inventory.
* **🤝 Trader Stock Swapping**:
  * Temporarily place any catalog item into a trader's shop stock for purchase in-game.
  * Reverts when the trader's stock refreshes in-game, or immediately via the dialog's **Undo** button (current editor session only).
* **📬 Mailbox Manager**:
  * View inbox messages, reward counts, read states, and NPC senders (`NpcBioId` resolution).
* **☢️ Hackerman's Lab**:
  * Edit nickname, character level, XP, individual skill levels (0–10), trader shop levels, and balance.
  * One-click convenience boosts.
* **🛡️ Safe Staging & Auto-Backup**:
  * Edits are staged in memory.
  * **Apply Changes** saves to disk while creating a timestamped backup in the `backups/` directory.
  * **Discard Changes** reverts pending edits to the last saved state.
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

## 📄 License & Terms

This project is licensed under the **[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](LICENSE)** license.

* **Non-Commercial**: You may **not** sell, monetize, or include this software or its source code in any commercial product.
* **Attribution**: You must give appropriate credit if you share or adapt this project.
* **ShareAlike**: Any modified versions must be distributed under the same license.

### Disclaimer
*This software is an unofficial, community-made fan tool and is NOT affiliated with, endorsed by, or associated with the developers or publishers of Cargo Hunters.*
