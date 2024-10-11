import chess
import chess.pgn
import pygame
import os
import re
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from dotenv import load_dotenv, find_dotenv
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI

# Carregar variáveis de ambiente
_ = load_dotenv(find_dotenv())

# Inicializar o pygame
pygame.init()

# Definir dimensões do tabuleiro
WIDTH, HEIGHT = 800, 800
SQUARE_SIZE = WIDTH // 8

# Cores do tabuleiro
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Configurações dos jogadores
white_player = "Humano"
black_player = "GPT-4"
llm1 = ChatOpenAI(temperature=0.1, model='gpt-3.5-turbo')

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

# Carregar imagens das peças com os novos nomes
def load_images():
    pieces = {
        'r': 'black_rook.png', 'n': 'black_knight.png', 'b': 'black_bishop.png', 
        'q': 'black_queen.png', 'k': 'black_king.png', 'p': 'black_pawn.png',
        'R': 'white_rook.png', 'N': 'white_knight.png', 'B': 'white_bishop.png', 
        'Q': 'white_queen.png', 'K': 'white_king.png', 'P': 'white_pawn.png'
    }
    images = {}
    for piece, filename in pieces.items():
        images[piece] = pygame.transform.scale(pygame.image.load(f'images/{filename}'), (SQUARE_SIZE, SQUARE_SIZE))
    return images

# Função para desenhar o tabuleiro
def draw_board(screen):
    colors = [pygame.Color("white"), pygame.Color("gray")]
    for row in range(8):
        for col in range(8):
            color = colors[(row + col) % 2]
            pygame.draw.rect(screen, color, pygame.Rect(col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))

# Função para desenhar as peças no tabuleiro
def draw_pieces(screen, board, images):
    for row in range(8):
        for col in range(8):
            piece = board.piece_at(row * 8 + col)
            if piece:
                piece_image = images[piece.symbol()]
                screen.blit(piece_image, pygame.Rect(col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))

# Função para obter o movimento do LLM (GPT-4)
def get_move_llm(llm_chain, last_move, board, node, color, alert_msg=False):
    global move_raw
    game_temp = chess.pgn.Game.from_board(board)
    str_board = str(board)
    history = str(game_temp)
    pattern = r".*?(?=1\. e4)"
    history = re.sub(pattern, "", history, flags=re.DOTALL)

    legal_moves = list(board.legal_moves)
    san_moves = [board.san(move).strip() for move in legal_moves]

    template_input = """ 
        Here's the history of the game:
        {history}

        The last move played was: 
        {last_move}   

        Find the best move.
    """
    
    if not alert_msg:
        user_input = template_input.format(last_move=last_move, history=history)
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
        """.format(san_moves=san_moves, history=history, str_board=str_board, last_move=last_move)
    
    response = llm_chain.invoke({"input": user_input})
    move_raw = response.content.strip()

    move_match = re.search(r"My move:\s*(\S+)", move_raw)
    
    if move_match:
        move_raw = move_match.group(1).strip()
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
    san_moves = [board.san(move).strip() for move in legal_moves]

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

# Inicializa janela do pygame
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Jogo de Xadrez: Humano vs GPT-4")

# Carregar imagens
images = load_images()

# Loop do jogo
running = True
while running and not board.is_game_over():
    draw_board(screen)
    draw_pieces(screen, board, images)
    pygame.display.flip()
    
    # Verifica eventos de saída
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    # Jogada do Humano (Brancas)
    move1 = None
    c = 0
    while move1 is None:
        move1, node = get_move_human(board, node)
        c += 1
    print("\n========================")
    
    # Atualizar o tabuleiro no pygame
    draw_board(screen)
    draw_pieces(screen, board, images)
    pygame.display.flip()

    if board.is_game_over():
        break
    
    # Jogada do GPT-4 (Pretas)
    move2 = None
    c = 0
    while move2 is None:
        move2, node = get_move_llm(chain1, move1, board, node, "black")
        c += 1
    print("\n========================")

    # Atualizar o tabuleiro no pygame
    draw_board(screen)
    draw_pieces(screen, board, images)
    pygame.display.flip()

# Fechar a janela do pygame
pygame.quit()

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