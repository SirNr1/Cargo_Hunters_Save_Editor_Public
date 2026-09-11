"""Der Text des Hilfereiters, in drei Sprachen.

**Reine Daten, ohne einen einzigen Import.** Die drei Listen standen bis zum 10.09.2026 in
`_build_help_tab` und machten 924 der 960 Zeilen dieser Methode aus - der eigentliche Aufbau
des Textfelds sind 36. Damit war sie mit Abstand die größte Methode der Datei, obwohl an ihr
nichts zu verstehen war: es ist Text.

Jeder Eintrag ist ein Paar aus Text und Markierung; die Markierungen sind `header`, `bullet`,
`highlight` und `link`, und `tests/test_help_text.py` hält sie gegen diese Liste.

**Drei Platzhalter werden erst beim Füllen ersetzt** - `{game_build}`, `{game_build_steam}`
und `{game_build_date}` für den getesteten Spiel-Build, dazu `{preset_total}` und
`{preset_outgrown}` für die Zahlen, die aus dem Bericht des Spielers kommen. Ersetzt wird mit
`str.replace`, nicht mit `.format`: in den Texten stehen geschweifte Klammern in Beispielen,
und `.format` würde daran scheitern oder sie stillschweigend fressen. Siehe
`SaveEditorGUI._populate_help_text`.
"""

