# Templates de Imagem para Automação Desktop (Senior)

Esta pasta armazena as capturas de tela (PNG) utilizadas pelo módulo de Visão Computacional (OpenCV + PyAutoGUI) para identificar os elementos da interface do sistema Senior Desktop.

## Lista de Templates Necessários (Passo a Passo do PDD):

| Arquivo PNG | Descrição no PDD | Passo |
|---|---|---|
| `pasta_senior.png` | Ícone da pasta "Senior" na Área de Trabalho do Windows | Passo 2.1 |
| `modulo_ponto.png` | Opção / Ícone "Controle de Ponto e Refeitório" | Passo 2.2 |
| `campo_login.png` | Campo para digitação do login na tela de autenticação | Passo 3.1 |
| `botao_autenticar.png` | Botão "Autenticar" | Passo 3.3 |
| `menu_calculos.png` | Aba superior "Cálculos" | Passo 4.1 |
| `menu_apuracao.png` | Submenu "Apuração" | Passo 4.2 |
| `menu_listar.png` | Submenu "Listar" | Passo 4.3 |
| `menu_cartao_ponto.png` | Opção "Cartão Ponto" | Passo 4.4 |
| `codigo_702.png` | Linha correspondente ao relatório código "702" | Passo 5.1 |
| `botao_executar.png` | Botão "Executar" | Passo 5.2 |
| `campo_data_inicial.png` | Campo "Data Inicial" na tela de parâmetros | Passo 6.1 |
| `botao_ok.png` | Botão "OK" na tela de parâmetros | Passo 6.3 |
| `relatorio_visualizador.png` | Elemento da janela de visualização do relatório pronto | Passo 7 |
| `botao_salvar_relatorio.png` | Ícone de Salvar / Exportar PDF do relatório consolidado | Passo 7 |

## Dicas para Captura de Templates:
1. Recorte apenas o elemento de interesse (ex: o ícone ou o texto do botão), evitando áreas de fundo que possam mudar de cor ou contraste.
2. Salve no formato PNG sem compressão com perdas.
3. Você pode usar a ferramenta nativa do Windows (Win + Shift + S) ou o comando da CLI Digitaly:
   ```bash
   python manage.py automate-shot --out captura.png
   ```

