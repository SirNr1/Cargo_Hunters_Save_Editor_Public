"""Erzeugt CH_Editor/app_icon.ico - den Frachtcontainer, den Fenster und .exe tragen.

Aufruf: `python Scripts/make_app_icon.py`. Die erzeugte Datei liegt im Repository; dieses
Skript ist da, damit sie sich nachziehen laesst, statt eine Binaerdatei zu sein, die niemand
mehr aendern kann.

Gezeichnet wird **pro Groesse einzeln.**

Eine .ico traegt pro Groesse ein eigenes Bild. Das ist hier nicht Kosmetik: bei 16 px sind
zwoelf Rippen schmaler als ein Pixel und laufen zu einem blauen Klotz zusammen - gemessen im
ersten Entwurf. Also bekommt jede Groesse so viele Rippen, wie sie noch trennen kann, und die
Fuesse und der Rahmenring fallen unten heraus, wo sie nur noch Matsch waeren.
"""
from pathlib import Path

from PIL import Image, ImageDraw

SCHIEFER, BLAU, HELLBLAU = (26,29,35,255), (51,153,255,255), (150,210,255,255)

def zeichne(S):
    im = Image.new("RGBA", (S,S), (0,0,0,0)); d = ImageDraw.Draw(im)
    e = S/256.0                                   # alles in Anteilen der Kantenlaenge
    def p(v): return v*e

    # Rahmen: Ring erst ab 32 px, darunter frisst die Linie den Inhalt.
    ring = BLAU if S >= 32 else None
    d.rounded_rectangle([p(4), p(4), S-p(4), S-p(4)], radius=p(48),
                        fill=SCHIEFER, outline=ring, width=max(1, int(p(6))))

    # So viele Rippen, wie die Groesse noch trennen kann. Jede Rippe braucht mindestens
    # zwei Pixel Nut, sonst verschmilzt sie mit der naechsten.
    rippen = {16: 3, 24: 4, 32: 5, 48: 7}.get(S, 11)

    # Je kleiner die Kachel, desto mehr davon gehoert dem Container. Bei 256 px darf um ihn
    # herum Luft stehen, bei 16 px ist jedes freie Pixel eines, das der Form fehlt - dort
    # bleibt nur der schmale Saum, der ihn gegen eine helle Taskleiste absetzt.
    rand, oben, unten = ((p(40), p(80), p(180)) if S >= 48 else
                         (p(26), p(58), p(200)) if S >= 24 else
                         (p(18), p(46), p(212)))
    x0, x1 = rand, S-rand
    d.rectangle([x0, oben, x1, unten], fill=BLAU)

    # Dachkante hell - sie gibt dem Klotz auch bei 16 px noch eine Oberseite.
    d.rectangle([x0, oben, x1, oben + max(1, p(16))], fill=HELLBLAU)

    # Die Rippen duerfen die untere Kante nicht auffressen. Bei 24 px war p(8) weniger als
    # ein Pixel, der Rahmen fiel weg, und aus dem Container wurde ein Zaun.
    breite = (x1-x0) / (rippen*2 + 1)
    fuss = max(1.0, p(8))
    for i in range(rippen):
        rx = x0 + breite*(i*2 + 1)
        d.rectangle([rx, oben + max(1.0, p(26)), rx + breite, unten - fuss], fill=SCHIEFER)

    # Fuesse nur, wo sie noch als zwei getrennte Bloecke ankommen.
    if S >= 32:
        f = p(24)
        d.rectangle([x0+p(16), unten, x0+p(16)+f, unten+p(18)], fill=BLAU)
        d.rectangle([x1-p(16)-f, unten, x1-p(16), unten+p(18)], fill=BLAU)
    return im

GROESSEN = [256, 128, 64, 48, 32, 24, 16]

ZIEL = Path(__file__).resolve().parent.parent / "CH_Editor" / "app_icon.ico"

if __name__ == "__main__":
    bilder = [zeichne(s) for s in GROESSEN]
    bilder[0].save(ZIEL, sizes=[(s, s) for s in GROESSEN], append_images=bilder[1:])
    print(f"{ZIEL} geschrieben, Groessen: {GROESSEN}")
