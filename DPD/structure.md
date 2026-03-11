Níže máš **hotový prompt**, který můžeš vložit do **Cursor / AI builderu**, aby vytvořil aplikaci přesně podle zadání. Prompt je napsaný tak, aby byl **maximálně přesný, blbuvzdorný a AI kontrolovala chyby**.

---

# PROMPT PRO VYTVOŘENÍ APLIKACE

Vytvoř jednoduchou, maximálně **blbuvzdornou webovou aplikaci pro evidenci hotovosti**, která bude mít **2 role: Uživatel a Admin**.

Aplikace musí být navržena tak, aby ji dokázal používat **i úplný laik (např. starší člověk)**.
UI musí být **velké, přehledné, minimum textu, velká tlačítka, jasné kroky**.

Použij **PIN login** místo hesla.

---

# ROLE V APLIKACI

## 1️⃣ Uživatel

Uživatel pouze **zadává hodnoty hotovosti**.

Po přihlášení vidí **2 velké sekce**:

1️⃣ **Obálka**
2️⃣ **Zbylo v kasičce**

---

# AUTOMATICKÉ HODNOTY (NESMÍ SE RUČNĚ ZADÁVAT)

Aplikace automaticky doplní:

Datum:

```
DNES()
```

Datum splatnosti:

```
=DNES()-DENTÝDNE(DNES();2)+2
```

Začátek týdne:

```
=DNES()-DENTÝDNE(DNES();2)-6
```

Konec týdne:

```
=DNES()-DENTÝDNE(DNES();2)
```

Uživatel tyto hodnoty **nevidí jako pole k úpravě**.

---

# SEKCE 1 — OBÁLKA

Název sekce:

**OBÁLKA (Hotovost k odevzdání)**

Aplikace vyzve uživatele:

„Zadejte počet bankovek“

Pole pro zadání počtu:

```
5000 Kč
2000 Kč
1000 Kč
500 Kč
200 Kč
100 Kč
```

U každé bankovky:

* velké tlačítko +
* velké tlačítko –
* nebo číslo

Automaticky se počítá:

```
celková částka
```

Na konci sekce velké zobrazení:

```
CELKEM V OBÁLCE: XXXXX Kč
```

---

# SEKCE 2 — ZBYLO V KASIČCE

Název sekce:

**ZBYLO V KASIČCE**

Uživatel zadává počet **bankovek a mincí**

Rozsah:

```
5000 Kč
2000 Kč
1000 Kč
500 Kč
200 Kč
100 Kč
50 Kč
20 Kč
10 Kč
5 Kč
2 Kč
1 Kč
```

Stejný systém:

*

-

nebo číslo

Na konci:

```
CELKEM V KASIČCE: XXXXX Kč
```

---

# ULOŽENÍ

Velké tlačítko:

```
ULOŽIT
```

Po uložení:

* data se uloží do databáze
* zobrazí se potvrzení

```
✔ Data byla uložena
```

---

# EXPORT OBÁLKY (PRO TISK)

Musí existovat tlačítko:

```
VYTISKNOUT OBÁLKU
```

Export musí být optimalizovaný pro **termotiskárnu Brother**

parametry:

šířka papíru

```
62 mm
```

Obsah tisku:

```
Pobočka
Datum
Datum Splatnosti
Týden

5000 Kč   x
2000 Kč   x
1000 Kč   x
500 Kč    x
200 Kč    x
100 Kč    x

CELKEM: XXXX Kč
```

Velký font.

Bez zbytečných prvků.

---

# ADMIN

Admin má **dashboard**.

Vidí tabulku:

```
Datum
Týden
K zaplacení
V hotovosti (Obálka)
Zbylo v kasičce
```

Data jsou rozdělená podle **poboček**.

Například:

```
Pepa – Praha
Evžen – Brno
```

Admin může:

* filtrovat podle pobočky
* filtrovat podle týdne
* zobrazit historii
* exportovat data

---

# LOGIN

Přihlášení pomocí **PIN**

například:

```
Uživatel
PIN
```

PIN je:

* 4–6 číslic
* uložený v databázi

Role:

```
user
admin
```

---

# BLBUVZDORNOST

Aplikace musí:

✔ zabránit záporným hodnotám
✔ zabránit nečíselným hodnotám
✔ automaticky ukládat průběžně
✔ potvrdit každou akci
✔ mít velká tlačítka
✔ minimum textu
✔ jednoduchý postup

Flow:

```
1 Přihlásit se
2 Zadání OBÁLKA
3 Zadání KASIČKA
4 Uložit
5 Vytisknout obálku
```

---

# UI DESIGN

Velmi jednoduché rozhraní:

* velké fonty
* velká tlačítka
* mobilní použití
* max šířka 600px
* vhodné i pro tablet

---

# TECHNICKÉ POŽADAVKY

Aplikace musí:

* být webová (flask,html,js,css)
* fungovat na mobilu
* mít databázi
* mít API
* validovat vstupy
* ukládat historii
* umožnit export

---

# KONTROLA CHYB (DŮLEŽITÉ)

Před dokončením aplikace proveď:

1️⃣ kontrolu logiky výpočtů
2️⃣ kontrolu ukládání dat
3️⃣ kontrolu exportu pro 62mm tisk
4️⃣ kontrolu role admin vs user
5️⃣ kontrolu validace vstupů

Aplikace musí být **odolná proti chybám uživatele**.

---

✅ Výsledek musí být **jednoduchá, přehledná aplikace pro evidenci hotovosti podle poboček**.

---

## Pokud chceš, můžu ti ještě udělat:

* **ještě lepší prompt pro Cursor (10× přesnější)**
* **návrh databáze**
* **UI wireframe**
* **automatické výpočty týdne podle ISO**
* **přímý export do účetnictví**

Stačí říct.
