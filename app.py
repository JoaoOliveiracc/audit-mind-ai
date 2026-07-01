import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

load_dotenv()


llm = ChatOllama(
    model="gemma3:12b",
    temperature=0,
    base_url="http://192.168.1.50/v1",
    headers={
        "x-api-key": "sk-indexacao-y1ALudHbiGLC2y2s5tMZiT2QE-4FdnlHNOaBpFVsAcM",
        "Content-Type": "application/json"
    }
)

# Template do Sistema
system_template = """
Atue como um Auditor de Segurança Sênior. 
Seu foco é analisar o código fornecido sob a ótica de Zero Trust e OWASP.

PROJETO: {nome_projeto}
DADOS DE ENTRADA: {dados_entrada}

Analise vulnerabilidades, configurações de segurança e boas práticas.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])

# Gerenciamento de Histórico
store = {}

def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

chain = prompt | llm

executor = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
    history_factory_config=[
        {
            "id": "session_id",
            "annotation": "ID da sessão de auditoria",
        }
    ]
)

# Função para ler arquivos locais
def carregar_contexto_projeto(diretorio):
    contexto = []
    # Extensões permitidas para análise
    extensoes = ('.py', '.js', '.ts', '.go', '.yml', '.yaml', 'Dockerfile', '.env.example')
    
    for root, dirs, files in os.walk(diretorio):
        # Ignora pastas de ambiente virtual e git para não estourar o limite de tokens
        if any(ignored in root for ignored in ['venv', '.venv', 'node_modules', '.git']):
            continue
            
        for file in files:
            if file.endswith(extensoes):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        conteudo = f.read()
                        contexto.append(f"--- ARQUIVO: {path} ---\n{conteudo}\n")
                except Exception as e:
                    print(f"Erro ao ler {path}: {e}")
                    
    return "\n".join(contexto)

def iniciar_auditoria():
    print("\n--- Security Audit Agent ---")
    caminho = input("Caminho do projeto para auditoria: ").strip()
    
    if not os.path.exists(caminho):
        print("Erro: O caminho especificado não existe.")
        return

    nome = input("Nome do projeto: ").strip()
    
    print("⏳ Analisando arquivos e gerando relatório (isso pode levar alguns segundos)...")
    contexto_codigo = carregar_contexto_projeto(caminho)
    
    if not contexto_codigo:
        print("Aviso: Nenhum arquivo compatível encontrado no diretório.")
        return

    # Primeira chamada com o contexto
    try:
        resposta = executor.invoke(
            {
                "input": "Inicie a auditoria detalhada com base nos arquivos fornecidos.", 
                "nome_projeto": nome, 
                "dados_entrada": contexto_codigo
            },
            config={"configurable": {"session_id": "audit_01"}}
        )
        
        print("\n" + "="*50)
        print("RELATÓRIO INICIAL:")
        print("="*50)
        print(resposta.content)

        # Loop de chat
        while True:
            duvida = input("\nVocê (ou 'sair'): ")
            if duvida.lower() in ['sair', 'exit', 'quit']:
                break
            
            res = executor.invoke(
                {
                    "input": duvida, 
                    "nome_projeto": nome, 
                    "dados_entrada": "O contexto já foi enviado anteriormente."
                },
                config={"configurable": {"session_id": "audit_01"}}
            )
            print("\nAI:", res.content)
            
    except Exception as e:
        print(f"\nErro durante a execução: {e}")

if __name__ == "__main__":
    iniciar_auditoria()