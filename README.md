# NOTIFICA-O-DE-PEDIDOS (TUBA)

Um utilitário para monitorar pastas e notificar quando novos arquivos são adicionados. O projeto fornece uma aplicação de bandeja (tray) que mostra notificações do Windows, toca sons e mantém um contador diário de arquivos detectados.

**Principais características**
- **Notificações**: mostra notificações nativas do Windows usando `win10toast`.
- **Sons**: toca alertas sonoros para eventos (usa `winsound`).
- **Bandeja (Tray)**: ícone na bandeja com menu para escolher pasta, iniciar/parar e abrir a pasta monitorada (`pystray`).
- **Contador diário**: reinicia o contador automaticamente quando o dia muda.
- **Persistência**: salva a pasta monitorada em `config.json` ao lado do executável/script.

**Requisitos**
- **SO**: Windows 10 / 11 (o código usa APIs e utilitários do Windows como `winsound` e `explorer`).
- **Python**: 3.8+ (recomendado usar a versão mais recente estável do Python 3).
- **Pacotes Python**: `watchdog`, `win10toast`, `pystray`, `Pillow`.
- **Tkinter**: já incluído nas distribuições oficiais do Python (usado para selecionar pasta via diálogo).

**Instalação (desenvolvimento)**
1. Clone o repositório:

```bash
git clone https://github.com/rtheuz/NOTIFICA-O-DE-PEDIDOS.git
cd NOTIFICA-O-DE-PEDIDOS
```

2. Crie e ative um ambiente virtual (opcional, recomendado):

```bash
python -m venv .venv
.venv\\Scripts\\activate
```

3. Instale dependências:

```bash
pip install watchdog win10toast pystray Pillow
```

Observação: `tkinter` normalmente já vem com o instalador do Python para Windows.

**Uso**
- Para executar em modo desenvolvimento (Windows):

```bash
python tuba_monitor.py
```

- No primeiro início, o aplicativo pede para escolher a pasta a ser monitorada (diálogo). Após isso, ele roda na bandeja e mostra notificações e sons quando novos arquivos são criados dentro da pasta monitorada.

- Menu da bandeja:
  - `Escolher pasta` — abrir diálogo para selecionar a pasta.
  - `Abrir pasta monitorada` — tenta abrir a pasta no Explorer.
  - `Iniciar` — inicia o monitoramento (se não estiver ativo).
  - `Parar` — pausa o monitoramento.
  - `Sair` — encerra o aplicativo.

**Arquivos de configuração / recursos**
- `config.json` — salvo automaticamente na mesma pasta do executável/script; contém a chave `pasta_monitorada`.
- `icone.ico`, `alert.wav`, `start.wav`, `pause.wav` — recursos usados pela aplicação (devem estar disponíveis ao empacotar a aplicação).

**Construir executável (opcional)**
Recomenda-se usar o `PyInstaller` para gerar um `.exe` autônomo. Exemplo de comando (executar no Windows):

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --icon="icone.ico" --name="TUBA" `
  --add-data "icone.ico;." `
  --add-data "alert.wav;." `
  --add-data "start.wav;." `
  --add-data "pause.wav;." `
  tuba_monitor.py

```

Observação: o separador em `--add-data` é `;` no Windows e `:` em sistemas Unix. Ajuste conforme necessário.

**Limitações e problemas conhecidos**
- Esta aplicação foi desenvolvida para Windows. Em outros sistemas operacionais as bibliotecas usadas podem não funcionar (por exemplo, `winsound`, `win10toast`, e chamadas para `explorer`).
- `pystray` pode precisar de backends adicionais em diferentes ambientes.

**Contribuição**
- Sugestões, correções e melhorias são bem-vindas. Abra uma issue ou envie um pull request com a descrição das mudanças.

**Contato**
- Autor: rtheuz
- Repositório: `https://github.com/rtheuz/NOTIFICA-O-DE-PEDIDOS`

---

Se quiser, eu posso:
- gerar um `requirements.txt` com as dependências listadas;
- adicionar um exemplo de `pyinstaller` já ajustado para os arquivos do projeto;
- ou adaptar o código para suportar Linux/macOS (com notificações alternativas).

