# 🌐 Sviluppo Remoto - Zero Installazioni Locali

Questa guida ti mostra come lavorare su questo progetto Python **completamente da remoto**, senza installare nulla sul tuo computer locale.

---

## ⭐ Opzione 1: GitHub Codespaces (CONSIGLIATA)

**GitHub Codespaces** è un ambiente di sviluppo completo nel browser, già configurato per questo progetto.

### Come iniziare:

1. Vai alla repository su GitHub: `https://github.com/sandrogeco/centrafari`

2. Clicca sul pulsante verde **"Code"** ▼

3. Seleziona la tab **"Codespaces"**

4. Clicca **"Create codespace on claude/centrafari2.0-LGwlK"**

5. Attendi ~2 minuti mentre viene creato l'ambiente

6. **Fatto!** Hai VS Code nel browser con tutto configurato

### Piano gratuito:
- ✅ 60 ore/mese gratuite per account personali
- ✅ 120 core-hours/mese
- ✅ 15 GB di storage

### Cosa è già configurato:
- ✅ Python 3.11
- ✅ OpenCV, SciPy, Pillow
- ✅ Estensioni VS Code per Python
- ✅ Tutti i tool di debug e linting

---

## 🚀 Opzione 2: Gitpod

Alternativa a Codespaces, molto simile.

### Come iniziare:

1. Vai su: `https://gitpod.io/#https://github.com/sandrogeco/centrafari`

2. Accedi con il tuo account GitHub

3. Attendi che l'ambiente si avvii

### Piano gratuito:
- ✅ 50 ore/mese gratuite
- ✅ Workspace condivisibili

---

## 🎯 Opzione 3: Replit

Ideale per test rapidi e progetti più semplici.

### Come iniziare:

1. Vai su [replit.com](https://replit.com)

2. Clicca **"Create Repl"**

3. Scegli **"Import from GitHub"**

4. Inserisci: `https://github.com/sandrogeco/centrafari`

5. Clicca **"Import from GitHub"**

### Piano gratuito:
- ✅ Illimitato per progetti pubblici
- ✅ Editor nel browser
- ⚠️ Limitato per progetti privati

---

## 📋 Confronto Rapido

| Caratteristica | Codespaces | Gitpod | Replit |
|----------------|------------|---------|---------|
| Ore gratuite/mese | 60 | 50 | ∞ (pubblici) |
| Ambiente | VS Code | VS Code/Theia | Custom |
| Potenza | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Setup | Automatico | Automatico | Manuale |
| Python + OpenCV | ✅ | ✅ | ✅ |

---

## 💡 Raccomandazione

**Usa GitHub Codespaces** se:
- Vuoi la miglior esperienza (identica a VS Code locale)
- Hai bisogno di potenza computazionale
- Vuoi zero configurazione

**Usa Gitpod** se:
- Hai finito le ore di Codespaces
- Preferisci un'alternativa open-source

**Usa Replit** se:
- Vuoi qualcosa di più semplice e leggero
- Fai solo modifiche veloci

---

## 🔧 Note Tecniche

### Configurazione Automatica
Questo repository include:
- `.devcontainer/devcontainer.json` - configurazione per Codespaces
- `requirements.txt` - dipendenze Python

All'avvio di Codespaces, vengono installate automaticamente:
- opencv-python
- scipy
- numpy
- Pillow

### Setup Iniziale in Codespaces

**Importante:** Alla prima apertura del Codespace, esegui:

```bash
./setup_codespaces.sh
```

Questo installerà:
- `python3-tk` (necessario per la GUI)
- Tutte le dipendenze Python da `requirements.txt`

Se hai problemi di rete durante il setup automatico, attendi qualche minuto e riesegui lo script.

---

## ❓ Domande Frequenti

**Q: Posso usare la webcam in Codespaces?**
A: No, Codespaces non ha accesso diretto all'hardware locale. Per testare il codice che usa la webcam, usa file video di test o immagini.

**Q: I miei file sono al sicuro?**
A: Sì, sono salvati su GitHub. Ricorda di fare commit regolari.

**Q: Posso invitare collaboratori?**
A: Sì, con Codespaces puoi condividere l'ambiente in tempo reale (Live Share).

**Q: Quanto costa dopo il piano gratuito?**
A: Codespaces: ~$0.18/ora. Gitpod: ~$0.36/ora. Ma con i piani gratuiti difficilmente pagherai.

---

## 🎉 Inizia Subito!

Vai su GitHub → Clicca "Code" → "Codespaces" → "Create codespace on claude/centrafari2.0-LGwlK"

**Buon coding senza installazioni! 🚀**
