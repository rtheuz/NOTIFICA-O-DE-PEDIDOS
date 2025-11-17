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
import logging

# ---------------------------------------------------
# Metadados da Aplicação
# ---------------------------------------------------
APP_NAME = "TUBA Monitor"
APP_VERSION = "2.0.0"
APP_AUTHOR = "rtheuz"
APP_DESCRIPTION = "Sistema de Monitoramento de Pasta para Notificações de Arquivos"

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
LOG_PATH = os.path.join(APP_DIR, "tuba_monitor.log")

ICON_PATH = resource_path("icone.ico")

# Sons resolvidos via resource_path (garante que funcionem no exe gerado)
START_SOUND = resource_path("start.wav")
ALERT_SOUND = resource_path("alert.wav")
PAUSE_SOUND = resource_path("pause.wav")

# Configurar sistema de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Notificador
toaster = ToastNotifier()

# Variáveis globais
observer = None
pasta = None
monitor_lock = threading.Lock()

# ---------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------
def verificar_recursos():
    """
    Verifica se todos os recursos necessários existem.
    
    Returns:
        bool: True se todos os recursos existem, False caso contrário.
    """
    recursos = [ICON_PATH, START_SOUND, ALERT_SOUND, PAUSE_SOUND]
    faltando = [r for r in recursos if not os.path.exists(r)]
    if faltando:
        logging.warning(f"Recursos faltando: {faltando}")
        return False
    logging.info("Todos os recursos validados com sucesso")
    return True

def escolher_pasta():
    """
    Abre um diálogo para o usuário selecionar a pasta a ser monitorada.
    
    Returns:
        str: Caminho da pasta selecionada ou None se cancelado.
    """
    try:
        root = tk.Tk()
        root.withdraw()
        pasta = filedialog.askdirectory(title="Selecione a pasta para monitorar")
        root.destroy()
        logging.info(f"Pasta selecionada: {pasta if pasta else 'Nenhuma'}")
        return pasta
    except Exception as e:
        logging.error(f"Erro ao escolher pasta: {e}")
        return None

def salvar_config(pasta_path):
    """
    Salva o caminho da pasta monitorada no arquivo de configuração.
    
    Args:
        pasta_path (str): Caminho da pasta a ser salva.
    
    Returns:
        bool: True se salvo com sucesso, False caso contrário.
    """
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"pasta": pasta_path}, f)
        logging.info(f"Configuração salva: {pasta_path}")
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar configuração: {e}")
        return False

def carregar_config():
    """
    Carrega o caminho da pasta monitorada do arquivo de configuração.
    Se não existir, solicita ao usuário que escolha uma pasta.
    
    Returns:
        str: Caminho da pasta ou None se não houver.
    """
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                pasta_config = json.load(f).get("pasta")
                if pasta_config and os.path.exists(pasta_config):
                    logging.info(f"Configuração carregada: {pasta_config}")
                    return pasta_config
                else:
                    logging.warning("Pasta configurada não existe mais")
        
        # Se não houver config válida, pede ao usuário
        pasta = escolher_pasta()
        if pasta:
            salvar_config(pasta)
        return pasta
    except Exception as e:
        logging.error(f"Erro ao carregar configuração: {e}")
        pasta = escolher_pasta()
        if pasta:
            salvar_config(pasta)
        return pasta

def tocar_som(caminho):
    """
    Toca um arquivo WAV de forma assíncrona.
    Verifica se o arquivo existe antes de tocar (importante no exe).
    
    Args:
        caminho (str): Caminho do arquivo de som a ser tocado.
    """
    try:
        if caminho and os.path.exists(caminho):
            winsound.PlaySound(caminho, winsound.SND_FILENAME | winsound.SND_ASYNC)
            logging.debug(f"Som tocado: {caminho}")
    except Exception as e:
        logging.warning(f"Erro ao tocar som {caminho}: {e}")

# ---------------------------------------------------
# Monitoramento
# ---------------------------------------------------
class Handler(FileSystemEventHandler):
    """
    Manipulador de eventos do sistema de arquivos.
    Detecta quando novos arquivos são criados na pasta monitorada.
    """
    
    def on_created(self, event):
        """
        Callback chamado quando um novo arquivo é criado.
        
        Args:
            event: Evento do watchdog contendo informações do arquivo.
        """
        try:
            if not event.is_directory:
                nome = os.path.basename(event.src_path)
                logging.info(f"Novo arquivo detectado: {nome}")
                
                # Notificação nativa do Windows
                toaster.show_toast(
                    "📄 Novo arquivo detectado!",
                    f"{nome}",
                    duration=3,
                    icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
                )
                
                # Tocar som de alerta
                tocar_som(ALERT_SOUND)
        except Exception as e:
            logging.error(f"Erro ao processar arquivo criado: {e}")

