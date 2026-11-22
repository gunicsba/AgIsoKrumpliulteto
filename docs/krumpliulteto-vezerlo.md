# ISOBUS krumpliültető vezérlő – tervezési jegyzet

## 1. Áttekintés

Saját ISOBUS implement ECU egy krumpliültetőhöz.

| Elem | Darab | Szerep |
|---|---|---|
| Villanymotor | 1 | Az adagoló (csészesor) hajtása – minden sort egy motor hajt |
| Munkakapcsoló | 1 | Gép leengedve = dolgozik |
| Forgásjeladó | 1 | Motor/tengely pozíció és fordulatszám |

**Felhasználói bemenet:** tőtávolság (cm).

**Hatókör most:** VT kliens + sebesség/távolság olvasás a buszról. **Section Control nincs**, Task Controller nincs (később bővíthető, lásd 8. pont).

---

## 2. Szabályzási elv: távolságkövetés („elektronikus fogaskerék”)

Sebességkövetés helyett a megtett távolsághoz kötjük a motor pozícióját.

- **Sebességalapú** (csak fordulatszám-szabályzás): egyszerű, de gyorsításnál/lassításnál/megállásnál a hiba halmozódik, kis sebességnél a sebességjel zajos és késik.
- **Távolságalapú** (pozíciókövetés): a hiba nem halmozódik, megállás → újraindulás után pontosan folytatja. **Ezt választjuk.**

### 2.1 Képletek

```
csésze_per_ford      : csészék száma a jeladó tengelyének egy fordulatára (áttétellel együtt)
tőtáv [m]            : felhasználói beállítás
v [m/s]              : kiválasztott sebességforrás
d [m]                : megtett távolság (munkakapcsolóval kapuzva)

cél_pozíció [ford]   = d / (tőtáv * csésze_per_ford)
előcsatolás [ford/s] = v / (tőtáv * csésze_per_ford)
```

### 2.2 Szabályzó struktúra

```
ff       = v / (tőtáv * csésze_per_ford)
pos_err  = cél_pozíció - tényleges_pozíció
pos_err  = clamp(pos_err, -max_lemaradás, +max_lemaradás)
n_cél    = ff + Kp_pos * pos_err

belső hurok: PI(n_cél - n_tényleges) -> PWM
```

- Az **előcsatolás** végzi a munka nagy részét, a pozícióhurok csak korrigál.
- A **clamp** megakadályozza, hogy elakadás/leállás után a motor egyszerre próbálja behozni a lemaradást (gumók egymásra kerülnének).
- Ha `|pos_err|` tartósan eléri a `max_lemaradás` értéket → **riasztás**, a többletet el kell dobni (a cél pozíciót a tényleges közelébe húzni).

### 2.3 Hasznos származtatott értékek

```
tő/ha     = 10000 / (sortáv [m] * tőtáv [m])
tőtáv [m] = 10000 / (sortáv [m] * tő/ha)
```

A belső rátát érdemes **tő/ha-ban** tárolni, a tőtáv csak megjelenítés és bevitel – így egy későbbi TC-GEO nem igényel átírást.

---

## 3. Sebesség- és távolságforrás (ISOBUS)

Prioritási sorrend:

| Prioritás | Üzenet | PGN | Megjegyzés |
|---|---|---|---|
| 1 | Machine Selected Speed | 0xF022 (61474) | Traktor által választott forrás, van benne halmozott távolság és irány |
| 2 | Ground-based Speed and Distance | 0xFE48 (65096) | Radar / GNSS |
| 3 | Wheel-based Speed and Distance | 0xFE49 (65097) | Csúszik – csak végső tartalék |

Kezelendő:

- **Felbontás:** sebesség 0,001 m/s, távolság 0,001 m (ellenőrizni az adott traktoron).
- **Érvénytelen érték** (0xFFFF / 0xFFFFFFFF, ill. a „not available” tartomány) → forrás kiesett.
- **Távolság-átfordulás:** a halmozott távolság számláló átfordul, mindig **különbséget** számolj (`Δd = d_most - d_előző`, előjeles, átfordulással).
- **Időtúllépés:** ha egy forrás ~300–500 ms-ig nem jön, válts a következőre; ha egyik sincs → motor áll + riasztás.
- **Csak sebesség van, távolság nincs:** integráld a sebességet (`d += v * dt`) – még mindig jobb, mint a puszta sebességkövetés.
- **Állás-holtsáv:** pl. `v < 0,3 km/h` → v = 0, különben a GNSS-zaj „csöpögtet” gumót.
- **Irány:** hátramenetnél ne ültessen (MSS irány bit, ha elérhető).

