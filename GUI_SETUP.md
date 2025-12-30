# 🖥️ Guida Rapida Desktop Remoto

## Per usare le GUI (Tkinter) in GitHub Codespaces

### Primo Setup (una sola volta)

Quando apri il Codespace per la prima volta, esegui:

```bash
./setup_codespaces.sh
```

Questo installa Python, OpenCV, SciPy e tutte le dipendenze necessarie.

---

### Come Aprire il Desktop Remoto

1. **In VS Code, vai alla tab "PORTS"** (in basso, accanto a "TERMINAL")

2. **Cerca la porta 6080** con label "Desktop (noVNC)"

3. **Clicca sull'icona del globo** 🌐 accanto alla porta

4. **Si aprirà una nuova finestra del browser** con il desktop remoto

5. **Password VNC:** `vscode`

---

### Come Eseguire le Applicazioni GUI

**Nel desktop remoto:**

1. Clicca sull'icona **Terminal** nel desktop
2. Esegui:
   ```bash
   cd /workspaces/centrafari
   python3 MW28912.py
   ```
3. La finestra tkinter apparirà nel desktop! 🎉

**Oppure, dal terminale VS Code:**

```bash
DISPLAY=:1 python3 MW28912.py
```

---

### 🎯 Riferimento Veloce

| Cosa | Come |
|------|------|
| **Aprire desktop** | PORTS tab → 6080 → Clicca globo 🌐 |
| **Password** | `vscode` |
| **Eseguire GUI** | Nel desktop: `python3 MW28912.py` |
| **Chiudere GUI** | Chiudi la finestra dell'app |

---

### ❓ Problemi Comuni

**Q: Non vedo la porta 6080**
- Ricostruisci il container: F1 → "Codespaces: Rebuild Container"

**Q: Il desktop non si apre**
- Controlla che la porta sia pubblica nella tab PORTS
- Riprova a cliccare sull'icona del globo

**Q: La GUI non appare**
- Verifica di essere nel desktop remoto (browser)
- Controlla che DISPLAY=:1 sia impostato

---

### 💡 Suggerimenti

- **Desktop leggero:** Il desktop usa XFCE, molto leggero e veloce
- **Più terminali:** Puoi aprire più terminali nel desktop
- **Copy/Paste:** Usa il menu VNC per copiare/incollare tra locale e remoto
- **Performance:** Se lento, riduci la qualità video nelle impostazioni VNC

---

**Buon lavoro! 🚀**
