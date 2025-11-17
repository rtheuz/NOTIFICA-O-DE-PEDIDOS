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
from pystray import MenuItem as item, Menu
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
monitor_ativo = False

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

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        # Forçar janela para frente
        root.attributes('-topmost', True)
        root.update()
        pasta = filedialog.askdirectory(title="Selecione a pasta para monitorar", parent=root)
        logging.info(f"Pasta selecionada: {pasta if pasta else 'Nenhuma'}")
        return pasta if pasta else None
    except Exception as e:
        logging.error(f"Erro ao escolher pasta: {e}")
        return None
    finally:
        # Garantir que a janela seja destruída de forma segura
        if root is not None:
            try:
                root.quit()
                root.destroy()
            except Exception as e:
                logging.warning(f"Erro ao destruir janela tkinter: {e}")

def salvar_config(pasta_path):

    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"pasta": pasta_path}, f)
        logging.info(f"Configuração salva: {pasta_path}")
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar configuração: {e}")
        return False

def carregar_config():

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

    
    def on_created(self, event):
        
        try:
            if not event.is_directory:
                nome = os.path.basename(event.src_path)
                                       
                logging.info(f"Novo arquivo detectado: {nome})")
                
                # Notificação nativa do Windows com contador
                toaster.show_toast(
                    f"📄 Novo arquivo detectado!",
                    f"{nome}",
                    duration=3,
                    icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
                )
                
                # Tocar som de alerta
                tocar_som(ALERT_SOUND)
        except Exception as e:
            logging.error(f"Erro ao processar arquivo criado: {e}")

def iniciar_monitor(pasta_path):

    global observer, monitor_ativo
    
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
            monitor_ativo = True
            
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

    global observer, monitor_ativo
    
    try:
        with monitor_lock:
            if observer is not None and observer.is_alive():
                observer.stop()
                observer.join(timeout=5)  # Aguardar até 5 segundos
                monitor_ativo = False
                logging.info("Monitor parado com sucesso")
                tocar_som(PAUSE_SOUND)
                return True
            else:
                logging.warning("Monitor não estava ativo")
                monitor_ativo = False
                return False
    except Exception as e:
        logging.error(f"Erro ao parar monitor: {e}")
        monitor_ativo = False
        return False

# ---------------------------------------------------
# Abertura da pasta monitorada (nova função solicitada)
# ---------------------------------------------------
def abrir_pasta(icon, item):

    global pasta
    
    try:
        # Obter caminho da pasta
        caminho = pasta or carregar_config() or ""
        logging.info(f"Tentando abrir pasta: {caminho}")
        
        # Verificar se o caminho existe
        if not caminho:
            logging.warning("Nenhuma pasta configurada")
            toaster.show_toast(
                "⚠️ Nenhuma pasta válida",
                "Defina uma pasta primeiro.",
                duration=3,
                icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
            )
            return
            
        if not os.path.exists(caminho):
            logging.error(f"Pasta não existe: {caminho}")
            toaster.show_toast(
                "⚠️ Pasta não encontrada",
                "A pasta configurada não existe.",
                duration=3,
                icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
            )
            return
        
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
        logging.info(f"Abrindo pasta: {caminho}")
        try:
            # Método preferido no Windows
            os.startfile(caminho)
            logging.info("Pasta aberta com sucesso usando os.startfile")
        except AttributeError:
            # os.startfile não existe (não é Windows)
            logging.info("os.startfile não disponível, usando subprocess")
            try:
                subprocess.Popen(['explorer', caminho])
                logging.info("Pasta aberta com explorer")
            except Exception as e2:
                logging.error(f"Erro ao abrir com explorer: {e2}")
                toaster.show_toast(
                    "⚠️ Erro",
                    "Não foi possível abrir a pasta.",
                    duration=3,
                    icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
                )
        except Exception as e1:
            logging.error(f"Erro ao abrir pasta: {e1}")
            # Fallback final
            try:
                subprocess.Popen(f'explorer "{caminho}"', shell=True)
                logging.info("Pasta aberta com fallback shell")
            except Exception as e3:
                logging.error(f"Erro no fallback: {e3}")
                toaster.show_toast(
                    "⚠️ Erro",
                    "Não foi possível abrir a pasta.",
                    duration=3,
                    icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
                )
                
    except Exception as e:
        logging.error(f"Erro inesperado ao abrir pasta: {e}", exc_info=True)
        toaster.show_toast(
            "⚠️ Erro",
            "Erro ao processar solicitação.",
            duration=3,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )

def mostrar_sobre(icon, item):
    try:
        mensagem = f"{APP_NAME} v{APP_VERSION}\n"
        mensagem += f"Por {APP_AUTHOR}\n\n"
        mensagem += f"{APP_DESCRIPTION}\n\n"
        mensagem += "Sistema de monitoramento profissional\n"
        mensagem += "com notificações em tempo real."
        
        toaster.show_toast(
            f"ℹ️ Sobre - {APP_NAME}",
            mensagem,
            duration=6,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )
        logging.info("Informações 'Sobre' exibidas")
    except Exception as e:
        logging.error(f"Erro ao exibir informações sobre: {e}")

# ---------------------------------------------------
# Ícone da bandeja
# ---------------------------------------------------
def alterar_pasta(icon, item):
    
    global pasta
    
    try:
        logging.info("Alterando pasta monitorada")
        parar_monitor()
        
        # Pequeno delay para evitar comportamento suspeito
        time.sleep(0.3)
        
        nova = escolher_pasta()
        if nova and os.path.exists(nova):
            pasta = nova
            salvar_config(pasta)
            
            # Delay adicional antes de reiniciar
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
            # Reiniciar monitor com pasta anterior se existir
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
            # Reiniciar monitor com pasta anterior se existir
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

    try:
        logging.info("Iniciando encerramento do aplicativo")
        
        # Parar o monitor de forma segura
        parar_monitor()
        
        # Notificar o usuário
        toaster.show_toast(
            "👋 Encerrando TUBA",
            "O monitor foi encerrado.",
            duration=1,
            icon_path=ICON_PATH if os.path.exists(ICON_PATH) else None
        )
        
        # Aguardar brevemente para garantir a notificação
        time.sleep(1.2)
        
        logging.info("Aplicativo encerrado com sucesso")
        
        # Parar o ícone da bandeja (isso encerra o loop principal do pystray)
        icon.stop()
        
    except Exception as e:
        logging.error(f"Erro durante encerramento: {e}")
        # Em caso de erro, tentar encerrar mesmo assim
        try:
            icon.stop()
        except:
            pass

def iniciar_bandeja():
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
        
        # Criar menu da bandeja com melhor organização e separadores
        menu = (
                 
            # Seção de pastas
            item("📂 Abrir pasta monitorada", abrir_pasta),
            item("🔄 Alterar pasta monitorada", alterar_pasta),
            Menu.SEPARATOR,
            
            # Seção de informações e configurações
            item("ℹ️ Sobre", mostrar_sobre),
            Menu.SEPARATOR,
            
            # Sair
            item("❌ Sair", sair)
        )
        
        # Criar e executar ícone da bandeja com título dinâmico
        titulo = f"{APP_NAME} v{APP_VERSION} - {'🟢 Ativo' if monitor_ativo else '🔴 Pausado'}"
        icone = pystray.Icon("TUBA", image, titulo, menu)
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
        logging.info(f"Pasta carregada na inicialização: {pasta}")
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