---

## 4. Munkakapcsoló és a „dolgozik” állapot

A „dolgozik-e” döntést **egy helyen**, egy függvényben számoljuk:

```
dolgozik = munkakapcsoló_lent && v > v_min && sebességforrás_érvényes && !riasztás_tiltó
```

- `dolgozik == false` → a távolság **nem** növeli a cél pozíciót, a motor áll.
- Később ide kerül be a TC-ből jövő section állapot is.
- Munkakapcsoló pergésmentesítése (debounce, pl. 50–100 ms).

### 4.1 Indulás / megállás section control nélkül

- **Emeléskor** a pozícióhibát **befagyasztjuk**, nem nullázzuk → visszaengedéskor pontosan onnan folytatja, nincs dupla vagy kihagyott gumó a forduló után.
- Opcionális paraméter: **indulási előretolás** (néhány cm vagy csésze), ha a szélen kell korrekció.

---

## 5. Forgásjeladó

- Lehetőleg a **motortengelyen** (hajtómű előtt) → nagy felbontás a pozícióhurokhoz.
- Kalibráció:
  - `impulzus_per_csésze` – forgatásos kalibrálás: „forgass N csészét, számold az impulzusokat”, vagy
  - áttétel + csészék száma fordulatonként megadva.
- **Elakadás / láncszakadás figyelés:**
  - nagy PWM, de nincs impulzus → elakadás
  - impulzus van, de a terhelés (áram) gyanúsan kicsi → lánc/hajtás szakadás (ha van áramméréses adat)

---

## 6. VT felület (minimális)

### Munkaképernyő
- Cél tőtáv (cm) – bevitel
- Tényleges tőtáv (cm), számolt tő/ha
- Sebesség + forrás (MSS / Ground / Wheel / nincs)
- Munkakapcsoló állapot
- Motor állapot / terhelés (%)
- Számlálók: terület (ha), gumószám (napi / összes, nullázható)

### Beállítások / kalibráció
- Sortáv, sorok száma (területszámításhoz)
- `impulzus_per_csésze` vagy áttétel + csészeszám
- Szabályzó paraméterek (`Kp_pos`, PI erősítések, `max_lemaradás`) – szerviz szint
- Indulási előretolás
- Sebesség-holtsáv

### Riasztások
- Elakadás
- Nagy lemaradás (`max_lemaradás` elérve)
- Nincs sebességjel
- Motor túláram / meghajtó hiba

### Softkey-ek
- Számláló nullázás
- Tőtáv +/- lépés

AUX-N funkciók (opcionális): tőtáv +/-.

---

## 7. Biztonság / hibakezelés

- Bármely tiltó riasztás → motor áll.
- Busz-kiesés (nincs sebesség) → motor áll, riasztás.
- Forgatásos kalibráció csak álló gépnél és felemelt munkakapcsolónál.
- Motor indulási áramkorlát, lágyindítás.

---

## 8. Későbbi bővítés (most NEM része)

1. **TC-BAS** – összesítők (terület, gumószám) a TC felé, minimális DDOP egy elemmel.
2. **TC-SC** – egy section (az egy motor miatt az egész szélesség), be/kikapcsolási késleltetések és elem-offszetek a DDOP-ban; a csésze → lerakási pont úthossza ide kerül.
3. **TC-GEO** – ráta tő/ha-ban (setpoint count per area), a belső tőtáv ebből számolva.

---

## 9. Nyitott kérdések

- [ ] Motor típusa, feszültség, meghajtó (áramméréssel?)
- [ ] Jeladó helye és felbontása, áttétel
- [ ] Csészék száma / fordulat
- [ ] Sortáv, sorszám
- [ ] Szükség van-e kézi sebességforrásra (pl. saját radar / GNSS) nem ISOBUS traktorhoz?