HELP_TEXT_EN = [
    ("★ BUILT FOR GAME VERSION ", "header"),
    ("{game_build} ★\n\n", "header"),
    ("• Tested against: ", "bullet"),
    ("Cargo Hunters {game_build} (Steam build {game_build_steam}, "
     "{game_build_date}). A game update can add items or change what the save "
     "holds. If your game is newer, run ", "bullet"),
    ("Refresh Names from Game", "highlight"),
    (" first - that alone fixes new items showing as raw IDs.\n\n\n", "bullet"),

    ("★ UPDATE NAMES FROM GAME ★\n\n", "header"),
    ("• Scan Assets: ", "bullet"),
    ("Click ", "bullet"),
    ("Refresh Names from Game", "highlight"),
    (" in the top-right corner. This parses game files to resolve encrypted IDs into readable item, skill and trader names - and reads the quest, crafting, weapon preset, NPC, shop and level data the Quests, Crafting and Character tabs need.\n\n", "bullet"),

    ("• Reload Save: ", "bullet"),
    ("The game writes the save when a raid ends. If you leave this editor open while you play, click ", "bullet"),
    ("Reload Save", "highlight"),
    (" to read the file again instead of restarting. Unsaved changes cannot survive that and you will be asked first.\n\n", "bullet"),

    ("• Safe Editing Workflow: ", "bullet"),
    ("Only edit and apply changes while your game is in the main menu or shelter. Never save changes while inside an active raid — the game completely overwrites your save file upon extraction or death, erasing your edits.\n\n\n", "bullet"),

    ("★ INVENTORY EDITOR ★\n\n", "header"),
    ("• Container Scope: ", "bullet"),
    ("Use the Scope dropdown above the tree to switch between all containers, your backpack, equipment slots, or individual warehouse tabs (0–N). The shelter container has no grid layout in game assets, so it is not offered as a move or spawn target.\n", "bullet"),
    ("• Expand Folders: ", "bullet"),
    ("Double-click", "highlight"),
    (" on category/tab folders to expand their items. A row like \"5 stacks, 95 "
     "units\" opens the same way, one line per stack, and anything you do to one of "
     "those lines applies to that stack alone.\n", "bullet"),
    ("• Search: ", "bullet"),
    ("Type a name, a category or an id and press Return (or press ", "bullet"),
    ("Ctrl+F", "highlight"),
    (" to jump straight into the search box). The tree keeps what matches, "
     "and a hit inside a container opens that container so you can see where it sits. "
     "An empty box shows everything again. It searches the chosen scope only, so pick "
     "the tab first.\n", "bullet"),
    ("• Category Colors: ", "bullet"),
    ("Toggle ", "bullet"),
    ("Category Colors", "highlight"),
    (" on the toolbar to tint rows by their item group (weapons, ammo types, armor, medical, etc.).\n", "bullet"),
    ("• Multi-Selection & Select All: ", "bullet"),
    ("Hold Shift or Ctrl while clicking, or press ", "bullet"),
    ("Ctrl+A", "highlight"),
    (" while the tree has focus, to select multiple rows. Context menu actions (Delete, Repair, Duplicate, Move) apply to all selected items at once.\n", "bullet"),
    ("• Condition, Durability & Mint: ", "bullet"),
    ("The tree displays ", "bullet"),
    ("COND", "highlight"),
    (" (0–4.0 scale) for wear on weapons, armor, and limbs, and ", "bullet"),
    ("DUR", "highlight"),
    (" for consumable charges (e.g. medkits, repair kits). Repair restores maximum durability, while ", "bullet"),
    ("Factory fresh (Mint)", "highlight"),
    (" completely removes the wear records, restoring the item to as-new state.\n", "bullet"),
    ("• Item Management: ", "bullet"),
    ("Right-click", "highlight"),
    (" on any item to open the action context menu:\n", "bullet"),
    ("  - Repair Item (Ctrl+R): ", "highlight"),
    ("Restores item durability back to 100%.\n", "bullet"),
    ("  - Duplicate Item (Ctrl+D): ", "highlight"),
    ("Creates a clone and asks which container it goes into; the original's own container is the default and Inbox is always available.\n", "bullet"),
    ("  - Move Item... (Ctrl+M): ", "highlight"),
    ("Takes the item to another container. Attachments come along, and an equipped "
     "item leaves its slot empty. The shelter is not offered - the game files do not "
     "describe its grid, so the editor does not guess at it.\n", "bullet"),
    ("  - Split Stack...: ", "highlight"),
    ("Takes part of a stack into a second one. At least one unit stays behind, since "
     "taking all of them would be a move rather than a split.\n", "bullet"),
    ("  - Set Stack Size...: ", "highlight"),
    ("Writes how many units one stack holds, up to what the item can carry. No free "
     "cell needed, unlike a duplicate. Items the game never stacked are turned down "
     "rather than turned into stacks.\n", "bullet"),
    ("  - Repair Item to... -> factory fresh: ", "highlight"),
    ("The tick in that window does the opposite of setting a value: it removes the "
     "condition, the record of what the item arrived with, and the charge count. That "
     "is what the game calls mint - a repair to maximum still reads as repaired, "
     "because the game keeps the record that the item was damaged.\n", "bullet"),
    ("  - Attachments...: ", "highlight"),
    ("Fits parts into the item and takes them off again. The window shows the slots "
     "on this item with whatever sits in each, and the items of yours that this one "
     "fits into - only the half that applies. A free slot offers exactly the parts "
     "the game allows there, out of what you own. Weapons, weapon parts, body parts "
     "and helmets have slots; the item's own stored size is left alone, so a weapon "
     "that grew with its parts may want more room in its container.\n", "bullet"),
    ("  - Item Info (Ctrl+I): ", "highlight"),
    ("Everything known about the item, read-only: value, weight, size, what "
     "recycling it yields at each recycler stage - with the one your own module can "
     "reach marked - and which recipes use it as an ingredient. For a weapon it "
     "also lists the cartridges it takes and its attachment points as a tree: a "
     "muzzle device fits the barrel, the barrel fits the receiver, the receiver fits "
     "the gun. Not only weapons: body parts and helmets have slots too, so an arm "
     "shows its hydraulics and structure and a helmet its visor. Open the visor "
     "instead and it names the helmet.\n", "bullet"),
    ("  - Delete Item (Del): ", "highlight"),
    ("Removes the item and everything attached to it. To drop a single attachment "
     "instead, expand the item and right-click that attachment's own row. Warehouse "
     "tabs and storage roots are refused - they are part of the save's layout, not "
     "items.\n\n\n", "bullet"),
    
    ("★ GAME ITEMS (SPAWNER CATALOG) ★\n\n", "header"),
    ("• Search & Filter: ", "bullet"),
    ("Filter by item categories or search for specific item names (focus with ", "bullet"),
    ("Ctrl+F", "highlight"),
    ("). Toggle ", "bullet"),
    ("Category Colors", "highlight"),
    (" to colour rows, or tick ", "bullet"),
    ("Only new", "highlight"),
    (" after a name refresh to see what game updates added.\n", "bullet"),
    ("• Spawn Items: ", "bullet"),
    ("Right-click an item template in the list and pick ", "bullet"),
    ("Add to Inventory...", "highlight"),
    (". One window asks how many, where they go, and - for items that can carry one "
     "- the condition they start at. Left at the maximum the item is spawned "
     "pristine, which is how the game stores an untouched one.\n", "bullet"),
    ("• Spawn a weapon assembled: ", "bullet"),
    ("Right-click a firearm and pick ", "bullet"),
    ("Spawn Assembled...", "highlight"),
    (" to get it the way the game itself builds it, with magazine, barrel, stock and "
     "sight already in their slots. {preset_total} weapons have such a configuration and "
     "some have "
     "several, in which case you pick from the variants and see what each carries. The "
     "inbox is not offered here: delivering a weapon with parts on it as mail is "
     "untested.\n", "bullet"),
    ("• It needs room: ", "bullet"),
    ("the game works out how much space an assembled weapon takes on its own and mails "
     "anything it cannot place, so the editor keeps the weapon's maximum size free. A "
     "small pouch is refused outright and a full tab answers \"no space\" rather than "
     "spawning something that would arrive as mail.\n", "bullet"),
    ("• Assembled weapon limits & Mailbox: ", "bullet"),
    ("{preset_outgrown} of the {preset_total} assembled weapon variants exceed standard grid dimensions with all attachments mounted. The game engine handles oversized weapons by delivering them to your mailbox upon loading. The editor reserves the weapon's full expanded footprint so nothing overlaps.\n", "bullet"),
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

    ("★ QUESTS ★\n\n", "header"),
    ("• What the tab shows: ", "bullet"),
    ("Every quest in the game against the ones your save has met, grouped and split "
     "into active, completed and never seen. The never-seen branches start open. "
     "Pick a quest for the full briefing, what it needs finished first, who sends it "
     "and what it pays.\n", "bullet"),
    ("• Search: ", "bullet"),
    ("The box above the tree matches the quest name, its briefing text, the sender, "
     "the group and the internal id (jump with ", "bullet"),
    ("Ctrl+F", "highlight"),
    ("). What is left standing is shown open. An empty box brings the whole list back.\n", "bullet"),
    ("• Community Guide: ", "bullet"),
    ("Click ", "bullet"),
    ("Community guide ↗", "highlight"),
    (" on the toolbar to open the player-maintained Steam guide in your browser.\n", "bullet"),
    ("• Read-only: ", "bullet"),
    ("Nothing here is written back. The progress of a running quest is not in the "
     "save at all, only what the quest asks for - so it cannot be shown either.\n\n\n",
     "bullet"),

    ("★ CRAFTING ★\n\n", "header"),
    ("• What the tab shows: ", "bullet"),
    ("Every recipe the game's workbenches have, grouped by shelter module and by the "
     "level that module needs. Each row says what it makes, what it takes, how long "
     "it runs, and whether you could start it now. Select one and the pane underneath "
     "lists each ingredient as have / needed, marking what you are short of.\n",
     "bullet"),
    ("• Search: ", "bullet"),
    ("The box above the tree matches the module, the recipe name and what it makes - "
     "and also what it consumes, so typing an ingredient answers \"what can I even "
     "do with this?\" (focus with ", "bullet"),
    ("Ctrl+F", "highlight"),
    ("). Matches are shown open.\n", "bullet"),
    ("• Not in the game yet: ", "bullet"),
    ("Some recipes ask for a workbench level the game has no build step for - the 3D "
     "Printer stops at level 1 and carries recipes for 2 and 3. Those are marked "
     "rather than listed as craftable.\n", "bullet"),
    ("• Recycling is elsewhere: ", "bullet"),
    ("It is the same recipe list read from the item's side, so it lives in Item Info "
     "where you have the item in hand. Read-only, like the Quests tab.\n\n\n",
     "bullet"),

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
    ("Five one-click buttons. ", "bullet"),
    ("Max Out All Skills", "highlight"),
    (" and ", "bullet"),
    ("Fill Trader Balances", "highlight"),
    (" (1,000,000 each) do what they say. ", "bullet"),
    ("Repair All Items", "highlight"),
    (" takes everything to its maximum, while ", "bullet"),
    ("Make Everything Factory Fresh", "highlight"),
    (" removes the wear record instead, which is the stronger one: the save then "
     "reads as never used. ", "bullet"),
    ("Fill All Stacks", "highlight"),
    (" tops every stack up to what its item can carry. The last two ask first and "
     "say afterwards how much they touched; nothing is written until you "
     "apply.\n\n\n", "bullet"),

    ("★ RAW JSON ★\n\n", "header"),
    ("• What the tab shows: ", "bullet"),
    ("The full formatted JSON representation of your in-memory save data. It reflects "
     "both saved and staged changes, including exact IDs, quantities, and structure.\n",
     "bullet"),
    ("• Search: ", "bullet"),
    ("Case-insensitive text search across the raw save data with live match counter "
     "and Next / Prev navigation (Enter / Shift+Enter). Focus search directly with ", "bullet"),
    ("Ctrl+F", "highlight"),
    (".\n", "bullet"),
    ("• Word wrap & Copy: ", "bullet"),
    ("Toggle word wrap to avoid horizontal scrolling, or click Copy JSON to place the "
     "entire text onto the system clipboard. Read-only, like Quests and Crafting.\n\n\n",
     "bullet"),

    ("★ KEYBOARD SHORTCUTS ★\n\n", "header"),
    ("• Global Shortcuts: ", "bullet"),
    ("Available across the entire window:\n", "bullet"),
    ("  - Ctrl+S: ", "highlight"),
    ("Applies pending changes to the save file (prompts for confirmation and creates a backup first).\n", "bullet"),
    ("  - Ctrl+F: ", "highlight"),
    ("Jumps focus straight into the search box of the currently active tab (Inventory, Catalog, Quests, Crafting, or Raw JSON).\n", "bullet"),
    ("• Inventory Tree Shortcuts: ", "bullet"),
    ("Active when navigating items in the inventory tree:\n", "bullet"),
    ("  - Shift+Click / Ctrl+Click: ", "highlight"),
    ("Selects a range or toggles individual items for batch operations.\n", "bullet"),
    ("  - Del: ", "highlight"),
    ("Deletes selected item(s) and their attachments.\n", "bullet"),
    ("  - Ctrl+D: ", "highlight"),
    ("Duplicates selected item(s).\n", "bullet"),
    ("  - Ctrl+R: ", "highlight"),
    ("Repairs selected item(s) to 100% durability.\n", "bullet"),
    ("  - Ctrl+M: ", "highlight"),
    ("Moves selected item(s) to another container.\n", "bullet"),
    ("  - Ctrl+I: ", "highlight"),
    ("Opens the detailed Item Info window.\n", "bullet"),
    ("  - Ctrl+A: ", "highlight"),
    ("Selects all visible rows in the current container scope.\n", "bullet"),
    ("• Raw JSON Navigation: ", "bullet"),
    ("When searching in the Raw JSON tab, press ", "bullet"),
    ("Enter", "highlight"),
    (" to jump to the next match, or ", "bullet"),
    ("Shift+Enter", "highlight"),
    (" to jump to the previous match.\n\n\n", "bullet"),

    ("★ SAVING YOUR CHANGES ★\n\n", "header"),
    ("• Apply Edits: ", "bullet"),
    ("Click ", "bullet"),
    ("Apply Changes", "highlight"),
    (" (or press ", "bullet"),
    ("Ctrl+S", "highlight"),
    (") at the top right to save all edits to your file. It shows the list of what it "
     "is about to write first - every new item, every removed one, every changed "
     "field with the value before and after - and waits for a yes. Cancel and nothing "
     "is written. The list compares against the file on disk, so it also shows what "
     "the game changed while the editor was open.\n", "bullet"),
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
     "anything older than that is deleted. Set it to 0 to keep every backup.\n", "bullet"),
    ("• Going back: ", "bullet"),
    ("Restore backup...", "highlight"),
    (" puts one back in place of your save. Your current save is copied aside first, "
     "so the restore itself can be undone. Nothing in the folder is deleted, and a "
     "file this editor did not write is never offered.\n", "bullet"),
    ("• Status Bar Controls: ", "bullet"),
    ("The bottom bar houses the background synth music toggle (", "bullet"),
    ("🔇 / 🔊", "highlight"),
    ("), the language switcher (US, DE, RU), and the backup retention spinner. Setting ", "bullet"),
    ("Keep backups", "highlight"),
    (" to 0 ensures all historical backups are preserved indefinitely.\n\n\n", "bullet"),

    ("★ SUPPORT THE PROJECT ★\n\n", "header"),
    ("• Support on Ko-fi: ", "bullet"),
    ("If you enjoy using this free save editor, consider supporting development on Ko-fi:\n", "bullet"),
    ("https://ko-fi.com/sirnr1\n", "link"),
]


