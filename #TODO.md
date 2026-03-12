# TODO: Ogma — Zbývající funkcionality

---

## 1. Odvozená Analytika (Backend výpočty)
Statistiky počítané z již uložených dat v DB — nevyžadují nový scraping.

- [ ] **Aktivita v čase (Activity Heatmap)**
  - *Výstup:* Vizuální heatmapa hodin × dní v týdnu, nebo text „Postuje 18:00–22:00"
  - *Cíl:* Určení časového pásma a Pattern of Life (detekce koordinovaného chování)
  - *Zdroj dat:* Sloupec `timestamp_posted` v tabulce `posts`

- [ ] **Nejpoužívanější Hashtagy**
  - *Logika:* Regex extrakce `#\w+` z `text_content`, top 5 z posledních N příspěvků
  - *Cíl:* Rychlá identifikace témat a narativů profilu

- [ ] **Nejčastější zmínky (Mentions)**
  - *Logika:* Regex extrakce `@\w+` z `text_content` příspěvků i komentářů
  - *Cíl:* Mapování sociální bubliny a klíčových vazeb

- [ ] **Poměr témat (Word Cloud / Top slova)**
  - *Logika:* Tokenizace textu, vyloučení stop-slov, top 10–20 slov
  - *Knihovny:* `wordcloud` + `matplotlib` nebo čistý výpis v GUI
  - *Cíl:* Rychlý přehled hlavních témat profilu

---

## 2. Technické "Flagy" (Auto-tagging profilů)
Automatické štítky přiřazované profilům na základě splněných podmínek.

- [ ] **Tag: "Meme Warfare"**
  - *Podmínka:* >50 % příspěvků má `media_url` ale prázdný `text_content`

- [ ] **Tag: "New Account"**
  - *Podmínka:* `joined_date` před méně než 30 dny od data scrape

- [ ] **Tag: "High Impact"**
  - *Podmínka:* Průměrně >1 000 lajků na příspěvek

- [ ] **Tag: "Bot Suspect"** *(nový návrh)*
  - *Podmínka:* Kombinace — nový účet + vysoký following/followers poměr + časté opakující se hashtagy

- [ ] **Uložení flagů do DB**
  - *Schema:* Nový sloupec `flags` (JSON pole) v tabulce `users`
  - *GUI:* Zobrazení tagů jako barevné badges na kartě profilu

---

## 3. Vizualizace dat
Grafické výstupy pro analýzu a prezentaci v diplomové práci.

- [ ] **Activity Heatmap graf**
  - *Knihovna:* `matplotlib` embedded v GUI (CTkFrame s canvas)
  - *Výstup:* Matice 24h × 7 dní s intenzitou aktivity

- [ ] **Síťový graf (Network Graph)**
  - *Knihovna:* `networkx` + `matplotlib`
  - *Data:* Tabulka `connections` (followers/following)
  - *Cíl:* Vizualizace vztahů mezi profily, detekce clusterů

- [ ] **Sentiment v čase**
  - *Graf:* Liniový graf sentiment_score příspěvků/komentářů na časové ose
  - *Cíl:* Identifikace událostí které způsobily nárůst negativního sentimentu

- [ ] **Export grafů**
  - *Formát:* PNG/PDF pro použití v diplomové práci

---

## 4. Export dat

- [ ] **Export do CSV / XLSX**
  - *Knihovna:* `pandas`
  - *Obsah:* Uživatelé, příspěvky, komentáře, sentiment skóre
  - *GUI:* Tlačítko "Exportovat" v záložce Databáze

- [ ] **Export reportu (PDF)**
  - *Obsah:* Shrnutí profilu — metadata, sentiment statistiky, top hashtagy, flagy
  - *Cíl:* Přímý výstup pro prezentaci nebo přílohu diplomové práce

---

## 5. Rozšíření scrapingu

- [ ] **Statické User ID (REST ID) pro X**
  - *Důvod:* Trvalá identifikace nezávislá na změně @handle
  - *Zdroj:* GraphQL response při načítání profilu

- [ ] **Podpora dalších platforem**
  - *Kandidáti:* Facebook (veřejné stránky), Telegram (veřejné kanály)
  - *Priorita:* Nízká — IG a X pokrývají jádro práce

---

## 6. Anti-Detect & Profile Management

- [ ] **User-Agent Persistence per profil**
  - *Implementace:* Uložit `user_agent` do `users.json`, vynutit při startu BaseBot
  - *Pravidlo:* Profil nesmí měnit OS/Browser verzi mezi relacemi

- [ ] **Konzistence rozlišení okna (Viewport)**
  - *Implementace:* Fixní `window_size` per profil uložený v `users.json`

- [ ] **Health Check profilu při startu**
  - *Funkce:* "Jsem přihlášen?", "Je účet shadowbanovaný?"
  - *Akce:* Při fail → update `account_status` v DB, přeskočit těžbu

- [ ] **Podpora Proxy per profil**
  - *Config:* Pole `proxy_url` v `users.json` (formát `http://user:pass@ip:port`)
  - *Implementace:* Injekce do Playwright `launch_persistent_context`

- [ ] **Canvas & WebGL Noise**
  - *Implementace:* JS injection — jemné zašumění pro unikátní fingerprint per profil

- [ ] **AudioContext Fingerprint**
  - *Implementace:* Modifikace audio stacku v `_apply_stealth_scripts()`

- [ ] **Font Enumeration Masking**
  - *Implementace:* Omezení viditelné sady systémových fontů

---

## 7. Account Warming (Zahřívání účtů)

- [ ] **Modul WarmupBot**
  - *Chování:* Scrollování home feedu, náhodné rozklikávání médií, 1–3 lajky za session
  - *Cíl:* Zvýšení „trust score" před spuštěním scrape

- [ ] **Simulace rychlosti čtení**
  - *Logika:* Pauza u dlouhých textů odpovídající ~200 slovům za minutu

- [ ] **Scheduler — pracovní doba profilu**
  - *Logika:* Virtuální timezone per profil, zákaz aktivity v „hluboké noci"

---

## 8. Databáze a Monitoring

- [ ] **Historie akcí a Rate Limiting**
  - *Metrika:* Logovat počet requestů, scrollů za 24h
  - *Limit:* Při překročení → Cooldown 24h

- [ ] **Sloupec `account_status` v tabulce `users`**
  - *Hodnoty:* `Active`, `Cooldown`, `Banned`, `Login Required`
  - *GUI:* Barevný indikátor na kartě profilu