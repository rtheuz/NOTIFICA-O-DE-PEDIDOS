import os
import sys
import json
import time
import threading
import subprocess
import winsound
from datetime import date
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from win10toast import ToastNotifier
from pystray import Icon, MenuItem, Menu
from PIL import Image
import tkinter as tk
from tkinter import filedialog
import multiprocessing

# ----------------------
# Helper para recursos
# ----------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ----------------------
# Recursos embutidos
# ----------------------
ICON_PATH = resource_path("icone.ico")
SOM_ALERTA = resource_path("alert.wav")
SOM_INICIO = resource_path("start.wav")
SOM_PAUSA = resource_path("pause.wav")

CONFIG_PATH = os.path.join(
    os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__),
    "config.json"
)

# ----------------------
# Config persistente
# ----------------------
def carregar_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"pasta_monitorada": ""}
    return {"pasta_monitorada": ""}

def salvar_config(dados):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

# ----------------------
# Som (winsound)
# ----------------------
def tocar_som(caminho):
    try:
        if caminho and os.path.exists(caminho):
            winsound.PlaySound(caminho, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass

# ----------------------
# Monitoramento
# ----------------------
class MonitorHandler(FileSystemEventHandler):
    def __init__(self, toaster, monitor):
        self.toaster = toaster
        self.monitor = monitor

    def on_created(self, event):
        if not event.is_directory:
            nome = os.path.basename(event.src_path)
            self.monitor.contador += 1
            self.toaster.show_toast(
                "📂 Novo Arquivo Detectado",
                f"{nome}\nTotal hoje: {self.monitor.contador}",
                duration=4,
                threaded=True
            )
            tocar_som(SOM_ALERTA)

class Monitoramento:
    def __init__(self, pasta):
        self.pasta = pasta
        self.observer = None
        self.toaster = ToastNotifier()
        self.ativo = False
        self.contador = 0
        self.data_atual = date.today()

    def _verificar_reset_diario(self):
        if date.today() != self.data_atual:
            self.data_atual = date.today()
            self.contador = 0
            self.toaster.show_toast("🕛 Contador reiniciado", "Novo dia detectado. Contador zerado.", duration=4, threaded=True)

    def iniciar(self):
        if not self.pasta or not os.path.exists(self.pasta):
            self.toaster.show_toast("❌ Erro", "A pasta monitorada não existe!", duration=4, threaded=True)
            return
        self.handler = MonitorHandler(self.toaster, self)
        self.observer = Observer()
        self.observer.schedule(self.handler, self.pasta, recursive=True)
        self.observer.start()
        self.ativo = True
        self.contador = 0
        threading.Thread(target=self._loop_reset, daemon=True).start()
        tocar_som(SOM_INICIO)
        self.toaster.show_toast("✅ Monitoramento iniciado", f"Pasta: {self.pasta}", duration=4, threaded=True)

    def _loop_reset(self):
        while self.ativo:
            self._verificar_reset_diario()
            time.sleep(60)

    def parar(self):
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join()
            except Exception:
                pass
        self.ativo = False
        tocar_som(SOM_PAUSA)
        self.toaster.show_toast("⏸️ Monitoramento pausado", duration=3, threaded=True)

# ----------------------
# Bandeja / UI
# ----------------------
def iniciar_bandeja():
    config = carregar_config()
    pasta_monitorada = config.get("pasta_monitorada", "") or ""
    toaster = ToastNotifier()
    monitor = Monitoramento(pasta_monitorada)

    # função que abre diálogo (na thread) e inicia monitor se escolhido
    def escolher_e_iniciar():
        try:
            root = tk.Tk()
            root.withdraw()
            pasta = filedialog.askdirectory(title="Selecione a pasta para monitorar")
            root.destroy()
        except Exception:
            pasta = ""
        if pasta:
            # normalizar caminho
            pasta = os.path.abspath(pasta)
            monitor.parar()
            monitor.pasta = pasta
            config["pasta_monitorada"] = pasta
            salvar_config(config)
            threading.Thread(target=monitor.iniciar, daemon=True).start()
            toaster.show_toast("✅ Pasta definida", f"Monitorando: {pasta}", duration=4, threaded=True)
            tocar_som(SOM_INICIO)
        else:
            toaster.show_toast("⚠️ Nenhuma pasta selecionada", "Você pode definir pelo menu da bandeja.", duration=4, threaded=True)

    # ao iniciar app pela primeira vez sem config -> abre diálogo automaticamente (em thread)
    if not pasta_monitorada:
        toaster.show_toast("🟡 TUBA iniciado", "Selecione a pasta para começar o monitoramento.", duration=4, threaded=True)
        threading.Thread(target=escolher_e_iniciar, daemon=True).start()
    else:
        # iniciar monitor automaticamente
        threading.Thread(target=monitor.iniciar, daemon=True).start()
        toaster.show_toast("🚀 TUBA iniciado", f"Monitorando: {pasta_monitorada}", duration=4, threaded=True)

    # funções do menu (sempre referenciam monitor e config atual)
    def menu_escolher(icon, item):
        threading.Thread(target=escolher_e_iniciar, daemon=True).start()

    def menu_iniciar(icon, item):
        if not monitor.ativo:
            threading.Thread(target=monitor.iniciar, daemon=True).start()

    def menu_parar(icon, item):
        monitor.parar()

    def menu_abrir_pasta(icon, item):
        # tenta priorizar monitor.pasta, se vazio usa config salvo
        caminho = getattr(monitor, "pasta", "") or config.get("pasta_monitorada", "") or ""
        if caminho and os.path.exists(caminho):
            # abrir a pasta correta
            try:
                subprocess.Popen(['explorer', caminho])
            except Exception:
                # fallback
                subprocess.Popen(f'explorer "{caminho}"')
        else:
            toaster.show_toast("⚠️ Nenhuma pasta válida", "Defina uma pasta primeiro.", duration=3, threaded=True)

    def menu_sair(icon, item):
        monitor.parar()
        icon.stop()

    menu = Menu(
        MenuItem("📁 Escolher pasta", menu_escolher),
        MenuItem("📂 Abrir pasta monitorada", menu_abrir_pasta),
        MenuItem("▶️ Iniciar", menu_iniciar),
        MenuItem("⏸️ Parar", menu_parar),
        MenuItem("🚪 Sair", menu_sair)
    )

    # carregar ícone (do exe, via resource_path)
    image = Image.open(ICON_PATH)
    icon = Icon("TUBA", image, "TUBA - Monitor de Arquivos", menu)
    icon.run()

# ----------------------
# Main
# ----------------------
if __name__ == "__main__":
    multiprocessing.freeze_support()
    iniciar_bandeja()