HELP_TEXT_DE = [
    ("★ GEBAUT FÜR SPIELVERSION ", "header"),
    ("{game_build} ★\n\n", "header"),
    ("• Getestet gegen: ", "bullet"),
    ("Cargo Hunters {game_build} (Steam-Build {game_build_steam}, "
     "{game_build_date}). Ein Spiel-Update kann Gegenstände hinzufügen oder "
     "ändern, was im Speicherstand steht. Ist dein Spiel neuer, zuerst ", "bullet"),
    ("Namen aus dem Spiel aktualisieren", "highlight"),
    (" ausführen - das allein behebt neue Gegenstände, die als rohe IDs erscheinen.\n\n\n", "bullet"),

    ("★ SPIELNAMEN AKTUALISIEREN ★\n\n", "header"),
    ("• Assets scannen: ", "bullet"),
    ("Klicke auf ", "bullet"),
    ("Spielnamen aktualisieren", "highlight"),
    (" in der oberen rechten Ecke. Dies analysiert die Spieldateien, um kryptische IDs in lesbare Gegenstands-, Skill- und Händlernamen aufzulösen - und liest die Quest-, Bauplan-, Waffenbausatz-, NPC-, Händler- und Stufendaten, die die Reiter Quests, Crafting und Character brauchen.\n\n", "bullet"),

    ("• Spielstand neu laden: ", "bullet"),
    ("Das Spiel schreibt den Spielstand am Ende eines Raids. Wenn du den Editor beim Spielen offen lässt, klicke auf ", "bullet"),
    ("Spielstand neu laden", "highlight"),
    (", statt ihn neu zu starten. Ungespeicherte Änderungen überstehen das nicht - danach wird vorher gefragt.\n\n", "bullet"),

    ("• Sicherer Bearbeitungs-Workflow: ", "bullet"),
    ("Bearbeite und übernimm Änderungen nur, wenn dein Spiel im Hauptmenü oder im Unterschlupf steht. Speichere niemals während eines aktiven Raids – das Spiel überschreibt die Datei beim Verlassen oder Sterben vollständig und löscht deine Änderungen.\n\n\n", "bullet"),

    ("★ INVENTAR-EDITOR ★\n\n", "header"),
    ("• Container-Auswahl (Scope): ", "bullet"),
    ("Nutze das Scope-Dropdown über dem Baum, um gezielt zwischen allen Behältern, Rucksack, Ausrüstung oder einzelnen Lager-Tabs (0–N) umzuschalten. Der Unterschlupf hat in den Spieldateien kein definiertes Raster und steht daher nicht als Ziel zur Wahl.\n", "bullet"),
    ("• Ordner erweitern: ", "bullet"),
    ("Doppelklicke", "highlight"),
    (" auf Kategorie- oder Reiter-Ordner, um deren Inhalt anzuzeigen. Eine Zeile wie "
     "\"5 Stapel, 95 Einheiten\" klappt genauso auf, eine Zeile je Stapel, und was du "
     "mit einer dieser Zeilen machst, betrifft nur diesen einen Stapel.\n", "bullet"),
    ("• Suche: ", "bullet"),
    ("Namen, Kategorie oder ID eintippen und Eingabetaste drücken (oder ", "bullet"),
    ("Ctrl+F", "highlight"),
    (" drücken, um direkt ins Suchfeld zu springen). Der Baum zeigt nur "
     "noch die Treffer, und ein Treffer in einem Behälter klappt diesen auf, damit du "
     "siehst, wo er steckt. Leeres Feld zeigt wieder alles. Gesucht wird nur im "
     "gewählten Bereich, also vorher den Reiter auswählen.\n", "bullet"),
    ("• Kategorie-Farben: ", "bullet"),
    ("Aktiviere ", "bullet"),
    ("Kategorie-Farben", "highlight"),
    (" in der Menüleiste, um Zeilen nach Gegenstandsgruppen (Waffen, Munitionstypen, Rüstung, Medizin usw.) farblich hervorzuheben.\n", "bullet"),
    ("• Mehrfachauswahl & Alles auswählen: ", "bullet"),
    ("Halte Shift oder Strg beim Anklicken gedrückt, oder drücke ", "bullet"),
    ("Ctrl+A", "highlight"),
    (" bei fokussiertem Inventarbaum, um alle aktuell sichtbaren Zeilen im gewählten Behälter zu markieren. Aktionen wie Löschen, Reparieren, Duplizieren und Verschieben wirken auf alle markierten Gegenstände gleichzeitig.\n", "bullet"),
    ("• Zustand, Haltbarkeit & Fabrikneu: ", "bullet"),
    ("Der Baum zeigt ", "bullet"),
    ("COND", "highlight"),
    (" (Skala 0–4,0) für die Abnutzung von Waffen, Rüstung und Gliedmaßen, und ", "bullet"),
    ("DUR", "highlight"),
    (" für Ladungen von Verbrauchsgütern (z. B. MedKits, Reparatursets). Reparieren setzt Werte auf Maximum, während ", "bullet"),
    ("Fabrikneu (Mint)", "highlight"),
    (" den Abnutzungseintrag restlos entfernt, sodass das Stück als fabrikneu gilt.\n", "bullet"),
    ("• Gegenstandsverwaltung: ", "bullet"),
    ("Klicke mit der rechten Maustaste", "highlight"),
    (" auf einen beliebigen Gegenstand, um das Kontextmenü zu öffnen:\n", "bullet"),
    ("  - Gegenstand reparieren (Ctrl+R): ", "highlight"),
    ("Setzt die Haltbarkeit des Gegenstands auf 100% zurück.\n", "bullet"),
    ("  - Gegenstand duplizieren (Ctrl+D): ", "highlight"),
    ("Erstellt eine Kopie und fragt, in welchen Behälter sie soll; vorgegeben ist der Behälter des Originals, der Posteingang steht immer zur Wahl.\n", "bullet"),
    ("  - Gegenstand verschieben... (Ctrl+M): ", "highlight"),
    ("Bringt den Gegenstand in einen anderen Behälter. Anbauteile kommen mit, und ein "
     "ausgerüsteter Gegenstand lässt seinen Platz leer zurück. Der Unterschlupf wird "
     "nicht angeboten - die Spieldateien beschreiben sein Raster nicht, und der Editor "
     "rät die Größe nicht.\n", "bullet"),
    ("  - Stapel teilen...: ", "highlight"),
    ("Trennt einen Teil eines Stapels zu einem zweiten ab. Mindestens ein Stück bleibt "
     "zurück, denn alles abzutrennen wäre ein Verschieben und kein Teilen.\n", "bullet"),
    ("  - Stapelgröße setzen...: ", "highlight"),
    ("Schreibt, wie viele Einheiten ein Stapel enthält, bis zu dem, was der "
     "Gegenstand fassen kann. Anders als beim Duplizieren wird dafür keine freie "
     "Zelle gebraucht. Was das Spiel nie gestapelt hat, wird auch nicht zum Stapel.\n",
     "bullet"),
    ("  - Reparieren auf... -> fabrikneu: ", "highlight"),
    ("Der Haken in dem Fenster macht das Gegenteil von einen Wert setzen: Er entfernt "
     "den Zustand, den Vermerk, womit das Stück ankam, und die Ladungen. Genau das "
     "heißt im Spiel mint - eine Reparatur auf Maximum bleibt eine Reparatur, weil "
     "das Spiel den Vermerk behält, dass der Gegenstand Schaden hatte.\n", "bullet"),
    ("  - Anbauteile...: ", "highlight"),
    ("Montiert Teile an den Gegenstand und nimmt sie wieder ab. Das Fenster zeigt die "
     "Aufnahmen dieses Gegenstands mit dem, was darin sitzt, und deine Gegenstände, "
     "auf die dieser passt - jeweils nur die Hälfte, die zutrifft. Eine freie Aufnahme "
     "bietet genau die Teile an, die das Spiel dort erlaubt, aus deinem Bestand. "
     "Aufnahmen haben Waffen, Waffenteile, Körperteile und Helme. Die gespeicherte "
     "Größe des Wirts bleibt unverändert - eine mit Teilen gewachsene Waffe kann in "
     "ihrem Behälter mehr Platz brauchen.\n", "bullet"),
    ("  - Info zum Gegenstand (Ctrl+I): ", "highlight"),
    ("Alles, was über den Gegenstand bekannt ist, nur zur Ansicht: Wert, Gewicht, "
     "Größe, was beim Recyceln auf jeder Ausbaustufe herauskommt - die für deinen "
     "eigenen Recycler erreichbare ist markiert - und in welchen Rezepten er Zutat "
     "ist. Bei einer Waffe zusätzlich die passende Munition und die Anbaupunkte als "
     "Baum: eine Mündungsvorrichtung sitzt am Lauf, der Lauf am Receiver, der "
     "Receiver an der Waffe. Nicht nur Waffen: Körperteile und Helme haben ebenfalls "
     "Slots, ein Arm zeigt also Hydraulik und Struktur und ein Helm sein Visier. "
     "Öffnest du stattdessen das Visier, nennt es den Helm.\n", "bullet"),
    ("  - Gegenstand löschen (Del): ", "highlight"),
    ("Entfernt den Gegenstand samt allem, was daran hängt. Um nur einen einzelnen "
     "Anbauteil zu entfernen, klappe den Gegenstand auf und mache den Rechtsklick auf "
     "die Zeile des Anbauteils. Lagerreiter und Container-Wurzeln werden abgelehnt - "
     "sie gehören zum Aufbau des Saves und sind keine Gegenstände.\n\n\n", "bullet"),
    
    ("★ GEGENSTANDSSPAWNER (KATALOG) ★\n\n", "header"),
    ("• Suchen & Filtern: ", "bullet"),
    ("Filtere nach Kategorien oder suche nach bestimmten Namen (Fokus mit ", "bullet"),
    ("Ctrl+F", "highlight"),
    ("). Aktiviere ", "bullet"),
    ("Kategorie-Farben", "highlight"),
    (" für farbliche Zeilen, oder aktiviere ", "bullet"),
    ("Nur neue", "highlight"),
    (" nach einem Namens-Update, um Neuerungen zu sehen.\n", "bullet"),
    ("• Gegenstände spawnen: ", "bullet"),
    ("Rechtsklick auf einen Gegenstand in der Liste, dann ", "bullet"),
    ("Zum Inventar hinzufügen...", "highlight"),
    (". Ein Fenster fragt wie viele, wohin, und - bei Gegenständen, die einen tragen "
     "können - mit welchem Zustand sie beginnen. Beim Maximum entstehen sie "
     "makellos, so wie das Spiel einen unberührten Gegenstand ablegt.\n", "bullet"),
    ("• Waffe fertig aufgebaut: ", "bullet"),
    ("Rechtsklick auf eine Schusswaffe und ", "bullet"),
    ("Fertig aufgebaut spawnen...", "highlight"),
    (" liefert sie so, wie das Spiel sie selbst baut - Magazin, Lauf, Schaft und "
     "Visier sitzen schon in ihren Aufnahmen. {preset_total} Waffen haben so eine "
     "Konfiguration, "
     "manche mehrere; dann wählst du aus den Varianten und siehst, was jede trägt. Der "
     "Posteingang steht hier nicht zur Wahl: eine Waffe mit Teilen als Post zu "
     "schicken ist ungetestet.\n", "bullet"),
    ("• Sie braucht Platz: ", "bullet"),
    ("wie viel Fläche eine zusammengebaute Waffe belegt, rechnet das Spiel selbst aus, "
     "und was es nicht platzieren kann, kommt ins Postfach. Der Editor hält deshalb die "
     "Maximalgröße der Waffe frei. Eine kleine Tasche wird direkt abgelehnt, ein voller "
     "Reiter antwortet mit \"kein Platz\" statt etwas zu spawnen, das als Post "
     "ankommt.\n", "bullet"),
    ("• Übergrößen bei Waffen & Postfach: ", "bullet"),
    ("{preset_outgrown} der {preset_total} aufgebauten Waffenvarianten überschreiten mit allen Anbauteilen die regulären Rastermaße. Das Spiel leitet solche Übergrößen beim Laden automatisch ins Postfach um. Der Editor reserviert stets die voll erweiterte Fläche, damit nichts überlappt.\n", "bullet"),
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

    ("★ QUESTS ★\n\n", "header"),
    ("• Was der Reiter zeigt: ", "bullet"),
    ("Alle Quests des Spiels gegen die, denen dein Spielstand begegnet ist - "
     "gruppiert und aufgeteilt in aktiv, erledigt und nie gesehen. Die "
     "Nie-gesehen-Zweige sind offen. Wähle eine Quest für den vollen Text, was sie "
     "voraussetzt, wer sie schickt und was sie bringt.\n", "bullet"),
    ("• Suche: ", "bullet"),
    ("Das Feld über dem Baum sucht in Questname, Auftragstext, Absender, Gruppe und "
     "interner ID (Fokus mit ", "bullet"),
    ("Ctrl+F", "highlight"),
    ("). Was stehen bleibt, wird aufgeklappt gezeigt. Leeres Feld holt "
     "die ganze Liste zurück.\n", "bullet"),
    ("• Community-Guide: ", "bullet"),
    ("Klicke in der Leiste auf ", "bullet"),
    ("Community guide ↗", "highlight"),
    (", um den von Spielern gepflegten Steam-Guide im Browser zu öffnen.\n", "bullet"),
    ("• Nur zur Ansicht: ", "bullet"),
    ("Hier wird nichts zurückgeschrieben. Der Fortschritt einer laufenden Quest steht "
     "gar nicht im Spielstand, nur ihr Ziel - deshalb lässt er sich auch nicht "
     "anzeigen.\n\n\n", "bullet"),

    ("★ HERSTELLUNG ★\n\n", "header"),
    ("• Was der Reiter zeigt: ", "bullet"),
    ("Jedes Rezept der Werkbänke im Spiel, gruppiert nach Shelter-Modul und nach der "
     "Stufe, die das Modul dafür braucht. Jede Zeile nennt Ergebnis, Zutaten, Dauer "
     "und ob du sofort anfangen könntest. Bei Auswahl listet das Feld darunter jede "
     "Zutat als vorhanden / nötig und hebt hervor, was fehlt.\n", "bullet"),
    ("• Suche: ", "bullet"),
    ("Das Feld über dem Baum sucht in Modul, Rezeptname und Ergebnis - und auch in "
     "den Zutaten, eine Zutat einzutippen beantwortet also \"was kann ich damit "
     "überhaupt anfangen?\" (Fokus mit ", "bullet"),
    ("Ctrl+F", "highlight"),
    ("). Treffer werden aufgeklappt gezeigt.\n", "bullet"),
    ("• Noch nicht im Spiel: ", "bullet"),
    ("Manche Rezepte verlangen eine Werkbankstufe, für die es keinen Bauschritt gibt "
     "- der 3D-Printer endet bei Stufe 1 und hat Rezepte für 2 und 3. Die sind "
     "markiert und nicht als machbar gelistet.\n", "bullet"),
    ("• Recyceln steht anderswo: ", "bullet"),
    ("Es ist dieselbe Rezeptliste von der Gegenstandsseite und steht deshalb in der "
     "Gegenstandsinfo, wo du den Gegenstand in der Hand hast. Nur zur Ansicht, wie "
     "der Quests-Reiter.\n\n\n", "bullet"),

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
    ("Fünf Knöpfe mit einem Klick. ", "bullet"),
    ("Alle Skills maximieren", "highlight"),
    (" und ", "bullet"),
    ("Händlerguthaben auffüllen", "highlight"),
    (" (je 1.000.000) tun, was sie sagen. ", "bullet"),
    ("Alle Gegenstände reparieren", "highlight"),
    (" bringt alles auf sein Maximum, ", "bullet"),
    ("Alles auf fabrikneu", "highlight"),
    (" nimmt stattdessen den Verschleißeintrag weg und geht damit weiter: der "
     "Spielstand liest sich danach wie nie benutzt. ", "bullet"),
    ("Alle Stapel auffüllen", "highlight"),
    (" füllt jeden Stapel bis zu dem, was der jeweilige Gegenstand fasst. Die "
     "letzten beiden fragen vorher und sagen hinterher, wie viel sie angefasst "
     "haben; geschrieben wird nichts, bevor du übernimmst.\n\n\n", "bullet"),

    ("★ RAW JSON ★\n\n", "header"),
    ("• Was der Reiter zeigt: ", "bullet"),
    ("Die vollständige formatierte JSON-Darstellung des im Speicher geladenen Spielstands. "
     "Zeigt sowohl gespeicherte als auch ausstehende Änderungen mit exakten IDs, Zahlen und Struktur.\n",
     "bullet"),
    ("• Suche: ", "bullet"),
    ("Groß-/Kleinschreibung ignorierende Volltextsuche mit Live-Trefferzähler und "
     "Weiterschalten über Vor / Zurück (Enter / Shift+Enter). Schnellsprung mit ", "bullet"),
    ("Ctrl+F", "highlight"),
    (".\n", "bullet"),
    ("• Zeilenumbruch & Kopieren: ", "bullet"),
    ("Zeilenumbruch umschalten, um horizontales Scrollen zu vermeiden, oder den gesamten "
     "JSON-Inhalt mit einem Klick in die Zwischenablage kopieren. Schreibgeschützt.\n\n\n",
     "bullet"),

    ("★ TASTATURKÜRZEL ★\n\n", "header"),
    ("• Globale Kürzel: ", "bullet"),
    ("Über das gesamte Hauptfenster hinweg verfügbar:\n", "bullet"),
    ("  - Ctrl+S: ", "highlight"),
    ("Änderungen in die Spielstandsdatei übernehmen (öffnet die Prüfliste und sichert vorher ein Backup).\n", "bullet"),
    ("  - Ctrl+F: ", "highlight"),
    ("Springt direkt mit dem Cursor in das Suchfeld des aktuell aktiven Reiters (Inventar, Katalog, Quests, Herstellung oder Raw JSON).\n", "bullet"),
    ("• Inventarbaum-Kürzel: ", "bullet"),
    ("Aktiv bei der Navigation im Inventarbaum:\n", "bullet"),
    ("  - Shift+Klick / Strg+Klick: ", "highlight"),
    ("Wählt einen Bereich oder einzelne Gegenstände für gemeinsame Aktionen aus.\n", "bullet"),
    ("  - Del: ", "highlight"),
    ("Ausgewählte(n) Gegenstand samt Anbauten löschen.\n", "bullet"),
    ("  - Ctrl+D: ", "highlight"),
    ("Ausgewählte(n) Gegenstand duplizieren.\n", "bullet"),
    ("  - Ctrl+R: ", "highlight"),
    ("Ausgewählte(n) Gegenstand auf 100% Haltbarkeit reparieren.\n", "bullet"),
    ("  - Ctrl+M: ", "highlight"),
    ("Ausgewählte(n) Gegenstand in einen anderen Behälter verschieben.\n", "bullet"),
    ("  - Ctrl+I: ", "highlight"),
    ("Ausführliches Info-Fenster zum Gegenstand öffnen.\n", "bullet"),
    ("  - Ctrl+A: ", "highlight"),
    ("Alle aktuell sichtbaren Zeilen im gewählten Behälter markieren.\n", "bullet"),
    ("• Raw-JSON-Navigation: ", "bullet"),
    ("Bei der Textsuche im Raw-JSON-Reiter springt ", "bullet"),
    ("Enter", "highlight"),
    (" zum nächsten Treffer und ", "bullet"),
    ("Shift+Enter", "highlight"),
    (" zum vorherigen Treffer.\n\n\n", "bullet"),

    ("★ ÄNDERUNGEN SPEICHERN ★\n\n", "header"),
    ("• Änderungen übernehmen: ", "bullet"),
    ("Klicke oben rechts auf ", "bullet"),
    ("Änderungen übernehmen", "highlight"),
    (" (oder drücke ", "bullet"),
    ("Ctrl+S", "highlight"),
    ("), um alle Änderungen in deine Datei zu schreiben. Es zeigt vorher die Liste dessen, "
     "was geschrieben werden soll - jeder neue Gegenstand, jeder entfernte, jedes geänderte Feld mit Wert vorher und nachher - "
     "und wartet auf ein Ja. Bei Abbruch wird nichts geschrieben. Verglichen wird mit der Datei auf der Platte, du siehst also auch, was das Spiel nebenher geändert hat.\n", "bullet"),
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
     "jedes Backup erhalten.\n", "bullet"),
    ("• Zurück: ", "bullet"),
    ("Backup zurückspielen...", "highlight"),
    (" setzt eines an die Stelle deines Spielstands. Der aktuelle Stand wird vorher "
     "weggesichert, das Zurückspielen ist also selbst umkehrbar. Im Ordner wird nichts "
     "gelöscht, und eine Datei, die dieser Editor nicht geschrieben hat, wird gar "
     "nicht erst angeboten.\n", "bullet"),
    ("• Statusleisten-Optionen: ", "bullet"),
    ("Die Leiste am unteren Rand enthält den Schalter für die Hintergrundmusik (", "bullet"),
    ("🔇 / 🔊", "highlight"),
    ("), die Sprachauswahl (US, DE, RU) und die Backup-Aufbewahrung. Ein Wert von 0 bei ", "bullet"),
    ("Backups behalten", "highlight"),
    (" bewahrt alle bisherigen Sicherungen dauerhaft auf.\n\n\n", "bullet"),

    ("★ PROJEKT UNTERSTÜTZEN ★\n\n", "header"),
    ("• Auf Ko-fi unterstützen: ", "bullet"),
    ("Wenn dir dieser kostenlose Speicherstand-Editor gefällt, kannst du die Entwicklung auf Ko-fi unterstützen:\n", "bullet"),
    ("https://ko-fi.com/sirnr1\n", "link"),
]


