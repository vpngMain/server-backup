# Upgrade Objednávač – stav implementace

## ✅ Implementováno

### 1. Rebranding
- Název **„Objednávač“** v `<title>`, v headeru (logo), v sidebaru adminu, na přihlašovací stránce
- Meta `application-name`: Objednávač
- Konfigurace: `app.config["APP_NAME"]`, env `APP_NAME` (volitelné přepsání)

### 2. Fakturační stav v objednávce
- V detailu objednávky (sklad) sekce **Faktura**:
  - Tlačítka **✅ Vše cajk** / **❌ Chyba**
  - U „Chyba“ povinná poznámka (pole + validace na backendu)
- Sklad vidí stav (cajk / chyba + poznámka)
- Při odeslání objednávky skladem se zobrazuje **suma objednaných a odeslaných kusů**
- Každá změna fakturačního stavu se zapisuje do **audit logu** (uživatel, datum, typ)

### 3. Audit log a identifikace uživatele
- Tabulka **`audit_log`** (id, created_at, user_id, username, action, entity_type, entity_id, details)
- Funkce **`audit_log(action, entity_type, entity_id, details)`**
- Objednávka má **`created_by_id`** (kdo objednávku vytvořil) – vyplňuje se při odeslání z košíku
- V detailech objednávky (admin, sklad, pobočka) se zobrazuje **„Vytvořil: &lt;username&gt;“**
- Logované akce: vytvoření objednávky, změna stavu, změna odeslaného množství, nemám/mám skladem, faktura cajk/chyba

### 4. Oprava vyhledávání (reset URL)
- Po **smazání** textu ve vyhledávání se URL s parametrem `q` zruší a stránka se **obnoví** (načte se celý seznam produktů)
- Nové vyhledání pak funguje nad kompletním seznamem (žádný „nenajde“ po změně značky)

### 5. Sklad – změna dostupnosti
- U položky označené **„Nemám skladem“** je tlačítko **„Má skladem“**
- POST na `/warehouse/order/<id>/item/<item_id>/available` nastaví `unavailable = False`
- Změna se zapisuje do audit logu

### 6. Suma kusů v objednávce
- **Sklad (detail objednávky):** „Celkem kusů: X objednáno, Y odesláno“
- **Admin (detail objednávky):** „Celkem kusů: X objednáno“
- Hodnoty se počítají z položek objednávky

### Příprava na další body
- **`Order.order_type`** (výchozí `"normal"`) – připraveno pro interní objednávky
- **`Order.created_by_warehouse_id`** – připraveno pro objednávky vytvořené skladem pro pobočku
- Migrace v `app.py`: nové sloupce u `orders`, tabulka `audit_log`

---

## ⏳ Zbývá implementovat

- **7. Live AJAX** – aktualizace bez reloadu (stavy, checkboxy, suma, nové objednávky) – např. polling nebo WebSockets
- **8. Import objednávek / výdejek** – CSV/XLSX, validace
- **9. Podkategorie podle značek** – první slovo názvu = značka, seskupení produktů
- **10. Přehled pro branch** – co nemá sklad z poslední objednávky
- **11. Interní objednávky** – samostatný typ (kancelář), vlastní produkty a seznam
- **12. Admin jako branch/sklad** – přepnutí do režimu pobočky/skladu, vše s logováním
- **13. Sklad vytváří objednávky pro pobočky** – vytvoření objednávky přiřazené pobočce, odlišené označení

---

## Technické poznámky

- **Audit:** všechny nové akce (stav, odesláno, nemám/mám, faktura) volají `audit_log(...)`.
- **Role:** zatím beze změny (admin/warehouse/branch); rozšíření rolí podle bodů 12 a 13 lze doplnit.
- **Validace:** faktura „Chyba“ vyžaduje poznámku na backendu i přes `required` na formuláři.