def iniciar_monitor(pasta_path):
    """
    Inicia o monitoramento da pasta especificada.
    
    Args:
        pasta_path (str): Caminho da pasta a ser monitorada.
    
    Returns:
        bool: True se iniciado com sucesso, False caso contrário.
    """
    global observer
    
    # Validar se a pasta existe
    if not pasta_path or not os.path.exists(pasta_path):
        logging.error(f"Pasta inválida ou não existe: {pasta_path}")
        toaster.show_toast(
            "⚠️ Erro",
            "Pasta não encontrada. Selecione uma pasta válida.",
            duration=3,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )
        return False
    
    # Verificar permissões de leitura
    if not os.access(pasta_path, os.R_OK):
        logging.error(f"Sem permissão de leitura na pasta: {pasta_path}")
        toaster.show_toast(
            "⚠️ Erro de Permissão",
            "Sem permissão para acessar a pasta.",
            duration=3,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )
        return False
    
    try:
        with monitor_lock:
            observer = Observer()
            event_handler = Handler()
            observer.schedule(event_handler, pasta_path, recursive=False)
            observer.start()
            
        logging.info(f"Monitor iniciado para: {pasta_path}")
        toaster.show_toast(
            "🚀 TUBA Iniciado",
            f"Monitorando: {pasta_path}",
            duration=4,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )
        tocar_som(START_SOUND)
        return True
    except Exception as e:
        logging.error(f"Erro ao iniciar monitor: {e}")
        toaster.show_toast(
            "⚠️ Erro",
            f"Não foi possível iniciar o monitor: {str(e)[:50]}",
            duration=4,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )
        return False

def parar_monitor():
    """
    Para o monitoramento de forma segura e graceful.
    
    Returns:
        bool: True se parado com sucesso, False caso contrário.
    """
    global observer
    
    try:
        with monitor_lock:
            if observer is not None and observer.is_alive():
                observer.stop()
                observer.join(timeout=5)  # Aguardar até 5 segundos
                logging.info("Monitor parado com sucesso")
                tocar_som(PAUSE_SOUND)
                return True
            else:
                logging.warning("Monitor não estava ativo")
                return False
    except Exception as e:
        logging.error(f"Erro ao parar monitor: {e}")
        return False

# ---------------------------------------------------
# Abertura da pasta monitorada (nova função solicitada)
# ---------------------------------------------------
def abrir_pasta(icon, item):
    """
    Abre a pasta atualmente monitorada no Windows Explorer.
    Usa a variável global 'pasta' e verifica existência antes de tentar abrir.
    
    Args:
        icon: Ícone da bandeja do sistema.
        item: Item do menu clicado.
    """
    global pasta
    
    try:
        # Obter caminho da pasta
        caminho = pasta or carregar_config() or ""
        
        # Verificar se o caminho existe
        if caminho and os.path.exists(caminho):
            # Verificar permissões
            if not os.access(caminho, os.R_OK):
                logging.warning(f"Sem permissão para acessar: {caminho}")
                toaster.show_toast(
                    "⚠️ Erro de Permissão",
                    "Sem permissão para acessar a pasta.",
                    duration=3,
                    icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
                )
                return
            
            # Tentar abrir no Explorer
            try:
                subprocess.Popen(['explorer', caminho])
                logging.info(f"Pasta aberta: {caminho}")
            except Exception as e1:
                logging.warning(f"Erro ao abrir pasta (tentativa 1): {e1}")
                # Fallback com aspas
                try:
                    subprocess.Popen(f'explorer "{caminho}"', shell=True)
                    logging.info(f"Pasta aberta (fallback): {caminho}")
                except Exception as e2:
                    logging.error(f"Erro ao abrir pasta (tentativa 2): {e2}")
                    toaster.show_toast(
                        "⚠️ Erro",
                        "Não foi possível abrir a pasta.",
                        duration=3,
                        icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
                    )
        else:
            logging.warning("Nenhuma pasta válida configurada")
            toaster.show_toast(
                "⚠️ Nenhuma pasta válida",
                "Defina uma pasta primeiro.",
                duration=3,
                icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
            )
    except Exception as e:
        logging.error(f"Erro inesperado ao abrir pasta: {e}")
        toaster.show_toast(
            "⚠️ Erro",
            "Erro ao processar solicitação.",
            duration=3,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )

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
        
        # Pequeno delay para evitar comportamento suspeito
        time.sleep(0.5)
        
        nova = escolher_pasta()
        if nova and os.path.exists(nova):
            pasta = nova
            salvar_config(pasta)
            
            # Delay adicional antes de reiniciar
            time.sleep(0.5)
            
            threading.Thread(target=iniciar_monitor, args=(pasta,), daemon=True).start()
            toaster.show_toast(
                "📂 Pasta alterada",
                f"Agora monitorando:\n{pasta}",
                duration=3,
                icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
            )
            logging.info(f"Pasta alterada para: {pasta}")
        else:
            logging.warning("Nova pasta não selecionada ou inválida")
            # Reiniciar monitor com pasta anterior se existir
            if pasta and os.path.exists(pasta):
                threading.Thread(target=iniciar_monitor, args=(pasta,), daemon=True).start()
    except Exception as e:
        logging.error(f"Erro ao alterar pasta: {e}")
        toaster.show_toast(
            "⚠️ Erro",
            "Erro ao alterar pasta.",
            duration=3,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )

def sair(icon, item):
    """
    Encerra o aplicativo de forma graceful e segura.
    Para o monitor, exibe notificação de encerramento e fecha adequadamente.
    
    Args:
        icon: Ícone da bandeja do sistema.
        item: Item do menu clicado.
    """
    try:
        logging.info("Iniciando encerramento do aplicativo")
        
        # Parar o monitor de forma segura
        parar_monitor()
        
        # Notificar o usuário
        toaster.show_toast(
            "👋 Encerrando TUBA",
            "O monitor foi encerrado.",
            duration=2,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )
        
        # Aguardar a notificação aparecer (evita comportamento suspeito)
        time.sleep(2.5)
        
        # Parar o ícone da bandeja
        icon.stop()
        
        logging.info("Aplicativo encerrado com sucesso")
        
        # Usar sys.exit ao invés de os._exit para encerramento graceful
        sys.exit(0)
    except Exception as e:
        logging.error(f"Erro durante encerramento: {e}")
        # Em caso de erro, tentar encerrar mesmo assim
        try:
            icon.stop()
        except:
            pass
        sys.exit(1)

def iniciar_bandeja():
    """
    Inicia o ícone na bandeja do sistema com o menu de opções.
    Carrega o ícone e configura o menu com as ações disponíveis.
    """
    try:
        # Validar se o ícone existe
        if not os.path.exists(ICON_PATH):
            logging.error(f"Ícone não encontrado: {ICON_PATH}")
            # Tentar continuar sem ícone
            image = None
        else:
            # Carregar ícone a partir do resource_path (funciona no exe)
            image = Image.open(ICON_PATH)
            logging.info("Ícone carregado com sucesso")
        
        # Criar menu da bandeja
        menu = (
            item("📂 Alterar pasta monitorada", alterar_pasta),
            item("📂 Abrir pasta monitorada", abrir_pasta),
            item("❌ Sair", sair)
        )
        
        # Criar e executar ícone da bandeja
        icone = pystray.Icon("TUBA", image, f"{APP_NAME} v{APP_VERSION}", menu)
        logging.info("Iniciando ícone da bandeja")
        icone.run()
    except Exception as e:
        logging.error(f"Erro ao iniciar bandeja: {e}")
        # Em caso de erro crítico, notificar e encerrar
        try:
            toaster.show_toast(
                "⚠️ Erro Crítico",
                "Não foi possível iniciar a interface.",
                duration=5
            )
            time.sleep(5)
        except:
            pass
        sys.exit(1)

# ---------------------------------------------------
# Inicialização principal
# ---------------------------------------------------
# NOTA: Para reduzir falsos positivos de antivírus, este executável deve ser
# assinado digitalmente após a compilação usando signtool.exe ou ferramenta similar.
# Exemplo: signtool sign /f certificado.pfx /p senha /t http://timestamp.server tuba_monitor.exe

if __name__ == "__main__":
    try:
        logging.info(f"=== Iniciando {APP_NAME} v{APP_VERSION} ===")
        logging.info(f"Autor: {APP_AUTHOR}")
        logging.info(f"Descrição: {APP_DESCRIPTION}")
        
        # Verificar recursos necessários
        if not verificar_recursos():
            logging.warning("Alguns recursos estão faltando, mas continuando...")
        
        # Carregar configuração
        pasta = carregar_config()
        if not pasta:
            logging.error("Nenhuma pasta selecionada")
            toaster.show_toast(
                "⚠️ Nenhuma pasta selecionada",
                "Selecione uma pasta para monitorar.",
                duration=4,
                icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
            )
            time.sleep(4)
            sys.exit(1)
        
        # Validar pasta antes de iniciar
        if not os.path.exists(pasta):
            logging.error(f"Pasta configurada não existe: {pasta}")
            toaster.show_toast(
                "⚠️ Pasta inválida",
                "A pasta configurada não existe mais.",
                duration=4,
                icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
            )
            time.sleep(4)
            sys.exit(1)
        
        # Delay inicial para evitar comportamento suspeito
        time.sleep(0.5)
        
        # Iniciar monitoramento em thread daemon
        threading.Thread(target=iniciar_monitor, args=(pasta,), daemon=True).start()
        
        # Iniciar interface da bandeja (loop principal)
        iniciar_bandeja()
        
    except KeyboardInterrupt:
        logging.info("Encerramento via Ctrl+C")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Erro crítico na inicialização: {e}", exc_info=True)
        try:
            toaster.show_toast(
                "⚠️ Erro Crítico",
                f"Erro ao iniciar: {str(e)[:50]}",
                duration=5
            )
            time.sleep(5)
        except:
            pass
        sys.exit(1)
