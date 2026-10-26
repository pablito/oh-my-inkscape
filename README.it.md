# Oh My Inkscape

Una raccolta di estensioni per Inkscape, destinata a crescere. Stanno tutte sotto
**Estensioni → Oh My Inkscape** e condividono un solo installatore, una libreria Python e un
catalogo di traduzioni.

*Read in English: [README.md](README.md).*

| Estensione | Cosa fa |
|---|---|
| **Elenchi Markdown** | Impagina Markdown (titoli, paragrafi, elenchi puntati, numerati e annidati, grassetto, corsivo) dentro un rettangolo, con veri rientri sospesi. Il blocco ricorda testo e impostazioni e si rigenera dopo aver modificato il testo o ridimensionato la cornice. |

Inkscape non ha elenchi, tabulazioni né rientri di paragrafo; Elenchi Markdown posiziona ogni
simbolo e ogni riga a coordinate calcolate. Può scrivere righe fisse (calcolate dai file dei font,
esatte e uguali ovunque) oppure testo a capo automatico che Inkscape continua a far andare a capo
mentre lo modifichi, con righe di riserva perché anche i browser lo mostrino correttamente.
Dettagli (in inglese): [docs/mdlists.md](docs/mdlists.md).

## Requisiti

- Inkscape 1.2 o successivo (sviluppato con la 1.4); Linux, comprese le versioni Snap e Flatpak.
  macOS e Windows dovrebbero funzionare ma non sono provati.
- fontconfig (`fc-list`, `fc-match`), che Inkscape usa già su Linux.
- Nient'altro: fontTools è incluso, lxml è fornito da Inkscape.

## Installazione

```bash
git clone https://github.com/pablito/oh-my-inkscape.git
cd oh-my-inkscape
./install.sh          # copia src/oh-my-inkscape nella cartella delle estensioni di Inkscape
```

Riavvia Inkscape. `./install.sh --link` crea un collegamento invece di copiare (per sviluppare),
`./install.sh --uninstall` la rimuove. La destinazione è `$INKSCAPE_EXTENSIONS_DIR` se impostata,
`~/snap/inkscape/common/extensions` per la versione Snap (il suo avvio sposta lì la cartella delle
estensioni utente), `~/.var/app/org.inkscape.Inkscape/config/inkscape/extensions` per Flatpak,
altrimenti `<inkscape --user-data-directory>/extensions`. Per installarla a mano, copia la cartella `src/oh-my-inkscape`
nella cartella indicata in *Modifica → Preferenze → Sistema → Estensioni utente*.

## Elenchi Markdown in 30 secondi

1. Disegna un rettangolo dove deve stare il testo.
2. Con il rettangolo selezionato, apri *Estensioni → Oh My Inkscape → Elenchi Markdown…*.
3. Incolla il Markdown nella scheda *Testo* (o scegli un file `.md`), imposta il font in *Carattere*,
   premi *Applica*.
4. Per cambiare il testo in seguito, modifica la *Descrizione* del blocco in
   *Oggetto → Proprietà oggetto* (Ctrl+Maiusc+O), oppure ridimensiona il rettangolo; seleziona il
   blocco o il rettangolo e rilancia l'estensione.

La versione a riga di comando, per script e lavori in serie:

```bash
python3 cli/md2svg.py regole.md --set font_family='"Nimbus Sans"' --set width_mm=88 --out regole.svg --check
```

## Sviluppo

```bash
python3 -m pytest tests          # servono lxml, fontTools (o la copia inclusa) e un font sans TTF/OTF
python3 tools/i18n.py --check    # estrae i testi, aggiorna po/*.po, compila locale/*.mo (GNU gettext)
```

Per aggiungere un'estensione: crea `omi_<nome>.inx` (con `translationdomain="oh-my-inkscape"` e il
sottomenu `Oh My Inkscape`) e `omi_<nome>.py`, metti il codice riutilizzabile in
`omi_lib/<nome>/`, racchiudi i messaggi Python per l'utente in `_()` da `omi_lib.i18n`, poi esegui
`tools/i18n.py` e traduci le nuove voci in `po/it.po`. La struttura completa è descritta nel
[README in inglese](README.md#development).

## Licenza

GPL-3.0-or-later, vedi [LICENSE](LICENSE). fontTools 4.61.1 incluso
(`src/oh-my-inkscape/omi_lib/_vendor/fontTools`, non modificato) è distribuito con licenza MIT, vedi
`src/oh-my-inkscape/omi_lib/_vendor/licenses/`.
