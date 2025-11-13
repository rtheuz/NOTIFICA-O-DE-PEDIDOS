import os
import sys
import time
import threading
import json
import tkinter as tk
from tkinter import filedialog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from win10toast import ToastNotifier
import pystray
from pystray import MenuItem as item
from PIL import Image
import winsound
import subprocess

# ---------------------------------------------------
# Helper para recursos (funciona com PyInstaller --onefile)
# ---------------------------------------------------
def resource_path(relative_path):
    """
    Retorna o caminho absoluto do recurso.
    - Quando empacotado com PyInstaller (--onefile), os arquivos adicionados com --add-data
      são extraídos em runtime para sys._MEIPASS.
    - Quando rodando em modo "normal" (python script), usa o diretório do arquivo.
    """
    if getattr(sys, "_MEIPASS", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)

# Caminhos principais (agora resolvidos via resource_path)
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

ICON_PATH = resource_path("icone.ico")

# Sons resolvidos via resource_path (garante que funcionem no exe gerado)
START_SOUND = resource_path("start.wav")
ALERT_SOUND = resource_path("alert.wav")
PAUSE_SOUND = resource_path("pause.wav")

# Notificador
toaster = ToastNotifier()

# ---------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------
def escolher_pasta():
    root = tk.Tk()
    root.withdraw()
    pasta = filedialog.askdirectory(title="Selecione a pasta para monitorar")
    root.destroy()
    return pasta

def salvar_config(pasta_path):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"pasta": pasta_path}, f)

def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("pasta")
    else:
        pasta = escolher_pasta()
        if pasta:
            salvar_config(pasta)
        return pasta

def tocar_som(caminho):
    """
    Toca um arquivo WAV de forma assíncrona.
    Verifica se o arquivo existe antes de tocar (importante no exe).
    """
    try:
        if caminho and os.path.exists(caminho):
            winsound.PlaySound(caminho, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass

# ---------------------------------------------------
# Monitoramento
# ---------------------------------------------------
class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            nome = os.path.basename(event.src_path)
            print(f"[{time.strftime('%H:%M:%S')}] Novo arquivo: {nome}")
            # notificação nativa
            toaster.show_toast("📄 Novo arquivo detectado!",
                               f"{nome}",
                               duration=3,
                               icon_path=ICON_PATH)
            # tocar alerta (WAV)
            tocar_som(ALERT_SOUND)

def iniciar_monitor(pasta_path):
    global observer
    observer = Observer()
    event_handler = Handler()
    observer.schedule(event_handler, pasta_path, recursive=False)
    observer.start()
    print(f"[{time.strftime('%H:%M:%S')}] 🟢 Monitorando: {pasta_path}")
    toaster.show_toast("🚀 TUBA Iniciado", f"Monitorando: {pasta_path}", duration=4, icon_path=ICON_PATH)
    tocar_som(START_SOUND)

def parar_monitor():
    global observer
    try:
        observer.stop()
        observer.join()
        print("[🟡] Monitor pausado.")
    except Exception:
        pass
    tocar_som(PAUSE_SOUND)

# ---------------------------------------------------
# Abertura da pasta monitorada (nova função solicitada)
# ---------------------------------------------------
def abrir_pasta(icon, item):
    """
    Abre a pasta atualmente monitorada no Explorer.
    Usa a variável global 'pasta' e verifica existência antes de tentar abrir.
    """
    global pasta
    caminho = pasta or carregar_config() or ""
    if caminho and os.path.exists(pasta):
        try:
            subprocess.Popen(['explorer', pasta])
        except Exception:
            # fallback (acerta aspas se necessário)
            try:
                subprocess.Popen(f'explorer "{pasta}"')
            except Exception:
                toaster.show_toast("⚠️ Erro", "Não foi possível abrir a pasta.", duration=3, icon_path=ICON_PATH)
    else:
        toaster.show_toast("⚠️ Nenhuma pasta válida", "Defina uma pasta primeiro.", duration=3, icon_path=ICON_PATH)

# ---------------------------------------------------
# Ícone da bandeja
# ---------------------------------------------------
def alterar_pasta(icon, item):
    global pasta
    parar_monitor()
    nova = escolher_pasta()
    if nova:
        pasta = nova
        salvar_config(pasta)
        threading.Thread(target=iniciar_monitor, args=(pasta,), daemon=True).start()
        toaster.show_toast("📂 Pasta alterada", f"Agora monitorando:\n{pasta}", duration=3, icon_path=ICON_PATH)

def sair(icon, item):
    parar_monitor()
    toaster.show_toast("👋 Encerrando TUBA", "O monitor foi encerrado.", duration=3, icon_path=ICON_PATH)
    icon.stop()
    os._exit(0)

def iniciar_bandeja():
    # carregar ícone a partir do resource_path (funciona no exe)
    image = Image.open(ICON_PATH)
    menu = (
        item("📂 Alterar pasta monitorada", alterar_pasta),
        item("📂 Abrir pasta monitorada", abrir_pasta),  # item adicionado
        item("❌ Sair", sair)
    )
    icone = pystray.Icon("TUBA", image, "TUBA Monitor", menu)
    icone.run()

# ---------------------------------------------------
# Inicialização principal
# ---------------------------------------------------
if __name__ == "__main__":
    pasta = carregar_config()
    if not pasta:
        toaster.show_toast("⚠️ Nenhuma pasta selecionada", "Selecione uma pasta para monitorar.", duration=4, icon_path=ICON_PATH)
        sys.exit()

    threading.Thread(target=iniciar_monitor, args=(pasta,), daemon=True).start()
    iniciar_bandeja()
