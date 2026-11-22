# Sito LWTV Channel – guida

Sito statico (HTML + Bootstrap) che si aggiorna da solo a ogni video pubblicato su YouTube.
Nessun PHP, nessun database. Tutto si gestisce dal browser, da GitHub.

## 1. Metterlo online (circa 15 minuti)

1. **Crea l'account**: vai su <https://github.com/signup> (gratis). Scegli un nome utente con calma: finisce nell'indirizzo del sito provvisorio.
2. **Crea il repository**: in alto a destra `+` → *New repository*. Nome: `lwtv-channel`. Lascialo **Public**. Crea.
3. **Carica i file**: nella pagina del repository scegli *uploading an existing file*. Decomprimi lo zip e trascina **il contenuto** della cartella (non lo zip). Premi *Commit changes*.
4. **Controlla la cartella nascosta `.github`**: se nel repository non vedi `.github/workflows/pubblica.yml`, crealo a mano: *Add file* → *Create new file*, come nome scrivi `.github/workflows/pubblica.yml`, incolla il contenuto del file `workflow-da-copiare.txt` e fai *Commit*. (Alcuni computer nascondono le cartelle che iniziano con il punto e il trascinamento le salta.)
5. **Attiva Pages**: *Settings* → *Pages* → alla voce *Source* scegli **GitHub Actions**.
6. **Prima pubblicazione**: scheda *Actions* → se compare un avviso, conferma di voler abilitare i workflow → scegli *Aggiorna e pubblica il sito* → *Run workflow*. Dopo uno o due minuti il sito è online su `https://TUO-UTENTE.github.io/lwtv-channel/`.

Da qui in poi il controllo dei nuovi video parte da solo **ogni ora**, e ogni volta che modifichi un file nel repository.

Se la pubblicazione fallisce con un errore sui permessi: *Settings* → *Actions* → *General* → *Workflow permissions* → **Read and write permissions** → Save, poi rilancia il workflow.

## 2. Quali video compaiono sul sito

Il sito mostra **solo** i video che riesce ad assegnare a una sezione. In ordine:

1. nel file di testo del video c'è `sezione: ...` (vedi punto 3);
2. nella descrizione su YouTube c'è un hashtag: `#garage` (Old Garage), `#tech` (Tech Lab), `#maker` (Maker);
3. nel titolo c'è una delle parole chiave elencate in `config.json`.

Un video che non rientra in nessuna regola (per esempio cucina o vlog) **resta nascosto**.
Per vedere come è stato trattato ogni video apri `data/elenco-video.txt` (si aggiorna da solo).
Per nascondere a mano un video: scrivi il suo ID in `content/nascosti.txt`.

**Consiglio:** da ora in poi metti un hashtag di sezione nella descrizione di ogni video, così la classificazione è certa.

## 3. Scrivere l'approfondimento di un video

Istruzioni complete in `content/videos/MODELLO-approfondimento.txt`. In breve:

1. L'ID del video sono le 11 lettere dopo `v=` nell'indirizzo YouTube (o lo trovi in `data/elenco-video.txt`).
2. Nel repository vai in `content/videos` → *Add file* → *Create new file* → nome `ID.md`.
3. Scrivi il testo (formato Markdown, esempi nel modello) → *Commit*. Il sito si aggiorna in un paio di minuti.

Se un video non ha ancora l'approfondimento, la pagina esce comunque con il video e la descrizione di YouTube.

## 4. File da scaricare e foto

- **File** (pdf, stl, zip…): cartella `downloads/ID/` → *Add file* → *Upload files*. Compaiono da soli nella pagina del video e in *Download*. Limite di GitHub: 100 MB a file.
- **Foto**: cartella `media/`, poi nel testo `![descrizione](/media/nome-foto.jpg)`. Meglio sotto i 1600 pixel di larghezza.

## 5. Importare tutti i 156 video vecchi

Il feed gratuito di YouTube arriva solo agli ultimi 15 video. Per l'archivio completo serve una chiave gratuita dell'API di YouTube:

1. <https://console.cloud.google.com> → nuovo progetto → *API e servizi* → abilita **YouTube Data API v3** → *Credenziali* → *Crea credenziali* → *Chiave API*.
2. Su GitHub: *Settings* → *Secrets and variables* → *Actions* → *New repository secret* → nome `YOUTUBE_API_KEY`, valore la chiave.
3. Rilancia il workflow. Da quel momento ogni giro legge l'intero canale.

Poi controlla `data/elenco-video.txt` e metti gli hashtag o i file `.md` per i video vecchi che vuoi mostrare.

## 6. Collegare il dominio (quando lo avete)

1. Nella radice del repository crea un file chiamato `CNAME` che contiene solo il dominio, per esempio `lwtvchannel.it`. Il sito sistema da solo indirizzi e link.
2. Dal pannello DNS di chi vi ha venduto il dominio: quattro record **A** verso `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`, e un record **CNAME** `www` verso `TUO-UTENTE.github.io`. (Controllate gli indirizzi aggiornati nella guida GitHub Pages: possono cambiare.)
3. *Settings* → *Pages* → *Custom domain* → scrivi il dominio → spunta *Enforce HTTPS* appena disponibile.

## 7. AdSense (più avanti)

In `config.json` c'è la sezione `adsense`: quando Google approva il sito mettete `"attivo": true`, il vostro `client` (`ca-pub-...`) e gli identificativi dei due spazi. Gli annunci compaiono nei punti già previsti.
Prima servono: dominio vostro, un po' di contenuti, la pagina `content/pages/privacy.md` completata e un **banner di consenso ai cookie** (richiesto in Italia). Il file `ads.txt` che Google fornisce va messo nella cartella `radice/`.

## 8. Personalizzare

- **Testi della home, aspetto delle pagine**: cartella `templates/`.
- **Colori, font, spaziature**: `static/css/style.css` (colori in cima, nelle variabili `--arancio`, `--azzurro`…).
- **Sezioni, nomi, parole chiave, descrizioni**: `config.json`. Se cambiate lo `slug` di una sezione cambia anche l'indirizzo della sua pagina.
- **Chi siamo e Privacy**: `content/pages/`. Contengono parti `[da compilare]`.

## 9. Provare il sito sul proprio computer (facoltativo, serve Python)

```
pip install -r requirements.txt
python build.py --feed-file tests/feed-prova.xml --data-dir prova-dati
python -m http.server -d public
```
Poi apri <http://localhost:8000>. I dati di prova stanno in `prova-dati/`, che puoi cancellare.

## Cose da sapere

- Un video eliminato da YouTube resta sul sito finché non lo nascondi in `content/nascosti.txt`.
- Gli indirizzi dei video (`/video/titolo-del-video/`) si decidono alla prima pubblicazione e non cambiano più, anche se poi cambiate il titolo su YouTube.
- I caratteri (Google Fonts) e Bootstrap vengono caricati da servizi esterni: va dichiarato nella privacy. Più avanti si possono ospitare sul sito stesso.
- GitHub può sospendere le attività programmate dei repository pubblici senza attività da 60 giorni: se succede, basta riattivarle dalla scheda *Actions*.