HELP_TEXT_RU = [
    ("★ СОБРАНО ДЛЯ ВЕРСИИ ИГРЫ ", "header"),
    ("{game_build} ★\n\n", "header"),
    ("• Проверено на: ", "bullet"),
    ("Cargo Hunters {game_build} (сборка Steam {game_build_steam}, "
     "{game_build_date}). Обновление игры может добавить предметы или изменить "
     "содержимое сохранения. Если игра новее, сначала выполните ", "bullet"),
    ("Обновить имена из игры", "highlight"),
    (" - это уже исправит новые предметы, показанные как сырые ID.\n\n\n", "bullet"),

    ("★ ОБНОВЛЕНИЕ ИГРОВЫХ ИМЕН ★\n\n", "header"),
    ("• Сканирование ресурсов: ", "bullet"),
    ("Нажмите кнопку ", "bullet"),
    ("Обновить имена из игры", "highlight"),
    (" в правом верхнем углу окна. Это просканирует файлы игры для сопоставления зашифрованных ID с реальными именами предметов, навыков и торговцев - и прочитает данные о квестах, рецептах, сборках оружия, NPC, торговцах и уровнях, которые нужны вкладкам Quests, Crafting и Character.\n\n", "bullet"),

    ("• Перезагрузить сохранение: ", "bullet"),
    ("Игра записывает сохранение по окончании рейда. Если редактор остаётся открытым во время игры, нажмите ", "bullet"),
    ("Перезагрузить сохранение", "highlight"),
    (", вместо того чтобы перезапускать его. Несохранённые изменения этого не переживут - сначала будет задан вопрос.\n\n", "bullet"),

    ("• Безопасный процесс редактирования: ", "bullet"),
    ("Редактируйте и сохраняйте изменения только тогда, когда игра находится в главном меню или в убежище. Никогда не сохраняйте изменения во время активного рейда — игра полностью перезаписывает файл сохранения при выходе или смерти, уничтожая ваши правки.\n\n\n", "bullet"),

    ("★ РЕДАКТОР ИНВЕНТАРЯ ★\n\n", "header"),
    ("• Область контейнеров (Scope): ", "bullet"),
    ("Используйте выпадающий список Scope над деревом для переключения между всеми контейнерами, рюкзаком, слотами экипировки или отдельными вкладками склада (0–N). Убежище не имеет сеточной структуры в файлах игры и поэтому недоступно для перемещения или спавна.\n", "bullet"),
    ("• Развернуть папки: ", "bullet"),
    ("Дважды щелкните", "highlight"),
    (" по папкам категорий, чтобы показать их содержимое. Строка вида «5 стаков, "
     "95 единиц» раскрывается так же — по строке на стак, и действие над такой "
     "строкой касается только этого стака.\n", "bullet"),
    ("• Поиск: ", "bullet"),
    ("Введите название, категорию или идентификатор и нажмите Enter (или ", "bullet"),
    ("Ctrl+F", "highlight"),
    (" для быстрого перехода в строку поиска). В дереве "
     "останутся только совпадения, а найденное внутри контейнера раскроет этот "
     "контейнер. Пустое поле снова показывает всё. Поиск идёт только по выбранной "
     "области, поэтому сначала выберите вкладку.\n", "bullet"),
    ("• Цвета категорий: ", "bullet"),
    ("Включите флажок ", "bullet"),
    ("Цвета категорий", "highlight"),
    (" на панели инструментов для подсветки строк по типам предметов (оружие, типы патронов, броня, медицина и др.).\n", "bullet"),
    ("• Множественный выбор & Выделить всё: ", "bullet"),
    ("Удерживайте Shift или Ctrl при клике или нажмите ", "bullet"),
    ("Ctrl+A", "highlight"),
    (" при фокусе на дереве инвентаря, чтобы выделить все видимые строки в текущем контейнере. Действия контекстного меню (Удалить, Починить, Дублировать, Переместить) применяются ко всем выбранным предметам одновременно.\n", "bullet"),
    ("• Состояние, прочность и как новое: ", "bullet"),
    ("В дереве отображается ", "bullet"),
    ("COND", "highlight"),
    (" (шкала 0–4.0) для износа оружия, брони и конечностей, и ", "bullet"),
    ("DUR", "highlight"),
    (" для зарядов расходников (например, аптечек, ремнаборов). Починка восстанавливает максимальную прочность, а ", "bullet"),
    ("Как новое (Mint)", "highlight"),
    (" полностью удаляет записи об износе, возвращая предмету идеальное заводское состояние.\n", "bullet"),
    ("• Управление предметами: ", "bullet"),
    ("Нажмите правой кнопкой мыши", "highlight"),
    (" по любому предмету для открытия контекстного меню:\n", "bullet"),
    ("  - Починить предмет (Ctrl+R): ", "highlight"),
    ("Восстанавливает прочность предмета до 100%.\n", "bullet"),
    ("  - Дублировать предмет (Ctrl+D): ", "highlight"),
    ("Создаёт копию и спрашивает, в какой контейнер её поместить; по умолчанию — контейнер оригинала, Входящие доступны всегда.\n", "bullet"),
    ("  - Переместить предмет... (Ctrl+M): ", "highlight"),
    ("Переносит предмет в другой контейнер. Навески перемещаются вместе с ним, а "
     "надетый предмет освобождает свой слот. Убежище не предлагается: игровые файлы "
     "не описывают его сетку, и редактор не угадывает размер.\n", "bullet"),
    ("  - Разделить стак...: ", "highlight"),
    ("Отделяет часть стака во второй стак. Хотя бы одна штука остаётся на месте: "
     "отделить всё — это перемещение, а не разделение.\n", "bullet"),
    ("  - Задать размер стака...: ", "highlight"),
    ("Записывает, сколько единиц в стаке, вплоть до вместимости предмета. В отличие "
     "от дублирования свободная клетка не нужна. То, что игра никогда не стакала, "
     "стаком не становится.\n", "bullet"),
    ("  - Починить до... -> как новое: ", "highlight"),
    ("Галочка в этом окне делает обратное установке значения: она убирает состояние, "
     "отметку о том, с чем предмет пришёл, и заряды. Именно это игра считает новым "
     "состоянием — починка до максимума остаётся починкой, потому что игра хранит "
     "запись о том, что предмет был повреждён.\n", "bullet"),
    ("  - Навесное...: ", "highlight"),
    ("Ставит части на предмет и снимает их обратно. Окно показывает слоты этого "
     "предмета с тем, что в них стоит, и ваши предметы, на которые он подходит — "
     "только ту половину, которая применима. Свободный слот предлагает ровно те "
     "части, которые игра там допускает, из того, что у вас есть. Слоты есть у "
     "оружия, частей оружия, частей тела и шлемов. Сохранённый размер носителя не "
     "меняется — выросшее оружие может занять в контейнере больше места.\n",
     "bullet"),
    ("  - Информация о предмете (Ctrl+I): ", "highlight"),
    ("Всё, что известно о предмете, только для чтения: цена, вес, размер, что даёт "
     "переработка на каждом уровне модуля — доступный вашему переработчику отмечен — "
     "и в каких рецептах предмет является ингредиентом. Для оружия — ещё и "
     "подходящие патроны и точки крепления в виде дерева: дульное устройство "
     "ставится на ствол, ствол в ресивер, ресивер в оружие. И не только оружие: у "
     "частей тела и шлемов слоты тоже есть — рука показывает гидравлику и структуру, "
     "шлем своё забрало. Откройте забрало — оно назовёт шлем.\n", "bullet"),
    ("  - Удалить предмет (Del): ", "highlight"),
    ("Удаляет предмет вместе со всем, что к нему присоединено. Чтобы снять только "
     "одно вложение, разверните предмет и нажмите правой кнопкой по строке самого "
     "вложения. Вкладки склада и корневые контейнеры удалить нельзя - они часть "
     "структуры сохранения, а не предметы.\n\n\n", "bullet"),
    
    ("★ СПАВН ПРЕДМЕТОВ (КАТАЛОГ) ★\n\n", "header"),
    ("• Поиск и фильтрация: ", "bullet"),
    ("Фильтруйте по категориям или ищите предметы по названию (фокус с помощью ", "bullet"),
    ("Ctrl+F", "highlight"),
    ("). Включите ", "bullet"),
    ("Цвета категорий", "highlight"),
    (" для подсветки или флажок ", "bullet"),
    ("Только новые", "highlight"),
    (" после обновления имен, чтобы увидеть новинки.\n", "bullet"),
    ("• Спавн предметов: ", "bullet"),
    ("Щёлкните предмет в списке правой кнопкой и выберите ", "bullet"),
    ("Добавить в инвентарь...", "highlight"),
    (". Одно окно спрашивает сколько, куда и - у предметов, которые его имеют - "
     "с каким состоянием они появятся. При максимуме предмет создаётся идеальным: "
     "именно так игра хранит нетронутый предмет.\n", "bullet"),
    ("• Оружие в сборе: ", "bullet"),
    ("Правый клик по огнестрельному оружию и ", "bullet"),
    ("Создать в сборе...", "highlight"),
    (" выдаёт его таким, каким его собирает сама игра: магазин, ствол, приклад и "
     "прицел уже стоят в слотах. Такая сборка есть у {preset_total} единиц оружия, "
     "у некоторых "
     "несколько — тогда вы выбираете вариант и видите, что несёт каждый. Входящие "
     "здесь не предлагаются: доставка оружия с частями почтой не проверена.\n",
     "bullet"),
    ("• Нужно место: ", "bullet"),
    ("сколько места занимает оружие в сборе, игра считает сама, а то, что не может "
     "разместить, отправляет в почтовый ящик. Поэтому редактор держит свободным "
     "максимальный размер оружия: маленькая сумка отклоняется сразу, а полный отсек "
     "отвечает «нет места» вместо того, чтобы создать предмет, который придёт "
     "письмом.\n", "bullet"),
    ("• Превышение размера оружия и почта: ", "bullet"),
    ("{preset_outgrown} из {preset_total} вариантов собранного оружия со всеми обвесами превышают стандартные размеры сетки. Движок игры обрабатывает негабаритное оружие, отправляя его в почтовый ящик при загрузке. Редактор резервирует полную расширенную площадь оружия, исключая перекрытия.\n", "bullet"),
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

    ("★ КВЕСТЫ ★\n\n", "header"),
    ("• Что показывает вкладка: ", "bullet"),
    ("Все квесты игры против тех, что встречались в вашем сохранении - по группам "
     "и по статусу: активные, завершённые и ни разу не встреченные. Ветки "
     "«ни разу» раскрыты сразу. Выберите квест, чтобы увидеть полный текст, "
     "что он требует, кто его присылает и что даёт.\n", "bullet"),
    ("• Поиск: ", "bullet"),
    ("Поле над деревом ищет по названию квеста, тексту задания, отправителю, группе "
     "и внутреннему идентификатору (фокус с ", "bullet"),
    ("Ctrl+F", "highlight"),
    ("). То, что осталось, показывается раскрытым. Пустое поле возвращает весь "
     "список.\n", "bullet"),
    ("• Руководство сообщества: ", "bullet"),
    ("Нажмите кнопку ", "bullet"),
    ("Community guide ↗", "highlight"),
    (" на панели, чтобы открыть руководство игроков в браузере.\n", "bullet"),
    ("• Только для просмотра: ", "bullet"),
    ("Здесь ничего не записывается. Прогресса активного квеста в сохранении нет "
     "вообще - есть только его цель, поэтому показать его тоже нельзя.\n\n\n",
     "bullet"),

    ("★ КРАФТ ★\n\n", "header"),
    ("• Что показывает вкладка: ", "bullet"),
    ("Каждый рецепт верстаков игры, сгруппированный по модулю убежища и по уровню, "
     "который этот модуль требует. В строке — что даёт, что требует, сколько идёт и "
     "можно ли начать сейчас. При выборе панель снизу перечисляет каждый ингредиент "
     "как в наличии / нужно и выделяет то, чего не хватает.\n", "bullet"),
    ("• Поиск: ", "bullet"),
    ("Поле над деревом ищет по модулю, названию рецепта и тому, что он даёт - а ещё "
     "по тому, что он расходует, так что ввод ингредиента отвечает на вопрос «а что "
     "с этим вообще можно сделать?» (фокус с ", "bullet"),
    ("Ctrl+F", "highlight"),
    ("). Совпадения показываются раскрытыми.\n", "bullet"),
    ("• Ещё нет в игре: ", "bullet"),
    ("Некоторые рецепты требуют уровня верстака, для которого в игре нет шага "
     "постройки: 3D-принтер заканчивается на уровне 1 и несёт рецепты для 2 и 3. Они "
     "помечены, а не показаны как доступные.\n", "bullet"),
    ("• Переработка — в другом месте: ", "bullet"),
    ("Это тот же список рецептов со стороны предмета, поэтому он в информации о "
     "предмете, где предмет у вас в руках. Только просмотр, как вкладка квестов.\n\n\n",
     "bullet"),

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
    ("Пять кнопок в один клик. ", "bullet"),
    ("Макс. все навыки", "highlight"),
    (" и ", "bullet"),
    ("Заполнить баланс торговцев", "highlight"),
    (" (по 1 000 000) делают ровно то, что написано. ", "bullet"),
    ("Починить все вещи", "highlight"),
    (" доводит всё до максимума, а ", "bullet"),
    ("Всё как новое", "highlight"),
    (" вместо этого убирает саму запись об износе и идёт дальше: сохранение потом "
     "читается как ни разу не использованное. ", "bullet"),
    ("Заполнить все стаки", "highlight"),
    (" доводит каждый стак до вместимости самой вещи. Последние два сначала "
     "спрашивают, а потом сообщают, скольких вещей коснулись; до применения ничего "
     "не записывается.\n\n\n", "bullet"),

    ("★ RAW JSON ★\n\n", "header"),
    ("• Что показывает вкладка: ", "bullet"),
    ("Полный отформатированный JSON загруженного в память сохранения. Отображает "
     "как сохранённые, так и ожидающие применения изменения с точными ID, числами и структурой.\n",
     "bullet"),
    ("• Поиск: ", "bullet"),
    ("Полнотекстовый поиск без учёта регистра со счётчиком совпадений и "
     "навигацией вперёд / назад (Enter / Shift+Enter). Быстрый переход по ", "bullet"),
    ("Ctrl+F", "highlight"),
    (".\n", "bullet"),
    ("• Перенос строк и копирование: ", "bullet"),
    ("Переключение переноса строк для удобного чтения без горизонтальной прокрутки, "
     "или копирование всего JSON в буфер обмена одной кнопкой. Только чтение.\n\n\n",
     "bullet"),

    ("★ ГОРЯЧИЕ КЛАВИШИ ★\n\n", "header"),
    ("• Глобальные комбинации: ", "bullet"),
    ("Доступны во всём главном окне:\n", "bullet"),
    ("  - Ctrl+S: ", "highlight"),
    ("Применить изменения и сохранить файл (показывает список изменений и создаёт резервную копию).\n", "bullet"),
    ("  - Ctrl+F: ", "highlight"),
    ("Перейти в поле поиска активной вкладки (Инвентарь, Каталог, Квесты, Крафт или Raw JSON).\n", "bullet"),
    ("• Комбинации в дереве инвентаря: ", "bullet"),
    ("Работают при навигации по предметам:\n", "bullet"),
    ("  - Shift+Клик / Ctrl+Клик: ", "highlight"),
    ("Выделяет диапазон или переключает отдельные предметы для массовых действий.\n", "bullet"),
    ("  - Del: ", "highlight"),
    ("Удалить выбранные предметы со всеми навесками.\n", "bullet"),
    ("  - Ctrl+D: ", "highlight"),
    ("Дублировать выбранные предметы.\n", "bullet"),
    ("  - Ctrl+R: ", "highlight"),
    ("Починить выбранные предметы до 100% прочности.\n", "bullet"),
    ("  - Ctrl+M: ", "highlight"),
    ("Переместить выбранные предметы в другой контейнер.\n", "bullet"),
    ("  - Ctrl+I: ", "highlight"),
    ("Открыть окно детальной информации о предмете.\n", "bullet"),
    ("  - Ctrl+A: ", "highlight"),
    ("Выделить все видимые строки в текущем контейнере.\n", "bullet"),
    ("• Навигация в Raw JSON: ", "bullet"),
    ("При поиске в Raw JSON нажмите ", "bullet"),
    ("Enter", "highlight"),
    (" для перехода к следующему совпадению или ", "bullet"),
    ("Shift+Enter", "highlight"),
    (" для перехода к предыдущему совпадению.\n\n\n", "bullet"),

    ("★ СОХРАНЕНИЕ ИЗМЕНЕНИЙ ★\n\n", "header"),
    ("• Применить изменения: ", "bullet"),
    ("Нажмите ", "bullet"),
    ("Применить изменения", "highlight"),
    (" (или нажмите ", "bullet"),
    ("Ctrl+S", "highlight"),
    (") в правом верхнем углу для сохранения файла. Сначала показывается список того, "
     "что будет записано: каждый новый предмет, каждый удалённый, каждое изменённое поле со значением до и после — и ждёт "
     "подтверждения. При отмене ничего не записывается. Сравнение идёт с файлом на диске, поэтому видно и то, что изменила сама игра.\n", "bullet"),
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
     "Значение 0 сохраняет все копии.\n", "bullet"),
    ("• Возврат: ", "bullet"),
    ("Восстановить копию...", "highlight"),
    (" ставит копию на место сохранения. Текущее сохранение сначала копируется "
     "в сторону, так что и само восстановление обратимо. В папке ничего не "
     "удаляется, а файл, который редактор не создавал, не предлагается вовсе.\n",
     "bullet"),
    ("• Элементы строки состояния: ", "bullet"),
    ("В нижней панели находятся переключатель фоновой синтвейв-музыки (", "bullet"),
    ("🔇 / 🔊", "highlight"),
    ("), переключатель языка (US, DE, RU) и счетчик хранения резервных копий. Значение 0 в поле ", "bullet"),
    ("Хранить копий", "highlight"),
    (" гарантирует постоянное сохранение всех созданных ранее бэкапов.\n\n\n", "bullet"),

    ("★ ПОДДЕРЖАТЬ ПРОЕКТ ★\n\n", "header"),
    ("• Поддержать на Ko-fi: ", "bullet"),
    ("Если вам нравится этот бесплатный редактор, вы можете поддержать разработку по ссылке:\n", "bullet"),
    ("https://ko-fi.com/sirnr1\n", "link"),
]
