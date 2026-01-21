import os
import pandas as pd
import requests
import time
from datetime import datetime
import re
from pandas.tseries.offsets import MonthBegin
import numpy as np
from datetime import datetime, timedelta
import argparse

nocache = False

def convert_to_integer(df):
    for col in df.select_dtypes(include=['float', 'int']).columns:
        df[col] = df[col].astype(int)
    return df

def baixar_csv_generico(nome_arquivo, url, pasta_temp="temp", ano = ""):
    """
    Função genérica para baixar um arquivo CSV de uma URL e salvar na pasta especificada, 
    verificando se o arquivo já existe ou se precisa ser atualizado.
    
    Parâmetros:
    - nome_arquivo: Nome base para o arquivo (sem extensão).
    - url: URL de onde o CSV será baixado.
    - pasta_temp: Diretório onde o arquivo será salvo (padrão: 'temp').
    - ano: Ano do arquivo (opcional).
    
    Retorna:
    - DataFrame Pandas com o conteúdo do CSV.
    
    Nota: Usa a variável global 'nocache' para determinar se deve ignorar cache.
    """
    
    global nocache
    
    # Verificar se a pasta temporária existe, se não, criá-la
    if not os.path.exists(pasta_temp):
        os.makedirs(pasta_temp)
    
    # Definir o nome completo do arquivo baseado no ano atual
    ano_atual = datetime.now().year

    arquivo_csv = os.path.join(pasta_temp, f"{nome_arquivo}_{ano}.csv") if ano else os.path.join(pasta_temp, f"{nome_arquivo}.csv")

    # Verificar se o arquivo já existe, se tem ano e não é o ano atual, e nocache não está ativo
    if os.path.exists(arquivo_csv) and ano != "" and ano != str(ano_atual) and not nocache:
        print(f"Arquivo já existe em: {arquivo_csv}")
        try :
            return pd.read_csv(arquivo_csv, sep=';', low_memory=False)
        except:
            count = count + 1 if 'count' in locals() else 1
            if count < 10:
                print("tentando novamente:....{count}")
                os.remove(arquivo_csv)
                baixar_csv_generico(nome_arquivo, url, pasta_temp, ano)    
            else:
                print("não rolou:....{count}")
                raise SystemExit("Erro fatal: O programa foi encerrado.")
    # Caso o arquivo não exista ou o ano seja o atual, fazer o download
    print(f"Baixando o CSV de {nome_arquivo}...{url}")
    
    # Headers para simular um navegador
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    # Tentar baixar com retry e suporte a resumable download
    max_tentativas = 5
    arquivo_temp = arquivo_csv + '.tmp'
    
    for tentativa in range(max_tentativas):
        try:
            # Verificar se há download parcial
            resume_byte_pos = 0
            if os.path.exists(arquivo_temp):
                resume_byte_pos = os.path.getsize(arquivo_temp)
                headers['Range'] = f'bytes={resume_byte_pos}-'
                print(f"Retomando download a partir de {resume_byte_pos} bytes...")
            
            response = requests.get(url, timeout=300, stream=True, headers=headers.copy())
            
            # 200 = download completo, 206 = partial content (resumindo)
            if response.status_code in [200, 206]:
                mode = 'ab' if response.status_code == 206 else 'wb'
                with open(arquivo_temp, mode) as file:
                    bytes_downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)
                            bytes_downloaded += len(chunk)
                            # Mostrar progresso a cada 10MB
                            if bytes_downloaded % (10 * 1024 * 1024) < 8192:
                                print(f"Downloaded: {(resume_byte_pos + bytes_downloaded) / (1024*1024):.2f} MB")
                
                # Download completo, renomear arquivo temporário
                if os.path.exists(arquivo_csv):
                    os.remove(arquivo_csv)
                os.rename(arquivo_temp, arquivo_csv)
                print(f"Arquivo salvo em: {arquivo_csv}")
                break
            else:
                print(f"Erro ao baixar o arquivo: {response.status_code}")
                if tentativa == max_tentativas - 1:
                    return None
        except (requests.exceptions.ChunkedEncodingError, 
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            print(f"Erro na tentativa {tentativa + 1}/{max_tentativas}: {type(e).__name__}")
            if tentativa < max_tentativas - 1:
                print(f"Aguardando 5 segundos antes de tentar novamente...")
                time.sleep(5)
                # Remove Range header para próxima tentativa caso arquivo temp não exista
                if 'Range' in headers:
                    del headers['Range']
            else:
                print(f"Falha após {max_tentativas} tentativas")
                # Limpar arquivo temporário em caso de falha final
                if os.path.exists(arquivo_temp):
                    os.remove(arquivo_temp)
                return None
    # Ler e retornar o CSV baixado
    try:
        return pd.read_csv(arquivo_csv, sep=';', low_memory=False)
    except Exception as e:
        print(f"Erro ao ler arquivo par dataframe")
        print(f"Detalhes do erro: {str(e)}")
        time.sleep(3)
        baixar_csv_generico(nome_arquivo, url, pasta_temp, ano)
        
def pegar_deputados(pasta_temp="temp"):
    """
    Função que baixa e processa o arquivo de deputados.
    
    Parâmetros:
    - pasta_temp: Diretório onde o arquivo CSV será salvo (padrão: 'temp').
    
    Retorna:
    - DataFrame Pandas com o conteúdo dos deputados.
    """
    
    url = 'http://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv'
    
    # Utiliza a função genérica para baixar o CSV
    data = baixar_csv_generico("deputados", url, pasta_temp)

    # Se o download foi bem-sucedido, processar o DataFrame
    if data is not None:
        # Extrair idDeputado do campo 'uri'
        data['idDeputado'] = data['uri'].apply(lambda x: re.search(r'\d+$', x).group() if pd.notnull(x) else None)

        # Selecionar colunas relevantes
        data = data[['idDeputado', 'nome', 'nomeCivil', 'cpf', 'siglaSexo']].copy()

        # Converter idDeputado para string e remover duplicatas
        data['idDeputado'] = data['idDeputado'].astype(str)
        data = data.drop_duplicates()

    return data

def pegar_proposicoes(ano_atual, ano_ini_legis, pasta_temp="temp", mes=""):
    """
    Função que baixa os arquivos de proposições para os anos entre o ano atual e o ano de início da legislatura.
    
    Parâmetros:
    - ano_atual: Ano atual.
    - ano_ini_legis: Ano inicial da legislatura.
    - pasta_temp: Diretório onde os arquivos CSV serão salvos (padrão: 'temp').
    - mes: Mês para filtrar até o final (formato: 01-12, padrão: vazio).
    
    Retorna:
    - DataFrame Pandas com o conteúdo de todas as proposições.
    """
    
    proposicoes = pd.DataFrame()  # DataFrame vazio para acumular as proposições

    for ano in range(ano_ini_legis, ano_atual + 1):
        print(f"Baixando proposições para o ano {ano}...")

        # Construir a URL para o ano específico
        url = f"http://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-{ano}.csv"
        
        # Utiliza a função genérica para baixar o CSV
        data = baixar_csv_generico(f"proposicoes", url, pasta_temp, str(ano))

        # Se o download foi bem-sucedido, processar o DataFrame
        if data is not None:
            # Selecionar colunas relevantes e renomear id para id.proposicao
            data = data[['id', 'siglaTipo', 'numero', 'ano', 'descricaoTipo', 'dataApresentacao',
                         'ementa', 'keywords', 'ultimoStatus_regime']].copy()
            data.rename(columns={'id': 'id.proposicao'}, inplace=True)
            
            # Adicionar coluna com o ano em loop
            data['ano.loop'] = ano
            data['dataApresentacao'] = pd.to_datetime(data['dataApresentacao'])
            
            # Filtrar até o final do mês especificado no ano_atual
            if mes and ano == ano_atual:
                # Criar data limite: último dia do mês especificado no ano_atual
                from calendar import monthrange
                ultimo_dia = monthrange(ano_atual, int(mes))[1]
                data_limite = pd.Timestamp(year=ano_atual, month=int(mes), day=ultimo_dia, hour=23, minute=59, second=59)
                data = data[data['dataApresentacao'] <= data_limite]
            
            data['dataApresentacao'] = data['dataApresentacao'].dt.strftime('%Y-%m-%dT%H:%M:%S')
            # Concatenar os dados baixados ao DataFrame principal
            proposicoes = pd.concat([proposicoes, data], ignore_index=True)
    
    # Aplicar filtro final se mes foi especificado
    if mes:
        from calendar import monthrange
        ultimo_dia = monthrange(ano_atual, int(mes))[1]
        data_limite_str = f"{ano_atual}-{int(mes):02d}-{ultimo_dia}T23:59:59"
        proposicoes['dataApresentacao_temp'] = pd.to_datetime(proposicoes['dataApresentacao'])
        proposicoes = proposicoes[proposicoes['dataApresentacao_temp'] <= data_limite_str]
        proposicoes = proposicoes.drop(columns=['dataApresentacao_temp'])
    
    # Filtrar proposições para garantir que não há datas anteriores ao ano_ini_legis
    data_ini_legis = f"{ano_ini_legis}-01-01T00:00:00"
    proposicoes['dataApresentacao_temp'] = pd.to_datetime(proposicoes['dataApresentacao'])
    proposicoes = proposicoes[proposicoes['dataApresentacao_temp'] >= data_ini_legis]
    proposicoes = proposicoes.drop(columns=['dataApresentacao_temp'])
    
    return proposicoes


def pegar_autores_proposicoes(ano_atual, ano_ini_legis, pasta_temp="temp"):
    """
    Função que baixa os arquivos de autores das proposições para os anos entre o ano atual e o ano de início da legislatura.
    
    Parâmetros:
    - ano_atual: Ano atual.
    - ano_ini_legis: Ano inicial da legislatura.
    - pasta_temp: Diretório onde os arquivos CSV serão salvos (padrão: 'temp').
    
    Retorna:
    - DataFrame Pandas com o conteúdo de todos os autores das proposições.
    """
    
    autores_prop = pd.DataFrame()  # DataFrame vazio para acumular os autores das proposições

    for ano in range(ano_ini_legis, ano_atual + 1):
        print(f"Baixando autores das proposições para o ano {ano}...")

        # Construir a URL para o ano específico
        url = f"http://dadosabertos.camara.leg.br/arquivos/proposicoesAutores/csv/proposicoesAutores-{ano}.csv"
        
        # Utiliza a função genérica para baixar o CSV
        data = baixar_csv_generico(f"proposicoesAutores", url, pasta_temp, str(ano))

        # Se o download foi bem-sucedido, processar o DataFrame
        if data is not None:
            # Adicionar coluna com o ano em loop
            data['ano.loop'] = ano

            # Concatenar os dados baixados ao DataFrame principal
            autores_prop = pd.concat([autores_prop, data], ignore_index=True)

    autores_prop['idDeputadoAutor'] =autores_prop['idDeputadoAutor'].fillna(0).astype(int)
    autores_prop['idDeputadoAutor'] = autores_prop['idDeputadoAutor'].astype('int64')
    return autores_prop


def pegar_temas_proposicoes(ano_atual, ano_ini_legis, pasta_temp="temp"):
    """
    Função que baixa os arquivos de temas das proposições para os anos entre o ano atual e o ano de início da legislatura.
    
    Parâmetros:
    - ano_atual: Ano atual.
    - ano_ini_legis: Ano inicial da legislatura.
    - pasta_temp: Diretório onde os arquivos CSV serão salvos (padrão: 'temp').
    
    Retorna:
    - DataFrame Pandas com o conteúdo de todos os temas das proposições.
    """
    
    temas_prop = pd.DataFrame()  # DataFrame vazio para acumular os temas das proposições

    for ano in range(ano_ini_legis, ano_atual + 1):
        print(f"Baixando temas das proposições para o ano {ano}...")

        # Construir a URL para o ano específico
        url = f"http://dadosabertos.camara.leg.br/arquivos/proposicoesTemas/csv/proposicoesTemas-{ano}.csv"
        
        # Utiliza a função genérica para baixar o CSV
        data = baixar_csv_generico(f"proposicoesTemas", url, pasta_temp, str(ano))

        # Se o download foi bem-sucedido, processar o DataFrame
        if data is not None:
            # Extrair id.proposicao do campo 'uriProposicao'
            data['id.proposicao'] = data['uriProposicao'].apply(lambda x: re.search(r'\d+$', x).group() if pd.notnull(x) else None)

            # Remover a coluna 'uriProposicao'
            data = data.drop(columns=['uriProposicao'])

            # Adicionar coluna com o ano em loop
            data['ano.loop'] = ano

            # Concatenar os dados baixados ao DataFrame principal
            temas_prop = pd.concat([temas_prop, data], ignore_index=True)
    
    return temas_prop

def pegar_eventos(ano_atual, ano_ini_legis, pasta_temp="temp", mes=""):
    """
    Função que baixa os arquivos de eventos para os anos entre o ano atual e o ano de início da legislatura.
    
    Parâmetros:
    - ano_atual: Ano atual.
    - ano_ini_legis: Ano inicial da legislatura.
    - pasta_temp: Diretório onde os arquivos CSV serão salvos (padrão: 'temp').
    - mes: Mês para filtrar até o final (formato: 01-12, padrão: vazio).
    
    Retorna:
    - DataFrame Pandas com o conteúdo de todos os eventos.
    """
    
    eventos = pd.DataFrame()  # DataFrame vazio para acumular os eventos

    for ano in range(ano_ini_legis, ano_atual + 1):
        print(f"Baixando eventos para o ano {ano}...")

        # Construir a URL para o ano específico
        url = f"http://dadosabertos.camara.leg.br/arquivos/eventos/csv/eventos-{ano}.csv"
        
        # Utiliza a função genérica para baixar o CSV
        data = baixar_csv_generico(f"eventos", url, pasta_temp, str(ano))

        # Se o download foi bem-sucedido, processar o DataFrame
        if data is not None:
            # Se for o primeiro ano (ano_ini_legis), inicializa o DataFrame eventos
            if ano == ano_ini_legis:
                eventos = data
            else:
                # Caso contrário, concatena os novos dados ao DataFrame de eventos
                eventos = pd.concat([eventos, data], ignore_index=True)

    
    # Aplicar filtros finais
    if 'dataHoraInicio' in eventos.columns:
        eventos['dataHoraInicio_temp'] = pd.to_datetime(eventos['dataHoraInicio'])
        
        # Filtrar por data inicial da legislatura
        data_ini_legis = f"{ano_ini_legis}-01-01T00:00:00"
        eventos = eventos[eventos['dataHoraInicio_temp'] >= data_ini_legis]
        
        # Filtrar até o final do mês especificado se mes foi fornecido
        if mes:
            from calendar import monthrange
            ultimo_dia = monthrange(ano_atual, int(mes))[1]
            data_limite_str = f"{ano_atual}-{int(mes):02d}-{ultimo_dia}T23:59:59"
            eventos = eventos[eventos['dataHoraInicio_temp'] <= data_limite_str]
        
        eventos = eventos.drop(columns=['dataHoraInicio_temp'])
    
    return eventos

def pegar_presenca_eventos_deputados(ano_atual, ano_ini_legis, pasta_temp="temp", mes=""):
    """
    Função que baixa os arquivos de presença em eventos dos deputados para os anos entre o ano atual e o ano de início da legislatura.
    
    Parâmetros:
    - ano_atual: Ano atual.
    - ano_ini_legis: Ano inicial da legislatura.
    - pasta_temp: Diretório onde os arquivos CSV serão salvos (padrão: 'temp').
    - mes: Mês para filtrar até o final (formato: 01-12, padrão: vazio).
    
    Retorna:
    - DataFrame Pandas com o conteúdo de presença em eventos dos deputados.
    """
    dep_eventos = pd.DataFrame()  # DataFrame vazio para acumular os dados de presença em eventos
    for ano in range(ano_ini_legis, ano_atual + 1):
        print(f"Baixando presença de eventos para o ano {ano}...")
        url = f"http://dadosabertos.camara.leg.br/arquivos/eventosPresencaDeputados/csv/eventosPresencaDeputados-{ano}.csv"
        data = baixar_csv_generico(f"eventosPresencaDeputados", url, pasta_temp, str(ano))
        if data is not None:
            data = data[['idEvento', 'dataHoraInicio', 'idDeputado']]
            dep_eventos = pd.concat([dep_eventos, data], ignore_index=True)
    
    # Aplicar filtros finais
    if 'dataHoraInicio' in dep_eventos.columns:
        dep_eventos['dataHoraInicio_temp'] = pd.to_datetime(dep_eventos['dataHoraInicio'])
        
        # Filtrar por data inicial da legislatura
        data_ini_legis = f"{ano_ini_legis}-01-01T00:00:00"
        dep_eventos = dep_eventos[dep_eventos['dataHoraInicio_temp'] >= data_ini_legis]
        
        # Filtrar até o final do mês especificado se mes foi fornecido
        if mes:
            from calendar import monthrange
            ultimo_dia = monthrange(ano_atual, int(mes))[1]
            data_limite_str = f"{ano_atual}-{int(mes):02d}-{ultimo_dia}T23:59:59"
            dep_eventos = dep_eventos[dep_eventos['dataHoraInicio_temp'] <= data_limite_str]
        
        dep_eventos = dep_eventos.drop(columns=['dataHoraInicio_temp'])
    
    return dep_eventos

def pegar_requerimentos_eventos(ano_atual, ano_ini_legis, pasta_temp="temp", eventos_df=None):
    """
    Função que baixa os arquivos de requerimentos dos eventos para os anos entre o ano atual e o ano de início da legislatura.
    
    Parâmetros:
    - ano_atual: Ano atual.
    - ano_ini_legis: Ano inicial da legislatura.
    - pasta_temp: Diretório onde os arquivos CSV serão salvos (padrão: 'temp').
    - eventos_df: DataFrame de eventos filtrados para garantir que apenas requerimentos de eventos válidos sejam mantidos (opcional).
    
    Retorna:
    - DataFrame Pandas com os requerimentos dos eventos, filtrado se eventos_df for fornecido.
    """
    
    requer_eventos = pd.DataFrame()  # DataFrame vazio para acumular os requerimentos dos eventos

    for ano in range(ano_ini_legis, ano_atual + 1):
        print(f"Baixando requerimentos dos eventos para o ano {ano}...")

        # Construir a URL para o ano específico
        url = f"http://dadosabertos.camara.leg.br/arquivos/eventosRequerimentos/csv/eventosRequerimentos-{ano}.csv"
        
        # Utiliza a função genérica para baixar o CSV
        data = baixar_csv_generico(f"eventosRequerimentos", url, pasta_temp, str(ano))

        # Se o download foi bem-sucedido, processar o DataFrame
        if data is not None:
            # Extrair idRequerimento do campo 'uriRequerimento'
            data['idRequerimento'] = data['uriRequerimento'].apply(lambda x: re.search(r'\d+$', x).group() if pd.notnull(x) else None)

            # Selecionar colunas relevantes
            data = data[['idEvento', 'idRequerimento', 'tituloRequerimento']]

            # Concatenar os dados baixados ao DataFrame principal
            requer_eventos = pd.concat([requer_eventos, data], ignore_index=True)

    
    # Filtrar apenas requerimentos de eventos válidos se eventos_df for fornecido
    if eventos_df is not None and not eventos_df.empty and 'id' in eventos_df.columns:
        eventos_validos = eventos_df['id'].unique()
        requer_eventos = requer_eventos[requer_eventos['idEvento'].isin(eventos_validos)]
    
    return requer_eventos

def pegar_votacoes(ano_atual, ano_ini_legis, pasta_temp="temp", mes=""):
    """
    Função que baixa os arquivos de votações para os anos entre o ano atual e o ano de início da legislatura.
    
    Parâmetros:
    - ano_atual: Ano atual.
    - ano_ini_legis: Ano inicial da legislatura.
    - pasta_temp: Diretório onde os arquivos CSV serão salvos (padrão: 'temp').
    - mes: Mês para filtrar até o final (formato: 01-12, padrão: vazio).
    
    Retorna:
    - DataFrame Pandas com o conteúdo de todas as votações.
    """
    
    votacoes = pd.DataFrame()  # DataFrame vazio para acumular as votações

    for ano in range(ano_ini_legis, ano_atual + 1):
        print(f"Baixando votações para o ano {ano}...")

        # Construir a URL para o ano específico
        url = f"http://dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-{ano}.csv"
        
        # Utiliza a função genérica para baixar o CSV
        data = baixar_csv_generico(f"votacoes", url, pasta_temp, str(ano))

        # Se o download foi bem-sucedido, processar o DataFrame
        if data is not None:
            # Selecionar colunas relevantes (excluir colunas especificadas)
            data = data.drop(columns=['uri', 'uriOrgao', 'uriEvento', 
                                      'ultimaApresentacaoProposicao_descricao',
                                      'ultimaApresentacaoProposicao_uriProposicao'])

            # Concatenar os dados baixados ao DataFrame principal
            votacoes = pd.concat([votacoes, data], ignore_index=True)
    
    votacoes['aprovacao'] = votacoes['aprovacao'].fillna(0).astype(int)
    votacoes['aprovacao'] = votacoes['aprovacao'].astype('int64')
    
    # Aplicar filtros finais
    if 'dataHoraRegistro' in votacoes.columns:
        votacoes['dataHoraRegistro_temp'] = pd.to_datetime(votacoes['dataHoraRegistro'])
        
        # Filtrar por data inicial da legislatura
        data_ini_legis = f"{ano_ini_legis}-01-01T00:00:00"
        votacoes = votacoes[votacoes['dataHoraRegistro_temp'] >= data_ini_legis]
        
        # Filtrar até o final do mês especificado se mes foi fornecido
        if mes:
            from calendar import monthrange
            ultimo_dia = monthrange(ano_atual, int(mes))[1]
            data_limite_str = f"{ano_atual}-{int(mes):02d}-{ultimo_dia}T23:59:59"
            votacoes = votacoes[votacoes['dataHoraRegistro_temp'] <= data_limite_str]
        
        votacoes = votacoes.drop(columns=['dataHoraRegistro_temp'])

    return votacoes

def pegar_votacoes_deputados(ano_atual, ano_ini_legis, pasta_temp="temp", mes=""):
    """
    Função que baixa os arquivos de votações por deputado para os anos entre o ano atual e o ano de início da legislatura.
    
    Parâmetros:
    - ano_atual: Ano atual.
    - ano_ini_legis: Ano inicial da legislatura.
    - pasta_temp: Diretório onde os arquivos CSV serão salvos (padrão: 'temp').
    - mes: Mês para filtrar até o final (formato: 01-12, padrão: vazio).
    
    Retorna:
    - DataFrame Pandas com o conteúdo de todas as votações por deputado.
    """
    
    dep_votacoes = pd.DataFrame()  # DataFrame vazio para acumular as votações por deputado

    for ano in range(ano_ini_legis, ano_atual + 1):
        print(f"Baixando votações por deputado para o ano {ano}...")

        # Construir a URL para o ano específico
        url = f"http://dadosabertos.camara.leg.br/arquivos/votacoesVotos/csv/votacoesVotos-{ano}.csv"
        
        # Utiliza a função genérica para baixar o CSV
        data = baixar_csv_generico(f"votacoesVotos", url, pasta_temp, str(ano))

        # Se o download foi bem-sucedido, processar o DataFrame
        if data is not None:
            # Selecionar colunas relevantes
            data = data[['idVotacao', 'dataHoraVoto', 'voto', 'deputado_id', 'deputado_nome',
                         'deputado_siglaPartido', 'deputado_siglaUf', 'deputado_idLegislatura']].copy()

            # Concatenar os dados baixados ao DataFrame principal
            dep_votacoes = pd.concat([dep_votacoes, data], ignore_index=True)
    
    # Aplicar filtros finais
    if 'dataHoraVoto' in dep_votacoes.columns:
        dep_votacoes['dataHoraVoto_temp'] = pd.to_datetime(dep_votacoes['dataHoraVoto'])
        
        # Filtrar por data inicial da legislatura
        data_ini_legis = f"{ano_ini_legis}-01-01T00:00:00"
        dep_votacoes = dep_votacoes[dep_votacoes['dataHoraVoto_temp'] >= data_ini_legis]
        
        # Filtrar até o final do mês especificado se mes foi fornecido
        if mes:
            from calendar import monthrange
            ultimo_dia = monthrange(ano_atual, int(mes))[1]
            data_limite_str = f"{ano_atual}-{int(mes):02d}-{ultimo_dia}T23:59:59"
            dep_votacoes = dep_votacoes[dep_votacoes['dataHoraVoto_temp'] <= data_limite_str]
        
        dep_votacoes = dep_votacoes.drop(columns=['dataHoraVoto_temp'])
    
    return dep_votacoes


def pegar_votacoes_orientacoes(ano_atual, ano_ini_legis, pasta_temp="temp"):
    """
    Função que baixa os arquivos de votações e orientação dos líderes para os anos entre o ano atual e o ano de início da legislatura.
    """
    
    votacoes_orientacoes = pd.DataFrame()  # DataFrame vazio para acumular as votações e orientações

    for ano in range(ano_ini_legis, ano_atual + 1):
        print(f"Baixando votações e orientações para o ano {ano}...")

        # Construir a URL para o ano específico
        url = f"http://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/csv/votacoesOrientacoes-{ano}.csv"
        
        # Utiliza a função genérica para baixar o CSV
        data = baixar_csv_generico(f"votacoesOrientacoes", url, pasta_temp, str(ano))

        # Se o download foi bem-sucedido, processar o DataFrame
        if data is not None:
            # Extrair idBancada do campo 'uriBancada'
            data['idBancada'] = data['uriBancada'].apply(lambda x: re.search(r'\d+$', x).group() if pd.notnull(x) else None)

            # Selecionar colunas relevantes
            data = data[['idVotacao', 'siglaOrgao', 'orientacao', 'idBancada', 'siglaBancada']]

            # Concatenar os dados baixados ao DataFrame principal
            votacoes_orientacoes = pd.concat([votacoes_orientacoes, data], ignore_index=True)
    
    return votacoes_orientacoes


def pegar_cargos_deputados(legislatura, ano_ini_legis, ano_atual, mes=""):
    """
    Função que baixa os arquivos de cargos dos deputados para os anos entre o ano atual e o ano de início da legislatura.
    
    Parâmetros:
    - legislatura: Número da legislatura.
    - ano_ini_legis: Ano inicial da legislatura.
    - ano_atual: Ano atual.
    - mes: Mês para filtrar até o final (formato: 01-12, padrão: vazio).
    
    Retorna:
    - DataFrame Pandas com os cargos dos deputados que têm sobreposição com o período de interesse.
    """
    
    dep_cargo = pd.DataFrame()  # DataFrame vazio para acumular os cargos dos deputados

    print(f"Baixando cargos dos deputados para a legislatura {legislatura}...") 
    # Construir a URL para o ano específico
    url = f"http://dadosabertos.camara.leg.br/arquivos/orgaosDeputados/csv/orgaosDeputados-L{legislatura}.csv"

    # Utiliza a função genérica para baixar o CSV
    data = baixar_csv_generico("orgaosDeputados", url)  
    # Se o download foi bem-sucedido, processar o DataFrame
    if data is not None:
        # Extrair id.deputado do campo 'uriDeputado'
        data['id.deputado'] = data['uriDeputado'].apply(lambda x: re.search(r'\d+$', x).group() if pd.notnull(x) else None) 
        # Selecionar colunas relevantes e adicionar a legislatura
        data = data[['siglaOrgao', 'nomeOrgao', 'nomePublicacaoOrgao', 'nomeDeputado', 'id.deputado',
                     'siglaPartido', 'siglaUF', 'cargo', 'dataInicio', 'dataFim']].copy()
        data['legislat'] = legislatura  
        # Concatenar os dados baixados ao DataFrame principal
        dep_cargo = pd.concat([dep_cargo, data], ignore_index=True)
    
    # Aplicar filtro de período
    if not dep_cargo.empty:
        # Definir período de interesse
        data_inicio_periodo = f"{ano_ini_legis}-01-01"
        
        if mes:
            from calendar import monthrange
            ultimo_dia = monthrange(ano_atual, int(mes))[1]
            data_fim_periodo = f"{ano_atual}-{int(mes):02d}-{ultimo_dia}"
        else:
            data_fim_periodo = f"{ano_atual}-12-31"
        
        # Converter datas para datetime
        dep_cargo['dataInicio_temp'] = pd.to_datetime(dep_cargo['dataInicio'])
        dep_cargo['dataFim_temp'] = pd.to_datetime(dep_cargo['dataFim'])
        data_inicio_periodo_dt = pd.to_datetime(data_inicio_periodo)
        data_fim_periodo_dt = pd.to_datetime(data_fim_periodo)
        
        # Filtrar registros com sobreposição:
        # dataInicio <= data_fim_periodo AND (dataFim >= data_inicio_periodo OR dataFim is null)
        mask = (dep_cargo['dataInicio_temp'] <= data_fim_periodo_dt) & \
               ((dep_cargo['dataFim_temp'] >= data_inicio_periodo_dt) | (dep_cargo['dataFim_temp'].isna()))
        
        dep_cargo = dep_cargo[mask]
        dep_cargo = dep_cargo.drop(columns=['dataInicio_temp', 'dataFim_temp'])

    return dep_cargo

def pegar_orgaos(ano_ini_legis, ano_atual, pasta_temp="temp", mes=""):
    """
    Função que baixa e processa o arquivo de órgãos.
    
    Parâmetros:
    - ano_ini_legis: Ano inicial da legislatura.
    - ano_atual: Ano atual.
    - pasta_temp: Diretório onde o arquivo CSV será salvo (padrão: 'temp').
    - mes: Mês para filtrar até o final (formato: 01-12, padrão: vazio).
    
    Retorna:
    - DataFrame Pandas com o conteúdo dos órgãos.
    """
    
    url = "http://dadosabertos.camara.leg.br/arquivos/orgaos/csv/orgaos.csv"
    
    # Utiliza a função genérica para baixar o CSV
    orgaos = baixar_csv_generico("orgaos", url, pasta_temp)
    orgaos['codSituacao'] = orgaos['codSituacao'].fillna(0).astype(int)
    orgaos['codSituacao'] = orgaos['codSituacao'].astype('int64')
    
    # Aplicar filtro de período se os campos existirem
    if not orgaos.empty and 'dataInicio' in orgaos.columns and 'dataFim' in orgaos.columns:
        # Definir período de interesse
        data_inicio_periodo = f"{ano_ini_legis}-01-01"
        
        if mes:
            from calendar import monthrange
            ultimo_dia = monthrange(ano_atual, int(mes))[1]
            data_fim_periodo = f"{ano_atual}-{int(mes):02d}-{ultimo_dia}"
        else:
            data_fim_periodo = f"{ano_atual}-12-31"
        
        # Converter datas para datetime
        orgaos['dataInicio_temp'] = pd.to_datetime(orgaos['dataInicio'])
        orgaos['dataFim_temp'] = pd.to_datetime(orgaos['dataFim'])
        data_inicio_periodo_dt = pd.to_datetime(data_inicio_periodo)
        data_fim_periodo_dt = pd.to_datetime(data_fim_periodo)
        
        # Filtrar registros com sobreposição:
        # dataInicio <= data_fim_periodo AND (dataFim >= data_inicio_periodo OR dataFim is null)
        mask = (orgaos['dataInicio_temp'] <= data_fim_periodo_dt) & \
               ((orgaos['dataFim_temp'] >= data_inicio_periodo_dt) | (orgaos['dataFim_temp'].isna()))
        
        orgaos = orgaos[mask]
        orgaos = orgaos.drop(columns=['dataInicio_temp', 'dataFim_temp'])

    return orgaos

def criar_indice_legislativo(dep_eventos_df, dep_votacoes_df):
    """
    Função que combina dados de presenças em eventos e votações de deputados para criar o índice legislativo.
    
    Parâmetros:
    - dep_eventos_df: DataFrame contendo as presenças dos deputados nos eventos.
    - dep_votacoes_df: DataFrame contendo os votos dos deputados.

    Retorna:
    - DataFrame com o índice legislativo combinado.
    """

    # Processar o DataFrame de presenças em eventos
    dep_eventos_df['dataHoraInicio'] = pd.to_datetime(dep_eventos_df['dataHoraInicio'], errors='coerce').dt.to_period('M').dt.to_timestamp()

    ind_legis = dep_eventos_df.groupby(['idDeputado', 'dataHoraInicio']).size().reset_index(name='N')

    # Processar o DataFrame de votações
    dep_votacoes_df['dataHoraVoto'] = pd.to_datetime(dep_votacoes_df['dataHoraVoto'], errors='coerce').dt.to_period('M').dt.to_timestamp()

    ind_votacoes = dep_votacoes_df.groupby(['deputado_id', 'dataHoraVoto']).size().reset_index(name='N')
    ind_votacoes.rename(columns={'deputado_id': 'idDeputado', 'dataHoraVoto': 'dataHoraInicio'}, inplace=True)

    # Combinar os dois DataFrames (full join)
    ind_legis = pd.merge(ind_legis, ind_votacoes, on=['idDeputado', 'dataHoraInicio'], how='outer')

    # Criar a coluna 'legislat' com base nas faixas de datas
    base_date = datetime(1995, 2, 1)
    
    def define_legislatura(date):
        if pd.isnull(date):  # Verificar se a data é nula
            return None
        if base_date <= date < base_date + timedelta(days=4*365):
            return "50"
        elif base_date + timedelta(days=4*365) <= date < base_date + timedelta(days=8*365):
            return "51"
        elif base_date + timedelta(days=8*365) <= date < base_date + timedelta(days=12*365):
            return "52"
        elif base_date + timedelta(days=12*365) <= date < base_date + timedelta(days=16*365):
            return "53"
        elif base_date + timedelta(days=16*365) <= date < base_date + timedelta(days=20*365):
            return "54"
        elif base_date + timedelta(days=20*365) <= date < base_date + timedelta(days=24*365):
            return "55"
        elif base_date + timedelta(days=24*365) <= date < base_date + timedelta(days=28*365):
            return "56"
        elif base_date + timedelta(days=28*365) <= date < base_date + timedelta(days=32*365):
            return "57"
        else:
            return None

    # Aplicar a função para definir a legislatura
    ind_legis['legislat'] = ind_legis['dataHoraInicio'].apply(define_legislatura)

    # Remover duplicatas e contar meses
    ind_legis = ind_legis[['idDeputado', 'dataHoraInicio', 'legislat']].drop_duplicates()
    
    # Agrupar por 'idDeputado' e 'legislat' e contar meses
    ind_legis = ind_legis.groupby(['idDeputado', 'legislat']).size().reset_index(name='meses')
    ind_legis['legislat'] = ind_legis['legislat'].astype('int64')

    return ind_legis

def processar_proposicoes(proposicoes_df, temas_prop_df, autores_prop_df):
    """
    Processa as proposições legislativas, juntando com temas, autores e definindo a relevância.
    
    Parâmetros:
    - proposicoes_df: DataFrame contendo as proposições legislativas.
    - temas_prop_df: DataFrame contendo os temas das proposições legislativas.
    - autores_prop_df: DataFrame contendo os autores das proposições legislativas.
    Retorna:
    - DataFrame processado com as transformações aplicadas.
    """

    # 1. Processar 'proposicoes'
    proposicoes_df['dataApresentacao'] = pd.to_datetime(proposicoes_df['dataApresentacao'], errors='coerce')
    proposicoes_df['dataApresentacao'] = proposicoes_df['dataApresentacao'].dt.to_period('M').dt.to_timestamp()

    keywords_pattern = r"hora|dia|Dia|semana|Semana|Mês|ano|data|festa|calendario|calendário|titulo|título|prêmio|medalha|nome|galeria|ponte|ferrovia|estrada| aeroporto|rotatória|honorário"
    proposicoes_df['keywords'] = proposicoes_df['ementa'].apply(lambda x: 1 if re.search(keywords_pattern, str(x)) else 0)

    proposicoes_df['id.proposicao'] = proposicoes_df['id.proposicao'].astype(str)
    proposicoes_df = proposicoes_df.drop(columns=['ementa']).drop_duplicates()
    proposicoes_df.to_csv("./temp/sem-tema.csv", index=False)

    # 2. Processar 'temas.prop'
    temas_filtro = temas_prop_df[temas_prop_df['tema'] == "Homenagens e Datas Comemorativas"]
    temas_filtro.loc[:,'id.proposicao'] = temas_filtro['id.proposicao'].astype(str)
    temas_filtro.loc[:,'tema'] = 1
    temas_filtro = temas_filtro[['id.proposicao', 'tema']].drop_duplicates()

    proposicoes_df = proposicoes_df.merge(temas_filtro, on='id.proposicao', how='left')
    
    with pd.option_context('future.no_silent_downcasting', True):
        proposicoes_df['tema'] = proposicoes_df['tema'].fillna(0).astype(int)
    proposicoes_df.to_csv("./temp/com_tema.csv", index=False)

    # 3. Juntar com 'autores.prop'
    autores_prop_df = autores_prop_df.drop(columns=['uriProposicao', 'uriAutor', 'uriPartidoAutor'])
    autores_prop_df['protagonista'] = autores_prop_df.apply(lambda row: 1 if row['ordemAssinatura'] == 1 and row['proponente'] == 1 else 0, axis=1)
    autores_prop_df['id.proposicao'] = autores_prop_df['idProposicao'].astype(str)
    autores_prop_df = autores_prop_df.drop(columns=['idProposicao']).drop_duplicates()

    proposicoes_df = proposicoes_df.merge(autores_prop_df, on='id.proposicao', how='left')
    proposicoes_df = proposicoes_df.dropna(subset=['idDeputadoAutor'])
    proposicoes_df = proposicoes_df.astype({
        'idDeputadoAutor': int, 
        'codTipoAutor': int, 
        'ordemAssinatura': int, 
        'proponente': int, 
        'protagonista': int, 
        'ano.loop_y': int
    })    
    proposicoes_df['relevancia'] = proposicoes_df.apply(lambda row: 0 if row['keywords'] == 1 or row['tema'] == 1 else 1, axis=1)
    proposicoes_df = proposicoes_df.rename(columns={"ano.loop_y": "ano.loop.y", "ano.loop_x": "ano.loop.x"})
    proposicoes_df = proposicoes_df[proposicoes_df['idDeputadoAutor'].notna() & (proposicoes_df['idDeputadoAutor'] != "") & (proposicoes_df['idDeputadoAutor'] != 0)]    
    proposicoes_df.to_csv("./temp/pre_leg.csv", index=False)

    # 4. Definir a legislatura
    def definir_legislatura(dataHoraInicio):
        if pd.isnull(dataHoraInicio):
            return None
        legislaturas = [
            (datetime(1995, 2, 1), datetime(1999, 1, 31), "50"),
            (datetime(1999, 2, 1), datetime(2003, 1, 31), "51"),
            (datetime(2003, 2, 1), datetime(2007, 1, 31), "52"),
            (datetime(2007, 2, 1), datetime(2011, 1, 31), "53"),
            (datetime(2011, 2, 1), datetime(2015, 1, 31), "54"),
            (datetime(2015, 2, 1), datetime(2019, 1, 31), "55"),
            (datetime(2019, 2, 1), datetime(2023, 1, 31), "56"),
            (datetime(2023, 2, 1), datetime(2027, 1, 31), "57")
        ]
        for inicio, fim, legislatura in legislaturas:
            if inicio <= dataHoraInicio < fim:
                return legislatura
        return None

    proposicoes_df = proposicoes_df.rename(columns={"dataApresentacao": "dataHoraInicio"})
    proposicoes_df['legislat'] = proposicoes_df['dataHoraInicio'].apply(definir_legislatura)
    proposicoes_df['legislat'] = proposicoes_df['legislat'].astype('int64')
    return proposicoes_df


def calcula_var_1(proposicoes_df_filtradas, ind_legis_df):
    """
    Função que calcula a variável 'Var1' (proposições de protagonismo e relevância) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - proposicoes_df_filtradas: DataFrame contendo as proposições legislativas.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo de proposições de protagonismo e relevância.
    """

    # 1. Filtrar as proposições pelos tipos relevantes
    prov = proposicoes_df_filtradas[proposicoes_df_filtradas['siglaTipo'].isin(["PDL", "PEC", "PL", "PLP", "PLV"])]

    # 2. Agrupar por legislatura, idDeputadoAutor, protagonista, relevancia e contar as ocorrências
    prov = (prov.groupby(['legislat', 'idDeputadoAutor', 'protagonista', 'relevancia'])
            .size()
            .reset_index(name='N'))

    # 3. Filtrar as proposições onde protagonista == 1 e relevancia == 1
    prov = prov[(prov['protagonista'] == 1) & (prov['relevancia'] == 1)]

    # 4. Selecionar as colunas relevantes e renomear colunas
    prov = prov[['legislat', 'idDeputadoAutor', 'N']].rename(columns={'N': 'proj.relev.prot', 'idDeputadoAutor': 'idDeputado'})

    # 5. Fazer a junção com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df = ind_legis_df.round(0).astype(int)
    return ind_legis_df

def calcula_var_2(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var2' (proposições de protagonismo e baixa relevância) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - proposicoes_df: DataFrame contendo as proposições legislativas.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo de proposições de protagonismo e baixa relevância.
    """

    # 1. Filtrar as proposições pelos tipos relevantes
    prov = proposicoes_df[proposicoes_df['siglaTipo'].isin(["PDL", "PEC", "PL", "PLP", "PLV"])]

    # 2. Agrupar por legislatura, idDeputadoAutor, protagonista, relevancia e contar as ocorrências
    prov = (prov.groupby(['legislat', 'idDeputadoAutor', 'protagonista', 'relevancia'])
            .size()
            .reset_index(name='N'))

    # 3. Filtrar as proposições onde protagonista == 1 e relevancia == 0
    prov = prov[(prov['protagonista'] == 1) & (prov['relevancia'] == 0)]

    # 4. Selecionar as colunas relevantes e renomear colunas
    prov = prov[['legislat', 'idDeputadoAutor', 'N']].rename(columns={'N': 'proj.n.relev.prot', 'idDeputadoAutor': 'idDeputado'})
    prov['legislat'] = prov['legislat'].astype('int64')
    ind_legis_df['legislat'] = ind_legis_df['legislat'].astype('int64')

    # 5. Fazer a junção com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df = ind_legis_df.round(0).astype(int)
    return ind_legis_df


def calcula_var_3(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var3' (proposições sem protagonismo, mas relevantes) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - proposicoes_df: DataFrame contendo as proposições legislativas.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo de proposições sem protagonismo, mas relevantes.
    """

    # 1. Filtrar as proposições pelos tipos relevantes
    prov = proposicoes_df[proposicoes_df['siglaTipo'].isin(["PDL", "PEC", "PL", "PLP", "PLV"])]

    # 2. Agrupar por legislatura, idDeputadoAutor, protagonista, relevancia e contar as ocorrências
    prov = (prov.groupby(['legislat', 'idDeputadoAutor', 'protagonista', 'relevancia'])
            .size()
            .reset_index(name='N'))

    # 3. Filtrar as proposições onde protagonista == 0 e relevancia == 1
    prov = prov[(prov['protagonista'] == 0) & (prov['relevancia'] == 1)]

    # 4. Selecionar as colunas relevantes e renomear colunas
    prov = prov[['legislat', 'idDeputadoAutor', 'N']].rename(columns={'N': 'proj.relev.n.prot', 'idDeputadoAutor': 'idDeputado'})

    # 5. Fazer a junção com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df = ind_legis_df.round(0).astype(int)
    return ind_legis_df

def calcula_var_4(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var4' (proposições sem protagonismo e pouco relevantes) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - proposicoes_df: DataFrame contendo as proposições legislativas.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo de proposições sem protagonismo e pouco relevantes.
    """

    # 1. Filtrar as proposições pelos tipos relevantes
    prov = proposicoes_df[proposicoes_df['siglaTipo'].isin(["PDL", "PEC", "PL", "PLP", "PLV"])]

    # 2. Agrupar por legislatura, idDeputadoAutor, protagonista, relevancia e contar as ocorrências
    prov = (prov.groupby(['legislat', 'idDeputadoAutor', 'protagonista', 'relevancia'])
            .size()
            .reset_index(name='N'))

    # 3. Filtrar as proposições onde protagonista == 0 e relevancia == 0
    prov = prov[(prov['protagonista'] == 0) & (prov['relevancia'] == 0)]

    # 4. Selecionar as colunas relevantes e renomear colunas
    prov = prov[['legislat', 'idDeputadoAutor', 'N']].rename(columns={'N': 'proj.n.relev.n.prot', 'idDeputadoAutor': 'idDeputado'})

    # 5. Fazer a junção com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df = ind_legis_df.round(0).astype(int)
    return ind_legis_df


def calcula_var_5(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var5' (Votos em separado) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - proposicoes_df: DataFrame contendo as proposições legislativas.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo de votos em separado.
    """
    
    # 1. Filtrar as proposições com siglaTipo == "VTS"
    prov = proposicoes_df[proposicoes_df['siglaTipo'] == "VTS"]

    # 2. Agrupar por legislatura e idDeputadoAutor e contar as ocorrências
    prov = prov.groupby(['legislat', 'idDeputadoAutor']).size().reset_index(name='N')

    # 3. Renomear colunas
    prov = prov.rename(columns={'N': 'voto.separado', 'idDeputadoAutor': 'idDeputado'})
    prov['legislat'] = prov['legislat'].astype('int64')

    # 4. Fazer a junção com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df = ind_legis_df.round(0).astype(int)
    return ind_legis_df


def calcula_var_6(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var6' (Substitutivos) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - proposicoes_df: DataFrame contendo as proposições legislativas.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo de substitutivos.
    """
    
    # 1. Filtrar as proposições com siglaTipo == "SBT"
    prov = proposicoes_df[proposicoes_df['siglaTipo'] == "SBT"]

    # 2. Agrupar por legislatura e idDeputadoAutor e contar as ocorrências
    prov = prov.groupby(['legislat', 'idDeputadoAutor']).size().reset_index(name='N')

    # 3. Renomear colunas
    prov = prov.rename(columns={'N': 'substitutivos', 'idDeputadoAutor': 'idDeputado'})
    prov['legislat'] = prov['legislat'].astype('int64')

    # 4. Fazer a junção com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df = ind_legis_df.round(0).astype(int)
    return ind_legis_df


def calcula_var_7(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var7' (Relatorias) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - proposicoes_df: DataFrame contendo as proposições legislativas.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo de relatorias.
    """
    
    # 1. Filtrar as proposições com siglaTipo == "PRL"
    prov = proposicoes_df[proposicoes_df['siglaTipo'] == "PRL"]

    # 2. Agrupar por legislatura e idDeputadoAutor e contar as ocorrências
    prov = prov.groupby(['legislat', 'idDeputadoAutor']).size().reset_index(name='N')

    # 3. Renomear colunas
    prov = prov.rename(columns={'N': 'relatorias', 'idDeputadoAutor': 'idDeputado'})
    prov['legislat'] = prov['legislat'].astype('int64')
    prov.to_csv("./temp/prov_7.csv", index=False)

    # 4. Fazer a junção com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df = ind_legis_df.round(0).astype(int)
    return ind_legis_df


def calcula_var_8(eventos_df, dep_eventos_df, ind_legis_df):
    """
    Função que calcula a variável 'Var8' (Presença em votações em Plenário) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - eventos_df: DataFrame contendo os eventos legislativos.
    - dep_eventos_df: DataFrame contendo a presença dos deputados nos eventos.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo da presença em votações no plenário.
    """

    # 1. Converter 'dataHoraInicio' para formato de data
    eventos_df['dataHoraInicio'] = pd.to_datetime(eventos_df['dataHoraInicio']).dt.date

    # 2. Definir a legislatura com base nas faixas de datas
    base_date = datetime(1995, 2, 1).date()
    eventos_df['legislat'] = None
    
    def definir_legislatura(dataHoraInicio):
        if base_date <= dataHoraInicio < base_date + timedelta(days=4*365):
            return "50"
        elif base_date + timedelta(days=4*365) <= dataHoraInicio < base_date + timedelta(days=8*365):
            return "51"
        elif base_date + timedelta(days=8*365) <= dataHoraInicio < base_date + timedelta(days=12*365):
            return "52"
        elif base_date + timedelta(days=12*365) <= dataHoraInicio < base_date + timedelta(days=16*365):
            return "53"
        elif base_date + timedelta(days=16*365) <= dataHoraInicio < base_date + timedelta(days=20*365):
            return "54"
        elif base_date + timedelta(days=20*365) <= dataHoraInicio < base_date + timedelta(days=24*365):
            return "55"
        elif base_date + timedelta(days=24*365) <= dataHoraInicio < base_date + timedelta(days=28*365):
            return "56"
        elif base_date + timedelta(days=28*365) <= dataHoraInicio < base_date + timedelta(days=32*365):
            return "57"
        return None

    eventos_df['legislat'] = eventos_df['dataHoraInicio'].apply(definir_legislatura)

    # 3. Filtrar eventos do tipo "Sessão Deliberativa"
    eventos_filtrados = eventos_df[eventos_df['descricaoTipo'] == "Sessão Deliberativa"]

    # 4. Selecionar colunas relevantes e fazer a junção com 'dep_eventos_df'
    prov = eventos_filtrados[['id', 'legislat']].rename(columns={'id': 'idEvento'})
    prov = pd.merge(prov, dep_eventos_df, on='idEvento', how='left')

    # 5. Agrupar por legislatura e idDeputado e contar presenças
    prov = prov.groupby(['legislat', 'idDeputado']).size().reset_index(name='pres.plenario')
    prov = prov.round(0).astype(int)
    ind_legis_df = ind_legis_df.round(0).astype(int)

    # 6. Fazer a junção com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df['pres.plenario'] = ind_legis_df['pres.plenario'].astype(int)

    return ind_legis_df

def calcula_var_9(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var9' (Emendas em Plenário) e faz a junção com o DataFrame ind_legis.
    """
    prov = proposicoes_df[(proposicoes_df['siglaTipo'].isin(["EMP", "EMR"])) & (~proposicoes_df['descricaoTipo'].str.contains("MPV"))]
    prov = prov.groupby(['legislat', 'idDeputadoAutor']).size().reset_index(name='emendas.plenario')
    prov = prov.rename(columns={'idDeputadoAutor': 'idDeputado'})
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df = ind_legis_df.round(0).astype(int)

    return ind_legis_df


def calcula_var_10(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var10' (Emendas às MPs) e faz a junção com o DataFrame ind_legis.
    """
    prov = proposicoes_df[(proposicoes_df['siglaTipo'] == "EMP") & (proposicoes_df['descricaoTipo'].str.contains("MPV"))]
    prov = prov.groupby(['legislat', 'idDeputadoAutor']).size().reset_index(name='emendas.mp')
    prov = prov.rename(columns={'idDeputadoAutor': 'idDeputado'})
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    return ind_legis_df


def calcula_var_11(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var11' (Emendas às LOA) e faz a junção com o DataFrame ind_legis.
    """
    prov = proposicoes_df[proposicoes_df['siglaTipo'].isin(["EMO", "EML"])]
    prov = prov.groupby(['legislat', 'idDeputadoAutor']).size().reset_index(name='emendas.loa')
    prov = prov.rename(columns={'idDeputadoAutor': 'idDeputado'})
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    return ind_legis_df


def calcula_var_12(proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var12' (Projeto com status especial) e faz a junção com o DataFrame ind_legis.
    """
    prov = proposicoes_df[(proposicoes_df['siglaTipo'].isin(["PDL", "PEC", "PL", "PLP", "PLV"])) & (proposicoes_df['ultimoStatus_regime'].str.contains(r"^Especial$|202"))]
    prov = prov.groupby(['legislat', 'idDeputadoAutor']).size().reset_index(name='proj.especial')
    prov = prov.rename(columns={'idDeputadoAutor': 'idDeputado'})
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)

    ind_legis_df = ind_legis_df.round(0).astype(int)

    return ind_legis_df


def calcula_var_13(cargos_deputados_df, ind_legis_df):
    """
    Função que calcula a variável 'Var13' (Cargos ocupados) e faz a junção com o DataFrame ind_legis.

    Parâmetros:
    - cargos_deputados_df: DataFrame contendo os cargos dos deputados.
    - ind_legis_df: DataFrame contendo o índice legislativo.

    Retorna:
    - DataFrame combinado com a variável calculada.
    """
    # Filtrar e processar os cargos
    prov = cargos_deputados_df[~cargos_deputados_df['nomeOrgao'].isin(
        ["CONGRESSO NACIONAL", "Plenário", "Plenário Comissão Geral", "CÂMARA DOS DEPUTADOS", "Bancada de "]
    )].copy()

    prov['idDeputadoAutor'] = pd.to_numeric(prov['id.deputado'], errors='coerce')
    prov = prov.drop(columns=['id.deputado'])
    prov['legislat'] = prov['legislat'].astype(str)
    prov.to_csv("./temp/ind_legis_df_atualizado_13-prov-1.csv", index=False)

    # Peso 2 para presidente
    prov['cargos'] = np.where(prov['cargo'] == 'Presidente', 2, 1)
    prov.to_csv("./temp/ind_legis_df_atualizado_13-prov-2.csv", index=False)

    # Atualizar a pontuação com base nas comissões
    prov['nomePublicacaoOrgao'] = prov['nomePublicacaoOrgao'].astype(str)
    # Atualizar a pontuação com base nas comissões usando expressões regulares
    prov['nomePublicacaoOrgao'] = prov['nomePublicacaoOrgao'].str.  lower()    
    prov['cargos'] = prov.apply(
        lambda row: 2 if pd.notna(row['nomePublicacaoOrgao']) and 
        not re.search(r'^comissão especial|comissão especial|cpi', row['nomePublicacaoOrgao']) and
        re.search(r'^comissão | comissão', row['nomePublicacaoOrgao']) 
        else row['cargos'], axis=1
    )


    # Agrupar por deputado e legislatura, somando a pontuação
    prov = prov.groupby(['legislat', 'idDeputadoAutor']).agg({'cargos': 'sum'}).reset_index()
    prov = prov.rename(columns={'idDeputadoAutor': 'idDeputado'})
    prov['legislat'] = prov['legislat'].astype('int64')
    prov.to_csv("./temp/ind_legis_df_atualizado_13-prov-3.csv", index=False)
    # Fazer a junção com ind_legis_df
    ind_legis_df = ind_legis_df.merge(prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)

    ind_legis_df = ind_legis_df.round(0).astype(int)

    return ind_legis_df

def calcula_var_14(eventos_df, requer_eventos_df, proposicoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var14' (Requerimentos de Audiência Pública) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - eventos_df: DataFrame contendo os eventos legislativos.
    - requer_eventos_df: DataFrame contendo os requerimentos dos eventos.
    - proposicoes_df: DataFrame contendo as proposições legislativas.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo dos requerimentos de Audiência Pública.
    """

    # Filtrar eventos que são audiências públicas
    prov = eventos_df[eventos_df['descricaoTipo'].isin(["Audiência Pública", "Audiência Pública e Deliberação"])]
    prov = prov[['id', 'legislat']].rename(columns={'id': 'idEvento'})

    # Juntar com os requerimentos dos eventos
    prov = pd.merge(prov, requer_eventos_df, on="idEvento", how='left')
    prov = prov[prov['idRequerimento'].notnull()]

    # Filtrar proposições do tipo REQ
    proposicoes_req = proposicoes_df[proposicoes_df['siglaTipo'] == 'REQ']
    proposicoes_req = proposicoes_req[['id.proposicao', 'siglaTipo', 'legislat', 'idDeputadoAutor']].rename(
        columns={'id.proposicao': 'idRequerimento', 'legislat': 'legislat.req', 'idDeputadoAutor': 'idDeputado'}
    )

    # Juntar com os requerimentos
    prov = pd.merge(prov, proposicoes_req, on="idRequerimento", how='left')
    prov = prov[prov['idDeputado'].notnull()]

    # Agrupar por legislatura e deputado
    prov = prov.groupby(['idDeputado', 'legislat.req']).size().reset_index(name='aud.publ')
    prov = prov.rename(columns={'legislat.req': 'legislat'})
    prov['legislat'] = prov['legislat'].astype('int64')
    ind_legis_df['legislat'] = ind_legis_df['legislat'].astype('int64')

    # Juntar com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')

    return ind_legis_df

def calcula_var_15(eventos_df, dep_eventos_df, ind_legis_df):
    """
    Função que calcula a variável 'Var15' (Reuniões e eventos técnicos) e faz a junção com o DataFrame ind_legis.
    
    Parâmetros:
    - eventos_df: DataFrame contendo os eventos legislativos.
    - dep_eventos_df: DataFrame contendo a presença dos deputados nos eventos.
    - ind_legis_df: DataFrame contendo o índice legislativo.
    
    Retorna:
    - DataFrame combinado com o cálculo de reuniões e eventos técnicos.
    """

    # Filtrar eventos técnicos
    prov = eventos_df[eventos_df['descricaoTipo'].isin(["Evento Técnico", "Reunião Técnica", "Visita Técnica"])]
    prov = prov[['legislat', 'id']].rename(columns={'id': 'idEvento'})
    prov['event.tecnico'] = 1

    # Juntar com a presença dos deputados nos eventos
    prov = pd.merge(dep_eventos_df, prov, on='idEvento', how='left')

    # Filtrar os eventos técnicos
    prov = prov[prov['event.tecnico'] == 1]

    # Agrupar por legislatura e deputado
    prov = prov.groupby(['legislat', 'idDeputado']).size().reset_index(name='event.tecnico')

    # Juntar com o DataFrame ind_legis
    prov['legislat'] = prov['legislat'].astype('int64')
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')

    return ind_legis_df

def calcula_var_16_17_18(proposicoes_df, ind_legis_df):
    """
    Função que calcula as variáveis 'Var16' (Requerimentos de Fiscalização), 'Var17' (Convocação de Autoridades)
    e 'Var18' (Requerimentos de CPI) e faz a junção com o DataFrame ind_legis.

    Parâmetros:
    - proposicoes_df: DataFrame contendo as proposições legislativas.
    - ind_legis_df: DataFrame contendo o índice legislativo.

    Retorna:
    - DataFrame combinado com as variáveis calculadas.
    """
    # Criar colunas para identificar os diferentes tipos de requerimentos
    proposicoes_df['req.fisc'] = proposicoes_df['descricaoTipo'].apply(lambda x: 1 if re.search('Proposta de Fiscalização e Controle', str(x)) else 0)
    proposicoes_df['req.conv'] = proposicoes_df['descricaoTipo'].apply(lambda x: 1 if re.search('Ministro de Estado no Plenário|Ministro de Estado na Comissão|Convocação de Autoridade', str(x)) else 0)
    proposicoes_df['req.cpi'] = proposicoes_df['descricaoTipo'].apply(lambda x: 1 if re.search('Comissão Parlamentar de Inquérito|Convocação em CPI|Instituição de CPI', str(x)) else 0)

    # Selecionar as colunas relevantes e garantir que sejam únicas
    prov = proposicoes_df[['id.proposicao', 'legislat', 'idDeputadoAutor', 'req.fisc', 'req.conv', 'req.cpi']].drop_duplicates()

    # Agrupar por legislatura e deputado e somar os valores de cada variável
    prov = prov.groupby(['legislat', 'idDeputadoAutor']).agg({'req.fisc': 'sum', 'req.conv': 'sum', 'req.cpi': 'sum'}).reset_index()

    # Renomear a coluna idDeputadoAutor para idDeputado
    prov = prov.rename(columns={'idDeputadoAutor': 'idDeputado'})

    # Juntar com o DataFrame ind_legis
    ind_legis_df = pd.merge(ind_legis_df, prov, on=['legislat', 'idDeputado'], how='left')
    ind_legis_df = ind_legis_df.fillna(0)
    ind_legis_df = ind_legis_df.round(0).astype(int)

    return ind_legis_df

def calcula_var_19(votacoes_df, dep_votacoes_df, ind_legis_df):
    """
    Função que calcula a variável 'Var 19' (desvio e alinhamento em relação à maioria) 
    e faz a junção com o DataFrame ind_legis_df.
    
    Parâmetros:
    - votacoes_df: DataFrame contendo as votações.
    - dep_votacoes_df: DataFrame contendo os votos dos deputados.
    - ind_legis_df: DataFrame com o índice legislativo.
    
    Retorna:
    - DataFrame ind_legis_df atualizado com os valores de 'desv.voto' e 'align.voto'.
    """

    # Filtrar apenas votações no plenário
    prov_votacoes = votacoes_df[votacoes_df['siglaOrgao'] == 'PLEN'].copy()
    
    # Selecionar colunas relevantes
    prov_votacoes = prov_votacoes[['id', 'data', 'idEvento', 'aprovacao', 'votosSim', 'votosNao', 'votosOutros']].copy()
    prov_votacoes = prov_votacoes.astype(str)  # Converter tudo para string
    prov_votacoes = prov_votacoes.rename(columns={'id': 'idVotacao'})  # Renomear a coluna 'id' para 'idVotacao'
    # Juntar com os dados de votos dos deputados
    prov_votos = dep_votacoes_df[['idVotacao', 'deputado_idLegislatura', 'deputado_id', 'deputado_nome', 'deputado_siglaPartido', 'voto']].copy()

    # Fazer o merge dos dados de votos dos deputados com os dados de votações
    prov = prov_votos.merge(prov_votacoes, on='idVotacao', how='left')

    # Filtrar apenas votações com idEvento (votações no plenário)
    prov = prov[prov['idEvento'].notna()].copy()

    # Transformar votos em valores numéricos (1 para 'Sim', 0 para os outros)
    prov['voto'] = prov['voto'].apply(lambda x: 1 if x == 'Sim' else 0)

    # Agrupar por legislatura, votação e partido e calcular a média dos votos
    prov['deputado_idLegislatura'] = prov['deputado_idLegislatura'].astype(str)
    prov['voto.part'] = prov.groupby(['deputado_idLegislatura', 'idVotacao', 'deputado_siglaPartido'])['voto'].transform('mean')

    # Calcular o desvio do voto do deputado em relação à média do partido
    prov['desv.voto'] = abs(prov['voto'] - prov['voto.part'])

    # Agrupar por legislatura e deputado para calcular o desvio médio
    prov_desvio = prov.groupby(['deputado_idLegislatura', 'deputado_id']).agg({'desv.voto': 'mean'}).reset_index()

    # Renomear colunas e calcular o alinhamento
    prov_desvio = prov_desvio.rename(columns={'deputado_id': 'idDeputado', 'deputado_idLegislatura': 'legislat'})
    prov_desvio['align.voto'] = 1 - prov_desvio['desv.voto']

    # Garantir que a coluna 'legislat' seja string em ambos os DataFrames
    prov_desvio['legislat'] = prov_desvio['legislat'].astype(str)

    ind_legis_df['legislat'] = ind_legis_df['legislat'].astype(str)

    # Juntar o resultado com o DataFrame ind_legis_df
    ind_legis_df = ind_legis_df.merge(prov_desvio, on=['legislat', 'idDeputado'], how='left')
    return ind_legis_df

def normaliza_indice(ind_legis):
    """
    Função que processa o DataFrame ind_legis, substitui NAs, ajusta a pontuação por tempo de mandato,
    aplica transformações logarítmicas e normaliza os dados.
    
    Parâmetros:
    - ind_legis: DataFrame contendo os dados do índice legislativo.

    Retorna:
    - DataFrame processado com as transformações aplicadas.
    """

    # Substituímos NAs por 0
    ind_legis = ind_legis.fillna(0)

    # Corrigimos a pontuação por tempo de mandato
    colunas_ajuste_mandato = [
        "proj.relev.prot", "proj.n.relev.prot", "proj.relev.n.prot", 
        "proj.n.relev.n.prot", "voto.separado", "substitutivos", "relatorias", 
        "pres.plenario", "emendas.plenario", "emendas.mp", "emendas.loa", "cargos", 
        "proj.especial", "aud.publ", "event.tecnico", "req.fisc", "req.conv", "req.cpi"
    ]
    
    for coluna in colunas_ajuste_mandato:
        ind_legis[coluna] = ind_legis[coluna] / (ind_legis['meses'] / 12)

    # Aplicamos logarítimo às variáveis selecionadas
    colunas_log = [
        "proj.relev.prot", "proj.n.relev.prot", "proj.relev.n.prot", "proj.n.relev.n.prot", 
        "voto.separado", "substitutivos", "relatorias", "pres.plenario", "emendas.plenario", 
        "emendas.mp", "proj.especial", "emendas.loa", "cargos", "aud.publ", "event.tecnico", 
        "req.fisc", "req.conv", "req.cpi", "desv.voto", "align.voto"
    ]
    
    for coluna in colunas_log:
        ind_legis[coluna + ".log"] = np.log(ind_legis[coluna] + 0.00001)

    # Normalizamos as variáveis por legislatura
    colunas_a_normalizar = ind_legis.columns.difference(['idDeputado', 'legislat', 'meses'])

    # Normalização por legislatura
    ind_legis = ind_legis.groupby('legislat', group_keys=False).apply(
        lambda group: group.assign(**{col: (group[col] - group[col].min()) / (group[col].max() - group[col].min())
                                      for col in colunas_a_normalizar})
    )

    # Substituímos NAs por 0 após a normalização
    ind_legis = ind_legis.fillna(0)
    return ind_legis

def calcular_notas_dos_eixos(ind_legis_df):
    """
    Função que calcula as notas dos eixos e o score final com base nas variáveis presentes no DataFrame ind_legis.

    Parâmetros:
    - ind_legis_df: DataFrame contendo as informações legislativas.

    Retorna:
    - DataFrame processado com as notas dos eixos e score final.
    """
    
    # Calculando os eixos
    ind_legis_df['eixo.legis'] = ((ind_legis_df['proj.relev.prot'] * 2) + ind_legis_df['proj.n.relev.prot'] +
                                  ind_legis_df['proj.relev.n.prot'] + ind_legis_df['voto.separado'] +
                                  ind_legis_df['substitutivos'] + ind_legis_df['pres.plenario'] +
                                  ind_legis_df['emendas.plenario'] + ind_legis_df['emendas.mp'] +
                                  ind_legis_df['emendas.loa']) / 11

    ind_legis_df['eixo.mob'] = (ind_legis_df['cargos'] + ind_legis_df['proj.especial'] + 
                                ind_legis_df['aud.publ'] + ind_legis_df['event.tecnico']) / 4

    ind_legis_df['eixo.fisc'] = (ind_legis_df['req.fisc'] + ind_legis_df['req.conv'] + ind_legis_df['req.cpi']) / 3

    ind_legis_df['eixo.part'] = ind_legis_df['align.voto']

    # Calculando o score final
    ind_legis_df['score_final'] = (ind_legis_df['eixo.legis'] + ind_legis_df['eixo.mob'] + 
                                   ind_legis_df['eixo.fisc'] + ind_legis_df['eixo.part']) / 4

    # Calculando os eixos em log
    ind_legis_df['eixo.legis.log'] = ((ind_legis_df['proj.relev.prot.log'] * 2) + ind_legis_df['proj.n.relev.prot.log'] +
                                      ind_legis_df['proj.relev.n.prot.log'] + ind_legis_df['voto.separado.log'] +
                                      ind_legis_df['substitutivos.log'] + ind_legis_df['pres.plenario.log'] +
                                      ind_legis_df['emendas.plenario.log'] + ind_legis_df['emendas.mp.log'] +
                                      ind_legis_df['emendas.loa.log']) / 11

    ind_legis_df['eixo.mob.log'] = (ind_legis_df['cargos.log'] + ind_legis_df['proj.especial.log'] + 
                                    ind_legis_df['aud.publ.log'] + ind_legis_df['event.tecnico.log']) / 4

    ind_legis_df['eixo.fisc.log'] = (ind_legis_df['req.fisc.log'] + ind_legis_df['req.conv.log'] + 
                                     ind_legis_df['req.cpi.log']) / 3

    ind_legis_df['eixo.part.log'] = ind_legis_df['align.voto.log']

    # Calculando o score final em log (não usamos o eixo.part em log aqui)
    ind_legis_df['score_final.log'] = (ind_legis_df['eixo.legis.log'] + ind_legis_df['eixo.mob.log'] + 
                                       ind_legis_df['eixo.fisc.log'] + ind_legis_df['eixo.part']) / 4

    return ind_legis_df

def ordenar_variaveis(ind_legis_df):
    """
    Função que renomeia as variáveis do DataFrame ind_legis conforme a convenção de nomes estabelecida.

    Parâmetros:
    - ind_legis_df: DataFrame contendo as variáveis legislativas.

    Retorna:
    - DataFrame com as variáveis renomeadas.
    """
    ind_legis_df = ind_legis_df.rename(columns={
        # Variáveis originais
        'proj.relev.prot': 'v01.proj.relev.prot', 
        'proj.n.relev.prot': 'v02.proj.n.relev.prot',
        'proj.relev.n.prot': 'v03.proj.relev.n.prot', 
        'voto.separado': 'v04.voto.separado',
        'substitutivos': 'v05.substitutivos', 
        'pres.plenario': 'v06.pres.plenario',
        'emendas.plenario': 'v07.emendas.plenario', 
        'emendas.mp': 'v08.emendas.mp',
        'emendas.loa': 'v09.emendas.loa', 
        'proj.especial': 'v10.proj.especial',
        'cargos': 'v11.cargos', 
        'aud.publ': 'v12.aud.publ', 
        'event.tecnico': 'v13.event.tecnico',
        'req.fisc': 'v14.req.fisc', 
        'req.conv': 'v15.req.conv', 
        'req.cpi': 'v16.req.cpi',
        'align.voto': 'v17.align.voto',

        # Eixos
        'eixo.legis': 'v1.eixo.legis', 
        'eixo.mob': 'v2.eixo.mob',
        'eixo.fisc': 'v3.eixo.fisc', 
        'eixo.part': 'v4.eixo.part',

        # Variáveis em log
        'proj.relev.prot.log': 'v01.proj.relev.prot.log', 
        'proj.n.relev.prot.log': 'v02.proj.n.relev.prot.log',
        'proj.relev.n.prot.log': 'v03.proj.relev.n.prot.log', 
        'voto.separado.log': 'v04.voto.separado.log',
        'substitutivos.log': 'v05.substitutivos.log', 
        'pres.plenario.log': 'v06.pres.plenario.log',
        'emendas.plenario.log': 'v07.emendas.plenario.log', 
        'emendas.mp.log': 'v08.emendas.mp.log',
        'emendas.loa.log': 'v09.emendas.loa.log', 
        'proj.especial.log': 'v10.proj.especial.log',
        'cargos.log': 'v11.cargos.log', 
        'aud.publ.log': 'v12.aud.publ.log', 
        'event.tecnico.log': 'v13.event.tecnico.log',
        'req.fisc.log': 'v14.req.fisc.log', 
        'req.conv.log': 'v15.req.conv.log', 
        'req.cpi.log': 'v16.req.cpi.log',
        'align.voto.log': 'v17.align.voto.log',

        # Eixos em log
        'eixo.legis.log': 'v1.eixo.legis.log', 
        'eixo.mob.log': 'v2.eixo.mob.log',
        'eixo.fisc.log': 'v3.eixo.fisc.log', 
        'eixo.part.log': 'v4.eixo.part.log'
    })
    ind_legis_df['meses'] = ind_legis_df['meses'].astype(str)
    return ind_legis_df

def adicionar_info_pessoais(ind_legis_df, deputados_df):
    """
    Função que adiciona informações pessoais dos deputados ao DataFrame ind_legis.

    Parâmetros:
    - ind_legis_df: DataFrame contendo o índice legislativo.
    - deputados_df: DataFrame contendo informações pessoais dos deputados.

    Retorna:
    - DataFrame atualizado com as informações pessoais dos deputados.
    """
    # Converter idDeputado para string em ambos os DataFrames
    ind_legis_df['idDeputado'] = ind_legis_df['idDeputado'].astype(str)
    deputados_df['idDeputado'] = deputados_df['idDeputado'].astype(str)
    
    # Adiciona informações pessoais
    ind_legis_df = ind_legis_df.merge(deputados_df, on='idDeputado', how='left')

    return ind_legis_df

def selecionar_variaveis(ind_legis_df):
    """
    Função que organiza e seleciona as variáveis do DataFrame final.

    Parâmetros:
    - ind_legis_df: DataFrame contendo o índice legislativo.

    Retorna:
    - DataFrame final com as variáveis organizadas e selecionadas.
    """
    
    # Ordena e seleciona variáveis
    final_ind_legis_df = ind_legis_df.sort_values(by=['legislat', 'meses'], ascending=[False, False]).copy()

    final_ind_legis_df = final_ind_legis_df[[
        'legislat', 'idDeputado', 'nome', 'nomeCivil', 'cpf', 'meses', 'siglaSexo',
        'v01.proj.relev.prot.log', 'v02.proj.n.relev.prot.log', 'v03.proj.relev.n.prot.log',
        'v04.voto.separado.log', 'v05.substitutivos.log', 'v06.pres.plenario.log',
        'v07.emendas.plenario.log', 'v08.emendas.mp.log', 'v09.emendas.loa.log',
        'v10.proj.especial.log', 'v11.cargos.log', 'v12.aud.publ.log', 'v13.event.tecnico.log',
        'v14.req.fisc.log', 'v15.req.conv.log', 'v16.req.cpi.log', 'v17.align.voto.log',
        'v1.eixo.legis.log', 'v2.eixo.mob.log', 'v3.eixo.fisc.log', 'v4.eixo.part', 'score_final.log'
    ]]

    return final_ind_legis_df

def arredondar_valores(ind_legis_df):
    """
    Função que arredonda os valores numéricos e os escala para uma faixa de 0 a 10.

    Parâmetros:
    - final_ind_legis_df: DataFrame com as variáveis finais.

    Retorna:
    - DataFrame com os valores arredondados e escalados.
    """
    ind_legis_df = ind_legis_df.copy()

    # Multiplica por 10 e arredonda para duas casas decimais
    ind_legis_df = ind_legis_df.apply(lambda col: col.map(lambda x: round(x * 10, 2) if isinstance(x, (int, float)) else x))
    return ind_legis_df

def renomear_e_filtrar(final_ind_legis_df, legislatura_atual=57):
    """
    Função que renomeia colunas e filtra os dados para a legislatura atual.

    Parâmetros:
    - final_ind_legis_df: DataFrame contendo as variáveis finais.
    - legislatura_atual: Número da legislatura atual (padrão: 57).

    Retorna:
    - DataFrame filtrado para a legislatura atual e com as colunas renomeadas.
    """
    # Verifique o número correto de colunas para renomear
    num_colunas_para_renomear = 22  # Número correto de colunas para renomear
    
    # Verifique se o intervalo existe e se o número de colunas está correto
    if len(final_ind_legis_df.columns.values[7:7 + num_colunas_para_renomear]) == num_colunas_para_renomear:
        # Renomear colunas
        final_ind_legis_df.columns.values[7:7 + num_colunas_para_renomear] = [
            'variavel_1_score', 'variavel_2_score', 'variavel_3_score', 'variavel_4_score',
            'variavel_5_score', 'variavel_6_score', 'variavel_7_score', 'variavel_8_score',
            'variavel_9_score', 'variavel_10_score', 'variavel_11_score', 'variavel_12_score',
            'variavel_13_score', 'variavel_14_score', 'variavel_15_score', 'variavel_16_score',
            'variavel_17_score', 'eixo_1', 'eixo_2', 'eixo_3', 'eixo_4', 'score_final'
        ]
    else:
        print("Número de colunas no DataFrame não corresponde ao número de colunas a serem renomeadas")
        raise ValueError("Número de colunas no DataFrame não corresponde ao número de colunas a serem renomeadas")

    # Filtrar para a legislatura atual
    final_ind_legis_atual = final_ind_legis_df[final_ind_legis_df['legislat'] == str(legislatura_atual)]

    return final_ind_legis_atual

def atribuir_estrelas(final_ind_legis_57):
    # Cria uma cópia do DataFrame para evitar modificações no original
    final_ind_legis_57 = final_ind_legis_57.copy()
    
    # Calcula o rank inverso do 'Score final'
    final_ind_legis_57['rank'] = final_ind_legis_57['score_final'].rank(ascending=False)
    score_st = 50  # Define o limite de pontuação para as estrelas
    
    # Atribui estrelas com base na classificação (rank)
    final_ind_legis_57['estrelas'] = 1  # Inicia com 1 estrela
    final_ind_legis_57.loc[final_ind_legis_57['rank'] <= score_st, 'estrelas'] = 5
    final_ind_legis_57.loc[(final_ind_legis_57['rank'] > score_st) & (final_ind_legis_57['rank'] <= score_st * 2.5), 'estrelas'] = 4
    final_ind_legis_57.loc[(final_ind_legis_57['rank'] > score_st * 2.5) & (final_ind_legis_57['rank'] <= score_st * 4.5), 'estrelas'] = 3
    final_ind_legis_57.loc[(final_ind_legis_57['rank'] > score_st * 4.5) & (final_ind_legis_57['rank'] <= score_st * 7.5), 'estrelas'] = 2
    final_ind_legis_57.to_csv("./temp/final_ind_legis_57-rank.csv", index=False)

    # Remove colunas temporárias
    final_ind_legis_57.drop(columns=['rank'], inplace=True)
    final_ind_legis_57.loc[(final_ind_legis_57['score_final'] < 7.5) & (final_ind_legis_57['estrelas'] == 5), 'estrelas'] = 4
    
    return final_ind_legis_57

def pegar_sigla_uf_deputado(deputado_id):
    url = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{deputado_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Acessa o campo 'siglaUf' dentro de 'ultimoStatus'
            sigla_uf = data['dados']['ultimoStatus']['siglaUf']
            return sigla_uf
        else:
            print(f"Erro ao buscar dados: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Erro ao fazer a requisição: {str(e)}")
        return None

def verificar_valor_no_csv(deputado_id,caminho_csv,coluna_id='id.deputado', coluna_nome="siglaUf"):
    try:
        # Lê o arquivo CSV
        df = pd.read_csv(caminho_csv)

        # Verifica se a coluna existe
        if coluna_nome not in df.columns:
            print(f"A coluna '{coluna_nome}' não existe no arquivo CSV.")
            return None
        
        # Verifica se existe uma linha com o ID do deputado e se o valor na coluna especificada está preenchido
        deputado_id = str(deputado_id)  # Certifique-se de que o ID está no formato de string
        linha = df.loc[df[coluna_id].astype(str) == deputado_id]        
        if linha.empty:
            print(f"Não existe nenhuma linha com o deputado_id {deputado_id}.")
            return None

        valor = linha[coluna_nome].values[0]

        # Verifica se o valor da coluna não está vazio (NA ou None)
        if pd.isna(valor):
            print(f"O valor da coluna '{coluna_nome}' para o deputado_id {deputado_id} está vazio.")
            return None

        return valor
    
    except Exception as e:
        print(f"Erro ao processar o arquivo CSV: {str(e)}")
        return None

# Função para pegar a siglaUf da API
import requests

def get_info(deputado_id):
    print(f"Consultando na API: {deputado_id}")
    url = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{deputado_id}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        try:
            dados = data['dados']
            ultimo_status = dados['ultimoStatus']
            
            # Captura dos campos requisitados
            sigla_uf = ultimo_status.get('siglaUf')
            sigla_partido = ultimo_status.get('siglaPartido')
            uri = dados.get('uri')
            url_foto = ultimo_status.get('urlFoto')
            situacao = ultimo_status.get('situacao')
            documento = dados.get('cpf')
            email = ultimo_status['gabinete'].get('email')
            data_nascimento = dados.get('dataNascimento')
            
            return {
                "sigla_uf": sigla_uf,
                "sigla_partido": sigla_partido,
                "uri": uri,
                "url_foto": url_foto,
                "situacao": situacao,
                "documento": documento,
                "email": email,
                "data_nascimento": data_nascimento
            }
        except KeyError as e:
            print(f"Erro: Campo {e} não encontrado para o deputado {deputado_id}")
            return None
    else:
        print(f"Erro ao consultar API para deputado {deputado_id}: {response.status_code}")
        return None

def get_deputado_sigla_partido(deputado_id):
    print(f"consultando na API: {deputado_id}")
    url = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{deputado_id}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        try:
            sigla_partido = data['dados']['ultimoStatus']['siglaPartido']
            return sigla_partido
        except KeyError:
            print(f"Erro: 'siglaPartido' não encontrado para o deputado {deputado_id}")
            return None
    else:
        print(f"Erro ao consultar API para deputado {deputado_id}: {response.status_code}")
        return None


# Função que itera pelo DataFrame e preenche a coluna 'siglaUf'
def pegar_info_deputados(df):
    # Verifica se a coluna 'siglaUf' existe, se não, cria ela
    if 'siglaUf' not in df.columns:
        df['siglaUf'] = None
    if 'siglaPartido' not in df.columns:
        df['siglaPartido'] = None
    if 'uri' not in df.columns:
        df['uri'] = None
    if 'urlFoto' not in df.columns:
        df['urlFoto'] = None
    if 'situacao' not in df.columns:
        df['situacao'] = None
    if 'documento' not in df.columns:
        df['documento'] = None
    if 'email' not in df.columns:
        df['email'] = None
    if 'dataNascimento' not in df.columns:
        df['dataNascimento'] = None
    for index, row in df.iterrows():
        deputado_id = row['idDeputado']
        info = get_info(deputado_id)
        df.at[index, 'siglaPartido'] = info.get('sigla_partido')
        df.at[index, 'siglaUf'] = info.get('sigla_uf')
        df.at[index, 'uri'] = info.get('uri')
        df.at[index, 'urlFoto'] = info.get('url_foto')
        df.at[index, 'situacao'] = info.get('situacao')
        df.at[index, 'documento'] = info.get('documento')
        df.at[index, 'email'] = info.get('email')
        df.at[index, 'dataNascimento'] = info.get('data_nascimento')
    return df


def main():
    """Função principal do script"""
    global nocache
    
    # Configurar argumentos da linha de comando
    ano_atual_default = datetime.now().year
    parser = argparse.ArgumentParser(description='Gerar CSVs de dados da Câmara dos Deputados')
    parser.add_argument('--ano-atual', type=int, default=ano_atual_default, help=f'Ano atual para coleta de dados (padrão: {ano_atual_default})')
    parser.add_argument('--ano-ini-legis', type=int, default=2023, help='Ano inicial da legislatura (padrão: 2023)')
    parser.add_argument('--mes', type=str, default="", help='Mês para filtrar dados (formato: 01-12, padrão: sem filtro)')
    parser.add_argument('--nocache', action='store_true', help='Forçar download de todos os arquivos, ignorando cache')
    
    args = parser.parse_args()
    ano_atual = args.ano_atual
    ano_ini_legis = args.ano_ini_legis
    mes = args.mes
    nocache = args.nocache
    
    print(f"Executando com ano_atual={ano_atual}, ano_ini_legis={ano_ini_legis}, mes={mes if mes else 'todos'}, nocache={nocache}")
    
    # deputados
    deputados_df = pegar_deputados()
    deputados_df.to_csv("./temp/deputados_df.csv", index=False)
    
    # proposições
    proposicoes_df = pegar_proposicoes(ano_atual, ano_ini_legis, mes=mes)
    proposicoes_df.to_csv("./temp/proposicoes_df.csv", index=False)
    # def pegar_proposicoes(ano_atual, ano_ini_legis, pasta_temp="temp", mes=""):
    
    # # autores
    autores_prop_df = pegar_autores_proposicoes(ano_atual, ano_ini_legis)
    autores_prop_df.to_csv("./temp/autores_prop_df.csv", index=False)

    # # temas
    temas_prop_df = pegar_temas_proposicoes(ano_atual, ano_ini_legis)
    temas_prop_df.to_csv("./temp/temas_prop_df.csv", index=False)

    # # eventos
    eventos_df = pegar_eventos(ano_atual, ano_ini_legis, mes=mes)
    eventos_df.to_csv("./temp/eventos_df.csv", index=False)

    # presença em eventos
    dep_eventos_df = pegar_presenca_eventos_deputados(ano_atual, ano_ini_legis, mes=mes)
    dep_eventos_df.to_csv("./temp/dep_eventos_df.csv", index=False)

    # requerimentos dos eventos (filtrado por eventos válidos)
    requer_eventos_df = pegar_requerimentos_eventos(ano_atual, ano_ini_legis, eventos_df=eventos_df)
    requer_eventos_df.to_csv("./temp/requer_eventos_df.csv", index=False)

    # votações
    votacoes_df = pegar_votacoes(ano_atual, ano_ini_legis, mes=mes)
    votacoes_df.to_csv("./temp/votacoes_df.csv", index=False)

    # votações por deputado
    dep_votacoes_df = pegar_votacoes_deputados(ano_atual, ano_ini_legis, mes=mes)
    dep_votacoes_df.to_csv("./temp/dep_votacoes_df.csv", index=False)

    # votações e orientações dos líderes
    part_votacoes_df = pegar_votacoes_orientacoes(ano_atual, ano_ini_legis)
    part_votacoes_df.to_csv("./temp/part_votacoes_df.csv", index=False)

    # cargos dos deputados
    cargos_deputados_df = pegar_cargos_deputados(57, ano_ini_legis, ano_atual, mes=mes)
    cargos_deputados_df.to_csv("./temp/cargos_deputados_df.csv", index=False)

    # órgãos
    orgaos_df = pegar_orgaos(ano_ini_legis, ano_atual, mes=mes)
    orgaos_df.to_csv("./temp/orgaos_df.csv", index=False)


    # índice legislativo
    ind_legis_df = criar_indice_legislativo(dep_eventos_df, dep_votacoes_df)
    ind_legis_df.to_csv("./temp/ind_legis_df.csv", index=False)

    # proposições filtradas
    proposicoes_df_filtrado = processar_proposicoes(proposicoes_df, temas_prop_df, autores_prop_df)
    proposicoes_df_filtrado.to_csv("./temp/proposicoes_df_filtrado.csv", index=False)

    # índice legislativo com Var1
    ind_legis_df_atualizado_1 = calcula_var_1(proposicoes_df_filtrado, ind_legis_df)
    ind_legis_df_atualizado_1.to_csv("./temp/ind_legis_df_atualizado_1.csv", index=False)

    # índice legislativo com Var2
    ind_legis_df_atualizado_2 = calcula_var_2(proposicoes_df_filtrado, ind_legis_df_atualizado_1)
    ind_legis_df_atualizado_2.to_csv("./temp/ind_legis_df_atualizado_2.csv", index=False)

    # calcula_var_3
    ind_legis_df_atualizado_3 = calcula_var_3(proposicoes_df_filtrado, ind_legis_df_atualizado_2)
    ind_legis_df_atualizado_3.to_csv("./temp/ind_legis_df_atualizado_3.csv")


    # calcula_var_4
    ind_legis_df_atualizado_4 = calcula_var_4(proposicoes_df_filtrado, ind_legis_df_atualizado_3)
    ind_legis_df_atualizado_4.to_csv("./temp/ind_legis_df_atualizado_4.csv", index=False)


    # Exemplo de uso da Var5 (Votos em separado)
    ind_legis_df_atualizado_5 = calcula_var_5(proposicoes_df_filtrado, ind_legis_df_atualizado_4)
    ind_legis_df_atualizado_5.to_csv("./temp/ind_legis_df_atualizado_5.csv", index=False)

    # Exemplo de uso da Var6 (Substitutivos)
    ind_legis_df_atualizado_6 = calcula_var_6(proposicoes_df_filtrado, ind_legis_df_atualizado_5)
    ind_legis_df_atualizado_6.to_csv("./temp/ind_legis_df_atualizado_6.csv", index=False)

    # Exemplo de uso da Var7 (Relatorias)
    ind_legis_df_atualizado_7 = calcula_var_7(proposicoes_df_filtrado, ind_legis_df_atualizado_6)
    ind_legis_df_atualizado_7.to_csv("./temp/ind_legis_df_atualizado_7.csv", index=False)

    # Exemplo de uso da Var8 (Presença em votações em Plenário)
    ind_legis_df_atualizado_8 = calcula_var_8(eventos_df, dep_eventos_df, ind_legis_df_atualizado_7)
    ind_legis_df_atualizado_8.to_csv("./temp/ind_legis_df_atualizado_8.csv", index=False)

    # Exemplo de uso da Var9 (Emendas em plenário)
    ind_legis_df_atualizado_9 = calcula_var_9(proposicoes_df_filtrado, ind_legis_df_atualizado_8)
    ind_legis_df_atualizado_9.to_csv("./temp/ind_legis_df_atualizado_9.csv", index=False)

    # Exemplo de uso da Var10 (Emendas às MPs)
    ind_legis_df_atualizado_10 = calcula_var_10(proposicoes_df_filtrado, ind_legis_df_atualizado_9)
    ind_legis_df_atualizado_10.to_csv("./temp/ind_legis_df_atualizado_10.csv", index=False)

    # Exemplo de uso da Var11 (Emendas às LOA)
    ind_legis_df_atualizado_11 = calcula_var_11(proposicoes_df_filtrado, ind_legis_df_atualizado_10)
    ind_legis_df_atualizado_11.to_csv("./temp/ind_legis_df_atualizado_11.csv", index=False)

    # Exemplo de uso da Var12 (Projetos com status especial)
    ind_legis_df_atualizado_12 = calcula_var_12(proposicoes_df_filtrado, ind_legis_df_atualizado_11)
    ind_legis_df_atualizado_12.to_csv("./temp/ind_legis_df_atualizado_12.csv", index=False)

    # Exemplo de uso da Var13 (Cargos ocupados)
    ind_legis_df_atualizado_13 = calcula_var_13(cargos_deputados_df, ind_legis_df_atualizado_12)
    ind_legis_df_atualizado_13.to_csv("./temp/ind_legis_df_atualizado_13.csv", index=False)

    # Exemplo de uso da Var14 (Requerimentos de Audiência Pública)
    ind_legis_df_atualizado_14 = calcula_var_14(eventos_df, requer_eventos_df, proposicoes_df_filtrado, ind_legis_df_atualizado_13)
    ind_legis_df_atualizado_14.to_csv("./temp/ind_legis_df_atualizado_14.csv", index=False)

    # Exemplo de uso da Var15 (Reuniões e eventos técnicos)
    ind_legis_df_atualizado_15 = calcula_var_15(eventos_df, dep_eventos_df, ind_legis_df_atualizado_14)
    ind_legis_df_atualizado_15.to_csv("./temp/ind_legis_df_atualizado_15.csv", index=False)

    ind_legis_df_atualizado_16_18 = calcula_var_16_17_18(proposicoes_df_filtrado, ind_legis_df_atualizado_15)
    ind_legis_df_atualizado_16_18.to_csv("./temp/ind_legis_df_atualizado_16_18.csv", index=False)

    # # # Exemplo de uso para calcular a variável Var19
    ind_legis_df_atualizado_19 = calcula_var_19(votacoes_df, dep_votacoes_df, ind_legis_df_atualizado_16_18)
    ind_legis_df_atualizado_19.to_csv("./temp/ind_legis_df_atualizado_19.csv", index=False)

    # normaliza_indice
    ind_legis_df_normalizado = normaliza_indice(ind_legis_df_atualizado_19)
    ind_legis_df_normalizado.to_csv("./temp/ind_legis_df_normalizado.csv", index=False)

    # calcular_notas_dos_eixos
    ind_legis_df_eixos = calcular_notas_dos_eixos(ind_legis_df_normalizado)
    ind_legis_df_eixos.to_csv("./temp/ind_legis_df_eixos.csv", index=False)

    # ordenar_variaveis
    ind_legis_df_ordenado = ordenar_variaveis(ind_legis_df_eixos)
    ind_legis_df_ordenado.to_csv("./temp/ind_legis_df_ordenado.csv", index=False)


    # adicionar_info_pessoais
    ind_legis_df_info_pessoal = adicionar_info_pessoais(ind_legis_df_ordenado, deputados_df)
    ind_legis_df_info_pessoal.to_csv("./temp/ind_legis_df_info_pessoal.csv", index=False)


    # selecionar_variaveis
    ind_legis_df_selecionado = selecionar_variaveis(ind_legis_df_info_pessoal)
    ind_legis_df_selecionado.to_csv("./temp/ind_legis_df_selecionado.csv", index=False)


    # arredondar_valores
    ind_legis_df_arredondado = arredondar_valores(ind_legis_df_selecionado)
    ind_legis_df_arredondado.to_csv("./temp/ind_legis_df_arredondado.csv", index=False)

    # renomear_e_filtrar
    final_ind_legis_57 = renomear_e_filtrar(ind_legis_df_arredondado, legislatura_atual=57)
    final_ind_legis_57.to_csv("./temp/final_ind_legis_57-filtrado.csv", index=False)

    final_ind_legis_57 = atribuir_estrelas(final_ind_legis_57)
    final_ind_legis_57.to_csv("./temp/final_ind_legis_57-estrelas.csv", index=False)

    # Garantir as UFs preenchidas
    final_ind_legis_57 = pegar_info_deputados(final_ind_legis_57)

    # salvar csv
    final_ind_legis_57.to_csv("./final_ind_legis_57.csv", sep=';', decimal=',', index=False)


if __name__ == "__main__":
    main()

