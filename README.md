# Billig el – notiser om dygnets billigaste kvartar

Varje dag cirka kl 13–14 hämtas morgondagens kvartspriser (SE4) från elprisetjustnu.se.
Då händer två saker:

1. **En plan** skickas direkt: morgondagens billigaste perioder.
2. **Påminnelser** schemaläggs 5 minuter innan varje billig period börjar.

Notiserna går via den gratis appen **ntfy** (Android och iPhone). Påminnelserna
schemaläggs hos ntfy, så de kommer på minuten även om GitHub Actions är sen.

## Installation (cirka 10 minuter)

### 1. Hitta på ett kanalnamn
ntfy-kanaler är öppna för den som känner till namnet, så välj något svårgissat,
t.ex. `elpris-johansson-k7q2x9`.

### 2. Installera ntfy i mobilerna
- Ladda ner **ntfy** från App Store / Google Play.
- Tryck **+**, skriv kanalnamnet, prenumerera.
- iPhone: tillåt notiser när appen frågar.
- Gör samma sak på Helenes telefon.

### 3. Skapa repot på GitHub
- Nytt repo, t.ex. `billig-el`. Ladda upp alla filer, även mappen `.github`.
- **Settings → Secrets and variables → Actions → Secrets → New repository secret**
  - Namn: `NTFY_TOPIC`, värde: ditt kanalnamn.
- **Settings → Actions → General → Workflow permissions**: välj *Read and write permissions*.

### 4. Testa
- **Actions → Elprisnotis → Run workflow**.
- Efter kl 13 kommer planen inom någon minut. Före kl 13 står det i loggen att priserna inte är publicerade än.
- Vill du testa en gång till samma dag: ta bort filen `skickat.txt` och kör igen.

### 5. Webbsidan (valfritt)
- **Settings → Pages → Deploy from a branch → main / (root)**.
- Sidan visar dagens och morgondagens kvartar med de billigaste markerade.
- Lägg in sidans adress som variabel `SIDA_URL` (se nedan), så öppnas sidan när du trycker på en notis.

## Inställningar
Under **Settings → Secrets and variables → Actions → Variables** (alla är valfria):

| Variabel | Standard | Betydelse |
|---|---|---|
| `ELOMRADE` | `SE4` | SE1, SE2, SE3 eller SE4 |
| `ANTAL_KVARTAR` | `8` | Hur många av dygnets kvartar som räknas som billiga (8 = 2 h) |
| `PAMINN_MINUTER_FORE` | `5` | Hur många minuter innan perioden påminnelsen kommer |
| `TYST_FRAN` | `22` | Inga påminnelser för perioder som startar från denna timme … |
| `TYST_TILL` | `7` | … till denna timme. Nattperioder syns ändå i planen. Sätt båda till 0 för att stänga av. |
| `SIDA_URL` | – | Länk som öppnas när man trycker på notisen |

## Bra att veta
- Priserna är **spotpris utan moms och avgifter**. Det påverkar inte vilka kvartar som är billigast.
- Varje dag committas filen `skickat.txt`. Det håller dessutom repot aktivt, så att GitHub inte stänger av schemat.
- Allt är gratis: GitHub Actions, GitHub Pages, ntfy.sh och elprisetjustnu.se.
