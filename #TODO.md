# TODO: Rozšíření profilů a analytika (X/Twitter)

## 1. Rozšířená Metadata (Scraping)
Data nutná získat přímo z profilu uživatele.
- [ ] **Datum založení účtu (Joined Date)**
  - *Důvod:* Detekce stáří účtu (rozlišení čerstvých botů vs. etablovaných uživatelů).
- [ ] **Lokace (Location)**
  - *Důvod:* Geografické zacílení a ověření relevance.
- [ ] **Webová stránka (Link in Bio)**
  - *Důvod:* Most k dalšímu vyšetřování (Linktree, OnlyFans, firemní weby).
- [ ] **Počet Sledovaných (Following)**
  - *Důvod:* Analýza poměru Followers vs. Following (detekce spamu vs. celebrit).
- [ ] **Statické User ID (REST ID)**
  - *Důvod:* Trvalá identifikace cíle nezávislá na změně @handle.

## 2. Vizuální prvky (GUI)
Prvky pro vizuální identifikaci na kartě profilu.
- [ ] **Banner (Header Image)**
  - *Implementace:* Použít jako pozadí horní části karty (obsahuje další info/loga).
- [ ] **Status Ověření (Verified / Blue Check)**
  - *Implementace:* Ikonka vedle jména pro rozlišení oficiálních zdrojů vs. parodií.

## 3. Odvozená Analytika (Backend výpočty)
Statistiky počítané z uložených příspěvků (bez nutnosti číst text).
- [ ] **Aktivita v čase (Activity Heatmap)**
  - *Výstup:* Graf nebo text (např. "Postuje 18:00 - 22:00").
  - *Cíl:* Určení časového pásma a Pattern of Life.
- [ ] **Nejpoužívanější Hashtagy**
  - *Logika:* Top 5 hashtagů z posledních 50 příspěvků.
  - *Cíl:* Rychlá identifikace témat profilu.
- [ ] **Nejčastější zmínky (Mentions)**
  - *Logika:* Statistika nejčastěji označovaných @uživatelů.
  - *Cíl:* Mapování sociální bubliny a vazeb.
- [ ] **Poměr témat (Word Cloud)**
  - *Logika:* 5 nejčastějších slov (po vyloučení stop-slov/spojek).

## 4. Technické "Flagy" (Auto-tagging)
Automatické štítky na základě splněných podmínek.
- [ ] **Tag: "Meme Warfare"**
  - *Podmínka:* >50 % příspěvků obsahuje obrázek bez textu.
- [ ] **Tag: "New Account"**
  - *Podmínka:* Účet založen před méně než 1 měsícem.
- [ ] **Tag: "High Impact"**
  - *Podmínka:* Průměrně > 1000 lajků na post.

# TODO: Ogma - Advanced Anti-Detect & Profile Management

## 1. Správa Identit a Profilů (Identity Management)
Cíl: Každý profil musí vypadat jako unikátní zařízení s trvalou historií.
- [ ] **User-Agent Persistence**
  - *Implementace:* Uložit string `user_agent` do `users.json`. Při startu `BaseBot` vynutit tento UA namísto defaultního z Chromia.
  - *Pravidlo:* Profil nesmí měnit OS/Browser verze mezi relacemi.
- [ ] **Konzistence rozlišení okna (Viewport)**
  - *Implementace:* Uložit a vynutit fixní `window_size` pro každý profil.
- [ ] **Health Check Profilu**
  - *Funkce:* Rychlý test po startu: "Jsem přihlášen?", "Je účet zamčený/shadowbanovaný?".
  - *Akce:* Pokud fail -> update status v DB, nezačínat těžbu.

## 2. Síťová vrstva a Proxy (Network Layer)
Cíl: Eliminace rizika hromadného IP banu.
- [ ] **Podpora Proxy per Profil**
  - *Config:* Do `users.json` přidat pole `proxy_url` (formát `http://user:pass@ip:port`).
- [ ] **Proxy Middleware v BaseBot**
  - *Implementace:* Injektovat proxy nastavení do `ChromiumOptions` při startu instance.
- [ ] **IP Leak Protection**
  - *Metoda:* Vypnutí WebRTC nebo konfigurace DrissionPage argumentů tak, aby nepropouštěly reálnou IP.
- [ ] **Rotace Mobilních Proxy (Volitelné)**
  - *Logika:* Integrace API pro reset IP (pokud se používají 4G/5G modemy) před startem session.

## 3. Fingerprinting & Anti-Detect
Cíl: Maskování automatizace na úrovni prohlížeče a hardwaru.
- [ ] **Canvas & WebGL Noise**
  - *Implementace:* JS injection při startu stránky. Jemné "zašumění" vykreslování pro unikátní, ale konzistentní fingerprint.
- [ ] **AudioContext Fingerprint**
  - *Implementace:* Jemná modifikace audio stacku (podobně jako u grafiky).
- [ ] **Skrytí automatizace (Stealth Mode)**
  - *Check:* Ověřit `navigator.webdriver = false`. Skrýt příznaky Selenium/Puppeteer (headless detekce).
- [ ] **Font Enumeration**
  - *Implementace:* Omezit nebo mírně upravit sadu viditelných systémových fontů pro každý profil.

## 4. Zahřívání Účtů (Account Warming Strategy)
Cíl: Simulace lidského chování pro zvýšení "trust score" účtu.
- [ ] **Modul WarmupBot**
  - *Chování:* Netěží data. Jde na Home Feed, náhodně scrolluje, rozklikává média.
  - *Interakce:* Low-risk like (1-3x za session).
- [ ] **Scénář "Ztracený uživatel"**
  - *Sekvence:* Profil -> Followers -> Random profil -> Čtení Bio -> Exit.
- [ ] **Simulace čtení (Human Reading Speed)**
  - *Logika:* Zastavit scroll u dlouhých textů na dobu odpovídající cca 200 slovům za minutu.

## 5. Plánování a Časování (Scheduler)
Cíl: Přirozené rozložení aktivity v čase.
- [ ] **Pracovní doba profilu (Timezone Awareness)**
  - *Logika:* Virtuální časové pásmo pro profil. Zákaz aktivity v "hluboké noci" daného pásma.
- [ ] **Úloha "Random Activity"**
  - *Scheduler:* Náhodné spouštění `WarmupBot` (5-15 min) v průběhu dne.
- [ ] **Rozložení zátěže (Load Balancing)**
  - *Queue:* Netěžit se všemi profily naráz v celou hodinu. Fronta s náhodnými odstupy (jitter).

## 6. Databáze a Logování
Cíl: Monitoring zdraví profilů a prevence rate-limitů.
- [ ] **Historie akcí (Rate Limiting)**
  - *Metrika:* Logovat počet requestů, liků, scrollů za 24h.
  - *Limit:* Pokud se blíží limitu, odstavit profil na 24h (Cooldown).
- [ ] **Stav Profilu**
  - *DB Schema:* Sloupec `account_status` (hodnoty: `Active`, `Cooldown`, `Banned`, `Login Required`).