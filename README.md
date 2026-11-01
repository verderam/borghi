# Borghi Start Up

Sito statico editoriale dedicato a **100 idee imprenditoriali per i borghi italiani**, realizzato con [Hugo](https://gohugo.io/).

La repository contiene sia il progetto sorgente sia i file già compilati nella cartella `public/`. Non richiede Node.js, package manager, temi esterni o servizi CDN.

## Requisiti

- Hugo **0.78.0 o successivo**;
- un qualsiasi web server per pubblicare i file statici.

Verifica la versione installata:

```bash
hugo version
```

## Clonare e compilare

```bash
git clone https://github.com/verderam/borghi.git
cd borghi
hugo --cleanDestinationDir
```

Il sito viene generato nella cartella `public/`. Per rigenerare anche le bozze, se ne venissero aggiunte:

```bash
hugo --cleanDestinationDir --buildDrafts
```

## Prova locale

Con Hugo:

```bash
hugo server --bind 0.0.0.0 --port 1313
```

Aprire `http://localhost:1313`.

In alternativa, per verificare direttamente i file compilati:

```bash
python3 -m http.server 8080 --directory public
```

Aprire `http://localhost:8080`.

## Pubblicazione su un web server

Copiare **il contenuto** di `public/` nella document root del sito, per esempio:

```bash
rsync -av --delete public/ UTENTE@SERVER:/var/www/borghi/
```

Per Apache non sono necessarie regole di riscrittura. Un esempio minimo per Nginx:

```nginx
server {
    listen 80;
    server_name esempio.it;
    root /var/www/borghi;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

La configurazione usa `baseURL = "/"` e `uglyURLs = true`: i collegamenti puntano direttamente ai file `.html` e il sito è predisposto per essere servito dalla radice del dominio. Se viene installato in una sottocartella o sotto un dominio diverso, aggiornare `baseURL` in `config.toml` e ricompilare.

## Struttura

```text
content/             Testi e 100 schede delle idee
layouts/             Template HTML del sito
static/              CSS, JavaScript, font, copertine SVG e licenze
config.toml          Configurazione Hugo
public/              Sito statico già compilato, pronto per il web server
CREDITS.md           Crediti e licenze
```

## Navigazione e accessibilità

InstantClick è incluso localmente e aggiunge navigazione dinamica progressiva. Con JavaScript disattivato tutti i normali collegamenti HTML continuano a funzionare. Ricerca e filtri del catalogo sono un miglioramento client-side e non richiedono un backend.

## Contenuti e diritti

Il progetto deriva da un documento in revisione. Le schede non costituiscono business plan: fattibilità, norme, mercato e sostenibilità economica devono essere verificati prima di qualsiasi iniziativa.

I diritti sui testi restano ai rispettivi titolari; la diffusione pubblica dei contenuti è subordinata alle necessarie autorizzazioni. Copertine, font, icone e componenti di terze parti sono documentati in `CREDITS.md` e nelle licenze incluse in `static/licenses/`.
