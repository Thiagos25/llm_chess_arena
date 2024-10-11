import chess
import chess.pgn
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from dotenv import load_dotenv, find_dotenv
from langchain.memory import ConversationBufferMemory

from langchain_openai import ChatOpenAI
import re
import os

# Carregar variáveis de ambiente
_ = load_dotenv(find_dotenv())

# Configurações dos jogadores
white_player = "Humano"  # Jogador humano jogando de brancas
black_player = "GPT-4"  # Máquina jogando de pretas
llm1 = ChatOpenAI(temperature=0.1, model='gpt-3.5-turbo')

# Função para desenhar o tabuleiro no terminal
def draw_board(board):
    print(board)  # Exibe o tabuleiro em formato ASCII

# Definindo o sistema de memória (não necessariamente usado no código atual)
memory = ConversationBufferMemory(memory_key="chat_history", input_key="input")

# Definindo os prompts para a LLM de pretas
system_template = """
    You are a Chess Grandmaster.
    We are currently playing chess. 
    You are playing with the {color} pieces.
    
    I will give you the last move, the history of the game so far, the
    actual board position and you must analyze the position and find the best move.

    # OUTPUT
    Do not use any special characters. 
    Give your response in the following order:

    1. Your move, using the following format: My move: "Move" (in the SAN notation, in english).
    2. The explanation, in Portuguese, of why you chose the move, in no more than 3 sentences.
    """

# Criando o template de prompt para o GPT-4
prompt_template1 = ChatPromptTemplate.from_messages([
    ("system", system_template.format(color="black")), 
    ("human", "{input}")
])

# Criando o LLMChain para as pretas
chain1 = prompt_template1 | llm1

# Função para obter o movimento do LLM (GPT-4)
def get_move_llm(llm_chain, last_move, board, node, color, alert_msg=False):
    global move_raw
    game_temp = chess.pgn.Game.from_board(board)
    str_board = str(board)
    history = str(game_temp)
    pattern = r".*?(?=1\. e4)"
    history = re.sub(pattern, "", history, flags=re.DOTALL)

    legal_moves = list(board.legal_moves)
    san_moves = [board.san(move).strip() for move in legal_moves]  # Removendo espaços desnecessários

    template_input = """ 
        Here's the history of the game:
        {history}

        The last move played was: 
        {last_move}   

        Find the best move.
    """
    
    if not alert_msg:
        user_input = template_input.format(
                                    last_move=last_move,
                                    history=history)
    else:  
        user_input = """
        Here's the actual board position: 
        {str_board}

        Here is the game history so far:
        {history}

        The last move played was: 
        {last_move}   

        Here's a list of valid moves in this position:
        {san_moves}

        You must choose one of the valid moves.
        """.format(san_moves=san_moves, 
                history=history, 
                str_board=str_board,
                last_move=last_move,
                )
    
    response = llm_chain.invoke({"input": user_input})
    move_raw = response.content.strip()

    # Usar regex para capturar apenas o movimento SAN
    move_match = re.search(r"My move:\s*(\S+)", move_raw)
    
    if move_match:
        move_raw = move_match.group(1).strip()  # Extraindo o movimento em SAN
    else:
        print(f"Erro ao capturar o movimento do LLM. Resposta: {move_raw}")
        return None, node
    
    try:
        if move_raw not in san_moves:
            print(f"Movimento inválido gerado por {color}: {move_raw}")
            return None, node

        print(f"Movimento escolhido: {move_raw}")
        move_board = board.push_san(move_raw)
        next_node = node.add_variation(move_board)
        return move_raw, next_node

    except ValueError:
        print(f"Erro ao processar o movimento gerado por {color}: {move_raw}")
        return None, node

# Função para obter o movimento do jogador humano
def get_move_human(board, node):
    legal_moves = list(board.legal_moves)
    san_moves = [board.san(move).strip() for move in legal_moves]  # Removendo espaços desnecessários

    # Solicitar jogada do jogador humano
    move_raw = input(f"Jogador Humano (Brancas), insira seu movimento em SAN (movimentos válidos: {san_moves}): ").strip()

    try:
        if move_raw in san_moves:
            move_board = board.push_san(move_raw)
            next_node = node.add_variation(move_board)
            return move_raw, next_node
        else:
            print("Movimento inválido, tente novamente.")
            return None, node
    except ValueError:
        print("Erro ao processar o movimento, tente novamente.")
        return None, node

# Inicializando o tabuleiro de xadrez
folder_name = f"{white_player} vs {black_player}"
if not os.path.exists(folder_name):
    os.makedirs(folder_name)
game_num = max([int(i.split("_")[0]) for i in ["0_0"] + os.listdir(folder_name)]) + 1

board = chess.Board()
game = chess.pgn.Game()
node = game

# Loop de jogo
while not board.is_game_over():    
    # Desenha o tabuleiro antes da jogada
    draw_board(board)
    
    # Jogada do Humano (Brancas)
    move1 = None
    c = 0
    while move1 is None:
        move1, node = get_move_human(board, node)
        c += 1
    print("\n========================")
    if board.is_game_over():
        break
    
    # Desenha o tabuleiro após a jogada do Humano
    draw_board(board)
    
    # Jogada do GPT-4 (Pretas)
    move2 = None
    c = 0
    while move2 is None:
        alert = False if c == 0 else True
        move2, node = get_move_llm(chain1, move1, board, node, "black", alert)
        c += 1
    print("\n========================")

    # Desenha o tabuleiro após a jogada do GPT-4
    draw_board(board)

    if board.is_game_over():
        break

# Salvando o jogo
game.headers["White"] = white_player
game.headers["Black"] = black_player

if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
    result = "1/2-1/2"
elif board.result() == "1-0":
    result = "1-0"
else:
    result = "0-1"
game.headers["Result"] = result

with open(f"{folder_name}/{game_num}_game.pgn", "w") as f:
    f.write(str(game))

print("Game Over")
print(board.result())