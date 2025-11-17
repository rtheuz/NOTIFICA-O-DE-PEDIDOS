import os
import sys
import time
import threading
import json
import logging
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
# Configuração de logging
# ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
    """
    Abre um diálogo para o usuário selecionar a pasta a ser monitorada.
    
    Returns:
        str: Caminho da pasta selecionada ou None se cancelado.
    """
    pasta_selecionada = None
    
    def _selecionar():
        nonlocal pasta_selecionada
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        root.lift()
        root.focus_force()
        
        try:
            pasta_selecionada = filedialog.askdirectory(
                title="Selecione a pasta para monitorar",
                parent=root
            )
            logging.info(f"Pasta selecionada: {pasta_selecionada if pasta_selecionada else 'Nenhuma'}")
        except Exception as e:
            logging.error(f"Erro ao escolher pasta: {e}")
            pasta_selecionada = None
        finally:
            root.destroy()
    
    try:
        _selecionar()
        return pasta_selecionada if pasta_selecionada else None
    except Exception as e:
        logging.error(f"Erro crítico ao escolher pasta: {e}")
        return None

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
    """
    Permite ao usuário alterar a pasta monitorada.
    Para o monitor atual, solicita nova pasta e reinicia o monitoramento.
    
    Args:
        icon: Ícone da bandeja do sistema.
        item: Item do menu clicado.
    """
    global pasta
    
    try:
        logging.info("Alterando pasta monitorada")
        parar_monitor()
        
        time.sleep(0.3)
        
        # Executar diretamente (Tkinter não é thread-safe)
        nova = escolher_pasta()
        
        if nova and os.path.exists(nova):
            pasta = nova
            salvar_config(pasta)
            time.sleep(0.3)
            threading.Thread(target=iniciar_monitor, args=(pasta,), daemon=True).start()
            toaster.show_toast(
                "📂 Pasta alterada",
                f"Agora monitorando:\n{pasta}",
                duration=3,
                icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
            )
            logging.info(f"Pasta alterada para: {pasta}")
        elif nova is None:
            logging.info("Usuário cancelou a seleção de pasta")
            if pasta and os.path.exists(pasta):
                threading.Thread(target=iniciar_monitor, args=(pasta,), daemon=True).start()
                toaster.show_toast(
                    "ℹ️ Seleção cancelada",
                    "Mantendo pasta atual.",
                    duration=2,
                    icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
                )
        else:
            logging.warning("Nova pasta não existe ou inválida")
            if pasta and os.path.exists(pasta):
                threading.Thread(target=iniciar_monitor, args=(pasta,), daemon=True).start()
            toaster.show_toast(
                "⚠️ Pasta inválida",
                "A pasta selecionada não existe.",
                duration=3,
                icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
            )
    except Exception as e:
        logging.error(f"Erro ao alterar pasta: {e}")
        toaster.show_toast(
            "⚠️ Erro",
            f"Erro ao alterar pasta: {str(e)[:30]}",
            duration=3,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )

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
